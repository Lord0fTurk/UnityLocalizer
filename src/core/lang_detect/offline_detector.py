# -*- coding: utf-8 -*-
"""Offline statistical language detection backed by ``py3langid`` (BSD-3-Clause).

The raw model returns an unnormalised score, so this wrapper normalises it to a
probability and only answers when it is sure. Game text is full of character names
and UI words that the model happily labels as Shona or Uzbek; a wrong source
language would then be applied to the whole run.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from typing import Any

from src.core.languages import canonical_language_code
from src.core.lang_detect.sampling import spread

logger = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.90
MIN_SAMPLES = 8
MAX_SAMPLES = 60

_identifier: Any = None
_identifier_failed = False
_identifier_lock = threading.Lock()


def _get_identifier() -> Any:
    """Load the model once; None (with a warning) when py3langid or its data is missing."""
    global _identifier, _identifier_failed
    if _identifier is not None or _identifier_failed:
        return _identifier
    with _identifier_lock:
        if _identifier is None and not _identifier_failed:
            try:
                from py3langid.langid import MODEL_FILE, LanguageIdentifier

                _identifier = LanguageIdentifier.from_model_file(MODEL_FILE, norm_probs=True)
            except (ImportError, OSError, ValueError) as exc:
                _identifier_failed = True
                logger.warning("Offline language detection unavailable: %s", exc)
    return _identifier


def detect_offline(prose: Sequence[str], min_confidence: float = MIN_CONFIDENCE) -> tuple[str, float] | None:
    """(canonical code, probability) for a spread of prose lines, or None when unsure."""
    if len(prose) < MIN_SAMPLES:
        return None
    identifier = _get_identifier()
    if identifier is None:
        return None
    sample = " ".join(spread(prose, MAX_SAMPLES))
    raw_code, probability = identifier.classify(sample)
    code = canonical_language_code(str(raw_code))
    if code is None or probability < min_confidence:
        logger.info("Offline language detection not confident (%s, p=%.2f)", raw_code, probability)
        return None
    logger.info("Offline language detection: %s (p=%.3f)", code, probability)
    return code, float(probability)
