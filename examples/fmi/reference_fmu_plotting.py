# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Render scientific figures from an already accepted Reference-FMU package."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import TextIO, cast

import matplotlib
import matplotlib.image as matplotlib_image
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np


class ReferenceFmuFigureConfig:
    """Own the accepted input manifest and new figure output directory."""

    __slots__ = ("manifest_path", "output_directory")

    manifest_path: Path
    output_directory: Path

    def __init__(self, manifest_path: Path, output_directory: Path) -> None:
        """Validate the explicit plotting paths.

        :param manifest_path: Accepted Reference-FMU manifest to consume.
        :param output_directory: Nonexistent final figure directory.
        :return: None.
        """

        paths_are_typed: bool = bool(
            isinstance(manifest_path, Path) and isinstance(output_directory, Path)
        )
        if paths_are_typed:
            self.manifest_path: Path = manifest_path
            self.output_directory: Path = output_directory
        else:
            raise TypeError("Reference-FMU figure paths must use pathlib.Path")


def _load_reference_fmu_figure_data(
    config: ReferenceFmuFigureConfig,
) -> tuple[
    Path,
    str,
    tuple[tuple[str, str, str, str, str, str, np.ndarray, np.ndarray], ...],
]:
    """Load hash-verified traces from one accepted immutable package.

    :param config: Explicit input and output plotting configuration.
    :return: Package root, manifest digest and detached trace records.
    """

    if isinstance(config, ReferenceFmuFigureConfig):
        pass
    else:
        raise TypeError("Reference-FMU plotting requires its typed configuration")
    manifest_candidate: Path = config.manifest_path
    manifest_is_valid: bool = bool(
        manifest_candidate.is_absolute()
        and not manifest_candidate.is_symlink()
        and manifest_candidate.is_file()
        and 0 < manifest_candidate.stat().st_size <= 2_097_152
    )
    if manifest_is_valid:
        manifest_path: Path = manifest_candidate.resolve(strict=True)
    else:
        raise ValueError("Reference-FMU manifest path is invalid")
    output_parent: Path = config.output_directory.parent
    output_is_valid: bool = bool(
        not config.output_directory.exists()
        and not output_parent.is_symlink()
        and output_parent.is_dir()
    )
    if output_is_valid:
        pass
    else:
        raise ValueError("Reference-FMU figure output must be new under a regular parent")

    manifest_bytes: bytes = manifest_path.read_bytes()
    manifest_sha256: str = hashlib.sha256(manifest_bytes).hexdigest()
    parsed_manifest: object = json.loads(manifest_bytes.decode("utf-8", errors="strict"))
    if isinstance(parsed_manifest, dict):
        manifest: dict[str, object] = cast(dict[str, object], parsed_manifest)
    else:
        raise ValueError("Reference-FMU manifest root must be an object")
    cells_value: object = manifest.get("cells", None)
    artifacts_value: object = manifest.get("artifacts", None)
    manifest_is_accepted: bool = bool(
        manifest.get("schema_name", None) == "veragrid-fmi-reference-execution-v1"
        and isinstance(cells_value, list)
        and len(cells_value) == 16
        and isinstance(artifacts_value, list)
        and len(artifacts_value) == 32
    )
    if manifest_is_accepted:
        cells: list[object] = cells_value
        artifacts: list[object] = artifacts_value
    else:
        raise ValueError("Reference-FMU manifest is not the accepted sixteen-cell schema")

    package_root: Path = manifest_path.parent.resolve(strict=True)
    traces: list[
        tuple[str, str, str, str, str, str, np.ndarray, np.ndarray]
    ] = list()
    cell_value: object
    for cell_value in cells:
        if isinstance(cell_value, dict):
            cell: dict[str, object] = cast(dict[str, object], cell_value)
        else:
            raise ValueError("Reference-FMU cell must be an object")
        relative_value: object = cell.get("raw_trace_path", None)
        status_value: object = cell.get("status", None)
        cell_is_accepted: bool = bool(
            isinstance(relative_value, str)
            and relative_value.startswith("raw/")
            and isinstance(status_value, str)
            and status_value.startswith("pass")
        )
        if cell_is_accepted:
            relative_path: str = cast(str, relative_value)
        else:
            raise ValueError("Reference-FMU plotting refuses an unaccepted cell")

        declared_size: int | None = None
        declared_sha256: str | None = None
        artifact_value: object
        for artifact_value in artifacts:
            if isinstance(artifact_value, dict):
                artifact: dict[str, object] = cast(dict[str, object], artifact_value)
                if artifact.get("path", None) == relative_path:
                    size_value: object = artifact.get("size_bytes", None)
                    digest_value: object = artifact.get("sha256", None)
                    if type(size_value) is int and isinstance(digest_value, str):
                        declared_size = size_value
                        declared_sha256 = digest_value
                    else:
                        raise ValueError("Reference-FMU artifact identity is malformed")
                else:
                    pass
            else:
                raise ValueError("Reference-FMU artifact must be an object")
        trace_candidate: Path = package_root / Path(relative_path)
        trace_is_valid: bool = bool(
            declared_size is not None
            and declared_sha256 is not None
            and not trace_candidate.is_symlink()
            and trace_candidate.is_file()
            and trace_candidate.resolve(strict=True).is_relative_to(package_root)
            and trace_candidate.stat().st_size == declared_size
            and 0 < declared_size <= 1_048_576
        )
        if trace_is_valid:
            trace_path: Path = trace_candidate.resolve(strict=True)
        else:
            raise ValueError("Reference-FMU trace path or size differs from its manifest")
        trace_bytes: bytes = trace_path.read_bytes()
        if hashlib.sha256(trace_bytes).hexdigest() == declared_sha256:
            pass
        else:
            raise ValueError("Reference-FMU trace digest differs from its manifest")

        trace_text: str = trace_bytes.decode("utf-8", errors="strict")
        rows: list[list[str]] = list(csv.reader(trace_text.splitlines()))
        if len(rows) >= 2 and len(rows[0]) == 2 and rows[0][0] == "time":
            pass
        else:
            raise ValueError("Reference-FMU trace columns are invalid")
        sample_count: int = len(rows) - 1
        time_values: np.ndarray = np.zeros(sample_count, dtype=float)
        signal_values: np.ndarray = np.zeros(sample_count, dtype=float)
        row_index: int
        for row_index in range(sample_count):
            time_values[row_index] = float(rows[row_index + 1][0])
            signal_values[row_index] = float(rows[row_index + 1][1])
        arrays_are_valid: bool = bool(
            np.all(np.isfinite(time_values))
            and np.all(np.isfinite(signal_values))
            and np.all(np.diff(time_values) >= 0.0)
        )
        if arrays_are_valid:
            pass
        else:
            raise ValueError("Reference-FMU trace contains invalid numerical values")
        traces.append(
            (
                str(cell["case_id"]),
                str(cell["model_name"]),
                str(cell["fmi_version"]),
                str(cell["interface_mode"]),
                str(cell["tool"]),
                rows[0][1],
                time_values,
                signal_values,
            )
        )
    return package_root, manifest_sha256, tuple(traces)


