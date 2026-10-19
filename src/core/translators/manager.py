# -*- coding: utf-8 -*-
"""Translation coordinator and engine factory."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

from src.core.cache import TranslationCache
from src.core.glossary import GlossaryManager
from src.core.languages import engine_language_code
from src.core.syntax_guard import set_protected_terms
from src.core.translation_memory import TranslationMemory
from src.core.translators.ai_translator import (AISettings, GeminiTranslator, LocalLLMTranslator,
                                                OpenAITranslator)
from src.core.translators.base import (
    BaseTranslator,
    TranslationEngine,
    TranslationResult,
)
from src.core.translators.google import GoogleTranslator
from src.core.translators.bing import BingTranslator
from src.core.translators.network import NetworkSettings, ProxyPool
from src.core.translators.deepl import DeepLTranslator
from src.core.translators.libretranslate import LibreTranslateTranslator
from src.core.translators.services import PseudoTranslator
from src.utils.config import ConfigManager

logger = logging.getLogger(__name__)


def _engine_codes(engine: TranslationEngine, source_lang: str, target_lang: str) -> tuple[str, str]:
    """Canonical source/target codes converted to the engine's own spelling."""
    return (
        engine_language_code(source_lang, engine.value, source=True),
        engine_language_code(target_lang, engine.value),
    )


def _canonical(result: TranslationResult, source_lang: str, target_lang: str) -> TranslationResult:
    """Restore canonical codes on a result so cache and review never see engine dialects."""
    result.source_lang = source_lang
    result.target_lang = target_lang
    return result


# Upper bound of parallel batches per engine (further capped to 4 without proxies).
_ENGINE_CONCURRENCY_CAP: dict[TranslationEngine, int] = {
    TranslationEngine.GOOGLE: 32,
    TranslationEngine.BING: 3,
    TranslationEngine.DEEPL: 2,
    TranslationEngine.LIBRETRANSLATE: 2,
    TranslationEngine.PSEUDO: 1,
    TranslationEngine.LOCAL_LLM: 1,
}
# Hard per-batch limits (RenLocalizer values): Edge rejects >100 items per request.
_ENGINE_BATCH_CAPS: dict[TranslationEngine, int] = {
    TranslationEngine.GOOGLE: 1000,
    TranslationEngine.BING: 100,
}
_AI_ENGINES = frozenset({TranslationEngine.GEMINI, TranslationEngine.OPENAI, TranslationEngine.DEEPSEEK})


def _make_result(
    original: str, translated: str, sl: str, tl: str, engine: TranslationEngine,
    metadata: dict[str, Any] | None = None, error: str | None = None,
) -> TranslationResult:
    return TranslationResult(
        original_text=original, translated_text=translated, source_lang=sl, target_lang=tl,
        engine=engine, success=error is None, error=error, metadata=metadata or {},
    )


