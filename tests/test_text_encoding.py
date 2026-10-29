# -*- coding: utf-8 -*-
"""Loose files in Shift-JIS, GBK, Big5, Windows code pages and UTF-16 keep their text and encoding."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from src.core.parsers import text_encoding
from src.core.parsers.streaming_assets import StreamingAssetsParser
from src.core.parsers.text_encoding import (
    TextEncoding,
    UnencodableTextError,
    decode_bytes,
    decode_file,
    detect_codec,
)

JA_LONG = "ようこそ、旅人よ。この村には古い言い伝えがあります。\n" * 12
ZH_SHORT = "欢迎来到我们的村庄。\n你好，勇士！\n"
ZH_LONG = "欢迎来到我们的村庄。这里有一个古老的传说。\n" * 12
ZH_TW_LONG = "歡迎來到我們的村莊。這裡有一個古老的傳說。\n" * 12
KO_LONG = "우리 마을에 오신 것을 환영합니다. 오래된 전설이 있습니다.\n" * 12
RU_SHORT = "Добро пожаловать в нашу деревню.\nЧто вам угодно?\n"
RU_LONG = "Добро пожаловать в нашу деревню. Здесь есть древняя легенда.\n" * 12
FR_SHORT = "Bienvenue à l'auberge, voyageur fatigué.\nUn café ou un thé ?\n"
FR_LONG = "Bienvenue à l'auberge, voyageur fatigué. Un café, peut-être ?\n" * 12
DE_LONG = "Willkommen im Dorf, müder Reisender. Möchtest du einen Tee?\n" * 12
PL_LONG = "Witaj w naszej wiosce, podróżniku. Czy chcesz herbatę albo kawę?\n" * 6
TR_LONG = "Köyümüze hoş geldin yolcu. Çay mı kahve mi istersin?\n" * 12

# (id, codec the game used, text, source language hint)
ENCODED_SAMPLES = [
    ("sjis menu", "cp932", '{"start": "ゲームを始める", "quit": "終了する"}', ""),
    ("sjis long, wrong hint", "cp932", JA_LONG, "en"),
    ("sjis long, ja hint", "cp932", JA_LONG, "ja"),
    ("gbk long", "gbk", ZH_LONG, ""),
    ("gbk short, zh hint", "gbk", ZH_SHORT, "zh-CN"),
    ("big5 long, zh-TW hint", "big5", ZH_TW_LONG, "zh-TW"),
    ("cp949 long", "cp949", KO_LONG, ""),
    ("cp1251 short", "cp1251", RU_SHORT, ""),
    ("cp1251 long, ru hint", "cp1251", RU_LONG, "ru"),
    ("cp1252 short, en hint", "cp1252", FR_SHORT, "en"),
    ("cp1252 long", "cp1252", FR_LONG, ""),
    ("cp1252 german, de hint", "cp1252", DE_LONG, "de"),
    ("cp1250 polish, pl hint", "cp1250", PL_LONG, "pl"),
    ("cp1254 turkish, tr hint", "cp1254", TR_LONG, "tr"),
    ("cp1257 lithuanian, lt hint", "cp1257", "Sveiki atvykę į mūsų kaimą, keliauninke. Ar norite arbatos?\n" * 6, "lt"),
    ("repeated french line, 6 MB", "cp1252", FR_SHORT * 70000, ""),
    ("utf-16 without BOM, ascii", "utf-16-le", "key,text\nstart,Start the game\nquit,Leave the village\n", ""),
    ("utf-16 without BOM, japanese", "utf-16-le", "ようこそ、旅人よ。\nお茶はいかがですか？\n", ""),
]


@pytest.mark.parametrize("name, codec, text, hint", ENCODED_SAMPLES, ids=[s[0] for s in ENCODED_SAMPLES])
def test_legacy_encodings_decode_to_the_original_text_and_round_trip(
    name: str, codec: str, text: str, hint: str
) -> None:
    data = text.encode(codec)
    decoded = decode_bytes(data, hint)
    assert decoded is not None and decoded.text == text
    assert decoded.encoding.encode(decoded.text) == data  # writing back changes no byte


def test_western_text_settles_on_windows_1252_whatever_the_detector_guesses() -> None:
    # charset-normalizer calls this cp1250/German; a Western game's file is Windows-1252.
    assert detect_codec(DE_LONG.encode("cp1252")) == "cp1252"
    assert detect_codec(FR_LONG.encode("cp1252")) == "cp1252"
    assert detect_codec((FR_SHORT * 70000).encode("cp1252")) == "cp1252"  # once labeled "Czech" / cp1250


def test_look_alike_latin_code_pages_need_the_language_hint() -> None:
    turkish = TR_LONG.encode("cp1254")
    assert detect_codec(turkish) == "cp1252"  # without a hint nothing tells cp1254 from cp1252
    assert detect_codec(turkish, "tr") == "cp1254"


@pytest.mark.parametrize(
    "data, codec, bom",
    [
        ("Başla\n".encode("utf-8-sig"), "utf-8", b"\xef\xbb\xbf"),
        ("Start\nQuit\n".encode("utf-16"), "utf-16-le", b"\xff\xfe"),
        ("ゲーム\n".encode("utf-16-le"), None, b""),
    ],
)
def test_byte_order_marks_are_detected_and_written_back(data: bytes, codec: str | None, bom: bytes) -> None:
    decoded = decode_bytes(data)
    assert decoded is not None and decoded.encoding.bom == bom
    if codec:
        assert decoded.encoding.codec == codec
    assert decoded.encoding.encode(decoded.text) == data


def test_big_endian_and_utf32_marks() -> None:
    big = b"\xfe\xff" + "Quit".encode("utf-16-be")
    assert decode_bytes(big).text == "Quit"  # type: ignore[union-attr]
    wide = b"\xff\xfe\x00\x00" + "Quit".encode("utf-32-le")
    decoded = decode_bytes(wide)
    assert decoded is not None and decoded.text == "Quit" and decoded.encoding.codec == "utf-32-le"
    assert decoded.encoding.encode("Quit") == wide


def test_plain_utf8_ascii_and_empty_files() -> None:
    assert decode_bytes("Başla ve çık".encode("utf-8")).text == "Başla ve çık"  # type: ignore[union-attr]
    assert decode_bytes(b'{"a": "Start"}').encoding == TextEncoding()  # type: ignore[union-attr]
    empty = decode_bytes(b"")
    assert empty is not None and empty.text == "" and empty.encoding == TextEncoding()


def test_nul_bytes_are_not_mistaken_for_utf8() -> None:
    decoded = decode_bytes("Start".encode("utf-16-le"))
    assert decoded is not None and decoded.text == "Start" and decoded.encoding.codec == "utf-16-le"
    big = decode_bytes("Start".encode("utf-16-be"))
    assert big is not None and big.text == "Start" and big.encoding.codec == "utf-16-be"


def test_an_undetectable_file_is_reported_not_guessed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                                      caplog: pytest.LogCaptureFixture) -> None:
    class _NoMatch:
        def best(self) -> None:
            return None

    monkeypatch.setattr(text_encoding, "from_bytes", lambda *args, **kwargs: _NoMatch())
    path = tmp_path / "blob.txt"
    path.write_bytes(b"\x81\x82\x83\x00\xfe")
    with caplog.at_level(logging.WARNING):
        assert decode_file(path) is None
    assert "encoding could not be determined" in caplog.text


def test_a_missing_file_is_reported(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR):
        assert decode_file(tmp_path / "gone.txt") is None
    assert "Failed to read" in caplog.text


def test_text_the_encoding_cannot_hold_raises_a_clear_error() -> None:
    with pytest.raises(UnencodableTextError, match="cp932 cannot represent"):
        TextEncoding("cp932").encode("Köyümüze hoş geldin")
    assert TextEncoding("utf-8").encode("Köyümüze") == "Köyümüze".encode("utf-8")


# --- loose files through the parser -------------------------------------------------


def _write(tmp_path: Path, name: str, codec: str, text: str, bom: bytes = b"") -> Path:
    path = tmp_path / name
    path.write_bytes(bom + text.encode(codec))
    return path


PARSER_CASES: list[tuple[str, str, str, str, list[str], dict[str, str]]] = [
    ("menu.json", "cp932", "ja", '{"start": "ゲームを始める", "quit": "終了する", "id": "btn_start"}',
     ["ゲームを始める", "終了する"], {"ゲームを始める": "新しいゲーム", "終了する": "やめる"}),
    ("dialog.txt", "gbk", "zh-CN", ZH_SHORT, ["欢迎来到我们的村庄。", "你好，勇士！"],
     {"欢迎来到我们的村庄。": "欢迎光临。", "你好，勇士！": "你好！"}),
    ("story.txt", "cp1251", "ru", RU_SHORT, ["Добро пожаловать в нашу деревню.", "Что вам угодно?"],
     {"Добро пожаловать в нашу деревню.": "Здравствуйте.", "Что вам угодно?": "Чем помочь?"}),
    ("shop.txt", "cp1252", "fr", FR_SHORT, ["Bienvenue à l'auberge, voyageur fatigué.", "Un café ou un thé ?"],
     {"Bienvenue à l'auberge, voyageur fatigué.": "Entrez, étranger.", "Un café ou un thé ?": "Un thé ?"}),
    ("movie.srt", "cp1251", "ru",
     "1\n00:00:01,000 --> 00:00:03,000\nДобрый вечер, друзья мои.\n\n2\n00:00:04,000 --> 00:00:05,000\nДо свидания.\n",
     ["Добрый вечер, друзья мои.", "До свидания."], {"До свидания.": "Пока."}),
    ("scene.nani", "gbk", "zh-CN", "Kohaku: 欢迎来到我们的村庄。\n", ["欢迎来到我们的村庄。"],
     {"欢迎来到我们的村庄。": "你好。"}),
]


@pytest.mark.parametrize("name, codec, lang, text, strings, translations", PARSER_CASES,
                         ids=[c[0] for c in PARSER_CASES])
def test_parser_harvests_clean_text_and_patches_in_the_same_encoding(
    tmp_path: Path, name: str, codec: str, lang: str, text: str, strings: list[str], translations: dict[str, str]
) -> None:
    path = _write(tmp_path, name, codec, text)
    parser = StreamingAssetsParser(source_lang=lang, target_lang="xx")
    assert parser.extract_strings(path) == strings
    assert parser.apply_translations(path, translations) is True
    patched = path.read_bytes().decode(codec)  # still decodes in the game's own encoding
    for source, target in translations.items():
        assert target in patched and source not in patched
    assert path.with_suffix(path.suffix + ".bak").read_bytes() == text.encode(codec)
    assert parser.extract_strings(path) == strings  # a re-run reads the untouched backup


def test_untranslated_lines_keep_their_exact_bytes(tmp_path: Path) -> None:
    path = _write(tmp_path, "story.txt", "cp1251", RU_SHORT)
    parser = StreamingAssetsParser(source_lang="ru")
    assert parser.apply_translations(path, {"Что вам угодно?": "Чем помочь?"})
    first_line = RU_SHORT.splitlines(keepends=True)[0].encode("cp1251")
    assert path.read_bytes().startswith(first_line)


def test_utf16_csv_keeps_its_byte_order_mark(tmp_path: Path) -> None:
    text = "key,text\nstart,Start the game\nquit,Leave the village\n"
    path = _write(tmp_path, "ui.csv", "utf-16-le", text, bom=b"\xff\xfe")
    parser = StreamingAssetsParser(source_lang="en", target_lang="tr")
    assert parser.extract_strings(path) == ["Start the game", "Leave the village"]
    assert parser.apply_translations(path, {"Start the game": "Oyunu başlat", "Leave the village": "Köyden ayrıl"})
    out = path.read_bytes()
    assert out.startswith(b"\xff\xfe")
    assert "Oyunu başlat" in out.decode("utf-16") and "key,text" in out.decode("utf-16")


def test_utf8_bom_is_kept_and_plain_utf8_stays_without_one(tmp_path: Path) -> None:
    with_bom = _write(tmp_path, "a.json", "utf-8", '{"t": "Start the game"}', bom=b"\xef\xbb\xbf")
    without = _write(tmp_path, "b.json", "utf-8", '{"t": "Start the game"}')
    parser = StreamingAssetsParser()
    assert parser.apply_translations(with_bom, {"Start the game": "Oyunu başlat"})
    assert parser.apply_translations(without, {"Start the game": "Oyunu başlat"})
    assert with_bom.read_bytes().startswith(b"\xef\xbb\xbf") and not without.read_bytes().startswith(b"\xef\xbb\xbf")


def test_xml_declared_as_gb2312_is_read_and_written_as_gb2312(tmp_path: Path) -> None:
    text = '<?xml version="1.0" encoding="gb2312"?>\n<root><item>欢迎来到我们的村庄。</item></root>'
    path = _write(tmp_path, "menu.xml", "gbk", text)
    parser = StreamingAssetsParser(source_lang="zh-CN")
    assert parser.extract_strings(path) == ["欢迎来到我们的村庄。"]
    assert parser.apply_translations(path, {"欢迎来到我们的村庄。": "欢迎光临。"})
    assert "欢迎光临。" in path.read_bytes().decode("gbk")


def test_a_translation_the_files_encoding_cannot_hold_leaves_the_file_alone(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    original = '{"start": "ゲームを始める"}'
    path = _write(tmp_path, "menu.json", "cp932", original)
    parser = StreamingAssetsParser(source_lang="ja", target_lang="tr")
    with caplog.at_level(logging.WARNING):
        assert parser.apply_translations(path, {"ゲームを始める": "Oyunu başlat"}) is False
    assert path.read_bytes() == original.encode("cp932")
    assert not path.with_suffix(".json.bak").exists()
    assert "Left menu.json unpatched" in caplog.text


def test_an_unreadable_encoding_is_never_patched(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "blob.txt"
    path.write_bytes(b"\x81\x82\x83\xfe\x80 not text")
    monkeypatch.setattr(text_encoding, "detect_codec", lambda *args, **kwargs: None)
    parser = StreamingAssetsParser()
    assert parser.extract_strings(path) == []
    assert parser.apply_translations(path, {"x": "y"}) is False
    assert path.read_bytes() == b"\x81\x82\x83\xfe\x80 not text"


def test_json_written_back_is_valid_in_the_original_encoding(tmp_path: Path) -> None:
    path = _write(tmp_path, "menu.json", "cp932", '{"start": "ゲームを始める", "n": 3}')
    assert StreamingAssetsParser(source_lang="ja").apply_translations(path, {"ゲームを始める": "新しいゲーム"})
    data: Any = json.loads(path.read_bytes().decode("cp932"))
    assert data == {"start": "新しいゲーム", "n": 3}


def test_unhinted_legacy_detection_is_marked_as_a_guess() -> None:
    from src.core.parsers.text_encoding import decode_bytes

    assert decode_bytes(DE_LONG.encode("cp1252")).guessed
    polish = "Zażółć gęślą jaźń. Cześć!"
    hinted = decode_bytes(polish.encode("cp1250"), "pl")  # the language's own code page, even for short text
    assert hinted.text == polish and not hinted.guessed
    assert not decode_bytes("héllo wörld".encode("utf-8")).guessed
