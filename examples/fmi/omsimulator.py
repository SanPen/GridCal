# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import csv
import hashlib
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import time
from typing import BinaryIO

import numpy as np

from VeraGridEngine.IO.fmu.model_description import FmuInterfaceMode


class OmsimulatorTrace:
    """Own one validated OMSimulator trajectory and its runtime identities."""

    __slots__ = (
        "_time_seconds",
        "_voltage_magnitude",
        "_active_power",
        "_reactive_power",
        "_runtime_version",
        "_executable_sha256",
        "_driver_sha256",
        "_input_sha256",
        "_output_sha256",
        "_runtime_log_sha256",
    )

    def __init__(
            self,
            time_seconds: np.ndarray,
            voltage_magnitude: np.ndarray,
            active_power: np.ndarray,
            reactive_power: np.ndarray,
            runtime_version: str,
            executable_sha256: str,
            driver_sha256: str,
            input_sha256: str,
            output_sha256: str,
            runtime_log_sha256: str,
    ) -> None:
        """Retain a validated trace without sharing mutable numerical arrays.

        :param time_seconds: Exact 301-sample comparison lattice.
        :param voltage_magnitude: Voltage input echoed by OMSimulator.
        :param active_power: OMSimulator active-power output in p.u.
        :param reactive_power: OMSimulator reactive-power output in p.u.
        :param runtime_version: Version reported by the pinned executable.
        :param executable_sha256: Stable executable identity.
        :param driver_sha256: Stable retained Lua-driver identity.
        :param input_sha256: Stable retained input-CSV identity.
        :param output_sha256: Stable retained output-CSV identity.
        :param runtime_log_sha256: Stable retained OMSimulator-log identity.
        :return: None.
        """

        arrays_are_valid: bool = bool(
            time_seconds.shape == (301,)
            and voltage_magnitude.shape == time_seconds.shape
            and active_power.shape == time_seconds.shape
            and reactive_power.shape == time_seconds.shape
            and np.all(np.isfinite(time_seconds))
            and np.all(np.isfinite(voltage_magnitude))
            and np.all(np.isfinite(active_power))
            and np.all(np.isfinite(reactive_power))
        )
        hashes_are_valid: bool = bool(
            len(executable_sha256) == 64
            and len(driver_sha256) == 64
            and len(input_sha256) == 64
            and len(output_sha256) == 64
            and len(runtime_log_sha256) == 64
        )
        if arrays_are_valid and hashes_are_valid and runtime_version.strip():
            pass
        else:
            raise ValueError("OMSimulator trace data and identities must be complete")

        self._time_seconds: np.ndarray = np.array(time_seconds, dtype=float, copy=True)
        self._voltage_magnitude: np.ndarray = np.array(
            voltage_magnitude,
            dtype=float,
            copy=True,
        )
        self._active_power: np.ndarray = np.array(active_power, dtype=float, copy=True)
        self._reactive_power: np.ndarray = np.array(
            reactive_power,
            dtype=float,
            copy=True,
        )
        self._runtime_version: str = runtime_version.strip()
        self._executable_sha256: str = executable_sha256
        self._driver_sha256: str = driver_sha256
        self._input_sha256: str = input_sha256
        self._output_sha256: str = output_sha256
        self._runtime_log_sha256: str = runtime_log_sha256

    def get_time_seconds(self) -> np.ndarray:
        """Return a defensive copy of the OMSimulator time lattice.

        :return: Time samples in seconds.
        """

        return self._time_seconds.copy()

    def get_voltage_magnitude(self) -> np.ndarray:
        """Return the voltage samples echoed by OMSimulator.

        :return: Voltage magnitude in p.u.
        """

        return self._voltage_magnitude.copy()

    def get_active_power(self) -> np.ndarray:
        """Return the OMSimulator active-power trajectory.

        :return: Active power in p.u.
        """

        return self._active_power.copy()

    def get_reactive_power(self) -> np.ndarray:
        """Return the OMSimulator reactive-power trajectory.

        :return: Reactive power in p.u.
        """

        return self._reactive_power.copy()

    def get_runtime_version(self) -> str:
        """Return the version reported by the OMSimulator executable.

        :return: Non-empty runtime version text.
        """

        return self._runtime_version

    def get_executable_sha256(self) -> str:
        """Return the stable OMSimulator executable SHA-256.

        :return: Lowercase SHA-256 text.
        """

        return self._executable_sha256

    def get_driver_sha256(self) -> str:
        """Return the stable retained Lua-driver SHA-256.

        :return: Lowercase SHA-256 text.
        """

        return self._driver_sha256

    def get_input_sha256(self) -> str:
        """Return the retained input-CSV SHA-256.

        :return: Lowercase SHA-256 text.
        """

        return self._input_sha256

    def get_output_sha256(self) -> str:
        """Return the retained raw output-CSV SHA-256.

        :return: Lowercase SHA-256 text.
        """

        return self._output_sha256

    def get_runtime_log_sha256(self) -> str:
        """Return the retained OMSimulator runtime-log SHA-256.

        :return: Lowercase SHA-256 text.
        """

        return self._runtime_log_sha256


