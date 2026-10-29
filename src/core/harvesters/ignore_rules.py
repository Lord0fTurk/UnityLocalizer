# -*- coding: utf-8 -*-
"""Strings that must never reach a translation engine, by built-in and user rules.

Every harvested string that survives goes to a (possibly paid) engine, so texts that are
engine boilerplate or that the user knows to be noise are dropped before translation.

Rule syntax, one per line (blank lines and lines starting with ``#`` are skipped):

* ``New Text``       exact text, case-insensitive, ignoring surrounding markup and spacing
* ``Debug:*``        a trailing ``*`` makes it a prefix rule
* ``re:^\\d+ FPS$``  a regular expression searched in the text (case-insensitive)
"""

from __future__ import annotations

import logging
import re
import warnings
from collections.abc import Iterable
from dataclasses import dataclass

from src.core.syntax_guard import UNITY_PROTECT_RE

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)  # Python 3.10 only has the old module name
    try:
        from re import _constants as _sre_constants, _parser as _sre_parser
    except ImportError:  # Python 3.10
        import sre_constants as _sre_constants
        import sre_parse as _sre_parser

logger = logging.getLogger(__name__)

# Text Unity's UI creation menus put into new objects (uGUI and TextMeshPro) that is easy to
# leave behind in a scene. Compared case-insensitively against the whole string.
ENGINE_PLACEHOLDERS: frozenset[str] = frozenset({
    "new text", "sample text", "enter text...", "enter text…",
    "button", "label", "option a", "option b", "option c",
})

REGEX_PREFIX = "re:"
COMMENT_PREFIX = "#"
_WHITESPACE_RE = re.compile(r"\s+")
# A regular expression is searched in at most this much of a string, which bounds a slow rule.
MAX_REGEX_INPUT = 1000
_REPEATS = (_sre_constants.MAX_REPEAT, _sre_constants.MIN_REPEAT)


def _normalize(text: str) -> str:
    """Lower-cased text with runs of whitespace collapsed."""
    return _WHITESPACE_RE.sub(" ", text).strip().casefold()


@dataclass(frozen=True)
class IgnoreRules:
    """Compiled ignore rules: exact texts, prefixes and regular expressions."""

    exact: frozenset[str] = frozenset()
    prefixes: tuple[str, ...] = ()
    patterns: tuple[re.Pattern[str], ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (self.exact or self.prefixes or self.patterns)

    def matches(self, text: str) -> bool:
        """True when the string is ignored by any rule."""
        stripped = text.strip()
        if not stripped:
            return False
        # "<b>New Text</b>" is the same boilerplate as "New Text".
        plain = UNITY_PROTECT_RE.sub(" ", stripped)
        for candidate in (_normalize(stripped), _normalize(plain)):
            if candidate in self.exact or (candidate and candidate.startswith(self.prefixes)):
                return True
        return any(pattern.search(stripped[:MAX_REGEX_INPUT]) for pattern in self.patterns)


EMPTY_RULES = IgnoreRules()


@dataclass(frozen=True)
class IgnoreResult:
    """Strings that stay and how many were left out."""

    kept: list[str]
    removed: int


def _sub_patterns(op: object, arg: object) -> list[object]:
    """Nested sub-patterns of one parsed regex item."""
    if op == _sre_constants.BRANCH:
        return list(arg[1])
    if op in _REPEATS:
        return [arg[2]]
    if op == _sre_constants.SUBPATTERN:
        return [arg[-1]]
    if op in (_sre_constants.ASSERT, _sre_constants.ASSERT_NOT):
        return [arg[1]]
    return []


def _has_nested_repeat(parsed: object, inside_repeat: bool = False) -> bool:
    """True for an unbounded repeat inside another one, e.g. ``(a+)+``: exponential backtracking."""
    for op, arg in parsed:
        unbounded = op in _REPEATS and arg[1] == _sre_constants.MAXREPEAT
        if unbounded and inside_repeat:
            return True
        if any(_has_nested_repeat(sub, inside_repeat or unbounded) for sub in _sub_patterns(op, arg)):
            return True
    return False


def _compile_pattern(source: str) -> re.Pattern[str] | None:
    """Compile a user regex; None (logged) when invalid, empty, matching everything or prone to backtracking."""
    label = REGEX_PREFIX + source
    try:
        pattern = re.compile(source, re.IGNORECASE)
        nested = _has_nested_repeat(_sre_parser.parse(source, re.IGNORECASE))
    except re.error as exc:
        logger.warning("Ignored an invalid ignore rule %r: %s", label, exc)
        return None
    if pattern.search(""):
        logger.warning("Ignored the ignore rule %r: it matches an empty text, so it would match every string", label)
        return None
    if nested:
        logger.warning("Ignored the ignore rule %r: a repeat inside a repeat can hang the scan", label)
        return None
    return pattern


def parse_rules(text: str, *, engine_placeholders: bool = True) -> IgnoreRules:
    """Compile the user's rule lines, plus the built-in Unity placeholders when requested.

    An invalid regular expression or an empty prefix is logged and skipped, so one typo
    never disables the other rules.
    """
    exact: set[str] = set(ENGINE_PLACEHOLDERS) if engine_placeholders else set()
    prefixes: list[str] = []
    patterns: list[re.Pattern[str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(COMMENT_PREFIX):
            continue
        if line.startswith(REGEX_PREFIX):
            pattern = _compile_pattern(line[len(REGEX_PREFIX):])
            if pattern:
                patterns.append(pattern)
        elif line.endswith("*"):
            prefix = _normalize(line[:-1])
            if prefix:
                prefixes.append(prefix)
            else:
                logger.warning("Ignored an ignore rule without text before '*': %r", line)
        else:
            exact.add(_normalize(line))
    return IgnoreRules(frozenset(exact), tuple(prefixes), tuple(patterns))


def filter_ignored(strings: Iterable[str], rules: IgnoreRules) -> IgnoreResult:
    """Split strings into those that stay and a count of those the rules removed."""
    items = list(strings)
    if rules.is_empty:
        return IgnoreResult(items, 0)
    kept = [text for text in items if not rules.matches(text)]
    return IgnoreResult(kept, len(items) - len(kept))
