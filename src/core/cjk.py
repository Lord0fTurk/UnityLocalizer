# -*- coding: utf-8 -*-
"""Tiny CJK helpers shared by harvesters and parsers (kept dependency-free)."""

from __future__ import annotations

import re

_CJK_CHAR_RE = re.compile("[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]")


def is_single_cjk(text: str) -> bool:
    """True for one Han/kana/Hangul character, which is a complete word in CJK UI labels."""
    stripped = text.strip()
    return len(stripped) == 1 and bool(_CJK_CHAR_RE.match(stripped))
