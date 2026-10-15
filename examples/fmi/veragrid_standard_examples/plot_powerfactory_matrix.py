"""Render static exact-sample PowerFactory/FMPy comparison figures."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from examples.fmi.veragrid_standard_examples.validate_powerfactory_matrix import load_numeric_csv


def load_comparison_csv(path: Path, output_names: tuple[str, ...]) -> np.ndarray:
    """Read one retained 10 ms comparison without smoothing or resampling.

    :param path: Exact comparison CSV path.
    :param output_names: Expected semantic output names.
    :return: Finite structured comparison rows.
    """
    trace: np.ndarray = load_numeric_csv(path)
    expected: tuple[str, ...] = tuple(["time"] + [column for name in output_names for column in ("ref_" + name, "pf_" + name, "abs_" + name)])
    if trace.dtype.names == expected and trace.size >= 2:
        pass
    else:
        raise ValueError("Comparison columns differ from published semantic outputs")
    lattice: np.ndarray = np.arange(trace.size, dtype=np.float64) * 0.01
    if np.all(np.abs(trace["time"] - lattice) <= 5e-12):
        return trace
    else:
        raise ValueError("Comparison is not on the exact 10 ms lattice")


def render_family_interface(
    execution_dir: Path,
    catalog_root: Path,
    family: str,
    interface: str,
    numerical_cells: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Render physical waves and absolute residuals for available versions.

    :param execution_dir: Authenticated external execution directory.
    :param catalog_root: Exact local published catalog.
    :param family: GENSAL, TGOV1 or ESDC2A.
    :param interface: CS or ME token.
    :param numerical_cells: Validated per-cell records.
    :return: Generated figure names and SHA-256 identities.
    """
    manifest: dict[str, object] = json.loads((catalog_root / "manifest.json").read_text(encoding="utf-8"))
    catalog_rows: list[object] = manifest["cells"]
    selected: list[tuple[str, np.ndarray, tuple[str, ...]]] = list()
    event_times: list[float] = list()
    cell_value: object
    for cell_value in catalog_rows:
        if isinstance(cell_value, dict) and cell_value.get("family", None) == family and cell_value.get("interface", None) == interface and cell_value.get("fmi_version", None) in ("2.0", "3.0"):
            model_name: str = str(cell_value["model_name"])
            verdicts: list[dict[str, object]] = [item for item in numerical_cells if item.get("model_name", None) == model_name and item.get("status", None) in ("PASS", "FAIL")]
            if len(verdicts) == 1:
                reference_path: Path = catalog_root / Path(str(cell_value["fmu_path"])).parent / (model_name + "_ref.csv")
                reference: np.ndarray = load_numeric_csv(reference_path)
                if reference.dtype.names is not None:
                    output_names: tuple[str, ...] = tuple(name for name in reference.dtype.names if name != "time")
                else:
                    raise ValueError("Published reference names are absent")
                comparison_path: Path = execution_dir / str(verdicts[0]["comparison_csv"])
                content_hash: str = hashlib.sha256(comparison_path.read_bytes()).hexdigest()
                if content_hash == verdicts[0].get("comparison_sha256", None):
                    trace: np.ndarray = load_comparison_csv(comparison_path, output_names)
                else:
                    raise ValueError("Comparison CSV differs from numerical receipt")
                selected.append((str(cell_value["fmi_version"]), trace, output_names))
                if len(event_times) == 0:
                    schedule_path: Path = catalog_root / Path(str(cell_value["fmu_path"])).parent / (model_name + "_in.csv")
                    schedule: np.ndarray = load_numeric_csv(schedule_path)
                    schedule_index: int
                    for schedule_index in range(1, schedule.size):
                        if abs(float(schedule[schedule_index]["time"]) - float(schedule[schedule_index - 1]["time"])) <= 5e-12:
                            event_times.append(float(schedule[schedule_index]["time"]))
                        else:
                            pass
            else:
                pass
        else:
            pass
    if len(selected) == 0:
        return list()
    else:
        pass
    output_names = selected[0][2]
    if all(entry[2] == output_names and np.array_equal(entry[1]["time"], selected[0][1]["time"]) for entry in selected):
        pass
    else:
        raise ValueError("Physical outputs or time grids differ inside family/interface")
    style_path: Path = Path(__file__).resolve().parent / "sober-scientific.mplstyle"
    figure_dir: Path = execution_dir / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    generated: list[dict[str, object]] = list()
    with plt.style.context(style_path):
        figure, axes = plt.subplots(len(output_names), 2, sharex="col", figsize=(11.0, max(3.2, 1.8 * len(output_names) + 0.7)), squeeze=False)
        output_index: int
        for output_index in range(len(output_names)):
            name: str = output_names[output_index]
            wave_axis: plt.Axes = axes[output_index, 0]
            error_axis: plt.Axes = axes[output_index, 1]
            wave_axis.plot(selected[0][1]["time"], selected[0][1]["ref_" + name], color="#202020", linewidth=1.8, label="FMPy reference")
            error_axis.axhline(0.005, color="#666666", linestyle="--", linewidth=0.8, label="0.005 pu gate")
            series_index: int
            for series_index in range(len(selected)):
                version: str = selected[series_index][0]
                trace: np.ndarray = selected[series_index][1]
                color: str = "#24476a" if version == "2.0" else "#b0502e"
                style: str = "-" if version == "2.0" else "-."
                wave_axis.plot(trace["time"], trace["pf_" + name], color=color, linestyle=style, linewidth=1.2, label="PowerFactory FMI " + version)
                error_axis.plot(trace["time"], trace["abs_" + name], color=color, linestyle=style, linewidth=1.2, label="PowerFactory FMI " + version)
            event_time: float
            for event_time in event_times:
                wave_axis.axvline(event_time, color="#777777", linewidth=0.55, alpha=0.55)
                error_axis.axvline(event_time, color="#777777", linewidth=0.55, alpha=0.55)
            wave_axis.set_ylabel(name + " (pu)")
            error_axis.set_ylabel("|Δ " + name + "| (pu)")
            wave_axis.legend(loc="best", frameon=False, fontsize=7)
            error_axis.legend(loc="best", frameon=False, fontsize=7)
        axes[0, 0].set_title("Waveforms")
        axes[0, 1].set_title("Absolute error")
        axes[-1, 0].set_xlabel("Time (s)")
        axes[-1, 1].set_xlabel("Time (s)")
        figure.tight_layout()
        stem: str = family + "_" + interface + "_comparison"
        extension: str
        for extension in ("png", "pdf"):
            figure_path: Path = figure_dir / (stem + "." + extension)
            if figure_path.exists():
                raise FileExistsError("Refusing to overwrite existing figure evidence")
            else:
                figure.savefig(figure_path, dpi=300)
            generated.append({"name": figure_path.relative_to(execution_dir).as_posix(), "sha256": hashlib.sha256(figure_path.read_bytes()).hexdigest()})
        plt.close(figure)
    return generated


