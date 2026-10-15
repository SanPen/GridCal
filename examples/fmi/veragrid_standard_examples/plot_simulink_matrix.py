"""Render exact-sample trajectory and error figures for the 18-cell replay."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load_cell_trace(path: Path) -> np.ndarray:
    """Read a validated comparison CSV without resampling or smoothing.

    :param path: One same-FMU Simulink/FMPy comparison CSV.
    :return: Finite structured numeric array on the exact public lattice.
    """
    with path.open("r", encoding="utf-8", newline="") as trace_stream:
        header: list[str] = next(csv.reader(trace_stream))
    if len(header) < 4 or len(header) != len(set(header)):
        raise ValueError(f"Malformed comparison header: {path}")
    else:
        pass
    trace: np.ndarray = np.atleast_1d(np.genfromtxt(path, delimiter=",", names=True, dtype=np.float64))
    if trace.dtype.names != tuple(header) or trace.shape[0] < 2:
        raise ValueError(f"Malformed comparison trace: {path}")
    else:
        pass
    for column in header:
        if not bool(np.all(np.isfinite(trace[column]))):
            raise ValueError(f"Non-finite comparison data: {path}")
        else:
            pass
    expected_time: np.ndarray = np.arange(trace.shape[0], dtype=np.float64) * 0.01
    if not bool(np.allclose(trace["time"], expected_time, rtol=0, atol=5e-12)):
        raise ValueError(f"Comparison data are not on the public lattice: {path}")
    else:
        pass
    return trace


def render_family_interface(bundle: Path, family: str, interface: str) -> list[str]:
    """Render a complete FMI 1/2/3 family/interface pair of figure types.

    :param bundle: External execution bundle with validated comparison CSVs.
    :param family: One physical model family.
    :param interface: ``cs`` or ``me``.
    :return: Relative names of the four generated PNG/PDF figure files.
    """
    with (bundle / "execution-cells.json").open("r", encoding="utf-8") as cells_stream:
        cells: list[dict[str, object]] = json.load(cells_stream)
    family_cells: list[dict[str, object]] = [cell for cell in cells if cell["family"] == family and cell["interface"] == interface]
    if len(family_cells) != 3 or {cell["fmi_version"] for cell in family_cells} != {"1.0", "2.0", "3.0"}:
        return list()
    else:
        pass
    ordered_cells: list[dict[str, object]] = [
        next(cell for cell in family_cells if cell["fmi_version"] == version)
        for version in ("1.0", "2.0", "3.0")
    ]
    comparison_paths: list[Path] = [bundle / "comparisons" / f"{cell['model_name']}.csv" for cell in ordered_cells]
    if not all(path.is_file() for path in comparison_paths):
        return list()
    else:
        pass
    traces: list[np.ndarray] = [load_cell_trace(path) for path in comparison_paths]
    output_names: list[str] = [str(item) for item in ordered_cells[0]["output_names"]]
    expected_columns: tuple[str, ...] = tuple(["time"] + [field for output_name in output_names for field in (f"ref_{output_name}", f"sim_{output_name}", f"abs_{output_name}")])
    if not all(trace.dtype.names == expected_columns for trace in traces):
        raise ValueError(f"Output columns differ within {family}/{interface}")
    else:
        pass
    if not all(bool(np.array_equal(traces[0]["time"], trace["time"])) for trace in traces[1:]):
        raise ValueError(f"Time grids differ within {family}/{interface}")
    else:
        pass

    # Locate physical schedule events from the authenticated input CSV.
    input_path: Path = bundle / "catalog" / str(ordered_cells[0]["input_csv"])
    with input_path.open("r", encoding="utf-8", newline="") as schedule_stream:
        schedule_rows: list[dict[str, str]] = list(csv.DictReader(schedule_stream))
    event_times: list[float] = list()
    for row_index in range(1, len(schedule_rows)):
        if any(schedule_rows[row_index][input_name] != schedule_rows[row_index - 1][input_name] for input_name in ordered_cells[0]["input_names"]):
            event_times.append(float(schedule_rows[row_index]["time"]))
        else:
            pass

    figure_names: list[str] = list()
    colors: tuple[str, str, str] = ("#24476a", "#b0502e", "#278064")
    for figure_kind in ("waves", "error"):
        figure, axes = plt.subplots(len(output_names), 1, sharex=True, figsize=(10, max(3.6, 2.6 * len(output_names))), squeeze=False)
        for output_index, output_name in enumerate(output_names):
            axis: plt.Axes = axes[output_index, 0]
            if figure_kind == "waves":
                axis.plot(traces[0]["time"], traces[0][f"ref_{output_name}"], color="#202020", linewidth=2.0, label="FMPy reference")
                for cell_index, trace in enumerate(traces):
                    axis.plot(trace["time"], trace[f"sim_{output_name}"], color=colors[cell_index], alpha=0.85, label=f"Simulink FMI {ordered_cells[cell_index]['fmi_version']}")
            else:
                for cell_index, trace in enumerate(traces):
                    axis.plot(trace["time"], trace[f"abs_{output_name}"], color=colors[cell_index], label=f"FMI {ordered_cells[cell_index]['fmi_version']}")
                axis.axhline(0.005, color="#9a3939", linewidth=0.9, linestyle="--", label="Acceptance limit")
            for event_time in event_times:
                axis.axvline(event_time, color="#777777", linewidth=0.65, alpha=0.45)
            axis.set_ylabel(f"{output_name} (pu)" if figure_kind == "waves" else f"|Δ {output_name}| (pu)")
            axis.legend(loc="best", ncol=2)
        axes[-1, 0].set_xlabel("Time (s)")
        figure.suptitle(f"{family} · {interface.upper()} · FMI 1/2/3 · {'physical trajectories' if figure_kind == 'waves' else 'same-FMU absolute residual'}")
        figure.tight_layout()
        figure_stem: str = f"{family}_{interface}_{figure_kind}"
        for extension in ("png", "pdf"):
            figure_path: Path = bundle / "figures" / f"{figure_stem}.{extension}"
            figure.savefig(figure_path, dpi=300)
            figure_names.append(figure_path.name)
        plt.close(figure)
    return figure_names


def main() -> None:
    """Render only complete validated family/interface groups.

    :return: Nothing; writes a figure receipt and omits incomplete groups.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    arguments: argparse.Namespace = parser.parse_args()
    bundle: Path = arguments.bundle.resolve()
    receipt_path: Path = bundle / "simulink-figure-receipt.json"
    figure_dir: Path = bundle / "figures"
    if receipt_path.exists() or figure_dir.exists():
        raise FileExistsError("Refusing to overwrite figure evidence")
    else:
        pass
    with (bundle / "simulink-validation-receipt.json").open("r", encoding="utf-8") as validation_stream:
        validation: dict[str, object] = json.load(validation_stream)
    if validation.get("status") != "PASS" or validation.get("pass_count") != 18:
        raise ValueError("All 18 numerical cells must pass before rendering")
    else:
        pass
    plt.style.use(Path(__file__).resolve().parent / "sober-scientific.mplstyle")
    figure_dir.mkdir()
    figures: list[str] = list()
    omitted: list[str] = list()
    for family in ("GENSAL", "TGOV1", "ESDC2A"):
        for interface in ("cs", "me"):
            group_figures: list[str] = render_family_interface(bundle, family, interface)
            if len(group_figures) == 4:
                figures.extend(group_figures)
            else:
                omitted.append(f"{family}/{interface}")
    receipt: dict[str, object] = dict()
    receipt["schema"] = "veragrid.standard-simulink-figures/1"
    receipt["status"] = "PASS" if len(figures) == 24 and not omitted else "INCOMPLETE"
    receipt["figure_count"] = len(figures)
    receipt["figures"] = figures
    figure_hashes: dict[str, str] = dict()
    for figure_name in figures:
        with (figure_dir / figure_name).open("rb") as figure_stream:
            figure_hashes[figure_name] = hashlib.file_digest(figure_stream, "sha256").hexdigest()
    receipt["figure_sha256"] = figure_hashes
    receipt["omitted_groups"] = omitted
    with receipt_path.open("x", encoding="utf-8", newline="\n") as receipt_stream:
        json.dump(receipt, receipt_stream, indent=2, sort_keys=True)
        receipt_stream.write("\n")
    print(f"{receipt['status']}: {len(figures)} figures; {receipt_path}")


if __name__ == "__main__":
    main()
else:
    pass
