# -*- coding: utf-8 -*-
"""Unity RichText and C# string formatting syntax protection layer."""

from __future__ import annotations

import logging
import re
import threading
from collections import Counter

logger = logging.getLogger(__name__)

# Unity uGUI / TextMeshPro RichText tag names (longest first so prefixes never shadow).
_RICHTEXT_TAGS = (
    "margin-left|margin-right|line-height|line-indent|font-weight|lowercase|uppercase|smallcaps|allcaps|"
    "material|gradient|voffset|noparse|mspace|indent|margin|rotate|sprite|"
    "cspace|style|align|alpha|color|space|width|nobr|link|mark|page|quad|font|"
    "size|pos|sup|sub|br|b|i|u|s"
)

# Body of a format item after ':': plain characters or one balanced {...} group.
_FORMAT_BODY = r"(?:[^{}]|\{[^{}]*\})*"

# Unity RichText tags & C# format placeholders pattern (order matters: first match wins)
_UNITY_TAG_PATTERNS = [
    # RichText tags with attributes (e.g. <color=#ff0000>, <size=20>, <sprite=0>, <br/>)
    rf"</?(?:{_RICHTEXT_TAGS})(?:=[^>]*|\s+[^>]*)?\s*/?>",
    # TextMeshPro shorthand color tag (e.g. <#ff0000>)
    r"<#[0-9a-fA-F]{3,8}>",
    # Escaped literal braces in string.Format ({{ and }})
    r"\{\{|\}\}",
    # Indexed C# format items with alignment/format (e.g. {0}, {0,-10}, {1:N2}, {2,5:0.00}); the
    # format part may hold one nested level so Smart String plurals ({0:plural:{} item|{} items}) stay whole
    rf"\{{\d+(?:\s*,\s*-?\d+)?(?::{_FORMAT_BODY})?\}}",
    # Named / dotted / Smart String / Ink-Yarn / I2 params (e.g. {playerName}, {player.name}, {$gold}, {[PARAM]})
    rf"\{{(?:\$?[A-Za-z_][\w.\[\]]*|\[[\w.]+\])(?::{_FORMAT_BODY})?\}}",
    # NGUI BBCode colors and styles (e.g. [ff0000], [-], [b], [/b], [url=x])
    r"\[(?:[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?|-|/?(?:b|i|u|s|c|sub|sup|url(?:=[^\]]*)?))\]",
    # Game directives in square brackets (e.g. [pic=39], [picc=12], [wait=0.5]): a name, '=' and a short
    # value without spaces. An engine would translate the name ("[resim=39]") and the game would not know it.
    r"\[[A-Za-z_][A-Za-z0-9_]*=[^\]\s]{1,64}\]",
    # Printf style format specifiers (e.g. %s, %5d, %.2f, positional %1$s)
    r"%(?:\d+\$)?-?\d*(?:\.\d+)?[sdifxX]",
    # Common escape sequences
    r"\\n|\\r|\\t",
]

UNITY_PROTECT_RE = re.compile("|".join(_UNITY_TAG_PATTERNS), re.IGNORECASE)
TOKEN_RE = re.compile(r"⟦ULPH_(\d+)⟧")
# Engines (CJK targets especially) swap ⟦ ⟧ for other brackets. Recovery is deliberately narrow:
# either a complete bracket pair around the token, or a bare ``ULPH_N``. A lone bracket is never
# consumed, so a legitimate quote such as 「…」 next to a mangled token is not eaten.
_FUZZY_OPEN = r"⟦\[\(\{［（｛【〔「『《«‹⟪<＜"
_FUZZY_CLOSE = r"⟧\]\)\}］）｝】〕」』》»›⟫>＞"
TOKEN_FUZZY_RE = re.compile(
    rf"[{_FUZZY_OPEN}]\s*ULPH[_＿\s-]*(\d+)\s*[{_FUZZY_CLOSE}]|(?<!\w)ULPH_(\d+)(?!\d)", re.IGNORECASE
)
LEAKED_TOKEN_RE = re.compile(r"ULPH_\d+|<ph\s+id=", re.IGNORECASE)

_state_lock = threading.RLock()
# User "do not translate" terms (character names, places, brands), set by the translation manager.
_protected_terms: frozenset[str] = frozenset()
# Tokens hidden from engines (markup, protected terms, glossary terms) ...
_active_protect_re: re.Pattern[str] = UNITY_PROTECT_RE
# ... and the subset the integrity gate enforces (glossary terms are rewritten afterwards).
_active_validate_re: re.Pattern[str] = UNITY_PROTECT_RE


