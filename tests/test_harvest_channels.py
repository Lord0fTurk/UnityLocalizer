# -*- coding: utf-8 -*-
"""Switching harvest channels off keeps their strings out of the translation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.backend.settings_schema import SETTING_SPECS, coerce_setting
from src.core.engine_profiler import EngineProfiler
from src.core.harvesters.harvest_collector import CHANNELS, HarvestCollector
from src.utils.config import DEFAULT_CONFIG


def _game(tmp_path: Path) -> Path:
    game = tmp_path / "Game"
    (game / "Game_Data" / "StreamingAssets").mkdir(parents=True)
    (game / "Game.exe").write_bytes(b"MZ")
    (game / "UnityPlayer.dll").write_bytes(b"MZ")
    (game / "Game_Data" / "StreamingAssets" / "menu.json").write_text(
        '{"start": "Start the adventure"}', encoding="utf-8"
    )
    (game / "Localization").mkdir()
    (game / "Localization" / "en.json").write_text('{"quit": "Leave the village"}', encoding="utf-8")
    return game


def _collect(game: Path, **kwargs: Any) -> Any:
    return HarvestCollector(**kwargs).collect(EngineProfiler.profile_game(game))


def test_every_channel_is_read_by_default(tmp_path: Path) -> None:
    result = _collect(_game(tmp_path))
    assert {"Start the adventure", "Leave the village"} <= set(result.strings)
    assert len(result.streaming_files) == 1


def test_skipping_streaming_drops_its_strings_and_files(tmp_path: Path) -> None:
    result = _collect(_game(tmp_path), skip_channels={"streaming"})
    assert "Start the adventure" not in result.strings and "Leave the village" in result.strings
    assert result.streaming_files == [] and result.per_channel["streaming"] == 0


def test_skipping_localization_drops_only_that_folder(tmp_path: Path) -> None:
    result = _collect(_game(tmp_path), skip_channels=["localization"])
    assert "Leave the village" not in result.strings and "Start the adventure" in result.strings
    assert result.per_channel["localization"] == 0


def test_skipping_every_channel_harvests_nothing(tmp_path: Path) -> None:
    result = _collect(_game(tmp_path), skip_channels=CHANNELS)
    assert result.strings == [] and result.streaming_files == []
    assert set(result.per_channel) == set(CHANNELS) and not any(result.per_channel.values())


def test_skipped_channels_report_no_progress(tmp_path: Path) -> None:
    events: list[Any] = []
    _collect(_game(tmp_path), progress=events.append, skip_channels={"assets", "code"})
    keys = [e.key for e in events]
    assert "pipeline.harvest_assets" not in keys and "pipeline.harvest_code" not in keys
    assert "pipeline.harvest_streaming" in keys and keys[-1] == "pipeline.harvest_done"


def test_unknown_channel_is_a_programming_error() -> None:
    with pytest.raises(ValueError, match="Unknown harvest channel"):
        HarvestCollector(skip_channels={"cheats"})


@pytest.mark.parametrize("skipped, expected", [((), True), (("code",), False)])
def test_encrypted_code_warning_only_when_code_is_read(tmp_path: Path, skipped: tuple[str, ...], expected: bool) -> None:
    profile = SimpleNamespace(game_path=tmp_path, data_dir=None, is_il2cpp=True, metadata_encrypted=True)
    result = HarvestCollector(skip_channels=skipped).collect(profile)  # type: ignore[arg-type]
    assert result.stats.encrypted_code is expected


class _Config:
    def __init__(self, values: dict[str, Any]) -> None:
        self.values = values

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)


class _Manager:
    def __init__(self, config: _Config | None = None) -> None:
        if config is not None:
            self.config = config

    def get_translator(self, engine: object) -> object:
        return object()


def _pipeline(config: _Config | None = None) -> Any:
    from src.core.pipeline.orchestrator import UnityTranslationPipeline

    return UnityTranslationPipeline(_Manager(config))  # type: ignore[arg-type]


def test_pipeline_reads_the_channel_switches_from_settings() -> None:
    pipeline = _pipeline(_Config({"harvest_code": False, "harvest_streaming": False, "harvest_assets": True}))
    assert pipeline._skipped_channels() == frozenset({"code", "streaming"})


def test_pipeline_reads_everything_without_a_config_or_values() -> None:
    assert _pipeline()._skipped_channels() == frozenset()
    assert _pipeline(_Config({}))._skipped_channels() == frozenset()


def test_pipeline_hands_the_switches_to_the_collector() -> None:
    pipeline = _pipeline(_Config({"harvest_code": False}))
    collector = pipeline._collector("ja")
    assert collector.source_lang == "ja" and collector.skip_channels == frozenset({"code"})


@pytest.mark.parametrize("name", CHANNELS)
def test_channel_switches_are_typed_settings_on_by_default(name: str) -> None:
    key = f"harvest_{name}"
    assert SETTING_SPECS[key].kind is bool and DEFAULT_CONFIG[key] is True
    assert coerce_setting(key, "false") is False
