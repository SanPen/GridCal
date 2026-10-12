# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Unit tests for the bounded FMI 3 worker wire protocol."""

from __future__ import annotations

from multiprocessing import Pipe
from multiprocessing.connection import Connection
from pathlib import Path
import struct

import pytest

from VeraGridEngine.IO.fmu.Elements.inspection import (
    FmuInspectionReceipt,
    inspect_fmu,
)
from VeraGridEngine.IO.fmu.Elements.protocol import (
    FmiThreeWorkerCompletedIntegratorStepRequest,
    FmiThreeWorkerCompletedIntegratorStepResult,
    FmiThreeWorkerConfigureFloat64Request,
    FmiThreeWorkerConfigureUInt64Request,
    FmiThreeWorkerDiscreteStatesResult,
    FmiThreeWorkerDoStepRequest,
    FmiThreeWorkerDoStepResult,
    FmiThreeWorkerFailureKind,
    FmiThreeWorkerFloat64Values,
    FmiThreeWorkerGetFloat64Request,
    FmiThreeWorkerGetInt32Request,
    FmiThreeWorkerInitializationRequest,
    FmiThreeWorkerInt32Values,
    FmiThreeWorkerModelExchangeEvaluationRequest,
    FmiThreeWorkerModelExchangeEvaluationResult,
    FmiThreeWorkerRequest,
    FmiThreeWorkerRequestKind,
    FmiThreeWorkerResponse,
    FmiThreeWorkerResponseKind,
    FmiThreeWorkerSetFloat64Request,
    FmiThreeWorkerSetInt32Request,
    FmiThreeWorkerSetTimeRequest,
    FmiThreeWorkerStagingIdentity,
    FmiThreeWorkerStartRequest,
    build_fmi_three_worker_staging_identity,
    decode_fmi_three_worker_request,
    decode_fmi_three_worker_response,
    encode_fmi_three_worker_request,
    encode_fmi_three_worker_response,
    receive_fmi_three_worker_frame,
    send_fmi_three_worker_frame,
    validate_fmi_three_worker_completed_step,
    validate_fmi_three_worker_float64_frame_capacity,
    validate_fmi_three_worker_initialization_frame_capacity,
    validate_fmi_three_worker_int32_frame_capacity,
    validate_fmi_three_worker_model_exchange_evaluation_frame_capacity,
    validate_fmi_three_worker_uint64_configuration_frame_capacity,
    validate_fmi_three_worker_response_correlation,
    validate_fmi_three_worker_minimum_start_frame_capacity,
    validate_fmi_three_worker_staging_identity,
)
from VeraGridEngine.IO.fmu.profile import (
    FmiThreeWorkerFloat64Profile,
)
from VeraGridEngine.enumerations import FmuInterfaceMode


def test_fmi_three_worker_start_preflight_rejects_identity_and_frame_bound() -> None:
    """Reject caller-known START failures without requiring a staged FMU.

    :return: None.
    """

    with pytest.raises(ValueError, match="instance name must not be empty"):
        validate_fmi_three_worker_minimum_start_frame_capacity(
            instantiation_token="fixture-token",
            model_identifier="fixture_model",
            instance_name=" ",
            interface_mode=FmuInterfaceMode.CO_SIMULATION,
            maximum_frame_size=262144,
        )
    with pytest.raises(ValueError, match="cannot fit"):
        validate_fmi_three_worker_minimum_start_frame_capacity(
            instantiation_token="fixture-token",
            model_identifier="fixture_model",
            instance_name="fixture-instance",
            interface_mode=FmuInterfaceMode.CO_SIMULATION,
            maximum_frame_size=32,
        )


def test_fmi_three_worker_scalar_requests_round_trip() -> None:
    """Preserve ordered finite scalar writes, reads, and step arguments.

    :return: None.
    """

    maximum_frame_size: int = 256
    maximum_value_count: int = 8
    set_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=31,
        kind=FmiThreeWorkerRequestKind.SET_FLOAT64,
        start=None,
        initialization=None,
        set_float64=FmiThreeWorkerSetFloat64Request(
            value_references=(9, 2),
            values=(-3.5, 7.25),
            maximum_value_count=maximum_value_count,
        ),
    )
    decoded_set: FmiThreeWorkerRequest = decode_fmi_three_worker_request(
        encode_fmi_three_worker_request(
            set_request,
            maximum_frame_size,
            maximum_value_count,
        ),
        maximum_frame_size,
        maximum_value_count,
    )
    if decoded_set.set_float64 is not None:
        assert decoded_set.set_float64.value_references == (9, 2)
        assert decoded_set.set_float64.values == (-3.5, 7.25)
    else:
        raise AssertionError("Decoded SET_FLOAT64 body is missing")

    get_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=32,
        kind=FmiThreeWorkerRequestKind.GET_FLOAT64,
        start=None,
        initialization=None,
        get_float64=FmiThreeWorkerGetFloat64Request(
            value_references=(2, 9),
            serialized_value_count=2,
            maximum_value_count=maximum_value_count,
        ),
    )
    decoded_get: FmiThreeWorkerRequest = decode_fmi_three_worker_request(
        encode_fmi_three_worker_request(
            get_request,
            maximum_frame_size,
            maximum_value_count,
        ),
        maximum_frame_size,
        maximum_value_count,
    )
    if decoded_get.get_float64 is not None:
        assert decoded_get.get_float64.value_references == (2, 9)
    else:
        raise AssertionError("Decoded GET_FLOAT64 body is missing")

    step_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=33,
        kind=FmiThreeWorkerRequestKind.DO_STEP,
        start=None,
        initialization=None,
        do_step=FmiThreeWorkerDoStepRequest(
            current_communication_point=1.0,
            communication_step_size=0.125,
            no_set_fmu_state_prior_to_current_point=True,
        ),
    )
    decoded_step: FmiThreeWorkerRequest = decode_fmi_three_worker_request(
        encode_fmi_three_worker_request(
            step_request,
            maximum_frame_size,
            maximum_value_count,
        ),
        maximum_frame_size,
        maximum_value_count,
    )
    if decoded_step.do_step is not None:
        assert decoded_step.do_step.current_communication_point == 1.0
        assert decoded_step.do_step.communication_step_size == 0.125
        assert decoded_step.do_step.no_set_fmu_state_prior_to_current_point
    else:
        raise AssertionError("Decoded DO_STEP body is missing")


def test_fmi_three_worker_model_exchange_messages_round_trip() -> None:
    """Preserve every bounded Model Exchange command and native result flag.

    :return: None.
    """

    maximum_frame_size: int = 256
    maximum_value_count: int = 8
    set_time_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=34,
        kind=FmiThreeWorkerRequestKind.SET_TIME,
        start=None,
        initialization=None,
        set_time=FmiThreeWorkerSetTimeRequest(time_value=1.25),
    )
    decoded_set_time: FmiThreeWorkerRequest = decode_fmi_three_worker_request(
        encode_fmi_three_worker_request(
            set_time_request,
            maximum_frame_size,
            maximum_value_count,
        ),
        maximum_frame_size,
        maximum_value_count,
    )
    if decoded_set_time.set_time is not None:
        assert decoded_set_time.set_time.time_value == 1.25
    else:
        raise AssertionError("Decoded SET_TIME body is missing")

    set_states_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=35,
        kind=FmiThreeWorkerRequestKind.SET_CONTINUOUS_STATES,
        start=None,
        initialization=None,
        continuous_states=FmiThreeWorkerFloat64Values(
            values=(2.0, -3.0),
            maximum_value_count=maximum_value_count,
        ),
    )
    decoded_set_states: FmiThreeWorkerRequest = decode_fmi_three_worker_request(
        encode_fmi_three_worker_request(
            set_states_request,
            maximum_frame_size,
            maximum_value_count,
        ),
        maximum_frame_size,
        maximum_value_count,
    )
    if decoded_set_states.continuous_states is not None:
        assert decoded_set_states.continuous_states.values == (2.0, -3.0)
    else:
        raise AssertionError("Decoded SET_CONTINUOUS_STATES body is missing")

    bodyless_kind: FmiThreeWorkerRequestKind
    for bodyless_kind in (
        FmiThreeWorkerRequestKind.GET_CONTINUOUS_STATES,
        FmiThreeWorkerRequestKind.GET_DERIVATIVES,
        FmiThreeWorkerRequestKind.ENTER_EVENT_MODE,
        FmiThreeWorkerRequestKind.UPDATE_DISCRETE_STATES,
        FmiThreeWorkerRequestKind.ENTER_CONTINUOUS_TIME_MODE,
        FmiThreeWorkerRequestKind.GET_EVENT_INDICATORS,
        FmiThreeWorkerRequestKind.GET_NOMINALS_OF_CONTINUOUS_STATES,
        FmiThreeWorkerRequestKind.SAVE_CHECKPOINT,
        FmiThreeWorkerRequestKind.RESTORE_CHECKPOINT,
        FmiThreeWorkerRequestKind.DISCARD_CHECKPOINT,
    ):
        bodyless_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=36 + int(bodyless_kind),
            kind=bodyless_kind,
            start=None,
            initialization=None,
        )
        decoded_bodyless: FmiThreeWorkerRequest = (
            decode_fmi_three_worker_request(
                encode_fmi_three_worker_request(
                    bodyless_request,
                    maximum_frame_size,
                    maximum_value_count,
                ),
                maximum_frame_size,
                maximum_value_count,
            )
        )
        assert decoded_bodyless.kind == bodyless_kind


