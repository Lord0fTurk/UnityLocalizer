# -*- coding: utf-8 -*-
"""Provisions a Unity-version-matched TextMeshPro fallback font AssetBundle.

Uses the prebuilt ArialUnicode SDF bundles published with XUnity.AutoTranslator
(MIT licensed, GPL-3.0 compatible). TMP font assets only load when built with a
matching Unity/TMP major version, hence the per-version selection.
"""

from __future__ import annotations

import logging
import re
import shutil
import tempfile
from pathlib import Path

from py7zr.exceptions import ArchiveError

from src.core.progress import ProgressCallback, emit
from src.utils.downloader import RemoteFile, download_cached

logger = logging.getLogger(__name__)

# SHA256 is the digest GitHub publishes for this asset; XUnity still points to these
# bundles (attached to the 5.5.0 release) as the latest TMP_Font_AssetBundles in 5.6.x.
FONT_ARCHIVE = RemoteFile(
    "https://github.com/bbepis/XUnity.AutoTranslator/releases/download/v5.5.0/"
    "TMP_Font_AssetBundles_2025-12-08.7z",
    "889e963fb9dbd4b64927e0adf5d9060e1d0fb9d6bceb0c407d0597643e2b54ec",
)
FONT_TARGET_DIR = Path("BepInEx") / "font"

# (minimum Unity major version, bundle file name), checked from newest to oldest.
_BUNDLES_BY_VERSION: tuple[tuple[int, str], ...] = (
    (6000, "arialuni_sdf_u6000"),
    (2022, "arialuni_sdf_u2022"),
    (2021, "arialuni_sdf_u2021"),
    (2019, "arialuni_sdf_u2019"),
    (2018, "arialuni_sdf_u2018"),
    (0, "arialuni_sdf-u55to2017"),
)
_MAJOR_RE = re.compile(r"^(\d{1,4})\.")


class FontProvisioner:
    """Selects, fetches (build-time only) and deploys the matching TMP font bundle."""

    @staticmethod
    def select_bundle(unity_version: str) -> str | None:
        """Map a Unity version string (e.g. '2021.3.16f1', '6000.0.23f1') to a bundle name."""
        match = _MAJOR_RE.match(unity_version.strip())
        if not match:
            return None
        major = int(match.group(1))
        for minimum, bundle in _BUNDLES_BY_VERSION:
            if major >= minimum:
                return bundle
        return None

    @classmethod
    def provision(
        cls, game_dir: Path, unity_version: str, progress: ProgressCallback | None = None
    ) -> Path | None:
        """Ensure the matching bundle exists under BepInEx/font and return its path."""
        bundle = cls.select_bundle(unity_version)
        if bundle is None:
            logger.warning("Unknown Unity version %r; skipping TMP font provisioning", unity_version)
            emit(progress, "font.version_unknown")
            return None
        target = game_dir / FONT_TARGET_DIR / bundle
        if target.is_file():
            return target
        emit(progress, "font.provisioning", name=bundle)
        try:
            archive = download_cached(FONT_ARCHIVE, progress, subdir="fonts")
            cls._extract_member(archive, bundle, target)
        except (OSError, ArchiveError) as exc:
            logger.warning("TMP font provisioning failed: %s", exc)
            emit(progress, "font.failed", error=str(exc))
            return None
        emit(progress, "font.provisioned", name=bundle)
        return target

    @staticmethod
    def _extract_member(archive: Path, member: str, target: Path) -> None:
        """Extract a single member from the 7z archive into target."""
        import py7zr

        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ul_font_") as tmp:
            with py7zr.SevenZipFile(archive, mode="r") as zf:
                zf.extract(path=tmp, targets=[member])
            extracted = Path(tmp) / member
            if not extracted.is_file():
                raise FileNotFoundError(f"{member} not found inside {archive.name}")
            shutil.move(str(extracted), target)
        logger.info("Deployed TMP fallback font bundle: %s", target)
