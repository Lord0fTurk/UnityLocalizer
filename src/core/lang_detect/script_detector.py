# -*- coding: utf-8 -*-
"""Unicode-script language detection for scripts that identify (nearly) one language.

Kana means Japanese, Hangul means Korean and Han ideographs mean Chinese unless kana
shows up elsewhere in the game. A statistical model needs whitespace-separated words
to work well, so these scripts are decided here, by counting lines.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from src.core.lang_detect.sampling import letter_count

MIN_SCRIPT_LINES = 8
MIN_SCRIPT_SHARE = 0.30
MIN_LINE_LETTERS = 2
_LINE_SCRIPT_SHARE = 0.30
_JAPANESE_SHARE_OF_CJK = 0.10

CHINESE = "zh-CN"
JAPANESE = "ja"

_RANGES: tuple[tuple[str, int, int], ...] = (
    ("kana", 0x3040, 0x30FF), ("kana", 0x31F0, 0x31FF),
    ("hangul", 0xAC00, 0xD7AF), ("hangul", 0x1100, 0x11FF), ("hangul", 0x3130, 0x318F),
    ("han", 0x4E00, 0x9FFF), ("han", 0x3400, 0x4DBF),
    ("thai", 0x0E00, 0x0E7F), ("hebrew", 0x0590, 0x05FF), ("greek", 0x0370, 0x03FF),
)
_SCRIPT_LANGUAGE: dict[str, str] = {
    "hangul": "ko", "han": CHINESE, "thai": "th", "hebrew": "he", "greek": "el",
}


def script_of(char: str) -> str | None:
    """Decisive script name of a character, or None for Latin, Cyrillic, Arabic, etc."""
    code = ord(char)
    return next((name for name, low, high in _RANGES if low <= code <= high), None)


def classify_line(line: str) -> str | None:
    """Language code when one decisive script dominates the line's letters."""
    letters = letter_count(line)
    if letters < MIN_LINE_LETTERS:
        return None
    counts = Counter(s for s in map(script_of, line) if s)
    if counts["kana"] and (counts["kana"] + counts["han"]) / letters >= _LINE_SCRIPT_SHARE:
        return JAPANESE
    for script, language in _SCRIPT_LANGUAGE.items():
        if counts[script] / letters >= _LINE_SCRIPT_SHARE:
            return language
    return None


def _merge_japanese(tally: Counter[str]) -> None:
    """Kanji-only lines are ambiguous; when kana lines exist they belong to Japanese."""
    cjk = tally[JAPANESE] + tally[CHINESE]
    if tally[JAPANESE] and tally[JAPANESE] >= _JAPANESE_SHARE_OF_CJK * cjk:
        tally[JAPANESE] += tally.pop(CHINESE, 0)


def detect_by_script(lines: Sequence[str]) -> tuple[str, float] | None:
    """(language, share of lines) when a decisive script covers enough of the game."""
    considered = [line for line in lines if letter_count(line) >= MIN_LINE_LETTERS]
    if not considered:
        return None
    tally = Counter(lang for lang in map(classify_line, considered) if lang)
    _merge_japanese(tally)
    if not tally:
        return None
    language, count = tally.most_common(1)[0]
    share = count / len(considered)
    if count < MIN_SCRIPT_LINES or share < MIN_SCRIPT_SHARE:
        return None
    return language, share
