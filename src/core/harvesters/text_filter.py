# -*- coding: utf-8 -*-
"""Shared rules deciding whether a harvested string is player-visible text.

Every string that passes is sent to a (possibly paid) translation engine, so the
harvesters share one definition of "technical" instead of three diverging ones:

* ``looks_technical``: paths, file names, namespaces, GUIDs, colors, symbol runs.
* ``is_code_literal_text``: C# string literals (Mono ``#US`` stream and IL2CPP
  metadata are the same kind of data), which are mostly identifiers, keys and
  format templates, so a natural-language heuristic is applied on top.

Serialized asset text (``AssetHarvester``) is mostly display text already and only
adds its own Unity-specific rules on top of ``looks_technical``.
"""

from __future__ import annotations

import re

from src.core.syntax_guard import UNITY_PROTECT_RE

TECHNICAL_PREFIXES: tuple[str, ...] = (
    "Assets/", "Resources/", "Packages/", "Plugins/", "Data/", "Shaders/", "Shader/",
    "Hidden/", "Legacy Shaders/", "UnityEngine.", "UnityEditor.", "TMPro.", "System.",
    "Mono.", "mscorlib", "Assembly-", "IEnumerator", "http://", "https://",
)
FILE_EXTENSIONS: tuple[str, ...] = (
    ".dll", ".exe", ".dat", ".asset", ".prefab", ".mat", ".shader", ".png", ".jpg", ".jpeg",
    ".tga", ".psd", ".anim", ".controller", ".ttf", ".otf", ".unity", ".unity3d", ".ress",
    ".resource", ".wav", ".mp3", ".ogg", ".bytes", ".json", ".xml", ".csv", ".txt",
)
_GUID_OR_HASH_RE = re.compile(r"^[0-9a-fA-F]{32}$|^[0-9a-fA-F-]{36}$|^[0-9a-fA-F]{40,64}$")
_COLOR_OR_SYMBOLS_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$|^[_{}0-9\-./\\:;]+$")
# One token that reads like code: dotted.path, snake_case, camelCase or CONSTANT_CASE.
_IDENTIFIER_RE = re.compile(r"^\S*(?:\w\.\w|_|[a-z][A-Z])\S*$")
_NON_LATIN_SCRIPT_RE = re.compile(
    r"[Ͱ-ϿЀ-ӿ֐-׿؀-ۿ฀-๿"
    r"぀-ヿ㐀-䶿一-鿿가-힯]"
)
_SENTENCE_MARKS: tuple[str, ...] = (" ", ".", ",", "!", "?", ":", "'", '"', "\n")


def looks_technical(text: str) -> bool:
    """True for paths, file names, namespaces, hashes, colors and symbol-only strings."""
    stripped = text.strip()
    if stripped.startswith(TECHNICAL_PREFIXES):
        return True
    if stripped.lower().endswith(FILE_EXTENSIONS):
        return True
    return bool(_GUID_OR_HASH_RE.match(stripped) or _COLOR_OR_SYMBOLS_RE.match(stripped))


def _visible_part(text: str) -> str | None:
    """Strip RichText/format tokens; None when a leading '<' is a compiler symbol, not markup.

    ``<color=red>Game Over</color>`` is display text, while ``<Module>`` or
    ``<Name>k__BackingField`` are compiler-generated identifiers.
    """
    plain = UNITY_PROTECT_RE.sub(" ", text).strip()
    if text.startswith("<") and plain == text:
        return None
    if "__" in plain and " " not in plain:
        return None
    return plain


def is_code_literal_text(text: str, max_length: int = 1500) -> bool:
    """True when a C# string literal is likely shown to the player."""
    stripped = text.strip()
    if len(stripped) < 2 or len(stripped) > max_length:
        return False
    plain = _visible_part(stripped)
    if not plain or plain.startswith(("<", "m_", "_")) or looks_technical(plain):
        return False
    if plain.isdigit() or not any(c.isalpha() for c in plain):
        return False
    if _NON_LATIN_SCRIPT_RE.search(plain):
        return True
    if _IDENTIFIER_RE.match(plain):
        return False
    if any(mark in plain for mark in _SENTENCE_MARKS):
        return True
    # Single short words are kept only when capitalized like UI labels ("Play", "Quit").
    return 3 <= len(plain) <= 30 and plain[0].isupper()
