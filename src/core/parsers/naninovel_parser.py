# -*- coding: utf-8 -*-
"""Naninovel script (.nani) localization parser.

A Naninovel line is a command (``@cmd ...``), a label (``# Label``), a comment
(``; ...``) or generic text, optionally prefixed by an author id with an
appearance (``Kohaku.Happy: Hello!``). Generic text may embed inline commands
(``[i]``, ``[wait 1]``, ``[char Kohaku]``) the engine executes, so only the text
between them is extracted and each piece is replaced in place on write; author
ids, commands and line endings are never touched. ``@choice "..."`` labels are
the only command arguments that are display text.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from src.core.parsers.base import BaseParser
from src.utils.file_ops import pristine_source, safe_write

logger = logging.getLogger(__name__)

_AUTHOR_RE = re.compile(r"^([\w.]+):\s?")
_INLINE_COMMAND_RE = re.compile(r"(\[[^\]]*\])")
_CHOICE_RE = re.compile(r'(@choice\s+")((?:[^"\\]|\\.)+)(")')


def _is_skipped(stripped: str) -> bool:
    """Blank lines, comments, labels and commands other than @choice."""
    return not stripped or stripped.startswith((";", "#")) or (
        stripped.startswith("@") and not stripped.startswith("@choice")
    )


def _text_pieces(body: str) -> list[str]:
    """Text between inline commands (even indices of the split)."""
    return _INLINE_COMMAND_RE.split(body)[::2]


def line_strings(line: str) -> list[str]:
    """Display strings of one script line."""
    stripped = line.strip()
    if _is_skipped(stripped):
        return []
    choice = _CHOICE_RE.search(stripped)
    if choice:
        return [choice.group(2)]
    body = _AUTHOR_RE.sub("", stripped, count=1)
    return [piece.strip() for piece in _text_pieces(body) if len(piece.strip()) > 1]


def _replace_piece(piece: str, translations: dict[str, str]) -> str:
    """Swap the text of one piece, keeping its surrounding whitespace."""
    core = piece.strip()
    if core not in translations:
        return piece
    start = piece.index(core)
    return piece[:start] + translations[core] + piece[start + len(core):]


def translate_line(line: str, translations: dict[str, str]) -> str:
    """Translate one script line (line ending included) in place."""
    stripped = line.strip()
    if _is_skipped(stripped):
        return line
    if _CHOICE_RE.search(stripped):
        return _CHOICE_RE.sub(
            lambda m: m.group(1) + translations.get(m.group(2), m.group(2)) + m.group(3), line, count=1
        )
    content_start = len(line) - len(line.lstrip())
    author = _AUTHOR_RE.match(line[content_start:])
    body_start = content_start + (author.end() if author else 0)
    parts = _INLINE_COMMAND_RE.split(line[body_start:])
    parts[::2] = [_replace_piece(piece, translations) for piece in parts[::2]]
    return line[:body_start] + "".join(parts)


class NaninovelParser(BaseParser):
    """Parses and localizes Naninovel visual novel scripts (.nani)."""

    def extract_strings(self, file_path: Path | str) -> list[str]:
        """Extract dialogue text and choice labels (from the original backup once patched)."""
        path = Path(file_path)
        if not path.is_file():
            return []
        try:
            text = pristine_source(path).read_text(encoding="utf-8-sig", errors="replace")
        except OSError as exc:
            logger.error("Failed to read Naninovel script %s: %s", path, exc)
            return []
        return [s for line in text.splitlines() for s in line_strings(line)]

    def apply_translations(
        self,
        file_path: Path | str,
        translations: dict[str, str],
        output_path: Path | str | None = None,
    ) -> bool:
        """Translate dialogue and choices, keeping commands, authors and line endings."""
        path = Path(file_path)
        out_path = Path(output_path) if output_path else path
        source = pristine_source(path)
        try:
            with open(source, "rb") as raw_f:
                encoding = "utf-8-sig" if raw_f.read(3) == b"\xef\xbb\xbf" else "utf-8"
            with open(source, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
                lines = f.read().splitlines(keepends=True)
            return safe_write(
                out_path,
                "".join(translate_line(line, translations) for line in lines),
                encoding=encoding,
            )
        except OSError as exc:
            logger.error("Failed to apply translations to Naninovel script %s: %s", path, exc)
            return False
