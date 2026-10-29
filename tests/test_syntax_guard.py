# -*- coding: utf-8 -*-
"""Unit tests for UnitySyntaxGuard."""

from src.core.syntax_guard import UnitySyntaxGuard


def test_protect_and_restore_richtext():
    text = "Hello <color=#ff0000><b>Hero</b></color>! Your score is {0}."
    protected, tags = UnitySyntaxGuard.protect(text, mode="token")

    assert "⟦ULPH_" in protected
    assert "<color=" not in protected
    assert "{0}" not in protected
    assert len(tags) == 5  # <color>, <b>, </b>, </color>, {0} -> 5 total tags

    restored = UnitySyntaxGuard.restore(protected, tags, mode="token")
    assert restored == text


def test_xml_mode_for_llms():
    text = "<size=24>Title</size> - Item: {itemName}"
    protected, tags = UnitySyntaxGuard.protect(text, mode="xml")

    assert '<ph id="0"/>' in protected
    restored = UnitySyntaxGuard.restore(protected, tags, mode="xml")
    assert restored == text


def test_fuzzy_recovery_mangled_brackets():
    text = "Hp: {0} / {1}"
    protected, tags = UnitySyntaxGuard.protect(text, mode="token")
    # Simulate machine engine replacing ⟦ ⟧ with [ ]
    mangled = protected.replace("⟦", "[").replace("⟧", "]")

    restored = UnitySyntaxGuard.restore(mangled, tags, mode="token")
    assert restored == text


def test_validate_integrity():
    orig = "Player: {0}, Gold: {1}"
    valid_trans = "Oyuncu: {0}, Altın: {1}"
    broken_trans = "Oyuncu: {0}, Altın: 100"

    ok, errors = UnitySyntaxGuard.validate_integrity(orig, valid_trans)
    assert ok is True
    assert len(errors) == 0

    broken_ok, broken_errors = UnitySyntaxGuard.validate_integrity(orig, broken_trans)
    assert broken_ok is False
    assert len(broken_errors) > 0


import pytest


@pytest.mark.parametrize(
    "text, token",
    [
        ("Score: {0,-6}", "{0,-6}"),
        ("Total: {2,5:0.00}", "{2,5:0.00}"),
        ("Hi {player.name}!", "{player.name}"),
        ("Gold: {$gold}", "{$gold}"),
        ("Hello {[PLAYER]}", "{[PLAYER]}"),
        ("Use {{braces}} here", "{{"),
        ("<#ff0000>Danger</color>", "<#ff0000>"),
        ("Line<br>Two", "<br>"),
        ("Line<br/>Two", "<br/>"),
        ("<nobr>No-break</nobr>", "<nobr>"),
        ("H<sub>2</sub>O", "<sub>"),
        ("<pos=50%>Right", "<pos=50%>"),
        ("[ff0000]Red[-] text", "[ff0000]"),
        ("[b]Bold[/b] text", "[/b]"),
    ],
)
def test_extended_tokens_are_protected(text: str, token: str) -> None:
    protected, tags = UnitySyntaxGuard.protect(text)
    assert token in tags
    assert token not in protected
    assert UnitySyntaxGuard.restore(protected, tags) == text


@pytest.mark.parametrize(
    "original, broken",
    [
        ("Score: {0,-6}", "Skor:"),
        ("Hi {player.name}!", "Merhaba!"),
        ("Line<br>Two", "Satır İki"),
        ("[ff0000]Red[-]", "Kırmızı"),
        ("<#ff0000>Danger</color>", "Tehlike</color>"),
    ],
)
def test_dropped_extended_tokens_fail_integrity(original: str, broken: str) -> None:
    ok, errors = UnitySyntaxGuard.validate_integrity(original, broken)
    assert ok is False
    assert errors


def test_escaped_braces_are_not_split() -> None:
    protected, tags = UnitySyntaxGuard.protect("{{literal}} {0}")
    assert tags == ["{{", "}}", "{0}"]
    assert "literal" in protected


