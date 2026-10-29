# -*- coding: utf-8 -*-
"""Main PyQt6 backend bridge connecting QML to UnityLocalizer core."""

from __future__ import annotations

import json
import logging
import sys
import threading
import time
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QUrl, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDesktopServices, QGuiApplication

from src.core.game_launcher import LaunchError, launch_command
from src.core.engine_profiler import EngineProfiler, UnityGameProfile
from src.core.harvesters.asset_harvester import AssetHarvester
from src.core.harvesters.asset_worker import scan_assets_isolated
from src.core.harvesters.assembly_harvester import AssemblyHarvester
from src.core.harvesters.harvest_stats import HarvestStats
from src.core.harvesters.memory_guard import MemoryGuard, format_size
from src.core.harvesters.metadata_harvester import MetadataHarvester
from src.core.harvesters.typetree_provider import create_typetree_generator
from src.core.hook_manager.font_bootstrap import FontBootstrap
from src.core.hook_manager.font_provisioner import FontProvisioner
from src.core.hook_manager.installer import HookInstaller, RuntimeSetupError
from src.core.hook_manager.runtime_state import LOG_ERROR, LOG_OK, inspect_runtime_log
from src.core.parsers.loc_table import resolve_source_language
from src.core.parsers.streaming_assets import SUPPORTED_SUFFIXES, StreamingAssetsParser
from src.core.pipeline.orchestrator import UnityTranslationPipeline
from src.core.pipeline.patch_exporter import PatchExporter, archive_path
from src.core.pipeline.translation_runner import TranslationEngineError
from src.core.progress import (
    NOTIFICATION_LEVELS,
    CancelToken,
    OperationCancelled,
    ProgressEvent,
    ProgressLogFilter,
    checkpoint,
)
from src.core.languages import Language, engine_supports, get_language, languages_for_engine
from src.core.rtl_shaper import is_rtl_language
from src.core.translators.base import TranslationEngine
from src.core.translators.manager import TranslationManager
from src.backend.locale_manager import LocaleManager
from src.backend.settings_schema import SETTING_SPECS, coerce_setting
from src.utils.config import DEFAULT_CONFIG, ConfigManager
from src.utils.file_ops import safe_write
from src.utils.logger import mask_secrets
from src.utils.paths import get_data_dir, get_patches_dir, resource_path
from src.version import VERSION

logger = logging.getLogger(__name__)


# Engines offered in the UI; names come from the "engines.<id>" i18n keys.
SELECTABLE_ENGINES: tuple[str, ...] = (
    "google", "bing", "deepl", "gemini", "openai", "deepseek", "local_llm", "libretranslate",
)
# Shown only when "show_debug_engines" is on (layout/overflow testing, never for release).
DEBUG_ENGINES: tuple[str, ...] = ("pseudo",)


def _language_entry(language: Language) -> dict[str, str]:
    """QML model row: 'Türkçe — Turkish' style label plus searchable parts."""
    label = language.native if language.native == language.english else f"{language.native} — {language.english}"
    return {"code": language.code, "name": label, "english": language.english, "native": language.native}


def _local_path(path_or_url: str) -> str:
    """Turn a QML file URL (or plain path) into a local filesystem path."""
    raw = str(path_or_url).strip()
    if raw.lower().startswith("file:"):
        local = QUrl(raw).toLocalFile()
        if local:
            return local
        clean = urllib.parse.unquote(raw)
        for prefix in ("file:///", "file://"):
            if clean.lower().startswith(prefix):
                return clean[len(prefix):]
    return raw


