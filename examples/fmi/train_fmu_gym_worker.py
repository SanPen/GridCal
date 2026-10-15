"""Run one isolated train_fmu_gym comparison workload."""

from __future__ import annotations

import argparse
from enum import Enum
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

import gymnasium as gym
import numpy as np
import torch
from stable_baselines3 import A2C
from torch.nn.utils import parameters_to_vector

import train_fmu_gym


class TrainFmuGymWorkerMode(str, Enum):
    """Workloads supported by the isolated worker."""

    TRAINING_CORE = "TRAINING_CORE"
    PUBLIC_CLI = "PUBLIC_CLI"


class TrainFmuGymWorkerConfig:
    """Immutable inputs for one isolated worker invocation."""

    __slots__ = ("mode", "environment_name", "fmu_path", "output_directory")

    def __init__(
        self,
        mode: TrainFmuGymWorkerMode,
        environment_name: str,
        fmu_path: Path,
        output_directory: Path,
    ) -> None:
        """Create a worker configuration.

        :param mode: Exact worker workload.
        :param environment_name: Registered train_fmu_gym environment name.
        :param fmu_path: FMU owned by the generated environment.
        :param output_directory: Existing private directory for raw evidence.
        """

        self.mode: TrainFmuGymWorkerMode = mode
        self.environment_name: str = environment_name
        self.fmu_path: Path = fmu_path
        self.output_directory: Path = output_directory


class TrainFmuGymWorkerResult:
    """Typed summary returned by a completed worker workload."""

    __slots__ = (
        "mode",
        "environment_name",
        "status",
        "result_path",
        "trace_path",
    )

    def __init__(
        self,
        mode: TrainFmuGymWorkerMode,
        environment_name: str,
        status: str,
        result_path: Path,
        trace_path: Path | None,
    ) -> None:
        """Create the typed worker summary.

        :param mode: Workload that ran.
        :param environment_name: Environment exercised by the workload.
        :param status: Evidence status written by the worker.
        :param result_path: Structured result JSON path.
        :param trace_path: Evaluation trace path, when produced.
        """

        self.mode: TrainFmuGymWorkerMode = mode
        self.environment_name: str = environment_name
        self.status: str = status
        self.result_path: Path = result_path
        self.trace_path: Path | None = trace_path


def _execute_training_core(config: TrainFmuGymWorkerConfig) -> TrainFmuGymWorkerResult:
    """Train A2C and retain one deterministic evaluation trajectory.

    :param config: Authenticated worker configuration.
    :return: Typed paths and status for the completed training workload.
    """

    # One Torch thread makes the numerical workload independent of host core
    # count while the fixed seed controls the policy initialization.
    torch.set_num_threads(1)
    environment: gym.Env = gym.make(config.environment_name)
    policy_options: dict[str, list[int]] = dict(net_arch=[16, 16])
    model: A2C = A2C(
        "MlpPolicy",
        environment,
        learning_rate=0.0007,
        n_steps=8,
        gamma=0.99,
        gae_lambda=1.0,
        ent_coef=0.0,
        seed=938,
        policy_kwargs=policy_options,
        device="cpu",
        verbose=0,
    )

    # A changed parameter vector distinguishes genuine optimization from mere
    # construction of an FMU-backed Gymnasium environment.
    initial_parameters: torch.Tensor = parameters_to_vector(
        model.policy.parameters()
    ).detach().clone()
    model.learn(total_timesteps=128, progress_bar=False)
    trained_parameters: torch.Tensor = parameters_to_vector(
        model.policy.parameters()
    ).detach().clone()
    parameter_delta: torch.Tensor = trained_parameters - initial_parameters

    observation_raw: np.ndarray
    reset_information: dict[str, object]
    observation_raw, reset_information = environment.reset(seed=938)
    observation: np.ndarray = np.asarray(observation_raw, dtype=np.float64)
    step_capacity: int = 256
    observation_count: int = int(observation.size)
    observations: np.ndarray = np.empty(
        (step_capacity + 1, observation_count), dtype=np.float64
    )
    actions: np.ndarray = np.empty(step_capacity, dtype=np.float64)
    rewards: np.ndarray = np.empty(step_capacity, dtype=np.float64)
    observations[0, :] = observation
    terminated: bool = False
    truncated: bool = False
    step_index: int = 0

    # Retain every accepted sample required to recompute finiteness, ranges,
    # reward and cross-version trace equality outside this process.
    while step_index < step_capacity and not terminated and not truncated:
        action_raw: np.ndarray
        predictor_state: object
        action_raw, predictor_state = model.predict(
            observation_raw, deterministic=True
        )
        next_observation_raw: np.ndarray
        reward_raw: float
        step_information: dict[str, object]
        next_observation_raw, reward_raw, terminated, truncated, step_information = (
            environment.step(action_raw)
        )
        action_vector: np.ndarray = np.asarray(action_raw, dtype=np.float64).reshape(-1)
        next_observation: np.ndarray = np.asarray(
            next_observation_raw, dtype=np.float64
        )
        actions[step_index] = float(action_vector[0])
        rewards[step_index] = float(reward_raw)
        observations[step_index + 1, :] = next_observation
        observation_raw = next_observation_raw
        step_index += 1

    environment.close()
    retained_observations: np.ndarray = observations[: step_index + 1, :]
    retained_actions: np.ndarray = actions[:step_index]
    retained_rewards: np.ndarray = rewards[:step_index]
    leading_missing: np.ndarray = np.asarray((np.nan,), dtype=np.float64)
    trace_matrix: np.ndarray = np.column_stack(
        (
            np.arange(step_index + 1, dtype=np.float64) * 0.01,
            retained_observations,
            np.concatenate((leading_missing, retained_actions)),
            np.concatenate((leading_missing, retained_rewards)),
        )
    )
    trace_path: Path = config.output_directory / "trace.csv"
    np.savetxt(
        trace_path,
        trace_matrix,
        delimiter=",",
        header=(
            "time,observation_0,observation_1,observation_2,"
            "observation_3,action,reward"
        ),
        comments="",
    )

    digest: hashlib._Hash = hashlib.sha256()
    digest.update(config.fmu_path.read_bytes())
    result: dict[str, object] = dict(
        schema="veragrid.train-fmu-gym-worker/1",
        mode=config.mode.name,
        status="PASS",
        environment=config.environment_name,
        fmu_size_bytes=config.fmu_path.stat().st_size,
        fmu_sha256=digest.hexdigest(),
        train_fmu_gym_version=importlib.metadata.version("train_fmu_gym"),
        stable_baselines3_version=importlib.metadata.version("stable_baselines3"),
        torch_version=torch.__version__,
        seed=938,
        training_timesteps=128,
        evaluation_steps=step_index,
        parameter_count=int(initial_parameters.numel()),
        parameter_max_abs_delta=float(torch.max(torch.abs(parameter_delta)).item()),
        parameters_changed=bool(torch.any(parameter_delta != 0.0).item()),
        finite_observations=bool(np.all(np.isfinite(retained_observations))),
        finite_actions=bool(np.all(np.isfinite(retained_actions))),
        finite_rewards=bool(np.all(np.isfinite(retained_rewards))),
        reward_sum=float(np.sum(retained_rewards)),
        terminated=terminated,
        truncated=truncated,
        reset_information_size=len(reset_information),
        predictor_state_was_none=predictor_state is None,
        final_step_information_size=len(step_information),
    )
    result_path: Path = config.output_directory / "result.json"
    _write_train_fmu_gym_worker_result(result_path, result)
    return TrainFmuGymWorkerResult(
        config.mode, config.environment_name, "PASS", result_path, trace_path
    )


