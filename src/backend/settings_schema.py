# -*- coding: utf-8 -*-
"""Typed schema for user-editable settings exposed to QML through ``AppBackend.setSetting``.

Every key declares its type and limits; values from the UI are coerced and clamped
here so the config file can never hold out-of-range or wrongly typed data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from src.core.translators.ai_translator import GEMINI_SAFETY_LEVELS
from src.core.translators.deepl import FORMALITY_VALUES


@dataclass(frozen=True)
class SettingSpec:
    """Type and constraints of one setting."""

    kind: type
    low: float | None = None
    high: float | None = None
    choices: tuple[str, ...] = ()


def _int(low: float, high: float) -> SettingSpec:
    return SettingSpec(int, low, high)


def _float(low: float, high: float) -> SettingSpec:
    return SettingSpec(float, low, high)


_BOOL = SettingSpec(bool)
_TEXT = SettingSpec(str)

SETTING_SPECS: dict[str, SettingSpec] = {
    # Performance & network
    "batch_size": _int(10, 500),
    "max_concurrency": _int(1, 32),
    "rate_limit_delay": _float(0.0, 10.0),
    "request_timeout": _int(5, 300),
    "max_retries": _int(1, 10),
    "max_chars_per_request": _int(500, 20000),
    "use_multi_endpoint": _BOOL,
    "lingva_fallback": _BOOL,
    "aggressive_retry": _BOOL,
    "proxy_enabled": _BOOL,
    "proxy_list": _TEXT,
    "use_cache": _BOOL,
    "tmp_system_font": _TEXT,
    "completed_runs": _int(0, 1_000_000),
    "hide_support_prompt": _BOOL,
    "custom_font_path": _TEXT,
    "override_font_ugui": _TEXT,
    "font_preset": SettingSpec(str, choices=("default_arial", "custom_ttf", "system_font")),
    "theme_mode": SettingSpec(str, choices=("obsidian", "daylight", "cyber_neon")),
    "accent_preset": SettingSpec(str, choices=("cyan", "emerald", "indigo", "amber")),
    "bilingual_mode": _BOOL,
    "bilingual_template": _TEXT,
    # Engines
    "deepl_key": _TEXT,
    "deepl_formality": SettingSpec(str, choices=tuple(FORMALITY_VALUES)),
    "gemini_key": _TEXT,
    "gemini_model": _TEXT,
    "gemini_safety": SettingSpec(str, choices=GEMINI_SAFETY_LEVELS),
    "openai_key": _TEXT,
    "openai_model": _TEXT,
    "openai_base_url": _TEXT,
    "deepseek_key": _TEXT,
    "deepseek_model": _TEXT,
    "local_llm_url": _TEXT,
    "local_llm_model": _TEXT,
    "local_llm_timeout": _int(10, 1800),
    "libretranslate_url": _TEXT,
    "libretranslate_key": _TEXT,
    "show_debug_engines": _BOOL,
    # AI generation
    "ai_temperature": _float(0.0, 1.0),
    "ai_max_tokens": _int(256, 65536),
    "ai_timeout": _int(10, 1800),
    "ai_retries": _int(0, 5),
    "ai_request_delay": _float(0.0, 30.0),
    "ai_batch_size": _int(1, 50),
    "ai_concurrency": _int(1, 16),
    "ai_custom_prompt": _TEXT,
    # Terminology & memory
    "protected_terms": _TEXT,
    "tm_enabled": _BOOL,
    "tm_files": _TEXT,
    "tm_fuzzy": _BOOL,
    "tm_fuzzy_threshold": _float(0.5, 1.0),
}


def coerce_setting(key: str, value: Any) -> Any:
    """Validated value for key; raises KeyError for unknown keys, ValueError for bad values."""
    spec = SETTING_SPECS[key]
    if spec.kind is bool:
        return value if isinstance(value, bool) else str(value).strip().lower() in ("1", "true", "yes", "on")
    if spec.kind is str:
        text = str(value if value is not None else "")
        if spec.choices and text not in spec.choices:
            raise ValueError(f"{key}: {text!r} not in {spec.choices}")
        return text if "\n" in text else text.strip()
    if isinstance(value, bool):
        raise TypeError(f"{key}: boolean is not a valid numeric value")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{key}: numeric value must be finite")
    if spec.low is not None:
        number = max(spec.low, number)
    if spec.high is not None:
        number = min(spec.high, number)
    return int(round(number)) if spec.kind is int else round(number, 3)
