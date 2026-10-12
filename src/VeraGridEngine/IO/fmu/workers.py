# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Isolated numeric lifecycle for FMI 3 Co-Simulation and Model Exchange."""

from __future__ import annotations

from ctypes import Array, c_double
from enum import Enum
from multiprocessing.connection import Connection

import fmpy
from fmpy.fmi3 import FMU3Model, FMU3Slave, fmi3FMUState
from fmpy.model_description import ModelDescription

from VeraGridEngine.IO.fmu.Elements.bindings import (
    FmiThreeFloat64VariableCardinalityPlan,
    resolve_fmi_three_float64_variable_cardinality_plan,
)
from VeraGridEngine.IO.fmu.Elements.inspection import FmuInspectionResult, inspect_fmu
from VeraGridEngine.IO.fmu.model_description import (
    FmuModelDescription,
    read_fmu_model_description,
)
from VeraGridEngine.IO.fmu.Elements.description import (
    FmiThreeCoSimulationCapabilities,
    FmiThreeModelExchangeCapabilities,
    FmuVariableDescription,
)
from VeraGridEngine.IO.fmu.native_binary import (
    resolve_fmi_three_host_binary,
    validate_fmi_three_native_binary,
)
from VeraGridEngine.IO.fmu.profile import (
    is_fmi_three_configuration_mode_writable,
    is_fmi_three_input_or_tunable_parameter,
    is_fmi_three_initialization_mode_writable,
    validate_fmi_three_co_simulation_worker_profile,
    validate_fmi_three_model_exchange_worker_profile,
)
from VeraGridEngine.IO.fmu.Elements.protocol import (
    FmiThreeWorkerCompletedIntegratorStepRequest,
    FmiThreeWorkerCompletedIntegratorStepResult,
    FmiThreeWorkerConfigureFloat64Request,
    FmiThreeWorkerConfigureUInt64Request,
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
    FmiThreeWorkerDoStepRequest,
    FmiThreeWorkerDoStepResult,
    FmiThreeWorkerDiscreteStatesResult,
    FmiThreeWorkerSetFloat64Request,
    FmiThreeWorkerSetInt32Request,
    FmiThreeWorkerSetTimeRequest,
    FmiThreeWorkerStartRequest,
    decode_fmi_three_worker_request,
    encode_fmi_three_worker_response,
    receive_fmi_three_worker_frame,
    send_fmi_three_worker_frame,
    validate_fmi_three_worker_completed_step,
    validate_fmi_three_worker_float64_value_limit,
    validate_fmi_three_worker_staging_identity,
)
from VeraGridEngine.enumerations import (
    FmiVersion,
    FmuInterfaceMode,
    FmuVariableType,
)


class _FmiThreeWorkerState(Enum):
    """Represent the bounded native lifecycle owned by one worker."""

    EXPECTING_START = 1
    READY = 2
    CONFIGURATION_ENTERED = 3
    INITIALIZATION_ENTERED = 4
    INITIALIZED = 5
    INPUT_VALUES_PENDING_STEP = 6
    TERMINATION_REQUESTED = 7
    CONTINUOUS_TIME = 8
    EVENT_MODE_REQUESTED = 9
    EVENT_MODE = 10
    NATIVE_FAILED = 11
    CLOSED = 12


def _resolve_fmi_three_worker_access_controls(
    metadata: FmuModelDescription,
    maximum_serialized_value_count: int,
) -> tuple[
    dict[int, int],
    dict[int, int],
    dict[int, int],
    dict[int, int],
    frozenset[int],
    frozenset[int],
    frozenset[int],
    frozenset[int],
    dict[int, FmiThreeFloat64VariableCardinalityPlan],
]:
    """Derive minimal Float64, Int32, and structural UInt64 ACLs.

    The worker retains integer reference-to-count lookups and minimal dimension
    plans after START. It does not keep a second metadata graph or resolve names
    during native calls.

    :param metadata: Freshly parsed authoritative FMI 3 metadata.
    :param maximum_serialized_value_count: Maximum values in one native call.
    :return: Float64 readable, Step Mode, Initialization Mode, and Configuration
        Mode ACLs; scalar UInt64 Configuration Mode ACL; scalar Int32 readable,
        Step Mode, and Initialization Mode ACLs; and Float64 cardinality plans.
    """

    readable_value_counts: dict[int, int] = dict()
    writable_value_counts: dict[int, int] = dict()
    initialization_writable_value_counts: dict[int, int] = dict()
    configuration_writable_value_counts: dict[int, int] = dict()
    configuration_uint64_writable_references: set[int] = set()
    readable_int32_references: set[int] = set()
    writable_int32_references: set[int] = set()
    initialization_writable_int32_references: set[int] = set()
    variable_cardinality_plans: dict[
        int, FmiThreeFloat64VariableCardinalityPlan
    ] = dict()
    variables_by_reference: dict[int, FmuVariableDescription] = dict()
    indexed_variable: FmuVariableDescription
    for indexed_variable in metadata.variables:
        variables_by_reference[indexed_variable.value_reference] = indexed_variable
    declared_variable: FmuVariableDescription
    for declared_variable in metadata.variables:
        if declared_variable.variable_type == FmuVariableType.FLOAT64:
            value_reference: int = declared_variable.value_reference
            cardinality_plan: FmiThreeFloat64VariableCardinalityPlan = (
                resolve_fmi_three_float64_variable_cardinality_plan(
                    variable=declared_variable,
                    variables_by_reference=variables_by_reference,
                    maximum_serialized_value_count=(
                        maximum_serialized_value_count
                    ),
                )
            )
            serialized_value_count: int = (
                cardinality_plan.resolve_serialized_value_count(
                    maximum_serialized_value_count
                )
            )
            variable_cardinality_plans[value_reference] = cardinality_plan
            existing_readable_count: int | None = readable_value_counts.get(
                value_reference,
                None,
            )
            if existing_readable_count is None:
                readable_value_counts[value_reference] = serialized_value_count
            else:
                if existing_readable_count == serialized_value_count:
                    pass
                else:
                    raise ValueError(
                        "FMI 3 aliases have inconsistent serialized cardinalities"
                    )
            if is_fmi_three_input_or_tunable_parameter(declared_variable):
                writable_value_counts[value_reference] = serialized_value_count
            else:
                pass
            if is_fmi_three_initialization_mode_writable(declared_variable):
                initialization_writable_value_counts[value_reference] = (
                    serialized_value_count
                )
            else:
                pass
            if is_fmi_three_configuration_mode_writable(declared_variable):
                configuration_writable_value_counts[value_reference] = (
                    serialized_value_count
                )
            else:
                pass
        else:
            if (
                declared_variable.variable_type == FmuVariableType.UINT64
                and is_fmi_three_configuration_mode_writable(declared_variable)
                and len(declared_variable.dimensions) == 0
            ):
                configuration_uint64_writable_references.add(
                    declared_variable.value_reference
                )
            else:
                if declared_variable.variable_type == FmuVariableType.INT32:
                    int32_value_reference: int = declared_variable.value_reference
                    readable_int32_references.add(int32_value_reference)
                    if is_fmi_three_input_or_tunable_parameter(declared_variable):
                        writable_int32_references.add(int32_value_reference)
                    else:
                        pass
                    if is_fmi_three_initialization_mode_writable(declared_variable):
                        initialization_writable_int32_references.add(
                            int32_value_reference
                        )
                    else:
                        pass
                else:
                    pass
    return (
        readable_value_counts,
        writable_value_counts,
        initialization_writable_value_counts,
        configuration_writable_value_counts,
        frozenset(configuration_uint64_writable_references),
        frozenset(readable_int32_references),
        frozenset(writable_int32_references),
        frozenset(initialization_writable_int32_references),
        variable_cardinality_plans,
    )


def _serialized_value_count_matches_access(
    requested_references: tuple[int, ...],
    serialized_value_count: int,
    allowed_value_counts: dict[int, int],
) -> bool:
    """Check requested references and their exact concatenated cardinality.

    :param requested_references: Ordered references requested by the parent.
    :param serialized_value_count: Concatenated value count declared by the request.
    :param allowed_value_counts: Metadata-derived reference-to-count ACL.
    :return: ``True`` only when access and total cardinality both match.
    """

    expected_value_count: int = 0
    references_are_allowed: bool = True
    requested_reference: int
    for requested_reference in requested_references:
        allowed_value_count: int | None = allowed_value_counts.get(
            requested_reference,
            None,
        )
        if allowed_value_count is not None:
            expected_value_count += allowed_value_count
        else:
            references_are_allowed = False
    return references_are_allowed and expected_value_count == serialized_value_count


