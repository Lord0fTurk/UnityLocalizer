# -*- coding: utf-8 -*-
"""Paged, searchable review rows: SQLite index, Turkish-aware search, revert and replace-all."""

from pathlib import Path
from typing import Any

import pytest

from src.core.pipeline.review_session import ReviewRow, ReviewSession, RunContext
from src.core.pipeline.review_store import ReviewStore, replace_outside_tokens
from src.core.text_fold import fold


def _session(count: int = 120) -> ReviewSession:
    rows = [ReviewRow(i, f"Line {i}", f"Satır {i}", "accepted") for i in range(count)]
    rows[0] = ReviewRow(0, "Istanbul gate", "İstanbul kapısı", "accepted")
    rows[1] = ReviewRow(1, "Quiet light", "Sessiz ışık", "accepted")
    rows[2] = ReviewRow(2, "Deal {0} damage", "Hasar {0}", "rejected", [("missing", ["{0}"])])
    return ReviewSession(rows, RunContext(Path("."), "tr"))


def test_fold_makes_turkish_text_searchable_with_plain_letters() -> None:
    assert fold("İstanbul") == fold("Istanbul") == fold("istanbul") == "istanbul"
    assert fold("ışık") == "isik" and fold("Şğüöç") == "sguoc"


def test_search_finds_turkish_translations_typed_without_diacritics() -> None:
    store = ReviewStore(_session())
    assert store.page("", "istanbul") == [0]
    assert store.page("", "isik") == [1]
    assert store.page("", "KAPISI") == [0]
    assert store.count("", "yokboyle") == 0


def test_paging_filters_and_counts() -> None:
    store = ReviewStore(_session(120))
    assert store.count() == 120
    assert len(store.page(page=1, page_size=50)) == 50
    assert store.page(page=3, page_size=50) == list(range(100, 120))
    assert store.ids("rejected") == [2]
    counts = store.counts()
    assert counts["accepted"] == 119 and counts["rejected"] == 1 and counts["warnings"] == 1 and counts["modified"] == 0


def test_refresh_mirrors_edits_into_filters() -> None:
    session = _session()
    store = ReviewStore(session)
    store.refresh(session.edit(5, "Beş"))
    assert store.ids("modified") == [5]
    assert store.ids("edited") == [5]
    assert store.page("", "beş") == [5]


def test_revert_restores_the_state_the_session_started_with() -> None:
    session = _session()
    session.edit(2, "Hasar {0} verir")
    assert session.rows[2].status == "edited"
    reverted = session.revert(2)
    assert (reverted.translation, reverted.status, reverted.dirty) == ("Hasar {0}", "rejected", False)
    assert reverted.issues == [("missing", ["{0}"])]


def test_replace_never_touches_tags_or_placeholders() -> None:
    text = "Hasar <color=red>red</color> {red} red"
    assert replace_outside_tokens(text, "red", "mavi", False) == "Hasar <color=red>mavi</color> {red} mavi"
    assert replace_outside_tokens("Red red", "red", "x", True) == "Red x"


def test_replace_all_follows_the_filter_and_validates_each_row() -> None:
    session = _session()
    store = ReviewStore(session)
    changed = store.replace_all("Satır", "Hat", False, query="satir 1")
    assert changed == len(store.ids("modified")) and changed > 0
    assert all(session.rows[i].translation.startswith("Hat") for i in store.ids("modified"))
    assert session.rows[3].translation == "Satır 3"  # outside the search: untouched
    assert store.replace_all("{0}", "", True, status="rejected") == 0  # placeholders are never replaced
    broken = store.replace_all("Hasar", "Hasar {1}", True, status="rejected")  # adds a placeholder: guarded
    assert broken == 1 and session.rows[2].status == "invalid"


# --- Qt bridge -------------------------------------------------------------------


class _Pipeline:
    def save_review(self, session: ReviewSession) -> bool:
        return True


@pytest.fixture
def editor() -> Any:
    from src.backend.editor_backend import EditorBackend

    backend = EditorBackend(pipeline=_Pipeline())  # type: ignore[arg-type]
    backend.loadSession(_session(120))
    return backend


def test_backend_pages_and_keeps_the_page_when_a_row_is_edited(editor: Any) -> None:
    assert editor.pageCount == 3 and editor.page == 1 and len(editor.filteredRows) == 50
    editor.setPage(2)
    assert editor.filteredRows[0]["id"] == 50 and editor.selected["id"] == 50
    editor.updateTranslation(50, "Elli")
    assert editor.page == 2 and editor.filteredRows[0]["translation"] == "Elli"
    assert editor.counts["modified"] == 1


def test_backend_search_resets_to_the_first_page_and_selects_a_row(editor: Any) -> None:
    editor.setPage(3)
    editor.setFilterQuery("istanbul")
    assert editor.page == 1 and [r["id"] for r in editor.filteredRows] == [0]
    assert editor.selected["id"] == 0 and editor.matchCount == 1


def test_backend_select_check_revert_and_replace(editor: Any) -> None:
    editor.select(2)
    assert editor.selected["tokens"] == ["{0}"] and editor.selected["status"] == "rejected"
    assert editor.checkText("Hasar") != ""            # placeholder dropped
    assert editor.checkText("Hasar {0}") == ""
    editor.updateTranslation(2, "Hasar {0} verir")
    assert editor.selected["dirty"] is True and editor.selected["initial"] == "Hasar {0}"
    editor.revertSelected()
    assert editor.selected["dirty"] is False and editor.selected["translation"] == "Hasar {0}"

    toasts: list[tuple[str, str]] = []
    editor.toastRequested.connect(lambda msg, kind: toasts.append((msg, kind)))
    editor.setFilterQuery("satir 7")
    changed = editor.replaceAll("Satır", "Hat", False)
    assert changed == editor.counts["modified"] and changed > 0
    assert toasts[-1][1] == "success"
    assert editor.replaceAll("", "x", False) == 0


def test_backend_unknown_filter_is_ignored_and_new_filters_work(editor: Any) -> None:
    editor.setStatusFilter("bogus")
    assert editor.statusFilter == ""
    editor.setStatusFilter("warnings")
    assert [r["id"] for r in editor.filteredRows] == [2]
    editor.setStatusFilter("modified")
    assert editor.filteredRows == []
