# -*- coding: utf-8 -*-
"""Unit tests for QML Lucide icon font and UI assets."""

import glob
import os
import re
from pathlib import Path

from PyQt6.QtCore import QUrl

from src.backend.app_backend import AppBackend

ROOT = os.path.join(os.path.dirname(__file__), "..")
QML_ROOT = os.path.join(ROOT, "src", "gui", "qml")
ICONS_QML = os.path.join(QML_ROOT, "components", "Icons.qml")
ICON_FONT = os.path.join(QML_ROOT, "fonts", "UnityLocalizerIcons.ttf")

ICON_DEF_RE = re.compile(r'readonly property string (\w+): "\x5cu([0-9a-f]{4})"')


def _qml_files():
    return glob.glob(os.path.join(QML_ROOT, "**", "*.qml"), recursive=True)


def _icon_defs():
    with open(ICONS_QML, encoding="utf-8") as fh:
        return {name: int(code, 16) for name, code in ICON_DEF_RE.findall(fh.read())}


def test_every_icon_used_in_qml_is_defined():
    """A misspelled Icons.<name> is undefined in QML and draws nothing silently."""
    defined = set(_icon_defs()) | {"family", "loader"}
    missing = []
    for path in _qml_files():
        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                for name in re.findall(r"\bIcons\.(\w+)", line.split("//", 1)[0]):
                    if name not in defined:
                        missing.append(f"{os.path.relpath(path, QML_ROOT)}:{lineno}: Icons.{name}")
    assert not missing, "Unknown icons:\n" + "\n".join(missing)


def test_icon_font_contains_every_icon():
    """Verify font file exists and contains every codepoint in Icons.qml."""
    assert os.path.exists(ICON_FONT), f"Missing icon font {ICON_FONT}"
    assert os.path.exists(os.path.join(QML_ROOT, "fonts", "LUCIDE_LICENSE.txt"))

    # If fontTools is available, test exact cmap coverage
    try:
        from fontTools.ttLib import TTFont
        font = TTFont(ICON_FONT)
        cmap = font.getBestCmap()
        absent = [name for name, code in _icon_defs().items() if code not in cmap]
        assert not absent, f"Icons.qml codes missing from the font: {absent}"
    except ImportError:
        pass


def test_app_backend_asset_url_resolves_icon():
    """Verify get_asset_url returns a valid file QUrl for application logo."""
    backend = AppBackend()
    url_str = backend.get_asset_url("icon.png")
    assert url_str.startswith("file://")
    url = QUrl(url_str)
    local_path = Path(url.toLocalFile())
    assert local_path.is_file(), f"Asset path not found: {local_path}"
    backend.shutdown()
