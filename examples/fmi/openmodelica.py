# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Build the maintained SMIB source with an explicitly pinned OpenModelica."""
from __future__ import annotations

import csv
import hashlib
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import BinaryIO, TextIO

import numpy as np


class OpenModelicaBuildConfig:
    """Own the exact source, compiler identity and build boundaries."""

    __slots__ = (
        "source_path",
        "source_expected_size_bytes",
        "source_expected_sha256",
        "omc_executable",
        "omc_expected_version",
        "omc_expected_size_bytes",
        "omc_expected_sha256",
        "output_directory",
        "stop_time",
        "step_size",
        "process_timeout_seconds",
    )

    source_path: Path
    source_expected_size_bytes: int
    source_expected_sha256: str
    omc_executable: Path
    omc_expected_version: str
    omc_expected_size_bytes: int
    omc_expected_sha256: str
    output_directory: Path
    stop_time: float
    step_size: float
    process_timeout_seconds: float

    def __init__(
        self,
        source_path: Path,
        source_expected_size_bytes: int,
        source_expected_sha256: str,
        omc_executable: Path,
        omc_expected_version: str,
        omc_expected_size_bytes: int,
        omc_expected_sha256: str,
        output_directory: Path,
        stop_time: float,
        step_size: float,
        process_timeout_seconds: float,
    ) -> None:
        """Validate caller-owned identities before retaining the configuration.

        :param source_path: Maintained Modelica source selected by the caller.
        :param source_expected_size_bytes: Required source byte count.
        :param source_expected_sha256: Required source SHA-256.
        :param omc_executable: Explicit OpenModelica compiler executable.
        :param omc_expected_version: Exact text returned by ``--version``.
        :param omc_expected_size_bytes: Required compiler byte count.
        :param omc_expected_sha256: Required compiler SHA-256.
        :param output_directory: Nonexistent final build-evidence directory.
        :param stop_time: Required simulation stop time in seconds.
        :param step_size: Required output interval in seconds.
        :param process_timeout_seconds: Maximum build-process duration.
        :return: None.
        """

        paths_are_valid: bool = bool(
            isinstance(source_path, Path)
            and isinstance(omc_executable, Path)
            and isinstance(output_directory, Path)
        )
        sizes_are_valid: bool = bool(
            type(source_expected_size_bytes) is int
            and source_expected_size_bytes > 0
            and type(omc_expected_size_bytes) is int
            and omc_expected_size_bytes > 0
        )
        identities_are_valid: bool = bool(
            re.fullmatch(r"[0-9a-f]{64}", source_expected_sha256) is not None
            and re.fullmatch(r"[0-9a-f]{64}", omc_expected_sha256) is not None
            and isinstance(omc_expected_version, str)
            and bool(omc_expected_version.strip())
            and "\n" not in omc_expected_version
            and "\r" not in omc_expected_version
        )
        numerical_contract_is_valid: bool = bool(
            math.isfinite(stop_time)
            and stop_time == 4.0
            and math.isfinite(step_size)
            and step_size == 0.002
            and math.isfinite(process_timeout_seconds)
            and 1.0 <= process_timeout_seconds <= 300.0
        )
        if (
            paths_are_valid
            and sizes_are_valid
            and identities_are_valid
            and numerical_contract_is_valid
        ):
            pass
        else:
            raise ValueError("OpenModelica build configuration is invalid")

        self.source_path: Path = source_path
        self.source_expected_size_bytes: int = source_expected_size_bytes
        self.source_expected_sha256: str = source_expected_sha256
        self.omc_executable: Path = omc_executable
        self.omc_expected_version: str = omc_expected_version.strip()
        self.omc_expected_size_bytes: int = omc_expected_size_bytes
        self.omc_expected_sha256: str = omc_expected_sha256
        self.output_directory: Path = output_directory
        self.stop_time: float = stop_time
        self.step_size: float = step_size
        self.process_timeout_seconds: float = process_timeout_seconds


