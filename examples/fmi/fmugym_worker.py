# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Execute one isolated FMUGym or direct-FMPy comparison cell."""
from __future__ import annotations

import argparse
import csv
from enum import Enum
from importlib.metadata import version
import json
import math
from pathlib import Path
import platform
import shutil
from typing import TextIO

from fmpy import extract, read_model_description
from fmpy.fmi2 import FMU2Slave
from fmpy.fmi3 import FMU3Slave
from fmpy.model_description import ModelDescription, ModelVariable
from fmugym import FMUGym, FMUGymConfig, VarSpace
import numpy as np


class FmugymWorkerEngine(str, Enum):
    """Execution engines supported by the isolated worker."""

    FMUGYM = "fmugym"
    FMPY = "fmpy"


class FmugymWorkerCase(str, Enum):
    """Fixed benchmark cases supported by the isolated worker."""

    FMI2_SMIB = "fmi2-smib"
    FMI3_FEEDTHROUGH = "fmi3-feedthrough"


class FmugymWorkerConfig:
    """Own the explicit immutable inputs for one worker execution."""

    __slots__ = (
        "engine",
        "case",
        "fmu_path",
        "trace_path",
        "result_path",
        "start_time",
        "stop_time",
        "step_size",
        "input_name",
        "output_names",
    )

    def __init__(
        self,
        engine: FmugymWorkerEngine,
        case: FmugymWorkerCase,
        fmu_path: Path,
        trace_path: Path,
        result_path: Path,
    ) -> None:
        """Build one closed worker configuration.

        :param engine: Wrapper or direct reference execution engine.
        :param case: Fixed FMI benchmark case.
        :param fmu_path: Authenticated FMU staged by the parent process.
        :param trace_path: Destination for the complete numerical trace.
        :param result_path: Destination for lifecycle and runtime metadata.
        :return: None.
        """

        self.engine: FmugymWorkerEngine = engine
        self.case: FmugymWorkerCase = case
        self.fmu_path: Path = fmu_path
        self.trace_path: Path = trace_path
        self.result_path: Path = result_path
        if case == FmugymWorkerCase.FMI2_SMIB:
            self.start_time: float = 0.0
            self.stop_time: float = 4.0
            self.step_size: float = 0.002
            self.input_name: str = "MECH_CONTROL"
            self.output_names: tuple[str, ...] = (
                "ANGLE",
                "SPEED",
                "PELEC",
                "X_EFFECTIVE",
            )
        else:
            self.start_time = 0.0
            self.stop_time = 2.0
            self.step_size = 0.01
            self.input_name = "Float64_continuous_input"
            self.output_names = ("Float64_continuous_output",)


class FmugymBenchmarkEnvironment(FMUGym):
    """Minimal model-specific FMUGym environment for deterministic evidence."""

    __slots__ = ()

    def _noisy_init(self) -> dict[int, float]:
        """Return the deterministic empty start-parameter mapping.

        The benchmark FMUs already own their complete initial state. Overriding
        this documented model-specific extension avoids the upstream base
        implementation reading an undefined ``init_states`` member.

        :return: Empty value-reference mapping supplied to FMUGym initialization.
        """

        initial_values: dict[int, float] = dict()
        return initial_values

    def compute_reward(
        self,
        observation: np.ndarray,
        info: dict[str, str],
    ) -> float:
        """Compute a finite diagnostic reward from the current observations.

        :param observation: Current ordered FMUGym observation vector.
        :param info: Upstream diagnostic mapping associated with the step.
        :return: Negative squared Euclidean observation norm.
        """

        reward: float = -float(np.dot(observation, observation))
        reward_is_valid: bool = bool(
            isinstance(info, dict) and math.isfinite(reward)
        )
        if reward_is_valid:
            return reward
        else:
            raise ValueError("FMUGym produced a non-finite diagnostic reward")


