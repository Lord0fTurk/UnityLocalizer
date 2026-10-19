# -*- coding: utf-8 -*-
"""Quality-gated batch translation runner shared by every pipeline route.

Batches run on a small thread pool sized per engine (``manager.concurrency_for``):
web engines get a few parallel requests, local LLMs stay sequential. New batches
are only submitted while the run is not cancelled, so a stop request takes effect
as soon as the in-flight batches return.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field

from src.core.progress import CancelToken, ProgressCallback, checkpoint, emit
from src.core.syntax_guard import UnitySyntaxGuard
from src.core.translators.base import TranslationEngine, TranslationResult
from src.core.translators.manager import TranslationManager

logger = logging.getLogger(__name__)

# A run stops once this many batches in a row failed completely (offline, bad key, ban):
# continuing would only send every remaining string into the same error.
MAX_CONSECUTIVE_FAILED_BATCHES = 3


class TranslationEngineError(RuntimeError):
    """The engine translated nothing: it failed every request of several batches in a row."""


@dataclass
class TranslationReport:
    """Outcome of a batch run: accepted translations plus rejection diagnostics."""

    translations: dict[str, str] = field(default_factory=dict)
    rejected: dict[str, list[str]] = field(default_factory=dict)
    rejected_translations: dict[str, str] = field(default_factory=dict)
    failed_sources: list[str] = field(default_factory=list)
    unchanged_sources: list[str] = field(default_factory=list)
    # Accepted after dropped standalone placeholders were re-inserted automatically.
    repaired: set[str] = field(default_factory=set)
    # First engine error message, shown to the user when nothing could be translated.
    first_error: str = ""

    @property
    def failed(self) -> int:
        return len(self.failed_sources)

    @property
    def unchanged(self) -> int:
        return len(self.unchanged_sources)


class BatchTranslationRunner:
    """Translates strings in (parallel) batches and drops results that would break the game."""

    def __init__(self, manager: TranslationManager, batch_size: int = 25) -> None:
        self.manager = manager
        self.batch_size = batch_size

    def run(
        self,
        strings: list[str],
        target_lang: str,
        engine: TranslationEngine,
        progress: ProgressCallback | None = None,
        source: str = "",
        source_lang: str = "auto",
        cancel: CancelToken | None = None,
    ) -> TranslationReport:
        """Translate all strings and return only integrity-validated results.

        ``source`` is an opaque label (e.g. a file name) forwarded to the UI;
        ``source_lang`` is the engine source language ('auto' lets the engine detect it).
        ``cancel`` is checked before every batch; finished batches stay in the cache.
        Raises TranslationEngineError after ``MAX_CONSECUTIVE_FAILED_BATCHES`` total failures.
        """
        report = TranslationReport()
        total = len(strings)
        done = 0
        failed_streak = 0

        def translate(chunk: list[str]) -> list[TranslationResult]:
            return self.manager.translate_batch(
                chunk, source_lang=source_lang, target_lang=target_lang, engine_type=engine
            )

        chunks = self._chunks(strings, self._batch_size(engine))
        for results in self._execute(chunks, translate, self._workers(engine), cancel):
            for result in results:
                self._accept(result, report)
            done = min(done + len(results), total)
            emit(progress, "pipeline.translating", done, total, source=source)
            engine_results = [r for r in results if not r.metadata.get("from_offline")]
            if engine_results:
                if any(r.success and r.translated_text.strip() for r in engine_results):
                    failed_streak = 0
                else:
                    failed_streak += 1
            if failed_streak >= MAX_CONSECUTIVE_FAILED_BATCHES:
                logger.error("Aborting: %d batches in a row failed (%s)", failed_streak, report.first_error)
                raise TranslationEngineError(report.first_error or "the translation engine returned no results")
        checkpoint(cancel)
        self._log_summary(report, total)
        return report

    @staticmethod
    def _chunks(strings: list[str], size: int) -> Iterator[list[str]]:
        return (strings[start : start + size] for start in range(0, len(strings), size))

    def _batch_size(self, engine: TranslationEngine) -> int:
        """Engine-specific lines per request (AI engines use a smaller batch)."""
        batch_size_for = getattr(self.manager, "batch_size_for", None)
        size = batch_size_for(engine, self.batch_size) if callable(batch_size_for) else self.batch_size
        return max(1, int(size))

    def _workers(self, engine: TranslationEngine) -> int:
        """Parallel batches for this engine (managers without the hook run sequentially)."""
        concurrency_for = getattr(self.manager, "concurrency_for", None)
        return max(1, int(concurrency_for(engine))) if callable(concurrency_for) else 1

    @staticmethod
    def _execute(
        chunks: Iterator[list[str]],
        translate: Callable[[list[str]], list[TranslationResult]],
        workers: int,
        cancel: CancelToken | None,
    ) -> Iterator[list[TranslationResult]]:
        """Yield batch results as they finish; stop submitting once cancelled."""
        if workers <= 1:
            for chunk in chunks:
                checkpoint(cancel)
                yield translate(chunk)
            return
        pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="translate")
        pending: set[Future[list[TranslationResult]]] = set()
        try:
            exhausted = False
            while pending or not exhausted:
                while not exhausted and len(pending) < workers and not (cancel and cancel.is_cancelled):
                    chunk = next(chunks, None)
                    if chunk is None:
                        exhausted = True
                        break
                    pending.add(pool.submit(translate, chunk))
                if not pending:
                    break
                finished, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in finished:
                    yield future.result()
        finally:
            for future in pending:
                future.cancel()
            pool.shutdown(wait=True, cancel_futures=True)

    @staticmethod
    def _accept(result: TranslationResult, report: TranslationReport) -> None:
        """Route a single result into accepted, repaired, rejected, failed or unchanged buckets."""
        original, translated = result.original_text, result.translated_text
        if not result.success or not translated.strip():
            report.failed_sources.append(original)
            if result.error and not report.first_error:
                report.first_error = result.error
            return
        if translated == original:
            report.unchanged_sources.append(original)
            return
        ok, errors = UnitySyntaxGuard.validate_integrity(original, translated)
        if ok:
            report.translations[original] = translated
            return
        repaired = UnitySyntaxGuard.repair_missing_tokens(original, translated)
        if repaired is not None:
            report.translations[original] = repaired
            report.repaired.add(original)
            return
        report.rejected[original] = errors
        # Kept so the review editor can offer the broken candidate for manual repair.
        report.rejected_translations[original] = translated

    @staticmethod
    def _log_summary(report: TranslationReport, total: int) -> None:
        """Log aggregate statistics and a sample of integrity rejections."""
        logger.info(
            "Batch done: %d/%d accepted (%d auto-repaired), %d rejected (syntax), %d failed, %d unchanged",
            len(report.translations), total, len(report.repaired), len(report.rejected),
            report.failed, report.unchanged,
        )
        for original, errors in list(report.rejected.items())[:10]:
            logger.warning("Rejected %r: %s", original[:80], "; ".join(errors))
