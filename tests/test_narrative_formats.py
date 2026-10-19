# -*- coding: utf-8 -*-
"""Tests for column-aware string tables, Yarn line splitting and compiled Ink stories."""

import json
from pathlib import Path

import pytest

from src.core.parsers.ink_json import ink_strings, is_ink_document, translate_ink
from src.core.parsers.loc_table import detect_layout, header_language, looks_like_identifier
from src.core.parsers.streaming_assets import StreamingAssetsParser
from src.core.parsers.text_formats import sniff_and_extract
from src.core.parsers.yarn_lines import split_yarn_line, translate_yarn_text, yarn_strings

# --- Localization tables -----------------------------------------------------


@pytest.mark.parametrize(
    "cell, code",
    [
        ("English", "en"),
        ("English [en-US]", "en"),
        ("English (United States)", "en"),
        ("fr", "fr"),
        ("pt-BR", "pt"),
        ("zh_CN", "zh"),
        ("Türkçe", "tr"),
        ("Japanese", "ja"),
        ("Key", None),
        ("ID", None),
        ("It happens", None),
        ("Description", None),
    ],
)
def test_header_language(cell: str, code: str | None) -> None:
    assert header_language(cell) == code


def test_detect_layout_prefers_requested_source_language() -> None:
    layout = detect_layout(["Key", "Type", "Desc", "Japanese", "English", "Turkish"], "en", "tr")
    assert layout is not None
    assert (layout.key_col, layout.source_col, layout.target_col) == (0, 4, 5)


def test_detect_layout_yarn_compiled_string_table() -> None:
    layout = detect_layout(["id", "text", "file", "node", "lineNumber", "lock", "comment"])
    assert layout is not None
    assert (layout.key_col, layout.source_col) == (0, 1)


def test_detect_layout_plain_sheet_is_not_a_table() -> None:
    assert detect_layout(["Start Game", "Options", "Quit"]) is None


def test_table_extraction_skips_keys_headers_and_other_locales() -> None:
    text = "Key,English,French\nMENU_START,Start Game,Commencer\nMENU_QUIT,Quit,Quitter\n"
    assert sniff_and_extract(text) == ["Start Game", "Quit"]


@pytest.mark.parametrize("value", ["MENU_START", "ui.title", "menuStart", "Audio/bgm_01"])
def test_identifier_heuristic_flags_keys(value: str) -> None:
    assert looks_like_identifier(value) is True


@pytest.mark.parametrize("value", ["OK", "Start Game", "Mr. Smith", "Hello!"])
def test_identifier_heuristic_keeps_display_text(value: str) -> None:
    assert looks_like_identifier(value) is False


def test_csv_apply_only_rewrites_source_and_empty_target(tmp_path: Path) -> None:
    sheet = tmp_path / "strings.csv"
    sheet.write_bytes(
        "Key,English,Turkish\r\nMENU_START,Start Game,\r\nMENU_QUIT,Quit,Çık\r\n".encode("utf-8")
    )
    parser = StreamingAssetsParser(target_lang="tr")
    assert parser.extract_strings(sheet) == ["Start Game", "Quit"]

    translations = {"Start Game": "Oyunu Başlat", "Quit": "Çıkış", "MENU_START": "MENÜ"}
    assert parser.apply_translations(sheet, translations) is True

    content = sheet.read_bytes().decode("utf-8-sig")
    assert content.splitlines() == [
        "Key,English,Turkish",
        "MENU_START,Oyunu Başlat,Oyunu Başlat",
        "MENU_QUIT,Çıkış,Çık",
    ]
    assert "\r\n" in content  # line endings preserved


def test_plain_csv_apply_never_rewrites_identifiers(tmp_path: Path) -> None:
    sheet = tmp_path / "menu.csv"
    sheet.write_text("Start Game,btn_start\nQuit,btn_quit\n", encoding="utf-8")
    parser = StreamingAssetsParser()
    assert parser.extract_strings(sheet) == ["Start Game", "Quit"]
    parser.apply_translations(sheet, {"Start Game": "Başla", "btn_start": "x"})
    assert sheet.read_text(encoding="utf-8-sig").splitlines()[0] == "Başla,btn_start"


# --- Yarn Spinner ---------------------------------------------------------------