def _construct_fmi_three_runtime(
    start: FmiThreeWorkerStartRequest,
) -> FMU3Slave | FMU3Model:
    """Load and instantiate the selected FMI 3 runtime interface.

    A constructor failure is terminal for the isolated process because FMPy did
    not return a valid owner. Once construction succeeds, later ABI or instance
    failures release the valid library owner explicitly.

    :param start: Validated start identity and native instance options.
    :return: Instantiated FMI 3 Co-Simulation or Model Exchange runtime.
    """

    if start.interface_mode == FmuInterfaceMode.CO_SIMULATION:
        runtime: FMU3Slave | FMU3Model = FMU3Slave(
            guid=start.instantiation_token,
            modelIdentifier=start.model_identifier,
            unzipDirectory=str(start.extracted_fmu_directory),
            instanceName=start.instance_name,
        )
    else:
        if start.interface_mode == FmuInterfaceMode.MODEL_EXCHANGE:
            runtime = FMU3Model(
                guid=start.instantiation_token,
                modelIdentifier=start.model_identifier,
                unzipDirectory=str(start.extracted_fmu_directory),
                instanceName=start.instance_name,
            )
        else:
            raise RuntimeError("Unsupported FMI 3 worker interface mode")
    try:
        if runtime.fmi3GetVersion() == b"3.0":
            pass
        else:
            raise RuntimeError("The native library did not report FMI version 3.0")
        if start.interface_mode == FmuInterfaceMode.CO_SIMULATION:
            runtime.instantiate(
                visible=start.visible,
                loggingOn=start.debug_logging,
                eventModeUsed=False,
                earlyReturnAllowed=start.early_return_allowed,
                requiredIntermediateVariables=list(),
            )
        else:
            runtime.instantiate(
                visible=start.visible,
                loggingOn=start.debug_logging,
            )
    except Exception:
        try:
            runtime.freeLibrary()
        except OSError:
            pass
        raise
    return runtime


