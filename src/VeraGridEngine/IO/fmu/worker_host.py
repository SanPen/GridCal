# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Parent-side ownership for the isolated FMI 3 numeric worker."""

from __future__ import annotations
from VeraGridEngine.enumerations import FmiThreeWorkerHostState

import math
from multiprocessing import get_context
from multiprocessing.connection import Connection, wait
from multiprocessing.context import BaseContext
from multiprocessing.process import BaseProcess
from pathlib import Path
import time
from typing import NoReturn

from VeraGridEngine.IO.fmu.Elements.description import (
    FmiThreeCoSimulationCapabilities,
    FmiThreeModelExchangeCapabilities,
    FmuModelDescription,
    FmuVariableDescription,
)
from VeraGridEngine.IO.fmu.native_binary import (
    validate_fmi_three_native_binary,
)
from VeraGridEngine.IO.fmu.profile import (
    FmiThreeWorkerFloat64Profile,
    resolve_fmi_three_configuration_float64_writable_references,
    resolve_fmi_three_configuration_uint64_writable_references,
    resolve_fmi_three_initialization_writable_references,
    is_fmi_three_input_or_tunable_parameter,
    is_fmi_three_initialization_mode_writable,
    validate_fmi_three_co_simulation_worker_profile,
    validate_fmi_three_model_exchange_worker_profile,
)
from VeraGridEngine.IO.fmu.Elements.protocol import (
    FmiThreeWorkerCompletedIntegratorStepRequest,
    FmiThreeWorkerCompletedIntegratorStepResult,
    FmiThreeWorkerDiscreteStatesResult,
    FmiThreeWorkerConfigureFloat64Request,
    FmiThreeWorkerConfigureUInt64Request,
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
    FmiThreeWorkerStartRequest,
    build_fmi_three_worker_staging_identity,
    decode_fmi_three_worker_response,
    encode_fmi_three_worker_request,
    receive_fmi_three_worker_frame,
    send_fmi_three_worker_frame,
    validate_fmi_three_worker_completed_step,
    validate_fmi_three_worker_float64_frame_capacity,
    validate_fmi_three_worker_float64_value_limit,
    validate_fmi_three_worker_initialization_frame_capacity,
    validate_fmi_three_worker_int32_frame_capacity,
    validate_fmi_three_worker_model_exchange_evaluation_frame_capacity,
    validate_fmi_three_worker_uint64_configuration_frame_capacity,
    validate_fmi_three_worker_response_correlation,
)
from VeraGridEngine.IO.fmu.workers import (
    run_fmi_three_worker,
)
from VeraGridEngine.IO.fmu.staging import FmuStagingArea, stage_fmu_source
from VeraGridEngine.enumerations import FmuInterfaceMode, FmuVariableType




class FmiThreeWorkerHostLimits:
    """Own every finite transport and shutdown limit selected by a caller.

    No product defaults are embedded because acceptable deadlines depend on
    the future simulation consumer and deployment environment.

    :param maximum_frame_size: Positive frame bound no greater than 256 KiB.
    :param maximum_float64_values_per_request: Established shared bound for
        numeric values and scalar UInt64 Configuration Mode values.
    :param response_timeout_seconds: Maximum wait for one worker response.
    :param graceful_join_timeout_seconds: Wait after a terminal response.
    :param terminate_join_timeout_seconds: Wait after process termination.
    :param kill_join_timeout_seconds: Final wait after forced process kill.
    """

    __slots__ = (
        "maximum_frame_size",
        "maximum_float64_values_per_request",
        "response_timeout_seconds",
        "graceful_join_timeout_seconds",
        "terminate_join_timeout_seconds",
        "kill_join_timeout_seconds",
    )

    def __init__(
        self,
        maximum_frame_size: int,
        maximum_float64_values_per_request: int,
        response_timeout_seconds: float,
        graceful_join_timeout_seconds: float,
        terminate_join_timeout_seconds: float,
        kill_join_timeout_seconds: float,
    ) -> None:
        """Validate and store explicit worker supervision limits.

        :param maximum_frame_size: Positive frame bound no greater than 256 KiB.
        :param maximum_float64_values_per_request: Established shared bound for
            numeric values and scalar UInt64 Configuration Mode values.
        :param response_timeout_seconds: Maximum wait for one worker response.
        :param graceful_join_timeout_seconds: Wait after a terminal response.
        :param terminate_join_timeout_seconds: Wait after process termination.
        :param kill_join_timeout_seconds: Final wait after forced process kill.
        :return: None.
        """

        if 0 < maximum_frame_size <= 262144:
            pass
        else:
            raise ValueError(
                "FMI 3 worker maximum frame size must be within 1 and 262144 bytes"
            )
        validate_fmi_three_worker_float64_value_limit(
            maximum_float64_values_per_request
        )
        validated_response_timeout: float = _validate_positive_timeout(
            response_timeout_seconds,
            "response timeout",
        )
        validated_graceful_join_timeout: float = _validate_positive_timeout(
            graceful_join_timeout_seconds,
            "graceful join timeout",
        )
        validated_terminate_join_timeout: float = _validate_positive_timeout(
            terminate_join_timeout_seconds,
            "terminate join timeout",
        )
        validated_kill_join_timeout: float = _validate_positive_timeout(
            kill_join_timeout_seconds,
            "kill join timeout",
        )
        self.maximum_frame_size: int = maximum_frame_size
        self.maximum_float64_values_per_request: int = (
            maximum_float64_values_per_request
        )
        self.response_timeout_seconds: float = validated_response_timeout
        self.graceful_join_timeout_seconds: float = (
            validated_graceful_join_timeout
        )
        self.terminate_join_timeout_seconds: float = (
            validated_terminate_join_timeout
        )
        self.kill_join_timeout_seconds: float = validated_kill_join_timeout


def _validate_positive_timeout(timeout_seconds: float, field_name: str) -> float:
    """Return one finite positive timeout selected by the caller.

    :param timeout_seconds: Timeout value to normalize.
    :param field_name: Limit name used in validation diagnostics.
    :return: Finite positive timeout in seconds.
    """

    validated_timeout: float = float(timeout_seconds)
    if math.isfinite(validated_timeout) and validated_timeout > 0.0:
        pass
    else:
        raise ValueError(f"FMI 3 worker {field_name} must be finite and positive")
    return validated_timeout


def _raise_worker_error_response(response: FmiThreeWorkerResponse) -> NoReturn:
    """Translate one terminal wire error into an existing importer exception.

    :param response: Correlated ERROR response from the isolated worker.
    :return: This function does not return.
    """

    failure_kind: FmiThreeWorkerFailureKind | None = response.failure_kind
    error_message: str | None = response.error_message
    if failure_kind is not None and error_message is not None:
        diagnostic: str = f"FMI 3 worker {failure_kind.name}: {error_message}"
    else:
        raise RuntimeError("FMI 3 worker returned an incomplete ERROR response")
    if failure_kind == FmiThreeWorkerFailureKind.DEPENDENCY:
        raise ImportError(diagnostic)
    else:
        if failure_kind == FmiThreeWorkerFailureKind.ARCHIVE:
            raise ValueError(diagnostic)
        else:
            if failure_kind == FmiThreeWorkerFailureKind.LIFECYCLE:
                raise RuntimeError(diagnostic)
            else:
                if failure_kind == FmiThreeWorkerFailureKind.VARIABLE_ACCESS:
                    raise ValueError(diagnostic)
                else:
                    raise RuntimeError(diagnostic)


