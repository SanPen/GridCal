"""Qualify FMU compilation through capabilities independently of provider identity."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import CompilerName
from VeraGridEngine.Utils.Compiler.interface import Compiler, CompilerInterface
from VeraGridEngine.IO.fmu.compiler import (
    compile_fmu_shared_library, fmu_compiler_available, _native_library_suffix,
)
from tests.FMI.fmi_test_support import build_test_fmi_compiler


class _UnbrandedCompilerHandler(CompilerInterface):
    """Delegate real operations without identifying a native provider."""

    __slots__ = ("_delegate",)

    def __init__(self, delegate: CompilerInterface) -> None:
        """Retain a real handler without adding an inspection dependency.

        :param delegate: Installed handler performing actual native operations.
        :return: None.
        """
        self._delegate: CompilerInterface = delegate
        super().__init__("unbranded", Logger(), delegate.executable_path)

    def _is_setup_valid(self) -> bool:
        """Preserve real setup evidence.

        :return: The delegate's setup status.
        """
        return self._delegate.setup_valid

    def compile(self, source_files: list[str], output_dir: str, lib_name: str = "", include_directories: list[str] | None = None) -> str:
        """Compile through the retained installed handler.

        :param source_files: Ordered native translation units.
        :param output_dir: Owned temporary build directory.
        :param lib_name: Requested native library filename.
        :param include_directories: Header search roots.
        :return: The real generated library path.
        """
        return self._delegate.compile(source_files, output_dir, lib_name, include_directories)


def test_fmu_uses_compiler_capabilities(tmp_path: Path, compiler: Compiler | None = None) -> None:
    """Compile with an unbranded handler that has no export inspector.

    :param tmp_path: Isolated native build directory.
    :param compiler: Optional installed compiler supplied by the builtin test.
    :return: None; failures include any DLL reference that prevents immediate removal.
    """
    selected: Compiler | None = compiler if compiler is not None else build_test_fmi_compiler()
    if selected is None:
        pytest.skip("No installed compiler; native qualification UNKNOWN")
    else:
        pass
    delegate: CompilerInterface | None = selected.get_handler()
    assert delegate is not None
    assert fmu_compiler_available(selected)
    handler: _UnbrandedCompilerHandler = _UnbrandedCompilerHandler(delegate)
    assert handler.get_native_framework() is None
    unbranded: Compiler = Compiler(compiler_handler=handler)
    assert fmu_compiler_available(unbranded)
    source: Path = tmp_path / "agnostic.c"
    source.write_text("int anchor(void) { return 0; }\n", encoding="utf-8")
    output: Path = tmp_path / ("agnostic" + _native_library_suffix())
    assert compile_fmu_shared_library((source,), (tmp_path,), output, compiler=unbranded) == output
    renamed: Path = output.with_name("released" + output.suffix)
    output.rename(renamed)
    renamed.unlink()
    assert not output.exists() and not renamed.exists()


@pytest.mark.parametrize("compiler_name", (CompilerName.GCC, CompilerName.CLANG, CompilerName.MSVC))
def test_fmu_retains_builtin_compilers(tmp_path: Path, pytestconfig: pytest.Config, compiler_name: CompilerName) -> None:
    """Exercise each installed builtin without substituting another compiler.

    :param tmp_path: Isolated actual native compilation directory.
    :param pytestconfig: Optional paths to already installed compiler executables.
    :param compiler_name: Builtin compiler family under qualification.
    :return: None; unavailable genuine compilers are explicit qualification skips.
    """
    configured: str | None = pytestconfig.getoption("fmi_test_" + compiler_name.name.lower())
    executable: str | None = configured if configured is not None else shutil.which("cl.exe" if compiler_name == CompilerName.MSVC else compiler_name.value)
    if executable is None:
        pytest.skip("Genuine " + compiler_name.name + " unavailable; execution qualification UNKNOWN")
    else:
        pass
    if compiler_name == CompilerName.GCC:
        version: subprocess.CompletedProcess[str] = subprocess.run([executable, "--version"], capture_output=True, text=True, check=False)
        if configured is None and "clang" in version.stdout.lower():
            pytest.skip("Discovered gcc is a Clang alias; genuine GNU GCC qualification UNKNOWN")
        else:
            assert version.returncode == 0 and "clang" not in version.stdout.lower(), "A Clang gcc alias is not GNU GCC evidence"
    else:
        pass
    paths: dict[CompilerName, str] = dict((name, str(tmp_path / ("absent-" + name.value))) for name in CompilerName)
    paths[compiler_name] = executable
    selected: Compiler = Compiler(compiler_name=compiler_name, compiler_paths=paths)
    assert selected.get_selected_compiler() == compiler_name, str(selected.logger)
    test_fmu_uses_compiler_capabilities(tmp_path, selected)
