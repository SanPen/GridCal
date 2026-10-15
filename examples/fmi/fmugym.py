# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Generate authenticated FMUGym and direct-FMPy comparison evidence."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import BinaryIO, TextIO, cast
import xml.etree.ElementTree as element_tree

import matplotlib
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import matplotlib.image as mpimg
import numpy as np

from examples.fmi.evidence_identity import (
    path_is_link_or_reparse_point,
    read_regular_tree_identity,
    verify_regular_file_identity,
)


class FmugymCellStatus(str, Enum):
    """Terminal classifications for one FMUGym comparison cell."""

    PASS = "PASS"
    COMPLETED_WITH_FINDINGS = "COMPLETED_WITH_FINDINGS"


class FmugymFindingKind(str, Enum):
    """Known upstream behavior retained by the FMUGym benchmark."""

    TIME_HORIZON_FLOAT_ACCUMULATION_RESET_AND_ADVANCE = (
        "time_horizon_float_accumulation_reset_and_advance"
    )


class FmugymComparisonConfig:
    """Own every explicit input and immutable identity for one comparison."""

    __slots__ = (
        "output_directory", "source_branch", "source_revision",
        "source_tree_sha256", "runtime_root", "runtime_entry_count",
        "runtime_regular_bytes", "runtime_tree_sha256",
        "python_executable_path", "python_executable_size_bytes",
        "python_executable_sha256", "wheel_path", "wheel_size_bytes",
        "wheel_sha256", "system_root_path", "processor_architecture",
        "fmi_two_path", "fmi_two_size_bytes", "fmi_two_sha256",
        "fmi_three_path", "fmi_three_size_bytes", "fmi_three_sha256",
        "worker_path", "worker_size_bytes", "worker_sha256",
        "process_timeout_seconds", "stream_limit_bytes",
    )

    def __init__(
        self,
        output_directory: Path,
        source_branch: str,
        source_revision: str,
        source_tree_sha256: str,
        runtime_root: Path,
        runtime_entry_count: int,
        runtime_regular_bytes: int,
        runtime_tree_sha256: str,
        python_executable_size_bytes: int,
        python_executable_sha256: str,
        wheel_path: Path,
        wheel_size_bytes: int,
        wheel_sha256: str,
        system_root_path: Path,
        processor_architecture: str,
        fmi_two_path: Path,
        fmi_two_size_bytes: int,
        fmi_two_sha256: str,
        fmi_three_path: Path,
        fmi_three_size_bytes: int,
        fmi_three_sha256: str,
        worker_path: Path,
        worker_size_bytes: int,
        worker_sha256: str,
        process_timeout_seconds: float,
        stream_limit_bytes: int,
    ) -> None:
        """Validate and retain one closed FMUGym comparison request.

        :param output_directory: New evidence directory published atomically.
        :param source_branch: Source branch recorded in the manifest.
        :param source_revision: Forty-character source commit identity.
        :param source_tree_sha256: Source-tree evidence digest.
        :param runtime_root: Exact external FMUGym Python environment.
        :param runtime_entry_count: Expected runtime regular-file count.
        :param runtime_regular_bytes: Expected aggregate runtime byte count.
        :param runtime_tree_sha256: Expected runtime tree digest.
        :param python_executable_size_bytes: Expected executable byte count.
        :param python_executable_sha256: Expected executable digest.
        :param wheel_path: Exact FMUGym distribution wheel.
        :param wheel_size_bytes: Expected wheel byte count.
        :param wheel_sha256: Expected wheel digest.
        :param system_root_path: Windows system root exposed to workers.
        :param processor_architecture: Windows worker architecture.
        :param fmi_two_path: Exact FMI 2 SMIB Co-Simulation FMU.
        :param fmi_two_size_bytes: Expected FMI 2 FMU byte count.
        :param fmi_two_sha256: Expected FMI 2 FMU digest.
        :param fmi_three_path: Exact FMI 3 Feedthrough Co-Simulation FMU.
        :param fmi_three_size_bytes: Expected FMI 3 FMU byte count.
        :param fmi_three_sha256: Expected FMI 3 FMU digest.
        :param worker_path: Repository-owned isolated worker.
        :param worker_size_bytes: Expected worker byte count.
        :param worker_sha256: Expected worker digest.
        :param process_timeout_seconds: Hard deadline for each worker.
        :param stream_limit_bytes: Independent stdout and stderr byte bound.
        :return: None.
        """

        absolute_paths: tuple[Path, ...] = (
            output_directory, runtime_root, wheel_path,
            system_root_path, fmi_two_path, fmi_three_path, worker_path,
        )
        positive_sizes: tuple[int, ...] = (
            runtime_entry_count, runtime_regular_bytes,
            python_executable_size_bytes, wheel_size_bytes, fmi_two_size_bytes,
            fmi_three_size_bytes, worker_size_bytes, stream_limit_bytes,
        )
        digests: tuple[str, ...] = (
            source_tree_sha256, runtime_tree_sha256, python_executable_sha256,
            wheel_sha256, fmi_two_sha256, fmi_three_sha256, worker_sha256,
        )
        values_are_valid: bool = bool(
            all(path_value.is_absolute() for path_value in absolute_paths)
            and all(
                isinstance(size_value, int)
                and not isinstance(size_value, bool)
                and size_value > 0
                for size_value in positive_sizes
            )
            and all(
                re.fullmatch(r"[0-9a-f]{64}", digest) is not None
                for digest in digests
            )
            and bool(source_branch)
            and re.fullmatch(r"[0-9a-f]{40}", source_revision) is not None
            and runtime_entry_count == 10_748
            and runtime_regular_bytes == 292_058_959
            and runtime_tree_sha256
            == "37f979dba3e17665d2dcf582ef1e70cbec098c1274459bd57e8dc7279cb9f4b5"
            and python_executable_size_bytes == 274_712
            and python_executable_sha256
            == "21bb438c0d4a6f1f164b9a646f6ee000340185e5871180aec06db8d3f07c0082"
            and wheel_size_bytes == 12_237
            and wheel_sha256
            == "9ffb332f2f0c347cea7e7039f1e938b2aeec4a18f76e1a6879ade97749d7d98e"
            and processor_architecture == "AMD64"
            and fmi_two_size_bytes == 1_383_924
            and fmi_two_sha256
            == "76d1b0588be8865c12581977b01c5f1946e2ac94dd00f3679409e893fb87ad6a"
            and fmi_three_size_bytes == 255_474
            and fmi_three_sha256
            == "cbb038007286be266707fb919ed4614ea3c5eba3c18941e3d50482a2b8e467c9"
            and float(process_timeout_seconds) == 120.0
            and stream_limit_bytes == 1_048_576
        )
        if values_are_valid:
            pass
        else:
            raise ValueError("FMUGym comparison configuration is invalid")
        self.output_directory: Path = output_directory
        self.source_branch: str = source_branch
        self.source_revision: str = source_revision
        self.source_tree_sha256: str = source_tree_sha256
        self.runtime_root: Path = runtime_root
        self.runtime_entry_count: int = runtime_entry_count
        self.runtime_regular_bytes: int = runtime_regular_bytes
        self.runtime_tree_sha256: str = runtime_tree_sha256
        self.python_executable_path: Path = runtime_root / "Scripts" / "python.exe"
        self.python_executable_size_bytes: int = python_executable_size_bytes
        self.python_executable_sha256: str = python_executable_sha256
        self.wheel_path: Path = wheel_path
        self.wheel_size_bytes: int = wheel_size_bytes
        self.wheel_sha256: str = wheel_sha256
        self.system_root_path: Path = system_root_path
        self.processor_architecture: str = processor_architecture
        self.fmi_two_path: Path = fmi_two_path
        self.fmi_two_size_bytes: int = fmi_two_size_bytes
        self.fmi_two_sha256: str = fmi_two_sha256
        self.fmi_three_path: Path = fmi_three_path
        self.fmi_three_size_bytes: int = fmi_three_size_bytes
        self.fmi_three_sha256: str = fmi_three_sha256
        self.worker_path: Path = worker_path
        self.worker_size_bytes: int = worker_size_bytes
        self.worker_sha256: str = worker_sha256
        self.process_timeout_seconds: float = process_timeout_seconds
        self.stream_limit_bytes: int = stream_limit_bytes


class FmugymProcessResult:
    """Retain bounded child-process evidence."""

    __slots__ = (
        "arguments", "return_code", "elapsed_seconds", "stdout_size_bytes",
        "stdout_sha256", "stderr_size_bytes", "stderr_sha256",
    )

    def __init__(
        self,
        arguments: tuple[str, ...],
        return_code: int,
        elapsed_seconds: float,
        stdout_size_bytes: int,
        stdout_sha256: str,
        stderr_size_bytes: int,
        stderr_sha256: str,
    ) -> None:
        """Store one completed process record.

        :param arguments: Exact argument vector without a shell.
        :param return_code: Child process exit status.
        :param elapsed_seconds: Monotonic elapsed execution time.
        :param stdout_size_bytes: Retained standard-output size.
        :param stdout_sha256: Retained standard-output digest.
        :param stderr_size_bytes: Retained standard-error size.
        :param stderr_sha256: Retained standard-error digest.
        :return: None.
        """

        self.arguments: tuple[str, ...] = arguments
        self.return_code: int = return_code
        self.elapsed_seconds: float = elapsed_seconds
        self.stdout_size_bytes: int = stdout_size_bytes
        self.stdout_sha256: str = stdout_sha256
        self.stderr_size_bytes: int = stderr_size_bytes
        self.stderr_sha256: str = stderr_sha256


