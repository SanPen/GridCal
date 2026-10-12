# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os
from pathlib import Path
import struct
import subprocess
from typing import Tuple

import pytest

from VeraGridEngine.enumerations import IeeeCigreDllPlatform, NativeModelInterface
from VeraGridEngine.IO.manufacturer_native.binary_validation import inspect_windows_pe_machine
from VeraGridEngine.IO.manufacturer_native.inspection import (
    ManufacturerNativeInspectionResult,
    inspect_manufacturer_native,
)
from VeraGridEngine.IO.manufacturer_native.worker_artifact import (
    ManufacturerNativeWorkerArtifact,
    resolve_packaged_windows_x86_worker,
)
from VeraGridEngine.IO.native_compiler.compiler_interface import NativeCompilerSelection, NativeCompilerToolset
from VeraGridEngine.IO.native_compiler.selected_interface import (
    load_saved_local_llvm_selection,
    resolve_native_compiler_toolset,
)


def _require_windows_x64_parent() -> None:
    """Skip PE32 execution evidence outside a Windows x64 parent.

    :return: None.
    """
    if os.name != "nt" or struct.calcsize("P") != 8:
        pytest.skip("Windows x86 worker evidence requires a Windows x64 parent")
    else:
        pass


def _compile_windows_x86_fixture(source: Path,
                                 binary: Path,
                                 definitions: Tuple[str, ...] = tuple()) -> None:
    """Compile one reviewed C fixture as a PE32 DLL with selected local LLVM.

    :param source: Reviewed fixture source.
    :param binary: Private PE32 output path.
    :param definitions: Optional ordered preprocessor definitions.
    :return: None after successful compilation.
    """
    selection: NativeCompilerSelection | None = load_saved_local_llvm_selection()
    if selection is None:
        pytest.skip("External LLVM is not configured for PE32 fixture generation")
    else:
        pass
    toolset: NativeCompilerToolset = resolve_native_compiler_toolset(selection)
    # The fixture uses the authenticated host tools with an explicit PE32 target.
    toolset.assert_unchanged()
    arguments: list[str] = list()
    arguments.extend((
        str(toolset.compiler_path),
        *toolset.compiler_prefix_arguments,
        "--target=i686-w64-windows-gnu",
        "-std=c11",
        "-O2",
        "-shared",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-Wno-unused-command-line-argument",
        "-fno-ident",
        "-Wl,--no-insert-timestamp",
    ))
    definition: str
    for definition in definitions:
        arguments.append("-D" + definition)
    arguments.extend(("-o", str(binary), str(source)))
    completed: subprocess.CompletedProcess[str] = subprocess.run(
        arguments,
        check=False,
        capture_output=True,
        text=True,
        shell=False,
    )
    toolset.assert_unchanged()
    assert completed.returncode == 0, completed.stderr
    assert inspect_windows_pe_machine(binary.read_bytes()) == 0x014c


def test_packaged_windows_x86_worker_is_common_source_bound() -> None:
    """Resolve the reviewed common-protocol PE32 worker and its manifest.

    :return: None.
    """
    _require_windows_x64_parent()
    artifact: ManufacturerNativeWorkerArtifact = resolve_packaged_windows_x86_worker()

    assert artifact.platform == IeeeCigreDllPlatform.WINDOWS_X86
    assert artifact.executable_path.name == "veragrid-manufacturer-worker-x86.exe"
    assert inspect_windows_pe_machine(artifact.executable_path.read_bytes()) == 0x014c
    assert len(artifact.content_sha256) == 64
    assert artifact.system_directory.lower().endswith(r"\windows\syswow64")


def test_windows_x86_ieee_cigre_v1_1_qualifies_through_common_worker(
        tmp_path: Path) -> None:
    """Qualify the IEEE/CIGRE 1.1 lifecycle through the common PE32 worker.

    :param tmp_path: Private fixture build directory.
    :return: None.
    """
    _require_windows_x64_parent()
    source: Path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "manufacturer_native"
        / "windows_x86"
        / "fixture.c"
    )
    binary: Path = tmp_path / "fixture_v11_x86.dll"
    _compile_windows_x86_fixture(source, binary, ("QUALIFIED=1",))

    result: ManufacturerNativeInspectionResult = inspect_manufacturer_native(
        source_path=binary,
        platform=IeeeCigreDllPlatform.WINDOWS_X86,
        native_interface=NativeModelInterface.IEEE_CIGRE_V1_1,
        vendor_declares_no_late_loading=True,
        vendor_declares_instance_isolation=True,
    )

    assert result.model_info.native_interface == NativeModelInterface.IEEE_CIGRE_V1_1
    assert result.model_info.model_name == "GoldenModel"
    assert result.model_info.fixed_step_base_sample_time == 0.000005


def test_windows_x86_ieee_cigre_v1_0_qualifies_through_common_worker(
        tmp_path: Path) -> None:
    """Qualify the IEEE/CIGRE 1.0 lifecycle through the common PE32 worker.

    :param tmp_path: Private fixture build directory.
    :return: None.
    """
    _require_windows_x64_parent()
    source: Path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "manufacturer_native"
        / "windows_x64_v10"
        / "fixture.c"
    )
    binary: Path = tmp_path / "fixture_v10_x86.dll"
    _compile_windows_x86_fixture(source, binary)

    result: ManufacturerNativeInspectionResult = inspect_manufacturer_native(
        source_path=binary,
        platform=IeeeCigreDllPlatform.WINDOWS_X86,
        native_interface=NativeModelInterface.IEEE_CIGRE_V1_0,
        vendor_declares_no_late_loading=True,
        vendor_declares_instance_isolation=False,
    )

    assert result.model_info.native_interface == NativeModelInterface.IEEE_CIGRE_V1_0
    assert result.model_info.model_name == "LegacyFixture"
    assert result.model_info.fixed_step_base_sample_time == 0.0003
    assert result.model_info.input_ports[1].width == 3
    assert result.model_info.output_ports[1].width == 3
    assert result.model_info.num_double_states == 5000


def test_windows_x86_iec_ese_qualifies_through_common_worker(tmp_path: Path) -> None:
    """Qualify the IEC ESE lifecycle through the common PE32 worker.

    :param tmp_path: Private fixture build directory.
    :return: None.
    """
    _require_windows_x64_parent()
    source: Path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "manufacturer_native"
        / "windows_x64_iec_ese"
        / "fixture.c"
    )
    binary: Path = tmp_path / "fixture_iec_ese_x86.dll"
    _compile_windows_x86_fixture(source, binary)

    result: ManufacturerNativeInspectionResult = inspect_manufacturer_native(
        source_path=binary,
        platform=IeeeCigreDllPlatform.WINDOWS_X86,
        native_interface=NativeModelInterface.IEC_ESE,
        vendor_declares_no_late_loading=True,
        vendor_declares_instance_isolation=False,
    )

    assert result.model_info.native_interface == NativeModelInterface.IEC_ESE
    assert result.model_info.model_name == "IecEseFixture"
    assert result.model_info.effective_sample_time == 0.0002
