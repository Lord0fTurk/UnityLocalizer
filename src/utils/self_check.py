# -*- coding: utf-8 -*-
"""Runtime dependency self-check (``run.py --self-check``).

A frozen PyInstaller build can start its UI fine and still miss package data that
is only touched later, e.g. UnityPy's ``lzma.tpk`` class database (needed to read
almost every player build) or py7zr's codec modules. This check loads each of
them once so a broken build fails right after packaging instead of on a user's game.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


def _unitypy_class_database() -> None:
    from UnityPy.helpers.Tpk import get_typetree

    if not get_typetree().ClassInformation:
        raise RuntimeError("UnityPy lzma.tpk is empty")


def _archives() -> None:
    import py7zr  # noqa: F401  (font archive)
    import zipfile  # noqa: F401  (BepInEx archives)


def _rtl_shaping() -> None:
    from src.core.rtl_shaper import shape_line

    if not shape_line("سلام"):
        raise RuntimeError("RTL shaping returned nothing")


def _binary_readers() -> None:
    import pefile  # noqa: F401
    import sqlite3

    sqlite3.connect(":memory:").close()


def _engines() -> None:
    import openai  # noqa: F401
    import rapidfuzz  # noqa: F401
    import requests  # noqa: F401
    from google import genai  # noqa: F401


def _ui_resources() -> None:
    from src.utils.paths import resource_path

    for rel in ("src/gui/qml/Main.qml", "src/gui/i18n/en.json", "src/gui/i18n/tr.json"):
        if not resource_path(rel).is_file():
            raise RuntimeError(f"Missing bundled UI resource: {rel}")


CHECKS: dict[str, Callable[[], None]] = {
    "unitypy-class-database": _unitypy_class_database,
    "archives": _archives,
    "rtl-shaping": _rtl_shaping,
    "binary-readers": _binary_readers,
    "translation-engines": _engines,
    "ui-resources": _ui_resources,
}


def run_self_check() -> list[str]:
    """Run every check; return the names (with errors) of those that failed."""
    failures: list[str] = []
    for name, check in CHECKS.items():
        try:
            check()
        except Exception as exc:  # any failure here means a broken installation
            logger.error("Self-check %s failed: %s", name, exc)
            failures.append(f"{name}: {exc}")
        else:
            logger.info("Self-check %s passed", name)
    return failures
