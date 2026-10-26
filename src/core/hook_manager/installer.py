# -*- coding: utf-8 -*-
"""BepInEx and runtime hook manager with autonomous downloader and installer."""

from __future__ import annotations

import logging
import os
import shutil
import urllib.error
import zipfile
from dataclasses import dataclass
from pathlib import Path

from src.core.hook_layout import (
    LINUX_LAUNCH_SCRIPT,
    PROXY_DLLS,
    proxy_present,
    runtime_flavor_matches,
    runtime_hook_ready,
    safe_lang_segment,
)
from src.core.hook_manager.font_bootstrap import FontBootstrap
from src.core.hook_manager.font_provisioner import FontProvisioner
from src.core.hook_manager.runtime_state import read_runtime_marker, remove_runtime_marker, write_runtime_marker
from src.core.progress import ProgressCallback, emit
from src.utils.file_ops import safe_write
from src.utils.downloader import IntegrityError, RemoteFile, download_cached

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

# Native Linux builds (SHA256 computed from independent downloads; the BepInEx 5 digests
# match the ones GitHub publishes). BepInEx 6 has no 32-bit Linux IL2CPP build.
_LINUX_BEPINEX_PACKAGES: dict[str, RemoteFile] = {
    "linux_mono_x64": RemoteFile(
        f"{_BEPINEX_RELEASES}/v5.4.23.5/BepInEx_linux_x64_5.4.23.5.zip",
        "e538560be65739f562519ab518a75f9c65b3f57f87457403ae7cde683c12dab7",
    ),
    "linux_mono_x86": RemoteFile(
        f"{_BEPINEX_RELEASES}/v5.4.23.5/BepInEx_linux_x86_5.4.23.5.zip",
        "b4a815b33635921faedeada0df00ba5436b4441d9e16bb13f4bc8c7ad4edde63",
    ),
    "linux_il2cpp_x64": RemoteFile(
        f"{_BEPINEX_RELEASES}/v6.0.0-pre.2/BepInEx-Unity.IL2CPP-linux-x64-6.0.0-pre.2.zip",
        "e63c34e49d080b19f14ece4af799d3d8c27c32cac9c81903af99dd9eea414a0e",
    ),
    "linux_il2cpp_modern_x64": RemoteFile(
        f"{_BEPINEX_BE_BUILDS}/764/BepInEx-Unity.IL2CPP-linux-x64-6.0.0-be.764%2B5f39645.zip",
        "372023f5278326c44b107ef11a27ae2882d69dd2dec498f1c4a7436e08fbd2ad",
    ),
}
BEPINEX_PACKAGES.update(_LINUX_BEPINEX_PACKAGES)

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


def bepinex_package_key(
    is_64bit: bool, is_il2cpp: bool, metadata_version: int | None = None, linux: bool = False
) -> str:
    """Pick the BepInEx build for a game: BepInEx 5 for Mono, BepInEx 6 for IL2CPP.

    IL2CPP games whose metadata version is unknown (encrypted or unreadable) also
    get the bleeding-edge build, whose metadata reader covers the most versions.
    """
    arch = "x64" if is_64bit else "x86"
    if not is_il2cpp:
        key = f"mono_{arch}"
    elif metadata_version is not None and metadata_version <= PRE2_MAX_METADATA_VERSION:
        key = f"il2cpp_{arch}"
    else:
        key = f"il2cpp_modern_{arch}"
    return f"linux_{key}" if linux else key


@dataclass(frozen=True)
class RuntimeTarget:
    """What kind of game the runtime hook is installed into."""

    is_64bit: bool = True
    is_il2cpp: bool = False
    metadata_version: int | None = None
    linux: bool = False
    # Linux only: the game executable written into run_bepinex.sh so it starts without arguments.
    executable_name: str = ""

    @property
    def package_key(self) -> str:
        return bepinex_package_key(self.is_64bit, self.is_il2cpp, self.metadata_version, self.linux)


class RuntimeSetupError(Exception):
    """The runtime hook could not be prepared; ``reason_key`` is an i18n key for the cause."""

    def __init__(self, reason_key: str, detail: str) -> None:
        super().__init__(detail)
        self.reason_key = reason_key
        self.detail = detail


