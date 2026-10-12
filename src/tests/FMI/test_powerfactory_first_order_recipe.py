"""Focused pure tests for the PowerFactory first-order replay contract."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import sys
import zipfile

import numpy as np
import pytest

from examples.fmi.powerfactory_first_order.plot_powerfactory_first_order import main as plot_main
from examples.fmi.powerfactory_first_order.run_powerfactory_first_order import (
    PowerFactoryCompatibilityProfile,
    build_powerfactory_compatibility_fmu,
    cleanup_probe_project,
    extract_checked_fmu,
    hash_source_closure,
)
from examples.fmi.powerfactory_first_order.supervise_powerfactory_first_order import (
    finalize_worker_evidence,
    main as supervisor_main,
)
from examples.fmi.powerfactory_first_order.validate_powerfactory_first_order import (
    FmpyCsPostEventRecorder,
    canonicalize_trace_rows,
    max_abs_delta,
    validate_me_refinement,
    validate_validated_run_record,
)
from examples.fmi.simulink_first_order.validate_first_order_matrix import (
    backward_euler_oracle,
    continuous_oracle,
)


def test_event_grid_and_oracles() -> None:
    """Prove the retained grid, event convention, and independent oracles."""

    time_values: np.ndarray = np.arange(1201, dtype=np.float64) / 1000.0
    input_values: np.ndarray = np.where(time_values >= 0.8, 0.25, np.where(time_values >= 0.5, -0.5, np.where(time_values >= 0.2, 1.0, 0.0)))
    analytic_x: np.ndarray = continuous_oracle(time_values)
    backward_x: np.ndarray = backward_euler_oracle(time_values, input_values)
    assert time_values.shape == (1201,)
    assert tuple(input_values[[199, 200, 499, 500, 799, 800]]) == (0.0, 1.0, 1.0, -0.5, -0.5, 0.25)
    assert analytic_x[200] == pytest.approx(0.0)
    assert backward_x[201] == pytest.approx(1.0 / 101.0)


def test_profile_patch_is_exact() -> None:
    """Pin the opt-in profile and exactly two guarded FMI 3 functions."""

    source_text: str = inspect.getsource(build_powerfactory_compatibility_fmu)
    assert PowerFactoryCompatibilityProfile.FMI_THREE_CONFIGURATION_MODE.value == "fmi_three_configuration_mode"
    assert source_text.count("fmi3EnterConfigurationMode") == 2
    assert source_text.count("fmi3ExitConfigurationMode") == 2
    assert '"changed_function_count": 2' in source_text
    assert "VG_STATE_INSTANTIATED" in source_text


def test_rejects_unsafe_archive(tmp_path: Path) -> None:
    """Reject parent traversal before any archive member is written.

    :param tmp_path: Pytest-owned temporary directory.
    """

    archive_path: Path = tmp_path / "unsafe.fmu"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../escape.txt", "unsafe")
    with pytest.raises(ValueError):
        extract_checked_fmu(archive_path, tmp_path / "out")


def test_source_closure_manifest_exact(tmp_path: Path) -> None:
    """Prove UUID normalization stability and extra-material rejection.

    :param tmp_path: Pytest-owned temporary directory.
    """

    roots: list[Path] = list()
    interface_index: int
    for interface_index in range(2):
        source_root: Path = tmp_path / ("root" + str(interface_index))
        (source_root / "src").mkdir(parents=True)
        (source_root / "include").mkdir()
        file_index: int
        for file_index in range(14):
            parent: Path = source_root / ("include" if file_index < 4 else "src")
            (parent / ("material_" + str(file_index) + ".h")).write_text("same\n", encoding="utf-8")
        uuid_text: str = "11111111-1111-4111-8111-111111111111" if interface_index == 0 else "22222222-2222-4222-8222-222222222222"
        (source_root / "src" / "generated_metadata.h").write_text('#define VG_MODEL_GUID "' + uuid_text + '"\n', encoding="utf-8")
        roots.append(source_root)
    first: dict[str, object] = hash_source_closure((("fmi30_cs", roots[0]), ("fmi30_me", roots[1])))
    (roots[0] / "src" / "generated_metadata.h").write_text('#define VG_MODEL_GUID "33333333-3333-4333-8333-333333333333"\n', encoding="utf-8")
    second: dict[str, object] = hash_source_closure((("fmi30_cs", roots[0]), ("fmi30_me", roots[1])))
    assert first["normalized_closure_sha256"] == second["normalized_closure_sha256"]
    (roots[0] / "src" / "extra.h").write_text("extra\n", encoding="utf-8")
    with pytest.raises(ValueError):
        hash_source_closure((("fmi30_cs", roots[0]), ("fmi30_me", roots[1])))


def test_event_canonicalization_patterns() -> None:
    """Accept only single or old/new/new PowerFactory event groups."""

    time_values: np.ndarray = np.arange(1201, dtype=np.float64) / 1000.0
    input_values: np.ndarray = np.where(time_values >= 0.8, 0.25, np.where(time_values >= 0.5, -0.5, np.where(time_values >= 0.2, 1.0, 0.0)))
    state_values: np.ndarray = continuous_oracle(time_values)
    rows: np.ndarray = np.column_stack((time_values, input_values, state_values))
    for event_index, old_input in ((800, -0.5), (500, 1.0), (200, 0.0)):
        event_row: np.ndarray = rows[event_index : event_index + 1, :]
        duplicate_rows: np.ndarray = np.vstack((event_row, event_row, event_row))
        duplicate_rows[0, 1] = old_input
        rows = np.vstack((rows[:event_index, :], duplicate_rows, rows[event_index + 1 :, :]))
    canonical: np.ndarray = canonicalize_trace_rows(rows)
    assert canonical.shape == (1201, 3)
    broken: np.ndarray = np.insert(canonical, 100, canonical[100, :], axis=0)
    with pytest.raises(ValueError):
        canonicalize_trace_rows(broken)


def test_fmpy_cs_post_event_recording() -> None:
    """Pin actual post-event recording and reject fabricated event patterns."""

    source_text: str = inspect.getsource(FmpyCsPostEventRecorder)
    assert "recorder.sample(time, force=True)" in source_text
    assert "setReal(" in source_text
    assert "setFloat64(" in source_text
    assert "doStep" not in source_text
    time_values: np.ndarray = np.arange(1201, dtype=np.float64) / 1000.0
    input_values: np.ndarray = np.where(time_values >= 0.8, 0.25, np.where(time_values >= 0.5, -0.5, np.where(time_values >= 0.2, 1.0, 0.0)))
    state_values: np.ndarray = continuous_oracle(time_values)
    rows: np.ndarray = np.column_stack((time_values, input_values, state_values))
    event_index: int
    old_input: float
    for event_index, old_input in ((800, -0.5), (500, 1.0), (200, 0.0)):
        post_row: np.ndarray = rows[event_index : event_index + 1, :]
        pre_row: np.ndarray = post_row.copy()
        pre_row[0, 1] = old_input
        rows = np.vstack((rows[:event_index, :], pre_row, post_row, rows[event_index + 1 :, :]))
    assert canonicalize_trace_rows(rows, powerfactory_rows=False).shape == (1201, 3)
    discontinuous: np.ndarray = rows.copy()
    discontinuous[201, 2] += 6e-12
    with pytest.raises(ValueError):
        canonicalize_trace_rows(discontinuous, powerfactory_rows=False)


def test_cross_tool_tolerance_boundaries() -> None:
    """Pin max-norm behavior at and beyond an absolute tolerance."""

    reference: np.ndarray = np.zeros(1201, dtype=np.float64)
    at_boundary: np.ndarray = reference.copy()
    at_boundary[600] = 2e-10
    beyond_boundary: np.ndarray = reference.copy()
    beyond_boundary[600] = np.nextafter(2e-10, np.inf)
    assert max_abs_delta(at_boundary, reference) <= 2e-10
    assert max_abs_delta(beyond_boundary, reference) > 2e-10


def test_me_refinement_order_edges() -> None:
    """Accept second-order refinement and reject non-monotone errors."""

    oracle: np.ndarray = np.zeros(1201, dtype=np.float64)
    passing: dict[str, object] = validate_me_refinement((np.full(1201, 4e-6), np.full(1201, 1e-6), np.full(1201, 2.5e-7)), oracle, "fmi20_me")
    failing: dict[str, object] = validate_me_refinement((np.full(1201, 1e-6), np.full(1201, 2e-6), np.full(1201, 1e-6)), oracle, "fmi20_me")
    assert passing["status"] == "PASS"
    assert failing["status"] == "FAIL"


def test_validated_run_schema_rejects_paths() -> None:
    """Reject machine and user paths recursively from tracked lineage."""

    record: dict[str, object] = {"schema_version": "1.0", "record_kind": "powerfactory_first_order_commercial_replay", "campaign": "veragrid-powerfactory-first-order-fmi2-fmi3-revision-1", "source_commit": "a" * 40, "git_tree_sha1": "b" * 40, "fixture": {"leak": "C:/Temp/run"}, "commercial_runtime": {}, "compatibility": {}, "numerical_results": {}, "evidence_sha256": {}, "repository_unchanged": True, "git_action": "NONE", "status": "PASS"}
    assert not validate_validated_run_record(record)


def test_cleanup_identity_contract() -> None:
    """Pin direct live-child absence and prohibit recycle-bin traversal."""

    source_text: str = inspect.getsource(cleanup_probe_project)
    assert '"*.IntPrj", 0' in source_text
    assert "ClearRecycleBin" not in source_text
    assert "project_name not in remaining_names" in source_text


def test_figure_manifest_binding() -> None:
    """Pin all six names and the source/receipt hash gates."""

    source_text: str = inspect.getsource(plot_main)
    stems: tuple[str, ...] = ("full-trajectory", "event-windows", "pointwise-errors")
    stem: str
    for stem in stems:
        assert source_text.count("powerfactory-first-order-" + stem) >= 2
    assert "comparison_sha256" in source_text
    assert "numerical_receipt_sha256" in source_text
    assert 'source["fmpy_" + first_id][window]' in source_text
    assert "axis.set_ylim(-1.1 * tolerance, 1.1 * tolerance)" in source_text


def test_validated_run_schema_rejects_shape_and_status() -> None:
    """Reject missing keys and every non-PASS publication status."""

    assert not validate_validated_run_record({})
    record: dict[str, object] = {"schema_version": "1.0", "record_kind": "powerfactory_first_order_commercial_replay", "campaign": "veragrid-powerfactory-first-order-fmi2-fmi3-revision-1", "source_commit": "a" * 40, "git_tree_sha1": "b" * 40, "fixture": {}, "commercial_runtime": {}, "compatibility": {}, "numerical_results": {}, "evidence_sha256": {}, "repository_unchanged": True, "git_action": "NONE", "status": "FAIL"}
    assert not validate_validated_run_record(record)


def test_supervisor_finalization_contract(tmp_path: Path) -> None:
    """Pin parent nonce ownership, native-exit fallback, and exact ME steps.

    :param tmp_path: Pytest-owned directory with no fabricated checkpoint.
    """

    supervisor_source: str = inspect.getsource(supervisor_main)
    finalizer_source: str = inspect.getsource(finalize_worker_evidence)
    assert 'secrets.token_hex(32)' in supervisor_source
    assert 'multiprocessing.get_context("spawn")' in supervisor_source
    assert ".terminate(" not in supervisor_source
    assert ".kill(" not in supervisor_source
    assert 'len(artifacts_value) == 14' in finalizer_source
    assert 'worker_exit_code != 0' in finalizer_source
    assert 'write_execution_receipt(' in finalizer_source
    # The remaining finalizer exercise inventories Windows processes through
    # PowerShell; the static ownership assertions above apply to every host.
    if sys.platform != "win32":
        pytest.skip("Native finalizer process inventory requires Windows PowerShell")
    else:
        pass
    run_nonce: str = "a" * 64
    worker_pid: int = 2147483000
    base_dir: Path = tmp_path / "base"
    base_dir.mkdir()
    artifact_names: tuple[str, ...] = (
        "process-before.json",
        "process-after-acquire.json",
        "cleanup-receipt.json",
        "mutation-journal.jsonl",
        "compatibility-build-receipt.json",
        "source-closure-manifest.txt",
        "raw_traces/fmi20_cs_h_0p001000000.csv",
        "raw_traces/fmi20_me_h_0p000125000.csv",
        "raw_traces/fmi20_me_h_0p000062500.csv",
        "raw_traces/fmi20_me_h_0p000031250.csv",
        "raw_traces/fmi30_cs_h_0p001000000.csv",
        "raw_traces/fmi30_me_h_0p000125000.csv",
        "raw_traces/fmi30_me_h_0p000062500.csv",
        "raw_traces/fmi30_me_h_0p000031250.csv",
    )
    expected_cells: tuple[tuple[str, float], ...] = (
        ("fmi20_cs", 0.001),
        ("fmi20_me", 0.000125),
        ("fmi20_me", 0.0000625),
        ("fmi20_me", 0.00003125),
        ("fmi30_cs", 0.001),
        ("fmi30_me", 0.000125),
        ("fmi30_me", 0.0000625),
        ("fmi30_me", 0.00003125),
    )
    cells: list[dict[str, object]] = [dict()] * len(expected_cells)
    cell_index: int
    for cell_index in range(len(expected_cells)):
        cells[cell_index] = {
            "cell_id": expected_cells[cell_index][0],
            "integration_step_s": expected_cells[cell_index][1],
            "output_step_s": 0.001,
            "event_count": 3,
            "status": "PASS",
        }
    cleanup: dict[str, object] = {
        "status": "PASS",
        "delete_code": 0,
        "project_absent_after": True,
    }
    observations: dict[str, object] = {
        "schema_version": "1.0",
        "claim": "synthetic focused test",
        "run_nonce": run_nonce,
        "project_name": "pytest-owned",
        "selected_cells": list(("fmi20_cs", "fmi20_me", "fmi30_cs", "fmi30_me")),
        "fmi1_imported": False,
        "fixture": dict(),
        "xml": dict(),
        "scaffold": dict(),
        "cells": cells,
        "cleanup": cleanup,
        "error": None,
        "comsim_executed": True,
        "event_executed": True,
    }
    cleanup_receipt: dict[str, object] = {
        "schema_version": "1.0",
        "cleanup": cleanup,
        "status": "PASS",
    }
    artifact_name: str
    for artifact_name in artifact_names:
        artifact_path: Path = base_dir / artifact_name
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        if artifact_name == "cleanup-receipt.json":
            artifact_path.write_text(
                json.dumps(cleanup_receipt, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        else:
            artifact_path.write_text(artifact_name + "\n", encoding="utf-8")
    artifact_records: list[dict[str, object]] = [dict()] * len(artifact_names)
    artifact_index: int
    for artifact_index in range(len(artifact_names)):
        artifact_path = base_dir / artifact_names[artifact_index]
        artifact_bytes: bytes = artifact_path.read_bytes()
        artifact_records[artifact_index] = {
            "name": artifact_names[artifact_index],
            "size_bytes": len(artifact_bytes),
            "sha256": hashlib.sha256(artifact_bytes).hexdigest(),
        }
    checkpoint: dict[str, object] = {
        "schema_version": "1.0",
        "record_kind": "powerfactory_pre_release_checkpoint",
        "run_nonce": run_nonce,
        "worker_pid": worker_pid,
        "observations": observations,
        "artifacts": artifact_records,
        "status": "READY_FOR_NATIVE_RELEASE",
    }
    (base_dir / "release-checkpoint.json").write_text(
        json.dumps(checkpoint, sort_keys=True) + "\n", encoding="utf-8"
    )
    case_names: tuple[str, ...] = (
        "exit", "order", "hash", "process",
    )
    case_name: str
    for case_name in case_names:
        shutil.copytree(base_dir, tmp_path / case_name)

    fallback_receipt: dict[str, object] = finalize_worker_evidence(
        base_dir, run_nonce, worker_pid, 1
    )
    assert fallback_receipt["status"] == "EXECUTION_EVIDENCE_COMPLETE"
    ordinary_receipt: dict[str, object] = finalize_worker_evidence(
        base_dir, run_nonce, worker_pid, 0
    )
    assert ordinary_receipt == fallback_receipt
    with pytest.raises(ValueError):
        finalize_worker_evidence(base_dir, run_nonce, worker_pid, 1)
    with pytest.raises(ValueError):
        finalize_worker_evidence(base_dir, "b" * 64, worker_pid, 0)
    with pytest.raises(ValueError):
        finalize_worker_evidence(base_dir, run_nonce, True, 0)
    with pytest.raises(ValueError):
        finalize_worker_evidence(tmp_path / "exit", run_nonce, worker_pid, 0)

    order_path: Path = tmp_path / "order" / "release-checkpoint.json"
    order_checkpoint: dict[str, object] = json.loads(order_path.read_text(encoding="utf-8"))
    order_artifacts: list[object] = order_checkpoint["artifacts"]
    order_artifacts[0], order_artifacts[1] = order_artifacts[1], order_artifacts[0]
    order_path.write_text(json.dumps(order_checkpoint) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        finalize_worker_evidence(tmp_path / "order", run_nonce, worker_pid, 1)

    hash_path: Path = tmp_path / "hash" / "release-checkpoint.json"
    hash_checkpoint: dict[str, object] = json.loads(hash_path.read_text(encoding="utf-8"))
    hash_artifacts: list[dict[str, object]] = hash_checkpoint["artifacts"]
    hash_artifacts[0]["sha256"] = "0" * 64
    hash_path.write_text(json.dumps(hash_checkpoint) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        finalize_worker_evidence(tmp_path / "hash", run_nonce, worker_pid, 1)

    process_path: Path = tmp_path / "process" / "release-checkpoint.json"
    process_checkpoint: dict[str, object] = json.loads(
        process_path.read_text(encoding="utf-8")
    )
    process_checkpoint["worker_pid"] = os.getpid()
    process_path.write_text(json.dumps(process_checkpoint) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        finalize_worker_evidence(tmp_path / "process", run_nonce, os.getpid(), 1)
