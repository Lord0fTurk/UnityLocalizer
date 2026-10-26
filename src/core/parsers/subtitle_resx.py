# -*- coding: utf-8 -*-
"""Extractors and patchers for SubRip subtitles (``.srt``) and .NET resource files (``.resx``)."""

from __future__ import annotations

import re
from xml.sax.saxutils import escape, unescape

_SRT_TIME_RE = re.compile(r"^\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}\s*-->\s*\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}")
_SRT_BLOCK_SPLIT_RE = re.compile(r"(?:\r?\n){2,}")
# <data name="x"><value>text</value></data>; entries with a type or mimetype hold binary/serialized data.
_RESX_DATA_RE = re.compile(r"(<data\b(?P<attrs>[^>]*)>\s*<value>)(?P<value>.*?)(</value>)", re.DOTALL)


def _srt_cue_text(block: str) -> list[str] | None:
    """Text lines of one subtitle block, or None when the block has no timing line."""
    lines = block.strip("\r\n").splitlines()
    for position, line in enumerate(lines[:3]):
        if _SRT_TIME_RE.match(line.strip()):
            return lines[position + 1 :]
    return None


def srt_strings(text: str) -> list[str]:
    """Return the text of every subtitle cue (multi-line cues stay one string)."""
    found: list[str] = []
    for block in _SRT_BLOCK_SPLIT_RE.split(text.lstrip("﻿")):
        lines = _srt_cue_text(block)
        cue = "\n".join(line.rstrip() for line in lines).strip() if lines else ""
        if cue:
            found.append(cue)
    return found


def translate_srt(text: str, translations: dict[str, str]) -> str:
    """Replace cue texts that have a translation; timing lines and numbering are untouched."""
    newline = "\r\n" if "\r\n" in text else "\n"
    out: list[str] = []
    for block in _SRT_BLOCK_SPLIT_RE.split(text):
        lines = _srt_cue_text(block)
        if lines is None:
            out.append(block)
            continue
        cue = "\n".join(line.rstrip() for line in lines).strip()
        translated = translations.get(cue)
        if not translated:
            out.append(block)
            continue
        all_lines = block.strip("\r\n").splitlines()
        head = all_lines[: len(all_lines) - len(lines)]
        out.append(newline.join([*head, *translated.splitlines()]))
    result = (newline * 2).join(out)
    return result + newline if text.endswith(("\n", "\r")) and not result.endswith(newline) else result


def _is_text_entry(attrs: str) -> bool:
    return "type=" not in attrs and "mimetype=" not in attrs and "name=\"$" not in attrs and "name=\">>" not in attrs


def resx_strings(text: str) -> list[str]:
    """Return the string values of a .resx file (binary and serialized entries are skipped)."""
    found: list[str] = []
    for match in _RESX_DATA_RE.finditer(text):
        value = unescape(match.group("value")).strip()
        if _is_text_entry(match.group("attrs")) and len(value) > 1:
            found.append(value)
    return found


def translate_resx(text: str, translations: dict[str, str]) -> str:
    """Replace translated string values in a .resx file, keeping everything else byte for byte."""

    def _swap(match: re.Match[str]) -> str:
        value = unescape(match.group("value")).strip()
        if not _is_text_entry(match.group("attrs")) or value not in translations:
            return match.group(0)
        return f"{match.group(1)}{escape(translations[value])}{match.group(4)}"

    return _RESX_DATA_RE.sub(_swap, text)
