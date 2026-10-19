# -*- coding: utf-8 -*-
"""Keyless Microsoft Translator through the Edge browser's web-translation endpoint.

Contract (as used by RenLocalizer in production):
    POST https://edge.microsoft.com/translate/translatetext?isEnterpriseClient=false&to=<lang>[&from=<lang>]
    body: JSON array of strings
    resp: [{"translations": [{"text": "...", "to": "tr"}], ...}, ...]

Requests are chunked by item count and character budget, retried with backoff
on 429/network errors, split in half when the service reports an oversized
request, and verified for response length. Items that still fail are handed to
the fallback translator (Google), whose request family is independent of Bing's.
"""

from __future__ import annotations

import json
import logging
import random
import time

import requests

from src.core.constants import (
    BING_EDGE_TRANSLATE_ENDPOINT,
    BING_MAX_CHARS_PER_REQUEST,
    BING_MAX_ITEMS_PER_REQUEST,
    USER_AGENTS,
)
from src.core.languages import canonical_from_bing, engine_language_code
from src.core.syntax_guard import UnitySyntaxGuard
from src.core.translators.base import BaseTranslator, TranslationEngine, TranslationResult
from src.core.translators.network import NetworkSettings, ProxyPool

logger = logging.getLogger(__name__)

RETRY_DELAYS = (2.0, 4.0, 8.0)
MIN_TIMEOUT = 60.0  # large chunks legitimately take tens of seconds
_SIZE_ERROR = "maximum allowed translation size"


class BingChunkError(Exception):
    """A chunk failed after retries (message is the last error)."""


