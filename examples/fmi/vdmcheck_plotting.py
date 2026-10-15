# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Render authenticated VDMCheck completed-with-findings evidence."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import cast

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from examples.fmi.evidence_identity import (
    verify_regular_file_identity,
)


class VdmCheckFigureConfig:
    """Own the immutable VDMCheck manifest and new figure destination."""

    __slots__ = (
        "source_manifest_path",
        "source_manifest_expected_size_bytes",
        "source_manifest_expected_sha256",
        "output_directory",
    )

    source_manifest_path: Path
    source_manifest_expected_size_bytes: int
    source_manifest_expected_sha256: str
    output_directory: Path

    def __init__(
        self,
        source_manifest_path: Path,
        source_manifest_expected_size_bytes: int,
        source_manifest_expected_sha256: str,
        output_directory: Path,
    ) -> None:
        """Validate and retain one categorical figure request.

        :param source_manifest_path: Verified rev20 VDMCheck manifest.
        :param source_manifest_expected_size_bytes: Exact manifest byte count.
        :param source_manifest_expected_sha256: Exact lowercase manifest digest.
        :param output_directory: New output directory published atomically.
        :return: None.
        """

        arguments_are_valid: bool = bool(
            isinstance(source_manifest_path, Path)
            and isinstance(source_manifest_expected_size_bytes, int)
            and not isinstance(source_manifest_expected_size_bytes, bool)
            and source_manifest_expected_size_bytes > 0
            and isinstance(source_manifest_expected_sha256, str)
            and len(source_manifest_expected_sha256) == 64
            and source_manifest_expected_sha256.isalnum()
            and isinstance(output_directory, Path)
            and output_directory.is_absolute()
            and not output_directory.exists()
            and output_directory.parent.is_dir()
            and not output_directory.parent.is_symlink()
        )
        if arguments_are_valid:
            self.source_manifest_path: Path = source_manifest_path
            self.source_manifest_expected_size_bytes: int = (
                source_manifest_expected_size_bytes
            )
            self.source_manifest_expected_sha256: str = (
                source_manifest_expected_sha256
            )
            self.output_directory: Path = output_directory
        else:
            raise ValueError("VDMCheck figure configuration is invalid")


def _load_vdmcheck_figure_data(
    config: VdmCheckFigureConfig,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[int, ...],
    tuple[str, ...],
]:
    """Load the exact four-cell static-validation summary.

    :param config: Authenticated source-manifest configuration.
    :return: Row labels, FMPy labels, VDMCheck labels, finding counts and findings.
    """

    manifest_content: bytes = verify_regular_file_identity(
        path=config.source_manifest_path,
        expected_size_bytes=config.source_manifest_expected_size_bytes,
        expected_sha256=config.source_manifest_expected_sha256,
    )
    parsed_value: object = json.loads(manifest_content.decode("utf-8", errors="strict"))
    if isinstance(parsed_value, dict):
        manifest: dict[str, object] = cast(dict[str, object], parsed_value)
    else:
        raise ValueError("VDMCheck source manifest root must be an object")
    root_is_valid: bool = bool(
        manifest.get("schema_version", None) == "veragrid-fmi-vdmcheck-evidence-v1"
        and manifest.get("package_status", None) == "completed_with_findings"
    )
    if root_is_valid:
        pass
    else:
        raise ValueError("VDMCheck source manifest is not verified evidence")
    cells_value: object = manifest.get("cells", None)
    if isinstance(cells_value, list) and len(cells_value) == 4:
        cells: list[object] = cells_value
    else:
        raise ValueError("VDMCheck source must contain four validation cells")

    model_names: list[str] = [""] * 4
    fmpy_labels: list[str] = [""] * 4
    vdmcheck_labels: list[str] = [""] * 4
    finding_counts: list[int] = [0] * 4
    diagnostics: list[str] = list()
    for cell_index in range(4):
        cell_value: object = cells[cell_index]
        if isinstance(cell_value, dict):
            cell: dict[str, object] = cast(dict[str, object], cell_value)
        else:
            raise ValueError("VDMCheck cell must be an object")
        findings_value: object = cell.get("vdmcheck_findings", None)
        if isinstance(findings_value, list):
            finding_values: list[object] = findings_value
        else:
            raise ValueError("VDMCheck findings must be a list")
        finding_count: int = len(finding_values)
        cell_is_exact: bool = bool(
            cell.get("fmpy_verdict", None) == "pass"
            and cell.get("vdmcheck_verdict", None) == "fail"
            and cell.get("vdmcheck_exit_code", None) == 1
            and finding_count in (1, 2)
            and isinstance(cell.get("model_name", None), str)
            and isinstance(cell.get("fmi_version", None), str)
        )
        if cell_is_exact:
            model_name: str = cast(str, cell["model_name"])
            fmi_version: str = cast(str, cell["fmi_version"])
            model_names[cell_index] = f"FMI {fmi_version} — {model_name}"
            fmpy_labels[cell_index] = "PASS"
            if finding_count == 1:
                vdmcheck_labels[cell_index] = "COMPLETED\n1 finding"
            else:
                vdmcheck_labels[cell_index] = "COMPLETED\n2 findings"
            finding_counts[cell_index] = finding_count
        else:
            raise ValueError("VDMCheck cell verdicts differ from sealed evidence")
        for finding_value in finding_values:
            if isinstance(finding_value, str) and len(finding_value) > 0:
                diagnostics.append(finding_value)
            else:
                raise ValueError("VDMCheck diagnostic must be non-empty text")
    if sum(finding_counts) == 5 and len(diagnostics) == 5:
        pass
    else:
        raise ValueError("VDMCheck finding cardinality differs from evidence")
    return (
        tuple(model_names),
        tuple(fmpy_labels),
        tuple(vdmcheck_labels),
        tuple(finding_counts),
        tuple(diagnostics),
    )


