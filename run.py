# -*- coding: utf-8 -*-
"""
UnityLocalizer — Desktop Launcher
High-performance localization automation suite for Unity games.
"""

from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path
from types import TracebackType

# Qt environment variables (MUST be set before importing PyQt6)
os.environ["QT_QPA_PLATFORM_THEME"] = ""
os.environ["QT_STYLE_OVERRIDE"] = ""
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Material"
os.environ["QT_QUICK_CONTROLS_MATERIAL_THEME"] = "Dark"
os.environ["QT_QUICK_CONTROLS_MATERIAL_ACCENT"] = "Purple"

if "QT_LOGGING_RULES" not in os.environ:
    os.environ["QT_LOGGING_RULES"] = "qt.qpa.fonts*=false;qt.text.font.db*=false;*.debug=false"

# Windows: Let Qt 6 handle Per-Monitor V2 DPI awareness natively
if sys.platform == "win32":
    # Taskbar identity
    try:
        import ctypes
        shell32 = ctypes.windll.shell32
        shell32.SetCurrentProcessExplicitAppUserModelID("UnityLocalizer")
    except (AttributeError, OSError) as exc:  # cosmetic only: taskbar grouping/icon
        print(f"Could not set the taskbar app ID: {exc}", file=sys.stderr)

warnings.filterwarnings("ignore", category=SyntaxWarning)

# Ensure root directory is on sys.path
WORK_DIR = Path(__file__).resolve().parent
if not getattr(sys, "frozen", False):
    os.chdir(WORK_DIR)
sys.path.insert(0, str(WORK_DIR))

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QGuiApplication, QIcon
from PyQt6.QtQml import QQmlApplicationEngine

from src.backend.app_backend import AppBackend
from src.backend.editor_backend import EditorBackend
from src.backend.locale_manager import LocaleManager
from src.utils.logger import setup_logger
from src.utils.data_migration import migrate_legacy_data
from src.utils.paths import get_data_dir, resource_path

logger = setup_logger()


def _global_exception_handler(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: TracebackType | None,
) -> None:
    """Log unhandled exceptions to crash log."""
    if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    import traceback
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logger.critical("Unhandled exception:\n%s", error_msg)
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _global_exception_handler


def main() -> int:
    """Launch PyQt6 application and load QML dashboard (``--self-check`` verifies dependencies)."""
    if "--self-check" in sys.argv[1:]:
        from src.utils.self_check import run_self_check

        failures = run_self_check()
        logger.info("Self-check %s", "passed" if not failures else "FAILED: " + "; ".join(failures))
        return 1 if failures else 0

    logger.info("Starting UnityLocalizer...")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("UnityLocalizer")
    app.setOrganizationName("UnityLocalizer")

    # Set icon if present
    for icon_name in ["icon.png", "icon.ico"]:
        icon_path = resource_path(icon_name)
        if icon_path.is_file():
            app.setWindowIcon(QIcon(str(icon_path)))
            break

    # Copy pre-data-directory user data (config, glossary, cache, logs) once.
    migrate_legacy_data()
    logger.info("User data directory: %s", get_data_dir())

    # Initialize backend bridges (keep unparented to prevent premature C++ destruction)
    app_backend = AppBackend()
    editor_backend = EditorBackend(translation_manager=app_backend.tm, pipeline=app_backend.pipeline)
    app_backend.reviewReady.connect(editor_backend.loadSession)
    locale_manager = LocaleManager(default_lang=str(app_backend.config.get("ui_language", "tr") or "tr"))
    locale_manager.languageChanged.connect(app_backend.onUiLanguageChanged)
    locale_manager.languageChanged.connect(editor_backend.onUiLanguageChanged)

    # Initialize QML engine
    engine = QQmlApplicationEngine()

    # Register context properties
    ctx = engine.rootContext()
    ctx.setContextProperty("appBackend", app_backend)
    ctx.setContextProperty("editorBackend", editor_backend)
    ctx.setContextProperty("localeManager", locale_manager)

    # Add QML import path
    qml_dir = resource_path("src/gui/qml")
    engine.addImportPath(str(qml_dir))

    # Load main QML
    qml_path = qml_dir / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))

    if not engine.rootObjects():
        logger.fatal("Failed to load QML root object from %s", qml_path)
        return 1

    logger.info("UI loaded successfully.")
    app_backend.restoreLastSession()
    
    # Auto-quit in headless smoke test mode if flag set
    if os.environ.get("UNITYLOCALIZER_SMOKE_TEST") == "1":
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, app.quit)

    exit_code = app.exec()

    # Explicit teardown order: Clean up QML engine first, then backend
    del engine
    app_backend.shutdown()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
