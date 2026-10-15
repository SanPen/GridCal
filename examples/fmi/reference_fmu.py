# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Sealed Reference FMU corpus metadata for interoperability benchmarks."""
from __future__ import annotations

from enum import Enum
import hashlib
import json
import math
from pathlib import Path
import re
from typing import BinaryIO, cast

import numpy as np

from VeraGridEngine.enumerations import (
    FmiVersion,
    FmuInterfaceMode,
    FmuVariableType,
    FmuVariableType as FmiVariableType,
)


class ReferenceFmuEventMechanism(str, Enum):
    """Event mechanisms represented by the maintained reference corpus."""

    TIME_EVENT = "time_event"
    STATE_EVENT = "state_event"


class ReferenceFmuEventDetectionRule(str, Enum):
    """Rules used to identify reference events in retained trajectories."""

    VALUE_CHANGE_AT_TIME = "value_change_at_time"
    NEGATIVE_TO_NONNEGATIVE = "negative_to_nonnegative"


class ReferenceFmuTerminationKind(str, Enum):
    """Reasons that delimit the retained reference trajectory."""

    FMU_REQUEST = "fmu_request"
    CONFIGURED_STOP = "configured_stop"


class ReferenceFmuEventOracle:
    """Own one validated event oracle for one FMI interface.

    The semantic final value is kept separate from the last value that a tool
    can serialize. This distinction is required for terminating time events,
    where the FMU state changes before public output can expose the new value.
    """

    __slots__ = (
        "interface_mode",
        "mechanism",
        "detection_rule",
        "observed_variable_name",
        "observed_variable_type",
        "event_lower_bounds_seconds",
        "event_upper_bounds_seconds",
        "observable_transition_count",
        "initial_observed_value",
        "semantic_final_value",
        "expected_last_observed_value",
        "expected_transition_delta",
        "termination_kind",
        "expected_termination_time_seconds",
        "terminal_post_event_observable",
        "terminal_value_must_be_sustained",
    )

    interface_mode: FmuInterfaceMode
    mechanism: ReferenceFmuEventMechanism
    detection_rule: ReferenceFmuEventDetectionRule
    observed_variable_name: str
    observed_variable_type: FmuVariableType
    event_lower_bounds_seconds: np.ndarray
    event_upper_bounds_seconds: np.ndarray
    observable_transition_count: int
    initial_observed_value: int | float
    semantic_final_value: int | float
    expected_last_observed_value: int | float
    expected_transition_delta: int | float | None
    termination_kind: ReferenceFmuTerminationKind
    expected_termination_time_seconds: float
    terminal_post_event_observable: bool
    terminal_value_must_be_sustained: bool

    def __init__(
        self,
        interface_mode: FmuInterfaceMode,
        mechanism: ReferenceFmuEventMechanism,
        detection_rule: ReferenceFmuEventDetectionRule,
        observed_variable_name: str,
        observed_variable_type: FmuVariableType,
        event_lower_bounds_seconds: tuple[float, ...],
        event_upper_bounds_seconds: tuple[float, ...],
        observable_transition_count: int,
        initial_observed_value: int | float,
        semantic_final_value: int | float,
        expected_last_observed_value: int | float,
        expected_transition_delta: int | float | None,
        termination_kind: ReferenceFmuTerminationKind,
        expected_termination_time_seconds: float,
        terminal_post_event_observable: bool,
        terminal_value_must_be_sustained: bool,
    ) -> None:
        """Validate and retain one event oracle without mutable aliases.

        :param interface_mode: FMI interface governed by this oracle.
        :param mechanism: FMI event mechanism represented by the oracle.
        :param detection_rule: Rule used to identify each event.
        :param observed_variable_name: Variable inspected by the rule.
        :param observed_variable_type: FMI scalar type of the variable.
        :param event_lower_bounds_seconds: Lower event-time bounds.
        :param event_upper_bounds_seconds: Upper event-time bounds.
        :param observable_transition_count: Transitions visible in raw output.
        :param initial_observed_value: Value at the first retained sample.
        :param semantic_final_value: Value reached by complete FMU semantics.
        :param expected_last_observed_value: Last value visible in raw output.
        :param expected_transition_delta: Per-event value change, if defined.
        :param termination_kind: Cause ending the retained trajectory.
        :param expected_termination_time_seconds: Expected end time in seconds.
        :param terminal_post_event_observable: Whether output exposes the final event.
        :param terminal_value_must_be_sustained: Whether the value must persist.
        :return: None.
        """

        # Validate the type-level description before allocating numerical data.
        enum_values_are_valid: bool = bool(
            isinstance(interface_mode, FmuInterfaceMode)
            and isinstance(mechanism, ReferenceFmuEventMechanism)
            and isinstance(detection_rule, ReferenceFmuEventDetectionRule)
            and isinstance(observed_variable_type, FmuVariableType)
            and isinstance(termination_kind, ReferenceFmuTerminationKind)
        )
        if enum_values_are_valid:
            pass
        else:
            raise ValueError("Reference event enums must use their declared types")

        descriptive_values_are_valid: bool = bool(
            isinstance(observed_variable_name, str)
            and bool(observed_variable_name.strip())
            and isinstance(terminal_post_event_observable, bool)
            and isinstance(terminal_value_must_be_sustained, bool)
        )
        if descriptive_values_are_valid:
            pass
        else:
            raise ValueError("Reference event descriptive values are invalid")

        bounds_are_tuples: bool = bool(
            isinstance(event_lower_bounds_seconds, tuple)
            and isinstance(event_upper_bounds_seconds, tuple)
        )
        if bounds_are_tuples:
            pass
        else:
            raise ValueError("Reference event bounds must be tuples")

        event_count: int = len(event_lower_bounds_seconds)
        cardinality_is_valid: bool = bool(
            event_count == len(event_upper_bounds_seconds)
            and event_count >= 1
            and event_count <= 1024
        )
        if cardinality_is_valid:
            pass
        else:
            raise ValueError("Reference event-bound cardinality is invalid")

        observable_count_is_valid: bool = bool(
            isinstance(observable_transition_count, int)
            and not isinstance(observable_transition_count, bool)
            and 0 <= observable_transition_count <= event_count
        )
        if observable_count_is_valid:
            pass
        else:
            raise ValueError("Observable transition count is invalid")

        # Fill known-size arrays and reject bool before numerical conversion.
        lower_bounds: np.ndarray = np.empty(event_count, dtype=np.float64)
        upper_bounds: np.ndarray = np.empty(event_count, dtype=np.float64)
        previous_upper_bound: float | None = None
        for event_index in range(event_count):
            lower_value: object = event_lower_bounds_seconds[event_index]
            upper_value: object = event_upper_bounds_seconds[event_index]
            bound_types_are_valid: bool = bool(
                isinstance(lower_value, (int, float))
                and not isinstance(lower_value, bool)
                and isinstance(upper_value, (int, float))
                and not isinstance(upper_value, bool)
            )
            if bound_types_are_valid:
                validated_lower_value: float = float(lower_value)
                validated_upper_value: float = float(upper_value)
            else:
                raise ValueError("Reference event bounds must be real scalars")

            bounds_are_finite: bool = bool(
                math.isfinite(validated_lower_value)
                and math.isfinite(validated_upper_value)
            )
            if bounds_are_finite:
                pass
            else:
                raise ValueError("Reference event bounds must be finite")

            interval_is_valid: bool = bool(
                validated_lower_value >= 0.0
                and validated_lower_value <= validated_upper_value
            )
            if previous_upper_bound is None:
                interval_is_separate: bool = True
            else:
                interval_is_separate = bool(
                    previous_upper_bound < validated_lower_value
                )
            if interval_is_valid and interval_is_separate:
                lower_bounds[event_index] = validated_lower_value
                upper_bounds[event_index] = validated_upper_value
                previous_upper_bound = validated_upper_value
            else:
                raise ValueError("Reference event intervals are invalid")

        termination_time_type_is_valid: bool = bool(
            isinstance(expected_termination_time_seconds, (int, float))
            and not isinstance(expected_termination_time_seconds, bool)
        )
        if termination_time_type_is_valid:
            validated_termination_time_seconds: float = float(
                expected_termination_time_seconds
            )
        else:
            raise ValueError("Reference termination time must be a real scalar")
        if math.isfinite(validated_termination_time_seconds):
            pass
        else:
            raise ValueError("Reference termination time must be finite")

        # Preserve discrete scalar identity and normalize only floating types.
        variable_is_integer: bool = bool(
            observed_variable_type
            in (FmuVariableType.INTEGER, FmuVariableType.INT32)
        )
        variable_is_floating: bool = bool(
            observed_variable_type
            in (FmuVariableType.REAL, FmuVariableType.FLOAT64)
        )
        if variable_is_integer:
            integer_values_are_valid: bool = bool(
                isinstance(initial_observed_value, int)
                and not isinstance(initial_observed_value, bool)
                and isinstance(semantic_final_value, int)
                and not isinstance(semantic_final_value, bool)
                and isinstance(expected_last_observed_value, int)
                and not isinstance(expected_last_observed_value, bool)
                and isinstance(expected_transition_delta, int)
                and not isinstance(expected_transition_delta, bool)
            )
            if integer_values_are_valid:
                validated_initial_value: int | float = int(initial_observed_value)
                validated_semantic_final_value: int | float = int(
                    semantic_final_value
                )
                validated_last_observed_value: int | float = int(
                    expected_last_observed_value
                )
                validated_transition_delta: int | float | None = int(
                    cast(int, expected_transition_delta)
                )
            else:
                raise ValueError("Integer event values must remain Python integers")

            if observed_variable_type == FmuVariableType.INT32:
                int32_values: tuple[int, ...] = (
                    cast(int, validated_initial_value),
                    cast(int, validated_semantic_final_value),
                    cast(int, validated_last_observed_value),
                    cast(int, validated_transition_delta),
                )
                int32_range_is_valid: bool = all(
                    -2147483648 <= integer_value <= 2147483647
                    for integer_value in int32_values
                )
                if int32_range_is_valid:
                    pass
                else:
                    raise ValueError("Int32 event values are out of range")
            else:
                pass
        else:
            if variable_is_floating:
                floating_values_are_valid: bool = bool(
                    isinstance(initial_observed_value, (int, float))
                    and not isinstance(initial_observed_value, bool)
                    and isinstance(semantic_final_value, (int, float))
                    and not isinstance(semantic_final_value, bool)
                    and isinstance(expected_last_observed_value, (int, float))
                    and not isinstance(expected_last_observed_value, bool)
                    and (
                        expected_transition_delta is None
                        or (
                            isinstance(expected_transition_delta, (int, float))
                            and not isinstance(expected_transition_delta, bool)
                        )
                    )
                )
                if floating_values_are_valid:
                    validated_initial_value = float(initial_observed_value)
                    validated_semantic_final_value = float(semantic_final_value)
                    validated_last_observed_value = float(
                        expected_last_observed_value
                    )
                    if expected_transition_delta is None:
                        validated_transition_delta = None
                    else:
                        validated_transition_delta = float(expected_transition_delta)
                else:
                    raise ValueError("Floating event values must be real scalars")

                floating_values: tuple[float, ...] = (
                    float(validated_initial_value),
                    float(validated_semantic_final_value),
                    float(validated_last_observed_value),
                )
                floating_values_are_finite: bool = all(
                    math.isfinite(floating_value)
                    for floating_value in floating_values
                )
                if validated_transition_delta is None:
                    transition_is_finite: bool = True
                else:
                    transition_is_finite = math.isfinite(
                        float(validated_transition_delta)
                    )
                if floating_values_are_finite and transition_is_finite:
                    pass
                else:
                    raise ValueError("Floating event values must be finite")
            else:
                raise ValueError("Observed variable type is not supported")

        # Enforce the cross-field semantics of each supported event family.
        if detection_rule == ReferenceFmuEventDetectionRule.VALUE_CHANGE_AT_TIME:
            point_bounds_are_valid: bool = bool(
                np.array_equal(lower_bounds, upper_bounds)
            )
            mechanism_is_valid: bool = bool(
                mechanism == ReferenceFmuEventMechanism.TIME_EVENT
            )
            transition_is_defined: bool = bool(
                validated_transition_delta is not None
                and validated_transition_delta != 0
            )
            expected_semantic_final_value: int | float = (
                validated_initial_value
                + event_count * cast(int | float, validated_transition_delta)
            )
            expected_visible_value: int | float = (
                validated_initial_value
                + observable_transition_count
                * cast(int | float, validated_transition_delta)
            )
            transition_arithmetic_is_valid: bool = bool(
                validated_semantic_final_value
                == expected_semantic_final_value
                and type(validated_semantic_final_value)
                is type(expected_semantic_final_value)
                and validated_last_observed_value == expected_visible_value
                and type(validated_last_observed_value)
                is type(expected_visible_value)
            )
            observability_is_valid: bool = bool(
                terminal_post_event_observable
                is (observable_transition_count == event_count)
            )
            termination_is_valid: bool = bool(
                termination_kind == ReferenceFmuTerminationKind.FMU_REQUEST
                and not terminal_value_must_be_sustained
                and abs(
                    float(upper_bounds[-1])
                    - validated_termination_time_seconds
                )
                <= 1.0e-12
            )
            time_event_is_valid: bool = bool(
                point_bounds_are_valid
                and mechanism_is_valid
                and transition_is_defined
                and transition_arithmetic_is_valid
                and observability_is_valid
                and termination_is_valid
            )
            if time_event_is_valid:
                pass
            else:
                raise ValueError("Time-event oracle is internally inconsistent")
        else:
            if (
                detection_rule
                == ReferenceFmuEventDetectionRule.NEGATIVE_TO_NONNEGATIVE
            ):
                state_event_is_valid: bool = bool(
                    mechanism == ReferenceFmuEventMechanism.STATE_EVENT
                    and variable_is_floating
                    and validated_transition_delta is None
                    and observable_transition_count == event_count
                    and validated_semantic_final_value == 0.0
                    and validated_last_observed_value == 0.0
                    and termination_kind
                    == ReferenceFmuTerminationKind.CONFIGURED_STOP
                    and terminal_post_event_observable
                    and terminal_value_must_be_sustained
                    and float(upper_bounds[-1])
                    <= validated_termination_time_seconds
                )
                if state_event_is_valid:
                    pass
                else:
                    raise ValueError("State-event oracle is internally inconsistent")
            else:
                raise ValueError("Reference event detection rule is unsupported")

        # Bytes own the storage so callers cannot re-enable NumPy write access.
        lower_bounds_bytes: bytes = lower_bounds.tobytes()
        upper_bounds_bytes: bytes = upper_bounds.tobytes()
        immutable_lower_bounds: np.ndarray = np.frombuffer(
            lower_bounds_bytes,
            dtype=np.float64,
        )
        immutable_upper_bounds: np.ndarray = np.frombuffer(
            upper_bounds_bytes,
            dtype=np.float64,
        )

        self.interface_mode: FmuInterfaceMode = interface_mode
        self.mechanism: ReferenceFmuEventMechanism = mechanism
        self.detection_rule: ReferenceFmuEventDetectionRule = detection_rule
        self.observed_variable_name: str = observed_variable_name
        self.observed_variable_type: FmuVariableType = observed_variable_type
        self.event_lower_bounds_seconds: np.ndarray = immutable_lower_bounds
        self.event_upper_bounds_seconds: np.ndarray = immutable_upper_bounds
        self.observable_transition_count: int = observable_transition_count
        self.initial_observed_value: int | float = validated_initial_value
        self.semantic_final_value: int | float = validated_semantic_final_value
        self.expected_last_observed_value: int | float = (
            validated_last_observed_value
        )
        self.expected_transition_delta: int | float | None = (
            validated_transition_delta
        )
        self.termination_kind: ReferenceFmuTerminationKind = termination_kind
        self.expected_termination_time_seconds: float = (
            validated_termination_time_seconds
        )
        self.terminal_post_event_observable: bool = terminal_post_event_observable
        self.terminal_value_must_be_sustained: bool = (
            terminal_value_must_be_sustained
        )


