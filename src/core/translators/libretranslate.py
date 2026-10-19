# -*- coding: utf-8 -*-
"""LibreTranslate engine (self-hosted or managed instance, optional API key)."""

from __future__ import annotations

import logging
import time

import requests

from src.core.syntax_guard import UnitySyntaxGuard
from src.core.translators.base import BaseTranslator, TranslationEngine, TranslationResult
from src.core.translators.network import NetworkSettings, ProxyPool

logger = logging.getLogger(__name__)

LIBRE_MAX_TEXTS = 50


class LibreTranslateTranslator(BaseTranslator):
    """POST {url}/translate with a list of texts (LibreTranslate >= 1.3 batch API)."""

    def __init__(
        self, url: str, api_key: str = "", settings: NetworkSettings | None = None,
        proxies: ProxyPool | None = None,
    ) -> None:
        super().__init__(api_key=api_key)
        self.url = url.strip().rstrip("/") + "/translate"
        self.settings = settings or NetworkSettings()
        self.proxies = proxies or ProxyPool(self.settings.proxies)
        self.session = requests.Session()

    def translate(self, text: str, source_lang: str = "auto", target_lang: str = "tr") -> TranslationResult:
        return self.translate_batch([text], source_lang, target_lang)[0]

    def translate_batch(
        self, texts: list[str], source_lang: str = "auto", target_lang: str = "tr"
    ) -> list[TranslationResult]:
        results: list[TranslationResult] = []
        for start in range(0, len(texts), LIBRE_MAX_TEXTS):
            results.extend(self._chunk(texts[start : start + LIBRE_MAX_TEXTS], source_lang, target_lang))
        return results

    def _chunk(self, texts: list[str], sl: str, tl: str) -> list[TranslationResult]:
        protected = [UnitySyntaxGuard.protect(t) for t in texts]
        body = {"q": [p for p, _ in protected], "source": sl or "auto", "target": tl, "format": "text"}
        if self.api_key:
            body["api_key"] = self.api_key
        try:
            translated = self._post(body)
        except RuntimeError as exc:
            return [self._result(t, t, sl, tl, str(exc)) for t in texts]
        if len(translated) != len(texts):
            return [self._result(t, t, sl, tl, "Unexpected LibreTranslate response length") for t in texts]
        return [self._result(t, UnitySyntaxGuard.restore(translated[i], protected[i][1]), sl, tl)
                for i, t in enumerate(texts)]

    def _post(self, body: dict[str, object]) -> list[str]:
        last_error = "unknown error"
        max_attempts = max(1, self.settings.max_retries)
        for attempt in range(max_attempts):
            if self.settings.request_delay > 0:
                time.sleep(self.settings.request_delay)
            proxy, proxy_map = self.proxies.requests_proxies() if self.proxies else (None, None)
            try:
                resp = self.session.post(self.url, json=body, timeout=self.settings.timeout, proxies=proxy_map)
            except requests.RequestException as exc:
                self.proxies.mark_failed(proxy)
                last_error = f"network: {exc}"
            else:
                if resp.status_code == 200:
                    try:
                        payload = resp.json()
                        value = payload.get("translatedText", []) if isinstance(payload, dict) else []
                        self.proxies.mark_success(proxy)
                        return [str(v) for v in value] if isinstance(value, list) else [str(value)]
                    except ValueError as exc:
                        self.proxies.mark_failed(proxy)
                        last_error = f"invalid JSON: {exc}"
                else:
                    self.proxies.mark_failed(proxy)
                    last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    if resp.status_code not in (429, 500, 502, 503, 504):
                        break
            if attempt < max_attempts - 1:
                time.sleep(2.0 * (attempt + 1))
        logger.error("LibreTranslate request failed: %s", last_error)
        raise RuntimeError(last_error)

    def close(self) -> None:
        self.session.close()

    @staticmethod
    def _result(original: str, translated: str, sl: str, tl: str, error: str | None = None) -> TranslationResult:
        return TranslationResult(
            original_text=original, translated_text=translated, source_lang=sl, target_lang=tl,
            engine=TranslationEngine.LIBRETRANSLATE, success=error is None, error=error,
        )
