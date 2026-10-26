# -*- coding: utf-8 -*-
"""The review editor opens the dictionary already in the game when no run is being reviewed."""

from pathlib import Path
from typing import Any

import pytest

from src.backend.editor_backend import EditorBackend
from src.core.hook_layout import dictionary_path
from src.core.parsers import xunity_codec
from src.core.pipeline.review_session import STATUS_ACCEPTED, STATUS_INVALID, ReviewSession, RunContext


def _write_dictionary(game: Path, lines: list[tuple[str, str]], lang: str = "tr") -> Path:
    path = dictionary_path(game, lang)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(xunity_codec.encode_line(k, v) for k, v in lines) + "\n", encoding="utf-8-sig")
    return path


@pytest.fixture
def editor() -> Any:
    backend = EditorBackend()
    yield backend


def test_rows_come_from_the_dictionary_problems_first(tmp_path: Path) -> None:
    session = ReviewSession.from_dictionary(
        [("Start", "Başla"), ("Deal {0} damage", "Hasar ver"), ("Quit", "Çık")], RunContext(tmp_path, "tr")
    )
    assert [r.original for r in session.rows] == ["Deal {0} damage", "Start", "Quit"]
    assert session.rows[0].status == STATUS_INVALID and session.rows[0].issues
    assert {r.status for r in session.rows[1:]} == {STATUS_ACCEPTED}


def test_variants_derived_from_an_earlier_entry_are_not_listed_twice(tmp_path: Path) -> None:
    entries = [
        ("Don't stop.\\nGo on.", "Durma.\\nDevam et."),
        ("Don't stop.\nGo on.", "Durma.\nDevam et."),  # real line break variant the writer derives
        ("Don't stop", "Durma"),
        ("Don’t stop", "Durma"),  # curly quote variant of the previous entry
    ]
    session = ReviewSession.from_dictionary(entries, RunContext(tmp_path, "tr"))
    assert [r.original for r in session.rows] == ["Don't stop.\\nGo on.", "Don't stop"]


def test_backend_opens_the_dictionary_of_the_selected_game(editor: Any, tmp_path: Path) -> None:
    _write_dictionary(tmp_path, [("Start", "Başla"), ("Quit", "Çık")])
    editor.loadExisting(str(tmp_path), "tr", "auto")
    assert editor.hasSession and editor.totalCount == 2
    assert editor._session.context.source_lang == "en" and editor._session.context.rtl_shaping is False


def test_a_finished_run_for_the_same_game_is_not_replaced(editor: Any, tmp_path: Path) -> None:
    _write_dictionary(tmp_path, [("Start", "Başla")])
    run = ReviewSession.from_dictionary([("Only in run", "Sadece çalıştırmada")], RunContext(tmp_path, "tr"))
    editor.loadSession(run)
    editor.loadExisting(str(tmp_path), "tr", "en")
    assert editor._session is run


def test_no_dictionary_or_a_right_to_left_target_leaves_the_editor_empty(editor: Any, tmp_path: Path) -> None:
    editor.loadExisting(str(tmp_path), "tr", "en")
    assert not editor.hasSession
    _write_dictionary(tmp_path, [("Start", "ابدأ")], lang="ar")
    editor.loadExisting(str(tmp_path), "ar", "en")
    assert not editor.hasSession


def test_a_different_game_replaces_the_session(editor: Any, tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    _write_dictionary(first, [("One", "Bir")])
    _write_dictionary(second, [("Two", "İki"), ("Three", "Üç")])
    editor.loadExisting(str(first), "tr", "en")
    editor.loadExisting(str(second), "tr", "en")
    assert editor.totalCount == 2
