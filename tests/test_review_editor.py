# -*- coding: utf-8 -*-
"""Tests for the post-run review session, its deployment and the editor bridge."""

from pathlib import Path
from typing import Any

from src.core.parsers import xunity_codec
from src.core.pipeline.orchestrator import UnityTranslationPipeline, dictionary_path
from src.core.pipeline.review_session import ReviewSession, RunContext
from src.core.pipeline.translation_runner import TranslationReport


def _report() -> TranslationReport:
    report = TranslationReport()
    report.translations["Start"] = "Başla"
    report.rejected["Gold: {0}"] = ["Missing tokens: ['{0}']"]
    report.rejected_translations["Gold: {0}"] = "Altın: 0"
    report.failed_sources.append("Quit")
    report.unchanged_sources.append("OK")
    return report


def _session(tmp_path: Path, target: str = "tr") -> ReviewSession:
    return ReviewSession.from_report(_report(), RunContext(tmp_path, target, "en", "google"))


def test_rows_put_problems_first_and_keep_rejected_candidate(tmp_path: Path) -> None:
    session = _session(tmp_path)
    assert [(r.original, r.status) for r in session.rows] == [
        ("Gold: {0}", "rejected"), ("Quit", "failed"), ("Start", "accepted"), ("OK", "unchanged"),
    ]
    assert session.rows[0].translation == "Altın: 0"
    assert session.rows[0].issues == [("missing", ["{0}"])]
    assert session.counts() == {
        "accepted": 1, "repaired": 0, "edited": 0, "rejected": 1, "invalid": 0, "failed": 1, "unchanged": 1,
        "excluded": 0,
    }


def test_edit_revalidates_with_syntax_guard(tmp_path: Path) -> None:
    session = _session(tmp_path)
    fixed = session.edit(0, "Altın: {0}")
    assert (fixed.status, fixed.issues) == ("edited", [])

    broken = session.edit(1, "Çık {1}")
    assert broken.status == "invalid"
    assert broken.issues == [("unexpected", ["{1}"])]

    cleared = session.edit(2, "  ")
    assert cleared.status == "failed"


def test_shippable_and_edited_maps(tmp_path: Path) -> None:
    session = _session(tmp_path)
    session.edit(0, "Altın: {0}")
    session.edit(1, "Çık {1}")
    assert session.shippable() == {"Gold: {0}": "Altın: {0}", "Start": "Başla"}
    assert session.edited() == {"Gold: {0}": "Altın: {0}"}


def test_filtered_by_status_and_query(tmp_path: Path) -> None:
    session = _session(tmp_path)
    assert [r.original for r in session.filtered("rejected")] == ["Gold: {0}"]
    assert [r.original for r in session.filtered("", "başla")] == ["Start"]
    assert session.filtered("accepted", "gold") == []


class _FakeCache:
    def __init__(self) -> None:
        self.stored: list[tuple[str, ...]] = []

    def set_many(self, translations: dict[str, str], *args: str) -> None:
        self.stored.extend((src, dst, *args) for src, dst in translations.items())


class _FakeManager:
    def __init__(self) -> None:
        self.cache = _FakeCache()


