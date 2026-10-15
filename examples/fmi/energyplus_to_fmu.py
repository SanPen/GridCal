# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Audit the declared EnergyPlusToFMU FMI 1 compatibility export."""
from __future__ import annotations

import csv
from collections.abc import Iterator
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import TextIO
import xml.etree.ElementTree as ElementTree
import zipfile

import matplotlib
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from fmpy.validation import validate_fmu

from examples.fmi.evidence_identity import (
    path_is_link_or_reparse_point,
    read_regular_tree_identity,
    verify_regular_file_identity,
)


class EnergyPlusToFmuCellStatus(str, Enum):
    """Possible outcomes of an EnergyPlusToFMU evidence cell."""

    PASS = "PASS"
    FAIL = "FAIL"
    COMPLETED_WITH_FINDINGS = "COMPLETED_WITH_FINDINGS"


class EnergyPlusToFmuComparisonConfig:
    """Own authenticated inputs and process limits for one comparison."""

    __slots__ = (
        "output_directory", "source_branch", "source_revision", "source_tree_sha256",
        "upstream_commit", "upstream_tree", "python_path", "python_size_bytes",
        "exporter_source_file_count", "exporter_source_total_size_bytes",
        "exporter_source_tree_sha256", "compatibility_patch_path",
        "compatibility_patch_size_bytes", "compatibility_patch_sha256",
        "python_sha256", "fmpy_root", "fmpy_file_count",
        "fmpy_total_size_bytes", "fmpy_tree_sha256", "worker_path",
        "worker_size_bytes", "worker_sha256",
        "exporter_path", "exporter_size_bytes", "exporter_sha256", "idd_path",
        "idd_size_bytes", "idd_sha256", "idf_path", "idf_size_bytes", "idf_sha256",
        "epw_path", "epw_size_bytes", "epw_sha256",
        "cmd_path", "cmd_size_bytes", "cmd_sha256", "vsdevcmd_path",
        "vsdevcmd_size_bytes", "vsdevcmd_sha256", "compiler_path",
        "compiler_size_bytes", "compiler_sha256", "linker_path",
        "linker_size_bytes", "linker_sha256", "energyplus_path",
        "energyplus_size_bytes", "energyplus_sha256", "temporary_directory",
        "energyplus_file_count", "energyplus_total_size_bytes",
        "energyplus_tree_sha256", "communication_step_seconds",
        "steps_per_level", "input_levels", "process_timeout_seconds",
        "stream_limit_bytes",
    )

    def __init__(
        self,
        output_directory: Path,
        source_branch: str,
        source_revision: str,
        source_tree_sha256: str,
        upstream_commit: str,
        upstream_tree: str,
        exporter_source_file_count: int,
        exporter_source_total_size_bytes: int,
        exporter_source_tree_sha256: str,
        compatibility_patch_path: Path,
        compatibility_patch_size_bytes: int,
        compatibility_patch_sha256: str,
        python_path: Path,
        python_size_bytes: int,
        python_sha256: str,
        fmpy_root: Path,
        fmpy_file_count: int,
        fmpy_total_size_bytes: int,
        fmpy_tree_sha256: str,
        worker_path: Path,
        worker_size_bytes: int,
        worker_sha256: str,
        exporter_path: Path,
        exporter_size_bytes: int,
        exporter_sha256: str,
        idd_path: Path,
        idd_size_bytes: int,
        idd_sha256: str,
        idf_path: Path,
        idf_size_bytes: int,
        idf_sha256: str,
        epw_path: Path,
        epw_size_bytes: int,
        epw_sha256: str,
        cmd_path: Path,
        cmd_size_bytes: int,
        cmd_sha256: str,
        vsdevcmd_path: Path,
        vsdevcmd_size_bytes: int,
        vsdevcmd_sha256: str,
        compiler_path: Path,
        compiler_size_bytes: int,
        compiler_sha256: str,
        linker_path: Path,
        linker_size_bytes: int,
        linker_sha256: str,
        energyplus_path: Path,
        energyplus_size_bytes: int,
        energyplus_sha256: str,
        energyplus_file_count: int,
        energyplus_total_size_bytes: int,
        energyplus_tree_sha256: str,
        communication_step_seconds: float,
        steps_per_level: int,
        input_levels: tuple[float, ...],
        temporary_directory: Path,
        process_timeout_seconds: float,
        stream_limit_bytes: int,
    ) -> None:
        """Initialize one fully explicit comparison request.

        :param output_directory: Nonexistent final package directory.
        :param source_branch: VeraGrid branch represented by the evidence.
        :param source_revision: VeraGrid commit represented by the evidence.
        :param source_tree_sha256: Candidate source-tree digest.
        :param upstream_commit: Declared EnergyPlusToFMU v3.1 provenance commit.
        :param upstream_tree: Declared EnergyPlusToFMU provenance Git tree.
        :param exporter_source_file_count: Patched exporter source file count.
        :param exporter_source_total_size_bytes: Patched exporter source byte count.
        :param exporter_source_tree_sha256: Patched exporter source tree digest.
        :param compatibility_patch_path: Declarative patch applied to upstream v3.1.
        :param compatibility_patch_size_bytes: Expected compatibility-patch size.
        :param compatibility_patch_sha256: Expected compatibility-patch digest.
        :param python_path: Python interpreter used for export and workers.
        :param python_size_bytes: Expected Python executable size.
        :param python_sha256: Expected Python executable digest.
        :param fmpy_root: Exact FMPy package root used for static and runtime checks.
        :param fmpy_file_count: Expected FMPy regular-file count.
        :param fmpy_total_size_bytes: Expected aggregate FMPy byte count.
        :param fmpy_tree_sha256: Expected FMPy package-tree digest.
        :param worker_path: Isolated worker module.
        :param worker_size_bytes: Expected worker size.
        :param worker_sha256: Expected worker digest.
        :param exporter_path: Authenticated compatibility export script.
        :param exporter_size_bytes: Expected exporter size.
        :param exporter_sha256: Expected exporter digest.
        :param idd_path: EnergyPlus 9.4 input dictionary.
        :param idd_size_bytes: Expected IDD size.
        :param idd_sha256: Expected IDD digest.
        :param idf_path: Official Schedule example input.
        :param idf_size_bytes: Expected IDF size.
        :param idf_sha256: Expected IDF digest.
        :param epw_path: Official Chicago weather data required by ``RunPeriod``.
        :param epw_size_bytes: Expected EPW size.
        :param epw_sha256: Expected EPW digest.
        :param cmd_path: Absolute Windows command processor.
        :param cmd_size_bytes: Expected command processor size.
        :param cmd_sha256: Expected command processor digest.
        :param vsdevcmd_path: Visual Studio environment script.
        :param vsdevcmd_size_bytes: Expected script size.
        :param vsdevcmd_sha256: Expected script digest.
        :param compiler_path: Exact compiler selected by VsDevCmd.
        :param compiler_size_bytes: Expected compiler executable size.
        :param compiler_sha256: Expected compiler executable digest.
        :param linker_path: Exact linker selected by VsDevCmd.
        :param linker_size_bytes: Expected linker executable size.
        :param linker_sha256: Expected linker executable digest.
        :param energyplus_path: Exact EnergyPlus 9.4 executable.
        :param energyplus_size_bytes: Expected EnergyPlus executable size.
        :param energyplus_sha256: Expected EnergyPlus executable digest.
        :param energyplus_file_count: Expected installed runtime file count.
        :param energyplus_total_size_bytes: Expected installed runtime byte count.
        :param energyplus_tree_sha256: Expected installed runtime tree digest.
        :param communication_step_seconds: FMI communication interval.
        :param steps_per_level: Number of intervals per heat-flow plateau.
        :param input_levels: Ordered heat-flow plateaus applied to the FMU.
        :param temporary_directory: Existing caller-owned scratch root.
        :param process_timeout_seconds: Hard deadline for each worker.
        :param stream_limit_bytes: Maximum retained bytes per stream.
        :return: None.
        """

        self.output_directory = output_directory
        self.source_branch = source_branch
        self.source_revision = source_revision
        self.source_tree_sha256 = source_tree_sha256
        self.upstream_commit = upstream_commit
        self.upstream_tree = upstream_tree
        self.exporter_source_file_count = exporter_source_file_count
        self.exporter_source_total_size_bytes = exporter_source_total_size_bytes
        self.exporter_source_tree_sha256 = exporter_source_tree_sha256
        self.compatibility_patch_path = compatibility_patch_path
        self.compatibility_patch_size_bytes = compatibility_patch_size_bytes
        self.compatibility_patch_sha256 = compatibility_patch_sha256
        self.python_path = python_path
        self.python_size_bytes = python_size_bytes
        self.python_sha256 = python_sha256
        self.fmpy_root: Path = fmpy_root
        self.fmpy_file_count: int = fmpy_file_count
        self.fmpy_total_size_bytes: int = fmpy_total_size_bytes
        self.fmpy_tree_sha256: str = fmpy_tree_sha256
        self.worker_path = worker_path
        self.worker_size_bytes = worker_size_bytes
        self.worker_sha256 = worker_sha256
        self.exporter_path = exporter_path
        self.exporter_size_bytes = exporter_size_bytes
        self.exporter_sha256 = exporter_sha256
        self.idd_path = idd_path
        self.idd_size_bytes = idd_size_bytes
        self.idd_sha256 = idd_sha256
        self.idf_path = idf_path
        self.idf_size_bytes = idf_size_bytes
        self.idf_sha256 = idf_sha256
        self.epw_path = epw_path
        self.epw_size_bytes = epw_size_bytes
        self.epw_sha256 = epw_sha256
        self.cmd_path = cmd_path
        self.cmd_size_bytes = cmd_size_bytes
        self.cmd_sha256 = cmd_sha256
        self.vsdevcmd_path = vsdevcmd_path
        self.vsdevcmd_size_bytes = vsdevcmd_size_bytes
        self.vsdevcmd_sha256 = vsdevcmd_sha256
        self.compiler_path: Path = compiler_path
        self.compiler_size_bytes: int = compiler_size_bytes
        self.compiler_sha256: str = compiler_sha256
        self.linker_path: Path = linker_path
        self.linker_size_bytes: int = linker_size_bytes
        self.linker_sha256: str = linker_sha256
        self.energyplus_path = energyplus_path
        self.energyplus_size_bytes = energyplus_size_bytes
        self.energyplus_sha256 = energyplus_sha256
        self.energyplus_file_count: int = energyplus_file_count
        self.energyplus_total_size_bytes: int = energyplus_total_size_bytes
        self.energyplus_tree_sha256: str = energyplus_tree_sha256
        self.communication_step_seconds: float = communication_step_seconds
        self.steps_per_level: int = steps_per_level
        self.input_levels: tuple[float, ...] = input_levels
        self.temporary_directory = temporary_directory
        self.process_timeout_seconds = process_timeout_seconds
        self.stream_limit_bytes = stream_limit_bytes