def _render_vdmcheck_matrix(
    model_names: tuple[str, ...],
    fmpy_labels: tuple[str, ...],
    vdmcheck_labels: tuple[str, ...],
    finding_counts: tuple[int, ...],
    staging_directory: Path,
) -> tuple[Path, Path, Path]:
    """Render the four-cell validator matrix in three static formats.

    :param model_names: Ordered FMI/model row labels.
    :param fmpy_labels: Ordered FMPy verdict labels.
    :param vdmcheck_labels: Ordered completed-with-findings labels.
    :param finding_counts: Ordered native finding counts.
    :param staging_directory: Unpublished output directory.
    :return: PNG, SVG and PDF paths.
    """

    inputs_are_valid: bool = bool(
        len(model_names) == 4
        and len(fmpy_labels) == 4
        and len(vdmcheck_labels) == 4
        and len(finding_counts) == 4
        and sum(finding_counts) == 5
        and staging_directory.is_dir()
    )
    if inputs_are_valid:
        pass
    else:
        raise ValueError("VDMCheck figure inputs are invalid")
    style: dict[str, object] = dict(
        font_family="DejaVu Sans",
        font_size=9.0,
        axes_titlesize=11.0,
        axes_labelsize=9.0,
        svg_fonttype="none",
        pdf_fonttype=42,
    )
    rc_style: dict[str, object] = {
        "font.family": style["font_family"],
        "font.size": style["font_size"],
        "axes.titlesize": style["axes_titlesize"],
        "axes.labelsize": style["axes_labelsize"],
        "svg.fonttype": style["svg_fonttype"],
        "pdf.fonttype": style["pdf_fonttype"],
    }
    png_path: Path = staging_directory / "vdmcheck-validation-matrix.png"
    svg_path: Path = staging_directory / "vdmcheck-validation-matrix.svg"
    pdf_path: Path = staging_directory / "vdmcheck-validation-matrix.pdf"
    with mpl.rc_context(rc=rc_style):
        figure: Figure = plt.figure(figsize=(7.2, 4.6), constrained_layout=True)
        axes: Axes = figure.add_subplot(1, 1, 1)
        axes.set_xlim(0.0, 3.0)
        axes.set_ylim(0.0, 5.15)
        axes.axis("off")
        axes.text(1.5, 4.9, "Static FMI validation — external Reference FMUs v0.0.41", ha="center", va="center", fontsize=12.0, fontweight="bold")
        headers: tuple[str, ...] = ("FMU", "FMPy", "VDMCheck 1.1.3")
        column_centers: tuple[float, ...] = (0.75, 1.75, 2.55)
        header_index: int
        for header_index in range(3):
            axes.text(column_centers[header_index], 4.35, headers[header_index], ha="center", va="center", fontweight="bold")
        for row_index in range(4):
            row_bottom: float = 3.75 - float(row_index)
            row_fill: str = "#f3f5f7" if row_index % 2 == 0 else "#ffffff"
            axes.add_patch(Rectangle((0.05, row_bottom), 2.9, 0.85, facecolor=row_fill, edgecolor="#9aa1a8", linewidth=0.7))
            axes.text(0.75, row_bottom + 0.425, model_names[row_index], ha="center", va="center")
            axes.add_patch(Rectangle((1.35, row_bottom + 0.12), 0.8, 0.61, facecolor="#dcefe1", edgecolor="#356b45", linewidth=1.0))
            axes.text(1.75, row_bottom + 0.425, fmpy_labels[row_index], ha="center", va="center", color="#204d2d", fontweight="bold")
            axes.add_patch(Rectangle((2.15, row_bottom + 0.12), 0.8, 0.61, facecolor="#f7ecd2", edgecolor="#8a681c", linewidth=1.0))
            axes.text(2.55, row_bottom + 0.425, vdmcheck_labels[row_index], ha="center", va="center", color="#6f5316", fontweight="bold", linespacing=1.15)
        axes.text(0.05, 0.16, "Native VDMCheck verdict: FAIL for each FMU. This denotes retained standards findings, not a VeraGrid runtime failure.", ha="left", va="bottom", fontsize=8.0, color="#3d4248")
        figure.savefig(png_path, dpi=300, facecolor="white")
        figure.savefig(svg_path, facecolor="white")
        figure.savefig(pdf_path, facecolor="white")
        plt.close(figure)
    return png_path, svg_path, pdf_path


