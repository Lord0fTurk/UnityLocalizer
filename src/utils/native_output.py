# -*- coding: utf-8 -*-
"""Discards what a native library prints to the process's standard output.

``TypeTreeGeneratorAPI`` is a .NET library that writes one "Error generating tree nodes" line per
script it cannot describe (74,584 lines for a single IL2CPP game) with ``Console.WriteLine``,
which Python's own ``sys.stdout`` never sees. Standard error is left alone, so the application's
log lines and Qt warnings still show.

The .NET runtime opens its console stream the first time it prints and keeps it for the life of
the process. Whatever is redirected at that moment must therefore never be closed afterwards:
redirecting Windows' descriptor 1 to a file and restoring it closed the handle .NET had cached,
and the next harvest crashed the whole process ("The handle is invalid"). So on Windows the
process's standard-output handle is set to NULL for the duration instead (.NET answers a NULL
handle with a null stream) and nothing is ever closed; elsewhere descriptor 1 is pointed at
``/dev/null`` (.NET duplicates the descriptor on first use, so restoring it is safe).
"""

from __future__ import annotations

import contextlib
import logging
import os
import sys
import threading
from collections.abc import Callable, Iterator

logger = logging.getLogger(__name__)

_STDOUT_FD = 1
_WINDOWS_STD_OUTPUT_HANDLE = -11 & 0xFFFFFFFF  # STD_OUTPUT_HANDLE as an unsigned DWORD

Restore = Callable[[], None]

_lock = threading.Lock()
_depth = 0
_restore: Restore | None = None


def _nothing_to_restore() -> None:
    return None


def _flush_python_streams() -> None:
    for stream in (sys.stdout, sys.__stdout__):
        if stream is not None:
            with contextlib.suppress(OSError, ValueError):  # closed stream or no console: nothing to flush
                stream.flush()


def _discard_with_descriptor() -> Restore:
    """Point descriptor 1 at the null device (POSIX); the returned callable puts it back."""
    try:
        saved = os.dup(_STDOUT_FD)
    except OSError:
        return _nothing_to_restore  # no standard output at all: nothing is printed anywhere
    try:
        with open(os.devnull, "wb") as null:
            os.dup2(null.fileno(), _STDOUT_FD)
    except OSError as exc:
        logger.warning("Could not silence native output: %s", exc)
        os.close(saved)
        return _nothing_to_restore

    def restore() -> None:
        os.dup2(saved, _STDOUT_FD)
        os.close(saved)

    return restore


def _discard_with_windows_handle() -> Restore:
    """Set the process's standard-output handle to NULL (Windows); the returned callable resets it."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel32.GetStdHandle.restype = ctypes.c_void_p
    kernel32.SetStdHandle.argtypes = [wintypes.DWORD, ctypes.c_void_p]
    kernel32.SetStdHandle.restype = wintypes.BOOL
    original = kernel32.GetStdHandle(_WINDOWS_STD_OUTPUT_HANDLE)
    if not kernel32.SetStdHandle(_WINDOWS_STD_OUTPUT_HANDLE, None):
        logger.warning("Could not silence native output (error %s)", ctypes.get_last_error())
        return _nothing_to_restore
    return lambda: bool(kernel32.SetStdHandle(_WINDOWS_STD_OUTPUT_HANDLE, original)) or None


def _begin_discard() -> Restore:
    return _discard_with_windows_handle() if sys.platform == "win32" else _discard_with_descriptor()


@contextlib.contextmanager
def discard_native_stdout() -> Iterator[None]:
    """Drop what native code prints to standard output inside the block, then restore it.

    The change is process-wide, so it is counted: nested or concurrent uses share one
    redirect and the last one to leave restores the original output.
    """
    global _depth, _restore
    _flush_python_streams()
    with _lock:
        if _depth == 0:
            _restore = _begin_discard()
        _depth += 1
    try:
        yield
    finally:
        _flush_python_streams()
        with _lock:
            _depth -= 1
            if _depth == 0 and _restore is not None:
                _restore()
                _restore = None
