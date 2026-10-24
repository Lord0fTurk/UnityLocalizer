# -*- coding: utf-8 -*-
"""Source-language detection chain: Unicode script, offline model, then Google."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass

from src.core.lang_detect.offline_detector import detect_offline
from src.core.lang_detect.online_detector import DetectOne, detect_online
from src.core.lang_detect.sampling import clean_lines, prose_lines
from src.core.lang_detect.script_detector import detect_by_script
from src.core.progress import CancelToken

logger = logging.getLogger(__name__)

METHOD_OFFLINE = "offline"
METHOD_ONLINE = "online"


@dataclass(frozen=True)
class DetectionResult:
    """A detected game language, how it was found and how sure the detector is (0-1)."""

    code: str
    method: str
    confidence: float


class SourceLanguageDetector:
    """Detects a game's language from harvested strings; None when nothing is certain."""

    def __init__(self, online: DetectOne | None = None) -> None:
        """``online`` is a single-text remote detector; omit it to stay fully offline."""
        self._online = online

    def detect(
        self, strings: Iterable[str], target_lang: str, cancel: CancelToken | None = None
    ) -> DetectionResult | None:
        """Try script, offline model and finally the online detector, in that order."""
        lines = clean_lines(strings)
        by_script = detect_by_script(lines)
        if by_script:
            logger.info("Script-based language detection: %s (%.0f%% of lines)", by_script[0], by_script[1] * 100)
            return DetectionResult(by_script[0], METHOD_OFFLINE, by_script[1])
        prose = prose_lines(lines)
        offline = detect_offline(prose)
        if offline:
            return DetectionResult(offline[0], METHOD_OFFLINE, offline[1])
        if self._online is None:
            return None
        online = detect_online(prose, self._online, target_lang, cancel)
        return DetectionResult(online[0], METHOD_ONLINE, online[1]) if online else None
