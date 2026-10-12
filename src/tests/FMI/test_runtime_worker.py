# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Spawn-based tests for the isolated FMI 3 scalar worker."""

from __future__ import annotations

from multiprocessing import get_context
from multiprocessing.connection import Connection
from multiprocessing.context import BaseContext
from multiprocessing.process import BaseProcess
from pathlib import Path

from VeraGridEngine.IO.fmu.model_description import (
    FmuModelDescription,
    read_fmu_model_description,
)
from VeraGridEngine.IO.fmu.Elements.protocol import (
    FmiThreeWorkerCompletedIntegratorStepRequest,
    FmiThreeWorkerConfigureFloat64Request,
    FmiThreeWorkerDoStepRequest,
    FmiThreeWorkerFailureKind,
    FmiThreeWorkerFloat64Values,
    FmiThreeWorkerGetFloat64Request,
    FmiThreeWorkerGetInt32Request,
    FmiThreeWorkerInitializationRequest,
    FmiThreeWorkerRequest,
    FmiThreeWorkerRequestKind,
    FmiThreeWorkerResponse,
    FmiThreeWorkerResponseKind,
    FmiThreeWorkerSetFloat64Request,
    FmiThreeWorkerSetInt32Request,
    FmiThreeWorkerSetTimeRequest,
    FmiThreeWorkerStartRequest,
    build_fmi_three_worker_staging_identity,
    decode_fmi_three_worker_response,
    encode_fmi_three_worker_request,
    receive_fmi_three_worker_frame,
    send_fmi_three_worker_frame,
    validate_fmi_three_worker_response_correlation,
)
from VeraGridEngine.IO.fmu.profile import (
    FmiThreeWorkerFloat64Profile,
)
from VeraGridEngine.IO.fmu.workers import (
    run_fmi_three_worker,
)
from VeraGridEngine.IO.fmu.staging import FmuStagingArea, stage_fmu_source
from VeraGridEngine.enumerations import FmuInterfaceMode


def _start_fmi_three_worker_process() -> tuple[BaseProcess, Connection, int]:
    """Start one child with a dedicated bounded bytes-only pipe.

    :return: Spawned process, parent endpoint, and shared frame-size bound.
    """

    process_context: BaseContext = get_context("spawn")
    parent_connection: Connection
    child_connection: Connection
    parent_connection, child_connection = process_context.Pipe(duplex=True)
    maximum_frame_size: int = 262144
    process: BaseProcess = process_context.Process(
        target=run_fmi_three_worker,
        args=(child_connection, maximum_frame_size, 64),
    )
    process.start()
    child_connection.close()
    return process, parent_connection, maximum_frame_size


def _stop_fmi_three_worker_process(process: BaseProcess) -> None:
    """Prove a test worker has stopped, escalating only for a stuck child.

    :param process: Worker process to join and, if necessary, stop.
    :return: None.
    """

    process.join(timeout=10.0)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5.0)
    else:
        pass
    if process.is_alive():
        process.kill()
        process.join(timeout=5.0)
    else:
        pass
    assert not process.is_alive()


def _exchange_worker_request(
    connection: Connection,
    request: FmiThreeWorkerRequest,
    expected_response_kind: FmiThreeWorkerResponseKind,
    maximum_frame_size: int,
) -> FmiThreeWorkerResponse:
    """Send one framed request and receive its bounded correlated response.

    :param connection: Parent endpoint for the worker under test.
    :param request: Typed request to encode.
    :param expected_response_kind: Successful transition expected by the test.
    :param maximum_frame_size: Bound shared with the spawned worker.
    :return: Decoded correlated response, including a permitted ERROR.
    """

    request_frame: bytes = encode_fmi_three_worker_request(
        request=request,
        maximum_frame_size=maximum_frame_size,
        maximum_float64_values_per_request=64,
    )
    send_fmi_three_worker_frame(
        connection=connection,
        frame=request_frame,
        maximum_frame_size=maximum_frame_size,
    )
    # Repeated Windows spawn and native-load checks reached 30 seconds under
    # suite load. This test-only deadline is separate from product host limits.
    assert connection.poll(60.0), "The FMI 3 worker did not answer before the test deadline"
    response_frame: bytes = receive_fmi_three_worker_frame(
        connection=connection,
        maximum_frame_size=maximum_frame_size,
    )
    response: FmiThreeWorkerResponse = decode_fmi_three_worker_response(
        frame=response_frame,
        maximum_frame_size=maximum_frame_size,
        maximum_float64_values_per_request=64,
    )
    validate_fmi_three_worker_response_correlation(
        response=response,
        expected_request_id=request.request_id,
        expected_response_kind=expected_response_kind,
    )
    return response


def _create_worker_start_request(
    metadata: FmuModelDescription,
    staging: FmuStagingArea,
    request_id: int,
    interface_mode: FmuInterfaceMode = FmuInterfaceMode.CO_SIMULATION,
) -> FmiThreeWorkerRequest:
    """Build START from the exact staged receipt and source metadata.

    :param metadata: Metadata parsed from the packaged test FMU.
    :param staging: Parent-owned private staging area.
    :param request_id: Positive request correlation identifier.
    :param interface_mode: Authenticated FMI 3 interface to instantiate.
    :return: Typed START request for the isolated worker.
    """

    if metadata.instantiation_token is not None:
        instantiation_token: str = metadata.instantiation_token
    else:
        raise AssertionError("The FMI 3 test fixture has no instantiation token")
    start: FmiThreeWorkerStartRequest = FmiThreeWorkerStartRequest(
        extracted_fmu_directory=staging.get_fmu_directory(),
        staging_identity=build_fmi_three_worker_staging_identity(
            staging.get_fmu_directory_receipt()
        ),
        instantiation_token=instantiation_token,
        model_identifier=metadata.get_model_identifier(interface_mode),
        instance_name="veragrid-fmi-three-worker-test",
        interface_mode=interface_mode,
        float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
        visible=False,
        debug_logging=False,
    )
    return FmiThreeWorkerRequest(
        request_id=request_id,
        kind=FmiThreeWorkerRequestKind.START,
        start=start,
        initialization=None,
    )


