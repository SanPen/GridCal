# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Contract tests for the FMU compiler boundary."""

from pathlib import Path

import pytest

from VeraGridEngine.IO.fmu.compiler import (
    Compiler,
    compile_fmu_shared_library,
    _native_library_suffix,
    fmu_compiler_available,
)
from tests.FMI.fmi_test_support import build_test_fmi_compiler


def test_shared_compiler_builds_fmu_library(tmp_path: Path) -> None:
    """Build a native library without requiring FMI exports at compile time."""

    if fmu_compiler_available():
        pass
    else:
        pytest.skip("No shared compiler is available")

    source_path: Path = tmp_path / "stub.c"
    symbols: tuple[str, ...] = ("anchor", "inspected")
    source_lines: list[str] = [
        "#if defined(_WIN32)",
        "#define VG_EXPORT __declspec(dllexport)",
        "#else",
        "#define VG_EXPORT __attribute__((visibility(\"default\")))",
        "#endif",
    ]
    for symbol in symbols:
        source_lines.append(f"VG_EXPORT int {symbol}(void) {{ return 0; }}")
    source_path.write_text("\n".join(source_lines) + "\n", encoding="utf-8")

    output_path: Path = tmp_path / ("stub" + _native_library_suffix())
    compiler: Compiler | None = build_test_fmi_compiler()
    assert compiler is not None
    compiled_path: Path = compile_fmu_shared_library(
        source_files=(source_path,),
        include_directories=(tmp_path,),
        output_path=output_path,
        compiler=compiler,
    )
    assert compiled_path == output_path
    assert compiled_path.is_file()
    compiled_path.unlink()
    assert not compiled_path.exists()
