# -*- coding: utf-8 -*-
"""One-time copy of legacy in-app user data into the data directory.

Before the data directory existed, config, glossary, translation cache and logs
were written beside the program. On first start they are *copied* (never moved
or overwritten) into the data directory, then a marker file prevents repeats.
The originals stay in place so an older build keeps working.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from src.utils.file_ops import safe_write
from src.utils.paths import get_app_dir, get_data_dir

logger = logging.getLogger(__name__)

MIGRATION_MARKER = ".migrated_v1"
# (legacy path relative to the app dir, destination relative to the data dir)
LEGACY_ITEMS: tuple[tuple[str, str], ...] = (
    ("config.json", "config.json"),
    ("glossary.json", "glossary.json"),
    (".unity_cache", "cache"),
    ("logs", "logs"),
)


def _copy_if_missing(src: str, dst: str) -> str:
    """shutil copy function that never overwrites data already in the new location."""
    if not Path(dst).exists():
        shutil.copy2(src, dst)
    return dst


def _copy_item(source: Path, target: Path) -> bool:
    """Copy one legacy file or directory; True when anything was copied."""
    if not source.exists() or source.resolve() == target.resolve():
        return False
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True, copy_function=_copy_if_missing)
        return True
    if target.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return True


def migrate_legacy_data(app_dir: Path | None = None, data_dir: Path | None = None) -> list[str]:
    """Copy legacy user data once; returns the legacy items that were copied."""
    app_dir = app_dir or get_app_dir()
    data_dir = data_dir or get_data_dir()
    marker = data_dir / MIGRATION_MARKER
    if marker.exists():
        return []
    copied: list[str] = []
    try:
        for legacy, destination in LEGACY_ITEMS:
            if _copy_item(app_dir / legacy, data_dir / destination):
                copied.append(legacy)
    except OSError as exc:
        # No marker: the copy is retried on the next start instead of being lost.
        logger.error("Copying legacy data from %s to %s failed: %s", app_dir, data_dir, exc)
        return copied
    safe_write(marker, f"Legacy data copied from {app_dir}\n", make_backup=False)
    if copied:
        logger.info("Copied legacy user data %s from %s to %s", copied, app_dir, data_dir)
    return copied
