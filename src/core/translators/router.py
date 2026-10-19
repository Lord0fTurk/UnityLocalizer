# -*- coding: utf-8 -*-
"""Endpoint health, IP rate-limit governor and multi-family router for Google Translate.

Google throttles by IP, not by mirror, so one HTTP 429 means *every* mirror must
back off. The router keeps a shared exponential cooldown (3s doubling to 60s);
after ``RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD`` consecutive 429s the IP is treated
as flagged: the primary ``/translate_a/single`` family is skipped for
``RATE_LIMIT_LONG_COOLDOWN`` seconds and only a single probe request per
``RATE_LIMIT_PRIMARY_PROBE_INTERVAL`` tests whether the flag has decayed.
All state is guarded by a lock because batches run on several worker threads.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from collections.abc import Callable

from src.core.constants import (
    GOOGLE_ENDPOINTS,
    MIRROR_BAN_TIME,
    MIRROR_MAX_FAILURES,
    RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD,
    RATE_LIMIT_LONG_COOLDOWN,
    RATE_LIMIT_PRIMARY_PROBE_INTERVAL,
)

logger = logging.getLogger(__name__)

MAX_COOLDOWN_WAIT = 25.0


class _FamilyHealth:
    """Per-family success/failure tracker."""

    __slots__ = ("success", "failure", "consecutive_failures", "blocked_until")

    def __init__(self) -> None:
        self.success = 0
        self.failure = 0
        self.consecutive_failures = 0
        self.blocked_until = 0.0

    def is_blocked(self, now: float) -> bool:
        return now < self.blocked_until


class EndpointRouter:
    """Thread-safe router between Google endpoint families and primary mirrors.

    Routing priority (batch):  PRIMARY -> BATCHEXECUTE -> CLIENTS5 -> LINGVA
    Routing priority (single): PRIMARY -> CLIENTS5 -> BATCHEXECUTE -> LINGVA
    """

    FAMILY_PRIMARY = "primary"
    FAMILY_BATCHEXECUTE = "batchexecute"
    FAMILY_CLIENTS5 = "clients5"
    FAMILY_LINGVA = "lingva"

    PRIORITY_BATCH = [FAMILY_PRIMARY, FAMILY_BATCHEXECUTE, FAMILY_CLIENTS5, FAMILY_LINGVA]
    PRIORITY_SINGLE = [FAMILY_PRIMARY, FAMILY_CLIENTS5, FAMILY_BATCHEXECUTE, FAMILY_LINGVA]
    # Two consecutive failures of an alternate family bench it for this long.
    FAMILY_FAILURES_BEFORE_BLOCK = 2
    FAMILY_BLOCK_SECONDS = 120.0

    def __init__(
        self,
        endpoints: list[str] | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.endpoints = list(endpoints) if endpoints else list(GOOGLE_ENDPOINTS)
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._health = {family: _FamilyHealth() for family in self.PRIORITY_BATCH}
        self._mirror_failures: dict[str, int] = {}
        self._mirror_banned_until: dict[str, float] = {}
        self._consecutive_429 = 0
        self._cooldown_until = 0.0
        self._probe_at = 0.0

    # ── IP rate-limit governor ───────────────────────────────────────────

    @property
    def breaker_tripped(self) -> bool:
        """True once enough consecutive 429s flagged the IP."""
        with self._lock:
            return self._consecutive_429 >= RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD

    @property
    def primary_blocked(self) -> bool:
        """Primary mirrors are skipped while the breaker is tripped and no probe is due."""
        with self._lock:
            return self._consecutive_429 >= RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD and self._clock() < self._probe_at

    def claim_primary_slot(self) -> bool:
        """Whether a primary request may be sent now; claims the single probe slot when tripped."""
        with self._lock:
            if self._consecutive_429 < RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD:
                return True
            now = self._clock()
            if now < self._probe_at:
                return False
            self._probe_at = now + RATE_LIMIT_PRIMARY_PROBE_INTERVAL
            return True

    def on_rate_limited(self) -> float:
        """Record an IP-level 429; returns the shared cooldown in seconds."""
        with self._lock:
            self._consecutive_429 += 1
            if self._consecutive_429 >= RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD:
                wait = float(RATE_LIMIT_LONG_COOLDOWN)
                if self._consecutive_429 == RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD:
                    self._probe_at = self._clock() + RATE_LIMIT_PRIMARY_PROBE_INTERVAL
                    logger.warning(
                        "Google rate limit persists after %d consecutive 429s; using alternate "
                        "endpoint families for %ss (a proxy list avoids this).",
                        self._consecutive_429, RATE_LIMIT_LONG_COOLDOWN,
                    )
            else:
                wait = min(3.0 * (2 ** (self._consecutive_429 - 1)), 60.0)
            self._cooldown_until = self._clock() + wait
            return wait

    def on_primary_success(self) -> None:
        """A primary request worked: the IP flag has decayed or never existed."""
        with self._lock:
            self._consecutive_429 = 0
            self._probe_at = 0.0

    def wait_for_cooldown(self, max_wait: float = MAX_COOLDOWN_WAIT) -> None:
        """Block the calling worker until the shared cooldown expires (capped)."""
        with self._lock:
            remaining = self._cooldown_until - self._clock()
        if remaining > 0:
            self._sleep(min(remaining, max_wait))

    # ── Family health ────────────────────────────────────────────────────

    def is_family_available(self, family: str) -> bool:
        with self._lock:
            tripped = self._consecutive_429 >= RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD
            if family == self.FAMILY_PRIMARY and tripped and self._clock() < self._probe_at:
                return False
            return not self._health[family].is_blocked(self._clock())

    def families(self, priority: list[str]) -> list[str]:
        """Families in priority order that are currently usable."""
        return [family for family in priority if self.is_family_available(family)]

    def best_family_for_batch(self) -> str:
        return next(iter(self.families(self.PRIORITY_BATCH)), self.FAMILY_LINGVA)

    def best_family_for_single(self) -> str:
        return next(iter(self.families(self.PRIORITY_SINGLE)), self.FAMILY_LINGVA)

    def record_family_success(self, family: str) -> None:
        with self._lock:
            health = self._health[family]
            health.success += 1
            health.consecutive_failures = 0

    def record_family_failure(self, family: str, block_for: float | None = None) -> None:
        """Count a failure; consecutive failures (or an explicit block) bench the family."""
        with self._lock:
            health = self._health[family]
            health.failure += 1
            health.consecutive_failures += 1
            duration = block_for
            if duration is None and health.consecutive_failures >= self.FAMILY_FAILURES_BEFORE_BLOCK:
                duration = self.FAMILY_BLOCK_SECONDS
            if duration:
                health.blocked_until = self._clock() + duration
                health.consecutive_failures = 0
                logger.info("Google endpoint family '%s' benched for %.0fs", family, duration)

    # ── Primary mirrors ──────────────────────────────────────────────────

    def get_endpoint(self) -> str:
        """Random healthy primary mirror (random avoids hammering one host)."""
        with self._lock:
            now = self._clock()
            available = [ep for ep in self.endpoints if self._mirror_banned_until.get(ep, 0.0) <= now]
            if not available:
                self._mirror_banned_until.clear()
                self._mirror_failures.clear()
                available = list(self.endpoints)
            return random.choice(available)

    def mark_mirror_failure(self, endpoint: str) -> None:
        """Bench a mirror for MIRROR_BAN_TIME after MIRROR_MAX_FAILURES failures."""
        with self._lock:
            self._mirror_failures[endpoint] = self._mirror_failures.get(endpoint, 0) + 1
            if self._mirror_failures[endpoint] >= MIRROR_MAX_FAILURES:
                self._mirror_banned_until[endpoint] = self._clock() + MIRROR_BAN_TIME
                self._mirror_failures[endpoint] = 0
                logger.warning("Google mirror benched for %ss: %s", MIRROR_BAN_TIME, endpoint)

    def mark_mirror_success(self, endpoint: str) -> None:
        with self._lock:
            self._mirror_failures[endpoint] = 0
