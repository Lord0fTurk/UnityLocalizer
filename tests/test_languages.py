# -*- coding: utf-8 -*-
"""Tests for the language catalog and per-engine language code mapping."""

from typing import Any

import pytest

from src.core.languages import (
    LANGUAGES,
    describe_for_prompt,
    engine_language_code,
    engine_supports,
    get_language,
    languages_for_engine,
)
from src.core.translators.base import TranslationEngine, TranslationResult
from src.core.translators.manager import TranslationManager


def test_catalog_has_over_100_unique_languages() -> None:
    codes = [lang.code for lang in LANGUAGES]
    assert len(codes) > 100
    assert len(set(code.lower() for code in codes)) == len(codes)
    assert all(lang.english and lang.native for lang in LANGUAGES)


def test_legacy_config_codes_still_resolve() -> None:
    for code in ("tr", "en", "de", "es", "fr", "ru", "pt-BR", "ja", "zh-CN", "ko", "it", "pl", "ar"):
        assert get_language(code) is not None, code


@pytest.mark.parametrize(
    "code, engine, source, expected",
    [
        ("zh-CN", "bing", False, "zh-Hans"),
        ("no", "bing", False, "nb"),
        ("pt-BR", "google", False, "pt"),
        ("tr", "google", False, "tr"),
        ("en", "deepl", False, "EN-US"),
        ("en", "deepl", True, "EN"),
        ("zh-TW", "deepl", False, "ZH-HANT"),
        ("pt-BR", "deepl", True, "PT"),
        ("ceb", "gemini", False, "ceb"),
        ("auto", "deepl", True, "auto"),
    ],
)
def test_engine_language_code(code: str, engine: str, source: bool, expected: str) -> None:
    assert engine_language_code(code, engine, source=source) == expected


def test_deepl_subset_and_full_lists() -> None:
    deepl = {lang.code for lang in languages_for_engine("deepl")}
    assert {"tr", "ja", "zh-CN", "pt-BR"} <= deepl
    assert "ceb" not in deepl and engine_supports("deepl", "ceb") is False
    assert len(languages_for_engine("google")) == len(LANGUAGES)
    english = [lang.english.lower() for lang in languages_for_engine("google")]
    assert english == sorted(english)


def test_prompt_description_is_unambiguous() -> None:
    assert describe_for_prompt("ceb") == "Cebuano (ceb)"
    assert describe_for_prompt("xx-unknown") == "xx-unknown"


class _RecordingTranslator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str) -> list[TranslationResult]:
        self.calls.append((source_lang, target_lang))
        return [
            TranslationResult(original_text=t, translated_text=t + "*", source_lang=source_lang,
                              target_lang=target_lang, engine=TranslationEngine.BING, success=True)
            for t in texts
        ]


class _NoCache:
    def get_many(self, *args: Any) -> dict[str, str]:
        return {}

    def set_many(self, translations: dict[str, str], *args: Any) -> None:
        self.last = (*next(iter(translations.items())), *args)


def test_manager_sends_engine_codes_but_keeps_canonical_results(tmp_path: Any) -> None:
    from src.utils.config import ConfigManager

    manager = TranslationManager(config=ConfigManager(tmp_path / "c.json"), cache=_NoCache())  # type: ignore[arg-type]
    fake = _RecordingTranslator()
    manager._translators[TranslationEngine.BING] = fake  # type: ignore[assignment]

    results = manager.translate_batch(["Hi"], source_lang="en", target_lang="zh-CN", engine_type=TranslationEngine.BING)
    assert fake.calls == [("en", "zh-Hans")]
    assert (results[0].source_lang, results[0].target_lang) == ("en", "zh-CN")
    assert manager.cache.last[2:4] == ("en", "zh-CN")  # cache keyed by canonical codes
