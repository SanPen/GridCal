"""Generate six external first-order FMI fixtures and local preflight evidence."""

from __future__ import annotations
from VeraGridEngine.enumerations import InterfaceType

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import traceback
import zipfile

import fmpy
from fmpy import read_model_description, simulate_fmu
import numpy as np

import VeraGridEngine
import VeraGridEngine.IO.fmu.interface as interface_api
from VeraGridEngine.enumerations import FmiVersion
from VeraGridEngine.IO.fmu.compiler import Compiler
from VeraGridEngine.IO.fmu.interface import export_model_as_fmu
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.IO.fmu.config import (
    ExportConfig as CsExportConfig,
    detect_target_platform as detect_cs_target_platform,
)
from VeraGridEngine.IO.fmu.config import (
    ExportConfig as MeExportConfig,
    detect_target_platform as detect_me_target_platform,
)
from examples.fmi.evidence_identity import (
    verify_regular_file_identity,
)


def verify_source_provenance(
    repository_root: Path,
    git_executable: Path,
    expected_head: str,
    expected_tree: str,
    output_dir: Path,
    exporter_module_paths: tuple[Path, ...],
) -> dict[str, object]:
    """Verify the checkout, imports, output boundary, and Python cache state.

    The pre-commit topology permits only this maintained recipe subtree and its
    parent discovery README to be unstaged. Product source and dependencies must
    remain identical to the explicitly selected Git commit and tree.

    :param repository_root: Explicit VeraGrid checkout root.
    :param git_executable: Explicit Git executable used for observations.
    :param expected_head: Required 40-character Git commit identifier.
    :param expected_tree: Required 40-character Git tree identifier.
    :param output_dir: New caller-owned output directory outside the checkout.
    :param exporter_module_paths: Imported VeraGrid module files to bind to src.
    :return: Observed Git identity, allowed dirty paths, imports, and cache state.
    """

    if sys.dont_write_bytecode:
        pass
    else:
        raise ValueError("Run this module with python -B -m")

    canonical_repository: Path = repository_root.resolve(strict=True)
    canonical_git: Path = git_executable.resolve(strict=True)
    canonical_output: Path = output_dir.resolve(strict=False)
    expected_source_root: Path = (
        canonical_repository / "src" / "VeraGridEngine"
    ).resolve(strict=True)
    arguments_are_valid: bool = bool(
        canonical_repository.is_dir()
        and canonical_git.is_file()
        and len(expected_head) == 40
        and len(expected_tree) == 40
        and all(character in "0123456789abcdef" for character in expected_head)
        and all(character in "0123456789abcdef" for character in expected_tree)
        and not canonical_output.is_relative_to(canonical_repository)
        and len(exporter_module_paths) == 3
    )
    if arguments_are_valid:
        pass
    else:
        raise ValueError("Invalid explicit provenance arguments")

    head_process: subprocess.CompletedProcess[str] = subprocess.run(
        [str(canonical_git), "rev-parse", "HEAD"],
        cwd=canonical_repository,
        env=dict(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        timeout=30.0,
        check=False,
    )
    tree_process: subprocess.CompletedProcess[str] = subprocess.run(
        [str(canonical_git), "rev-parse", "HEAD^{tree}"],
        cwd=canonical_repository,
        env=dict(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        timeout=30.0,
        check=False,
    )
    status_process: subprocess.CompletedProcess[str] = subprocess.run(
        [str(canonical_git), "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=canonical_repository,
        env=dict(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        timeout=30.0,
        check=False,
    )
    git_observation_is_valid: bool = bool(
        head_process.returncode == 0
        and tree_process.returncode == 0
        and status_process.returncode == 0
        and head_process.stderr == ""
        and tree_process.stderr == ""
        and status_process.stderr == ""
        and head_process.stdout.strip() == expected_head
        and tree_process.stdout.strip() == expected_tree
    )
    if git_observation_is_valid:
        pass
    else:
        raise ValueError("Observed Git HEAD or tree does not match")

    allowed_parent_path: str = "examples/fmi/README.md"
    allowed_subtree: str = "examples/fmi/simulink_first_order/"
    dirty_paths: list[str] = list()
    status_lines: list[str] = status_process.stdout.splitlines()
    for status_line in status_lines:
        status_is_parseable: bool = bool(
            len(status_line) >= 4
            and " -> " not in status_line
            and not status_line[3:].startswith('"')
        )
        if status_is_parseable:
            pass
        else:
            raise ValueError("Git status contains an unsupported path encoding")
        index_status: str = status_line[0]
        portable_path: str = status_line[3:].replace("\\", "/")
        path_is_allowed: bool = bool(
            portable_path == allowed_parent_path
            or portable_path.startswith(allowed_subtree)
        )
        if index_status in (" ", "?") and path_is_allowed:
            dirty_paths.append(portable_path)
        else:
            raise ValueError("Checkout contains staged or out-of-scope changes")
    dirty_paths.sort()

    imported_paths: list[str] = [""] * len(exporter_module_paths)
    for module_index in range(len(exporter_module_paths)):
        module_path: Path = exporter_module_paths[module_index].resolve(strict=True)
        if module_path.is_file() and module_path.is_relative_to(expected_source_root):
            imported_paths[module_index] = module_path.as_posix()
        else:
            raise ValueError("VeraGrid exporter import is outside repository src")

    cache_records: list[tuple[str, dict[str, object]]] = list()
    cache_directories: list[Path] = list(canonical_repository.rglob("__pycache__"))
    cache_files: list[Path] = list(canonical_repository.rglob("*.pyc"))
    for cache_directory in cache_directories:
        relative_directory: str = cache_directory.relative_to(
            canonical_repository
        ).as_posix()
        cache_records.append(
            (relative_directory, {"kind": "directory", "path": relative_directory})
        )
    for cache_file in cache_files:
        cache_content: bytes = cache_file.read_bytes()
        relative_file: str = cache_file.relative_to(canonical_repository).as_posix()
        cache_records.append(
            (
                relative_file,
                {
                    "kind": "file",
                    "path": relative_file,
                    "size_bytes": len(cache_content),
                    "sha256": hashlib.sha256(cache_content).hexdigest(),
                },
            )
        )
    cache_records.sort()
    cache_entries: list[dict[str, object]] = [dict()] * len(cache_records)
    for cache_index in range(len(cache_records)):
        cache_entries[cache_index] = cache_records[cache_index][1]
    return {
        "head": head_process.stdout.strip(),
        "tree": tree_process.stdout.strip(),
        "dirty_paths": dirty_paths,
        "imported_module_paths": imported_paths,
        "output_dir": canonical_output.as_posix(),
        "python_dont_write_bytecode": sys.dont_write_bytecode,
        "cache_entries": cache_entries,
    }


def build_first_order_block() -> Block:
    """Build the approved normalized first-order verification model.

    The state equation is ``dx/dt = 10 * (u - x)``, which is exactly the
    approved ``tau * dx/dt = u - x`` model for ``tau = 0.1 s``. The state is
    also the sole FMU output so every importer observes the true dynamic state.

    :return: Independent symbolic block with input ``u`` and output/state ``x``.
    """

    # Allocate a fresh variable graph for every export so no exporter mutation
    # or identity assignment can leak from one FMI version into another.
    x: Var = Var("x")
    dx: Var = Var("dx", base_var=x)
    u: Var = Var("u")

    # Express the normalized continuous equation directly in the established
    # Block DSL; no device-specific physical interpretation is introduced.
    return Block(
        state_vars=list((x,)),
        state_eqs=list((Const(10.0) * (u - x),)),
        algebraic_vars=list(),
        algebraic_eqs=list(),
        diff_vars=list((dx,)),
        init_values=dict(((x, Const(0.0)),)),
        init_eqs=dict(),
        in_vars=list((u,)),
        out_vars=list((x,)),
    )


def main() -> None:
    """Generate and preflight the authenticated six-cell external FMU matrix.

    :return: None. A failing provenance or numerical check exits non-zero.
    """

    argument_parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Generate the maintained Simulink first-order FMI matrix."
    )
    argument_parser.add_argument("--repository-root", type=Path, required=True)
    argument_parser.add_argument("--git-executable", type=Path, required=True)
    argument_parser.add_argument("--expected-head", required=True)
    argument_parser.add_argument("--expected-tree", required=True)
    argument_parser.add_argument("--output-dir", type=Path, required=True)
    argument_parser.add_argument("--build-script-size-bytes", type=int, required=True)
    argument_parser.add_argument("--build-script-sha256", required=True)
    argument_parser.add_argument("--run-script-size-bytes", type=int, required=True)
    argument_parser.add_argument("--run-script-sha256", required=True)
    argument_parser.add_argument("--style-size-bytes", type=int, required=True)
    argument_parser.add_argument("--style-sha256", required=True)
    arguments: argparse.Namespace = argument_parser.parse_args()

    module_files_are_available: bool = bool(
        VeraGridEngine.__file__ is not None
        and interface_api.__file__ is not None
        and interface_api.__file__ is not None
    )
    if module_files_are_available:
        exporter_module_paths: tuple[Path, ...] = (
            Path(VeraGridEngine.__file__),
            Path(interface_api.__file__),
            Path(interface_api.__file__),
        )
    else:
        raise ValueError("Imported VeraGrid modules have no filesystem identity")

    repository_root: Path = arguments.repository_root
    execution_dir: Path = arguments.output_dir
    if execution_dir.resolve(strict=False).exists():
        raise ValueError("External output directory must not already exist")
    else:
        pass
    pre_provenance: dict[str, object] = verify_source_provenance(
        repository_root=repository_root,
        git_executable=arguments.git_executable,
        expected_head=arguments.expected_head,
        expected_tree=arguments.expected_tree,
        output_dir=execution_dir,
        exporter_module_paths=exporter_module_paths,
    )
    source_dir: Path = Path(__file__).resolve().parent
    build_script_bytes: bytes = verify_regular_file_identity(
        source_dir / "build_first_order_matrix.m",
        arguments.build_script_size_bytes,
        arguments.build_script_sha256,
    )
    run_script_bytes: bytes = verify_regular_file_identity(
        source_dir / "run_first_order_matrix.m",
        arguments.run_script_size_bytes,
        arguments.run_script_sha256,
    )
    style_bytes: bytes = verify_regular_file_identity(
        source_dir / "sober-scientific.mplstyle",
        arguments.style_size_bytes,
        arguments.style_sha256,
    )

    # Keep every generated source, binary, trace, and receipt outside the Git
    # checkout, as required by the sealed evidence-only contract.
    fmu_dir: Path = execution_dir / "fmus"
    build_root: Path = execution_dir / "build"
    staging_root: Path = execution_dir / "staging"
    trace_dir: Path = execution_dir / "local_traces"
    manifest_path: Path = execution_dir / "first-order-fmu-manifest.json"
    receipt_path: Path = execution_dir / "local-preflight-receipt.json"
    if manifest_path.exists() or receipt_path.exists():
        raise RuntimeError("Refusing to overwrite first-order campaign receipts")
    else:
        pass
    fmu_dir.mkdir(parents=True, exist_ok=False)
    build_root.mkdir(parents=True, exist_ok=False)
    staging_root.mkdir(parents=True, exist_ok=False)
    trace_dir.mkdir(parents=True, exist_ok=False)
    (execution_dir / "build_first_order_matrix.m").write_bytes(build_script_bytes)
    (execution_dir / "run_first_order_matrix.m").write_bytes(run_script_bytes)
    (execution_dir / "sober-scientific.mplstyle").write_bytes(style_bytes)

    started_at_utc: str = datetime.now(timezone.utc).isoformat()
    versions: tuple[FmiVersion, ...] = (
        FmiVersion.FMI_1_0,
        FmiVersion.FMI_2_0,
        FmiVersion.FMI_3_0,
    )
    interfaces: tuple[str, ...] = ("cs", "me")
    cells: list[dict[str, object]] = list()
    model_identifiers: set[str] = set()

    # Duplicated boundaries make the local FMPy smoke input explicitly
    # right-continuous; the commercial harness later uses Step plus ZOH blocks.
    input_dtype: np.dtype = np.dtype([("time", np.float64), ("u", np.float64)])
    input_table: np.ndarray = np.array(
        [
            (0.0, 0.0),
            (0.2, 0.0),
            (0.2, 1.0),
            (0.5, 1.0),
            (0.5, -0.5),
            (0.8, -0.5),
            (0.8, 0.25),
            (1.2, 0.25),
        ],
        dtype=input_dtype,
    )
    target_time: np.ndarray = np.linspace(0.0, 1.2, 1201, dtype=np.float64)
    analytic_x: np.ndarray = np.empty(1201, dtype=np.float64)
    analytic_x[0] = 0.0
    analytic_state: float = 0.0
    segment_start: float = 0.0
    segment_input: float = 0.0
    target_index: int
    for target_index in range(1201):
        time_value: float = float(target_time[target_index])
        if time_value >= 0.8:
            segment_start = 0.8
            segment_input = 0.25
            state_at_02: float = 0.0
            state_at_05: float = 1.0 + (state_at_02 - 1.0) * np.exp(-3.0)
            state_at_08: float = -0.5 + (state_at_05 + 0.5) * np.exp(-3.0)
            analytic_state = state_at_08
        elif time_value >= 0.5:
            segment_start = 0.5
            segment_input = -0.5
            state_at_02 = 0.0
            state_at_05 = 1.0 + (state_at_02 - 1.0) * np.exp(-3.0)
            analytic_state = state_at_05
        elif time_value >= 0.2:
            segment_start = 0.2
            segment_input = 1.0
            analytic_state = 0.0
        else:
            segment_start = 0.0
            segment_input = 0.0
            analytic_state = 0.0
        analytic_x[target_index] = segment_input + (
            analytic_state - segment_input
        ) * np.exp(-(time_value - segment_start) / 0.1)

    be_x: np.ndarray = np.empty(1201, dtype=np.float64)
    be_x[0] = 0.0
    be_index: int
    for be_index in range(1200):
        be_time: float = float(target_time[be_index])
        if be_time >= 0.8:
            be_input: float = 0.25
        elif be_time >= 0.5:
            be_input = -0.5
        elif be_time >= 0.2:
            be_input = 1.0
        else:
            be_input = 0.0
        be_x[be_index + 1] = (be_x[be_index] + 0.01 * be_input) / 1.01

    compiler: Compiler = Compiler()
    try:
        version: FmiVersion
        interface: str
        for version in versions:
            for interface in interfaces:
                cell_id: str = f"fmi{version.value.replace('.', '')}_{interface}"
                model_name: str = (
                    f"VGFirstOrder{arguments.expected_head[:12]}_{cell_id.upper()}"
                )
                fmu_path: Path = fmu_dir / f"{model_name}.fmu"
                cell: dict[str, object] = {
                    "cell_id": cell_id,
                    "fmi_version_requested": version.value,
                    "interface_requested": interface,
                    "model_name_requested": model_name,
                    "status": "FAIL",
                }
                try:
                    if interface == "cs":
                        generated_path: Path = export_model_as_fmu(
                            build_first_order_block(),
                            CsExportConfig(
                                model_name=model_name,
                                output_path=fmu_path,
                                target_platform=detect_cs_target_platform(),
                                compile_binary=True,
                                keep_build_dir=True,
                                fixed_step=0.001,
                                build_dir=build_root / cell_id,
                                staging_dir=staging_root / cell_id,
                                fmi_version=version,
                            ),
                            compiler,
                        )
                        fmi_type: str = "CoSimulation"
                    elif interface == "me":
                        generated_path = export_model_as_fmu(
                            build_first_order_block(),
                            MeExportConfig(interface_type=InterfaceType.MODEL_EXCHANGE, 
                                model_name=model_name,
                                output_path=fmu_path,
                                target_platform=detect_me_target_platform(),
                                compile_binary=True,
                                keep_build_dir=True,
                                fixed_step=0.001,
                                build_dir=build_root / cell_id,
                                staging_dir=staging_root / cell_id,
                                fmi_version=version,
                            ),
                            compiler,
                        )
                        fmi_type = "ModelExchange"
                    else:
                        raise RuntimeError(f"Unsupported interface {interface}")

                    model_description: object = read_model_description(
                        str(generated_path), validate=True
                    )
                    if interface == "cs":
                        declared_interface: object = model_description.coSimulation
                    else:
                        declared_interface = model_description.modelExchange
                    if declared_interface is None:
                        raise RuntimeError("Expected FMI interface is absent")
                    else:
                        pass
                    model_identifier: str = str(declared_interface.modelIdentifier)
                    if model_identifier in model_identifiers:
                        raise RuntimeError(f"Duplicate model identifier {model_identifier}")
                    else:
                        model_identifiers.add(model_identifier)

                    input_names: list[str] = list()
                    output_names: list[str] = list()
                    variable: object
                    for variable in model_description.modelVariables:
                        if str(variable.causality) == "input":
                            input_names.append(str(variable.name))
                        elif str(variable.causality) == "output":
                            output_names.append(str(variable.name))
                        else:
                            pass
                    if input_names != ["u"] or output_names != ["x"]:
                        raise RuntimeError(
                            f"Unexpected variables inputs={input_names} outputs={output_names}"
                        )
                    else:
                        pass

                    with zipfile.ZipFile(generated_path, "r") as archive:
                        archive_members: list[str] = archive.namelist()
                    binary_members: list[str] = list()
                    archive_member: str
                    for archive_member in archive_members:
                        if archive_member.lower().startswith("binaries/") and archive_member.lower().endswith(".dll"):
                            binary_members.append(archive_member)
                        else:
                            pass
                    if len(binary_members) == 0:
                        raise RuntimeError("FMU archive contains no Windows DLL")
                    else:
                        pass

                    raw_result: np.ndarray = simulate_fmu(
                        filename=str(generated_path),
                        validate=True,
                        start_time=0.0,
                        stop_time=1.2,
                        solver="Euler",
                        step_size=0.001,
                        output_interval=0.001,
                        record_events=True,
                        fmi_type=fmi_type,
                        input=input_table,
                        output=["x"],
                    )
                    normalized_x: np.ndarray = np.empty(1201, dtype=np.float64)
                    missing_boundaries: list[float] = list()
                    boundary_index: int
                    for boundary_index in range(1201):
                        boundary: float = float(target_time[boundary_index])
                        matches: np.ndarray = np.flatnonzero(
                            np.isclose(raw_result["time"], boundary, rtol=0.0, atol=5.0e-13)
                        )
                        if matches.size == 0:
                            missing_boundaries.append(boundary)
                            normalized_x[boundary_index] = np.nan
                        else:
                            normalized_x[boundary_index] = float(raw_result["x"][int(matches[-1])])
                    finite: bool = bool(np.all(np.isfinite(normalized_x)))
                    if interface == "cs":
                        primary_error: float = float(np.max(np.abs(normalized_x - be_x)))
                        primary_tolerance: float = 2.0e-10
                    else:
                        primary_error = float(np.max(np.abs(normalized_x - analytic_x)))
                        primary_tolerance = 4.0e-3
                    local_pass: bool = bool(
                        len(missing_boundaries) == 0
                        and finite
                        and primary_error <= primary_tolerance
                    )

                    trace_path: Path = trace_dir / f"{cell_id}.csv"
                    np.savetxt(
                        trace_path,
                        np.column_stack((target_time, normalized_x, analytic_x, be_x)),
                        delimiter=",",
                        header="time,x,analytic_x,backward_euler_x",
                        comments="",
                        fmt="%.17g",
                    )
                    fmu_digest: hashlib._Hash = hashlib.sha256()
                    with generated_path.open("rb") as fmu_stream:
                        while True:
                            fmu_chunk: bytes = fmu_stream.read(1024 * 1024)
                            if fmu_chunk == b"":
                                break
                            else:
                                fmu_digest.update(fmu_chunk)
                    trace_digest: hashlib._Hash = hashlib.sha256()
                    with trace_path.open("rb") as trace_stream:
                        while True:
                            trace_chunk: bytes = trace_stream.read(1024 * 1024)
                            if trace_chunk == b"":
                                break
                            else:
                                trace_digest.update(trace_chunk)
                    cell.update(
                        {
                            "fmi_version": str(model_description.fmiVersion),
                            "interface": interface,
                            "model_identifier": model_identifier,
                            "input_names": input_names,
                            "output_names": output_names,
                            "binary_members": sorted(binary_members),
                            "fmu_path": str(generated_path),
                            "fmu_name": generated_path.name,
                            "fmu_sha256": fmu_digest.hexdigest(),
                            "fmu_size_bytes": int(generated_path.stat().st_size),
                            "local_trace_path": str(trace_path),
                            "local_trace_sha256": trace_digest.hexdigest(),
                            "raw_record_count": int(raw_result.shape[0]),
                            "normalized_record_count": 1201,
                            "missing_boundaries": missing_boundaries,
                            "finite": finite,
                            "local_primary_reference": "backward_euler" if interface == "cs" else "analytic_continuous",
                            "local_primary_max_abs_error": primary_error,
                            "local_primary_tolerance": primary_tolerance,
                            "local_solver": "FMU internal backward Euler" if interface == "cs" else "FMPy Euler smoke only",
                            "status": "PASS" if local_pass else "FAIL",
                        }
                    )
                except Exception as exception:
                    cell["error_type"] = type(exception).__name__
                    cell["error_message"] = str(exception)
                    cell["traceback"] = traceback.format_exc()
                cells.append(cell)
                print(f"{cell_id}: {cell['status']}", flush=True)

    except BaseException as primary_error:
        raise
    
    pass_count: int = 0
    recorded_cell: dict[str, object]
    for recorded_cell in cells:
        if recorded_cell["status"] == "PASS":
            pass_count += 1
        else:
            pass
    post_provenance: dict[str, object] = verify_source_provenance(
        repository_root=repository_root,
        git_executable=arguments.git_executable,
        expected_head=arguments.expected_head,
        expected_tree=arguments.expected_tree,
        output_dir=execution_dir,
        exporter_module_paths=exporter_module_paths,
    )
    if post_provenance == pre_provenance:
        pass
    else:
        raise RuntimeError("Repository or Python cache identity changed during export")
    manifest: dict[str, object] = {
        "schema_version": "1.0",
        "campaign": "veragrid-maintained-simulink-first-order-fmi-matrix",
        "claim": "normalized first-order verification fixture; not a device-specific physical model",
        "source_commit": pre_provenance["head"],
        "git_tree_sha1": pre_provenance["tree"],
        "source_provenance": pre_provenance,
        "post_source_provenance": post_provenance,
        "recipe_assets": {
            "builder": {
                "file_name": "build_first_order_matrix.m",
                "size_bytes": len(build_script_bytes),
                "sha256": hashlib.sha256(build_script_bytes).hexdigest(),
            },
            "runner": {
                "file_name": "run_first_order_matrix.m",
                "size_bytes": len(run_script_bytes),
                "sha256": hashlib.sha256(run_script_bytes).hexdigest(),
            },
            "style": {
                "file_name": "sober-scientific.mplstyle",
                "size_bytes": len(style_bytes),
                "sha256": hashlib.sha256(style_bytes).hexdigest(),
            },
        },
        "equation": "tau*dx/dt=u-x",
        "tau_s": 0.1,
        "initial_x": 0.0,
        "step_s": 0.001,
        "stop_s": 1.2,
        "input_schedule": [[0.0, 0.0], [0.2, 1.0], [0.5, -0.5], [0.8, 0.25]],
        "host": platform.node(),
        "platform": platform.platform(),
        "python": sys.version,
        "fmpy": fmpy.__version__,
        "numpy": np.__version__,
        "started_at_utc": started_at_utc,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "cell_count": len(cells),
        "pass_count": pass_count,
        "fail_count": len(cells) - pass_count,
        "status": "PASS" if len(cells) == 6 and pass_count == 6 else "FAIL",
        "cells": cells,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    manifest_digest: hashlib._Hash = hashlib.sha256()
    with manifest_path.open("rb") as manifest_stream:
        while True:
            manifest_chunk: bytes = manifest_stream.read(1024 * 1024)
            if manifest_chunk == b"":
                break
            else:
                manifest_digest.update(manifest_chunk)
    receipt: dict[str, object] = {
        "schema_version": "1.0",
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_digest.hexdigest(),
        "cell_count": len(cells),
        "pass_count": pass_count,
        "fail_count": len(cells) - pass_count,
        "status": manifest["status"],
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    receipt_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt), flush=True)
    if manifest["status"] != "PASS":
        raise SystemExit(1)
    else:
        pass


if __name__ == "__main__":
    main()
else:
    pass
