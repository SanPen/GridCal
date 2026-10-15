"""Validate commercial first-order traces against independent pointwise oracles."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np


def continuous_oracle(time_values: np.ndarray) -> np.ndarray:
    """Evaluate the exact continuous solution for the approved held input.

    The state is continuous at every event. Each interval is evaluated as
    ``x(t)=u_k+(x(t_k)-u_k)*exp(-(t-t_k)/tau)`` with ``tau=0.1 s``.

    :param time_values: Monotonic reporting times between 0 and 1.2 seconds.
    :return: Exact first-order state at every supplied time.
    """

    result: np.ndarray = np.empty(time_values.shape[0], dtype=np.float64)
    state_at_02: float = 0.0
    state_at_05: float = 1.0 + (state_at_02 - 1.0) * np.exp(-3.0)
    state_at_08: float = -0.5 + (state_at_05 + 0.5) * np.exp(-3.0)
    index: int
    for index in range(time_values.shape[0]):
        time_value: float = float(time_values[index])
        if time_value >= 0.8:
            segment_start: float = 0.8
            segment_input: float = 0.25
            segment_state: float = state_at_08
        elif time_value >= 0.5:
            segment_start = 0.5
            segment_input = -0.5
            segment_state = state_at_05
        elif time_value >= 0.2:
            segment_start = 0.2
            segment_input = 1.0
            segment_state = state_at_02
        else:
            segment_start = 0.0
            segment_input = 0.0
            segment_state = 0.0
        result[index] = segment_input + (segment_state - segment_input) * np.exp(
            -(time_value - segment_start) / 0.1
        )
    return result


def backward_euler_oracle(time_values: np.ndarray, input_values: np.ndarray) -> np.ndarray:
    """Evaluate the sealed backward-Euler interval recurrence.

    With ``t[n]=n*h`` and ``h/tau=0.01``, the input sample ``u[n]`` is held
    over ``[t[n],t[n+1])`` and advances the state to ``x[n+1]``.

    :param time_values: Exact common reporting grid.
    :param input_values: Right-continuous held input on the same grid.
    :return: Backward-Euler state sequence beginning at ``x[0]=0``.
    :raises ValueError: If the arrays do not share the required shape.
    """

    if time_values.shape != input_values.shape:
        raise ValueError("Time and input arrays must have identical shapes")
    else:
        pass
    result: np.ndarray = np.empty(time_values.shape[0], dtype=np.float64)
    result[0] = 0.0
    index: int
    for index in range(time_values.shape[0] - 1):
        result[index + 1] = (result[index] + 0.01 * input_values[index]) / 1.01
    return result


def main() -> None:
    """Validate six retained traces against every sealed pointwise oracle.

    :return: None. A failed cell, version pair, event, or grid check exits non-zero.
    """

    if sys.dont_write_bytecode:
        pass
    else:
        raise ValueError("Run this module with python -B -m")
    argument_parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Validate the Simulink first-order FMI trace matrix."
    )
    argument_parser.add_argument("--execution-dir", type=Path, required=True)
    arguments: argparse.Namespace = argument_parser.parse_args()
    execution_dir: Path = arguments.execution_dir.resolve(strict=True)
    repository_root: Path = Path(__file__).resolve().parents[4]
    if execution_dir.is_relative_to(repository_root):
        raise ValueError("Numerical output must remain outside the repository")
    else:
        pass
    manifest_path: Path = execution_dir / "first-order-fmu-manifest.json"
    generator_manifest: dict[str, object] = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )
    runtime_receipt_path: Path = execution_dir / "simulink-six-cell-receipt.json"
    runtime_receipt: dict[str, object] = json.loads(
        runtime_receipt_path.read_text(encoding="utf-8")
    )
    runtime_binding_is_valid: bool = bool(
        generator_manifest["status"] == "PASS"
        and runtime_receipt["status"] == "PASS"
        and runtime_receipt["cell_count"] == 6
        and runtime_receipt["pass_count"] == 6
        and runtime_receipt["source_commit"] == generator_manifest["source_commit"]
        and runtime_receipt["git_tree_sha1"] == generator_manifest["git_tree_sha1"]
        and runtime_receipt["source_provenance"] == generator_manifest["source_provenance"]
        and runtime_receipt["recipe_assets"] == generator_manifest["recipe_assets"]
    )
    if runtime_binding_is_valid:
        pass
    else:
        raise ValueError("Runtime receipt is not bound to the current FMU manifest")
    trace_dir: Path = execution_dir / "traces"
    comparison_dir: Path = execution_dir / "comparison"
    receipt_path: Path = execution_dir / "numerical-comparison-receipt.json"
    comparison_path: Path = comparison_dir / "all-traces-and-oracles.csv"
    if receipt_path.exists() or comparison_dir.exists():
        raise RuntimeError("Refusing to overwrite numerical evidence")
    else:
        pass
    comparison_dir.mkdir(parents=True, exist_ok=False)

    target_time: np.ndarray = np.linspace(0.0, 1.2, 1201, dtype=np.float64)
    target_input: np.ndarray = np.where(
        target_time >= 0.8,
        0.25,
        np.where(target_time >= 0.5, -0.5, np.where(target_time >= 0.2, 1.0, 0.0)),
    )
    analytic_x: np.ndarray = continuous_oracle(target_time)
    be_x: np.ndarray = backward_euler_oracle(target_time, target_input)
    cell_ids: tuple[str, ...] = (
        "fmi10_cs",
        "fmi10_me",
        "fmi20_cs",
        "fmi20_me",
        "fmi30_cs",
        "fmi30_me",
    )
    traces: dict[str, np.ndarray] = dict()
    cell_receipts: list[dict[str, object]] = list()
    cell_id: str
    for cell_index in range(len(cell_ids)):
        cell_id = cell_ids[cell_index]
        trace_path: Path = trace_dir / f"{cell_id}.csv"
        trace: np.ndarray = np.genfromtxt(
            trace_path,
            delimiter=",",
            names=True,
            dtype=np.float64,
            encoding="utf-8",
        )
        if trace.shape[0] != 1201:
            raise RuntimeError(f"{cell_id} has {trace.shape[0]} samples")
        else:
            pass
        time_error: float = float(np.max(np.abs(trace["time"] - target_time)))
        input_error: float = float(np.max(np.abs(trace["u"] - target_input)))
        finite: bool = bool(
            np.all(np.isfinite(trace["time"]))
            and np.all(np.isfinite(trace["u"]))
            and np.all(np.isfinite(trace["x"]))
        )
        if cell_id.endswith("_cs"):
            primary_reference: np.ndarray = be_x
            primary_reference_name: str = "backward_euler"
            primary_tolerance: float = 2.0e-10
        else:
            primary_reference = analytic_x
            primary_reference_name = "continuous_analytic"
            primary_tolerance = 1.0e-7
        primary_abs_error: np.ndarray = np.abs(trace["x"] - primary_reference)
        analytic_abs_error: np.ndarray = np.abs(trace["x"] - analytic_x)
        primary_max_index: int = int(np.argmax(primary_abs_error))
        analytic_max_index: int = int(np.argmax(analytic_abs_error))
        primary_max_error: float = float(primary_abs_error[primary_max_index])
        analytic_max_error: float = float(analytic_abs_error[analytic_max_index])

        # Event-neighborhood assertions expose the one-sample convention and
        # prove that the state at each event is inherited, not reset.
        event_checks: list[dict[str, object]] = list()
        event_index: int
        for event_index in (200, 500, 800):
            old_input: float = float(target_input[event_index - 1])
            new_input: float = float(target_input[event_index])
            event_reference: float
            if cell_id.endswith("_cs"):
                event_reference = float(be_x[event_index])
            else:
                event_reference = float(analytic_x[event_index])
            inherited_state_error: float = abs(float(trace["x"][event_index]) - event_reference)
            event_checks.append(
                {
                    "event_time": float(target_time[event_index]),
                    "u_before": float(trace["u"][event_index - 1]),
                    "u_at": float(trace["u"][event_index]),
                    "u_after": float(trace["u"][event_index + 1]),
                    "expected_old_u": old_input,
                    "expected_new_u": new_input,
                    "inherited_state_reference": primary_reference_name,
                    "inherited_state_abs_error": inherited_state_error,
                    "status": "PASS"
                    if (
                        abs(float(trace["u"][event_index - 1]) - old_input) <= 1.0e-15
                        and abs(float(trace["u"][event_index]) - new_input) <= 1.0e-15
                        and abs(float(trace["u"][event_index + 1]) - new_input) <= 1.0e-15
                        and inherited_state_error <= primary_tolerance
                    )
                    else "FAIL",
                }
            )
        event_pass: bool = bool(
            all(str(event_check["status"]) == "PASS" for event_check in event_checks)
        )
        cell_pass: bool = bool(
            finite
            and time_error <= 5.0e-13
            and input_error <= 1.0e-15
            and primary_max_error <= primary_tolerance
            and analytic_max_error <= 0.004
            and event_pass
        )
        trace_digest: hashlib._Hash = hashlib.sha256()
        with trace_path.open("rb") as trace_stream:
            while True:
                trace_chunk: bytes = trace_stream.read(1024 * 1024)
                if trace_chunk == b"":
                    break
                else:
                    trace_digest.update(trace_chunk)
        runtime_cell: dict[str, object] = runtime_receipt["cells"][cell_index]
        manifest_cell: dict[str, object] = generator_manifest["cells"][cell_index]
        trace_binding_is_valid: bool = bool(
            runtime_cell["cell_id"] == cell_id
            and manifest_cell["cell_id"] == cell_id
            and runtime_cell["trace_sha256"] == trace_digest.hexdigest()
            and runtime_cell["fmu_sha256"] == manifest_cell["fmu_sha256"]
        )
        if trace_binding_is_valid:
            pass
        else:
            raise ValueError("Trace or FMU identity differs from the current runtime")
        traces[cell_id] = np.asarray(trace["x"], dtype=np.float64)
        cell_receipts.append(
            {
                "cell_id": cell_id,
                "trace_sha256": trace_digest.hexdigest(),
                "sample_count": int(trace.shape[0]),
                "finite": finite,
                "max_abs_time_error": time_error,
                "max_abs_input_error": input_error,
                "primary_reference": primary_reference_name,
                "primary_tolerance": primary_tolerance,
                "primary_max_abs_error": primary_max_error,
                "primary_max_error_time": float(target_time[primary_max_index]),
                "analytic_crosscheck_tolerance": 0.004,
                "analytic_crosscheck_max_abs_error": analytic_max_error,
                "analytic_crosscheck_max_error_time": float(target_time[analytic_max_index]),
                "event_checks": event_checks,
                "status": "PASS" if cell_pass else "FAIL",
            }
        )

    version_pairs: list[dict[str, object]] = list()
    interface: str
    for interface in ("cs", "me"):
        interface_ids: tuple[str, ...] = (
            f"fmi10_{interface}",
            f"fmi20_{interface}",
            f"fmi30_{interface}",
        )
        left_index: int
        right_index: int
        for left_index in range(3):
            for right_index in range(left_index + 1, 3):
                left_id: str = interface_ids[left_index]
                right_id: str = interface_ids[right_index]
                delta: np.ndarray = np.abs(traces[left_id] - traces[right_id])
                max_index: int = int(np.argmax(delta))
                max_delta: float = float(delta[max_index])
                version_pairs.append(
                    {
                        "interface": interface.upper(),
                        "left": left_id,
                        "right": right_id,
                        "tolerance": 1.0e-12,
                        "max_abs_delta": max_delta,
                        "max_delta_time": float(target_time[max_index]),
                        "status": "PASS" if max_delta <= 1.0e-12 else "FAIL",
                    }
                )

    comparison_values: np.ndarray = np.column_stack(
        (
            target_time,
            target_input,
            analytic_x,
            be_x,
            traces["fmi10_cs"],
            traces["fmi20_cs"],
            traces["fmi30_cs"],
            traces["fmi10_me"],
            traces["fmi20_me"],
            traces["fmi30_me"],
        )
    )
    np.savetxt(
        comparison_path,
        comparison_values,
        delimiter=",",
        header="time,u,continuous_oracle,backward_euler_oracle,fmi10_cs,fmi20_cs,fmi30_cs,fmi10_me,fmi20_me,fmi30_me",
        comments="",
        fmt="%.17g",
    )
    comparison_digest: hashlib._Hash = hashlib.sha256()
    with comparison_path.open("rb") as comparison_stream:
        while True:
            comparison_chunk: bytes = comparison_stream.read(1024 * 1024)
            if comparison_chunk == b"":
                break
            else:
                comparison_digest.update(comparison_chunk)

    cells_pass: bool = bool(
        all(str(cell_receipt["status"]) == "PASS" for cell_receipt in cell_receipts)
    )
    pairs_pass: bool = bool(
        all(str(pair_receipt["status"]) == "PASS" for pair_receipt in version_pairs)
    )
    dynamics_visible: bool = bool(
        float(np.max(analytic_x) - np.min(analytic_x)) >= 1.0
        and float(np.max(np.abs(np.diff(analytic_x)))) > 1.0e-4
    )
    overall_pass: bool = bool(cells_pass and pairs_pass and dynamics_visible)
    receipt: dict[str, object] = {
        "schema_version": "1.0",
        "campaign": "veragrid-maintained-simulink-first-order-fmi-matrix",
        "claim": "normalized first-order verification fixture; not a device-specific physical model",
        "source_commit": generator_manifest["source_commit"],
        "git_tree_sha1": generator_manifest["git_tree_sha1"],
        "source_provenance": generator_manifest["source_provenance"],
        "recipe_assets": generator_manifest["recipe_assets"],
        "fmu_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "runtime_receipt_sha256": hashlib.sha256(runtime_receipt_path.read_bytes()).hexdigest(),
        "equation": "tau*dx/dt=u-x",
        "tau_s": 0.1,
        "step_s": 0.001,
        "stop_s": 1.2,
        "sample_count": 1201,
        "boundary_convention": "observe x[n], update/log u[n], hold on [t[n],t[n+1]), advance, observe x[n+1]",
        "comparison_path": str(comparison_path),
        "comparison_sha256": comparison_digest.hexdigest(),
        "dynamics_visible": dynamics_visible,
        "analytic_range": float(np.max(analytic_x) - np.min(analytic_x)),
        "cells": cell_receipts,
        "version_pairs": version_pairs,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if overall_pass else "FAIL",
    }
    receipt_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "analytic_range": receipt["analytic_range"],
                "cell_max_errors": {
                    str(item["cell_id"]): item["primary_max_abs_error"]
                    for item in cell_receipts
                },
                "version_pair_maxima": {
                    f"{item['left']}:{item['right']}": item["max_abs_delta"]
                    for item in version_pairs
                },
            }
        ),
        flush=True,
    )
    if not overall_pass:
        raise SystemExit(1)
    else:
        pass
if __name__ == "__main__":
    main()
else:
    pass
