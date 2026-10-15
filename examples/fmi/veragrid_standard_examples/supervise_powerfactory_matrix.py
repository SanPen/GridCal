"""Supervise the licensed standard-FMU worker across native engine release."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
from multiprocessing.process import BaseProcess
import os
from pathlib import Path
import secrets
import time

from examples.fmi.powerfactory_first_order.run_powerfactory_first_order import inspect_process_inventory
from examples.fmi.veragrid_standard_examples.run_powerfactory_matrix import (
    PowerFactoryCell,
    PowerFactoryRunJob,
    load_catalog_cells,
    prepare_powerfactory_compatibility_cells,
    run_powerfactory_cell_worker,
)


def hash_file(path: Path) -> str:
    """Return the SHA-256 content identity of one existing evidence file.

    :param path: Exact evidence path.
    :return: Lowercase hexadecimal digest.
    """
    return hashlib.sha256(path.resolve(strict=True).read_bytes()).hexdigest()


def validate_release_checkpoint(
    output_dir: Path,
    expected_nonce: str,
    worker_pid: int,
    job: PowerFactoryRunJob,
) -> dict[str, object]:
    """Verify the worker's immutable pre-release evidence closure.

    :param output_dir: Exact new execution directory.
    :param expected_nonce: Parent-origin run nonce.
    :param worker_pid: Spawned worker PID.
    :param job: Exact expected isolated job.
    :return: Authenticated worker observations.
    """
    checkpoint_path: Path = output_dir / "child-checkpoint.json"
    checkpoint: dict[str, object] = json.loads(checkpoint_path.resolve(strict=True).read_text(encoding="utf-8"))
    identity_valid: bool = bool(
        checkpoint.get("schema_version", None) == "1.0"
        and checkpoint.get("record_kind", None) == "powerfactory_standard_child_checkpoint"
        and checkpoint.get("sealed_dossier_sha256", None) == "4b3aa0ccd496daa7cfbcc3b2d80639724ee0d0255b4b2e2a6763dc5894e57edc"
        and checkpoint.get("run_nonce", None) == expected_nonce
        and checkpoint.get("worker_pid", None) == worker_pid
        and checkpoint.get("job_id", None) == job.job_id
        and checkpoint.get("job_index", None) == job.job_index
        and checkpoint.get("model_name", None) == job.cell.model_name
        and checkpoint.get("fmi_version", None) == job.cell.version
        and checkpoint.get("interface", None) == job.cell.interface
        and checkpoint.get("integration_step_s", None) == job.integration_step
        and checkpoint.get("status", None) == "READY_FOR_PARENT_ACK"
    )
    if identity_valid:
        pass
    else:
        raise ValueError("PowerFactory release checkpoint identity mismatch")
    artifacts_value: object = checkpoint.get("artifacts", None)
    if isinstance(artifacts_value, list):
        artifacts: list[object] = artifacts_value
    else:
        raise ValueError("PowerFactory checkpoint artifact table is absent")
    expected_names: set[str] = set()
    artifact_value: object
    for artifact_value in artifacts:
        if isinstance(artifact_value, dict):
            artifact: dict[str, object] = artifact_value
        else:
            raise ValueError("Malformed checkpoint artifact")
        name: str = str(artifact.get("name", ""))
        path: Path = (output_dir / name).resolve(strict=True)
        if path.is_relative_to(output_dir) and name not in expected_names:
            pass
        else:
            raise ValueError("Artifact path escapes output or repeats")
        content: bytes = path.read_bytes()
        if artifact.get("size_bytes", None) == len(content) and artifact.get("sha256", None) == hashlib.sha256(content).hexdigest():
            expected_names.add(name)
        else:
            raise ValueError("Checkpoint artifact hash or size differs")
    excluded_names: tuple[str, ...] = ("child-checkpoint.json", "parent-checkpoint-ack.json", "worker-ack-validated.json")
    actual_names: set[str] = set(path.relative_to(output_dir).as_posix() for path in output_dir.rglob("*") if path.is_file() and path.name not in excluded_names)
    if actual_names == expected_names:
        pass
    else:
        raise ValueError("Pre-release artifact set differs from checkpoint")
    observations_value: object = checkpoint.get("observations", None)
    if isinstance(observations_value, dict):
        observations: dict[str, object] = observations_value
    else:
        raise ValueError("Checkpoint observations are absent")
    observations_path: Path = output_dir / "observations.json"
    if json.loads(observations_path.read_text(encoding="utf-8")) == observations:
        pass
    else:
        raise ValueError("Observations file differs from checkpoint")
    cells_value: object = observations.get("cells", None)
    cleanup_value: object = observations.get("cleanup", None)
    if isinstance(cells_value, list) and len(cells_value) == 1 and all(isinstance(cell, dict) and cell.get("status", None) == "PASS" for cell in cells_value) and isinstance(cleanup_value, dict) and cleanup_value.get("status", None) == "PASS":
        return observations
    else:
        raise ValueError("Execution matrix or exact project cleanup is incomplete")


def write_matrix_release_checkpoint(
    output_dir: Path,
    child_records: list[dict[str, object]],
) -> dict[str, object]:
    """Publish the authenticated 24-job closure consumed by the validator.

    :param output_dir: Exact external campaign root.
    :param child_records: Parent-authenticated job records in plan order.
    :return: Master checkpoint matching the atomic file on disk.
    """
    cells: list[dict[str, object]] = list()
    child_record: dict[str, object]
    for child_record in child_records:
        observation_value: object = child_record.get("observation", None)
        if isinstance(observation_value, dict):
            observation: dict[str, object] = observation_value
        else:
            raise ValueError("Child record lacks its single observation")
        prefixed: dict[str, object] = dict(observation)
        raw_name: object = observation.get("raw_csv", None)
        job_relative_dir: str = str(child_record.get("job_relative_dir", ""))
        if isinstance(raw_name, str) and job_relative_dir != "":
            prefixed["raw_csv"] = job_relative_dir + "/" + raw_name
        else:
            raise ValueError("Child raw evidence path is absent")
        cells.append(prefixed)
    artifact_paths: list[Path] = sorted(
        path for path in output_dir.rglob("*")
        if path.is_file() and path.name != "release-checkpoint.json"
    )
    artifacts: list[dict[str, object]] = list()
    artifact_path: Path
    for artifact_path in artifact_paths:
        content: bytes = artifact_path.read_bytes()
        artifacts.append({"name": artifact_path.relative_to(output_dir).as_posix(), "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    observations: dict[str, object] = {
        "schema_version": "1.0",
        "sealed_dossier_sha256": "4b3aa0ccd496daa7cfbcc3b2d80639724ee0d0255b4b2e2a6763dc5894e57edc",
        "manifest_sha256": "7099296e4360555daa1ca14f854f3c6b7f11b1c6b0ba38e5e603b9896e726113",
        "cells": cells,
        "children": child_records,
        "status": "PASS",
    }
    checkpoint: dict[str, object] = {
        "schema_version": "1.0",
        "record_kind": "powerfactory_standard_matrix_checkpoint",
        "sealed_dossier_sha256": "4b3aa0ccd496daa7cfbcc3b2d80639724ee0d0255b4b2e2a6763dc5894e57edc",
        "observations": observations,
        "artifacts": artifacts,
        "status": "EXECUTION_EVIDENCE_COMPLETE",
    }
    checkpoint_path: Path = output_dir / "release-checkpoint.json"
    temporary_path: Path = output_dir / "release-checkpoint.json.tmp"
    with temporary_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary_path, checkpoint_path)
    return checkpoint


def parse_arguments() -> argparse.Namespace:
    """Read explicit paths for one new supervised licensed run.

    :return: Parsed worker-compatible arguments.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-root", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--powerfactory-root", type=Path, required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    """Run and authenticate twenty-four isolated licensed workers.

    :return: Zero only after all jobs, exits and process inventories pass.
    """
    arguments: argparse.Namespace = parse_arguments()
    output_dir: Path = arguments.output_dir.resolve(strict=False)
    if output_dir.exists():
        raise FileExistsError("Execution output directory already exists")
    else:
        output_dir.mkdir(parents=True, exist_ok=False)
    repository_root: Path = arguments.repository_root.resolve(strict=True)
    catalog_root: Path = arguments.catalog_root.resolve(strict=True)
    canonical_cells: tuple[PowerFactoryCell, ...] = load_catalog_cells(catalog_root)
    runnable_cells: tuple[PowerFactoryCell, ...] = prepare_powerfactory_compatibility_cells(canonical_cells, repository_root, output_dir)
    jobs: list[PowerFactoryRunJob] = list()
    cell: PowerFactoryCell
    for cell in runnable_cells:
        steps: tuple[float, ...] = (0.001,) if cell.interface == "cs" else (0.000125, 0.0000625, 0.00003125)
        step: float
        for step in steps:
            job_index: int = len(jobs)
            step_tag: str = format(step, ".9f").replace(".", "p")
            job_id: str = str(job_index).zfill(2) + "_" + cell.model_name + "_h_" + step_tag
            jobs.append(PowerFactoryRunJob(job_index, job_id, cell, step))
    if len(jobs) == 24:
        pass
    else:
        raise ValueError("PowerFactory plan must contain exactly twenty-four jobs")
    context: multiprocessing.context.BaseContext = multiprocessing.get_context("spawn")
    child_records: list[dict[str, object]] = list()
    job: PowerFactoryRunJob
    for job in jobs:
        nonce: str = secrets.token_hex(32)
        job_relative_dir: str = "jobs/" + job.job_id
        job_dir: Path = output_dir / job_relative_dir
        child_arguments: argparse.Namespace = argparse.Namespace(
            catalog_root=catalog_root,
            repository_root=repository_root,
            powerfactory_root=arguments.powerfactory_root,
            binding=arguments.binding,
            output_dir=job_dir,
        )
        worker: BaseProcess = context.Process(target=run_powerfactory_cell_worker, args=(child_arguments, job, nonce))
        worker.start()
        worker_pid_value: int | None = worker.pid
        if worker_pid_value is not None and worker_pid_value > 0:
            worker_pid: int = worker_pid_value
        else:
            raise RuntimeError("Spawned PowerFactory worker has no PID")
        checkpoint_path: Path = job_dir / "child-checkpoint.json"
        checkpoint_deadline: float = time.monotonic() + 900.0
        while not checkpoint_path.is_file() and worker.is_alive() and time.monotonic() < checkpoint_deadline:
            time.sleep(0.1)
        if checkpoint_path.is_file():
            pass
        else:
            worker.join(timeout=1.0)
            raise RuntimeError("PowerFactory child did not publish its checkpoint")
        observations: dict[str, object] = validate_release_checkpoint(job_dir.resolve(strict=True), nonce, worker_pid, job)
        checkpoint_hash: str = hash_file(checkpoint_path)
        acknowledgement: dict[str, object] = {"schema_version": "1.0", "record_kind": "powerfactory_parent_checkpoint_ack", "sealed_dossier_sha256": "4b3aa0ccd496daa7cfbcc3b2d80639724ee0d0255b4b2e2a6763dc5894e57edc", "run_nonce": nonce, "worker_pid": worker_pid, "job_id": job.job_id, "job_index": job.job_index, "checkpoint_sha256": checkpoint_hash, "observed_at_utc": time.time(), "status": "ACKNOWLEDGED"}
        acknowledgement_path: Path = job_dir / "parent-checkpoint-ack.json"
        acknowledgement_temporary_path: Path = job_dir / ("parent-checkpoint-ack.json.tmp-" + nonce)
        with acknowledgement_temporary_path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(acknowledgement, indent=2, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(acknowledgement_temporary_path, acknowledgement_path)
        marker_path: Path = job_dir / "worker-ack-validated.json"
        marker_deadline: float = time.monotonic() + 30.0
        while not marker_path.is_file() and worker.is_alive() and time.monotonic() < marker_deadline:
            time.sleep(0.05)
        worker.join(timeout=30.0)
        if worker.is_alive():
            raise TimeoutError("PowerFactory child remained alive after ACK validation")
        else:
            pass
        worker_exit_value: int | None = worker.exitcode
        if worker_exit_value == 0 and marker_path.is_file():
            worker_exit_code: int = 0
        else:
            raise RuntimeError("PowerFactory child did not exit through the authenticated zero path")
        marker_value: object = json.loads(marker_path.read_text(encoding="utf-8"))
        if isinstance(marker_value, dict):
            marker: dict[str, object] = marker_value
        else:
            raise ValueError("Worker ACK marker is malformed")
        acknowledgement_hash: str = hash_file(acknowledgement_path)
        marker_valid: bool = bool(
            marker.get("run_nonce", None) == nonce
            and marker.get("worker_pid", None) == worker_pid
            and marker.get("job_id", None) == job.job_id
            and marker.get("job_index", None) == job.job_index
            and marker.get("checkpoint_sha256", None) == checkpoint_hash
            and marker.get("ack_sha256", None) == acknowledgement_hash
            and marker.get("status", None) == "ACK_VALIDATED"
        )
        if marker_valid:
            pass
        else:
            raise ValueError("Worker ACK marker identity mismatch")
        release_inventory: dict[str, object] = inspect_process_inventory(worker_pid)
        release_rows: object = release_inventory.get("rows", None)
        if isinstance(release_rows, list) and release_rows == list():
            pass
        else:
            raise RuntimeError("Owned worker or PowerFactory process remains alive")
        release_path: Path = job_dir / "process-after-release.json"
        release_path.write_text(json.dumps(release_inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        cells_value: object = observations.get("cells", None)
        if isinstance(cells_value, list) and len(cells_value) == 1 and isinstance(cells_value[0], dict):
            observation: dict[str, object] = cells_value[0]
        else:
            raise ValueError("Authenticated child observation is malformed")
        child_records.append({"job_id": job.job_id, "job_index": job.job_index, "job_relative_dir": job_relative_dir, "run_nonce": nonce, "worker_pid": worker_pid, "worker_exit_code": worker_exit_code, "checkpoint_sha256": checkpoint_hash, "ack_sha256": acknowledgement_hash, "marker_sha256": hash_file(marker_path), "process_after_release_sha256": hash_file(release_path), "observation": observation, "status": "PASS"})
        print(json.dumps({"job": job.job_id, "status": "PASS"}, sort_keys=True), flush=True)
    checkpoint: dict[str, object] = write_matrix_release_checkpoint(output_dir, child_records)
    execution_complete: bool = len(child_records) == 24 and all(record.get("status", None) == "PASS" for record in child_records)
    receipt: dict[str, object] = {"schema_version": "1.0", "sealed_dossier_sha256": "4b3aa0ccd496daa7cfbcc3b2d80639724ee0d0255b4b2e2a6763dc5894e57edc", "checkpoint_sha256": hash_file(output_dir / "release-checkpoint.json"), "execution_pass_count": len(child_records), "execution_run_count": len(jobs), "numerical_verdict": "PENDING_INDEPENDENT_VALIDATION", "status": "EXECUTION_EVIDENCE_COMPLETE" if execution_complete and checkpoint.get("status", None) == "EXECUTION_EVIDENCE_COMPLETE" else "COMPLETED_WITH_FINDINGS"}
    (output_dir / "execution-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["status"] == "EXECUTION_EVIDENCE_COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