def _render_reference_fmu_event_figure(
    case_id: str,
    model_name: str,
    fmi_version: str,
    signal_name: str,
    traces: tuple[tuple[str, str, np.ndarray, np.ndarray], ...],
    output_directory: Path,
) -> tuple[Path, ...]:
    """Render trajectory and absolute-error views for one four-cell case.

    :param case_id: Stable Reference-FMU case identity.
    :param model_name: Human-readable FMU model name.
    :param fmi_version: FMI standard version.
    :param signal_name: Trace output variable name.
    :param traces: Interface, tool, time and value tuples for the case.
    :param output_directory: Existing owned figure staging directory.
    :return: Six generated PNG, PDF and SVG paths.
    """

    if len(traces) == 4:
        pass
    else:
        raise ValueError("Each Reference-FMU figure requires four accepted cells")
    event_times: list[float] = list()
    reference_time: np.ndarray = traces[0][2]
    reference_signal: np.ndarray = traces[0][3]
    if signal_name == "counter":
        signal_index: int
        for signal_index in range(1, reference_signal.size):
            if reference_signal[signal_index] != reference_signal[signal_index - 1]:
                event_times.append(float(reference_time[signal_index]))
            else:
                pass
    else:
        # Velocity state events are detected from negative-to-nonnegative
        # crossings in the retained raw trace rather than prescribed times.
        event_reference_time: np.ndarray | None = None
        event_reference_signal: np.ndarray | None = None
        for trace in traces:
            if trace[0] == "ModelExchange" and trace[1] == "fmpy":
                event_reference_time = trace[2]
                event_reference_signal = trace[3]
            else:
                pass
        if event_reference_time is not None and event_reference_signal is not None:
            pass
        else:
            raise ValueError("BouncingBall event plotting requires the FMPy ME trace")
        event_index: int
        for event_index in range(1, event_reference_signal.size):
            crossed_upward: bool = bool(
                event_reference_signal[event_index - 1] < 0.0
                and event_reference_signal[event_index] >= 0.0
            )
            if crossed_upward:
                candidate_time: float = float(event_reference_time[event_index])
                if len(event_times) == 0 or abs(candidate_time - event_times[-1]) > 1e-8:
                    event_times.append(candidate_time)
                else:
                    pass
            else:
                pass

    stem: str = case_id.replace(".", "_")
    generated_paths: list[Path] = list()
    with matplotlib.rc_context({
        "font.family": "DejaVu Sans",
        "font.size": 9.0,
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "grid.alpha": 0.22,
        "grid.linewidth": 0.6,
        "legend.frameon": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    }):
        trajectory_figure: Figure = Figure(figsize=(7.2, 4.3), constrained_layout=True)
        FigureCanvasAgg(trajectory_figure)
        trajectory_axis: Axes = trajectory_figure.add_subplot(1, 1, 1)
        colors: tuple[str, ...] = ("#000000", "#4477AA", "#228833", "#AA3377")
        styles: tuple[str, ...] = ("-", "--", "-.", ":")
        markers: tuple[str, ...] = ("", "o", "s", "^")
        trace_index: int
        for trace_index in range(len(traces)):
            current_trace: tuple[str, str, np.ndarray, np.ndarray] = traces[trace_index]
            trajectory_axis.plot(
                current_trace[2],
                current_trace[3],
                color=colors[trace_index],
                linestyle=styles[trace_index],
                linewidth=1.35,
                marker=markers[trace_index],
                markevery=max(1, current_trace[2].size // 18),
                markersize=2.5,
                label=f"{current_trace[1]} · {current_trace[0]}",
            )
        event_time: float
        for event_time in event_times:
            trajectory_axis.axvline(event_time, color="#666666", linewidth=0.7, alpha=0.65)
        trajectory_axis.set_title(f"{model_name} — FMI {fmi_version} event trajectories")
        trajectory_axis.set_xlabel("Time [s]")
        if signal_name == "counter":
            trajectory_axis.set_ylabel("Counter [1]")
        else:
            trajectory_axis.set_ylabel("Velocity [m s⁻¹]")
        trajectory_axis.legend(ncols=2, loc="best")
        for extension in ("png", "pdf", "svg"):
            trajectory_path: Path = output_directory / f"{stem}-trajectories.{extension}"
            if extension == "png":
                trajectory_figure.savefig(trajectory_path, dpi=300, facecolor="white")
            else:
                trajectory_figure.savefig(trajectory_path, facecolor="white")
            generated_paths.append(trajectory_path)
        trajectory_figure.clear()

        error_figure: Figure = Figure(figsize=(7.2, 3.8), constrained_layout=True)
        FigureCanvasAgg(error_figure)
        error_axis: Axes = error_figure.add_subplot(1, 1, 1)
        for interface_index, interface_mode in enumerate(("CoSimulation", "ModelExchange")):
            fmpy_time: np.ndarray | None = None
            fmpy_signal: np.ndarray | None = None
            fmusim_time: np.ndarray | None = None
            fmusim_signal: np.ndarray | None = None
            for current_trace in traces:
                if current_trace[0] == interface_mode and current_trace[1] == "fmpy":
                    fmpy_time = current_trace[2]
                    fmpy_signal = current_trace[3]
                else:
                    if current_trace[0] == interface_mode and current_trace[1] == "fmusim":
                        fmusim_time = current_trace[2]
                        fmusim_signal = current_trace[3]
                    else:
                        pass
            pair_is_aligned: bool = bool(
                fmpy_time is not None
                and fmpy_signal is not None
                and fmusim_time is not None
                and fmusim_signal is not None
                and fmpy_time.shape == fmusim_time.shape
                and np.max(np.abs(fmpy_time - fmusim_time)) <= 2e-6
            )
            if pair_is_aligned:
                absolute_error: np.ndarray = np.abs(fmpy_signal - fmusim_signal)
                error_axis.plot(
                    fmpy_time,
                    absolute_error,
                    color=colors[interface_index + 1],
                    linestyle=styles[interface_index + 1],
                    linewidth=1.2,
                    label=f"|FMPy − fmusim| · {interface_mode}",
                )
            else:
                raise ValueError("Reference-FMU pair is not aligned for error plotting")
        for event_time in event_times:
            error_axis.axvline(event_time, color="#666666", linewidth=0.7, alpha=0.65)
        error_axis.set_title(
            f"{model_name} — FMI {fmi_version} accepted paired-row differences"
        )
        error_axis.set_xlabel("Time [s]")
        error_axis.set_ylabel("Paired-row absolute difference")
        error_axis.legend(loc="best")
        for extension in ("png", "pdf", "svg"):
            error_path: Path = output_directory / f"{stem}-errors.{extension}"
            if extension == "png":
                error_figure.savefig(error_path, dpi=300, facecolor="white")
            else:
                error_figure.savefig(error_path, facecolor="white")
            generated_paths.append(error_path)
        error_figure.clear()
    return tuple(generated_paths)


def _publish_reference_fmu_figure_manifest(
    staging_directory: Path,
    source_manifest_sha256: str,
    generated_paths: tuple[Path, ...],
) -> Path:
    """Write a closed manifest for the generated scientific figures.

    :param staging_directory: Owned figure staging directory.
    :param source_manifest_sha256: Digest of the accepted input manifest.
    :param generated_paths: Exact generated figure paths.
    :return: Written figure manifest path.
    """

    artifacts: list[dict[str, object]] = list()
    generated_path: Path
    for generated_path in generated_paths:
        content: bytes = generated_path.read_bytes()
        artifacts.append(
            dict(
                path=generated_path.name,
                size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
            )
        )
    manifest: dict[str, object] = dict(
        schema="veragrid.reference-fmu-figures/1",
        status="CANDIDATE_EVIDENCE",
        source_manifest_sha256=source_manifest_sha256,
        case_count=4,
        figure_artifact_count=len(artifacts),
        artifacts=artifacts,
    )
    manifest_path: Path = staging_directory / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest_path


def _verify_reference_fmu_figure_package(
    staging_directory: Path,
    manifest_path: Path,
) -> None:
    """Verify closed artifact membership, sizes, hashes and raster resolution.

    :param staging_directory: Complete figure staging directory.
    :param manifest_path: Figure manifest written last.
    :return: None.
    """

    parsed: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    if isinstance(parsed, dict):
        manifest: dict[str, object] = cast(dict[str, object], parsed)
    else:
        raise RuntimeError("Reference-FMU figure manifest root is invalid")
    artifacts_value: object = manifest.get("artifacts", None)
    if isinstance(artifacts_value, list) and len(artifacts_value) == 24:
        artifacts: list[object] = artifacts_value
    else:
        raise RuntimeError("Reference-FMU figure package must contain 24 figures")
    declared_names: set[str] = set()
    artifact_value: object
    for artifact_value in artifacts:
        if isinstance(artifact_value, dict):
            artifact: dict[str, object] = cast(dict[str, object], artifact_value)
        else:
            raise RuntimeError("Reference-FMU figure artifact is invalid")
        artifact_name: str = str(artifact.get("path", ""))
        artifact_path: Path = staging_directory / artifact_name
        content: bytes = artifact_path.read_bytes()
        identity_matches: bool = bool(
            not artifact_path.is_symlink()
            and artifact_path.is_file()
            and artifact_path.resolve(strict=True).is_relative_to(staging_directory)
            and artifact.get("size_bytes", None) == len(content)
            and artifact.get("sha256", None) == hashlib.sha256(content).hexdigest()
        )
        if identity_matches:
            declared_names.add(artifact_name)
        else:
            raise RuntimeError("Reference-FMU figure artifact identity differs")
        artifact_suffix: str = artifact_path.suffix
        is_trajectory: bool = "-trajectories." in artifact_name
        expected_height_pixels: int
        expected_height_points: str
        if is_trajectory:
            expected_height_pixels = 1290
            expected_height_points = "309.6"
        else:
            expected_height_pixels = 1140
            expected_height_points = "273.6"
        if artifact_suffix == ".png":
            image_array: np.ndarray = matplotlib_image.imread(artifact_path)
            raster_matches: bool = bool(
                image_array.shape[0] == expected_height_pixels
                and image_array.shape[1] == 2160
            )
            if raster_matches:
                pass
            else:
                raise RuntimeError("Reference-FMU PNG geometry is invalid")
        elif artifact_suffix == ".svg":
            svg_text: str = artifact_path.read_text(encoding="utf-8")
            svg_matches: bool = bool(
                'width="518.4pt"' in svg_text
                and f'height="{expected_height_points}pt"' in svg_text
                and "<text" in svg_text
            )
            if svg_matches:
                pass
            else:
                raise RuntimeError("Reference-FMU SVG geometry or text is invalid")
        elif artifact_suffix == ".pdf":
            pdf_width_pattern: bytes = b"518.4"
            pdf_height_pattern: bytes = expected_height_points.encode("ascii")
            pdf_matches: bool = bool(
                b"/MediaBox" in content
                and pdf_width_pattern in content
                and pdf_height_pattern in content
                and (b"/FontFile2" in content or b"/CIDFontType2" in content)
            )
            if pdf_matches:
                pass
            else:
                raise RuntimeError("Reference-FMU PDF geometry or fonts are invalid")
        else:
            raise RuntimeError("Reference-FMU figure suffix is unsupported")
    physical_names: set[str] = set()
    physical_path: Path
    for physical_path in staging_directory.iterdir():
        if physical_path.is_file():
            physical_names.add(physical_path.name)
        else:
            raise RuntimeError("Reference-FMU figure package contains a directory")
    if physical_names == declared_names | {"manifest.json"}:
        pass
    else:
        raise RuntimeError("Reference-FMU figure package membership is not closed")


def generate_reference_fmu_figures(config: ReferenceFmuFigureConfig) -> Path:
    """Generate four event-aware figure sets from accepted Reference-FMU data.

    :param config: Explicit immutable input and new output directory.
    :return: Published figure-package manifest path.
    """

    package_root: Path
    source_manifest_sha256: str
    trace_records: tuple[
        tuple[str, str, str, str, str, str, np.ndarray, np.ndarray], ...
    ]
    package_root, source_manifest_sha256, trace_records = (
        _load_reference_fmu_figure_data(config)
    )
    if package_root == config.manifest_path.resolve(strict=True).parent:
        pass
    else:
        raise RuntimeError("Reference-FMU package root changed during loading")
    staging_directory: Path = Path(
        tempfile.mkdtemp(
            prefix=".reference-fmu-figures-",
            dir=str(config.output_directory.parent.resolve(strict=True)),
        )
    ).resolve(strict=True)
    publication_succeeded: bool = False
    try:
        case_ids: list[str] = list()
        record: tuple[str, str, str, str, str, str, np.ndarray, np.ndarray]
        for record in trace_records:
            if record[0] not in case_ids:
                case_ids.append(record[0])
            else:
                pass
        if len(case_ids) == 4:
            pass
        else:
            raise RuntimeError("Reference-FMU package must expose four cases")
        generated_paths: list[Path] = list()
        case_id: str
        for case_id in case_ids:
            case_traces: list[tuple[str, str, np.ndarray, np.ndarray]] = list()
            model_name: str = ""
            fmi_version: str = ""
            signal_name: str = ""
            for record in trace_records:
                if record[0] == case_id:
                    model_name = record[1]
                    fmi_version = record[2]
                    signal_name = record[5]
                    case_traces.append((record[3], record[4], record[6], record[7]))
                else:
                    pass
            figure_paths: tuple[Path, ...] = _render_reference_fmu_event_figure(
                case_id=case_id,
                model_name=model_name,
                fmi_version=fmi_version,
                signal_name=signal_name,
                traces=tuple(case_traces),
                output_directory=staging_directory,
            )
            generated_paths.extend(figure_paths)
        manifest_path: Path = _publish_reference_fmu_figure_manifest(
            staging_directory=staging_directory,
            source_manifest_sha256=source_manifest_sha256,
            generated_paths=tuple(generated_paths),
        )
        _verify_reference_fmu_figure_package(staging_directory, manifest_path)
        if not config.output_directory.exists():
            os.replace(staging_directory, config.output_directory)
            publication_succeeded = True
        else:
            raise RuntimeError("Reference-FMU figure output appeared before publication")
    finally:
        if publication_succeeded:
            pass
        else:
            if staging_directory.exists():
                shutil.rmtree(staging_directory)
            else:
                pass
    return config.output_directory / "manifest.json"
