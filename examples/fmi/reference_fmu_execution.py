# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Execute the sealed Reference FMU interoperability comparison matrix."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from enum import Enum
import hashlib
import io
from importlib import metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import tempfile
import time
from typing import BinaryIO, TextIO, cast
import warnings
import zipfile

import numpy as np
from fmpy import simulate_fmu

from VeraGridEngine.enumerations import FmuInterfaceMode, FmuVariableType
from examples.fmi.reference_fmu import (
    ReferenceFmuCase,
    ReferenceFmuCatalog,
    ReferenceFmuEventDetectionRule,
    ReferenceFmuEventOracle,
    ReferenceFmuTerminationKind,
    ValidatedReferenceFmuAsset,
    load_reference_fmu_catalog,
)


class ReferenceFmuExecutionTool(str, Enum):
    """Tools admitted to the fixed interoperability matrix."""

    FMPY = "fmpy"
    FMUSIM = "fmusim"


class ReferenceFmuAcceptanceBasis(str, Enum):
    """Independent evidence used to accept one matrix cell."""

    OFFICIAL_REFERENCE = "official_reference"
    TOOL_PAIR_AND_INTERFACE_ORACLE = "tool_pair_and_interface_oracle"


class ReferenceFmuCellStatus(str, Enum):
    """Successful cell outcomes exposed by the evidence package."""

    PASS = "pass"
    PASS_WITH_OBSERVABILITY_LIMIT = "pass_with_observability_limit"


class ReferenceFmuExecutionKind(str, Enum):
    """Execution boundaries used by supported comparison tools."""

    IN_PROCESS_PYTHON = "in_process_python"
    EXTERNAL_PROCESS = "external_process"


class ReferenceFmuArtifactKind(str, Enum):
    """Retained artifact kinds in the published evidence package."""

    TRACE_CSV = "trace_csv"
    STDOUT_LOG = "stdout_log"
    STDERR_LOG = "stderr_log"


class ReferenceFmuObservedTermination(str, Enum):
    """Termination observed by one completed tool execution."""

    CONFIGURED_STOP = "configured_stop"
    FMU_TERMINATION_BOUNDARY = "fmu_termination_boundary"


class ReferenceFmuTerminalObservation(str, Enum):
    """How the semantic terminal value appears in raw output."""

    TERMINAL_VALUE = "terminal_value"
    SUSTAINED_TERMINAL_VALUE = "sustained_terminal_value"
    PRE_TERMINAL_VALUE_ONLY = "pre_terminal_value_only"


class ReferenceFmuExecutionConfig:
    """Own validated caller-supplied paths and tool identities."""

    __slots__ = (
        "output_dir",
        "source_branch",
        "source_revision",
        "source_tree_sha256",
        "catalog_path",
        "corpus_root",
        "fmpy_expected_version",
        "fmpy_expected_distribution_sha256",
        "fmusim_executable",
        "fmusim_expected_size_bytes",
        "fmusim_expected_sha256",
        "fmusim_expected_version",
    )

    output_dir: Path
    source_branch: str
    source_revision: str
    source_tree_sha256: str
    catalog_path: Path
    corpus_root: Path
    fmpy_expected_version: str
    fmpy_expected_distribution_sha256: str
    fmusim_executable: Path
    fmusim_expected_size_bytes: int
    fmusim_expected_sha256: str
    fmusim_expected_version: str

    def __init__(
        self,
        output_dir: Path,
        source_branch: str,
        source_revision: str,
        source_tree_sha256: str,
        catalog_path: Path,
        corpus_root: Path,
        fmpy_expected_version: str,
        fmpy_expected_distribution_sha256: str,
        fmusim_executable: Path,
        fmusim_expected_size_bytes: int,
        fmusim_expected_sha256: str,
        fmusim_expected_version: str,
    ) -> None:
        """Validate explicit execution configuration.

        :param output_dir: Nonexistent final evidence directory.
        :param source_branch: Caller-observed source branch.
        :param source_revision: Caller-observed source commit.
        :param source_tree_sha256: Caller-computed source-tree digest.
        :param catalog_path: Explicit schema-v2 catalog path.
        :param corpus_root: Explicit root containing the pinned FMU paths.
        :param fmpy_expected_version: Required installed FMPy version.
        :param fmpy_expected_distribution_sha256: Required FMPy file digest.
        :param fmusim_executable: Explicit official fmusim executable.
        :param fmusim_expected_size_bytes: Required executable size.
        :param fmusim_expected_sha256: Required executable digest.
        :param fmusim_expected_version: Exact ``--version`` output.
        :return: None.
        """

        paths_are_typed: bool = bool(
            isinstance(output_dir, Path)
            and isinstance(catalog_path, Path)
            and isinstance(corpus_root, Path)
            and isinstance(fmusim_executable, Path)
        )
        text_values: tuple[object, ...] = (
            source_branch,
            source_revision,
            source_tree_sha256,
            fmpy_expected_version,
            fmpy_expected_distribution_sha256,
            fmusim_expected_sha256,
            fmusim_expected_version,
        )
        text_is_valid: bool = all(
            isinstance(value, str) and bool(value.strip())
            for value in text_values
        )
        identities_are_valid: bool = bool(
            source_branch == "devel_dynamics_rebuild"
            and re.fullmatch(r"[0-9a-f]{40}", source_revision) is not None
            and re.fullmatch(r"[0-9a-f]{64}", source_tree_sha256) is not None
            and fmpy_expected_version == "0.3.31"
            and fmpy_expected_distribution_sha256
            == "39eb2d78370dd241001e5724734f79caf2afcaafc968ba8f93afc597a0337e85"
            and isinstance(fmusim_expected_size_bytes, int)
            and not isinstance(fmusim_expected_size_bytes, bool)
            and fmusim_expected_size_bytes == 6_743_040
            and fmusim_expected_sha256
            == "e25529b1a52d441a2c9f284193ba135a418b66a5ef26cc82754bd479c98ba874"
            and fmusim_expected_version == "fmusim 0.10.0"
        )
        paths_are_valid: bool = bool(
            paths_are_typed
            and not output_dir.exists()
            and catalog_path.is_file()
            and not catalog_path.is_symlink()
            and corpus_root.is_dir()
            and not corpus_root.is_symlink()
        )
        if text_is_valid and identities_are_valid and paths_are_valid:
            pass
        else:
            raise ValueError("Reference FMU execution configuration is invalid")

        self.output_dir: Path = output_dir
        self.source_branch: str = source_branch
        self.source_revision: str = source_revision
        self.source_tree_sha256: str = source_tree_sha256
        self.catalog_path: Path = catalog_path
        self.corpus_root: Path = corpus_root
        self.fmpy_expected_version: str = fmpy_expected_version
        self.fmpy_expected_distribution_sha256: str = (
            fmpy_expected_distribution_sha256
        )
        self.fmusim_executable: Path = fmusim_executable
        self.fmusim_expected_size_bytes: int = fmusim_expected_size_bytes
        self.fmusim_expected_sha256: str = fmusim_expected_sha256
        self.fmusim_expected_version: str = fmusim_expected_version


class ReferenceFmuProcessResult:
    """Own bounded external-process evidence for one fmusim cell."""

    __slots__ = (
        "arguments",
        "return_code",
        "stdout_path",
        "stderr_path",
        "elapsed_seconds",
        "stdout_sha256",
        "stderr_sha256",
    )

    arguments: tuple[str, ...]
    return_code: int
    stdout_path: Path
    stderr_path: Path
    elapsed_seconds: float
    stdout_sha256: str
    stderr_sha256: str

    def __init__(
        self,
        arguments: tuple[str, ...],
        return_code: int,
        stdout_path: Path,
        stderr_path: Path,
        elapsed_seconds: float,
        stdout_sha256: str,
        stderr_sha256: str,
    ) -> None:
        """Validate retained process evidence.

        :param arguments: Exact shell-free process arguments.
        :param return_code: Observed process return code.
        :param stdout_path: Retained standard-output log.
        :param stderr_path: Retained standard-error log.
        :param elapsed_seconds: Monotonic elapsed execution time.
        :param stdout_sha256: Digest of retained standard output.
        :param stderr_sha256: Digest of retained standard error.
        :return: None.
        """

        values_are_valid: bool = bool(
            isinstance(arguments, tuple)
            and len(arguments) > 0
            and all(isinstance(argument, str) for argument in arguments)
            and isinstance(return_code, int)
            and not isinstance(return_code, bool)
            and isinstance(stdout_path, Path)
            and isinstance(stderr_path, Path)
            and isinstance(elapsed_seconds, (int, float))
            and not isinstance(elapsed_seconds, bool)
            and math.isfinite(float(elapsed_seconds))
            and float(elapsed_seconds) >= 0.0
            and re.fullmatch(r"[0-9a-f]{64}", stdout_sha256) is not None
            and re.fullmatch(r"[0-9a-f]{64}", stderr_sha256) is not None
        )
        if values_are_valid:
            pass
        else:
            raise ValueError("Reference FMU process result is invalid")
        self.arguments: tuple[str, ...] = arguments
        self.return_code: int = return_code
        self.stdout_path: Path = stdout_path
        self.stderr_path: Path = stderr_path
        self.elapsed_seconds: float = float(elapsed_seconds)
        self.stdout_sha256: str = stdout_sha256
        self.stderr_sha256: str = stderr_sha256


