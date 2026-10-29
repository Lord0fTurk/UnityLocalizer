# -*- coding: utf-8 -*-
"""A memory ceiling for a child process (Windows Job Object).

A scan that outgrows the free memory makes Windows grow its paging file on the system disk and the
whole PC crawl. Putting the scan worker in a Job Object with a per-process memory limit makes the
operating system refuse the allocation instead: the worker fails (a ``MemoryError`` or a crash)
while the application and the rest of the system stay responsive. The job also kills the worker if
this process dies (``KILL_ON_JOB_CLOSE``), so no orphan keeps eating memory.

Windows only. Elsewhere ``limit_process_memory`` returns None and the caller carries on without a ceiling.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)

_PROCESS_SET_QUOTA = 0x0100
_PROCESS_TERMINATE = 0x0001
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_LIMIT_PROCESS_MEMORY = 0x00000100
_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000


class MemoryCeiling:
    """Handle of the job that holds a limited process; closing it ends the limit (and the process)."""

    def __init__(self, handle: Any, kernel32: Any) -> None:
        self._handle, self._kernel32 = handle, kernel32

    def close(self) -> None:
        if self._handle:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None


def _structures() -> tuple[Any, Any]:
    import ctypes

    class BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", ctypes.c_uint32), ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_uint32),
            ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_uint32), ("SchedulingClass", ctypes.c_uint32),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimits), ("IoInfo", IoCounters), ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    return BasicLimits, ExtendedLimits


def limit_process_memory(pid: int, limit_bytes: int) -> MemoryCeiling | None:
    """Cap the memory a running process may commit; None (logged) when that is not possible here."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    job = kernel32.CreateJobObjectW(None, None)
    process = kernel32.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, pid) if job else None
    try:
        if not job or not process:
            raise OSError(ctypes.get_last_error(), "cannot open the job or the process")
        _basic, extended = _structures()
        info = extended()
        info.BasicLimitInformation.LimitFlags = _LIMIT_PROCESS_MEMORY | _LIMIT_KILL_ON_JOB_CLOSE
        info.ProcessMemoryLimit = int(limit_bytes)
        if not kernel32.SetInformationJobObject(
            job, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(info), ctypes.sizeof(info)
        ):
            raise OSError(ctypes.get_last_error(), "SetInformationJobObject failed")
        if not kernel32.AssignProcessToJobObject(job, process):
            raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject failed")
    except OSError as exc:
        logger.warning("Could not put a memory ceiling on process %s: %s", pid, exc)
        if job:
            kernel32.CloseHandle(job)
        return None
    finally:
        if process:
            kernel32.CloseHandle(process)
    return MemoryCeiling(job, kernel32)
