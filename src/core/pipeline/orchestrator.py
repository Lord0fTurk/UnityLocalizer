# -*- coding: utf-8 -*-
"""Unified AOT localization pipeline: profile -> harvest -> translate -> deploy."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from src.core.engine_profiler import EngineProfiler, UnityGameProfile
from src.core.harvesters.anti_mod import MAX_REPORTED_NAMES, find_bepinex_removers
from src.core.harvesters.harvest_collector import HarvestCollector, HarvestResult
from src.core.harvesters.harvest_stats import HarvestStats
from src.core.hook_layout import dictionary_path, substitutions_path
from src.core.hook_manager.font_bootstrap import FontBootstrap
from src.core.hook_manager.font_provisioner import FontProvisioner
from src.core.hook_manager.glyph_coverage import analyze_coverage, tmp_bundle_codepoints
from src.core.lang_detect import SourceLanguageDetector
from src.core.lang_detect.script_filter import filter_foreign_script
from src.core.languages import AUTO, canonical_language_code, english_name
from src.core.parsers.auto_translator import AutoTranslatorParser
from src.core.parsers.loc_table import DEFAULT_SOURCE_LANGUAGE, base_language, resolve_source_language
from src.core.parsers.streaming_assets import StreamingAssetsParser
from src.core.pipeline.review_session import ReviewSession, RunContext
from src.core.pipeline.translation_runner import BatchTranslationRunner, TranslationEngineError
from src.core.progress import CancelToken, ProgressCallback, ProgressEvent, checkpoint, emit
from src.core.rtl_shaper import is_rtl_language, shape_translations
from src.core.translators.base import TranslationEngine
from src.core.translators.google import GoogleTranslator
from src.core.translators.manager import TranslationManager

logger = logging.getLogger(__name__)


def _names(files: list[str], limit: int = 3) -> str:
    """A short, readable list of file names for a message ("a, b, c and 4 more")."""
    shown = ", ".join(files[:limit])
    return f"{shown} (+{len(files) - limit})" if len(files) > limit else shown


def make_bilingual(source: str, translation: str, template: str = "{target}\n({source})") -> str:
    """Format source and translation together for comparative/dual-language display."""
    src_clean = source.strip()
    dst_clean = translation.strip()
    if not src_clean or not dst_clean or src_clean == dst_clean:
        return translation
    if len(src_clean) <= 2:
        return translation
    try:
        return template.format(target=translation, source=source)
    except (KeyError, ValueError):
        return f"{translation}\n({source})"


def apply_bilingual_mode(
    translations: dict[str, str], template: str = "{target}\n({source})"
) -> dict[str, str]:
    """Return dictionary with translations augmented by their source text."""
    return {src: make_bilingual(src, dst, template) for src, dst in translations.items()}


def prepare_for_display(
    translations: dict[str, str],
    target_lang: str,
    rtl_shaping: bool = True,
    bilingual_mode: bool = False,
    bilingual_template: str = "{target}\n({source})",
) -> dict[str, str]:
    """Return translations formatted for game display (bilingual and/or RTL visual order).

    The cache and editor keep logical order; only deployed files are shaped.
    """
    out = apply_bilingual_mode(translations, bilingual_template) if bilingual_mode else translations
    if not (rtl_shaping and is_rtl_language(target_lang)):
        return out
    logger.info("Applying static RTL shaping to %d translations (%s)", len(out), target_lang)
    return shape_translations(out)


class UnityTranslationPipeline:
    """Coordinates game profiling, text harvesting, batch translation, and deployment."""

    def __init__(self, translation_manager: TranslationManager | None = None) -> None:
        self.tm = translation_manager or TranslationManager()
        self.runner = BatchTranslationRunner(self.tm)
        self.progress_callback: ProgressCallback | None = None
        self.last_session: ReviewSession | None = None
        self.last_harvest_count = 0
        self.last_harvest_stats: HarvestStats | None = None
        # XUnity OverrideFontTextMeshPro to deploy (None leaves the INI value alone).
        self.tmp_override_font: str | None = None
        # XUnity OverrideFont (uGUI / UnityEngine.UI.Text) to deploy.
        self.override_font: str | None = None

    def save_review(self, session: ReviewSession) -> bool:
        """Write every validated row of a review to the game dictionary and patched loose files.

        Manual edits are also stored in the translation cache so the next run
        reuses the human fix instead of re-translating the string.
        """
        ctx = session.context
        deployed = prepare_for_display(
            session.shippable(),
            ctx.target_lang,
            ctx.rtl_shaping,
            bilingual_mode=ctx.bilingual_mode,
            bilingual_template=ctx.bilingual_template,
        )
        written = AutoTranslatorParser().apply_translations(
            dictionary_path(ctx.game_root, ctx.target_lang), deployed
        )
        glossary = getattr(self.tm, "glossary", None)
        if glossary and glossary.terms:
            AutoTranslatorParser().apply_substitutions(
                substitutions_path(ctx.game_root, ctx.target_lang), glossary.terms
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
        bilingual_mode: bool = False,
        bilingual_template: str = "{target}\n({source})",
        cancel: CancelToken | None = None,
    ) -> int:
        """Harvest every text channel, translate offline-ahead, and deploy the patch.

        ``patch_loose_files`` additionally rewrites StreamingAssets files in place; it is
        off by default because data files often mix display text with logic keys.
        ``source_lang`` 'auto' is resolved right after the harvest by the detection chain
        (Unicode script, offline model, Google); the detected code then goes to the engine,
        table columns and XUnity's ``FromLanguage``. When nothing is certain, the engine
        still receives 'auto' while tables and XUnity fall back to English.
        ``rtl_shaping`` converts right-to-left targets to visual order at deploy time.
        ``cancel`` raises ``OperationCancelled`` at a checkpoint; nothing is deployed then.
        Raises ``TranslationEngineError`` when the engine translated nothing (nothing is
        deployed either). Returns the number of translations written to the game;
        ``last_harvest_count`` tells a game without text apart from a run that kept nothing.
        """
        self.last_session = None
        self.last_harvest_count = 0
        self.last_harvest_stats = None
        profile = EngineProfiler.profile_game(game_dir)
        self._warn_if_anti_mod(profile)
        harvest = HarvestCollector(self._report, resolve_source_language(source_lang)).collect(profile, cancel)
        self.last_harvest_count = len(harvest.strings)
        logger.info("Unified harvest: %d unique strings", len(harvest.strings))
        if not harvest.strings:
            self._report_harvest_coverage(harvest.stats)
            return 0

        harvest, source_lang = self._resolve_source(profile, harvest, source_lang, target_lang, engine, cancel)
        self._drop_foreign_script(harvest, source_lang)
        self.last_harvest_stats = harvest.stats
        self._report_harvest_coverage(harvest.stats)
        concrete_source = resolve_source_language(source_lang)
        self._announce_plan(harvest.strings, source_lang, target_lang, engine)
        report = self.runner.run(
            harvest.strings, target_lang, engine, self._report, source_lang=source_lang, cancel=cancel
        )
        checkpoint(cancel)
        if not report.translations and report.failed:
            raise TranslationEngineError(report.first_error or "the translation engine returned no results")
        loose_files = harvest.streaming_files if patch_loose_files else []
        context = RunContext(
            profile.game_path,
            target_lang,
            source_lang,
            engine.value,
            rtl_shaping,
            bilingual_mode=bilingual_mode,
            bilingual_template=bilingual_template,
            streaming_files=tuple(loose_files),
        )
        self.last_session = ReviewSession.from_report(report, context)
        deployed = prepare_for_display(
            report.translations,
            target_lang,
            rtl_shaping,
            bilingual_mode=bilingual_mode,
            bilingual_template=bilingual_template,
        )
        self._deploy(profile, loose_files, deployed, target_lang, concrete_source)
        emit(self._report, "pipeline.completed", len(report.translations), len(report.translations))
        return len(report.translations)

    def _resolve_source(
        self,
        profile: UnityGameProfile,
        harvest: HarvestResult,
        source_lang: str,
        target_lang: str,
        engine: TranslationEngine,
        cancel: CancelToken | None,
    ) -> tuple[HarvestResult, str]:
        """Replace 'auto' with the detected game language and notify the user either way.

        Loose tables were harvested with the English default, so when the detected
        language differs and such files exist, they are harvested again with it.
        """
        if source_lang != AUTO:
            return harvest, source_lang
        detected = self._detect_source_language(harvest.strings, target_lang, engine, cancel, harvest.stats)
        if detected is None:
            return harvest, source_lang
        language_dependent = bool(harvest.streaming_files) or harvest.stats.language_sensitive
        needs_reharvest = language_dependent and base_language(detected) != DEFAULT_SOURCE_LANGUAGE
        if needs_reharvest:
            harvest = HarvestCollector(self._report, detected).collect(profile, cancel)
            self.last_harvest_count = len(harvest.strings)
        return harvest, detected

    def _drop_foreign_script(self, harvest: HarvestResult, source_lang: str) -> None:
        """Leave out strings in another script than the source language (other locales of the game).

        Skipped while the source language is unknown, and when most text would go: that
        points at a wrong source language setting, which the user is told about instead.
        """
        if source_lang == AUTO:
            return
        result = filter_foreign_script(harvest.strings, source_lang)
        if not result.removed:
            return
        language = english_name(resolve_source_language(source_lang))
        if result.mismatch:
            emit(self._report, "pipeline.source_script_mismatch", language=language, count=result.removed)
            return
        harvest.strings = result.kept
        self.last_harvest_count = len(result.kept)
        emit(self._report, "pipeline.foreign_text_removed", count=result.removed, language=language)

    @staticmethod
    def _table_locale_hint(guess: str | None, stats: HarvestStats) -> str | None:
        """Language of localization tables that only exist in a non-English locale.

        With the English default, a game that ships only Japanese StringTables yields no
        table text at all; the remaining strings can then be misdetected as English or
        not detected. A confident non-English guess is kept; otherwise the tables decide.
        """
        if guess is not None and base_language(guess) != DEFAULT_SOURCE_LANGUAGE:
            return None
        seen = stats.dominant_skipped_locale()
        return canonical_language_code(seen) if seen else None

    def _warn_if_anti_mod(self, profile: UnityGameProfile) -> None:
        """Warn when the game contains code that deletes BepInEx (the translation would not show)."""
        removers = find_bepinex_removers(profile)
        if removers:
            logger.warning("Game removes BepInEx at start: %s", removers)
            emit(self._report, "pipeline.anti_mod_detected", names=", ".join(removers[:MAX_REPORTED_NAMES]))

    def _report_harvest_coverage(self, stats: HarvestStats) -> None:
        """Tell the user which parts of the game could not be read completely."""
        logger.info("Harvest coverage: %s", stats.to_report())
        unreadable = stats.files_failed
        if unreadable:
            emit(self._report, "pipeline.harvest_warn_unreadable_files", count=len(unreadable), names=_names(unreadable))
        if stats.raw_scanned_objects:
            emit(
                self._report, "pipeline.harvest_warn_raw_scan",
                count=stats.raw_scanned_objects, files=len(stats.raw_scanned_files),
                names=_names(stats.raw_scanned_files),
            )
        if stats.encrypted_code:
            emit(self._report, "pipeline.harvest_warn_code_encrypted")

    def _detect_source_language(
        self,
        strings: list[str],
        target_lang: str,
        engine: TranslationEngine,
        cancel: CancelToken | None,
        stats: HarvestStats | None = None,
    ) -> str | None:
        """Run the detection chain and emit the user-facing outcome; None when undecided."""
        result = SourceLanguageDetector(self._online_detector(engine)).detect(strings, target_lang, cancel)
        table_locale = self._table_locale_hint(result.code if result else None, stats or HarvestStats())
        if table_locale:
            emit(self._report, "pipeline.source_detected_tables", language=english_name(table_locale), code=table_locale)
            return table_locale
        if result is None:
            emit(self._report, "pipeline.source_detect_failed")
            return None
        emit(
            self._report, f"pipeline.source_detected_{result.method}",
            language=english_name(result.code), code=result.code, confidence=round(result.confidence * 100),
        )
        return result.code

    def _online_detector(self, engine: TranslationEngine) -> Callable[[str], str | None] | None:
        """Google detection, only for keyless engines: private/paid-engine users keep text local."""
        if engine not in (TranslationEngine.GOOGLE, TranslationEngine.BING):
            return None
        translator = self.tm.get_translator(TranslationEngine.GOOGLE)
        return translator.detect_language if isinstance(translator, GoogleTranslator) else None

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
        glossary = getattr(self.tm, "glossary", None)
        if glossary and glossary.terms:
            AutoTranslatorParser().apply_substitutions(
                substitutions_path(root, target_lang), glossary.terms
            )
        self._patch_streaming_files(loose_files, translations, target_lang, source_lang)
        font_bundle = FontProvisioner.provision(root, profile.unity_version, self._report)
        tmp_font = self.tmp_override_font
        if tmp_font is None and font_bundle is not None and not profile.is_il2cpp:
            available = tmp_bundle_codepoints(font_bundle)
            if available is not None:
                report = analyze_coverage(translations.values(), available)
                if not report.is_complete:
                    from src.core.hook_manager.font_bootstrap import (
                        DEFAULT_IL2CPP_SYSTEM_FONTS,
                        FALLBACK_IL2CPP_SYSTEM_FONT,
                    )
                    base_target = target_lang.split("-")[0].lower()
                    tmp_font = DEFAULT_IL2CPP_SYSTEM_FONTS.get(base_target, FALLBACK_IL2CPP_SYSTEM_FONT)
                    logger.info(
                        "Automatically wired system font %s for TextMeshPro to cover %d missing glyphs",
                        tmp_font, len(report.missing),
                    )

        FontBootstrap.inject_font(
            root,
            target_lang=target_lang,
            source_lang=source_lang,
            tmp_override_font=tmp_font,
            preferred_bundle=font_bundle,
            override_font=self.override_font,
            is_il2cpp=profile.is_il2cpp,
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
