# -*- coding: utf-8 -*-
"""System font names for the TextMeshPro fallback, per language and operating system.

IL2CPP games cannot load a font AssetBundle, so XUnity builds a TextMeshPro font from an
installed OS font by name. Windows and Linux ship different fonts under different names,
so the name has to match the system the game runs on.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys

logger = logging.getLogger(__name__)

# Windows fonts for IL2CPP builds whose stripped runtime cannot load AssetBundles.
DEFAULT_IL2CPP_SYSTEM_FONTS: dict[str, str] = {
    "zh": "SimHei",
    "ja": "Meiryo",
    "ko": "Malgun Gothic",
    "ar": "Segoe UI",
    "fa": "Segoe UI",
    "he": "Segoe UI",
    "ru": "Arial",
    "uk": "Arial",
    "be": "Arial",
    "tr": "Arial",
}
FALLBACK_IL2CPP_SYSTEM_FONT: str = "Arial"

# Font families (as fontconfig reports them) that cover a language on common Linux and
# Steam Deck installs, best first. The first installed one wins; without a way to list the
# installed fonts the first name is used.
_LINUX_LATIN = ("DejaVu Sans", "Liberation Sans", "Noto Sans", "FreeSans")
_LINUX_ARABIC = ("DejaVu Sans", "Noto Sans Arabic", "Noto Naskh Arabic", "FreeSans")
LINUX_SYSTEM_FONTS: dict[str, tuple[str, ...]] = {
    "zh": ("Noto Sans CJK SC", "Noto Sans SC", "WenQuanYi Micro Hei", "WenQuanYi Zen Hei", "Droid Sans Fallback"),
    "ja": ("Noto Sans CJK JP", "Noto Sans JP", "IPAexGothic", "TakaoGothic", "VL Gothic"),
    "ko": ("Noto Sans CJK KR", "Noto Sans KR", "NanumGothic", "Baekmuk Gulim"),
    **dict.fromkeys(("ar", "fa", "ur", "ps", "sd", "ug"), _LINUX_ARABIC),
    "he": ("DejaVu Sans", "Noto Sans Hebrew", "FreeSans"),
    "th": ("Noto Sans Thai", "Loma", "Garuda", "DejaVu Sans"),
    **dict.fromkeys(("hi", "mr", "ne", "sa"), ("Noto Sans Devanagari", "Lohit Devanagari", "DejaVu Sans")),
}


def installed_linux_fonts() -> set[str] | None:
    """Lower-cased font families installed on this machine, or None when they cannot be listed."""
    if not sys.platform.startswith("linux") or shutil.which("fc-list") is None:
        return None
    try:
        out = subprocess.run(
            ["fc-list", ":", "family"], capture_output=True, text=True, timeout=10, check=False
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("Could not list installed fonts with fc-list: %s", exc)
        return None
    families = {name.strip().casefold() for line in out.splitlines() for name in line.split(",") if name.strip()}
    return families or None


def default_system_font(language: str, linux: bool = False, installed: set[str] | None = None) -> str:
    """System font name for the TextMeshPro fallback of a target language.

    ``linux`` selects names for a native Linux game. ``installed`` (lower-cased families) lets the
    choice follow what this machine has; when None and this is a Linux machine it is read with
    ``fc-list``.
    """
    base = language.split("-")[0].lower()
    if not linux:
        return DEFAULT_IL2CPP_SYSTEM_FONTS.get(base, FALLBACK_IL2CPP_SYSTEM_FONT)
    candidates = (*LINUX_SYSTEM_FONTS.get(base, ()), *_LINUX_LATIN)
    available = installed if installed is not None else installed_linux_fonts()
    if available:
        for name in candidates:
            if name.casefold() in available:
                return name
    return candidates[0]
