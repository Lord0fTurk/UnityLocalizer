# -*- coding: utf-8 -*-
"""The asset scan worker: results stream back, a dead worker keeps what it sent, Stop ends it at once."""

from __future__ import annotations

import logging
import queue
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from src.core.engine_profiler import UnityGameProfile
from src.core.harvesters import asset_worker
from src.core.harvesters.harvest_stats import FileStat, HarvestStats
from src.core.progress import CancelToken, OperationCancelled, ProgressEvent


class FakeQueue(queue.Queue):
    def close(self) -> None:  # multiprocessing.Queue API the collector calls
        pass

    def cancel_join_thread(self) -> None:
        pass


class FakeProcess:
    def __init__(self, alive: bool = True, exitcode: int | None = None) -> None:
        self.alive, self.exitcode, self.terminated = alive, exitcode, False

    def is_alive(self) -> bool:
        return self.alive

    def terminate(self) -> None:
        self.terminated, self.alive = True, False

    def join(self, timeout: float | None = None) -> None:
        pass


def _event(name: str) -> ProgressEvent:
    return ProgressEvent(key="pipeline.harvest_asset_file", current=1, total=2, params={"name": name})


def test_strings_progress_and_statistics_come_back() -> None:
    out = FakeQueue()
    stats = HarvestStats(encrypted_code=True)
    seen: list[ProgressEvent] = []
    worker_stats = HarvestStats(tables_matched=3)
    for message in [("progress", _event("a")), ("strings", ["Hello", "World"]), ("strings", ["World", "Bye"]),
                    ("done", worker_stats)]:
        out.put(message)
    result = asset_worker._receive(FakeProcess(), out, seen.append, None)
    asset_worker._merge(stats, result.stats)
    assert sorted(result.found) == ["Bye", "Hello", "World"] and result.finished
    assert [e.params["name"] for e in seen] == ["a"] and result.seen == ["a"]
    assert stats.tables_matched == 3 and stats.encrypted_code is True  # the collector's own flag is kept


def test_cancel_ends_the_worker_at_once() -> None:
    cancel = CancelToken()
    cancel.cancel()
    process = FakeProcess()
    with pytest.raises(OperationCancelled):
        asset_worker._receive(process, FakeQueue(), None, cancel)
    assert process.terminated


def test_worker_log_records_are_replayed_in_the_parent(caplog: pytest.LogCaptureFixture) -> None:
    record = logging.LogRecord("src.core.test", logging.WARNING, __file__, 1, "from the child", None, None)
    out = FakeQueue()
    out.put(("log", record))
    out.put(("done", HarvestStats()))
    with caplog.at_level(logging.WARNING):
        asset_worker._receive(FakeProcess(), out, None, None)
    assert "from the child" in caplog.text


def test_a_dead_worker_keeps_what_it_sent_and_its_replacement_continues_after_the_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    runs: list[frozenset[str]] = []
    outcomes = [
        asset_worker._Outcome(found={"First"}, seen=["a.assets", "big.assets"], exitcode=-9,
                              stats=HarvestStats(files=[FileStat("a.assets", strings=1)])),
        asset_worker._Outcome(found={"Last"}, seen=["z.assets"], finished=True,
                              stats=HarvestStats(files=[FileStat("z.assets", strings=1)], tables_matched=2)),
    ]

    def fake_run(profile: Any, lang: str, guard: bool, skip: frozenset[str], *_rest: Any) -> Any:
        runs.append(skip)
        return outcomes[len(runs) - 1]

    monkeypatch.setattr(asset_worker, "_run_worker", fake_run)
    stats = HarvestStats()
    with caplog.at_level(logging.ERROR):
        result = asset_worker.scan_assets_isolated(UnityGameProfile(game_path=tmp_path, data_dir=tmp_path), stats=stats)
    assert result == ["First", "Last"]
    assert runs == [frozenset(), frozenset({"a.assets", "big.assets"})]  # the second worker skips what is done
    assert [(f.name, f.failed) for f in stats.files] == [("a.assets", False), ("big.assets", True), ("z.assets", False)]
    assert stats.tables_matched == 2 and "exit code -9" in caplog.text