def test_fmi_three_worker_model_exchange_evaluation_round_trip() -> None:
    """Preserve one atomic evaluation and its two independently bounded results.

    :return: None.
    """

    maximum_frame_size: int = 256
    maximum_value_count: int = 8
    evaluation: FmiThreeWorkerModelExchangeEvaluationRequest = (
        FmiThreeWorkerModelExchangeEvaluationRequest(
            set_time=FmiThreeWorkerSetTimeRequest(time_value=0.25),
            continuous_states=FmiThreeWorkerFloat64Values(
                values=(3.0,),
                maximum_value_count=maximum_value_count,
            ),
            set_float64=FmiThreeWorkerSetFloat64Request(
                value_references=(10,),
                values=(2.0,),
                maximum_value_count=maximum_value_count,
            ),
            get_float64=FmiThreeWorkerGetFloat64Request(
                value_references=(11, 12),
                serialized_value_count=3,
                maximum_value_count=maximum_value_count,
            ),
        )
    )
    request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=70,
        kind=FmiThreeWorkerRequestKind.EVALUATE_MODEL_EXCHANGE,
        start=None,
        initialization=None,
        model_exchange_evaluation=evaluation,
    )
    decoded_request: FmiThreeWorkerRequest = decode_fmi_three_worker_request(
        frame=encode_fmi_three_worker_request(
            request=request,
            maximum_frame_size=maximum_frame_size,
            maximum_float64_values_per_request=maximum_value_count,
        ),
        maximum_frame_size=maximum_frame_size,
        maximum_float64_values_per_request=maximum_value_count,
    )
    if decoded_request.model_exchange_evaluation is not None:
        decoded_evaluation: FmiThreeWorkerModelExchangeEvaluationRequest = (
            decoded_request.model_exchange_evaluation
        )
    else:
        raise AssertionError("Decoded Model Exchange evaluation is missing")
    assert decoded_evaluation.set_time.time_value == pytest.approx(0.25)
    assert decoded_evaluation.continuous_states.values == pytest.approx((3.0,))
    if decoded_evaluation.set_float64 is not None:
        assert decoded_evaluation.set_float64.value_references == (10,)
        assert decoded_evaluation.set_float64.values == pytest.approx((2.0,))
    else:
        raise AssertionError("Decoded evaluation input assignment is missing")
    if decoded_evaluation.get_float64 is not None:
        assert decoded_evaluation.get_float64.value_references == (11, 12)
        assert decoded_evaluation.get_float64.serialized_value_count == 3
    else:
        raise AssertionError("Decoded evaluation readable request is missing")

    empty_evaluation_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=71,
        kind=FmiThreeWorkerRequestKind.EVALUATE_MODEL_EXCHANGE,
        start=None,
        initialization=None,
        model_exchange_evaluation=(
            FmiThreeWorkerModelExchangeEvaluationRequest(
                set_time=FmiThreeWorkerSetTimeRequest(time_value=0.5),
                continuous_states=FmiThreeWorkerFloat64Values(
                    values=tuple(),
                    maximum_value_count=maximum_value_count,
                ),
                set_float64=None,
                get_float64=None,
            )
        ),
    )
    decoded_empty_request: FmiThreeWorkerRequest = (
        decode_fmi_three_worker_request(
            frame=encode_fmi_three_worker_request(
                request=empty_evaluation_request,
                maximum_frame_size=maximum_frame_size,
                maximum_float64_values_per_request=maximum_value_count,
            ),
            maximum_frame_size=maximum_frame_size,
            maximum_float64_values_per_request=maximum_value_count,
        )
    )
    if decoded_empty_request.model_exchange_evaluation is not None:
        assert decoded_empty_request.model_exchange_evaluation.set_float64 is None
        assert decoded_empty_request.model_exchange_evaluation.get_float64 is None
    else:
        raise AssertionError("Decoded empty Model Exchange evaluation is missing")

    result: FmiThreeWorkerModelExchangeEvaluationResult = (
        FmiThreeWorkerModelExchangeEvaluationResult(
            derivatives=FmiThreeWorkerFloat64Values(
                values=(-1.0,),
                maximum_value_count=maximum_value_count,
            ),
            readable_values=FmiThreeWorkerFloat64Values(
                values=(0.0, 0.25, 2.0),
                maximum_value_count=maximum_value_count,
            ),
        )
    )
    response: FmiThreeWorkerResponse = FmiThreeWorkerResponse(
        request_id=70,
        kind=FmiThreeWorkerResponseKind.MODEL_EXCHANGE_EVALUATED,
        failure_kind=None,
        error_message=None,
        model_exchange_evaluation_result=result,
    )
    decoded_response: FmiThreeWorkerResponse = decode_fmi_three_worker_response(
        frame=encode_fmi_three_worker_response(
            response=response,
            maximum_frame_size=maximum_frame_size,
            maximum_float64_values_per_request=maximum_value_count,
        ),
        maximum_frame_size=maximum_frame_size,
        maximum_float64_values_per_request=maximum_value_count,
    )
    if decoded_response.model_exchange_evaluation_result is not None:
        decoded_result: FmiThreeWorkerModelExchangeEvaluationResult = (
            decoded_response.model_exchange_evaluation_result
        )
    else:
        raise AssertionError("Decoded Model Exchange evaluation result is missing")
    assert decoded_result.derivatives.values == pytest.approx((-1.0,))
    assert decoded_result.readable_values.values == pytest.approx(
        (0.0, 0.25, 2.0)
    )
    with pytest.raises(ValueError, match="exceeds the frame bound"):
        validate_fmi_three_worker_model_exchange_evaluation_frame_capacity(
            continuous_state_count=8,
            writable_reference_count=8,
            writable_value_count=8,
            readable_reference_count=8,
            readable_value_count=8,
            maximum_frame_size=64,
            maximum_value_count=8,
        )

    completed_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=49,
        kind=FmiThreeWorkerRequestKind.COMPLETED_INTEGRATOR_STEP,
        start=None,
        initialization=None,
        completed_integrator_step=(
            FmiThreeWorkerCompletedIntegratorStepRequest(
                no_set_fmu_state_prior_to_current_point=True
            )
        ),
    )
    decoded_completed: FmiThreeWorkerRequest = decode_fmi_three_worker_request(
        encode_fmi_three_worker_request(
            completed_request,
            maximum_frame_size,
            maximum_value_count,
        ),
        maximum_frame_size,
        maximum_value_count,
    )
    if decoded_completed.completed_integrator_step is not None:
        assert (
            decoded_completed.completed_integrator_step.no_set_fmu_state_prior_to_current_point
        )
    else:
        raise AssertionError("Decoded COMPLETED_INTEGRATOR_STEP body is missing")

    completed_response: FmiThreeWorkerResponse = FmiThreeWorkerResponse(
        request_id=49,
        kind=FmiThreeWorkerResponseKind.INTEGRATOR_STEP_COMPLETED,
        failure_kind=None,
        error_message=None,
        completed_integrator_step_result=(
            FmiThreeWorkerCompletedIntegratorStepResult(
                enter_event_mode=True,
                terminate_simulation=False,
            )
        ),
    )
    decoded_response: FmiThreeWorkerResponse = decode_fmi_three_worker_response(
        encode_fmi_three_worker_response(
            completed_response,
            maximum_frame_size,
            maximum_value_count,
        ),
        maximum_frame_size,
        maximum_value_count,
    )
    if decoded_response.completed_integrator_step_result is not None:
        assert decoded_response.completed_integrator_step_result.enter_event_mode
        assert not decoded_response.completed_integrator_step_result.terminate_simulation
    else:
        raise AssertionError("Decoded integrator-step result is missing")

    discrete_states_response: FmiThreeWorkerResponse = FmiThreeWorkerResponse(
        request_id=50,
        kind=FmiThreeWorkerResponseKind.DISCRETE_STATES_UPDATED,
        failure_kind=None,
        error_message=None,
        discrete_states_result=FmiThreeWorkerDiscreteStatesResult(
            discrete_states_need_update=True,
            terminate_simulation=False,
            nominals_of_continuous_states_changed=True,
            values_of_continuous_states_changed=False,
            next_event_time_defined=True,
            next_event_time=2.5,
        ),
    )
    decoded_discrete_states: FmiThreeWorkerResponse = (
        decode_fmi_three_worker_response(
            encode_fmi_three_worker_response(
                discrete_states_response,
                maximum_frame_size,
                maximum_value_count,
            ),
            maximum_frame_size,
            maximum_value_count,
        )
    )
    if decoded_discrete_states.discrete_states_result is not None:
        assert decoded_discrete_states.discrete_states_result.discrete_states_need_update
        assert not decoded_discrete_states.discrete_states_result.terminate_simulation
        assert (
            decoded_discrete_states.discrete_states_result.nominals_of_continuous_states_changed
        )
        assert not (
            decoded_discrete_states.discrete_states_result.values_of_continuous_states_changed
        )
        assert decoded_discrete_states.discrete_states_result.next_event_time_defined
        assert decoded_discrete_states.discrete_states_result.next_event_time == 2.5
    else:
        raise AssertionError("Decoded discrete-state result is missing")


def test_fmi_three_worker_scalar_responses_round_trip() -> None:
    """Preserve scalar result order and every ``fmi3DoStep`` output flag.

    :return: None.
    """

    maximum_frame_size: int = 256
    maximum_value_count: int = 8
    values_response: FmiThreeWorkerResponse = FmiThreeWorkerResponse(
        request_id=41,
        kind=FmiThreeWorkerResponseKind.FLOAT64_VALUES,
        failure_kind=None,
        error_message=None,
        float64_values=FmiThreeWorkerFloat64Values(
            values=(4.5, -2.25),
            maximum_value_count=maximum_value_count,
        ),
    )
    decoded_values: FmiThreeWorkerResponse = decode_fmi_three_worker_response(
        encode_fmi_three_worker_response(
            values_response,
            maximum_frame_size,
            maximum_value_count,
        ),
        maximum_frame_size,
        maximum_value_count,
    )
    if decoded_values.float64_values is not None:
        assert decoded_values.float64_values.values == (4.5, -2.25)
    else:
        raise AssertionError("Decoded FLOAT64_VALUES body is missing")

    step_response: FmiThreeWorkerResponse = FmiThreeWorkerResponse(
        request_id=42,
        kind=FmiThreeWorkerResponseKind.STEP_COMPLETED,
        failure_kind=None,
        error_message=None,
        do_step_result=FmiThreeWorkerDoStepResult(
            event_handling_needed=False,
            terminate_simulation=True,
            early_return=False,
            last_successful_time=1.125,
        ),
    )
    decoded_step: FmiThreeWorkerResponse = decode_fmi_three_worker_response(
        encode_fmi_three_worker_response(
            step_response,
            maximum_frame_size,
            maximum_value_count,
        ),
        maximum_frame_size,
        maximum_value_count,
    )
    if decoded_step.do_step_result is not None:
        assert not decoded_step.do_step_result.event_handling_needed
        assert decoded_step.do_step_result.terminate_simulation
        assert not decoded_step.do_step_result.early_return
        assert decoded_step.do_step_result.last_successful_time == 1.125
    else:
        raise AssertionError("Decoded STEP_COMPLETED body is missing")