class FmiThreeWorkerHost:
    """Supervise one FMI 3 numeric worker and its private staging lifetime.

    Instances are prepared before spawning so callers retain the owner even if
    a terminal platform failure prevents the process from being proven dead.
    Use :func:`prepare_fmi_three_worker_host` to construct one.

    :param staging_area: Private staged FMU transferred to this host.
    :param instantiation_token: Exact FMI 3 model-instantiation identity.
    :param model_identifier: Exact selected-interface native model identifier.
    :param interface_mode: Authenticated Model Exchange or Co-Simulation mode.
    :param float64_profile: Scalar or constant-array access profile.
    :param can_handle_variable_communication_step_size: Whether Co-Simulation
        step sizes may vary, or ``None`` for Model Exchange.
    :param might_return_early_from_do_step: Whether Co-Simulation may return
        early without an Intermediate Update request, or ``None`` for Model Exchange.
    :param early_return_allowed: Whether the importing session can consume a
        partial Co-Simulation step.
    :param configuration_float64_writable_references: Parent Float64 configuration ACL.
    :param configuration_uint64_writable_references: Parent UInt64 configuration ACL.
    :param initialization_writable_value_references: Parent-parsed initialization ACL.
    :param readable_int32_references: Parent scalar Int32 read ACL.
    :param writable_int32_references: Parent scalar Int32 runtime-write ACL.
    :param initialization_writable_int32_references: Parent scalar Int32
        initialization-write ACL.
    :param limits: Explicit finite transport and shutdown limits.
    """

    __slots__ = (
        "_staging_area",
        "_instantiation_token",
        "_model_identifier",
        "_interface_mode",
        "_float64_profile",
        "_can_get_and_set_fmu_state",
        "_can_serialize_fmu_state",
        "_needs_completed_integrator_step",
        "_can_handle_variable_communication_step_size",
        "_might_return_early_from_do_step",
        "_early_return_allowed",
        "_configuration_float64_writable_references",
        "_configuration_uint64_writable_references",
        "_initialization_writable_value_references",
        "_readable_int32_references",
        "_writable_int32_references",
        "_initialization_writable_int32_references",
        "_limits",
        "_process",
        "_connection",
        "_next_request_id",
        "_state",
        "_exit_code",
        "_current_communication_time",
        "_communication_step_size",
        "_checkpoint_host_state",
        "_checkpoint_communication_time",
        "_checkpoint_communication_step_size",
        "_spawn_outcome_unknown",
    )

    def __init__(
        self,
        staging_area: FmuStagingArea,
        instantiation_token: str,
        model_identifier: str,
        interface_mode: FmuInterfaceMode,
        float64_profile: FmiThreeWorkerFloat64Profile,
        can_get_and_set_fmu_state: bool,
        can_serialize_fmu_state: bool,
        needs_completed_integrator_step: bool | None,
        can_handle_variable_communication_step_size: bool | None,
        might_return_early_from_do_step: bool | None,
        early_return_allowed: bool,
        configuration_float64_writable_references: frozenset[int],
        configuration_uint64_writable_references: frozenset[int],
        initialization_writable_value_references: frozenset[int],
        readable_int32_references: frozenset[int],
        writable_int32_references: frozenset[int],
        initialization_writable_int32_references: frozenset[int],
        limits: FmiThreeWorkerHostLimits,
    ) -> None:
        """Store prepared ownership without spawning or loading native code.

        :param staging_area: Private staged FMU transferred to this host.
        :param instantiation_token: Exact FMI 3 model-instantiation identity.
        :param model_identifier: Exact selected-interface native model identifier.
        :param interface_mode: Authenticated Model Exchange or Co-Simulation mode.
        :param float64_profile: Scalar or constant-array access profile.
        :param can_get_and_set_fmu_state: Whether native checkpoints are
            supported.
        :param can_serialize_fmu_state: Whether native checkpoints can be
            serialized.
        :param needs_completed_integrator_step: Model Exchange notification
            requirement, or ``None`` for Co-Simulation.
        :param can_handle_variable_communication_step_size: Whether Co-Simulation
            step sizes may vary, or ``None`` for Model Exchange.
        :param might_return_early_from_do_step: Whether Co-Simulation may return
            early without an Intermediate Update request, or ``None`` for Model Exchange.
        :param early_return_allowed: Whether the importing session can consume a
            partial Co-Simulation step.
        :param configuration_float64_writable_references: Parent Float64 configuration ACL.
        :param configuration_uint64_writable_references: Parent UInt64 configuration ACL.
        :param initialization_writable_value_references: Parent-parsed initialization ACL.
        :param readable_int32_references: Parent scalar Int32 read ACL.
        :param writable_int32_references: Parent scalar Int32 runtime-write ACL.
        :param initialization_writable_int32_references: Parent scalar Int32
            initialization-write ACL.
        :param limits: Explicit finite transport and shutdown limits.
        :return: None.
        """

        if staging_area.is_closed():
            raise ValueError("Closed FMI 3 staging cannot be supervised")
        else:
            pass
        if instantiation_token.strip() != "" and model_identifier.strip() != "":
            pass
        else:
            raise ValueError("FMI 3 worker host identity fields must not be empty")
        if isinstance(float64_profile, FmiThreeWorkerFloat64Profile):
            pass
        else:
            raise ValueError("FMI 3 worker host Float64 profile is invalid")
        if interface_mode in (
            FmuInterfaceMode.MODEL_EXCHANGE,
            FmuInterfaceMode.CO_SIMULATION,
        ):
            pass
        else:
            raise ValueError("FMI 3 worker host interface mode is invalid")
        if (
            isinstance(can_get_and_set_fmu_state, bool)
            and isinstance(can_serialize_fmu_state, bool)
            and (can_get_and_set_fmu_state or not can_serialize_fmu_state)
        ):
            pass
        else:
            raise ValueError("FMI 3 worker host state capabilities are invalid")
        if (
            interface_mode == FmuInterfaceMode.CO_SIMULATION
            and can_handle_variable_communication_step_size is not None
            and might_return_early_from_do_step is not None
            and needs_completed_integrator_step is None
        ):
            pass
        else:
            if (
                interface_mode == FmuInterfaceMode.MODEL_EXCHANGE
                and can_handle_variable_communication_step_size is None
                and might_return_early_from_do_step is None
                and not early_return_allowed
                and isinstance(needs_completed_integrator_step, bool)
            ):
                pass
            else:
                raise ValueError(
                    "FMI 3 worker host communication-step capability contradicts "
                    "its interface mode"
                )
        self._staging_area: FmuStagingArea = staging_area
        self._instantiation_token: str = instantiation_token
        self._model_identifier: str = model_identifier
        self._interface_mode: FmuInterfaceMode = interface_mode
        self._float64_profile: FmiThreeWorkerFloat64Profile = float64_profile
        self._can_get_and_set_fmu_state: bool = can_get_and_set_fmu_state
        self._can_serialize_fmu_state: bool = can_serialize_fmu_state
        self._needs_completed_integrator_step: bool | None = (
            needs_completed_integrator_step
        )
        self._can_handle_variable_communication_step_size: bool | None = (
            can_handle_variable_communication_step_size
        )
        self._might_return_early_from_do_step: bool | None = (
            might_return_early_from_do_step
        )
        self._early_return_allowed: bool = early_return_allowed
        self._configuration_float64_writable_references: frozenset[int] = (
            frozenset(configuration_float64_writable_references)
        )
        self._configuration_uint64_writable_references: frozenset[int] = (
            frozenset(configuration_uint64_writable_references)
        )
        self._initialization_writable_value_references: frozenset[int] = frozenset(
            initialization_writable_value_references
        )
        self._readable_int32_references: frozenset[int] = frozenset(
            readable_int32_references
        )
        self._writable_int32_references: frozenset[int] = frozenset(
            writable_int32_references
        )
        self._initialization_writable_int32_references: frozenset[int] = frozenset(
            initialization_writable_int32_references
        )
        self._limits: FmiThreeWorkerHostLimits = limits
        self._process: BaseProcess | None = None
        self._connection: Connection | None = None
        self._next_request_id: int = 1
        self._state: FmiThreeWorkerHostState = (
            FmiThreeWorkerHostState.CREATED
        )
        self._exit_code: int | None = None
        self._current_communication_time: float | None = None
        self._communication_step_size: float | None = None
        self._checkpoint_host_state: FmiThreeWorkerHostState | None = None
        self._checkpoint_communication_time: float | None = None
        self._checkpoint_communication_step_size: float | None = None
        self._spawn_outcome_unknown: bool = False

    def get_state(self) -> FmiThreeWorkerHostState:
        """Return the explicit parent-side lifecycle state.

        :return: Current worker-host state.
        """

        return self._state

    def get_interface_mode(self) -> FmuInterfaceMode:
        """Return the interface authenticated before private staging.

        :return: Model Exchange or Co-Simulation mode owned by this host.
        """

        return self._interface_mode

    def supports_fmu_state_checkpoint(self) -> bool:
        """Return whether the authenticated interface supports Get/Set state.

        :return: ``True`` when native save, restore, and free are available.
        """

        return self._can_get_and_set_fmu_state

    def supports_serialized_fmu_state(self) -> bool:
        """Return whether the authenticated interface supports state bytes.

        :return: ``True`` when FMI state serialization is declared.
        """

        return self._can_serialize_fmu_state

    def needs_completed_integrator_step(self) -> bool:
        """Return the authenticated Model Exchange notification requirement.

        :return: Whether every accepted integrator step needs native notification.
        :raises RuntimeError: If this host owns Co-Simulation.
        """

        if self._needs_completed_integrator_step is not None:
            return self._needs_completed_integrator_step
        else:
            raise RuntimeError(
                "FMI 3 completed-integrator-step capability requires Model Exchange"
            )

    def get_process_id(self) -> int | None:
        """Return the child process identifier while the handle is retained.

        :return: Spawned child PID, or ``None`` before spawning or after cleanup.
        """

        process: BaseProcess | None = self._process
        if process is not None:
            process_id: int | None = process.pid
        else:
            process_id = None
        return process_id

    def get_exit_code(self) -> int | None:
        """Return the captured child exit code after death is proven.

        :return: Child exit code, or ``None`` before confirmed process death.
        """

        return self._exit_code

    def get_staging_root(self) -> Path:
        """Return the exact private staging root retained by this host.

        :return: Parent-owned staging root path.
        """

        return self._staging_area.get_root()

    def get_staged_fmu_directory(self) -> Path:
        """Return the private FMU directory consumed by the child process.

        :return: Parent-owned staged FMU directory.
        """

        return self._staging_area.get_fmu_directory()

    def is_closed(self) -> bool:
        """Return whether process and staging ownership were fully released.

        :return: ``True`` only after the host reached CLOSED.
        """

        return self._state == FmiThreeWorkerHostState.CLOSED

    def _allocate_request_id(self) -> int:
        """Allocate one monotonically increasing positive UInt64 identifier.

        :return: Identifier for the next single in-flight request.
        """

        request_id: int = self._next_request_id
        if 0 < request_id <= 18446744073709551615:
            pass
        else:
            raise RuntimeError("FMI 3 worker request identifiers are exhausted")
        if request_id < 18446744073709551615:
            self._next_request_id = request_id + 1
        else:
            self._next_request_id = 18446744073709551616
        return request_id

    def _stop_worker_process(self, allow_graceful_join: bool) -> bool:
        """Close transport and escalate until child death is proven or bounded.

        :param allow_graceful_join: Whether to wait before sending termination.
        :return: ``True`` only when the child is confirmed dead.
        """

        connection: Connection | None = self._connection
        if connection is not None:
            try:
                connection.close()
            except (OSError, ValueError):
                pass
            self._connection = None
        else:
            pass
        process: BaseProcess | None = self._process
        if process is None:
            process_stopped: bool = True
        else:
            if allow_graceful_join:
                process.join(timeout=self._limits.graceful_join_timeout_seconds)
            else:
                pass
            if process.is_alive():
                try:
                    process.terminate()
                except OSError:
                    pass
                process.join(timeout=self._limits.terminate_join_timeout_seconds)
            else:
                pass
            if process.is_alive():
                try:
                    process.kill()
                except OSError:
                    pass
                process.join(timeout=self._limits.kill_join_timeout_seconds)
            else:
                pass
            process_stopped = not process.is_alive() and process.exitcode is not None
            if process_stopped:
                self._exit_code = process.exitcode
                try:
                    process.close()
                except (OSError, ValueError):
                    pass
                self._process = None
            else:
                pass
        return process_stopped

    def _release_after_failure(
        self,
        failure_message: str,
        allow_graceful_join: bool,
    ) -> NoReturn:
        """Stop a failed worker and release staging only after proven death.

        :param failure_message: Parent-side failure to report.
        :param allow_graceful_join: Whether the worker is expected to exit itself.
        :return: This method does not return.
        """

        self._state = FmiThreeWorkerHostState.FAILED
        process_stopped: bool = self._stop_worker_process(allow_graceful_join)
        if process_stopped:
            self._staging_area.close()
            raise RuntimeError(failure_message)
        else:
            raise RuntimeError(
                f"{failure_message}; staging retained because child death is unproven"
            )

    def _release_incomplete_start(self, process_start_attempted: bool) -> None:
        """Release a failed or interrupted START without assuming child death.

        A process whose ``start`` call was interrupted before publishing a PID
        has an unknown spawn outcome. Its staging must remain intact because
        the parent cannot prove that no native child still references it.

        :param process_start_attempted: Whether ``BaseProcess.start`` was entered.
        :return: None.
        """

        self._state = FmiThreeWorkerHostState.FAILED
        process: BaseProcess | None = self._process
        if process is not None:
            process_identifier: int | None = process.pid
        else:
            process_identifier = None
        if not process_start_attempted:
            connection: Connection | None = self._connection
            if connection is not None:
                try:
                    connection.close()
                except (OSError, ValueError):
                    pass
                self._connection = None
            else:
                pass
            if process is not None:
                try:
                    process.close()
                except (OSError, ValueError):
                    pass
                self._process = None
            else:
                pass
            process_stopped: bool = True
        else:
            if process is not None and process_identifier is not None:
                process_stopped = self._stop_worker_process(
                    allow_graceful_join=False
                )
            else:
                unknown_connection: Connection | None = self._connection
                if unknown_connection is not None:
                    try:
                        unknown_connection.close()
                    except (OSError, ValueError):
                        pass
                    self._connection = None
                else:
                    pass
                process_stopped = False
        if process_stopped:
            self._spawn_outcome_unknown = False
            self._staging_area.close()
        else:
            self._spawn_outcome_unknown = True

    def _exchange(
        self,
        request: FmiThreeWorkerRequest,
        expected_response_kind: FmiThreeWorkerResponseKind,
    ) -> FmiThreeWorkerResponse:
        """Send one request and receive one correlated response before deadline.

        Process exit wakes the wait even when another handle keeps the Pipe
        open. A readable response takes precedence over simultaneous exit.

        :param request: Typed request for the single in-flight transition.
        :param expected_response_kind: Successful response required by the caller.
        :return: Correlated successful response.
        """

        connection: Connection | None = self._connection
        if connection is not None:
            pass
        else:
            self._release_after_failure(
                "FMI 3 worker connection is unavailable",
                allow_graceful_join=False,
            )
        process: BaseProcess | None = self._process
        if process is not None:
            process_sentinel: int = process.sentinel
        else:
            self._release_after_failure(
                "FMI 3 worker process is unavailable",
                allow_graceful_join=False,
            )
        try:
            request_frame: bytes = encode_fmi_three_worker_request(
                request=request,
                maximum_frame_size=self._limits.maximum_frame_size,
                maximum_float64_values_per_request=(
                    self._limits.maximum_float64_values_per_request
                ),
            )
            send_fmi_three_worker_frame(
                connection=connection,
                frame=request_frame,
                maximum_frame_size=self._limits.maximum_frame_size,
            )
        except (OSError, ValueError) as error:
            self._release_after_failure(
                f"FMI 3 worker request transport failed: {error}",
                allow_graceful_join=False,
            )

        response_deadline: float = (
            time.monotonic() + self._limits.response_timeout_seconds
        )
        remaining_seconds: float = response_deadline - time.monotonic()
        try:
            if remaining_seconds > 0.0:
                # A duplicated peer handle can suppress Pipe EOF after a
                # bootstrap failure, so process death must wake this wait too.
                ready_objects: list[Connection | int] = wait(
                    (connection, process_sentinel),
                    timeout=remaining_seconds,
                )
                response_available: bool = connection in ready_objects
                process_exited: bool = process_sentinel in ready_objects
                if process_exited and not response_available:
                    # Prefer a terminal response sent just before process exit.
                    response_available = connection.poll(0.0)
                else:
                    pass
            else:
                response_available = False
                process_exited = False
        except (OSError, ValueError) as error:
            self._release_after_failure(
                f"FMI 3 worker response polling failed: {error}",
                allow_graceful_join=True,
            )
        if response_available:
            pass
        else:
            if process_exited:
                # The signalled sentinel proves death; reap without replacing
                # the natural exit code by terminating an already dead worker.
                process.join(timeout=0.0)
                self._release_after_failure(
                    f"FMI 3 worker exited with code {process.exitcode} before "
                    f"response for request {request.request_id}",
                    allow_graceful_join=True,
                )
            else:
                pass
            self._release_after_failure(
                f"FMI 3 worker response timed out for request {request.request_id}",
                allow_graceful_join=False,
            )
        try:
            response_frame: bytes = receive_fmi_three_worker_frame(
                connection=connection,
                maximum_frame_size=self._limits.maximum_frame_size,
            )
            response: FmiThreeWorkerResponse = decode_fmi_three_worker_response(
                frame=response_frame,
                maximum_frame_size=self._limits.maximum_frame_size,
                maximum_float64_values_per_request=(
                    self._limits.maximum_float64_values_per_request
                ),
            )
            validate_fmi_three_worker_response_correlation(
                response=response,
                expected_request_id=request.request_id,
                expected_response_kind=expected_response_kind,
            )
        except (EOFError, OSError, ValueError) as error:
            self._release_after_failure(
                f"FMI 3 worker response transport failed: {error}",
                allow_graceful_join=True,
            )
        if response.kind == FmiThreeWorkerResponseKind.ERROR:
            self._state = FmiThreeWorkerHostState.FAILED
            process_stopped = self._stop_worker_process(allow_graceful_join=True)
            if process_stopped:
                self._staging_area.close()
                _raise_worker_error_response(response)
            else:
                raise RuntimeError(
                    "FMI 3 worker staging retained because child death is unproven"
                )
        else:
            return response

    def start(
        self,
        instance_name: str,
        visible: bool,
        debug_logging: bool,
    ) -> None:
        """Spawn the fixed worker target and complete its START transition.

        :param instance_name: Stable native FMI instance name.
        :param visible: Whether the native FMU may expose its own interface.
        :param debug_logging: Whether FMI debug logging is requested.
        :return: None.
        """

        if self._state == FmiThreeWorkerHostState.CREATED:
            pass
        else:
            raise RuntimeError("FMI 3 worker host START requires CREATED state")
        child_connection: Connection | None = None
        process_start_attempted: bool = False
        try:
            self._state = FmiThreeWorkerHostState.STARTING
            request_id: int = self._allocate_request_id()
            start_body: FmiThreeWorkerStartRequest = FmiThreeWorkerStartRequest(
                extracted_fmu_directory=self._staging_area.get_fmu_directory(),
                staging_identity=build_fmi_three_worker_staging_identity(
                    self._staging_area.get_fmu_directory_receipt()
                ),
                instantiation_token=self._instantiation_token,
                model_identifier=self._model_identifier,
                instance_name=instance_name,
                interface_mode=self._interface_mode,
                float64_profile=self._float64_profile,
                visible=visible,
                debug_logging=debug_logging,
                early_return_allowed=self._early_return_allowed,
            )
            request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
                request_id=request_id,
                kind=FmiThreeWorkerRequestKind.START,
                start=start_body,
                initialization=None,
            )
            process_context: BaseContext = get_context("spawn")
            parent_connection: Connection
            parent_connection, child_connection = process_context.Pipe(
                duplex=True
            )
            self._connection = parent_connection
            process: BaseProcess = process_context.Process(
                target=run_fmi_three_worker,
                args=(
                    child_connection,
                    self._limits.maximum_frame_size,
                    self._limits.maximum_float64_values_per_request,
                ),
            )
            self._process = process
            process_start_attempted = True
            try:
                process.start()
            except (OSError, RuntimeError) as error:
                self._release_incomplete_start(process_start_attempted)
                raise RuntimeError(
                    "Could not spawn the FMI 3 worker process"
                ) from error
            child_connection.close()
            child_connection = None
            self._exchange(
                request=request,
                expected_response_kind=FmiThreeWorkerResponseKind.READY,
            )
            self._state = FmiThreeWorkerHostState.READY
        except BaseException:
            if self._state == FmiThreeWorkerHostState.STARTING:
                self._release_incomplete_start(process_start_attempted)
            else:
                pass
            raise
        finally:
            if child_connection is not None:
                try:
                    child_connection.close()
                except (OSError, ValueError):
                    pass
            else:
                pass

    def configure_float64(
        self,
        value_references: tuple[int, ...],
        values: tuple[float, ...],
    ) -> None:
        """Apply one structural Float64 batch through Configuration Mode.

        :param value_references: Ordered unique structural-parameter references.
        :param values: Concatenated finite values for the references.
        :return: None.
        """

        if self._state == FmiThreeWorkerHostState.READY:
            pass
        else:
            raise RuntimeError(
                "FMI 3 worker host CONFIGURE_FLOAT64 requires READY state"
            )
        if self._float64_profile == FmiThreeWorkerFloat64Profile.SCALAR:
            if len(value_references) == len(values):
                pass
            else:
                raise ValueError(
                    "FMI 3 scalar worker configuration references and values "
                    "must align"
                )
        else:
            pass
        configuration: FmiThreeWorkerConfigureFloat64Request = (
            FmiThreeWorkerConfigureFloat64Request(
                value_references=value_references,
                values=values,
                maximum_value_count=(
                    self._limits.maximum_float64_values_per_request
                ),
            )
        )
        validate_fmi_three_worker_float64_frame_capacity(
            request_kind=FmiThreeWorkerRequestKind.CONFIGURE_FLOAT64,
            value_reference_count=len(configuration.value_references),
            serialized_value_count=len(configuration.values),
            maximum_frame_size=self._limits.maximum_frame_size,
            maximum_value_count=(
                self._limits.maximum_float64_values_per_request
            ),
        )
        references_are_allowed: bool = True
        value_reference: int
        for value_reference in configuration.value_references:
            if value_reference in self._configuration_float64_writable_references:
                pass
            else:
                references_are_allowed = False
        if references_are_allowed:
            pass
        else:
            raise ValueError(
                "FMI 3 worker host CONFIGURE_FLOAT64 reference is not writable "
                "in Configuration Mode"
            )
        request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=self._allocate_request_id(),
            kind=FmiThreeWorkerRequestKind.CONFIGURE_FLOAT64,
            start=None,
            initialization=None,
            configuration=configuration,
        )
        self._state = FmiThreeWorkerHostState.CONFIGURING
        self._exchange(
            request=request,
            expected_response_kind=FmiThreeWorkerResponseKind.CONFIGURED,
        )
        self._state = FmiThreeWorkerHostState.READY

    def configure_uint64(
        self,
        value_references: tuple[int, ...],
        values: tuple[int, ...],
    ) -> None:
        """Apply scalar structural UInt64 values through Configuration Mode.

        :param value_references: Ordered unique structural UInt64 references.
        :param values: UInt64 values aligned one-to-one with the references.
        :return: None.
        """

        if self._state == FmiThreeWorkerHostState.READY:
            pass
        else:
            raise RuntimeError(
                "FMI 3 worker host CONFIGURE_UINT64 requires READY state"
            )
        configuration: FmiThreeWorkerConfigureUInt64Request = (
            FmiThreeWorkerConfigureUInt64Request(
                value_references=value_references,
                values=values,
                maximum_value_count=(
                    self._limits.maximum_float64_values_per_request
                ),
            )
        )
        validate_fmi_three_worker_uint64_configuration_frame_capacity(
            value_count=len(configuration.values),
            maximum_frame_size=self._limits.maximum_frame_size,
            maximum_value_count=(
                self._limits.maximum_float64_values_per_request
            ),
        )
        references_are_allowed: bool = True
        value_reference: int
        for value_reference in configuration.value_references:
            if value_reference in self._configuration_uint64_writable_references:
                pass
            else:
                references_are_allowed = False
        if references_are_allowed:
            pass
        else:
            raise ValueError(
                "FMI 3 worker host CONFIGURE_UINT64 reference is not writable "
                "in Configuration Mode"
            )
        request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=self._allocate_request_id(),
            kind=FmiThreeWorkerRequestKind.CONFIGURE_UINT64,
            start=None,
            initialization=None,
            configuration_uint64=configuration,
        )
        self._state = FmiThreeWorkerHostState.CONFIGURING
        self._exchange(
            request=request,
            expected_response_kind=FmiThreeWorkerResponseKind.CONFIGURED,
        )
        self._state = FmiThreeWorkerHostState.READY

    def initialize(
        self,
        start_time: float,
        stop_time: float | None,
        relative_tolerance: float | None,
        initial_float64_value_references: tuple[int, ...],
        initial_float64_values: tuple[float, ...],
        initial_int32_value_references: tuple[int, ...] = tuple(),
        initial_int32_values: tuple[int, ...] = tuple(),
    ) -> None:
        """Complete the bounded FMI 3 initialization transition.

        :param start_time: Finite simulation start time.
        :param stop_time: Optional finite stop time greater than start time.
        :param relative_tolerance: Optional finite positive relative tolerance.
        :param initial_float64_value_references: Ordered scalar assignments made
            inside Initialization Mode, or an empty tuple for no assignments.
        :param initial_float64_values: Finite values aligned with the references.
        :param initial_int32_value_references: Ordered scalar Int32 assignments
            made inside Initialization Mode, or an empty tuple.
        :param initial_int32_values: Signed values aligned with the Int32
            references.
        :return: None.
        """

        if self._state == FmiThreeWorkerHostState.READY:
            pass
        else:
            raise RuntimeError("FMI 3 worker host INITIALIZE requires READY state")
        if self._float64_profile == FmiThreeWorkerFloat64Profile.SCALAR:
            if len(initial_float64_value_references) == len(initial_float64_values):
                pass
            else:
                raise ValueError(
                    "FMI 3 scalar worker initial references and values must align"
                )
        else:
            pass
        initialization_body: FmiThreeWorkerInitializationRequest = (
            FmiThreeWorkerInitializationRequest(
                start_time=start_time,
                stop_time=stop_time,
                relative_tolerance=relative_tolerance,
                initial_float64_value_references=(
                    initial_float64_value_references
                ),
                initial_float64_values=initial_float64_values,
                initial_int32_value_references=initial_int32_value_references,
                initial_int32_values=initial_int32_values,
                maximum_value_count=(
                    self._limits.maximum_float64_values_per_request
                ),
            )
        )
        validate_fmi_three_worker_initialization_frame_capacity(
            float64_value_reference_count=len(
                initialization_body.initial_float64_value_references
            ),
            float64_serialized_value_count=len(
                initialization_body.initial_float64_values
            ),
            int32_value_reference_count=len(
                initialization_body.initial_int32_value_references
            ),
            int32_value_count=len(initialization_body.initial_int32_values),
            maximum_frame_size=self._limits.maximum_frame_size,
            maximum_value_count=(
                self._limits.maximum_float64_values_per_request
            ),
        )
        initial_float64_references_are_allowed: bool = True
        initial_float64_value_reference: int
        for initial_float64_value_reference in (
            initialization_body.initial_float64_value_references
        ):
            if (
                initial_float64_value_reference
                in self._initialization_writable_value_references
            ):
                pass
            else:
                initial_float64_references_are_allowed = False
        initial_int32_references_are_allowed: bool = True
        initial_int32_value_reference: int
        for initial_int32_value_reference in (
            initialization_body.initial_int32_value_references
        ):
            if (
                initial_int32_value_reference
                in self._initialization_writable_int32_references
            ):
                pass
            else:
                initial_int32_references_are_allowed = False
        if (
            initial_float64_references_are_allowed
            and initial_int32_references_are_allowed
        ):
            pass
        else:
            raise ValueError(
                "FMI 3 worker host initial numeric reference is not writable in "
                "Initialization Mode"
            )
        request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=self._allocate_request_id(),
            kind=FmiThreeWorkerRequestKind.INITIALIZE,
            start=None,
            initialization=initialization_body,
        )
        self._state = FmiThreeWorkerHostState.INITIALIZING
        self._exchange(
            request=request,
            expected_response_kind=FmiThreeWorkerResponseKind.INITIALIZED,
        )
        self._current_communication_time = initialization_body.start_time
        if self._interface_mode == FmuInterfaceMode.MODEL_EXCHANGE:
            self._state = FmiThreeWorkerHostState.EVENT_MODE
        else:
            self._state = FmiThreeWorkerHostState.INITIALIZED

    def set_float64(
        self,
        value_references: tuple[int, ...],
        values: tuple[float, ...],
    ) -> None:
        """Write one bounded finite writable Float64 batch in the active mode.

        :param value_references: Ordered unique scalar or array references.
        :param values: Concatenated finite values for the references.
        :return: None.
        """

        if self._interface_mode == FmuInterfaceMode.CO_SIMULATION:
            if self._state in (
                FmiThreeWorkerHostState.INITIALIZED,
                FmiThreeWorkerHostState.INPUT_VALUES_PENDING_STEP,
            ):
                pass
            else:
                raise RuntimeError(
                    "FMI 3 worker host SET_FLOAT64 requires Step Mode"
                )
        else:
            if self._state in (
                FmiThreeWorkerHostState.CONTINUOUS_TIME,
                FmiThreeWorkerHostState.EVENT_MODE,
            ):
                pass
            else:
                raise RuntimeError(
                    "FMI 3 worker host SET_FLOAT64 requires Model Exchange "
                    "Continuous-Time or Event Mode"
                )
        if self._float64_profile == FmiThreeWorkerFloat64Profile.SCALAR:
            if len(value_references) == len(values):
                pass
            else:
                raise ValueError(
                    "FMI 3 scalar worker references and values must align"
                )
        else:
            pass
        set_float64: FmiThreeWorkerSetFloat64Request = (
            FmiThreeWorkerSetFloat64Request(
                value_references=value_references,
                values=values,
                maximum_value_count=(
                    self._limits.maximum_float64_values_per_request
                ),
            )
        )
        validate_fmi_three_worker_float64_frame_capacity(
            request_kind=FmiThreeWorkerRequestKind.SET_FLOAT64,
            value_reference_count=len(set_float64.value_references),
            serialized_value_count=len(set_float64.values),
            maximum_frame_size=self._limits.maximum_frame_size,
            maximum_value_count=self._limits.maximum_float64_values_per_request,
        )
        request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=self._allocate_request_id(),
            kind=FmiThreeWorkerRequestKind.SET_FLOAT64,
            start=None,
            initialization=None,
            set_float64=set_float64,
        )
        self._exchange(
            request=request,
            expected_response_kind=FmiThreeWorkerResponseKind.FLOAT64_SET,
        )
        if self._interface_mode == FmuInterfaceMode.CO_SIMULATION:
            self._state = FmiThreeWorkerHostState.INPUT_VALUES_PENDING_STEP
        else:
            pass

    def get_float64(
        self,
        value_references: tuple[int, ...],
        serialized_value_count: int,
    ) -> tuple[float, ...]:
        """Read one bounded finite Float64 batch in request order.

        :param value_references: Ordered unique scalar or array references.
        :param serialized_value_count: Expected concatenated Float64 count.
        :return: Finite values corresponding positionally to the request.
        """

        if self._interface_mode == FmuInterfaceMode.CO_SIMULATION:
            if self._state in (
                FmiThreeWorkerHostState.INITIALIZED,
                FmiThreeWorkerHostState.TERMINATION_REQUESTED,
            ):
                pass
            else:
                if self._state == FmiThreeWorkerHostState.INPUT_VALUES_PENDING_STEP:
                    raise RuntimeError(
                        "FMI 3 worker host GET_FLOAT64 must precede input writes at "
                        "the current communication point"
                    )
                else:
                    raise RuntimeError(
                        "FMI 3 worker host GET_FLOAT64 requires Step Mode"
                    )
        else:
            if self._state in (
                FmiThreeWorkerHostState.CONTINUOUS_TIME,
                FmiThreeWorkerHostState.EVENT_MODE,
                FmiThreeWorkerHostState.TERMINATION_REQUESTED,
            ):
                pass
            else:
                raise RuntimeError(
                    "FMI 3 worker host GET_FLOAT64 requires Model Exchange "
                    "Continuous-Time or Event Mode"
                )
        get_float64: FmiThreeWorkerGetFloat64Request = (
            FmiThreeWorkerGetFloat64Request(
                value_references=value_references,
                serialized_value_count=serialized_value_count,
                maximum_value_count=(
                    self._limits.maximum_float64_values_per_request
                ),
            )
        )
        validate_fmi_three_worker_float64_frame_capacity(
            request_kind=FmiThreeWorkerRequestKind.GET_FLOAT64,
            value_reference_count=len(get_float64.value_references),
            serialized_value_count=get_float64.serialized_value_count,
            maximum_frame_size=self._limits.maximum_frame_size,
            maximum_value_count=self._limits.maximum_float64_values_per_request,
        )
        request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=self._allocate_request_id(),
            kind=FmiThreeWorkerRequestKind.GET_FLOAT64,
            start=None,
            initialization=None,
            get_float64=get_float64,
        )
        response: FmiThreeWorkerResponse = self._exchange(
            request=request,
            expected_response_kind=FmiThreeWorkerResponseKind.FLOAT64_VALUES,
        )
        if response.float64_values is not None:
            returned_values: tuple[float, ...] = response.float64_values.values
        else:
            self._release_after_failure(
                "FMI 3 worker GET_FLOAT64 response has no typed values",
                allow_graceful_join=False,
            )
        if len(returned_values) == serialized_value_count:
            return returned_values
        else:
            self._release_after_failure(
                "FMI 3 worker GET_FLOAT64 response cardinality is inconsistent",
                allow_graceful_join=False,
            )

    def set_int32(
        self,
        value_references: tuple[int, ...],
        values: tuple[int, ...],
    ) -> None:
        """Write one bounded scalar Int32 batch in the active interface mode.

        Co-Simulation accepts writes before the communication step. Model
        Exchange accepts discrete writes only in Event Mode, as required by
        the FMI 3 lifecycle.

        :param value_references: Ordered unique scalar Int32 references.
        :param values: Signed Int32 values aligned with the references.
        :return: None.
        """

        if self._interface_mode == FmuInterfaceMode.CO_SIMULATION:
            if self._state in (
                FmiThreeWorkerHostState.INITIALIZED,
                FmiThreeWorkerHostState.INPUT_VALUES_PENDING_STEP,
            ):
                pass
            else:
                raise RuntimeError(
                    "FMI 3 worker host SET_INT32 requires Step Mode"
                )
        else:
            if self._state == FmiThreeWorkerHostState.EVENT_MODE:
                pass
            else:
                raise RuntimeError(
                    "FMI 3 worker host SET_INT32 requires Model Exchange Event Mode"
                )
        set_int32: FmiThreeWorkerSetInt32Request = FmiThreeWorkerSetInt32Request(
            value_references=value_references,
            values=values,
            maximum_value_count=(
                self._limits.maximum_float64_values_per_request
            ),
        )
        validate_fmi_three_worker_int32_frame_capacity(
            request_kind=FmiThreeWorkerRequestKind.SET_INT32,
            value_count=len(set_int32.values),
            maximum_frame_size=self._limits.maximum_frame_size,
            maximum_value_count=(
                self._limits.maximum_float64_values_per_request
            ),
        )
        references_are_writable: bool = True
        value_reference: int
        for value_reference in set_int32.value_references:
            if value_reference in self._writable_int32_references:
                pass
            else:
                references_are_writable = False
        if references_are_writable:
            pass
        else:
            raise ValueError(
                "FMI 3 worker host SET_INT32 reference is not writable"
            )
        request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=self._allocate_request_id(),
            kind=FmiThreeWorkerRequestKind.SET_INT32,
            start=None,
            initialization=None,
            set_int32=set_int32,
        )
        self._exchange(
            request=request,
            expected_response_kind=FmiThreeWorkerResponseKind.INT32_SET,
        )
        if self._interface_mode == FmuInterfaceMode.CO_SIMULATION:
            self._state = FmiThreeWorkerHostState.INPUT_VALUES_PENDING_STEP
        else:
            pass

    def get_int32(
        self,
        value_references: tuple[int, ...],
    ) -> tuple[int, ...]:
        """Read one bounded scalar Int32 batch in request order.

        :param value_references: Ordered unique scalar Int32 references.
        :return: Signed Int32 values corresponding positionally to the request.
        """

        if self._interface_mode == FmuInterfaceMode.CO_SIMULATION:
            if self._state in (
                FmiThreeWorkerHostState.INITIALIZED,
                FmiThreeWorkerHostState.TERMINATION_REQUESTED,
            ):
                pass
            else:
                if self._state == FmiThreeWorkerHostState.INPUT_VALUES_PENDING_STEP:
                    raise RuntimeError(
                        "FMI 3 worker host GET_INT32 must precede input writes at "
                        "the current communication point"
                    )
                else:
                    raise RuntimeError(
                        "FMI 3 worker host GET_INT32 requires Step Mode"
                    )
        else:
            if self._state in (
                FmiThreeWorkerHostState.CONTINUOUS_TIME,
                FmiThreeWorkerHostState.EVENT_MODE,
                FmiThreeWorkerHostState.TERMINATION_REQUESTED,
            ):
                pass
            else:
                raise RuntimeError(
                    "FMI 3 worker host GET_INT32 requires Model Exchange "
                    "Continuous-Time or Event Mode"
                )
        get_int32: FmiThreeWorkerGetInt32Request = FmiThreeWorkerGetInt32Request(
            value_references=value_references,
            maximum_value_count=(
                self._limits.maximum_float64_values_per_request
            ),
        )
        validate_fmi_three_worker_int32_frame_capacity(
            request_kind=FmiThreeWorkerRequestKind.GET_INT32,
            value_count=len(get_int32.value_references),
            maximum_frame_size=self._limits.maximum_frame_size,
            maximum_value_count=(
                self._limits.maximum_float64_values_per_request
            ),
        )
        references_are_readable: bool = True
        value_reference: int
        for value_reference in get_int32.value_references:
            if value_reference in self._readable_int32_references:
                pass
            else:
                references_are_readable = False
        if references_are_readable:
            pass
        else:
            raise ValueError(
                "FMI 3 worker host GET_INT32 reference is not readable"
            )
        request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=self._allocate_request_id(),
            kind=FmiThreeWorkerRequestKind.GET_INT32,
            start=None,
            initialization=None,
            get_int32=get_int32,
        )
        response: FmiThreeWorkerResponse = self._exchange(
            request=request,
            expected_response_kind=FmiThreeWorkerResponseKind.INT32_VALUES,
        )
        int32_values: FmiThreeWorkerInt32Values | None = response.int32_values
        if int32_values is not None:
            returned_values: tuple[int, ...] = int32_values.values
        else:
            self._release_after_failure(
                "FMI 3 worker GET_INT32 response has no typed values",
                allow_graceful_join=False,
            )
        if len(returned_values) == len(value_references):
            return returned_values
        else:
            self._release_after_failure(
                "FMI 3 worker GET_INT32 response cardinality is inconsistent",
                allow_graceful_join=False,
            )

    def _require_model_exchange_continuous_time(
        self,
        request_kind: FmiThreeWorkerRequestKind,
    ) -> None:
        """Require the parent state that maps to native Continuous-Time Mode.

        :param request_kind: Model Exchange request requiring continuous time.
        :return: None.
        """

        if (
            self._interface_mode == FmuInterfaceMode.MODEL_EXCHANGE
            and self._state == FmiThreeWorkerHostState.CONTINUOUS_TIME
        ):
            pass
        else:
            raise RuntimeError(
                f"FMI 3 worker host {request_kind.name} requires Model Exchange "
                "Continuous-Time Mode"
            )

    def set_time(self, time_value: float) -> None:
        """Set the finite independent variable in Continuous-Time Mode.

        :param time_value: Time value presented to the Model Exchange FMU.
        :return: None.
        """

        request_kind: FmiThreeWorkerRequestKind = FmiThreeWorkerRequestKind.SET_TIME
        self._require_model_exchange_continuous_time(request_kind)
        set_time: FmiThreeWorkerSetTimeRequest = FmiThreeWorkerSetTimeRequest(
            time_value=time_value
        )
        request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=self._allocate_request_id(),
            kind=request_kind,
            start=None,
            initialization=None,
            set_time=set_time,
        )
        self._exchange(
            request=request,
            expected_response_kind=FmiThreeWorkerResponseKind.TIME_SET,
        )
        # Retain the independent variable only after the child confirms it.
        self._current_communication_time = set_time.time_value

    def set_continuous_states(self, values: tuple[float, ...]) -> None:
        """Set one bounded Model Exchange continuous-state vector.

        The child authenticates the exact runtime cardinality because FMI 3
        structural parameters can determine it during Configuration Mode.

        :param values: Ordered finite continuous-state values.
        :return: None.
        """

        request_kind: FmiThreeWorkerRequestKind = (
            FmiThreeWorkerRequestKind.SET_CONTINUOUS_STATES
        )
        self._require_model_exchange_continuous_time(request_kind)
        continuous_states: FmiThreeWorkerFloat64Values = (
            FmiThreeWorkerFloat64Values(
                values=values,
                maximum_value_count=(
                    self._limits.maximum_float64_values_per_request
                ),
            )
        )
        request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=self._allocate_request_id(),
            kind=request_kind,
            start=None,
            initialization=None,
            continuous_states=continuous_states,
        )
        self._exchange(
            request=request,
            expected_response_kind=(
                FmiThreeWorkerResponseKind.CONTINUOUS_STATES_SET
            ),
        )

    def _read_model_exchange_vector(
        self,
        request_kind: FmiThreeWorkerRequestKind,
    ) -> tuple[float, ...]:
        """Read one bounded state-sized vector from Continuous-Time Mode.

        :param request_kind: Exact Model Exchange vector read operation.
        :return: Ordered finite values authenticated and bounded by the protocol.
        """

        if request_kind == FmiThreeWorkerRequestKind.GET_CONTINUOUS_STATES:
            response_kind: FmiThreeWorkerResponseKind = (
                FmiThreeWorkerResponseKind.CONTINUOUS_STATES_VALUES
            )
        else:
            if request_kind == FmiThreeWorkerRequestKind.GET_DERIVATIVES:
                response_kind = FmiThreeWorkerResponseKind.DERIVATIVE_VALUES
            else:
                if request_kind == FmiThreeWorkerRequestKind.GET_EVENT_INDICATORS:
                    response_kind = FmiThreeWorkerResponseKind.EVENT_INDICATOR_VALUES
                else:
                    if (
                        request_kind
                        == FmiThreeWorkerRequestKind.GET_NOMINALS_OF_CONTINUOUS_STATES
                    ):
                        response_kind = (
                            FmiThreeWorkerResponseKind.CONTINUOUS_STATE_NOMINAL_VALUES
                        )
                    else:
                        raise ValueError(
                            "FMI 3 worker host vector read kind is not Model Exchange"
                        )
        vector_state_is_valid: bool = (
            self._interface_mode == FmuInterfaceMode.MODEL_EXCHANGE
            and (
                self._state == FmiThreeWorkerHostState.CONTINUOUS_TIME
                or (
                    self._state == FmiThreeWorkerHostState.EVENT_MODE
                    and request_kind
                    in (
                        FmiThreeWorkerRequestKind.GET_CONTINUOUS_STATES,
                        FmiThreeWorkerRequestKind.GET_NOMINALS_OF_CONTINUOUS_STATES,
                    )
                )
            )
        )
        if vector_state_is_valid:
            pass
        else:
            raise RuntimeError(
                f"FMI 3 worker host {request_kind.name} is invalid in the current mode"
            )
        request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=self._allocate_request_id(),
            kind=request_kind,
            start=None,
            initialization=None,
        )
        response: FmiThreeWorkerResponse = self._exchange(
            request=request,
            expected_response_kind=response_kind,
        )
        if response.float64_values is not None:
            values: tuple[float, ...] = response.float64_values.values
        else:
            self._release_after_failure(
                f"FMI 3 worker {response_kind.name} response has no typed values",
                allow_graceful_join=False,
            )
        return values

    def get_continuous_states(self) -> tuple[float, ...]:
        """Read the bounded continuous-state vector.

        :return: Ordered continuous-state values from the Model Exchange FMU.
        """

        state_values: tuple[float, ...] = self._read_model_exchange_vector(
            FmiThreeWorkerRequestKind.GET_CONTINUOUS_STATES
        )
        return state_values

    def get_derivatives(self) -> tuple[float, ...]:
        """Evaluate the bounded continuous-state derivative vector.

        :return: Ordered derivatives from the Model Exchange FMU.
        """

        derivative_values: tuple[float, ...] = self._read_model_exchange_vector(
            FmiThreeWorkerRequestKind.GET_DERIVATIVES
        )
        return derivative_values

    def get_event_indicators(self) -> tuple[float, ...]:
        """Read the bounded event-indicator vector in Continuous-Time Mode.

        :return: Ordered event indicators from the Model Exchange FMU.
        """

        event_indicator_values: tuple[float, ...] = (
            self._read_model_exchange_vector(
                FmiThreeWorkerRequestKind.GET_EVENT_INDICATORS
            )
        )
        return event_indicator_values

    def get_nominals_of_continuous_states(self) -> tuple[float, ...]:
        """Read state nominal values in Continuous-Time or Event Mode.

        :return: Ordered positive nominal values from the Model Exchange FMU.
        """

        nominal_values: tuple[float, ...] = self._read_model_exchange_vector(
            FmiThreeWorkerRequestKind.GET_NOMINALS_OF_CONTINUOUS_STATES
        )
        return nominal_values

    def evaluate_model_exchange(
        self,
        time_value: float,
        continuous_state_values: tuple[float, ...],
        writable_value_references: tuple[int, ...],
        writable_values: tuple[float, ...],
        readable_value_references: tuple[int, ...],
        readable_value_count: int,
    ) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """Evaluate one solver point with a single bounded worker exchange.

        :param time_value: Finite Model Exchange independent variable.
        :param continuous_state_values: Complete externally integrated state.
        :param writable_value_references: Optional input variable references.
        :param writable_values: Serialized values aligned with input references.
        :param readable_value_references: Optional consumer output references.
        :param readable_value_count: Serialized readable value cardinality.
        :return: Derivatives followed by readable consumer values.
        """

        request_kind: FmiThreeWorkerRequestKind = (
            FmiThreeWorkerRequestKind.EVALUATE_MODEL_EXCHANGE
        )
        self._require_model_exchange_continuous_time(request_kind)
        set_time: FmiThreeWorkerSetTimeRequest = FmiThreeWorkerSetTimeRequest(
            time_value=time_value
        )
        continuous_states: FmiThreeWorkerFloat64Values = (
            FmiThreeWorkerFloat64Values(
                values=continuous_state_values,
                maximum_value_count=(
                    self._limits.maximum_float64_values_per_request
                ),
            )
        )
        if len(writable_value_references) > 0:
            set_float64: FmiThreeWorkerSetFloat64Request | None = (
                FmiThreeWorkerSetFloat64Request(
                    value_references=writable_value_references,
                    values=writable_values,
                    maximum_value_count=(
                        self._limits.maximum_float64_values_per_request
                    ),
                )
            )
        else:
            if len(writable_values) == 0:
                set_float64 = None
            else:
                raise ValueError(
                    "FMI 3 worker empty evaluation write layout has values"
                )
        if len(readable_value_references) > 0:
            get_float64: FmiThreeWorkerGetFloat64Request | None = (
                FmiThreeWorkerGetFloat64Request(
                    value_references=readable_value_references,
                    serialized_value_count=readable_value_count,
                    maximum_value_count=(
                        self._limits.maximum_float64_values_per_request
                    ),
                )
            )
        else:
            if readable_value_count == 0:
                get_float64 = None
            else:
                raise ValueError(
                    "FMI 3 worker empty evaluation read layout has values"
                )
        validate_fmi_three_worker_model_exchange_evaluation_frame_capacity(
            continuous_state_count=len(continuous_states.values),
            writable_reference_count=len(writable_value_references),
            writable_value_count=len(writable_values),
            readable_reference_count=len(readable_value_references),
            readable_value_count=readable_value_count,
            maximum_frame_size=self._limits.maximum_frame_size,
            maximum_value_count=(
                self._limits.maximum_float64_values_per_request
            ),
        )
        evaluation: FmiThreeWorkerModelExchangeEvaluationRequest = (
            FmiThreeWorkerModelExchangeEvaluationRequest(
                set_time=set_time,
                continuous_states=continuous_states,
                set_float64=set_float64,
                get_float64=get_float64,
            )
        )
        request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=self._allocate_request_id(),
            kind=request_kind,
            start=None,
            initialization=None,
            model_exchange_evaluation=evaluation,
        )
        response: FmiThreeWorkerResponse = self._exchange(
            request=request,
            expected_response_kind=(
                FmiThreeWorkerResponseKind.MODEL_EXCHANGE_EVALUATED
            ),
        )
        evaluation_result: FmiThreeWorkerModelExchangeEvaluationResult | None = (
            response.model_exchange_evaluation_result
        )
        if evaluation_result is not None:
            derivative_values: tuple[float, ...] = (
                evaluation_result.derivatives.values
            )
            readable_values: tuple[float, ...] = (
                evaluation_result.readable_values.values
            )
        else:
            self._release_after_failure(
                "FMI 3 worker MODEL_EXCHANGE_EVALUATED response has no typed result",
                allow_graceful_join=False,
            )
        if (
            len(derivative_values) == len(continuous_state_values)
            and len(readable_values) == readable_value_count
        ):
            pass
        else:
            self._release_after_failure(
                "FMI 3 worker evaluation response cardinality is inconsistent",
                allow_graceful_join=False,
            )
        # Advance the parent clock only after the complete result is accepted.
        self._current_communication_time = set_time.time_value
        return derivative_values, readable_values

    def completed_integrator_step(
        self,
        no_set_fmu_state_prior_to_current_point: bool,
    ) -> FmiThreeWorkerCompletedIntegratorStepResult:
        """Notify the FMU that one external integrator step completed.

        :param no_set_fmu_state_prior_to_current_point: FMI rollback guarantee.
        :return: Exact event-mode and termination requests from the FMU.
        """

        request_kind: FmiThreeWorkerRequestKind = (
            FmiThreeWorkerRequestKind.COMPLETED_INTEGRATOR_STEP
        )
        self._require_model_exchange_continuous_time(request_kind)
        completed_step: FmiThreeWorkerCompletedIntegratorStepRequest = (
            FmiThreeWorkerCompletedIntegratorStepRequest(
                no_set_fmu_state_prior_to_current_point=(
                    no_set_fmu_state_prior_to_current_point
                )
            )
        )
        request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=self._allocate_request_id(),
            kind=request_kind,
            start=None,
            initialization=None,
            completed_integrator_step=completed_step,
        )
        response: FmiThreeWorkerResponse = self._exchange(
            request=request,
            expected_response_kind=(
                FmiThreeWorkerResponseKind.INTEGRATOR_STEP_COMPLETED
            ),
        )
        if response.completed_integrator_step_result is not None:
            completed_result: FmiThreeWorkerCompletedIntegratorStepResult = (
                response.completed_integrator_step_result
            )
        else:
            self._release_after_failure(
                "FMI 3 worker INTEGRATOR_STEP_COMPLETED response has no typed result",
                allow_graceful_join=False,
            )
        # Mirror the child's terminal precedence before exposing the result.
        if completed_result.terminate_simulation:
            self._state = FmiThreeWorkerHostState.TERMINATION_REQUESTED
        else:
            if completed_result.enter_event_mode:
                self._state = FmiThreeWorkerHostState.EVENT_MODE_REQUESTED
            else:
                self._state = FmiThreeWorkerHostState.CONTINUOUS_TIME
        return completed_result

    def enter_event_mode(self) -> None:
        """Enter Event Mode for any event detected by the owning importer.

        :return: None.
        """

        if (
            self._interface_mode == FmuInterfaceMode.MODEL_EXCHANGE
            and self._state in (
                FmiThreeWorkerHostState.CONTINUOUS_TIME,
                FmiThreeWorkerHostState.EVENT_MODE_REQUESTED,
            )
        ):
            pass
        else:
            raise RuntimeError(
                "FMI 3 worker host ENTER_EVENT_MODE requires Model Exchange "
                "Continuous-Time Mode or a completed-step event request"
            )
        request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=self._allocate_request_id(),
            kind=FmiThreeWorkerRequestKind.ENTER_EVENT_MODE,
            start=None,
            initialization=None,
        )
        self._exchange(
            request=request,
            expected_response_kind=FmiThreeWorkerResponseKind.EVENT_MODE_ENTERED,
        )
        self._state = FmiThreeWorkerHostState.EVENT_MODE

    def update_discrete_states(self) -> FmiThreeWorkerDiscreteStatesResult:
        """Execute one bounded native discrete-state update.

        :return: Exact six-field result without consumer interpretation.
        """

        if (
            self._interface_mode == FmuInterfaceMode.MODEL_EXCHANGE
            and self._state == FmiThreeWorkerHostState.EVENT_MODE
        ):
            pass
        else:
            raise RuntimeError(
                "FMI 3 worker host UPDATE_DISCRETE_STATES requires Event Mode"
            )
        request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=self._allocate_request_id(),
            kind=FmiThreeWorkerRequestKind.UPDATE_DISCRETE_STATES,
            start=None,
            initialization=None,
        )
        response: FmiThreeWorkerResponse = self._exchange(
            request=request,
            expected_response_kind=(
                FmiThreeWorkerResponseKind.DISCRETE_STATES_UPDATED
            ),
        )
        if response.discrete_states_result is not None:
            discrete_states_result: FmiThreeWorkerDiscreteStatesResult = (
                response.discrete_states_result
            )
        else:
            self._release_after_failure(
                "FMI 3 worker DISCRETE_STATES_UPDATED response has no typed result",
                allow_graceful_join=False,
            )
        if discrete_states_result.terminate_simulation:
            self._state = FmiThreeWorkerHostState.TERMINATION_REQUESTED
        else:
            self._state = FmiThreeWorkerHostState.EVENT_MODE
        return discrete_states_result

    def enter_continuous_time_mode(self) -> None:
        """Leave FMI 3 Model Exchange Event Mode after convergence.

        :return: None.
        """

        if (
            self._interface_mode == FmuInterfaceMode.MODEL_EXCHANGE
            and self._state == FmiThreeWorkerHostState.EVENT_MODE
        ):
            pass
        else:
            raise RuntimeError(
                "FMI 3 worker host ENTER_CONTINUOUS_TIME_MODE requires Event Mode"
            )
        request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=self._allocate_request_id(),
            kind=FmiThreeWorkerRequestKind.ENTER_CONTINUOUS_TIME_MODE,
            start=None,
            initialization=None,
        )
        self._exchange(
            request=request,
            expected_response_kind=(
                FmiThreeWorkerResponseKind.CONTINUOUS_TIME_MODE_ENTERED
            ),
        )
        self._state = FmiThreeWorkerHostState.CONTINUOUS_TIME

    def _build_validated_do_step_request(
        self,
        current_communication_point: float,
        communication_step_size: float,
        no_set_fmu_state_prior_to_current_point: bool,
    ) -> FmiThreeWorkerDoStepRequest:
        """Validate one step before a caller may change native writable values.

        :param current_communication_point: Importer communication time.
        :param communication_step_size: Positive requested step size.
        :param no_set_fmu_state_prior_to_current_point: FMI rollback guarantee.
        :return: Immutable request body approved for the current host clock.
        """

        if self._interface_mode == FmuInterfaceMode.CO_SIMULATION:
            pass
        else:
            raise RuntimeError(
                "FMI 3 worker host DO_STEP requires Co-Simulation"
            )
        if self._state in (
            FmiThreeWorkerHostState.INITIALIZED,
            FmiThreeWorkerHostState.INPUT_VALUES_PENDING_STEP,
        ):
            pass
        else:
            raise RuntimeError("FMI 3 worker host DO_STEP requires Step Mode")
        do_step: FmiThreeWorkerDoStepRequest = FmiThreeWorkerDoStepRequest(
            current_communication_point=current_communication_point,
            communication_step_size=communication_step_size,
            no_set_fmu_state_prior_to_current_point=(
                no_set_fmu_state_prior_to_current_point
            ),
        )
        if do_step.current_communication_point == self._current_communication_time:
            pass
        else:
            raise RuntimeError(
                "FMI 3 worker host DO_STEP communication point is not continuous"
            )
        can_handle_variable_step_size: bool | None = (
            self._can_handle_variable_communication_step_size
        )
        if can_handle_variable_step_size is not None:
            pass
        else:
            raise RuntimeError(
                "FMI 3 worker host communication-step capability is unavailable"
            )
        if (
            can_handle_variable_step_size
            or self._communication_step_size is None
            or do_step.communication_step_size == self._communication_step_size
        ):
            pass
        else:
            raise RuntimeError(
                "FMI 3 worker host requires a constant communication step size"
            )
        return do_step

    def _execute_validated_do_step_request(
        self,
        do_step: FmiThreeWorkerDoStepRequest,
    ) -> FmiThreeWorkerDoStepResult:
        """Execute one request already approved against parent-owned state.

        :param do_step: Side-effect-free request produced by the host preflight.
        :return: Exact successful ``fmi3DoStep`` result.
        """

        request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=self._allocate_request_id(),
            kind=FmiThreeWorkerRequestKind.DO_STEP,
            start=None,
            initialization=None,
            do_step=do_step,
        )
        response: FmiThreeWorkerResponse = self._exchange(
            request=request,
            expected_response_kind=FmiThreeWorkerResponseKind.STEP_COMPLETED,
        )
        if response.do_step_result is not None:
            do_step_result: FmiThreeWorkerDoStepResult = response.do_step_result
        else:
            self._release_after_failure(
                "FMI 3 worker STEP_COMPLETED response has no typed result",
                allow_graceful_join=False,
            )
        try:
            # Revalidate the child result before advancing parent-owned time.
            validate_fmi_three_worker_completed_step(
                request=do_step,
                result=do_step_result,
                early_return_allowed=self._early_return_allowed,
                might_return_early_from_do_step=bool(
                    self._might_return_early_from_do_step
                ),
            )
        except ValueError as error:
            self._release_after_failure(
                f"FMI 3 worker STEP_COMPLETED result is invalid: {error}",
                allow_graceful_join=False,
            )
        self._current_communication_time = do_step_result.last_successful_time
        if self._communication_step_size is None:
            self._communication_step_size = do_step.communication_step_size
        else:
            pass
        if do_step_result.terminate_simulation:
            self._state = FmiThreeWorkerHostState.TERMINATION_REQUESTED
        else:
            self._state = FmiThreeWorkerHostState.INITIALIZED
        return do_step_result

    def set_numeric_values_and_do_step(
        self,
        float64_value_references: tuple[int, ...],
        float64_values: tuple[float, ...],
        current_communication_point: float,
        communication_step_size: float,
        no_set_fmu_state_prior_to_current_point: bool,
        int32_value_references: tuple[int, ...] = tuple(),
        int32_values: tuple[int, ...] = tuple(),
    ) -> FmiThreeWorkerDoStepResult:
        """Validate mixed inputs and execute one ordered Co-Simulation step.

        All step, value, frame, and ACL checks complete before the first native
        write. Native calls then use the fixed Float64, Int32, ``doStep`` order.
        A later transport or native failure remains terminal under the worker's
        existing fail-stop policy.

        :param float64_value_references: Ordered Float64 references to write.
        :param float64_values: Concatenated finite Float64 values.
        :param int32_value_references: Ordered scalar Int32 references to write.
        :param int32_values: Signed Int32 values aligned with their references.
        :param current_communication_point: Importer communication time.
        :param communication_step_size: Positive requested step size.
        :param no_set_fmu_state_prior_to_current_point: FMI rollback guarantee.
        :return: Exact successful ``fmi3DoStep`` result.
        """

        do_step: FmiThreeWorkerDoStepRequest = (
            self._build_validated_do_step_request(
                current_communication_point=current_communication_point,
                communication_step_size=communication_step_size,
                no_set_fmu_state_prior_to_current_point=(
                    no_set_fmu_state_prior_to_current_point
                ),
            )
        )
        if len(float64_value_references) > 0:
            validated_float64_write: FmiThreeWorkerSetFloat64Request | None = (
                FmiThreeWorkerSetFloat64Request(
                    value_references=float64_value_references,
                    values=float64_values,
                    maximum_value_count=(
                        self._limits.maximum_float64_values_per_request
                    ),
                )
            )
            validate_fmi_three_worker_float64_frame_capacity(
                request_kind=FmiThreeWorkerRequestKind.SET_FLOAT64,
                value_reference_count=len(
                    validated_float64_write.value_references
                ),
                serialized_value_count=len(validated_float64_write.values),
                maximum_frame_size=self._limits.maximum_frame_size,
                maximum_value_count=(
                    self._limits.maximum_float64_values_per_request
                ),
            )
        else:
            if len(float64_values) == 0:
                validated_float64_write = None
            else:
                raise ValueError(
                    "FMI 3 worker empty Float64 reference batch cannot contain values"
                )
        if len(int32_value_references) > 0:
            validated_int32_write: FmiThreeWorkerSetInt32Request | None = (
                FmiThreeWorkerSetInt32Request(
                    value_references=int32_value_references,
                    values=int32_values,
                    maximum_value_count=(
                        self._limits.maximum_float64_values_per_request
                    ),
                )
            )
            validate_fmi_three_worker_int32_frame_capacity(
                request_kind=FmiThreeWorkerRequestKind.SET_INT32,
                value_count=len(validated_int32_write.values),
                maximum_frame_size=self._limits.maximum_frame_size,
                maximum_value_count=(
                    self._limits.maximum_float64_values_per_request
                ),
            )
            int32_references_are_writable: bool = True
            int32_value_reference: int
            for int32_value_reference in validated_int32_write.value_references:
                if int32_value_reference in self._writable_int32_references:
                    pass
                else:
                    int32_references_are_writable = False
            if int32_references_are_writable:
                pass
            else:
                raise ValueError(
                    "FMI 3 worker host SET_INT32 reference is not writable"
                )
        else:
            if len(int32_values) == 0:
                validated_int32_write = None
            else:
                raise ValueError(
                    "FMI 3 worker empty Int32 reference batch cannot contain values"
                )
        if validated_float64_write is not None:
            self.set_float64(
                value_references=validated_float64_write.value_references,
                values=validated_float64_write.values,
            )
        else:
            pass
        if validated_int32_write is not None:
            self.set_int32(
                value_references=validated_int32_write.value_references,
                values=validated_int32_write.values,
            )
        else:
            pass
        return self._execute_validated_do_step_request(do_step)

    def do_step(
        self,
        current_communication_point: float,
        communication_step_size: float,
        no_set_fmu_state_prior_to_current_point: bool,
    ) -> FmiThreeWorkerDoStepResult:
        """Advance one Co-Simulation step and return the FMU-reported outcome.

        :param current_communication_point: Importer communication time.
        :param communication_step_size: Positive requested step size.
        :param no_set_fmu_state_prior_to_current_point: FMI rollback guarantee.
        :return: Exact successful ``fmi3DoStep`` result.
        """

        do_step: FmiThreeWorkerDoStepRequest = (
            self._build_validated_do_step_request(
                current_communication_point=current_communication_point,
                communication_step_size=communication_step_size,
                no_set_fmu_state_prior_to_current_point=(
                    no_set_fmu_state_prior_to_current_point
                ),
            )
        )
        return self._execute_validated_do_step_request(do_step)

    def save_checkpoint(self) -> None:
        """Replace the worker's sole checkpoint at one accepted stable point.

        :return: None.
        """

        if (
            self._can_get_and_set_fmu_state
            and self._state in (
                FmiThreeWorkerHostState.INITIALIZED,
                FmiThreeWorkerHostState.CONTINUOUS_TIME,
            )
        ):
            saved_host_state: FmiThreeWorkerHostState = self._state
        else:
            raise RuntimeError(
                "FMI 3 worker host SAVE_CHECKPOINT requires supported Step or Continuous-Time Mode"
            )
        request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=self._allocate_request_id(),
            kind=FmiThreeWorkerRequestKind.SAVE_CHECKPOINT,
            start=None,
            initialization=None,
        )
        self._exchange(
            request=request,
            expected_response_kind=FmiThreeWorkerResponseKind.CHECKPOINT_SAVED,
        )
        self._checkpoint_host_state = saved_host_state
        self._checkpoint_communication_time = self._current_communication_time
        self._checkpoint_communication_step_size = self._communication_step_size

    def restore_checkpoint(self) -> None:
        """Restore the worker's sole checkpoint without consuming it.

        :return: None.
        """

        saved_host_state: FmiThreeWorkerHostState | None = (
            self._checkpoint_host_state
        )
        co_simulation_restore_is_valid: bool = (
            saved_host_state == FmiThreeWorkerHostState.INITIALIZED
            and self._state
            in (
                FmiThreeWorkerHostState.INITIALIZED,
                FmiThreeWorkerHostState.INPUT_VALUES_PENDING_STEP,
                FmiThreeWorkerHostState.TERMINATION_REQUESTED,
            )
        )
        model_exchange_restore_is_valid: bool = (
            saved_host_state == FmiThreeWorkerHostState.CONTINUOUS_TIME
            and self._state
            in (
                FmiThreeWorkerHostState.CONTINUOUS_TIME,
                FmiThreeWorkerHostState.EVENT_MODE_REQUESTED,
                FmiThreeWorkerHostState.EVENT_MODE,
                FmiThreeWorkerHostState.TERMINATION_REQUESTED,
            )
        )
        if (
            self._can_get_and_set_fmu_state
            and saved_host_state is not None
            and (co_simulation_restore_is_valid or model_exchange_restore_is_valid)
        ):
            pass
        else:
            raise RuntimeError(
                "FMI 3 worker host RESTORE_CHECKPOINT requires a compatible saved state"
            )
        request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=self._allocate_request_id(),
            kind=FmiThreeWorkerRequestKind.RESTORE_CHECKPOINT,
            start=None,
            initialization=None,
        )
        self._exchange(
            request=request,
            expected_response_kind=FmiThreeWorkerResponseKind.CHECKPOINT_RESTORED,
        )
        self._state = saved_host_state
        self._current_communication_time = self._checkpoint_communication_time
        self._communication_step_size = self._checkpoint_communication_step_size

    def discard_checkpoint(self) -> None:
        """Free the worker's sole checkpoint without changing live state.

        :return: None.
        """

        if self._can_get_and_set_fmu_state and self._checkpoint_host_state is not None:
            pass
        else:
            raise RuntimeError(
                "FMI 3 worker host DISCARD_CHECKPOINT requires a saved state"
            )
        request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
            request_id=self._allocate_request_id(),
            kind=FmiThreeWorkerRequestKind.DISCARD_CHECKPOINT,
            start=None,
            initialization=None,
        )
        self._exchange(
            request=request,
            expected_response_kind=FmiThreeWorkerResponseKind.CHECKPOINT_DISCARDED,
        )
        self._checkpoint_host_state = None
        self._checkpoint_communication_time = None
        self._checkpoint_communication_step_size = None

    def close(self) -> None:
        """Close the worker and staging idempotently with bounded escalation.

        :return: None.
        """

        if self._state == FmiThreeWorkerHostState.CLOSED:
            pass
        else:
            if self._state == FmiThreeWorkerHostState.CREATED:
                self._staging_area.close()
                self._state = FmiThreeWorkerHostState.CLOSED
            else:
                if self._state in (
                    FmiThreeWorkerHostState.READY,
                    FmiThreeWorkerHostState.INITIALIZED,
                    FmiThreeWorkerHostState.INPUT_VALUES_PENDING_STEP,
                    FmiThreeWorkerHostState.TERMINATION_REQUESTED,
                    FmiThreeWorkerHostState.EVENT_MODE_REQUESTED,
                    FmiThreeWorkerHostState.CONTINUOUS_TIME,
                    FmiThreeWorkerHostState.EVENT_MODE,
                ):
                    self._state = FmiThreeWorkerHostState.STOPPING
                    request: FmiThreeWorkerRequest = FmiThreeWorkerRequest(
                        request_id=self._allocate_request_id(),
                        kind=FmiThreeWorkerRequestKind.CLOSE,
                        start=None,
                        initialization=None,
                    )
                    self._exchange(
                        request=request,
                        expected_response_kind=FmiThreeWorkerResponseKind.CLOSED,
                    )
                    process_stopped: bool = self._stop_worker_process(
                        allow_graceful_join=True
                    )
                    if process_stopped:
                        self._staging_area.close()
                        self._checkpoint_host_state = None
                        self._checkpoint_communication_time = None
                        self._checkpoint_communication_step_size = None
                        self._state = FmiThreeWorkerHostState.CLOSED
                    else:
                        self._state = FmiThreeWorkerHostState.FAILED
                        raise RuntimeError(
                            "FMI 3 worker staging retained because child death is unproven"
                        )
                else:
                    if self._state == FmiThreeWorkerHostState.FAILED:
                        if self._spawn_outcome_unknown:
                            raise RuntimeError(
                                "FMI 3 worker staging remains retained because "
                                "the START spawn outcome is unknown"
                            )
                        else:
                            failed_process_stopped: bool = self._stop_worker_process(
                                allow_graceful_join=False
                            )
                            if failed_process_stopped:
                                self._staging_area.close()
                                self._state = FmiThreeWorkerHostState.CLOSED
                            else:
                                raise RuntimeError(
                                    "FMI 3 worker staging remains retained after cleanup retry"
                                )
                    else:
                        raise RuntimeError(
                            "FMI 3 worker host cannot close during an active transition"
                        )


