# -*- coding: utf-8 -*-
"""Pseudo-localization engine for UI layout and placeholder testing."""

from __future__ import annotations

import logging
import math
import re


from src.core.syntax_guard import UnitySyntaxGuard
from src.core.translators.base import (
    BaseTranslator,
    TranslationEngine,
    TranslationResult,
)

logger = logging.getLogger(__name__)


class PseudoTranslator(BaseTranslator):
    """Pseudo-localization for layout testing before a real translation exists.

    Latin letters become accented look-alikes (glyph coverage) and every string is
    padded by ``expansion`` (default 30%, typical for German/Russian) so buttons
    that will overflow are visible in game. Placeholders and tags stay untouched.
    """

    _SOURCE = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    _ACCENTED = "äḅĉḍëḟĝĥïĵḳĺṁńöṗqrśẗüṿẅẍÿżÄḄĈḌËḞĜĤÏĴḲĹṀŃÖṖQRŚṪÜṾẄẌŸŻ"
    _TOKEN = re.compile(r"(⟦ULPH_\d+⟧)")

    def __init__(self, expansion: float = 0.3) -> None:
        super().__init__()
        self._map = str.maketrans(self._SOURCE, self._ACCENTED)
        self.expansion = max(0.0, expansion)

    def translate(self, text: str, source_lang: str = "auto", target_lang: str = "tr") -> TranslationResult:
        protected, tags = UnitySyntaxGuard.protect(text)
        parts = self._TOKEN.split(protected)
        accented = "".join(p if self._TOKEN.fullmatch(p) else p.translate(self._map) for p in parts)
        visible = sum(len(p) for p in parts if not self._TOKEN.fullmatch(p))
        padding = "~" * math.ceil(visible * self.expansion)
        marker = target_lang.split("-")[0].upper()
        final = UnitySyntaxGuard.restore(f"[{marker}~{accented}{padding}~{marker}]", tags)
        return TranslationResult(
            original_text=text, translated_text=final, source_lang=source_lang,
            target_lang=target_lang, engine=TranslationEngine.PSEUDO, success=True,
        )
