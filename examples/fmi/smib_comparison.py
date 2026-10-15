# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Execute and compare one nontrivial SMIB FMU across open-source runtimes."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import TextIO, cast

import matplotlib
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np
from fmpy import simulate_fmu

from VeraGridEngine.IO.fmu.Elements.bindings import FmuImportConfig
from VeraGridEngine.IO.fmu.host import FmuRuntimeHost, open_fmu_runtime_host
from VeraGridEngine.enumerations import FmuInterfaceMode
from examples.fmi.omsimulator import run_bounded_omsimulator_process
from examples.fmi.openmodelica import OpenModelicaBuildEvidence
from examples.fmi.reference_fmu_execution import read_fmpy_distribution_identity


class SmibComparisonConfig:
    """Own exact tool identities and the SMIB numerical grids."""

    __slots__ = (
        "build_evidence", "omsimulator_executable", "omsimulator_expected_version",
        "omsimulator_expected_size_bytes", "omsimulator_expected_sha256",
        "fmpy_expected_version", "fmpy_expected_distribution_sha256",
        "output_directory", "process_timeout_seconds", "communication_step",
        "output_interval", "convergence_step_sizes",
    )

    build_evidence: OpenModelicaBuildEvidence
    omsimulator_executable: Path
    omsimulator_expected_version: str
    omsimulator_expected_size_bytes: int
    omsimulator_expected_sha256: str
    fmpy_expected_version: str
    fmpy_expected_distribution_sha256: str
    output_directory: Path
    process_timeout_seconds: float
    communication_step: float
    output_interval: float
    convergence_step_sizes: tuple[float, ...]

    def __init__(
        self,
        build_evidence: OpenModelicaBuildEvidence,
        omsimulator_executable: Path,
        omsimulator_expected_version: str,
        omsimulator_expected_size_bytes: int,
        omsimulator_expected_sha256: str,
        fmpy_expected_version: str,
        fmpy_expected_distribution_sha256: str,
        output_directory: Path,
        process_timeout_seconds: float,
        communication_step: float,
        output_interval: float,
        convergence_step_sizes: tuple[float, ...],
    ) -> None:
        """Validate the caller-owned comparison configuration.

        :param build_evidence: Published OpenModelica SMIB build evidence.
        :param omsimulator_executable: Explicit OMSimulator executable.
        :param omsimulator_expected_version: Exact ``--version`` text.
        :param omsimulator_expected_size_bytes: Required executable size.
        :param omsimulator_expected_sha256: Required executable SHA-256.
        :param fmpy_expected_version: Required installed FMPy version.
        :param fmpy_expected_distribution_sha256: Required distribution digest.
        :param output_directory: Nonexistent final comparison directory.
        :param process_timeout_seconds: Native OMSimulator deadline.
        :param communication_step: Finest FMI communication step in seconds.
        :param output_interval: Retained comparison interval in seconds.
        :param convergence_step_sizes: Ordered communication steps for convergence.
        :return: None.
        """

        basic_types_are_valid: bool = bool(
            isinstance(build_evidence, OpenModelicaBuildEvidence)
            and isinstance(omsimulator_executable, Path)
            and isinstance(output_directory, Path)
            and type(omsimulator_expected_size_bytes) is int
            and omsimulator_expected_size_bytes > 0
            and isinstance(convergence_step_sizes, tuple)
        )
        identities_are_valid: bool = bool(
            isinstance(omsimulator_expected_version, str)
            and bool(omsimulator_expected_version.strip())
            and isinstance(fmpy_expected_version, str)
            and bool(fmpy_expected_version.strip())
            and re.fullmatch(r"[0-9a-f]{64}", omsimulator_expected_sha256) is not None
            and re.fullmatch(r"[0-9a-f]{64}", fmpy_expected_distribution_sha256) is not None
        )
        timeout_is_valid: bool = bool(
            math.isfinite(process_timeout_seconds)
            and 1.0 <= process_timeout_seconds <= 120.0
        )
        numerical_grid_is_valid: bool = bool(
            communication_step == 0.000125
            and output_interval == 0.002
            and convergence_step_sizes == (0.002, 0.001, 0.0005, 0.00025, 0.000125)
        )
        if (
            basic_types_are_valid
            and identities_are_valid
            and timeout_is_valid
            and numerical_grid_is_valid
        ):
            pass
        else:
            raise ValueError("SMIB comparison configuration is invalid")
        self.build_evidence: OpenModelicaBuildEvidence = build_evidence
        self.omsimulator_executable: Path = omsimulator_executable
        self.omsimulator_expected_version: str = omsimulator_expected_version.strip()
        self.omsimulator_expected_size_bytes: int = omsimulator_expected_size_bytes
        self.omsimulator_expected_sha256: str = omsimulator_expected_sha256
        self.fmpy_expected_version: str = fmpy_expected_version.strip()
        self.fmpy_expected_distribution_sha256: str = fmpy_expected_distribution_sha256
        self.output_directory: Path = output_directory
        self.process_timeout_seconds: float = process_timeout_seconds
        self.communication_step: float = communication_step
        self.output_interval: float = output_interval
        self.convergence_step_sizes: tuple[float, ...] = convergence_step_sizes

class SmibTrace:
    """Own one validated 2001-row SMIB trajectory."""

    __slots__ = (
        "tool_name", "time", "angle", "speed", "electrical_power",
        "effective_reactance",
    )

    tool_name: str
    time: np.ndarray
    angle: np.ndarray
    speed: np.ndarray
    electrical_power: np.ndarray
    effective_reactance: np.ndarray

    def __init__(
        self,
        tool_name: str,
        time: np.ndarray,
        angle: np.ndarray,
        speed: np.ndarray,
        electrical_power: np.ndarray,
        effective_reactance: np.ndarray,
    ) -> None:
        """Validate and retain one detached trajectory.

        :param tool_name: Stable comparison-tool label.
        :param time: Exact simulation lattice in seconds.
        :param angle: Rotor angle in radians.
        :param speed: Rotor speed in p.u.
        :param electrical_power: Electrical power in p.u.
        :param effective_reactance: Active network reactance in p.u.
        :return: None.
        """

        arrays: tuple[np.ndarray, ...] = (
            time, angle, speed, electrical_power, effective_reactance,
        )
        arrays_are_valid: bool = bool(
            tool_name in ("OpenModelica", "VeraGrid", "FMPy", "OMSimulator")
            and all(isinstance(array, np.ndarray) for array in arrays)
            and all(array.shape == (2001,) for array in arrays)
            and all(np.all(np.isfinite(array)) for array in arrays)
            and np.max(np.abs(time - np.arange(2001, dtype=float) * 0.002)) <= 1e-12
        )
        if arrays_are_valid:
            pass
        else:
            raise ValueError("SMIB trace must be finite on the exact 2001-row lattice")
        self.tool_name: str = tool_name
        self.time: np.ndarray = np.array(time, dtype=float, copy=True)
        self.angle: np.ndarray = np.array(angle, dtype=float, copy=True)
        self.speed: np.ndarray = np.array(speed, dtype=float, copy=True)
        self.electrical_power: np.ndarray = np.array(electrical_power, dtype=float, copy=True)
        self.effective_reactance: np.ndarray = np.array(
            effective_reactance, dtype=float, copy=True
        )


class SmibComparisonMetrics:
    """Retain fixed pointwise error maxima for one tool pair."""

    __slots__ = (
        "left_tool", "right_tool", "max_angle_error", "max_speed_error",
        "max_electrical_power_error", "max_effective_reactance_error", "passed",
    )

    left_tool: str
    right_tool: str
    max_angle_error: float
    max_speed_error: float
    max_electrical_power_error: float
    max_effective_reactance_error: float
    passed: bool

    def __init__(
        self,
        left_tool: str,
        right_tool: str,
        max_angle_error: float,
        max_speed_error: float,
        max_electrical_power_error: float,
        max_effective_reactance_error: float,
        passed: bool,
    ) -> None:
        """Retain immutable pairwise acceptance results.

        :param left_tool: First comparison-tool label.
        :param right_tool: Second comparison-tool label.
        :param max_angle_error: Maximum absolute rotor-angle difference.
        :param max_speed_error: Maximum absolute speed difference.
        :param max_electrical_power_error: Maximum absolute power difference.
        :param max_effective_reactance_error: Maximum reactance difference.
        :param passed: Whether every pointwise budget passed.
        :return: None.
        """

        self.left_tool: str = left_tool
        self.right_tool: str = right_tool
        self.max_angle_error: float = float(max_angle_error)
        self.max_speed_error: float = float(max_speed_error)
        self.max_electrical_power_error: float = float(max_electrical_power_error)
        self.max_effective_reactance_error: float = float(max_effective_reactance_error)
        self.passed: bool = bool(passed)


