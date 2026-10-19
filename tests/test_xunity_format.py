# -*- coding: utf-8 -*-
"""XUnity dictionary format: codec parity with XUnity's TextHelper and runtime-format regexes.

Expected values were cross-checked against XUnity's own C# ``TextHelper`` and
``RegexTranslation`` compiled with .NET (see CHANGELOG, 0.1.0).
"""

import re
from pathlib import Path

import pytest

from src.core.hook_layout import DICTIONARY_FILE, XUNITY_TEXT_DIRECTORY, dictionary_path
from src.core.hook_manager.font_bootstrap import FontBootstrap
from src.core.hook_manager.installer import BEPINEX_PACKAGES, AUTOTRANSLATOR_PACKAGES, bepinex_package_key
from src.core.parsers import xunity_codec
from src.core.parsers.auto_translator import REGEX_SECTION_BEGIN, REGEX_SECTION_END, AutoTranslatorParser
from src.core.parsers.xunity_regex import build_regex_entry, has_runtime_placeholders
from src.utils.downloader import RemoteFile

# --- Codec ---------------------------------------------------------------------------------


@pytest.mark.parametrize("key, value", [
    ("Visit https://example.com//x", "Ziyaret: https://example.com//x"),
    ("// slashes", "// eğik"),
    ("100%3D off", "%3D indirim"),
    ("#1 Player", "#1 Oyuncu"),
    ("C:\\path\\new", "C:\\yol\\yeni"),
    ("\\u0041 is not an escape here", "\\u0041 değil"),
    ("Line1\nLine2\r", "Satır1\nSatır2\r"),
    ("Ends with backslash\\", "Ters bölü\\"),
    ("a=b", "c=d"),
])
def test_codec_round_trip_survives_xunity_specials(key: str, value: str) -> None:
    line = xunity_codec.encode_line(key, value)
    assert "//" not in line  # XUnity treats an unescaped "//" as an inline comment
    assert not line.startswith("#")  # "#set"/"#unset" lines are directives
    assert xunity_codec.decode_line(line) == (key, value)


def test_decoder_follows_xunity_rules() -> None:
    assert xunity_codec.decode_line("Hello=Merhaba // translator note") == ("Hello", "Merhaba ")
    assert xunity_codec.decode_line("a//b=c") is None  # comment before the separator
    assert xunity_codec.decode_line("a=b=c") is None  # two separators
    assert xunity_codec.decode_line("x%3Dy=z") == ("x=y", "z")  # legacy "=" encoding
    assert xunity_codec.decode_line("\\u0041=\\u00e7") == ("A", "ç")
    assert xunity_codec.decode_line("bad\\u00zz=x") is None
    assert xunity_codec.decode_line("a\\tb=c") == ("a\\tb", "c")  # unknown escapes stay literal


def test_comment_and_directive_lines() -> None:
    assert xunity_codec.is_comment("// comment")
    assert xunity_codec.is_comment("#set level 1,2")
    assert xunity_codec.is_comment("   ")
    assert not xunity_codec.is_comment("#1 Player=#1 Oyuncu")  # XUnity loads this as a translation
    assert not xunity_codec.is_literal_key('r:"^x$"') and not xunity_codec.is_literal_key("sr:x")


# --- Runtime-format regexes -------------------------------------------------------------------

_NET_GROUP = re.compile(r"\$\{(\d+)\}")


def _apply(entry: tuple[str, str], runtime_text: str) -> str | None:
    """Apply an entry the way XUnity does (pattern/value between the outer quotes)."""
    key, value = entry
    pattern = key[key.index('"') + 1 : key.rindex('"')]
    replacement = value[value.index('"') + 1 : value.rindex('"')]
    match = re.match(pattern.replace("\\#", "#"), runtime_text)
    if not match:
        return None
    # .NET replacement syntax: ${N} groups and $$ for a literal dollar.
    parts = re.split(r"(\$\$|\$\{\d+\})", replacement)
    return "".join(
        "$" if part == "$$" else match.group(int(_NET_GROUP.match(part).group(1))) if _NET_GROUP.match(part) else part
        for part in parts
    )


@pytest.mark.parametrize("source, translation, shown, expected", [
    ("Gold: {0}", "Altın: {0}", "Gold: 150", "Altın: 150"),
    ("{0} of {1}", "{1} içinde {0}", "3 of 10", "10 içinde 3"),
    ("Hi {name}, {name}!", "Selam {name}, {name}!", "Hi Bob, Bob!", "Selam Bob, Bob!"),
    ("%s vs %s", "%s - %s", "Red vs Blue", "Red - Blue"),
    ("Cost: $5 {0}", "Fiyat: $5 {0}", "Cost: $5 now", "Fiyat: $5 now"),
    ("{{0}} literal {0}", "{{0}} sabit {0}", "{0} literal X", "{0} sabit X"),
    ('Say "{0}"', '"{0}" de', 'Say "hi"', '"hi" de'),
    ("Score {0:N0} (x{1})", "Skor {0:N0} (x{1})", "Score 1,200 (x3)", "Skor 1,200 (x3)"),
])
def test_regex_entry_translates_the_formatted_text(source: str, translation: str, shown: str, expected: str) -> None:
    entry = build_regex_entry(source, translation)
    assert entry is not None
    assert _apply(entry, shown) == expected