def _read_dictionary(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        decoded = xunity_codec.decode_line(line)
        if decoded:
            entries[decoded[0]] = decoded[1]
    return entries


def test_save_review_writes_dictionary_and_caches_edits(tmp_path: Path) -> None:
    manager = _FakeManager()
    pipeline = UnityTranslationPipeline(manager)  # type: ignore[arg-type]
    session = _session(tmp_path)
    session.edit(0, "Altın: {0}")

    assert pipeline.save_review(session) is True
    written = _read_dictionary(dictionary_path(tmp_path, "tr"))
    plain = {k: v for k, v in written.items() if not k.startswith("r:")}
    assert plain == {"Gold: {0}": "Altın: {0}", "Start": "Başla"}
    # "Gold: 150" on screen never equals the "Gold: {0}" key, so a runtime regex is added.
    assert written['r:"^Gold: (.*?)$"'] == '"Altın: ${1}"'
    assert manager.cache.stored == [("Gold: {0}", "Altın: {0}", "en", "tr", "google")]


def test_save_review_shapes_rtl_targets(tmp_path: Path) -> None:
    pipeline = UnityTranslationPipeline(_FakeManager())  # type: ignore[arg-type]
    report = TranslationReport()
    report.translations["Hello"] = "مرحبا"
    session = ReviewSession.from_report(report, RunContext(tmp_path, "ar"))

    assert pipeline.save_review(session) is True
    assert _read_dictionary(dictionary_path(tmp_path, "ar")) == {"Hello": "ﺎﺒﺣﺮﻣ"}
    assert session.rows[0].translation == "مرحبا"  # editor keeps logical order


# --- Qt bridge -------------------------------------------------------------------


class _FakePipeline:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.saved: list[ReviewSession] = []

    def save_review(self, session: ReviewSession) -> bool:
        self.saved.append(session)
        return self.result


def _editor(pipeline: Any) -> Any:
    from src.backend.editor_backend import EditorBackend

    return EditorBackend(pipeline=pipeline)


def test_editor_backend_filters_edits_and_saves(tmp_path: Path) -> None:
    pipeline = _FakePipeline()
    editor = _editor(pipeline)
    toasts: list[tuple[str, str]] = []
    editor.toastRequested.connect(lambda msg, kind: toasts.append((msg, kind)))

    assert editor.hasSession is False
    assert editor.filteredRows == []

    editor.loadSession(_session(tmp_path, "ar"))
    assert editor.hasSession is True
    assert editor.isRtl is True
    assert editor.totalCount == 4

    editor.setStatusFilter("rejected")
    assert [row["original"] for row in editor.filteredRows] == ["Gold: {0}"]

    editor.updateTranslation(0, "Altın: 0")  # unchanged text -> no-op
    editor.updateTranslation(0, "Altın")
    assert editor.counts["invalid"] == 1
    assert toasts and toasts[-1][1] == "warning"

    editor.updateTranslation(0, "Altın: {0}")
    assert editor.counts["edited"] == 1
    assert editor.shippableCount == 2

    editor.saveToGame()
    assert pipeline.saved and toasts[-1][1] == "success"


def test_editor_backend_reports_failed_save(tmp_path: Path) -> None:
    editor = _editor(_FakePipeline(result=False))
    toasts: list[tuple[str, str]] = []
    editor.toastRequested.connect(lambda msg, kind: toasts.append((msg, kind)))
    editor.loadSession(_session(tmp_path))
    editor.saveToGame()
    assert toasts[-1][1] == "error"


def test_editor_backend_ignores_bad_filter_and_row(tmp_path: Path) -> None:
    editor = _editor(_FakePipeline())
    editor.loadSession(_session(tmp_path))
    editor.setStatusFilter("bogus")
    assert editor.statusFilter == ""
    editor.updateTranslation(99, "x")
    assert editor.counts["edited"] == 0


def test_issue_descriptions_are_localized() -> None:
    from src.backend.editor_backend import describe_issues
    from src.backend.locale_manager import LocaleManager

    LocaleManager(default_lang="tr")
    text = describe_issues([("missing", ["{0}"]), ("unexpected", ["<b>", "</b>"])])
    assert text == "Eksik etiket/yer tutucu: {0}; Fazladan etiket/yer tutucu: <b> </b>"


def test_bilingual_mode_formatting() -> None:
    from src.core.pipeline.orchestrator import make_bilingual, apply_bilingual_mode, prepare_for_display

    assert make_bilingual("Hello", "Selam") == "Selam\n(Hello)"
    assert make_bilingual("OK", "OK") == "OK"
    assert make_bilingual("+", "+") == "+"
    assert make_bilingual("X", "Kapat") == "Kapat"

    batch = {"Start": "Başla", "Continue": "Devam Et", "X": "X"}
    bilingual = apply_bilingual_mode(batch)
    assert bilingual["Start"] == "Başla\n(Start)"
    assert bilingual["Continue"] == "Devam Et\n(Continue)"
    assert bilingual["X"] == "X"

    prepared = prepare_for_display(batch, "tr", rtl_shaping=False, bilingual_mode=True)
    assert prepared["Start"] == "Başla\n(Start)"
