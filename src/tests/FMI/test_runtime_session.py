# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Tests for bound FMI 3 scalar consumer sessions."""

from __future__ import annotations

from pathlib import Path
import struct
from unittest.mock import Mock

import pytest

from VeraGridEngine.IO.fmu.Elements.bindings import (
    FmiThreeFloat64SessionValueSelector,
    FmuImportConfig,
    FmuRefBinding,
    resolve_fmi_three_float64_session_value_selectors,
)
from VeraGridEngine.IO.fmu.Elements.protocol import (
    FmiThreeWorkerCompletedIntegratorStepResult,
    FmiThreeWorkerDiscreteStatesResult,
    FmiThreeWorkerDoStepResult,
    validate_fmi_three_worker_float64_frame_capacity,
    validate_fmi_three_worker_initialization_frame_capacity,
)
from VeraGridEngine.IO.fmu.profile import (
    FmiThreeWorkerFloat64Profile,
)
from VeraGridEngine.IO.fmu.coordinator import (
    FmiThreeModelExchangeCoordinator,
)
from VeraGridEngine.IO.fmu.Elements.session import (
    FmiThreeNumericSession,
    open_fmi_three_numeric_session,
)
from VeraGridEngine.IO.fmu.worker_host import (
    FmiThreeWorkerHostLimits,
)
from VeraGridEngine.IO.fmu.model_description import (
    read_fmu_model_description,
)
from VeraGridEngine.IO.fmu.Elements.description import (
    FmuModelDescription,
    FmuVariableDescription,
)
from VeraGridEngine.enumerations import (
    FmuInterfaceMode,
    VarPowerFlowReferenceType,
)


def _create_scalar_session_limits() -> FmiThreeWorkerHostLimits:
    """Create explicit finite limits for scalar-session integration tests.

    Repeated Windows spawn and native-load checks can exceed twenty seconds
    under full-suite load, so this test-only deadline matches the worker tests.

    :return: Complete worker supervision policy owned by this test consumer.
    """

    return FmiThreeWorkerHostLimits(
        maximum_frame_size=262144,
        maximum_float64_values_per_request=64,
        response_timeout_seconds=60.0,
        graceful_join_timeout_seconds=10.0,
        terminate_join_timeout_seconds=5.0,
        kill_join_timeout_seconds=5.0,
    )


def test_compiled_fmi_three_parameterized_configurable_array_fmu_exposes_observable_parameters(
    compiled_fmi_three_parameterized_configurable_array_fmu: Path,
) -> None:
    """Expose fixed and tunable scalar parameters beside the configured array.

    :param compiled_fmi_three_parameterized_configurable_array_fmu: Native
        dual-interface fixture with scalar parameters.
    :return: None.
    """

    metadata: FmuModelDescription = read_fmu_model_description(
        compiled_fmi_three_parameterized_configurable_array_fmu
    )
    fixed_gain: FmuVariableDescription = metadata.get_variable("fixed_gain")
    tunable_bias: FmuVariableDescription = metadata.get_variable("tunable_bias")
    assert fixed_gain.causality == "parameter"
    assert fixed_gain.variability == "fixed"
    assert fixed_gain.initial == "exact"
    assert fixed_gain.start == "2.0"
    assert tunable_bias.causality == "parameter"
    assert tunable_bias.variability == "tunable"
    assert tunable_bias.initial == "exact"
    assert tunable_bias.start == "0.5"


def test_fmi_three_session_initializes_parameters_for_cs_and_me(
    compiled_fmi_three_parameterized_configurable_array_fmu: Path,
    tmp_path: Path,
) -> None:
    """Write parameters during initialization and observe them in CS and ME.

    :param compiled_fmi_three_parameterized_configurable_array_fmu: Native
        dual-interface fixture with scalar parameters.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    initialization_names: tuple[str, ...] = (
        "fixed_gain",
        "tunable_bias",
        "array_input",
    )
    cs_staging_parent: Path = tmp_path / "parameterized-cs-session"
    cs_session: FmiThreeNumericSession = open_fmi_three_numeric_session(
        config=FmuImportConfig(
            fmu_path=compiled_fmi_three_parameterized_configurable_array_fmu,
            extraction_root=cs_staging_parent,
        ),
        instance_name="veragrid-fmi-three-parameterized-cs-session",
        readable_variable_names=("array_output", "time"),
        writable_variable_names=("array_input",),
        initialization_variable_names=initialization_names,
        configuration_uint64_variable_names=("structural_size",),
        limits=_create_scalar_session_limits(),
        float64_profile=FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY,
    )
    try:
        cs_session.configure_uint64(configuration_uint64_values=(3,))
        cs_initial_values: tuple[float, ...] = (
            cs_session.initialize_co_simulation_and_read(
                start_time=0.0,
                stop_time=1.0,
                relative_tolerance=1.0e-6,
                initial_writable_float64_values=(3.0, 1.0, 1.0, 2.0, 3.0),
            )
        )
        assert cs_initial_values == pytest.approx((4.0, 7.0, 10.0, 0.0))
        cs_step_result: FmiThreeWorkerDoStepResult
        cs_readable_values: tuple[float, ...]
        cs_step_result, cs_readable_values = cs_session.advance_co_simulation(
            current_communication_point=0.0,
            communication_step_size=0.25,
            writable_float64_values=(2.0, 4.0, 6.0),
            no_set_fmu_state_prior_to_current_point=True,
        )
        assert cs_step_result.last_successful_time == pytest.approx(0.25)
        assert cs_readable_values == pytest.approx((7.25, 13.25, 19.25, 0.25))
    finally:
        cs_session.close()

    me_staging_parent: Path = tmp_path / "parameterized-me-session"
    me_session: FmiThreeNumericSession = open_fmi_three_numeric_session(
        config=FmuImportConfig(
            fmu_path=compiled_fmi_three_parameterized_configurable_array_fmu,
            preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE,
            extraction_root=me_staging_parent,
        ),
        instance_name="veragrid-fmi-three-parameterized-me-session",
        readable_variable_names=("array_output", "time"),
        writable_variable_names=("array_input",),
        initialization_variable_names=initialization_names,
        configuration_uint64_variable_names=("structural_size",),
        limits=_create_scalar_session_limits(),
        float64_profile=FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY,
    )
    try:
        me_session.configure_uint64(configuration_uint64_values=(3,))
        me_state_values: tuple[float, ...]
        me_initial_values: tuple[float, ...]
        me_state_values, me_initial_values = (
            me_session.initialize_model_exchange_and_read(
                start_time=0.0,
                stop_time=1.0,
                relative_tolerance=1.0e-6,
                initial_writable_float64_values=(4.0, -1.0, 1.0, 2.0, 3.0),
            )
        )
        assert me_state_values == tuple()
        assert me_initial_values == pytest.approx((3.0, 7.0, 11.0, 0.0))
        me_derivatives: tuple[float, ...]
        me_readable_values: tuple[float, ...]
        me_derivatives, me_readable_values = me_session.evaluate_model_exchange(
            time_value=0.5,
            continuous_state_values=tuple(),
            writable_float64_values=(2.0, 3.0, 4.0),
        )
        assert me_derivatives == tuple()
        assert me_readable_values == pytest.approx((7.5, 11.5, 15.5, 0.5))
    finally:
        me_session.close()
    assert tuple(cs_staging_parent.glob("veragrid_fmu_stage_*")) == tuple()
    assert tuple(me_staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmi_three_initialization_layout_recomputes_configurable_cardinality_atomically(
    compiled_fmi_three_parameterized_configurable_array_fmu: Path,
    tmp_path: Path,
) -> None:
    """Reject an oversized prospective initialization layout without mutation.

    :param compiled_fmi_three_parameterized_configurable_array_fmu: Native
        parameterized configurable-array fixture.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "atomic-initialization-layout"
    bounded_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
        maximum_frame_size=262144,
        maximum_float64_values_per_request=6,
        response_timeout_seconds=60.0,
        graceful_join_timeout_seconds=10.0,
        terminate_join_timeout_seconds=5.0,
        kill_join_timeout_seconds=5.0,
    )
    session: FmiThreeNumericSession = open_fmi_three_numeric_session(
        config=FmuImportConfig(
            fmu_path=compiled_fmi_three_parameterized_configurable_array_fmu,
            extraction_root=staging_parent,
        ),
        instance_name="veragrid-fmi-three-atomic-parameter-layout",
        readable_variable_names=("array_output",),
        writable_variable_names=("array_input",),
        initialization_variable_names=(
            "fixed_gain",
            "tunable_bias",
            "array_input",
        ),
        configuration_uint64_variable_names=("structural_size",),
        limits=bounded_limits,
        float64_profile=FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY,
    )
    try:
        with pytest.raises(ValueError, match="serialized value bound"):
            session.configure_uint64(configuration_uint64_values=(7,))
        session.configure_uint64(configuration_uint64_values=(2,))
        initialized_values: tuple[float, ...] = (
            session.initialize_co_simulation_and_read(
                start_time=0.0,
                stop_time=1.0,
                relative_tolerance=1.0e-6,
                initial_writable_float64_values=(2.0, 0.5, 1.0, 2.0),
            )
        )
        assert initialized_values == pytest.approx((2.5, 4.5))
    finally:
        session.close()
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmi_three_initialization_frame_capacity_rejects_limit_plus_one_without_start() -> None:
    """Accept the exact INITIALIZE frame and reject a one-byte-smaller bound.

    :return: None.
    """

    value_reference_count: int = 3
    serialized_value_count: int = 5
    exact_frame_size: int = (
        struct.calcsize("!4sBBBQI")
        + struct.calcsize("!Bddd")
        + 16
        + value_reference_count * 4
        + serialized_value_count * 8
    )
    validate_fmi_three_worker_initialization_frame_capacity(
        float64_value_reference_count=value_reference_count,
        float64_serialized_value_count=serialized_value_count,
        int32_value_reference_count=0,
        int32_value_count=0,
        maximum_frame_size=exact_frame_size,
        maximum_value_count=64,
    )
    with pytest.raises(ValueError, match="exceeds the frame bound"):
        validate_fmi_three_worker_initialization_frame_capacity(
            float64_value_reference_count=value_reference_count,
            float64_serialized_value_count=serialized_value_count,
            int32_value_reference_count=0,
            int32_value_count=0,
            maximum_frame_size=exact_frame_size - 1,
            maximum_value_count=64,
        )


