# -*- coding: utf-8 -*-
"""Unit tests for static binary and assembly harvesters."""

from pathlib import Path
from typing import Any

from src.core.harvesters.assembly_harvester import AssemblyHarvester
from src.core.harvesters.asset_harvester import AssetHarvester


def test_assembly_harvester_is_translatable() -> None:
    """Test filtering of translatable vs technical strings."""
    assert AssemblyHarvester.is_translatable("Start Game") is True
    assert AssemblyHarvester.is_translatable("Are you sure you want to exit?") is True
    assert AssemblyHarvester.is_translatable("Seçenekler") is True

    # Technical strings must be filtered
    assert AssemblyHarvester.is_translatable("Assets/Textures/hero.png") is False
    assert AssemblyHarvester.is_translatable("UnityEngine.UI") is False
    assert AssemblyHarvester.is_translatable("audio.wav") is False
    assert AssemblyHarvester.is_translatable("a1b2c3d4e5f607182930415263748596") is False
    assert AssemblyHarvester.is_translatable("#FFFFFF") is False
    assert AssemblyHarvester.is_translatable("x") is False
    assert AssemblyHarvester.is_translatable("   ") is False


def test_assembly_harvester_7bit_decoder() -> None:
    """Test decoding of .NET 7-bit encoded integers."""
    # 1-byte length (< 128)
    data = bytes([0x2A])  # 42
    length, ptr = AssemblyHarvester._read_7bit_encoded_int(data, 0)
    assert length == 42
    assert ptr == 1

    # 2-byte length
    data = bytes([0x80 | 0x05, 0x02])  # 0x0205
    length, ptr = AssemblyHarvester._read_7bit_encoded_int(data, 0)
    assert length == ((5 << 8) | 2)
    assert ptr == 2


def test_assembly_harvester_missing_file() -> None:
    """Test graceful handling of non-existent files."""
    strings = AssemblyHarvester.harvest(Path("non_existent_file.dll"))
    assert strings == []


def test_asset_harvester_is_translatable() -> None:
    """Test filtering of translatable vs technical tokens in AssetHarvester."""
    from src.core.harvesters.asset_harvester import AssetHarvester

    # Legitimate UI strings
    assert AssetHarvester.is_translatable("Continue") is True
    assert AssetHarvester.is_translatable("Settings") is True
    assert AssetHarvester.is_translatable("Credits") is True
    assert AssetHarvester.is_translatable("Gallery") is True
    assert AssetHarvester.is_translatable("Movement") is True
    assert AssetHarvester.is_translatable("Cast Spells") is True
    assert AssetHarvester.is_translatable("Empties your lower intestines") is True

    # Technical strings must be rejected
    assert AssetHarvester.is_translatable("<Keyboard>/w") is False
    assert AssetHarvester.is_translatable("<Gamepad>/rightStick") is False
    assert AssetHarvester.is_translatable("UnityEngine.Transform") is False
    assert AssetHarvester.is_translatable("TMPro.TextMeshProUGUI") is False
    assert AssetHarvester.is_translatable("_MainTex") is False
    assert AssetHarvester.is_translatable("_Color") is False
    assert AssetHarvester.is_translatable("Wall_01 left_cover") is False
    assert AssetHarvester.is_translatable("texture.png") is False
    assert AssetHarvester.is_translatable("sound.wav") is False
    assert AssetHarvester.is_translatable("abc\x00def") is False
    assert AssetHarvester.is_translatable("#10B981") is False


def test_asset_harvester_extract_binary_object() -> None:
    """Test binary length-prefixed string extraction from raw MonoBehaviour bytes."""
    import struct
    from src.core.harvesters.asset_harvester import AssetHarvester

    class DummyObj:
        class Type:
            name = "MonoBehaviour"
        type = Type()

        def get_raw_data(self) -> bytes:
            header = b"\x00" * 32
            # Pack 'Continue' with 4-byte length prefix
            s1 = b"Continue"
            entry1 = struct.pack("<I", len(s1)) + s1
            # Padding to 4 bytes
            entry1 += b"\x00" * ((4 - (len(s1) % 4)) % 4)

            s2 = b"Settings"
            entry2 = struct.pack("<I", len(s2)) + s2

            return header + entry1 + entry2

    dummy = DummyObj()
    extracted = AssetHarvester.extract_strings_from_object(dummy)
    assert "Continue" in extracted
    assert "Settings" in extracted


def test_asset_harvester_empty_data_dir(tmp_path: Path) -> None:
    """Test asset harvester handling of empty directories."""
    from src.core.harvesters.asset_harvester import AssetHarvester

    assert AssetHarvester.harvest_data_dir(tmp_path) == []
    assert AssetHarvester.harvest_data_dir(tmp_path / "nonexistent") == []


