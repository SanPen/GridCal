# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Execute and verify the isolated PathSim-FMI reference comparison."""
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
from matplotlib.colors import ListedColormap
from matplotlib.figure import Figure
import matplotlib.image as mpimg
import numpy as np

from VeraGridEngine.enumerations import FmuInterfaceMode
from examples.fmi.evidence_identity import (
    path_is_link_or_reparse_point,
    read_regular_tree_identity,
    verify_regular_file_identity,
)
from examples.fmi.reference_fmu import (
    ReferenceFmuCatalog,
    ReferenceFmuCase,
    ReferenceFmuEventOracle,
    ValidatedReferenceFmuAsset,
    load_reference_fmu_catalog,
)
from examples.fmi.reference_fmu_execution import (
    ReferenceFmuTrace,
    build_reference_fmu_regular_trace,
    read_reference_fmu_trace_csv,
)


class PathSimCellStatus(str, Enum):
    """Terminal classifications for one PathSim comparison cell."""

    PASS = "PASS"
    COMPLETED_WITH_FINDINGS = "COMPLETED_WITH_FINDINGS"


class PathSimFindingKind(str, Enum):
    """Known external limitations preserved by the PathSim benchmark."""

    UNSUPPORTED_SCALAR_OUTPUT = "unsupported_scalar_output"


class PathSimComparisonConfig:
    """Own every explicit input and bound of one PathSim comparison."""

    __slots__ = (
        "output_directory",
        "source_branch",
        "source_revision",
        "source_tree_sha256",
        "runtime_root",
        "runtime_entry_count",
        "runtime_regular_bytes",
        "runtime_tree_sha256",
        "python_executable_path",
        "python_executable_size_bytes",
        "python_executable_sha256",
        "system_root_path",
        "processor_architecture",
        "catalog_path",
        "catalog_size_bytes",
        "catalog_sha256",
        "archive_path",
        "archive_size_bytes",
        "archive_sha256",
        "fmu_paths",
        "reference_manifest_path",
        "reference_manifest_size_bytes",
        "reference_manifest_sha256",
        "worker_path",
        "worker_size_bytes",
        "worker_sha256",
        "process_timeout_seconds",
        "stream_limit_bytes",
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
        python_executable_path: Path,
        python_executable_size_bytes: int,
        python_executable_sha256: str,
        system_root_path: Path,
        processor_architecture: str,
        catalog_path: Path,
        catalog_size_bytes: int,
        catalog_sha256: str,
        archive_path: Path,
        archive_size_bytes: int,
        archive_sha256: str,
        fmu_paths: tuple[Path, Path, Path, Path],
        reference_manifest_path: Path,
        reference_manifest_size_bytes: int,
        reference_manifest_sha256: str,
        worker_path: Path,
        worker_size_bytes: int,
        worker_sha256: str,
        process_timeout_seconds: float,
        stream_limit_bytes: int,
    ) -> None:
        """Validate and retain one closed PathSim comparison request.

        :param output_directory: New package directory published atomically.
        :param source_branch: Source branch recorded in the package.
        :param source_revision: Forty-character source commit identity.
        :param source_tree_sha256: Source-tree evidence digest.
        :param runtime_root: Exact external Python environment root.
        :param runtime_entry_count: Expected regular-file count of the runtime.
        :param runtime_regular_bytes: Expected aggregate runtime file bytes.
        :param runtime_tree_sha256: Expected path-size-content runtime digest.
        :param python_executable_path: Absolute Python executable for every cell.
        :param python_executable_size_bytes: Expected Python executable size.
        :param python_executable_sha256: Expected Python executable digest.
        :param system_root_path: Explicit Windows system root exposed to children.
        :param processor_architecture: Explicit Windows architecture exposed to children.
        :param catalog_path: Sealed Reference FMU catalog.
        :param catalog_size_bytes: Exact catalog byte count.
        :param catalog_sha256: Exact catalog digest.
        :param archive_path: Official Reference FMUs release archive.
        :param archive_size_bytes: Exact release archive byte count.
        :param archive_sha256: Exact release archive digest.
        :param fmu_paths: Four extracted FMUs in sealed catalog order.
        :param reference_manifest_path: Accepted FMPy execution manifest.
        :param reference_manifest_size_bytes: Exact manifest byte count.
        :param reference_manifest_sha256: Exact manifest digest.
        :param worker_path: Repository-owned single-cell worker.
        :param worker_size_bytes: Exact worker byte count.
        :param worker_sha256: Exact worker digest.
        :param process_timeout_seconds: Hard deadline for each child process.
        :param stream_limit_bytes: Independent stdout and stderr size bound.
        :return: None.
        """

        explicit_paths: tuple[Path, ...] = (
            output_directory,
            runtime_root,
            python_executable_path,
            system_root_path,
            catalog_path,
            archive_path,
            fmu_paths[0],
            fmu_paths[1],
            fmu_paths[2],
            fmu_paths[3],
            reference_manifest_path,
            worker_path,
        )
        sizes: tuple[int, ...] = (
            runtime_entry_count,
            runtime_regular_bytes,
            python_executable_size_bytes,
            catalog_size_bytes,
            archive_size_bytes,
            reference_manifest_size_bytes,
            worker_size_bytes,
            stream_limit_bytes,
        )
        digests: tuple[str, ...] = (
            source_tree_sha256,
            runtime_tree_sha256,
            python_executable_sha256,
            catalog_sha256,
            archive_sha256,
            reference_manifest_sha256,
            worker_sha256,
        )
        values_are_valid: bool = bool(
            isinstance(fmu_paths, tuple)
            and len(fmu_paths) == 4
            and all(
                isinstance(path_value, Path) and path_value.is_absolute()
                for path_value in explicit_paths
            )
            and all(
                isinstance(size_value, int)
                and not isinstance(size_value, bool)
                and size_value > 0
                for size_value in sizes
            )
            and all(
                re.fullmatch(r"[0-9a-f]{64}", digest) is not None
                for digest in digests
            )
            and isinstance(source_branch, str)
            and bool(source_branch)
            and re.fullmatch(r"[0-9a-f]{40}", source_revision) is not None
            and runtime_entry_count == 13_024
            and runtime_regular_bytes == 428_818_054
            and runtime_tree_sha256
            == "15899e333049b92e3fd8de68bc63492e1b5ea523c08097301df12e5e1aed8e90"
            and python_executable_size_bytes == 274_712
            and python_executable_sha256
            == "21bb438c0d4a6f1f164b9a646f6ee000340185e5871180aec06db8d3f07c0082"
            and processor_architecture == "AMD64"
            and archive_size_bytes == 3_390_239
            and archive_sha256 == "62babca76b9c23a51c3096be4bb5930ff8b4388659056be3c0c4ef7a3aeb5403"
            and reference_manifest_size_bytes == 26_321
            and reference_manifest_sha256
            == "7c0dce184104e6ff78bb38cb234c7159cc33fa2ed352ec9c7955d787d8d27c78"
            and float(process_timeout_seconds) == 120.0
            and stream_limit_bytes == 1_048_576
        )
        if values_are_valid:
            pass
        else:
            raise ValueError("PathSim comparison configuration is invalid")
        self.output_directory: Path = output_directory
        self.source_branch: str = source_branch
        self.source_revision: str = source_revision
        self.source_tree_sha256: str = source_tree_sha256
        self.runtime_root: Path = runtime_root
        self.runtime_entry_count: int = runtime_entry_count
        self.runtime_regular_bytes: int = runtime_regular_bytes
        self.runtime_tree_sha256: str = runtime_tree_sha256
        self.python_executable_path: Path = python_executable_path
        self.python_executable_size_bytes: int = python_executable_size_bytes
        self.python_executable_sha256: str = python_executable_sha256
        self.system_root_path: Path = system_root_path
        self.processor_architecture: str = processor_architecture
        self.catalog_path: Path = catalog_path
        self.catalog_size_bytes: int = catalog_size_bytes
        self.catalog_sha256: str = catalog_sha256
        self.archive_path: Path = archive_path
        self.archive_size_bytes: int = archive_size_bytes
        self.archive_sha256: str = archive_sha256
        self.fmu_paths: tuple[Path, Path, Path, Path] = fmu_paths
        self.reference_manifest_path: Path = reference_manifest_path
        self.reference_manifest_size_bytes: int = reference_manifest_size_bytes
        self.reference_manifest_sha256: str = reference_manifest_sha256
        self.worker_path: Path = worker_path
        self.worker_size_bytes: int = worker_size_bytes
        self.worker_sha256: str = worker_sha256
        self.process_timeout_seconds: float = float(process_timeout_seconds)
        self.stream_limit_bytes: int = stream_limit_bytes


