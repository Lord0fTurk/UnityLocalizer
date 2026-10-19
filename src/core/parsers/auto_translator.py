# -*- coding: utf-8 -*-
"""Parser for XUnity.AutoTranslator dictionary text files.

The dictionary UnityLocalizer writes holds plain ``key=value`` entries followed by
a generated section of regex entries for strings whose placeholders are filled
in at runtime (``Gold: {0}`` -> ``Gold: 150``). That section is rebuilt from the
plain entries on every write, so it always matches them; everything outside it,
including entries and regexes added by hand, is preserved.
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.core.parsers import xunity_codec
from src.core.parsers.base import BaseParser
from src.core.parsers.xunity_regex import build_regex_entries
from src.utils.file_ops import safe_write

logger = logging.getLogger(__name__)

REGEX_SECTION_BEGIN = "// <UnityLocalizer:runtime-formats> generated from the entries above, edits are overwritten"
REGEX_SECTION_END = "// </UnityLocalizer:runtime-formats>"


class AutoTranslatorParser(BaseParser):
    """Parses and updates XUnity.AutoTranslator key=value dictionary files."""

    def extract_strings(self, file_path: Path | str, only_untranslated: bool = False) -> list[str]:
        """Extract decoded original keys from a dictionary file."""
        keys: list[str] = []
        for key, value in self._read_entries(Path(file_path)):
            if only_untranslated and value.strip():
                continue
            keys.append(key)
        return keys

    @staticmethod
    def _read_lines(path: Path) -> list[str]:
        """Read raw dictionary lines without trailing newlines."""
        if not path.is_file():
            return []
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
                return [line.rstrip("\r\n") for line in f]
        except OSError as exc:
            logger.warning("Failed to read AutoTranslator dictionary %s: %s", path, exc)
            return []

    def _read_entries(self, path: Path) -> list[tuple[str, str]]:
        """Decode all plain (non-regex) key/value entries of a dictionary file."""
        entries: list[tuple[str, str]] = []
        for line in self._read_lines(path):
            if xunity_codec.is_comment(line):
                continue
            decoded = xunity_codec.decode_line(line)
            if decoded and xunity_codec.is_literal_key(decoded[0]):
                entries.append(decoded)
        return entries

    def apply_translations(
        self,
        file_path: Path | str,
        translations: dict[str, str],
        output_path: Path | str | None = None,
    ) -> bool:
        """Merge translations, keep other lines verbatim and regenerate the regex section."""
        path = Path(file_path)
        out_path = Path(output_path) if output_path else path
        literal = {k: v for k, v in translations.items() if xunity_codec.is_literal_key(k)}
        if len(literal) != len(translations):
            # XUnity reads keys starting with r:/sr: as regexes, so such texts cannot be keys.
            logger.info("Skipped %d texts starting with r:/sr:", len(translations) - len(literal))
        kept = self._without_generated_section(self._read_lines(path))
        lines_out, entries = self._merge_entries(kept, literal)
        lines_out += self._regex_section(entries)
        try:
            return safe_write(out_path, "\n".join(lines_out) + "\n", encoding="utf-8-sig")
        except OSError as exc:
            logger.error("Failed to write AutoTranslator dictionary %s: %s", out_path, exc)
            return False

    @staticmethod
    def _without_generated_section(lines: list[str]) -> list[str]:
        """Drop the previously generated regex section (it is rebuilt from the entries)."""
        kept: list[str] = []
        inside = False
        for line in lines:
            if line.strip() == REGEX_SECTION_BEGIN:
                inside = True
            elif line.strip() == REGEX_SECTION_END:
                inside = False
            elif not inside:
                kept.append(line)
        return kept

    @staticmethod
    def _merge_entries(lines: list[str], translations: dict[str, str]) -> tuple[list[str], dict[str, str]]:
        """Update existing entries in place, append new ones; return lines and all plain entries."""
        lines_out: list[str] = []
        entries: dict[str, str] = {}
        for line in lines:
            decoded = None if xunity_codec.is_comment(line) else xunity_codec.decode_line(line)
            if decoded is None or not xunity_codec.is_literal_key(decoded[0]):
                lines_out.append(line)  # comments, directives and hand-written regexes
                continue
            key, value = decoded
            if key in translations:
                value = translations[key]
                line = xunity_codec.encode_line(key, value)
            entries[key] = value
            lines_out.append(line)
        for key, value in translations.items():
            if key not in entries:
                entries[key] = value
                lines_out.append(xunity_codec.encode_line(key, value))
        return lines_out, entries

    @staticmethod
    def _regex_section(entries: dict[str, str]) -> list[str]:
        """Regex entries for runtime-formatted strings, between the section markers."""
        regexes = build_regex_entries(entries.items())
        if not regexes:
            return []
        return [REGEX_SECTION_BEGIN, *(xunity_codec.encode_line(k, v) for k, v in regexes), REGEX_SECTION_END]