class BingTranslator(BaseTranslator):
    """Microsoft Edge keyless translation with chunking, retries and Google fallback."""

    def __init__(self, settings: NetworkSettings | None = None, proxies: ProxyPool | None = None) -> None:
        super().__init__()
        self.settings = settings or NetworkSettings()
        self.proxies = proxies or ProxyPool(self.settings.proxies)
        self.session = requests.Session()

    # ── public API ───────────────────────────────────────────────────────

    def translate(self, text: str, source_lang: str = "auto", target_lang: str = "tr") -> TranslationResult:
        return self.translate_batch([text], source_lang, target_lang)[0]

    def translate_batch(
        self, texts: list[str], source_lang: str = "auto", target_lang: str = "tr"
    ) -> list[TranslationResult]:
        """Translate texts; failures fall back to the secondary engine when one is set."""
        if not texts:
            return []
        protected = [UnitySyntaxGuard.protect(t) for t in texts]
        raw: list[str | None] = [None] * len(texts)
        errors: dict[int, str] = {}
        for indices in self._chunks([p for p, _ in protected]):
            self._translate_indices(indices, protected, raw, errors, source_lang, target_lang)
        results = [
            self._result(t, UnitySyntaxGuard.restore(raw[i], protected[i][1]), source_lang, target_lang)
            if raw[i] is not None else None
            for i, t in enumerate(texts)
        ]
        return self._fill_failures(texts, results, errors, source_lang, target_lang)

    def close(self) -> None:
        self.session.close()
        if self.fallback_translator is not None:
            self.fallback_translator.close()

    # ── chunking & requests ──────────────────────────────────────────────

    @staticmethod
    def _chunks(bodies: list[str]) -> list[list[int]]:
        chunks: list[list[int]] = []
        current: list[int] = []
        chars = 0
        for index, body in enumerate(bodies):
            if current and (len(current) >= BING_MAX_ITEMS_PER_REQUEST or chars + len(body) > BING_MAX_CHARS_PER_REQUEST):
                chunks.append(current)
                current, chars = [], 0
            current.append(index)
            chars += len(body)
        if current:
            chunks.append(current)
        return chunks

    def _translate_indices(
        self, indices: list[int], protected: list[tuple[str, list[str]]],
        raw: list[str | None], errors: dict[int, str], sl: str, tl: str,
    ) -> None:
        """Translate one chunk in place; halves the chunk when the service says it is too large."""
        payload = [protected[i][0] for i in indices]
        try:
            translations = self._post_with_retries(payload, sl, tl)
        except BingChunkError as exc:
            if _SIZE_ERROR in str(exc).lower() and len(indices) > 1:
                middle = len(indices) // 2
                self._translate_indices(indices[:middle], protected, raw, errors, sl, tl)
                self._translate_indices(indices[middle:], protected, raw, errors, sl, tl)
                return
            logger.warning("Bing chunk of %d item(s) failed: %s", len(indices), exc)
            errors.update({i: str(exc) for i in indices})
            return
        for index, translated in zip(indices, translations):
            if translated is None:
                errors[index] = "Missing translation in Bing response"
            else:
                raw[index] = translated

    def _post_with_retries(self, payload: list[str], sl: str, tl: str) -> list[str | None]:
        """POST a chunk; retries 429, 5xx and network errors with 2s/4s/8s backoff."""
        last_error = "unknown error"
        for attempt in range(max(1, self.settings.max_retries)):
            try:
                return self._post(payload, sl, tl)
            except BingChunkError as exc:
                last_error = str(exc)
                if not _is_retryable(last_error):
                    break
            if attempt < self.settings.max_retries - 1:
                time.sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
        raise BingChunkError(last_error)

    def _post(self, payload: list[str], sl: str, tl: str) -> list[str | None]:
        params = {"isEnterpriseClient": "false", "to": tl}
        if sl and sl != "auto":
            params["from"] = sl
        if self.settings.request_delay > 0:
            time.sleep(self.settings.request_delay)
        proxy, proxy_map = self.proxies.requests_proxies() if self.proxies else (None, None)
        try:
            resp = self.session.post(
                BING_EDGE_TRANSLATE_ENDPOINT, params=params,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=_headers(), proxies=proxy_map, timeout=max(self.settings.timeout, MIN_TIMEOUT),
            )
        except requests.RequestException as exc:
            self.proxies.mark_failed(proxy)
            raise BingChunkError(f"network: {exc}") from exc
        if resp.status_code != 200:
            self.proxies.mark_failed(proxy)
            raise BingChunkError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        self.proxies.mark_success(proxy)
        return _parse_response(resp, len(payload))

    # ── results ──────────────────────────────────────────────────────────

    def _fill_failures(
        self, texts: list[str], results: list[TranslationResult | None],
        errors: dict[int, str], sl: str, tl: str,
    ) -> list[TranslationResult]:
        """Delegate failed items to the fallback engine; report the rest as failures."""
        failed = [i for i, r in enumerate(results) if r is None]
        if failed and self.fallback_translator is not None:
            logger.warning("Bing: %d item(s) failed; delegating to %s", len(failed),
                           type(self.fallback_translator).__name__)
            fb_sl = engine_language_code(canonical_from_bing(sl), "google", source=True)
            fb_tl = engine_language_code(canonical_from_bing(tl), "google")
            try:
                fallback = self.fallback_translator.translate_batch([texts[i] for i in failed], fb_sl, fb_tl)
            except Exception as exc:  # the fallback is best-effort; its own errors are logged
                logger.warning("Bing fallback failed: %s", exc)
                fallback = []
            for index, fb in zip(failed, fallback):
                if fb.success and fb.translated_text.strip():
                    results[index] = self._result(texts[index], fb.translated_text, sl, tl)
        return [
            r if r is not None else self._result(texts[i], texts[i], sl, tl, errors.get(i, "Bing translation failed"))
            for i, r in enumerate(results)
        ]

    @staticmethod
    def _result(original: str, translated: str, sl: str, tl: str, error: str | None = None) -> TranslationResult:
        return TranslationResult(
            original_text=original, translated_text=translated, source_lang=sl, target_lang=tl,
            engine=TranslationEngine.BING, success=error is None, error=error,
        )


def _headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": random.choice(USER_AGENTS),
        "Origin": "https://www.bing.com",
        "Referer": "https://www.bing.com/",
    }


def _is_retryable(error: str) -> bool:
    """429, server errors and network failures are transient; 4xx (bad language, size) are not."""
    return error.startswith(("HTTP 429", "HTTP 5", "network:", "Unexpected"))


def _parse_response(resp: requests.Response, expected: int) -> list[str | None]:
    """Per-item translations; the response must contain exactly one entry per input."""
    try:
        data = resp.json()
        if isinstance(data, str):
            data = json.loads(data)
    except ValueError as exc:
        raise BingChunkError(f"Unexpected response body: {exc}") from exc
    if not isinstance(data, list) or len(data) != expected:
        raise BingChunkError(f"Unexpected response shape ({len(data) if isinstance(data, list) else '?'} of {expected})")
    out: list[str | None] = []
    for item in data:
        try:
            out.append(item["translations"][0]["text"])
        except (KeyError, IndexError, TypeError):
            out.append(None)
    return out
