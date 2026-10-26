# -*- coding: utf-8 -*-
"""Drops harvested strings written in another script than the game's source language.

Games often ship every language side by side (language menus, all locales of a table
read by raw scanning). Once the source language is known, a Cyrillic or Han line in an
English game is a different language's text: translating it wastes the engine's quota
and the dictionary entry never matches what the player sees.

Only scripts that identify a language family are judged. Latin text is always kept
(Latin-script languages cannot be told apart by script, and English UI words are common
in every game), and scripts without a rule here are never dropped.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

from src.core.lang_detect.sampling import clean_text
from src.core.parsers.loc_table import base_language

_RANGES: tuple[tuple[str, int, int], ...] = (
    ("kana", 0x3040, 0x30FF), ("kana", 0x31F0, 0x31FF),
    ("hangul", 0xAC00, 0xD7AF), ("hangul", 0x1100, 0x11FF), ("hangul", 0x3130, 0x318F),
    ("han", 0x4E00, 0x9FFF), ("han", 0x3400, 0x4DBF),
    ("thai", 0x0E00, 0x0E7F), ("hebrew", 0x0590, 0x05FF), ("greek", 0x0370, 0x03FF),
    ("cyrillic", 0x0400, 0x052F),
    ("arabic", 0x0600, 0x06FF), ("arabic", 0x0750, 0x077F), ("arabic", 0xFB50, 0xFDFF), ("arabic", 0xFE70, 0xFEFF),
    ("devanagari", 0x0900, 0x097F),
)
# Scripts a language may be written in, besides Latin. Languages not listed are Latin-script.
_SOURCE_SCRIPTS: dict[str, frozenset[str]] = {
    "ja": frozenset({"han", "kana"}), "zh": frozenset({"han"}), "ko": frozenset({"hangul", "han"}),
    "th": frozenset({"thai"}), "he": frozenset({"hebrew"}), "el": frozenset({"greek"}),
    **dict.fromkeys(("ru", "uk", "be", "bg", "sr", "mk", "kk", "ky", "tg", "mn", "tt"), frozenset({"cyrillic"})),
    **dict.fromkeys(("ar", "fa", "ur", "ps", "sd", "ug"), frozenset({"arabic"})),
    **dict.fromkeys(("hi", "mr", "ne", "sa"), frozenset({"devanagari"})),
}
_DOMINANT_SHARE = 0.5
# Below this share of kept strings the chosen source language is probably wrong, not the game.
MIN_KEPT_SHARE = 0.30


def _script_of(char: str) -> str | None:
    code = ord(char)
    return next((name for name, low, high in _RANGES if low <= code <= high), None)


def dominant_script(text: str) -> str | None:
    """The recognised non-Latin script that makes up most of the text's letters, if any.

    Han mixed with kana counts as kana (Japanese): Chinese never contains kana.
    """
    letters = [c for c in clean_text(text) if c.isalpha()]
    if not letters:
        return None
    counts = Counter(s for s in map(_script_of, letters) if s)
    if counts["kana"] and (counts["kana"] + counts["han"]) / len(letters) >= _DOMINANT_SHARE:
        return "kana"
    script, count = counts.most_common(1)[0] if counts else (None, 0)
    return script if script and count / len(letters) >= _DOMINANT_SHARE else None


def is_foreign_script(text: str, source_lang: str) -> bool:
    """True when the text is dominated by a script the source language does not use."""
    script = dominant_script(text)
    return script is not None and script not in _SOURCE_SCRIPTS.get(base_language(source_lang), frozenset())


@dataclass
class ScriptFilterResult:
    """Strings kept for translation and how many other-script strings were left out."""

    kept: list[str] = field(default_factory=list)
    removed: int = 0

    @property
    def mismatch(self) -> bool:
        """True when most text is in another script: the source language setting looks wrong."""
        total = len(self.kept) + self.removed
        return bool(total) and len(self.kept) / total < MIN_KEPT_SHARE


def filter_foreign_script(strings: Iterable[str], source_lang: str) -> ScriptFilterResult:
    """Split strings into those matching the source language's script and the rest."""
    result = ScriptFilterResult()
    for text in strings:
        if is_foreign_script(text, source_lang):
            result.removed += 1
        else:
            result.kept.append(text)
    return result
