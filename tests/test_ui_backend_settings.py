# -*- coding: utf-8 -*-
"""Tests for cancellation, engine settings and the settings-facing backend API."""

from pathlib import Path
from typing import Any

import pytest

from src.core.engine_profiler import UnityGameProfile
from src.core.harvesters.harvest_collector import HarvestCollector
from src.core.pipeline.translation_runner import BatchTranslationRunner
from src.core.progress import CancelToken, OperationCancelled
from src.core.translators.base import TranslationEngine, TranslationResult
from src.core.translators.manager import TranslationManager
from src.core.translators.deepl import DeepLTranslator
from src.core.translators.libretranslate import LibreTranslateTranslator
from src.core.translators.services import PseudoTranslator
from src.utils.config import ConfigManager

# --- Cancellation -------------------------------------------------------------------


class _CountingManager:
    def __init__(self, cancel_after: int, token: CancelToken) -> None:
        self.calls = 0
        self.cancel_after = cancel_after
        self.token = token

    def translate_batch(self, texts: list[str], **_: Any) -> list[TranslationResult]:
        self.calls += 1
        if self.calls == self.cancel_after:
            self.token.cancel()
        return [
            TranslationResult(original_text=t, translated_text=t + "!", source_lang="en",
                              target_lang="tr", engine=TranslationEngine.GOOGLE, success=True)
            for t in texts
        ]


def test_runner_stops_at_next_batch_after_cancel() -> None:
    token = CancelToken()
    manager = _CountingManager(cancel_after=2, token=token)
    runner = BatchTranslationRunner(manager, batch_size=10)  # type: ignore[arg-type]
    with pytest.raises(OperationCancelled):
        runner.run([f"s{i}" for i in range(100)], "tr", TranslationEngine.GOOGLE, cancel=token)
    assert manager.calls == 2  # finished batches are kept; no further requests


def test_harvest_collector_honours_cancel(tmp_path: Path) -> None:
    token = CancelToken()
    token.cancel()
    profile = UnityGameProfile(game_path=tmp_path, data_dir=tmp_path)
    with pytest.raises(OperationCancelled):
        HarvestCollector().collect(profile, token)


# --- Translator factory -------------------------------------------------------------


def _manager(tmp_path: Path, **config: Any) -> TranslationManager:
    cfg = ConfigManager(tmp_path / "config.json")
    for key, value in config.items():
        cfg.set(key, value, auto_save=False)
    return TranslationManager(config=cfg)


def test_every_engine_has_a_real_builder(tmp_path: Path) -> None:
    manager = _manager(tmp_path, libretranslate_url="http://libre.local:5000")
    libre = manager.get_translator(TranslationEngine.LIBRETRANSLATE)
    assert isinstance(libre, LibreTranslateTranslator) and libre.url == "http://libre.local:5000/translate"
    for engine in TranslationEngine:
        translator = manager.get_translator(engine)
        # Only the explicit PSEUDO engine may produce pseudo text.
        assert isinstance(translator, PseudoTranslator) == (engine is TranslationEngine.PSEUDO)


def test_deepl_formality_and_ai_settings_reach_engines(tmp_path: Path) -> None:
    manager = _manager(
        tmp_path, deepl_formality="less", ai_temperature=0.9, ai_custom_prompt="Use Gen-Z slang.",
        openai_base_url="https://openrouter.ai/api/v1", local_llm_url="http://localhost:11434",
    )
    assert manager.get_translator(TranslationEngine.DEEPL).formality == "prefer_less"
    openai = manager.get_translator(TranslationEngine.OPENAI)
    assert openai.base_url == "https://openrouter.ai/api/v1"
    assert openai.settings.temperature == 0.9 and openai.settings.style_guide == "Use Gen-Z slang."
    assert manager.get_translator(TranslationEngine.LOCAL_LLM).base_url == "http://localhost:11434/v1"