class ReferenceFmuTrace:
    """Own one typed raw event trace with immutable array payloads."""

    __slots__ = ("time_seconds", "observed_values", "observed_variable_type")

    time_seconds: np.ndarray
    observed_values: np.ndarray
    observed_variable_type: FmuVariableType

    def __init__(
        self,
        time_seconds: np.ndarray,
        observed_values: np.ndarray,
        observed_variable_type: FmuVariableType,
    ) -> None:
        """Validate and freeze raw trace arrays.

        :param time_seconds: Ordered finite event-preserving time samples.
        :param observed_values: Values aligned with ``time_seconds``.
        :param observed_variable_type: FMI scalar type retained by the trace.
        :return: None.
        """

        arrays_are_valid: bool = bool(
            isinstance(time_seconds, np.ndarray)
            and isinstance(observed_values, np.ndarray)
            and time_seconds.ndim == 1
            and observed_values.ndim == 1
            and time_seconds.size == observed_values.size
            and time_seconds.size >= 2
            and time_seconds.dtype == np.dtype(np.float64)
            and np.all(np.isfinite(time_seconds))
            and np.all(np.diff(time_seconds) >= 0.0)
            and isinstance(observed_variable_type, FmuVariableType)
        )
        integer_type: bool = bool(
            observed_variable_type
            in (FmuVariableType.INTEGER, FmuVariableType.INT32)
        )
        if integer_type:
            value_type_is_valid: bool = bool(
                observed_values.dtype == np.dtype(np.int32)
            )
        else:
            value_type_is_valid = bool(
                observed_variable_type
                in (FmuVariableType.REAL, FmuVariableType.FLOAT64)
                and observed_values.dtype == np.dtype(np.float64)
                and np.all(np.isfinite(observed_values))
            )
        if arrays_are_valid and value_type_is_valid:
            pass
        else:
            raise ValueError("Reference FMU trace is invalid")

        immutable_time: np.ndarray = np.frombuffer(
            np.ascontiguousarray(time_seconds, dtype=np.float64).tobytes(),
            dtype=np.float64,
        )
        if integer_type:
            immutable_values: np.ndarray = np.frombuffer(
                np.ascontiguousarray(observed_values, dtype=np.int32).tobytes(),
                dtype=np.int32,
            )
        else:
            immutable_values = np.frombuffer(
                np.ascontiguousarray(observed_values, dtype=np.float64).tobytes(),
                dtype=np.float64,
            )
        self.time_seconds: np.ndarray = immutable_time
        self.observed_values: np.ndarray = immutable_values
        self.observed_variable_type: FmuVariableType = observed_variable_type


class ReferenceFmuCellResult:
    """Own the validated numerical result of one exact matrix cell."""

    __slots__ = (
        "cell_index",
        "cell_id",
        "tool",
        "case",
        "interface_mode",
        "status",
        "acceptance_basis",
        "trace",
        "raw_trace_path",
        "process_result",
        "peer_cell_id",
        "maximum_absolute_error",
        "maximum_relative_error",
        "maximum_event_time_error_seconds",
        "observed_event_count",
        "observed_termination",
        "terminal_observation",
    )

    cell_index: int
    cell_id: str
    tool: ReferenceFmuExecutionTool
    case: ReferenceFmuCase
    interface_mode: FmuInterfaceMode
    status: ReferenceFmuCellStatus
    acceptance_basis: ReferenceFmuAcceptanceBasis
    trace: ReferenceFmuTrace
    raw_trace_path: Path
    process_result: ReferenceFmuProcessResult | None
    peer_cell_id: str | None
    maximum_absolute_error: float
    maximum_relative_error: float
    maximum_event_time_error_seconds: float | None
    observed_event_count: int
    observed_termination: ReferenceFmuObservedTermination
    terminal_observation: ReferenceFmuTerminalObservation

    def __init__(
        self,
        cell_index: int,
        cell_id: str,
        tool: ReferenceFmuExecutionTool,
        case: ReferenceFmuCase,
        interface_mode: FmuInterfaceMode,
        status: ReferenceFmuCellStatus,
        acceptance_basis: ReferenceFmuAcceptanceBasis,
        trace: ReferenceFmuTrace,
        raw_trace_path: Path,
        process_result: ReferenceFmuProcessResult | None,
        peer_cell_id: str | None,
        maximum_absolute_error: float,
        maximum_relative_error: float,
        maximum_event_time_error_seconds: float | None,
        observed_event_count: int,
        observed_termination: ReferenceFmuObservedTermination,
        terminal_observation: ReferenceFmuTerminalObservation,
    ) -> None:
        """Validate one accepted comparison cell.

        :param cell_index: Stable matrix index from zero through fifteen.
        :param cell_id: Stable derived cell identifier.
        :param tool: Executed comparison tool.
        :param case: Canonical corpus case.
        :param interface_mode: Executed FMI interface.
        :param status: Successful acceptance status.
        :param acceptance_basis: Evidence used for acceptance.
        :param trace: Immutable raw event trace.
        :param raw_trace_path: Published trace path.
        :param process_result: External-process evidence for fmusim.
        :param peer_cell_id: Corresponding tool cell identifier.
        :param maximum_absolute_error: Maximum accepted absolute error.
        :param maximum_relative_error: Maximum accepted relative error.
        :param maximum_event_time_error_seconds: Maximum ME event-center error.
        :param observed_event_count: Events or transitions in raw output.
        :param observed_termination: Observed end condition.
        :param terminal_observation: Visibility of the terminal event value.
        :return: None.
        """

        scalar_values_are_valid: bool = bool(
            isinstance(cell_index, int)
            and not isinstance(cell_index, bool)
            and 0 <= cell_index <= 15
            and isinstance(cell_id, str)
            and bool(cell_id)
            and isinstance(observed_event_count, int)
            and not isinstance(observed_event_count, bool)
            and observed_event_count >= 0
            and isinstance(maximum_absolute_error, (int, float))
            and not isinstance(maximum_absolute_error, bool)
            and math.isfinite(float(maximum_absolute_error))
            and float(maximum_absolute_error) >= 0.0
            and isinstance(maximum_relative_error, (int, float))
            and not isinstance(maximum_relative_error, bool)
            and math.isfinite(float(maximum_relative_error))
            and float(maximum_relative_error) >= 0.0
        )
        owner_values_are_valid: bool = bool(
            isinstance(tool, ReferenceFmuExecutionTool)
            and isinstance(case, ReferenceFmuCase)
            and isinstance(interface_mode, FmuInterfaceMode)
            and isinstance(status, ReferenceFmuCellStatus)
            and isinstance(acceptance_basis, ReferenceFmuAcceptanceBasis)
            and isinstance(trace, ReferenceFmuTrace)
            and isinstance(raw_trace_path, Path)
            and (process_result is None or isinstance(process_result, ReferenceFmuProcessResult))
            and (peer_cell_id is None or isinstance(peer_cell_id, str))
            and isinstance(observed_termination, ReferenceFmuObservedTermination)
            and isinstance(terminal_observation, ReferenceFmuTerminalObservation)
        )
        if maximum_event_time_error_seconds is None:
            event_error_is_valid: bool = bool(
                interface_mode == FmuInterfaceMode.CO_SIMULATION
            )
        else:
            event_error_is_valid = bool(
                interface_mode == FmuInterfaceMode.MODEL_EXCHANGE
                and isinstance(maximum_event_time_error_seconds, (int, float))
                and not isinstance(maximum_event_time_error_seconds, bool)
                and math.isfinite(float(maximum_event_time_error_seconds))
                and float(maximum_event_time_error_seconds) >= 0.0
            )
        process_boundary_is_valid: bool = bool(
            (tool == ReferenceFmuExecutionTool.FMPY and process_result is None)
            or (tool == ReferenceFmuExecutionTool.FMUSIM and process_result is not None)
        )
        if (
            scalar_values_are_valid
            and owner_values_are_valid
            and event_error_is_valid
            and process_boundary_is_valid
        ):
            pass
        else:
            raise ValueError("Reference FMU cell result is invalid")

        self.cell_index: int = cell_index
        self.cell_id: str = cell_id
        self.tool: ReferenceFmuExecutionTool = tool
        self.case: ReferenceFmuCase = case
        self.interface_mode: FmuInterfaceMode = interface_mode
        self.status: ReferenceFmuCellStatus = status
        self.acceptance_basis: ReferenceFmuAcceptanceBasis = acceptance_basis
        self.trace: ReferenceFmuTrace = trace
        self.raw_trace_path: Path = raw_trace_path
        self.process_result: ReferenceFmuProcessResult | None = process_result
        self.peer_cell_id: str | None = peer_cell_id
        self.maximum_absolute_error: float = float(maximum_absolute_error)
        self.maximum_relative_error: float = float(maximum_relative_error)
        self.maximum_event_time_error_seconds: float | None = (
            None
            if maximum_event_time_error_seconds is None
            else float(maximum_event_time_error_seconds)
        )
        self.observed_event_count: int = observed_event_count
        self.observed_termination: ReferenceFmuObservedTermination = (
            observed_termination
        )
        self.terminal_observation: ReferenceFmuTerminalObservation = (
            terminal_observation
        )


def _verify_explicit_regular_file(
    path: Path,
    expected_suffix: str | None,
) -> None:
    """Reject absent, linked, nonregular or incorrectly suffixed files.

    :param path: Explicit file path supplied by the caller.
    :param expected_suffix: Required suffix, or ``None`` when unrestricted.
    :return: None.
    """

    path_is_valid: bool = False
    try:
        path_is_valid = bool(
            isinstance(path, Path)
            and path.exists()
            and path.is_file()
            and not path.is_symlink()
            and (expected_suffix is None or path.suffix == expected_suffix)
        )
    except OSError:
        path_is_valid = False
    if path_is_valid:
        pass
    else:
        raise ValueError("Explicit file path is unsafe or invalid")


