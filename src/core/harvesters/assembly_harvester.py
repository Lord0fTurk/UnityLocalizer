# -*- coding: utf-8 -*-
"""Mono Assembly-CSharp.dll static string harvester for Unity games."""

from __future__ import annotations

import logging
import struct
from pathlib import Path

import pefile

from src.core.harvesters.text_filter import is_code_literal_text

logger = logging.getLogger(__name__)

# Engine, BCL and widespread third-party assemblies that never hold game UI text.
FRAMEWORK_DLL_PREFIXES: tuple[str, ...] = (
    "unityengine", "unity.", "system", "mscorlib", "netstandard", "mono.", "microsoft.",
    "newtonsoft", "dotween", "demigiant", "steamworks", "facepunch", "rewired",
    "fmod", "wwise", "ak.wwise", "zstring", "unitask", "cinemachine", "bepinex",
    "0harmony", "harmony", "xunity", "il2cpp", "assembly-csharp-editor",
)


class AssemblyHarvester:
    """Extracts translatable string literals from Mono .NET PE assemblies (#US stream)."""

    @staticmethod
    def is_translatable(text: str) -> bool:
        """C# literal filter shared with the IL2CPP metadata harvester.

        Mono ``#US`` literals are mostly identifiers, PlayerPrefs keys and input axis
        names; the shared natural-language heuristic keeps them away from the engine.
        """
        return is_code_literal_text(text, max_length=1000)

    @classmethod
    def _read_7bit_encoded_int(cls, data: bytes, ptr: int) -> tuple[int, int]:
        """Decode .NET 7-bit encoded length prefix. Returns (length, new_ptr)."""
        if ptr >= len(data):
            return 0, ptr
        b = data[ptr]
        ptr += 1
        if (b & 0x80) == 0:
            return b, ptr
        if (b & 0xC0) == 0x80 and ptr < len(data):
            length = ((b & 0x3F) << 8) | data[ptr]
            return length, ptr + 1
        if (b & 0xE0) == 0xC0 and ptr + 2 < len(data):
            length = (
                ((b & 0x1F) << 24)
                | (data[ptr] << 16)
                | (data[ptr + 1] << 8)
                | data[ptr + 2]
            )
            return length, ptr + 3
        return 0, ptr

    @classmethod
    def _extract_us_stream(cls, pe: pefile.PE) -> bytes:
        """Locate and return raw bytes of the #US (User String) stream from PE metadata."""
        com_entry = pefile.DIRECTORY_ENTRY.get("IMAGE_DIRECTORY_ENTRY_COM_DESCRIPTOR")
        if com_entry is None or com_entry >= len(pe.OPTIONAL_HEADER.DATA_DIRECTORY):
            return b""

        com_dir = pe.OPTIONAL_HEADER.DATA_DIRECTORY[com_entry]
        if com_dir.VirtualAddress == 0 or com_dir.Size < 16:
            return b""

        com_data = pe.get_data(com_dir.VirtualAddress, min(com_dir.Size, 72))
        if len(com_data) < 16:
            return b""
        cb, major, minor, meta_rva, meta_size = struct.unpack_from("<IHHII", com_data)
        if meta_rva == 0 or meta_size < 20 or meta_size > 256 * 1024 * 1024:
            return b""
        meta_data = pe.get_data(meta_rva, meta_size)
        if len(meta_data) < 20:
            return b""

        sig = struct.unpack_from("<I", meta_data, 0)[0]
        if sig != 0x424A5342:  # 'BSJB' signature
            return b""

        v_len = struct.unpack_from("<I", meta_data, 12)[0]
        offset = 16 + v_len
        if offset % 4 != 0:
            offset += 4 - (offset % 4)
        if offset + 4 > len(meta_data):
            return b""

        flags, num_streams = struct.unpack_from("<HH", meta_data, offset)
        offset += 4

        for _ in range(min(num_streams, 64)):
            if offset + 8 > len(meta_data):
                break
            s_offset, s_size = struct.unpack_from("<II", meta_data, offset)
            offset += 8
            name = b""
            while offset < len(meta_data):
                b = meta_data[offset : offset + 1]
                offset += 1
                if b == b"\x00" or not b:
                    break
                name += b
            if offset % 4 != 0:
                offset += 4 - (offset % 4)

            if name == b"#US":
                if s_offset > len(meta_data) or s_offset + s_size > len(meta_data):
                    return b""
                return meta_data[s_offset : s_offset + s_size]

        return b""

    @classmethod
    def _decode_us_stream(cls, us_data: bytes) -> list[str]:
        """Parse UTF-16LE user strings from a raw #US metadata stream."""
        results: list[str] = []
        seen: set[str] = set()
        ptr = 1  # First byte of #US stream is always 0
        total_len = len(us_data)

        while ptr < total_len:
            length, next_ptr = cls._read_7bit_encoded_int(us_data, ptr)
            if next_ptr == ptr:
                break
            ptr = next_ptr
            if length == 0:
                continue
            if ptr + length > total_len:
                break
            if length == 1:
                ptr += 1
                continue

            str_bytes = us_data[ptr : ptr + length - 1]
            ptr += length

            try:
                decoded = str_bytes.decode("utf-16le")
            except UnicodeDecodeError:
                continue
            if cls.is_translatable(decoded) and decoded not in seen:
                seen.add(decoded)
                results.append(decoded)
        return results

    @classmethod
    def harvest(cls, assembly_path: Path | str) -> list[str]:
        """Harvest translatable user strings from a .NET assembly file."""
        target = Path(assembly_path)
        if not target.is_file():
            logger.warning("Assembly file not found: %s", target)
            return []

        pe = None
        try:
            pe = pefile.PE(str(target), fast_load=True)
            us_data = cls._extract_us_stream(pe)
        except Exception as exc:
            logger.error("Failed to parse assembly PE %s: %s", target, exc)
            return []
        finally:
            if pe:
                try:
                    pe.close()
                except Exception as close_exc:
                    logger.debug("Closing PE handle for %s failed: %s", target, close_exc)

        if not us_data:
            logger.info("No #US stream found in %s", target.name)
            return []

        results = cls._decode_us_stream(us_data)
        logger.info("Harvested %d translatable strings from %s", len(results), target.name)
        return results

    @staticmethod
    def candidate_assemblies(managed_dir: Path) -> list[Path]:
        """Return game-owned assemblies, skipping engine, BCL and common framework DLLs."""
        return [
            dll
            for dll in sorted(managed_dir.glob("*.dll"))
            if not dll.name.lower().startswith(FRAMEWORK_DLL_PREFIXES)
        ]

    @classmethod
    def harvest_managed_dir(cls, managed_dir: Path | str) -> list[str]:
        """Harvest strings from all game-owned assemblies in the Managed folder."""
        managed_path = Path(managed_dir)
        if not managed_path.is_dir():
            return []

        all_strings: list[str] = []
        seen: set[str] = set()
        for dll_file in cls.candidate_assemblies(managed_path):
            for s in cls.harvest(dll_file):
                if s not in seen:
                    seen.add(s)
                    all_strings.append(s)
        return all_strings