@pytest.mark.parametrize("key, pro", [("abc:fx", False), ("abc-pro-key", True)])
def test_deepl_endpoint_follows_key_type(tmp_path: Path, key: str, pro: bool) -> None:
    translator = _manager(tmp_path, deepl_key=key).get_translator(TranslationEngine.DEEPL)
    assert isinstance(translator, DeepLTranslator)
    assert ("api-free" not in translator.endpoint) is pro


def test_reset_translators_picks_up_new_keys(tmp_path: Path) -> None:
    manager = _manager(tmp_path, deepl_key="old:fx")
    first = manager.get_translator(TranslationEngine.DEEPL)
    manager.config.set("deepl_key", "new-pro", auto_save=False)
    assert manager.get_translator(TranslationEngine.DEEPL) is first
    manager.reset_translators()
    assert manager.get_translator(TranslationEngine.DEEPL).endpoint.startswith("https://api.deepl.com")


# --- AppBackend settings API ---------------------------------------------------------


@pytest.fixture()
def backend(tmp_path: Path, monkeypatch: Any) -> Any:
    import src.backend.app_backend as module

    monkeypatch.setattr(module, "ConfigManager", lambda: ConfigManager(tmp_path / "config.json"))
    return module.AppBackend()


def test_engine_list_is_localized_and_settable(backend: Any) -> None:
    ids = [engine["id"] for engine in backend.supportedEngines]
    assert ids == ["google", "bing", "deepl", "gemini", "openai", "deepseek", "local_llm", "libretranslate"]
    assert all(engine["name"] for engine in backend.supportedEngines)

    backend.setSelectedEngine("deepl")
    assert backend.selectedEngine == "deepl"
    backend.setSelectedEngine("pseudo")  # developer engine hidden by default -> ignored
    assert backend.selectedEngine == "deepl"
    backend.setSetting("show_debug_engines", True)
    assert backend.supportedEngines[-1]["id"] == "pseudo"
    backend.setSelectedEngine("pseudo")
    assert backend.selectedEngine == "pseudo"


def test_generic_settings_are_validated_and_rebuild_engines(backend: Any) -> None:
    from src.core.translators.base import TranslationEngine

    first = backend.tm.get_translator(TranslationEngine.GOOGLE)
    backend.setSetting("max_concurrency", 999)
    backend.setSetting("ai_temperature", "0.75")
    backend.setSetting("lingva_fallback", "false")
    backend.setSetting("deepl_formality", "rude")  # not a valid choice -> ignored
    backend.setSetting("unknown_key", 1)  # not in schema -> ignored
    assert backend.settings["max_concurrency"] == 32
    assert backend.settings["ai_temperature"] == 0.75
    assert backend.settings["lingva_fallback"] is False
    assert backend.settings["deepl_formality"] == "default"
    assert "unknown_key" not in backend.settings
    assert backend.tm.get_translator(TranslationEngine.GOOGLE) is not first
def test_target_rtl_and_loose_file_toggle(backend: Any) -> None:
    backend.setTargetLanguage("ar")
    assert backend.targetIsRtl is True
    backend.setTargetLanguage("tr")
    assert backend.targetIsRtl is False

    assert backend.patchLooseFiles is False
    backend.setPatchLooseFiles(True)
    assert backend.patchLooseFiles is True


def test_status_text_is_resolved_on_read(backend: Any) -> None:
    from src.backend.locale_manager import LocaleManager

    LocaleManager(default_lang="en")
    assert backend.statusText and backend.statusText != "dashboard.status_ready"


def test_stop_without_running_job_is_noop(backend: Any) -> None:
    backend.stopTranslation()
    assert backend.isBusy is False


def test_glossary_add_and_remove(backend: Any, tmp_path: Path) -> None:
    from src.core.glossary import GlossaryManager

    backend.tm.glossary = GlossaryManager(tmp_path / "glossary.json")
    backend.addGlossaryTerm(" Blade ", "Sword")
    backend.addGlossaryTerm("", "ignored")
    assert backend.glossaryTerms == [{"term": "Blade", "replacement": "Sword"}]
    backend.removeGlossaryTerm("Blade")
    assert backend.glossaryTerms == []