def _read_explicit_file_bytes(path: Path, maximum_size_bytes: int) -> bytes:
    """Read one explicit regular file through a strict size boundary.

    :param path: File previously selected by the caller or sealed corpus.
    :param maximum_size_bytes: Maximum accepted byte count.
    :return: Exact immutable file bytes.
    """

    if (
        isinstance(maximum_size_bytes, int)
        and not isinstance(maximum_size_bytes, bool)
        and maximum_size_bytes > 0
    ):
        pass
    else:
        raise ValueError("File size boundary is invalid")
    _verify_explicit_regular_file(path, None)
    source_file: BinaryIO = path.open("rb")
    try:
        content: bytes = source_file.read(maximum_size_bytes + 1)
    finally:
        source_file.close()
    if len(content) <= maximum_size_bytes:
        return content
    else:
        raise ValueError("Explicit file exceeds its size boundary")


def read_fmpy_distribution_identity() -> tuple[str, str]:
    """Recompute the complete installed FMPy distribution identity.

    :return: Installed version and deterministic all-file SHA-256 digest.
    """

    distribution: metadata.Distribution = metadata.distribution("FMPy")
    distribution_files: list[metadata.PackagePath] = list(
        distribution.files or list()
    )
    portable_paths: list[str] = [
        str(relative_path).replace("\\", "/")
        for relative_path in distribution_files
    ]
    portable_paths.sort()
    records: list[str] = list()
    for portable_path in portable_paths:
        absolute_path: Path = Path(distribution.locate_file(portable_path))
        _verify_explicit_regular_file(absolute_path, None)
        content: bytes = _read_explicit_file_bytes(absolute_path, 64 * 1024 * 1024)
        file_sha256: str = hashlib.sha256(content).hexdigest()
        records.append(f"{portable_path} {len(content)} {file_sha256}")
    digest_input: bytes = "\n".join(records).encode("utf-8")
    return distribution.version, hashlib.sha256(digest_input).hexdigest()


def read_reference_fmu_embedded_trace(
    asset: ValidatedReferenceFmuAsset,
) -> ReferenceFmuTrace:
    """Read the single sealed reference CSV member from validated FMU bytes.

    :param asset: Immutable corpus-validated FMU bytes.
    :return: Strictly parsed official Co-Simulation reference trace.
    """

    if isinstance(asset, ValidatedReferenceFmuAsset):
        pass
    else:
        raise ValueError("Reference trace requires a validated FMU asset")
    archive_stream: io.BytesIO = io.BytesIO(asset.content)
    archive: zipfile.ZipFile = zipfile.ZipFile(archive_stream, mode="r")
    try:
        matching_members: list[zipfile.ZipInfo] = list()
        for member in archive.infolist():
            member_path: str = member.filename.replace("\\", "/")
            if member_path == asset.case.reference_output_relative_path:
                matching_members.append(member)
            else:
                pass
        if len(matching_members) == 1:
            selected_member: zipfile.ZipInfo = matching_members[0]
        else:
            raise ValueError("Reference CSV member is absent or duplicated")
        member_is_safe: bool = bool(
            selected_member.compress_size <= 1_048_576
            and selected_member.file_size <= 1_048_576
            and selected_member.file_size > 0
            and not bool(selected_member.flag_bits & 0x1)
            and ((selected_member.external_attr >> 16) & 0o170000)
            in (0, 0o100000)
        )
        if member_is_safe:
            reference_bytes: bytes = archive.read(selected_member)
        else:
            raise ValueError("Reference CSV archive member is unsafe")
    finally:
        archive.close()
        archive_stream.close()
    if (
        len(reference_bytes) == selected_member.file_size
        and hashlib.sha256(reference_bytes).hexdigest()
        == asset.case.reference_output_sha256
    ):
        pass
    else:
        raise ValueError("Reference CSV bytes do not match the sealed identity")

    reference_text: str = reference_bytes.decode("utf-8", errors="strict")
    csv_stream: io.StringIO = io.StringIO(reference_text, newline="")
    reader: csv.reader = csv.reader(csv_stream)
    rows: list[list[str]] = list(reader)
    csv_stream.close()
    if len(rows) == asset.case.expected_sample_count + 1:
        header: list[str] = rows[0]
    else:
        raise ValueError("Reference CSV sample count is invalid")
    if "time" in header and asset.case.interface_oracles[0].observed_variable_name in header:
        time_index: int = header.index("time")
        value_index: int = header.index(
            asset.case.interface_oracles[0].observed_variable_name
        )
    else:
        raise ValueError("Reference CSV does not expose required fields")
    time_values: np.ndarray = np.empty(asset.case.expected_sample_count, dtype=np.float64)
    oracle: ReferenceFmuEventOracle = asset.case.interface_oracles[0]
    integer_type: bool = bool(
        oracle.observed_variable_type
        in (FmuVariableType.INTEGER, FmuVariableType.INT32)
    )
    if integer_type:
        observed_values: np.ndarray = np.empty(
            asset.case.expected_sample_count,
            dtype=np.int32,
        )
    else:
        observed_values = np.empty(
            asset.case.expected_sample_count,
            dtype=np.float64,
        )
    for row_index in range(asset.case.expected_sample_count):
        row: list[str] = rows[row_index + 1]
        if len(row) == len(header):
            time_token: str = row[time_index]
            value_token: str = row[value_index]
        else:
            raise ValueError("Reference CSV row width is invalid")
        parsed_time: float = float(time_token)
        if math.isfinite(parsed_time):
            time_values[row_index] = parsed_time
        else:
            raise ValueError("Reference CSV time is not finite")
        if integer_type:
            if re.fullmatch(r"-?(0|[1-9][0-9]*)", value_token) is not None:
                parsed_integer: int = int(value_token)
            else:
                raise ValueError("Reference CSV integer token is invalid")
            if -2_147_483_648 <= parsed_integer <= 2_147_483_647:
                observed_values[row_index] = parsed_integer
            else:
                raise ValueError("Reference CSV integer is outside Int32")
        else:
            parsed_float: float = float(value_token)
            if math.isfinite(parsed_float):
                observed_values[row_index] = parsed_float
            else:
                raise ValueError("Reference CSV value is not finite")
    return ReferenceFmuTrace(time_values, observed_values, oracle.observed_variable_type)


def _write_staged_fmu(
    asset: ValidatedReferenceFmuAsset,
    runtime_dir: Path,
) -> Path:
    """Write validated immutable FMU bytes into the private runtime tree.

    :param asset: Corpus-validated FMU bytes.
    :param runtime_dir: Owned private runtime directory.
    :return: Exact staged FMU path.
    """

    staged_path: Path = runtime_dir / "model.fmu"
    staged_file: BinaryIO = staged_path.open("xb")
    try:
        staged_file.write(asset.content)
    finally:
        staged_file.close()
    staged_content: bytes = _read_explicit_file_bytes(
        staged_path,
        asset.case.fmu_size_bytes,
    )
    if staged_content == asset.content:
        return staged_path
    else:
        raise ValueError("Staged FMU bytes changed during publication")


def _write_staged_fmusim(
    executable_content: bytes,
    runtime_dir: Path,
) -> Path:
    """Write exact fmusim bytes into the private runtime tree.

    :param executable_content: Previously identity-validated executable bytes.
    :param runtime_dir: Owned private runtime directory.
    :return: Executable path used for every external process.
    """

    staged_path: Path = runtime_dir / "fmusim.exe"
    staged_file: BinaryIO = staged_path.open("xb")
    try:
        staged_file.write(executable_content)
    finally:
        staged_file.close()
    staged_content: bytes = _read_explicit_file_bytes(staged_path, 8 * 1024 * 1024)
    if staged_content == executable_content:
        return staged_path
    else:
        raise ValueError("Staged fmusim bytes changed during publication")


def _terminate_fmusim_process_group(
    process: subprocess.Popen[bytes],
) -> None:
    """Terminate one owned fmusim process and require an observed exit.

    :param process: Direct process launched in its own process group.
    :return: None after the process is known to have exited.
    """

    if process.poll() is None:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.terminate()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2.0)
    else:
        pass
    if process.poll() is None:
        raise RuntimeError("fmusim process exit could not be observed")
    else:
        pass


