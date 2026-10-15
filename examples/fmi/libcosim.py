# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Produce authenticated libcosim evidence for the two-FMU SMIB benchmark."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile

import matplotlib as mpl
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
import numpy as np

from examples.fmi.evidence_identity import (
    read_regular_tree_identity,
    verify_regular_file_identity,
)


class LibcosimStreamEncoding(str, Enum):
    """Declare the two strict encodings emitted across the WSL boundary."""

    UTF8 = "utf-8"
    UTF16 = "utf-16"


class LibcosimComparisonConfig:
    """Own every explicit source, runtime, FMU and process identity."""

    __slots__ = (
        "output_directory", "source_branch", "source_revision",
        "source_tree_sha256", "wsl_executable_path",
        "wsl_executable_expected_size_bytes",
        "wsl_executable_expected_sha256", "wsl_expected_version",
        "wsl_distribution_name", "wsl_expected_distribution_pretty_name",
        "wsl_expected_distribution_version_id", "wsl_expected_architecture",
        "wsl_expected_kernel", "wsl_expected_glibc_version",
        "libcosim_bundle_path", "libcosim_bundle_expected_size_bytes",
        "libcosim_bundle_expected_sha256", "libcosim_expected_cosim_version",
        "libcosim_expected_library_version", "reference_manifest_path",
        "reference_manifest_expected_size_bytes",
        "reference_manifest_expected_sha256", "plant_fmu_path",
        "plant_fmu_expected_size_bytes", "plant_fmu_expected_sha256",
        "governor_fmu_path", "governor_fmu_expected_size_bytes",
        "governor_fmu_expected_sha256", "process_timeout_seconds",
        "stream_limit_bytes",
    )

    def __init__(
        self,
        output_directory: Path,
        source_branch: str,
        source_revision: str,
        source_tree_sha256: str,
        wsl_executable_path: Path,
        wsl_executable_expected_size_bytes: int,
        wsl_executable_expected_sha256: str,
        wsl_expected_version: str,
        wsl_distribution_name: str,
        wsl_expected_distribution_pretty_name: str,
        wsl_expected_distribution_version_id: str,
        wsl_expected_architecture: str,
        wsl_expected_kernel: str,
        wsl_expected_glibc_version: str,
        libcosim_bundle_path: Path,
        libcosim_bundle_expected_size_bytes: int,
        libcosim_bundle_expected_sha256: str,
        libcosim_expected_cosim_version: str,
        libcosim_expected_library_version: str,
        reference_manifest_path: Path,
        reference_manifest_expected_size_bytes: int,
        reference_manifest_expected_sha256: str,
        plant_fmu_path: Path,
        plant_fmu_expected_size_bytes: int,
        plant_fmu_expected_sha256: str,
        governor_fmu_path: Path,
        governor_fmu_expected_size_bytes: int,
        governor_fmu_expected_sha256: str,
        process_timeout_seconds: float,
        stream_limit_bytes: int,
    ) -> None:
        """Validate and retain the sealed comparison configuration.

        :param output_directory: New evidence-package destination.
        :param source_branch: Branch represented by the evidence.
        :param source_revision: Exact forty-character Git revision.
        :param source_tree_sha256: Exact source-tree evidence digest.
        :param wsl_executable_path: Explicit Windows WSL executable.
        :param wsl_executable_expected_size_bytes: Expected WSL executable size.
        :param wsl_executable_expected_sha256: Expected WSL executable digest.
        :param wsl_expected_version: Required WSL version.
        :param wsl_distribution_name: Explicit installed distribution name.
        :param wsl_expected_distribution_pretty_name: Required distribution label.
        :param wsl_expected_distribution_version_id: Required distribution version.
        :param wsl_expected_architecture: Required Linux architecture.
        :param wsl_expected_kernel: Required WSL kernel release.
        :param wsl_expected_glibc_version: Required glibc version.
        :param libcosim_bundle_path: Explicit libcosim release ZIP.
        :param libcosim_bundle_expected_size_bytes: Expected bundle size.
        :param libcosim_bundle_expected_sha256: Expected bundle digest.
        :param libcosim_expected_cosim_version: Required cosim CLI version.
        :param libcosim_expected_library_version: Required libcosim version.
        :param reference_manifest_path: Sealed Maestro comparison manifest.
        :param reference_manifest_expected_size_bytes: Expected manifest size.
        :param reference_manifest_expected_sha256: Expected manifest digest.
        :param plant_fmu_path: Explicit portable plant FMU.
        :param plant_fmu_expected_size_bytes: Expected plant FMU size.
        :param plant_fmu_expected_sha256: Expected plant FMU digest.
        :param governor_fmu_path: Explicit portable governor FMU.
        :param governor_fmu_expected_size_bytes: Expected governor FMU size.
        :param governor_fmu_expected_sha256: Expected governor FMU digest.
        :param process_timeout_seconds: Fixed process deadline.
        :param stream_limit_bytes: Independent stdout and stderr byte bound.
        :return: None.
        """

        paths_are_explicit: bool = bool(
            output_directory.is_absolute()
            and wsl_executable_path.is_absolute()
            and libcosim_bundle_path.is_absolute()
            and reference_manifest_path.is_absolute()
            and plant_fmu_path.is_absolute()
            and governor_fmu_path.is_absolute()
        )
        identities_are_sealed: bool = bool(
            wsl_executable_expected_size_bytes == 274_432
            and wsl_executable_expected_sha256
            == "27cc8dd52be326e138a89f8889241b1d8c51dd1978b22eb70be77036ccdee3c2"
            and wsl_expected_version == "2.6.3.0"
            and wsl_distribution_name == "Ubuntu"
            and wsl_expected_distribution_pretty_name == "Ubuntu 24.04.4 LTS"
            and wsl_expected_distribution_version_id == "24.04"
            and wsl_expected_architecture == "x86_64"
            and wsl_expected_kernel == "6.6.87.2-microsoft-standard-WSL2"
            and wsl_expected_glibc_version == "2.39"
            and libcosim_bundle_expected_size_bytes == 6_546_593
            and libcosim_bundle_expected_sha256
            == "d71369ea50169e34f13217ba3e666c9b3614d1bd2480995bd5459e1aea99ad0c"
            and libcosim_expected_cosim_version == "0.8.0"
            and libcosim_expected_library_version == "0.11.2"
            and reference_manifest_expected_size_bytes == 6_302
            and reference_manifest_expected_sha256
            == "541a63e3898dcf991ef8fe5a0422f5659ab581240ece523c1d3ab9bd8db4a7a5"
            and plant_fmu_expected_size_bytes == 1_383_924
            and plant_fmu_expected_sha256
            == "76d1b0588be8865c12581977b01c5f1946e2ac94dd00f3679409e893fb87ad6a"
            and governor_fmu_expected_size_bytes == 1_368_403
            and governor_fmu_expected_sha256
            == "270eecec1f1f46e0e54d1559dc56677abcac3b88b8a4a081af257194f881130b"
        )
        source_and_bounds_are_valid: bool = bool(
            len(source_branch) > 0
            and re.fullmatch(r"[0-9a-f]{40}", source_revision) is not None
            and re.fullmatch(r"[0-9a-f]{64}", source_tree_sha256) is not None
            and float(process_timeout_seconds) == 120.0
            and stream_limit_bytes == 1_048_576
        )
        if paths_are_explicit and identities_are_sealed and source_and_bounds_are_valid:
            pass
        else:
            raise ValueError("Libcosim comparison configuration differs from rev27")
        self.output_directory: Path = output_directory
        self.source_branch: str = source_branch
        self.source_revision: str = source_revision
        self.source_tree_sha256: str = source_tree_sha256
        self.wsl_executable_path: Path = wsl_executable_path
        self.wsl_executable_expected_size_bytes: int = wsl_executable_expected_size_bytes
        self.wsl_executable_expected_sha256: str = wsl_executable_expected_sha256
        self.wsl_expected_version: str = wsl_expected_version
        self.wsl_distribution_name: str = wsl_distribution_name
        self.wsl_expected_distribution_pretty_name: str = wsl_expected_distribution_pretty_name
        self.wsl_expected_distribution_version_id: str = wsl_expected_distribution_version_id
        self.wsl_expected_architecture: str = wsl_expected_architecture
        self.wsl_expected_kernel: str = wsl_expected_kernel
        self.wsl_expected_glibc_version: str = wsl_expected_glibc_version
        self.libcosim_bundle_path: Path = libcosim_bundle_path
        self.libcosim_bundle_expected_size_bytes: int = libcosim_bundle_expected_size_bytes
        self.libcosim_bundle_expected_sha256: str = libcosim_bundle_expected_sha256
        self.libcosim_expected_cosim_version: str = libcosim_expected_cosim_version
        self.libcosim_expected_library_version: str = libcosim_expected_library_version
        self.reference_manifest_path: Path = reference_manifest_path
        self.reference_manifest_expected_size_bytes: int = reference_manifest_expected_size_bytes
        self.reference_manifest_expected_sha256: str = reference_manifest_expected_sha256
        self.plant_fmu_path: Path = plant_fmu_path
        self.plant_fmu_expected_size_bytes: int = plant_fmu_expected_size_bytes
        self.plant_fmu_expected_sha256: str = plant_fmu_expected_sha256
        self.governor_fmu_path: Path = governor_fmu_path
        self.governor_fmu_expected_size_bytes: int = governor_fmu_expected_size_bytes
        self.governor_fmu_expected_sha256: str = governor_fmu_expected_sha256
        self.process_timeout_seconds: float = float(process_timeout_seconds)
        self.stream_limit_bytes: int = stream_limit_bytes


class LibcosimProcessResult:
    """Retain one bounded native-process result."""

    __slots__ = ("exit_code", "stdout_text", "stderr_text")

    def __init__(self, exit_code: int, stdout_text: str, stderr_text: str) -> None:
        """Store exact decoded process streams.

        :param exit_code: Native process exit code.
        :param stdout_text: Strictly decoded standard output.
        :param stderr_text: Strictly decoded standard error.
        :return: None.
        """

        if isinstance(exit_code, int) and isinstance(stdout_text, str) and isinstance(stderr_text, str):
            self.exit_code: int = exit_code
            self.stdout_text: str = stdout_text
            self.stderr_text: str = stderr_text
        else:
            raise ValueError("Libcosim process result is invalid")