def main() -> int:
    """Render all available authenticated standard-cell comparison groups.

    :return: Zero when at least one comparable group was rendered.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution-dir", type=Path, required=True)
    parser.add_argument("--catalog-root", type=Path, required=True)
    arguments: argparse.Namespace = parser.parse_args()
    execution_dir: Path = arguments.execution_dir.resolve(strict=True)
    catalog_root: Path = arguments.catalog_root.resolve(strict=True)
    numerical_path: Path = execution_dir / "numerical-receipt-rev16.json"
    numerical: dict[str, object] = json.loads(numerical_path.read_text(encoding="utf-8"))
    cell_values: object = numerical.get("cells", None)
    if numerical.get("sealed_dossier_sha256", None) == "4b3aa0ccd496daa7cfbcc3b2d80639724ee0d0255b4b2e2a6763dc5894e57edc" and isinstance(cell_values, list):
        numerical_cells: list[dict[str, object]] = [item for item in cell_values if isinstance(item, dict)]
    else:
        raise ValueError("Numerical receipt identity or cells differ")
    figures: list[dict[str, object]] = list()
    family: str
    for family in ("GENSAL", "TGOV1", "ESDC2A"):
        interface: str
        for interface in ("cs", "me"):
            figures.extend(render_family_interface(execution_dir, catalog_root, family, interface, numerical_cells))
    receipt: dict[str, object] = {"schema_version": "1.0", "numerical_receipt_sha256": hashlib.sha256(numerical_path.read_bytes()).hexdigest(), "figures": figures, "status": "PASS" if len(figures) > 0 else "INCOMPLETE"}
    receipt_path: Path = execution_dir / "figure-receipt.json"
    with receipt_path.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return 0 if receipt["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
