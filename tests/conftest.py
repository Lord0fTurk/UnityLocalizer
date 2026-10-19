# -*- coding: utf-8 -*-
"""Test-session isolation: never read or write the user's real data directory."""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

_SESSION_DATA_DIR = Path(tempfile.mkdtemp(prefix="unitylocalizer_tests_"))


def pytest_configure(config: pytest.Config) -> None:
    """Point every default path (config, glossary, cache, logs) at a throwaway folder."""
    os.environ["UNITYLOCALIZER_DATA_DIR"] = str(_SESSION_DATA_DIR)
    from src.utils.paths import reset_data_dir_cache

    reset_data_dir_cache()


def pytest_unconfigure(config: pytest.Config) -> None:
    """Remove the temporary test data directory when the test session ends."""
    shutil.rmtree(_SESSION_DATA_DIR, ignore_errors=True)
