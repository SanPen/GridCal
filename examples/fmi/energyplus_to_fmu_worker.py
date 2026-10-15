# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Isolated worker for the EnergyPlusToFMU compatibility export and probe."""
from __future__ import annotations

import argparse
import csv
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
from typing import BinaryIO, TextIO

from fmpy import calloc, extract, free, read_model_description
from fmpy.fmi1 import (
    FMICallException,
    FMU1Slave,
    fmi1CallbackAllocateMemoryTYPE,
    fmi1CallbackFreeMemoryTYPE,
    fmi1CallbackFunctions,
    fmi1CallbackLoggerTYPE,
)
from fmpy.model_description import ModelDescription


class EnergyPlusToFmuWorkerMode(str, Enum):
    """Operations that require an isolated operating-system process."""

    EXPORT = "EXPORT"
    RUNTIME_PROBE = "RUNTIME_PROBE"


class EnergyPlusToFmuWorkerConfig:
    """Own all explicit paths and bounds consumed by one worker invocation."""

    __slots__ = (
        "mode",
        "result_path",
        "working_directory",
        "cmd_path",
        "vsdevcmd_path",
        "compiler_path",
        "compiler_size_bytes",
        "compiler_sha256",
        "linker_path",
        "linker_size_bytes",
        "linker_sha256",
        "python_path",
        "exporter_path",
        "idd_path",
        "idf_path",
        "epw_path",
        "fmu_path",
        "trace_path",
        "energyplus_directory",
        "communication_step_seconds",
        "steps_per_level",
        "input_levels",
        "temporary_directory",
        "process_timeout_seconds",
        "stream_limit_bytes",
    )

    def __init__(
        self,
        mode: EnergyPlusToFmuWorkerMode,
        result_path: Path,
        working_directory: Path,
        cmd_path: Path,
        vsdevcmd_path: Path,
        compiler_path: Path,
        compiler_size_bytes: int,
        compiler_sha256: str,
        linker_path: Path,
        linker_size_bytes: int,
        linker_sha256: str,
        python_path: Path,
        exporter_path: Path,
        idd_path: Path,
        idf_path: Path,
        epw_path: Path,
        fmu_path: Path,
        trace_path: Path,
        energyplus_directory: Path,
        communication_step_seconds: float,
        steps_per_level: int,
        input_levels: tuple[float, ...],
        temporary_directory: Path,
        process_timeout_seconds: float,
        stream_limit_bytes: int,
    ) -> None:
        """Initialize a closed worker request.

        :param mode: Export or runtime-probe operation.
        :param result_path: Destination for the structured worker result.
        :param working_directory: Private directory owned by this invocation.
        :param cmd_path: Absolute Windows command processor path.
        :param vsdevcmd_path: Authenticated Visual Studio environment script.
        :param compiler_path: Exact compiler expected from VsDevCmd.
        :param compiler_size_bytes: Required compiler byte count.
        :param compiler_sha256: Required compiler digest.
        :param linker_path: Exact linker expected from VsDevCmd.
        :param linker_size_bytes: Required linker byte count.
        :param linker_sha256: Required linker digest.
        :param python_path: Absolute Python interpreter used by the exporter.
        :param exporter_path: Authenticated compatibility entry script.
        :param idd_path: Authenticated EnergyPlus 9.4 dictionary.
        :param idf_path: Authenticated Schedule model.
        :param epw_path: Authenticated Chicago weather data for ``RunPeriod``.
        :param fmu_path: FMU consumed by a runtime probe.
        :param trace_path: Destination for the complete runtime trajectory.
        :param energyplus_directory: Directory containing energyplus.exe.
        :param communication_step_seconds: FMI communication interval.
        :param steps_per_level: Number of intervals per input plateau.
        :param input_levels: Ordered heat-flow plateaus applied to ``Q``.
        :param temporary_directory: Explicit temporary directory.
        :param process_timeout_seconds: Hard external-process deadline.
        :param stream_limit_bytes: Maximum retained bytes per output stream.
        :return: None.
        """

        self.mode = mode
        self.result_path = result_path
        self.working_directory = working_directory
        self.cmd_path = cmd_path
        self.vsdevcmd_path = vsdevcmd_path
        self.compiler_path: Path = compiler_path
        self.compiler_size_bytes: int = compiler_size_bytes
        self.compiler_sha256: str = compiler_sha256
        self.linker_path: Path = linker_path
        self.linker_size_bytes: int = linker_size_bytes
        self.linker_sha256: str = linker_sha256
        self.python_path = python_path
        self.exporter_path = exporter_path
        self.idd_path = idd_path
        self.idf_path = idf_path
        self.epw_path = epw_path
        self.fmu_path = fmu_path
        self.trace_path: Path = trace_path
        self.energyplus_directory = energyplus_directory
        self.communication_step_seconds: float = communication_step_seconds
        self.steps_per_level: int = steps_per_level
        self.input_levels: tuple[float, ...] = input_levels
        self.temporary_directory = temporary_directory
        self.process_timeout_seconds = process_timeout_seconds
        self.stream_limit_bytes = stream_limit_bytes


