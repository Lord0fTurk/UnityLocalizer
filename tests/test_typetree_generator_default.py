# -*- coding: utf-8 -*-
"""TypeTreeGeneratorAPI as a default dependency: quiet native output, honest fallbacks, packaging."""

from __future__ import annotations

import contextlib
import importlib.util
import logging
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from src.core.engine_profiler import UnityGameProfile
from src.core.harvesters import asset_harvester, typetree_provider
from src.core.harvesters.asset_harvester import AssetHarvester
from src.utils import native_output
from src.utils.native_output import discard_native_stdout
from src.utils.self_check import CHECKS

ROOT = Path(__file__).resolve().parent.parent


# --- native output --------------------------------------------------------------------


class _FakeDiscard:
    """Stands in for the platform redirect so the counting logic can be tested anywhere."""

    def __init__(self) -> None:
        self.begun = 0
        self.restored = 0

    def begin(self) -> Any:
        self.begun += 1

        def restore() -> None:
            self.restored += 1

        return restore


@pytest.fixture
def fake_discard(monkeypatch: pytest.MonkeyPatch) -> _FakeDiscard:
    fake = _FakeDiscard()
    monkeypatch.setattr(native_output, "_begin_discard", fake.begin)
    return fake


def test_the_redirect_is_made_once_and_undone_once(fake_discard: _FakeDiscard) -> None:
    with discard_native_stdout():
        assert (fake_discard.begun, fake_discard.restored) == (1, 0)
    assert (fake_discard.begun, fake_discard.restored) == (1, 1)
    assert native_output._depth == 0 and native_output._restore is None


def test_nested_blocks_share_one_redirect(fake_discard: _FakeDiscard) -> None:
    with discard_native_stdout():
        with discard_native_stdout():
            pass
        assert fake_discard.restored == 0  # the inner block must not undo the outer one
    assert (fake_discard.begun, fake_discard.restored) == (1, 1)


def test_the_output_is_restored_when_the_block_raises(fake_discard: _FakeDiscard) -> None:
    with pytest.raises(RuntimeError), discard_native_stdout():
        raise RuntimeError("boom")
    assert fake_discard.restored == 1 and native_output._depth == 0


@pytest.mark.skipif(sys.platform == "win32", reason="descriptor redirect is the POSIX strategy")
def test_native_stdout_descriptor_is_discarded_inside_the_block_and_restored_after(
    capfd: pytest.CaptureFixture[str],
) -> None:
    os.write(1, b"before\n")
    with discard_native_stdout():
        os.write(1, b"Error generating tree nodes:\n")  # what the native library does
        os.write(2, b"stderr stays visible\n")
    os.write(1, b"after\n")
    out, err = capfd.readouterr()
    assert out == "before\nafter\n"
    assert err == "stderr stays visible\n"


