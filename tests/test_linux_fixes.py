# -*- coding: utf-8 -*-
"""Linux fixes: starting the game, system fonts, patch scripts that report failures, clean uninstall."""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from src.core.engine_profiler import EngineProfiler
from src.core.game_launcher import REASON_WINDOWS_GAME_ON_LINUX, LaunchError, launch_command
from src.core.hook_layout import AUTOTRANSLATOR_CONFIG, RUNTIME_MARKER
from src.core.hook_manager.font_bootstrap import FontBootstrap
from src.core.hook_manager.installer import HookInstaller
from src.core.hook_manager.runtime_state import write_runtime_marker
from src.core.hook_manager.system_fonts import default_system_font
from src.core.pipeline.patch_scripts import write_scripts

ELF = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 56


def _linux_game(root: Path) -> Path:
    (root / "Game_Data").mkdir(parents=True)
    (root / "Game.x86_64").write_bytes(ELF)
    (root / "UnityPlayer.so").write_bytes(b"\x7fELF")
    return root


def _windows_game(root: Path) -> Path:
    (root / "Win_Data").mkdir(parents=True)
    (root / "Win.exe").write_bytes(b"MZ")
    (root / "UnityPlayer.dll").write_bytes(b"MZ")
    return root


# --- starting the game --------------------------------------------------------------


def test_windows_host_starts_the_exe_directly(tmp_path: Path) -> None:
    profile = EngineProfiler.profile_game(_windows_game(tmp_path / "win"))
    command = launch_command(profile, host="win32")
    assert command.argv == [str(profile.game_exe)] and command.cwd == profile.game_exe.parent


