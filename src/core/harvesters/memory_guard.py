# -*- coding: utf-8 -*-
"""Decides whether scanning one asset file fits in the memory that is free right now.

UnityPy unpacks a compressed bundle completely in memory. Measured with a 1 GiB-unpacked bundle,
two real ones and plain serialized files, a scan peaks at about twice the unpacked size for a
bundle and at about the file size for a plain ``.assets``/``level`` file. A file that does not fit
makes the system swap: Windows grows its paging file on the system disk and the whole PC crawls
(a user reported the scan stuck for hours and the system disk full). Such a file is skipped
instead, and the harvest reports it so its text is not silently missing.

A readable UnityFS bundle is not opened whole: only its serialized files are unpacked
(``bundle_unpack``), so it costs twice the largest of those, not twice the bundle. Bundles whose
layout cannot be read (other formats, encryption) are still opened whole and estimated from their size.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from src.core.harvesters.bundle_header import UNITYFS_SIGNATURE, read_layout
from src.core.harvesters.bundle_locator import BUNDLE_MAGICS
from src.core.harvesters.bundle_unpack import peak_unpack_bytes

logger = logging.getLogger(__name__)

PEAK_FACTOR_BUNDLE = 2.0           # measured: an unpacked bundle costs about twice its uncompressed size
PEAK_FACTOR_SERIALIZED = 1.2       # measured 0.7-1.1x the file for plain serialized files
UNKNOWN_COMPRESSION_RATIO = 3.0    # a bundle whose header cannot be read; measured ratios were 1.5-2.6x
DEFAULT_RAM_FRACTION = 0.7         # the rest stays free for the system and other programs
_SPLIT_PART_RE = re.compile(r"^(?P<stem>.+)\.split\d+$", re.IGNORECASE)
_SIZE_UNITS = ("KB", "MB", "GB", "TB")


def format_size(size: int) -> str:
    """Human readable size such as ``3.2 GB`` (units of 1024, like Windows Explorer)."""
    if size < 1024:
        return f"{size} B"
    value = float(size)
    for unit in _SIZE_UNITS:
        value /= 1024
        if value < 1024 or unit == _SIZE_UNITS[-1]:
            return f"{value:.1f} {unit}"
    return f"{size} B"  # pragma: no cover - the loop always returns


def available_memory() -> int | None:
    """Physical memory that can be used right now, in bytes; None when it cannot be determined."""
    try:
        import psutil

        return int(psutil.virtual_memory().available)
    except Exception as exc:  # psutil missing on an exotic platform or a failing OS query
        logger.debug("Available memory is unknown: %s", exc)
        return None


def disk_size(path: Path) -> int:
    """Size of a serialized file on disk; every ``.splitN`` part counts, UnityPy merges them."""
    match = _SPLIT_PART_RE.match(path.name)
    if not match:
        return path.stat().st_size
    parts = path.parent.glob(f"{match['stem']}.split*")
    return sum(part.stat().st_size for part in parts if _SPLIT_PART_RE.match(part.name))


def estimate_peak_bytes(path: Path) -> int:
    """Memory a scan of ``path`` is expected to need at its peak."""
    on_disk = disk_size(path)
    try:
        with open(path, "rb") as f:
            head = f.read(12)
    except OSError as exc:
        logger.debug("Cannot read the header of %s: %s", path, exc)
        return int(on_disk * PEAK_FACTOR_SERIALIZED)
    if not head.startswith(BUNDLE_MAGICS):
        return int(on_disk * PEAK_FACTOR_SERIALIZED)
    layout = read_layout(path) if head.startswith(UNITYFS_SIGNATURE[:-1]) else None
    if layout is not None:
        # The harvest unpacks only the files that can hold text, one at a time (see bundle_unpack).
        return int(peak_unpack_bytes(layout) * PEAK_FACTOR_BUNDLE)
    return int(on_disk * UNKNOWN_COMPRESSION_RATIO * PEAK_FACTOR_BUNDLE)


@dataclass(frozen=True)
class FileAssessment:
    """What scanning one file is expected to cost, and whether it fits."""

    path: Path
    disk_bytes: int
    peak_bytes: int
    available_bytes: int | None
    fits: bool


class MemoryGuard:
    """Compares the expected peak memory of a file scan with the memory that is free."""

    def __init__(
        self,
        enabled: bool = True,
        fraction: float = DEFAULT_RAM_FRACTION,
        available: Callable[[], int | None] = available_memory,
    ) -> None:
        self.enabled = enabled
        self.fraction = fraction
        self._available = available

    def assess(self, path: Path) -> FileAssessment:
        """Expected cost of scanning ``path``; with the guard off every file fits."""
        try:
            on_disk = disk_size(path)
        except OSError as exc:
            logger.debug("Cannot size %s: %s", path, exc)
            return FileAssessment(path, 0, 0, None, True)  # the scan itself reports an unreadable file
        if not self.enabled:
            return FileAssessment(path, on_disk, 0, None, True)
        peak = estimate_peak_bytes(path)
        free = self._available()
        fits = free is None or peak <= self.fraction * free
        return FileAssessment(path, on_disk, peak, free, fits)
