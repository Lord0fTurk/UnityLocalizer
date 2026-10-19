# -*- coding: utf-8 -*-
"""Persistent SQLite semantic translation cache."""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import time
from collections.abc import Iterable, Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from src.utils.paths import get_cache_dir

logger = logging.getLogger(__name__)

# Stay below SQLite's historical limit of 999 bound parameters per statement.
_LOOKUP_CHUNK = 900


class TranslationCache:
    """Thread-safe SQLite storage for caching translation results.

    Every operation opens and closes its own connection, so the cache holds no
    resources between calls and can be used from any worker thread. The batch
    methods (``get_many``/``set_many``) use one connection and one transaction,
    which keeps runs with tens of thousands of strings fast.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else get_cache_dir() / "translations.db"
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Open a connection, commit on success, roll back on error, always close."""
        with closing(sqlite3.connect(self.db_path, timeout=30)) as conn:
            with conn:
                yield conn

    def _init_db(self) -> None:
        """Create the translations table if not present."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS translations (
                    cache_key TEXT PRIMARY KEY,
                    source_text TEXT NOT NULL,
                    translated_text TEXT NOT NULL,
                    source_lang TEXT NOT NULL,
                    target_lang TEXT NOT NULL,
                    engine TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )

    @staticmethod
    def _make_key(source_text: str, source_lang: str, target_lang: str, engine: str) -> str:
        """Generate deterministic SHA256 cache key."""
        raw = f"{source_text}::{source_lang}::{target_lang}::{engine}".encode(
            "utf-8", errors="surrogatepass"
        )
        return hashlib.sha256(raw).hexdigest()

    def get(
        self, source_text: str, source_lang: str, target_lang: str, engine: str
    ) -> str | None:
        """Retrieve cached translation or return None."""
        return self.get_many([source_text], source_lang, target_lang, engine).get(source_text)

    def get_many(
        self, source_texts: Iterable[str], source_lang: str, target_lang: str, engine: str
    ) -> dict[str, str]:
        """Return ``{source: translation}`` for every non-empty text present in the cache."""
        keys = {self._make_key(t, source_lang, target_lang, engine): t for t in source_texts}
        if not keys:
            return {}
        key_list = list(keys)
        found: dict[str, str] = {}
        try:
            with self._connect() as conn:
                for start in range(0, len(key_list), _LOOKUP_CHUNK):
                    chunk = key_list[start : start + _LOOKUP_CHUNK]
                    marks = ",".join("?" * len(chunk))
                    rows = conn.execute(
                        f"SELECT cache_key, translated_text FROM translations WHERE cache_key IN ({marks})",
                        chunk,
                    )
                    found.update(
                        (keys[key], str(text))
                        for key, text in rows
                        if text is not None and str(text).strip()
                    )
        except sqlite3.Error as exc:
            logger.error("Error reading %d cache entries: %s", len(keys), exc)
        return found

    def set(
        self,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
        engine: str,
    ) -> None:
        """Store a translation in cache."""
        self.set_many({source_text: translated_text}, source_lang, target_lang, engine)

    def set_many(
        self, translations: dict[str, str], source_lang: str, target_lang: str, engine: str
    ) -> None:
        """Store many non-empty translations in a single transaction."""
        if not translations:
            return
        now = time.time()
        rows = [
            (self._make_key(src, source_lang, target_lang, engine), src, dst,
             source_lang, target_lang, engine, now)
            for src, dst in translations.items()
            if src and dst and dst.strip()
        ]
        if not rows:
            return
        try:
            with self._connect() as conn:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO translations
                    (cache_key, source_text, translated_text, source_lang, target_lang, engine, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
        except sqlite3.Error as exc:
            logger.error("Error writing %d cache entries: %s", len(rows), exc)

    def count(self) -> int:
        """Return total number of cached translation entries."""
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT COUNT(*) FROM translations").fetchone()
                return int(row[0]) if row else 0
        except sqlite3.Error as exc:
            logger.error("Error counting cache entries: %s", exc)
            return 0

    def clear(self) -> None:
        """Delete every cached entry (explicit user action only, never on shutdown)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM translations")
