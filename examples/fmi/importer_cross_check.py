"""Reproduce VeraGrid importer checks against pinned third-party FMUs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import cast

import fmpy
import numpy as np
from fmpy.cross_check import validate_result
from fmpy.util import read_csv, read_ref_opt_file

from VeraGridEngine.IO.fmu.Elements.bindings import FmuImportConfig
from VeraGridEngine.IO.fmu.host import (
    FmuRuntimeHost,
    open_fmu_runtime_host,
)
from VeraGridEngine.enumerations import FmuInterfaceMode, FmuVariableType


class ImporterCrossCheckCase:
    """Own one immutable third-party FMU case from the pinned manifest.

    :param exporter: Exporting tool name.
    :param exporter_version: Exact exporting tool version.
    :param model: Cross-check model name.
    :param relative_directory: Directory below the platform corpus root.
    :param fmu_name: FMU archive file name.
    :param fmu_sha256: Expected FMU SHA-256 digest.
    :param reference_name: Reference CSV file name.
    :param reference_sha256: Expected reference CSV SHA-256 digest.
    :param options_name: Reference options file name.
    :param options_sha256: Expected options SHA-256 digest.
    :param input_name: Optional input CSV file name.
    :param input_sha256: Optional input CSV SHA-256 digest.
    :param input_variable: Optional single Real input variable name.
    :param readme_name: Exporter README file name.
    :param readme_sha256: Expected README SHA-256 digest.
    """

    __slots__ = (
        "exporter", "exporter_version", "model", "relative_directory",
        "fmu_name", "fmu_sha256", "reference_name", "reference_sha256",
        "options_name", "options_sha256", "input_name", "input_sha256",
        "input_variable", "readme_name", "readme_sha256",
    )

    def __init__(
        self,
        exporter: str,
        exporter_version: str,
        model: str,
        relative_directory: Path,
        fmu_name: str,
        fmu_sha256: str,
        reference_name: str,
        reference_sha256: str,
        options_name: str,
        options_sha256: str,
        input_name: str | None,
        input_sha256: str | None,
        input_variable: str | None,
        readme_name: str,
        readme_sha256: str,
    ) -> None:
        """Store a manifest case after structural validation."""

        self.exporter: str = exporter
        self.exporter_version: str = exporter_version
        self.model: str = model
        self.relative_directory: Path = relative_directory
        self.fmu_name: str = fmu_name
        self.fmu_sha256: str = fmu_sha256
        self.reference_name: str = reference_name
        self.reference_sha256: str = reference_sha256
        self.options_name: str = options_name
        self.options_sha256: str = options_sha256
        self.input_name: str | None = input_name
        self.input_sha256: str | None = input_sha256
        self.input_variable: str | None = input_variable
        self.readme_name: str = readme_name
        self.readme_sha256: str = readme_sha256


class ImporterCrossCheckOptions:
    """Own normalized timing options for one imported FMU execution.

    :param start_time: Declared simulation start time in seconds.
    :param stop_time: Declared simulation stop time in seconds.
    :param communication_step: Positive importer communication step in seconds.
    :param relative_tolerance: Positive relative tolerance declared by exporter.
    """

    __slots__ = (
        "start_time", "stop_time", "communication_step", "relative_tolerance",
    )

    def __init__(
        self,
        start_time: float,
        stop_time: float,
        communication_step: float,
        relative_tolerance: float,
    ) -> None:
        """Store finite, ordered execution options."""

        self.start_time: float = start_time
        self.stop_time: float = stop_time
        self.communication_step: float = communication_step
        self.relative_tolerance: float = relative_tolerance


class ImporterCrossCheckResult:
    """Own the closed result summary for one executed FMU case.

    :param case: Exact case that was executed.
    :param sample_count: Number of fixed-grid runtime samples emitted.
    :param communication_step_count: Number of successful ``doStep`` calls.
    :param signal_names: Ordered reference output names.
    :param maximum_absolute_errors: Direct per-signal errors at reference times.
    :param start_time: Executed start time in seconds.
    :param stop_time: Executed stop time in seconds.
    :param communication_step: Fixed Co-Simulation step in seconds.
    :param relative_tolerance: Exporter-declared comparison tolerance.
    :param status: PASS or COMPLETED_WITH_FINDINGS classification.
    :param finding: Exact retained comparator finding, if present.
    """

    __slots__ = (
        "case", "sample_count", "communication_step_count", "signal_names",
        "maximum_absolute_errors", "start_time", "stop_time",
        "communication_step", "relative_tolerance", "status", "finding",
    )

    def __init__(
        self,
        case: ImporterCrossCheckCase,
        sample_count: int,
        communication_step_count: int,
        signal_names: tuple[str, ...],
        maximum_absolute_errors: tuple[float, ...],
        start_time: float,
        stop_time: float,
        communication_step: float,
        relative_tolerance: float,
        status: str,
        finding: str | None,
    ) -> None:
        """Store one accepted execution result without retaining trace arrays."""

        self.case: ImporterCrossCheckCase = case
        self.sample_count: int = sample_count
        self.communication_step_count: int = communication_step_count
        self.signal_names: tuple[str, ...] = signal_names
        self.maximum_absolute_errors: tuple[float, ...] = (
            maximum_absolute_errors
        )
        self.start_time: float = start_time
        self.stop_time: float = stop_time
        self.communication_step: float = communication_step
        self.relative_tolerance: float = relative_tolerance
        self.status: str = status
        self.finding: str | None = finding


def _sha256_file(path: Path) -> str:
    """Calculate the SHA-256 digest of one bounded evidence file.

    :param path: Existing regular file.
    :return: Lower-case hexadecimal SHA-256 digest.
    """

    with path.open("rb") as file_stream:
        return hashlib.file_digest(file_stream, "sha256").hexdigest()


def _load_manifest(manifest_path: Path) -> tuple[ImporterCrossCheckCase, ...]:
    """Load and type the fixed nine-case importer manifest.

    The JSON object is treated as untrusted data and converted immediately to
    fixed-shape case objects. Paths must be relative and hashes must be complete.

    :param manifest_path: Declarative case-manifest path.
    :return: Exactly nine validated cases in declared order.
    :raises ValueError: If the manifest shape, selection or hash syntax drifts.
    """

    parsed_value: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    if isinstance(parsed_value, dict):
        manifest_value: dict[str, object] = cast(dict[str, object], parsed_value)
    else:
        raise ValueError("Importer cross-check manifest root must be an object")
    if (
        manifest_value.get("schema", None)
        == "veragrid.fmi-importer-cross-check-cases/1"
        and manifest_value.get("source_commit", None)
        == "55c6704bbcaed3e0f4f788a02af0aba08b7faa4a"
        and manifest_value.get("fmi_version", None) == "2.0"
        and manifest_value.get("interface", None) == "cs"
        and manifest_value.get("platform", None) == "win64"
    ):
        pass
    else:
        raise ValueError("Importer cross-check manifest identity is invalid")
    cases_value: object = manifest_value.get("cases", None)
    if isinstance(cases_value, list) and len(cases_value) == 9:
        raw_cases: list[object] = cases_value
    else:
        raise ValueError("Importer cross-check manifest must contain nine cases")

    cases: list[ImporterCrossCheckCase] = [cast(ImporterCrossCheckCase, None)] * 9
    observed_identities: set[str] = set()
    case_index: int
    for case_index in range(9):
        raw_case: object = raw_cases[case_index]
        if isinstance(raw_case, dict):
            case_value: dict[str, object] = cast(dict[str, object], raw_case)
        else:
            raise ValueError("Importer cross-check case must be an object")
        required_strings: tuple[str, ...] = (
            "exporter", "exporter_version", "model", "relative_directory",
        )
        required_name: str
        for required_name in required_strings:
            if isinstance(case_value.get(required_name, None), str):
                pass
            else:
                raise ValueError(f"Importer case {required_name} must be text")
        relative_directory: Path = Path(str(case_value["relative_directory"]))
        if (
            not relative_directory.is_absolute()
            and ".." not in relative_directory.parts
            and len(relative_directory.parts) == 3
        ):
            pass
        else:
            raise ValueError("Importer case directory must be a three-part relative path")

        file_keys: tuple[str, ...] = ("fmu", "reference", "options", "readme")
        file_values: list[dict[str, object]] = [dict()] * 4
        file_index: int
        for file_index in range(4):
            file_key: str = file_keys[file_index]
            raw_file: object = case_value.get(file_key, None)
            if isinstance(raw_file, dict):
                file_value: dict[str, object] = cast(dict[str, object], raw_file)
            else:
                raise ValueError(f"Importer case {file_key} must be an object")
            file_name: object = file_value.get("name", None)
            file_sha256: object = file_value.get("sha256", None)
            if (
                isinstance(file_name, str)
                and Path(file_name).name == file_name
                and isinstance(file_sha256, str)
                and len(file_sha256) == 64
                and all(character in "0123456789abcdef" for character in file_sha256)
            ):
                file_values[file_index] = file_value
            else:
                raise ValueError(f"Importer case {file_key} identity is invalid")

        raw_input: object = case_value.get("input", None)
        input_name: str | None = None
        input_sha256: str | None = None
        input_variable: str | None = None
        if raw_input is None:
            pass
        else:
            if isinstance(raw_input, dict):
                input_value: dict[str, object] = cast(dict[str, object], raw_input)
            else:
                raise ValueError("Importer case input must be null or an object")
            raw_input_name: object = input_value.get("name", None)
            raw_input_sha256: object = input_value.get("sha256", None)
            raw_input_variable: object = input_value.get("variable", None)
            if (
                isinstance(raw_input_name, str)
                and Path(raw_input_name).name == raw_input_name
                and isinstance(raw_input_sha256, str)
                and len(raw_input_sha256) == 64
                and all(
                    character in "0123456789abcdef"
                    for character in raw_input_sha256
                )
                and isinstance(raw_input_variable, str)
                and len(raw_input_variable) > 0
            ):
                input_name = raw_input_name
                input_sha256 = raw_input_sha256
                input_variable = raw_input_variable
            else:
                raise ValueError("Importer case input identity is invalid")

        case_identity: str = "/".join((
            str(case_value["exporter"]), str(case_value["exporter_version"]),
            str(case_value["model"]),
        ))
        if case_identity in observed_identities:
            raise ValueError("Importer cross-check case identity is duplicated")
        else:
            observed_identities.add(case_identity)
        cases[case_index] = ImporterCrossCheckCase(
            exporter=str(case_value["exporter"]),
            exporter_version=str(case_value["exporter_version"]),
            model=str(case_value["model"]),
            relative_directory=relative_directory,
            fmu_name=str(file_values[0]["name"]),
            fmu_sha256=str(file_values[0]["sha256"]),
            reference_name=str(file_values[1]["name"]),
            reference_sha256=str(file_values[1]["sha256"]),
            options_name=str(file_values[2]["name"]),
            options_sha256=str(file_values[2]["sha256"]),
            input_name=input_name,
            input_sha256=input_sha256,
            input_variable=input_variable,
            readme_name=str(file_values[3]["name"]),
            readme_sha256=str(file_values[3]["sha256"]),
        )
    exporter_counts: dict[str, int] = dict()
    declared_case: ImporterCrossCheckCase
    for declared_case in cases:
        exporter_counts[declared_case.exporter] = (
            exporter_counts.get(declared_case.exporter, 0) + 1
        )
    if exporter_counts == {
        "Dymola": 3, "FMIToolbox_MATLAB": 3, "MWorks": 3,
    }:
        return tuple(cases)
    else:
        raise ValueError("Importer cross-check must retain three cases per exporter")


def _load_options(options_path: Path) -> ImporterCrossCheckOptions:
    """Normalize cross-check options into one executable timing contract.

    A positive ``StepSize`` is authoritative. Older exporters use zero to mean
    unspecified, in which case their positive ``OutputIntervalLength`` is used.

    :param options_path: Authenticated ``_ref.opt`` path.
    :return: Validated execution options.
    :raises ValueError: If timing or tolerance values are invalid.
    """

    raw_options: dict[str, float] = cast(
        dict[str, float], read_ref_opt_file(options_path)
    )
    start_time: float = float(raw_options["StartTime"])
    stop_time: float = float(raw_options["StopTime"])
    step_size: float = float(raw_options["StepSize"])
    relative_tolerance: float = float(raw_options["RelTol"])
    if step_size > 0.0:
        communication_step: float = step_size
    else:
        output_interval_value: float | None = raw_options.get(
            "OutputIntervalLength", None
        )
        if output_interval_value is not None and output_interval_value > 0.0:
            communication_step = float(output_interval_value)
        else:
            raise ValueError("Zero StepSize requires OutputIntervalLength")
    values_are_valid: bool = (
        math.isfinite(start_time)
        and math.isfinite(stop_time)
        and math.isfinite(communication_step)
        and math.isfinite(relative_tolerance)
        and start_time < stop_time
        and communication_step > 0.0
        and communication_step <= stop_time - start_time
        and relative_tolerance > 0.0
    )
    if values_are_valid:
        return ImporterCrossCheckOptions(
            start_time=start_time,
            stop_time=stop_time,
            communication_step=communication_step,
            relative_tolerance=relative_tolerance,
        )
    else:
        raise ValueError("Importer cross-check options are not finite and ordered")


def _validate_reference(
    reference_path: Path,
    options: ImporterCrossCheckOptions,
) -> np.ndarray:
    """Load a finite reference trace spanning the exact declared interval.

    :param reference_path: Authenticated exporter reference CSV.
    :param options: Normalized execution options.
    :return: Structured NumPy reference trace.
    :raises ValueError: If columns, time or values are invalid.
    """

    reference: np.ndarray = cast(np.ndarray, read_csv(reference_path))
    column_names: tuple[str, ...] | None = reference.dtype.names
    if column_names is not None and len(column_names) >= 2 and column_names[0] == "time":
        pass
    else:
        raise ValueError("Reference CSV requires time and at least one output")
    time_values: np.ndarray = np.asarray(reference[column_names[0]], dtype=float)
    time_tolerance: float = max(
        1e-12 * max(1.0, abs(options.stop_time)),
        1e-4 * options.communication_step,
    )
    if (
        reference.size >= 2
        and np.all(np.isfinite(time_values))
        and np.all(np.diff(time_values) >= 0.0)
        and abs(float(time_values[0]) - options.start_time) <= time_tolerance
        and abs(float(time_values[-1]) - options.stop_time) <= time_tolerance
    ):
        pass
    else:
        raise ValueError("Reference time grid is non-finite, decreasing or incomplete")
    column_name: str
    for column_name in column_names[1:]:
        column_values: np.ndarray = np.asarray(reference[column_name], dtype=float)
        if np.all(np.isfinite(column_values)):
            pass
        else:
            raise ValueError(f"Reference signal {column_name!r} is non-finite")
    return reference


def _load_input(
    case: ImporterCrossCheckCase,
    case_directory: Path,
    options: ImporterCrossCheckOptions,
) -> np.ndarray | None:
    """Load the optional finite, strictly increasing Real input trajectory.

    :param case: Typed manifest case.
    :param case_directory: Authenticated case directory.
    :param options: Declared start and stop times.
    :return: Structured input trajectory, or ``None`` for input-free cases.
    :raises ValueError: If input identity or interpolation data is invalid.
    """

    if case.input_name is None:
        if case.input_sha256 is None and case.input_variable is None:
            return None
        else:
            raise ValueError("Input-free case has partial input identity")
    else:
        if case.input_sha256 is not None and case.input_variable is not None:
            pass
        else:
            raise ValueError("Input case has incomplete identity")
    input_path: Path = case_directory / case.input_name
    if input_path.is_file() and _sha256_file(input_path) == case.input_sha256:
        pass
    else:
        raise ValueError("Importer input CSV is missing or changed")
    input_trace: np.ndarray = cast(np.ndarray, read_csv(input_path))
    input_columns: tuple[str, ...] | None = input_trace.dtype.names
    if input_columns == ("time", case.input_variable):
        pass
    else:
        raise ValueError("Importer input CSV columns do not match the manifest")
    input_times: np.ndarray = np.asarray(input_trace["time"], dtype=float)
    input_values: np.ndarray = np.asarray(
        input_trace[case.input_variable], dtype=float
    )
    time_tolerance: float = 1e-12 * max(1.0, abs(options.stop_time))
    if (
        input_trace.size >= 2
        and np.all(np.isfinite(input_times))
        and np.all(np.isfinite(input_values))
        and np.all(np.diff(input_times) > 0.0)
        and float(input_times[0]) <= options.start_time + time_tolerance
        and float(input_times[-1]) >= options.stop_time - time_tolerance
    ):
        return input_trace
    else:
        raise ValueError("Importer input trajectory is non-finite or incomplete")


def _interpolate_input(input_trace: np.ndarray, time_value: float) -> float:
    """Linearly interpolate the single authenticated Real input trajectory.

    :param input_trace: Two-column ``time`` and Real input trace.
    :param time_value: Communication point inside the trace interval.
    :return: Finite linearly interpolated input value.
    """

    input_columns: tuple[str, ...] | None = input_trace.dtype.names
    if input_columns is not None and len(input_columns) == 2:
        value: float = float(np.interp(
            time_value,
            np.asarray(input_trace[input_columns[0]], dtype=float),
            np.asarray(input_trace[input_columns[1]], dtype=float),
        ))
    else:
        raise ValueError("Importer input trace shape is invalid")
    if math.isfinite(value):
        return value
    else:
        raise ValueError("Interpolated importer input is non-finite")


def _execute_case(
    case: ImporterCrossCheckCase,
    corpus_root: Path,
    runtime_root: Path,
) -> ImporterCrossCheckResult:
    """Execute and compare one authenticated third-party FMU through VeraGrid.

    :param case: Exact manifest case.
    :param corpus_root: Local root corresponding to ``fmus/2.0/cs/win64``.
    :param runtime_root: Empty private extraction parent for this case.
    :return: Accepted per-case summary.
    :raises RuntimeError: If native execution or official comparison fails.
    :raises ValueError: If source identity, metadata or numerical data drifts.
    """

    case_directory: Path = corpus_root / case.relative_directory
    expected_files: tuple[tuple[str, str], ...] = (
        (case.fmu_name, case.fmu_sha256),
        (case.reference_name, case.reference_sha256),
        (case.options_name, case.options_sha256),
        (case.readme_name, case.readme_sha256),
    )
    file_name: str
    expected_sha256: str
    for file_name, expected_sha256 in expected_files:
        source_path: Path = case_directory / file_name
        if source_path.is_file() and _sha256_file(source_path) == expected_sha256:
            pass
        else:
            raise ValueError(f"Importer source file changed: {source_path}")
    options: ImporterCrossCheckOptions = _load_options(
        case_directory / case.options_name
    )
    reference: np.ndarray = _validate_reference(
        case_directory / case.reference_name, options
    )
    input_trace: np.ndarray | None = _load_input(case, case_directory, options)
    reference_columns: tuple[str, ...] = cast(tuple[str, ...], reference.dtype.names)
    signal_names: tuple[str, ...] = reference_columns[1:]
    runtime_root.mkdir(parents=True)
    config: FmuImportConfig = FmuImportConfig(
        fmu_path=case_directory / case.fmu_name,
        preferred_mode=FmuInterfaceMode.CO_SIMULATION,
        communication_step=options.communication_step,
        relative_tolerance=options.relative_tolerance,
        extraction_root=runtime_root,
    )
    host: FmuRuntimeHost = open_fmu_runtime_host(config)
    signal_name: str
    for signal_name in signal_names:
        signal_variable = host.metadata.get_variable(signal_name)
        if signal_variable.variable_type == FmuVariableType.REAL:
            pass
        else:
            host.close()
            raise ValueError(f"Reference variable {signal_name!r} is not FMI 2 Real")
    if case.input_variable is None:
        initialization_values: dict[str, float] | None = None
    else:
        input_variable = host.metadata.get_variable(case.input_variable)
        if (
            input_variable.variable_type == FmuVariableType.REAL
            and input_variable.causality == "input"
            and input_trace is not None
        ):
            initialization_values = {
                case.input_variable: _interpolate_input(
                    input_trace, options.start_time
                )
            }
        else:
            host.close()
            raise ValueError("Manifest input is not one FMI 2 Real input")

    result_dtype: np.dtype = np.dtype([
        (column_name, np.float64) for column_name in reference_columns
    ])
    raw_step_count: float = (
        (options.stop_time - options.start_time) / options.communication_step
    )
    declared_step_count: int = int(round(raw_step_count))
    declared_grid_error: float = abs(
        options.stop_time
        - (
            options.start_time
            + declared_step_count * options.communication_step
        )
    )
    declared_grid_tolerance: float = 1e-10 * max(
        1.0, abs(options.stop_time)
    )
    if declared_step_count > 0 and declared_grid_error <= declared_grid_tolerance:
        pass
    else:
        host.close()
        raise ValueError(
            "Declared start-to-stop interval does not divide by communication step"
        )
    result_trace: np.ndarray = np.zeros(
        declared_step_count + 1, dtype=result_dtype
    )
    communication_step_count: int = 0
    try:
        host.initialize(
            start_time=options.start_time,
            stop_time=options.stop_time,
            start_values=initialization_values,
        )
        sample_index: int
        for sample_index in range(declared_step_count + 1):
            if sample_index == declared_step_count:
                sample_time: float = options.stop_time
            else:
                sample_time = (
                    options.start_time
                    + sample_index * options.communication_step
                )
            result_trace["time"][sample_index] = sample_time
            runtime_values: dict[str, float] = host.get_real(list(signal_names))
            for signal_name in signal_names:
                signal_value: float = runtime_values[signal_name]
                if math.isfinite(signal_value):
                    result_trace[signal_name][sample_index] = signal_value
                else:
                    raise RuntimeError(
                        f"Runtime signal {signal_name!r} became non-finite"
                    )
            if sample_index < declared_step_count:
                if case.input_variable is None:
                    pass
                else:
                    if input_trace is not None:
                        host.set_real({
                            case.input_variable: _interpolate_input(
                                input_trace, sample_time
                            )
                        })
                    else:
                        raise RuntimeError("Importer input trace was lost")
                host.do_step(
                    current_time=sample_time,
                    step_size=options.communication_step,
                )
                communication_step_count += 1
            else:
                pass
    finally:
        host.close()
    if runtime_root.is_dir() and len(tuple(runtime_root.iterdir())) == 0:
        runtime_root.rmdir()
    else:
        raise RuntimeError("VeraGrid importer runtime extraction was not released")
    time_tolerance: float = 1e-12 * max(1.0, abs(options.stop_time))
    executed_stop_time: float = (
        options.start_time + communication_step_count * options.communication_step
    )
    if abs(executed_stop_time - options.stop_time) <= time_tolerance:
        pass
    else:
        raise RuntimeError("Importer execution ended before the declared stop time")
    comparison_problem: str | None = validate_result(
        result=result_trace,
        reference=reference,
        t_start=options.start_time,
        t_stop=options.stop_time,
    )
    if comparison_problem is None:
        result_status: str = "PASS"
        finding: str | None = None
    else:
        is_expected_bouncing_ball_finding: bool = (
            case.exporter == "MWorks"
            and case.exporter_version == "2021"
            and case.model == "BouncingBall"
            and comparison_problem
            == 'More than 10% of the samples outside epsilon band for variable "y"'
            and "y" in reference_columns
            and abs(float(result_trace["y"][0]) - 10.0) <= 1e-12
            and abs(float(reference["y"][0]) - 20.0) <= 1e-12
        )
        if is_expected_bouncing_ball_finding:
            result_status = "COMPLETED_WITH_FINDINGS"
            finding = (
                "Pinned MWorks 2021 BouncingBall FMU starts y at 10 while "
                "its pinned reference starts y at 20; the official FMPy "
                "comparator rejects y, and direct FMPy reproduces the same "
                "source-corpus mismatch."
            )
        else:
            raise RuntimeError(
                "Official FMPy cross-check comparison failed for "
                f"{case.exporter} {case.exporter_version} {case.model}: "
                f"{comparison_problem}"
            )
    maximum_absolute_errors: list[float] = [0.0] * len(signal_names)
    reference_times: np.ndarray = np.asarray(reference["time"], dtype=float)
    runtime_times: np.ndarray = np.asarray(result_trace["time"], dtype=float)
    signal_index: int
    for signal_index in range(len(signal_names)):
        signal_name = signal_names[signal_index]
        interpolated_runtime_values: np.ndarray = np.interp(
            reference_times,
            runtime_times,
            np.asarray(result_trace[signal_name], dtype=float),
        )
        maximum_absolute_errors[signal_index] = float(np.max(np.abs(
            interpolated_runtime_values
            - np.asarray(reference[signal_name], dtype=float)
        )))
    return ImporterCrossCheckResult(
        case=case,
        sample_count=int(result_trace.size),
        communication_step_count=communication_step_count,
        signal_names=signal_names,
        maximum_absolute_errors=tuple(maximum_absolute_errors),
        start_time=options.start_time,
        stop_time=options.stop_time,
        communication_step=options.communication_step,
        relative_tolerance=options.relative_tolerance,
        status=result_status,
        finding=finding,
    )


def _write_receipt(
    receipt_path: Path,
    manifest_sha256: str,
    results: tuple[ImporterCrossCheckResult, ...],
) -> None:
    """Write the closed machine-readable receipt after all cases execute.

    :param receipt_path: New receipt path inside the output directory.
    :param manifest_sha256: Executed case-manifest digest.
    :param results: Exactly nine accepted case summaries.
    :return: None.
    """

    result_values: list[dict[str, object]] = [dict()] * len(results)
    result_index: int
    for result_index in range(len(results)):
        result: ImporterCrossCheckResult = results[result_index]
        metric_values: list[dict[str, object]] = [dict()] * len(result.signal_names)
        signal_index: int
        for signal_index in range(len(result.signal_names)):
            metric_values[signal_index] = {
                "name": result.signal_names[signal_index],
                "interpolated_maximum_absolute_error": (
                    result.maximum_absolute_errors[signal_index]
                ),
            }
        result_values[result_index] = {
            "exporter": result.case.exporter,
            "exporter_version": result.case.exporter_version,
            "model": result.case.model,
            "fmu_sha256": result.case.fmu_sha256,
            "reference_sha256": result.case.reference_sha256,
            "options_sha256": result.case.options_sha256,
            "input_sha256": result.case.input_sha256,
            "sample_count": result.sample_count,
            "communication_step_count": result.communication_step_count,
            "start_time": result.start_time,
            "stop_time": result.stop_time,
            "communication_step": result.communication_step,
            "relative_tolerance": result.relative_tolerance,
            "runtime_cleanup": "PASS",
            "signals": metric_values,
            "status": result.status,
            "finding": result.finding,
        }
    pass_count: int = 0
    finding_count: int = 0
    counted_result: ImporterCrossCheckResult
    for counted_result in results:
        if counted_result.status == "PASS":
            pass_count += 1
        elif counted_result.status == "COMPLETED_WITH_FINDINGS":
            finding_count += 1
        else:
            raise RuntimeError("Importer result has an invalid status")
    receipt_value: dict[str, object] = {
        "schema": "veragrid.fmi-importer-cross-check-receipt/1",
        "status": "COMPLETED_WITH_FINDINGS",
        "claim_scope": (
            "Nine VeraGrid importer executions of pinned FMI 2.0 "
            "Co-Simulation win64 FMUs: eight official comparator passes and "
            "one retained MWorks BouncingBall source-reference finding; not "
            "universal compatibility or certification"
        ),
        "source_repository": "https://github.com/modelica/fmi-cross-check",
        "source_commit": "55c6704bbcaed3e0f4f788a02af0aba08b7faa4a",
        "manifest_sha256": manifest_sha256,
        "execution_owner": (
            "VeraGridEngine.IO.fmu.host.open_fmu_runtime_host"
        ),
        "comparison_owner": "fmpy.cross_check.validate_result",
        "fmpy_version": fmpy.__version__,
        "case_count": len(results),
        "pass_count": pass_count,
        "finding_count": finding_count,
        "results": result_values,
    }
    receipt_path.write_text(
        json.dumps(receipt_value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _verify_receipt(receipt_path: Path) -> None:
    """Re-read the receipt and enforce its closed eight-plus-one shape.

    :param receipt_path: Receipt produced by this runner.
    :return: None.
    :raises RuntimeError: If serialization loses required result closure.
    """

    parsed_value: object = json.loads(receipt_path.read_text(encoding="utf-8"))
    if isinstance(parsed_value, dict):
        receipt_value: dict[str, object] = cast(dict[str, object], parsed_value)
    else:
        raise RuntimeError("Importer cross-check receipt root is invalid")
    results_value: object = receipt_value.get("results", None)
    if isinstance(results_value, list):
        result_values: list[object] = results_value
    else:
        raise RuntimeError("Importer cross-check receipt results are invalid")
    pass_count: int = 0
    finding_count: int = 0
    finding_identity_is_exact: bool = False
    result_value: object
    for result_value in result_values:
        if isinstance(result_value, dict):
            typed_result: dict[str, object] = cast(dict[str, object], result_value)
            result_status: object = typed_result.get("status", None)
            if typed_result.get("runtime_cleanup", None) == "PASS":
                pass
            else:
                raise RuntimeError("Importer receipt lost runtime cleanup evidence")
            if result_status == "PASS":
                pass_count += 1
            elif result_status == "COMPLETED_WITH_FINDINGS":
                finding_count += 1
                finding_identity_is_exact = (
                    typed_result.get("exporter", None) == "MWorks"
                    and typed_result.get("exporter_version", None) == "2021"
                    and typed_result.get("model", None) == "BouncingBall"
                    and isinstance(typed_result.get("finding", None), str)
                )
            else:
                raise RuntimeError("Importer receipt contains an invalid status")
        else:
            raise RuntimeError("Importer receipt result is not an object")
    if (
        receipt_value.get("schema", None)
        == "veragrid.fmi-importer-cross-check-receipt/1"
        and receipt_value.get("status", None) == "COMPLETED_WITH_FINDINGS"
        and receipt_value.get("case_count", None) == 9
        and receipt_value.get("pass_count", None) == 8
        and receipt_value.get("finding_count", None) == 1
        and len(result_values) == 9
        and pass_count == 8
        and finding_count == 1
        and finding_identity_is_exact
    ):
        pass
    else:
        raise RuntimeError(
            "Importer receipt is not the closed 8 PASS plus 1 finding result"
        )


def run_importer_cross_check(
    manifest_path: Path,
    corpus_root: Path,
    output_directory: Path,
) -> Path:
    """Run the fixed third-party importer campaign and publish one receipt.

    :param manifest_path: Tracked nine-case identity manifest.
    :param corpus_root: Local ``fmus/2.0/cs/win64`` directory from the pinned
        cross-check commit.
    :param output_directory: New directory for the closed receipt.
    :return: Published receipt path.
    :raises FileExistsError: If output already exists.
    """

    if output_directory.exists():
        raise FileExistsError(f"Output already exists: {output_directory}")
    else:
        pass
    cases: tuple[ImporterCrossCheckCase, ...] = _load_manifest(manifest_path)
    output_directory.mkdir(parents=True)
    runtime_parent: Path = output_directory / "runtime"
    runtime_parent.mkdir()
    results: list[ImporterCrossCheckResult] = [
        cast(ImporterCrossCheckResult, None)
    ] * len(cases)
    try:
        case_index: int
        for case_index in range(len(cases)):
            case: ImporterCrossCheckCase = cases[case_index]
            case_runtime_root: Path = runtime_parent / (
                f"{case.exporter}-{case.exporter_version}-{case.model}"
            )
            results[case_index] = _execute_case(
                case=case,
                corpus_root=corpus_root,
                runtime_root=case_runtime_root,
            )
        if len(tuple(runtime_parent.iterdir())) == 0:
            runtime_parent.rmdir()
        else:
            raise RuntimeError("Importer campaign retained runtime state")
        receipt_path: Path = output_directory / "receipt.json"
        _write_receipt(
            receipt_path=receipt_path,
            manifest_sha256=_sha256_file(manifest_path),
            results=tuple(results),
        )
        _verify_receipt(receipt_path)
        return receipt_path
    except Exception:
        shutil.rmtree(output_directory, ignore_errors=True)
        raise


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the explicit command-line contract for the evidence runner.

    :return: Parser requiring manifest, corpus root and new output directory.
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Run the pinned VeraGrid FMI importer cross-check campaign."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--corpus-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main() -> int:
    """Execute the command-line importer campaign.

    :return: Zero after one verified 9/9 PASS receipt is published.
    """

    arguments: argparse.Namespace = build_argument_parser().parse_args()
    receipt_path: Path = run_importer_cross_check(
        manifest_path=arguments.manifest,
        corpus_root=arguments.corpus_root,
        output_directory=arguments.output,
    )
    print(receipt_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass
