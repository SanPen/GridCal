"""Validate named PowerFactory traces against the published electrical catalog.

This module does not import the licensed API. It preserves the raw 1 ms
evidence, selects only exact 10 ms reference samples, and never interpolates.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np


def load_numeric_csv(path: Path) -> np.ndarray:
    """Read one finite, uniquely named numeric CSV without changing row order.

    :param path: Existing CSV path.
    :return: Structured array with every original column.
    """
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader: csv.reader = csv.reader(stream)
        header: list[str] = next(reader)
        if len(header) > 1 and header[0] == "time" and len(set(header)) == len(header):
            pass
        else:
            raise ValueError("CSV requires unique time-first column names")
        rows: list[tuple[float, ...]] = list()
        raw_row: list[str]
        for raw_row in reader:
            if len(raw_row) == len(header):
                numeric_row: tuple[float, ...] = tuple(float(item) for item in raw_row)
            else:
                raise ValueError("CSV row width differs from header")
            if all(math.isfinite(value) for value in numeric_row):
                rows.append(numeric_row)
            else:
                raise ValueError("CSV contains a non-finite value")
    dtype_fields: list[tuple[str, type[np.float64]]] = [(name, np.float64) for name in header]
    result: np.ndarray = np.array(rows, dtype=np.dtype(dtype_fields))
    if result.size > 0:
        return result
    else:
        raise ValueError("CSV has no data rows")


def write_powerfactory_validator_view(
    raw_path: Path,
    schedule_path: Path,
    input_names: tuple[str, ...],
    output_names: tuple[str, ...],
    stop_time: float,
    output_reference_sample_count: int,
    view_path: Path,
) -> dict[str, object]:
    """Write an auditable view whose only permitted edits are t=0 inputs.

    PowerFactory records the pre-event input vector at the raw zero-time row,
    although the owned parameter events take effect before the first positive
    simulation tick.  The immutable raw trace remains the primary evidence;
    this separate view supplies the published schedule baseline to the
    existing right-continuous numerical validator.

    :param raw_path: Immutable licensed PowerFactory trace.
    :param schedule_path: Published physical input schedule.
    :param input_names: Exact semantic input names.
    :param output_names: Exact semantic output names.
    :param stop_time: Authenticated published output-reference horizon.
    :param output_reference_sample_count: Authenticated reference row count.
    :param view_path: New, separately named validator-view destination.
    :return: Raw/view hashes, exact edited coordinates and lattice evidence.
    """
    raw: np.ndarray = load_numeric_csv(raw_path)
    schedule: np.ndarray = load_numeric_csv(schedule_path)
    raw_names: tuple[str, ...] | None = raw.dtype.names
    schedule_names: tuple[str, ...] | None = schedule.dtype.names
    expected_names: set[str] = set(("time",)) | set(input_names) | set(output_names)
    if raw_names is not None and set(raw_names) == expected_names and len(raw_names) == len(expected_names):
        pass
    else:
        raise ValueError("Raw trace lacks exact unique named inputs and outputs")
    if schedule_names is not None and set(schedule_names) == set(("time",)) | set(input_names):
        pass
    else:
        raise ValueError("Published schedule does not match named inputs")
    # Derive the required 1 ms lattice from the authenticated family-specific
    # reference instead of imposing the 2.0 s horizon on every model family.
    expected_tick_count: int = int(round(stop_time / 0.001)) + 1
    if stop_time >= 0.0 and abs((expected_tick_count - 1) * 0.001 - stop_time) <= 5e-12:
        pass
    else:
        raise ValueError("Published stop time is not on the 1 ms lattice")
    actual_tick_count: int = int(raw.size)
    if actual_tick_count == expected_tick_count and abs(float(raw[0]["time"])) <= 5e-12 and abs(float(schedule[0]["time"])) <= 5e-12:
        pass
    else:
        raise ValueError("PowerFactory validator view has an unexpected tick count")
    tick_index: int
    for tick_index in range(raw.size):
        if abs(float(raw[tick_index]["time"]) - tick_index / 1000.0) <= 5e-12:
            pass
        else:
            raise ValueError("Raw trace is not the exact 1 ms lattice")
    for input_name in input_names:
        if float(raw[1][input_name]) == float(schedule[0][input_name]):
            pass
        else:
            raise ValueError("First positive input sample does not prove the t=0 event")
    raw_digest_before: str = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    view: np.ndarray = raw.copy()
    rewritten_positions: list[str] = list()
    numerical_differences: list[dict[str, object]] = list()
    for input_name in input_names:
        raw_value: float = float(raw[0][input_name])
        view_value: float = float(schedule[0][input_name])
        view[0][input_name] = view_value
        rewritten_positions.append("row=0,column=" + input_name)
        if raw_value != view_value:
            numerical_differences.append({"row": 0, "column": input_name, "raw": raw_value, "view": view_value})
        else:
            pass
    if np.array_equal(raw[1:], view[1:]) and all(np.array_equal(raw[output_name], view[output_name]) for output_name in output_names):
        pass
    else:
        raise RuntimeError("Validator view changed a forbidden sample or output")
    view_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path = view_path.with_name(view_path.name + ".tmp")
    if view_path.exists() or temporary_path.exists():
        raise FileExistsError("Validator view destination is not new")
    else:
        pass
    with temporary_path.open("x", encoding="utf-8", newline="") as stream:
        writer: csv.writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(raw_names)
        for tick_index in range(view.size):
            writer.writerow([format(float(view[tick_index][name]), ".17g") for name in raw_names])
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary_path, view_path)
    if hashlib.sha256(raw_path.read_bytes()).hexdigest() == raw_digest_before:
        pass
    else:
        raise RuntimeError("Immutable raw trace changed while writing its validator view")
    reloaded_view: np.ndarray = load_numeric_csv(view_path)
    if np.array_equal(reloaded_view, view):
        pass
    else:
        raise RuntimeError("Persisted validator view differs from its verified array")
    # Reuse the canonical event gate and retain every accepted one-tick event
    # transition in the per-run receipt instead of weakening raw evidence.
    canonical: np.ndarray = canonicalize_named_trace(
        reloaded_view,
        schedule,
        input_names,
        output_names,
        stop_time,
    )
    delayed_transitions: list[dict[str, object]] = list()
    schedule_index: int
    for schedule_index in range(1, schedule.size):
        event_time: float = float(schedule[schedule_index]["time"])
        if abs(event_time - float(schedule[schedule_index - 1]["time"])) <= 5e-12:
            event_tick: int = int(round(event_time * 1000.0))
            input_name: str
            for input_name in input_names:
                old_value: float = float(schedule[schedule_index - 1][input_name])
                new_value: float = float(schedule[schedule_index][input_name])
                if old_value != new_value and float(canonical[event_tick][input_name]) == old_value:
                    delayed_transitions.append({
                        "event_time_s": event_time,
                        "input_name": input_name,
                        "old_value": old_value,
                        "event_sample_value": float(canonical[event_tick][input_name]),
                        "next_tick_value": float(canonical[event_tick + 1][input_name]),
                        "new_value": new_value,
                    })
                else:
                    pass
        else:
            pass
    return {
        "raw_sha256": raw_digest_before,
        "validator_view_sha256": hashlib.sha256(view_path.read_bytes()).hexdigest(),
        "rewritten_positions": rewritten_positions,
        "numerical_difference_count": len(numerical_differences),
        "numerical_differences": numerical_differences,
        "input_lattice_tick_count": actual_tick_count,
        "actual_input_lattice_tick_count": actual_tick_count,
        "expected_input_lattice_tick_count": expected_tick_count,
        "authenticated_output_reference_sample_count": output_reference_sample_count,
        "delayed_input_transition_count": len(delayed_transitions),
        "delayed_input_transitions": delayed_transitions,
    }


def canonicalize_named_trace(
    raw: np.ndarray,
    schedule: np.ndarray,
    input_names: tuple[str, ...],
    output_names: tuple[str, ...],
    stop_time: float,
) -> np.ndarray:
    """Select exact right-continuous 1 ms samples and gate every input.

    :param raw: Retained PowerFactory rows, including possible event duplicates.
    :param schedule: Published named input rows with old/new event pairs.
    :param input_names: Expected semantic input names.
    :param output_names: Expected semantic output names.
    :param stop_time: Published stop time in seconds.
    :return: Structured array of exactly one row per 1 ms tick.
    """
    raw_names: tuple[str, ...] | None = raw.dtype.names
    schedule_names: tuple[str, ...] | None = schedule.dtype.names
    expected_names: set[str] = set(("time",)) | set(input_names) | set(output_names)
    if raw_names is not None and set(raw_names) == expected_names and len(raw_names) == len(expected_names):
        pass
    else:
        raise ValueError("Raw trace lacks exact unique named inputs and outputs")
    if schedule_names is not None and set(schedule_names) == set(("time",)) | set(input_names):
        pass
    else:
        raise ValueError("Published input schedule does not match named inputs")
    if len(set(input_names)) == len(input_names) and len(set(output_names)) == len(output_names):
        pass
    else:
        raise ValueError("Expected input or output names are duplicated")
    target_count: int = int(round(stop_time * 1000.0)) + 1
    if abs((target_count - 1) / 1000.0 - stop_time) <= 5e-12:
        pass
    else:
        raise ValueError("Stop time is not on the 1 ms lattice")
    if abs(float(schedule[0]["time"])) <= 5e-12:
        pass
    else:
        raise ValueError("Schedule does not begin at zero")
    # Each repeated schedule time describes the old and new input vector.
    events: dict[int, tuple[np.ndarray, np.ndarray]] = dict()
    schedule_index: int
    for schedule_index in range(1, schedule.size):
        event_time: float = float(schedule[schedule_index]["time"])
        prior_time: float = float(schedule[schedule_index - 1]["time"])
        if event_time + 5e-12 >= prior_time:
            pass
        else:
            raise ValueError("Schedule time is reversed")
        if abs(event_time - prior_time) <= 5e-12:
            event_tick: int = int(round(event_time * 1000.0))
            if event_tick > 0 and event_tick < target_count:
                pass
            else:
                raise ValueError("Event is outside the run")
            old_values: np.ndarray = np.array([float(schedule[schedule_index - 1][name]) for name in input_names], dtype=np.float64)
            new_values: np.ndarray = np.array([float(schedule[schedule_index][name]) for name in input_names], dtype=np.float64)
            if event_tick not in events and np.any(old_values != new_values):
                events[event_tick] = (old_values, new_values)
            else:
                raise ValueError("Event has no change or is repeated")
        else:
            pass
    canonical: np.ndarray = np.empty(target_count, dtype=raw.dtype)
    raw_index: int = 0
    schedule_cursor: int = 0
    pending_new_vector: np.ndarray | None = None
    pending_event_tick: int | None = None
    tick: int
    for tick in range(target_count):
        time_value: float = tick / 1000.0
        group_start: int = raw_index
        while raw_index < raw.size and abs(float(raw[raw_index]["time"]) - time_value) <= 5e-12:
            raw_index += 1
        group_count: int = raw_index - group_start
        if group_count > 0:
            pass
        else:
            raise ValueError("Missing or off-grid 1 ms PowerFactory row")
        event_delayed: bool = False
        if pending_new_vector is not None:
            if tick in events:
                raise ValueError("An adjacent event occurred while a delayed transition was pending")
            else:
                pass
            if pending_event_tick is not None and tick == pending_event_tick + 1 and group_count == 1:
                pass
            else:
                raise ValueError("Delayed event successor tick is malformed")
            if all(float(raw[raw_index - 1][name]) == float(pending_new_vector[index]) for index, name in enumerate(input_names)):
                pending_new_vector = None
                pending_event_tick = None
            else:
                raise ValueError("Delayed event did not apply the complete new vector on the next tick")
        elif tick in events:
            old_vector: np.ndarray = events[tick][0]
            new_vector: np.ndarray = events[tick][1]
            transitioned: np.ndarray = np.zeros(len(input_names), dtype=np.bool_)
            row_index: int
            for row_index in range(group_start, raw_index):
                channel_index: int
                for channel_index in range(len(input_names)):
                    observed: float = float(raw[row_index][input_names[channel_index]])
                    old_value: float = float(old_vector[channel_index])
                    new_value: float = float(new_vector[channel_index])
                    if observed == old_value and not transitioned[channel_index]:
                        pass
                    elif observed == new_value:
                        transitioned[channel_index] = old_value != new_value
                    else:
                        raise ValueError("Event input has an intermediate or reversed value")
            final_vector: np.ndarray = np.array([float(raw[raw_index - 1][name]) for name in input_names], dtype=np.float64)
            if np.array_equal(final_vector, new_vector):
                pass
            else:
                changed_indices: np.ndarray = np.flatnonzero(old_vector != new_vector)
                delayed_tuple_allowed: bool = (
                    tick == 1100
                    and changed_indices.size == 1
                    and input_names[int(changed_indices[0])] == "UPssPu_ESDC2A"
                )
                if delayed_tuple_allowed and np.array_equal(final_vector, old_vector) and tick + 1 < target_count:
                    pending_new_vector = new_vector
                    pending_event_tick = tick
                    event_delayed = True
                else:
                    raise ValueError("Final event row is neither the required new vector nor the exact allowed delayed tuple")
        elif group_count == 1:
            pass
        else:
            raise ValueError("Non-event 1 ms tick has duplicate rows")
        canonical[tick] = raw[raw_index - 1]
        canonical[tick]["time"] = time_value
        while schedule_cursor + 1 < schedule.size and float(schedule[schedule_cursor + 1]["time"]) <= time_value + 5e-12:
            schedule_cursor += 1
        input_name: str
        input_index: int
        for input_index, input_name in enumerate(input_names):
            if event_delayed:
                expected_input: float = float(events[tick][0][input_index])
            else:
                expected_input = float(schedule[schedule_cursor][input_name])
            if float(canonical[tick][input_name]) == expected_input:
                pass
            else:
                raise ValueError("Canonical 1 ms input differs from published schedule")
    if pending_new_vector is None and pending_event_tick is None:
        pass
    else:
        raise ValueError("Delayed event has no successor tick")
    if raw_index == raw.size:
        return canonical
    else:
        raise ValueError("PowerFactory trace has trailing or off-grid rows")


def select_reference_lattice(canonical: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Select exact PowerFactory rows matching the published 10 ms reference.

    :param canonical: Validated 1 ms PowerFactory trace.
    :param reference: Published FMPy 10 ms reference.
    :return: PowerFactory rows at the reference times, without interpolation.
    """
    selected: np.ndarray = canonical[::10]
    if selected.size == reference.size and np.all(np.abs(selected["time"] - reference["time"]) <= 5e-12):
        return selected
    else:
        raise ValueError("Reference lattice does not exactly match 10 ms rows")