def _stage_compiled_fmi_three_fmu(
    compiled_fmu_path: Path,
) -> tuple[FmuModelDescription, FmuStagingArea]:
    """Parse and privately stage the generated host-native test FMU.

    :param compiled_fmu_path: Packaged host-native FMI 3 fixture.
    :return: Authoritative metadata and parent-owned staging area.
    """

    metadata: FmuModelDescription = read_fmu_model_description(compiled_fmu_path)
    if metadata.inspection_receipt is not None:
        staging: FmuStagingArea = stage_fmu_source(
            path=compiled_fmu_path,
            expected_receipt=metadata.inspection_receipt,
        )
    else:
        raise AssertionError("The FMI 3 test fixture has no inspection receipt")
    return metadata, staging


def test_fmi_three_worker_rejects_changed_staging_before_native_load(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Reject a same-size staged source mutation before loading its library.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native test FMU.
    :return: None.
    """

    metadata: FmuModelDescription
    staging: FmuStagingArea
    metadata, staging = _stage_compiled_fmi_three_fmu(
        compiled_fmi_three_scalar_co_simulation_fmu
    )
    start_request: FmiThreeWorkerRequest = _create_worker_start_request(
        metadata,
        staging,
        21,
    )
    source_path: Path = staging.get_fmu_directory() / "sources" / "model.c"
    source_bytes: bytes = source_path.read_bytes()
    if source_bytes[-1:] == b" ":
        replacement_byte: bytes = b"\n"
    else:
        replacement_byte = b" "
    source_path.write_bytes(b"".join((source_bytes[:-1], replacement_byte)))
    process: BaseProcess
    connection: Connection
    maximum_frame_size: int
    process, connection, maximum_frame_size = _start_fmi_three_worker_process()
    try:
        response: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=start_request,
            expected_response_kind=FmiThreeWorkerResponseKind.READY,
            maximum_frame_size=maximum_frame_size,
        )
        assert response.kind == FmiThreeWorkerResponseKind.ERROR
        assert response.failure_kind == FmiThreeWorkerFailureKind.ARCHIVE
    finally:
        connection.close()
        _stop_fmi_three_worker_process(process)
        staging.close()
    assert process.exitcode == 0


def test_fmi_three_worker_runs_model_exchange_continuous_time_lifecycle(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Construct native ``FMU3Model`` and exercise the bounded ME commands.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated dual-interface
        host-native test FMU.
    :return: None.
    """

    metadata: FmuModelDescription
    staging: FmuStagingArea
    metadata, staging = _stage_compiled_fmi_three_fmu(
        compiled_fmi_three_scalar_co_simulation_fmu
    )
    process: BaseProcess
    connection: Connection
    maximum_frame_size: int
    process, connection, maximum_frame_size = _start_fmi_three_worker_process()
    try:
        ready: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=_create_worker_start_request(
                metadata,
                staging,
                91,
                interface_mode=FmuInterfaceMode.MODEL_EXCHANGE,
            ),
            expected_response_kind=FmiThreeWorkerResponseKind.READY,
            maximum_frame_size=maximum_frame_size,
        )
        assert ready.kind == FmiThreeWorkerResponseKind.READY
        initialize_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=92,
            kind=FmiThreeWorkerRequestKind.INITIALIZE,
            start=None,
            initialization=FmiThreeWorkerInitializationRequest(
                start_time=0.0,
                stop_time=1.0,
                relative_tolerance=1.0e-6,
                    initial_float64_value_references=tuple(),
                    initial_float64_values=tuple(),
                    initial_int32_value_references=tuple(),
                    initial_int32_values=tuple(),
                    maximum_value_count=64,
            ),
        )
        initialized: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=initialize_request,
            expected_response_kind=FmiThreeWorkerResponseKind.INITIALIZED,
            maximum_frame_size=maximum_frame_size,
        )
        assert initialized.kind == FmiThreeWorkerResponseKind.INITIALIZED

        discrete_states_updated: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=120,
                kind=FmiThreeWorkerRequestKind.UPDATE_DISCRETE_STATES,
                start=None,
                initialization=None,
            ),
            expected_response_kind=(
                FmiThreeWorkerResponseKind.DISCRETE_STATES_UPDATED
            ),
            maximum_frame_size=maximum_frame_size,
        )
        if discrete_states_updated.discrete_states_result is not None:
            assert not (
                discrete_states_updated.discrete_states_result.discrete_states_need_update
            )
            assert not discrete_states_updated.discrete_states_result.terminate_simulation
            assert not (
                discrete_states_updated.discrete_states_result.next_event_time_defined
            )
        else:
            raise AssertionError("Model Exchange discrete-state result is missing")
        continuous_time_entered: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=121,
                kind=FmiThreeWorkerRequestKind.ENTER_CONTINUOUS_TIME_MODE,
                start=None,
                initialization=None,
            ),
            expected_response_kind=(
                FmiThreeWorkerResponseKind.CONTINUOUS_TIME_MODE_ENTERED
            ),
            maximum_frame_size=maximum_frame_size,
        )
        assert (
            continuous_time_entered.kind
            == FmiThreeWorkerResponseKind.CONTINUOUS_TIME_MODE_ENTERED
        )
        checkpoint_saved: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=130,
                kind=FmiThreeWorkerRequestKind.SAVE_CHECKPOINT,
                start=None,
                initialization=None,
            ),
            expected_response_kind=FmiThreeWorkerResponseKind.CHECKPOINT_SAVED,
            maximum_frame_size=maximum_frame_size,
        )
        assert checkpoint_saved.kind == FmiThreeWorkerResponseKind.CHECKPOINT_SAVED

        # Bind the input before evaluating the synthetic state equation so the
        # raw protocol test proves both operands cross the process boundary.
        set_input_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=93,
            kind=FmiThreeWorkerRequestKind.SET_FLOAT64,
            start=None,
            initialization=None,
            set_float64=FmiThreeWorkerSetFloat64Request(
                value_references=(1,),
                values=(2.0,),
                maximum_value_count=64,
            ),
        )
        input_set: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=set_input_request,
            expected_response_kind=FmiThreeWorkerResponseKind.FLOAT64_SET,
            maximum_frame_size=maximum_frame_size,
        )
        assert input_set.kind == FmiThreeWorkerResponseKind.FLOAT64_SET

        set_time_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=94,
            kind=FmiThreeWorkerRequestKind.SET_TIME,
            start=None,
            initialization=None,
            set_time=FmiThreeWorkerSetTimeRequest(time_value=0.25),
        )
        time_set: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=set_time_request,
            expected_response_kind=FmiThreeWorkerResponseKind.TIME_SET,
            maximum_frame_size=maximum_frame_size,
        )
        assert time_set.kind == FmiThreeWorkerResponseKind.TIME_SET

        set_states_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=95,
            kind=FmiThreeWorkerRequestKind.SET_CONTINUOUS_STATES,
            start=None,
            initialization=None,
            continuous_states=FmiThreeWorkerFloat64Values(
                values=(3.0,),
                maximum_value_count=64,
            ),
        )
        states_set: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=set_states_request,
            expected_response_kind=(
                FmiThreeWorkerResponseKind.CONTINUOUS_STATES_SET
            ),
            maximum_frame_size=maximum_frame_size,
        )
        assert states_set.kind == FmiThreeWorkerResponseKind.CONTINUOUS_STATES_SET

        vector_request_kind: FmiThreeWorkerRequestKind
        expected_vector_response: FmiThreeWorkerResponseKind
        expected_vector_values: tuple[float, ...]
        for vector_request_kind, expected_vector_response, expected_vector_values in (
            (
                FmiThreeWorkerRequestKind.GET_CONTINUOUS_STATES,
                FmiThreeWorkerResponseKind.CONTINUOUS_STATES_VALUES,
                (3.0,),
            ),
            (
                FmiThreeWorkerRequestKind.GET_DERIVATIVES,
                FmiThreeWorkerResponseKind.DERIVATIVE_VALUES,
                (-1.0,),
            ),
            (
                FmiThreeWorkerRequestKind.GET_EVENT_INDICATORS,
                FmiThreeWorkerResponseKind.EVENT_INDICATOR_VALUES,
                (0.5,),
            ),
            (
                FmiThreeWorkerRequestKind.GET_NOMINALS_OF_CONTINUOUS_STATES,
                FmiThreeWorkerResponseKind.CONTINUOUS_STATE_NOMINAL_VALUES,
                (1.0,),
            ),
        ):
            vector_response: FmiThreeWorkerResponse = _exchange_worker_request(
                connection=connection,
                request=FmiThreeWorkerRequest(
                    request_id=95 + int(vector_request_kind),
                    kind=vector_request_kind,
                    start=None,
                    initialization=None,
                ),
                expected_response_kind=expected_vector_response,
                maximum_frame_size=maximum_frame_size,
            )
            if vector_response.float64_values is not None:
                assert vector_response.float64_values.values == expected_vector_values
            else:
                raise AssertionError("Model Exchange vector response is missing")

        checkpoint_restored: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=131,
                kind=FmiThreeWorkerRequestKind.RESTORE_CHECKPOINT,
                start=None,
                initialization=None,
            ),
            expected_response_kind=FmiThreeWorkerResponseKind.CHECKPOINT_RESTORED,
            maximum_frame_size=maximum_frame_size,
        )
        assert (
            checkpoint_restored.kind
            == FmiThreeWorkerResponseKind.CHECKPOINT_RESTORED
        )
        restored_states: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=132,
                kind=FmiThreeWorkerRequestKind.GET_CONTINUOUS_STATES,
                start=None,
                initialization=None,
            ),
            expected_response_kind=(
                FmiThreeWorkerResponseKind.CONTINUOUS_STATES_VALUES
            ),
            maximum_frame_size=maximum_frame_size,
        )
        if restored_states.float64_values is not None:
            assert restored_states.float64_values.values == (1.0,)
        else:
            raise AssertionError("Restored Model Exchange state is missing")
        checkpoint_discarded: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=133,
                kind=FmiThreeWorkerRequestKind.DISCARD_CHECKPOINT,
                start=None,
                initialization=None,
            ),
            expected_response_kind=(
                FmiThreeWorkerResponseKind.CHECKPOINT_DISCARDED
            ),
            maximum_frame_size=maximum_frame_size,
        )
        assert (
            checkpoint_discarded.kind
            == FmiThreeWorkerResponseKind.CHECKPOINT_DISCARDED
        )

        completed_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=110,
            kind=FmiThreeWorkerRequestKind.COMPLETED_INTEGRATOR_STEP,
            start=None,
            initialization=None,
            completed_integrator_step=(
                FmiThreeWorkerCompletedIntegratorStepRequest(
                    no_set_fmu_state_prior_to_current_point=True
                )
            ),
        )
        completed: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=completed_request,
            expected_response_kind=(
                FmiThreeWorkerResponseKind.INTEGRATOR_STEP_COMPLETED
            ),
            maximum_frame_size=maximum_frame_size,
        )
        if completed.completed_integrator_step_result is not None:
            assert not completed.completed_integrator_step_result.enter_event_mode
            assert not completed.completed_integrator_step_result.terminate_simulation
        else:
            raise AssertionError("Model Exchange integrator result is missing")

        # The importer may detect a time, state, input, or clock event without
        # a completedIntegratorStep request from the FMU.
        direct_event_entered: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=111,
                kind=FmiThreeWorkerRequestKind.ENTER_EVENT_MODE,
                start=None,
                initialization=None,
            ),
            expected_response_kind=FmiThreeWorkerResponseKind.EVENT_MODE_ENTERED,
            maximum_frame_size=maximum_frame_size,
        )
        assert direct_event_entered.kind == FmiThreeWorkerResponseKind.EVENT_MODE_ENTERED
        direct_event_update: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=112,
                kind=FmiThreeWorkerRequestKind.UPDATE_DISCRETE_STATES,
                start=None,
                initialization=None,
            ),
            expected_response_kind=(
                FmiThreeWorkerResponseKind.DISCRETE_STATES_UPDATED
            ),
            maximum_frame_size=maximum_frame_size,
        )
        assert direct_event_update.kind == (
            FmiThreeWorkerResponseKind.DISCRETE_STATES_UPDATED
        )
        direct_continuous_time: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=113,
                kind=FmiThreeWorkerRequestKind.ENTER_CONTINUOUS_TIME_MODE,
                start=None,
                initialization=None,
            ),
            expected_response_kind=(
                FmiThreeWorkerResponseKind.CONTINUOUS_TIME_MODE_ENTERED
            ),
            maximum_frame_size=maximum_frame_size,
        )
        assert direct_continuous_time.kind == (
            FmiThreeWorkerResponseKind.CONTINUOUS_TIME_MODE_ENTERED
        )

        closed: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=114,
                kind=FmiThreeWorkerRequestKind.CLOSE,
                start=None,
                initialization=None,
            ),
            expected_response_kind=FmiThreeWorkerResponseKind.CLOSED,
            maximum_frame_size=maximum_frame_size,
        )
        assert closed.kind == FmiThreeWorkerResponseKind.CLOSED
        _stop_fmi_three_worker_process(process)
    finally:
        connection.close()
        if process.is_alive():
            _stop_fmi_three_worker_process(process)
        else:
            pass
        staging.close()
    assert process.exitcode == 0


