# -*- coding: utf-8 -*-
"""Games that delete BepInEx at start are reported before any translation work."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from src.core.harvesters.anti_mod import find_bepinex_removers
from src.core.progress import NOTIFICATION_LEVELS


def _profile(game: Path) -> Any:
    data = game / "Game_Data"
    (data / "Managed").mkdir(parents=True)
    return SimpleNamespace(data_dir=data)


def test_remover_routine_in_a_mono_assembly_is_found(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    (profile.data_dir / "Managed" / "Assembly-CSharp.dll").write_bytes(
        b"\x00BepInExRemover\x00CheckAndRemoveBepInEx\x00Update\x00"
    )
    assert find_bepinex_removers(profile) == ["BepInExRemover", "CheckAndRemoveBepInEx"]


def test_remover_routine_in_il2cpp_metadata_is_found(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    metadata = profile.data_dir / "il2cpp_data" / "Metadata"
    metadata.mkdir(parents=True)
    (metadata / "global-metadata.dat").write_bytes(b"\x00DeleteBepInExFolders\x00")
    assert find_bepinex_removers(profile) == ["DeleteBepInExFolders"]


def test_a_plain_bepinex_string_is_not_a_remover(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    (profile.data_dir / "Managed" / "Assembly-CSharp.dll").write_bytes(b"\x00BepInEx\x00Thanks to BepInEx\x00")
    assert find_bepinex_removers(profile) == []


def test_game_without_data_dir_is_ignored() -> None:
    assert find_bepinex_removers(SimpleNamespace(data_dir=None)) == []


def test_warning_is_a_notification() -> None:
    assert NOTIFICATION_LEVELS["pipeline.anti_mod_detected"] == "warning"
