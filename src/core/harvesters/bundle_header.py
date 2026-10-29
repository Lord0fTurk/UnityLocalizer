# -*- coding: utf-8 -*-
"""The block and file tables of a UnityFS bundle, read from its header without unpacking any data.

UnityPy unpacks a whole bundle (every block, including the textures and audio streams the
harvest never reads) before it looks at a single object, so the memory a scan needs follows
the *uncompressed* size, which can be many times the file's size on disk. Everything the harvest
wants to know before opening a bundle sits in a small "blocks info" record next to the header:
how large the bundle becomes when unpacked, and which files it holds at which offsets. That is
enough to unpack only the serialized files (see ``bundle_unpack``) and to know what that costs.

The layout mirrors ``UnityPy.files.BundleFile.read_fs`` (big-endian):
signature, format version, player and engine version strings, total size, compressed and
uncompressed size of the blocks info, flags; then, 16-byte aligned for format 7 and later and
for Unity 2019.4.15+, the (compressed) blocks info at that position or at the end of the file:
16-byte hash, block count, per block uncompressed size, compressed size and flags, then the
file count and per file offset (into the unpacked data), size, flags and path. The data blocks
follow the blocks info (or the header when the blocks info is at the end), aligned to 16 bytes
when the engine's ``BlockInfoNeedPaddingAtStart`` flag is set.
"""

from __future__ import annotations

import logging
import os
import re
import struct
from dataclasses import dataclass
from pathlib import Path

from UnityPy.enums import CompressionFlags
from UnityPy.helpers import CompressionHelper

logger = logging.getLogger(__name__)

UNITYFS_SIGNATURE = b"UnityFS\x00"
_BLOCKS_INFO_AT_END = 0x80
_PADDING_AT_START = 0x200
_ENCRYPTED_NEW, _ENCRYPTED_OLD = 0x400, 0x200  # the same bit means different things before and after the alignment fix
COMPRESSION_MASK = 0x3F
_HEADER_PROBE = 1024  # the signature, version strings and size fields fit comfortably in the first bytes
_HASH_BYTES = 16
_BLOCK_RECORD = struct.Struct(">IIH")  # uncompressed size, compressed size, flags
_NODE_RECORD = struct.Struct(">qqI")  # offset, size, flags (the path follows, null-terminated)
_ENGINE_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)")
# First engine version, per major, that carries the alignment fix (older ones use 0x200 for encryption).
_ALIGNMENT_FIX = {2020: (2020, 3, 34), 2021: (2021, 3, 2), 2022: (2022, 1, 1)}


@dataclass(frozen=True)
class BlockInfo:
    """One compressed block of a bundle's data."""

    uncompressed: int
    compressed: int
    flags: int


@dataclass(frozen=True)
class NodeInfo:
    """One file inside a bundle: a range of the unpacked data."""

    offset: int
    size: int
    flags: int
    path: str


@dataclass(frozen=True)
class BundleLayout:
    """Where a bundle's blocks and files are; ``data_start`` is the file offset of the first data block."""

    blocks: tuple[BlockInfo, ...]
    nodes: tuple[NodeInfo, ...]
    data_start: int

    @property
    def unpacked_size(self) -> int:
        return sum(block.uncompressed for block in self.blocks)


def _read_cstring(data: bytes, pos: int) -> tuple[str, int]:
    end = data.index(b"\x00", pos)
    return data[pos:end].decode("utf-8", errors="replace"), end + 1


def _parse_header(head: bytes) -> tuple[int, str, int, int, int, int]:
    """(format version, engine version, position after the header, compressed and uncompressed blocks-info size, flags)."""
    pos = len(UNITYFS_SIGNATURE)
    (version,) = struct.unpack_from(">I", head, pos)
    _player, pos = _read_cstring(head, pos + 4)
    engine, pos = _read_cstring(head, pos)
    _total, compressed, uncompressed, flags = struct.unpack_from(">qIII", head, pos)
    return version, engine, pos + struct.calcsize(">qIII"), compressed, uncompressed, flags


def _engine_tuple(engine: str) -> tuple[int, int, int] | None:
    match = _ENGINE_VERSION_RE.match(engine)
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


