# -*- coding: utf-8 -*-
"""Tests for data-directory resolution, legacy migration and persisted session state."""

from pathlib import Path
from typing import Any

import pytest

from src.utils import paths
from src.utils.data_migration import MIGRATION_MARKER, migrate_legacy_data


@pytest.fixture()
def app_and_data(tmp_path: Path, monkeypatch: Any) -> tuple[Path, Path]:
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    appdata = tmp_path / "appdata"
    monkeypatch.setattr(paths, "get_app_dir", lambda: app_dir)
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.delenv(paths.DATA_DIR_ENV, raising=False)
    monkeypatch.setattr(paths.platform, "system", lambda: "Windows")
    paths.reset_data_dir_cache()
    yield app_dir, appdata / "UnityLocalizer"
    paths.reset_data_dir_cache()


def test_default_is_system_data_dir(app_and_data: tuple[Path, Path]) -> None:
    app_dir, system_dir = app_and_data
    assert paths.get_data_dir() == system_dir
    assert paths.get_config_path() == system_dir / "config.json"
    assert paths.get_cache_dir() == system_dir / "cache" and paths.get_cache_dir().is_dir()
    assert paths.get_patches_dir() == system_dir / "Patches"


def test_portable_marker_keeps_data_beside_app(app_and_data: tuple[Path, Path]) -> None:
    app_dir, _ = app_and_data
    (app_dir / paths.PORTABLE_MARKER).write_text("", encoding="utf-8")
    assert paths.get_data_dir() == app_dir


def test_existing_config_beside_app_stays_portable(app_and_data: tuple[Path, Path]) -> None:
    app_dir, _ = app_and_data
    (app_dir / "config.json").write_text("{}", encoding="utf-8")
    assert paths.get_data_dir() == app_dir


def test_environment_override_wins(app_and_data: tuple[Path, Path], tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path / "custom"))
    paths.reset_data_dir_cache()
    assert paths.get_data_dir() == tmp_path / "custom"


def test_migration_copies_once_without_overwriting(tmp_path: Path) -> None:
    app_dir, data_dir = tmp_path / "app", tmp_path / "data"
    (app_dir / ".unity_cache" / "hooks").mkdir(parents=True)
    (app_dir / ".unity_cache" / "translations.db").write_bytes(b"db")
    (app_dir / ".unity_cache" / "hooks" / "BepInEx.zip").write_bytes(b"zip")
    (app_dir / "glossary.json").write_text('{"a": "b"}', encoding="utf-8")
    data_dir.mkdir()
    (data_dir / "glossary.json").write_text('{"new": "keep"}', encoding="utf-8")

    copied = migrate_legacy_data(app_dir, data_dir)
    assert copied == [".unity_cache"]  # glossary.json already existed in the data dir
    assert (data_dir / "cache" / "translations.db").read_bytes() == b"db"
    assert (data_dir / "cache" / "hooks" / "BepInEx.zip").is_file()
    assert (data_dir / "glossary.json").read_text(encoding="utf-8") == '{"new": "keep"}'  # never overwritten
    assert (app_dir / ".unity_cache" / "translations.db").is_file()  # originals stay
    assert (data_dir / MIGRATION_MARKER).is_file()

    (app_dir / "config.json").write_text("{}", encoding="utf-8")
    assert migrate_legacy_data(app_dir, data_dir) == []  # marker prevents a second run


def test_portable_mode_migrates_old_cache_folder_name(tmp_path: Path) -> None:
    app_dir = tmp_path / "app"
    (app_dir / ".unity_cache").mkdir(parents=True)
    (app_dir / ".unity_cache" / "translations.db").write_bytes(b"db")
    (app_dir / "config.json").write_text("{}", encoding="utf-8")
    assert migrate_legacy_data(app_dir, app_dir) == [".unity_cache"]
    assert (app_dir / "cache" / "translations.db").is_file()


# --- Persisted session state ----------------------------------------------------------


@pytest.fixture()
def backend(tmp_path: Path, monkeypatch: Any) -> Any:
    import src.backend.app_backend as module
    from src.utils.config import ConfigManager

    config_path = tmp_path / "config.json"
    monkeypatch.setattr(module, "ConfigManager", lambda: ConfigManager(config_path))
    # Runs must never download BepInEx during tests; runtime-setup tests override this.
    monkeypatch.setattr(module.HookInstaller, "needs_install", classmethod(lambda cls, *a, **k: False))
    instance = module.AppBackend()
    instance.config_path = config_path
    return instance


def _reload(backend: Any) -> dict[str, Any]:
    import json

    return json.loads(backend.config_path.read_text(encoding="utf-8"))


def test_ui_language_window_and_settings_are_written_to_config(backend: Any) -> None:
    backend.onUiLanguageChanged("de")
    backend.saveWindowState(1440, 900, True)
    backend.setTargetLanguage("ja")
    backend.setSetting("max_concurrency", 6)
    saved = _reload(backend)
    assert saved["ui_language"] == "de"
    assert (saved["window_width"], saved["window_height"], saved["window_maximized"]) == (1440, 900, True)
    assert saved["target_language"] == "ja" and saved["max_concurrency"] == 6
    assert backend.windowGeometry == {"width": 1440, "height": 900, "maximized": True}