class LibcosimTrace:
    """Own the eight fixed arrays retained from one composition execution."""

    __slots__ = (
        "time_values", "plant_angle_rad", "plant_speed_pu",
        "plant_electrical_power_pu", "plant_effective_reactance_pu",
        "plant_mechanical_control_input_pu", "controller_speed_input_pu",
        "controller_mechanical_control_output_pu",
    )

    def __init__(
        self,
        time_values: np.ndarray,
        plant_angle_rad: np.ndarray,
        plant_speed_pu: np.ndarray,
        plant_electrical_power_pu: np.ndarray,
        plant_effective_reactance_pu: np.ndarray,
        plant_mechanical_control_input_pu: np.ndarray,
        controller_speed_input_pu: np.ndarray,
        controller_mechanical_control_output_pu: np.ndarray,
    ) -> None:
        """Validate and retain one fixed-shape numerical trace.

        :param time_values: Retained communication times.
        :param plant_angle_rad: Plant rotor angle in radians.
        :param plant_speed_pu: Plant speed deviation in p.u.
        :param plant_electrical_power_pu: Plant electrical power in p.u.
        :param plant_effective_reactance_pu: Network reactance in p.u.
        :param plant_mechanical_control_input_pu: Plant control input in p.u.
        :param controller_speed_input_pu: Controller speed input in p.u.
        :param controller_mechanical_control_output_pu: Controller output in p.u.
        :return: None.
        """

        arrays: tuple[np.ndarray, ...] = (
            time_values, plant_angle_rad, plant_speed_pu,
            plant_electrical_power_pu, plant_effective_reactance_pu,
            plant_mechanical_control_input_pu, controller_speed_input_pu,
            controller_mechanical_control_output_pu,
        )
        arrays_are_valid: bool = True
        array_value: np.ndarray
        for array_value in arrays:
            arrays_are_valid = bool(
                arrays_are_valid
                and array_value.shape == (2001,)
                and np.issubdtype(array_value.dtype, np.floating)
                and np.isfinite(array_value).all()
            )
        expected_time: np.ndarray = np.linspace(0.0, 4.0, 2001, dtype=float)
        if arrays_are_valid and np.allclose(time_values, expected_time, rtol=0.0, atol=1e-12):
            pass
        else:
            raise ValueError("Libcosim trace does not match the sealed lattice")
        self.time_values: np.ndarray = time_values
        self.plant_angle_rad: np.ndarray = plant_angle_rad
        self.plant_speed_pu: np.ndarray = plant_speed_pu
        self.plant_electrical_power_pu: np.ndarray = plant_electrical_power_pu
        self.plant_effective_reactance_pu: np.ndarray = plant_effective_reactance_pu
        self.plant_mechanical_control_input_pu: np.ndarray = plant_mechanical_control_input_pu
        self.controller_speed_input_pu: np.ndarray = controller_speed_input_pu
        self.controller_mechanical_control_output_pu: np.ndarray = controller_mechanical_control_output_pu


class LibcosimSignalMetrics:
    """Retain serialization-aware error metrics for one signal."""

    __slots__ = ("maximum_absolute_error", "rms_absolute_error", "serialization_mismatch_count")

    def __init__(
        self,
        maximum_absolute_error: float,
        rms_absolute_error: float,
        serialization_mismatch_count: int,
    ) -> None:
        """Store one accepted signal comparison.

        :param maximum_absolute_error: Largest absolute numerical difference.
        :param rms_absolute_error: Root-mean-square numerical difference.
        :param serialization_mismatch_count: Six-digit mismatches.
        :return: None.
        """

        if (
            math.isfinite(maximum_absolute_error)
            and math.isfinite(rms_absolute_error)
            and maximum_absolute_error >= 0.0
            and rms_absolute_error >= 0.0
            and serialization_mismatch_count >= 0
        ):
            self.maximum_absolute_error: float = maximum_absolute_error
            self.rms_absolute_error: float = rms_absolute_error
            self.serialization_mismatch_count: int = serialization_mismatch_count
        else:
            raise ValueError("Libcosim signal metrics are invalid")


class LibcosimComparisonMetrics:
    """Retain the numerical decisions of the libcosim comparison."""

    __slots__ = (
        "maximum_time_error_seconds", "plant_angle", "plant_speed",
        "plant_electrical_power", "plant_effective_reactance",
        "plant_mechanical_control_input", "controller_speed_input",
        "controller_mechanical_control_output",
        "plant_angle_material_departure_rad",
        "plant_speed_material_departure_pu",
        "plant_electrical_power_material_departure_pu",
        "controller_mechanical_control_material_departure_pu",
    )

    def __init__(
        self,
        maximum_time_error_seconds: float,
        plant_angle: LibcosimSignalMetrics,
        plant_speed: LibcosimSignalMetrics,
        plant_electrical_power: LibcosimSignalMetrics,
        plant_effective_reactance: LibcosimSignalMetrics,
        plant_mechanical_control_input: LibcosimSignalMetrics,
        controller_speed_input: LibcosimSignalMetrics,
        controller_mechanical_control_output: LibcosimSignalMetrics,
        plant_angle_material_departure_rad: float,
        plant_speed_material_departure_pu: float,
        plant_electrical_power_material_departure_pu: float,
        controller_mechanical_control_material_departure_pu: float,
    ) -> None:
        """Store a complete accepted comparison.

        :param maximum_time_error_seconds: Largest retained time difference.
        :param plant_angle: Rotor-angle metrics.
        :param plant_speed: Speed metrics.
        :param plant_electrical_power: Electrical-power metrics.
        :param plant_effective_reactance: Reactance metrics.
        :param plant_mechanical_control_input: Plant-input metrics.
        :param controller_speed_input: Controller-input metrics.
        :param controller_mechanical_control_output: Controller-output metrics.
        :param plant_angle_material_departure_rad: Material angle response.
        :param plant_speed_material_departure_pu: Material speed response.
        :param plant_electrical_power_material_departure_pu: Material power response.
        :param controller_mechanical_control_material_departure_pu: Material control response.
        :return: None.
        """

        scalar_values: tuple[float, ...] = (
            maximum_time_error_seconds, plant_angle_material_departure_rad,
            plant_speed_material_departure_pu,
            plant_electrical_power_material_departure_pu,
            controller_mechanical_control_material_departure_pu,
        )
        if all(math.isfinite(value) and value >= 0.0 for value in scalar_values):
            self.maximum_time_error_seconds: float = maximum_time_error_seconds
            self.plant_angle: LibcosimSignalMetrics = plant_angle
            self.plant_speed: LibcosimSignalMetrics = plant_speed
            self.plant_electrical_power: LibcosimSignalMetrics = plant_electrical_power
            self.plant_effective_reactance: LibcosimSignalMetrics = plant_effective_reactance
            self.plant_mechanical_control_input: LibcosimSignalMetrics = plant_mechanical_control_input
            self.controller_speed_input: LibcosimSignalMetrics = controller_speed_input
            self.controller_mechanical_control_output: LibcosimSignalMetrics = controller_mechanical_control_output
            self.plant_angle_material_departure_rad: float = plant_angle_material_departure_rad
            self.plant_speed_material_departure_pu: float = plant_speed_material_departure_pu
            self.plant_electrical_power_material_departure_pu: float = plant_electrical_power_material_departure_pu
            self.controller_mechanical_control_material_departure_pu: float = controller_mechanical_control_material_departure_pu
        else:
            raise ValueError("Libcosim comparison metrics are invalid")


def _run_libcosim_process(
    arguments: list[str],
    timeout_seconds: float,
    stream_limit_bytes: int,
    stream_encoding: LibcosimStreamEncoding,
) -> LibcosimProcessResult:
    """Run one explicit shell-free command with bounded captured streams.

    :param arguments: Complete process argument vector.
    :param timeout_seconds: Hard process deadline.
    :param stream_limit_bytes: Independent byte limit for each stream.
    :param stream_encoding: Strict stream decoder for the command.
    :return: Captured exit code and decoded streams.
    """

    if len(arguments) > 0:
        completed: subprocess.CompletedProcess[bytes] = subprocess.run(
            arguments, shell=False, check=False, capture_output=True,
            timeout=timeout_seconds,
        )
    else:
        raise ValueError("Libcosim process arguments are empty")
    if len(completed.stdout) <= stream_limit_bytes and len(completed.stderr) <= stream_limit_bytes:
        stdout_text: str = completed.stdout.decode(stream_encoding.value, errors="strict")
        stderr_text: str = completed.stderr.decode(stream_encoding.value, errors="strict")
    else:
        raise ValueError("Libcosim process stream exceeded its sealed bound")
    return LibcosimProcessResult(completed.returncode, stdout_text, stderr_text)


def _translate_windows_path_to_wsl(windows_path: Path) -> str:
    """Translate one canonical local C-drive path into one WSL argv item.

    :param windows_path: Existing absolute local Windows path.
    :return: Canonical ``/mnt/c`` path for direct argv use.
    """

    original_text: str = str(windows_path)
    original_parts: tuple[str, ...] = windows_path.parts
    forbidden_form: bool = bool(
        not windows_path.is_absolute()
        or original_text.startswith("\\\\")
        or original_text.startswith("\\\\?\\")
        or original_text.startswith("\\\\.\\")
        or any(part in ("", ".", "..") for part in original_parts[1:])
    )
    if forbidden_form:
        raise ValueError("Only canonical absolute local C-drive paths are accepted")
    else:
        resolved_path: Path = windows_path.resolve(strict=True)
    if resolved_path.drive.casefold() == "c:":
        translated_path: str = "/mnt/c/" + resolved_path.as_posix()[3:]
    else:
        raise ValueError("Only the local C drive is accepted across WSL")
    return translated_path


