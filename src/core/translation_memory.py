# -*- coding: utf-8 -*-
"""External translation memory (TM): reuse existing human translations before any engine.

Supported files:
* ``.tmx`` — TMX 1.4 translation units; segments picked by source/target language.
* ``.csv`` / ``.tsv`` — string tables (language headers detected) or two-column sheets.
* ``.json`` — ``{"source": "target"}`` or ``[{"source": ..., "target": ...}]``.
* ``.txt`` — XUnity.AutoTranslator dictionaries (``key=value``), e.g. from other patches.

Exact matches are always used. Fuzzy matching (opt-in) only accepts a candidate whose
placeholders and tags are identical to the query, so a neighbour sentence can never
move a ``{0}`` into the wrong place.
"""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from pathlib import Path

from src.core.parsers import xunity_codec
from src.core.parsers.loc_table import base_language, detect_layout, header_language, parse_rows
from src.core.syntax_guard import UNITY_PROTECT_RE

logger = logging.getLogger(__name__)

SUPPORTED_TM_SUFFIXES = frozenset({".tmx", ".csv", ".tsv", ".json", ".txt"})
_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(sorted(UNITY_PROTECT_RE.findall(text)))


class TranslationMemory:
    """In-memory source -> target lookup with optional placeholder-safe fuzzy matching."""

    def __init__(self, entries: dict[str, str], fuzzy_threshold: float | None = None) -> None:
        self.entries = {k: v for k, v in entries.items() if k.strip() and v.strip()}
        self.fuzzy_threshold = fuzzy_threshold
        self._keys = list(self.entries)
        self._keys_by_tokens: dict[tuple[str, ...], list[str]] = {}
        if self.fuzzy_threshold:
            for key in self._keys:
                self._keys_by_tokens.setdefault(_tokens(key), []).append(key)

    def __len__(self) -> int:
        return len(self.entries)

    def lookup(self, text: str) -> str | None:
        """Exact (then, if enabled, placeholder-identical fuzzy) translation for text."""
        exact = self.entries.get(text) or self.entries.get(text.strip())
        if exact or not self.fuzzy_threshold or not self._keys:
            return exact
        candidates = self._keys_by_tokens.get(_tokens(text))
        if not candidates:
            return None
        from rapidfuzz import fuzz, process

        match = process.extractOne(text, candidates, scorer=fuzz.ratio, score_cutoff=self.fuzzy_threshold * 100)
        if match:
            return self.entries[match[0]]
        return None

    @classmethod
    def load(
        cls, paths: Iterable[str | Path], source_lang: str, target_lang: str, fuzzy_threshold: float | None = None
    ) -> TranslationMemory:
        """Merge every readable file (later files override earlier ones)."""
        entries: dict[str, str] = {}
        for raw_path in paths:
            path = Path(str(raw_path).strip())
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_TM_SUFFIXES:
                logger.warning("Translation memory skipped (missing or unsupported): %s", path)
                continue
            try:
                loaded = _load_file(path, source_lang, target_lang)
            except (OSError, ValueError, TypeError, ET.ParseError) as exc:
                logger.warning("Translation memory %s could not be read: %s", path.name, exc)
                continue
            entries.update(loaded)
            logger.info("Translation memory %s: %d entries", path.name, len(loaded))
        return cls(entries, fuzzy_threshold)


def _load_file(path: Path, source_lang: str, target_lang: str) -> dict[str, str]:
    suffix = path.suffix.lower()
    if suffix == ".tmx":
        return load_tmx(path, source_lang, target_lang)
    text = path.read_text(encoding="utf-8-sig")
    if suffix == ".json":
        return load_json(text)
    if suffix == ".txt":
        return dict(entry for line in text.splitlines() if (entry := xunity_codec.decode_line(line)))
    return load_table(text, "\t" if suffix == ".tsv" else ",", source_lang, target_lang)


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def load_tmx(path: Path, source_lang: str, target_lang: str) -> dict[str, str]:
    """Translation units whose segments match the language pair (first/second tuv as fallback)."""
    text = path.read_text(encoding="utf-8-sig")
    if "<!ENTITY" in text.upper():
        raise ValueError("DOCTYPE ENTITY declarations are not allowed in TMX files")
    src, tgt = base_language(source_lang), base_language(target_lang)
    entries: dict[str, str] = {}
    root = ET.fromstring(text)
    for tu in (el for el in root.iter() if _local_tag(el.tag) == "tu"):
        segments: list[tuple[str, str]] = []
        for tuv in (el for el in tu.iter() if _local_tag(el.tag) == "tuv"):
            seg = next((el for el in tuv if _local_tag(el.tag) == "seg"), None)
            lang = tuv.get(_XML_LANG) or tuv.get("lang") or ""
            if seg is not None:
                segments.append((base_language(lang), "".join(seg.itertext())))
        by_lang = dict(segments)
        source = by_lang.get(src) if src != "auto" else None
        target = by_lang.get(tgt)
        if source is None and len(segments) == 2:
            source = segments[0][1] if segments[0][0] != tgt else segments[1][1]
        if source and target:
            entries[source] = target
    return entries


def load_json(text: str) -> dict[str, str]:
    data = json.loads(text)
    if isinstance(data, dict):
        return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}
    if isinstance(data, list):
        return {
            str(item["source"]): str(item["target"])
            for item in data
            if isinstance(item, dict) and isinstance(item.get("source"), str) and isinstance(item.get("target"), str)
        }
    return {}


def load_table(text: str, delimiter: str, source_lang: str, target_lang: str) -> dict[str, str]:
    """Language-headed string table (source -> target column) or a plain two-column sheet."""
    rows = parse_rows(text, delimiter)
    if not rows:
        return {}
    layout = detect_layout(rows[0], source_lang if source_lang != "auto" else "en", target_lang)
    if layout is not None and layout.target_col is not None:
        src_col, tgt_col, body = layout.source_col, layout.target_col, rows[1:]
    else:
        has_header = any(header_language(cell) for cell in rows[0])
        src_col, tgt_col, body = 0, 1, rows[1:] if has_header else rows
    return {row[src_col]: row[tgt_col] for row in body if len(row) > max(src_col, tgt_col)}
