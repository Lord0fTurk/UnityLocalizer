# -*- coding: utf-8 -*-
"""Multi-language game data: only the source language is harvested."""

import json
from typing import Any

import pytest

from src.core.harvesters.harvest_collector import HarvestResult
from src.core.harvesters.harvest_stats import HarvestStats
from src.core.lang_detect.script_filter import dominant_script, filter_foreign_script, is_foreign_script
from src.core.parsers.loc_table import key_language
from src.core.parsers.text_formats import sniff_and_extract, strings_from_json_data
from src.core.progress import NOTIFICATION_LEVELS

RECORD = {
    "id": "^Talk_01",
    "chinese_text": "别光站在那儿看。",
    "cn_text": "別光站在那兒看。",
    "english_text": "Don't just stand there staring.",
    "japanese_text": "そこに突っ立ってるな。",
    "korea_text": "그냥 서 있지 마.",
    "russian_text": "Не стой столбом.",
    "spain_text": "No te quedes ahí parado.",
    "french_text": "Ne reste pas planté là.",
    "Turkey_text": "Öyle durup bakma.",
}


@pytest.mark.parametrize(
    ("key", "language"),
    [
        ("english_text", "en"), ("chinese_text", "zh"), ("cn_text", "zh"), ("korea_text", "ko"),
        ("spain_text", "es"), ("Turkey_text", "tr"), ("japaneseText", "ja"), ("English", "en"),
        ("zh-CN", "zh"), ("de", "de"),
    ],
)
def test_key_language_reads_language_and_country_tags(key: str, language: str) -> None:
    assert key_language(key) == language


@pytest.mark.parametrize("key", ["id", "text_id", "text_uk", "name", "text", "item_type", "description", "no"])
def test_key_language_ignores_ordinary_field_names(key: str) -> None:
    assert key_language(key) is None


def test_record_keeps_only_the_source_language() -> None:
    stats = HarvestStats()
    assert strings_from_json_data([RECORD], "", "en", stats) == ["Don't just stand there staring."]
    assert stats.tables_matched == 1 and not stats.tables_skipped
    assert strings_from_json_data([RECORD], "", "ja") == ["そこに突っ立ってるな。"]
    assert sorted(strings_from_json_data([RECORD], "", "zh")) == sorted(["别光站在那儿看。", "別光站在那兒看。"])


def test_record_without_the_source_language_reports_what_it_has() -> None:
    stats = HarvestStats()
    record = {k: v for k, v in RECORD.items() if k != "english_text"}
    assert strings_from_json_data([record], "", "en", stats) == []
    assert stats.tables_matched == 0 and stats.tables_skipped["ja"] == 1
    assert stats.dominant_skipped_locale() in stats.tables_skipped


def test_two_language_fields_are_not_a_multi_language_record() -> None:
    plain = {"english": "Hello there", "note": "Hello again"}
    assert sorted(strings_from_json_data(plain)) == ["Hello again", "Hello there"]


def test_language_keyed_objects_keep_one_subtree() -> None:
    data = {"en": {"menu": "Start the game"}, "fr": {"menu": "Commencer"}, "de": {"menu": "Spiel starten"}}
    assert strings_from_json_data(data, "", "fr") == ["Commencer"]


def test_json_with_raw_newlines_in_strings_still_parses() -> None:
    text = '[{"id":"a","english_text":"Line one\nline two","french_text":"Un","german_text":"Eins"}]'
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)
    assert sniff_and_extract(text, "en") == ["Line one\nline two"]


def test_dominant_script_and_foreign_detection() -> None:
    assert dominant_script("そこに突っ立ってるな。") == "kana"
    assert dominant_script("别光站在那儿看") == "han"
    assert dominant_script("Привет, мир") == "cyrillic"
    assert dominant_script("Hello world") is None
    assert is_foreign_script("Привет, мир", "en") and not is_foreign_script("Привет, мир", "ru")
    assert is_foreign_script("别光站在那儿看", "ja") is False and is_foreign_script("そこに", "zh")
    assert not is_foreign_script("Game Over", "ja")  # Latin is always kept
    assert not is_foreign_script("ঘর", "en")  # scripts without a rule are never dropped


def test_filter_reports_a_wrong_source_language_instead_of_dropping_everything() -> None:
    japanese = ["そこに突っ立ってるな。", "戻る", "終了する", "はじめから"]
    result = filter_foreign_script([*japanese, "Quit"], "en")
    assert result.mismatch and result.removed == 4
    assert not filter_foreign_script(["Start", "Quit", "Options", "Credits", "日本語"], "en").mismatch


class _StubManager:
    def get_translator(self, engine: object) -> object:
        return object()


def _pipeline() -> tuple[Any, list[Any]]:
    from src.core.pipeline.orchestrator import UnityTranslationPipeline

    pipeline = UnityTranslationPipeline(_StubManager())  # type: ignore[arg-type]
    events: list[Any] = []
    pipeline.progress_callback = events.append
    return pipeline, events


def test_pipeline_drops_other_scripts_and_says_so() -> None:
    pipeline, events = _pipeline()
    harvest = HarvestResult(strings=["Start", "Quit", "Options", "日本語", "Русский"])
    pipeline._drop_foreign_script(harvest, "en")
    assert harvest.strings == ["Start", "Quit", "Options"] and pipeline.last_harvest_count == 3
    assert events[-1].key == "pipeline.foreign_text_removed" and events[-1].params["count"] == 2


def test_pipeline_keeps_everything_when_the_source_language_looks_wrong() -> None:
    pipeline, events = _pipeline()
    original = ["そこに突っ立ってるな。", "戻る", "終了する", "Quit"]
    harvest = HarvestResult(strings=list(original))
    pipeline._drop_foreign_script(harvest, "en")
    assert harvest.strings == original and events[-1].key == "pipeline.source_script_mismatch"


def test_pipeline_does_not_filter_while_the_language_is_unknown() -> None:
    pipeline, events = _pipeline()
    harvest = HarvestResult(strings=["Start", "日本語"])
    pipeline._drop_foreign_script(harvest, "auto")
    assert harvest.strings == ["Start", "日本語"] and not events


def test_filter_events_are_notifications() -> None:
    assert NOTIFICATION_LEVELS["pipeline.foreign_text_removed"] == "info"
    assert NOTIFICATION_LEVELS["pipeline.source_script_mismatch"] == "warning"
