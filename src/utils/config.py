# -*- coding: utf-8 -*-
"""Persistent JSON configuration manager."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.utils.file_ops import safe_write
from src.utils.paths import get_config_path

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: dict[str, Any] = {
    "target_language": "tr",
    "source_language": "auto",
    "rtl_static_shaping": True,
    "patch_loose_files": False,
    # XUnity OverrideFontTextMeshPro: system font for IL2CPP games whose fallback bundle fails ("" = off)
    "tmp_system_font": "",
    "deepl_key": "",
    "ui_language": "tr",
    # Session (restored on next start)
    "last_game_path": "",
    "window_width": 0,
    "window_height": 0,
    "window_maximized": False,
    "engine": "google",
    "batch_size": 100,
    # Network (shared by Google, Bing and other HTTP engines)
    "rate_limit_delay": 0.15,
    "max_concurrency": 4,
    "request_timeout": 30,
    "max_chars_per_request": 5000,
    "use_multi_endpoint": True,
    "lingva_fallback": True,
    "aggressive_retry": False,
    "proxy_enabled": False,
    "proxy_list": "",
    "ai_concurrency": 2,
    # AI generation
    "ai_temperature": 0.3,
    "ai_max_tokens": 4096,
    "ai_timeout": 120,
    "ai_retries": 2,
    "ai_request_delay": 0.5,
    "ai_batch_size": 15,
    "ai_custom_prompt": "",
    "openai_base_url": "",
    "deepseek_model": "deepseek-chat",
    "gemini_safety": "BLOCK_NONE",
    "local_llm_timeout": 300,
    # Other engines
    "deepl_formality": "default",
    "libretranslate_url": "http://localhost:5000",
    "libretranslate_key": "",
    "show_debug_engines": False,
    # Translation memory, cache & terminology
    "use_cache": True,
    "tm_enabled": False,
    "tm_files": "",
    "tm_fuzzy": False,
    "tm_fuzzy_threshold": 0.9,
    "protected_terms": "",
    "openai_key": "",
    "openai_model": "gpt-4o-mini",
    "gemini_key": "",
    "gemini_model": "gemini-2.5-flash",
    "deepseek_key": "",
    "local_llm_url": "http://localhost:11434",
    "local_llm_model": "qwen2.5:latest",
    "theme": "Dark",
    "enable_auto_backup": True,
    "max_retries": 3,
}


class ConfigManager:
    """Manages application settings stored in a JSON file."""

    def __init__(self, config_path: Path | str | None = None) -> None:
        self.config_path = (
            Path(config_path) if config_path else get_config_path()
        )
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> dict[str, Any]:
        """Load configuration from disk, applying defaults for missing or invalid keys."""
        self._data = dict(DEFAULT_CONFIG)
        if self.config_path.is_file():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        self._merge_loaded(loaded)
            except Exception as exc:
                logger.error("Failed to load config from %s: %s", self.config_path, exc)
        return self._data

    def _merge_loaded(self, loaded: dict[str, Any]) -> None:
        """Merge loaded JSON values while guarding default types against corruption."""
        for key, value in loaded.items():
            if key not in DEFAULT_CONFIG:
                self._data[key] = value
                continue
            default_val = DEFAULT_CONFIG[key]
            if isinstance(default_val, bool):
                self._data[key] = value if isinstance(value, bool) else str(value).strip().lower() in ("1", "true", "yes", "on")
            elif isinstance(default_val, int):
                try:
                    if isinstance(value, bool):
                        raise TypeError("bool is not int")
                    self._data[key] = int(float(value))
                except (TypeError, ValueError):
                    logger.warning("Ignoring invalid int config %s=%r; using default %r", key, value, default_val)
            elif isinstance(default_val, float):
                try:
                    if isinstance(value, bool):
                        raise TypeError("bool is not float")
                    self._data[key] = float(value)
                except (TypeError, ValueError):
                    logger.warning("Ignoring invalid float config %s=%r; using default %r", key, value, default_val)
            elif isinstance(default_val, str):
                self._data[key] = str(value) if value is not None else ""
            else:
                self._data[key] = value

    def save(self) -> bool:
        """Persist current settings to disk atomically."""
        try:
            content = json.dumps(self._data, indent=2, ensure_ascii=False)
            safe_write(self.config_path, content, make_backup=False)
            return True
        except Exception as exc:
            logger.error("Failed to save config to %s: %s", self.config_path, exc)
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value with fallback."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any, auto_save: bool = True) -> None:
        """Set a configuration value and optionally persist."""
        self._data[key] = value
        if auto_save:
            self.save()

    def reset_defaults(self) -> None:
        """Reset all configuration values to defaults."""
        self._data = dict(DEFAULT_CONFIG)
        self.save()
