# -*- coding: utf-8 -*-
"""Unit tests for standalone PatchExporter."""

import zipfile
from pathlib import Path

import pytest

from src.core.hook_layout import DICTIONARY_FILE, dictionary_path
from src.core.pipeline.patch_exporter import PatchExporter, PatchNotReadyError, archive_path


def _ready_game(root: Path, name: str = "TestGame", lang: str = "tr") -> Path:
    """A game folder with an installed hook and a translated dictionary."""
    game = root / name
    (game / f"{name}_Data").mkdir(parents=True)
    (game / "winhttp.dll").write_text("mock proxy", encoding="utf-8")
    (game / "BepInEx" / "core").mkdir(parents=True)
    (game / "BepInEx" / "core" / "BepInEx.dll").write_bytes(b"MZ")
    plugin = game / "BepInEx" / "plugins" / "XUnity.AutoTranslator"
    plugin.mkdir(parents=True)
    (plugin / "XUnity.AutoTranslator.Plugin.Core.dll").write_bytes(b"MZ")
    dictionary_path(game, lang).parent.mkdir(parents=True)
    dictionary_path(game, lang).write_text("Hello=Merhaba\n", encoding="utf-8")
    return game


def _shipped(patch_dir: Path) -> set[str]:
    return {p.relative_to(patch_dir).as_posix() for p in patch_dir.rglob("*") if p.is_file()}


def test_export_patch_basic(tmp_path: Path) -> None:
    """Verify basic standalone patch packaging with scripts and payloads."""
    game_dir = _ready_game(tmp_path)
    sa_dir = game_dir / "TestGame_Data" / "StreamingAssets"
    sa_dir.mkdir(parents=True)
    (sa_dir / "dialogue.json").write_text('{"text": "Merhaba"}', encoding="utf-8")
    (sa_dir / "dialogue.json.bak").write_text('{"text": "Hello"}', encoding="utf-8")
    (sa_dir / "untouched.json").write_text('{"text": "Untouched"}', encoding="utf-8")
    (sa_dir / "ignore.bak").write_text("backup", encoding="utf-8")

    patch_dir = PatchExporter.export_patch(game_dir, target_lang="tr", output_dir=tmp_path / "Patches")
    shipped = _shipped(patch_dir)

    assert patch_dir.name == "TestGame_tr_Patch"
    assert {"Yama_Kur.bat", "Install_Patch.bat", "Yama_Kaldir.bat", "Uninstall_Patch.bat", "BENI_OKU.txt"} <= shipped
    assert "winhttp.dll" in shipped
    assert "TestGame_Data/StreamingAssets/dialogue.json" in shipped
    assert "TestGame_Data/StreamingAssets/untouched.json" not in shipped
    assert not any(path.endswith(".bak") for path in shipped)
    assert f"BepInEx/Translation/tr/Text/{DICTIONARY_FILE}" in shipped


def test_export_patch_multilingual(tmp_path: Path) -> None:
    """Verify patch export for non-Turkish target languages (e.g. Spanish)."""
    game_dir = _ready_game(tmp_path, "Solaris", lang="es")
    patch_dir = PatchExporter.export_patch(game_dir, target_lang="es", output_dir=tmp_path / "Patches")

    assert patch_dir.name == "Solaris_es_Patch"
    assert (patch_dir / "BepInEx" / "Translation" / "es" / "Text" / DICTIONARY_FILE).is_file()
    assert "ES" in (patch_dir / "Install_Patch.bat").read_text(encoding="utf-8")


def test_export_is_refused_when_the_patch_could_not_work(tmp_path: Path) -> None:
    bare = tmp_path / "Bare"
    (bare / "Bare_Data").mkdir(parents=True)
    with pytest.raises(PatchNotReadyError) as missing_everything:
        PatchExporter.export_patch(bare, target_lang="tr", output_dir=tmp_path / "out")
    assert missing_everything.value.errors == ["dashboard.patch_no_hook", "dashboard.patch_no_translations"]

    game = _ready_game(tmp_path, lang="tr")
    assert PatchExporter.preflight(game, "de").errors == ["dashboard.patch_no_translations"]
    assert PatchExporter.preflight(game, "tr").errors == []
    assert not (tmp_path / "out").exists() or not any((tmp_path / "out").iterdir())


def test_packaged_config_names_the_exported_language(tmp_path: Path) -> None:
    """The game's INI may still name the language translated last; the patch must not."""
    game = _ready_game(tmp_path, lang="tr")
    config = game / "BepInEx" / "config" / "AutoTranslatorConfig.ini"
    config.parent.mkdir(parents=True)
    config.write_text("[General]\nLanguage=es\nFromLanguage=ja\n[Behaviour]\nMaxCharactersPerTranslation=900\n", encoding="utf-8")

    patch_dir = PatchExporter.export_patch(game, target_lang="tr", source_lang="ja", output_dir=tmp_path / "out")
    packaged = (patch_dir / "BepInEx" / "config" / "AutoTranslatorConfig.ini").read_text(encoding="utf-8-sig")
    assert "Language=tr" in packaged and "Language=es" not in packaged
    assert "FromLanguage=ja" in packaged and "Endpoint=" in packaged
    assert "MaxCharactersPerTranslation=900" in packaged  # translator's tuning travels with the patch
    assert not (patch_dir / "BepInEx" / "config" / "AutoTranslatorConfig.ini.bak").exists()
    assert config.read_text(encoding="utf-8").startswith("[General]\nLanguage=es")  # game copy untouched


