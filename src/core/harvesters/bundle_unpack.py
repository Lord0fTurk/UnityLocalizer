# -*- coding: utf-8 -*-
"""Unpacks only the files of a UnityFS bundle that can hold text, leaving the big streams packed.

A bundle holds serialized files (objects: ``TextAsset``, ``MonoBehaviour``, ...) next to resource
streams (``.resS`` textures, meshes and ``.resource`` audio) that are far larger and that the harvest
never reads. UnityPy unpacks all of it, about twice the unpacked size in memory. Here only the blocks
that overlap a wanted file are unpacked, and an LZMA block (one long stream, so nothing before the
end of the file can be skipped) is decoded in pieces and abandoned as soon as the file is complete.

Which files are wanted: every one except resource streams. UnityPy tells a serialized file, a nested
bundle or a plain resource apart by its content, not by the node flags, so a file that is not clearly a
stream is handed over and UnityPy decides.
"""

from __future__ import annotations

import lzma
import struct
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import BinaryIO

from UnityPy.enums import CompressionFlags
from UnityPy.helpers import CompressionHelper

from src.core.harvesters.bundle_header import COMPRESSION_MASK, BlockInfo, BundleLayout, NodeInfo

NODE_FLAG_SERIALIZED = 0x4
RESOURCE_STREAM_SUFFIXES = (".ress", ".resource")
_LZMA_PIECE = 1 << 20  # compressed bytes read, and unpacked bytes produced, per step of an LZMA block


def is_wanted(node: NodeInfo) -> bool:
    """True for a file that may hold objects: flagged as serialized, or anything that is not a resource stream."""
    if not node.size:
        return False
    return bool(node.flags & NODE_FLAG_SERIALIZED) or not node.path.lower().endswith(RESOURCE_STREAM_SUFFIXES)


def _overlapping_blocks(layout: BundleLayout, node: NodeInfo) -> Iterator[tuple[int, BlockInfo, int, int, int]]:
    """(index, block, file offset of its data, first and one-past-last byte of the node inside it)."""
    unpacked_at, packed_at = 0, layout.data_start
    end = node.offset + node.size
    for index, block in enumerate(layout.blocks):
        if unpacked_at < end and unpacked_at + block.uncompressed > node.offset:
            lo = max(node.offset, unpacked_at) - unpacked_at
            hi = min(end, unpacked_at + block.uncompressed) - unpacked_at
            yield index, block, packed_at, lo, hi
        unpacked_at += block.uncompressed
        packed_at += block.compressed


def _is_lzma(block: BlockInfo) -> bool:
    return block.flags & COMPRESSION_MASK == CompressionFlags.LZMA


def node_unpack_cost(layout: BundleLayout, node: NodeInfo) -> int:
    """Bytes held at once while unpacking ``node``: the file itself plus the largest block (or LZMA prefix) in flight."""
    in_flight = max((hi if _is_lzma(block) else block.uncompressed
                     for _i, block, _at, _lo, hi in _overlapping_blocks(layout, node)), default=0)
    return node.size + in_flight


def peak_unpack_bytes(layout: BundleLayout) -> int:
    """The largest amount held at once while unpacking the wanted files one after the other."""
    return max((node_unpack_cost(layout, node) for node in layout.nodes if is_wanted(node)), default=0)


class _LzmaStream:
    """A Unity LZMA block (5 property bytes, then a raw LZMA1 stream) decoded as far as asked, and no further.

    Later files of the same block continue where the previous one stopped instead of decoding
    the block from its start again (many serialized files in one LZMA bundle would otherwise cost
    quadratic time).
    """

    def __init__(self, f: BinaryIO, packed_at: int, packed_size: int) -> None:
        f.seek(packed_at)
        props, dict_size = struct.unpack("<BI", f.read(5))
        lc, rest = props % 9, props // 9
        self._decoder = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[{
            "id": lzma.FILTER_LZMA1, "dict_size": dict_size, "lc": lc, "lp": rest % 5, "pb": rest // 5,
        }])
        self._f, self._next_read, self._left = f, packed_at + 5, packed_size - 5
        self._out = bytearray()

    def prefix(self, need: int) -> memoryview:
        """The first ``need`` unpacked bytes (fewer when the block ends earlier)."""
        while len(self._out) < need and not self._decoder.eof:
            piece = b""
            if self._decoder.needs_input:
                self._f.seek(self._next_read)
                piece = self._f.read(min(_LZMA_PIECE, self._left))
                self._left -= len(piece)
                self._next_read += len(piece)
                if not piece:
                    raise ValueError("the LZMA block ends before the file does")
            self._out += self._decoder.decompress(piece, max_length=min(_LZMA_PIECE, need - len(self._out)))
        return memoryview(self._out)[:need]


def _unpack_block(
    f: BinaryIO, block: BlockInfo, index: int, packed_at: int, hi: int, streams: dict[int, _LzmaStream]
) -> bytes:
    if _is_lzma(block):
        stream = streams.get(index)
        if stream is None:
            streams.clear()  # blocks are visited in order: the previous stream is never needed again
            stream = streams[index] = _LzmaStream(f, packed_at, block.compressed)
        return stream.prefix(hi)
    f.seek(packed_at)
    unpack = CompressionHelper.DECOMPRESSION_MAP[CompressionFlags(block.flags & COMPRESSION_MASK)]
    return bytes(unpack(f.read(block.compressed), block.uncompressed))


def unpack_node(
    f: BinaryIO, layout: BundleLayout, node: NodeInfo, streams: dict[int, _LzmaStream] | None = None
) -> bytes:
    """The bytes of one file of an open bundle, unpacking only the blocks it overlaps."""
    streams = {} if streams is None else streams
    parts = []
    for index, block, packed_at, lo, hi in _overlapping_blocks(layout, node):
        parts.append(bytes(_unpack_block(f, block, index, packed_at, hi, streams)[lo:hi]))
    data = b"".join(parts)
    if len(data) != node.size:
        raise ValueError(f"{node.path}: unpacked {len(data)} of {node.size} bytes")
    return data


def unpack_nodes(
    path: Path | str, layout: BundleLayout, select: Callable[[NodeInfo], bool] = is_wanted
) -> Iterator[tuple[NodeInfo, bytes]]:
    """Each selected file of the bundle with its bytes, one at a time (the previous one can be freed)."""
    streams: dict[int, _LzmaStream] = {}
    with open(path, "rb") as f:
        for node in layout.nodes:
            if select(node):
                yield node, unpack_node(f, layout, node, streams)