def _validate_libcosim_platform(config: LibcosimComparisonConfig) -> None:
    """Authenticate WSL and its exact Ubuntu execution boundary.

    :param config: Sealed comparison configuration.
    :return: None after every platform probe matches.
    """

    verify_regular_file_identity(
        config.wsl_executable_path,
        config.wsl_executable_expected_size_bytes,
        config.wsl_executable_expected_sha256,
    )
    wsl_path: str = str(config.wsl_executable_path)
    version_result: LibcosimProcessResult = _run_libcosim_process(
        [wsl_path, "--version"], config.process_timeout_seconds,
        config.stream_limit_bytes, LibcosimStreamEncoding.UTF16,
    )
    architecture_result: LibcosimProcessResult = _run_libcosim_process(
        [wsl_path, "-d", config.wsl_distribution_name, "--", "uname", "-m"],
        config.process_timeout_seconds, config.stream_limit_bytes,
        LibcosimStreamEncoding.UTF8,
    )
    kernel_result: LibcosimProcessResult = _run_libcosim_process(
        [wsl_path, "-d", config.wsl_distribution_name, "--", "uname", "-r"],
        config.process_timeout_seconds, config.stream_limit_bytes,
        LibcosimStreamEncoding.UTF8,
    )
    glibc_result: LibcosimProcessResult = _run_libcosim_process(
        [wsl_path, "-d", config.wsl_distribution_name, "--", "ldd", "--version"],
        config.process_timeout_seconds, config.stream_limit_bytes,
        LibcosimStreamEncoding.UTF8,
    )
    release_result: LibcosimProcessResult = _run_libcosim_process(
        [wsl_path, "-d", config.wsl_distribution_name, "--", "/bin/cat", "/etc/os-release"],
        config.process_timeout_seconds, config.stream_limit_bytes,
        LibcosimStreamEncoding.UTF8,
    )
    process_results: tuple[LibcosimProcessResult, ...] = (
        version_result, architecture_result, kernel_result,
        glibc_result, release_result,
    )
    processes_are_clean: bool = all(
        result.exit_code == 0 and result.stderr_text == ""
        for result in process_results
    )
    # The executable localizes its labels, while the first four-part value is
    # the stable WSL product version represented by this evidence boundary.
    version_match: re.Match[str] | None = re.search(
        r":\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)",
        version_result.stdout_text,
    )
    first_glibc_line: str = glibc_result.stdout_text.splitlines()[0]
    glibc_match: re.Match[str] | None = re.search(
        r"\b([0-9]+\.[0-9]+)\s*$", first_glibc_line
    )
    pretty_name: str = ""
    distribution_id: str = ""
    distribution_version: str = ""
    release_line: str
    for release_line in release_result.stdout_text.splitlines():
        if release_line.startswith("PRETTY_NAME="):
            pretty_name = release_line.removeprefix("PRETTY_NAME=").strip('"')
        else:
            pass
        if release_line.startswith("ID="):
            distribution_id = release_line.removeprefix("ID=").strip('"')
        else:
            pass
        if release_line.startswith("VERSION_ID="):
            distribution_version = release_line.removeprefix("VERSION_ID=").strip('"')
        else:
            pass
    platform_matches: bool = bool(
        processes_are_clean
        and version_match is not None
        and version_match.group(1) == config.wsl_expected_version
        and architecture_result.stdout_text.strip() == config.wsl_expected_architecture
        and kernel_result.stdout_text.strip() == config.wsl_expected_kernel
        and glibc_match is not None
        and glibc_match.group(1) == config.wsl_expected_glibc_version
        and pretty_name == config.wsl_expected_distribution_pretty_name
        and distribution_id == "ubuntu"
        and distribution_version == config.wsl_expected_distribution_version_id
    )
    if platform_matches:
        pass
    else:
        raise ValueError("The WSL execution platform differs from the sealed identity")


def _validate_libcosim_config(config: LibcosimComparisonConfig) -> None:
    """Authenticate every immutable input before native execution.

    :param config: Sealed comparison configuration.
    :return: None after identities and reference schema match.
    """

    if not config.output_directory.exists() and config.output_directory.parent.is_dir():
        pass
    else:
        raise ValueError("The libcosim output directory must be a new path")
    verify_regular_file_identity(
        config.libcosim_bundle_path,
        config.libcosim_bundle_expected_size_bytes,
        config.libcosim_bundle_expected_sha256,
    )
    reference_bytes: bytes = verify_regular_file_identity(
        config.reference_manifest_path,
        config.reference_manifest_expected_size_bytes,
        config.reference_manifest_expected_sha256,
    )
    verify_regular_file_identity(
        config.plant_fmu_path,
        config.plant_fmu_expected_size_bytes,
        config.plant_fmu_expected_sha256,
    )
    verify_regular_file_identity(
        config.governor_fmu_path,
        config.governor_fmu_expected_size_bytes,
        config.governor_fmu_expected_sha256,
    )
    reference_manifest_value: object = json.loads(
        reference_bytes.decode("utf-8", errors="strict")
    )
    if isinstance(reference_manifest_value, dict):
        reference_schema: object = reference_manifest_value.get("schema", None)
        reference_status: object = reference_manifest_value.get("status", None)
        traces_value: object = reference_manifest_value.get("traces", None)
    else:
        raise ValueError("The sealed reference manifest is not an object")
    reference_record_matches: bool = False
    if (
        reference_schema == "veragrid.fmi-maestro-comparison/1"
        and reference_status == "PASS"
        and isinstance(traces_value, dict)
    ):
        reference_record: object = traces_value.get("veragrid_closed", None)
        if isinstance(reference_record, dict):
            reference_record_matches = bool(
                set(reference_record) == {
                    "relative_path", "row_count", "sha256", "size_bytes"
                }
                and reference_record.get("relative_path", None)
                == "raw/veragrid-closed-outputs.csv"
                and reference_record.get("row_count", None) == 2001
                and reference_record.get("size_bytes", None) == 279_085
                and reference_record.get("sha256", None)
                == "5dd944e79ca8646f377d31bd63e6f8c41069ee69c349063be082ee904e04ec45"
            )
        else:
            pass
    else:
        pass
    if reference_record_matches:
        pass
    else:
        raise ValueError("The sealed reference trace declaration is missing or changed")


def _extract_libcosim_bundle(
    config: LibcosimComparisonConfig,
    extraction_root: Path,
) -> Path:
    """Extract the authenticated bundle through a closed ZIP policy.

    :param config: Sealed comparison configuration.
    :param extraction_root: New unpublished extraction root.
    :return: Explicit extracted ``cosim`` executable path.
    """

    if not extraction_root.exists() and extraction_root.parent.is_dir():
        extraction_root.mkdir()
    else:
        raise ValueError("Libcosim extraction requires a new root")
    normalized_names: set[str] = set()
    aggregate_size_bytes: int = 0
    with zipfile.ZipFile(config.libcosim_bundle_path, mode="r") as archive:
        entries: list[zipfile.ZipInfo] = archive.infolist()
        if len(entries) == 22:
            pass
        else:
            raise ValueError("Libcosim bundle central-directory count changed")
        entry: zipfile.ZipInfo
        for entry in entries:
            entry_name: str = entry.filename
            posix_path: PurePosixPath = PurePosixPath(entry_name)
            unix_mode: int = (entry.external_attr >> 16) & 0xFFFF
            entry_kind: int = stat.S_IFMT(unix_mode)
            normalized_name: str = entry_name.casefold()
            path_is_safe: bool = bool(
                len(entry_name) > 0
                and "\\" not in entry_name
                and not posix_path.is_absolute()
                and all(part not in ("", ".", "..") for part in posix_path.parts)
                and not entry.is_dir()
                and entry.file_size <= 33_554_432
                and (entry_kind == 0 or entry_kind == stat.S_IFREG)
                and normalized_name not in normalized_names
            )
            if path_is_safe:
                normalized_names.add(normalized_name)
                aggregate_size_bytes += entry.file_size
            else:
                raise ValueError("Libcosim bundle contains an unsafe or duplicate entry")
            if aggregate_size_bytes <= 67_108_864:
                payload: bytes = archive.read(entry)
            else:
                raise ValueError("Libcosim bundle exceeds its extraction bound")
            target_path: Path = extraction_root.joinpath(*posix_path.parts)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            resolved_parent: Path = target_path.parent.resolve(strict=True)
            resolved_root: Path = extraction_root.resolve(strict=True)
            if (
                len(payload) == entry.file_size
                and (resolved_parent == resolved_root or resolved_root in resolved_parent.parents)
            ):
                target_path.write_bytes(payload)
            else:
                raise ValueError("Libcosim extraction escaped its root or changed length")
    extracted_identity: tuple[int, int, str] = read_regular_tree_identity(
        extraction_root
    )
    if extracted_identity == (
        22, 18_086_364,
        "363bbda9f3e72c65a86bdb443c7d914f6275dddfb83df250819aebe5d689a1d4",
    ):
        cosim_path: Path = extraction_root / "bin" / "cosim"
    else:
        raise ValueError("Extracted libcosim tree differs from the sealed identity")
    if cosim_path.is_file() and not cosim_path.is_symlink():
        return cosim_path
    else:
        raise ValueError("The authenticated libcosim executable is missing")


def _write_libcosim_inputs(
    input_directory: Path,
    plant_fmu_path: Path,
    governor_fmu_path: Path,
) -> None:
    """Write the fixed delayed OSP composition and logger configuration.

    :param input_directory: New native input directory.
    :param plant_fmu_path: Authenticated portable plant FMU.
    :param governor_fmu_path: Authenticated portable governor FMU.
    :return: None.
    """

    if not input_directory.exists():
        input_directory.mkdir()
    else:
        raise ValueError("Libcosim input directory must be new")
    osp_text: str = """<?xml version="1.0" encoding="utf-8"?>
<OspSystemStructure
    xmlns="http://opensimulationplatform.com/MSMI/OSPSystemStructure"
    version="0.1">
  <StartTime>0.0</StartTime>
  <BaseStepSize>0.002</BaseStepSize>
  <Algorithm>fixedStep</Algorithm>
  <Simulators>
    <Simulator name="plant" source="SMIBNetworkPlant.fmu" stepSize="0.002"/>
    <Simulator name="controller" source="SMIBGovernorController.fmu" stepSize="0.002">
      <InitialValues>
        <InitialValue variable="K">
          <Real value="4.0"/>
        </InitialValue>
      </InitialValues>
    </Simulator>
  </Simulators>
  <Functions/>
  <Connections>
    <VariableConnection>
      <Variable simulator="plant" name="SPEED"/>
      <Variable simulator="controller" name="SPEED"/>
    </VariableConnection>
    <VariableConnection>
      <Variable simulator="controller" name="MECH_CONTROL"/>
      <Variable simulator="plant" name="MECH_CONTROL"/>
    </VariableConnection>
  </Connections>
</OspSystemStructure>
"""
    log_text: str = """<?xml version="1.0" encoding="utf-8"?>
<simulators timeStampedFileNames="false">
  <simulator name="plant" decimationFactor="1">
    <variable name="ANGLE"/>
    <variable name="MECH_CONTROL"/>
    <variable name="PELEC"/>
    <variable name="SPEED"/>
    <variable name="X_EFFECTIVE"/>
  </simulator>
  <simulator name="controller" decimationFactor="1">
    <variable name="MECH_CONTROL"/>
    <variable name="SPEED"/>
  </simulator>
</simulators>
"""
    (input_directory / "OspSystemStructure.xml").write_text(
        osp_text, encoding="utf-8", newline="\n"
    )
    (input_directory / "LogConfig.xml").write_text(
        log_text, encoding="utf-8", newline="\n"
    )
    shutil.copyfile(plant_fmu_path, input_directory / "SMIBNetworkPlant.fmu")
    shutil.copyfile(
        governor_fmu_path, input_directory / "SMIBGovernorController.fmu"
    )