class EnergyPlusToFmuWorkerResult:
    """Own the JSON-compatible outcome of one isolated operation."""

    __slots__ = ("payload",)

    def __init__(self, payload: dict[str, object]) -> None:
        """Retain a complete result payload.

        :param payload: JSON-compatible result with explicit status.
        :return: None.
        """

        self.payload = payload


def _log_energyplus_fmi_message(
    _component: int | None,
    _instance_name: bytes,
    status: int,
    _category: bytes,
    message: bytes,
) -> None:
    """Decode legacy EnergyPlus diagnostics without crossing the C callback.

    :param _component: Opaque FMI component pointer, unused by the logger.
    :param _instance_name: FMI instance name, unused by this bounded logger.
    :param status: FMI 1 status code.
    :param _category: FMI log category, unused by this bounded logger.
    :param message: Native diagnostic bytes.
    :return: None.
    """

    labels: tuple[str, ...] = (
        "OK", "WARNING", "DISCARD", "ERROR", "FATAL", "PENDING",
    )
    if 0 <= status < len(labels):
        label: str = labels[status]
    else:
        label = "UNKNOWN"
    decoded_message: str = message.decode("utf-8", errors="replace")
    print(f"[{label}] {decoded_message}")


def _create_energyplus_fmi_callbacks() -> fmi1CallbackFunctions:
    """Create an invocation-owned FMI 1 callback table.

    :return: Callback table using FMPy''s allocator and tolerant logger.
    """

    callbacks: fmi1CallbackFunctions = fmi1CallbackFunctions()
    callbacks.logger = fmi1CallbackLoggerTYPE(_log_energyplus_fmi_message)
    callbacks.allocateMemory = fmi1CallbackAllocateMemoryTYPE(calloc)
    callbacks.freeMemory = fmi1CallbackFreeMemoryTYPE(free)
    callbacks.stepFinished = None
    return callbacks