def test_export_writes_a_zip_with_the_patch_folder(tmp_path: Path) -> None:
    game = _ready_game(tmp_path)
    patch_dir = PatchExporter.export_patch(game, target_lang="tr", output_dir=tmp_path / "out")
    archive = archive_path(patch_dir)
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
    assert "TestGame_tr_Patch/Install_Patch.bat" in names
    assert f"TestGame_tr_Patch/BepInEx/Translation/tr/Text/{DICTIONARY_FILE}" in names


def test_il2cpp_base_libraries_ship_and_missing_ones_warn(tmp_path: Path) -> None:
    game = _ready_game(tmp_path)
    (game / "BepInEx" / "core" / "BepInEx.Unity.IL2CPP.dll").write_bytes(b"MZ")
    assert PatchExporter.preflight(game, "tr").warnings == ["dashboard.patch_il2cpp_first_run"]

    (game / "BepInEx" / "unity-libs").mkdir()
    (game / "BepInEx" / "unity-libs" / "UnityEngine.CoreModule.dll").write_bytes(b"MZ")
    assert PatchExporter.preflight(game, "tr").warnings == []
    patch_dir = PatchExporter.export_patch(game, target_lang="tr", output_dir=tmp_path / "out")
    assert "BepInEx/unity-libs/UnityEngine.CoreModule.dll" in _shipped(patch_dir)


def test_export_ships_only_patched_files_and_no_backups(tmp_path: Path) -> None:
    game_dir = _ready_game(tmp_path, "Game")
    sa_dir = game_dir / "Game_Data" / "StreamingAssets"
    sa_dir.mkdir(parents=True)
    (sa_dir / "vanilla.json").write_text('{"text": "Hello"}', encoding="utf-8")
    dictionary_path(game_dir, "tr").with_name(f"{DICTIONARY_FILE}.bak").write_text("A=\n", encoding="utf-8")

    shipped = _shipped(PatchExporter.export_patch(game_dir, target_lang="tr", output_dir=tmp_path / "out"))
    assert not any(name.endswith("vanilla.json") for name in shipped)  # untranslated game files never ship
    assert not any(name.endswith(".bak") for name in shipped)


def test_reexport_removes_files_from_previous_export(tmp_path: Path) -> None:
    game_dir = _ready_game(tmp_path, "Game")
    out_root = tmp_path / "out"
    patch_dir = PatchExporter.export_patch(game_dir, target_lang="tr", output_dir=out_root)
    (patch_dir / "stale.txt").write_text("old", encoding="utf-8")
    patch_dir = PatchExporter.export_patch(game_dir, target_lang="tr", output_dir=out_root)
    assert not (patch_dir / "stale.txt").exists()


def test_batch_scripts_use_crlf_and_manifest_subroutines(tmp_path: Path) -> None:
    patch_dir = PatchExporter.export_patch(_ready_game(tmp_path, "Game"), target_lang="tr", output_dir=tmp_path / "out")
    install = (patch_dir / "Install_Patch.bat").read_bytes()
    assert b"\r\n" in install and b"\n" not in install.replace(b"\r\n", b"")
    text = install.decode("utf-8")
    assert "call if" not in text  # CALL cannot run IF: the old backup step silently did nothing
    assert ":install_file" in text and ".ul_orig" in text
    uninstall = (patch_dir / "Uninstall_Patch.bat").read_text(encoding="utf-8")
    assert ":remove_file" in uninstall and "move /Y" in uninstall


def test_export_leaves_out_unrelated_mods(tmp_path: Path) -> None:
    game_dir = _ready_game(tmp_path, "Game")
    plugins = game_dir / "BepInEx" / "plugins"
    (plugins / "SomeCheatMod").mkdir()
    (plugins / "SomeCheatMod" / "Cheat.dll").write_bytes(b"MZ")
    config = game_dir / "BepInEx" / "config"
    config.mkdir(parents=True)
    (config / "AutoTranslatorConfig.ini").write_text("[Service]\n", encoding="utf-8")
    (config / "com.cheat.mod.cfg").write_text("god=true\n", encoding="utf-8")

    shipped = _shipped(PatchExporter.export_patch(game_dir, target_lang="tr", output_dir=tmp_path / "out"))
    assert "BepInEx/plugins/XUnity.AutoTranslator/XUnity.AutoTranslator.Plugin.Core.dll" in shipped
    assert "BepInEx/config/AutoTranslatorConfig.ini" in shipped
    assert not any("cheat" in path.lower() for path in shipped)
