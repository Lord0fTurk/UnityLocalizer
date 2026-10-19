# -*- coding: utf-8 -*-
"""Yarn Spinner script line splitter.

A Yarn dialogue line such as ``-> Sally: Hello there! <<if $met>> #line:a1b2c3``
carries an option arrow, a speaker, display text, inline commands and line tags.
Only the speaker and the display text are translatable; ``#line:`` IDs must stay
byte-identical or Yarn can no longer resolve the line. Node headers (``title:``,
``position:``) live before ``---`` and are never translated.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

_HEADER_END = "---"
_NODE_END = "==="

_YARN_LINE_RE = re.compile(
    r"^(?P<lead>\s*(?:->\s*)?)"
    r"(?P<speaker_full>(?P<speaker>[A-Za-z_À-ÖØ-öø-ÿ\u0100-\uFFFF][\w.\-]{0,29}(?: [A-ZÀ-ÖØ-Þ\u0100-\uFFFF][\w.\-]{0,19})?):\s+)?"
    r"(?P<body>.*?)"
    r"(?P<tail>(?:\s*(?:<<[^<>]*>>|#[^\s#]+))*\s*)$"
)


@dataclass(frozen=True)
class YarnLine:
    """Structural parts of one Yarn dialogue line."""

    lead: str
    speaker_full: str
    speaker: str
    body: str
    tail: str

    def render(self, translate: Callable[[str], str]) -> str:
        """Rebuild the line, passing speaker and body through translate."""
        speaker_full = self.speaker_full
        if self.speaker:
            speaker_full = speaker_full.replace(self.speaker, translate(self.speaker), 1)
        return f"{self.lead}{speaker_full}{translate(self.body)}{self.tail}"


def looks_like_yarn(text: str) -> bool:
    """True when text has Yarn node structure (title header, '---' and '===' markers)."""
    lines = {line.lstrip("\ufeff").strip() for line in text.splitlines()}
    return _HEADER_END in lines and _NODE_END in lines and any(ln.startswith("title:") for ln in lines)


def split_yarn_line(line: str) -> YarnLine | None:
    """Split a dialogue body line; None for commands, comments and blank lines."""
    stripped = line.lstrip("\ufeff").strip()
    if not stripped or stripped.startswith(("<<", "//")):
        return None
    match = _YARN_LINE_RE.match(line.rstrip("\r\n"))
    if not match or not match.group("body").strip():
        return None
    return YarnLine(
        lead=match.group("lead"),
        speaker_full=match.group("speaker_full") or "",
        speaker=(match.group("speaker") or "").strip(),
        body=match.group("body"),
        tail=match.group("tail"),
    )


def _body_lines(text: str) -> Iterator[tuple[str, bool]]:
    """Yield (line, is_body) honoring node header/body sections."""
    lines = text.splitlines(keepends=True)
    in_body = not any(line.strip() == _HEADER_END for line in lines)
    for line in lines:
        marker = line.strip()
        if marker == _HEADER_END:
            in_body = True
            yield line, False
        elif marker == _NODE_END:
            in_body = False
            yield line, False
        else:
            yield line, in_body


def yarn_strings(text: str) -> list[str]:
    """Collect speaker names and display text from a Yarn script."""
    found: list[str] = []
    for line, is_body in _body_lines(text):
        parsed = split_yarn_line(line) if is_body else None
        if parsed is None:
            continue
        if parsed.speaker:
            found.append(parsed.speaker)
        if len(parsed.body.strip()) > 1:
            found.append(parsed.body.strip())
    return found


def translate_yarn_text(text: str, translations: dict[str, str]) -> str:
    """Return the script with speakers and display text replaced, structure untouched."""

    def _translate(segment: str) -> str:
        core = segment.strip()
        if core not in translations:
            return segment
        start = segment.index(core)
        return f"{segment[:start]}{translations[core]}{segment[start + len(core):]}"

    out: list[str] = []
    for line, is_body in _body_lines(text):
        parsed = split_yarn_line(line) if is_body else None
        if parsed is None:
            out.append(line)
            continue
        newline = line[len(line.rstrip("\r\n")):]
        out.append(parsed.render(_translate) + newline)
    return "".join(out)
