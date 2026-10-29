# -*- coding: utf-8 -*-
"""Source channel labels in the review editor and leaving rows out of the game dictionary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.core.engine_profiler import EngineProfiler
from src.core.harvesters.harvest_collector import HarvestCollector
from src.core.hook_layout import dictionary_path
from src.core.parsers.auto_translator import AutoTranslatorParser
from src.core.pipeline.orchestrator import UnityTranslationPipeline
from src.core.pipeline.review_session import (
    STATUS_ACCEPTED,
    STATUS_EDITED,
    STATUS_EXCLUDED,
    STATUS_REJECTED,
    ReviewRow,
    ReviewSession,
    RunContext,
)
from src.core.pipeline.review_store import ReviewStore
from src.core.pipeline.translation_runner import TranslationReport


def _session(root: Path = Path(".")) -> ReviewSession:
    rows = [
        ReviewRow(0, "Start", "Başla", "accepted", source="assets"),
        ReviewRow(1, "Quit", "Çık", "accepted", source="assets"),
        ReviewRow(2, "Spawn enemy {0}", "Düşman {0}", "accepted", source="code"),
        ReviewRow(3, "Debug view", "Hata ayıklama", "accepted", source="code"),
        ReviewRow(4, "Gold: {0}", "Altın", "rejected", [("missing", ["{0}"])], source="code"),
        ReviewRow(5, "Old line", "Eski satır", "accepted"),
    ]
    return ReviewSession(rows, RunContext(root, "tr"))


# --- harvest -> review rows ------------------------------------------------------


def test_collector_records_the_first_channel_of_every_string(tmp_path: Path) -> None:
    game = tmp_path / "Game"
    (game / "Game_Data" / "StreamingAssets").mkdir(parents=True)
    (game / "Game.exe").write_bytes(b"MZ")
    (game / "UnityPlayer.dll").write_bytes(b"MZ")
    (game / "Game_Data" / "StreamingAssets" / "menu.json").write_text(
        '{"a": "Start the adventure", "b": "Shared sentence here"}', encoding="utf-8"
    )
    (game / "Localization").mkdir()
    (game / "Localization" / "en.json").write_text(
        '{"a": "Leave the village", "b": "Shared sentence here"}', encoding="utf-8"
    )
    result = HarvestCollector().collect(EngineProfiler.profile_game(game))
    assert result.sources["Start the adventure"] == "streaming"
    assert result.sources["Leave the village"] == "localization"
    assert result.sources["Shared sentence here"] == "streaming"  # the earlier channel wins
    assert set(result.sources) == set(result.strings)


def test_review_rows_carry_the_harvest_channel() -> None:
    report = TranslationReport()
    report.translations["Start"] = "Başla"
    report.failed_sources.append("Quit")
    report.unchanged_sources.append("Mystery")
    session = ReviewSession.from_report(
        report, RunContext(Path("."), "tr"), sources={"Start": "assets", "Quit": "code"}
    )
    assert {r.original: r.source for r in session.rows} == {"Start": "assets", "Quit": "code", "Mystery": ""}


def test_rows_without_a_source_map_have_no_source() -> None:
    report = TranslationReport()
    report.translations["Start"] = "Başla"
    assert ReviewSession.from_report(report, RunContext(Path("."), "tr")).rows[0].source == ""


# --- leaving rows out ------------------------------------------------------------


def test_excluded_rows_are_not_shippable_and_come_back_with_their_status() -> None:
    session = _session()
    changed = session.exclude([2, 3, 4])
    assert [r.row_id for r in changed] == [2, 3, 4]
    assert session.excluded() == {"Spawn enemy {0}", "Debug view", "Gold: {0}"}
    assert set(session.shippable()) == {"Start", "Quit", "Old line"}
    assert session.counts()["excluded"] == 3 and session.counts()["accepted"] == 3
    restored = session.include([2, 3, 4])
    assert [r.status for r in restored] == [STATUS_ACCEPTED, STATUS_ACCEPTED, STATUS_REJECTED]
    assert session.excluded() == set() and "Spawn enemy {0}" in session.shippable()


def test_exclude_and_include_only_touch_rows_that_change() -> None:
    session = _session()
    assert session.exclude([0]) and session.exclude([0]) == []
    assert session.include([1]) == [] and session.rows[1].status == STATUS_ACCEPTED
    assert [r.row_id for r in session.include([0])] == [0]


def test_exclude_rejects_an_unknown_row() -> None:
    with pytest.raises(IndexError):
        _session().exclude([99])


def test_editing_a_left_out_row_brings_it_back() -> None:
    session = _session()
    session.exclude([0])
    row = session.edit(0, "Başlat")
    assert row.status == STATUS_EDITED and "Start" not in session.excluded()


def test_filtered_and_source_counts_follow_the_source() -> None:
    session = _session()
    assert [r.row_id for r in session.filtered(source="assets")] == [0, 1]
    assert [r.row_id for r in session.filtered(status="rejected", source="code")] == [4]
    assert session.filtered(source="streaming") == []
    assert session.source_counts() == {"assets": 2, "code": 3}  # the unlabeled row is not counted


# --- index -----------------------------------------------------------------------


def test_store_filters_by_source_and_lists_sources() -> None:
    store = ReviewStore(_session())
    assert store.ids(source="code") == [2, 3, 4]
    assert store.count("rejected", source="assets") == 0
    assert store.page("", "debug", source="code") == [3]
    assert store.sources() == {"code": 3, "assets": 2}


def test_store_mirrors_bulk_exclusion() -> None:
    session = _session()
    store = ReviewStore(session)
    store.refresh_many(session.exclude(store.ids(source="code")))
    assert store.ids("excluded") == [2, 3, 4]
    assert store.counts()["excluded"] == 3 and store.counts()["accepted"] == 3
    store.refresh_many([])  # nothing to mirror is fine


def test_replace_all_respects_the_source_filter() -> None:
    session = _session()
    store = ReviewStore(session)
    changed = store.replace_all("ı", "i", False, source="assets")
    assert changed == 1 and session.rows[1].translation == "Çik"
    assert session.rows[3].translation == "Hata ayıklama"  # other source untouched


# --- writing the game dictionary -------------------------------------------------


def _write(path: Path, entries: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    assert AutoTranslatorParser().apply_translations(path, entries)


def test_remove_keys_delete_entries_but_keep_hand_written_lines(tmp_path: Path) -> None:
    path = tmp_path / "dict.txt"
    _write(path, {"Start": "Başla", "Quit": "Çık", "Gold: {0}": "Altın: {0}"})
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("// my note\n")
    assert AutoTranslatorParser().apply_translations(path, {}, remove_keys={"Quit", "Gold: {0}"})
    text = path.read_text(encoding="utf-8-sig")
    assert "Start=Başla" in text and "// my note" in text
    assert "Quit" not in text and "Gold" not in text and "Altın" not in text  # entry and its regex are gone


def test_remove_keys_also_remove_the_variants_derived_from_them(tmp_path: Path) -> None:
    path = tmp_path / "dict.txt"
    _write(path, {"Bob: Hello there, friend": "Bob: Merhaba dostum", "It's here": "Burada"})
    assert "Hello there, friend=" in path.read_text(encoding="utf-8-sig")  # body variant was written
    AutoTranslatorParser().apply_translations(path, {}, remove_keys={"Bob: Hello there, friend", "It's here"})
    assert AutoTranslatorParser().read_dictionary(path) == []


def test_a_key_that_is_still_translated_survives_removal(tmp_path: Path) -> None:
    path = tmp_path / "dict.txt"
    _write(path, {"Bob: Hello there, friend": "Bob: Merhaba dostum"})
    AutoTranslatorParser().apply_translations(
        path, {"Hello there, friend": "Selam dostum"}, remove_keys={"Bob: Hello there, friend"}
    )
    assert AutoTranslatorParser().read_dictionary(path) == [("Hello there, friend", "Selam dostum")]


def test_without_remove_keys_nothing_is_deleted(tmp_path: Path) -> None:
    path = tmp_path / "dict.txt"
    _write(path, {"Start": "Başla", "Quit": "Çık"})
    AutoTranslatorParser().apply_translations(path, {"Start": "Başlat"})
    assert dict(AutoTranslatorParser().read_dictionary(path)) == {"Start": "Başlat", "Quit": "Çık"}


class _Cache:
    def set_many(self, *args: Any) -> None:
        pass


class _Manager:
    cache = _Cache()

    def get_translator(self, engine: object) -> object:
        return object()


def test_saving_a_review_removes_left_out_rows_from_the_game_dictionary(tmp_path: Path) -> None:
    root = tmp_path / "Game"
    path = dictionary_path(root, "tr")
    _write(path, {"Start": "Başla", "Quit": "Çık", "Debug view": "Hata ayıklama"})
    session = _session(root)
    session.exclude([3])
    assert UnityTranslationPipeline(_Manager()).save_review(session)  # type: ignore[arg-type]
    saved = dict(AutoTranslatorParser().read_dictionary(path))
    assert "Debug view" not in saved
    assert saved["Start"] == "Başla" and saved["Quit"] == "Çık" and saved["Old line"] == "Eski satır"


# --- Qt bridge -------------------------------------------------------------------


class _Pipeline:
    def save_review(self, session: ReviewSession) -> bool:
        return True


@pytest.fixture
def editor() -> Any:
    from src.backend.editor_backend import EditorBackend

    backend = EditorBackend(pipeline=_Pipeline())  # type: ignore[arg-type]
    backend.loadSession(_session())
    backend.toasts = []  # type: ignore[attr-defined]
    backend.toastRequested.connect(lambda text, kind: backend.toasts.append((text, kind)))  # type: ignore[attr-defined]
    return backend


def test_backend_lists_sources_with_a_label_key(editor: Any) -> None:
    assert editor.sources == [
        {"key": "code", "count": 3, "labelKey": "settings.channel_code_label"},
        {"key": "assets", "count": 2, "labelKey": "settings.channel_assets_label"},
    ]
    assert editor.filteredRows[0]["source"] == "assets"


def test_backend_source_filter_narrows_the_list_and_ignores_unknown_sources(editor: Any) -> None:
    editor.setSourceFilter("code")
    assert editor.sourceFilter == "code" and [r["id"] for r in editor.filteredRows] == [2, 3, 4]
    assert editor.matchCount == 3
    editor.setSourceFilter("streaming")
    assert editor.sourceFilter == "" and editor.matchCount == 6


def test_backend_excludes_the_shown_rows_and_puts_them_back(editor: Any) -> None:
    editor.setSourceFilter("code")
    assert editor.excludeShown() == 3
    assert editor.counts["excluded"] == 3 and editor.shippableCount == 3
    assert editor.matchCount == 3 and all(r["status"] == STATUS_EXCLUDED for r in editor.filteredRows)
    editor.setSourceFilter("")
    editor.setStatusFilter("excluded")
    assert editor.includeShown() == 3
    assert editor.counts["excluded"] == 0 and editor.shippableCount == 5
    assert [kind for _, kind in editor.toasts] == ["success", "success"]
    assert len(editor.toasts) == 2  # the wording depends on whether a locale is loaded; the kind does not


def test_backend_exclude_respects_status_and_search(editor: Any) -> None:
    editor.setStatusFilter("rejected")
    assert editor.excludeShown() == 1
    editor.setStatusFilter("")
    editor.setFilterQuery("debug")
    assert editor.excludeShown() == 1
    assert editor.counts["excluded"] == 2 and editor.counts["accepted"] == 4


def test_backend_exclude_with_nothing_shown_reports_info(editor: Any) -> None:
    editor.setFilterQuery("no such text anywhere")
    assert editor.excludeShown() == 0
    assert editor.toasts[-1][1] == "info"


def test_backend_loading_a_new_session_clears_the_source_filter(editor: Any) -> None:
    editor.setSourceFilter("code")
    editor.loadSession(_session())
    assert editor.sourceFilter == ""
