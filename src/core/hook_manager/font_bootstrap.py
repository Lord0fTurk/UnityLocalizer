# -*- coding: utf-8 -*-
"""Dynamic font injector and configuration bootstrap."""

from __future__ import annotations

import logging
from pathlib import Path

from src.core.hook_layout import AUTOTRANSLATOR_CONFIG, XUNITY_TEXT_DIRECTORY
from src.core.hook_manager.ini_merge import IniValues, merge_ini
from src.utils.file_ops import safe_write

logger = logging.getLogger(__name__)

# Directories (relative to game root) where TMP font AssetBundles are conventionally placed.
TMP_BUNDLE_DIRS: tuple[str, ...] = ("BepInEx/font", "BepInEx/fonts", ".")

# Written only when missing, so a user's later tuning of these options survives re-runs.
_LAYOUT_SAFE_DEFAULTS: IniValues = {
    "TextFrameworks": {
        "EnableTextMeshPro": "True", "EnableUGUI": "True", "EnableNGUI": "True",
        "EnableTextMesh": "True", "EnableIMGUI": "True",
    },
    "Behaviour": {
        "MaxCharactersPerTranslation": "2500", "IgnoreWhitespaceInDialogue": "True",
        "MinDialogueChars": "2", "ForceUIResizing": "False", "EnableUIResizing": "True",
        "OverrideFont": "", "OverrideFontTextMeshPro": "", "FallbackFontTextMeshPro": "",
        "CopyToClipboard": "False", "EnableTextureTranslation": "False",
        "EnableTextureDumping": "False", "EnableTextureReloading": "False",
    },
}


class FontBootstrap:
    """Configures TMP fallback font bundles and AutoTranslator INI settings."""

    @classmethod
    def inject_font(
        cls,
        game_dir: Path | str,
        target_lang: str = "tr",
        source_lang: str = "en",
        make_backup: bool = True,
        tmp_override_font: str | None = None,
        preferred_bundle: Path | None = None,
    ) -> bool:
        """Wire a detected TMP font bundle into an offline-only AutoTranslatorConfig.ini.

        ``make_backup=False`` is used for exported patch folders, which must not
        ship a ``.bak`` copy of the config. ``tmp_override_font`` (when not None)
        sets XUnity's ``OverrideFontTextMeshPro``: a system font name such as
        ``Arial`` is loaded as a TMP font by XUnity 5.6.2+ (TextMeshPro 3.2+), the
        workaround for IL2CPP builds whose stripped AssetBundle API cannot load the
        fallback bundle; an empty string switches the override off.
        """
        game_path = Path(game_dir)
        if not game_path.is_dir():
            raise NotADirectoryError(f"Game directory not found: {game_path}")

        bundle = cls._resolve_preferred_bundle(game_path, preferred_bundle) or cls.find_tmp_font_bundle(game_path)
        if bundle is None:
            logger.warning(
                "No TMP font AssetBundle found; missing glyphs may render as tofu in TextMeshPro"
            )
        config_path = game_path / AUTOTRANSLATOR_CONFIG
        behaviour: dict[str, str] = {}
        if bundle:
            behaviour["FallbackFontTextMeshPro"] = bundle
        if tmp_override_font is not None:
            behaviour["OverrideFontTextMeshPro"] = tmp_override_font.strip()
        return cls._write_optimized_config(config_path, target_lang, behaviour, source_lang, make_backup)

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
        }
        if behaviour:
            forced["Behaviour"] = dict(behaviour)
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
