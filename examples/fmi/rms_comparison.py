# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import sys
import tempfile

import matplotlib
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np

from VeraGridEngine.IO.fmu.CosimulationInterface.validate import (
    simulate_fmu_with_fmpy as simulate_cs_fmu_with_fmpy,
    validate_fmu_with_fmpy as validate_cs_fmu_with_fmpy,
)
from VeraGridEngine.IO.fmu.ExportInterface.validate import (
    simulate_fmu_with_fmpy as simulate_me_fmu_with_fmpy,
    validate_fmu_with_fmpy as validate_me_fmu_with_fmpy,
)
from examples.fmi.fmi_example_runner import (
    RmsFmiExampleExecution,
    execute_rms_fmi_example,
)
from examples.fmi.event_scenario import (
    RmsLoadPowerStepScenario,
    build_default_rms_load_power_step_scenario,
)
from examples.fmi.omsimulator import (
    OmsimulatorTrace,
    _verify_regular_file_path,
    execute_omsimulator_trace,
)
from VeraGridEngine.IO.fmu.model_description import FmuInterfaceMode


class RmsFmiComparisonConfig:
    """Own the explicit inputs of one RMS FMI comparison package."""

    __slots__ = (
        "_output_dir",
        "_source_revision",
        "_source_tree_sha256",
        "_absolute_tolerance",
        "_relative_tolerance",
        "_omsimulator_executable",
        "_omsimulator_timeout_seconds",
        "_omsimulator_absolute_tolerance",
        "_omsimulator_relative_tolerance",
        "_scenario",
    )

    def __init__(
            self,
            output_dir: Path,
            source_revision: str,
            source_tree_sha256: str,
            omsimulator_executable: Path,
            absolute_tolerance: float = 1.0e-12,
            relative_tolerance: float = 1.0e-10,
            omsimulator_timeout_seconds: float = 35.0,
            omsimulator_absolute_tolerance: float = 1.0e-10,
            omsimulator_relative_tolerance: float = 1.0e-10,
            scenario: RmsLoadPowerStepScenario | None = None,
    ) -> None:
        """Validate and retain the caller-declared comparison configuration.

        :param output_dir: Final package directory, which must not exist.
        :param source_revision: Caller-declared source revision.
        :param source_tree_sha256: Caller-declared SHA-256 of the complete source tree.
        :param omsimulator_executable: Explicit regular OMSimulator executable.
        :param absolute_tolerance: Floating-point absolute comparison term.
        :param relative_tolerance: Floating-point relative comparison term.
        :param omsimulator_timeout_seconds: Python-side process deadline.
        :param omsimulator_absolute_tolerance: OMSimulator absolute solver allowance.
        :param omsimulator_relative_tolerance: OMSimulator relative solver allowance.
        :param scenario: Validated benchmark scenario, or None for the maintained default.
        :return: None.
        """

        # Retain one validated scenario copy so later caller mutation cannot
        # change the configuration shared by both FMI modes.
        active_scenario: RmsLoadPowerStepScenario
        if scenario is None:
            active_scenario = build_default_rms_load_power_step_scenario()
        elif isinstance(scenario, RmsLoadPowerStepScenario):
            active_scenario = scenario.copy_validated()
        else:
            raise TypeError("RMS FMI comparison scenario has an unsupported type")

        revision_is_valid: bool = bool(source_revision.strip())
        tree_hash_is_valid: bool = bool(
            len(source_tree_sha256) == 64
            and source_tree_sha256 == source_tree_sha256.lower()
            and all(
                character in "0123456789abcdef"
                for character in source_tree_sha256
            )
        )
        tolerances_are_valid: bool = bool(
            math.isfinite(absolute_tolerance)
            and absolute_tolerance > 0.0
            and math.isfinite(relative_tolerance)
            and relative_tolerance >= 0.0
            and math.isfinite(omsimulator_timeout_seconds)
            and omsimulator_timeout_seconds == 35.0
            and math.isfinite(omsimulator_absolute_tolerance)
            and omsimulator_absolute_tolerance == 1.0e-10
            and math.isfinite(omsimulator_relative_tolerance)
            and omsimulator_relative_tolerance == 1.0e-10
        )
        resolved_omsimulator_executable: Path = _verify_regular_file_path(
            omsimulator_executable,
            None,
            "OMSimulator executable",
        )
        executable_is_valid: bool = True
        if revision_is_valid:
            pass
        else:
            raise ValueError("Source revision must be a non-empty caller declaration")
        if tree_hash_is_valid:
            pass
        else:
            raise ValueError("Source tree identity must be a lowercase SHA-256")
        if tolerances_are_valid:
            pass
        else:
            raise ValueError("Comparison tolerances must match the sealed contract")
        if executable_is_valid:
            pass
        else:
            raise ValueError("OMSimulator executable must be a regular non-symlink file")

        self._output_dir: Path = output_dir.resolve()
        self._source_revision: str = source_revision.strip()
        self._source_tree_sha256: str = source_tree_sha256
        self._absolute_tolerance: float = float(absolute_tolerance)
        self._relative_tolerance: float = float(relative_tolerance)
        self._omsimulator_executable: Path = resolved_omsimulator_executable
        self._omsimulator_timeout_seconds: float = float(omsimulator_timeout_seconds)
        self._omsimulator_absolute_tolerance: float = float(
            omsimulator_absolute_tolerance
        )
        self._omsimulator_relative_tolerance: float = float(
            omsimulator_relative_tolerance
        )
        self._scenario: RmsLoadPowerStepScenario = active_scenario

    def get_output_dir(self) -> Path:
        """Return the final package destination.

        :return: Resolved final directory.
        """

        return self._output_dir

    def get_source_revision(self) -> str:
        """Return the caller-declared source revision.

        :return: Source revision text.
        """

        return self._source_revision

    def get_source_tree_sha256(self) -> str:
        """Return the caller-declared source-tree SHA-256.

        :return: Lowercase SHA-256 text.
        """

        return self._source_tree_sha256

    def get_absolute_tolerance(self) -> float:
        """Return the floating-point absolute comparison term.

        :return: Absolute tolerance.
        """

        return self._absolute_tolerance

    def get_relative_tolerance(self) -> float:
        """Return the floating-point relative comparison term.

        :return: Relative tolerance.
        """

        return self._relative_tolerance

    def get_omsimulator_executable(self) -> Path:
        """Return the explicit OMSimulator executable.

        :return: Resolved regular executable path.
        """

        return self._omsimulator_executable

    def get_omsimulator_timeout_seconds(self) -> float:
        """Return the Python-side OMSimulator deadline.

        :return: Process timeout in seconds.
        """

        return self._omsimulator_timeout_seconds

    def get_omsimulator_absolute_tolerance(self) -> float:
        """Return the OMSimulator absolute solver allowance.

        :return: Absolute tolerance in p.u.
        """

        return self._omsimulator_absolute_tolerance

    def get_omsimulator_relative_tolerance(self) -> float:
        """Return the OMSimulator relative solver allowance.

        :return: Relative tolerance coefficient.
        """

        return self._omsimulator_relative_tolerance

    def get_scenario(self) -> RmsLoadPowerStepScenario:
        """Return an independent validated benchmark scenario.

        :return: Copy of the configured RMS load active-power step scenario.
        """

        return self._scenario.copy_validated()


class RmsFmiComparisonMetrics:
    """Own errors and per-sample budgets from one aligned FMI comparison."""

    __slots__ = (
        "_absolute_active_power_error",
        "_absolute_reactive_power_error",
        "_active_power_budget",
        "_reactive_power_budget",
        "_max_active_power_error",
        "_max_reactive_power_error",
        "_rms_active_power_error",
        "_rms_reactive_power_error",
    )

    def __init__(
            self,
            absolute_active_power_error: np.ndarray,
            absolute_reactive_power_error: np.ndarray,
            active_power_budget: np.ndarray,
            reactive_power_budget: np.ndarray,
    ) -> None:
        """Store one comparison result after all samples have passed.

        :param absolute_active_power_error: Absolute active-power errors in p.u.
        :param absolute_reactive_power_error: Absolute reactive-power errors in p.u.
        :param active_power_budget: Active-power acceptance budget per sample.
        :param reactive_power_budget: Reactive-power acceptance budget per sample.
        :return: None.
        """

        arrays_match: bool = bool(
            absolute_active_power_error.ndim == 1
            and absolute_reactive_power_error.shape
            == absolute_active_power_error.shape
            and active_power_budget.shape == absolute_active_power_error.shape
            and reactive_power_budget.shape == absolute_active_power_error.shape
            and absolute_active_power_error.size > 0
        )
        if arrays_match:
            pass
        else:
            raise ValueError("Comparison metric arrays must be aligned and non-empty")

        self._absolute_active_power_error: np.ndarray = np.array(
            absolute_active_power_error,
            dtype=float,
            copy=True,
        )
        self._absolute_reactive_power_error: np.ndarray = np.array(
            absolute_reactive_power_error,
            dtype=float,
            copy=True,
        )
        self._active_power_budget: np.ndarray = np.array(
            active_power_budget,
            dtype=float,
            copy=True,
        )
        self._reactive_power_budget: np.ndarray = np.array(
            reactive_power_budget,
            dtype=float,
            copy=True,
        )
        self._max_active_power_error: float = float(
            np.max(self._absolute_active_power_error)
        )
        self._max_reactive_power_error: float = float(
            np.max(self._absolute_reactive_power_error)
        )
        self._rms_active_power_error: float = float(
            np.sqrt(np.mean(np.square(self._absolute_active_power_error)))
        )
        self._rms_reactive_power_error: float = float(
            np.sqrt(np.mean(np.square(self._absolute_reactive_power_error)))
        )

    def get_absolute_active_power_error(self) -> np.ndarray:
        """Return a defensive copy of active-power errors.

        :return: Absolute active-power error by sample.
        """

        return self._absolute_active_power_error.copy()

    def get_absolute_reactive_power_error(self) -> np.ndarray:
        """Return a defensive copy of reactive-power errors.

        :return: Absolute reactive-power error by sample.
        """

        return self._absolute_reactive_power_error.copy()

    def get_active_power_budget(self) -> np.ndarray:
        """Return a defensive copy of active-power budgets.

        :return: Active-power acceptance budget by sample.
        """

        return self._active_power_budget.copy()

    def get_reactive_power_budget(self) -> np.ndarray:
        """Return a defensive copy of reactive-power budgets.

        :return: Reactive-power acceptance budget by sample.
        """

        return self._reactive_power_budget.copy()

    def get_max_active_power_error(self) -> float:
        """Return the maximum absolute active-power error.

        :return: Maximum active-power error in p.u.
        """

        return self._max_active_power_error

    def get_max_reactive_power_error(self) -> float:
        """Return the maximum absolute reactive-power error.

        :return: Maximum reactive-power error in p.u.
        """

        return self._max_reactive_power_error

    def get_rms_active_power_error(self) -> float:
        """Return the root-mean-square active-power error.

        :return: RMS active-power error in p.u.
        """

        return self._rms_active_power_error

    def get_rms_reactive_power_error(self) -> float:
        """Return the root-mean-square reactive-power error.

        :return: RMS reactive-power error in p.u.
        """

        return self._rms_reactive_power_error


class RmsFmiRetainedTrace:
    """Own the exact combined-CSV arrays used by verification and figures."""

    __slots__ = (
        "_time_seconds",
        "_voltage_magnitude",
        "_veragrid_active_power",
        "_fmpy_active_power",
        "_omsimulator_active_power",
        "_veragrid_reactive_power",
        "_fmpy_reactive_power",
        "_omsimulator_reactive_power",
        "_veragrid_fmpy_metrics",
        "_veragrid_omsimulator_metrics",
        "_fmpy_omsimulator_metrics",
    )

    def __init__(
            self,
            time_seconds: np.ndarray,
            voltage_magnitude: np.ndarray,
            veragrid_active_power: np.ndarray,
            fmpy_active_power: np.ndarray,
            omsimulator_active_power: np.ndarray,
            veragrid_reactive_power: np.ndarray,
            fmpy_reactive_power: np.ndarray,
            omsimulator_reactive_power: np.ndarray,
            veragrid_fmpy_metrics: RmsFmiComparisonMetrics,
            veragrid_omsimulator_metrics: RmsFmiComparisonMetrics,
            fmpy_omsimulator_metrics: RmsFmiComparisonMetrics,
    ) -> None:
        """Retain one verified 301-sample three-path comparison.

        :param time_seconds: Canonical time lattice read from the combined CSV.
        :param voltage_magnitude: Retained voltage input read from the CSV.
        :param veragrid_active_power: VeraGrid active-power trajectory.
        :param fmpy_active_power: Direct-FMPy active-power trajectory.
        :param omsimulator_active_power: OMSimulator active-power trajectory.
        :param veragrid_reactive_power: VeraGrid reactive-power trajectory.
        :param fmpy_reactive_power: Direct-FMPy reactive-power trajectory.
        :param omsimulator_reactive_power: OMSimulator reactive-power trajectory.
        :param veragrid_fmpy_metrics: Reconstructed VeraGrid--FMPy metrics.
        :param veragrid_omsimulator_metrics: Reconstructed VeraGrid--OMSimulator metrics.
        :param fmpy_omsimulator_metrics: Reconstructed FMPy--OMSimulator metrics.
        :return: None.
        """

        numerical_arrays: tuple[np.ndarray, ...] = (
            time_seconds,
            voltage_magnitude,
            veragrid_active_power,
            fmpy_active_power,
            omsimulator_active_power,
            veragrid_reactive_power,
            fmpy_reactive_power,
            omsimulator_reactive_power,
        )
        arrays_are_valid: bool = bool(
            all(value.shape == (301,) for value in numerical_arrays)
            and all(np.all(np.isfinite(value)) for value in numerical_arrays)
            and np.all(np.diff(time_seconds) > 0.0)
        )
        if arrays_are_valid:
            pass
        else:
            raise ValueError("Retained FMI comparison arrays must be finite and aligned")
        self._time_seconds: np.ndarray = np.array(time_seconds, dtype=float, copy=True)
        self._voltage_magnitude: np.ndarray = np.array(
            voltage_magnitude,
            dtype=float,
            copy=True,
        )
        self._veragrid_active_power: np.ndarray = np.array(
            veragrid_active_power,
            dtype=float,
            copy=True,
        )
        self._fmpy_active_power: np.ndarray = np.array(
            fmpy_active_power,
            dtype=float,
            copy=True,
        )
        self._omsimulator_active_power: np.ndarray = np.array(
            omsimulator_active_power,
            dtype=float,
            copy=True,
        )
        self._veragrid_reactive_power: np.ndarray = np.array(
            veragrid_reactive_power,
            dtype=float,
            copy=True,
        )
        self._fmpy_reactive_power: np.ndarray = np.array(
            fmpy_reactive_power,
            dtype=float,
            copy=True,
        )
        self._omsimulator_reactive_power: np.ndarray = np.array(
            omsimulator_reactive_power,
            dtype=float,
            copy=True,
        )
        self._veragrid_fmpy_metrics: RmsFmiComparisonMetrics = veragrid_fmpy_metrics
        self._veragrid_omsimulator_metrics: RmsFmiComparisonMetrics = (
            veragrid_omsimulator_metrics
        )
        self._fmpy_omsimulator_metrics: RmsFmiComparisonMetrics = (
            fmpy_omsimulator_metrics
        )

    def get_time_seconds(self) -> np.ndarray:
        """Return the canonical retained time lattice.

        :return: Defensive copy of time in seconds.
        """

        return self._time_seconds.copy()

    def get_voltage_magnitude(self) -> np.ndarray:
        """Return the retained shared voltage input.

        :return: Defensive copy of voltage magnitude in p.u.
        """

        return self._voltage_magnitude.copy()

    def get_veragrid_active_power(self) -> np.ndarray:
        """Return the retained VeraGrid active-power trace.

        :return: Defensive copy of active power in p.u.
        """

        return self._veragrid_active_power.copy()

    def get_fmpy_active_power(self) -> np.ndarray:
        """Return the retained direct-FMPy active-power trace.

        :return: Defensive copy of active power in p.u.
        """

        return self._fmpy_active_power.copy()

    def get_omsimulator_active_power(self) -> np.ndarray:
        """Return the retained OMSimulator active-power trace.

        :return: Defensive copy of active power in p.u.
        """

        return self._omsimulator_active_power.copy()

    def get_veragrid_reactive_power(self) -> np.ndarray:
        """Return the retained VeraGrid reactive-power trace.

        :return: Defensive copy of reactive power in p.u.
        """

        return self._veragrid_reactive_power.copy()

    def get_fmpy_reactive_power(self) -> np.ndarray:
        """Return the retained direct-FMPy reactive-power trace.

        :return: Defensive copy of reactive power in p.u.
        """

        return self._fmpy_reactive_power.copy()

    def get_omsimulator_reactive_power(self) -> np.ndarray:
        """Return the retained OMSimulator reactive-power trace.

        :return: Defensive copy of reactive power in p.u.
        """

        return self._omsimulator_reactive_power.copy()

    def get_veragrid_fmpy_metrics(self) -> RmsFmiComparisonMetrics:
        """Return reconstructed VeraGrid--FMPy metrics.

        :return: Immutable comparison-metrics owner.
        """

        return self._veragrid_fmpy_metrics

    def get_veragrid_omsimulator_metrics(self) -> RmsFmiComparisonMetrics:
        """Return reconstructed VeraGrid--OMSimulator metrics.

        :return: Immutable comparison-metrics owner.
        """

        return self._veragrid_omsimulator_metrics

    def get_fmpy_omsimulator_metrics(self) -> RmsFmiComparisonMetrics:
        """Return reconstructed FMPy--OMSimulator metrics.

        :return: Immutable comparison-metrics owner.
        """

        return self._fmpy_omsimulator_metrics


