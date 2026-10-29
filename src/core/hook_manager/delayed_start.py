# -*- coding: utf-8 -*-
"""Starts XUnity.AutoTranslator a few frames late on Unity versions that crash when it starts while plugins load.

On Unity 6000.5.2 calling ``StartCoroutine`` before the player loop runs kills the player with an access
violation inside ``UnityPlayer.dll``, and XUnity's start-up starts a coroutine: a patched game dies about
13 s after launch with the BepInEx log ending at "Loading [XUnity Auto Translator]" (found on Situation Succ
Inn Elysium; BepInEx alone and the Resource Redirector alone run fine, XUnity 5.6.2 and 5.6.3.1 both crash
whatever the configuration). The wrapper in ``xunity_wrapper/`` is XUnity's own BepInEx 5 wrapper except that it
calls ``PluginLoader.LoadWithConfig`` from ``Update()`` after three frames; the plugin identity is unchanged.

Which games get it: Mono games on Unity 6000.5 and newer (the one version seen crashing is 6000.5.2), and any Mono
game whose last BepInEx log ends while XUnity was loading, which is the signature of this crash on a version nobody
has reported yet: the next run then switches the wrapper without waiting for a version list to catch up.

Only the Mono / BepInEx 5 wrapper of the pinned XUnity release is replaced, and only when the installed file is
exactly that release's wrapper (or already ours): a hand-installed XUnity of another version is left alone.
"""

from __future__ import annotations

import hashlib
import logging
import re
from enum import Enum
from pathlib import Path

from src.utils.file_ops import safe_write
from src.utils.paths import resource_path

logger = logging.getLogger(__name__)

# First Unity version known to crash (6000.5.2); the whole 6000.5 line is covered until a fixed one is reported.
MIN_UNITY_VERSION: tuple[int, int, int] = (6000, 5, 0)

WRAPPER_DLL = "XUnity.AutoTranslator.Plugin.BepInEx.dll"
WRAPPER_RESOURCE = "src/core/hook_manager/xunity_wrapper"
# SHA256 of the wrapper DLL built from xunity_wrapper/DelayedStart.cs (tools/build_xunity_wrapper.py).
WRAPPER_SHA256 = "83521086e23c5c78c28b5bb5fda54578dff97a88f0d05fa16159208a205b0687"
# SHA256 of the wrapper inside the pinned XUnity.AutoTranslator-BepInEx-5.6.2.zip that it replaces.
ORIGINAL_WRAPPER_SHA256 = "8d54de55fb6c1284d3f381cdfb2be37c9f60f8d5b9cd4e9051f36ff9b024a722"

_UNITY_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)")
# BepInEx writes "Loading [XUnity Auto Translator ...]" before it starts the plugin and XUnity logs
# "Loaded XUnity.AutoTranslator into Unity [...] game." as the last step of its start-up.
_LOG_NAME = "LogOutput.log"
_LOADING_MARK = "Loading [XUnity Auto Translator"
_LOADED_MARK = "Loaded XUnity.AutoTranslator into Unity"
_LOG_TAIL_BYTES = 256 * 1024


class DelayedStartResult(str, Enum):
    """What ``apply_delayed_start`` did."""

    NOT_NEEDED = "not_needed"
    APPLIED = "applied"
    APPLIED_AFTER_CRASH = "applied_after_crash"
    ALREADY = "already"
    SKIPPED_MISSING = "skipped_missing"
    SKIPPED_FOREIGN = "skipped_foreign"
    SKIPPED_NO_WRAPPER = "skipped_no_wrapper"


def unity_needs_delayed_start(unity_version: str) -> bool:
    """True for Unity versions from 6000.5 on; unknown or unparsable versions are left alone."""
    match = _UNITY_VERSION_RE.match(unity_version.strip())
    return match is not None and tuple(int(part) for part in match.groups()) >= MIN_UNITY_VERSION


def plugin_dll_path(root: Path) -> Path:
    """Where the BepInEx 5 wrapper of XUnity.AutoTranslator lives inside a game folder."""
    return root / "BepInEx" / "plugins" / "XUnity.AutoTranslator" / WRAPPER_DLL


def startup_crash_in_log(root: Path) -> bool:
    """True when the last BepInEx log ends while XUnity was starting: it began loading and never finished."""
    log = root / "BepInEx" / _LOG_NAME
    try:
        with open(log, "rb") as handle:
            handle.seek(0, 2)
            handle.seek(max(handle.tell() - _LOG_TAIL_BYTES, 0))
            text = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return False  # no log yet: the game was never started with the hook
    start = text.rfind(_LOADING_MARK)
    return start != -1 and _LOADED_MARK not in text[start:]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def shipped_wrapper() -> Path | None:
    """The wrapper DLL that ships with the application, or None when it is missing or does not match its hash."""
    path = resource_path(WRAPPER_RESOURCE) / WRAPPER_DLL
    if not path.is_file():
        logger.error("The delayed-start wrapper is missing: %s", path)
        return None
    if _sha256(path) != WRAPPER_SHA256:
        logger.error("The delayed-start wrapper %s does not match its recorded SHA256; not using it", path)
        return None
    return path


def apply_delayed_start(root: Path, unity_version: str, is_il2cpp: bool = False) -> DelayedStartResult:
    """Replace XUnity's BepInEx 5 wrapper by the delayed-start one when the game's Unity version needs it."""
    by_version = unity_needs_delayed_start(unity_version)
    after_crash = not by_version and startup_crash_in_log(root)
    if is_il2cpp or not (by_version or after_crash):
        if is_il2cpp and startup_crash_in_log(root):
            logger.warning("The last run of this IL2CPP game ended while XUnity was starting; the delayed-start "
                           "wrapper is only available for Mono games")
        return DelayedStartResult.NOT_NEEDED
    target = plugin_dll_path(root)
    if not target.is_file():
        return DelayedStartResult.SKIPPED_MISSING
    installed = _sha256(target)
    if installed == WRAPPER_SHA256:
        return DelayedStartResult.ALREADY
    if installed != ORIGINAL_WRAPPER_SHA256:
        logger.warning("Unity %s needs the delayed-start wrapper, but %s is not the XUnity release this application "
                       "ships (a hand-installed version?); it is left as it is", unity_version, target)
        return DelayedStartResult.SKIPPED_FOREIGN
    wrapper = shipped_wrapper()
    if wrapper is None:
        return DelayedStartResult.SKIPPED_NO_WRAPPER
    safe_write(target, wrapper.read_bytes())  # the original wrapper stays next to it as a .bak
    logger.info("Unity %s: XUnity Auto Translator now starts a few frames late (%s; the original is kept as .bak)",
                unity_version, "the last run ended while it was starting" if after_crash else "this Unity version needs it")
    return DelayedStartResult.APPLIED_AFTER_CRASH if after_crash else DelayedStartResult.APPLIED
