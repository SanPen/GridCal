"""Validate exact-lattice Simulink traces against the published FMI references."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from fmpy import simulate_fmu


def load_numeric_csv(path: Path) -> np.ndarray:
    """Read a numeric trace without repairing its time axis or missing values.

    :param path: Existing CSV with unique headers and finite numeric fields.
    :return: Structured array in original row order and original precision.
    """
    with path.open("r", encoding="utf-8-sig", newline="") as csv_stream:
        reader: csv.reader = csv.reader(csv_stream)
        header: list[str] = next(reader)
    if len(header) < 2 or header[0] != "time" or len(header) != len(set(header)):
        raise ValueError(f"Invalid CSV header: {path}")
    else:
        pass
    data: np.ndarray = np.genfromtxt(path, delimiter=",", names=True, dtype=np.float64, encoding="utf-8-sig")
    data = np.atleast_1d(data)
    if data.dtype.names != tuple(header) or data.shape[0] < 2:
        raise ValueError(f"Invalid CSV columns or row count: {path}")
    else:
        pass
    for name in header:
        if not bool(np.all(np.isfinite(data[name]))):
            raise ValueError(f"Non-finite data: {path}: {name}")
        else:
            pass
    if not bool(np.all(np.diff(data["time"]) > 0)):
        raise ValueError(f"Non-monotonic or duplicate time: {path}")
    else:
        pass
    return data


def validate_cell(bundle: Path, cell: dict[str, object]) -> dict[str, object]:
    """Gate one physical trace and every separately pulsed input channel.

    :param bundle: Execution bundle containing catalog and raw Simulink data.
    :param cell: Authenticated cell identity generated from FMI XML and CSV.
    :return: Cell verdict, errors, signatures, and comparison CSV identity.
    """
    name: str = str(cell["model_name"])
    family: str = str(cell["family"])
    interface: str = str(cell["interface"])
    trace_path: Path = bundle / "traces" / f"{name}.csv"
    reference_path: Path = bundle / "catalog" / str(cell["reference_csv"])
    input_path: Path = bundle / "catalog" / str(cell["input_csv"])
    fmu_path: Path = bundle / "catalog" / str(cell["fmu_path"])
    input_names: list[str] = [str(item) for item in cell["input_names"]]
    output_names: list[str] = [str(item) for item in cell["output_names"]]
    observed: np.ndarray = load_numeric_csv(trace_path)
    reference: np.ndarray = load_numeric_csv(reference_path)
    with trace_path.open("rb") as trace_stream:
        trace_hash: str = hashlib.file_digest(trace_stream, "sha256").hexdigest()
    with fmu_path.open("rb") as fmu_stream:
        fmu_hash: str = hashlib.file_digest(fmu_stream, "sha256").hexdigest()
    if fmu_hash != cell["fmu_sha256"]:
        raise ValueError(f"FMU hash changed: {name}")
    else:
        pass
    if observed.dtype.names != tuple(["time"] + input_names + output_names):
        raise ValueError(f"Unexpected trace columns: {name}")
    else:
        pass
    if reference.dtype.names != tuple(["time"] + output_names):
        raise ValueError(f"Unexpected reference columns: {name}")
    else:
        pass
    raw_expected: np.ndarray = np.arange(observed.shape[0], dtype=np.float64) * 0.001
    public_expected: np.ndarray = np.arange(reference.shape[0], dtype=np.float64) * 0.01
    if not bool(np.allclose(observed["time"], raw_expected, rtol=0, atol=5e-12)):
        raise ValueError(f"Missing, duplicate, or off-grid raw sample: {name}")
    else:
        pass
    if not bool(np.allclose(reference["time"], public_expected, rtol=0, atol=5e-12)):
        raise ValueError(f"Malformed public reference grid: {name}")
    else:
        pass
    if observed.shape[0] != (reference.shape[0] - 1) * 10 + 1:
        raise ValueError(f"Raw/public horizon mismatch: {name}")
    else:
        pass
    public_rows: np.ndarray = np.arange(reference.shape[0], dtype=np.int64) * 10
    if not bool(np.allclose(observed["time"][public_rows], reference["time"], rtol=0, atol=5e-12)):
        raise ValueError(f"Public grid is not an exact raw subset: {name}")
    else:
        pass
    with input_path.open("r", encoding="utf-8", newline="") as schedule_stream:
        schedule_rows: list[dict[str, str]] = list(csv.DictReader(schedule_stream))
    schedule_times: np.ndarray = np.array([float(row["time"]) for row in schedule_rows], dtype=np.float64)
    if not bool(np.all(np.diff(schedule_times) >= 0)):
        raise ValueError(f"Unordered input schedule: {name}")
    else:
        pass
    source_rows: np.ndarray = np.searchsorted(schedule_times, observed["time"] + 5e-13, side="right") - 1
    if bool(np.any(source_rows < 0)):
        raise ValueError(f"Uncovered input sample: {name}")
    else:
        pass
    for input_name in input_names:
        commanded: np.ndarray = np.array([float(row[input_name]) for row in schedule_rows], dtype=np.float64)[source_rows]
        if not bool(np.allclose(observed[input_name], commanded, rtol=0, atol=1e-12)):
            raise ValueError(f"Wrong right-continuous input: {name}: {input_name}")
        else:
            pass

    comparison_path: Path = bundle / "comparisons" / f"{name}.csv"
    maximum_absolute: float = 0.0
    maximum_normalized: float = 0.0
    t0_differences: dict[str, float] = dict()
    first_sample_differences: dict[str, float] = dict()
    event_diagnostics: dict[str, dict[str, list[float]]] = dict()
    comparison_columns: list[np.ndarray] = [reference["time"]]
    comparison_header: list[str] = ["time"]
    for output_name in output_names:
        measured: np.ndarray = observed[output_name][public_rows]
        expected: np.ndarray = reference[output_name]
        error: np.ndarray = np.abs(measured - expected)
        denominator: float = max(1.0, float(np.ptp(expected)))
        maximum_absolute = max(maximum_absolute, float(np.max(error[1:])))
        maximum_normalized = max(maximum_normalized, float(np.max(error[1:] / denominator)))
        t0_differences[output_name] = float(error[0])
        first_sample_differences[output_name] = float(error[1])
        output_events: dict[str, list[float]] = dict()
        changed_times: list[float] = list()
        for schedule_index in range(1, len(schedule_rows)):
            if any(schedule_rows[schedule_index][input_name] != schedule_rows[schedule_index - 1][input_name] for input_name in input_names):
                changed_times.append(float(schedule_rows[schedule_index]["time"]))
            else:
                pass
        for event_time in sorted(set(changed_times)):
            event_index: int = int(round(event_time / 0.01))
            neighbor_indices: np.ndarray = np.array([max(0, event_index - 1), event_index, min(error.size - 1, event_index + 1)], dtype=np.int64)
            output_events[format(event_time, ".12g")] = [float(value) for value in error[neighbor_indices]]
        event_diagnostics[output_name] = output_events
        comparison_columns.extend((expected, measured, error))
        comparison_header.extend((f"ref_{output_name}", f"sim_{output_name}", f"abs_{output_name}"))
    comparison_matrix: np.ndarray = np.column_stack(comparison_columns)
    with comparison_path.open("x", encoding="utf-8", newline="") as comparison_stream:
        writer: csv.writer = csv.writer(comparison_stream)
        writer.writerow(comparison_header)
        for comparison_row in comparison_matrix:
            writer.writerow([format(float(value), ".17g") for value in comparison_row])

    # Pulse signatures are measured per input, with the unpulsed FMU subtracted.
    signature_time: np.ndarray = np.arange(601, dtype=np.float64) * 0.001
    input_dtype: np.dtype = np.dtype([("time", np.float64)] + [(input_name, np.float64) for input_name in input_names])
    baseline_input: np.ndarray = np.zeros(601, dtype=input_dtype)
    baseline_input["time"] = signature_time
    for input_name in input_names:
        baseline_input[input_name] = float(schedule_rows[0][input_name])
    fmi_type: str = "CoSimulation" if interface == "cs" else "ModelExchange"
    baseline_result: np.ndarray = simulate_fmu(
        filename=str(fmu_path), validate=True, start_time=0.0, stop_time=0.6,
        solver="Euler", step_size=0.001, output_interval=0.001,
        record_events=True, fmi_type=fmi_type, input=baseline_input, output=output_names,
    )
    signatures: dict[str, np.ndarray] = dict()
    signature_errors: dict[str, float] = dict()
    response_magnitudes: dict[str, float] = dict()
    for input_name in input_names:
        if family == "GENSAL":
            amplitude: float = 0.1 if input_name in ("IdPu_GENSAL", "IqPu_GENSAL") else 0.5
        elif family == "TGOV1":
            amplitude = 0.01 if input_name == "OmegaPu_TGOV1" else 0.05
        else:
            amplitude = 0.05 if input_name == "UsPu_ESDC2A" else 0.02
        pulse_input: np.ndarray = baseline_input.copy()
        pulse_input[input_name][(signature_time >= 0.2) & (signature_time < 0.4)] += amplitude
        pulse_result: np.ndarray = simulate_fmu(
            filename=str(fmu_path), validate=True, start_time=0.0, stop_time=0.6,
            solver="Euler", step_size=0.001, output_interval=0.001,
            record_events=True, fmi_type=fmi_type, input=pulse_input, output=output_names,
        )
        signature_path: Path = bundle / "signatures" / f"{name}__{input_name}.csv"
        signature_trace: np.ndarray = load_numeric_csv(signature_path)
        if signature_trace.dtype.names != tuple(["time"] + [f"delta_{output_name}" for output_name in output_names]):
            raise ValueError(f"Malformed signature columns: {name}: {input_name}")
        else:
            pass
        if signature_trace.shape[0] != 601 or not bool(np.allclose(signature_trace["time"], signature_time, rtol=0, atol=5e-12)):
            raise ValueError(f"Malformed signature grid: {name}: {input_name}")
        else:
            pass
        reference_signature: np.ndarray = np.column_stack([
            np.interp(signature_time, pulse_result["time"], pulse_result[output_name])
            - np.interp(signature_time, baseline_result["time"], baseline_result[output_name])
            for output_name in output_names
        ])
        measured_signature: np.ndarray = np.column_stack([signature_trace[f"delta_{output_name}"] for output_name in output_names])
        signatures[input_name] = measured_signature[::10]
        signature_errors[input_name] = float(np.max(np.abs(measured_signature[::10] - reference_signature[::10])))
        response_magnitudes[input_name] = float(np.max(np.abs(reference_signature[::10])))

    separation: dict[str, float] = dict()
    for input_name in input_names:
        other_names: list[str] = [other for other in input_names if other != input_name]
        if family == "ESDC2A" and input_name != "UsPu_ESDC2A":
            other_names = ["UsPu_ESDC2A"]
        elif family == "ESDC2A":
            other_names = [other for other in input_names if other != "UsPu_ESDC2A"]
        else:
            pass
        separation[input_name] = min(float(np.max(np.abs(signatures[input_name] - signatures[other]))) for other in other_names)
    channel_pass: bool = all(
        response_magnitudes[input_name] >= 0.01
        and signature_errors[input_name] <= 0.005
        and separation[input_name] > 0.01
        and signature_errors[input_name] <= 0.5 * separation[input_name]
        for input_name in input_names
    )
    result: dict[str, object] = dict()
    result["model_name"] = name
    result["family"] = family
    result["interface"] = interface
    result["fmi_version"] = cell["fmi_version"]
    result["trace_sha256"] = trace_hash
    result["comparison_csv"] = comparison_path.name
    result["maximum_absolute_error"] = maximum_absolute
    result["maximum_normalized_error"] = maximum_normalized
    result["raw_t0_absolute_differences"] = t0_differences
    result["first_0p01_absolute_differences"] = first_sample_differences
    result["event_neighbor_absolute_differences"] = event_diagnostics
    if family == "GENSAL":
        result["named_initial_check"] = {"output": "UqPu_GENSAL", "raw_t0_absolute_difference": t0_differences["UqPu_GENSAL"]}
    elif family == "ESDC2A":
        result["named_initial_check"] = {"output": "EfdPu_ESDC2A", "raw_t0_absolute_difference": t0_differences["EfdPu_ESDC2A"]}
    else:
        result["named_initial_check"] = None
    result["channel_response_magnitudes"] = response_magnitudes
    result["channel_matched_errors"] = signature_errors
    result["channel_nearest_separation"] = separation
    result["channel_status"] = "PASS" if channel_pass else "INCONCLUSIVE"
    result["status"] = "PASS" if maximum_absolute <= 0.005 and maximum_normalized <= 0.005 and channel_pass else "INCONCLUSIVE"
    return result


def main() -> None:
    """Validate all 18 cells, including same-interface version agreement.

    :return: Nothing; writes a fail-closed receipt outside the repository.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    arguments: argparse.Namespace = parser.parse_args()
    bundle: Path = arguments.bundle.resolve()
    receipt_path: Path = bundle / "simulink-validation-receipt.json"
    if receipt_path.exists() or (bundle / "comparisons").exists():
        raise FileExistsError("Refusing to overwrite validation evidence")
    else:
        pass
    with (bundle / "execution-cells.json").open("r", encoding="utf-8") as cells_stream:
        cells: list[dict[str, object]] = json.load(cells_stream)
    with (bundle / "simulink-run-receipt.json").open("r", encoding="utf-8") as run_stream:
        run_receipt: dict[str, object] = json.load(run_stream)
    if len(cells) != 18 or run_receipt.get("cell_count") != 18 or run_receipt.get("matlab_release") != "2025b":
        raise ValueError("Incomplete or wrong-release Simulink run")
    else:
        pass
    (bundle / "comparisons").mkdir()
    results: list[dict[str, object]] = list()
    for cell in cells:
        results.append(validate_cell(bundle, cell))
    version_errors: dict[str, float] = dict()
    for family in ("GENSAL", "TGOV1", "ESDC2A"):
        for interface in ("cs", "me"):
            family_cells: list[dict[str, object]] = [cell for cell in cells if cell["family"] == family and cell["interface"] == interface]
            if len(family_cells) != 3:
                raise ValueError("Incomplete family/interface version triple")
            else:
                pass
            baseline_cell: dict[str, object] = next(cell for cell in family_cells if cell["fmi_version"] == "2.0")
            baseline_trace: np.ndarray = load_numeric_csv(bundle / "traces" / f"{baseline_cell['model_name']}.csv")
            baseline_names: list[str] = [str(item) for item in baseline_cell["output_names"]]
            for cell in family_cells:
                trace: np.ndarray = load_numeric_csv(bundle / "traces" / f"{cell['model_name']}.csv")
                maximum: float = 0.0
                for output_name in baseline_names:
                    delta: np.ndarray = np.abs(trace[output_name][::10] - baseline_trace[output_name][::10])
                    scale: float = max(1.0, float(np.ptp(baseline_trace[output_name][::10])))
                    maximum = max(maximum, float(np.max(delta)), float(np.max(delta / scale)))
                version_errors[str(cell["model_name"])] = maximum
    passing: bool = all(result["status"] == "PASS" for result in results) and all(error <= 0.005 for error in version_errors.values())
    receipt: dict[str, object] = dict()
    receipt["schema"] = "veragrid.standard-simulink-validation/1"
    receipt["status"] = "PASS" if passing else "INCONCLUSIVE"
    receipt["cell_count"] = len(results)
    receipt["pass_count"] = sum(result["status"] == "PASS" for result in results)
    receipt["maximum_version_difference"] = max(version_errors.values())
    receipt["version_errors"] = version_errors
    receipt["cells"] = results
    with receipt_path.open("x", encoding="utf-8", newline="\n") as receipt_stream:
        json.dump(receipt, receipt_stream, indent=2, sort_keys=True)
        receipt_stream.write("\n")
    print(f"{receipt['status']}: {receipt['pass_count']}/18; {receipt_path}")
    if not passing:
        raise SystemExit(1)
    else:
        pass


if __name__ == "__main__":
    main()
else:
    pass
