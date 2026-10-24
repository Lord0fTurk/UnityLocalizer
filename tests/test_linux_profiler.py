# -*- coding: utf-8 -*-
"""Tests for Linux Unity game profiling (.x86_64, .x86 and ELF architecture detection)."""

from pathlib import Path
from src.core.engine_profiler import EngineProfiler, UnityGameProfile


def test_find_game_exe_locates_linux_x86_64_binary(tmp_path: Path) -> None:
    data_dir = tmp_path / "MyLinuxGame_Data"
    data_dir.mkdir()
    linux_bin = tmp_path / "MyLinuxGame.x86_64"
    linux_bin.write_bytes(b"\x7fELF\x02\x01\x01\x00")  # ELF64 header

    found = EngineProfiler._find_game_exe(tmp_path)
    assert found == linux_bin


def test_detect_architecture_identifies_linux_elf64(tmp_path: Path) -> None:
    data_dir = tmp_path / "Game_Data"
    data_dir.mkdir()
    linux_bin = tmp_path / "Game.x86_64"
    # ELF class 2 = 64-bit
    linux_bin.write_bytes(b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 56)

    profile = UnityGameProfile(game_path=tmp_path, game_exe=linux_bin, data_dir=data_dir)
    EngineProfiler._detect_architecture(profile)

    assert profile.is_windows_build is False
    assert profile.is_64bit is True


def test_detect_architecture_identifies_linux_elf32(tmp_path: Path) -> None:
    data_dir = tmp_path / "Game_Data"
    data_dir.mkdir()
    linux_bin = tmp_path / "Game.x86"
    # ELF class 1 = 32-bit
    linux_bin.write_bytes(b"\x7fELF\x01\x01\x01\x00" + b"\x00" * 56)

    profile = UnityGameProfile(game_path=tmp_path, game_exe=linux_bin, data_dir=data_dir)
    EngineProfiler._detect_architecture(profile)

    assert profile.is_windows_build is False
    assert profile.is_64bit is False