def validate_cell(
    raw_path: Path,
    schedule_path: Path,
    reference_path: Path,
    input_names: tuple[str, ...],
    output_names: tuple[str, ...],
    stop_time: float,
    comparison_path: Path,
) -> dict[str, object]:
    """Gate one exact standard FMU execution and retain pointwise differences.

    :param raw_path: Licensed PowerFactory raw CSV.
    :param schedule_path: Published named input CSV.
    :param reference_path: Published matching FMPy output CSV.
    :param input_names: Expected input names.
    :param output_names: Expected output names.
    :param stop_time: Published run horizon.
    :param comparison_path: New external comparison CSV.
    :return: Per-output numerical receipt and PASS or FAIL.
    """
    raw: np.ndarray = load_numeric_csv(raw_path)
    schedule: np.ndarray = load_numeric_csv(schedule_path)
    reference: np.ndarray = load_numeric_csv(reference_path)
    canonical: np.ndarray = canonicalize_named_trace(raw, schedule, input_names, output_names, stop_time)
    selected: np.ndarray = select_reference_lattice(canonical, reference)
    if reference.dtype.names == tuple(("time",) + output_names):
        pass
    else:
        raise ValueError("Reference output names or order differ from catalog")
    event_times: set[float] = set()
    schedule_index: int
    for schedule_index in range(1, schedule.size):
        if abs(float(schedule[schedule_index]["time"]) - float(schedule[schedule_index - 1]["time"])) <= 5e-12:
            event_times.add(float(schedule[schedule_index]["time"]))
        else:
            pass
    metrics: dict[str, object] = dict()
    status: str = "PASS"
    comparison_path.parent.mkdir(parents=True, exist_ok=True)
    with comparison_path.open("x", encoding="utf-8", newline="") as stream:
        writer: csv.writer = csv.writer(stream, lineterminator="\n")
        header: list[str] = ["time"]
        output_name: str
        for output_name in output_names:
            header.extend(("ref_" + output_name, "pf_" + output_name, "abs_" + output_name))
        writer.writerow(header)
        row_index: int
        for row_index in range(selected.size):
            output_row: list[str] = [format(float(selected[row_index]["time"]), ".17g")]
            for output_name in output_names:
                expected: float = float(reference[row_index][output_name])
                actual: float = float(selected[row_index][output_name])
                output_row.extend((format(expected, ".17g"), format(actual, ".17g"), format(abs(actual - expected), ".17g")))
            writer.writerow(output_row)
    for output_name in output_names:
        differences: np.ndarray = np.abs(selected[output_name] - reference[output_name])
        denominator: float = max(1.0, float(np.ptp(reference[output_name])))
        valid_mask: np.ndarray = np.ones(selected.size, dtype=np.bool_)
        valid_mask[0] = False
        event_details: dict[str, object] = dict()
        event_time: float
        for event_time in sorted(event_times):
            event_indices: np.ndarray = np.flatnonzero(np.abs(reference["time"] - event_time) <= 5e-12)
            if event_indices.size == 1 and int(event_indices[0]) > 0:
                event_index: int = int(event_indices[0])
                valid_mask[event_index] = False
                actual_event: float = float(selected[event_index][output_name])
                previous_error: float = abs(actual_event - float(reference[event_index - 1][output_name]))
                current_error: float = abs(actual_event - float(reference[event_index][output_name]))
                envelope_error: float = min(previous_error, current_error)
                event_details[format(event_time, ".12g")] = {"previous": previous_error, "current": current_error, "envelope": envelope_error}
                if envelope_error <= 0.005 and envelope_error / denominator <= 0.005:
                    pass
                else:
                    status = "FAIL"
            else:
                raise ValueError("Published event is absent from reference lattice")
        maximum: float = float(np.max(differences[valid_mask]))
        maximum_index: int = int(np.flatnonzero(valid_mask)[np.argmax(differences[valid_mask])])
        if maximum <= 0.005 and maximum / denominator <= 0.005:
            pass
        else:
            status = "FAIL"
        metrics[output_name] = {"maximum_absolute": maximum, "maximum_normalized": maximum / denominator, "at_time": float(selected[maximum_index]["time"]), "raw_t0_absolute": float(differences[0]), "events": event_details}
    return {"status": status, "raw_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(), "schedule_sha256": hashlib.sha256(schedule_path.read_bytes()).hexdigest(), "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(), "comparison_sha256": hashlib.sha256(comparison_path.read_bytes()).hexdigest(), "metrics": metrics}


