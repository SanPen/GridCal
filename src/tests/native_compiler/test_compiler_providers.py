"""Exercise native compiler providers through the shared facade."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import CompilerName, NativeCompilerFramework
from VeraGridEngine.Utils.Compiler.interface import Compiler
from VeraGridEngine.IO.native_compiler.compiler_interface import NativeCompilerSelection, NativeCompilerToolset
from VeraGridEngine.IO.native_compiler.local_llvm_interface import (
    LocalLlvmCompilerHandler, _build_local_llvm_compile_command,
)
from VeraGridEngine.IO.native_compiler.pygslv_interface import PygslvCompilerHandler
from VeraGridEngine.IO.native_compiler.selected_interface import (
    load_saved_local_llvm_selection, resolve_native_compiler, resolve_native_compiler_toolset,
)


def test_native_handler_injection_preserves_facade(tmp_path: Path) -> None:
    """Keep native arguments, metadata and facade move/cleanup semantics.

    :param tmp_path: Isolated source/build/destination root.
    :return: None.
    """
    selection: NativeCompilerSelection | None = load_saved_local_llvm_selection()
    if selection is None:
        pytest.skip("No saved LLVM installation")
    else:
        pass
    toolset: NativeCompilerToolset = resolve_native_compiler_toolset(selection)
    logger: Logger = Logger()
    handler: LocalLlvmCompilerHandler = LocalLlvmCompilerHandler(toolset, logger)
    compiler: Compiler = Compiler(logger=logger, compiler_handler=handler)
    assert compiler.get_handler() is handler
    assert compiler.get_compiler_paths() == dict()
    assert compiler.get_compiler_status() == dict()
    assert compiler.get_selected_compiler() == CompilerName.CLANG
    assert handler.get_native_framework() == NativeCompilerFramework.LOCAL_LLVM
    source: Path = tmp_path / "facade.c"
    source.write_text("int ordinary_definition(void) { return 3; }\n", encoding="utf-8")
    output: Path = tmp_path / ("facade" + toolset.library_suffix)
    build: Path = tmp_path / "build"
    command: list[str] = _build_local_llvm_compile_command(toolset, [str(source)], [str(tmp_path)], output)
    assert command[1:1 + len(toolset.compiler_prefix_arguments)] == list(toolset.compiler_prefix_arguments)
    assert str(source.resolve()) in command and "-std=c99" in command
    assert compiler.compile([str(source)], str(build), output.name, str(output), True, [str(tmp_path)])
    assert output.is_file() and not build.exists()
    assert compiler.get_compiled_library_path() == str(output)
    assert not compiler.compile([str(tmp_path / "missing.c")], str(tmp_path / "bad-build"), output.name)
    assert compiler.get_compiled_library_path() is None
    # Uninjected callers retain executable discovery/status semantics, including failure.
    generic_paths: dict[CompilerName, str] = dict((name, str(tmp_path / ("unavailable-" + name.value))) for name in CompilerName)
    generic: Compiler = Compiler(compiler_name=CompilerName.GCC, compiler_paths=generic_paths)
    assert generic.get_requested_compiler() == CompilerName.GCC
    assert generic.get_handler() is None
    assert set(generic.get_compiler_paths()) == set(CompilerName)
    assert generic.get_compiler_status() != dict()


def test_optional_pygslv_does_not_switch_provider(tmp_path: Path) -> None:
    """A selected absent/broken package never falls back to saved LLVM.

    :param tmp_path: Explicit invalid executable root for a package provider.
    :return: None.
    """
    selection: NativeCompilerSelection = NativeCompilerSelection(NativeCompilerFramework.PYGSLV)
    handler: PygslvCompilerHandler = PygslvCompilerHandler()
    compiler: Compiler | None = resolve_native_compiler(selection)
    if handler.setup_valid:
        assert compiler is not None
        assert isinstance(compiler.get_handler(), PygslvCompilerHandler)
        assert compiler.get_selected_compiler() is None
    else:
        assert compiler is None
        assert len(handler.logger.entries) > 0
    assert resolve_native_compiler(NativeCompilerSelection(NativeCompilerFramework.PYGSLV, tmp_path)) is None


def test_pygslv_real_compile(tmp_path: Path) -> None:
    """Qualify the real optional package only when installed with its API.

    :param tmp_path: Package compilation workspace.
    :return: None; absence stays an explicit skip, never substitute-provider success.
    """
    if importlib.util.find_spec("pygslv") is None:
        pytest.skip("Optional pygslv is not installed; execution qualification remains UNKNOWN")
    else:
        pass
    handler: PygslvCompilerHandler = PygslvCompilerHandler()
    assert handler.setup_valid, "Installed pygslv is broken or lacks its required API"
    compiler: Compiler = Compiler(compiler_handler=handler)
    source: Path = tmp_path / "package.cpp"
    source.write_text("int package_anchor(void) { return 0; }\n", encoding="utf-8")
    assert compiler.compile([str(source)], str(tmp_path / "build"))
    output: str | None = compiler.get_compiled_library_path()
    assert output is not None
    assert Path(output).is_file()