class ReferenceFmuCase:
    """Own one validated reference FMU identity and its numerical oracle."""

    __slots__ = (
        "case_id",
        "model_name",
        "fmi_version",
        "archive_relative_path",
        "fmu_sha256",
        "fmu_size_bytes",
        "interfaces",
        "reference_output_relative_path",
        "reference_output_sha256",
        "start_time_seconds",
        "declared_stop_time_seconds",
        "step_size_seconds",
        "expected_last_sample_time_seconds",
        "expected_sample_count",
        "interface_oracles",
    )

    case_id: str
    model_name: str
    fmi_version: FmiVersion
    archive_relative_path: str
    fmu_sha256: str
    fmu_size_bytes: int
    interfaces: tuple[FmuInterfaceMode, ...]
    reference_output_relative_path: str
    reference_output_sha256: str
    start_time_seconds: float
    declared_stop_time_seconds: float
    step_size_seconds: float
    expected_last_sample_time_seconds: float
    expected_sample_count: int
    interface_oracles: tuple[ReferenceFmuEventOracle, ...]

    def __init__(
        self,
        case_id: str,
        model_name: str,
        fmi_version: FmiVersion,
        archive_relative_path: str,
        fmu_sha256: str,
        fmu_size_bytes: int,
        interfaces: tuple[FmuInterfaceMode, ...],
        reference_output_relative_path: str,
        reference_output_sha256: str,
        start_time_seconds: float,
        declared_stop_time_seconds: float,
        step_size_seconds: float,
        expected_last_sample_time_seconds: float,
        expected_sample_count: int,
        interface_oracles: tuple[ReferenceFmuEventOracle, ...],
    ) -> None:
        """Validate and retain one reference FMU case.

        :param case_id: Stable corpus case identifier.
        :param model_name: Model name declared by the FMU.
        :param fmi_version: FMI specification family.
        :param archive_relative_path: FMU path inside the release archive.
        :param fmu_sha256: SHA-256 of the exact FMU bytes.
        :param fmu_size_bytes: Exact FMU byte count.
        :param interfaces: Supported interfaces in canonical order.
        :param reference_output_relative_path: CSV path inside the FMU.
        :param reference_output_sha256: SHA-256 of the reference CSV.
        :param start_time_seconds: First reference sample time.
        :param declared_stop_time_seconds: Default experiment stop time.
        :param step_size_seconds: Uniform reference sampling interval.
        :param expected_last_sample_time_seconds: Last retained sample time.
        :param expected_sample_count: Inclusive number of samples.
        :param interface_oracles: Immutable CS then ME event oracles.
        :return: None.
        """

        # Validate identity values before deriving the time lattice.
        identity_is_valid: bool = bool(
            isinstance(case_id, str)
            and bool(case_id.strip())
            and isinstance(model_name, str)
            and bool(model_name.strip())
            and isinstance(fmi_version, FmiVersion)
        )
        if identity_is_valid:
            pass
        else:
            raise ValueError("Reference FMU case identity is invalid")

        path_values: tuple[str, str] = (
            archive_relative_path,
            reference_output_relative_path,
        )
        for path_value in path_values:
            path_is_portable: bool = bool(
                isinstance(path_value, str)
                and bool(path_value)
                and path_value.isascii()
                and re.fullmatch(
                    r"[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*",
                    path_value,
                )
                is not None
            )
            if path_is_portable:
                pass
            else:
                raise ValueError("Reference FMU paths must use portable POSIX syntax")

        validated_fmu_sha256: str = _validate_lowercase_hex(
            fmu_sha256,
            "fmu_sha256",
            64,
        )
        validated_reference_output_sha256: str = _validate_lowercase_hex(
            reference_output_sha256,
            "reference_output_sha256",
            64,
        )
        size_is_valid: bool = bool(
            isinstance(fmu_size_bytes, int)
            and not isinstance(fmu_size_bytes, bool)
            and fmu_size_bytes > 0
        )
        count_is_valid: bool = bool(
            isinstance(expected_sample_count, int)
            and not isinstance(expected_sample_count, bool)
            and 2 <= expected_sample_count <= 1_000_001
        )
        if size_is_valid and count_is_valid:
            pass
        else:
            raise ValueError("Reference FMU size or sample count is invalid")

        expected_interfaces: tuple[FmuInterfaceMode, ...] = (
            FmuInterfaceMode.CO_SIMULATION,
            FmuInterfaceMode.MODEL_EXCHANGE,
        )
        interfaces_are_valid: bool = bool(
            isinstance(interfaces, tuple) and interfaces == expected_interfaces
        )
        if interfaces_are_valid:
            pass
        else:
            raise ValueError("Reference FMU interfaces must be CS then ME")

        oracles_are_valid: bool = bool(
            isinstance(interface_oracles, tuple)
            and len(interface_oracles) == 2
            and all(
                oracle.__class__ is ReferenceFmuEventOracle
                for oracle in interface_oracles
            )
            and interface_oracles[0].interface_mode
            == FmuInterfaceMode.CO_SIMULATION
            and interface_oracles[1].interface_mode
            == FmuInterfaceMode.MODEL_EXCHANGE
        )
        if oracles_are_valid:
            pass
        else:
            raise ValueError("Reference FMU oracles must be CS then ME")

        temporal_values: tuple[object, ...] = (
            start_time_seconds,
            declared_stop_time_seconds,
            step_size_seconds,
            expected_last_sample_time_seconds,
        )
        temporal_types_are_valid: bool = all(
            isinstance(temporal_value, (int, float))
            and not isinstance(temporal_value, bool)
            for temporal_value in temporal_values
        )
        if temporal_types_are_valid:
            validated_start_time_seconds: float = float(start_time_seconds)
            validated_declared_stop_time_seconds: float = float(
                declared_stop_time_seconds
            )
            validated_step_size_seconds: float = float(step_size_seconds)
            validated_last_sample_time_seconds: float = float(
                expected_last_sample_time_seconds
            )
        else:
            raise ValueError("Reference FMU temporal values must be real scalars")

        validated_temporal_values: tuple[float, ...] = (
            validated_start_time_seconds,
            validated_declared_stop_time_seconds,
            validated_step_size_seconds,
            validated_last_sample_time_seconds,
        )
        temporal_domain_is_valid: bool = bool(
            all(
                math.isfinite(temporal_value)
                for temporal_value in validated_temporal_values
            )
            and validated_start_time_seconds >= 0.0
            and validated_step_size_seconds > 0.0
            and validated_start_time_seconds
            <= validated_last_sample_time_seconds
            <= validated_declared_stop_time_seconds
        )
        if temporal_domain_is_valid:
            pass
        else:
            raise ValueError("Reference FMU temporal domain is invalid")

        lattice_ratio: float = (
            validated_last_sample_time_seconds - validated_start_time_seconds
        ) / validated_step_size_seconds
        if math.isfinite(lattice_ratio):
            lattice_interval_count: int = int(round(lattice_ratio))
        else:
            raise ValueError("Reference FMU lattice ratio must be finite")
        lattice_error_seconds: float = abs(
            validated_start_time_seconds
            + lattice_interval_count * validated_step_size_seconds
            - validated_last_sample_time_seconds
        )
        lattice_is_valid: bool = bool(
            lattice_error_seconds <= 1.0e-12
            and expected_sample_count == lattice_interval_count + 1
        )
        if lattice_is_valid:
            pass
        else:
            raise ValueError("Reference FMU sample lattice is invalid")

        # Both interfaces observe the same variable while retaining their own
        # event timing and terminal observability semantics.
        for oracle in interface_oracles:
            oracle_matches_case: bool = bool(
                oracle.observed_variable_name
                == interface_oracles[0].observed_variable_name
                and oracle.observed_variable_type
                == interface_oracles[0].observed_variable_type
                and np.all(
                    oracle.event_lower_bounds_seconds
                    >= validated_start_time_seconds
                )
                and np.all(
                    oracle.event_upper_bounds_seconds
                    <= oracle.expected_termination_time_seconds
                )
            )
            if oracle_matches_case:
                pass
            else:
                raise ValueError("Reference oracle is inconsistent with its case")

            if oracle.termination_kind == ReferenceFmuTerminationKind.FMU_REQUEST:
                termination_is_coherent: bool = bool(
                    abs(
                        oracle.expected_termination_time_seconds
                        - validated_last_sample_time_seconds
                    )
                    <= 1.0e-12
                    and abs(
                        float(oracle.event_upper_bounds_seconds[-1])
                        - validated_last_sample_time_seconds
                    )
                    <= 1.0e-12
                )
            else:
                termination_is_coherent = bool(
                    oracle.termination_kind
                    == ReferenceFmuTerminationKind.CONFIGURED_STOP
                    and abs(
                        oracle.expected_termination_time_seconds
                        - validated_declared_stop_time_seconds
                    )
                    <= 1.0e-12
                    and abs(
                        validated_last_sample_time_seconds
                        - validated_declared_stop_time_seconds
                    )
                    <= 1.0e-12
                )
            if termination_is_coherent:
                pass
            else:
                raise ValueError("Reference FMU termination is inconsistent")

        self.case_id: str = case_id
        self.model_name: str = model_name
        self.fmi_version: FmiVersion = fmi_version
        self.archive_relative_path: str = archive_relative_path
        self.fmu_sha256: str = validated_fmu_sha256
        self.fmu_size_bytes: int = fmu_size_bytes
        self.interfaces: tuple[FmuInterfaceMode, ...] = interfaces
        self.reference_output_relative_path: str = reference_output_relative_path
        self.reference_output_sha256: str = validated_reference_output_sha256
        self.start_time_seconds: float = validated_start_time_seconds
        self.declared_stop_time_seconds: float = (
            validated_declared_stop_time_seconds
        )
        self.step_size_seconds: float = validated_step_size_seconds
        self.expected_last_sample_time_seconds: float = (
            validated_last_sample_time_seconds
        )
        self.expected_sample_count: int = expected_sample_count
        self.interface_oracles: tuple[ReferenceFmuEventOracle, ...] = (
            interface_oracles
        )

    def find_interface_oracle(
        self,
        interface_mode: FmuInterfaceMode,
    ) -> ReferenceFmuEventOracle:
        """Return the oracle owned by one exact FMI interface.

        :param interface_mode: Interface whose event semantics are required.
        :return: Canonical oracle for the requested interface.
        """

        if isinstance(interface_mode, FmuInterfaceMode):
            pass
        else:
            raise ValueError("FMI interface mode must use its declared Enum")

        selected_oracle: ReferenceFmuEventOracle | None = None
        for oracle in self.interface_oracles:
            if oracle.interface_mode == interface_mode:
                selected_oracle = oracle
            else:
                pass
        if selected_oracle is None:
            raise ValueError("Reference FMU interface oracle was not found")
        else:
            return selected_oracle