class PathSimProcessResult:
    """Own the bounded process evidence for one comparison cell."""

    __slots__ = (
        "arguments",
        "return_code",
        "elapsed_seconds",
        "stdout_size_bytes",
        "stdout_sha256",
        "stderr_size_bytes",
        "stderr_sha256",
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
        """Validate and retain one finished child-process observation.

        :param arguments: Exact shell-free process argument vector.
        :param return_code: Observed process exit code.
        :param elapsed_seconds: Monotonic wall time consumed by the process.
        :param stdout_size_bytes: Retained standard-output byte count.
        :param stdout_sha256: Retained standard-output digest.
        :param stderr_size_bytes: Retained standard-error byte count.
        :param stderr_sha256: Retained standard-error digest.
        :return: None.
        """

        values_are_valid: bool = bool(
            isinstance(arguments, tuple)
            and len(arguments) >= 4
            and all(isinstance(argument, str) for argument in arguments)
            and isinstance(return_code, int)
            and not isinstance(return_code, bool)
            and isinstance(elapsed_seconds, (int, float))
            and math.isfinite(float(elapsed_seconds))
            and float(elapsed_seconds) >= 0.0
            and isinstance(stdout_size_bytes, int)
            and stdout_size_bytes >= 0
            and isinstance(stderr_size_bytes, int)
            and stderr_size_bytes >= 0
            and re.fullmatch(r"[0-9a-f]{64}", stdout_sha256) is not None
            and re.fullmatch(r"[0-9a-f]{64}", stderr_sha256) is not None
        )
        if values_are_valid:
            pass
        else:
            raise ValueError("PathSim process result is invalid")
        self.arguments: tuple[str, ...] = arguments
        self.return_code: int = return_code
        self.elapsed_seconds: float = float(elapsed_seconds)
        self.stdout_size_bytes: int = stdout_size_bytes
        self.stdout_sha256: str = stdout_sha256
        self.stderr_size_bytes: int = stderr_size_bytes
        self.stderr_sha256: str = stderr_sha256


class PathSimWorkerResult:
    """Own the strictly parsed declarative result of one worker."""

    __slots__ = (
        "status",
        "python_version",
        "pathsim_version",
        "pathsim_fmi_version",
        "fmpy_version",
        "sample_count",
        "event_times_seconds",
        "finding_kind",
        "fmi_function",
        "fmi_status",
    )

    def __init__(
        self,
        status: PathSimCellStatus,
        python_version: str,
        pathsim_version: str,
        pathsim_fmi_version: str,
        fmpy_version: str,
        sample_count: int,
        event_times_seconds: np.ndarray,
        finding_kind: PathSimFindingKind | None,
        fmi_function: str | None,
        fmi_status: int | None,
    ) -> None:
        """Validate and retain one worker result without dynamic state.

        :param status: Passing or completed-with-findings classification.
        :param python_version: Python version observed inside the child.
        :param pathsim_version: PathSim version observed inside the child.
        :param pathsim_fmi_version: PathSim-FMI version observed inside the child.
        :param fmpy_version: FMPy version observed inside the child.
        :param sample_count: Number of samples written by the worker.
        :param event_times_seconds: Native public event times from the worker.
        :param finding_kind: Exact known limitation, when present.
        :param fmi_function: Native FMI function attached to a finding.
        :param fmi_status: Native FMI status attached to a finding.
        :return: None.
        """

        versions_are_valid: bool = bool(
            python_version == "3.11.9"
            and pathsim_version == "0.25.0"
            and pathsim_fmi_version == "0.1.1"
            and fmpy_version == "0.3.31"
        )
        common_values_are_valid: bool = bool(
            isinstance(status, PathSimCellStatus)
            and isinstance(sample_count, int)
            and not isinstance(sample_count, bool)
            and sample_count >= 0
            and isinstance(event_times_seconds, np.ndarray)
            and event_times_seconds.ndim == 1
            and np.all(np.isfinite(event_times_seconds))
        )
        pass_values_are_valid: bool = bool(
            status == PathSimCellStatus.PASS
            and sample_count > 0
            and finding_kind is None
            and fmi_function is None
            and fmi_status is None
        )
        finding_values_are_valid: bool = bool(
            status == PathSimCellStatus.COMPLETED_WITH_FINDINGS
            and sample_count == 0
            and event_times_seconds.size == 0
            and finding_kind == PathSimFindingKind.UNSUPPORTED_SCALAR_OUTPUT
            and isinstance(fmi_function, str)
            and bool(fmi_function)
            and isinstance(fmi_status, int)
            and not isinstance(fmi_status, bool)
        )
        result_is_valid: bool = bool(
            versions_are_valid
            and common_values_are_valid
            and (pass_values_are_valid or finding_values_are_valid)
        )
        if result_is_valid:
            pass
        else:
            raise ValueError("PathSim worker result does not match its closed schema")
        self.status: PathSimCellStatus = status
        self.python_version: str = python_version
        self.pathsim_version: str = pathsim_version
        self.pathsim_fmi_version: str = pathsim_fmi_version
        self.fmpy_version: str = fmpy_version
        self.sample_count: int = sample_count
        self.event_times_seconds: np.ndarray = np.asarray(
            event_times_seconds,
            dtype=np.float64,
        ).copy()
        self.finding_kind: PathSimFindingKind | None = finding_kind
        self.fmi_function: str | None = fmi_function
        self.fmi_status: int | None = fmi_status


class PathSimCellResult:
    """Own evaluated evidence for one ordered PathSim matrix cell."""

    __slots__ = (
        "cell_index",
        "cell_id",
        "case",
        "interface_mode",
        "status",
        "finding_kind",
        "raw_result_path",
        "stdout_path",
        "stderr_path",
        "trace_path",
        "reference_trace_path",
        "sample_count",
        "event_times_seconds",
        "maximum_absolute_error",
        "rms_absolute_error",
        "maximum_event_time_error_seconds",
        "fmi_function",
        "fmi_status",
        "trace",
        "reference_trace",
        "process_result",
    )

    def __init__(
        self,
        cell_index: int,
        cell_id: str,
        case: ReferenceFmuCase,
        interface_mode: FmuInterfaceMode,
        status: PathSimCellStatus,
        finding_kind: PathSimFindingKind | None,
        raw_result_path: Path,
        stdout_path: Path,
        stderr_path: Path,
        trace_path: Path | None,
        reference_trace_path: Path,
        sample_count: int,
        event_times_seconds: np.ndarray,
        maximum_absolute_error: float | None,
        rms_absolute_error: float | None,
        maximum_event_time_error_seconds: float | None,
        fmi_function: str | None,
        fmi_status: int | None,
        trace: ReferenceFmuTrace | None,
        reference_trace: ReferenceFmuTrace,
        process_result: PathSimProcessResult,
    ) -> None:
        """Retain one fully evaluated cell for publication and rendering.

        :param cell_index: Zero-based canonical matrix position.
        :param cell_id: Stable PathSim cell identifier.
        :param case: Sealed Reference FMU case.
        :param interface_mode: FMI interface exercised by the cell.
        :param status: Passing or completed-with-findings outcome.
        :param finding_kind: Exact known external limitation, when present.
        :param raw_result_path: Worker result relative to the staging package.
        :param stdout_path: Retained standard-output relative path.
        :param stderr_path: Retained standard-error relative path.
        :param trace_path: Retained PathSim trace relative path, when successful.
        :param reference_trace_path: Accepted FMPy trace absolute path.
        :param sample_count: Number of PathSim samples.
        :param event_times_seconds: Retained native event timestamps.
        :param maximum_absolute_error: Maximum value error, when evaluated.
        :param rms_absolute_error: RMS value error, when evaluated.
        :param maximum_event_time_error_seconds: Maximum event-center error.
        :param fmi_function: Failing FMI function for a finding.
        :param fmi_status: Failing FMI status for a finding.
        :param trace: Parsed PathSim trace, when successful.
        :param reference_trace: Parsed accepted FMPy trace.
        :param process_result: Bounded child-process evidence.
        :return: None.
        """

        common_values_are_valid: bool = bool(
            isinstance(cell_index, int)
            and not isinstance(cell_index, bool)
            and 0 <= cell_index < 8
            and isinstance(cell_id, str)
            and bool(cell_id)
            and isinstance(case, ReferenceFmuCase)
            and isinstance(interface_mode, FmuInterfaceMode)
            and isinstance(status, PathSimCellStatus)
            and isinstance(raw_result_path, Path)
            and isinstance(stdout_path, Path)
            and isinstance(stderr_path, Path)
            and isinstance(reference_trace_path, Path)
            and isinstance(sample_count, int)
            and sample_count >= 0
            and isinstance(event_times_seconds, np.ndarray)
            and isinstance(reference_trace, ReferenceFmuTrace)
            and isinstance(process_result, PathSimProcessResult)
        )
        pass_values_are_valid: bool = bool(
            status == PathSimCellStatus.PASS
            and finding_kind is None
            and isinstance(trace_path, Path)
            and isinstance(trace, ReferenceFmuTrace)
            and sample_count == case.expected_sample_count
            and isinstance(maximum_absolute_error, float)
            and isinstance(rms_absolute_error, float)
            and isinstance(maximum_event_time_error_seconds, float)
            and fmi_function is None
            and fmi_status is None
        )
        finding_values_are_valid: bool = bool(
            status == PathSimCellStatus.COMPLETED_WITH_FINDINGS
            and finding_kind == PathSimFindingKind.UNSUPPORTED_SCALAR_OUTPUT
            and trace_path is None
            and trace is None
            and sample_count == 0
            and maximum_absolute_error is None
            and rms_absolute_error is None
            and maximum_event_time_error_seconds is None
            and isinstance(fmi_function, str)
            and isinstance(fmi_status, int)
        )
        if common_values_are_valid and (pass_values_are_valid or finding_values_are_valid):
            pass
        else:
            raise ValueError("PathSim cell result is invalid")
        self.cell_index: int = cell_index
        self.cell_id: str = cell_id
        self.case: ReferenceFmuCase = case
        self.interface_mode: FmuInterfaceMode = interface_mode
        self.status: PathSimCellStatus = status
        self.finding_kind: PathSimFindingKind | None = finding_kind
        self.raw_result_path: Path = raw_result_path
        self.stdout_path: Path = stdout_path
        self.stderr_path: Path = stderr_path
        self.trace_path: Path | None = trace_path
        self.reference_trace_path: Path = reference_trace_path
        self.sample_count: int = sample_count
        self.event_times_seconds: np.ndarray = event_times_seconds.copy()
        self.maximum_absolute_error: float | None = maximum_absolute_error
        self.rms_absolute_error: float | None = rms_absolute_error
        self.maximum_event_time_error_seconds: float | None = maximum_event_time_error_seconds
        self.fmi_function: str | None = fmi_function
        self.fmi_status: int | None = fmi_status
        self.trace: ReferenceFmuTrace | None = trace
        self.reference_trace: ReferenceFmuTrace = reference_trace
        self.process_result: PathSimProcessResult = process_result


def _validate_pathsim_config(
    config: PathSimComparisonConfig,
) -> tuple[ReferenceFmuCatalog, tuple[ValidatedReferenceFmuAsset, ...]]:
    """Authenticate every immutable PathSim comparison input.

    :param config: Closed caller-owned comparison configuration.
    :return: Validated catalog and four immutable FMU assets.
    """

    if isinstance(config, PathSimComparisonConfig):
        pass
    else:
        raise ValueError("PathSim comparison requires its declared config type")
    output_parent: Path = config.output_directory.parent
    output_is_safe: bool = bool(
        output_parent.exists()
        and output_parent.is_dir()
        and not path_is_link_or_reparse_point(output_parent)
        and not config.output_directory.exists()
    )
    system_root_is_safe: bool = bool(
        config.system_root_path.exists()
        and config.system_root_path.is_dir()
        and not path_is_link_or_reparse_point(config.system_root_path)
        and config.system_root_path.is_absolute()
    )
    if output_is_safe and system_root_is_safe:
        pass
    else:
        raise ValueError("PathSim output or system-root path is unsafe")

    # The complete interpreter tree and executable are bound before any FMU
    # reaches a native loader.
    runtime_identity: tuple[int, int, str] = read_regular_tree_identity(
        config.runtime_root
    )
    expected_runtime_identity: tuple[int, int, str] = (
        config.runtime_entry_count,
        config.runtime_regular_bytes,
        config.runtime_tree_sha256,
    )
    if runtime_identity == expected_runtime_identity:
        pass
    else:
        raise ValueError("PathSim runtime tree identity changed")

    # Require the interpreter to be the canonical member of the authenticated
    # tree. Matching executable bytes beside other site-packages are not the
    # same runtime identity.
    resolved_runtime_root: Path = config.runtime_root.resolve(strict=True)
    expected_python_executable: Path = (
        resolved_runtime_root / "Scripts" / "python.exe"
    ).resolve(strict=True)
    resolved_python_executable: Path = config.python_executable_path.resolve(
        strict=True
    )
    python_belongs_to_runtime: bool = bool(
        resolved_python_executable == expected_python_executable
        and not path_is_link_or_reparse_point(config.python_executable_path)
    )
    if python_belongs_to_runtime:
        pass
    else:
        raise ValueError("PathSim Python executable is outside its runtime")
    verify_regular_file_identity(
        config.python_executable_path,
        config.python_executable_size_bytes,
        config.python_executable_sha256,
    )
    verify_regular_file_identity(
        config.catalog_path,
        config.catalog_size_bytes,
        config.catalog_sha256,
    )
    verify_regular_file_identity(
        config.archive_path,
        config.archive_size_bytes,
        config.archive_sha256,
    )
    verify_regular_file_identity(
        config.reference_manifest_path,
        config.reference_manifest_size_bytes,
        config.reference_manifest_sha256,
    )
    verify_regular_file_identity(
        config.worker_path,
        config.worker_size_bytes,
        config.worker_sha256,
    )

    # The catalog, not caller ordering alone, validates each extracted FMU.
    catalog: ReferenceFmuCatalog = load_reference_fmu_catalog(config.catalog_path)
    if len(catalog.cases) == 4 and catalog.archive_sha256 == config.archive_sha256:
        pass
    else:
        raise ValueError("PathSim corpus does not match the sealed release")
    assets: tuple[ValidatedReferenceFmuAsset, ...] = (
        catalog.validate_asset(catalog.cases[0].case_id, config.fmu_paths[0]),
        catalog.validate_asset(catalog.cases[1].case_id, config.fmu_paths[1]),
        catalog.validate_asset(catalog.cases[2].case_id, config.fmu_paths[2]),
        catalog.validate_asset(catalog.cases[3].case_id, config.fmu_paths[3]),
    )
    return catalog, assets


def _read_reference_execution_manifest(
    config: PathSimComparisonConfig,
) -> dict[str, object]:
    """Read the authenticated accepted FMPy execution manifest.

    :param config: Configuration binding the manifest identity.
    :return: Parsed immutable-evidence object used only for reference lookup.
    """

    manifest_bytes: bytes = verify_regular_file_identity(
        config.reference_manifest_path,
        config.reference_manifest_size_bytes,
        config.reference_manifest_sha256,
    )
    parsed_value: object = json.loads(manifest_bytes.decode("utf-8", errors="strict"))
    if isinstance(parsed_value, dict):
        manifest: dict[str, object] = cast(dict[str, object], parsed_value)
    else:
        raise ValueError("Accepted Reference-FMU manifest is not an object")
    expected_keys: set[str] = {
        "schema_name",
        "source",
        "corpus",
        "tools",
        "policy",
        "cells",
        "artifacts",
        "claim",
    }
    if set(manifest.keys()) == expected_keys:
        pass
    else:
        raise ValueError("Accepted Reference-FMU manifest keys changed")
    schema_name: object = manifest.get("schema_name", None)
    cells_value: object = manifest.get("cells", None)
    artifacts_value: object = manifest.get("artifacts", None)
    if (
        schema_name == "veragrid-fmi-reference-execution-v1"
        and isinstance(cells_value, list)
        and len(cells_value) == 16
        and isinstance(artifacts_value, list)
    ):
        return manifest
    else:
        raise ValueError("Accepted Reference-FMU manifest shape changed")


def _run_pathsim_worker(
    config: PathSimComparisonConfig,
    arguments: tuple[str, ...],
    environment: dict[str, str],
    working_directory: Path,
    stdout_path: Path,
    stderr_path: Path,
) -> PathSimProcessResult:
    """Run one worker without a shell while bounding time and both streams.

    :param config: Process deadline and stream bounds.
    :param arguments: Exact absolute process argument vector.
    :param environment: Closed four-key child environment.
    :param working_directory: Owned per-cell runtime directory.
    :param stdout_path: Retained standard-output path.
    :param stderr_path: Retained standard-error path.
    :return: Finished process evidence.
    """

    arguments_are_valid: bool = bool(
        isinstance(arguments, tuple)
        and len(arguments) == 20
        and arguments[0] == str(config.python_executable_path)
        and arguments[1:3] == ("-B", "-I")
        and all(isinstance(argument, str) for argument in arguments)
    )
    environment_is_valid: bool = bool(
        isinstance(environment, dict)
        and set(environment.keys())
        == {"PROCESSOR_ARCHITECTURE", "SystemRoot", "TEMP", "TMP"}
        and environment["PROCESSOR_ARCHITECTURE"]
        == config.processor_architecture
        and environment["SystemRoot"] == str(config.system_root_path)
        and environment["TEMP"] == str(working_directory / "temp")
        and environment["TMP"] == str(working_directory / "temp")
    )
    paths_are_valid: bool = bool(
        working_directory.exists()
        and working_directory.is_dir()
        and not path_is_link_or_reparse_point(working_directory)
        and stdout_path.parent.exists()
        and stderr_path.parent == stdout_path.parent
        and not stdout_path.exists()
        and not stderr_path.exists()
    )
    if arguments_are_valid and environment_is_valid and paths_are_valid:
        pass
    else:
        raise ValueError("PathSim worker process contract is invalid")

    stdout_file: BinaryIO = stdout_path.open("xb")
    stderr_file: BinaryIO = stderr_path.open("xb")
    process: subprocess.Popen[bytes] | None = None
    process_failure: str | None = None
    started_at: float = time.monotonic()
    try:
        process = subprocess.Popen(
            list(arguments),
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            cwd=working_directory,
            env=environment,
        )
        process_finished: bool = False
        while not process_finished:
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
                process_finished = bool(process.poll() is not None)
                if process_finished:
                    pass
                else:
                    time.sleep(0.05)
            else:
                if streams_are_bounded:
                    process_failure = "PathSim worker exceeded its deadline"
                else:
                    process_failure = "PathSim worker exceeded a stream boundary"
                process.kill()
                process.wait(timeout=5.0)
                process_finished = True
        return_code: int = cast(int, process.returncode)
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=5.0)
        else:
            pass
        stdout_file.close()
        stderr_file.close()
    if process_failure is None:
        pass
    else:
        raise RuntimeError(process_failure)
    elapsed_seconds = time.monotonic() - started_at
    stdout_bytes: bytes = stdout_path.read_bytes()
    stderr_bytes: bytes = stderr_path.read_bytes()
    if (
        len(stdout_bytes) <= config.stream_limit_bytes
        and len(stderr_bytes) <= config.stream_limit_bytes
    ):
        pass
    else:
        raise ValueError("PathSim retained stream exceeded its boundary")
    if return_code == 0:
        pass
    else:
        stderr_text: str = stderr_bytes.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"PathSim worker exited with status {return_code}: {stderr_text}"
        )
    return PathSimProcessResult(
        arguments,
        return_code,
        elapsed_seconds,
        len(stdout_bytes),
        hashlib.sha256(stdout_bytes).hexdigest(),
        len(stderr_bytes),
        hashlib.sha256(stderr_bytes).hexdigest(),
    )