def _parse_libcosim_trace(
    plant_csv_path: Path,
    controller_csv_path: Path,
) -> LibcosimTrace:
    """Parse the two exact libcosim CSV streams without interpolation.

    :param plant_csv_path: Native plant logger CSV.
    :param controller_csv_path: Native controller logger CSV.
    :return: Aligned fixed-shape libcosim trace.
    """

    plant_values: np.ndarray = np.empty((2001, 6), dtype=float)
    controller_values: np.ndarray = np.empty((2001, 3), dtype=float)
    expected_plant_header: list[str] = [
        "Time", "StepCount", "ANGLE", "MECH_CONTROL", "PELEC", "SPEED",
        "X_EFFECTIVE",
    ]
    expected_controller_header: list[str] = [
        "Time", "StepCount", "MECH_CONTROL", "SPEED"
    ]
    with plant_csv_path.open("r", encoding="utf-8", newline="") as plant_stream:
        plant_reader: csv.reader = csv.reader(plant_stream)
        if next(plant_reader) == expected_plant_header:
            pass
        else:
            raise ValueError("Libcosim plant CSV header changed")
        plant_row_index: int = 0
        plant_row: list[str]
        for plant_row in plant_reader:
            if (
                plant_row_index < 2001
                and len(plant_row) == 7
                and int(plant_row[1]) == plant_row_index
            ):
                plant_values[plant_row_index, :] = np.asarray(
                    [
                        float(plant_row[0]), float(plant_row[2]),
                        float(plant_row[3]), float(plant_row[4]),
                        float(plant_row[5]), float(plant_row[6]),
                    ],
                    dtype=float,
                )
                plant_row_index += 1
            else:
                raise ValueError("Libcosim plant CSV row is malformed")
    with controller_csv_path.open(
        "r", encoding="utf-8", newline=""
    ) as controller_stream:
        controller_reader: csv.reader = csv.reader(controller_stream)
        if next(controller_reader) == expected_controller_header:
            pass
        else:
            raise ValueError("Libcosim controller CSV header changed")
        controller_row_index: int = 0
        controller_row: list[str]
        for controller_row in controller_reader:
            if (
                controller_row_index < 2001
                and len(controller_row) == 4
                and int(controller_row[1]) == controller_row_index
            ):
                controller_values[controller_row_index, :] = np.asarray(
                    [
                        float(controller_row[0]), float(controller_row[2]),
                        float(controller_row[3]),
                    ],
                    dtype=float,
                )
                controller_row_index += 1
            else:
                raise ValueError("Libcosim controller CSV row is malformed")
    if (
        plant_row_index == 2001
        and controller_row_index == 2001
        and np.allclose(
            plant_values[:, 0], controller_values[:, 0], rtol=0.0, atol=1e-12
        )
    ):
        pass
    else:
        raise ValueError("Libcosim CSV files do not contain the same 2001 rows")
    return LibcosimTrace(
        time_values=plant_values[:, 0],
        plant_angle_rad=plant_values[:, 1],
        plant_speed_pu=plant_values[:, 4],
        plant_electrical_power_pu=plant_values[:, 3],
        plant_effective_reactance_pu=plant_values[:, 5],
        plant_mechanical_control_input_pu=plant_values[:, 2],
        controller_speed_input_pu=controller_values[:, 2],
        controller_mechanical_control_output_pu=controller_values[:, 1],
    )


def _parse_veragrid_reference_trace(trace_path: Path) -> LibcosimTrace:
    """Parse the sealed VeraGrid composition reference CSV.

    :param trace_path: Authenticated reference trace path.
    :return: Fixed-shape VeraGrid trace.
    """

    expected_header: list[str] = [
        "time", "{controller}.controller.MECH_CONTROL",
        "{controller}.controller.SPEED", "{plant}.plant.ANGLE",
        "{plant}.plant.MECH_CONTROL", "{plant}.plant.PELEC",
        "{plant}.plant.SPEED", "{plant}.plant.X_EFFECTIVE",
    ]
    values: np.ndarray = np.empty((2001, 8), dtype=float)
    with trace_path.open("r", encoding="utf-8", newline="") as trace_stream:
        trace_reader: csv.reader = csv.reader(trace_stream)
        if next(trace_reader) == expected_header:
            pass
        else:
            raise ValueError("VeraGrid reference CSV header changed")
        row_index: int = 0
        row_value: list[str]
        for row_value in trace_reader:
            if row_index < 2001 and len(row_value) == 8:
                row_values: list[float] = list()
                token_value: str
                for token_value in row_value:
                    row_values.append(float(token_value))
                values[row_index, :] = np.asarray(row_values, dtype=float)
                row_index += 1
            else:
                raise ValueError("VeraGrid reference CSV row is malformed")
    if row_index == 2001:
        pass
    else:
        raise ValueError("VeraGrid reference CSV row count changed")
    return LibcosimTrace(
        time_values=values[:, 0],
        plant_angle_rad=values[:, 3],
        plant_speed_pu=values[:, 6],
        plant_electrical_power_pu=values[:, 5],
        plant_effective_reactance_pu=values[:, 7],
        plant_mechanical_control_input_pu=values[:, 4],
        controller_speed_input_pu=values[:, 2],
        controller_mechanical_control_output_pu=values[:, 1],
    )


def _evaluate_libcosim_comparison(
    libcosim_trace: LibcosimTrace,
    veragrid_trace: LibcosimTrace,
) -> LibcosimComparisonMetrics:
    """Evaluate exact serialization, events and material response.

    :param libcosim_trace: Native libcosim trace.
    :param veragrid_trace: Sealed VeraGrid reference trace.
    :return: Typed metrics after all numerical gates pass.
    """

    native_signals: tuple[np.ndarray, ...] = (
        libcosim_trace.plant_angle_rad, libcosim_trace.plant_speed_pu,
        libcosim_trace.plant_electrical_power_pu,
        libcosim_trace.plant_effective_reactance_pu,
        libcosim_trace.plant_mechanical_control_input_pu,
        libcosim_trace.controller_speed_input_pu,
        libcosim_trace.controller_mechanical_control_output_pu,
    )
    reference_signals: tuple[np.ndarray, ...] = (
        veragrid_trace.plant_angle_rad, veragrid_trace.plant_speed_pu,
        veragrid_trace.plant_electrical_power_pu,
        veragrid_trace.plant_effective_reactance_pu,
        veragrid_trace.plant_mechanical_control_input_pu,
        veragrid_trace.controller_speed_input_pu,
        veragrid_trace.controller_mechanical_control_output_pu,
    )
    signal_metrics: list[LibcosimSignalMetrics] = list()
    native_signal: np.ndarray
    reference_signal: np.ndarray
    for native_signal, reference_signal in zip(
        native_signals, reference_signals, strict=True
    ):
        absolute_error: np.ndarray = np.abs(native_signal - reference_signal)
        serialized_reference: np.ndarray = np.empty(2001, dtype=float)
        sample_index: int
        for sample_index in range(2001):
            serialized_reference[sample_index] = float(
                format(reference_signal[sample_index], ".6g")
            )
        signal_metrics.append(
            LibcosimSignalMetrics(
                maximum_absolute_error=float(np.max(absolute_error)),
                rms_absolute_error=float(
                    np.sqrt(np.mean(np.square(absolute_error)))
                ),
                serialization_mismatch_count=int(
                    np.count_nonzero(native_signal != serialized_reference)
                ),
            )
        )
    maximum_time_error: float = float(np.max(np.abs(
        libcosim_trace.time_values - veragrid_trace.time_values
    )))
    oracle_rows: np.ndarray = np.asarray([500, 501, 575, 576], dtype=int)
    expected_reactance: np.ndarray = np.asarray(
        [0.6, 1.2, 1.2, 0.6], dtype=float
    )
    event_values_are_exact: bool = bool(
        np.allclose(
            libcosim_trace.plant_effective_reactance_pu[oracle_rows],
            expected_reactance, rtol=0.0, atol=1e-12,
        )
        and np.allclose(
            veragrid_trace.plant_effective_reactance_pu[oracle_rows],
            expected_reactance, rtol=0.0, atol=1e-12,
        )
    )
    departures: tuple[float, float, float, float] = (
        float(np.max(np.abs(
            libcosim_trace.plant_angle_rad - libcosim_trace.plant_angle_rad[0]
        ))),
        float(np.max(np.abs(
            libcosim_trace.plant_speed_pu - libcosim_trace.plant_speed_pu[0]
        ))),
        float(np.max(np.abs(
            libcosim_trace.plant_electrical_power_pu
            - libcosim_trace.plant_electrical_power_pu[0]
        ))),
        float(np.max(np.abs(
            libcosim_trace.controller_mechanical_control_output_pu
            - libcosim_trace.controller_mechanical_control_output_pu[0]
        ))),
    )
    comparison_passes: bool = bool(
        maximum_time_error <= 1e-12
        and all(metric.serialization_mismatch_count == 0 for metric in signal_metrics)
        and event_values_are_exact
        and departures[0] > 0.1
        and departures[1] > 0.001
        and departures[2] > 0.1
        and departures[3] > 0.01
    )
    if comparison_passes:
        pass
    else:
        raise ValueError("Libcosim comparison failed its numerical contract")
    return LibcosimComparisonMetrics(
        maximum_time_error_seconds=maximum_time_error,
        plant_angle=signal_metrics[0], plant_speed=signal_metrics[1],
        plant_electrical_power=signal_metrics[2],
        plant_effective_reactance=signal_metrics[3],
        plant_mechanical_control_input=signal_metrics[4],
        controller_speed_input=signal_metrics[5],
        controller_mechanical_control_output=signal_metrics[6],
        plant_angle_material_departure_rad=departures[0],
        plant_speed_material_departure_pu=departures[1],
        plant_electrical_power_material_departure_pu=departures[2],
        controller_mechanical_control_material_departure_pu=departures[3],
    )