def test_bundle_locator(tmp_path: Path) -> None:
    """Verify bundle detection identifies UnityFS containers and ignores media."""
    from src.core.harvesters.bundle_locator import find_serialized_sources, has_bundle_magic

    data_dir = tmp_path / "Game_Data"
    data_dir.mkdir(parents=True)

    # 1. Root scene and shared assets
    (data_dir / "sharedassets0.assets").write_bytes(b"UnityFS header dummy data")
    (data_dir / "level0").write_bytes(b"level data")

    # 2. Addressables bundle with UnityFS magic
    aa_dir = data_dir / "StreamingAssets" / "aa" / "StandaloneWindows64"
    aa_dir.mkdir(parents=True)
    bundle_file = aa_dir / "dialogue_assets_all.bundle"
    bundle_file.write_bytes(b"UnityFS\x00\x00\x00\x075.x.x")

    # 3. Media files that must be ignored
    (aa_dir / "cutscene.mp4").write_bytes(b"UnityFS media mock")
    (aa_dir / "soundtrack.wav").write_bytes(b"UnityFS audio mock")

    assert has_bundle_magic(bundle_file) is True
    found = find_serialized_sources(data_dir)
    assert (data_dir / "sharedassets0.assets") in found
    assert (data_dir / "level0") in found
    assert bundle_file in found
    assert (aa_dir / "cutscene.mp4") not in found
    assert (aa_dir / "soundtrack.wav") not in found


def test_harvest_collector(tmp_path: Path) -> None:
    """Verify aggregation across assets, assemblies and StreamingAssets."""
    from src.core.engine_profiler import UnityGameProfile
    from src.core.harvesters.harvest_collector import HarvestCollector
    from src.core.progress import ProgressEvent

    game_dir = tmp_path / "Game"
    data_dir = game_dir / "Game_Data"
    sa_dir = data_dir / "StreamingAssets"
    sa_dir.mkdir(parents=True)

    (sa_dir / "dialogue.json").write_text('{"greeting": "Welcome traveler!"}', encoding="utf-8")

    profile = UnityGameProfile(
        game_path=game_dir,
        data_dir=data_dir,
        is_il2cpp=False,
        is_64bit=True,
    )

    events: list[ProgressEvent] = []
    collector = HarvestCollector(progress=events.append)
    result = collector.collect(profile)

    assert "Welcome traveler!" in result.strings
    assert (sa_dir / "dialogue.json") in result.streaming_files
    assert "streaming" in result.per_channel
    assert any(e.key == "pipeline.harvest_streaming" for e in events)
    assert any(e.key == "pipeline.harvest_done" for e in events)




def test_metadata_filter_accepts_richtext_and_rejects_compiler_symbols() -> None:
    from src.core.harvesters.metadata_harvester import MetadataHarvester

    accepts = MetadataHarvester._is_translatable_string
    assert accepts("<color=red>Game Over</color>") is True
    assert accepts("<b>Warning:</b> low health") is True
    assert accepts("<Module>") is False
    assert accepts("<Name>k__BackingField") is False
    assert accepts("<b>5__2") is False
    assert accepts("<Keyboard>/space") is False
    assert accepts("<color=red></color>") is False


def test_code_literal_filter_is_shared_and_rejects_identifiers() -> None:
    from src.core.harvesters.metadata_harvester import MetadataHarvester

    for accepts in (AssemblyHarvester.is_translatable, MetadataHarvester._is_translatable_string):
        assert accepts("Start Game") is True
        assert accepts("Are you sure?") is True
        assert accepts("Seçenekler") is True
        assert accepts("ゲーム開始") is True
        for technical in ("playerName", "MAX_HEALTH", "ui.menu.title", "save_slot_1", "audio.wav", "config.json"):
            assert accepts(technical) is False, technical


def test_asset_filter_uses_shared_technical_rules() -> None:
    assert AssetHarvester.is_translatable("Assets/UI/menu.prefab") is False
    assert AssetHarvester.is_translatable("d41d8cd98f00b204e9800998ecf8427e") is False
    assert AssetHarvester.is_translatable("cache.resS") is False  # was missed: ".resS" never matched lowercase
    assert AssetHarvester.is_translatable("New Game") is True


def test_asset_harvest_reports_each_file_and_honours_cancel(tmp_path: Path, monkeypatch: Any) -> None:
    import pytest

    from src.core.progress import CancelToken, OperationCancelled, ProgressEvent

    data_dir = tmp_path / "Game_Data"
    data_dir.mkdir()
    for name in ("level0", "level1", "sharedassets0.assets"):
        (data_dir / name).write_bytes(b"\x00" * 16)
    seen: list[str] = []
    monkeypatch.setattr(AssetHarvester, "harvest_asset_file", classmethod(lambda cls, p, *a: seen.append(p.name) or []))

    events: list[ProgressEvent] = []
    AssetHarvester.harvest_data_dir(data_dir, progress=events.append)
    file_events = [e for e in events if e.key == "pipeline.harvest_asset_file"]
    assert [(e.current, e.total) for e in file_events] == [(1, 3), (2, 3), (3, 3)]

    token = CancelToken()
    seen.clear()
    monkeypatch.setattr(
        AssetHarvester, "harvest_asset_file", classmethod(lambda cls, p, *a: (seen.append(p.name), token.cancel()) and [])
    )
    with pytest.raises(OperationCancelled):
        AssetHarvester.harvest_data_dir(data_dir, cancel=token)
    assert len(seen) == 1  # stops before the next file