class ValidatedReferenceFmuAsset:
    """Retain exact immutable FMU bytes validated against one corpus case."""

    __slots__ = ("case", "source_path", "content")

    case: ReferenceFmuCase
    source_path: Path
    content: bytes

    def __init__(
        self,
        case: ReferenceFmuCase,
        source_path: Path,
        content: bytes,
    ) -> None:
        """Validate and retain the exact bytes read from an FMU path.

        :param case: Corpus case authorizing the expected identity.
        :param source_path: Path from which the bytes were read once.
        :param content: Immutable bytes obtained through that file handle.
        :return: None.
        """

        inputs_are_valid: bool = bool(
            isinstance(case, ReferenceFmuCase)
            and isinstance(source_path, Path)
            and isinstance(content, bytes)
        )
        if inputs_are_valid:
            pass
        else:
            raise ValueError("Validated FMU asset inputs have invalid types")

        content_hash: str = hashlib.sha256(content).hexdigest()
        content_matches_case: bool = bool(
            len(content) == case.fmu_size_bytes
            and content_hash == case.fmu_sha256
        )
        if content_matches_case:
            pass
        else:
            raise ValueError("FMU bytes do not match the selected corpus case")

        self.case: ReferenceFmuCase = case
        self.source_path: Path = source_path
        self.content: bytes = content


