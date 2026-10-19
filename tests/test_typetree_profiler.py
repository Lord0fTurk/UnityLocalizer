# -*- coding: utf-8 -*-
"""Tests for TypeTree-aware asset harvesting and framework/metadata profiling."""

import struct
from pathlib import Path
from typing import Any

from src.core.engine_profiler import (
    IL2CPP_METADATA_MAGIC,
    EngineProfiler,
    UnityGameProfile,
    read_metadata_header,
    scan_markers,
)
from src.core.harvesters.asset_harvester import AssetHarvester
from src.core.harvesters.typetree_provider import create_typetree_generator
from src.core.harvesters.typetree_text import collect_display_strings, has_user_fields

# --- TypeTree dict rules ---------------------------------------------------------


def test_generic_walk_skips_object_names_and_technical_fields() -> None:
    tree = {
        "m_GameObject": {"m_FileID": 0, "m_PathID": 12},
        "m_Name": "StartButtonLabel",
        "m_EditorClassIdentifier": "",
        "m_text": "Start Game",
        "tooltip": {"title": "Begin", "item_id": "btn_start", "icon": "ui/start"},
        "options": ["Easy", "Hard"],
    }
    assert collect_display_strings(tree) == ["Start Game", "Begin", "Easy", "Hard"]


def test_unity_localization_string_table_source_only() -> None:
    table = {
        "m_Name": "UI_en",
        "m_TableCollectionName": "UI",
        "m_LocaleId": {"m_Code": "en"},
        "m_TableData": [
            {"m_Id": 1, "m_Localized": "New Game", "m_Metadata": {"m_Items": []}},
            {"m_Id": 2, "m_Localized": "Load Game", "m_Metadata": {"m_Items": []}},
        ],
    }
    assert collect_display_strings(table, "en") == ["New Game", "Load Game"]
    french = dict(table, m_LocaleId={"m_Code": "fr-FR"})
    assert collect_display_strings(french, "en") == []


def test_i2_language_source_picks_source_column() -> None:
    tree = {
        "mSource": {
            "mLanguages": [{"Name": "French", "Code": "fr"}, {"Name": "English", "Code": "en"}],
            "mTerms": [
                {"Term": "Menu/Start", "TermType": 0, "Languages": ["Commencer", "Start"]},
                {"Term": "Menu/Quit", "TermType": 0, "Languages": ["Quitter", "Quit"]},
                {"Term": "Menu/Empty", "TermType": 0, "Languages": ["Vide"]},
            ],
        }
    }
    assert collect_display_strings(tree, "en") == ["Start", "Quit"]


def test_dialogue_system_database_display_fields() -> None:
    tree = {
        "actors": [{"id": 1, "fields": [
            {"title": "Name", "value": "Sally", "type": 0},
            {"title": "Pictures", "value": "[]", "type": 3},
        ]}],
        "conversations": [{"id": 1, "fields": [{"title": "Title", "value": "Intro"}],
                           "dialogueEntries": [{"id": 0, "fields": [
                               {"title": "Dialogue Text", "value": "Welcome to town!"},
                               {"title": "Menu Text", "value": "Say hello"},
                               {"title": "Sequence", "value": "Camera(Closeup)"},
                               {"title": "fr", "value": "Bienvenue"},
                           ]}]}],
    }
    assert sorted(collect_display_strings(tree)) == sorted(
        ["Sally", "Intro", "Welcome to town!", "Say hello"]
    )


def test_has_user_fields_detects_base_only_read() -> None:
    assert has_user_fields({"m_GameObject": {}, "m_Enabled": 1, "m_Script": {}, "m_Name": ""}) is False
    assert has_user_fields({"m_Script": {}, "storyText": "Hi"}) is True


# --- AssetHarvester integration ----------------------------------------------------


class _FakeMonoBehaviour:
    class Type:
        name = "MonoBehaviour"

    type = Type()

    def __init__(self, tree: dict[str, Any] | None, raw: bytes = b"") -> None:
        self._tree = tree
        self._raw = raw

    def read_typetree(self) -> dict[str, Any]:
        if self._tree is None:
            raise ValueError("There are no TypeTree nodes for this object.")
        return self._tree

    def get_raw_data(self) -> bytes:
        return self._raw


def _prefixed(text: str) -> bytes:
    data = text.encode("utf-8")
    return struct.pack("<I", len(data)) + data + b"\x00" * ((4 - len(data) % 4) % 4)


