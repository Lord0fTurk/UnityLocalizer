# -*- coding: utf-8 -*-
"""Script data lines kept as text, and the readable words hidden inside them.

Some games store their dialogue and sequencer scripts as lines of ``key="a|b|c",`` or ``key=58,`` in
text fields (Situation Succ Inn Elysium: 18,232 of 30,893 harvested strings, such as
``task="0|0|false|false|ActionManager|UpdateEvidence|true"`` or ``line="21|1_scene_intro/21|null"``).
They are data, not display text: an engine "translates" them into ``görev = "..."`` and the game
cannot parse them any more, and the harvest spends most of its budget on them. The words the player
actually sees are in a few of them, usually as one segment of a ``|`` or ``*`` separated value
(``choice="Ask about cameras|DialogueSystem|StartConversation|3_Lily_CCTV|..."``); XUnity can only
translate those words once they stand alone, because the game shows them on their own.

``split_data_lines`` therefore replaces every such line by the readable segments it holds.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# key="value", / key=58, / key=true / key={...}: one assignment, nothing else on the line.
_DATA_LINE_RE = re.compile(
    r'^\s*(?P<key>[A-Za-z_][\w.]*)\s*=\s*(?:"(?P<quoted>[^"]*)"|(?P<bare>-?\d[\w.\-*|]*|true|false|null|nil))\s*,?\s*$',
    re.IGNORECASE,
)
# The first line of a multi-line value: the quote is opened here and closed on a later line.
_OPEN_VALUE_RE = re.compile(r'^\s*(?P<key>[A-Za-z_][\w.]*)\s*=\s*"(?P<body>[^"]*)$')
_SEPARATORS_RE = re.compile(r"[|*]")
# Keys whose value is display text; the leading segment is taken even when it is a single word ("Leave").
TEXT_KEYS = frozenset({
    "choice", "displayname", "display_name", "description", "descriptiontext", "text", "title", "label",
    "tooltip", "dialoguetext", "menutext", "subtitle", "caption", "message",
})
# Keys that only ever hold ids, scripts, conditions and paths: nothing in them is shown to the player.
DATA_KEYS = frozenset({
    "task", "line", "name", "id", "itemid", "conversation", "linkedsequence", "linkeddialogue", "condition",
    "scheduletask", "audiofilepath", "sequence", "file", "path", "tag", "script", "event", "trigger", "target",
})
_FLAGS = frozenset({"true", "false", "null", "nil", "none", "dialoguesystem", "startconversation"})
_WORD_RE = re.compile(r"[^\W\d_]{2,}")
_IDENTIFIER_RE = re.compile(r"^[\w./\\:\-]+$")
_FILE_LIKE_RE = re.compile(r"(?:[/\\]|\.\w{2,4}$)")


@dataclass
class DataLineSplit:
    """Strings after the data lines were replaced by their readable segments."""

    strings: list[str]
    lines_removed: int = 0
    segments_added: int = 0
    origin: dict[str, str] = field(default_factory=dict)  # extracted segment -> the line it came from


def _is_readable(segment: str, lenient: bool) -> bool:
    """True for a segment that is words rather than an identifier, a path or a flag."""
    text = segment.strip()
    if len(text) < 2 or text.lower() in _FLAGS or "_" in text or _FILE_LIKE_RE.search(text):
        return False
    if lenient:
        return bool(_WORD_RE.search(text))
    return bool(" " in text and len(_WORD_RE.findall(text)) >= 2) and not _IDENTIFIER_RE.match(text)


def _is_text_start(key: str, body: str) -> bool:
    """True when the text after ``key="`` is words (a description, a title) rather than an identifier."""
    if key.lower() in TEXT_KEYS:
        return bool(_WORD_RE.search(body))
    return _is_readable(body, lenient=False)


def readable_segments(key: str, value: str) -> list[str]:
    """The display-text segments of one data value (empty for pure data)."""
    if key.lower() in DATA_KEYS:
        return []
    lenient_key = key.lower() in TEXT_KEYS
    found: list[str] = []
    for index, raw in enumerate(_SEPARATORS_RE.split(value)):
        # In a text key only the first segment is the text; the rest are conversation ids, flags and the like.
        if _is_readable(raw, lenient=lenient_key and index == 0):
            found.append(raw.strip())
    return found


def split_data_lines(strings: Iterable[str]) -> DataLineSplit:
    """Replace script data lines by the readable words inside them; other strings pass through unchanged."""
    kept: dict[str, None] = {}
    result = DataLineSplit([])
    extracted: list[tuple[str, str]] = []
    for text in strings:
        match = _DATA_LINE_RE.match(text)
        if match is not None:
            result.lines_removed += 1
            extracted.extend((segment, text) for segment in readable_segments(match["key"], match["quoted"] or ""))
            continue
        opened = _OPEN_VALUE_RE.match(text)
        if opened is None:
            kept[text] = None
            continue
        result.lines_removed += 1
        body = opened["body"].strip()
        if body and opened["key"].lower() not in DATA_KEYS and _is_text_start(opened["key"], body):
            extracted.append((body, text))
    for segment, line in extracted:
        if segment not in kept:
            kept[segment] = None
            result.segments_added += 1
            result.origin[segment] = line
    result.strings = list(kept)
    if result.lines_removed:
        logger.info("Data lines: %d left out, %d readable segments kept", result.lines_removed, result.segments_added)
    return result
