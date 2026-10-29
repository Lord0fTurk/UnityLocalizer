# -*- coding: utf-8 -*-
"""A scan that would not fit in memory is skipped, reported and visible: bundle sizes, guard, harvest."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest
import UnityPy
from bundle_factory import NODE_SERIALIZED, build_unityfs, build_sparse, unitypy_files

from src.core.engine_profiler import UnityGameProfile
from src.core.harvesters import asset_harvester, memory_guard
from src.core.harvesters.asset_harvester import AssetHarvester
from src.core.harvesters.bundle_header import unityfs_uncompressed_size
from src.core.harvesters.harvest_collector import HarvestCollector
from src.core.harvesters.harvest_stats import FileStat, HarvestStats
from src.core.harvesters.memory_guard import (
    DEFAULT_RAM_FRACTION,
    FileAssessment,
    MemoryGuard,
    available_memory,
    disk_size,
    estimate_peak_bytes,
    format_size,
)
from src.core.progress import NOTIFICATION_LEVELS

MIB = 2**20


PAYLOAD = (b"unity " * 40000) + bytes(range(256)) * 300  # about 316 KiB over several blocks


@pytest.mark.parametrize(
    "kwargs",
    [
        {}, {"version": 6, "engine": "2018.4.30f1"}, {"version": 6, "engine": "2019.4.20f1"},
        {"at_end": True}, {"version": 8, "engine": "6000.0.1f1"},
    ],
    ids=["v7", "v6-unaligned", "v6-2019.4-aligned", "blocks-info-at-end", "v8"],
)
def test_the_header_reader_agrees_with_unitypy(tmp_path: Path, kwargs: dict[str, Any]) -> None:
    blob = build_unityfs(PAYLOAD, **kwargs)
    path = tmp_path / "x.bundle"
    path.write_bytes(blob)
    assert unitypy_files(blob)["CAB-test"] == PAYLOAD  # the hand-built bundle is a real one
    assert unityfs_uncompressed_size(path) == len(PAYLOAD)


@pytest.mark.parametrize("packer", ["lzma", "lz4", "none"])
def test_every_compression_unitypy_can_write_is_read(tmp_path: Path, packer: str) -> None:
    env = UnityPy.load(build_unityfs(PAYLOAD))
    path = tmp_path / f"{packer}.bundle"
    path.write_bytes(env.file.save(packer=packer))
    assert unityfs_uncompressed_size(path) == len(PAYLOAD)


def test_a_huge_stream_costs_only_its_header_to_measure(tmp_path: Path) -> None:
    path = tmp_path / "huge.bundle"
    path.write_bytes(build_unityfs(bytes(256 * MIB)))  # compresses to a few hundred KiB
    assert path.stat().st_size < 4 * MIB
    assert unityfs_uncompressed_size(path) == 256 * MIB


@pytest.mark.parametrize(
    "blob",
    [b"", b"UnityFS", b"not a bundle at all", b"UnityWeb\x00" + b"\x00" * 64, b"UnityFS\x00" + b"\xff" * 40],
    ids=["empty", "truncated", "garbage", "other-format", "corrupt-header"],
)
def test_unreadable_bundles_give_none(tmp_path: Path, blob: bytes) -> None:
    path = tmp_path / "bad.bundle"
    path.write_bytes(blob)
    assert unityfs_uncompressed_size(path) is None


def test_a_damaged_blocks_info_gives_none(tmp_path: Path) -> None:
    blob = bytearray(build_unityfs(PAYLOAD))
    blob[60:90] = b"\xaa" * 30  # inside the compressed blocks info
    path = tmp_path / "damaged.bundle"
    path.write_bytes(bytes(blob))
    assert unityfs_uncompressed_size(path) is None


def test_a_missing_file_gives_none(tmp_path: Path) -> None:
    assert unityfs_uncompressed_size(tmp_path / "gone.bundle") is None


# --- expected peak memory ----------------------------------------------------------------


def test_a_bundle_costs_twice_its_largest_unpacked_file_not_twice_the_bundle(tmp_path: Path) -> None:
    path = tmp_path / "a.bundle"
    path.write_bytes(build_unityfs(nodes=[("CAB-a", bytes(3 * MIB), NODE_SERIALIZED), ("CAB-a.resS", bytes(40 * MIB), 0)]))
    assert estimate_peak_bytes(path) == 2 * (3 * MIB + 64 * 1024)  # the file plus the largest block in flight, twice


def test_a_huge_stream_does_not_count_but_a_huge_serialized_file_does(tmp_path: Path) -> None:
    stream_heavy = tmp_path / "stream.bundle"
    stream_heavy.write_bytes(build_sparse(bytes(2 * MIB), 6 * 2**30))
    serialized_heavy = tmp_path / "serialized.bundle"
    serialized_heavy.write_bytes(build_sparse(bytes(MIB), 6 * 2**30, claimed_path="CAB-sparse.big", claimed_flags=NODE_SERIALIZED))
    assert estimate_peak_bytes(stream_heavy) == 2 * (2 * MIB + 2 * MIB)  # only the 2 MiB file counts: the 6 GiB .resS stays packed
    assert estimate_peak_bytes(serialized_heavy) > 12 * 2**30   # a serialized file of that size is unpacked


def test_a_bundle_with_an_unreadable_header_is_estimated_from_its_size(tmp_path: Path) -> None:
    path = tmp_path / "odd.bundle"
    path.write_bytes(b"UnityFS\x00" + b"\xff" * (2 * MIB))
    assert estimate_peak_bytes(path) == int(path.stat().st_size * 3.0 * 2.0)


def test_other_bundle_formats_are_estimated_from_their_size(tmp_path: Path) -> None:
    path = tmp_path / "old.unity3d"
    path.write_bytes(b"UnityWeb\x00" + b"\x00" * MIB)
    assert estimate_peak_bytes(path) == int(path.stat().st_size * 3.0 * 2.0)


def test_a_plain_serialized_file_costs_about_its_size(tmp_path: Path) -> None:
    path = tmp_path / "level0"
    path.write_bytes(b"\x00" * (5 * MIB))
    assert estimate_peak_bytes(path) == int(5 * MIB * 1.2)


def test_split_parts_count_as_one_file(tmp_path: Path) -> None:
    for number in range(3):
        (tmp_path / f"level1.split{number}").write_bytes(b"\x00" * MIB)
    (tmp_path / "level2.split0").write_bytes(b"\x00" * MIB)  # another file's part
    assert disk_size(tmp_path / "level1.split0") == 3 * MIB
    assert estimate_peak_bytes(tmp_path / "level1.split0") == int(3 * MIB * 1.2)


# --- the guard -------------------------------------------------------------------------


def _guard(free: int | None, enabled: bool = True) -> MemoryGuard:
    return MemoryGuard(enabled=enabled, available=lambda: free)


def test_a_file_fits_up_to_the_share_of_free_memory(tmp_path: Path) -> None:
    path = tmp_path / "level0"
    path.write_bytes(b"\x00" * (10 * MIB))  # needs 12 MiB
    peak = estimate_peak_bytes(path)
    edge = int(peak / DEFAULT_RAM_FRACTION)
    assert _guard(edge + 1).assess(path).fits
    assert not _guard(edge - MIB).assess(path).fits


def test_the_assessment_carries_the_numbers_for_the_warning(tmp_path: Path) -> None:
    path = tmp_path / "a.bundle"
    path.write_bytes(build_unityfs(nodes=[("CAB-a", bytes(8 * MIB), NODE_SERIALIZED)]))
    cost = _guard(4 * MIB).assess(path)
    assert (cost.fits, cost.peak_bytes, cost.available_bytes) == (False, 2 * (8 * MIB + 64 * 1024), 4 * MIB)
    assert cost.disk_bytes == path.stat().st_size


def test_an_unknown_amount_of_free_memory_never_blocks(tmp_path: Path) -> None:
    path = tmp_path / "level0"
    path.write_bytes(b"\x00" * MIB)
    assert _guard(None).assess(path).fits


def test_a_disabled_guard_lets_everything_through_without_reading_headers(tmp_path: Path) -> None:
    path = tmp_path / "a.bundle"
    path.write_bytes(build_unityfs(bytes(8 * MIB)))
    cost = _guard(1, enabled=False).assess(path)
    assert cost.fits and cost.peak_bytes == 0 and cost.disk_bytes == path.stat().st_size


def test_a_vanished_file_is_left_to_the_scan_to_report(tmp_path: Path) -> None:
    cost = _guard(1).assess(tmp_path / "gone.assets")
    assert cost.fits and cost.disk_bytes == 0


def test_available_memory_is_reported_and_failures_become_none(monkeypatch: pytest.MonkeyPatch) -> None:
    assert (available_memory() or 0) > 0
    import psutil

    def broken() -> Any:
        raise OSError("no access")

    monkeypatch.setattr(psutil, "virtual_memory", broken)
    assert available_memory() is None


@pytest.mark.parametrize(
    "size, text",
    [(0, "0 B"), (1023, "1023 B"), (1024, "1.0 KB"), (5 * MIB, "5.0 MB"), (int(3.2 * 2**30), "3.2 GB"), (2**41, "2.0 TB"),
     (2**51, "2048.0 TB")],
)
def test_format_size(size: int, text: str) -> None:
    assert format_size(size) == text


# --- the harvest ---------------------------------------------------------------------


class _Verdict:
    """A guard that rejects files by name."""

    def __init__(self, reject: set[str]) -> None:
        self.reject = reject

    def assess(self, path: Path) -> FileAssessment:
        return FileAssessment(path, 3 * MIB, 16 * MIB, 4 * MIB, path.name not in self.reject)


def _sources(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, names: list[str]) -> list[str]:
    scanned: list[str] = []

    def scan(cls: Any, path: Path, source_lang: str = "en", generator: Any = None, stats: Any = None) -> list[str]:
        scanned.append(path.name)
        return [f"text of {path.name}"]

    monkeypatch.setattr(asset_harvester, "find_serialized_sources", lambda data_dir: [tmp_path / n for n in names])
    monkeypatch.setattr(AssetHarvester, "harvest_asset_file", classmethod(scan))
    return scanned


def test_an_oversized_file_is_skipped_recorded_and_the_rest_is_scanned(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    scanned = _sources(monkeypatch, tmp_path, ["level0", "big.bundle", "level1"])
    stats = HarvestStats()
    with caplog.at_level(logging.WARNING):
        strings = AssetHarvester.harvest_data_dir(tmp_path, stats=stats, memory_guard=_Verdict({"big.bundle"}))  # type: ignore[arg-type]
    assert scanned == ["level0", "level1"] and strings == ["text of level0", "text of level1"]
    (skipped,) = stats.files_skipped_for_memory
    assert (skipped.name, skipped.disk_bytes, skipped.peak_bytes, skipped.available_bytes) == (
        "big.bundle", 3 * MIB, 16 * MIB, 4 * MIB,
    )
    assert "Skipped big.bundle" in caplog.text and "3.0 MB" in caplog.text and "16.0 MB" in caplog.text


def test_progress_names_the_file_and_its_size_even_when_it_is_skipped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sources(monkeypatch, tmp_path, ["level0", "big.bundle"])
    events: list[Any] = []
    AssetHarvester.harvest_data_dir(tmp_path, progress=events.append, memory_guard=_Verdict({"big.bundle"}))  # type: ignore[arg-type]
    shown = [(e.params["name"], e.params["size"]) for e in events if e.key == "pipeline.harvest_asset_file"]
    assert shown == [("level0", "3.0 MB"), ("big.bundle", "3.0 MB")]


def test_a_disabled_guard_scans_every_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    scanned = _sources(monkeypatch, tmp_path, ["level0", "big.bundle"])
    AssetHarvester.harvest_data_dir(tmp_path, memory_guard=MemoryGuard(enabled=False))
    assert scanned == ["level0", "big.bundle"]


def test_a_real_bundle_too_big_for_the_free_memory_is_skipped_end_to_end(tmp_path: Path) -> None:
    folder = tmp_path / "Game_Data" / "AssetBundles"
    folder.mkdir(parents=True)
    (folder / "big.bundle").write_bytes(build_unityfs(bytes(64 * MIB)))  # 128 MiB expected, a few hundred KiB on disk
    stats = HarvestStats()
    tight = MemoryGuard(available=lambda: 64 * MIB)
    assert AssetHarvester.harvest_data_dir(tmp_path / "Game_Data", stats=stats, memory_guard=tight) == []
    assert [f.name for f in stats.files_skipped_for_memory] == ["big.bundle"]
    roomy = HarvestStats()
    AssetHarvester.harvest_data_dir(tmp_path / "Game_Data", stats=roomy, memory_guard=MemoryGuard(available=lambda: 2**33))
    assert roomy.files_skipped_for_memory == [] and [f.name for f in roomy.files] == ["big.bundle"]


def test_stats_report_lists_the_skipped_files() -> None:
    stats = HarvestStats(files=[FileStat("a.assets", strings=3), FileStat(
        "big.bundle", skipped_for_memory=True, disk_bytes=3 * MIB, peak_bytes=16 * MIB, available_bytes=4 * MIB)])
    report = stats.to_report()
    assert report["files_skipped_for_memory"] == [
        {"name": "big.bundle", "size_mb": 3, "expected_peak_mb": 16, "free_memory_mb": 4}
    ]
    assert report["files"][0]["name"] == "big.bundle" and report["files"][0]["skipped_for_memory"] is True


# --- wiring --------------------------------------------------------------------------


def test_the_collector_hands_its_memory_switch_to_the_asset_harvest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: list[bool] = []

    def capture(data_dir: Any, *args: Any, memory_guard: MemoryGuard | None = None, **kwargs: Any) -> list[str]:
        seen.append(bool(memory_guard and memory_guard.enabled))
        return []

    monkeypatch.setattr(AssetHarvester, "harvest_data_dir", staticmethod(capture))
    profile = UnityGameProfile(game_path=tmp_path, data_dir=tmp_path, unity_version="Unknown")
    HarvestCollector()._harvest_assets(profile, None, HarvestStats())
    HarvestCollector(memory_guard=False)._harvest_assets(profile, None, HarvestStats())
    assert seen == [True, False]


class _Config:
    def __init__(self, values: dict[str, Any]) -> None:
        self.values = values

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)


class _Manager:
    def __init__(self, config: _Config | None = None) -> None:
        if config is not None:
            self.config = config

    def get_translator(self, engine: object) -> object:
        return object()


def _pipeline(config: _Config | None = None) -> tuple[Any, list[Any]]:
    from src.core.pipeline.orchestrator import UnityTranslationPipeline

    pipeline = UnityTranslationPipeline(_Manager(config))  # type: ignore[arg-type]
    events: list[Any] = []
    pipeline.progress_callback = events.append
    return pipeline, events


@pytest.mark.parametrize("config, expected", [(None, True), (_Config({}), True), (_Config({"harvest_memory_guard": False}), False)])
def test_the_pipeline_reads_the_memory_guard_setting(config: _Config | None, expected: bool) -> None:
    pipeline, _ = _pipeline(config)
    assert pipeline._collector("en").memory_guard is expected


def test_skipped_files_are_reported_as_a_warning_with_their_sizes() -> None:
    pipeline, events = _pipeline()
    stats = HarvestStats(files=[
        FileStat("a.bundle", skipped_for_memory=True, disk_bytes=3 * 2**30),
        FileStat("b.bundle", skipped_for_memory=True, disk_bytes=700 * MIB),
    ])
    pipeline._report_harvest_coverage(stats)
    (event,) = [e for e in events if e.key == "pipeline.harvest_warn_oversized"]
    assert event.params["count"] == 2 and event.params["names"] == "a.bundle (3.0 GB), b.bundle (700.0 MB)"


def test_the_oversized_warning_is_a_notification_and_the_setting_is_typed() -> None:
    from src.backend.settings_schema import SETTING_SPECS, coerce_setting
    from src.utils.config import DEFAULT_CONFIG

    assert NOTIFICATION_LEVELS["pipeline.harvest_warn_oversized"] == "warning"
    assert SETTING_SPECS["harvest_memory_guard"].kind is bool and DEFAULT_CONFIG["harvest_memory_guard"] is True
    assert coerce_setting("harvest_memory_guard", "off") is False


def test_the_module_reports_which_peak_factors_it_assumes() -> None:
    # The factors are measurements (see the module docstring); changing one should be a conscious act.
    assert (memory_guard.PEAK_FACTOR_BUNDLE, memory_guard.PEAK_FACTOR_SERIALIZED) == (2.0, 1.2)



def test_report_lists_slowest_files_with_time_and_memory() -> None:
    from src.core.harvesters.harvest_stats import FileStat, HarvestStats

    stats = HarvestStats(files=[FileStat("a", seconds=0.5), FileStat("b", seconds=26.2, process_peak_bytes=8 * 2**30)])
    report = stats.to_report()
    assert report["slowest_files"][0] == {"name": "b", "seconds": 26.2, "process_peak_mb": 8192}
    assert {f["name"]: f["seconds"] for f in report["files"]} == {"a": 0.5, "b": 26.2}