class SmibNativeFidelityMetrics:
    """Retain independently reproducible native-reference fidelity metrics."""

    __slots__ = (
        "tool_name", "signal_baselines", "response_scales", "max_absolute_errors",
        "rms_absolute_errors", "normalized_max_errors", "normalized_rms_errors",
        "max_effective_reactance_error", "passed",
    )

    tool_name: str
    signal_baselines: np.ndarray
    response_scales: np.ndarray
    max_absolute_errors: np.ndarray
    rms_absolute_errors: np.ndarray
    normalized_max_errors: np.ndarray
    normalized_rms_errors: np.ndarray
    max_effective_reactance_error: float
    passed: bool

    def __init__(
        self,
        tool_name: str,
        signal_baselines: np.ndarray,
        response_scales: np.ndarray,
        max_absolute_errors: np.ndarray,
        rms_absolute_errors: np.ndarray,
        normalized_max_errors: np.ndarray,
        normalized_rms_errors: np.ndarray,
        max_effective_reactance_error: float,
        passed: bool,
    ) -> None:
        """Validate and retain one native-fidelity result.

        Arrays use the fixed order angle, speed and electrical power.

        :param tool_name: FMI runtime compared with native OpenModelica DASSL.
        :param signal_baselines: Native retained-row-zero values, shape ``(3,)``.
        :param response_scales: Native response excursions, shape ``(3,)``.
        :param max_absolute_errors: Maximum absolute errors, shape ``(3,)``.
        :param rms_absolute_errors: RMS absolute errors, shape ``(3,)``.
        :param normalized_max_errors: Scale-normalized maxima, shape ``(3,)``.
        :param normalized_rms_errors: Scale-normalized RMS values, shape ``(3,)``.
        :param max_effective_reactance_error: Maximum reactance error in p.u.
        :param passed: Whether all fidelity limits passed.
        :return: None.
        """

        arrays: tuple[np.ndarray, ...] = (
            signal_baselines, response_scales, max_absolute_errors,
            rms_absolute_errors, normalized_max_errors, normalized_rms_errors,
        )
        arrays_are_valid: bool = bool(
            tool_name in ("VeraGrid", "FMPy", "OMSimulator")
            and all(isinstance(array, np.ndarray) for array in arrays)
            and all(array.shape == (3,) for array in arrays)
            and all(np.all(np.isfinite(array)) for array in arrays)
            and np.all(response_scales > 1e-5)
            and all(np.all(array >= 0.0) for array in arrays[2:])
            and math.isfinite(max_effective_reactance_error)
            and max_effective_reactance_error >= 0.0
        )
        if arrays_are_valid:
            pass
        else:
            raise ValueError("Native-fidelity metrics are invalid")
        self.tool_name: str = tool_name
        self.signal_baselines: np.ndarray = np.array(signal_baselines, copy=True)
        self.response_scales: np.ndarray = np.array(response_scales, copy=True)
        self.max_absolute_errors: np.ndarray = np.array(max_absolute_errors, copy=True)
        self.rms_absolute_errors: np.ndarray = np.array(rms_absolute_errors, copy=True)
        self.normalized_max_errors: np.ndarray = np.array(normalized_max_errors, copy=True)
        self.normalized_rms_errors: np.ndarray = np.array(normalized_rms_errors, copy=True)
        self.max_effective_reactance_error: float = float(max_effective_reactance_error)
        self.passed: bool = bool(passed)


class SmibConvergenceMetrics:
    """Retain the fixed five-grid first-order convergence evidence."""

    __slots__ = (
        "step_sizes", "normalized_max_errors", "normalized_rms_errors",
        "refinement_ratios", "passed",
    )

    step_sizes: np.ndarray
    normalized_max_errors: np.ndarray
    normalized_rms_errors: np.ndarray
    refinement_ratios: np.ndarray
    passed: bool

    def __init__(
        self,
        step_sizes: np.ndarray,
        normalized_max_errors: np.ndarray,
        normalized_rms_errors: np.ndarray,
        refinement_ratios: np.ndarray,
        passed: bool,
    ) -> None:
        """Validate and retain convergence matrices.

        Matrix columns use the fixed angle, speed and electrical-power order.

        :param step_sizes: Descending communication steps, shape ``(5,)``.
        :param normalized_max_errors: Normalized maxima, shape ``(5, 3)``.
        :param normalized_rms_errors: Normalized RMS values, shape ``(5, 3)``.
        :param refinement_ratios: Adjacent maximum-error ratios, shape ``(4, 3)``.
        :param passed: Whether monotonicity and first-order bounds passed.
        :return: None.
        """

        arrays_are_valid: bool = bool(
            isinstance(step_sizes, np.ndarray)
            and isinstance(normalized_max_errors, np.ndarray)
            and isinstance(normalized_rms_errors, np.ndarray)
            and isinstance(refinement_ratios, np.ndarray)
            and step_sizes.shape == (5,)
            and normalized_max_errors.shape == (5, 3)
            and normalized_rms_errors.shape == (5, 3)
            and refinement_ratios.shape == (4, 3)
            and np.all(np.isfinite(step_sizes))
            and np.all(np.isfinite(normalized_max_errors))
            and np.all(np.isfinite(normalized_rms_errors))
            and np.all(np.isfinite(refinement_ratios))
            and np.all(step_sizes > 0.0)
            and np.all(normalized_max_errors > 0.0)
            and np.all(normalized_rms_errors >= 0.0)
        )
        if arrays_are_valid:
            pass
        else:
            raise ValueError("SMIB convergence metrics are invalid")
        self.step_sizes: np.ndarray = np.array(step_sizes, copy=True)
        self.normalized_max_errors: np.ndarray = np.array(normalized_max_errors, copy=True)
        self.normalized_rms_errors: np.ndarray = np.array(normalized_rms_errors, copy=True)
        self.refinement_ratios: np.ndarray = np.array(refinement_ratios, copy=True)
        self.passed: bool = bool(passed)