def _is_aligned(version: int, engine: str) -> bool:
    """Format 7+ and Unity 2019.4.15+ (which ship format 6 but aligned) pad the header to 16 bytes."""
    if version >= 7:
        return True
    parsed = _engine_tuple(engine)
    return parsed is not None and parsed[0] == 2019 and parsed >= (2019, 4, 15)


def _has_alignment_fix_flags(engine: str) -> bool:
    """True when 0x200 means "padding at start" (and 0x400 encryption), as UnityPy decides it."""
    parsed = _engine_tuple(engine)
    if parsed is None:
        return False  # UnityPy cannot even open a bundle without a readable engine version
    first_fixed = _ALIGNMENT_FIX.get(parsed[0])
    if first_fixed is not None:
        return parsed >= first_fixed
    return parsed[0] >= 2023  # 2019 and older never had the fix; 2023 and Unity 6 always have it


def _parse_blocks_info(info: bytes) -> tuple[tuple[BlockInfo, ...], tuple[NodeInfo, ...]]:
    (count,) = struct.unpack_from(">i", info, _HASH_BYTES)
    at = _HASH_BYTES + 4
    if not 0 <= count <= (len(info) - at) // _BLOCK_RECORD.size:
        raise ValueError(f"implausible block count {count}")
    blocks = tuple(BlockInfo(*_BLOCK_RECORD.unpack_from(info, at + i * _BLOCK_RECORD.size)) for i in range(count))
    at += count * _BLOCK_RECORD.size
    (node_count,) = struct.unpack_from(">i", info, at)
    at += 4
    if not 0 <= node_count <= len(info) - at:
        raise ValueError(f"implausible file count {node_count}")
    nodes: list[NodeInfo] = []
    for _ in range(node_count):
        offset, size, flags = _NODE_RECORD.unpack_from(info, at)
        path, at = _read_cstring(info, at + _NODE_RECORD.size)
        nodes.append(NodeInfo(offset, size, flags, path))
    return blocks, tuple(nodes)


def _read_blocks_info(f, head: bytes) -> tuple[bytes, int, int, int, bool, str]:
    """(raw blocks info, its uncompressed size, flags, data start, flags are the new kind, engine) of an open bundle."""
    version, engine, pos, compressed, uncompressed, flags = _parse_header(head)
    if _is_aligned(version, engine):
        pos = (pos + 15) & ~15
    if flags & _BLOCKS_INFO_AT_END:
        data_start = pos
        pos = os.fstat(f.fileno()).st_size - compressed
    else:
        data_start = pos + compressed
    f.seek(pos)
    return f.read(compressed), uncompressed, flags, data_start, _has_alignment_fix_flags(engine), engine


def read_layout(path: Path | str) -> BundleLayout | None:
    """Blocks, files and data offset of a UnityFS bundle; None when it cannot be read.

    Encrypted bundles, other bundle formats, damaged headers and unknown compression give None,
    and the caller falls back to opening the bundle the usual way.
    """
    try:
        with open(path, "rb") as f:
            head = f.read(_HEADER_PROBE)
            if not head.startswith(UNITYFS_SIGNATURE):
                return None
            raw, uncompressed, flags, data_start, new_flags, _engine = _read_blocks_info(f, head)
            if flags & (_ENCRYPTED_NEW if new_flags else _ENCRYPTED_OLD):
                return None
            if new_flags and flags & _PADDING_AT_START:
                data_start = (data_start + 15) & ~15
        compression = CompressionFlags(flags & COMPRESSION_MASK)
        info = CompressionHelper.DECOMPRESSION_MAP[compression](raw, uncompressed)
        blocks, nodes = _parse_blocks_info(bytes(info))
        layout = BundleLayout(blocks, nodes, data_start)
        if any(n.offset < 0 or n.size < 0 or n.offset + n.size > layout.unpacked_size for n in nodes):
            raise ValueError("a file lies outside the unpacked data")
        return layout
    except Exception as exc:  # corrupt or encrypted header, unknown compression, lz4/lzma errors, truncated file
        logger.debug("Cannot read the layout of %s: %s", path, exc)
        return None


def unityfs_uncompressed_size(path: Path | str) -> int | None:
    """Total uncompressed size of a UnityFS bundle's data blocks; None when it cannot be read."""
    layout = read_layout(path)
    return None if layout is None else layout.unpacked_size
