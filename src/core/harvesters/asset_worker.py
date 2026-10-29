# -*- coding: utf-8 -*-
"""Runs the asset scan in a child process so Stop works at once and a runaway scan cannot take the app down.

UnityPy and the TypeTree generator spend seconds inside native code that no cancel flag can reach
(26 s on one scene of How to Fish), and a scan that outgrows memory used to drag the whole
application with it. The child process does the scan and streams what it finds back through a queue:
progress events, the strings and statistics of each finished file, the child's log records and, at the
end, a completion mark. The parent polls the queue, so a cancel request ends the child immediately
(``terminate``); everything received until then is kept.

On Windows the child also lives in a Job Object with a memory ceiling (``src.utils.job_limit``):
a scan that outgrows it fails alone; elsewhere a watchdog thread ends a worker whose resident memory
passes the same limit. A child that dies on a file is replaced by a new one that
continues after that file, which is recorded as failed (up to ``MAX_RESTARTS`` times).

If the child cannot be started (a packaging problem, a locked-down system) the scan runs in this
process as before, and a warning says so.
"""

from __future__ import annotations

import logging
import logging.handlers
import multiprocessing
import queue as queue_module
import threading
from dataclasses import dataclass, field, fields
from typing import Any

from src.core.engine_profiler import UnityGameProfile
from src.core.harvesters.asset_harvester import AssetHarvester
from src.core.harvesters.harvest_stats import FileStat, HarvestStats
from src.core.harvesters.memory_guard import DEFAULT_RAM_FRACTION, MemoryGuard, available_memory
from src.core.harvesters.typetree_provider import create_typetree_generator
from src.core.progress import CancelToken, OperationCancelled, ProgressCallback
from src.utils.job_limit import limit_process_memory

logger = logging.getLogger(__name__)

POLL_SECONDS = 0.1
JOIN_SECONDS = 5.0
MAX_RESTARTS = 8
WATCHDOG_SECONDS = 0.1
MIN_CEILING_BYTES = 2 * 2**30  # below this a normal scan could not run at all
_KEPT_BY_PARENT = frozenset({"encrypted_code"})  # set by the collector after the scan, not by the worker


class _RecordForwarder(logging.handlers.QueueHandler):
    """Sends the child's log records to the parent, tagged so they are not mistaken for results."""

    def enqueue(self, record: logging.LogRecord) -> None:
        self.queue.put(("log", record))


def _scan_in_child(
    profile: UnityGameProfile, source_lang: str, guard_enabled: bool, level: int, skip: frozenset[str], out: Any
) -> None:
    """Entry point of the child process: scan, streaming results through ``out``."""
    root = logging.getLogger()
    root.handlers[:] = [_RecordForwarder(out)]
    root.setLevel(level)  # the parent's level: records below it would only be thrown away there
    stats = HarvestStats()

    def file_done(found: list[str]) -> None:
        out.put(("strings", found))
        out.put(("stats", stats))

    try:
        AssetHarvester.harvest_data_dir(
            profile.data_dir, source_lang, create_typetree_generator(profile),
            progress=lambda event: out.put(("progress", event)), stats=stats,
            memory_guard=MemoryGuard(enabled=guard_enabled), on_file=file_done, skip=skip,
        )
        out.put(("done", stats))
    except Exception as exc:  # reported to the parent, which knows what to do with a failed scan
        logger.exception("Asset scan failed in the worker")
        out.put(("error", f"{type(exc).__name__}: {exc}"))


def _stop(process: Any) -> None:
    if process.is_alive():
        process.terminate()
    process.join(JOIN_SECONDS)


def _merge(total: HarvestStats, part: HarvestStats) -> None:
    """Add one worker's statistics to the running total (several workers may share one scan)."""
    for item in fields(HarvestStats):
        if item.name in _KEPT_BY_PARENT:
            continue
        mine, theirs = getattr(total, item.name), getattr(part, item.name)
        if isinstance(mine, list):
            mine.extend(theirs)
        elif isinstance(mine, (int, float)) and not isinstance(mine, bool):
            setattr(total, item.name, mine + theirs)
        elif hasattr(mine, "update"):
            mine.update(theirs)
        else:
            setattr(total, item.name, mine or theirs)


def _ceiling_bytes(memory_guard: bool) -> int | None:
    """The memory one worker may commit: the share of the free memory the guard allows, with a floor."""
    free = available_memory() if memory_guard else None
    return None if free is None else max(MIN_CEILING_BYTES, int(free * DEFAULT_RAM_FRACTION))


class _MemoryWatchdog(threading.Thread):
    """Ends a worker whose resident memory passes ``limit`` bytes (where no Job Object ceiling exists).

    A polling check cannot stop a single allocation, but a scan grows over seconds (8 GB in about
    4 s at worst, so a 100 ms poll sees it long before it matters). The worker dies like any other
    crashed one and a new one continues after the file it was on.
    """

    def __init__(self, process: Any, limit: int, interval: float = WATCHDOG_SECONDS) -> None:
        super().__init__(daemon=True, name="scan-memory-watchdog")
        self._process, self._limit, self._interval = process, limit, interval
        self._stop_event = threading.Event()
        self.tripped = False

    def run(self) -> None:
        import psutil

        try:
            watched = psutil.Process(self._process.pid)
        except psutil.Error as exc:
            logger.warning("The scan worker's memory cannot be watched: %s", exc)
            return
        while not self._stop_event.wait(self._interval):
            try:
                if watched.memory_info().rss > self._limit:
                    self.tripped = True
                    logger.error("The scan worker passed its memory limit (%d MB) and is ended", self._limit >> 20)
                    self._process.terminate()
                    return
            except psutil.Error:
                return  # the worker is already gone

    def stop(self) -> None:
        self._stop_event.set()