def _run_bounded_fmusim_process(
    arguments: tuple[str, ...],
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: float,
    maximum_stream_size_bytes: int,
) -> ReferenceFmuProcessResult:
    """Run fmusim without a shell while bounding time and file-backed streams.

    :param arguments: Exact process arguments with executable first.
    :param stdout_path: Owned file receiving standard output.
    :param stderr_path: Owned file receiving standard error.
    :param timeout_seconds: Hard execution deadline.
    :param maximum_stream_size_bytes: Independent bound for each stream.
    :return: Immutable observed process result.
    """

    inputs_are_valid: bool = bool(
        isinstance(arguments, tuple)
        and len(arguments) > 0
        and all(isinstance(argument, str) for argument in arguments)
        and isinstance(stdout_path, Path)
        and isinstance(stderr_path, Path)
        and isinstance(timeout_seconds, (int, float))
        and not isinstance(timeout_seconds, bool)
        and float(timeout_seconds) > 0.0
        and isinstance(maximum_stream_size_bytes, int)
        and not isinstance(maximum_stream_size_bytes, bool)
        and maximum_stream_size_bytes > 0
    )
    if inputs_are_valid:
        pass
    else:
        raise ValueError("Bounded fmusim process arguments are invalid")
    creation_flags: int
    if os.name == "nt":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        creation_flags = 0
    stdout_file: BinaryIO = stdout_path.open("xb")
    stderr_file: BinaryIO = stderr_path.open("xb")
    process: subprocess.Popen[bytes] | None = None
    started_at: float = time.monotonic()
    try:
        process = subprocess.Popen(
            list(arguments),
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            creationflags=creation_flags,
        )
        process_finished: bool = False
        while not process_finished:
            elapsed_seconds: float = time.monotonic() - started_at
            stdout_file.flush()
            stderr_file.flush()
            streams_are_bounded: bool = bool(
                stdout_path.stat().st_size <= maximum_stream_size_bytes
                and stderr_path.stat().st_size <= maximum_stream_size_bytes
            )
            deadline_is_valid: bool = bool(elapsed_seconds <= timeout_seconds)
            if streams_are_bounded and deadline_is_valid:
                process_finished = bool(process.poll() is not None)
                if process_finished:
                    pass
                else:
                    time.sleep(0.05)
            else:
                _terminate_fmusim_process_group(process)
                if streams_are_bounded:
                    raise TimeoutError("fmusim exceeded its execution deadline")
                else:
                    raise ValueError("fmusim stream exceeded its size boundary")
        return_code: int = cast(int, process.returncode)
    except Exception:
        if process is None:
            pass
        else:
            _terminate_fmusim_process_group(process)
        raise
    finally:
        stdout_file.close()
        stderr_file.close()
    final_elapsed_seconds: float = time.monotonic() - started_at
    stdout_content: bytes = _read_explicit_file_bytes(
        stdout_path,
        maximum_stream_size_bytes,
    )
    stderr_content: bytes = _read_explicit_file_bytes(
        stderr_path,
        maximum_stream_size_bytes,
    )
    return ReferenceFmuProcessResult(
        arguments=arguments,
        return_code=return_code,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        elapsed_seconds=final_elapsed_seconds,
        stdout_sha256=hashlib.sha256(stdout_content).hexdigest(),
        stderr_sha256=hashlib.sha256(stderr_content).hexdigest(),
    )


def _execute_fmpy_cell(
    case: ReferenceFmuCase,
    interface_mode: FmuInterfaceMode,
    staged_fmu_path: Path,
    raw_trace_path: Path,
) -> ReferenceFmuTrace:
    """Execute one FMPy cell and preserve every returned event row.

    :param case: Canonical corpus case.
    :param interface_mode: FMI interface to execute.
    :param staged_fmu_path: Private immutable FMU copy.
    :param raw_trace_path: Destination for the raw typed trace.
    :return: Immutable parsed trace.
    """

    oracle: ReferenceFmuEventOracle = case.find_interface_oracle(interface_mode)
    if interface_mode == FmuInterfaceMode.CO_SIMULATION:
        fmi_type: str = "CoSimulation"
        solver: str | None = None
        record_events: bool = False
    else:
        fmi_type = "ModelExchange"
        solver = "CVode"
        record_events = True
    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        result: np.ndarray = simulate_fmu(
            filename=str(staged_fmu_path),
            validate=True,
            start_time=case.start_time_seconds,
            stop_time=case.declared_stop_time_seconds,
            output_interval=case.step_size_seconds,
            output=[oracle.observed_variable_name],
            timeout=35.0,
            set_stop_time=True,
            fmi_type=fmi_type,
            solver=solver,
            relative_tolerance=1.0e-8,
            record_events=record_events,
        )
    if len(captured_warnings) == 0:
        pass
    else:
        raise RuntimeError("FMPy emitted a warning during a benchmark cell")
    if (
        isinstance(result, np.ndarray)
        and result.dtype.names is not None
        and "time" in result.dtype.names
        and oracle.observed_variable_name in result.dtype.names
    ):
        pass
    else:
        raise ValueError("FMPy result is missing required fields")
    time_values: np.ndarray = np.asarray(result["time"], dtype=np.float64)
    raw_values: np.ndarray = np.asarray(result[oracle.observed_variable_name])
    integer_type: bool = bool(
        oracle.observed_variable_type
        in (FmuVariableType.INTEGER, FmuVariableType.INT32)
    )
    if integer_type:
        numeric_values: np.ndarray = np.asarray(raw_values, dtype=np.float64)
        values_are_integral: bool = bool(
            np.all(np.isfinite(numeric_values))
            and np.all(numeric_values == np.trunc(numeric_values))
            and np.all(numeric_values >= -2_147_483_648)
            and np.all(numeric_values <= 2_147_483_647)
        )
        if values_are_integral:
            observed_values: np.ndarray = numeric_values.astype(np.int32)
        else:
            raise ValueError("FMPy integer result lost exact Int32 semantics")
    else:
        observed_values = np.asarray(raw_values, dtype=np.float64)
        if np.all(np.isfinite(observed_values)):
            pass
        else:
            raise ValueError("FMPy floating result contains nonfinite values")
    trace: ReferenceFmuTrace = ReferenceFmuTrace(
        time_values,
        observed_values,
        oracle.observed_variable_type,
    )
    trace_file: TextIO = raw_trace_path.open("x", encoding="utf-8", newline="")
    try:
        writer: csv.writer = csv.writer(trace_file, lineterminator="\n")
        writer.writerow(("time", oracle.observed_variable_name))
        for row_index in range(trace.time_seconds.size):
            writer.writerow(
                (
                    repr(float(trace.time_seconds[row_index])),
                    str(trace.observed_values[row_index]),
                )
            )
    finally:
        trace_file.close()
    return trace


def _execute_fmusim_cell(
    case: ReferenceFmuCase,
    interface_mode: FmuInterfaceMode,
    staged_fmu_path: Path,
    staged_fmusim_path: Path,
    raw_trace_path: Path,
    stdout_path: Path,
    stderr_path: Path,
) -> tuple[ReferenceFmuTrace, ReferenceFmuProcessResult]:
    """Execute one official fmusim cell using the documented CLI.

    :param case: Canonical corpus case.
    :param interface_mode: FMI interface to execute.
    :param staged_fmu_path: Private immutable FMU copy.
    :param staged_fmusim_path: Private immutable tool copy.
    :param raw_trace_path: Destination CSV created by fmusim.
    :param stdout_path: File-backed standard-output destination.
    :param stderr_path: File-backed standard-error destination.
    :return: Parsed raw trace and bounded process evidence.
    """

    oracle: ReferenceFmuEventOracle = case.find_interface_oracle(interface_mode)
    if interface_mode == FmuInterfaceMode.CO_SIMULATION:
        interface_argument: str = "cs"
        solver_arguments: tuple[str, ...] = (
            "--fixed-step-size",
            repr(case.step_size_seconds),
        )
    else:
        interface_argument = "me"
        solver_arguments = ("--solver", "cvode")
    common_arguments: tuple[str, ...] = (
        str(staged_fmusim_path),
        "simulate",
        "--start-time",
        repr(case.start_time_seconds),
        "--stop-time",
        repr(case.declared_stop_time_seconds),
        "--set-stop-time",
        "--output-interval",
        repr(case.step_size_seconds),
        "--tolerance",
        "1e-8",
        "--set-tolerance",
        "--interface-type",
        interface_argument,
        "--output-file",
        str(raw_trace_path),
        "--output-variable",
        oracle.observed_variable_name,
    )
    arguments: tuple[str, ...] = common_arguments + solver_arguments + (
        str(staged_fmu_path),
    )
    process_result: ReferenceFmuProcessResult = _run_bounded_fmusim_process(
        arguments,
        stdout_path,
        stderr_path,
        35.0,
        4 * 1024 * 1024,
    )
    if process_result.return_code == 0:
        trace: ReferenceFmuTrace = read_reference_fmu_trace_csv(
            raw_trace_path,
            oracle.observed_variable_name,
            oracle.observed_variable_type,
        )
    else:
        raise RuntimeError("fmusim returned a nonzero status")
    return trace, process_result


def read_reference_fmu_trace_csv(
    trace_path: Path,
    observed_variable_name: str,
    observed_variable_type: FmuVariableType,
) -> ReferenceFmuTrace:
    """Parse one raw tool CSV without coercing discrete event values.

    :param trace_path: Explicit bounded CSV produced by the tool.
    :param observed_variable_name: Required output column.
    :param observed_variable_type: FMI scalar type governing token parsing.
    :return: Immutable raw trace preserving row order and duplicates.
    """

    trace_bytes: bytes = _read_explicit_file_bytes(trace_path, 1_048_576)
    trace_text: str = trace_bytes.decode("utf-8", errors="strict")
    csv_stream: io.StringIO = io.StringIO(trace_text, newline="")
    reader: csv.reader = csv.reader(csv_stream)
    rows: list[list[str]] = list(reader)
    csv_stream.close()
    if len(rows) >= 3:
        header: list[str] = rows[0]
    else:
        raise ValueError("Tool trace contains too few rows")
    if "time" in header and observed_variable_name in header:
        time_index: int = header.index("time")
        value_index: int = header.index(observed_variable_name)
    else:
        raise ValueError("Tool trace is missing required columns")
    sample_count: int = len(rows) - 1
    time_values: np.ndarray = np.empty(sample_count, dtype=np.float64)
    integer_type: bool = bool(
        observed_variable_type
        in (FmuVariableType.INTEGER, FmuVariableType.INT32)
    )
    if integer_type:
        observed_values: np.ndarray = np.empty(sample_count, dtype=np.int32)
    else:
        observed_values = np.empty(sample_count, dtype=np.float64)
    for row_index in range(sample_count):
        row: list[str] = rows[row_index + 1]
        if len(row) == len(header):
            time_token: str = row[time_index]
            value_token: str = row[value_index]
        else:
            raise ValueError("Tool trace row width is invalid")
        parsed_time: float = float(time_token)
        if math.isfinite(parsed_time):
            time_values[row_index] = parsed_time
        else:
            raise ValueError("Tool trace time is not finite")
        if integer_type:
            if re.fullmatch(r"-?(0|[1-9][0-9]*)", value_token) is not None:
                parsed_integer: int = int(value_token)
            else:
                raise ValueError("Tool trace integer token is invalid")
            if -2_147_483_648 <= parsed_integer <= 2_147_483_647:
                observed_values[row_index] = parsed_integer
            else:
                raise ValueError("Tool trace integer is outside Int32")
        else:
            parsed_float: float = float(value_token)
            if math.isfinite(parsed_float):
                observed_values[row_index] = parsed_float
            else:
                raise ValueError("Tool trace value is not finite")
    return ReferenceFmuTrace(time_values, observed_values, observed_variable_type)


