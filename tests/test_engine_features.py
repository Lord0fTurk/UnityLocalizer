# -*- coding: utf-8 -*-
"""Tests for translation memory, protected terms, cache toggle, AI/DeepL/Libre engines."""

import json
from pathlib import Path
from typing import Any

import pytest

from src.core.syntax_guard import UnitySyntaxGuard, set_protected_terms
from src.core.translation_memory import TranslationMemory, load_table, load_tmx
from src.core.translators import ai_translator as ai_module
from src.core.translators import deepl as deepl_module
from src.core.translators import libretranslate as libre_module
from src.core.translators.ai_translator import AISettings, ChatTranslator, build_system_prompt, parse_xml_items
from src.core.translators.base import TranslationEngine, TranslationResult
from src.core.translators.deepl import DeepLTranslator
from src.core.translators.libretranslate import LibreTranslateTranslator
from src.core.translators.manager import TranslationManager
from src.core.translators.network import NetworkSettings
from src.utils.config import ConfigManager


@pytest.fixture(autouse=True)
def _reset_terms_and_sleep(monkeypatch: Any) -> Any:
    for module in (ai_module, deepl_module, libre_module):
        monkeypatch.setattr(module.time, "sleep", lambda s: None)
    yield
    set_protected_terms([])


# --- Translation memory ---------------------------------------------------------------


def test_tmx_picks_language_pair(tmp_path: Path) -> None:
    tmx = tmp_path / "m.tmx"
    tmx.write_text(
        '<tmx version="1.4"><body>'
        '<tu><tuv xml:lang="en-US"><seg>Start</seg></tuv><tuv xml:lang="tr"><seg>Başla</seg></tuv>'
        '<tuv xml:lang="de"><seg>Starten</seg></tuv></tu>'
        '<tu><tuv xml:lang="en"><seg>Quit</seg></tuv><tuv xml:lang="de"><seg>Beenden</seg></tuv></tu>'
        "</body></tmx>",
        encoding="utf-8",
    )
    assert load_tmx(tmx, "en", "tr") == {"Start": "Başla"}
    assert load_tmx(tmx, "en", "de") == {"Start": "Starten", "Quit": "Beenden"}


def test_tables_json_and_xunity_files(tmp_path: Path) -> None:
    assert load_table("Key,English,Turkish\nk1,Start,Başla\n", ",", "en", "tr") == {"Start": "Başla"}
    assert load_table("Start\tBaşla\nQuit\tÇık\n", "\t", "en", "tr") == {"Start": "Başla", "Quit": "Çık"}
    (tmp_path / "a.json").write_text(json.dumps([{"source": "Hi", "target": "Selam"}]), encoding="utf-8")
    (tmp_path / "b.txt").write_text("Hello=Merhaba\nLine\\nTwo=Satır\\nİki\n", encoding="utf-8")
    memory = TranslationMemory.load([tmp_path / "a.json", tmp_path / "b.txt", tmp_path / "missing.tmx"], "en", "tr")
    assert memory.lookup("Hi") == "Selam"
    assert memory.lookup("Line\nTwo") == "Satır\nİki"
    assert len(memory) == 3


def test_fuzzy_match_requires_identical_placeholders() -> None:
    memory = TranslationMemory({"You found {0} gold coins!": "{0} altın buldun!"}, fuzzy_threshold=0.85)
    assert memory.lookup("You found {0} gold coin!") == "{0} altın buldun!"
    assert memory.lookup("You found {1} gold coins!") is None
    assert TranslationMemory({"Hello world": "Merhaba dünya"}).lookup("Hello worlds") is None  # fuzzy off


# --- Protected terms ------------------------------------------------------------------


def test_protected_terms_are_tokens_and_must_survive() -> None:
    set_protected_terms(["Aria", "Night City"])
    protected, tags = UnitySyntaxGuard.protect("Aria reached Night City, unlike Ariana.")
    assert tags == ["Aria", "Night City"] and "Ariana" in protected
    assert UnitySyntaxGuard.validate_integrity("Aria waits", "Arya bekliyor")[0] is False
    assert UnitySyntaxGuard.repair_missing_tokens("Aria waits {0}", "bekliyor {0}") is None
    set_protected_terms([])
    assert UnitySyntaxGuard.protect("Aria")[1] == []


