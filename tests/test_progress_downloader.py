# -*- coding: utf-8 -*-
"""Unit tests for ProgressEvent and cached Downloader."""

import hashlib
import io
from pathlib import Path

import pytest

from src.core.progress import ProgressEvent, emit
from src.utils.downloader import IntegrityError, RemoteFile, download_cached


def test_progress_event_fraction() -> None:
    """Verify ProgressEvent fraction calculations and boundary guards."""
    ev1 = ProgressEvent(key="test.step", current=50, total=100)
    assert ev1.fraction == 0.5

    ev_zero = ProgressEvent(key="test.zero", current=0, total=0)
    assert ev_zero.fraction == 0.0

    ev_overflow = ProgressEvent(key="test.over", current=150, total=100)
    assert ev_overflow.fraction == 1.0


def test_progress_emit() -> None:
    """Verify emit correctly constructs and dispatches ProgressEvent."""
    received: list[ProgressEvent] = []

    emit(received.append, "installer.extracting", current=1, total=5, name="test.zip")
    assert len(received) == 1
    assert received[0].key == "installer.extracting"
    assert received[0].current == 1
    assert received[0].total == 5
    assert received[0].params == {"name": "test.zip"}

    # None callback must not raise
    emit(None, "ignored.event")


def test_downloader_cached_hit(tmp_path: Path, monkeypatch) -> None:
    """Verify download_cached returns existing file without network requests."""
    # Point cache dir to tmp_path
    monkeypatch.setattr("src.utils.downloader.get_cache_dir", lambda: tmp_path)

    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir(parents=True)
    cached_file = hooks_dir / "test_package.zip"
    payload = b"A" * 15_000
    cached_file.write_bytes(payload)

    events: list[ProgressEvent] = []
    remote = RemoteFile("https://invalid.example.com/test_package.zip", hashlib.sha256(payload).hexdigest())
    result = download_cached(remote, progress=events.append, subdir="hooks")

    assert result == cached_file
    assert any(e.key == "download.cached" and e.params.get("name") == "test_package.zip" for e in events)


class _FakeResponse(io.BytesIO):
    headers: dict[str, str] = {}

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _serve(monkeypatch: pytest.MonkeyPatch, body: bytes) -> list[str]:
    requested: list[str] = []

    def fake_urlopen(request, timeout: float = 0) -> _FakeResponse:  # type: ignore[no-untyped-def]
        requested.append(request.full_url)
        return _FakeResponse(body)

    monkeypatch.setattr("src.utils.downloader.urllib.request.urlopen", fake_urlopen)
    return requested


def test_downloader_replaces_corrupted_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.utils.downloader.get_cache_dir", lambda: tmp_path)
    good = b"real archive"
    (tmp_path / "hooks").mkdir()
    (tmp_path / "hooks" / "pkg.zip").write_bytes(b"truncated")
    requested = _serve(monkeypatch, good)

    result = download_cached(RemoteFile("https://example.com/pkg.zip", hashlib.sha256(good).hexdigest()))
    assert requested == ["https://example.com/pkg.zip"]
    assert result.read_bytes() == good


def test_downloader_rejects_tampered_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.utils.downloader.get_cache_dir", lambda: tmp_path)
    _serve(monkeypatch, b"tampered")
    remote = RemoteFile("https://example.com/pkg.zip", hashlib.sha256(b"expected").hexdigest())

    with pytest.raises(IntegrityError):
        download_cached(remote)
    assert list((tmp_path / "hooks").iterdir()) == []  # neither the file nor a .part is kept


def test_message_params_include_counters() -> None:
    from src.core.progress import ProgressEvent

    event = ProgressEvent("download.progress", 3, 10, {"name": "a.7z"})
    assert event.message_params() == {"current": 3, "total": 10, "name": "a.7z"}


def test_progress_log_filter_logs_milestones_only() -> None:
    from src.core.progress import ProgressEvent, ProgressLogFilter

    log_filter = ProgressLogFilter(step=0.1)
    logged = [
        e.current for e in (ProgressEvent("pipeline.translating", i, 7948) for i in range(25, 7949, 25))
        if log_filter.should_log(e)
    ] + [c for c in [7948] if log_filter.should_log(ProgressEvent("pipeline.translating", 7948, 7948))]
    assert logged[0] == 25
    assert len(logged) == 11  # first event + 9 milestones + completion, no duplicate completion


def test_progress_log_filter_unknown_total_and_phase_change() -> None:
    from src.core.progress import ProgressEvent, ProgressLogFilter

    log_filter = ProgressLogFilter()
    chunks = [log_filter.should_log(ProgressEvent("download.progress", n * 65536, 0)) for n in range(1, 300)]
    assert chunks.count(True) == 1
    assert log_filter.should_log(ProgressEvent("download.done", 1, 1)) is True
    assert log_filter.should_log(ProgressEvent("download.progress", 1, 100)) is True