def build_reference_fmu_regular_trace(
    case: ReferenceFmuCase,
    raw_trace: ReferenceFmuTrace,
) -> ReferenceFmuTrace:
    """Select the declared regular lattice without interpolation or synthesis.

    :param case: Canonical case defining the lattice.
    :param raw_trace: Event-preserving tool output.
    :return: Immutable trace containing exactly one row per lattice point.
    """

    lattice: np.ndarray = (
        case.start_time_seconds
        + np.arange(case.expected_sample_count, dtype=np.float64)
        * case.step_size_seconds
    )
    selected_time: np.ndarray = np.empty(
        case.expected_sample_count,
        dtype=np.float64,
    )
    integer_type: bool = bool(
        raw_trace.observed_variable_type
        in (FmuVariableType.INTEGER, FmuVariableType.INT32)
    )
    if integer_type:
        selected_values: np.ndarray = np.empty(
            case.expected_sample_count,
            dtype=np.int32,
        )
    else:
        selected_values = np.empty(
            case.expected_sample_count,
            dtype=np.float64,
        )
    oracle: ReferenceFmuEventOracle = case.find_interface_oracle(
        FmuInterfaceMode.CO_SIMULATION
    )
    for lattice_index in range(case.expected_sample_count):
        candidate_indices: np.ndarray = np.flatnonzero(
            np.abs(raw_trace.time_seconds - lattice[lattice_index]) <= 1.0e-12
        )
        if candidate_indices.size == 1:
            selected_index: int = int(candidate_indices[0])
        else:
            duplicate_is_time_event: bool = bool(
                candidate_indices.size >= 2
                and oracle.detection_rule
                == ReferenceFmuEventDetectionRule.VALUE_CHANGE_AT_TIME
            )
            if duplicate_is_time_event:
                selected_index = int(candidate_indices[-1])
            else:
                raise ValueError("Regular lattice has missing or ambiguous rows")
        selected_time[lattice_index] = lattice[lattice_index]
        selected_values[lattice_index] = raw_trace.observed_values[selected_index]
    return ReferenceFmuTrace(
        selected_time,
        selected_values,
        raw_trace.observed_variable_type,
    )


def evaluate_reference_fmu_cs_trace(
    case: ReferenceFmuCase,
    raw_trace: ReferenceFmuTrace,
    reference_trace: ReferenceFmuTrace,
) -> tuple[
    float,
    float,
    int,
    ReferenceFmuObservedTermination,
    ReferenceFmuTerminalObservation,
]:
    """Validate one CS trace against official samples and the CS oracle.

    :param case: Canonical corpus case.
    :param raw_trace: Event-preserving tool output.
    :param reference_trace: Official embedded CS reference output.
    :return: Error metrics, event count and terminal classifications.
    """

    regular_trace: ReferenceFmuTrace = build_reference_fmu_regular_trace(case, raw_trace)
    if np.array_equal(regular_trace.time_seconds, reference_trace.time_seconds):
        pass
    else:
        raise ValueError("CS regular time lattice differs from the reference")
    oracle: ReferenceFmuEventOracle = case.find_interface_oracle(
        FmuInterfaceMode.CO_SIMULATION
    )
    integer_type: bool = bool(
        oracle.observed_variable_type
        in (FmuVariableType.INTEGER, FmuVariableType.INT32)
    )
    if integer_type:
        if np.array_equal(regular_trace.observed_values, reference_trace.observed_values):
            absolute_errors: np.ndarray = np.zeros(
                regular_trace.observed_values.size,
                dtype=np.float64,
            )
        else:
            raise ValueError("CS discrete output differs from the official reference")
    else:
        absolute_errors = np.abs(
            regular_trace.observed_values - reference_trace.observed_values
        )
        tolerances: np.ndarray = (
            1.0e-9 + 1.0e-9 * np.abs(reference_trace.observed_values)
        )
        if np.all(absolute_errors <= tolerances):
            pass
        else:
            raise ValueError("CS floating output exceeds reference tolerance")
    relative_errors: np.ndarray = absolute_errors / np.maximum(
        np.abs(reference_trace.observed_values.astype(np.float64)),
        1.0e-9,
    )
    if oracle.detection_rule == ReferenceFmuEventDetectionRule.VALUE_CHANGE_AT_TIME:
        changed_indices: np.ndarray = np.flatnonzero(
            raw_trace.observed_values[1:] != raw_trace.observed_values[:-1]
        ) + 1
    else:
        changed_indices = np.flatnonzero(
            (raw_trace.observed_values[:-1] < 0.0)
            & (raw_trace.observed_values[1:] >= 0.0)
        ) + 1
    observed_event_count: int = int(changed_indices.size)
    if observed_event_count == oracle.observable_transition_count:
        pass
    else:
        raise ValueError("CS observed event count differs from its oracle")
    for event_index in range(observed_event_count):
        event_time: float = float(raw_trace.time_seconds[changed_indices[event_index]])
        lower_bound: float = float(oracle.event_lower_bounds_seconds[event_index])
        upper_bound: float = float(oracle.event_upper_bounds_seconds[event_index])
        if (
            lower_bound - 1.0e-12
            <= event_time
            <= upper_bound + 1.0e-12
        ):
            pass
        else:
            raise ValueError("CS event lies outside its oracle interval")
    if raw_trace.observed_values[-1] == oracle.expected_last_observed_value:
        pass
    else:
        raise ValueError("CS terminal value differs from its oracle")
    if oracle.termination_kind == ReferenceFmuTerminationKind.FMU_REQUEST:
        observed_termination: ReferenceFmuObservedTermination = (
            ReferenceFmuObservedTermination.FMU_TERMINATION_BOUNDARY
        )
    else:
        observed_termination = ReferenceFmuObservedTermination.CONFIGURED_STOP
    if oracle.terminal_value_must_be_sustained:
        terminal_observation: ReferenceFmuTerminalObservation = (
            ReferenceFmuTerminalObservation.SUSTAINED_TERMINAL_VALUE
        )
    else:
        terminal_observation = ReferenceFmuTerminalObservation.TERMINAL_VALUE
    return (
        float(np.max(absolute_errors)),
        float(np.max(relative_errors)),
        observed_event_count,
        observed_termination,
        terminal_observation,
    )


