# -*- coding: utf-8 -*-
"""Parser for loose dialogue and text files inside StreamingAssets."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.core.parsers.base import BaseParser
from src.core.parsers.ink_json import is_ink_document, translate_ink
from src.core.parsers.loc_table import (
    apply_to_table,
    detect_layout,
    looks_like_identifier,
    parse_rows,
    serialize_rows,
)
from src.core.parsers.text_formats import (
    _detect_table_delimiter,
    is_control_line,
    is_technical_key,
    sniff_and_extract,
    strings_from_csv_text,
    strings_from_json_document,
    strings_from_xml_text,
    translate_xml_text,
)
from src.core.parsers.naninovel_parser import NaninovelParser, line_strings
from src.core.parsers.subtitle_resx import resx_strings, srt_strings, translate_resx, translate_srt
from src.core.parsers.yarn_lines import looks_like_yarn, translate_yarn_text, yarn_strings
from src.utils.file_ops import pristine_source, safe_write

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = frozenset({".json", ".csv", ".tsv", ".txt", ".yarn", ".xml", ".nani", ".srt", ".resx"})


def _detect_encoding(path: Path) -> str:
    """Return 'utf-8-sig' if the original file starts with a UTF-8 BOM, else 'utf-8'."""
    try:
        with open(path, "rb") as f:
            return "utf-8-sig" if f.read(3) == b"\xef\xbb\xbf" else "utf-8"
    except OSError:
        return "utf-8"


def _replace_json_iterative(root: Any, translations: dict[str, str]) -> Any:
    """Iteratively replace translatable string leaves in a JSON tree without recursion."""
    if not isinstance(root, (dict, list)):
        return translations.get(root, root) if isinstance(root, str) else root
    clone_map: dict[int, Any] = {}
    stack: list[tuple[Any, str, bool]] = [(root, "", False)]
    while stack:
        node, key_name, visited = stack.pop()
        if not visited:
            stack.append((node, key_name, True))
            if isinstance(node, dict):
                for k, v in reversed(list(node.items())):
                    if isinstance(v, (dict, list)):
                        stack.append((v, str(k).lower(), False))
            elif isinstance(node, list):
                for elem in reversed(node):
                    if isinstance(elem, (dict, list)):
                        stack.append((elem, key_name, False))
            continue
        if isinstance(node, dict):
            out_dict: dict[Any, Any] = {}
            for k, v in node.items():
                k_low = str(k).lower()
                if isinstance(v, (dict, list)):
                    out_dict[k] = clone_map.get(id(v), v)
                elif isinstance(v, str) and v in translations and not is_technical_key(k_low):
                    out_dict[k] = translations[v]
                else:
                    out_dict[k] = v
            clone_map[id(node)] = out_dict
        elif isinstance(node, list):
            out_list: list[Any] = []
            for elem in node:
                if isinstance(elem, (dict, list)):
                    out_list.append(clone_map.get(id(elem), elem))
                elif isinstance(elem, str) and elem in translations and not is_technical_key(key_name):
                    out_list.append(translations[elem])
                else:
                    out_list.append(elem)
            clone_map[id(node)] = out_list
    return clone_map.get(id(root), root)


class StreamingAssetsParser(BaseParser):
    """Parses JSON, CSV, TSV, XML, text, Yarn and Naninovel files located in StreamingAssets."""

    def __init__(self, source_lang: str = "en", target_lang: str = "") -> None:
        self.source_lang = source_lang
        self.target_lang = target_lang

    def extract_strings(self, file_path: Path | str) -> list[str]:
        """Extract translatable strings from a supported loose text file.

        A file this tool already patched is read from its original backup, so
        re-runs harvest the game's source text rather than the last translation.
        """
        path = Path(file_path)
        suffix = path.suffix.lower()
        if not path.is_file() or suffix not in SUPPORTED_SUFFIXES:
            return []
        try:
            text = pristine_source(path).read_text(encoding="utf-8-sig", errors="replace")
        except OSError as exc:
            logger.error("Failed to read %s: %s", path, exc)
            return []
        return self._extract_by_suffix(text, suffix, path)

    def _extract_by_suffix(self, text: str, suffix: str, path: Path) -> list[str]:
        """Dispatch text to the extractor matching the file extension."""
        if suffix == ".json":
            try:
                return strings_from_json_document(json.loads(text, strict=False), self.source_lang)
            except json.JSONDecodeError as exc:
                logger.error("Failed to parse JSON %s: %s", path, exc)
                return []
        if suffix in (".csv", ".tsv"):
            return strings_from_csv_text(text, "\t" if suffix == ".tsv" else ",", self.source_lang)
        if suffix == ".xml":
            return strings_from_xml_text(text)
        if suffix == ".yarn":
            return yarn_strings(text)
        if suffix == ".nani":
            return [s for line in text.splitlines() for s in line_strings(line)]
        if suffix == ".srt":
            return srt_strings(text)
        if suffix == ".resx":
            return resx_strings(text)
        return sniff_and_extract(text, self.source_lang)

    def apply_translations(
        self,
        file_path: Path | str,
        translations: dict[str, str],
        output_path: Path | str | None = None,
    ) -> bool:
        """Apply translations back to file and persist.

        The original game text is always the input (the ``.bak`` backup once the
        file was patched), so repeated runs re-translate from source instead of
        searching for source strings in an already translated file.
        """
        path = Path(file_path)
        source = pristine_source(path)
        out_path = Path(output_path) if output_path else path
        suffix = path.suffix.lower()

        if suffix == ".json":
            return self._apply_json(source, out_path, translations)
        if suffix in (".csv", ".tsv"):
            delimiter = "\t" if suffix == ".tsv" else ","
            return self._apply_csv(source, out_path, translations, delimiter)
        if suffix == ".xml":
            return self._apply_xml(source, out_path, translations)
        if suffix in (".txt", ".yarn"):
            return self._apply_txt(source, out_path, translations, is_yarn=suffix == ".yarn")
        if suffix == ".nani":
            return NaninovelParser().apply_translations(path, translations, out_path)
        if suffix in (".srt", ".resx"):
            return self._apply_converter(
                source, out_path, translations, translate_srt if suffix == ".srt" else translate_resx
            )
        return False

    @staticmethod
    def _apply_converter(
        in_path: Path, out_path: Path, translations: dict[str, str], convert: Callable[[str, dict[str, str]], str]
    ) -> bool:
        """Run a text converter over the pristine file and write the result atomically."""
        try:
            encoding = _detect_encoding(in_path)
            with open(in_path, "r", encoding="utf-8-sig", errors="ignore", newline="") as f:
                text = f.read()
            return safe_write(out_path, convert(text, translations), encoding=encoding)
        except Exception as exc:
            logger.error("Failed to apply translations to %s: %s", in_path, exc)
            return False

    def _apply_json(self, in_path: Path, out_path: Path, translations: dict[str, str]) -> bool:
        """Replace translated strings in JSON structure and write atomically."""
        try:
            encoding = _detect_encoding(in_path)
            with open(in_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                data = json.load(f, strict=False)

            updated = translate_ink(data, translations) if is_ink_document(data) else _replace_json_iterative(data, translations)
            indent = None if is_ink_document(data) else 2
            content = json.dumps(updated, indent=indent, ensure_ascii=False)
            return safe_write(out_path, content, encoding=encoding)
        except Exception as exc:
            logger.error("Failed to apply translations to JSON %s: %s", in_path, exc)
            return False

    def _apply_xml(self, in_path: Path, out_path: Path, translations: dict[str, str]) -> bool:
        """Replace translated element text in XML and write atomically."""
        try:
            encoding = _detect_encoding(in_path)
            with open(in_path, "r", encoding="utf-8-sig", errors="ignore", newline="") as f:
                text = f.read()
            updated = translate_xml_text(text, translations)
            if updated is None:
                return False
            return safe_write(out_path, updated, encoding=encoding)
        except Exception as exc:
            logger.error("Failed to apply translations to XML %s: %s", in_path, exc)
            return False

    def _apply_csv(
        self, in_path: Path, out_path: Path, translations: dict[str, str], delimiter: str
    ) -> bool:
        """Replace translated cells (source column only for string tables) and write atomically."""
        try:
            encoding = _detect_encoding(in_path)
            with open(in_path, "r", encoding="utf-8-sig", errors="ignore", newline="") as f:
                text = f.read()
            rows = parse_rows(text, delimiter)
            layout = detect_layout(rows[0], self.source_lang, self.target_lang) if rows else None
            if layout is not None:
                apply_to_table(rows, layout, translations)
            else:
                rows = [[self._translate_cell(cell, translations) for cell in row] for row in rows]
            newline = "\r\n" if "\r\n" in text else "\n"
            content = serialize_rows(rows, delimiter, newline)
            return safe_write(out_path, content, encoding=encoding)
        except Exception as exc:
            logger.error("Failed to apply translations to CSV %s: %s", in_path, exc)
            return False

    @staticmethod
    def _translate_cell(cell: str, translations: dict[str, str]) -> str:
        """Translate a plain-sheet cell unless it looks like a lookup key or path."""
        value = cell.strip()
        if value in translations and not looks_like_identifier(value):
            return translations[value]
        return cell

    def _apply_txt(
        self, in_path: Path, out_path: Path, translations: dict[str, str], is_yarn: bool = False
    ) -> bool:
        """Replace translated lines in flat text, Yarn, or sniffed structured .txt files."""
        try:
            encoding = _detect_encoding(in_path)
            with open(in_path, "r", encoding="utf-8-sig", errors="ignore", newline="") as f:
                text = f.read()
            if is_yarn or looks_like_yarn(text):
                return safe_write(out_path, translate_yarn_text(text, translations), encoding=encoding)

            stripped = text.lstrip("\ufeff").strip()
            if not is_yarn and stripped:
                if stripped[0] in "{[":
                    if self._apply_json(in_path, out_path, translations):
                        return True
                elif stripped.startswith("<"):
                    if self._apply_xml(in_path, out_path, translations):
                        return True
                else:
                    delim = _detect_table_delimiter(stripped)
                    if delim:
                        return self._apply_csv(in_path, out_path, translations, delim)

            out_lines: list[str] = []
            for line in text.splitlines(keepends=True):
                line_stripped = line.strip()
                if not is_control_line(line) and line_stripped in translations:
                    indent = line[: len(line) - len(line.lstrip())]
                    newline = line[len(line.rstrip("\r\n")):]
                    out_lines.append(f"{indent}{translations[line_stripped]}{newline}")
                    continue
                out_lines.append(line)

            return safe_write(out_path, "".join(out_lines), encoding=encoding)
        except Exception as exc:
            logger.error("Failed to apply translations to TXT %s: %s", in_path, exc)
            return False
