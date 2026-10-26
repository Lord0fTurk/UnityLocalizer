# -*- coding: utf-8 -*-
"""Standalone PyInstaller build automation script for UnityLocalizer."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("Builder")


def ensure_pyinstaller() -> bool:
    """Ensure PyInstaller is installed in the current environment."""
    try:
        import PyInstaller  # type: ignore # noqa: F401
        return True
    except ImportError:
        logger.info("PyInstaller not found. Installing via pip...")
        res = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyinstaller"],
            capture_output=True,
            text=True,
            check=False,
        )
        return res.returncode == 0


def get_data_args(root_dir: Path) -> list[str]:
    """Generate PyInstaller --add-data arguments with correct path separators."""
    sep = ";" if sys.platform == "win32" else ":"
    data_items = [
        ("src/gui/qml", "src/gui/qml"),
        ("src/gui/i18n", "src/gui/i18n"),
    ]
    args: list[str] = []
    for src, dst in data_items:
        src_path = root_dir / src
        if src_path.exists():
            args.extend(["--add-data", f"{src_path}{sep}{dst}"])

    for icon in ["icon.ico", "icon.png"]:
        icon_path = root_dir / icon
        if icon_path.exists():
            args.extend(["--add-data", f"{icon_path}{sep}."])

    return args


def get_hidden_imports() -> list[str]:
    """Return required dynamic/hidden module imports for PyQt6 & core."""
    modules = [
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtQml",
        "PyQt6.QtQuick",
        "PyQt6.QtQuickControls2",
        "sqlite3",
        "urllib.request",
        "zipfile",
        "shutil",
        "json",
        "xml.etree.ElementTree",
    ]
    args: list[str] = []
    for mod in modules:
        args.extend(["--hidden-import", mod])
    return args


def get_collect_args() -> list[str]:
    """Packages whose data files or lazily imported modules PyInstaller cannot see.

    UnityPy reads its class database (``resources/lzma.tpk``) through
    importlib.resources and imports helpers lazily; py7zr picks codecs at runtime;
    py3langid loads its language model from a ``data`` file next to the module.
    """
    args: list[str] = [
        "--collect-all", "UnityPy", "--collect-submodules", "py7zr", "--collect-all", "py3langid",
    ]
    return args


def build_binary(root_dir: Path, onefile: bool = False, console: bool = False) -> int:
    """Execute PyInstaller with configured flags."""
    entry_point = root_dir / "run.py"
    icon_file = root_dir / "icon.ico"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "UnityLocalizer",
        "--noconfirm",
        "--clean",
    ]

    cmd.append("--onefile" if onefile else "--onedir")
    cmd.append("--console" if console else "--windowed")

    if icon_file.is_file() and sys.platform == "win32":  # .ico is a Windows icon; other platforms ignore or reject it
        cmd.extend(["--icon", str(icon_file)])

    cmd.extend(get_data_args(root_dir))
    cmd.extend(get_hidden_imports())
    cmd.extend(get_collect_args())
    cmd.append(str(entry_point))

    logger.info("Starting PyInstaller packaging...")
    result = subprocess.run(cmd, cwd=str(root_dir), check=False)
    if result.returncode != 0:
        logger.error("Build failed with returncode %s", result.returncode)
        return result.returncode
    logger.info("Build completed successfully! Output in: %s", root_dir / "dist")
    return verify_binary(root_dir, onefile)


def verify_binary(root_dir: Path, onefile: bool) -> int:
    """Run the frozen app's ``--self-check`` so missing package data fails the build."""
    exe = root_dir / "dist" / ("UnityLocalizer.exe" if onefile else "UnityLocalizer/UnityLocalizer.exe")
    if not exe.is_file():
        exe = exe.with_suffix("")  # Linux/macOS builds have no .exe suffix
    result = subprocess.run([str(exe), "--self-check"], cwd=str(root_dir), check=False, timeout=300)
    if result.returncode != 0:
        logger.error("Frozen self-check failed (see app.log in the user data directory)")
    else:
        logger.info("Frozen self-check passed")
    return result.returncode


def main() -> int:
    """Entry point for build script."""
    parser = argparse.ArgumentParser(description="Build UnityLocalizer standalone executable.")
    parser.add_argument("--onefile", action="store_true", help="Package into a single executable")
    parser.add_argument("--console", action="store_true", help="Keep console window open for debugging")
    args = parser.parse_args()

    root_dir = Path(__file__).resolve().parent
    if not ensure_pyinstaller():
        logger.error("Failed to install or verify PyInstaller.")
        return 1

    return build_binary(root_dir, onefile=args.onefile, console=args.console)


if __name__ == "__main__":
    sys.exit(main())