def _validate_smib_comparison_config(
    config: SmibComparisonConfig,
) -> tuple[Path, str, str, str, str]:
    """Validate static identities, then bounded versions, before simulation.

    :param config: Exact build, tool and output configuration.
    :return: OMS path/version/digest followed by FMPy version/digest.
    """

    if isinstance(config, SmibComparisonConfig):
        pass
    else:
        raise TypeError("SMIB comparison requires its typed configuration")
    evidence: OpenModelicaBuildEvidence = config.build_evidence
    fmu_is_valid: bool = bool(
        evidence.fmu_path.is_absolute()
        and not evidence.fmu_path.is_symlink()
        and evidence.fmu_path.is_file()
        and 0 < evidence.fmu_path.stat().st_size <= 67_108_864
    )
    if fmu_is_valid:
        with evidence.fmu_path.open("rb") as fmu_file:
            fmu_sha256: str = hashlib.file_digest(fmu_file, "sha256").hexdigest()
    else:
        raise ValueError("OpenModelica FMU evidence is absent or unsafe")
    if fmu_sha256 == evidence.fmu_sha256:
        pass
    else:
        raise ValueError("OpenModelica FMU evidence digest differs")

    oms_candidate: Path = config.omsimulator_executable
    oms_is_valid: bool = bool(
        oms_candidate.is_absolute()
        and not oms_candidate.is_symlink()
        and oms_candidate.is_file()
        and oms_candidate.stat().st_size == config.omsimulator_expected_size_bytes
    )
    if oms_is_valid:
        resolved_oms: Path = oms_candidate.resolve(strict=True)
    else:
        raise ValueError("OMSimulator executable path or size is invalid")
    with resolved_oms.open("rb") as oms_file:
        oms_sha256: str = hashlib.file_digest(oms_file, "sha256").hexdigest()
    if oms_sha256 == config.omsimulator_expected_sha256:
        pass
    else:
        raise ValueError("OMSimulator executable digest differs")
    output_parent: Path = config.output_directory.parent
    output_is_valid: bool = bool(
        not config.output_directory.exists()
        and not output_parent.is_symlink()
        and output_parent.is_dir()
    )
    if output_is_valid:
        resolved_parent: Path = output_parent.resolve(strict=True)
    else:
        raise ValueError("SMIB output directory must be new under a regular parent")

    # Static identity checks passed. The only native work admitted here is the
    # bounded version probe; no FMU instance exists yet.
    probe_directory: Path = Path(
        tempfile.mkdtemp(prefix=".smib-oms-version-", dir=str(resolved_parent))
    ).resolve(strict=True)
    try:
        run_bounded_omsimulator_process(
            executable_path=resolved_oms,
            runtime_dir=probe_directory,
            process_arguments=("--version",),
            timeout_seconds=10.0,
        )
        version_bytes: bytes = (probe_directory / "omsimulator_stdout.log").read_bytes()
        stderr_bytes: bytes = (probe_directory / "omsimulator_stderr.log").read_bytes()
        oms_version: str = version_bytes.decode("utf-8", errors="strict").strip()
        version_is_valid: bool = bool(
            len(version_bytes) <= 4096
            and len(stderr_bytes) <= 4096
            and oms_version == config.omsimulator_expected_version
        )
        if version_is_valid:
            pass
        else:
            raise RuntimeError("OMSimulator version differs from the pinned identity")
    finally:
        shutil.rmtree(probe_directory)

    # FMPy is loaded in-process; bind its complete distribution before the FMU opens.
    fmpy_version: str
    fmpy_sha256: str
    fmpy_version, fmpy_sha256 = read_fmpy_distribution_identity()
    fmpy_is_valid: bool = bool(
        fmpy_version == config.fmpy_expected_version
        and fmpy_sha256 == config.fmpy_expected_distribution_sha256
    )
    if fmpy_is_valid:
        return resolved_oms, oms_version, oms_sha256, fmpy_version, fmpy_sha256
    else:
        raise ValueError("FMPy distribution identity differs from the pinned identity")


def _parse_smib_trace_csv(csv_path: Path, tool_name: str) -> SmibTrace:
    """Parse one canonical six-column SMIB trace without interpolation.

    :param csv_path: Explicit canonical trace path.
    :param tool_name: Stable owner label for the resulting trace.
    :return: Validated detached SMIB trace.
    """

    trace_is_valid: bool = bool(
        not csv_path.is_symlink()
        and csv_path.is_file()
        and 0 < csv_path.stat().st_size <= 2_097_152
    )
    if trace_is_valid:
        pass
    else:
        raise ValueError("SMIB trace path or size is invalid")
    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        csv_handle: TextIO = csv_file
        rows: list[list[str]] = list(csv.reader(csv_handle))
    expected_header: list[str] = [
        "sample_index", "time_seconds", "angle_rad", "speed_pu",
        "electrical_power_pu", "effective_reactance_pu",
    ]
    if len(rows) == 2002 and rows[0] == expected_header:
        pass
    else:
        raise ValueError("SMIB trace must contain the canonical header and 2001 rows")
    time_values: np.ndarray = np.zeros(2001, dtype=float)
    angle_values: np.ndarray = np.zeros(2001, dtype=float)
    speed_values: np.ndarray = np.zeros(2001, dtype=float)
    power_values: np.ndarray = np.zeros(2001, dtype=float)
    reactance_values: np.ndarray = np.zeros(2001, dtype=float)
    sample_index: int
    for sample_index in range(2001):
        row: list[str] = rows[sample_index + 1]
        if len(row) == 6 and int(row[0]) == sample_index:
            time_values[sample_index] = float(row[1])
            angle_values[sample_index] = float(row[2])
            speed_values[sample_index] = float(row[3])
            power_values[sample_index] = float(row[4])
            reactance_values[sample_index] = float(row[5])
        else:
            raise ValueError("SMIB trace row is not canonical")
    return SmibTrace(
        tool_name=tool_name,
        time=time_values,
        angle=angle_values,
        speed=speed_values,
        electrical_power=power_values,
        effective_reactance=reactance_values,
    )


def _execute_veragrid_smib_trace(
    fmu_path: Path,
    staging_directory: Path,
    trace_path: Path,
    communication_step: float,
    output_interval: float,
) -> SmibTrace:
    """Execute the SMIB FMU through VeraGrid's public FMI runtime host.

    :param fmu_path: Exact OpenModelica-produced FMI 2 CS archive.
    :param staging_directory: Existing owned comparison staging directory.
    :param trace_path: New canonical retained-trace path.
    :param communication_step: FMI communication step in seconds.
    :param output_interval: Retained comparison interval in seconds.
    :return: Validated VeraGrid trace.
    """

    substeps_per_output: int = int(round(output_interval / communication_step))
    grid_is_exact: bool = bool(
        substeps_per_output >= 1
        and abs(substeps_per_output * communication_step - output_interval) <= 1e-15
    )
    if grid_is_exact:
        pass
    else:
        raise ValueError("VeraGrid communication and output grids are incompatible")
    runtime_parent: Path = staging_directory / (trace_path.stem + "_runtime")
    runtime_parent.mkdir()
    runtime_config: FmuImportConfig = FmuImportConfig(
        fmu_path=fmu_path,
        preferred_mode=FmuInterfaceMode.CO_SIMULATION,
        communication_step=communication_step,
        relative_tolerance=1e-10,
        extraction_root=runtime_parent,
    )
    host: FmuRuntimeHost = open_fmu_runtime_host(runtime_config)
    variable_names: list[str] = [
        "angle", "speed", "electricalPower", "effectiveReactance",
    ]
    try:
        host.initialize(start_time=0.0, stop_time=4.0)
        with trace_path.open("x", encoding="utf-8", newline="\n") as trace_file:
            trace_handle: TextIO = trace_file
            writer: csv.writer = csv.writer(trace_handle, lineterminator="\n")
            writer.writerow([
                "sample_index", "time_seconds", "angle_rad", "speed_pu",
                "electrical_power_pu", "effective_reactance_pu",
            ])
            sample_index: int
            for sample_index in range(2001):
                time_value: float = sample_index * output_interval
                values: dict[str, float] = host.get_real(variable_names)
                writer.writerow([
                    sample_index, f"{time_value:.17e}", f"{values['angle']:.17e}",
                    f"{values['speed']:.17e}", f"{values['electricalPower']:.17e}",
                    f"{values['effectiveReactance']:.17e}",
                ])
                if sample_index < 2000:
                    substep_index: int
                    for substep_index in range(substeps_per_output):
                        communication_index: int = (
                            sample_index * substeps_per_output + substep_index
                        )
                        current_time: float = communication_index * communication_step
                        host.do_step(
                            current_time=current_time,
                            step_size=communication_step,
                        )
                else:
                    pass
    finally:
        host.close()
    if runtime_parent.is_dir() and len(tuple(runtime_parent.iterdir())) == 0:
        runtime_parent.rmdir()
    else:
        raise RuntimeError("VeraGrid runtime extraction was not released")
    (staging_directory / (trace_path.stem + ".log")).write_text(
        "execution=VeraGridEngine.IO.fmu.host.open_fmu_runtime_host\n"
        "backend=FMPy FMI 2 native binding\n"
        f"communication_step_seconds={communication_step:.17e}\n"
        f"output_interval_seconds={output_interval:.17e}\n"
        "status=completed\n",
        encoding="utf-8", newline="\n",
    )
    return _parse_smib_trace_csv(trace_path, "VeraGrid")