class ReferenceFmuCatalog:
    """Own the deeply validated identity of Reference FMUs release v0.0.41."""

    __slots__ = (
        "schema_name",
        "project_name",
        "repository_url",
        "release_tag",
        "published_at_utc",
        "release_url",
        "tag_object_sha",
        "commit_sha",
        "archive_name",
        "archive_size_bytes",
        "archive_sha256",
        "license_spdx",
        "license_url",
        "license_file_sha256",
        "cases",
    )

    schema_name: str
    project_name: str
    repository_url: str
    release_tag: str
    published_at_utc: str
    release_url: str
    tag_object_sha: str
    commit_sha: str
    archive_name: str
    archive_size_bytes: int
    archive_sha256: str
    license_spdx: str
    license_url: str
    license_file_sha256: str
    cases: tuple[ReferenceFmuCase, ...]

    def __init__(
        self,
        schema_name: str,
        project_name: str,
        repository_url: str,
        release_tag: str,
        published_at_utc: str,
        release_url: str,
        tag_object_sha: str,
        commit_sha: str,
        archive_name: str,
        archive_size_bytes: int,
        archive_sha256: str,
        license_spdx: str,
        license_url: str,
        license_file_sha256: str,
        cases: tuple[ReferenceFmuCase, ...],
    ) -> None:
        """Validate the exact release and every nested canonical case.

        :param schema_name: Sealed catalog schema identifier.
        :param project_name: Upstream project name.
        :param repository_url: Upstream repository URL.
        :param release_tag: Pinned upstream release tag.
        :param published_at_utc: Upstream publication timestamp.
        :param release_url: Pinned release page URL.
        :param tag_object_sha: Annotated Git tag-object SHA.
        :param commit_sha: Commit referenced by the release tag.
        :param archive_name: Official release archive name.
        :param archive_size_bytes: Exact archive byte count.
        :param archive_sha256: SHA-256 of the official archive.
        :param license_spdx: Upstream SPDX license identifier.
        :param license_url: Pinned upstream license URL.
        :param license_file_sha256: SHA-256 of the license file.
        :param cases: Four canonical reference cases in sealed order.
        :return: None.
        """

        # The catalog is an audited corpus identity, not a generic release DTO.
        release_is_canonical: bool = bool(
            schema_name == "veragrid-fmi-reference-corpus-v2"
            and project_name == "Reference FMUs"
            and repository_url == "https://github.com/modelica/Reference-FMUs"
            and release_tag == "v0.0.41"
            and published_at_utc == "2026-08-12T14:42:51Z"
            and release_url
            == "https://github.com/modelica/Reference-FMUs/releases/tag/v0.0.41"
            and tag_object_sha == "fc8b52dcf22e9fb13a5d9ac4e2e1605af665a106"
            and commit_sha == "1258711a41e28b1c25e058abd04f6214beefa3cb"
            and archive_name == "Reference-FMUs.zip"
            and isinstance(archive_size_bytes, int)
            and not isinstance(archive_size_bytes, bool)
            and archive_size_bytes == 3390239
            and archive_sha256
            == "62babca76b9c23a51c3096be4bb5930ff8b4388659056be3c0c4ef7a3aeb5403"
            and license_spdx == "BSD-2-Clause"
            and license_url
            == "https://github.com/modelica/Reference-FMUs/blob/v0.0.41/LICENSE.txt"
            and license_file_sha256
            == "3bd19affe120c783d1bb63f423ba1e5b31fed892d98d583001aac013a3432041"
        )
        if release_is_canonical:
            pass
        else:
            raise ValueError("Reference FMU release identity is not canonical")

        _validate_lowercase_hex(tag_object_sha, "tag_object_sha", 40)
        _validate_lowercase_hex(commit_sha, "commit_sha", 40)
        _validate_lowercase_hex(archive_sha256, "archive_sha256", 64)
        _validate_lowercase_hex(
            license_file_sha256,
            "license_file_sha256",
            64,
        )

        cases_are_structurally_valid: bool = bool(
            isinstance(cases, tuple)
            and len(cases) == 4
            and all(case.__class__ is ReferenceFmuCase for case in cases)
        )
        if cases_are_structurally_valid:
            pass
        else:
            raise ValueError("Reference FMU catalog must contain four exact cases")

        # Compare every nested field so public constructors cannot bypass the
        # sealed loader by retaining only the canonical case identifiers.
        for case_index in range(4):
            reference_case: ReferenceFmuCase = cases[case_index]
            expected_case_id: str
            expected_model_name: str
            expected_fmi_version: FmiVersion
            expected_archive_relative_path: str
            expected_fmu_sha256: str
            expected_fmu_size_bytes: int
            expected_reference_output_relative_path: str
            expected_reference_output_sha256: str
            expected_start_time_seconds: float
            expected_declared_stop_time_seconds: float
            expected_step_size_seconds: float
            expected_last_sample_time_seconds: float
            expected_sample_count: int
            expected_mechanism: ReferenceFmuEventMechanism
            expected_detection_rule: ReferenceFmuEventDetectionRule
            expected_observed_variable_name: str
            expected_observed_variable_type: FmuVariableType
            expected_lower_bounds: tuple[float, ...]
            expected_upper_bounds: tuple[float, ...]
            expected_initial_value: int | float
            expected_semantic_final_value: int | float
            expected_transition_delta: int | float | None
            expected_termination_kind: ReferenceFmuTerminationKind
            expected_termination_time_seconds: float
            expected_last_observed_value: int | float
            expected_sustained: bool

            match case_index:
                case 0:
                    expected_case_id = "reference-fmus-2.0-bouncing-ball"
                    expected_model_name = "BouncingBall"
                    expected_fmi_version = FmiVersion.FMI_2_0
                    expected_archive_relative_path = "2.0/BouncingBall.fmu"
                    expected_fmu_sha256 = "3959d0dea751e788b7b9591da6beb11955352a1ac46138244ee5343efb7ce5e4"
                    expected_fmu_size_bytes = 198193
                    expected_reference_output_relative_path = "extra/org.fmi-standard.fmi-ls-ref/BouncingBall_out.csv"
                    expected_reference_output_sha256 = "7123af5e548a120e20a8167a7ece4df442474b7788a31bf57d2c0c177702a150"
                    expected_start_time_seconds = 0.0
                    expected_declared_stop_time_seconds = 3.0
                    expected_step_size_seconds = 0.01
                    expected_last_sample_time_seconds = 3.0
                    expected_sample_count = 301
                    expected_mechanism = ReferenceFmuEventMechanism.STATE_EVENT
                    expected_detection_rule = ReferenceFmuEventDetectionRule.NEGATIVE_TO_NONNEGATIVE
                    expected_observed_variable_name = "v"
                    expected_observed_variable_type = FmuVariableType.REAL
                    expected_lower_bounds = (0.45, 1.08, 1.53, 1.85, 2.07, 2.23, 2.35, 2.43, 2.49, 2.54, 2.57, 2.60)
                    expected_upper_bounds = (0.46, 1.09, 1.54, 1.86, 2.08, 2.24, 2.36, 2.44, 2.50, 2.55, 2.58, 2.61)
                    expected_initial_value = 0.0
                    expected_semantic_final_value = 0.0
                    expected_transition_delta = None
                    expected_termination_kind = ReferenceFmuTerminationKind.CONFIGURED_STOP
                    expected_termination_time_seconds = 3.0
                    expected_last_observed_value = 0.0
                    expected_sustained = True
                case 1:
                    expected_case_id = "reference-fmus-2.0-stair"
                    expected_model_name = "Stair"
                    expected_fmi_version = FmiVersion.FMI_2_0
                    expected_archive_relative_path = "2.0/Stair.fmu"
                    expected_fmu_sha256 = "917f5a7123cf5b2857ac6bc7a121fe96e0a37a9a734b84d0166fd0554298789c"
                    expected_fmu_size_bytes = 185583
                    expected_reference_output_relative_path = "extra/org.fmi-standard.fmi-ls-ref/Stair_out.csv"
                    expected_reference_output_sha256 = "15e6142e3422925c88cd73b0c7993016228988cc2a5832d99cbdf23170828f30"
                    expected_start_time_seconds = 0.0
                    expected_declared_stop_time_seconds = 10.0
                    expected_step_size_seconds = 0.2
                    expected_last_sample_time_seconds = 9.0
                    expected_sample_count = 46
                    expected_mechanism = ReferenceFmuEventMechanism.TIME_EVENT
                    expected_detection_rule = ReferenceFmuEventDetectionRule.VALUE_CHANGE_AT_TIME
                    expected_observed_variable_name = "counter"
                    expected_observed_variable_type = FmuVariableType.INTEGER
                    expected_lower_bounds = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0)
                    expected_upper_bounds = expected_lower_bounds
                    expected_initial_value = 1
                    expected_semantic_final_value = 10
                    expected_transition_delta = 1
                    expected_termination_kind = ReferenceFmuTerminationKind.FMU_REQUEST
                    expected_termination_time_seconds = 9.0
                    expected_last_observed_value = 10
                    expected_sustained = False
                case 2:
                    expected_case_id = "reference-fmus-3.0-bouncing-ball"
                    expected_model_name = "BouncingBall"
                    expected_fmi_version = FmiVersion.FMI_3_0
                    expected_archive_relative_path = "3.0/BouncingBall.fmu"
                    expected_fmu_sha256 = "f14f1f46c97c21bc208c139fa30d19ebce5b1d0fa0789f09a1ff1b9a6b9ee8c5"
                    expected_fmu_size_bytes = 246743
                    expected_reference_output_relative_path = "extra/org.fmi-standard.fmi-ls-ref/BouncingBall_out.csv"
                    expected_reference_output_sha256 = "7123af5e548a120e20a8167a7ece4df442474b7788a31bf57d2c0c177702a150"
                    expected_start_time_seconds = 0.0
                    expected_declared_stop_time_seconds = 3.0
                    expected_step_size_seconds = 0.01
                    expected_last_sample_time_seconds = 3.0
                    expected_sample_count = 301
                    expected_mechanism = ReferenceFmuEventMechanism.STATE_EVENT
                    expected_detection_rule = ReferenceFmuEventDetectionRule.NEGATIVE_TO_NONNEGATIVE
                    expected_observed_variable_name = "v"
                    expected_observed_variable_type = FmuVariableType.FLOAT64
                    expected_lower_bounds = (0.45, 1.08, 1.53, 1.85, 2.07, 2.23, 2.35, 2.43, 2.49, 2.54, 2.57, 2.60)
                    expected_upper_bounds = (0.46, 1.09, 1.54, 1.86, 2.08, 2.24, 2.36, 2.44, 2.50, 2.55, 2.58, 2.61)
                    expected_initial_value = 0.0
                    expected_semantic_final_value = 0.0
                    expected_transition_delta = None
                    expected_termination_kind = ReferenceFmuTerminationKind.CONFIGURED_STOP
                    expected_termination_time_seconds = 3.0
                    expected_last_observed_value = 0.0
                    expected_sustained = True
                case 3:
                    expected_case_id = "reference-fmus-3.0-stair"
                    expected_model_name = "Stair"
                    expected_fmi_version = FmiVersion.FMI_3_0
                    expected_archive_relative_path = "3.0/Stair.fmu"
                    expected_fmu_sha256 = "031dc8028fae3d8c48c7f3c11ab4f7db5ab1df81f9e0a8dc1f5610c69d1939d4"
                    expected_fmu_size_bytes = 231692
                    expected_reference_output_relative_path = "extra/org.fmi-standard.fmi-ls-ref/Stair_out.csv"
                    expected_reference_output_sha256 = "15e6142e3422925c88cd73b0c7993016228988cc2a5832d99cbdf23170828f30"
                    expected_start_time_seconds = 0.0
                    expected_declared_stop_time_seconds = 10.0
                    expected_step_size_seconds = 0.2
                    expected_last_sample_time_seconds = 9.0
                    expected_sample_count = 46
                    expected_mechanism = ReferenceFmuEventMechanism.TIME_EVENT
                    expected_detection_rule = ReferenceFmuEventDetectionRule.VALUE_CHANGE_AT_TIME
                    expected_observed_variable_name = "counter"
                    expected_observed_variable_type = FmuVariableType.INT32
                    expected_lower_bounds = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0)
                    expected_upper_bounds = expected_lower_bounds
                    expected_initial_value = 1
                    expected_semantic_final_value = 10
                    expected_transition_delta = 1
                    expected_termination_kind = ReferenceFmuTerminationKind.FMU_REQUEST
                    expected_termination_time_seconds = 9.0
                    expected_last_observed_value = 10
                    expected_sustained = False
                case _:
                    raise ValueError("Reference FMU case index is outside the corpus")

            expected_interfaces: tuple[FmuInterfaceMode, ...] = (
                FmuInterfaceMode.CO_SIMULATION,
                FmuInterfaceMode.MODEL_EXCHANGE,
            )
            oracle: ReferenceFmuEventOracle = reference_case.interface_oracles[0]
            oracle_class_is_exact: bool = bool(
                oracle.__class__ is ReferenceFmuEventOracle
            )
            lower_bounds_match: bool = bool(
                oracle.event_lower_bounds_seconds.dtype == np.dtype(np.float64)
                and oracle.event_lower_bounds_seconds.shape
                == (len(expected_lower_bounds),)
                and np.array_equal(
                    oracle.event_lower_bounds_seconds,
                    np.asarray(expected_lower_bounds, dtype=np.float64),
                )
            )
            upper_bounds_match: bool = bool(
                oracle.event_upper_bounds_seconds.dtype == np.dtype(np.float64)
                and oracle.event_upper_bounds_seconds.shape
                == (len(expected_upper_bounds),)
                and np.array_equal(
                    oracle.event_upper_bounds_seconds,
                    np.asarray(expected_upper_bounds, dtype=np.float64),
                )
            )
            scalar_types_match: bool = bool(
                type(oracle.initial_observed_value) is type(expected_initial_value)
                and type(oracle.semantic_final_value)
                is type(expected_semantic_final_value)
                and type(oracle.expected_transition_delta)
                is type(expected_transition_delta)
                and type(oracle.expected_last_observed_value)
                is type(expected_last_observed_value)
            )
            case_is_canonical: bool = bool(
                reference_case.case_id == expected_case_id
                and reference_case.model_name == expected_model_name
                and reference_case.fmi_version == expected_fmi_version
                and reference_case.archive_relative_path
                == expected_archive_relative_path
                and reference_case.fmu_sha256 == expected_fmu_sha256
                and reference_case.fmu_size_bytes == expected_fmu_size_bytes
                and reference_case.interfaces == expected_interfaces
                and reference_case.reference_output_relative_path
                == expected_reference_output_relative_path
                and reference_case.reference_output_sha256
                == expected_reference_output_sha256
                and reference_case.start_time_seconds
                == expected_start_time_seconds
                and reference_case.declared_stop_time_seconds
                == expected_declared_stop_time_seconds
                and reference_case.step_size_seconds == expected_step_size_seconds
                and reference_case.expected_last_sample_time_seconds
                == expected_last_sample_time_seconds
                and reference_case.expected_sample_count == expected_sample_count
                and oracle_class_is_exact
                and oracle.interface_mode == FmuInterfaceMode.CO_SIMULATION
                and oracle.mechanism == expected_mechanism
                and oracle.detection_rule == expected_detection_rule
                and oracle.observed_variable_name
                == expected_observed_variable_name
                and oracle.observed_variable_type
                == expected_observed_variable_type
                and lower_bounds_match
                and upper_bounds_match
                and scalar_types_match
                and oracle.initial_observed_value == expected_initial_value
                and oracle.semantic_final_value
                == expected_semantic_final_value
                and oracle.expected_transition_delta == expected_transition_delta
                and oracle.termination_kind == expected_termination_kind
                and oracle.expected_termination_time_seconds
                == expected_termination_time_seconds
                and oracle.expected_last_observed_value
                == expected_last_observed_value
                and oracle.observable_transition_count
                == len(expected_lower_bounds)
                and oracle.terminal_post_event_observable
                and oracle.terminal_value_must_be_sustained
                is expected_sustained
            )

            # Model Exchange owns a different numerical event oracle. State
            # roots use analytical windows; Stair exposes only eight of nine
            # semantic transitions before the FMU termination request.
            me_oracle: ReferenceFmuEventOracle = reference_case.interface_oracles[1]
            if expected_mechanism == ReferenceFmuEventMechanism.STATE_EVENT:
                me_centers: tuple[float, ...] = (
                    0.4515236409857309,
                    1.083656738365754,
                    1.5261499065317703,
                    1.8358951242479815,
                    2.0527167766493295,
                    2.204491933330273,
                    2.3107345430069337,
                    2.385104369780596,
                    2.4371632485221597,
                    2.473604463641254,
                    2.4991133142246205,
                )
                me_lower_bounds: np.ndarray = (
                    np.asarray(me_centers, dtype=np.float64) - 2.0e-6
                )
                me_upper_bounds: np.ndarray = (
                    np.asarray(me_centers, dtype=np.float64) + 2.0e-6
                )
                expected_me_observable_count: int = 11
                expected_me_last_value: int | float = 0.0
                expected_me_terminal_observable: bool = True
            else:
                me_lower_bounds = np.asarray(
                    expected_lower_bounds,
                    dtype=np.float64,
                )
                me_upper_bounds = np.asarray(
                    expected_upper_bounds,
                    dtype=np.float64,
                )
                expected_me_observable_count = 8
                expected_me_last_value = 9
                expected_me_terminal_observable = False

            me_scalar_types_match: bool = bool(
                type(me_oracle.initial_observed_value)
                is type(expected_initial_value)
                and type(me_oracle.semantic_final_value)
                is type(expected_semantic_final_value)
                and type(me_oracle.expected_last_observed_value)
                is type(expected_me_last_value)
                and type(me_oracle.expected_transition_delta)
                is type(expected_transition_delta)
            )
            me_oracle_is_canonical: bool = bool(
                me_oracle.__class__ is ReferenceFmuEventOracle
                and me_oracle.interface_mode == FmuInterfaceMode.MODEL_EXCHANGE
                and me_oracle.mechanism == expected_mechanism
                and me_oracle.detection_rule == expected_detection_rule
                and me_oracle.observed_variable_name
                == expected_observed_variable_name
                and me_oracle.observed_variable_type
                == expected_observed_variable_type
                and me_oracle.event_lower_bounds_seconds.dtype
                == np.dtype(np.float64)
                and me_oracle.event_upper_bounds_seconds.dtype
                == np.dtype(np.float64)
                and np.array_equal(
                    me_oracle.event_lower_bounds_seconds,
                    me_lower_bounds,
                )
                and np.array_equal(
                    me_oracle.event_upper_bounds_seconds,
                    me_upper_bounds,
                )
                and me_scalar_types_match
                and me_oracle.observable_transition_count
                == expected_me_observable_count
                and me_oracle.initial_observed_value == expected_initial_value
                and me_oracle.semantic_final_value
                == expected_semantic_final_value
                and me_oracle.expected_last_observed_value
                == expected_me_last_value
                and me_oracle.expected_transition_delta
                == expected_transition_delta
                and me_oracle.termination_kind == expected_termination_kind
                and me_oracle.expected_termination_time_seconds
                == expected_termination_time_seconds
                and me_oracle.terminal_post_event_observable
                is expected_me_terminal_observable
                and me_oracle.terminal_value_must_be_sustained
                is expected_sustained
            )
            if case_is_canonical and me_oracle_is_canonical:
                pass
            else:
                raise ValueError("Reference FMU case is not canonical")

        self.schema_name: str = schema_name
        self.project_name: str = project_name
        self.repository_url: str = repository_url
        self.release_tag: str = release_tag
        self.published_at_utc: str = published_at_utc
        self.release_url: str = release_url
        self.tag_object_sha: str = tag_object_sha
        self.commit_sha: str = commit_sha
        self.archive_name: str = archive_name
        self.archive_size_bytes: int = archive_size_bytes
        self.archive_sha256: str = archive_sha256
        self.license_spdx: str = license_spdx
        self.license_url: str = license_url
        self.license_file_sha256: str = license_file_sha256
        self.cases: tuple[ReferenceFmuCase, ...] = cases

    def find_case(self, case_id: str) -> ReferenceFmuCase:
        """Return one canonical case by its stable identifier.

        :param case_id: Exact case identifier to locate.
        :return: Matching canonical reference case.
        """

        if isinstance(case_id, str) and bool(case_id.strip()):
            pass
        else:
            raise ValueError("Reference FMU case ID must be nonempty text")

        selected_case: ReferenceFmuCase | None = None
        for reference_case in self.cases:
            if reference_case.case_id == case_id:
                selected_case = reference_case
                break
            else:
                pass
        if selected_case is None:
            raise ValueError(f"Unknown Reference FMU case: {case_id}")
        else:
            return selected_case

    def validate_asset(
        self,
        case_id: str,
        asset_path: Path,
    ) -> ValidatedReferenceFmuAsset:
        """Read and validate one exact FMU without executing or extracting it.

        :param case_id: Canonical case identifying the expected bytes.
        :param asset_path: Explicit local path to the candidate FMU.
        :return: Owner containing the exact immutable validated bytes.
        """

        reference_case: ReferenceFmuCase = self.find_case(case_id)
        # Filesystem metadata can be inaccessible for unsupported reparse
        # points. Such a path is not a valid immutable FMU source, so keep
        # that platform detail behind the public validation boundary.
        path_is_valid: bool = False
        try:
            path_is_valid = bool(
                isinstance(asset_path, Path)
                and asset_path.exists()
                and asset_path.is_file()
                and not asset_path.is_symlink()
                and asset_path.suffix == ".fmu"
            )
        except OSError:
            path_is_valid = False
        if path_is_valid:
            pass
        else:
            raise ValueError("Reference FMU asset path is unsafe or invalid")

        # One bounded read produces the exact bytes passed to the typed owner.
        asset_file: BinaryIO = asset_path.open("rb")
        try:
            content: bytes = asset_file.read(reference_case.fmu_size_bytes + 1)
        finally:
            asset_file.close()
        if len(content) <= reference_case.fmu_size_bytes:
            pass
        else:
            raise ValueError("Reference FMU asset is larger than declared")

        return ValidatedReferenceFmuAsset(
            case=reference_case,
            source_path=asset_path,
            content=content,
        )

