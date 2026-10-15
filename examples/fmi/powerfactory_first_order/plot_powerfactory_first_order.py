"""Render fixed scientific figures from an authenticated numerical PASS."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageStat


def main() -> int:
    """Render and objectively verify the six contracted figure files.

    :return: Zero only when the numerical binding and all render checks pass.
    """

    if sys.dont_write_bytecode:
        pass
    else:
        raise ValueError("Run this plotter with python -B")
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution-dir", type=Path, required=True)
    arguments: argparse.Namespace = parser.parse_args()
    execution_dir: Path = arguments.execution_dir.resolve(strict=True)
    numerical_path: Path = execution_dir / "numerical-comparison-receipt.json"
    numerical_bytes: bytes = numerical_path.read_bytes()
    numerical: dict[str, object] = json.loads(numerical_bytes.decode("utf-8"))
    source_path: Path = execution_dir / str(numerical["comparison_name"])
    if numerical.get("status", None) == "PASS" and hashlib.sha256(source_path.read_bytes()).hexdigest() == numerical.get("comparison_sha256", None):
        pass
    else:
        raise ValueError("Plot source is not bound to a numerical PASS")
    source: np.ndarray = np.genfromtxt(source_path, delimiter=",", names=True, dtype=np.float64, encoding="utf-8")
    if source.shape[0] == 1201 and np.all(np.isfinite(np.column_stack(tuple(source[name] for name in source.dtype.names or tuple())))):
        pass
    else:
        raise ValueError("Plot source is not a finite 1201-sample table")
    figure_dir: Path = execution_dir / "figures"
    if figure_dir.exists():
        raise FileExistsError("Refusing to overwrite figure evidence")
    else:
        figure_dir.mkdir(parents=True, exist_ok=False)
    style_path: Path = Path(__file__).resolve().parents[1] / "simulink_first_order" / "sober-scientific.mplstyle"
    time_values: np.ndarray = source["time"]
    events: tuple[float, ...] = (0.2, 0.5, 0.8)
    cell_ids: tuple[str, ...] = ("fmi20_cs", "fmi30_cs", "fmi20_me", "fmi30_me")
    line_contract: tuple[tuple[str, str, str], ...] = (
        ("PF FMI 2", "tab:blue", "-"),
        ("PF FMI 3", "tab:orange", "-"),
        ("FMPy FMI 2", "tab:blue", "--"),
        ("FMPy FMI 3", "tab:orange", "--"),
        ("Simulink FMI 2", "0.30", "-."),
        ("Simulink FMI 3", "0.55", ":"),
    )
    outputs: list[Path] = list()
    with plt.style.context(style_path):
        full_figure: plt.Figure
        full_axes: np.ndarray
        full_figure, full_axes = plt.subplots(3, 1, figsize=(7.2, 6.2), sharex=True)
        full_axes[0].step(time_values, source["u"], where="post", color="black", label="Input u")
        for event in events:
            for axis in full_axes:
                axis.axvline(event, color="0.75", linestyle="--", linewidth=0.6)
        full_axes[0].set_ylabel("Input u [p.u.]")
        full_axes[0].set_title("First-order response under three input events")
        full_axes[0].legend(loc="upper right")
        interface: str
        axis_index: int
        for axis_index, interface in ((1, "cs"), (2, "me")):
            first_id: str = "fmi20_" + interface
            second_id: str = "fmi30_" + interface
            columns: tuple[str, ...] = (
                "pf_" + first_id, "pf_" + second_id,
                "fmpy_" + first_id, "fmpy_" + second_id,
                "simulink_" + first_id, "simulink_" + second_id,
            )
            line_index: int
            for line_index in range(len(columns)):
                full_axes[axis_index].plot(time_values, source[columns[line_index]], color=line_contract[line_index][1], linestyle=line_contract[line_index][2], label=line_contract[line_index][0])
            oracle_name: str = "backward_euler_oracle" if interface == "cs" else "continuous_oracle"
            full_axes[axis_index].plot(time_values, source[oracle_name], color="black", linewidth=0.8, label=("Backward Euler" if interface == "cs" else "Analytic"))
            full_axes[axis_index].set_ylabel(interface.upper() + " state x [p.u.]")
            full_axes[axis_index].legend(ncols=4, loc="best", fontsize=6.4)
            full_axes[axis_index].grid(axis="y")
        full_axes[2].set_xlabel("Time [s]")
        full_png: Path = figure_dir / "powerfactory-first-order-full-trajectory.png"
        full_pdf: Path = figure_dir / "powerfactory-first-order-full-trajectory.pdf"
        # Matplotlib truncates this fractional-inch canvas two pixels below the
        # contractual 300-DPI raster.  Render PDF at the declared physical size,
        # then compensate only the raster canvas to retain exactly 2160 pixels.
        full_figure.savefig(full_pdf, bbox_inches=None)
        full_figure.set_size_inches(7.2 + 2.0 / 300.0, 6.2 + 2.0 / 300.0)
        full_figure.savefig(full_png, dpi=300, bbox_inches=None)
        plt.close(full_figure)
        outputs.extend((full_png, full_pdf))

        event_figure: plt.Figure
        event_axes: np.ndarray
        event_figure, event_axes = plt.subplots(2, 3, figsize=(7.2, 5.4), sharey="row")
        event_column: int
        for event_column in range(3):
            event_time: float = events[event_column]
            window: np.ndarray = (time_values >= event_time - 0.055) & (time_values <= event_time + 0.085)
            for axis_index, interface in ((0, "cs"), (1, "me")):
                first_id = "fmi20_" + interface
                second_id = "fmi30_" + interface
                event_axes[axis_index, event_column].plot(time_values[window], source["pf_" + first_id][window], color="tab:blue", label="PF FMI 2")
                event_axes[axis_index, event_column].plot(time_values[window], source["pf_" + second_id][window], color="tab:orange", linestyle="--", label="PF FMI 3")
                event_axes[axis_index, event_column].plot(time_values[window], source["fmpy_" + first_id][window], color="black", linewidth=0.8, linestyle="-.", label="FMPy FMI 2")
                event_axes[axis_index, event_column].plot(time_values[window], source["simulink_" + first_id][window], color="0.4", linestyle=":", label="Simulink")
                event_axes[axis_index, event_column].plot(time_values[window], source[("backward_euler_oracle" if interface == "cs" else "continuous_oracle")][window], color="black", linewidth=0.8, label="Interface oracle")
                event_axes[axis_index, event_column].axvline(event_time, color="0.65", linestyle="--", linewidth=0.7)
                event_axes[axis_index, event_column].grid(axis="y")
                if event_column == 0:
                    event_axes[axis_index, event_column].set_ylabel(interface.upper() + " state x [p.u.]")
                else:
                    pass
                if axis_index == 1:
                    event_axes[axis_index, event_column].set_xlabel("Time [s]")
                else:
                    pass
            event_axes[0, event_column].set_title("Event at " + format(event_time, ".1f") + " s")
        event_axes[0, 0].legend(ncols=2, fontsize=6.5, loc="best")
        event_png: Path = figure_dir / "powerfactory-first-order-event-windows.png"
        event_pdf: Path = figure_dir / "powerfactory-first-order-event-windows.pdf"
        event_figure.savefig(event_pdf, bbox_inches=None)
        event_figure.set_size_inches(7.2 + 2.0 / 300.0, 5.4 + 2.0 / 300.0)
        event_figure.savefig(event_png, dpi=300, bbox_inches=None)
        plt.close(event_figure)
        outputs.extend((event_png, event_pdf))

        error_figure: plt.Figure
        error_axes: np.ndarray
        error_figure, error_axes = plt.subplots(2, 2, figsize=(7.2, 7.0), sharex=True)
        panels: tuple[tuple[str, str, float, str], ...] = (
            ("cs", "fmpy", 2e-10, "PF - FMPy CS [p.u.]"),
            ("cs", "simulink", 2.1e-10, "PF - Simulink CS [p.u.]"),
            ("me", "fmpy", 1e-4, "PF - FMPy ME [p.u.]"),
            ("me", "simulink", 5.1e-5, "PF - Simulink ME [p.u.]"),
        )
        panel_index: int
        for panel_index in range(len(panels)):
            interface, peer, tolerance, label = panels[panel_index]
            axis: plt.Axes = error_axes.flat[panel_index]
            for version, color, linestyle in (("20", "tab:blue", "-"), ("30", "tab:orange", "--")):
                source_id: str = "fmi" + version + "_" + interface
                axis.plot(time_values, source["pf_" + source_id] - source[peer + "_" + source_id], color=color, linestyle=linestyle, label="FMI " + version[0])
            axis.axhline(0.0, color="black", linewidth=0.6)
            axis.axhline(tolerance, color="0.55", linestyle=":", linewidth=0.7, label="± tolerance")
            axis.axhline(-tolerance, color="0.55", linestyle=":", linewidth=0.7)
            # Bind every residual panel to its declared acceptance scale so a
            # near-zero CS series cannot trigger Matplotlib's broad singular
            # fallback and visually collapse both tolerance lines onto zero.
            axis.set_ylim(-1.1 * tolerance, 1.1 * tolerance)
            for event in events:
                axis.axvline(event, color="0.82", linestyle="--", linewidth=0.5)
            axis.set_ylabel(label)
            axis.grid(axis="y")
            axis.legend(loc="best", fontsize=7)
            if panel_index >= 2:
                axis.set_xlabel("Time [s]")
            else:
                pass
        error_axes[0, 0].set_title("Pointwise residuals on the retained 1 ms lattice")
        error_png: Path = figure_dir / "powerfactory-first-order-pointwise-errors.png"
        error_pdf: Path = figure_dir / "powerfactory-first-order-pointwise-errors.pdf"
        error_figure.savefig(error_pdf, bbox_inches=None)
        error_figure.set_size_inches(7.2 + 2.0 / 300.0, 7.0 + 2.0 / 300.0)
        error_figure.savefig(error_png, dpi=300, bbox_inches=None)
        plt.close(error_figure)
        outputs.extend((error_png, error_pdf))

    expected_sizes: dict[str, tuple[float, float]] = {
        "powerfactory-first-order-full-trajectory": (7.2, 6.2),
        "powerfactory-first-order-event-windows": (7.2, 5.4),
        "powerfactory-first-order-pointwise-errors": (7.2, 7.0),
    }
    output_records: list[dict[str, object]] = list()
    qa_records: list[dict[str, object]] = list()
    output_path: Path
    for output_path in outputs:
        expected_inches: tuple[float, float] = expected_sizes[output_path.stem]
        if output_path.suffix == ".png":
            with Image.open(output_path) as image:
                expected_pixels: tuple[int, int] = (round(expected_inches[0] * 300), round(expected_inches[1] * 300))
                dimension_pass: bool = bool(abs(image.width - expected_pixels[0]) <= 1 and abs(image.height - expected_pixels[1]) <= 1)
                extrema: list[tuple[int, int]] = list(ImageStat.Stat(image.convert("RGB")).extrema)
                content_pass: bool = bool(any(maximum > minimum for minimum, maximum in extrema))
            qa_pass: bool = bool(dimension_pass and content_pass)
        else:
            pdf_bytes: bytes = output_path.read_bytes()
            page_count: int = len(re.findall(rb"/Type /Page\b", pdf_bytes))
            media_matches: list[tuple[bytes, bytes]] = re.findall(
                rb"/MediaBox\s*\[\s*0\s+0\s+([0-9.]+)\s+([0-9.]+)\s*\]",
                pdf_bytes,
            )
            if len(media_matches) == 1:
                width_points = float(media_matches[0][0])
                height_points = float(media_matches[0][1])
            else:
                width_points = 0.0
                height_points = 0.0
            dimension_pass = bool(abs(width_points - expected_inches[0] * 72) <= 1 and abs(height_points - expected_inches[1] * 72) <= 1)
            content_pass = bool(page_count == 1 and b"/Font" in pdf_bytes and len(pdf_bytes) > 1000)
            qa_pass = bool(dimension_pass and content_pass)
        output_bytes: bytes = output_path.read_bytes()
        output_records.append({"name": output_path.name, "format": output_path.suffix[1:], "size_bytes": len(output_bytes), "sha256": hashlib.sha256(output_bytes).hexdigest()})
        qa_records.append({"name": output_path.name, "dimension_status": "PASS" if dimension_pass else "FAIL", "content_status": "PASS" if content_pass else "FAIL", "status": "PASS" if qa_pass else "FAIL"})
    qa_status: str = "PASS" if all(item["status"] == "PASS" for item in qa_records) else "FAIL"
    manifest: dict[str, object] = {"schema_version": "1.0", "campaign": "veragrid-powerfactory-first-order-fmi2-fmi3-revision-1", "source_name": "comparison/all-traces-and-oracles.csv", "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(), "numerical_receipt_sha256": hashlib.sha256(numerical_bytes).hexdigest(), "lattice": "exact retained 0.001 s grid; no interpolation or resampling", "events_s": events, "physical_sizes_in": expected_sizes, "outputs": output_records, "status": qa_status, "completed_at_utc": datetime.now(timezone.utc).isoformat()}
    qa_receipt: dict[str, object] = {"schema_version": "1.0", "checks": qa_records, "status": qa_status, "completed_at_utc": datetime.now(timezone.utc).isoformat()}
    (execution_dir / "figure-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (execution_dir / "figure-qa-receipt.json").write_text(json.dumps(qa_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": qa_status, "output_count": len(outputs)}, sort_keys=True))
    return 0 if qa_status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
