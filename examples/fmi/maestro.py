# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Compare a delayed two-FMU composition under Maestro and VeraGrid."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import BinaryIO, TextIO, cast

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
import numpy as np

from VeraGridEngine.IO.fmu.Elements.bindings import FmuImportConfig
from VeraGridEngine.IO.fmu.model_description import FmuInterfaceMode
from VeraGridEngine.IO.fmu.host import (
    FmuRuntimeHost,
    open_fmu_runtime_host,
)
from examples.fmi.evidence_identity import (
    read_regular_tree_identity,
    verify_regular_file_identity,
)


class MaestroComparisonConfig:
    """Own every explicit tool, FMU, source and process identity."""

    __slots__ = (
        "output_directory",
        "source_branch",
        "source_revision",
        "source_tree_sha256",
        "java_runtime_root",
        "java_runtime_expected_file_count",
        "java_runtime_expected_total_size_bytes",
        "java_runtime_expected_tree_sha256",
        "java_expected_version",
        "maestro_jar_path",
        "maestro_jar_expected_size_bytes",
        "maestro_jar_expected_sha256",
        "maestro_expected_version",
        "plant_fmu_path",
        "plant_fmu_expected_size_bytes",
        "plant_fmu_expected_sha256",
        "governor_fmu_path",
        "governor_fmu_expected_size_bytes",
        "governor_fmu_expected_sha256",
        "process_timeout_seconds",
        "stream_limit_bytes",
    )

    def __init__(
        self,
        output_directory: Path,
        source_branch: str,
        source_revision: str,
        source_tree_sha256: str,
        java_runtime_root: Path,
        java_runtime_expected_file_count: int,
        java_runtime_expected_total_size_bytes: int,
        java_runtime_expected_tree_sha256: str,
        java_expected_version: str,
        maestro_jar_path: Path,
        maestro_jar_expected_size_bytes: int,
        maestro_jar_expected_sha256: str,
        maestro_expected_version: str,
        plant_fmu_path: Path,
        plant_fmu_expected_size_bytes: int,
        plant_fmu_expected_sha256: str,
        governor_fmu_path: Path,
        governor_fmu_expected_size_bytes: int,
        governor_fmu_expected_sha256: str,
        process_timeout_seconds: float,
        stream_limit_bytes: int,
    ) -> None:
        """Validate and retain the sealed benchmark configuration.

        :param output_directory: New package destination.
        :param source_branch: Source branch represented by the evidence.
        :param source_revision: Exact forty-character Git revision.
        :param source_tree_sha256: Exact source-tree evidence digest.
        :param java_runtime_root: Complete caller-owned JRE tree.
        :param java_runtime_expected_file_count: Exact JRE file count.
        :param java_runtime_expected_total_size_bytes: Exact JRE aggregate bytes.
        :param java_runtime_expected_tree_sha256: Exact JRE tree digest.
        :param java_expected_version: Version declared by the authenticated JRE.
        :param maestro_jar_path: Explicit Maestro fat JAR.
        :param maestro_jar_expected_size_bytes: Exact Maestro JAR bytes.
        :param maestro_jar_expected_sha256: Exact Maestro JAR digest.
        :param maestro_expected_version: Maestro implementation version.
        :param plant_fmu_path: Explicit SMIB plant FMU.
        :param plant_fmu_expected_size_bytes: Exact plant FMU bytes.
        :param plant_fmu_expected_sha256: Exact plant FMU digest.
        :param governor_fmu_path: Explicit governor FMU.
        :param governor_fmu_expected_size_bytes: Exact governor FMU bytes.
        :param governor_fmu_expected_sha256: Exact governor FMU digest.
        :param process_timeout_seconds: Fixed process deadline.
        :param stream_limit_bytes: Fixed independent stream limit.
        :return: None.
        """

        scalar_values_are_exact: bool = bool(
            isinstance(output_directory, Path)
            and output_directory.is_absolute()
            and not output_directory.exists()
            and output_directory.parent.is_dir()
            and not output_directory.parent.is_symlink()
            and isinstance(source_branch, str)
            and len(source_branch) > 0
            and isinstance(source_revision, str)
            and len(source_revision) == 40
            and re.fullmatch(r"[0-9a-f]{40}", source_revision) is not None
            and isinstance(source_tree_sha256, str)
            and len(source_tree_sha256) == 64
            and re.fullmatch(r"[0-9a-f]{64}", source_tree_sha256) is not None
            and java_runtime_expected_file_count == 315
            and java_runtime_expected_total_size_bytes == 151_523_285
            and java_runtime_expected_tree_sha256
            == "98792300be37d6f994a12fd96459604c94e8c6c3f443c002e1df8a35a16b9408"
            and java_expected_version == "21.0.12"
            and maestro_jar_expected_size_bytes == 63_640_302
            and maestro_jar_expected_sha256
            == "cddc8cf30bd787f68ce04327e550ff2af3d4472725cb53637b3c4e55cf9c9c7d"
            and maestro_expected_version == "4.1.0"
            and plant_fmu_expected_size_bytes == 1_383_924
            and plant_fmu_expected_sha256
            == "76d1b0588be8865c12581977b01c5f1946e2ac94dd00f3679409e893fb87ad6a"
            and governor_fmu_expected_size_bytes == 1_368_403
            and governor_fmu_expected_sha256
            == "270eecec1f1f46e0e54d1559dc56677abcac3b88b8a4a081af257194f881130b"
            and isinstance(process_timeout_seconds, (int, float))
            and not isinstance(process_timeout_seconds, bool)
            and float(process_timeout_seconds) == 120.0
            and isinstance(stream_limit_bytes, int)
            and not isinstance(stream_limit_bytes, bool)
            and stream_limit_bytes == 1_048_576
        )
        path_values_are_explicit: bool = bool(
            isinstance(java_runtime_root, Path)
            and java_runtime_root.is_absolute()
            and isinstance(maestro_jar_path, Path)
            and maestro_jar_path.is_absolute()
            and isinstance(plant_fmu_path, Path)
            and plant_fmu_path.is_absolute()
            and isinstance(governor_fmu_path, Path)
            and governor_fmu_path.is_absolute()
        )
        if scalar_values_are_exact and path_values_are_explicit:
            pass
        else:
            raise ValueError("Maestro comparison configuration differs from rev27")
        self.output_directory: Path = output_directory
        self.source_branch: str = source_branch
        self.source_revision: str = source_revision
        self.source_tree_sha256: str = source_tree_sha256
        self.java_runtime_root: Path = java_runtime_root
        self.java_runtime_expected_file_count: int = java_runtime_expected_file_count
        self.java_runtime_expected_total_size_bytes: int = java_runtime_expected_total_size_bytes
        self.java_runtime_expected_tree_sha256: str = java_runtime_expected_tree_sha256
        self.java_expected_version: str = java_expected_version
        self.maestro_jar_path: Path = maestro_jar_path
        self.maestro_jar_expected_size_bytes: int = maestro_jar_expected_size_bytes
        self.maestro_jar_expected_sha256: str = maestro_jar_expected_sha256
        self.maestro_expected_version: str = maestro_expected_version
        self.plant_fmu_path: Path = plant_fmu_path
        self.plant_fmu_expected_size_bytes: int = plant_fmu_expected_size_bytes
        self.plant_fmu_expected_sha256: str = plant_fmu_expected_sha256
        self.governor_fmu_path: Path = governor_fmu_path
        self.governor_fmu_expected_size_bytes: int = governor_fmu_expected_size_bytes
        self.governor_fmu_expected_sha256: str = governor_fmu_expected_sha256
        self.process_timeout_seconds: float = float(process_timeout_seconds)
        self.stream_limit_bytes: int = stream_limit_bytes