class FmugymTrace:
    """Own one parsed fixed-size comparison trace."""

    __slots__ = ("time", "action", "outputs", "reward", "output_names")

    def __init__(
        self,
        time: np.ndarray,
        action: np.ndarray,
        outputs: np.ndarray,
        reward: np.ndarray,
        output_names: tuple[str, ...],
    ) -> None:
        """Store immutable-shape numerical columns.

        :param time: Actual FMI communication times.
        :param action: Interval action values.
        :param outputs: Ordered output matrix.
        :param reward: Diagnostic reward vector.
        :param output_names: Semantic column order.
        :return: None.
        """

        self.time: np.ndarray = time
        self.action: np.ndarray = action
        self.outputs: np.ndarray = outputs
        self.reward: np.ndarray = reward
        self.output_names: tuple[str, ...] = output_names


class FmugymWorkerResult:
    """Own strict lifecycle metadata from one isolated worker."""

    __slots__ = (
        "engine", "case_id", "python_version", "fmi_version", "row_count",
        "output_names", "reset_observation", "horizon_terminated",
        "horizon_truncated", "horizon_time",
    )

    def __init__(
        self,
        engine: str,
        case_id: str,
        python_version: str,
        fmi_version: str,
        row_count: int,
        output_names: tuple[str, ...],
        reset_observation: np.ndarray,
        horizon_terminated: np.ndarray,
        horizon_truncated: np.ndarray,
        horizon_time: np.ndarray,
    ) -> None:
        """Store validated worker metadata.

        :param engine: Worker engine identifier.
        :param case_id: Fixed benchmark case identifier.
        :param python_version: Isolated runtime Python version.
        :param fmi_version: FMU standard version.
        :param row_count: Number of retained trace rows.
        :param output_names: Ordered semantic outputs.
        :param reset_observation: Observation returned by reset.
        :param horizon_terminated: Post-horizon termination flags.
        :param horizon_truncated: Post-horizon truncation flags.
        :param horizon_time: FMUGym times after horizon probes.
        :return: None.
        """

        self.engine: str = engine
        self.case_id: str = case_id
        self.python_version: str = python_version
        self.fmi_version: str = fmi_version
        self.row_count: int = row_count
        self.output_names: tuple[str, ...] = output_names
        self.reset_observation: np.ndarray = reset_observation
        self.horizon_terminated: np.ndarray = horizon_terminated
        self.horizon_truncated: np.ndarray = horizon_truncated
        self.horizon_time: np.ndarray = horizon_time


class FmugymCellResult:
    """Own one evaluated wrapper-to-backend cell."""

    __slots__ = (
        "case_id", "fmi_version", "status", "fmugym_trace", "fmpy_trace",
        "fmugym_worker", "fmpy_worker", "fmugym_process", "fmpy_process",
        "maximum_native_error", "maximum_lattice_drift_seconds",
        "projection_mismatch_count", "event_rows",
    )

    def __init__(
        self,
        case_id: str,
        fmi_version: str,
        status: FmugymCellStatus,
        fmugym_trace: FmugymTrace,
        fmpy_trace: FmugymTrace,
        fmugym_worker: FmugymWorkerResult,
        fmpy_worker: FmugymWorkerResult,
        fmugym_process: FmugymProcessResult,
        fmpy_process: FmugymProcessResult,
        maximum_native_error: float,
        maximum_lattice_drift_seconds: float,
        projection_mismatch_count: int,
        event_rows: np.ndarray,
    ) -> None:
        """Store a complete numerical and lifecycle verdict.

        :param case_id: Fixed benchmark case identifier.
        :param fmi_version: FMI standard version exercised.
        :param status: Numerical cell status.
        :param fmugym_trace: Wrapper trace.
        :param fmpy_trace: Direct backend trace.
        :param fmugym_worker: Wrapper lifecycle metadata.
        :param fmpy_worker: Direct backend metadata.
        :param fmugym_process: Wrapper process evidence.
        :param fmpy_process: Direct backend process evidence.
        :param maximum_native_error: Maximum wrapper-to-native value error.
        :param maximum_lattice_drift_seconds: Maximum ideal-time deviation.
        :param projection_mismatch_count: Exact Float32 projection mismatches.
        :param event_rows: Detected discrete-event row indices.
        :return: None.
        """

        self.case_id: str = case_id
        self.fmi_version: str = fmi_version
        self.status: FmugymCellStatus = status
        self.fmugym_trace: FmugymTrace = fmugym_trace
        self.fmpy_trace: FmugymTrace = fmpy_trace
        self.fmugym_worker: FmugymWorkerResult = fmugym_worker
        self.fmpy_worker: FmugymWorkerResult = fmpy_worker
        self.fmugym_process: FmugymProcessResult = fmugym_process
        self.fmpy_process: FmugymProcessResult = fmpy_process
        self.maximum_native_error: float = maximum_native_error
        self.maximum_lattice_drift_seconds: float = maximum_lattice_drift_seconds
        self.projection_mismatch_count: int = projection_mismatch_count
        self.event_rows: np.ndarray = event_rows


def _validate_fmugym_config(
    config: FmugymComparisonConfig,
) -> tuple[bytes, bytes, bytes]:
    """Authenticate the closed runtime, Python, wheel, worker and two FMUs.

    :param config: Closed comparison configuration.
    :return: Worker, FMI 2 FMU and FMI 3 FMU bytes.
    """

    runtime_identity: tuple[int, int, str] = read_regular_tree_identity(
        config.runtime_root
    )
    if runtime_identity == (
        config.runtime_entry_count,
        config.runtime_regular_bytes,
        config.runtime_tree_sha256,
    ):
        pass
    else:
        raise ValueError("FMUGym runtime identity changed")
    canonical_runtime: Path = config.runtime_root.resolve(strict=True)
    canonical_python: Path = config.python_executable_path.resolve(strict=True)
    try:
        canonical_python.relative_to(canonical_runtime)
    except ValueError as error:
        raise ValueError("FMUGym Python is outside its authenticated runtime") from error
    verify_regular_file_identity(
        canonical_python,
        config.python_executable_size_bytes,
        config.python_executable_sha256,
    )
    verify_regular_file_identity(
        config.wheel_path, config.wheel_size_bytes, config.wheel_sha256
    )
    worker_bytes: bytes = verify_regular_file_identity(
        config.worker_path, config.worker_size_bytes, config.worker_sha256
    )
    fmi_two_bytes: bytes = verify_regular_file_identity(
        config.fmi_two_path, config.fmi_two_size_bytes, config.fmi_two_sha256
    )
    fmi_three_bytes: bytes = verify_regular_file_identity(
        config.fmi_three_path,
        config.fmi_three_size_bytes,
        config.fmi_three_sha256,
    )
    return worker_bytes, fmi_two_bytes, fmi_three_bytes


def _run_fmugym_worker(
    config: FmugymComparisonConfig,
    arguments: tuple[str, ...],
    environment: dict[str, str],
    working_directory: Path,
    stdout_path: Path,
    stderr_path: Path,
) -> FmugymProcessResult:
    """Run one isolated worker without a shell and with bounded streams.

    :param config: Process deadline and stream bounds.
    :param arguments: Exact process argument vector.
    :param environment: Closed four-key worker environment.
    :param working_directory: Private per-process directory.
    :param stdout_path: Retained standard-output file.
    :param stderr_path: Retained standard-error file.
    :return: Completed process evidence.
    """

    arguments_are_valid: bool = bool(
        len(arguments) == 14
        and arguments[0] == str(config.python_executable_path)
        and arguments[1:3] == ("-B", "-I")
        and all(isinstance(argument, str) for argument in arguments)
    )
    environment_is_valid: bool = bool(
        set(environment.keys())
        == {"PROCESSOR_ARCHITECTURE", "SystemRoot", "TEMP", "TMP"}
        and environment["PROCESSOR_ARCHITECTURE"]
        == config.processor_architecture
        and environment["SystemRoot"] == str(config.system_root_path)
        and environment["TEMP"] == str(working_directory / "temp")
        and environment["TMP"] == str(working_directory / "temp")
    )
    paths_are_valid: bool = bool(
        working_directory.is_dir()
        and not path_is_link_or_reparse_point(working_directory)
        and stdout_path.parent == stderr_path.parent
        and not stdout_path.exists()
        and not stderr_path.exists()
    )
    if arguments_are_valid and environment_is_valid and paths_are_valid:
        pass
    else:
        raise ValueError("FMUGym worker process contract is invalid")
    stdout_file: BinaryIO = stdout_path.open("xb")
    stderr_file: BinaryIO = stderr_path.open("xb")
    process: subprocess.Popen[bytes] | None = None
    failure: str | None = None
    started_at: float = time.monotonic()
    try:
        process = subprocess.Popen(
            list(arguments), shell=False, stdin=subprocess.DEVNULL,
            stdout=stdout_file, stderr=stderr_file, cwd=working_directory,
            env=environment,
        )
        finished: bool = False
        while not finished:
            stdout_file.flush()
            stderr_file.flush()
            elapsed_seconds: float = time.monotonic() - started_at
            streams_are_bounded: bool = bool(
                stdout_path.stat().st_size <= config.stream_limit_bytes
                and stderr_path.stat().st_size <= config.stream_limit_bytes
            )
            deadline_is_valid: bool = bool(
                elapsed_seconds <= config.process_timeout_seconds
            )
            if streams_are_bounded and deadline_is_valid:
                finished = bool(process.poll() is not None)
                if finished:
                    pass
                else:
                    time.sleep(0.05)
            else:
                if streams_are_bounded:
                    failure = "FMUGym worker exceeded its deadline"
                else:
                    failure = "FMUGym worker exceeded a stream boundary"
                process.kill()
                process.wait(timeout=5.0)
                finished = True
        return_code: int = cast(int, process.returncode)
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=5.0)
        else:
            pass
        stdout_file.close()
        stderr_file.close()
    if failure is None:
        pass
    else:
        raise RuntimeError(failure)
    elapsed_seconds = time.monotonic() - started_at
    stdout_bytes: bytes = stdout_path.read_bytes()
    stderr_bytes: bytes = stderr_path.read_bytes()
    streams_are_valid: bool = bool(
        len(stdout_bytes) <= config.stream_limit_bytes
        and len(stderr_bytes) <= config.stream_limit_bytes
    )
    if streams_are_valid and return_code == 0:
        pass
    else:
        stderr_text: str = stderr_bytes.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"FMUGym worker failed with status {return_code}: {stderr_text}"
        )
    return FmugymProcessResult(
        arguments=arguments,
        return_code=return_code,
        elapsed_seconds=elapsed_seconds,
        stdout_size_bytes=len(stdout_bytes),
        stdout_sha256=hashlib.sha256(stdout_bytes).hexdigest(),
        stderr_size_bytes=len(stderr_bytes),
        stderr_sha256=hashlib.sha256(stderr_bytes).hexdigest(),
    )


