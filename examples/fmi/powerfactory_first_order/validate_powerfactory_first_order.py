"""Validate retained PowerFactory traces without importing the licensed API."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import cast

from fmpy import read_model_description, simulate_fmu
from fmpy.fmi2 import FMU2Slave
from fmpy.fmi3 import FMU3Slave
from fmpy.model_description import ModelDescription, ModelVariable
from fmpy.simulation import Recorder
import numpy as np

from examples.fmi.simulink_first_order.validate_first_order_matrix import (
    backward_euler_oracle,
    continuous_oracle,
)


class FmpyCsPostEventRecorder:
    """Append authenticated post-input CS samples without advancing time."""

    __slots__ = (
        "_event_index",
        "_event_observations",
        "_input_value_reference",
        "_state_value_reference",
    )

    def __init__(self, model_description: ModelDescription) -> None:
        """Resolve the exact scalar input and state value references.

        :param model_description: Parsed description of the selected CS FMU.
        :return: None.
        """

        input_variable: ModelVariable | None = None
        state_variable: ModelVariable | None = None
        variable: ModelVariable
        for variable in model_description.modelVariables:
            if variable.name == "u" and variable.causality == "input":
                if input_variable is None:
                    input_variable = variable
                else:
                    raise ValueError("FMPy CS model contains multiple input u variables")
            elif variable.name == "x" and variable.causality == "output":
                if state_variable is None:
                    state_variable = variable
                else:
                    raise ValueError("FMPy CS model contains multiple state x outputs")
            else:
                pass
        expected_variable_type: str = "Real" if model_description.fmiVersion == "2.0" else "Float64"
        if (
            model_description.fmiVersion in ("2.0", "3.0")
            and input_variable is not None
            and state_variable is not None
            and input_variable.type == expected_variable_type
            and state_variable.type == expected_variable_type
            and input_variable.shape in (None, tuple())
            and state_variable.shape in (None, tuple())
        ):
            self._input_value_reference: int = int(input_variable.valueReference)
            self._state_value_reference: int = int(state_variable.valueReference)
        else:
            raise ValueError("FMPy CS requires scalar FMI2 Real or FMI3 Float64 u/x variables")
        self._event_index: int = 0
        self._event_observations: np.ndarray = np.empty((3, 5), dtype=np.float64)

    def __call__(self, time: float, recorder: Recorder) -> bool:
        """Set and read the next declared event input at the same FMU time.

        :param time: Current completed CS communication time.
        :param recorder: Active public FMPy recorder and FMU instance.
        :return: True so FMPy continues the simulation.
        """

        event_times: tuple[float, ...] = (0.2, 0.5, 0.8)
        old_inputs: tuple[float, ...] = (0.0, 1.0, -0.5)
        new_inputs: tuple[float, ...] = (1.0, -0.5, 0.25)
        if self._event_index > 0 and time <= event_times[self._event_index - 1] + 5e-13:
            raise ValueError("FMPy CS callback repeated or reordered an event")
        else:
            pass
        if self._event_index < 3:
            expected_time: float = event_times[self._event_index]
            if abs(time - expected_time) <= 5e-13:
                value_references: list[int] = list((
                    self._input_value_reference,
                    self._state_value_reference,
                ))
                if isinstance(recorder.fmu, FMU2Slave):
                    before_values: list[float] = recorder.fmu.getReal(vr=value_references)
                elif isinstance(recorder.fmu, FMU3Slave):
                    before_values = recorder.fmu.getFloat64(vr=value_references, nValues=2)
                else:
                    raise TypeError("FMPy CS post-event recorder received an unsupported FMU")
                # Fail before mutating the input if the existing event side
                # does not match the declared schedule or finite state.
                if len(before_values) == 2 and float(before_values[0]) == old_inputs[self._event_index] and math.isfinite(float(before_values[1])):
                    pass
                else:
                    raise ValueError("FMPy CS pre-event input or state is invalid")
                if isinstance(recorder.fmu, FMU2Slave):
                    recorder.fmu.setReal(
                        vr=list((self._input_value_reference,)),
                        value=list((new_inputs[self._event_index],)),
                    )
                    after_values: list[float] = recorder.fmu.getReal(vr=value_references)
                elif isinstance(recorder.fmu, FMU3Slave):
                    recorder.fmu.setFloat64(
                        vr=list((self._input_value_reference,)),
                        values=list((new_inputs[self._event_index],)),
                    )
                    after_values = recorder.fmu.getFloat64(vr=value_references, nValues=2)
                else:
                    raise TypeError("FMPy CS post-event recorder received an unsupported FMU")
                if (
                    len(before_values) == 2
                    and len(after_values) == 2
                    and float(before_values[0]) == old_inputs[self._event_index]
                    and float(after_values[0]) == new_inputs[self._event_index]
                    and abs(float(after_values[1]) - float(before_values[1])) <= 5e-12
                ):
                    pass
                else:
                    raise ValueError("FMPy CS event input or continuous state is invalid")
                self._event_observations[self._event_index, :] = np.array(
                    (time, before_values[0], after_values[0], before_values[1], after_values[1]),
                    dtype=np.float64,
                )
                recorder.sample(time, force=True)
                self._event_index += 1
            elif time < expected_time:
                pass
            else:
                raise ValueError("FMPy CS callback missed or reordered a declared event")
        else:
            pass
        return True

    def get_event_observations(self) -> np.ndarray:
        """Return the complete immutable-by-copy event evidence.

        :return: Three rows of time, old/new input, and before/after state.
        """

        if self._event_index == 3:
            return self._event_observations.copy()
        else:
            raise RuntimeError("FMPy CS event observations are incomplete")


def load_trace_rows(trace_path: Path) -> np.ndarray:
    """Load a retained time/u/x CSV as a fixed-width numerical array.

    :param trace_path: Existing UTF-8 trace with time, u, and x columns.
    :return: Finite two-dimensional array with those three ordered columns.
    """

    trace: np.ndarray = np.genfromtxt(
        trace_path.resolve(strict=True),
        delimiter=",",
        names=True,
        dtype=np.float64,
        encoding="utf-8",
    )
    names: tuple[str, ...] | None = trace.dtype.names
    if names is not None and all(name in names for name in ("time", "u", "x")):
        rows: np.ndarray = np.column_stack((trace["time"], trace["u"], trace["x"]))
    else:
        raise ValueError("Trace lacks its time/u/x columns")
    if rows.ndim == 2 and rows.shape[1] == 3 and np.all(np.isfinite(rows)):
        return rows
    else:
        raise ValueError("Trace rows must be finite time/u/x values")


def canonicalize_trace_rows(
    rows: np.ndarray,
    powerfactory_rows: bool = True,
) -> np.ndarray:
    """Select exact right-continuous grid rows without interpolation.

    :param rows: Raw finite time/u/x rows in retained execution order.
    :param powerfactory_rows: Require the vendor one-or-old/new/new event rule.
    :return: Exactly 1201 canonical time/u/x rows on the 1 ms lattice.
    """

    if rows.ndim == 2 and rows.shape[1] == 3 and np.all(np.isfinite(rows)):
        pass
    else:
        raise ValueError("Raw trace shape or finiteness is invalid")
    canonical: np.ndarray = np.empty((1201, 3), dtype=np.float64)
    raw_index: int = 0
    grid_index: int
    event_indices: tuple[int, ...] = (200, 500, 800)
    old_inputs: tuple[float, ...] = (0.0, 1.0, -0.5)
    new_inputs: tuple[float, ...] = (1.0, -0.5, 0.25)
    for grid_index in range(1201):
        time_value: float = grid_index / 1000.0
        group_start: int = raw_index
        while raw_index < rows.shape[0] and abs(float(rows[raw_index, 0]) - time_value) <= 5e-13:
            raw_index += 1
        group_count: int = raw_index - group_start
        if group_count == 0:
            raise ValueError("Trace has a missing, reordered, or off-grid row")
        else:
            pass
        if grid_index in event_indices:
            event_index: int = event_indices.index(grid_index)
            old_input: float = old_inputs[event_index]
            new_input: float = new_inputs[event_index]
            if powerfactory_rows:
                if group_count == 1:
                    pass
                elif group_count == 3:
                    if np.array_equal(rows[group_start:raw_index, 1], np.array((old_input, new_input, new_input))):
                        pass
                    else:
                        raise ValueError("PowerFactory event rows are not old/new/new")
                    if float(np.ptp(rows[group_start:raw_index, 2])) <= 5e-12:
                        pass
                    else:
                        raise ValueError("PowerFactory event state is discontinuous")
                else:
                    raise ValueError("PowerFactory event cardinality is not one or three")
            else:
                event_inputs: np.ndarray = rows[group_start:raw_index, 1]
                event_states: np.ndarray = rows[group_start:raw_index, 2]
                if group_count == 1 and float(event_inputs[0]) == new_input:
                    pass
                elif group_count == 2 and np.array_equal(
                    event_inputs,
                    np.array((old_input, new_input), dtype=np.float64),
                ) and float(np.ptp(event_states)) <= 5e-12:
                    pass
                elif group_count == 3 and np.array_equal(
                    event_inputs,
                    np.array((old_input, new_input, new_input), dtype=np.float64),
                ) and float(np.ptp(event_states)) <= 5e-12:
                    pass
                else:
                    raise ValueError("FMPy event rows or state continuity are invalid")
            if float(rows[raw_index - 1, 1]) == new_input:
                pass
            else:
                raise ValueError("Canonical event input is not right-continuous")
        else:
            if group_count == 1:
                pass
            else:
                raise ValueError("Non-event grid point contains duplicate rows")
        canonical[grid_index, :] = rows[raw_index - 1, :]
        canonical[grid_index, 0] = time_value
    if raw_index == rows.shape[0]:
        pass
    else:
        raise ValueError("Trace contains extra or off-grid trailing rows")
    expected_input: np.ndarray = np.where(
        np.arange(1201) >= 800,
        0.25,
        np.where(np.arange(1201) >= 500, -0.5, np.where(np.arange(1201) >= 200, 1.0, 0.0)),
    )
    if np.array_equal(canonical[:, 1], expected_input):
        return canonical
    else:
        raise ValueError("Trace input schedule or event adjacency is invalid")


def max_abs_delta(first: np.ndarray, second: np.ndarray) -> float:
    """Measure every retained sample using an absolute max norm.

    :param first: First finite canonical series.
    :param second: Second finite canonical series with identical shape.
    :return: Nonnegative maximum absolute difference, with no relative term.
    """

    if first.shape == second.shape and first.size > 0 and np.all(np.isfinite(first)) and np.all(np.isfinite(second)):
        return float(np.max(np.abs(first - second)))
    else:
        raise ValueError("Compared series have invalid shape or non-finite values")


def validate_me_refinement(
    traces: tuple[np.ndarray, np.ndarray, np.ndarray],
    analytic_x: np.ndarray,
    cell_id: str,
) -> dict[str, object]:
    """Apply the sealed all-sample ME max-norm convergence rule.

    :param traces: Canonical state series at 0.125, 0.0625, and 0.03125 ms
        integration.
    :param analytic_x: Exact continuous oracle at the common output lattice.
    :param cell_id: Stable ME cell identifier.
    :return: Fixed-step errors, adjacent orders, floor branch, and verdict.
    """

    errors: tuple[float, float, float] = (
        max_abs_delta(traces[0], analytic_x),
        max_abs_delta(traces[1], analytic_x),
        max_abs_delta(traces[2], analytic_x),
    )
    floor_applied: bool = bool(all(error <= 1e-14 for error in errors))
    if floor_applied:
        orders: tuple[float, float] = (0.0, 0.0)
        converged: bool = True
    else:
        if errors[0] > errors[1] > errors[2] > 1e-14:
            orders = (math.log2(errors[0] / errors[1]), math.log2(errors[1] / errors[2]))
            converged = bool(orders[0] >= 1.5 and orders[1] >= 1.5)
        else:
            orders = (0.0, 0.0)
            converged = False
    within_bound: bool = bool(all(error <= 5e-5 for error in errors))
    return {
        "cell_id": cell_id,
        "steps_s": (0.000125, 0.0000625, 0.00003125),
        "max_errors": errors,
        "orders": orders,
        "floor_rule_applied": floor_applied,
        "status": "PASS" if converged and within_bound else "FAIL",
    }


def validate_validated_run_record(record: dict[str, object]) -> bool:
    """Reject unqualified or path-bearing tracked commercial lineage.

    :param record: Candidate declarative validated-run record.
    :return: True only for a sanitized fixed top-level PASS schema.
    """

    expected_keys: set[str] = set((
        "schema_version", "record_kind", "campaign", "source_commit",
        "git_tree_sha1", "fixture", "commercial_runtime",
        "compatibility", "numerical_results", "evidence_sha256",
        "repository_unchanged", "git_action", "status",
    ))
    valid: bool = bool(
        set(record) == expected_keys
        and record.get("schema_version", None) == "1.0"
        and record.get("record_kind", None) == "powerfactory_first_order_commercial_replay"
        and record.get("campaign", None) == "veragrid-powerfactory-first-order-fmi2-fmi3-revision-1"
        and record.get("repository_unchanged", None) is True
        and record.get("git_action", None) == "NONE"
        and record.get("status", None) == "PASS"
    )
    short_hash_pattern: re.Pattern[str] = re.compile(r"[0-9a-f]{40}")
    if short_hash_pattern.fullmatch(str(record.get("source_commit", ""))) is not None and short_hash_pattern.fullmatch(str(record.get("git_tree_sha1", ""))) is not None:
        pass
    else:
        valid = False
    fixture_value: object = record.get("fixture", None)
    if isinstance(fixture_value, dict):
        fixture: dict[str, object] = cast(dict[str, object], fixture_value)
    else:
        fixture = dict()
        valid = False
    fixture_keys: set[str] = set(("classification", "equation", "tau_s", "initial_state", "events", "step_s", "stop_s", "sample_count"))
    events_value: object = fixture.get("events", None)
    if isinstance(events_value, list):
        events: list[object] = events_value
    else:
        events = list()
    expected_events: tuple[tuple[float, float], ...] = ((0.2, 1.0), (0.5, -0.5), (0.8, 0.25))
    fixture_valid: bool = bool(
        set(fixture) == fixture_keys
        and fixture.get("classification", None) == "normalized first-order verification fixture; not a device-specific physical model"
        and fixture.get("equation", None) == "tau*dx/dt=u-x"
        and fixture.get("tau_s", None) == 0.1
        and fixture.get("initial_state", None) == 0.0
        and fixture.get("step_s", None) == 0.001
        and fixture.get("stop_s", None) == 1.2
        and type(fixture.get("sample_count", None)) is int
        and fixture.get("sample_count", None) == 1201
        and len(events) == 3
    )
    event_index: int
    for event_index in range(len(events)):
        event_value: object = events[event_index]
        if isinstance(event_value, dict):
            event: dict[str, object] = cast(dict[str, object], event_value)
            event_valid: bool = bool(set(event) == set(("time_s", "u")) and event.get("time_s", None) == expected_events[event_index][0] and event.get("u", None) == expected_events[event_index][1])
        else:
            event_valid = False
        fixture_valid = bool(fixture_valid and event_valid)
    valid = bool(valid and fixture_valid)
    runtime_value: object = record.get("commercial_runtime", None)
    if isinstance(runtime_value, dict):
        runtime: dict[str, object] = cast(dict[str, object], runtime_value)
    else:
        runtime = dict()
    expected_cells: list[str] = list(("fmi20_cs", "fmi20_me", "fmi30_cs_pf_compat", "fmi30_me_pf_compat"))
    runtime_valid: bool = bool(
        set(runtime) == set(("name", "version", "licensed", "binding_sha256", "platform", "cells"))
        and runtime.get("name", None) == "DIgSILENT PowerFactory"
        and runtime.get("version", None) == "2025 SP4"
        and runtime.get("licensed", None) is True
        and runtime.get("platform", None) == "Windows AMD64"
        and runtime.get("cells", None) == expected_cells
        and hash_pattern.fullmatch(str(runtime.get("binding_sha256", ""))) is not None
    )
    valid = bool(valid and runtime_valid)
    compatibility_value: object = record.get("compatibility", None)
    if isinstance(compatibility_value, dict):
        compatibility: dict[str, object] = cast(dict[str, object], compatibility_value)
    else:
        compatibility = dict()
    derivatives_value: object = compatibility.get("derivatives", None)
    if isinstance(derivatives_value, list):
        derivatives: list[object] = derivatives_value
    else:
        derivatives = list()
    compatibility_valid: bool = bool(
        set(compatibility) == set(("profile", "opt_in", "standard_fmi3_preserved", "standard_preflight_cominc_codes", "derivatives"))
        and compatibility.get("profile", None) == "powerfactory_fmi3_empty_configuration_mode_v1"
        and compatibility.get("opt_in", None) is True
        and compatibility.get("standard_fmi3_preserved", None) is True
        and compatibility.get("standard_preflight_cominc_codes", None) == list((2, 2))
        and len(derivatives) == 2
    )
    expected_derivative_ids: tuple[str, ...] = ("fmi30_cs_pf_compat", "fmi30_me_pf_compat")
    derivative_index: int
    for derivative_index in range(len(derivatives)):
        derivative_value: object = derivatives[derivative_index]
        if isinstance(derivative_value, dict):
            derivative: dict[str, object] = cast(dict[str, object], derivative_value)
            derivative_keys: set[str] = set(("cell_id", "standard_fmu_sha256", "source_closure_sha256", "patch_sha256", "derivative_fmu_sha256"))
            derivative_valid: bool = bool(set(derivative) == derivative_keys and derivative.get("cell_id", None) == expected_derivative_ids[derivative_index])
            hash_key: str
            for hash_key in ("standard_fmu_sha256", "source_closure_sha256", "patch_sha256", "derivative_fmu_sha256"):
                derivative_valid = bool(derivative_valid and hash_pattern.fullmatch(str(derivative.get(hash_key, ""))) is not None)
            derivative_valid = bool(derivative_valid and derivative.get("standard_fmu_sha256", None) != derivative.get("derivative_fmu_sha256", None))
        else:
            derivative_valid = False
        compatibility_valid = bool(compatibility_valid and derivative_valid)
    valid = bool(valid and compatibility_valid)
    numerical_value: object = record.get("numerical_results", None)
    if isinstance(numerical_value, dict):
        numerical: dict[str, object] = cast(dict[str, object], numerical_value)
    else:
        numerical = dict()
    primary_value: object = numerical.get("primary_cells", None)
    refinement_value: object = numerical.get("me_refinements", None)
    primary_cells: list[object] = primary_value if isinstance(primary_value, list) else list()
    refinements: list[object] = refinement_value if isinstance(refinement_value, list) else list()
    numerical_valid: bool = bool(
        set(numerical) == set(("primary_cells", "me_refinements", "event_canonicalization_status", "all_finite_and_grid_status", "status"))
        and len(primary_cells) == 4
        and len(refinements) == 2
        and numerical.get("event_canonicalization_status", None) == "PASS"
        and numerical.get("all_finite_and_grid_status", None) == "PASS"
        and numerical.get("status", None) == "PASS"
    )
    primary_index: int
    for primary_index in range(len(primary_cells)):
        primary_value = primary_cells[primary_index]
        if isinstance(primary_value, dict):
            primary: dict[str, object] = cast(dict[str, object], primary_value)
            primary_keys: set[str] = set(("cell_id", "sample_count", "oracle", "oracle_atol", "oracle_max_abs_error", "fmpy_atol", "fmpy_max_abs_delta", "simulink_atol", "simulink_max_abs_delta", "status"))
            primary_valid: bool = bool(
                set(primary) == primary_keys
                and primary.get("cell_id", None) == expected_cells[primary_index]
                and primary.get("sample_count", None) == 1201
                and primary.get("oracle", None) == ("backward_euler" if primary_index in (0, 2) else "analytic")
                and primary.get("status", None) == "PASS"
            )
            bound_key: str
            value_key: str
            for bound_key, value_key in (("oracle_atol", "oracle_max_abs_error"), ("fmpy_atol", "fmpy_max_abs_delta"), ("simulink_atol", "simulink_max_abs_delta")):
                bound: float = float(primary.get(bound_key, math.nan))
                observed: float = float(primary.get(value_key, math.nan))
                primary_valid = bool(primary_valid and math.isfinite(bound) and math.isfinite(observed) and 0.0 <= observed <= bound)
        else:
            primary_valid = False
        numerical_valid = bool(numerical_valid and primary_valid)
    expected_refinement_ids: tuple[str, ...] = ("fmi20_me", "fmi30_me_pf_compat")
    refinement_index: int
    for refinement_index in range(len(refinements)):
        refinement_value = refinements[refinement_index]
        if isinstance(refinement_value, dict):
            refinement: dict[str, object] = cast(dict[str, object], refinement_value)
            error_values: list[object] = cast(list[object], refinement.get("max_errors", list())) if isinstance(refinement.get("max_errors", None), list) else list()
            order_values: list[object] = cast(list[object], refinement.get("orders", list())) if isinstance(refinement.get("orders", None), list) else list()
            refinement_valid: bool = bool(
                set(refinement) == set(("cell_id", "steps_s", "max_errors", "orders", "floor_rule_applied", "status"))
                and refinement.get("cell_id", None) == expected_refinement_ids[refinement_index]
                and refinement.get("steps_s", None)
                == list((0.000125, 0.0000625, 0.00003125))
                and len(error_values) == 3
                and len(order_values) == 2
                and type(refinement.get("floor_rule_applied", None)) is bool
                and refinement.get("status", None) == "PASS"
            )
            if len(error_values) == 3 and len(order_values) == 2:
                refinement_errors: tuple[float, float, float] = (float(error_values[0]), float(error_values[1]), float(error_values[2]))
                refinement_orders: tuple[float, float] = (float(order_values[0]), float(order_values[1]))
                finite_values: bool = bool(all(math.isfinite(value) for value in refinement_errors + refinement_orders))
                within_me_bound: bool = bool(all(0.0 <= value <= 5e-5 for value in refinement_errors))
                if refinement.get("floor_rule_applied", None) is True:
                    convergence_valid: bool = bool(all(value <= 1e-14 for value in refinement_errors))
                else:
                    convergence_valid = bool(refinement_errors[0] > refinement_errors[1] > refinement_errors[2] > 1e-14 and refinement_orders[0] >= 1.5 and refinement_orders[1] >= 1.5)
                refinement_valid = bool(refinement_valid and finite_values and within_me_bound and convergence_valid)
            else:
                refinement_valid = False
        else:
            refinement_valid = False
        numerical_valid = bool(numerical_valid and refinement_valid)
    valid = bool(valid and numerical_valid)
    evidence_value: object = record.get("evidence_sha256", None)
    if isinstance(evidence_value, dict):
        evidence: dict[str, object] = cast(dict[str, object], evidence_value)
    else:
        evidence = dict()
    evidence_keys: set[str] = set(("generator_manifest", "source_closure_manifest", "compatibility_build_receipt", "powerfactory_execution_receipt", "fmpy_receipt", "simulink_numerical_receipt", "numerical_comparison_receipt", "figure_manifest", "figure_qa_receipt", "cleanup_receipt", "repository_post_snapshot", "change_control_receipt"))
    evidence_valid: bool = bool(set(evidence) == evidence_keys)
    evidence_hash: object
    for evidence_hash in evidence.values():
        evidence_valid = bool(evidence_valid and hash_pattern.fullmatch(str(evidence_hash)) is not None)
    valid = bool(valid and evidence_valid)
    stack: list[object] = list((record,))
    while len(stack) > 0:
        item: object = stack.pop()
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, (list, tuple)):
            stack.extend(item)
        elif isinstance(item, str):
            lowered: str = item.casefold()
            path_leak: bool = bool(
                re.search(r"[a-z]:[\\/]", lowered) is not None
                or item.startswith(("/", "\\\\"))
                or "file://" in lowered
                or ".." in item.replace("\\", "/").split("/")
                or any(fragment in lowered for fragment in ("appdata", "program files", "temp/", "workdir", "password", "secret", "andre", "joan", ".pfd", ".dz"))
            )
            if path_leak:
                valid = False
            else:
                pass
        elif isinstance(item, float):
            if math.isfinite(item):
                pass
            else:
                valid = False
        else:
            if isinstance(item, (int, bool)):
                pass
            else:
                valid = False
    return valid


def write_validated_run(record: dict[str, object], output_path: Path) -> None:
    """Publish a qualified sanitized record to a new external destination.

    :param record: Fully qualified fixed-schema commercial PASS record.
    :param output_path: New external JSON path, never the tracked recipe path.
    :return: None.
    """

    if validate_validated_run_record(record):
        pass
    else:
        raise ValueError("Commercial validated-run record is not qualified")
    with output_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
    if json.loads(output_path.read_text(encoding="utf-8")) == record:
        pass
    else:
        raise RuntimeError("Validated-run record reopen mismatch")


def validate_powerfactory_first_order(
    execution_dir: Path,
    generator_manifest_path: Path,
    simulink_dir: Path,
) -> dict[str, object]:
    """Validate PowerFactory/FMPy/Simulink/oracle pointwise agreement.

    :param execution_dir: Retained PowerFactory execution directory.
    :param generator_manifest_path: Authenticated clean-source generator manifest.
    :param simulink_dir: Historical same-fixture Simulink execution directory.
    :return: Reopened numerical comparison receipt, including any failed bound.
    """

    execution_dir = execution_dir.resolve(strict=True)
    generator_manifest_path = generator_manifest_path.resolve(strict=True)
    simulink_dir = simulink_dir.resolve(strict=True)
    execution_receipt_path: Path = execution_dir / "execution-receipt.json"
    execution_receipt: dict[str, object] = json.loads(execution_receipt_path.read_text(encoding="utf-8"))
    observations: dict[str, object] = json.loads((execution_dir / "observations.json").read_text(encoding="utf-8"))
    if execution_receipt.get("status", None) == "EXECUTION_EVIDENCE_COMPLETE" and observations.get("cleanup", dict()).get("status", None) == "PASS":
        pass
    else:
        raise ValueError("PowerFactory execution or cleanup did not complete")
    generator_manifest: dict[str, object] = json.loads(generator_manifest_path.read_text(encoding="utf-8"))
    build_receipt: dict[str, object] = json.loads((execution_dir / "compatibility-build-receipt.json").read_text(encoding="utf-8"))
    simulink_receipt_path: Path = simulink_dir / "numerical-comparison-receipt.json"
    simulink_receipt_bytes: bytes = simulink_receipt_path.read_bytes()
    simulink_receipt: dict[str, object] = json.loads(simulink_receipt_bytes.decode("utf-8"))
    simulink_cells_value: object = simulink_receipt.get("cells", None)
    simulink_receipt_valid: bool = bool(
        simulink_receipt.get("status", None) == "PASS"
        and re.fullmatch(r"[0-9a-f]{40}", str(simulink_receipt.get("source_commit", ""))) is not None
        and isinstance(simulink_cells_value, list)
        and len(simulink_cells_value) == 6
        and all(
            isinstance(cell_value, dict)
            and cell_value.get("status", None) == "PASS"
            and re.fullmatch(r"[0-9a-f]{64}", str(cell_value.get("trace_sha256", ""))) is not None
            for cell_value in cast(list[object], simulink_cells_value)
        )
    )
    if simulink_receipt_valid:
        pass
    else:
        raise ValueError("Retained Simulink numerical receipt contract is invalid")
    comparison_dir: Path = execution_dir / "comparison"
    if comparison_dir.exists():
        raise FileExistsError("Refusing to overwrite numerical comparison evidence")
    else:
        comparison_dir.mkdir(parents=True, exist_ok=False)
    fmpy_dir: Path = execution_dir / "fmpy_traces"
    fmpy_dir.mkdir(parents=True, exist_ok=False)
    time_values: np.ndarray = np.arange(1201, dtype=np.float64) / 1000.0
    input_values: np.ndarray = np.where(time_values >= 0.8, 0.25, np.where(time_values >= 0.5, -0.5, np.where(time_values >= 0.2, 1.0, 0.0)))
    analytic_x: np.ndarray = continuous_oracle(time_values)
    backward_euler_x: np.ndarray = backward_euler_oracle(time_values, input_values)
    input_table: np.ndarray = np.empty(
        8,
        dtype=np.dtype(list((("time", np.float64), ("u", np.float64)))),
    )
    # Duplicate timestamps declare right-continuous jumps to FMPy without
    # asking NumPy to interpret the outer tuple as a single structured row.
    input_table["time"] = np.array((0.0, 0.2, 0.2, 0.5, 0.5, 0.8, 0.8, 1.2), dtype=np.float64)
    input_table["u"] = np.array((0.0, 0.0, 1.0, 1.0, -0.5, -0.5, 0.25, 0.25), dtype=np.float64)
    cell_ids: tuple[str, ...] = ("fmi20_cs", "fmi20_me", "fmi30_cs", "fmi30_me")
    primary_results: list[dict[str, object]] = list()
    refinement_results: list[dict[str, object]] = list()
    fmpy_results: list[dict[str, object]] = list()
    combined_columns: list[np.ndarray] = list((time_values, input_values, analytic_x, backward_euler_x))
    combined_names: list[str] = list(("time", "u", "continuous_oracle", "backward_euler_oracle"))
    all_passed: bool = True
    cell_id: str
    for cell_id in cell_ids:
        interface: str = "cs" if cell_id.endswith("cs") else "me"
        primary_step_tag: str = (
            "0p001000000" if interface == "cs" else "0p000125000"
        )
        pf_trace: np.ndarray = canonicalize_trace_rows(
            load_trace_rows(
                execution_dir
                / "raw_traces"
                / (cell_id + "_h_" + primary_step_tag + ".csv")
            )
        )
        if cell_id.startswith("fmi30"):
            fmu_path: Path = execution_dir / "compatibility_fmus" / ("VGFirstOrder81d8da9c2034_FMI30_" + interface.upper() + "_PowerFactory.fmu")
            build_items: list[dict[str, object]] = cast(list[dict[str, object]], build_receipt["builds"])
            expected_fmu_sha256: str = str(next(item["derived_fmu_sha256"] for item in build_items if item["cell_id"] == cell_id))
        else:
            generator_cells: list[dict[str, object]] = cast(list[dict[str, object]], generator_manifest["cells"])
            generator_cell: dict[str, object] = next(item for item in generator_cells if item["cell_id"] == cell_id)
            fmu_path = generator_manifest_path.parent / "fmus" / str(generator_cell["fmu_name"])
            expected_fmu_sha256 = str(generator_cell["fmu_sha256"])
        fmu_sha256: str = hashlib.sha256(fmu_path.read_bytes()).hexdigest()
        if fmu_sha256 == expected_fmu_sha256:
            pass
        else:
            raise ValueError("Selected PowerFactory FMU identity changed before FMPy")
        model_description: ModelDescription = read_model_description(str(fmu_path), validate=True)
        post_event_recorder: FmpyCsPostEventRecorder | None
        if interface == "cs":
            post_event_recorder = FmpyCsPostEventRecorder(model_description)
        else:
            post_event_recorder = None
        simulation_result: np.ndarray = simulate_fmu(
            filename=str(fmu_path),
            fmi_type="CoSimulation" if interface == "cs" else "ModelExchange",
            start_time=0.0,
            stop_time=1.2,
            step_size=0.001,
            output_interval=0.001,
            solver="CVode",
            relative_tolerance=1e-10,
            input=input_table,
            output=list(("u", "x")),
            record_events=True,
            model_description=model_description,
            step_finished=post_event_recorder,
        )
        raw_fmpy: np.ndarray = np.column_stack((simulation_result["time"], simulation_result["u"], simulation_result["x"]))
        fmpy_path: Path = fmpy_dir / (cell_id + ".csv")
        np.savetxt(fmpy_path, raw_fmpy, delimiter=",", header="time,u,x", comments="", fmt="%.17g")
        fmpy_trace: np.ndarray = canonicalize_trace_rows(raw_fmpy, powerfactory_rows=False)
        if hashlib.sha256(fmu_path.read_bytes()).hexdigest() == fmu_sha256:
            pass
        else:
            raise ValueError("Selected FMU changed during FMPy execution")
        simulink_path: Path = simulink_dir / "traces" / (cell_id + ".csv")
        simulink_cells: list[dict[str, object]] = cast(list[dict[str, object]], simulink_receipt["cells"])
        simulink_cell: dict[str, object] = next(item for item in simulink_cells if item["cell_id"] == cell_id)
        if hashlib.sha256(simulink_path.read_bytes()).hexdigest() == simulink_cell["trace_sha256"]:
            pass
        else:
            raise ValueError("Retained Simulink trace identity mismatch")
        simulink_trace: np.ndarray = canonicalize_trace_rows(load_trace_rows(simulink_path))
        oracle_x: np.ndarray = backward_euler_x if interface == "cs" else analytic_x
        oracle_atol: float = 2e-10 if interface == "cs" else 5e-5
        fmpy_atol: float = 2e-10 if interface == "cs" else 1e-4
        simulink_atol: float = 2.1e-10 if interface == "cs" else 5.1e-5
        oracle_error: float = max_abs_delta(pf_trace[:, 2], oracle_x)
        fmpy_delta: float = max_abs_delta(pf_trace[:, 2], fmpy_trace[:, 2])
        simulink_delta: float = max_abs_delta(pf_trace[:, 2], simulink_trace[:, 2])
        analytic_error: float = max_abs_delta(pf_trace[:, 2], analytic_x)
        passed: bool = bool(oracle_error <= oracle_atol and fmpy_delta <= fmpy_atol and simulink_delta <= simulink_atol and (interface == "me" or analytic_error <= 0.004))
        all_passed = bool(all_passed and passed)
        qualified_cell_id: str = cell_id + "_pf_compat" if cell_id.startswith("fmi30") else cell_id
        primary_results.append({
            "cell_id": qualified_cell_id,
            "sample_count": 1201,
            "oracle": "backward_euler" if interface == "cs" else "analytic",
            "oracle_atol": oracle_atol,
            "oracle_max_abs_error": oracle_error,
            "fmpy_atol": fmpy_atol,
            "fmpy_max_abs_delta": fmpy_delta,
            "simulink_atol": simulink_atol,
            "simulink_max_abs_delta": simulink_delta,
            "status": "PASS" if passed else "FAIL",
        })
        if post_event_recorder is not None:
            event_observations: list[list[float]] = post_event_recorder.get_event_observations().tolist()
            event_observation_status: str = "PASS"
        else:
            event_observations = list()
            event_observation_status = "NOT_APPLICABLE"
        fmpy_results.append({"cell_id": qualified_cell_id, "selected_fmu_sha256": fmu_sha256, "trace_sha256": hashlib.sha256(fmpy_path.read_bytes()).hexdigest(), "sample_count": 1201, "event_observations": event_observations, "event_observation_status": event_observation_status, "status": "PASS"})
        if interface == "me":
            half_trace: np.ndarray = canonicalize_trace_rows(
                load_trace_rows(
                    execution_dir
                    / "raw_traces"
                    / (cell_id + "_h_0p000062500.csv")
                )
            )
            quarter_trace: np.ndarray = canonicalize_trace_rows(
                load_trace_rows(
                    execution_dir
                    / "raw_traces"
                    / (cell_id + "_h_0p000031250.csv")
                )
            )
            refinement: dict[str, object] = validate_me_refinement((pf_trace[:, 2], half_trace[:, 2], quarter_trace[:, 2]), analytic_x, qualified_cell_id)
            refinement_results.append(refinement)
            all_passed = bool(all_passed and refinement["status"] == "PASS")
        else:
            pass
        combined_columns.extend((pf_trace[:, 2], fmpy_trace[:, 2], simulink_trace[:, 2]))
        combined_names.extend(("pf_" + cell_id, "fmpy_" + cell_id, "simulink_" + cell_id))
    combined_path: Path = comparison_dir / "all-traces-and-oracles.csv"
    np.savetxt(combined_path, np.column_stack(combined_columns), delimiter=",", header=",".join(combined_names), comments="", fmt="%.17g")
    fmpy_receipt: dict[str, object] = {"schema_version": "1.0", "cells": fmpy_results, "status": "PASS", "completed_at_utc": datetime.now(timezone.utc).isoformat()}
    fmpy_receipt_path: Path = execution_dir / "fmpy-receipt.json"
    fmpy_receipt_path.write_text(json.dumps(fmpy_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt: dict[str, object] = {
        "schema_version": "1.0",
        "campaign": "veragrid-powerfactory-first-order-fmi2-fmi3-revision-1",
        "source_commit": generator_manifest["source_commit"],
        "git_tree_sha1": generator_manifest["git_tree_sha1"],
        "simulink_source_commit": simulink_receipt["source_commit"],
        "simulink_same_fixture_not_same_binary": True,
        "sample_count": 1201,
        "primary_cells": primary_results,
        "me_refinements": refinement_results,
        "event_canonicalization_status": "PASS",
        "all_finite_and_grid_status": "PASS",
        "comparison_name": "comparison/all-traces-and-oracles.csv",
        "comparison_sha256": hashlib.sha256(combined_path.read_bytes()).hexdigest(),
        "generator_manifest_sha256": hashlib.sha256(generator_manifest_path.read_bytes()).hexdigest(),
        "execution_receipt_sha256": hashlib.sha256(execution_receipt_path.read_bytes()).hexdigest(),
        "fmpy_receipt_sha256": hashlib.sha256(fmpy_receipt_path.read_bytes()).hexdigest(),
        "simulink_numerical_receipt_sha256": hashlib.sha256(simulink_receipt_bytes).hexdigest(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if all_passed else "FAIL",
    }
    receipt_path: Path = execution_dir / "numerical-comparison-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    reopened: dict[str, object] = json.loads(receipt_path.read_text(encoding="utf-8"))
    if reopened == json.loads(json.dumps(receipt)):
        return reopened
    else:
        raise RuntimeError("Numerical comparison receipt reopen mismatch")


def main() -> int:
    """Validate a retained licensed run with explicit external evidence paths.

    :return: Zero only when every fixed pointwise and convergence gate passes.
    """

    if sys.dont_write_bytecode:
        pass
    else:
        raise ValueError("Run this validator with python -B")
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution-dir", type=Path, required=True)
    parser.add_argument("--generator-manifest", type=Path, required=True)
    parser.add_argument("--simulink-dir", type=Path, required=True)
    arguments: argparse.Namespace = parser.parse_args()
    receipt: dict[str, object] = validate_powerfactory_first_order(arguments.execution_dir, arguments.generator_manifest, arguments.simulink_dir)
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
