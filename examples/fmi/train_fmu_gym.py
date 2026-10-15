"""Generate authenticated train_fmu_gym comparison evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from uuid import uuid4

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from examples.fmi.evidence_identity import (
    path_is_link_or_reparse_point,
    read_regular_tree_identity,
    verify_regular_file_identity,
)


class TrainFmuGymCellStatus(str, Enum):
    """Accepted cell verdicts."""

    PASS = "PASS"
    COMPLETED_WITH_FINDINGS = "COMPLETED_WITH_FINDINGS"


class TrainFmuGymFindingKind(str, Enum):
    """Upstream findings retained by this comparison."""

    CHILD_INTERPRETER_NOT_BOUND = "TRAIN_FMU_GYM_CHILD_INTERPRETER_NOT_BOUND"
    CHILD_FAILURE_NOT_PROPAGATED = "TRAIN_FMU_GYM_CHILD_FAILURE_NOT_PROPAGATED"


class TrainFmuGymComparisonConfig:
    """Caller-owned identities and execution limits for the comparison."""

    __slots__ = (
        "output_directory", "source_branch", "source_revision",
        "source_tree_sha256", "upstream_root", "upstream_commit",
        "upstream_git_tree", "runtime_root", "runtime_file_count",
        "runtime_total_size_bytes", "runtime_tree_sha256",
        "python_size_bytes", "python_sha256", "cli_python_path",
        "cli_python_size_bytes", "cli_python_sha256",
        "worker_path", "worker_size_bytes", "worker_sha256",
        "fmi_two_path", "fmi_two_size_bytes", "fmi_two_sha256",
        "fmi_three_path", "fmi_three_size_bytes", "fmi_three_sha256",
        "system_root", "temporary_directory", "processor_architecture",
        "process_timeout_seconds", "stream_limit_bytes",
    )

    def __init__(
        self,
        output_directory: Path,
        source_branch: str,
        source_revision: str,
        source_tree_sha256: str,
        upstream_root: Path,
        upstream_commit: str,
        upstream_git_tree: str,
        runtime_root: Path,
        runtime_file_count: int,
        runtime_total_size_bytes: int,
        runtime_tree_sha256: str,
        python_size_bytes: int,
        python_sha256: str,
        cli_python_path: Path,
        cli_python_size_bytes: int,
        cli_python_sha256: str,
        worker_path: Path,
        worker_size_bytes: int,
        worker_sha256: str,
        fmi_two_path: Path,
        fmi_two_size_bytes: int,
        fmi_two_sha256: str,
        fmi_three_path: Path,
        fmi_three_size_bytes: int,
        fmi_three_sha256: str,
        system_root: Path,
        temporary_directory: Path,
        processor_architecture: str,
        process_timeout_seconds: float,
        stream_limit_bytes: int,
    ) -> None:
        """Store the complete closed comparison configuration.

        :param output_directory: New package directory published atomically.
        :param source_branch: VeraGrid branch represented by the evidence.
        :param source_revision: VeraGrid revision represented by the evidence.
        :param source_tree_sha256: VeraGrid source-tree identity.
        :param upstream_root: Canonical train_fmu_gym checkout root.
        :param upstream_commit: Required upstream Git commit.
        :param upstream_git_tree: Required upstream Git tree.
        :param runtime_root: Caller-owned Python virtual environment.
        :param runtime_file_count: Required runtime regular-file count.
        :param runtime_total_size_bytes: Required runtime byte total.
        :param runtime_tree_sha256: Required runtime tree digest.
        :param python_size_bytes: Required contained Python size.
        :param python_sha256: Required contained Python digest.
        :param cli_python_path: Exact interpreter selected by upstream literal command.
        :param cli_python_size_bytes: Required selected interpreter size.
        :param cli_python_sha256: Required selected interpreter digest.
        :param worker_path: Maintained isolated worker source.
        :param worker_size_bytes: Required worker size.
        :param worker_sha256: Required worker digest.
        :param fmi_two_path: Generated FMI 2 training FMU.
        :param fmi_two_size_bytes: Required FMI 2 FMU size.
        :param fmi_two_sha256: Required FMI 2 FMU digest.
        :param fmi_three_path: Generated FMI 3 training FMU.
        :param fmi_three_size_bytes: Required FMI 3 FMU size.
        :param fmi_three_sha256: Required FMI 3 FMU digest.
        :param system_root: Explicit Windows system root for children.
        :param temporary_directory: Explicit private temporary root.
        :param processor_architecture: Explicit child architecture label.
        :param process_timeout_seconds: Per-process timeout.
        :param stream_limit_bytes: Independent stdout/stderr byte bound.
        """

        self.output_directory: Path = output_directory
        self.source_branch: str = source_branch
        self.source_revision: str = source_revision
        self.source_tree_sha256: str = source_tree_sha256
        self.upstream_root: Path = upstream_root
        self.upstream_commit: str = upstream_commit
        self.upstream_git_tree: str = upstream_git_tree
        self.runtime_root: Path = runtime_root
        self.runtime_file_count: int = runtime_file_count
        self.runtime_total_size_bytes: int = runtime_total_size_bytes
        self.runtime_tree_sha256: str = runtime_tree_sha256
        self.python_size_bytes: int = python_size_bytes
        self.python_sha256: str = python_sha256
        self.cli_python_path: Path = cli_python_path
        self.cli_python_size_bytes: int = cli_python_size_bytes
        self.cli_python_sha256: str = cli_python_sha256
        self.worker_path: Path = worker_path
        self.worker_size_bytes: int = worker_size_bytes
        self.worker_sha256: str = worker_sha256
        self.fmi_two_path: Path = fmi_two_path
        self.fmi_two_size_bytes: int = fmi_two_size_bytes
        self.fmi_two_sha256: str = fmi_two_sha256
        self.fmi_three_path: Path = fmi_three_path
        self.fmi_three_size_bytes: int = fmi_three_size_bytes
        self.fmi_three_sha256: str = fmi_three_sha256
        self.system_root: Path = system_root
        self.temporary_directory: Path = temporary_directory
        self.processor_architecture: str = processor_architecture
        self.process_timeout_seconds: float = process_timeout_seconds
        self.stream_limit_bytes: int = stream_limit_bytes


class TrainFmuGymCellResult:
    """One authenticated worker result and its retained raw paths."""

    __slots__ = ("name", "status", "result", "directory")

    def __init__(
        self,
        name: str,
        status: TrainFmuGymCellStatus,
        result: dict[str, object],
        directory: Path,
    ) -> None:
        """Create a comparison cell result.

        :param name: Stable cell identifier.
        :param status: Evaluated cell verdict.
        :param result: Authenticated structured worker payload.
        :param directory: Directory containing retained raw outputs.
        """

        self.name: str = name
        self.status: TrainFmuGymCellStatus = status
        self.result: dict[str, object] = result
        self.directory: Path = directory


def _validate_train_fmu_gym_config(config: TrainFmuGymComparisonConfig) -> Path:
    """Authenticate every external input before target code executes.

    :param config: Complete caller-owned comparison configuration.
    :return: Contained Python executable path.
    :raises ValueError: If an identity or containment check fails.
    """

    runtime_root: Path = config.runtime_root.resolve(strict=True)
    if path_is_link_or_reparse_point(runtime_root):
        raise ValueError("The train_fmu_gym runtime root must not be a reparse point")
    else:
        observed_tree: tuple[int, int, str] = read_regular_tree_identity(runtime_root)
        expected_tree: tuple[int, int, str] = (
            config.runtime_file_count,
            config.runtime_total_size_bytes,
            config.runtime_tree_sha256,
        )
        if observed_tree != expected_tree:
            raise ValueError("Unexpected train_fmu_gym runtime tree identity")
        else:
            python_path: Path = (runtime_root / "Scripts" / "python.exe").resolve(strict=True)
            if runtime_root not in python_path.parents:
                raise ValueError("Python executable escapes the authenticated runtime")
            else:
                verify_regular_file_identity(
                    python_path, config.python_size_bytes, config.python_sha256
                )
    verify_regular_file_identity(
        config.worker_path, config.worker_size_bytes, config.worker_sha256
    )
    verify_regular_file_identity(
        config.cli_python_path, config.cli_python_size_bytes,
        config.cli_python_sha256,
    )
    verify_regular_file_identity(
        config.fmi_two_path, config.fmi_two_size_bytes, config.fmi_two_sha256
    )
    verify_regular_file_identity(
        config.fmi_three_path, config.fmi_three_size_bytes, config.fmi_three_sha256
    )
    if config.upstream_commit != "3e561ef9b6f7742ef00e2dd6290c7b32db0cf50d":
        raise ValueError("Unexpected train_fmu_gym commit")
    else:
        if config.upstream_git_tree != "e8a407a18b0ca787ce614a870198be2169d60662":
            raise ValueError("Unexpected train_fmu_gym Git tree")
        else:
            return python_path

def _run_train_fmu_gym_worker(
    config: TrainFmuGymComparisonConfig,
    python_path: Path,
    mode: str,
    environment_name: str,
    fmu_path: Path,
    output_directory: Path,
) -> None:
    """Run one bounded worker with a closed explicit environment.

    :param config: Complete comparison configuration.
    :param python_path: Authenticated contained interpreter.
    :param mode: Exact worker enum member name.
    :param environment_name: Registered Gymnasium environment.
    :param fmu_path: Authenticated FMU for the cell.
    :param output_directory: Private raw-output directory.
    :return: None.
    """

    cli_python_path: Path = config.cli_python_path.resolve(strict=True)
    system_root: Path = config.system_root.resolve(strict=True)
    search_paths: list[str] = list(
        (str(cli_python_path.parent), str(system_root / "System32"), str(system_root))
    )
    child_environment: dict[str, str] = dict(
        SystemRoot=str(config.system_root.resolve(strict=True)),
        TEMP=str(config.temporary_directory.resolve(strict=True)),
        TMP=str(config.temporary_directory.resolve(strict=True)),
        PROCESSOR_ARCHITECTURE=config.processor_architecture,
        PATH=os.pathsep.join(search_paths),
    )
    command: list[str] = list(
        (
            str(python_path), "-B", "-I", str(config.worker_path),
            "--mode", mode, "--environment", environment_name,
            "--fmu", str(fmu_path), "--output-directory", str(output_directory),
        )
    )
    process: subprocess.CompletedProcess[bytes] = subprocess.run(
        command,
        cwd=config.upstream_root,
        env=child_environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=config.process_timeout_seconds,
        check=False,
    )
    if len(process.stdout) > config.stream_limit_bytes:
        raise ValueError("train_fmu_gym worker stdout exceeded its bound")
    else:
        if len(process.stderr) > config.stream_limit_bytes:
            raise ValueError("train_fmu_gym worker stderr exceeded its bound")
        else:
            (output_directory / "worker-stdout.log").write_bytes(process.stdout)
            (output_directory / "worker-stderr.log").write_bytes(process.stderr)
            if process.returncode != 0:
                raise ValueError(
                    "train_fmu_gym worker failed: "
                    + process.stderr.decode("utf-8", errors="replace")
                )
            else:
                if not (output_directory / "result.json").is_file():
                    raise ValueError("train_fmu_gym worker produced no result")
                else:
                    return None


def _read_train_fmu_gym_worker_result(
    name: str,
    directory: Path,
) -> TrainFmuGymCellResult:
    """Parse and classify one retained worker result.

    :param name: Stable comparison-cell identifier.
    :param directory: Raw cell directory.
    :return: Typed evaluated cell result.
    """

    result_path: Path = directory / "result.json"
    payload_value: object = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(payload_value, dict):
        raise ValueError("Worker result must be a JSON object")
    else:
        payload: dict[str, object] = payload_value
        status_value: object = payload.get("status", None)
        if status_value == TrainFmuGymCellStatus.PASS.name:
            status: TrainFmuGymCellStatus = TrainFmuGymCellStatus.PASS
        else:
            if status_value == TrainFmuGymCellStatus.COMPLETED_WITH_FINDINGS.name:
                status = TrainFmuGymCellStatus.COMPLETED_WITH_FINDINGS
            else:
                raise ValueError("Unexpected worker status")
        return TrainFmuGymCellResult(name, status, payload, directory)


def _evaluate_train_fmu_gym_cells(
    cells: tuple[TrainFmuGymCellResult, ...],
) -> None:
    """Apply the training and CLI acceptance contracts.

    :param cells: Four ordered authenticated worker results.
    :return: None.
    """

    if len(cells) != 4:
        raise ValueError("Exactly four train_fmu_gym cells are required")
    else:
        core_index: int = 0
        while core_index < 2:
            core: TrainFmuGymCellResult = cells[core_index]
            changed: object = core.result.get("parameters_changed", None)
            parameter_count: object = core.result.get("parameter_count", None)
            evaluation_steps: object = core.result.get("evaluation_steps", None)
            finite_values: tuple[object, object, object] = (
                core.result.get("finite_observations", None),
                core.result.get("finite_actions", None),
                core.result.get("finite_rewards", None),
            )
            if (
                core.status != TrainFmuGymCellStatus.PASS
                or changed is not True
                or parameter_count != 739
                or evaluation_steps != 256
                or finite_values != (True, True, True)
            ):
                raise ValueError("A direct training cell failed its numerical contract")
            else:
                core_index += 1
        cli_index: int = 2
        while cli_index < 4:
            cli: TrainFmuGymCellResult = cells[cli_index]
            if cli.status == TrainFmuGymCellStatus.PASS:
                artifact_count: object = cli.result.get("trained_artifact_count", None)
                if not isinstance(artifact_count, int) or artifact_count < 1:
                    raise ValueError("CLI PASS requires a trained-agent artifact")
                else:
                    cli_index += 1
            else:
                findings: object = cli.result.get("findings", None)
                expected_findings: list[str] = list(
                    (
                        TrainFmuGymFindingKind.CHILD_INTERPRETER_NOT_BOUND.value,
                        TrainFmuGymFindingKind.CHILD_FAILURE_NOT_PROPAGATED.value,
                    )
                )
                if findings != expected_findings:
                    raise ValueError("CLI findings do not match the closed contract")
                else:
                    cli_index += 1


def _render_train_fmu_gym_figure(
    fmi_two_trace: np.ndarray,
    fmi_three_trace: np.ndarray,
    figure_directory: Path,
) -> None:
    """Render the accepted FMI 2/FMI 3 training trajectories.

    :param fmi_two_trace: Accepted FMI 2 evaluation matrix.
    :param fmi_three_trace: Accepted FMI 3 evaluation matrix.
    :param figure_directory: Directory receiving PNG, SVG and PDF.
    :return: None.
    """

    time_values: np.ndarray = fmi_two_trace[:, 0]
    if not np.array_equal(time_values, fmi_three_trace[:, 0]):
        raise ValueError("Training traces use different time lattices")
    else:
        residual: np.ndarray = np.max(
            np.abs(fmi_three_trace[:, 1:5] - fmi_two_trace[:, 1:5]), axis=1
        )
        style: dict[str, object] = dict(
            (
                ("font.family", "DejaVu Sans"),
                ("font.size", 8.0),
                ("axes.linewidth", 0.8),
                ("xtick.direction", "in"),
                ("ytick.direction", "in"),
                ("pdf.fonttype", 42),
                ("svg.fonttype", "none"),
                ("svg.hashsalt", "veragrid-train-fmu-gym-comparison"),
            )
        )
        png_metadata: dict[str, str] = dict(
            Software="VeraGrid train_fmu_gym FMI comparison"
        )
        svg_metadata: dict[str, str] = dict(
            Creator="VeraGrid train_fmu_gym FMI comparison",
            Date="1970-01-01T00:00:00Z",
        )
        fixed_pdf_time: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)
        pdf_metadata: dict[str, object] = dict(
            Creator="VeraGrid train_fmu_gym FMI comparison",
            CreationDate=fixed_pdf_time,
            ModDate=fixed_pdf_time,
        )
        with plt.rc_context(style):
            figure: Figure
            axes: np.ndarray
            figure, axes = plt.subplots(4, 1, figsize=(7.2, 6.0), sharex=True)
            position_axis: Axes = axes[0]
            angle_axis: Axes = axes[1]
            action_axis: Axes = axes[2]
            residual_axis: Axes = axes[3]
            position_axis.plot(time_values, fmi_two_trace[:, 1], "k-", label="FMI 2.0 CS")
            position_axis.plot(time_values, fmi_three_trace[:, 1], color="#0072B2", linestyle="--", label="FMI 3.0 CS")
            position_axis.set_ylabel("Cart position [m]")
            position_axis.legend(loc="upper left", ncols=2)
            angle_axis.plot(time_values, fmi_two_trace[:, 3], "k-")
            angle_axis.plot(time_values, fmi_three_trace[:, 3], color="#0072B2", linestyle="--")
            angle_axis.set_ylabel("Pole angle [rad]")
            action_axis.plot(time_values[1:], fmi_two_trace[1:, 5], "k-")
            action_axis.plot(time_values[1:], fmi_three_trace[1:, 5], color="#0072B2", linestyle="--")
            action_axis.set_ylabel("Policy action\n[normalized]")
            residual_axis.plot(time_values, residual, color="#D55E00")
            residual_axis.set_ylabel("Max. state\n|FMI 3 - FMI 2|")
            residual_axis.set_xlabel("Evaluation time [s]")
            axis: Axes
            for axis in axes:
                axis.grid(axis="y", color="0.86", linewidth=0.5)
                axis.set_xlim(float(time_values[0]), float(time_values[-1]))
            figure_directory.mkdir(parents=True, exist_ok=False)
            output_base: Path = figure_directory / "train-fmu-gym-fmi2-fmi3-training"
            figure.savefig(
                output_base.with_suffix(".png"), dpi=300, metadata=png_metadata
            )
            figure.savefig(output_base.with_suffix(".svg"), metadata=svg_metadata)
            figure.savefig(output_base.with_suffix(".pdf"), metadata=pdf_metadata)
            plt.close(figure)


def _write_train_fmu_gym_manifest(
    config: TrainFmuGymComparisonConfig,
    cells: tuple[TrainFmuGymCellResult, ...],
    package_root: Path,
) -> Path:
    """Write the claim-bounded package manifest.

    :param config: Complete comparison configuration.
    :param cells: Four accepted comparison cells.
    :param package_root: Complete unpublished package root.
    :return: Manifest path.
    """

    file_records: list[dict[str, object]] = list()
    package_file: Path
    for package_file in sorted(package_root.rglob("*")):
        if package_file.is_file() and package_file.name != "manifest.json":
            relative_path: str = package_file.relative_to(package_root).as_posix()
            digest: str = hashlib.sha256(package_file.read_bytes()).hexdigest()
            file_records.append(dict(path=relative_path, size_bytes=package_file.stat().st_size, sha256=digest))
        else:
            pass
    cell_records: list[dict[str, object]] = list()
    cell: TrainFmuGymCellResult
    for cell in cells:
        cell_records.append(dict(name=cell.name, status=cell.status.name, result=cell.result))
    manifest: dict[str, object] = dict(
        schema="veragrid.fmi-train-fmu-gym-comparison/1",
        status="COMPLETED_WITH_FINDINGS",
        source=dict(branch=config.source_branch, revision=config.source_revision, tree_sha256=config.source_tree_sha256),
        upstream=dict(repository="https://codebase.helmholtz.cloud/dlr-vsdc/train_fmu_gym.git", commit=config.upstream_commit, git_tree=config.upstream_git_tree, version="0.8.1"),
        cells=cell_records,
        findings=list((TrainFmuGymFindingKind.CHILD_INTERPRETER_NOT_BOUND.value, TrainFmuGymFindingKind.CHILD_FAILURE_NOT_PROPAGATED.value)),
        claim_boundary=dict(proven=list(("FMI 2 and FMI 3 Co-Simulation environments complete real A2C optimization and deterministic evaluation on the recorded Windows runtime.",)), not_proven=list(("Public tfg train storage lifecycle completion.", "Independent FMI solver diversity.", "Certification or multiplatform support."))),
        figures=dict(formats=list(("png", "svg", "pdf")), width_inches=7.2, height_inches=6.0, dpi=300, png_width_pixels=2160, png_height_pixels=1800),
        files=file_records,
    )
    manifest_path: Path = package_root / "manifest.json"
    manifest_bytes: bytes = (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    manifest_path.write_bytes(manifest_bytes)
    return manifest_path


def _verify_train_fmu_gym_package(
    config: TrainFmuGymComparisonConfig,
    package_root: Path,
    authenticate_external_inputs: bool,
) -> None:
    """Reopen and verify one complete evidence package.

    :param config: Complete comparison configuration.
    :param package_root: Staging or published package root.
    :param authenticate_external_inputs: Whether to reauthenticate the external
        runtime and input artifacts before reopening the package.
    :return: None.
    """

    if authenticate_external_inputs:
        _validate_train_fmu_gym_config(config)
    else:
        pass
    resolved_package_root: Path = package_root.resolve(strict=True)
    paths: list[Path] = list(resolved_package_root.rglob("*"))
    package_path: Path
    for package_path in paths:
        if path_is_link_or_reparse_point(package_path):
            raise ValueError("Evidence package contains a reparse point")
        else:
            pass
    manifest_path: Path = resolved_package_root / "manifest.json"
    manifest_value: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest_value, dict):
        raise ValueError("Comparison manifest must be an object")
    else:
        manifest: dict[str, object] = manifest_value
        if manifest.get("schema", None) != "veragrid.fmi-train-fmu-gym-comparison/1":
            raise ValueError("Unexpected train_fmu_gym manifest schema")
        else:
            expected_findings: list[str] = list(
                (
                    TrainFmuGymFindingKind.CHILD_INTERPRETER_NOT_BOUND.value,
                    TrainFmuGymFindingKind.CHILD_FAILURE_NOT_PROPAGATED.value,
                )
            )
            expected_source: dict[str, object] = dict(
                branch=config.source_branch,
                revision=config.source_revision,
                tree_sha256=config.source_tree_sha256,
            )
            expected_upstream: dict[str, object] = dict(
                repository="https://codebase.helmholtz.cloud/dlr-vsdc/train_fmu_gym.git",
                commit=config.upstream_commit,
                git_tree=config.upstream_git_tree,
                version="0.8.1",
            )
            if (
                manifest.get("status", None) != "COMPLETED_WITH_FINDINGS"
                or manifest.get("findings", None) != expected_findings
                or manifest.get("source", None) != expected_source
                or manifest.get("upstream", None) != expected_upstream
            ):
                raise ValueError("Unexpected train_fmu_gym package status")
            else:
                pass

    # Bind every declared path to its exact bytes and reject undeclared output.
    file_records_value: object = manifest.get("files", None)
    if not isinstance(file_records_value, list) or len(file_records_value) != 21:
        raise ValueError("train_fmu_gym manifest must bind exactly 21 files")
    else:
        file_records: list[object] = file_records_value
    declared_paths: set[str] = set()
    file_record: object
    for file_record in file_records:
        if not isinstance(file_record, dict):
            raise ValueError("train_fmu_gym file record must be an object")
        else:
            record: dict[str, object] = file_record
        if tuple(sorted(record.keys())) != ("path", "sha256", "size_bytes"):
            raise ValueError("Unexpected train_fmu_gym file-record fields")
        else:
            pass
        relative_value: object = record.get("path", None)
        size_value: object = record.get("size_bytes", None)
        digest_value: object = record.get("sha256", None)
        if (
            not isinstance(relative_value, str)
            or not isinstance(size_value, int)
            or not isinstance(digest_value, str)
            or len(digest_value) != 64
        ):
            raise ValueError("Invalid train_fmu_gym file-record value")
        else:
            relative_path: Path = Path(relative_value)
        if (
            relative_path.is_absolute()
            or ".." in relative_path.parts
            or relative_path.as_posix() != relative_value
            or relative_value in declared_paths
        ):
            raise ValueError("Unsafe or duplicate train_fmu_gym package path")
        else:
            declared_paths.add(relative_value)
        bound_path: Path = (resolved_package_root / relative_path).resolve(strict=True)
        if resolved_package_root not in bound_path.parents:
            raise ValueError("train_fmu_gym package path escapes its root")
        else:
            verify_regular_file_identity(bound_path, size_value, digest_value)
    discovered_paths: set[str] = set()
    discovered_path: Path
    for discovered_path in paths:
        if discovered_path.is_file():
            discovered_paths.add(
                discovered_path.relative_to(resolved_package_root).as_posix()
            )
        else:
            pass
    expected_paths: set[str] = set(declared_paths)
    expected_paths.add("manifest.json")
    if discovered_paths != expected_paths:
        raise ValueError("train_fmu_gym package closure changed")
    else:
        pass

    # Reconstruct and re-evaluate all four retained worker results.
    raw_root: Path = resolved_package_root / "raw"
    cell_names: tuple[str, str, str, str] = (
        "fmi2-training-core", "fmi3-training-core",
        "fmi2-public-cli", "fmi3-public-cli",
    )
    reconstructed_results: list[TrainFmuGymCellResult] = list()
    cell_name: str
    for cell_name in cell_names:
        reconstructed_results.append(
            _read_train_fmu_gym_worker_result(cell_name, raw_root / cell_name)
        )
    reconstructed_cells: tuple[TrainFmuGymCellResult, ...] = tuple(
        reconstructed_results
    )
    _evaluate_train_fmu_gym_cells(reconstructed_cells)
    expected_cell_records: list[dict[str, object]] = list()
    reconstructed_cell: TrainFmuGymCellResult
    for reconstructed_cell in reconstructed_cells:
        expected_cell_records.append(
            dict(
                name=reconstructed_cell.name,
                status=reconstructed_cell.status.name,
                result=reconstructed_cell.result,
            )
        )
    if manifest.get("cells", None) != expected_cell_records:
        raise ValueError("train_fmu_gym manifest cells differ from raw results")
    else:
        pass

    # Recompute numerical trace invariants rather than trusting result metadata.
    fmi_two_trace: np.ndarray = np.loadtxt(
        raw_root / "fmi2-training-core" / "trace.csv",
        delimiter=",", skiprows=1,
    )
    fmi_three_trace: np.ndarray = np.loadtxt(
        raw_root / "fmi3-training-core" / "trace.csv",
        delimiter=",", skiprows=1,
    )
    if (
        fmi_two_trace.shape != (257, 7)
        or fmi_three_trace.shape != (257, 7)
        or not np.all(np.isfinite(fmi_two_trace[:, 0:5]))
        or not np.all(np.isfinite(fmi_three_trace[:, 0:5]))
        or not np.all(np.isfinite(fmi_two_trace[1:, 5:7]))
        or not np.all(np.isfinite(fmi_three_trace[1:, 5:7]))
        or not np.all(np.diff(fmi_two_trace[:, 0]) > 0.0)
        or not np.all(np.diff(fmi_three_trace[:, 0]) > 0.0)
    ):
        raise ValueError("train_fmu_gym trace invariants changed")
    else:
        pass
    trace_index: int = 0
    while trace_index < 2:
        trace_cell: TrainFmuGymCellResult = reconstructed_cells[trace_index]
        trace: np.ndarray
        if trace_index == 0:
            trace = fmi_two_trace
        else:
            trace = fmi_three_trace
        reward_sum_value: object = trace_cell.result.get("reward_sum", None)
        if (
            not isinstance(reward_sum_value, float)
            or not np.isclose(
                float(np.sum(trace[1:, 6])), reward_sum_value,
                rtol=1.0e-12, atol=1.0e-12,
            )
        ):
            raise ValueError("train_fmu_gym reward aggregate changed")
        else:
            trace_index += 1

    # Re-render from the authenticated traces and require identical artifacts.
    verification_root: Path = Path(
        tempfile.mkdtemp(
            prefix=".train-fmu-gym-figure-verification-",
            dir=resolved_package_root.parent,
        )
    )
    try:
        _render_train_fmu_gym_figure(
            fmi_two_trace, fmi_three_trace, verification_root / "figures"
        )
        figure_suffixes: tuple[str, str, str] = (".png", ".svg", ".pdf")
        figure_suffix: str
        for figure_suffix in figure_suffixes:
            figure_name: str = (
                "train-fmu-gym-fmi2-fmi3-training" + figure_suffix
            )
            published_bytes: bytes = (
                resolved_package_root / "figures" / figure_name
            ).read_bytes()
            reconstructed_bytes: bytes = (
                verification_root / "figures" / figure_name
            ).read_bytes()
            if published_bytes != reconstructed_bytes:
                raise ValueError(
                    "train_fmu_gym figure differs from reconstructed evidence"
                )
            else:
                pass
    finally:
        cleanup_is_scoped: bool = bool(
            verification_root.parent == resolved_package_root.parent
            and verification_root.name.startswith(
                ".train-fmu-gym-figure-verification-"
            )
        )
        if cleanup_is_scoped and verification_root.exists():
            shutil.rmtree(verification_root)
        else:
            pass
    canonical_manifest: bytes = (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    if manifest_path.read_bytes() != canonical_manifest:
        raise ValueError("train_fmu_gym manifest is not canonically encoded")
    else:
        return None


def generate_train_fmu_gym_comparison(config: TrainFmuGymComparisonConfig) -> Path:
    """Execute four workers and atomically publish their evidence.

    :param config: Complete comparison configuration.
    :return: Published package directory.
    """

    python_path: Path = _validate_train_fmu_gym_config(config)
    if config.output_directory.exists():
        raise ValueError("Output directory already exists")
    else:
        pass
    staging_root: Path = config.output_directory.parent / (
        config.output_directory.name + ".staging-" + uuid4().hex
    )
    staging_root.mkdir(parents=False, exist_ok=False)
    published: bool = False
    try:
        raw_root: Path = staging_root / "raw"
        raw_root.mkdir()
        cell_specs: tuple[tuple[str, str, str, Path], ...] = (
            ("fmi2-training-core", "TRAINING_CORE", "tfg_reward_fmi2_v1", config.fmi_two_path),
            ("fmi3-training-core", "TRAINING_CORE", "tfg_reward_fmi3_v1", config.fmi_three_path),
            ("fmi2-public-cli", "PUBLIC_CLI", "tfg_reward_fmi2_v1", config.fmi_two_path),
            ("fmi3-public-cli", "PUBLIC_CLI", "tfg_reward_fmi3_v1", config.fmi_three_path),
        )
        results: list[TrainFmuGymCellResult] = list()
        cell_spec: tuple[str, str, str, Path]
        for cell_spec in cell_specs:
            cell_directory: Path = raw_root / cell_spec[0]
            cell_directory.mkdir()
            _run_train_fmu_gym_worker(config, python_path, cell_spec[1], cell_spec[2], cell_spec[3], cell_directory)
            results.append(_read_train_fmu_gym_worker_result(cell_spec[0], cell_directory))
        cells: tuple[TrainFmuGymCellResult, ...] = tuple(results)
        _evaluate_train_fmu_gym_cells(cells)
        fmi_two_trace: np.ndarray = np.loadtxt(raw_root / "fmi2-training-core" / "trace.csv", delimiter=",", skiprows=1)
        fmi_three_trace: np.ndarray = np.loadtxt(raw_root / "fmi3-training-core" / "trace.csv", delimiter=",", skiprows=1)
        _render_train_fmu_gym_figure(fmi_two_trace, fmi_three_trace, staging_root / "figures")
        _write_train_fmu_gym_manifest(config, cells, staging_root)
        _verify_train_fmu_gym_package(config, staging_root, False)
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
    _verify_train_fmu_gym_package(config, config.output_directory, True)
    return config.output_directory

