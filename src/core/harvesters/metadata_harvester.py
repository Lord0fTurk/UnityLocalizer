# -*- coding: utf-8 -*-
"""Direct string harvester for IL2CPP global-metadata.dat."""

from __future__ import annotations

import logging
import struct
from pathlib import Path

from src.core.harvesters.text_filter import is_code_literal_text

logger = logging.getLogger(__name__)

IL2CPP_METADATA_MAGIC = 0xFAB11BAF


class MetadataHarvester:
    """Parses IL2CPP global-metadata.dat binary files to extract translatable string literals."""

    @staticmethod
    def _read_tables(path: Path) -> tuple[int, bytes, bytes]:
        """Validate header offsets against file size and read literal table + string pool."""
        file_size = path.stat().st_size
        with open(path, "rb") as f:
            header_bytes = f.read(256)
            if len(header_bytes) < 32:
                raise ValueError("Corrupt metadata file: header too short")

            magic, _version = struct.unpack_from("<II", header_bytes, 0)
            if magic != IL2CPP_METADATA_MAGIC:
                raise ValueError(f"Invalid IL2CPP metadata magic: 0x{magic:08X}")

            str_lit_offset, str_lit_field = struct.unpack_from("<II", header_bytes, 8)
            str_data_offset, str_data_size = struct.unpack_from("<II", header_bytes, 16)

            if str_data_offset >= str_lit_offset + (str_lit_field * 8):
                num_literals = str_lit_field
                table_bytes_len = str_lit_field * 8
            else:
                num_literals = str_lit_field // 8
                table_bytes_len = str_lit_field

            if (
                table_bytes_len < 0
                or str_data_size < 0
                or str_lit_offset + table_bytes_len > file_size
                or str_data_offset + str_data_size > file_size
            ):
                raise ValueError("Corrupt or obfuscated IL2CPP metadata header offsets")

            f.seek(str_lit_offset)
            lit_bytes = f.read(table_bytes_len)
            f.seek(str_data_offset)
            data_blob = f.read(str_data_size)
        return num_literals, lit_bytes, data_blob

    @classmethod
    def harvest(cls, metadata_path: Path | str) -> list[str]:
        """Extract translatable string pool from global-metadata.dat without executing the game."""
        path = Path(metadata_path)
        if not path.is_file():
            raise FileNotFoundError(f"global-metadata.dat not found at: {path}")

        num_literals, lit_bytes, data_blob = cls._read_tables(path)
        extracted: list[str] = []
        seen: set[str] = set()
        undecodable = 0

        for i in range(num_literals):
            if (i * 8) + 8 > len(lit_bytes):
                break
            length, data_idx = struct.unpack_from("<II", lit_bytes, i * 8)
            if data_idx + length <= len(data_blob):
                try:
                    text = data_blob[data_idx : data_idx + length].decode("utf-8").strip()
                except UnicodeDecodeError:
                    undecodable += 1
                    continue
                if text not in seen and cls._is_translatable_string(text):
                    seen.add(text)
                    extracted.append(text)

        if undecodable:
            logger.debug("Skipped %d non-UTF-8 literals in %s", undecodable, path.name)
        logger.info("Harvested %d translatable strings from %s", len(extracted), path.name)
        return extracted

    @staticmethod
    def _is_translatable_string(text: str) -> bool:
        """C# literal filter shared with the Mono assembly harvester."""
        return is_code_literal_text(text)