class MaestroProcessResult:
    """Retain one bounded Maestro process result."""

    __slots__ = ("exit_code", "stdout_text", "stderr_text")

    def __init__(self, exit_code: int, stdout_text: str, stderr_text: str) -> None:
        """Store the exact decoded process streams.

        :param exit_code: Native process exit code.
        :param stdout_text: Strict UTF-8 standard output.
        :param stderr_text: Strict UTF-8 standard error.
        :return: None.
        """

        if isinstance(exit_code, int) and isinstance(stdout_text, str) and isinstance(stderr_text, str):
            self.exit_code: int = exit_code
            self.stdout_text: str = stdout_text
            self.stderr_text: str = stderr_text
        else:
            raise ValueError("Maestro process result is invalid")


class MaestroTrace:
    """Own the eight fixed arrays retained from one composition execution."""

    __slots__ = (
        "time_values",
        "plant_angle_rad",
        "plant_speed_pu",
        "plant_electrical_power_pu",
        "plant_effective_reactance_pu",
        "plant_mechanical_control_input_pu",
        "controller_speed_input_pu",
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
        """Validate and retain one immutable-shape numerical trace.

        :param time_values: Retained communication times.
        :param plant_angle_rad: Plant rotor-angle values in radians.
        :param plant_speed_pu: Plant speed deviation in p.u.
        :param plant_electrical_power_pu: Plant electrical power in p.u.
        :param plant_effective_reactance_pu: Applied network reactance in p.u.
        :param plant_mechanical_control_input_pu: Control input seen by the plant.
        :param controller_speed_input_pu: Speed input seen by the governor.
        :param controller_mechanical_control_output_pu: Governor output in p.u.
        :return: None.
        """

        arrays: tuple[np.ndarray, ...] = (
            time_values,
            plant_angle_rad,
            plant_speed_pu,
            plant_electrical_power_pu,
            plant_effective_reactance_pu,
            plant_mechanical_control_input_pu,
            controller_speed_input_pu,
            controller_mechanical_control_output_pu,
        )
        arrays_are_valid: bool = True
        array_value: np.ndarray
        for array_value in arrays:
            arrays_are_valid = bool(
                arrays_are_valid
                and isinstance(array_value, np.ndarray)
                and array_value.shape == (2001,)
                and np.issubdtype(array_value.dtype, np.floating)
                and np.isfinite(array_value).all()
            )
        expected_time: np.ndarray = np.linspace(0.0, 4.0, 2001, dtype=float)
        if arrays_are_valid and np.allclose(time_values, expected_time, rtol=0.0, atol=1e-12):
            pass
        else:
            raise ValueError("Maestro trace does not match the sealed lattice")
        self.time_values: np.ndarray = time_values
        self.plant_angle_rad: np.ndarray = plant_angle_rad
        self.plant_speed_pu: np.ndarray = plant_speed_pu
        self.plant_electrical_power_pu: np.ndarray = plant_electrical_power_pu
        self.plant_effective_reactance_pu: np.ndarray = plant_effective_reactance_pu
        self.plant_mechanical_control_input_pu: np.ndarray = plant_mechanical_control_input_pu
        self.controller_speed_input_pu: np.ndarray = controller_speed_input_pu
        self.controller_mechanical_control_output_pu: np.ndarray = controller_mechanical_control_output_pu


class MaestroComparisonMetrics:
    """Retain the five numerical decisions of the two-FMU benchmark."""

    __slots__ = (
        "closed_open_max_angle_difference_rad",
        "closed_open_max_speed_difference_pu",
        "closed_open_max_control_difference_pu",
        "maestro_veragrid_delayed_speed_max_error_pu",
        "maestro_veragrid_delayed_control_max_error_pu",
    )

    def __init__(
        self,
        closed_open_max_angle_difference_rad: float,
        closed_open_max_speed_difference_pu: float,
        closed_open_max_control_difference_pu: float,
        maestro_veragrid_delayed_speed_max_error_pu: float,
        maestro_veragrid_delayed_control_max_error_pu: float,
    ) -> None:
        """Store finite metrics after the acceptance oracle passes.

        :param closed_open_max_angle_difference_rad: Maximum controller effect on angle.
        :param closed_open_max_speed_difference_pu: Maximum controller effect on speed.
        :param closed_open_max_control_difference_pu: Maximum controller output difference.
        :param maestro_veragrid_delayed_speed_max_error_pu: Delayed SPEED exchange error.
        :param maestro_veragrid_delayed_control_max_error_pu: Delayed control exchange error.
        :return: None.
        """

        values: tuple[float, ...] = (
            closed_open_max_angle_difference_rad,
            closed_open_max_speed_difference_pu,
            closed_open_max_control_difference_pu,
            maestro_veragrid_delayed_speed_max_error_pu,
            maestro_veragrid_delayed_control_max_error_pu,
        )
        if all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in values):
            pass
        else:
            raise ValueError("Maestro comparison metrics must be finite")
        self.closed_open_max_angle_difference_rad: float = float(closed_open_max_angle_difference_rad)
        self.closed_open_max_speed_difference_pu: float = float(closed_open_max_speed_difference_pu)
        self.closed_open_max_control_difference_pu: float = float(closed_open_max_control_difference_pu)
        self.maestro_veragrid_delayed_speed_max_error_pu: float = float(maestro_veragrid_delayed_speed_max_error_pu)
        self.maestro_veragrid_delayed_control_max_error_pu: float = float(maestro_veragrid_delayed_control_max_error_pu)


def _validate_maestro_config(config: MaestroComparisonConfig) -> None:
    """Authenticate every external input before execution.

    :param config: Sealed Maestro comparison configuration.
    :return: None after all complete identities and versions match.
    """

    runtime_identity: tuple[int, int, str] = read_regular_tree_identity(config.java_runtime_root)
    expected_runtime_identity: tuple[int, int, str] = (
        config.java_runtime_expected_file_count,
        config.java_runtime_expected_total_size_bytes,
        config.java_runtime_expected_tree_sha256,
    )
    if runtime_identity == expected_runtime_identity:
        pass
    else:
        raise ValueError("Maestro JRE tree identity differs from configuration")
    java_path: Path = config.java_runtime_root.resolve(strict=True) / "bin" / "java.exe"
    release_path: Path = config.java_runtime_root.resolve(strict=True) / "release"
    java_paths_are_valid: bool = bool(
        java_path.is_file()
        and not java_path.is_symlink()
        and release_path.is_file()
        and not release_path.is_symlink()
    )
    if java_paths_are_valid:
        release_text: str = release_path.read_text(encoding="utf-8", errors="strict")
    else:
        raise ValueError("Authenticated JRE lacks its canonical launcher or release file")
    if f'JAVA_VERSION="{config.java_expected_version}"' in release_text:
        pass
    else:
        raise ValueError("Authenticated JRE version differs from configuration")
    verify_regular_file_identity(config.maestro_jar_path, config.maestro_jar_expected_size_bytes, config.maestro_jar_expected_sha256)
    verify_regular_file_identity(config.plant_fmu_path, config.plant_fmu_expected_size_bytes, config.plant_fmu_expected_sha256)
    verify_regular_file_identity(config.governor_fmu_path, config.governor_fmu_expected_size_bytes, config.governor_fmu_expected_sha256)


