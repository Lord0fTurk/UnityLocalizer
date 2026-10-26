# -*- coding: utf-8 -*-
"""Dynamic font injector and configuration bootstrap."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from src.core.hook_layout import AUTOTRANSLATOR_CONFIG, XUNITY_TEXT_DIRECTORY
from src.core.hook_manager.ini_merge import IniValues, merge_ini
from src.utils.file_ops import safe_write

logger = logging.getLogger(__name__)

# Directories (relative to game root) where TMP font AssetBundles are conventionally placed.
TMP_BUNDLE_DIRS: tuple[str, ...] = ("BepInEx/font", "BepInEx/fonts", ".")

# Reliable OS TrueType fonts for IL2CPP builds whose stripped runtime cannot load AssetBundles.
DEFAULT_IL2CPP_SYSTEM_FONTS: dict[str, str] = {
    "zh": "SimHei",
    "ja": "Meiryo",
    "ko": "Malgun Gothic",
    "ar": "Segoe UI",
    "fa": "Segoe UI",
    "he": "Segoe UI",
    "ru": "Arial",
    "uk": "Arial",
    "be": "Arial",
    "tr": "Arial",
}
FALLBACK_IL2CPP_SYSTEM_FONT: str = "Arial"

# Written only when missing, so a user's later tuning of these options survives re-runs.
_LAYOUT_SAFE_DEFAULTS: IniValues = {
    "TextFrameworks": {
        "EnableTextMeshPro": "True", "EnableUGUI": "True", "EnableNGUI": "True",
        "EnableTextMesh": "True", "EnableIMGUI": "True", "EnableFairyGUI": "True",
    },
    "Behaviour": {
        "MaxCharactersPerTranslation": "2500", "IgnoreWhitespaceInDialogue": "True",
        "MinDialogueChars": "1", "ForceUIResizing": "False", "EnableUIResizing": "True",
        "CacheRegexPatternResults": "True",
        "OverrideFont": "", "OverrideFontTextMeshPro": "", "FallbackFontTextMeshPro": "",
        "CopyToClipboard": "False", "EnableTextureTranslation": "False",
        "EnableTextureDumping": "False", "EnableTextureReloading": "False",
        "EnableTranslationScoping": "False", "IgnoreVirtualTextSetterCallingRules": "True",
        "ForceMonoModHooks": "False",
    },
}


class FontBootstrap:
    """Configures TMP fallback font bundles and AutoTranslator INI settings."""

    @classmethod
    def install_custom_font(cls, game_dir: Path | str, font_path: Path | str) -> str:
        """Copy a user-provided .ttf/.otf font into BepInEx/fonts/ and return relative path.

        Raises FileNotFoundError if font does not exist, or ValueError if not a font file.
        """
        source = Path(font_path)
        if not source.is_file():
            raise FileNotFoundError(f"Font file not found: {source}")
        if source.suffix.lower() not in {".ttf", ".otf"}:
            raise ValueError(f"Unsupported font format {source.suffix}; expected .ttf or .otf")

        target_dir = Path(game_dir) / "BepInEx" / "fonts"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / source.name
        shutil.copy2(source, target_file)
        logger.info("Installed custom font %s to %s", source.name, target_file)
        return f"BepInEx/fonts/{source.name}"

    @classmethod
    def inject_font(
        cls,
        game_dir: Path | str,
        target_lang: str = "tr",
        source_lang: str = "en",
        make_backup: bool = True,
        tmp_override_font: str | None = None,
        preferred_bundle: Path | None = None,
        override_font: str | None = None,
        is_il2cpp: bool = False,
    ) -> bool:
        """Wire a detected TMP font bundle into an offline-only AutoTranslatorConfig.ini.

        ``make_backup=False`` is used for exported patch folders, which must not
        ship a ``.bak`` copy of the config. ``tmp_override_font`` is a system font name
        such as ``Arial``. For IL2CPP builds (whose stripped AssetBundle API cannot load the
        fallback bundle) it becomes XUnity's ``FallbackFontTextMeshPro`` (extra glyphs only,
        chosen automatically per language when None) and ``OverrideFontTextMeshPro`` stays
        empty; otherwise it sets ``OverrideFontTextMeshPro`` (an empty string switches it off).
        ``override_font`` sets XUnity's ``OverrideFont`` (uGUI / UnityEngine.UI.Text).
        """
        game_path = Path(game_dir)
        if not game_path.is_dir():
            raise NotADirectoryError(f"Game directory not found: {game_path}")

        config_path = game_path / AUTOTRANSLATOR_CONFIG
        behaviour: dict[str, str] = {}
        base_target = target_lang.split("-")[0].lower()
        if is_il2cpp:
            # AssetBundle loading is stripped in IL2CPP runtime, so the fallback is an OS font. It is added
            # as a *fallback* (extra glyphs only): XUnity's OverrideFontTextMeshPro swaps the material of
            # every text and crashed a Unity 6000 game (access violation in TMP_Text.set_fontSharedMaterial).
            if tmp_override_font is None:
                tmp_override_font = DEFAULT_IL2CPP_SYSTEM_FONTS.get(base_target, FALLBACK_IL2CPP_SYSTEM_FONT)
            behaviour["FallbackFontTextMeshPro"] = tmp_override_font.strip()
            behaviour["OverrideFontTextMeshPro"] = ""
            tmp_override_font = None
        else:
            bundle = cls._resolve_preferred_bundle(game_path, preferred_bundle) or cls.find_tmp_font_bundle(game_path)
            if bundle:
                behaviour["FallbackFontTextMeshPro"] = bundle
            elif tmp_override_font is None:
                logger.warning(
                    "No TMP font AssetBundle found; missing glyphs may render as tofu in TextMeshPro"
                )

        if tmp_override_font is not None:
            behaviour["OverrideFontTextMeshPro"] = tmp_override_font.strip()
        if override_font is not None:
            behaviour["OverrideFont"] = override_font.strip()
        return cls._write_optimized_config(
            config_path, target_lang, behaviour, source_lang, make_backup, is_il2cpp=is_il2cpp
        )

    @staticmethod
    def _resolve_preferred_bundle(game_path: Path, preferred_bundle: Path | None) -> str | None:
        """Return game-root-relative POSIX path for ``preferred_bundle`` if it sits inside ``game_path``."""
        if preferred_bundle is None or not preferred_bundle.is_file():
            return None
        try:
            return preferred_bundle.resolve().relative_to(game_path.resolve()).as_posix()
        except ValueError:
            return None

    @staticmethod
    def find_tmp_font_bundle(game_path: Path) -> str | None:
        """Return the game-root-relative path of the first TMP SDF font bundle, if any.

        XUnity resolves ``FallbackFontTextMeshPro`` via ``Path.Combine(GameRoot, value)``
        and loads it with ``AssetBundle.LoadFromFile``, so the value must be a real file.
        """
        for rel_dir in TMP_BUNDLE_DIRS:
            directory = game_path / rel_dir
            if not directory.is_dir():
                continue
            for candidate in sorted(directory.iterdir()):
                if candidate.is_file() and "_sdf" in candidate.name.lower() and not candidate.suffix:
                    return candidate.relative_to(game_path).as_posix()
        return None

    @classmethod
    def _write_optimized_config(
        cls,
        config_path: Path,
        target_lang: str,
        behaviour: dict[str, str] | None = None,
        source_lang: str = "en",
        make_backup: bool = True,
        is_il2cpp: bool = False,
    ) -> bool:
        """Merge the offline settings into AutoTranslatorConfig.ini, keeping the user's other options.

        The offline endpoint, languages and dictionary paths are always enforced;
        ``behaviour`` keys (fallback font only when a bundle was found, so a font
        the user wired manually is not cleared when ours is missing) as given.
        """
        config_path.parent.mkdir(parents=True, exist_ok=True)
        forced: IniValues = {
            "Service": {"Endpoint": "", "FallbackEndpoint": ""},
            "General": {"Language": target_lang, "FromLanguage": source_lang},
            # XUnity loads every *.txt below Directory, so it must be per language;
            # "Translation" alone would mix the dictionaries of all target languages.
            "Files": {
                "Directory": XUNITY_TEXT_DIRECTORY,
                "OutputFile": rf"{XUNITY_TEXT_DIRECTORY}\_AutoGeneratedTranslations.txt",
                "SubstitutionFile": rf"{XUNITY_TEXT_DIRECTORY}\_Substitutions.txt",
            },
            "Behaviour": {
                "EnableTranslationScoping": "False",
                "IgnoreVirtualTextSetterCallingRules": "True",
                # XUnity's TMP/UGUI hooks exist as Harmony hooks only under IL2CPP; forcing MonoMod
                # there makes every hook fail ("Harmony is not supported in this runtime").
                "ForceMonoModHooks": "False",
            },
        }
        if is_il2cpp:
            # IMGUI hooks are not implemented in IL2CPP XUnity and trigger NotImplementedException.
            forced["TextFrameworks"] = {"EnableIMGUI": "False"}
        if behaviour:
            forced["Behaviour"].update(behaviour)
        try:
            # Bytes, not read_text(): universal newlines would silently turn the file's CRLF into LF.
            existing = config_path.read_bytes().decode("utf-8-sig") if config_path.is_file() else ""
            ini_content = merge_ini(existing, forced, _LAYOUT_SAFE_DEFAULTS)
            safe_write(config_path, ini_content, encoding="utf-8-sig", make_backup=make_backup)
            logger.info("Updated AutoTranslatorConfig.ini at %s", config_path)
            return True
        except Exception as exc:
            logger.error("Failed to write AutoTranslatorConfig.ini: %s", exc)
            return False