def _write_vdmcheck_figure_manifest(
    config: VdmCheckFigureConfig,
    model_names: tuple[str, ...],
    fmpy_labels: tuple[str, ...],
    vdmcheck_labels: tuple[str, ...],
    finding_counts: tuple[int, ...],
    diagnostics: tuple[str, ...],
    package_root: Path,
) -> Path:
    """Write the closed categorical-figure manifest.

    :param config: Authenticated source-manifest configuration.
    :param model_names: Ordered row labels.
    :param fmpy_labels: Ordered user-facing FMPy labels.
    :param vdmcheck_labels: Ordered user-facing VDMCheck labels.
    :param finding_counts: Ordered finding cardinalities.
    :param diagnostics: Five native VDMCheck diagnostics.
    :param package_root: Unpublished exact package root.
    :return: Staged manifest path.
    """

    source_bytes: bytes = verify_regular_file_identity(
        config.source_manifest_path,
        config.source_manifest_expected_size_bytes,
        config.source_manifest_expected_sha256,
    )
    source_value: object = json.loads(source_bytes.decode("utf-8", errors="strict"))
    if isinstance(source_value, dict):
        source_manifest: dict[str, object] = cast(dict[str, object], source_value)
    else:
        raise ValueError("VDMCheck source manifest root is invalid")
    cells_value: object = source_manifest.get("cells", None)
    if isinstance(cells_value, list) and len(cells_value) == 4:
        source_cells: list[object] = cells_value
    else:
        raise ValueError("VDMCheck source cells are unavailable")
    native_fmpy_verdicts: list[str] = [""] * 4
    native_vdmcheck_verdicts: list[str] = [""] * 4
    native_exit_codes: list[int] = [0] * 4
    for cell_index in range(4):
        cell_value: object = source_cells[cell_index]
        if isinstance(cell_value, dict):
            cell: dict[str, object] = cast(dict[str, object], cell_value)
        else:
            raise ValueError("VDMCheck source cell is invalid")
        fmpy_value: object = cell.get("fmpy_verdict", None)
        vdmcheck_value: object = cell.get("vdmcheck_verdict", None)
        exit_value: object = cell.get("vdmcheck_exit_code", None)
        if isinstance(fmpy_value, str) and isinstance(vdmcheck_value, str) and isinstance(exit_value, int):
            native_fmpy_verdicts[cell_index] = fmpy_value
            native_vdmcheck_verdicts[cell_index] = vdmcheck_value
            native_exit_codes[cell_index] = exit_value
        else:
            raise ValueError("VDMCheck native verdict fields are invalid")
    figure_names: tuple[str, ...] = (
        "vdmcheck-validation-matrix.png",
        "vdmcheck-validation-matrix.svg",
        "vdmcheck-validation-matrix.pdf",
    )
    figure_payloads: list[dict[str, object]] = [dict()] * 3
    for figure_index in range(3):
        figure_path: Path = package_root / figure_names[figure_index]
        figure_content: bytes = figure_path.read_bytes()
        figure_payloads[figure_index] = dict(
            relative_path=figure_names[figure_index],
            size_bytes=len(figure_content),
            sha256=hashlib.sha256(figure_content).hexdigest(),
        )
    manifest: dict[str, object] = dict(
        schema="veragrid.fmi-vdmcheck-figures/1",
        status="COMPLETED_WITH_FINDINGS",
        source_manifest=dict(
            path=config.source_manifest_path.as_posix(),
            size_bytes=config.source_manifest_expected_size_bytes,
            sha256=config.source_manifest_expected_sha256,
        ),
        summary=dict(
            corpus="External Reference FMUs v0.0.41",
            model_names=list(model_names),
            fmpy_labels=list(fmpy_labels),
            vdmcheck_labels=list(vdmcheck_labels),
            finding_counts=list(finding_counts),
            fmpy_pass_count=4,
            vdmcheck_completed_count=4,
            total_findings=5,
            native_fmpy_verdicts=native_fmpy_verdicts,
            native_vdmcheck_verdicts=native_vdmcheck_verdicts,
            native_vdmcheck_exit_codes=native_exit_codes,
            diagnostics=list(diagnostics),
        ),
        figures=figure_payloads,
        package_files=sorted(("manifest.json",) + figure_names),
    )
    manifest_path: Path = package_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _verify_vdmcheck_figure_package(
    package_root: Path,
    config: VdmCheckFigureConfig,
) -> None:
    """Reopen the exact four-file figure package and verify every claim.

    :param package_root: Complete unpublished package root.
    :param config: Original authenticated source configuration.
    :return: None after exact closure and geometry pass.
    """

    expected_names: set[str] = set((
        "manifest.json",
        "vdmcheck-validation-matrix.png",
        "vdmcheck-validation-matrix.svg",
        "vdmcheck-validation-matrix.pdf",
    ))
    physical_names: set[str] = set()
    physical_path: Path
    for physical_path in package_root.rglob("*"):
        if physical_path.is_file() and not physical_path.is_symlink():
            physical_names.add(physical_path.relative_to(package_root).as_posix())
        else:
            raise ValueError("VDMCheck figure package contains an invalid path")
    if physical_names == expected_names:
        pass
    else:
        raise ValueError("VDMCheck figure package membership is not closed")
    manifest_value: object = json.loads((package_root / "manifest.json").read_text(encoding="utf-8"))
    if isinstance(manifest_value, dict):
        manifest: dict[str, object] = cast(dict[str, object], manifest_value)
    else:
        raise ValueError("VDMCheck figure manifest root is invalid")
    root_keys: set[str] = set(("schema", "status", "source_manifest", "summary", "figures", "package_files"))
    root_is_exact: bool = bool(
        set(manifest.keys()) == root_keys
        and manifest.get("schema", None) == "veragrid.fmi-vdmcheck-figures/1"
        and manifest.get("status", None) == "COMPLETED_WITH_FINDINGS"
        and manifest.get("package_files", None) == sorted(expected_names)
    )
    if root_is_exact:
        pass
    else:
        raise ValueError("VDMCheck figure manifest is not closed")
    summary_value: object = manifest.get("summary", None)
    if isinstance(summary_value, dict):
        summary: dict[str, object] = cast(dict[str, object], summary_value)
    else:
        raise ValueError("VDMCheck figure summary is invalid")
    summary_is_exact: bool = bool(
        summary.get("corpus", None) == "External Reference FMUs v0.0.41"
        and summary.get("fmpy_pass_count", None) == 4
        and summary.get("vdmcheck_completed_count", None) == 4
        and summary.get("total_findings", None) == 5
        and summary.get("native_fmpy_verdicts", None) == ["pass"] * 4
        and summary.get("native_vdmcheck_verdicts", None) == ["fail"] * 4
        and summary.get("native_vdmcheck_exit_codes", None) == [1] * 4
    )
    if summary_is_exact:
        pass
    else:
        raise ValueError("VDMCheck figure summary changes native evidence")
    figures_value: object = manifest.get("figures", None)
    if isinstance(figures_value, list) and len(figures_value) == 3:
        figure_values: list[object] = figures_value
    else:
        raise ValueError("VDMCheck figure identities are incomplete")
    for figure_value in figure_values:
        if isinstance(figure_value, dict):
            figure_record: dict[str, object] = cast(dict[str, object], figure_value)
        else:
            raise ValueError("VDMCheck figure identity is invalid")
        relative_value: object = figure_record.get("relative_path", None)
        size_value: object = figure_record.get("size_bytes", None)
        sha_value: object = figure_record.get("sha256", None)
        if isinstance(relative_value, str) and isinstance(size_value, int) and isinstance(sha_value, str):
            figure_path = package_root / relative_value
            verify_regular_file_identity(figure_path, size_value, sha_value)
        else:
            raise ValueError("VDMCheck figure identity fields are invalid")
    png_content: bytes = (package_root / "vdmcheck-validation-matrix.png").read_bytes()
    png_is_exact: bool = bool(
        png_content[:8] == b"\x89PNG\r\n\x1a\n"
        and int.from_bytes(png_content[16:20], "big") == 2160
        and int.from_bytes(png_content[20:24], "big") == 1380
    )
    if png_is_exact:
        pass
    else:
        raise ValueError("VDMCheck PNG geometry differs from 2160x1380")
    svg_text: str = (package_root / "vdmcheck-validation-matrix.svg").read_text(encoding="utf-8")
    pdf_content: bytes = (package_root / "vdmcheck-validation-matrix.pdf").read_bytes()
    vectors_are_valid: bool = bool(
        'width="518.4pt" height="331.2pt"' in svg_text
        and "Static FMI validation" in svg_text
        and "COMPLETED" in svg_text
        and b"/Subtype /CIDFontType2" in pdf_content
    )
    if vectors_are_valid:
        pass
    else:
        raise ValueError("VDMCheck vector geometry, text or font is invalid")
    verify_regular_file_identity(
        config.source_manifest_path,
        config.source_manifest_expected_size_bytes,
        config.source_manifest_expected_sha256,
    )