def _drain(out: Any) -> list[tuple[str, Any]]:
    messages = []
    while True:
        try:
            messages.append(out.get_nowait())
        except queue_module.Empty:
            return messages


@dataclass
class _Outcome:
    """What one worker sent before it finished or died."""

    found: set[str] = field(default_factory=set)
    stats: HarvestStats = field(default_factory=HarvestStats)
    seen: list[str] = field(default_factory=list)  # files it started, in order; the last one is where it stopped
    finished: bool = False
    error: str | None = None
    exitcode: int | None = None


def _receive(
    process: Any, out: Any, progress: ProgressCallback | None, cancel: CancelToken | None
) -> _Outcome:
    outcome = _Outcome()

    def handle(kind: str, payload: Any) -> None:
        if kind == "strings":
            outcome.found.update(payload)
        elif kind == "stats":
            outcome.stats = payload
        elif kind == "progress":
            name = payload.params.get("name")
            if name and (not outcome.seen or outcome.seen[-1] != name):
                outcome.seen.append(name)
            if progress is not None:
                progress(payload)
        elif kind == "log":
            logging.getLogger(payload.name).handle(payload)
        elif kind == "done":
            outcome.stats, outcome.finished = payload, True
        elif kind == "error":
            outcome.error = payload

    try:
        while not outcome.finished and outcome.error is None:
            if cancel is not None and cancel.is_cancelled:
                raise OperationCancelled()
            try:
                handle(*out.get(timeout=POLL_SECONDS))
            except queue_module.Empty:
                if not process.is_alive():
                    for kind, payload in _drain(out):
                        handle(kind, payload)
                    break
    finally:
        _stop(process)
        out.close()
        out.cancel_join_thread()
    outcome.exitcode = process.exitcode
    return outcome


def _run_worker(
    profile: UnityGameProfile, source_lang: str, memory_guard: bool, skip: frozenset[str],
    progress: ProgressCallback | None, cancel: CancelToken | None,
) -> _Outcome:
    context = multiprocessing.get_context("spawn")
    out = context.Queue()
    level = logging.getLogger().getEffectiveLevel()
    process = context.Process(target=_scan_in_child, args=(profile, source_lang, memory_guard, level, skip, out),
                              daemon=True)
    process.start()
    limit = _ceiling_bytes(memory_guard)
    ceiling = None if limit is None else limit_process_memory(process.pid, limit)
    watchdog = None
    if limit is not None and ceiling is None:  # no Job Object (not Windows, or it was refused): watch from here
        watchdog = _MemoryWatchdog(process, limit)
        watchdog.start()
    try:
        return _receive(process, out, progress, cancel)
    finally:
        if ceiling is not None:
            ceiling.close()
        if watchdog is not None:
            watchdog.stop()


def scan_assets_isolated(
    profile: UnityGameProfile,
    source_lang: str = "en",
    *,
    memory_guard: bool = True,
    progress: ProgressCallback | None = None,
    cancel: CancelToken | None = None,
    stats: HarvestStats | None = None,
) -> list[str]:
    """Unique strings of every serialized file, scanned in a child process.

    Raises ``OperationCancelled`` as soon as ``cancel`` is set (the child is ended at once). A child
    that dies on a file is replaced by one that continues after it; that file is recorded as failed.
    """
    if profile.data_dir is None:
        return []
    stats = stats if stats is not None else HarvestStats()
    found: set[str] = set()
    skip: frozenset[str] = frozenset()
    for _attempt in range(MAX_RESTARTS + 1):
        try:
            outcome = _run_worker(profile, source_lang, memory_guard, skip, progress, cancel)
        except (OSError, RuntimeError, ValueError, ImportError) as exc:  # cannot spawn here
            if skip:
                raise
            logger.warning("Could not start the scan worker (%s); scanning in the main process", exc)
            return AssetHarvester.harvest_data_dir(
                profile.data_dir, source_lang, create_typetree_generator(profile), progress=progress, cancel=cancel,
                stats=stats, memory_guard=MemoryGuard(enabled=memory_guard),
            )
        found |= outcome.found
        _merge(stats, outcome.stats)
        if outcome.finished:
            break
        culprit = outcome.seen[-1] if outcome.seen else None
        reason = outcome.error or f"the worker ended unexpectedly (exit code {outcome.exitcode})"
        logger.error("The asset scan worker stopped: %s (last file: %s)", reason, culprit)
        if culprit is None or outcome.error is not None:
            break  # it never got to a file, or the scan itself failed: another worker would meet the same thing
        stats.files.append(FileStat(culprit, failed=True))
        skip = skip | frozenset(outcome.seen)
    else:
        logger.error("The asset scan worker kept dying; the text found so far is kept")
    return sorted(found)