@pytest.mark.skipif(sys.platform == "win32", reason="descriptor redirect is the POSIX strategy")
def test_a_process_without_standard_output_is_not_an_error(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    def no_stdout(fd: int) -> int:
        raise OSError("no console")

    # os is a shared module: patch it only around the call so pytest's own capture keeps working
    with monkeypatch.context() as patch:
        patch.setattr(native_output.os, "dup", no_stdout)
        with discard_native_stdout():
            os.write(1, b"nothing to silence\n")
    assert capfd.readouterr().out == "nothing to silence\n"  # the redirect was simply not made


def _std_output_handle() -> int | None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel32.GetStdHandle.restype = ctypes.c_void_p
    return kernel32.GetStdHandle(-11 & 0xFFFFFFFF)


@pytest.mark.skipif(sys.platform != "win32", reason="the NULL standard-output handle is the Windows strategy")
def test_windows_standard_output_handle_is_nulled_inside_the_block_and_reset_after() -> None:
    before = _std_output_handle()
    with discard_native_stdout():
        assert not _std_output_handle()  # NULL: .NET answers that with a null stream
        os.write(2, b"")  # Python's own descriptors are untouched
    assert _std_output_handle() == before


NATIVE_BLOCKS_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
from src.utils.native_output import discard_native_stdout

generator = TypeTreeGenerator("2022.3.0f1")
for block in range(3):  # three separate harvests in one process
    with discard_native_stdout():
        try:
            generator.get_nodes_as_json("Assembly-CSharp.dll", "Some.Missing.Type")  # the library prints an error
        except AssertionError:
            pass
    print("block", block, "done", flush=True)
print("all blocks finished", flush=True)\n"""


def test_repeated_harvests_with_the_real_native_library_do_not_crash_or_print(tmp_path: Path) -> None:
    # Regression: redirecting descriptor 1 to a file and restoring it closed the handle the .NET
    # runtime had cached, so the second harvest of a session killed the whole process.
    pytest.importorskip("TypeTreeGeneratorAPI")
    script = tmp_path / "blocks.py"
    script.write_text(NATIVE_BLOCKS_SCRIPT.format(root=str(ROOT)), encoding="utf-8")
    run = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120, env={**os.environ, "PYTHONUTF8": "1"}, cwd=tmp_path, check=False,
    )
    assert run.returncode == 0, run.stderr[-600:]
    assert "Error generating tree nodes" not in run.stdout
    assert run.stdout.split() == ["block", "0", "done", "block", "1", "done", "block", "2", "done",
                                  "all", "blocks", "finished"]


# --- harvesting -----------------------------------------------------------------------


def _fake_harvest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[str]:
    entered: list[str] = []

    @contextlib.contextmanager
    def counting_discard() -> Iterator[None]:
        entered.append("discard")
        yield

    def harvest_file(cls: Any, path: Path, source_lang: str = "en", generator: Any = None, stats: Any = None) -> list[str]:
        entered.append("file")
        return ["Hello there"]

    monkeypatch.setattr(asset_harvester, "find_serialized_sources", lambda data_dir: [tmp_path / "a.assets"])
    monkeypatch.setattr(asset_harvester, "discard_native_stdout", counting_discard)
    monkeypatch.setattr(AssetHarvester, "harvest_asset_file", classmethod(harvest_file))
    return entered


def test_a_harvest_with_a_generator_runs_inside_the_native_output_discard(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    entered = _fake_harvest(monkeypatch, tmp_path)
    assert AssetHarvester.harvest_data_dir(tmp_path, "en", object()) == ["Hello there"]
    assert entered == ["discard", "file"]  # the whole file loop is inside the block


def test_a_harvest_without_a_generator_leaves_standard_output_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    entered = _fake_harvest(monkeypatch, tmp_path)
    assert AssetHarvester.harvest_data_dir(tmp_path, "en", None) == ["Hello there"]
    assert entered == ["file"]


# --- generator provider ---------------------------------------------------------------


class _Generator:
    def __init__(self, fail_with: Exception | None = None) -> None:
        self.fail_with = fail_with
        self.loaded: list[tuple[str, int | str]] = []

    def load_il2cpp(self, binary: bytes, metadata: bytes) -> None:
        if self.fail_with:
            raise self.fail_with
        self.loaded.append(("il2cpp", len(binary) + len(metadata)))

    def load_local_dll_folder(self, folder: str) -> None:
        self.loaded.append(("mono", folder))


def _il2cpp_game(tmp_path: Path, **profile: Any) -> UnityGameProfile:
    data = tmp_path / "Game_Data"
    (data / "il2cpp_data" / "Metadata").mkdir(parents=True)
    (tmp_path / "GameAssembly.dll").write_bytes(b"MZ")
    (data / "il2cpp_data" / "Metadata" / "global-metadata.dat").write_bytes(b"meta")
    return UnityGameProfile(game_path=tmp_path, data_dir=data, unity_version="6000.3.10f1", is_il2cpp=True, **profile)


def test_an_il2cpp_load_failure_names_the_metadata_version_and_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    generator = _Generator(RuntimeError("failed to load il2cpp"))
    monkeypatch.setattr(typetree_provider, "_new_generator", lambda version: generator)
    with caplog.at_level(logging.WARNING):
        assert typetree_provider.create_typetree_generator(_il2cpp_game(tmp_path, metadata_version=39)) is None
    assert "IL2CPP metadata v39" in caplog.text and "raw string scanning" in caplog.text
    assert "failed to load il2cpp" in caplog.text


def test_a_loaded_il2cpp_generator_is_returned(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    generator = _Generator()
    monkeypatch.setattr(typetree_provider, "_new_generator", lambda version: generator)
    assert typetree_provider.create_typetree_generator(_il2cpp_game(tmp_path, metadata_version=31)) is generator
    assert generator.loaded == [("il2cpp", 6)]


def test_a_mono_game_loads_its_managed_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "Game_Data" / "Managed").mkdir(parents=True)
    generator = _Generator()
    monkeypatch.setattr(typetree_provider, "_new_generator", lambda version: generator)
    profile = UnityGameProfile(game_path=tmp_path, data_dir=tmp_path / "Game_Data", unity_version="6000.3.20f1")
    assert typetree_provider.create_typetree_generator(profile) is generator
    assert generator.loaded == [("mono", str(tmp_path / "Game_Data" / "Managed"))]


def test_a_mono_game_without_a_managed_folder_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(typetree_provider, "_new_generator", lambda version: _Generator())
    profile = UnityGameProfile(game_path=tmp_path, data_dir=tmp_path, unity_version="6000.3.20f1")
    with caplog.at_level(logging.WARNING):
        assert typetree_provider.create_typetree_generator(profile) is None
    assert "Mono assemblies" in caplog.text


def test_encrypted_il2cpp_metadata_never_builds_a_generator(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def must_not_run(version: str) -> Any:
        raise AssertionError("no generator should be created for encrypted metadata")

    monkeypatch.setattr(typetree_provider, "_new_generator", must_not_run)
    profile = _il2cpp_game(tmp_path, metadata_encrypted=True)
    assert typetree_provider.create_typetree_generator(profile) is None


def test_a_missing_native_package_falls_back_quietly(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(typetree_provider, "_new_generator", lambda version: None)
    assert typetree_provider.create_typetree_generator(_il2cpp_game(tmp_path, metadata_version=31)) is None


# --- packaging ------------------------------------------------------------------------


def test_requirements_ask_for_the_unitypy_ttgen_extra() -> None:
    lines = [ln.strip() for ln in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()]
    assert any(ln.startswith("UnityPy[ttgen]") for ln in lines)
    assert not any(ln.startswith("UnityPy>=") for ln in lines)  # one UnityPy line, with the extra


def test_pyinstaller_collects_the_native_generator() -> None:
    spec = importlib.util.spec_from_file_location("project_build", ROOT / "build.py")
    assert spec is not None and spec.loader is not None
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    args = build.get_collect_args()
    assert args[args.index("TypeTreeGeneratorAPI") - 1] == "--collect-all"


def test_self_check_verifies_the_generator_is_installed() -> None:
    assert "typetree-generator" in CHECKS
    pytest.importorskip("TypeTreeGeneratorAPI")
    CHECKS["typetree-generator"]()
