# -*- coding: utf-8 -*-
"""File discovery, extra loose formats and CJK single-character labels."""

from pathlib import Path

from src.core.engine_profiler import EngineProfiler
from src.core.harvesters.asset_harvester import AssetHarvester
from src.core.harvesters.bundle_locator import find_serialized_sources
from src.core.harvesters.harvest_collector import HarvestCollector
from src.core.harvesters.text_filter import is_code_literal_text
from src.core.parsers.streaming_assets import StreamingAssetsParser
from src.core.parsers.subtitle_resx import resx_strings, srt_strings, translate_resx, translate_srt

SRT = "1\n00:00:01,000 --> 00:00:03,000\nHello there.\nHow are you?\n\n2\n00:00:04,000 --> 00:00:05,000\nGoodbye.\n"
RESX = (
    '<root><resheader name="mimetype"><value>text/microsoft-resx</value></resheader>'
    '<data name="Start" xml:space="preserve"><value>Start game</value></data>'
    '<data name="Icon" type="System.Byte[]"><value>AAAA</value></data></root>'
)


def _names(paths: list[Path]) -> list[str]:
    return [p.name for p in paths]


def test_locator_finds_main_data_and_only_the_first_split_part(tmp_path: Path) -> None:
    # The locator also looks around the data folder (next to the game), so it gets a folder of its own:
    # tmp_path's parent is shared with the bundles other tests write.
    data = tmp_path / "Game_Data"
    data.mkdir()
    for name in ("mainData", "level0.split0", "level0.split1", "level0.split2", "sharedassets0.assets", "notes.txt"):
        (data / name).write_bytes(b"x")
    assert _names(find_serialized_sources(data)) == ["level0.split0", "mainData", "sharedassets0.assets"]


def test_locator_finds_bundles_outside_streaming_assets(tmp_path: Path) -> None:
    data = tmp_path / "Game_Data"
    (data / "AssetBundles").mkdir(parents=True)
    (tmp_path / "DLC").mkdir()
    (tmp_path / "BepInEx" / "cache").mkdir(parents=True)
    magic = b"UnityFS\x00" + b"\x00" * 16
    (data / "AssetBundles" / "ui.bundle").write_bytes(magic)
    (tmp_path / "DLC" / "story.unity3d").write_bytes(magic)
    (tmp_path / "DLC" / "fake.bundle").write_bytes(b"not a bundle")
    (tmp_path / "BepInEx" / "cache" / "skip.bundle").write_bytes(magic)
    assert sorted(_names(find_serialized_sources(data))) == ["story.unity3d", "ui.bundle"]


def test_srt_round_trip_keeps_timing_and_numbering() -> None:
    assert srt_strings(SRT) == ["Hello there.\nHow are you?", "Goodbye."]
    out = translate_srt(SRT, {"Goodbye.": "Hoşça kal.", "Hello there.\nHow are you?": "Merhaba.\nNasılsın?"})
    assert "00:00:01,000 --> 00:00:03,000\nMerhaba.\nNasılsın?" in out
    assert out.startswith("1\n") and "2\n00:00:04,000 --> 00:00:05,000\nHoşça kal." in out
    assert out.endswith("\n")


def test_resx_skips_headers_and_binary_entries() -> None:
    assert resx_strings(RESX) == ["Start game"]
    out = translate_resx(RESX, {"Start game": "Oyunu başlat & git"})
    assert "<value>Oyunu başlat &amp; git</value>" in out and "AAAA" in out and "text/microsoft-resx" in out


def test_loose_srt_files_are_harvested_and_patched(tmp_path: Path) -> None:
    path = tmp_path / "intro.srt"
    path.write_text(SRT, encoding="utf-8")
    parser = StreamingAssetsParser(target_lang="tr")
    assert parser.extract_strings(path) == ["Hello there.\nHow are you?", "Goodbye."]
    assert parser.apply_translations(path, {"Goodbye.": "Hoşça kal."})
    assert "Hoşça kal." in path.read_text(encoding="utf-8")


def test_single_cjk_labels_are_kept_but_single_latin_letters_are_not() -> None:
    assert AssetHarvester.is_translatable("是") and AssetHarvester.is_translatable("戻")
    assert not AssetHarvester.is_translatable("X") and not AssetHarvester.is_translatable("。")
    assert is_code_literal_text("確") and not is_code_literal_text("Q")


def _game(tmp_path: Path) -> Path:
    game = tmp_path / "Game"
    (game / "Game_Data").mkdir(parents=True)
    (game / "Game.exe").write_bytes(b"MZ")
    (game / "UnityPlayer.dll").write_bytes(b"MZ")
    return game


def test_localization_folders_are_read_but_never_patched(tmp_path: Path) -> None:
    game = _game(tmp_path)
    (game / "Localization").mkdir()
    (game / "Localization" / "en.json").write_text('{"menu": "Start the adventure"}', encoding="utf-8")
    (game / "Localization" / "README.txt").write_text("Please do not translate this readme text", encoding="utf-8")
    (game / "Textures").mkdir()
    (game / "Textures" / "atlas.json").write_text('{"name": "Texture atlas file"}', encoding="utf-8")
    (game / "Config").mkdir()
    (game / "Config" / "settings.json").write_text('{"title": "Not a localization folder"}', encoding="utf-8")

    result = HarvestCollector().collect(EngineProfiler.profile_game(game))
    assert "Start the adventure" in result.strings
    assert not any("readme" in s.lower() or "atlas" in s.lower() or "Not a localization" in s for s in result.strings)
    assert result.streaming_files == []  # harvest-only: nothing here is rewritten in place
    assert result.per_channel["localization"] >= 1