def test_fmi_three_worker_array_value_counts_round_trip() -> None:
    """Preserve independent FMI 3 reference and serialized-value counts.

    :return: None.
    """

    maximum_frame_size: int = 256
    maximum_value_count: int = 8
    set_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=43,
        kind=FmiThreeWorkerRequestKind.SET_FLOAT64,
        start=None,
        initialization=None,
        set_float64=FmiThreeWorkerSetFloat64Request(
            value_references=(17,),
            values=(1.0, 2.0, 3.0),
            maximum_value_count=maximum_value_count,
        ),
    )
    decoded_set: FmiThreeWorkerRequest = decode_fmi_three_worker_request(
        encode_fmi_three_worker_request(
            set_request,
            maximum_frame_size,
            maximum_value_count,
        ),
        maximum_frame_size,
        maximum_value_count,
    )
    if decoded_set.set_float64 is not None:
        assert decoded_set.set_float64.value_references == (17,)
        assert decoded_set.set_float64.values == (1.0, 2.0, 3.0)
    else:
        raise AssertionError("Decoded array SET_FLOAT64 body is missing")

    get_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=44,
        kind=FmiThreeWorkerRequestKind.GET_FLOAT64,
        start=None,
        initialization=None,
        get_float64=FmiThreeWorkerGetFloat64Request(
            value_references=(17,),
            serialized_value_count=3,
            maximum_value_count=maximum_value_count,
        ),
    )
    decoded_get: FmiThreeWorkerRequest = decode_fmi_three_worker_request(
        encode_fmi_three_worker_request(
            get_request,
            maximum_frame_size,
            maximum_value_count,
        ),
        maximum_frame_size,
        maximum_value_count,
    )
    if decoded_get.get_float64 is not None:
        assert decoded_get.get_float64.value_references == (17,)
        assert decoded_get.get_float64.serialized_value_count == 3
    else:
        raise AssertionError("Decoded array GET_FLOAT64 body is missing")


def test_fmi_three_worker_configuration_request_round_trip() -> None:
    """Preserve bounded structural Float64 assignments as a distinct operation.

    :return: None.
    """

    maximum_frame_size: int = 256
    maximum_value_count: int = 8
    configuration_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=45,
        kind=FmiThreeWorkerRequestKind.CONFIGURE_FLOAT64,
        start=None,
        initialization=None,
        configuration=FmiThreeWorkerConfigureFloat64Request(
            value_references=(21, 34),
            values=(2.0, 3.0, 4.0),
            maximum_value_count=maximum_value_count,
        ),
    )
    decoded_configuration: FmiThreeWorkerRequest = (
        decode_fmi_three_worker_request(
            encode_fmi_three_worker_request(
                configuration_request,
                maximum_frame_size,
                maximum_value_count,
            ),
            maximum_frame_size,
            maximum_value_count,
        )
    )
    if decoded_configuration.configuration is not None:
        assert decoded_configuration.configuration.value_references == (21, 34)
        assert decoded_configuration.configuration.values == (2.0, 3.0, 4.0)
    else:
        raise AssertionError("Decoded CONFIGURE_FLOAT64 body is missing")

    configured_response: FmiThreeWorkerResponse = FmiThreeWorkerResponse(
        request_id=45,
        kind=FmiThreeWorkerResponseKind.CONFIGURED,
        failure_kind=None,
        error_message=None,
    )
    decoded_response: FmiThreeWorkerResponse = decode_fmi_three_worker_response(
        encode_fmi_three_worker_response(
            configured_response,
            maximum_frame_size,
            maximum_value_count,
        ),
        maximum_frame_size,
        maximum_value_count,
    )
    assert decoded_response.kind == FmiThreeWorkerResponseKind.CONFIGURED


def test_fmi_three_worker_uint64_configuration_request_round_trip() -> None:
    """Preserve bounded UInt64 structural assignments without Float64 coercion.

    :return: None.
    """

    maximum_frame_size: int = 256
    maximum_value_count: int = 8
    maximum_uint64: int = 18446744073709551615
    configuration_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=46,
        kind=FmiThreeWorkerRequestKind.CONFIGURE_UINT64,
        start=None,
        initialization=None,
        configuration_uint64=FmiThreeWorkerConfigureUInt64Request(
            value_references=(100, 101),
            values=(3, maximum_uint64),
            maximum_value_count=maximum_value_count,
        ),
    )
    decoded_configuration: FmiThreeWorkerRequest = (
        decode_fmi_three_worker_request(
            encode_fmi_three_worker_request(
                configuration_request,
                maximum_frame_size,
                maximum_value_count,
            ),
            maximum_frame_size,
            maximum_value_count,
        )
    )

    if decoded_configuration.configuration_uint64 is not None:
        assert decoded_configuration.configuration_uint64.value_references == (
            100,
            101,
        )
        assert decoded_configuration.configuration_uint64.values == (
            3,
            maximum_uint64,
        )
    else:
        raise AssertionError("Decoded CONFIGURE_UINT64 body is missing")


def test_fmi_three_worker_zero_length_array_frames_round_trip() -> None:
    """Preserve active array references whose configured cardinality is zero.

    :return: None.
    """

    maximum_frame_size: int = 128
    maximum_value_count: int = 8
    request_bodies: tuple[FmiThreeWorkerRequest, ...] = (
        FmiThreeWorkerRequest(
            request_id=47,
            kind=FmiThreeWorkerRequestKind.SET_FLOAT64,
            start=None,
            initialization=None,
            set_float64=FmiThreeWorkerSetFloat64Request(
                value_references=(20,),
                values=tuple(),
                maximum_value_count=maximum_value_count,
            ),
        ),
        FmiThreeWorkerRequest(
            request_id=48,
            kind=FmiThreeWorkerRequestKind.GET_FLOAT64,
            start=None,
            initialization=None,
            get_float64=FmiThreeWorkerGetFloat64Request(
                value_references=(20,),
                serialized_value_count=0,
                maximum_value_count=maximum_value_count,
            ),
        ),
        FmiThreeWorkerRequest(
            request_id=49,
            kind=FmiThreeWorkerRequestKind.CONFIGURE_FLOAT64,
            start=None,
            initialization=None,
            configuration=FmiThreeWorkerConfigureFloat64Request(
                value_references=(20,),
                values=tuple(),
                maximum_value_count=maximum_value_count,
            ),
        ),
        FmiThreeWorkerRequest(
            request_id=50,
            kind=FmiThreeWorkerRequestKind.INITIALIZE,
            start=None,
            initialization=FmiThreeWorkerInitializationRequest(
                start_time=0.0,
                stop_time=None,
                relative_tolerance=None,
                initial_float64_value_references=(20,),
                initial_float64_values=tuple(),
                initial_int32_value_references=tuple(),
                initial_int32_values=tuple(),
                maximum_value_count=maximum_value_count,
            ),
        ),
    )
    request: FmiThreeWorkerRequest
    for request in request_bodies:
        decoded_request: FmiThreeWorkerRequest = decode_fmi_three_worker_request(
            encode_fmi_three_worker_request(
                request=request,
                maximum_frame_size=maximum_frame_size,
                maximum_float64_values_per_request=maximum_value_count,
            ),
            maximum_frame_size=maximum_frame_size,
            maximum_float64_values_per_request=maximum_value_count,
        )
        assert decoded_request.kind == request.kind

    empty_values_response: FmiThreeWorkerResponse = FmiThreeWorkerResponse(
        request_id=48,
        kind=FmiThreeWorkerResponseKind.FLOAT64_VALUES,
        failure_kind=None,
        error_message=None,
        float64_values=FmiThreeWorkerFloat64Values(
            values=tuple(),
            maximum_value_count=maximum_value_count,
        ),
    )
    decoded_response: FmiThreeWorkerResponse = decode_fmi_three_worker_response(
        encode_fmi_three_worker_response(
            response=empty_values_response,
            maximum_frame_size=maximum_frame_size,
            maximum_float64_values_per_request=maximum_value_count,
        ),
        maximum_frame_size=maximum_frame_size,
        maximum_float64_values_per_request=maximum_value_count,
    )
    if decoded_response.float64_values is not None:
        assert decoded_response.float64_values.values == tuple()
    else:
        raise AssertionError("Decoded zero-length Float64 response is missing")


