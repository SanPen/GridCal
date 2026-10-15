"""Supervise the PowerFactory worker across native interpreter release.

The parent owns the run nonce and remains alive when releasing the native
PowerFactory application terminates the isolated Python worker.  It validates
the worker's pre-release checkpoint before completing the evidence receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
from multiprocessing.process import BaseProcess
from pathlib import Path
import re
import secrets
from typing import cast

from examples.fmi.powerfactory_first_order.run_powerfactory_first_order import (
    inspect_process_inventory,
    main as worker_main,
    parse_arguments,
    write_execution_receipt,
)


def finalize_worker_evidence(
    output_dir: Path,
    expected_nonce: str,
    worker_pid: int,
    worker_exit_code: int,
) -> dict[str, object]:
    """Validate the checkpoint and finalize evidence after worker exit.

    :param output_dir: Exact external directory created by the worker.
    :param expected_nonce: Parent-origin 64-hex run nonce retained in memory.
    :param worker_pid: Exact spawned worker process identifier.
    :param worker_exit_code: Native worker exit code observed after ``join``.
    :return: Reopened complete execution receipt.
    """

    if (
        re.fullmatch(r"[0-9a-f]{64}", expected_nonce) is not None
        and isinstance(worker_pid, int)
        and not isinstance(worker_pid, bool)
        and worker_pid > 0
        and isinstance(worker_exit_code, int)
        and not isinstance(worker_exit_code, bool)
    ):
        pass
    else:
        raise ValueError("Parent nonce, worker PID, or exit code has invalid type")
    checkpoint_path: Path = output_dir / "release-checkpoint.json"
    checkpoint_value: object = json.loads(
        checkpoint_path.resolve(strict=True).read_text(encoding="utf-8")
    )
    if isinstance(checkpoint_value, dict):
        checkpoint: dict[str, object] = cast(dict[str, object], checkpoint_value)
    else:
        raise ValueError("Release checkpoint must be one JSON object")
    expected_checkpoint_keys: set[str] = set(
        (
            "schema_version",
            "record_kind",
            "run_nonce",
            "worker_pid",
            "observations",
            "artifacts",
            "status",
        )
    )
    checkpoint_identity_valid: bool = bool(
        set(checkpoint.keys()) == expected_checkpoint_keys
        and checkpoint.get("schema_version", None) == "1.0"
        and checkpoint.get("record_kind", None)
        == "powerfactory_pre_release_checkpoint"
        and checkpoint.get("run_nonce", None) == expected_nonce
        and isinstance(checkpoint.get("worker_pid", None), int)
        and not isinstance(checkpoint.get("worker_pid", None), bool)
        and checkpoint.get("worker_pid", None) == worker_pid
        and checkpoint.get("status", None) == "READY_FOR_NATIVE_RELEASE"
    )
    if checkpoint_identity_valid:
        pass
    else:
        raise ValueError("Release checkpoint identity or parent nonce mismatch")

    expected_artifact_names: tuple[str, ...] = (
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
    artifacts_value: object = checkpoint.get("artifacts", None)
    if isinstance(artifacts_value, list) and len(artifacts_value) == 14:
        artifact_records: list[object] = artifacts_value
    else:
        raise ValueError("Release checkpoint must authenticate exactly 14 artifacts")
    pre_release_paths: list[Path] = [output_dir] * len(expected_artifact_names)
    artifact_index: int
    for artifact_index in range(len(expected_artifact_names)):
        artifact_value: object = artifact_records[artifact_index]
        if isinstance(artifact_value, dict):
            artifact: dict[str, object] = cast(dict[str, object], artifact_value)
        else:
            raise ValueError("Checkpoint artifact entry must be one JSON object")
        expected_name: str = expected_artifact_names[artifact_index]
        artifact_path: Path = output_dir / Path(expected_name)
        artifact_bytes: bytes = artifact_path.resolve(strict=True).read_bytes()
        artifact_valid: bool = bool(
            set(artifact.keys()) == set(("name", "size_bytes", "sha256"))
            and artifact.get("name", None) == expected_name
            and isinstance(artifact.get("size_bytes", None), int)
            and not isinstance(artifact.get("size_bytes", None), bool)
            and artifact.get("size_bytes", None) == len(artifact_bytes)
            and artifact.get("sha256", None)
            == hashlib.sha256(artifact_bytes).hexdigest()
        )
        if artifact_valid:
            pre_release_paths[artifact_index] = artifact_path
        else:
            raise ValueError("Checkpoint artifact closure mismatch")

    observations_value: object = checkpoint.get("observations", None)
    if isinstance(observations_value, dict):
        observations: dict[str, object] = cast(
            dict[str, object], observations_value
        )
    else:
        raise ValueError("Checkpoint observations must be one JSON object")
    cells_value: object = observations.get("cells", None)
    cleanup_value: object = observations.get("cleanup", None)
    expected_observation_keys: set[str] = set(
        (
            "schema_version", "claim", "run_nonce",
            "project_name", "selected_cells", "fmi1_imported", "fixture",
            "xml", "scaffold", "cells", "cleanup", "error",
            "comsim_executed", "event_executed",
        )
    )
    observations_complete: bool = bool(
        set(observations.keys()) == expected_observation_keys
        and observations.get("schema_version", None) == "1.0"
        and observations.get("run_nonce", None) == expected_nonce
        and observations.get("error", None) is None
        and isinstance(cells_value, list)
        and len(cells_value) == 8
        and all(
            isinstance(item, dict) and item.get("status", None) == "PASS"
            for item in cast(list[object], cells_value)
        )
        and isinstance(cleanup_value, dict)
        and cast(dict[str, object], cleanup_value).get("status", None) == "PASS"
        and cast(dict[str, object], cleanup_value).get("delete_code", None) == 0
        and cast(dict[str, object], cleanup_value).get("project_absent_after", None) is True
        and observations.get("selected_cells", None)
        == list(("fmi20_cs", "fmi20_me", "fmi30_cs", "fmi30_me"))
        and observations.get("fmi1_imported", None) is False
        and observations.get("comsim_executed", None) is True
        and observations.get("event_executed", None) is True
    )
    if observations_complete:
        pass
    else:
        raise ValueError("Checkpoint observations are incomplete")
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
    cells: list[object] = cast(list[object], cells_value)
    cell_index: int
    for cell_index in range(len(expected_cells)):
        cell: dict[str, object] = cast(dict[str, object], cells[cell_index])
        if (
            cell.get("cell_id", None) == expected_cells[cell_index][0]
            and cell.get("integration_step_s", None) == expected_cells[cell_index][1]
            and cell.get("output_step_s", None) == 0.001
            and cell.get("event_count", None) == 3
        ):
            pass
        else:
            raise ValueError("Checkpoint cell order or fixed-step identity mismatch")
    cleanup_receipt_value: object = json.loads(
        (output_dir / "cleanup-receipt.json").read_text(encoding="utf-8")
    )
    if (
        isinstance(cleanup_receipt_value, dict)
        and cleanup_receipt_value.get("schema_version", None) == "1.0"
        and cleanup_receipt_value.get("status", None) == "PASS"
        and cleanup_receipt_value.get("cleanup", None) == cleanup_value
    ):
        pass
    else:
        raise ValueError("Checkpoint cleanup differs from authenticated cleanup receipt")

    # This inventory is captured only after join, proving that neither the
    # worker nor a PowerFactory-named process remains alive.
    release_inventory: dict[str, object] = inspect_process_inventory(worker_pid)
    release_rows: object = release_inventory.get("rows", None)
    if isinstance(release_rows, list) and release_rows == list():
        pass
    else:
        raise RuntimeError("Worker or PowerFactory process remains after native release")

    receipt_path: Path = output_dir / "execution-receipt.json"
    release_path: Path = output_dir / "process-after-release.json"
    if receipt_path.exists():
        if worker_exit_code == 0:
            receipt_value: object = json.loads(receipt_path.read_text(encoding="utf-8"))
            if isinstance(receipt_value, dict):
                receipt: dict[str, object] = cast(dict[str, object], receipt_value)
            else:
                raise ValueError("Execution receipt must be one JSON object")
            receipt_artifacts_value: object = receipt.get("artifacts", None)
            expected_receipt_names: tuple[str, ...] = (
                *expected_artifact_names,
                "release-checkpoint.json",
                "process-after-release.json",
                "observations.json",
            )
            receipt_valid: bool = bool(
                receipt.get("status", None) == "EXECUTION_EVIDENCE_COMPLETE"
                and isinstance(receipt_artifacts_value, list)
                and len(receipt_artifacts_value) == len(expected_receipt_names)
                and receipt.get("artifact_count", None) == len(expected_receipt_names)
                and any(
                    isinstance(item, dict)
                    and item.get("name", None) == "release-checkpoint.json"
                    and item.get("sha256", None)
                    == hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
                    for item in cast(list[object], receipt_artifacts_value)
                )
            )
            if receipt_valid:
                ordinary_artifacts: list[object] = cast(
                    list[object], receipt_artifacts_value
                )
                ordinary_index: int
                for ordinary_index in range(len(expected_receipt_names)):
                    ordinary_value: object = ordinary_artifacts[ordinary_index]
                    ordinary_name: str = expected_receipt_names[ordinary_index]
                    ordinary_bytes: bytes = (output_dir / ordinary_name).read_bytes()
                    if (
                        isinstance(ordinary_value, dict)
                        and set(ordinary_value.keys())
                        == set(("name", "size_bytes", "sha256"))
                        and ordinary_value.get("name", None) == ordinary_name
                        and ordinary_value.get("size_bytes", None) == len(ordinary_bytes)
                        and ordinary_value.get("sha256", None)
                        == hashlib.sha256(ordinary_bytes).hexdigest()
                    ):
                        pass
                    else:
                        raise ValueError("Ordinary execution receipt artifact mismatch")
                ordinary_observations: object = json.loads(
                    (output_dir / "observations.json").read_text(encoding="utf-8")
                )
                if ordinary_observations == observations:
                    pass
                else:
                    raise ValueError("Ordinary receipt observations differ from checkpoint")
                return receipt
            else:
                raise ValueError("Ordinary worker receipt does not bind the checkpoint")
        else:
            raise ValueError("Non-zero worker exit cannot leave an ordinary receipt")
    else:
        if worker_exit_code != 0 and not release_path.exists():
            release_path.write_text(
                json.dumps(release_inventory, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            final_artifact_paths: tuple[Path, ...] = (
                *tuple(pre_release_paths),
                checkpoint_path,
                release_path,
            )
            fallback_receipt: dict[str, object] = write_execution_receipt(
                output_dir,
                observations,
                final_artifact_paths,
            )
            if fallback_receipt.get("status", None) == "EXECUTION_EVIDENCE_COMPLETE":
                return fallback_receipt
            else:
                raise ValueError("Parent finalization produced an incomplete receipt")
        else:
            raise ValueError("Fallback requires non-zero exit and no prior release evidence")


def main() -> int:
    """Run the isolated worker and finalize its release evidence.

    :return: Zero only when the execution receipt is complete and authenticated.
    """

    arguments: argparse.Namespace = parse_arguments()
    expected_nonce: str = secrets.token_hex(32)
    context: multiprocessing.context.BaseContext = multiprocessing.get_context("spawn")
    worker: BaseProcess = context.Process(
        target=worker_main,
        args=(arguments, expected_nonce),
    )
    worker.start()
    worker_pid_value: int | None = worker.pid
    if worker_pid_value is not None and worker_pid_value > 0:
        worker_pid: int = worker_pid_value
    else:
        raise RuntimeError("Spawned PowerFactory worker has no process identifier")
    worker.join()
    worker_exit_value: int | None = worker.exitcode
    if worker_exit_value is not None:
        worker_exit_code: int = worker_exit_value
    else:
        raise RuntimeError("Joined PowerFactory worker has no exit code")
    try:
        receipt: dict[str, object] = finalize_worker_evidence(
            arguments.output_dir.resolve(strict=True),
            expected_nonce,
            worker_pid,
            worker_exit_code,
        )
    except Exception as exception:
        finding: dict[str, object] = {
            "status": "FAIL",
            "worker_pid": worker_pid,
            "worker_exit_code": worker_exit_code,
            "error": f"{exception.__class__.__name__}: {exception}",
        }
        print(json.dumps(finding, sort_keys=True))
        return 2
    print(json.dumps(receipt, sort_keys=True))
    if receipt.get("status", None) == "EXECUTION_EVIDENCE_COMPLETE":
        return 0
    else:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
