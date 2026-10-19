# -*- coding: utf-8 -*-
"""Line codec matching XUnity.AutoTranslator's ``TextHelper`` dictionary format exactly.

Mirrors ``TextHelper.ReadTranslationLineAndDecode`` (XUnity 5.x source):

* ``\\=``, ``\\\\``, ``\\n``, ``\\r`` and ``\\uXXXX`` are escapes; any other ``\\x``
  stays as the two characters ``\\x``.
* An unescaped ``=`` separates key and value; a second one makes the line invalid.
* An unescaped ``//`` starts an inline comment that ends the line, so a text
  containing ``//`` (``https://...``) must not be written raw: it would be cut off
  or dropped. XUnity's own ``\\/\\/`` escape decodes back to ``\\/\\/`` (the
  backslashes survive), so the second slash is written as ``\\u002F`` instead.
* The literal sequence ``%3D`` is decoded as ``=`` (legacy encoding); a real
  ``%3D`` in game text is therefore written as ``\\u0025`` + ``3D``.
* A line starting with ``#set``/``#unset``/``#enable`` is a directive, so a key
  starting with ``#`` is written as ``\\u0023`` + rest.
* Keys starting with ``r:``/``sr:`` are regex entries and cannot be literal keys.
"""

from __future__ import annotations

_SIMPLE_ESCAPES: dict[str, str] = {"=": "=", "\\": "\\", "n": "\n", "r": "\r"}
_DIRECTIVE_PREFIXES: tuple[str, ...] = ("#set ", "#unset ", "#enable ")
REGEX_KEY_PREFIXES: tuple[str, ...] = ("r:", "sr:")


def encode(text: str) -> str:
    """Encode raw text into one XUnity dictionary token (key or value)."""
    out: list[str] = []
    for index, char in enumerate(text):
        if char == "\\":
            out.append("\\\\")
        elif char == "=":
            out.append("\\=")
        elif char == "\n":
            out.append("\\n")
        elif char == "\r":
            out.append("\\r")
        elif char == "/" and index > 0 and text[index - 1] == "/":
            out.append("\\u002F")  # never emit an unescaped "//" (inline comment)
        elif char == "%" and text[index + 1 : index + 3] == "3D":
            out.append("\\u0025")  # "%3D" would be decoded as "="
        else:
            out.append(char)
    return "".join(out)


def _encode_key(key: str) -> str:
    encoded = encode(key)
    return "\\u0023" + encoded[1:] if encoded.startswith("#") else encoded


def is_literal_key(key: str) -> bool:
    """False for keys XUnity would treat as regex entries (``r:``/``sr:``) or skip (blank)."""
    return bool(key) and not key.startswith(REGEX_KEY_PREFIXES)


def encode_line(key: str, value: str) -> str:
    """Build an encoded ``key=value`` dictionary line."""
    return f"{_encode_key(key)}={encode(value)}"


def _unicode_escape(line: str, index: int) -> str | None:
    """Character of a ``\\uXXXX`` escape whose 'u' is at index, None when malformed."""
    digits = line[index + 1 : index + 5]
    if len(digits) == 4 and all(c in "0123456789abcdefABCDEF" for c in digits):
        return chr(int(digits, 16))
    return None


def decode_line(line: str) -> tuple[str, str] | None:
    """Split and decode one dictionary line into (key, value) like XUnity does.

    Returns None for lines XUnity ignores: no separator, two separators,
    a malformed ``\\u`` escape, or an inline comment before the separator.
    """
    parts: list[str] = []
    buffer: list[str] = []
    index = 0
    while index < len(line):
        char = line[index]
        if char == "\\":
            if index + 1 == len(line):
                break  # XUnity drops a dangling escape character
            nxt = line[index + 1]
            if nxt == "u":
                decoded = _unicode_escape(line, index + 1)
                if decoded is None:
                    return None
                buffer.append(decoded)
                index += 6
                continue
            buffer.append(_SIMPLE_ESCAPES.get(nxt, "\\" + nxt))
            index += 2
            continue
        if char == "=":
            if parts:
                return None
            parts.append("".join(buffer))
            buffer = []
        elif char == "%" and line[index + 1 : index + 3] == "3D":
            buffer.append("=")
            index += 2
        elif char == "/" and line[index + 1 : index + 2] == "/":
            break  # inline comment ends the line
        else:
            buffer.append(char)
        index += 1
    if len(parts) != 1:
        return None
    return parts[0], "".join(buffer)


def is_comment(line: str) -> bool:
    """True for lines that are never translations: blank, ``//`` comments, directives."""
    stripped = line.strip()
    return not stripped or stripped.startswith("//") or stripped.startswith(_DIRECTIVE_PREFIXES)
