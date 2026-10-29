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


def _language_detection() -> None:
    from src.core.lang_detect.offline_detector import detect_offline

    english = ["The quick brown fox jumps over the lazy dog near the river bank."] * 10
    result = detect_offline(english)
    if result is None or result[0] != "en":
        raise RuntimeError(f"Offline language model gave {result!r} for English text")


def _typetree_generator() -> None:
    from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator

    TypeTreeGenerator("2022.3.0f1")  # raises ImportError when the native TypeTreeGeneratorAPI is missing


def _memory_guard() -> None:
    import lz4.block  # noqa: F401  (bundle blocks)
    import lzma  # noqa: F401  (LZMA bundles)

    from src.core.harvesters.bundle_unpack import unpack_nodes  # noqa: F401
    from src.core.harvesters.memory_guard import available_memory

    if not available_memory():
        raise RuntimeError("psutil could not report the available memory")


def _scan_worker() -> None:
    """The asset scan runs in a spawned child process: start one on an empty folder and get its answer."""
    import tempfile
    from pathlib import Path

    from src.core.engine_profiler import UnityGameProfile
    from src.core.harvesters.asset_worker import scan_assets_isolated

    with tempfile.TemporaryDirectory() as folder:
        data = Path(folder) / "Game_Data"
        data.mkdir()
        if scan_assets_isolated(UnityGameProfile(game_path=Path(folder), data_dir=data)) != []:
            raise RuntimeError("the scan worker returned text for an empty folder")


def _text_encoding() -> None:
    from src.core.parsers.text_encoding import decode_bytes

    sample = "ゲームを始める。ようこそ、旅人よ。" * 4
    decoded = decode_bytes(sample.encode("cp932"), "ja")
    if decoded is None or decoded.text != sample:
        raise RuntimeError("Shift-JIS text was not decoded; charset-normalizer is broken or missing")


def _xml_patching() -> None:
    from src.core.parsers.xml_text import translate_xml

    source = '<?xml version="1.0"?><r xmlns:x="urn:x"><!-- c --><i><![CDATA[Hello <b>there</b>]]></i></r>'
    patched = translate_xml(source, {"Hello <b>there</b>": "Merhaba"})
    if patched is None or "<!-- c -->" not in patched or "<![CDATA[Merhaba]]>" not in patched:
        raise RuntimeError(f"lxml did not keep the comment and CDATA section: {patched!r}")


def _ui_resources() -> None:
    from src.utils.paths import resource_path

    for rel in ("src/gui/qml/Main.qml", "src/gui/i18n/en.json", "src/gui/i18n/tr.json"):
        if not resource_path(rel).is_file():
            raise RuntimeError(f"Missing bundled UI resource: {rel}")


CHECKS: dict[str, Callable[[], None]] = {
    "unitypy-class-database": _unitypy_class_database,
    "typetree-generator": _typetree_generator,
    "memory-guard": _memory_guard,
    "scan-worker": _scan_worker,
    "archives": _archives,
    "rtl-shaping": _rtl_shaping,
    "binary-readers": _binary_readers,
    "translation-engines": _engines,
    "language-detection": _language_detection,
    "text-encoding": _text_encoding,
    "xml-patching": _xml_patching,
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
