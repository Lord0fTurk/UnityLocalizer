# -*- coding: utf-8 -*-
"""Read-only Unity assets crawler for TextAssets, TextMeshPro, uGUI, and ScriptableObjects using UnityPy."""

from __future__ import annotations

import gc
import logging
import re
import struct
from pathlib import Path
from typing import Any

from src.core.cjk import is_single_cjk
from src.core.harvesters.bundle_locator import find_serialized_sources
from src.core.harvesters.harvest_stats import FileStat, HarvestStats
from src.core.harvesters.text_filter import looks_technical
from src.core.harvesters.typetree_text import collect_display_strings, has_user_fields
from src.core.parsers.text_formats import sniff_and_extract
from src.core.progress import CancelToken, ProgressCallback, checkpoint, emit
from src.core.syntax_guard import UNITY_PROTECT_RE

logger = logging.getLogger(__name__)

HARVESTED_TYPES = frozenset({"TextAsset", "TextMesh", "MonoBehaviour"})
_SURROGATE_RE = re.compile("[\ud800-\udfff]")
_ALLOWED_FORMAT_CHARS = frozenset("\r\n\t\u00a0\u202f\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u200b\u200c\u200d\u2060\u00ad\ufeff")
# Input System binding paths and IMGUI style names stored in serialized assets.
_ASSET_TECHNICAL_PREFIXES: tuple[str, ...] = (
    "<Keyboard>/", "<Gamepad>/", "<Mouse>/", "<Joystick>/", "<Pen>/", "<Pointer>/", "<Touchscreen>/",
    "GUI/", "GUIStyle",
)
# Numbered scene object names such as "Wall_01" or "Rock_3 left".
_NUMBERED_OBJECT_RE = re.compile(r"^[A-Za-z0-9\s]+_\d+(\s.*)?$")
# Speaker prefix in serialized dialogue templates like "{0}: ..." or "{$way}: ..."
_SPEAKER_PREFIX_RE = re.compile(r"^\{(?:\$?[A-Za-z_]\w*|\d+)\}:\s*(.+)$")


def _first_attr(data: Any, *names: str) -> Any:
    """Return the first non-None attribute among names (UnityPy renamed fields across versions)."""
    for name in names:
        value = getattr(data, name, None)
        if value is not None:
            return value
    return None


def _object_name(obj: Any) -> str:
    """Serialized ``m_Name`` of an object, '' when it cannot be peeked."""
    try:
        name = obj.peek_name()
    except Exception as exc:  # UnityPy raises heterogeneous errors on stripped layouts
        logger.debug("Cannot peek name of object %s: %s", getattr(obj, "path_id", "?"), exc)
        return ""
    return name if isinstance(name, str) else ""