def _execute_fmpy_smib_trace(
    fmu_path: Path,
    staging_directory: Path,
    communication_step: float,
    output_interval: float,
) -> SmibTrace:
    """Execute the same SMIB FMU through direct public FMPy simulation.

    :param fmu_path: Exact OpenModelica-produced FMI 2 CS archive.
    :param staging_directory: Existing owned comparison staging directory.
    :param communication_step: FMI communication step in seconds.
    :param output_interval: Retained comparison interval in seconds.
    :return: Validated direct-FMPy trace.
    """

    substeps_per_output: int = int(round(output_interval / communication_step))
    total_communication_steps: int = int(round(4.0 / communication_step))
    result: np.ndarray = simulate_fmu(
        filename=str(fmu_path), validate=True, start_time=0.0, stop_time=4.0,
        step_size=communication_step, relative_tolerance=1e-10,
        output_interval=communication_step, record_events=False,
        fmi_type="CoSimulation",
        output=("angle", "speed", "electricalPower", "effectiveReactance"),
        timeout=60.0,
    )
    raw_shape_is_valid: bool = bool(
        result.shape[0] == total_communication_steps + 1
        and substeps_per_output == 16
    )
    if raw_shape_is_valid:
        retained_result: np.ndarray = result[::substeps_per_output]
    else:
        raise RuntimeError("Direct FMPy did not return the exact communication lattice")
    if retained_result.shape[0] == 2001:
        pass
    else:
        raise RuntimeError("Direct FMPy did not retain the exact SMIB output lattice")
    trace_path: Path = staging_directory / "fmpy_trace.csv"
    with trace_path.open("x", encoding="utf-8", newline="\n") as trace_file:
        trace_handle: TextIO = trace_file
        writer: csv.writer = csv.writer(trace_handle, lineterminator="\n")
        writer.writerow([
            "sample_index", "time_seconds", "angle_rad", "speed_pu",
            "electrical_power_pu", "effective_reactance_pu",
        ])
        sample_index: int
        for sample_index in range(2001):
            writer.writerow([
                sample_index, f"{float(retained_result['time'][sample_index]):.17e}",
                f"{float(retained_result['angle'][sample_index]):.17e}",
                f"{float(retained_result['speed'][sample_index]):.17e}",
                f"{float(retained_result['electricalPower'][sample_index]):.17e}",
                f"{float(retained_result['effectiveReactance'][sample_index]):.17e}",
            ])
    (staging_directory / "fmpy.log").write_text(
        "execution=fmpy.simulate_fmu\ninterface=CoSimulation\n"
        f"communication_step_seconds={communication_step:.17e}\n"
        f"output_interval_seconds={output_interval:.17e}\n"
        "status=completed\n",
        encoding="utf-8", newline="\n",
    )
    return _parse_smib_trace_csv(trace_path, "FMPy")

def _execute_omsimulator_smib_trace(
    executable_path: Path,
    fmu_path: Path,
    staging_directory: Path,
    timeout_seconds: float,
) -> SmibTrace:
    """Execute the SMIB FMU through the shared bounded OMSimulator owner.

    :param executable_path: Authenticated OMSimulator executable.
    :param fmu_path: Exact OpenModelica-produced FMI 2 CS archive.
    :param staging_directory: Existing comparison staging directory.
    :param timeout_seconds: Native process deadline.
    :return: Validated OMSimulator trace.
    """

    runtime_directory: Path = Path(
        tempfile.mkdtemp(prefix=".smib-oms-runtime-", dir=str(staging_directory))
    ).resolve(strict=True)
    driver_source: Path = Path(__file__).resolve(strict=True).with_name(
        "smib_omsimulator_driver.lua"
    )
    if not driver_source.is_symlink() and driver_source.is_file():
        pass
    else:
        raise RuntimeError("SMIB OMSimulator driver is absent or unsafe")
    try:
        shutil.copyfile(fmu_path, runtime_directory / "model.fmu")
        shutil.copyfile(driver_source, runtime_directory / driver_source.name)
        process_arguments: tuple[str, ...] = (
            "--workingDir=.", "--tempDir=temp", "--deleteTempFiles=true",
            "--logFile=omsimulator.log", "--suppressPath=true", "--timeout=60",
            driver_source.name,
        )
        run_bounded_omsimulator_process(
            executable_path=executable_path,
            runtime_dir=runtime_directory,
            process_arguments=process_arguments,
            timeout_seconds=timeout_seconds,
        )
        retained_trace: Path = staging_directory / "omsimulator_trace.csv"
        shutil.copyfile(runtime_directory / "smib_omsimulator_trace.csv", retained_trace)
        shutil.copyfile(
            runtime_directory / "omsimulator_stdout.log",
            staging_directory / "omsimulator_stdout.log",
        )
        shutil.copyfile(
            runtime_directory / "omsimulator_stderr.log",
            staging_directory / "omsimulator_stderr.log",
        )
        shutil.copyfile(
            runtime_directory / "omsimulator.log",
            staging_directory / "omsimulator.log",
        )
    finally:
        shutil.rmtree(runtime_directory)
    return _parse_smib_trace_csv(retained_trace, "OMSimulator")


def _evaluate_smib_pair(
    left_trace: SmibTrace,
    right_trace: SmibTrace,
) -> SmibComparisonMetrics:
    """Apply the strict same-FMU budget to every retained runtime row.

    :param left_trace: First runtime trajectory.
    :param right_trace: Second runtime trajectory.
    :return: Pairwise maxima and aggregate PASS state.
    """

    time_error: np.ndarray = np.abs(left_trace.time - right_trace.time)
    angle_error: np.ndarray = np.abs(left_trace.angle - right_trace.angle)
    speed_error: np.ndarray = np.abs(left_trace.speed - right_trace.speed)
    power_error: np.ndarray = np.abs(
        left_trace.electrical_power - right_trace.electrical_power
    )
    reactance_error: np.ndarray = np.abs(
        left_trace.effective_reactance - right_trace.effective_reactance
    )
    angle_budget: np.ndarray = 1e-12 + 1e-11 * np.maximum(
        np.abs(left_trace.angle), np.abs(right_trace.angle)
    )
    speed_budget: np.ndarray = 1e-12 + 1e-11 * np.maximum(
        np.abs(left_trace.speed), np.abs(right_trace.speed)
    )
    power_budget: np.ndarray = 1e-12 + 1e-11 * np.maximum(
        np.abs(left_trace.electrical_power), np.abs(right_trace.electrical_power)
    )
    passed: bool = bool(
        np.max(time_error) <= 1e-12
        and np.all(angle_error <= angle_budget)
        and np.all(speed_error <= speed_budget)
        and np.all(power_error <= power_budget)
        and np.max(reactance_error) <= 1e-12
    )
    return SmibComparisonMetrics(
        left_tool=left_trace.tool_name,
        right_tool=right_trace.tool_name,
        max_angle_error=float(np.max(angle_error)),
        max_speed_error=float(np.max(speed_error)),
        max_electrical_power_error=float(np.max(power_error)),
        max_effective_reactance_error=float(np.max(reactance_error)),
        passed=passed,
    )


def _evaluate_smib_native_fidelity(
    native_trace: SmibTrace,
    candidate_trace: SmibTrace,
) -> SmibNativeFidelityMetrics:
    """Compare one retained runtime trace with native DASSL exactly.

    :param native_trace: OpenModelica native DASSL reference.
    :param candidate_trace: Finest-grid FMI runtime trajectory.
    :return: Reproducible absolute and normalized fidelity metrics.
    """

    native_signals: np.ndarray = np.column_stack((
        native_trace.angle, native_trace.speed, native_trace.electrical_power,
    ))
    candidate_signals: np.ndarray = np.column_stack((
        candidate_trace.angle, candidate_trace.speed,
        candidate_trace.electrical_power,
    ))
    signal_baselines: np.ndarray = np.array(native_signals[0, :], copy=True)
    response_scales: np.ndarray = np.max(
        np.abs(native_signals - signal_baselines), axis=0
    )
    scales_are_valid: bool = bool(
        response_scales.shape == (3,)
        and np.all(np.isfinite(response_scales))
        and np.all(response_scales > 1e-5)
    )
    if scales_are_valid:
        pass
    else:
        raise RuntimeError("Native SMIB response scales are not material")
    absolute_errors: np.ndarray = np.abs(candidate_signals - native_signals)
    max_absolute_errors: np.ndarray = np.max(absolute_errors, axis=0)
    rms_absolute_errors: np.ndarray = np.sqrt(
        np.sum(absolute_errors * absolute_errors, axis=0) / 2001.0
    )
    normalized_max_errors: np.ndarray = max_absolute_errors / response_scales
    normalized_rms_errors: np.ndarray = rms_absolute_errors / response_scales
    max_reactance_error: float = float(np.max(np.abs(
        candidate_trace.effective_reactance - native_trace.effective_reactance
    )))
    passed: bool = bool(
        np.all(normalized_max_errors <= 0.01)
        and np.all(normalized_rms_errors <= 0.005)
        and max_reactance_error <= 1e-12
    )
    return SmibNativeFidelityMetrics(
        tool_name=candidate_trace.tool_name,
        signal_baselines=signal_baselines,
        response_scales=response_scales,
        max_absolute_errors=max_absolute_errors,
        rms_absolute_errors=rms_absolute_errors,
        normalized_max_errors=normalized_max_errors,
        normalized_rms_errors=normalized_rms_errors,
        max_effective_reactance_error=max_reactance_error,
        passed=passed,
    )


