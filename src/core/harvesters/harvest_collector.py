# -*- coding: utf-8 -*-
"""Aggregates every static text channel of a Unity game into one deduplicated pool."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.core.engine_profiler import UnityGameProfile
from src.core.harvesters.asset_harvester import AssetHarvester
from src.core.harvesters.assembly_harvester import AssemblyHarvester
from src.core.harvesters.metadata_harvester import MetadataHarvester
from src.core.harvesters.typetree_provider import create_typetree_generator
from src.core.parsers.streaming_assets import SUPPORTED_SUFFIXES, StreamingAssetsParser
from src.core.progress import CancelToken, ProgressCallback, checkpoint, emit

logger = logging.getLogger(__name__)


@dataclass
class HarvestResult:
    """Deduplicated strings plus the loose files they came from."""

    strings: list[str] = field(default_factory=list)
    streaming_files: list[Path] = field(default_factory=list)
    per_channel: dict[str, int] = field(default_factory=dict)


class HarvestCollector:
    """Runs asset, code and StreamingAssets harvesters for a profiled game."""

    def __init__(self, progress: ProgressCallback | None = None, source_lang: str = "en") -> None:
        self.progress = progress
        self.source_lang = source_lang

    def collect(self, profile: UnityGameProfile, cancel: CancelToken | None = None) -> HarvestResult:
        """Harvest all channels and return the merged result (cancellable between channels)."""
        pool: dict[str, None] = {}
        result = HarvestResult()
        channels = (
            ("assets", lambda p: self._harvest_assets(p, cancel)),
            ("code", self._harvest_code),
            ("streaming", lambda p: self._harvest_streaming(p, result)),
        )
        for index, (name, harvester) in enumerate(channels, start=1):
            checkpoint(cancel)
            emit(self.progress, f"pipeline.harvest_{name}", index, len(channels))
            strings = harvester(profile)
            result.per_channel[name] = len(strings)
            pool.update(dict.fromkeys(strings))
        result.strings = list(pool)
        emit(self.progress, "pipeline.harvest_done", len(channels), len(channels), count=len(pool))
        logger.info("Harvest per channel: %s", result.per_channel)
        return result

    def _harvest_assets(self, profile: UnityGameProfile, cancel: CancelToken | None) -> list[str]:
        """Scenes, shared assets, data.unity3d and AssetBundles (per-file progress and cancel)."""
        if not profile.data_dir:
            return []
        generator = create_typetree_generator(profile)
        return AssetHarvester.harvest_data_dir(
            profile.data_dir, self.source_lang, generator, progress=self.progress, cancel=cancel
        )

    @staticmethod
    def _harvest_code(profile: UnityGameProfile) -> list[str]:
        """C# string literals from Mono assemblies or IL2CPP metadata."""
        if profile.data_dir is None:
            return []
        if not profile.is_il2cpp:
            return AssemblyHarvester.harvest_managed_dir(profile.data_dir / "Managed")
        if profile.metadata_encrypted:
            logger.warning("IL2CPP metadata is encrypted; code strings are left to the runtime route")
            return []
        metadata = profile.data_dir / "il2cpp_data" / "Metadata" / "global-metadata.dat"
        if not metadata.is_file():
            logger.warning("IL2CPP metadata not found at %s", metadata)
            return []
        try:
            return MetadataHarvester.harvest(metadata)
        except ValueError as exc:
            logger.warning("IL2CPP metadata unreadable (likely encrypted): %s", exc)
            return []

    _IGNORED_STREAMING_NAMES = ("lovense", "analytics", "steam", "telemetry", "hardware")
    _IGNORED_ADDRESSABLES_FILES = frozenset({"catalog.json", "settings.json", "link.xml"})

    @classmethod
    def _is_ignored_streaming_file(cls, path: Path, sa_dir: Path) -> bool:
        lower_name = path.name.lower()
        if any(ig in lower_name for ig in cls._IGNORED_STREAMING_NAMES):
            return True
        try:
            rel_parts = [p.lower() for p in path.relative_to(sa_dir).parts]
        except ValueError:
            rel_parts = [lower_name]
        if "aa" in rel_parts or "addressables" in rel_parts:
            return True
        return lower_name in cls._IGNORED_ADDRESSABLES_FILES

    def _harvest_streaming(self, profile: UnityGameProfile, result: HarvestResult) -> list[str]:
        """Loose JSON/CSV/TSV/XML/TXT/Yarn files under StreamingAssets."""
        if profile.data_dir is None:
            return []
        sa_dir = profile.data_dir / "StreamingAssets"
        if not sa_dir.is_dir():
            return []
        parser = StreamingAssetsParser(source_lang=self.source_lang)
        strings: list[str] = []
        for path in sorted(sa_dir.rglob("*")):
            if (
                path.is_file()
                and path.suffix.lower() in SUPPORTED_SUFFIXES
                and not self._is_ignored_streaming_file(path, sa_dir)
            ):
                found = parser.extract_strings(path)
                if found:
                    result.streaming_files.append(path)
                    strings.extend(found)
        return strings
