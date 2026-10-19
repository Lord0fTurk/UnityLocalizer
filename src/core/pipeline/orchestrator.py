# -*- coding: utf-8 -*-
"""Unified AOT localization pipeline: profile -> harvest -> translate -> deploy."""

from __future__ import annotations

import logging
from pathlib import Path

from src.core.engine_profiler import EngineProfiler, UnityGameProfile
from src.core.harvesters.harvest_collector import HarvestCollector
from src.core.hook_layout import dictionary_path
from src.core.hook_manager.font_bootstrap import FontBootstrap
from src.core.hook_manager.font_provisioner import FontProvisioner
from src.core.hook_manager.glyph_coverage import analyze_coverage, tmp_bundle_codepoints
from src.core.parsers.auto_translator import AutoTranslatorParser
from src.core.parsers.loc_table import resolve_source_language
from src.core.parsers.streaming_assets import StreamingAssetsParser
from src.core.pipeline.review_session import ReviewSession, RunContext
from src.core.pipeline.translation_runner import BatchTranslationRunner, TranslationEngineError
from src.core.progress import CancelToken, ProgressCallback, ProgressEvent, checkpoint, emit
from src.core.rtl_shaper import is_rtl_language, shape_translations
from src.core.translators.base import TranslationEngine
from src.core.translators.manager import TranslationManager

logger = logging.getLogger(__name__)


def prepare_for_display(
    translations: dict[str, str], target_lang: str, rtl_shaping: bool = True
) -> dict[str, str]:
    """Return translations as the game must render them (visual order for RTL targets).

    The cache and editor keep logical order; only deployed files are shaped.
    """
    if not (rtl_shaping and is_rtl_language(target_lang)):
        return translations
    logger.info("Applying static RTL shaping to %d translations (%s)", len(translations), target_lang)
    return shape_translations(translations)