class RmsFmiModeEvidence:
    """Own one mode execution and every typed retained comparison input."""

    __slots__ = (
        "_execution",
        "_retained_trace",
        "_fmpy_raw_evidence",
        "_omsimulator_trace",
        "_process_arguments",
        "_veragrid_fmpy_metrics",
        "_veragrid_omsimulator_metrics",
        "_fmpy_omsimulator_metrics",
        "_fmu_sha256",
        "_fmpy_time_alignment_max_error_seconds",
    )

    def __init__(
            self,
            execution: RmsFmiExampleExecution,
            retained_trace: RmsFmiRetainedTrace,
            fmpy_raw_evidence: Path,
            omsimulator_trace: OmsimulatorTrace,
            process_arguments: tuple[str, ...],
            veragrid_fmpy_metrics: RmsFmiComparisonMetrics,
            veragrid_omsimulator_metrics: RmsFmiComparisonMetrics,
            fmpy_omsimulator_metrics: RmsFmiComparisonMetrics,
            fmu_sha256: str,
            fmpy_time_alignment_max_error_seconds: float,
    ) -> None:
        """Retain one complete mode after numerical and file validation.

        :param execution: Conclusive VeraGrid RMS execution.
        :param retained_trace: Combined CSV reread into a typed owner.
        :param fmpy_raw_evidence: Retained canonical direct-FMPy CSV.
        :param omsimulator_trace: Validated independent runtime trace.
        :param process_arguments: Immutable arguments passed to OMSimulator.
        :param veragrid_fmpy_metrics: VeraGrid--FMPy pair metrics.
        :param veragrid_omsimulator_metrics: VeraGrid--OMSimulator pair metrics.
        :param fmpy_omsimulator_metrics: FMPy--OMSimulator pair metrics.
        :param fmu_sha256: Stable per-mode FMU identity.
        :param fmpy_time_alignment_max_error_seconds: Exact retained alignment error.
        :return: None.
        """

        hash_is_valid: bool = bool(
            len(fmu_sha256) == 64
            and fmu_sha256 == fmu_sha256.lower()
            and all(character in "0123456789abcdef" for character in fmu_sha256)
        )
        retained_metrics: tuple[RmsFmiComparisonMetrics, ...] = (
            retained_trace.get_veragrid_fmpy_metrics(),
            retained_trace.get_veragrid_omsimulator_metrics(),
            retained_trace.get_fmpy_omsimulator_metrics(),
        )
        provided_metrics: tuple[RmsFmiComparisonMetrics, ...] = (
            veragrid_fmpy_metrics,
            veragrid_omsimulator_metrics,
            fmpy_omsimulator_metrics,
        )
        metrics_are_equal: bool = all(
            np.array_equal(
                provided_metric.get_absolute_active_power_error(),
                retained_metric.get_absolute_active_power_error(),
            )
            and np.array_equal(
                provided_metric.get_absolute_reactive_power_error(),
                retained_metric.get_absolute_reactive_power_error(),
            )
            and np.array_equal(
                provided_metric.get_active_power_budget(),
                retained_metric.get_active_power_budget(),
            )
            and np.array_equal(
                provided_metric.get_reactive_power_budget(),
                retained_metric.get_reactive_power_budget(),
            )
            for provided_metric, retained_metric in zip(
                provided_metrics,
                retained_metrics,
            )
        )
        evidence_is_valid: bool = bool(
            not fmpy_raw_evidence.is_symlink()
            and fmpy_raw_evidence.is_file()
            and fmpy_raw_evidence.stat().st_size <= 262144
            and len(process_arguments) > 0
            and math.isfinite(fmpy_time_alignment_max_error_seconds)
            and 0.0 <= fmpy_time_alignment_max_error_seconds <= 1.0e-12
            and metrics_are_equal
        )
        if hash_is_valid and evidence_is_valid:
            pass
        else:
            raise ValueError("RMS FMI mode evidence is incomplete or inconsistent")
        self._execution: RmsFmiExampleExecution = execution
        self._retained_trace: RmsFmiRetainedTrace = retained_trace
        self._fmpy_raw_evidence: Path = fmpy_raw_evidence.resolve(strict=True)
        self._omsimulator_trace: OmsimulatorTrace = omsimulator_trace
        self._process_arguments: tuple[str, ...] = tuple(process_arguments)
        self._veragrid_fmpy_metrics: RmsFmiComparisonMetrics = retained_metrics[0]
        self._veragrid_omsimulator_metrics: RmsFmiComparisonMetrics = (
            retained_metrics[1]
        )
        self._fmpy_omsimulator_metrics: RmsFmiComparisonMetrics = retained_metrics[2]
        self._fmu_sha256: str = fmu_sha256
        self._fmpy_time_alignment_max_error_seconds: float = float(
            fmpy_time_alignment_max_error_seconds
        )
    def get_execution(self) -> RmsFmiExampleExecution:
        """Return the conclusive VeraGrid execution owner.

        :return: Mode-specific execution evidence.
        """

        return self._execution

    def get_retained_trace(self) -> RmsFmiRetainedTrace:
        """Return the combined-CSV retained trace owner.

        :return: Verified retained trace.
        """

        return self._retained_trace

    def get_fmpy_raw_evidence(self) -> Path:
        """Return the canonical direct-FMPy raw CSV path.

        :return: Strictly resolved retained CSV path.
        """

        return self._fmpy_raw_evidence

    def get_omsimulator_trace(self) -> OmsimulatorTrace:
        """Return the validated OMSimulator trace owner.

        :return: Independent-runtime trace evidence.
        """

        return self._omsimulator_trace

    def get_process_arguments(self) -> tuple[str, ...]:
        """Return the exact immutable OMSimulator arguments.

        :return: Ordered argument tuple excluding the executable.
        """

        return self._process_arguments

    def get_veragrid_fmpy_metrics(self) -> RmsFmiComparisonMetrics:
        """Return VeraGrid--FMPy metrics.

        :return: Pair metrics used by the manifest.
        """

        return self._veragrid_fmpy_metrics

    def get_veragrid_omsimulator_metrics(self) -> RmsFmiComparisonMetrics:
        """Return VeraGrid--OMSimulator metrics.

        :return: Pair metrics used by the manifest.
        """

        return self._veragrid_omsimulator_metrics

    def get_fmpy_omsimulator_metrics(self) -> RmsFmiComparisonMetrics:
        """Return FMPy--OMSimulator metrics.

        :return: Pair metrics used by the manifest.
        """

        return self._fmpy_omsimulator_metrics

    def get_fmu_sha256(self) -> str:
        """Return the stable per-mode FMU identity.

        :return: Lowercase SHA-256 text.
        """

        return self._fmu_sha256

    def get_fmpy_time_alignment_max_error_seconds(self) -> float:
        """Return the exact maximum retained FMPy time-alignment error.

        :return: Maximum absolute time error in seconds.
        """

        return self._fmpy_time_alignment_max_error_seconds

def _hash_file(path: Path) -> str:
    """Compute the SHA-256 identity of one retained artifact.

    :param path: File to hash.
    :return: Lowercase SHA-256 text.
    """

    with path.open("rb") as file_handle:
        return hashlib.file_digest(file_handle, "sha256").hexdigest()


def _hash_float_array(values: np.ndarray) -> str:
    """Hash one finite vector with the manifest canonical float encoding.

    :param values: One-dimensional finite numerical vector.
    :return: SHA-256 of one ``.17e`` value plus LF per sample.
    """

    values_are_valid: bool = bool(
        values.ndim == 1
        and values.size > 0
        and np.all(np.isfinite(values))
    )
    if values_are_valid:
        canonical_text: str = "".join(
            f"{float(value):.17e}\n" for value in values
        )
    else:
        raise ValueError("Only finite one-dimensional arrays can be hashed")
    return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()


