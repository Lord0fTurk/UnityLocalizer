# -*- coding: utf-8 -*-
"""Only the files that can hold text are unpacked from a bundle; the big streams stay packed."""

from __future__ import annotations

import random
import tracemalloc
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import UnityPy
from bundle_factory import NODE_SERIALIZED, build_sparse, build_unityfs, unitypy_files

from src.core.harvesters.asset_harvester import AssetHarvester
from src.core.harvesters.bundle_header import NodeInfo, read_layout
from src.core.harvesters.bundle_unpack import is_wanted, peak_unpack_bytes, unpack_nodes
from src.core.harvesters.harvest_stats import HarvestStats

MIB = 2**20
_RNG = random.Random(7)
SERIALIZED_A = _RNG.randbytes(150_000)
SERIALIZED_B = _RNG.randbytes(90_000)
STREAM = (b"texture " * 150_000)[:900_000]
NODES = [("CAB-a", SERIALIZED_A, NODE_SERIALIZED), ("CAB-a.resS", STREAM, 0), ("CAB-b", SERIALIZED_B, NODE_SERIALIZED)]

VARIANTS = [
    {}, {"version": 6, "engine": "2018.4.30f1"}, {"version": 6, "engine": "2019.4.20f1"}, {"at_end": True},
    {"version": 8, "engine": "6000.0.1f1"}, {"pad_blocks": True}, {"pad_blocks": True, "at_end": True},
    {"compression": "none"}, {"chunk": 4096}, {"chunk": 10 * MIB},
]
VARIANT_IDS = ["v7", "v6-old-engine", "v6-2019.4-aligned", "blocks-info-at-end", "v8-unity6", "padding-at-start",
               "padding-and-at-end", "no-compression", "small-blocks", "one-block"]


def _write(tmp_path: Path, blob: bytes, name: str = "x.bundle") -> Path:
    path = tmp_path / name
    path.write_bytes(blob)
    return path


def _unpacked(path: Path, select: Any = is_wanted) -> dict[str, bytes]:
    layout = read_layout(path)
    assert layout is not None
    return {node.path: data for node, data in unpack_nodes(path, layout, select)}


# --- layout ------------------------------------------------------------------------------


@pytest.mark.parametrize("kwargs", VARIANTS, ids=VARIANT_IDS)
def test_the_layout_lists_the_blocks_and_files(tmp_path: Path, kwargs: dict[str, Any]) -> None:
    layout = read_layout(_write(tmp_path, build_unityfs(nodes=NODES, **kwargs)))
    assert layout is not None
    assert [(n.path, n.offset, n.size, n.flags) for n in layout.nodes] == [
        ("CAB-a", 0, len(SERIALIZED_A), 4),
        ("CAB-a.resS", len(SERIALIZED_A), len(STREAM), 0),
        ("CAB-b", len(SERIALIZED_A) + len(STREAM), len(SERIALIZED_B), 4),
    ]
    assert layout.unpacked_size == len(SERIALIZED_A) + len(STREAM) + len(SERIALIZED_B)


@pytest.mark.parametrize("kwargs", VARIANTS, ids=VARIANT_IDS)
def test_only_the_wanted_files_are_unpacked_and_byte_exact(tmp_path: Path, kwargs: dict[str, Any]) -> None:
    path = _write(tmp_path, build_unityfs(nodes=NODES, **kwargs))
    assert _unpacked(path) == {"CAB-a": SERIALIZED_A, "CAB-b": SERIALIZED_B}  # the .resS stream is left packed
    assert _unpacked(path, select=lambda node: True) == {n: d for n, d, _f in NODES}


@pytest.mark.parametrize("kwargs", VARIANTS, ids=VARIANT_IDS)
def test_the_unpacker_agrees_with_unitypy(tmp_path: Path, kwargs: dict[str, Any]) -> None:
    nodes = [(name, data, 0) for name, data, _flags in NODES]  # UnityPy would try to parse flagged random bytes
    blob = build_unityfs(nodes=nodes, **kwargs)
    everything = _unpacked(_write(tmp_path, blob), select=lambda node: True)
    assert everything == unitypy_files(blob) == {name: data for name, data, _f in nodes}


@pytest.mark.parametrize("packer", ["lzma", "lz4", "none"])
def test_bundles_written_by_unitypy_are_read(tmp_path: Path, packer: str) -> None:
    base = build_unityfs(nodes=[("CAB-a", SERIALIZED_A, 0), ("CAB-a.resS", STREAM, 0)])
    path = _write(tmp_path, UnityPy.load(base).file.save(packer=packer))
    assert _unpacked(path, select=lambda node: True) == {"CAB-a": SERIALIZED_A, "CAB-a.resS": STREAM}
    assert _unpacked(path) == {"CAB-a": SERIALIZED_A}