class UnityTranslationPipeline:
    """Coordinates game profiling, text harvesting, batch translation, and deployment."""

    def __init__(self, translation_manager: TranslationManager | None = None) -> None:
        self.tm = translation_manager or TranslationManager()
        self.runner = BatchTranslationRunner(self.tm)
        self.progress_callback: ProgressCallback | None = None
        self.last_session: ReviewSession | None = None
        self.last_harvest_count = 0
        # XUnity OverrideFontTextMeshPro to deploy (None leaves the INI value alone).
        self.tmp_override_font: str | None = None

    def save_review(self, session: ReviewSession) -> bool:
        """Write every validated row of a review to the game dictionary and patched loose files.

        Manual edits are also stored in the translation cache so the next run
        reuses the human fix instead of re-translating the string.
        """
        ctx = session.context
        deployed = prepare_for_display(session.shippable(), ctx.target_lang, ctx.rtl_shaping)
        written = AutoTranslatorParser().apply_translations(
            dictionary_path(ctx.game_root, ctx.target_lang), deployed
        )
        if ctx.streaming_files:
            self._patch_streaming_files(
                list(ctx.streaming_files), deployed, ctx.target_lang, resolve_source_language(ctx.source_lang)
            )
        edits = session.edited()
        self.tm.cache.set_many(edits, ctx.source_lang, ctx.target_lang, ctx.engine)
        logger.info("Saved review: %d shippable rows, %d manual edits", len(deployed), len(edits))
        return written

    def _report(self, event: ProgressEvent) -> None:
        """Forward an event to the listener; a broken UI listener must not kill the run."""
        if not self.progress_callback:
            return
        try:
            self.progress_callback(event)
        except Exception:
            logger.exception("Progress callback raised; continuing pipeline")

    def run_unified_localization_pipeline(
        self,
        game_dir: Path | str,
        target_lang: str = "tr",
        engine: TranslationEngine = TranslationEngine.GOOGLE,
        patch_loose_files: bool = False,
        source_lang: str = "auto",
        rtl_shaping: bool = True,
        cancel: CancelToken | None = None,
    ) -> int:
        """Harvest every text channel, translate offline-ahead, and deploy the patch.

        ``patch_loose_files`` additionally rewrites StreamingAssets files in place; it is
        off by default because data files often mix display text with logic keys.
        ``source_lang`` goes to the engine as-is; table columns and XUnity's
        ``FromLanguage`` use its concrete form ('auto' resolves to English).
        ``rtl_shaping`` converts right-to-left targets to visual order at deploy time.
        ``cancel`` raises ``OperationCancelled`` at a checkpoint; nothing is deployed then.
        Raises ``TranslationEngineError`` when the engine translated nothing (nothing is
        deployed either). Returns the number of translations written to the game;
        ``last_harvest_count`` tells a game without text apart from a run that kept nothing.
        """
        self.last_session = None
        self.last_harvest_count = 0
        concrete_source = resolve_source_language(source_lang)
        profile = EngineProfiler.profile_game(game_dir)
        harvest = HarvestCollector(self._report, concrete_source).collect(profile, cancel)
        self.last_harvest_count = len(harvest.strings)
        logger.info("Unified harvest: %d unique strings", len(harvest.strings))
        if not harvest.strings:
            return 0

        self._announce_plan(harvest.strings, source_lang, target_lang, engine)
        report = self.runner.run(
            harvest.strings, target_lang, engine, self._report, source_lang=source_lang, cancel=cancel
        )
        checkpoint(cancel)
        if not report.translations and report.failed:
            raise TranslationEngineError(report.first_error or "the translation engine returned no results")
        loose_files = harvest.streaming_files if patch_loose_files else []
        context = RunContext(
            profile.game_path, target_lang, source_lang, engine.value, rtl_shaping, tuple(loose_files)
        )
        self.last_session = ReviewSession.from_report(report, context)
        deployed = prepare_for_display(report.translations, target_lang, rtl_shaping)
        self._deploy(profile, loose_files, deployed, target_lang, concrete_source)
        emit(self._report, "pipeline.completed", len(report.translations), len(report.translations))
        return len(report.translations)

    def _announce_plan(
        self, strings: list[str], source_lang: str, target_lang: str, engine: TranslationEngine
    ) -> None:
        """Report how much text will reach the engine (cached strings cost nothing)."""
        raw_cached = self.tm.cache.get_many(strings, source_lang, target_lang, engine.value) if self.tm.use_cache else {}
        cached = {k: v for k, v in raw_cached.items() if self.tm.glossary.covers(k, v)}
        chars = sum(len(text) for text in strings if text not in cached)
        logger.info("Translation plan: %d strings, %d cached, %d characters to send", len(strings), len(cached), chars)
        emit(self._report, "pipeline.translation_plan", count=len(strings), cached=len(cached), chars=chars)

    def _deploy(
        self,
        profile: UnityGameProfile,
        loose_files: list[Path],
        translations: dict[str, str],
        target_lang: str,
        source_lang: str = "en",
    ) -> None:
        """Write dictionary, optionally patch loose files, and wire the TMP fallback font."""
        root = profile.game_path
        emit(self._report, "pipeline.deploying")
        AutoTranslatorParser().apply_translations(dictionary_path(root, target_lang), translations)
        self._patch_streaming_files(loose_files, translations, target_lang, source_lang)
        font_bundle = FontProvisioner.provision(root, profile.unity_version, self._report)
        FontBootstrap.inject_font(
            root,
            target_lang=target_lang,
            source_lang=source_lang,
            tmp_override_font=self.tmp_override_font,
            preferred_bundle=font_bundle,
        )
        self._report_glyph_coverage(font_bundle, translations)

    def _report_glyph_coverage(self, font_bundle: Path | None, translations: dict[str, str]) -> None:
        """Warn about deployed characters the TMP fallback font cannot render (tofu risk)."""
        if font_bundle is None:
            return
        available = tmp_bundle_codepoints(font_bundle)
        if available is None:
            emit(self._report, "font.coverage_unknown", name=font_bundle.name)
            return
        report = analyze_coverage(translations.values(), available)
        if report.is_complete:
            emit(self._report, "font.coverage_ok", count=report.required, name=font_bundle.name)
            return
        logger.warning(
            "TMP fallback %s lacks %d characters used %d times: %s",
            font_bundle.name, len(report.missing), report.missing_uses, report.sample(),
        )
        emit(
            self._report, "font.coverage_missing", name=font_bundle.name,
            count=len(report.missing), uses=report.missing_uses, chars=report.sample(),
        )

    @staticmethod
    def _patch_streaming_files(
        files: list[Path], translations: dict[str, str], target_lang: str, source_lang: str = "en"
    ) -> None:
        """Apply translations in-place to loose StreamingAssets files (with .bak)."""
        parser = StreamingAssetsParser(source_lang=source_lang, target_lang=target_lang)
        for path in files:
            try:
                parser.apply_translations(path, translations)
            except (OSError, ValueError) as exc:
                logger.warning("Failed applying translations to %s: %s", path.name, exc)
