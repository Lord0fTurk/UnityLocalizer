# -*- coding: utf-8 -*-
"""Shared network settings and proxy rotation for web translation engines."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Without proxies every request comes from one IP; more parallelism than this gets
# the address flagged by Google's WAF almost immediately (RenLocalizer field data).
MAX_CONCURRENCY_WITHOUT_PROXY = 4
PROXY_FAILURE_LIMIT = 3
PROXY_BAN_SECONDS = 300.0


def _clamp(value: Any, default: float, low: float, high: float) -> float:
    try:
        return max(low, min(float(value), high))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class NetworkSettings:
    """User-tunable behaviour shared by Google, Bing and other HTTP engines."""

    concurrency: int = 4
    request_delay: float = 0.15
    timeout: float = 30.0
    max_retries: int = 3
    max_chars_per_request: int = 5000
    use_multi_endpoint: bool = True
    lingva_fallback: bool = True
    aggressive_retry: bool = False
    proxies: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_config(cls, config: Any) -> NetworkSettings:
        """Build clamped settings from a ConfigManager-like object (``get(key, default)``)."""
        proxies: tuple[str, ...] = ()
        if config.get("proxy_enabled", False):
            proxies = parse_proxy_list(str(config.get("proxy_list", "")))
        return cls(
            concurrency=int(_clamp(config.get("max_concurrency", 4), 4, 1, 32)),
            request_delay=_clamp(config.get("rate_limit_delay", 0.15), 0.15, 0.0, 10.0),
            timeout=_clamp(config.get("request_timeout", 30), 30.0, 5.0, 300.0),
            max_retries=int(_clamp(config.get("max_retries", 3), 3, 1, 10)),
            max_chars_per_request=int(_clamp(config.get("max_chars_per_request", 5000), 5000, 500, 20000)),
            use_multi_endpoint=bool(config.get("use_multi_endpoint", True)),
            lingva_fallback=bool(config.get("lingva_fallback", True)),
            aggressive_retry=bool(config.get("aggressive_retry", False)),
            proxies=proxies,
        )

    def effective_concurrency(self, engine_cap: int) -> int:
        """Parallel batches allowed for an engine, respecting the single-IP safety cap."""
        cap = engine_cap if self.proxies else min(engine_cap, MAX_CONCURRENCY_WITHOUT_PROXY)
        return max(1, min(self.concurrency, cap))


def parse_proxy_list(raw: str) -> tuple[str, ...]:
    """Proxy URLs from free text (one per line or comma separated; '#' comments ignored)."""
    entries: list[str] = []
    for chunk in raw.replace(",", "\n").splitlines():
        entry = chunk.split("#", 1)[0].strip()
        if not entry:
            continue
        if "://" not in entry:
            entry = f"http://{entry}"
        entries.append(entry)
    return tuple(dict.fromkeys(entries))


class ProxyPool:
    """Round-robin proxy rotation that benches proxies after repeated failures."""

    def __init__(self, proxies: tuple[str, ...] | list[str]) -> None:
        self._proxies = list(proxies)
        self._failures: dict[str, int] = {}
        self._banned_until: dict[str, float] = {}
        self._index = 0
        self._lock = threading.Lock()

    def __bool__(self) -> bool:
        return bool(self._proxies)

    def next(self) -> str | None:
        """Next usable proxy URL, or None when the pool is empty or fully benched."""
        with self._lock:
            now = time.monotonic()
            for _ in range(len(self._proxies)):
                proxy = self._proxies[self._index % len(self._proxies)]
                self._index += 1
                if self._banned_until.get(proxy, 0.0) <= now:
                    return proxy
            return None

    def requests_proxies(self) -> tuple[str | None, dict[str, str] | None]:
        """(proxy url, requests ``proxies=`` mapping) for the next request."""
        proxy = self.next()
        return proxy, ({"http": proxy, "https": proxy} if proxy else None)

    def mark_failed(self, proxy: str | None) -> None:
        if not proxy:
            return
        with self._lock:
            self._failures[proxy] = self._failures.get(proxy, 0) + 1
            if self._failures[proxy] >= PROXY_FAILURE_LIMIT:
                self._banned_until[proxy] = time.monotonic() + PROXY_BAN_SECONDS
                self._failures[proxy] = 0
                logger.warning("Proxy benched for %.0fs after repeated failures: %s", PROXY_BAN_SECONDS, proxy)

    def mark_success(self, proxy: str | None) -> None:
        if proxy:
            with self._lock:
                self._failures[proxy] = 0
