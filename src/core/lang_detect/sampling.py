# -*- coding: utf-8 -*-
"""Turns harvested game strings into clean, spread-out samples for language detection."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

# Unity RichText tags, C# format items, NGUI/TMP bracket codes, printf specifiers and escapes.
_MARKUP_RE = re.compile(r"<[^<>]{1,80}>|\{[^{}]*\}|\[[^\[\]]{0,40}\]|%\(?\w*\)?[sdfi]|\\[nrt]")
_WS_RE = re.compile(r"\s+")

MIN_PROSE_LETTERS = 12
MIN_PROSE_WORDS = 3
MAX_SAMPLE_CHARS = 300


def clean_text(text: str) -> str:
    """Strip markup and collapse whitespace so only readable text remains."""
    return _WS_RE.sub(" ", _MARKUP_RE.sub(" ", text or "")).strip()


def letter_count(text: str) -> int:
    """Number of alphabetic characters (CJK ideographs count as letters)."""
    return sum(1 for ch in text if ch.isalpha())


def clean_lines(strings: Iterable[str]) -> list[str]:
    """Cleaned, non-empty versions of the given strings (order preserved)."""
    return [cleaned for cleaned in (clean_text(s) for s in strings) if cleaned]


def prose_lines(lines: Iterable[str], is_cjk: bool = False) -> list[str]:
    """Sentence-like lines: enough letters and, outside CJK, at least a few words.

    Menu words, character names and identifiers carry no reliable language signal.
    """
    return [
        line for line in lines
        if letter_count(line) >= MIN_PROSE_LETTERS and (is_cjk or len(line.split()) >= MIN_PROSE_WORDS)
    ]


def spread(lines: Sequence[str], limit: int) -> list[str]:
    """Pick up to ``limit`` lines evenly across the whole pool, not just its first lines."""
    if limit <= 0 or not lines:
        return []
    step = max(1, len(lines) // limit)
    return [line[:MAX_SAMPLE_CHARS] for line in lines[::step][:limit]]
