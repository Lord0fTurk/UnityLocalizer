# -*- coding: utf-8 -*-
"""How to start the selected game from the app on the current operating system."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from src.core.engine_profiler import UnityGameProfile
from src.core.hook_layout import LINUX_LAUNCH_SCRIPT

REASON_WINDOWS_GAME_ON_LINUX = "dashboard.launch_windows_game_on_linux"
REASON_NOT_EXECUTABLE = "dashboard.launch_not_executable"


class LaunchError(Exception):
    """The game cannot be started from here; ``reason_key`` is a localized UI message key."""

    def __init__(self, reason_key: str) -> None:
        super().__init__(reason_key)
        self.reason_key = reason_key


@dataclass(frozen=True)
class LaunchCommand:
    """Program and arguments to start, and the folder to start them in."""

    argv: list[str]
    cwd: Path


def launch_command(profile: UnityGameProfile, host: str | None = None) -> LaunchCommand:
    """Command that starts the game the way its installed hook needs.

    A native Linux game with BepInEx must be started through ``run_bepinex.sh``: running the
    game binary directly never loads the hook, so the translation would not appear. A Windows
    game cannot be run directly on Linux at all (it needs Steam with Proton).
    """
    exe = profile.game_exe
    if exe is None or not exe.is_file():
        raise LaunchError("dashboard.game_exe_not_found")
    host = host or sys.platform
    if host.startswith("win"):
        return LaunchCommand([str(exe)], exe.parent)
    if not profile.is_linux_build:
        raise LaunchError(REASON_WINDOWS_GAME_ON_LINUX)
    script = exe.parent / LINUX_LAUNCH_SCRIPT
    if script.is_file():
        return LaunchCommand(["/bin/sh", str(script)], exe.parent)
    if not os.access(exe, os.X_OK):
        raise LaunchError(REASON_NOT_EXECUTABLE)
    return LaunchCommand([str(exe)], exe.parent)