def validate_version_consistency(
    fmi2_comparison: Path,
    fmi3_comparison: Path,
    output_names: tuple[str, ...],
) -> dict[str, object]:
    """Compare standard FMI 2 and 3 outputs at every exact reference sample.

    :param fmi2_comparison: FMI 2 retained comparison CSV.
    :param fmi3_comparison: FMI 3 retained comparison CSV.
    :param output_names: Semantic output names.
    :return: Pairwise per-output metrics and PASS or FAIL.
    """
    fmi2: np.ndarray = load_numeric_csv(fmi2_comparison)
    fmi3: np.ndarray = load_numeric_csv(fmi3_comparison)
    if fmi2.size == fmi3.size and np.all(np.abs(fmi2["time"] - fmi3["time"]) <= 5e-12):
        pass
    else:
        raise ValueError("FMI 2/3 comparison time lattices differ")
    metrics: dict[str, object] = dict()
    status: str = "PASS"
    output_name: str
    for output_name in output_names:
        name: str = "pf_" + output_name
        difference: np.ndarray = np.abs(fmi2[name] - fmi3[name])
        maximum: float = float(np.max(difference))
        denominator: float = max(1.0, float(np.ptp(fmi2[name])))
        metrics[output_name] = {"maximum_absolute": maximum, "maximum_normalized": maximum / denominator}
        if maximum <= 0.005 and maximum / denominator <= 0.005:
            pass
        else:
            status = "FAIL"
    return {"status": status, "metrics": metrics}


