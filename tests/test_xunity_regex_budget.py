# -*- coding: utf-8 -*-
"""Which runtime regex entries survive the per-dictionary cap."""

import pytest

from src.core.parsers import xunity_regex as xr


@pytest.fixture
def small_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(xr, "MAX_REGEX_ENTRIES", 10)
    monkeypatch.setattr(xr, "CHOICE_ENTRY_RESERVE", 3)


def _keys(entries: list[tuple[str, str]]) -> str:
    return "\n".join(key for key, _ in entries)


def test_ui_templates_beat_library_diagnostics_beyond_the_cap(small_cap: None) -> None:
    diagnostics = [(f"The value '{{0}}' of item {n} is invalid.", f"çeviri {n}") for n in range(30)]
    ui = [("Cooldown: {0} Turns", "Bekleme: {0} Tur"), ("Strength reaches {0}", "Güç {0} değerine ulaştı")]
    kept = _keys(xr.build_regex_entries(diagnostics + ui))
    assert "Cooldown" in kept and "Strength reaches" in kept


def test_choice_entries_keep_their_reserved_slots(small_cap: None) -> None:
    templates = [(f"Template number {n} is {{0}}", f"Şablon {n} {{0}}") for n in range(30)]
    choices = [("Open the door", "Kapıyı aç"), ("Close the window", "Pencereyi kapat")]
    entries = xr.build_regex_entries(templates + choices)
    assert len(entries) == 10
    assert sum("Open the door" in key or "Close the window" in key for key, _ in entries) == 2


def test_everything_is_kept_below_the_cap() -> None:
    entries = [("Cooldown: {0} Turns", "Bekleme: {0} Tur"), ("Open the door", "Kapıyı aç")]
    assert len(xr.build_regex_entries(entries)) == 2


def test_cap_is_large_enough_for_big_games() -> None:
    assert xr.MAX_REGEX_ENTRIES >= 3000
