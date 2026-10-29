# -*- coding: utf-8 -*-
"""Script data lines are left out and only the readable words inside them are kept."""

from __future__ import annotations

import pytest

from src.core.harvesters.data_lines import readable_segments, split_data_lines
from src.core.syntax_guard import UnitySyntaxGuard

DATA_LINES = [
    'task="0|0|false|false|ActionManager|UpdateEvidence|escape*Brew a luck potion*false"',
    'line="21|1_morrigan_guest_room_igotsenthere_Sora/21|null",',
    'name="sora_theme",',
    'name="Pan Yu Doppel 2",',
    'conversation="1_Morrigan_front_DeskA",',
    'condition="bathroom_pass|false"',
    'audiofilepath="Voices/Sora/hello there.wav",',
    "itemid=58,",
    "id=168,",
    "flag=true",
]


@pytest.mark.parametrize("line", DATA_LINES)
def test_pure_data_lines_are_removed_and_leave_no_words(line: str) -> None:
    result = split_data_lines([line])
    assert result.strings == [] and result.lines_removed == 1 and result.segments_added == 0


def test_a_choice_keeps_its_text_and_loses_the_ids() -> None:
    line = 'choice="Ask about cameras|DialogueSystem|StartConversation|3_Lily_CCTV_Bedroom_Cameras|clh_cam|false|null_flag"'
    assert split_data_lines([line]).strings == ["Ask about cameras"]


def test_a_single_word_is_kept_for_a_text_key_only() -> None:
    assert readable_segments("choice", "Leave|DialogueSystem|x_y") == ["Leave"]
    assert readable_segments("displayname", "Sora") == ["Sora"]
    assert readable_segments("tag", "Leave|Stay") == []  # a data key never yields words
    assert readable_segments("mood", "Leave|Stay") == []  # an unknown key needs real words, not one-word ids


def test_unknown_keys_yield_only_sentences() -> None:
    assert readable_segments("hint", "Open the red door|door_red_2") == ["Open the red door"]


def test_ordinary_text_passes_through_unchanged_and_in_order() -> None:
    strings = ["Hello world.", "x = see you later", "[pic=3] Hi!", 'He said "yes" = no']
    result = split_data_lines(strings)
    assert result.strings == strings and result.lines_removed == 0


def test_extracted_words_are_deduplicated_and_remember_their_line() -> None:
    lines = ['choice="Ask about Wi-Fi|DialogueSystem|a_b",', 'choice="Ask about Wi-Fi|DialogueSystem|c_d",', "Ask about Wi-Fi"]
    result = split_data_lines(lines)
    assert result.strings == ["Ask about Wi-Fi"] and result.lines_removed == 2
    assert result.segments_added == 0  # the text was already a string of its own


def test_square_bracket_directives_survive_translation() -> None:
    text = "But there isn't any! Just relax!  [pic=39] and [picc=7]"
    protected, tags = UnitySyntaxGuard.protect(text)
    assert tags == ["[pic=39]", "[picc=7]"] and "pic" not in protected
    assert UnitySyntaxGuard.restore(protected.replace("But", "Ama"), tags).endswith("[pic=39] and [picc=7]")


@pytest.mark.parametrize("text", ["[b]bold[/b]", "[ff0000]red[-]", "[url=http://x]a[/url]"])
def test_ngui_tags_keep_working(text: str) -> None:
    _protected, tags = UnitySyntaxGuard.protect(text)
    assert tags and all(t.startswith("[") for t in tags)


def test_prose_in_brackets_is_not_taken_for_a_directive() -> None:
    _protected, tags = UnitySyntaxGuard.protect("[Charm] He said x = y and [Strength 5]")
    assert tags == []


class _StubManager:
    def __init__(self, config: dict[str, object] | None = None) -> None:
        self.config = config

    def get_translator(self, engine: object) -> object:
        return object()


def _pipeline(config: dict[str, object] | None) -> tuple[object, list[object]]:
    from src.core.pipeline.orchestrator import UnityTranslationPipeline

    manager = _StubManager(type("Config", (), {"get": lambda self, key, default=None: (config or {}).get(key, default)})())
    pipeline = UnityTranslationPipeline(manager)  # type: ignore[arg-type]
    events: list[object] = []
    pipeline.progress_callback = events.append
    return pipeline, events


def test_the_pipeline_replaces_data_lines_and_keeps_the_channel_label() -> None:
    from src.core.harvesters.harvest_collector import HarvestResult

    pipeline, events = _pipeline(None)
    line = 'choice="Ask about cameras|DialogueSystem|a_b",'
    harvest = HarvestResult(strings=["Hello there.", line], sources={"Hello there.": "assets", line: "assets"})
    pipeline._split_data_lines(harvest)  # type: ignore[attr-defined]
    assert harvest.strings == ["Hello there.", "Ask about cameras"]
    assert harvest.sources["Ask about cameras"] == "assets"
    assert [(e.key, e.params) for e in events] == [("pipeline.data_lines_split", {"count": 1, "words": 1})]  # type: ignore[attr-defined]


def test_the_setting_turns_the_split_off() -> None:
    from src.core.harvesters.harvest_collector import HarvestResult

    pipeline, events = _pipeline({"harvest_split_data_lines": False})
    harvest = HarvestResult(strings=['task="1|2",'])
    pipeline._split_data_lines(harvest)  # type: ignore[attr-defined]
    assert harvest.strings == ['task="1|2",'] and events == []


def test_the_first_line_of_a_multi_line_value_keeps_only_its_text() -> None:
    lines = ['description="A tiny key, too small for a door.', 'description="', 'task="1|2', 'id=5*6,', 'combineditemid=27*79,']
    assert split_data_lines(lines).strings == ["A tiny key, too small for a door."]