def _read_pathsim_worker_result(result_path: Path) -> PathSimWorkerResult:
    """Parse one worker result through its exact declarative schema.

    :param result_path: Explicit JSON file written by one isolated worker.
    :return: Strictly typed worker result.
    """

    if (
        isinstance(result_path, Path)
        and result_path.exists()
        and result_path.is_file()
        and not path_is_link_or_reparse_point(result_path)
        and result_path.stat().st_size <= 65_536
    ):
        pass
    else:
        raise ValueError("PathSim worker result path is unsafe")
    parsed_value: object = json.loads(result_path.read_text(encoding="utf-8"))
    if isinstance(parsed_value, dict):
        result_value: dict[str, object] = cast(dict[str, object], parsed_value)
    else:
        raise ValueError("PathSim worker result is not an object")
    expected_keys: set[str] = {
        "schema",
        "status",
        "python_version",
        "pathsim_version",
        "pathsim_fmi_version",
        "fmpy_version",
        "sample_count",
        "event_times_seconds",
        "finding_kind",
        "fmi_function",
        "fmi_status",
    }
    if set(result_value.keys()) == expected_keys:
        pass
    else:
        raise ValueError("PathSim worker result keys changed")
    status_value: object = result_value["status"]
    if status_value == "PASS":
        status: PathSimCellStatus = PathSimCellStatus.PASS
    else:
        if status_value == "FINDING":
            status = PathSimCellStatus.COMPLETED_WITH_FINDINGS
        else:
            raise ValueError("PathSim worker status is unknown")
    finding_value: object = result_value["finding_kind"]
    if finding_value is None:
        finding_kind: PathSimFindingKind | None = None
    else:
        if finding_value == PathSimFindingKind.UNSUPPORTED_SCALAR_OUTPUT.value:
            finding_kind = PathSimFindingKind.UNSUPPORTED_SCALAR_OUTPUT
        else:
            raise ValueError("PathSim worker finding kind is unknown")
    event_values: object = result_value["event_times_seconds"]
    if isinstance(event_values, list) and all(
        isinstance(event_value, (int, float)) and not isinstance(event_value, bool)
        for event_value in event_values
    ):
        event_times_seconds: np.ndarray = np.asarray(
            event_values,
            dtype=np.float64,
        )
    else:
        raise ValueError("PathSim worker event values are invalid")
    sample_count_value: object = result_value["sample_count"]
    if isinstance(sample_count_value, int) and not isinstance(sample_count_value, bool):
        sample_count: int = sample_count_value
    else:
        raise ValueError("PathSim worker sample count is invalid")
    fmi_function_value: object = result_value["fmi_function"]
    if fmi_function_value is None or isinstance(fmi_function_value, str):
        fmi_function: str | None = cast(str | None, fmi_function_value)
    else:
        raise ValueError("PathSim worker FMI function is invalid")
    fmi_status_value: object = result_value["fmi_status"]
    if fmi_status_value is None or (
        isinstance(fmi_status_value, int) and not isinstance(fmi_status_value, bool)
    ):
        fmi_status: int | None = cast(int | None, fmi_status_value)
    else:
        raise ValueError("PathSim worker FMI status is invalid")
    version_values: tuple[object, object, object, object] = (
        result_value["python_version"],
        result_value["pathsim_version"],
        result_value["pathsim_fmi_version"],
        result_value["fmpy_version"],
    )
    if result_value["schema"] == "veragrid.fmi-pathsim-worker/1" and all(
        isinstance(version_value, str) for version_value in version_values
    ):
        pass
    else:
        raise ValueError("PathSim worker schema or versions are invalid")
    return PathSimWorkerResult(
        status,
        cast(str, version_values[0]),
        cast(str, version_values[1]),
        cast(str, version_values[2]),
        cast(str, version_values[3]),
        sample_count,
        event_times_seconds,
        finding_kind,
        fmi_function,
        fmi_status,
    )


def _evaluate_pathsim_cell(
    cell_index: int,
    case: ReferenceFmuCase,
    interface_mode: FmuInterfaceMode,
    worker_result: PathSimWorkerResult,
    process_result: PathSimProcessResult,
    raw_result_path: Path,
    stdout_path: Path,
    stderr_path: Path,
    trace_file_path: Path,
    trace_path: Path,
    reference_trace_path: Path,
) -> PathSimCellResult:
    """Evaluate one worker result against its accepted FMPy trace and oracle.

    :param cell_index: Zero-based canonical PathSim matrix position.
    :param case: Sealed Reference FMU case.
    :param interface_mode: FMI interface exercised by the worker.
    :param worker_result: Strictly parsed child result.
    :param process_result: Bounded process evidence.
    :param raw_result_path: Worker JSON path relative to the package root.
    :param stdout_path: Standard-output path relative to the package root.
    :param stderr_path: Standard-error path relative to the package root.
    :param trace_file_path: Absolute candidate PathSim trace used for evaluation.
    :param trace_path: Candidate PathSim trace relative to the package root.
    :param reference_trace_path: Authenticated accepted FMPy trace.
    :return: Fully evaluated immutable cell result.
    """

    if process_result.return_code == 0:
        pass
    else:
        raise RuntimeError("PathSim worker returned a nonzero status")
    oracle: ReferenceFmuEventOracle = case.find_interface_oracle(interface_mode)
    reference_trace: ReferenceFmuTrace = read_reference_fmu_trace_csv(
        reference_trace_path,
        oracle.observed_variable_name,
        oracle.observed_variable_type,
    )
    interface_token: str
    if interface_mode == FmuInterfaceMode.CO_SIMULATION:
        interface_token = "cs"
    else:
        interface_token = "me"
    cell_id: str = (
        f"cell-{cell_index:02d}--{case.case_id}--{interface_token}--pathsim"
    )

    if worker_result.status == PathSimCellStatus.COMPLETED_WITH_FINDINGS:
        if case.model_name == "Stair":
            pass
        else:
            raise RuntimeError("PathSim produced a finding for a state-event case")
        if case.fmi_version.value == "2.0":
            expected_function: str = "fmi2GetReal"
        else:
            expected_function = "fmi3GetFloat64"
        finding_is_exact: bool = bool(
            worker_result.finding_kind
            == PathSimFindingKind.UNSUPPORTED_SCALAR_OUTPUT
            and worker_result.fmi_function == expected_function
            and worker_result.fmi_status == 3
            and not trace_file_path.exists()
        )
        if finding_is_exact:
            pass
        else:
            raise RuntimeError("PathSim Stair finding differs from the accepted limitation")
        return PathSimCellResult(
            cell_index,
            cell_id,
            case,
            interface_mode,
            PathSimCellStatus.COMPLETED_WITH_FINDINGS,
            PathSimFindingKind.UNSUPPORTED_SCALAR_OUTPUT,
            raw_result_path,
            stdout_path,
            stderr_path,
            None,
            reference_trace_path,
            0,
            np.empty(0, dtype=np.float64),
            None,
            None,
            None,
            worker_result.fmi_function,
            worker_result.fmi_status,
            None,
            reference_trace,
            process_result,
        )
    else:
        pass

    if case.model_name == "BouncingBall" and trace_file_path.exists():
        pathsim_trace: ReferenceFmuTrace = read_reference_fmu_trace_csv(
            trace_file_path,
            oracle.observed_variable_name,
            oracle.observed_variable_type,
        )
    else:
        raise RuntimeError("Only BouncingBall may produce a passing PathSim trace")
    regular_pathsim: ReferenceFmuTrace = build_reference_fmu_regular_trace(
        case,
        pathsim_trace,
    )
    regular_reference: ReferenceFmuTrace = build_reference_fmu_regular_trace(
        case,
        reference_trace,
    )
    if (
        worker_result.sample_count == case.expected_sample_count
        and regular_pathsim.time_seconds.size == case.expected_sample_count
        and np.array_equal(
            regular_pathsim.time_seconds,
            regular_reference.time_seconds,
        )
    ):
        pass
    else:
        raise ValueError("PathSim cell does not share the accepted regular lattice")
    absolute_errors: np.ndarray = np.abs(
        regular_pathsim.observed_values.astype(np.float64)
        - regular_reference.observed_values.astype(np.float64)
    )
    maximum_absolute_error: float = float(np.max(absolute_errors))
    rms_absolute_error: float = float(
        np.sqrt(np.mean(np.square(absolute_errors)))
    )
    if interface_mode == FmuInterfaceMode.CO_SIMULATION:
        values_are_accepted: bool = bool(
            np.array_equal(
                regular_pathsim.observed_values,
                regular_reference.observed_values,
            )
            and maximum_absolute_error == 0.0
            and rms_absolute_error == 0.0
        )
    else:
        values_are_accepted = bool(
            maximum_absolute_error <= 1.0e-5
            and rms_absolute_error <= 2.0e-6
        )
    if values_are_accepted:
        pass
    else:
        raise ValueError("PathSim BouncingBall values exceed their oracle")

    event_count: int = int(worker_result.event_times_seconds.size)
    if event_count == oracle.observable_transition_count:
        pass
    else:
        raise ValueError("PathSim BouncingBall event count differs from its oracle")
    maximum_event_time_error_seconds: float = 0.0
    for event_index in range(event_count):
        event_time: float = float(worker_result.event_times_seconds[event_index])
        lower_bound: float = float(oracle.event_lower_bounds_seconds[event_index])
        upper_bound: float = float(oracle.event_upper_bounds_seconds[event_index])
        if lower_bound - 1.0e-12 <= event_time <= upper_bound + 1.0e-12:
            event_center: float = 0.5 * (lower_bound + upper_bound)
            maximum_event_time_error_seconds = max(
                maximum_event_time_error_seconds,
                abs(event_time - event_center),
            )
        else:
            raise ValueError("PathSim BouncingBall event lies outside its oracle")
    if math.isclose(
        float(regular_pathsim.time_seconds[-1]),
        case.declared_stop_time_seconds,
        abs_tol=1.0e-12,
    ):
        pass
    else:
        raise ValueError("PathSim BouncingBall did not reach configured stop")
    return PathSimCellResult(
        cell_index,
        cell_id,
        case,
        interface_mode,
        PathSimCellStatus.PASS,
        None,
        raw_result_path,
        stdout_path,
        stderr_path,
        trace_path,
        reference_trace_path,
        worker_result.sample_count,
        worker_result.event_times_seconds,
        maximum_absolute_error,
        rms_absolute_error,
        maximum_event_time_error_seconds,
        None,
        None,
        pathsim_trace,
        reference_trace,
        process_result,
    )


