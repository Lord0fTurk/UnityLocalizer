# -*- coding: utf-8 -*-
"""Google Translate engine: health-aware routing across four endpoint families.

Batch path (per slice of <= 50 items / 8000 chars):
  1. PRIMARY + separator: all lines joined by a separator in ONE POST to
     /translate_a/single (fastest, cheapest); verified for count, bleeding and
     separator remnants before it is trusted.
  2. BATCHEXECUTE: true multi-item RPC in one round-trip.
  3. Per item through the single path.
Single path: PRIMARY -> CLIENTS5 -> BATCHEXECUTE -> LINGVA, skipping families the
router has benched. Bulk results that lost a placeholder are retried one by one,
and (optionally) results Google returned unchanged get a second opinion.
"""

from __future__ import annotations

import logging
import re
import time

from src.core.constants import GOOGLE_SEPARATOR_MAX_CHARS, GOOGLE_SEPARATOR_MAX_ITEMS
from src.core.syntax_guard import TOKEN_RE, UnitySyntaxGuard
from src.core.translators.base import BaseTranslator, TranslationEngine, TranslationResult
from src.core.translators.google_transport import (
    GET_SAFE_CHARS,
    GoogleTransport,
    RateLimitedError,
    TransportError,
)
from src.core.translators.network import NetworkSettings, ProxyPool
from src.core.translators.router import EndpointRouter

logger = logging.getLogger(__name__)

SEPARATOR = "\n|||RNLSEP999|||\n"
_SEPARATOR_SPLIT = re.compile(r"\s*\|\|\|\s*RNLSEP999\s*\|\|\|\s*")
_SEPARATOR_REMNANTS = ("|||", "RNLSEP")
MAX_INDIVIDUAL_RECOVERY = 30
MAX_AGGRESSIVE_RETRY = 100
_SENTENCE_END = re.compile(r"[.!?。！？]+\s*")


class FamilyUnavailableError(TransportError):
    """A family was skipped (e.g. primary breaker open) — not a failure to count."""


def _last_sentence_end(window: str) -> int:
    ends = [m.end() for m in _SENTENCE_END.finditer(window)]
    return ends[-1] if ends else 0


def _best_cut(text: str, limit: int) -> int:
    """Cut position <= limit preferring line, sentence, then word boundaries."""
    window = text[:limit]
    for cut in (window.rfind("\n") + 1, _last_sentence_end(window), window.rfind(" ") + 1):
        if cut > limit // 2:
            return cut
    token_start = window.rfind("⟦")
    if token_start > window.rfind("⟧"):  # never split a ⟦ULPH_n⟧ placeholder
        return token_start or limit
    return limit


def split_long_text(text: str, limit: int) -> list[str]:
    """Split text into chunks <= limit; joining the chunks reproduces the input exactly."""
    chunks: list[str] = []
    rest = text
    while len(rest) > limit:
        cut = _best_cut(rest, limit)
        chunks.append(rest[:cut])
        rest = rest[cut:]
    chunks.append(rest)
    return chunks


def _keep_edges(original: str, translated: str) -> str:
    """Re-apply the original leading/trailing whitespace the separator path strips."""
    lead = original[: len(original) - len(original.lstrip())]
    trail = original[len(original.rstrip()):]
    return f"{lead}{translated.strip()}{trail}"


def _has_letters(text: str) -> bool:
    visible = TOKEN_RE.sub("", UnitySyntaxGuard.protect(text)[0])
    return any(ch.isalpha() for ch in visible)


