# -*- coding: utf-8 -*-
"""Glyph coverage check: do deployed translations fit the TMP fallback font?

TextMeshPro draws a missing glyph as a tofu box (□). The fallback SDF bundle
shipped with the patch only renders characters baked into its character table,
so every character the translations need is compared against it before release.
Font assets are read through UnityPy strictly read-only; AssetBundles carry
TypeTrees, so their ``TMP_FontAsset`` tables deserialize without a generator.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.core.syntax_guard import UNITY_PROTECT_RE

logger = logging.getLogger(__name__)

MISSING_SAMPLE_SIZE = 20


@dataclass
class CoverageReport:
    """Characters required by translations versus characters the font provides."""

    required: int = 0
    missing: list[str] = field(default_factory=list)
    missing_uses: int = 0

    @property
    def is_complete(self) -> bool:
        return not self.missing

    def sample(self, size: int = MISSING_SAMPLE_SIZE) -> str:
        """Most frequent missing characters, joined for display."""
        return " ".join(self.missing[:size])


def required_codepoints(texts: Iterable[str]) -> Counter[int]:
    """Count printable code points the game must render, excluding markup and spaces."""
    counts: Counter[int] = Counter()
    for text in texts:
        visible = UNITY_PROTECT_RE.sub("", text)
        counts.update(ord(ch) for ch in visible if not ch.isspace() and ch.isprintable())
    return counts


def analyze_coverage(texts: Iterable[str], available: set[int]) -> CoverageReport:
    """Compare required code points against a font's code point set."""
    counts = required_codepoints(texts)
    missing = [cp for cp, _ in counts.most_common() if cp not in available]
    return CoverageReport(
        required=len(counts),
        missing=[chr(cp) for cp in missing],
        missing_uses=sum(counts[cp] for cp in missing),
    )


def codepoints_from_font_tree(tree: dict[str, Any]) -> set[int]:
    """Read code points from a TMP_FontAsset TypeTree (TMP 1.4+ or legacy TMP)."""
    found: set[int] = set()
    for entry in tree.get("m_CharacterTable") or []:
        if isinstance(entry, dict) and isinstance(entry.get("m_Unicode"), int):
            found.add(entry["m_Unicode"])
    for glyph in tree.get("m_glyphInfoList") or []:
        if isinstance(glyph, dict) and isinstance(glyph.get("id"), int):
            found.add(glyph["id"])
    return found


def tmp_bundle_codepoints(bundle_path: Path) -> set[int] | None:
    """Union of code points across TMP font assets in a bundle; None when none are readable."""
    import UnityPy

    found: set[int] = set()
    try:
        env = UnityPy.load(str(bundle_path))
        for obj in env.objects:
            if obj.type.name == "MonoBehaviour":
                found |= _font_tree_codepoints(obj)
    except Exception as exc:  # UnityPy raises heterogeneous errors on unknown layouts
        logger.warning("Could not read TMP font bundle %s: %s", bundle_path.name, exc)
        return None
    return found or None


def _font_tree_codepoints(obj: Any) -> set[int]:
    """Code points of one MonoBehaviour if it is a TMP font asset; empty otherwise."""
    try:
        tree = obj.read_typetree()
    except Exception as exc:  # stripped or foreign MonoBehaviour layouts
        logger.debug("Skipping unreadable MonoBehaviour %s: %s", getattr(obj, "path_id", "?"), exc)
        return set()
    return codepoints_from_font_tree(tree) if isinstance(tree, dict) else set()
