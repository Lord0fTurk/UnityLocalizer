# -*- coding: utf-8 -*-
"""Case- and diacritic-insensitive text folding for searching."""

from __future__ import annotations

import unicodedata


def fold(text: str) -> str:
    """Lower-case text without diacritics; Turkish dotted and dotless i both fold to ``i``.

    ``"İstanbul"``, ``"Istanbul"`` and ``"istanbul"`` fold to the same string, and so do
    ``"ışık"`` and ``"isik"``, so searching works without a Turkish keyboard.
    """
    text = (text or "").replace("İ", "i").replace("I", "i").casefold()
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return text.replace("ı", "i")
