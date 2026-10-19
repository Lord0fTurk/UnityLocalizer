# -*- coding: utf-8 -*-
"""Base parser interface for file and framework formats."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BaseParser(ABC):
    """Abstract interface for extracting and applying translations to game files."""

    @abstractmethod
    def extract_strings(self, file_path: Path | str) -> list[str]:
        """Extract all translatable strings from target file."""
        pass

    @abstractmethod
    def apply_translations(
        self,
        file_path: Path | str,
        translations: dict[str, str],
        output_path: Path | str | None = None,
    ) -> bool:
        """Apply translated strings back to file and persist."""
        pass