def _read_fmugym_worker_result(result_path: Path) -> FmugymWorkerResult:
    """Parse one worker result through its closed declarative schema.

    :param result_path: Worker JSON result path.
    :return: Strictly typed lifecycle metadata.
    """

    path_is_valid: bool = bool(
        result_path.is_file()
        and not path_is_link_or_reparse_point(result_path)
        and result_path.stat().st_size <= 65_536
    )
    if path_is_valid:
        pass
    else:
        raise ValueError("FMUGym worker result path is unsafe")
    parsed_value: object = json.loads(result_path.read_text(encoding="utf-8"))
    if isinstance(parsed_value, dict):
        result: dict[str, object] = cast(dict[str, object], parsed_value)
    else:
        raise ValueError("FMUGym worker result is not an object")
    expected_keys: set[str] = {
        "schema", "status", "engine", "case", "python_version", "packages",
        "fmi_version", "start_time", "stop_time", "step_size", "row_count",
        "input_name", "output_names", "reset_observation", "horizon",
    }
    if set(result.keys()) == expected_keys:
        pass
    else:
        raise ValueError("FMUGym worker result keys changed")
    packages_value: object = result["packages"]
    horizon_value: object = result["horizon"]
    output_names_value: object = result["output_names"]
    reset_value: object = result["reset_observation"]
    engine_value: object = result["engine"]
    if engine_value == "fmugym":
        horizon_is_valid: bool = bool(
            isinstance(horizon_value, dict)
            and set(horizon_value.keys())
            == {"terminated", "truncated", "time_after_step"}
        )
    else:
        if engine_value == "fmpy":
            horizon_is_valid = bool(horizon_value is None)
        else:
            horizon_is_valid = False
    content_is_valid: bool = bool(
        result["schema"] == "veragrid.fmugym-worker/1"
        and result["status"] == "PASS"
        and packages_value
        == {
            "fmugym": "0.2.0", "fmpy": "0.3.31",
            "gymnasium": "0.29.1", "matplotlib": "3.11.1",
            "numpy": "2.4.6",
        }
        and isinstance(output_names_value, list)
        and all(isinstance(name, str) for name in output_names_value)
        and isinstance(reset_value, list)
        and all(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            for value in reset_value
        )
        and horizon_is_valid
    )
    if content_is_valid:
        pass
    else:
        raise ValueError("FMUGym worker result content changed")
    case_value: object = result["case"]
    start_time_value: object = result["start_time"]
    stop_time_value: object = result["stop_time"]
    step_size_value: object = result["step_size"]
    input_name_value: object = result["input_name"]
    fixed_values_are_typed: bool = bool(
        isinstance(case_value, str)
        and isinstance(start_time_value, (int, float))
        and not isinstance(start_time_value, bool)
        and isinstance(stop_time_value, (int, float))
        and not isinstance(stop_time_value, bool)
        and isinstance(step_size_value, (int, float))
        and not isinstance(step_size_value, bool)
        and isinstance(input_name_value, str)
    )
    if fixed_values_are_typed:
        pass
    else:
        raise ValueError("FMUGym worker fixed metadata has invalid types")
    if case_value == "fmi2-smib":
        fixed_metadata_is_valid: bool = bool(
            result["fmi_version"] == "2.0"
            and float(start_time_value) == 0.0
            and float(stop_time_value) == 4.0
            and float(step_size_value) == 0.002
            and result["row_count"] == 2_001
            and input_name_value == "MECH_CONTROL"
            and output_names_value == ["ANGLE", "SPEED", "PELEC", "X_EFFECTIVE"]
        )
    else:
        if case_value == "fmi3-feedthrough":
            fixed_metadata_is_valid = bool(
                result["fmi_version"] == "3.0"
                and float(start_time_value) == 0.0
                and float(stop_time_value) == 2.0
                and float(step_size_value) == 0.01
                and result["row_count"] == 201
                and input_name_value == "Float64_continuous_input"
                and output_names_value == ["Float64_continuous_output"]
            )
        else:
            fixed_metadata_is_valid = False
    if fixed_metadata_is_valid:
        pass
    else:
        raise ValueError("FMUGym worker fixed metadata changed")
    if engine_value == "fmugym":
        horizon: dict[str, object] = cast(dict[str, object], horizon_value)
        terminated_value: object = horizon["terminated"]
        truncated_value: object = horizon["truncated"]
        horizon_time_value: object = horizon["time_after_step"]
    else:
        terminated_value = list()
        truncated_value = list()
        horizon_time_value = list()
    arrays_are_valid: bool = bool(
        isinstance(terminated_value, list)
        and all(isinstance(value, bool) for value in terminated_value)
        and isinstance(truncated_value, list)
        and all(isinstance(value, bool) for value in truncated_value)
        and isinstance(horizon_time_value, list)
        and all(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            for value in horizon_time_value
        )
        and isinstance(result["row_count"], int)
        and not isinstance(result["row_count"], bool)
        and isinstance(result["engine"], str)
        and isinstance(result["case"], str)
        and isinstance(result["python_version"], str)
        and isinstance(result["fmi_version"], str)
        and np.all(np.isfinite(np.asarray(reset_value, dtype=np.float64)))
        and np.all(np.isfinite(np.asarray(horizon_time_value, dtype=np.float64)))
    )
    if arrays_are_valid:
        pass
    else:
        raise ValueError("FMUGym worker result arrays are invalid")
    return FmugymWorkerResult(
        engine=cast(str, result["engine"]),
        case_id=cast(str, result["case"]),
        python_version=cast(str, result["python_version"]),
        fmi_version=cast(str, result["fmi_version"]),
        row_count=cast(int, result["row_count"]),
        output_names=tuple(cast(list[str], output_names_value)),
        reset_observation=np.asarray(reset_value, dtype=np.float64),
        horizon_terminated=np.asarray(terminated_value, dtype=np.bool_),
        horizon_truncated=np.asarray(truncated_value, dtype=np.bool_),
        horizon_time=np.asarray(horizon_time_value, dtype=np.float64),
    )


def _read_fmugym_trace(
    trace_path: Path,
    output_names: tuple[str, ...],
    expected_rows: int,
) -> FmugymTrace:
    """Read one bounded trace with exact columns and row count.

    :param trace_path: Worker CSV trace path.
    :param output_names: Required semantic output columns.
    :param expected_rows: Required row count.
    :return: Parsed finite numerical trace.
    """

    path_is_valid: bool = bool(
        trace_path.is_file()
        and not path_is_link_or_reparse_point(trace_path)
        and trace_path.stat().st_size <= 2_000_000
        and expected_rows > 0
    )
    if path_is_valid:
        pass
    else:
        raise ValueError("FMUGym trace path is unsafe")
    trace_file: TextIO = trace_path.open("r", encoding="utf-8", newline="")
    try:
        reader: csv.reader = csv.reader(trace_file)
        rows: list[list[str]] = list(reader)
    finally:
        trace_file.close()
    expected_header: list[str] = ["time", "action"]
    expected_header.extend(output_names)
    expected_header.append("reward")
    if len(rows) == expected_rows + 1 and rows[0] == expected_header:
        pass
    else:
        raise ValueError("FMUGym trace shape or columns changed")
    time_values: np.ndarray = np.empty(expected_rows, dtype=np.float64)
    action_values: np.ndarray = np.empty(expected_rows, dtype=np.float64)
    output_values: np.ndarray = np.empty(
        (expected_rows, len(output_names)), dtype=np.float64
    )
    reward_values: np.ndarray = np.empty(expected_rows, dtype=np.float64)
    for row_index in range(expected_rows):
        row: list[str] = rows[row_index + 1]
        if len(row) == len(expected_header):
            pass
        else:
            raise ValueError("FMUGym trace row width changed")
        time_values[row_index] = float(row[0])
        action_values[row_index] = float(row[1])
        for output_index in range(len(output_names)):
            output_values[row_index, output_index] = float(row[output_index + 2])
        reward_values[row_index] = float(row[-1])
    values_are_finite: bool = bool(
        np.all(np.isfinite(time_values))
        and np.all(np.isfinite(action_values))
        and np.all(np.isfinite(output_values))
        and np.all(np.isfinite(reward_values))
    )
    if values_are_finite:
        pass
    else:
        raise ValueError("FMUGym trace contains non-finite data")
    return FmugymTrace(
        time=time_values, action=action_values, outputs=output_values,
        reward=reward_values, output_names=output_names,
    )