def _write_maestro_inputs(
    staging_directory: Path,
    plant_fmu_path: Path,
    governor_fmu_path: Path,
) -> tuple[Path, Path, Path]:
    """Write the two initialization documents and one execution document.

    :param staging_directory: Existing unpublished inputs directory.
    :param plant_fmu_path: Authenticated plant FMU.
    :param governor_fmu_path: Authenticated governor FMU.
    :return: Closed-loop, open-loop and execution-parameter paths.
    """

    if staging_directory.is_dir() and not staging_directory.is_symlink():
        pass
    else:
        raise ValueError("Maestro input staging directory is invalid")
    plant_uri: str = plant_fmu_path.resolve(strict=True).as_uri()
    governor_uri: str = governor_fmu_path.resolve(strict=True).as_uri()
    closed_payload: dict[str, object] = dict(
        fmus={"{plant}": plant_uri, "{controller}": governor_uri},
        connections={
            "{plant}.plant.SPEED": ["{controller}.controller.SPEED"],
            "{controller}.controller.MECH_CONTROL": ["{plant}.plant.MECH_CONTROL"],
        },
        parameters={"{controller}.controller.K": 4.0},
        sigver={"reactivity": {"{plant}.plant.MECH_CONTROL": "Delayed"}, "verification": False},
        logVariables={
            "{plant}.plant": ["ANGLE", "MECH_CONTROL", "PELEC", "SPEED", "X_EFFECTIVE"],
            "{controller}.controller": ["MECH_CONTROL", "SPEED"],
        },
    )
    open_payload: dict[str, object] = json.loads(json.dumps(closed_payload))
    open_payload["parameters"] = {"{controller}.controller.K": 0.0}
    execution_payload: dict[str, object] = dict(
        algorithm=dict(
            size=0.002,
            type="fixed-step",
        ),
        endTime=4.0,
        startTime=0.0,
    )
    closed_path: Path = staging_directory / "closed-loop.json"
    open_path: Path = staging_directory / "open-loop.json"
    execution_path: Path = staging_directory / "execution-parameters.json"
    document_paths: tuple[Path, ...] = (closed_path, open_path, execution_path)
    document_payloads: tuple[dict[str, object], ...] = (closed_payload, open_payload, execution_payload)
    for document_index in range(3):
        document_paths[document_index].write_text(
            json.dumps(document_payloads[document_index], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return closed_path, open_path, execution_path


def _run_maestro_process(
    java_path: Path,
    maestro_jar_path: Path,
    initialization_path: Path,
    execution_parameters_path: Path,
    process_output_directory: Path,
    timeout_seconds: float,
    stream_limit_bytes: int,
) -> MaestroProcessResult:
    """Execute one Maestro SG1 import with bounded raw streams.

    :param java_path: Canonical launcher inside the authenticated JRE.
    :param maestro_jar_path: Authenticated Maestro fat JAR.
    :param initialization_path: Canonical composition JSON.
    :param execution_parameters_path: Canonical execution JSON.
    :param process_output_directory: Isolated disposable Maestro output directory.
    :param timeout_seconds: Exact process deadline.
    :param stream_limit_bytes: Exact per-stream byte ceiling.
    :return: Exit code and strict UTF-8 process streams.
    """

    inputs_are_valid: bool = bool(
        java_path.is_file()
        and maestro_jar_path.is_file()
        and initialization_path.is_file()
        and execution_parameters_path.is_file()
        and process_output_directory.is_dir()
        and timeout_seconds == 120.0
        and stream_limit_bytes == 1_048_576
    )
    if inputs_are_valid:
        pass
    else:
        raise ValueError("Maestro process inputs differ from rev23")
    stdout_path: Path = process_output_directory / "maestro-stdout.capture"
    stderr_path: Path = process_output_directory / "maestro-stderr.capture"
    arguments: list[str] = [
        str(java_path), "-jar", str(maestro_jar_path), "import", "-output",
        str(process_output_directory), "--dump-intermediate", "-i", "-vi", "FMI2",
        "sg1", str(initialization_path), str(execution_parameters_path),
    ]
    stdout_file: BinaryIO = stdout_path.open("xb")
    stderr_file: BinaryIO = stderr_path.open("xb")
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            arguments,
            cwd=str(process_output_directory.parent),
            stdout=stdout_file,
            stderr=stderr_file,
            shell=False,
        )
        started_at: float = time.monotonic()
        process_finished: bool = False
        while not process_finished:
            exit_code_value: int | None = process.poll()
            stdout_file.flush()
            stderr_file.flush()
            streams_within_limit: bool = bool(
                stdout_path.stat().st_size <= stream_limit_bytes
                and stderr_path.stat().st_size <= stream_limit_bytes
            )
            deadline_is_valid: bool = bool(time.monotonic() - started_at <= timeout_seconds)
            if streams_within_limit and deadline_is_valid:
                if exit_code_value is None:
                    time.sleep(0.02)
                else:
                    process_finished = True
            else:
                process.kill()
                process.wait(timeout=2.0)
                raise ValueError("Maestro process exceeded its time or stream bound")
    finally:
        stdout_file.close()
        stderr_file.close()
    stdout_content: bytes = stdout_path.read_bytes()
    stderr_content: bytes = stderr_path.read_bytes()
    stdout_path.unlink()
    stderr_path.unlink()
    if process is not None and process.returncode is not None:
        exit_code: int = process.returncode
    else:
        raise ValueError("Maestro process did not return an exit code")
    if len(stdout_content) <= stream_limit_bytes and len(stderr_content) <= stream_limit_bytes:
        stdout_text: str = stdout_content.decode("utf-8", errors="strict")
        stderr_text: str = stderr_content.decode("utf-8", errors="strict")
    else:
        raise ValueError("Maestro process stream changed after completion")
    return MaestroProcessResult(exit_code, stdout_text, stderr_text)


def _parse_maestro_trace(csv_path: Path) -> MaestroTrace:
    """Parse one exact Maestro-compatible eight-column CSV trace.

    :param csv_path: Authenticated raw trace path.
    :return: Fixed-shape numerical trace.
    """

    expected_header: tuple[str, ...] = (
        "time",
        "{controller}.controller.MECH_CONTROL",
        "{controller}.controller.SPEED",
        "{plant}.plant.ANGLE",
        "{plant}.plant.MECH_CONTROL",
        "{plant}.plant.PELEC",
        "{plant}.plant.SPEED",
        "{plant}.plant.X_EFFECTIVE",
    )
    arrays: list[np.ndarray] = [
        np.zeros(2001, dtype=float),
        np.zeros(2001, dtype=float),
        np.zeros(2001, dtype=float),
        np.zeros(2001, dtype=float),
        np.zeros(2001, dtype=float),
        np.zeros(2001, dtype=float),
        np.zeros(2001, dtype=float),
        np.zeros(2001, dtype=float),
    ]
    csv_file: TextIO = csv_path.open("r", encoding="utf-8", errors="strict", newline="")
    try:
        reader: csv.reader = csv.reader(csv_file)
        header_values: list[str] = next(reader)
        if tuple(header_values) == expected_header:
            pass
        else:
            raise ValueError("Maestro CSV header differs from the sealed schema")
        row_count: int = 0
        row_values: list[str]
        for row_values in reader:
            if row_count < 2001 and len(row_values) == 8:
                column_index: int
                for column_index in range(8):
                    arrays[column_index][row_count] = float(row_values[column_index])
                row_count += 1
            else:
                raise ValueError("Maestro CSV row cardinality differs from rev23")
    finally:
        csv_file.close()
    if row_count == 2001:
        pass
    else:
        raise ValueError("Maestro CSV must contain exactly 2001 rows")
    return MaestroTrace(
        time_values=arrays[0],
        plant_angle_rad=arrays[3],
        plant_speed_pu=arrays[6],
        plant_electrical_power_pu=arrays[5],
        plant_effective_reactance_pu=arrays[7],
        plant_mechanical_control_input_pu=arrays[4],
        controller_speed_input_pu=arrays[2],
        controller_mechanical_control_output_pu=arrays[1],
    )


def _execute_veragrid_composition(
    config: MaestroComparisonConfig,
    output_csv_path: Path,
) -> MaestroTrace:
    """Execute the same delayed closed loop through two public runtime hosts.

    :param config: Authenticated FMU configuration.
    :param output_csv_path: New raw CSV retained in the candidate package.
    :return: Parsed VeraGrid composition trace.
    """

    plant_config: FmuImportConfig = FmuImportConfig(
        fmu_path=config.plant_fmu_path,
        preferred_mode=FmuInterfaceMode.CO_SIMULATION,
        communication_step=0.002,
        relative_tolerance=1e-6,
    )
    controller_config: FmuImportConfig = FmuImportConfig(
        fmu_path=config.governor_fmu_path,
        preferred_mode=FmuInterfaceMode.CO_SIMULATION,
        communication_step=0.002,
        relative_tolerance=1e-6,
    )
    plant_host: FmuRuntimeHost | None = None
    controller_host: FmuRuntimeHost | None = None
    output_file: TextIO = output_csv_path.open("x", encoding="utf-8", newline="")
    try:
        writer: csv.writer = csv.writer(output_file, lineterminator="\n")
        writer.writerow((
            "time", "{controller}.controller.MECH_CONTROL", "{controller}.controller.SPEED",
            "{plant}.plant.ANGLE", "{plant}.plant.MECH_CONTROL", "{plant}.plant.PELEC",
            "{plant}.plant.SPEED", "{plant}.plant.X_EFFECTIVE",
        ))
        plant_host = open_fmu_runtime_host(plant_config)
        controller_host = open_fmu_runtime_host(controller_config)
        plant_host.initialize(start_time=0.0, stop_time=4.0)
        controller_host.initialize(start_time=0.0, stop_time=4.0, start_values={"K": 4.0})
        initial_plant: dict[str, float] = plant_host.get_real(["ANGLE", "MECH_CONTROL", "PELEC", "SPEED", "X_EFFECTIVE"])
        initial_controller: dict[str, float] = controller_host.get_real(["MECH_CONTROL", "SPEED"])
        writer.writerow((
            0.0, initial_controller["MECH_CONTROL"], initial_controller["SPEED"],
            initial_plant["ANGLE"], initial_plant["MECH_CONTROL"], initial_plant["PELEC"],
            initial_plant["SPEED"], initial_plant["X_EFFECTIVE"],
        ))
        for step_index in range(2000):
            current_time: float = float(step_index) * 0.002
            plant_speed: float = plant_host.get_real(["SPEED"])["SPEED"]
            controller_control: float = controller_host.get_real(["MECH_CONTROL"])["MECH_CONTROL"]
            controller_host.set_real({"SPEED": plant_speed})
            plant_host.set_real({"MECH_CONTROL": controller_control})
            controller_host.do_step(current_time=current_time, step_size=0.002)
            plant_host.do_step(current_time=current_time, step_size=0.002)
            plant_values: dict[str, float] = plant_host.get_real(["ANGLE", "PELEC", "SPEED", "X_EFFECTIVE"])
            controller_values: dict[str, float] = controller_host.get_real(["MECH_CONTROL"])
            writer.writerow((
                current_time + 0.002,
                controller_values["MECH_CONTROL"],
                plant_speed,
                plant_values["ANGLE"],
                controller_control,
                plant_values["PELEC"],
                plant_values["SPEED"],
                plant_values["X_EFFECTIVE"],
            ))
    finally:
        output_file.close()
        if controller_host is not None:
            controller_host.close()
        else:
            pass
        if plant_host is not None:
            plant_host.close()
        else:
            pass
    return _parse_maestro_trace(output_csv_path)


def _evaluate_maestro_comparison(
    maestro_closed: MaestroTrace,
    maestro_open: MaestroTrace,
    veragrid_closed: MaestroTrace,
) -> MaestroComparisonMetrics:
    """Apply event, material-response and delayed-exchange acceptance oracles.

    :param maestro_closed: Current Maestro closed-loop trace.
    :param maestro_open: Current Maestro open-loop trace.
    :param veragrid_closed: Fresh public-host VeraGrid trace.
    :return: Five accepted comparison metrics.
    """

    traces: tuple[MaestroTrace, ...] = (maestro_closed, maestro_open, veragrid_closed)
    trace: MaestroTrace
    for trace in traces:
        event_rows_are_exact: bool = bool(
            abs(trace.plant_effective_reactance_pu[500] - 0.6) <= 1e-12
            and abs(trace.plant_effective_reactance_pu[501] - 1.2) <= 1e-12
            and abs(trace.plant_effective_reactance_pu[575] - 1.2) <= 1e-12
            and abs(trace.plant_effective_reactance_pu[576] - 0.6) <= 1e-12
        )
        if event_rows_are_exact:
            pass
        else:
            raise ValueError("SMIB network event rows differ from rev23")
    angle_difference: float = float(np.max(np.abs(maestro_closed.plant_angle_rad - maestro_open.plant_angle_rad)))
    speed_difference: float = float(np.max(np.abs(maestro_closed.plant_speed_pu - maestro_open.plant_speed_pu)))
    control_difference: float = float(np.max(np.abs(
        maestro_closed.controller_mechanical_control_output_pu
        - maestro_open.controller_mechanical_control_output_pu
    )))
    delayed_speed_error: float = float(np.max(np.abs(
        maestro_closed.controller_speed_input_pu
        - veragrid_closed.controller_speed_input_pu
    )))
    delayed_control_error: float = float(np.max(np.abs(
        maestro_closed.plant_mechanical_control_input_pu
        - veragrid_closed.plant_mechanical_control_input_pu
    )))
    metrics_are_accepted: bool = bool(
        angle_difference > 0.05
        and speed_difference > 0.001
        and control_difference > 0.01
        and delayed_speed_error <= 1e-12
        and delayed_control_error <= 1e-12
    )
    if metrics_are_accepted:
        return MaestroComparisonMetrics(
            angle_difference,
            speed_difference,
            control_difference,
            delayed_speed_error,
            delayed_control_error,
        )
    else:
        raise ValueError("Maestro two-FMU acceptance oracle failed")


def _render_maestro_figures(
    staging_directory: Path,
    maestro_closed: MaestroTrace,
    maestro_open: MaestroTrace,
    veragrid_closed: MaestroTrace,
) -> tuple[Path, Path, Path]:
    """Render the sealed four-panel scientific comparison.

    :param staging_directory: Unpublished package root.
    :param maestro_closed: Maestro closed-loop trace.
    :param maestro_open: Maestro open-loop trace.
    :param veragrid_closed: VeraGrid closed-loop trace.
    :return: PNG, SVG and PDF paths in that order.
    """

    figure_directory: Path = staging_directory / "figures"
    if figure_directory.is_dir() and not figure_directory.is_symlink():
        pass
    else:
        raise ValueError("Maestro figure directory is invalid")
    png_path: Path = figure_directory / "maestro-smib-composition.png"
    svg_path: Path = figure_directory / "maestro-smib-composition.svg"
    pdf_path: Path = figure_directory / "maestro-smib-composition.pdf"
    style_values: dict[str, object] = {
        "font.family": "DejaVu Sans",
        "font.size": 8.0,
        "axes.labelsize": 8.0,
        "axes.titlesize": 9.0,
        "legend.fontsize": 7.2,
        "xtick.labelsize": 7.2,
        "ytick.labelsize": 7.2,
        "axes.linewidth": 0.8,
        "lines.linewidth": 1.15,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "xtick.top": True,
        "ytick.right": True,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    }
    with mpl.rc_context(style_values):
        figure: Figure = plt.figure(figsize=(7.2, 7.0), constrained_layout=True)
        axes_array: np.ndarray = cast(np.ndarray, figure.subplots(4, 1, sharex=True))
        angle_axis: Axes = cast(Axes, axes_array[0])
        speed_axis: Axes = cast(Axes, axes_array[1])
        control_axis: Axes = cast(Axes, axes_array[2])
        exchange_axis: Axes = cast(Axes, axes_array[3])
        closed_color: str = "#1f4e79"
        open_color: str = "#a23b3b"
        veragrid_color: str = "#2f6f4e"

        # Closed/open trajectories demonstrate that the controller materially acts.
        angle_axis.plot(
            maestro_closed.time_values,
            maestro_closed.plant_angle_rad,
            color=closed_color,
            linestyle="-",
            label="Maestro closed loop",
        )
        angle_axis.plot(
            maestro_open.time_values,
            maestro_open.plant_angle_rad,
            color=open_color,
            linestyle="--",
            label="Maestro open loop",
        )
        angle_axis.set_ylabel("Rotor angle (rad)")
        angle_axis.legend(loc="best", frameon=False, ncol=2)

        speed_axis.plot(
            maestro_closed.time_values,
            maestro_closed.plant_speed_pu,
            color=closed_color,
            linestyle="-",
            label="Maestro closed loop",
        )
        speed_axis.plot(
            maestro_open.time_values,
            maestro_open.plant_speed_pu,
            color=open_color,
            linestyle="--",
            label="Maestro open loop",
        )
        speed_axis.set_ylabel("Speed deviation (p.u.)")

        control_axis.plot(
            maestro_closed.time_values,
            maestro_closed.controller_mechanical_control_output_pu,
            color=closed_color,
            linestyle="-",
            label="Maestro controller output",
        )
        control_axis.plot(
            maestro_open.time_values,
            maestro_open.controller_mechanical_control_output_pu,
            color=open_color,
            linestyle="--",
            label="Open-loop controller output",
        )
        control_axis.set_ylabel("Mechanical control (p.u.)")

        # The lower panel exposes the specified one-step delayed coupling directly.
        exchange_axis.plot(
            maestro_closed.time_values,
            maestro_closed.controller_speed_input_pu,
            color=closed_color,
            linestyle="-",
            label="Maestro controller SPEED",
        )
        exchange_axis.plot(
            veragrid_closed.time_values,
            veragrid_closed.controller_speed_input_pu,
            color=veragrid_color,
            linestyle=":",
            label="VeraGrid applied SPEED",
        )
        exchange_axis.set_ylabel("Delayed SPEED (p.u.)")
        exchange_axis.set_xlabel("Time (s)")
        exchange_axis.legend(loc="best", frameon=False, ncol=2)

        axes: tuple[Axes, ...] = (
            angle_axis,
            speed_axis,
            control_axis,
            exchange_axis,
        )
        plot_axis: Axes
        for plot_axis in axes:
            plot_axis.axvspan(1.001, 1.151, color="#d9d9d9", alpha=0.45)
            plot_axis.axvline(1.001, color="#555555", linestyle="-.", linewidth=0.8)
            plot_axis.axvline(1.151, color="#555555", linestyle="-.", linewidth=0.8)
            plot_axis.grid(True, which="major", color="#d0d0d0", linewidth=0.45)
        figure.suptitle("FMI 2.0 CS two-FMU delayed composition: Maestro 4.1.0 and VeraGrid")
        figure.savefig(png_path, dpi=300, format="png")
        figure.savefig(svg_path, format="svg")
        figure.savefig(pdf_path, format="pdf")
        plt.close(figure)
    return png_path, svg_path, pdf_path


def _write_maestro_manifest(
    config: MaestroComparisonConfig,
    staging_directory: Path,
    closed_result: MaestroProcessResult,
    open_result: MaestroProcessResult,
    metrics: MaestroComparisonMetrics,
) -> Path:
    """Write the exact rev23 evidence manifest before final verification.

    :param config: Authenticated run configuration.
    :param staging_directory: Unpublished package root.
    :param closed_result: Closed-loop Maestro process result.
    :param open_result: Open-loop Maestro process result.
    :param metrics: Accepted numerical comparison metrics.
    :return: Newly written manifest path.
    """

    relative_paths: tuple[str, ...] = (
        "figures/maestro-smib-composition.pdf",
        "figures/maestro-smib-composition.png",
        "figures/maestro-smib-composition.svg",
        "inputs/closed-loop.json",
        "inputs/execution-parameters.json",
        "inputs/open-loop.json",
        "manifest.json",
        "raw/maestro-closed-outputs.csv",
        "raw/maestro-closed-stderr.log",
        "raw/maestro-closed-stdout.log",
        "raw/maestro-open-outputs.csv",
        "raw/maestro-open-stderr.log",
        "raw/maestro-open-stdout.log",
        "raw/veragrid-closed-outputs.csv",
    )
    file_records: dict[str, dict[str, object]] = dict()
    relative_path: str
    for relative_path in relative_paths:
        if relative_path == "manifest.json":
            pass
        else:
            retained_path: Path = staging_directory / Path(relative_path)
            retained_bytes: bytes = retained_path.read_bytes()
            file_records[relative_path] = {
                "relative_path": relative_path,
                "size_bytes": len(retained_bytes),
                "sha256": hashlib.sha256(retained_bytes).hexdigest(),
            }
    maestro_closed_trace_record: dict[str, object] = {
        "relative_path": file_records[
            "raw/maestro-closed-outputs.csv"
        ]["relative_path"],
        "size_bytes": file_records[
            "raw/maestro-closed-outputs.csv"
        ]["size_bytes"],
        "sha256": file_records[
            "raw/maestro-closed-outputs.csv"
        ]["sha256"],
        "row_count": 2001,
    }
    maestro_open_trace_record: dict[str, object] = {
        "relative_path": file_records[
            "raw/maestro-open-outputs.csv"
        ]["relative_path"],
        "size_bytes": file_records[
            "raw/maestro-open-outputs.csv"
        ]["size_bytes"],
        "sha256": file_records[
            "raw/maestro-open-outputs.csv"
        ]["sha256"],
        "row_count": 2001,
    }
    veragrid_closed_trace_record: dict[str, object] = {
        "relative_path": file_records[
            "raw/veragrid-closed-outputs.csv"
        ]["relative_path"],
        "size_bytes": file_records[
            "raw/veragrid-closed-outputs.csv"
        ]["size_bytes"],
        "sha256": file_records[
            "raw/veragrid-closed-outputs.csv"
        ]["sha256"],
        "row_count": 2001,
    }
    payload: dict[str, object] = {
        "schema": "veragrid.fmi-maestro-comparison/1",
        "status": "PASS",
        "source": {
            "branch": config.source_branch,
            "revision": config.source_revision,
            "tree_sha256": config.source_tree_sha256,
        },
        "tools": {
            "java_runtime": {
                "path": str(config.java_runtime_root),
                "file_count": config.java_runtime_expected_file_count,
                "total_size_bytes": config.java_runtime_expected_total_size_bytes,
                "tree_sha256": config.java_runtime_expected_tree_sha256,
                "version": config.java_expected_version,
            },
            "maestro": {
                "path": str(config.maestro_jar_path),
                "size_bytes": config.maestro_jar_expected_size_bytes,
                "sha256": config.maestro_jar_expected_sha256,
                "version": config.maestro_expected_version,
            },
            "plant_fmu": {
                "path": str(config.plant_fmu_path),
                "size_bytes": config.plant_fmu_expected_size_bytes,
                "sha256": config.plant_fmu_expected_sha256,
            },
            "governor_fmu": {
                "path": str(config.governor_fmu_path),
                "size_bytes": config.governor_fmu_expected_size_bytes,
                "sha256": config.governor_fmu_expected_sha256,
            },
        },
        "execution": {
            "start_time": 0.0,
            "end_time": 4.0,
            "step_size": 0.002,
            "steps": 2000,
            "closed_gain": 4.0,
            "open_gain": 0.0,
            "process_timeout_seconds": config.process_timeout_seconds,
            "stream_limit_bytes": config.stream_limit_bytes,
        },
        "topology": {
            "name": "SMIB plant-governor delayed composition",
            "connections": [
                "{plant}.plant.SPEED -> {controller}.controller.SPEED",
                "{controller}.controller.MECH_CONTROL -> {plant}.plant.MECH_CONTROL",
            ],
            "delay_steps": 1,
            "initial_speed_input_pu": 0.0,
            "initial_mechanical_control_input_pu": 0.0,
            "event_rows": [500, 501, 575, 576],
            "event_times": [1.001, 1.151],
        },
        "inputs": {
            "closed_loop": file_records["inputs/closed-loop.json"],
            "open_loop": file_records["inputs/open-loop.json"],
            "execution_parameters": file_records["inputs/execution-parameters.json"],
        },
        "processes": {
            "closed": {
                "exit_code": closed_result.exit_code,
                "stdout": file_records["raw/maestro-closed-stdout.log"],
                "stderr": file_records["raw/maestro-closed-stderr.log"],
            },
            "open": {
                "exit_code": open_result.exit_code,
                "stdout": file_records["raw/maestro-open-stdout.log"],
                "stderr": file_records["raw/maestro-open-stderr.log"],
            },
        },
        "traces": {
            "maestro_closed": maestro_closed_trace_record,
            "maestro_open": maestro_open_trace_record,
            "veragrid_closed": veragrid_closed_trace_record,
        },
        "metrics": {
            "closed_open_max_angle_difference_rad": metrics.closed_open_max_angle_difference_rad,
            "closed_open_max_speed_difference_pu": metrics.closed_open_max_speed_difference_pu,
            "closed_open_max_control_difference_pu": metrics.closed_open_max_control_difference_pu,
            "maestro_veragrid_delayed_speed_max_error_pu": metrics.maestro_veragrid_delayed_speed_max_error_pu,
            "maestro_veragrid_delayed_control_max_error_pu": metrics.maestro_veragrid_delayed_control_max_error_pu,
            "limits": {
                "minimum_angle_difference_rad": 0.05,
                "minimum_speed_difference_pu": 0.001,
                "minimum_control_difference_pu": 0.01,
                "maximum_delayed_exchange_error_pu": 1e-12,
            },
        },
        "figures": {
            "png": file_records["figures/maestro-smib-composition.png"],
            "svg": file_records["figures/maestro-smib-composition.svg"],
            "pdf": file_records["figures/maestro-smib-composition.pdf"],
        },
        "package_files": list(relative_paths),
    }
    manifest_path: Path = staging_directory / "manifest.json"
    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest_path


def _verify_maestro_package(
    config: MaestroComparisonConfig,
    package_root: Path,
) -> None:
    """Reopen and verify every retained byte and numerical claim.

    :param config: Authenticated benchmark configuration.
    :param package_root: Unpublished complete package root.
    :return: None after all rev23 invariants pass.
    """

    expected_files: tuple[str, ...] = (
        "figures/maestro-smib-composition.pdf",
        "figures/maestro-smib-composition.png",
        "figures/maestro-smib-composition.svg",
        "inputs/closed-loop.json",
        "inputs/execution-parameters.json",
        "inputs/open-loop.json",
        "manifest.json",
        "raw/maestro-closed-outputs.csv",
        "raw/maestro-closed-stderr.log",
        "raw/maestro-closed-stdout.log",
        "raw/maestro-open-outputs.csv",
        "raw/maestro-open-stderr.log",
        "raw/maestro-open-stdout.log",
        "raw/veragrid-closed-outputs.csv",
    )
    expected_directories: tuple[str, ...] = ("figures", "inputs", "raw")
    actual_files: list[str] = list()
    actual_directories: list[str] = list()
    package_entry: Path
    for package_entry in package_root.rglob("*"):
        portable_path: str = package_entry.relative_to(package_root).as_posix()
        if package_entry.is_symlink():
            raise ValueError("Maestro package contains a symbolic link")
        else:
            if package_entry.is_file():
                actual_files.append(portable_path)
            else:
                if package_entry.is_dir():
                    actual_directories.append(portable_path)
                else:
                    raise ValueError("Maestro package contains an unsupported entry")
    actual_files.sort()
    actual_directories.sort()
    if tuple(actual_files) == expected_files and tuple(actual_directories) == expected_directories:
        pass
    else:
        raise ValueError("Maestro package path closure differs from rev23")

    manifest_path: Path = package_root / "manifest.json"
    manifest_value: object = json.loads(manifest_path.read_text(encoding="utf-8", errors="strict"))
    if isinstance(manifest_value, dict):
        manifest: dict[str, object] = cast(dict[str, object], manifest_value)
    else:
        raise ValueError("Maestro manifest root must be an object")
    expected_top_keys: set[str] = {
        "schema", "status", "source", "tools", "execution", "topology", "inputs",
        "processes", "traces", "metrics", "figures", "package_files",
    }
    top_level_is_exact: bool = bool(
        set(manifest.keys()) == expected_top_keys
        and manifest["schema"] == "veragrid.fmi-maestro-comparison/1"
        and manifest["status"] == "PASS"
        and manifest["package_files"] == list(expected_files)
    )
    if top_level_is_exact:
        pass
    else:
        raise ValueError("Maestro manifest top-level contract differs from rev23")

    # Canonical input bytes are part of the evidence, not passive configuration.
    input_names: tuple[str, ...] = (
        "inputs/closed-loop.json",
        "inputs/open-loop.json",
        "inputs/execution-parameters.json",
    )
    input_documents: list[dict[str, object]] = [dict(), dict(), dict()]
    input_index: int
    for input_index in range(3):
        input_path: Path = package_root / Path(input_names[input_index])
        input_bytes: bytes = input_path.read_bytes()
        parsed_input_value: object = json.loads(input_bytes.decode("utf-8", errors="strict"))
        if isinstance(parsed_input_value, dict):
            parsed_input: dict[str, object] = cast(dict[str, object], parsed_input_value)
        else:
            raise ValueError("Maestro input document must be an object")
        canonical_input: bytes = (
            json.dumps(parsed_input, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        if input_bytes == canonical_input:
            input_documents[input_index] = parsed_input
        else:
            raise ValueError("Maestro input document is not canonical UTF-8 JSON")
    closed_document: dict[str, object] = input_documents[0]
    open_document: dict[str, object] = input_documents[1]
    execution_document: dict[str, object] = input_documents[2]
    initialization_keys: set[str] = {
        "fmus", "connections", "parameters", "sigver", "logVariables",
    }
    initialization_documents: tuple[dict[str, object], ...] = (
        closed_document,
        open_document,
    )
    initialization_document: dict[str, object]
    for initialization_document in initialization_documents:
        if set(initialization_document.keys()) == initialization_keys:
            pass
        else:
            raise ValueError("Maestro initialization key closure differs from rev23")
    expected_fmus: dict[str, str] = {
        "{plant}": config.plant_fmu_path.resolve(strict=True).as_uri(),
        "{controller}": config.governor_fmu_path.resolve(strict=True).as_uri(),
    }
    expected_connections: dict[str, list[str]] = {
        "{plant}.plant.SPEED": ["{controller}.controller.SPEED"],
        "{controller}.controller.MECH_CONTROL": ["{plant}.plant.MECH_CONTROL"],
    }
    expected_sigver: dict[str, object] = {
        "reactivity": {"{plant}.plant.MECH_CONTROL": "Delayed"},
        "verification": False,
    }
    expected_log_variables: dict[str, list[str]] = {
        "{plant}.plant": ["ANGLE", "MECH_CONTROL", "PELEC", "SPEED", "X_EFFECTIVE"],
        "{controller}.controller": ["MECH_CONTROL", "SPEED"],
    }
    initialization_semantics_are_exact: bool = bool(
        closed_document["fmus"] == expected_fmus
        and open_document["fmus"] == expected_fmus
        and closed_document["connections"] == expected_connections
        and open_document["connections"] == expected_connections
        and closed_document["parameters"] == {"{controller}.controller.K": 4.0}
        and open_document["parameters"] == {"{controller}.controller.K": 0.0}
        and closed_document["sigver"] == expected_sigver
        and open_document["sigver"] == expected_sigver
        and closed_document["logVariables"] == expected_log_variables
        and open_document["logVariables"] == expected_log_variables
    )
    expected_execution: dict[str, object] = dict(
        algorithm=dict(
            size=0.002,
            type="fixed-step",
        ),
        endTime=4.0,
        startTime=0.0,
    )
    if initialization_semantics_are_exact and execution_document == expected_execution:
        pass
    else:
        raise ValueError("Maestro input semantics differ from rev26")

    # Every referenced retained file is independently rehashed.
    manifest_sections: tuple[str, ...] = ("inputs", "processes", "traces", "figures")
    manifest_section_name: str
    for manifest_section_name in manifest_sections:
        if isinstance(manifest[manifest_section_name], dict):
            pass
        else:
            raise ValueError("Maestro manifest section must be an object")
    retained_relative_path: str
    for retained_relative_path in expected_files:
        if retained_relative_path == "manifest.json":
            pass
        else:
            retained_path: Path = package_root / Path(retained_relative_path)
            retained_content: bytes = retained_path.read_bytes()
            retained_sha256: str = hashlib.sha256(retained_content).hexdigest()
            manifest_text: str = manifest_path.read_text(encoding="utf-8", errors="strict")
            file_identity_is_bound: bool = bool(
                retained_relative_path in manifest_text
                and str(len(retained_content)) in manifest_text
                and retained_sha256 in manifest_text
            )
            if file_identity_is_bound:
                pass
            else:
                raise ValueError("Maestro retained-file identity is not manifest-bound")

    closed_trace: MaestroTrace = _parse_maestro_trace(
        package_root / "raw" / "maestro-closed-outputs.csv"
    )
    open_trace: MaestroTrace = _parse_maestro_trace(
        package_root / "raw" / "maestro-open-outputs.csv"
    )
    veragrid_trace: MaestroTrace = _parse_maestro_trace(
        package_root / "raw" / "veragrid-closed-outputs.csv"
    )
    recomputed_metrics: MaestroComparisonMetrics = _evaluate_maestro_comparison(
        closed_trace,
        open_trace,
        veragrid_trace,
    )
    metrics_value: object = manifest["metrics"]
    if isinstance(metrics_value, dict):
        manifest_metrics: dict[str, object] = cast(dict[str, object], metrics_value)
    else:
        raise ValueError("Maestro metrics must be an object")
    metrics_are_exact: bool = bool(
        manifest_metrics["closed_open_max_angle_difference_rad"]
        == recomputed_metrics.closed_open_max_angle_difference_rad
        and manifest_metrics["closed_open_max_speed_difference_pu"]
        == recomputed_metrics.closed_open_max_speed_difference_pu
        and manifest_metrics["closed_open_max_control_difference_pu"]
        == recomputed_metrics.closed_open_max_control_difference_pu
        and manifest_metrics["maestro_veragrid_delayed_speed_max_error_pu"]
        == recomputed_metrics.maestro_veragrid_delayed_speed_max_error_pu
        and manifest_metrics["maestro_veragrid_delayed_control_max_error_pu"]
        == recomputed_metrics.maestro_veragrid_delayed_control_max_error_pu
    )
    if metrics_are_exact:
        pass
    else:
        raise ValueError("Maestro metrics differ from recomputation")

    closed_stderr: bytes = (package_root / "raw" / "maestro-closed-stderr.log").read_bytes()
    open_stderr: bytes = (package_root / "raw" / "maestro-open-stderr.log").read_bytes()
    if len(closed_stderr) == 0 and len(open_stderr) == 0:
        pass
    else:
        raise ValueError("Maestro stderr must be empty")
    png_array: np.ndarray = plt.imread(
        package_root / "figures" / "maestro-smib-composition.png"
    )
    svg_text: str = (
        package_root / "figures" / "maestro-smib-composition.svg"
    ).read_text(encoding="utf-8", errors="strict")
    pdf_bytes: bytes = (
        package_root / "figures" / "maestro-smib-composition.pdf"
    ).read_bytes()
    figures_are_exact: bool = bool(
        png_array.shape[0] == 2100
        and png_array.shape[1] == 2160
        and "<text" in svg_text
        and "518.4pt" in svg_text
        and "504pt" in svg_text
        and b"/MediaBox [ 0 0 518.4 504 ]" in pdf_bytes
    )
    if figures_are_exact:
        pass
    else:
        raise ValueError("Maestro figure geometry or selectable text differs from rev23")
    _validate_maestro_config(config)


def generate_maestro_comparison(config: MaestroComparisonConfig) -> Path:
    """Execute, verify and atomically publish the Maestro comparison.

    :param config: Complete authenticated benchmark configuration.
    :return: Published manifest path.
    """

    _validate_maestro_config(config)
    work_root_text: str = tempfile.mkdtemp(
        prefix=".maestro-comparison-",
        dir=str(config.output_directory.parent),
    )
    work_root: Path = Path(work_root_text)
    package_root: Path = work_root / "package"
    process_closed_root: Path = work_root / "maestro-closed"
    process_open_root: Path = work_root / "maestro-open"
    try:
        package_root.mkdir()
        inputs_root: Path = package_root / "inputs"
        raw_root: Path = package_root / "raw"
        figures_root: Path = package_root / "figures"
        inputs_root.mkdir()
        raw_root.mkdir()
        figures_root.mkdir()
        process_closed_root.mkdir()
        process_open_root.mkdir()
        closed_input_path: Path
        open_input_path: Path
        execution_input_path: Path
        closed_input_path, open_input_path, execution_input_path = _write_maestro_inputs(
            inputs_root,
            config.plant_fmu_path,
            config.governor_fmu_path,
        )
        closed_input_bytes: bytes = closed_input_path.read_bytes()
        open_input_bytes: bytes = open_input_path.read_bytes()
        execution_input_bytes: bytes = execution_input_path.read_bytes()
        java_path: Path = config.java_runtime_root.resolve(strict=True) / "bin" / "java.exe"

        # Reauthenticate all external and declarative inputs around each process.
        _validate_maestro_config(config)
        closed_result: MaestroProcessResult = _run_maestro_process(
            java_path,
            config.maestro_jar_path,
            closed_input_path,
            execution_input_path,
            process_closed_root,
            config.process_timeout_seconds,
            config.stream_limit_bytes,
        )
        _validate_maestro_config(config)
        closed_inputs_are_stable: bool = bool(
            closed_input_path.read_bytes() == closed_input_bytes
            and open_input_path.read_bytes() == open_input_bytes
            and execution_input_path.read_bytes() == execution_input_bytes
        )
        if closed_inputs_are_stable and closed_result.exit_code == 0 and closed_result.stderr_text == "":
            pass
        else:
            raise ValueError("Closed-loop Maestro execution did not satisfy rev23")
        closed_output_source: Path = process_closed_root / "outputs.csv"
        if closed_output_source.is_file() and not closed_output_source.is_symlink():
            shutil.copyfile(
                closed_output_source,
                raw_root / "maestro-closed-outputs.csv",
            )
        else:
            raise ValueError("Closed-loop Maestro outputs.csv is unavailable")
        (raw_root / "maestro-closed-stdout.log").write_text(
            closed_result.stdout_text,
            encoding="utf-8",
            newline="\n",
        )
        (raw_root / "maestro-closed-stderr.log").write_text(
            closed_result.stderr_text,
            encoding="utf-8",
            newline="\n",
        )

        _validate_maestro_config(config)
        open_result: MaestroProcessResult = _run_maestro_process(
            java_path,
            config.maestro_jar_path,
            open_input_path,
            execution_input_path,
            process_open_root,
            config.process_timeout_seconds,
            config.stream_limit_bytes,
        )
        _validate_maestro_config(config)
        open_inputs_are_stable: bool = bool(
            closed_input_path.read_bytes() == closed_input_bytes
            and open_input_path.read_bytes() == open_input_bytes
            and execution_input_path.read_bytes() == execution_input_bytes
        )
        if open_inputs_are_stable and open_result.exit_code == 0 and open_result.stderr_text == "":
            pass
        else:
            raise ValueError("Open-loop Maestro execution did not satisfy rev23")
        open_output_source: Path = process_open_root / "outputs.csv"
        if open_output_source.is_file() and not open_output_source.is_symlink():
            shutil.copyfile(
                open_output_source,
                raw_root / "maestro-open-outputs.csv",
            )
        else:
            raise ValueError("Open-loop Maestro outputs.csv is unavailable")
        (raw_root / "maestro-open-stdout.log").write_text(
            open_result.stdout_text,
            encoding="utf-8",
            newline="\n",
        )
        (raw_root / "maestro-open-stderr.log").write_text(
            open_result.stderr_text,
            encoding="utf-8",
            newline="\n",
        )

        maestro_closed: MaestroTrace = _parse_maestro_trace(
            raw_root / "maestro-closed-outputs.csv"
        )
        maestro_open: MaestroTrace = _parse_maestro_trace(
            raw_root / "maestro-open-outputs.csv"
        )
        veragrid_closed: MaestroTrace = _execute_veragrid_composition(
            config,
            raw_root / "veragrid-closed-outputs.csv",
        )
        metrics: MaestroComparisonMetrics = _evaluate_maestro_comparison(
            maestro_closed,
            maestro_open,
            veragrid_closed,
        )
        _render_maestro_figures(
            package_root,
            maestro_closed,
            maestro_open,
            veragrid_closed,
        )
        _write_maestro_manifest(
            config,
            package_root,
            closed_result,
            open_result,
            metrics,
        )
        _verify_maestro_package(config, package_root)
        os.replace(package_root, config.output_directory)
    finally:
        if work_root.exists():
            shutil.rmtree(work_root)
        else:
            pass
    return config.output_directory / "manifest.json"
