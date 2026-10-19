# -*- coding: utf-8 -*-
"""Atomic file operations and backup management."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


def calculate_sha256(file_path: Path | str) -> str:
    """Calculate SHA256 checksum of a file in streaming chunks."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found for checksum: {path}")

    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def backup_path_for(target_path: Path | str) -> Path:
    """Path of the ``.bak`` backup that ``safe_write`` keeps next to a file."""
    target = Path(target_path)
    return target.with_suffix(target.suffix + ".bak")


def pristine_source(target_path: Path | str) -> Path:
    """The untouched original of a file: its first ``.bak`` backup, else the file itself.

    ``safe_write`` backs up a file only once, so the backup holds the game's
    original content even after several patch runs. Reading from it keeps
    re-runs from harvesting (and re-translating) already translated text.
    """
    backup = backup_path_for(target_path)
    return backup if backup.is_file() else Path(target_path)


def _create_backup(target: Path) -> Path:
    """Create a .bak copy of an existing file if not already present."""
    backup_path = backup_path_for(target)
    if backup_path.exists():
        logger.debug("Original backup already exists, preserving: %s", backup_path.name)
        return backup_path

    shutil.copy2(target, backup_path)
    logger.info("Created backup: %s (SHA256: %s)", backup_path.name, calculate_sha256(backup_path))
    return backup_path


def safe_write(
    target_path: Path | str,
    content: str | bytes,
    encoding: str = "utf-8",
    make_backup: bool = True,
) -> bool:
    """Atomically write content to target file using a temporary file."""
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() and make_backup:
        _create_backup(target)

    temp_path = target.with_suffix(target.suffix + f".tmp_{os.getpid()}_{threading.get_ident()}")
    try:
        if isinstance(content, str):
            with open(temp_path, "w", encoding=encoding, newline="\n") as f:
                f.write(content)
        else:
            with open(temp_path, "wb") as f:
                f.write(content)

        os.replace(temp_path, target)
        return True
    except Exception as exc:
        logger.error("Failed atomic write to %s: %s", target, exc)
        try:
            temp_path.unlink(missing_ok=True)
        except OSError as cleanup_exc:
            logger.warning("Could not remove temporary file %s: %s", temp_path, cleanup_exc)
        raise


def restore_backup(target_path: Path | str) -> bool:
    """Restore a file from its .bak backup if present."""
    target = Path(target_path)
    backup_path = backup_path_for(target)
    if not backup_path.is_file():
        logger.warning("No backup found to restore for %s", target)
        return False

    shutil.copy2(backup_path, target)
    logger.info("Restored %s from backup %s", target.name, backup_path.name)
    return True
