# -*- coding: utf-8 -*-
"""Column-aware localization table detection for CSV/TSV string tables.

Game string tables (I2 exports, Yarn Spinner compiled string tables, custom
``Key,English,French`` sheets) mix lookup keys, metadata and other locales with
the source text. Only the source column may be translated; keys must never change.
"""

from __future__ import annotations

import csv
import io
import re
import sys
from dataclasses import dataclass

try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2147483647)

# Base language code -> lowercase header aliases (English and native names).
LANGUAGE_ALIASES: dict[str, tuple[str, ...]] = {
    "en": ("english", "en", "eng", "source", "original"),
    "tr": ("turkish", "türkçe", "turkce", "tr"),
    "de": ("german", "deutsch", "de"),
    "fr": ("french", "français", "francais", "fr"),
    "es": ("spanish", "español", "espanol", "es"),
    "it": ("italian", "italiano", "it"),
    "pt": ("portuguese", "português", "portugues", "pt", "brazilian"),
    "ru": ("russian", "русский", "ru"),
    "pl": ("polish", "polski", "pl"),
    "ja": ("japanese", "日本語", "ja", "jp"),
    "ko": ("korean", "한국어", "ko", "kr"),
    "zh": ("chinese", "中文", "简体中文", "繁體中文", "zh", "cn", "schinese", "tchinese"),
    "ar": ("arabic", "العربية", "ar"),
    "fa": ("persian", "farsi", "فارسی", "fa"),
    "uk": ("ukrainian", "українська", "uk"),
    "nl": ("dutch", "nederlands", "nl"),
    "th": ("thai", "ไทย", "th"),
    "vi": ("vietnamese", "tiếng việt", "vi"),
    "id": ("indonesian", "bahasa indonesia", "id"),
}

KEY_HEADERS = frozenset({"key", "keys", "id", "term", "terms", "lineid", "line id", "string id", "stringid"})
TEXT_HEADERS = frozenset({"text", "value", "string", "message", "content", "dialogue", "line"})

_BRACKET_CODE_RE = re.compile(r"[\[(]\s*([a-z]{2,3})(?:[-_][a-z0-9]{2,4})?\s*[\])]")
_LOCALE_CODE_RE = re.compile(r"^([a-z]{2,3})(?:[-_][a-z0-9]{2,4})?$")
_IDENTIFIER_RE = re.compile(r"[_/\\]|[a-z][A-Z]|\w\.\w")


@dataclass(frozen=True)
class TableLayout:
    """Resolved column roles of a localization table (header is row 0)."""

    source_col: int
    key_col: int | None = None
    target_col: int | None = None


DEFAULT_SOURCE_LANGUAGE = "en"


def resolve_source_language(code: str) -> str:
    """Concrete source locale for column picking and XUnity ``FromLanguage`` ('auto' -> 'en')."""
    cleaned = code.strip()
    return DEFAULT_SOURCE_LANGUAGE if not cleaned or cleaned.lower() == "auto" else cleaned


def base_language(code: str) -> str:
    """Normalize a locale code such as 'pt-BR' or 'zh_CN' to its base language."""
    return re.split(r"[-_]", code.strip().lower(), maxsplit=1)[0]


def header_language(cell: str) -> str | None:
    """Return the base language code a header cell names, e.g. 'English [en-US]' -> 'en'."""
    clean = cell.strip().lower()
    if not clean or clean in KEY_HEADERS:
        return None
    bracket = _BRACKET_CODE_RE.search(clean)
    if bracket:
        code = _code_for_alias(bracket.group(1))
        if code:
            return code
    locale = _LOCALE_CODE_RE.match(clean)
    code = _code_for_alias(clean) or (_code_for_alias(locale.group(1)) if locale else None)
    if code:
        return code
    # 'English (United States)' style: only full English names may carry a suffix.
    first_word = re.split(r"[\s(\[]", clean, maxsplit=1)[0]
    return next((c for c, aliases in LANGUAGE_ALIASES.items() if first_word == aliases[0]), None)


def _code_for_alias(alias: str) -> str | None:
    """Return the base language code an exact alias belongs to."""
    return next((code for code, aliases in LANGUAGE_ALIASES.items() if alias in aliases), None)


def looks_like_identifier(value: str) -> bool:
    """Heuristic for lookup keys/paths such as 'MENU_START', 'ui.title' or 'menuStart'."""
    stripped = value.strip()
    return bool(stripped) and not any(c.isspace() for c in stripped) and bool(_IDENTIFIER_RE.search(stripped))


def detect_layout(header: list[str], source_lang: str = "en", target_lang: str = "") -> TableLayout | None:
    """Detect key/source/target columns from a header row; None when it is not a string table."""
    languages = {idx: header_language(cell) for idx, cell in enumerate(header)}
    lang_cols = [idx for idx, code in languages.items() if code]
    normalized = [cell.strip().lower() for cell in header]
    key_col = next((idx for idx, name in enumerate(normalized) if name in KEY_HEADERS), None)

    if lang_cols:
        wanted = base_language(source_lang)
        source = next((idx for idx in lang_cols if languages[idx] == wanted), lang_cols[0])
    else:
        text_cols = [idx for idx, name in enumerate(normalized) if name in TEXT_HEADERS]
        if not text_cols or key_col is None:
            return None
        source = text_cols[0]

    target = None
    if target_lang:
        wanted_target = base_language(target_lang)
        target = next((idx for idx in lang_cols if languages[idx] == wanted_target and idx != source), None)
    return TableLayout(source_col=source, key_col=key_col, target_col=target)


def parse_rows(text: str, delimiter: str) -> list[list[str]]:
    """Parse delimited text into rows."""
    try:
        return list(csv.reader(io.StringIO(text), delimiter=delimiter))
    except (csv.Error, OverflowError):
        return []


def table_strings(rows: list[list[str]], layout: TableLayout) -> list[str]:
    """Collect translatable source-column cells, skipping the header."""
    found: list[str] = []
    for row in rows[1:]:
        if len(row) <= layout.source_col:
            continue
        value = row[layout.source_col].strip()
        if len(value) > 1 and not value.isdigit():
            found.append(value)
    return found


def apply_to_table(rows: list[list[str]], layout: TableLayout, translations: dict[str, str]) -> int:
    """Rewrite source cells (and empty target-locale cells) in place; return changed rows."""
    changed = 0
    for row in rows[1:]:
        if len(row) <= layout.source_col:
            continue
        translated = translations.get(row[layout.source_col].strip())
        if translated is None:
            continue
        row[layout.source_col] = translated
        target = layout.target_col
        if target is not None and target < len(row) and not row[target].strip():
            row[target] = translated
        changed += 1
    return changed


def serialize_rows(rows: list[list[str]], delimiter: str, newline: str = "\n") -> str:
    """Serialize rows back to delimited text."""
    buffer = io.StringIO()
    csv.writer(buffer, delimiter=delimiter, lineterminator=newline).writerows(rows)
    return buffer.getvalue()