def _harvest_streaming_dir(sa_dir: Path) -> list[str]:
    """Strings of every supported loose file below a StreamingAssets folder."""
    parser = StreamingAssetsParser()
    strings: list[str] = []
    for path in sorted(sa_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            strings.extend(parser.extract_strings(path))
    return strings


# Levels that stay on the dashboard instead of vanishing with a toast.
NOTICE_LEVELS: frozenset[str] = frozenset({"warning", "error"})
# The completion dialog asks for support only after this many finished runs (never on the first ones).
SUPPORT_PROMPT_MIN_RUNS = 3

ROUTE_I18N_MAP: dict[str, str] = {
    "Route 1: Native Static Patcher": "routes.route1_native",
    "Route 3: Runtime Hook (BepInEx)": "routes.route3_hook",
}


class AppBackend(QObject):
    """Primary QObject bridge exposed to QML as 'appBackend'."""

    gameChanged = pyqtSignal()
    profileChanged = pyqtSignal()
    progressChanged = pyqtSignal()
    statusChanged = pyqtSignal()
    logsChanged = pyqtSignal()
    noticesChanged = pyqtSignal()
    statsChanged = pyqtSignal()
    settingsChanged = pyqtSignal()
    toastRequested = pyqtSignal(str, str)
    reviewReady = pyqtSignal(object)
    cacheChanged = pyqtSignal()
    glossaryChanged = pyqtSignal()
    pipelineCompleted = pyqtSignal("QVariantMap", arguments=["summary"])

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state_lock = threading.RLock()
        self._worker_thread: threading.Thread | None = None
        self._translators_dirty: bool = False
        self.config = ConfigManager()
        self.tm = TranslationManager(config=self.config)
        self.pipeline = UnityTranslationPipeline(translation_manager=self.tm)
        self.pipeline.progress_callback = self._handle_progress
        self._cancel_token: CancelToken | None = None

        self._game_path: str = ""
        self._profile: UnityGameProfile | None = None
        self._status_key: str = "dashboard.status_ready"
        self._status_params: dict[str, Any] = {}
        self._is_busy: bool = False
        self._progress_val: float = 0.0
        self._progress_msg: str = ""
        self._logs: list[dict[str, str]] = []
        # Persistent dashboard notices: {level, key, params}; localized when read.
        self._notices: list[dict[str, Any]] = []
        self._harvest_count: int = 0
        self._progress_log_filter = ProgressLogFilter()

    def _translate_text(self, key_or_text: str, **kwargs: Any) -> str:
        """Resolve localized string if key exists in LocaleManager."""
        lm = LocaleManager.get_instance()
        if lm:
            tmpl = lm.t(key_or_text, key_or_text)
            for k, v in kwargs.items():
                tmpl = tmpl.replace(f"{{{k}}}", str(v))
            return mask_secrets(tmpl)
        return mask_secrets(key_or_text)

    def _set_status(self, key_or_text: str, **kwargs: Any) -> None:
        """Remember the status key; it is localized on read so UI language switches apply."""
        with self._state_lock:
            self._status_key = key_or_text
            self._status_params = kwargs
        self.statusChanged.emit()

    def _notify(self, level: str, key: str, **params: Any) -> None:
        """Log, show in the status bar and toast one localized message.

        Warnings and errors also stay on the dashboard until dismissed: players rarely read logs.
        """
        self.add_log(level, key, **params)
        if level in NOTICE_LEVELS:
            self._post_notice(level, key, **params)
        self._set_status(key, **params)
        self.toastRequested.emit(self._translate_text(key, **params), level)

    def _post_notice(self, level: str, key: str, **params: Any) -> None:
        """Show a message on the dashboard card; the same key replaces its older entry."""
        with self._state_lock:
            self._notices = [n for n in self._notices if n["key"] != key]
            self._notices.append({"level": level, "key": key, "params": params})
        self.noticesChanged.emit()

    def _warn(self, level: str, key: str, **params: Any) -> None:
        """Log a message and keep it visible on the dashboard."""
        self.add_log(level, key, **params)
        self._post_notice(level, key, **params)

    @pyqtProperty("QVariantList", notify=noticesChanged)
    def notices(self) -> list[dict[str, str]]:
        """Dashboard notices as ``{level, text}`` rows, localized at read time."""
        with self._state_lock:
            current = list(self._notices)
        return [
            {"level": n["level"], "text": self._translate_text(n["key"], **n["params"])} for n in current
        ]

    @pyqtSlot()
    def dismissNotices(self) -> None:
        """Hide every dashboard notice (also called when a new run starts)."""
        with self._state_lock:
            self._notices = []
        self.noticesChanged.emit()

    @pyqtSlot(str)
    def onUiLanguageChanged(self, lang_code: str) -> None:
        """Persist the UI language and re-emit localized properties."""
        if self.config.get("ui_language") != lang_code:
            self.config.set("ui_language", lang_code)
        self.profileChanged.emit()
        self.statusChanged.emit()
        self.settingsChanged.emit()
        self.noticesChanged.emit()

    @pyqtSlot()
    def restoreLastSession(self) -> None:
        """Re-open the last successfully profiled game if its folder still exists."""
        last = str(self.config.get("last_game_path", "") or "")
        if last and Path(last).exists():
            self.selectGame(last)

    @pyqtProperty("QVariantMap", constant=True)
    def windowGeometry(self) -> dict[str, Any]:
        """Window size/state saved on the previous close (read once at startup)."""
        return {
            "width": int(self.config.get("window_width", 0) or 0),
            "height": int(self.config.get("window_height", 0) or 0),
            "maximized": bool(self.config.get("window_maximized", False)),
        }

    @pyqtSlot(int, int, bool)
    def saveWindowState(self, width: int, height: int, maximized: bool) -> None:
        """Remember the normal (non-maximized) window size and the maximized flag."""
        for key, value in (("window_width", width), ("window_height", height), ("window_maximized", maximized)):
            self.config.set(key, value, auto_save=False)
        self.config.save()

    def _handle_progress(self, event: ProgressEvent) -> None:
        """Update the progress bar on every event; log only phase changes and milestones."""
        message = self._translate_text(event.key, **event.message_params())
        with self._state_lock:
            self._progress_val = event.fraction
            self._progress_msg = message
            should_log = self._progress_log_filter.should_log(event)
        self.progressChanged.emit()
        level = NOTIFICATION_LEVELS.get(event.key)
        if level:
            self.add_log(level, message)
            self.toastRequested.emit(message, level)
            if level in NOTICE_LEVELS:
                self._post_notice(level, event.key, **event.message_params())
            return
        if not should_log:
            return
        # Templates without their own counters get a "[n/m]" prefix (e.g. harvest phases).
        template = self._translate_text(event.key)
        show_counter = event.total > 1 and "{current}" not in template
        prefix = f"[{event.current}/{event.total}] " if show_counter else ""
        self.add_log("info", f"{prefix}{message}")

    def add_log(self, level: str, message: str, **kwargs: Any) -> None:
        """Add formatted log entry with timestamp, resolving i18n keys if available."""
        msg = self._translate_text(message, **kwargs)
        ts = time.strftime("%H:%M:%S")
        with self._state_lock:
            self._logs.append({"level": level, "message": msg, "ts": ts})
            if len(self._logs) > 500:
                self._logs.pop(0)
        self.logsChanged.emit()

    @pyqtProperty(str, notify=gameChanged)
    def gamePath(self) -> str:
        return self._game_path

    @pyqtProperty(str, notify=profileChanged)
    def unityVersion(self) -> str:
        return self._profile.unity_version if self._profile else self._translate_text("common.unknown")

    @pyqtProperty(str, notify=profileChanged)
    def architecture(self) -> str:
        if not self._profile:
            return self._translate_text("common.unknown")
        backend = "IL2CPP" if self._profile.is_il2cpp else "Mono"
        bits = "64-bit" if self._profile.is_64bit else "32-bit"
        return f"{backend} ({bits})"

    @pyqtProperty(str, notify=profileChanged)
    def recommendedRoute(self) -> str:
        if not self._profile:
            return self._translate_text("dashboard.select_game_first")
        route_key = ROUTE_I18N_MAP.get(self._profile.recommended_route, self._profile.recommended_route)
        return self._translate_text(route_key)

    @pyqtProperty(bool, notify=profileChanged)
    def hasTextMeshPro(self) -> bool:
        return bool(self._profile and self._profile.has_text_mesh_pro)

    @pyqtProperty(bool, notify=profileChanged)
    def hasBepInEx(self) -> bool:
        return bool(self._profile and self._profile.has_bepinex)

    @pyqtProperty(bool, notify=statusChanged)
    def isBusy(self) -> bool:
        return self._is_busy

    @pyqtProperty(str, notify=statusChanged)
    def statusText(self) -> str:
        with self._state_lock:
            key, params = self._status_key, dict(self._status_params)
        return self._translate_text(key, **params)

    @pyqtProperty(float, notify=progressChanged)
    def progress(self) -> float:
        return self._progress_val

    @pyqtProperty(str, notify=progressChanged)
    def progressMessage(self) -> str:
        return self._progress_msg

    @pyqtProperty(int, notify=statsChanged)
    def harvestCount(self) -> int:
        return self._harvest_count

    @pyqtProperty(list, notify=logsChanged)
    def logs(self) -> list[dict[str, str]]:
        with self._state_lock:
            return list(self._logs)

    @pyqtProperty(str, constant=True)
    def version(self) -> str:
        return VERSION

    @pyqtProperty(str, notify=settingsChanged)
    def selectedEngine(self) -> str:
        return str(self.config.get("engine", "google"))

    @pyqtProperty(int, notify=settingsChanged)
    def batchSize(self) -> int:
        return int(self.config.get("batch_size", 100))

    @pyqtProperty(str, notify=settingsChanged)
    def targetLanguage(self) -> str:
        return str(self.config.get("target_language", "tr"))

    @pyqtProperty(list, notify=settingsChanged)
    def supportedTargetLanguages(self) -> list[dict[str, str]]:
        """Catalog languages the selected engine can handle (native name + English name)."""
        return [_language_entry(lang) for lang in languages_for_engine(self.selectedEngine)]

    @pyqtProperty(bool, notify=settingsChanged)
    def languagesSupportedByEngine(self) -> bool:
        """False when the chosen source/target pair is outside the selected engine's set."""
        engine = self.selectedEngine
        return engine_supports(engine, self.targetLanguage) and engine_supports(engine, self.sourceLanguage)

    @pyqtSlot(str)
    def setTargetLanguage(self, lang_code: str) -> None:
        lang = get_language(lang_code)
        if lang is None:
            logger.warning("Ignoring unknown target language code: %r", lang_code)
            return
        self.config.set("target_language", lang.code)
        self.settingsChanged.emit()

    @pyqtProperty(str, notify=settingsChanged)
    def sourceLanguage(self) -> str:
        """Game source language code, or 'auto' to let the engine detect it."""
        return str(self.config.get("source_language", "auto"))

    @pyqtSlot(str)
    def setSourceLanguage(self, lang_code: str) -> None:
        code = lang_code.strip()
        if code.lower() == "auto":
            self.config.set("source_language", "auto")
            self.settingsChanged.emit()
            return
        lang = get_language(code)
        if lang is None:
            logger.warning("Ignoring unknown source language code: %r", lang_code)
            return
        self.config.set("source_language", lang.code)
        self.settingsChanged.emit()

    @pyqtProperty(bool, notify=settingsChanged)
    def targetIsRtl(self) -> bool:
        """True when the selected target language is written right to left."""
        return is_rtl_language(self.targetLanguage)

    @pyqtProperty(bool, notify=settingsChanged)
    def rtlStaticShaping(self) -> bool:
        """Whether right-to-left targets are shipped in reshaped visual order."""
        return bool(self.config.get("rtl_static_shaping", True))

    @pyqtSlot(bool)
    def setRtlStaticShaping(self, enabled: bool) -> None:
        self.config.set("rtl_static_shaping", enabled)
        self.settingsChanged.emit()

    @pyqtSlot(str)
    def selectGame(self, path: str) -> None:
        """Set game path, profile engine, and notify UI (ignored while a job runs)."""
        if self._is_busy:
            return
        target = Path(_local_path(path))
        if not target.exists():
            self._set_status("dashboard.path_not_found")
            return

        self._game_path = str(target)
        self.gameChanged.emit()

        try:
            self._profile = EngineProfiler.profile_game(target)
            self._set_status("dashboard.status_ready")
            self.profileChanged.emit()
            self.add_log("success", "dashboard.game_selected", path=self._game_path)
            if self.config.get("last_game_path") != self._game_path:
                self.config.set("last_game_path", self._game_path)
        except ValueError as val_err:
            logger.warning("Game validation error: %s", val_err)
            self._profile = None
            self.profileChanged.emit()
            self._notify("error", str(val_err))
        except Exception as exc:
            logger.exception("Profiling failed")
            self._profile = None
            self.profileChanged.emit()
            self._notify("error", "dashboard.status_error", error=str(exc))

    def _game_dir(self) -> Path:
        """Folder of the selected game (the path may point at the executable)."""
        target = Path(self._game_path)
        return target if target.is_dir() else target.parent

    def _can_start_job(self, toast: bool = False) -> bool:
        """True when a Unity game is profiled and no job runs; reports why otherwise."""
        if self._is_busy:
            return False
        if self._profile is None:
            key = "dashboard.select_game_first" if not self._game_path else "profiler.error_not_unity"
            if toast:
                self._notify("warning", key)
            else:
                self.add_log("warning", key)
            return False
        return True

    def _run_in_background(self, job: Callable[[], None]) -> None:
        """Mark the backend busy and run ``job`` on a daemon thread until it returns."""
        with self._state_lock:
            self._is_busy = True
            self._progress_val = 0.0
            self._progress_msg = ""
            self._progress_log_filter = ProgressLogFilter()
        self.progressChanged.emit()
        self.statusChanged.emit()

        def _worker() -> None:
            try:
                job()
            finally:
                with self._state_lock:
                    self._is_busy = False
                    dirty = self._translators_dirty
                    self._translators_dirty = False
                if dirty:
                    self.tm.reset_translators()
                self.statusChanged.emit()

        self._worker_thread = threading.Thread(target=_worker, daemon=True)
        self._worker_thread.start()

    @pyqtSlot()
    def startLocalization(self) -> None:
        """Run localization pipeline in background thread."""
        if not self._can_start_job(toast=True):
            return
        token = self._cancel_token = CancelToken()
        self.dismissNotices()
        self._set_status("dashboard.status_translating")
        self.add_log("info", "dashboard.status_translating")
        self._run_in_background(lambda: self._run_localization(token))

    def _tmp_override_font(self) -> str | None:
        """System font for XUnity's OverrideFontTextMeshPro from Settings; None = choose automatically.

        An empty setting must stay None: ``""`` would switch the override off and skip the
        automatic system-font choice that covers glyphs the fallback bundle lacks.
        """
        return str(self.config.get("tmp_system_font", "") or "").strip() or None

    def _override_font_ugui(self) -> str:
        """Font for XUnity's OverrideFont (uGUI), from Settings."""
        return str(self.config.get("override_font_ugui", "") or "").strip()

    def _selected_engine_enum(self) -> TranslationEngine:
        """Configured engine, falling back to Google for unknown values."""
        try:
            return TranslationEngine(str(self.config.get("engine", "google")).lower())
        except ValueError:
            return TranslationEngine.GOOGLE

    def _execute_pipeline(self, cancel: CancelToken) -> int:
        """Run the unified pipeline with the current settings and publish the review."""
        self.pipeline.runner.batch_size = max(1, self.batchSize)
        self.pipeline.tmp_override_font = self._tmp_override_font()
        self.pipeline.override_font = self._override_font_ugui()
        total = self.pipeline.run_unified_localization_pipeline(
            self._game_dir(),
            target_lang=self.targetLanguage,
            engine=self._selected_engine_enum(),
            patch_loose_files=self.patchLooseFiles,
            source_lang=self.sourceLanguage,
            rtl_shaping=self.rtlStaticShaping,
            bilingual_mode=bool(self.config.get("bilingual_mode", False)),
            bilingual_template=str(self.config.get("bilingual_template", "{target}\n({source})")),
            cancel=cancel,
        )
        if self.pipeline.last_session is not None:
            self.reviewReady.emit(self.pipeline.last_session)
        self._save_harvest_report()
        return total

    def _save_harvest_report(self) -> None:
        """Write what the last scan saw and skipped to the data folder for diagnosis."""
        stats = self.pipeline.last_harvest_stats
        if stats is None:
            return
        path = get_data_dir() / "harvest_report.json"
        try:
            safe_write(path, json.dumps(stats.to_report(), ensure_ascii=False, indent=2), make_backup=False)
        except OSError as exc:
            logger.warning("Could not save the harvest report: %s", exc)
            return
        self.add_log("info", "dashboard.harvest_report_saved", path=str(path))

    def _run_localization(self, cancel: CancelToken) -> None:
        """Background job: run the pipeline and report its outcome."""
        try:
            self._ensure_runtime(cancel)
            total = self._execute_pipeline(cancel)
            self._report_outcome(total)
        except RuntimeSetupError as exc:
            logger.error("Runtime setup failed: %s", exc.detail)
            reason = self._translate_text(exc.reason_key, error=exc.detail[:200])
            self._notify("error", "dashboard.runtime_setup_failed", reason=reason)
        except OperationCancelled:
            self.add_log("warning", "dashboard.status_cancelled")
            self._set_status("dashboard.status_cancelled")
        except TranslationEngineError as exc:
            logger.error("Translation engine failed: %s", exc)
            self._notify("error", "dashboard.status_translation_failed", error=str(exc)[:300])
        except FileNotFoundError as exc:
            logger.warning("Pipeline prerequisite missing: %s", exc)
            self._warn("warning", "dashboard.prerequisite_missing", error=str(exc))
            self._set_status("dashboard.prerequisite_missing", error=str(exc))
        except Exception as exc:
            logger.exception("Pipeline failure")
            self._warn("error", "dashboard.status_error", error=str(exc))
            self._set_status("dashboard.status_error", error=str(exc))
        finally:
            self._cancel_token = None
            self.cacheChanged.emit()

    def _report_outcome(self, total: int) -> None:
        """Completed with a count, or 'no strings' only when the harvest itself found none."""
        if total == 0 and self.pipeline.last_harvest_count == 0:
            self._warn("warning", "dashboard.status_no_strings_found")
            self._set_status("dashboard.status_no_strings_found")
            return
        self.add_log("success" if total else "warning", "dashboard.status_completed", count=total)
        self._set_status("dashboard.status_completed", count=total)
        if not self._profile_hook_ready():
            self._warn("warning", "dashboard.status_hook_missing_proxy")
        else:
            self._report_runtime_log()

        # Publish completion summary event for UI modal
        harvested = self.pipeline.last_harvest_count
        failed = 0
        rejected = 0
        unchanged = 0
        if self.pipeline.last_session is not None:
            failed = sum(1 for r in self.pipeline.last_session.rows if r.status == "failed")
            rejected = sum(1 for r in self.pipeline.last_session.rows if r.status in ("rejected", "invalid"))
            unchanged = sum(1 for r in self.pipeline.last_session.rows if r.status == "unchanged")

        rate_val = (total / harvested * 100) if harvested > 0 else 100.0
        runs = int(self.config.get("completed_runs", 0) or 0) + (1 if total else 0)
        self.config.set("completed_runs", runs)
        summary = {
            "show_support": runs >= SUPPORT_PROMPT_MIN_RUNS and not self.config.get("hide_support_prompt", False),
            "total_harvested": harvested,
            "translated_count": total,
            "failed_count": failed,
            "rejected_count": rejected,
            "unchanged_count": unchanged,
            "success_rate": f"{rate_val:.1f}%",
            "game_name": self._game_dir().name,
            "game_path": str(self._game_dir()),
            "target_lang": self.targetLanguage,
            "has_exe": bool(self._profile and self._profile.game_exe and self._profile.game_exe.is_file()),
        }
        self.pipelineCompleted.emit(summary)

    def _report_runtime_log(self) -> None:
        """Tell whether BepInEx has really started in the game, from its own LogOutput.log."""
        status = inspect_runtime_log(self._game_dir())
        if status.state == LOG_OK:
            self._warn("success", "dashboard.runtime_log_ok")
        elif status.state == LOG_ERROR:
            self._warn("warning", "dashboard.runtime_log_error", error=status.detail)
        else:
            self._warn("info", "dashboard.runtime_log_missing")

    def _profile_hook_ready(self) -> bool:
        """Re-check the hook after a run: translations only show up in game with it."""
        self._reprofile()
        return bool(self._profile and self._profile.has_bepinex)

    def _harvest_in_background(
        self, harvest: Callable[[], list[str]], success_key: str, error_key: str
    ) -> None:
        """Run a toolbox harvester off the UI thread and publish its string count."""

        def _job() -> None:
            try:
                count = len(harvest())
            except Exception as exc:
                logger.exception("Toolbox harvest failed")
                self.add_log("error", error_key, error=str(exc))
                self._set_status(error_key, error=str(exc))
                return
            self._harvest_count = count
            self.statsChanged.emit()
            self.add_log("success", success_key, count=count)
            self._set_status(success_key, count=count)

        self._run_in_background(_job)

    @pyqtSlot()
    def harvestAssembly(self) -> None:
        """Scan Mono Managed/Assembly-CSharp.dll in background."""
        if not self._can_start_job():
            return
        managed = next(iter(self._game_dir().glob("**/Managed")), None)
        if managed is None:
            self.add_log("warning", "toolbox.managed_not_found")
            return
        self.add_log("info", "dashboard.status_harvesting_mono")
        self._harvest_in_background(
            lambda: AssemblyHarvester.harvest_managed_dir(managed),
            "dashboard.status_harvested_count", "dashboard.status_error",
        )

    @pyqtSlot()
    def harvestMetadata(self) -> None:
        """Scan IL2CPP global-metadata.dat in background."""
        if not self._can_start_job():
            return
        metadata = next(iter(self._game_dir().glob("**/global-metadata.dat")), None)
        if metadata is None:
            self.add_log("warning", "toolbox.metadata_not_found")
            return
        self.add_log("info", "toolbox.scanning_metadata_file", filename=metadata.name)
        self._harvest_in_background(
            lambda: MetadataHarvester.harvest(metadata),
            "toolbox.metadata_harvested_count", "toolbox.metadata_harvest_error",
        )

    @pyqtSlot()
    def harvestAssets(self) -> None:
        """Deep scan all .assets and scene level* files in background."""
        if not self._can_start_job():
            return
        profile = self._profile
        data_dir = profile.data_dir if profile else None
        if profile is None or data_dir is None or not data_dir.is_dir():
            self.add_log("warning", "toolbox.data_dir_not_found")
            return
        self.add_log("info", "toolbox.scanning_assets")
        self._harvest_in_background(
            lambda: self._scan_assets(profile, data_dir),
            "toolbox.assets_harvested_count", "toolbox.assets_harvest_error",
        )

    def _scan_assets(self, profile: UnityGameProfile, data_dir: Path) -> list[str]:
        """Scan every asset file; files too large for the free memory are skipped and reported."""
        stats = HarvestStats()
        guard_on = bool(self.config.get("harvest_memory_guard", True))
        if bool(self.config.get("harvest_isolated", True)):
            strings = scan_assets_isolated(profile, memory_guard=guard_on, progress=self._handle_progress, stats=stats)
        else:
            strings = AssetHarvester.harvest_data_dir(
                data_dir, typetree_generator=create_typetree_generator(profile), progress=self._handle_progress,
                stats=stats, memory_guard=MemoryGuard(enabled=guard_on),
            )
        skipped = stats.files_skipped_for_memory
        if skipped:
            names = ", ".join(f"{f.name} ({format_size(f.disk_bytes)})" for f in skipped[:3])
            self._warn("warning", "pipeline.harvest_warn_oversized", count=len(skipped), names=names)
        return strings

    @pyqtSlot()
    def harvestStreamingAssets(self) -> None:
        """Scan StreamingAssets folder in background."""
        if not self._can_start_job():
            return
        sa_dir = next((p for p in self._game_dir().glob("**/StreamingAssets") if p.is_dir()), None)
        if sa_dir is None:
            self.add_log("warning", "toolbox.streaming_not_found")
            return
        self.add_log("info", "toolbox.scanning_streaming")
        self._harvest_in_background(
            lambda: _harvest_streaming_dir(sa_dir),
            "toolbox.streaming_harvested_count", "toolbox.streaming_harvest_error",
        )

    @pyqtSlot()
    def injectFont(self) -> None:
        """Provision the version-matched TMP fallback bundle and wire it into the config."""
        if not self._can_start_job(toast=True) or self._profile is None:
            return
        profile = self._profile
        self._run_in_background(lambda: self._provision_font(profile))

    @pyqtSlot(str, str, str, result=bool)
    def applyFontConfiguration(self, preset: str, custom_ttf_path: str = "", system_font_name: str = "") -> bool:
        """Configure font settings for uGUI and TMP, installing font files if needed."""
        if self._profile is None:
            self._notify("error", "dashboard.select_game_first")
            return False
        profile = self._profile
        preset = preset.strip().lower()
        try:
            if preset == "custom_ttf":
                local = _local_path(custom_ttf_path)
                if not local:
                    self._notify("error", "toolbox.font_custom_path_required")
                    return False
                rel_path = FontBootstrap.install_custom_font(profile.game_path, local)
                self.setSetting("custom_font_path", local)
                self.setSetting("override_font_ugui", rel_path)
                self.setSetting("font_preset", "custom_ttf")
            elif preset == "system_font":
                sys_font = (system_font_name or "Arial").strip()
                self.setSetting("override_font_ugui", sys_font)
                self.setSetting("tmp_system_font", sys_font)
                self.setSetting("font_preset", "system_font")
            else:
                self.setSetting("override_font_ugui", "")
                self.setSetting("tmp_system_font", "")
                self.setSetting("font_preset", "default_arial")

            self.injectFont()
            return True
        except Exception as exc:
            logger.exception("Failed configuring font")
            self.add_log("error", "toolbox.font_custom_error", error=str(exc))
            self._notify("error", "toolbox.font_custom_error")
            return False

    def _provision_font(self, profile: UnityGameProfile) -> None:
        """Background job: download/deploy the TMP bundle (cached) and write the INI."""
        try:
            font_bundle = FontProvisioner.provision(profile.game_path, profile.unity_version, self._handle_progress)
            success = FontBootstrap.inject_font(
                profile.game_path,
                target_lang=self.targetLanguage,
                source_lang=resolve_source_language(self.sourceLanguage),
                tmp_override_font=self._tmp_override_font(),
                preferred_bundle=font_bundle,
                override_font=self._override_font_ugui(),
                is_il2cpp=profile.is_il2cpp,
                linux=profile.is_linux_build,
            )
            key = "toolbox.font_inject_success" if success else "toolbox.font_inject_fail"
            self._notify("success" if success else "error", key)
        except Exception as exc:
            logger.exception("Font provisioning failed")
            self.add_log("error", "toolbox.font_inject_error", error=str(exc))

    def _ensure_runtime(self, cancel: CancelToken) -> None:
        """Install or repair BepInEx + XUnity for this game when it is missing or mismatched.

        Runs silently at the start of every translation; the user only sees a status line.
        Raises ``RuntimeSetupError`` when the download or install fails.
        """
        profile = self._profile
        if profile is None:
            return
        if not (profile.is_windows_build or profile.is_linux_build):
            # Pinned packages exist for Windows and Linux players only (not macOS).
            self._warn("warning", "toolbox.hook_platform_unsupported")
            return
        if profile.is_linux_build:
            self._post_notice("info", "dashboard.linux_native_hint")
        elif sys.platform.startswith("linux"):
            self._post_notice("info", "dashboard.proton_hint")
        args = (profile.is_64bit, profile.is_il2cpp, profile.metadata_version, profile.is_linux_build)
        if not HookInstaller.needs_install(self._game_dir(), *args):
            HookInstaller.apply_runtime_fixes(
                self._game_dir(), profile.unity_version, profile.is_il2cpp, self._handle_progress
            )
            return
        if not profile.architecture_certain:
            self._warn("warning", "dashboard.bitness_uncertain")
        checkpoint(cancel)
        self._set_status("dashboard.status_preparing_runtime")
        self.add_log("info", "dashboard.status_preparing_runtime")
        HookInstaller.ensure_runtime(
            self._game_dir(),
            is_64bit=profile.is_64bit,
            is_il2cpp=profile.is_il2cpp,
            target_lang=self.targetLanguage,
            progress_callback=self._handle_progress,
            unity_version=profile.unity_version,
            source_lang=resolve_source_language(self.sourceLanguage),
            metadata_version=profile.metadata_version,
            linux=profile.is_linux_build,
            executable_name=profile.game_exe.name if profile.game_exe else "",
        )
        self._reprofile()
        checkpoint(cancel)

    def _reprofile(self) -> None:
        """Refresh the profile after hooks changed the game folder."""
        try:
            self._profile = EngineProfiler.profile_game(Path(self._game_path))
        except ValueError as exc:
            logger.warning("Re-profiling after hook change failed: %s", exc)
            self._profile = None
        self.profileChanged.emit()

    @pyqtSlot()
    def exportPatchPackage(self) -> None:
        """Create a standalone offline patch package (folder + ZIP) for the active game.

        Refused up front, with the reason, when the package could not work for
        players: no installed hook, or no translations for the target language.
        """
        if not self._can_start_job(toast=True):
            return
        game_dir = self._game_dir()
        target_lang = self.targetLanguage
        source_lang = resolve_source_language(self.sourceLanguage)
        check = PatchExporter.preflight(game_dir, target_lang)
        if check.errors:
            for key in check.errors[1:]:
                self.add_log("error", key, lang=target_lang)
            self._notify("error", check.errors[0], lang=target_lang)
            return
        for key in check.warnings:
            self.add_log("warning", key)
        self.add_log("info", "dashboard.patch_exporting")
        self.toastRequested.emit(self._translate_text("dashboard.patch_exporting"), "info")

        def _job() -> None:
            try:
                out_path = PatchExporter.export_patch(game_dir, target_lang=target_lang, source_lang=source_lang)
                self._notify("success", "dashboard.patch_exported_success", name=archive_path(out_path).name)
            except Exception as exc:
                logger.exception("Patch export error")
                self.add_log("error", "dashboard.patch_export_failed", error=str(exc))
                self.toastRequested.emit(
                    self._translate_text("dashboard.patch_export_failed", error=str(exc)), "error"
                )

        self._run_in_background(_job)

    @pyqtSlot()
    def openPatchFolder(self) -> None:
        """Open the Patches export folder in the system file manager (any platform)."""
        patch_root = get_patches_dir()
        patch_root.mkdir(parents=True, exist_ok=True)
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(patch_root))):
            logger.warning("Could not open patch folder %s", patch_root)
            self.add_log("error", "dashboard.status_error", error=str(patch_root))

    @pyqtSlot()
    def openGameFolder(self) -> None:
        """Open the active game folder in the system file manager."""
        if not self._game_path:
            return
        folder = self._game_dir()
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
            logger.warning("Could not open game folder %s", folder)

    @pyqtSlot()
    def launchGame(self) -> None:
        """Launch the profiled game executable (non-blocking)."""
        if not self._profile or not self._profile.game_exe or not self._profile.game_exe.is_file():
            self._notify("error", "dashboard.game_exe_not_found")
            return
        try:
            command = launch_command(self._profile)
        except LaunchError as exc:
            self._notify("error", exc.reason_key)
            return
        try:
            import subprocess
            subprocess.Popen(command.argv, cwd=str(command.cwd))
            self._notify("info", "dashboard.game_launched")
        except OSError as exc:
            logger.error("Failed to launch game %s: %s", command.argv, exc)
            self._notify("error", "dashboard.status_error", error=str(exc))

    @pyqtSlot()
    def uninstallHooks(self) -> None:
        """Remove BepInEx proxy hooks to return game to vanilla state."""
        if not self._game_path or self._is_busy:
            return
        removed = HookInstaller.uninstall(self._game_dir())
        key = "toolbox.hook_uninstall_success" if removed else "toolbox.hook_uninstall_fail"
        self._notify("info" if removed else "error", key)
        if removed:
            self._reprofile()

    @pyqtSlot()
    def stopTranslation(self) -> None:
        """Ask the running pipeline to stop at its next checkpoint (busy until it does)."""
        if self._cancel_token is None or self._cancel_token.is_cancelled:
            return
        self._cancel_token.cancel()
        self._set_status("dashboard.status_cancelling")
        self.add_log("warning", "dashboard.status_cancelling")

    @pyqtProperty("QVariantMap", notify=settingsChanged)
    def settings(self) -> dict[str, Any]:
        """Current values of every schema-declared setting (bound by the Settings view)."""
        return {key: self.config.get(key, DEFAULT_CONFIG.get(key)) for key in SETTING_SPECS}

    @pyqtSlot(str, "QVariant")
    def setSetting(self, key: str, value: Any) -> None:
        """Validate, persist and apply one setting immediately (engines are rebuilt)."""
        try:
            coerced = coerce_setting(key, value)
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("Rejected setting %s=%r: %s", key, value, exc)
            return
        if self.config.get(key, DEFAULT_CONFIG.get(key)) == coerced:
            return
        self.config.set(key, coerced)
        # Translators capture keys, models and network options at creation time.
        with self._state_lock:
            busy = self._is_busy
            if busy:
                self._translators_dirty = True
        if not busy:
            self.tm.reset_translators()
        self.settingsChanged.emit()

    @pyqtSlot("QVariant")
    def addTranslationMemoryFile(self, file_url: Any) -> None:
        """Append a file chosen in a FileDialog (URL or path) to the translation memory list."""
        url = file_url if isinstance(file_url, QUrl) else QUrl(str(file_url))
        path = url.toLocalFile() if url.isLocalFile() else str(file_url)
        if not path:
            return
        current = [line for line in str(self.config.get("tm_files", "")).splitlines() if line.strip()]
        if path not in current:
            self.setSetting("tm_files", "\n".join(current + [path]))
            self.setSetting("tm_enabled", True)

    @pyqtProperty(list, notify=settingsChanged)
    def supportedEngines(self) -> list[dict[str, str]]:
        """Selectable engines with localized names (single source for every view)."""
        return [
            {"id": engine_id, "name": self._translate_text(f"engines.{engine_id}")}
            for engine_id in self._engine_ids()
        ]

    def _engine_ids(self) -> tuple[str, ...]:
        """Selectable engines; the pseudo-localization engine only in developer mode."""
        if self.config.get("show_debug_engines", False):
            return SELECTABLE_ENGINES + DEBUG_ENGINES
        return SELECTABLE_ENGINES

    @pyqtSlot(str)
    def setSelectedEngine(self, engine_id: str) -> None:
        """Persist the engine immediately (used by the Dashboard quick settings)."""
        if engine_id not in self._engine_ids():
            return
        self.config.set("engine", engine_id)
        self.settingsChanged.emit()

    @pyqtProperty(bool, notify=settingsChanged)
    def patchLooseFiles(self) -> bool:
        """Also rewrite StreamingAssets files in place (off by default: data files mix logic keys)."""
        return bool(self.config.get("patch_loose_files", False))

    @pyqtSlot(bool)
    def setPatchLooseFiles(self, enabled: bool) -> None:
        self.config.set("patch_loose_files", enabled)
        self.settingsChanged.emit()

    @pyqtProperty(int, notify=cacheChanged)
    def cacheEntryCount(self) -> int:
        return self.tm.cache.count()

    @pyqtSlot()
    def clearCache(self) -> None:
        """Delete every cached translation (manual review fixes included)."""
        if self._is_busy:
            return
        self.tm.cache.clear()
        self.cacheChanged.emit()
        self.add_log("warning", "settings.cache_cleared")
        self.toastRequested.emit(self._translate_text("settings.cache_cleared"), "warning")

    @pyqtProperty(list, notify=glossaryChanged)
    def glossaryTerms(self) -> list[dict[str, str]]:
        """Glossary entries sorted by term, for the glossary editor."""
        terms = self.tm.glossary.terms
        return [{"term": term, "replacement": terms[term]} for term in sorted(terms, key=str.lower)]

    @pyqtSlot(str, str)
    def addGlossaryTerm(self, term: str, replacement: str) -> None:
        """Add or update a glossary entry applied to every translated string."""
        if not term.strip() or not replacement.strip():
            return
        self.tm.glossary.add_term(term.strip(), replacement.strip())
        self.tm.refresh_term_protection()
        self.glossaryChanged.emit()

    @pyqtSlot(str)
    def removeGlossaryTerm(self, term: str) -> None:
        if self.tm.glossary.remove_term(term):
            self.tm.refresh_term_protection()
            self.glossaryChanged.emit()

    @pyqtSlot()
    def clearLogs(self) -> None:
        """Clear all logs in list."""
        with self._state_lock:
            self._logs.clear()
        self.logsChanged.emit()

    @pyqtSlot()
    def copyLogs(self) -> None:
        """Copy all log entries to OS clipboard."""
        with self._state_lock:
            logs_snapshot = list(self._logs)
        text = "\n".join(f"[{item['ts']}] [{item['level'].upper()}] {item['message']}" for item in logs_snapshot)
        cb = QGuiApplication.clipboard()
        if cb:
            cb.setText(text)
            self.add_log("info", "console.logs_copied")

    @pyqtSlot(str, result=str)
    def get_asset_url(self, relative_path: str) -> str:
        """Return a QUrl string for a relative asset path (frozen bundle and dev compatible)."""
        full = resource_path(relative_path)
        return QUrl.fromLocalFile(str(full)).toString()

    def shutdown(self) -> None:
        """Release engine sessions; cached translations stay on disk for the next run."""
        if self._cancel_token is not None:
            self._cancel_token.cancel()
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        self.tm.close()
        logger.info("AppBackend shut down cleanly.")
