# -*- coding: utf-8 -*-
"""Hand-written UnityFS bundles for the tests, with known contents, checked against UnityPy where it can read them."""

from __future__ import annotations

import struct

import lz4.block
import UnityPy

CHUNK = 64 * 1024
NODE_SERIALIZED = 4
Node = tuple[str, bytes, int]  # path, bytes, node flags


def _pack(chunks: list[bytes], compression: str) -> tuple[list[bytes], int]:
    if compression == "none":
        return chunks, 0
    return [lz4.block.compress(c, mode="high_compression", store_size=False) for c in chunks], 2


def _is_aligned(version: int, engine: str) -> bool:
    return version >= 7 or (engine.startswith("2019.4.") and int(engine.split(".")[2].split("f")[0]) >= 15)


def _assemble(
    info: bytes, packed_blocks: list[bytes], block_flag: int, *, version: int, engine: str, at_end: bool,
    pad_blocks: bool, extra_flags: int,
) -> bytes:
    info_packed = info if block_flag == 0 else lz4.block.compress(info, store_size=False)
    flags = block_flag | (0x80 if at_end else 0x40) | (0x200 if pad_blocks else 0) | extra_flags
    head = b"UnityFS\x00" + struct.pack(">I", version) + b"5.x.x\x00" + engine.encode() + b"\x00"
    fixed = struct.calcsize(">qIII")
    pad = (-(len(head) + fixed)) % 16 if _is_aligned(version, engine) else 0
    data = b"".join(packed_blocks)
    start = len(head) + fixed + pad
    data_pad = 0
    if pad_blocks:
        data_pad = (-(start if at_end else start + len(info_packed))) % 16
    body = (b"\x00" * data_pad + data + info_packed) if at_end else (info_packed + b"\x00" * data_pad + data)
    total = start + len(body)
    return head + struct.pack(">qIII", total, len(info_packed), len(info), flags) + b"\x00" * pad + body


def _info(blocks: list[tuple[int, int, int]], nodes: list[tuple[int, int, int, str]]) -> bytes:
    return (
        b"\x00" * 16 + struct.pack(">i", len(blocks)) + b"".join(struct.pack(">IIH", *b) for b in blocks)
        + struct.pack(">i", len(nodes))
        + b"".join(struct.pack(">qqI", offset, size, flags) + path.encode() + b"\x00" for offset, size, flags, path in nodes)
    )


def build_unityfs(
    payload: bytes | None = None, *, nodes: list[Node] | None = None, version: int = 7, engine: str = "2022.3.10f1",
    at_end: bool = False, pad_blocks: bool = False, extra_flags: int = 0, compression: str = "lz4",
    chunk: int = CHUNK,
) -> bytes:
    """A valid UnityFS bundle: the nodes' bytes are laid out one after the other and cut into ``chunk`` blocks."""
    files = nodes or [("CAB-test", payload or b"", 0)]
    stream = b"".join(data for _path, data, _flags in files)
    chunks = [stream[i:i + chunk] for i in range(0, len(stream), chunk)] or [b""]
    packed, block_flag = _pack(chunks, compression)
    blocks = [(len(c), len(p), block_flag) for c, p in zip(chunks, packed)]
    offsets, at = [], 0
    for _path, data, _flags in files:
        offsets.append(at)
        at += len(data)
    table = [(offset, len(data), flags, path) for offset, (path, data, flags) in zip(offsets, files)]
    return _assemble(_info(blocks, table), packed, block_flag, version=version, engine=engine, at_end=at_end,
                     pad_blocks=pad_blocks, extra_flags=extra_flags)


def build_sparse(
    first: bytes, claimed: int, *, first_flags: int = NODE_SERIALIZED, claimed_flags: int = 0,
    claimed_path: str = "CAB-sparse.resS",
) -> bytes:
    """A bundle that says it holds ``claimed`` more bytes behind ``first`` but whose data is junk.

    Reading the first file is fine; unpacking the claimed blocks would fail (or need gigabytes),
    so it proves that they are never touched.
    """
    packed, block_flag = _pack([first], "lz4")
    blocks = [(len(first), len(packed[0]), block_flag)]
    junk = []
    remaining = claimed
    while remaining > 0:
        size = min(2**31, remaining)
        blocks.append((size, 8, block_flag))
        junk.append(b"\xde\xad\xbe\xef" * 2)
        remaining -= size
    table = [(0, len(first), first_flags, "CAB-sparse"), (len(first), claimed, claimed_flags, claimed_path)]
    return _assemble(_info(blocks, table), packed + junk, block_flag, version=7, engine="2022.3.10f1",
                     at_end=False, pad_blocks=False, extra_flags=0)


def unitypy_files(blob: bytes) -> dict[str, bytes]:
    """What UnityPy unpacks from a bundle, file by file: the oracle for the unpacker."""
    out: dict[str, bytes] = {}
    for name, sub in UnityPy.load(blob).file.files.items():
        reader = getattr(sub, "reader", sub)
        out[name] = bytes(reader.view)
    return out
