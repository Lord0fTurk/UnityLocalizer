# -*- coding: utf-8 -*-
"""Format-agnostic string extractors shared by loose files and in-bundle TextAssets."""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from typing import Any

from src.core.parsers.ink_json import ink_strings, is_ink_document
from src.core.parsers.loc_table import detect_layout, looks_like_identifier, parse_rows, table_strings
from src.core.parsers.yarn_lines import looks_like_yarn, yarn_strings

logger = logging.getLogger(__name__)

NON_TRANSLATABLE_KEYS = frozenset({
    "id", "guid", "uuid", "type", "tag", "asset", "prefab", "path",
    "audio", "sound", "bgm", "sfx", "image", "texture", "icon", "scene", "event",
    "shader", "anim", "clip", "key", "voice", "sprite", "portrait", "animation",
    "m_internalids", "m_keydatastring", "m_bucketdatastring", "m_entrydatastring",
    "m_extradatastring", "m_providerids", "m_resourceproviderdata", "m_locatorid",
})

YARN_CONTROL_PREFIXES = ("title:", "tags:", "===", "---", "<<", "//")


def is_technical_key(key: str) -> bool:
    """Check if JSON key represents technical metadata rather than dialogue/UI."""
    k = key.lower().strip()
    if k in NON_TRANSLATABLE_KEYS:
        return True
    if k.endswith(("_id", "_guid", "_uuid", "_key", "_type", "_tag", "_name_id")):
        return True
    if k.startswith(("id_", "guid_", "uuid_")):
        return True
    return False


def strings_from_json_data(data: Any, key_name: str = "") -> list[str]:
    """Collect string leaves from parsed JSON, skipping technical keys."""
    found: list[str] = []
    stack: list[tuple[Any, str]] = [(data, key_name)]
    while stack:
        item, key = stack.pop()
        if isinstance(item, dict):
            stack.extend((v, str(k).lower()) for k, v in item.items())
        elif isinstance(item, list):
            stack.extend((elem, key) for elem in item)
        elif isinstance(item, str) and len(item.strip()) > 1 and not is_technical_key(key):
            found.append(item)
    found.reverse()
    return found


def strings_from_json_document(data: Any) -> list[str]:
    """Collect strings from parsed JSON, dispatching compiled Ink stories to their extractor."""
    if is_ink_document(data):
        return ink_strings(data)
    return strings_from_json_data(data)


def strings_from_csv_text(text: str, delimiter: str = ",", source_lang: str = "en") -> list[str]:
    """Collect source-column cells of a string table, or display-like cells of a plain sheet."""
    rows = parse_rows(text, delimiter)
    layout = detect_layout(rows[0], source_lang) if rows else None
    if layout is not None:
        return table_strings(rows, layout)
    found: list[str] = []
    for row in rows:
        for cell in row:
            value = cell.strip()
            if len(value) > 1 and not value.isdigit() and not looks_like_identifier(value):
                found.append(value)
    return found


def is_control_line(line: str) -> bool:
    """Return True for blank lines and Yarn/Ink control lines that must never be translated."""
    stripped = line.strip()
    return not stripped or stripped.startswith(YARN_CONTROL_PREFIXES)


def strings_from_lines(text: str) -> list[str]:
    """Collect non-empty lines, skipping Yarn/Ink style control lines."""
    return [line.strip() for line in text.splitlines() if not is_control_line(line)]


def strings_from_xml_text(text: str) -> list[str]:
    """Collect element text nodes from XML content."""
    if "<!ENTITY" in text.upper():
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        logger.debug("XML parse failed: %s", exc)
        return []
    return [chunk.strip() for chunk in root.itertext() if len(chunk.strip()) > 1]


def translate_xml_text(text: str, translations: dict[str, str]) -> str | None:
    """Replace element text/tail nodes in XML content; None if XML is invalid."""
    if "<!ENTITY" in text.upper():
        return None
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        logger.debug("XML parse failed on write: %s", exc)
        return None

    def _swap(raw: str | None) -> str | None:
        if not raw:
            return raw
        core = raw.strip()
        if core not in translations:
            return raw
        start = raw.index(core)
        return f"{raw[:start]}{translations[core]}{raw[start + len(core):]}"

    for elem in root.iter():
        elem.text = _swap(elem.text)
        elem.tail = _swap(elem.tail)
    body = ET.tostring(root, encoding="unicode")
    stripped = text.lstrip("\ufeff").lstrip()
    if stripped.startswith("<?xml"):
        decl_end = stripped.find("?>")
        if decl_end != -1:
            return stripped[: decl_end + 2] + "\n" + body
    return body


def sniff_and_extract(text: str) -> list[str]:
    """Detect the content format of an untyped text blob and extract its strings."""
    stripped = text.lstrip("\ufeff").strip()
    if not stripped:
        return []
    if stripped[0] in "{[":
        try:
            return strings_from_json_document(json.loads(stripped))
        except json.JSONDecodeError:
            logger.debug("Blob looked like JSON but failed to parse; using line mode")
    if stripped.startswith("<"):
        xml_strings = strings_from_xml_text(stripped)
        if xml_strings:
            return xml_strings
    if looks_like_yarn(stripped):
        return yarn_strings(stripped)
    delimiter = _detect_table_delimiter(stripped)
    if delimiter:
        return strings_from_csv_text(stripped, delimiter)
    return strings_from_lines(stripped)


def _detect_table_delimiter(text: str) -> str | None:
    """Return ',' or '\\t' when the first lines form a consistent table."""
    sample_lines = [ln for ln in text.splitlines()[:20] if ln.strip()]
    if len(sample_lines) < 3:
        return None
    sample = "\n".join(sample_lines)
    for delimiter in ("\t", ","):
        rows = parse_rows(sample, delimiter)
        if len(rows) < 3:
            continue
        widths = {len(r) for r in rows if any(c.strip() for c in r)}
        if len(widths) != 1:
            continue
        cols = next(iter(widths))
        if cols < 2:
            continue
        if delimiter == "," and cols == 2:
            # Avoid misclassifying normal prose sentences containing a single comma:
            # require a recognized language/key header or an identifier-like first column.
            has_layout = detect_layout(rows[0], "en") is not None
            first_col_ids = all(looks_like_identifier(r[0].strip()) or " " not in r[0].strip() for r in rows)
            if not (has_layout or first_col_ids):
                continue
        return delimiter
    return None
