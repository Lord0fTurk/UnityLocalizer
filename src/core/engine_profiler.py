# -*- coding: utf-8 -*-
"""Engine diagnostics and Unity game profile analyzer."""

from __future__ import annotations

import logging
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path

from src.core.hook_layout import runtime_hook_ready

logger = logging.getLogger(__name__)

ROUTE_STATIC = "Route 1: Native Static Patcher"
ROUTE_RUNTIME = "Route 3: Runtime Hook (BepInEx)"

# Files a Unity player's <Game>_Data folder contains (any one identifies the build).
_UNITY_DATA_MARKERS: tuple[str, ...] = (
    "globalgamemanagers", "mainData", "data.unity3d", "resources.assets", "level0",
    "sharedassets0.assets", "boot.config", "app.info", "Managed", "il2cpp_data",
)
# Runtime binaries next to the executable (Windows, Linux).
_UNITY_RUNTIME_FILES: tuple[str, ...] = ("UnityPlayer.dll", "GameAssembly.dll", "UnityPlayer.so", "GameAssembly.so")
_EXE_EXCLUDES: tuple[str, ...] = ("crashhandler", "unins", "setup", "redist", "vc_redist", "dxsetup")

_UNITY_VERSION_RE = re.compile(r"\b((?:20\d{2}|[56]\d{3}|5)\.\d+\.\d+[abfp]\d+[a-zA-Z0-9]*)\b")

IL2CPP_METADATA_MAGIC = 0xFAB11BAF
# Metadata versions shipped by Unity 5.3 (v16) up to Unity 6.x (v31-v39 range).
_KNOWN_METADATA_VERSIONS = range(16, 40)
_SCAN_CHUNK = 4 * 1024 * 1024


@dataclass(frozen=True)
class FrameworkSignature:
    """How to recognize a text/narrative framework in a build."""

    name: str
    dll_prefixes: tuple[str, ...]
    markers: tuple[bytes, ...]


FRAMEWORK_SIGNATURES: tuple[FrameworkSignature, ...] = (
    FrameworkSignature("I2 Localization", ("i2.loc", "i2localization"), (b"I2.Loc",)),
    FrameworkSignature("Unity Localization", ("unity.localization",), (b"UnityEngine.Localization",)),
    FrameworkSignature("Naninovel", ("naninovel", "elringus.naninovel"), (b"Naninovel",)),
    FrameworkSignature("Fungus", ("fungus",), (b"Fungus.Say", b"Fungus.Flowchart")),
    FrameworkSignature("Yarn Spinner", ("yarnspinner", "yarn.unity"), (b"YarnSpinner", b"Yarn.Unity")),
    FrameworkSignature("Ink", ("ink-", "ink.runtime", "ink-engine-runtime"), (b"Ink.Runtime",)),
    FrameworkSignature(
        "Dialogue System", ("pixelcrushers.dialoguesystem", "dialoguesystem"),
        (b"PixelCrushers.DialogueSystem",),
    ),
)
_TMP_MARKERS: tuple[bytes, ...] = (b"Unity.TextMeshPro", b"TMPro.TextMeshProUGUI")


def scan_markers(path: Path, markers: tuple[bytes, ...]) -> set[bytes]:
    """Stream a binary file and return which byte markers it contains."""
    found: set[bytes] = set()
    overlap = max((len(m) for m in markers), default=1) - 1
    tail = b""
    try:
        with open(path, "rb") as f:
            while len(found) < len(markers):
                chunk = f.read(_SCAN_CHUNK)
                if not chunk:
                    break
                window = tail + chunk
                found.update(m for m in markers if m not in found and m in window)
                tail = window[-overlap:] if overlap else b""
    except OSError as exc:
        logger.debug("Marker scan failed for %s: %s", path, exc)
    return found


def read_metadata_header(path: Path) -> tuple[int | None, bool]:
    """Return (metadata version, looks_encrypted) for an IL2CPP global-metadata.dat."""
    try:
        with open(path, "rb") as f:
            header = f.read(8)
    except OSError as exc:
        logger.debug("Cannot read %s: %s", path, exc)
        return None, False
    if len(header) < 8:
        return None, True
    magic, version = struct.unpack("<II", header)
    if magic != IL2CPP_METADATA_MAGIC or version not in _KNOWN_METADATA_VERSIONS:
        return None, True
    return version, False


@dataclass
class UnityGameProfile:
    """Diagnostic profile of a target Unity game."""

    game_path: Path
    game_exe: Path | None = None
    data_dir: Path | None = None
    unity_version: str = "Unknown"
    is_64bit: bool = True
    is_il2cpp: bool = False
    has_text_mesh_pro: bool = False
    has_streaming_assets: bool = False
    # True only when proxy DLL, BepInEx core and the XUnity plugin are all in place.
    has_bepinex: bool = False
    # Windows player build (BepInEx/XUnity packages and patch scripts are Windows-only).
    is_windows_build: bool = True
    detected_frameworks: list[str] = field(default_factory=list)
    metadata_version: int | None = None
    metadata_encrypted: bool = False
    available_routes: list[str] = field(default_factory=list)
    recommended_route: str = ROUTE_RUNTIME