def _render_libcosim_figures(
    libcosim_trace: LibcosimTrace,
    veragrid_trace: LibcosimTrace,
    figure_directory: Path,
) -> None:
    """Render the four-panel scientific overlay in three formats.

    :param libcosim_trace: Accepted native libcosim trace.
    :param veragrid_trace: Accepted VeraGrid reference trace.
    :param figure_directory: Existing package figure directory.
    :return: None after PNG, SVG and PDF are written.
    """

    native_signals: tuple[np.ndarray, ...] = (
        libcosim_trace.plant_angle_rad, libcosim_trace.plant_speed_pu,
        libcosim_trace.plant_electrical_power_pu,
        libcosim_trace.controller_mechanical_control_output_pu,
    )
    reference_signals: tuple[np.ndarray, ...] = (
        veragrid_trace.plant_angle_rad, veragrid_trace.plant_speed_pu,
        veragrid_trace.plant_electrical_power_pu,
        veragrid_trace.controller_mechanical_control_output_pu,
    )
    y_labels: tuple[str, ...] = (
        "Rotor angle [rad]", "Speed deviation [p.u.]",
        "Electrical power [p.u.]", "Controller action [p.u.]",
    )
    style: dict[str, object] = {
        "font.family": "DejaVu Sans", "font.size": 8.5,
        "axes.labelsize": 8.5, "axes.titlesize": 9.0,
        "legend.fontsize": 7.5, "xtick.labelsize": 7.5,
        "ytick.labelsize": 7.5, "axes.linewidth": 0.7,
        "pdf.fonttype": 42, "ps.fonttype": 42,
        "svg.fonttype": "none", "savefig.facecolor": "white",
    }
    with mpl.rc_context(style):
        figure: Figure
        axes: np.ndarray
        figure, axes = plt.subplots(
            4, 1, figsize=(7.2, 7.0), sharex=True,
            constrained_layout=True,
        )
        panel_index: int
        for panel_index in range(4):
            axis: Axes = axes[panel_index]
            axis.plot(
                veragrid_trace.time_values, reference_signals[panel_index],
                color="#1f4e79", linewidth=1.25, linestyle="-",
                label="VeraGrid",
            )
            axis.plot(
                libcosim_trace.time_values, native_signals[panel_index],
                color="#202020", linewidth=0.95, linestyle="--",
                label="libcosim",
            )
            axis.axvline(
                1.001, color="#777777", linewidth=0.75, linestyle=":"
            )
            axis.axvline(
                1.151, color="#777777", linewidth=0.75, linestyle=":"
            )
            axis.set_ylabel(y_labels[panel_index])
            axis.grid(True, color="#d7d7d7", linewidth=0.45)
            axis.margins(x=0.0)
            if panel_index == 0:
                axis.legend(loc="best", frameon=False, ncol=2)
                axis.text(
                    1.001, 1.02, "fault applied",
                    transform=axis.get_xaxis_transform(), ha="right",
                    va="bottom", fontsize=7.0,
                )
                axis.text(
                    1.151, 1.02, "fault cleared",
                    transform=axis.get_xaxis_transform(), ha="left",
                    va="bottom", fontsize=7.0,
                )
            else:
                pass
        axes[3].set_xlabel("Time [s]")
        figure.suptitle(
            "SMIB delayed two-FMU composition: VeraGrid and libcosim",
            fontsize=10.0,
        )
        output_stem: Path = figure_directory / "libcosim-smib-composition"
        figure.savefig(output_stem.with_suffix(".png"), dpi=300)
        figure.savefig(output_stem.with_suffix(".svg"))
        figure.savefig(output_stem.with_suffix(".pdf"))
        figure.clear()
        plt.close(figure)
    png_pixels: np.ndarray = mpimg.imread(
        figure_directory / "libcosim-smib-composition.png"
    )
    if png_pixels.shape[0] == 2100 and png_pixels.shape[1] == 2160:
        pass
    else:
        raise ValueError("Libcosim PNG geometry differs from the sealed figure")


def _write_libcosim_manifest(
    package_directory: Path,
    config: LibcosimComparisonConfig,
    version_result: LibcosimProcessResult,
    run_result: LibcosimProcessResult,
    native_plant_csv_name: str,
    native_plant_metadata_name: str,
    native_controller_csv_name: str,
    native_controller_metadata_name: str,
    metrics: LibcosimComparisonMetrics,
) -> Path:
    """Write the closed provenance and numerical manifest.

    :param package_directory: Unpublished package root.
    :param config: Sealed comparison configuration.
    :param version_result: Captured native version process.
    :param run_result: Captured native simulation process.
    :param native_plant_csv_name: Original timestamped plant CSV name.
    :param native_plant_metadata_name: Original plant metadata name.
    :param native_controller_csv_name: Original controller CSV name.
    :param native_controller_metadata_name: Original controller metadata name.
    :param metrics: Accepted numerical comparison metrics.
    :return: Written manifest path.
    """

    signal_names: tuple[str, ...] = (
        "plant_angle", "plant_speed", "plant_electrical_power",
        "plant_effective_reactance", "plant_mechanical_control_input",
        "controller_speed_input", "controller_mechanical_control_output",
    )
    metric_values: tuple[LibcosimSignalMetrics, ...] = (
        metrics.plant_angle, metrics.plant_speed,
        metrics.plant_electrical_power, metrics.plant_effective_reactance,
        metrics.plant_mechanical_control_input, metrics.controller_speed_input,
        metrics.controller_mechanical_control_output,
    )
    signal_metrics: dict[str, object] = dict()
    signal_index: int
    for signal_index in range(7):
        signal_metric: LibcosimSignalMetrics = metric_values[signal_index]
        signal_metrics[signal_names[signal_index]] = {
            "maximum_absolute_error": signal_metric.maximum_absolute_error,
            "rms_absolute_error": signal_metric.rms_absolute_error,
            "serialization_mismatch_count": (
                signal_metric.serialization_mismatch_count
            ),
        }
    reference_trace_path: Path = (
        config.reference_manifest_path.parent
        / "raw" / "veragrid-closed-outputs.csv"
    )
    reference_manifest: dict[str, object] = json.loads(
        config.reference_manifest_path.read_text(encoding="utf-8")
    )
    file_paths: tuple[str, ...] = (
        "inputs/OspSystemStructure.xml", "inputs/LogConfig.xml",
        "raw/libcosim-version-stdout.log",
        "raw/libcosim-version-stderr.log",
        "raw/libcosim-run-stdout.log", "raw/libcosim-run-stderr.log",
        "raw/libcosim-plant.csv", "raw/libcosim-controller.csv",
        "raw/libcosim-plant-metadata.yaml",
        "raw/libcosim-controller-metadata.yaml",
        "raw/veragrid-reference.csv",
        "figures/libcosim-smib-composition.png",
        "figures/libcosim-smib-composition.svg",
        "figures/libcosim-smib-composition.pdf",
    )
    file_records: list[dict[str, object]] = list()
    relative_path: str
    for relative_path in file_paths:
        artifact_path: Path = package_directory / relative_path
        artifact_bytes: bytes = artifact_path.read_bytes()
        file_records.append({
            "path": relative_path,
            "size_bytes": len(artifact_bytes),
            "sha256": hashlib.sha256(artifact_bytes).hexdigest(),
        })
    manifest: dict[str, object] = {
        "schema": "veragrid.fmi-libcosim-comparison/1",
        "status": "PASS",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "branch": config.source_branch,
            "revision": config.source_revision,
            "tree_sha256": config.source_tree_sha256,
        },
        "runtime": {
            "architecture": config.wsl_expected_architecture,
            "bundle_label": "0.9.0",
            "bundle_path": str(config.libcosim_bundle_path),
            "bundle_sha256": config.libcosim_bundle_expected_sha256,
            "bundle_size_bytes": config.libcosim_bundle_expected_size_bytes,
            "cosim_reported_version": config.libcosim_expected_cosim_version,
            "distribution_name": config.wsl_distribution_name,
            "distribution_pretty_name": (
                config.wsl_expected_distribution_pretty_name
            ),
            "distribution_version_id": (
                config.wsl_expected_distribution_version_id
            ),
            "extracted_file_count": 22,
            "extracted_total_size_bytes": 18_086_364,
            "extracted_tree_sha256": (
                "363bbda9f3e72c65a86bdb443c7d914f6275dddfb83df250819aebe5d689a1d4"
            ),
            "glibc_version": config.wsl_expected_glibc_version,
            "kernel": config.wsl_expected_kernel,
            "libcosim_reported_version": (
                config.libcosim_expected_library_version
            ),
            "wsl_executable_path": str(config.wsl_executable_path),
            "wsl_executable_sha256": config.wsl_executable_expected_sha256,
            "wsl_executable_size_bytes": (
                config.wsl_executable_expected_size_bytes
            ),
            "wsl_version": config.wsl_expected_version,
        },
        "inputs": {
            "governor_fmu": {
                "path": str(config.governor_fmu_path),
                "size_bytes": config.governor_fmu_expected_size_bytes,
                "sha256": config.governor_fmu_expected_sha256,
            },
            "plant_fmu": {
                "path": str(config.plant_fmu_path),
                "size_bytes": config.plant_fmu_expected_size_bytes,
                "sha256": config.plant_fmu_expected_sha256,
            },
            "reference_manifest": {
                "path": str(config.reference_manifest_path),
                "size_bytes": config.reference_manifest_expected_size_bytes,
                "sha256": config.reference_manifest_expected_sha256,
                "schema": reference_manifest["schema"],
                "status": reference_manifest["status"],
            },
            "reference_trace": {
                "path": str(reference_trace_path), "size_bytes": 279_085,
                "sha256": (
                    "5dd944e79ca8646f377d31bd63e6f8c41069ee69c349063be082ee904e04ec45"
                ),
                "row_count": 2001,
            },
        },
        "execution": {
            "communication_step_seconds": 0.002,
            "controller_gain": 4.0, "end_time_seconds": 4.0,
            "native_outputs": {
                "native_plant_csv_name": native_plant_csv_name,
                "native_plant_metadata_name": native_plant_metadata_name,
                "native_controller_csv_name": native_controller_csv_name,
                "native_controller_metadata_name": (
                    native_controller_metadata_name
                ),
            },
            "run_process": {
                "exit_code": run_result.exit_code,
                "stdout_relative_path": "raw/libcosim-run-stdout.log",
                "stderr_relative_path": "raw/libcosim-run-stderr.log",
            },
            "start_time_seconds": 0.0,
            "version_process": {
                "exit_code": version_result.exit_code,
                "stdout_relative_path": "raw/libcosim-version-stdout.log",
                "stderr_relative_path": "raw/libcosim-version-stderr.log",
            },
        },
        "comparison": {
            "material_departures": {
                "plant_angle_rad": metrics.plant_angle_material_departure_rad,
                "plant_speed_pu": metrics.plant_speed_material_departure_pu,
                "plant_electrical_power_pu": (
                    metrics.plant_electrical_power_material_departure_pu
                ),
                "controller_mechanical_control_output_pu": (
                    metrics.controller_mechanical_control_material_departure_pu
                ),
            },
            "maximum_time_error_seconds": metrics.maximum_time_error_seconds,
            "row_count": 2001, "signal_count": 7,
            "signal_metrics": signal_metrics,
            "token_comparison_count": 14_007,
        },
        "event_family": {
            "apply_time_seconds": 1.001, "clear_time_seconds": 1.151,
            "effective_reactance_pu": [0.6, 1.2, 1.2, 0.6],
            "name": "SMIB network-reactance fault application and clearing",
            "oracle_rows": [500, 501, 575, 576],
        },
        "figures": {
            "dpi": 300, "formats": ["png", "svg", "pdf"],
            "height_inches": 7.0,
            "panels": [
                "angle_rad", "speed_pu", "electrical_power_pu",
                "controller_action_pu",
            ],
            "png_height_pixels": 2100, "png_width_pixels": 2160,
            "width_inches": 7.2,
        },
        "files": file_records,
    }
    manifest_path: Path = package_directory / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    return manifest_path


