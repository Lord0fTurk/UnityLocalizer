# -*- coding: utf-8 -*-
"""Tests for Linux & Steam Deck patch exporter scripts and README instructions."""

from pathlib import Path
from src.core.pipeline.patch_scripts import write_readme, write_scripts


def test_write_scripts_creates_linux_shell_scripts_with_lf(tmp_path: Path) -> None:
    write_scripts(tmp_path, target_lang="tr")

    expected_sh = ("Install_Patch.sh", "Uninstall_Patch.sh", "Yama_Kur.sh", "Yama_Kaldir.sh")
    for script_name in expected_sh:
        path = tmp_path / script_name
        assert path.is_file(), f"{script_name} must be generated"
        raw_bytes = path.read_bytes()
        # Bash scripts must have LF only, never CRLF
        assert b"\r\n" not in raw_bytes, f"{script_name} must not contain CRLF"
        text = raw_bytes.decode("utf-8")
        assert "#!/bin/sh" in text
        if "Install" in script_name or "Kur" in script_name:
            assert "WINEDLLOVERRIDES" in text


def test_write_readme_contains_steam_deck_and_proton_guide(tmp_path: Path) -> None:
    write_readme(tmp_path, game_name="TestGame", target_lang="tr")

    for readme_name in ("README.txt", "BENI_OKU.txt"):
        path = tmp_path / readme_name
        assert path.is_file()
        content = path.read_text(encoding="utf-8-sig")
        assert "STEAM DECK / LINUX (PROTON)" in content
        assert 'WINEDLLOVERRIDES="winhttp=n,b" %command%' in content