def _validate_lowercase_hex(
    value: object,
    field_name: str,
    character_count: int,
) -> str:
    """Validate one exact-length lowercase hexadecimal identifier.

    :param value: Candidate identifier.
    :param field_name: Field name used in validation errors.
    :param character_count: Required number of hexadecimal characters.
    :return: Validated lowercase hexadecimal text.
    """

    arguments_are_valid: bool = bool(
        isinstance(field_name, str)
        and bool(field_name)
        and isinstance(character_count, int)
        and not isinstance(character_count, bool)
        and character_count > 0
    )
    if arguments_are_valid:
        pass
    else:
        raise ValueError("Hexadecimal validation arguments are invalid")

    value_is_valid: bool = bool(
        isinstance(value, str)
        and len(value) == character_count
        and all(character in "0123456789abcdef" for character in value)
    )
    if value_is_valid:
        return cast(str, value)
    else:
        raise ValueError(f"{field_name} must be lowercase hexadecimal text")


def _require_exact_keys(
    value: object,
    expected_keys: tuple[str, ...],
    object_name: str,
) -> dict[str, object]:
    """Require one parsed JSON object to expose exactly the expected keys.

    :param value: Candidate parsed JSON value.
    :param expected_keys: Complete accepted key set.
    :param object_name: Logical object name used in validation errors.
    :return: The validated transient parsing dictionary.
    """

    arguments_are_valid: bool = bool(
        isinstance(expected_keys, tuple)
        and all(isinstance(key, str) for key in expected_keys)
        and len(set(expected_keys)) == len(expected_keys)
        and isinstance(object_name, str)
        and bool(object_name)
    )
    if arguments_are_valid:
        pass
    else:
        raise ValueError("Exact-key validation arguments are invalid")

    if isinstance(value, dict):
        parsed_object: dict[str, object] = cast(dict[str, object], value)
    else:
        raise ValueError(f"{object_name} must be a JSON object")
    provided_keys: set[str] = set(parsed_object.keys())
    required_keys: set[str] = set(expected_keys)
    if provided_keys == required_keys:
        return parsed_object
    else:
        raise ValueError(f"{object_name} keys do not match the sealed schema")


