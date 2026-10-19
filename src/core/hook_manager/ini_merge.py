# -*- coding: utf-8 -*-
"""Line-preserving INI merge for XUnity's AutoTranslatorConfig.ini.

XUnity keeps dozens of user-tunable options in this file. Rewriting it wholesale
would wipe the user's (or another tool's) choices on every run, so only the keys
UnityLocalizer manages are touched:

* ``forced`` keys are always set (offline endpoint, languages, dictionary paths);
* ``defaults`` are written only when the key is missing (layout-safe behaviour).

Comments, ordering, unknown sections/keys and the file's line endings are preserved.
"""

from __future__ import annotations

import re

IniValues = dict[str, dict[str, str]]

_SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
_KEY_RE = re.compile(r"^\s*([^=;#\s][^=]*?)\s*=")


def _pending(forced: IniValues, defaults: IniValues) -> dict[str, dict[str, tuple[str, str, bool]]]:
    """section(lower) -> key(lower) -> (key, value, is_forced) still to be written."""
    pending: dict[str, dict[str, tuple[str, str, bool]]] = {}
    for values, is_forced in ((defaults, False), (forced, True)):
        for section, keys in values.items():
            bucket = pending.setdefault(section.lower(), {})
            for key, value in keys.items():
                bucket[key.lower()] = (key, value, is_forced)
    return pending


def _flush(lines: list[str], pending: dict[str, tuple[str, str, bool]]) -> None:
    """Append the section's keys that were not found, before its trailing blank lines."""
    insert_at = len(lines)
    while insert_at > 0 and not lines[insert_at - 1].strip():
        insert_at -= 1
    lines[insert_at:insert_at] = [f"{key}={value}" for key, value, _ in pending.values()]
    pending.clear()


def _coalesce_sections(lines: list[str]) -> list[str]:
    """Merge lines from repeated [Section] headers into the first occurrence of that section."""
    preamble: list[str] = []
    order: list[str] = []
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        header = _SECTION_RE.match(line)
        if header:
            sec = header.group(1).strip().lower()
            current = sec
            if sec not in blocks:
                order.append(sec)
                blocks[sec] = [line]
            continue
        if current is None:
            preamble.append(line)
        else:
            block = blocks[current]
            insert_at = len(block)
            while insert_at > 1 and not block[insert_at - 1].strip():
                insert_at -= 1
            block.insert(insert_at, line)
    return preamble + [line for sec in order for line in blocks[sec]]


def merge_ini(existing: str, forced: IniValues, defaults: IniValues) -> str:
    """Return ``existing`` with forced keys set and missing default keys added."""
    newline = "\r\n" if "\r\n" in existing else "\n"
    pending = _pending(forced, defaults)
    managed = {sec: set(bucket) for sec, bucket in pending.items()}
    section_names = {section.lower(): section for section in (*defaults, *forced)}
    out: list[str] = []
    current: str | None = None
    for line in _coalesce_sections(existing.splitlines()):
        header = _SECTION_RE.match(line)
        if header:
            if current in pending:
                _flush(out, pending.pop(current))
            current = header.group(1).strip().lower()
        else:
            key = _KEY_RE.match(line)
            key_lower = key.group(1).strip().lower() if key and current else None
            if key_lower is not None and current in managed and key_lower in managed[current]:
                entry = pending.get(current, {}).pop(key_lower, None)
                if entry is None:
                    continue
                line = f"{entry[0]}={entry[1]}" if entry[2] else line
        out.append(line)
    if current in pending:
        _flush(out, pending.pop(current))
    for section, keys in pending.items():
        if out and out[-1].strip():
            out.append("")
        out.append(f"[{section_names[section]}]")
        _flush(out, keys)
    return newline.join(out) + newline