class FmugymWorkerTrace:
    """Retain one complete fixed-lattice worker trace and lifecycle probe."""

    __slots__ = (
        "time",
        "action",
        "outputs",
        "reward",
        "reset_observation",
        "horizon_terminated",
        "horizon_truncated",
        "horizon_time",
    )

    def __init__(
        self,
        time: np.ndarray,
        action: np.ndarray,
        outputs: np.ndarray,
        reward: np.ndarray,
        reset_observation: np.ndarray,
        horizon_terminated: np.ndarray,
        horizon_truncated: np.ndarray,
        horizon_time: np.ndarray,
    ) -> None:
        """Store one worker result without changing array sizes afterward.

        :param time: Accepted sample times.
        :param action: Action applied on the interval ending at each row.
        :param outputs: Ordered FMU output samples.
        :param reward: Diagnostic reward per accepted row.
        :param reset_observation: Observation returned by the explicit reset.
        :param horizon_terminated: Termination flags from post-trace probes.
        :param horizon_truncated: Truncation flags from post-trace probes.
        :param horizon_time: Environment time after each post-trace probe.
        :return: None.
        """

        self.time: np.ndarray = time
        self.action: np.ndarray = action
        self.outputs: np.ndarray = outputs
        self.reward: np.ndarray = reward
        self.reset_observation: np.ndarray = reset_observation
        self.horizon_terminated: np.ndarray = horizon_terminated
        self.horizon_truncated: np.ndarray = horizon_truncated
        self.horizon_time: np.ndarray = horizon_time


def _action_value(case: FmugymWorkerCase, time_value: float) -> np.float32:
    """Evaluate the fixed interval action for one benchmark case.

    :param case: Benchmark case selecting the action schedule.
    :param time_value: Accepted lower boundary of the communication interval.
    :return: Single-precision action passed identically to both engines.
    """

    if case == FmugymWorkerCase.FMI2_SMIB:
        if time_value < 0.5:
            action: np.float32 = np.float32(0.0)
        else:
            if time_value < 2.5:
                action = np.float32(0.025)
            else:
                action = np.float32(-0.01)
    else:
        action = np.float32(0.1 + 0.25 * math.sin(math.pi * time_value))
    return action