def _evaluate_fmugym_cell(
    case_id: str,
    fmugym_trace: FmugymTrace,
    fmpy_trace: FmugymTrace,
    fmugym_worker: FmugymWorkerResult,
    fmpy_worker: FmugymWorkerResult,
    fmugym_process: FmugymProcessResult,
    fmpy_process: FmugymProcessResult,
) -> FmugymCellResult:
    """Evaluate one wrapper trace against the direct FMPy oracle.

    :param case_id: Fixed benchmark case identifier.
    :param fmugym_trace: FMUGym trace.
    :param fmpy_trace: Direct FMPy trace on the same executed lattice.
    :param fmugym_worker: FMUGym lifecycle metadata.
    :param fmpy_worker: FMPy lifecycle metadata.
    :param fmugym_process: FMUGym process evidence.
    :param fmpy_process: FMPy process evidence.
    :return: Complete cell verdict and metrics.
    """

    if case_id == "fmi2-smib":
        expected_rows: int = 2_001
        step_size: float = 0.002
        fmi_version: str = "2.0"
        expected_output_names: tuple[str, ...] = (
            "ANGLE", "SPEED", "PELEC", "X_EFFECTIVE",
        )
    else:
        if case_id == "fmi3-feedthrough":
            expected_rows = 201
            step_size = 0.01
            fmi_version = "3.0"
            expected_output_names = ("Float64_continuous_output",)
        else:
            raise ValueError("Unknown FMUGym comparison case")
    shapes_match: bool = bool(
        fmugym_worker.row_count == expected_rows
        and fmpy_worker.row_count == expected_rows
        and fmugym_trace.time.shape == (expected_rows,)
        and fmpy_trace.time.shape == (expected_rows,)
        and fmugym_trace.outputs.shape == fmpy_trace.outputs.shape
        and fmugym_worker.output_names == fmpy_worker.output_names
        and fmugym_worker.output_names == expected_output_names
        and fmugym_worker.engine == "fmugym"
        and fmpy_worker.engine == "fmpy"
        and fmugym_worker.case_id == case_id
        and fmpy_worker.case_id == case_id
        and fmugym_worker.fmi_version == fmi_version
        and fmpy_worker.fmi_version == fmi_version
        and fmugym_worker.python_version == "3.11.9"
        and fmpy_worker.python_version == "3.11.9"
    )
    if shapes_match:
        pass
    else:
        raise ValueError("FMUGym cell shape or runtime metadata changed")
    projected_values: np.ndarray = fmpy_trace.outputs.astype(
        np.float32
    ).astype(np.float64)
    projected_reset: np.ndarray = fmpy_worker.reset_observation.astype(
        np.float32
    ).astype(np.float64)
    projection_mismatch_count: int = int(
        np.count_nonzero(fmugym_trace.outputs != projected_values)
        + np.count_nonzero(fmugym_worker.reset_observation != projected_reset)
    )
    native_error: np.ndarray = np.abs(fmugym_trace.outputs - fmpy_trace.outputs)
    native_allowance: np.ndarray = (
        4.0 * np.finfo(np.float32).eps
        * np.maximum(1.0, np.abs(fmpy_trace.outputs))
    )
    maximum_native_error: float = float(np.max(native_error))
    ideal_time: np.ndarray = step_size * np.arange(expected_rows, dtype=np.float64)
    expected_time: np.ndarray = np.empty(expected_rows, dtype=np.float64)
    expected_time[0] = 0.0
    for time_index in range(1, expected_rows):
        expected_time[time_index] = expected_time[time_index - 1] + step_size
    interval_lower_time: np.ndarray = step_size * np.arange(
        expected_rows - 1, dtype=np.float64
    )
    expected_action: np.ndarray = np.empty(expected_rows, dtype=np.float64)
    if case_id == "fmi2-smib":
        interval_action: np.ndarray = np.where(
            interval_lower_time < 0.5,
            0.0,
            np.where(interval_lower_time < 2.5, 0.025, -0.01),
        ).astype(np.float32).astype(np.float64)
    else:
        interval_action = np.asarray(
            0.1 + 0.25 * np.sin(np.pi * interval_lower_time),
            dtype=np.float32,
        ).astype(np.float64)
    expected_action[0] = interval_action[0]
    expected_action[1:] = interval_action
    maximum_lattice_drift_seconds: float = float(
        np.max(np.abs(fmugym_trace.time - ideal_time))
    )
    common_values_match: bool = bool(
        np.array_equal(fmugym_trace.time, fmpy_trace.time)
        and np.array_equal(fmugym_trace.time, expected_time)
        and np.all(np.diff(fmugym_trace.time) > 0.0)
        and np.array_equal(fmugym_trace.action, fmpy_trace.action)
        and np.array_equal(fmugym_trace.action, expected_action)
        and projection_mismatch_count == 0
        and np.all(native_error <= native_allowance)
        and np.all(np.isfinite(fmugym_trace.reward))
        and np.all(np.isfinite(fmpy_trace.reward))
        and fmpy_worker.horizon_terminated.size == 0
        and fmpy_worker.horizon_truncated.size == 0
        and fmpy_worker.horizon_time.size == 0
    )
    if case_id == "fmi2-smib":
        event_rows: np.ndarray = (
            np.flatnonzero(np.diff(fmugym_trace.outputs[:, 3]) != 0.0) + 1
        )
        dynamic_is_material: bool = bool(
            np.ptp(fmugym_trace.outputs[:, 0]) > 0.1
            and np.ptp(fmugym_trace.outputs[:, 1]) > 0.001
            and np.ptp(fmugym_trace.outputs[:, 2]) > 0.1
            and np.ptp(fmugym_trace.action) > 0.02
            and np.array_equal(event_rows, np.asarray([500, 575], dtype=np.int64))
            and np.array_equal(
                fmugym_trace.outputs[[500, 501, 575, 576], 3],
                np.asarray([1.2, 1.2, 0.6, 0.6], dtype=np.float32).astype(
                    np.float64
                ),
            )
        )
        horizon_is_expected: bool = bool(
            np.array_equal(
                fmugym_worker.horizon_terminated,
                np.asarray([False, True], dtype=np.bool_),
            )
            and np.array_equal(
                fmugym_worker.horizon_truncated,
                np.asarray([False, False], dtype=np.bool_),
            )
            and np.array_equal(
                fmugym_worker.horizon_time,
                np.asarray([expected_time[-1] + step_size, step_size]),
            )
        )
    else:
        event_rows = np.empty(0, dtype=np.int64)
        expected_output: np.ndarray = np.empty(expected_rows, dtype=np.float64)
        expected_output[0] = 0.0
        expected_output[1:] = expected_action[1:]
        dynamic_is_material = bool(
            np.max(np.abs(fmugym_trace.action)) > 0.2
            and np.array_equal(fmugym_trace.outputs[:, 0], expected_output)
        )
        horizon_is_expected = bool(
            np.array_equal(
                fmugym_worker.horizon_terminated,
                np.asarray([True, False], dtype=np.bool_),
            )
            and np.array_equal(
                fmugym_worker.horizon_truncated,
                np.asarray([False, False], dtype=np.bool_),
            )
            and np.array_equal(
                fmugym_worker.horizon_time,
                np.asarray([step_size, 2.0 * step_size]),
            )
        )
    if common_values_match and dynamic_is_material and horizon_is_expected:
        status: FmugymCellStatus = FmugymCellStatus.PASS
    else:
        raise ValueError("FMUGym cell failed its numerical or lifecycle oracle")
    return FmugymCellResult(
        case_id=case_id, fmi_version=fmi_version, status=status,
        fmugym_trace=fmugym_trace, fmpy_trace=fmpy_trace,
        fmugym_worker=fmugym_worker, fmpy_worker=fmpy_worker,
        fmugym_process=fmugym_process, fmpy_process=fmpy_process,
        maximum_native_error=maximum_native_error,
        maximum_lattice_drift_seconds=maximum_lattice_drift_seconds,
        projection_mismatch_count=projection_mismatch_count,
        event_rows=event_rows,
    )


