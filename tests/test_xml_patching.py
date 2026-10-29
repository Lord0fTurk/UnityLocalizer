# -*- coding: utf-8 -*-
"""XML patching changes only the translated words: comments, CDATA and namespaces survive."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from lxml import etree

from src.core.parsers.streaming_assets import StreamingAssetsParser
from src.core.parsers.text_formats import sniff_and_extract, strings_from_xml_text, translate_xml_text
from src.core.parsers.xml_text import parse_xml, translate_xml, xml_strings

SOURCE = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    "<!-- menu texts, do not remove -->\n"
    '<root xmlns="urn:game" xmlns:x="urn:extra" version="2">\n'
    "  <!-- Quit stays in this comment -->\n"
    '  <item id="1" x:kind="menu"><![CDATA[Start <b>game</b>]]></item>\n'
    '  <item id="2">Quit</item>\n'
    "  <?note keep me?>\n"
    '  <item id="3">Options</item>\n'
    "</root>\n"
)


def _patched(translations: dict[str, str], source: str = SOURCE) -> str:
    result = translate_xml_text(source, translations)
    assert result is not None
    return result


def _shape(xml: str) -> list[tuple[str, str | None, str | None]]:
    root = etree.fromstring(xml.encode("utf-8"), etree.XMLParser(strip_cdata=False))
    return [(n.tag if isinstance(n.tag, str) else type(n).__name__, n.text, n.tail) for n in root.iter()]


def test_comments_cdata_and_namespaces_survive_a_patch() -> None:
    out = _patched({"Quit": "Çık"})
    assert "<!-- menu texts, do not remove -->" in out
    assert "<!-- Quit stays in this comment -->" in out  # comment text is never translated
    assert "<![CDATA[Start <b>game</b>]]>" in out
    assert 'xmlns="urn:game"' in out and 'xmlns:x="urn:extra"' in out
    assert '<item id="1" x:kind="menu">' in out  # attribute order and values unchanged
    assert "<?note keep me?>" in out
    assert '<item id="2">Çık</item>' in out


def test_a_patch_with_nothing_to_translate_keeps_every_node() -> None:
    assert _shape(_patched({})) == _shape(SOURCE)


def test_a_translated_cdata_leaf_stays_a_cdata_section() -> None:
    out = _patched({"Start <b>game</b>": "Oyunu <b>başlat</b>"})
    assert "<![CDATA[Oyunu <b>başlat</b>]]>" in out
    assert "&lt;b&gt;" not in out


def test_a_translation_with_a_cdata_terminator_still_reads_back_as_the_same_text() -> None:
    # lxml splits the section (older versions refuse it and the patch falls back to escaped text)
    out = _patched({"Start <b>game</b>": "a ]]> b"})
    root = parse_xml(out)
    assert root is not None and root[1].text == "a ]]> b"


def test_text_after_a_comment_is_content_and_is_translated() -> None:
    source = "<root><!-- c -->Hello there<item>Quit</item></root>"
    assert _patched({"Hello there": "Merhaba"}, source) == "<root><!-- c -->Merhaba<item>Quit</item></root>"
    assert xml_strings(source) == ["Hello there", "Quit"]


def test_a_cdata_leaf_is_found_by_the_harvest() -> None:
    assert strings_from_xml_text(SOURCE) == ["Start <b>game</b>", "Quit", "Options"]


def test_harvest_order_single_cjk_and_short_text_rules_are_unchanged() -> None:
    xml = "<r><a>是</a><b>X</b><c>Play game</c><d> </d>tail text</r>"
    assert strings_from_xml_text(xml) == ["是", "Play game", "tail text"]


def test_the_declaration_is_kept_as_written_and_the_body_follows() -> None:
    out = _patched({"Quit": "Çık"}, "<?xml version='1.0' encoding='gb2312'?><root><i>Quit</i></root>")
    assert out.startswith("<?xml version='1.0' encoding='gb2312'?>\n<root>")
    assert "<i>Çık</i>" in out


def test_a_document_without_a_declaration_gets_none() -> None:
    assert _patched({"Quit": "Çık"}, "<root><i>Quit</i></root>") == "<root><i>Çık</i></root>"


def test_leading_whitespace_and_a_stray_bom_are_tolerated() -> None:
    assert xml_strings("﻿ \n<?xml version='1.0'?>\n<r><i>Play game</i></r>") == ["Play game"]


def test_an_external_doctype_is_kept() -> None:
    source = '<?xml version="1.0"?>\n<!DOCTYPE root SYSTEM "game.dtd">\n<root><i>Quit</i></root>'
    assert '<!DOCTYPE root SYSTEM "game.dtd">' in _patched({"Quit": "Çık"}, source)


@pytest.mark.parametrize(
    "source",
    [
        '<?xml version="1.0"?>\n<!DOCTYPE a [<!ENTITY x "boom">]><a>&x;</a>',
        '<!DOCTYPE a [<!entity x "boom">]><a>text here</a>',
    ],
)
def test_documents_declaring_entities_are_refused(source: str) -> None:
    assert translate_xml(source, {"text here": "x"}) is None
    assert xml_strings(source) == []


def test_invalid_xml_is_refused_without_raising(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        assert translate_xml("<root><unclosed></root>", {}) is None
        assert xml_strings("not xml at all") == []
    assert "XML parse failed" in caplog.text


def test_an_encoding_declaration_in_text_input_is_not_a_problem() -> None:
    # lxml rejects str input that carries one; the text is parsed as UTF-8 bytes instead
    assert xml_strings('<?xml version="1.0" encoding="shift_jis"?><r><i>ゲームを始める</i></r>') == ["ゲームを始める"]


def test_xml_found_while_sniffing_an_untyped_file_uses_the_same_reader() -> None:
    assert sniff_and_extract("<r><!-- c --><i>Play game</i></r>") == ["Play game"]


def test_the_streaming_assets_parser_keeps_comments_through_a_patch(tmp_path: Path) -> None:
    path = tmp_path / "strings.xml"
    path.write_bytes(SOURCE.encode("utf-8"))
    parser = StreamingAssetsParser()
    assert parser.apply_translations(path, {"Quit": "Çık", "Start <b>game</b>": "Oyunu başlat"})
    out = path.read_text(encoding="utf-8")
    assert "<!-- menu texts, do not remove -->" in out and "<![CDATA[Oyunu başlat]]>" in out
    assert path.with_suffix(".xml.bak").read_bytes() == SOURCE.encode("utf-8")
