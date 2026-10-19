# -*- coding: utf-8 -*-
"""Tests for application logging: module loggers reach app.log and secrets are masked."""

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from src.utils import logger as logger_module


@pytest.fixture()
def log_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    root = logging.getLogger()
    level = root.level
    monkeypatch.setattr(logger_module, "get_logs_dir", lambda: tmp_path)
    logger_module.setup_logger(log_file="test.log")
    yield tmp_path / "test.log"
    # pytest swaps its own capture handlers between phases, so find ours by their filter.
    for handler in [h for h in root.handlers if any(isinstance(f, logger_module.SensitiveDataFilter) for f in h.filters)]:
        root.removeHandler(handler)
        handler.close()
    root.setLevel(level)


def test_module_loggers_reach_the_log_file(log_file: Path) -> None:
    logging.getLogger("src.core.pipeline.orchestrator").info("Unified harvest: 42 unique strings")
    logging.getLogger("urllib3.connectionpool").info("third-party chatter")
    content = log_file.read_text(encoding="utf-8")
    assert "Unified harvest: 42 unique strings" in content
    assert "third-party chatter" not in content


def test_secrets_are_masked(log_file: Path) -> None:
    log = logging.getLogger("src.core.translators.deepl")
    log.warning("key=%s", "sk-abcdefghijklmnopqrstuvwxyz123456")
    log.warning("DeepL key 0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0:fx rejected")
    log.warning("header DeepL-Auth-Key 0f1e2d3c-secret")
    content = log_file.read_text(encoding="utf-8")
    assert "sk-abcdef" not in content and "0f1e2d3c" not in content
    assert content.count("[REDACTED_API_KEY]") == 3


def test_setup_is_idempotent(log_file: Path) -> None:
    root = logging.getLogger()
    count = len(root.handlers)
    logger_module.setup_logger(log_file="test.log")
    assert len(root.handlers) == count