def test_fmi_three_worker_scalar_contract_rejects_ambiguous_values() -> None:
    """Reject duplicate references, non-finite values, and invalid step sizes.

    :return: None.
    """

    with pytest.raises(ValueError, match="unique"):
        FmiThreeWorkerGetFloat64Request(
            (1, 1),
            serialized_value_count=2,
            maximum_value_count=8,
        )
    with pytest.raises(ValueError, match="finite"):
        FmiThreeWorkerSetFloat64Request(
            value_references=(1,),
            values=(float("nan"),),
            maximum_value_count=8,
        )
    with pytest.raises(ValueError, match="outside its bound"):
        FmiThreeWorkerConfigureFloat64Request(
            value_references=(1,),
            values=(1.0,) * 9,
            maximum_value_count=8,
        )
    with pytest.raises(ValueError, match="must align"):
        FmiThreeWorkerConfigureUInt64Request(
            value_references=(1,),
            values=(2, 3),
            maximum_value_count=8,
        )
    with pytest.raises(ValueError, match="outside UInt64"):
        FmiThreeWorkerConfigureUInt64Request(
            value_references=(1,),
            values=(-1,),
            maximum_value_count=8,
        )
    with pytest.raises(ValueError, match="outside UInt64"):
        FmiThreeWorkerConfigureUInt64Request(
            value_references=(1,),
            values=(1.0,),  # type: ignore[arg-type]
            maximum_value_count=8,
        )
    with pytest.raises(ValueError, match="finite and positive"):
        FmiThreeWorkerDoStepRequest(
            current_communication_point=0.0,
            communication_step_size=0.0,
            no_set_fmu_state_prior_to_current_point=True,
        )
    with pytest.raises(ValueError, match="endpoint must be finite and advance time"):
        FmiThreeWorkerDoStepRequest(
            current_communication_point=1.7e308,
            communication_step_size=1.7e308,
            no_set_fmu_state_prior_to_current_point=True,
        )
    with pytest.raises(ValueError, match="endpoint must be finite and advance time"):
        FmiThreeWorkerDoStepRequest(
            current_communication_point=1.0e16,
            communication_step_size=0.25,
            no_set_fmu_state_prior_to_current_point=True,
        )


@pytest.mark.parametrize(
    (
        "event_handling_needed",
        "early_return",
        "last_successful_time",
        "early_return_allowed",
        "might_return_early_from_do_step",
        "diagnostic",
    ),
    (
        (True, False, 1.25, False, False, "Event Mode"),
        (False, True, 1.125, False, True, "returned early"),
        (False, True, 1.125, True, False, "without advertising"),
        (False, True, 1.25, True, True, "outside the requested step"),
        (False, False, 0.999, True, True, "precedes the communication point"),
    ),
)
def test_fmi_three_worker_completed_step_rejects_profile_contradictions(
    event_handling_needed: bool,
    early_return: bool,
    last_successful_time: float,
    early_return_allowed: bool,
    might_return_early_from_do_step: bool,
    diagnostic: str,
) -> None:
    """Reject native results that require an unsupported step lifecycle.

    :param event_handling_needed: Candidate native Event Mode flag.
    :param early_return: Candidate native early-return flag.
    :param last_successful_time: Candidate native endpoint.
    :param early_return_allowed: Candidate importer permission.
    :param might_return_early_from_do_step: Candidate advertised capability.
    :param diagnostic: Expected rejection fragment.
    :return: None.
    """

    result: FmiThreeWorkerDoStepResult = FmiThreeWorkerDoStepResult(
        event_handling_needed=event_handling_needed,
        terminate_simulation=True,
        early_return=early_return,
        last_successful_time=last_successful_time,
    )
    request: FmiThreeWorkerDoStepRequest = FmiThreeWorkerDoStepRequest(
        current_communication_point=1.0,
        communication_step_size=0.25,
        no_set_fmu_state_prior_to_current_point=True,
    )

    with pytest.raises(ValueError, match=diagnostic):
        validate_fmi_three_worker_completed_step(
            request=request,
            result=result,
            early_return_allowed=early_return_allowed,
            might_return_early_from_do_step=might_return_early_from_do_step,
        )


def test_fmi_three_worker_completed_step_accepts_exact_time_and_termination() -> None:
    """Accept the exact fixed-step endpoint and retain termination.

    :return: None.
    """

    result: FmiThreeWorkerDoStepResult = FmiThreeWorkerDoStepResult(
        event_handling_needed=False,
        terminate_simulation=True,
        early_return=False,
        last_successful_time=1.25,
    )
    request: FmiThreeWorkerDoStepRequest = FmiThreeWorkerDoStepRequest(
        current_communication_point=1.0,
        communication_step_size=0.25,
        no_set_fmu_state_prior_to_current_point=True,
    )

    validate_fmi_three_worker_completed_step(
        request=request,
        result=result,
        early_return_allowed=False,
        might_return_early_from_do_step=False,
    )


def test_fmi_three_worker_completed_step_rejects_deviating_time() -> None:
    """Reject a valid FMI endpoint that the fixed-step adapters cannot represent.

    :return: None.
    """

    result: FmiThreeWorkerDoStepResult = FmiThreeWorkerDoStepResult(
        event_handling_needed=False,
        terminate_simulation=False,
        early_return=False,
        last_successful_time=1.2499999999999998,
    )
    request: FmiThreeWorkerDoStepRequest = FmiThreeWorkerDoStepRequest(
        current_communication_point=1.0,
        communication_step_size=0.25,
        no_set_fmu_state_prior_to_current_point=True,
    )

    with pytest.raises(ValueError, match="differs from the requested endpoint"):
        validate_fmi_three_worker_completed_step(
            request=request,
            result=result,
            early_return_allowed=False,
            might_return_early_from_do_step=False,
        )


@pytest.mark.parametrize(
    ("early_return", "last_successful_time"),
    (
        (True, 1.125),
        (False, 1.2499999999999998),
        (False, 1.2500000000000002),
    ),
)
def test_fmi_three_worker_completed_step_accepts_negotiated_partial_time(
    early_return: bool,
    last_successful_time: float,
) -> None:
    """Accept FMI 3 partial or non-exact time when the consumer negotiated it.

    :param early_return: Whether the FMU explicitly reports early return.
    :param last_successful_time: Finite internal time reached by the FMU.
    :return: None.
    """

    result: FmiThreeWorkerDoStepResult = FmiThreeWorkerDoStepResult(
        event_handling_needed=False,
        terminate_simulation=False,
        early_return=early_return,
        last_successful_time=last_successful_time,
    )
    request: FmiThreeWorkerDoStepRequest = FmiThreeWorkerDoStepRequest(
        current_communication_point=1.0,
        communication_step_size=0.25,
        no_set_fmu_state_prior_to_current_point=True,
    )

    validate_fmi_three_worker_completed_step(
        request=request,
        result=result,
        early_return_allowed=True,
        might_return_early_from_do_step=True,
    )


def test_fmi_three_worker_scalar_decoder_rejects_bounds_and_reserved_flags() -> None:
    """Reject declared scalar amplification and unknown step flag bits.

    :return: None.
    """

    maximum_frame_size: int = 256
    maximum_value_count: int = 8
    get_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=51,
        kind=FmiThreeWorkerRequestKind.GET_FLOAT64,
        start=None,
        initialization=None,
        get_float64=FmiThreeWorkerGetFloat64Request(
            value_references=(1,),
            serialized_value_count=1,
            maximum_value_count=maximum_value_count,
        ),
    )
    oversized_count_frame: bytearray = bytearray(
        encode_fmi_three_worker_request(
            get_request,
            maximum_frame_size,
            maximum_value_count,
        )
    )
    header_size: int = struct.calcsize("!4sBBBQI")
    struct.pack_into("!I", oversized_count_frame, header_size, 9)
    with pytest.raises(ValueError, match="outside its bound"):
        decode_fmi_three_worker_request(
            bytes(oversized_count_frame),
            maximum_frame_size,
            maximum_value_count,
        )

    amplified_get_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=53,
        kind=FmiThreeWorkerRequestKind.GET_FLOAT64,
        start=None,
        initialization=None,
        get_float64=FmiThreeWorkerGetFloat64Request(
            value_references=(1, 2),
            serialized_value_count=2,
            maximum_value_count=maximum_value_count,
        ),
    )
    amplified_get_frame: bytes = encode_fmi_three_worker_request(
        amplified_get_request,
        maximum_frame_size,
        maximum_value_count,
    )
    with pytest.raises(ValueError, match="request or response exceeds"):
        decode_fmi_three_worker_request(
            amplified_get_frame,
            maximum_frame_size=38,
            maximum_float64_values_per_request=maximum_value_count,
        )

    step_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=52,
        kind=FmiThreeWorkerRequestKind.DO_STEP,
        start=None,
        initialization=None,
        do_step=FmiThreeWorkerDoStepRequest(
            current_communication_point=0.0,
            communication_step_size=0.25,
            no_set_fmu_state_prior_to_current_point=True,
        ),
    )
    unknown_flags_frame: bytearray = bytearray(
        encode_fmi_three_worker_request(
            step_request,
            maximum_frame_size,
            maximum_value_count,
        )
    )
    unknown_flags_frame[header_size] = 2
    with pytest.raises(ValueError, match="unknown flags"):
        decode_fmi_three_worker_request(
            bytes(unknown_flags_frame),
            maximum_frame_size,
            maximum_value_count,
        )


def _worker_staging_identity() -> FmiThreeWorkerStagingIdentity:
    """Return a deterministic staged-tree identity for protocol tests.

    :return: Valid typed staging identity.
    """

    identity: FmiThreeWorkerStagingIdentity = FmiThreeWorkerStagingIdentity(
        tree_sha256="a" * 64,
        model_description_sha256="b" * 64,
        tree_size=4096,
        entry_count=7,
    )
    return identity


def _worker_start_request(
    extracted_fmu_directory: Path,
    request_id: int = 7,
    interface_mode: FmuInterfaceMode = FmuInterfaceMode.CO_SIMULATION,
    float64_profile: FmiThreeWorkerFloat64Profile = (
        FmiThreeWorkerFloat64Profile.CONSTANT_ARRAY
    ),
    early_return_allowed: bool = False,
) -> FmiThreeWorkerRequest:
    """Return a self-contained START request with v41-style identifiers.

    :param extracted_fmu_directory: Absolute private staged FMU directory.
    :param request_id: Positive request correlation identifier.
    :param interface_mode: Selected interface encoded in START.
    :param float64_profile: Float64 profile encoded in START.
    :param early_return_allowed: Whether START authorizes partial CS steps.
    :return: Valid typed START request.
    """

    start: FmiThreeWorkerStartRequest = FmiThreeWorkerStartRequest(
        extracted_fmu_directory=extracted_fmu_directory,
        staging_identity=_worker_staging_identity(),
        instantiation_token="{78277fc9-f825-54fc-a932-c79731732e85}",
        model_identifier="VeraGridPhysicalCompositionContainerPFTimeLatticeV41",
        instance_name="VeraGrid v41 μ-worker",
        interface_mode=interface_mode,
        float64_profile=float64_profile,
        visible=False,
        debug_logging=True,
        early_return_allowed=early_return_allowed,
    )
    request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=request_id,
        kind=FmiThreeWorkerRequestKind.START,
        start=start,
        initialization=None,
    )
    return request