# --- Manager: cache toggle, memory, batch size -------------------------------------------


class _Echo:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def translate_batch(self, texts: list[str], sl: str, tl: str) -> list[TranslationResult]:
        self.seen.extend(texts)
        return [TranslationResult(t, f"<{t}>", sl, tl, TranslationEngine.GOOGLE, True) for t in texts]

    def close(self) -> None:
        pass


class _Cache:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def get_many(self, texts: list[str], *args: Any) -> dict[str, str]:
        return {t: self.store[t] for t in texts if t in self.store}

    def set_many(self, translations: dict[str, str], *args: Any) -> None:
        self.store.update(translations)


def _manager(tmp_path: Path, **config: Any) -> tuple[TranslationManager, _Echo, _Cache]:
    cfg = ConfigManager(tmp_path / "c.json")
    for key, value in config.items():
        cfg.set(key, value, auto_save=False)
    cache = _Cache()
    manager = TranslationManager(config=cfg, cache=cache)  # type: ignore[arg-type]
    echo = _Echo()
    manager._translators[TranslationEngine.GOOGLE] = echo  # type: ignore[assignment]
    return manager, echo, cache


def test_memory_hits_skip_engine_and_cache_toggle(tmp_path: Path) -> None:
    (tmp_path / "tm.json").write_text(json.dumps({"Start": "Başla"}), encoding="utf-8")
    manager, echo, cache = _manager(tmp_path, tm_enabled=True, tm_files=str(tmp_path / "tm.json"), use_cache=False)
    results = manager.translate_batch(["Start", "Quit", ""], "en", "tr")
    assert [r.translated_text for r in results] == ["Başla", "<Quit>", ""]
    assert results[0].metadata.get("from_memory") is True
    assert echo.seen == ["Quit"] and cache.store == {}  # cache disabled: nothing stored


def test_cache_used_when_enabled(tmp_path: Path) -> None:
    manager, echo, cache = _manager(tmp_path)
    manager.translate_batch(["Quit"], "en", "tr")
    manager.translate_batch(["Quit"], "en", "tr")
    assert echo.seen == ["Quit"] and cache.store == {"Quit": "<Quit>"}


def test_protected_terms_come_from_config(tmp_path: Path) -> None:
    _manager(tmp_path, protected_terms="Aria\n  \nNight City")
    assert UnitySyntaxGuard.protect("Aria")[1] == ["Aria"]


def test_ai_engines_use_ai_batch_size(tmp_path: Path) -> None:
    manager, _, _ = _manager(tmp_path, ai_batch_size=7)
    assert manager.batch_size_for(TranslationEngine.GEMINI, 50) == 7
    assert manager.batch_size_for(TranslationEngine.LOCAL_LLM, 50) == 7
    assert manager.batch_size_for(TranslationEngine.GOOGLE, 50) == 50
    assert manager.batch_size_for(TranslationEngine.BING, 300) == 100  # Edge hard cap
    assert manager.batch_size_for(TranslationEngine.DEEPL, 300) == 300


# --- AI engines -------------------------------------------------------------------------


def test_ai_settings_and_prompt() -> None:
    cfg = {"ai_temperature": 5, "ai_custom_prompt": "  Formal tone. ", "gemini_safety": "bogus", "local_llm_timeout": 900}
    settings = AISettings.from_config(cfg)
    assert settings.temperature == 1.0 and settings.gemini_safety == "BLOCK_NONE"
    assert AISettings.from_config(cfg, local=True).timeout == 900
    prompt = build_system_prompt("ceb", settings.style_guide)
    assert "Cebuano (ceb)" in prompt and prompt.rstrip().endswith("Formal tone.") and "{0}" in prompt


def test_parse_xml_items_tolerates_fences() -> None:
    reply = "```xml\n<items><item id=\"0\"> Bir </item><item id='1'>İki</item></items>\n```"
    assert parse_xml_items(reply) == {0: "Bir", 1: "İki"}


