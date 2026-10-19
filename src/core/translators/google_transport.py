# -*- coding: utf-8 -*-
"""Low-level HTTP calls for the four Google endpoint families.

Every call honours the shared request delay, timeout and proxy rotation, and
raises ``RateLimitedError`` on HTTP 429 so the caller can trigger the router's
IP-wide cooldown. Primary mirrors are called with POST: the text travels in the
form body, so long strings never hit URL length limits.
"""

from __future__ import annotations

import json
import logging
import random
import time
import urllib.parse
from typing import Any

import requests

from src.core.constants import (
    GOOGLE_BATCHEXECUTE_ENDPOINT,
    GOOGLE_BROWSER_HEADERS,
    GOOGLE_CLIENTS5_ENDPOINT,
    LINGVA_INSTANCES,
    USER_AGENTS,
)
from src.core.translators.network import NetworkSettings, ProxyPool

logger = logging.getLogger(__name__)

# GET endpoints carry the text in the URL; above this they risk HTTP 400/413.
GET_SAFE_CHARS = 1500


class RateLimitedError(Exception):
    """HTTP 429 from a Google endpoint (IP-level throttling)."""


class TransportError(Exception):
    """Non-rate-limit failure: network error, bad status or unexpected payload."""


class GoogleTransport:
    """Thread-safe HTTP client for the Google endpoint families."""

    def __init__(self, settings: NetworkSettings, proxies: ProxyPool | None = None) -> None:
        self.settings = settings
        self.proxies = proxies or ProxyPool(settings.proxies)
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=32, pool_maxsize=32)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    # ── plumbing ─────────────────────────────────────────────────────────

    def _headers(self, content_type: str | None = None) -> dict[str, str]:
        headers = dict(GOOGLE_BROWSER_HEADERS)
        headers["User-Agent"] = random.choice(USER_AGENTS)
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _pace(self) -> None:
        """Per-request delay with jitter so parallel workers do not fire in lockstep."""
        delay = self.settings.request_delay
        if delay > 0:
            time.sleep(delay * random.uniform(0.8, 1.2))

    def _request(self, method: str, url: str, timeout: float | None = None, **kwargs: Any) -> requests.Response:
        """Send one request through the proxy pool; maps 429 and failures to typed errors."""
        self._pace()
        proxy, proxy_map = self.proxies.requests_proxies() if self.proxies else (None, None)
        try:
            resp = self.session.request(
                method, url, timeout=timeout or self.settings.timeout, proxies=proxy_map, **kwargs
            )
        except requests.RequestException as exc:
            self.proxies.mark_failed(proxy)
            raise TransportError(f"{type(exc).__name__}: {exc}") from exc
        if resp.status_code == 429:
            self.proxies.mark_failed(proxy)
            raise RateLimitedError(url)
        if resp.status_code != 200:
            self.proxies.mark_failed(proxy)
            raise TransportError(f"HTTP {resp.status_code}")
        self.proxies.mark_success(proxy)
        return resp

    # ── families ─────────────────────────────────────────────────────────

    def primary(self, endpoint: str, text: str, source_lang: str, target_lang: str) -> str:
        """POST /translate_a/single (form body, no URL length limit)."""
        body = urllib.parse.urlencode(
            {"client": "gtx", "sl": source_lang or "auto", "tl": target_lang, "dt": "t", "q": text}
        )
        resp = self._request(
            "POST", endpoint, data=body,
            headers=self._headers("application/x-www-form-urlencoded;charset=utf-8"),
        )
        try:
            segments = resp.json()[0]
            return "".join(part[0] for part in segments if part and part[0])
        except (ValueError, TypeError, IndexError) as exc:
            raise TransportError(f"Unexpected primary payload: {exc}") from exc

    def clients5(self, text: str, source_lang: str, target_lang: str) -> str:
        """Chrome dictionary endpoint (GET; short texts only)."""
        params = {"client": "dict-chrome-ex", "sl": source_lang or "auto", "tl": target_lang, "q": text}
        resp = self._request("GET", GOOGLE_CLIENTS5_ENDPOINT, params=params, headers=self._headers())
        try:
            data = resp.json()
        except ValueError as exc:
            raise TransportError(f"Unexpected clients5 JSON: {exc}") from exc
        if isinstance(data, list) and data:
            if isinstance(data[0], str):
                return data[0]
            if isinstance(data[0], list) and data[0] and isinstance(data[0][0], str):
                return data[0][0]
        raise TransportError("Unexpected clients5 payload")

    def batchexecute(self, texts: list[str], source_lang: str, target_lang: str) -> list[str] | None:
        """Translate many items in one RPC; None when any item is missing from the reply."""
        if not texts:
            return []
        sl = source_lang or "auto"
        rpc = [["MkEWBc", json.dumps([[t, sl, target_lang, True], [None]]), None, str(i)] for i, t in enumerate(texts)]
        freq = json.dumps([rpc], separators=(",", ":"))
        params = {"rpcids": "MkEWBc", "source-path": "/", "hl": "en-US", "soc-app": "1",
                  "soc-platform": "1", "soc-device": "1", "_reqid": str(random.randint(1000, 9999)), "rt": "c"}
        resp = self._request(
            "POST", GOOGLE_BATCHEXECUTE_ENDPOINT, params=params, data=f"f.req={urllib.parse.quote(freq)}&",
            headers=self._headers("application/x-www-form-urlencoded;charset=UTF-8"),
        )
        results = parse_batchexecute(resp.text, len(texts))
        return results if all(r is not None for r in results) else None  # type: ignore[return-value]

    def lingva(self, text: str, source_lang: str, target_lang: str) -> str:
        """Try each Lingva instance in random order (GET; path-encoded text)."""
        instances = list(LINGVA_INSTANCES)
        random.shuffle(instances)
        # safe="" also encodes "/" so slashes in game text cannot break the URL path.
        encoded = urllib.parse.quote(text, safe="")
        for base_url in instances:
            try:
                resp = self._request("GET", f"{base_url}/api/v1/{source_lang or 'auto'}/{target_lang}/{encoded}", timeout=10.0)
                payload = resp.json()
                translation = payload.get("translation") if isinstance(payload, dict) else None
                if isinstance(translation, str) and translation:
                    return translation
            except (TransportError, RateLimitedError, ValueError) as exc:
                logger.debug("Lingva instance %s failed: %s", base_url, exc)
        raise TransportError("All Lingva instances failed")

    def close(self) -> None:
        self.session.close()


def parse_batchexecute(raw: str, count: int) -> list[str | None]:
    """Extract per-item translations (by RPC id) from a batchexecute response."""
    results: list[str | None] = [None] * count
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("[") or "wrb.fr" not in line:
            continue
        try:
            envelope = json.loads(line)
        except ValueError:
            continue
        for entry in envelope:
            _store_batch_entry(entry, results)
    return results


def _store_batch_entry(entry: Any, results: list[str | None]) -> None:
    """Decode one ``wrb.fr`` entry into results[item_id]."""
    if not (isinstance(entry, list) and len(entry) >= 4 and entry[0] == "wrb.fr" and entry[2]):
        return
    try:
        item_id = int(entry[-1])
        node = json.loads(entry[2])[1][0][0]
    except (ValueError, TypeError, IndexError):
        return
    if not 0 <= item_id < len(results):
        return
    if isinstance(node, str) and node:
        results[item_id] = node
    elif isinstance(node, list) and len(node) > 5 and isinstance(node[5], list):
        results[item_id] = "".join(seg[0] for seg in node[5] if seg and seg[0]) or None
    elif isinstance(node, list) and node and isinstance(node[0], str) and node[0]:
        results[item_id] = node[0]
