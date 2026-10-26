# -*- coding: utf-8 -*-
"""Install marker and BepInEx start-up log inspection for a game's runtime hook.

The marker records which BepInEx package UnityLocalizer deployed, so a later run can
tell a correct install from a stale or wrong one. ``LogOutput.log`` is written by
BepInEx itself on every game start, so it is the only proof the hook really loaded.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.hook_layout import BEPINEX_LOG, RUNTIME_MARKER
from src.utils.file_ops import safe_write

logger = logging.getLogger(__name__)

LOG_OK = "ok"
LOG_MISSING = "missing"
LOG_ERROR = "error"

_LOG_TAIL_BYTES = 512 * 1024
_CHAINLOADER_DONE = "Chainloader startup complete"
_FATAL_MARKERS = ("[Fatal", "[Error")


@dataclass(frozen=True)
class LogStatus:
    """Outcome of reading BepInEx's start-up log: ``ok``, ``missing`` or ``error``."""

    state: str
    detail: str = ""


def write_runtime_marker(
    game_dir: Path | str, package_key: str, unity_version: str, owned: list[str] | None = None
) -> None:
    """Record the package that was deployed and when.

    ``owned`` lists the top-level files and folders the install added to the game root (names
    that did not exist before), so an uninstall removes exactly those and nothing of the game.
    """
    payload: dict[str, Any] = {
        "package": package_key, "unity_version": unity_version, "installed_at": time.time(),
        "owned": sorted(owned or []),
    }
    safe_write(Path(game_dir) / RUNTIME_MARKER, json.dumps(payload, indent=2), make_backup=False)


def read_runtime_marker(game_dir: Path | str) -> dict[str, Any]:
    """Return the install marker, or an empty dict when absent or unreadable."""
    path = Path(game_dir) / RUNTIME_MARKER
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        logger.warning("Ignoring unreadable runtime marker %s: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def remove_runtime_marker(game_dir: Path | str) -> None:
    """Delete the install marker (the hook was uninstalled)."""
    try:
        (Path(game_dir) / RUNTIME_MARKER).unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Could not remove runtime marker: %s", exc)


def _read_log_tail(log: Path) -> str:
    """Last part of the log; BepInEx logs of long sessions can grow large."""
    with open(log, "rb") as handle:
        handle.seek(0, 2)
        handle.seek(max(0, handle.tell() - _LOG_TAIL_BYTES))
        return handle.read().decode("utf-8", errors="replace")


def _first_problem_line(text: str) -> str:
    """First fatal/error line, trimmed for display; '' when there is none."""
    for line in text.splitlines():
        if line.startswith(_FATAL_MARKERS):
            return line.strip()[:200]
    return ""


def inspect_runtime_log(game_dir: Path | str) -> LogStatus:
    """Judge whether BepInEx and XUnity started in the game since they were installed.

    A log older than the install belongs to a previous setup and counts as missing.
    """
    root = Path(game_dir)
    log = root / BEPINEX_LOG
    try:
        if not log.is_file():
            return LogStatus(LOG_MISSING)
        installed_at = float(read_runtime_marker(root).get("installed_at") or 0)
        if log.stat().st_mtime < installed_at:
            return LogStatus(LOG_MISSING)
        text = _read_log_tail(log)
    except (OSError, ValueError) as exc:
        logger.warning("Cannot read BepInEx log %s: %s", log, exc)
        return LogStatus(LOG_MISSING)
    problem = _first_problem_line(text)
    if _CHAINLOADER_DONE not in text:
        return LogStatus(LOG_ERROR, problem) if problem else LogStatus(LOG_MISSING)
    if "XUnity" not in text:
        return LogStatus(LOG_ERROR, "XUnity.AutoTranslator did not load")
    return LogStatus(LOG_OK)
