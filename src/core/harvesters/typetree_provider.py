# -*- coding: utf-8 -*-
"""Optional TypeTree generator for player builds that ship without serialized TypeTrees.

Release ``level*``/``sharedassets*`` files normally strip MonoBehaviour TypeTrees,
so UnityPy can only read their base fields. When the optional native package
``TypeTreeGeneratorAPI`` is installed, script layouts are rebuilt from the game's
own assemblies (Mono ``Managed/*.dll`` or IL2CPP ``GameAssembly.dll`` + metadata).
Without it the harvester transparently falls back to raw length-prefixed scanning.
"""

from __future__ import annotations

import logging
from typing import Any

from src.core.engine_profiler import UnityGameProfile

logger = logging.getLogger(__name__)


def _new_generator(unity_version: str) -> Any | None:
    """Instantiate UnityPy's generator; None when the native API is not installed."""
    try:
        from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator

        return TypeTreeGenerator(unity_version)
    except ImportError as exc:
        logger.info("TypeTree generator unavailable (%s); using raw string scanning", exc)
        return None


def _load_assemblies(generator: Any, profile: UnityGameProfile) -> None:
    """Feed the game's script assemblies into the generator."""
    if profile.data_dir is None:
        raise FileNotFoundError("Game data directory not found")
    if profile.is_il2cpp:
        if profile.metadata_encrypted:
            raise ValueError("IL2CPP metadata is encrypted; skipping TypeTree generation")
        game_assembly = profile.game_path / "GameAssembly.dll"
        metadata = profile.data_dir / "il2cpp_data" / "Metadata" / "global-metadata.dat"
        if not game_assembly.is_file() or not metadata.is_file():
            raise FileNotFoundError("IL2CPP GameAssembly.dll or global-metadata.dat not found")
        generator.load_il2cpp(game_assembly.read_bytes(), metadata.read_bytes())
    else:
        managed = profile.data_dir / "Managed"
        if not managed.is_dir():
            raise FileNotFoundError("Managed directory not found")
        generator.load_local_dll_folder(str(managed))


def create_typetree_generator(profile: UnityGameProfile) -> Any | None:
    """Return a loaded generator for the game, or None when it cannot be built."""
    if not profile.unity_version or profile.unity_version == "Unknown":
        return None
    if profile.is_il2cpp and profile.metadata_encrypted:
        return None
    generator = _new_generator(profile.unity_version)
    if generator is None:
        return None
    try:
        _load_assemblies(generator, profile)
    except Exception as exc:  # native loader raises heterogeneous errors (encrypted metadata, bad PE)
        logger.warning("TypeTree generator could not load game assemblies: %s", exc)
        return None
    logger.info("TypeTree generator ready for Unity %s", profile.unity_version)
    return generator
