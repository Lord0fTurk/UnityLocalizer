# -*- coding: utf-8 -*-
"""Base translation types and abstract translator class."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class TranslationEngine(Enum):
    """Supported translation engines."""

    GOOGLE = "google"
    BING = "bing"
    GEMINI = "gemini"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    LOCAL_LLM = "local_llm"
    DEEPL = "deepl"
    LIBRETRANSLATE = "libretranslate"
    PSEUDO = "pseudo"


@dataclass
class TranslationRequest:
    """Incoming request for text translation."""

    text: str
    source_lang: str
    target_lang: str
    engine: TranslationEngine
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TranslationResult:
    """Standardized result returned by any translation engine."""

    original_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    engine: TranslationEngine
    success: bool
    error: str | None = None
    quota_exceeded: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseTranslator(ABC):
    """Abstract base class for all translation engines."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        self.logger = logging.getLogger(self.__class__.__name__)
        self.status_callback: Callable[[str, str], None] | None = None
        self.fallback_translator: BaseTranslator | None = None

    def set_fallback(self, fallback: BaseTranslator | None) -> None:
        """Register a secondary fallback translator."""
        self.fallback_translator = fallback

    def emit_log(self, level: str, message: str) -> None:
        """Log message and notify status callback if registered."""
        if level.lower() == "error":
            self.logger.error(message)
        elif level.lower() == "warning":
            self.logger.warning(message)
        else:
            self.logger.info(message)

        if self.status_callback:
            try:
                self.status_callback(level, message)
            except Exception:  # a broken UI listener must not abort a translation
                self.logger.exception("Status callback failed")

    @abstractmethod
    def translate(
        self, text: str, source_lang: str = "auto", target_lang: str = "tr"
    ) -> TranslationResult:
        """Translate a single text string."""
        pass

    def translate_batch(
        self, texts: list[str], source_lang: str = "auto", target_lang: str = "tr"
    ) -> list[TranslationResult]:
        """Translate a batch of texts. Default implementation calls translate in sequence."""
        results: list[TranslationResult] = []
        for t in texts:
            results.append(self.translate(t, source_lang, target_lang))
        return results

    def close(self) -> None:
        """Clean up resources, network sessions, or connections."""
        pass