def _execute_fmugym(config: FmugymWorkerConfig) -> FmugymWorkerTrace:
    """Run one fixed case through the public FMUGym environment lifecycle.

    :param config: Validated worker configuration.
    :return: Complete accepted trace plus reset and horizon evidence.
    """

    inputs: VarSpace = VarSpace("inputs")
    inputs.add_var_box(config.input_name, -1000.0, 1000.0)
    outputs: VarSpace = VarSpace("outputs")
    output_index: int
    for output_index in range(len(config.output_names)):
        outputs.add_var_box(
            config.output_names[output_index],
            -1.0e30,
            1.0e30,
        )
    random_variables: VarSpace = VarSpace("random_vars")
    upstream_config: FMUGymConfig = FMUGymConfig(
        fmu_path=str(config.fmu_path),
        start_time=config.start_time,
        stop_time=config.stop_time,
        sim_step_size=config.step_size,
        # FMUGym always performs a full simulation step while its accumulated
        # time is below the action boundary. A strictly smaller action period
        # therefore requests exactly one FMI step and leaves enough margin to
        # prevent accumulated round-off from requesting a second one.
        action_step_size=0.5 * config.step_size,
        inputs=inputs,
        outputs=outputs,
        random_vars=random_variables,
    )
    environment: FmugymBenchmarkEnvironment = FmugymBenchmarkEnvironment(
        upstream_config
    )
    mapping_is_valid: bool = bool(
        len(environment.input_dict) == 1
        and len(environment.output_dict) == len(config.output_names)
    )
    if mapping_is_valid:
        pass
    else:
        environment.close()
        raise ValueError("FMUGym did not map the declared benchmark signals")
    # FMUGym emits observations in modelDescription order. The evidence
    # contract owns a stable semantic order, so map every observed position by
    # signal name before accepting numerical values.
    observed_output_names: tuple[str, ...] = tuple(environment.output_dict.keys())
    output_positions: list[int] = [0] * len(config.output_names)
    output_index: int
    for output_index in range(len(config.output_names)):
        output_positions[output_index] = observed_output_names.index(
            config.output_names[output_index]
        )
    ordered_positions: np.ndarray = np.asarray(output_positions, dtype=np.int64)
    reset_observation_raw: np.ndarray
    reset_info: dict[str, str]
    reset_observation_raw, reset_info = environment.reset(seed=0)
    reset_is_valid: bool = bool(
        isinstance(reset_info, dict)
        and reset_observation_raw.shape == (len(config.output_names),)
        and np.all(np.isfinite(reset_observation_raw))
    )
    if reset_is_valid:
        reset_observation: np.ndarray = np.asarray(
            reset_observation_raw[ordered_positions],
            dtype=np.float64,
        )
    else:
        environment.close()
        raise ValueError("FMUGym reset did not return the declared observation")

    interval_count: int = int(
        round((config.stop_time - config.start_time) / config.step_size)
    )
    row_count: int = interval_count + 1
    times: np.ndarray = np.empty(row_count, dtype=np.float64)
    actions: np.ndarray = np.empty(row_count, dtype=np.float64)
    values: np.ndarray = np.empty(
        (row_count, len(config.output_names)),
        dtype=np.float64,
    )
    rewards: np.ndarray = np.empty(row_count, dtype=np.float64)
    times[0] = config.start_time
    actions[0] = float(_action_value(config.case, config.start_time))
    values[0, :] = reset_observation
    rewards[0] = -float(np.dot(reset_observation, reset_observation))

    for interval_index in range(interval_count):
        lower_time: float = config.start_time + interval_index * config.step_size
        action_value: np.float32 = _action_value(config.case, lower_time)
        action_vector: np.ndarray = np.asarray([action_value], dtype=np.float32)
        observation_raw: np.ndarray
        reward_raw: float
        terminated: bool
        truncated: bool
        info: dict[str, str]
        observation_raw, reward_raw, terminated, truncated, info = environment.step(
            action_vector
        )
        accepted_step_is_valid: bool = bool(
            not terminated
            and not truncated
            and isinstance(info, dict)
            and observation_raw.shape == (len(config.output_names),)
            and np.all(np.isfinite(observation_raw))
            and math.isfinite(float(reward_raw))
        )
        if accepted_step_is_valid:
            destination_index: int = interval_index + 1
            # Preserve the time that FMUGym actually supplied to the FMU. The
            # parent comparison evaluates its drift from the ideal lattice as
            # a separate wrapper finding instead of rewriting runtime state.
            times[destination_index] = float(environment.time)
            actions[destination_index] = float(action_value)
            values[destination_index, :] = np.asarray(
                observation_raw[ordered_positions],
                dtype=np.float64,
            )
            rewards[destination_index] = float(reward_raw)
        else:
            environment.close()
            raise ValueError("FMUGym ended before the accepted comparison lattice")

    horizon_terminated: np.ndarray = np.empty(2, dtype=np.bool_)
    horizon_truncated: np.ndarray = np.empty(2, dtype=np.bool_)
    horizon_time: np.ndarray = np.empty(2, dtype=np.float64)
    for probe_index in range(2):
        probe_action: np.float32 = _action_value(config.case, environment.time)
        probe_vector: np.ndarray = np.asarray([probe_action], dtype=np.float32)
        probe_observation: np.ndarray
        probe_reward: float
        probe_terminated: bool
        probe_truncated: bool
        probe_info: dict[str, str]
        (
            probe_observation,
            probe_reward,
            probe_terminated,
            probe_truncated,
            probe_info,
        ) = environment.step(probe_vector)
        probe_is_valid: bool = bool(
            probe_observation.shape == (len(config.output_names),)
            and np.all(np.isfinite(probe_observation))
            and math.isfinite(float(probe_reward))
            and isinstance(probe_info, dict)
        )
        if probe_is_valid:
            horizon_terminated[probe_index] = probe_terminated
            horizon_truncated[probe_index] = probe_truncated
            horizon_time[probe_index] = float(environment.time)
        else:
            environment.close()
            raise ValueError("FMUGym horizon probe returned invalid data")
    environment.close()
    return FmugymWorkerTrace(
        time=times,
        action=actions,
        outputs=values,
        reward=rewards,
        reset_observation=reset_observation,
        horizon_terminated=horizon_terminated,
        horizon_truncated=horizon_truncated,
        horizon_time=horizon_time,
    )


