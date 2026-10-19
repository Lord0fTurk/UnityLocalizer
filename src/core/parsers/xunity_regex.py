# -*- coding: utf-8 -*-
"""XUnity regex entries for strings whose placeholders are filled in at runtime.

A code literal such as ``"Gold: {0}"`` reaches the screen as ``"Gold: 150"``, so a
plain dictionary entry keyed by the template never matches. XUnity supports
regex entries for exactly this case (``r:"^Gold: (.*?)$"="Altın: $1"``), applied
when no direct lookup matches. They only work in files whose name does not start
with ``_`` (see ``hook_layout.DICTIONARY_FILE``).

Patterns are .NET regexes: placeholders become capture groups (a repeated
placeholder becomes a backreference), literal text is escaped, ``{{``/``}}``
become literal braces, and the replacement uses ``$N`` with literal ``$``
doubled. Both sides are wrapped in quotes because XUnity takes the text between
the first and last quote, which keeps quotes inside a translation intact.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

logger = logging.getLogger(__name__)

# Upper bound of regex entries per dictionary: XUnity compiles every regex at startup
# and tries them on each text without a direct match, so thousands would cost load time.
MAX_REGEX_ENTRIES = 1000

# Runtime-filled placeholders (string.Format items, named Smart String / I2 / Ink
# parameters, printf) plus the escaped braces string.Format turns into single ones.
_TOKEN_RE = re.compile(
    r"\{\{|\}\}"
    r"|\{\d+(?:\s*,\s*-?\d+)?(?::[^{}]*)?\}"
    r"|\{(?:\$?[A-Za-z_][\w.\[\]]*|\[[\w.]+\])(?::[^{}]*)?\}"
    r"|%-?\d*(?:\.\d+)?[sdifxX]"
)
_STRIP_MARKUP_RE = re.compile(r"<[^>]+>")
_NET_SPECIAL = frozenset("\\*+?|{}[]()^$.#")


def _is_placeholder(token: str) -> bool:
    return token not in ("{{", "}}")


def _has_literal_anchor(source: str) -> bool:
    """True when source has at least 2 literal alphanumeric chars outside placeholders and tags."""
    without_tokens = _TOKEN_RE.sub("", source)
    without_tags = _STRIP_MARKUP_RE.sub("", without_tokens)
    return sum(1 for ch in without_tags if ch.isalnum()) >= 2


def _tokens(text: str) -> list[tuple[re.Match[str], str]]:
    """Matches with an identity: ``{0}``/``{name}`` repeat the same value, while each
    printf ``%s`` is a new argument, so printf tokens are numbered per occurrence."""
    seen: dict[str, int] = {}
    found: list[tuple[re.Match[str], str]] = []
    for match in _TOKEN_RE.finditer(text):
        token = match.group(0)
        if token.startswith("%"):
            seen[token] = seen.get(token, 0) + 1
            token = f"{token}#{seen[token]}"
        found.append((match, token))
    return found


def has_runtime_placeholders(text: str) -> bool:
    """True when text contains at least one placeholder filled in at runtime."""
    return any(_is_placeholder(m.group(0)) for m in _TOKEN_RE.finditer(text))


def _escape_net(text: str) -> str:
    """Escape .NET regex metacharacters in literal text."""
    return "".join("\\" + char if char in _NET_SPECIAL else char for char in text)


def _source_pattern(source: str) -> tuple[str, dict[str, int]]:
    """Anchored .NET pattern for source and the group number of each placeholder."""
    groups: dict[str, int] = {}
    parts: list[str] = ["^"]
    position = 0
    tokens = _tokens(source)
    for idx, (match, token) in enumerate(tokens):
        parts.append(_escape_net(source[position:match.start()]))
        if not _is_placeholder(token):
            parts.append("\\" + token[0])
        elif token in groups:
            next_pos = match.end()
            next_char = source[next_pos : next_pos + 1]
            # If the next literal character is a digit, \1 followed by 0 would be read as \10.
            if next_char.isdigit():
                parts.append(f"(?:\\{groups[token]})")
            else:
                parts.append(f"\\{groups[token]}")
        else:
            groups[token] = len(groups) + 1
            parts.append("(.*?)")
        position = match.end()
    parts.append(_escape_net(source[position:]))
    parts.append("$")
    return "".join(parts), groups


def _replacement(translation: str, groups: dict[str, int]) -> str | None:
    """.NET replacement for translation; None when it uses a placeholder the source lacks."""
    parts: list[str] = []
    position = 0
    for match, token in _tokens(translation):
        parts.append(translation[position:match.start()].replace("$", "$$"))
        if not _is_placeholder(token):
            parts.append(token[0])
        elif token in groups:
            parts.append(f"${{{groups[token]}}}")
        else:
            return None
        position = match.end()
    parts.append(translation[position:].replace("$", "$$"))
    return "".join(parts)


def build_regex_entry(source: str, translation: str) -> tuple[str, str] | None:
    """(key, value) of an XUnity regex entry, or None when source has no placeholder or anchor."""
    if not has_runtime_placeholders(source) or not _has_literal_anchor(source):
        return None
    pattern, groups = _source_pattern(source)
    replacement = _replacement(translation, groups)
    if replacement is None:
        return None
    return f'r:"{pattern}"', f'"{replacement}"'


def build_regex_entries(translations: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """Regex entries for every placeholder string, capped at ``MAX_REGEX_ENTRIES``."""
    entries = [entry for src, dst in translations if (entry := build_regex_entry(src, dst))]
    if len(entries) > MAX_REGEX_ENTRIES:
        logger.warning(
            "%d runtime-format strings found; only the first %d get regex entries",
            len(entries), MAX_REGEX_ENTRIES,
        )
    return entries[:MAX_REGEX_ENTRIES]