def test_fmi_three_worker_rejects_variable_step_size_when_not_supported(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Enforce constant step size from independently parsed capabilities.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native test FMU.
    :return: None.
    """

    metadata: FmuModelDescription
    staging: FmuStagingArea
    metadata, staging = _stage_compiled_fmi_three_fmu(
        compiled_fmi_three_scalar_co_simulation_fmu
    )
    process: BaseProcess
    connection: Connection
    maximum_frame_size: int
    process, connection, maximum_frame_size = _start_fmi_three_worker_process()
    try:
        ready: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=_create_worker_start_request(metadata, staging, 81),
            expected_response_kind=FmiThreeWorkerResponseKind.READY,
            maximum_frame_size=maximum_frame_size,
        )
        assert ready.kind == FmiThreeWorkerResponseKind.READY
        initialize_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=82,
            kind=FmiThreeWorkerRequestKind.INITIALIZE,
            start=None,
            initialization=FmiThreeWorkerInitializationRequest(
                start_time=0.0,
                stop_time=1.0,
                relative_tolerance=1.0e-6,
                    initial_float64_value_references=tuple(),
                    initial_float64_values=tuple(),
                    initial_int32_value_references=tuple(),
                    initial_int32_values=tuple(),
                    maximum_value_count=64,
            ),
        )
        initialized: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=initialize_request,
            expected_response_kind=FmiThreeWorkerResponseKind.INITIALIZED,
            maximum_frame_size=maximum_frame_size,
        )
        assert initialized.kind == FmiThreeWorkerResponseKind.INITIALIZED
        first_step_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=83,
            kind=FmiThreeWorkerRequestKind.DO_STEP,
            start=None,
            initialization=None,
            do_step=FmiThreeWorkerDoStepRequest(
                current_communication_point=0.0,
                communication_step_size=0.25,
                no_set_fmu_state_prior_to_current_point=True,
            ),
        )
        first_step: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=first_step_request,
            expected_response_kind=FmiThreeWorkerResponseKind.STEP_COMPLETED,
            maximum_frame_size=maximum_frame_size,
        )
        assert first_step.kind == FmiThreeWorkerResponseKind.STEP_COMPLETED
        second_step_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=84,
            kind=FmiThreeWorkerRequestKind.DO_STEP,
            start=None,
            initialization=None,
            do_step=FmiThreeWorkerDoStepRequest(
                current_communication_point=0.25,
                communication_step_size=0.5,
                no_set_fmu_state_prior_to_current_point=True,
            ),
        )
        rejected_step: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=second_step_request,
            expected_response_kind=FmiThreeWorkerResponseKind.STEP_COMPLETED,
            maximum_frame_size=maximum_frame_size,
        )
        assert rejected_step.kind == FmiThreeWorkerResponseKind.ERROR
        assert rejected_step.failure_kind == FmiThreeWorkerFailureKind.LIFECYCLE
        assert rejected_step.error_message == (
            "FMI 3 worker requires a constant communication step size"
        )
        _stop_fmi_three_worker_process(process)
    finally:
        connection.close()
        if process.is_alive():
            _stop_fmi_three_worker_process(process)
        else:
            pass
        staging.close()
    assert process.exitcode == 0


def test_fmi_three_worker_rejects_initialization_before_start() -> None:
    """Fail closed when INITIALIZE arrives before native construction.

    :return: None.
    """

    process: BaseProcess
    connection: Connection
    maximum_frame_size: int
    process, connection, maximum_frame_size = _start_fmi_three_worker_process()
    try:
        request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=31,
            kind=FmiThreeWorkerRequestKind.INITIALIZE,
            start=None,
            initialization=FmiThreeWorkerInitializationRequest(
                start_time=0.0,
                stop_time=None,
                relative_tolerance=None,
                    initial_float64_value_references=tuple(),
                    initial_float64_values=tuple(),
                    initial_int32_value_references=tuple(),
                    initial_int32_values=tuple(),
                    maximum_value_count=64,
            ),
        )
        response: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=request,
            expected_response_kind=FmiThreeWorkerResponseKind.INITIALIZED,
            maximum_frame_size=maximum_frame_size,
        )
        assert response.kind == FmiThreeWorkerResponseKind.ERROR
        assert response.failure_kind == FmiThreeWorkerFailureKind.LIFECYCLE
    finally:
        connection.close()
        _stop_fmi_three_worker_process(process)
    assert process.exitcode == 0


def test_fmi_three_worker_rejects_wrong_start_token_before_native_load(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Reject a parent token that differs from staged metadata.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native test FMU.
    :return: None.
    """

    metadata: FmuModelDescription
    staging: FmuStagingArea
    metadata, staging = _stage_compiled_fmi_three_fmu(
        compiled_fmi_three_scalar_co_simulation_fmu
    )
    valid_request: FmiThreeWorkerRequest = _create_worker_start_request(
        metadata,
        staging,
        41,
    )
    if valid_request.start is not None:
        valid_start: FmiThreeWorkerStartRequest = valid_request.start
    else:
        raise AssertionError("The test START request has no typed body")
    wrong_start: FmiThreeWorkerStartRequest = FmiThreeWorkerStartRequest(
        extracted_fmu_directory=valid_start.extracted_fmu_directory,
        staging_identity=valid_start.staging_identity,
        instantiation_token="wrong-veragrid-worker-token",
        model_identifier=valid_start.model_identifier,
        instance_name=valid_start.instance_name,
        interface_mode=FmuInterfaceMode.CO_SIMULATION,
        float64_profile=valid_start.float64_profile,
        visible=valid_start.visible,
        debug_logging=valid_start.debug_logging,
    )
    wrong_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=41,
        kind=FmiThreeWorkerRequestKind.START,
        start=wrong_start,
        initialization=None,
    )
    process: BaseProcess
    connection: Connection
    maximum_frame_size: int
    process, connection, maximum_frame_size = _start_fmi_three_worker_process()
    try:
        response: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=wrong_request,
            expected_response_kind=FmiThreeWorkerResponseKind.READY,
            maximum_frame_size=maximum_frame_size,
        )
        assert response.kind == FmiThreeWorkerResponseKind.ERROR
        assert response.failure_kind == FmiThreeWorkerFailureKind.LIFECYCLE
    finally:
        connection.close()
        _stop_fmi_three_worker_process(process)
        staging.close()
    assert process.exitcode == 0


