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
MAX_REGEX_ENTRIES = 1500

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


# Regex matching common option/choice prefixes:
# 1) Numbers: "1. ", "2) ", "(3) ", "[4] "
# 2) Bullets/Arrows: "- ", "-- ", "> ", "* ", "• ", "-> "
# 3) Roleplay / Skill checks: "[Charm] ", "[Strength 14] ", "[Lie] ", "[Success] "
# 4) Lettered choices: "A. ", "B) ", "a) "
_CHOICE_PREFIX_RE = (
    r"^((?:(?:\d+[\.\)]|[\(\[]\d+[\)\]]|[A-Za-z][\.\)]|\[[A-Za-z0-9_\s\+\-]+\]|[-–—*•>]|->|=>)\s*)+)"
)


def is_choice_candidate(source: str) -> bool:
    """True when source is a multi-word phrase that may appear in-game with option prefixes."""
    stripped = source.strip()
    if len(stripped) < 4 or len(stripped) > 120 or "\n" in stripped or "\r" in stripped:
        return False
    if has_runtime_placeholders(stripped) or not _has_literal_anchor(stripped):
        return False
    words = stripped.split()
    return 2 <= len(words) <= 20 and any(c.isalpha() for c in stripped)


def build_choice_prefix_entry(source: str, translation: str) -> tuple[str, str] | None:
    """Generate a regex entry preserving dynamic choice numbering and skill tags ($1Translation)."""
    if not is_choice_candidate(source):
        return None
    escaped_source = _escape_net(source.strip())
    pattern = f"{_CHOICE_PREFIX_RE}{escaped_source}$"
    escaped_trans = translation.replace("$", "$$")
    replacement = f"${{1}}{escaped_trans}"
    return f'r:"{pattern}"', f'"{replacement}"'


def build_regex_entries(translations: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """Regex entries for runtime placeholders and dynamic choices, capped at MAX_REGEX_ENTRIES."""
    ph_entries: list[tuple[str, str]] = []
    ch_entries: list[tuple[str, str]] = []

    for src, dst in translations:
        if ph_entry := build_regex_entry(src, dst):
            ph_entries.append(ph_entry)
        elif ch_entry := build_choice_prefix_entry(src, dst):
            ch_entries.append(ch_entry)

    # Placeholder entries have priority because runtime templates never match without regex.
    combined = ph_entries + ch_entries
    if len(combined) > MAX_REGEX_ENTRIES:
        logger.info(
            "%d runtime regex candidates found (%d placeholders, %d choices); capping to %d",
            len(combined), len(ph_entries), len(ch_entries), MAX_REGEX_ENTRIES,
        )
    return combined[:MAX_REGEX_ENTRIES]
