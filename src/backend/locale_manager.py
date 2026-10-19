# -*- coding: utf-8 -*-
"""Internationalization and UI language management bridge."""

from __future__ import annotations

import json
import logging
from typing import Any

from PyQt6.QtCore import QLocale, QObject, pyqtProperty, pyqtSignal, pyqtSlot

from src.utils.paths import resource_path

logger = logging.getLogger(__name__)


class LocaleManager(QObject):
    """Manages application UI languages and exposes localized strings to QML."""

    languageChanged = pyqtSignal(str)

    SUPPORTED_LANGUAGES: list[dict[str, str]] = [
        {"code": "tr", "name": "Türkçe"},
        {"code": "en", "name": "English"},
        {"code": "de", "name": "Deutsch"},
        {"code": "es", "name": "Español"},
        {"code": "fr", "name": "Français"},
        {"code": "ru", "name": "Русский"},
        {"code": "pt-BR", "name": "Português (Brasil)"},
        {"code": "ja", "name": "日本語"},
        {"code": "zh-CN", "name": "简体中文"},
        {"code": "ko", "name": "한국어"},
        {"code": "it", "name": "Italiano"},
        {"code": "fa", "name": "فارسی"},
    ]

    TURKIC_LANGUAGES: set[str] = {
        "tr", "az", "uz", "kk", "ky", "tk", "ug", "tt", "ba", "cv", "gag"
    }

    _instance: LocaleManager | None = None

    def __init__(self, default_lang: str = "tr", parent: QObject | None = None) -> None:
        super().__init__(parent)
        LocaleManager._instance = self
        self._current_lang = default_lang
        self._strings: dict[str, Any] = {}
        self._en_fallback: dict[str, Any] = self._load_locale_file("en")
        self.setLanguage(default_lang)

    @classmethod
    def get_instance(cls) -> LocaleManager | None:
        """Return the active LocaleManager singleton instance."""
        return cls._instance

    @classmethod
    def detect_system_language(cls) -> str:
        """Detect OS interface language and map to a supported locale."""
        try:
            bcp47 = QLocale.system().bcp47Name().lower()
            lang = bcp47.split("-")[0]

            if lang in cls.TURKIC_LANGUAGES:
                return "tr"
            if bcp47 in ("pt-br", "pt_br"):
                return "pt-BR"
            if lang in ("zh", "zh-cn", "zh_cn", "zh-hans"):
                return "zh-CN"
            if lang in ("de", "es", "fr", "ru", "ja", "ko", "it", "fa", "en"):
                return lang
            if lang in ("uk", "be"):
                return "ru"
        except Exception as exc:
            logger.debug("System language detection error: %s", exc)
        return "tr"

    def _load_locale_file(self, code: str) -> dict[str, Any]:
        """Load and parse JSON locale dictionary from src/gui/i18n/."""
        path = resource_path(f"src/gui/i18n/{code}.json")
        if not path.is_file():
            logger.warning("Locale file not found: %s", path)
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.error("Failed to parse locale %s: %s", path, exc)
            return {}

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Recursively merge override dictionary into a copy of base dictionary."""
        result = dict(base)
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    @pyqtProperty(str, notify=languageChanged)
    def currentLanguage(self) -> str:
        """Return currently active language code."""
        return self._current_lang

    @pyqtProperty(list, constant=True)
    def supportedLanguages(self) -> list[dict[str, str]]:
        """Return list of supported languages with code and display names."""
        return self.SUPPORTED_LANGUAGES

    @pyqtProperty("QVariantMap", notify=languageChanged)
    def strings(self) -> dict[str, Any]:
        """Return active localized strings mapping for QML binding."""
        return self._strings

    @pyqtSlot(str)
    def setLanguage(self, lang_code: str) -> None:
        """Switch active UI language and reload strings."""
        if not any(item["code"] == lang_code for item in self.SUPPORTED_LANGUAGES):
            logger.warning("Unsupported language code: %s, falling back to 'tr'", lang_code)
            lang_code = "tr"

        loaded = self._load_locale_file(lang_code)
        self._strings = self._deep_merge(self._en_fallback, loaded)
        self._current_lang = lang_code
        self.languageChanged.emit(lang_code)
        logger.info("UI language switched to: %s", lang_code)

    @pyqtSlot(str, str, result=str)
    @pyqtSlot(str, result=str)
    def t(self, key_path: str, fallback: str = "") -> str:
        """Lookup localized string by dotted path with optional fallback."""
        cur: Any = self._strings
        for part in key_path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return fallback if fallback else key_path
        return str(cur) if cur is not None else (fallback if fallback else key_path)