class TranslationManager:
    """Orchestrates translation engines, cache, translation memory and glossary."""

    def __init__(
        self,
        config: ConfigManager | None = None,
        cache: TranslationCache | None = None,
        glossary: GlossaryManager | None = None,
    ) -> None:
        self.config = config or ConfigManager()
        self.cache = cache or TranslationCache()
        self.glossary = glossary or GlossaryManager()
        self._translators: dict[TranslationEngine, BaseTranslator] = {}
        self._lock = threading.Lock()
        self.network = NetworkSettings.from_config(self.config)
        self.proxies = ProxyPool(self.network.proxies)
        self._memories: dict[tuple[str, str], TranslationMemory] = {}
        self.refresh_term_protection()

    def refresh_term_protection(self) -> None:
        """Push do-not-translate terms and glossary terms into the shared Syntax Guard.

        Both are hidden from engines; glossary terms are then replaced by
        ``GlossaryManager.apply``. Call after the glossary or the term list changes.
        """
        set_protected_terms(
            [t for t in self._text("protected_terms").splitlines() if t.strip()],
            glossary_terms=list(self.glossary.terms),
        )

    def reset_translators(self) -> None:
        """Drop cached engines and re-read network settings so new values take effect."""
        with self._lock:
            for translator in self._translators.values():
                translator.close()
            self._translators.clear()
            self.network = NetworkSettings.from_config(self.config)
            self.proxies = ProxyPool(self.network.proxies)
            self._memories.clear()
        self.refresh_term_protection()

    def concurrency_for(self, engine: TranslationEngine) -> int:
        """Parallel batches the runner may send to this engine."""
        if engine in _AI_ENGINES:
            ai_cap = int(self.config.get("ai_concurrency", 2) or 1)
            return self.network.effective_concurrency(max(1, ai_cap))
        return self.network.effective_concurrency(_ENGINE_CONCURRENCY_CAP.get(engine, 1))

    def get_translator(self, engine: TranslationEngine) -> BaseTranslator:
        """Get or lazily instantiate the requested translator engine (thread-safe)."""
        with self._lock:
            if engine not in self._translators:
                self._translators[engine] = self._build_translator(engine)
            return self._translators[engine]

    def _build_translator(self, engine: TranslationEngine) -> BaseTranslator:
        builders: dict[TranslationEngine, Callable[[], BaseTranslator]] = {
            TranslationEngine.GOOGLE: lambda: GoogleTranslator(self.network, proxies=self.proxies),
            TranslationEngine.BING: self._build_bing,
            TranslationEngine.OPENAI: lambda: OpenAITranslator(
                api_key=self._text("openai_key"),
                model=self._text("openai_model", "gpt-4o-mini"),
                base_url=self._text("openai_base_url") or None,  # OpenRouter & other compatible APIs
                settings=AISettings.from_config(self.config),
            ),
            TranslationEngine.GEMINI: lambda: GeminiTranslator(
                api_key=self._text("gemini_key"),
                model=self._text("gemini_model", "gemini-2.5-flash"),
                settings=AISettings.from_config(self.config),
            ),
            TranslationEngine.DEEPSEEK: lambda: OpenAITranslator(
                api_key=self._text("deepseek_key"), model=self._text("deepseek_model", "deepseek-chat"),
                base_url="https://api.deepseek.com", engine=TranslationEngine.DEEPSEEK,
                settings=AISettings.from_config(self.config),
            ),
            TranslationEngine.LOCAL_LLM: lambda: LocalLLMTranslator(
                base_url=self._text("local_llm_url", "http://localhost:11434/v1"),
                model=self._text("local_llm_model", "qwen2.5:latest"),
                settings=AISettings.from_config(self.config, local=True),
            ),
            TranslationEngine.DEEPL: self._build_deepl,
            TranslationEngine.LIBRETRANSLATE: lambda: LibreTranslateTranslator(
                url=self._text("libretranslate_url", "http://localhost:5000"),
                api_key=self._text("libretranslate_key"), settings=self.network, proxies=self.proxies,
            ),
            TranslationEngine.PSEUDO: PseudoTranslator,
        }
        if engine not in builders:
            # Never fall back to the pseudo engine silently: it would ship fake text.
            raise ValueError(f"Translation engine not implemented: {engine.value}")
        return builders[engine]()

    def _build_bing(self) -> BaseTranslator:
        """Bing with Google as fallback: independent request families fail independently."""
        bing = BingTranslator(self.network, proxies=self.proxies)
        bing.set_fallback(GoogleTranslator(self.network, proxies=self.proxies))
        return bing

    def _build_deepl(self) -> BaseTranslator:
        key = self._text("deepl_key")
        # DeepL convention: Free API keys end with ":fx"; everything else is Pro.
        return DeepLTranslator(
            api_key=key, is_pro=bool(key) and not key.endswith(":fx"),
            formality=self._text("deepl_formality", "default"), settings=self.network, proxies=self.proxies,
        )

    def _text(self, key: str, default: str = "") -> str:
        return str(self.config.get(key, default) or default).strip()

    def translate_text(
        self,
        text: str,
        source_lang: str = "auto",
        target_lang: str = "tr",
        engine_type: TranslationEngine = TranslationEngine.GOOGLE,
    ) -> TranslationResult:
        """Translate one string (cache, translation memory, then engine)."""
        return self.translate_batch([text], source_lang, target_lang, engine_type)[0]

    def translate_batch(
        self,
        texts: list[str],
        source_lang: str = "auto",
        target_lang: str = "tr",
        engine_type: TranslationEngine = TranslationEngine.GOOGLE,
    ) -> list[TranslationResult]:
        """Resolve each text offline when possible; send the rest to the engine in one batch."""
        results: list[TranslationResult | None] = [None] * len(texts)
        cached = self._cached_batch(texts, source_lang, target_lang, engine_type)
        pending = [
            i for i, text in enumerate(texts)
            if not self._resolve_offline(i, text, cached, results, source_lang, target_lang, engine_type)
        ]
        if pending:
            self._translate_with_engine(pending, texts, results, source_lang, target_lang, engine_type)
        return [
            r if r is not None else _make_result(texts[i], texts[i], source_lang, target_lang, engine_type,
                                                 error="Engine returned no result")
            for i, r in enumerate(results)
        ]

    def batch_size_for(self, engine: TranslationEngine, default: int) -> int:
        """Lines per batch: AI engines use ``ai_batch_size``, the others the general size.

        Two separate settings, as in RenLocalizer: machine-translation engines handle
        large batches, while LLMs degrade (skipped items, broken XML) on big prompts.
        Engine hard caps apply on top of the user's value.
        """
        if engine in _AI_ENGINES or engine is TranslationEngine.LOCAL_LLM:
            return max(1, int(self.config.get("ai_batch_size", 15) or 15))
        cap = _ENGINE_BATCH_CAPS.get(engine)
        return max(1, min(default, cap) if cap else default)

    def _cached_batch(
        self, texts: list[str], sl: str, tl: str, engine: TranslationEngine
    ) -> dict[str, str]:
        """Cached translations for a whole batch, fetched in one database round trip."""
        if not self.use_cache:
            return {}
        return self.cache.get_many([t for t in texts if t.strip()], sl, tl, engine.value)

    def _resolve_offline(
        self, index: int, text: str, cached: dict[str, str], results: list[TranslationResult | None],
        sl: str, tl: str, engine: TranslationEngine,
    ) -> bool:
        """Fill results[index] from blank text, the cache or the translation memory."""
        if not text.strip():
            results[index] = _make_result(text, text, sl, tl, engine, {"from_offline": True})
            return True
        hit = cached.get(text)
        if hit is not None and hit.strip() and self.glossary.covers(text, hit):
            results[index] = _make_result(
                text, self.glossary.apply(hit), sl, tl, engine, {"from_cache": True, "from_offline": True}
            )
            return True
        remembered = self._memory_for(sl, tl).lookup(text) if self._memory_enabled() else None
        if remembered and remembered.strip():
            results[index] = _make_result(
                text, self.glossary.apply(remembered), sl, tl, engine, {"from_memory": True, "from_offline": True}
            )
            return True
        return False

    def _translate_with_engine(
        self, pending: list[int], texts: list[str], results: list[TranslationResult | None],
        sl: str, tl: str, engine: TranslationEngine,
    ) -> None:
        translator = self.get_translator(engine)
        engine_src, engine_tgt = _engine_codes(engine, sl, tl)
        outputs = translator.translate_batch([texts[i] for i in pending], engine_src, engine_tgt)
        fresh: dict[str, str] = {}
        # Engines may return fewer results; translate_batch reports the gaps as failures.
        for index, output in zip(pending, outputs):
            result = _canonical(output, sl, tl)
            if result.success and not result.translated_text.strip():
                result.success = False
                result.error = result.error or "Engine returned empty translation"
            if result.success:
                fresh[result.original_text] = result.translated_text  # cached before the glossary
                result.translated_text = self.glossary.apply(result.translated_text)
            results[index] = result
        if self.use_cache and fresh:
            self.cache.set_many(fresh, sl, tl, engine.value)

    @property
    def use_cache(self) -> bool:
        return bool(self.config.get("use_cache", True))

    def _memory_enabled(self) -> bool:
        return bool(self.config.get("tm_enabled", False)) and bool(self._text("tm_files"))

    def _memory_for(self, sl: str, tl: str) -> TranslationMemory:
        """Translation memory for a language pair, loaded once and cached until reset."""
        key = (sl, tl)
        with self._lock:
            if key not in self._memories:
                fuzzy = bool(self.config.get("tm_fuzzy", False))
                threshold = float(self.config.get("tm_fuzzy_threshold", 0.9) or 0.9)
                files = [line for line in self._text("tm_files").splitlines() if line.strip()]
                self._memories[key] = TranslationMemory.load(files, sl, tl, threshold if fuzzy else None)
            return self._memories[key]

    def close(self) -> None:
        """Close all active translators (the cache keeps no open connection)."""
        with self._lock:
            translators = list(self._translators.values())
            self._translators.clear()
        for translator in translators:
            try:
                translator.close()
            except Exception as exc:  # shutdown must continue for the other engines
                logger.warning("Closing %s failed: %s", type(translator).__name__, exc)