def test_fmi_three_worker_start_request_round_trip(tmp_path: Path) -> None:
    """Verify exact runtime and staging identity survives the protocol.

    :param tmp_path: Absolute temporary parent supplied by pytest.
    :return: None.
    """

    maximum_frame_size: int = 4096
    request: FmiThreeWorkerRequest = _worker_start_request(
        tmp_path / "fmu",
        early_return_allowed=True,
    )

    frame: bytes = encode_fmi_three_worker_request(
        request,
        maximum_frame_size,
        maximum_float64_values_per_request=16384,
    )
    decoded: FmiThreeWorkerRequest = decode_fmi_three_worker_request(
        frame,
        maximum_frame_size,
        maximum_float64_values_per_request=16384,
    )

    assert decoded.request_id == request.request_id
    assert decoded.kind is FmiThreeWorkerRequestKind.START
    if decoded.start is None or request.start is None:
        raise AssertionError("Both START bodies must be present")
    else:
        pass
    assert decoded.start.extracted_fmu_directory == request.start.extracted_fmu_directory
    assert decoded.start.instantiation_token == request.start.instantiation_token
    assert decoded.start.model_identifier == request.start.model_identifier
    assert decoded.start.instance_name == request.start.instance_name
    assert decoded.start.interface_mode is FmuInterfaceMode.CO_SIMULATION
    assert decoded.start.float64_profile is FmiThreeWorkerFloat64Profile.CONSTANT_ARRAY
    assert decoded.start.staging_identity.tree_sha256 == (
        request.start.staging_identity.tree_sha256
    )
    assert decoded.start.staging_identity.model_description_sha256 == (
        request.start.staging_identity.model_description_sha256
    )
    assert decoded.start.staging_identity.tree_size == 4096
    assert decoded.start.staging_identity.entry_count == 7
    assert not decoded.start.visible
    assert decoded.start.debug_logging
    assert decoded.start.early_return_allowed
    assert decoded.initialization is None


def test_fmi_three_worker_configurable_array_start_round_trip(
    tmp_path: Path,
) -> None:
    """Preserve the configurable-array profile in the bounded START flags.

    :param tmp_path: Absolute temporary parent supplied by pytest.
    :return: None.
    """

    request: FmiThreeWorkerRequest = _worker_start_request(
        extracted_fmu_directory=tmp_path / "configurable-fmu",
        interface_mode=FmuInterfaceMode.MODEL_EXCHANGE,
        float64_profile=FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY,
    )
    frame: bytes = encode_fmi_three_worker_request(
        request=request,
        maximum_frame_size=4096,
        maximum_float64_values_per_request=64,
    )
    decoded: FmiThreeWorkerRequest = decode_fmi_three_worker_request(
        frame=frame,
        maximum_frame_size=4096,
        maximum_float64_values_per_request=64,
    )

    if decoded.start is not None:
        assert (
            decoded.start.float64_profile
            is FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY
        )
        assert decoded.start.interface_mode is FmuInterfaceMode.MODEL_EXCHANGE
    else:
        raise AssertionError("Decoded configurable START body is missing")


@pytest.mark.parametrize(
    ("stop_time", "relative_tolerance"),
    (
        (None, None),
        (5.0, 1.0e-6),
    ),
)
def test_fmi_three_worker_initialization_request_round_trip(
    stop_time: float | None,
    relative_tolerance: float | None,
) -> None:
    """Verify optional initialization values retain declared presence.

    :param stop_time: Optional stop time encoded in the test case.
    :param relative_tolerance: Optional tolerance encoded in the test case.
    :return: None.
    """

    initialization: FmiThreeWorkerInitializationRequest = (
        FmiThreeWorkerInitializationRequest(
            start_time=0.25,
            stop_time=stop_time,
            relative_tolerance=relative_tolerance,
            initial_float64_value_references=tuple(),
            initial_float64_values=tuple(),
            initial_int32_value_references=tuple(),
            initial_int32_values=tuple(),
            maximum_value_count=16384,
        )
    )
    request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=8,
        kind=FmiThreeWorkerRequestKind.INITIALIZE,
        start=None,
        initialization=initialization,
    )

    frame: bytes = encode_fmi_three_worker_request(
        request,
        maximum_frame_size=128,
        maximum_float64_values_per_request=16384,
    )
    decoded: FmiThreeWorkerRequest = decode_fmi_three_worker_request(
        frame,
        maximum_frame_size=128,
        maximum_float64_values_per_request=16384,
    )

    assert decoded.request_id == 8
    assert decoded.kind is FmiThreeWorkerRequestKind.INITIALIZE
    if decoded.initialization is None:
        raise AssertionError("The decoded INITIALIZE body must be present")
    else:
        pass
    assert decoded.initialization.start_time == pytest.approx(0.25)
    assert decoded.initialization.stop_time == stop_time
    assert decoded.initialization.relative_tolerance == relative_tolerance
    assert decoded.initialization.initial_float64_value_references == tuple()
    assert decoded.initialization.initial_float64_values == tuple()
    assert decoded.initialization.initial_int32_value_references == tuple()
    assert decoded.initialization.initial_int32_values == tuple()
    assert decoded.start is None


def test_mixed_initialization_typed_sections_and_combined_limits() -> None:
    """Preserve typed numeric sections and their shared cardinality bound.

    :return: None.
    """

    initialization: FmiThreeWorkerInitializationRequest = (
        FmiThreeWorkerInitializationRequest(
            start_time=0.25,
            stop_time=5.0,
            relative_tolerance=1.0e-6,
            initial_float64_value_references=(7,),
            initial_float64_values=(2.0, -3.0),
            initial_int32_value_references=(11, 12),
            initial_int32_values=(-2147483648, 2147483647),
            maximum_value_count=8,
        )
    )
    request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=9,
        kind=FmiThreeWorkerRequestKind.INITIALIZE,
        start=None,
        initialization=initialization,
    )

    frame: bytes = encode_fmi_three_worker_request(
        request=request,
        maximum_frame_size=128,
        maximum_float64_values_per_request=8,
    )
    expected_body: bytes = b"".join(
        (
            struct.pack("!Bddd", 3, 0.25, 5.0, 1.0e-6),
            struct.pack("!II", 1, 2),
            struct.pack("!I", 7),
            struct.pack("!dd", 2.0, -3.0),
            struct.pack("!II", 2, 2),
            struct.pack("!II", 11, 12),
            struct.pack("!ii", -2147483648, 2147483647),
        )
    )
    expected_header: bytes = struct.pack(
        "!4sBBBQI",
        b"VGFW",
        11,
        1,
        int(FmiThreeWorkerRequestKind.INITIALIZE),
        9,
        len(expected_body),
    )
    decoded: FmiThreeWorkerRequest = decode_fmi_three_worker_request(
        frame=frame,
        maximum_frame_size=128,
        maximum_float64_values_per_request=8,
    )

    assert frame == b"".join((expected_header, expected_body))
    if decoded.initialization is not None:
        pass
    else:
        raise AssertionError("The decoded INITIALIZE body must be present")
    assert decoded.initialization.initial_float64_value_references == (7,)
    assert decoded.initialization.initial_float64_values == pytest.approx((2.0, -3.0))
    assert decoded.initialization.initial_int32_value_references == (11, 12)
    assert decoded.initialization.initial_int32_values == (
        -2147483648,
        2147483647,
    )
    with pytest.raises(ValueError, match="combined initialization count"):
        validate_fmi_three_worker_initialization_frame_capacity(
            float64_value_reference_count=1,
            float64_serialized_value_count=2,
            int32_value_reference_count=2,
            int32_value_count=2,
            maximum_frame_size=128,
            maximum_value_count=3,
        )


def test_fmi_three_worker_initialization_assignment_frame_capacity() -> None:
    """Count the fixed initialization body before accepting assignments.

    :return: None.
    """

    empty_frame_size: int = (
        struct.calcsize("!4sBBBQI") + struct.calcsize("!Bddd") + 16
    )
    validate_fmi_three_worker_initialization_frame_capacity(
        float64_value_reference_count=0,
        float64_serialized_value_count=0,
        int32_value_reference_count=0,
        int32_value_count=0,
        maximum_frame_size=empty_frame_size,
        maximum_value_count=8,
    )
    exact_frame_size: int = empty_frame_size + 2 * 4 + 2 * 8
    validate_fmi_three_worker_initialization_frame_capacity(
        float64_value_reference_count=2,
        float64_serialized_value_count=2,
        int32_value_reference_count=0,
        int32_value_count=0,
        maximum_frame_size=exact_frame_size,
        maximum_value_count=8,
    )
    with pytest.raises(ValueError, match="initialization request exceeds"):
        validate_fmi_three_worker_initialization_frame_capacity(
            float64_value_reference_count=2,
            float64_serialized_value_count=2,
            int32_value_reference_count=0,
            int32_value_count=0,
            maximum_frame_size=exact_frame_size - 1,
            maximum_value_count=8,
        )


