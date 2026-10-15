# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Execute one isolated PathSim-FMI reference cell."""
from __future__ import annotations

import argparse
import csv
from enum import Enum
from importlib import metadata
import json
import math
from pathlib import Path
import platform
from typing import TextIO

from fmpy.fmi1 import FMICallException
import numpy as np
from pathsim import Connection, Simulation
from pathsim.blocks import Scope
from pathsim.solvers import RKBS32
from pathsim_fmi import CoSimulationFMU, ModelExchangeFMU
from pathsim_fmi.wrapper import StepResult


class PathSimWorkerInterface(str, Enum):
    """FMI interfaces executable by one PathSim worker."""

    CO_SIMULATION = "co_simulation"
    MODEL_EXCHANGE = "model_exchange"


class PathSimWorkerStatus(str, Enum):
    """Terminal outcomes emitted by one PathSim worker."""

    PASS = "PASS"
    FINDING = "FINDING"


class PathSimWorkerConfig:
    """Own the explicit inputs of one isolated PathSim execution."""

    __slots__ = (
        "fmu_path",
        "result_path",
        "trace_path",
        "interface_mode",
        "observed_variable_name",
        "start_time_seconds",
        "stop_time_seconds",
        "step_size_seconds",
    )

    def __init__(
        self,
        fmu_path: Path,
        result_path: Path,
        trace_path: Path,
        interface_mode: PathSimWorkerInterface,
        observed_variable_name: str,
        start_time_seconds: float,
        stop_time_seconds: float,
        step_size_seconds: float,
    ) -> None:
        """Validate and retain one worker request.

        :param fmu_path: Private regular FMU file used by this process.
        :param result_path: New JSON result path owned by this process.
        :param trace_path: New CSV trace path owned by this process.
        :param interface_mode: FMI interface exercised by this process.
        :param observed_variable_name: Public FMU output to record.
        :param start_time_seconds: First requested sample time.
        :param stop_time_seconds: Inclusive configured stop time.
        :param step_size_seconds: Communication and sampling interval.
        :return: None.
        """

        paths_are_valid: bool = bool(
            isinstance(fmu_path, Path)
            and isinstance(result_path, Path)
            and isinstance(trace_path, Path)
            and fmu_path.is_absolute()
            and result_path.is_absolute()
            and trace_path.is_absolute()
            and fmu_path.exists()
            and fmu_path.is_file()
            and not fmu_path.is_symlink()
            and not result_path.exists()
            and not trace_path.exists()
            and result_path.parent == trace_path.parent
            and result_path.parent.exists()
            and result_path.parent.is_dir()
            and not result_path.parent.is_symlink()
        )
        numeric_values_are_valid: bool = bool(
            isinstance(start_time_seconds, (int, float))
            and not isinstance(start_time_seconds, bool)
            and isinstance(stop_time_seconds, (int, float))
            and not isinstance(stop_time_seconds, bool)
            and isinstance(step_size_seconds, (int, float))
            and not isinstance(step_size_seconds, bool)
            and math.isfinite(float(start_time_seconds))
            and math.isfinite(float(stop_time_seconds))
            and math.isfinite(float(step_size_seconds))
            and float(stop_time_seconds) > float(start_time_seconds)
            and float(step_size_seconds) > 0.0
        )
        descriptive_values_are_valid: bool = bool(
            isinstance(interface_mode, PathSimWorkerInterface)
            and isinstance(observed_variable_name, str)
            and bool(observed_variable_name)
            and observed_variable_name.isascii()
        )
        if paths_are_valid and numeric_values_are_valid and descriptive_values_are_valid:
            pass
        else:
            raise ValueError("PathSim worker configuration is invalid")
        self.fmu_path: Path = fmu_path
        self.result_path: Path = result_path
        self.trace_path: Path = trace_path
        self.interface_mode: PathSimWorkerInterface = interface_mode
        self.observed_variable_name: str = observed_variable_name
        self.start_time_seconds: float = float(start_time_seconds)
        self.stop_time_seconds: float = float(stop_time_seconds)
        self.step_size_seconds: float = float(step_size_seconds)