def _clean_terms(terms: list[str] | tuple[str, ...] | set[str]) -> list[str]:
    """Unique non-blank terms, longest first so they win over their prefixes."""
    return sorted({t.strip() for t in terms if t and t.strip()}, key=len, reverse=True)


# Scripts written without spaces: a name there is adjacent to other letters by nature.
_UNSPACED_SCRIPTS = "぀-ヿ㐀-䶿一-鿿가-힯฀-๿"
_UNSPACED_RE = re.compile(f"[{_UNSPACED_SCRIPTS}]")


def _term_pattern(term: str) -> str:
    """Whole-word pattern; terms in unspaced scripts match anywhere, others stop at foreign letters.

    ``\\w`` also covers kana and Han, so "Alice" in "Aliceは" or "アルス" in "アルスは勇者だ"
    would never match a plain ``(?<!\\w)…(?!\\w)`` boundary.
    """
    escaped = re.escape(term)
    if _UNSPACED_RE.search(term):
        return escaped
    return rf"(?:(?<!\w)|(?<=[{_UNSPACED_SCRIPTS}])){escaped}(?:(?!\w)|(?=[{_UNSPACED_SCRIPTS}]))"


def _whole_words(terms: list[str]) -> str:
    return "|".join(_term_pattern(t) for t in terms)


def set_protected_terms(
    terms: list[str] | tuple[str, ...] | set[str],
    glossary_terms: list[str] | tuple[str, ...] | set[str] = (),
) -> None:
    """Treat the given terms like placeholders: never sent to engines, must survive translation.

    Protected terms match case-sensitively as whole words. ``glossary_terms`` match
    case-insensitively and are also kept away from engines, so the glossary can swap
    them for the user's translation afterwards; the integrity gate does not enforce
    them because that substitution removes them on purpose.
    """
    global _protected_terms, _active_protect_re, _active_validate_re
    cleaned = _clean_terms(terms)
    protected = frozenset(t.lower() for t in cleaned)
    glossary = [t for t in _clean_terms(glossary_terms) if t.lower() not in protected]
    validate = UNITY_PROTECT_RE.pattern + (f"|(?-i:{_whole_words(cleaned)})" if cleaned else "")
    protect = validate + (f"|{_whole_words(glossary)}" if glossary else "")
    val_re = re.compile(validate, re.IGNORECASE) if cleaned else UNITY_PROTECT_RE
    prot_re = re.compile(protect, re.IGNORECASE) if (cleaned or glossary) else UNITY_PROTECT_RE
    with _state_lock:
        _protected_terms = protected
        _active_validate_re = val_re
        _active_protect_re = prot_re


def protected_terms() -> frozenset[str]:
    """Currently protected terms (lowercased)."""
    with _state_lock:
        return _protected_terms
_COSMETIC_TOKENS = frozenset({"\\n", "\\r", "\\t"})

ISSUE_LEAKED = "leaked"
ISSUE_MISSING = "missing"
ISSUE_UNEXPECTED = "unexpected"
# English renderings for logs only; the UI localizes issue codes via i18n keys.
_ISSUE_LOG_TEMPLATES: dict[str, str] = {
    ISSUE_LEAKED: "Unrestored placeholder token leaked into translation",
    ISSUE_MISSING: "Missing tokens: {tokens}",
    ISSUE_UNEXPECTED: "Unexpected tokens: {tokens}",
}


# --- Tag pairing (shared by RTL shaping and placeholder repair) ---

_OPEN_TAG_RE = re.compile(r"^<(?:(#)[0-9a-f]{3,8}|([a-z-]+)(?:[=\s][^>]*)?)>$", re.IGNORECASE)
_CLOSE_TAG_RE = re.compile(r"^</([a-z-]+)\s*>$", re.IGNORECASE)
_NGUI_OPEN_RE = re.compile(r"^\[(?:[0-9a-f]{6}(?:[0-9a-f]{2})?|b|i|u|s|c|sub|sup|url=[^\]]*)\]$", re.IGNORECASE)
_NGUI_COLOR_RE = re.compile(r"[0-9a-f]{6}(?:[0-9a-f]{2})?")
_SELF_CLOSING_TAGS = frozenset({"br", "sprite", "quad", "space", "pos", "page"})