def test_fmi_three_worker_configuration_assignment_frame_capacity() -> None:
    """Bound one structural assignment frame before Configuration Mode.

    :return: None.
    """

    exact_frame_size: int = struct.calcsize("!4sBBBQI") + 8 + 2 * 4 + 2 * 8
    validate_fmi_three_worker_float64_frame_capacity(
        request_kind=FmiThreeWorkerRequestKind.CONFIGURE_FLOAT64,
        value_reference_count=2,
        serialized_value_count=2,
        maximum_frame_size=exact_frame_size,
        maximum_value_count=8,
    )
    with pytest.raises(ValueError, match="request or response exceeds"):
        validate_fmi_three_worker_float64_frame_capacity(
            request_kind=FmiThreeWorkerRequestKind.CONFIGURE_FLOAT64,
            value_reference_count=2,
            serialized_value_count=2,
            maximum_frame_size=exact_frame_size - 1,
            maximum_value_count=8,
        )


def test_fmi_three_worker_uint64_configuration_frame_capacity() -> None:
    """Bound aligned UInt64 structural assignments before encoding.

    :return: None.
    """

    exact_frame_size: int = struct.calcsize("!4sBBBQI") + 8 + 2 * 12
    validate_fmi_three_worker_uint64_configuration_frame_capacity(
        value_count=2,
        maximum_frame_size=exact_frame_size,
        maximum_value_count=8,
    )
    with pytest.raises(ValueError, match="exceeds the frame bound"):
        validate_fmi_three_worker_uint64_configuration_frame_capacity(
            value_count=2,
            maximum_frame_size=exact_frame_size - 1,
            maximum_value_count=8,
        )


def test_fmi_three_worker_close_request_round_trip() -> None:
    """Verify CLOSE remains an exactly bodyless correlated request.

    :return: None.
    """

    close_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=9,
        kind=FmiThreeWorkerRequestKind.CLOSE,
        start=None,
        initialization=None,
    )
    close_frame: bytes = encode_fmi_three_worker_request(
        close_request,
        maximum_frame_size=64,
        maximum_float64_values_per_request=16384,
    )
    decoded_close: FmiThreeWorkerRequest = decode_fmi_three_worker_request(
        close_frame,
        maximum_frame_size=64,
        maximum_float64_values_per_request=16384,
    )

    assert decoded_close.request_id == 9
    assert decoded_close.kind is FmiThreeWorkerRequestKind.CLOSE
    assert decoded_close.start is None
    assert decoded_close.initialization is None


def test_fmi_three_worker_close_frame_has_canonical_network_order() -> None:
    """Fix the complete version-eleven header as a byte-exact wire vector.

    :return: None.
    """

    close_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=0x0102030405060708,
        kind=FmiThreeWorkerRequestKind.CLOSE,
        start=None,
        initialization=None,
    )
    frame: bytes = encode_fmi_three_worker_request(
        close_request,
        maximum_frame_size=64,
        maximum_float64_values_per_request=16384,
    )

    assert frame == (
        b"VGFW"
        b"\x0b"
        b"\x01"
        b"\x03"
        b"\x01\x02\x03\x04\x05\x06\x07\x08"
        b"\x00\x00\x00\x00"
    )


def test_int32_protocol_round_trip_and_network_order_bounds() -> None:
    """Round-trip signed Int32 extrema and preserve network byte order.

    :return: None.
    """

    set_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=51,
        kind=FmiThreeWorkerRequestKind.SET_INT32,
        start=None,
        initialization=None,
        set_int32=FmiThreeWorkerSetInt32Request(
            value_references=(7, 8),
            values=(-2147483648, 2147483647),
            maximum_value_count=8,
        ),
    )
    set_frame: bytes = encode_fmi_three_worker_request(
        request=set_request,
        maximum_frame_size=128,
        maximum_float64_values_per_request=8,
    )
    assert set_frame.endswith(struct.pack("!ii", -2147483648, 2147483647))
    decoded_set: FmiThreeWorkerRequest = decode_fmi_three_worker_request(
        frame=set_frame,
        maximum_frame_size=128,
        maximum_float64_values_per_request=8,
    )
    if decoded_set.set_int32 is not None:
        assert decoded_set.set_int32.value_references == (7, 8)
        assert decoded_set.set_int32.values == (-2147483648, 2147483647)
    else:
        raise AssertionError("Decoded SET_INT32 body is missing")

    response: FmiThreeWorkerResponse = FmiThreeWorkerResponse(
        request_id=52,
        kind=FmiThreeWorkerResponseKind.INT32_VALUES,
        failure_kind=None,
        error_message=None,
        int32_values=FmiThreeWorkerInt32Values(
            values=(-2147483648, 2147483647),
            maximum_value_count=8,
        ),
    )
    response_frame: bytes = encode_fmi_three_worker_response(
        response=response,
        maximum_frame_size=128,
        maximum_float64_values_per_request=8,
    )
    assert response_frame.endswith(struct.pack("!ii", -2147483648, 2147483647))
    decoded_response: FmiThreeWorkerResponse = decode_fmi_three_worker_response(
        frame=response_frame,
        maximum_frame_size=128,
        maximum_float64_values_per_request=8,
    )
    if decoded_response.int32_values is not None:
        assert decoded_response.int32_values.values == (
            -2147483648,
            2147483647,
        )
    else:
        raise AssertionError("Decoded INT32_VALUES body is missing")
    with pytest.raises(ValueError, match="Python int"):
        FmiThreeWorkerSetInt32Request((7,), (True,), 8)
    with pytest.raises(ValueError, match="outside signed Int32"):
        FmiThreeWorkerSetInt32Request((7,), (2147483648,), 8)
    validate_fmi_three_worker_int32_frame_capacity(
        request_kind=FmiThreeWorkerRequestKind.GET_INT32,
        value_count=2,
        maximum_frame_size=128,
        maximum_value_count=8,
    )


def test_protocol_version_ten_frames_are_rejected() -> None:
    """Reject the superseded protocol version before body decoding.

    :return: None.
    """

    request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=53,
        kind=FmiThreeWorkerRequestKind.CLOSE,
        start=None,
        initialization=None,
    )
    version_ten_frame: bytearray = bytearray(
        encode_fmi_three_worker_request(request, 64, 8)
    )
    version_ten_frame[4] = 10
    with pytest.raises(ValueError, match="protocol version 10"):
        decode_fmi_three_worker_request(bytes(version_ten_frame), 64, 8)


def test_initialization_absent_optionals_reject_negative_zero() -> None:
    """Reject negative zero in absent optional Float64 header slots.

    :return: None.
    """

    initialization: FmiThreeWorkerInitializationRequest = (
        FmiThreeWorkerInitializationRequest(
            start_time=0.0,
            stop_time=None,
            relative_tolerance=None,
            initial_float64_value_references=tuple(),
            initial_float64_values=tuple(),
            initial_int32_value_references=tuple(),
            initial_int32_values=tuple(),
            maximum_value_count=8,
        )
    )
    request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=54,
        kind=FmiThreeWorkerRequestKind.INITIALIZE,
        start=None,
        initialization=initialization,
    )
    frame: bytes = encode_fmi_three_worker_request(request, 128, 8)
    negative_zero_stop: bytearray = bytearray(frame)
    struct.pack_into("!d", negative_zero_stop, 28, -0.0)
    with pytest.raises(ValueError, match="absent stop time slot.*canonical zero"):
        decode_fmi_three_worker_request(bytes(negative_zero_stop), 128, 8)
    negative_zero_tolerance: bytearray = bytearray(frame)
    struct.pack_into("!d", negative_zero_tolerance, 36, -0.0)
    with pytest.raises(ValueError, match="absent tolerance slot.*canonical zero"):
        decode_fmi_three_worker_request(bytes(negative_zero_tolerance), 128, 8)


def test_fmi_three_worker_success_response_round_trip() -> None:
    """Verify one successful response keeps its request correlation.

    :return: None.
    """

    success: FmiThreeWorkerResponse = FmiThreeWorkerResponse(
        request_id=10,
        kind=FmiThreeWorkerResponseKind.CLOSED,
        failure_kind=None,
        error_message=None,
    )
    frame: bytes = encode_fmi_three_worker_response(
        success,
        maximum_frame_size=64,
        maximum_float64_values_per_request=16384,
    )
    decoded: FmiThreeWorkerResponse = decode_fmi_three_worker_response(
        frame,
        maximum_frame_size=64,
        maximum_float64_values_per_request=16384,
    )

    assert decoded.request_id == 10
    assert decoded.kind is FmiThreeWorkerResponseKind.CLOSED
    assert decoded.failure_kind is None
    assert decoded.error_message is None
    checkpoint_response_kind: FmiThreeWorkerResponseKind
    for checkpoint_response_kind in (
        FmiThreeWorkerResponseKind.CHECKPOINT_SAVED,
        FmiThreeWorkerResponseKind.CHECKPOINT_RESTORED,
        FmiThreeWorkerResponseKind.CHECKPOINT_DISCARDED,
    ):
        checkpoint_response: FmiThreeWorkerResponse = FmiThreeWorkerResponse(
            request_id=10 + int(checkpoint_response_kind),
            kind=checkpoint_response_kind,
            failure_kind=None,
            error_message=None,
        )
        decoded_checkpoint_response: FmiThreeWorkerResponse = (
            decode_fmi_three_worker_response(
                encode_fmi_three_worker_response(
                    checkpoint_response,
                    maximum_frame_size=64,
                    maximum_float64_values_per_request=16384,
                ),
                maximum_frame_size=64,
                maximum_float64_values_per_request=16384,
            )
        )
        assert decoded_checkpoint_response.kind == checkpoint_response_kind


def test_fmi_three_worker_error_response_round_trip() -> None:
    """Verify failures use typed categories and diagnostic text, not pickle.

    :return: None.
    """

    failure: FmiThreeWorkerResponse = FmiThreeWorkerResponse(
        request_id=11,
        kind=FmiThreeWorkerResponseKind.ERROR,
        failure_kind=FmiThreeWorkerFailureKind.LIFECYCLE,
        error_message="INITIALIZE requires a ready worker",
    )
    frame: bytes = encode_fmi_three_worker_response(
        failure,
        maximum_frame_size=128,
        maximum_float64_values_per_request=16384,
    )
    decoded: FmiThreeWorkerResponse = decode_fmi_three_worker_response(
        frame,
        maximum_frame_size=128,
        maximum_float64_values_per_request=16384,
    )

    assert decoded.request_id == 11
    assert decoded.kind is FmiThreeWorkerResponseKind.ERROR
    assert decoded.failure_kind is FmiThreeWorkerFailureKind.LIFECYCLE
    assert decoded.error_message == "INITIALIZE requires a ready worker"