def _open_float64_session(
    compiled_fmu_path: Path,
    staging_parent: Path,
    float64_profile: FmiThreeWorkerFloat64Profile,
    interface_mode: FmuInterfaceMode = FmuInterfaceMode.CO_SIMULATION,
    early_return_allowed: bool = False,
) -> FmiThreeNumericSession:
    """Open the generated fixture with deliberately non-source ordering.

    :param compiled_fmu_path: Generated host-native FMI 3 fixture.
    :param staging_parent: Test-owned parent for private staging.
    :param float64_profile: Worker value profile exercised by the caller.
    :param interface_mode: FMI 3 interface selected for the child instance.
    :param early_return_allowed: Whether this test consumer accepts partial steps.
    :return: Started session with one writable and three readable bindings.
    """

    config: FmuImportConfig = FmuImportConfig(
        fmu_path=compiled_fmu_path,
        preferred_mode=interface_mode,
        extraction_root=staging_parent,
    )
    return open_fmi_three_numeric_session(
        config=config,
        instance_name="veragrid-fmi-three-bound-session",
        readable_variable_names=(
            "observed_output",
            "time",
            "control_input",
        ),
        writable_variable_names=("control_input",),
        limits=_create_scalar_session_limits(),
        float64_profile=float64_profile,
        early_return_allowed=early_return_allowed,
    )