def _evaluate_me_pair_and_oracles(
    case: ReferenceFmuCase,
    fmpy_trace: ReferenceFmuTrace,
    fmusim_trace: ReferenceFmuTrace,
) -> tuple[float, float, float, float, int, int]:
    """Validate the ME tool pair and each tool against the independent oracle.

    :param case: Canonical corpus case.
    :param fmpy_trace: Raw event-preserving FMPy output.
    :param fmusim_trace: Raw event-preserving fmusim output.
    :return: Pair errors, per-tool event errors and event counts.
    """

    oracle: ReferenceFmuEventOracle = case.find_interface_oracle(
        FmuInterfaceMode.MODEL_EXCHANGE
    )
    fmpy_regular: ReferenceFmuTrace = build_reference_fmu_regular_trace(case, fmpy_trace)
    fmusim_regular: ReferenceFmuTrace = build_reference_fmu_regular_trace(case, fmusim_trace)
    if np.array_equal(fmpy_regular.time_seconds, fmusim_regular.time_seconds):
        pass
    else:
        raise ValueError("ME tools do not share the declared regular lattice")
    integer_type: bool = bool(
        oracle.observed_variable_type
        in (FmuVariableType.INTEGER, FmuVariableType.INT32)
    )
    if integer_type:
        if np.array_equal(fmpy_regular.observed_values, fmusim_regular.observed_values):
            absolute_errors: np.ndarray = np.zeros(
                fmpy_regular.observed_values.size,
                dtype=np.float64,
            )
        else:
            raise ValueError("ME discrete tool outputs differ")
    else:
        absolute_errors = np.abs(
            fmpy_regular.observed_values - fmusim_regular.observed_values
        )
        tolerances: np.ndarray = (
            1.0e-6 + 1.0e-6 * np.abs(fmusim_regular.observed_values)
        )
        if np.all(absolute_errors <= tolerances):
            pass
        else:
            raise ValueError("ME floating tool outputs exceed pair tolerance")
    relative_errors: np.ndarray = absolute_errors / np.maximum(
        np.abs(fmusim_regular.observed_values.astype(np.float64)),
        1.0e-6,
    )

    traces: tuple[ReferenceFmuTrace, ReferenceFmuTrace] = (
        fmpy_trace,
        fmusim_trace,
    )
    event_errors: np.ndarray = np.empty(2, dtype=np.float64)
    event_counts: np.ndarray = np.empty(2, dtype=np.int32)
    for trace_index in range(2):
        trace: ReferenceFmuTrace = traces[trace_index]
        if oracle.detection_rule == ReferenceFmuEventDetectionRule.VALUE_CHANGE_AT_TIME:
            changed_indices: np.ndarray = np.flatnonzero(
                trace.observed_values[1:] != trace.observed_values[:-1]
            ) + 1
        else:
            changed_indices = np.flatnonzero(
                (trace.observed_values[:-1] < 0.0)
                & (trace.observed_values[1:] >= 0.0)
            ) + 1
        observed_count: int = int(changed_indices.size)
        if observed_count == oracle.observable_transition_count:
            pass
        else:
            raise ValueError("ME observed event count differs from its oracle")
        event_counts[trace_index] = observed_count
        maximum_event_error: float = 0.0
        for event_index in range(observed_count):
            event_time: float = float(trace.time_seconds[changed_indices[event_index]])
            lower_bound: float = float(oracle.event_lower_bounds_seconds[event_index])
            upper_bound: float = float(oracle.event_upper_bounds_seconds[event_index])
            if (
                lower_bound - 1.0e-12
                <= event_time
                <= upper_bound + 1.0e-12
            ):
                center: float = 0.5 * (lower_bound + upper_bound)
                maximum_event_error = max(
                    maximum_event_error,
                    abs(event_time - center),
                )
            else:
                raise ValueError("ME event lies outside its oracle interval")
        if not oracle.terminal_post_event_observable:
            termination_error: float = abs(
                float(trace.time_seconds[-1])
                - oracle.expected_termination_time_seconds
            )
            maximum_event_error = max(maximum_event_error, termination_error)
        else:
            pass
        if trace.observed_values[-1] == oracle.expected_last_observed_value:
            pass
        else:
            raise ValueError("ME terminal value differs from its oracle")
        if oracle.terminal_value_must_be_sustained:
            terminal_bound: float = float(oracle.event_upper_bounds_seconds[-1])
            terminal_indices: np.ndarray = np.flatnonzero(
                trace.time_seconds >= terminal_bound
            )
            if np.all(trace.observed_values[terminal_indices] == oracle.semantic_final_value):
                pass
            else:
                raise ValueError("ME terminal value is not sustained")
        else:
            pass
        event_errors[trace_index] = maximum_event_error
    return (
        float(np.max(absolute_errors)),
        float(np.max(relative_errors)),
        float(event_errors[0]),
        float(event_errors[1]),
        int(event_counts[0]),
        int(event_counts[1]),
    )


def _write_manifest(
    config: ReferenceFmuExecutionConfig,
    catalog: ReferenceFmuCatalog,
    cells: tuple[ReferenceFmuCellResult, ...],
    staging_dir: Path,
    generated_at_utc: str,
    fmpy_version: str,
    fmpy_distribution_sha256: str,
) -> Path:
    """Write the closed evidence manifest after all cells pass.

    :param config: Immutable explicit run configuration.
    :param catalog: Sealed reference corpus.
    :param cells: Exact sixteen accepted matrix cells.
    :param staging_dir: Owned package staging directory.
    :param generated_at_utc: UTC generation timestamp.
    :param fmpy_version: Observed installed FMPy version.
    :param fmpy_distribution_sha256: Observed complete FMPy digest.
    :return: Newly written manifest path.
    """

    if len(cells) == 16:
        pass
    else:
        raise ValueError("Reference matrix must contain sixteen cells")
    catalog_content: bytes = _read_explicit_file_bytes(config.catalog_path, 65_536)
    cell_records: list[dict[str, object]] = list()
    for cell in cells:
        if cell.interface_mode == FmuInterfaceMode.CO_SIMULATION:
            interface_text: str = "CoSimulation"
        else:
            interface_text = "ModelExchange"
        if cell.process_result is None:
            stdout_relative_path: str | None = None
            stderr_relative_path: str | None = None
        else:
            stdout_relative_path = cell.process_result.stdout_path.relative_to(
                staging_dir
            ).as_posix()
            stderr_relative_path = cell.process_result.stderr_path.relative_to(
                staging_dir
            ).as_posix()
        cell_records.append(
            dict(
                cell_index=cell.cell_index,
                cell_id=cell.cell_id,
                case_id=cell.case.case_id,
                fmi_version=cell.case.fmi_version.value,
                model_name=cell.case.model_name,
                interface_mode=interface_text,
                tool=cell.tool.value,
                status=cell.status.value,
                acceptance_basis=cell.acceptance_basis.value,
                peer_cell_id=cell.peer_cell_id,
                raw_trace_path=cell.raw_trace_path.relative_to(
                    staging_dir
                ).as_posix(),
                stdout_path=stdout_relative_path,
                stderr_path=stderr_relative_path,
                raw_sample_count=int(cell.trace.time_seconds.size),
                regular_sample_count=cell.case.expected_sample_count,
                native_event_count=cell.observed_event_count,
                maximum_absolute_error=cell.maximum_absolute_error,
                maximum_relative_error=cell.maximum_relative_error,
                maximum_event_time_error_seconds=(
                    cell.maximum_event_time_error_seconds
                ),
                expected_termination_kind=(
                    cell.case.find_interface_oracle(
                        cell.interface_mode
                    ).termination_kind.value
                ),
                observed_termination=cell.observed_termination.value,
                terminal_observation=cell.terminal_observation.value,
            )
        )

    artifact_records: list[dict[str, object]] = list()
    artifact_paths: list[Path] = list()
    for cell in cells:
        if cell.process_result is None:
            artifact_paths.append(cell.raw_trace_path)
        else:
            artifact_paths.append(cell.process_result.stderr_path)
            artifact_paths.append(cell.process_result.stdout_path)
            artifact_paths.append(cell.raw_trace_path)
    for artifact_path in artifact_paths:
        artifact_content: bytes = _read_explicit_file_bytes(
            artifact_path,
            4 * 1024 * 1024,
        )
        relative_path: str = artifact_path.relative_to(staging_dir).as_posix()
        cell_directory_name: str = artifact_path.parent.name
        cell_index: int = int(cell_directory_name.split("-")[1])
        cell_id: str = cells[cell_index].cell_id
        if artifact_path.name == "trace.csv":
            artifact_kind: ReferenceFmuArtifactKind = (
                ReferenceFmuArtifactKind.TRACE_CSV
            )
        else:
            if artifact_path.name == "stdout.log":
                artifact_kind = ReferenceFmuArtifactKind.STDOUT_LOG
            else:
                if artifact_path.name == "stderr.log":
                    artifact_kind = ReferenceFmuArtifactKind.STDERR_LOG
                else:
                    raise ValueError("Unexpected retained artifact name")
        artifact_records.append(
            dict(
                path=relative_path,
                cell_id=cell_id,
                kind=artifact_kind.value,
                size_bytes=len(artifact_content),
                sha256=hashlib.sha256(artifact_content).hexdigest(),
            )
        )

    manifest: dict[str, object] = dict(
        schema_name="veragrid-fmi-reference-execution-v1",
        source=dict(
            repository_id="veragrid-dynamics",
            branch=config.source_branch,
            source_revision=config.source_revision,
            source_tree_sha256=config.source_tree_sha256,
            generated_at_utc=generated_at_utc,
            host_os=platform.system(),
            host_architecture=platform.machine(),
            python_version=platform.python_version(),
        ),
        corpus=dict(
            catalog_relative_identity=(
                "examples/fmi/reference_fmu_catalog.json"
            ),
            catalog_sha256=hashlib.sha256(catalog_content).hexdigest(),
            release_tag=catalog.release_tag,
            archive_sha256=catalog.archive_sha256,
            case_ids=[reference_case.case_id for reference_case in catalog.cases],
        ),
        tools=[
            dict(
                name="FMPy",
                version=fmpy_version,
                execution_kind=ReferenceFmuExecutionKind.IN_PROCESS_PYTHON.value,
                identity_path="importlib.metadata:FMPy",
                size_bytes=None,
                sha256=fmpy_distribution_sha256,
                release_url="https://pypi.org/project/FMPy/0.3.31/",
                commit_sha=None,
                license_spdx="BSD-2-Clause",
            ),
            dict(
                name="fmusim",
                version=config.fmusim_expected_version,
                execution_kind=ReferenceFmuExecutionKind.EXTERNAL_PROCESS.value,
                identity_path="caller-supplied:fmusim.exe",
                size_bytes=config.fmusim_expected_size_bytes,
                sha256=config.fmusim_expected_sha256,
                release_url="https://github.com/modelica/fmusim/releases/tag/v0.10.0",
                commit_sha="0af4d43b62bc65b8895ddd7fe3b4850dde189b6f",
                license_spdx="BSD-2-Clause",
            ),
        ],
        policy=dict(
            cs_absolute_tolerance=1.0e-9,
            cs_relative_tolerance=1.0e-9,
            me_absolute_tolerance=1.0e-6,
            me_relative_tolerance=1.0e-6,
            me_solver_relative_tolerance=1.0e-8,
            time_tolerance_seconds=1.0e-12,
            event_time_tolerance_seconds=1.0e-6,
            version_timeout_seconds=10,
            simulation_timeout_seconds=35,
            version_stream_limit_bytes=65_536,
            simulation_stream_limit_bytes=4_194_304,
            csv_limit_bytes=1_048_576,
            runtime_tree_limit_bytes=33_554_432,
            runtime_entry_limit=128,
            manifest_limit_bytes=2_097_152,
        ),
        cells=cell_records,
        artifacts=artifact_records,
        claim=dict(
            scope=(
                "Current-host execution of Reference FMUs v0.0.41 with "
                "FMPy 0.3.31 and fmusim 0.10.0"
            ),
            limitations=[
                (
                    "Model Exchange uses tool-pair plus corpus-owned interface "
                    "oracles, not the CS reference trace."
                ),
                (
                    "Stair Model Exchange terminates before public output "
                    "serializes semantic counter 10."
                ),
            ],
            certification=False,
            multiplatform=False,
            veragrid_runtime=False,
        ),
    )
    manifest_path: Path = staging_dir / "manifest.json"
    manifest_file: TextIO = manifest_path.open("x", encoding="utf-8", newline="\n")
    try:
        json.dump(manifest, manifest_file, indent=2, ensure_ascii=True, allow_nan=False)
        manifest_file.write("\n")
    finally:
        manifest_file.close()
    if manifest_path.stat().st_size <= 2_097_152:
        return manifest_path
    else:
        raise ValueError("Evidence manifest exceeds its size boundary")


