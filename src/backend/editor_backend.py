# -*- coding: utf-8 -*-
"""Review editor bridge: browse, repair and approve a pipeline run's (or a game's) translations."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from src.backend.locale_manager import LocaleManager
from src.core.hook_layout import dictionary_path
from src.core.parsers.auto_translator import AutoTranslatorParser
from src.core.pipeline.orchestrator import UnityTranslationPipeline
from src.core.pipeline.review_session import (
    SHIPPABLE_STATUSES,
    Issue,
    ReviewRow,
    ReviewSession,
    RunContext,
)
from src.core.pipeline.review_store import ALL_FILTERS, ReviewStore
from src.core.rtl_shaper import is_rtl_language
from src.core.syntax_guard import UNITY_PROTECT_RE, UnitySyntaxGuard
from src.core.translators.manager import TranslationManager

logger = logging.getLogger(__name__)

# Rows per page; the list stays light however large the dictionary is.
PAGE_SIZE = 50


def _t(key: str, **params: Any) -> str:
    """Resolve a UI string through the shared locale manager."""
    lm = LocaleManager.get_instance()
    text = lm.t(key, key) if lm else key
    for name, value in params.items():
        text = text.replace(f"{{{name}}}", str(value))
    return text


def describe_issues(issues: list[Issue]) -> str:
    """Localized, human-readable summary of Syntax Guard issue codes."""
    return "; ".join(_t(f"editor.issue_{code}", tokens=" ".join(tokens)) for code, tokens in issues)


def code_tokens(text: str) -> list[str]:
    """RichText tags and placeholders in *text*, unique, in order of appearance."""
    return list(dict.fromkeys(match.group(0) for match in UNITY_PROTECT_RE.finditer(text or "")))


def _row_to_qml(row: ReviewRow) -> dict[str, Any]:
    """Plain dict for QML delegates."""
    return {
        "id": row.row_id,
        "original": row.original,
        "translation": row.translation,
        "status": row.status,
        "errors": describe_issues(row.issues),
        "dirty": row.dirty,
    }


class EditorBackend(QObject):
    """Bridge exposing a ``ReviewSession`` to the editor view as filtered, searchable pages."""

    dataChanged = pyqtSignal()
    statsUpdated = pyqtSignal()
    selectedChanged = pyqtSignal()
    toastRequested = pyqtSignal(str, str)

    def __init__(
        self,
        translation_manager: TranslationManager | None = None,
        pipeline: UnityTranslationPipeline | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.pipeline = pipeline or UnityTranslationPipeline(translation_manager)
        self._session: ReviewSession | None = None
        self._store: ReviewStore | None = None
        self._filter_query: str = ""
        self._status_filter: str = ""
        self._page: int = 1
        self._match_count: int = 0
        self._page_rows: list[dict[str, Any]] = []
        self._counts: dict[str, int] = dict.fromkeys(ALL_FILTERS, 0)
        self._selected_id: int = -1

    # ── Session state ───────────────────────────────────────────────────

    def _set_session(self, session: ReviewSession | None) -> None:
        if self._store is not None:
            self._store.close()
        self._session = session
        self._store = ReviewStore(session) if session is not None else None
        self._status_filter = ""
        self._filter_query = ""
        self._page = 1
        self._selected_id = -1
        self._refresh()

    def _refresh(self) -> None:
        """Recompute counts and the current page (clamped to the page count), then tell the view."""
        store, session = self._store, self._session
        if store is None or session is None:
            self._counts = dict.fromkeys(ALL_FILTERS, 0)
            self._match_count, self._page_rows, self._page, self._selected_id = 0, [], 1, -1
        else:
            self._counts = store.counts()
            self._match_count = store.count(self._status_filter, self._filter_query)
            pages = self.pageCount
            self._page = max(1, min(self._page, pages))
            ids = store.page(self._status_filter, self._filter_query, self._page, PAGE_SIZE)
            self._page_rows = [_row_to_qml(session.rows[i]) for i in ids]
            if self._selected_id not in ids:
                self._selected_id = ids[0] if ids else -1
        self.dataChanged.emit()
        self.statsUpdated.emit()
        self.selectedChanged.emit()

    def _replace_in_page(self, row: ReviewRow) -> None:
        """Update one visible row in place after an edit (the page itself stays put)."""
        view = _row_to_qml(row)
        self._page_rows = [view if r["id"] == row.row_id else r for r in self._page_rows]

    # ── Properties ──────────────────────────────────────────────────────

    @pyqtProperty(bool, notify=dataChanged)
    def hasSession(self) -> bool:
        return self._session is not None

    @pyqtProperty(bool, notify=dataChanged)
    def isRtl(self) -> bool:
        """True when the reviewed target language is right-to-left (editor text direction)."""
        return self._session is not None and is_rtl_language(self._session.context.target_lang)

    @pyqtProperty(str, notify=dataChanged)
    def targetLanguage(self) -> str:
        return self._session.context.target_lang if self._session else ""

    @pyqtProperty(list, notify=dataChanged)
    def filteredRows(self) -> list[dict[str, Any]]:
        """Rows of the current page (matching the status filter and search query)."""
        return self._page_rows

    @pyqtProperty(int, notify=dataChanged)
    def matchCount(self) -> int:
        """Total matches over all pages."""
        return self._match_count

    @pyqtProperty(int, constant=True)
    def pageSize(self) -> int:
        return PAGE_SIZE

    @pyqtProperty(int, notify=dataChanged)
    def page(self) -> int:
        return self._page

    @pyqtProperty(int, notify=dataChanged)
    def pageCount(self) -> int:
        return max(1, (self._match_count + PAGE_SIZE - 1) // PAGE_SIZE)

    @pyqtProperty("QVariantMap", notify=statsUpdated)
    def counts(self) -> dict[str, int]:
        return self._counts

    @pyqtProperty(int, notify=statsUpdated)
    def totalCount(self) -> int:
        return len(self._session.rows) if self._session else 0

    @pyqtProperty(int, notify=statsUpdated)
    def shippableCount(self) -> int:
        return sum(self._counts.get(status, 0) for status in SHIPPABLE_STATUSES)

    @pyqtProperty(str, notify=dataChanged)
    def statusFilter(self) -> str:
        return self._status_filter

    @pyqtProperty("QVariantMap", notify=selectedChanged)
    def selected(self) -> dict[str, Any]:
        """The row being edited: texts, status, issues, placeholders and tags of its source."""
        if self._session is None or not 0 <= self._selected_id < len(self._session.rows):
            return {}
        row = self._session.rows[self._selected_id]
        view = _row_to_qml(row)
        view.update({
            "tokens": code_tokens(row.original),
            "initial": row.initial_translation or "",
            "position": self._selected_id + 1,
        })
        return view

    # ── Slots ───────────────────────────────────────────────────────────

    @pyqtSlot(object)
    def loadSession(self, session: ReviewSession) -> None:
        """Receive a finished run from the pipeline (connected to AppBackend.reviewReady)."""
        logger.info("Review session loaded: %d rows", len(session.rows))
        self._set_session(session)

    @pyqtSlot(str, str, str)
    def loadExisting(self, game_path: str, target_lang: str, source_lang: str) -> None:
        """Open the dictionary already in the game for review (no translation run needed).

        A session from a run that just finished for the same game and language is kept, so
        its rejected and failed rows are not replaced. Right-to-left targets are skipped:
        their dictionary holds shaped text, and a manual edit could not be shaped again.
        """
        if not game_path:
            return
        root = Path(game_path)
        root = root if root.is_dir() else root.parent
        current = self._session
        if current is not None and current.context.game_root == root and current.context.target_lang == target_lang:
            return
        path = dictionary_path(root, target_lang)
        session: ReviewSession | None = None
        if not is_rtl_language(target_lang) and path.is_file():
            context = RunContext(
                root, target_lang, source_lang if source_lang and source_lang != "auto" else "en",
                engine="manual", rtl_shaping=False, bilingual_mode=False,
            )
            session = ReviewSession.from_dictionary(AutoTranslatorParser().read_dictionary(path), context)
            logger.info("Existing dictionary opened for review: %d rows from %s", len(session.rows), path)
        self._set_session(session)

    @pyqtSlot(str)
    def setFilterQuery(self, query: str) -> None:
        self._filter_query = query.strip()
        self._page = 1
        self._refresh()

    @pyqtSlot(str)
    def setStatusFilter(self, status: str) -> None:
        self._status_filter = status if status in ALL_FILTERS else ""
        self._page = 1
        self._refresh()

    @pyqtSlot(int)
    def setPage(self, page: int) -> None:
        self._page = max(1, min(page, self.pageCount))
        self._refresh()

    @pyqtSlot(int)
    def select(self, row_id: int) -> None:
        if self._session is not None and 0 <= row_id < len(self._session.rows) and row_id != self._selected_id:
            self._selected_id = row_id
            self.selectedChanged.emit()

    @pyqtSlot(str, result=str)
    def checkText(self, text: str) -> str:
        """Format problems of *text* as the selected row's translation, while it is typed ('' = fine)."""
        if self._session is None or not 0 <= self._selected_id < len(self._session.rows) or not text.strip():
            return ""
        original = self._session.rows[self._selected_id].original
        if text == original:
            return ""
        return describe_issues(UnitySyntaxGuard.integrity_issues(original, text))

    @pyqtSlot(int, str)
    def updateTranslation(self, row_id: int, new_text: str) -> None:
        """Apply a manual edit; the row is re-validated by the Syntax Guard."""
        if self._session is None or self._store is None or not 0 <= row_id < len(self._session.rows):
            return
        if self._session.rows[row_id].translation == new_text:
            return
        row = self._session.edit(row_id, new_text)
        self._store.refresh(row)
        if row.issues:
            self.toastRequested.emit(_t("editor.edit_invalid", errors=describe_issues(row.issues)), "warning")
        self._after_edit(row)

    @pyqtSlot()
    def revertSelected(self) -> None:
        """Undo every change of the selected row since the session was built."""
        if self._session is None or self._store is None or not 0 <= self._selected_id < len(self._session.rows):
            return
        row = self._session.revert(self._selected_id)
        self._store.refresh(row)
        self._after_edit(row)

    @pyqtSlot(str, str, bool, result=int)
    def replaceAll(self, find: str, replace: str, match_case: bool) -> int:
        """Replace in the translations matching the current filter and search; returns rows changed."""
        if self._session is None or self._store is None or not find:
            return 0
        count = self._store.replace_all(find, replace, match_case, self._status_filter, self._filter_query)
        self._refresh()
        self.toastRequested.emit(_t("editor.replaced", count=count), "success" if count else "info")
        return count

    @pyqtSlot()
    def saveToGame(self) -> None:
        """Write validated rows to the game dictionary and cache manual edits."""
        if self._session is None:
            return
        try:
            written = self.pipeline.save_review(self._session)
        except OSError as exc:
            logger.error("Saving review failed: %s", exc)
            self.toastRequested.emit(_t("editor.save_failed", error=str(exc)), "error")
            return
        if written:
            self.toastRequested.emit(_t("editor.save_success", count=self.shippableCount), "success")
        else:
            self.toastRequested.emit(_t("editor.save_failed", error=_t("editor.write_error")), "error")

    @pyqtSlot(str)
    def onUiLanguageChanged(self, _lang_code: str = "") -> None:
        """Re-emit row data so localized Syntax Guard issue messages update immediately."""
        if self._session is not None:
            self._refresh()

    def _after_edit(self, row: ReviewRow) -> None:
        """Refresh counts and the visible row after one edit, without moving the page or the selection."""
        assert self._store is not None
        self._counts = self._store.counts()
        self._match_count = self._store.count(self._status_filter, self._filter_query)
        self._replace_in_page(row)
        self.dataChanged.emit()
        self.statsUpdated.emit()
        self.selectedChanged.emit()