def _ngui_role(token: str) -> tuple[str, str] | None:
    """Classify NGUI BBCode tokens ([ff0000]/[-], [b]/[/b])."""
    if token == "[-]":
        return "close", "ngui-color"
    if token.startswith("[/"):
        return "close", "ngui-" + token[2:-1].split("=")[0]
    if _NGUI_OPEN_RE.match(token):
        name = token[1:-1].split("=")[0]
        return "open", "ngui-color" if _NGUI_COLOR_RE.fullmatch(name) else "ngui-" + name
    return None


def tag_role(token: str) -> tuple[str, str] | None:
    """Classify a token as ('open'|'close', tag_name); None for unpaired tokens."""
    lowered = token.lower()
    if lowered.startswith("["):
        return _ngui_role(lowered)
    close = _CLOSE_TAG_RE.match(lowered)
    if close:
        return "close", close.group(1)
    opening = _OPEN_TAG_RE.match(lowered)
    if not opening or lowered.endswith("/>"):
        return None
    name = "color" if opening.group(1) else opening.group(2)
    return None if name in _SELF_CLOSING_TAGS else ("open", name)


class UnitySyntaxGuard:
    """Protects Unity markup and format specifiers during translation."""

    @staticmethod
    def protect(text: str, mode: str = "token") -> tuple[str, list[str]]:
        """Extract tags and replace them with immutable placeholders.

        Args:
            text: Original string.
            mode: 'token' (⟦ULPH_N⟧) or 'xml' (<ph id="N"/>).
        """
        extracted_tags: list[str] = []

        def _replacer(match: re.Match[str]) -> str:
            tag = match.group(0)
            idx = len(extracted_tags)
            extracted_tags.append(tag)
            if mode == "xml":
                return f'<ph id="{idx}"/>'
            return f"⟦ULPH_{idx}⟧"

        with _state_lock:
            protect_re = _active_protect_re
        protected = protect_re.sub(_replacer, text)
        return protected, extracted_tags

    @staticmethod
    def restore(translated_text: str, tags: list[str], mode: str = "token") -> str:
        """Restore extracted tags into translated text, recovering mangled tokens."""
        if not tags:
            return translated_text

        result = translated_text

        def _restore_match(m: re.Match[str]) -> str:
            idx = int(next(group for group in m.groups() if group is not None))
            return tags[idx] if 0 <= idx < len(tags) else m.group(0)

        if mode == "xml":
            return re.sub(
                r'<ph\s+id=["\']?(\d+)["\']?\s*(?:/>|>\s*</ph\s*>)',
                _restore_match,
                result,
                flags=re.IGNORECASE,
            )

        result = TOKEN_RE.sub(_restore_match, result)

        # Fuzzy recovery for tokens spaced or bracket-mangled by machine engines
        if "ulph" in result.lower():
            result = TOKEN_FUZZY_RE.sub(_restore_match, result)

        return result

    @staticmethod
    def _critical_tokens(text: str) -> Counter[str]:
        """Collect format placeholders and RichText tags, ignoring cosmetic escapes."""
        with _state_lock:
            validate_re = _active_validate_re
        tokens = (t for t in validate_re.findall(text) if t not in _COSMETIC_TOKENS)
        return Counter(t if t.startswith(("{", "%")) else t.lower() for t in tokens)

    @staticmethod
    def integrity_issues(original: str, translated: str) -> list[tuple[str, list[str]]]:
        """Structured integrity problems as (code, tokens); codes: leaked, missing, unexpected.

        UI layers localize these codes; ``validate_integrity`` renders them for logs.
        """
        issues: list[tuple[str, list[str]]] = []
        if LEAKED_TOKEN_RE.search(translated):
            issues.append((ISSUE_LEAKED, []))
        expected = UnitySyntaxGuard._critical_tokens(original)
        actual = UnitySyntaxGuard._critical_tokens(translated)
        missing = expected - actual
        extra = actual - expected
        if missing:
            issues.append((ISSUE_MISSING, sorted(missing.elements())))
        if extra:
            issues.append((ISSUE_UNEXPECTED, sorted(extra.elements())))
        return issues

    @staticmethod
    def validate_integrity(original: str, translated: str) -> tuple[bool, list[str]]:
        """Verify every placeholder and RichText tag survived translation unchanged.

        A missing ``{0}`` crashes ``string.Format`` at runtime and an unbalanced
        ``<color>`` bleeds styling, so any multiset mismatch is a hard failure.
        """
        errors = [
            _ISSUE_LOG_TEMPLATES[code].format(tokens=tokens)
            for code, tokens in UnitySyntaxGuard.integrity_issues(original, translated)
        ]
        return len(errors) == 0, errors

    @staticmethod
    def repair_missing_tokens(original: str, translated: str) -> str | None:
        """Re-insert standalone tokens an engine dropped; None when repair is unsafe.

        Only unpaired tokens ({0}, {name}, %s, <sprite=1>, <br>) are re-inserted, at the
        position proportional to where they sat in the original, snapped to the nearest
        word boundary. Paired tags (<b>…</b>) are never guessed: wrapping the wrong words
        is worse than a review. Returns the repaired text only if it passes the gate.
        """
        issues = UnitySyntaxGuard.integrity_issues(original, translated)
        if not issues or any(code != ISSUE_MISSING for code, _ in issues):
            return None
        missing = Counter(token for _, tokens in issues for token in tokens)
        with _state_lock:
            prot_terms = _protected_terms
        if any(tag_role(token) is not None or token.lower() in prot_terms for token in missing):
            return None  # paired tags and dropped names are never guessed back in
        if any(_token_became_text(token, original, translated) for token in missing):
            return None
        insertions = _missing_token_positions(original, missing)
        if not insertions:
            return None
        repaired = translated
        # Sort by ratio descending; for start-anchored tokens (ratio <= 0.1), prepend in
        # reverse source order so the first source token ends up first; for end-anchored
        # tokens (ratio >= 0.9), append in forward source order so source order is kept.
        for ratio, _order, token in sorted(
            insertions,
            key=lambda item: (-item[0], -item[1] if item[0] < 0.1 else item[1]),
        ):
            repaired = _insert_at_word_boundary(repaired, token, ratio)
        return repaired if not UnitySyntaxGuard.integrity_issues(original, repaired) else None