def _execute_direct_fmpy(config: FmugymWorkerConfig) -> FmugymWorkerTrace:
    """Run one fixed case directly through the pinned low-level FMPy API.

    :param config: Validated worker configuration.
    :return: Complete reference trace on the same action and time lattice.
    """

    model_description: ModelDescription = read_model_description(config.fmu_path)
    interface_is_valid: bool = bool(model_description.coSimulation is not None)
    if interface_is_valid:
        model_identifier: str = model_description.coSimulation.modelIdentifier
    else:
        raise ValueError("Direct reference requires a Co-Simulation FMU")

    input_reference: int | None = None
    output_references: list[int] = [0] * len(config.output_names)
    output_found: list[bool] = [False] * len(config.output_names)
    variable: ModelVariable
    for variable in model_description.modelVariables:
        if variable.name == config.input_name:
            input_reference = int(variable.valueReference)
        else:
            pass
        output_index: int
        for output_index in range(len(config.output_names)):
            if variable.name == config.output_names[output_index]:
                output_references[output_index] = int(variable.valueReference)
                output_found[output_index] = True
            else:
                pass
    mapping_is_valid: bool = bool(
        input_reference is not None and all(output_found)
    )
    if mapping_is_valid:
        pass
    else:
        raise ValueError("Direct FMPy did not map the declared benchmark signals")

    unzip_directory: str = extract(config.fmu_path)
    is_fmi_two: bool = bool(model_description.fmiVersion == "2.0")
    is_fmi_three: bool = bool(model_description.fmiVersion.startswith("3.0"))
    slave: FMU2Slave | FMU3Slave
    if is_fmi_two:
        slave = FMU2Slave(
            guid=model_description.guid,
            unzipDirectory=unzip_directory,
            modelIdentifier=model_identifier,
            instanceName="direct-fmpy",
        )
        slave.instantiate()
        slave.setupExperiment(startTime=config.start_time)
        slave.enterInitializationMode()
        slave.exitInitializationMode()
    else:
        if is_fmi_three:
            slave = FMU3Slave(
                guid=model_description.guid,
                unzipDirectory=unzip_directory,
                modelIdentifier=model_identifier,
                instanceName="direct-fmpy",
            )
            slave.instantiate()
            slave.enterInitializationMode()
            slave.exitInitializationMode()
        else:
            shutil.rmtree(unzip_directory, ignore_errors=True)
            raise ValueError("Direct reference supports only FMI 2 or FMI 3")

    interval_count: int = int(
        round((config.stop_time - config.start_time) / config.step_size)
    )
    row_count: int = interval_count + 1
    times: np.ndarray = np.empty(row_count, dtype=np.float64)
    actions: np.ndarray = np.empty(row_count, dtype=np.float64)
    values: np.ndarray = np.empty(
        (row_count, len(config.output_names)),
        dtype=np.float64,
    )
    rewards: np.ndarray = np.empty(row_count, dtype=np.float64)
    times[0] = config.start_time
    actions[0] = float(_action_value(config.case, config.start_time))
    if is_fmi_two:
        initial_values: list[float] = slave.getReal(output_references)
    else:
        initial_values = slave.getFloat64(output_references)
    values[0, :] = np.asarray(initial_values, dtype=np.float64)
    rewards[0] = -float(np.dot(values[0, :], values[0, :]))

    current_time: float = config.start_time
    for interval_index in range(interval_count):
        ideal_lower_time: float = (
            config.start_time + interval_index * config.step_size
        )
        action_value: np.float32 = _action_value(config.case, ideal_lower_time)
        if is_fmi_two:
            slave.setReal([input_reference], [float(action_value)])
        else:
            slave.setFloat64([input_reference], [float(action_value)])
        slave.doStep(
            currentCommunicationPoint=current_time,
            communicationStepSize=config.step_size,
        )
        current_time = current_time + config.step_size
        if is_fmi_two:
            output_values: list[float] = slave.getReal(output_references)
        else:
            output_values = slave.getFloat64(output_references)
        destination_index: int = interval_index + 1
        times[destination_index] = current_time
        actions[destination_index] = float(action_value)
        values[destination_index, :] = np.asarray(
            output_values,
            dtype=np.float64,
        )
        rewards[destination_index] = -float(
            np.dot(values[destination_index, :], values[destination_index, :])
        )
    slave.terminate()
    slave.freeInstance()
    shutil.rmtree(unzip_directory, ignore_errors=True)
    finite_trace: bool = bool(
        np.all(np.isfinite(times))
        and np.all(np.isfinite(actions))
        and np.all(np.isfinite(values))
        and np.all(np.isfinite(rewards))
    )
    if finite_trace:
        pass
    else:
        raise ValueError("Direct FMPy produced non-finite trace data")
    empty_bool: np.ndarray = np.empty(0, dtype=np.bool_)
    empty_float: np.ndarray = np.empty(0, dtype=np.float64)
    return FmugymWorkerTrace(
        time=times,
        action=actions,
        outputs=values,
        reward=rewards,
        reset_observation=np.asarray(initial_values, dtype=np.float64),
        horizon_terminated=empty_bool,
        horizon_truncated=empty_bool.copy(),
        horizon_time=empty_float,
    )


