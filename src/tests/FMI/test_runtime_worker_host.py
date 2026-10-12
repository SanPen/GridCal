# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Integration tests for parent-side FMI 3 worker supervision."""

from __future__ import annotations

import os
from pathlib import Path
import signal

import pytest

from VeraGridEngine.IO.fmu.model_description import (
    FmuModelDescription,
    read_fmu_model_description,
)
from VeraGridEngine.IO.fmu.Elements.protocol import (
    FmiThreeWorkerCompletedIntegratorStepResult,
    FmiThreeWorkerDiscreteStatesResult,
    FmiThreeWorkerDoStepResult,
)
from VeraGridEngine.IO.fmu.profile import (
    FmiThreeWorkerFloat64Profile,
)
from VeraGridEngine.IO.fmu.worker_host import (
    FmiThreeWorkerHost,
    FmiThreeWorkerHostLimits,
    FmiThreeWorkerHostState,
    prepare_fmi_three_worker_host,
)
from VeraGridEngine.enumerations import FmuInterfaceMode


class _InterruptBeforeSpawnInstanceName(str):
    """Raise a deterministic cancellation during START identity validation."""

    __slots__ = ()

    def strip(self, chars: str | None = None) -> str:
        """Interrupt before the worker process has been constructed.

        :param chars: Optional characters accepted by the ``str`` contract.
        :return: This method does not return.
        """

        raise KeyboardInterrupt


class _InterruptAfterSpawnInstanceName(str):
    """Raise a deterministic cancellation while encoding a live START."""

    __slots__ = ()

    def encode(
        self,
        encoding: str = "utf-8",
        errors: str = "strict",
    ) -> bytes:
        """Interrupt after START has spawned its child process.

        :param encoding: Requested text encoding.
        :param errors: Requested encoding error policy.
        :return: This method does not return.
        """

        raise KeyboardInterrupt


def _create_worker_host_limits(
    response_timeout_seconds: float,
    maximum_frame_size: int,
) -> FmiThreeWorkerHostLimits:
    """Create explicit finite limits used only by the integration tests.

    :param response_timeout_seconds: Test-selected response deadline.
    :param maximum_frame_size: Shared worker frame bound.
    :return: Complete supervisor limits without product defaults.
    """

    return FmiThreeWorkerHostLimits(
        maximum_frame_size=maximum_frame_size,
        maximum_float64_values_per_request=64,
        response_timeout_seconds=response_timeout_seconds,
        graceful_join_timeout_seconds=10.0,
        terminate_join_timeout_seconds=5.0,
        kill_join_timeout_seconds=5.0,
    )


def _prepare_compiled_fmi_three_scalar_worker_host(
    compiled_fmu_path: Path,
    limits: FmiThreeWorkerHostLimits,
    interface_mode: FmuInterfaceMode = FmuInterfaceMode.CO_SIMULATION,
) -> FmiThreeWorkerHost:
    """Parse and prepare one generated FMI 3 FMU for explicit START.

    :param compiled_fmu_path: Generated host-native FMI 3 test FMU.
    :param limits: Explicit supervisor limits selected by the test.
    :param interface_mode: FMI 3 interface selected for the child instance.
    :return: Prepared host that owns its private staging area.
    """

    metadata: FmuModelDescription = read_fmu_model_description(compiled_fmu_path)
    return prepare_fmi_three_worker_host(
        metadata=metadata,
        interface_mode=interface_mode,
        staging_parent=compiled_fmu_path.parent,
        limits=limits,
        float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
    )