class _FmiThreeWorkerSession:
    """Own one fail-stop FMI 3 numeric lifecycle inside the child process."""

    __slots__ = (
        "state",
        "runtime",
        "readable_value_counts",
        "writable_value_counts",
        "initialization_writable_value_counts",
        "configuration_writable_value_counts",
        "configuration_uint64_writable_references",
        "readable_int32_references",
        "writable_int32_references",
        "initialization_writable_int32_references",
        "variable_cardinality_plans",
        "interface_mode",
        "continuous_state_count",
        "event_indicator_count",
        "current_communication_time",
        "can_get_and_set_fmu_state",
        "can_serialize_fmu_state",
        "can_handle_variable_communication_step_size",
        "might_return_early_from_do_step",
        "early_return_allowed",
        "communication_step_size",
        "checkpoint_state",
        "checkpoint_worker_state",
        "checkpoint_communication_time",
        "checkpoint_communication_step_size",
        "maximum_float64_values_per_request",
    )

    def __init__(self, maximum_float64_values_per_request: int) -> None:
        """Create a worker that has not loaded native code yet.

        :param maximum_float64_values_per_request: Maximum serialized-value count.
        :return: None.
        """

        validate_fmi_three_worker_float64_value_limit(
            maximum_float64_values_per_request
        )
        self.state: _FmiThreeWorkerState = (
            _FmiThreeWorkerState.EXPECTING_START
        )
        self.runtime: FMU3Slave | FMU3Model | None = None
        self.readable_value_counts: dict[int, int] = dict()
        self.writable_value_counts: dict[int, int] = dict()
        self.initialization_writable_value_counts: dict[int, int] = dict()
        self.configuration_writable_value_counts: dict[int, int] = dict()
        self.configuration_uint64_writable_references: frozenset[int] = (
            frozenset()
        )
        self.readable_int32_references: frozenset[int] = frozenset()
        self.writable_int32_references: frozenset[int] = frozenset()
        self.initialization_writable_int32_references: frozenset[int] = (
            frozenset()
        )
        self.variable_cardinality_plans: dict[
            int, FmiThreeFloat64VariableCardinalityPlan
        ] = dict()
        self.interface_mode: FmuInterfaceMode | None = None
        self.continuous_state_count: int | None = None
        self.event_indicator_count: int | None = None
        self.current_communication_time: float | None = None
        self.can_get_and_set_fmu_state: bool = False
        self.can_serialize_fmu_state: bool = False
        self.can_handle_variable_communication_step_size: bool | None = None
        self.might_return_early_from_do_step: bool | None = None
        self.early_return_allowed: bool = False
        self.communication_step_size: float | None = None
        self.checkpoint_state: fmi3FMUState | None = None
        self.checkpoint_worker_state: _FmiThreeWorkerState | None = None
        self.checkpoint_communication_time: float | None = None
        self.checkpoint_communication_step_size: float | None = None
        self.maximum_float64_values_per_request: int = (
            maximum_float64_values_per_request
        )

    def _error_response(
        self,
        request_id: int,
        failure_kind: FmiThreeWorkerFailureKind,
        error_message: str,
    ) -> FmiThreeWorkerResponse:
        """Close native ownership and return one typed terminal failure.

        :param request_id: Identifier of the request that failed.
        :param failure_kind: Stable failure category for the parent.
        :param error_message: Controlled diagnostic without exception transport.
        :return: Terminal worker response.
        """

        self.release()
        return FmiThreeWorkerResponse(
            request_id=request_id,
            kind=FmiThreeWorkerResponseKind.ERROR,
            failure_kind=failure_kind,
            error_message=error_message,
        )

    def _handle_start(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Revalidate metadata and instantiate the exact staged native FMU.

        :param request: Decoded START request envelope.
        :return: READY or one typed terminal failure.
        """

        start: FmiThreeWorkerStartRequest | None = request.start
        if (
            self.state == _FmiThreeWorkerState.EXPECTING_START
            and start is not None
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker START is valid only before native construction",
            )

        # Parsing performs the fresh bounded directory inspection. Its receipt
        # must still identify the exact tree authorized by the parent.
        try:
            metadata: FmuModelDescription = read_fmu_model_description(
                start.extracted_fmu_directory
            )
        except ValueError:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.ARCHIVE,
                "FMI 3 worker rejected the staged FMU identity or metadata",
            )
        except RuntimeError:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker rejected the staged FMU execution mode",
            )
        if metadata.inspection_receipt is None:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.ARCHIVE,
                "FMI 3 worker metadata has no directory inspection receipt",
            )
        else:
            pass
        try:
            validate_fmi_three_worker_staging_identity(
                expected=start.staging_identity,
                observed_receipt=metadata.inspection_receipt,
            )
        except ValueError:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.ARCHIVE,
                "FMI 3 worker rejected the staged FMU identity or metadata",
            )

        # The selected interface owns its distinct lifecycle capabilities while
        # both modes share the same bounded variable and staging policy.
        # Exact request-to-metadata identity checks prevent the parent from
        # selecting an alternate interface binary or instantiation token.
        try:
            if start.interface_mode == FmuInterfaceMode.CO_SIMULATION:
                validate_fmi_three_co_simulation_worker_profile(
                    metadata=metadata,
                    preferred_mode=start.interface_mode,
                    float64_profile=start.float64_profile,
                )
            else:
                if start.interface_mode == FmuInterfaceMode.MODEL_EXCHANGE:
                    validate_fmi_three_model_exchange_worker_profile(
                        metadata=metadata,
                        preferred_mode=start.interface_mode,
                        float64_profile=start.float64_profile,
                    )
                else:
                    return self._error_response(
                        request.request_id,
                        FmiThreeWorkerFailureKind.LIFECYCLE,
                        "FMI 3 worker rejected the declared interface profile",
                    )
            declared_model_identifier: str = metadata.get_model_identifier(
                start.interface_mode
            )
        except RuntimeError:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker rejected the declared interface profile",
            )
        if start.interface_mode == FmuInterfaceMode.CO_SIMULATION:
            co_simulation_capabilities: FmiThreeCoSimulationCapabilities | None = (
                metadata.fmi_three_co_simulation_capabilities
            )
            if co_simulation_capabilities is None:
                return self._error_response(
                    request.request_id,
                    FmiThreeWorkerFailureKind.LIFECYCLE,
                    "FMI 3 worker Co-Simulation capabilities are unavailable",
                )
            else:
                can_get_and_set_fmu_state: bool = (
                    co_simulation_capabilities.can_get_and_set_fmu_state
                )
                can_serialize_fmu_state: bool = (
                    co_simulation_capabilities.can_serialize_fmu_state
                )
        else:
            model_exchange_capabilities: FmiThreeModelExchangeCapabilities | None = (
                metadata.fmi_three_model_exchange_capabilities
            )
            if model_exchange_capabilities is None:
                return self._error_response(
                    request.request_id,
                    FmiThreeWorkerFailureKind.LIFECYCLE,
                    "FMI 3 worker Model Exchange capabilities are unavailable",
                )
            else:
                co_simulation_capabilities = None
                can_get_and_set_fmu_state = (
                    model_exchange_capabilities.can_get_and_set_fmu_state
                )
                can_serialize_fmu_state = (
                    model_exchange_capabilities.can_serialize_fmu_state
                )
        identity_matches: bool = (
            metadata.fmi_version_family == FmiVersion.FMI_3_0
            and metadata.instantiation_token == start.instantiation_token
            and declared_model_identifier == start.model_identifier
        )
        if identity_matches:
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker START identity differs from modelDescription.xml",
            )

        # Retain only bounded integer ACL lookups after metadata validation.
        # Names and the complete parsed model do not enter native execution.
        try:
            readable_value_counts: dict[int, int]
            writable_value_counts: dict[int, int]
            initialization_writable_value_counts: dict[int, int]
            configuration_writable_value_counts: dict[int, int]
            configuration_uint64_writable_references: frozenset[int]
            readable_int32_references: frozenset[int]
            writable_int32_references: frozenset[int]
            initialization_writable_int32_references: frozenset[int]
            variable_cardinality_plans: dict[
                int, FmiThreeFloat64VariableCardinalityPlan
            ]
            (
                readable_value_counts,
                writable_value_counts,
                initialization_writable_value_counts,
                configuration_writable_value_counts,
                configuration_uint64_writable_references,
                readable_int32_references,
                writable_int32_references,
                initialization_writable_int32_references,
                variable_cardinality_plans,
            ) = _resolve_fmi_three_worker_access_controls(
                metadata=metadata,
                maximum_serialized_value_count=(
                    self.maximum_float64_values_per_request
                ),
            )
        except (ValueError, RuntimeError):
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker could not resolve numeric variable access",
            )

        # Reconcile the independent FMPy parser before trusting its ABI wrapper.
        # This does not replace VeraGrid's authoritative metadata; it detects a
        # disagreement at the boundary that will construct the native object.
        try:
            fmpy_metadata: ModelDescription = fmpy.read_model_description(
                start.extracted_fmu_directory,
                validate=True,
            )
            if start.interface_mode == FmuInterfaceMode.CO_SIMULATION:
                if fmpy_metadata.coSimulation is not None:
                    fmpy_model_identifier: str | None = (
                        fmpy_metadata.coSimulation.modelIdentifier
                    )
                else:
                    fmpy_model_identifier = None
            else:
                if fmpy_metadata.modelExchange is not None:
                    fmpy_model_identifier = (
                        fmpy_metadata.modelExchange.modelIdentifier
                    )
                else:
                    fmpy_model_identifier = None
            fmpy_metadata_matches: bool = (
                fmpy_metadata.fmiVersion == metadata.fmi_version
                and fmpy_metadata.modelName == metadata.model_name
                and fmpy_metadata.instantiationToken == metadata.instantiation_token
                and fmpy_model_identifier == declared_model_identifier
            )
        except Exception:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.ARCHIVE,
                "FMI 3 worker rejected the FMPy metadata interpretation",
            )
        if fmpy_metadata_matches:
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.ARCHIVE,
                "FMI 3 worker metadata parsers disagree on native identity",
            )

        # Re-inspect immediately before the native boundary. A mutation during
        # metadata reconciliation remains an archive failure, not a misleading
        # native-load diagnostic.
        try:
            native_inspection: FmuInspectionResult = inspect_fmu(
                start.extracted_fmu_directory
            )
            validate_fmi_three_worker_staging_identity(
                expected=start.staging_identity,
                observed_receipt=native_inspection.receipt,
            )
        except ValueError:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.ARCHIVE,
                "FMI 3 worker staging changed before native construction",
            )

        # Native preflight happens only after all source and metadata checks.
        # Construction resolves only the authenticated interface ABI. The
        # Co-Simulation branch keeps Event Mode, early return, and Intermediate
        # Update callbacks disabled; Model Exchange uses its narrower constructor.
        try:
            validate_fmi_three_native_binary(
                receipt=native_inspection.receipt,
                model_identifier=declared_model_identifier,
            )
            platform_tuple: str
            library_suffix: str
            platform_tuple, library_suffix = resolve_fmi_three_host_binary()
            if (
                fmpy.platform_tuple == platform_tuple
                and fmpy.sharedLibraryExtension == library_suffix
            ):
                pass
            else:
                raise RuntimeError(
                    "FMPy and VeraGrid resolve different FMI 3 host binaries"
                )
            self.runtime = _construct_fmi_three_runtime(start)
        except Exception:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker could not construct the validated native instance",
            )
        self.readable_value_counts = readable_value_counts
        self.writable_value_counts = writable_value_counts
        self.initialization_writable_value_counts = (
            initialization_writable_value_counts
        )
        self.configuration_writable_value_counts = (
            configuration_writable_value_counts
        )
        self.configuration_uint64_writable_references = (
            configuration_uint64_writable_references
        )
        self.readable_int32_references = readable_int32_references
        self.writable_int32_references = writable_int32_references
        self.initialization_writable_int32_references = (
            initialization_writable_int32_references
        )
        self.variable_cardinality_plans = variable_cardinality_plans
        self.interface_mode = start.interface_mode
        self.can_get_and_set_fmu_state = can_get_and_set_fmu_state
        self.can_serialize_fmu_state = can_serialize_fmu_state
        if metadata.number_of_event_indicators <= self.maximum_float64_values_per_request:
            self.event_indicator_count = metadata.number_of_event_indicators
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.VARIABLE_ACCESS,
                "FMI 3 worker event-indicator count exceeds its value bound",
            )
        # ``fixedInternalStepSize`` is an importer synchronization hint in FMI,
        # not a validity rule. The normative variable-size capability is the
        # only step-size restriction enforced at this execution boundary.
        if co_simulation_capabilities is not None:
            self.can_handle_variable_communication_step_size = (
                co_simulation_capabilities.can_handle_variable_communication_step_size
            )
            self.might_return_early_from_do_step = (
                co_simulation_capabilities.might_return_early_from_do_step
            )
            self.early_return_allowed = start.early_return_allowed
        else:
            self.can_handle_variable_communication_step_size = None
            self.might_return_early_from_do_step = None
            self.early_return_allowed = False
        self.state = _FmiThreeWorkerState.READY
        return FmiThreeWorkerResponse(
            request_id=request.request_id,
            kind=FmiThreeWorkerResponseKind.READY,
            failure_kind=None,
            error_message=None,
        )

    def _handle_configuration(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Apply one bounded structural Float64 Configuration Mode batch.

        :param request: Decoded CONFIGURE_FLOAT64 request envelope.
        :return: CONFIGURED or one typed terminal failure.
        """

        configuration: FmiThreeWorkerConfigureFloat64Request | None = (
            request.configuration
        )
        if (
            self.state == _FmiThreeWorkerState.READY
            and self.runtime is not None
            and configuration is not None
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker CONFIGURE_FLOAT64 requires one ready native "
                "instance",
            )
        if _serialized_value_count_matches_access(
            requested_references=configuration.value_references,
            serialized_value_count=len(configuration.values),
            allowed_value_counts=self.configuration_writable_value_counts,
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.VARIABLE_ACCESS,
                "FMI 3 worker CONFIGURE_FLOAT64 reference or serialized "
                "cardinality is not writable in Configuration Mode",
            )
        try:
            self.runtime.enterConfigurationMode()
            self.state = _FmiThreeWorkerState.CONFIGURATION_ENTERED
            self.runtime.setFloat64(
                list(configuration.value_references),
                list(configuration.values),
            )
            self.runtime.exitConfigurationMode()
        except Exception:
            self.state = _FmiThreeWorkerState.NATIVE_FAILED
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker native Configuration Mode failed",
            )
        self.state = _FmiThreeWorkerState.READY
        return FmiThreeWorkerResponse(
            request_id=request.request_id,
            kind=FmiThreeWorkerResponseKind.CONFIGURED,
            failure_kind=None,
            error_message=None,
        )

    def _handle_configuration_uint64(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Apply scalar structural UInt64 values in Configuration Mode.

        :param request: Decoded CONFIGURE_UINT64 request envelope.
        :return: CONFIGURED or one typed terminal failure.
        """

        configuration: FmiThreeWorkerConfigureUInt64Request | None = (
            request.configuration_uint64
        )
        if (
            self.state == _FmiThreeWorkerState.READY
            and self.runtime is not None
            and configuration is not None
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker CONFIGURE_UINT64 requires one ready native "
                "instance",
            )
        references_are_allowed: bool = True
        value_reference: int
        for value_reference in configuration.value_references:
            if value_reference in self.configuration_uint64_writable_references:
                pass
            else:
                references_are_allowed = False
        if references_are_allowed:
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.VARIABLE_ACCESS,
                "FMI 3 worker CONFIGURE_UINT64 reference is not a scalar "
                "structural UInt64 parameter",
            )
        # Preview every Float64 variable independently before native mutation.
        # This preserves the worker's memory bound even for arrays that are not
        # selected by the parent session but remain accessible through the ABI.
        configured_cardinality_plans: dict[
            int, FmiThreeFloat64VariableCardinalityPlan
        ] = dict()
        configured_value_counts: dict[int, int] = dict()
        try:
            current_value_reference: int
            for current_value_reference in self.variable_cardinality_plans:
                current_plan: FmiThreeFloat64VariableCardinalityPlan = (
                    self.variable_cardinality_plans[current_value_reference]
                )
                configured_plan: FmiThreeFloat64VariableCardinalityPlan = (
                    current_plan.configure_uint64(
                        value_references=configuration.value_references,
                        values=configuration.values,
                        maximum_serialized_value_count=(
                            self.maximum_float64_values_per_request
                        ),
                    )
                )
                configured_cardinality_plans[current_value_reference] = (
                    configured_plan
                )
                configured_value_counts[current_value_reference] = (
                    configured_plan.resolve_serialized_value_count(
                        self.maximum_float64_values_per_request
                    )
                )
        except ValueError:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.VARIABLE_ACCESS,
                "FMI 3 worker CONFIGURE_UINT64 would exceed the Float64 "
                "cardinality bound",
            )
        try:
            self.runtime.enterConfigurationMode()
            self.state = _FmiThreeWorkerState.CONFIGURATION_ENTERED
            self.runtime.setUInt64(
                list(configuration.value_references),
                list(configuration.values),
            )
            self.runtime.exitConfigurationMode()
        except Exception:
            self.state = _FmiThreeWorkerState.NATIVE_FAILED
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker native UInt64 Configuration Mode failed",
            )
        # Publish the new plans and exact ACL counts only after the FMU has
        # resized its arrays successfully while leaving Configuration Mode.
        self.variable_cardinality_plans = configured_cardinality_plans
        configured_value_reference: int
        for configured_value_reference in configured_value_counts:
            configured_value_count: int = configured_value_counts[
                configured_value_reference
            ]
            if configured_value_reference in self.readable_value_counts:
                self.readable_value_counts[configured_value_reference] = (
                    configured_value_count
                )
            else:
                pass
            if configured_value_reference in self.writable_value_counts:
                self.writable_value_counts[configured_value_reference] = (
                    configured_value_count
                )
            else:
                pass
            if (
                configured_value_reference
                in self.initialization_writable_value_counts
            ):
                self.initialization_writable_value_counts[
                    configured_value_reference
                ] = configured_value_count
            else:
                pass
            if (
                configured_value_reference
                in self.configuration_writable_value_counts
            ):
                self.configuration_writable_value_counts[
                    configured_value_reference
                ] = configured_value_count
            else:
                pass
        self.state = _FmiThreeWorkerState.READY
        return FmiThreeWorkerResponse(
            request_id=request.request_id,
            kind=FmiThreeWorkerResponseKind.CONFIGURED,
            failure_kind=None,
            error_message=None,
        )

    def _handle_initialization(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Execute FMI 3 initialization without entering productive stepping.

        :param request: Decoded INITIALIZE request envelope.
        :return: INITIALIZED or one typed terminal failure.
        """

        initialization: FmiThreeWorkerInitializationRequest | None = (
            request.initialization
        )
        if (
            self.state == _FmiThreeWorkerState.READY
            and self.runtime is not None
            and initialization is not None
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker INITIALIZE requires one ready native instance",
            )
        if _serialized_value_count_matches_access(
            requested_references=initialization.initial_float64_value_references,
            serialized_value_count=len(initialization.initial_float64_values),
            allowed_value_counts=self.initialization_writable_value_counts,
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.VARIABLE_ACCESS,
                "FMI 3 worker initial Float64 reference or serialized "
                "cardinality is not writable in Initialization Mode",
            )
        int32_references_are_allowed: bool = (
            len(initialization.initial_int32_value_references)
            == len(initialization.initial_int32_values)
        )
        initial_int32_value_reference: int
        for initial_int32_value_reference in (
            initialization.initial_int32_value_references
        ):
            if (
                initial_int32_value_reference
                in self.initialization_writable_int32_references
            ):
                pass
            else:
                int32_references_are_allowed = False
        if int32_references_are_allowed:
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.VARIABLE_ACCESS,
                "FMI 3 worker initial Int32 reference is not writable in "
                "Initialization Mode",
            )
        try:
            self.runtime.enterInitializationMode(
                tolerance=initialization.relative_tolerance,
                startTime=initialization.start_time,
                stopTime=initialization.stop_time,
            )
            self.state = _FmiThreeWorkerState.INITIALIZATION_ENTERED
            if len(initialization.initial_float64_value_references) > 0:
                self.runtime.setFloat64(
                    list(initialization.initial_float64_value_references),
                    list(initialization.initial_float64_values),
                )
            else:
                pass
            if len(initialization.initial_int32_value_references) > 0:
                self.runtime.setInt32(
                    list(initialization.initial_int32_value_references),
                    list(initialization.initial_int32_values),
                )
            else:
                pass
            self.runtime.exitInitializationMode()
            if self.interface_mode == FmuInterfaceMode.MODEL_EXCHANGE:
                native_continuous_state_count: int = int(
                    self.runtime.getNumberOfContinuousStates()
                )
                native_event_indicator_count: int = int(
                    self.runtime.getNumberOfEventIndicators()
                )
                if (
                    native_continuous_state_count >= 0
                    and native_continuous_state_count
                    <= self.maximum_float64_values_per_request
                    and native_event_indicator_count == self.event_indicator_count
                ):
                    self.continuous_state_count = native_continuous_state_count
                else:
                    raise RuntimeError(
                        "Native FMI 3 Model Exchange vector counts differ from metadata"
                    )
            else:
                pass
        except Exception:
            self.state = _FmiThreeWorkerState.NATIVE_FAILED
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker native initialization failed",
            )
        self.current_communication_time = initialization.start_time
        if self.interface_mode == FmuInterfaceMode.MODEL_EXCHANGE:
            # FMI 3 Model Exchange exits Initialization Mode into Event Mode.
            # The parent consumer owns the bounded discrete-state iteration.
            self.state = _FmiThreeWorkerState.EVENT_MODE
        else:
            self.state = _FmiThreeWorkerState.INITIALIZED
        return FmiThreeWorkerResponse(
            request_id=request.request_id,
            kind=FmiThreeWorkerResponseKind.INITIALIZED,
            failure_kind=None,
            error_message=None,
        )

    def _handle_set_float64(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Write finite writable Float64 variables in Step Mode.

        :param request: Decoded SET_FLOAT64 request envelope.
        :return: FLOAT64_SET or one typed terminal failure.
        """

        set_float64: FmiThreeWorkerSetFloat64Request | None = request.set_float64
        if (
            self.state in (
                _FmiThreeWorkerState.INITIALIZED,
                _FmiThreeWorkerState.INPUT_VALUES_PENDING_STEP,
                _FmiThreeWorkerState.CONTINUOUS_TIME,
                _FmiThreeWorkerState.EVENT_MODE,
            )
            and self.runtime is not None
            and set_float64 is not None
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker SET_FLOAT64 requires Step Mode",
            )
        if _serialized_value_count_matches_access(
            requested_references=set_float64.value_references,
            serialized_value_count=len(set_float64.values),
            allowed_value_counts=self.writable_value_counts,
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.VARIABLE_ACCESS,
                "FMI 3 worker SET_FLOAT64 reference or serialized cardinality "
                "requires an input or tunable parameter",
            )
        state_before_write: _FmiThreeWorkerState = self.state
        try:
            self.runtime.setFloat64(
                list(set_float64.value_references),
                list(set_float64.values),
            )
        except Exception:
            self.state = _FmiThreeWorkerState.NATIVE_FAILED
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker native SET_FLOAT64 failed",
            )
        if self.interface_mode == FmuInterfaceMode.MODEL_EXCHANGE:
            self.state = state_before_write
        else:
            self.state = _FmiThreeWorkerState.INPUT_VALUES_PENDING_STEP
        return FmiThreeWorkerResponse(
            request_id=request.request_id,
            kind=FmiThreeWorkerResponseKind.FLOAT64_SET,
            failure_kind=None,
            error_message=None,
        )

    def _handle_get_float64(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Read finite declared Float64 values in request order.

        :param request: Decoded GET_FLOAT64 request envelope.
        :return: FLOAT64_VALUES or one typed terminal failure.
        """

        get_float64: FmiThreeWorkerGetFloat64Request | None = request.get_float64
        if (
            self.state in (
                _FmiThreeWorkerState.INITIALIZED,
                _FmiThreeWorkerState.TERMINATION_REQUESTED,
                _FmiThreeWorkerState.CONTINUOUS_TIME,
                _FmiThreeWorkerState.EVENT_MODE,
            )
            and self.runtime is not None
            and get_float64 is not None
        ):
            pass
        else:
            if (
                self.state == _FmiThreeWorkerState.INPUT_VALUES_PENDING_STEP
                and self.runtime is not None
                and get_float64 is not None
            ):
                return self._error_response(
                    request.request_id,
                    FmiThreeWorkerFailureKind.LIFECYCLE,
                    "FMI 3 worker GET_FLOAT64 must precede input writes at "
                    "the current communication point",
                )
            else:
                return self._error_response(
                    request.request_id,
                    FmiThreeWorkerFailureKind.LIFECYCLE,
                    "FMI 3 worker GET_FLOAT64 requires Step Mode",
                )
        if _serialized_value_count_matches_access(
            requested_references=get_float64.value_references,
            serialized_value_count=get_float64.serialized_value_count,
            allowed_value_counts=self.readable_value_counts,
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.VARIABLE_ACCESS,
                "FMI 3 worker GET_FLOAT64 reference or serialized cardinality "
                "is not a declared Float64 variable",
            )
        try:
            native_values: list[float] = self.runtime.getFloat64(
                list(get_float64.value_references),
                nValues=get_float64.serialized_value_count,
            )
            returned_values: tuple[float, ...] = tuple(native_values)
            if len(returned_values) == get_float64.serialized_value_count:
                pass
            else:
                raise RuntimeError(
                    "The native FMI 3 GET_FLOAT64 cardinality is inconsistent"
                )
            float64_values: FmiThreeWorkerFloat64Values = (
                FmiThreeWorkerFloat64Values(
                    values=returned_values,
                    maximum_value_count=self.maximum_float64_values_per_request,
                )
            )
        except Exception:
            self.state = _FmiThreeWorkerState.NATIVE_FAILED
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker native GET_FLOAT64 failed or returned invalid values",
            )
        return FmiThreeWorkerResponse(
            request_id=request.request_id,
            kind=FmiThreeWorkerResponseKind.FLOAT64_VALUES,
            failure_kind=None,
            error_message=None,
            float64_values=float64_values,
        )

    def _handle_set_int32(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Write scalar Int32 inputs under the active interface lifecycle.

        :param request: Decoded SET_INT32 request envelope.
        :return: INT32_SET or one typed terminal failure.
        """

        set_int32: FmiThreeWorkerSetInt32Request | None = request.set_int32
        co_simulation_state_is_valid: bool = (
            self.interface_mode == FmuInterfaceMode.CO_SIMULATION
            and self.state
            in (
                _FmiThreeWorkerState.INITIALIZED,
                _FmiThreeWorkerState.INPUT_VALUES_PENDING_STEP,
            )
        )
        model_exchange_state_is_valid: bool = (
            self.interface_mode == FmuInterfaceMode.MODEL_EXCHANGE
            and self.state == _FmiThreeWorkerState.EVENT_MODE
        )
        if (
            (co_simulation_state_is_valid or model_exchange_state_is_valid)
            and self.runtime is not None
            and set_int32 is not None
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker SET_INT32 requires CS Step Mode or ME Event Mode",
            )
        references_are_writable: bool = True
        value_reference: int
        for value_reference in set_int32.value_references:
            if value_reference in self.writable_int32_references:
                pass
            else:
                references_are_writable = False
        if references_are_writable:
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.VARIABLE_ACCESS,
                "FMI 3 worker SET_INT32 requires an Int32 input or tunable parameter",
            )
        state_before_write: _FmiThreeWorkerState = self.state
        try:
            self.runtime.setInt32(
                list(set_int32.value_references),
                list(set_int32.values),
            )
        except Exception:
            self.state = _FmiThreeWorkerState.NATIVE_FAILED
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker native SET_INT32 failed",
            )
        if self.interface_mode == FmuInterfaceMode.MODEL_EXCHANGE:
            self.state = state_before_write
        else:
            self.state = _FmiThreeWorkerState.INPUT_VALUES_PENDING_STEP
        return FmiThreeWorkerResponse(
            request_id=request.request_id,
            kind=FmiThreeWorkerResponseKind.INT32_SET,
            failure_kind=None,
            error_message=None,
        )

    def _handle_get_int32(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Read scalar Int32 values under CS or ME readable states.

        :param request: Decoded GET_INT32 request envelope.
        :return: INT32_VALUES or one typed terminal failure.
        """

        get_int32: FmiThreeWorkerGetInt32Request | None = request.get_int32
        if (
            self.state
            in (
                _FmiThreeWorkerState.INITIALIZED,
                _FmiThreeWorkerState.TERMINATION_REQUESTED,
                _FmiThreeWorkerState.CONTINUOUS_TIME,
                _FmiThreeWorkerState.EVENT_MODE,
            )
            and self.runtime is not None
            and get_int32 is not None
        ):
            pass
        else:
            if (
                self.state == _FmiThreeWorkerState.INPUT_VALUES_PENDING_STEP
                and self.runtime is not None
                and get_int32 is not None
            ):
                return self._error_response(
                    request.request_id,
                    FmiThreeWorkerFailureKind.LIFECYCLE,
                    "FMI 3 worker GET_INT32 must precede input writes at the "
                    "current communication point",
                )
            else:
                return self._error_response(
                    request.request_id,
                    FmiThreeWorkerFailureKind.LIFECYCLE,
                    "FMI 3 worker GET_INT32 requires a readable runtime state",
                )
        references_are_readable: bool = True
        value_reference: int
        for value_reference in get_int32.value_references:
            if value_reference in self.readable_int32_references:
                pass
            else:
                references_are_readable = False
        if references_are_readable:
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.VARIABLE_ACCESS,
                "FMI 3 worker GET_INT32 reference is not a declared scalar Int32",
            )
        try:
            native_values: list[int] = self.runtime.getInt32(
                list(get_int32.value_references)
            )
            returned_values: tuple[int, ...] = tuple(native_values)
            if len(returned_values) == len(get_int32.value_references):
                int32_values: FmiThreeWorkerInt32Values = (
                    FmiThreeWorkerInt32Values(
                        values=returned_values,
                        maximum_value_count=(
                            self.maximum_float64_values_per_request
                        ),
                    )
                )
            else:
                raise RuntimeError(
                    "The native FMI 3 GET_INT32 cardinality is inconsistent"
                )
        except Exception:
            self.state = _FmiThreeWorkerState.NATIVE_FAILED
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker native GET_INT32 failed or returned invalid values",
            )
        return FmiThreeWorkerResponse(
            request_id=request.request_id,
            kind=FmiThreeWorkerResponseKind.INT32_VALUES,
            failure_kind=None,
            error_message=None,
            int32_values=int32_values,
        )

    def _handle_do_step(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Advance one scalar Co-Simulation step and retain its reported time.

        :param request: Decoded DO_STEP request envelope.
        :return: STEP_COMPLETED or one typed terminal failure.
        """

        do_step: FmiThreeWorkerDoStepRequest | None = request.do_step
        if (
            self.state in (
                _FmiThreeWorkerState.INITIALIZED,
                _FmiThreeWorkerState.INPUT_VALUES_PENDING_STEP,
            )
            and self.runtime is not None
            and isinstance(self.runtime, FMU3Slave)
            and do_step is not None
            and self.current_communication_time is not None
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker DO_STEP requires Step Mode",
            )
        if do_step.current_communication_point == self.current_communication_time:
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker DO_STEP communication point is not continuous",
            )
        can_handle_variable_step_size: bool | None = (
            self.can_handle_variable_communication_step_size
        )
        if can_handle_variable_step_size is not None:
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker communication-step capability is unavailable",
            )
        if (
            can_handle_variable_step_size
            or self.communication_step_size is None
            or do_step.communication_step_size == self.communication_step_size
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker requires a constant communication step size",
            )
        try:
            native_step_result: tuple[bool, bool, bool, float] = self.runtime.doStep(
                currentCommunicationPoint=do_step.current_communication_point,
                communicationStepSize=do_step.communication_step_size,
                noSetFMUStatePriorToCurrentPoint=(
                    do_step.no_set_fmu_state_prior_to_current_point
                ),
            )
            do_step_result: FmiThreeWorkerDoStepResult = FmiThreeWorkerDoStepResult(
                event_handling_needed=bool(native_step_result[0]),
                terminate_simulation=bool(native_step_result[1]),
                early_return=bool(native_step_result[2]),
                last_successful_time=float(native_step_result[3]),
            )
            # Validate the complete result before advancing child-owned time.
            validate_fmi_three_worker_completed_step(
                request=do_step,
                result=do_step_result,
                early_return_allowed=self.early_return_allowed,
                might_return_early_from_do_step=bool(
                    self.might_return_early_from_do_step
                ),
            )
        except Exception:
            self.state = _FmiThreeWorkerState.NATIVE_FAILED
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker native DO_STEP failed or contradicted its profile",
            )
        self.current_communication_time = do_step_result.last_successful_time
        if self.communication_step_size is None:
            self.communication_step_size = do_step.communication_step_size
        else:
            pass
        if do_step_result.terminate_simulation:
            self.state = _FmiThreeWorkerState.TERMINATION_REQUESTED
        else:
            self.state = _FmiThreeWorkerState.INITIALIZED
        return FmiThreeWorkerResponse(
            request_id=request.request_id,
            kind=FmiThreeWorkerResponseKind.STEP_COMPLETED,
            failure_kind=None,
            error_message=None,
            do_step_result=do_step_result,
        )

    def _handle_set_time(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Set the finite independent variable in Continuous-Time Mode.

        :param request: Decoded SET_TIME request envelope.
        :return: TIME_SET or one typed terminal failure.
        """

        set_time: FmiThreeWorkerSetTimeRequest | None = request.set_time
        if (
            self.state == _FmiThreeWorkerState.CONTINUOUS_TIME
            and isinstance(self.runtime, FMU3Model)
            and set_time is not None
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker SET_TIME requires Model Exchange Continuous-Time Mode",
            )
        try:
            self.runtime.setTime(set_time.time_value)
        except Exception:
            self.state = _FmiThreeWorkerState.NATIVE_FAILED
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker native SET_TIME failed",
            )
        self.current_communication_time = set_time.time_value
        return FmiThreeWorkerResponse(
            request_id=request.request_id,
            kind=FmiThreeWorkerResponseKind.TIME_SET,
            failure_kind=None,
            error_message=None,
        )

    def _handle_set_continuous_states(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Set the complete bounded Model Exchange state vector.

        :param request: Decoded SET_CONTINUOUS_STATES request envelope.
        :return: CONTINUOUS_STATES_SET or one typed terminal failure.
        """

        continuous_states: FmiThreeWorkerFloat64Values | None = (
            request.continuous_states
        )
        if (
            self.state == _FmiThreeWorkerState.CONTINUOUS_TIME
            and isinstance(self.runtime, FMU3Model)
            and self.continuous_state_count is not None
            and continuous_states is not None
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker SET_CONTINUOUS_STATES requires Model Exchange "
                "Continuous-Time Mode",
            )
        if len(continuous_states.values) == self.continuous_state_count:
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.VARIABLE_ACCESS,
                "FMI 3 worker continuous-state cardinality differs from the FMU",
            )
        try:
            state_buffer: Array[c_double] = (c_double * len(continuous_states.values))(
                *continuous_states.values
            )
            self.runtime.setContinuousStates(
                state_buffer,
                len(continuous_states.values),
            )
        except Exception:
            self.state = _FmiThreeWorkerState.NATIVE_FAILED
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker native SET_CONTINUOUS_STATES failed",
            )
        return FmiThreeWorkerResponse(
            request_id=request.request_id,
            kind=FmiThreeWorkerResponseKind.CONTINUOUS_STATES_SET,
            failure_kind=None,
            error_message=None,
        )

    def _handle_get_continuous_values(
        self,
        request: FmiThreeWorkerRequest,
        request_kind: FmiThreeWorkerRequestKind,
    ) -> FmiThreeWorkerResponse:
        """Read one bounded Model Exchange vector with native cardinality.

        :param request: Decoded bodyless state or derivative request.
        :param request_kind: Exact state, derivative, indicator, or nominal read.
        :return: The matching bounded Float64 response or terminal failure.
        """

        vector_state_is_valid: bool = (
            self.state == _FmiThreeWorkerState.CONTINUOUS_TIME
            or (
                self.state == _FmiThreeWorkerState.EVENT_MODE
                and request_kind
                in (
                    FmiThreeWorkerRequestKind.GET_CONTINUOUS_STATES,
                    FmiThreeWorkerRequestKind.GET_NOMINALS_OF_CONTINUOUS_STATES,
                )
            )
        )
        if (
            vector_state_is_valid
            and isinstance(self.runtime, FMU3Model)
            and self.continuous_state_count is not None
            and self.event_indicator_count is not None
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker continuous-vector read requires Model Exchange "
                "Continuous-Time Mode",
            )
        try:
            if request_kind == FmiThreeWorkerRequestKind.GET_EVENT_INDICATORS:
                value_count: int = self.event_indicator_count
            else:
                value_count = self.continuous_state_count
            value_buffer: Array[c_double] = (c_double * value_count)()
            if request_kind == FmiThreeWorkerRequestKind.GET_DERIVATIVES:
                self.runtime.getContinuousStateDerivatives(
                    value_buffer,
                    value_count,
                )
                response_kind: FmiThreeWorkerResponseKind = (
                    FmiThreeWorkerResponseKind.DERIVATIVE_VALUES
                )
            else:
                if request_kind == FmiThreeWorkerRequestKind.GET_CONTINUOUS_STATES:
                    self.runtime.getContinuousStates(value_buffer, value_count)
                    response_kind = (
                        FmiThreeWorkerResponseKind.CONTINUOUS_STATES_VALUES
                    )
                else:
                    if request_kind == FmiThreeWorkerRequestKind.GET_EVENT_INDICATORS:
                        self.runtime.getEventIndicators(value_buffer, value_count)
                        response_kind = (
                            FmiThreeWorkerResponseKind.EVENT_INDICATOR_VALUES
                        )
                    else:
                        if (
                            request_kind
                            == FmiThreeWorkerRequestKind.GET_NOMINALS_OF_CONTINUOUS_STATES
                        ):
                            self.runtime.getNominalsOfContinuousStates(
                                value_buffer,
                                value_count,
                            )
                            response_kind = (
                                FmiThreeWorkerResponseKind.CONTINUOUS_STATE_NOMINAL_VALUES
                            )
                        else:
                            raise RuntimeError(
                                "Unsupported FMI 3 Model Exchange vector read"
                            )
            returned_values: list[float] = [0.0] * value_count
            value_index: int
            for value_index in range(value_count):
                returned_values[value_index] = float(value_buffer[value_index])
            float64_values: FmiThreeWorkerFloat64Values = (
                FmiThreeWorkerFloat64Values(
                    values=tuple(returned_values),
                    maximum_value_count=self.maximum_float64_values_per_request,
                )
            )
        except Exception:
            self.state = _FmiThreeWorkerState.NATIVE_FAILED
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker native continuous-vector read failed",
            )
        return FmiThreeWorkerResponse(
            request_id=request.request_id,
            kind=response_kind,
            failure_kind=None,
            error_message=None,
            float64_values=float64_values,
        )

    def _handle_evaluate_model_exchange(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Evaluate one externally supplied Model Exchange solver point.

        :param request: Decoded EVALUATE_MODEL_EXCHANGE request envelope.
        :return: Derivatives and readable values from one native call sequence.
        """

        evaluation: FmiThreeWorkerModelExchangeEvaluationRequest | None = (
            request.model_exchange_evaluation
        )
        if (
            self.state == _FmiThreeWorkerState.CONTINUOUS_TIME
            and isinstance(self.runtime, FMU3Model)
            and self.continuous_state_count is not None
            and evaluation is not None
        ):
            runtime: FMU3Model = self.runtime
            continuous_state_count: int = self.continuous_state_count
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker EVALUATE_MODEL_EXCHANGE requires Continuous-Time Mode",
            )
        if len(evaluation.continuous_states.values) == continuous_state_count:
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.VARIABLE_ACCESS,
                "FMI 3 worker evaluation state cardinality differs from the FMU",
            )
        set_float64: FmiThreeWorkerSetFloat64Request | None = (
            evaluation.set_float64
        )
        if set_float64 is not None:
            write_access_is_valid: bool = _serialized_value_count_matches_access(
                requested_references=set_float64.value_references,
                serialized_value_count=len(set_float64.values),
                allowed_value_counts=self.writable_value_counts,
            )
        else:
            write_access_is_valid = True
        get_float64: FmiThreeWorkerGetFloat64Request | None = (
            evaluation.get_float64
        )
        if get_float64 is not None:
            read_access_is_valid: bool = _serialized_value_count_matches_access(
                requested_references=get_float64.value_references,
                serialized_value_count=get_float64.serialized_value_count,
                allowed_value_counts=self.readable_value_counts,
            )
        else:
            read_access_is_valid = True
        if write_access_is_valid and read_access_is_valid:
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.VARIABLE_ACCESS,
                "FMI 3 worker evaluation requested undeclared Float64 access",
            )
        try:
            # Present the complete solver point before requesting any result.
            runtime.setTime(evaluation.set_time.time_value)
            state_buffer: Array[c_double] = (
                c_double * continuous_state_count
            )(*evaluation.continuous_states.values)
            runtime.setContinuousStates(
                state_buffer,
                continuous_state_count,
            )
            if set_float64 is not None:
                runtime.setFloat64(
                    list(set_float64.value_references),
                    list(set_float64.values),
                )
            else:
                pass
            # Read both consumer result groups before acknowledging the point.
            derivative_buffer: Array[c_double] = (
                c_double * continuous_state_count
            )()
            runtime.getContinuousStateDerivatives(
                derivative_buffer,
                continuous_state_count,
            )
            derivative_values: list[float] = [0.0] * continuous_state_count
            derivative_index: int
            for derivative_index in range(continuous_state_count):
                derivative_values[derivative_index] = float(
                    derivative_buffer[derivative_index]
                )
            if get_float64 is not None:
                native_readable_values: list[float] = runtime.getFloat64(
                    list(get_float64.value_references),
                    nValues=get_float64.serialized_value_count,
                )
                readable_values: tuple[float, ...] = tuple(
                    native_readable_values
                )
                if len(readable_values) == get_float64.serialized_value_count:
                    pass
                else:
                    raise RuntimeError(
                        "Native Model Exchange readable cardinality is inconsistent"
                    )
            else:
                readable_values = tuple()
            evaluation_result: FmiThreeWorkerModelExchangeEvaluationResult = (
                FmiThreeWorkerModelExchangeEvaluationResult(
                    derivatives=FmiThreeWorkerFloat64Values(
                        values=tuple(derivative_values),
                        maximum_value_count=(
                            self.maximum_float64_values_per_request
                        ),
                    ),
                    readable_values=FmiThreeWorkerFloat64Values(
                        values=readable_values,
                        maximum_value_count=(
                            self.maximum_float64_values_per_request
                        ),
                    ),
                )
            )
        except Exception:
            self.state = _FmiThreeWorkerState.NATIVE_FAILED
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker native Model Exchange evaluation failed",
            )
        self.current_communication_time = evaluation.set_time.time_value
        return FmiThreeWorkerResponse(
            request_id=request.request_id,
            kind=FmiThreeWorkerResponseKind.MODEL_EXCHANGE_EVALUATED,
            failure_kind=None,
            error_message=None,
            model_exchange_evaluation_result=evaluation_result,
        )

    def _handle_completed_integrator_step(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Notify the FMU that one external integrator step completed.

        :param request: Decoded COMPLETED_INTEGRATOR_STEP request envelope.
        :return: INTEGRATOR_STEP_COMPLETED or one typed terminal failure.
        """

        completed_step: FmiThreeWorkerCompletedIntegratorStepRequest | None = (
            request.completed_integrator_step
        )
        if (
            self.state == _FmiThreeWorkerState.CONTINUOUS_TIME
            and isinstance(self.runtime, FMU3Model)
            and completed_step is not None
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker COMPLETED_INTEGRATOR_STEP requires Model Exchange "
                "Continuous-Time Mode",
            )
        try:
            native_result: tuple[bool, bool] = self.runtime.completedIntegratorStep(
                noSetFMUStatePriorToCurrentPoint=(
                    completed_step.no_set_fmu_state_prior_to_current_point
                )
            )
            completed_result: FmiThreeWorkerCompletedIntegratorStepResult = (
                FmiThreeWorkerCompletedIntegratorStepResult(
                    enter_event_mode=bool(native_result[0]),
                    terminate_simulation=bool(native_result[1]),
                )
            )
        except Exception:
            self.state = _FmiThreeWorkerState.NATIVE_FAILED
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker native COMPLETED_INTEGRATOR_STEP failed",
            )
        if completed_result.terminate_simulation:
            self.state = _FmiThreeWorkerState.TERMINATION_REQUESTED
        else:
            if completed_result.enter_event_mode:
                self.state = _FmiThreeWorkerState.EVENT_MODE_REQUESTED
            else:
                self.state = _FmiThreeWorkerState.CONTINUOUS_TIME
        return FmiThreeWorkerResponse(
            request_id=request.request_id,
            kind=FmiThreeWorkerResponseKind.INTEGRATOR_STEP_COMPLETED,
            failure_kind=None,
            error_message=None,
            completed_integrator_step_result=completed_result,
        )

    def _handle_enter_event_mode(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Execute one native transition from Continuous-Time to Event Mode.

        :param request: Decoded bodyless ENTER_EVENT_MODE request.
        :return: EVENT_MODE_ENTERED or one typed terminal failure.
        """

        if (
            self.state in (
                _FmiThreeWorkerState.CONTINUOUS_TIME,
                _FmiThreeWorkerState.EVENT_MODE_REQUESTED,
            )
            and isinstance(self.runtime, FMU3Model)
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker ENTER_EVENT_MODE requires Model Exchange "
                "Continuous-Time Mode or a completed-step event request",
            )
        try:
            self.runtime.enterEventMode()
        except Exception:
            self.state = _FmiThreeWorkerState.NATIVE_FAILED
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker native ENTER_EVENT_MODE failed",
            )
        self.state = _FmiThreeWorkerState.EVENT_MODE
        return FmiThreeWorkerResponse(
            request_id=request.request_id,
            kind=FmiThreeWorkerResponseKind.EVENT_MODE_ENTERED,
            failure_kind=None,
            error_message=None,
        )

    def _handle_update_discrete_states(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Execute exactly one native discrete-state update in Event Mode.

        :param request: Decoded bodyless UPDATE_DISCRETE_STATES request.
        :return: Exact six-field result or one typed terminal failure.
        """

        if (
            self.state == _FmiThreeWorkerState.EVENT_MODE
            and isinstance(self.runtime, FMU3Model)
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker UPDATE_DISCRETE_STATES requires Model Exchange Event Mode",
            )
        try:
            native_result: tuple[bool, bool, bool, bool, bool, float] = (
                self.runtime.updateDiscreteStates()
            )
            discrete_states_result: FmiThreeWorkerDiscreteStatesResult = (
                FmiThreeWorkerDiscreteStatesResult(
                    discrete_states_need_update=bool(native_result[0]),
                    terminate_simulation=bool(native_result[1]),
                    nominals_of_continuous_states_changed=bool(native_result[2]),
                    values_of_continuous_states_changed=bool(native_result[3]),
                    next_event_time_defined=bool(native_result[4]),
                    next_event_time=float(native_result[5]),
                )
            )
        except Exception:
            self.state = _FmiThreeWorkerState.NATIVE_FAILED
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker native UPDATE_DISCRETE_STATES failed",
            )
        if discrete_states_result.terminate_simulation:
            self.state = _FmiThreeWorkerState.TERMINATION_REQUESTED
        else:
            self.state = _FmiThreeWorkerState.EVENT_MODE
        return FmiThreeWorkerResponse(
            request_id=request.request_id,
            kind=FmiThreeWorkerResponseKind.DISCRETE_STATES_UPDATED,
            failure_kind=None,
            error_message=None,
            discrete_states_result=discrete_states_result,
        )

    def _handle_enter_continuous_time_mode(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Execute one native transition from Event to Continuous-Time Mode.

        :param request: Decoded bodyless ENTER_CONTINUOUS_TIME_MODE request.
        :return: CONTINUOUS_TIME_MODE_ENTERED or one typed terminal failure.
        """

        if (
            self.state == _FmiThreeWorkerState.EVENT_MODE
            and isinstance(self.runtime, FMU3Model)
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker ENTER_CONTINUOUS_TIME_MODE requires Model Exchange Event Mode",
            )
        try:
            self.runtime.enterContinuousTimeMode()
            native_continuous_state_count: int = int(
                self.runtime.getNumberOfContinuousStates()
            )
            if (
                native_continuous_state_count >= 0
                and native_continuous_state_count
                <= self.maximum_float64_values_per_request
            ):
                self.continuous_state_count = native_continuous_state_count
            else:
                raise RuntimeError(
                    "The native FMI 3 continuous-state count exceeds the worker bound"
                )
        except Exception:
            self.state = _FmiThreeWorkerState.NATIVE_FAILED
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker native ENTER_CONTINUOUS_TIME_MODE failed",
            )
        self.state = _FmiThreeWorkerState.CONTINUOUS_TIME
        return FmiThreeWorkerResponse(
            request_id=request.request_id,
            kind=FmiThreeWorkerResponseKind.CONTINUOUS_TIME_MODE_ENTERED,
            failure_kind=None,
            error_message=None,
        )

    def _release_checkpoint_state(self) -> bool:
        """Release the sole native checkpoint and clear its mirrored metadata.

        :return: ``True`` when no native checkpoint remains allocated.
        """

        release_succeeded: bool = True
        native_checkpoint_state: fmi3FMUState | None = self.checkpoint_state
        runtime: FMU3Slave | FMU3Model | None = self.runtime
        if native_checkpoint_state is not None:
            if runtime is not None:
                try:
                    runtime.freeFMUState(native_checkpoint_state)
                except Exception:
                    release_succeeded = False
            else:
                release_succeeded = False
        else:
            pass
        self.checkpoint_state = None
        self.checkpoint_worker_state = None
        self.checkpoint_communication_time = None
        self.checkpoint_communication_step_size = None
        return release_succeeded

    def _handle_save_checkpoint(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Replace the sole native checkpoint at one accepted stable point.

        :param request: Decoded bodyless SAVE_CHECKPOINT request.
        :return: CHECKPOINT_SAVED or one typed terminal failure.
        """

        if (
            self.can_get_and_set_fmu_state
            and self.state in (
                _FmiThreeWorkerState.INITIALIZED,
                _FmiThreeWorkerState.CONTINUOUS_TIME,
            )
            and self.runtime is not None
        ):
            runtime: FMU3Slave | FMU3Model = self.runtime
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker SAVE_CHECKPOINT requires supported Step or Continuous-Time Mode",
            )
        if self._release_checkpoint_state():
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker could not replace the previous native checkpoint",
            )
        try:
            native_checkpoint_state: fmi3FMUState = runtime.getFMUState()
        except Exception:
            self.state = _FmiThreeWorkerState.NATIVE_FAILED
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker native SAVE_CHECKPOINT failed",
            )
        self.checkpoint_state = native_checkpoint_state
        self.checkpoint_worker_state = self.state
        self.checkpoint_communication_time = self.current_communication_time
        self.checkpoint_communication_step_size = self.communication_step_size
        return FmiThreeWorkerResponse(
            request_id=request.request_id,
            kind=FmiThreeWorkerResponseKind.CHECKPOINT_SAVED,
            failure_kind=None,
            error_message=None,
        )

    def _handle_restore_checkpoint(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Restore the sole native checkpoint without consuming it.

        :param request: Decoded bodyless RESTORE_CHECKPOINT request.
        :return: CHECKPOINT_RESTORED or one typed terminal failure.
        """

        saved_worker_state: _FmiThreeWorkerState | None = (
            self.checkpoint_worker_state
        )
        co_simulation_restore_is_valid: bool = (
            saved_worker_state == _FmiThreeWorkerState.INITIALIZED
            and self.state
            in (
                _FmiThreeWorkerState.INITIALIZED,
                _FmiThreeWorkerState.INPUT_VALUES_PENDING_STEP,
                _FmiThreeWorkerState.TERMINATION_REQUESTED,
            )
        )
        model_exchange_restore_is_valid: bool = (
            saved_worker_state == _FmiThreeWorkerState.CONTINUOUS_TIME
            and self.state
            in (
                _FmiThreeWorkerState.CONTINUOUS_TIME,
                _FmiThreeWorkerState.EVENT_MODE_REQUESTED,
                _FmiThreeWorkerState.EVENT_MODE,
                _FmiThreeWorkerState.TERMINATION_REQUESTED,
            )
        )
        native_checkpoint_state: fmi3FMUState | None = self.checkpoint_state
        if (
            self.can_get_and_set_fmu_state
            and (co_simulation_restore_is_valid or model_exchange_restore_is_valid)
            and native_checkpoint_state is not None
            and self.runtime is not None
            and saved_worker_state is not None
        ):
            runtime: FMU3Slave | FMU3Model = self.runtime
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker RESTORE_CHECKPOINT requires a compatible saved state",
            )
        try:
            runtime.setFMUState(native_checkpoint_state)
        except Exception:
            self.state = _FmiThreeWorkerState.NATIVE_FAILED
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker native RESTORE_CHECKPOINT failed",
            )
        self.state = saved_worker_state
        self.current_communication_time = self.checkpoint_communication_time
        self.communication_step_size = self.checkpoint_communication_step_size
        return FmiThreeWorkerResponse(
            request_id=request.request_id,
            kind=FmiThreeWorkerResponseKind.CHECKPOINT_RESTORED,
            failure_kind=None,
            error_message=None,
        )

    def _handle_discard_checkpoint(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Free the sole native checkpoint without changing live FMU state.

        :param request: Decoded bodyless DISCARD_CHECKPOINT request.
        :return: CHECKPOINT_DISCARDED or one typed terminal failure.
        """

        if (
            self.can_get_and_set_fmu_state
            and self.checkpoint_state is not None
            and self.runtime is not None
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker DISCARD_CHECKPOINT requires a saved state",
            )
        if self._release_checkpoint_state():
            return FmiThreeWorkerResponse(
                request_id=request.request_id,
                kind=FmiThreeWorkerResponseKind.CHECKPOINT_DISCARDED,
                failure_kind=None,
                error_message=None,
            )
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.NATIVE,
                "FMI 3 worker native DISCARD_CHECKPOINT failed",
            )

    def _handle_close(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Terminate when required and release the native library.

        :param request: Decoded CLOSE request envelope.
        :return: CLOSED or one typed terminal failure.
        """

        if self.state in (
            _FmiThreeWorkerState.READY,
            _FmiThreeWorkerState.INITIALIZED,
            _FmiThreeWorkerState.INPUT_VALUES_PENDING_STEP,
            _FmiThreeWorkerState.TERMINATION_REQUESTED,
            _FmiThreeWorkerState.CONTINUOUS_TIME,
            _FmiThreeWorkerState.EVENT_MODE_REQUESTED,
            _FmiThreeWorkerState.EVENT_MODE,
        ):
            pass
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.LIFECYCLE,
                "FMI 3 worker CLOSE requires a constructed native instance",
            )
        release_succeeded: bool = self.release()
        if release_succeeded:
            return FmiThreeWorkerResponse(
                request_id=request.request_id,
                kind=FmiThreeWorkerResponseKind.CLOSED,
                failure_kind=None,
                error_message=None,
            )
        else:
            return FmiThreeWorkerResponse(
                request_id=request.request_id,
                kind=FmiThreeWorkerResponseKind.ERROR,
                failure_kind=FmiThreeWorkerFailureKind.NATIVE,
                error_message="FMI 3 worker could not release the native instance cleanly",
            )

    def handle_request(
        self,
        request: FmiThreeWorkerRequest,
    ) -> FmiThreeWorkerResponse:
        """Apply one decoded request to the explicit worker state machine.

        :param request: Validated request received from the parent.
        :return: Successful outcome or typed terminal failure.
        """

        if request.kind == FmiThreeWorkerRequestKind.START:
            return self._handle_start(request)
        elif request.kind == FmiThreeWorkerRequestKind.INITIALIZE:
            return self._handle_initialization(request)
        elif request.kind == FmiThreeWorkerRequestKind.CONFIGURE_FLOAT64:
            return self._handle_configuration(request)
        elif request.kind == FmiThreeWorkerRequestKind.CONFIGURE_UINT64:
            return self._handle_configuration_uint64(request)
        elif request.kind == FmiThreeWorkerRequestKind.SET_FLOAT64:
            return self._handle_set_float64(request)
        elif request.kind == FmiThreeWorkerRequestKind.GET_FLOAT64:
            return self._handle_get_float64(request)
        elif request.kind == FmiThreeWorkerRequestKind.SET_INT32:
            return self._handle_set_int32(request)
        elif request.kind == FmiThreeWorkerRequestKind.GET_INT32:
            return self._handle_get_int32(request)
        elif request.kind == FmiThreeWorkerRequestKind.DO_STEP:
            return self._handle_do_step(request)
        elif request.kind == FmiThreeWorkerRequestKind.SET_TIME:
            return self._handle_set_time(request)
        elif request.kind == FmiThreeWorkerRequestKind.SET_CONTINUOUS_STATES:
            return self._handle_set_continuous_states(request)
        elif request.kind in (
            FmiThreeWorkerRequestKind.GET_CONTINUOUS_STATES,
            FmiThreeWorkerRequestKind.GET_DERIVATIVES,
            FmiThreeWorkerRequestKind.GET_EVENT_INDICATORS,
            FmiThreeWorkerRequestKind.GET_NOMINALS_OF_CONTINUOUS_STATES,
        ):
            return self._handle_get_continuous_values(
                request,
                request_kind=request.kind,
            )
        elif request.kind == FmiThreeWorkerRequestKind.COMPLETED_INTEGRATOR_STEP:
            return self._handle_completed_integrator_step(request)
        elif request.kind == FmiThreeWorkerRequestKind.ENTER_EVENT_MODE:
            return self._handle_enter_event_mode(request)
        elif request.kind == FmiThreeWorkerRequestKind.UPDATE_DISCRETE_STATES:
            return self._handle_update_discrete_states(request)
        elif request.kind == FmiThreeWorkerRequestKind.ENTER_CONTINUOUS_TIME_MODE:
            return self._handle_enter_continuous_time_mode(request)
        elif request.kind == FmiThreeWorkerRequestKind.SAVE_CHECKPOINT:
            return self._handle_save_checkpoint(request)
        elif request.kind == FmiThreeWorkerRequestKind.RESTORE_CHECKPOINT:
            return self._handle_restore_checkpoint(request)
        elif request.kind == FmiThreeWorkerRequestKind.DISCARD_CHECKPOINT:
            return self._handle_discard_checkpoint(request)
        elif request.kind == FmiThreeWorkerRequestKind.EVALUATE_MODEL_EXCHANGE:
            return self._handle_evaluate_model_exchange(request)
        elif request.kind == FmiThreeWorkerRequestKind.CLOSE:
            return self._handle_close(request)
        else:
            return self._error_response(
                request.request_id,
                FmiThreeWorkerFailureKind.PROTOCOL,
                "FMI 3 worker request kind is not implemented",
            )

    def release(self) -> bool:
        """Release native ownership according to the last completed state.

        :return: ``True`` when every required native cleanup call succeeded.
        """

        release_succeeded: bool = True
        runtime: FMU3Slave | FMU3Model | None = self.runtime
        if runtime is not None:
            if self._release_checkpoint_state():
                pass
            else:
                release_succeeded = False
            if self.state in (
                _FmiThreeWorkerState.INITIALIZED,
                _FmiThreeWorkerState.INPUT_VALUES_PENDING_STEP,
                _FmiThreeWorkerState.TERMINATION_REQUESTED,
                _FmiThreeWorkerState.CONTINUOUS_TIME,
                _FmiThreeWorkerState.EVENT_MODE_REQUESTED,
                _FmiThreeWorkerState.EVENT_MODE,
            ):
                try:
                    runtime.terminate()
                except Exception:
                    release_succeeded = False
            else:
                pass
            try:
                runtime.freeInstance()
            except Exception:
                release_succeeded = False
        else:
            pass
        self.runtime = None
        self.state = _FmiThreeWorkerState.CLOSED
        return release_succeeded