def _render_pathsim_figures(
    package_root: Path,
    cells: tuple[PathSimCellResult, ...],
) -> tuple[dict[str, object], dict[str, object]]:
    """Render the retained trajectory overlay and eight-cell capability matrix.

    :param package_root: Unpublished package staging directory.
    :param cells: Eight fully evaluated cells in canonical order.
    :return: Exact declarative contracts for the two figure families.
    """

    if len(cells) == 8:
        pass
    else:
        raise ValueError("PathSim rendering requires eight ordered cells")
    figures_directory: Path = package_root / "figures"
    figures_directory.mkdir()
    style: dict[str, object] = {
        "font.family": "DejaVu Sans",
        "font.size": 8.0,
        "axes.titlesize": 8.5,
        "axes.labelsize": 8.0,
        "xtick.labelsize": 7.0,
        "ytick.labelsize": 7.0,
        "legend.fontsize": 7.0,
        "axes.linewidth": 0.7,
        "lines.linewidth": 1.2,
        "svg.fonttype": "none",
        "svg.hashsalt": "veragrid-pathsim-comparison",
        "pdf.fonttype": 42,
    }
    # These format APIs require mapping objects. Fixed metadata removes
    # wall-clock entropy so the verifier can reproduce every published byte.
    png_metadata: dict[str, str] = {
        "Software": "VeraGrid PathSim FMI comparison",
    }
    svg_metadata: dict[str, str] = {
        "Creator": "VeraGrid PathSim FMI comparison",
        "Date": "1970-01-01T00:00:00Z",
    }
    fixed_pdf_time: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)
    pdf_metadata: dict[str, object] = {
        "Creator": "VeraGrid PathSim FMI comparison",
        "CreationDate": fixed_pdf_time,
        "ModDate": fixed_pdf_time,
    }
    with matplotlib.rc_context(style):
        # Four aligned panels preserve the exact FMI/interface distinctions and
        # add a signed residual when visual overlap hides numerical differences.
        overlay_figure: Figure = Figure(figsize=(7.2, 7.0), dpi=300)
        FigureCanvasAgg(overlay_figure)
        overlay_axes_value: object = overlay_figure.subplots(
            4,
            1,
            sharex=True,
            squeeze=False,
        )
        overlay_axes: np.ndarray = np.asarray(overlay_axes_value, dtype=object)
        pass_indices: tuple[int, int, int, int] = (0, 1, 4, 5)
        for panel_index in range(4):
            cell: PathSimCellResult = cells[pass_indices[panel_index]]
            if cell.trace is not None:
                pathsim_regular: ReferenceFmuTrace = build_reference_fmu_regular_trace(
                    cell.case,
                    cell.trace,
                )
            else:
                raise ValueError("Overlay cell is missing its PathSim trace")
            reference_regular: ReferenceFmuTrace = build_reference_fmu_regular_trace(
                cell.case,
                cell.reference_trace,
            )
            axis: Axes = cast(Axes, overlay_axes[panel_index, 0])
            axis.plot(
                reference_regular.time_seconds,
                reference_regular.observed_values,
                color="#202020",
                linestyle="-",
                label="FMPy reference",
                zorder=2,
            )
            axis.plot(
                pathsim_regular.time_seconds,
                pathsim_regular.observed_values,
                color="#3569a8",
                linestyle="--",
                label="PathSim-FMI",
                zorder=3,
            )
            for event_time in cell.event_times_seconds:
                axis.axvline(
                    float(event_time),
                    color="#777777",
                    linestyle=":",
                    linewidth=0.65,
                    zorder=1,
                )
            interface_label: str
            if cell.interface_mode == FmuInterfaceMode.CO_SIMULATION:
                interface_label = "Co-Simulation"
            else:
                interface_label = "Model Exchange"
            axis.set_title(
                f"FMI {cell.case.fmi_version.value} — {interface_label}",
                loc="left",
                pad=3.0,
            )
            axis.set_ylabel("Velocity [m/s]")
            axis.grid(axis="y", color="#d9d9d9", linewidth=0.45)
            axis.tick_params(direction="in")
            if panel_index == 0:
                axis.legend(frameon=False, loc="upper right")
            else:
                pass
        cast(Axes, overlay_axes[3, 0]).set_xlabel("Time [s]")
        overlay_figure.subplots_adjust(
            left=0.105,
            right=0.975,
            bottom=0.075,
            top=0.975,
            hspace=0.28,
        )
        overlay_base: Path = figures_directory / "bouncing-ball-overlay"
        overlay_figure.savefig(
            overlay_base.with_suffix(".png"),
            dpi=300,
            metadata=png_metadata,
        )
        overlay_figure.savefig(
            overlay_base.with_suffix(".svg"),
            metadata=svg_metadata,
        )
        overlay_figure.savefig(
            overlay_base.with_suffix(".pdf"),
            metadata=pdf_metadata,
        )
        overlay_figure.clear()

        # The matrix reports attempted capability, including retained external
        # limitations, without converting them into interoperability claims.
        matrix_figure: Figure = Figure(figsize=(7.2, 4.6), dpi=300)
        FigureCanvasAgg(matrix_figure)
        matrix_axis: Axes = matrix_figure.subplots(1, 1)
        matrix_values: np.ndarray = np.empty((4, 2), dtype=np.float64)
        matrix_labels: np.ndarray = np.empty((4, 2), dtype=object)
        for case_index in range(4):
            for interface_index in range(2):
                matrix_cell: PathSimCellResult = cells[2 * case_index + interface_index]
                if matrix_cell.status == PathSimCellStatus.PASS:
                    matrix_values[case_index, interface_index] = 1.0
                    matrix_labels[case_index, interface_index] = "PASS"
                else:
                    matrix_values[case_index, interface_index] = 0.0
                    matrix_labels[case_index, interface_index] = "Finding"
        color_map: ListedColormap = ListedColormap(["#d9d9d9", "#7aa6c2"])
        matrix_axis.imshow(
            matrix_values,
            cmap=color_map,
            vmin=0.0,
            vmax=1.0,
            aspect="auto",
            interpolation="nearest",
        )
        row_labels: tuple[str, str, str, str] = (
            "FMI 2.0 · BouncingBall · state event",
            "FMI 2.0 · Stair · time event",
            "FMI 3.0 · BouncingBall · state event",
            "FMI 3.0 · Stair · time event",
        )
        matrix_axis.set_xticks((0, 1), ("Co-Simulation", "Model Exchange"))
        matrix_axis.set_yticks((0, 1, 2, 3), row_labels)
        matrix_axis.tick_params(length=0.0)
        for case_index in range(4):
            for interface_index in range(2):
                matrix_axis.text(
                    interface_index,
                    case_index,
                    cast(str, matrix_labels[case_index, interface_index]),
                    ha="center",
                    va="center",
                    color="#202020",
                    fontsize=8.0,
                )
        matrix_axis.set_title(
            "PathSim-FMI 0.1.1 attempted interoperability",
            loc="left",
            pad=8.0,
        )
        matrix_figure.subplots_adjust(
            left=0.40,
            right=0.97,
            bottom=0.14,
            top=0.90,
        )
        matrix_base: Path = figures_directory / "capability-matrix"
        matrix_figure.savefig(
            matrix_base.with_suffix(".png"),
            dpi=300,
            metadata=png_metadata,
        )
        matrix_figure.savefig(
            matrix_base.with_suffix(".svg"),
            metadata=svg_metadata,
        )
        matrix_figure.savefig(
            matrix_base.with_suffix(".pdf"),
            metadata=pdf_metadata,
        )
        matrix_figure.clear()

    overlay_contract: dict[str, object] = {
        "figure_id": "bouncing-ball-overlay",
        "png_path": "figures/bouncing-ball-overlay.png",
        "svg_path": "figures/bouncing-ball-overlay.svg",
        "pdf_path": "figures/bouncing-ball-overlay.pdf",
        "width_inches": 7.2,
        "height_inches": 7.0,
        "png_width_pixels": 2160,
        "png_height_pixels": 2100,
        "dpi": 300,
        "font_family": "DejaVu Sans",
    }
    matrix_contract: dict[str, object] = {
        "figure_id": "capability-matrix",
        "png_path": "figures/capability-matrix.png",
        "svg_path": "figures/capability-matrix.svg",
        "pdf_path": "figures/capability-matrix.pdf",
        "width_inches": 7.2,
        "height_inches": 4.6,
        "png_width_pixels": 2160,
        "png_height_pixels": 1380,
        "dpi": 300,
        "font_family": "DejaVu Sans",
    }
    return overlay_contract, matrix_contract


