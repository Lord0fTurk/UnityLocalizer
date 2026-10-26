# -*- coding: utf-8 -*-
"""Standalone patch exporter packaging offline multilingual patches.

The patch is a folder (plus a ZIP of it) that the player drops into the game's
main folder. It mirrors the game layout, so the scripts from ``patch_scripts``
install and uninstall it file by file. Only what the translation needs ships:
the Doorstop proxy and BepInEx runtime, XUnity's plugins and config, the
dictionary, fonts and the StreamingAssets files the pipeline actually patched.

An export is refused when it could not work on a player's machine: without an
installed hook or without translations for the chosen language.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from src.core.hook_layout import (
    AUTOTRANSLATOR_CONFIG,
    IL2CPP_RUNTIME_MARKER,
    LINUX_LAUNCH_SCRIPT,
    PROXY_DLLS,
    UNITY_BASE_LIBS_DIR,
    XUNITY_PLUGIN_DIRS,
    dictionary_path,
    runtime_hook_ready,
    safe_lang_segment,
)
from src.core.hook_manager.font_bootstrap import FontBootstrap
from src.core.parsers.auto_translator import AutoTranslatorParser
from src.core.pipeline.patch_scripts import write_readme, write_scripts
from src.utils.file_ops import backup_path_for
from src.utils.paths import get_patches_dir

logger = logging.getLogger(__name__)

# Never ship our own backups or interrupted atomic writes.
_IGNORED_PAYLOAD = shutil.ignore_patterns("*.bak", "*.tmp_*")
# BepInEx folders the translation runtime needs: loader, fonts, IL2CPP base libraries
# (downloaded by BepInEx 6 on first launch otherwise) and XUnity's plugins.
# Other mods the user installed (plugins, patchers, their configs) never ship.
_BEPINEX_DIRS: tuple[str, ...] = (
    "core", "font", "fonts", UNITY_BASE_LIBS_DIR.name,
    *(path.relative_to("BepInEx").as_posix() for path in XUNITY_PLUGIN_DIRS),
)
_BEPINEX_CONFIG_FILES: tuple[str, ...] = (AUTOTRANSLATOR_CONFIG.name, "BepInEx.cfg")
# Root-level runtime pieces besides the proxy DLLs (BepInEx 6 IL2CPP ships its own .NET).
_ROOT_RUNTIME_DIRS: tuple[str, ...] = ("dotnet",)
_ROOT_RUNTIME_FILES: tuple[str, ...] = (".doorstop_version",)


@dataclass
class PatchCheck:
    """Preflight result: blocking problems and warnings, both as i18n keys."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class PatchNotReadyError(RuntimeError):
    """The game folder cannot produce a working patch yet (see ``PatchCheck.errors``)."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__(", ".join(errors))
        self.errors = errors


def archive_path(patch_dir: Path) -> Path:
    """The distributable ZIP written next to a patch folder."""
    return patch_dir.parent / f"{patch_dir.name}.zip"


class PatchExporter:
    """Exports self-contained offline patch distributions for any target language."""

    @staticmethod
    def preflight(game_dir: Path | str, target_lang: str) -> PatchCheck:
        """Check that a patch exported now would actually translate the game for players."""
        root = Path(game_dir)
        check = PatchCheck()
        if not runtime_hook_ready(root):
            check.errors.append("dashboard.patch_no_hook")
        if not AutoTranslatorParser().extract_strings(dictionary_path(root, target_lang)):
            check.errors.append("dashboard.patch_no_translations")
        if (root / IL2CPP_RUNTIME_MARKER).is_file() and not (root / UNITY_BASE_LIBS_DIR).is_dir():
            check.warnings.append("dashboard.patch_il2cpp_first_run")
        return check

    @classmethod
    def export_patch(
        cls,
        game_dir: Path | str,
        target_lang: str = "tr",
        output_dir: Path | str | None = None,
        source_lang: str = "en",
    ) -> Path:
        """Build the patch folder and its ZIP from scratch; return the folder.

        Raises PatchNotReadyError when ``preflight`` reports blocking problems.
        The packaged AutoTranslatorConfig.ini is rewritten for ``target_lang``
        (the game's own copy may name whichever language was translated last).
        """
        root = Path(game_dir)
        safe_lang = safe_lang_segment(target_lang)
        check = cls.preflight(root, safe_lang)
        if check.errors:
            raise PatchNotReadyError(check.errors)
        game_name = root.name or "UnityGame"
        out_root = Path(output_dir) if output_dir else get_patches_dir()
        patch_dir = out_root / f"{game_name}_{safe_lang}_Patch"
        if patch_dir.is_dir():
            shutil.rmtree(patch_dir)  # files from an older export must not leak into this one
        patch_dir.mkdir(parents=True)

        cls._copy_streaming_assets(root, patch_dir)
        cls._copy_hook_payload(root, patch_dir, safe_lang)
        is_il2cpp = (root / IL2CPP_RUNTIME_MARKER).is_file()
        FontBootstrap.inject_font(
            patch_dir, target_lang=safe_lang, source_lang=source_lang, make_backup=False, is_il2cpp=is_il2cpp,
            linux=(root / LINUX_LAUNCH_SCRIPT).is_file(),
        )
        write_scripts(patch_dir, safe_lang)
        write_readme(patch_dir, game_name, safe_lang)
        archive = cls._archive(patch_dir)
        logger.info("Exported standalone patch to %s (%s)", patch_dir, archive.name)
        return patch_dir

    @staticmethod
    def _patched_files(sa_dir: Path) -> list[Path]:
        """StreamingAssets files this tool rewrote (they have a ``.bak`` original)."""
        return sorted(
            item for item in sa_dir.rglob("*")
            if item.is_file() and item.suffix != ".bak" and backup_path_for(item).is_file()
        )

    @classmethod
    def _copy_streaming_assets(cls, game_dir: Path, patch_dir: Path) -> None:
        """Copy only the StreamingAssets files the pipeline translated in place."""
        for sa_src in game_dir.glob("*_Data/StreamingAssets"):
            if not sa_src.is_dir():
                continue
            sa_dst = patch_dir / sa_src.relative_to(game_dir)
            for item in cls._patched_files(sa_src):
                dest_file = sa_dst / item.relative_to(sa_src)
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest_file)

    @classmethod
    def _copy_hook_payload(cls, game_dir: Path, patch_dir: Path, target_lang: str) -> None:
        """Copy BepInEx proxies, runtime, offline configs, fonts and the dictionary."""
        for name in (*PROXY_DLLS, *_ROOT_RUNTIME_FILES):
            if (game_dir / name).is_file():
                shutil.copy2(game_dir / name, patch_dir / name)
        for candidate in game_dir.iterdir():
            if candidate.is_file() and "_sdf" in candidate.name.lower() and not candidate.suffix:
                shutil.copy2(candidate, patch_dir / candidate.name)
        for name in _ROOT_RUNTIME_DIRS:
            cls._copy_tree(game_dir / name, patch_dir / name)

        bep_src = game_dir / "BepInEx"
        bep_dst = patch_dir / "BepInEx"
        for sub in (*_BEPINEX_DIRS, f"Translation/{target_lang}", "Translation/fonts"):
            cls._copy_tree(bep_src / sub, bep_dst / sub)
        for name in _BEPINEX_CONFIG_FILES:
            config = bep_src / "config" / name
            if config.is_file():
                (bep_dst / "config").mkdir(parents=True, exist_ok=True)
                shutil.copy2(config, bep_dst / "config" / name)

    @staticmethod
    def _copy_tree(src: Path, dst: Path) -> None:
        """Copy a folder (if present) without backups or temporary files."""
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True, ignore=_IGNORED_PAYLOAD)

    @staticmethod
    def _archive(patch_dir: Path) -> Path:
        """Zip the patch folder (folder included) so it can be shared as one file."""
        archive = archive_path(patch_dir)
        archive.unlink(missing_ok=True)
        shutil.make_archive(str(archive.with_suffix("")), "zip", root_dir=patch_dir.parent, base_dir=patch_dir.name)
        return archive
