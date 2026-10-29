# -*- coding: utf-8 -*-
"""Tests for the built-in and user ignore rules applied before translation."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from src.backend.settings_schema import SETTING_SPECS, coerce_setting
from src.core.harvesters.harvest_collector import HarvestResult
from src.core.harvesters.ignore_rules import ENGINE_PLACEHOLDERS, filter_ignored, parse_rules
from src.core.progress import NOTIFICATION_LEVELS


@pytest.mark.parametrize("text", ["New Text", "new text", "  NEW   TEXT ", "Button", "Option B", "Enter text..."])
def test_engine_placeholders_are_ignored_whatever_the_case(text: str) -> None:
    assert parse_rules("").matches(text)


@pytest.mark.parametrize("text", ["Play", "Button of Doom", "New Game", "Press the button", "Text speed"])
def test_real_ui_text_is_not_mistaken_for_a_placeholder(text: str) -> None:
    assert not parse_rules("").matches(text)


def test_placeholder_wrapped_in_markup_is_still_a_placeholder() -> None:
    rules = parse_rules("")
    assert rules.matches("<b>New Text</b>")
    assert rules.matches("<color=#ff0000>Button</color>")
    assert not rules.matches("<b>New Game</b>")


def test_placeholders_can_be_switched_off() -> None:
    rules = parse_rules("", engine_placeholders=False)
    assert rules.is_empty
    assert not rules.matches("New Text")


def test_exact_rule_matches_whole_text_only() -> None:
    rules = parse_rules("Lorem Ipsum", engine_placeholders=False)
    assert rules.matches("lorem   ipsum")
    assert not rules.matches("Lorem Ipsum dolor")


def test_prefix_rule_matches_the_start() -> None:
    rules = parse_rules("Debug:*", engine_placeholders=False)
    assert rules.matches("DEBUG: spawned 3 enemies")
    assert rules.matches("<b>Debug: x</b>")
    assert not rules.matches("Not a Debug: line")


def test_regex_rule_is_searched_case_insensitively() -> None:
    rules = parse_rules("re:^[0-9]+ fps$", engine_placeholders=False)
    assert rules.matches("60 FPS")
    assert not rules.matches("60 FPS limit")


def test_comments_and_blank_lines_are_skipped() -> None:
    rules = parse_rules("# note\n\n   \nTODO\n", engine_placeholders=False)
    assert rules.exact == frozenset({"todo"})
    assert not rules.matches("# note")


def test_invalid_regex_is_reported_and_other_rules_still_work(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        rules = parse_rules("re:([unclosed\nTODO", engine_placeholders=False)
    assert "invalid ignore rule" in caplog.text
    assert rules.matches("todo") and not rules.patterns


def test_bare_star_never_matches_everything(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        rules = parse_rules("*\n  *  ", engine_placeholders=False)
    assert rules.is_empty and not rules.matches("Anything")
    assert "without text" in caplog.text


def test_blank_strings_are_never_ignored() -> None:
    rules = parse_rules("TODO\nre:.*")
    assert not rules.matches("   ")
    assert not rules.matches("")


def test_filter_ignored_counts_removed_strings() -> None:
    result = filter_ignored(iter(["Play", "New Text", "Quit", "Button"]), parse_rules(""))
    assert result.kept == ["Play", "Quit"] and result.removed == 2


def test_filter_ignored_with_no_rules_keeps_everything() -> None:
    result = filter_ignored(["a", "b"], parse_rules("", engine_placeholders=False))
    assert result.kept == ["a", "b"] and result.removed == 0


def test_every_builtin_placeholder_is_stored_normalized() -> None:
    assert all(p == " ".join(p.split()).casefold() for p in ENGINE_PLACEHOLDERS)


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


def _pipeline(config: _Config | None = None) -> tuple[Any, list[Any]]:
    from src.core.pipeline.orchestrator import UnityTranslationPipeline

    pipeline = UnityTranslationPipeline(_Manager(config))  # type: ignore[arg-type]
    events: list[Any] = []
    pipeline.progress_callback = events.append
    return pipeline, events


def test_pipeline_drops_ignored_texts_and_says_so() -> None:
    pipeline, events = _pipeline(_Config({"ignore_rules": "Debug:*", "ignore_engine_placeholders": True}))
    harvest = HarvestResult(strings=["Play", "New Text", "Debug: x", "Quit"])
    pipeline._drop_ignored(harvest, pipeline._ignore_rules())
    assert harvest.strings == ["Play", "Quit"] and pipeline.last_harvest_count == 2
    assert events[-1].key == "pipeline.ignored_text_removed" and events[-1].params["count"] == 2


def test_pipeline_stays_silent_when_nothing_matches() -> None:
    pipeline, events = _pipeline(_Config({"ignore_rules": "", "ignore_engine_placeholders": True}))
    harvest = HarvestResult(strings=["Play", "Quit"])
    pipeline._drop_ignored(harvest, pipeline._ignore_rules())
    assert harvest.strings == ["Play", "Quit"] and not events


def test_pipeline_honours_the_placeholder_switch() -> None:
    pipeline, _ = _pipeline(_Config({"ignore_rules": "", "ignore_engine_placeholders": False}))
    assert pipeline._ignore_rules().is_empty


def test_pipeline_without_a_config_ignores_nothing() -> None:
    pipeline, _ = _pipeline()
    assert pipeline._ignore_rules().is_empty


def test_ignore_event_is_a_notification() -> None:
    assert NOTIFICATION_LEVELS["pipeline.ignored_text_removed"] == "info"


def test_ignore_settings_are_typed_in_the_schema() -> None:
    assert SETTING_SPECS["ignore_rules"].kind is str
    assert SETTING_SPECS["ignore_engine_placeholders"].kind is bool
    assert coerce_setting("ignore_engine_placeholders", "off") is False
    assert coerce_setting("ignore_rules", "a\nb") == "a\nb"


@pytest.mark.parametrize("rule", ["re:", "re:.*", "re:|foo", "re:x*"])
def test_regex_matching_empty_text_is_refused(rule: str) -> None:
    rules = parse_rules(rule, engine_placeholders=False)
    assert rules.is_empty
    assert not rules.matches("Hello")


@pytest.mark.parametrize("rule", ["re:(a+)+$", "re:(a*)*b", "re:((ab)+c?)*d"])
def test_nested_unbounded_repeat_is_refused(rule: str) -> None:
    assert parse_rules(rule, engine_placeholders=False).is_empty


def test_bounded_and_flat_repeats_stay_allowed() -> None:
    rules = parse_rules("re:^\\d+ FPS$\nre:(ab){1,3}x", engine_placeholders=False)
    assert rules.matches("60 FPS") and rules.matches("ababx")


def test_re_prefix_is_lowercase_only() -> None:
    rules = parse_rules("Re: Hello", engine_placeholders=False)
    assert rules.matches("re: hello") and not rules.matches("Say Hello")


def test_regex_only_sees_the_start_of_a_long_string() -> None:
    rules = parse_rules("re:needle", engine_placeholders=False)
    assert not rules.matches("x" * 2000 + "needle")