class _FakeChat(ChatTranslator):
    def __init__(self, replies: list[Any]) -> None:
        super().__init__("key", "model", AISettings(request_delay=0.0, retries=1))
        self._client = object()
        self.replies = replies
        self.requests: list[str] = []

    def _complete(self, system: str, user: str) -> str:
        self.requests.append(user)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def test_chat_batch_retries_missing_items_individually() -> None:
    chat = _FakeChat(['<items><item id="0">Selam {0}</item></items>', "Dünya"])
    results = chat.translate_batch(["Hello {0}", "World"], "en", "tr")
    assert [r.translated_text for r in results] == ["Selam {0}", "Dünya"]
    assert "<item id=\"1\">" in chat.requests[0]


def test_chat_retries_then_reports_failure() -> None:
    chat = _FakeChat([RuntimeError("quota"), RuntimeError("quota")])
    result = chat.translate("Hi", "en", "tr")
    assert result.success is False and "quota" in (result.error or "")
    assert len(chat.requests) == 2


class _ApiError(Exception):
    def __init__(self, status: int, message: str = "error") -> None:
        super().__init__(message)
        self.status_code = status


def test_chat_invalid_key_disables_engine_without_retries() -> None:
    chat = _FakeChat([_ApiError(401, "invalid api key")])
    first = chat.translate("Hi", "en", "tr")
    batch = chat.translate_batch(["One", "Two", "Three"], "en", "tr")
    assert first.success is False and "invalid api key" in (first.error or "")
    assert all(not r.success for r in batch)
    assert len(chat.requests) == 1  # no retry, no per-item fallback, nothing after the fatal error


def test_chat_failed_batch_is_not_multiplied_into_single_requests() -> None:
    chat = _FakeChat([TimeoutError("timeout"), TimeoutError("timeout")])
    results = chat.translate_batch([f"line {i}" for i in range(15)], "en", "tr")
    assert all(not r.success for r in results)
    assert len(chat.requests) == 2  # the batch and its single retry


def test_chat_rejected_batch_falls_back_to_single_items() -> None:
    chat = _FakeChat([_ApiError(400, "context length exceeded"), "Bir", "İki"])
    results = chat.translate_batch(["One", "Two"], "en", "tr")
    assert [r.translated_text for r in results] == ["Bir", "İki"]
    assert len(chat.requests) == 3


# --- DeepL & LibreTranslate ---------------------------------------------------------------


class _Resp:
    def __init__(self, status: int, data: Any = None, text: str = "") -> None:
        self.status_code, self._data, self.text = status, data, text

    def json(self) -> Any:
        return self._data


class _Session:
    def __init__(self, responder: Any) -> None:
        self.responder = responder
        self.bodies: list[dict[str, Any]] = []

    def post(self, url: str, json: dict[str, Any], **kwargs: Any) -> _Resp:
        self.bodies.append(json)
        return self.responder(json)

    def close(self) -> None:
        pass


def test_deepl_batches_fifty_and_sends_formality() -> None:
    deepl = DeepLTranslator("k:fx", formality="more", settings=NetworkSettings(max_retries=2))
    deepl.session = _Session(lambda body: _Resp(200, {"translations": [{"text": t.upper()} for t in body["text"]]}))  # type: ignore[assignment]
    results = deepl.translate_batch([f"t{i}" for i in range(60)], "EN", "TR")
    assert [len(b["text"]) for b in deepl.session.bodies] == [50, 10]
    assert deepl.session.bodies[0]["formality"] == "prefer_more" and results[59].translated_text == "T59"


def test_deepl_quota_is_final() -> None:
    deepl = DeepLTranslator("k:fx", settings=NetworkSettings(max_retries=3))
    deepl.session = _Session(lambda body: _Resp(456, text="Quota exceeded"))  # type: ignore[assignment]
    result = deepl.translate("Hi")
    assert result.success is False and "456" in (result.error or "") and len(deepl.session.bodies) == 1


def test_libretranslate_batch_and_key() -> None:
    libre = LibreTranslateTranslator("http://libre:5000/", api_key="secret", settings=NetworkSettings(max_retries=1))
    libre.session = _Session(lambda body: _Resp(200, {"translatedText": [q.upper() for q in body["q"]]}))  # type: ignore[assignment]
    results = libre.translate_batch(["a {0}", "b"], "en", "tr")
    assert [r.translated_text for r in results] == ["A {0}", "B"]
    assert libre.session.bodies[0]["api_key"] == "secret" and libre.url == "http://libre:5000/translate"