@pytest.mark.parametrize(
    ("start_time", "stop_time", "relative_tolerance", "expected_error"),
    (
        (float("nan"), None, None, "start time must be finite"),
        (float("inf"), None, None, "start time must be finite"),
        (0.0, float("nan"), None, "stop time must be finite"),
        (0.0, float("inf"), None, "stop time must be finite"),
        (1.0, 1.0, None, "stop time must be greater"),
        (1.0, 0.0, None, "stop time must be greater"),
        (0.0, None, float("nan"), "relative tolerance must be finite"),
        (0.0, None, float("inf"), "relative tolerance must be finite"),
        (0.0, None, 0.0, "relative tolerance must be positive"),
        (0.0, None, -1.0, "relative tolerance must be positive"),
    ),
)
def test_fmi_three_worker_initialization_rejects_invalid_values(
    start_time: float,
    stop_time: float | None,
    relative_tolerance: float | None,
    expected_error: str,
) -> None:
    """Verify invalid FMI initialization values fail before encoding.

    :param start_time: Candidate start time.
    :param stop_time: Candidate stop time.
    :param relative_tolerance: Candidate relative tolerance.
    :param expected_error: Diagnostic fragment identifying the rejection.
    :return: None.
    """

    with pytest.raises(ValueError, match=expected_error):
        FmiThreeWorkerInitializationRequest(
            start_time=start_time,
            stop_time=stop_time,
            relative_tolerance=relative_tolerance,
            initial_float64_value_references=tuple(),
            initial_float64_values=tuple(),
            initial_int32_value_references=tuple(),
            initial_int32_values=tuple(),
            maximum_value_count=16384,
        )


def test_fmi_three_worker_initialization_rejects_invalid_assignments() -> None:
    """Reject malformed initial assignment collections before encoding.

    :return: None.
    """

    with pytest.raises(ValueError, match="initial Float64 references and values"):
        FmiThreeWorkerInitializationRequest(
            start_time=0.0,
            stop_time=None,
            relative_tolerance=None,
            initial_float64_value_references=tuple(),
            initial_float64_values=(1.0,),
            initial_int32_value_references=tuple(),
            initial_int32_values=tuple(),
            maximum_value_count=8,
        )
    with pytest.raises(ValueError, match="value references must be unique"):
        FmiThreeWorkerInitializationRequest(
            start_time=0.0,
            stop_time=None,
            relative_tolerance=None,
            initial_float64_value_references=(7, 7),
            initial_float64_values=(1.0, 2.0),
            initial_int32_value_references=tuple(),
            initial_int32_values=tuple(),
            maximum_value_count=8,
        )
    with pytest.raises(ValueError, match="values must be finite"):
        FmiThreeWorkerInitializationRequest(
            start_time=0.0,
            stop_time=None,
            relative_tolerance=None,
            initial_float64_value_references=(7,),
            initial_float64_values=(float("nan"),),
            initial_int32_value_references=tuple(),
            initial_int32_values=tuple(),
            maximum_value_count=8,
        )
    with pytest.raises(ValueError, match="numeric value count is outside"):
        FmiThreeWorkerInitializationRequest(
            start_time=0.0,
            stop_time=None,
            relative_tolerance=None,
            initial_float64_value_references=(7, 8),
            initial_float64_values=(1.0, 2.0),
            initial_int32_value_references=tuple(),
            initial_int32_values=tuple(),
            maximum_value_count=1,
        )


def test_fmi_three_worker_start_rejects_invalid_identity(tmp_path: Path) -> None:
    """Verify START cannot represent ambiguous paths or empty identities.

    :param tmp_path: Absolute temporary parent supplied by pytest.
    :return: None.
    """

    identity: FmiThreeWorkerStagingIdentity = _worker_staging_identity()
    with pytest.raises(ValueError, match="directory must be absolute"):
        FmiThreeWorkerStartRequest(
            Path("relative-fmu"),
            identity,
            "token",
            "model",
            "instance",
            FmuInterfaceMode.CO_SIMULATION,
            FmiThreeWorkerFloat64Profile.SCALAR,
            False,
            False,
        )
    with pytest.raises(ValueError, match="instantiation token must not be empty"):
        FmiThreeWorkerStartRequest(
            tmp_path,
            identity,
            "  ",
            "model",
            "instance",
            FmuInterfaceMode.CO_SIMULATION,
            FmiThreeWorkerFloat64Profile.SCALAR,
            False,
            False,
        )
    with pytest.raises(ValueError, match="model identifier must not be empty"):
        FmiThreeWorkerStartRequest(
            tmp_path,
            identity,
            "token",
            "",
            "instance",
            FmuInterfaceMode.CO_SIMULATION,
            FmiThreeWorkerFloat64Profile.SCALAR,
            False,
            False,
        )
    with pytest.raises(ValueError, match="instance name must not be empty"):
        FmiThreeWorkerStartRequest(
            tmp_path,
            identity,
            "token",
            "model",
            "\t",
            FmuInterfaceMode.CO_SIMULATION,
            FmiThreeWorkerFloat64Profile.SCALAR,
            False,
            False,
        )
    with pytest.raises(ValueError, match="Model Exchange cannot allow"):
        FmiThreeWorkerStartRequest(
            tmp_path,
            identity,
            "token",
            "model",
            "instance",
            FmuInterfaceMode.MODEL_EXCHANGE,
            FmiThreeWorkerFloat64Profile.SCALAR,
            False,
            False,
            True,
        )


def test_fmi_three_worker_staging_identity_rejects_invalid_bounds() -> None:
    """Verify tree identity fields are exact and finitely representable.

    :return: None.
    """

    with pytest.raises(ValueError, match="SHA-256 digest"):
        FmiThreeWorkerStagingIdentity("z" * 64, "b" * 64, 1, 1)
    with pytest.raises(ValueError, match="tree size"):
        FmiThreeWorkerStagingIdentity("a" * 64, "b" * 64, -1, 1)
    with pytest.raises(ValueError, match="entry count"):
        FmiThreeWorkerStagingIdentity("a" * 64, "b" * 64, 1, 0)


def test_fmi_three_worker_staging_identity_binds_fresh_inspection(
    tmp_path: Path,
) -> None:
    """Verify a same-size staged-tree mutation is rejected before native load.

    :param tmp_path: Absolute temporary parent supplied by pytest.
    :return: None.
    """

    staged_fmu_directory: Path = tmp_path / "staged-fmu"
    staged_fmu_directory.mkdir()
    model_description_path: Path = staged_fmu_directory / "modelDescription.xml"
    model_description_path.write_text(
        '<fmiModelDescription fmiVersion="3.0" modelName="WorkerIdentity" '
        'instantiationToken="worker-identity-token"/>',
        encoding="utf-8",
    )
    resources_directory: Path = staged_fmu_directory / "resources"
    resources_directory.mkdir()
    resource_path: Path = resources_directory / "state.txt"
    resource_path.write_text("one", encoding="utf-8")

    parent_receipt: FmuInspectionReceipt = inspect_fmu(
        staged_fmu_directory
    ).receipt
    expected: FmiThreeWorkerStagingIdentity = (
        build_fmi_three_worker_staging_identity(parent_receipt)
    )
    validate_fmi_three_worker_staging_identity(expected, parent_receipt)

    # Same-size content proves digest comparison is authoritative rather than
    # allowing size and cardinality to stand in for complete tree identity.
    resource_path.write_text("two", encoding="utf-8")
    child_receipt: FmuInspectionReceipt = inspect_fmu(staged_fmu_directory).receipt
    assert child_receipt.source_size == parent_receipt.source_size
    assert child_receipt.entry_count == parent_receipt.entry_count
    with pytest.raises(ValueError, match="identity changed"):
        validate_fmi_three_worker_staging_identity(expected, child_receipt)


def test_fmi_three_worker_response_correlation_fails_closed() -> None:
    """Verify stale ids and unexpected transitions are never accepted.

    :return: None.
    """

    response: FmiThreeWorkerResponse = FmiThreeWorkerResponse(
        request_id=15,
        kind=FmiThreeWorkerResponseKind.READY,
        failure_kind=None,
        error_message=None,
    )
    with pytest.raises(ValueError, match="request id does not match"):
        validate_fmi_three_worker_response_correlation(
            response,
            expected_request_id=14,
            expected_response_kind=FmiThreeWorkerResponseKind.READY,
        )
    with pytest.raises(ValueError, match="kind does not match"):
        validate_fmi_three_worker_response_correlation(
            response,
            expected_request_id=15,
            expected_response_kind=FmiThreeWorkerResponseKind.INITIALIZED,
        )


