# -*- coding: utf-8 -*-
"""Detects games that ship code to remove BepInEx (anti-mod protection).

Some games contain a routine such as ``CheckAndRemoveBepInEx`` that deletes the
BepInEx folders and quits shortly after start. The runtime hook (route 3) is then
gone before any text is drawn, so a finished translation never shows up. The check
only reads class/method names from the game's own code (read-only), in the Mono
``Assembly-CSharp*.dll`` or the IL2CPP ``global-metadata.dat`` string pool.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from src.core.engine_profiler import UnityGameProfile

logger = logging.getLogger(__name__)

# Identifiers that name BepInEx together with a removal / detection verb or noun.
_REMOVER_RE = re.compile(
    rb"[A-Za-z_]*(?:(?:Remove|Delete|Detect|Check|Block|Ban|Kill)[A-Za-z_]*BepInEx"
    rb"|BepInEx[A-Za-z_]*(?:Remover|Deleter|Detector|Checker|Blocker|Killer))[A-Za-z_]*"
)
MAX_REPORTED_NAMES = 3


def _code_files(profile: UnityGameProfile) -> list[Path]:
    """Files whose string pools hold the game's own class and method names."""
    data_dir = profile.data_dir
    if data_dir is None:
        return []
    files = sorted((data_dir / "Managed").glob("Assembly-CSharp*.dll"))
    metadata = data_dir / "il2cpp_data" / "Metadata" / "global-metadata.dat"
    if metadata.is_file():
        files.append(metadata)
    return files


def find_bepinex_removers(profile: UnityGameProfile) -> list[str]:
    """Names of routines in the game that remove or detect BepInEx (empty when none)."""
    found: set[str] = set()
    for path in _code_files(profile):
        try:
            data = path.read_bytes()
        except OSError as exc:
            logger.warning("Could not read %s for the anti-mod check: %s", path.name, exc)
            continue
        found.update(match.decode("ascii", errors="ignore") for match in _REMOVER_RE.findall(data))
    return sorted(found)