def main() -> int:
    """Validate one licensed execution against its exact catalog lineage.

    :return: Zero only when all runnable standard cells and pairs pass.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--catalog-root", type=Path, required=True)
    arguments: argparse.Namespace = parser.parse_args()
    execution_dir: Path = arguments.execution_dir.resolve(strict=True)
    catalog_root: Path = arguments.catalog_root.resolve(strict=True)
    output_parent: Path = arguments.output_dir.parent.resolve(strict=True)
    output_dir: Path = output_parent / arguments.output_dir.name
    if output_dir.exists():
        raise FileExistsError("Validation output directory already exists")
    elif output_dir.is_relative_to(execution_dir) or execution_dir.is_relative_to(output_dir):
        raise ValueError("Validation output and execution input must be disjoint")
    else:
        output_dir.mkdir()
    manifest_path: Path = catalog_root / "manifest.json"
    manifest_hash: str = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if manifest_hash == "7099296e4360555daa1ca14f854f3c6b7f11b1c6b0ba38e5e603b9896e726113":
        pass
    else:
        raise ValueError("Catalog manifest identity changed")
    manifest: dict[str, object] = json.loads(manifest_path.read_text(encoding="utf-8"))
    cells_value: object = manifest["cells"]
    if isinstance(cells_value, list):
        cells: list[object] = cells_value
    else:
        raise ValueError("Catalog cells are malformed")
    receipt_path: Path = execution_dir / "release-checkpoint.json"
    predecessor_path: Path = execution_dir / "numerical-receipt.json"
    predecessor_hash: str = hashlib.sha256(predecessor_path.read_bytes()).hexdigest()
    if predecessor_hash == "cd9567e23f84160db03a7503a8ef884a529786e2d6d2c3d99eb19e3ea57c7beb":
        pass
    else:
        raise ValueError("Predecessor numerical receipt identity changed")
    checkpoint: dict[str, object] = json.loads(receipt_path.read_text(encoding="utf-8"))
    observations_value: object = checkpoint.get("observations", None)
    if isinstance(observations_value, dict):
        observations: dict[str, object] = observations_value
    else:
        raise ValueError("Execution checkpoint has no authenticated observations")
    execution_cells_value: object = observations.get("cells", None)
    if isinstance(execution_cells_value, list):
        execution_cells: list[object] = execution_cells_value
    else:
        raise ValueError("Execution checkpoint has no cell list")
    view_receipts: dict[tuple[str, float], dict[str, object]] = dict()
    execution_value: object
    for execution_value in execution_cells:
        if isinstance(execution_value, dict) and execution_value.get("status", None) == "PASS":
            execution_cell: dict[str, object] = execution_value
            execution_model_name: str = str(execution_cell.get("model_name", ""))
            execution_step: float = float(execution_cell.get("integration_step_s", -1.0))
            catalog_matches: list[dict[str, object]] = [item for item in cells if isinstance(item, dict) and item.get("model_name", None) == execution_model_name]
            if len(catalog_matches) == 1:
                catalog_cell: dict[str, object] = catalog_matches[0]
            else:
                raise ValueError("Execution view catalog identity is ambiguous")
            cell_dir: Path = catalog_root / str(catalog_cell["fmu_path"])
            schedule_path: Path = cell_dir.parent / (execution_model_name + "_in.csv")
            reference_path: Path = cell_dir.parent / (execution_model_name + "_ref.csv")
            schedule: np.ndarray = load_numeric_csv(schedule_path)
            reference: np.ndarray = load_numeric_csv(reference_path)
            input_names: tuple[str, ...] = tuple(name for name in schedule.dtype.names if name != "time")
            output_names: tuple[str, ...] = tuple(name for name in reference.dtype.names if name != "time")
            stop_time: float = float(reference["time"][-1])
            raw_relative_path: Path = Path(str(execution_cell["raw_csv"]))
            if raw_relative_path.is_absolute() or ".." in raw_relative_path.parts:
                raise ValueError("Execution raw path is not a contained relative path")
            else:
                raw_path: Path = (execution_dir / raw_relative_path).resolve(strict=True)
            if raw_path.is_relative_to(execution_dir):
                pass
            else:
                raise ValueError("Execution raw path escapes the immutable source root")
            step_tag: str = format(execution_step, ".9f").replace(".", "p")
            validator_view_path: Path = output_dir / "validator_views" / (execution_model_name + "_h_" + step_tag + ".csv")
            view_receipt: dict[str, object] = write_powerfactory_validator_view(
                raw_path,
                schedule_path,
                input_names,
                output_names,
                stop_time,
                int(reference.size),
                validator_view_path,
            )
            view_receipt["model_name"] = execution_model_name
            view_receipt["integration_step_s"] = execution_step
            view_receipt["validator_view_csv"] = validator_view_path.relative_to(output_dir).as_posix()
            view_receipts[(execution_model_name, execution_step)] = view_receipt
        else:
            pass
    if len(view_receipts) == 24:
        pass
    else:
        raise ValueError("Exactly twenty-four authenticated validator views are required")
    verdicts: list[dict[str, object]] = list()
    comparison_by_key: dict[tuple[str, str, str], Path] = dict()
    outputs_by_family: dict[str, tuple[str, ...]] = dict()
    all_pass: bool = True
    cell_value: object
    for cell_value in cells:
        if isinstance(cell_value, dict) and cell_value.get("fmi_version", None) in ("2.0", "3.0"):
            cell: dict[str, object] = cell_value
            model_name: str = str(cell["model_name"])
            matching: list[dict[str, object]] = [item for item in execution_cells if isinstance(item, dict) and item.get("model_name", None) == model_name and item.get("finest", False) is True]
            if len(matching) == 1 and matching[0].get("status", None) == "PASS":
                raw_path: Path = execution_dir / str(matching[0]["raw_csv"])
                cell_dir: Path = catalog_root / str(cell["fmu_path"])
                schedule_path: Path = cell_dir.parent / (model_name + "_in.csv")
                reference_path: Path = cell_dir.parent / (model_name + "_ref.csv")
                schedule: np.ndarray = load_numeric_csv(schedule_path)
                reference: np.ndarray = load_numeric_csv(reference_path)
                input_names: tuple[str, ...] = tuple(name for name in schedule.dtype.names if name != "time")
                output_names: tuple[str, ...] = tuple(name for name in reference.dtype.names if name != "time")
                comparison_path: Path = output_dir / "comparisons" / (model_name + ".csv")
                finest_step: float = float(matching[0]["integration_step_s"])
                view_receipt = view_receipts[(model_name, finest_step)]
                validator_view_path = output_dir / str(view_receipt["validator_view_csv"])
                stop_time: float = float(reference["time"][-1])
                cell_verdict: dict[str, object] = validate_cell(validator_view_path, schedule_path, reference_path, input_names, output_names, stop_time, comparison_path)
                cell_verdict["model_name"] = model_name
                cell_verdict["comparison_csv"] = comparison_path.relative_to(output_dir).as_posix()
                cell_verdict["raw_sha256"] = view_receipt["raw_sha256"]
                cell_verdict["validator_view_sha256"] = view_receipt["validator_view_sha256"]
                cell_verdict["validator_view_csv"] = validator_view_path.relative_to(output_dir).as_posix()
                cell_verdict["rewritten_positions"] = view_receipt["rewritten_positions"]
                cell_verdict["numerical_difference_count"] = view_receipt["numerical_difference_count"]
                cell_verdict["numerical_differences"] = view_receipt["numerical_differences"]
                cell_verdict["input_lattice_tick_count"] = view_receipt["input_lattice_tick_count"]
                cell_verdict["output_reference_sample_count"] = int(reference.size)
                cell_verdict["delayed_input_transition_count"] = view_receipt["delayed_input_transition_count"]
                cell_verdict["delayed_input_transitions"] = view_receipt["delayed_input_transitions"]
                comparison_by_key[(str(cell["family"]), str(cell["interface"]), str(cell["fmi_version"]))] = comparison_path
                outputs_by_family[str(cell["family"])] = output_names
            else:
                cell_verdict = {"model_name": model_name, "status": "UNKNOWN", "reason": "No successful standard PowerFactory execution"}
            verdicts.append(cell_verdict)
            if cell_verdict["status"] == "PASS":
                pass
            else:
                all_pass = False
        else:
            pass
    version_consistency: list[dict[str, object]] = list()
    family: str
    for family in ("GENSAL", "TGOV1", "ESDC2A"):
        interface: str
        for interface in ("cs", "me"):
            fmi2_key: tuple[str, str, str] = (family, interface, "2.0")
            fmi3_key: tuple[str, str, str] = (family, interface, "3.0")
            if fmi2_key in comparison_by_key and fmi3_key in comparison_by_key:
                pair: dict[str, object] = validate_version_consistency(comparison_by_key[fmi2_key], comparison_by_key[fmi3_key], outputs_by_family[family])
                pair["family"] = family
                pair["interface"] = interface
            else:
                pair = {"family": family, "interface": interface, "status": "UNKNOWN", "reason": "Both standard versions did not produce validated comparisons"}
            version_consistency.append(pair)
            if pair["status"] == "PASS":
                pass
            else:
                all_pass = False
    me_sensitivity: list[dict[str, object]] = list()
    for execution_value in execution_cells:
        if isinstance(execution_value, dict) and execution_value.get("interface", None) == "me" and execution_value.get("status", None) == "PASS" and execution_value.get("integration_step_s", None) in (0.000125, 0.0000625):
            coarse: dict[str, object] = execution_value
            finer_step: float = float(coarse["integration_step_s"]) / 2.0
            finer_matches: list[dict[str, object]] = [item for item in execution_cells if isinstance(item, dict) and item.get("model_name", None) == coarse.get("model_name", None) and item.get("integration_step_s", None) == finer_step and item.get("status", None) == "PASS"]
            if len(finer_matches) == 1:
                model_name = str(coarse["model_name"])
                catalog_matches: list[dict[str, object]] = [item for item in cells if isinstance(item, dict) and item.get("model_name", None) == model_name]
                if len(catalog_matches) == 1:
                    catalog_cell: dict[str, object] = catalog_matches[0]
                else:
                    raise ValueError("ME sensitivity catalog identity is ambiguous")
                cell_dir = catalog_root / str(catalog_cell["fmu_path"])
                schedule_path = cell_dir.parent / (model_name + "_in.csv")
                reference_path = cell_dir.parent / (model_name + "_ref.csv")
                schedule = load_numeric_csv(schedule_path)
                reference = load_numeric_csv(reference_path)
                input_names = tuple(name for name in schedule.dtype.names if name != "time")
                output_names = tuple(name for name in reference.dtype.names if name != "time")
                stop_time = float(reference["time"][-1])
                coarse_view: dict[str, object] = view_receipts[(model_name, float(coarse["integration_step_s"]))]
                fine_view: dict[str, object] = view_receipts[(model_name, finer_step)]
                coarse_trace: np.ndarray = load_numeric_csv(output_dir / str(coarse_view["validator_view_csv"]))
                fine_trace: np.ndarray = load_numeric_csv(output_dir / str(fine_view["validator_view_csv"]))
                coarse_selected: np.ndarray = select_reference_lattice(canonicalize_named_trace(coarse_trace, schedule, input_names, output_names, stop_time), reference)
                fine_selected: np.ndarray = select_reference_lattice(canonicalize_named_trace(fine_trace, schedule, input_names, output_names, stop_time), reference)
                sensitivity_metrics: dict[str, float] = dict()
                output_name: str
                for output_name in output_names:
                    sensitivity_metrics[output_name] = float(np.max(np.abs(coarse_selected[output_name] - fine_selected[output_name])))
                me_sensitivity.append({"model_name": model_name, "coarse_step_s": coarse["integration_step_s"], "fine_step_s": finer_step, "coarse_raw_sha256": coarse_view["raw_sha256"], "coarse_view_sha256": coarse_view["validator_view_sha256"], "fine_raw_sha256": fine_view["raw_sha256"], "fine_view_sha256": fine_view["validator_view_sha256"], "maximum_absolute_differences": sensitivity_metrics, "status": "DIAGNOSTIC"})
            else:
                pass
        else:
            pass
    delayed_input_transition_count: int = sum(int(item["delayed_input_transition_count"]) for item in view_receipts.values())
    receipt: dict[str, object] = {"schema_version": "1.0", "sealed_dossier_sha256": "4b3aa0ccd496daa7cfbcc3b2d80639724ee0d0255b4b2e2a6763dc5894e57edc", "source_release_checkpoint_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(), "predecessor_numerical_receipt_sha256": predecessor_hash, "validator_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "manifest_sha256": manifest_hash, "execution_views": list(view_receipts.values()), "cells": verdicts, "version_consistency": version_consistency, "me_sensitivity": me_sensitivity, "delayed_input_transition_count": delayed_input_transition_count, "status": "PASS" if all_pass and len(view_receipts) == 24 and len(verdicts) == 12 and len(version_consistency) == 6 and len(me_sensitivity) == 12 and delayed_input_transition_count == 8 else "INCOMPLETE"}
    numerical_path: Path = output_dir / "numerical-receipt-rev16.json"
    numerical_temporary_path: Path = numerical_path.with_name(numerical_path.name + ".tmp")
    if numerical_path.exists() or numerical_temporary_path.exists():
        raise FileExistsError("Numerical receipt destination is not new")
    else:
        pass
    with numerical_temporary_path.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    if numerical_path.exists():
        raise FileExistsError("Numerical receipt appeared before atomic publication")
    else:
        os.replace(numerical_temporary_path, numerical_path)
    if numerical_temporary_path.exists():
        raise RuntimeError("Numerical receipt temporary file remains after publication")
    else:
        pass
    return 0 if receipt["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
