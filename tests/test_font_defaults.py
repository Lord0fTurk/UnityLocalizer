# -*- coding: utf-8 -*-
"""XUnity hook mode and automatic TMP font choice for IL2CPP games."""

from pathlib import Path
from typing import Any

from src.core.hook_layout import AUTOTRANSLATOR_CONFIG
from src.core.hook_manager.font_bootstrap import FontBootstrap


def _ini(game: Path) -> str:
    return (game / AUTOTRANSLATOR_CONFIG).read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def test_monomod_hooks_are_never_forced(tmp_path: Path) -> None:
    """Forcing MonoMod hooks makes every XUnity hook fail under IL2CPP, so it must be off."""
    config = tmp_path / AUTOTRANSLATOR_CONFIG
    config.parent.mkdir(parents=True)
    config.write_text("[Behaviour]\nForceMonoModHooks=True\n", encoding="utf-8")
    FontBootstrap.inject_font(tmp_path, is_il2cpp=True)
    assert "ForceMonoModHooks=False" in _ini(tmp_path)
    assert "ForceMonoModHooks=True" not in _ini(tmp_path)


def test_il2cpp_without_a_chosen_font_gets_a_system_font_as_fallback(tmp_path: Path) -> None:
    FontBootstrap.inject_font(tmp_path, target_lang="tr", tmp_override_font=None, is_il2cpp=True)
    ini = _ini(tmp_path)
    assert "FallbackFontTextMeshPro=Arial" in ini
    assert "OverrideFontTextMeshPro=\n" in ini


def test_empty_setting_means_automatic_not_off(tmp_path: Path) -> None:
    from src.backend.app_backend import AppBackend

    backend: Any = AppBackend()
    try:
        backend.setSetting("tmp_system_font", "   ")
        assert backend._tmp_override_font() is None
        backend.setSetting("tmp_system_font", "Segoe UI")
        assert backend._tmp_override_font() == "Segoe UI"
    finally:
        backend.shutdown()


def test_il2cpp_never_uses_the_override_that_crashed_a_unity6_game(tmp_path: Path) -> None:
    """XUnity's OverrideFontTextMeshPro caused an access violation in a Unity 6000 IL2CPP game;
    a value written by an older run is cleared and the user's font becomes a fallback instead."""
    config = tmp_path / AUTOTRANSLATOR_CONFIG
    config.parent.mkdir(parents=True)
    config.write_text("[Behaviour]\nOverrideFontTextMeshPro=Arial\n", encoding="utf-8")
    FontBootstrap.inject_font(tmp_path, target_lang="tr", tmp_override_font="Segoe UI", is_il2cpp=True)
    ini = _ini(tmp_path)
    assert "OverrideFontTextMeshPro=\n" in ini
    assert "FallbackFontTextMeshPro=Segoe UI" in ini
