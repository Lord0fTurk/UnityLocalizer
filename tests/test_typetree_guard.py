# -*- coding: utf-8 -*-
"""The TypeTree array guard rejects counts that cannot fit in the object."""

from __future__ import annotations

import pytest
from UnityPy.helpers import TypeTreeHelper
from UnityPy.helpers.TypeTreeNode import TypeTreeNode
from UnityPy.streams import EndianBinaryReader

from src.core.harvesters.typetree_guard import install_array_guard


def _int_list_node() -> TypeTreeNode:
    node = TypeTreeNode(0, "vector", "list", 0, 0)
    array = TypeTreeNode(1, "Array", "Array", 0, 0)
    array.m_Children = [TypeTreeNode(2, "int", "size", 4, 0), TypeTreeNode(2, "int", "data", 4, 0)]
    node.m_Children = [array]
    return node


def test_garbage_array_length_is_refused_and_real_one_is_read() -> None:
    install_array_guard()
    install_array_guard()  # idempotent
    config = TypeTreeHelper.TypeTreeConfig(True, None, False)
    bad = EndianBinaryReader(b"\xff\xff\xff\x7f" + b"\x00" * 16, "<")
    with pytest.raises(ValueError, match="exceeds"):
        TypeTreeHelper.read_value(_int_list_node(), bad, config)
    good = EndianBinaryReader(b"\x02\x00\x00\x00" + b"\x07\x00\x00\x00\x09\x00\x00\x00", "<")
    assert TypeTreeHelper.read_value(_int_list_node(), good, config) == [7, 9]


class _FakeMonoBehaviour:
    """Just enough of a UnityPy object: ``peek_name`` fails as it does when a TypeTree generator is attached."""

    def __init__(self, name: bytes, header: int = 28) -> None:
        import struct

        self._raw = b"\x00" * header + struct.pack("<i", len(name)) + name + b"\x00" * 4
        self.path_id = 1
        self.type = type("T", (), {"name": "MonoBehaviour"})()

    def peek_name(self) -> str:
        raise AssertionError("failed to dump nodes raw")

    def get_raw_data(self) -> bytes:
        return self._raw


def test_the_object_name_is_read_from_the_bytes_when_peeking_fails() -> None:
    from src.core.harvesters.asset_harvester import _object_name

    assert _object_name(_FakeMonoBehaviour(b"SpellData_Fireball")) == "SpellData_Fireball"
    assert _object_name(_FakeMonoBehaviour(b"")) == ""
    broken = _FakeMonoBehaviour(b"x", header=4)
    assert _object_name(broken) == ""