class OpenModelicaBuildEvidence:
    """Retain immutable identities and paths from one published SMIB build."""

    __slots__ = (
        "source_path",
        "source_size_bytes",
        "source_sha256",
        "omc_executable",
        "omc_sha256",
        "omc_version",
        "fmu_path",
        "fmu_sha256",
        "native_csv_path",
        "build_stdout_path",
        "build_stderr_path",
    )

    source_path: Path
    source_size_bytes: int
    source_sha256: str
    omc_executable: Path
    omc_sha256: str
    omc_version: str
    fmu_path: Path
    fmu_sha256: str
    native_csv_path: Path
    build_stdout_path: Path
    build_stderr_path: Path

    def __init__(
        self,
        source_path: Path,
        source_size_bytes: int,
        source_sha256: str,
        omc_executable: Path,
        omc_sha256: str,
        omc_version: str,
        fmu_path: Path,
        fmu_sha256: str,
        native_csv_path: Path,
        build_stdout_path: Path,
        build_stderr_path: Path,
    ) -> None:
        """Retain the complete published evidence boundary.

        :param source_path: Canonical maintained source path.
        :param source_size_bytes: Observed source byte count.
        :param source_sha256: Observed source SHA-256.
        :param omc_executable: Canonical compiler path.
        :param omc_sha256: Observed compiler SHA-256.
        :param omc_version: Observed compiler version text.
        :param fmu_path: Published FMI 2 Co-Simulation archive.
        :param fmu_sha256: Published FMU SHA-256.
        :param native_csv_path: Published canonical OpenModelica trace.
        :param build_stdout_path: Retained compiler standard output.
        :param build_stderr_path: Retained compiler standard error.
        :return: None.
        """

        self.source_path: Path = source_path
        self.source_size_bytes: int = source_size_bytes
        self.source_sha256: str = source_sha256
        self.omc_executable: Path = omc_executable
        self.omc_sha256: str = omc_sha256
        self.omc_version: str = omc_version
        self.fmu_path: Path = fmu_path
        self.fmu_sha256: str = fmu_sha256
        self.native_csv_path: Path = native_csv_path
        self.build_stdout_path: Path = build_stdout_path
        self.build_stderr_path: Path = build_stderr_path


def _validate_openmodelica_config(
    config: OpenModelicaBuildConfig,
) -> tuple[Path, Path, Path, str, str]:
    """Validate static identities without launching any native process.

    :param config: Explicit caller-owned build configuration.
    :return: Canonical source, compiler, parent and their two SHA-256 values.
    """

    if isinstance(config, OpenModelicaBuildConfig):
        pass
    else:
        raise TypeError("OpenModelica build requires its typed configuration")

    maintained_source: Path = Path(__file__).resolve(strict=True).with_name(
        "smib_network_plant.mo"
    )
    candidate_source: Path = config.source_path
    source_is_valid: bool = bool(
        not candidate_source.is_symlink()
        and candidate_source.is_file()
        and candidate_source.resolve(strict=True) == maintained_source
        and candidate_source.stat().st_size == config.source_expected_size_bytes
    )
    if source_is_valid:
        resolved_source: Path = candidate_source.resolve(strict=True)
    else:
        raise ValueError("Modelica source path or size differs from the sealed source")

    candidate_compiler: Path = config.omc_executable
    compiler_is_valid: bool = bool(
        candidate_compiler.is_absolute()
        and not candidate_compiler.is_symlink()
        and candidate_compiler.is_file()
        and candidate_compiler.stat().st_size == config.omc_expected_size_bytes
    )
    if compiler_is_valid:
        resolved_compiler: Path = candidate_compiler.resolve(strict=True)
    else:
        raise ValueError("OpenModelica executable path or size is invalid")

    output_parent: Path = config.output_directory.parent
    output_is_valid: bool = bool(
        not config.output_directory.exists()
        and not output_parent.is_symlink()
        and output_parent.is_dir()
    )
    if output_is_valid:
        resolved_parent: Path = output_parent.resolve(strict=True)
    else:
        raise ValueError("OpenModelica output directory must be new under a regular parent")

    with resolved_source.open("rb") as source_file:
        source_handle: BinaryIO = source_file
        source_sha256: str = hashlib.file_digest(source_handle, "sha256").hexdigest()
    with resolved_compiler.open("rb") as compiler_file:
        compiler_handle: BinaryIO = compiler_file
        compiler_sha256: str = hashlib.file_digest(compiler_handle, "sha256").hexdigest()
    identities_match: bool = bool(
        source_sha256 == config.source_expected_sha256
        and compiler_sha256 == config.omc_expected_sha256
    )
    if identities_match:
        return (
            resolved_source,
            resolved_compiler,
            resolved_parent,
            source_sha256,
            compiler_sha256,
        )
    else:
        raise ValueError("Modelica source or OpenModelica executable digest differs")


