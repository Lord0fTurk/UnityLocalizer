# -*- coding: utf-8 -*-
"""Refuses TypeTree arrays that cannot fit in the object being read.

UnityPy reads an array's length from the data and then builds that many elements. When a
generated TypeTree does not match the bytes (a script compiled differently from its assembly,
a mismatched metadata), the "length" is garbage: one 1 KB MonoBehaviour of How to Fish made the
reader allocate 8.3 GB and run for six seconds before failing. An array cannot hold more elements
than the object has bytes left, so a count beyond that is rejected up front and the harvester
falls back to the raw scan for that object, as for any other unreadable TypeTree.
"""

from __future__ import annotations

import logging
from typing import Any

from UnityPy.helpers import TypeTreeHelper

logger = logging.getLogger(__name__)

_ARRAY_TYPE = "Array"
_installed = False


def _guarded(original: Any) -> Any:
    def read_value(node: Any, reader: Any, config: Any) -> Any:
        children = node.m_Children
        if children and children[0].m_Type == _ARRAY_TYPE and node.m_Type not in TypeTreeHelper.FUNCTION_READ_MAP:
            position = reader.Position
            count = reader.read_int()
            reader.Position = position
            if count > reader.Length - position:
                raise ValueError(f"Array length {count} exceeds the data left in the object")
        return original(node, reader, config)

    return read_value


def install_array_guard() -> None:
    """Wrap UnityPy's TypeTree value reader once per process (recursive reads go through the wrapper)."""
    global _installed
    if _installed:
        return
    # UnityPy's native reader (UnityPyBoost) allocates the garbage count before Python can look at it,
    # so objects are read by the Python reader, where the guard sees every array.
    TypeTreeHelper.read_typetree_boost = None
    TypeTreeHelper.read_value = _guarded(TypeTreeHelper.read_value)
    _installed = True
    logger.debug("TypeTree array guard installed")
