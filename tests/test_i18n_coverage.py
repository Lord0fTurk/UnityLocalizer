# -*- coding: utf-8 -*-
"""Guards the zero-hardcoded-text rule: every UI string comes from src/gui/i18n/*.json."""

import json
import re
from pathlib import Path

import pytest

from src.backend.settings_schema import SETTING_SPECS

ROOT = Path(__file__).resolve().parent.parent
QML_FILES = sorted((ROOT / "src" / "gui" / "qml").rglob("*.qml"))
LOCALE_FILES = sorted((ROOT / "src" / "gui" / "i18n").glob("*.json"))

_STRING = r'"((?:[^"\\]|\\.)*)"'
_I18N_CALL = re.compile(r'(?:localeManager\.t|root\.tr|root\.t)\("([\w.]+)"\)')
_WORD = re.compile(r"[^\W\d_]{3,}")
_SKIP_LINE = re.compile(r'^\s*(import |id:|objectName:|//)')
# Literals that are not translatable prose: brand, technical identifiers, placeholders.
_ALLOWED = {
    "UnityLocalizer", "auto", "code", "name", "id", "level", "info", "success", "warning", "error",
    "AIzaSy...", "sk-...", "gemini-2.5-flash", "gpt-4o-mini", "qwen2.5:latest", "Arial",
    "http://localhost:11434", "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:fx",
    "rejected", "invalid", "failed", "edited", "accepted", "unchanged", "repaired",
    "ALL", "INFO", "SUCCESS", "WARNING", "WARN", "ERROR",
    "Consolas, 'Cascadia Code', monospace", "english", "native",
}
# Keys composed at runtime ("prefix" + value) in QML or the backend.
_DYNAMIC_KEYS = [
    *(f"editor.status_{s}" for s in ("accepted", "repaired", "edited", "rejected", "invalid", "failed", "unchanged")),
    *(f"editor.issue_{c}" for c in ("leaked", "missing", "unexpected")),
    *(f"engines.{e}" for e in ("google", "bing", "deepl", "gemini", "openai", "deepseek", "local_llm")),
    *(f"console.filter_{lvl}" for lvl in ("info", "success", "warn", "error")),
    *(f"settings.formality_{f}" for f in ("default", "more", "less")),
    *(f"settings.safety_{s}" for s in ("BLOCK_NONE", "BLOCK_ONLY_HIGH", "BLOCK_MEDIUM_AND_ABOVE", "BLOCK_LOW_AND_ABOVE")),
    "engines.libretranslate", "engines.pseudo",
    # PatchExporter.preflight() problems, shown by AppBackend.exportPatchPackage.
    "dashboard.patch_no_hook", "dashboard.patch_no_translations", "dashboard.patch_il2cpp_first_run",
]
# AboutView technology list: product names, not translatable prose.
_TECH_NAMES = {
    "Python 3.10+", "PyQt6", "Qt Quick (QML)", "UnityPy", "IL2CPP Metadata", "BepInEx 5/6",
    "Google Translate", "DeepL", "Google Gemini", "OpenAI GPT-4o", "DeepSeek V3", "Ollama / LM Studio",
}
_PLACEHOLDER = re.compile(r"\{\w+\}")
# Technical values: config keys and their allowed choice codes come from the settings schema.
_TECHNICAL = set(SETTING_SPECS) | {c for spec in SETTING_SPECS.values() for c in spec.choices}
_EXAMPLE_VALUE = re.compile(r"^(https?://|socks5://)|^[\w.-]+-chat$|^\w+ / [\w /]+\(\*\.\w+")


