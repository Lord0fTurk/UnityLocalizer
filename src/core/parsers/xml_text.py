# -*- coding: utf-8 -*-
"""XML text extraction and patching that leaves the rest of the document alone.

The standard library's ElementTree drops comments, turns ``<![CDATA[...]]>`` into escaped
text and forgets unused namespace declarations, so a patched file differed from the game's
original in more than the translated words. ``lxml`` keeps all of that; only the text that
was translated changes (a translated CDATA leaf stays CDATA).

Documents are parsed from UTF-8 bytes with the declared encoding overridden: the text was
already decoded by ``text_encoding``, and ``lxml`` refuses ``str`` input that carries an
encoding declaration. A document with an entity declaration is refused outright.
"""

from __future__ import annotations

import logging
from typing import Any

from lxml import etree

from src.core.cjk import is_single_cjk

logger = logging.getLogger(__name__)

_CDATA_OPEN = b"<![CDATA["
_LEADING_JUNK = "﻿ \t\r\n"


def parse_xml(text: str) -> Any | None:
    """Root element of an XML document held as text; None when invalid or it declares entities."""
    if "<!ENTITY" in text.upper():
        return None
    parser = etree.XMLParser(
        strip_cdata=False, resolve_entities=False, load_dtd=False, no_network=True,
        huge_tree=False, encoding="utf-8",
    )
    try:
        return etree.fromstring(text.lstrip(_LEADING_JUNK).encode("utf-8"), parser)
    except etree.XMLSyntaxError as exc:
        logger.debug("XML parse failed: %s", exc)
        return None


def xml_strings(text: str) -> list[str]:
    """Text and tail nodes of an XML document, in document order (comments are not text)."""
    root = parse_xml(text)
    if root is None:
        return []
    return [chunk.strip() for chunk in root.itertext() if len(chunk.strip()) > 1 or is_single_cjk(chunk)]


def _swap(raw: str | None, translations: dict[str, str]) -> str | None:
    """``raw`` with its stripped core replaced by the translation, keeping surrounding whitespace."""
    if not raw:
        return raw
    core = raw.strip()
    if core not in translations:
        return raw
    start = raw.index(core)
    return f"{raw[:start]}{translations[core]}{raw[start + len(core):]}"


def _is_cdata_leaf(element: Any) -> bool:
    """True for an element without children whose text was written as a CDATA section."""
    return len(element) == 0 and _CDATA_OPEN in etree.tostring(element, with_tail=False)


def _swap_element_text(element: Any, translations: dict[str, str]) -> None:
    swapped = _swap(element.text, translations)
    if swapped == element.text:
        return
    if _is_cdata_leaf(element):
        try:
            element.text = etree.CDATA(swapped)
            return
        except ValueError:
            pass  # older lxml refuses a "]]>" inside a CDATA section; newer ones split it themselves
    element.text = swapped


def translate_xml(text: str, translations: dict[str, str]) -> str | None:
    """XML content with element text and tail nodes translated; None if the XML is invalid.

    Comments and processing instructions keep their own text, but the text that follows
    them is ordinary content and is translated.
    """
    root = parse_xml(text)
    if root is None:
        return None
    for node in root.iter():
        if isinstance(node.tag, str):
            _swap_element_text(node, translations)
        node.tail = _swap(node.tail, translations)
    body = etree.tostring(root.getroottree(), encoding="unicode")
    stripped = text.lstrip(_LEADING_JUNK)
    if stripped.startswith("<?xml"):
        decl_end = stripped.find("?>")
        if decl_end != -1:
            return stripped[: decl_end + 2] + "\n" + body
    return body