def _evaluate_smib_convergence(
    native_trace: SmibTrace,
    candidate_traces: tuple[SmibTrace, ...],
    step_sizes: tuple[float, ...],
) -> SmibConvergenceMetrics:
    """Evaluate first-order convergence on five retained VeraGrid traces.

    :param native_trace: OpenModelica native DASSL reference.
    :param candidate_traces: Five VeraGrid traces from coarse to fine.
    :param step_sizes: Matching descending communication steps.
    :return: Normalized errors, adjacent ratios and PASS state.
    """

    if len(candidate_traces) == 5 and len(step_sizes) == 5:
        pass
    else:
        raise ValueError("SMIB convergence requires exactly five grids")
    normalized_max_errors: np.ndarray = np.zeros((5, 3), dtype=float)
    normalized_rms_errors: np.ndarray = np.zeros((5, 3), dtype=float)
    grid_index: int
    for grid_index in range(5):
        fidelity: SmibNativeFidelityMetrics = _evaluate_smib_native_fidelity(
            native_trace, candidate_traces[grid_index]
        )
        normalized_max_errors[grid_index, :] = fidelity.normalized_max_errors
        normalized_rms_errors[grid_index, :] = fidelity.normalized_rms_errors
    denominators_are_valid: bool = bool(
        np.all(np.isfinite(normalized_max_errors[1:, :]))
        and np.all(normalized_max_errors[1:, :] > 0.0)
    )
    if denominators_are_valid:
        refinement_ratios: np.ndarray = (
            normalized_max_errors[:-1, :] / normalized_max_errors[1:, :]
        )
    else:
        raise RuntimeError("SMIB convergence ratio denominator is invalid")
    passed: bool = bool(
        np.all(normalized_max_errors[:-1, :] > normalized_max_errors[1:, :])
        and np.all(refinement_ratios >= 1.8)
        and np.all(refinement_ratios <= 2.2)
    )
    return SmibConvergenceMetrics(
        step_sizes=np.array(step_sizes, dtype=float),
        normalized_max_errors=normalized_max_errors,
        normalized_rms_errors=normalized_rms_errors,
        refinement_ratios=refinement_ratios,
        passed=passed,
    )

def _render_smib_comparison_figures(
    traces: tuple[SmibTrace, ...],
    convergence: SmibConvergenceMetrics,
    staging_directory: Path,
) -> tuple[Path, ...]:
    """Render exact-size trajectory, native-error and convergence figures.

    :param traces: Native DASSL followed by three accepted FMI runtime traces.
    :param convergence: Accepted five-grid convergence metrics.
    :param staging_directory: Existing comparison staging directory.
    :return: Nine PNG, PDF and SVG figure paths.
    """

    generated_paths: list[Path] = list()
    with matplotlib.rc_context({
        "font.family": "DejaVu Sans", "font.size": 8.5,
        "axes.linewidth": 0.8, "axes.grid": True, "grid.alpha": 0.22,
        "grid.linewidth": 0.6, "legend.frameon": False,
        "svg.fonttype": "none", "pdf.fonttype": 42,
    }):
        colors: tuple[str, ...] = ("#000000", "#4477AA", "#228833", "#AA3377")
        styles: tuple[str, ...] = ("-", "--", "-.", ":")
        markers: tuple[str, ...] = ("", "o", "s", "^")
        signal_labels: tuple[str, ...] = (
            "Rotor angle [rad]", "Rotor speed [p.u.]",
            "Electrical power [p.u.]", "Network reactance [p.u.]",
        )
        trajectory_figure: Figure = Figure(figsize=(7.2, 7.0), constrained_layout=True)
        FigureCanvasAgg(trajectory_figure)
        trajectory_axes: np.ndarray = trajectory_figure.subplots(4, 1, sharex=True)
        trace_index: int
        signal_index: int
        for trace_index in range(len(traces)):
            trace: SmibTrace = traces[trace_index]
            trace_signals: tuple[np.ndarray, ...] = (
                trace.angle, trace.speed, trace.electrical_power,
                trace.effective_reactance,
            )
            for signal_index in range(len(trace_signals)):
                axis: Axes = trajectory_axes[signal_index]
                axis.plot(
                    trace.time, trace_signals[signal_index],
                    color=colors[trace_index], linestyle=styles[trace_index],
                    linewidth=1.15, marker=markers[trace_index], markevery=160,
                    markersize=2.2, label=trace.tool_name,
                )
                axis.set_ylabel(signal_labels[signal_index])
        for axis in trajectory_axes:
            axis.axvline(1.001, color="#666666", linewidth=0.8, alpha=0.75)
            axis.axvline(1.151, color="#666666", linewidth=0.8, alpha=0.75)
        trajectory_axes[0].annotate(
            "Fault on", xy=(1.001, 1.0), xycoords=("data", "axes fraction"),
            xytext=(-3, -3), textcoords="offset points", ha="right", va="top",
        )
        trajectory_axes[0].annotate(
            "Fault clear", xy=(1.151, 1.0), xycoords=("data", "axes fraction"),
            xytext=(3, -3), textcoords="offset points", ha="left", va="top",
        )
        trajectory_axes[0].legend(ncols=4, loc="best")
        trajectory_axes[0].set_title("SMIB response: native DASSL and FMI 2 CS runtimes")
        trajectory_axes[-1].set_xlabel("Time [s]")
        extension: str
        for extension in ("png", "pdf", "svg"):
            trajectory_path: Path = staging_directory / f"smib-trajectories.{extension}"
            if extension == "png":
                trajectory_figure.savefig(trajectory_path, dpi=300, facecolor="white")
            else:
                trajectory_figure.savefig(trajectory_path, facecolor="white")
            generated_paths.append(trajectory_path)
        trajectory_figure.clear()

        native_trace: SmibTrace = traces[0]
        error_labels: tuple[str, ...] = (
            "|Angle error| [rad]", "|Speed error| [p.u.]", "|Power error| [p.u.]",
        )
        error_figure: Figure = Figure(figsize=(7.2, 5.4), constrained_layout=True)
        FigureCanvasAgg(error_figure)
        error_axes: np.ndarray = error_figure.subplots(3, 1, sharex=True)
        native_signals: tuple[np.ndarray, ...] = (
            native_trace.angle, native_trace.speed, native_trace.electrical_power,
        )
        for trace_index in range(1, len(traces)):
            trace = traces[trace_index]
            candidate_signals: tuple[np.ndarray, ...] = (
                trace.angle, trace.speed, trace.electrical_power,
            )
            for signal_index in range(3):
                error_values: np.ndarray = np.abs(
                    candidate_signals[signal_index] - native_signals[signal_index]
                )
                axis = error_axes[signal_index]
                axis.plot(
                    trace.time, error_values, color=colors[trace_index],
                    linestyle=styles[trace_index], linewidth=1.15,
                    label=f"{trace.tool_name} vs DASSL",
                )
                axis.set_ylabel(error_labels[signal_index])
        for axis in error_axes:
            axis.axvline(1.001, color="#666666", linewidth=0.8, alpha=0.75)
            axis.axvline(1.151, color="#666666", linewidth=0.8, alpha=0.75)
        error_axes[0].legend(ncols=3, loc="best")
        error_axes[0].set_title("Absolute fidelity error relative to native DASSL")
        error_axes[-1].set_xlabel("Time [s]")
        for extension in ("png", "pdf", "svg"):
            error_path: Path = staging_directory / f"smib-native-errors.{extension}"
            if extension == "png":
                error_figure.savefig(error_path, dpi=300, facecolor="white")
            else:
                error_figure.savefig(error_path, facecolor="white")
            generated_paths.append(error_path)
        error_figure.clear()

        convergence_figure: Figure = Figure(figsize=(7.2, 4.5), constrained_layout=True)
        FigureCanvasAgg(convergence_figure)
        convergence_axis: Axes = convergence_figure.subplots(1, 1)
        convergence_labels: tuple[str, ...] = ("Angle", "Speed", "Electrical power")
        for signal_index in range(3):
            convergence_axis.loglog(
                convergence.step_sizes,
                convergence.normalized_max_errors[:, signal_index],
                color=colors[signal_index + 1], linestyle=styles[signal_index + 1],
                marker=markers[signal_index + 1], markersize=4.0,
                linewidth=1.2, label=convergence_labels[signal_index],
            )
        first_order_reference: np.ndarray = (
            convergence.normalized_max_errors[-1, 0]
            * convergence.step_sizes / convergence.step_sizes[-1]
        )
        convergence_axis.loglog(
            convergence.step_sizes, first_order_reference,
            color="#555555", linestyle="--", linewidth=1.0,
            label="First-order slope",
        )
        convergence_axis.set_xlabel("Communication step [s]")
        convergence_axis.set_ylabel("Response-normalized maximum error [-]")
        convergence_axis.set_title("Forward-Euler convergence relative to native DASSL")
        convergence_axis.legend(loc="best")
        convergence_axis.invert_xaxis()
        for extension in ("png", "pdf", "svg"):
            convergence_path: Path = staging_directory / f"smib-convergence.{extension}"
            if extension == "png":
                convergence_figure.savefig(convergence_path, dpi=300, facecolor="white")
            else:
                convergence_figure.savefig(convergence_path, facecolor="white")
            generated_paths.append(convergence_path)
        convergence_figure.clear()
    return tuple(generated_paths)