def _verify_libcosim_package(
    package_directory: Path,
    config: LibcosimComparisonConfig,
) -> None:
    """Reopen the package and recompute decisive evidence.

    :param package_directory: Unpublished candidate package.
    :param config: Sealed comparison configuration.
    :return: None after exact closure and numerical verification.
    """

    expected_paths: set[str] = {
        "inputs/OspSystemStructure.xml", "inputs/LogConfig.xml",
        "raw/libcosim-version-stdout.log",
        "raw/libcosim-version-stderr.log",
        "raw/libcosim-run-stdout.log", "raw/libcosim-run-stderr.log",
        "raw/libcosim-plant.csv", "raw/libcosim-controller.csv",
        "raw/libcosim-plant-metadata.yaml",
        "raw/libcosim-controller-metadata.yaml",
        "raw/veragrid-reference.csv",
        "figures/libcosim-smib-composition.png",
        "figures/libcosim-smib-composition.svg",
        "figures/libcosim-smib-composition.pdf", "manifest.json",
    }
    observed_paths: set[str] = set()
    observed_path: Path
    for observed_path in package_directory.rglob("*"):
        if observed_path.is_file() and not observed_path.is_symlink():
            observed_paths.add(observed_path.relative_to(package_directory).as_posix())
        else:
            if observed_path.is_symlink():
                raise ValueError("Libcosim package contains a symbolic link")
            else:
                pass
    if observed_paths == expected_paths:
        pass
    else:
        raise ValueError("Libcosim package differs from the sealed fifteen files")
    manifest_value: object = json.loads(
        (package_directory / "manifest.json").read_text(encoding="utf-8")
    )
    if isinstance(manifest_value, dict):
        manifest: dict[str, object] = manifest_value
    else:
        raise ValueError("Libcosim manifest is not an object")
    expected_top_keys: set[str] = {
        "schema", "status", "generated_at_utc", "source", "runtime",
        "inputs", "execution", "comparison", "event_family", "figures",
        "files",
    }
    if (
        set(manifest) == expected_top_keys
        and manifest["schema"] == "veragrid.fmi-libcosim-comparison/1"
        and manifest["status"] == "PASS"
    ):
        pass
    else:
        raise ValueError("Libcosim manifest top-level schema changed")
    files_value: object = manifest["files"]
    declared_paths: set[str] = set()
    if isinstance(files_value, list) and len(files_value) == 14:
        file_record: object
        for file_record in files_value:
            if isinstance(file_record, dict) and set(file_record) == {
                "path", "sha256", "size_bytes"
            }:
                record_path_value: object = file_record["path"]
                record_size_value: object = file_record["size_bytes"]
                record_sha256_value: object = file_record["sha256"]
                if (
                    isinstance(record_path_value, str)
                    and type(record_size_value) is int
                    and isinstance(record_sha256_value, str)
                    and re.fullmatch(
                        r"[0-9a-f]{64}", record_sha256_value
                    ) is not None
                    and record_path_value in expected_paths
                    and record_path_value != "manifest.json"
                ):
                    artifact_bytes: bytes = (
                        package_directory / record_path_value
                    ).read_bytes()
                    record_matches: bool = bool(
                        record_size_value == len(artifact_bytes)
                        and record_sha256_value
                        == hashlib.sha256(artifact_bytes).hexdigest()
                    )
                    if record_matches and record_path_value not in declared_paths:
                        declared_paths.add(record_path_value)
                    else:
                        raise ValueError("A libcosim file record is inconsistent")
                else:
                    raise ValueError("A libcosim file record path is invalid")
            else:
                raise ValueError("Libcosim file record schema changed")
    else:
        raise ValueError("Libcosim manifest must declare fourteen artifacts")
    if declared_paths == expected_paths - {"manifest.json"}:
        pass
    else:
        raise ValueError("Libcosim manifest does not close every artifact")
    source_expected: dict[str, object] = {
        "branch": config.source_branch,
        "revision": config.source_revision,
        "tree_sha256": config.source_tree_sha256,
    }
    runtime_expected: dict[str, object] = {
        "architecture": config.wsl_expected_architecture,
        "bundle_label": "0.9.0",
        "bundle_path": str(config.libcosim_bundle_path),
        "bundle_sha256": config.libcosim_bundle_expected_sha256,
        "bundle_size_bytes": config.libcosim_bundle_expected_size_bytes,
        "cosim_reported_version": config.libcosim_expected_cosim_version,
        "distribution_name": config.wsl_distribution_name,
        "distribution_pretty_name": (
            config.wsl_expected_distribution_pretty_name
        ),
        "distribution_version_id": config.wsl_expected_distribution_version_id,
        "extracted_file_count": 22,
        "extracted_total_size_bytes": 18_086_364,
        "extracted_tree_sha256": (
            "363bbda9f3e72c65a86bdb443c7d914f6275dddfb83df250819aebe5d689a1d4"
        ),
        "glibc_version": config.wsl_expected_glibc_version,
        "kernel": config.wsl_expected_kernel,
        "libcosim_reported_version": config.libcosim_expected_library_version,
        "wsl_executable_path": str(config.wsl_executable_path),
        "wsl_executable_sha256": config.wsl_executable_expected_sha256,
        "wsl_executable_size_bytes": config.wsl_executable_expected_size_bytes,
        "wsl_version": config.wsl_expected_version,
    }
    reference_trace_path: Path = (
        config.reference_manifest_path.parent
        / "raw" / "veragrid-closed-outputs.csv"
    )
    inputs_expected: dict[str, object] = {
        "governor_fmu": {
            "path": str(config.governor_fmu_path),
            "size_bytes": config.governor_fmu_expected_size_bytes,
            "sha256": config.governor_fmu_expected_sha256,
        },
        "plant_fmu": {
            "path": str(config.plant_fmu_path),
            "size_bytes": config.plant_fmu_expected_size_bytes,
            "sha256": config.plant_fmu_expected_sha256,
        },
        "reference_manifest": {
            "path": str(config.reference_manifest_path),
            "size_bytes": config.reference_manifest_expected_size_bytes,
            "sha256": config.reference_manifest_expected_sha256,
            "schema": "veragrid.fmi-maestro-comparison/1",
            "status": "PASS",
        },
        "reference_trace": {
            "path": str(reference_trace_path),
            "size_bytes": 279_085,
            "sha256": (
                "5dd944e79ca8646f377d31bd63e6f8c41069ee69c349063be082ee904e04ec45"
            ),
            "row_count": 2001,
        },
    }
    generated_at_value: object = manifest["generated_at_utc"]
    source_value: object = manifest["source"]
    runtime_value: object = manifest["runtime"]
    inputs_value: object = manifest["inputs"]
    provenance_types_match: bool = False
    if (
        isinstance(source_value, dict)
        and isinstance(runtime_value, dict)
        and isinstance(inputs_value, dict)
    ):
        governor_fmu_value: object = inputs_value.get("governor_fmu", None)
        plant_fmu_value: object = inputs_value.get("plant_fmu", None)
        reference_manifest_value: object = inputs_value.get(
            "reference_manifest", None
        )
        reference_trace_value: object = inputs_value.get(
            "reference_trace", None
        )
        if (
            isinstance(governor_fmu_value, dict)
            and isinstance(plant_fmu_value, dict)
            and isinstance(reference_manifest_value, dict)
            and isinstance(reference_trace_value, dict)
        ):
            typed_provenance_values: tuple[tuple[object, type[object]], ...] = (
                (source_value.get("branch", None), str),
                (source_value.get("revision", None), str),
                (source_value.get("tree_sha256", None), str),
                (runtime_value.get("architecture", None), str),
                (runtime_value.get("bundle_label", None), str),
                (runtime_value.get("bundle_path", None), str),
                (runtime_value.get("bundle_sha256", None), str),
                (runtime_value.get("bundle_size_bytes", None), int),
                (runtime_value.get("cosim_reported_version", None), str),
                (runtime_value.get("distribution_name", None), str),
                (runtime_value.get("distribution_pretty_name", None), str),
                (runtime_value.get("distribution_version_id", None), str),
                (runtime_value.get("extracted_file_count", None), int),
                (runtime_value.get("extracted_total_size_bytes", None), int),
                (runtime_value.get("extracted_tree_sha256", None), str),
                (runtime_value.get("glibc_version", None), str),
                (runtime_value.get("kernel", None), str),
                (runtime_value.get("libcosim_reported_version", None), str),
                (runtime_value.get("wsl_executable_path", None), str),
                (runtime_value.get("wsl_executable_sha256", None), str),
                (runtime_value.get("wsl_executable_size_bytes", None), int),
                (runtime_value.get("wsl_version", None), str),
                (governor_fmu_value.get("path", None), str),
                (governor_fmu_value.get("size_bytes", None), int),
                (governor_fmu_value.get("sha256", None), str),
                (plant_fmu_value.get("path", None), str),
                (plant_fmu_value.get("size_bytes", None), int),
                (plant_fmu_value.get("sha256", None), str),
                (reference_manifest_value.get("path", None), str),
                (reference_manifest_value.get("size_bytes", None), int),
                (reference_manifest_value.get("sha256", None), str),
                (reference_manifest_value.get("schema", None), str),
                (reference_manifest_value.get("status", None), str),
                (reference_trace_value.get("path", None), str),
                (reference_trace_value.get("size_bytes", None), int),
                (reference_trace_value.get("sha256", None), str),
                (reference_trace_value.get("row_count", None), int),
            )
            provenance_types_match = all(
                type(typed_value) is expected_tpe
                for typed_value, expected_tpe in typed_provenance_values
            )
        else:
            provenance_types_match = False
    else:
        provenance_types_match = False
    if (
        source_value == source_expected
        and runtime_value == runtime_expected
        and inputs_value == inputs_expected
        and type(generated_at_value) is str
        and datetime.fromisoformat(generated_at_value).tzinfo is not None
        and provenance_types_match
    ):
        pass
    else:
        raise ValueError("Libcosim provenance schema or identity changed")
    execution_value: object = manifest["execution"]
    execution_matches: bool = False
    if isinstance(execution_value, dict) and set(execution_value) == {
        "communication_step_seconds", "controller_gain", "end_time_seconds",
        "native_outputs", "run_process", "start_time_seconds",
        "version_process",
    }:
        native_outputs_value: object = execution_value["native_outputs"]
        run_process_value: object = execution_value["run_process"]
        version_process_value: object = execution_value["version_process"]
        if (
            isinstance(native_outputs_value, dict)
            and set(native_outputs_value) == {
                "native_controller_csv_name",
                "native_controller_metadata_name",
                "native_plant_csv_name",
                "native_plant_metadata_name",
            }
            and isinstance(run_process_value, dict)
            and run_process_value == {
                "exit_code": 0,
                "stdout_relative_path": "raw/libcosim-run-stdout.log",
                "stderr_relative_path": "raw/libcosim-run-stderr.log",
            }
            and isinstance(version_process_value, dict)
            and version_process_value == {
                "exit_code": 0,
                "stdout_relative_path": "raw/libcosim-version-stdout.log",
                "stderr_relative_path": "raw/libcosim-version-stderr.log",
            }
        ):
            native_plant_csv_value: object = native_outputs_value[
                "native_plant_csv_name"
            ]
            native_controller_csv_value: object = native_outputs_value[
                "native_controller_csv_name"
            ]
            native_plant_metadata_value: object = native_outputs_value[
                "native_plant_metadata_name"
            ]
            native_controller_metadata_value: object = native_outputs_value[
                "native_controller_metadata_name"
            ]
            execution_matches = bool(
                execution_value["communication_step_seconds"] == 0.002
                and type(execution_value["communication_step_seconds"]) is float
                and execution_value["controller_gain"] == 4.0
                and type(execution_value["controller_gain"]) is float
                and execution_value["end_time_seconds"] == 4.0
                and type(execution_value["end_time_seconds"]) is float
                and execution_value["start_time_seconds"] == 0.0
                and type(execution_value["start_time_seconds"]) is float
                and type(run_process_value.get("exit_code", None)) is int
                and type(version_process_value.get("exit_code", None)) is int
                and isinstance(native_plant_csv_value, str)
                and isinstance(native_controller_csv_value, str)
                and isinstance(native_plant_metadata_value, str)
                and isinstance(native_controller_metadata_value, str)
                and re.fullmatch(
                    r"plant_[0-9]{8}_[0-9]{6}_[0-9]{6}\.csv",
                    native_plant_csv_value,
                ) is not None
                and re.fullmatch(
                    r"controller_[0-9]{8}_[0-9]{6}_[0-9]{6}\.csv",
                    native_controller_csv_value,
                ) is not None
                and native_plant_metadata_value
                == native_plant_csv_value.removesuffix(".csv") + "_metadata.yaml"
                and native_controller_metadata_value
                == native_controller_csv_value.removesuffix(".csv")
                + "_metadata.yaml"
            )
        else:
            execution_matches = False
    else:
        execution_matches = False
    if execution_matches:
        pass
    else:
        raise ValueError("Libcosim execution schema or values changed")
    native_trace: LibcosimTrace = _parse_libcosim_trace(
        package_directory / "raw" / "libcosim-plant.csv",
        package_directory / "raw" / "libcosim-controller.csv",
    )
    reference_trace: LibcosimTrace = _parse_veragrid_reference_trace(
        package_directory / "raw" / "veragrid-reference.csv"
    )
    recomputed_metrics: LibcosimComparisonMetrics = (
        _evaluate_libcosim_comparison(native_trace, reference_trace)
    )
    signal_names: tuple[str, ...] = (
        "plant_angle", "plant_speed", "plant_electrical_power",
        "plant_effective_reactance", "plant_mechanical_control_input",
        "controller_speed_input", "controller_mechanical_control_output",
    )
    recomputed_signal_values: tuple[LibcosimSignalMetrics, ...] = (
        recomputed_metrics.plant_angle, recomputed_metrics.plant_speed,
        recomputed_metrics.plant_electrical_power,
        recomputed_metrics.plant_effective_reactance,
        recomputed_metrics.plant_mechanical_control_input,
        recomputed_metrics.controller_speed_input,
        recomputed_metrics.controller_mechanical_control_output,
    )
    expected_signal_metrics: dict[str, object] = dict()
    signal_index: int
    for signal_index in range(7):
        recomputed_signal: LibcosimSignalMetrics = (
            recomputed_signal_values[signal_index]
        )
        expected_signal_metrics[signal_names[signal_index]] = {
            "maximum_absolute_error": recomputed_signal.maximum_absolute_error,
            "rms_absolute_error": recomputed_signal.rms_absolute_error,
            "serialization_mismatch_count": (
                recomputed_signal.serialization_mismatch_count
            ),
        }
    expected_material_departures: dict[str, object] = {
        "plant_angle_rad": (
            recomputed_metrics.plant_angle_material_departure_rad
        ),
        "plant_speed_pu": (
            recomputed_metrics.plant_speed_material_departure_pu
        ),
        "plant_electrical_power_pu": (
            recomputed_metrics.plant_electrical_power_material_departure_pu
        ),
        "controller_mechanical_control_output_pu": (
            recomputed_metrics.controller_mechanical_control_material_departure_pu
        ),
    }
    comparison_value: object = manifest["comparison"]
    if isinstance(comparison_value, dict):
        material_departures_value: object = comparison_value.get(
            "material_departures", None
        )
        signal_metrics_value: object = comparison_value.get(
            "signal_metrics", None
        )
        metric_types_match: bool = False
        if (
            isinstance(material_departures_value, dict)
            and isinstance(signal_metrics_value, dict)
            and set(material_departures_value)
            == set(expected_material_departures)
            and set(signal_metrics_value) == set(expected_signal_metrics)
        ):
            signal_metric_types_match: bool = True
            signal_name: str
            for signal_name in signal_names:
                signal_metric_value: object = signal_metrics_value.get(
                    signal_name, None
                )
                if (
                    isinstance(signal_metric_value, dict)
                    and set(signal_metric_value) == {
                        "maximum_absolute_error",
                        "rms_absolute_error",
                        "serialization_mismatch_count",
                    }
                    and type(
                        signal_metric_value.get(
                            "maximum_absolute_error", None
                        )
                    ) is float
                    and type(
                        signal_metric_value.get("rms_absolute_error", None)
                    ) is float
                    and type(
                        signal_metric_value.get(
                            "serialization_mismatch_count", None
                        )
                    ) is int
                ):
                    pass
                else:
                    signal_metric_types_match = False
            metric_types_match = bool(
                signal_metric_types_match
                and type(
                    material_departures_value.get("plant_angle_rad", None)
                ) is float
                and type(
                    material_departures_value.get("plant_speed_pu", None)
                ) is float
                and type(
                    material_departures_value.get(
                        "plant_electrical_power_pu", None
                    )
                ) is float
                and type(
                    material_departures_value.get(
                        "controller_mechanical_control_output_pu", None
                    )
                ) is float
                and type(
                    comparison_value.get("maximum_time_error_seconds", None)
                ) is float
                and type(comparison_value.get("row_count", None)) is int
                and type(comparison_value.get("signal_count", None)) is int
                and type(
                    comparison_value.get("token_comparison_count", None)
                ) is int
            )
        else:
            metric_types_match = False
        decisive_values_match: bool = bool(
            set(comparison_value) == {
                "material_departures", "maximum_time_error_seconds",
                "row_count", "signal_count", "signal_metrics",
                "token_comparison_count",
            }
            and comparison_value.get("row_count", None) == 2001
            and comparison_value.get("signal_count", None) == 7
            and comparison_value.get("token_comparison_count", None) == 14_007
            and comparison_value.get("maximum_time_error_seconds", None)
            == recomputed_metrics.maximum_time_error_seconds
            and comparison_value.get("material_departures", None)
            == expected_material_departures
            and comparison_value.get("signal_metrics", None)
            == expected_signal_metrics
            and metric_types_match
        )
    else:
        decisive_values_match = False
    expected_event_family: dict[str, object] = {
        "apply_time_seconds": 1.001,
        "clear_time_seconds": 1.151,
        "effective_reactance_pu": [0.6, 1.2, 1.2, 0.6],
        "name": "SMIB network-reactance fault application and clearing",
        "oracle_rows": [500, 501, 575, 576],
    }
    expected_figure_contract: dict[str, object] = {
        "dpi": 300, "formats": ["png", "svg", "pdf"],
        "height_inches": 7.0,
        "panels": [
            "angle_rad", "speed_pu", "electrical_power_pu",
            "controller_action_pu",
        ],
        "png_height_pixels": 2100, "png_width_pixels": 2160,
        "width_inches": 7.2,
    }
    event_family_value: object = manifest["event_family"]
    figures_value: object = manifest["figures"]
    event_and_figure_types_match: bool = False
    if (
        isinstance(event_family_value, dict)
        and isinstance(figures_value, dict)
    ):
        effective_reactance_value: object = event_family_value.get(
            "effective_reactance_pu", None
        )
        oracle_rows_value: object = event_family_value.get(
            "oracle_rows", None
        )
        formats_value: object = figures_value.get("formats", None)
        panels_value: object = figures_value.get("panels", None)
        event_and_figure_types_match = bool(
            type(event_family_value.get("apply_time_seconds", None)) is float
            and type(event_family_value.get("clear_time_seconds", None))
            is float
            and type(event_family_value.get("name", None)) is str
            and isinstance(effective_reactance_value, list)
            and len(effective_reactance_value) == 4
            and all(
                type(reactance_value) is float
                for reactance_value in effective_reactance_value
            )
            and isinstance(oracle_rows_value, list)
            and len(oracle_rows_value) == 4
            and all(
                type(oracle_row_value) is int
                for oracle_row_value in oracle_rows_value
            )
            and type(figures_value.get("dpi", None)) is int
            and type(figures_value.get("height_inches", None)) is float
            and type(figures_value.get("png_height_pixels", None)) is int
            and type(figures_value.get("png_width_pixels", None)) is int
            and type(figures_value.get("width_inches", None)) is float
            and isinstance(formats_value, list)
            and all(type(format_value) is str for format_value in formats_value)
            and isinstance(panels_value, list)
            and all(type(panel_value) is str for panel_value in panels_value)
        )
    else:
        event_and_figure_types_match = False
    png_pixels: np.ndarray = mpimg.imread(
        package_directory / "figures" / "libcosim-smib-composition.png"
    )
    svg_text: str = (
        package_directory / "figures" / "libcosim-smib-composition.svg"
    ).read_text(encoding="utf-8", errors="strict")
    pdf_bytes: bytes = (
        package_directory / "figures" / "libcosim-smib-composition.pdf"
    ).read_bytes()
    if (
        decisive_values_match
        and event_family_value == expected_event_family
        and figures_value == expected_figure_contract
        and event_and_figure_types_match
        and png_pixels.shape[0] == 2100
        and png_pixels.shape[1] == 2160
        and 'width="518.4pt"' in svg_text
        and 'height="504pt"' in svg_text
        and "<text" in svg_text
        and b"/MediaBox [ 0 0 518.4 504 ]" in pdf_bytes
        and (b"/FontFile2" in pdf_bytes or b"/CIDFontType2" in pdf_bytes)
    ):
        pass
    else:
        raise ValueError("Libcosim metrics or figure contract changed")