def _read_openmodelica_version(
    executable_path: Path,
    expected_version: str,
) -> str:
    """Run the sole bounded version probe admitted before compilation.

    :param executable_path: Statically authenticated compiler executable.
    :param expected_version: Exact caller-expected version text.
    :return: Validated version text.
    """

    try:
        completed: subprocess.CompletedProcess[bytes] = subprocess.run(
            [str(executable_path), "--version"],
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as version_error:
        raise RuntimeError("OpenModelica version probe failed") from version_error
    stdout_text: str = completed.stdout.decode("utf-8", errors="strict").strip()
    stderr_text: str = completed.stderr.decode("utf-8", errors="strict").strip()
    output_is_valid: bool = bool(
        completed.returncode == 0
        and len(completed.stdout) <= 4096
        and len(completed.stderr) <= 4096
        and stdout_text == expected_version
        and "\x00" not in stdout_text
        and "\x00" not in stderr_text
    )
    if output_is_valid:
        return stdout_text
    else:
        raise RuntimeError("OpenModelica version differs from the pinned identity")


def _write_openmodelica_build_script(
    script_path: Path,
    source_path: Path,
    stop_time: float,
    step_size: float,
) -> None:
    """Write the deterministic OpenModelica build and native-simulation script.

    :param script_path: New script path inside the owned staging directory.
    :param source_path: Canonical authenticated Modelica source.
    :param stop_time: Simulation stop time in seconds.
    :param step_size: Output interval in seconds.
    :return: None.
    """

    interval_count: int = int(round(stop_time / step_size))
    portable_source: str = source_path.as_posix().replace('"', '\\"')
    script_text: str = (
        f'loadFile("{portable_source}");\n'
        "getErrorString();\n"
        "buildModelFMU(VeraGridSmibNetworkPlant, version=\"2.0\", "
        "fmuType=\"cs\", fileNamePrefix=\"smib_network_plant\");\n"
        "getErrorString();\n"
        f"simulate(VeraGridSmibNetworkPlant, startTime=0.0, stopTime={stop_time:.17g}, "
        f"numberOfIntervals={interval_count}, tolerance=1e-10, method=\"dassl\", "
        "outputFormat=\"csv\", fileNamePrefix=\"smib_native\");\n"
        "getErrorString();\n"
    )
    script_path.write_text(script_text, encoding="utf-8", newline="\n")


def _run_bounded_openmodelica_process(
    executable_path: Path,
    staging_directory: Path,
    script_path: Path,
    timeout_seconds: float,
) -> None:
    """Run one shell-free OpenModelica build within time and output bounds.

    :param executable_path: Authenticated OpenModelica executable.
    :param staging_directory: Unique owned build directory.
    :param script_path: Build script inside the staging directory.
    :param timeout_seconds: Maximum elapsed process time.
    :return: None.
    """

    stdout_path: Path = staging_directory / "openmodelica_stdout.log"
    stderr_path: Path = staging_directory / "openmodelica_stderr.log"
    command: list[str] = [str(executable_path), str(script_path)]
    with stdout_path.open("wb") as stdout_file, stderr_path.open("wb") as stderr_file:
        stdout_handle: BinaryIO = stdout_file
        stderr_handle: BinaryIO = stderr_file
        try:
            process: subprocess.Popen[bytes] = subprocess.Popen(
                command,
                cwd=staging_directory,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
            )
        except OSError as launch_error:
            raise RuntimeError("Unable to launch authenticated OpenModelica") from launch_error
        started_at: float = time.monotonic()
        process_error: RuntimeError | None = None
        while process.poll() is None and process_error is None:
            elapsed_seconds: float = time.monotonic() - started_at
            output_size_bytes: int = 0
            try:
                output_entry: Path
                for output_entry in staging_directory.rglob("*"):
                    if output_entry.is_symlink():
                        process_error = RuntimeError("OpenModelica produced a symbolic link")
                    else:
                        if output_entry.is_file():
                            output_size_bytes += output_entry.stat().st_size
                        else:
                            pass
            except FileNotFoundError:
                pass
            if process_error is not None:
                pass
            else:
                if elapsed_seconds > timeout_seconds:
                    process_error = RuntimeError("OpenModelica exceeded its deadline")
                else:
                    if output_size_bytes > 268435456:
                        process_error = RuntimeError("OpenModelica output exceeded 256 MiB")
                    else:
                        time.sleep(0.05)
        if process_error is not None:
            process.terminate()
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2.0)
            raise process_error
        else:
            return_code: int = process.wait()
    if return_code == 0:
        pass
    else:
        raise RuntimeError(f"OpenModelica exited with status {return_code}")


