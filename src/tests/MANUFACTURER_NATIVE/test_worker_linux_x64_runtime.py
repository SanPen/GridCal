# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import subprocess
import sys

import pytest

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.Dynamic.manufacturer_native_model import (
    ManufacturerNativeBinarySource,
    ManufacturerNativeBinaryVariant,
)
from VeraGridEngine.enumerations import (
    IeeeCigreDllPlatform,
    IeeeCigreDllVerificationStatus,
    NativeModelInterface,
)
from VeraGridEngine.IO.manufacturer_native.inspection import (
    _ManufacturerNativeQualificationTrace,
    _mode_for_qualification,
    _qualification_inputs,
    _qualification_overrides,
    _qualification_trace,
    inspect_manufacturer_native,
)
from VeraGridEngine.IO.manufacturer_native.runtime_host import (
    ManufacturerNativeWorkerHost,
    prepare_manufacturer_native_worker_host,
)
from VeraGridEngine.IO.manufacturer_native.worker_artifact import (
    ManufacturerNativeWorkerArtifact,
    prepare_manufacturer_native_runtime,
)
from VeraGridEngine.IO.native_compiler.compiler_interface import NativeCompilerSelection, NativeCompilerToolset
from VeraGridEngine.IO.native_compiler.selected_interface import (
    load_saved_local_llvm_selection,
    resolve_native_compiler_toolset,
)
from VeraGridEngine.IO.native_runtime import NativeWorkerLimits


