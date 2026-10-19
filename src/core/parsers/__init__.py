# -*- coding: utf-8 -*-
"""Format and framework parsers."""

from src.core.parsers.base import BaseParser
from src.core.parsers.streaming_assets import StreamingAssetsParser
from src.core.parsers.auto_translator import AutoTranslatorParser
from src.core.parsers.naninovel_parser import NaninovelParser

__all__ = [
    "BaseParser",
    "StreamingAssetsParser",
    "AutoTranslatorParser",
    "NaninovelParser",
]
