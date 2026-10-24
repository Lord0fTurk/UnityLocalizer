# -*- coding: utf-8 -*-
"""Online language detection by majority vote over a few Google-detected samples."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable, Sequence

from src.core.languages import canonical_language_code
from src.core.lang_detect.sampling import spread
from src.core.progress import CancelToken, checkpoint

logger = logging.getLogger(__name__)

DetectOne = Callable[[str], str | None]

SAMPLE_COUNT = 9
MIN_VOTES = 3
MIN_AGREEMENT = 0.60


def _base(code: str) -> str:
    return code.split("-")[0].lower()


def _collect_votes(samples: Sequence[str], detect_one: DetectOne, cancel: CancelToken | None) -> list[str]:
    """Canonical language codes the remote detector returned for each sample."""
    votes: list[str] = []
    for sample in samples:
        checkpoint(cancel)
        raw = detect_one(sample)
        code = canonical_language_code(raw) if raw else None
        if code:
            votes.append(code)
    return votes


def detect_online(
    prose: Sequence[str],
    detect_one: DetectOne,
    target_lang: str,
    cancel: CancelToken | None = None,
) -> tuple[str, float] | None:
    """(code, agreement ratio) when most samples agree on a language other than the target."""
    samples = spread(prose, SAMPLE_COUNT)
    if len(samples) < MIN_VOTES:
        return None
    votes = _collect_votes(samples, detect_one, cancel)
    if len(votes) < MIN_VOTES:
        logger.info("Online language detection got only %d usable answer(s)", len(votes))
        return None
    counter = Counter(votes)
    code, count = counter.most_common(1)[0]
    agreement = count / len(votes)
    logger.info("Online language detection votes: %s", dict(counter))
    if agreement < MIN_AGREEMENT:
        return None
    if _base(code) == _base(target_lang):
        logger.info("Online detection equals the target language (%s); ignoring", code)
        return None
    return code, agreement