def _execute_public_cli(config: TrainFmuGymWorkerConfig) -> TrainFmuGymWorkerResult:
    """Execute the public training command and retain its real child outcome.

    :param config: Authenticated worker configuration.
    :return: Typed paths and status for the completed CLI workload.
    """

    environment_base: str = config.environment_name.rsplit("_v", maxsplit=1)[0]
    command: list[str] = list(
        (
            sys.executable,
            "-m",
            "train_fmu_gym",
            "train",
            "-e",
            environment_base,
            "-v",
            "v1",
            "-s",
            "default_a2c",
        )
    )
    process: subprocess.CompletedProcess[bytes] = subprocess.run(
        command,
        cwd=config.output_directory,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120.0,
        check=False,
    )
    stdout_path: Path = config.output_directory / "stdout.log"
    stderr_path: Path = config.output_directory / "stderr.log"
    stdout_path.write_bytes(process.stdout)
    stderr_path.write_bytes(process.stderr)
    combined_text: str = process.stdout.decode("utf-8", errors="replace") + process.stderr.decode(
        "utf-8", errors="replace"
    )
    child_failed: bool = "ModuleNotFoundError" in combined_text
    trained_artifacts: list[Path] = list(config.output_directory.rglob("*.zip"))
    if process.returncode == 0 and not child_failed and len(trained_artifacts) > 0:
        status: str = "PASS"
        findings: list[str] = list()
    else:
        status = "COMPLETED_WITH_FINDINGS"
        findings = list(
            (
                "TRAIN_FMU_GYM_CHILD_INTERPRETER_NOT_BOUND",
                "TRAIN_FMU_GYM_CHILD_FAILURE_NOT_PROPAGATED",
            )
        )
    result: dict[str, object] = dict(
        schema="veragrid.train-fmu-gym-worker/1",
        mode=config.mode.name,
        status=status,
        environment=config.environment_name,
        command=command,
        outer_exit_code=process.returncode,
        module_not_found_observed=child_failed,
        trained_artifact_count=len(trained_artifacts),
        findings=findings,
    )
    result_path: Path = config.output_directory / "result.json"
    _write_train_fmu_gym_worker_result(result_path, result)
    return TrainFmuGymWorkerResult(
        config.mode, config.environment_name, status, result_path, None
    )


def _write_train_fmu_gym_worker_result(
    result_path: Path,
    result: dict[str, object],
) -> None:
    """Write one deterministic structured worker result.

    :param result_path: Destination JSON path.
    :param result: Complete worker result payload.
    :return: None.
    """

    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    """Parse explicit arguments and execute exactly one worker workload.

    :return: Zero after a structured result is written.
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=tuple(member.name for member in TrainFmuGymWorkerMode))
    parser.add_argument("--environment", required=True)
    parser.add_argument("--fmu", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    arguments: argparse.Namespace = parser.parse_args()
    mode: TrainFmuGymWorkerMode = TrainFmuGymWorkerMode[arguments.mode]
    output_directory: Path = arguments.output_directory.resolve(strict=True)
    config: TrainFmuGymWorkerConfig = TrainFmuGymWorkerConfig(
        mode=mode,
        environment_name=arguments.environment,
        fmu_path=arguments.fmu.resolve(strict=True),
        output_directory=output_directory,
    )
    if mode == TrainFmuGymWorkerMode.TRAINING_CORE:
        _execute_training_core(config)
    else:
        _execute_public_cli(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