def _verify_staged_package(
    staging_dir: Path,
    manifest_path: Path,
) -> None:
    """Reopen and verify the complete package before atomic publication.

    :param staging_dir: Owned package staging directory.
    :param manifest_path: Manifest generated inside that directory.
    :return: None after schema, files and hashes are revalidated.
    """

    manifest_content: bytes = _read_explicit_file_bytes(manifest_path, 2_097_152)
    parsed: object = json.loads(manifest_content.decode("utf-8", errors="strict"))
    if isinstance(parsed, dict):
        manifest: dict[str, object] = cast(dict[str, object], parsed)
    else:
        raise ValueError("Evidence manifest root must be an object")
    exact_root_keys: set[str] = set(
        ("schema_name", "source", "corpus", "tools", "policy", "cells", "artifacts", "claim")
    )
    if set(manifest.keys()) == exact_root_keys:
        pass
    else:
        raise ValueError("Evidence manifest root keys are invalid")
    cells_value: object = manifest.get("cells", None)
    artifacts_value: object = manifest.get("artifacts", None)
    if (
        manifest.get("schema_name", None)
        == "veragrid-fmi-reference-execution-v1"
        and isinstance(cells_value, list)
        and len(cells_value) == 16
        and isinstance(artifacts_value, list)
        and len(artifacts_value) == 32
    ):
        artifact_records: list[object] = cast(list[object], artifacts_value)
    else:
        raise ValueError("Evidence manifest cardinality or schema is invalid")
    declared_paths: set[str] = set()
    for artifact_value in artifact_records:
        if isinstance(artifact_value, dict):
            artifact: dict[str, object] = cast(dict[str, object], artifact_value)
        else:
            raise ValueError("Evidence artifact record must be an object")
        if set(artifact.keys()) == set(("path", "cell_id", "kind", "size_bytes", "sha256")):
            pass
        else:
            raise ValueError("Evidence artifact keys are invalid")
        relative_path_value: object = artifact.get("path", None)
        size_value: object = artifact.get("size_bytes", None)
        sha_value: object = artifact.get("sha256", None)
        if (
            isinstance(relative_path_value, str)
            and relative_path_value not in declared_paths
            and re.fullmatch(r"raw/cell-[0-9]{2}/(trace[.]csv|stdout[.]log|stderr[.]log)", relative_path_value)
            is not None
            and isinstance(size_value, int)
            and not isinstance(size_value, bool)
            and isinstance(sha_value, str)
        ):
            relative_path: str = relative_path_value
            declared_paths.add(relative_path)
        else:
            raise ValueError("Evidence artifact identity is invalid")
        artifact_path: Path = staging_dir / Path(relative_path)
        content: bytes = _read_explicit_file_bytes(artifact_path, 4_194_304)
        if len(content) == size_value and hashlib.sha256(content).hexdigest() == sha_value:
            pass
        else:
            raise ValueError("Evidence artifact bytes differ from the manifest")
    physical_paths: set[str] = set()
    for candidate_path in staging_dir.rglob("*"):
        if candidate_path.is_file() and not candidate_path.is_symlink():
            physical_paths.add(candidate_path.relative_to(staging_dir).as_posix())
        else:
            if candidate_path.is_dir() and not candidate_path.is_symlink():
                pass
            else:
                raise ValueError("Evidence package contains an unsafe entry")
    if physical_paths == declared_paths | set(("manifest.json",)):
        pass
    else:
        raise ValueError("Evidence package contains undeclared files")


