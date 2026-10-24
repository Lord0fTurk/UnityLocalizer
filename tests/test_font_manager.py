# -*- coding: utf-8 -*-
"""Tests for advanced font manager: uGUI override, custom TTF/OTF installation, and presets."""

from pathlib import Path
import pytest

from src.core.hook_layout import AUTOTRANSLATOR_CONFIG
from src.core.hook_manager.font_bootstrap import FontBootstrap


def test_install_custom_font_copies_to_bepinex_fonts(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    fake_font = tmp_path / "retro_pixel.ttf"
    fake_font.write_bytes(b"\x00\x01\x00\x00fontdata")

    rel_path = FontBootstrap.install_custom_font(game_dir, fake_font)
    assert rel_path == "BepInEx/fonts/retro_pixel.ttf"

    installed = game_dir / "BepInEx" / "fonts" / "retro_pixel.ttf"
    assert installed.is_file()
    assert installed.read_bytes() == b"\x00\x01\x00\x00fontdata"


def test_install_custom_font_rejects_invalid_extension(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    bad_font = tmp_path / "not_a_font.txt"
    bad_font.write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported font format"):
        FontBootstrap.install_custom_font(game_dir, bad_font)


def test_install_custom_font_rejects_missing_file(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    missing = tmp_path / "does_not_exist.ttf"

    with pytest.raises(FileNotFoundError):
        FontBootstrap.install_custom_font(game_dir, missing)


def test_inject_font_wires_ugui_override_font(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()

    success = FontBootstrap.inject_font(
        game_dir,
        target_lang="tr",
        override_font="BepInEx/fonts/custom.ttf",
        tmp_override_font="Arial",
    )
    assert success is True

    ini_path = game_dir / AUTOTRANSLATOR_CONFIG
    assert ini_path.is_file()
    content = ini_path.read_text(encoding="utf-8-sig")

    assert "OverrideFont=BepInEx/fonts/custom.ttf" in content
    assert "OverrideFontTextMeshPro=Arial" in content
    assert "Endpoint=" in content
    assert "Language=tr" in content