def _execute_energyplus_export(
    config: EnergyPlusToFmuWorkerConfig,
) -> EnergyPlusToFmuWorkerResult:
    """Capture MSVC's environment and invoke the compatibility exporter.

    :param config: Closed export configuration.
    :return: Structured export status and complete child environment.
    """

    # VsDevCmd is the sole authority for compiler paths. The bootstrap does
    # not inherit the interactive shell, making compiler selection auditable.
    bootstrap_environment: dict[str, str] = dict(
        SystemRoot=str(config.cmd_path.parents[1]),
        TEMP=str(config.temporary_directory),
        TMP=str(config.temporary_directory),
        PROCESSOR_ARCHITECTURE="AMD64",
        SystemDrive=str(config.cmd_path.anchor).rstrip("\\"),
        PATH=str(config.cmd_path.parent),
    )
    environment_command: str = (
        f"call {config.vsdevcmd_path} -arch=amd64 -host_arch=amd64 "
        ">nul && set"
    )
    environment_process: subprocess.CompletedProcess[str] = subprocess.run(
        [str(config.cmd_path), "/d", "/s", "/c", environment_command],
        cwd=config.working_directory,
        env=bootstrap_environment,
        shell=False,
        capture_output=True,
        text=True,
        timeout=config.process_timeout_seconds,
        check=False,
    )
    environment_lines: list[str] = environment_process.stdout.splitlines()
    compiler_environment: dict[str, str] = dict()
    for environment_line in environment_lines:
        separator_index: int = environment_line.find("=")
        if separator_index > 0:
            environment_key: str = environment_line[:separator_index]
            environment_value: str = environment_line[separator_index + 1:]
            compiler_environment[environment_key] = environment_value
        else:
            pass
    environment_is_valid: bool = bool(
        environment_process.returncode == 0
        and environment_process.stderr == ""
        and compiler_environment.get("PATH", None) is not None
        and compiler_environment.get("VCINSTALLDIR", None) is not None
    )
    if environment_is_valid:
        allowed_environment_keys: set[str] = set((
            "CommandPromptType", "COMSPEC", "DevEnvDir", "EXTERNAL_INCLUDE",
            "Framework40Version", "FrameworkDir", "FrameworkDir64",
            "FrameworkVersion", "FrameworkVersion64", "INCLUDE", "LIB",
            "LIBPATH", "PATH", "PATHEXT", "PROCESSOR_ARCHITECTURE", "PROMPT",
            "SystemDrive", "SystemRoot", "TEMP", "TMP", "VCIDEInstallDir", "VCINSTALLDIR",
            "VCToolsInstallDir", "VCToolsRedistDir", "VCToolsVersion",
            "VisualStudioVersion", "VS170COMNTOOLS", "VSCMD_ARG_app_plat",
            "VSCMD_ARG_HOST_ARCH", "VSCMD_ARG_TGT_ARCH", "VSCMD_VER",
            "VSINSTALLDIR", "WindowsLibPath", "WindowsSDKLibVersion",
            "WindowsSDKVersion", "WindowsSdkBinPath", "WindowsSdkDir",
            "WindowsSdkVerBinPath", "__VSCMD_PREINIT_PATH",
            "UniversalCRTSdkDir", "UCRTVersion", "ExtensionSdkDir",
            "__DOTNET_ADD_64BIT",
            "__DOTNET_PREFERRED_BITNESS",
        ))
        returned_keys_are_allowed: bool = set(compiler_environment.keys()).issubset(
            allowed_environment_keys
        )
        if returned_keys_are_allowed:
            pass
        else:
            raise RuntimeError("VsDevCmd returned an unexpected environment key")
        compiler_path: str = compiler_environment["PATH"]
        compiler_environment["PATH"] = (
            compiler_path + os.pathsep + str(config.energyplus_directory)
        )
        resolved_compiler: str | None = shutil.which("cl.exe", path=compiler_path)
        resolved_linker: str | None = shutil.which("link.exe", path=compiler_path)
        if resolved_compiler is not None and resolved_linker is not None:
            resolved_compiler_path: Path = Path(resolved_compiler).resolve(strict=True)
            resolved_linker_path: Path = Path(resolved_linker).resolve(strict=True)
            compiler_bytes: bytes = resolved_compiler_path.read_bytes()
            linker_bytes: bytes = resolved_linker_path.read_bytes()
            toolchain_is_authenticated: bool = bool(
                resolved_compiler_path == config.compiler_path.resolve(strict=True)
                and len(compiler_bytes) == config.compiler_size_bytes
                and hashlib.sha256(compiler_bytes).hexdigest()
                == config.compiler_sha256
                and resolved_linker_path == config.linker_path.resolve(strict=True)
                and len(linker_bytes) == config.linker_size_bytes
                and hashlib.sha256(linker_bytes).hexdigest()
                == config.linker_sha256
            )
            if toolchain_is_authenticated:
                pass
            else:
                raise RuntimeError(
                    "VsDevCmd resolved an unauthenticated compiler toolchain"
                )
        else:
            raise RuntimeError("VsDevCmd did not expose cl.exe and link.exe")
    else:
        raise RuntimeError("VsDevCmd did not produce a usable MSVC environment")

    export_command: list[str] = list(
        (
            str(config.python_path),
            "-B",
            str(config.exporter_path),
            "-w",
            str(config.epw_path),
            "-i",
            str(config.idd_path),
            "-a",
            "1",
            str(config.idf_path),
        )
    )
    export_process: subprocess.CompletedProcess[str] = subprocess.run(
        export_command,
        cwd=config.working_directory,
        env=compiler_environment,
        shell=False,
        capture_output=True,
        text=True,
        timeout=config.process_timeout_seconds,
        check=False,
    )
    expected_fmu: Path = config.working_directory / (config.idf_path.stem + ".fmu")
    stream_bounds_hold: bool = bool(
        len(export_process.stdout.encode("utf-8")) <= config.stream_limit_bytes
        and len(export_process.stderr.encode("utf-8")) <= config.stream_limit_bytes
    )
    export_passed: bool = bool(
        export_process.returncode == 0
        and expected_fmu.exists()
        and expected_fmu.is_file()
        and stream_bounds_hold
    )
    payload: dict[str, object] = dict(
        schema="veragrid.energyplus-to-fmu-worker/1",
        mode=config.mode.value,
        status="PASS" if export_passed else "FAIL",
        command=export_command,
        exit_code=export_process.returncode,
        environment=compiler_environment,
        stdout=export_process.stdout,
        stderr=export_process.stderr,
        fmu_name=expected_fmu.name,
        compiler_path=resolved_compiler,
        linker_path=resolved_linker,
    )
    return EnergyPlusToFmuWorkerResult(payload)