def generate_reference_fmu_comparison(
    config: ReferenceFmuExecutionConfig,
) -> Path:
    """Execute and atomically publish the complete reference comparison.

    :param config: Explicit validated corpus, tool and output configuration.
    :return: Final published evidence directory.
    """

    if isinstance(config, ReferenceFmuExecutionConfig):
        pass
    else:
        raise ValueError("Reference comparison requires a typed configuration")

    # Copy and revalidate every caller-owned binding once. The remainder of the
    # run consumes only this local owner, so caller rebinding cannot redirect
    # tool validation, corpus reads, staging or publication mid-execution.
    execution_config: ReferenceFmuExecutionConfig = ReferenceFmuExecutionConfig(
        output_dir=config.output_dir,
        source_branch=config.source_branch,
        source_revision=config.source_revision,
        source_tree_sha256=config.source_tree_sha256,
        catalog_path=config.catalog_path,
        corpus_root=config.corpus_root,
        fmpy_expected_version=config.fmpy_expected_version,
        fmpy_expected_distribution_sha256=(
            config.fmpy_expected_distribution_sha256
        ),
        fmusim_executable=config.fmusim_executable,
        fmusim_expected_size_bytes=config.fmusim_expected_size_bytes,
        fmusim_expected_sha256=config.fmusim_expected_sha256,
        fmusim_expected_version=config.fmusim_expected_version,
    )
    output_parent: Path = execution_config.output_dir.parent
    parent_is_valid: bool = bool(
        output_parent.exists()
        and output_parent.is_dir()
        and not output_parent.is_symlink()
        and not execution_config.output_dir.exists()
    )
    if parent_is_valid:
        pass
    else:
        raise ValueError("Reference comparison output parent is invalid")

    # Validate every identity before creating evidence staging or executing FMUs.
    catalog: ReferenceFmuCatalog = load_reference_fmu_catalog(
        execution_config.catalog_path
    )
    fmpy_version: str
    fmpy_distribution_sha256: str
    fmpy_version, fmpy_distribution_sha256 = read_fmpy_distribution_identity()
    if (
        fmpy_version == execution_config.fmpy_expected_version
        and fmpy_distribution_sha256
        == execution_config.fmpy_expected_distribution_sha256
    ):
        pass
    else:
        raise ValueError("Installed FMPy identity does not match configuration")
    _verify_explicit_regular_file(execution_config.fmusim_executable, ".exe")
    fmusim_content: bytes = _read_explicit_file_bytes(
        execution_config.fmusim_executable,
        8 * 1024 * 1024,
    )
    if (
        len(fmusim_content) == execution_config.fmusim_expected_size_bytes
        and hashlib.sha256(fmusim_content).hexdigest()
        == execution_config.fmusim_expected_sha256
    ):
        pass
    else:
        raise ValueError("fmusim executable identity does not match configuration")
    validated_assets: list[ValidatedReferenceFmuAsset | None] = [None] * 4
    reference_traces: list[ReferenceFmuTrace | None] = [None] * 4
    for case_index in range(4):
        reference_case: ReferenceFmuCase = catalog.cases[case_index]
        asset_path: Path = execution_config.corpus_root / Path(
            reference_case.archive_relative_path
        )
        validated_asset: ValidatedReferenceFmuAsset = catalog.validate_asset(
            reference_case.case_id,
            asset_path,
        )
        validated_assets[case_index] = validated_asset
        reference_traces[case_index] = read_reference_fmu_embedded_trace(
            validated_asset
        )

    staging_dir: Path = Path(
        tempfile.mkdtemp(
            prefix=f".{execution_config.output_dir.name}.staging-",
            dir=output_parent,
        )
    )
    runtime_dir: Path = Path(
        tempfile.mkdtemp(
            prefix=f".{execution_config.output_dir.name}.runtime-",
            dir=output_parent,
        )
    )
    publication_succeeded: bool = False
    try:
        staged_fmusim_path: Path = _write_staged_fmusim(
            fmusim_content,
            runtime_dir,
        )
        version_stdout_path: Path = runtime_dir / "version.stdout"
        version_stderr_path: Path = runtime_dir / "version.stderr"
        version_result: ReferenceFmuProcessResult = _run_bounded_fmusim_process(
            (str(staged_fmusim_path), "--version"),
            version_stdout_path,
            version_stderr_path,
            10.0,
            65_536,
        )
        version_stdout: str = _read_explicit_file_bytes(
            version_stdout_path,
            65_536,
        ).decode("utf-8", errors="strict").strip()
        version_stderr: bytes = _read_explicit_file_bytes(
            version_stderr_path,
            65_536,
        )
        if (
            version_result.return_code == 0
            and version_stdout == execution_config.fmusim_expected_version
            and len(version_stderr) == 0
        ):
            version_stdout_path.unlink()
            version_stderr_path.unlink()
        else:
            raise ValueError("fmusim version probe did not match configuration")

        raw_root: Path = staging_dir / "raw"
        raw_root.mkdir()
        traces: list[ReferenceFmuTrace | None] = [None] * 16
        process_results: list[ReferenceFmuProcessResult | None] = [None] * 16
        raw_trace_paths: list[Path | None] = [None] * 16
        for case_index in range(4):
            reference_case = catalog.cases[case_index]
            asset = cast(ValidatedReferenceFmuAsset, validated_assets[case_index])
            case_runtime_dir: Path = runtime_dir / f"case-{case_index:02d}"
            case_runtime_dir.mkdir()
            staged_fmu_path: Path = _write_staged_fmu(asset, case_runtime_dir)
            for interface_index in range(2):
                interface_mode: FmuInterfaceMode = reference_case.interfaces[
                    interface_index
                ]
                for tool_index in range(2):
                    cell_index: int = (
                        case_index * 4 + interface_index * 2 + tool_index
                    )
                    cell_dir: Path = raw_root / f"cell-{cell_index:02d}"
                    cell_dir.mkdir()
                    raw_trace_path: Path = cell_dir / "trace.csv"
                    if tool_index == 0:
                        trace: ReferenceFmuTrace = _execute_fmpy_cell(
                            reference_case,
                            interface_mode,
                            staged_fmu_path,
                            raw_trace_path,
                        )
                        process_result: ReferenceFmuProcessResult | None = None
                    else:
                        trace, process_result = _execute_fmusim_cell(
                            reference_case,
                            interface_mode,
                            staged_fmu_path,
                            staged_fmusim_path,
                            raw_trace_path,
                            cell_dir / "stdout.log",
                            cell_dir / "stderr.log",
                        )
                    traces[cell_index] = trace
                    process_results[cell_index] = process_result
                    raw_trace_paths[cell_index] = raw_trace_path
                    runtime_entries: list[Path] = list(runtime_dir.rglob("*"))
                    runtime_size_bytes: int = 0
                    for runtime_entry in runtime_entries:
                        if runtime_entry.is_file() and not runtime_entry.is_symlink():
                            runtime_size_bytes += runtime_entry.stat().st_size
                        else:
                            if runtime_entry.is_dir() and not runtime_entry.is_symlink():
                                pass
                            else:
                                raise ValueError("Runtime tree contains an unsafe entry")
                    if len(runtime_entries) <= 128 and runtime_size_bytes <= 33_554_432:
                        pass
                    else:
                        raise ValueError("Runtime tree exceeds its resource boundary")
            shutil.rmtree(case_runtime_dir)

        cells: list[ReferenceFmuCellResult | None] = [None] * 16
        for case_index in range(4):
            reference_case = catalog.cases[case_index]
            reference_trace = cast(ReferenceFmuTrace, reference_traces[case_index])
            for interface_index in range(2):
                interface_mode = reference_case.interfaces[interface_index]
                first_cell_index: int = case_index * 4 + interface_index * 2
                second_cell_index: int = first_cell_index + 1
                first_trace: ReferenceFmuTrace = cast(
                    ReferenceFmuTrace,
                    traces[first_cell_index],
                )
                second_trace: ReferenceFmuTrace = cast(
                    ReferenceFmuTrace,
                    traces[second_cell_index],
                )
                if interface_mode == FmuInterfaceMode.CO_SIMULATION:
                    first_evaluation: tuple[
                        float,
                        float,
                        int,
                        ReferenceFmuObservedTermination,
                        ReferenceFmuTerminalObservation,
                    ] = evaluate_reference_fmu_cs_trace(
                        reference_case,
                        first_trace,
                        reference_trace,
                    )
                    second_evaluation: tuple[
                        float,
                        float,
                        int,
                        ReferenceFmuObservedTermination,
                        ReferenceFmuTerminalObservation,
                    ] = evaluate_reference_fmu_cs_trace(
                        reference_case,
                        second_trace,
                        reference_trace,
                    )
                    maximum_absolute_errors: tuple[float, float] = (
                        first_evaluation[0],
                        second_evaluation[0],
                    )
                    maximum_relative_errors: tuple[float, float] = (
                        first_evaluation[1],
                        second_evaluation[1],
                    )
                    maximum_event_errors: tuple[float | None, float | None] = (
                        None,
                        None,
                    )
                    observed_event_counts: tuple[int, int] = (
                        first_evaluation[2],
                        second_evaluation[2],
                    )
                    observed_terminations: tuple[
                        ReferenceFmuObservedTermination,
                        ReferenceFmuObservedTermination,
                    ] = (first_evaluation[3], second_evaluation[3])
                    terminal_observations: tuple[
                        ReferenceFmuTerminalObservation,
                        ReferenceFmuTerminalObservation,
                    ] = (first_evaluation[4], second_evaluation[4])
                    acceptance_basis: ReferenceFmuAcceptanceBasis = (
                        ReferenceFmuAcceptanceBasis.OFFICIAL_REFERENCE
                    )
                    cell_status: ReferenceFmuCellStatus = (
                        ReferenceFmuCellStatus.PASS
                    )
                else:
                    me_evaluation: tuple[float, float, float, float, int, int] = (
                        _evaluate_me_pair_and_oracles(
                            reference_case,
                            first_trace,
                            second_trace,
                        )
                    )
                    maximum_absolute_errors = (
                        me_evaluation[0],
                        me_evaluation[0],
                    )
                    maximum_relative_errors = (
                        me_evaluation[1],
                        me_evaluation[1],
                    )
                    maximum_event_errors = (
                        me_evaluation[2],
                        me_evaluation[3],
                    )
                    observed_event_counts = (
                        me_evaluation[4],
                        me_evaluation[5],
                    )
                    oracle: ReferenceFmuEventOracle = (
                        reference_case.find_interface_oracle(interface_mode)
                    )
                    if oracle.termination_kind == ReferenceFmuTerminationKind.FMU_REQUEST:
                        me_termination: ReferenceFmuObservedTermination = (
                            ReferenceFmuObservedTermination.FMU_TERMINATION_BOUNDARY
                        )
                    else:
                        me_termination = ReferenceFmuObservedTermination.CONFIGURED_STOP
                    observed_terminations = (me_termination, me_termination)
                    if oracle.terminal_post_event_observable:
                        terminal_observation = (
                            ReferenceFmuTerminalObservation.SUSTAINED_TERMINAL_VALUE
                        )
                        cell_status = ReferenceFmuCellStatus.PASS
                    else:
                        terminal_observation = (
                            ReferenceFmuTerminalObservation.PRE_TERMINAL_VALUE_ONLY
                        )
                        cell_status = (
                            ReferenceFmuCellStatus.PASS_WITH_OBSERVABILITY_LIMIT
                        )
                    terminal_observations = (
                        terminal_observation,
                        terminal_observation,
                    )
                    acceptance_basis = (
                        ReferenceFmuAcceptanceBasis.TOOL_PAIR_AND_INTERFACE_ORACLE
                    )
                interface_token: str
                if interface_mode == FmuInterfaceMode.CO_SIMULATION:
                    interface_token = "cs"
                else:
                    interface_token = "me"
                first_cell_id: str = (
                    f"cell-{first_cell_index:02d}--{reference_case.case_id}--"
                    f"{interface_token}--fmpy"
                )
                second_cell_id: str = (
                    f"cell-{second_cell_index:02d}--{reference_case.case_id}--"
                    f"{interface_token}--fmusim"
                )
                cell_ids: tuple[str, str] = (first_cell_id, second_cell_id)
                peer_ids: tuple[str, str] = (second_cell_id, first_cell_id)
                cell_tools: tuple[ReferenceFmuExecutionTool, ...] = (
                    ReferenceFmuExecutionTool.FMPY,
                    ReferenceFmuExecutionTool.FMUSIM,
                )
                cell_indices: tuple[int, int] = (
                    first_cell_index,
                    second_cell_index,
                )
                for pair_index in range(2):
                    current_index: int = cell_indices[pair_index]
                    cells[current_index] = ReferenceFmuCellResult(
                        cell_index=current_index,
                        cell_id=cell_ids[pair_index],
                        tool=cell_tools[pair_index],
                        case=reference_case,
                        interface_mode=interface_mode,
                        status=cell_status,
                        acceptance_basis=acceptance_basis,
                        trace=cast(ReferenceFmuTrace, traces[current_index]),
                        raw_trace_path=cast(Path, raw_trace_paths[current_index]),
                        process_result=process_results[current_index],
                        peer_cell_id=peer_ids[pair_index],
                        maximum_absolute_error=maximum_absolute_errors[pair_index],
                        maximum_relative_error=maximum_relative_errors[pair_index],
                        maximum_event_time_error_seconds=maximum_event_errors[pair_index],
                        observed_event_count=observed_event_counts[pair_index],
                        observed_termination=observed_terminations[pair_index],
                        terminal_observation=terminal_observations[pair_index],
                    )

        canonical_cells: tuple[ReferenceFmuCellResult, ...] = tuple(
            cast(ReferenceFmuCellResult, cell) for cell in cells
        )
        generated_at_utc: str = datetime.now(timezone.utc).replace(
            microsecond=0
        ).isoformat().replace("+00:00", "Z")
        manifest_path: Path = _write_manifest(
            execution_config,
            catalog,
            canonical_cells,
            staging_dir,
            generated_at_utc,
            fmpy_version,
            fmpy_distribution_sha256,
        )
        _verify_staged_package(staging_dir, manifest_path)
        shutil.rmtree(runtime_dir)
        os.replace(staging_dir, execution_config.output_dir)
        publication_succeeded = True
    finally:
        if publication_succeeded:
            pass
        else:
            if runtime_dir.exists():
                shutil.rmtree(runtime_dir)
            else:
                pass
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
            else:
                pass
    return execution_config.output_dir