def _render_fmugym_figure(
    package_root: Path,
    cells: tuple[FmugymCellResult, FmugymCellResult],
) -> dict[str, object]:
    """Render one sober four-panel scientific comparison figure.

    :param package_root: Unpublished evidence package root.
    :param cells: Ordered FMI 2 and FMI 3 comparison cells.
    :return: Declarative figure identity record.
    """

    if cells[0].case_id == "fmi2-smib" and cells[1].case_id == "fmi3-feedthrough":
        pass
    else:
        raise ValueError("FMUGym figure cells are not in canonical order")
    style: dict[str, object] = {
        "font.family": "DejaVu Sans", "font.size": 8.0,
        "axes.titlesize": 8.5, "axes.labelsize": 8.0,
        "xtick.labelsize": 7.0, "ytick.labelsize": 7.0,
        "legend.fontsize": 7.0, "axes.linewidth": 0.7,
        "lines.linewidth": 1.2, "svg.fonttype": "none",
        "svg.hashsalt": "veragrid-fmugym-comparison", "pdf.fonttype": 42,
    }
    with matplotlib.rc_context(style):
        figure: Figure = Figure(figsize=(7.2, 7.0), dpi=300)
        FigureCanvasAgg(figure)
        axes_value: object = figure.subplots(4, 1, squeeze=False)
        axes: np.ndarray = np.asarray(axes_value, dtype=object)
        fmi_two: FmugymCellResult = cells[0]
        fmi_three: FmugymCellResult = cells[1]
        panel_names: tuple[str, ...] = (
            "SMIB rotor angle", "SMIB speed", "SMIB effective reactance",
            "FMI 3 feedthrough",
        )
        y_labels: tuple[str, ...] = (
            "Angle [rad]", "Speed [p.u.]", "Reactance [p.u.]", "Signal [-]",
        )
        fmi_two_columns: tuple[int, int, int] = (0, 1, 3)
        for panel_index in range(3):
            axis: Axes = cast(Axes, axes[panel_index, 0])
            column_index: int = fmi_two_columns[panel_index]
            axis.plot(
                fmi_two.fmpy_trace.time,
                fmi_two.fmpy_trace.outputs[:, column_index],
                color="#202020", linestyle="-", label="Direct FMPy", zorder=2,
            )
            axis.plot(
                fmi_two.fmugym_trace.time,
                fmi_two.fmugym_trace.outputs[:, column_index],
                color="#3569a8", linestyle="--", label="FMUGym 0.2.0", zorder=3,
            )
            for marker_time in (0.5, 1.001, 1.151, 2.5):
                if marker_time in (1.001, 1.151):
                    marker_style: str = ":"
                else:
                    marker_style = "-."
                axis.axvline(
                    marker_time, color="#777777", linestyle=marker_style,
                    linewidth=0.8, zorder=1,
                )
            axis.set_title(panel_names[panel_index], loc="left")
            axis.set_ylabel(y_labels[panel_index])
            axis.tick_params(direction="in")
            axis.grid(True, color="#d9d9d9", linewidth=0.5)
        final_axis: Axes = cast(Axes, axes[3, 0])
        final_axis.plot(
            fmi_three.fmugym_trace.time, fmi_three.fmugym_trace.action,
            color="#9c5b25", linestyle=":", label="Action", zorder=1,
        )
        final_axis.plot(
            fmi_three.fmpy_trace.time, fmi_three.fmpy_trace.outputs[:, 0],
            color="#202020", linestyle="-", label="Direct FMPy", zorder=2,
        )
        final_axis.plot(
            fmi_three.fmugym_trace.time, fmi_three.fmugym_trace.outputs[:, 0],
            color="#3569a8", linestyle="--", label="FMUGym 0.2.0", zorder=3,
        )
        final_axis.set_title(panel_names[3], loc="left")
        final_axis.set_ylabel(y_labels[3])
        final_axis.set_xlabel("Time [s]")
        final_axis.tick_params(direction="in")
        final_axis.grid(True, color="#d9d9d9", linewidth=0.5)
        cast(Axes, axes[0, 0]).legend(loc="best", frameon=False)
        final_axis.legend(loc="best", frameon=False, ncol=3)
        figure.suptitle(
            "FMUGym wrapper interoperability against direct FMPy", fontsize=10.0
        )
        figure.subplots_adjust(
            left=0.12, right=0.98, bottom=0.08, top=0.93, hspace=0.38
        )
        figures_directory: Path = package_root / "figures"
        figures_directory.mkdir()
        png_path: Path = figures_directory / "fmugym-interoperability.png"
        svg_path: Path = figures_directory / "fmugym-interoperability.svg"
        pdf_path: Path = figures_directory / "fmugym-interoperability.pdf"
        png_metadata: dict[str, str] = {
            "Software": "VeraGrid FMUGym FMI comparison"
        }
        svg_metadata: dict[str, str] = {
            "Creator": "VeraGrid FMUGym FMI comparison",
            "Date": "1970-01-01T00:00:00Z",
        }
        fixed_pdf_time: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)
        pdf_metadata: dict[str, object] = {
            "Creator": "VeraGrid FMUGym FMI comparison",
            "CreationDate": fixed_pdf_time,
            "ModDate": fixed_pdf_time,
        }
        figure.savefig(png_path, dpi=300, metadata=png_metadata)
        figure.savefig(svg_path, metadata=svg_metadata)
        figure.savefig(pdf_path, metadata=pdf_metadata)
        figure.clear()
    return {
        "title": "FMUGym wrapper interoperability against direct FMPy",
        "size_inches": [7.2, 7.0], "png_pixels": [2160, 2100],
        "files": [
            "figures/fmugym-interoperability.png",
            "figures/fmugym-interoperability.svg",
            "figures/fmugym-interoperability.pdf",
        ],
        "event_markers_seconds": [0.5, 1.001, 1.151, 2.5],
    }


def _write_fmugym_manifest(
    config: FmugymComparisonConfig,
    cells: tuple[FmugymCellResult, FmugymCellResult],
    figure: dict[str, object],
    package_root: Path,
) -> Path:
    """Write the closed package manifest and bind every other file.

    :param config: Authenticated comparison configuration.
    :param cells: Ordered evaluated comparison cells.
    :param figure: Figure contract and file set.
    :param package_root: Unpublished evidence package root.
    :return: New manifest path.
    """

    cell_records: list[dict[str, object]] = [dict(), dict()]
    for cell_index in range(2):
        cell: FmugymCellResult = cells[cell_index]
        native_error: np.ndarray = np.abs(
            cell.fmugym_trace.outputs - cell.fmpy_trace.outputs
        )
        if cell_index == 0:
            material_departures: dict[str, float] = {
                "angle_rad": float(np.ptp(cell.fmugym_trace.outputs[:, 0])),
                "speed_pu": float(np.ptp(cell.fmugym_trace.outputs[:, 1])),
                "electrical_power_pu": float(
                    np.ptp(cell.fmugym_trace.outputs[:, 2])
                ),
                "action_pu": float(np.ptp(cell.fmugym_trace.action)),
            }
        else:
            material_departures = {
                "action_absolute_maximum": float(
                    np.max(np.abs(cell.fmugym_trace.action))
                )
            }
        cell_records[cell_index] = {
            "cell_index": cell_index, "case": cell.case_id,
            "fmi_version": cell.fmi_version, "interface": "Co-Simulation",
            "numerical_status": cell.status.value,
            "row_count": cell.fmugym_worker.row_count,
            "output_names": list(cell.fmugym_worker.output_names),
            "maximum_native_error": cell.maximum_native_error,
            "rms_native_error": float(np.sqrt(np.mean(native_error * native_error))),
            "maximum_lattice_drift_seconds": cell.maximum_lattice_drift_seconds,
            "float32_projection_mismatch_count": cell.projection_mismatch_count,
            "event_rows": cell.event_rows.tolist(),
            "material_departures": material_departures,
            "reset_observation": cell.fmugym_worker.reset_observation.tolist(),
            "horizon": {
                "terminated": cell.fmugym_worker.horizon_terminated.tolist(),
                "truncated": cell.fmugym_worker.horizon_truncated.tolist(),
                "time_after_step": cell.fmugym_worker.horizon_time.tolist(),
            },
            "processes": {
                "fmugym": {
                    "return_code": cell.fmugym_process.return_code,
                    "elapsed_seconds": cell.fmugym_process.elapsed_seconds,
                    "stdout_size_bytes": cell.fmugym_process.stdout_size_bytes,
                    "stdout_sha256": cell.fmugym_process.stdout_sha256,
                    "stderr_size_bytes": cell.fmugym_process.stderr_size_bytes,
                    "stderr_sha256": cell.fmugym_process.stderr_sha256,
                },
                "fmpy": {
                    "return_code": cell.fmpy_process.return_code,
                    "elapsed_seconds": cell.fmpy_process.elapsed_seconds,
                    "stdout_size_bytes": cell.fmpy_process.stdout_size_bytes,
                    "stdout_sha256": cell.fmpy_process.stdout_sha256,
                    "stderr_size_bytes": cell.fmpy_process.stderr_size_bytes,
                    "stderr_sha256": cell.fmpy_process.stderr_sha256,
                },
            },
        }
    portable_names: list[str] = list()
    paths_by_name: dict[str, Path] = dict()
    for discovered_path in package_root.rglob("*"):
        if path_is_link_or_reparse_point(discovered_path):
            raise ValueError("FMUGym package contains a link or reparse point")
        else:
            if discovered_path.is_file():
                portable_name: str = discovered_path.relative_to(
                    package_root
                ).as_posix()
                portable_names.append(portable_name)
                paths_by_name[portable_name] = discovered_path
            else:
                if discovered_path.is_dir():
                    pass
                else:
                    raise ValueError("FMUGym package contains a special entry")
    portable_names.sort()
    if len(portable_names) == 19:
        pass
    else:
        raise ValueError("FMUGym package must contain 19 files before its manifest")
    file_records: list[dict[str, object]] = [dict()] * 19
    for file_index in range(19):
        portable_name = portable_names[file_index]
        file_bytes: bytes = paths_by_name[portable_name].read_bytes()
        file_records[file_index] = {
            "path": portable_name, "size_bytes": len(file_bytes),
            "sha256": hashlib.sha256(file_bytes).hexdigest(),
        }
    manifest: dict[str, object] = {
        "schema": "veragrid.fmi-fmugym-comparison/1",
        "status": FmugymCellStatus.COMPLETED_WITH_FINDINGS.value,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "branch": config.source_branch, "revision": config.source_revision,
            "tree_sha256": config.source_tree_sha256,
        },
        "runtime": {
            "python": "3.11.9", "fmugym": "0.2.0", "fmpy": "0.3.31",
            "gymnasium": "0.29.1", "matplotlib": "3.11.1", "numpy": "2.4.6",
            "root": str(config.runtime_root),
            "runtime_entry_count": config.runtime_entry_count,
            "runtime_regular_bytes": config.runtime_regular_bytes,
            "runtime_tree_sha256": config.runtime_tree_sha256,
            "python_path": str(config.python_executable_path),
            "python_size_bytes": config.python_executable_size_bytes,
            "python_sha256": config.python_executable_sha256,
            "wheel_path": str(config.wheel_path),
            "wheel_size_bytes": config.wheel_size_bytes,
            "wheel_sha256": config.wheel_sha256, "platform": "Windows AMD64",
        },
        "inputs": {
            "fmi2_smib": {
                "path": str(config.fmi_two_path),
                "size_bytes": config.fmi_two_size_bytes,
                "sha256": config.fmi_two_sha256,
            },
            "fmi3_feedthrough": {
                "path": str(config.fmi_three_path),
                "size_bytes": config.fmi_three_size_bytes,
                "sha256": config.fmi_three_sha256,
            },
        },
        "execution": {
            "fresh_process_count": 4, "python_flags": ["-B", "-I"],
            "environment_keys": [
                "PROCESSOR_ARCHITECTURE", "SystemRoot", "TEMP", "TMP"
            ],
            "timeout_seconds": config.process_timeout_seconds,
            "stream_limit_bytes": config.stream_limit_bytes,
        },
        "cells": cell_records,
        "comparison": {
            "oracle": "exact float32 projection of direct FMPy",
            "native_error_allowance": (
                "4*eps_float32*max(1,abs(direct_fmpy_value))"
            ),
            "claim": (
                "Windows AMD64 evidence that FMUGym 0.2.0 interoperates as an "
                "FMPy-backed FMI 2 and FMI 3 Co-Simulation wrapper. This is not "
                "an independent solver, certification, or multiplatform claim."
            ),
        },
        "findings": [
            {
                "kind": FmugymFindingKind.TIME_HORIZON_FLOAT_ACCUMULATION_RESET_AND_ADVANCE.value,
                "meaning": (
                    "FMUGym accumulates binary floating-point time, checks the "
                    "horizon before advancing, resets when it is exceeded, and "
                    "still advances once in the terminating call."
                ),
            }
        ],
        "figures": figure,
        "files": file_records,
    }
    manifest_path: Path = package_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    return manifest_path


