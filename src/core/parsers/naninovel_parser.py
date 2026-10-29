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
from src.core.parsers.text_encoding import UnencodableTextError, decode_file
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

    def __init__(self, source_lang: str = "") -> None:
        # Tells Shift-JIS, GBK and Korean scripts apart when the encoding has to be detected.
        self.source_lang = source_lang

    def extract_strings(self, file_path: Path | str) -> list[str]:
        """Extract dialogue text and choice labels (from the original backup once patched)."""
        path = Path(file_path)
        if not path.is_file():
            return []
        decoded = decode_file(pristine_source(path), self.source_lang)
        if decoded is None:
            return []
        return [s for line in decoded.text.splitlines() for s in line_strings(line)]

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
        decoded = decode_file(source, self.source_lang)
        if decoded is None:
            return False
        lines = decoded.text.splitlines(keepends=True)
        try:
            data = decoded.encoding.encode("".join(translate_line(line, translations) for line in lines))
        except UnencodableTextError as exc:
            logger.warning("Left %s unpatched: %s", path.name, exc)
            return False
        try:
            return safe_write(out_path, data)
        except OSError as exc:
            logger.error("Failed to apply translations to Naninovel script %s: %s", path, exc)
            return False