def _publish_smib_comparison(
    staging_directory: Path,
    config: SmibComparisonConfig,
    traces: tuple[SmibTrace, ...],
    runtime_metrics: tuple[SmibComparisonMetrics, ...],
    fidelity_metrics: tuple[SmibNativeFidelityMetrics, ...],
    convergence: SmibConvergenceMetrics,
    oms_version: str,
    oms_sha256: str,
    fmpy_version: str,
    fmpy_sha256: str,
) -> Path:
    """Write the closed manifest after every numerical oracle passes.

    :param staging_directory: Complete comparison staging directory.
    :param config: Exact comparison configuration.
    :param traces: Native DASSL followed by three accepted runtime trajectories.
    :param runtime_metrics: Three strict same-FMU pair results.
    :param fidelity_metrics: Three native-DASSL fidelity results.
    :param convergence: Five-grid VeraGrid convergence evidence.
    :param oms_version: Observed OMSimulator version.
    :param oms_sha256: Observed OMSimulator digest.
    :param fmpy_version: Observed FMPy version.
    :param fmpy_sha256: Observed FMPy distribution digest.
    :return: Written manifest path.
    """

    artifact_records: list[dict[str, object]] = list()
    artifact_path: Path
    for artifact_path in sorted(staging_directory.iterdir()):
        if artifact_path.is_file() and artifact_path.name != "manifest.json":
            content: bytes = artifact_path.read_bytes()
            artifact_records.append(dict(
                path=artifact_path.name, size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
            ))
        else:
            raise RuntimeError("SMIB staging contains an unexpected directory")

    runtime_metric_records: list[dict[str, object]] = list()
    metric: SmibComparisonMetrics
    for metric in runtime_metrics:
        runtime_metric_records.append(dict(
            left_tool=metric.left_tool,
            right_tool=metric.right_tool,
            max_angle_error=metric.max_angle_error,
            max_speed_error=metric.max_speed_error,
            max_electrical_power_error=metric.max_electrical_power_error,
            max_effective_reactance_error=metric.max_effective_reactance_error,
            passed=metric.passed,
        ))
    fidelity_records: list[dict[str, object]] = list()
    fidelity: SmibNativeFidelityMetrics
    for fidelity in fidelity_metrics:
        fidelity_records.append(dict(
            tool_name=fidelity.tool_name,
            signal_order=["angle_rad", "speed_pu", "electrical_power_pu"],
            signal_baselines=fidelity.signal_baselines.tolist(),
            response_scales=fidelity.response_scales.tolist(),
            max_absolute_errors=fidelity.max_absolute_errors.tolist(),
            rms_absolute_errors=fidelity.rms_absolute_errors.tolist(),
            normalized_max_errors=fidelity.normalized_max_errors.tolist(),
            normalized_rms_errors=fidelity.normalized_rms_errors.tolist(),
            max_effective_reactance_error=fidelity.max_effective_reactance_error,
            passed=fidelity.passed,
        ))
    manifest: dict[str, object] = dict(
        schema="veragrid.fmi-smib-open-source-comparison/2",
        status="CANDIDATE_EVIDENCE",
        claim_scope=(
            "FMI 2 Co-Simulation dynamic interoperability for one OpenModelica "
            "SMIB on the recorded Windows host; not certification or multiplatform evidence"
        ),
        source=dict(
            path=str(config.build_evidence.source_path),
            size_bytes=config.build_evidence.source_size_bytes,
            sha256=config.build_evidence.source_sha256,
        ),
        fmu=dict(
            path=str(config.build_evidence.fmu_path),
            sha256=config.build_evidence.fmu_sha256,
        ),
        tools=[
            dict(
                name="OpenModelica", version=config.build_evidence.omc_version,
                sha256=config.build_evidence.omc_sha256, solver="DASSL native reference",
            ),
            dict(name="VeraGrid", backend="FMPy FMI 2 public runtime host"),
            dict(name="FMPy", version=fmpy_version, sha256=fmpy_sha256),
            dict(name="OMSimulator", version=oms_version, sha256=oms_sha256),
        ],
        configuration=dict(
            start_time_seconds=0.0, stop_time_seconds=4.0,
            communication_step_seconds=config.communication_step,
            output_interval_seconds=config.output_interval,
            convergence_step_sizes_seconds=list(config.convergence_step_sizes),
            sample_count=2001, fault_start_seconds=1.001,
            fault_end_seconds=1.151,
            strict_absolute_tolerance=1e-12,
            strict_relative_tolerance=1e-11,
            normalized_maximum_tolerance=0.01,
            normalized_rms_tolerance=0.005,
            signal_order=["angle_rad", "speed_pu", "electrical_power_pu"],
        ),
        runtime_metrics=runtime_metric_records,
        native_fidelity=fidelity_records,
        convergence=dict(
            signal_order=["angle_rad", "speed_pu", "electrical_power_pu"],
            step_sizes=convergence.step_sizes.tolist(),
            normalized_max_errors=convergence.normalized_max_errors.tolist(),
            normalized_rms_errors=convergence.normalized_rms_errors.tolist(),
            refinement_ratios=convergence.refinement_ratios.tolist(),
            passed=convergence.passed,
        ),
        artifacts=artifact_records,
    )
    manifest_path: Path = staging_directory / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    return manifest_path

