# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Contract tests for the FMU compiler boundary."""

from pathlib import Path

import pytest

from VeraGridEngine.IO.fmu.compiler import (
    FmuBinaryInterface,
    Compiler,
    compile_fmu_shared_library,
    _missing_exported_symbols,
    _required_fmi_symbols,
    fmu_compiler_available,
)
from VeraGridEngine.IO.fmu.config import detect_target_platform, library_suffix


def test_required_symbols_are_interface_specific() -> None:
    """Ensure Co-Simulation and Model Exchange require different APIs."""

    co_simulation_symbols: tuple[str, ...] = _required_fmi_symbols(
        FmuBinaryInterface.FMI_TWO_CO_SIMULATION
    )
    model_exchange_symbols: tuple[str, ...] = _required_fmi_symbols(
        FmuBinaryInterface.FMI_TWO_MODEL_EXCHANGE
    )
    assert "fmi2DoStep" in co_simulation_symbols
    assert "fmi2DoStep" not in model_exchange_symbols
    assert "fmi2GetDerivatives" in model_exchange_symbols
    assert "fmi2GetDerivatives" not in co_simulation_symbols


def test_missing_symbol_validation_is_platform_aware() -> None:
    """Ensure symbol inventories normalize Darwin leading underscores."""

    symbols: tuple[str, ...] = _required_fmi_symbols(
        FmuBinaryInterface.FMI_TWO_CO_SIMULATION
    )
    inventory: str = "\n".join("_" + symbol for symbol in symbols)
    assert _missing_exported_symbols(
        inventory,
        FmuBinaryInterface.FMI_TWO_CO_SIMULATION,
        "darwin",
    ) == tuple()


def test_shared_compiler_builds_fmu_library(tmp_path: Path) -> None:
    """Build a complete FMI 2 Co-Simulation symbol stub through Compiler."""

    if fmu_compiler_available():
        pass
    else:
        pytest.skip("No shared compiler is available")

    source_path: Path = tmp_path / "stub.c"
    symbols: tuple[str, ...] = _required_fmi_symbols(
        FmuBinaryInterface.FMI_TWO_CO_SIMULATION
    )
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

    output_path: Path = tmp_path / ("stub" + library_suffix(detect_target_platform()))
    compiler: Compiler = Compiler()
    compiled_path: Path = compile_fmu_shared_library(
        source_files=(source_path,),
        include_directories=(tmp_path,),
        output_path=output_path,
        interface=FmuBinaryInterface.FMI_TWO_CO_SIMULATION,
        compiler=compiler,
    )
    assert compiled_path == output_path
    assert compiled_path.is_file()