def _verify_fmugym_package(
    config: FmugymComparisonConfig,
    package_root: Path,
) -> None:
    """Reopen and verify the exact closed FMUGym evidence package.

    :param config: Configuration rebinding immutable provenance.
    :param package_root: Complete staging or published package root.
    :return: None after every structural and identity check passes.
    """

    # Bind every external executable input before trusting package metadata.
    # Repeating this authentication at function exit also detects drift during
    # a standalone verification run.
    worker_before: bytes
    fmi_two_before: bytes
    fmi_three_before: bytes
    worker_before, fmi_two_before, fmi_three_before = _validate_fmugym_config(
        config
    )
    manifest_path: Path = package_root / "manifest.json"
    root_is_safe: bool = bool(
        package_root.is_dir()
        and not path_is_link_or_reparse_point(package_root)
        and manifest_path.is_file()
        and not path_is_link_or_reparse_point(manifest_path)
    )
    if root_is_safe:
        pass
    else:
        raise ValueError("FMUGym package root is unsafe or incomplete")
    parsed_value: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    if isinstance(parsed_value, dict):
        manifest: dict[str, object] = cast(dict[str, object], parsed_value)
    else:
        raise ValueError("FMUGym manifest is not an object")
    expected_keys: tuple[str, ...] = (
        "schema", "status", "generated_at_utc", "source", "runtime",
        "inputs", "execution", "cells", "comparison", "findings",
        "figures", "files",
    )
    generated_at_value: object = manifest.get("generated_at_utc", None)
    source_value: object = manifest.get("source", None)
    execution_value: object = manifest.get("execution", None)
    files_value: object = manifest.get("files", None)
    root_is_valid: bool = bool(
        tuple(manifest.keys()) == expected_keys
        and manifest["schema"] == "veragrid.fmi-fmugym-comparison/1"
        and manifest["status"] == "COMPLETED_WITH_FINDINGS"
        and isinstance(generated_at_value, str)
        and source_value
        == {
            "branch": config.source_branch,
            "revision": config.source_revision,
            "tree_sha256": config.source_tree_sha256,
        }
        and isinstance(execution_value, dict)
        and execution_value.get("fresh_process_count", None) == 4
        and isinstance(files_value, list)
        and len(files_value) == 19
    )
    if root_is_valid:
        file_records: list[object] = cast(list[object], files_value)
    else:
        raise ValueError("FMUGym manifest root differs from its closed schema")
    generated_at: datetime = datetime.fromisoformat(
        cast(str, generated_at_value)
    )
    if generated_at.tzinfo == timezone.utc:
        pass
    else:
        raise ValueError("FMUGym manifest timestamp is not explicit UTC")
    expected_runtime: dict[str, object] = {
        "python": "3.11.9", "fmugym": "0.2.0", "fmpy": "0.3.31",
        "gymnasium": "0.29.1", "matplotlib": "3.11.1", "numpy": "2.4.6",
        "root": str(config.runtime_root),
        "runtime_entry_count": config.runtime_entry_count,
        "runtime_regular_bytes": config.runtime_regular_bytes,
        "runtime_tree_sha256": config.runtime_tree_sha256,
        "python_path": str(config.python_executable_path),
        "python_size_bytes": config.python_executable_size_bytes,
        "python_sha256": config.python_executable_sha256,
        "wheel_path": str(config.wheel_path),
        "wheel_size_bytes": config.wheel_size_bytes,
        "wheel_sha256": config.wheel_sha256, "platform": "Windows AMD64",
    }
    expected_inputs: dict[str, object] = {
        "fmi2_smib": {
            "path": str(config.fmi_two_path),
            "size_bytes": config.fmi_two_size_bytes,
            "sha256": config.fmi_two_sha256,
        },
        "fmi3_feedthrough": {
            "path": str(config.fmi_three_path),
            "size_bytes": config.fmi_three_size_bytes,
            "sha256": config.fmi_three_sha256,
        },
    }
    expected_execution: dict[str, object] = {
        "fresh_process_count": 4, "python_flags": ["-B", "-I"],
        "environment_keys": [
            "PROCESSOR_ARCHITECTURE", "SystemRoot", "TEMP", "TMP"
        ],
        "timeout_seconds": config.process_timeout_seconds,
        "stream_limit_bytes": config.stream_limit_bytes,
    }
    expected_comparison: dict[str, object] = {
        "oracle": "exact float32 projection of direct FMPy",
        "native_error_allowance": (
            "4*eps_float32*max(1,abs(direct_fmpy_value))"
        ),
        "claim": (
            "Windows AMD64 evidence that FMUGym 0.2.0 interoperates as an "
            "FMPy-backed FMI 2 and FMI 3 Co-Simulation wrapper. This is not "
            "an independent solver, certification, or multiplatform claim."
        ),
    }
    expected_findings: list[dict[str, object]] = [
        {
            "kind": FmugymFindingKind.TIME_HORIZON_FLOAT_ACCUMULATION_RESET_AND_ADVANCE.value,
            "meaning": (
                "FMUGym accumulates binary floating-point time, checks the "
                "horizon before advancing, resets when it is exceeded, and "
                "still advances once in the terminating call."
            ),
        }
    ]
    expected_figure: dict[str, object] = {
        "title": "FMUGym wrapper interoperability against direct FMPy",
        "size_inches": [7.2, 7.0], "png_pixels": [2160, 2100],
        "files": [
            "figures/fmugym-interoperability.png",
            "figures/fmugym-interoperability.svg",
            "figures/fmugym-interoperability.pdf",
        ],
        "event_markers_seconds": [0.5, 1.001, 1.151, 2.5],
    }
    metadata_is_closed: bool = bool(
        manifest["runtime"] == expected_runtime
        and manifest["inputs"] == expected_inputs
        and execution_value == expected_execution
        and manifest["comparison"] == expected_comparison
        and manifest["findings"] == expected_findings
        and manifest["figures"] == expected_figure
    )
    if metadata_is_closed:
        pass
    else:
        raise ValueError("FMUGym manifest metadata changed")
    discovered_files: list[Path] = list()
    for discovered_path in package_root.rglob("*"):
        if path_is_link_or_reparse_point(discovered_path):
            raise ValueError("FMUGym package contains an indirection")
        else:
            if discovered_path.is_file():
                discovered_files.append(discovered_path)
            else:
                if discovered_path.is_dir():
                    pass
                else:
                    raise ValueError("FMUGym package contains a special entry")
    if len(discovered_files) == 20:
        pass
    else:
        raise ValueError("FMUGym package file count changed")
    recorded_paths: set[str] = set()
    for record_value in file_records:
        if isinstance(record_value, dict):
            record: dict[str, object] = cast(dict[str, object], record_value)
        else:
            raise ValueError("FMUGym file record is not an object")
        record_path_value: object = record.get("path", None)
        record_size_value: object = record.get("size_bytes", None)
        record_sha_value: object = record.get("sha256", None)
        record_is_valid: bool = bool(
            isinstance(record_path_value, str)
            and isinstance(record_size_value, int)
            and not isinstance(record_size_value, bool)
            and isinstance(record_sha_value, str)
            and re.fullmatch(r"[0-9a-f]{64}", record_sha_value) is not None
            and record_path_value not in recorded_paths
            and record_path_value != "manifest.json"
        )
        if record_is_valid:
            recorded_paths.add(cast(str, record_path_value))
        else:
            raise ValueError("FMUGym file record is invalid")
        bound_path: Path = package_root / cast(str, record_path_value)
        bound_bytes: bytes = verify_regular_file_identity(
            bound_path,
            cast(int, record_size_value),
            cast(str, record_sha_value),
        )
        if len(bound_bytes) == record_size_value:
            pass
        else:
            raise ValueError("FMUGym file identity changed during verification")
    actual_non_manifest: set[str] = set()
    for discovered_file in discovered_files:
        if discovered_file != manifest_path:
            actual_non_manifest.add(
                discovered_file.relative_to(package_root).as_posix()
            )
        else:
            pass
    if recorded_paths == actual_non_manifest:
        pass
    else:
        raise ValueError("FMUGym manifest file closure changed")
    png_path: Path = package_root / "figures" / "fmugym-interoperability.png"
    svg_path: Path = package_root / "figures" / "fmugym-interoperability.svg"
    pdf_path: Path = package_root / "figures" / "fmugym-interoperability.pdf"
    png_image: np.ndarray = np.asarray(mpimg.imread(png_path))
    svg_root: element_tree.Element = element_tree.parse(svg_path).getroot()
    svg_text: str = svg_path.read_text(encoding="utf-8")
    pdf_bytes: bytes = pdf_path.read_bytes()
    figure_geometry_is_valid: bool = bool(
        png_image.shape[0:2] == (2_100, 2_160)
        and svg_root.attrib.get("width", None) == "518.4pt"
        and svg_root.attrib.get("height", None) == "504pt"
        and svg_root.attrib.get("viewBox", None) == "0 0 518.4 504"
        and "<text" in svg_text
        and b"/MediaBox [ 0 0 518.4 504 ]" in pdf_bytes
        and b"/FontFile2" in pdf_bytes
    )
    if figure_geometry_is_valid:
        pass
    else:
        raise ValueError("FMUGym figure geometry or text contract changed")
    cells_value: object = manifest["cells"]
    if isinstance(cells_value, list) and len(cells_value) == 2:
        cell_records: list[object] = cast(list[object], cells_value)
    else:
        raise ValueError("FMUGym manifest cell matrix changed")
    case_ids: tuple[str, str] = ("fmi2-smib", "fmi3-feedthrough")
    fmi_versions: tuple[str, str] = ("2.0", "3.0")
    expected_rows: tuple[int, int] = (2_001, 201)
    expected_events: tuple[list[int], list[int]] = ([500, 575], list())
    verified_cells: list[FmugymCellResult] = [
        cast(FmugymCellResult, None), cast(FmugymCellResult, None),
    ]
    for cell_index in range(2):
        record_value: object = cell_records[cell_index]
        if isinstance(record_value, dict):
            cell_record: dict[str, object] = cast(
                dict[str, object], record_value
            )
        else:
            raise ValueError("FMUGym manifest cell is not an object")
        expected_cell_keys: set[str] = {
            "cell_index", "case", "fmi_version", "interface",
            "numerical_status", "row_count", "output_names",
            "maximum_native_error", "rms_native_error",
            "maximum_lattice_drift_seconds",
            "float32_projection_mismatch_count", "event_rows",
            "material_departures", "reset_observation", "horizon", "processes",
        }
        if cell_index == 0:
            expected_output_names: list[str] = [
                "ANGLE", "SPEED", "PELEC", "X_EFFECTIVE"
            ]
        else:
            expected_output_names = ["Float64_continuous_output"]
        fixed_cell_is_valid: bool = bool(
            set(cell_record.keys()) == expected_cell_keys
            and cell_record["cell_index"] == cell_index
            and cell_record["case"] == case_ids[cell_index]
            and cell_record["fmi_version"] == fmi_versions[cell_index]
            and cell_record["interface"] == "Co-Simulation"
            and cell_record["numerical_status"] == "PASS"
            and cell_record["row_count"] == expected_rows[cell_index]
            and cell_record["output_names"] == expected_output_names
            and cell_record["float32_projection_mismatch_count"] == 0
            and cell_record["event_rows"] == expected_events[cell_index]
        )
        if fixed_cell_is_valid:
            pass
        else:
            raise ValueError("FMUGym manifest cell declaration changed")
        wrapper_trace: FmugymTrace = _read_fmugym_trace(
            package_root / "raw" / f"fmi{cell_index + 2}-fmugym" / "trace.csv",
            (
                ("ANGLE", "SPEED", "PELEC", "X_EFFECTIVE")
                if cell_index == 0
                else ("Float64_continuous_output",)
            ),
            expected_rows[cell_index],
        )
        reference_trace: FmugymTrace = _read_fmugym_trace(
            package_root / "raw" / f"fmi{cell_index + 2}-fmpy" / "trace.csv",
            wrapper_trace.output_names,
            expected_rows[cell_index],
        )
        recomputed_error: float = float(
            np.max(np.abs(wrapper_trace.outputs - reference_trace.outputs))
        )
        error_values: np.ndarray = np.abs(
            wrapper_trace.outputs - reference_trace.outputs
        )
        recomputed_rms_error: float = float(
            np.sqrt(np.mean(error_values * error_values))
        )
        step_size: float = 0.002 if cell_index == 0 else 0.01
        ideal_time: np.ndarray = step_size * np.arange(
            expected_rows[cell_index], dtype=np.float64
        )
        recomputed_drift: float = float(
            np.max(np.abs(wrapper_trace.time - ideal_time))
        )
        numerical_metadata_matches: bool = bool(
            cell_record["maximum_native_error"] == recomputed_error
            and cell_record["rms_native_error"] == recomputed_rms_error
            and cell_record["maximum_lattice_drift_seconds"] == recomputed_drift
        )
        if numerical_metadata_matches:
            pass
        else:
            raise ValueError("FMUGym manifest numerical metrics changed")
        fmugym_worker_result: FmugymWorkerResult = _read_fmugym_worker_result(
            package_root / "raw" / f"fmi{cell_index + 2}-fmugym"
            / "result.json"
        )
        fmpy_worker_result: FmugymWorkerResult = _read_fmugym_worker_result(
            package_root / "raw" / f"fmi{cell_index + 2}-fmpy"
            / "result.json"
        )
        lifecycle_matches: bool = bool(
            cell_record["reset_observation"]
            == fmugym_worker_result.reset_observation.tolist()
            and cell_record["horizon"]
            == {
                "terminated": fmugym_worker_result.horizon_terminated.tolist(),
                "truncated": fmugym_worker_result.horizon_truncated.tolist(),
                "time_after_step": fmugym_worker_result.horizon_time.tolist(),
            }
        )
        if lifecycle_matches:
            pass
        else:
            raise ValueError("FMUGym manifest lifecycle metadata changed")
        if cell_index == 0:
            expected_departures: dict[str, float] = {
                "angle_rad": float(np.ptp(wrapper_trace.outputs[:, 0])),
                "speed_pu": float(np.ptp(wrapper_trace.outputs[:, 1])),
                "electrical_power_pu": float(
                    np.ptp(wrapper_trace.outputs[:, 2])
                ),
                "action_pu": float(np.ptp(wrapper_trace.action)),
            }
        else:
            expected_departures = {
                "action_absolute_maximum": float(
                    np.max(np.abs(wrapper_trace.action))
                )
            }
        if cell_record["material_departures"] == expected_departures:
            pass
        else:
            raise ValueError("FMUGym manifest material departures changed")
        processes_value: object = cell_record["processes"]
        if isinstance(processes_value, dict) and set(processes_value.keys()) == {
            "fmugym", "fmpy"
        }:
            processes: dict[str, object] = cast(
                dict[str, object], processes_value
            )
        else:
            raise ValueError("FMUGym manifest process matrix changed")
        process_results: list[FmugymProcessResult] = [
            cast(FmugymProcessResult, None), cast(FmugymProcessResult, None),
        ]
        for engine in ("fmugym", "fmpy"):
            process_value: object = processes[engine]
            if isinstance(process_value, dict):
                process: dict[str, object] = cast(
                    dict[str, object], process_value
                )
            else:
                raise ValueError("FMUGym process record is not an object")
            expected_process_keys: set[str] = {
                "return_code", "elapsed_seconds", "stdout_size_bytes",
                "stdout_sha256", "stderr_size_bytes", "stderr_sha256",
            }
            stdout_bytes: bytes = (
                package_root / "raw" / f"fmi{cell_index + 2}-{engine}"
                / "stdout.log"
            ).read_bytes()
            stderr_bytes: bytes = (
                package_root / "raw" / f"fmi{cell_index + 2}-{engine}"
                / "stderr.log"
            ).read_bytes()
            elapsed_value: object = process.get("elapsed_seconds", None)
            process_matches: bool = bool(
                set(process.keys()) == expected_process_keys
                and process["return_code"] == 0
                and isinstance(elapsed_value, (int, float))
                and not isinstance(elapsed_value, bool)
                and math.isfinite(float(elapsed_value))
                and float(elapsed_value) >= 0.0
                and process["stdout_size_bytes"] == len(stdout_bytes)
                and process["stdout_sha256"]
                == hashlib.sha256(stdout_bytes).hexdigest()
                and process["stderr_size_bytes"] == len(stderr_bytes)
                and process["stderr_sha256"]
                == hashlib.sha256(stderr_bytes).hexdigest()
            )
            if process_matches:
                process_index: int = 0 if engine == "fmugym" else 1
                process_results[process_index] = FmugymProcessResult(
                    arguments=tuple(),
                    return_code=cast(int, process["return_code"]),
                    elapsed_seconds=float(cast(float, elapsed_value)),
                    stdout_size_bytes=cast(int, process["stdout_size_bytes"]),
                    stdout_sha256=cast(str, process["stdout_sha256"]),
                    stderr_size_bytes=cast(int, process["stderr_size_bytes"]),
                    stderr_sha256=cast(str, process["stderr_sha256"]),
                )
            else:
                raise ValueError("FMUGym process evidence changed")
        # Reuse the generation-time oracle on artifacts reopened from disk. This
        # prevents coordinated trace, manifest and digest changes from bypassing
        # any numerical, event, action or lifecycle requirement.
        verified_cells[cell_index] = _evaluate_fmugym_cell(
            case_id=case_ids[cell_index],
            fmugym_trace=wrapper_trace,
            fmpy_trace=reference_trace,
            fmugym_worker=fmugym_worker_result,
            fmpy_worker=fmpy_worker_result,
            fmugym_process=process_results[0],
            fmpy_process=process_results[1],
        )
    # Render the authenticated traces a second time outside the package and
    # compare exact bytes. The published plots therefore remain a deterministic
    # projection of the numerical evidence rather than an unaudited attachment.
    figure_verification_root: Path = Path(
        tempfile.mkdtemp(
            prefix=".fmugym-figure-verification-", dir=package_root.parent
        )
    )
    try:
        verified_figure: dict[str, object] = _render_fmugym_figure(
            figure_verification_root,
            (verified_cells[0], verified_cells[1]),
        )
        figure_names: tuple[str, str, str] = (
            "fmugym-interoperability.png",
            "fmugym-interoperability.svg",
            "fmugym-interoperability.pdf",
        )
        figure_bytes_match: bool = bool(verified_figure == expected_figure)
        for figure_name in figure_names:
            original_figure_bytes: bytes = (
                package_root / "figures" / figure_name
            ).read_bytes()
            verified_figure_bytes: bytes = (
                figure_verification_root / "figures" / figure_name
            ).read_bytes()
            figure_bytes_match = bool(
                figure_bytes_match
                and original_figure_bytes == verified_figure_bytes
            )
        if figure_bytes_match:
            pass
        else:
            raise ValueError("FMUGym figures do not match authenticated traces")
    finally:
        shutil.rmtree(figure_verification_root)
    worker_after: bytes
    fmi_two_after: bytes
    fmi_three_after: bytes
    worker_after, fmi_two_after, fmi_three_after = _validate_fmugym_config(config)
    external_inputs_are_stable: bool = bool(
        worker_after == worker_before
        and fmi_two_after == fmi_two_before
        and fmi_three_after == fmi_three_before
    )
    if external_inputs_are_stable:
        pass
    else:
        raise ValueError("FMUGym external inputs changed during verification")


