# -*- coding: utf-8 -*-
"""Unit tests for HookInstaller and FontBootstrap."""

from pathlib import Path

from src.core.hook_manager.installer import HookInstaller
from src.core.hook_manager.font_bootstrap import FontBootstrap


def test_hook_installer_detection_and_uninstall(tmp_path: Path) -> None:
    """Verify proxy detection and uninstall cleanup."""
    assert not HookInstaller.is_installed(tmp_path)

    # Simulate installed proxy DLL
    proxy_file = tmp_path / "winhttp.dll"
    proxy_file.write_text("dummy proxy", encoding="utf-8")
    assert HookInstaller.is_installed(tmp_path)

    # Uninstall
    result = HookInstaller.uninstall(tmp_path)
    assert result is True
    assert not proxy_file.exists()
    assert not HookInstaller.is_installed(tmp_path)


def test_hook_installer_prepare_directories(tmp_path: Path) -> None:
    """Verify BepInEx directory structure creation."""
    trans_dir = HookInstaller.prepare_directories(tmp_path, target_lang="tr")
    assert trans_dir.is_dir()
    assert trans_dir.name == "Text"
    assert (tmp_path / "BepInEx" / "Translation" / "tr" / "Text").exists()


def test_font_bootstrap_inject_font(tmp_path: Path) -> None:
    """Without a bundle, config stays offline and never references a fake font."""
    success = FontBootstrap.inject_font(tmp_path, target_lang="tr")
    assert success is True

    ini_file = tmp_path / "BepInEx" / "config" / "AutoTranslatorConfig.ini"
    assert ini_file.is_file()
    content = ini_file.read_text(encoding="utf-8-sig")
    assert "FallbackFontTextMeshPro=\n" in content
    assert "OverrideFont=\n" in content
    assert "Endpoint=\n" in content
    assert "Language=tr" in content
    assert "CacheRegexPatternResults=True" in content
    assert "MinDialogueChars=1" in content
    assert "EnableFairyGUI=True" in content


def test_font_bootstrap_wires_detected_bundle(tmp_path: Path) -> None:
    """A TMP SDF bundle under BepInEx/font is referenced by its game-root-relative path."""
    font_dir = tmp_path / "BepInEx" / "font"
    font_dir.mkdir(parents=True)
    (font_dir / "arialuni_sdf_u2019").write_bytes(b"UnityFS")

    FontBootstrap.inject_font(tmp_path, target_lang="tr")
    content = (tmp_path / "BepInEx" / "config" / "AutoTranslatorConfig.ini").read_text(
        encoding="utf-8-sig"
    )
    assert "FallbackFontTextMeshPro=BepInEx/font/arialuni_sdf_u2019" in content


def test_font_provisioner_version_mapping() -> None:
    """Verify Unity major version maps to the exact matching SDF bundle."""
    from src.core.hook_manager.font_provisioner import FontProvisioner

    assert FontProvisioner.select_bundle("6000.0.23f1") == "arialuni_sdf_u6000"
    assert FontProvisioner.select_bundle("2022.3.16f1") == "arialuni_sdf_u2022"
    assert FontProvisioner.select_bundle("2021.3.4f1") == "arialuni_sdf_u2021"
    assert FontProvisioner.select_bundle("2019.4.40f1") == "arialuni_sdf_u2019"
    assert FontProvisioner.select_bundle("2018.4.36f1") == "arialuni_sdf_u2018"
    assert FontProvisioner.select_bundle("2017.4.3f1") == "arialuni_sdf-u55to2017"
    assert FontProvisioner.select_bundle("5.6.7f1") == "arialuni_sdf-u55to2017"
    assert FontProvisioner.select_bundle("invalid_version") is None
    assert FontProvisioner.select_bundle("") is None



def test_font_bootstrap_keeps_user_options_and_enforces_offline(tmp_path: Path) -> None:
    ini_file = tmp_path / "BepInEx" / "config" / "AutoTranslatorConfig.ini"
    ini_file.parent.mkdir(parents=True)
    ini_file.write_bytes(
        b"[Service]\r\nEndpoint=GoogleTranslate\r\n\r\n"
        b"[Behaviour]\r\n; user tuned this\r\nMaxCharactersPerTranslation=900\r\nEnableUIResizing=False\r\n"
        b"FallbackFontTextMeshPro=BepInEx/font/mine_sdf\r\n\r\n[Custom]\r\nKeep=Me\r\n"
    )

    assert FontBootstrap.inject_font(tmp_path, target_lang="tr", source_lang="ja")
    content = ini_file.read_bytes().decode("utf-8-sig")

    assert "Endpoint=\r\n" in content and "GoogleTranslate" not in content  # always offline
    assert "Language=tr" in content
    assert "CacheRegexPatternResults=True" in content
    assert "MinDialogueChars=1" in content
    assert "EnableFairyGUI=True" in content and "FromLanguage=ja" in content
    assert "MaxCharactersPerTranslation=900" in content and "EnableUIResizing=False" in content
    assert "; user tuned this" in content and "[Custom]\r\nKeep=Me" in content
    assert "FallbackFontTextMeshPro=BepInEx/font/mine_sdf" in content  # no bundle found: user's font kept
    assert "ForceUIResizing=False" in content  # missing defaults are added
    assert content.count("[Behaviour]") == 1


def test_merge_ini_is_idempotent() -> None:
    from src.core.hook_manager.ini_merge import merge_ini

    forced = {"General": {"Language": "tr"}}
    defaults = {"Behaviour": {"ForceUIResizing": "False"}}
    once = merge_ini("", forced, defaults)
    assert merge_ini(once, forced, defaults) == once
    assert once == "[Behaviour]\nForceUIResizing=False\n\n[General]\nLanguage=tr\n"


def test_font_bootstrap_il2cpp_disables_imgui_and_adds_a_system_font_fallback(tmp_path: Path) -> None:
    """IL2CPP builds bypass AssetBundles, disable unsupported IMGUI and add an OS font as TMP fallback."""
    font_dir = tmp_path / "BepInEx" / "font"
    font_dir.mkdir(parents=True)
    (font_dir / "arialuni_sdf_u6000").write_bytes(b"UnityFS")

    assert FontBootstrap.inject_font(tmp_path, target_lang="ru", is_il2cpp=True)
    ini_file = tmp_path / "BepInEx" / "config" / "AutoTranslatorConfig.ini"
    content = ini_file.read_text(encoding="utf-8-sig")

    assert "EnableIMGUI=False" in content
    assert "FallbackFontTextMeshPro=Arial" in content
    assert "OverrideFontTextMeshPro=\n" in content or "OverrideFontTextMeshPro=\r\n" in content