# --- which files are wanted ----------------------------------------------------------------


@pytest.mark.parametrize(
    "path, flags, size, wanted",
    [
        ("CAB-a", 4, 10, True), ("CAB-a.resS", 0, 10, False), ("CAB-a.RESS", 0, 10, False), ("CAB-a.resource", 0, 10, False),
        ("CAB-a.RESOURCE", 0, 10, False), ("CAB-a.resS", 4, 10, True),  # the flag outranks the name
        ("odd-name", 0, 10, True), ("nested.bundle", 0, 10, True),       # UnityPy decides by content
        ("CAB-a", 4, 0, False),
    ],
)
def test_which_files_are_unpacked(path: str, flags: int, size: int, wanted: bool) -> None:
    assert is_wanted(NodeInfo(0, size, flags, path)) is wanted


# --- memory --------------------------------------------------------------------------------


def _peak_of(path: Path) -> int:
    layout = read_layout(path)
    assert layout is not None
    tracemalloc.start()
    try:
        list(unpack_nodes(path, layout))
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def test_a_huge_stream_is_never_touched(tmp_path: Path) -> None:
    first = _RNG.randbytes(MIB)
    path = _write(tmp_path, build_sparse(first, 6 * 2**30))  # its data blocks are junk that cannot be unpacked
    layout = read_layout(path)
    assert layout is not None and layout.unpacked_size > 6 * 2**30
    assert peak_unpack_bytes(layout) == 2 * MIB  # the file and its one block, not the 6 GiB
    assert _unpacked(path) == {"CAB-sparse": first}
    assert _peak_of(path) < 6 * MIB


def test_an_lzma_bundle_is_decoded_in_pieces_and_abandoned_early(tmp_path: Path) -> None:
    base = build_unityfs(nodes=[("CAB-a", SERIALIZED_A, 0), ("CAB-a.resS", bytes(48 * MIB), 0)])
    path = _write(tmp_path, UnityPy.load(base).file.save(packer="lzma"))
    layout = read_layout(path)
    assert layout is not None and len(layout.blocks) == 1 and layout.blocks[0].flags & 0x3F == 1  # one LZMA stream
    assert _unpacked(path) == {"CAB-a": SERIALIZED_A}
    # The decoder's own dictionary (8 MiB here) is unavoidable; the 48 MiB that follow the file are never produced.
    assert _peak_of(path) < 16 * MIB


def test_a_file_behind_a_big_stream_in_an_lzma_block_costs_the_stream_too(tmp_path: Path) -> None:
    base = build_unityfs(nodes=[("CAB-a.resS", bytes(8 * MIB), 0), ("CAB-b", SERIALIZED_B, NODE_SERIALIZED)])
    path = _write(tmp_path, UnityPy.load(base).file.save(packer="lzma"))
    layout = read_layout(path)
    assert layout is not None
    assert peak_unpack_bytes(layout) == len(SERIALIZED_B) + 8 * MIB + len(SERIALIZED_B)  # file + prefix up to its end
    assert _unpacked(path) == {"CAB-b": SERIALIZED_B}


# --- bundles that cannot be read, damaged data ---------------------------------------------------


def test_encrypted_bundles_have_no_layout(tmp_path: Path) -> None:
    assert read_layout(_write(tmp_path, build_unityfs(nodes=NODES, extra_flags=0x400))) is None
    old = build_unityfs(nodes=NODES, version=6, engine="2019.4.20f1", extra_flags=0x200)  # 0x200 was encryption then
    assert read_layout(_write(tmp_path, old, "old.bundle")) is None


def test_the_same_bit_means_padding_on_a_newer_engine(tmp_path: Path) -> None:
    padded = build_unityfs(nodes=NODES, pad_blocks=True)
    assert _unpacked(_write(tmp_path, padded)) == {"CAB-a": SERIALIZED_A, "CAB-b": SERIALIZED_B}


@pytest.mark.parametrize("blob", [b"", b"UnityFS", b"UnityFS\x00" + b"\xff" * 60, b"UnityWeb\x00" + b"\x00" * 64, b"plain"])
def test_other_files_have_no_layout(tmp_path: Path, blob: bytes) -> None:
    assert read_layout(_write(tmp_path, blob)) is None


