# -*- coding: utf-8 -*-
"""Tests for automatic source-language detection."""

from __future__ import annotations

import pytest

from src.core.lang_detect import SourceLanguageDetector
from src.core.lang_detect.online_detector import detect_online
from src.core.lang_detect.sampling import clean_text, prose_lines, spread
from src.core.lang_detect.script_detector import classify_line, detect_by_script
from src.core.languages import canonical_language_code
from src.core.progress import NOTIFICATION_LEVELS

ENGLISH = [f"Welcome back traveler, the road to the village number {i} is long and dangerous." for i in range(20)]
CHINESE = [f"欢迎回来，旅行者，通往第{i}号村庄的道路漫长而危险。" for i in range(20)]
JAPANESE = [f"おかえりなさい、旅人さん。{i}番目の村への道は長くて危険です。" for i in range(20)]
KOREAN = [f"돌아오신 것을 환영합니다 여행자님 {i}번 마을로 가는 길은 멀고 위험합니다." for i in range(20)]
TURKISH = [f"Tekrar hoş geldin yolcu, {i} numaralı köye giden yol uzun ve tehlikelidir." for i in range(20)]
GERMAN = [f"Willkommen zurück, Reisender, der Weg zum Dorf Nummer {i} ist lang und gefährlich." for i in range(20)]


def test_clean_text_strips_markup() -> None:
    assert clean_text("<color=red>Hello</color> {0}, [Charm] %s\\n") == "Hello ,"


def test_prose_lines_drops_names_and_menu_words() -> None:
    lines = ["Start", "Mio Akira", "Welcome back traveler, the road is long."]
    assert prose_lines(lines) == ["Welcome back traveler, the road is long."]


def test_spread_covers_the_whole_pool() -> None:
    pool = [str(i) for i in range(100)]
    picked = spread(pool, 10)
    assert len(picked) == 10 and picked[0] == "0" and int(picked[-1]) >= 80


@pytest.mark.parametrize(
    ("lines", "expected"),
    [(CHINESE, "zh-CN"), (JAPANESE, "ja"), (KOREAN, "ko")],
)
def test_script_detection_decides_cjk(lines: list[str], expected: str) -> None:
    result = detect_by_script(lines)
    assert result is not None and result[0] == expected


def test_script_detection_ignores_latin_text() -> None:
    assert detect_by_script(ENGLISH) is None


def test_kanji_only_lines_follow_japanese_when_kana_exists() -> None:
    kanji_only = ["勇者の冒険物語最終章"] * 6
    result = detect_by_script(kanji_only + JAPANESE[:6])
    assert result is not None and result[0] == "ja"


def test_english_code_strings_do_not_hide_a_chinese_game() -> None:
    result = detect_by_script(CHINESE + ENGLISH[:12])
    assert result is not None and result[0] == "zh-CN"


def test_classify_line_needs_enough_script_share() -> None:
    assert classify_line("Hello 你") is None
    assert classify_line("你好吗朋友") == "zh-CN"


@pytest.mark.parametrize(
    ("lines", "expected"),
    [(ENGLISH, "en"), (TURKISH, "tr"), (GERMAN, "de")],
)
def test_offline_model_detects_latin_languages(lines: list[str], expected: str) -> None:
    result = SourceLanguageDetector().detect(lines, "fr")
    assert result is not None
    assert (result.code, result.method) == (expected, "offline")


def test_detector_gives_up_without_prose_and_without_online() -> None:
    assert SourceLanguageDetector().detect(["Start", "Quit", "Mio", "OK"], "tr") is None


def test_online_fallback_votes_when_offline_is_unsure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.core.lang_detect.detector.detect_offline", lambda prose: None)
    result = SourceLanguageDetector(online=lambda text: "de").detect(GERMAN, "tr")
    assert result is not None
    assert (result.code, result.method) == ("de", "online")


def test_online_detection_requires_agreement() -> None:
    answers = iter(["de", "fr", "es", "en", "it", "pt", "nl", "pl", "sv"])
    assert detect_online(GERMAN, lambda text: next(answers), "tr") is None


def test_online_detection_rejects_target_language() -> None:
    assert detect_online(TURKISH, lambda text: "tr", "tr") is None


def test_online_detection_survives_failed_requests() -> None:
    assert detect_online(GERMAN, lambda text: None, "tr") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("zh", "zh-CN"), ("iw", "he"), ("NB", "no"), ("fil", "tl"), ("pt", "pt-BR"), ("en", "en"), ("xx", None)],
)
def test_canonical_language_code(raw: str, expected: str | None) -> None:
    assert canonical_language_code(raw) == expected


def test_detection_events_are_notifications() -> None:
    assert NOTIFICATION_LEVELS["pipeline.source_detect_failed"] == "warning"
    assert NOTIFICATION_LEVELS["pipeline.source_detected_online"] == "info"


class _StubManager:
    """Minimal translation manager: no Google translator, so no online detection."""

    def get_translator(self, engine: object) -> object:
        return object()


def _pipeline_with_events() -> tuple[object, list[object]]:
    from src.core.pipeline.orchestrator import UnityTranslationPipeline

    pipeline = UnityTranslationPipeline(_StubManager())  # type: ignore[arg-type]
    events: list[object] = []
    pipeline.progress_callback = events.append
    return pipeline, events


def test_pipeline_announces_detected_language() -> None:
    from src.core.harvesters.harvest_collector import HarvestResult
    from src.core.translators.base import TranslationEngine

    pipeline, events = _pipeline_with_events()
    harvest = HarvestResult(strings=CHINESE)
    result, source = pipeline._resolve_source(  # type: ignore[attr-defined]
        None, harvest, "auto", "tr", TranslationEngine.GOOGLE, None
    )
    assert source == "zh-CN" and result is harvest
    event = events[-1]
    assert event.key == "pipeline.source_detected_offline"  # type: ignore[attr-defined]
    assert event.params["code"] == "zh-CN"  # type: ignore[attr-defined]


def test_pipeline_warns_when_language_is_undetectable() -> None:
    from src.core.harvesters.harvest_collector import HarvestResult
    from src.core.translators.base import TranslationEngine

    pipeline, events = _pipeline_with_events()
    _, source = pipeline._resolve_source(  # type: ignore[attr-defined]
        None, HarvestResult(strings=["Start", "Quit"]), "auto", "tr", TranslationEngine.DEEPL, None
    )
    assert source == "auto"
    assert events[-1].key == "pipeline.source_detect_failed"  # type: ignore[attr-defined]


def test_pipeline_leaves_an_explicit_source_language_alone() -> None:
    from src.core.harvesters.harvest_collector import HarvestResult
    from src.core.translators.base import TranslationEngine

    pipeline, events = _pipeline_with_events()
    _, source = pipeline._resolve_source(  # type: ignore[attr-defined]
        None, HarvestResult(strings=CHINESE), "ja", "tr", TranslationEngine.GOOGLE, None
    )
    assert source == "ja" and not events
