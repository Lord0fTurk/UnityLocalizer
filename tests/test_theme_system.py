# -*- coding: utf-8 -*-
"""Unit tests for Universal Multi-Theme & Accent Preset system."""

from pathlib import Path
import pytest

from src.backend.settings_schema import coerce_setting, SETTING_SPECS
from src.utils.config import DEFAULT_CONFIG, ConfigManager

ROOT = Path(__file__).resolve().parent.parent


def test_theme_settings_schema_constraints() -> None:
    """Verify theme_mode and accent_preset choices are strictly enforced."""
    assert "theme_mode" in SETTING_SPECS
    assert set(SETTING_SPECS["theme_mode"].choices) == {"obsidian", "daylight", "cyber_neon"}
    assert "accent_preset" in SETTING_SPECS
    assert set(SETTING_SPECS["accent_preset"].choices) == {"cyan", "emerald", "indigo", "amber"}

    # Valid values
    assert coerce_setting("theme_mode", "obsidian") == "obsidian"
    assert coerce_setting("theme_mode", "daylight") == "daylight"
    assert coerce_setting("theme_mode", "cyber_neon") == "cyber_neon"

    assert coerce_setting("accent_preset", "cyan") == "cyan"
    assert coerce_setting("accent_preset", "emerald") == "emerald"
    assert coerce_setting("accent_preset", "indigo") == "indigo"
    assert coerce_setting("accent_preset", "amber") == "amber"

    # Invalid values must raise ValueError
    with pytest.raises(ValueError):
        coerce_setting("theme_mode", "invalid_theme")

    with pytest.raises(ValueError):
        coerce_setting("accent_preset", "neon_pink")


def test_default_config_theme_values(tmp_path: Path) -> None:
    """Verify default config provides obsidian and cyan presets."""
    assert DEFAULT_CONFIG["theme_mode"] == "obsidian"
    assert DEFAULT_CONFIG["accent_preset"] == "cyan"

    cfg = ConfigManager(tmp_path / "config.json")
    assert cfg.get("theme_mode") == "obsidian"
    assert cfg.get("accent_preset") == "cyan"


def test_theme_qml_singleton_registered() -> None:
    """Verify Theme singleton and archetypes are registered in qmldir."""
    qmldir_path = ROOT / "src" / "gui" / "qml" / "components" / "qmldir"
    assert qmldir_path.exists()
    content = qmldir_path.read_text(encoding="utf-8")
    assert "singleton Theme 1.0 Theme.qml" in content
    assert "PrimaryButton 1.0 PrimaryButton.qml" in content
    assert "SecondaryButton 1.0 SecondaryButton.qml" in content
    assert "SegmentedToggle 1.0 SegmentedToggle.qml" in content
    assert "SectionCard 1.0 SectionCard.qml" in content
    assert "QuickTag 1.0 QuickTag.qml" in content