def test_truncated_data_raises_instead_of_returning_a_short_file(tmp_path: Path) -> None:
    blob = build_unityfs(nodes=NODES)
    path = _write(tmp_path, blob[: len(blob) // 3])
    layout = read_layout(path)
    assert layout is not None  # the tables are intact
    with pytest.raises(Exception):  # noqa: B017 - lz4 or our own size check, either is fine
        list(unpack_nodes(path, layout))


# --- the harvest uses it -----------------------------------------------------------------


class _Env:
    """What the harvest sees of a UnityPy environment: objects and a slot for the generator."""

    def __init__(self, source: Any) -> None:
        self.source = source
        self.objects = [SimpleNamespace(type=SimpleNamespace(name="TextAsset"))]
        self.typetree_generator: Any = None


@pytest.fixture
def loads(monkeypatch: pytest.MonkeyPatch) -> list[_Env]:
    made: list[_Env] = []

    def fake_load(source: Any) -> _Env:
        made.append(_Env(source))
        return made[-1]

    monkeypatch.setattr(UnityPy, "load", fake_load)
    monkeypatch.setattr(
        AssetHarvester, "extract_strings_from_object",
        classmethod(lambda cls, obj, source_lang="en", file_stat=None, stats=None: ["text"]),
    )
    return made


def test_a_readable_bundle_hands_unitypy_one_unpacked_file_at_a_time(tmp_path: Path, loads: list[_Env]) -> None:
    path = _write(tmp_path, build_unityfs(nodes=NODES))
    stats, generator = HarvestStats(), object()
    assert AssetHarvester.harvest_asset_file(path, "en", generator, stats) == ["text"]
    assert [env.source for env in loads] == [SERIALIZED_A, SERIALIZED_B]  # bytes of the files, never the path or the stream
    assert all(env.typetree_generator is generator for env in loads)
    assert [(f.name, f.strings, f.failed) for f in stats.files] == [("x.bundle", 1, False)]


def test_a_bundle_with_only_streams_has_nothing_to_unpack(tmp_path: Path, loads: list[_Env]) -> None:
    path = _write(tmp_path, build_unityfs(nodes=[("CAB-a.resS", STREAM, 0), ("CAB-a.resource", STREAM, 0)]))
    stats = HarvestStats()
    assert AssetHarvester.harvest_asset_file(path, "en", None, stats) == []
    assert loads == [] and not stats.files[0].failed


@pytest.mark.parametrize(
    "blob",
    [b"UnityFS\x00" + b"\xff" * 60, b"UnityWeb\x00" + b"\x00" * 64, b"\x00" * 300],
    ids=["unreadable-unityfs", "other-bundle-format", "plain-serialized-file"],
)
def test_anything_else_is_opened_the_usual_way(tmp_path: Path, loads: list[_Env], blob: bytes) -> None:
    path = _write(tmp_path, blob, "level0")
    assert AssetHarvester.harvest_asset_file(path) == ["text"]
    assert [env.source for env in loads] == [str(path)]


def test_damaged_bundle_data_marks_the_file_failed_without_raising(tmp_path: Path, loads: list[_Env]) -> None:
    blob = build_unityfs(nodes=NODES)
    path = _write(tmp_path, blob[: len(blob) // 3])
    stats = HarvestStats()
    AssetHarvester.harvest_asset_file(path, "en", None, stats)
    assert stats.files[0].failed is True


def test_lzma_stream_continues_instead_of_restarting(tmp_path: Path) -> None:
    import lzma
    import os
    import struct

    from src.core.harvesters.bundle_unpack import _LzmaStream

    data = os.urandom(300_000) + b"tail" * 1000
    packer = lzma.LZMACompressor(format=lzma.FORMAT_RAW, filters=[
        {"id": lzma.FILTER_LZMA1, "dict_size": 1 << 20, "lc": 3, "lp": 0, "pb": 2}])
    packed = struct.pack("<BI", 93, 1 << 20) + packer.compress(data) + packer.flush()
    path = tmp_path / "block.bin"
    path.write_bytes(b"\x00" * 7 + packed)
    with open(path, "rb") as f:
        stream = _LzmaStream(f, 7, len(packed))
        for end in (10, 150_000, 150_000, 100, len(data)):  # growing, repeated and shrinking requests
            assert bytes(stream.prefix(end)) == data[:end]
        assert bytes(stream.prefix(len(data) + 50)) == data  # the block ends first: no more than it holds