def generate_vdmcheck_figures(config: VdmCheckFigureConfig) -> Path:
    """Generate and atomically publish the VDMCheck evidence figure package.

    :param config: Authenticated source and new output directory.
    :return: Published manifest path.
    """

    model_names: tuple[str, ...]
    fmpy_labels: tuple[str, ...]
    vdmcheck_labels: tuple[str, ...]
    finding_counts: tuple[int, ...]
    diagnostics: tuple[str, ...]
    model_names, fmpy_labels, vdmcheck_labels, finding_counts, diagnostics = (
        _load_vdmcheck_figure_data(config)
    )
    staging_directory: Path = Path(tempfile.mkdtemp(
        prefix=".vdmcheck-figures-",
        dir=str(config.output_directory.parent.resolve(strict=True)),
    )).resolve(strict=True)
    publication_succeeded: bool = False
    try:
        _render_vdmcheck_matrix(
            model_names,
            fmpy_labels,
            vdmcheck_labels,
            finding_counts,
            staging_directory,
        )
        _write_vdmcheck_figure_manifest(
            config,
            model_names,
            fmpy_labels,
            vdmcheck_labels,
            finding_counts,
            diagnostics,
            staging_directory,
        )
        _verify_vdmcheck_figure_package(staging_directory, config)
        if not config.output_directory.exists():
            os.replace(staging_directory, config.output_directory)
            publication_succeeded = True
        else:
            raise ValueError("VDMCheck figure output appeared before publication")
    finally:
        if publication_succeeded:
            pass
        else:
            if staging_directory.exists():
                shutil.rmtree(staging_directory)
            else:
                pass
    return config.output_directory / "manifest.json"
