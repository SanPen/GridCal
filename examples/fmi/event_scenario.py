# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Validated event-scenario data for maintained FMI comparison benchmarks."""
from __future__ import annotations

import math

import numpy as np


class RmsLoadPowerStepScenario:
    """Describe the maintained RMS load active-power step benchmark.

    The object retains only independent physical inputs and their deterministic
    time-lattice derivations. Comparison boundaries retain validated copies so
    caller mutation cannot alter accepted event evidence.

    :ivar time_step_seconds: Uniform communication step in seconds.
    :ivar stop_time_seconds: Inclusive simulation stop time in seconds.
    :ivar event_time_seconds: Accepted sample retaining the pre-event value.
    :ivar event_boundary_index: Index of the accepted event-boundary sample.
    :ivar first_post_event_index: First index using the post-event value.
    :ivar first_post_event_time_seconds: Time of the first post-event sample.
    :ivar sample_count: Inclusive number of time-lattice samples.
    :ivar disturbance_load_initial_active_power_mw: Static load active power.
    :ivar disturbance_load_initial_reactive_power_mvar: Static load reactive power.
    :ivar pre_event_active_power_pu: Active-power parameter before the event.
    :ivar pre_event_reactive_power_pu: Reactive-power parameter before the event.
    :ivar post_event_active_power_pu: Active-power parameter after the event.
    :ivar event_group_name: Stable name of the RMS event group.
    :ivar force_step_alignment: Whether the RMS solver must land on the event.
    :ivar voltage_response_threshold_pu: Minimum conclusive voltage response.
    :ivar active_power_response_threshold_pu: Minimum conclusive power response.
    """

    __slots__ = (
        "time_step_seconds",
        "stop_time_seconds",
        "event_time_seconds",
        "event_boundary_index",
        "first_post_event_index",
        "first_post_event_time_seconds",
        "sample_count",
        "disturbance_load_initial_active_power_mw",
        "disturbance_load_initial_reactive_power_mvar",
        "pre_event_active_power_pu",
        "pre_event_reactive_power_pu",
        "post_event_active_power_pu",
        "event_group_name",
        "force_step_alignment",
        "voltage_response_threshold_pu",
        "active_power_response_threshold_pu",
    )

    time_step_seconds: float
    stop_time_seconds: float
    event_time_seconds: float
    event_boundary_index: int
    first_post_event_index: int
    first_post_event_time_seconds: float
    sample_count: int
    disturbance_load_initial_active_power_mw: float
    disturbance_load_initial_reactive_power_mvar: float
    pre_event_active_power_pu: float
    pre_event_reactive_power_pu: float
    post_event_active_power_pu: float
    event_group_name: str
    force_step_alignment: bool
    voltage_response_threshold_pu: float
    active_power_response_threshold_pu: float

    def __init__(
        self,
        time_step_seconds: float,
        stop_time_seconds: float,
        event_time_seconds: float,
        disturbance_load_initial_active_power_mw: float,
        disturbance_load_initial_reactive_power_mvar: float,
        pre_event_active_power_pu: float,
        pre_event_reactive_power_pu: float,
        post_event_active_power_pu: float,
        event_group_name: str,
        force_step_alignment: bool,
        voltage_response_threshold_pu: float,
        active_power_response_threshold_pu: float,
    ) -> None:
        """Validate and construct one RMS load active-power step scenario.

        :param time_step_seconds: Uniform communication step in seconds.
        :param stop_time_seconds: Inclusive simulation stop time in seconds.
        :param event_time_seconds: Accepted pre-event boundary in seconds.
        :param disturbance_load_initial_active_power_mw: Static active power in MW.
        :param disturbance_load_initial_reactive_power_mvar: Static reactive power in MVAr.
        :param pre_event_active_power_pu: Active-power parameter before the event.
        :param pre_event_reactive_power_pu: Reactive-power parameter before the event.
        :param post_event_active_power_pu: Active-power parameter after the event.
        :param event_group_name: Stable RMS event-group name.
        :param force_step_alignment: Whether to force the solver onto the event.
        :param voltage_response_threshold_pu: Minimum conclusive voltage response.
        :param active_power_response_threshold_pu: Minimum conclusive power response.
        :return: None.
        """

        # Reject bool explicitly because it is an int subclass but never a
        # meaningful physical value.  Conversion happens once after this gate.
        numerical_values: tuple[object, ...] = (
            time_step_seconds,
            stop_time_seconds,
            event_time_seconds,
            disturbance_load_initial_active_power_mw,
            disturbance_load_initial_reactive_power_mvar,
            pre_event_active_power_pu,
            pre_event_reactive_power_pu,
            post_event_active_power_pu,
            voltage_response_threshold_pu,
            active_power_response_threshold_pu,
        )
        numerical_values_are_scalars: bool = all(
            isinstance(numerical_value, (int, float))
            and not isinstance(numerical_value, bool)
            for numerical_value in numerical_values
        )
        if numerical_values_are_scalars:
            pass
        else:
            raise ValueError("RMS load-step numerical values must be real scalars")

        validated_time_step_seconds: float = float(time_step_seconds)
        validated_stop_time_seconds: float = float(stop_time_seconds)
        validated_event_time_seconds: float = float(event_time_seconds)
        validated_initial_active_power_mw: float = float(
            disturbance_load_initial_active_power_mw
        )
        validated_initial_reactive_power_mvar: float = float(
            disturbance_load_initial_reactive_power_mvar
        )
        validated_pre_event_active_power_pu: float = float(
            pre_event_active_power_pu
        )
        validated_pre_event_reactive_power_pu: float = float(
            pre_event_reactive_power_pu
        )
        validated_post_event_active_power_pu: float = float(
            post_event_active_power_pu
        )
        validated_voltage_response_threshold_pu: float = float(
            voltage_response_threshold_pu
        )
        validated_active_power_response_threshold_pu: float = float(
            active_power_response_threshold_pu
        )
        validated_numerical_values: tuple[float, ...] = (
            validated_time_step_seconds,
            validated_stop_time_seconds,
            validated_event_time_seconds,
            validated_initial_active_power_mw,
            validated_initial_reactive_power_mvar,
            validated_pre_event_active_power_pu,
            validated_pre_event_reactive_power_pu,
            validated_post_event_active_power_pu,
            validated_voltage_response_threshold_pu,
            validated_active_power_response_threshold_pu,
        )
        numerical_values_are_finite: bool = all(
            math.isfinite(numerical_value)
            for numerical_value in validated_numerical_values
        )
        if numerical_values_are_finite:
            pass
        else:
            raise ValueError("RMS load-step numerical values must be finite")

        # A step greater than twice the absolute alignment tolerance makes the
        # accepted nearest lattice point unique.
        temporal_domain_is_valid: bool = bool(
            validated_time_step_seconds > 2.0e-12
            and validated_stop_time_seconds > 0.0
            and validated_event_time_seconds > 0.0
            and validated_event_time_seconds < validated_stop_time_seconds
        )
        if temporal_domain_is_valid:
            pass
        else:
            raise ValueError("RMS load-step temporal values are out of range")

        # Validate ratios before integerization so extreme finite inputs fail
        # deterministically instead of reaching round with infinity.
        stop_ratio: float = (
            validated_stop_time_seconds / validated_time_step_seconds
        )
        event_ratio: float = (
            validated_event_time_seconds / validated_time_step_seconds
        )
        temporal_ratios_are_finite: bool = bool(
            math.isfinite(stop_ratio) and math.isfinite(event_ratio)
        )
        if temporal_ratios_are_finite:
            pass
        else:
            raise ValueError("RMS load-step temporal ratios must be finite")

        stop_interval_count: int = int(round(stop_ratio))
        event_boundary_index: int = int(round(event_ratio))
        stop_alignment_error_seconds: float = abs(
            stop_interval_count * validated_time_step_seconds
            - validated_stop_time_seconds
        )
        event_alignment_error_seconds: float = abs(
            event_boundary_index * validated_time_step_seconds
            - validated_event_time_seconds
        )
        sample_count: int = stop_interval_count + 1
        maximum_sample_count: int = 1_000_001
        lattice_is_valid: bool = bool(
            stop_alignment_error_seconds <= 1.0e-12
            and event_alignment_error_seconds <= 1.0e-12
            and stop_interval_count >= 2
            and event_boundary_index >= 1
            and event_boundary_index < stop_interval_count
            and sample_count <= maximum_sample_count
        )
        if lattice_is_valid:
            pass
        else:
            raise ValueError("RMS load-step time lattice is invalid")

        descriptive_values_are_valid: bool = bool(
            isinstance(event_group_name, str)
            and bool(event_group_name.strip())
            and isinstance(force_step_alignment, bool)
        )
        physical_values_are_valid: bool = bool(
            validated_initial_active_power_mw >= 0.0
            and validated_initial_reactive_power_mvar >= 0.0
            and validated_pre_event_active_power_pu
            != validated_post_event_active_power_pu
            and validated_voltage_response_threshold_pu > 0.0
            and validated_active_power_response_threshold_pu > 0.0
        )
        if descriptive_values_are_valid and physical_values_are_valid:
            pass
        else:
            raise ValueError("RMS load-step physical values are invalid")

        first_post_event_index: int = event_boundary_index + 1
        first_post_event_time_seconds: float = (
            first_post_event_index * validated_time_step_seconds
        )

        # Publish the validated state only after every independent input and
        # derived lattice invariant has passed.
        self.time_step_seconds: float = validated_time_step_seconds
        self.stop_time_seconds: float = validated_stop_time_seconds
        self.event_time_seconds: float = validated_event_time_seconds
        self.event_boundary_index: int = event_boundary_index
        self.first_post_event_index: int = first_post_event_index
        self.first_post_event_time_seconds: float = (
            first_post_event_time_seconds
        )
        self.sample_count: int = sample_count
        self.disturbance_load_initial_active_power_mw: float = (
            validated_initial_active_power_mw
        )
        self.disturbance_load_initial_reactive_power_mvar: float = (
            validated_initial_reactive_power_mvar
        )
        self.pre_event_active_power_pu: float = (
            validated_pre_event_active_power_pu
        )
        self.pre_event_reactive_power_pu: float = (
            validated_pre_event_reactive_power_pu
        )
        self.post_event_active_power_pu: float = (
            validated_post_event_active_power_pu
        )
        self.event_group_name: str = event_group_name.strip()
        self.force_step_alignment: bool = force_step_alignment
        self.voltage_response_threshold_pu: float = (
            validated_voltage_response_threshold_pu
        )
        self.active_power_response_threshold_pu: float = (
            validated_active_power_response_threshold_pu
        )

    def copy_validated(self) -> RmsLoadPowerStepScenario:
        """Build an independent scenario through the canonical validation path.

        :return: New scenario containing the same validated independent inputs.
        """

        # Reconstruct from independent inputs so every derived lattice field is
        # recomputed and any caller mutation is checked again at the boundary.
        return RmsLoadPowerStepScenario(
            time_step_seconds=self.time_step_seconds,
            stop_time_seconds=self.stop_time_seconds,
            event_time_seconds=self.event_time_seconds,
            disturbance_load_initial_active_power_mw=(
                self.disturbance_load_initial_active_power_mw
            ),
            disturbance_load_initial_reactive_power_mvar=(
                self.disturbance_load_initial_reactive_power_mvar
            ),
            pre_event_active_power_pu=self.pre_event_active_power_pu,
            pre_event_reactive_power_pu=self.pre_event_reactive_power_pu,
            post_event_active_power_pu=self.post_event_active_power_pu,
            event_group_name=self.event_group_name,
            force_step_alignment=self.force_step_alignment,
            voltage_response_threshold_pu=self.voltage_response_threshold_pu,
            active_power_response_threshold_pu=(
                self.active_power_response_threshold_pu
            ),
        )

    def build_time_lattice(self) -> np.ndarray:
        """Build a new inclusive time lattice for one comparison consumer.

        :return: Independent finite floating-point time array in seconds.
        """

        # A fresh allocation prevents one consumer from changing another
        # consumer's accepted sample locations.
        time_lattice: np.ndarray = (
            np.arange(self.sample_count, dtype=float) * self.time_step_seconds
        )
        return time_lattice

    def build_manifest_event_record(self) -> dict[str, object]:
        """Build the unchanged schema-v3 RMS event evidence record.

        :return: Event mapping consumed by the comparison manifest producer.
        """

        # Fixed strings describe this one maintained evidence case.  They stay
        # at the serialization boundary instead of becoming false taxonomy.
        return dict(
            kind="RMS native load active-power step",
            parameter="Pl0",
            event_time_seconds=self.event_time_seconds,
            event_boundary_index=self.event_boundary_index,
            first_post_event_index=self.first_post_event_index,
            boundary_semantics="old_value_at_boundary_step_after_boundary",
            disturbance_load_initial_active_power_mw=(
                self.disturbance_load_initial_active_power_mw
            ),
            disturbance_load_initial_reactive_power_mvar=(
                self.disturbance_load_initial_reactive_power_mvar
            ),
            pre_event_value_pu=self.pre_event_active_power_pu,
            post_event_value_pu=self.post_event_active_power_pu,
            voltage_response_threshold_pu=self.voltage_response_threshold_pu,
            active_power_response_threshold_pu=(
                self.active_power_response_threshold_pu
            ),
            fmu_active_power_equation="p_out = -0.1 - 2.0*(u - x)",
            fmu_reactive_power_equation="q_out = -0.01 - (u - x)",
            fmu_state_derivative="der(x) = 0",
            fmu_state_initialization="x(0) = u(0)",
            shared_input="u = retained VeraGrid RMS bus voltage magnitude",
        )


def build_default_rms_load_power_step_scenario() -> RmsLoadPowerStepScenario:
    """Build the exact maintained RMS load active-power step scenario.

    :return: Validated scenario with the schema-v3 benchmark values.
    """

    return RmsLoadPowerStepScenario(
        time_step_seconds=1.0e-3,
        stop_time_seconds=3.0e-1,
        event_time_seconds=1.0e-1,
        disturbance_load_initial_active_power_mw=5.0,
        disturbance_load_initial_reactive_power_mvar=1.0,
        pre_event_active_power_pu=-0.05,
        pre_event_reactive_power_pu=-0.01,
        post_event_active_power_pu=-0.15,
        event_group_name="rms_load_step",
        force_step_alignment=True,
        voltage_response_threshold_pu=1.0e-5,
        active_power_response_threshold_pu=1.0e-5,
    )