def test_fmi_three_worker_request_decoder_rejects_header_attacks() -> None:
    """Verify magic, direction, length, id, opcode and size fail closed.

    :return: None.
    """

    close_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=21,
        kind=FmiThreeWorkerRequestKind.CLOSE,
        start=None,
        initialization=None,
    )
    valid_frame: bytes = encode_fmi_three_worker_request(
        close_request,
        maximum_frame_size=64,
        maximum_float64_values_per_request=16384,
    )
    invalid_magic: bytes = b"BAD!" + valid_frame[4:]
    with pytest.raises(ValueError, match="magic is invalid"):
        decode_fmi_three_worker_request(
            invalid_magic, 64, maximum_float64_values_per_request=16384
        )
    invalid_version: bytes = valid_frame[:4] + b"\x01" + valid_frame[5:]
    with pytest.raises(ValueError, match="Unsupported.*version 1"):
        decode_fmi_three_worker_request(
            invalid_version, 64, maximum_float64_values_per_request=16384
        )
    previous_version: bytes = valid_frame[:4] + b"\x06" + valid_frame[5:]
    with pytest.raises(ValueError, match="Unsupported.*version 6"):
        decode_fmi_three_worker_request(
            previous_version, 64, maximum_float64_values_per_request=16384
        )
    reflected_request: bytes = valid_frame[:5] + b"\x02" + valid_frame[6:]
    with pytest.raises(ValueError, match="direction does not match"):
        decode_fmi_three_worker_request(
            reflected_request, 64, maximum_float64_values_per_request=16384
        )
    unknown_opcode: bytes = valid_frame[:6] + b"\xfe" + valid_frame[7:]
    with pytest.raises(ValueError, match="Unknown.*request kind 254"):
        decode_fmi_three_worker_request(
            unknown_opcode, 64, maximum_float64_values_per_request=16384
        )
    zero_request_id: bytes = valid_frame[:7] + (b"\x00" * 8) + valid_frame[15:]
    with pytest.raises(ValueError, match="request id"):
        decode_fmi_three_worker_request(
            zero_request_id, 64, maximum_float64_values_per_request=16384
        )
    wrong_body_size: bytes = valid_frame[:15] + struct.pack("!I", 1)
    with pytest.raises(ValueError, match="body length is inconsistent"):
        decode_fmi_three_worker_request(
            wrong_body_size, 64, maximum_float64_values_per_request=16384
        )
    with pytest.raises(ValueError, match="exceeds the configured size bound"):
        decode_fmi_three_worker_request(
            valid_frame, 18, maximum_float64_values_per_request=16384
        )


def test_fmi_three_worker_request_decoder_rejects_body_attacks(tmp_path: Path) -> None:
    """Verify invalid UTF-8, text lengths, flags and Float64 fail closed.

    :param tmp_path: Absolute temporary parent supplied by pytest.
    :return: None.
    """

    start_frame: bytes = encode_fmi_three_worker_request(
        _worker_start_request(tmp_path / "fmu"),
        maximum_frame_size=4096,
        maximum_float64_values_per_request=16384,
    )
    invalid_start_flags: bytearray = bytearray(start_frame)
    invalid_start_flags[19] = 12
    with pytest.raises(ValueError, match="START request has unknown flags"):
        decode_fmi_three_worker_request(bytes(invalid_start_flags), 4096, 16384)
    invalid_utf8: bytearray = bytearray(start_frame)
    invalid_utf8[22] = 255
    with pytest.raises(ValueError, match="not valid UTF-8"):
        decode_fmi_three_worker_request(bytes(invalid_utf8), 4096, 16384)
    truncated_text: bytearray = bytearray(start_frame)
    struct.pack_into("!H", truncated_text, 20, 65535)
    with pytest.raises(ValueError, match="truncated inside extracted FMU directory"):
        decode_fmi_three_worker_request(bytes(truncated_text), 4096, 16384)

    initialization: FmiThreeWorkerInitializationRequest = (
        FmiThreeWorkerInitializationRequest(
            start_time=0.0,
            stop_time=None,
            relative_tolerance=None,
            initial_float64_value_references=tuple(),
            initial_float64_values=tuple(),
            initial_int32_value_references=tuple(),
            initial_int32_values=tuple(),
            maximum_value_count=16384,
        )
    )
    initialize_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        22,
        FmiThreeWorkerRequestKind.INITIALIZE,
        None,
        initialization,
    )
    initialize_frame: bytes = encode_fmi_three_worker_request(
        initialize_request,
        maximum_frame_size=64,
        maximum_float64_values_per_request=16384,
    )
    invalid_initialize_flags: bytearray = bytearray(initialize_frame)
    invalid_initialize_flags[19] = 4
    with pytest.raises(ValueError, match="INITIALIZE request has unknown flags"):
        decode_fmi_three_worker_request(bytes(invalid_initialize_flags), 64, 16384)
    non_finite_start: bytearray = bytearray(initialize_frame)
    struct.pack_into("!d", non_finite_start, 20, float("nan"))
    with pytest.raises(ValueError, match="start time must be finite"):
        decode_fmi_three_worker_request(bytes(non_finite_start), 64, 16384)
    hidden_stop_time: bytearray = bytearray(initialize_frame)
    struct.pack_into("!d", hidden_stop_time, 28, float("nan"))
    with pytest.raises(ValueError, match="absent stop time slot.*canonical zero"):
        decode_fmi_three_worker_request(bytes(hidden_stop_time), 64, 16384)
    hidden_tolerance: bytearray = bytearray(initialize_frame)
    struct.pack_into("!d", hidden_tolerance, 36, 1.0e-6)
    with pytest.raises(ValueError, match="absent tolerance slot.*canonical zero"):
        decode_fmi_three_worker_request(bytes(hidden_tolerance), 64, 16384)


def test_fmi_three_worker_initialization_decoder_rejects_assignment_attacks() -> None:
    """Reject inconsistent, excessive, duplicate, and non-finite assignments.

    :return: None.
    """

    assigned_initialization: FmiThreeWorkerInitializationRequest = (
        FmiThreeWorkerInitializationRequest(
            start_time=0.0,
            stop_time=None,
            relative_tolerance=None,
            initial_float64_value_references=(7, 8),
            initial_float64_values=(1.0, 2.0),
            initial_int32_value_references=tuple(),
            initial_int32_values=tuple(),
            maximum_value_count=8,
        )
    )
    assigned_request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
        request_id=23,
        kind=FmiThreeWorkerRequestKind.INITIALIZE,
        start=None,
        initialization=assigned_initialization,
    )
    assigned_frame: bytes = encode_fmi_three_worker_request(
        request=assigned_request,
        maximum_frame_size=128,
        maximum_float64_values_per_request=8,
    )
    empty_count_with_trailing: bytearray = bytearray(assigned_frame)
    struct.pack_into("!II", empty_count_with_trailing, 44, 0, 0)
    with pytest.raises(ValueError, match="combined initialization count"):
        decode_fmi_three_worker_request(
            bytes(empty_count_with_trailing),
            128,
            maximum_float64_values_per_request=8,
        )
    inconsistent_count: bytearray = bytearray(assigned_frame)
    struct.pack_into("!I", inconsistent_count, 44, 3)
    with pytest.raises(ValueError, match="Float64 collection is truncated"):
        decode_fmi_three_worker_request(
            bytes(inconsistent_count),
            128,
            maximum_float64_values_per_request=8,
        )
    with pytest.raises(ValueError, match="Float64 count is outside"):
        decode_fmi_three_worker_request(
            assigned_frame,
            128,
            maximum_float64_values_per_request=1,
        )
    duplicate_initial_reference: bytearray = bytearray(assigned_frame)
    struct.pack_into("!I", duplicate_initial_reference, 56, 7)
    with pytest.raises(ValueError, match="value references must be unique"):
        decode_fmi_three_worker_request(
            bytes(duplicate_initial_reference),
            128,
            maximum_float64_values_per_request=8,
        )
    non_finite_initial_value: bytearray = bytearray(assigned_frame)
    struct.pack_into("!d", non_finite_initial_value, 60, float("inf"))
    with pytest.raises(ValueError, match="values must be finite"):
        decode_fmi_three_worker_request(
            bytes(non_finite_initial_value),
            128,
            maximum_float64_values_per_request=8,
        )


def test_fmi_three_worker_response_decoder_rejects_adversarial_frames() -> None:
    """Verify reflected, unknown and oversized responses fail closed.

    :return: None.
    """

    response: FmiThreeWorkerResponse = FmiThreeWorkerResponse(
        request_id=31,
        kind=FmiThreeWorkerResponseKind.CLOSED,
        failure_kind=None,
        error_message=None,
    )
    valid_frame: bytes = encode_fmi_three_worker_response(
        response,
        maximum_frame_size=64,
        maximum_float64_values_per_request=16384,
    )
    reflected_response: bytes = valid_frame[:5] + b"\x01" + valid_frame[6:]
    with pytest.raises(ValueError, match="direction does not match"):
        decode_fmi_three_worker_response(reflected_response, 64, 16384)
    unknown_response: bytes = valid_frame[:6] + b"\xfe" + valid_frame[7:]
    with pytest.raises(ValueError, match="Unknown.*response kind 254"):
        decode_fmi_three_worker_response(unknown_response, 64, 16384)

    error_response: FmiThreeWorkerResponse = FmiThreeWorkerResponse(
        request_id=32,
        kind=FmiThreeWorkerResponseKind.ERROR,
        failure_kind=FmiThreeWorkerFailureKind.PROTOCOL,
        error_message="bad frame",
    )
    error_frame: bytes = encode_fmi_three_worker_response(
        error_response,
        maximum_frame_size=64,
        maximum_float64_values_per_request=16384,
    )
    unknown_failure: bytes = error_frame[:19] + b"\xfe" + error_frame[20:]
    with pytest.raises(ValueError, match="Unknown.*failure kind 254"):
        decode_fmi_three_worker_response(unknown_failure, 64, 16384)
    with pytest.raises(ValueError, match="exceeds the configured size bound"):
        encode_fmi_three_worker_response(
            error_response, 20, maximum_float64_values_per_request=16384
        )


def test_fmi_three_worker_transport_uses_bounded_bytes_frames() -> None:
    """Verify the connection boundary uses bytes APIs and recv allocation bounds.

    :return: None.
    """

    first_connection: Connection
    second_connection: Connection
    first_connection, second_connection = Pipe(duplex=True)
    try:
        frame: bytes = b"bounded-frame"
        send_fmi_three_worker_frame(first_connection, frame, maximum_frame_size=32)
        received_frame: bytes = receive_fmi_three_worker_frame(
            second_connection,
            maximum_frame_size=32,
        )
        assert received_frame == frame

        first_connection.send_bytes(b"x" * 33)
        with pytest.raises(OSError):
            receive_fmi_three_worker_frame(second_connection, maximum_frame_size=32)
    finally:
        first_connection.close()
        second_connection.close()