def _validate_energyplus_to_fmu_config(config: EnergyPlusToFmuComparisonConfig) -> None:
    """Fail closed before native tools run or evidence is published.

    :param config: Comparison configuration to authenticate.
    :return: None.
    """

    text_is_valid: bool = bool(
        config.source_branch == "devel_dynamics_rebuild"
        and re.fullmatch(r"[0-9a-f]{40}", config.source_revision) is not None
        and re.fullmatch(r"[0-9a-f]{64}", config.source_tree_sha256) is not None
        and config.upstream_commit == "eaa2c1f46ebf8848c7ce7f12e0d3f27b634668de"
        and config.upstream_tree == "0b5154ba50e8bdca16141ffaab7c189586ecf4a7"
        and config.exporter_source_file_count == 405
        and config.exporter_source_total_size_bytes == 21_726_876
        and config.exporter_source_tree_sha256
        == "b671f197c21613630c5aa479e96094dc950288dddc8a841aef1ea5995f56a58f"
        and config.compatibility_patch_size_bytes == 2_490
        and config.compatibility_patch_sha256
        == "7ee75dd188f46cae7d2ddd7673b79158023cd341af36e470ac6b34002a75d368"
        and config.fmpy_file_count == 204
        and config.fmpy_total_size_bytes == 19_885_303
        and config.fmpy_tree_sha256 == "06a563c79ff419e04fe045c70bf6cc12fa2e0a6804236ff4f2f248a71f7cbec9"
        and config.energyplus_file_count == 3_304
        and config.energyplus_total_size_bytes == 669_590_726
        and config.energyplus_tree_sha256
        == "87847ac803c88bea5d8195441a06ac612a8d1eacd870856779e9860d36bc25ba"
        and config.communication_step_seconds == 900.0
        and config.steps_per_level == 24
        and config.input_levels == (0.0, 1_000.0, -500.0, 500.0)
        and 0.0 < config.process_timeout_seconds <= 300.0
        and config.stream_limit_bytes == 1_048_576
        and config.temporary_directory.exists()
        and config.temporary_directory.is_dir()
    )
    if text_is_valid:
        pass
    else:
        raise ValueError("EnergyPlusToFMU comparison configuration is invalid")

    # The clean Git export authenticates every helper imported by the legacy
    # entry point, not only EnergyPlusToFMU.py itself.
    upstream_root: Path = config.exporter_path.parents[1]
    upstream_identity: tuple[int, int, str] = read_regular_tree_identity(upstream_root)
    expected_exporter_source_identity: tuple[int, int, str] = (
        config.exporter_source_file_count,
        config.exporter_source_total_size_bytes,
        config.exporter_source_tree_sha256,
    )
    if upstream_identity == expected_exporter_source_identity:
        pass
    else:
        raise ValueError("EnergyPlusToFMU source tree identity does not match v3.1")

    fmpy_identity: tuple[int, int, str] = read_regular_tree_identity(
        config.fmpy_root
    )
    expected_fmpy_identity: tuple[int, int, str] = (
        config.fmpy_file_count,
        config.fmpy_total_size_bytes,
        config.fmpy_tree_sha256,
    )
    if fmpy_identity == expected_fmpy_identity:
        pass
    else:
        raise ValueError("FMPy package identity does not match 0.3.31")

    energyplus_identity: tuple[int, int, str] = read_regular_tree_identity(
        config.energyplus_path.parent,
        excluded_directory_names=("__pycache__",),
    )
    expected_energyplus_identity: tuple[int, int, str] = (
        config.energyplus_file_count,
        config.energyplus_total_size_bytes,
        config.energyplus_tree_sha256,
    )
    if energyplus_identity == expected_energyplus_identity:
        pass
    else:
        raise ValueError("EnergyPlus installation tree does not match 9.4.0")

    # Every executable or source file is content-bound before the first child.
    identity_rows: tuple[tuple[Path, int, str], ...] = (
        (config.python_path, config.python_size_bytes, config.python_sha256),
        (
            config.compatibility_patch_path,
            config.compatibility_patch_size_bytes,
            config.compatibility_patch_sha256,
        ),
        (config.worker_path, config.worker_size_bytes, config.worker_sha256),
        (config.exporter_path, config.exporter_size_bytes, config.exporter_sha256),
        (config.idd_path, config.idd_size_bytes, config.idd_sha256),
        (config.idf_path, config.idf_size_bytes, config.idf_sha256),
        (config.epw_path, config.epw_size_bytes, config.epw_sha256),
        (config.cmd_path, config.cmd_size_bytes, config.cmd_sha256),
        (config.vsdevcmd_path, config.vsdevcmd_size_bytes, config.vsdevcmd_sha256),
        (config.compiler_path, config.compiler_size_bytes, config.compiler_sha256),
        (config.linker_path, config.linker_size_bytes, config.linker_sha256),
        (config.energyplus_path, config.energyplus_size_bytes, config.energyplus_sha256),
    )
    for identity_path, identity_size, identity_sha256 in identity_rows:
        verify_regular_file_identity(identity_path, identity_size, identity_sha256)


