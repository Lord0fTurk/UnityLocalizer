# -*- coding: utf-8 -*-
"""Bookkeeping of what a text harvest saw, skipped and could only read roughly.

The numbers drive two things: whether a finished harvest has to be repeated once the
game's language is known (localization tables are picked by language), and the
coverage warnings shown to the user ("some text may be missing").
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

# A file listed in the report only when it needs attention; clean files are just counted.
_REPORT_FILE_LIMIT = 50


@dataclass
class FileStat:
    """What one serialized file contributed."""

    name: str
    strings: int = 0
    failed: bool = False
    # MonoBehaviours read by rough raw scanning because no TypeTree was available.
    raw_scanned: int = 0


@dataclass
class HarvestStats:
    """Aggregated harvest observations, filled in by the asset harvester."""

    files: list[FileStat] = field(default_factory=list)
    # Unity Localization StringTables whose locale matched / did not match the source language.
    tables_matched: int = 0
    tables_skipped: Counter[str] = field(default_factory=Counter)
    # I2 sources where the source language was not found and the first column was used.
    i2_unmatched: int = 0
    i2_sources: int = 0
    encrypted_code: bool = False

    @property
    def files_failed(self) -> list[str]:
        return [f.name for f in self.files if f.failed]

    @property
    def raw_scanned_objects(self) -> int:
        return sum(f.raw_scanned for f in self.files)

    @property
    def raw_scanned_files(self) -> list[str]:
        return [f.name for f in self.files if f.raw_scanned]

    @property
    def language_sensitive(self) -> bool:
        """True when the chosen source language changed which text was harvested."""
        return bool(self.tables_matched or self.tables_skipped or self.i2_sources)

    def dominant_skipped_locale(self) -> str | None:
        """The locale of the largest StringTables skipped, when none matched the source.

        A game that ships only e.g. Japanese tables loses all of them to an English
        default, so the harvest has to be repeated with the locale that was seen.
        """
        if self.tables_matched or not self.tables_skipped:
            return None
        return self.tables_skipped.most_common(1)[0][0]

    def to_report(self) -> dict[str, Any]:
        """JSON-serializable summary for the diagnostics file."""
        interesting = [f for f in self.files if f.failed or f.raw_scanned]
        return {
            "files_scanned": len(self.files),
            "files_failed": self.files_failed,
            "raw_scanned_objects": self.raw_scanned_objects,
            "string_tables_matched": self.tables_matched,
            "string_tables_skipped_by_locale": dict(self.tables_skipped),
            "i2_sources": self.i2_sources,
            "i2_source_language_not_found": self.i2_unmatched,
            "code_strings_unavailable": self.encrypted_code,
            "files": [
                {"name": f.name, "strings": f.strings, "failed": f.failed, "raw_scanned_objects": f.raw_scanned}
                for f in (interesting + [f for f in self.files if f not in interesting])[:_REPORT_FILE_LIMIT]
            ],
        }