def _build_unique_json_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    """Build one transient JSON object while rejecting duplicate keys.

    :param pairs: Ordered key-value pairs supplied by ``json.loads``.
    :return: Parsed object containing each key exactly once.
    """

    parsed_object: dict[str, object] = dict()
    for key, value in pairs:
        if key in parsed_object:
            raise ValueError(f"Duplicate JSON key is forbidden: {key}")
        else:
            parsed_object[key] = value
    return parsed_object


def load_reference_fmu_catalog(catalog_path: Path) -> ReferenceFmuCatalog:
    """Load the exact validated Reference FMUs v0.0.41 catalog.

    :param catalog_path: Explicit path to the committed catalog JSON.
    :return: Deeply validated reference corpus.
    """

    path_is_valid: bool = bool(
        isinstance(catalog_path, Path)
        and catalog_path.exists()
        and catalog_path.is_file()
        and not catalog_path.is_symlink()
    )
    if path_is_valid:
        pass
    else:
        raise ValueError("Reference FMU catalog path is unsafe or invalid")

    # Bound the read before JSON parsing so malformed inputs cannot grow freely.
    catalog_file: BinaryIO = catalog_path.open("rb")
    try:
        catalog_bytes: bytes = catalog_file.read(65_537)
    finally:
        catalog_file.close()
    if len(catalog_bytes) <= 65_536:
        pass
    else:
        raise ValueError("Reference FMU catalog exceeds 64 KiB")
    catalog_text: str = catalog_bytes.decode("utf-8", errors="strict")
    parsed_value: object = json.loads(
        catalog_text,
        object_pairs_hook=_build_unique_json_object,
    )

    root: dict[str, object] = _require_exact_keys(
        parsed_value,
        ("schema", "release", "cases"),
        "catalog",
    )
    release: dict[str, object] = _require_exact_keys(
        root["release"],
        (
            "project_name",
            "repository_url",
            "release_tag",
            "published_at_utc",
            "release_url",
            "tag_object_sha",
            "commit_sha",
            "archive_name",
            "archive_size_bytes",
            "archive_sha256",
            "license_spdx",
            "license_url",
            "license_file_sha256",
        ),
        "release",
    )
    cases_value: object = root["cases"]
    if isinstance(cases_value, list) and len(cases_value) == 4:
        case_records: list[object] = cast(list[object], cases_value)
    else:
        raise ValueError("Reference FMU catalog requires four cases")

    parsed_cases: list[ReferenceFmuCase | None] = [None] * 4
    for case_index in range(4):
        case_record: dict[str, object] = _require_exact_keys(
            case_records[case_index],
            (
                "case_id",
                "model_name",
                "fmi_version",
                "archive_relative_path",
                "fmu_sha256",
                "fmu_size_bytes",
                "interfaces",
                "reference_output_relative_path",
                "reference_output_sha256",
                "start_time_seconds",
                "declared_stop_time_seconds",
                "step_size_seconds",
                "expected_last_sample_time_seconds",
                "expected_sample_count",
                "interface_oracles",
            ),
            f"case[{case_index}]",
        )

        case_string_keys: tuple[str, ...] = (
            "case_id",
            "model_name",
            "fmi_version",
            "archive_relative_path",
            "fmu_sha256",
            "reference_output_relative_path",
            "reference_output_sha256",
        )
        case_strings_are_valid: bool = all(
            isinstance(case_record[key], str) for key in case_string_keys
        )
        if case_strings_are_valid:
            pass
        else:
            raise ValueError("Reference FMU text fields have invalid types")

        interfaces_value: object = case_record["interfaces"]
        if isinstance(interfaces_value, list) and len(interfaces_value) == 2:
            interface_records: list[object] = cast(
                list[object],
                interfaces_value,
            )
        else:
            raise ValueError("Reference FMU interfaces must contain two values")
        parsed_interfaces: list[FmuInterfaceMode | None] = [None] * 2
        for interface_index in range(2):
            interface_value: object = interface_records[interface_index]
            if isinstance(interface_value, str):
                parsed_interfaces[interface_index] = FmuInterfaceMode(
                    interface_value
                )
            else:
                raise ValueError("Reference FMU interface must be text")
        interfaces: tuple[FmuInterfaceMode, ...] = (
            cast(FmuInterfaceMode, parsed_interfaces[0]),
            cast(FmuInterfaceMode, parsed_interfaces[1]),
        )

        oracle_values: object = case_record["interface_oracles"]
        if isinstance(oracle_values, list) and len(oracle_values) == 2:
            oracle_records: list[object] = cast(list[object], oracle_values)
        else:
            raise ValueError("Reference FMU case requires CS and ME oracles")

        parsed_oracles: list[ReferenceFmuEventOracle | None] = [None] * 2
        for oracle_index in range(2):
            oracle_record: dict[str, object] = _require_exact_keys(
                oracle_records[oracle_index],
                (
                    "interface_mode",
                    "mechanism",
                    "detection_rule",
                    "observed_variable_name",
                    "observed_variable_type",
                    "event_lower_bounds_seconds",
                    "event_upper_bounds_seconds",
                    "observable_transition_count",
                    "initial_observed_value",
                    "semantic_final_value",
                    "expected_last_observed_value",
                    "expected_transition_delta",
                    "termination_kind",
                    "expected_termination_time_seconds",
                    "terminal_post_event_observable",
                    "terminal_value_must_be_sustained",
                ),
                f"case[{case_index}].interface_oracles[{oracle_index}]",
            )
            oracle_string_keys: tuple[str, ...] = (
                "interface_mode",
                "mechanism",
                "detection_rule",
                "observed_variable_name",
                "observed_variable_type",
                "termination_kind",
            )
            oracle_strings_are_valid: bool = all(
                isinstance(oracle_record[key], str)
                for key in oracle_string_keys
            )
            if oracle_strings_are_valid:
                pass
            else:
                raise ValueError("Reference oracle text fields are invalid")

            lower_values: object = oracle_record["event_lower_bounds_seconds"]
            upper_values: object = oracle_record["event_upper_bounds_seconds"]
            if isinstance(lower_values, list) and isinstance(upper_values, list):
                lower_records: list[object] = cast(list[object], lower_values)
                upper_records: list[object] = cast(list[object], upper_values)
            else:
                raise ValueError("Reference event bounds must be JSON arrays")
            if len(lower_records) == len(upper_records):
                event_count: int = len(lower_records)
            else:
                raise ValueError("Reference event bounds have unequal lengths")
            parsed_lower_bounds: list[float] = [0.0] * event_count
            parsed_upper_bounds: list[float] = [0.0] * event_count
            for event_index in range(event_count):
                lower_value: object = lower_records[event_index]
                upper_value: object = upper_records[event_index]
                bound_types_are_valid: bool = bool(
                    isinstance(lower_value, (int, float))
                    and not isinstance(lower_value, bool)
                    and isinstance(upper_value, (int, float))
                    and not isinstance(upper_value, bool)
                )
                if bound_types_are_valid:
                    parsed_lower_bounds[event_index] = float(lower_value)
                    parsed_upper_bounds[event_index] = float(upper_value)
                else:
                    raise ValueError("Reference event bounds must be real")

            initial_value: object = oracle_record["initial_observed_value"]
            semantic_value: object = oracle_record["semantic_final_value"]
            last_value: object = oracle_record["expected_last_observed_value"]
            transition_delta: object = oracle_record["expected_transition_delta"]
            scalar_types_are_valid: bool = bool(
                isinstance(initial_value, (int, float))
                and not isinstance(initial_value, bool)
                and isinstance(semantic_value, (int, float))
                and not isinstance(semantic_value, bool)
                and isinstance(last_value, (int, float))
                and not isinstance(last_value, bool)
                and (
                    transition_delta is None
                    or (
                        isinstance(transition_delta, (int, float))
                        and not isinstance(transition_delta, bool)
                    )
                )
            )
            if scalar_types_are_valid:
                typed_initial_value: int | float = cast(int | float, initial_value)
                typed_semantic_value: int | float = cast(int | float, semantic_value)
                typed_last_value: int | float = cast(int | float, last_value)
                typed_transition_delta: int | float | None = cast(
                    int | float | None,
                    transition_delta,
                )
            else:
                raise ValueError("Reference event scalar values are invalid")

            observable_count: object = oracle_record["observable_transition_count"]
            terminal_observable: object = oracle_record[
                "terminal_post_event_observable"
            ]
            sustained_value: object = oracle_record[
                "terminal_value_must_be_sustained"
            ]
            oracle_flags_are_valid: bool = bool(
                isinstance(observable_count, int)
                and not isinstance(observable_count, bool)
                and isinstance(terminal_observable, bool)
                and isinstance(sustained_value, bool)
            )
            if oracle_flags_are_valid:
                pass
            else:
                raise ValueError("Reference event count or flags are invalid")

            termination_time: object = oracle_record[
                "expected_termination_time_seconds"
            ]
            if (
                isinstance(termination_time, (int, float))
                and not isinstance(termination_time, bool)
            ):
                typed_termination_time: float = float(termination_time)
            else:
                raise ValueError("Reference termination time is invalid")

            parsed_oracles[oracle_index] = ReferenceFmuEventOracle(
                interface_mode=FmuInterfaceMode(
                    cast(str, oracle_record["interface_mode"])
                ),
                mechanism=ReferenceFmuEventMechanism(
                    cast(str, oracle_record["mechanism"])
                ),
                detection_rule=ReferenceFmuEventDetectionRule(
                    cast(str, oracle_record["detection_rule"])
                ),
                observed_variable_name=cast(
                    str,
                    oracle_record["observed_variable_name"],
                ),
                observed_variable_type=FmuVariableType(
                    cast(str, oracle_record["observed_variable_type"])
                ),
                event_lower_bounds_seconds=tuple(parsed_lower_bounds),
                event_upper_bounds_seconds=tuple(parsed_upper_bounds),
                observable_transition_count=cast(int, observable_count),
                initial_observed_value=typed_initial_value,
                semantic_final_value=typed_semantic_value,
                expected_last_observed_value=typed_last_value,
                expected_transition_delta=typed_transition_delta,
                termination_kind=ReferenceFmuTerminationKind(
                    cast(str, oracle_record["termination_kind"])
                ),
                expected_termination_time_seconds=typed_termination_time,
                terminal_post_event_observable=cast(bool, terminal_observable),
                terminal_value_must_be_sustained=cast(bool, sustained_value),
            )

        interface_oracles: tuple[ReferenceFmuEventOracle, ...] = (
            cast(ReferenceFmuEventOracle, parsed_oracles[0]),
            cast(ReferenceFmuEventOracle, parsed_oracles[1]),
        )
        parsed_cases[case_index] = ReferenceFmuCase(
            case_id=cast(str, case_record["case_id"]),
            model_name=cast(str, case_record["model_name"]),
            fmi_version=FmiVersion(cast(str, case_record["fmi_version"])),
            archive_relative_path=cast(
                str,
                case_record["archive_relative_path"],
            ),
            fmu_sha256=cast(str, case_record["fmu_sha256"]),
            fmu_size_bytes=cast(int, case_record["fmu_size_bytes"]),
            interfaces=interfaces,
            reference_output_relative_path=cast(
                str,
                case_record["reference_output_relative_path"],
            ),
            reference_output_sha256=cast(
                str,
                case_record["reference_output_sha256"],
            ),
            start_time_seconds=cast(float, case_record["start_time_seconds"]),
            declared_stop_time_seconds=cast(
                float,
                case_record["declared_stop_time_seconds"],
            ),
            step_size_seconds=cast(float, case_record["step_size_seconds"]),
            expected_last_sample_time_seconds=cast(
                float,
                case_record["expected_last_sample_time_seconds"],
            ),
            expected_sample_count=cast(
                int,
                case_record["expected_sample_count"],
            ),
            interface_oracles=interface_oracles,
        )

    canonical_cases: tuple[ReferenceFmuCase, ...] = (
        cast(ReferenceFmuCase, parsed_cases[0]),
        cast(ReferenceFmuCase, parsed_cases[1]),
        cast(ReferenceFmuCase, parsed_cases[2]),
        cast(ReferenceFmuCase, parsed_cases[3]),
    )
    return ReferenceFmuCatalog(
        schema_name=cast(str, root["schema"]),
        project_name=cast(str, release["project_name"]),
        repository_url=cast(str, release["repository_url"]),
        release_tag=cast(str, release["release_tag"]),
        published_at_utc=cast(str, release["published_at_utc"]),
        release_url=cast(str, release["release_url"]),
        tag_object_sha=cast(str, release["tag_object_sha"]),
        commit_sha=cast(str, release["commit_sha"]),
        archive_name=cast(str, release["archive_name"]),
        archive_size_bytes=cast(int, release["archive_size_bytes"]),
        archive_sha256=cast(str, release["archive_sha256"]),
        license_spdx=cast(str, release["license_spdx"]),
        license_url=cast(str, release["license_url"]),
        license_file_sha256=cast(str, release["license_file_sha256"]),
        cases=canonical_cases,
    )
