# -*- coding: utf-8 -*-
"""The delayed-start XUnity wrapper for Unity 6000.5: when it applies, what it replaces, what it leaves alone."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from src.core.hook_manager import delayed_start, installer
from src.core.hook_manager.delayed_start import (
    DelayedStartResult,
    apply_delayed_start,
    plugin_dll_path,
    shipped_wrapper,
    startup_crash_in_log,
    unity_needs_delayed_start,
)

ORIGINAL = b"original wrapper bytes"


@pytest.mark.parametrize("version, expected", [
    ("6000.5.2f1", True), ("6000.5.0f1", True), ("6000.6.1f1", True), ("6001.0.0f1", True), ("6000.5.2", True),
    ("6000.4.4f1", False), ("6000.0.69f1", False), ("2022.3.10f1", False), ("5.6.7f1", False),
    ("Unknown", False), ("", False),
])
def test_only_unity_6000_5_and_newer_needs_the_delayed_start(version: str, expected: bool) -> None:
    assert unity_needs_delayed_start(version) is expected


def test_the_shipped_wrapper_matches_its_recorded_hash() -> None:
    path = shipped_wrapper()
    assert path is not None and path.name == delayed_start.WRAPPER_DLL
    assert hashlib.sha256(path.read_bytes()).hexdigest() == delayed_start.WRAPPER_SHA256


def test_the_source_never_starts_a_coroutine_and_keeps_the_plugin_identity() -> None:
    source = (Path(delayed_start.__file__).parent / "xunity_wrapper" / "DelayedStart.cs").read_text(encoding="utf-8")
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("//"))
    assert "StartCoroutine" not in code and "gravydevsupreme.xunity.autotranslator" in code
    assert "PluginLoader.LoadWithConfig" in code and "Update()" in code


@pytest.fixture
def game(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A game folder whose wrapper is the 'original' one, with the original hash pointed at it."""
    target = plugin_dll_path(tmp_path)
    target.parent.mkdir(parents=True)
    target.write_bytes(ORIGINAL)
    monkeypatch.setattr(delayed_start, "ORIGINAL_WRAPPER_SHA256", hashlib.sha256(ORIGINAL).hexdigest())
    return tmp_path


def test_the_original_wrapper_is_replaced_and_kept_as_backup(game: Path) -> None:
    assert apply_delayed_start(game, "6000.5.2f1") is DelayedStartResult.APPLIED
    target = plugin_dll_path(game)
    assert target.read_bytes() == shipped_wrapper().read_bytes()  # type: ignore[union-attr]
    assert target.with_name(target.name + ".bak").read_bytes() == ORIGINAL


def test_applying_twice_changes_nothing_more(game: Path) -> None:
    apply_delayed_start(game, "6000.5.2f1")
    before = plugin_dll_path(game).read_bytes()
    assert apply_delayed_start(game, "6000.5.2f1") is DelayedStartResult.ALREADY
    assert plugin_dll_path(game).read_bytes() == before


@pytest.mark.parametrize("version, il2cpp", [("6000.4.4f1", False), ("2022.3.10f1", False), ("6000.5.2f1", True)])
def test_other_games_are_left_alone(game: Path, version: str, il2cpp: bool) -> None:
    assert apply_delayed_start(game, version, il2cpp) is DelayedStartResult.NOT_NEEDED
    assert plugin_dll_path(game).read_bytes() == ORIGINAL


def test_a_hand_installed_xunity_is_not_overwritten(game: Path, caplog: pytest.LogCaptureFixture) -> None:
    plugin_dll_path(game).write_bytes(b"some other XUnity version")
    assert apply_delayed_start(game, "6000.5.2f1") is DelayedStartResult.SKIPPED_FOREIGN
    assert plugin_dll_path(game).read_bytes() == b"some other XUnity version"
    assert "hand-installed" in caplog.text


def test_a_game_without_xunity_is_skipped(tmp_path: Path) -> None:
    assert apply_delayed_start(tmp_path, "6000.5.2f1") is DelayedStartResult.SKIPPED_MISSING


