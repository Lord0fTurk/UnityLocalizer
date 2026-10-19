# -*- coding: utf-8 -*-
"""DeepL API engine: 50 texts per request, XML tag handling, formality and retries."""

from __future__ import annotations

import logging
import time

import requests

from src.core.syntax_guard import UnitySyntaxGuard
from src.core.translators.base import BaseTranslator, TranslationEngine, TranslationResult
from src.core.translators.network import NetworkSettings, ProxyPool

logger = logging.getLogger(__name__)

DEEPL_FREE_URL = "https://api-free.deepl.com/v2/translate"
DEEPL_PRO_URL = "https://api.deepl.com/v2/translate"
DEEPL_MAX_TEXTS = 50
# "prefer_*" variants never fail for languages without formality support.
FORMALITY_VALUES = {"default": None, "more": "prefer_more", "less": "prefer_less"}
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504, 529})


class DeepLTranslator(BaseTranslator):
    """DeepL Free/Pro (Free keys end with ':fx')."""

    def __init__(
        self, api_key: str, is_pro: bool = False, formality: str = "default",
        settings: NetworkSettings | None = None, proxies: ProxyPool | None = None,
    ) -> None:
        super().__init__(api_key=api_key)
        self.endpoint = DEEPL_PRO_URL if is_pro else DEEPL_FREE_URL
        self.formality = FORMALITY_VALUES.get(formality)
        self.settings = settings or NetworkSettings()
        self.proxies = proxies or ProxyPool(self.settings.proxies)
        self.session = requests.Session()

    def translate(self, text: str, source_lang: str = "auto", target_lang: str = "tr") -> TranslationResult:
        return self.translate_batch([text], source_lang, target_lang)[0]

    def translate_batch(
        self, texts: list[str], source_lang: str = "auto", target_lang: str = "tr"
    ) -> list[TranslationResult]:
        if not self.api_key:
            return [self._result(t, t, source_lang, target_lang, "DeepL API key required") for t in texts]
        results: list[TranslationResult] = []
        for start in range(0, len(texts), DEEPL_MAX_TEXTS):
            results.extend(self._translate_chunk(texts[start : start + DEEPL_MAX_TEXTS], source_lang, target_lang))
        return results

    def _translate_chunk(self, texts: list[str], sl: str, tl: str) -> list[TranslationResult]:
        protected = [UnitySyntaxGuard.protect(t, mode="xml") for t in texts]
        body: dict[str, object] = {"text": [p for p, _ in protected], "target_lang": tl, "tag_handling": "xml"}
        if sl and sl != "auto":
            body["source_lang"] = sl
        if self.formality:
            body["formality"] = self.formality
        try:
            translations = self._post(body)
        except RuntimeError as exc:
            return [self._result(t, t, sl, tl, str(exc)) for t in texts]
        if len(translations) != len(texts):
            return [self._result(t, t, sl, tl, "Unexpected DeepL response length") for t in texts]
        return [
            self._result(t, UnitySyntaxGuard.restore(translations[i], protected[i][1], mode="xml"), sl, tl)
            for i, t in enumerate(texts)
        ]

    def _post(self, body: dict[str, object]) -> list[str]:
        """POST with retries on 429/5xx; 456 (quota exceeded) and 4xx are final."""
        headers = {"Authorization": f"DeepL-Auth-Key {self.api_key}"}
        last_error = "unknown error"
        max_attempts = max(1, self.settings.max_retries)
        for attempt in range(max_attempts):
            if self.settings.request_delay > 0:
                time.sleep(self.settings.request_delay)
            proxy, proxy_map = self.proxies.requests_proxies() if self.proxies else (None, None)
            try:
                resp = self.session.post(self.endpoint, headers=headers, json=body,
                                         timeout=self.settings.timeout, proxies=proxy_map)
            except requests.RequestException as exc:
                self.proxies.mark_failed(proxy)
                last_error = f"network: {exc}"
            else:
                if resp.status_code == 200:
                    try:
                        payload = resp.json()
                        items = payload.get("translations", []) if isinstance(payload, dict) else []
                        self.proxies.mark_success(proxy)
                        return [str(item.get("text", "")) for item in items if isinstance(item, dict)]
                    except ValueError as exc:
                        self.proxies.mark_failed(proxy)
                        last_error = f"invalid JSON: {exc}"
                else:
                    self.proxies.mark_failed(proxy)
                    last_error = (
                        "DeepL quota exceeded (HTTP 456)"
                        if resp.status_code == 456
                        else f"HTTP {resp.status_code}: {resp.text[:200]}"
                    )
                    if resp.status_code not in _RETRYABLE_STATUS:
                        break
            if attempt < max_attempts - 1:
                time.sleep(2.0 * (attempt + 1))
        logger.error("DeepL request failed: %s", last_error)
        raise RuntimeError(last_error)

    def close(self) -> None:
        self.session.close()

    @staticmethod
    def _result(original: str, translated: str, sl: str, tl: str, error: str | None = None) -> TranslationResult:
        return TranslationResult(
            original_text=original, translated_text=translated, source_lang=sl, target_lang=tl,
            engine=TranslationEngine.DEEPL, success=error is None, error=error,
        )
