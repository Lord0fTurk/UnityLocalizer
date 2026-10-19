# -*- coding: utf-8 -*-
"""Unit tests for EngineProfiler."""

from pathlib import Path
from src.core.engine_profiler import EngineProfiler


def test_profile_mono_game(tmp_path: Path):
    game_dir = tmp_path / "MyUnityGame"
    game_dir.mkdir()

    # Create Game.exe and Game_Data
    (game_dir / "MyUnityGame.exe").touch()
    data_dir = game_dir / "MyUnityGame_Data"
    data_dir.mkdir()

    # Create Managed folder with Managed DLLs
    managed = data_dir / "Managed"
    managed.mkdir()
    (managed / "Assembly-CSharp.dll").touch()
    (managed / "Unity.TextMeshPro.dll").touch()

    # Create StreamingAssets
    sa = data_dir / "StreamingAssets"
    sa.mkdir()
    (sa / "dialogue.json").touch()

    profile = EngineProfiler.profile_game(game_dir)

    assert profile.is_il2cpp is False
    assert profile.has_text_mesh_pro is True
    assert profile.has_streaming_assets is True
    assert "Route 1: Native Static Patcher" in profile.available_routes


def test_profile_il2cpp_game(tmp_path: Path):
    game_dir = tmp_path / "IL2CPPGame"
    game_dir.mkdir()

    (game_dir / "IL2CPPGame.exe").touch()
    (game_dir / "GameAssembly.dll").touch()
    data_dir = game_dir / "IL2CPPGame_Data"
    data_dir.mkdir()
    (data_dir / "il2cpp_data").mkdir()

    profile = EngineProfiler.profile_game(game_dir)

    assert profile.is_il2cpp is True


def test_reject_unreal_engine(tmp_path: Path):
    game_dir = tmp_path / "UnrealGame"
    game_dir.mkdir()
    (game_dir / "Engine").mkdir()
    (game_dir / "Manifest_NonUFSFiles_Win64.txt").touch()

    import pytest
    with pytest.raises(ValueError, match="profiler.error_unreal_engine"):
        EngineProfiler.profile_game(game_dir)


def test_reject_renpy_engine(tmp_path: Path):
    game_dir = tmp_path / "RenpyGame"
    game_dir.mkdir()
    (game_dir / "renpy").mkdir()

    import pytest
    with pytest.raises(ValueError, match="profiler.error_renpy_engine"):
        EngineProfiler.profile_game(game_dir)


def test_reject_rpg_maker_engine(tmp_path: Path):
    game_dir = tmp_path / "RPGMGame"
    game_dir.mkdir()
    (game_dir / "www").mkdir()

    import pytest
    with pytest.raises(ValueError, match="profiler.error_rpgm_engine"):
        EngineProfiler.profile_game(game_dir)


def test_reject_non_unity_folder(tmp_path: Path):
    random_dir = tmp_path / "RandomApp"
    random_dir.mkdir()
    (random_dir / "something.txt").touch()

    import pytest
    with pytest.raises(ValueError, match="profiler.error_not_unity"):
        EngineProfiler.profile_game(random_dir)


def test_reject_nonexistent_path(tmp_path: Path):
    nonexistent = tmp_path / "Does_Not_Exist"

    import pytest
    with pytest.raises(FileNotFoundError):
        EngineProfiler.profile_game(nonexistent)



def _unity_game(root: Path, name: str = "Game") -> Path:
    game = root / name
    (game / f"{name}_Data").mkdir(parents=True)
    (game / f"{name}.exe").write_bytes(b"MZ")
    (game / "UnityPlayer.dll").write_bytes(b"MZ")
    return game


def test_pipeline_output_alone_does_not_count_as_installed_bepinex(tmp_path: Path) -> None:
    """The pipeline writes BepInEx/Translation and BepInEx/config even without a hook."""
    game = _unity_game(tmp_path)
    (game / "BepInEx" / "Translation" / "tr" / "Text").mkdir(parents=True)
    (game / "BepInEx" / "config").mkdir(parents=True)
    assert EngineProfiler.profile_game(game).has_bepinex is False

    (game / "winhttp.dll").write_bytes(b"MZ")
    (game / "BepInEx" / "core").mkdir()
    (game / "BepInEx" / "plugins" / "XUnity.AutoTranslator").mkdir(parents=True)
    assert EngineProfiler.profile_game(game).has_bepinex is True


def test_unity_game_with_engine_folder_is_not_reported_as_unreal(tmp_path: Path) -> None:
    game = _unity_game(tmp_path)
    (game / "Engine").mkdir()
    assert EngineProfiler.profile_game(game).game_path == game


def test_folder_named_data_without_unity_files_is_rejected(tmp_path: Path) -> None:
    import pytest

    app = tmp_path / "Tool"
    (app / "Tool_Data").mkdir(parents=True)
    (app / "Tool.exe").write_bytes(b"MZ")
    with pytest.raises(ValueError, match="profiler.error_not_unity"):
        EngineProfiler.profile_game(app)


def test_game_exe_is_the_one_owning_the_data_folder(tmp_path: Path) -> None:
    game = _unity_game(tmp_path, "Zeta")
    (game / "Alpha Launcher.exe").write_bytes(b"MZ")  # sorts first, but has no Alpha Launcher_Data
    assert EngineProfiler.profile_game(game).game_exe == game / "Zeta.exe"


def test_linux_build_is_flagged_as_non_windows(tmp_path: Path) -> None:
    game = tmp_path / "Game"
    (game / "Game_Data").mkdir(parents=True)
    (game / "Game.x86_64").write_bytes(b"\x7fELF")
    (game / "UnityPlayer.so").write_bytes(b"\x7fELF")
    profile = EngineProfiler.profile_game(game)
    assert profile.is_windows_build is False


def test_runtime_hook_is_always_the_recommended_route(tmp_path: Path) -> None:
    game = _unity_game(tmp_path)
    profile = EngineProfiler.profile_game(game)
    assert profile.recommended_route == "Route 3: Runtime Hook (BepInEx)"
    assert profile.available_routes == ["Route 3: Runtime Hook (BepInEx)"]
