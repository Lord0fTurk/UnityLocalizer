# -*- coding: utf-8 -*-
"""Inkle Ink compiled story (``.ink.json``) text extraction and patching.

Compiled Ink stores display text as ``"^text"`` list items; every other string
is a runtime command (``"ev"``, ``"out"``, ``"/str"``) or a divert/variable
path stored as a dict value. Tags are wrapped in ``"#" ... "/#"`` markers (ink
v21+) and must not be translated because game code matches on them.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

_TEXT_PREFIX = "^"
_TAG_START = "#"
_TAG_END = "/#"
_EVAL_START = "ev"
_EVAL_END = "/ev"


def is_ink_document(data: Any) -> bool:
    """True when parsed JSON is a compiled Ink story."""
    return isinstance(data, dict) and "inkVersion" in data and "root" in data


def _map_segment(segment: str, fn: Callable[[str], str]) -> str:
    """Apply fn to the trimmed core of a text segment, keeping its glue whitespace."""
    core = segment.strip()
    if len(core) < 2:
        return segment
    start = segment.index(core)
    return f"{segment[:start]}{fn(core)}{segment[start + len(core):]}"


def _is_logic_eval_block(node: list[Any], start_idx: int) -> bool:
    """True when the 'ev'...'/'ev' block at start_idx performs logic/variable assignment rather than choice output."""
    logic_ops = {"==", "!=", "<", ">", "<=", ">=", "&&", "||", "!", "?", "!", "+", "-", "*", "/", "%", "MIN", "MAX"}
    for idx in range(start_idx + 1, len(node)):
        item = node[idx]
        if item == _EVAL_END:
            break
        if isinstance(item, str) and item in logic_ops:
            return True
        if isinstance(item, dict) and any(k in item for k in ("VAR=", "temp=", "VAR?", "CNT?", "f()")):
            return True
    return False


def _clone_ink_shell(node: Any, fn: Callable[[str], str]) -> tuple[Any, list[tuple[Any, Any, Any]]]:
    """Clone a single list/dict level of an Ink AST and return deferred child nodes."""
    if isinstance(node, list):
        out: list[Any] = []
        children: list[tuple[Any, Any, Any]] = []
        in_tag = False
        skip_eval = False
        for idx, item in enumerate(node):
            if item == _TAG_START:
                in_tag = True
                out.append(item)
            elif item == _TAG_END:
                in_tag = False
                out.append(item)
            elif item == _EVAL_START:
                skip_eval = _is_logic_eval_block(node, idx)
                out.append(item)
            elif item == _EVAL_END:
                skip_eval = False
                out.append(item)
            elif isinstance(item, str) and item.startswith(_TEXT_PREFIX) and not in_tag and not skip_eval:
                out.append(_TEXT_PREFIX + _map_segment(item[1:], fn))
            elif isinstance(item, (list, dict)):
                children.append((out, len(out), item))
                out.append(None)
            else:
                out.append(item)
        return out, children
    out_dict: dict[Any, Any] = {}
    children = []
    for key, value in node.items():
        if isinstance(value, (list, dict)):
            out_dict[key] = None
            children.append((out_dict, key, value))
        else:
            out_dict[key] = value
    return out_dict, children


def _map_content(root_node: Any, fn: Callable[[str], str]) -> Any:
    """Iteratively rebuild an Ink node in pre-order with display strings passed through fn."""
    if not isinstance(root_node, (list, dict)):
        return root_node
    root_copy, root_children = _clone_ink_shell(root_node, fn)
    stack: list[tuple[Any, Any, Any]] = list(reversed(root_children))
    while stack:
        parent, key_or_idx, child = stack.pop()
        child_copy, grandchildren = _clone_ink_shell(child, fn)
        parent[key_or_idx] = child_copy
        for gc in reversed(grandchildren):
            stack.append(gc)
    return root_copy


def ink_strings(data: dict[str, Any]) -> list[str]:
    """Collect display text from a compiled Ink story."""
    found: list[str] = []

    def _collect(text: str) -> str:
        found.append(text)
        return text

    _map_content(data["root"], _collect)
    return found


def translate_ink(data: dict[str, Any], translations: dict[str, str]) -> dict[str, Any]:
    """Return a copy of the story with display text replaced from translations."""
    patched = dict(data)
    patched["root"] = _map_content(data["root"], lambda text: translations.get(text, text))
    return patched
