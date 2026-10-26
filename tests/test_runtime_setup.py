# -*- coding: utf-8 -*-
"""Automatic runtime setup: needs_install decision, failure reasons and BepInEx log check."""

import os
import urllib.error
from pathlib import Path

import pytest

from src.core.hook_layout import BEPINEX_LOG, IL2CPP_RUNTIME_MARKER, runtime_flavor_matches
from src.core.hook_manager import installer as installer_module
from src.core.hook_manager.installer import HookInstaller, RuntimeSetupError, bepinex_package_key
from src.core.hook_manager.runtime_state import (
    LOG_ERROR,
    LOG_MISSING,
    LOG_OK,
    inspect_runtime_log,
    read_runtime_marker,
    write_runtime_marker,
)
from src.utils.downloader import IntegrityError


def _fake_hook(root: Path, il2cpp: bool = False) -> None:
    """Lay out the files runtime_hook_ready() looks for."""
    (root / "winhttp.dll").write_bytes(b"x")
    (root / "BepInEx" / "core").mkdir(parents=True)
    (root / "BepInEx" / "plugins" / "XUnity.AutoTranslator").mkdir(parents=True)
    if il2cpp:
        (root / IL2CPP_RUNTIME_MARKER).write_bytes(b"x")


def test_needs_install_when_nothing_installed(tmp_path: Path) -> None:
    assert HookInstaller.needs_install(tmp_path, True, False)


def test_hand_installed_hook_of_right_generation_is_kept(tmp_path: Path) -> None:
    _fake_hook(tmp_path)
    assert not HookInstaller.needs_install(tmp_path, True, False)


def test_wrong_generation_is_replaced(tmp_path: Path) -> None:
    _fake_hook(tmp_path)  # BepInEx 5 layout on an IL2CPP game
    assert not runtime_flavor_matches(tmp_path, True)
    assert HookInstaller.needs_install(tmp_path, True, True, 29)


def test_marker_for_other_architecture_triggers_reinstall(tmp_path: Path) -> None:
    _fake_hook(tmp_path)
    write_runtime_marker(tmp_path, bepinex_package_key(False, False), "2019.4.1f1")
    assert HookInstaller.needs_install(tmp_path, True, False)
    assert not HookInstaller.needs_install(tmp_path, False, False)


def test_ensure_runtime_skips_download_when_current(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_hook(tmp_path)
    monkeypatch.setattr(installer_module, "download_cached", lambda *a, **k: pytest.fail("downloaded"))
    assert HookInstaller.ensure_runtime(tmp_path) is False


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (urllib.error.URLError("offline"), "installer.reason_network"),
        (IntegrityError("bad hash"), "installer.reason_integrity"),
        (PermissionError("denied"), "installer.reason_permission"),
        (OSError("boom"), "installer.reason_other"),
    ],
)
def test_failed_download_raises_readable_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception, reason: str
) -> None:
    def fail(*args: object, **kwargs: object) -> Path:
        raise error

    monkeypatch.setattr(installer_module, "download_cached", fail)
    with pytest.raises(RuntimeSetupError) as caught:
        HookInstaller.ensure_runtime(tmp_path)
    assert caught.value.reason_key == reason


def test_install_writes_marker_and_uninstall_removes_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer_module, "download_cached", lambda *a, **k: tmp_path / "x.zip")
    monkeypatch.setattr(HookInstaller, "_safe_extract_zip", classmethod(lambda cls, z, d: None))
    assert HookInstaller.install(tmp_path, is_64bit=False, is_il2cpp=False) is True
    assert read_runtime_marker(tmp_path)["package"] == "mono_x86"
    HookInstaller.uninstall(tmp_path)
    assert read_runtime_marker(tmp_path) == {}


def _write_log(root: Path, text: str) -> Path:
    log = root / BEPINEX_LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(text, encoding="utf-8")
    return log


def test_log_missing(tmp_path: Path) -> None:
    assert inspect_runtime_log(tmp_path).state == LOG_MISSING


def test_log_ok(tmp_path: Path) -> None:
    _write_log(tmp_path, "[Info   :   BepInEx] Loading [XUnity Auto Translator 5.6.2]\n"
                         "[Message:   BepInEx] Chainloader startup complete\n")
    assert inspect_runtime_log(tmp_path).state == LOG_OK


def test_log_without_xunity_is_an_error(tmp_path: Path) -> None:
    _write_log(tmp_path, "[Message:   BepInEx] Chainloader startup complete\n")
    assert inspect_runtime_log(tmp_path).state == LOG_ERROR


def test_log_with_fatal_before_completion_reports_the_line(tmp_path: Path) -> None:
    _write_log(tmp_path, "[Fatal  :   BepInEx] Could not read metadata\n")
    status = inspect_runtime_log(tmp_path)
    assert status.state == LOG_ERROR
    assert "metadata" in status.detail


def test_log_older_than_install_counts_as_missing(tmp_path: Path) -> None:
    log = _write_log(tmp_path, "[Message:   BepInEx] Chainloader startup complete\nXUnity\n")
    os.utime(log, (1_000, 1_000))
    write_runtime_marker(tmp_path, "mono_x64", "2019.4.1f1")
    assert inspect_runtime_log(tmp_path).state == LOG_MISSING