def _run_energyplus_to_fmu_worker(
    config: EnergyPlusToFmuComparisonConfig,
    mode: str,
    working_directory: Path,
    result_path: Path,
    fmu_path: Path,
    trace_path: Path,
) -> tuple[dict[str, object], str, str]:
    """Run one bounded worker and retain its complete streams.

    :param config: Authenticated comparison configuration.
    :param mode: Exact worker operation.
    :param working_directory: Private operation directory.
    :param result_path: Structured result destination.
    :param fmu_path: FMU path used by the selected operation.
    :param trace_path: Runtime trace destination.
    :return: Parsed result, stdout and stderr.
    """

    # Authenticate every external input immediately before the child starts.
    _validate_energyplus_to_fmu_config(config)
    worker_environment: dict[str, str] = dict(
        SystemRoot=str(config.cmd_path.parents[1]),
        TEMP=str(config.temporary_directory),
        TMP=str(config.temporary_directory),
        PROCESSOR_ARCHITECTURE="AMD64",
        SystemDrive=str(config.cmd_path.anchor).rstrip("\\"),
        PATH=str(config.cmd_path.parent) + os.pathsep + str(config.energyplus_path.parent),
    )
    command: list[str] = [
        str(config.python_path), "-B", str(config.worker_path), "--mode", mode,
        "--result-path", str(result_path), "--working-directory", str(working_directory),
        "--cmd-path", str(config.cmd_path), "--vsdevcmd-path", str(config.vsdevcmd_path),
        "--compiler-path", str(config.compiler_path),
        "--compiler-size-bytes", str(config.compiler_size_bytes),
        "--compiler-sha256", config.compiler_sha256,
        "--linker-path", str(config.linker_path),
        "--linker-size-bytes", str(config.linker_size_bytes),
        "--linker-sha256", config.linker_sha256,
        "--python-path", str(config.python_path), "--exporter-path", str(config.exporter_path),
        "--idd-path", str(config.idd_path), "--idf-path", str(config.idf_path),
        "--epw-path", str(config.epw_path),
        "--fmu-path", str(fmu_path), "--trace-path", str(trace_path),
        "--energyplus-directory", str(config.energyplus_path.parent),
        "--communication-step-seconds", str(config.communication_step_seconds),
        "--steps-per-level", str(config.steps_per_level),
        "--temporary-directory", str(config.temporary_directory),
        "--process-timeout-seconds", str(config.process_timeout_seconds),
        "--stream-limit-bytes", str(config.stream_limit_bytes),
    ]
    input_level: float
    for input_level in config.input_levels:
        command.extend(("--input-level", str(input_level)))
    process: subprocess.CompletedProcess[str] = subprocess.run(
        command, cwd=working_directory, env=worker_environment, shell=False,
        capture_output=True, text=True, timeout=config.process_timeout_seconds, check=False,
    )
    # Reject toolchain or input drift that occurred while the child was active.
    _validate_energyplus_to_fmu_config(config)
    streams_are_valid: bool = bool(
        len(process.stdout.encode("utf-8")) <= config.stream_limit_bytes
        and len(process.stderr.encode("utf-8")) <= config.stream_limit_bytes
    )
    if process.returncode == 0 and result_path.exists() and streams_are_valid:
        parsed_result: object = json.loads(result_path.read_text(encoding="utf-8"))
        if isinstance(parsed_result, dict):
            return parsed_result, process.stdout, process.stderr
        else:
            raise ValueError("EnergyPlusToFMU worker result is not an object")
    else:
        raise RuntimeError("EnergyPlusToFMU worker did not complete safely")


