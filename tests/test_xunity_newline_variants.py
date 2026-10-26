# -*- coding: utf-8 -*-
"""Texts that store "\\n" as two characters must also match once the game draws a real line break."""

from pathlib import Path

from src.core.parsers import xunity_codec
from src.core.parsers.auto_translator import AutoTranslatorParser, expand_dialogue_and_quote_variants

STORED = "Inner part.\\nNo sunlight reaches it."  # backslash + n, as read from the game data
TRANSLATED = "İç kısım.\\nGüneş ışığı ulaşmaz."


def test_stored_backslash_n_gets_a_real_line_break_variant() -> None:
    expanded = expand_dialogue_and_quote_variants({STORED: TRANSLATED})
    assert expanded[STORED] == TRANSLATED
    assert expanded["Inner part.\nNo sunlight reaches it."] == "İç kısım.\nGüneş ışığı ulaşmaz."


def test_text_without_stored_escapes_is_not_duplicated() -> None:
    assert expand_dialogue_and_quote_variants({"Hello there": "Merhaba"}) == {"Hello there": "Merhaba"}


def test_existing_real_line_break_entry_is_kept(tmp_path: Path) -> None:
    real = "Inner part.\nNo sunlight reaches it."
    expanded = expand_dialogue_and_quote_variants({STORED: TRANSLATED, real: "özel çeviri"})
    assert expanded[real] == "özel çeviri"


def test_dictionary_file_carries_both_forms(tmp_path: Path) -> None:
    path = tmp_path / "dict.txt"
    assert AutoTranslatorParser().apply_translations(path, {STORED: TRANSLATED})
    keys = {
        decoded[0]
        for line in path.read_text(encoding="utf-8-sig").split("\n")
        if not xunity_codec.is_comment(line) and (decoded := xunity_codec.decode_line(line))
    }
    assert STORED in keys
    assert "Inner part.\nNo sunlight reaches it." in keys
