# -*- coding: utf-8 -*-
"""In-memory SQLite index over a review session: filtered, searched and paged row lookups.

The session stays the source of truth (edits, validation, saving); this index only mirrors
the columns the editor filters on, so a 40,000-row dictionary pages and searches in
milliseconds instead of rebuilding a Python list on every keystroke.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from collections.abc import Callable

from src.core.pipeline.review_session import ALL_STATUSES, ReviewRow, ReviewSession
from src.core.syntax_guard import UNITY_PROTECT_RE
from src.core.text_fold import fold

FILTER_MODIFIED = "modified"
FILTER_WARNINGS = "warnings"
# Chip filters: every status plus "edited by hand" and "has a format problem".
ALL_FILTERS: tuple[str, ...] = (*ALL_STATUSES, FILTER_MODIFIED, FILTER_WARNINGS)


def _search_blob(row: ReviewRow) -> str:
    return fold(f"{row.original}\n{row.translation}")


def replace_outside_tokens(text: str, find: str, replace: str, match_case: bool) -> str:
    """Replace *find* in *text* but never inside RichText tags or {placeholders}."""
    pattern = re.compile(re.escape(find), 0 if match_case else re.IGNORECASE)
    parts: list[str] = []
    position = 0
    for match in UNITY_PROTECT_RE.finditer(text):
        parts.append(pattern.sub(lambda _m: replace, text[position:match.start()]))
        parts.append(match.group(0))
        position = match.end()
    parts.append(pattern.sub(lambda _m: replace, text[position:]))
    return "".join(parts)


class ReviewStore:
    """Row ids of a session by filter, search text and page."""

    def __init__(self, session: ReviewSession) -> None:
        self._session = session
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE rows (id INTEGER PRIMARY KEY, status TEXT NOT NULL, modified INTEGER NOT NULL, "
            "problem INTEGER NOT NULL, search TEXT NOT NULL)"
        )
        self._conn.execute("CREATE INDEX idx_status ON rows(status)")
        self._conn.executemany(
            "INSERT INTO rows VALUES (?, ?, ?, ?, ?)", [self._values(row) for row in session.rows]
        )
        self._conn.commit()

    @staticmethod
    def _values(row: ReviewRow) -> tuple[int, str, int, int, str]:
        return (row.row_id, row.status, int(row.dirty), int(bool(row.issues)), _search_blob(row))

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _where(status: str, query: str) -> tuple[str, list[object]]:
        clauses: list[str] = []
        params: list[object] = []
        if status == FILTER_MODIFIED:
            clauses.append("modified = 1")
        elif status == FILTER_WARNINGS:
            clauses.append("problem = 1")
        elif status:
            clauses.append("status = ?")
            params.append(status)
        needle = fold(query.strip())
        if needle:
            clauses.append("instr(search, ?) > 0")
            params.append(needle)
        return ("WHERE " + " AND ".join(clauses)) if clauses else "", params

    def count(self, status: str = "", query: str = "") -> int:
        where, params = self._where(status, query)
        with self._lock:
            return int(self._conn.execute(f"SELECT COUNT(*) FROM rows {where}", params).fetchone()[0])

    def page(self, status: str = "", query: str = "", page: int = 1, page_size: int = 50) -> list[int]:
        """Row ids on a 1-based page, in session order."""
        where, params = self._where(status, query)
        offset = (max(1, page) - 1) * page_size
        with self._lock:
            found = self._conn.execute(
                f"SELECT id FROM rows {where} ORDER BY id LIMIT ? OFFSET ?", [*params, page_size, offset]
            ).fetchall()
        return [int(r[0]) for r in found]

    def ids(self, status: str = "", query: str = "") -> list[int]:
        """Every matching row id (for bulk operations)."""
        where, params = self._where(status, query)
        with self._lock:
            return [int(r[0]) for r in self._conn.execute(f"SELECT id FROM rows {where} ORDER BY id", params)]

    def counts(self) -> dict[str, int]:
        """Rows per chip filter, every filter present."""
        counts = dict.fromkeys(ALL_FILTERS, 0)
        with self._lock:
            for status, number in self._conn.execute("SELECT status, COUNT(*) FROM rows GROUP BY status"):
                counts[status] = int(number)
            counts[FILTER_MODIFIED] = int(self._conn.execute("SELECT COUNT(*) FROM rows WHERE modified = 1").fetchone()[0])
            counts[FILTER_WARNINGS] = int(self._conn.execute("SELECT COUNT(*) FROM rows WHERE problem = 1").fetchone()[0])
        return counts

    def refresh(self, row: ReviewRow) -> None:
        """Mirror a row after the session changed it."""
        with self._lock:
            self._conn.execute(
                "UPDATE rows SET status = ?, modified = ?, problem = ?, search = ? WHERE id = ?",
                (row.status, int(row.dirty), int(bool(row.issues)), _search_blob(row), row.row_id),
            )
            self._conn.commit()

    def replace_all(
        self, find: str, replace: str, match_case: bool, status: str = "", query: str = "",
        edit: Callable[[int, str], ReviewRow] | None = None,
    ) -> int:
        """Replace in the translations of matching rows (tags and placeholders are left alone).

        Returns how many rows changed. Each change goes through ``edit`` (default: the session's
        guarded edit), so a replacement that breaks a placeholder marks the row invalid.
        """
        if not find:
            return 0
        apply = edit or self._session.edit
        changed = 0
        for row_id in self.ids(status, query):
            row = self._session.rows[row_id]
            if not row.translation:
                continue
            new = replace_outside_tokens(row.translation, find, replace, match_case)
            if new != row.translation:
                self.refresh(apply(row_id, new))
                changed += 1
        return changed