def _inspect_energyplus_fmu(fmu_path: Path) -> dict[str, object]:
    """Validate archive safety, FMI 1 metadata and static conformance.

    :param fmu_path: Newly exported compatibility FMU.
    :return: Complete static inspection result.
    """

    archive: zipfile.ZipFile = zipfile.ZipFile(fmu_path, "r")
    try:
        members: list[str] = archive.namelist()
        safe_members: bool = True
        for member in members:
            member_path: Path = Path(member)
            if member_path.is_absolute() or ".." in member_path.parts or "\\" in member:
                safe_members = False
            else:
                pass
        description_bytes: bytes = archive.read("modelDescription.xml")
    finally:
        archive.close()
    root: ElementTree.Element = ElementTree.fromstring(description_bytes)
    scalar_variables: ElementTree.Element | None = root.find("ModelVariables")
    variable_names: list[str] = list()
    if scalar_variables is not None:
        for variable in scalar_variables.findall("ScalarVariable"):
            variable_name: str | None = variable.get("name")
            if variable_name is not None:
                variable_names.append(variable_name)
            else:
                pass
    else:
        pass
    static_findings: list[str] = list(validate_fmu(str(fmu_path)))
    expected_members: set[str] = set(
        (
            "modelDescription.xml",
            "resources/schedule.idf",
            "resources/variables.cfg",
            "resources/Energy+.idd",
            "resources/idf-to-fmu-export-prep-win.exe",
            "resources/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw",
            "binaries/win64/schedule.dll",
        )
    )
    passed: bool = bool(
        safe_members
        and len(members) == len(expected_members)
        and set(members) == expected_members
        and root.get("fmiVersion") == "1.0"
        and root.find("Implementation/CoSimulation_Tool") is not None
        and "Q" in variable_names and "TRooMea" in variable_names
        and len(static_findings) == 0
    )
    return dict(
        status=EnergyPlusToFmuCellStatus.PASS.value if passed else EnergyPlusToFmuCellStatus.FAIL.value,
        member_count=len(members), members=members, safe_members=safe_members,
        fmi_version=root.get("fmiVersion"), variables=variable_names,
        static_findings=static_findings,
    )


def _read_energyplus_runtime_trace(
    trace_path: Path,
) -> tuple[list[float], list[float], list[float]]:
    """Read and validate the complete EnergyPlus FMI trajectory.

    :param trace_path: Worker-produced deterministic CSV trace.
    :return: Time in hours, heat-flow input and zone temperature in Celsius.
    """

    time_hours: list[float] = list()
    heat_flow_watts: list[float] = list()
    zone_temperature_deg_c: list[float] = list()
    trace_file: TextIO = trace_path.open("r", encoding="utf-8", newline="")
    try:
        reader: Iterator[list[str]] = csv.reader(trace_file)
        header: list[str] = next(reader)
        if header == ["time_s", "Q_W", "TRooMea_degC"]:
            pass
        else:
            raise ValueError("EnergyPlus runtime trace header changed")
        row: list[str]
        for row in reader:
            if len(row) == 3:
                time_hours.append(float(row[0]) / 3_600.0)
                heat_flow_watts.append(float(row[1]))
                zone_temperature_deg_c.append(float(row[2]))
            else:
                raise ValueError("EnergyPlus runtime trace row width changed")
    finally:
        trace_file.close()
    trace_is_valid: bool = bool(
        len(time_hours) == 97
        and len(heat_flow_watts) == 97
        and len(zone_temperature_deg_c) == 97
        and all(math.isfinite(value) for value in time_hours)
        and all(math.isfinite(value) for value in heat_flow_watts)
        and all(math.isfinite(value) for value in zone_temperature_deg_c)
    )
    if trace_is_valid:
        return time_hours, heat_flow_watts, zone_temperature_deg_c
    else:
        raise ValueError("EnergyPlus runtime trace is incomplete or non-finite")