def _parse_openmodelica_native_trace(
    raw_csv_path: Path,
    canonical_csv_path: Path,
    stop_time: float,
    step_size: float,
) -> Path:
    """Select exact post-event lattice rows from OpenModelica native output.

    :param raw_csv_path: Native OpenModelica result CSV.
    :param canonical_csv_path: New canonical retained trace path.
    :param stop_time: Required final time in seconds.
    :param step_size: Required lattice interval in seconds.
    :return: Written canonical trace path.
    """

    if not raw_csv_path.is_symlink() and raw_csv_path.is_file():
        pass
    else:
        raise RuntimeError("OpenModelica native result CSV is absent or unsafe")
    sample_count: int = int(round(stop_time / step_size)) + 1
    time_values: np.ndarray = np.zeros(sample_count, dtype=float)
    angle_values: np.ndarray = np.zeros(sample_count, dtype=float)
    speed_values: np.ndarray = np.zeros(sample_count, dtype=float)
    power_values: np.ndarray = np.zeros(sample_count, dtype=float)
    reactance_values: np.ndarray = np.zeros(sample_count, dtype=float)
    rows_present: np.ndarray = np.zeros(sample_count, dtype=bool)
    with raw_csv_path.open("r", encoding="utf-8", newline="") as raw_file:
        raw_handle: TextIO = raw_file
        reader: csv.reader = csv.reader(raw_handle)
        header: list[str] = next(reader)
        required_columns: tuple[str, ...] = (
            "time",
            "angle",
            "speed",
            "electricalPower",
            "effectiveReactance",
        )
        column_indices: list[int] = [0] * len(required_columns)
        column_index: int
        for column_index in range(len(required_columns)):
            column_indices[column_index] = header.index(required_columns[column_index])
        row: list[str]
        for row in reader:
            time_value: float = float(row[column_indices[0]])
            sample_index: int = int(round(time_value / step_size))
            row_is_on_lattice: bool = bool(
                0 <= sample_index < sample_count
                and abs(time_value - sample_index * step_size) <= 1e-12
            )
            if row_is_on_lattice:
                # OpenModelica can emit both sides of a time event. Overwriting
                # retains the final post-event row without interpolation.
                time_values[sample_index] = time_value
                angle_values[sample_index] = float(row[column_indices[1]])
                speed_values[sample_index] = float(row[column_indices[2]])
                power_values[sample_index] = float(row[column_indices[3]])
                reactance_values[sample_index] = float(row[column_indices[4]])
                rows_present[sample_index] = True
            else:
                pass
    arrays_are_valid: bool = bool(
        np.all(rows_present)
        and np.all(np.isfinite(time_values))
        and np.all(np.isfinite(angle_values))
        and np.all(np.isfinite(speed_values))
        and np.all(np.isfinite(power_values))
        and np.all(np.isfinite(reactance_values))
    )
    if arrays_are_valid:
        pass
    else:
        raise RuntimeError("OpenModelica native trace is incomplete or nonfinite")
    with canonical_csv_path.open("x", encoding="utf-8", newline="\n") as output_file:
        output_handle: TextIO = output_file
        writer: csv.writer = csv.writer(output_handle, lineterminator="\n")
        writer.writerow(
            [
                "sample_index",
                "time_seconds",
                "angle_rad",
                "speed_pu",
                "electrical_power_pu",
                "effective_reactance_pu",
            ]
        )
        sample_index: int
        for sample_index in range(sample_count):
            writer.writerow(
                [
                    sample_index,
                    f"{time_values[sample_index]:.17e}",
                    f"{angle_values[sample_index]:.17e}",
                    f"{speed_values[sample_index]:.17e}",
                    f"{power_values[sample_index]:.17e}",
                    f"{reactance_values[sample_index]:.17e}",
                ]
            )
    return canonical_csv_path