class PathSimWorkerOutcome:
    """Own one successful trace or one exact external FMI finding."""

    __slots__ = (
        "status",
        "time_seconds",
        "observed_values",
        "event_times_seconds",
        "finding_kind",
        "fmi_function",
        "fmi_status",
    )

    def __init__(
        self,
        status: PathSimWorkerStatus,
        time_seconds: np.ndarray,
        observed_values: np.ndarray,
        event_times_seconds: np.ndarray,
        finding_kind: str | None,
        fmi_function: str | None,
        fmi_status: int | None,
    ) -> None:
        """Validate and retain one immutable worker outcome.

        :param status: Successful execution or preserved external finding.
        :param time_seconds: Ordered sample times for a successful execution.
        :param observed_values: Output values paired with the sample times.
        :param event_times_seconds: Publicly observed native event times.
        :param finding_kind: Stable finding identifier, when execution is unsupported.
        :param fmi_function: Failing FMI function, when reported by FMPy.
        :param fmi_status: Numeric FMI status, when reported by FMPy.
        :return: None.
        """

        arrays_are_valid: bool = bool(
            isinstance(time_seconds, np.ndarray)
            and isinstance(observed_values, np.ndarray)
            and isinstance(event_times_seconds, np.ndarray)
            and time_seconds.ndim == 1
            and observed_values.ndim == 1
            and event_times_seconds.ndim == 1
            and time_seconds.size == observed_values.size
            and np.all(np.isfinite(time_seconds))
            and np.all(np.isfinite(observed_values))
            and np.all(np.isfinite(event_times_seconds))
        )
        pass_shape_is_valid: bool = bool(
            status == PathSimWorkerStatus.PASS
            and time_seconds.size >= 2
            and finding_kind is None
            and fmi_function is None
            and fmi_status is None
        )
        finding_shape_is_valid: bool = bool(
            status == PathSimWorkerStatus.FINDING
            and time_seconds.size == 0
            and observed_values.size == 0
            and event_times_seconds.size == 0
            and finding_kind == "unsupported_scalar_output"
            and isinstance(fmi_function, str)
            and bool(fmi_function)
            and isinstance(fmi_status, int)
            and not isinstance(fmi_status, bool)
        )
        if arrays_are_valid and (pass_shape_is_valid or finding_shape_is_valid):
            pass
        else:
            raise ValueError("PathSim worker result is invalid")
        self.status: PathSimWorkerStatus = status
        self.time_seconds: np.ndarray = np.asarray(
            time_seconds,
            dtype=np.float64,
        ).copy()
        self.observed_values: np.ndarray = np.asarray(
            observed_values,
            dtype=np.float64,
        ).copy()
        self.event_times_seconds: np.ndarray = np.asarray(
            event_times_seconds,
            dtype=np.float64,
        ).copy()
        self.finding_kind: str | None = finding_kind
        self.fmi_function: str | None = fmi_function
        self.fmi_status: int | None = fmi_status