def _render_energyplus_runtime_figure(
    package_root: Path,
    trace_path: Path,
) -> dict[str, object]:
    """Render the input schedule and resulting thermal trajectory.

    :param package_root: Unpublished evidence package root.
    :param trace_path: Verified runtime trace to visualize.
    :return: Declarative figure identity and transition metadata.
    """

    time_hours, heat_flow_watts, zone_temperature_deg_c = (
        _read_energyplus_runtime_trace(trace_path)
    )
    transition_hours: tuple[float, float, float] = (6.0, 12.0, 18.0)
    style: dict[str, object] = {
        "font.family": "DejaVu Sans",
        "font.size": 8.0,
        "axes.titlesize": 8.5,
        "axes.labelsize": 8.0,
        "xtick.labelsize": 7.0,
        "ytick.labelsize": 7.0,
        "axes.linewidth": 0.7,
        "lines.linewidth": 1.2,
        "svg.fonttype": "none",
        "svg.hashsalt": "veragrid-energyplus-to-fmu-comparison",
        "pdf.fonttype": 42,
    }
    with matplotlib.rc_context(style):
        figure: Figure = Figure(figsize=(7.2, 5.2), dpi=300)
        FigureCanvasAgg(figure)
        input_axis: Axes = figure.add_subplot(2, 1, 1)
        temperature_axis: Axes = figure.add_subplot(2, 1, 2, sharex=input_axis)
        input_axis.step(
            time_hours,
            heat_flow_watts,
            where="post",
            color="#3569a8",
            label="FMU input Q",
        )
        temperature_axis.plot(
            time_hours,
            zone_temperature_deg_c,
            color="#202020",
            label="EnergyPlus TRooMea",
        )
        transition_hour: float
        for transition_hour in transition_hours:
            input_axis.axvline(
                transition_hour, color="#777777", linestyle=":", linewidth=0.8
            )
            temperature_axis.axvline(
                transition_hour, color="#777777", linestyle=":", linewidth=0.8
            )
        input_axis.set_title("Applied heat-flow schedule", loc="left")
        input_axis.set_ylabel("Q [W]")
        temperature_axis.set_title("Zone thermal response", loc="left")
        temperature_axis.set_ylabel("TRooMea [°C]")
        temperature_axis.set_xlabel("Time [h]")
        input_axis.set_xlim(0.0, 24.0)
        for axis in (input_axis, temperature_axis):
            axis.tick_params(direction="in")
            axis.grid(True, color="#d9d9d9", linewidth=0.5)
            axis.legend(loc="best", frameon=False)
        figure.suptitle(
            "EnergyPlusToFMU 3.1 compatibility runtime — FMI 1.0 Co-Simulation",
            fontsize=10.0,
        )
        figure.subplots_adjust(
            left=0.12, right=0.98, bottom=0.11, top=0.90, hspace=0.34
        )
        figures_directory: Path = package_root / "figures"
        figures_directory.mkdir()
        figure_stem: Path = figures_directory / "energyplus-fmi1-cs-trajectory"
        png_metadata: dict[str, str] = {
            "Software": "VeraGrid EnergyPlusToFMU comparison"
        }
        svg_metadata: dict[str, str] = {
            "Creator": "VeraGrid EnergyPlusToFMU comparison",
            "Date": "1970-01-01T00:00:00Z",
        }
        fixed_pdf_time: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)
        pdf_metadata: dict[str, object] = {
            "Creator": "VeraGrid EnergyPlusToFMU comparison",
            "CreationDate": fixed_pdf_time,
            "ModDate": fixed_pdf_time,
        }
        figure.savefig(figure_stem.with_suffix(".png"), dpi=300, metadata=png_metadata)
        figure.savefig(figure_stem.with_suffix(".svg"), metadata=svg_metadata)
        figure.savefig(figure_stem.with_suffix(".pdf"), metadata=pdf_metadata)
        figure.clear()
    return dict(
        title="EnergyPlusToFMU 3.1 compatibility runtime — FMI 1.0 Co-Simulation",
        size_inches=[7.2, 5.2],
        png_pixels=[2160, 1560],
        transition_hours=list(transition_hours),
        files=list(
            (
                "figures/energyplus-fmi1-cs-trajectory.png",
                "figures/energyplus-fmi1-cs-trajectory.svg",
                "figures/energyplus-fmi1-cs-trajectory.pdf",
            )
        ),
    )