def _verify_openmodelica_outputs(
    staging_directory: Path,
    source_path: Path,
    source_sha256: str,
    compiler_path: Path,
    compiler_sha256: str,
) -> tuple[Path, str, Path]:
    """Verify required outputs and that authenticated inputs did not drift.

    :param staging_directory: Completed owned build directory.
    :param source_path: Authenticated Modelica source.
    :param source_sha256: Source digest observed before execution.
    :param compiler_path: Authenticated compiler executable.
    :param compiler_sha256: Compiler digest observed before execution.
    :return: FMU path, FMU digest and canonical native trace path.
    """

    with source_path.open("rb") as source_file:
        source_after: str = hashlib.file_digest(source_file, "sha256").hexdigest()
    with compiler_path.open("rb") as compiler_file:
        compiler_after: str = hashlib.file_digest(compiler_file, "sha256").hexdigest()
    if source_after == source_sha256 and compiler_after == compiler_sha256:
        pass
    else:
        raise RuntimeError("Authenticated OpenModelica input changed during execution")
    fmu_path: Path = staging_directory / "smib_network_plant.fmu"
    raw_csv_path: Path = staging_directory / "smib_native_res.csv"
    outputs_are_valid: bool = bool(
        not fmu_path.is_symlink()
        and fmu_path.is_file()
        and 0 < fmu_path.stat().st_size <= 67108864
        and not raw_csv_path.is_symlink()
        and raw_csv_path.is_file()
        and 0 < raw_csv_path.stat().st_size <= 16777216
    )
    if outputs_are_valid:
        pass
    else:
        raise RuntimeError("OpenModelica did not produce the bounded FMU and trace")
    with fmu_path.open("rb") as fmu_file:
        fmu_sha256: str = hashlib.file_digest(fmu_file, "sha256").hexdigest()
    canonical_csv_path: Path = _parse_openmodelica_native_trace(
        raw_csv_path=raw_csv_path,
        canonical_csv_path=staging_directory / "openmodelica_native_trace.csv",
        stop_time=4.0,
        step_size=0.002,
    )
    return fmu_path, fmu_sha256, canonical_csv_path


def _publish_openmodelica_evidence(
    staging_directory: Path,
    output_directory: Path,
) -> None:
    """Publish the verified OpenModelica directory atomically.

    :param staging_directory: Complete verified staging directory.
    :param output_directory: Nonexistent final evidence directory.
    :return: None.
    """

    if not output_directory.exists():
        os.replace(staging_directory, output_directory)
    else:
        raise RuntimeError("OpenModelica output directory appeared before publication")


def build_openmodelica_smib_evidence(
    config: OpenModelicaBuildConfig,
) -> OpenModelicaBuildEvidence:
    """Build the SMIB FMI 2 CS archive and native reference trajectory.

    :param config: Exact source, compiler and output contract.
    :return: Published OpenModelica build evidence.
    """

    resolved_source: Path
    resolved_compiler: Path
    resolved_parent: Path
    source_sha256: str
    compiler_sha256: str
    (
        resolved_source,
        resolved_compiler,
        resolved_parent,
        source_sha256,
        compiler_sha256,
    ) = _validate_openmodelica_config(config)

    # Only a successful bounded probe unlocks compiler workload execution.
    compiler_version: str = _read_openmodelica_version(
        executable_path=resolved_compiler,
        expected_version=config.omc_expected_version,
    )
    staging_directory: Path = Path(
        tempfile.mkdtemp(prefix=".smib-openmodelica-", dir=str(resolved_parent))
    ).resolve(strict=True)
    publication_succeeded: bool = False
    try:
        script_path: Path = staging_directory / "build_smib.mos"
        _write_openmodelica_build_script(
            script_path=script_path,
            source_path=resolved_source,
            stop_time=config.stop_time,
            step_size=config.step_size,
        )
        _run_bounded_openmodelica_process(
            executable_path=resolved_compiler,
            staging_directory=staging_directory,
            script_path=script_path,
            timeout_seconds=config.process_timeout_seconds,
        )
        staged_fmu_path: Path
        fmu_sha256: str
        staged_native_csv_path: Path
        staged_fmu_path, fmu_sha256, staged_native_csv_path = (
            _verify_openmodelica_outputs(
                staging_directory=staging_directory,
                source_path=resolved_source,
                source_sha256=source_sha256,
                compiler_path=resolved_compiler,
                compiler_sha256=compiler_sha256,
            )
        )
        _publish_openmodelica_evidence(
            staging_directory=staging_directory,
            output_directory=config.output_directory,
        )
        publication_succeeded = True
    finally:
        if publication_succeeded:
            pass
        else:
            if staging_directory.exists():
                shutil.rmtree(staging_directory)
            else:
                pass

    return OpenModelicaBuildEvidence(
        source_path=resolved_source,
        source_size_bytes=config.source_expected_size_bytes,
        source_sha256=source_sha256,
        omc_executable=resolved_compiler,
        omc_sha256=compiler_sha256,
        omc_version=compiler_version,
        fmu_path=config.output_directory / staged_fmu_path.name,
        fmu_sha256=fmu_sha256,
        native_csv_path=config.output_directory / staged_native_csv_path.name,
        build_stdout_path=config.output_directory / "openmodelica_stdout.log",
        build_stderr_path=config.output_directory / "openmodelica_stderr.log",
    )