def _token_became_text(token: str, original: str, translated: str) -> bool:
    """True when an engine rewrote '{0}' as '0' (or '{name}' as 'name') instead of dropping it.

    Re-inserting the token would then duplicate the value ('Gold: {0} 0').
    """
    inner = token.strip("{}%<>").split(":")[0].split(",")[0].split("=")[0].strip("$[]")
    if not inner:
        return False
    word = re.compile(rf"(?<![\w{{]){re.escape(inner)}(?![\w}}])", re.IGNORECASE)
    with _state_lock:
        validate_re = _active_validate_re
    outside_tokens = validate_re.sub(" ", original)
    return bool(word.search(translated)) and not word.search(outside_tokens)


def _missing_token_positions(original: str, missing: Counter[str]) -> list[tuple[float, int, str]]:
    """(relative position, source offset, token) for the last occurrences of each missing token."""
    positions: list[tuple[float, int, str]] = []
    length = max(len(original), 1)
    with _state_lock:
        validate_re = _active_validate_re
    for match in reversed(list(validate_re.finditer(original))):
        token = match.group(0)
        key = token if token.startswith(("{", "%")) else token.lower()
        if missing.get(key, 0) > 0:
            missing[key] -= 1
            before = validate_re.sub("", original[: match.start()])
            after = validate_re.sub("", original[match.end():])
            # A token that ends (or starts) the visible text keeps that anchor exactly.
            if not any(ch.isalnum() for ch in after):
                ratio = 1.0
            elif not any(ch.isalnum() for ch in before):
                ratio = 0.0
            else:
                ratio = match.start() / length
            positions.append((ratio, match.start(), token))
    return positions if sum(missing.values()) == 0 else []


def _insert_at_word_boundary(text: str, token: str, ratio: float) -> str:
    """Insert token near ratio*len(text), preferring a space within ±20 characters."""
    if ratio < 0.1:
        return f"{token} {text}"
    if ratio > 0.9:
        return f"{text} {token}"
    target = int(ratio * len(text))
    for delta in range(21):
        for pos in (target + delta, target - delta):
            if 0 < pos < len(text) and text[pos - 1] == " ":
                return f"{text[:pos]}{token} {text[pos:]}"
    return f"{token} {text}" if ratio < 0.5 else f"{text} {token}"
