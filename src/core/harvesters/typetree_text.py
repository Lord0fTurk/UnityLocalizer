# -*- coding: utf-8 -*-
"""Field-aware display text extraction from deserialized Unity TypeTree dictionaries.

With a TypeTree, a MonoBehaviour is a nested dict whose keys are C# field names,
so object names, GUIDs and enum-like values can be dropped by field instead of by
guessing on raw bytes. Known localization containers get dedicated rules so that
only the source-language column is harvested:

* Unity Localization ``StringTable``: one table per locale; foreign tables skipped.
* I2 Localization ``LanguageSourceData``: ``mTerms[].Languages[source_index]``.
* Pixel Crushers ``DialogueDatabase``: display fields of ``fields[]`` entries only.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from src.core.harvesters.harvest_stats import HarvestStats
from src.core.parsers.loc_table import base_language, header_language
from src.core.parsers.text_formats import is_technical_key

# Unity serialization fields that never hold player-visible text (compared lowercase).
UNITY_TECHNICAL_FIELDS = frozenset({
    "m_name", "m_editorclassidentifier", "m_classname", "m_namespace", "m_assemblyname",
    "m_tablecollectionname", "m_code", "m_key", "m_tag", "m_identifier", "m_sharedtabledata",
    "m_fontdata", "m_material", "m_sprite", "m_script", "m_gameobject", "m_animation",
    "term", "termtype", "flags", "languages_touch", "mterm", "typestring", "m_metadata",
    "m_eventid", "m_methodname", "m_targetassemblytypename", "m_objectargumentassemblytypename",
})

BASE_MONOBEHAVIOUR_KEYS = frozenset({
    "m_GameObject", "m_Enabled", "m_Script", "m_Name", "m_EditorHideFlags", "m_EditorClassIdentifier",
})

# Dialogue System field titles that carry display text (others are IDs, scripts, sequences).
DIALOGUE_SYSTEM_TEXT_FIELDS = frozenset({
    "Dialogue Text", "Menu Text", "Display Name", "Name", "Description", "Title",
    "Success Description", "Failure Description",
})


def has_user_fields(tree: dict[str, Any]) -> bool:
    """False when only the MonoBehaviour base fields were read (no script TypeTree)."""
    return any(key not in BASE_MONOBEHAVIOUR_KEYS for key in tree)


def _is_skipped_field(key: str) -> bool:
    """True for Unity bookkeeping fields and generic technical keys."""
    lowered = key.lower()
    return lowered in UNITY_TECHNICAL_FIELDS or is_technical_key(lowered)


def generic_strings(tree: Any) -> list[str]:
    """Collect string leaves whose owning field is not technical."""
    found: list[str] = []
    stack: list[tuple[Any, str]] = [(tree, "")]
    while stack:
        node, key = stack.pop()
        if isinstance(node, dict):
            stack.extend((v, str(k)) for k, v in node.items() if not _is_skipped_field(str(k)))
        elif isinstance(node, list):
            stack.extend((item, key) for item in node)
        elif isinstance(node, str) and node.strip():
            found.append(node)
    found.reverse()
    return found


def _is_string_table(tree: dict[str, Any]) -> bool:
    return "m_TableData" in tree and "m_LocaleId" in tree


def string_table_strings(tree: dict[str, Any], source_lang: str, stats: HarvestStats | None = None) -> list[str]:
    """Return ``m_Localized`` values when the table's locale is the source language."""
    locale = tree.get("m_LocaleId") or {}
    code = locale.get("m_Code", "") if isinstance(locale, dict) else ""
    entries = [
        entry["m_Localized"]
        for entry in tree.get("m_TableData") or []
        if isinstance(entry, dict) and isinstance(entry.get("m_Localized"), str) and entry["m_Localized"].strip()
    ]
    if code and base_language(code) != base_language(source_lang):
        if stats is not None and entries:
            stats.tables_skipped[base_language(code)] += len(entries)
        return []
    if stats is not None and entries:
        stats.tables_matched += 1
    return entries


def _i2_source(tree: dict[str, Any]) -> dict[str, Any] | None:
    """Return the I2 LanguageSourceData dict (wrapped in ``mSource`` since I2 2.8.x)."""
    source = tree.get("mSource", tree)
    if isinstance(source, dict) and "mTerms" in source and "mLanguages" in source:
        return source
    return None


def _i2_source_index(languages: list[Any], source_lang: str) -> tuple[int, bool]:
    """Index of the source language among I2 ``mLanguages`` entries and whether it was listed.

    The first column is the default when the language is not listed.
    """
    wanted = base_language(source_lang)
    for index, lang in enumerate(languages):
        if not isinstance(lang, dict):
            continue
        code = str(lang.get("Code") or "")
        if (code and base_language(code) == wanted) or header_language(str(lang.get("Name") or "")) == wanted:
            return index, True
    return 0, False


def i2_strings(source: dict[str, Any], source_lang: str, stats: HarvestStats | None = None) -> list[str]:
    """Return the source-language cell of every I2 term."""
    index, found_language = _i2_source_index(source.get("mLanguages") or [], source_lang)
    if stats is not None:
        stats.i2_sources += 1
        stats.i2_unmatched += 0 if found_language else 1
    found: list[str] = []
    for term in source.get("mTerms") or []:
        cells = term.get("Languages") if isinstance(term, dict) else None
        if isinstance(cells, list) and index < len(cells) and isinstance(cells[index], str):
            if cells[index].strip():
                found.append(cells[index])
    return found


def _is_dialogue_database(tree: dict[str, Any]) -> bool:
    return "conversations" in tree and "actors" in tree


def _iter_field_lists(node: Any) -> Iterator[list[Any]]:
    """Yield every ``fields`` list nested anywhere under node."""
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            fields = current.get("fields")
            if isinstance(fields, list):
                yield fields
            stack.extend(v for k, v in current.items() if k != "fields")
        elif isinstance(current, list):
            stack.extend(current)


def dialogue_database_strings(tree: dict[str, Any]) -> list[str]:
    """Return display-field values of a Pixel Crushers DialogueDatabase."""
    found: list[str] = []
    for fields in _iter_field_lists(tree):
        for field in fields:
            if not isinstance(field, dict) or field.get("title") not in DIALOGUE_SYSTEM_TEXT_FIELDS:
                continue
            value = field.get("value")
            if isinstance(value, str) and value.strip():
                found.append(value)
    return found


def collect_display_strings(
    tree: dict[str, Any], source_lang: str = "en", stats: HarvestStats | None = None
) -> list[str]:
    """Dispatch a TypeTree dict to the matching framework rule or the generic walker."""
    if _is_string_table(tree):
        return string_table_strings(tree, source_lang, stats)
    i2_source = _i2_source(tree)
    if i2_source is not None:
        return i2_strings(i2_source, source_lang, stats)
    if _is_dialogue_database(tree):
        return dialogue_database_strings(tree)
    return generic_strings(tree)
