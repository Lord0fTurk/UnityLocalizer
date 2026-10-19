# -*- coding: utf-8 -*-
"""AI translation engines (OpenAI-compatible: OpenAI/OpenRouter/DeepSeek/Local LLM; Gemini).

All engines share one chat contract: a system prompt with the placeholder rules
(plus an optional user style guide) and either a single text or an XML batch
``<items><item id="N">…</item></items>``. Items missing from a batch reply are
retried one by one. Temperature, token limit, timeout, retries and pacing come
from ``AISettings``.
"""

from __future__ import annotations

import logging
import re
import time
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any

from src.core.languages import describe_for_prompt
from src.core.syntax_guard import UnitySyntaxGuard
from src.core.translators.base import BaseTranslator, TranslationEngine, TranslationResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a professional video game localization expert. Translate the text into {target_lang}. "
    "Do NOT translate code, markup, or placeholders such as <ph id=\"N\"/>, {{0}}, <color>, <b>, etc. "
    "Keep tone natural for video games. Output only the translation, without notes or explanations."
)
BATCH_INSTRUCTIONS = (
    "Translate the text of each <item id=\"N\">. Preserve every XML tag, ID and <ph id=\"...\"/> placeholder "
    "exactly. Output ONLY the translated <items>...</items> block, without markdown."
)
GEMINI_SAFETY_LEVELS = ("BLOCK_NONE", "BLOCK_ONLY_HIGH", "BLOCK_MEDIUM_AND_ABOVE", "BLOCK_LOW_AND_ABOVE")
_GEMINI_CATEGORIES = (
    "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT",
)
_CODE_FENCE = re.compile(r"^```(?:xml)?\s*|\s*```$", re.MULTILINE)
_XML_ITEM = re.compile(r'<item\s+id=["\']?(\d+)["\']?>(.*?)</item>', re.DOTALL)
# HTTP statuses no retry can fix for the whole session: bad key, no billing, forbidden, unknown model.
_SESSION_FATAL_STATUS = frozenset({401, 402, 403, 404})


class RequestRejectedError(RuntimeError):
    """The API refused this particular request (HTTP 400, e.g. too long); retrying it is pointless."""


class FatalEngineError(RuntimeError):
    """The engine cannot work this session (invalid key, exhausted quota, missing model)."""


def _http_status(exc: Exception) -> int | None:
    """Status code of an SDK error (``status_code`` in openai, ``code`` in google-genai)."""
    for attribute in ("status_code", "code"):
        value = getattr(exc, attribute, None)
        if isinstance(value, int):
            return value
    return None


def _classify(exc: Exception) -> type[RuntimeError] | None:
    """Error class to raise without retrying, or None for transient errors worth a retry."""
    status = _http_status(exc)
    if status in _SESSION_FATAL_STATUS or "insufficient_quota" in str(exc):
        return FatalEngineError
    if status == 400:
        return RequestRejectedError
    return None


def _clamp(value: Any, default: float, low: float, high: float) -> float:
    try:
        return max(low, min(float(value), high))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class AISettings:
    """Generation and transport options shared by every AI engine."""

    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: float = 120.0
    retries: int = 2
    request_delay: float = 0.5
    style_guide: str = ""
    gemini_safety: str = "BLOCK_NONE"

    @classmethod
    def from_config(cls, config: Any, local: bool = False) -> AISettings:
        safety = str(config.get("gemini_safety", "BLOCK_NONE"))
        timeout_key = "local_llm_timeout" if local else "ai_timeout"
        default_timeout = 300.0 if local else 120.0
        return cls(
            temperature=_clamp(config.get("ai_temperature", 0.3), 0.3, 0.0, 1.0),
            max_tokens=int(_clamp(config.get("ai_max_tokens", 4096), 4096, 256, 65536)),
            timeout=_clamp(config.get(timeout_key, default_timeout), default_timeout, 10.0, 1800.0),
            retries=int(_clamp(config.get("ai_retries", 2), 2, 0, 5)),
            request_delay=_clamp(config.get("ai_request_delay", 0.5), 0.5, 0.0, 30.0),
            style_guide=str(config.get("ai_custom_prompt", "")).strip(),
            gemini_safety=safety if safety in GEMINI_SAFETY_LEVELS else "BLOCK_NONE",
        )


