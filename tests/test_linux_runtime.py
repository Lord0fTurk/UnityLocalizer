# -*- coding: utf-8 -*-
"""Native Linux support: pinned packages, launcher preparation, hook detection and patch export."""

import os
import zipfile
from pathlib import Path
from typing import Any

import pytest

from src.core.engine_profiler import EngineProfiler
from src.core.hook_layout import runtime_hook_ready
from src.core.hook_manager import installer as installer_module
from src.core.hook_manager.installer import (
    BEPINEX_PACKAGES,
    HookInstaller,
    RuntimeSetupError,
    RuntimeTarget,
    bepinex_package_key,
)
from src.core.hook_manager.runtime_state import read_runtime_marker, write_runtime_marker
from src.core.pipeline.patch_exporter import PatchExporter

SCRIPT = '#!/bin/sh\n# BepInEx start script\nexecutable_name=""\nenabled="1"\n'


def _linux_game(tmp_path: Path) -> Path:
    game = tmp_path / "Game"
    (game / "Game_Data").mkdir(parents=True)
    (game / "Game.x86_64").write_bytes(b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 56)
    (game / "UnityPlayer.so").write_bytes(b"\x7fELF")
    return game


def _fake_package(path: Path, il2cpp: bool = False) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("run_bepinex.sh", SCRIPT)
        zf.writestr("libdoorstop.so", b"\x7fELF")
        zf.writestr(".doorstop_version", "4.5.0")
        zf.writestr("BepInEx/core/BepInEx.dll", b"x")
        if il2cpp:
            zf.writestr("BepInEx/core/BepInEx.Unity.IL2CPP.dll", b"x")
        zf.writestr("BepInEx/plugins/XUnity.AutoTranslator/x.dll", b"x")
    return path


def _extract(archive: Path, game: Path) -> None:
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(game)


def test_profiler_recognizes_a_native_linux_build(tmp_path: Path) -> None:
    profile = EngineProfiler.profile_game(_linux_game(tmp_path))
    assert profile.is_linux_build and not profile.is_windows_build and profile.architecture_certain


def test_windows_build_is_not_a_linux_build(tmp_path: Path) -> None:
    game = tmp_path / "Win"
    (game / "Win_Data").mkdir(parents=True)
    (game / "Win.exe").write_bytes(b"MZ")
    (game / "UnityPlayer.dll").write_bytes(b"MZ")
    assert not EngineProfiler.profile_game(game).is_linux_build


@pytest.mark.parametrize(
    ("is_64bit", "il2cpp", "meta", "key"),
    [
        (True, False, None, "linux_mono_x64"),
        (False, False, None, "linux_mono_x86"),
        (True, True, 29, "linux_il2cpp_x64"),
        (True, True, 31, "linux_il2cpp_modern_x64"),
    ],
)
def test_linux_package_keys_are_pinned(is_64bit: bool, il2cpp: bool, meta: int | None, key: str) -> None:
    assert bepinex_package_key(is_64bit, il2cpp, meta, linux=True) == key
    package = BEPINEX_PACKAGES[key]
    assert "linux" in package.filename and len(package.sha256) == 64


def test_pinned_linux_hashes_match_the_verified_downloads() -> None:
    assert BEPINEX_PACKAGES["linux_mono_x64"].sha256.startswith("e538560b")
    assert BEPINEX_PACKAGES["linux_il2cpp_modern_x64"].sha256.startswith("372023f5")


def test_32bit_il2cpp_on_linux_is_reported_as_unsupported(tmp_path: Path) -> None:
    with pytest.raises(RuntimeSetupError) as caught:
        HookInstaller.ensure_runtime(tmp_path, is_64bit=False, is_il2cpp=True, metadata_version=29, linux=True)
    assert caught.value.reason_key == "installer.reason_unsupported"


def test_linux_install_prepares_the_launcher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    game = _linux_game(tmp_path)
    archive = _fake_package(tmp_path / "bep.zip")
    monkeypatch.setattr(installer_module, "download_cached", lambda *a, **k: archive)
    assert HookInstaller.install(game, is_64bit=True, linux=True, executable_name="Game.x86_64") is True
    assert 'executable_name="Game.x86_64"' in (game / "run_bepinex.sh").read_text(encoding="utf-8")
    if os.name != "nt":
        assert os.access(game / "run_bepinex.sh", os.X_OK)
    assert read_runtime_marker(game)["package"] == "linux_mono_x64"
    assert runtime_hook_ready(game)


def test_windows_package_marker_triggers_reinstall_for_a_linux_game(tmp_path: Path) -> None:
    game = _linux_game(tmp_path)
    _extract(_fake_package(tmp_path / "bep.zip"), game)
    write_runtime_marker(game, "mono_x64", "2021.3.1f1")
    assert HookInstaller.needs_install(game, True, False, None, True)
    assert not HookInstaller.needs_install(game, True, False, None, False)


def test_uninstall_removes_the_linux_launcher_files(tmp_path: Path) -> None:
    game = _linux_game(tmp_path)
    _extract(_fake_package(tmp_path / "bep.zip"), game)
    assert HookInstaller.is_installed(game)
    assert HookInstaller.uninstall(game)
    assert not (game / "run_bepinex.sh").exists() and not (game / "libdoorstop.so").exists()


def test_runtime_target_key_includes_the_platform() -> None:
    assert RuntimeTarget(linux=True).package_key == "linux_mono_x64"
    assert RuntimeTarget().package_key == "mono_x64"


def test_exported_linux_patch_ships_the_launcher_and_chmods_it(tmp_path: Path) -> None:
    game = _linux_game(tmp_path)
    _extract(_fake_package(tmp_path / "bep.zip"), game)
    trans = game / "BepInEx" / "Translation" / "tr" / "Text"
    trans.mkdir(parents=True)
    (trans / "UnityLocalizer.txt").write_text("Hello=Merhaba\n", encoding="utf-8")
    patch = PatchExporter.export_patch(game, target_lang="tr", output_dir=tmp_path / "out")
    assert (patch / "run_bepinex.sh").is_file() and (patch / "libdoorstop.so").is_file()
    script = (patch / "Install_Patch.sh").read_text(encoding="utf-8")
    assert "chmod +x" in script and "./run_bepinex.sh %command%" in script


def test_backend_passes_the_linux_target_to_the_installer(tmp_path: Path, monkeypatch: Any) -> None:
    import src.backend.app_backend as module
    from src.core.progress import CancelToken
    from src.utils.config import ConfigManager

    monkeypatch.setattr(module, "ConfigManager", lambda: ConfigManager(tmp_path / "config.json"))
    backend = module.AppBackend()
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(module.HookInstaller, "needs_install", classmethod(lambda cls, *a, **k: True))
    monkeypatch.setattr(module.HookInstaller, "ensure_runtime", classmethod(lambda cls, *a, **k: calls.append(k) or True))
    backend.selectGame(str(_linux_game(tmp_path)))
    backend._ensure_runtime(CancelToken())
    assert calls[0]["linux"] is True and calls[0]["executable_name"] == "Game.x86_64"
    assert any(n["text"] == "dashboard.linux_native_hint" for n in backend.notices)
