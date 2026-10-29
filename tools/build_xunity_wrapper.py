# -*- coding: utf-8 -*-
"""Builds the delayed-start XUnity wrapper (``src/core/hook_manager/xunity_wrapper``).

The DLL is compiled with the Roslyn compiler of the .NET SDK against the assemblies of a game that has
BepInEx 5 and XUnity.AutoTranslator 5.6.2 installed (its ``<Game>_Data/Managed`` folder for ``mscorlib``
and ``UnityEngine``, ``BepInEx/core/BepInEx.dll`` and ``BepInEx/plugins/XUnity.AutoTranslator``).

    python tools/build_xunity_wrapper.py --game-dir "D:/Games/Some Unity Game"

It prints the SHA256 of the result; put that value into ``WRAPPER_SHA256`` in
``src/core/hook_manager/delayed_start.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WRAPPER_DIR = ROOT / "src" / "core" / "hook_manager" / "xunity_wrapper"
SOURCE = WRAPPER_DIR / "DelayedStart.cs"
OUTPUT_NAME = "XUnity.AutoTranslator.Plugin.BepInEx.dll"


def find_csc() -> Path:
    """Roslyn's ``csc.dll`` from the newest installed .NET SDK."""
    program_files = Path("C:/Program Files/dotnet/sdk")
    candidates = sorted(program_files.glob("*/Roslyn/bincore/csc.dll")) if program_files.is_dir() else []
    if not candidates:
        raise FileNotFoundError("csc.dll not found: install the .NET SDK or pass --csc")
    return candidates[-1]


def references(game_dir: Path) -> list[Path]:
    managed = next(game_dir.glob("*_Data/Managed"))
    plugin = game_dir / "BepInEx" / "plugins" / "XUnity.AutoTranslator"
    return [
        managed / "mscorlib.dll", managed / "System.dll", managed / "System.Core.dll", managed / "netstandard.dll",
        managed / "UnityEngine.dll", managed / "UnityEngine.CoreModule.dll",
        game_dir / "BepInEx" / "core" / "BepInEx.dll",
        plugin / "XUnity.AutoTranslator.Plugin.Core.dll", plugin / "ExIni.dll",
    ]


def build(game_dir: Path, output: Path, csc: Path) -> str:
    """Compile the wrapper and return the SHA256 of the DLL."""
    refs = references(game_dir)
    missing = [str(path) for path in refs if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing reference assemblies:\n  " + "\n  ".join(missing))
    command = ["dotnet", str(csc), "-nologo", "-nostdlib+", "-target:library", "-optimize+", "-deterministic+",
               f"-out:{output}", *[f"-r:{path}" for path in refs], str(SOURCE)]
    subprocess.run(command, check=True)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the delayed-start XUnity wrapper DLL.")
    parser.add_argument("--game-dir", required=True, type=Path, help="a game with BepInEx 5 + XUnity 5.6.2 installed")
    parser.add_argument("--output", type=Path, default=WRAPPER_DIR / OUTPUT_NAME)
    parser.add_argument("--csc", type=Path, default=None, help="path to Roslyn's csc.dll")
    args = parser.parse_args()
    digest = build(args.game_dir, args.output, args.csc or find_csc())
    print(f"built {args.output}\nSHA256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