class AssetHarvester:
    """Safely extracts translatable text from .assets and scenes in read-only mode."""

    @classmethod
    def is_translatable(cls, text: str) -> bool:
        """Filter out technical tokens, input bindings, asset paths, and engine classes."""
        stripped = text.strip()
        if (len(stripped) < 2 and not is_single_cjk(stripped)) or len(stripped) > 2500 or "\x00" in stripped or _SURROGATE_RE.search(stripped):
            return False
        if not all(c.isprintable() or c.isspace() or c in _ALLOWED_FORMAT_CHARS for c in stripped):
            return False
        visible = UNITY_PROTECT_RE.sub(" ", stripped)
        if not any(c.isalpha() for c in visible):
            return False
        if stripped.startswith(_ASSET_TECHNICAL_PREFIXES) or looks_technical(stripped):
            return False
        if stripped.startswith("_") and " " not in stripped:
            return False
        return not _NUMBERED_OBJECT_RE.match(stripped)

    @classmethod
    def extract_strings_from_object(
        cls, obj: Any, source_lang: str = "en", file_stat: FileStat | None = None, stats: HarvestStats | None = None
    ) -> list[str]:
        """Extract translatable strings from a TextAsset, TextMesh or MonoBehaviour object."""
        type_name = obj.type.name
        try:
            if type_name == "TextAsset":
                return cls._from_text_asset(obj, source_lang, stats)
            if type_name == "TextMesh":
                text = _first_attr(obj.read(), "m_Text", "text")
                return [text.strip()] if isinstance(text, str) and cls.is_translatable(text) else []
            if type_name == "MonoBehaviour":
                return cls._from_monobehaviour(obj, source_lang, file_stat, stats)
        except (ValueError, KeyError, EOFError, AttributeError, TypeError) as exc:
            logger.debug("Failed extracting strings from object %s: %s", getattr(obj, "path_id", "?"), exc)
        return []

    @classmethod
    def _from_text_asset(cls, obj: Any, source_lang: str = "en", stats: HarvestStats | None = None) -> list[str]:
        """Split a TextAsset into individual strings by sniffing its content format."""
        raw = _first_attr(obj.read(), "m_Script", "script")
        if isinstance(raw, bytes):
            try:
                raw = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                return []  # binary .bytes payload (serialized data, not text)
        if not isinstance(raw, str) or _SURROGATE_RE.search(raw):
            return []
        return [s.strip() for s in sniff_and_extract(raw, source_lang, stats) if cls.is_translatable(s)]

    @classmethod
    def _from_monobehaviour(
        cls, obj: Any, source_lang: str, file_stat: FileStat | None = None, stats: HarvestStats | None = None
    ) -> list[str]:
        """Prefer field-aware TypeTree extraction; fall back to raw length-prefixed scanning."""
        tree = cls._read_tree(obj)
        if tree is None:
            if file_stat is not None:
                file_stat.raw_scanned += 1
            # The object's own name (ScriptableObject asset names such as "Item_Sword") is not text.
            name = _object_name(obj)
            return [s for s in cls._scan_length_prefixed(obj.get_raw_data()) if s != name]
        strings = collect_display_strings(tree, source_lang, stats)
        return [s.strip() for s in strings if cls.is_translatable(s)]

    @staticmethod
    def _read_tree(obj: Any) -> dict[str, Any] | None:
        """Deserialize a MonoBehaviour TypeTree; None when only base fields are available."""
        try:
            tree = obj.read_typetree()
        except Exception as exc:  # UnityPy raises TypeTreeError/ValueError/EOFError on stripped layouts
            logger.debug("No usable TypeTree for object %s: %s", getattr(obj, "path_id", "?"), exc)
            return None
        return tree if isinstance(tree, dict) and has_user_fields(tree) else None

    @classmethod
    def _scan_length_prefixed(cls, raw: bytes) -> list[str]:
        """Scan 4-byte aligned little-endian length-prefixed UTF-8 strings."""
        extracted: list[str] = []
        size = len(raw)
        offset = 0
        while offset <= size - 4:
            length = struct.unpack_from("<I", raw, offset)[0]
            pad = (4 - (length % 4)) % 4
            end = offset + 4 + length
            if not (2 <= length <= 2500) or end + pad > size:
                offset += 4
                continue
            if pad and raw[end : end + pad] != b"\x00" * pad:
                offset += 4
                continue
            candidate = raw[offset + 4 : end]
            if b"\x00" in candidate:
                offset += 4
                continue
            try:
                text = candidate.decode("utf-8")
            except UnicodeDecodeError:
                offset += 4
                continue
            if cls.is_translatable(text):
                cleaned = text.strip()
                extracted.append(cleaned)
                if spk_match := _SPEAKER_PREFIX_RE.match(cleaned):
                    body = spk_match.group(1).strip()
                    if cls.is_translatable(body):
                        extracted.append(body)
                offset = end + pad
            else:
                offset += 4
        return extracted

    @classmethod
    def harvest_asset_file(
        cls,
        asset_path: Path | str,
        source_lang: str = "en",
        typetree_generator: Any | None = None,
        stats: HarvestStats | None = None,
    ) -> list[str]:
        """Extract translatable strings from a single serialized file or bundle."""
        path = Path(asset_path)
        if not path.is_file():
            return []
        file_stat = FileStat(path.name)

        import UnityPy

        strings: set[str] = set()
        try:
            env = UnityPy.load(str(path))
            if typetree_generator is not None:
                env.typetree_generator = typetree_generator
            for obj in env.objects:
                if obj.type.name in HARVESTED_TYPES:
                    strings.update(cls.extract_strings_from_object(obj, source_lang, file_stat, stats))
        except Exception as exc:  # UnityPy raises heterogeneous errors on unknown layouts
            logger.warning("Failed to harvest from %s: %s", path.name, exc)
            file_stat.failed = True
        finally:
            env = None
            gc.collect()
        file_stat.strings = len(strings)
        if stats is not None:
            stats.files.append(file_stat)
        logger.debug("Harvested %d unique strings from %s", len(strings), path.name)
        return sorted(strings)

    @classmethod
    def harvest_data_dir(
        cls,
        data_dir: Path | str,
        source_lang: str = "en",
        typetree_generator: Any | None = None,
        progress: ProgressCallback | None = None,
        cancel: CancelToken | None = None,
        stats: HarvestStats | None = None,
    ) -> list[str]:
        """Crawl scenes, shared assets, data.unity3d and bundles; return unique strings.

        Large games ship gigabytes of assets, so progress is reported per file and a
        cancel request is honoured before each one.
        """
        files = find_serialized_sources(data_dir)
        total_strings: set[str] = set()
        for index, path in enumerate(files, start=1):
            checkpoint(cancel)
            emit(progress, "pipeline.harvest_asset_file", index, len(files), name=path.name)
            total_strings.update(cls.harvest_asset_file(path, source_lang, typetree_generator, stats))
        logger.info("Deep asset harvest completed: %d unique strings", len(total_strings))
        return sorted(total_strings)
