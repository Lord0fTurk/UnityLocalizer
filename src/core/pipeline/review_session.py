# -*- coding: utf-8 -*-
"""Post-run translation review: inspect, repair and approve results before shipping.

A ``ReviewSession`` turns a ``TranslationReport`` into editable rows. Integrity
rejections keep their broken candidate so a human can repair it; every edit is
re-validated with the same Syntax Guard gate the batch runner uses, so a manual
fix can never reintroduce a missing ``{0}`` or an unbalanced tag.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.core.pipeline.translation_runner import TranslationReport
from src.core.syntax_guard import UnitySyntaxGuard

STATUS_ACCEPTED = "accepted"
STATUS_EDITED = "edited"
STATUS_REPAIRED = "repaired"
STATUS_REJECTED = "rejected"
STATUS_INVALID = "invalid"
STATUS_FAILED = "failed"
STATUS_UNCHANGED = "unchanged"

ALL_STATUSES: tuple[str, ...] = (
    STATUS_ACCEPTED, STATUS_REPAIRED, STATUS_EDITED, STATUS_REJECTED, STATUS_INVALID, STATUS_FAILED, STATUS_UNCHANGED,
)
SHIPPABLE_STATUSES = frozenset({STATUS_ACCEPTED, STATUS_REPAIRED, STATUS_EDITED})

# (issue code, offending tokens) as produced by UnitySyntaxGuard.integrity_issues.
Issue = tuple[str, list[str]]


@dataclass
class ReviewRow:
    """One source string with its current translation and validation state."""

    row_id: int
    original: str
    translation: str
    status: str
    issues: list[Issue] = field(default_factory=list)
    dirty: bool = False


@dataclass(frozen=True)
class RunContext:
    """Where and how a reviewed run must be deployed."""

    game_root: Path
    target_lang: str
    source_lang: str = "auto"
    engine: str = "google"
    rtl_shaping: bool = True
    streaming_files: tuple[Path, ...] = ()


class ReviewSession:
    """Editable, validated view over one pipeline run."""

    def __init__(self, rows: list[ReviewRow], context: RunContext) -> None:
        self.rows = rows
        self.context = context

    @classmethod
    def from_report(cls, report: TranslationReport, context: RunContext) -> ReviewSession:
        """Build rows: problems first (rejected, failed), then accepted and unchanged."""
        entries: list[tuple[str, str, str, list[Issue]]] = []
        for original in report.rejected:
            candidate = report.rejected_translations.get(original, "")
            issues = UnitySyntaxGuard.integrity_issues(original, candidate)
            entries.append((original, candidate, STATUS_REJECTED, issues))
        entries += [(original, "", STATUS_FAILED, []) for original in report.failed_sources]
        entries += [(o, t, STATUS_REPAIRED, []) for o, t in report.translations.items() if o in report.repaired]
        entries += [(o, t, STATUS_ACCEPTED, []) for o, t in report.translations.items() if o not in report.repaired]
        entries += [(o, o, STATUS_UNCHANGED, []) for o in report.unchanged_sources]
        rows = [ReviewRow(i, o, t, s, e) for i, (o, t, s, e) in enumerate(entries)]
        return cls(rows, context)

    def edit(self, row_id: int, text: str) -> ReviewRow:
        """Apply a manual translation and re-run the integrity gate on it."""
        if not (0 <= row_id < len(self.rows)):
            raise IndexError(f"Review row index out of range: {row_id}")
        row = self.rows[row_id]
        row.translation = text
        row.dirty = True
        if not text.strip():
            row.status, row.issues = STATUS_FAILED, []
            return row
        if text == row.original:
            row.status, row.issues = STATUS_UNCHANGED, []
            return row
        row.issues = UnitySyntaxGuard.integrity_issues(row.original, text)
        row.status = STATUS_INVALID if row.issues else STATUS_EDITED
        return row

    def filtered(self, status: str = "", query: str = "") -> list[ReviewRow]:
        """Rows matching a status ('' for all) and a case-insensitive text query."""
        needle = query.strip().lower()
        return [
            row for row in self.rows
            if (not status or row.status == status)
            and (not needle or needle in row.original.lower() or needle in row.translation.lower())
        ]

    def counts(self) -> dict[str, int]:
        """Number of rows per status (every status present, zero included)."""
        counts = dict.fromkeys(ALL_STATUSES, 0)
        for row in self.rows:
            counts[row.status] += 1
        return counts

    def shippable(self) -> dict[str, str]:
        """Source -> translation for every row that passed validation."""
        return {row.original: row.translation for row in self.rows if row.status in SHIPPABLE_STATUSES}

    def edited(self) -> dict[str, str]:
        """Validated manual edits, e.g. for persisting into the translation cache."""
        return {row.original: row.translation for row in self.rows if row.dirty and row.status == STATUS_EDITED}
