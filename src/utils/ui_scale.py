# -*- coding: utf-8 -*-
"""Interface size: one global zoom that Qt applies before the first window exists.

``QT_SCALE_FACTOR`` scales text, controls, icons and spacing together, so the type
hierarchy stays as designed and large screens (or low vision) get a bigger interface
without touching any font size in the QML. Qt reads the variable only while the
application object is created, so the choice takes effect on the next start.
"""

from __future__ import annotations

import logging
import os
from collections.abc import MutableMapping
from pathlib import Path

from src.utils.config import ConfigManager

logger = logging.getLogger(__name__)

# Percent values offered in Settings, as strings so they fit the typed choice schema.
UI_SCALE_CHOICES: tuple[str, ...] = ("100", "115", "130", "150")
DEFAULT_UI_SCALE = "100"
SCALE_ENV_VAR = "QT_SCALE_FACTOR"


def scale_factor(value: object) -> float:
    """Return the Qt scale factor for a stored percent value (1.0 for anything unknown)."""
    text = str(value).strip()
    if text not in UI_SCALE_CHOICES:
        return 1.0
    return int(text) / 100


def apply_ui_scale(
    config_path: Path | str | None = None,
    environ: MutableMapping[str, str] | None = None,
) -> float:
    """Export ``QT_SCALE_FACTOR`` from the saved setting; call before ``QGuiApplication``.

    A factor the user already set in the environment wins, so launchers and
    debugging sessions keep full control. Returns the factor that will be used.
    """
    env = os.environ if environ is None else environ
    if SCALE_ENV_VAR in env:
        logger.info("Interface size: %s=%s comes from the environment", SCALE_ENV_VAR, env[SCALE_ENV_VAR])
        return _env_factor(env[SCALE_ENV_VAR])
    stored = ConfigManager(config_path).get("ui_scale", DEFAULT_UI_SCALE)
    factor = scale_factor(stored)
    if factor != 1.0:
        env[SCALE_ENV_VAR] = f"{factor:g}"
        logger.info("Interface size: %d%%", round(factor * 100))
    return factor


def _env_factor(text: str) -> float:
    """Parse a factor given through the environment (1.0 when it is not a positive number)."""
    try:
        factor = float(text)
    except ValueError:
        return 1.0
    return factor if factor > 0 else 1.0
