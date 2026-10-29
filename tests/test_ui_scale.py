# -*- coding: utf-8 -*-
"""Tests for the interface-size setting (QT_SCALE_FACTOR exported before Qt starts)."""

import json
from pathlib import Path

import pytest

from src.backend.settings_schema import coerce_setting
from src.utils.config import DEFAULT_CONFIG
from src.utils.ui_scale import DEFAULT_UI_SCALE, UI_SCALE_CHOICES, apply_ui_scale, scale_factor


def _config(tmp_path: Path, **values: object) -> Path:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    return path


@pytest.mark.parametrize(("stored", "factor"), [("100", 1.0), ("115", 1.15), ("150", 1.5), (" 130 ", 1.3), (150, 1.5)])
def test_scale_factor_accepts_the_offered_percentages(stored: object, factor: float) -> None:
    assert scale_factor(stored) == pytest.approx(factor)


@pytest.mark.parametrize("stored", ["", "abc", "90", "400", None, "1.5"])
def test_scale_factor_falls_back_to_normal_size(stored: object) -> None:
    assert scale_factor(stored) == 1.0


def test_apply_exports_the_saved_factor(tmp_path: Path) -> None:
    env: dict[str, str] = {}
    assert apply_ui_scale(_config(tmp_path, ui_scale="130"), env) == pytest.approx(1.3)
    assert env["QT_SCALE_FACTOR"] == "1.3"


def test_apply_leaves_the_environment_alone_at_normal_size(tmp_path: Path) -> None:
    env: dict[str, str] = {}
    assert apply_ui_scale(_config(tmp_path, ui_scale="100"), env) == 1.0
    assert "QT_SCALE_FACTOR" not in env


def test_apply_ignores_a_corrupt_saved_value(tmp_path: Path) -> None:
    env: dict[str, str] = {}
    assert apply_ui_scale(_config(tmp_path, ui_scale="huge"), env) == 1.0
    assert "QT_SCALE_FACTOR" not in env


def test_environment_variable_set_by_the_user_wins(tmp_path: Path) -> None:
    env = {"QT_SCALE_FACTOR": "2"}
    assert apply_ui_scale(_config(tmp_path, ui_scale="130"), env) == 2.0
    assert env["QT_SCALE_FACTOR"] == "2"


def test_setting_schema_only_takes_the_offered_values() -> None:
    assert DEFAULT_CONFIG["ui_scale"] == DEFAULT_UI_SCALE
    for choice in UI_SCALE_CHOICES:
        assert coerce_setting("ui_scale", choice) == choice
    with pytest.raises(ValueError):
        coerce_setting("ui_scale", "400")
