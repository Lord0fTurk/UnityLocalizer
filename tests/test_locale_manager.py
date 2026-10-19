# -*- coding: utf-8 -*-
"""Unit tests for LocaleManager and internationalization."""

from src.backend.locale_manager import LocaleManager


def test_locale_manager_languages():
    lm = LocaleManager(default_lang="tr")
    supported = lm.supportedLanguages

    assert len(supported) >= 10  # Must be at least 10 UI languages
    codes = [item["code"] for item in supported]
    assert "tr" in codes
    assert "en" in codes
    assert "de" in codes
    assert "es" in codes
    assert "fr" in codes
    assert "ru" in codes
    assert "ja" in codes
    assert "zh-CN" in codes
    assert "ko" in codes
    assert "pt-BR" in codes


def test_locale_switching_and_fallback():
    lm = LocaleManager(default_lang="tr")
    assert lm.currentLanguage == "tr"
    assert lm.t("common.ok") == "Tamam"

    lm.setLanguage("en")
    assert lm.currentLanguage == "en"
    assert lm.t("common.ok") == "OK"

    lm.setLanguage("de")
    assert lm.currentLanguage == "de"
    assert lm.t("common.ok") == "OK"  # In German 'common.ok' is 'OK'


def test_system_language_detection():
    detected = LocaleManager.detect_system_language()
    assert isinstance(detected, str)
    assert len(detected) >= 2