def _verify_smib_comparison_package(
    staging_directory: Path,
    manifest_path: Path,
    config: SmibComparisonConfig,
) -> None:
    """Verify closed membership, artifact identity and reproducible metrics.

    :param staging_directory: Complete comparison staging directory.
    :param manifest_path: Manifest written after acceptance.
    :param config: Exact numerical grids used by the package.
    :return: None.
    """

    parsed: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    if isinstance(parsed, dict):
        manifest: dict[str, object] = cast(dict[str, object], parsed)
    else:
        raise RuntimeError("SMIB manifest root is invalid")
    runtime_value: object = manifest.get("runtime_metrics", None)
    fidelity_value: object = manifest.get("native_fidelity", None)
    convergence_value: object = manifest.get("convergence", None)
    artifacts_value: object = manifest.get("artifacts", None)
    manifest_is_valid: bool = bool(
        manifest.get("schema", None) == "veragrid.fmi-smib-open-source-comparison/2"
        and manifest.get("status", None) == "CANDIDATE_EVIDENCE"
        and isinstance(runtime_value, list)
        and len(runtime_value) == 3
        and isinstance(fidelity_value, list)
        and len(fidelity_value) == 3
        and isinstance(convergence_value, dict)
        and isinstance(artifacts_value, list)
    )
    if manifest_is_valid:
        runtime_records: list[object] = runtime_value
        fidelity_records: list[object] = fidelity_value
        convergence_record: dict[str, object] = cast(dict[str, object], convergence_value)
        artifacts: list[object] = artifacts_value
    else:
        raise RuntimeError("SMIB manifest sections are invalid")
    record_value: object
    for record_value in runtime_records:
        if isinstance(record_value, dict) and record_value.get("passed", None) is True:
            pass
        else:
            raise RuntimeError("SMIB manifest contains a failed runtime pair")
    for record_value in fidelity_records:
        if isinstance(record_value, dict) and record_value.get("passed", None) is True:
            pass
        else:
            raise RuntimeError("SMIB manifest contains a failed native-fidelity result")
    if convergence_record.get("passed", None) is True:
        pass
    else:
        raise RuntimeError("SMIB manifest contains failed convergence evidence")

    declared_names: set[str] = set()
    artifact_value: object
    for artifact_value in artifacts:
        if isinstance(artifact_value, dict):
            artifact: dict[str, object] = cast(dict[str, object], artifact_value)
        else:
            raise RuntimeError("SMIB artifact record is invalid")
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
            raise RuntimeError("SMIB artifact identity differs from its manifest")
    physical_names: set[str] = set()
    physical_path: Path
    for physical_path in staging_directory.iterdir():
        if physical_path.is_file():
            physical_names.add(physical_path.name)
        else:
            raise RuntimeError("SMIB package contains an undeclared directory")
    if physical_names == declared_names | {"manifest.json"}:
        pass
    else:
        raise RuntimeError("SMIB package membership is not closed")

    # Recompute all three numerical layers from authenticated retained traces.
    native_trace: SmibTrace = _parse_smib_trace_csv(
        staging_directory / "openmodelica_trace.csv", "OpenModelica"
    )
    runtime_traces: tuple[SmibTrace, ...] = (
        _parse_smib_trace_csv(staging_directory / "veragrid_trace.csv", "VeraGrid"),
        _parse_smib_trace_csv(staging_directory / "fmpy_trace.csv", "FMPy"),
        _parse_smib_trace_csv(staging_directory / "omsimulator_trace.csv", "OMSimulator"),
    )
    recomputed_runtime: tuple[SmibComparisonMetrics, ...] = (
        _evaluate_smib_pair(runtime_traces[0], runtime_traces[1]),
        _evaluate_smib_pair(runtime_traces[0], runtime_traces[2]),
        _evaluate_smib_pair(runtime_traces[1], runtime_traces[2]),
    )
    if all(metric.passed for metric in recomputed_runtime):
        pass
    else:
        raise RuntimeError("Authenticated traces fail strict runtime recomputation")
    runtime_index: int
    for runtime_index in range(3):
        runtime_record_value: object = runtime_records[runtime_index]
        runtime_metric: SmibComparisonMetrics = recomputed_runtime[runtime_index]
        if isinstance(runtime_record_value, dict):
            runtime_record: dict[str, object] = cast(
                dict[str, object], runtime_record_value
            )
        else:
            raise RuntimeError("SMIB runtime metric record is invalid")
        runtime_matches: bool = bool(
            runtime_record.get("left_tool", None) == runtime_metric.left_tool
            and runtime_record.get("right_tool", None) == runtime_metric.right_tool
            and runtime_record.get("max_angle_error", None)
            == runtime_metric.max_angle_error
            and runtime_record.get("max_speed_error", None)
            == runtime_metric.max_speed_error
            and runtime_record.get("max_electrical_power_error", None)
            == runtime_metric.max_electrical_power_error
            and runtime_record.get("max_effective_reactance_error", None)
            == runtime_metric.max_effective_reactance_error
            and runtime_record.get("passed", None) == runtime_metric.passed
        )
        if runtime_matches:
            pass
        else:
            raise RuntimeError("Manifest runtime metrics are not reproducible")
    recomputed_fidelity: tuple[SmibNativeFidelityMetrics, ...] = tuple(
        _evaluate_smib_native_fidelity(native_trace, trace) for trace in runtime_traces
    )
    if all(metric.passed for metric in recomputed_fidelity):
        pass
    else:
        raise RuntimeError("Authenticated traces fail native-fidelity recomputation")
    fidelity_index: int
    for fidelity_index in range(3):
        fidelity_record_value: object = fidelity_records[fidelity_index]
        fidelity_metric: SmibNativeFidelityMetrics = recomputed_fidelity[fidelity_index]
        if isinstance(fidelity_record_value, dict):
            fidelity_record: dict[str, object] = cast(
                dict[str, object], fidelity_record_value
            )
        else:
            raise RuntimeError("SMIB native-fidelity record is invalid")
        fidelity_matches: bool = bool(
            fidelity_record.get("tool_name", None) == fidelity_metric.tool_name
            and fidelity_record.get("signal_order", None)
            == ["angle_rad", "speed_pu", "electrical_power_pu"]
            and fidelity_record.get("signal_baselines", None)
            == fidelity_metric.signal_baselines.tolist()
            and fidelity_record.get("response_scales", None)
            == fidelity_metric.response_scales.tolist()
            and fidelity_record.get("max_absolute_errors", None)
            == fidelity_metric.max_absolute_errors.tolist()
            and fidelity_record.get("rms_absolute_errors", None)
            == fidelity_metric.rms_absolute_errors.tolist()
            and fidelity_record.get("normalized_max_errors", None)
            == fidelity_metric.normalized_max_errors.tolist()
            and fidelity_record.get("normalized_rms_errors", None)
            == fidelity_metric.normalized_rms_errors.tolist()
            and fidelity_record.get("max_effective_reactance_error", None)
            == fidelity_metric.max_effective_reactance_error
            and fidelity_record.get("passed", None) == fidelity_metric.passed
        )
        if fidelity_matches:
            pass
        else:
            raise RuntimeError("Manifest native-fidelity metrics are not reproducible")
    convergence_traces_list: list[SmibTrace] = list()
    grid_index: int
    for grid_index in range(5):
        if grid_index == 4:
            convergence_path: Path = staging_directory / "veragrid_trace.csv"
        else:
            convergence_path = staging_directory / f"veragrid_convergence_{grid_index}.csv"
        convergence_traces_list.append(
            _parse_smib_trace_csv(convergence_path, "VeraGrid")
        )
    recomputed_convergence: SmibConvergenceMetrics = _evaluate_smib_convergence(
        native_trace, tuple(convergence_traces_list), config.convergence_step_sizes
    )
    manifest_max_errors: np.ndarray = np.asarray(
        convergence_record.get("normalized_max_errors", None), dtype=float
    )
    manifest_rms_errors: np.ndarray = np.asarray(
        convergence_record.get("normalized_rms_errors", None), dtype=float
    )
    manifest_ratios: np.ndarray = np.asarray(
        convergence_record.get("refinement_ratios", None), dtype=float
    )
    convergence_matches: bool = bool(
        recomputed_convergence.passed
        and convergence_record.get("signal_order", None)
        == ["angle_rad", "speed_pu", "electrical_power_pu"]
        and convergence_record.get("step_sizes", None)
        == recomputed_convergence.step_sizes.tolist()
        and np.array_equal(
            manifest_max_errors, recomputed_convergence.normalized_max_errors
        )
        and np.array_equal(
            manifest_rms_errors, recomputed_convergence.normalized_rms_errors
        )
        and np.array_equal(manifest_ratios, recomputed_convergence.refinement_ratios)
    )
    if convergence_matches:
        pass
    else:
        raise RuntimeError("Manifest convergence values are not reproducible")

    # Verify exact raster geometry and editable vector-font evidence.
    figure_specs: tuple[tuple[str, int, int, float, float], ...] = (
        ("smib-trajectories", 2160, 2100, 518.4, 504.0),
        ("smib-native-errors", 2160, 1620, 518.4, 388.8),
        ("smib-convergence", 2160, 1350, 518.4, 324.0),
    )
    figure_spec: tuple[str, int, int, float, float]
    for figure_spec in figure_specs:
        figure_stem: str = figure_spec[0]
        png_bytes: bytes = (staging_directory / (figure_stem + ".png")).read_bytes()
        png_width: int = int.from_bytes(png_bytes[16:20], byteorder="big")
        png_height: int = int.from_bytes(png_bytes[20:24], byteorder="big")
        svg_text: str = (staging_directory / (figure_stem + ".svg")).read_text(
            encoding="utf-8"
        )
        pdf_bytes: bytes = (staging_directory / (figure_stem + ".pdf")).read_bytes()
        svg_size_matches: bool = bool(
            f'width="{figure_spec[3]:g}pt"' in svg_text
            and f'height="{figure_spec[4]:g}pt"' in svg_text
            and "<text" in svg_text
        )
        pdf_width_pattern: bytes = f"{figure_spec[3]:g}".encode("ascii")
        pdf_height_pattern: bytes = f"{figure_spec[4]:g}".encode("ascii")
        pdf_size_matches: bool = bool(
            b"/MediaBox" in pdf_bytes
            and pdf_width_pattern in pdf_bytes
            and pdf_height_pattern in pdf_bytes
            and (b"/FontFile2" in pdf_bytes or b"/CIDFontType2" in pdf_bytes)
        )
        figure_matches: bool = bool(
            png_width == figure_spec[1]
            and png_height == figure_spec[2]
            and svg_size_matches
            and pdf_size_matches
        )
        if figure_matches:
            pass
        else:
            raise RuntimeError("SMIB figure geometry or vector fonts are invalid")

