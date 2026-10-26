# -*- coding: utf-8 -*-
"""Post-run translation review: inspect, repair and approve results before shipping.

A ``ReviewSession`` turns a ``TranslationReport`` into editable rows. Integrity
rejections keep their broken candidate so a human can repair it; every edit is
re-validated with the same Syntax Guard gate the batch runner uses, so a manual
fix can never reintroduce a missing ``{0}`` or an unbalanced tag.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from src.core.parsers.auto_translator import expand_dialogue_and_quote_variants
from src.core.pipeline.translation_runner import TranslationReport
from src.core.syntax_guard import UnitySyntaxGuard
from src.core.text_fold import fold

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
    # The state the row had when the session was built; "revert" returns to it.
    initial_translation: str | None = None
    initial_status: str | None = None
    initial_issues: list[Issue] | None = None

    def __post_init__(self) -> None:
        if self.initial_translation is None:
            self.initial_translation = self.translation
            self.initial_status = self.status
            self.initial_issues = list(self.issues)


@dataclass(frozen=True)
class RunContext:
    """Where and how a reviewed run must be deployed."""

    game_root: Path
    target_lang: str
    source_lang: str = "auto"
    engine: str = "google"
    rtl_shaping: bool = True
    bilingual_mode: bool = False
    bilingual_template: str = "{target}\n({source})"
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

    @classmethod
    def from_dictionary(cls, entries: Iterable[tuple[str, str]], context: RunContext) -> ReviewSession:
        """Rows for a game's existing dictionary (no run needed): problems first, then the rest.

        The writer appends variants derived from earlier entries (speaker-less dialogue bodies,
        curly quotes, real line breaks). An entry already produced by an earlier one is left out
        so every text appears once; saving regenerates the variants from the reviewed rows.
        """
        derived: set[str] = set()
        invalid: list[tuple[str, str, str, list[Issue]]] = []
        rest: list[tuple[str, str, str, list[Issue]]] = []
        for key, value in dict.fromkeys(entries):
            if key in derived:
                continue
            derived.update(k for k in expand_dialogue_and_quote_variants({key: value}) if k != key)
            if value == key:
                rest.append((key, value, STATUS_UNCHANGED, []))
                continue
            issues = UnitySyntaxGuard.integrity_issues(key, value)
            (invalid if issues else rest).append((key, value, STATUS_INVALID if issues else STATUS_ACCEPTED, issues))
        ordered = invalid + rest
        return cls([ReviewRow(i, o, t, s, e) for i, (o, t, s, e) in enumerate(ordered)], context)

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

    def revert(self, row_id: int) -> ReviewRow:
        """Put a row back to the state it had when the session was built."""
        if not (0 <= row_id < len(self.rows)):
            raise IndexError(f"Review row index out of range: {row_id}")
        row = self.rows[row_id]
        row.translation = row.initial_translation or ""
        row.status = row.initial_status or row.status
        row.issues = list(row.initial_issues or [])
        row.dirty = False
        return row

    def filtered(self, status: str = "", query: str = "") -> list[ReviewRow]:
        """Rows matching a status ('' for all) and a case- and diacritic-insensitive text query."""
        needle = fold(query.strip())
        return [
            row for row in self.rows
            if (not status or row.status == status)
            and (not needle or needle in fold(row.original) or needle in fold(row.translation))
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
