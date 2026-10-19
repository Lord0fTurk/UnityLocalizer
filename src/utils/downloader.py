# -*- coding: utf-8 -*-
"""Cached, integrity-checked downloader for runtime dependencies (BepInEx, XUnity, fonts).

Everything fetched here ends up inside the user's game (injected DLLs, font bundles),
so every file is pinned by SHA256: a cached copy is reused only while its hash
matches, and a fresh download is accepted only after it matches.
"""

from __future__ import annotations

import logging
import os
import threading
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from src.core.progress import ProgressCallback, emit
from src.utils.file_ops import calculate_sha256
from src.utils.paths import get_cache_dir

logger = logging.getLogger(__name__)

_USER_AGENT = "UnityLocalizer (+https://www.gnu.org/licenses/gpl-3.0)"
_CHUNK = 1 << 16
_MAX_DOWNLOAD_BYTES = 250 * 1024 * 1024


class IntegrityError(OSError):
    """A downloaded or cached file does not match its pinned SHA256."""


@dataclass(frozen=True)
class RemoteFile:
    """A downloadable release asset and its expected SHA256 (lowercase hex)."""

    url: str
    sha256: str

    @property
    def filename(self) -> str:
        """Sanitized, URL-decoded last URL segment (``be.764%2B5f39645`` -> ``be.764+5f39645``)."""
        raw = urllib.parse.unquote(self.url.rsplit("/", 1)[-1])
        cleaned = raw.replace("\\", "/").rsplit("/", 1)[-1].strip()
        name = Path(cleaned).name
        if not name or name in (".", ".."):
            raise ValueError(f"Invalid remote filename in URL: {self.url!r}")
        return name


def download_cached(
    remote: RemoteFile, progress: ProgressCallback | None = None, subdir: str = "hooks"
) -> Path:
    """Return a verified local copy of ``remote``, downloading it at most once.

    The download goes to a ``.part`` file that is renamed only after its hash
    matched, so an interrupted or tampered transfer never becomes a cache hit.
    """
    cache_dir = get_cache_dir() / subdir
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / remote.filename
    if target.is_file():
        if calculate_sha256(target) == remote.sha256.lower():
            logger.info("Using cached download: %s", target)
            emit(progress, "download.cached", 1, 1, name=remote.filename)
            return target
        logger.warning("Cached %s failed its checksum; downloading it again", target.name)

    temp = target.with_suffix(target.suffix + f".part_{os.getpid()}_{threading.get_ident()}")
    try:
        _fetch(remote, temp, progress)
        actual = calculate_sha256(temp)
        if actual != remote.sha256.lower():
            raise IntegrityError(
                f"{remote.filename}: SHA256 mismatch (expected {remote.sha256}, got {actual})"
            )
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    emit(progress, "download.done", 1, 1, name=remote.filename)
    return target


def _fetch(remote: RemoteFile, destination: Path, progress: ProgressCallback | None) -> None:
    """Stream ``remote`` into ``destination`` while reporting byte progress."""
    scheme = urllib.parse.urlsplit(remote.url).scheme.lower()
    if scheme != "https":
        raise ValueError(f"Refusing non-HTTPS download URL: {remote.url!r}")
    logger.info("Downloading %s -> %s", remote.url, destination)
    request = urllib.request.Request(remote.url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as resp, open(destination, "wb") as out:
        total = int(resp.headers.get("Content-Length", 0) or 0)
        if total > _MAX_DOWNLOAD_BYTES:
            raise IntegrityError(f"{remote.filename}: Content-Length {total} exceeds safety cap")
        done = 0
        while chunk := resp.read(_CHUNK):
            done += len(chunk)
            if done > _MAX_DOWNLOAD_BYTES:
                raise IntegrityError(f"{remote.filename}: download exceeded {_MAX_DOWNLOAD_BYTES} bytes")
            out.write(chunk)
            emit(progress, "download.progress", done, total, name=remote.filename)