def generate_smib_comparison(config: SmibComparisonConfig) -> Path:
    """Execute four open-source paths and publish accepted dynamic evidence.

    :param config: Exact build evidence, tool identities and numerical grids.
    :return: Published SMIB comparison manifest path.
    """

    resolved_oms: Path
    oms_version: str
    oms_sha256: str
    fmpy_version: str
    fmpy_sha256: str
    resolved_oms, oms_version, oms_sha256, fmpy_version, fmpy_sha256 = (
        _validate_smib_comparison_config(config)
    )
    staging_directory: Path = Path(tempfile.mkdtemp(
        prefix=".smib-comparison-",
        dir=str(config.output_directory.parent.resolve(strict=True)),
    )).resolve(strict=True)
    publication_succeeded: bool = False
    try:
        # Retain the independent equation-level reference and original build logs.
        openmodelica_trace_path: Path = staging_directory / "openmodelica_trace.csv"
        shutil.copyfile(config.build_evidence.native_csv_path, openmodelica_trace_path)
        shutil.copyfile(
            config.build_evidence.build_stdout_path,
            staging_directory / "openmodelica_stdout.log",
        )
        shutil.copyfile(
            config.build_evidence.build_stderr_path,
            staging_directory / "openmodelica_stderr.log",
        )
        native_trace: SmibTrace = _parse_smib_trace_csv(
            openmodelica_trace_path, "OpenModelica"
        )

        # Execute five explicit communication grids through the public VeraGrid host.
        convergence_traces_list: list[SmibTrace] = list()
        grid_index: int
        for grid_index in range(5):
            grid_step: float = config.convergence_step_sizes[grid_index]
            if grid_index == 4:
                veragrid_trace_path: Path = staging_directory / "veragrid_trace.csv"
            else:
                veragrid_trace_path = (
                    staging_directory / f"veragrid_convergence_{grid_index}.csv"
                )
            grid_trace: SmibTrace = _execute_veragrid_smib_trace(
                fmu_path=config.build_evidence.fmu_path,
                staging_directory=staging_directory,
                trace_path=veragrid_trace_path,
                communication_step=grid_step,
                output_interval=config.output_interval,
            )
            convergence_traces_list.append(grid_trace)
        convergence_traces: tuple[SmibTrace, ...] = tuple(convergence_traces_list)
        veragrid_trace: SmibTrace = convergence_traces[-1]
        convergence: SmibConvergenceMetrics = _evaluate_smib_convergence(
            native_trace, convergence_traces, config.convergence_step_sizes
        )
        if convergence.passed:
            pass
        else:
            raise RuntimeError("VeraGrid SMIB convergence is not first order")

        # Independent consumers receive the identical finest communication lattice.
        fmpy_trace: SmibTrace = _execute_fmpy_smib_trace(
            config.build_evidence.fmu_path,
            staging_directory,
            config.communication_step,
            config.output_interval,
        )
        omsimulator_trace: SmibTrace = _execute_omsimulator_smib_trace(
            executable_path=resolved_oms,
            fmu_path=config.build_evidence.fmu_path,
            staging_directory=staging_directory,
            timeout_seconds=config.process_timeout_seconds,
        )
        runtime_traces: tuple[SmibTrace, ...] = (
            veragrid_trace, fmpy_trace, omsimulator_trace,
        )
        traces: tuple[SmibTrace, ...] = (native_trace,) + runtime_traces

        # Both internal events are verified at the first retained post-event rows.
        expected_reactance: np.ndarray = np.full(2001, 0.6, dtype=float)
        expected_reactance[501:576] = 1.2
        trace: SmibTrace
        for trace in traces:
            initial_residual_is_valid: bool = bool(
                abs(trace.speed[0] - 1.0) <= 1e-12
                and abs(trace.electrical_power[0] - 0.8) <= 1e-9
            )
            dynamics_are_material: bool = bool(
                np.max(np.abs(trace.speed - 1.0)) >= 1e-5
                and np.max(np.abs(trace.angle - trace.angle[0])) >= 1e-5
            )
            events_are_exact: bool = bool(
                np.max(np.abs(trace.effective_reactance - expected_reactance)) <= 1e-12
                and trace.effective_reactance[501] == 1.2
                and trace.effective_reactance[576] == 0.6
            )
            if initial_residual_is_valid and dynamics_are_material and events_are_exact:
                pass
            else:
                raise RuntimeError(
                    f"{trace.tool_name} failed steady-state, dynamic or event checks"
                )

        runtime_metrics: tuple[SmibComparisonMetrics, ...] = (
            _evaluate_smib_pair(runtime_traces[0], runtime_traces[1]),
            _evaluate_smib_pair(runtime_traces[0], runtime_traces[2]),
            _evaluate_smib_pair(runtime_traces[1], runtime_traces[2]),
        )
        if all(metric.passed for metric in runtime_metrics):
            pass
        else:
            raise RuntimeError("Same-FMU runtime traces exceeded the strict budget")
        fidelity_metrics: tuple[SmibNativeFidelityMetrics, ...] = tuple(
            _evaluate_smib_native_fidelity(native_trace, trace)
            for trace in runtime_traces
        )
        if all(metric.passed for metric in fidelity_metrics):
            pass
        else:
            raise RuntimeError("One FMI runtime exceeded native DASSL fidelity limits")

        _render_smib_comparison_figures(traces, convergence, staging_directory)
        manifest_path: Path = _publish_smib_comparison(
            staging_directory, config, traces, runtime_metrics, fidelity_metrics,
            convergence, oms_version, oms_sha256, fmpy_version, fmpy_sha256,
        )
        _verify_smib_comparison_package(staging_directory, manifest_path, config)
        if not config.output_directory.exists():
            os.replace(staging_directory, config.output_directory)
            publication_succeeded = True
        else:
            raise RuntimeError("SMIB output directory appeared before publication")
    finally:
        if publication_succeeded:
            pass
        else:
            if staging_directory.exists():
                shutil.rmtree(staging_directory)
            else:
                pass
    return config.output_directory / "manifest.json"