def build_system_prompt(target_lang: str, style_guide: str) -> str:
    """Built-in rules always apply; the user's style guide is appended, never replacing them."""
    prompt = SYSTEM_PROMPT.format(target_lang=describe_for_prompt(target_lang))
    if style_guide:
        prompt += f"\n\nStyle guide from the user (follow it unless it conflicts with the rules above):\n{style_guide}"
    return prompt


def parse_xml_items(content: str) -> dict[int, str]:
    """Translated items by id from a model reply (code fences tolerated)."""
    cleaned = _CODE_FENCE.sub("", content.strip())
    return {int(item_id): text.strip() for item_id, text in _XML_ITEM.findall(cleaned)}


class ChatTranslator(BaseTranslator):
    """Shared single/XML-batch logic; subclasses only implement ``_complete``."""

    engine_type: TranslationEngine = TranslationEngine.OPENAI

    def __init__(self, api_key: str, model: str, settings: AISettings | None = None) -> None:
        super().__init__(api_key=api_key)
        self.model = model
        self.settings = settings or AISettings()
        self._client: Any = None
        # Set by an unrecoverable error; later calls fail at once instead of hammering the API.
        self._fatal_error: str | None = None

    @abstractmethod
    def _complete(self, system: str, user: str) -> str:
        """Send one chat request and return the model's text."""

    def close(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            try:
                self._client.close()
            except Exception as exc:
                logger.debug("Closing %s client failed: %s", self.engine_type.value, exc)

    def _ready(self) -> bool:
        return self._client is not None and bool(self.api_key)

    def _ask(self, system: str, user: str) -> str:
        """Paced request with retries and linear backoff for transient errors only.

        Raises FatalEngineError (remembered for this translator's lifetime, i.e. until
        settings change), RequestRejectedError, or RuntimeError after the last retry.
        """
        if self._fatal_error:
            raise FatalEngineError(self._fatal_error)
        last_error: Exception | None = None
        for attempt in range(self.settings.retries + 1):
            if self.settings.request_delay > 0:
                time.sleep(self.settings.request_delay)
            try:
                return self._complete(system, user)
            except Exception as exc:  # SDKs raise many error types (auth, quota, network, parse)
                last_error = exc
                self._raise_if_unretryable(exc)
                logger.warning("%s request failed (attempt %d): %s", self.engine_type.value, attempt + 1, exc)
                if attempt < self.settings.retries:
                    time.sleep(2.0 * (attempt + 1))
        raise RuntimeError(str(last_error))

    def _raise_if_unretryable(self, exc: Exception) -> None:
        """Stop retrying on errors a retry cannot fix; remember session-fatal ones."""
        error_class = _classify(exc)
        if error_class is None:
            return
        if error_class is FatalEngineError:
            self._fatal_error = f"{self.engine_type.value}: {exc}"
            logger.error("%s disabled for this session: %s", self.engine_type.value, exc)
        raise error_class(str(exc)) from exc

    def translate(self, text: str, source_lang: str = "auto", target_lang: str = "tr") -> TranslationResult:
        if not self._ready():
            return self._result(text, text, source_lang, target_lang, "API key missing or client not initialized")
        protected, tags = UnitySyntaxGuard.protect(text, mode="xml")
        try:
            raw = self._ask(build_system_prompt(target_lang, self.settings.style_guide), protected)
        except RuntimeError as exc:
            return self._result(text, text, source_lang, target_lang, str(exc))
        restored = UnitySyntaxGuard.restore(raw.strip(), tags, mode="xml")
        if not restored.strip():
            return self._result(text, text, source_lang, target_lang, "Empty response from model")
        return self._result(text, restored, source_lang, target_lang)

    def translate_batch(
        self, texts: list[str], source_lang: str = "auto", target_lang: str = "tr"
    ) -> list[TranslationResult]:
        """XML batch request; items the model skipped are retried individually.

        A batch the API refused as a request (HTTP 400, e.g. too long) is split into
        single items. Any other failure already used up its retries (or is fatal),
        so every item is reported failed instead of multiplying requests by the batch size.
        """
        if len(texts) <= 1 or not self._ready():
            return [self.translate(t, source_lang, target_lang) for t in texts]
        protected = [UnitySyntaxGuard.protect(t, mode="xml") for t in texts]
        payload = (
            "<items>\n"
            + "\n".join(f'<item id="{i}">{p.replace("</item>", "&lt;/item&gt;")}</item>' for i, (p, _) in enumerate(protected))
            + "\n</items>"
        )
        system = build_system_prompt(target_lang, self.settings.style_guide) + "\n\n" + BATCH_INSTRUCTIONS
        try:
            items = parse_xml_items(self._ask(system, payload))
        except RequestRejectedError as exc:
            logger.warning("%s rejected the batch (%s); translating items one by one", self.engine_type.value, exc)
            items = {}
        except RuntimeError as exc:
            logger.error("%s batch failed: %s", self.engine_type.value, exc)
            return [self._result(t, t, source_lang, target_lang, str(exc)) for t in texts]
        return [
            self._result(
                t,
                UnitySyntaxGuard.restore(items[i].replace("&lt;/item&gt;", "</item>"), protected[i][1], mode="xml"),
                source_lang,
                target_lang,
            )
            if items.get(i) else self.translate(t, source_lang, target_lang)
            for i, t in enumerate(texts)
        ]

    def _result(self, original: str, translated: str, sl: str, tl: str, error: str | None = None) -> TranslationResult:
        return TranslationResult(
            original_text=original, translated_text=translated, source_lang=sl, target_lang=tl,
            engine=self.engine_type, success=error is None, error=error,
        )


class OpenAITranslator(ChatTranslator):
    """OpenAI-compatible chat API: OpenAI, OpenRouter (custom base URL) and DeepSeek."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        engine: TranslationEngine = TranslationEngine.OPENAI,
        settings: AISettings | None = None,
    ) -> None:
        super().__init__(api_key, model, settings)
        self.engine_type = engine
        self.base_url = base_url or None
        try:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key, base_url=self.base_url, timeout=self.settings.timeout, max_retries=0)
        except Exception as exc:  # missing package or invalid configuration
            logger.error("Failed to initialize OpenAI client: %s", exc)

    def _complete(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
        )
        choices = getattr(resp, "choices", None)
        if not choices:
            raise RuntimeError("Model response contained no choices")
        msg = getattr(choices[0], "message", None)
        return (getattr(msg, "content", None) or "") if msg is not None else ""


class GeminiTranslator(ChatTranslator):
    """Google Gemini through the google-genai SDK with configurable safety threshold."""

    engine_type = TranslationEngine.GEMINI

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", settings: AISettings | None = None) -> None:
        super().__init__(api_key, model, settings)
        try:
            from google import genai
            from google.genai import types

            self._types = types
            self._client = genai.Client(
                api_key=api_key, http_options=types.HttpOptions(timeout=int(self.settings.timeout * 1000))
            )
        except Exception as exc:  # missing package or invalid configuration
            logger.error("Failed to initialize Google GenAI client: %s", exc)

    def _complete(self, system: str, user: str) -> str:
        types = self._types
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=self.settings.temperature,
            max_output_tokens=self.settings.max_tokens,
            safety_settings=[
                types.SafetySetting(category=category, threshold=self.settings.gemini_safety)
                for category in _GEMINI_CATEGORIES
            ],
        )
        resp = self._client.models.generate_content(model=self.model, contents=user, config=config)
        return getattr(resp, "text", None) or ""


class LocalLLMTranslator(OpenAITranslator):
    """Local LLM (Ollama, LM Studio, vLLM) through their OpenAI-compatible endpoint."""

    def __init__(
        self, base_url: str = "http://localhost:11434/v1", model: str = "qwen2.5:latest",
        settings: AISettings | None = None,
    ) -> None:
        super().__init__(
            api_key="ollama_local", model=model, base_url=_openai_base(base_url),
            engine=TranslationEngine.LOCAL_LLM, settings=settings,
        )


def _openai_base(url: str) -> str:
    """Ollama/LM Studio expose the OpenAI API under /v1; accept the bare host too."""
    cleaned = url.strip().rstrip("/")
    return cleaned if cleaned.endswith("/v1") else f"{cleaned}/v1"