def _write_worker_trace(
    config: FmugymWorkerConfig,
    trace: FmugymWorkerTrace,
) -> None:
    """Write one complete trace with deterministic columns and precision.

    :param config: Worker configuration defining ordered output names.
    :param trace: Completed worker trace.
    :return: None.
    """

    trace_file: TextIO = config.trace_path.open(
        "w",
        encoding="utf-8",
        newline="",
    )
    try:
        writer: csv.writer = csv.writer(trace_file, lineterminator="\n")
        header: list[str] = ["time", "action"]
        header.extend(config.output_names)
        header.append("reward")
        writer.writerow(header)
        row_index: int
        for row_index in range(trace.time.size):
            row: list[str] = [
                format(float(trace.time[row_index]), ".17g"),
                format(float(trace.action[row_index]), ".17g"),
            ]
            output_index: int
            for output_index in range(len(config.output_names)):
                row.append(
                    format(float(trace.outputs[row_index, output_index]), ".17g")
                )
            row.append(format(float(trace.reward[row_index]), ".17g"))
            writer.writerow(row)
    finally:
        trace_file.close()


def _write_worker_result(
    config: FmugymWorkerConfig,
    trace: FmugymWorkerTrace,
) -> None:
    """Write lifecycle and runtime facts for independent parent verification.

    :param config: Worker configuration defining the fixed cell.
    :param trace: Completed worker trace and horizon probe.
    :return: None.
    """

    horizon: dict[str, object] | None
    if config.engine == FmugymWorkerEngine.FMUGYM:
        horizon = {
            "terminated": [
                bool(trace.horizon_terminated[0]),
                bool(trace.horizon_terminated[1]),
            ],
            "truncated": [
                bool(trace.horizon_truncated[0]),
                bool(trace.horizon_truncated[1]),
            ],
            "time_after_step": [
                float(trace.horizon_time[0]),
                float(trace.horizon_time[1]),
            ],
        }
    else:
        horizon = None
    payload: dict[str, object] = {
        "schema": "veragrid.fmugym-worker/1",
        "status": "PASS",
        "engine": config.engine.value,
        "case": config.case.value,
        "python_version": platform.python_version(),
        "packages": {
            "fmugym": version("fmugym"),
            "fmpy": version("FMPy"),
            "gymnasium": version("gymnasium"),
            "matplotlib": version("matplotlib"),
            "numpy": version("numpy"),
        },
        "fmi_version": (
            "2.0"
            if config.case == FmugymWorkerCase.FMI2_SMIB
            else "3.0"
        ),
        "start_time": config.start_time,
        "stop_time": config.stop_time,
        "step_size": config.step_size,
        "row_count": int(trace.time.size),
        "input_name": config.input_name,
        "output_names": list(config.output_names),
        "reset_observation": trace.reset_observation.tolist(),
        "horizon": horizon,
    }
    result_file: TextIO = config.result_path.open("w", encoding="utf-8")
    try:
        json.dump(payload, result_file, indent=2, ensure_ascii=False)
        result_file.write("\n")
    finally:
        result_file.close()


def main() -> int:
    """Parse the fixed worker CLI and execute exactly one engine/case pair.

    :return: Zero after complete trace and result publication.
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Run one isolated FMUGym comparison cell."
    )
    parser.add_argument("--engine", required=True, choices=[item.value for item in FmugymWorkerEngine])
    parser.add_argument("--case", required=True, choices=[item.value for item in FmugymWorkerCase])
    parser.add_argument("--fmu", required=True, type=Path)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    arguments: argparse.Namespace = parser.parse_args()
    config: FmugymWorkerConfig = FmugymWorkerConfig(
        engine=FmugymWorkerEngine(arguments.engine),
        case=FmugymWorkerCase(arguments.case),
        fmu_path=arguments.fmu,
        trace_path=arguments.trace,
        result_path=arguments.result,
    )
    parent_paths_are_valid: bool = bool(
        config.fmu_path.is_file()
        and config.trace_path.parent.is_dir()
        and config.result_path.parent == config.trace_path.parent
    )
    if parent_paths_are_valid:
        pass
    else:
        raise ValueError("Worker paths do not satisfy the staged ownership boundary")
    if config.engine == FmugymWorkerEngine.FMUGYM:
        trace: FmugymWorkerTrace = _execute_fmugym(config)
    else:
        trace = _execute_direct_fmpy(config)
    _write_worker_trace(config, trace)
    _write_worker_result(config, trace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