def test_fmi_three_worker_rejects_undeclared_interface_before_native_load(
    compiled_fmi_three_constant_array_co_simulation_fmu: Path,
) -> None:
    """Reject Model Exchange when only Co-Simulation is declared.

    :param compiled_fmi_three_constant_array_co_simulation_fmu: Generated
        Co-Simulation-only host-native test FMU.
    :return: None.
    """

    metadata: FmuModelDescription
    staging: FmuStagingArea
    metadata, staging = _stage_compiled_fmi_three_fmu(
        compiled_fmi_three_constant_array_co_simulation_fmu
    )
    valid_request: FmiThreeWorkerRequest = _create_worker_start_request(
        metadata,
        staging,
        42,
    )
    if valid_request.start is not None:
        valid_start: FmiThreeWorkerStartRequest = valid_request.start
    else:
        raise AssertionError("The test START request has no typed body")
    wrong_start: FmiThreeWorkerStartRequest = FmiThreeWorkerStartRequest(
        extracted_fmu_directory=valid_start.extracted_fmu_directory,
        staging_identity=valid_start.staging_identity,
        instantiation_token=valid_start.instantiation_token,
        model_identifier=valid_start.model_identifier,
        instance_name=valid_start.instance_name,
        interface_mode=FmuInterfaceMode.MODEL_EXCHANGE,
        float64_profile=valid_start.float64_profile,
        visible=valid_start.visible,
        debug_logging=valid_start.debug_logging,
    )
    process: BaseProcess
    connection: Connection
    maximum_frame_size: int
    process, connection, maximum_frame_size = _start_fmi_three_worker_process()
    try:
        response: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=42,
                kind=FmiThreeWorkerRequestKind.START,
                start=wrong_start,
                initialization=None,
            ),
            expected_response_kind=FmiThreeWorkerResponseKind.READY,
            maximum_frame_size=maximum_frame_size,
        )
        assert response.kind == FmiThreeWorkerResponseKind.ERROR
        assert response.failure_kind == FmiThreeWorkerFailureKind.LIFECYCLE
    finally:
        connection.close()
        _stop_fmi_three_worker_process(process)
        staging.close()
    assert process.exitcode == 0


