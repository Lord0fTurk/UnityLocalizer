# -*- coding: utf-8 -*-
"""Tests for TMP fallback font glyph coverage reporting."""

from pathlib import Path
from typing import Any


from src.core.hook_manager import glyph_coverage
from src.core.hook_manager.glyph_coverage import (
    analyze_coverage,
    codepoints_from_font_tree,
    required_codepoints,
)
from src.core.pipeline import orchestrator
from src.core.pipeline.orchestrator import UnityTranslationPipeline
from src.core.progress import ProgressEvent

def test_required_codepoints_ignore_markup_and_whitespace() -> None:
    counts = required_codepoints(["<b>Aç</b> {0}", "ç\n<sprite=1>"])
    assert counts == {ord("A"): 1, ord("ç"): 2}


def test_analyze_coverage_orders_missing_by_frequency() -> None:
    report = analyze_coverage(["ğğğ şş a"], {ord("a"), ord("ş")})
    assert report.required == 3
    assert report.missing == ["ğ"]
    assert report.missing_uses == 3
    assert report.is_complete is False

    full = analyze_coverage(["ab"], {ord("a"), ord("b")})
    assert full.is_complete is True
    assert full.sample() == ""


def test_codepoints_from_modern_and_legacy_tmp_trees() -> None:
    modern = {"m_CharacterTable": [{"m_Unicode": 65, "m_GlyphIndex": 3}, {"m_Unicode": 231}]}
    legacy = {"m_glyphInfoList": [{"id": 66, "x": 0.0}, {"id": 287}]}
    assert codepoints_from_font_tree(modern) == {65, 231}
    assert codepoints_from_font_tree(legacy) == {66, 287}
    assert codepoints_from_font_tree({"m_Name": "NotAFont"}) == set()


def test_tmp_bundle_codepoints_unreadable_file(tmp_path: Path) -> None:
    junk = tmp_path / "arialuni_sdf_u2021"
    junk.write_bytes(b"not a bundle")
    assert glyph_coverage.tmp_bundle_codepoints(junk) is None


def _run_report(monkeypatch: Any, available: set[int] | None, translations: dict[str, str]) -> list[ProgressEvent]:
    monkeypatch.setattr(orchestrator, "tmp_bundle_codepoints", lambda path: available)
    events: list[ProgressEvent] = []
    pipeline = UnityTranslationPipeline.__new__(UnityTranslationPipeline)
    pipeline.progress_callback = events.append
    pipeline._report_glyph_coverage(Path("BepInEx/font/arialuni_sdf_u2021"), translations)
    return events


def test_pipeline_reports_missing_glyphs(monkeypatch: Any) -> None:
    events = _run_report(monkeypatch, {ord("a")}, {"x": "aç"})
    assert [e.key for e in events] == ["font.coverage_missing"]
    assert events[0].params["chars"] == "ç"
    assert events[0].params["count"] == 1


def test_pipeline_reports_full_coverage(monkeypatch: Any) -> None:
    events = _run_report(monkeypatch, {ord("a"), ord("ç")}, {"x": "aç"})
    assert [e.key for e in events] == ["font.coverage_ok"]
    assert events[0].params["count"] == 2


def test_pipeline_reports_unknown_font_table(monkeypatch: Any) -> None:
    events = _run_report(monkeypatch, None, {"x": "aç"})
    assert [e.key for e in events] == ["font.coverage_unknown"]
