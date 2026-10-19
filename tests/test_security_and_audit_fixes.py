# -*- coding: utf-8 -*-
"""Regression tests for security, concurrency, and logic fixes from the project audit."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from src.backend.settings_schema import coerce_setting
from src.core.cache import TranslationCache
from src.core.glossary import GlossaryManager
from src.core.hook_layout import dictionary_path, safe_lang_segment
from src.core.hook_manager.ini_merge import merge_ini
from src.core.languages import canonical_from_bing
from src.core.parsers.ink_json import ink_strings
from src.core.parsers.streaming_assets import StreamingAssetsParser
from src.core.parsers.xunity_regex import build_regex_entry
from src.core.parsers.yarn_lines import split_yarn_line
from src.core.pipeline.orchestrator import UnityTranslationPipeline
from src.core.pipeline.patch_scripts import write_scripts
from src.core.pipeline.review_session import STATUS_ACCEPTED, STATUS_UNCHANGED, ReviewRow, ReviewSession, RunContext
from src.core.pipeline.translation_runner import BatchTranslationRunner, TranslationEngineError
from src.core.syntax_guard import UnitySyntaxGuard
from src.core.translation_memory import TranslationMemory
from src.core.translators.base import TranslationEngine, TranslationResult
from src.utils.downloader import RemoteFile
from src.utils.logger import SensitiveDataFilter, mask_secrets


def test_syntax_guard_xml_restore_with_backslashes_and_expanded_tags() -> None:
    protected, tags = UnitySyntaxGuard.protect(r"<color=#ff0000>Save path</color>", mode="xml")
    assert '<ph id="0"/>' in protected
    llm_output = protected.replace('<ph id="0"/>', '<ph id="0"></ph>').replace("Save path", r"Kayıt: D:\new\folder\1")
    restored = UnitySyntaxGuard.restore(llm_output, tags, mode="xml")
    assert restored == r"<color=#ff0000>Kayıt: D:\new\folder\1</color>"


def test_syntax_guard_repair_missing_tokens_preserves_boundary_order() -> None:
    src = "{0} {1} Hello world <sprite=1> <sprite=2>"
    repaired = UnitySyntaxGuard.repair_missing_tokens(src, "Merhaba dünya")
    assert repaired == "{0} {1} Merhaba dünya <sprite=1> <sprite=2>"


def test_glossary_skips_unity_richtext_tags(tmp_path: Path) -> None:
    glossary = GlossaryManager(glossary_path=tmp_path / "glossary.json")
    glossary.add_term("color", "renk")
    glossary.add_term("size", "boyut")
    assert glossary.apply("<color=red>The color and size</color>") == "<color=red>The renk and boyut</color>"
    assert glossary.covers("<color=red>Hello</color>", "<color=red>Merhaba</color>")
    assert not glossary.covers("<color=red>The color</color>", "<color=red>Bu ton</color>")


def test_translation_memory_blocks_xml_entity_expansion_and_handles_xmlns(tmp_path: Path) -> None:
    bomb_tmx = tmp_path / "bomb.tmx"
    bomb_tmx.write_text(
        '<?xml version="1.0"?>\n<!DOCTYPE tmx [<!ENTITY lol "lol">]>\n<tmx><body></body></tmx>',
        encoding="utf-8",
    )
    tm_bomb = TranslationMemory.load([bomb_tmx], "en", "tr")
    assert len(tm_bomb) == 0

    namespaced_tmx = tmp_path / "ns.tmx"
    namespaced_tmx.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<tmx version="1.4" xmlns="http://www.lisa.org/tmx14">\n'
        "  <body>\n"
        "    <tu>\n"
        '      <tuv xml:lang="en"><seg>Start Game</seg></tuv>\n'
        '      <tuv xml:lang="tr"><seg>Oyunu Başlat</seg></tuv>\n'
        "    </tu>\n"
        "  </body>\n"
        "</tmx>",
        encoding="utf-8",
    )
    tm = TranslationMemory.load([namespaced_tmx], "en", "tr")
    assert len(tm) == 1
    assert tm.lookup("Start Game") == "Oyunu Başlat"


def test_cache_rejects_empty_translations_and_handles_surrogates(tmp_path: Path) -> None:
    cache = TranslationCache(db_path=tmp_path / "cache.db")
    cache.set_many({"Hello": "", "World": "   ", "Valid": "Geçerli"}, "en", "tr", "google")
    hits = cache.get_many(["Hello", "World", "Valid", "surrogate_\ud800_text"], "en", "tr", "google")
    assert "Hello" not in hits
    assert "World" not in hits
    assert hits.get("Valid") == "Geçerli"


def test_safe_lang_segment_blocks_traversal(tmp_path: Path) -> None:
    assert safe_lang_segment("../../evil") == "evil"
    assert safe_lang_segment("..") == "en"
    path = dictionary_path(tmp_path, "../../evil")
    assert tmp_path in path.resolve().parents


def test_xunity_regex_rejects_anchorless_and_escapes_digit_backrefs() -> None:
    assert build_regex_entry("{0}", "{0}") is None
    assert build_regex_entry("{0} {1}", "{0} {1}") is None
    entry = build_regex_entry("Combo {0}-{0}9!", "Kombo {0}-{0}9!")
    assert entry is not None
    pattern, _ = entry
    assert "(?:\\1)9" in pattern


def test_ink_skips_logic_eval_but_keeps_choice_text() -> None:
    ink_root = {
        "inkVersion": 21,
        "root": [
            ["^Welcome to the tavern!", "\n"],
            ["ev", "str", "^quest_flag_internal", "/str", {"VAR?": "state"}, {"==": 1}, "/ev"],
            ["ev", "str", "^Ask about the dragon", "/str", "/ev", {"*": "0.c-0", "flg": 4}],
        ],
    }
    extracted = ink_strings(ink_root)
    assert "Welcome to the tavern!" in extracted
    assert "Ask about the dragon" in extracted
    assert "quest_flag_internal" not in extracted


def test_yarn_speaker_ignores_urls() -> None:
    parsed = split_yarn_line("https://example.com/docs: Visit our site #line:1")
    assert parsed is not None
    assert parsed.speaker == ""
    assert "https://example.com/docs" in parsed.body
    assert parsed.tail == " #line:1"


def test_streaming_assets_patches_xml_and_preserves_utf8_bom(tmp_path: Path) -> None:
    xml_file = tmp_path / "strings.xml"
    xml_file.write_bytes(
        b"\xef\xbb\xbf<?xml version='1.0' encoding='utf-8'?>\n<root><item>New Game</item></root>"
    )
    parser = StreamingAssetsParser()
    extracted = parser.extract_strings(xml_file)
    assert extracted == ["New Game"]

    ok = parser.apply_translations(xml_file, {"New Game": "Yeni Oyun"})
    assert ok is True
    raw = xml_file.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert "Yeni Oyun" in raw.decode("utf-8-sig")


def test_merge_ini_deduplicates_keys_and_sections() -> None:
    existing = (
        "[Service]\n"
        "Endpoint=GoogleTranslate\n"
        "Endpoint=BingTranslate\n\n"
        "[General]\n"
        "Language=en\n\n"
        "[Service]\n"
        "FallbackEndpoint=DeepL\n"
    )
    merged = merge_ini(
        existing,
        forced={"Service": {"Endpoint": ""}, "General": {"Language": "tr"}},
        defaults={"Service": {"FallbackEndpoint": ""}},
    )
    assert merged.count("[Service]") == 1
    assert merged.count("\nEndpoint=") == 1
    assert "\nEndpoint=\n" in merged
    assert "\nLanguage=tr\n" in merged


def test_runner_failed_streak_not_masked_by_offline_hits() -> None:
    class _AlwaysFailingTM:
        def concurrency_for(self, engine_type: TranslationEngine) -> int:
            return 1

        def batch_size_for(self, engine_type: TranslationEngine, fallback: int) -> int:
            return fallback

        def translate_batch(
            self,
            texts: list[str],
            source_lang: str = "auto",
            target_lang: str = "tr",
            engine_type: TranslationEngine = TranslationEngine.OPENAI,
        ) -> list[TranslationResult]:
            return [
                TranslationResult(
                    original_text=texts[0],
                    translated_text="Önbellek",
                    source_lang=source_lang,
                    target_lang=target_lang,
                    engine=engine_type,
                    success=True,
                    metadata={"from_offline": True},
                ),
                TranslationResult(
                    original_text=texts[1],
                    translated_text=texts[1],
                    source_lang=source_lang,
                    target_lang=target_lang,
                    engine=engine_type,
                    success=False,
                    error="HTTP 401",
                    metadata={"from_offline": False},
                ),
            ]

    runner = BatchTranslationRunner(_AlwaysFailingTM(), batch_size=2)  # type: ignore[arg-type]
    items = [f"Line {i}" for i in range(12)]
    with pytest.raises(TranslationEngineError):
        runner.run(items, target_lang="tr", engine=TranslationEngine.OPENAI)


def test_review_session_unchanged_edit_and_loose_file_repatch(tmp_path: Path) -> None:
    sa_dir = tmp_path / "Game_Data" / "StreamingAssets"
    sa_dir.mkdir(parents=True)
    json_file = sa_dir / "ui.json"
    json_file.write_text('{"quit": "Quit game"}', encoding="utf-8")

    context = RunContext(
        game_root=tmp_path,
        target_lang="tr",
        source_lang="en",
        engine="google",
        rtl_shaping=False,
        streaming_files=(json_file,),
    )
    row = ReviewRow(row_id=0, original="Quit game", translation="Oyundan çık", status=STATUS_ACCEPTED)
    session = ReviewSession(rows=[row], context=context)

    reverted = session.edit(0, "Quit game")
    assert reverted.status == STATUS_UNCHANGED

    edited = session.edit(0, "Oyunu Kapat")
    assert edited.dirty is True

    pipeline = UnityTranslationPipeline()
    pipeline.save_review(session)
    assert "Oyunu Kapat" in json_file.read_text(encoding="utf-8")


def test_patch_install_bat_has_no_call_set_double_expansion(tmp_path: Path) -> None:
    write_scripts(tmp_path, "../../tr&calc")
    bat = (tmp_path / "Install_Patch.bat").read_text(encoding="utf-8")
    assert "DisableDelayedExpansion" in bat
    assert "call set" not in bat
    assert "tr&calc" not in bat


def test_remote_file_rejects_traversal() -> None:
    rf = RemoteFile(url="https://example.com/dir%2F..%2F..%2Fpayload.zip", sha256="0" * 64)
    assert rf.filename == "payload.zip"
    bad = RemoteFile(url="https://example.com/..", sha256="0" * 64)
    with pytest.raises(ValueError):
        _ = bad.filename


def test_coerce_setting_rejects_bool_for_numeric_fields() -> None:
    with pytest.raises(TypeError):
        coerce_setting("batch_size", True)
    with pytest.raises(TypeError):
        coerce_setting("rate_limit_delay", False)
    assert coerce_setting("local_llm_timeout", 450) == 450


def test_mask_secrets_redacts_query_keys_basic_auth_and_tracebacks() -> None:
    raw = (
        "GET https://generativelanguage.googleapis.com/v1beta/models?key=AIzaSySecretKey1234567890 "
        "via socks5://myuser:supersecretpass@127.0.0.1:1080"
    )
    masked = mask_secrets(raw)
    assert "AIzaSySecretKey1234567890" not in masked
    assert "supersecretpass" not in masked

    filt = SensitiveDataFilter()
    try:
        raise RuntimeError("Bearer sk-proj-1234567890abcdefghijklmnop")
    except RuntimeError:
        import sys

        record = logging.LogRecord("test", logging.ERROR, __file__, 1, "boom", (), sys.exc_info())
        filt.filter(record)
        assert record.exc_info is None
        assert "sk-proj-1234567890abcdefghijklmnop" not in (record.exc_text or "")


def test_canonical_from_bing_maps_dialect_back() -> None:
    assert canonical_from_bing("zh-Hans") == "zh-CN"
    assert canonical_from_bing("nb") == "no"
    assert canonical_from_bing("en") == "en"