def test_monobehaviour_prefers_typetree_over_raw_scan() -> None:
    obj = _FakeMonoBehaviour(
        {"m_Script": {}, "m_Name": "SayCommand", "storyText": "Hello traveler!"},
        raw=b"\x00" * 4 + _prefixed("SayCommand") + _prefixed("Hello traveler!"),
    )
    assert AssetHarvester.extract_strings_from_object(obj) == ["Hello traveler!"]


def test_monobehaviour_falls_back_to_raw_scan_without_typetree() -> None:
    raw = b"\x00" * 4 + _prefixed("Continue")
    assert AssetHarvester.extract_strings_from_object(_FakeMonoBehaviour(None, raw)) == ["Continue"]
    base_only = _FakeMonoBehaviour({"m_Script": {}, "m_Name": "", "m_Enabled": 1}, raw)
    assert AssetHarvester.extract_strings_from_object(base_only) == ["Continue"]


def test_foreign_string_table_yields_nothing_even_with_raw_text() -> None:
    table = {"m_Script": {}, "m_LocaleId": {"m_Code": "de"}, "m_TableData": [{"m_Localized": "Spiel"}]}
    obj = _FakeMonoBehaviour(table, raw=_prefixed("Spiel starten"))
    assert AssetHarvester.extract_strings_from_object(obj, "en") == []


def test_typetree_generator_absent_or_unknown_version(tmp_path: Path) -> None:
    profile = UnityGameProfile(game_path=tmp_path, data_dir=tmp_path, unity_version="Unknown")
    assert create_typetree_generator(profile) is None


# --- Profiler -----------------------------------------------------------------------


def test_scan_markers_finds_marker_across_chunk_boundary(tmp_path: Path, monkeypatch: Any) -> None:
    import src.core.engine_profiler as profiler

    monkeypatch.setattr(profiler, "_SCAN_CHUNK", 8)
    blob = tmp_path / "blob.bin"
    blob.write_bytes(b"xxxxxxI2.Locyyyy PixelCrushers.DialogueSystem")
    found = scan_markers(blob, (b"I2.Loc", b"PixelCrushers.DialogueSystem", b"Fungus.Say"))
    assert found == {b"I2.Loc", b"PixelCrushers.DialogueSystem"}


def test_read_metadata_header(tmp_path: Path) -> None:
    good = tmp_path / "good.dat"
    good.write_bytes(struct.pack("<II", IL2CPP_METADATA_MAGIC, 29) + b"\x00" * 64)
    assert read_metadata_header(good) == (29, False)

    encrypted = tmp_path / "enc.dat"
    encrypted.write_bytes(b"\x13\x37\xde\xad" * 32)
    assert read_metadata_header(encrypted) == (None, True)

    odd_version = tmp_path / "odd.dat"
    odd_version.write_bytes(struct.pack("<II", IL2CPP_METADATA_MAGIC, 9999) + b"\x00" * 64)
    assert read_metadata_header(odd_version) == (None, True)


def _make_game(tmp_path: Path) -> Path:
    game = tmp_path / "Game"
    data = game / "Game_Data"
    data.mkdir(parents=True)
    (game / "Game.exe").write_bytes(b"MZ")
    (game / "UnityPlayer.dll").write_bytes(b"MZ")
    return game


def test_profiler_detects_frameworks_in_mono_assemblies(tmp_path: Path) -> None:
    game = _make_game(tmp_path)
    managed = game / "Game_Data" / "Managed"
    managed.mkdir()
    (managed / "Unity.Localization.dll").write_bytes(b"MZ")
    (managed / "Assembly-CSharp-firstpass.dll").write_bytes(b"..PixelCrushers.DialogueSystem..I2.Loc..")
    (managed / "Assembly-CSharp.dll").write_bytes(b"..TMPro.TextMeshProUGUI..Ink.Runtime..")

    profile = EngineProfiler.profile_game(game)
    assert profile.has_text_mesh_pro is True
    assert set(profile.detected_frameworks) == {
        "Unity Localization", "Dialogue System", "I2 Localization", "Ink",
    }


def test_profiler_flags_encrypted_il2cpp_metadata(tmp_path: Path) -> None:
    game = _make_game(tmp_path)
    (game / "GameAssembly.dll").write_bytes(b"MZ")
    meta_dir = game / "Game_Data" / "il2cpp_data" / "Metadata"
    meta_dir.mkdir(parents=True)
    (meta_dir / "global-metadata.dat").write_bytes(b"\x00\x01\x02\x03" * 64 + b"I2.Loc")

    profile = EngineProfiler.profile_game(game)
    assert profile.is_il2cpp is True
    assert profile.metadata_encrypted is True
    assert profile.detected_frameworks == []
    assert "Route 1: Native Static Patcher" not in profile.available_routes