def test_last_game_is_remembered_and_restored(backend: Any, tmp_path: Path) -> None:
    game = tmp_path / "Game"
    (game / "Game_Data").mkdir(parents=True)
    (game / "Game.exe").write_bytes(b"MZ")
    (game / "UnityPlayer.dll").write_bytes(b"MZ")
    backend.selectGame(str(game))
    assert _reload(backend)["last_game_path"] == str(game)

    backend._game_path = ""
    backend.restoreLastSession()
    assert backend.gamePath == str(game)


def test_missing_last_game_is_ignored(backend: Any, tmp_path: Path) -> None:
    backend.config.set("last_game_path", str(tmp_path / "gone"))
    backend.restoreLastSession()
    assert backend.gamePath == ""


def test_shutdown_keeps_cached_translations(backend: Any) -> None:
    backend.tm.cache.set("Attack", "Saldırı", "en", "tr", "google")
    backend.shutdown()
    assert backend.tm.cache.get("Attack", "en", "tr", "google") == "Saldırı"


def test_open_patch_folder_uses_desktop_services(backend: Any, monkeypatch: Any) -> None:
    import src.backend.app_backend as module

    opened: list[str] = []
    monkeypatch.setattr(module.QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()) or True)
    backend.openPatchFolder()
    assert len(opened) == 1 and Path(opened[0]).is_dir()


def test_game_cannot_change_while_a_job_runs(backend: Any, tmp_path: Path) -> None:
    game = tmp_path / "Game"
    (game / "Game_Data").mkdir(parents=True)
    (game / "UnityPlayer.dll").write_bytes(b"MZ")
    backend._is_busy = True
    backend.selectGame(str(game))
    assert backend.gamePath == ""


def _game(tmp_path: Path) -> Path:
    game = tmp_path / "Game"
    sa_dir = game / "Game_Data" / "StreamingAssets"
    sa_dir.mkdir(parents=True)
    (sa_dir / "lines.json").write_text('{"a": "Open the door", "b": "Close it"}', encoding="utf-8")
    (game / "Game.exe").write_bytes(b"MZ")
    (game / "UnityPlayer.dll").write_bytes(b"MZ")
    return game


def test_failed_engine_is_reported_instead_of_no_strings(backend: Any, tmp_path: Path, monkeypatch: Any) -> None:
    from src.core.translators.base import TranslationEngine, TranslationResult

    def offline(texts: list[str], *args: Any, **kwargs: Any) -> list[TranslationResult]:
        return [TranslationResult(t, t, "en", "tr", TranslationEngine.GOOGLE, False, error="no internet") for t in texts]

    game = _game(tmp_path)
    monkeypatch.setattr(backend.tm, "translate_batch", offline)
    backend.selectGame(str(game))
    from src.core.progress import CancelToken

    backend._run_localization(CancelToken())
    assert backend._status_key == "dashboard.status_translation_failed"
    assert "no internet" in backend._status_params["error"]
    assert not (game / "BepInEx").exists()  # nothing deployed


def test_completed_run_without_hook_warns_that_bepinex_is_missing(backend: Any, tmp_path: Path, monkeypatch: Any) -> None:
    from src.core.progress import CancelToken
    from src.core.translators.base import TranslationEngine, TranslationResult

    def echo(texts: list[str], *args: Any, **kwargs: Any) -> list[TranslationResult]:
        return [TranslationResult(t, t + " (tr)", "en", "tr", TranslationEngine.GOOGLE, True) for t in texts]

    game = _game(tmp_path)
    monkeypatch.setattr(backend.tm, "translate_batch", echo)
    monkeypatch.setattr("src.core.pipeline.orchestrator.FontProvisioner.provision", lambda *a, **k: None)
    backend.selectGame(str(game))
    backend._run_localization(CancelToken())

    assert backend._status_key == "dashboard.status_completed"
    assert backend.hasBepInEx is False  # the BepInEx folder the pipeline wrote is not a hook
    assert any("BepInEx" in entry["message"] or "status_hook_missing_proxy" in entry["message"] for entry in backend.logs)


def test_runtime_setup_is_skipped_with_a_warning_for_unsupported_platforms(
    backend: Any, tmp_path: Path, monkeypatch: Any
) -> None:
    import src.backend.app_backend as module
    from src.core.progress import CancelToken

    game = tmp_path / "Game"
    (game / "Game_Data").mkdir(parents=True)
    (game / "Game_Data" / "globalgamemanagers").write_bytes(b"x")
    (game / "Game").write_bytes(b"\xcf\xfa\xed\xfe")  # Mach-O: no BepInEx package for macOS
    backend.selectGame(str(game))
    assert backend._profile is not None and not backend._profile.is_windows_build
    monkeypatch.setattr(module.HookInstaller, "needs_install", classmethod(lambda cls, *a, **k: pytest.fail("checked")))

    backend._ensure_runtime(CancelToken())
    assert any("hook_platform_unsupported" in entry["message"] for entry in backend.logs)