def prepare_fmi_three_worker_host(
    metadata: FmuModelDescription,
    interface_mode: FmuInterfaceMode,
    staging_parent: str | Path | None,
    limits: FmiThreeWorkerHostLimits,
    float64_profile: FmiThreeWorkerFloat64Profile,
    early_return_allowed: bool = False,
) -> FmiThreeWorkerHost:
    """Validate and stage one FMI 3 interface for later explicit START.

    Preparation does not spawn a process or load native code. The returned host
    owns the staging area immediately, preserving its lifetime across any later
    START failure.

    :param metadata: Authoritative metadata and source inspection receipt.
    :param interface_mode: Model Exchange or Co-Simulation interface to own.
    :param staging_parent: Optional parent for the private staging child.
    :param limits: Explicit finite transport and shutdown limits.
    :param float64_profile: Scalar or constant-array access profile.
    :param early_return_allowed: Whether the importing session can consume a
        partial Co-Simulation step.
    :return: Prepared worker host in CREATED state.
    """

    if interface_mode == FmuInterfaceMode.CO_SIMULATION:
        validate_fmi_three_co_simulation_worker_profile(
            metadata=metadata,
            preferred_mode=interface_mode,
            float64_profile=float64_profile,
        )
        if metadata.fmi_three_co_simulation_capabilities is not None:
            capabilities: FmiThreeCoSimulationCapabilities = (
                metadata.fmi_three_co_simulation_capabilities
            )
            can_handle_variable_communication_step_size: bool | None = (
                capabilities.can_handle_variable_communication_step_size
            )
            might_return_early_from_do_step: bool | None = (
                capabilities.might_return_early_from_do_step
            )
            can_get_and_set_fmu_state: bool = (
                capabilities.can_get_and_set_fmu_state
            )
            can_serialize_fmu_state: bool = capabilities.can_serialize_fmu_state
            needs_completed_integrator_step: bool | None = None
        else:
            raise RuntimeError("FMI 3 Co-Simulation capabilities are unavailable")
    else:
        if interface_mode == FmuInterfaceMode.MODEL_EXCHANGE:
            if early_return_allowed:
                raise RuntimeError(
                    "FMI 3 Model Exchange cannot enable Co-Simulation early return"
                )
            else:
                pass
            validate_fmi_three_model_exchange_worker_profile(
                metadata=metadata,
                preferred_mode=interface_mode,
                float64_profile=float64_profile,
            )
            can_handle_variable_communication_step_size = None
            might_return_early_from_do_step = None
            if metadata.fmi_three_model_exchange_capabilities is not None:
                model_exchange_capabilities: FmiThreeModelExchangeCapabilities = (
                    metadata.fmi_three_model_exchange_capabilities
                )
                can_get_and_set_fmu_state = (
                    model_exchange_capabilities.can_get_and_set_fmu_state
                )
                can_serialize_fmu_state = (
                    model_exchange_capabilities.can_serialize_fmu_state
                )
                needs_completed_integrator_step = (
                    model_exchange_capabilities.needs_completed_integrator_step
                )
            else:
                raise RuntimeError(
                    "FMI 3 Model Exchange capabilities are unavailable"
                )
        else:
            raise ValueError("FMI 3 worker host interface mode is invalid")
    if metadata.inspection_receipt is not None:
        pass
    else:
        raise ValueError("FMI 3 worker metadata has no inspection receipt")
    if metadata.instantiation_token is not None:
        instantiation_token: str = metadata.instantiation_token
    else:
        raise ValueError("FMI 3 worker metadata has no instantiation token")
    model_identifier: str = metadata.get_model_identifier(
        interface_mode
    )
    initialization_writable_references: frozenset[int] = (
        resolve_fmi_three_initialization_writable_references(metadata)
    )
    initialization_float64_count: int = 0
    readable_int32_count: int = 0
    writable_int32_count: int = 0
    initialization_int32_count: int = 0
    declared_variable: FmuVariableDescription
    for declared_variable in metadata.variables:
        variable_is_scalar_int32: bool = (
            declared_variable.variable_type == FmuVariableType.INT32
            and len(declared_variable.dimensions) == 0
        )
        if (
            declared_variable.variable_type == FmuVariableType.FLOAT64
            and declared_variable.value_reference
            in initialization_writable_references
        ):
            initialization_float64_count += 1
        else:
            pass
        if variable_is_scalar_int32:
            readable_int32_count += 1
            if is_fmi_three_input_or_tunable_parameter(declared_variable):
                writable_int32_count += 1
            else:
                pass
            if is_fmi_three_initialization_mode_writable(declared_variable):
                initialization_int32_count += 1
            else:
                pass
        else:
            pass
    initialization_float64_references: list[int] = [0] * (
        initialization_float64_count
    )
    readable_int32_reference_values: list[int] = [0] * readable_int32_count
    writable_int32_reference_values: list[int] = [0] * writable_int32_count
    initialization_int32_reference_values: list[int] = [0] * (
        initialization_int32_count
    )
    initialization_float64_index: int = 0
    readable_int32_index: int = 0
    writable_int32_index: int = 0
    initialization_int32_index: int = 0
    for declared_variable in metadata.variables:
        variable_is_scalar_int32 = (
            declared_variable.variable_type == FmuVariableType.INT32
            and len(declared_variable.dimensions) == 0
        )
        if (
            declared_variable.variable_type == FmuVariableType.FLOAT64
            and declared_variable.value_reference
            in initialization_writable_references
        ):
            initialization_float64_references[initialization_float64_index] = (
                declared_variable.value_reference
            )
            initialization_float64_index += 1
        else:
            pass
        if variable_is_scalar_int32:
            readable_int32_reference_values[readable_int32_index] = (
                declared_variable.value_reference
            )
            readable_int32_index += 1
            if is_fmi_three_input_or_tunable_parameter(declared_variable):
                writable_int32_reference_values[writable_int32_index] = (
                    declared_variable.value_reference
                )
                writable_int32_index += 1
            else:
                pass
            if is_fmi_three_initialization_mode_writable(declared_variable):
                initialization_int32_reference_values[
                    initialization_int32_index
                ] = declared_variable.value_reference
                initialization_int32_index += 1
            else:
                pass
        else:
            pass
    initialization_writable_value_references: frozenset[int] = frozenset(
        initialization_float64_references
    )
    readable_int32_references: frozenset[int] = frozenset(
        readable_int32_reference_values
    )
    writable_int32_references: frozenset[int] = frozenset(
        writable_int32_reference_values
    )
    initialization_writable_int32_references: frozenset[int] = frozenset(
        initialization_int32_reference_values
    )
    configuration_float64_writable_references: frozenset[int] = (
        resolve_fmi_three_configuration_float64_writable_references(metadata)
    )
    configuration_uint64_writable_references: frozenset[int] = (
        resolve_fmi_three_configuration_uint64_writable_references(metadata)
    )
    validate_fmi_three_native_binary(
        receipt=metadata.inspection_receipt,
        model_identifier=model_identifier,
    )
    staging_area: FmuStagingArea = stage_fmu_source(
        path=metadata.path,
        expected_receipt=metadata.inspection_receipt,
        staging_parent=staging_parent,
    )
    try:
        worker_host: FmiThreeWorkerHost = (
            FmiThreeWorkerHost(
                staging_area=staging_area,
                instantiation_token=instantiation_token,
                model_identifier=model_identifier,
                interface_mode=interface_mode,
                float64_profile=float64_profile,
                can_get_and_set_fmu_state=can_get_and_set_fmu_state,
                can_serialize_fmu_state=can_serialize_fmu_state,
                needs_completed_integrator_step=needs_completed_integrator_step,
                can_handle_variable_communication_step_size=(
                    can_handle_variable_communication_step_size
                ),
                might_return_early_from_do_step=(
                    might_return_early_from_do_step
                ),
                early_return_allowed=early_return_allowed,
                configuration_float64_writable_references=(
                    configuration_float64_writable_references
                ),
                configuration_uint64_writable_references=(
                    configuration_uint64_writable_references
                ),
                initialization_writable_value_references=(
                    initialization_writable_value_references
                ),
                readable_int32_references=readable_int32_references,
                writable_int32_references=writable_int32_references,
                initialization_writable_int32_references=(
                    initialization_writable_int32_references
                ),
                limits=limits,
            )
        )
    except BaseException:
        # Ownership has not transferred when construction fails. Do not hide a
        # cleanup failure because it means the staging outcome is uncertain.
        staging_area.close()
        raise
    return worker_host