def test_numeric_session_initializes_and_reads_int32_without_second_worker(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Use one numeric session for Float64 and scalar Int32 lifecycle calls.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native
        scalar test FMU.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "numeric-int32-session"
    session: FmiThreeNumericSession = open_fmi_three_numeric_session(
        config=FmuImportConfig(
            fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
            extraction_root=staging_parent,
        ),
        instance_name="veragrid-fmi-three-numeric-int32-session",
        readable_variable_names=("observed_output", "time"),
        writable_variable_names=("control_input",),
        limits=_create_scalar_session_limits(),
        float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
        readable_int32_variable_names=("integer_output", "integer_input"),
        writable_int32_variable_names=("integer_input",),
    )
    try:
        initial_float64_values: tuple[float, ...] = (
            session.initialize_co_simulation_and_read(
                start_time=0.0,
                stop_time=1.0,
                relative_tolerance=1.0e-6,
                initial_writable_float64_values=(2.0,),
                initial_writable_int32_values=(-2,),
            )
        )
        assert initial_float64_values == pytest.approx((0.0, 0.0))
        assert session.read_int32_values() == (0, -2)

        step_result: FmiThreeWorkerDoStepResult
        readable_float64_values: tuple[float, ...]
        step_result, readable_float64_values = session.advance_co_simulation(
            current_communication_point=0.0,
            communication_step_size=0.25,
            writable_float64_values=(3.0,),
            no_set_fmu_state_prior_to_current_point=True,
            writable_int32_values=(-5,),
        )
        assert step_result.last_successful_time == pytest.approx(0.25)
        assert readable_float64_values == pytest.approx((3.25, 0.25))
        assert session.read_int32_values() == (-5, -5)
    finally:
        session.close()
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_numeric_session_preserves_float64_array_behavior(
    compiled_fmi_three_constant_array_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Preserve row-major Float64 arrays after generalizing the session owner.

    :param compiled_fmi_three_constant_array_co_simulation_fmu: Native array FMU.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "numeric-array-regression"
    session: FmiThreeNumericSession = open_fmi_three_numeric_session(
        config=FmuImportConfig(
            fmu_path=compiled_fmi_three_constant_array_co_simulation_fmu,
            extraction_root=staging_parent,
        ),
        instance_name="veragrid-fmi-three-numeric-array-regression",
        readable_variable_names=("array_output",),
        writable_variable_names=("array_input",),
        limits=_create_scalar_session_limits(),
        float64_profile=FmiThreeWorkerFloat64Profile.CONSTANT_ARRAY,
    )
    initial_values: tuple[float, ...] = (0.0, 0.1, 1.0, 1.1, 2.0, 2.1)
    step_values: tuple[float, ...] = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    try:
        assert session.initialize_co_simulation_and_read(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_writable_float64_values=initial_values,
        ) == pytest.approx((0.0,) * 6)
        step_result: FmiThreeWorkerDoStepResult
        readable_values: tuple[float, ...]
        step_result, readable_values = session.advance_co_simulation(
            current_communication_point=0.0,
            communication_step_size=0.25,
            writable_float64_values=step_values,
            no_set_fmu_state_prior_to_current_point=True,
        )
        assert step_result.last_successful_time == pytest.approx(0.25)
        assert readable_values == pytest.approx(
            (1.25, 2.25, 3.25, 4.25, 5.25, 6.25)
        )
        assert session.read_int32_values() == tuple()
    finally:
        session.close()
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmi_three_scalar_session_runs_ordered_consumer_operations(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Resolve names once and run initialization plus two complete consumer steps.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated native fixture.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "ordered-session"
    session: FmiThreeNumericSession = _open_float64_session(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        staging_parent=staging_parent,
        float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
    )
    try:
        assert session.supports_fmu_state_checkpoint()
        assert not session.supports_serialized_fmu_state()
        with pytest.raises(RuntimeError, match="requires Model Exchange"):
            session.needs_completed_integrator_step()
        initialized_values: tuple[float, ...] = session.initialize_co_simulation_and_read(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_writable_float64_values=(2.0,),
        )
        assert initialized_values == pytest.approx((0.0, 0.0, 2.0))
        session.save_checkpoint()

        first_result: FmiThreeWorkerDoStepResult
        first_values: tuple[float, ...]
        first_result, first_values = session.advance_co_simulation(
            current_communication_point=0.0,
            communication_step_size=0.25,
            writable_float64_values=(2.0,),
            no_set_fmu_state_prior_to_current_point=False,
        )
        assert not first_result.terminate_simulation
        assert first_result.last_successful_time == pytest.approx(0.25)
        assert first_values == pytest.approx((2.25, 0.25, 2.0))
        session.restore_checkpoint()

        repeated_first_result: FmiThreeWorkerDoStepResult
        repeated_first_values: tuple[float, ...]
        repeated_first_result, repeated_first_values = session.advance_co_simulation(
            current_communication_point=0.0,
            communication_step_size=0.25,
            writable_float64_values=(2.0,),
            no_set_fmu_state_prior_to_current_point=False,
        )
        assert repeated_first_result.last_successful_time == pytest.approx(0.25)
        assert repeated_first_values == pytest.approx(first_values)
        session.discard_checkpoint()

        second_result: FmiThreeWorkerDoStepResult
        second_values: tuple[float, ...]
        second_result, second_values = session.advance_co_simulation(
            current_communication_point=0.25,
            communication_step_size=0.25,
            writable_float64_values=(-1.0,),
            no_set_fmu_state_prior_to_current_point=True,
        )
        assert second_result.last_successful_time == pytest.approx(0.5)
        assert second_values == pytest.approx((-0.5, 0.5, -1.0))
    finally:
        session.close()
        session.close()

    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmi_three_float64_session_disables_early_return_by_default(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Keep the native FMU on the complete-step path without explicit opt-in.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated native fixture.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "early-return-disabled-session"
    session: FmiThreeNumericSession = _open_float64_session(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        staging_parent=staging_parent,
        float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
    )
    try:
        session.initialize_co_simulation_and_read(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_writable_float64_values=(8.0,),
        )
        step_result: FmiThreeWorkerDoStepResult
        readable_values: tuple[float, ...]
        step_result, readable_values = session.advance_co_simulation(
            current_communication_point=0.0,
            communication_step_size=0.25,
            writable_float64_values=(8.0,),
            no_set_fmu_state_prior_to_current_point=True,
        )
        assert not step_result.early_return
        assert step_result.last_successful_time == pytest.approx(0.25)
        assert readable_values == pytest.approx((8.25, 0.25, 8.0))
    finally:
        session.close()
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmi_three_float64_session_resumes_after_negotiated_early_return(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Resume from native partial time and finish the original target interval.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated native fixture.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "early-return-enabled-session"
    session: FmiThreeNumericSession = _open_float64_session(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        staging_parent=staging_parent,
        float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
        early_return_allowed=True,
    )
    try:
        session.initialize_co_simulation_and_read(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_writable_float64_values=(8.0,),
        )
        partial_result: FmiThreeWorkerDoStepResult
        partial_values: tuple[float, ...]
        partial_result, partial_values = session.advance_co_simulation(
            current_communication_point=0.0,
            communication_step_size=0.25,
            writable_float64_values=(8.0,),
            no_set_fmu_state_prior_to_current_point=True,
        )
        assert partial_result.early_return
        assert partial_result.last_successful_time == pytest.approx(0.0)
        assert partial_values == pytest.approx((8.0, 0.0, 8.0))

        completed_result: FmiThreeWorkerDoStepResult
        completed_values: tuple[float, ...]
        completed_result, completed_values = session.advance_co_simulation(
            current_communication_point=partial_result.last_successful_time,
            communication_step_size=0.25,
            writable_float64_values=(2.0,),
            no_set_fmu_state_prior_to_current_point=True,
        )
        assert not completed_result.early_return
        assert completed_result.last_successful_time == pytest.approx(0.25)
        assert completed_values == pytest.approx((2.25, 0.25, 2.0))
    finally:
        session.close()
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmi_three_model_exchange_session_evaluates_without_integrating(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Expose bounded ME evaluation while retaining solver ownership outside.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated dual-interface
        native fixture.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "model-exchange-session"
    session: FmiThreeNumericSession = _open_float64_session(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        staging_parent=staging_parent,
        float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
        interface_mode=FmuInterfaceMode.MODEL_EXCHANGE,
    )
    try:
        assert session.supports_fmu_state_checkpoint()
        assert not session.supports_serialized_fmu_state()
        assert session.needs_completed_integrator_step()
        state_values: tuple[float, ...]
        initialized_values: tuple[float, ...]
        state_values, initialized_values = (
            session.initialize_model_exchange_and_read(
                start_time=0.0,
                stop_time=1.0,
                relative_tolerance=1.0e-6,
                initial_writable_float64_values=(2.0,),
            )
        )
        assert state_values == pytest.approx((1.0,))
        assert initialized_values == pytest.approx((0.0, 0.0, 2.0))
        session.save_checkpoint()

        derivative_values: tuple[float, ...]
        readable_values: tuple[float, ...]
        derivative_values, readable_values = session.evaluate_model_exchange(
            time_value=0.25,
            continuous_state_values=(3.0,),
            writable_float64_values=(2.0,),
        )
        assert derivative_values == pytest.approx((-1.0,))
        assert session.get_model_exchange_event_indicators() == pytest.approx(
            (0.5,)
        )
        assert (
            session.get_model_exchange_continuous_state_nominals()
            == pytest.approx((1.0,))
        )
        # Model Exchange evaluates the derivative without manufacturing the
        # Co-Simulation-only observed-output update performed by doStep.
        assert readable_values == pytest.approx((0.0, 0.25, 2.0))
        session.restore_checkpoint()
        restored_states: tuple[float, ...]
        restored_values: tuple[float, ...]
        restored_states, restored_values = (
            session.read_model_exchange_state_and_values()
        )
        assert restored_states == pytest.approx((1.0,))
        assert restored_values == pytest.approx((0.0, 0.0, 2.0))
        session.discard_checkpoint()
        completed_result: FmiThreeWorkerCompletedIntegratorStepResult = (
            session.complete_model_exchange_integrator_step(
                no_set_fmu_state_prior_to_current_point=True
            )
        )
        assert not completed_result.enter_event_mode
        assert not completed_result.terminate_simulation
        with pytest.raises(RuntimeError, match="requires Co-Simulation"):
            session.advance_co_simulation(
                current_communication_point=0.25,
                communication_step_size=0.1,
                writable_float64_values=(2.0,),
                no_set_fmu_state_prior_to_current_point=True,
            )
    finally:
        session.close()
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmi_three_model_exchange_coordinator_resolves_candidates_and_events(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Coordinate acceptance, rollback, and bounded Event Mode without solving.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated dual-interface
        native fixture.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "model-exchange-coordinator"
    session: FmiThreeNumericSession = _open_float64_session(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        staging_parent=staging_parent,
        float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
        interface_mode=FmuInterfaceMode.MODEL_EXCHANGE,
    )
    coordinator: FmiThreeModelExchangeCoordinator = (
        FmiThreeModelExchangeCoordinator(
            session=session,
            maximum_event_iterations=4,
        )
    )
    try:
        initialized_states: tuple[float, ...]
        initialized_values: tuple[float, ...]
        initialized_states, initialized_values = coordinator.initialize(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_writable_values=(2.0,),
        )
        assert coordinator.supports_rollback()
        assert initialized_states == pytest.approx((1.0,))
        assert initialized_values == pytest.approx((0.0, 0.0, 2.0))
        accepted_point = coordinator.get_accepted_point()
        assert accepted_point[0] == pytest.approx(0.0)
        assert accepted_point[1] == pytest.approx((1.0,))

        probe_derivatives: tuple[float, ...]
        probe_values: tuple[float, ...]
        probe_derivatives, probe_values = coordinator.evaluate_probe(
            time_value=0.0,
            continuous_state_values=(1.0,),
            writable_values=(2.0,),
        )
        assert probe_derivatives == pytest.approx((1.0,))
        assert probe_values == pytest.approx((0.0, 0.0, 2.0))
        assert not coordinator.has_pending_candidate()
        assert coordinator.get_accepted_point()[1] == pytest.approx((1.0,))

        derivative_values: tuple[float, ...]
        readable_values: tuple[float, ...]
        event_indicators: tuple[float, ...]
        derivative_values, readable_values, event_indicators = (
            coordinator.evaluate_candidate(
                time_value=0.25,
                continuous_state_values=(3.0,),
                writable_values=(2.0,),
            )
        )
        assert derivative_values == pytest.approx((-1.0,))
        assert readable_values == pytest.approx((0.0, 0.25, 2.0))
        assert event_indicators == pytest.approx((0.5,))
        assert coordinator.has_pending_candidate()
        assert coordinator.get_accepted_point()[1] == pytest.approx((1.0,))
        coordinator.reject_candidate()
        assert not coordinator.has_pending_candidate()

        coordinator.evaluate_candidate(
            time_value=0.25,
            continuous_state_values=(3.0,),
            writable_values=(2.0,),
        )
        accepted_states: tuple[float, ...]
        accepted_values: tuple[float, ...]
        accepted_states, accepted_values = coordinator.accept_candidate(
            importer_detected_event=False
        )
        assert accepted_states == pytest.approx((3.0,))
        assert accepted_values == pytest.approx((0.0, 0.25, 2.0))

        # Input 9 makes completedIntegratorStep request Event Mode. The native
        # fixture then needs two discrete-state iterations and increments state.
        coordinator.evaluate_candidate(
            time_value=0.5,
            continuous_state_values=(4.0,),
            writable_values=(9.0,),
        )
        accepted_states, accepted_values = coordinator.accept_candidate(
            importer_detected_event=False
        )
        assert accepted_states == pytest.approx((5.0,))
        assert accepted_values == pytest.approx((0.0, 0.5, 9.0))
        assert coordinator.get_accepted_point()[0] == pytest.approx(0.5)

        # A solver-localized event enters Event Mode even without an FMU request.
        coordinator.evaluate_candidate(
            time_value=0.75,
            continuous_state_values=(6.0,),
            writable_values=(2.0,),
        )
        accepted_states, accepted_values = coordinator.accept_candidate(
            importer_detected_event=True
        )
        assert accepted_states == pytest.approx((6.0,))
        assert accepted_values == pytest.approx((0.0, 0.75, 2.0))
        coordinator.reject_candidate()
        restored_point = coordinator.get_accepted_point()
        assert restored_point[0] == pytest.approx(0.75)
        assert restored_point[1] == pytest.approx((6.0,))
    finally:
        coordinator.close()
        coordinator.close()
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmi_three_model_exchange_coordinator_bounds_event_iterations(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Fail closed when an FMU exceeds the caller-owned Event Mode bound.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated dual-interface
        native fixture.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    rejected_bound: object
    for rejected_bound in (True, False, 0, 1025):
        rejected_session: Mock = Mock()
        with pytest.raises(ValueError, match="between 1 and 1024"):
            FmiThreeModelExchangeCoordinator(
                session=rejected_session,
                maximum_event_iterations=rejected_bound,
            )
        rejected_session.assert_not_called()

    accepted_bound: int
    for accepted_bound in (1, 1024):
        accepted_session: Mock = Mock()
        accepted_session.supports_fmu_state_checkpoint.return_value = True
        accepted_coordinator: FmiThreeModelExchangeCoordinator = (
            FmiThreeModelExchangeCoordinator(
                session=accepted_session,
                maximum_event_iterations=accepted_bound,
            )
        )
        assert accepted_coordinator._maximum_event_iterations == accepted_bound

    staging_parent: Path = tmp_path / "model-exchange-event-bound"
    session: FmiThreeNumericSession = _open_float64_session(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        staging_parent=staging_parent,
        float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
        interface_mode=FmuInterfaceMode.MODEL_EXCHANGE,
    )
    coordinator: FmiThreeModelExchangeCoordinator = (
        FmiThreeModelExchangeCoordinator(
            session=session,
            maximum_event_iterations=1,
        )
    )
    try:
        coordinator.initialize(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_writable_values=(2.0,),
        )
        coordinator.evaluate_candidate(
            time_value=0.25,
            continuous_state_values=(3.0,),
            writable_values=(9.0,),
        )
        with pytest.raises(RuntimeError, match="exceeded its iteration bound"):
            coordinator.accept_candidate(importer_detected_event=False)
        assert coordinator.has_pending_candidate()
        coordinator.reject_candidate()
        assert coordinator.get_accepted_point()[1] == pytest.approx((1.0,))
    finally:
        coordinator.close()
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmi_three_model_exchange_rejects_nonprogressing_time_events() -> None:
    """Validate nextEventTime against each exact Event Mode entry time."""

    invalid_initial_time: float
    for invalid_initial_time in (0.0, -1.0, float("nan"), float("inf")):
        initial_session: Mock = Mock()
        initial_session.supports_fmu_state_checkpoint.return_value = True
        initial_result: FmiThreeWorkerDiscreteStatesResult = (
            FmiThreeWorkerDiscreteStatesResult(
                discrete_states_need_update=False,
                terminate_simulation=False,
                nominals_of_continuous_states_changed=False,
                values_of_continuous_states_changed=False,
                next_event_time_defined=True,
                next_event_time=0.0,
            )
        )
        initial_result.next_event_time = invalid_initial_time
        initial_session.update_model_exchange_discrete_states.return_value = (
            initial_result
        )
        initial_coordinator: FmiThreeModelExchangeCoordinator = (
            FmiThreeModelExchangeCoordinator(
                session=initial_session,
                maximum_event_iterations=4,
            )
        )
        with pytest.raises(RuntimeError, match="follow Event Mode entry"):
            initial_coordinator.initialize(
                start_time=0.0,
                stop_time=3.0,
                relative_tolerance=1.0e-6,
                initial_writable_values=tuple(),
            )
        initial_session.enter_model_exchange_continuous_time_mode.assert_not_called()
        initial_session.save_checkpoint.assert_not_called()

    invalid_candidate_time: float
    for invalid_candidate_time in (1.0, 0.5, float("nan"), float("inf")):
        candidate_session: Mock = Mock()
        candidate_session.supports_fmu_state_checkpoint.return_value = True
        accepted_discrete_result: FmiThreeWorkerDiscreteStatesResult = (
            FmiThreeWorkerDiscreteStatesResult(
                discrete_states_need_update=False,
                terminate_simulation=False,
                nominals_of_continuous_states_changed=False,
                values_of_continuous_states_changed=False,
                next_event_time_defined=False,
                next_event_time=0.0,
            )
        )
        rejected_discrete_result: FmiThreeWorkerDiscreteStatesResult = (
            FmiThreeWorkerDiscreteStatesResult(
                discrete_states_need_update=False,
                terminate_simulation=False,
                nominals_of_continuous_states_changed=False,
                values_of_continuous_states_changed=False,
                next_event_time_defined=True,
                next_event_time=0.0,
            )
        )
        rejected_discrete_result.next_event_time = invalid_candidate_time
        candidate_session.update_model_exchange_discrete_states.side_effect = (
            accepted_discrete_result,
            rejected_discrete_result,
        )
        candidate_session.read_model_exchange_state_and_values.return_value = (
            tuple(),
            tuple(),
        )
        candidate_session.get_model_exchange_event_indicators.return_value = tuple()
        candidate_session.get_model_exchange_continuous_state_nominals.return_value = (
            tuple()
        )
        candidate_session.evaluate_model_exchange.return_value = (
            tuple(),
            tuple(),
        )
        candidate_session.complete_model_exchange_integrator_step.return_value = (
            FmiThreeWorkerCompletedIntegratorStepResult(
                enter_event_mode=True,
                terminate_simulation=False,
            )
        )
        candidate_coordinator: FmiThreeModelExchangeCoordinator = (
            FmiThreeModelExchangeCoordinator(
                session=candidate_session,
                maximum_event_iterations=4,
            )
        )
        candidate_coordinator.initialize(
            start_time=0.0,
            stop_time=3.0,
            relative_tolerance=1.0e-6,
            initial_writable_values=tuple(),
        )
        candidate_coordinator.evaluate_candidate(
            time_value=1.0,
            continuous_state_values=tuple(),
            writable_values=tuple(),
        )
        with pytest.raises(RuntimeError, match="follow Event Mode entry"):
            candidate_coordinator.accept_candidate(importer_detected_event=False)
        assert candidate_session.save_checkpoint.call_count == 1

    future_session: Mock = Mock()
    future_session.supports_fmu_state_checkpoint.return_value = True
    future_session.update_model_exchange_discrete_states.side_effect = (
        FmiThreeWorkerDiscreteStatesResult(
            discrete_states_need_update=False,
            terminate_simulation=False,
            nominals_of_continuous_states_changed=False,
            values_of_continuous_states_changed=False,
            next_event_time_defined=False,
            next_event_time=0.0,
        ),
        FmiThreeWorkerDiscreteStatesResult(
            discrete_states_need_update=False,
            terminate_simulation=False,
            nominals_of_continuous_states_changed=False,
            values_of_continuous_states_changed=False,
            next_event_time_defined=True,
            next_event_time=2.0,
        ),
    )
    future_session.read_model_exchange_state_and_values.return_value = (
        tuple(),
        tuple(),
    )
    future_session.get_model_exchange_event_indicators.return_value = tuple()
    future_session.get_model_exchange_continuous_state_nominals.return_value = tuple()
    future_session.evaluate_model_exchange.return_value = (tuple(), tuple())
    future_session.complete_model_exchange_integrator_step.return_value = (
        FmiThreeWorkerCompletedIntegratorStepResult(
            enter_event_mode=True,
            terminate_simulation=False,
        )
    )
    future_coordinator: FmiThreeModelExchangeCoordinator = (
        FmiThreeModelExchangeCoordinator(
            session=future_session,
            maximum_event_iterations=4,
        )
    )
    future_coordinator.initialize(
        start_time=0.0,
        stop_time=3.0,
        relative_tolerance=1.0e-6,
        initial_writable_values=tuple(),
    )
    future_coordinator.evaluate_candidate(
        time_value=1.0,
        continuous_state_values=tuple(),
        writable_values=tuple(),
    )
    future_coordinator.accept_candidate(importer_detected_event=False)
    assert future_coordinator.get_next_event_time() == pytest.approx(2.0)


def test_fmi_three_model_exchange_accepts_optional_checkpoint_absence() -> None:
    """Construct the coordinator without invoking an optional checkpoint API."""

    session: Mock = Mock()
    session.supports_fmu_state_checkpoint.return_value = False

    coordinator: FmiThreeModelExchangeCoordinator = (
        FmiThreeModelExchangeCoordinator(
            session=session,
            maximum_event_iterations=4,
        )
    )

    assert not coordinator.supports_rollback()
    session.initialize_model_exchange.assert_not_called()
    session.evaluate_model_exchange.assert_not_called()
    session.save_checkpoint.assert_not_called()
    session.restore_checkpoint.assert_not_called()


def test_fmi_three_model_exchange_reconstructs_without_optional_checkpoint(
    compiled_fmi_three_scalar_model_exchange_without_checkpoint_fmu: Path,
    tmp_path: Path,
) -> None:
    """Reject a candidate by exact visible reconstruction without checkpoints.

    :param compiled_fmi_three_scalar_model_exchange_without_checkpoint_fmu:
        Scalar Model Exchange fixture declaring no checkpoint support.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "model-exchange-no-checkpoint-reconstruction"
    session: FmiThreeNumericSession = _open_float64_session(
        compiled_fmu_path=(
            compiled_fmi_three_scalar_model_exchange_without_checkpoint_fmu
        ),
        staging_parent=staging_parent,
        float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
        interface_mode=FmuInterfaceMode.MODEL_EXCHANGE,
    )
    coordinator: FmiThreeModelExchangeCoordinator = (
        FmiThreeModelExchangeCoordinator(
            session=session,
            maximum_event_iterations=4,
        )
    )
    try:
        initialized_states: tuple[float, ...]
        initialized_values: tuple[float, ...]
        initialized_states, initialized_values = coordinator.initialize(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_writable_values=(2.0,),
        )
        assert not coordinator.supports_rollback()
        assert initialized_states == pytest.approx((1.0,))
        assert initialized_values == pytest.approx((0.0, 0.0, 2.0))
        coordinator.evaluate_candidate(
            time_value=0.25,
            continuous_state_values=(1.25,),
            writable_values=(2.0,),
        )
        coordinator.reject_candidate()
        accepted_point = coordinator.get_accepted_point()
        assert accepted_point[0] == pytest.approx(0.0)
        assert accepted_point[1] == pytest.approx((1.0,))
    finally:
        coordinator.close()
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmi_three_no_checkpoint_reconstruction_rejects_observable_state_leakage(
    compiled_fmi_three_state_leak_model_exchange_fmu: Path,
    tmp_path: Path,
) -> None:
    """Reject hidden native state that changes a reconstructed visible point.

    :param compiled_fmi_three_state_leak_model_exchange_fmu: Native adversarial
        Model Exchange fixture declaring no checkpoint support.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "model-exchange-visible-state-leak"
    session: FmiThreeNumericSession = _open_float64_session(
        compiled_fmu_path=compiled_fmi_three_state_leak_model_exchange_fmu,
        staging_parent=staging_parent,
        float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
        interface_mode=FmuInterfaceMode.MODEL_EXCHANGE,
    )
    coordinator: FmiThreeModelExchangeCoordinator = (
        FmiThreeModelExchangeCoordinator(
            session=session,
            maximum_event_iterations=4,
        )
    )
    try:
        coordinator.initialize(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_writable_values=(2.0,),
        )
        coordinator.evaluate_candidate(
            time_value=0.25,
            continuous_state_values=(1.25,),
            writable_values=(2.0,),
        )
        with pytest.raises(
            RuntimeError,
            match="unsupported observable state leakage",
        ):
            coordinator.reject_candidate()
    finally:
        coordinator.close()
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmi_three_constant_array_profile_preserves_scalar_subset(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Run the scalar subset through the negotiated constant-array profile.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated native fixture.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "constant-array-profile"
    session: FmiThreeNumericSession = _open_float64_session(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        staging_parent=staging_parent,
        float64_profile=FmiThreeWorkerFloat64Profile.CONSTANT_ARRAY,
    )
    try:
        initialized_values: tuple[float, ...] = session.initialize_co_simulation_and_read(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_writable_float64_values=(3.0,),
        )
        assert initialized_values == pytest.approx((0.0, 0.0, 3.0))
        step_result: FmiThreeWorkerDoStepResult
        readable_values: tuple[float, ...]
        step_result, readable_values = session.advance_co_simulation(
            current_communication_point=0.0,
            communication_step_size=0.25,
            writable_float64_values=(3.0,),
            no_set_fmu_state_prior_to_current_point=True,
        )
        assert step_result.last_successful_time == pytest.approx(0.25)
        assert readable_values == pytest.approx((3.25, 0.25, 3.0))
    finally:
        session.close()
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmi_three_constant_array_session_runs_one_to_six_native_access(
    compiled_fmi_three_constant_array_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Execute one array reference as six row-major native Float64 values.

    :param compiled_fmi_three_constant_array_co_simulation_fmu: Native array FMU.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "native-array-session"
    config: FmuImportConfig = FmuImportConfig(
        fmu_path=compiled_fmi_three_constant_array_co_simulation_fmu,
        extraction_root=staging_parent,
    )
    session: FmiThreeNumericSession = (
        open_fmi_three_numeric_session(
            config=config,
            instance_name="veragrid-fmi-three-native-array-session",
            readable_variable_names=("array_output",),
            writable_variable_names=("array_input",),
            limits=_create_scalar_session_limits(),
            float64_profile=FmiThreeWorkerFloat64Profile.CONSTANT_ARRAY,
        )
    )
    initial_input_values: tuple[float, ...] = (0.0, 0.1, 1.0, 1.1, 2.0, 2.1)
    step_input_values: tuple[float, ...] = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    try:
        assert not session.supports_fmu_state_checkpoint()
        assert not session.supports_serialized_fmu_state()
        initialized_values: tuple[float, ...] = session.initialize_co_simulation_and_read(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_writable_float64_values=initial_input_values,
        )
        assert initialized_values == pytest.approx((0.0,) * 6)
        with pytest.raises(RuntimeError, match="requires supported Step"):
            session.save_checkpoint()
        step_result: FmiThreeWorkerDoStepResult
        readable_values: tuple[float, ...]
        step_result, readable_values = session.advance_co_simulation(
            current_communication_point=0.0,
            communication_step_size=0.25,
            writable_float64_values=step_input_values,
            no_set_fmu_state_prior_to_current_point=True,
        )
        assert step_result.last_successful_time == pytest.approx(0.25)
        assert readable_values == pytest.approx(
            (1.25, 2.25, 3.25, 4.25, 5.25, 6.25)
        )
    finally:
        session.close()
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmi_three_session_selects_row_major_device_values(
    compiled_fmi_three_constant_array_co_simulation_fmu: Path,
    compiled_fmi_three_configurable_array_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Select device values without duplicating one native array reference.

    :param compiled_fmi_three_constant_array_co_simulation_fmu: Native array FMU.
    :param compiled_fmi_three_configurable_array_co_simulation_fmu: Native
        configurable-array FMU.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    output_bindings: tuple[FmuRefBinding, ...] = (
        FmuRefBinding(
            reference=VarPowerFlowReferenceType.P,
            fmu_variable_name="array_output",
            flat_index=4,
        ),
        FmuRefBinding(
            reference=VarPowerFlowReferenceType.Q,
            fmu_variable_name="array_output",
            flat_index=1,
        ),
    )
    readable_variable_names: tuple[str, ...]
    readable_value_selectors: tuple[
        FmiThreeFloat64SessionValueSelector, ...
    ]
    (
        readable_variable_names,
        readable_value_selectors,
    ) = resolve_fmi_three_float64_session_value_selectors(output_bindings)
    assert readable_variable_names == ("array_output",)

    staging_parent: Path = tmp_path / "row-major-device-values"
    session: FmiThreeNumericSession = open_fmi_three_numeric_session(
        config=FmuImportConfig(
            fmu_path=compiled_fmi_three_constant_array_co_simulation_fmu,
            extraction_root=staging_parent,
        ),
        instance_name="veragrid-fmi-three-selected-array-values",
        readable_variable_names=readable_variable_names,
        writable_variable_names=("array_input",),
        limits=_create_scalar_session_limits(),
        float64_profile=FmiThreeWorkerFloat64Profile.CONSTANT_ARRAY,
        readable_value_selectors=readable_value_selectors,
    )
    try:
        initialized_values: tuple[float, ...] = (
            session.initialize_co_simulation_and_read(
                start_time=0.0,
                stop_time=1.0,
                relative_tolerance=1.0e-6,
                initial_writable_float64_values=(0.0,) * 6,
            )
        )
        assert initialized_values == pytest.approx((0.0, 0.0))
        step_result: FmiThreeWorkerDoStepResult
        selected_values: tuple[float, ...]
        step_result, selected_values = session.advance_co_simulation(
            current_communication_point=0.0,
            communication_step_size=0.25,
            writable_float64_values=(1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
            no_set_fmu_state_prior_to_current_point=True,
        )
        assert step_result.last_successful_time == pytest.approx(0.25)
        assert selected_values == pytest.approx((5.25, 2.25))
    finally:
        session.close()
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()

    configurable_bindings: tuple[FmuRefBinding, ...] = (
        FmuRefBinding(
            reference=VarPowerFlowReferenceType.P,
            fmu_variable_name="array_output",
            flat_index=2,
        ),
    )
    configurable_variable_names: tuple[str, ...]
    configurable_value_selectors: tuple[
        FmiThreeFloat64SessionValueSelector, ...
    ]
    (
        configurable_variable_names,
        configurable_value_selectors,
    ) = resolve_fmi_three_float64_session_value_selectors(
        configurable_bindings
    )
    configurable_staging_parent: Path = tmp_path / "configured-selected-values"
    configurable_session: FmiThreeNumericSession = (
        open_fmi_three_numeric_session(
            config=FmuImportConfig(
                fmu_path=(
                    compiled_fmi_three_configurable_array_co_simulation_fmu
                ),
                extraction_root=configurable_staging_parent,
            ),
            instance_name="veragrid-fmi-three-configured-selected-values",
            readable_variable_names=configurable_variable_names,
            writable_variable_names=tuple(),
            limits=_create_scalar_session_limits(),
            float64_profile=FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY,
            configuration_uint64_variable_names=("structural_size",),
            readable_value_selectors=configurable_value_selectors,
        )
    )
    try:
        with pytest.raises(ValueError, match="exceeds array cardinality"):
            configurable_session.configure_uint64(
                configuration_uint64_values=(2,)
            )
        configurable_session.configure_uint64(
            configuration_uint64_values=(3,)
        )
        configured_values: tuple[float, ...] = (
            configurable_session.initialize_co_simulation_and_read(
                start_time=0.0,
                stop_time=1.0,
                relative_tolerance=1.0e-6,
                initial_writable_float64_values=tuple(),
            )
        )
        assert configured_values == pytest.approx((0.0,))
    finally:
        configurable_session.close()
    assert (
        tuple(configurable_staging_parent.glob("veragrid_fmu_stage_*"))
        == tuple()
    )


def test_fmi_three_configurable_array_session_resizes_positive_and_zero(
    compiled_fmi_three_configurable_array_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Resize native arrays to two elements and then to a vanished layout.

    :param compiled_fmi_three_configurable_array_co_simulation_fmu: Native fixture.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    positive_staging_parent: Path = tmp_path / "positive-configurable-session"
    positive_config: FmuImportConfig = FmuImportConfig(
        fmu_path=compiled_fmi_three_configurable_array_co_simulation_fmu,
        extraction_root=positive_staging_parent,
    )
    positive_session: FmiThreeNumericSession = (
        open_fmi_three_numeric_session(
            config=positive_config,
            instance_name="veragrid-fmi-three-positive-configurable-session",
            readable_variable_names=("array_output", "time"),
            writable_variable_names=("array_input",),
            limits=_create_scalar_session_limits(),
            float64_profile=FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY,
            configuration_uint64_variable_names=("structural_size",),
        )
    )
    try:
        positive_session.configure_uint64(configuration_uint64_values=(2,))
        initialized_values: tuple[float, ...] = (
            positive_session.initialize_co_simulation_and_read(
                start_time=0.0,
                stop_time=1.0,
                relative_tolerance=1.0e-6,
                initial_writable_float64_values=(1.0, 2.0),
            )
        )
        assert initialized_values == pytest.approx((0.0, 0.0, 0.0))
        step_result: FmiThreeWorkerDoStepResult
        readable_values: tuple[float, ...]
        step_result, readable_values = positive_session.advance_co_simulation(
            current_communication_point=0.0,
            communication_step_size=0.25,
            writable_float64_values=(4.0, 5.0),
            no_set_fmu_state_prior_to_current_point=True,
        )
        assert step_result.last_successful_time == pytest.approx(0.25)
        assert readable_values == pytest.approx((4.25, 5.25, 0.25))
    finally:
        positive_session.close()

    zero_staging_parent: Path = tmp_path / "zero-configurable-session"
    zero_config: FmuImportConfig = FmuImportConfig(
        fmu_path=compiled_fmi_three_configurable_array_co_simulation_fmu,
        extraction_root=zero_staging_parent,
    )
    zero_session: FmiThreeNumericSession = (
        open_fmi_three_numeric_session(
            config=zero_config,
            instance_name="veragrid-fmi-three-zero-configurable-session",
            readable_variable_names=("array_output", "time"),
            writable_variable_names=("array_input",),
            limits=_create_scalar_session_limits(),
            float64_profile=FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY,
            configuration_uint64_variable_names=("structural_size",),
        )
    )
    try:
        zero_session.configure_uint64(configuration_uint64_values=(0,))
        zero_initialized_values: tuple[float, ...] = (
            zero_session.initialize_co_simulation_and_read(
                start_time=0.0,
                stop_time=1.0,
                relative_tolerance=1.0e-6,
                initial_writable_float64_values=tuple(),
            )
        )
        assert zero_initialized_values == pytest.approx((0.0,))
        zero_step_result: FmiThreeWorkerDoStepResult
        zero_readable_values: tuple[float, ...]
        zero_step_result, zero_readable_values = zero_session.advance_co_simulation(
            current_communication_point=0.0,
            communication_step_size=0.25,
            writable_float64_values=tuple(),
            no_set_fmu_state_prior_to_current_point=True,
        )
        assert zero_step_result.last_successful_time == pytest.approx(0.25)
        assert zero_readable_values == pytest.approx((0.25,))
    finally:
        zero_session.close()
    assert tuple(positive_staging_parent.glob("veragrid_fmu_stage_*")) == tuple()
    assert tuple(zero_staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmi_three_scalar_session_configures_structural_values_natively(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Apply Float64 and UInt64 structural values before initialization.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated native fixture.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "native-configuration-session"
    config: FmuImportConfig = FmuImportConfig(
        fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        extraction_root=staging_parent,
    )
    session: FmiThreeNumericSession = (
        open_fmi_three_numeric_session(
            config=config,
            instance_name="veragrid-fmi-three-native-configuration-session",
            readable_variable_names=("observed_output",),
            writable_variable_names=("control_input",),
            limits=_create_scalar_session_limits(),
            float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
            configuration_variable_names=("structural_gain",),
            configuration_uint64_variable_names=("structural_size",),
        )
    )
    try:
        with pytest.raises(ValueError, match="must align"):
            session.configure_uint64(configuration_uint64_values=tuple())
        session.configure_uint64(configuration_uint64_values=(5,))
        with pytest.raises(ValueError, match="must align"):
            session.configure(configuration_float64_values=tuple())
        session.configure(configuration_float64_values=(2.0,))
        initialized_values: tuple[float, ...] = session.initialize_co_simulation_and_read(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_writable_float64_values=(3.0,),
        )
        assert initialized_values == pytest.approx((0.0,))
        step_result: FmiThreeWorkerDoStepResult
        readable_values: tuple[float, ...]
        step_result, readable_values = session.advance_co_simulation(
            current_communication_point=0.0,
            communication_step_size=0.25,
            writable_float64_values=(3.0,),
            no_set_fmu_state_prior_to_current_point=True,
        )
        assert step_result.last_successful_time == pytest.approx(0.25)
        assert readable_values == pytest.approx((6.25,))
        with pytest.raises(RuntimeError, match="READY state"):
            session.configure(configuration_float64_values=(4.0,))
        with pytest.raises(RuntimeError, match="READY state"):
            session.configure_uint64(configuration_uint64_values=(7,))
    finally:
        session.close()
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmi_three_constant_array_session_rejects_wrong_native_cardinality(
    compiled_fmi_three_constant_array_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Reject five values for one six-value array before the native ABI call.

    :param compiled_fmi_three_constant_array_co_simulation_fmu: Native array FMU.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "invalid-native-array-cardinality"
    config: FmuImportConfig = FmuImportConfig(
        fmu_path=compiled_fmi_three_constant_array_co_simulation_fmu,
        extraction_root=staging_parent,
    )
    session: FmiThreeNumericSession = (
        open_fmi_three_numeric_session(
            config=config,
            instance_name="veragrid-fmi-three-invalid-array-cardinality",
            readable_variable_names=("array_output",),
            writable_variable_names=("array_input",),
            limits=_create_scalar_session_limits(),
            float64_profile=FmiThreeWorkerFloat64Profile.CONSTANT_ARRAY,
        )
    )
    try:
        with pytest.raises(ValueError, match="do not match the bound layout"):
            session.initialize_co_simulation_and_read(
                start_time=0.0,
                stop_time=1.0,
                relative_tolerance=1.0e-6,
                initial_writable_float64_values=(0.0, 0.1, 1.0, 1.1, 2.0),
            )
    finally:
        session.close()
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()


def test_fmi_three_scalar_session_rejects_binding_before_staging(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Reject an unknown consumer name before allocating a private stage.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated native fixture.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "invalid-binding"
    config: FmuImportConfig = FmuImportConfig(
        fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        extraction_root=staging_parent,
    )

    with pytest.raises(ValueError, match="was not found"):
        open_fmi_three_numeric_session(
            config=config,
            instance_name="veragrid-fmi-three-invalid-binding",
            readable_variable_names=("missing_output",),
            writable_variable_names=("control_input",),
            limits=_create_scalar_session_limits(),
            float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
        )
    assert not staging_parent.exists()


def test_fmi_three_scalar_session_rejects_instance_name_before_staging(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Reject an empty native instance identity before allocating a stage.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated native fixture.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "invalid-instance-name"
    config: FmuImportConfig = FmuImportConfig(
        fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        extraction_root=staging_parent,
    )

    with pytest.raises(ValueError, match="instance name must not be empty"):
        open_fmi_three_numeric_session(
            config=config,
            instance_name=" ",
            readable_variable_names=("observed_output",),
            writable_variable_names=("control_input",),
            limits=_create_scalar_session_limits(),
            float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
        )
    assert not staging_parent.exists()


def test_fmi_three_scalar_session_rejects_batch_limit_before_staging(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Reject a bound read batch that cannot fit the consumer limits.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated native fixture.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    staging_parent: Path = tmp_path / "invalid-batch-limit"
    config: FmuImportConfig = FmuImportConfig(
        fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        extraction_root=staging_parent,
    )
    restrictive_limits: FmiThreeWorkerHostLimits = (
        FmiThreeWorkerHostLimits(
            maximum_frame_size=262144,
            maximum_float64_values_per_request=1,
            response_timeout_seconds=20.0,
            graceful_join_timeout_seconds=10.0,
            terminate_join_timeout_seconds=5.0,
            kill_join_timeout_seconds=5.0,
        )
    )

    with pytest.raises(ValueError, match="count is outside its bound"):
        open_fmi_three_numeric_session(
            config=config,
            instance_name="veragrid-fmi-three-invalid-batch",
            readable_variable_names=("observed_output", "time"),
            writable_variable_names=("control_input",),
            limits=restrictive_limits,
            float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
        )
    assert not staging_parent.exists()


def test_fmi_three_scalar_session_rejects_cardinality_before_step(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Reject a writable-value mismatch without advancing worker time.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated native fixture.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    session: FmiThreeNumericSession = _open_float64_session(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        staging_parent=tmp_path / "cardinality-session",
        float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
    )
    try:
        session.initialize_co_simulation_and_read(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_writable_float64_values=(2.0,),
        )
        with pytest.raises(ValueError, match="do not match the bound layout"):
            session.advance_co_simulation(
                current_communication_point=0.0,
                communication_step_size=0.25,
                writable_float64_values=tuple(),
                no_set_fmu_state_prior_to_current_point=True,
            )
        valid_result: FmiThreeWorkerDoStepResult
        valid_values: tuple[float, ...]
        valid_result, valid_values = session.advance_co_simulation(
            current_communication_point=0.0,
            communication_step_size=0.25,
            writable_float64_values=(2.0,),
            no_set_fmu_state_prior_to_current_point=True,
        )
        assert valid_result.last_successful_time == pytest.approx(0.25)
        assert valid_values == pytest.approx((2.25, 0.25, 2.0))
    finally:
        session.close()


def test_fmi_three_scalar_session_returns_final_readable_values_before_close(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Return final readable values with termination and prohibit another step.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated native fixture.
    :param tmp_path: Isolated staging parent provided by pytest.
    :return: None.
    """

    session: FmiThreeNumericSession = _open_float64_session(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        staging_parent=tmp_path / "termination-session",
        float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
    )
    try:
        session.initialize_co_simulation_and_read(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_writable_float64_values=(9.0,),
        )
        termination_result: FmiThreeWorkerDoStepResult
        final_values: tuple[float, ...]
        termination_result, final_values = session.advance_co_simulation(
            current_communication_point=0.0,
            communication_step_size=0.25,
            writable_float64_values=(9.0,),
            no_set_fmu_state_prior_to_current_point=True,
        )
        assert termination_result.terminate_simulation
        assert final_values == pytest.approx((9.25, 0.25, 9.0))
        with pytest.raises(RuntimeError, match="requires Step Mode"):
            session.advance_co_simulation(
                current_communication_point=0.25,
                communication_step_size=0.25,
                writable_float64_values=(9.0,),
                no_set_fmu_state_prior_to_current_point=True,
            )
    finally:
        session.close()