def generate_libcosim_comparison(config: LibcosimComparisonConfig) -> Path:
    """Execute libcosim and atomically publish verified evidence.

    :param config: Sealed comparison configuration.
    :return: Final verified manifest path.
    """

    _validate_libcosim_config(config)
    _validate_libcosim_platform(config)
    work_root: Path = Path(tempfile.mkdtemp(
        prefix=".libcosim-", dir=config.output_directory.parent
    ))
    package_directory: Path = work_root / "package"
    published: bool = False
    try:
        package_directory.mkdir()
        input_directory: Path = work_root / "native-input"
        native_output_directory: Path = work_root / "native-output"
        native_output_directory.mkdir()
        runtime_root: Path = work_root / "runtime"
        raw_directory: Path = package_directory / "raw"
        figure_directory: Path = package_directory / "figures"
        package_input_directory: Path = package_directory / "inputs"
        raw_directory.mkdir()
        figure_directory.mkdir()
        package_input_directory.mkdir()
        cosim_path: Path = _extract_libcosim_bundle(config, runtime_root)
        _write_libcosim_inputs(
            input_directory, config.plant_fmu_path, config.governor_fmu_path
        )
        shutil.copyfile(
            input_directory / "OspSystemStructure.xml",
            package_input_directory / "OspSystemStructure.xml",
        )
        shutil.copyfile(
            input_directory / "LogConfig.xml",
            package_input_directory / "LogConfig.xml",
        )
        staged_plant_fmu_path: Path = (
            input_directory / "SMIBNetworkPlant.fmu"
        )
        staged_governor_fmu_path: Path = (
            input_directory / "SMIBGovernorController.fmu"
        )
        verify_regular_file_identity(
            staged_plant_fmu_path,
            config.plant_fmu_expected_size_bytes,
            config.plant_fmu_expected_sha256,
        )
        verify_regular_file_identity(
            staged_governor_fmu_path,
            config.governor_fmu_expected_size_bytes,
            config.governor_fmu_expected_sha256,
        )
        input_tree_identity: tuple[int, int, str] = (
            read_regular_tree_identity(input_directory)
        )
        if input_tree_identity[0] == 4:
            pass
        else:
            raise ValueError("Libcosim native input tree must contain four files")
        cosim_wsl_path: str = _translate_windows_path_to_wsl(cosim_path)
        input_wsl_path: str = _translate_windows_path_to_wsl(input_directory)
        output_wsl_path: str = _translate_windows_path_to_wsl(native_output_directory)
        wsl_path: str = str(config.wsl_executable_path)
        version_result: LibcosimProcessResult = _run_libcosim_process(
            [
                wsl_path, "-d", config.wsl_distribution_name, "--",
                cosim_wsl_path, "--version",
            ],
            config.process_timeout_seconds, config.stream_limit_bytes,
            LibcosimStreamEncoding.UTF8,
        )
        if (
            version_result.exit_code == 0
            and version_result.stdout_text
            == (
                "cosim " + config.libcosim_expected_cosim_version + "\n"
                + "Using libcosim "
                + config.libcosim_expected_library_version
                + "\n"
            )
            and version_result.stderr_text == ""
        ):
            pass
        else:
            raise ValueError("Libcosim native version output changed")
        if len(list(native_output_directory.iterdir())) == 0:
            pass
        else:
            raise ValueError("Libcosim output directory was not initially empty")
        run_result: LibcosimProcessResult = _run_libcosim_process(
            [
                wsl_path, "-d", config.wsl_distribution_name, "--",
                cosim_wsl_path, "run", input_wsl_path,
                "--end-time=4.0", "--output-dir=" + output_wsl_path, "-v",
            ],
            config.process_timeout_seconds, config.stream_limit_bytes,
            LibcosimStreamEncoding.UTF8,
        )
        if run_result.exit_code == 0:
            pass
        else:
            raise ValueError("Libcosim native simulation failed")
        verify_regular_file_identity(
            staged_plant_fmu_path,
            config.plant_fmu_expected_size_bytes,
            config.plant_fmu_expected_sha256,
        )
        verify_regular_file_identity(
            staged_governor_fmu_path,
            config.governor_fmu_expected_size_bytes,
            config.governor_fmu_expected_sha256,
        )
        if (
            read_regular_tree_identity(input_directory) == input_tree_identity
            and (
                input_directory / "OspSystemStructure.xml"
            ).read_bytes()
            == (
                package_input_directory / "OspSystemStructure.xml"
            ).read_bytes()
            and (input_directory / "LogConfig.xml").read_bytes()
            == (package_input_directory / "LogConfig.xml").read_bytes()
        ):
            pass
        else:
            raise ValueError("Libcosim native inputs changed during execution")
        output_files: list[Path] = sorted(native_output_directory.iterdir())
        if len(output_files) == 4 and all(
            path_value.is_file() and not path_value.is_symlink()
            for path_value in output_files
        ):
            pass
        else:
            raise ValueError("Libcosim emitted an unexpected output set")
        plant_csv_candidates: list[Path] = list()
        controller_csv_candidates: list[Path] = list()
        output_path: Path
        for output_path in output_files:
            if re.fullmatch(
                r"plant_[0-9]{8}_[0-9]{6}_[0-9]{6}\.csv", output_path.name
            ) is not None:
                plant_csv_candidates.append(output_path)
            else:
                pass
            if re.fullmatch(
                r"controller_[0-9]{8}_[0-9]{6}_[0-9]{6}\.csv",
                output_path.name,
            ) is not None:
                controller_csv_candidates.append(output_path)
            else:
                pass
        if len(plant_csv_candidates) == 1 and len(controller_csv_candidates) == 1:
            plant_csv_path: Path = plant_csv_candidates[0]
            controller_csv_path: Path = controller_csv_candidates[0]
        else:
            raise ValueError("Libcosim timestamped CSV association is ambiguous")
        plant_metadata_path: Path = plant_csv_path.with_name(
            plant_csv_path.stem + "_metadata.yaml"
        )
        controller_metadata_path: Path = controller_csv_path.with_name(
            controller_csv_path.stem + "_metadata.yaml"
        )
        if plant_metadata_path in output_files and controller_metadata_path in output_files:
            pass
        else:
            raise ValueError("Libcosim metadata does not share the CSV stems")
        metadata_pairs: tuple[tuple[Path, str], ...] = (
            (plant_metadata_path, "VeraGridOpenIPSLBenchmarks.SMIBNetworkPlant"),
            (controller_metadata_path, "VeraGridOpenIPSLBenchmarks.SMIBGovernorController"),
        )
        metadata_path: Path
        expected_model_name: str
        for metadata_path, expected_model_name in metadata_pairs:
            metadata_lines: list[str] = metadata_path.read_text(
                encoding="utf-8", errors="strict"
            ).splitlines()
            variables_indices: list[int] = list()
            name_indices: list[int] = list()
            line_index: int
            line_text: str
            for line_index, line_text in enumerate(metadata_lines):
                if line_text == "variables:":
                    variables_indices.append(line_index)
                else:
                    pass
                if line_text.startswith("name:"):
                    name_indices.append(line_index)
                else:
                    pass
            metadata_matches: bool = bool(
                len(variables_indices) == 1
                and len(name_indices) == 1
                and name_indices[0] < variables_indices[0]
                and metadata_lines[name_indices[0]].removeprefix("name:").strip()
                == expected_model_name
                and '"' not in metadata_lines[name_indices[0]]
                and "'" not in metadata_lines[name_indices[0]]
            )
            if metadata_matches:
                pass
            else:
                raise ValueError("Libcosim metadata model identity is malformed")
        shutil.copyfile(plant_csv_path, raw_directory / "libcosim-plant.csv")
        shutil.copyfile(controller_csv_path, raw_directory / "libcosim-controller.csv")
        shutil.copyfile(
            plant_metadata_path, raw_directory / "libcosim-plant-metadata.yaml"
        )
        shutil.copyfile(
            controller_metadata_path,
            raw_directory / "libcosim-controller-metadata.yaml",
        )
        reference_trace_path: Path = (
            config.reference_manifest_path.parent
            / "raw" / "veragrid-closed-outputs.csv"
        )
        verify_regular_file_identity(
            reference_trace_path, 279_085,
            "5dd944e79ca8646f377d31bd63e6f8c41069ee69c349063be082ee904e04ec45",
        )
        shutil.copyfile(reference_trace_path, raw_directory / "veragrid-reference.csv")
        (raw_directory / "libcosim-version-stdout.log").write_text(
            version_result.stdout_text, encoding="utf-8", newline="\n"
        )
        (raw_directory / "libcosim-version-stderr.log").write_text(
            version_result.stderr_text, encoding="utf-8", newline="\n"
        )
        (raw_directory / "libcosim-run-stdout.log").write_text(
            run_result.stdout_text, encoding="utf-8", newline="\n"
        )
        (raw_directory / "libcosim-run-stderr.log").write_text(
            run_result.stderr_text, encoding="utf-8", newline="\n"
        )
        libcosim_trace: LibcosimTrace = _parse_libcosim_trace(
            plant_csv_path, controller_csv_path
        )
        veragrid_trace: LibcosimTrace = _parse_veragrid_reference_trace(reference_trace_path)
        metrics: LibcosimComparisonMetrics = _evaluate_libcosim_comparison(
            libcosim_trace, veragrid_trace
        )
        _render_libcosim_figures(libcosim_trace, veragrid_trace, figure_directory)
        _validate_libcosim_platform(config)
        _validate_libcosim_config(config)
        if read_regular_tree_identity(runtime_root) == (
            22, 18_086_364,
            "363bbda9f3e72c65a86bdb443c7d914f6275dddfb83df250819aebe5d689a1d4",
        ):
            pass
        else:
            raise ValueError("Libcosim runtime changed during execution")
        _write_libcosim_manifest(
            package_directory, config, version_result, run_result,
            plant_csv_path.name, plant_metadata_path.name,
            controller_csv_path.name, controller_metadata_path.name, metrics,
        )
        _verify_libcosim_package(package_directory, config)
        package_directory.replace(config.output_directory)
        published = True
    finally:
        if work_root.exists():
            shutil.rmtree(work_root)
        else:
            pass
    if published:
        return config.output_directory / "manifest.json"
    else:
        raise ValueError("Libcosim comparison did not publish")
