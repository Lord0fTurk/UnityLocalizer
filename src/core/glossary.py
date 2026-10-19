# -*- coding: utf-8 -*-
"""Custom terminology glossary and term protection manager."""

from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path

from src.core.syntax_guard import UNITY_PROTECT_RE
from src.utils.file_ops import safe_write
from src.utils.paths import get_glossary_path

logger = logging.getLogger(__name__)


class GlossaryManager:
    """Manages term dictionaries to ensure consistent translations."""

    def __init__(self, glossary_path: Path | str | None = None) -> None:
        self.glossary_path = (
            Path(glossary_path) if glossary_path else get_glossary_path()
        )
        self._lock = threading.RLock()
        self._terms: dict[str, str] = {}
        self._pattern: re.Pattern[str] | None = None
        self._by_lower: dict[str, str] = {}
        self.load()

    def load(self) -> dict[str, str]:
        """Load glossary mappings from disk."""
        with self._lock:
            self._terms = {}
            self._pattern = None
            if self.glossary_path.is_file():
                try:
                    with open(self.glossary_path, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        if isinstance(loaded, dict):
                            self._terms = {
                                str(k).strip(): str(v).strip()
                                for k, v in loaded.items()
                                if str(k).strip() and str(v).strip()
                            }
                except Exception as exc:
                    logger.error("Failed to load glossary from %s: %s", self.glossary_path, exc)
            return dict(self._terms)

    def save(self) -> bool:
        """Persist glossary mappings to disk atomically."""
        try:
            with self._lock:
                content = json.dumps(self._terms, indent=2, ensure_ascii=False)
            safe_write(self.glossary_path, content, make_backup=False)
            return True
        except Exception as exc:
            logger.error("Failed to save glossary: %s", exc)
            return False

    def add_term(self, original: str, translation: str, auto_save: bool = True) -> None:
        """Add or update a glossary term."""
        orig = original.strip()
        trans = translation.strip()
        if not orig or not trans:
            return
        with self._lock:
            self._terms[orig] = trans
            self._pattern = None
        if auto_save:
            self.save()

    def remove_term(self, original: str, auto_save: bool = True) -> bool:
        """Remove a term from glossary."""
        with self._lock:
            if original in self._terms:
                del self._terms[original]
                self._pattern = None
                if auto_save:
                    self.save()
                return True
        return False

    def _compiled(self) -> tuple[re.Pattern[str] | None, dict[str, str]]:
        """One case-insensitive whole-word alternation, longest term first (rebuilt on change)."""
        with self._lock:
            if not self._terms:
                return None, {}
            if self._pattern is None:
                terms = [t for t in sorted(self._terms, key=len, reverse=True) if t.strip()]
                if not terms:
                    return None, {}
                self._by_lower = {term.lower(): self._terms[term] for term in terms}
                alternatives = "|".join(rf"(?<!\w){re.escape(term)}(?!\w)" for term in terms)
                self._pattern = re.compile(alternatives, re.IGNORECASE)
            return self._pattern, dict(self._by_lower)

    def apply(self, text: str) -> str:
        """Replace glossary terms with their translations outside RichText tags and placeholders."""
        pattern, by_lower = self._compiled()
        if pattern is None:
            return text
        parts: list[str] = []
        pos = 0
        for match in UNITY_PROTECT_RE.finditer(text):
            if match.start() > pos:
                segment = text[pos : match.start()]
                parts.append(pattern.sub(lambda m: by_lower[m.group(0).lower()], segment))
            parts.append(match.group(0))
            pos = match.end()
        if pos < len(text):
            parts.append(pattern.sub(lambda m: by_lower[m.group(0).lower()], text[pos:]))
        return "".join(parts)

    def covers(self, source: str, cached: str) -> bool:
        """True when each glossary term of ``source`` is in ``cached`` or already replaced there.

        Engine output made before a term was added contains the engine's own
        rendering of it, which ``apply`` cannot fix; such entries must be
        re-translated. Manual review fixes already hold the replacement and stay valid.
        """
        pattern, by_lower = self._compiled()
        if pattern is None:
            return True
        clean_source = UNITY_PROTECT_RE.sub(" ", source)
        clean_cached = UNITY_PROTECT_RE.sub(" ", cached)
        present = {match.lower() for match in pattern.findall(clean_cached)}
        lowered = clean_cached.lower()
        return all(
            term in present or by_lower[term].lower() in lowered
            for term in {match.lower() for match in pattern.findall(clean_source)}
        )

    @property
    def terms(self) -> dict[str, str]:
        """Return a copy of the current glossary terms."""
        with self._lock:
            return dict(self._terms)