def test_plain_brackets_and_text_untouched() -> None:
    text = "Press [Space] to jump (hold for 2s)"
    protected, tags = UnitySyntaxGuard.protect(text)
    assert tags == []
    assert protected == text


@pytest.mark.parametrize(
    "text, token",
    [
        ("<margin-left=1em>Indented</margin-left>", "<margin-left=1em>"),
        ("<margin-right=10%>Text", "<margin-right=10%>"),
        ("%1$s has %2$d gold", "%1$s"),
        ("%2$d gold left", "%2$d"),
        ("{count:plural:one item|{} items}", "{count:plural:one item|{} items}"),
        ("{0:plural:{} coin|{} coins}", "{0:plural:{} coin|{} coins}"),
        ("Total {0:{1}}", "{0:{1}}"),
    ],
)
def test_nested_and_positional_tokens_are_protected_whole(text: str, token: str) -> None:
    protected, tags = UnitySyntaxGuard.protect(text)
    assert token in tags
    assert token not in protected
    assert UnitySyntaxGuard.restore(protected, tags) == text


def test_dropped_plural_structure_fails_integrity() -> None:
    ok, _ = UnitySyntaxGuard.validate_integrity(
        "You have {0} {0:plural:coin|coins}", "Elinde {0} jeton var"
    )
    assert ok is False


@pytest.fixture
def reset_protected_terms():
    from src.core.syntax_guard import set_protected_terms

    yield set_protected_terms
    set_protected_terms([])


@pytest.mark.parametrize(
    "text, term",
    [
        ("アルスは勇者だ", "アルス"),
        ("勇者アルス", "アルス"),
        ("艾尔来了", "艾尔"),
        ("Aliceは勇者だ", "Alice"),
        ("Alice's sword", "Alice"),
        ("Alice,Bob", "Alice"),
    ],
)
def test_protected_terms_match_inside_unspaced_scripts(reset_protected_terms, text: str, term: str) -> None:
    reset_protected_terms([term])
    protected, tags = UnitySyntaxGuard.protect(text)
    assert tags == [term]
    assert UnitySyntaxGuard.restore(protected, tags) == text


@pytest.mark.parametrize("text", ["Malice in wonderland", "Alicent waits", "Alice_2 is here"])
def test_latin_terms_still_need_word_boundaries(reset_protected_terms, text: str) -> None:
    reset_protected_terms(["Alice"])
    assert UnitySyntaxGuard.protect(text)[1] == []


@pytest.mark.parametrize(
    "mangled",
    [
        "［ULPH_0］嗨［ULPH_1］ ［ULPH_2］",
        "【ULPH_0】嗨【ULPH_1】 【ULPH_2】",
        "«ULPH_0»Hi«ULPH_1» «ULPH_2»",
        "ULPH_0 Hi ULPH_1 ULPH_2",
        "⟦ULPH 0⟧Hi⟦ULPH 1⟧ ⟦ULPH 2⟧",
    ],
)
def test_fuzzy_recovery_other_bracket_styles(mangled: str) -> None:
    original = "<b>Hi</b> {0}"
    _, tags = UnitySyntaxGuard.protect(original)
    restored = UnitySyntaxGuard.restore(mangled, tags)
    assert "ULPH" not in restored
    assert [t for t in tags if t in restored] == tags


def test_fuzzy_recovery_never_eats_a_lone_bracket() -> None:
    _, tags = UnitySyntaxGuard.protect("Hi {0}")
    restored = UnitySyntaxGuard.restore("「Merhaba」 ULPH_0", tags)
    assert restored == "「Merhaba」 {0}"
    assert UnitySyntaxGuard.restore("「ULPH_0 selam", tags) == "「{0} selam"


def test_fuzzy_recovery_ignores_out_of_range_index() -> None:
    _, tags = UnitySyntaxGuard.protect("Hi {0}")
    assert UnitySyntaxGuard.restore("ULPH_7 selam", tags) == "ULPH_7 selam"