def _write_energyplus_to_fmu_manifest(
    config: EnergyPlusToFmuComparisonConfig,
    package_root: Path,
    export_result: dict[str, object],
    static_result: dict[str, object],
    runtime_result: dict[str, object],
    figure_record: dict[str, object],
) -> None:
    """Write the claim-bounded package manifest.

    :param config: Authenticated comparison configuration.
    :param package_root: Staging package root.
    :param export_result: Compatibility exporter outcome.
    :param static_result: Archive and FMPy validation outcome.
    :param runtime_result: Isolated runtime-probe outcome.
    :param figure_record: Deterministic scientific-figure metadata.
    :return: None.
    """

    indexed_files: list[tuple[str, dict[str, object]]] = list()
    package_paths: list[Path] = list(package_root.rglob("*"))
    for package_path in package_paths:
        if package_path.is_file() and package_path.name != "manifest.json":
            content: bytes = package_path.read_bytes()
            portable_path: str = package_path.relative_to(package_root).as_posix()
            file_record: dict[str, object] = dict(
                path=portable_path,
                size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest(),
            )
            indexed_files.append((portable_path, file_record))
        else:
            pass
    indexed_files.sort()
    files: list[dict[str, object]] = list()
    for indexed_file in indexed_files:
        files.append(indexed_file[1])
    runtime_findings_value: object = runtime_result.get("findings", None)
    if isinstance(runtime_findings_value, list):
        runtime_findings: list[object] = runtime_findings_value
    else:
        raise ValueError("EnergyPlusToFMU runtime findings must be a list")
    all_cells_passed: bool = bool(
        export_result.get("status", None) == EnergyPlusToFmuCellStatus.PASS.value
        and static_result.get("status", None)
        == EnergyPlusToFmuCellStatus.PASS.value
        and runtime_result.get("status", None)
        == EnergyPlusToFmuCellStatus.PASS.value
        and len(runtime_findings) == 0
    )
    if all_cells_passed:
        package_status: str = EnergyPlusToFmuCellStatus.PASS.value
    else:
        raise ValueError("EnergyPlusToFMU evidence cells must all pass before publication")
    proven_claims: list[str] = list(
        (
            "EnergyPlusToFMU 3.1-derived FMI 1.0 CS export and FMPy validation on the recorded Windows toolchain using the declared compatibility patch.",
            "One 24-hour FMI 1.0 CS runtime trajectory with EnergyPlus 9.4 and FMPy 0.3.31: 96 steps, four input plateaus and three transitions.",
        )
    )
    manifest: dict[str, object] = dict(
        schema="veragrid.energyplus-to-fmu-comparison/1",
        status=package_status,
        source=dict(branch=config.source_branch, revision=config.source_revision,
                    tree_sha256=config.source_tree_sha256),
        upstream=dict(version="3.1.0", commit=config.upstream_commit,
                      git_tree=config.upstream_tree),
        compatibility=dict(
            patch="provenance/energyplus-to-fmu-v3.1-windows-runtime.patch",
            source_tree=dict(
                file_count=config.exporter_source_file_count,
                total_size_bytes=config.exporter_source_total_size_bytes,
                sha256=config.exporter_source_tree_sha256,
            ),
        ),
        scenario_inputs=dict(
            idd=dict(size_bytes=config.idd_size_bytes, sha256=config.idd_sha256),
            idf=dict(size_bytes=config.idf_size_bytes, sha256=config.idf_sha256),
            epw=dict(size_bytes=config.epw_size_bytes, sha256=config.epw_sha256),
        ),
        export=export_result, static_validation=static_result,
        runtime=runtime_result,
        findings=runtime_findings,
        figure_generated=True,
        figure=figure_record,
        claim_boundary=dict(
            proven=proven_claims,
            not_proven=[
                "Unmodified upstream runtime on this host.",
                "FMI certification.",
                "Multiplatform support.",
                "Numerical equivalence with VeraGrid.",
            ],
        ),
        files=files,
    )
    manifest_bytes: bytes = (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    (package_root / "manifest.json").write_bytes(manifest_bytes)


def _verify_energyplus_to_fmu_package(
    config: EnergyPlusToFmuComparisonConfig,
    package_root: Path,
) -> None:
    """Reopen a completed package and reject unsafe or inconsistent state.

    :param config: Authenticated comparison configuration.
    :param package_root: Complete staging or published package.
    :return: None.
    """

    _validate_energyplus_to_fmu_config(config)
    resolved_package_root: Path = package_root.resolve(strict=True)
    entries: list[Path] = list(resolved_package_root.rglob("*"))
    for entry in entries:
        if path_is_link_or_reparse_point(entry):
            raise ValueError("EnergyPlusToFMU package contains an indirection")
        else:
            pass
    manifest_path: Path = resolved_package_root / "manifest.json"
    manifest_bytes: bytes = manifest_path.read_bytes()
    manifest_object: object = json.loads(manifest_bytes.decode("utf-8", errors="strict"))
    if isinstance(manifest_object, dict):
        manifest: dict[str, object] = manifest_object
    else:
        raise ValueError("EnergyPlusToFMU manifest is not an object")
    canonical_manifest: bytes = (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    expected_source: dict[str, object] = dict(
        branch=config.source_branch,
        revision=config.source_revision,
        tree_sha256=config.source_tree_sha256,
    )
    expected_upstream: dict[str, object] = dict(
        version="3.1.0",
        commit=config.upstream_commit,
        git_tree=config.upstream_tree,
    )
    expected_compatibility: dict[str, object] = dict(
        patch="provenance/energyplus-to-fmu-v3.1-windows-runtime.patch",
        source_tree=dict(
            file_count=config.exporter_source_file_count,
            total_size_bytes=config.exporter_source_total_size_bytes,
            sha256=config.exporter_source_tree_sha256,
        ),
    )
    expected_scenario_inputs: dict[str, object] = dict(
        idd=dict(size_bytes=config.idd_size_bytes, sha256=config.idd_sha256),
        idf=dict(size_bytes=config.idf_size_bytes, sha256=config.idf_sha256),
        epw=dict(size_bytes=config.epw_size_bytes, sha256=config.epw_sha256),
    )
    expected_figure: dict[str, object] = dict(
        title="EnergyPlusToFMU 3.1 compatibility runtime — FMI 1.0 Co-Simulation",
        size_inches=[7.2, 5.2],
        png_pixels=[2160, 1560],
        transition_hours=[6.0, 12.0, 18.0],
        files=list(
            (
                "figures/energyplus-fmi1-cs-trajectory.png",
                "figures/energyplus-fmi1-cs-trajectory.svg",
                "figures/energyplus-fmi1-cs-trajectory.pdf",
            )
        ),
    )
    package_is_valid: bool = bool(
        tuple(sorted(manifest.keys()))
        == (
            "claim_boundary", "compatibility", "export", "figure",
            "figure_generated", "files", "findings", "runtime", "scenario_inputs",
            "schema", "source", "static_validation", "status", "upstream",
        )
        and manifest.get("schema", None)
        == "veragrid.energyplus-to-fmu-comparison/1"
        and manifest.get("source", None) == expected_source
        and manifest.get("upstream", None) == expected_upstream
        and manifest.get("compatibility", None) == expected_compatibility
        and manifest.get("scenario_inputs", None) == expected_scenario_inputs
        and manifest.get("figure_generated", None) is True
        and manifest.get("figure", None) == expected_figure
        and manifest_bytes == canonical_manifest
    )
    if package_is_valid:
        pass
    else:
        raise ValueError("EnergyPlusToFMU package contract failed")

    # Bind the complete evidence closure and reject every undeclared path.
    files_value: object = manifest.get("files", None)
    if not isinstance(files_value, list) or len(files_value) != 12:
        raise ValueError("EnergyPlusToFMU package must bind exactly twelve files")
    else:
        file_records: list[object] = files_value
    declared_paths: set[str] = set()
    file_record_value: object
    for file_record_value in file_records:
        if not isinstance(file_record_value, dict):
            raise ValueError("EnergyPlusToFMU file record must be an object")
        else:
            file_record: dict[str, object] = file_record_value
        if tuple(sorted(file_record.keys())) != ("path", "sha256", "size_bytes"):
            raise ValueError("Unexpected EnergyPlusToFMU file-record fields")
        else:
            pass
        relative_value: object = file_record.get("path", None)
        size_value: object = file_record.get("size_bytes", None)
        digest_value: object = file_record.get("sha256", None)
        if (
            not isinstance(relative_value, str)
            or not isinstance(size_value, int)
            or not isinstance(digest_value, str)
            or len(digest_value) != 64
        ):
            raise ValueError("Invalid EnergyPlusToFMU file-record value")
        else:
            relative_path: Path = Path(relative_value)
        if (
            relative_path.is_absolute()
            or ".." in relative_path.parts
            or relative_path.as_posix() != relative_value
            or relative_value in declared_paths
        ):
            raise ValueError("Unsafe or duplicate EnergyPlusToFMU package path")
        else:
            declared_paths.add(relative_value)
        bound_path: Path = (resolved_package_root / relative_path).resolve(strict=True)
        if resolved_package_root not in bound_path.parents:
            raise ValueError("EnergyPlusToFMU package path escapes its root")
        else:
            verify_regular_file_identity(bound_path, size_value, digest_value)
    expected_paths: set[str] = set(
        (
            "figures/energyplus-fmi1-cs-trajectory.pdf",
            "figures/energyplus-fmi1-cs-trajectory.png",
            "figures/energyplus-fmi1-cs-trajectory.svg",
            "provenance/energyplus-to-fmu-v3.1-windows-runtime.patch",
            "raw/export/result.json",
            "raw/export/schedule.fmu",
            "raw/export/worker-stderr.log",
            "raw/export/worker-stdout.log",
            "raw/runtime/result.json",
            "raw/runtime/trace.csv",
            "raw/runtime/worker-stderr.log",
            "raw/runtime/worker-stdout.log",
        )
    )
    if declared_paths != expected_paths:
        raise ValueError("EnergyPlusToFMU declared file set changed")
    else:
        pass
    discovered_paths: set[str] = set()
    for entry in entries:
        if entry.is_file():
            discovered_paths.add(entry.relative_to(resolved_package_root).as_posix())
        else:
            pass
    expected_paths.add("manifest.json")
    if discovered_paths != expected_paths:
        raise ValueError("EnergyPlusToFMU package closure changed")
    else:
        pass

    # Reopen raw results and independently rerun the static FMU inspection.
    export_result_value: object = json.loads(
        (resolved_package_root / "raw" / "export" / "result.json").read_text(
            encoding="utf-8"
        )
    )
    runtime_result_value: object = json.loads(
        (resolved_package_root / "raw" / "runtime" / "result.json").read_text(
            encoding="utf-8"
        )
    )
    if not isinstance(export_result_value, dict) or not isinstance(
        runtime_result_value, dict
    ):
        raise ValueError("EnergyPlusToFMU raw result must be an object")
    else:
        export_result: dict[str, object] = export_result_value
        runtime_result: dict[str, object] = runtime_result_value
    static_result: dict[str, object] = _inspect_energyplus_fmu(
        resolved_package_root / "raw" / "export" / "schedule.fmu"
    )
    runtime_findings_value: object = runtime_result.get("findings", None)
    if not isinstance(runtime_findings_value, list):
        raise ValueError("EnergyPlusToFMU runtime findings must be a list")
    else:
        runtime_findings: list[object] = runtime_findings_value
    lifecycle_value: object = runtime_result.get("lifecycle", None)
    trajectory_value: object = runtime_result.get("trajectory", None)
    if isinstance(lifecycle_value, dict) and isinstance(trajectory_value, dict):
        lifecycle: dict[str, object] = lifecycle_value
        trajectory: dict[str, object] = trajectory_value
    else:
        raise ValueError("EnergyPlusToFMU runtime contract is incomplete")
    trace_path: Path = resolved_package_root / "raw" / "runtime" / "trace.csv"
    time_hours, heat_flow_watts, zone_temperature_deg_c = (
        _read_energyplus_runtime_trace(trace_path)
    )
    expected_sample_count: int = (
        len(config.input_levels) * config.steps_per_level + 1
    )
    expected_input_values: list[float] = [0.0] * expected_sample_count
    expected_time_hours: list[float] = [0.0] * expected_sample_count
    input_level_index: int
    input_sample_index: int
    for input_level_index in range(len(config.input_levels)):
        for input_sample_index in range(config.steps_per_level):
            expected_input_values[
                input_level_index * config.steps_per_level + input_sample_index
            ] = config.input_levels[input_level_index]
    expected_input_values[-1] = config.input_levels[-1]
    for input_sample_index in range(expected_sample_count):
        expected_time_hours[input_sample_index] = (
            input_sample_index * config.communication_step_seconds / 3_600.0
        )
    observed_transition_count: int = 0
    sample_index: int
    for sample_index in range(1, len(heat_flow_watts)):
        if heat_flow_watts[sample_index] != heat_flow_watts[sample_index - 1]:
            observed_transition_count += 1
        else:
            pass
    trace_is_consistent: bool = bool(
        time_hours == expected_time_hours
        and heat_flow_watts == expected_input_values
        and observed_transition_count == len(config.input_levels) - 1
        and trajectory.get("trace_name", None) == "trace.csv"
        and trajectory.get("sample_count", None) == expected_sample_count
        and trajectory.get("total_steps", None) == expected_sample_count - 1
        and trajectory.get("communication_step_seconds", None)
        == config.communication_step_seconds
        and trajectory.get("stop_time_seconds", None)
        == (expected_sample_count - 1) * config.communication_step_seconds
        and trajectory.get("steps_per_level", None) == config.steps_per_level
        and trajectory.get("input_levels", None) == list(config.input_levels)
        and trajectory.get("input_transition_count", None) == observed_transition_count
        and trajectory.get("output_minimum_deg_c", None) == min(zone_temperature_deg_c)
        and trajectory.get("output_maximum_deg_c", None) == max(zone_temperature_deg_c)
        and trajectory.get("output_span_deg_c", None)
        == max(zone_temperature_deg_c) - min(zone_temperature_deg_c)
        and max(zone_temperature_deg_c) - min(zone_temperature_deg_c) > 0.01
        and trajectory.get("finite", None) is True
        and runtime_result.get("diagnostic", None) == ""
    )
    all_cells_passed: bool = bool(
        export_result.get("schema", None)
        == "veragrid.energyplus-to-fmu-worker/1"
        and export_result.get("mode", None) == "EXPORT"
        and export_result.get("status", None) == EnergyPlusToFmuCellStatus.PASS.value
        and export_result.get("fmu_name", None) == "schedule.fmu"
        and static_result.get("status", None) == EnergyPlusToFmuCellStatus.PASS.value
        and runtime_result.get("schema", None)
        == "veragrid.energyplus-to-fmu-worker/2"
        and runtime_result.get("mode", None) == "RUNTIME_PROBE"
        and runtime_result.get("status", None) == EnergyPlusToFmuCellStatus.PASS.value
        and len(runtime_findings) == 0
        and lifecycle
        == dict(
            instantiated=True,
            initialized=True,
            terminated=True,
            instance_released=True,
        )
        and trace_is_consistent
    )
    if all_cells_passed:
        expected_status: str = EnergyPlusToFmuCellStatus.PASS.value
        expected_proven: list[str] = list(
            (
                "EnergyPlusToFMU 3.1-derived FMI 1.0 CS export and FMPy validation on the recorded Windows toolchain using the declared compatibility patch.",
                "One 24-hour FMI 1.0 CS runtime trajectory with EnergyPlus 9.4 and FMPy 0.3.31: 96 steps, four input plateaus and three transitions.",
            )
        )
    else:
        raise ValueError("EnergyPlusToFMU evidence cells or trajectory failed")
    expected_claim_boundary: dict[str, object] = dict(
        proven=expected_proven,
        not_proven=list(
            (
                "Unmodified upstream runtime on this host.",
                "FMI certification.",
                "Multiplatform support.",
                "Numerical equivalence with VeraGrid.",
            )
        ),
    )
    if (
        manifest.get("export", None) != export_result
        or manifest.get("runtime", None) != runtime_result
        or manifest.get("static_validation", None) != static_result
        or manifest.get("findings", None) != runtime_findings
        or manifest.get("status", None) != expected_status
        or manifest.get("claim_boundary", None) != expected_claim_boundary
        or manifest.get("figure", None) != expected_figure
    ):
        raise ValueError("EnergyPlusToFMU evidence semantics changed")
    else:
        pass

    # Re-render from the authenticated trace and require byte-identical figures.
    verification_root: Path = Path(
        tempfile.mkdtemp(
            prefix=".energyplus-figure-verification-",
            dir=config.temporary_directory,
        )
    )
    try:
        regenerated_figure: dict[str, object] = _render_energyplus_runtime_figure(
            verification_root, trace_path
        )
        if regenerated_figure == expected_figure:
            pass
        else:
            raise ValueError("EnergyPlusToFMU regenerated figure metadata changed")
        figure_suffix: str
        for figure_suffix in (".png", ".svg", ".pdf"):
            packaged_figure_path: Path = (
                resolved_package_root
                / "figures"
                / ("energyplus-fmi1-cs-trajectory" + figure_suffix)
            )
            regenerated_figure_path: Path = (
                verification_root
                / "figures"
                / ("energyplus-fmi1-cs-trajectory" + figure_suffix)
            )
            if packaged_figure_path.read_bytes() == regenerated_figure_path.read_bytes():
                pass
            else:
                raise ValueError("EnergyPlusToFMU figure is not reproducible")
    finally:
        shutil.rmtree(verification_root)
    _validate_energyplus_to_fmu_config(config)


def generate_energyplus_to_fmu_comparison(
    config: EnergyPlusToFmuComparisonConfig,
) -> Path:
    """Export, validate, probe and atomically publish one evidence package.

    :param config: Complete authenticated comparison configuration.
    :return: Final verified package path.
    """

    _validate_energyplus_to_fmu_config(config)
    if config.output_directory.exists():
        raise FileExistsError("EnergyPlusToFMU output directory already exists")
    else:
        pass
    staging_path: Path = Path(tempfile.mkdtemp(
        prefix=config.output_directory.name + ".", dir=config.output_directory.parent
    ))
    package_was_published: bool = False
    try:
        raw_root: Path = staging_path / "raw"
        export_root: Path = raw_root / "export"
        runtime_root: Path = raw_root / "runtime"
        provenance_root: Path = staging_path / "provenance"
        export_root.mkdir(parents=True)
        runtime_root.mkdir(parents=True)
        provenance_root.mkdir()
        shutil.copyfile(
            config.compatibility_patch_path,
            provenance_root / "energyplus-to-fmu-v3.1-windows-runtime.patch",
        )
        export_result_path: Path = export_root / "result.json"
        export_work_path: Path = Path(
            tempfile.mkdtemp(
                prefix=".energyplus-export-",
                dir=config.temporary_directory,
            )
        )
        try:
            export_result, export_stdout, export_stderr = (
                _run_energyplus_to_fmu_worker(
                    config,
                    "EXPORT",
                    export_work_path,
                    export_result_path,
                    export_work_path / "schedule.fmu",
                    export_root / "unused-trace.csv",
                )
            )
            shutil.copyfile(
                export_work_path / "schedule.fmu",
                export_root / "schedule.fmu",
            )
        finally:
            if export_work_path.exists():
                shutil.rmtree(export_work_path)
            else:
                pass
        (export_root / "worker-stdout.log").write_text(export_stdout, encoding="utf-8")
        (export_root / "worker-stderr.log").write_text(export_stderr, encoding="utf-8")
        exported_fmu: Path = export_root / "schedule.fmu"
        static_result: dict[str, object] = _inspect_energyplus_fmu(exported_fmu)
        runtime_result_path: Path = runtime_root / "result.json"
        runtime_trace_path: Path = runtime_root / "trace.csv"
        runtime_work_path: Path = Path(
            tempfile.mkdtemp(
                prefix=".energyplus-runtime-",
                dir=config.temporary_directory,
            )
        )
        try:
            runtime_result, runtime_stdout, runtime_stderr = (
                _run_energyplus_to_fmu_worker(
                    config,
                    "RUNTIME_PROBE",
                    runtime_work_path,
                    runtime_result_path,
                    exported_fmu,
                    runtime_trace_path,
                )
            )
        finally:
            if runtime_work_path.exists():
                shutil.rmtree(runtime_work_path)
            else:
                pass
        (runtime_root / "worker-stdout.log").write_text(runtime_stdout, encoding="utf-8")
        (runtime_root / "worker-stderr.log").write_text(runtime_stderr, encoding="utf-8")
        if runtime_result.get("status", None) == EnergyPlusToFmuCellStatus.PASS.value:
            figure_record: dict[str, object] = _render_energyplus_runtime_figure(
                staging_path, runtime_trace_path
            )
        else:
            raise ValueError("EnergyPlusToFMU runtime did not satisfy the figure oracle")
        _write_energyplus_to_fmu_manifest(
            config,
            staging_path,
            export_result,
            static_result,
            runtime_result,
            figure_record,
        )
        _verify_energyplus_to_fmu_package(config, staging_path)
        staging_path.replace(config.output_directory)
        package_was_published = True
        _verify_energyplus_to_fmu_package(config, config.output_directory)
        return config.output_directory
    except Exception:
        if package_was_published and config.output_directory.exists():
            shutil.rmtree(config.output_directory)
        else:
            if staging_path.exists():
                shutil.rmtree(staging_path)
            else:
                pass
        raise












