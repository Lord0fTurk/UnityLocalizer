# -*- coding: utf-8 -*-
"""Core constants and network endpoints for UnityLocalizer."""

from __future__ import annotations

# Google Translate endpoints for round-robin load balancing
GOOGLE_ENDPOINTS: list[str] = [
    "https://translate.googleapis.com/translate_a/single",
    "https://translate.google.com/translate_a/single",
    "https://translate.google.com.tr/translate_a/single",
    "https://translate.google.co.uk/translate_a/single",
    "https://translate.google.de/translate_a/single",
    "https://translate.google.fr/translate_a/single",
    "https://translate.google.ru/translate_a/single",
    "https://translate.google.jp/translate_a/single",
    "https://translate.google.ca/translate_a/single",
    "https://translate.google.com.au/translate_a/single",
    "https://translate.google.pl/translate_a/single",
    "https://translate.google.es/translate_a/single",
    "https://translate.google.it/translate_a/single",
]

# Alternate Google endpoint family (/translate_a/t, Chrome dictionary client)
GOOGLE_CLIENTS5_ENDPOINT: str = "https://clients5.google.com/translate_a/t"

# TranslateWebserverUi RPC layer (rpcid MkEWBc) — multi-item batch in single request
GOOGLE_BATCHEXECUTE_ENDPOINT: str = (
    "https://translate.google.com/_/TranslateWebserverUi/data/batchexecute"
)

# Microsoft Edge keyless web-translation endpoint (Bing engine)
BING_EDGE_TRANSLATE_ENDPOINT: str = "https://edge.microsoft.com/translate/translatetext"

# Lingva free fallback proxies
LINGVA_INSTANCES: list[str] = [
    "https://lingva.ml",
    "https://translate.plausibility.cloud",
    "https://lingva.lunar.icu",
    "https://translate.projectsegfau.lt",
    "https://lingva.garudalinux.org",
]

# Modern browser headers with consent cookies to avoid HTTP 429
GOOGLE_BROWSER_HEADERS: dict[str, str] = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
    "Referer": "https://translate.google.com/",
    "Cookie": "CONSENT=YES+cb",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0",
]

# Circuit breaker constants (values proven in RenLocalizer production use)
RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD: int = 6
RATE_LIMIT_PRIMARY_PROBE_INTERVAL: float = 300.0
RATE_LIMIT_LONG_COOLDOWN: float = 300.0

# Primary mirror health: failures before a temporary ban, and ban duration (seconds)
MIRROR_MAX_FAILURES: int = 5
MIRROR_BAN_TIME: float = 120.0

# Batch-separator path limits (one POST to /translate_a/single carrying many lines)
GOOGLE_SEPARATOR_MAX_ITEMS: int = 50
GOOGLE_SEPARATOR_MAX_CHARS: int = 8000

# Bing (Edge) request limits observed live: ~120 items / ~50k chars accepted
BING_MAX_ITEMS_PER_REQUEST: int = 100
BING_MAX_CHARS_PER_REQUEST: int = 40_000