def _execute_pathsim_cs(config: PathSimWorkerConfig) -> PathSimWorkerOutcome:
    """Advance one Co-Simulation FMU on its declared communication lattice.

    :param config: Validated single-cell execution request.
    :return: Successful PathSim trace and detected state-event times.
    """

    # Constructing the public PathSim-FMI block performs the complete FMI
    # initialization and reads row zero before any communication step.
    fmu: CoSimulationFMU = CoSimulationFMU(
        fmu_path=str(config.fmu_path),
        instance_name="veragrid_pathsim_cs",
        start_values=None,
        dt=config.step_size_seconds,
    )
    output_names: tuple[str, ...] = tuple(fmu.fmu_wrapper.output_refs.keys())
    if config.observed_variable_name in output_names:
        observed_index: int = output_names.index(config.observed_variable_name)
    else:
        raise ValueError("PathSim CS output does not contain the requested variable")
    interval_count_float: float = (
        (config.stop_time_seconds - config.start_time_seconds)
        / config.step_size_seconds
    )
    interval_count: int = int(round(interval_count_float))
    if math.isclose(interval_count_float, float(interval_count), abs_tol=1.0e-12):
        pass
    else:
        raise ValueError("PathSim CS interval does not form an exact lattice")
    sample_count: int = interval_count + 1
    time_seconds: np.ndarray = np.empty(sample_count, dtype=np.float64)
    observed_values: np.ndarray = np.empty(sample_count, dtype=np.float64)
    time_seconds[0] = config.start_time_seconds
    observed_values[0] = float(
        fmu.fmu_wrapper.get_outputs_as_array()[observed_index]
    )

    # Every accepted communication point becomes exactly one retained row.
    for sample_index in range(1, sample_count):
        previous_time: float = (
            config.start_time_seconds
            + float(sample_index - 1) * config.step_size_seconds
        )
        step_result: StepResult = fmu.fmu_wrapper.do_step(
            current_time=previous_time,
            step_size=config.step_size_seconds,
        )
        if step_result.terminate_simulation:
            raise RuntimeError("PathSim CS FMU requested early termination")
        else:
            pass
        time_seconds[sample_index] = (
            config.start_time_seconds
            + float(sample_index) * config.step_size_seconds
        )
        observed_values[sample_index] = float(
            fmu.fmu_wrapper.get_outputs_as_array()[observed_index]
        )

    # BouncingBall exposes each state event as a negative-to-nonnegative
    # velocity transition on the public communication lattice.
    transition_indices: np.ndarray = np.flatnonzero(
        (observed_values[:-1] < 0.0) & (observed_values[1:] >= 0.0)
    )
    event_times_seconds: np.ndarray = time_seconds[transition_indices + 1].copy()
    return PathSimWorkerOutcome(
        PathSimWorkerStatus.PASS,
        time_seconds,
        observed_values,
        event_times_seconds,
        None,
        None,
        None,
    )


def _execute_pathsim_me(config: PathSimWorkerConfig) -> PathSimWorkerOutcome:
    """Integrate one Model Exchange FMU with the documented PathSim solver.

    :param config: Validated single-cell execution request.
    :return: Successful regular-lattice trace and native event times.
    """

    # These are the exact upstream PathSim BouncingBall settings retained by
    # the comparison contract rather than benchmark-specific tuning.
    fmu: ModelExchangeFMU = ModelExchangeFMU(
        fmu_path=str(config.fmu_path),
        instance_name="veragrid_pathsim_me",
        start_values=None,
        tolerance=1.0e-10,
        verbose=False,
    )
    output_names: tuple[str, ...] = tuple(fmu.fmu_wrapper.output_refs.keys())
    if config.observed_variable_name in output_names:
        observed_index: int = output_names.index(config.observed_variable_name)
    else:
        raise ValueError("PathSim ME output does not contain the requested variable")
    scope: Scope = Scope(
        sampling_period=config.step_size_seconds,
        t_wait=config.start_time_seconds,
        labels=[config.observed_variable_name],
    )
    connection: Connection = Connection(fmu[observed_index], scope[0])
    simulation: Simulation = Simulation(
        [fmu, scope],
        [connection],
        dt=0.01,
        dt_max=0.01,
        Solver=RKBS32,
        tolerance_lte_rel=1.0e-6,
        tolerance_lte_abs=1.0e-9,
        log=False,
    )
    duration_seconds: float = (
        config.stop_time_seconds - config.start_time_seconds
    )
    simulation.run(duration_seconds)
    recorded_time: np.ndarray | None
    recorded_data: np.ndarray | None
    recorded_time, recorded_data = scope.read()
    if isinstance(recorded_time, np.ndarray) and isinstance(recorded_data, np.ndarray):
        pass
    else:
        raise ValueError("PathSim ME scope did not produce a trace")
    time_seconds: np.ndarray = np.asarray(recorded_time, dtype=np.float64)
    if recorded_data.ndim == 2 and recorded_data.shape[0] == 1:
        observed_values: np.ndarray = np.asarray(
            recorded_data[0],
            dtype=np.float64,
        )
    else:
        raise ValueError("PathSim ME scope produced an unexpected shape")
    event_times_seconds: np.ndarray = np.asarray(
        tuple(float(event_time) for event_time in fmu.events[0]),
        dtype=np.float64,
    )
    return PathSimWorkerOutcome(
        PathSimWorkerStatus.PASS,
        time_seconds,
        observed_values,
        event_times_seconds,
        None,
        None,
        None,
    )