def test_fmi_three_worker_rejects_repeated_start(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Treat a second START as a terminal lifecycle violation.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native test FMU.
    :return: None.
    """

    metadata: FmuModelDescription
    staging: FmuStagingArea
    metadata, staging = _stage_compiled_fmi_three_fmu(
        compiled_fmi_three_scalar_co_simulation_fmu
    )
    process: BaseProcess
    connection: Connection
    maximum_frame_size: int
    process, connection, maximum_frame_size = _start_fmi_three_worker_process()
    try:
        ready: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=_create_worker_start_request(metadata, staging, 51),
            expected_response_kind=FmiThreeWorkerResponseKind.READY,
            maximum_frame_size=maximum_frame_size,
        )
        assert ready.kind == FmiThreeWorkerResponseKind.READY
        repeated: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=_create_worker_start_request(metadata, staging, 52),
            expected_response_kind=FmiThreeWorkerResponseKind.READY,
            maximum_frame_size=maximum_frame_size,
        )
        assert repeated.kind == FmiThreeWorkerResponseKind.ERROR
        assert repeated.failure_kind == FmiThreeWorkerFailureKind.LIFECYCLE
    finally:
        connection.close()
        _stop_fmi_three_worker_process(process)
        staging.close()
    assert process.exitcode == 0


def test_fmi_three_worker_releases_ready_instance_after_parent_eof(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Release native ownership when the parent closes after START.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native test FMU.
    :return: None.
    """

    metadata: FmuModelDescription
    staging: FmuStagingArea
    metadata, staging = _stage_compiled_fmi_three_fmu(
        compiled_fmi_three_scalar_co_simulation_fmu
    )
    process: BaseProcess
    connection: Connection
    maximum_frame_size: int
    process, connection, maximum_frame_size = _start_fmi_three_worker_process()
    try:
        response: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=_create_worker_start_request(metadata, staging, 61),
            expected_response_kind=FmiThreeWorkerResponseKind.READY,
            maximum_frame_size=maximum_frame_size,
        )
        assert response.kind == FmiThreeWorkerResponseKind.READY
        connection.close()
        _stop_fmi_three_worker_process(process)
    finally:
        connection.close()
        if process.is_alive():
            _stop_fmi_three_worker_process(process)
        else:
            pass
        staging.close()
    assert process.exitcode == 0