def test_patch_export_is_refused_with_the_reason(backend: Any, tmp_path: Path, monkeypatch: Any) -> None:
    game = tmp_path / "Game"
    (game / "Game_Data").mkdir(parents=True)
    (game / "Game.exe").write_bytes(b"MZ")
    (game / "UnityPlayer.dll").write_bytes(b"MZ")
    backend.selectGame(str(game))
    started: list[Any] = []
    monkeypatch.setattr(backend, "_run_in_background", started.append)

    backend.exportPatchPackage()
    assert started == []  # nothing useless is packaged
    assert backend._status_key == "dashboard.patch_no_hook"
    assert any(entry["level"] == "error" for entry in backend.logs)


def test_tmp_system_font_setting_reaches_the_pipeline(backend: Any, monkeypatch: Any) -> None:
    from src.core.progress import CancelToken

    backend.setSetting("tmp_system_font", "  Arial  ")
    assert _reload(backend)["tmp_system_font"] == "Arial"
    seen: list[Any] = []
    monkeypatch.setattr(backend.pipeline, "run_unified_localization_pipeline",
                        lambda *a, **k: seen.append(backend.pipeline.tmp_override_font) or 0)
    backend._game_path = "."
    backend._execute_pipeline(CancelToken())
    assert seen == ["Arial"]


def test_run_installs_runtime_first_and_reports_status(backend: Any, tmp_path: Path, monkeypatch: Any) -> None:
    import src.backend.app_backend as module
    from src.core.progress import CancelToken

    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(module.HookInstaller, "needs_install", classmethod(lambda cls, *a, **k: True))
    monkeypatch.setattr(module.HookInstaller, "ensure_runtime", classmethod(lambda cls, *a, **k: calls.append(k) or True))
    statuses: list[str] = []
    monkeypatch.setattr(backend, "_set_status", lambda key, **kw: statuses.append(key))
    backend.selectGame(str(_game(tmp_path)))
    backend._ensure_runtime(CancelToken())
    assert len(calls) == 1 and calls[0]["is_il2cpp"] is False
    assert "dashboard.status_preparing_runtime" in statuses


def test_runtime_setup_failure_stops_the_run_with_a_clear_message(backend: Any, tmp_path: Path, monkeypatch: Any) -> None:
    import src.backend.app_backend as module
    from src.core.hook_manager.installer import RuntimeSetupError
    from src.core.progress import CancelToken

    def offline(cls: Any, *a: Any, **k: Any) -> bool:
        raise RuntimeSetupError("installer.reason_network", "getaddrinfo failed")

    monkeypatch.setattr(module.HookInstaller, "needs_install", classmethod(lambda cls, *a, **k: True))
    monkeypatch.setattr(module.HookInstaller, "ensure_runtime", classmethod(offline))
    monkeypatch.setattr(backend, "_execute_pipeline", lambda cancel: pytest.fail("pipeline must not start"))
    backend.selectGame(str(_game(tmp_path)))
    backend._run_localization(CancelToken())
    assert backend._status_key == "dashboard.runtime_setup_failed"
    assert backend._status_params["reason"] == "installer.reason_network"


def test_linux_host_gets_the_proton_launch_option_hint(backend: Any, tmp_path: Path, monkeypatch: Any) -> None:
    import src.backend.app_backend as module
    from src.core.progress import CancelToken

    monkeypatch.setattr(module.sys, "platform", "linux")
    backend.selectGame(str(_game(tmp_path)))
    backend._ensure_runtime(CancelToken())
    assert any(n["text"] == "dashboard.proton_hint" for n in backend.notices)


def test_support_prompt_appears_from_the_third_finished_run_until_dismissed(backend: Any, tmp_path: Path) -> None:
    backend._game_path = str(tmp_path)
    backend.pipeline.last_harvest_count = 10
    seen: list[bool] = []
    backend.pipelineCompleted.connect(lambda summary: seen.append(summary["show_support"]))
    for _ in range(3):
        backend._report_outcome(10)
    backend.setSetting("hide_support_prompt", True)
    backend._report_outcome(10)
    assert seen == [False, False, True, False]


def test_an_installed_runtime_still_gets_the_runtime_fixes(backend: Any, tmp_path: Path, monkeypatch: Any) -> None:
    import src.backend.app_backend as module
    from src.core.progress import CancelToken

    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(module.HookInstaller, "needs_install", classmethod(lambda cls, *a, **k: False))
    monkeypatch.setattr(module.HookInstaller, "apply_runtime_fixes", staticmethod(lambda *a, **k: calls.append(a)))
    backend.selectGame(str(_game(tmp_path)))
    backend._ensure_runtime(CancelToken())
    assert len(calls) == 1 and calls[0][2] is False  # (game dir, Unity version, is_il2cpp, progress)