YARN_SCRIPT = (
    "title: Start\n"
    "position: 0,0\n"
    "---\n"
    "Sally: Hello there! #line:a1b2c3\n"
    "-> Ask about the weather #line:opt1\n"
    "Narrator: The rain stops. <<wait 1>>\n"
    "<<jump End>>\n"
    "===\n"
)


def test_split_yarn_line_parts() -> None:
    parsed = split_yarn_line("-> Sally: Hi {$name}! <<if $met>> #line:abc")
    assert parsed is not None
    assert parsed.lead == "-> "
    assert parsed.speaker == "Sally"
    assert parsed.body == "Hi {$name}!"
    assert parsed.tail == " <<if $met>> #line:abc"


def test_yarn_strings_skip_headers_tags_and_commands() -> None:
    assert yarn_strings(YARN_SCRIPT) == [
        "Sally", "Hello there!", "Ask about the weather", "Narrator", "The rain stops.",
    ]


def test_yarn_sniffed_from_untyped_text_asset() -> None:
    assert "Hello there!" in sniff_and_extract(YARN_SCRIPT)
    assert all("#line" not in s for s in sniff_and_extract(YARN_SCRIPT))


def test_translate_yarn_preserves_structure() -> None:
    translations = {
        "Sally": "Sally",
        "Hello there!": "Merhaba!",
        "Ask about the weather": "Havayı sor",
        "Narrator": "Anlatıcı",
        "The rain stops.": "Yağmur durur.",
        "position": "konum",
    }
    out = translate_yarn_text(YARN_SCRIPT, translations).splitlines()
    assert out == [
        "title: Start",
        "position: 0,0",
        "---",
        "Sally: Merhaba! #line:a1b2c3",
        "-> Havayı sor #line:opt1",
        "Anlatıcı: Yağmur durur. <<wait 1>>",
        "<<jump End>>",
        "===",
    ]


def test_yarn_file_roundtrip(tmp_path: Path) -> None:
    yarn_file = tmp_path / "intro.yarn"
    yarn_file.write_text(YARN_SCRIPT, encoding="utf-8")
    parser = StreamingAssetsParser()
    assert "Hello there!" in parser.extract_strings(yarn_file)
    assert parser.apply_translations(yarn_file, {"Hello there!": "Merhaba!"}) is True
    assert "Sally: Merhaba! #line:a1b2c3" in yarn_file.read_text(encoding="utf-8-sig")


# --- Ink -------------------------------------------------------------------------

INK_STORY = {
    "inkVersion": 21,
    "root": [
        [
            "^Hello, ", "ev", {"VAR?": "name"}, "out", "/ev", "^! How are you?", "\n",
            "#", "^speaker_tag", "/#",
            ["ev", "str", "^Fine thanks", "/str", "/ev", {"*": "0.c-0", "flg": 4}],
            {"c-0": ["^ I am fine.", "\n", {"->": "end"}], "#f": 5},
        ],
        "done",
        {"end": ["^The End.", "\n", "end"]},
    ],
    "listDefs": {},
}


def test_ink_detection_and_extraction() -> None:
    assert is_ink_document(INK_STORY) is True
    assert is_ink_document({"root": []}) is False
    assert ink_strings(INK_STORY) == [
        "Hello,", "! How are you?", "Fine thanks", "I am fine.", "The End.",
    ]


def test_ink_translation_keeps_glue_tags_and_paths() -> None:
    patched = translate_ink(INK_STORY, {"Hello,": "Merhaba,", "I am fine.": "İyiyim.", "end": "son"})
    container = patched["root"][0]
    assert container[0] == "^Merhaba, "
    assert container[8] == "^speaker_tag"
    assert container[11]["c-0"][0] == "^ İyiyim."
    assert container[11]["c-0"][2] == {"->": "end"}
    assert INK_STORY["root"][0][0] == "^Hello, "  # original untouched


def test_ink_json_file_roundtrip(tmp_path: Path) -> None:
    story = tmp_path / "story.ink.json"
    story.write_text(json.dumps(INK_STORY), encoding="utf-8")
    parser = StreamingAssetsParser()
    assert "The End." in parser.extract_strings(story)
    assert "ev" not in parser.extract_strings(story)
    assert parser.apply_translations(story, {"The End.": "Son."}) is True
    data = json.loads(story.read_text(encoding="utf-8"))
    assert data["root"][2]["end"][0] == "^Son."
