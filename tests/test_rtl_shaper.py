# -*- coding: utf-8 -*-
"""Tests for static RTL shaping of Arabic/Persian/Hebrew translations."""

import pytest

from src.core.pipeline.orchestrator import prepare_for_display
from src.core.rtl_shaper import contains_rtl, is_rtl_language, shape_rtl, shape_translations
from src.core.syntax_guard import UnitySyntaxGuard


@pytest.mark.parametrize("code", ["ar", "fa", "he", "ur", "ar-SA", "fa_IR"])
def test_rtl_languages(code: str) -> None:
    assert is_rtl_language(code) is True


@pytest.mark.parametrize("code", ["tr", "en", "ja", "zh-CN", "pt-BR"])
def test_ltr_languages(code: str) -> None:
    assert is_rtl_language(code) is False


def test_plain_arabic_is_joined_and_reversed() -> None:
    shaped = shape_rtl("مرحبا")
    assert shaped == "ﺎﺒﺣﺮﻣ"
    # Presentation forms only: Unity renders them without a shaping engine.
    assert all("ﭐ" <= ch <= "﻿" for ch in shaped)


def test_ltr_text_is_untouched() -> None:
    assert shape_rtl("Hello <b>World</b> {0}") == "Hello <b>World</b> {0}"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("<b>مرحبا</b> عالم", "ﻢﻟﺎﻋ <b>ﺎﺒﺣﺮﻣ</b>"),
        ("سلام دنیا <#ff0000>قرمز</color>", "<#ff0000>ﺰﻣﺮﻗ</color> ﺎﯿﻧﺩ ﻡﻼﺳ"),
        ("[ff0000]قرمز[-] سلام", "ﻡﻼﺳ [ff0000]ﺰﻣﺮﻗ[-]"),
        ("<b><i>نص</i></b> آخر", "ﺮﺧﺁ <b><i>ﺺﻧ</i></b>"),
    ],
)
def test_paired_tags_stay_well_formed(text: str, expected: str) -> None:
    assert shape_rtl(text) == expected


def test_unpaired_tokens_keep_their_run_position() -> None:
    assert shape_rtl("اضغط <sprite=1> للقفز") == "ﺰﻔﻘﻠﻟ <sprite=1> ﻂﻐﺿﺍ"
    assert shape_rtl("الذهب: {0}") == "{0} :ﺐﻫﺬﻟﺍ"


def test_line_breaks_keep_line_order() -> None:
    shaped = shape_rtl("سطر واحد\nسطر اثنان\\nثلاثة")
    lines = shaped.replace("\\n", "\n").split("\n")
    assert len(lines) == 3
    assert lines[0] == shape_rtl("سطر واحد")
    assert "\\n" in shaped


@pytest.mark.parametrize(
    "text",
    [
        "<color=red>خطر</color> {0} <size=20>كبير</size>",
        "[b]عريض[/b] {player.name} <br> سطر",
        "نص {0,-6} و {{ثابت}} <#ff0000>أحمر</color>",
    ],
)
def test_shaping_preserves_integrity_tokens(text: str) -> None:
    ok, errors = UnitySyntaxGuard.validate_integrity(text, shape_rtl(text))
    assert ok, errors


def test_contains_rtl() -> None:
    assert contains_rtl("abc مرحبا") is True
    assert contains_rtl("שלום") is True
    assert contains_rtl("Hello") is False


def test_prepare_for_display_respects_language_and_toggle() -> None:
    translations = {"Hello": "مرحبا"}
    assert prepare_for_display(translations, "ar") == shape_translations(translations)
    assert prepare_for_display(translations, "ar", rtl_shaping=False) == translations
    assert prepare_for_display({"Hello": "Merhaba"}, "tr") == {"Hello": "Merhaba"}