@pytest.mark.parametrize(
    ("fixture_directory", "native_interface", "model_name", "sample_time", "defines"),
    (
        (
            "linux_x64_v11",
            NativeModelInterface.IEEE_CIGRE_V1_1,
            "GoldenModel",
            0.000005,
            ("-DQUALIFIED=1",),
        ),
        (
            "windows_x64_v10",
            NativeModelInterface.IEEE_CIGRE_V1_0,
            "LegacyFixture",
            0.0003,
            tuple(),
        ),
        (
            "windows_x64_iec_ese",
            NativeModelInterface.IEC_ESE,
            "IecEseFixture",
            0.0002,
            tuple(),
        ),
    ),
)
def test_linux_x64_fixture_qualifies_through_prepared_c_worker(
        tmp_path: Path,
        fixture_directory: str,
        native_interface: NativeModelInterface,
        model_name: str,
        sample_time: float,
        defines: tuple[str, ...]) -> None:
    """Compile and qualify one reviewed ABI fixture on a Linux x64 host.

    :param tmp_path: Private build directory supplied by pytest.
    :param fixture_directory: Existing portable fixture directory.
    :param native_interface: ABI contract exercised by the fixture.
    :param model_name: Expected model identity returned by the ABI.
    :param sample_time: Expected exact declared sample time.
    :param defines: Required fixture compile definitions.
    :return: None.
    """
    if not sys.platform.startswith("linux") or struct.calcsize("P") != 8:
        pytest.skip("Linux x64 worker evidence runs only on a Linux x64 host")
    else:
        pass
    fixture_source: Path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "manufacturer_native"
        / fixture_directory
        / "fixture.c"
    )
    fixture_binary: Path = tmp_path / (fixture_directory + ".so")
    selection: NativeCompilerSelection | None = load_saved_local_llvm_selection()
    if selection is None:
        pytest.skip("External LLVM is not configured")
    else:
        pass
    toolset: NativeCompilerToolset = resolve_native_compiler_toolset(selection)
    worker_artifact: ManufacturerNativeWorkerArtifact = prepare_manufacturer_native_runtime(
        timeout_seconds=120.0,
        selection=selection,
    ).artifact
    arguments: list[str] = [
        str(toolset.compiler_path),
        *toolset.compiler_prefix_arguments,
        "-std=c11",
        "-O2",
        "-shared",
        "-fPIC",
        "-Wall",
        "-Wextra",
        "-Werror",
        *defines,
        "-o",
        str(fixture_binary),
        str(fixture_source),
    ]
    completed: subprocess.CompletedProcess[str] = subprocess.run(
        arguments,
        check=False,
        capture_output=True,
        text=True,
        shell=False,
    )
    assert completed.returncode == 0, completed.stderr

    result = inspect_manufacturer_native(
        source_path=fixture_binary,
        platform=IeeeCigreDllPlatform.LINUX_X64,
        native_interface=native_interface,
        vendor_declares_no_late_loading=True,
        vendor_declares_instance_isolation=True,
        worker_artifact=worker_artifact,
    )

    assert result.model_info.model_name == model_name
    assert result.model_info.fixed_step_base_sample_time == sample_time
    assert result.verification_status.value == "declared_and_qualified"

    if native_interface == NativeModelInterface.IEEE_CIGRE_V1_0:
        source: ManufacturerNativeBinarySource = ManufacturerNativeBinarySource(
            platform=IeeeCigreDllPlatform.LINUX_X64,
            file_path=str(fixture_binary),
        )
        variant: ManufacturerNativeBinaryVariant = ManufacturerNativeBinaryVariant(
            platform=IeeeCigreDllPlatform.LINUX_X64,
            extension=".so",
            content_sha256=result.binary_sha256,
            byte_size=result.binary_size,
            zip_member=(
                "native_models/manufacturer/by_sha256/"
                + result.binary_sha256
                + ".so"
            ),
            verification_status=result.verification_status,
        )
        trace: _ManufacturerNativeQualificationTrace = _qualification_trace(
            source=source,
            variant=variant,
            canonical_bytes=result.canonical_model_info,
            model_info=result.model_info,
            limits=NativeWorkerLimits(),
            alternate_order=(False,),
        )
        assert trace.primary == (
            (1.0, 0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0, 0.0),
            (3.0, 0.0, 0.0, 0.0),
            (4.0, 0.0, 0.0, 0.0),
        )
    elif native_interface == NativeModelInterface.IEEE_CIGRE_V1_1:
        # Each fault happens after initialization and proves that vendor code
        # cannot retain a worker process or its private staged library.
        failure_cases: tuple[tuple[str, type[BaseException], str], ...] = (
            ("CRASH_ON_SAMPLE", RuntimeError, "External native worker"),
            ("HANG_ON_SAMPLE", TimeoutError, "response timed out"),
            ("NAN_ON_SAMPLE", ValueError, "output value is not finite"),
            ("FAIL_ON_SAMPLE", RuntimeError, "Model_Outputs failed"),
        )
        failure_macro: str
        expected_error: type[BaseException]
        expected_message: str
        for failure_macro, expected_error, expected_message in failure_cases:
            failure_binary: Path = tmp_path / (failure_macro.lower() + ".so")
            failure_arguments: list[str] = [
                str(toolset.compiler_path),
                *toolset.compiler_prefix_arguments,
                "-std=c11",
                "-O2",
                "-shared",
                "-fPIC",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-DQUALIFIED=1",
                "-D" + failure_macro + "=1",
                "-o",
                str(failure_binary),
                str(fixture_source),
            ]
            failure_completed: subprocess.CompletedProcess[str] = subprocess.run(
                failure_arguments,
                check=False,
                capture_output=True,
                text=True,
                shell=False,
            )
            assert failure_completed.returncode == 0, failure_completed.stderr
            failure_bytes: bytes = failure_binary.read_bytes()
            failure_sha256: str = hashlib.sha256(failure_bytes).hexdigest()
            failure_source: ManufacturerNativeBinarySource = ManufacturerNativeBinarySource(
                platform=IeeeCigreDllPlatform.LINUX_X64,
                file_path=str(failure_binary),
            )
            failure_variant: ManufacturerNativeBinaryVariant = ManufacturerNativeBinaryVariant(
                platform=IeeeCigreDllPlatform.LINUX_X64,
                extension=".so",
                content_sha256=failure_sha256,
                byte_size=len(failure_bytes),
                zip_member=(
                    "native_models/manufacturer/by_sha256/"
                    + failure_sha256
                    + ".so"
                ),
                verification_status=IeeeCigreDllVerificationStatus.UNVERIFIED,
            )
            failure_limits: NativeWorkerLimits = NativeWorkerLimits(
                response_timeout_seconds=0.25,
                graceful_join_timeout_seconds=0.25,
                terminate_join_timeout_seconds=0.25,
                kill_join_timeout_seconds=0.25,
            )
            failure_host: ManufacturerNativeWorkerHost = (
                prepare_manufacturer_native_worker_host(
                    source=failure_source,
                    variant=failure_variant,
                    canonical_model_info=result.canonical_model_info,
                    limits=failure_limits,
                    logger=Logger(),
                    worker_artifact=worker_artifact,
                )
            )
            qualification_inputs: tuple[int | float, ...] = _qualification_inputs(
                model_info=result.model_info,
                alternate=False,
            )
            qualification_overrides: tuple[
                tuple[int, int, bool, int | float | str], ...
            ] = _qualification_overrides(
                model_info=result.model_info,
                alternate=False,
            )
            initial_outputs: tuple[tuple[str, tuple[int | float, ...]], ...] = (
                failure_host.initialize_instances((
                    (
                        "failure-instance",
                        _mode_for_qualification(result.model_info),
                        qualification_inputs,
                        qualification_overrides,
                    ),
                ))
            )
            assert initial_outputs == (("failure-instance", (0.25,)),)
            with pytest.raises(expected_error, match=expected_message):
                failure_host.sample_batch(
                    sample_time=result.model_info.fixed_step_base_sample_time,
                    samples=(("failure-instance", qualification_inputs),),
                )
            try:
                failure_host.close()
            except RuntimeError:
                # A crash or timeout already closed the owner and proved death.
                pass
            assert failure_host._owner._closed
            assert failure_host._owner._staging.is_closed()
    else:
        pass
