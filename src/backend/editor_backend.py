# -*- coding: utf-8 -*-
"""Review editor bridge: browse, repair and approve a pipeline run's translations."""

from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from src.backend.locale_manager import LocaleManager
from src.core.pipeline.orchestrator import UnityTranslationPipeline
from src.core.pipeline.review_session import ALL_STATUSES, Issue, ReviewRow, ReviewSession
from src.core.rtl_shaper import is_rtl_language
from src.core.translators.manager import TranslationManager

logger = logging.getLogger(__name__)

# Upper bound of rows handed to QML at once; the search box narrows larger sets.
MAX_VISIBLE_ROWS = 500


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
    """Bridge exposing the last run's ``ReviewSession`` to the editor view."""

    dataChanged = pyqtSignal()
    statsUpdated = pyqtSignal()
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
        self._filter_query: str = ""
        self._status_filter: str = ""

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
        """Rows matching the status filter and search query (capped for UI responsiveness)."""
        if self._session is None:
            return []
        rows = self._session.filtered(self._status_filter, self._filter_query)
        return [_row_to_qml(row) for row in rows[:MAX_VISIBLE_ROWS]]

    @pyqtProperty(int, notify=dataChanged)
    def matchCount(self) -> int:
        """Total matches before the display cap."""
        if self._session is None:
            return 0
        return len(self._session.filtered(self._status_filter, self._filter_query))

    @pyqtProperty(int, constant=True)
    def maxVisibleRows(self) -> int:
        return MAX_VISIBLE_ROWS

    @pyqtProperty("QVariantMap", notify=statsUpdated)
    def counts(self) -> dict[str, int]:
        return self._session.counts() if self._session else dict.fromkeys(ALL_STATUSES, 0)

    @pyqtProperty(int, notify=statsUpdated)
    def totalCount(self) -> int:
        return len(self._session.rows) if self._session else 0

    @pyqtProperty(int, notify=statsUpdated)
    def shippableCount(self) -> int:
        return len(self._session.shippable()) if self._session else 0

    @pyqtProperty(str, notify=dataChanged)
    def statusFilter(self) -> str:
        return self._status_filter

    @pyqtSlot(object)
    def loadSession(self, session: ReviewSession) -> None:
        """Receive a finished run from the pipeline (connected to AppBackend.reviewReady)."""
        self._session = session
        self._status_filter = ""
        self._filter_query = ""
        logger.info("Review session loaded: %d rows", len(session.rows))
        self._notify()

    @pyqtSlot(str)
    def setFilterQuery(self, query: str) -> None:
        self._filter_query = query.strip()
        self.dataChanged.emit()

    @pyqtSlot(str)
    def setStatusFilter(self, status: str) -> None:
        self._status_filter = status if status in ALL_STATUSES else ""
        self.dataChanged.emit()

    @pyqtSlot(int, str)
    def updateTranslation(self, row_id: int, new_text: str) -> None:
        """Apply a manual edit; the row is re-validated by the Syntax Guard."""
        if self._session is None or not 0 <= row_id < len(self._session.rows):
            return
        if self._session.rows[row_id].translation == new_text:
            return
        row = self._session.edit(row_id, new_text)
        if row.issues:
            self.toastRequested.emit(_t("editor.edit_invalid", errors=describe_issues(row.issues)), "warning")
        self._notify()

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
            count = len(self._session.shippable())
            self.toastRequested.emit(_t("editor.save_success", count=count), "success")
        else:
            self.toastRequested.emit(_t("editor.save_failed", error=_t("editor.write_error")), "error")

    @pyqtSlot(str)
    def onUiLanguageChanged(self, _lang_code: str = "") -> None:
        """Re-emit row data so localized Syntax Guard issue messages update immediately."""
        if self._session is not None:
            self._notify()

    def _notify(self) -> None:
        self.dataChanged.emit()
        self.statsUpdated.emit()