class GoogleTranslator(BaseTranslator):
    """Keyless Google Translate with IP-aware throttling and family failover."""

    def __init__(
        self,
        settings: NetworkSettings | None = None,
        router: EndpointRouter | None = None,
        transport: GoogleTransport | None = None,
        proxies: ProxyPool | None = None,
    ) -> None:
        super().__init__()
        self.settings = settings or NetworkSettings()
        self.router = router or EndpointRouter()
        self.transport = transport or GoogleTransport(self.settings, proxies)

    # ── public API ───────────────────────────────────────────────────────

    def translate(self, text: str, source_lang: str = "auto", target_lang: str = "tr") -> TranslationResult:
        """Translate one string through the single-item family chain."""
        if not text.strip():
            return self._result(text, text, source_lang, target_lang)
        protected, tags = UnitySyntaxGuard.protect(text)
        try:
            raw = self._translate_protected(protected, source_lang, target_lang)
        except TransportError as exc:
            return self._result(text, text, source_lang, target_lang, error=str(exc))
        return self._result(text, UnitySyntaxGuard.restore(raw, tags), source_lang, target_lang)

    def translate_batch(
        self, texts: list[str], source_lang: str = "auto", target_lang: str = "tr"
    ) -> list[TranslationResult]:
        """Translate many strings with bulk paths first, then per-item fallback and repair."""
        protected = [UnitySyntaxGuard.protect(t) for t in texts]
        bodies = [p for p, _ in protected]
        raw: list[str | None] = [None] * len(texts)
        errors: dict[int, str] = {}
        bulk: set[int] = set()
        for indices in self._slices(bodies):
            self._translate_slice(indices, bodies, raw, errors, bulk, source_lang, target_lang)
        restored = [
            UnitySyntaxGuard.restore(r, protected[i][1]) if r is not None else None for i, r in enumerate(raw)
        ]
        self._recover_integrity(texts, restored, bulk, source_lang, target_lang)
        if self.settings.aggressive_retry:
            self._retry_unchanged(texts, restored, source_lang, target_lang)
        return [
            self._result(t, restored[i], source_lang, target_lang)
            if restored[i] is not None
            else self._result(t, t, source_lang, target_lang, error=errors.get(i, "Google translation failed"))
            for i, t in enumerate(texts)
        ]

    def close(self) -> None:
        self.transport.close()

    # ── batch helpers ────────────────────────────────────────────────────

    @staticmethod
    def _slices(bodies: list[str]) -> list[list[int]]:
        """Group indices so each slice fits the separator request limits."""
        slices: list[list[int]] = []
        current: list[int] = []
        chars = 0
        for index, body in enumerate(bodies):
            if current and (len(current) >= GOOGLE_SEPARATOR_MAX_ITEMS or chars + len(body) > GOOGLE_SEPARATOR_MAX_CHARS):
                slices.append(current)
                current, chars = [], 0
            current.append(index)
            chars += len(body)
        if current:
            slices.append(current)
        return slices

    def _translate_slice(
        self, indices: list[int], bodies: list[str], raw: list[str | None],
        errors: dict[int, str], bulk: set[int], sl: str, tl: str,
    ) -> None:
        """Fill raw[] for one slice: separator, then batchexecute, then single items."""
        texts = [bodies[i] for i in indices]
        translated = self._try_separator(texts, sl, tl) if len(texts) > 1 else None
        if translated is None and len(texts) > 1:
            translated = self._try_batchexecute(texts, sl, tl)
        if translated is not None:
            for index, value in zip(indices, translated):
                raw[index] = value
                bulk.add(index)
            return
        for index in indices:
            try:
                raw[index] = self._translate_protected(bodies[index], sl, tl)
            except TransportError as exc:
                errors[index] = str(exc)

    def _try_separator(self, texts: list[str], sl: str, tl: str) -> list[str] | None:
        """One POST for the whole slice; None when the reply cannot be split safely."""
        if not self.router.is_family_available(EndpointRouter.FAMILY_PRIMARY):
            return None
        try:
            combined = self._primary(SEPARATOR.join(texts), sl, tl)
        except (TransportError, RateLimitedError) as exc:
            logger.debug("Separator batch failed: %s", exc)
            return None
        parts = _SEPARATOR_SPLIT.split(combined.strip())
        if len(parts) != len(texts):
            logger.debug("Separator split mismatch: expected %d, got %d", len(texts), len(parts))
            return None
        for original, part in zip(texts, parts):
            length = len(part.strip())
            if length > max(len(original) * 3, len(original) + 50) or any(r in part for r in _SEPARATOR_REMNANTS):
                logger.debug("Separator bleeding detected; falling back")
                return None
        self.router.record_family_success(EndpointRouter.FAMILY_PRIMARY)
        return [_keep_edges(original, part) for original, part in zip(texts, parts)]

    def _try_batchexecute(self, texts: list[str], sl: str, tl: str) -> list[str] | None:
        family = EndpointRouter.FAMILY_BATCHEXECUTE
        if not self.router.is_family_available(family):
            return None
        try:
            result = self.transport.batchexecute(texts, sl, tl)
        except (TransportError, RateLimitedError) as exc:
            logger.debug("batchexecute failed: %s", exc)
            result = None
        if result is None:
            self.router.record_family_failure(family)
            return None
        self.router.record_family_success(family)
        return result

    def _recover_integrity(
        self, texts: list[str], restored: list[str | None], bulk: set[int], sl: str, tl: str
    ) -> None:
        """Retry bulk results that lost a placeholder or tag through the single path."""
        broken = [i for i in sorted(bulk) if restored[i] is not None
                  and UnitySyntaxGuard.integrity_issues(texts[i], restored[i])]
        for index in broken[:MAX_INDIVIDUAL_RECOVERY]:
            retry = self.translate(texts[index], sl, tl)
            if retry.success and not UnitySyntaxGuard.integrity_issues(texts[index], retry.translated_text):
                restored[index] = retry.translated_text
        if broken:
            logger.info("Google bulk integrity recovery: %d candidate(s)", min(len(broken), MAX_INDIVIDUAL_RECOVERY))

    def _retry_unchanged(self, texts: list[str], restored: list[str | None], sl: str, tl: str) -> None:
        """Second opinion from a *different* family for lines echoed back untranslated (opt-in)."""
        unchanged = [i for i, t in enumerate(texts)
                     if restored[i] is not None and restored[i].strip() == t.strip() and _has_letters(t)]
        recovered = 0
        for index in unchanged[:MAX_AGGRESSIVE_RETRY]:
            protected, tags = UnitySyntaxGuard.protect(texts[index])
            try:
                second = UnitySyntaxGuard.restore(
                    self._route_single(protected, sl, tl, exclude={EndpointRouter.FAMILY_PRIMARY}), tags
                )
            except TransportError:
                continue
            if (
                second.strip()
                and second.strip() != texts[index].strip()
                and not UnitySyntaxGuard.integrity_issues(texts[index], second)
            ):
                restored[index] = second
                recovered += 1
        if unchanged:
            logger.info("Aggressive retry recovered %d/%d unchanged line(s)", recovered, len(unchanged))

    # ── single path ──────────────────────────────────────────────────────

    def _translate_protected(self, text: str, sl: str, tl: str) -> str:
        """Translate protected text, splitting it when it exceeds the per-request budget."""
        limit = self.settings.max_chars_per_request
        if len(text) <= limit:
            return self._route_single(text, sl, tl)
        return "".join(self._route_single(part, sl, tl) if part.strip() else part
                       for part in split_long_text(text, limit))

    def _single_families(self, text: str, exclude: set[str] | None = None) -> list[str]:
        families = [f for f in self.router.families(EndpointRouter.PRIORITY_SINGLE) if f not in (exclude or set())]
        if not self.settings.lingva_fallback:
            families = [f for f in families if f != EndpointRouter.FAMILY_LINGVA]
        if len(text) > GET_SAFE_CHARS:  # GET families carry the text in the URL
            families = [f for f in families if f not in (EndpointRouter.FAMILY_CLIENTS5, EndpointRouter.FAMILY_LINGVA)]
        return families or [EndpointRouter.FAMILY_BATCHEXECUTE]

    def _route_single(self, text: str, sl: str, tl: str, exclude: set[str] | None = None) -> str:
        """Walk usable families in priority order until one translates the text."""
        errors: list[str] = []
        for family in self._single_families(text, exclude):
            try:
                out = self._call_family(family, text, sl, tl)
            except RateLimitedError:
                if family != EndpointRouter.FAMILY_PRIMARY:
                    self.router.record_family_failure(family)
                errors.append(f"{family}: HTTP 429")
                continue
            except FamilyUnavailableError as exc:
                errors.append(f"{family}: {exc}")
                continue
            except TransportError as exc:
                self.router.record_family_failure(family)
                errors.append(f"{family}: {exc}")
                continue
            self.router.record_family_success(family)
            return out
        raise TransportError("; ".join(errors) or "No Google endpoint family available")

    def _call_family(self, family: str, text: str, sl: str, tl: str) -> str:
        if family == EndpointRouter.FAMILY_PRIMARY:
            return self._primary(text, sl, tl)
        if family == EndpointRouter.FAMILY_CLIENTS5:
            return self.transport.clients5(text, sl, tl)
        if family == EndpointRouter.FAMILY_BATCHEXECUTE:
            result = self.transport.batchexecute([text], sl, tl)
            if not result:
                raise TransportError("batchexecute returned no item")
            return result[0]
        return self.transport.lingva(text, sl, tl)

    def _primary(self, text: str, sl: str, tl: str) -> str:
        """POST to a primary mirror with shared 429 cooldown, mirror health and retries."""
        last_error: Exception = FamilyUnavailableError("primary blocked")
        for attempt in range(self.settings.max_retries):
            probing = self.router.breaker_tripped
            if not self.router.claim_primary_slot():
                raise FamilyUnavailableError("primary blocked by rate-limit breaker")
            if not probing:
                self.router.wait_for_cooldown()
            endpoint = self.router.get_endpoint() if self.settings.use_multi_endpoint else self.router.endpoints[0]
            try:
                out = self.transport.primary(endpoint, text, sl, tl)
            except RateLimitedError as exc:
                self.router.on_rate_limited()
                self.router.mark_mirror_failure(endpoint)
                last_error = exc
                if self.router.breaker_tripped:
                    break
                continue
            except TransportError as exc:
                self.router.mark_mirror_failure(endpoint)
                last_error = exc
                time.sleep(0.5 * (attempt + 1))
                continue
            self.router.mark_mirror_success(endpoint)
            self.router.on_primary_success()
            return out
        if isinstance(last_error, RateLimitedError):
            raise last_error
        raise TransportError(str(last_error))

    @staticmethod
    def _result(
        original: str, translated: str, sl: str, tl: str, error: str | None = None
    ) -> TranslationResult:
        return TranslationResult(
            original_text=original,
            translated_text=translated,
            source_lang=sl,
            target_lang=tl,
            engine=TranslationEngine.GOOGLE,
            success=error is None,
            error=error,
        )