def _verify_regular_file_path(
        path: Path,
        size_limit_bytes: int | None,
        role: str,
) -> Path:
    """Validate every caller-visible path component before resolving identity.

    :param path: File path whose components must not use symbolic indirection.
    :param size_limit_bytes: Inclusive maximum file size, or ``None`` when the
        caller requires identity validation without a size cap.
    :param role: Human-readable role used in a failure message.
    :return: Strictly resolved regular-file path.
    """

    # Build an absolute spelling without resolving links so every caller-visible
    # component remains available for the reparse-point inspection below.
    absolute_path: Path = path.absolute()
    component_path: Path = Path(absolute_path.anchor)
    components_are_regular: bool = True
    path_part: str
    for path_part in absolute_path.parts[1:]:
        component_path = component_path / path_part
        component_exists: bool = bool(
            component_path.exists() or component_path.is_symlink()
        )
        if component_exists:
            if os.name == "nt":
                component_status: os.stat_result = os.lstat(component_path)
                component_is_indirect: bool = bool(
                    component_status.st_file_attributes
                    & stat.FILE_ATTRIBUTE_REPARSE_POINT
                )
            else:
                component_is_indirect = component_path.is_symlink()
            if component_is_indirect:
                components_are_regular = False
            else:
                pass
        else:
            components_are_regular = False

    size_limit_is_valid: bool = bool(
        size_limit_bytes is None
        or (
            isinstance(size_limit_bytes, int)
            and not isinstance(size_limit_bytes, bool)
            and size_limit_bytes >= 0
        )
    )
    path_is_valid: bool = bool(
        components_are_regular
        and not path.is_symlink()
        and path.is_file()
        and size_limit_is_valid
        and bool(role.strip())
    )
    if path_is_valid:
        resolved_path: Path = path.resolve(strict=True)
    else:
        raise ValueError(f"{role} must be a regular non-symlink file")

    # Recheck the resolved target and size to detect replacement between the
    # caller-visible component walk and the final identity acquisition.
    resolved_path_is_valid: bool = bool(
        not resolved_path.is_symlink()
        and resolved_path.is_file()
        and (
            size_limit_bytes is None
            or resolved_path.stat().st_size <= size_limit_bytes
        )
    )
    if resolved_path_is_valid:
        return resolved_path
    else:
        raise ValueError(f"{role} exceeds its size limit or changed during validation")


def _write_omsimulator_input_csv(
        path: Path,
        mode: FmuInterfaceMode,
        time_seconds: np.ndarray,
        voltage_magnitude: np.ndarray,
) -> str:
    """Write the strict input contract consumed by the static Lua driver.

    :param path: Retained CSV destination.
    :param mode: FMI interface mode for every row.
    :param time_seconds: Exact 301-sample time lattice.
    :param voltage_magnitude: Finite voltage input for every sample.
    :return: SHA-256 of the written CSV.
    """

    expected_time_seconds: np.ndarray = np.arange(301, dtype=float) * 1.0e-3
    values_are_valid: bool = bool(
        mode in (FmuInterfaceMode.CO_SIMULATION, FmuInterfaceMode.MODEL_EXCHANGE)
        and time_seconds.shape == expected_time_seconds.shape
        and voltage_magnitude.shape == expected_time_seconds.shape
        and np.all(np.isfinite(time_seconds))
        and np.all(np.isfinite(voltage_magnitude))
        and np.all(np.abs(time_seconds - expected_time_seconds) <= 1.0e-12)
    )
    if values_are_valid:
        pass
    else:
        raise ValueError("OMSimulator input requires the exact finite 301-sample lattice")

    # Writing rows directly avoids a second in-memory representation of the trace.
    with path.open("w", encoding="utf-8", newline="\n") as file_handle:
        file_handle.write("sample_index,mode,time_seconds,voltage_magnitude_pu\n")
        sample_index: int
        for sample_index in range(time_seconds.size):
            file_handle.write(
                f"{sample_index},{mode.value},"
                f"{time_seconds[sample_index]:.17e},"
                f"{voltage_magnitude[sample_index]:.17e}\n"
            )

    if path.stat().st_size <= 65536:
        pass
    else:
        raise RuntimeError("OMSimulator input CSV exceeds the 64 KiB contract")
    with path.open("rb") as file_handle_binary:
        return hashlib.file_digest(file_handle_binary, "sha256").hexdigest()