def test_fmi_three_worker_child_acl_rejects_initial_output_assignment(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Reject a calculated output through the independently parsed child ACL.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native test FMU.
    :return: None.
    """

    metadata: FmuModelDescription
    staging: FmuStagingArea
    metadata, staging = _stage_compiled_fmi_three_fmu(
        compiled_fmi_three_scalar_co_simulation_fmu
    )
    process: BaseProcess
    connection: Connection
    maximum_frame_size: int
    process, connection, maximum_frame_size = _start_fmi_three_worker_process()
    try:
        ready: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=_create_worker_start_request(metadata, staging, 91),
            expected_response_kind=FmiThreeWorkerResponseKind.READY,
            maximum_frame_size=maximum_frame_size,
        )
        assert ready.kind == FmiThreeWorkerResponseKind.READY
        rejected_initialization: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=92,
                kind=FmiThreeWorkerRequestKind.INITIALIZE,
                start=None,
                initialization=FmiThreeWorkerInitializationRequest(
                    start_time=0.0,
                    stop_time=1.0,
                    relative_tolerance=1.0e-6,
                        initial_float64_value_references=(2,),
                        initial_float64_values=(3.0,),
                        initial_int32_value_references=tuple(),
                        initial_int32_values=tuple(),
                        maximum_value_count=64,
                ),
            ),
            expected_response_kind=FmiThreeWorkerResponseKind.INITIALIZED,
            maximum_frame_size=maximum_frame_size,
        )
        assert rejected_initialization.kind == FmiThreeWorkerResponseKind.ERROR
        assert (
            rejected_initialization.failure_kind
            == FmiThreeWorkerFailureKind.VARIABLE_ACCESS
        )
        _stop_fmi_three_worker_process(process)
    finally:
        connection.close()
        if process.is_alive():
            _stop_fmi_three_worker_process(process)
        else:
            pass
        staging.close()
    assert process.exitcode == 0


def test_fmi_three_worker_child_acl_rejects_configuration_input_assignment(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Reject a normal input through the independently parsed configuration ACL.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated native fixture.
    :return: None.
    """

    metadata: FmuModelDescription
    staging: FmuStagingArea
    metadata, staging = _stage_compiled_fmi_three_fmu(
        compiled_fmi_three_scalar_co_simulation_fmu
    )
    process: BaseProcess
    connection: Connection
    maximum_frame_size: int
    process, connection, maximum_frame_size = _start_fmi_three_worker_process()
    try:
        ready: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=_create_worker_start_request(metadata, staging, 93),
            expected_response_kind=FmiThreeWorkerResponseKind.READY,
            maximum_frame_size=maximum_frame_size,
        )
        assert ready.kind == FmiThreeWorkerResponseKind.READY
        rejected_configuration: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=94,
                kind=FmiThreeWorkerRequestKind.CONFIGURE_FLOAT64,
                start=None,
                initialization=None,
                configuration=FmiThreeWorkerConfigureFloat64Request(
                    value_references=(1,),
                    values=(2.0,),
                    maximum_value_count=64,
                ),
            ),
            expected_response_kind=FmiThreeWorkerResponseKind.CONFIGURED,
            maximum_frame_size=maximum_frame_size,
        )
        assert rejected_configuration.kind == FmiThreeWorkerResponseKind.ERROR
        assert (
            rejected_configuration.failure_kind
            == FmiThreeWorkerFailureKind.VARIABLE_ACCESS
        )
        _stop_fmi_three_worker_process(process)
    finally:
        connection.close()
        if process.is_alive():
            _stop_fmi_three_worker_process(process)
        else:
            pass
        staging.close()
    assert process.exitcode == 0