def test_a_worker_that_never_reached_a_file_is_not_restarted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = []
    monkeypatch.setattr(asset_worker, "_run_worker", lambda *a: calls.append(1) or asset_worker._Outcome(exitcode=1))
    assert asset_worker.scan_assets_isolated(UnityGameProfile(game_path=tmp_path, data_dir=tmp_path)) == []
    assert len(calls) == 1


def test_restarts_are_bounded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    count = [0]

    def always_dies(*_a: Any) -> Any:
        count[0] += 1
        return asset_worker._Outcome(seen=[f"f{count[0]}"], exitcode=1)

    monkeypatch.setattr(asset_worker, "_run_worker", always_dies)
    asset_worker.scan_assets_isolated(UnityGameProfile(game_path=tmp_path, data_dir=tmp_path))
    assert count[0] == asset_worker.MAX_RESTARTS + 1


def test_the_ceiling_is_a_share_of_free_memory_with_a_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(asset_worker, "available_memory", lambda: 16 * 2**30)
    assert asset_worker._ceiling_bytes(True) == int(16 * 2**30 * asset_worker.DEFAULT_RAM_FRACTION)
    monkeypatch.setattr(asset_worker, "available_memory", lambda: 1 * 2**30)
    assert asset_worker._ceiling_bytes(True) == asset_worker.MIN_CEILING_BYTES
    assert asset_worker._ceiling_bytes(False) is None


@pytest.mark.skipif(sys.platform != "win32", reason="Job Objects exist only on Windows")
def test_a_job_object_makes_an_oversized_allocation_fail_in_the_child_only() -> None:
    from src.utils.job_limit import limit_process_memory

    code = """import sys
sys.stdin.readline()
try:
    bytearray(1 << 30)
    print('ALLOCATED')
except MemoryError:
    print('REFUSED')
"""
    child = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    ceiling = limit_process_memory(child.pid, 300 * 2**20)
    assert ceiling is not None
    out, _ = child.communicate(input="go" + chr(10), timeout=60)
    ceiling.close()
    assert out.strip() == "REFUSED"


def test_a_real_worker_process_scans_a_data_folder(tmp_path: Path) -> None:
    data = tmp_path / "Game_Data"
    data.mkdir()
    (data / "level0").write_bytes(b"not a serialized file")
    events: list[Any] = []
    stats = HarvestStats()
    profile = UnityGameProfile(game_path=tmp_path, data_dir=data)
    assert asset_worker.scan_assets_isolated(profile, progress=events.append, stats=stats) == []
    assert [e.key for e in events] == ["pipeline.harvest_asset_file"]
    assert [f.name for f in stats.files] == ["level0"]


def test_nothing_to_scan_without_a_data_folder(tmp_path: Path) -> None:
    assert asset_worker.scan_assets_isolated(UnityGameProfile(game_path=tmp_path)) == []


def test_the_watchdog_ends_a_worker_that_outgrows_its_limit() -> None:
    import multiprocessing
    import time

    context = multiprocessing.get_context("spawn")
    process = context.Process(target=_grow_memory, daemon=True)
    process.start()
    watchdog = asset_worker._MemoryWatchdog(process, 150 * 2**20, interval=0.05)
    watchdog.start()
    process.join(60)
    watchdog.stop()
    started = time.time()
    assert not process.is_alive() and watchdog.tripped
    assert time.time() - started < 5


def _grow_memory() -> None:  # runs in the child: touch memory a little at a time until ended
    import time

    chunks = []
    while True:
        chunks.append(bytearray(b"x" * (20 * 2**20)))
        time.sleep(0.02)