def _write_pathsim_trace(
    config: PathSimWorkerConfig,
    result: PathSimWorkerOutcome,
) -> None:
    """Write one successful worker trace with stable numeric tokens.

    :param config: Validated worker paths and output name.
    :param result: Successful result containing paired samples.
    :return: None.
    """

    if result.status == PathSimWorkerStatus.PASS:
        pass
    else:
        raise ValueError("A finding must not create a synthetic trace")
    trace_file: TextIO = config.trace_path.open("x", encoding="utf-8", newline="")
    try:
        writer: csv.writer = csv.writer(trace_file, lineterminator="\n")
        writer.writerow(("time", config.observed_variable_name))
        for sample_index in range(result.time_seconds.size):
            writer.writerow(
                (
                    repr(float(result.time_seconds[sample_index])),
                    repr(float(result.observed_values[sample_index])),
                )
            )
    finally:
        trace_file.close()


def _write_pathsim_result(
    config: PathSimWorkerConfig,
    result: PathSimWorkerOutcome,
) -> None:
    """Write one closed JSON description of the worker outcome.

    :param config: Validated worker destination.
    :param result: Successful execution or preserved external finding.
    :return: None.
    """

    result_value: dict[str, object] = {
        "schema": "veragrid.fmi-pathsim-worker/1",
        "status": result.status.value,
        "python_version": platform.python_version(),
        "pathsim_version": metadata.version("pathsim"),
        "pathsim_fmi_version": metadata.version("pathsim-fmi"),
        "fmpy_version": metadata.version("FMPy"),
        "sample_count": int(result.time_seconds.size),
        "event_times_seconds": [
            float(event_time) for event_time in result.event_times_seconds
        ],
        "finding_kind": result.finding_kind,
        "fmi_function": result.fmi_function,
        "fmi_status": result.fmi_status,
    }
    config.result_path.write_text(
        json.dumps(result_value, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    """Parse one explicit request, execute it and publish bounded worker output.

    :return: Zero when either a trace or a structured FMI finding was retained.
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Execute one isolated PathSim-FMI reference cell.",
    )
    parser.add_argument("--fmu", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--trace", required=True)
    parser.add_argument(
        "--interface",
        required=True,
        choices=[item.value for item in PathSimWorkerInterface],
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--start", required=True, type=float)
    parser.add_argument("--stop", required=True, type=float)
    parser.add_argument("--step", required=True, type=float)
    arguments: argparse.Namespace = parser.parse_args()
    config: PathSimWorkerConfig = PathSimWorkerConfig(
        fmu_path=Path(arguments.fmu),
        result_path=Path(arguments.result),
        trace_path=Path(arguments.trace),
        interface_mode=PathSimWorkerInterface(arguments.interface),
        observed_variable_name=arguments.output,
        start_time_seconds=arguments.start,
        stop_time_seconds=arguments.stop,
        step_size_seconds=arguments.step,
    )
    try:
        if config.interface_mode == PathSimWorkerInterface.CO_SIMULATION:
            result: PathSimWorkerOutcome = _execute_pathsim_cs(config)
        else:
            result = _execute_pathsim_me(config)
    except FMICallException as fmi_error:
        # PathSim-FMI currently requests every output through Real/Float64.
        # Preserve the native FMI function and status so the orchestrator can
        # accept only the exact known Integer/Int32 limitation.
        result = PathSimWorkerOutcome(
            PathSimWorkerStatus.FINDING,
            np.empty(0, dtype=np.float64),
            np.empty(0, dtype=np.float64),
            np.empty(0, dtype=np.float64),
            "unsupported_scalar_output",
            fmi_error.function,
            int(fmi_error.status),
        )
    if result.status == PathSimWorkerStatus.PASS:
        _write_pathsim_trace(config, result)
    else:
        pass
    _write_pathsim_result(config, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