def generate_fmugym_comparison(config: FmugymComparisonConfig) -> Path:
    """Execute four fresh workers and atomically publish their evidence.

    :param config: Closed authenticated FMUGym comparison configuration.
    :return: Published manifest path after complete re-verification.
    """

    output_parent_is_valid: bool = bool(
        config.output_directory.parent.exists()
        and config.output_directory.parent.is_dir()
        and not path_is_link_or_reparse_point(config.output_directory.parent)
        and not config.output_directory.exists()
    )
    if output_parent_is_valid:
        pass
    else:
        raise ValueError("FMUGym output destination is unsafe or already exists")
    worker_bytes: bytes
    fmi_two_bytes: bytes
    fmi_three_bytes: bytes
    worker_bytes, fmi_two_bytes, fmi_three_bytes = _validate_fmugym_config(config)
    temporary_root: Path = Path(
        tempfile.mkdtemp(
            prefix=".fmugym-comparison-", dir=config.output_directory.parent
        )
    )
    published: bool = False
    try:
        package_root: Path = temporary_root / "package"
        work_root: Path = temporary_root / "work"
        package_root.mkdir()
        work_root.mkdir()
        raw_root: Path = package_root / "raw"
        raw_root.mkdir()
        case_ids: tuple[str, str] = ("fmi2-smib", "fmi3-feedthrough")
        fmu_contents: tuple[bytes, bytes] = (fmi_two_bytes, fmi_three_bytes)
        fmu_sizes: tuple[int, int] = (
            config.fmi_two_size_bytes, config.fmi_three_size_bytes,
        )
        fmu_digests: tuple[str, str] = (
            config.fmi_two_sha256, config.fmi_three_sha256,
        )
        cell_results: list[FmugymCellResult] = [
            cast(FmugymCellResult, None), cast(FmugymCellResult, None),
        ]
        for case_index in range(2):
            case_id: str = case_ids[case_index]
            worker_results: list[FmugymWorkerResult] = [
                cast(FmugymWorkerResult, None),
                cast(FmugymWorkerResult, None),
            ]
            traces: list[FmugymTrace] = [
                cast(FmugymTrace, None), cast(FmugymTrace, None),
            ]
            process_results: list[FmugymProcessResult] = [
                cast(FmugymProcessResult, None),
                cast(FmugymProcessResult, None),
            ]
            engines: tuple[str, str] = ("fmugym", "fmpy")
            for engine_index in range(2):
                engine: str = engines[engine_index]
                run_name: str = f"fmi{case_index + 2}-{engine}"
                run_root: Path = raw_root / run_name
                work_directory: Path = work_root / run_name
                run_root.mkdir()
                work_directory.mkdir()
                temp_directory: Path = work_directory / "temp"
                temp_directory.mkdir()
                staged_worker: Path = work_directory / "fmugym_worker.py"
                staged_fmu: Path = work_directory / "model.fmu"
                staged_worker.write_bytes(worker_bytes)
                staged_fmu.write_bytes(fmu_contents[case_index])
                verify_regular_file_identity(
                    staged_worker, config.worker_size_bytes, config.worker_sha256
                )
                verify_regular_file_identity(
                    staged_fmu, fmu_sizes[case_index], fmu_digests[case_index]
                )
                trace_path: Path = run_root / "trace.csv"
                result_path: Path = run_root / "result.json"
                stdout_path: Path = run_root / "stdout.log"
                stderr_path: Path = run_root / "stderr.log"
                arguments: tuple[str, ...] = (
                    str(config.python_executable_path), "-B", "-I",
                    str(staged_worker), "--engine", engine, "--case", case_id,
                    "--fmu", str(staged_fmu), "--trace", str(trace_path),
                    "--result", str(result_path),
                )
                environment: dict[str, str] = {
                    "PROCESSOR_ARCHITECTURE": config.processor_architecture,
                    "SystemRoot": str(config.system_root_path),
                    "TEMP": str(temp_directory), "TMP": str(temp_directory),
                }
                process_results[engine_index] = _run_fmugym_worker(
                    config, arguments, environment, work_directory,
                    stdout_path, stderr_path,
                )
                # Re-authenticate both executable input copies after the child
                # exits so a successful result cannot hide worker or FMU drift.
                verify_regular_file_identity(
                    staged_worker, config.worker_size_bytes, config.worker_sha256
                )
                verify_regular_file_identity(
                    staged_fmu, fmu_sizes[case_index], fmu_digests[case_index]
                )
                worker_results[engine_index] = _read_fmugym_worker_result(
                    result_path
                )
                traces[engine_index] = _read_fmugym_trace(
                    trace_path, worker_results[engine_index].output_names,
                    worker_results[engine_index].row_count,
                )
            cell_results[case_index] = _evaluate_fmugym_cell(
                case_id=case_id, fmugym_trace=traces[0], fmpy_trace=traces[1],
                fmugym_worker=worker_results[0], fmpy_worker=worker_results[1],
                fmugym_process=process_results[0], fmpy_process=process_results[1],
            )
        ordered_cells: tuple[FmugymCellResult, FmugymCellResult] = (
            cell_results[0], cell_results[1],
        )
        worker_after: bytes
        fmi_two_after: bytes
        fmi_three_after: bytes
        worker_after, fmi_two_after, fmi_three_after = _validate_fmugym_config(
            config
        )
        identities_are_stable: bool = bool(
            worker_after == worker_bytes
            and fmi_two_after == fmi_two_bytes
            and fmi_three_after == fmi_three_bytes
        )
        if identities_are_stable:
            pass
        else:
            raise ValueError("FMUGym authenticated inputs changed after execution")
        figure: dict[str, object] = _render_fmugym_figure(
            package_root, ordered_cells
        )
        manifest_path: Path = _write_fmugym_manifest(
            config, ordered_cells, figure, package_root
        )
        _verify_fmugym_package(config, package_root)
        package_root.rename(config.output_directory)
        published = True
        published_manifest: Path = config.output_directory / manifest_path.name
        _verify_fmugym_package(config, config.output_directory)
        return published_manifest
    finally:
        if temporary_root.exists():
            shutil.rmtree(temporary_root)
        else:
            pass
        if published:
            pass
        else:
            if config.output_directory.exists():
                shutil.rmtree(config.output_directory)
            else:
                pass