def _write_energyplus_runtime_trace(
    trace_path: Path,
    time_values: list[float],
    input_values: list[float],
    output_values: list[float],
) -> None:
    """Write the complete FMI 1 trajectory with deterministic precision.

    :param trace_path: Explicit CSV destination.
    :param time_values: Accepted communication-point times in seconds.
    :param input_values: Heat-flow values applied to Q.
    :param output_values: Zone temperatures read from TRooMea.
    :return: None.
    """

    trace_file: TextIO = trace_path.open("w", encoding="utf-8", newline="")
    try:
        writer: csv.writer = csv.writer(trace_file, lineterminator="\n")
        writer.writerow(("time_s", "Q_W", "TRooMea_degC"))
        row_index: int
        for row_index in range(len(time_values)):
            writer.writerow(
                (
                    format(time_values[row_index], ".17g"),
                    format(input_values[row_index], ".17g"),
                    format(output_values[row_index], ".17g"),
                )
            )
    finally:
        trace_file.close()


def _execute_energyplus_runtime_probe(
    config: EnergyPlusToFmuWorkerConfig,
) -> EnergyPlusToFmuWorkerResult:
    """Execute a bounded FMI 1 Co-Simulation trajectory through FMPy.

    :param config: Closed runtime-probe configuration.
    :return: Structured lifecycle verdict and numerical evidence summary.
    """

    findings: list[str] = list()
    diagnostic: str = ""
    time_values: list[float] = list()
    input_values: list[float] = list()
    output_values: list[float] = list()
    instantiated: bool = False
    initialized: bool = False
    terminated: bool = False
    instance_released: bool = False
    extraction_directory: Path = config.working_directory / "extracted-fmu"
    extracted_path: str = extract(
        filename=str(config.fmu_path),
        unzipdir=str(extraction_directory),
    )
    model_description: ModelDescription = read_model_description(
        str(config.fmu_path),
        validate=True,
    )
    if model_description.coSimulation is not None:
        model_identifier: str = model_description.coSimulation.modelIdentifier
    else:
        raise ValueError("EnergyPlusToFMU artifact is not Co-Simulation")
    fmu: FMU1Slave = FMU1Slave(
        guid=model_description.guid,
        unzipDirectory=extracted_path,
        modelIdentifier=model_identifier,
        instanceName="veragrid_energyplus_probe",
    )
    callbacks: fmi1CallbackFunctions = _create_energyplus_fmi_callbacks()
    total_steps: int = len(config.input_levels) * config.steps_per_level
    stop_time: float = total_steps * config.communication_step_seconds
    try:
        # EnergyPlusToFMU requires midnight boundaries, matching the complete
        # 86,400-second scenario validated by the worker input contract.
        print("ENERGYPLUS_FMI_STAGE=instantiate", flush=True)
        fmu.instantiate(functions=callbacks, loggingOn=False)
        instantiated = fmu.component is not None
        if instantiated:
            print("ENERGYPLUS_FMI_STAGE=set_initial_input", flush=True)
            fmu.setReal((1,), (config.input_levels[0],))
            print("ENERGYPLUS_FMI_STAGE=initialize", flush=True)
            fmu.initialize(tStart=0.0, stopTime=stop_time)
            initialized = True
            print("ENERGYPLUS_FMI_STAGE=initialized", flush=True)
            sample_index: int
            for sample_index in range(total_steps + 1):
                level_index: int = min(
                    sample_index // config.steps_per_level,
                    len(config.input_levels) - 1,
                )
                time_value: float = sample_index * config.communication_step_seconds
                input_value: float = config.input_levels[level_index]

                # The official importer contract requires every input set and
                # every output read before each subsequent fmiDoStep call.
                fmu.setReal((1,), (input_value,))
                output_value: float = float(fmu.getReal((100001,))[0])
                time_values.append(time_value)
                input_values.append(input_value)
                output_values.append(output_value)
                if sample_index < total_steps:
                    if sample_index == 0:
                        print("ENERGYPLUS_FMI_STAGE=first_step", flush=True)
                    else:
                        pass
                    fmu.doStep(
                        currentCommunicationPoint=time_value,
                        communicationStepSize=config.communication_step_seconds,
                    )
                else:
                    pass
            fmu.terminate()
            print("ENERGYPLUS_FMI_STAGE=terminated", flush=True)
            terminated = True
            fmu.freeInstance()
            instance_released = True
        else:
            findings.append("ENERGYPLUS_TO_FMU_FMI1_NULL_COMPONENT")
            diagnostic = "fmiInstantiateSlave returned a null component"
    except (FMICallException, OSError, RuntimeError, ValueError) as runtime_error:
        diagnostic = str(runtime_error)
        findings.append("ENERGYPLUS_TO_FMU_FMI1_RUNTIME_FAILURE")
    finally:
        if instantiated and not instance_released:
            if initialized and not terminated:
                try:
                    fmu.terminate()
                except FMICallException:
                    pass
            else:
                pass
            fmu.freeInstance()
            instance_released = True
        else:
            if not instantiated:
                fmu.freeLibrary()
            else:
                pass
        if extraction_directory.exists():
            shutil.rmtree(extraction_directory)
        else:
            pass

    finite_trace: bool = bool(
        len(time_values) == total_steps + 1
        and len(input_values) == total_steps + 1
        and len(output_values) == total_steps + 1
        and all(math.isfinite(value) for value in time_values)
        and all(math.isfinite(value) for value in input_values)
        and all(math.isfinite(value) for value in output_values)
    )
    input_transition_count: int = 0
    transition_index: int
    for transition_index in range(1, len(input_values)):
        if input_values[transition_index] != input_values[transition_index - 1]:
            input_transition_count += 1
        else:
            pass
    if len(output_values) > 0:
        output_minimum: float | None = min(output_values)
        output_maximum: float | None = max(output_values)
        output_span: float | None = output_maximum - output_minimum
    else:
        output_minimum = None
        output_maximum = None
        output_span = None
    trajectory_passed: bool = bool(
        finite_trace
        and input_transition_count == len(config.input_levels) - 1
        and output_span is not None
        and output_span > 0.01
        and terminated
        and instance_released
        and len(findings) == 0
    )
    if trajectory_passed:
        _write_energyplus_runtime_trace(
            config.trace_path, time_values, input_values, output_values
        )
        status: str = "PASS"
    else:
        if "ENERGYPLUS_TO_FMU_FMI1_RUNTIME_FAILURE" not in findings:
            findings.append("ENERGYPLUS_TO_FMU_FMI1_TRAJECTORY_FAILURE")
        else:
            pass
        status = "COMPLETED_WITH_FINDINGS"
    payload: dict[str, object] = dict(
        schema="veragrid.energyplus-to-fmu-worker/2",
        mode=config.mode.value,
        status=status,
        findings=findings,
        diagnostic=diagnostic,
        lifecycle=dict(
            instantiated=instantiated,
            initialized=initialized,
            terminated=terminated,
            instance_released=instance_released,
        ),
        trajectory=dict(
            trace_name=config.trace_path.name if trajectory_passed else None,
            sample_count=len(time_values),
            total_steps=total_steps,
            communication_step_seconds=config.communication_step_seconds,
            stop_time_seconds=stop_time,
            steps_per_level=config.steps_per_level,
            input_levels=list(config.input_levels),
            input_transition_count=input_transition_count,
            output_minimum_deg_c=output_minimum,
            output_maximum_deg_c=output_maximum,
            output_span_deg_c=output_span,
            finite=finite_trace,
        ),
    )
    return EnergyPlusToFmuWorkerResult(payload)