class EngineProfiler:
    """Analyzes game directory and determines architecture and localization routes."""

    @classmethod
    def profile_game(cls, target_dir_or_exe: Path | str) -> UnityGameProfile:
        """Analyze a target directory or executable and build a diagnostic profile."""
        path = Path(target_dir_or_exe).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        if path.is_file():
            exe_path = path
            game_dir = path.parent
            data_dir = cls._find_data_dir(game_dir, exe_path)
        elif path.is_dir() and path.name.endswith("_Data"):
            game_dir = path.parent
            exe_path = cls._find_game_exe(game_dir)
            data_dir = path
        else:
            game_dir = path
            exe_path = cls._find_game_exe(game_dir)
            data_dir = cls._find_data_dir(game_dir, exe_path)

        cls._validate_unity_engine(game_dir, data_dir)

        profile = UnityGameProfile(game_path=game_dir, game_exe=exe_path, data_dir=data_dir)
        cls._detect_architecture(profile)
        cls._detect_unity_version(profile)
        cls._detect_frameworks(profile)
        cls._determine_routes(profile)

        logger.info(
            "Profiled: Unity %s | %s %s | Routes: %s",
            profile.unity_version,
            "IL2CPP" if profile.is_il2cpp else "Mono",
            "x64" if profile.is_64bit else "x86",
            ", ".join(profile.available_routes),
        )
        return profile

    @staticmethod
    def _find_game_exe(game_dir: Path) -> Path | None:
        """Locate the game executable: the one owning a ``<stem>_Data`` folder wins.

        Folders often hold launchers or tools next to the game, so the first
        executable is not necessarily the Unity player whose bitness matters.
        Supports both Windows (.exe) and Linux (.x86_64 / .x86 / extensionless).
        """
        # 1. First check matching <stem>_Data directory for precise pair
        for sub in sorted(game_dir.iterdir()):
            if sub.is_dir() and sub.name.endswith("_Data"):
                stem = sub.name[:-5]
                for ext in (".exe", ".x86_64", ".x86", ""):
                    cand = game_dir / f"{stem}{ext}"
                    if cand.is_file() and not any(part in cand.name.lower() for part in _EXE_EXCLUDES):
                        return cand

        # 2. Otherwise scan executables
        found: list[Path] = []
        for pattern in ("*.exe", "*.x86_64", "*.x86"):
            found.extend(game_dir.glob(pattern))
        candidates = [
            exe for exe in sorted(found)
            if not any(part in exe.name.lower() for part in _EXE_EXCLUDES)
        ]
        return candidates[0] if candidates else None

    @staticmethod
    def _find_data_dir(game_dir: Path, exe_path: Path | None) -> Path | None:
        """Find the <GameName>_Data directory."""
        if exe_path:
            candidate = game_dir / f"{exe_path.stem}_Data"
            if candidate.is_dir():
                return candidate

        for sub in game_dir.iterdir():
            if sub.is_dir() and sub.name.endswith("_Data"):
                return sub

        candidate_data = game_dir / "Data"
        if candidate_data.is_dir() and (game_dir / "UnityPlayer.dll").is_file():
            return candidate_data

        return None

    @classmethod
    def _validate_unity_engine(cls, game_dir: Path, data_dir: Path | None) -> None:
        """Validate that target directory contains a genuine Unity game.

        Raises ValueError with an i18n key when non-Unity or unknown engine is detected.
        A positive Unity signature wins first, so a Unity game that happens to have an
        ``Engine`` or ``www`` folder is never misreported as Unreal or RPG Maker.
        """
        if cls._has_unity_signature(game_dir, data_dir):
            return

        if cls._is_unreal_engine(game_dir):
            raise ValueError("profiler.error_unreal_engine")

        if cls._is_renpy_engine(game_dir):
            raise ValueError("profiler.error_renpy_engine")

        if cls._is_rpgm_engine(game_dir):
            raise ValueError("profiler.error_rpgm_engine")

        raise ValueError("profiler.error_not_unity")

    @classmethod
    def _is_unreal_engine(cls, game_dir: Path) -> bool:
        """Check for Unreal Engine 4/5 file structure signatures."""
        if (game_dir / "Engine").is_dir():
            return True
        if list(game_dir.glob("Manifest_NonUFSFiles_*.txt")):
            return True
        if list(game_dir.glob("*-Shipping.exe")):
            return True
        if list(game_dir.glob("*/Content/Paks")):
            return True
        return False

    @classmethod
    def _is_renpy_engine(cls, game_dir: Path) -> bool:
        """Check for Ren'Py file structure signatures."""
        if (game_dir / "renpy").is_dir():
            return True
        game_sub = game_dir / "game"
        if game_sub.is_dir():
            renpy_files = [
                f for f in game_sub.iterdir()
                if f.is_file() and f.suffix.lower() in (".rpy", ".rpyc", ".rpa")
            ]
            if renpy_files:
                return True
        return False

    @classmethod
    def _is_rpgm_engine(cls, game_dir: Path) -> bool:
        """Check for RPG Maker (XP/VX/Ace/MV/MZ) file structure signatures."""
        if (game_dir / "www").is_dir():
            return True
        if list(game_dir.glob("Game.rgss*")):
            return True
        rpgm_data = game_dir / "Data"
        if rpgm_data.is_dir():
            rgss_files = [
                f for f in rpgm_data.iterdir()
                if f.is_file() and f.suffix.lower() in (".rxdata", ".rvdata", ".rvdata2")
            ]
            if rgss_files:
                return True
        return False

    @classmethod
    def _has_unity_signature(cls, game_dir: Path, data_dir: Path | None) -> bool:
        """A ``*_Data`` folder plus a Unity runtime binary or Unity player data inside it.

        A folder merely named ``*_Data`` is not enough: many non-Unity apps use one.
        """
        if data_dir is None or not data_dir.is_dir():
            return False
        if any((game_dir / name).is_file() for name in _UNITY_RUNTIME_FILES):
            return True
        if any(game_dir.glob("UnityCrashHandler*.exe")):
            return True
        return any((data_dir / name).exists() for name in _UNITY_DATA_MARKERS)

    @classmethod
    def _detect_architecture(cls, profile: UnityGameProfile) -> None:
        """Check for IL2CPP vs Mono and 32-bit vs 64-bit."""
        # 1. Check IL2CPP markers
        root = profile.game_path
        has_game_assembly = (root / "GameAssembly.dll").is_file() or (root / "GameAssembly.so").is_file()
        has_il2cpp_dir = (
            profile.data_dir and (profile.data_dir / "il2cpp_data").is_dir()
        )
        profile.is_il2cpp = bool(has_game_assembly or has_il2cpp_dir)
        is_windows_exe = profile.game_exe is not None and profile.game_exe.suffix.lower() == ".exe"
        profile.is_windows_build = bool(
            is_windows_exe or any((root / name).is_file() for name in ("UnityPlayer.dll", "GameAssembly.dll"))
        )

        # 2. Check ELF vs PE header for bitness
        if profile.game_exe and profile.game_exe.is_file():
            try:
                with open(profile.game_exe, "rb") as bf:
                    magic = bf.read(4)
                    if magic == b"\x7fELF":
                        elf_class = bf.read(1)
                        if elf_class:
                            profile.is_64bit = (elf_class[0] == 2)
                            return
            except OSError:
                pass

        # Check PE header for bitness (fall back to UnityPlayer.dll / GameAssembly.dll)
        candidates = [
            b for b in (profile.game_exe, root / "UnityPlayer.dll", root / "GameAssembly.dll")
            if b is not None and b.is_file()
        ]
        for binary in candidates:
            try:
                import pefile

                pe = pefile.PE(str(binary), fast_load=True)
                try:
                    profile.is_64bit = (pe.FILE_HEADER.Machine == 0x8664)
                    break
                finally:
                    pe.close()
            except Exception as exc:
                logger.debug("pefile architecture check error on %s: %s", binary.name, exc)

    @classmethod
    def _detect_unity_version(cls, profile: UnityGameProfile) -> None:
        """Resolve the exact Unity version from PE resources, falling back to globalgamemanagers."""
        for binary in (profile.game_path / "UnityPlayer.dll", profile.game_exe):
            version = cls._version_from_pe(binary) if binary else None
            if version:
                profile.unity_version = version
                return
        if profile.data_dir:
            version = cls._version_from_ggm(profile.data_dir / "globalgamemanagers")
            if version:
                profile.unity_version = version

    @staticmethod
    def _version_from_pe(binary: Path) -> str | None:
        """Read ProductVersion/FileVersion from a PE file's VS_VERSIONINFO resource."""
        if not binary.is_file():
            return None
        import pefile

        try:
            pe = pefile.PE(str(binary), fast_load=True)
            pe.parse_data_directories([pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]])
        except pefile.PEFormatError as exc:
            logger.debug("PE parse failed for %s: %s", binary.name, exc)
            return None
        try:
            for file_info in getattr(pe, "FileInfo", []) or []:
                for entry in file_info:
                    for table in getattr(entry, "StringTable", []):
                        for key in (b"ProductVersion", b"FileVersion"):
                            raw = table.entries.get(key, b"").decode("utf-8", "replace")
                            match = _UNITY_VERSION_RE.search(raw)
                            if match:
                                return match.group(1)
        finally:
            pe.close()
        return None

    @staticmethod
    def _version_from_ggm(ggm: Path) -> str | None:
        """Extract the version string from the serialized file header of globalgamemanagers."""
        if not ggm.is_file():
            return None
        try:
            with open(ggm, "rb") as f:
                chunk = f.read(128)
        except OSError as exc:
            logger.debug("Cannot read %s: %s", ggm, exc)
            return None
        match = re.search(rb"\b((?:20\d{2}|[56]\d{3}|5)\.\d+\.\d+[abfp]\d+[a-zA-Z0-9]*)", chunk)
        return match.group(1).decode("ascii", "replace") if match else None

    @classmethod
    def _detect_frameworks(cls, profile: UnityGameProfile) -> None:
        """Detect TextMeshPro, StreamingAssets, BepInEx and specialized narrative engines."""
        profile.has_bepinex = runtime_hook_ready(profile.game_path)
        if not profile.data_dir:
            return
        profile.has_streaming_assets = cls._has_streaming_text(profile.data_dir / "StreamingAssets")
        if profile.is_il2cpp:
            cls._inspect_il2cpp(profile)
        else:
            cls._inspect_managed(profile)

    @staticmethod
    def _has_streaming_text(sa: Path) -> bool:
        """True when StreamingAssets holds text data beyond 3rd-party hardware/analytics configs."""
        if not sa.is_dir():
            return False
        ignored_patterns = ("lovense", "analytics", "steam", "telemetry", "hardware")
        return any(
            f.is_file()
            and f.suffix.lower() in (".json", ".csv", ".tsv", ".txt", ".xml", ".yarn", ".nani")
            and not any(ig in f.name.lower() for ig in ignored_patterns)
            for f in sa.glob("**/*")
        )

    @staticmethod
    def _all_markers() -> tuple[bytes, ...]:
        return _TMP_MARKERS + tuple(m for sig in FRAMEWORK_SIGNATURES for m in sig.markers)

    @classmethod
    def _apply_markers(cls, profile: UnityGameProfile, found: set[bytes]) -> None:
        """Record TextMeshPro and frameworks whose byte markers were found."""
        if found & set(_TMP_MARKERS):
            profile.has_text_mesh_pro = True
        for sig in FRAMEWORK_SIGNATURES:
            if found & set(sig.markers) and sig.name not in profile.detected_frameworks:
                profile.detected_frameworks.append(sig.name)

    @classmethod
    def _inspect_managed(cls, profile: UnityGameProfile) -> None:
        """Mono: match framework DLL names, then scan game assemblies for namespaces."""
        managed = profile.data_dir / "Managed" if profile.data_dir else None
        if not managed or not managed.is_dir():
            return
        dll_names = [f.name.lower() for f in managed.glob("*.dll")]
        if any(name.startswith(("unity.textmeshpro", "textmeshpro")) for name in dll_names):
            profile.has_text_mesh_pro = True
        for sig in FRAMEWORK_SIGNATURES:
            if any(name.startswith(sig.dll_prefixes) for name in dll_names):
                profile.detected_frameworks.append(sig.name)
        found: set[bytes] = set()
        for assembly in sorted(managed.glob("Assembly-CSharp*.dll")):
            found |= scan_markers(assembly, cls._all_markers())
        cls._apply_markers(profile, found)

    @classmethod
    def _inspect_il2cpp(cls, profile: UnityGameProfile) -> None:
        """IL2CPP: read metadata header (version/encryption) and scan its full string pool."""
        meta_path = profile.data_dir / "il2cpp_data" / "Metadata" / "global-metadata.dat" if profile.data_dir else None
        if not meta_path or not meta_path.is_file():
            return
        profile.metadata_version, profile.metadata_encrypted = read_metadata_header(meta_path)
        if profile.metadata_encrypted:
            logger.warning("global-metadata.dat looks encrypted or obfuscated; static code harvest disabled")
            return
        cls._apply_markers(profile, scan_markers(meta_path, cls._all_markers()))

    @classmethod
    def _determine_routes(cls, profile: UnityGameProfile) -> None:
        """List the delivery routes this game supports and recommend one.

        Only loose StreamingAssets text can be patched in place (Route 1); text from
        scenes, assets, bundles and code is harvested read-only and reaches the game
        through the XUnity dictionary, so the runtime hook (Route 3) is always needed
        and therefore always recommended.
        """
        routes = [ROUTE_STATIC] if profile.has_streaming_assets else []
        routes.append(ROUTE_RUNTIME)
        profile.available_routes = routes
        profile.recommended_route = ROUTE_RUNTIME
