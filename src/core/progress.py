# -*- coding: utf-8 -*-
"""Locale-neutral progress events emitted by core services.

Core never builds user-facing sentences; it emits an i18n key plus parameters and
the UI layer resolves them through ``src/gui/i18n/*.json``.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable


class OperationCancelled(Exception):
    """Raised at a safe checkpoint after the user asked to stop a long operation."""


class CancelToken:
    """Thread-safe cooperative cancellation flag checked between work units."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        """Abort the current operation at a checkpoint where nothing is half-written."""
        if self._event.is_set():
            raise OperationCancelled()


def checkpoint(token: CancelToken | None) -> None:
    """Raise OperationCancelled when an optional token was cancelled."""
    if token is not None:
        token.raise_if_cancelled()


@dataclass(frozen=True)
class ProgressEvent:
    """A progress update identified by an i18n key."""

    key: str
    current: int = 0
    total: int = 0
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def fraction(self) -> float:
        """Completion ratio in [0, 1]; 0 when total is unknown."""
        return min(1.0, self.current / self.total) if self.total > 0 else 0.0

    def message_params(self) -> dict[str, Any]:
        """i18n template parameters, including ``{current}``/``{total}`` counters."""
        return {"current": self.current, "total": self.total, **self.params}


class ProgressLogFilter:
    """Selects which progress events deserve a console line.

    Progress bars consume every event, but logging each download chunk or batch
    floods the console and evicts older entries. A line is logged when the phase
    (event key) changes, at every ``step`` of completion, and once on completion.
    """

    def __init__(self, step: float = 0.1) -> None:
        self.step = step
        self._key: str | None = None
        self._next_milestone = 0.0
        self._completed = False

    def should_log(self, event: ProgressEvent) -> bool:
        """True for a phase's first event, each milestone crossing and its final event."""
        if event.key != self._key:
            self._key = event.key
            self._completed = event.total > 0 and event.current >= event.total
            self._next_milestone = self._milestone_after(event.fraction)
            return True
        if event.total <= 0 or self._completed:
            return False
        if event.current >= event.total:
            self._completed = True
            return True
        if event.fraction >= self._next_milestone:
            self._next_milestone = self._milestone_after(event.fraction)
            return True
        return False

    def _milestone_after(self, fraction: float) -> float:
        """Next milestone strictly above fraction."""
        return (int(round(fraction / self.step, 9)) + 1) * self.step


ProgressCallback = Callable[[ProgressEvent], None]

# Events the user must notice (toast + warning-level log) instead of only a console line.
NOTIFICATION_LEVELS: dict[str, str] = {
    "pipeline.source_detected_offline": "info",
    "pipeline.source_detected_online": "info",
    "pipeline.source_detect_failed": "warning",
    "font.version_unknown": "warning",
    "font.coverage_missing": "warning",
}


def emit(callback: ProgressCallback | None, key: str, current: int = 0, total: int = 0, **params: Any) -> None:
    """Invoke the callback with a new event when one is registered."""
    if callback is not None:
        callback(ProgressEvent(key=key, current=current, total=total, params=params))