def _read_omsimulator_trace_csv(
        path: Path,
        mode: FmuInterfaceMode,
        expected_time_seconds: np.ndarray,
        expected_voltage_magnitude: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Parse and independently validate the raw OMSimulator CSV.

    :param path: Raw output CSV produced by the static driver.
    :param mode: Expected interface mode in every row.
    :param expected_time_seconds: Exact input time lattice.
    :param expected_voltage_magnitude: Exact input voltage samples.
    :return: Time, voltage, active-power and reactive-power arrays.
    """

    raw_bytes: bytes = path.read_bytes()
    bytes_are_valid: bool = bool(
        len(raw_bytes) <= 262144
        and raw_bytes.endswith(b"\n")
        and b"\r" not in raw_bytes
        and b"\xef\xbb\xbf" not in raw_bytes[:3]
        and b'"' not in raw_bytes
        and b"\n\n" not in raw_bytes
    )
    if bytes_are_valid:
        pass
    else:
        raise RuntimeError("OMSimulator raw CSV violates encoding or size limits")

    time_seconds: np.ndarray = np.empty(301, dtype=float)
    voltage_magnitude: np.ndarray = np.empty(301, dtype=float)
    active_power: np.ndarray = np.empty(301, dtype=float)
    reactive_power: np.ndarray = np.empty(301, dtype=float)
    with path.open("r", encoding="utf-8", newline="") as file_handle:
        rows: list[list[str]] = list(csv.reader(file_handle))
    header_is_valid: bool = bool(
        len(rows) == 302
        and rows[0] == [
            "sample_index",
            "mode",
            "time_seconds",
            "voltage_magnitude_pu",
            "active_power_pu",
            "reactive_power_pu",
        ]
    )
    if header_is_valid:
        pass
    else:
        raise RuntimeError("OMSimulator raw CSV header or row count is invalid")

    sample_index: int
    for sample_index in range(301):
        row: list[str] = rows[sample_index + 1]
        if len(row) == 6:
            pass
        else:
            raise RuntimeError("OMSimulator raw CSV has an invalid column count")
        try:
            row_index: int = int(row[0])
            row_time: float = float(row[2])
            row_voltage: float = float(row[3])
            row_active_power: float = float(row[4])
            row_reactive_power: float = float(row[5])
        except ValueError as parse_error:
            raise RuntimeError("OMSimulator raw CSV contains a malformed value") from parse_error
        row_is_valid: bool = bool(
            row[0] == str(sample_index)
            and row_index == sample_index
            and row[1] == mode.value
            and row[2] == format(row_time, ".17e")
            and row[3] == format(row_voltage, ".17e")
            and row[4] == format(row_active_power, ".17e")
            and row[5] == format(row_reactive_power, ".17e")
            and math.isfinite(row_time)
            and math.isfinite(row_voltage)
            and math.isfinite(row_active_power)
            and math.isfinite(row_reactive_power)
        )
        if row_is_valid:
            time_seconds[sample_index] = row_time
            voltage_magnitude[sample_index] = row_voltage
            active_power[sample_index] = row_active_power
            reactive_power[sample_index] = row_reactive_power
        else:
            raise RuntimeError("OMSimulator raw CSV contains a noncanonical row")

    alignment_is_valid: bool = bool(
        np.all(np.diff(time_seconds) > 0.0)
        and np.all(np.abs(time_seconds - expected_time_seconds) <= 1.0e-12)
        and np.all(
            np.abs(voltage_magnitude - expected_voltage_magnitude) <= 1.0e-12
        )
        # The native RMS event first changes the retained voltage input at 101.
        # A causal CS FMU consumes that value during the following interval,
        # while ME may expose direct feedthrough at the same sample.
        and abs(voltage_magnitude[101] - voltage_magnitude[100]) > 1.0e-5
    )
    if alignment_is_valid:
        return time_seconds, voltage_magnitude, active_power, reactive_power
    else:
        raise RuntimeError("OMSimulator raw trace is not aligned with its input")


def _run_bounded_version_process(
        executable_path: Path,
        runtime_dir: Path,
) -> tuple[bytes, bytes]:
    """Run ``OMSimulator --version`` with bounded file-backed output.

    :param executable_path: Validated explicit OMSimulator executable.
    :param runtime_dir: Unique runtime directory owned by the current execution.
    :return: Bounded stdout and stderr bytes after a successful zero exit.
    """

    stdout_path: Path = runtime_dir / "omsimulator_version_stdout.log"
    stderr_path: Path = runtime_dir / "omsimulator_version_stderr.log"
    command: list[str] = list((str(executable_path), "--version"))
    with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
        typed_stdout_handle: BinaryIO = stdout_handle
        typed_stderr_handle: BinaryIO = stderr_handle
        try:
            process: subprocess.Popen[bytes] = subprocess.Popen(
                command,
                cwd=runtime_dir,
                shell=False,
                stdout=typed_stdout_handle,
                stderr=typed_stderr_handle,
            )
        except OSError as launch_error:
            raise RuntimeError("Unable to launch OMSimulator version process") from launch_error
        started_at: float = time.monotonic()
        process_failure: RuntimeError | None = None
        while process.poll() is None and process_failure is None:
            elapsed_seconds: float = time.monotonic() - started_at
            stdout_size_bytes: int = stdout_path.stat().st_size
            stderr_size_bytes: int = stderr_path.stat().st_size
            if elapsed_seconds > 10.0:
                process_failure = RuntimeError("OMSimulator version process timed out")
            elif stdout_size_bytes > 4194304 or stderr_size_bytes > 4194304:
                process_failure = RuntimeError("OMSimulator version output exceeded 4 MiB")
            else:
                time.sleep(0.02)
        if process_failure is not None:
            _terminate_omsimulator_process(process)
            raise process_failure
        else:
            return_code: int = process.wait()
    stdout_bytes: bytes = stdout_path.read_bytes()
    stderr_bytes: bytes = stderr_path.read_bytes()
    result_is_valid: bool = bool(
        return_code == 0
        and len(stdout_bytes) <= 4194304
        and len(stderr_bytes) <= 4194304
    )
    if result_is_valid:
        return stdout_bytes, stderr_bytes
    elif return_code != 0:
        raise RuntimeError(f"OMSimulator version process exited with status {return_code}")
    else:
        raise RuntimeError("OMSimulator version output exceeded 4 MiB")


def _read_omsimulator_version(
        executable_path: Path,
        runtime_dir: Path,
) -> str:
    """Read a bounded version string from the pinned OMSimulator executable.

    :param executable_path: Explicit validated regular executable path.
    :param runtime_dir: Unique owned directory for file-backed process output.
    :return: Non-empty single-line version text.
    """

    stdout_bytes: bytes
    stderr_bytes: bytes
    stdout_bytes, stderr_bytes = _run_bounded_version_process(
        executable_path,
        runtime_dir,
    )
    try:
        version_text: str = stdout_bytes.decode("utf-8", errors="strict").strip()
        stderr_text: str = stderr_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as decode_error:
        raise RuntimeError("OMSimulator returned non-UTF-8 version output") from decode_error
    version_is_valid: bool = bool(
        bool(version_text)
        and "\n" not in version_text
        and "\r" not in version_text
        and "\x00" not in version_text
        and "\x00" not in stderr_text
    )
    if version_is_valid:
        return version_text
    else:
        raise RuntimeError("OMSimulator returned an invalid version string")

def _terminate_omsimulator_process(process: subprocess.Popen[bytes]) -> None:
    """Stop the direct OMSimulator process within the bounded shutdown window.

    :param process: Running direct child process.
    :return: None.
    """

    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2.0)
    else:
        pass


def run_bounded_omsimulator_process(
        executable_path: Path,
        runtime_dir: Path,
        process_arguments: tuple[str, ...],
        timeout_seconds: float,
) -> None:
    """Run and monitor one shell-free OMSimulator simulation process.

    :param executable_path: Explicit pinned OMSimulator executable.
    :param runtime_dir: Unique owned runtime working directory.
    :param process_arguments: Immutable ordered argument sequence.
    :param timeout_seconds: Python-side process deadline in seconds.
    :return: None.
    """

    stdout_path: Path = runtime_dir / "omsimulator_stdout.log"
    stderr_path: Path = runtime_dir / "omsimulator_stderr.log"
    command: list[str] = [str(executable_path), *process_arguments]
    with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
        typed_stdout_handle: BinaryIO = stdout_handle
        typed_stderr_handle: BinaryIO = stderr_handle
        try:
            process: subprocess.Popen[bytes] = subprocess.Popen(
                command,
                cwd=runtime_dir,
                shell=False,
                stdout=typed_stdout_handle,
                stderr=typed_stderr_handle,
            )
        except OSError as launch_error:
            raise RuntimeError("Unable to launch the pinned OMSimulator executable") from launch_error
        started_at: float = time.monotonic()
        process_failure: RuntimeError | None = None
        while process.poll() is None and process_failure is None:
            elapsed_seconds: float = time.monotonic() - started_at
            runtime_size_bytes: int = 0
            try:
                runtime_entry: Path
                for runtime_entry in runtime_dir.rglob("*"):
                    if runtime_entry.is_symlink():
                        process_failure = RuntimeError(
                            "OMSimulator runtime produced an unsupported symbolic link"
                        )
                    elif runtime_entry.is_file():
                        runtime_size_bytes += runtime_entry.stat().st_size
                    else:
                        pass
            except FileNotFoundError:
                pass
            stdout_size_bytes: int = stdout_path.stat().st_size
            stderr_size_bytes: int = stderr_path.stat().st_size
            if process_failure is not None:
                pass
            elif elapsed_seconds > timeout_seconds:
                process_failure = RuntimeError("OMSimulator exceeded its 35 s deadline")
            elif stdout_size_bytes > 4194304 or stderr_size_bytes > 4194304:
                process_failure = RuntimeError("OMSimulator stdout or stderr exceeded 4 MiB")
            elif runtime_size_bytes > 134217728:
                process_failure = RuntimeError("OMSimulator runtime tree exceeded 128 MiB")
            else:
                time.sleep(0.02)
        if process_failure is not None:
            _terminate_omsimulator_process(process)
            raise process_failure
        else:
            return_code: int = process.wait()
    final_runtime_size_bytes: int = 0
    final_runtime_entry: Path
    for final_runtime_entry in runtime_dir.rglob("*"):
        if final_runtime_entry.is_symlink():
            raise RuntimeError(
                "OMSimulator runtime produced an unsupported symbolic link"
            )
        elif final_runtime_entry.is_file():
            final_runtime_size_bytes += final_runtime_entry.stat().st_size
        else:
            pass
    process_result_is_valid: bool = bool(
        return_code == 0 and final_runtime_size_bytes <= 134217728
    )
    if process_result_is_valid:
        pass
    elif return_code != 0:
        raise RuntimeError(f"OMSimulator exited with status {return_code}")
    else:
        raise RuntimeError("OMSimulator runtime tree exceeded 128 MiB")


def execute_omsimulator_trace(
        executable_path: Path,
        mode: FmuInterfaceMode,
        fmu_path: Path,
        output_dir: Path,
        time_seconds: np.ndarray,
        voltage_magnitude: np.ndarray,
        timeout_seconds: float,
) -> tuple[OmsimulatorTrace, tuple[str, ...]]:
    """Execute one FMI mode with OMSimulator and retain validated raw evidence.

    :param executable_path: Explicit installed OMSimulator executable.
    :param mode: Co-Simulation or Model Exchange mode to execute.
    :param fmu_path: Exact exported FMU used by every comparison path.
    :param output_dir: Existing mode-specific staging directory.
    :param time_seconds: Exact accepted VeraGrid time lattice.
    :param voltage_magnitude: Exact accepted VeraGrid voltage input.
    :param timeout_seconds: Python-side process deadline.
    :return: Validated trace and the immutable arguments passed to OMSimulator.
    """

    resolved_executable: Path = _verify_regular_file_path(
        executable_path,
        None,
        "OMSimulator executable",
    )
    resolved_fmu: Path = _verify_regular_file_path(
        fmu_path,
        67108864,
        "Exported FMU",
    )
    output_dir_is_valid: bool = bool(
        not output_dir.is_symlink()
        and output_dir.is_dir()
    )
    if output_dir_is_valid:
        resolved_output_dir: Path = output_dir.resolve(strict=True)
    else:
        raise ValueError("OMSimulator output directory must be a regular directory")
    timeout_is_valid: bool = bool(
        math.isfinite(timeout_seconds)
        and timeout_seconds == 35.0
    )
    if timeout_is_valid:
        pass
    else:
        raise ValueError("OMSimulator timeout must match the sealed contract")

    driver_source_candidate: Path = Path(__file__).resolve(strict=True).with_name("omsimulator_driver.lua")
    driver_source_path: Path = _verify_regular_file_path(
        driver_source_candidate,
        65536,
        "Static OMSimulator driver",
    )
    retained_driver_path: Path = resolved_output_dir / "omsimulator_driver.lua"
    retained_input_path: Path = resolved_output_dir / "omsimulator_input.csv"
    retained_output_path: Path = resolved_output_dir / "omsimulator_output.csv"
    retained_runtime_log_path: Path = resolved_output_dir / "omsimulator.log"
    retained_stdout_path: Path = resolved_output_dir / "omsimulator_stdout.log"
    retained_stderr_path: Path = resolved_output_dir / "omsimulator_stderr.log"
    shutil.copyfile(driver_source_path, retained_driver_path)
    input_sha256: str = _write_omsimulator_input_csv(
        retained_input_path,
        mode,
        time_seconds,
        voltage_magnitude,
    )
    with driver_source_path.open("rb") as driver_source_handle:
        driver_source_sha256: str = hashlib.file_digest(
            driver_source_handle,
            "sha256",
        ).hexdigest()
    with retained_driver_path.open("rb") as retained_driver_handle:
        driver_sha256_before: str = hashlib.file_digest(
            retained_driver_handle,
            "sha256",
        ).hexdigest()
    with resolved_executable.open("rb") as executable_handle:
        executable_sha256_before: str = hashlib.file_digest(
            executable_handle,
            "sha256",
        ).hexdigest()
    with resolved_fmu.open("rb") as source_fmu_handle:
        source_fmu_sha256_before: str = hashlib.file_digest(
            source_fmu_handle,
            "sha256",
        ).hexdigest()
    if driver_source_sha256 == driver_sha256_before:
        pass
    else:
        raise RuntimeError("Retained OMSimulator driver differs from its source")

    runtime_dir: Path = Path(
        tempfile.mkdtemp(prefix=".omsimulator-runtime-", dir=str(resolved_output_dir))
    ).resolve()
    primary_error: OSError | ValueError | RuntimeError | subprocess.SubprocessError | None = None
    try:
        runtime_fmu_path: Path = runtime_dir / "model.fmu"
        runtime_driver_path: Path = runtime_dir / "omsimulator_driver.lua"
        runtime_input_path: Path = runtime_dir / "omsimulator_input.csv"
        shutil.copyfile(resolved_fmu, runtime_fmu_path)
        shutil.copyfile(retained_driver_path, runtime_driver_path)
        shutil.copyfile(retained_input_path, runtime_input_path)
        with runtime_fmu_path.open("rb") as runtime_fmu_handle:
            runtime_fmu_sha256_before: str = hashlib.file_digest(
                runtime_fmu_handle,
                "sha256",
            ).hexdigest()
        if runtime_fmu_sha256_before == source_fmu_sha256_before:
            pass
        else:
            raise RuntimeError("Owned OMSimulator FMU copy differs from its source")

        if mode == FmuInterfaceMode.CO_SIMULATION:
            process_arguments: tuple[str, ...] = (
                "--workingDir=.", "--tempDir=temp", "--deleteTempFiles=true",
                "--logFile=omsimulator.log", "--suppressPath=true",
                "--timeout=30", "omsimulator_driver.lua",
            )
        elif mode == FmuInterfaceMode.MODEL_EXCHANGE:
            process_arguments = (
                "--workingDir=.", "--tempDir=temp", "--deleteTempFiles=true",
                "--logFile=omsimulator.log", "--suppressPath=true",
                "--timeout=30", "--stepSize=1e-5,1e-8,1e-3",
                "omsimulator_driver.lua",
            )
        else:
            raise ValueError(f"Unsupported OMSimulator FMI mode: {mode.value}")

        runtime_version: str = _read_omsimulator_version(
            resolved_executable,
            runtime_dir,
        )
        run_bounded_omsimulator_process(
            resolved_executable, runtime_dir, process_arguments, timeout_seconds
        )
        runtime_output_path: Path = runtime_dir / "omsimulator_output.csv"
        runtime_log_path: Path = runtime_dir / "omsimulator.log"
        runtime_stdout_path: Path = runtime_dir / "omsimulator_stdout.log"
        runtime_stderr_path: Path = runtime_dir / "omsimulator_stderr.log"
        runtime_files_are_valid: bool = bool(
            runtime_output_path.is_file()
            and runtime_log_path.is_file()
            and runtime_stdout_path.is_file()
            and runtime_stderr_path.is_file()
            and runtime_output_path.stat().st_size <= 262144
            and runtime_log_path.stat().st_size <= 4194304
            and runtime_stdout_path.stat().st_size <= 4194304
            and runtime_stderr_path.stat().st_size <= 4194304
        )
        if runtime_files_are_valid:
            pass
        else:
            raise RuntimeError("OMSimulator did not produce bounded raw evidence")
        shutil.copyfile(runtime_output_path, retained_output_path)
        shutil.copyfile(runtime_log_path, retained_runtime_log_path)
        shutil.copyfile(runtime_stdout_path, retained_stdout_path)
        shutil.copyfile(runtime_stderr_path, retained_stderr_path)

        parsed_time: np.ndarray
        parsed_voltage: np.ndarray
        parsed_active_power: np.ndarray
        parsed_reactive_power: np.ndarray
        (
            parsed_time,
            parsed_voltage,
            parsed_active_power,
            parsed_reactive_power,
        ) = _read_omsimulator_trace_csv(
            retained_output_path, mode, time_seconds, voltage_magnitude
        )
        with resolved_executable.open("rb") as executable_after_handle:
            executable_sha256_after: str = hashlib.file_digest(
                executable_after_handle, "sha256"
            ).hexdigest()
        with retained_driver_path.open("rb") as retained_driver_after_handle:
            driver_sha256_after: str = hashlib.file_digest(
                retained_driver_after_handle, "sha256"
            ).hexdigest()
        with runtime_driver_path.open("rb") as runtime_driver_after_handle:
            runtime_driver_sha256_after: str = hashlib.file_digest(
                runtime_driver_after_handle, "sha256"
            ).hexdigest()
        with resolved_fmu.open("rb") as source_fmu_after_handle:
            source_fmu_sha256_after: str = hashlib.file_digest(
                source_fmu_after_handle, "sha256"
            ).hexdigest()
        with runtime_fmu_path.open("rb") as runtime_fmu_after_handle:
            runtime_fmu_sha256_after: str = hashlib.file_digest(
                runtime_fmu_after_handle, "sha256"
            ).hexdigest()
        identities_are_stable: bool = bool(
            executable_sha256_before == executable_sha256_after
            and driver_source_sha256 == driver_sha256_before
            and driver_sha256_before == driver_sha256_after
            and driver_sha256_after == runtime_driver_sha256_after
            and source_fmu_sha256_before == source_fmu_sha256_after
            and source_fmu_sha256_after == runtime_fmu_sha256_before
            and runtime_fmu_sha256_before == runtime_fmu_sha256_after
        )
        if identities_are_stable:
            pass
        else:
            raise RuntimeError("OMSimulator executable, driver or FMU identity changed")
        with retained_output_path.open("rb") as output_handle:
            output_sha256: str = hashlib.file_digest(output_handle, "sha256").hexdigest()
        with retained_runtime_log_path.open("rb") as runtime_log_handle:
            runtime_log_sha256: str = hashlib.file_digest(
                runtime_log_handle, "sha256"
            ).hexdigest()
        trace: OmsimulatorTrace = OmsimulatorTrace(
            parsed_time, parsed_voltage, parsed_active_power, parsed_reactive_power,
            runtime_version, executable_sha256_after, driver_sha256_after,
            input_sha256, output_sha256, runtime_log_sha256,
        )
        return trace, process_arguments
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as execution_error:
        primary_error = execution_error
        raise
    finally:
        try:
            shutil.rmtree(runtime_dir)
            if runtime_dir.exists():
                raise OSError("Owned OMSimulator runtime child still exists")
            else:
                pass
        except OSError as cleanup_error:
            if primary_error is not None:
                primary_error.add_note(f"OMSimulator cleanup also failed: {cleanup_error}")
            else:
                raise RuntimeError("Unable to remove the owned OMSimulator runtime") from cleanup_error