def test_native_linux_game_with_the_hook_starts_through_run_bepinex(tmp_path: Path) -> None:
    game = _linux_game(tmp_path / "linux")
    (game / "run_bepinex.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    command = launch_command(EngineProfiler.profile_game(game), host="linux")
    assert command.argv == ["/bin/sh", str(game / "run_bepinex.sh")] and command.cwd == game


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no executable bit")
def test_native_linux_game_without_the_hook_needs_an_executable_file(tmp_path: Path) -> None:
    game = _linux_game(tmp_path / "linux")
    profile = EngineProfiler.profile_game(game)
    with pytest.raises(LaunchError) as caught:
        launch_command(profile, host="linux")
    assert caught.value.reason_key == "dashboard.launch_not_executable"
    (game / "Game.x86_64").chmod(0o755)
    assert launch_command(profile, host="linux").argv == [str(game / "Game.x86_64")]


def test_a_windows_game_cannot_be_started_on_linux(tmp_path: Path) -> None:
    profile = EngineProfiler.profile_game(_windows_game(tmp_path / "win"))
    with pytest.raises(LaunchError) as caught:
        launch_command(profile, host="linux")
    assert caught.value.reason_key == REASON_WINDOWS_GAME_ON_LINUX


# --- system fonts --------------------------------------------------------------------


def test_windows_font_names_are_unchanged() -> None:
    assert default_system_font("tr") == "Arial" and default_system_font("ja") == "Meiryo"
    assert default_system_font("zh-CN") == "SimHei"


def test_linux_font_follows_what_is_installed() -> None:
    installed = {"liberation sans", "noto sans cjk jp"}
    assert default_system_font("tr", linux=True, installed=installed) == "Liberation Sans"
    assert default_system_font("ja", linux=True, installed=installed) == "Noto Sans CJK JP"
    assert default_system_font("tr", linux=True, installed={"dejavu sans"}) == "DejaVu Sans"


def test_linux_font_without_a_font_list_uses_the_first_candidate() -> None:
    assert default_system_font("tr", linux=True, installed=set()) == "DejaVu Sans"
    assert default_system_font("ko", linux=True, installed=set()) == "Noto Sans CJK KR"
    assert default_system_font("ar", linux=True, installed=set()) == "DejaVu Sans"


def test_il2cpp_linux_config_gets_a_linux_fallback_font(tmp_path: Path) -> None:
    FontBootstrap.inject_font(tmp_path, target_lang="tr", is_il2cpp=True, linux=True)
    ini = (tmp_path / AUTOTRANSLATOR_CONFIG).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    assert "FallbackFontTextMeshPro=Arial" not in ini
    fallback = [line for line in ini.split("\n") if line.startswith("FallbackFontTextMeshPro=")][0]
    assert fallback.split("=", 1)[1] in {"DejaVu Sans", "Liberation Sans", "Noto Sans", "FreeSans"}


# --- patch scripts ---------------------------------------------------------------------

SH = shutil.which("sh")


def _patch_and_game(tmp_path: Path) -> tuple[Path, Path]:
    game = tmp_path / "Game"
    (game / "Game_Data").mkdir(parents=True)
    patch = game / "Game_tr_Patch"
    (patch / "BepInEx" / "Translation").mkdir(parents=True)
    (patch / "BepInEx" / "Translation" / "dict.txt").write_text("a=b\n", encoding="utf-8")
    (patch / "winhttp.dll").write_bytes(b"dll")
    write_scripts(patch, "tr")
    return game, patch


def _run(script: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([SH, script.name], cwd=script.parent, capture_output=True, text=True, timeout=60, check=False)


@pytest.mark.skipif(SH is None, reason="no POSIX shell available")
def test_install_and_uninstall_scripts_round_trip(tmp_path: Path) -> None:
    game, patch = _patch_and_game(tmp_path)
    (game / "winhttp.dll").write_bytes(b"original")
    installed = _run(patch / "Install_Patch.sh")
    assert installed.returncode == 0, installed.stdout + installed.stderr
    assert (game / "BepInEx" / "Translation" / "dict.txt").read_text(encoding="utf-8") == "a=b\n"
    assert (game / "winhttp.dll").read_bytes() == b"dll" and (game / "winhttp.dll.ul_orig").read_bytes() == b"original"

    restored = _run(patch / "Uninstall_Patch.sh")
    assert restored.returncode == 0, restored.stdout + restored.stderr
    assert (game / "winhttp.dll").read_bytes() == b"original"
    assert not (game / "BepInEx" / "Translation" / "dict.txt").exists()


@pytest.mark.skipif(SH is None, reason="no POSIX shell available")
def test_install_script_fails_loudly_when_a_file_cannot_be_installed(tmp_path: Path) -> None:
    game, patch = _patch_and_game(tmp_path)
    (game / "BepInEx").write_text("a file where the folder should be", encoding="utf-8")
    result = _run(patch / "Install_Patch.sh")
    assert result.returncode != 0
    assert "[ERROR]" in result.stdout and "could not be installed" in result.stdout
    assert "[SUCCESS]" not in result.stdout


# --- uninstall leaves nothing of the install behind -----------------------------------


def test_extract_skips_changelog_and_reports_top_level_names(tmp_path: Path) -> None:
    archive = tmp_path / "pkg.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("changelog.txt", "BepInEx changelog")
        zf.writestr(".doorstop_version", "4.5.0")
        zf.writestr("dotnet/libcoreclr.so", b"x")
        zf.writestr("BepInEx/core/a.dll", b"x")
    game = tmp_path / "game"
    game.mkdir()
    (game / "changelog.txt").write_text("the game's own changelog", encoding="utf-8")
    names = HookInstaller._safe_extract_zip(archive, game)
    assert names == [".doorstop_version", "BepInEx", "dotnet"]
    assert (game / "changelog.txt").read_text(encoding="utf-8") == "the game's own changelog"


def test_uninstall_removes_what_the_marker_lists_and_nothing_else(tmp_path: Path) -> None:
    (tmp_path / "dotnet").mkdir()
    (tmp_path / "dotnet" / "libcoreclr.so").write_bytes(b"x")
    (tmp_path / ".doorstop_version").write_text("4.5.0", encoding="utf-8")
    (tmp_path / "winhttp.dll").write_bytes(b"x")
    (tmp_path / "game.dat").write_bytes(b"keep")
    (tmp_path / "BepInEx" / "Translation").mkdir(parents=True)
    write_runtime_marker(tmp_path, "mono_x64", "2021.3", ["winhttp.dll", "dotnet", ".doorstop_version", "../escape", "BepInEx"])
    assert HookInstaller.uninstall(tmp_path) is True
    assert not (tmp_path / "dotnet").exists() and not (tmp_path / ".doorstop_version").exists()
    assert not (tmp_path / "winhttp.dll").exists() and not (tmp_path / RUNTIME_MARKER).exists()
    assert (tmp_path / "game.dat").exists() and (tmp_path / "BepInEx" / "Translation").is_dir()


def test_uninstall_of_an_older_install_recognises_only_what_is_surely_bepinex(tmp_path: Path) -> None:
    (tmp_path / "dotnet").mkdir()
    (tmp_path / "dotnet" / "libcoreclr.so").write_bytes(b"x")
    (tmp_path / ".doorstop_version").write_text("4.5.0", encoding="utf-8")
    (tmp_path / "changelog.txt").write_text("could belong to the game", encoding="utf-8")
    other = tmp_path / "other"
    other.mkdir()
    (other / "dotnet").mkdir()
    (other / "dotnet" / "tool.dll").write_bytes(b"x")  # a "dotnet" folder that is not BepInEx's runtime
    HookInstaller.uninstall(tmp_path)
    HookInstaller.uninstall(other)
    assert not (tmp_path / "dotnet").exists() and not (tmp_path / ".doorstop_version").exists()
    assert (tmp_path / "changelog.txt").exists() and (other / "dotnet" / "tool.dll").exists()
