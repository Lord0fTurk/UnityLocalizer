# -*- coding: utf-8 -*-
"""Harvest bookkeeping: language-dependent re-harvest, coverage warnings and dashboard notices."""

from pathlib import Path
from typing import Any

import pytest

from src.core.harvesters.harvest_collector import HarvestResult
from src.core.harvesters.harvest_stats import FileStat, HarvestStats
from src.core.harvesters.typetree_text import collect_display_strings
from src.core.progress import NOTIFICATION_LEVELS
from src.core.translators.base import TranslationEngine


def _string_table(code: str, entries: list[str]) -> dict[str, Any]:
    return {
        "m_Script": {},
        "m_LocaleId": {"m_Code": code},
        "m_TableData": [{"m_Id": i, "m_Localized": text} for i, text in enumerate(entries)],
    }


def test_stats_record_matched_and_skipped_string_tables() -> None:
    stats = HarvestStats()
    assert collect_display_strings(_string_table("ja", ["開始", "終了"]), "en", stats) == []
    assert stats.tables_skipped["ja"] == 2 and stats.tables_matched == 0
    assert stats.dominant_skipped_locale() == "ja" and stats.language_sensitive
    assert collect_display_strings(_string_table("en", ["Start"]), "en", stats) == ["Start"]
    assert stats.tables_matched == 1
    assert stats.dominant_skipped_locale() is None  # an English table exists: nothing to correct


def test_stats_flag_i2_source_language_not_found() -> None:
    tree = {"mSource": {"mLanguages": [{"Name": "German", "Code": "de"}], "mTerms": [{"Languages": ["Spiel"]}]}}
    stats = HarvestStats()
    assert collect_display_strings(tree, "en", stats) == ["Spiel"]
    assert stats.i2_sources == 1 and stats.i2_unmatched == 1


def test_report_lists_problem_files_first() -> None:
    stats = HarvestStats(files=[FileStat("ok.assets", 5), FileStat("bad.assets", failed=True), FileStat("raw", raw_scanned=2)])
    report = stats.to_report()
    assert report["files_failed"] == ["bad.assets"] and report["raw_scanned_objects"] == 2
    assert [f["name"] for f in report["files"]][:2] == ["bad.assets", "raw"]


class _StubManager:
    def get_translator(self, engine: object) -> object:
        return object()


def _pipeline() -> tuple[Any, list[Any]]:
    from src.core.pipeline.orchestrator import UnityTranslationPipeline

    pipeline = UnityTranslationPipeline(_StubManager())  # type: ignore[arg-type]
    events: list[Any] = []
    pipeline.progress_callback = events.append
    return pipeline, events


class _FakeCollector:
    calls: list[str] = []

    def __init__(
        self, progress: object, source_lang: str = "en", skip_channels: object = (), memory_guard: bool = True,
        isolated: bool = False,
    ) -> None:
        self.source_lang = source_lang

    def collect(self, profile: object, cancel: object = None) -> HarvestResult:
        _FakeCollector.calls.append(self.source_lang)
        return HarvestResult(strings=["再収集"])


def test_assets_only_game_with_foreign_tables_is_reharvested_in_that_language(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core.pipeline import orchestrator

    _FakeCollector.calls = []
    monkeypatch.setattr(orchestrator, "HarvestCollector", _FakeCollector)
    pipeline, events = _pipeline()
    harvest = HarvestResult(strings=["Start", "Quit"])  # no loose files: only assets were read
    harvest.stats.tables_skipped["ja"] = 40
    result, source = pipeline._resolve_source(
        None, harvest, "auto", "tr", TranslationEngine.DEEPL, None
    )
    assert source == "ja" and _FakeCollector.calls == ["ja"] and result is not harvest
    assert [e.key for e in events] == ["pipeline.source_detected_tables"]


def test_english_game_is_not_scanned_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core.pipeline import orchestrator

    _FakeCollector.calls = []
    monkeypatch.setattr(orchestrator, "HarvestCollector", _FakeCollector)
    pipeline, _ = _pipeline()
    harvest = HarvestResult(strings=["Start", "Quit"])
    harvest.stats.tables_matched = 3
    _, source = pipeline._resolve_source(None, harvest, "auto", "tr", TranslationEngine.DEEPL, None)
    assert _FakeCollector.calls == [] and source == "auto"


def test_coverage_warnings_are_notifications() -> None:
    pipeline, events = _pipeline()
    stats = HarvestStats(
        files=[FileStat("a.assets", failed=True), FileStat("b.assets", raw_scanned=4)], encrypted_code=True
    )
    pipeline._report_harvest_coverage(stats)
    keys = [e.key for e in events]
    assert keys == [
        "pipeline.harvest_warn_unreadable_files",
        "pipeline.harvest_warn_raw_scan",
        "pipeline.harvest_warn_code_encrypted",
    ]
    assert all(NOTIFICATION_LEVELS[k] == "warning" for k in keys)
    assert events[1].params["count"] == 4 and events[1].params["names"] == "b.assets"


def test_clean_harvest_emits_no_warnings() -> None:
    pipeline, events = _pipeline()
    pipeline._report_harvest_coverage(HarvestStats(files=[FileStat("a.assets", 9)]))
    assert events == []


def test_dashboard_notices_replace_dismiss_and_localize(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import src.backend.app_backend as module
    from src.core.progress import ProgressEvent
    from src.utils.config import ConfigManager

    config_path = tmp_path / "config.json"
    monkeypatch.setattr(module, "ConfigManager", lambda: ConfigManager(config_path))
    backend = module.AppBackend()
    backend._notify("warning", "dashboard.status_hook_missing_proxy")
    backend._notify("warning", "dashboard.status_hook_missing_proxy")
    backend._handle_progress(ProgressEvent("pipeline.harvest_warn_raw_scan", params={"count": 2, "files": 1, "names": "x"}))
    backend._notify("info", "dashboard.game_launched")  # info stays a toast, not a notice
    notices = backend.notices
    assert [n["level"] for n in notices] == ["warning", "warning"]
    backend.dismissNotices()
    assert backend.notices == []
