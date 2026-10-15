"""Render publication-style figures from retained first-order evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np


def main() -> None:
    """Render and hash trajectory, event, and pointwise-error figures.

    This function reads only the retained comparison table and numerical
    receipt. It does not rerun, resample, smooth, clip, or normalize any trace.

    :return: None.
    """

    if sys.dont_write_bytecode:
        pass
    else:
        raise ValueError("Run this module with python -B -m")
    argument_parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Plot the retained Simulink first-order comparison."
    )
    argument_parser.add_argument("--execution-dir", type=Path, required=True)
    arguments: argparse.Namespace = argument_parser.parse_args()
    execution_dir: Path = arguments.execution_dir.resolve(strict=True)
    repository_root: Path = Path(__file__).resolve().parents[4]
    if execution_dir.is_relative_to(repository_root):
        raise ValueError("Figure output must remain outside the repository")
    else:
        pass
    source_path: Path = execution_dir / "comparison" / "all-traces-and-oracles.csv"
    numerical_receipt_path: Path = execution_dir / "numerical-comparison-receipt.json"
    style_path: Path = execution_dir / "sober-scientific.mplstyle"
    figure_dir: Path = execution_dir / "figures"
    manifest_path: Path = execution_dir / "figure-manifest.json"
    if figure_dir.exists() or manifest_path.exists():
        raise RuntimeError("Refusing to overwrite scientific figure evidence")
    else:
        pass
    figure_dir.mkdir(parents=True, exist_ok=False)

    source: np.ndarray = np.genfromtxt(
        source_path,
        delimiter=",",
        names=True,
        dtype=np.float64,
        encoding="utf-8",
    )
    numerical_receipt: dict[str, object] = json.loads(
        numerical_receipt_path.read_text(encoding="utf-8")
    )
    source_identity_is_valid: bool = bool(
        numerical_receipt["status"] == "PASS"
        and hashlib.sha256(source_path.read_bytes()).hexdigest()
        == numerical_receipt["comparison_sha256"]
        and hashlib.sha256(style_path.read_bytes()).hexdigest()
        == numerical_receipt["recipe_assets"]["style"]["sha256"]
    )
    if source_identity_is_valid:
        pass
    else:
        raise ValueError("Plot source, numerical receipt, or style identity differs")
    time_values: np.ndarray = np.asarray(source["time"], dtype=np.float64)
    input_values: np.ndarray = np.asarray(source["u"], dtype=np.float64)
    analytic_x: np.ndarray = np.asarray(source["continuous_oracle"], dtype=np.float64)
    be_x: np.ndarray = np.asarray(source["backward_euler_oracle"], dtype=np.float64)
    cs_ids: tuple[str, ...] = ("fmi10_cs", "fmi20_cs", "fmi30_cs")
    me_ids: tuple[str, ...] = ("fmi10_me", "fmi20_me", "fmi30_me")
    labels: tuple[str, ...] = ("FMI 1", "FMI 2", "FMI 3")
    colors: tuple[str, ...] = ("#0072B2", "#D55E00", "#009E73")
    line_styles: tuple[str, ...] = ("--", ":", "-.")
    events: tuple[float, ...] = (0.2, 0.5, 0.8)

    if time_values.shape[0] != 1201:
        raise RuntimeError("Plot source does not contain the sealed 1201-point lattice")
    else:
        pass
    expected_time: np.ndarray = np.linspace(0.0, 1.2, 1201, dtype=np.float64)
    if float(np.max(np.abs(time_values - expected_time))) > 5.0e-13:
        raise RuntimeError("Plot source time lattice differs from the retained grid")
    else:
        pass

    receipt_cells: list[dict[str, object]] = list(numerical_receipt["cells"])
    receipt_by_id: dict[str, dict[str, object]] = dict()
    receipt_cell: dict[str, object]
    for receipt_cell in receipt_cells:
        receipt_by_id[str(receipt_cell["cell_id"])] = receipt_cell
    cell_id: str
    for cell_id in cs_ids:
        plotted_error: float = float(np.max(np.abs(source[cell_id] - be_x)))
        receipt_error: float = float(receipt_by_id[cell_id]["primary_max_abs_error"])
        if abs(plotted_error - receipt_error) > 1.0e-18:
            raise RuntimeError(f"Plotted CS error differs from receipt for {cell_id}")
        else:
            pass
    for cell_id in me_ids:
        plotted_error = float(np.max(np.abs(source[cell_id] - analytic_x)))
        receipt_error = float(receipt_by_id[cell_id]["primary_max_abs_error"])
        if abs(plotted_error - receipt_error) > 1.0e-18:
            raise RuntimeError(f"Plotted ME error differs from receipt for {cell_id}")
        else:
            pass

    output_paths: list[Path] = list()
    with plt.style.context(str(style_path)):
        # Figure 1: the full input and all six commercial state trajectories.
        trajectory_figure: plt.Figure
        trajectory_axes: np.ndarray
        trajectory_figure, trajectory_axes = plt.subplots(
            3,
            1,
            sharex=True,
            figsize=(7.2, 6.2),
            height_ratios=(0.72, 1.0, 1.0),
        )
        input_axis: plt.Axes = trajectory_axes[0]
        cs_axis: plt.Axes = trajectory_axes[1]
        me_axis: plt.Axes = trajectory_axes[2]
        input_axis.step(time_values, input_values, where="post", color="black", linewidth=1.35)
        input_axis.set_ylabel("Input $u$ [p.u.]")
        input_axis.set_title("Normalized first-order response across FMI versions")
        input_axis.grid(axis="y")
        version_index: int
        for version_index in range(3):
            cs_axis.plot(
                time_values,
                source[cs_ids[version_index]],
                color=colors[version_index],
                linestyle=line_styles[version_index],
                label=labels[version_index],
            )
            me_axis.plot(
                time_values,
                source[me_ids[version_index]],
                color=colors[version_index],
                linestyle=line_styles[version_index],
                label=labels[version_index],
            )
        cs_axis.plot(time_values, analytic_x, color="black", linewidth=1.0, label="Continuous oracle")
        me_axis.plot(time_values, analytic_x, color="black", linewidth=1.0, label="Continuous oracle")
        cs_axis.set_ylabel("CS state $x$ [p.u.]")
        me_axis.set_ylabel("ME state $x$ [p.u.]")
        me_axis.set_xlabel("Time [s]")
        cs_axis.grid(axis="y")
        me_axis.grid(axis="y")
        cs_axis.legend(ncols=4, loc="upper right")
        me_axis.legend(ncols=4, loc="upper right")
        event: float
        for event in events:
            for event_axis in trajectory_axes:
                event_axis.axvline(event, color="0.6", linewidth=0.7, linestyle="--")
        trajectory_png: Path = figure_dir / "first-order-full-trajectory.png"
        trajectory_pdf: Path = figure_dir / "first-order-full-trajectory.pdf"
        trajectory_figure.savefig(trajectory_png, dpi=300)
        trajectory_figure.savefig(trajectory_pdf)
        plt.close(trajectory_figure)
        output_paths.extend((trajectory_png, trajectory_pdf))

        # Figure 2: bounded views around all three discontinuities. FMI 3 is
        # representative because the retained equivalence deltas are exactly 0.
        event_figure: plt.Figure
        event_axes: np.ndarray
        event_figure, event_axes = plt.subplots(
            1,
            3,
            sharey=True,
            figsize=(7.2, 2.75),
        )
        event_index: int
        for event_index in range(3):
            event_axis: plt.Axes = event_axes[event_index]
            event = events[event_index]
            window: np.ndarray = (time_values >= event - 0.055) & (time_values <= event + 0.085)
            event_axis.plot(
                time_values[window],
                analytic_x[window],
                color="black",
                linewidth=1.25,
                label="Continuous oracle",
            )
            event_axis.plot(
                time_values[window],
                source["fmi30_cs"][window],
                color="#0072B2",
                linestyle="--",
                label="FMI 3 CS",
            )
            event_axis.plot(
                time_values[window],
                source["fmi30_me"][window],
                color="#D55E00",
                linestyle="-.",
                label="FMI 3 ME",
            )
            event_axis.axvline(event, color="0.45", linewidth=0.8, linestyle=":")
            event_axis.set_title(f"Event at {event:.1f} s")
            event_axis.set_xlabel("Time [s]")
            event_axis.grid(axis="y")
        event_axes[0].set_ylabel("State $x$ [p.u.]")
        event_axes[0].legend(loc="best")
        event_png: Path = figure_dir / "first-order-event-windows.png"
        event_pdf: Path = figure_dir / "first-order-event-windows.pdf"
        event_figure.savefig(event_png, dpi=300)
        event_figure.savefig(event_pdf)
        plt.close(event_figure)
        output_paths.extend((event_png, event_pdf))

        # Figure 3: pointwise numerical evidence. The first two panels isolate
        # implementation residual; the third shows expected CS method error.
        error_figure: plt.Figure
        error_axes: np.ndarray
        error_figure, error_axes = plt.subplots(
            3,
            1,
            sharex=True,
            figsize=(7.2, 5.8),
        )
        cs_error_axis: plt.Axes = error_axes[0]
        me_error_axis: plt.Axes = error_axes[1]
        method_error_axis: plt.Axes = error_axes[2]
        for version_index in range(3):
            cs_error_axis.plot(
                time_values,
                source[cs_ids[version_index]] - be_x,
                color=colors[version_index],
                linestyle=line_styles[version_index],
                label=labels[version_index],
            )
            me_error_axis.plot(
                time_values,
                source[me_ids[version_index]] - analytic_x,
                color=colors[version_index],
                linestyle=line_styles[version_index],
                label=labels[version_index],
            )
            method_error_axis.plot(
                time_values,
                source[cs_ids[version_index]] - analytic_x,
                color=colors[version_index],
                linestyle=line_styles[version_index],
                label=labels[version_index],
            )
        cs_error_axis.axhline(0.0, color="0.45", linewidth=0.7)
        me_error_axis.axhline(0.0, color="0.45", linewidth=0.7)
        method_error_axis.axhline(0.0, color="0.45", linewidth=0.7)
        cs_error_axis.set_ylabel("CS - BE [p.u.]")
        me_error_axis.set_ylabel("ME - analytic [p.u.]")
        method_error_axis.set_ylabel("CS - analytic [p.u.]")
        method_error_axis.set_xlabel("Time [s]")
        cs_error_axis.set_title("Pointwise residuals on the retained 1 ms lattice")
        for event in events:
            for event_axis in error_axes:
                event_axis.axvline(event, color="0.7", linewidth=0.6, linestyle="--")
        for event_axis in error_axes:
            event_axis.grid(axis="y")
        cs_error_axis.legend(ncols=3, loc="upper right")
        error_png: Path = figure_dir / "first-order-pointwise-errors.png"
        error_pdf: Path = figure_dir / "first-order-pointwise-errors.pdf"
        error_figure.savefig(error_png, dpi=300)
        error_figure.savefig(error_pdf)
        plt.close(error_figure)
        output_paths.extend((error_png, error_pdf))

    source_hash: str = hashlib.sha256(source_path.read_bytes()).hexdigest()
    numerical_receipt_hash: str = hashlib.sha256(
        numerical_receipt_path.read_bytes()
    ).hexdigest()
    style_hash: str = hashlib.sha256(style_path.read_bytes()).hexdigest()
    output_records: list[dict[str, object]] = list()
    output_path: Path
    for output_path in output_paths:
        output_records.append(
            {
                "path": str(output_path),
                "format": output_path.suffix.removeprefix("."),
                "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
                "size_bytes": int(output_path.stat().st_size),
            }
        )
    manifest: dict[str, object] = {
        "schema_version": "1.0",
        "campaign": "veragrid-maintained-simulink-first-order-fmi-matrix",
        "claim": "normalized first-order verification fixture; not a device-specific physical model",
        "source_commit": numerical_receipt["source_commit"],
        "git_tree_sha1": numerical_receipt["git_tree_sha1"],
        "source_provenance": numerical_receipt["source_provenance"],
        "recipe_assets": numerical_receipt["recipe_assets"],
        "scientific_questions": [
            "Do all FMI 1/2/3 CS/ME trajectories show the same first-order transient under three events?",
            "Is state continuity visible at each retained event boundary?",
            "Do pointwise solver-specific residuals remain within predeclared tolerances?",
        ],
        "source": {
            "path": str(source_path),
            "sha256": source_hash,
            "sample_count": 1201,
            "time_quantity": "time",
            "time_unit": "s",
            "state_quantity": "normalized state x",
            "state_unit": "p.u.",
            "input_quantity": "normalized input u",
            "input_unit": "p.u.",
            "lattice": "exact retained 0.001 s grid; no interpolation or resampling",
        },
        "numerical_receipt_sha256": numerical_receipt_hash,
        "style_sha256": style_hash,
        "events_s": list(events),
        "references": {
            "CS": "sealed backward-Euler recurrence",
            "ME": "piecewise exact continuous solution under 1 ms ZOH",
        },
        "error_definitions": ["x_CS-x_BE", "x_ME-x_analytic", "x_CS-x_analytic"],
        "tolerances": {
            "CS_vs_BE_atol": 2.0e-10,
            "ME_vs_analytic_atol": 1.0e-7,
            "CS_vs_analytic_atol": 0.004,
            "within_interface_version_atol": 1.0e-12,
            "rtol": 0.0,
        },
        "physical_width_in": 7.2,
        "formats": ["PNG 300 dpi", "PDF vector"],
        "outputs": output_records,
        "numerical_binding_status": "PASS",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS", "figure_count": 3, "output_count": 6}), flush=True)


if __name__ == "__main__":
    main()
else:
    pass