def _write_energyplus_to_fmu_worker_result(
    result: EnergyPlusToFmuWorkerResult,
    result_path: Path,
) -> None:
    """Write one deterministic worker result.

    :param result: Completed operation outcome.
    :param result_path: Explicit JSON destination.
    :return: None.
    """

    output_file: BinaryIO = result_path.open("wb")
    try:
        encoded_result: bytes = (
            json.dumps(result.payload, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        output_file.write(encoded_result)
    finally:
        output_file.close()


def main() -> int:
    """Parse an explicit request and execute exactly one worker mode.

    :return: Zero after a structured result is written.
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=[item.value for item in EnergyPlusToFmuWorkerMode])
    parser.add_argument("--result-path", required=True, type=Path)
    parser.add_argument("--working-directory", required=True, type=Path)
    parser.add_argument("--cmd-path", required=True, type=Path)
    parser.add_argument("--vsdevcmd-path", required=True, type=Path)
    parser.add_argument("--compiler-path", required=True, type=Path)
    parser.add_argument("--compiler-size-bytes", required=True, type=int)
    parser.add_argument("--compiler-sha256", required=True)
    parser.add_argument("--linker-path", required=True, type=Path)
    parser.add_argument("--linker-size-bytes", required=True, type=int)
    parser.add_argument("--linker-sha256", required=True)
    parser.add_argument("--python-path", required=True, type=Path)
    parser.add_argument("--exporter-path", required=True, type=Path)
    parser.add_argument("--idd-path", required=True, type=Path)
    parser.add_argument("--idf-path", required=True, type=Path)
    parser.add_argument("--epw-path", required=True, type=Path)
    parser.add_argument("--fmu-path", required=True, type=Path)
    parser.add_argument("--trace-path", required=True, type=Path)
    parser.add_argument("--energyplus-directory", required=True, type=Path)
    parser.add_argument("--communication-step-seconds", required=True, type=float)
    parser.add_argument("--steps-per-level", required=True, type=int)
    parser.add_argument("--input-level", required=True, action="append", type=float)
    parser.add_argument("--temporary-directory", required=True, type=Path)
    parser.add_argument("--process-timeout-seconds", required=True, type=float)
    parser.add_argument("--stream-limit-bytes", required=True, type=int)
    arguments: argparse.Namespace = parser.parse_args()
    config: EnergyPlusToFmuWorkerConfig = EnergyPlusToFmuWorkerConfig(
        mode=EnergyPlusToFmuWorkerMode(arguments.mode),
        result_path=arguments.result_path,
        working_directory=arguments.working_directory,
        cmd_path=arguments.cmd_path,
        vsdevcmd_path=arguments.vsdevcmd_path,
        compiler_path=arguments.compiler_path,
        compiler_size_bytes=arguments.compiler_size_bytes,
        compiler_sha256=arguments.compiler_sha256,
        linker_path=arguments.linker_path,
        linker_size_bytes=arguments.linker_size_bytes,
        linker_sha256=arguments.linker_sha256,
        python_path=arguments.python_path,
        exporter_path=arguments.exporter_path,
        idd_path=arguments.idd_path,
        idf_path=arguments.idf_path,
        epw_path=arguments.epw_path,
        fmu_path=arguments.fmu_path,
        trace_path=arguments.trace_path,
        energyplus_directory=arguments.energyplus_directory,
        communication_step_seconds=arguments.communication_step_seconds,
        steps_per_level=arguments.steps_per_level,
        input_levels=tuple(arguments.input_level),
        temporary_directory=arguments.temporary_directory,
        process_timeout_seconds=arguments.process_timeout_seconds,
        stream_limit_bytes=arguments.stream_limit_bytes,
    )
    adjacent_levels_are_distinct: bool = True
    level_index: int
    for level_index in range(1, len(config.input_levels)):
        if config.input_levels[level_index] == config.input_levels[level_index - 1]:
            adjacent_levels_are_distinct = False
        else:
            pass
    scenario_is_valid: bool = bool(
        config.working_directory.is_dir()
        and config.result_path.parent.is_dir()
        and config.trace_path.parent.is_dir()
        and config.energyplus_directory.is_dir()
        and (config.energyplus_directory / "energyplus.exe").is_file()
        and config.epw_path.is_file()
        and config.communication_step_seconds == 900.0
        and config.steps_per_level > 0
        and len(config.input_levels) >= 2
        and len(config.input_levels) * config.steps_per_level
        * config.communication_step_seconds == 86_400.0
        and all(math.isfinite(level) for level in config.input_levels)
        and adjacent_levels_are_distinct
    )
    if scenario_is_valid and config.mode == EnergyPlusToFmuWorkerMode.EXPORT:
        result: EnergyPlusToFmuWorkerResult = _execute_energyplus_export(config)
    else:
        if scenario_is_valid:
            result = _execute_energyplus_runtime_probe(config)
        else:
            raise ValueError("EnergyPlusToFMU worker scenario is invalid")
    _write_energyplus_to_fmu_worker_result(result, config.result_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())










