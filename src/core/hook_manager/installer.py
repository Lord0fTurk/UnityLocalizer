# -*- coding: utf-8 -*-
"""BepInEx and runtime hook manager with autonomous downloader and installer."""

from __future__ import annotations

import logging
import shutil
import zipfile
from pathlib import Path

from src.core.hook_layout import PROXY_DLLS, proxy_present, safe_lang_segment
from src.core.hook_manager.font_bootstrap import FontBootstrap
from src.core.hook_manager.font_provisioner import FontProvisioner
from src.core.progress import ProgressCallback, emit
from src.utils.downloader import RemoteFile, download_cached

logger = logging.getLogger(__name__)

_BEPINEX_RELEASES = "https://github.com/BepInEx/BepInEx/releases/download"
_BEPINEX_BE_BUILDS = "https://builds.bepinex.dev/projects/bepinex_be"
_XUNITY_RELEASES = "https://github.com/bbepis/XUnity.AutoTranslator/releases/download"

# Every package is pinned by SHA256: these DLLs are injected into the game, so a
# tampered or truncated download must never be extracted. GitHub release hashes are
# the digests GitHub publishes for the assets; the 6.0.0-pre.2 release and the
# bleeding-edge build predate/lack published digests, so their hashes were computed
# from two independent downloads.
BEPINEX_PACKAGES: dict[str, RemoteFile] = {
    # BepInEx 5 LTS: 5.4.23.5 fixes logging on Unity 6 and Unity 2022.3.62f3.
    "mono_x64": RemoteFile(
        f"{_BEPINEX_RELEASES}/v5.4.23.5/BepInEx_win_x64_5.4.23.5.zip",
        "82f9878551030f54657792c0740d9d51a09500eeae1fba21106b0c441e6732c4",
    ),
    "mono_x86": RemoteFile(
        f"{_BEPINEX_RELEASES}/v5.4.23.5/BepInEx_win_x86_5.4.23.5.zip",
        "37651c79e40d6f909572a4f461ac25350bb3ef8fe7fbd29f1aa8791a33b84c82",
    ),
    # BepInEx 6.0.0-pre.2 reads IL2CPP metadata v23-v29 only.
    "il2cpp_x64": RemoteFile(
        f"{_BEPINEX_RELEASES}/v6.0.0-pre.2/BepInEx-Unity.IL2CPP-win-x64-6.0.0-pre.2.zip",
        "616ec7eb06cf11b2a0000e8fcef04d1b12bb58e84a2e0bdac9523234fc193ceb",
    ),
    "il2cpp_x86": RemoteFile(
        f"{_BEPINEX_RELEASES}/v6.0.0-pre.2/BepInEx-Unity.IL2CPP-win-x86-6.0.0-pre.2.zip",
        "cfef3a1e946dac5db8b9de4de1a922f47584dd775da32863f36762fbaad80f19",
    ),
    # Late Unity 2022.3 and Unity 6 games use metadata v31, which pre.2 rejects at startup.
    # Bleeding-edge build 764 is the build XUnity 5.6.x is reported to translate with on
    # Unity 6 IL2CPP (XUnity.AutoTranslator issue #856).
    "il2cpp_modern_x64": RemoteFile(
        f"{_BEPINEX_BE_BUILDS}/764/BepInEx-Unity.IL2CPP-win-x64-6.0.0-be.764%2B5f39645.zip",
        "5c3792669f7157431ab8c66b52710a61738f51c5cf721a6fc8d04ffcc31f9f72",
    ),
    "il2cpp_modern_x86": RemoteFile(
        f"{_BEPINEX_BE_BUILDS}/764/BepInEx-Unity.IL2CPP-win-x86-6.0.0-be.764%2B5f39645.zip",
        "a448350753a45058b00462987ddb3160b51803a0e6c49b4fe7a051aca907bd4b",
    ),
}

AUTOTRANSLATOR_PACKAGES: dict[str, RemoteFile] = {
    # 5.6.1 fixed TMP font bundle loading on IL2CPP; 5.6 added UIElements support.
    "mono": RemoteFile(
        f"{_XUNITY_RELEASES}/v5.6.2/XUnity.AutoTranslator-BepInEx-5.6.2.zip",
        "836a4066b9369b0d23dc1b0ef6336ad7fe7ae16880931259ec4d157aff7a81c0",
    ),
    "il2cpp": RemoteFile(
        f"{_XUNITY_RELEASES}/v5.6.2/XUnity.AutoTranslator-BepInEx-IL2CPP-5.6.2.zip",
        "639392d3ee3c7542cca98c6c04b384deee4961fe965f3d80a4d9c8413884a0f3",
    ),
}

# Highest IL2CPP metadata version BepInEx 6.0.0-pre.2 can read.
PRE2_MAX_METADATA_VERSION = 29