def _write_fmpy_trace_csv(
        csv_path: Path,
        mode: FmuInterfaceMode,
        time_seconds: np.ndarray,
        voltage_magnitude: np.ndarray,
        active_power: np.ndarray,
        reactive_power: np.ndarray,
        scenario: RmsLoadPowerStepScenario,
) -> Path:
    """Retain the original direct-FMPy trajectory as canonical raw evidence.

    :param csv_path: Mode-local CSV destination.
    :param mode: FMI interface mode executed by direct FMPy.
    :param time_seconds: Original time values returned by FMPy.
    :param voltage_magnitude: Shared retained VeraGrid voltage input.
    :param active_power: Direct-FMPy active power in p.u.
    :param reactive_power: Direct-FMPy reactive power in p.u.
    :param scenario: Scenario that defines the maintained producer lattice.
    :return: Written regular CSV path.
    """

    expected_time_seconds: np.ndarray = scenario.build_time_lattice()
    expected_sample_count: int = scenario.sample_count
    event_boundary_index: int = scenario.event_boundary_index
    first_post_event_index: int = scenario.first_post_event_index
    arrays_are_valid: bool = bool(
        mode in (FmuInterfaceMode.CO_SIMULATION, FmuInterfaceMode.MODEL_EXCHANGE)
        and time_seconds.shape == expected_time_seconds.shape
        and voltage_magnitude.shape == time_seconds.shape
        and active_power.shape == time_seconds.shape
        and reactive_power.shape == time_seconds.shape
        and np.all(np.isfinite(time_seconds))
        and np.all(np.isfinite(voltage_magnitude))
        and np.all(np.isfinite(active_power))
        and np.all(np.isfinite(reactive_power))
        and np.all(np.diff(time_seconds) > 0.0)
        and np.all(np.abs(time_seconds - expected_time_seconds) <= 1.0e-12)
        and abs(
            voltage_magnitude[first_post_event_index]
            - voltage_magnitude[event_boundary_index]
        ) > scenario.voltage_response_threshold_pu
    )
    if arrays_are_valid:
        pass
    else:
        raise ValueError("Direct-FMPy raw evidence is incomplete or misaligned")
    header: tuple[str, ...] = (
        "sample_index",
        "mode",
        "time_seconds",
        "voltage_magnitude_pu",
        "active_power_pu",
        "reactive_power_pu",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer: csv.writer = csv.writer(csv_file, lineterminator="\n")
        writer.writerow(header)
        sample_index: int
        for sample_index in range(expected_sample_count):
            row: tuple[object, ...] = (
                sample_index,
                mode.value,
                f"{time_seconds[sample_index]:.17e}",
                f"{voltage_magnitude[sample_index]:.17e}",
                f"{active_power[sample_index]:.17e}",
                f"{reactive_power[sample_index]:.17e}",
            )
            writer.writerow(row)
    retained_path: Path = _verify_regular_file_path(
        csv_path,
        262144,
        "Direct-FMPy raw CSV",
    )
    return retained_path


def _read_rms_report_scalars(report_path: Path) -> tuple[float, float]:
    """Parse the two canonical numerical scalars owned by an RMS report.

    :param report_path: Retained UTF-8 RMS execution report.
    :return: RMS solver tolerance followed by power-flow residual.
    """

    validated_report_path: Path = _verify_regular_file_path(
        report_path,
        65536,
        "RMS execution report",
    )
    try:
        report_text: str = validated_report_path.read_text(
            encoding="utf-8",
            errors="strict",
        )
    except UnicodeDecodeError as decode_error:
        raise RuntimeError("RMS execution report is not strict UTF-8") from decode_error
    scalar_pattern: re.Pattern[str] = re.compile(
        r"^(power_flow_residual|rms_solver_tolerance) = "
        r"([0-9]\.[0-9]{16}e[+-][0-9]{2,3})$"
    )
    power_flow_text: str | None = None
    solver_tolerance_text: str | None = None
    report_line: str
    for report_line in report_text.splitlines():
        line_has_relevant_prefix: bool = bool(
            report_line.startswith("power_flow_residual")
            or report_line.startswith("rms_solver_tolerance")
        )
        if line_has_relevant_prefix:
            scalar_match: re.Match[str] | None = scalar_pattern.fullmatch(report_line)
            if scalar_match is None:
                raise RuntimeError("RMS report scalar line is not canonical")
            else:
                scalar_name: str = scalar_match.group(1)
                scalar_text: str = scalar_match.group(2)
            if scalar_name == "power_flow_residual":
                if power_flow_text is None:
                    power_flow_text = scalar_text
                else:
                    raise RuntimeError("RMS report repeats power_flow_residual")
            elif scalar_name == "rms_solver_tolerance":
                if solver_tolerance_text is None:
                    solver_tolerance_text = scalar_text
                else:
                    raise RuntimeError("RMS report repeats rms_solver_tolerance")
            else:
                raise RuntimeError("RMS report contains an unsupported scalar")
        else:
            pass
    if power_flow_text is not None and solver_tolerance_text is not None:
        power_flow_residual: float = float(power_flow_text)
        solver_tolerance: float = float(solver_tolerance_text)
    else:
        raise RuntimeError("RMS report omits a required canonical scalar")
    scalars_are_valid: bool = bool(
        math.isfinite(power_flow_residual)
        and power_flow_residual >= 0.0
        and math.isfinite(solver_tolerance)
        and solver_tolerance >= 0.0
    )
    if scalars_are_valid:
        return solver_tolerance, power_flow_residual
    else:
        raise RuntimeError("RMS report scalars must be finite and nonnegative")


def _read_retained_comparison_csv(csv_path: Path) -> RmsFmiRetainedTrace:
    """Read the combined CSV into the sole typed owner used by plots.

    :param csv_path: Canonical 23-column combined comparison CSV.
    :return: Verified retained trace and its three reconstructed metric owners.
    """

    validated_csv_path: Path = _verify_regular_file_path(
        csv_path,
        None,
        "Combined comparison CSV",
    )
    with validated_csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        rows: list[list[str]] = list(csv.reader(csv_file))
    expected_header: tuple[str, ...] = (
        "sample_index", "time_seconds", "regime", "scenario_phase",
        "voltage_magnitude_pu", "veragrid_active_power_pu",
        "fmpy_active_power_pu", "omsimulator_active_power_pu",
        "veragrid_reactive_power_pu", "fmpy_reactive_power_pu",
        "omsimulator_reactive_power_pu", "veragrid__fmpy_active_error_pu",
        "veragrid__fmpy_active_budget_pu", "veragrid__fmpy_reactive_error_pu",
        "veragrid__fmpy_reactive_budget_pu",
        "veragrid__omsimulator_active_error_pu",
        "veragrid__omsimulator_active_budget_pu",
        "veragrid__omsimulator_reactive_error_pu",
        "veragrid__omsimulator_reactive_budget_pu",
        "fmpy__omsimulator_active_error_pu",
        "fmpy__omsimulator_active_budget_pu",
        "fmpy__omsimulator_reactive_error_pu",
        "fmpy__omsimulator_reactive_budget_pu",
    )
    shape_is_valid: bool = bool(
        len(rows) == 302
        and tuple(rows[0]) == expected_header
        and all(len(row) == 23 for row in rows[1:])
    )
    if shape_is_valid:
        pass
    else:
        raise RuntimeError("Combined FMI CSV has an invalid shape")
    numerical_columns: tuple[int, ...] = (
        1, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18,
        19, 20, 21, 22,
    )
    retained_arrays: np.ndarray = np.empty((20, 301), dtype=float)
    sample_index: int
    for sample_index in range(301):
        row: list[str] = rows[sample_index + 1]
        if sample_index == 0:
            expected_regime: str = "initial_projection"
            expected_phase: str = "baseline"
        else:
            expected_regime = "accepted_step"
            if sample_index < 100:
                expected_phase = "pre_event"
            elif sample_index == 100:
                expected_phase = "event_boundary"
            else:
                expected_phase = "post_event"
        identity_is_valid: bool = bool(
            row[0] == str(sample_index)
            and row[2] == expected_regime
            and row[3] == expected_phase
        )
        if identity_is_valid:
            pass
        else:
            raise RuntimeError("Combined FMI CSV index, regime or phase is invalid")
        column_position: int
        for column_position in range(len(numerical_columns)):
            csv_column: int = numerical_columns[column_position]
            try:
                numerical_value: float = float(row[csv_column])
            except ValueError as parse_error:
                raise RuntimeError("Combined FMI CSV contains malformed data") from parse_error
            number_is_canonical: bool = bool(
                math.isfinite(numerical_value)
                and row[csv_column] == f"{numerical_value:.17e}"
            )
            if number_is_canonical:
                retained_arrays[column_position, sample_index] = numerical_value
            else:
                raise RuntimeError("Combined FMI CSV contains noncanonical data")
    expected_time_seconds: np.ndarray = np.arange(301, dtype=float) * 1.0e-3
    if np.all(np.abs(retained_arrays[0, :] - expected_time_seconds) <= 1.0e-12):
        pass
    else:
        raise RuntimeError("Combined FMI CSV time lattice is invalid")
    veragrid_fmpy_metrics: RmsFmiComparisonMetrics = RmsFmiComparisonMetrics(
        retained_arrays[8, :],
        retained_arrays[10, :],
        retained_arrays[9, :],
        retained_arrays[11, :],
    )
    veragrid_omsimulator_metrics: RmsFmiComparisonMetrics = RmsFmiComparisonMetrics(
        retained_arrays[12, :],
        retained_arrays[14, :],
        retained_arrays[13, :],
        retained_arrays[15, :],
    )
    fmpy_omsimulator_metrics: RmsFmiComparisonMetrics = RmsFmiComparisonMetrics(
        retained_arrays[16, :],
        retained_arrays[18, :],
        retained_arrays[17, :],
        retained_arrays[19, :],
    )
    return RmsFmiRetainedTrace(
        time_seconds=retained_arrays[0, :],
        voltage_magnitude=retained_arrays[1, :],
        veragrid_active_power=retained_arrays[2, :],
        fmpy_active_power=retained_arrays[3, :],
        omsimulator_active_power=retained_arrays[4, :],
        veragrid_reactive_power=retained_arrays[5, :],
        fmpy_reactive_power=retained_arrays[6, :],
        omsimulator_reactive_power=retained_arrays[7, :],
        veragrid_fmpy_metrics=veragrid_fmpy_metrics,
        veragrid_omsimulator_metrics=veragrid_omsimulator_metrics,
        fmpy_omsimulator_metrics=fmpy_omsimulator_metrics,
    )

def _build_input_signal(
        time_seconds: np.ndarray,
        voltage_magnitude: np.ndarray,
) -> np.ndarray:
    """Build the direct FMPy input from accepted RMS voltage samples.

    :param time_seconds: Exact accepted RMS time lattice.
    :param voltage_magnitude: Exact accepted bus-voltage samples.
    :return: Structured FMPy input signal with time and voltage fields.
    """

    inputs_are_valid: bool = bool(
        time_seconds.ndim == 1
        and voltage_magnitude.shape == time_seconds.shape
        and time_seconds.size > 0
        and np.all(np.isfinite(time_seconds))
        and np.all(np.isfinite(voltage_magnitude))
    )
    if inputs_are_valid:
        pass
    else:
        raise ValueError("FMI input time and voltage traces must be finite and aligned")

    input_signal: np.ndarray = np.empty(
        time_seconds.size,
        dtype=np.dtype([("time", np.float64), ("u", np.float64)]),
    )
    input_signal["time"] = time_seconds
    input_signal["u"] = voltage_magnitude
    return input_signal


def _get_direct_fmpy_trace(
        execution: RmsFmiExampleExecution,
        extraction_root: Path,
        scenario: RmsLoadPowerStepScenario,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Execute the exact retained FMU directly through its FMPy backend.

    :param execution: Native RMS execution that owns the exact FMU and lattice.
    :param extraction_root: Owned directory used for temporary FMPy extraction.
    :param scenario: Scenario that defines the direct-runtime communication step.
    :return: Direct time, active-power and reactive-power trajectories.
    """

    time_seconds: np.ndarray = execution.get_time_seconds()
    stop_time: float = float(time_seconds[-1])
    output_names: list[str] = list(("p_out", "q_out"))
    voltage_magnitude: np.ndarray | None = execution.get_voltage_magnitude()
    if voltage_magnitude is None:
        raise RuntimeError("The RMS execution did not retain its voltage input")
    else:
        input_signal: np.ndarray = _build_input_signal(
            time_seconds,
            voltage_magnitude,
        )
    mode: FmuInterfaceMode = execution.get_mode()
    if mode == FmuInterfaceMode.CO_SIMULATION:
        simulation_result: np.ndarray = simulate_cs_fmu_with_fmpy(
            execution.get_fmu_path(),
            stop_time=stop_time,
            output=output_names,
            input_signal=input_signal,
            extraction_root=extraction_root,
            output_interval=scenario.time_step_seconds,
        )
    elif mode == FmuInterfaceMode.MODEL_EXCHANGE:
        simulation_result = simulate_me_fmu_with_fmpy(
            execution.get_fmu_path(),
            stop_time=stop_time,
            output=output_names,
            input_signal=input_signal,
            extraction_root=extraction_root,
            step_size=scenario.time_step_seconds,
        )
    else:
        raise ValueError(f"Unsupported RMS FMI comparison mode: {mode.value}")

    result_names: tuple[str, ...] | None = simulation_result.dtype.names
    required_names_are_present: bool = bool(
        result_names is not None
        and "time" in result_names
        and "p_out" in result_names
        and "q_out" in result_names
    )
    if required_names_are_present:
        direct_time: np.ndarray = np.asarray(
            simulation_result["time"],
            dtype=float,
        ).copy()
        direct_active_power: np.ndarray = np.asarray(
            simulation_result["p_out"],
            dtype=float,
        ).copy()
        direct_reactive_power: np.ndarray = np.asarray(
            simulation_result["q_out"],
            dtype=float,
        ).copy()
    else:
        raise RuntimeError("Direct FMPy result omitted a required comparison field")

    direct_values_are_finite: bool = bool(
        direct_time.ndim == 1
        and direct_active_power.shape == direct_time.shape
        and direct_reactive_power.shape == direct_time.shape
        and direct_time.size > 0
        and np.all(np.isfinite(direct_time))
        and np.all(np.isfinite(direct_active_power))
        and np.all(np.isfinite(direct_reactive_power))
    )
    if direct_values_are_finite:
        return direct_time, direct_active_power, direct_reactive_power
    else:
        raise RuntimeError("Direct FMPy result is incomplete or non-finite")


def _compare_aligned_trajectories(
        left_time_seconds: np.ndarray,
        left_active_power: np.ndarray,
        left_reactive_power: np.ndarray,
        right_time_seconds: np.ndarray,
        right_active_power: np.ndarray,
        right_reactive_power: np.ndarray,
        left_absolute_allowance: np.ndarray,
        right_absolute_allowance: np.ndarray,
        left_relative_allowance: float,
        right_relative_allowance: float,
        comparison_absolute_tolerance: float,
        comparison_relative_tolerance: float,
        expected_time_seconds: np.ndarray,
) -> RmsFmiComparisonMetrics:
    """Compare two exact-lattice paths with symmetric declared allowances.

    :param left_time_seconds: Left path time lattice.
    :param left_active_power: Left active-power trajectory.
    :param left_reactive_power: Left reactive-power trajectory.
    :param right_time_seconds: Right path time lattice.
    :param right_active_power: Right active-power trajectory.
    :param right_reactive_power: Right reactive-power trajectory.
    :param left_absolute_allowance: Left path absolute allowance by sample.
    :param right_absolute_allowance: Right path absolute allowance by sample.
    :param left_relative_allowance: Left path relative allowance.
    :param right_relative_allowance: Right path relative allowance.
    :param comparison_absolute_tolerance: Pair-independent floating absolute term.
    :param comparison_relative_tolerance: Pair-independent floating relative term.
    :param expected_time_seconds: Independent expected lattice for this caller.
    :return: Conclusive pair metrics after every sample passes.
    """

    expected_lattice_is_valid: bool = bool(
        expected_time_seconds.ndim == 1
        and expected_time_seconds.size > 0
        and np.all(np.isfinite(expected_time_seconds))
        and np.all(np.diff(expected_time_seconds) > 0.0)
    )
    shapes_are_valid: bool = bool(
        expected_lattice_is_valid
        and left_time_seconds.shape == expected_time_seconds.shape
        and left_active_power.shape == expected_time_seconds.shape
        and left_reactive_power.shape == expected_time_seconds.shape
        and right_time_seconds.shape == expected_time_seconds.shape
        and right_active_power.shape == expected_time_seconds.shape
        and right_reactive_power.shape == expected_time_seconds.shape
        and left_absolute_allowance.shape == expected_time_seconds.shape
        and right_absolute_allowance.shape == expected_time_seconds.shape
    )
    values_are_valid: bool = bool(
        shapes_are_valid
        and np.all(np.isfinite(left_time_seconds))
        and np.all(np.isfinite(left_active_power))
        and np.all(np.isfinite(left_reactive_power))
        and np.all(np.isfinite(right_time_seconds))
        and np.all(np.isfinite(right_active_power))
        and np.all(np.isfinite(right_reactive_power))
        and np.all(np.isfinite(left_absolute_allowance))
        and np.all(left_absolute_allowance >= 0.0)
        and np.all(np.isfinite(right_absolute_allowance))
        and np.all(right_absolute_allowance >= 0.0)
        and math.isfinite(left_relative_allowance)
        and left_relative_allowance >= 0.0
        and math.isfinite(right_relative_allowance)
        and right_relative_allowance >= 0.0
        and math.isfinite(comparison_absolute_tolerance)
        and comparison_absolute_tolerance > 0.0
        and math.isfinite(comparison_relative_tolerance)
        and comparison_relative_tolerance >= 0.0
    )
    if values_are_valid:
        pass
    else:
        raise ValueError("FMI pair comparison inputs must be finite and aligned")

    lattices_are_valid: bool = bool(
        np.all(np.abs(left_time_seconds - expected_time_seconds) <= 1.0e-12)
        and np.all(np.abs(right_time_seconds - expected_time_seconds) <= 1.0e-12)
    )
    if lattices_are_valid:
        pass
    else:
        raise ValueError("FMI comparison paths must share the exact time lattice")

    # A symmetric scale prevents either path from being privileged as the truth.
    active_scale: np.ndarray = np.maximum(
        np.abs(left_active_power),
        np.abs(right_active_power),
    )
    reactive_scale: np.ndarray = np.maximum(
        np.abs(left_reactive_power),
        np.abs(right_reactive_power),
    )
    absolute_active_power_error: np.ndarray = np.abs(
        left_active_power - right_active_power
    )
    absolute_reactive_power_error: np.ndarray = np.abs(
        left_reactive_power - right_reactive_power
    )
    active_power_budget: np.ndarray = (
        comparison_absolute_tolerance
        + comparison_relative_tolerance * active_scale
        + left_absolute_allowance
        + right_absolute_allowance
        + left_relative_allowance * active_scale
        + right_relative_allowance * active_scale
    )
    reactive_power_budget: np.ndarray = (
        comparison_absolute_tolerance
        + comparison_relative_tolerance * reactive_scale
        + left_absolute_allowance
        + right_absolute_allowance
        + left_relative_allowance * reactive_scale
        + right_relative_allowance * reactive_scale
    )
    active_power_passes: bool = bool(
        np.all(absolute_active_power_error <= active_power_budget)
    )
    reactive_power_passes: bool = bool(
        np.all(absolute_reactive_power_error <= reactive_power_budget)
    )
    if active_power_passes and reactive_power_passes:
        return RmsFmiComparisonMetrics(
            absolute_active_power_error=absolute_active_power_error,
            absolute_reactive_power_error=absolute_reactive_power_error,
            active_power_budget=active_power_budget,
            reactive_power_budget=reactive_power_budget,
        )
    else:
        active_excess: float = float(
            np.max(absolute_active_power_error - active_power_budget)
        )
        reactive_excess: float = float(
            np.max(absolute_reactive_power_error - reactive_power_budget)
        )
        raise RuntimeError(
            "FMI trajectory pair exceeds its derived comparison budget: "
            f"active excess={active_excess:.17e}, "
            f"reactive excess={reactive_excess:.17e}"
        )


def _write_trace_csv(
        csv_path: Path,
        execution: RmsFmiExampleExecution,
        fmpy_time_seconds: np.ndarray,
        fmpy_active_power: np.ndarray,
        fmpy_reactive_power: np.ndarray,
        omsimulator_trace: OmsimulatorTrace,
        veragrid_fmpy_metrics: RmsFmiComparisonMetrics,
        veragrid_omsimulator_metrics: RmsFmiComparisonMetrics,
        fmpy_omsimulator_metrics: RmsFmiComparisonMetrics,
        scenario: RmsLoadPowerStepScenario,
) -> Path:
    """Write the three paths and every pair-specific error budget.

    :param csv_path: Destination comparison CSV.
    :param execution: Native VeraGrid RMS execution evidence.
    :param fmpy_time_seconds: Direct FMPy time lattice.
    :param fmpy_active_power: Direct FMPy active-power trace.
    :param fmpy_reactive_power: Direct FMPy reactive-power trace.
    :param omsimulator_trace: Independent OMSimulator trace.
    :param veragrid_fmpy_metrics: VeraGrid-to-FMPy pair metrics.
    :param veragrid_omsimulator_metrics: VeraGrid-to-OMSimulator pair metrics.
    :param fmpy_omsimulator_metrics: FMPy-to-OMSimulator pair metrics.
    :param scenario: Scenario that defines event-phase sample boundaries.
    :return: Written CSV path.
    """

    time_seconds: np.ndarray = execution.get_time_seconds()
    veragrid_active_power: np.ndarray = execution.get_active_power()
    veragrid_reactive_power: np.ndarray = execution.get_reactive_power()
    voltage_magnitude: np.ndarray | None = execution.get_voltage_magnitude()
    if voltage_magnitude is not None:
        pass
    else:
        raise RuntimeError("RMS FMI trace evidence requires its voltage input")
    omsimulator_time_seconds: np.ndarray = omsimulator_trace.get_time_seconds()
    omsimulator_active_power: np.ndarray = omsimulator_trace.get_active_power()
    omsimulator_reactive_power: np.ndarray = omsimulator_trace.get_reactive_power()
    times_are_aligned: bool = bool(
        np.all(np.abs(fmpy_time_seconds - time_seconds) <= 1.0e-12)
        and np.all(np.abs(omsimulator_time_seconds - time_seconds) <= 1.0e-12)
    )
    if times_are_aligned:
        pass
    else:
        raise RuntimeError("Combined FMI CSV paths are not time-aligned")

    veragrid_fmpy_active_error: np.ndarray = (
        veragrid_fmpy_metrics.get_absolute_active_power_error()
    )
    veragrid_fmpy_active_budget: np.ndarray = (
        veragrid_fmpy_metrics.get_active_power_budget()
    )
    veragrid_fmpy_reactive_error: np.ndarray = (
        veragrid_fmpy_metrics.get_absolute_reactive_power_error()
    )
    veragrid_fmpy_reactive_budget: np.ndarray = (
        veragrid_fmpy_metrics.get_reactive_power_budget()
    )
    veragrid_omsimulator_active_error: np.ndarray = (
        veragrid_omsimulator_metrics.get_absolute_active_power_error()
    )
    veragrid_omsimulator_active_budget: np.ndarray = (
        veragrid_omsimulator_metrics.get_active_power_budget()
    )
    veragrid_omsimulator_reactive_error: np.ndarray = (
        veragrid_omsimulator_metrics.get_absolute_reactive_power_error()
    )
    veragrid_omsimulator_reactive_budget: np.ndarray = (
        veragrid_omsimulator_metrics.get_reactive_power_budget()
    )
    fmpy_omsimulator_active_error: np.ndarray = (
        fmpy_omsimulator_metrics.get_absolute_active_power_error()
    )
    fmpy_omsimulator_active_budget: np.ndarray = (
        fmpy_omsimulator_metrics.get_active_power_budget()
    )
    fmpy_omsimulator_reactive_error: np.ndarray = (
        fmpy_omsimulator_metrics.get_absolute_reactive_power_error()
    )
    fmpy_omsimulator_reactive_budget: np.ndarray = (
        fmpy_omsimulator_metrics.get_reactive_power_budget()
    )
    header: tuple[str, ...] = (
        "sample_index", "time_seconds", "regime", "scenario_phase",
        "voltage_magnitude_pu", "veragrid_active_power_pu",
        "fmpy_active_power_pu", "omsimulator_active_power_pu",
        "veragrid_reactive_power_pu", "fmpy_reactive_power_pu",
        "omsimulator_reactive_power_pu", "veragrid__fmpy_active_error_pu",
        "veragrid__fmpy_active_budget_pu", "veragrid__fmpy_reactive_error_pu",
        "veragrid__fmpy_reactive_budget_pu",
        "veragrid__omsimulator_active_error_pu",
        "veragrid__omsimulator_active_budget_pu",
        "veragrid__omsimulator_reactive_error_pu",
        "veragrid__omsimulator_reactive_budget_pu",
        "fmpy__omsimulator_active_error_pu",
        "fmpy__omsimulator_active_budget_pu",
        "fmpy__omsimulator_reactive_error_pu",
        "fmpy__omsimulator_reactive_budget_pu",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer: csv.writer = csv.writer(csv_file, lineterminator="\n")
        writer.writerow(header)
        sample_index: int
        for sample_index in range(time_seconds.size):
            if sample_index == 0:
                regime: str = "initial_projection"
                scenario_phase: str = "baseline"
            else:
                regime = "accepted_step"
                if sample_index < scenario.event_boundary_index:
                    scenario_phase = "pre_event"
                elif sample_index == scenario.event_boundary_index:
                    scenario_phase = "event_boundary"
                else:
                    scenario_phase = "post_event"
            row: tuple[object, ...] = (
                sample_index,
                f"{time_seconds[sample_index]:.17e}",
                regime,
                scenario_phase,
                f"{voltage_magnitude[sample_index]:.17e}",
                f"{veragrid_active_power[sample_index]:.17e}",
                f"{fmpy_active_power[sample_index]:.17e}",
                f"{omsimulator_active_power[sample_index]:.17e}",
                f"{veragrid_reactive_power[sample_index]:.17e}",
                f"{fmpy_reactive_power[sample_index]:.17e}",
                f"{omsimulator_reactive_power[sample_index]:.17e}",
                f"{veragrid_fmpy_active_error[sample_index]:.17e}",
                f"{veragrid_fmpy_active_budget[sample_index]:.17e}",
                f"{veragrid_fmpy_reactive_error[sample_index]:.17e}",
                f"{veragrid_fmpy_reactive_budget[sample_index]:.17e}",
                f"{veragrid_omsimulator_active_error[sample_index]:.17e}",
                f"{veragrid_omsimulator_active_budget[sample_index]:.17e}",
                f"{veragrid_omsimulator_reactive_error[sample_index]:.17e}",
                f"{veragrid_omsimulator_reactive_budget[sample_index]:.17e}",
                f"{fmpy_omsimulator_active_error[sample_index]:.17e}",
                f"{fmpy_omsimulator_active_budget[sample_index]:.17e}",
                f"{fmpy_omsimulator_reactive_error[sample_index]:.17e}",
                f"{fmpy_omsimulator_reactive_budget[sample_index]:.17e}",
            )
            writer.writerow(row)
    return csv_path

def _configure_scientific_axis(axis: Axes, y_label: str) -> None:
    """Apply restrained scientific styling to one comparison axis.

    :param axis: Matplotlib axes to configure.
    :param y_label: Physical quantity and unit shown on the vertical axis.
    :return: None.
    """

    axis.set_ylabel(y_label)
    axis.set_axisbelow(True)
    axis.grid(
        visible=True,
        which="major",
        axis="both",
        color="#d9d9d9",
        linewidth=0.6,
    )
    axis.tick_params(direction="out", width=0.8, length=3.5)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["left"].set_linewidth(0.8)
    axis.spines["bottom"].set_linewidth(0.8)
    axis.ticklabel_format(
        axis="y",
        style="sci",
        scilimits=(-3, 3),
        useMathText=True,
    )


def _save_figure_formats(figure: Figure, output_base: Path) -> tuple[Path, ...]:
    """Save vector masters and one exact-size 300 dpi review raster.

    :param figure: Fully composed Matplotlib figure.
    :param output_base: Output path without an extension.
    :return: Written PDF, SVG and PNG paths.
    """

    pdf_path: Path = output_base.with_suffix(".pdf")
    svg_path: Path = output_base.with_suffix(".svg")
    png_path: Path = output_base.with_suffix(".png")
    with matplotlib.rc_context():
        # Preserve editable SVG text and portable PDF fonts while keeping the
        # configured 7.2 x 4.8 inch canvas unchanged for the 2160 x 1440 PNG.
        matplotlib.rcParams["svg.fonttype"] = "none"
        matplotlib.rcParams["pdf.fonttype"] = 42
        matplotlib.rcParams["ps.fonttype"] = 42
        figure.savefig(pdf_path, format="pdf")
        figure.savefig(svg_path, format="svg")
        figure.savefig(png_path, format="png", dpi=300)
    return pdf_path, svg_path, png_path


def _render_trajectory_figure(
        output_base: Path,
        mode: FmuInterfaceMode,
        retained_trace: RmsFmiRetainedTrace,
        event_time_seconds: float,
) -> tuple[Path, ...]:
    """Render three P/Q trajectories solely from the retained combined CSV.

    :param output_base: Output path without an extension.
    :param mode: FMI interface mode represented by the trajectories.
    :param retained_trace: Typed data reconstructed from the retained CSV.
    :param event_time_seconds: Exact load-step boundary in seconds.
    :return: Written PDF, SVG and PNG paths.
    """

    if mode == FmuInterfaceMode.CO_SIMULATION:
        interface_label: str = "Co-Simulation"
    elif mode == FmuInterfaceMode.MODEL_EXCHANGE:
        interface_label = "Model Exchange"
    else:
        raise ValueError(f"Unsupported RMS FMI figure mode: {mode.value}")
    time_seconds: np.ndarray = retained_trace.get_time_seconds()
    veragrid_active_power: np.ndarray = retained_trace.get_veragrid_active_power()
    fmpy_active_power: np.ndarray = retained_trace.get_fmpy_active_power()
    omsimulator_active_power: np.ndarray = retained_trace.get_omsimulator_active_power()
    veragrid_reactive_power: np.ndarray = retained_trace.get_veragrid_reactive_power()
    fmpy_reactive_power: np.ndarray = retained_trace.get_fmpy_reactive_power()
    omsimulator_reactive_power: np.ndarray = (
        retained_trace.get_omsimulator_reactive_power()
    )

    figure: Figure = Figure(figsize=(7.2, 4.8), constrained_layout=True)
    canvas: FigureCanvasAgg = FigureCanvasAgg(figure)
    active_axis: Axes = figure.add_subplot(2, 1, 1)
    reactive_axis: Axes = figure.add_subplot(2, 1, 2, sharex=active_axis)
    marker_interval: int = max(1, int(time_seconds.size // 12))
    # Line, marker and color redundantly encode each runtime so printed and
    # grayscale copies preserve the three-path distinction.
    active_axis.plot(
        time_seconds, veragrid_active_power, color="#222222", linestyle="-",
        linewidth=1.6, label="VeraGrid RMS",
    )
    active_axis.plot(
        time_seconds, fmpy_active_power, color="#0072B2", linestyle="--",
        linewidth=1.35, marker="o", markerfacecolor="none", markersize=3.4,
        markevery=marker_interval, label="Direct FMPy",
    )
    active_axis.plot(
        time_seconds, omsimulator_active_power, color="#D55E00", linestyle=":",
        linewidth=1.45, marker="^", markerfacecolor="none", markersize=3.6,
        markevery=marker_interval, label="OMSimulator",
    )
    reactive_axis.plot(
        time_seconds, veragrid_reactive_power, color="#222222", linestyle="-",
        linewidth=1.6,
    )
    reactive_axis.plot(
        time_seconds, fmpy_reactive_power, color="#0072B2", linestyle="--",
        linewidth=1.35, marker="o", markerfacecolor="none", markersize=3.4,
        markevery=marker_interval,
    )
    reactive_axis.plot(
        time_seconds, omsimulator_reactive_power, color="#D55E00", linestyle=":",
        linewidth=1.45, marker="^", markerfacecolor="none", markersize=3.6,
        markevery=marker_interval,
    )
    active_axis.axvline(
        event_time_seconds, color="#777777", linestyle="-.", linewidth=1.0,
        label="Load-step boundary",
    )
    reactive_axis.axvline(
        event_time_seconds, color="#777777", linestyle="-.", linewidth=1.0,
    )
    _configure_scientific_axis(active_axis, "Active power (p.u.)")
    _configure_scientific_axis(reactive_axis, "Reactive power (p.u.)")
    active_axis.tick_params(labelbottom=False)
    reactive_axis.set_xlabel("Time (s)")
    active_axis.legend(
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        borderaxespad=0.0,
        frameon=False,
        fontsize=7.5,
    )
    figure.suptitle(
        f"RMS FMI 2 {interface_label} load-step response",
        fontsize=11,
        fontweight="normal",
    )
    canvas.draw()
    output_paths: tuple[Path, ...] = _save_figure_formats(figure, output_base)
    figure.clear()
    return output_paths


def _render_error_figure(
        output_base: Path,
        mode: FmuInterfaceMode,
        retained_trace: RmsFmiRetainedTrace,
        event_time_seconds: float,
) -> tuple[Path, ...]:
    """Render all pair errors and budgets solely from the retained CSV.

    :param output_base: Output path without an extension.
    :param mode: FMI interface mode represented by the errors.
    :param retained_trace: Typed data reconstructed from the retained CSV.
    :param event_time_seconds: Exact load-step boundary in seconds.
    :return: Written PDF, SVG and PNG paths.
    """

    if mode == FmuInterfaceMode.CO_SIMULATION:
        interface_label: str = "Co-Simulation"
    elif mode == FmuInterfaceMode.MODEL_EXCHANGE:
        interface_label = "Model Exchange"
    else:
        raise ValueError(f"Unsupported RMS FMI figure mode: {mode.value}")
    time_seconds: np.ndarray = retained_trace.get_time_seconds()
    figure: Figure = Figure(figsize=(7.2, 4.8), constrained_layout=True)
    canvas: FigureCanvasAgg = FigureCanvasAgg(figure)
    active_axis: Axes = figure.add_subplot(2, 1, 1)
    reactive_axis: Axes = figure.add_subplot(2, 1, 2, sharex=active_axis)
    pair_metrics: tuple[RmsFmiComparisonMetrics, ...] = (
        retained_trace.get_veragrid_fmpy_metrics(),
        retained_trace.get_veragrid_omsimulator_metrics(),
        retained_trace.get_fmpy_omsimulator_metrics(),
    )
    pair_ids: tuple[str, ...] = (
        "veragrid_integrated__fmpy_direct",
        "veragrid_integrated__omsimulator_independent",
        "fmpy_direct__omsimulator_independent",
    )
    pair_labels: tuple[str, ...] = (
        "VeraGrid–FMPy",
        "VeraGrid–OMSimulator",
        "FMPy–OMSimulator",
    )
    pair_colors: tuple[str, ...] = ("#222222", "#D55E00", "#0072B2")
    pair_styles: tuple[str, ...] = ("-", "--", "-.")
    budget_styles: tuple[tuple[int, tuple[int, ...]], ...] = (
        (0, (1, 1)),
        (0, (5, 2)),
        (0, (3, 1, 1, 1)),
    )
    budget_markers: tuple[str, ...] = ("o", "s", "^")
    marker_interval: int = max(1, int(time_seconds.size // 12))
    marker_offsets: tuple[int, ...] = (
        0,
        marker_interval // 3,
        2 * (marker_interval // 3),
    )
    pair_index: int
    for pair_index in range(3):
        metrics: RmsFmiComparisonMetrics = pair_metrics[pair_index]
        active_axis.plot(
            time_seconds,
            metrics.get_absolute_active_power_error(),
            color=pair_colors[pair_index],
            linestyle=pair_styles[pair_index],
            linewidth=1.4,
            label=f"{pair_labels[pair_index]} error",
        )
        active_axis.plot(
            time_seconds,
            metrics.get_active_power_budget(),
            color=pair_colors[pair_index],
            linestyle=budget_styles[pair_index],
            linewidth=1.0,
            alpha=0.75,
            marker=budget_markers[pair_index],
            markerfacecolor="none",
            markersize=3.0,
            markevery=(marker_offsets[pair_index], marker_interval),
            gid=f"active-budget-{pair_ids[pair_index]}",
            label=f"{pair_labels[pair_index]} budget",
        )
        reactive_axis.plot(
            time_seconds,
            metrics.get_absolute_reactive_power_error(),
            color=pair_colors[pair_index],
            linestyle=pair_styles[pair_index],
            linewidth=1.4,
        )
        reactive_axis.plot(
            time_seconds,
            metrics.get_reactive_power_budget(),
            color=pair_colors[pair_index],
            linestyle=budget_styles[pair_index],
            linewidth=1.0,
            alpha=0.75,
            marker=budget_markers[pair_index],
            markerfacecolor="none",
            markersize=3.0,
            markevery=(marker_offsets[pair_index], marker_interval),
            gid=f"reactive-budget-{pair_ids[pair_index]}",
        )
    active_axis.axvline(
        event_time_seconds, color="#777777", linestyle=":", linewidth=1.0,
    )
    reactive_axis.axvline(
        event_time_seconds, color="#777777", linestyle=":", linewidth=1.0,
    )
    _configure_scientific_axis(active_axis, "Absolute P error (p.u.)")
    _configure_scientific_axis(reactive_axis, "Absolute Q error (p.u.)")
    active_axis.tick_params(labelbottom=False)
    reactive_axis.set_xlabel("Time (s)")
    active_axis.legend(
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        borderaxespad=0.0,
        frameon=False,
        fontsize=7.0,
    )
    figure.suptitle(
        f"RMS FMI 2 {interface_label} pairwise error",
        fontsize=11,
        fontweight="normal",
    )
    canvas.draw()
    output_paths: tuple[Path, ...] = _save_figure_formats(figure, output_base)
    figure.clear()
    return output_paths

def _build_artifact_record(path: Path, staging_dir: Path) -> dict[str, object]:
    """Build one exact JSON-boundary artifact record.

    :param path: Retained regular artifact file.
    :param staging_dir: Owned package staging root.
    :return: Relative path, SHA-256 and byte size mapping.
    """

    validated_path: Path = _verify_regular_file_path(path, None, "Package artifact")
    staging_root: Path = staging_dir.resolve(strict=True)
    try:
        relative_path: str = validated_path.relative_to(staging_root).as_posix()
    except ValueError as path_error:
        raise RuntimeError("Package artifact escapes the staging root") from path_error
    return dict(
        path=relative_path,
        sha256=_hash_file(validated_path),
        size_bytes=validated_path.stat().st_size,
    )


def _build_path_record(
        path_id: str,
        runtime_family: str,
        independent_runtime: bool,
        fmu_sha256: str,
        time_seconds: np.ndarray,
        voltage_magnitude: np.ndarray,
        active_power: np.ndarray,
        reactive_power: np.ndarray,
        expected_sample_count: int,
) -> dict[str, object]:
    """Build one numerical-path record at the private JSON boundary.

    :param path_id: Stable path identifier.
    :param runtime_family: Runtime family disclosed by the path.
    :param independent_runtime: Whether the path is runtime-independent.
    :param fmu_sha256: Exact per-mode FMU identity.
    :param time_seconds: Original path time values.
    :param voltage_magnitude: Original path voltage values.
    :param active_power: Original path active-power values.
    :param reactive_power: Original path reactive-power values.
    :param expected_sample_count: Independent expected number of path samples.
    :return: Exact schema-v3 path mapping.
    """

    arrays_are_valid: bool = bool(
        isinstance(expected_sample_count, int)
        and not isinstance(expected_sample_count, bool)
        and expected_sample_count > 0
        and time_seconds.shape == (expected_sample_count,)
        and voltage_magnitude.shape == time_seconds.shape
        and active_power.shape == time_seconds.shape
        and reactive_power.shape == time_seconds.shape
    )
    if arrays_are_valid:
        pass
    else:
        raise ValueError("FMI path arrays do not match the expected sample count")

    return dict(
        path_id=path_id,
        runtime_family=runtime_family,
        independent_runtime=independent_runtime,
        fmu_sha256=fmu_sha256,
        sample_count=expected_sample_count,
        time_sha256=_hash_float_array(time_seconds),
        voltage_magnitude_sha256=_hash_float_array(voltage_magnitude),
        active_power_sha256=_hash_float_array(active_power),
        reactive_power_sha256=_hash_float_array(reactive_power),
    )


def _build_comparison_record(
        left_path: str,
        right_path: str,
        metrics: RmsFmiComparisonMetrics,
) -> dict[str, object]:
    """Build one pair summary from retained per-sample metrics.

    :param left_path: Stable left numerical-path identifier.
    :param right_path: Stable right numerical-path identifier.
    :param metrics: Verified errors and budgets for the oriented pair.
    :return: Exact schema-v3 comparison mapping.
    """

    return dict(
        left_path=left_path,
        right_path=right_path,
        active_power_max_error_pu=metrics.get_max_active_power_error(),
        active_power_rms_error_pu=metrics.get_rms_active_power_error(),
        active_power_max_budget_pu=float(np.max(metrics.get_active_power_budget())),
        reactive_power_max_error_pu=metrics.get_max_reactive_power_error(),
        reactive_power_rms_error_pu=metrics.get_rms_reactive_power_error(),
        reactive_power_max_budget_pu=float(
            np.max(metrics.get_reactive_power_budget())
        ),
        passed=True,
    )


def _build_mode_record(
        staging_dir: Path,
        mode_evidence: RmsFmiModeEvidence,
        scenario: RmsLoadPowerStepScenario,
) -> dict[str, object]:
    """Build one complete mode record from typed retained evidence.

    :param staging_dir: Owned package staging root.
    :param mode_evidence: Typed execution and retained numerical evidence.
    :param scenario: Scenario that defines maintained mode evidence semantics.
    :return: Exact schema-v3 mode mapping.
    """

    execution: RmsFmiExampleExecution = mode_evidence.get_execution()
    mode: FmuInterfaceMode = execution.get_mode()
    retained_trace: RmsFmiRetainedTrace = mode_evidence.get_retained_trace()
    omsimulator_trace: OmsimulatorTrace = mode_evidence.get_omsimulator_trace()
    fmpy_raw_path: Path = mode_evidence.get_fmpy_raw_evidence()
    fmpy_time: np.ndarray
    fmpy_voltage: np.ndarray
    fmpy_active_power: np.ndarray
    fmpy_reactive_power: np.ndarray
    (
        fmpy_time,
        fmpy_voltage,
        fmpy_active_power,
        fmpy_reactive_power,
    ) = _verify_raw_evidence(fmpy_raw_path, mode)
    retained_time: np.ndarray = retained_trace.get_time_seconds()
    retained_voltage: np.ndarray = retained_trace.get_voltage_magnitude()
    raw_matches_combined: bool = bool(
        np.all(np.abs(fmpy_time - retained_time) <= 1.0e-12)
        and np.array_equal(fmpy_voltage, retained_voltage)
        and np.array_equal(
            fmpy_active_power,
            retained_trace.get_fmpy_active_power(),
        )
        and np.array_equal(
            fmpy_reactive_power,
            retained_trace.get_fmpy_reactive_power(),
        )
    )
    fmpy_time_alignment: float = float(np.max(np.abs(fmpy_time - retained_time)))
    if (
            raw_matches_combined
            and fmpy_time_alignment
            == mode_evidence.get_fmpy_time_alignment_max_error_seconds()
    ):
        pass
    else:
        raise RuntimeError("Direct-FMPy raw and combined evidence diverge")
    solver_tolerance: float
    power_flow_residual: float
    solver_tolerance, power_flow_residual = _read_rms_report_scalars(
        execution.get_report_path()
    )
    report_matches_execution: bool = bool(
        solver_tolerance == execution.get_solver_tolerance()
        and power_flow_residual == execution.get_power_flow_residual()
    )
    if report_matches_execution:
        pass
    else:
        raise RuntimeError("RMS report scalars diverge from execution evidence")

    fmu_sha256: str = mode_evidence.get_fmu_sha256()
    expected_sample_count: int = scenario.sample_count
    veragrid_path_record: dict[str, object] = _build_path_record(
        "veragrid", "FMPy", False, fmu_sha256,
        retained_time,
        retained_voltage,
        retained_trace.get_veragrid_active_power(),
        retained_trace.get_veragrid_reactive_power(),
        expected_sample_count,
    )
    fmpy_path_record: dict[str, object] = _build_path_record(
        "fmpy", "FMPy", False, fmu_sha256,
        fmpy_time,
        fmpy_voltage,
        fmpy_active_power,
        fmpy_reactive_power,
        expected_sample_count,
    )
    omsimulator_path_record: dict[str, object] = _build_path_record(
        "omsimulator", "OMSimulator", True, fmu_sha256,
        omsimulator_trace.get_time_seconds(),
        omsimulator_trace.get_voltage_magnitude(),
        omsimulator_trace.get_active_power(),
        omsimulator_trace.get_reactive_power(),
        expected_sample_count,
    )
    comparison_records: list[dict[str, object]] = list((
        _build_comparison_record(
            "veragrid", "fmpy", retained_trace.get_veragrid_fmpy_metrics()
        ),
        _build_comparison_record(
            "veragrid", "omsimulator",
            retained_trace.get_veragrid_omsimulator_metrics(),
        ),
        _build_comparison_record(
            "fmpy", "omsimulator",
            retained_trace.get_fmpy_omsimulator_metrics(),
        ),
    ))

    mode_dir: Path = execution.get_fmu_path().parent
    retained_driver_path: Path = mode_dir / "omsimulator_driver.lua"
    retained_input_path: Path = mode_dir / "omsimulator_input.csv"
    retained_output_path: Path = mode_dir / "omsimulator_output.csv"
    retained_runtime_log_path: Path = mode_dir / "omsimulator.log"
    retained_stdout_path: Path = mode_dir / "omsimulator_stdout.log"
    retained_stderr_path: Path = mode_dir / "omsimulator_stderr.log"
    driver_record: dict[str, object] = _build_artifact_record(
        retained_driver_path,
        staging_dir,
    )
    driver_record["source_sha256"] = omsimulator_trace.get_driver_sha256()
    driver_record["before_sha256"] = omsimulator_trace.get_driver_sha256()
    driver_record["after_sha256"] = omsimulator_trace.get_driver_sha256()
    raw_evidence: dict[str, object] = dict(
        driver=driver_record,
        input=_build_artifact_record(retained_input_path, staging_dir),
        output=_build_artifact_record(retained_output_path, staging_dir),
        runtime_log=_build_artifact_record(retained_runtime_log_path, staging_dir),
        stdout=_build_artifact_record(retained_stdout_path, staging_dir),
        stderr=_build_artifact_record(retained_stderr_path, staging_dir),
    )
    process_arguments: tuple[str, ...] = mode_evidence.get_process_arguments()
    if mode == FmuInterfaceMode.CO_SIMULATION:
        protocol: dict[str, object] = dict(
            system_type="oms_system_wc",
            solver="oms_solver_wc_ma",
            configuration_source="explicit_status_checked_lua_and_process_argv",
            process_arguments=list(process_arguments),
            input_hold="u[i-1] on [t[i-1],t[i])",
            sample_side="stepUntil(t[i]); set u[i]; read outputs",
            fixed_step_seconds=scenario.time_step_seconds,
            absolute_tolerance=None,
            relative_tolerance=None,
            variable_initial_step_seconds=None,
            variable_minimum_step_seconds=None,
            variable_maximum_step_seconds=None,
            recorder_enabled=False,
        )
    elif mode == FmuInterfaceMode.MODEL_EXCHANGE:
        protocol = dict(
            system_type="oms_system_sc",
            solver="oms_solver_sc_cvode",
            configuration_source="explicit_status_checked_lua_and_process_argv",
            process_arguments=list(process_arguments),
            input_hold="u[i-1] on [t[i-1],t[i])",
            sample_side="stepUntil(t[i]); set u[i]; read outputs",
            fixed_step_seconds=None,
            absolute_tolerance=1.0e-10,
            relative_tolerance=1.0e-10,
            variable_initial_step_seconds=1.0e-5,
            variable_minimum_step_seconds=1.0e-8,
            variable_maximum_step_seconds=1.0e-3,
            recorder_enabled=False,
        )
    else:
        raise ValueError(f"Unsupported manifest mode: {mode.value}")
    event_boundary_index: int = scenario.event_boundary_index
    first_post_event_index: int = scenario.first_post_event_index
    post_event_voltage_response: float = float(np.max(np.abs(
        retained_voltage[first_post_event_index:]
        - retained_voltage[event_boundary_index]
    )))
    veragrid_active_power: np.ndarray = retained_trace.get_veragrid_active_power()
    post_event_active_power_response: float = float(np.max(np.abs(
        veragrid_active_power[first_post_event_index:]
        - veragrid_active_power[event_boundary_index]
    )))
    responses_are_conclusive: bool = bool(
        post_event_voltage_response
        >= scenario.voltage_response_threshold_pu
        and post_event_active_power_response
        >= scenario.active_power_response_threshold_pu
    )
    if responses_are_conclusive:
        pass
    else:
        raise RuntimeError("Mode evidence lacks the required event response")
    return dict(
        mode=mode.value,
        fmu_path=execution.get_fmu_path().relative_to(staging_dir).as_posix(),
        fmu_sha256=fmu_sha256,
        source_fmu_sha256_before=fmu_sha256,
        source_fmu_sha256_after=fmu_sha256,
        owned_fmu_sha256_before=fmu_sha256,
        owned_fmu_sha256_after=fmu_sha256,
        sample_count=expected_sample_count,
        trace_csv_path=(
            "co_simulation_trace.csv"
            if mode == FmuInterfaceMode.CO_SIMULATION
            else "model_exchange_trace.csv"
        ),
        report_path=execution.get_report_path().relative_to(staging_dir).as_posix(),
        fmpy_raw_evidence=_build_artifact_record(fmpy_raw_path, staging_dir),
        fmpy_time_alignment_max_error_seconds=fmpy_time_alignment,
        protocol=protocol,
        raw_evidence=raw_evidence,
        paths=list((
            veragrid_path_record,
            fmpy_path_record,
            omsimulator_path_record,
        )),
        comparisons=comparison_records,
        validation_issues=list(),
        rms_solver_tolerance=solver_tolerance,
        power_flow_residual=power_flow_residual,
        post_event_voltage_response=post_event_voltage_response,
        post_event_active_power_response=post_event_active_power_response,
        voltage_input_min=float(np.min(retained_voltage)),
        voltage_input_max=float(np.max(retained_voltage)),
    )


def _write_staged_manifest(
        staging_dir: Path,
        config: RmsFmiComparisonConfig,
        mode_evidence: tuple[RmsFmiModeEvidence, ...],
        scenario: RmsLoadPowerStepScenario,
) -> Path:
    """Write the complete schema-v3 evidence manifest last.

    :param staging_dir: Complete owned staging directory.
    :param config: Caller-declared provenance and runtime configuration.
    :param mode_evidence: Ordered CS and ME typed evidence owners.
    :param scenario: Scenario shared by execution and manifest producers.
    :return: Written manifest path.
    """

    modes_are_valid: bool = bool(
        len(mode_evidence) == 2
        and mode_evidence[0].get_execution().get_mode()
        == FmuInterfaceMode.CO_SIMULATION
        and mode_evidence[1].get_execution().get_mode()
        == FmuInterfaceMode.MODEL_EXCHANGE
    )
    if modes_are_valid:
        cs_omsimulator_trace: OmsimulatorTrace = (
            mode_evidence[0].get_omsimulator_trace()
        )
        me_omsimulator_trace: OmsimulatorTrace = (
            mode_evidence[1].get_omsimulator_trace()
        )
    else:
        raise RuntimeError("Manifest requires ordered CS and ME evidence")
    identities_are_stable: bool = bool(
        _hash_file(mode_evidence[0].get_execution().get_fmu_path())
        == mode_evidence[0].get_fmu_sha256()
        and _hash_file(mode_evidence[1].get_execution().get_fmu_path())
        == mode_evidence[1].get_fmu_sha256()
        and cs_omsimulator_trace.get_executable_sha256()
        == me_omsimulator_trace.get_executable_sha256()
        and cs_omsimulator_trace.get_driver_sha256()
        == me_omsimulator_trace.get_driver_sha256()
        and cs_omsimulator_trace.get_runtime_version()
        == me_omsimulator_trace.get_runtime_version()
    )
    if identities_are_stable:
        pass
    else:
        raise RuntimeError("FMU or OMSimulator identities changed during comparison")
    mode_records: list[dict[str, object]] = list()
    evidence: RmsFmiModeEvidence
    for evidence in mode_evidence:
        mode_records.append(_build_mode_record(staging_dir, evidence, scenario))

    artifact_relative_paths: list[str] = list()
    candidate_path: Path
    for candidate_path in staging_dir.rglob("*"):
        if candidate_path.is_symlink():
            raise RuntimeError("Comparison package cannot retain symbolic links")
        elif candidate_path.is_file():
            artifact_relative_paths.append(
                candidate_path.relative_to(staging_dir).as_posix()
            )
        else:
            pass
    artifact_relative_paths.sort()
    if len(artifact_relative_paths) == 32:
        pass
    else:
        raise RuntimeError(
            "Schema-v3 package requires exactly 32 artifacts, got "
            f"{len(artifact_relative_paths)}"
        )
    artifact_records: list[dict[str, object]] = list()
    artifact_relative_path: str
    for artifact_relative_path in artifact_relative_paths:
        artifact_records.append(
            _build_artifact_record(staging_dir / artifact_relative_path, staging_dir)
        )

    manifest_payload: dict[str, object] = dict(
        schema="veragrid.rms-fmi-comparison/3",
        status="CANDIDATE_EVIDENCE",
        source_identity=dict(
            provenance="caller_declared",
            revision=config.get_source_revision(),
            source_tree_sha256=config.get_source_tree_sha256(),
            verification="UNVERIFIED_BY_GENERATOR",
        ),
        runtime=dict(
            platform=platform.platform(),
            python=platform.python_version(),
            byte_order=sys.byteorder,
            numpy=importlib.metadata.version("numpy"),
            matplotlib=importlib.metadata.version("matplotlib"),
            fmpy=importlib.metadata.version("fmpy"),
            omsimulator=dict(
                name="OMSimulator",
                version=cs_omsimulator_trace.get_runtime_version(),
                executable_path_name=config.get_omsimulator_executable().name,
                executable_sha256_before=(
                    cs_omsimulator_trace.get_executable_sha256()
                ),
                executable_sha256_after=(
                    cs_omsimulator_trace.get_executable_sha256()
                ),
                driver_source_sha256=cs_omsimulator_trace.get_driver_sha256(),
                internal_timeout_seconds=30.0,
                process_timeout_seconds=config.get_omsimulator_timeout_seconds(),
            ),
        ),
        configuration=dict(
            sample_count=scenario.sample_count,
            time_step_seconds=scenario.time_step_seconds,
            stop_time_seconds=scenario.stop_time_seconds,
            time_alignment_tolerance_seconds=1.0e-12,
            input_alignment_tolerance_pu=1.0e-12,
            floating_absolute_term=config.get_absolute_tolerance(),
            floating_relative_coefficient=config.get_relative_tolerance(),
            pair_budget_formula=(
                "scale=max(abs(left),abs(right)); budget=floating_absolute_term+"
                "floating_relative_coefficient*scale+left_abs_allowance[i]+"
                "right_abs_allowance[i]+left_rel_allowance*scale+"
                "right_rel_allowance*scale; VeraGrid abs allowance="
                "rms_solver_tolerance+(i==0?power_flow_residual:0), rel allowance=0; "
                "FMPy abs allowance=0, rel allowance=0; OMSimulator abs allowance="
                "omsimulator_absolute_tolerance, rel allowance="
                "omsimulator_relative_tolerance"
            ),
            omsimulator_absolute_tolerance=(
                config.get_omsimulator_absolute_tolerance()
            ),
            omsimulator_relative_tolerance=(
                config.get_omsimulator_relative_tolerance()
            ),
            input_csv_header=list((
                "sample_index", "mode", "time_seconds", "voltage_magnitude_pu",
            )),
            raw_output_csv_header=list((
                "sample_index", "mode", "time_seconds", "voltage_magnitude_pu",
                "active_power_pu", "reactive_power_pu",
            )),
            combined_csv_header=list((
                "sample_index", "time_seconds", "regime", "scenario_phase",
                "voltage_magnitude_pu", "veragrid_active_power_pu",
                "fmpy_active_power_pu", "omsimulator_active_power_pu",
                "veragrid_reactive_power_pu", "fmpy_reactive_power_pu",
                "omsimulator_reactive_power_pu", "veragrid__fmpy_active_error_pu",
                "veragrid__fmpy_active_budget_pu",
                "veragrid__fmpy_reactive_error_pu",
                "veragrid__fmpy_reactive_budget_pu",
                "veragrid__omsimulator_active_error_pu",
                "veragrid__omsimulator_active_budget_pu",
                "veragrid__omsimulator_reactive_error_pu",
                "veragrid__omsimulator_reactive_budget_pu",
                "fmpy__omsimulator_active_error_pu",
                "fmpy__omsimulator_active_budget_pu",
                "fmpy__omsimulator_reactive_error_pu",
                "fmpy__omsimulator_reactive_budget_pu",
            )),
            file_limits_bytes=dict(
                driver=65536,
                input=65536,
                output=262144,
                report=65536,
                each_log=4194304,
                fmu=67108864,
                runtime_tree=134217728,
            ),
        ),
        event_scenario=scenario.build_manifest_event_record(),
        modes=mode_records,
        artifacts=artifact_records,
        backend_disclosure=(
            "VeraGrid and direct FMPy share the FMPy runtime backend; "
            "OMSimulator is the independent runtime path"
        ),
        claim_scope=(
            "FMI 2.0 CS/ME RMS orchestration compared across VeraGrid, direct "
            "FMPy, and OMSimulator on the recorded Windows host; zero-derivative "
            "fixture only; no solver-accuracy or cross-platform claim"
        ),
    )
    manifest_path: Path = staging_dir / "manifest.json"
    manifest_text: str = json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n"
    manifest_path.write_text(manifest_text, encoding="utf-8", newline="\n")
    return manifest_path


def _verify_manifest_sections(
        manifest: dict[object, object],
) -> tuple[
    dict[object, object],
    dict[object, object],
    list[object],
    list[object],
]:
    """Validate fixed schema-v3 sections and return typed boundary values.

    :param manifest: Parsed JSON root mapping.
    :return: Runtime, configuration, modes and artifacts sections.
    """

    expected_root_keys: set[str] = set((
        "schema", "status", "source_identity", "runtime", "configuration",
        "event_scenario", "modes", "artifacts", "backend_disclosure",
        "claim_scope",
    ))
    root_is_valid: bool = bool(
        set(manifest.keys()) == expected_root_keys
        and manifest.get("schema", None) == "veragrid.rms-fmi-comparison/3"
        and manifest.get("status", None) == "CANDIDATE_EVIDENCE"
        and manifest.get("backend_disclosure", None)
        == (
            "VeraGrid and direct FMPy share the FMPy runtime backend; "
            "OMSimulator is the independent runtime path"
        )
        and manifest.get("claim_scope", None)
        == (
            "FMI 2.0 CS/ME RMS orchestration compared across VeraGrid, direct "
            "FMPy, and OMSimulator on the recorded Windows host; zero-derivative "
            "fixture only; no solver-accuracy or cross-platform claim"
        )
    )
    if root_is_valid:
        pass
    else:
        raise RuntimeError("Staged RMS FMI schema-v3 root is invalid")
    source_value: object = manifest.get("source_identity", None)
    runtime_value: object = manifest.get("runtime", None)
    configuration_value: object = manifest.get("configuration", None)
    event_value: object = manifest.get("event_scenario", None)
    modes_value: object = manifest.get("modes", None)
    artifacts_value: object = manifest.get("artifacts", None)
    sections_are_typed: bool = bool(
        isinstance(source_value, dict)
        and isinstance(runtime_value, dict)
        and isinstance(configuration_value, dict)
        and isinstance(event_value, dict)
        and isinstance(modes_value, list)
        and isinstance(artifacts_value, list)
    )
    if sections_are_typed:
        source: dict[object, object] = source_value
        runtime: dict[object, object] = runtime_value
        configuration: dict[object, object] = configuration_value
        event: dict[object, object] = event_value
        mode_records: list[object] = modes_value
        artifact_records: list[object] = artifacts_value
    else:
        raise RuntimeError("Staged RMS FMI manifest sections have invalid types")
    source_revision: object = source.get("revision", None)
    source_hash: object = source.get("source_tree_sha256", None)
    source_is_valid: bool = bool(
        set(source.keys()) == set((
            "provenance", "revision", "source_tree_sha256", "verification",
        ))
        and source.get("provenance", None) == "caller_declared"
        and isinstance(source_revision, str)
        and bool(source_revision.strip())
        and isinstance(source_hash, str)
        and len(source_hash) == 64
        and source_hash == source_hash.lower()
        and all(character in "0123456789abcdef" for character in source_hash)
        and source.get("verification", None) == "UNVERIFIED_BY_GENERATOR"
    )
    if source_is_valid:
        pass
    else:
        raise RuntimeError("Staged source identity is incomplete")

    expected_input_header: list[str] = list((
        "sample_index", "mode", "time_seconds", "voltage_magnitude_pu",
    ))
    expected_output_header: list[str] = list((
        "sample_index", "mode", "time_seconds", "voltage_magnitude_pu",
        "active_power_pu", "reactive_power_pu",
    ))
    expected_combined_header: list[str] = list((
        "sample_index", "time_seconds", "regime", "scenario_phase",
        "voltage_magnitude_pu", "veragrid_active_power_pu",
        "fmpy_active_power_pu", "omsimulator_active_power_pu",
        "veragrid_reactive_power_pu", "fmpy_reactive_power_pu",
        "omsimulator_reactive_power_pu", "veragrid__fmpy_active_error_pu",
        "veragrid__fmpy_active_budget_pu", "veragrid__fmpy_reactive_error_pu",
        "veragrid__fmpy_reactive_budget_pu",
        "veragrid__omsimulator_active_error_pu",
        "veragrid__omsimulator_active_budget_pu",
        "veragrid__omsimulator_reactive_error_pu",
        "veragrid__omsimulator_reactive_budget_pu",
        "fmpy__omsimulator_active_error_pu",
        "fmpy__omsimulator_active_budget_pu",
        "fmpy__omsimulator_reactive_error_pu",
        "fmpy__omsimulator_reactive_budget_pu",
    ))
    expected_budget_formula: str = (
        "scale=max(abs(left),abs(right)); budget=floating_absolute_term+"
        "floating_relative_coefficient*scale+left_abs_allowance[i]+"
        "right_abs_allowance[i]+left_rel_allowance*scale+"
        "right_rel_allowance*scale; VeraGrid abs allowance="
        "rms_solver_tolerance+(i==0?power_flow_residual:0), rel allowance=0; "
        "FMPy abs allowance=0, rel allowance=0; OMSimulator abs allowance="
        "omsimulator_absolute_tolerance, rel allowance="
        "omsimulator_relative_tolerance"
    )
    file_limits_value: object = configuration.get("file_limits_bytes", None)
    if isinstance(file_limits_value, dict):
        file_limits: dict[object, object] = file_limits_value
    else:
        raise RuntimeError("Staged file limits are missing")
    absolute_term: object = configuration.get("floating_absolute_term", None)
    relative_coefficient: object = configuration.get(
        "floating_relative_coefficient",
        None,
    )
    comparison_numbers_are_valid: bool = bool(
        isinstance(absolute_term, (int, float))
        and not isinstance(absolute_term, bool)
        and math.isfinite(float(absolute_term))
        and float(absolute_term) > 0.0
        and isinstance(relative_coefficient, (int, float))
        and not isinstance(relative_coefficient, bool)
        and math.isfinite(float(relative_coefficient))
        and float(relative_coefficient) >= 0.0
    )
    configuration_is_valid: bool = bool(
        set(configuration.keys()) == set((
            "sample_count", "time_step_seconds", "stop_time_seconds",
            "time_alignment_tolerance_seconds", "input_alignment_tolerance_pu",
            "floating_absolute_term", "floating_relative_coefficient",
            "pair_budget_formula", "omsimulator_absolute_tolerance",
            "omsimulator_relative_tolerance", "input_csv_header",
            "raw_output_csv_header", "combined_csv_header", "file_limits_bytes",
        ))
        and comparison_numbers_are_valid
        and configuration.get("sample_count", None) == 301
        and configuration.get("time_step_seconds", None) == 1.0e-3
        and configuration.get("stop_time_seconds", None) == 0.3
        and configuration.get("time_alignment_tolerance_seconds", None) == 1.0e-12
        and configuration.get("input_alignment_tolerance_pu", None) == 1.0e-12
        and configuration.get("pair_budget_formula", None) == expected_budget_formula
        and configuration.get("omsimulator_absolute_tolerance", None) == 1.0e-10
        and configuration.get("omsimulator_relative_tolerance", None) == 1.0e-10
        and configuration.get("input_csv_header", None) == expected_input_header
        and configuration.get("raw_output_csv_header", None) == expected_output_header
        and configuration.get("combined_csv_header", None) == expected_combined_header
        and set(file_limits.keys()) == set((
            "driver", "input", "output", "report", "each_log", "fmu",
            "runtime_tree",
        ))
        and file_limits.get("driver", None) == 65536
        and file_limits.get("input", None) == 65536
        and file_limits.get("output", None) == 262144
        and file_limits.get("report", None) == 65536
        and file_limits.get("each_log", None) == 4194304
        and file_limits.get("fmu", None) == 67108864
        and file_limits.get("runtime_tree", None) == 134217728
    )
    if configuration_is_valid:
        pass
    else:
        raise RuntimeError("Staged numerical configuration is invalid")

    event_is_valid: bool = bool(
        set(event.keys()) == set((
            "kind", "parameter", "event_time_seconds", "event_boundary_index",
            "first_post_event_index", "boundary_semantics",
            "disturbance_load_initial_active_power_mw",
            "disturbance_load_initial_reactive_power_mvar", "pre_event_value_pu",
            "post_event_value_pu", "voltage_response_threshold_pu",
            "active_power_response_threshold_pu", "fmu_active_power_equation",
            "fmu_reactive_power_equation", "fmu_state_derivative",
            "fmu_state_initialization", "shared_input",
        ))
        and event.get("kind", None) == "RMS native load active-power step"
        and event.get("parameter", None) == "Pl0"
        and event.get("event_time_seconds", None) == 0.1
        and event.get("event_boundary_index", None) == 100
        and event.get("first_post_event_index", None) == 101
        and event.get("boundary_semantics", None)
        == "old_value_at_boundary_step_after_boundary"
        and event.get("disturbance_load_initial_active_power_mw", None) == 5.0
        and event.get("disturbance_load_initial_reactive_power_mvar", None) == 1.0
        and event.get("pre_event_value_pu", None) == -0.05
        and event.get("post_event_value_pu", None) == -0.15
        and event.get("voltage_response_threshold_pu", None) == 1.0e-5
        and event.get("active_power_response_threshold_pu", None) == 1.0e-5
        and event.get("fmu_active_power_equation", None)
        == "p_out = -0.1 - 2.0*(u - x)"
        and event.get("fmu_reactive_power_equation", None)
        == "q_out = -0.01 - (u - x)"
        and event.get("fmu_state_derivative", None) == "der(x) = 0"
        and event.get("fmu_state_initialization", None) == "x(0) = u(0)"
        and event.get("shared_input", None)
        == "u = retained VeraGrid RMS bus voltage magnitude"
    )
    if event_is_valid:
        pass
    else:
        raise RuntimeError("Staged event scenario is invalid")

    omsimulator_value: object = runtime.get("omsimulator", None)
    if isinstance(omsimulator_value, dict):
        omsimulator_runtime: dict[object, object] = omsimulator_value
    else:
        raise RuntimeError("Staged OMSimulator identity is missing")
    executable_hash_before: object = omsimulator_runtime.get(
        "executable_sha256_before",
        None,
    )
    executable_hash_after: object = omsimulator_runtime.get(
        "executable_sha256_after",
        None,
    )
    driver_source_hash: object = omsimulator_runtime.get(
        "driver_source_sha256",
        None,
    )
    runtime_is_valid: bool = bool(
        set(runtime.keys()) == set((
            "platform", "python", "byte_order", "numpy", "matplotlib", "fmpy",
            "omsimulator",
        ))
        and all(
            isinstance(runtime.get(name, None), str)
            and bool(runtime.get(name, None))
            for name in ("platform", "python", "numpy", "matplotlib", "fmpy")
        )
        and runtime.get("byte_order", None) in ("little", "big")
        and set(omsimulator_runtime.keys()) == set((
            "name", "version", "executable_path_name", "executable_sha256_before",
            "executable_sha256_after", "driver_source_sha256",
            "internal_timeout_seconds", "process_timeout_seconds",
        ))
        and omsimulator_runtime.get("name", None) == "OMSimulator"
        and isinstance(omsimulator_runtime.get("version", None), str)
        and bool(omsimulator_runtime.get("version", None))
        and isinstance(omsimulator_runtime.get("executable_path_name", None), str)
        and bool(omsimulator_runtime.get("executable_path_name", None))
        and isinstance(executable_hash_before, str)
        and executable_hash_before == executable_hash_after
        and len(executable_hash_before) == 64
        and executable_hash_before == executable_hash_before.lower()
        and all(
            character in "0123456789abcdef"
            for character in executable_hash_before
        )
        and isinstance(driver_source_hash, str)
        and len(driver_source_hash) == 64
        and driver_source_hash == driver_source_hash.lower()
        and all(character in "0123456789abcdef" for character in driver_source_hash)
        and omsimulator_runtime.get("internal_timeout_seconds", None) == 30.0
        and omsimulator_runtime.get("process_timeout_seconds", None) == 35.0
    )
    if runtime_is_valid:
        pass
    else:
        raise RuntimeError("Staged OMSimulator runtime identity is invalid")
    return runtime, configuration, mode_records, artifact_records


def _verify_artifact_records(
        staging_dir: Path,
        manifest_path: Path,
        artifact_records: list[object],
) -> dict[str, tuple[str, int]]:
    """Validate the exact regular-file tree and return artifact identities.

    :param staging_dir: Owned package directory.
    :param manifest_path: Manifest excluded from the artifact set.
    :param artifact_records: Parsed schema-v3 artifact records.
    :return: Mapping from safe relative path to hash and size.
    """

    if len(artifact_records) == 32:
        pass
    else:
        raise RuntimeError("Schema-v3 package must declare exactly 32 artifacts")
    staging_root: Path = staging_dir.resolve(strict=True)
    identities: dict[str, tuple[str, int]] = dict()
    declared_order: list[str] = list()
    record_value: object
    for record_value in artifact_records:
        if isinstance(record_value, dict):
            record: dict[object, object] = record_value
        else:
            raise RuntimeError("Staged artifact record must be an object")
        path_value: object = record.get("path", None)
        hash_value: object = record.get("sha256", None)
        size_value: object = record.get("size_bytes", None)
        record_is_typed: bool = bool(
            set(record.keys()) == set(("path", "sha256", "size_bytes"))
            and isinstance(path_value, str)
            and isinstance(hash_value, str)
            and len(hash_value) == 64
            and hash_value == hash_value.lower()
            and all(character in "0123456789abcdef" for character in hash_value)
            and isinstance(size_value, int)
            and not isinstance(size_value, bool)
            and size_value >= 0
        )
        if record_is_typed:
            relative_path: str = path_value
            declared_hash: str = hash_value
            declared_size: int = size_value
        else:
            raise RuntimeError("Staged artifact fields have invalid types")
        relative_candidate: Path = Path(relative_path)
        path_is_safe: bool = bool(
            bool(relative_path)
            and "\\" not in relative_path
            and relative_path == relative_candidate.as_posix()
            and not relative_candidate.is_absolute()
            and ".." not in relative_candidate.parts
            and relative_path != "manifest.json"
            and relative_path not in identities
        )
        if path_is_safe:
            unresolved_artifact_path: Path = staging_root / relative_candidate
        else:
            raise RuntimeError("Manifest artifact path is unsafe or duplicated")
        validated_artifact_path: Path = _verify_regular_file_path(
            unresolved_artifact_path,
            None,
            "Manifest artifact",
        )
        try:
            validated_artifact_path.relative_to(staging_root)
        except ValueError as path_error:
            raise RuntimeError("Manifest artifact escapes the package") from path_error
        identity_is_valid: bool = bool(
            validated_artifact_path.stat().st_size == declared_size
            and _hash_file(validated_artifact_path) == declared_hash
        )
        if identity_is_valid:
            identities[relative_path] = (declared_hash, declared_size)
            declared_order.append(relative_path)
        else:
            raise RuntimeError(f"Artifact identity mismatch: {relative_path}")
    actual_paths: set[str] = set()
    actual_path: Path
    for actual_path in staging_root.rglob("*"):
        if actual_path.is_symlink():
            raise RuntimeError("Package tree contains a symbolic link")
        elif actual_path.is_file() and actual_path != manifest_path:
            actual_paths.add(actual_path.relative_to(staging_root).as_posix())
        else:
            pass
    tree_is_valid: bool = bool(
        actual_paths == set(identities.keys())
        and declared_order == sorted(declared_order)
    )
    if tree_is_valid:
        return identities
    else:
        raise RuntimeError("Manifest is unsorted or does not cover the file tree")


def _verify_raw_evidence(
        csv_path: Path,
        mode: FmuInterfaceMode,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Parse one strict six-column FMPy or OMSimulator raw trace.

    :param csv_path: Retained raw trace file.
    :param mode: Expected FMI mode in every row.
    :return: Original time, voltage, active-power and reactive-power arrays.
    """

    validated_path: Path = _verify_regular_file_path(
        csv_path,
        262144,
        "Raw FMI trace CSV",
    )
    raw_bytes: bytes = validated_path.read_bytes()
    bytes_are_valid: bool = bool(
        raw_bytes.endswith(b"\n")
        and b"\r" not in raw_bytes
        and b"\xef\xbb\xbf" not in raw_bytes[:3]
        and b'"' not in raw_bytes
        and b"\n\n" not in raw_bytes
    )
    if bytes_are_valid:
        pass
    else:
        raise RuntimeError("Raw FMI CSV violates the byte contract")
    with validated_path.open("r", encoding="utf-8", newline="") as csv_file:
        rows: list[list[str]] = list(csv.reader(csv_file))
    expected_header: list[str] = list((
        "sample_index", "mode", "time_seconds", "voltage_magnitude_pu",
        "active_power_pu", "reactive_power_pu",
    ))
    shape_is_valid: bool = bool(
        len(rows) == 302
        and rows[0] == expected_header
        and all(len(row) == 6 for row in rows[1:])
    )
    if shape_is_valid:
        pass
    else:
        raise RuntimeError("Raw FMI CSV shape is invalid")
    values: np.ndarray = np.empty((4, 301), dtype=float)
    sample_index: int
    for sample_index in range(301):
        row: list[str] = rows[sample_index + 1]
        try:
            row_index: int = int(row[0])
            row_time: float = float(row[2])
            row_voltage: float = float(row[3])
            row_active: float = float(row[4])
            row_reactive: float = float(row[5])
        except ValueError as parse_error:
            raise RuntimeError("Raw FMI CSV contains malformed data") from parse_error
        row_is_valid: bool = bool(
            row[0] == str(sample_index)
            and row_index == sample_index
            and row[1] == mode.value
            and row[2] == f"{row_time:.17e}"
            and row[3] == f"{row_voltage:.17e}"
            and row[4] == f"{row_active:.17e}"
            and row[5] == f"{row_reactive:.17e}"
            and math.isfinite(row_time)
            and math.isfinite(row_voltage)
            and math.isfinite(row_active)
            and math.isfinite(row_reactive)
        )
        if row_is_valid:
            values[:, sample_index] = (
                row_time,
                row_voltage,
                row_active,
                row_reactive,
            )
        else:
            raise RuntimeError("Raw FMI CSV contains a noncanonical row")
    expected_time: np.ndarray = np.arange(301, dtype=float) * 1.0e-3
    trace_is_valid: bool = bool(
        np.all(np.diff(values[0, :]) > 0.0)
        and np.all(np.abs(values[0, :] - expected_time) <= 1.0e-12)
        and abs(values[1, 101] - values[1, 100]) > 1.0e-5
    )
    if trace_is_valid:
        return values[0, :], values[1, :], values[2, :], values[3, :]
    else:
        raise RuntimeError("Raw FMI trace violates time or event semantics")


def _verify_combined_trace(
        trace_path: Path,
        mode: FmuInterfaceMode,
        input_path: Path,
        fmpy_time: np.ndarray,
        fmpy_voltage: np.ndarray,
        fmpy_active: np.ndarray,
        fmpy_reactive: np.ndarray,
        omsimulator_time: np.ndarray,
        omsimulator_voltage: np.ndarray,
        omsimulator_active: np.ndarray,
        omsimulator_reactive: np.ndarray,
        solver_tolerance: float,
        power_flow_residual: float,
        comparison_absolute_term: float,
        comparison_relative_coefficient: float,
        omsimulator_absolute_tolerance: float,
        omsimulator_relative_tolerance: float,
) -> RmsFmiRetainedTrace:
    """Verify rowwise raw-to-combined relations and all pair budgets.

    :param trace_path: Retained 23-column combined CSV.
    :param mode: Expected FMI interface mode.
    :param input_path: Retained four-column OMSimulator input CSV.
    :param fmpy_time: Original direct-FMPy time values.
    :param fmpy_voltage: Direct-FMPy raw voltage values.
    :param fmpy_active: Direct-FMPy raw active power.
    :param fmpy_reactive: Direct-FMPy raw reactive power.
    :param omsimulator_time: Raw OMSimulator time values.
    :param omsimulator_voltage: Raw OMSimulator voltage values.
    :param omsimulator_active: Raw OMSimulator active power.
    :param omsimulator_reactive: Raw OMSimulator reactive power.
    :param solver_tolerance: Parsed RMS solver allowance.
    :param power_flow_residual: Parsed initial-projection allowance.
    :param comparison_absolute_term: Global absolute comparison term.
    :param comparison_relative_coefficient: Global relative comparison term.
    :param omsimulator_absolute_tolerance: OMSimulator absolute allowance.
    :param omsimulator_relative_tolerance: OMSimulator relative allowance.
    :return: Fully verified typed combined trace.
    """

    retained_trace: RmsFmiRetainedTrace = _read_retained_comparison_csv(trace_path)
    validated_input_path: Path = _verify_regular_file_path(
        input_path,
        65536,
        "OMSimulator input CSV",
    )
    with validated_input_path.open("r", encoding="utf-8", newline="") as csv_file:
        input_rows: list[list[str]] = list(csv.reader(csv_file))
    input_shape_is_valid: bool = bool(
        len(input_rows) == 302
        and input_rows[0] == [
            "sample_index", "mode", "time_seconds", "voltage_magnitude_pu",
        ]
        and all(len(row) == 4 for row in input_rows[1:])
    )
    if input_shape_is_valid:
        pass
    else:
        raise RuntimeError("OMSimulator input CSV shape is invalid")
    input_time: np.ndarray = np.empty(301, dtype=float)
    input_voltage: np.ndarray = np.empty(301, dtype=float)
    sample_index: int
    for sample_index in range(301):
        row: list[str] = input_rows[sample_index + 1]
        try:
            row_index: int = int(row[0])
            row_time: float = float(row[2])
            row_voltage: float = float(row[3])
        except ValueError as parse_error:
            raise RuntimeError("OMSimulator input CSV contains malformed data") from parse_error
        row_is_valid: bool = bool(
            row[0] == str(sample_index)
            and row_index == sample_index
            and row[1] == mode.value
            and row[2] == f"{row_time:.17e}"
            and row[3] == f"{row_voltage:.17e}"
            and math.isfinite(row_time)
            and math.isfinite(row_voltage)
        )
        if row_is_valid:
            input_time[sample_index] = row_time
            input_voltage[sample_index] = row_voltage
        else:
            raise RuntimeError("OMSimulator input CSV row is not canonical")
    retained_time: np.ndarray = retained_trace.get_time_seconds()
    retained_voltage: np.ndarray = retained_trace.get_voltage_magnitude()
    raw_relations_are_valid: bool = bool(
        np.array_equal(input_time, retained_time)
        and np.array_equal(input_voltage, retained_voltage)
        and np.all(np.abs(fmpy_time - retained_time) <= 1.0e-12)
        and np.array_equal(fmpy_voltage, retained_voltage)
        and np.array_equal(fmpy_active, retained_trace.get_fmpy_active_power())
        and np.array_equal(fmpy_reactive, retained_trace.get_fmpy_reactive_power())
        and np.all(np.abs(omsimulator_time - retained_time) <= 1.0e-12)
        and np.array_equal(omsimulator_voltage, retained_voltage)
        and np.array_equal(
            omsimulator_active,
            retained_trace.get_omsimulator_active_power(),
        )
        and np.array_equal(
            omsimulator_reactive,
            retained_trace.get_omsimulator_reactive_power(),
        )
    )
    if raw_relations_are_valid:
        pass
    else:
        raise RuntimeError("Raw and combined FMI rows diverge")
    veragrid_allowance: np.ndarray = np.full(301, solver_tolerance, dtype=float)
    veragrid_allowance[0] += power_flow_residual
    fmpy_allowance: np.ndarray = np.zeros(301, dtype=float)
    omsimulator_allowance: np.ndarray = np.full(
        301,
        omsimulator_absolute_tolerance,
        dtype=float,
    )
    expected_time_seconds: np.ndarray = np.arange(301, dtype=float) * 1.0e-3
    veragrid_fmpy_expected: RmsFmiComparisonMetrics = _compare_aligned_trajectories(
        retained_time,
        retained_trace.get_veragrid_active_power(),
        retained_trace.get_veragrid_reactive_power(),
        fmpy_time,
        fmpy_active,
        fmpy_reactive,
        veragrid_allowance,
        fmpy_allowance,
        0.0,
        0.0,
        comparison_absolute_term,
        comparison_relative_coefficient,
        expected_time_seconds,
    )
    veragrid_omsimulator_expected: RmsFmiComparisonMetrics = (
        _compare_aligned_trajectories(
            retained_time,
            retained_trace.get_veragrid_active_power(),
            retained_trace.get_veragrid_reactive_power(),
            omsimulator_time,
            omsimulator_active,
            omsimulator_reactive,
            veragrid_allowance,
            omsimulator_allowance,
            0.0,
            omsimulator_relative_tolerance,
            comparison_absolute_term,
            comparison_relative_coefficient,
            expected_time_seconds,
        )
    )
    fmpy_omsimulator_expected: RmsFmiComparisonMetrics = _compare_aligned_trajectories(
        fmpy_time,
        fmpy_active,
        fmpy_reactive,
        omsimulator_time,
        omsimulator_active,
        omsimulator_reactive,
        fmpy_allowance,
        omsimulator_allowance,
        0.0,
        omsimulator_relative_tolerance,
        comparison_absolute_term,
        comparison_relative_coefficient,
        expected_time_seconds,
    )
    retained_metrics: tuple[RmsFmiComparisonMetrics, ...] = (
        retained_trace.get_veragrid_fmpy_metrics(),
        retained_trace.get_veragrid_omsimulator_metrics(),
        retained_trace.get_fmpy_omsimulator_metrics(),
    )
    expected_metrics: tuple[RmsFmiComparisonMetrics, ...] = (
        veragrid_fmpy_expected,
        veragrid_omsimulator_expected,
        fmpy_omsimulator_expected,
    )
    pair_index: int
    for pair_index in range(3):
        retained_metric: RmsFmiComparisonMetrics = retained_metrics[pair_index]
        expected_metric: RmsFmiComparisonMetrics = expected_metrics[pair_index]
        metrics_are_equal: bool = bool(
            np.array_equal(
                retained_metric.get_absolute_active_power_error(),
                expected_metric.get_absolute_active_power_error(),
            )
            and np.array_equal(
                retained_metric.get_absolute_reactive_power_error(),
                expected_metric.get_absolute_reactive_power_error(),
            )
            and np.array_equal(
                retained_metric.get_active_power_budget(),
                expected_metric.get_active_power_budget(),
            )
            and np.array_equal(
                retained_metric.get_reactive_power_budget(),
                expected_metric.get_reactive_power_budget(),
            )
        )
        if metrics_are_equal:
            pass
        else:
            raise RuntimeError("Combined FMI error or budget differs from formula")
    return retained_trace


def _verify_mode_record(
        staging_root: Path,
        mode_record_value: object,
        expected_mode: FmuInterfaceMode,
        artifact_identities: dict[str, tuple[str, int]],
        driver_source_hash: str,
        comparison_absolute_term: float,
        comparison_relative_coefficient: float,
        omsimulator_absolute_tolerance: float,
        omsimulator_relative_tolerance: float,
) -> set[str]:
    """Validate one schema-v3 mode and return all semantic file references.

    :param staging_root: Resolved package root.
    :param mode_record_value: Parsed JSON mode value.
    :param expected_mode: Required ordered FMI mode.
    :param artifact_identities: Verified artifact hash and size records.
    :param driver_source_hash: Manifest runtime driver identity.
    :param comparison_absolute_term: Manifest absolute comparison term.
    :param comparison_relative_coefficient: Manifest relative coefficient.
    :param omsimulator_absolute_tolerance: Manifest OMSimulator absolute term.
    :param omsimulator_relative_tolerance: Manifest OMSimulator relative term.
    :return: Exact semantic artifact paths referenced by the mode.
    """

    if isinstance(mode_record_value, dict):
        mode_record: dict[object, object] = mode_record_value
    else:
        raise RuntimeError("Staged mode record must be an object")
    expected_mode_keys: set[str] = set((
        "mode", "fmu_path", "fmu_sha256", "source_fmu_sha256_before",
        "source_fmu_sha256_after", "owned_fmu_sha256_before",
        "owned_fmu_sha256_after", "sample_count", "trace_csv_path",
        "report_path", "fmpy_raw_evidence",
        "fmpy_time_alignment_max_error_seconds", "protocol", "raw_evidence",
        "paths", "comparisons", "validation_issues", "rms_solver_tolerance",
        "power_flow_residual", "post_event_voltage_response",
        "post_event_active_power_response", "voltage_input_min",
        "voltage_input_max",
    ))
    fmu_path_value: object = mode_record.get("fmu_path", None)
    trace_path_value: object = mode_record.get("trace_csv_path", None)
    report_path_value: object = mode_record.get("report_path", None)
    fmpy_record_value: object = mode_record.get("fmpy_raw_evidence", None)
    raw_evidence_value: object = mode_record.get("raw_evidence", None)
    path_records_value: object = mode_record.get("paths", None)
    comparison_records_value: object = mode_record.get("comparisons", None)
    mode_is_typed: bool = bool(
        set(mode_record.keys()) == expected_mode_keys
        and mode_record.get("mode", None) == expected_mode.value
        and mode_record.get("sample_count", None) == 301
        and isinstance(fmu_path_value, str)
        and isinstance(trace_path_value, str)
        and isinstance(report_path_value, str)
        and isinstance(fmpy_record_value, dict)
        and isinstance(raw_evidence_value, dict)
        and isinstance(path_records_value, list)
        and len(path_records_value) == 3
        and isinstance(comparison_records_value, list)
        and len(comparison_records_value) == 3
        and mode_record.get("validation_issues", None) == list()
    )
    if mode_is_typed:
        fmu_relative_path: str = fmu_path_value
        trace_relative_path: str = trace_path_value
        report_relative_path: str = report_path_value
        fmpy_record: dict[object, object] = fmpy_record_value
        raw_evidence: dict[object, object] = raw_evidence_value
        path_records: list[object] = path_records_value
        comparison_records: list[object] = comparison_records_value
    else:
        raise RuntimeError("Staged mode record is incomplete")
    fmpy_path_value: object = fmpy_record.get("path", None)
    if isinstance(fmpy_path_value, str):
        fmpy_relative_path: str = fmpy_path_value
    else:
        raise RuntimeError("Direct-FMPy evidence path is invalid")
    expected_raw_names: tuple[str, ...] = (
        "driver", "input", "output", "runtime_log", "stdout", "stderr",
    )
    if set(raw_evidence.keys()) == set(expected_raw_names):
        pass
    else:
        raise RuntimeError("OMSimulator raw evidence is incomplete")
    raw_relative_paths: dict[str, str] = dict()
    raw_name: str
    for raw_name in expected_raw_names:
        raw_record_value: object = raw_evidence.get(raw_name, None)
        if isinstance(raw_record_value, dict):
            raw_record: dict[object, object] = raw_record_value
        else:
            raise RuntimeError("OMSimulator raw record must be an object")
        expected_raw_keys: set[str]
        if raw_name == "driver":
            expected_raw_keys = set((
                "path", "sha256", "size_bytes", "source_sha256",
                "before_sha256", "after_sha256",
            ))
        else:
            expected_raw_keys = set(("path", "sha256", "size_bytes"))
        raw_path_value: object = raw_record.get("path", None)
        raw_hash_value: object = raw_record.get("sha256", None)
        raw_size_value: object = raw_record.get("size_bytes", None)
        raw_size_limit: int
        if raw_name == "driver" or raw_name == "input":
            raw_size_limit = 65536
        elif raw_name == "output":
            raw_size_limit = 262144
        else:
            raw_size_limit = 4194304
        raw_record_is_valid: bool = bool(
            set(raw_record.keys()) == expected_raw_keys
            and isinstance(raw_path_value, str)
            and raw_path_value in artifact_identities
            and isinstance(raw_hash_value, str)
            and isinstance(raw_size_value, int)
            and not isinstance(raw_size_value, bool)
            and raw_size_value <= raw_size_limit
            and artifact_identities.get(raw_path_value, None)
            == (raw_hash_value, raw_size_value)
        )
        if raw_record_is_valid:
            raw_relative_paths[raw_name] = raw_path_value
        else:
            raise RuntimeError("OMSimulator raw record identity is invalid")
        if raw_name == "driver":
            driver_is_valid: bool = bool(
                raw_record.get("source_sha256", None) == driver_source_hash
                and raw_record.get("before_sha256", None) == driver_source_hash
                and raw_record.get("after_sha256", None) == driver_source_hash
                and raw_hash_value == driver_source_hash
            )
            if driver_is_valid:
                pass
            else:
                raise RuntimeError("OMSimulator driver identity changed")
        else:
            pass
    fmpy_record_is_valid: bool = bool(
        set(fmpy_record.keys()) == set(("path", "sha256", "size_bytes"))
        and fmpy_relative_path in artifact_identities
        and isinstance(fmpy_record.get("sha256", None), str)
        and isinstance(fmpy_record.get("size_bytes", None), int)
        and not isinstance(fmpy_record.get("size_bytes", None), bool)
        and fmpy_record.get("size_bytes", None) <= 262144
        and artifact_identities.get(fmpy_relative_path, None)
        == (fmpy_record.get("sha256", None), fmpy_record.get("size_bytes", None))
    )
    if fmpy_record_is_valid:
        pass
    else:
        raise RuntimeError("Direct-FMPy evidence identity is invalid")
    semantic_paths: set[str] = set((
        fmu_relative_path,
        trace_relative_path,
        report_relative_path,
        fmpy_relative_path,
    ))
    semantic_paths.update(raw_relative_paths.values())
    semantic_paths_are_valid: bool = bool(
        len(semantic_paths) == 10
        and semantic_paths.issubset(set(artifact_identities.keys()))
    )
    if semantic_paths_are_valid:
        pass
    else:
        raise RuntimeError("Mode semantic files alias or lack artifacts")

    fmu_hash_value: object = mode_record.get("fmu_sha256", None)
    fmu_identity_is_valid: bool = bool(
        isinstance(fmu_hash_value, str)
        and artifact_identities.get(fmu_relative_path, None) is not None
        and artifact_identities[fmu_relative_path][0] == fmu_hash_value
        and artifact_identities[fmu_relative_path][1] <= 67108864
        and mode_record.get("source_fmu_sha256_before", None) == fmu_hash_value
        and mode_record.get("source_fmu_sha256_after", None) == fmu_hash_value
        and mode_record.get("owned_fmu_sha256_before", None) == fmu_hash_value
        and mode_record.get("owned_fmu_sha256_after", None) == fmu_hash_value
    )
    if fmu_identity_is_valid:
        fmu_sha256: str = fmu_hash_value
    else:
        raise RuntimeError("FMU identity changed across runtime ownership")

    protocol_value: object = mode_record.get("protocol", None)
    if isinstance(protocol_value, dict):
        protocol: dict[object, object] = protocol_value
    else:
        raise RuntimeError("OMSimulator protocol is missing")
    expected_protocol_keys: set[str] = set((
        "system_type", "solver", "configuration_source", "process_arguments",
        "input_hold", "sample_side", "fixed_step_seconds",
        "absolute_tolerance", "relative_tolerance",
        "variable_initial_step_seconds", "variable_minimum_step_seconds",
        "variable_maximum_step_seconds", "recorder_enabled",
    ))
    if expected_mode == FmuInterfaceMode.CO_SIMULATION:
        expected_protocol: dict[str, object] = dict(
            system_type="oms_system_wc",
            solver="oms_solver_wc_ma",
            configuration_source="explicit_status_checked_lua_and_process_argv",
            process_arguments=list((
                "--workingDir=.", "--tempDir=temp", "--deleteTempFiles=true",
                "--logFile=omsimulator.log", "--suppressPath=true",
                "--timeout=30", "omsimulator_driver.lua",
            )),
            input_hold="u[i-1] on [t[i-1],t[i])",
            sample_side="stepUntil(t[i]); set u[i]; read outputs",
            fixed_step_seconds=1.0e-3,
            absolute_tolerance=None,
            relative_tolerance=None,
            variable_initial_step_seconds=None,
            variable_minimum_step_seconds=None,
            variable_maximum_step_seconds=None,
            recorder_enabled=False,
        )
    elif expected_mode == FmuInterfaceMode.MODEL_EXCHANGE:
        expected_protocol = dict(
            system_type="oms_system_sc",
            solver="oms_solver_sc_cvode",
            configuration_source="explicit_status_checked_lua_and_process_argv",
            process_arguments=list((
                "--workingDir=.", "--tempDir=temp", "--deleteTempFiles=true",
                "--logFile=omsimulator.log", "--suppressPath=true",
                "--timeout=30", "--stepSize=1e-5,1e-8,1e-3",
                "omsimulator_driver.lua",
            )),
            input_hold="u[i-1] on [t[i-1],t[i])",
            sample_side="stepUntil(t[i]); set u[i]; read outputs",
            fixed_step_seconds=None,
            absolute_tolerance=1.0e-10,
            relative_tolerance=1.0e-10,
            variable_initial_step_seconds=1.0e-5,
            variable_minimum_step_seconds=1.0e-8,
            variable_maximum_step_seconds=1.0e-3,
            recorder_enabled=False,
        )
    else:
        raise RuntimeError("Unexpected FMI mode in staged package")
    if set(protocol.keys()) == expected_protocol_keys and protocol == expected_protocol:
        pass
    else:
        raise RuntimeError("OMSimulator protocol differs from the contract")

    report_path: Path = staging_root / report_relative_path
    solver_tolerance: float
    power_flow_residual: float
    solver_tolerance, power_flow_residual = _read_rms_report_scalars(report_path)
    scalar_names: tuple[str, ...] = (
        "fmpy_time_alignment_max_error_seconds",
        "rms_solver_tolerance",
        "power_flow_residual",
        "post_event_voltage_response",
        "post_event_active_power_response",
        "voltage_input_min",
        "voltage_input_max",
    )
    scalar_name: str
    for scalar_name in scalar_names:
        scalar_value: object = mode_record.get(scalar_name, None)
        scalar_is_valid: bool = bool(
            isinstance(scalar_value, (int, float))
            and not isinstance(scalar_value, bool)
            and math.isfinite(float(scalar_value))
        )
        if scalar_is_valid:
            pass
        else:
            raise RuntimeError(f"Mode scalar is invalid: {scalar_name}")
    report_scalars_match: bool = bool(
        mode_record.get("rms_solver_tolerance", None) == solver_tolerance
        and mode_record.get("power_flow_residual", None) == power_flow_residual
        and solver_tolerance >= 0.0
        and power_flow_residual >= 0.0
    )
    if report_scalars_match:
        pass
    else:
        raise RuntimeError("Manifest and RMS report scalars diverge")

    fmpy_path: Path = staging_root / fmpy_relative_path
    omsimulator_output_path: Path = staging_root / raw_relative_paths["output"]
    fmpy_time: np.ndarray
    fmpy_voltage: np.ndarray
    fmpy_active: np.ndarray
    fmpy_reactive: np.ndarray
    omsimulator_time: np.ndarray
    omsimulator_voltage: np.ndarray
    omsimulator_active: np.ndarray
    omsimulator_reactive: np.ndarray
    fmpy_time, fmpy_voltage, fmpy_active, fmpy_reactive = _verify_raw_evidence(
        fmpy_path,
        expected_mode,
    )
    (
        omsimulator_time,
        omsimulator_voltage,
        omsimulator_active,
        omsimulator_reactive,
    ) = _verify_raw_evidence(omsimulator_output_path, expected_mode)
    retained_trace: RmsFmiRetainedTrace = _verify_combined_trace(
        staging_root / trace_relative_path,
        expected_mode,
        staging_root / raw_relative_paths["input"],
        fmpy_time,
        fmpy_voltage,
        fmpy_active,
        fmpy_reactive,
        omsimulator_time,
        omsimulator_voltage,
        omsimulator_active,
        omsimulator_reactive,
        solver_tolerance,
        power_flow_residual,
        comparison_absolute_term,
        comparison_relative_coefficient,
        omsimulator_absolute_tolerance,
        omsimulator_relative_tolerance,
    )
    retained_time: np.ndarray = retained_trace.get_time_seconds()
    retained_voltage: np.ndarray = retained_trace.get_voltage_magnitude()
    alignment_error: float = float(np.max(np.abs(fmpy_time - retained_time)))
    veragrid_active: np.ndarray = retained_trace.get_veragrid_active_power()
    voltage_response: float = float(np.max(np.abs(
        retained_voltage[101:] - retained_voltage[100]
    )))
    active_response: float = float(np.max(np.abs(
        veragrid_active[101:] - veragrid_active[100]
    )))
    derived_scalars_match: bool = bool(
        mode_record.get("fmpy_time_alignment_max_error_seconds", None)
        == alignment_error
        and alignment_error <= 1.0e-12
        and mode_record.get("post_event_voltage_response", None) == voltage_response
        and mode_record.get("post_event_active_power_response", None)
        == active_response
        and voltage_response >= 1.0e-5
        and active_response >= 1.0e-5
        and mode_record.get("voltage_input_min", None)
        == float(np.min(retained_voltage))
        and mode_record.get("voltage_input_max", None)
        == float(np.max(retained_voltage))
    )
    if derived_scalars_match:
        pass
    else:
        raise RuntimeError("Mode scalar does not equal retained evidence")

    expected_paths: list[dict[str, object]] = list((
        _build_path_record(
            "veragrid", "FMPy", False, fmu_sha256,
            retained_time,
            retained_voltage,
            veragrid_active,
            retained_trace.get_veragrid_reactive_power(),
            301,
        ),
        _build_path_record(
            "fmpy", "FMPy", False, fmu_sha256,
            fmpy_time, fmpy_voltage, fmpy_active, fmpy_reactive,
            301,
        ),
        _build_path_record(
            "omsimulator", "OMSimulator", True, fmu_sha256,
            omsimulator_time,
            omsimulator_voltage,
            omsimulator_active,
            omsimulator_reactive,
            301,
        ),
    ))
    if path_records == expected_paths:
        pass
    else:
        raise RuntimeError("Mode path identities differ from retained bytes")
    expected_comparisons: list[dict[str, object]] = list((
        _build_comparison_record(
            "veragrid", "fmpy", retained_trace.get_veragrid_fmpy_metrics()
        ),
        _build_comparison_record(
            "veragrid", "omsimulator",
            retained_trace.get_veragrid_omsimulator_metrics(),
        ),
        _build_comparison_record(
            "fmpy", "omsimulator",
            retained_trace.get_fmpy_omsimulator_metrics(),
        ),
    ))
    if comparison_records == expected_comparisons:
        return semantic_paths
    else:
        raise RuntimeError("Mode comparison summaries differ from retained CSV")


def _verify_staged_package(staging_dir: Path) -> None:
    """Verify the complete schema-v3 package before or after publication.

    :param staging_dir: Complete package directory to verify fail-closed.
    :return: None.
    """

    if staging_dir.is_symlink() or not staging_dir.is_dir():
        raise RuntimeError("RMS FMI package root must be a regular directory")
    else:
        staging_root: Path = staging_dir.resolve(strict=True)
    manifest_candidate: Path = staging_root / "manifest.json"
    manifest_path: Path = _verify_regular_file_path(
        manifest_candidate,
        None,
        "RMS FMI manifest",
    )
    try:
        manifest_payload: object = json.loads(
            manifest_path.read_text(encoding="utf-8", errors="strict")
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as parse_error:
        raise RuntimeError("RMS FMI manifest is not strict JSON UTF-8") from parse_error
    if isinstance(manifest_payload, dict):
        manifest: dict[object, object] = manifest_payload
    else:
        raise RuntimeError("RMS FMI manifest root must be an object")
    runtime: dict[object, object]
    configuration: dict[object, object]
    mode_records: list[object]
    artifact_records: list[object]
    runtime, configuration, mode_records, artifact_records = (
        _verify_manifest_sections(manifest)
    )
    artifact_identities: dict[str, tuple[str, int]] = _verify_artifact_records(
        staging_root,
        manifest_path,
        artifact_records,
    )
    if len(mode_records) == 2:
        pass
    else:
        raise RuntimeError("Schema-v3 package must contain exactly two modes")
    omsimulator_value: object = runtime.get("omsimulator", None)
    if isinstance(omsimulator_value, dict):
        omsimulator_runtime: dict[object, object] = omsimulator_value
    else:
        raise RuntimeError("OMSimulator runtime section is invalid")
    driver_source_value: object = omsimulator_runtime.get(
        "driver_source_sha256",
        None,
    )
    if isinstance(driver_source_value, str):
        driver_source_hash: str = driver_source_value
    else:
        raise RuntimeError("OMSimulator driver identity is invalid")
    comparison_absolute_term: float = float(
        configuration.get("floating_absolute_term", 0.0)
    )
    comparison_relative_coefficient: float = float(
        configuration.get("floating_relative_coefficient", 0.0)
    )
    omsimulator_absolute_tolerance: float = float(
        configuration.get("omsimulator_absolute_tolerance", 0.0)
    )
    omsimulator_relative_tolerance: float = float(
        configuration.get("omsimulator_relative_tolerance", 0.0)
    )
    expected_modes: tuple[FmuInterfaceMode, ...] = (
        FmuInterfaceMode.CO_SIMULATION,
        FmuInterfaceMode.MODEL_EXCHANGE,
    )
    referenced_paths: set[str] = set()
    mode_index: int
    for mode_index in range(2):
        mode_paths: set[str] = _verify_mode_record(
            staging_root,
            mode_records[mode_index],
            expected_modes[mode_index],
            artifact_identities,
            driver_source_hash,
            comparison_absolute_term,
            comparison_relative_coefficient,
            omsimulator_absolute_tolerance,
            omsimulator_relative_tolerance,
        )
        if referenced_paths.isdisjoint(mode_paths):
            referenced_paths.update(mode_paths)
        else:
            raise RuntimeError("Mode artifact references alias one another")
    figure_paths: set[str] = set()
    mode_stem: str
    for mode_stem in ("co_simulation", "model_exchange"):
        figure_kind: str
        for figure_kind in ("trajectories", "absolute_error"):
            figure_extension: str
            for figure_extension in ("pdf", "svg", "png"):
                figure_paths.add(
                    f"figures/{mode_stem}_{figure_kind}.{figure_extension}"
                )
    if referenced_paths.union(figure_paths) == set(artifact_identities.keys()):
        pass
    else:
        raise RuntimeError("Schema-v3 artifact references are incomplete")
    figure_relative_path: str
    for figure_relative_path in figure_paths:
        figure_path: Path = staging_root / figure_relative_path
        figure_bytes: bytes = figure_path.read_bytes()
        if figure_relative_path.endswith(".png"):
            figure_is_valid: bool = bool(
                len(figure_bytes) >= 24
                and figure_bytes[:8] == b"\x89PNG\r\n\x1a\n"
                and int.from_bytes(figure_bytes[16:20], "big") == 2160
                and int.from_bytes(figure_bytes[20:24], "big") == 1440
            )
        elif figure_relative_path.endswith(".pdf"):
            figure_is_valid = figure_bytes.startswith(b"%PDF-")
        else:
            try:
                svg_text: str = figure_bytes.decode("utf-8", errors="strict")
            except UnicodeDecodeError as decode_error:
                raise RuntimeError("SVG figure is not strict UTF-8") from decode_error
            figure_is_valid = bool(
                "<svg" in svg_text
                and "<image" not in svg_text.lower()
            )
        if figure_is_valid:
            pass
        else:
            raise RuntimeError(f"Scientific figure is invalid: {figure_relative_path}")


def _publish_staged_package(staging_dir: Path, final_dir: Path) -> Path:
    """Verify and atomically rename one owned sibling staging directory.

    :param staging_dir: Owned complete staging directory.
    :param final_dir: Nonexistent final package destination.
    :return: Published final directory.
    """

    same_parent: bool = bool(
        staging_dir.resolve().parent == final_dir.resolve().parent
    )
    if same_parent and not final_dir.exists():
        pass
    else:
        raise FileExistsError(
            "Atomic publication requires sibling staging and a nonexistent destination"
        )
    _verify_staged_package(staging_dir)
    os.replace(staging_dir, final_dir)
    try:
        # The rename is the publication boundary; rehash the complete package
        # at its final name before returning conclusive candidate evidence.
        _verify_staged_package(final_dir)
    except RuntimeError as verification_error:
        try:
            shutil.rmtree(final_dir)
        except OSError as cleanup_error:
            verification_error.add_note(
                f"Published-package cleanup also failed: {cleanup_error}"
            )
        raise
    return final_dir


def generate_rms_fmi_comparison(config: RmsFmiComparisonConfig) -> Path:
    """Generate and atomically publish the complete RMS FMI comparison package.

    :param config: Validated destination, provenance and floating tolerances.
    :return: Published package directory.
    """

    # Resolve one validated scenario copy before any filesystem effect;
    # every producer below receives the same local scenario value.
    scenario: RmsLoadPowerStepScenario = config.get_scenario()
    expected_time_seconds: np.ndarray = scenario.build_time_lattice()
    final_dir: Path = config.get_output_dir()
    if final_dir.exists():
        raise FileExistsError(f"RMS FMI comparison destination exists: {final_dir}")
    else:
        final_dir.parent.mkdir(parents=True, exist_ok=True)

    staging_dir: Path = Path(
        tempfile.mkdtemp(
            prefix=f".{final_dir.name}.stage-",
            dir=str(final_dir.parent),
        )
    ).resolve()
    published: bool = False
    try:
        cs_dir: Path = staging_dir / "co_simulation"
        me_dir: Path = staging_dir / "model_exchange"
        figures_dir: Path = staging_dir / "figures"
        cs_dir.mkdir()
        me_dir.mkdir()
        figures_dir.mkdir()

        # Export each mode once so all three runtime paths consume the exact
        # same immutable FMU archive for that mode.
        cs_execution: RmsFmiExampleExecution = execute_rms_fmi_example(
            cs_dir,
            FmuInterfaceMode.CO_SIMULATION,
            scenario,
        )
        cs_fmu_sha256: str = _hash_file(cs_execution.get_fmu_path())
        cs_validation_issues: list[str] = validate_cs_fmu_with_fmpy(
            cs_execution.get_fmu_path(),
            extraction_root=cs_dir,
        )
        if len(cs_validation_issues) == 0:
            pass
        else:
            raise RuntimeError(
                f"Co-Simulation FMU validation issues: {cs_validation_issues}"
            )
        cs_fmpy_time: np.ndarray
        cs_fmpy_active_power: np.ndarray
        cs_fmpy_reactive_power: np.ndarray
        (
            cs_fmpy_time,
            cs_fmpy_active_power,
            cs_fmpy_reactive_power,
        ) = _get_direct_fmpy_trace(cs_execution, cs_dir, scenario)
        cs_voltage_magnitude: np.ndarray | None = (
            cs_execution.get_voltage_magnitude()
        )
        if cs_voltage_magnitude is not None:
            pass
        else:
            raise RuntimeError("Co-Simulation evidence lacks its voltage input")
        cs_fmpy_raw_path: Path = _write_fmpy_trace_csv(
            cs_dir / "direct_fmpy_output.csv",
            FmuInterfaceMode.CO_SIMULATION,
            cs_fmpy_time,
            cs_voltage_magnitude,
            cs_fmpy_active_power,
            cs_fmpy_reactive_power,
            scenario,
        )
        cs_omsimulator_trace: OmsimulatorTrace
        cs_process_arguments: tuple[str, ...]
        (
            cs_omsimulator_trace,
            cs_process_arguments,
        ) = execute_omsimulator_trace(
            executable_path=config.get_omsimulator_executable(),
            mode=FmuInterfaceMode.CO_SIMULATION,
            fmu_path=cs_execution.get_fmu_path(),
            output_dir=cs_dir,
            time_seconds=cs_execution.get_time_seconds(),
            voltage_magnitude=cs_voltage_magnitude,
            timeout_seconds=config.get_omsimulator_timeout_seconds(),
        )

        me_execution: RmsFmiExampleExecution = execute_rms_fmi_example(
            me_dir,
            FmuInterfaceMode.MODEL_EXCHANGE,
            scenario,
        )
        me_fmu_sha256: str = _hash_file(me_execution.get_fmu_path())
        me_validation_issues: list[str] = validate_me_fmu_with_fmpy(
            me_execution.get_fmu_path(),
            extraction_root=me_dir,
        )
        if len(me_validation_issues) == 0:
            pass
        else:
            raise RuntimeError(
                f"Model Exchange FMU validation issues: {me_validation_issues}"
            )
        me_fmpy_time: np.ndarray
        me_fmpy_active_power: np.ndarray
        me_fmpy_reactive_power: np.ndarray
        (
            me_fmpy_time,
            me_fmpy_active_power,
            me_fmpy_reactive_power,
        ) = _get_direct_fmpy_trace(me_execution, me_dir, scenario)
        me_voltage_magnitude: np.ndarray | None = (
            me_execution.get_voltage_magnitude()
        )
        if me_voltage_magnitude is not None:
            pass
        else:
            raise RuntimeError("Model Exchange evidence lacks its voltage input")
        me_fmpy_raw_path: Path = _write_fmpy_trace_csv(
            me_dir / "direct_fmpy_output.csv",
            FmuInterfaceMode.MODEL_EXCHANGE,
            me_fmpy_time,
            me_voltage_magnitude,
            me_fmpy_active_power,
            me_fmpy_reactive_power,
            scenario,
        )
        me_omsimulator_trace: OmsimulatorTrace
        me_process_arguments: tuple[str, ...]
        (
            me_omsimulator_trace,
            me_process_arguments,
        ) = execute_omsimulator_trace(
            executable_path=config.get_omsimulator_executable(),
            mode=FmuInterfaceMode.MODEL_EXCHANGE,
            fmu_path=me_execution.get_fmu_path(),
            output_dir=me_dir,
            time_seconds=me_execution.get_time_seconds(),
            voltage_magnitude=me_voltage_magnitude,
            timeout_seconds=config.get_omsimulator_timeout_seconds(),
        )

        # VeraGrid has a solver allowance at every accepted sample and an
        # additional power-flow residual only at the initial projection.
        sample_count: int = scenario.sample_count
        cs_veragrid_allowance: np.ndarray = np.full(
            sample_count,
            cs_execution.get_solver_tolerance(),
            dtype=float,
        )
        cs_veragrid_allowance[0] += cs_execution.get_power_flow_residual()
        me_veragrid_allowance: np.ndarray = np.full(
            sample_count,
            me_execution.get_solver_tolerance(),
            dtype=float,
        )
        me_veragrid_allowance[0] += me_execution.get_power_flow_residual()
        fmpy_allowance: np.ndarray = np.zeros(sample_count, dtype=float)
        omsimulator_allowance: np.ndarray = np.full(
            sample_count,
            config.get_omsimulator_absolute_tolerance(),
            dtype=float,
        )

        cs_veragrid_fmpy_metrics: RmsFmiComparisonMetrics = (
            _compare_aligned_trajectories(
                left_time_seconds=cs_execution.get_time_seconds(),
                left_active_power=cs_execution.get_active_power(),
                left_reactive_power=cs_execution.get_reactive_power(),
                right_time_seconds=cs_fmpy_time,
                right_active_power=cs_fmpy_active_power,
                right_reactive_power=cs_fmpy_reactive_power,
                left_absolute_allowance=cs_veragrid_allowance,
                right_absolute_allowance=fmpy_allowance,
                left_relative_allowance=0.0,
                right_relative_allowance=0.0,
                comparison_absolute_tolerance=config.get_absolute_tolerance(),
                comparison_relative_tolerance=config.get_relative_tolerance(),
                expected_time_seconds=expected_time_seconds,
            )
        )
        cs_veragrid_omsimulator_metrics: RmsFmiComparisonMetrics = (
            _compare_aligned_trajectories(
                left_time_seconds=cs_execution.get_time_seconds(),
                left_active_power=cs_execution.get_active_power(),
                left_reactive_power=cs_execution.get_reactive_power(),
                right_time_seconds=cs_omsimulator_trace.get_time_seconds(),
                right_active_power=cs_omsimulator_trace.get_active_power(),
                right_reactive_power=cs_omsimulator_trace.get_reactive_power(),
                left_absolute_allowance=cs_veragrid_allowance,
                right_absolute_allowance=omsimulator_allowance,
                left_relative_allowance=0.0,
                right_relative_allowance=config.get_omsimulator_relative_tolerance(),
                comparison_absolute_tolerance=config.get_absolute_tolerance(),
                comparison_relative_tolerance=config.get_relative_tolerance(),
                expected_time_seconds=expected_time_seconds,
            )
        )
        cs_fmpy_omsimulator_metrics: RmsFmiComparisonMetrics = (
            _compare_aligned_trajectories(
                left_time_seconds=cs_fmpy_time,
                left_active_power=cs_fmpy_active_power,
                left_reactive_power=cs_fmpy_reactive_power,
                right_time_seconds=cs_omsimulator_trace.get_time_seconds(),
                right_active_power=cs_omsimulator_trace.get_active_power(),
                right_reactive_power=cs_omsimulator_trace.get_reactive_power(),
                left_absolute_allowance=fmpy_allowance,
                right_absolute_allowance=omsimulator_allowance,
                left_relative_allowance=0.0,
                right_relative_allowance=config.get_omsimulator_relative_tolerance(),
                comparison_absolute_tolerance=config.get_absolute_tolerance(),
                comparison_relative_tolerance=config.get_relative_tolerance(),
                expected_time_seconds=expected_time_seconds,
            )
        )
        me_veragrid_fmpy_metrics: RmsFmiComparisonMetrics = (
            _compare_aligned_trajectories(
                left_time_seconds=me_execution.get_time_seconds(),
                left_active_power=me_execution.get_active_power(),
                left_reactive_power=me_execution.get_reactive_power(),
                right_time_seconds=me_fmpy_time,
                right_active_power=me_fmpy_active_power,
                right_reactive_power=me_fmpy_reactive_power,
                left_absolute_allowance=me_veragrid_allowance,
                right_absolute_allowance=fmpy_allowance,
                left_relative_allowance=0.0,
                right_relative_allowance=0.0,
                comparison_absolute_tolerance=config.get_absolute_tolerance(),
                comparison_relative_tolerance=config.get_relative_tolerance(),
                expected_time_seconds=expected_time_seconds,
            )
        )
        me_veragrid_omsimulator_metrics: RmsFmiComparisonMetrics = (
            _compare_aligned_trajectories(
                left_time_seconds=me_execution.get_time_seconds(),
                left_active_power=me_execution.get_active_power(),
                left_reactive_power=me_execution.get_reactive_power(),
                right_time_seconds=me_omsimulator_trace.get_time_seconds(),
                right_active_power=me_omsimulator_trace.get_active_power(),
                right_reactive_power=me_omsimulator_trace.get_reactive_power(),
                left_absolute_allowance=me_veragrid_allowance,
                right_absolute_allowance=omsimulator_allowance,
                left_relative_allowance=0.0,
                right_relative_allowance=config.get_omsimulator_relative_tolerance(),
                comparison_absolute_tolerance=config.get_absolute_tolerance(),
                comparison_relative_tolerance=config.get_relative_tolerance(),
                expected_time_seconds=expected_time_seconds,
            )
        )
        me_fmpy_omsimulator_metrics: RmsFmiComparisonMetrics = (
            _compare_aligned_trajectories(
                left_time_seconds=me_fmpy_time,
                left_active_power=me_fmpy_active_power,
                left_reactive_power=me_fmpy_reactive_power,
                right_time_seconds=me_omsimulator_trace.get_time_seconds(),
                right_active_power=me_omsimulator_trace.get_active_power(),
                right_reactive_power=me_omsimulator_trace.get_reactive_power(),
                left_absolute_allowance=fmpy_allowance,
                right_absolute_allowance=omsimulator_allowance,
                left_relative_allowance=0.0,
                right_relative_allowance=config.get_omsimulator_relative_tolerance(),
                comparison_absolute_tolerance=config.get_absolute_tolerance(),
                comparison_relative_tolerance=config.get_relative_tolerance(),
                expected_time_seconds=expected_time_seconds,
            )
        )

        cs_trace_path: Path = _write_trace_csv(
            staging_dir / "co_simulation_trace.csv",
            cs_execution,
            cs_fmpy_time,
            cs_fmpy_active_power,
            cs_fmpy_reactive_power,
            cs_omsimulator_trace,
            cs_veragrid_fmpy_metrics,
            cs_veragrid_omsimulator_metrics,
            cs_fmpy_omsimulator_metrics,
            scenario,
        )
        me_trace_path: Path = _write_trace_csv(
            staging_dir / "model_exchange_trace.csv",
            me_execution,
            me_fmpy_time,
            me_fmpy_active_power,
            me_fmpy_reactive_power,
            me_omsimulator_trace,
            me_veragrid_fmpy_metrics,
            me_veragrid_omsimulator_metrics,
            me_fmpy_omsimulator_metrics,
            scenario,
        )
        # Reopen the durable CSV files before any rendering so the published
        # plots cannot silently diverge from the retained numerical evidence.
        cs_retained_trace: RmsFmiRetainedTrace = _read_retained_comparison_csv(
            cs_trace_path
        )
        me_retained_trace: RmsFmiRetainedTrace = _read_retained_comparison_csv(
            me_trace_path
        )
        cs_fmpy_time_alignment: float = float(np.max(np.abs(
            cs_fmpy_time - cs_retained_trace.get_time_seconds()
        )))
        me_fmpy_time_alignment: float = float(np.max(np.abs(
            me_fmpy_time - me_retained_trace.get_time_seconds()
        )))
        cs_mode_evidence: RmsFmiModeEvidence = RmsFmiModeEvidence(
            execution=cs_execution,
            retained_trace=cs_retained_trace,
            fmpy_raw_evidence=cs_fmpy_raw_path,
            omsimulator_trace=cs_omsimulator_trace,
            process_arguments=cs_process_arguments,
            veragrid_fmpy_metrics=cs_veragrid_fmpy_metrics,
            veragrid_omsimulator_metrics=cs_veragrid_omsimulator_metrics,
            fmpy_omsimulator_metrics=cs_fmpy_omsimulator_metrics,
            fmu_sha256=cs_fmu_sha256,
            fmpy_time_alignment_max_error_seconds=cs_fmpy_time_alignment,
        )
        me_mode_evidence: RmsFmiModeEvidence = RmsFmiModeEvidence(
            execution=me_execution,
            retained_trace=me_retained_trace,
            fmpy_raw_evidence=me_fmpy_raw_path,
            omsimulator_trace=me_omsimulator_trace,
            process_arguments=me_process_arguments,
            veragrid_fmpy_metrics=me_veragrid_fmpy_metrics,
            veragrid_omsimulator_metrics=me_veragrid_omsimulator_metrics,
            fmpy_omsimulator_metrics=me_fmpy_omsimulator_metrics,
            fmu_sha256=me_fmu_sha256,
            fmpy_time_alignment_max_error_seconds=me_fmpy_time_alignment,
        )
        _render_trajectory_figure(
            figures_dir / "co_simulation_trajectories",
            FmuInterfaceMode.CO_SIMULATION,
            cs_retained_trace,
            cs_execution.get_event_time_seconds(),
        )
        _render_error_figure(
            figures_dir / "co_simulation_absolute_error",
            FmuInterfaceMode.CO_SIMULATION,
            cs_retained_trace,
            cs_execution.get_event_time_seconds(),
        )
        _render_trajectory_figure(
            figures_dir / "model_exchange_trajectories",
            FmuInterfaceMode.MODEL_EXCHANGE,
            me_retained_trace,
            me_execution.get_event_time_seconds(),
        )
        _render_error_figure(
            figures_dir / "model_exchange_absolute_error",
            FmuInterfaceMode.MODEL_EXCHANGE,
            me_retained_trace,
            me_execution.get_event_time_seconds(),
        )
        mode_evidence: tuple[RmsFmiModeEvidence, ...] = (
            cs_mode_evidence,
            me_mode_evidence,
        )
        _write_staged_manifest(
            staging_dir=staging_dir,
            config=config,
            mode_evidence=mode_evidence,
            scenario=scenario,
        )
        published_dir: Path = _publish_staged_package(staging_dir, final_dir)
        published = True
        return published_dir
    finally:
        # Cleanup is restricted to the unique staging directory created above.
        # A failed run never writes or removes the requested final destination.
        if not published and staging_dir.exists():
            shutil.rmtree(staging_dir)
        else:
            pass
