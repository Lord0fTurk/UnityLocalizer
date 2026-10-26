# -*- coding: utf-8 -*-
"""Locates every Unity serialized source (assets, scenes, bundles) inside a game."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

BUNDLE_MAGICS: tuple[bytes, ...] = (b"UnityFS", b"UnityWeb", b"UnityRaw", b"UnityArchive")

# Large media/audio containers that are never Unity bundles; skipped without opening.
SKIP_SUFFIXES = frozenset({
    ".mp4", ".webm", ".mov", ".avi", ".usm", ".bank", ".wem", ".pck", ".bnk",
    ".ogg", ".wav", ".mp3", ".png", ".jpg", ".jpeg", ".ttf", ".otf", ".dll",
    ".json", ".csv", ".tsv", ".txt", ".xml", ".yarn", ".nani", ".bak", ".resS", ".ress",
    ".resource",
})


# Bundles shipped outside StreamingAssets (custom loaders, DLC folders next to the game).
BUNDLE_SUFFIXES = frozenset({".bundle", ".unity3d", ".assetbundle", ".ab"})
# Folders that never hold game bundles; pruned so a large install is not walked in full.
_NON_BUNDLE_DIRS = frozenset({
    "streamingassets", "managed", "mono", "monobleedingedge", "il2cpp_data", "plugins", "bepinex",
    "patches", "__pycache__", ".git",
})
_SPLIT_PART_RE = re.compile(r"\.split(\d+)$", re.IGNORECASE)
# Unity 4/5 players keep the main serialized file in ``mainData``.
_PLAYER_FILE_NAMES = frozenset({"data.unity3d", "maindata"})


def has_bundle_magic(path: Path) -> bool:
    """Return True when the file starts with a UnityFS/UnityWeb/UnityRaw signature."""
    try:
        with open(path, "rb") as f:
            head = f.read(12)
    except OSError as exc:
        logger.debug("Cannot read header of %s: %s", path, exc)
        return False
    return head.startswith(BUNDLE_MAGICS)


def _player_files(data_dir: Path) -> list[Path]:
    """Serialized files shipped directly in <Game>_Data (scenes, shared assets, data.unity3d)."""
    files: list[Path] = []
    for path in sorted(data_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() in SKIP_SUFFIXES:
            continue
        split = _SPLIT_PART_RE.search(path.name)
        if split and split.group(1) != "0":
            continue  # UnityPy merges every part when it is given the first one
        name = _SPLIT_PART_RE.sub("", path.name).lower()
        if name.startswith("level") or name.endswith(".assets") or name in _PLAYER_FILE_NAMES:
            files.append(path)
    return files


def _walk_bundles(root: Path, skip: Path | None = None) -> list[Path]:
    """Bundle files below ``root``, pruning folders that cannot hold game bundles."""
    found: list[Path] = []
    for current, dirs, names in os.walk(root):
        here = Path(current)
        dirs[:] = sorted(d for d in dirs if d.lower() not in _NON_BUNDLE_DIRS and (here / d) != skip)
        for name in sorted(names):
            path = here / name
            if path.suffix.lower() in BUNDLE_SUFFIXES and has_bundle_magic(path):
                found.append(path)
    return found


def _extra_bundles(data_dir: Path) -> list[Path]:
    """Bundles in other game folders (inside ``<Game>_Data`` or next to the executable)."""
    return _walk_bundles(data_dir) + _walk_bundles(data_dir.parent, skip=data_dir)


def _streaming_bundles(data_dir: Path) -> list[Path]:
    """AssetBundles/Addressables under StreamingAssets, detected by magic header."""
    sa_dir = data_dir / "StreamingAssets"
    if not sa_dir.is_dir():
        return []
    return [
        path
        for path in sorted(sa_dir.rglob("*"))
        if path.is_file() and path.suffix.lower() not in SKIP_SUFFIXES and has_bundle_magic(path)
    ]


def find_serialized_sources(data_dir: Path | str) -> list[Path]:
    """Return all scene, asset and bundle files worth scanning for text."""
    root = Path(data_dir)
    if not root.is_dir():
        return []
    sources = _player_files(root) + _streaming_bundles(root)
    known = {path.resolve() for path in sources}
    for extra in _extra_bundles(root):
        if extra.resolve() not in known:
            known.add(extra.resolve())
            sources.append(extra)
    logger.info("Located %d serialized sources in %s", len(sources), root.name)
    return sources