def test_regex_entry_is_skipped_without_placeholders_or_with_foreign_ones() -> None:
    assert not has_runtime_placeholders("Plain text {{ braces }}")
    assert build_regex_entry("Plain text", "Düz metin") is None
    assert build_regex_entry("Gold: {0}", "Altın: {1}") is None  # placeholder the source lacks


def test_dictionary_regenerates_regex_section_and_keeps_manual_lines(tmp_path: Path) -> None:
    path = tmp_path / DICTIONARY_FILE
    path.write_text('// manual\nr:"^Lv\\.(\\d+)$"="Sv.$1"\n', encoding="utf-8")
    parser = AutoTranslatorParser()
    parser.apply_translations(path, {"Gold: {0}": "Altın: {0}", 'r:"x"': "skipped"})
    parser.apply_translations(path, {"Start": "Başla"})

    lines = path.read_text(encoding="utf-8-sig").splitlines()
    assert lines[:2] == ["// manual", 'r:"^Lv\\.(\\d+)$"="Sv.$1"']  # hand-written regex kept
    assert lines.count(REGEX_SECTION_BEGIN) == 1 and lines.count(REGEX_SECTION_END) == 1
    section = lines[lines.index(REGEX_SECTION_BEGIN) + 1 : lines.index(REGEX_SECTION_END)]
    assert section == [xunity_codec.encode_line('r:"^Gold: (.*?)$"', '"Altın: ${1}"')]
    assert parser.extract_strings(path) == ["Gold: {0}", "Start"]  # regex keys are not texts
    assert not any(line.startswith('r:"x"') for line in lines)


# --- XUnity layout and packages ----------------------------------------------------------------


def test_dictionary_file_and_config_directory_are_per_language(tmp_path: Path) -> None:
    assert dictionary_path(tmp_path, "tr").name == DICTIONARY_FILE
    assert not DICTIONARY_FILE.startswith("_")  # XUnity ignores regexes in "_" files
    FontBootstrap.inject_font(tmp_path, target_lang="tr")
    ini = (tmp_path / "BepInEx" / "config" / "AutoTranslatorConfig.ini").read_text(encoding="utf-8-sig")
    assert f"Directory={XUNITY_TEXT_DIRECTORY}\n" in ini  # "Translation" alone mixes all languages


def test_bepinex_build_follows_runtime_and_metadata_version() -> None:
    assert bepinex_package_key(True, False) == "mono_x64"
    assert bepinex_package_key(False, False) == "mono_x86"
    assert bepinex_package_key(True, True, 29) == "il2cpp_x64"  # 6.0.0-pre.2 reads v23-v29
    assert bepinex_package_key(True, True, 31) == "il2cpp_modern_x64"  # late 2022.3 / Unity 6
    assert bepinex_package_key(False, True, None) == "il2cpp_modern_x86"  # unknown: widest reader
    assert "5.4.23.5" in BEPINEX_PACKAGES["mono_x64"].url
    assert all("5.6.2" in package.url for package in AUTOTRANSLATOR_PACKAGES.values())
    assert all(len(package.sha256) == 64 for package in BEPINEX_PACKAGES.values())


def test_remote_filename_is_url_decoded() -> None:
    remote = RemoteFile("https://x/764/BepInEx-Unity.IL2CPP-win-x64-6.0.0-be.764%2B5f39645.zip", "0" * 64)
    assert remote.filename == "BepInEx-Unity.IL2CPP-win-x64-6.0.0-be.764+5f39645.zip"


def test_tmp_system_font_override_is_set_cleared_or_left_alone(tmp_path: Path) -> None:
    ini = tmp_path / "BepInEx" / "config" / "AutoTranslatorConfig.ini"

    def override() -> list[str]:
        return [line for line in ini.read_text(encoding="utf-8-sig").splitlines() if line.startswith("OverrideFontTextMeshPro=")]

    FontBootstrap.inject_font(tmp_path, tmp_override_font="Arial")
    assert override() == ["OverrideFontTextMeshPro=Arial"]
    FontBootstrap.inject_font(tmp_path)  # None: e.g. hook install, the setting is not involved
    assert override() == ["OverrideFontTextMeshPro=Arial"]
    FontBootstrap.inject_font(tmp_path, tmp_override_font="")
    assert override() == ["OverrideFontTextMeshPro="]