def _failure_reason_key(exc: Exception) -> str:
    """Map an install failure to a plain-language reason (network, integrity, permission, other)."""
    if isinstance(exc, IntegrityError):
        return "installer.reason_integrity"
    if isinstance(exc, PermissionError):
        return "installer.reason_permission"
    if isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError)):
        return "installer.reason_network"
    if isinstance(exc, zipfile.BadZipFile):
        return "installer.reason_integrity"
    return "installer.reason_other"


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
        remove_runtime_marker(root)

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
    def _packages(target: RuntimeTarget) -> tuple[RemoteFile, RemoteFile]:
        """Return the (BepInEx, AutoTranslator) packages for the game's runtime flavour."""
        bepinex = BEPINEX_PACKAGES.get(target.package_key)
        if bepinex is None:
            raise RuntimeSetupError(
                "installer.reason_unsupported", f"No BepInEx package exists for {target.package_key}"
            )
        return bepinex, AUTOTRANSLATOR_PACKAGES["il2cpp" if target.is_il2cpp else "mono"]

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
        linux: bool = False,
        executable_name: str = "",
    ) -> bool:
        """Download (cached), extract and configure BepInEx, AutoTranslator and TMP font.

        ``metadata_version`` (IL2CPP only) selects a BepInEx 6 build able to read it.
        """
        target = RuntimeTarget(is_64bit, is_il2cpp, metadata_version, linux, executable_name)
        try:
            cls._deploy(Path(game_dir), target, target_lang, progress_callback, unity_version, source_lang)
            return True
        except RuntimeSetupError as exc:
            emit(progress_callback, "installer.failed", error=exc.detail)
            return False

    @classmethod
    def needs_install(
        cls,
        game_dir: Path | str,
        is_64bit: bool,
        is_il2cpp: bool,
        metadata_version: int | None = None,
        linux: bool = False,
    ) -> bool:
        """True when the game has no working hook of the right kind.

        A hook with no UnityLocalizer marker (installed by hand, possibly with other
        mods) is kept as long as its BepInEx generation fits the game. A marked install
        is replaced when it was made for a different package (e.g. x86 vs x64).
        """
        root = Path(game_dir)
        if not runtime_hook_ready(root) or not runtime_flavor_matches(root, is_il2cpp):
            return True
        installed = read_runtime_marker(root).get("package")
        return bool(installed) and installed != bepinex_package_key(is_64bit, is_il2cpp, metadata_version, linux)

    @classmethod
    def ensure_runtime(
        cls,
        game_dir: Path | str,
        is_64bit: bool = True,
        is_il2cpp: bool = False,
        target_lang: str = "tr",
        progress_callback: ProgressCallback | None = None,
        unity_version: str = "",
        source_lang: str = "en",
        metadata_version: int | None = None,
        linux: bool = False,
        executable_name: str = "",
    ) -> bool:
        """Install the hook only when needed; return True when something was installed.

        Raises ``RuntimeSetupError`` with a user-presentable reason when it fails.
        """
        if not cls.needs_install(game_dir, is_64bit, is_il2cpp, metadata_version, linux):
            return False
        target = RuntimeTarget(is_64bit, is_il2cpp, metadata_version, linux, executable_name)
        cls._deploy(Path(game_dir), target, target_lang, progress_callback, unity_version, source_lang)
        return True

    @classmethod
    def _deploy(
        cls,
        root: Path,
        target: RuntimeTarget,
        target_lang: str,
        progress_callback: ProgressCallback | None,
        unity_version: str,
        source_lang: str,
    ) -> None:
        """Download, extract and configure the packages; failures become RuntimeSetupError."""
        if not root.is_dir():
            raise NotADirectoryError(f"Target game directory not found: {root}")
        try:
            for package in cls._packages(target):
                archive = download_cached(package, progress=progress_callback)
                emit(progress_callback, "installer.extracting", name=package.filename)
                cls._safe_extract_zip(archive, root)

            emit(progress_callback, "installer.configuring")
            if target.linux:
                cls._prepare_linux_launcher(root, target.executable_name)
            cls.prepare_directories(root, target_lang=target_lang)
            font_bundle = FontProvisioner.provision(root, unity_version, progress_callback) if unity_version else None
            if not FontBootstrap.inject_font(
                root, target_lang=target_lang, source_lang=source_lang, preferred_bundle=font_bundle
            ):
                raise OSError("Failed to write AutoTranslatorConfig.ini")
            write_runtime_marker(root, target.package_key, unity_version)
        except RuntimeSetupError:
            raise
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            logger.error("Failed to install BepInEx hooks: %s", exc)
            raise RuntimeSetupError(_failure_reason_key(exc), str(exc)) from exc
        emit(progress_callback, "installer.done", 1, 1)
        logger.info("Successfully deployed BepInEx + AutoTranslator to %s", root)

    @staticmethod
    def _prepare_linux_launcher(root: Path, executable_name: str) -> None:
        """Make run_bepinex.sh runnable and point it at the game executable.

        Zip extraction drops the executable bit, and the script starts nothing without
        ``executable_name`` unless the game path is passed on the command line.
        """
        script = root / LINUX_LAUNCH_SCRIPT
        if not script.is_file():
            raise OSError(f"{LINUX_LAUNCH_SCRIPT} is missing from the extracted BepInEx package")
        if executable_name:
            lines = script.read_text(encoding="utf-8").split("\n")
            for index, line in enumerate(lines):
                if line.startswith("executable_name="):
                    lines[index] = f'executable_name="{executable_name}"'
                    break
            safe_write(script, "\n".join(lines), make_backup=False)
        os.chmod(script, 0o755)
        library = root / "libdoorstop.so"
        if library.is_file():
            os.chmod(library, 0o755)