def bepinex_package_key(is_64bit: bool, is_il2cpp: bool, metadata_version: int | None = None) -> str:
    """Pick the BepInEx build for a game: BepInEx 5 for Mono, BepInEx 6 for IL2CPP.

    IL2CPP games whose metadata version is unknown (encrypted or unreadable) also
    get the bleeding-edge build, whose metadata reader covers the most versions.
    """
    arch = "x64" if is_64bit else "x86"
    if not is_il2cpp:
        return f"mono_{arch}"
    if metadata_version is not None and metadata_version <= PRE2_MAX_METADATA_VERSION:
        return f"il2cpp_{arch}"
    return f"il2cpp_modern_{arch}"


class HookInstaller:
    """Manages BepInEx framework installation, automated deployment, and clean uninstallation."""

    @classmethod
    def is_installed(cls, game_dir: Path | str) -> bool:
        """Check if a BepInEx proxy file exists in game root (something to uninstall)."""
        return proxy_present(game_dir)

    @classmethod
    def uninstall(cls, game_dir: Path | str, full_cleanup: bool = False) -> bool:
        """Cleanly remove BepInEx injection DLLs, restoring game to vanilla state."""
        root = Path(game_dir)
        success = True

        for dll in PROXY_DLLS:
            path = root / dll
            if path.is_file():
                try:
                    path.unlink()
                    logger.info("Removed proxy hook: %s", path.name)
                except Exception as exc:
                    logger.error("Failed to delete %s: %s", path, exc)
                    success = False

        if full_cleanup:
            bep_dir = root / "BepInEx"
            if bep_dir.is_dir():
                try:
                    shutil.rmtree(bep_dir)
                    logger.info("Removed BepInEx folder: %s", bep_dir)
                except Exception as exc:
                    logger.error("Failed to remove BepInEx directory: %s", exc)
                    success = False

        return success

    @classmethod
    def prepare_directories(cls, game_dir: Path | str, target_lang: str = "tr") -> Path:
        """Ensure standard BepInEx Translation directory structure exists."""
        root = Path(game_dir)
        safe_lang = safe_lang_segment(target_lang)
        trans_dir = root / "BepInEx" / "Translation" / safe_lang / "Text"
        trans_dir.mkdir(parents=True, exist_ok=True)
        return trans_dir

    @classmethod
    def _safe_extract_zip(cls, zip_path: Path, dest_dir: Path) -> None:
        """Extract zip archive with Zip Slip (path traversal) security check."""
        dest_resolved = dest_dir.resolve()
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.infolist():
                member_path = (dest_dir / member.filename).resolve()
                if not member_path.is_relative_to(dest_resolved):
                    raise ValueError(f"Zip slip attempt detected for file: {member.filename}")
            zf.extractall(dest_dir)

    @staticmethod
    def _packages(
        is_64bit: bool, is_il2cpp: bool, metadata_version: int | None = None
    ) -> tuple[RemoteFile, RemoteFile]:
        """Return the (BepInEx, AutoTranslator) packages for the game's runtime flavour."""
        bepinex = BEPINEX_PACKAGES[bepinex_package_key(is_64bit, is_il2cpp, metadata_version)]
        return bepinex, AUTOTRANSLATOR_PACKAGES["il2cpp" if is_il2cpp else "mono"]

    @classmethod
    def install(
        cls,
        game_dir: Path | str,
        is_64bit: bool = True,
        is_il2cpp: bool = False,
        target_lang: str = "tr",
        progress_callback: ProgressCallback | None = None,
        unity_version: str = "",
        source_lang: str = "en",
        metadata_version: int | None = None,
    ) -> bool:
        """Download (cached), extract and configure BepInEx, AutoTranslator and TMP font.

        ``metadata_version`` (IL2CPP only) selects a BepInEx 6 build able to read it.
        """
        root = Path(game_dir)
        if not root.is_dir():
            raise NotADirectoryError(f"Target game directory not found: {root}")

        try:
            for package in cls._packages(is_64bit, is_il2cpp, metadata_version):
                archive = download_cached(package, progress=progress_callback)
                emit(progress_callback, "installer.extracting", name=package.filename)
                cls._safe_extract_zip(archive, root)

            emit(progress_callback, "installer.configuring")
            cls.prepare_directories(root, target_lang=target_lang)
            font_bundle = FontProvisioner.provision(root, unity_version, progress_callback) if unity_version else None
            if not FontBootstrap.inject_font(
                root, target_lang=target_lang, source_lang=source_lang, preferred_bundle=font_bundle
            ):
                raise OSError("Failed to write AutoTranslatorConfig.ini")
            emit(progress_callback, "installer.done", 1, 1)
            logger.info("Successfully deployed BepInEx + AutoTranslator to %s", root)
            return True
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            logger.error("Failed to install BepInEx hooks: %s", exc)
            emit(progress_callback, "installer.failed", error=str(exc))
            return False