def _qml_literals(path: Path) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if _SKIP_LINE.search(line):
            continue
        code = _I18N_CALL.sub("T()", line)
        for literal in re.findall(_STRING, code):
            if literal in _ALLOWED or literal in _TECH_NAMES or literal in _TECHNICAL or _EXAMPLE_VALUE.search(literal) \
                    or literal.startswith(("#", "../", "views", "components")):
                continue
            prose = _PLACEHOLDER.sub("", literal).replace("UnityLocalizer", "")
            if prose.strip(" —-()v") == "" or literal in ("transparent", "warn"):
                continue  # placeholders, brand name, colors and log-level identifiers
            if literal.startswith(("dashboard.", "settings.", "editor.", "console.", "toolbox.", "nav.")):
                continue  # dynamic key prefixes such as "editor.status_" + status
            if _WORD.search(literal):
                found.append((number, literal))
    return found


def _qml_keys() -> set[str]:
    keys: set[str] = set()
    for path in QML_FILES:
        keys.update(_I18N_CALL.findall(path.read_text(encoding="utf-8")))
    return keys


def _has_key(data: dict, key: str) -> bool:
    section, _, name = key.partition(".")
    return isinstance(data.get(section), dict) and name in data[section]


@pytest.mark.parametrize("path", QML_FILES, ids=lambda p: p.name)
def test_qml_has_no_hardcoded_text(path: Path) -> None:
    assert _qml_literals(path) == []


@pytest.mark.parametrize("locale_file", LOCALE_FILES, ids=lambda p: p.stem)
def test_every_ui_key_exists_in_every_locale(locale_file: Path) -> None:
    data = json.loads(locale_file.read_text(encoding="utf-8"))
    missing = sorted(k for k in _qml_keys() | set(_DYNAMIC_KEYS) if not _has_key(data, k))
    assert missing == []


_BACKEND_FILES = sorted((ROOT / "src" / "backend").glob("*.py"))
_BACKEND_KEY = re.compile(
    r'(?:add_log|_set_status|_translate_text|_notify|_t|emit)\(\s*(?:"(?:info|success|warning|error)"\s*,\s*)?"([a-z_]+\.[a-z_0-9]+)"'
)


def test_backend_messages_use_existing_keys() -> None:
    """Strings the backend logs, toasts or shows as status must be i18n keys present everywhere."""
    keys = {k for path in _BACKEND_FILES for k in _BACKEND_KEY.findall(path.read_text(encoding="utf-8"))}
    assert len(keys) > 20
    for locale_file in LOCALE_FILES:
        data = json.loads(locale_file.read_text(encoding="utf-8"))
        assert sorted(k for k in keys if not _has_key(data, k)) == [], locale_file.name


def test_all_locales_share_the_same_keys() -> None:
    def flatten(data: dict, prefix: str = "") -> set[str]:
        keys: set[str] = set()
        for key, value in data.items():
            keys |= flatten(value, f"{prefix}{key}.") if isinstance(value, dict) else {f"{prefix}{key}"}
        return keys

    reference = flatten(json.loads((ROOT / "src" / "gui" / "i18n" / "en.json").read_text(encoding="utf-8")))
    for locale_file in LOCALE_FILES:
        keys = flatten(json.loads(locale_file.read_text(encoding="utf-8")))
        assert keys == reference, f"{locale_file.name}: {sorted(keys ^ reference)[:10]}"


_CORE_FILES = sorted((ROOT / "src" / "core").rglob("*.py"))
_CORE_EMIT = re.compile(r'emit\(\s*[\w.]+\s*,\s*"([a-z_]+\.[a-z_0-9]+)"')


def test_core_progress_events_use_existing_keys() -> None:
    """Progress keys emitted by core services are shown verbatim when a locale lacks them."""
    keys = {k for path in _CORE_FILES for k in _CORE_EMIT.findall(path.read_text(encoding="utf-8"))}
    assert {"pipeline.translation_plan", "pipeline.harvest_asset_file", "installer.done"} <= keys
    for locale_file in LOCALE_FILES:
        data = json.loads(locale_file.read_text(encoding="utf-8"))
        assert sorted(k for k in keys if not _has_key(data, k)) == [], locale_file.name
