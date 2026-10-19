# -*- coding: utf-8 -*-
"""Locates every Unity serialized source (assets, scenes, bundles) inside a game."""

from __future__ import annotations

import logging
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
        name = path.name.lower()
        if name.startswith("level") or name.endswith(".assets") or name == "data.unity3d":
            files.append(path)
    return files


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
    logger.info("Located %d serialized sources in %s", len(sources), root.name)
    return sources