def test_a_tampered_shipped_wrapper_is_never_copied(game: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(delayed_start, "WRAPPER_SHA256", "0" * 64)
    assert apply_delayed_start(game, "6000.5.2f1") is DelayedStartResult.SKIPPED_NO_WRAPPER
    assert plugin_dll_path(game).read_bytes() == ORIGINAL


def test_an_existing_install_is_repaired_without_a_reinstall(game: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer.HookInstaller, "needs_install", classmethod(lambda cls, *a, **k: False))
    assert installer.HookInstaller.ensure_runtime(game, unity_version="6000.5.2f1") is False
    assert plugin_dll_path(game).read_bytes() == shipped_wrapper().read_bytes()  # type: ignore[union-attr]


def test_a_locked_file_does_not_fail_the_run(game: Path, monkeypatch: pytest.MonkeyPatch,
                                              caplog: pytest.LogCaptureFixture) -> None:
    def locked(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("the file is in use")

    monkeypatch.setattr(installer, "apply_delayed_start", locked)
    installer.HookInstaller.apply_runtime_fixes(game, "6000.5.2f1", False)
    assert "Could not apply the delayed-start wrapper" in caplog.text


# --- the crash signature in BepInEx's log ----------------------------------------------------------------

LOADING = "[Info   :   BepInEx] Loading [XUnity Auto Translator 5.6.2]\n"
LOADED = "[Info   :XUnity.AutoTranslator] Loaded XUnity.AutoTranslator into Unity [6000.5.2f1] game.\n"
START = "[Message:   BepInEx] Chainloader started\n[Info   :   BepInEx] 2 plugins to load\n"


def _write_log(root: Path, text: str) -> None:
    log = root / "BepInEx" / "LogOutput.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(text, encoding="utf-8")


@pytest.mark.parametrize("text, expected", [
    (START + LOADING, True),                                       # died while XUnity was loading
    (START + LOADING + "[Info   :XUnity.AutoTranslator] Version of TextMesh Pro: 1.4.0.\n", True),
    (START + LOADING + LOADED, False),                             # it finished: a later problem is something else
    (START + "[Info   :   BepInEx] Loading [XUnity Resource Redirector 2.1.0]\n", False),
    ("[Info   :   BepInEx] Preloader started\n", False),           # never got as far as the plugins
    (LOADING + LOADED + START + LOADING, True),                    # only the last start counts
    ("", False),
])
def test_the_crash_signature_is_a_log_that_ends_while_xunity_loads(tmp_path: Path, text: str, expected: bool) -> None:
    _write_log(tmp_path, text)
    assert startup_crash_in_log(tmp_path) is expected


def test_no_log_is_no_signature(tmp_path: Path) -> None:
    assert startup_crash_in_log(tmp_path) is False


def test_an_older_unity_is_switched_after_a_crash_on_the_last_run(game: Path) -> None:
    _write_log(game, START + LOADING)
    assert apply_delayed_start(game, "6000.4.4f1") is DelayedStartResult.APPLIED_AFTER_CRASH
    assert plugin_dll_path(game).read_bytes() == shipped_wrapper().read_bytes()  # type: ignore[union-attr]


def test_an_older_unity_without_a_crash_is_left_alone(game: Path) -> None:
    _write_log(game, START + LOADING + LOADED)
    assert apply_delayed_start(game, "2022.3.10f1") is DelayedStartResult.NOT_NEEDED
    assert plugin_dll_path(game).read_bytes() == ORIGINAL


def test_a_known_version_does_not_report_a_crash(game: Path) -> None:
    _write_log(game, START + LOADING)
    assert apply_delayed_start(game, "6000.5.2f1") is DelayedStartResult.APPLIED  # the version rule, no crash message


def test_il2cpp_games_are_not_touched_even_after_a_crash(game: Path, caplog: pytest.LogCaptureFixture) -> None:
    _write_log(game, START + LOADING)
    assert apply_delayed_start(game, "6000.4.4f1", is_il2cpp=True) is DelayedStartResult.NOT_NEEDED
    assert plugin_dll_path(game).read_bytes() == ORIGINAL and "only available for Mono" in caplog.text


def test_a_foreign_xunity_is_left_alone_after_a_crash_too(game: Path) -> None:
    plugin_dll_path(game).write_bytes(b"some other XUnity version")
    _write_log(game, START + LOADING)
    assert apply_delayed_start(game, "6000.4.4f1") is DelayedStartResult.SKIPPED_FOREIGN


def test_the_user_is_told_only_when_the_crash_log_triggered_it(game: Path) -> None:
    events: list[str] = []
    _write_log(game, START + LOADING)
    installer.HookInstaller.apply_runtime_fixes(game, "6000.4.4f1", False, lambda event: events.append(event.key))
    assert events == ["installer.delayed_start_after_crash"]

    events.clear()
    installer.HookInstaller.apply_runtime_fixes(game, "6000.4.4f1", False, lambda event: events.append(event.key))
    assert events == []  # already applied: no second message

    other = game.parent / "other"
    shutil.copytree(game, other)
    plugin_dll_path(other).write_bytes(ORIGINAL)
    installer.HookInstaller.apply_runtime_fixes(other, "6000.5.2f1", False, lambda event: events.append(event.key))
    assert events == []  # a version the rule knows: applied silently


def test_the_notification_is_registered_and_translated() -> None:
    import json

    from src.core.progress import NOTIFICATION_LEVELS

    assert NOTIFICATION_LEVELS["installer.delayed_start_after_crash"] == "warning"
    languages = sorted(Path("src/gui/i18n").glob("*.json"))
    assert len(languages) == 12
    for path in languages:
        text = json.loads(path.read_text(encoding="utf-8"))["installer"]["delayed_start_after_crash"]
        assert "XUnity" in text, path.name