def test_fmi_three_worker_rejects_get_after_set_before_step(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Enforce the Step Mode GET-before-SET ordering inside the child.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated host-native test FMU.
    :return: None.
    """

    metadata: FmuModelDescription
    staging: FmuStagingArea
    metadata, staging = _stage_compiled_fmi_three_fmu(
        compiled_fmi_three_scalar_co_simulation_fmu
    )
    process: BaseProcess
    connection: Connection
    maximum_frame_size: int
    process, connection, maximum_frame_size = _start_fmi_three_worker_process()
    try:
        ready: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=_create_worker_start_request(metadata, staging, 71),
            expected_response_kind=FmiThreeWorkerResponseKind.READY,
            maximum_frame_size=maximum_frame_size,
        )
        assert ready.kind == FmiThreeWorkerResponseKind.READY
        initialize_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=72,
            kind=FmiThreeWorkerRequestKind.INITIALIZE,
            start=None,
            initialization=FmiThreeWorkerInitializationRequest(
                start_time=0.0,
                stop_time=1.0,
                relative_tolerance=1.0e-6,
                    initial_float64_value_references=tuple(),
                    initial_float64_values=tuple(),
                    initial_int32_value_references=tuple(),
                    initial_int32_values=tuple(),
                    maximum_value_count=64,
            ),
        )
        initialized: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=initialize_request,
            expected_response_kind=FmiThreeWorkerResponseKind.INITIALIZED,
            maximum_frame_size=maximum_frame_size,
        )
        assert initialized.kind == FmiThreeWorkerResponseKind.INITIALIZED
        set_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=73,
            kind=FmiThreeWorkerRequestKind.SET_FLOAT64,
            start=None,
            initialization=None,
            set_float64=FmiThreeWorkerSetFloat64Request(
                value_references=(1,),
                values=(2.0,),
                maximum_value_count=64,
            ),
        )
        float64_set: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=set_request,
            expected_response_kind=FmiThreeWorkerResponseKind.FLOAT64_SET,
            maximum_frame_size=maximum_frame_size,
        )
        assert float64_set.kind == FmiThreeWorkerResponseKind.FLOAT64_SET
        get_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=74,
            kind=FmiThreeWorkerRequestKind.GET_FLOAT64,
            start=None,
            initialization=None,
            get_float64=FmiThreeWorkerGetFloat64Request(
                value_references=(2,),
                serialized_value_count=1,
                maximum_value_count=64,
            ),
        )
        rejected_get: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=get_request,
            expected_response_kind=FmiThreeWorkerResponseKind.FLOAT64_VALUES,
            maximum_frame_size=maximum_frame_size,
        )
        assert rejected_get.kind == FmiThreeWorkerResponseKind.ERROR
        assert rejected_get.failure_kind == FmiThreeWorkerFailureKind.LIFECYCLE
        assert rejected_get.error_message == (
            "FMI 3 worker GET_FLOAT64 must precede input writes at the current "
            "communication point"
        )
        _stop_fmi_three_worker_process(process)
    finally:
        connection.close()
        if process.is_alive():
            _stop_fmi_three_worker_process(process)
        else:
            pass
        staging.close()
    assert process.exitcode == 0


def test_worker_int32_access_matrix_and_terminal_failures(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Enforce scalar Int32 lifecycle matrices inside the isolated worker.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Generated dual-interface
        native test FMU.
    :return: None.
    """

    metadata: FmuModelDescription
    staging: FmuStagingArea
    metadata, staging = _stage_compiled_fmi_three_fmu(
        compiled_fmi_three_scalar_co_simulation_fmu
    )
    process: BaseProcess
    connection: Connection
    maximum_frame_size: int
    process, connection, maximum_frame_size = _start_fmi_three_worker_process()
    try:
        _exchange_worker_request(
            connection=connection,
            request=_create_worker_start_request(metadata, staging, 101),
            expected_response_kind=FmiThreeWorkerResponseKind.READY,
            maximum_frame_size=maximum_frame_size,
        )
        _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=102,
                kind=FmiThreeWorkerRequestKind.INITIALIZE,
                start=None,
                initialization=FmiThreeWorkerInitializationRequest(
                    start_time=0.0,
                    stop_time=1.0,
                    relative_tolerance=1.0e-6,
                    initial_float64_value_references=tuple(),
                    initial_float64_values=tuple(),
                    initial_int32_value_references=(7,),
                    initial_int32_values=(-2,),
                    maximum_value_count=64,
                ),
            ),
            expected_response_kind=FmiThreeWorkerResponseKind.INITIALIZED,
            maximum_frame_size=maximum_frame_size,
        )
        initial_values: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=103,
                kind=FmiThreeWorkerRequestKind.GET_INT32,
                start=None,
                initialization=None,
                get_int32=FmiThreeWorkerGetInt32Request(
                    value_references=(7, 8),
                    maximum_value_count=64,
                ),
            ),
            expected_response_kind=FmiThreeWorkerResponseKind.INT32_VALUES,
            maximum_frame_size=maximum_frame_size,
        )
        if initial_values.int32_values is not None:
            assert initial_values.int32_values.values == (-2, 0)
        else:
            raise AssertionError("Worker omitted the typed Int32 response")

        # Co-Simulation accepts repeated typed writes in the shared pending state.
        request_id: int
        int32_value: int
        for request_id, int32_value in ((104, -3), (105, 4)):
            int32_set: FmiThreeWorkerResponse = _exchange_worker_request(
                connection=connection,
                request=FmiThreeWorkerRequest(
                    request_id=request_id,
                    kind=FmiThreeWorkerRequestKind.SET_INT32,
                    start=None,
                    initialization=None,
                    set_int32=FmiThreeWorkerSetInt32Request(
                        value_references=(7,),
                        values=(int32_value,),
                        maximum_value_count=64,
                    ),
                ),
                expected_response_kind=FmiThreeWorkerResponseKind.INT32_SET,
                maximum_frame_size=maximum_frame_size,
            )
            assert int32_set.kind == FmiThreeWorkerResponseKind.INT32_SET
        rejected_pending_get: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=106,
                kind=FmiThreeWorkerRequestKind.GET_INT32,
                start=None,
                initialization=None,
                get_int32=FmiThreeWorkerGetInt32Request(
                    value_references=(8,),
                    maximum_value_count=64,
                ),
            ),
            expected_response_kind=FmiThreeWorkerResponseKind.INT32_VALUES,
            maximum_frame_size=maximum_frame_size,
        )
        assert rejected_pending_get.kind == FmiThreeWorkerResponseKind.ERROR
        assert (
            rejected_pending_get.failure_kind
            == FmiThreeWorkerFailureKind.LIFECYCLE
        )
        _stop_fmi_three_worker_process(process)
    finally:
        connection.close()
        if process.is_alive():
            _stop_fmi_three_worker_process(process)
        else:
            pass

    process, connection, maximum_frame_size = _start_fmi_three_worker_process()
    try:
        _exchange_worker_request(
            connection=connection,
            request=_create_worker_start_request(
                metadata,
                staging,
                111,
                interface_mode=FmuInterfaceMode.MODEL_EXCHANGE,
            ),
            expected_response_kind=FmiThreeWorkerResponseKind.READY,
            maximum_frame_size=maximum_frame_size,
        )
        _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=112,
                kind=FmiThreeWorkerRequestKind.INITIALIZE,
                start=None,
                initialization=FmiThreeWorkerInitializationRequest(
                    start_time=0.0,
                    stop_time=1.0,
                    relative_tolerance=1.0e-6,
                    initial_float64_value_references=tuple(),
                    initial_float64_values=tuple(),
                    initial_int32_value_references=(7,),
                    initial_int32_values=(-2,),
                    maximum_value_count=64,
                ),
            ),
            expected_response_kind=FmiThreeWorkerResponseKind.INITIALIZED,
            maximum_frame_size=maximum_frame_size,
        )
        _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=113,
                kind=FmiThreeWorkerRequestKind.SET_INT32,
                start=None,
                initialization=None,
                set_int32=FmiThreeWorkerSetInt32Request(
                    value_references=(7,),
                    values=(6,),
                    maximum_value_count=64,
                ),
            ),
            expected_response_kind=FmiThreeWorkerResponseKind.INT32_SET,
            maximum_frame_size=maximum_frame_size,
        )
        event_values: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=114,
                kind=FmiThreeWorkerRequestKind.GET_INT32,
                start=None,
                initialization=None,
                get_int32=FmiThreeWorkerGetInt32Request(
                    value_references=(7,),
                    maximum_value_count=64,
                ),
            ),
            expected_response_kind=FmiThreeWorkerResponseKind.INT32_VALUES,
            maximum_frame_size=maximum_frame_size,
        )
        if event_values.int32_values is not None:
            assert event_values.int32_values.values == (6,)
        else:
            raise AssertionError("Worker omitted Event Mode Int32 values")
        _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=115,
                kind=FmiThreeWorkerRequestKind.ENTER_CONTINUOUS_TIME_MODE,
                start=None,
                initialization=None,
            ),
            expected_response_kind=(
                FmiThreeWorkerResponseKind.CONTINUOUS_TIME_MODE_ENTERED
            ),
            maximum_frame_size=maximum_frame_size,
        )
        continuous_values: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=116,
                kind=FmiThreeWorkerRequestKind.GET_INT32,
                start=None,
                initialization=None,
                get_int32=FmiThreeWorkerGetInt32Request(
                    value_references=(7,),
                    maximum_value_count=64,
                ),
            ),
            expected_response_kind=FmiThreeWorkerResponseKind.INT32_VALUES,
            maximum_frame_size=maximum_frame_size,
        )
        if continuous_values.int32_values is not None:
            assert continuous_values.int32_values.values == (6,)
        else:
            raise AssertionError("Worker omitted Continuous-Time Int32 values")
        rejected_write: FmiThreeWorkerResponse = _exchange_worker_request(
            connection=connection,
            request=FmiThreeWorkerRequest(
                request_id=117,
                kind=FmiThreeWorkerRequestKind.SET_INT32,
                start=None,
                initialization=None,
                set_int32=FmiThreeWorkerSetInt32Request(
                    value_references=(7,),
                    values=(7,),
                    maximum_value_count=64,
                ),
            ),
            expected_response_kind=FmiThreeWorkerResponseKind.INT32_SET,
            maximum_frame_size=maximum_frame_size,
        )
        assert rejected_write.kind == FmiThreeWorkerResponseKind.ERROR
        assert rejected_write.failure_kind == FmiThreeWorkerFailureKind.LIFECYCLE
        _stop_fmi_three_worker_process(process)
    finally:
        connection.close()
        if process.is_alive():
            _stop_fmi_three_worker_process(process)
        else:
            pass
        staging.close()
    assert process.exitcode == 0