def test_worker_host_int32_round_trip_uses_same_session(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Round-trip Float64 and Int32 through one worker and native instance.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native
        scalar test FMU.
    :return: None.
    """

    host: FmiThreeWorkerHost = _prepare_compiled_fmi_three_scalar_worker_host(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        limits=_create_worker_host_limits(60.0, 262144),
    )
    staging_root: Path = host.get_staging_root()
    try:
        host.start(
            instance_name="veragrid-fmi-three-int32-one-session",
            visible=False,
            debug_logging=False,
        )
        process_id: int | None = host.get_process_id()
        assert process_id is not None
        host.initialize(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_float64_value_references=(1,),
            initial_float64_values=(2.0,),
            initial_int32_value_references=(7,),
            initial_int32_values=(-2,),
        )
        assert host.get_int32((7, 8)) == (-2, 0)
        step_result: FmiThreeWorkerDoStepResult = (
            host.set_numeric_values_and_do_step(
                float64_value_references=(1,),
                float64_values=(3.0,),
                current_communication_point=0.0,
                communication_step_size=0.1,
                no_set_fmu_state_prior_to_current_point=True,
                int32_value_references=(7,),
                int32_values=(-5,),
            )
        )
        assert step_result.last_successful_time == pytest.approx(0.1)
        assert host.get_int32((8, 7)) == (-5, -5)
        assert host.get_process_id() == process_id
    finally:
        host.close()
    assert host.get_exit_code() == 0
    assert not staging_root.exists()


def test_worker_host_accepts_both_mixed_numeric_write_orders(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Allow either typed input order while preserving one pending-step state.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native
        scalar test FMU.
    :return: None.
    """

    host: FmiThreeWorkerHost = _prepare_compiled_fmi_three_scalar_worker_host(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        limits=_create_worker_host_limits(60.0, 262144),
    )
    staging_root: Path = host.get_staging_root()
    try:
        host.start(
            instance_name="veragrid-fmi-three-mixed-write-orders",
            visible=False,
            debug_logging=False,
        )
        host.initialize(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_float64_value_references=tuple(),
            initial_float64_values=tuple(),
            initial_int32_value_references=(7,),
            initial_int32_values=(-2,),
        )

        # Both setters share one pending state, so Float64 then Int32 remains valid.
        host.set_float64(value_references=(1,), values=(2.0,))
        host.set_int32(value_references=(7,), values=(-3,))
        host.do_step(
            current_communication_point=0.0,
            communication_step_size=0.1,
            no_set_fmu_state_prior_to_current_point=True,
        )
        assert host.get_int32((8,)) == (-3,)

        # The inverse order must use the same state transition and worker.
        host.set_int32(value_references=(7,), values=(4,))
        host.set_float64(value_references=(1,), values=(5.0,))
        host.do_step(
            current_communication_point=0.1,
            communication_step_size=0.1,
            no_set_fmu_state_prior_to_current_point=True,
        )
        assert host.get_int32((8,)) == (4,)
    finally:
        host.close()
    assert host.get_exit_code() == 0
    assert not staging_root.exists()


def test_worker_host_restores_int32_and_mixed_pending_checkpoints(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Restore reusable checkpoints after Int32-only and mixed pending writes.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native
        scalar test FMU with native state support.
    :return: None.
    """

    host: FmiThreeWorkerHost = _prepare_compiled_fmi_three_scalar_worker_host(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        limits=_create_worker_host_limits(60.0, 262144),
    )
    staging_root: Path = host.get_staging_root()
    try:
        host.start(
            instance_name="veragrid-fmi-three-int32-checkpoints",
            visible=False,
            debug_logging=False,
        )
        host.initialize(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_float64_value_references=(1,),
            initial_float64_values=(2.0,),
            initial_int32_value_references=(7,),
            initial_int32_values=(-2,),
        )

        host.save_checkpoint()
        host.set_int32(value_references=(7,), values=(4,))
        assert host.get_state() == FmiThreeWorkerHostState.INPUT_VALUES_PENDING_STEP
        host.restore_checkpoint()
        assert host.get_int32((7,)) == (-2,)
        host.discard_checkpoint()

        host.save_checkpoint()
        host.set_float64(value_references=(1,), values=(6.0,))
        host.set_int32(value_references=(7,), values=(7,))
        assert host.get_state() == FmiThreeWorkerHostState.INPUT_VALUES_PENDING_STEP
        host.restore_checkpoint()
        assert host.get_float64((1,), 1) == pytest.approx((2.0,))
        assert host.get_int32((7,)) == (-2,)
        host.discard_checkpoint()
    finally:
        host.close()
    assert host.get_exit_code() == 0
    assert not staging_root.exists()


def test_fmi_three_worker_host_initializes_and_closes_owned_staging(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Supervise READY, INITIALIZED, and CLOSED with exact staging ownership.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native test FMU.
    :return: None.
    """

    metadata: FmuModelDescription = read_fmu_model_description(
        compiled_fmi_three_scalar_co_simulation_fmu
    )
    host: FmiThreeWorkerHost = (
        prepare_fmi_three_worker_host(
            metadata=metadata,
            interface_mode=FmuInterfaceMode.CO_SIMULATION,
            staging_parent=compiled_fmi_three_scalar_co_simulation_fmu.parent,
            limits=_create_worker_host_limits(60.0, 262144),
            float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
        )
    )
    staging_root: Path = host.get_staging_root()
    assert staging_root.is_dir()
    try:
        host.start(
            instance_name="veragrid-fmi-three-supervised-initialization",
            visible=False,
            debug_logging=False,
        )
        assert host.get_state() == FmiThreeWorkerHostState.READY
        assert host.get_process_id() is not None
        assert staging_root.is_dir()
        with pytest.raises(ValueError, match="CONFIGURE_UINT64 reference"):
            host.configure_uint64(
                value_references=(3,),
                values=(5,),
            )
        host.configure_uint64(
            value_references=(4,),
            values=(5,),
        )
        assert host.get_state() == FmiThreeWorkerHostState.READY
        host.initialize(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_float64_value_references=(1,),
            initial_float64_values=(2.0,),
        )
        assert host.get_state() == FmiThreeWorkerHostState.INITIALIZED
        with pytest.raises(RuntimeError, match="requires READY state"):
            host.initialize(
                start_time=0.0,
                stop_time=1.0,
                relative_tolerance=1.0e-6,
                initial_float64_value_references=tuple(),
                initial_float64_values=tuple(),
            )
        assert host.get_state() == FmiThreeWorkerHostState.INITIALIZED
        with pytest.raises(RuntimeError, match="requires Model Exchange"):
            host.set_time(0.25)
        host.close()
    finally:
        host.close()
    assert host.is_closed()
    assert host.get_exit_code() == 0
    assert host.get_process_id() is None
    assert not staging_root.exists()


def test_fmi_three_worker_host_runs_model_exchange_continuous_time_lifecycle(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Drive the bounded FMI 3 Model Exchange API through the parent owner.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated dual-interface
        host-native test FMU.
    :return: None.
    """

    host: FmiThreeWorkerHost = _prepare_compiled_fmi_three_scalar_worker_host(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        limits=_create_worker_host_limits(60.0, 262144),
        interface_mode=FmuInterfaceMode.MODEL_EXCHANGE,
    )
    staging_root: Path = host.get_staging_root()
    try:
        host.start(
            instance_name="veragrid-fmi-three-supervised-model-exchange",
            visible=False,
            debug_logging=False,
        )
        assert host.get_interface_mode() == FmuInterfaceMode.MODEL_EXCHANGE
        assert host.supports_fmu_state_checkpoint()
        assert not host.supports_serialized_fmu_state()
        assert host.needs_completed_integrator_step()
        assert host.get_state() == FmiThreeWorkerHostState.READY
        host.initialize(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_float64_value_references=tuple(),
            initial_float64_values=tuple(),
        )
        assert host.get_state() == FmiThreeWorkerHostState.EVENT_MODE
        assert host.get_nominals_of_continuous_states() == pytest.approx((1.0,))
        discrete_states_result: FmiThreeWorkerDiscreteStatesResult = (
            host.update_discrete_states()
        )
        assert not discrete_states_result.discrete_states_need_update
        assert not discrete_states_result.terminate_simulation
        assert not discrete_states_result.next_event_time_defined
        host.enter_continuous_time_mode()
        assert host.get_state() == FmiThreeWorkerHostState.CONTINUOUS_TIME
        assert host.get_continuous_states() == pytest.approx((1.0,))
        host.save_checkpoint()

        # Model Exchange writes remain in Continuous-Time Mode and do not
        # acquire the Co-Simulation pending-step constraint.
        host.set_float64(value_references=(1,), values=(2.0,))
        assert host.get_state() == FmiThreeWorkerHostState.CONTINUOUS_TIME
        with pytest.raises(ValueError, match="empty evaluation write layout"):
            host.evaluate_model_exchange(
                time_value=0.25,
                continuous_state_values=(3.0,),
                writable_value_references=tuple(),
                writable_values=(2.0,),
                readable_value_references=(2, 0, 1),
                readable_value_count=3,
            )
        derivative_values: tuple[float, ...]
        readable_values: tuple[float, ...]
        derivative_values, readable_values = host.evaluate_model_exchange(
            time_value=0.25,
            continuous_state_values=(3.0,),
            writable_value_references=(1,),
            writable_values=(2.0,),
            readable_value_references=(2, 0, 1),
            readable_value_count=3,
        )
        assert derivative_values == pytest.approx((-1.0,))
        assert readable_values == pytest.approx((0.0, 0.25, 2.0))
        assert host.get_continuous_states() == pytest.approx((3.0,))
        assert host.get_event_indicators() == pytest.approx((0.5,))
        assert host.get_nominals_of_continuous_states() == pytest.approx((1.0,))
        # One checkpoint remains reusable across several candidate evaluations.
        host.restore_checkpoint()
        assert host.get_state() == FmiThreeWorkerHostState.CONTINUOUS_TIME
        assert host.get_continuous_states() == pytest.approx((1.0,))
        host.set_continuous_states((4.0,))
        host.restore_checkpoint()
        assert host.get_continuous_states() == pytest.approx((1.0,))
        host.discard_checkpoint()
        with pytest.raises(RuntimeError, match="requires a compatible saved state"):
            host.restore_checkpoint()
        completed_result: FmiThreeWorkerCompletedIntegratorStepResult = (
            host.completed_integrator_step(
                no_set_fmu_state_prior_to_current_point=True
            )
        )
        assert not completed_result.enter_event_mode
        assert not completed_result.terminate_simulation
        assert host.get_state() == FmiThreeWorkerHostState.CONTINUOUS_TIME
        # Time, state, input, and clock events are detected by the importer,
        # so their native transition starts directly in Continuous-Time Mode.
        host.enter_event_mode()
        assert host.get_state() == FmiThreeWorkerHostState.EVENT_MODE
        direct_event_result: FmiThreeWorkerDiscreteStatesResult = (
            host.update_discrete_states()
        )
        assert not direct_event_result.discrete_states_need_update
        host.enter_continuous_time_mode()
        assert host.get_state() == FmiThreeWorkerHostState.CONTINUOUS_TIME
        with pytest.raises(RuntimeError, match="requires Co-Simulation"):
            host.do_step(
                current_communication_point=0.25,
                communication_step_size=0.1,
                no_set_fmu_state_prior_to_current_point=True,
            )
        host.set_float64(value_references=(1,), values=(9.0,))
        event_result: FmiThreeWorkerCompletedIntegratorStepResult = (
            host.completed_integrator_step(
                no_set_fmu_state_prior_to_current_point=True
            )
        )
        assert event_result.enter_event_mode
        assert not event_result.terminate_simulation
        assert host.get_state() == FmiThreeWorkerHostState.EVENT_MODE_REQUESTED
        host.enter_event_mode()
        assert host.get_state() == FmiThreeWorkerHostState.EVENT_MODE
        event_update_result: FmiThreeWorkerDiscreteStatesResult = (
            host.update_discrete_states()
        )
        assert event_update_result.discrete_states_need_update
        assert host.get_state() == FmiThreeWorkerHostState.EVENT_MODE
    finally:
        host.close()
    assert host.is_closed()
    assert host.get_exit_code() == 0
    assert not staging_root.exists()


def test_fmi_three_worker_host_cleans_cancelled_start_before_spawn(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Release staging when cancellation proves spawn was never attempted.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated native fixture.
    :return: None.
    """

    host: FmiThreeWorkerHost = (
        _prepare_compiled_fmi_three_scalar_worker_host(
            compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
            limits=_create_worker_host_limits(20.0, 262144),
        )
    )
    staging_root: Path = host.get_staging_root()
    with pytest.raises(KeyboardInterrupt):
        host.start(
            instance_name=_InterruptBeforeSpawnInstanceName(
                "veragrid-fmi-three-cancel-before-spawn"
            ),
            visible=False,
            debug_logging=False,
        )
    assert host.get_state() == FmiThreeWorkerHostState.FAILED
    assert host.get_process_id() is None
    assert not staging_root.exists()
    host.close()
    assert host.is_closed()


def test_fmi_three_worker_host_cleans_cancelled_start_after_spawn(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Prove child death before releasing staging after live cancellation.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated native fixture.
    :return: None.
    """

    host: FmiThreeWorkerHost = (
        _prepare_compiled_fmi_three_scalar_worker_host(
            compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
            limits=_create_worker_host_limits(20.0, 262144),
        )
    )
    staging_root: Path = host.get_staging_root()
    with pytest.raises(KeyboardInterrupt):
        host.start(
            instance_name=_InterruptAfterSpawnInstanceName(
                "veragrid-fmi-three-cancel-after-spawn"
            ),
            visible=False,
            debug_logging=False,
        )
    assert host.get_state() == FmiThreeWorkerHostState.FAILED
    assert host.get_process_id() is None
    assert host.get_exit_code() is not None
    assert not staging_root.exists()
    host.close()
    assert host.is_closed()


def test_fmi_three_worker_host_retains_unknown_spawn_after_owner_gc(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Retain staging when START was attempted but no PID became observable.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated native fixture.
    :return: None.
    """

    host: FmiThreeWorkerHost = (
        _prepare_compiled_fmi_three_scalar_worker_host(
            compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
            limits=_create_worker_host_limits(20.0, 262144),
        )
    )
    staging_root: Path = host.get_staging_root()

    host._release_incomplete_start(process_start_attempted=True)
    assert host.get_state() == FmiThreeWorkerHostState.FAILED
    assert host.get_process_id() is None
    assert staging_root.is_dir()
    with pytest.raises(RuntimeError, match="spawn outcome is unknown"):
        host.close()
    assert host.get_state() == FmiThreeWorkerHostState.FAILED
    assert staging_root.is_dir()

    del host
    assert staging_root.is_dir()


def test_fmi_three_worker_host_rejects_step_before_native_write(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Preserve the current writable value across invalid step requests.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated native fixture.
    :return: None.
    """

    host: FmiThreeWorkerHost = (
        _prepare_compiled_fmi_three_scalar_worker_host(
            compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
            limits=_create_worker_host_limits(60.0, 262144),
        )
    )
    try:
        host.start(
            instance_name="veragrid-fmi-three-step-preflight",
            visible=False,
            debug_logging=False,
        )
        host.initialize(
            start_time=0.0,
            stop_time=2.0,
            relative_tolerance=1.0e-6,
            initial_float64_value_references=(1,),
            initial_float64_values=(2.0,),
        )
        with pytest.raises(ValueError, match="references and values must align"):
            host.set_float64(
                value_references=(1,),
                values=(9.0, 10.0),
            )
        assert host.get_state() == FmiThreeWorkerHostState.INITIALIZED
        with pytest.raises(RuntimeError, match="not continuous"):
            host.set_numeric_values_and_do_step(
                float64_value_references=(1,),
                float64_values=(9.0,),
                current_communication_point=0.25,
                communication_step_size=0.25,
                no_set_fmu_state_prior_to_current_point=True,
            )
        with pytest.raises(ValueError, match="finite and positive"):
            host.set_numeric_values_and_do_step(
                float64_value_references=(1,),
                float64_values=(9.0,),
                current_communication_point=0.0,
                communication_step_size=float("nan"),
                no_set_fmu_state_prior_to_current_point=True,
            )
        with pytest.raises(ValueError, match="endpoint must be finite"):
            host.set_numeric_values_and_do_step(
                float64_value_references=(1,),
                float64_values=(9.0,),
                current_communication_point=1.7976931348623157e308,
                communication_step_size=1.7976931348623157e308,
                no_set_fmu_state_prior_to_current_point=True,
            )
        with pytest.raises(ValueError, match="endpoint must be finite"):
            host.set_numeric_values_and_do_step(
                float64_value_references=(1,),
                float64_values=(9.0,),
                current_communication_point=1.0e308,
                communication_step_size=1.0e-308,
                no_set_fmu_state_prior_to_current_point=True,
            )
        assert host.get_float64((1,), 1) == pytest.approx((2.0,))

        first_result: FmiThreeWorkerDoStepResult = (
            host.set_numeric_values_and_do_step(
                float64_value_references=(1,),
                float64_values=(-1.0,),
                current_communication_point=0.0,
                communication_step_size=0.25,
                no_set_fmu_state_prior_to_current_point=True,
            )
        )
        assert first_result.last_successful_time == pytest.approx(0.25)
        with pytest.raises(RuntimeError, match="constant communication step size"):
            host.set_numeric_values_and_do_step(
                float64_value_references=(1,),
                float64_values=(9.0,),
                current_communication_point=0.25,
                communication_step_size=0.5,
                no_set_fmu_state_prior_to_current_point=True,
            )
        with pytest.raises(RuntimeError, match="not continuous"):
            host.set_numeric_values_and_do_step(
                float64_value_references=(1,),
                float64_values=(9.0,),
                current_communication_point=0.0,
                communication_step_size=0.25,
                no_set_fmu_state_prior_to_current_point=False,
            )
        assert host.get_float64((1,), 1) == pytest.approx((-1.0,))
    finally:
        host.close()
    assert host.is_closed()


def test_fmi_three_worker_host_closes_ready_instance_idempotently(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Close directly from READY and accept a repeated local close.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native test FMU.
    :return: None.
    """

    host: FmiThreeWorkerHost = _prepare_compiled_fmi_three_scalar_worker_host(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        limits=_create_worker_host_limits(60.0, 262144),
    )
    staging_root: Path = host.get_staging_root()
    try:
        host.start(
            instance_name="veragrid-fmi-three-supervised-ready-close",
            visible=False,
            debug_logging=False,
        )
        assert host.get_state() == FmiThreeWorkerHostState.READY
        host.close()
        host.close()
    finally:
        host.close()
    assert host.get_state() == FmiThreeWorkerHostState.CLOSED
    assert host.get_exit_code() == 0
    assert not staging_root.exists()


def test_fmi_three_worker_host_preserves_final_readable_values_after_termination_request(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Allow final reads while rejecting work after native termination request.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native test FMU.
    :return: None.
    """

    host: FmiThreeWorkerHost = _prepare_compiled_fmi_three_scalar_worker_host(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        limits=_create_worker_host_limits(60.0, 262144),
    )
    staging_root: Path = host.get_staging_root()
    try:
        host.start(
            instance_name="veragrid-fmi-three-termination-output",
            visible=False,
            debug_logging=False,
        )
        host.initialize(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_float64_value_references=(1,),
            initial_float64_values=(9.0,),
        )
        step_result: FmiThreeWorkerDoStepResult = host.do_step(
            current_communication_point=0.0,
            communication_step_size=0.25,
            no_set_fmu_state_prior_to_current_point=True,
        )

        assert step_result.terminate_simulation
        assert host.get_state() == (
            FmiThreeWorkerHostState.TERMINATION_REQUESTED
        )
        assert host.get_float64((0, 1, 2), 3) == pytest.approx(
            (0.25, 9.0, 9.25)
        )
        with pytest.raises(RuntimeError, match="SET_FLOAT64 requires Step Mode"):
            host.set_float64(value_references=(1,), values=(2.0,))
        with pytest.raises(RuntimeError, match="DO_STEP requires Step Mode"):
            host.do_step(
                current_communication_point=0.25,
                communication_step_size=0.25,
                no_set_fmu_state_prior_to_current_point=True,
            )
        assert host.get_state() == (
            FmiThreeWorkerHostState.TERMINATION_REQUESTED
        )
    finally:
        host.close()
    assert host.is_closed()
    assert not staging_root.exists()


def test_fmi_three_worker_host_rejects_invalid_initial_assignments_locally(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Keep a READY child alive after local initialization validation errors.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native test FMU.
    :return: None.
    """

    host: FmiThreeWorkerHost = _prepare_compiled_fmi_three_scalar_worker_host(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        limits=_create_worker_host_limits(60.0, 262144),
    )
    staging_root: Path = host.get_staging_root()
    try:
        host.start(
            instance_name="veragrid-fmi-three-initial-validation",
            visible=False,
            debug_logging=False,
        )
        process_id: int | None = host.get_process_id()
        with pytest.raises(ValueError, match="Initialization Mode"):
            host.initialize(
                start_time=0.0,
                stop_time=1.0,
                relative_tolerance=1.0e-6,
                initial_float64_value_references=(2,),
                initial_float64_values=(3.0,),
            )
        assert host.get_state() == FmiThreeWorkerHostState.READY
        assert host.get_process_id() == process_id
        assert staging_root.is_dir()
        with pytest.raises(ValueError, match="initial references and values must align"):
            host.initialize(
                start_time=0.0,
                stop_time=1.0,
                relative_tolerance=1.0e-6,
                initial_float64_value_references=(1,),
                initial_float64_values=tuple(),
            )
        assert host.get_state() == FmiThreeWorkerHostState.READY
        assert host.get_process_id() == process_id
        assert staging_root.is_dir()
    finally:
        host.close()
    assert host.is_closed()
    assert not staging_root.exists()


def test_fmi_three_worker_host_rejects_float64_output_write(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Fail closed when the parent requests a write to a declared output.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native test FMU.
    :return: None.
    """

    host: FmiThreeWorkerHost = _prepare_compiled_fmi_three_scalar_worker_host(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        limits=_create_worker_host_limits(60.0, 262144),
    )
    staging_root: Path = host.get_staging_root()
    try:
        host.start(
            instance_name="veragrid-fmi-three-output-write-rejection",
            visible=False,
            debug_logging=False,
        )
        host.initialize(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_float64_value_references=tuple(),
            initial_float64_values=tuple(),
        )
        with pytest.raises(ValueError, match="input or tunable parameter"):
            host.set_float64(value_references=(2,), values=(3.0,))
        assert host.get_state() == FmiThreeWorkerHostState.FAILED
        assert not staging_root.exists()
    finally:
        host.close()
    assert host.is_closed()


def test_fmi_three_worker_host_rejects_get_response_amplification_locally(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Keep the worker alive when a GET response cannot fit its frame.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native test FMU.
    :return: None.
    """

    limits: FmiThreeWorkerHostLimits = (
        FmiThreeWorkerHostLimits(
            maximum_frame_size=1024,
            maximum_float64_values_per_request=128,
            response_timeout_seconds=60.0,
            graceful_join_timeout_seconds=10.0,
            terminate_join_timeout_seconds=5.0,
            kill_join_timeout_seconds=5.0,
        )
    )
    host: FmiThreeWorkerHost = _prepare_compiled_fmi_three_scalar_worker_host(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        limits=limits,
    )
    try:
        host.start(
            instance_name="veragrid-fmi-three-get-capacity-rejection",
            visible=False,
            debug_logging=False,
        )
        host.initialize(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_float64_value_references=tuple(),
            initial_float64_values=tuple(),
        )
        oversized_references: tuple[int, ...] = tuple(range(126))
        with pytest.raises(ValueError, match="request or response exceeds"):
            host.get_float64(
                value_references=oversized_references,
                serialized_value_count=len(oversized_references),
            )
        assert host.get_state() == FmiThreeWorkerHostState.INITIALIZED
        assert host.get_process_id() is not None
    finally:
        host.close()
    assert host.is_closed()


def test_fmi_three_worker_host_releases_staging_after_frame_bound_failure(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Stop the spawned child when START cannot fit the configured frame.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native test FMU.
    :return: None.
    """

    host: FmiThreeWorkerHost = _prepare_compiled_fmi_three_scalar_worker_host(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        limits=_create_worker_host_limits(20.0, 32),
    )
    staging_root: Path = host.get_staging_root()
    try:
        with pytest.raises(RuntimeError, match="request transport failed"):
            host.start(
                instance_name="veragrid-fmi-three-frame-bound-failure",
                visible=False,
                debug_logging=False,
            )
        assert host.get_state() == FmiThreeWorkerHostState.FAILED
        assert host.get_exit_code() is not None
        assert not staging_root.exists()
    finally:
        host.close()
    assert host.is_closed()


def test_fmi_three_worker_host_enforces_start_response_deadline(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Terminate a real spawned worker that cannot answer a nanosecond deadline.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native test FMU.
    :return: None.
    """

    host: FmiThreeWorkerHost = _prepare_compiled_fmi_three_scalar_worker_host(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        limits=_create_worker_host_limits(1.0e-9, 262144),
    )
    staging_root: Path = host.get_staging_root()
    try:
        with pytest.raises(RuntimeError, match="response timed out"):
            host.start(
                instance_name="veragrid-fmi-three-start-timeout",
                visible=False,
                debug_logging=False,
            )
        assert host.get_state() == FmiThreeWorkerHostState.FAILED
        assert host.get_exit_code() is not None
        assert not staging_root.exists()
    finally:
        host.close()
    assert host.is_closed()


def test_fmi_three_worker_host_maps_child_archive_error_and_cleans_up(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Map a real child ARCHIVE response after staged-tree mutation.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native test FMU.
    :return: None.
    """

    host: FmiThreeWorkerHost = _prepare_compiled_fmi_three_scalar_worker_host(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        limits=_create_worker_host_limits(60.0, 262144),
    )
    staging_root: Path = host.get_staging_root()
    source_path: Path = host.get_staged_fmu_directory() / "sources" / "model.c"
    source_bytes: bytes = source_path.read_bytes()
    if source_bytes[-1:] == b" ":
        replacement_byte: bytes = b"\n"
    else:
        replacement_byte = b" "
    source_path.write_bytes(b"".join((source_bytes[:-1], replacement_byte)))
    try:
        with pytest.raises(ValueError, match="worker ARCHIVE"):
            host.start(
                instance_name="veragrid-fmi-three-child-archive-error",
                visible=False,
                debug_logging=False,
            )
        assert host.get_state() == FmiThreeWorkerHostState.FAILED
        assert host.get_exit_code() is not None
        assert not staging_root.exists()
    finally:
        host.close()
    assert host.is_closed()


def test_fmi_three_worker_host_fails_closed_after_exact_child_termination(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Detect a terminated READY child before the next lifecycle response.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native test FMU.
    :return: None.
    """

    host: FmiThreeWorkerHost = _prepare_compiled_fmi_three_scalar_worker_host(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        limits=_create_worker_host_limits(60.0, 262144),
    )
    staging_root: Path = host.get_staging_root()
    try:
        host.start(
            instance_name="veragrid-fmi-three-exact-child-termination",
            visible=False,
            debug_logging=False,
        )
        process_id: int | None = host.get_process_id()
        if process_id is not None:
            os.kill(process_id, signal.SIGTERM)
        else:
            raise AssertionError("The supervised worker has no process identifier")
        with pytest.raises(RuntimeError, match="worker"):
            host.initialize(
                start_time=0.0,
                stop_time=1.0,
                relative_tolerance=1.0e-6,
                initial_float64_value_references=tuple(),
                initial_float64_values=tuple(),
            )
        assert host.get_state() == FmiThreeWorkerHostState.FAILED
        assert host.get_exit_code() is not None
        assert not staging_root.exists()
    finally:
        host.close()
    assert host.is_closed()


def test_fmi_three_worker_host_limits_reject_unbounded_values() -> None:
    """Reject frame and timeout values that cannot form a finite contract.

    :return: None.
    """

    with pytest.raises(ValueError, match="maximum frame size"):
        _create_worker_host_limits(20.0, 262145)
    with pytest.raises(ValueError, match="response timeout"):
        _create_worker_host_limits(float("inf"), 262144)