def _write_pathsim_manifest(
    config: PathSimComparisonConfig,
    catalog: ReferenceFmuCatalog,
    cells: tuple[PathSimCellResult, ...],
    figures: tuple[dict[str, object], dict[str, object]],
    package_root: Path,
) -> Path:
    """Write the exact closed PathSim comparison manifest.

    :param config: Authenticated comparison configuration.
    :param catalog: Sealed Reference FMU catalog.
    :param cells: Eight evaluated PathSim cells.
    :param figures: Two exact figure-family contracts.
    :param package_root: Unpublished complete package root.
    :return: New manifest path.
    """

    if len(cells) == 8 and len(figures) == 2:
        pass
    else:
        raise ValueError("PathSim manifest requires eight cells and two figures")
    fmu_records: list[dict[str, object]] = [dict()] * 4
    for case_index in range(4):
        case: ReferenceFmuCase = catalog.cases[case_index]
        fmu_records[case_index] = {
            "case_id": case.case_id,
            "path": str(config.fmu_paths[case_index]),
            "size_bytes": case.fmu_size_bytes,
            "sha256": case.fmu_sha256,
        }
    reference_trace_records: list[dict[str, object]] = [dict()] * 8
    cell_records: list[dict[str, object]] = [dict()] * 8
    canonical_cell_ids: list[str] = [""] * 8
    for cell_index in range(8):
        cell: PathSimCellResult = cells[cell_index]
        reference_bytes: bytes = cell.reference_trace_path.read_bytes()
        reference_trace_records[cell_index] = {
            "cell_id": cell.cell_id,
            "path": str(cell.reference_trace_path),
            "size_bytes": len(reference_bytes),
            "sha256": hashlib.sha256(reference_bytes).hexdigest(),
        }
        oracle: ReferenceFmuEventOracle = cell.case.find_interface_oracle(
            cell.interface_mode
        )
        if cell.finding_kind is None:
            finding_value: str | None = None
        else:
            finding_value = cell.finding_kind.value
        if cell.trace_path is None:
            trace_value: str | None = None
        else:
            trace_value = cell.trace_path.as_posix()
        cell_records[cell_index] = {
            "cell_index": cell.cell_index,
            "cell_id": cell.cell_id,
            "case_id": cell.case.case_id,
            "fmi_version": cell.case.fmi_version.value,
            "model_name": cell.case.model_name,
            "event_mechanism": oracle.mechanism.value,
            "interface_mode": cell.interface_mode.value,
            "status": cell.status.value,
            "finding_kind": finding_value,
            "raw_result_path": cell.raw_result_path.as_posix(),
            "stdout_path": cell.stdout_path.as_posix(),
            "stderr_path": cell.stderr_path.as_posix(),
            "trace_path": trace_value,
            "reference_trace_path": str(cell.reference_trace_path),
            "sample_count": cell.sample_count,
            "event_count": int(cell.event_times_seconds.size),
            "maximum_absolute_error": cell.maximum_absolute_error,
            "rms_absolute_error": cell.rms_absolute_error,
            "maximum_event_time_error_seconds": cell.maximum_event_time_error_seconds,
            "fmi_function": cell.fmi_function,
            "fmi_status": cell.fmi_status,
        }
        canonical_cell_ids[cell_index] = cell.cell_id

    regular_paths: list[Path] = list()
    for discovered_path in package_root.rglob("*"):
        if path_is_link_or_reparse_point(discovered_path):
            raise ValueError("PathSim package contains a symbolic link")
        else:
            if discovered_path.is_file():
                regular_paths.append(discovered_path)
            else:
                if discovered_path.is_dir():
                    pass
                else:
                    raise ValueError("PathSim package contains a special entry")
    paths_by_name: dict[str, Path] = dict()
    for regular_path in regular_paths:
        portable_name: str = regular_path.relative_to(package_root).as_posix()
        paths_by_name[portable_name] = regular_path
    regular_names: list[str] = list(paths_by_name.keys())
    regular_names.sort()
    if len(regular_paths) == 34:
        pass
    else:
        raise ValueError("PathSim package must contain 34 pre-manifest files")
    package_file_records: list[dict[str, object]] = [dict()] * 34
    for file_index in range(34):
        package_path: Path = paths_by_name[regular_names[file_index]]
        content: bytes = package_path.read_bytes()
        package_file_records[file_index] = {
            "path": package_path.relative_to(package_root).as_posix(),
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    manifest: dict[str, object] = {
        "schema": "veragrid.fmi-pathsim-comparison/1",
        "status": "COMPLETED_WITH_FINDINGS",
        "source": {
            "branch": config.source_branch,
            "revision": config.source_revision,
            "tree_sha256": config.source_tree_sha256,
        },
        "tools": {
            "python": {
                "path": str(config.python_executable_path),
                "version": "3.11.9",
                "executable_size_bytes": config.python_executable_size_bytes,
                "executable_sha256": config.python_executable_sha256,
                "runtime_entry_count": config.runtime_entry_count,
                "runtime_regular_bytes": config.runtime_regular_bytes,
                "runtime_tree_sha256": config.runtime_tree_sha256,
                "system_root_path": str(config.system_root_path),
                "processor_architecture": config.processor_architecture,
            },
            "pathsim": {"version": "0.25.0"},
            "pathsim_fmi": {"version": "0.1.1"},
            "fmpy": {"version": "0.3.31"},
        },
        "corpus": {
            "catalog_path": str(config.catalog_path),
            "catalog_size_bytes": config.catalog_size_bytes,
            "catalog_sha256": config.catalog_sha256,
            "release_tag": "v0.0.41",
            "archive_path": str(config.archive_path),
            "archive_size_bytes": config.archive_size_bytes,
            "archive_sha256": config.archive_sha256,
            "fmus": fmu_records,
        },
        "reference": {
            "manifest_path": str(config.reference_manifest_path),
            "manifest_size_bytes": config.reference_manifest_size_bytes,
            "manifest_sha256": config.reference_manifest_sha256,
            "traces": reference_trace_records,
        },
        "execution": {
            "process_timeout_seconds": 120.0,
            "stream_limit_bytes": 1_048_576,
            "python_flags": ["-B", "-I"],
            "environment_keys": [
                "PROCESSOR_ARCHITECTURE",
                "SystemRoot",
                "TEMP",
                "TMP",
            ],
            "cell_order": canonical_cell_ids,
            "me_solver": "RKBS32",
            "me_dt_seconds": 0.01,
            "me_dt_max_seconds": 0.01,
            "me_relative_tolerance": 1.0e-6,
            "me_absolute_tolerance": 1.0e-9,
            "event_tolerance": 1.0e-10,
        },
        "cells": cell_records,
        "summary": {
            "attempted_cell_count": 8,
            "passed_cell_count": 4,
            "finding_cell_count": 4,
            "attempted_event_families": ["state_event", "time_event"],
            "successful_event_families": ["state_event"],
            "certification_claim": False,
        },
        "figures": [figures[0], figures[1]],
        "package_files": package_file_records,
        "limitations": [
            "PathSim-FMI 0.1.1 is an Alpha FMPy-backed orchestration layer, "
            "not an independent low-level FMI runtime.",
            "Stair FMI 2.0/3.0 CS/ME did not demonstrate time-event "
            "interoperability because Integer and Int32 outputs were requested "
            "through Real/Float64 getters.",
        ],
    }
    manifest_path: Path = package_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _verify_pathsim_package(
    config: PathSimComparisonConfig,
    package_root: Path,
) -> None:
    """Reopen and verify the exact closed PathSim evidence package.

    :param config: Configuration used to rebind immutable provenance.
    :param package_root: Complete staging or published package root.
    :return: None after every structural and identity check passes.
    """

    manifest_path: Path = package_root / "manifest.json"
    root_is_valid: bool = bool(
        package_root.exists()
        and package_root.is_dir()
        and not path_is_link_or_reparse_point(package_root)
        and manifest_path.exists()
        and manifest_path.is_file()
        and not path_is_link_or_reparse_point(manifest_path)
    )
    if root_is_valid:
        pass
    else:
        raise ValueError("PathSim package root is unsafe or incomplete")
    manifest_bytes: bytes = manifest_path.read_bytes()
    parsed_value: object = json.loads(
        manifest_bytes.decode("utf-8", errors="strict")
    )
    if isinstance(parsed_value, dict):
        manifest: dict[str, object] = cast(dict[str, object], parsed_value)
    else:
        raise ValueError("PathSim manifest is not an object")
    expected_top_keys: set[str] = {
        "schema", "status", "source", "tools", "corpus", "reference",
        "execution", "cells", "summary", "figures", "package_files",
        "limitations",
    }
    expected_top_order: tuple[str, ...] = (
        "schema", "status", "source", "tools", "corpus", "reference",
        "execution", "cells", "summary", "figures", "package_files",
        "limitations",
    )
    root_matches: bool = bool(
        set(manifest.keys()) == expected_top_keys
        and tuple(manifest.keys()) == expected_top_order
        and manifest["schema"] == "veragrid.fmi-pathsim-comparison/1"
        and manifest["status"] == "COMPLETED_WITH_FINDINGS"
    )
    if root_matches:
        pass
    else:
        raise ValueError("PathSim manifest root differs from its closed schema")
    expected_source: dict[str, object] = {
        "branch": config.source_branch,
        "revision": config.source_revision,
        "tree_sha256": config.source_tree_sha256,
    }
    expected_tools: dict[str, object] = {
        "python": {
            "path": str(config.python_executable_path),
            "version": "3.11.9",
            "executable_size_bytes": config.python_executable_size_bytes,
            "executable_sha256": config.python_executable_sha256,
            "runtime_entry_count": config.runtime_entry_count,
            "runtime_regular_bytes": config.runtime_regular_bytes,
            "runtime_tree_sha256": config.runtime_tree_sha256,
            "system_root_path": str(config.system_root_path),
            "processor_architecture": config.processor_architecture,
        },
        "pathsim": {"version": "0.25.0"},
        "pathsim_fmi": {"version": "0.1.1"},
        "fmpy": {"version": "0.3.31"},
    }
    expected_execution: dict[str, object] = {
        "process_timeout_seconds": 120.0,
        "stream_limit_bytes": 1_048_576,
        "python_flags": ["-B", "-I"],
        "environment_keys": [
            "PROCESSOR_ARCHITECTURE",
            "SystemRoot",
            "TEMP",
            "TMP",
        ],
        "cell_order": [
            "cell-00--reference-fmus-2.0-bouncing-ball--cs--pathsim",
            "cell-01--reference-fmus-2.0-bouncing-ball--me--pathsim",
            "cell-02--reference-fmus-2.0-stair--cs--pathsim",
            "cell-03--reference-fmus-2.0-stair--me--pathsim",
            "cell-04--reference-fmus-3.0-bouncing-ball--cs--pathsim",
            "cell-05--reference-fmus-3.0-bouncing-ball--me--pathsim",
            "cell-06--reference-fmus-3.0-stair--cs--pathsim",
            "cell-07--reference-fmus-3.0-stair--me--pathsim",
        ],
        "me_solver": "RKBS32",
        "me_dt_seconds": 0.01,
        "me_dt_max_seconds": 0.01,
        "me_relative_tolerance": 1.0e-6,
        "me_absolute_tolerance": 1.0e-9,
        "event_tolerance": 1.0e-10,
    }
    expected_summary: dict[str, object] = {
        "attempted_cell_count": 8,
        "passed_cell_count": 4,
        "finding_cell_count": 4,
        "attempted_event_families": ["state_event", "time_event"],
        "successful_event_families": ["state_event"],
        "certification_claim": False,
    }
    expected_limitations: list[str] = [
        "PathSim-FMI 0.1.1 is an Alpha FMPy-backed orchestration layer, "
        "not an independent low-level FMI runtime.",
        "Stair FMI 2.0/3.0 CS/ME did not demonstrate time-event "
        "interoperability because Integer and Int32 outputs were requested "
        "through Real/Float64 getters.",
    ]
    stable_manifest_values: tuple[object, object, object, object, object] = (
        manifest["source"],
        manifest["tools"],
        manifest["execution"],
        manifest["summary"],
        manifest["limitations"],
    )
    stable_expected_values: tuple[object, object, object, object, object] = (
        expected_source,
        expected_tools,
        expected_execution,
        expected_summary,
        expected_limitations,
    )
    stable_objects_match: bool = bool(
        json.dumps(
            stable_manifest_values,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        == json.dumps(
            stable_expected_values,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    if stable_objects_match:
        pass
    else:
        raise ValueError("PathSim manifest provenance, execution or claims changed")

    corpus_value: object = manifest["corpus"]
    reference_value: object = manifest["reference"]
    cells_value: object = manifest["cells"]
    figures_value: object = manifest["figures"]
    files_value: object = manifest["package_files"]
    nested_shapes_match: bool = bool(
        isinstance(corpus_value, dict)
        and set(corpus_value.keys()) == {
            "catalog_path", "catalog_size_bytes", "catalog_sha256",
            "release_tag", "archive_path", "archive_size_bytes",
            "archive_sha256", "fmus",
        }
        and isinstance(reference_value, dict)
        and set(reference_value.keys()) == {
            "manifest_path", "manifest_size_bytes", "manifest_sha256", "traces",
        }
        and isinstance(cells_value, list)
        and len(cells_value) == 8
        and isinstance(figures_value, list)
        and len(figures_value) == 2
        and isinstance(files_value, list)
        and len(files_value) == 34
    )
    if nested_shapes_match:
        corpus: dict[str, object] = cast(dict[str, object], corpus_value)
        reference: dict[str, object] = cast(dict[str, object], reference_value)
        cells: list[object] = cast(list[object], cells_value)
        figures: list[object] = cast(list[object], figures_value)
        file_records: list[object] = cast(list[object], files_value)
    else:
        raise ValueError("PathSim nested manifest shape changed")
    corpus_matches: bool = bool(
        corpus["catalog_path"] == str(config.catalog_path)
        and corpus["catalog_size_bytes"] == config.catalog_size_bytes
        and corpus["catalog_sha256"] == config.catalog_sha256
        and corpus["release_tag"] == "v0.0.41"
        and corpus["archive_path"] == str(config.archive_path)
        and corpus["archive_size_bytes"] == config.archive_size_bytes
        and corpus["archive_sha256"] == config.archive_sha256
        and isinstance(corpus["fmus"], list)
        and len(cast(list[object], corpus["fmus"])) == 4
    )
    reference_matches: bool = bool(
        reference["manifest_path"] == str(config.reference_manifest_path)
        and reference["manifest_size_bytes"] == config.reference_manifest_size_bytes
        and reference["manifest_sha256"] == config.reference_manifest_sha256
        and isinstance(reference["traces"], list)
        and len(cast(list[object], reference["traces"])) == 8
    )
    if corpus_matches and reference_matches:
        pass
    else:
        raise ValueError("PathSim corpus or reference binding changed")

    # Reauthenticate every external input instead of trusting self-consistent
    # values copied into the package manifest.
    runtime_identity: tuple[int, int, str] = read_regular_tree_identity(
        config.runtime_root
    )
    expected_runtime_identity: tuple[int, int, str] = (
        config.runtime_entry_count,
        config.runtime_regular_bytes,
        config.runtime_tree_sha256,
    )
    if runtime_identity == expected_runtime_identity:
        pass
    else:
        raise ValueError("PathSim runtime identity changed during verification")
    resolved_runtime_root: Path = config.runtime_root.resolve(strict=True)
    expected_python_executable: Path = (
        resolved_runtime_root / "Scripts" / "python.exe"
    ).resolve(strict=True)
    resolved_python_executable: Path = config.python_executable_path.resolve(
        strict=True
    )
    python_belongs_to_runtime: bool = bool(
        resolved_python_executable == expected_python_executable
        and not path_is_link_or_reparse_point(config.python_executable_path)
    )
    if python_belongs_to_runtime:
        pass
    else:
        raise ValueError("PathSim Python executable is outside its runtime")
    verify_regular_file_identity(
        config.python_executable_path,
        config.python_executable_size_bytes,
        config.python_executable_sha256,
    )
    verify_regular_file_identity(
        config.catalog_path,
        config.catalog_size_bytes,
        config.catalog_sha256,
    )
    verify_regular_file_identity(
        config.archive_path,
        config.archive_size_bytes,
        config.archive_sha256,
    )
    verify_regular_file_identity(
        config.worker_path,
        config.worker_size_bytes,
        config.worker_sha256,
    )
    verified_catalog: ReferenceFmuCatalog = load_reference_fmu_catalog(
        config.catalog_path
    )
    catalog_shape_is_valid: bool = bool(
        len(verified_catalog.cases) == 4
        and verified_catalog.archive_sha256 == config.archive_sha256
    )
    if catalog_shape_is_valid:
        pass
    else:
        raise ValueError("PathSim verified catalog changed")
    expected_fmu_records: list[dict[str, object]] = [dict()] * 4
    for case_index in range(4):
        verified_case: ReferenceFmuCase = verified_catalog.cases[case_index]
        # Reauthenticate the concrete FMU even though only its declarative
        # catalog identity is retained in the published manifest.
        verified_catalog.validate_asset(
            verified_case.case_id,
            config.fmu_paths[case_index],
        )
        expected_fmu_records[case_index] = {
            "case_id": verified_case.case_id,
            "path": str(config.fmu_paths[case_index]),
            "size_bytes": verified_case.fmu_size_bytes,
            "sha256": verified_case.fmu_sha256,
        }

    accepted_manifest: dict[str, object] = _read_reference_execution_manifest(
        config
    )
    accepted_cells_value: object = accepted_manifest["cells"]
    accepted_artifacts_value: object = accepted_manifest["artifacts"]
    if isinstance(accepted_cells_value, list) and isinstance(
        accepted_artifacts_value,
        list,
    ):
        accepted_cells: list[object] = cast(list[object], accepted_cells_value)
        accepted_artifacts: list[object] = cast(
            list[object],
            accepted_artifacts_value,
        )
    else:
        raise ValueError("PathSim accepted reference collections changed")
    bound_reference_paths: list[Path | None] = [None] * 8
    expected_reference_records: list[dict[str, object]] = [dict()] * 8
    canonical_cell_ids: list[str] = [""] * 8
    for cell_index in range(8):
        verified_case = verified_catalog.cases[cell_index // 2]
        verified_interface: FmuInterfaceMode = verified_case.interfaces[
            cell_index % 2
        ]
        if verified_interface == FmuInterfaceMode.CO_SIMULATION:
            verified_interface_token: str = "cs"
        else:
            verified_interface_token = "me"
        canonical_cell_id: str = (
            f"cell-{cell_index:02d}--{verified_case.case_id}--"
            f"{verified_interface_token}--pathsim"
        )
        canonical_cell_ids[cell_index] = canonical_cell_id
        matched_reference_path: Path | None = None
        matched_reference_size: int | None = None
        matched_reference_sha256: str | None = None
        reference_cell_matches: int = 0
        reference_artifact_matches: int = 0
        for accepted_cell_value in accepted_cells:
            if isinstance(accepted_cell_value, dict):
                accepted_cell: dict[str, object] = cast(
                    dict[str, object],
                    accepted_cell_value,
                )
            else:
                raise ValueError("PathSim accepted reference cell changed")
            accepted_cell_matches: bool = bool(
                accepted_cell.get("case_id", None) == verified_case.case_id
                and accepted_cell.get("interface_mode", None)
                == verified_interface.value
                and accepted_cell.get("tool", None) == "fmpy"
                and accepted_cell.get("status", None)
                in ("pass", "pass_with_observability_limit")
            )
            if accepted_cell_matches:
                reference_cell_matches += 1
                accepted_trace_value: object = accepted_cell.get(
                    "raw_trace_path",
                    None,
                )
                accepted_cell_id: object = accepted_cell.get("cell_id", None)
                if isinstance(accepted_trace_value, str) and isinstance(
                    accepted_cell_id,
                    str,
                ):
                    accepted_trace_path: Path = (
                        config.reference_manifest_path.parent
                        / Path(accepted_trace_value)
                    )
                else:
                    raise ValueError("PathSim accepted trace path changed")
                for accepted_artifact_value in accepted_artifacts:
                    if isinstance(accepted_artifact_value, dict):
                        accepted_artifact: dict[str, object] = cast(
                            dict[str, object],
                            accepted_artifact_value,
                        )
                    else:
                        raise ValueError("PathSim accepted artifact changed")
                    accepted_artifact_matches: bool = bool(
                        accepted_artifact.get("path", None)
                        == accepted_trace_value
                        and accepted_artifact.get("cell_id", None)
                        == accepted_cell_id
                        and accepted_artifact.get("kind", None) == "trace_csv"
                    )
                    if accepted_artifact_matches:
                        reference_artifact_matches += 1
                        accepted_size_value: object = accepted_artifact.get(
                            "size_bytes",
                            None,
                        )
                        accepted_sha_value: object = accepted_artifact.get(
                            "sha256",
                            None,
                        )
                        accepted_identity_is_valid: bool = bool(
                            isinstance(accepted_size_value, int)
                            and not isinstance(accepted_size_value, bool)
                            and isinstance(accepted_sha_value, str)
                        )
                        if accepted_identity_is_valid:
                            matched_reference_path = accepted_trace_path
                            matched_reference_size = cast(int, accepted_size_value)
                            matched_reference_sha256 = cast(str, accepted_sha_value)
                        else:
                            raise ValueError("PathSim accepted trace identity changed")
                    else:
                        pass
            else:
                pass
        binding_is_unique: bool = bool(
            reference_cell_matches == 1
            and reference_artifact_matches == 1
            and isinstance(matched_reference_path, Path)
            and isinstance(matched_reference_size, int)
            and isinstance(matched_reference_sha256, str)
        )
        if binding_is_unique:
            bound_reference_path: Path = cast(Path, matched_reference_path)
            bound_reference_size: int = cast(int, matched_reference_size)
            bound_reference_sha256: str = cast(
                str,
                matched_reference_sha256,
            )
            verify_regular_file_identity(
                bound_reference_path,
                bound_reference_size,
                bound_reference_sha256,
            )
            bound_reference_paths[cell_index] = bound_reference_path
            expected_reference_records[cell_index] = {
                "cell_id": canonical_cell_id,
                "path": str(bound_reference_path),
                "size_bytes": bound_reference_size,
                "sha256": bound_reference_sha256,
            }
        else:
            raise ValueError("PathSim accepted reference binding is ambiguous")

    expected_corpus: dict[str, object] = {
        "catalog_path": str(config.catalog_path),
        "catalog_size_bytes": config.catalog_size_bytes,
        "catalog_sha256": config.catalog_sha256,
        "release_tag": "v0.0.41",
        "archive_path": str(config.archive_path),
        "archive_size_bytes": config.archive_size_bytes,
        "archive_sha256": config.archive_sha256,
        "fmus": expected_fmu_records,
    }
    expected_reference: dict[str, object] = {
        "manifest_path": str(config.reference_manifest_path),
        "manifest_size_bytes": config.reference_manifest_size_bytes,
        "manifest_sha256": config.reference_manifest_sha256,
        "traces": expected_reference_records,
    }
    corpus_json: str = json.dumps(corpus, ensure_ascii=False, separators=(",", ":"))
    expected_corpus_json: str = json.dumps(
        expected_corpus,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    reference_json: str = json.dumps(
        reference,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    expected_reference_json: str = json.dumps(
        expected_reference,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    if corpus_json == expected_corpus_json and reference_json == expected_reference_json:
        pass
    else:
        raise ValueError("PathSim corpus or reference records are not exact")

    # Establish the complete canonical path set before joining or opening any
    # manifest-provided relative path.
    expected_package_names: list[str] = [""] * 34
    package_name_index: int = 0
    passing_cell_indices: tuple[int, int, int, int] = (0, 1, 4, 5)
    for cell_index in range(8):
        raw_prefix: str = f"raw/cell-{cell_index:02d}"
        expected_package_names[package_name_index] = f"{raw_prefix}/result.json"
        package_name_index += 1
        expected_package_names[package_name_index] = f"{raw_prefix}/stderr.log"
        package_name_index += 1
        expected_package_names[package_name_index] = f"{raw_prefix}/stdout.log"
        package_name_index += 1
        if cell_index in passing_cell_indices:
            expected_package_names[package_name_index] = f"{raw_prefix}/trace.csv"
            package_name_index += 1
        else:
            pass
    expected_figure_names: tuple[str, ...] = (
        "figures/bouncing-ball-overlay.pdf",
        "figures/bouncing-ball-overlay.png",
        "figures/bouncing-ball-overlay.svg",
        "figures/capability-matrix.pdf",
        "figures/capability-matrix.png",
        "figures/capability-matrix.svg",
    )
    for expected_figure_name in expected_figure_names:
        expected_package_names[package_name_index] = expected_figure_name
        package_name_index += 1
    if package_name_index == 34:
        pass
    else:
        raise ValueError("PathSim expected package cardinality changed")
    expected_package_names.sort()
    declared_package_names: list[str] = [""] * 34
    for file_index in range(34):
        file_record_value: object = file_records[file_index]
        if isinstance(file_record_value, dict) and tuple(
            file_record_value.keys()
        ) == ("path", "size_bytes", "sha256"):
            checked_file_record: dict[str, object] = cast(
                dict[str, object],
                file_record_value,
            )
        else:
            raise ValueError("PathSim file record shape changed")
        checked_relative_value: object = checked_file_record["path"]
        if isinstance(checked_relative_value, str):
            declared_package_names[file_index] = checked_relative_value
        else:
            raise ValueError("PathSim file record path is not text")
    if declared_package_names == expected_package_names:
        pass
    else:
        raise ValueError("PathSim package paths are not canonical")

    # Reject links and special entries before opening any package member.  The
    # manifest is the only file intentionally excluded from package_files.
    discovered_package_names: list[str] = [""] * 35
    discovered_package_index: int = 0
    for discovered_package_path in package_root.rglob("*"):
        if path_is_link_or_reparse_point(discovered_package_path):
            raise ValueError("PathSim package contains a link")
        else:
            if discovered_package_path.is_file():
                if discovered_package_index < 35:
                    discovered_package_names[discovered_package_index] = (
                        discovered_package_path.relative_to(package_root).as_posix()
                    )
                    discovered_package_index += 1
                else:
                    raise ValueError("PathSim package file count changed")
            else:
                if discovered_package_path.is_dir():
                    pass
                else:
                    raise ValueError("PathSim package contains a special entry")
    expected_discovered_names: list[str] = [""] * 35
    expected_discovered_names[0] = "manifest.json"
    for expected_package_index in range(34):
        expected_discovered_names[expected_package_index + 1] = (
            expected_package_names[expected_package_index]
        )
    expected_discovered_names.sort()
    discovered_package_names.sort()
    discovered_tree_is_exact: bool = bool(
        discovered_package_index == 35
        and discovered_package_names == expected_discovered_names
    )
    if discovered_tree_is_exact:
        pass
    else:
        raise ValueError("PathSim package contains an undeclared path")
    for file_index in range(34):
        checked_file_record = cast(dict[str, object], file_records[file_index])
        checked_relative_name: str = expected_package_names[file_index]
        checked_file_path: Path = package_root / Path(checked_relative_name)
        checked_content: bytes = checked_file_path.read_bytes()
        expected_file_record: dict[str, object] = {
            "path": checked_relative_name,
            "size_bytes": len(checked_content),
            "sha256": hashlib.sha256(checked_content).hexdigest(),
        }
        checked_record_json: str = json.dumps(
            checked_file_record,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        expected_record_json: str = json.dumps(
            expected_file_record,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if checked_record_json == expected_record_json:
            pass
        else:
            raise ValueError("PathSim package file identity is not exact")

    # Reconstruct every typed cell from raw evidence and compare its complete
    # declarative record, including all numerical and event metrics.
    reconstructed_cells: list[PathSimCellResult | None] = [None] * 8
    for cell_index in range(8):
        verified_case = verified_catalog.cases[cell_index // 2]
        verified_interface = verified_case.interfaces[cell_index % 2]
        raw_cell_relative: Path = Path("raw") / f"cell-{cell_index:02d}"
        result_relative: Path = raw_cell_relative / "result.json"
        stdout_relative: Path = raw_cell_relative / "stdout.log"
        stderr_relative: Path = raw_cell_relative / "stderr.log"
        trace_relative: Path = raw_cell_relative / "trace.csv"
        result_file_path: Path = package_root / result_relative
        stdout_file_path: Path = package_root / stdout_relative
        stderr_file_path: Path = package_root / stderr_relative
        trace_file_path: Path = package_root / trace_relative
        stdout_content: bytes = stdout_file_path.read_bytes()
        stderr_content: bytes = stderr_file_path.read_bytes()
        streams_are_bounded: bool = bool(
            len(stdout_content) <= config.stream_limit_bytes
            and len(stderr_content) <= config.stream_limit_bytes
        )
        if streams_are_bounded:
            pass
        else:
            raise ValueError("PathSim package stream exceeds its configured bound")
        if verified_interface == FmuInterfaceMode.CO_SIMULATION:
            interface_argument: str = "co_simulation"
        else:
            interface_argument = "model_exchange"
        verified_oracle: ReferenceFmuEventOracle = verified_case.find_interface_oracle(
            verified_interface
        )
        verification_arguments: tuple[str, ...] = (
            str(config.python_executable_path),
            "-B",
            "-I",
            str(config.worker_path),
            "--fmu",
            str(config.fmu_paths[cell_index // 2]),
            "--result",
            str(result_file_path),
            "--trace",
            str(trace_file_path),
            "--interface",
            interface_argument,
            "--output",
            verified_oracle.observed_variable_name,
            "--start",
            repr(verified_case.start_time_seconds),
            "--stop",
            repr(verified_case.declared_stop_time_seconds),
            "--step",
            repr(verified_case.step_size_seconds),
        )
        reconstructed_process: PathSimProcessResult = PathSimProcessResult(
            verification_arguments,
            0,
            0.0,
            len(stdout_content),
            hashlib.sha256(stdout_content).hexdigest(),
            len(stderr_content),
            hashlib.sha256(stderr_content).hexdigest(),
        )
        reconstructed_worker: PathSimWorkerResult = _read_pathsim_worker_result(
            result_file_path
        )
        reference_path_value: Path | None = bound_reference_paths[cell_index]
        if isinstance(reference_path_value, Path):
            reconstructed_reference_path: Path = reference_path_value
        else:
            raise ValueError("PathSim reconstructed reference path is absent")
        reconstructed_cell: PathSimCellResult = _evaluate_pathsim_cell(
            cell_index,
            verified_case,
            verified_interface,
            reconstructed_worker,
            reconstructed_process,
            result_relative,
            stdout_relative,
            stderr_relative,
            trace_file_path,
            trace_relative,
            reconstructed_reference_path,
        )
        if reconstructed_cell.finding_kind is None:
            reconstructed_finding: str | None = None
        else:
            reconstructed_finding = reconstructed_cell.finding_kind.value
        if reconstructed_cell.trace_path is None:
            reconstructed_trace_path: str | None = None
        else:
            reconstructed_trace_path = reconstructed_cell.trace_path.as_posix()
        expected_cell_record: dict[str, object] = {
            "cell_index": reconstructed_cell.cell_index,
            "cell_id": reconstructed_cell.cell_id,
            "case_id": reconstructed_cell.case.case_id,
            "fmi_version": reconstructed_cell.case.fmi_version.value,
            "model_name": reconstructed_cell.case.model_name,
            "event_mechanism": verified_oracle.mechanism.value,
            "interface_mode": reconstructed_cell.interface_mode.value,
            "status": reconstructed_cell.status.value,
            "finding_kind": reconstructed_finding,
            "raw_result_path": reconstructed_cell.raw_result_path.as_posix(),
            "stdout_path": reconstructed_cell.stdout_path.as_posix(),
            "stderr_path": reconstructed_cell.stderr_path.as_posix(),
            "trace_path": reconstructed_trace_path,
            "reference_trace_path": str(reconstructed_cell.reference_trace_path),
            "sample_count": reconstructed_cell.sample_count,
            "event_count": int(reconstructed_cell.event_times_seconds.size),
            "maximum_absolute_error": reconstructed_cell.maximum_absolute_error,
            "rms_absolute_error": reconstructed_cell.rms_absolute_error,
            "maximum_event_time_error_seconds": (
                reconstructed_cell.maximum_event_time_error_seconds
            ),
            "fmi_function": reconstructed_cell.fmi_function,
            "fmi_status": reconstructed_cell.fmi_status,
        }
        manifest_cell_value: object = cells[cell_index]
        if isinstance(manifest_cell_value, dict) and tuple(
            manifest_cell_value.keys()
        ) == (
            "cell_index", "cell_id", "case_id", "fmi_version", "model_name",
            "event_mechanism", "interface_mode", "status", "finding_kind",
            "raw_result_path", "stdout_path", "stderr_path", "trace_path",
            "reference_trace_path", "sample_count", "event_count",
            "maximum_absolute_error", "rms_absolute_error",
            "maximum_event_time_error_seconds", "fmi_function", "fmi_status",
        ):
            manifest_cell: dict[str, object] = cast(
                dict[str, object],
                manifest_cell_value,
            )
        else:
            raise ValueError("PathSim cell record order or keys changed")
        manifest_cell_json: str = json.dumps(
            manifest_cell,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        expected_cell_json: str = json.dumps(
            expected_cell_record,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if manifest_cell_json == expected_cell_json:
            reconstructed_cells[cell_index] = reconstructed_cell
        else:
            raise ValueError("PathSim cell differs from reconstructed evidence")

    complete_reconstructed_cells: tuple[PathSimCellResult, ...] = (
        cast(PathSimCellResult, reconstructed_cells[0]),
        cast(PathSimCellResult, reconstructed_cells[1]),
        cast(PathSimCellResult, reconstructed_cells[2]),
        cast(PathSimCellResult, reconstructed_cells[3]),
        cast(PathSimCellResult, reconstructed_cells[4]),
        cast(PathSimCellResult, reconstructed_cells[5]),
        cast(PathSimCellResult, reconstructed_cells[6]),
        cast(PathSimCellResult, reconstructed_cells[7]),
    )

    expected_cell_keys: set[str] = {
        "cell_index", "cell_id", "case_id", "fmi_version", "model_name",
        "event_mechanism", "interface_mode", "status", "finding_kind",
        "raw_result_path", "stdout_path", "stderr_path", "trace_path",
        "reference_trace_path", "sample_count", "event_count",
        "maximum_absolute_error", "rms_absolute_error",
        "maximum_event_time_error_seconds", "fmi_function", "fmi_status",
    }
    pass_count: int = 0
    finding_count: int = 0
    for cell_index in range(8):
        cell_value: object = cells[cell_index]
        if isinstance(cell_value, dict) and set(cell_value.keys()) == expected_cell_keys:
            cell_record: dict[str, object] = cast(dict[str, object], cell_value)
        else:
            raise ValueError("PathSim cell keys changed")
        if cell_record["cell_index"] == cell_index:
            pass
        else:
            raise ValueError("PathSim cell order changed")
        if cell_record["status"] == "PASS":
            pass_count += 1
            pass_shape_is_valid: bool = bool(
                cell_record["finding_kind"] is None
                and isinstance(cell_record["trace_path"], str)
                and isinstance(cell_record["maximum_absolute_error"], float)
                and isinstance(cell_record["rms_absolute_error"], float)
                and isinstance(cell_record["maximum_event_time_error_seconds"], float)
                and cell_record["fmi_function"] is None
                and cell_record["fmi_status"] is None
            )
            if pass_shape_is_valid:
                pass
            else:
                raise ValueError("PathSim PASS cell shape changed")
        else:
            if cell_record["status"] == "COMPLETED_WITH_FINDINGS":
                finding_count += 1
                finding_shape_is_valid: bool = bool(
                    cell_record["finding_kind"] == "unsupported_scalar_output"
                    and cell_record["trace_path"] is None
                    and cell_record["sample_count"] == 0
                    and cell_record["fmi_status"] == 3
                )
                if finding_shape_is_valid:
                    pass
                else:
                    raise ValueError("PathSim finding cell shape changed")
            else:
                raise ValueError("PathSim cell status changed")
    if pass_count == 4 and finding_count == 4:
        pass
    else:
        raise ValueError("PathSim result counts changed")

    # Re-render from reconstructed numerical evidence. Exact bytes establish
    # that the PNG, SVG and PDF files represent these eight cells rather than
    # unrelated content with plausible dimensions or metadata.
    figure_verification_root: Path = Path(
        tempfile.mkdtemp(
            prefix=".pathsim-figure-verification-",
            dir=package_root.parent,
        )
    )
    try:
        _render_pathsim_figures(
            figure_verification_root,
            complete_reconstructed_cells,
        )
        for figure_relative_name in expected_figure_names:
            published_figure_bytes: bytes = (
                package_root / Path(figure_relative_name)
            ).read_bytes()
            reconstructed_figure_bytes: bytes = (
                figure_verification_root / Path(figure_relative_name)
            ).read_bytes()
            if published_figure_bytes == reconstructed_figure_bytes:
                pass
            else:
                raise ValueError(
                    "PathSim figure differs from reconstructed evidence"
                )
    finally:
        figure_cleanup_is_scoped: bool = bool(
            figure_verification_root.parent == package_root.parent
            and figure_verification_root.name.startswith(
                ".pathsim-figure-verification-"
            )
        )
        if figure_cleanup_is_scoped and figure_verification_root.exists():
            shutil.rmtree(figure_verification_root)
        else:
            if figure_verification_root.exists():
                raise RuntimeError("Refusing unscoped figure-verification cleanup")
            else:
                pass

    expected_figures: tuple[tuple[str, int, int], tuple[str, int, int]] = (
        ("bouncing-ball-overlay", 2160, 2100),
        ("capability-matrix", 2160, 1380),
    )
    expected_figure_records: tuple[dict[str, object], dict[str, object]] = (
        {
            "figure_id": "bouncing-ball-overlay",
            "png_path": "figures/bouncing-ball-overlay.png",
            "svg_path": "figures/bouncing-ball-overlay.svg",
            "pdf_path": "figures/bouncing-ball-overlay.pdf",
            "width_inches": 7.2,
            "height_inches": 7.0,
            "png_width_pixels": 2160,
            "png_height_pixels": 2100,
            "dpi": 300,
            "font_family": "DejaVu Sans",
        },
        {
            "figure_id": "capability-matrix",
            "png_path": "figures/capability-matrix.png",
            "svg_path": "figures/capability-matrix.svg",
            "pdf_path": "figures/capability-matrix.pdf",
            "width_inches": 7.2,
            "height_inches": 4.6,
            "png_width_pixels": 2160,
            "png_height_pixels": 1380,
            "dpi": 300,
            "font_family": "DejaVu Sans",
        },
    )
    required_svg_tokens: tuple[tuple[str, ...], tuple[str, ...]] = (
        (
            "FMPy reference",
            "PathSim-FMI",
            "FMI 2.0",
            "FMI 3.0",
            "Co-Simulation",
            "Model Exchange",
            "Velocity [m/s]",
            "Time [s]",
        ),
        (
            "PathSim-FMI 0.1.1 attempted interoperability",
            "FMI 2.0",
            "FMI 3.0",
            "state event",
            "time event",
            "PASS",
            "Finding",
            "Co-Simulation",
            "Model Exchange",
        ),
    )
    expected_svg_heights: tuple[str, str] = ("504pt", "331.2pt")
    expected_pdf_media_boxes: tuple[bytes, bytes] = (
        b"/MediaBox [ 0 0 518.4 504 ]",
        b"/MediaBox [ 0 0 518.4 331.2 ]",
    )
    expected_figure_keys: set[str] = {
        "figure_id", "png_path", "svg_path", "pdf_path", "width_inches",
        "height_inches", "png_width_pixels", "png_height_pixels", "dpi",
        "font_family",
    }
    for figure_index in range(2):
        figure_value: object = figures[figure_index]
        if isinstance(figure_value, dict) and set(figure_value.keys()) == expected_figure_keys:
            figure_record: dict[str, object] = cast(dict[str, object], figure_value)
        else:
            raise ValueError("PathSim figure record changed")
        expected_figure_id: str = expected_figures[figure_index][0]
        expected_width_pixels: int = expected_figures[figure_index][1]
        expected_height_pixels: int = expected_figures[figure_index][2]
        expected_figure_record: dict[str, object] = expected_figure_records[
            figure_index
        ]
        figure_record_json: str = json.dumps(
            figure_record,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        expected_figure_json: str = json.dumps(
            expected_figure_record,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        png_path_value: object = figure_record["png_path"]
        figure_matches: bool = bool(
            figure_record_json == expected_figure_json
            and figure_record["figure_id"] == expected_figure_id
            and figure_record["png_width_pixels"] == expected_width_pixels
            and figure_record["png_height_pixels"] == expected_height_pixels
            and figure_record["dpi"] == 300
            and figure_record["font_family"] == "DejaVu Sans"
            and isinstance(png_path_value, str)
        )
        if figure_matches:
            png_data: np.ndarray = mpimg.imread(
                package_root / cast(str, png_path_value)
            )
        else:
            raise ValueError("PathSim figure contract changed")
        png_dimensions_are_exact: bool = bool(
            png_data.shape[1] == expected_width_pixels
            and png_data.shape[0] == expected_height_pixels
        )
        if png_dimensions_are_exact:
            pass
        else:
            raise ValueError("PathSim PNG dimensions changed")
        svg_path_value: object = figure_record["svg_path"]
        pdf_path_value: object = figure_record["pdf_path"]
        if isinstance(svg_path_value, str) and isinstance(pdf_path_value, str):
            svg_path: Path = package_root / Path(svg_path_value)
            pdf_path: Path = package_root / Path(pdf_path_value)
            svg_text: str = svg_path.read_text(encoding="utf-8", errors="strict")
            pdf_bytes: bytes = pdf_path.read_bytes()
        else:
            raise ValueError("PathSim vector figure paths changed")
        try:
            svg_root: element_tree.Element = element_tree.fromstring(svg_text)
        except element_tree.ParseError as error:
            raise ValueError("PathSim SVG is malformed") from error
        svg_text_nodes: list[str] = list()
        for svg_element in svg_root.iter():
            element_name: str = svg_element.tag.rsplit("}", 1)[-1]
            if element_name == "text":
                node_text: str = "".join(svg_element.itertext())
                svg_text_nodes.append(node_text)
            else:
                pass
        svg_text_content: str = "\n".join(svg_text_nodes)
        svg_width_is_exact: bool = 'width="518.4pt"' in svg_text
        svg_height_is_exact: bool = bool(
            f'height="{expected_svg_heights[figure_index]}"' in svg_text
        )
        missing_svg_tokens: tuple[str, ...] = tuple(
            required_token
            for required_token in required_svg_tokens[figure_index]
            if required_token not in svg_text_content
        )
        svg_geometry_is_exact: bool = bool(
            svg_width_is_exact
            and svg_height_is_exact
            and len(svg_text_nodes) > 0
            and len(missing_svg_tokens) == 0
        )
        pdf_contract_is_exact: bool = bool(
            expected_pdf_media_boxes[figure_index] in pdf_bytes
            and b"/Subtype /Type0" in pdf_bytes
            and b"/Subtype /CIDFontType2" in pdf_bytes
            and b"/FontFile2" in pdf_bytes
        )
        if svg_geometry_is_exact:
            pass
        else:
            raise ValueError(
                "PathSim SVG contract changed: "
                f"width={svg_width_is_exact}, height={svg_height_is_exact}, "
                f"missing={missing_svg_tokens}"
            )
        if pdf_contract_is_exact:
            pass
        else:
            raise ValueError("PathSim PDF contract changed")

    # Detect external-input replacement that occurs while the package itself is
    # being reopened and recomputed.
    final_runtime_identity: tuple[int, int, str] = read_regular_tree_identity(
        config.runtime_root
    )
    if final_runtime_identity == expected_runtime_identity:
        pass
    else:
        raise ValueError("PathSim runtime changed during package verification")
    verify_regular_file_identity(
        config.python_executable_path,
        config.python_executable_size_bytes,
        config.python_executable_sha256,
    )
    verify_regular_file_identity(
        config.worker_path,
        config.worker_size_bytes,
        config.worker_sha256,
    )
    for reference_record_index in range(8):
        reference_path_value: Path | None = bound_reference_paths[
            reference_record_index
        ]
        if isinstance(reference_path_value, Path):
            reference_content: bytes = reference_path_value.read_bytes()
            expected_reference_record: dict[str, object] = (
                expected_reference_records[reference_record_index]
            )
            reference_identity_is_stable: bool = bool(
                len(reference_content)
                == expected_reference_record["size_bytes"]
                and hashlib.sha256(reference_content).hexdigest()
                == expected_reference_record["sha256"]
            )
            if reference_identity_is_stable:
                pass
            else:
                raise ValueError("PathSim reference trace changed during verification")
        else:
            raise ValueError("PathSim reference trace binding was lost")

    # Close the package after all reconstruction work. A member replaced after
    # the initial traversal cannot survive as a link, special entry, changed
    # byte sequence or undeclared path at the successful return boundary.
    final_root_is_regular: bool = bool(
        package_root.exists()
        and package_root.is_dir()
        and not path_is_link_or_reparse_point(package_root)
        and manifest_path.exists()
        and manifest_path.is_file()
        and not path_is_link_or_reparse_point(manifest_path)
        and manifest_path.read_bytes() == manifest_bytes
    )
    if final_root_is_regular:
        pass
    else:
        raise ValueError("PathSim package root changed during verification")
    final_discovered_names: list[str] = [""] * 35
    final_discovered_index: int = 0
    for final_discovered_path in package_root.rglob("*"):
        if path_is_link_or_reparse_point(final_discovered_path):
            raise ValueError("PathSim package acquired a link during verification")
        else:
            if final_discovered_path.is_file():
                if final_discovered_index < 35:
                    final_discovered_names[final_discovered_index] = (
                        final_discovered_path.relative_to(package_root).as_posix()
                    )
                    final_discovered_index += 1
                else:
                    raise ValueError("PathSim package acquired an extra file")
            else:
                if final_discovered_path.is_dir():
                    pass
                else:
                    raise ValueError(
                        "PathSim package acquired a special entry during verification"
                    )
    final_discovered_names.sort()
    final_tree_is_exact: bool = bool(
        final_discovered_index == 35
        and final_discovered_names == expected_discovered_names
    )
    if final_tree_is_exact:
        pass
    else:
        raise ValueError("PathSim package tree changed during verification")
    for final_file_index in range(34):
        final_file_record: dict[str, object] = cast(
            dict[str, object],
            file_records[final_file_index],
        )
        final_relative_name: str = cast(str, final_file_record["path"])
        final_size_bytes: int = cast(int, final_file_record["size_bytes"])
        final_sha256: str = cast(str, final_file_record["sha256"])
        final_file_path: Path = package_root / Path(final_relative_name)
        final_file_is_regular: bool = bool(
            final_file_path.exists()
            and final_file_path.is_file()
            and not path_is_link_or_reparse_point(final_file_path)
            and final_file_path.stat().st_size == final_size_bytes
        )
        if final_file_is_regular:
            final_file_bytes: bytes = final_file_path.read_bytes()
        else:
            raise ValueError("PathSim package member changed during verification")
        final_file_identity_is_exact: bool = bool(
            len(final_file_bytes) == final_size_bytes
            and hashlib.sha256(final_file_bytes).hexdigest() == final_sha256
            and final_file_path.exists()
            and final_file_path.is_file()
            and not path_is_link_or_reparse_point(final_file_path)
            and final_file_path.stat().st_size == final_size_bytes
        )
        if final_file_identity_is_exact:
            pass
        else:
            raise ValueError("PathSim package member changed during verification")


def generate_pathsim_comparison(config: PathSimComparisonConfig) -> Path:
    """Execute all eight PathSim cells and atomically publish their evidence.

    :param config: Closed authenticated PathSim comparison configuration.
    :return: Published package manifest path.
    """

    catalog: ReferenceFmuCatalog
    assets: tuple[ValidatedReferenceFmuAsset, ...]
    catalog, assets = _validate_pathsim_config(config)
    reference_manifest: dict[str, object] = _read_reference_execution_manifest(
        config
    )
    staging_root: Path = Path(
        tempfile.mkdtemp(
            prefix=".pathsim-comparison-",
            dir=config.output_directory.parent,
        )
    )
    published: bool = False
    try:
        raw_root: Path = staging_root / "raw"
        work_root: Path = staging_root / "work"
        raw_root.mkdir()
        work_root.mkdir()
        reference_cells_value: object = reference_manifest["cells"]
        reference_artifacts_value: object = reference_manifest["artifacts"]
        reference_cells: list[object] = cast(
            list[object],
            reference_cells_value,
        )
        reference_artifacts: list[object] = cast(
            list[object],
            reference_artifacts_value,
        )
        cell_results: list[PathSimCellResult] = [
            cast(PathSimCellResult, None)
        ] * 8
        worker_source: bytes = verify_regular_file_identity(
            config.worker_path,
            config.worker_size_bytes,
            config.worker_sha256,
        )
        for case_index in range(4):
            case: ReferenceFmuCase = catalog.cases[case_index]
            asset: ValidatedReferenceFmuAsset = assets[case_index]
            for interface_index in range(2):
                cell_index: int = 2 * case_index + interface_index
                interface_mode: FmuInterfaceMode = case.interfaces[interface_index]
                raw_cell_relative: Path = Path("raw") / f"cell-{cell_index:02d}"
                raw_cell_root: Path = staging_root / raw_cell_relative
                raw_cell_root.mkdir()
                work_cell_root: Path = work_root / f"cell-{cell_index:02d}"
                work_cell_root.mkdir()
                temp_root: Path = work_cell_root / "temp"
                temp_root.mkdir()

                # Each child receives private immutable copies so neither the
                # repository worker nor the authenticated corpus is executable in place.
                staged_worker_path: Path = work_cell_root / "pathsim_worker.py"
                staged_worker_path.write_bytes(worker_source)
                staged_fmu_path: Path = work_cell_root / "model.fmu"
                staged_fmu_path.write_bytes(asset.content)
                verify_regular_file_identity(
                    staged_worker_path,
                    config.worker_size_bytes,
                    config.worker_sha256,
                )
                verify_regular_file_identity(
                    staged_fmu_path,
                    case.fmu_size_bytes,
                    case.fmu_sha256,
                )

                # Resolve the accepted FMPy peer by semantic identity, then bind
                # its file through the manifest artifact record before use.
                reference_trace_path: Path | None = None
                reference_trace_size: int | None = None
                reference_trace_sha256: str | None = None
                reference_cell_match_count: int = 0
                reference_artifact_match_count: int = 0
                reference_interface_name: str = interface_mode.value
                for reference_cell_value in reference_cells:
                    if isinstance(reference_cell_value, dict):
                        reference_cell: dict[str, object] = cast(
                            dict[str, object],
                            reference_cell_value,
                        )
                    else:
                        raise ValueError("Accepted reference cell is invalid")
                    cell_matches: bool = bool(
                        reference_cell.get("case_id", None) == case.case_id
                        and reference_cell.get("interface_mode", None)
                        == reference_interface_name
                        and reference_cell.get("tool", None) == "fmpy"
                        and reference_cell.get("status", None)
                        in ("pass", "pass_with_observability_limit")
                    )
                    if cell_matches:
                        reference_cell_match_count += 1
                        relative_trace_value: object = reference_cell.get(
                            "raw_trace_path",
                            None,
                        )
                        reference_cell_id: object = reference_cell.get(
                            "cell_id",
                            None,
                        )
                        reference_binding_shape_is_valid: bool = bool(
                            isinstance(relative_trace_value, str)
                            and isinstance(reference_cell_id, str)
                        )
                        if reference_binding_shape_is_valid:
                            candidate_trace_path: Path = (
                                config.reference_manifest_path.parent
                                / Path(relative_trace_value)
                            )
                        else:
                            raise ValueError("Accepted reference trace path is invalid")
                        for artifact_value in reference_artifacts:
                            if isinstance(artifact_value, dict):
                                artifact: dict[str, object] = cast(
                                    dict[str, object],
                                    artifact_value,
                                )
                            else:
                                raise ValueError("Accepted reference artifact is invalid")
                            artifact_matches: bool = bool(
                                artifact.get("path", None) == relative_trace_value
                                and artifact.get("cell_id", None) == reference_cell_id
                                and artifact.get("kind", None) == "trace_csv"
                            )
                            if artifact_matches:
                                reference_artifact_match_count += 1
                                size_value: object = artifact.get("size_bytes", None)
                                digest_value: object = artifact.get("sha256", None)
                                if (
                                    isinstance(size_value, int)
                                    and not isinstance(size_value, bool)
                                    and isinstance(digest_value, str)
                                ):
                                    reference_trace_path = candidate_trace_path
                                    reference_trace_size = size_value
                                    reference_trace_sha256 = digest_value
                                else:
                                    raise ValueError("Accepted trace identity is invalid")
                            else:
                                pass
                    else:
                        pass
                reference_binding_is_unique: bool = bool(
                    reference_cell_match_count == 1
                    and reference_artifact_match_count == 1
                    and isinstance(reference_trace_path, Path)
                    and isinstance(reference_trace_size, int)
                    and isinstance(reference_trace_sha256, str)
                )
                if reference_binding_is_unique:
                    bound_reference_path: Path = cast(Path, reference_trace_path)
                    bound_reference_size: int = cast(int, reference_trace_size)
                    bound_reference_sha256: str = cast(str, reference_trace_sha256)
                    verify_regular_file_identity(
                        bound_reference_path,
                        bound_reference_size,
                        bound_reference_sha256,
                    )
                else:
                    raise ValueError(
                        "Accepted FMPy trace is absent or ambiguous for "
                        f"{case.case_id} {reference_interface_name}"
                    )

                result_relative: Path = raw_cell_relative / "result.json"
                stdout_relative: Path = raw_cell_relative / "stdout.log"
                stderr_relative: Path = raw_cell_relative / "stderr.log"
                trace_relative: Path = raw_cell_relative / "trace.csv"
                result_path: Path = staging_root / result_relative
                stdout_path: Path = staging_root / stdout_relative
                stderr_path: Path = staging_root / stderr_relative
                trace_path: Path = staging_root / trace_relative
                if interface_mode == FmuInterfaceMode.CO_SIMULATION:
                    interface_argument: str = "co_simulation"
                else:
                    interface_argument = "model_exchange"
                oracle: ReferenceFmuEventOracle = case.find_interface_oracle(
                    interface_mode
                )
                arguments: tuple[str, ...] = (
                    str(config.python_executable_path),
                    "-B",
                    "-I",
                    str(staged_worker_path),
                    "--fmu",
                    str(staged_fmu_path),
                    "--result",
                    str(result_path),
                    "--trace",
                    str(trace_path),
                    "--interface",
                    interface_argument,
                    "--output",
                    oracle.observed_variable_name,
                    "--start",
                    repr(case.start_time_seconds),
                    "--stop",
                    repr(case.declared_stop_time_seconds),
                    "--step",
                    repr(case.step_size_seconds),
                )
                child_environment: dict[str, str] = {
                    "PROCESSOR_ARCHITECTURE": config.processor_architecture,
                    "SystemRoot": str(config.system_root_path),
                    "TEMP": str(temp_root),
                    "TMP": str(temp_root),
                }
                process_result: PathSimProcessResult = _run_pathsim_worker(
                    config,
                    arguments,
                    child_environment,
                    work_cell_root,
                    stdout_path,
                    stderr_path,
                )

                # Reauthenticate all executable inputs after the native process
                # exits so a passing result cannot hide input mutation.
                verify_regular_file_identity(
                    config.worker_path,
                    config.worker_size_bytes,
                    config.worker_sha256,
                )
                verify_regular_file_identity(
                    staged_worker_path,
                    config.worker_size_bytes,
                    config.worker_sha256,
                )
                verify_regular_file_identity(
                    config.fmu_paths[case_index],
                    case.fmu_size_bytes,
                    case.fmu_sha256,
                )
                verify_regular_file_identity(
                    staged_fmu_path,
                    case.fmu_size_bytes,
                    case.fmu_sha256,
                )
                verify_regular_file_identity(
                    bound_reference_path,
                    bound_reference_size,
                    bound_reference_sha256,
                )
                worker_result: PathSimWorkerResult = _read_pathsim_worker_result(
                    result_path
                )
                cell_results[cell_index] = _evaluate_pathsim_cell(
                    cell_index,
                    case,
                    interface_mode,
                    worker_result,
                    process_result,
                    result_relative,
                    stdout_relative,
                    stderr_relative,
                    trace_path,
                    trace_relative,
                    bound_reference_path,
                )
                shutil.rmtree(work_cell_root)
        shutil.rmtree(work_root)

        # The external environment is immutable evidence, so the full tree and
        # executable must retain the same identity after all eight processes.
        final_runtime_identity: tuple[int, int, str] = read_regular_tree_identity(
            config.runtime_root
        )
        if final_runtime_identity == (
            config.runtime_entry_count,
            config.runtime_regular_bytes,
            config.runtime_tree_sha256,
        ):
            pass
        else:
            raise ValueError("PathSim runtime changed during execution")
        verify_regular_file_identity(
            config.python_executable_path,
            config.python_executable_size_bytes,
            config.python_executable_sha256,
        )
        closed_cells: tuple[PathSimCellResult, ...] = tuple(cell_results)
        figure_contracts: tuple[dict[str, object], dict[str, object]] = (
            _render_pathsim_figures(staging_root, closed_cells)
        )
        _write_pathsim_manifest(
            config,
            catalog,
            closed_cells,
            figure_contracts,
            staging_root,
        )
        _verify_pathsim_package(config, staging_root)
        staging_root.rename(config.output_directory)
        published = True
    finally:
        if published:
            pass
        else:
            if staging_root.exists():
                shutil.rmtree(staging_root)
            else:
                pass
    _verify_pathsim_package(config, config.output_directory)
    return config.output_directory / "manifest.json"