def run_fmi_three_worker(
    connection: Connection,
    maximum_frame_size: int,
    maximum_float64_values_per_request: int,
) -> None:
    """Run one isolated, fail-stop FMI 3 numeric worker.

    Malformed transport frames cannot be correlated safely and therefore close
    the private channel without a response. Decoded requests receive exactly
    one typed response. Any error response ends the worker after native cleanup.

    :param connection: Child endpoint of a dedicated multiprocessing pipe.
    :param maximum_frame_size: Positive bound for every request and response.
    :param maximum_float64_values_per_request: Established shared bound for
        Float64 values and scalar UInt64 Configuration Mode values.
    :return: None.
    """

    worker_session: _FmiThreeWorkerSession = (
        _FmiThreeWorkerSession(maximum_float64_values_per_request)
    )
    worker_finished: bool = False
    try:
        while not worker_finished:
            request_frame: bytes = receive_fmi_three_worker_frame(
                connection=connection,
                maximum_frame_size=maximum_frame_size,
            )
            request: FmiThreeWorkerRequest = decode_fmi_three_worker_request(
                frame=request_frame,
                maximum_frame_size=maximum_frame_size,
                maximum_float64_values_per_request=(
                    maximum_float64_values_per_request
                ),
            )
            response: FmiThreeWorkerResponse = worker_session.handle_request(request)
            response_frame: bytes = encode_fmi_three_worker_response(
                response=response,
                maximum_frame_size=maximum_frame_size,
                maximum_float64_values_per_request=(
                    maximum_float64_values_per_request
                ),
            )
            send_fmi_three_worker_frame(
                connection=connection,
                frame=response_frame,
                maximum_frame_size=maximum_frame_size,
            )
            worker_finished = (
                response.kind == FmiThreeWorkerResponseKind.CLOSED
                or response.kind == FmiThreeWorkerResponseKind.ERROR
            )
    except (EOFError, OSError, ValueError):
        pass
    finally:
        release_succeeded: bool = worker_session.release()
        connection.close()
        if release_succeeded:
            pass
        else:
            raise RuntimeError(
                "FMI 3 worker could not release native ownership during shutdown"
            )
