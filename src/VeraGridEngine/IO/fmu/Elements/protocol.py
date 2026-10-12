# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Bounded binary messages for the isolated FMI 3 runtime worker."""

from __future__ import annotations
from VeraGridEngine.enumerations import FmiThreeWorkerFailureKind, FmiThreeWorkerFrameDirection, FmiThreeWorkerProtocolVersion, FmiThreeWorkerRequestKind, FmiThreeWorkerResponseKind

import math
from multiprocessing.connection import Connection
from pathlib import Path
import struct

from VeraGridEngine.IO.fmu.Elements.inspection import FmuInspectionReceipt
from VeraGridEngine.IO.fmu.profile import (
    FmiThreeWorkerFloat64Profile,
)
from VeraGridEngine.enumerations import FmuInterfaceMode, FmuSourceKind












class FmiThreeWorkerStagingIdentity:
    """Identify the complete staged FMU tree expected by the parent.

    :param tree_sha256: SHA-256 of the inspected staged directory tree.
    :param model_description_sha256: SHA-256 of ``modelDescription.xml``.
    :param tree_size: Combined staged file size in bytes.
    :param entry_count: Number of inspected staged entries.
    """

    __slots__ = (
        "tree_sha256",
        "model_description_sha256",
        "tree_size",
        "entry_count",
    )

    def __init__(
        self,
        tree_sha256: str,
        model_description_sha256: str,
        tree_size: int,
        entry_count: int,
    ) -> None:
        """Validate and store the expected staging identity.

        :param tree_sha256: SHA-256 of the inspected staged directory tree.
        :param model_description_sha256: SHA-256 of ``modelDescription.xml``.
        :param tree_size: Combined staged file size in bytes.
        :param entry_count: Number of inspected staged entries.
        :return: None.
        """

        _validate_sha256_digest(tree_sha256, "staged tree digest")
        _validate_sha256_digest(
            model_description_sha256,
            "model-description digest",
        )
        if tree_size >= 0 and tree_size <= 18446744073709551615:
            pass
        else:
            raise ValueError("FMI 3 worker staged tree size is outside UInt64")
        if entry_count > 0 and entry_count <= 4294967295:
            pass
        else:
            raise ValueError("FMI 3 worker staged entry count is outside positive UInt32")
        self.tree_sha256: str = tree_sha256
        self.model_description_sha256: str = model_description_sha256
        self.tree_size: int = tree_size
        self.entry_count: int = entry_count


class FmiThreeWorkerStartRequest:
    """Describe the inspected FMI 3 instance that a worker may construct.

    :param extracted_fmu_directory: Private staged FMU directory.
    :param staging_identity: Expected identity re-inspected before native load.
    :param instantiation_token: Exact FMI 3 instantiation token.
    :param model_identifier: Exact selected-interface model identifier.
    :param instance_name: Stable name for the native FMU instance.
    :param interface_mode: Selected Model Exchange or Co-Simulation interface.
    :param float64_profile: Scalar, constant-array, or configurable-array
        profile.
    :param visible: Whether the native FMU may expose its own interface.
    :param debug_logging: Whether FMI debug logging is requested.
    :param early_return_allowed: Whether the importer can consume a partial
        Co-Simulation step.
    """

    __slots__ = (
        "extracted_fmu_directory",
        "staging_identity",
        "instantiation_token",
        "model_identifier",
        "instance_name",
        "interface_mode",
        "float64_profile",
        "visible",
        "debug_logging",
        "early_return_allowed",
    )

    def __init__(
        self,
        extracted_fmu_directory: Path,
        staging_identity: FmiThreeWorkerStagingIdentity,
        instantiation_token: str,
        model_identifier: str,
        instance_name: str,
        interface_mode: FmuInterfaceMode,
        float64_profile: FmiThreeWorkerFloat64Profile,
        visible: bool,
        debug_logging: bool,
        early_return_allowed: bool = False,
    ) -> None:
        """Validate and store inputs required before native construction.

        :param extracted_fmu_directory: Private staged FMU directory.
        :param staging_identity: Expected identity re-inspected before native load.
        :param instantiation_token: Exact FMI 3 instantiation token.
        :param model_identifier: Exact selected-interface model identifier.
        :param instance_name: Stable name for the native FMU instance.
        :param interface_mode: Selected Model Exchange or Co-Simulation interface.
        :param float64_profile: Scalar, constant-array, or configurable-array
            profile.
        :param visible: Whether the native FMU may expose its own interface.
        :param debug_logging: Whether FMI debug logging is requested.
        :param early_return_allowed: Whether the importer can consume a partial
            Co-Simulation step.
        :return: None.
        """

        if extracted_fmu_directory.is_absolute():
            pass
        else:
            raise ValueError("FMI 3 worker extracted FMU directory must be absolute")
        _validate_required_text(instantiation_token, "instantiation token")
        _validate_required_text(model_identifier, "model identifier")
        _validate_required_text(instance_name, "instance name")
        if interface_mode in (
            FmuInterfaceMode.MODEL_EXCHANGE,
            FmuInterfaceMode.CO_SIMULATION,
        ):
            pass
        else:
            raise ValueError("FMI 3 worker interface mode is invalid")
        if isinstance(float64_profile, FmiThreeWorkerFloat64Profile):
            pass
        else:
            raise ValueError("FMI 3 worker Float64 profile is invalid")
        if (
            interface_mode == FmuInterfaceMode.CO_SIMULATION
            or not early_return_allowed
        ):
            pass
        else:
            raise ValueError(
                "FMI 3 worker Model Exchange cannot allow Co-Simulation early return"
            )
        self.extracted_fmu_directory: Path = extracted_fmu_directory
        self.staging_identity: FmiThreeWorkerStagingIdentity = staging_identity
        self.instantiation_token: str = instantiation_token
        self.model_identifier: str = model_identifier
        self.instance_name: str = instance_name
        self.interface_mode: FmuInterfaceMode = interface_mode
        self.float64_profile: FmiThreeWorkerFloat64Profile = float64_profile
        self.visible: bool = visible
        self.debug_logging: bool = debug_logging
        self.early_return_allowed: bool = early_return_allowed


class FmiThreeWorkerInitializationRequest:
    """Describe a validated FMI 3 initialization transition.

    :param start_time: Finite simulation start time.
    :param stop_time: Optional finite stop time greater than start time.
    :param relative_tolerance: Optional finite positive relative tolerance.
    :param initial_float64_value_references: Ordered scalar or array assignments applied
        inside Initialization Mode, or an empty tuple.
    :param initial_float64_values: Concatenated finite values for the Float64 references.
    :param initial_int32_value_references: Ordered scalar Int32 assignments.
    :param initial_int32_values: Signed values aligned with the Int32 references.
    :param maximum_value_count: Positive caller-owned serialized value limit.
    """

    __slots__ = (
        "start_time",
        "stop_time",
        "relative_tolerance",
        "initial_float64_value_references",
        "initial_float64_values",
        "initial_int32_value_references",
        "initial_int32_values",
    )

    def __init__(
        self,
        start_time: float,
        stop_time: float | None,
        relative_tolerance: float | None,
        initial_float64_value_references: tuple[int, ...],
        initial_float64_values: tuple[float, ...],
        initial_int32_value_references: tuple[int, ...],
        initial_int32_values: tuple[int, ...],
        maximum_value_count: int,
    ) -> None:
        """Validate and store initialization values without runtime defaults.

        :param start_time: Finite simulation start time.
        :param stop_time: Optional finite stop time greater than start time.
        :param relative_tolerance: Optional finite positive relative tolerance.
        :param initial_float64_value_references: Ordered unique Float64 references.
        :param initial_float64_values: Concatenated finite Float64 values.
        :param initial_int32_value_references: Ordered unique scalar Int32 references.
        :param initial_int32_values: Signed values aligned with Int32 references.
        :param maximum_value_count: Positive caller-owned serialized value limit.
        :return: None.
        """

        validated_start_time: float = float(start_time)
        if math.isfinite(validated_start_time):
            pass
        else:
            raise ValueError("FMI 3 worker start time must be finite")
        if stop_time is None:
            validated_stop_time: float | None = None
        else:
            validated_stop_time = float(stop_time)
            if math.isfinite(validated_stop_time):
                pass
            else:
                raise ValueError("FMI 3 worker stop time must be finite")
            if validated_stop_time > validated_start_time:
                pass
            else:
                raise ValueError("FMI 3 worker stop time must be greater than start time")
        if relative_tolerance is None:
            validated_relative_tolerance: float | None = None
        else:
            validated_relative_tolerance = float(relative_tolerance)
            if math.isfinite(validated_relative_tolerance):
                pass
            else:
                raise ValueError("FMI 3 worker relative tolerance must be finite")
            if validated_relative_tolerance > 0.0:
                pass
            else:
                raise ValueError("FMI 3 worker relative tolerance must be positive")
        self.start_time: float = validated_start_time
        self.stop_time: float | None = validated_stop_time
        self.relative_tolerance: float | None = validated_relative_tolerance
        validate_fmi_three_worker_float64_value_limit(maximum_value_count)
        if len(initial_float64_value_references) == 0:
            if len(initial_float64_values) == 0:
                pass
            else:
                raise ValueError(
                    "FMI 3 worker initial Float64 references and values must align"
                )
        else:
            _validate_numeric_value_references(
                initial_float64_value_references,
                maximum_value_count,
            )
            if len(initial_float64_values) <= maximum_value_count:
                pass
            else:
                raise ValueError(
                    "FMI 3 worker initial Float64 value count is outside its bound"
                )
        if len(initial_int32_value_references) == 0:
            if len(initial_int32_values) == 0:
                pass
            else:
                raise ValueError(
                    "FMI 3 worker initial Int32 references and values must align"
                )
        else:
            _validate_numeric_value_references(
                initial_int32_value_references,
                maximum_value_count,
            )
            if len(initial_int32_values) == len(initial_int32_value_references):
                pass
            else:
                raise ValueError(
                    "FMI 3 worker initial Int32 references and values must align"
                )
        combined_reference_count: int = (
            len(initial_float64_value_references)
            + len(initial_int32_value_references)
        )
        combined_value_count: int = (
            len(initial_float64_values) + len(initial_int32_values)
        )
        if (
            combined_reference_count <= maximum_value_count
            and combined_value_count <= maximum_value_count
        ):
            pass
        else:
            raise ValueError(
                "FMI 3 worker combined initialization count is outside its bound"
            )
        self.initial_float64_value_references: tuple[int, ...] = tuple(
            initial_float64_value_references
        )
        self.initial_float64_values: tuple[float, ...] = (
            _validate_finite_float64_values(initial_float64_values)
        )
        self.initial_int32_value_references: tuple[int, ...] = tuple(
            initial_int32_value_references
        )
        self.initial_int32_values: tuple[int, ...] = _validate_int32_values(
            initial_int32_values
        )


def validate_fmi_three_worker_float64_value_limit(
    maximum_value_count: int,
) -> None:
    """Require the established numeric-value limit within its protocol ceiling.

    :param maximum_value_count: Caller-owned serialized-value count limit.
    :return: None.
    """

    if maximum_value_count > 0 and maximum_value_count <= 16384:
        pass
    else:
        raise ValueError(
            "FMI 3 worker maximum numeric value count must be within 1 and 16384"
        )


def _validate_numeric_value_references(
    value_references: tuple[int, ...],
    maximum_value_count: int,
) -> None:
    """Validate one bounded, non-empty sequence of unique UInt32 references.

    :param value_references: Ordered scalar or array value references to validate.
    :param maximum_value_count: Positive caller-owned serialized-value limit.
    :return: None.
    """

    validate_fmi_three_worker_float64_value_limit(maximum_value_count)
    if len(value_references) > 0 and len(value_references) <= maximum_value_count:
        pass
    else:
        raise ValueError("FMI 3 worker numeric value count is outside its bound")
    observed_references: set[int] = set()
    value_reference: int
    for value_reference in value_references:
        if value_reference >= 0 and value_reference <= 4294967295:
            pass
        else:
            raise ValueError("FMI 3 worker value reference is outside UInt32")
        if value_reference in observed_references:
            raise ValueError("FMI 3 worker value references must be unique")
        else:
            observed_references.add(value_reference)


def _validate_finite_float64_values(values: tuple[float, ...]) -> tuple[float, ...]:
    """Normalize and validate finite Float64 values for the initial profile.

    :param values: Ordered concatenated values to normalize.
    :return: Finite floating-point values in the original order.
    """

    normalized_values: list[float] = [0.0] * len(values)
    value_index: int
    for value_index in range(len(values)):
        normalized_value: float = float(values[value_index])
        if math.isfinite(normalized_value):
            normalized_values[value_index] = normalized_value
        else:
            raise ValueError("FMI 3 worker Float64 values must be finite")
    return tuple(normalized_values)


def _validate_int32_values(values: tuple[int, ...]) -> tuple[int, ...]:
    """Validate Python integer identity and signed Int32 bounds.

    :param values: Ordered scalar values to validate.
    :return: Values preserved in their original order.
    :raises ValueError: If a value is Boolean, non-integer, or out of range.
    """

    validated_values: list[int] = [0] * len(values)
    value_index: int
    for value_index in range(len(values)):
        value: int = values[value_index]
        if type(value) is int:
            if -2147483648 <= value <= 2147483647:
                validated_values[value_index] = value
            else:
                raise ValueError("FMI 3 worker value is outside signed Int32")
        else:
            raise ValueError("FMI 3 worker Int32 values must be Python int values")
    return tuple(validated_values)


class FmiThreeWorkerSetFloat64Request:
    """Describe one bounded write to scalar or array FMI 3 Float64 variables.

    :param value_references: Ordered unique scalar or array value references.
    :param values: Concatenated finite values for the referenced variables.
    :param maximum_value_count: Positive caller-owned serialized-value limit.
    """

    __slots__ = ("value_references", "values")

    def __init__(
        self,
        value_references: tuple[int, ...],
        values: tuple[float, ...],
        maximum_value_count: int,
    ) -> None:
        """Validate and store one Float64 write request.

        :param value_references: Ordered unique scalar or array value references.
        :param values: Concatenated finite values for the references.
        :param maximum_value_count: Positive caller-owned serialized-value limit.
        :return: None.
        """

        _validate_numeric_value_references(value_references, maximum_value_count)
        if len(values) <= maximum_value_count:
            pass
        else:
            raise ValueError(
                "FMI 3 worker serialized Float64 value count is outside its bound"
            )
        self.value_references: tuple[int, ...] = tuple(value_references)
        self.values: tuple[float, ...] = _validate_finite_float64_values(values)


class FmiThreeWorkerConfigureFloat64Request:
    """Describe structural Float64 assignments for one Configuration Mode.

    :param value_references: Ordered unique structural-parameter references.
    :param values: Concatenated finite values for the referenced variables.
    :param maximum_value_count: Positive caller-owned serialized-value limit.
    """

    __slots__ = ("value_references", "values")

    def __init__(
        self,
        value_references: tuple[int, ...],
        values: tuple[float, ...],
        maximum_value_count: int,
    ) -> None:
        """Validate and store one Configuration Mode assignment request.

        :param value_references: Ordered unique structural-parameter references.
        :param values: Concatenated finite values for the references.
        :param maximum_value_count: Positive caller-owned serialized-value limit.
        :return: None.
        """

        _validate_numeric_value_references(value_references, maximum_value_count)
        if len(values) <= maximum_value_count:
            pass
        else:
            raise ValueError(
                "FMI 3 worker serialized configuration value count is outside "
                "its bound"
            )
        self.value_references: tuple[int, ...] = tuple(value_references)
        self.values: tuple[float, ...] = _validate_finite_float64_values(values)


class FmiThreeWorkerConfigureUInt64Request:
    """Describe scalar UInt64 assignments for one Configuration Mode.

    :param value_references: Ordered unique structural-parameter references.
    :param values: UInt64 values aligned one-to-one with the references.
    :param maximum_value_count: Positive caller-owned scalar-value limit.
    """

    __slots__ = ("value_references", "values")

    def __init__(
        self,
        value_references: tuple[int, ...],
        values: tuple[int, ...],
        maximum_value_count: int,
    ) -> None:
        """Validate and store one UInt64 Configuration Mode request.

        :param value_references: Ordered unique structural-parameter references.
        :param values: UInt64 values aligned one-to-one with the references.
        :param maximum_value_count: Positive caller-owned scalar-value limit.
        :return: None.
        """

        _validate_numeric_value_references(value_references, maximum_value_count)
        if len(values) == len(value_references):
            pass
        else:
            raise ValueError(
                "FMI 3 worker UInt64 references and values must align"
            )
        validated_values: list[int] = [0] * len(values)
        value_index: int
        for value_index in range(len(values)):
            value: int = values[value_index]
            value_is_uint64: bool = (
                isinstance(value, int)
                and not isinstance(value, bool)
                and value >= 0
                and value <= 18446744073709551615
            )
            if value_is_uint64:
                validated_values[value_index] = value
            else:
                raise ValueError("FMI 3 worker value is outside UInt64")
        self.value_references: tuple[int, ...] = tuple(value_references)
        self.values: tuple[int, ...] = tuple(validated_values)


class FmiThreeWorkerGetFloat64Request:
    """Describe one bounded read of scalar or array FMI 3 Float64 variables.

    :param value_references: Ordered unique scalar or array value references.
    :param serialized_value_count: Number of concatenated values to return.
    :param maximum_value_count: Positive caller-owned serialized-value limit.
    """

    __slots__ = ("value_references", "serialized_value_count")

    def __init__(
        self,
        value_references: tuple[int, ...],
        serialized_value_count: int,
        maximum_value_count: int,
    ) -> None:
        """Validate and store one Float64 read request.

        :param value_references: Ordered unique scalar or array value references.
        :param serialized_value_count: Number of concatenated values to return.
        :param maximum_value_count: Positive caller-owned serialized-value limit.
        :return: None.
        """

        _validate_numeric_value_references(value_references, maximum_value_count)
        if serialized_value_count >= 0 and serialized_value_count <= maximum_value_count:
            pass
        else:
            raise ValueError(
                "FMI 3 worker serialized Float64 value count is outside its bound"
            )
        self.value_references: tuple[int, ...] = tuple(value_references)
        self.serialized_value_count: int = serialized_value_count


class FmiThreeWorkerSetInt32Request:
    """Describe one bounded write to scalar FMI 3 Int32 variables.

    :param value_references: Ordered unique scalar Int32 references.
    :param values: Signed values aligned one-to-one with the references.
    :param maximum_value_count: Positive caller-owned numeric count limit.
    """

    __slots__ = ("value_references", "values")

    def __init__(
        self,
        value_references: tuple[int, ...],
        values: tuple[int, ...],
        maximum_value_count: int,
    ) -> None:
        """Validate and store one scalar Int32 write request.

        :param value_references: Ordered unique scalar Int32 references.
        :param values: Signed values aligned with the references.
        :param maximum_value_count: Positive caller-owned numeric count limit.
        :return: None.
        """

        _validate_numeric_value_references(value_references, maximum_value_count)
        if len(values) == len(value_references):
            pass
        else:
            raise ValueError("FMI 3 worker Int32 references and values must align")
        self.value_references: tuple[int, ...] = tuple(value_references)
        self.values: tuple[int, ...] = _validate_int32_values(values)


class FmiThreeWorkerGetInt32Request:
    """Describe one bounded read of scalar FMI 3 Int32 variables.

    :param value_references: Ordered unique scalar Int32 references.
    :param maximum_value_count: Positive caller-owned numeric count limit.
    """

    __slots__ = ("value_references",)

    def __init__(
        self,
        value_references: tuple[int, ...],
        maximum_value_count: int,
    ) -> None:
        """Validate and store one scalar Int32 read request.

        :param value_references: Ordered unique scalar Int32 references.
        :param maximum_value_count: Positive caller-owned numeric count limit.
        :return: None.
        """

        _validate_numeric_value_references(value_references, maximum_value_count)
        self.value_references: tuple[int, ...] = tuple(value_references)


class FmiThreeWorkerInt32Values:
    """Own one bounded ordered scalar Int32 response body.

    :param values: Signed scalar values transported in protocol order.
    :param maximum_value_count: Positive caller-owned numeric count limit.
    """

    __slots__ = ("values",)

    def __init__(
        self,
        values: tuple[int, ...],
        maximum_value_count: int,
    ) -> None:
        """Validate and store transported Int32 values.

        :param values: Signed scalar values transported in protocol order.
        :param maximum_value_count: Positive caller-owned numeric count limit.
        :return: None.
        """

        validate_fmi_three_worker_float64_value_limit(maximum_value_count)
        if len(values) <= maximum_value_count:
            self.values: tuple[int, ...] = _validate_int32_values(values)
        else:
            raise ValueError("FMI 3 worker Int32 response count is outside its bound")


class FmiThreeWorkerDoStepRequest:
    """Describe one bounded FMI 3 Co-Simulation step.

    :param current_communication_point: Importer communication time.
    :param communication_step_size: Positive requested step size.
    :param no_set_fmu_state_prior_to_current_point: FMI rollback guarantee.
    """

    __slots__ = (
        "current_communication_point",
        "communication_step_size",
        "no_set_fmu_state_prior_to_current_point",
    )

    def __init__(
        self,
        current_communication_point: float,
        communication_step_size: float,
        no_set_fmu_state_prior_to_current_point: bool,
    ) -> None:
        """Validate and store one Co-Simulation step request.

        :param current_communication_point: Importer communication time.
        :param communication_step_size: Positive requested step size.
        :param no_set_fmu_state_prior_to_current_point: FMI rollback guarantee.
        :return: None.
        """

        validated_communication_point: float = float(current_communication_point)
        validated_step_size: float = float(communication_step_size)
        if math.isfinite(validated_communication_point):
            pass
        else:
            raise ValueError("FMI 3 worker communication point must be finite")
        if math.isfinite(validated_step_size) and validated_step_size > 0.0:
            pass
        else:
            raise ValueError("FMI 3 worker communication step size must be finite and positive")
        # Reject requests whose positive mathematical step cannot produce a
        # later finite Float64 communication point for the native transition.
        requested_endpoint: float = (
            validated_communication_point + validated_step_size
        )
        if (
            math.isfinite(requested_endpoint)
            and requested_endpoint > validated_communication_point
        ):
            pass
        else:
            raise ValueError(
                "FMI 3 worker communication endpoint must be finite and advance time"
            )
        self.current_communication_point: float = validated_communication_point
        self.communication_step_size: float = validated_step_size
        self.no_set_fmu_state_prior_to_current_point: bool = (
            no_set_fmu_state_prior_to_current_point
        )


class FmiThreeWorkerSetTimeRequest:
    """Describe one finite Model Exchange time assignment.

    :param time_value: Finite independent-variable value for the FMU.
    """

    __slots__ = ("time_value",)

    def __init__(self, time_value: float) -> None:
        """Validate and store one Model Exchange time value.

        :param time_value: Independent-variable value for the FMU.
        :return: None.
        """

        validated_time_value: float = float(time_value)
        if math.isfinite(validated_time_value):
            pass
        else:
            raise ValueError("FMI 3 worker Model Exchange time must be finite")
        self.time_value: float = validated_time_value


class FmiThreeWorkerCompletedIntegratorStepRequest:
    """Describe one Model Exchange completed-integrator-step notification.

    :param no_set_fmu_state_prior_to_current_point: Host rollback guarantee.
    """

    __slots__ = ("no_set_fmu_state_prior_to_current_point",)

    def __init__(
        self,
        no_set_fmu_state_prior_to_current_point: bool,
    ) -> None:
        """Store the explicit rollback guarantee for the native notification.

        :param no_set_fmu_state_prior_to_current_point: Whether the host will
            avoid restoring an FMU state before the current point.
        :return: None.
        """

        self.no_set_fmu_state_prior_to_current_point: bool = (
            no_set_fmu_state_prior_to_current_point
        )


class FmiThreeWorkerFloat64Values:
    """Own one bounded ordered Float64 protocol body.

    :param values: Finite scalar values transported in protocol order.
    :param maximum_value_count: Positive caller-owned scalar count limit.
    """

    __slots__ = ("values",)

    def __init__(
        self,
        values: tuple[float, ...],
        maximum_value_count: int,
    ) -> None:
        """Validate and store transported Float64 values.

        :param values: Finite scalar values transported in protocol order.
        :param maximum_value_count: Positive caller-owned scalar count limit.
        :return: None.
        """

        validate_fmi_three_worker_float64_value_limit(maximum_value_count)
        if len(values) <= maximum_value_count:
            pass
        else:
            raise ValueError("FMI 3 worker Float64 response count is outside its bound")
        self.values: tuple[float, ...] = _validate_finite_float64_values(values)


class FmiThreeWorkerModelExchangeEvaluationRequest:
    """Own one atomic Model Exchange evaluation request.

    :param set_time: Finite independent-variable assignment.
    :param continuous_states: Complete externally integrated state vector.
    :param set_float64: Optional bounded input assignment.
    :param get_float64: Optional bounded readable-value request.
    """

    __slots__ = (
        "set_time",
        "continuous_states",
        "set_float64",
        "get_float64",
    )

    def __init__(
        self,
        set_time: FmiThreeWorkerSetTimeRequest,
        continuous_states: FmiThreeWorkerFloat64Values,
        set_float64: FmiThreeWorkerSetFloat64Request | None,
        get_float64: FmiThreeWorkerGetFloat64Request | None,
    ) -> None:
        """Store the already validated native-call sequence.

        Empty input and readable layouts are represented by ``None`` so an
        encoded zero reference count has one canonical meaning.

        :param set_time: Finite independent-variable assignment.
        :param continuous_states: Complete externally integrated state vector.
        :param set_float64: Optional bounded input assignment.
        :param get_float64: Optional bounded readable-value request.
        :return: None.
        """

        self.set_time: FmiThreeWorkerSetTimeRequest = set_time
        self.continuous_states: FmiThreeWorkerFloat64Values = continuous_states
        self.set_float64: FmiThreeWorkerSetFloat64Request | None = set_float64
        self.get_float64: FmiThreeWorkerGetFloat64Request | None = get_float64


class FmiThreeWorkerModelExchangeEvaluationResult:
    """Own the two independently bounded Model Exchange result vectors.

    :param derivatives: Continuous-state derivatives in state order.
    :param readable_values: Consumer values in binding-layout order.
    """

    __slots__ = ("derivatives", "readable_values")

    def __init__(
        self,
        derivatives: FmiThreeWorkerFloat64Values,
        readable_values: FmiThreeWorkerFloat64Values,
    ) -> None:
        """Store one atomic evaluation result without joining its vectors.

        :param derivatives: Continuous-state derivatives in state order.
        :param readable_values: Consumer values in binding-layout order.
        :return: None.
        """

        self.derivatives: FmiThreeWorkerFloat64Values = derivatives
        self.readable_values: FmiThreeWorkerFloat64Values = readable_values


class FmiThreeWorkerCompletedIntegratorStepResult:
    """Represent the exact successful result of ``fmi3CompletedIntegratorStep``.

    :param enter_event_mode: Whether the FMU requests Event Mode.
    :param terminate_simulation: Whether the FMU requests termination.
    """

    __slots__ = ("enter_event_mode", "terminate_simulation")

    def __init__(
        self,
        enter_event_mode: bool,
        terminate_simulation: bool,
    ) -> None:
        """Store the two native lifecycle flags without interpreting them.

        :param enter_event_mode: Whether the FMU requests Event Mode.
        :param terminate_simulation: Whether the FMU requests termination.
        :return: None.
        """

        self.enter_event_mode: bool = enter_event_mode
        self.terminate_simulation: bool = terminate_simulation


class FmiThreeWorkerDiscreteStatesResult:
    """Represent one exact successful ``fmi3UpdateDiscreteStates`` result.

    :param discrete_states_need_update: Whether another super-dense iteration
        is required.
    :param terminate_simulation: Whether the FMU requests termination.
    :param nominals_of_continuous_states_changed: Whether state nominals changed.
    :param values_of_continuous_states_changed: Whether state values changed.
    :param next_event_time_defined: Whether the FMU scheduled a time event.
    :param next_event_time: Absolute candidate time returned by the FMU.
    """

    __slots__ = (
        "discrete_states_need_update",
        "terminate_simulation",
        "nominals_of_continuous_states_changed",
        "values_of_continuous_states_changed",
        "next_event_time_defined",
        "next_event_time",
    )

    def __init__(
        self,
        discrete_states_need_update: bool,
        terminate_simulation: bool,
        nominals_of_continuous_states_changed: bool,
        values_of_continuous_states_changed: bool,
        next_event_time_defined: bool,
        next_event_time: float,
    ) -> None:
        """Validate and retain every native discrete-state output.

        :param discrete_states_need_update: Whether another event iteration is
            required.
        :param terminate_simulation: Whether the FMU requests termination.
        :param nominals_of_continuous_states_changed: Whether state nominals changed.
        :param values_of_continuous_states_changed: Whether state values changed.
        :param next_event_time_defined: Whether a valid time event was returned.
        :param next_event_time: Absolute candidate time returned by the FMU.
        :return: None.
        """

        validated_next_event_time: float = float(next_event_time)
        if math.isfinite(validated_next_event_time):
            pass
        else:
            raise ValueError("FMI 3 worker next event time must be finite")
        self.discrete_states_need_update: bool = discrete_states_need_update
        self.terminate_simulation: bool = terminate_simulation
        self.nominals_of_continuous_states_changed: bool = (
            nominals_of_continuous_states_changed
        )
        self.values_of_continuous_states_changed: bool = (
            values_of_continuous_states_changed
        )
        self.next_event_time_defined: bool = next_event_time_defined
        self.next_event_time: float = validated_next_event_time


class FmiThreeWorkerDoStepResult:
    """Represent the exact successful outcome of ``fmi3DoStep``.

    :param event_handling_needed: Whether the FMU requests Event Mode.
    :param terminate_simulation: Whether the FMU requests termination.
    :param early_return: Whether the requested step ended early.
    :param last_successful_time: Finite internal time reported by the FMU.
    """

    __slots__ = (
        "event_handling_needed",
        "terminate_simulation",
        "early_return",
        "last_successful_time",
    )

    def __init__(
        self,
        event_handling_needed: bool,
        terminate_simulation: bool,
        early_return: bool,
        last_successful_time: float,
    ) -> None:
        """Validate and store one successful step result.

        :param event_handling_needed: Whether the FMU requests Event Mode.
        :param terminate_simulation: Whether the FMU requests termination.
        :param early_return: Whether the requested step ended early.
        :param last_successful_time: Finite internal time reported by the FMU.
        :return: None.
        """

        validated_last_successful_time: float = float(last_successful_time)
        if math.isfinite(validated_last_successful_time):
            pass
        else:
            raise ValueError("FMI 3 worker last successful time must be finite")
        self.event_handling_needed: bool = event_handling_needed
        self.terminate_simulation: bool = terminate_simulation
        self.early_return: bool = early_return
        self.last_successful_time: float = validated_last_successful_time


def validate_fmi_three_worker_completed_step(
    request: FmiThreeWorkerDoStepRequest,
    result: FmiThreeWorkerDoStepResult,
    early_return_allowed: bool,
    might_return_early_from_do_step: bool,
) -> None:
    """Validate one native step against the supported Co-Simulation profile.

    A termination request is retained as an explicit result for the importer.
    When partial-step handling was negotiated, the result may either report an
    advertised early return before the requested endpoint or a non-exact
    ``lastSuccessfulTime`` permitted by FMI 3. The strict default retains the
    exact endpoint required by the current RMS and EMT adapters.

    :param request: Validated step request that owns the expected endpoint.
    :param result: Exact output arguments returned by the native function.
    :param early_return_allowed: Whether the importer negotiated partial-step
        handling at instantiation.
    :param might_return_early_from_do_step: Whether the FMU declared that it may
        return early without an Intermediate Update request.
    :return: None.
    :raises ValueError: If the result contradicts the supported profile.
    """

    if result.event_handling_needed:
        raise ValueError(
            "FMI 3 worker step requested unsupported Event Mode handling"
        )
    else:
        pass
    requested_endpoint: float = (
        request.current_communication_point + request.communication_step_size
    )
    if result.early_return:
        if early_return_allowed:
            pass
        else:
            raise ValueError("FMI 3 worker step returned early while disabled")
        if might_return_early_from_do_step:
            pass
        else:
            raise ValueError(
                "FMI 3 worker step returned early without advertising that capability"
            )
        if (
            result.last_successful_time >= request.current_communication_point
            and result.last_successful_time < requested_endpoint
        ):
            pass
        else:
            raise ValueError(
                "FMI 3 worker early-return time is outside the requested step"
            )
    else:
        if result.last_successful_time >= request.current_communication_point:
            pass
        else:
            raise ValueError(
                "FMI 3 worker last successful time precedes the communication point"
            )
        if early_return_allowed:
            pass
        else:
            if result.last_successful_time == requested_endpoint:
                pass
            else:
                raise ValueError(
                    "FMI 3 worker last successful time differs from the requested endpoint"
                )


class FmiThreeWorkerRequest:
    """Own exactly one typed FMI 3 worker request body.

    :param request_id: Positive identifier paired with the response.
    :param kind: Requested worker operation.
    :param start: START body or ``None``.
    :param initialization: INITIALIZE body or ``None``.
    :param configuration: CONFIGURE_FLOAT64 body or ``None``.
    :param configuration_uint64: CONFIGURE_UINT64 body or ``None``.
    :param set_float64: SET_FLOAT64 body or ``None``.
    :param get_float64: GET_FLOAT64 body or ``None``.
    :param do_step: DO_STEP body or ``None``.
    :param set_time: SET_TIME body or ``None``.
    :param continuous_states: SET_CONTINUOUS_STATES body or ``None``.
    :param completed_integrator_step: COMPLETED_INTEGRATOR_STEP body or ``None``.
    :param model_exchange_evaluation: EVALUATE_MODEL_EXCHANGE body or ``None``.
    :param set_int32: SET_INT32 body or ``None``.
    :param get_int32: GET_INT32 body or ``None``.
    """

    __slots__ = (
        "request_id",
        "kind",
        "start",
        "initialization",
        "configuration",
        "configuration_uint64",
        "set_float64",
        "get_float64",
        "do_step",
        "set_time",
        "continuous_states",
        "completed_integrator_step",
        "model_exchange_evaluation",
        "set_int32",
        "get_int32",
    )

    def __init__(
        self,
        request_id: int,
        kind: FmiThreeWorkerRequestKind,
        start: FmiThreeWorkerStartRequest | None,
        initialization: FmiThreeWorkerInitializationRequest | None,
        configuration: FmiThreeWorkerConfigureFloat64Request | None = None,
        configuration_uint64: FmiThreeWorkerConfigureUInt64Request | None = None,
        set_float64: FmiThreeWorkerSetFloat64Request | None = None,
        get_float64: FmiThreeWorkerGetFloat64Request | None = None,
        do_step: FmiThreeWorkerDoStepRequest | None = None,
        set_time: FmiThreeWorkerSetTimeRequest | None = None,
        continuous_states: FmiThreeWorkerFloat64Values | None = None,
        completed_integrator_step: (
            FmiThreeWorkerCompletedIntegratorStepRequest | None
        ) = None,
        model_exchange_evaluation: (
            FmiThreeWorkerModelExchangeEvaluationRequest | None
        ) = None,
        set_int32: FmiThreeWorkerSetInt32Request | None = None,
        get_int32: FmiThreeWorkerGetInt32Request | None = None,
    ) -> None:
        """Validate and store one request envelope.

        :param request_id: Positive identifier paired with the response.
        :param kind: Requested worker operation.
        :param start: START body or ``None``.
        :param initialization: INITIALIZE body or ``None``.
        :param configuration: CONFIGURE_FLOAT64 body or ``None``.
        :param configuration_uint64: CONFIGURE_UINT64 body or ``None``.
        :param set_float64: SET_FLOAT64 body or ``None``.
        :param get_float64: GET_FLOAT64 body or ``None``.
        :param do_step: DO_STEP body or ``None``.
        :param set_time: SET_TIME body or ``None``.
        :param continuous_states: SET_CONTINUOUS_STATES body or ``None``.
        :param completed_integrator_step: COMPLETED_INTEGRATOR_STEP body or ``None``.
        :param model_exchange_evaluation: EVALUATE_MODEL_EXCHANGE body or
            ``None``.
        :param set_int32: SET_INT32 body or ``None``.
        :param get_int32: GET_INT32 body or ``None``.
        :return: None.
        """

        _validate_request_id(request_id)
        # Pair every body-bearing operation with its constructor argument so
        # the envelope invariant remains explicit as the protocol grows.
        body_contract: tuple[
            tuple[FmiThreeWorkerRequestKind, bool], ...
        ] = (
            (FmiThreeWorkerRequestKind.START, start is not None),
            (FmiThreeWorkerRequestKind.INITIALIZE, initialization is not None),
            (
                FmiThreeWorkerRequestKind.CONFIGURE_FLOAT64,
                configuration is not None,
            ),
            (
                FmiThreeWorkerRequestKind.CONFIGURE_UINT64,
                configuration_uint64 is not None,
            ),
            (FmiThreeWorkerRequestKind.SET_FLOAT64, set_float64 is not None),
            (FmiThreeWorkerRequestKind.GET_FLOAT64, get_float64 is not None),
            (FmiThreeWorkerRequestKind.DO_STEP, do_step is not None),
            (FmiThreeWorkerRequestKind.SET_TIME, set_time is not None),
            (
                FmiThreeWorkerRequestKind.SET_CONTINUOUS_STATES,
                continuous_states is not None,
            ),
            (
                FmiThreeWorkerRequestKind.COMPLETED_INTEGRATOR_STEP,
                completed_integrator_step is not None,
            ),
            (
                FmiThreeWorkerRequestKind.EVALUATE_MODEL_EXCHANGE,
                model_exchange_evaluation is not None,
            ),
            (FmiThreeWorkerRequestKind.SET_INT32, set_int32 is not None),
            (FmiThreeWorkerRequestKind.GET_INT32, get_int32 is not None),
        )
        request_is_valid: bool = True
        body_kind: FmiThreeWorkerRequestKind
        body_is_present: bool
        body_matches_kind: bool
        for body_kind, body_is_present in body_contract:
            body_matches_kind = body_is_present == (kind == body_kind)
            request_is_valid = request_is_valid and body_matches_kind
        if request_is_valid:
            pass
        else:
            raise ValueError("FMI 3 worker request body does not match its kind")
        self.request_id: int = request_id
        self.kind: FmiThreeWorkerRequestKind = kind
        self.start: FmiThreeWorkerStartRequest | None = start
        self.initialization: FmiThreeWorkerInitializationRequest | None = initialization
        self.configuration: FmiThreeWorkerConfigureFloat64Request | None = (
            configuration
        )
        self.configuration_uint64: FmiThreeWorkerConfigureUInt64Request | None = (
            configuration_uint64
        )
        self.set_float64: FmiThreeWorkerSetFloat64Request | None = set_float64
        self.get_float64: FmiThreeWorkerGetFloat64Request | None = get_float64
        self.do_step: FmiThreeWorkerDoStepRequest | None = do_step
        self.set_time: FmiThreeWorkerSetTimeRequest | None = set_time
        self.continuous_states: FmiThreeWorkerFloat64Values | None = (
            continuous_states
        )
        self.completed_integrator_step: (
            FmiThreeWorkerCompletedIntegratorStepRequest | None
        ) = completed_integrator_step
        self.model_exchange_evaluation: (
            FmiThreeWorkerModelExchangeEvaluationRequest | None
        ) = model_exchange_evaluation
        self.set_int32: FmiThreeWorkerSetInt32Request | None = set_int32
        self.get_int32: FmiThreeWorkerGetInt32Request | None = get_int32


class FmiThreeWorkerResponse:
    """Own one typed response without transporting an exception object.

    :param request_id: Identifier copied from the matching request.
    :param kind: Worker outcome.
    :param failure_kind: Stable error category or ``None`` for success.
    :param error_message: Bounded diagnostic text or ``None`` for success.
    :param float64_values: FLOAT64_VALUES body or ``None``.
    :param do_step_result: STEP_COMPLETED body or ``None``.
    :param completed_integrator_step_result: INTEGRATOR_STEP_COMPLETED body or
        ``None``.
    :param discrete_states_result: DISCRETE_STATES_UPDATED body or ``None``.
    :param model_exchange_evaluation_result: MODEL_EXCHANGE_EVALUATED body or
        ``None``.
    :param int32_values: INT32_VALUES body or ``None``.
    """

    __slots__ = (
        "request_id",
        "kind",
        "failure_kind",
        "error_message",
        "float64_values",
        "do_step_result",
        "completed_integrator_step_result",
        "discrete_states_result",
        "model_exchange_evaluation_result",
        "int32_values",
    )

    def __init__(
        self,
        request_id: int,
        kind: FmiThreeWorkerResponseKind,
        failure_kind: FmiThreeWorkerFailureKind | None,
        error_message: str | None,
        float64_values: FmiThreeWorkerFloat64Values | None = None,
        do_step_result: FmiThreeWorkerDoStepResult | None = None,
        completed_integrator_step_result: (
            FmiThreeWorkerCompletedIntegratorStepResult | None
        ) = None,
        discrete_states_result: FmiThreeWorkerDiscreteStatesResult | None = None,
        model_exchange_evaluation_result: (
            FmiThreeWorkerModelExchangeEvaluationResult | None
        ) = None,
        int32_values: FmiThreeWorkerInt32Values | None = None,
    ) -> None:
        """Validate and store one response envelope.

        :param request_id: Identifier copied from the matching request.
        :param kind: Worker outcome.
        :param failure_kind: Stable error category or ``None`` for success.
        :param error_message: Bounded diagnostic text or ``None`` for success.
        :param float64_values: FLOAT64_VALUES body or ``None``.
        :param do_step_result: STEP_COMPLETED body or ``None``.
        :param completed_integrator_step_result: INTEGRATOR_STEP_COMPLETED body
            or ``None``.
        :param discrete_states_result: DISCRETE_STATES_UPDATED body or ``None``.
        :param model_exchange_evaluation_result: MODEL_EXCHANGE_EVALUATED body
            or ``None``.
        :param int32_values: INT32_VALUES body or ``None``.
        :return: None.
        """

        _validate_request_id(request_id)
        if kind == FmiThreeWorkerResponseKind.ERROR:
            response_is_valid: bool = (
                failure_kind is not None
                and error_message is not None
                and float64_values is None
                and do_step_result is None
                and completed_integrator_step_result is None
                and discrete_states_result is None
                and model_exchange_evaluation_result is None
                and int32_values is None
            )
        else:
            response_is_valid = failure_kind is None and error_message is None
            if kind in (
                FmiThreeWorkerResponseKind.FLOAT64_VALUES,
                FmiThreeWorkerResponseKind.CONTINUOUS_STATES_VALUES,
                FmiThreeWorkerResponseKind.DERIVATIVE_VALUES,
                FmiThreeWorkerResponseKind.EVENT_INDICATOR_VALUES,
                FmiThreeWorkerResponseKind.CONTINUOUS_STATE_NOMINAL_VALUES,
            ):
                response_is_valid = (
                    response_is_valid
                    and float64_values is not None
                    and do_step_result is None
                    and completed_integrator_step_result is None
                    and discrete_states_result is None
                    and model_exchange_evaluation_result is None
                    and int32_values is None
                )
            else:
                if kind == FmiThreeWorkerResponseKind.STEP_COMPLETED:
                    response_is_valid = (
                        response_is_valid
                        and float64_values is None
                        and do_step_result is not None
                        and completed_integrator_step_result is None
                        and discrete_states_result is None
                        and model_exchange_evaluation_result is None
                        and int32_values is None
                    )
                else:
                    if (
                        kind
                        == FmiThreeWorkerResponseKind.INTEGRATOR_STEP_COMPLETED
                    ):
                        response_is_valid = (
                            response_is_valid
                            and float64_values is None
                            and do_step_result is None
                            and completed_integrator_step_result is not None
                            and discrete_states_result is None
                            and model_exchange_evaluation_result is None
                            and int32_values is None
                        )
                    else:
                        if (
                            kind
                            == FmiThreeWorkerResponseKind.DISCRETE_STATES_UPDATED
                        ):
                            response_is_valid = (
                                response_is_valid
                                and float64_values is None
                                and do_step_result is None
                                and completed_integrator_step_result is None
                                and discrete_states_result is not None
                                and model_exchange_evaluation_result is None
                                and int32_values is None
                            )
                        else:
                            if (
                                kind
                                == FmiThreeWorkerResponseKind.MODEL_EXCHANGE_EVALUATED
                            ):
                                response_is_valid = (
                                    response_is_valid
                                    and float64_values is None
                                    and do_step_result is None
                                    and completed_integrator_step_result is None
                                    and discrete_states_result is None
                                    and model_exchange_evaluation_result is not None
                                    and int32_values is None
                                )
                            else:
                                if kind == FmiThreeWorkerResponseKind.INT32_VALUES:
                                    response_is_valid = (
                                        response_is_valid
                                        and float64_values is None
                                        and do_step_result is None
                                        and completed_integrator_step_result is None
                                        and discrete_states_result is None
                                        and model_exchange_evaluation_result is None
                                        and int32_values is not None
                                    )
                                else:
                                    response_is_valid = (
                                        response_is_valid
                                        and float64_values is None
                                        and do_step_result is None
                                        and completed_integrator_step_result is None
                                        and discrete_states_result is None
                                        and model_exchange_evaluation_result is None
                                        and int32_values is None
                                    )
        if response_is_valid:
            pass
        else:
            raise ValueError("FMI 3 worker response fields do not match its kind")
        self.request_id: int = request_id
        self.kind: FmiThreeWorkerResponseKind = kind
        self.failure_kind: FmiThreeWorkerFailureKind | None = failure_kind
        self.error_message: str | None = error_message
        self.float64_values: FmiThreeWorkerFloat64Values | None = float64_values
        self.do_step_result: FmiThreeWorkerDoStepResult | None = do_step_result
        self.completed_integrator_step_result: (
            FmiThreeWorkerCompletedIntegratorStepResult | None
        ) = completed_integrator_step_result
        self.discrete_states_result: FmiThreeWorkerDiscreteStatesResult | None = (
            discrete_states_result
        )
        self.model_exchange_evaluation_result: (
            FmiThreeWorkerModelExchangeEvaluationResult | None
        ) = model_exchange_evaluation_result
        self.int32_values: FmiThreeWorkerInt32Values | None = int32_values


class _FmiThreeWorkerBodyReader:
    """Read one bounded worker frame body with explicit cursor ownership.

    :param body: Binary body whose header has already been validated.
    """

    __slots__ = ("body", "offset")

    def __init__(self, body: bytes) -> None:
        """Initialize the reader at the start of one body.

        :param body: Complete binary protocol body.
        :return: None.
        """

        self.body: bytes = body
        self.offset: int = 0

    def read_unsigned_byte(self, field_name: str) -> int:
        """Read one unsigned byte or reject a truncated body.

        :param field_name: Field identified in truncation errors.
        :return: Parsed integer value.
        """

        field_end: int = self.offset + 1
        if field_end <= len(self.body):
            value: int = self.body[self.offset]
            self.offset = field_end
            return value
        else:
            raise ValueError(f"FMI 3 worker body is truncated before {field_name}")

    def read_unsigned_int(self, field_name: str) -> int:
        """Read one network-order UInt32 or reject a truncated body.

        :param field_name: Field identified in truncation errors.
        :return: Parsed integer value.
        """

        field_end: int = self.offset + 4
        if field_end <= len(self.body):
            value: int = int(struct.unpack_from("!I", self.body, self.offset)[0])
            self.offset = field_end
            return value
        else:
            raise ValueError(f"FMI 3 worker body is truncated before {field_name}")

    def read_signed_int(self, field_name: str) -> int:
        """Read one network-order Int32 or reject a truncated body.

        :param field_name: Field identified in truncation errors.
        :return: Parsed signed integer value.
        """

        field_end: int = self.offset + 4
        if field_end <= len(self.body):
            value: int = int(struct.unpack_from("!i", self.body, self.offset)[0])
            self.offset = field_end
            return value
        else:
            raise ValueError(f"FMI 3 worker body is truncated before {field_name}")

    def read_unsigned_long(self, field_name: str) -> int:
        """Read one network-order UInt64 or reject a truncated body.

        :param field_name: Field identified in truncation errors.
        :return: Parsed integer value.
        """

        field_end: int = self.offset + 8
        if field_end <= len(self.body):
            value: int = int(struct.unpack_from("!Q", self.body, self.offset)[0])
            self.offset = field_end
            return value
        else:
            raise ValueError(f"FMI 3 worker body is truncated before {field_name}")

    def read_float64(self, field_name: str) -> float:
        """Read one network-order Float64 or reject a truncated body.

        :param field_name: Field identified in truncation errors.
        :return: Parsed floating-point value.
        """

        field_end: int = self.offset + 8
        if field_end <= len(self.body):
            value: float = float(struct.unpack_from("!d", self.body, self.offset)[0])
            self.offset = field_end
            return value
        else:
            raise ValueError(f"FMI 3 worker body is truncated before {field_name}")

    def read_text(self, field_name: str) -> str:
        """Read one UInt16-length-prefixed UTF-8 string.

        :param field_name: Field identified in protocol errors.
        :return: Decoded text.
        """

        length_end: int = self.offset + 2
        if length_end <= len(self.body):
            text_length: int = int(struct.unpack_from("!H", self.body, self.offset)[0])
            self.offset = length_end
        else:
            raise ValueError(f"FMI 3 worker body is truncated before {field_name} length")
        field_end: int = self.offset + text_length
        if field_end <= len(self.body):
            encoded_text: bytes = self.body[self.offset:field_end]
            self.offset = field_end
        else:
            raise ValueError(f"FMI 3 worker body is truncated inside {field_name}")
        try:
            decoded_text: str = encoded_text.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"FMI 3 worker {field_name} is not valid UTF-8") from error
        return decoded_text

    def ensure_finished(self) -> None:
        """Reject unrepresented trailing bytes after a complete body.

        :return: None.
        """

        if self.offset == len(self.body):
            pass
        else:
            raise ValueError("FMI 3 worker body contains trailing bytes")

def _validate_required_text(text_value: str, field_name: str) -> None:
    """Reject an empty required protocol identity field.

    :param text_value: Required text value.
    :param field_name: Field identified in validation errors.
    :return: None.
    """

    if text_value.strip() != "":
        pass
    else:
        raise ValueError(f"FMI 3 worker {field_name} must not be empty")


def _validate_sha256_digest(digest: str, field_name: str) -> None:
    """Require one exact 64-character hexadecimal SHA-256 digest.

    :param digest: Digest text to validate.
    :param field_name: Field identified in validation errors.
    :return: None.
    """

    digest_is_valid: bool = len(digest) == 64
    digest_character: str
    for digest_character in digest:
        if digest_character in "0123456789abcdefABCDEF":
            pass
        else:
            digest_is_valid = False
    if digest_is_valid:
        pass
    else:
        raise ValueError(f"FMI 3 worker {field_name} must be a SHA-256 digest")


def _validate_request_id(request_id: int) -> None:
    """Require a positive request identifier representable as UInt64.

    :param request_id: Correlation identifier to validate.
    :return: None.
    """

    if request_id > 0 and request_id <= 18446744073709551615:
        pass
    else:
        raise ValueError("FMI 3 worker request id is outside positive UInt64")


def _encode_protocol_text(text_value: str, field_name: str) -> bytes:
    """Encode one bounded UTF-8 string with its UInt16 length.

    :param text_value: Text to encode.
    :param field_name: Field identified in bounds errors.
    :return: Length-prefixed UTF-8 bytes.
    """

    encoded_text: bytes = text_value.encode("utf-8")
    if len(encoded_text) <= 65535:
        pass
    else:
        raise ValueError(f"FMI 3 worker {field_name} exceeds 65535 encoded bytes")
    return b"".join((struct.pack("!H", len(encoded_text)), encoded_text))


def _validate_frame_size(frame: bytes, maximum_frame_size: int) -> None:
    """Enforce a caller-owned positive transport bound.

    :param frame: Complete encoded or received frame.
    :param maximum_frame_size: Maximum accepted bytes.
    :return: None.
    """

    if maximum_frame_size > 0:
        pass
    else:
        raise ValueError("FMI 3 worker maximum frame size must be positive")
    if len(frame) <= maximum_frame_size:
        pass
    else:
        raise ValueError("FMI 3 worker frame exceeds the configured size bound")


def validate_fmi_three_worker_minimum_start_frame_capacity(
    instantiation_token: str,
    model_identifier: str,
    instance_name: str,
    interface_mode: FmuInterfaceMode,
    maximum_frame_size: int,
) -> None:
    """Validate caller-known START identity and its minimum encoded frame.

    The staged absolute path is unavailable before extraction. Its UInt16
    length prefix, both fixed-size SHA-256 texts, and the staging counters are
    nevertheless included so an impossible START frame fails before staging.

    :param instantiation_token: Exact FMI 3 instantiation token.
    :param model_identifier: Exact selected-interface model identifier.
    :param instance_name: Stable name for the native FMU instance.
    :param interface_mode: Selected Model Exchange or Co-Simulation interface.
    :param maximum_frame_size: Maximum complete request frame size.
    :return: None.
    """

    _validate_required_text(instantiation_token, "instantiation token")
    _validate_required_text(model_identifier, "model identifier")
    _validate_required_text(instance_name, "instance name")
    if interface_mode in (
        FmuInterfaceMode.MODEL_EXCHANGE,
        FmuInterfaceMode.CO_SIMULATION,
    ):
        pass
    else:
        raise ValueError("FMI 3 worker interface mode is invalid")
    encoded_instantiation_token: bytes = _encode_protocol_text(
        instantiation_token,
        "instantiation token",
    )
    encoded_model_identifier: bytes = _encode_protocol_text(
        model_identifier,
        "model identifier",
    )
    encoded_instance_name: bytes = _encode_protocol_text(
        instance_name,
        "instance name",
    )
    frame_header_size: int = struct.calcsize("!4sBBBQI")
    start_flags_size: int = struct.calcsize("!B")
    staged_path_length_size: int = struct.calcsize("!H")
    staged_digest_size: int = 2 + 64
    staging_counters_size: int = struct.calcsize("!QI")
    minimum_frame_size: int = (
        frame_header_size
        + start_flags_size
        + staged_path_length_size
        + len(encoded_instantiation_token)
        + len(encoded_model_identifier)
        + len(encoded_instance_name)
        + staged_digest_size * 2
        + staging_counters_size
    )
    if maximum_frame_size > 0:
        pass
    else:
        raise ValueError("FMI 3 worker maximum frame size must be positive")
    if minimum_frame_size <= maximum_frame_size:
        pass
    else:
        raise ValueError(
            "FMI 3 worker START identity cannot fit the configured frame bound"
        )


def validate_fmi_three_worker_float64_frame_capacity(
    request_kind: FmiThreeWorkerRequestKind,
    value_reference_count: int,
    serialized_value_count: int,
    maximum_frame_size: int,
    maximum_value_count: int,
) -> None:
    """Require both sides of one Float64 exchange to fit configured limits.

    GET validation includes the larger response before the worker performs any
    native read. This prevents a small request from creating an unencodable
    response after crossing the ABI boundary.

    :param request_kind: CONFIGURE_FLOAT64, SET_FLOAT64, or GET_FLOAT64 kind.
    :param value_reference_count: Number of scalar or array references.
    :param serialized_value_count: Number of concatenated Float64 values.
    :param maximum_frame_size: Maximum complete request or response frame size.
    :param maximum_value_count: Maximum serialized-value cardinality.
    :return: None.
    """

    validate_fmi_three_worker_float64_value_limit(maximum_value_count)
    if (
        value_reference_count > 0
        and value_reference_count <= maximum_value_count
        and serialized_value_count >= 0
        and serialized_value_count <= maximum_value_count
    ):
        pass
    else:
        raise ValueError("FMI 3 worker Float64 value count is outside its bound")
    if maximum_frame_size > 0:
        pass
    else:
        raise ValueError("FMI 3 worker maximum frame size must be positive")
    frame_header_size: int = struct.calcsize("!4sBBBQI")
    if request_kind in (
        FmiThreeWorkerRequestKind.CONFIGURE_FLOAT64,
        FmiThreeWorkerRequestKind.SET_FLOAT64,
    ):
        request_frame_size: int = (
            frame_header_size
            + 8
            + value_reference_count * 4
            + serialized_value_count * 8
        )
        response_frame_size: int = frame_header_size
    else:
        if request_kind == FmiThreeWorkerRequestKind.GET_FLOAT64:
            request_frame_size = frame_header_size + 8 + value_reference_count * 4
            response_frame_size = frame_header_size + 4 + serialized_value_count * 8
        else:
            raise ValueError(
                "FMI 3 Float64 frame capacity requires CONFIGURE, SET, or GET"
            )
    if (
        request_frame_size <= maximum_frame_size
        and response_frame_size <= maximum_frame_size
    ):
        pass
    else:
        raise ValueError(
            "FMI 3 worker Float64 request or response exceeds the frame bound"
        )


def validate_fmi_three_worker_int32_frame_capacity(
    request_kind: FmiThreeWorkerRequestKind,
    value_count: int,
    maximum_frame_size: int,
    maximum_value_count: int,
) -> None:
    """Require one scalar Int32 request and response to fit both bounds.

    :param request_kind: SET_INT32 or GET_INT32 operation.
    :param value_count: Number of aligned scalar references and values.
    :param maximum_frame_size: Maximum complete request or response size.
    :param maximum_value_count: Shared numeric cardinality limit.
    :return: None.
    """

    validate_fmi_three_worker_float64_value_limit(maximum_value_count)
    if value_count > 0 and value_count <= maximum_value_count:
        pass
    else:
        raise ValueError("FMI 3 worker Int32 value count is outside its bound")
    if maximum_frame_size > 0:
        pass
    else:
        raise ValueError("FMI 3 worker maximum frame size must be positive")
    frame_header_size: int = struct.calcsize("!4sBBBQI")
    if request_kind == FmiThreeWorkerRequestKind.SET_INT32:
        request_frame_size: int = frame_header_size + 8 + value_count * 8
        response_frame_size: int = frame_header_size
    else:
        if request_kind == FmiThreeWorkerRequestKind.GET_INT32:
            request_frame_size = frame_header_size + 4 + value_count * 4
            response_frame_size = frame_header_size + 4 + value_count * 4
        else:
            raise ValueError("FMI 3 Int32 frame capacity requires SET or GET")
    if (
        request_frame_size <= maximum_frame_size
        and response_frame_size <= maximum_frame_size
    ):
        pass
    else:
        raise ValueError(
            "FMI 3 worker Int32 request or response exceeds the frame bound"
        )


def validate_fmi_three_worker_initialization_frame_capacity(
    float64_value_reference_count: int,
    float64_serialized_value_count: int,
    int32_value_reference_count: int,
    int32_value_count: int,
    maximum_frame_size: int,
    maximum_value_count: int,
) -> None:
    """Require the complete mixed numeric INITIALIZE body to fit its bounds.

    :param float64_value_reference_count: Float64 scalar or array references.
    :param float64_serialized_value_count: Concatenated Float64 values.
    :param int32_value_reference_count: Scalar Int32 references.
    :param int32_value_count: Signed Int32 values.
    :param maximum_frame_size: Maximum complete request frame size.
    :param maximum_value_count: Shared numeric cardinality limit.
    :return: None.
    """

    validate_fmi_three_worker_float64_value_limit(maximum_value_count)
    counts_are_nonnegative: bool = (
        float64_value_reference_count >= 0
        and float64_serialized_value_count >= 0
        and int32_value_reference_count >= 0
        and int32_value_count >= 0
    )
    float64_presence_is_valid: bool = (
        float64_value_reference_count > 0
        or float64_serialized_value_count == 0
    )
    int32_alignment_is_valid: bool = (
        int32_value_reference_count == int32_value_count
    )
    combined_reference_count: int = (
        float64_value_reference_count + int32_value_reference_count
    )
    combined_value_count: int = float64_serialized_value_count + int32_value_count
    if (
        counts_are_nonnegative
        and float64_presence_is_valid
        and int32_alignment_is_valid
        and combined_reference_count <= maximum_value_count
        and combined_value_count <= maximum_value_count
    ):
        pass
    else:
        raise ValueError(
            "FMI 3 worker combined initialization count is outside its bound"
        )
    if maximum_frame_size > 0:
        pass
    else:
        raise ValueError("FMI 3 worker maximum frame size must be positive")
    request_frame_size: int = (
        struct.calcsize("!4sBBBQI")
        + struct.calcsize("!Bddd")
        + 16
        + 4 * combined_reference_count
        + 8 * float64_serialized_value_count
        + 4 * int32_value_count
    )
    if request_frame_size <= maximum_frame_size:
        pass
    else:
        raise ValueError(
            "FMI 3 worker initialization request exceeds the frame bound"
        )


def validate_fmi_three_worker_model_exchange_evaluation_frame_capacity(
    continuous_state_count: int,
    writable_reference_count: int,
    writable_value_count: int,
    readable_reference_count: int,
    readable_value_count: int,
    maximum_frame_size: int,
    maximum_value_count: int,
) -> None:
    """Require one atomic Model Exchange evaluation to fit both wire frames.

    :param continuous_state_count: Number of state values and derivatives.
    :param writable_reference_count: Number of optional input references.
    :param writable_value_count: Number of optional serialized input values.
    :param readable_reference_count: Number of optional output references.
    :param readable_value_count: Number of optional serialized output values.
    :param maximum_frame_size: Maximum complete request or response frame size.
    :param maximum_value_count: Maximum count for each numeric collection.
    :return: None.
    """

    validate_fmi_three_worker_float64_value_limit(maximum_value_count)
    count_is_valid: bool = (
        continuous_state_count >= 0
        and continuous_state_count <= maximum_value_count
        and writable_reference_count >= 0
        and writable_reference_count <= maximum_value_count
        and writable_value_count >= 0
        and writable_value_count <= maximum_value_count
        and readable_reference_count >= 0
        and readable_reference_count <= maximum_value_count
        and readable_value_count >= 0
        and readable_value_count <= maximum_value_count
    )
    writable_presence_is_valid: bool = (
        writable_reference_count > 0 or writable_value_count == 0
    )
    readable_presence_is_valid: bool = (
        readable_reference_count > 0 or readable_value_count == 0
    )
    if count_is_valid and writable_presence_is_valid and readable_presence_is_valid:
        pass
    else:
        raise ValueError(
            "FMI 3 Model Exchange evaluation value count is outside its bound"
        )
    if maximum_frame_size > 0:
        pass
    else:
        raise ValueError("FMI 3 worker maximum frame size must be positive")
    frame_header_size: int = struct.calcsize("!4sBBBQI")
    request_frame_size: int = (
        frame_header_size
        + 28
        + continuous_state_count * 8
        + writable_reference_count * 4
        + writable_value_count * 8
        + readable_reference_count * 4
    )
    response_frame_size: int = (
        frame_header_size
        + 8
        + continuous_state_count * 8
        + readable_value_count * 8
    )
    if (
        request_frame_size <= maximum_frame_size
        and response_frame_size <= maximum_frame_size
    ):
        pass
    else:
        raise ValueError(
            "FMI 3 Model Exchange evaluation request or response exceeds the frame bound"
        )


def validate_fmi_three_worker_uint64_configuration_frame_capacity(
    value_count: int,
    maximum_frame_size: int,
    maximum_value_count: int,
) -> None:
    """Require one scalar UInt64 Configuration Mode frame to fit its limits.

    Each structural UInt64 parameter is scalar, so its reference and value
    collections have the same cardinality.

    :param value_count: Number of aligned UInt64 references and values.
    :param maximum_frame_size: Maximum complete request frame size.
    :param maximum_value_count: Maximum UInt64 scalar count.
    :return: None.
    """

    if maximum_value_count > 0 and maximum_value_count <= 16384:
        pass
    else:
        raise ValueError(
            "FMI 3 worker maximum UInt64 value count must be within 1 and 16384"
        )
    if value_count > 0 and value_count <= maximum_value_count:
        pass
    else:
        raise ValueError("FMI 3 worker UInt64 value count is outside its bound")
    if maximum_frame_size > 0:
        pass
    else:
        raise ValueError("FMI 3 worker maximum frame size must be positive")
    frame_header_size: int = struct.calcsize("!4sBBBQI")
    request_frame_size: int = frame_header_size + 8 + value_count * 12
    if request_frame_size <= maximum_frame_size:
        pass
    else:
        raise ValueError(
            "FMI 3 worker UInt64 request exceeds the frame bound"
        )


def _encode_worker_frame(
    direction: FmiThreeWorkerFrameDirection,
    opcode: int,
    request_id: int,
    body: bytes,
    maximum_frame_size: int,
) -> bytes:
    """Encode magic, version, direction, opcode, id, and body length.

    :param direction: Request or response direction.
    :param opcode: Direction-specific enum value.
    :param request_id: Positive correlation identifier.
    :param body: Already encoded message body.
    :param maximum_frame_size: Maximum complete frame size.
    :return: Complete framed message.
    """

    _validate_request_id(request_id)
    frame_header: bytes = struct.pack(
        "!4sBBBQI",
        b"VGFW",
        int(FmiThreeWorkerProtocolVersion.VERSION_ELEVEN),
        int(direction),
        opcode,
        request_id,
        len(body),
    )
    frame: bytes = b"".join((frame_header, body))
    _validate_frame_size(frame, maximum_frame_size)
    return frame


def _decode_worker_frame(
    frame: bytes,
    expected_direction: FmiThreeWorkerFrameDirection,
    maximum_frame_size: int,
) -> tuple[int, int, bytes]:
    """Validate a fixed header and return opcode, request id, and exact body.

    :param frame: Complete received frame.
    :param expected_direction: Direction required by the caller.
    :param maximum_frame_size: Maximum accepted frame size.
    :return: Opcode, request id, and bounded body bytes.
    """

    _validate_frame_size(frame, maximum_frame_size)
    header_size: int = struct.calcsize("!4sBBBQI")
    if len(frame) >= header_size:
        pass
    else:
        raise ValueError("FMI 3 worker frame is truncated before its fixed header")
    magic: bytes
    version_number: int
    direction_number: int
    opcode: int
    request_id: int
    declared_body_size: int
    magic, version_number, direction_number, opcode, request_id, declared_body_size = (
        struct.unpack_from("!4sBBBQI", frame, 0)
    )
    if magic == b"VGFW":
        pass
    else:
        raise ValueError("FMI 3 worker frame magic is invalid")
    if version_number == int(FmiThreeWorkerProtocolVersion.VERSION_ELEVEN):
        pass
    else:
        raise ValueError(f"Unsupported FMI 3 worker protocol version {version_number}")
    if direction_number == int(expected_direction):
        pass
    else:
        raise ValueError("FMI 3 worker frame direction does not match the receiver")
    _validate_request_id(request_id)
    actual_body_size: int = len(frame) - header_size
    if declared_body_size == actual_body_size:
        pass
    else:
        raise ValueError("FMI 3 worker frame body length is inconsistent")
    body: bytes = frame[header_size:]
    return opcode, request_id, body


def _validate_encoded_value_count(
    value_count: int,
    maximum_value_count: int,
    remaining_body_size: int,
    bytes_per_value: int,
    allow_zero: bool,
) -> None:
    """Reject unbounded or structurally inconsistent scalar collection bodies.

    :param value_count: Declared scalar count from the wire body.
    :param maximum_value_count: Positive caller-owned scalar count limit.
    :param remaining_body_size: Bytes after the count field.
    :param bytes_per_value: Exact encoded bytes owned by each scalar entry.
    :param allow_zero: Whether an active zero-length array may encode no values.
    :return: None.
    """

    validate_fmi_three_worker_float64_value_limit(maximum_value_count)
    lower_bound_is_valid: bool = value_count >= 0 if allow_zero else value_count > 0
    if lower_bound_is_valid and value_count <= maximum_value_count:
        pass
    else:
        raise ValueError("FMI 3 worker Float64 value count is outside its bound")
    expected_body_size: int = value_count * bytes_per_value
    if remaining_body_size == expected_body_size:
        pass
    else:
        raise ValueError("FMI 3 worker Float64 collection body size is inconsistent")


def _encode_float64_assignments_body(
    value_references: tuple[int, ...],
    values: tuple[float, ...],
) -> bytes:
    """Encode separate reference and serialized-value collections.

    :param value_references: Validated ordered scalar or array references.
    :param values: Validated concatenated finite values.
    :return: Two counts followed by references and values.
    """

    value_reference_count: int = len(value_references)
    serialized_value_count: int = len(values)
    encoded_body: bytearray = bytearray(
        8 + value_reference_count * 4 + serialized_value_count * 8
    )
    struct.pack_into(
        "!II",
        encoded_body,
        0,
        value_reference_count,
        serialized_value_count,
    )
    value_reference_index: int
    for value_reference_index in range(value_reference_count):
        struct.pack_into(
            "!I",
            encoded_body,
            8 + value_reference_index * 4,
            value_references[value_reference_index],
        )
    values_offset: int = 8 + value_reference_count * 4
    value_index: int
    for value_index in range(serialized_value_count):
        struct.pack_into(
            "!d",
            encoded_body,
            values_offset + value_index * 8,
            values[value_index],
        )
    return bytes(encoded_body)


def _encode_int32_assignments_body(
    value_references: tuple[int, ...],
    values: tuple[int, ...],
) -> bytes:
    """Encode aligned scalar Int32 references and signed values.

    :param value_references: Validated ordered scalar references.
    :param values: Validated signed values aligned with the references.
    :return: Equal counts followed by UInt32 references and Int32 values.
    """

    value_count: int = len(values)
    encoded_body: bytearray = bytearray(8 + value_count * 8)
    struct.pack_into("!II", encoded_body, 0, value_count, value_count)
    value_index: int
    for value_index in range(value_count):
        struct.pack_into(
            "!I",
            encoded_body,
            8 + value_index * 4,
            value_references[value_index],
        )
    values_offset: int = 8 + value_count * 4
    for value_index in range(value_count):
        struct.pack_into(
            "!i",
            encoded_body,
            values_offset + value_index * 4,
            values[value_index],
        )
    return bytes(encoded_body)


def _encode_uint64_configuration_body(
    configuration: FmiThreeWorkerConfigureUInt64Request,
) -> bytes:
    """Encode aligned scalar UInt64 references and values.

    :param configuration: Validated UInt64 Configuration Mode request.
    :return: Two equal counts followed by references and UInt64 values.
    """

    value_count: int = len(configuration.values)
    encoded_body: bytearray = bytearray(8 + value_count * 12)
    struct.pack_into("!II", encoded_body, 0, value_count, value_count)
    value_index: int
    for value_index in range(value_count):
        struct.pack_into(
            "!I",
            encoded_body,
            8 + value_index * 4,
            configuration.value_references[value_index],
        )
    values_offset: int = 8 + value_count * 4
    for value_index in range(value_count):
        struct.pack_into(
            "!Q",
            encoded_body,
            values_offset + value_index * 8,
            configuration.values[value_index],
        )
    return bytes(encoded_body)


def _decode_nonempty_float64_assignments(
    reader: _FmiThreeWorkerBodyReader,
    request_kind: FmiThreeWorkerRequestKind,
    field_prefix: str,
    value_reference_count: int,
    serialized_value_count: int,
    maximum_frame_size: int,
    maximum_value_count: int,
) -> tuple[tuple[int, ...], tuple[float, ...]]:
    """Decode one bounded non-empty Float64 assignment collection.

    :param reader: Bounded request-body reader positioned after the value count.
    :param request_kind: CONFIGURE_FLOAT64 or SET_FLOAT64 capacity profile.
    :param field_prefix: Stable diagnostic prefix for the enclosing operation.
    :param value_reference_count: Declared positive reference count.
    :param serialized_value_count: Declared positive serialized value count.
    :param maximum_frame_size: Maximum complete request frame size.
    :param maximum_value_count: Maximum serialized-value cardinality.
    :return: Ordered reference and value tuples validated by the caller's body.
    """

    validate_fmi_three_worker_float64_frame_capacity(
        request_kind=request_kind,
        value_reference_count=value_reference_count,
        serialized_value_count=serialized_value_count,
        maximum_frame_size=maximum_frame_size,
        maximum_value_count=maximum_value_count,
    )
    expected_body_size: int = (
        value_reference_count * 4 + serialized_value_count * 8
    )
    if len(reader.body) - reader.offset == expected_body_size:
        pass
    else:
        raise ValueError("FMI 3 worker Float64 collection body size is inconsistent")
    value_references: list[int] = [0] * value_reference_count
    values: list[float] = [0.0] * serialized_value_count
    value_reference_index: int
    for value_reference_index in range(value_reference_count):
        value_references[value_reference_index] = reader.read_unsigned_int(
            f"{field_prefix} value reference"
        )
    value_index: int
    for value_index in range(serialized_value_count):
        values[value_index] = reader.read_float64(f"{field_prefix} value")
    return tuple(value_references), tuple(values)


def _decode_nonempty_int32_assignments(
    reader: _FmiThreeWorkerBodyReader,
    request_kind: FmiThreeWorkerRequestKind,
    field_prefix: str,
    value_reference_count: int,
    value_count: int,
    maximum_frame_size: int,
    maximum_value_count: int,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Decode one bounded non-empty scalar Int32 assignment collection.

    :param reader: Bounded reader positioned after both counts.
    :param request_kind: SET_INT32 capacity profile.
    :param field_prefix: Stable diagnostic prefix for the operation.
    :param value_reference_count: Declared positive scalar reference count.
    :param value_count: Declared signed-value count.
    :param maximum_frame_size: Maximum complete request frame size.
    :param maximum_value_count: Shared numeric cardinality bound.
    :return: Ordered scalar references and signed values.
    """

    if value_reference_count == value_count:
        pass
    else:
        raise ValueError("FMI 3 worker Int32 references and values must align")
    validate_fmi_three_worker_int32_frame_capacity(
        request_kind=request_kind,
        value_count=value_count,
        maximum_frame_size=maximum_frame_size,
        maximum_value_count=maximum_value_count,
    )
    expected_body_size: int = value_count * 8
    if len(reader.body) - reader.offset == expected_body_size:
        pass
    else:
        raise ValueError("FMI 3 worker Int32 collection body size is inconsistent")
    value_references: list[int] = [0] * value_reference_count
    values: list[int] = [0] * value_count
    value_index: int
    for value_index in range(value_reference_count):
        value_references[value_index] = reader.read_unsigned_int(
            f"{field_prefix} value reference"
        )
    for value_index in range(value_count):
        values[value_index] = reader.read_signed_int(f"{field_prefix} value")
    return tuple(value_references), tuple(values)


def _decode_uint64_configuration(
    reader: _FmiThreeWorkerBodyReader,
    value_reference_count: int,
    serialized_value_count: int,
    maximum_frame_size: int,
    maximum_value_count: int,
) -> FmiThreeWorkerConfigureUInt64Request:
    """Decode one bounded scalar UInt64 Configuration Mode collection.

    :param reader: Bounded request-body reader positioned after both counts.
    :param value_reference_count: Declared structural-parameter reference count.
    :param serialized_value_count: Declared UInt64 value count.
    :param maximum_frame_size: Maximum complete request frame size.
    :param maximum_value_count: Maximum UInt64 scalar count.
    :return: Validated typed UInt64 configuration body.
    """

    if value_reference_count == serialized_value_count:
        pass
    else:
        raise ValueError(
            "FMI 3 worker CONFIGURE_UINT64 references and values must align"
        )
    validate_fmi_three_worker_uint64_configuration_frame_capacity(
        value_count=serialized_value_count,
        maximum_frame_size=maximum_frame_size,
        maximum_value_count=maximum_value_count,
    )
    expected_body_size: int = value_reference_count * 12
    if len(reader.body) - reader.offset == expected_body_size:
        pass
    else:
        raise ValueError(
            "FMI 3 worker UInt64 collection body size is inconsistent"
        )
    value_references: list[int] = [0] * value_reference_count
    values: list[int] = [0] * serialized_value_count
    value_index: int
    for value_index in range(value_reference_count):
        value_references[value_index] = reader.read_unsigned_int(
            "CONFIGURE_UINT64 value reference"
        )
    for value_index in range(serialized_value_count):
        values[value_index] = reader.read_unsigned_long(
            "CONFIGURE_UINT64 value"
        )
    return FmiThreeWorkerConfigureUInt64Request(
        value_references=tuple(value_references),
        values=tuple(values),
        maximum_value_count=maximum_value_count,
    )


def _encode_get_float64_body(
    get_float64: FmiThreeWorkerGetFloat64Request,
) -> bytes:
    """Encode ordered scalar or array references for one GET_FLOAT64 request.

    :param get_float64: Validated bounded read request.
    :return: Exact GET_FLOAT64 request body.
    """

    value_reference_count: int = len(get_float64.value_references)
    encoded_body: bytearray = bytearray(8 + value_reference_count * 4)
    struct.pack_into(
        "!II",
        encoded_body,
        0,
        value_reference_count,
        get_float64.serialized_value_count,
    )
    value_reference_index: int
    for value_reference_index in range(value_reference_count):
        struct.pack_into(
            "!I",
            encoded_body,
            8 + value_reference_index * 4,
            get_float64.value_references[value_reference_index],
        )
    return bytes(encoded_body)


def _encode_get_int32_body(
    get_int32: FmiThreeWorkerGetInt32Request,
) -> bytes:
    """Encode ordered scalar references for one GET_INT32 request.

    :param get_int32: Validated bounded scalar read request.
    :return: Exact GET_INT32 request body.
    """

    value_count: int = len(get_int32.value_references)
    encoded_body: bytearray = bytearray(4 + value_count * 4)
    struct.pack_into("!I", encoded_body, 0, value_count)
    value_index: int
    for value_index in range(value_count):
        struct.pack_into(
            "!I",
            encoded_body,
            4 + value_index * 4,
            get_int32.value_references[value_index],
        )
    return bytes(encoded_body)


def _encode_float64_values_body(
    float64_values: FmiThreeWorkerFloat64Values,
) -> bytes:
    """Encode ordered scalar values without duplicating request references.

    :param float64_values: Validated finite Float64 response values.
    :return: Exact FLOAT64_VALUES response body.
    """

    value_count: int = len(float64_values.values)
    encoded_body: bytearray = bytearray(4 + value_count * 8)
    struct.pack_into("!I", encoded_body, 0, value_count)
    value_index: int
    for value_index in range(value_count):
        struct.pack_into(
            "!d",
            encoded_body,
            4 + value_index * 8,
            float64_values.values[value_index],
        )
    return bytes(encoded_body)


def _encode_int32_values_body(
    int32_values: FmiThreeWorkerInt32Values,
) -> bytes:
    """Encode ordered signed scalar Int32 response values.

    :param int32_values: Validated Int32 response body.
    :return: Exact INT32_VALUES response body.
    """

    value_count: int = len(int32_values.values)
    encoded_body: bytearray = bytearray(4 + value_count * 4)
    struct.pack_into("!I", encoded_body, 0, value_count)
    value_index: int
    for value_index in range(value_count):
        struct.pack_into(
            "!i",
            encoded_body,
            4 + value_index * 4,
            int32_values.values[value_index],
        )
    return bytes(encoded_body)


def _encode_model_exchange_evaluation_request_body(
    evaluation: FmiThreeWorkerModelExchangeEvaluationRequest,
) -> bytes:
    """Encode one atomic Model Exchange native-call sequence.

    :param evaluation: Validated evaluation request components.
    :return: Time, states, optional writes, and optional reads in fixed order.
    """

    if evaluation.set_float64 is not None:
        write_body: bytes = _encode_float64_assignments_body(
            value_references=evaluation.set_float64.value_references,
            values=evaluation.set_float64.values,
        )
    else:
        write_body = struct.pack("!II", 0, 0)
    if evaluation.get_float64 is not None:
        read_body: bytes = _encode_get_float64_body(evaluation.get_float64)
    else:
        read_body = struct.pack("!II", 0, 0)
    return b"".join(
        (
            struct.pack("!d", evaluation.set_time.time_value),
            _encode_float64_values_body(evaluation.continuous_states),
            write_body,
            read_body,
        )
    )


def _encode_model_exchange_evaluation_result_body(
    result: FmiThreeWorkerModelExchangeEvaluationResult,
) -> bytes:
    """Encode independently bounded derivative and readable-value vectors.

    :param result: Validated atomic Model Exchange result.
    :return: Derivative collection followed by readable values.
    """

    return b"".join(
        (
            _encode_float64_values_body(result.derivatives),
            _encode_float64_values_body(result.readable_values),
        )
    )


def encode_fmi_three_worker_request(
    request: FmiThreeWorkerRequest,
    maximum_frame_size: int,
    maximum_float64_values_per_request: int,
) -> bytes:
    """Encode one typed request into the bounded wire format.

    :param request: Validated request envelope.
    :param maximum_frame_size: Maximum complete frame size.
    :param maximum_float64_values_per_request: Established shared bound for
        Float64, scalar Int32, and scalar UInt64 Configuration Mode values.
    :return: Complete binary frame.
    """

    validate_fmi_three_worker_float64_value_limit(
        maximum_float64_values_per_request
    )
    if request.kind == FmiThreeWorkerRequestKind.START:
        start: FmiThreeWorkerStartRequest | None = request.start
        if start is not None:
            pass
        else:
            raise ValueError("FMI 3 START request is missing its typed body")
        start_flags: int = int(start.visible) | (int(start.debug_logging) << 1)
        if start.float64_profile == FmiThreeWorkerFloat64Profile.SCALAR:
            encoded_float64_profile: int = 0
        else:
            if start.float64_profile == FmiThreeWorkerFloat64Profile.CONSTANT_ARRAY:
                encoded_float64_profile = 1
            else:
                if (
                    start.float64_profile
                    == FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY
                ):
                    encoded_float64_profile = 2
                else:
                    raise ValueError("Unsupported FMI 3 worker Float64 profile")
        start_flags |= encoded_float64_profile << 2
        if start.interface_mode == FmuInterfaceMode.CO_SIMULATION:
            encoded_interface_mode: int = 0
        else:
            if start.interface_mode == FmuInterfaceMode.MODEL_EXCHANGE:
                encoded_interface_mode = 1
            else:
                raise ValueError("Unsupported FMI 3 worker interface mode")
        start_flags |= encoded_interface_mode << 4
        start_flags |= int(start.early_return_allowed) << 5
        body: bytes = b"".join(
            (
                struct.pack("!B", start_flags),
                _encode_protocol_text(
                    str(start.extracted_fmu_directory),
                    "extracted FMU directory",
                ),
                _encode_protocol_text(start.instantiation_token, "instantiation token"),
                _encode_protocol_text(start.model_identifier, "model identifier"),
                _encode_protocol_text(start.instance_name, "instance name"),
                _encode_protocol_text(
                    start.staging_identity.tree_sha256,
                    "staged tree digest",
                ),
                _encode_protocol_text(
                    start.staging_identity.model_description_sha256,
                    "model-description digest",
                ),
                struct.pack(
                    "!QI",
                    start.staging_identity.tree_size,
                    start.staging_identity.entry_count,
                ),
            )
        )
    else:
        if request.kind == FmiThreeWorkerRequestKind.INITIALIZE:
            initialization: FmiThreeWorkerInitializationRequest | None = (
                request.initialization
            )
            if initialization is not None:
                pass
            else:
                raise ValueError("FMI 3 INITIALIZE request is missing its typed body")
            initialization_flags: int = int(initialization.stop_time is not None)
            initialization_flags |= int(initialization.relative_tolerance is not None) << 1
            stop_time: float = (
                0.0 if initialization.stop_time is None else initialization.stop_time
            )
            relative_tolerance: float = (
                0.0
                if initialization.relative_tolerance is None
                else initialization.relative_tolerance
            )
            initialization_header: bytes = struct.pack(
                "!Bddd",
                initialization_flags,
                initialization.start_time,
                stop_time,
                relative_tolerance,
            )
            validate_fmi_three_worker_initialization_frame_capacity(
                float64_value_reference_count=len(
                    initialization.initial_float64_value_references
                ),
                float64_serialized_value_count=len(
                    initialization.initial_float64_values
                ),
                int32_value_reference_count=len(
                    initialization.initial_int32_value_references
                ),
                int32_value_count=len(initialization.initial_int32_values),
                maximum_frame_size=maximum_frame_size,
                maximum_value_count=maximum_float64_values_per_request,
            )
            initialization_float64_body: bytes = _encode_float64_assignments_body(
                value_references=(
                    initialization.initial_float64_value_references
                ),
                values=initialization.initial_float64_values,
            )
            initialization_int32_body: bytes = _encode_int32_assignments_body(
                value_references=initialization.initial_int32_value_references,
                values=initialization.initial_int32_values,
            )
            body = b"".join(
                (
                    initialization_header,
                    initialization_float64_body,
                    initialization_int32_body,
                )
            )
        else:
            if request.kind == FmiThreeWorkerRequestKind.CONFIGURE_FLOAT64:
                configuration: FmiThreeWorkerConfigureFloat64Request | None = (
                    request.configuration
                )
                if configuration is not None:
                    validate_fmi_three_worker_float64_frame_capacity(
                        request_kind=request.kind,
                        value_reference_count=len(configuration.value_references),
                        serialized_value_count=len(configuration.values),
                        maximum_frame_size=maximum_frame_size,
                        maximum_value_count=maximum_float64_values_per_request,
                    )
                    body = _encode_float64_assignments_body(
                        value_references=configuration.value_references,
                        values=configuration.values,
                    )
                else:
                    raise ValueError(
                        "FMI 3 CONFIGURE_FLOAT64 request is missing its typed body"
                    )
            else:
                if request.kind == FmiThreeWorkerRequestKind.CONFIGURE_UINT64:
                    configuration_uint64: (
                        FmiThreeWorkerConfigureUInt64Request | None
                    ) = request.configuration_uint64
                    if configuration_uint64 is not None:
                        validate_fmi_three_worker_uint64_configuration_frame_capacity(
                            value_count=len(configuration_uint64.values),
                            maximum_frame_size=maximum_frame_size,
                            maximum_value_count=(
                                maximum_float64_values_per_request
                            ),
                        )
                        body = _encode_uint64_configuration_body(
                            configuration=configuration_uint64,
                        )
                    else:
                        raise ValueError(
                            "FMI 3 CONFIGURE_UINT64 request is missing its "
                            "typed body"
                        )
                else:
                    if request.kind == FmiThreeWorkerRequestKind.SET_FLOAT64:
                        set_float64: FmiThreeWorkerSetFloat64Request | None = (
                            request.set_float64
                        )
                        if set_float64 is not None:
                            validate_fmi_three_worker_float64_frame_capacity(
                                request_kind=request.kind,
                                value_reference_count=len(
                                    set_float64.value_references
                                ),
                                serialized_value_count=len(set_float64.values),
                                maximum_frame_size=maximum_frame_size,
                                maximum_value_count=(
                                    maximum_float64_values_per_request
                                ),
                            )
                            body = _encode_float64_assignments_body(
                                value_references=set_float64.value_references,
                                values=set_float64.values,
                            )
                        else:
                            raise ValueError(
                                "FMI 3 SET_FLOAT64 request is missing its typed body"
                            )
                    else:
                        if request.kind == FmiThreeWorkerRequestKind.GET_FLOAT64:
                            get_float64: FmiThreeWorkerGetFloat64Request | None = (
                                request.get_float64
                            )
                            if get_float64 is not None:
                                validate_fmi_three_worker_float64_frame_capacity(
                                    request_kind=request.kind,
                                    value_reference_count=len(
                                        get_float64.value_references
                                    ),
                                    serialized_value_count=(
                                        get_float64.serialized_value_count
                                    ),
                                    maximum_frame_size=maximum_frame_size,
                                    maximum_value_count=(
                                        maximum_float64_values_per_request
                                    ),
                                )
                                body = _encode_get_float64_body(get_float64)
                            else:
                                raise ValueError(
                                    "FMI 3 GET_FLOAT64 request is missing its typed body"
                                )
                        else:
                            if request.kind == FmiThreeWorkerRequestKind.DO_STEP:
                                do_step: FmiThreeWorkerDoStepRequest | None = (
                                    request.do_step
                                )
                                if do_step is not None:
                                    step_flags: int = int(
                                        do_step.no_set_fmu_state_prior_to_current_point
                                    )
                                    body = struct.pack(
                                        "!Bdd",
                                        step_flags,
                                        do_step.current_communication_point,
                                        do_step.communication_step_size,
                                    )
                                else:
                                    raise ValueError(
                                        "FMI 3 DO_STEP request is missing its typed body"
                                    )
                            else:
                                if request.kind == FmiThreeWorkerRequestKind.SET_TIME:
                                    set_time: FmiThreeWorkerSetTimeRequest | None = (
                                        request.set_time
                                    )
                                    if set_time is not None:
                                        body = struct.pack("!d", set_time.time_value)
                                    else:
                                        raise ValueError(
                                            "FMI 3 SET_TIME request is missing its typed body"
                                        )
                                else:
                                    if (
                                        request.kind
                                        == FmiThreeWorkerRequestKind.SET_CONTINUOUS_STATES
                                    ):
                                        continuous_states: (
                                            FmiThreeWorkerFloat64Values | None
                                        ) = request.continuous_states
                                        if continuous_states is not None:
                                            body = _encode_float64_values_body(
                                                continuous_states
                                            )
                                        else:
                                            raise ValueError(
                                                "FMI 3 SET_CONTINUOUS_STATES request "
                                                "is missing its typed body"
                                            )
                                    else:
                                        if (
                                            request.kind
                                            == FmiThreeWorkerRequestKind.COMPLETED_INTEGRATOR_STEP
                                        ):
                                            completed_integrator_step: (
                                                FmiThreeWorkerCompletedIntegratorStepRequest
                                                | None
                                            ) = request.completed_integrator_step
                                            if completed_integrator_step is not None:
                                                body = struct.pack(
                                                    "!B",
                                                    int(
                                                        completed_integrator_step.no_set_fmu_state_prior_to_current_point
                                                    ),
                                                )
                                            else:
                                                raise ValueError(
                                                    "FMI 3 COMPLETED_INTEGRATOR_STEP "
                                                    "request is missing its typed body"
                                                )
                                        else:
                                            if (
                                                request.kind
                                                == FmiThreeWorkerRequestKind.EVALUATE_MODEL_EXCHANGE
                                            ):
                                                evaluation: (
                                                    FmiThreeWorkerModelExchangeEvaluationRequest
                                                    | None
                                                ) = request.model_exchange_evaluation
                                                if evaluation is not None:
                                                    pass
                                                else:
                                                    raise ValueError(
                                                        "FMI 3 EVALUATE_MODEL_EXCHANGE "
                                                        "request is missing its typed body"
                                                    )
                                                if evaluation.set_float64 is not None:
                                                    writable_reference_count: int = len(
                                                        evaluation.set_float64.value_references
                                                    )
                                                    writable_value_count: int = len(
                                                        evaluation.set_float64.values
                                                    )
                                                else:
                                                    writable_reference_count = 0
                                                    writable_value_count = 0
                                                if evaluation.get_float64 is not None:
                                                    readable_reference_count: int = len(
                                                        evaluation.get_float64.value_references
                                                    )
                                                    readable_value_count: int = (
                                                        evaluation.get_float64.serialized_value_count
                                                    )
                                                else:
                                                    readable_reference_count = 0
                                                    readable_value_count = 0
                                                validate_fmi_three_worker_model_exchange_evaluation_frame_capacity(
                                                    continuous_state_count=len(
                                                        evaluation.continuous_states.values
                                                    ),
                                                    writable_reference_count=(
                                                        writable_reference_count
                                                    ),
                                                    writable_value_count=(
                                                        writable_value_count
                                                    ),
                                                    readable_reference_count=(
                                                        readable_reference_count
                                                    ),
                                                    readable_value_count=(
                                                        readable_value_count
                                                    ),
                                                    maximum_frame_size=maximum_frame_size,
                                                    maximum_value_count=(
                                                        maximum_float64_values_per_request
                                                    ),
                                                )
                                                body = _encode_model_exchange_evaluation_request_body(
                                                    evaluation
                                                )
                                            else:
                                                if request.kind == FmiThreeWorkerRequestKind.SET_INT32:
                                                    set_int32: FmiThreeWorkerSetInt32Request | None = request.set_int32
                                                    if set_int32 is not None:
                                                        validate_fmi_three_worker_int32_frame_capacity(
                                                            request_kind=request.kind,
                                                            value_count=len(set_int32.values),
                                                            maximum_frame_size=maximum_frame_size,
                                                            maximum_value_count=maximum_float64_values_per_request,
                                                        )
                                                        body = _encode_int32_assignments_body(
                                                            value_references=set_int32.value_references,
                                                            values=set_int32.values,
                                                        )
                                                    else:
                                                        raise ValueError(
                                                            "FMI 3 SET_INT32 request is missing its typed body"
                                                        )
                                                else:
                                                    if request.kind == FmiThreeWorkerRequestKind.GET_INT32:
                                                        get_int32: FmiThreeWorkerGetInt32Request | None = request.get_int32
                                                        if get_int32 is not None:
                                                            validate_fmi_three_worker_int32_frame_capacity(
                                                                request_kind=request.kind,
                                                                value_count=len(get_int32.value_references),
                                                                maximum_frame_size=maximum_frame_size,
                                                                maximum_value_count=maximum_float64_values_per_request,
                                                            )
                                                            body = _encode_get_int32_body(get_int32)
                                                        else:
                                                            raise ValueError(
                                                                "FMI 3 GET_INT32 request is missing its typed body"
                                                            )
                                                    else:
                                                        body = b""
    return _encode_worker_frame(
        FmiThreeWorkerFrameDirection.REQUEST,
        int(request.kind),
        request.request_id,
        body,
        maximum_frame_size,
    )


def decode_fmi_three_worker_request(
    frame: bytes,
    maximum_frame_size: int,
    maximum_float64_values_per_request: int,
) -> FmiThreeWorkerRequest:
    """Decode one bounded request without evaluating serialized objects.

    :param frame: Complete binary request frame.
    :param maximum_frame_size: Maximum accepted frame size.
    :param maximum_float64_values_per_request: Established shared bound for
        Float64 values and scalar UInt64 Configuration Mode values.
    :return: Validated typed request envelope.
    """

    validate_fmi_three_worker_float64_value_limit(
        maximum_float64_values_per_request
    )
    request_number: int
    request_id: int
    body: bytes
    request_number, request_id, body = _decode_worker_frame(
        frame,
        FmiThreeWorkerFrameDirection.REQUEST,
        maximum_frame_size,
    )
    try:
        request_kind: FmiThreeWorkerRequestKind = FmiThreeWorkerRequestKind(request_number)
    except ValueError as error:
        raise ValueError(f"Unknown FMI 3 worker request kind {request_number}") from error
    reader: _FmiThreeWorkerBodyReader = _FmiThreeWorkerBodyReader(body)
    start: FmiThreeWorkerStartRequest | None = None
    initialization: FmiThreeWorkerInitializationRequest | None = None
    configuration: FmiThreeWorkerConfigureFloat64Request | None = None
    configuration_uint64: FmiThreeWorkerConfigureUInt64Request | None = None
    set_float64: FmiThreeWorkerSetFloat64Request | None = None
    get_float64: FmiThreeWorkerGetFloat64Request | None = None
    do_step: FmiThreeWorkerDoStepRequest | None = None
    set_time: FmiThreeWorkerSetTimeRequest | None = None
    continuous_states: FmiThreeWorkerFloat64Values | None = None
    completed_integrator_step: (
        FmiThreeWorkerCompletedIntegratorStepRequest | None
    ) = None
    model_exchange_evaluation: (
        FmiThreeWorkerModelExchangeEvaluationRequest | None
    ) = None
    set_int32: FmiThreeWorkerSetInt32Request | None = None
    get_int32: FmiThreeWorkerGetInt32Request | None = None
    if request_kind == FmiThreeWorkerRequestKind.START:
        start_flags: int = reader.read_unsigned_byte("START flags")
        if start_flags & ~63 == 0:
            pass
        else:
            raise ValueError("FMI 3 worker START request has unknown flags")
        extracted_fmu_directory: Path = Path(
            reader.read_text("extracted FMU directory")
        )
        instantiation_token: str = reader.read_text("instantiation token")
        model_identifier: str = reader.read_text("model identifier")
        instance_name: str = reader.read_text("instance name")
        tree_sha256: str = reader.read_text("staged tree digest")
        model_description_sha256: str = reader.read_text("model-description digest")
        tree_size: int = reader.read_unsigned_long("staged tree size")
        entry_count: int = reader.read_unsigned_int("staged entry count")
        encoded_float64_profile: int = (start_flags >> 2) & 3
        if encoded_float64_profile == 0:
            float64_profile: FmiThreeWorkerFloat64Profile = (
                FmiThreeWorkerFloat64Profile.SCALAR
            )
        else:
            if encoded_float64_profile == 1:
                float64_profile = FmiThreeWorkerFloat64Profile.CONSTANT_ARRAY
            else:
                if encoded_float64_profile == 2:
                    float64_profile = (
                        FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY
                    )
                else:
                    raise ValueError(
                        "FMI 3 worker START request has unknown flags"
                    )
        if start_flags & 16:
            interface_mode: FmuInterfaceMode = FmuInterfaceMode.MODEL_EXCHANGE
        else:
            interface_mode = FmuInterfaceMode.CO_SIMULATION
        staging_identity: FmiThreeWorkerStagingIdentity = FmiThreeWorkerStagingIdentity(
            tree_sha256=tree_sha256,
            model_description_sha256=model_description_sha256,
            tree_size=tree_size,
            entry_count=entry_count,
        )
        start = FmiThreeWorkerStartRequest(
            extracted_fmu_directory=extracted_fmu_directory,
            staging_identity=staging_identity,
            instantiation_token=instantiation_token,
            model_identifier=model_identifier,
            instance_name=instance_name,
            interface_mode=interface_mode,
            float64_profile=float64_profile,
            visible=bool(start_flags & 1),
            debug_logging=bool(start_flags & 2),
            early_return_allowed=bool(start_flags & 32),
        )
    else:
        if request_kind == FmiThreeWorkerRequestKind.INITIALIZE:
            initialization_flags: int = reader.read_unsigned_byte("INITIALIZE flags")
            if initialization_flags & ~3 == 0:
                pass
            else:
                raise ValueError("FMI 3 worker INITIALIZE request has unknown flags")
            start_time: float = reader.read_float64("start time")
            stop_time_offset: int = reader.offset
            encoded_stop_time: float = reader.read_float64("stop time")
            encoded_stop_time_bytes: bytes = reader.body[
                stop_time_offset:reader.offset
            ]
            tolerance_offset: int = reader.offset
            encoded_tolerance: float = reader.read_float64("relative tolerance")
            encoded_tolerance_bytes: bytes = reader.body[
                tolerance_offset:reader.offset
            ]
            if initialization_flags & 1:
                stop_time: float | None = encoded_stop_time
            else:
                if encoded_stop_time_bytes == b"\x00\x00\x00\x00\x00\x00\x00\x00":
                    stop_time = None
                else:
                    raise ValueError(
                        "FMI 3 worker absent stop time slot must be canonical zero"
                    )
            if initialization_flags & 2:
                relative_tolerance: float | None = encoded_tolerance
            else:
                if encoded_tolerance_bytes == b"\x00\x00\x00\x00\x00\x00\x00\x00":
                    relative_tolerance = None
                else:
                    raise ValueError(
                        "FMI 3 worker absent tolerance slot must be canonical zero"
                    )
            initial_float64_reference_count: int = reader.read_unsigned_int(
                "INITIALIZE Float64 reference count"
            )
            initial_float64_value_count: int = reader.read_unsigned_int(
                "INITIALIZE Float64 serialized value count"
            )
            float64_counts_are_valid: bool = (
                initial_float64_reference_count
                <= maximum_float64_values_per_request
                and initial_float64_value_count
                <= maximum_float64_values_per_request
                and (
                    initial_float64_reference_count > 0
                    or initial_float64_value_count == 0
                )
            )
            if float64_counts_are_valid:
                pass
            else:
                raise ValueError(
                    "FMI 3 worker initial Float64 count is outside its bound"
                )
            minimum_float64_tail_size: int = (
                initial_float64_reference_count * 4
                + initial_float64_value_count * 8
                + 8
            )
            if (
                len(reader.body) - reader.offset >= minimum_float64_tail_size
            ):
                pass
            else:
                raise ValueError(
                    "FMI 3 worker INITIALIZE Float64 collection is truncated"
                )
            initial_float64_references: list[int] = [0] * (
                initial_float64_reference_count
            )
            initial_float64_values: list[float] = [0.0] * (
                initial_float64_value_count
            )
            initial_index: int
            for initial_index in range(initial_float64_reference_count):
                initial_float64_references[initial_index] = (
                    reader.read_unsigned_int(
                        "INITIALIZE Float64 value reference"
                    )
                )
            for initial_index in range(initial_float64_value_count):
                initial_float64_values[initial_index] = reader.read_float64(
                    "INITIALIZE Float64 value"
                )
            initial_int32_reference_count: int = reader.read_unsigned_int(
                "INITIALIZE Int32 reference count"
            )
            initial_int32_value_count: int = reader.read_unsigned_int(
                "INITIALIZE Int32 value count"
            )
            validate_fmi_three_worker_initialization_frame_capacity(
                float64_value_reference_count=initial_float64_reference_count,
                float64_serialized_value_count=initial_float64_value_count,
                int32_value_reference_count=initial_int32_reference_count,
                int32_value_count=initial_int32_value_count,
                maximum_frame_size=maximum_frame_size,
                maximum_value_count=maximum_float64_values_per_request,
            )
            expected_int32_body_size: int = initial_int32_value_count * 8
            if len(reader.body) - reader.offset == expected_int32_body_size:
                pass
            else:
                raise ValueError(
                    "FMI 3 worker INITIALIZE Int32 collection body is inconsistent"
                )
            initial_int32_references: list[int] = [0] * (
                initial_int32_reference_count
            )
            initial_int32_values: list[int] = [0] * initial_int32_value_count
            for initial_index in range(initial_int32_reference_count):
                initial_int32_references[initial_index] = reader.read_unsigned_int(
                    "INITIALIZE Int32 value reference"
                )
            for initial_index in range(initial_int32_value_count):
                initial_int32_values[initial_index] = reader.read_signed_int(
                    "INITIALIZE Int32 value"
                )
            initialization = FmiThreeWorkerInitializationRequest(
                start_time=start_time,
                stop_time=stop_time,
                relative_tolerance=relative_tolerance,
                initial_float64_value_references=tuple(
                    initial_float64_references
                ),
                initial_float64_values=tuple(initial_float64_values),
                initial_int32_value_references=tuple(initial_int32_references),
                initial_int32_values=tuple(initial_int32_values),
                maximum_value_count=maximum_float64_values_per_request,
            )
        else:
            if request_kind == FmiThreeWorkerRequestKind.CONFIGURE_FLOAT64:
                configuration_reference_count: int = reader.read_unsigned_int(
                    "CONFIGURE_FLOAT64 reference count"
                )
                configuration_serialized_value_count: int = (
                    reader.read_unsigned_int(
                        "CONFIGURE_FLOAT64 serialized value count"
                    )
                )
                configuration_references: tuple[int, ...]
                configuration_values: tuple[float, ...]
                configuration_references, configuration_values = (
                    _decode_nonempty_float64_assignments(
                        reader=reader,
                        request_kind=request_kind,
                        field_prefix="CONFIGURE_FLOAT64",
                        value_reference_count=configuration_reference_count,
                        serialized_value_count=(
                            configuration_serialized_value_count
                        ),
                        maximum_frame_size=maximum_frame_size,
                        maximum_value_count=maximum_float64_values_per_request,
                    )
                )
                configuration = FmiThreeWorkerConfigureFloat64Request(
                    value_references=configuration_references,
                    values=configuration_values,
                    maximum_value_count=maximum_float64_values_per_request,
                )
            else:
                if request_kind == FmiThreeWorkerRequestKind.CONFIGURE_UINT64:
                    uint64_reference_count: int = reader.read_unsigned_int(
                        "CONFIGURE_UINT64 reference count"
                    )
                    uint64_value_count: int = reader.read_unsigned_int(
                        "CONFIGURE_UINT64 serialized value count"
                    )
                    configuration_uint64 = _decode_uint64_configuration(
                        reader=reader,
                        value_reference_count=uint64_reference_count,
                        serialized_value_count=uint64_value_count,
                        maximum_frame_size=maximum_frame_size,
                        maximum_value_count=maximum_float64_values_per_request,
                    )
                else:
                    if request_kind == FmiThreeWorkerRequestKind.SET_FLOAT64:
                        set_value_reference_count: int = reader.read_unsigned_int(
                            "SET_FLOAT64 reference count"
                        )
                        set_serialized_value_count: int = reader.read_unsigned_int(
                            "SET_FLOAT64 serialized value count"
                        )
                        set_references: tuple[int, ...]
                        set_values: tuple[float, ...]
                        set_references, set_values = (
                            _decode_nonempty_float64_assignments(
                                reader=reader,
                                request_kind=request_kind,
                                field_prefix="SET_FLOAT64",
                                value_reference_count=set_value_reference_count,
                                serialized_value_count=set_serialized_value_count,
                                maximum_frame_size=maximum_frame_size,
                                maximum_value_count=(
                                    maximum_float64_values_per_request
                                ),
                            )
                        )
                        set_float64 = FmiThreeWorkerSetFloat64Request(
                            value_references=set_references,
                            values=set_values,
                            maximum_value_count=maximum_float64_values_per_request,
                        )
                    else:
                        if request_kind == FmiThreeWorkerRequestKind.GET_FLOAT64:
                            get_value_reference_count: int = reader.read_unsigned_int(
                                "GET_FLOAT64 reference count"
                            )
                            get_serialized_value_count: int = reader.read_unsigned_int(
                                "GET_FLOAT64 serialized value count"
                            )
                            _validate_encoded_value_count(
                                value_count=get_value_reference_count,
                                maximum_value_count=(
                                    maximum_float64_values_per_request
                                ),
                                remaining_body_size=len(reader.body) - reader.offset,
                                bytes_per_value=4,
                                allow_zero=False,
                            )
                            validate_fmi_three_worker_float64_frame_capacity(
                                request_kind=request_kind,
                                value_reference_count=get_value_reference_count,
                                serialized_value_count=get_serialized_value_count,
                                maximum_frame_size=maximum_frame_size,
                                maximum_value_count=(
                                    maximum_float64_values_per_request
                                ),
                            )
                            get_references: list[int] = [0] * (
                                get_value_reference_count
                            )
                            get_index: int
                            for get_index in range(get_value_reference_count):
                                get_references[get_index] = reader.read_unsigned_int(
                                    "GET_FLOAT64 value reference"
                                )
                            get_float64 = FmiThreeWorkerGetFloat64Request(
                                value_references=tuple(get_references),
                                serialized_value_count=get_serialized_value_count,
                                maximum_value_count=(
                                    maximum_float64_values_per_request
                                ),
                            )
                        else:
                            if request_kind == FmiThreeWorkerRequestKind.DO_STEP:
                                step_flags: int = reader.read_unsigned_byte(
                                    "DO_STEP flags"
                                )
                                if step_flags & ~1 == 0:
                                    pass
                                else:
                                    raise ValueError(
                                        "FMI 3 worker DO_STEP request has unknown flags"
                                    )
                                current_communication_point: float = (
                                    reader.read_float64(
                                        "current communication point"
                                    )
                                )
                                communication_step_size: float = (
                                    reader.read_float64(
                                        "communication step size"
                                    )
                                )
                                do_step = FmiThreeWorkerDoStepRequest(
                                    current_communication_point=(
                                        current_communication_point
                                    ),
                                    communication_step_size=(
                                        communication_step_size
                                    ),
                                    no_set_fmu_state_prior_to_current_point=bool(
                                        step_flags & 1
                                    ),
                                )
                            else:
                                if request_kind == FmiThreeWorkerRequestKind.SET_TIME:
                                    set_time = FmiThreeWorkerSetTimeRequest(
                                        time_value=reader.read_float64(
                                            "Model Exchange time"
                                        )
                                    )
                                else:
                                    if (
                                        request_kind
                                        == FmiThreeWorkerRequestKind.SET_CONTINUOUS_STATES
                                    ):
                                        continuous_state_count: int = (
                                            reader.read_unsigned_int(
                                                "continuous-state count"
                                            )
                                        )
                                        _validate_encoded_value_count(
                                            value_count=continuous_state_count,
                                            maximum_value_count=(
                                                maximum_float64_values_per_request
                                            ),
                                            remaining_body_size=(
                                                len(reader.body) - reader.offset
                                            ),
                                            bytes_per_value=8,
                                            allow_zero=True,
                                        )
                                        decoded_continuous_states: list[float] = (
                                            [0.0] * continuous_state_count
                                        )
                                        continuous_state_index: int
                                        for continuous_state_index in range(
                                            continuous_state_count
                                        ):
                                            decoded_continuous_states[
                                                continuous_state_index
                                            ] = reader.read_float64(
                                                "continuous state"
                                            )
                                        continuous_states = (
                                            FmiThreeWorkerFloat64Values(
                                                values=tuple(
                                                    decoded_continuous_states
                                                ),
                                                maximum_value_count=(
                                                    maximum_float64_values_per_request
                                                ),
                                            )
                                        )
                                    else:
                                        if (
                                            request_kind
                                            == FmiThreeWorkerRequestKind.COMPLETED_INTEGRATOR_STEP
                                        ):
                                            integrator_step_flags: int = (
                                                reader.read_unsigned_byte(
                                                    "COMPLETED_INTEGRATOR_STEP flags"
                                                )
                                            )
                                            if integrator_step_flags & ~1 == 0:
                                                pass
                                            else:
                                                raise ValueError(
                                                    "FMI 3 worker "
                                                    "COMPLETED_INTEGRATOR_STEP "
                                                    "request has unknown flags"
                                                )
                                            completed_integrator_step = (
                                                FmiThreeWorkerCompletedIntegratorStepRequest(
                                                    no_set_fmu_state_prior_to_current_point=bool(
                                                        integrator_step_flags & 1
                                                    )
                                                )
                                            )
                                        else:
                                            if (
                                                request_kind
                                                == FmiThreeWorkerRequestKind.EVALUATE_MODEL_EXCHANGE
                                            ):
                                                evaluation_time: FmiThreeWorkerSetTimeRequest = (
                                                    FmiThreeWorkerSetTimeRequest(
                                                        time_value=reader.read_float64(
                                                            "Model Exchange evaluation time"
                                                        )
                                                    )
                                                )
                                                evaluation_state_count: int = (
                                                    reader.read_unsigned_int(
                                                        "Model Exchange state count"
                                                    )
                                                )
                                                if (
                                                    evaluation_state_count
                                                    <= maximum_float64_values_per_request
                                                ):
                                                    pass
                                                else:
                                                    raise ValueError(
                                                        "FMI 3 Model Exchange state count "
                                                        "is outside its bound"
                                                    )
                                                evaluation_state_values: list[float] = (
                                                    [0.0] * evaluation_state_count
                                                )
                                                evaluation_state_index: int
                                                for evaluation_state_index in range(
                                                    evaluation_state_count
                                                ):
                                                    evaluation_state_values[
                                                        evaluation_state_index
                                                    ] = reader.read_float64(
                                                        "Model Exchange state"
                                                    )
                                                evaluation_write_reference_count: int = (
                                                    reader.read_unsigned_int(
                                                        "Model Exchange write reference count"
                                                    )
                                                )
                                                evaluation_write_value_count: int = (
                                                    reader.read_unsigned_int(
                                                        "Model Exchange write value count"
                                                    )
                                                )
                                                write_counts_are_valid: bool = (
                                                    evaluation_write_reference_count
                                                    <= maximum_float64_values_per_request
                                                    and evaluation_write_value_count
                                                    <= maximum_float64_values_per_request
                                                    and (
                                                        evaluation_write_reference_count
                                                        > 0
                                                        or evaluation_write_value_count
                                                        == 0
                                                    )
                                                )
                                                if write_counts_are_valid:
                                                    pass
                                                else:
                                                    raise ValueError(
                                                        "FMI 3 Model Exchange write count "
                                                        "is outside its bound"
                                                    )
                                                evaluation_write_references: list[int] = (
                                                    [0]
                                                    * evaluation_write_reference_count
                                                )
                                                evaluation_write_values: list[float] = (
                                                    [0.0] * evaluation_write_value_count
                                                )
                                                evaluation_write_index: int
                                                for evaluation_write_index in range(
                                                    evaluation_write_reference_count
                                                ):
                                                    evaluation_write_references[
                                                        evaluation_write_index
                                                    ] = reader.read_unsigned_int(
                                                        "Model Exchange write reference"
                                                    )
                                                for evaluation_write_index in range(
                                                    evaluation_write_value_count
                                                ):
                                                    evaluation_write_values[
                                                        evaluation_write_index
                                                    ] = reader.read_float64(
                                                        "Model Exchange write value"
                                                    )
                                                if evaluation_write_reference_count > 0:
                                                    evaluation_set_float64: (
                                                        FmiThreeWorkerSetFloat64Request
                                                        | None
                                                    ) = FmiThreeWorkerSetFloat64Request(
                                                        value_references=tuple(
                                                            evaluation_write_references
                                                        ),
                                                        values=tuple(
                                                            evaluation_write_values
                                                        ),
                                                        maximum_value_count=(
                                                            maximum_float64_values_per_request
                                                        ),
                                                    )
                                                else:
                                                    evaluation_set_float64 = None
                                                evaluation_read_reference_count: int = (
                                                    reader.read_unsigned_int(
                                                        "Model Exchange read reference count"
                                                    )
                                                )
                                                evaluation_read_value_count: int = (
                                                    reader.read_unsigned_int(
                                                        "Model Exchange read value count"
                                                    )
                                                )
                                                read_counts_are_valid: bool = (
                                                    evaluation_read_reference_count
                                                    <= maximum_float64_values_per_request
                                                    and evaluation_read_value_count
                                                    <= maximum_float64_values_per_request
                                                    and (
                                                        evaluation_read_reference_count
                                                        > 0
                                                        or evaluation_read_value_count
                                                        == 0
                                                    )
                                                )
                                                if read_counts_are_valid:
                                                    pass
                                                else:
                                                    raise ValueError(
                                                        "FMI 3 Model Exchange read count "
                                                        "is outside its bound"
                                                    )
                                                evaluation_read_references: list[int] = (
                                                    [0]
                                                    * evaluation_read_reference_count
                                                )
                                                evaluation_read_index: int
                                                for evaluation_read_index in range(
                                                    evaluation_read_reference_count
                                                ):
                                                    evaluation_read_references[
                                                        evaluation_read_index
                                                    ] = reader.read_unsigned_int(
                                                        "Model Exchange read reference"
                                                    )
                                                if evaluation_read_reference_count > 0:
                                                    evaluation_get_float64: (
                                                        FmiThreeWorkerGetFloat64Request
                                                        | None
                                                    ) = FmiThreeWorkerGetFloat64Request(
                                                        value_references=tuple(
                                                            evaluation_read_references
                                                        ),
                                                        serialized_value_count=(
                                                            evaluation_read_value_count
                                                        ),
                                                        maximum_value_count=(
                                                            maximum_float64_values_per_request
                                                        ),
                                                    )
                                                else:
                                                    evaluation_get_float64 = None
                                                validate_fmi_three_worker_model_exchange_evaluation_frame_capacity(
                                                    continuous_state_count=(
                                                        evaluation_state_count
                                                    ),
                                                    writable_reference_count=(
                                                        evaluation_write_reference_count
                                                    ),
                                                    writable_value_count=(
                                                        evaluation_write_value_count
                                                    ),
                                                    readable_reference_count=(
                                                        evaluation_read_reference_count
                                                    ),
                                                    readable_value_count=(
                                                        evaluation_read_value_count
                                                    ),
                                                    maximum_frame_size=maximum_frame_size,
                                                    maximum_value_count=(
                                                        maximum_float64_values_per_request
                                                    ),
                                                )
                                                model_exchange_evaluation = (
                                                    FmiThreeWorkerModelExchangeEvaluationRequest(
                                                        set_time=evaluation_time,
                                                        continuous_states=(
                                                            FmiThreeWorkerFloat64Values(
                                                                values=tuple(
                                                                    evaluation_state_values
                                                                ),
                                                                maximum_value_count=(
                                                                    maximum_float64_values_per_request
                                                                ),
                                                            )
                                                        ),
                                                        set_float64=(
                                                            evaluation_set_float64
                                                        ),
                                                        get_float64=(
                                                            evaluation_get_float64
                                                        ),
                                                    )
                                                )
                                            else:
                                                if request_kind == FmiThreeWorkerRequestKind.SET_INT32:
                                                    int32_reference_count: int = reader.read_unsigned_int(
                                                        "SET_INT32 reference count"
                                                    )
                                                    int32_value_count: int = reader.read_unsigned_int(
                                                        "SET_INT32 value count"
                                                    )
                                                    int32_references: tuple[int, ...]
                                                    int32_values: tuple[int, ...]
                                                    int32_references, int32_values = (
                                                        _decode_nonempty_int32_assignments(
                                                            reader=reader,
                                                            request_kind=request_kind,
                                                            field_prefix="SET_INT32",
                                                            value_reference_count=int32_reference_count,
                                                            value_count=int32_value_count,
                                                            maximum_frame_size=maximum_frame_size,
                                                            maximum_value_count=maximum_float64_values_per_request,
                                                        )
                                                    )
                                                    set_int32 = FmiThreeWorkerSetInt32Request(
                                                        value_references=int32_references,
                                                        values=int32_values,
                                                        maximum_value_count=maximum_float64_values_per_request,
                                                    )
                                                else:
                                                    if request_kind == FmiThreeWorkerRequestKind.GET_INT32:
                                                        int32_reference_count = reader.read_unsigned_int(
                                                            "GET_INT32 reference count"
                                                        )
                                                        _validate_encoded_value_count(
                                                            value_count=int32_reference_count,
                                                            maximum_value_count=maximum_float64_values_per_request,
                                                            remaining_body_size=len(reader.body) - reader.offset,
                                                            bytes_per_value=4,
                                                            allow_zero=False,
                                                        )
                                                        validate_fmi_three_worker_int32_frame_capacity(
                                                            request_kind=request_kind,
                                                            value_count=int32_reference_count,
                                                            maximum_frame_size=maximum_frame_size,
                                                            maximum_value_count=maximum_float64_values_per_request,
                                                        )
                                                        int32_reference_values: list[int] = [0] * int32_reference_count
                                                        int32_index: int
                                                        for int32_index in range(int32_reference_count):
                                                            int32_reference_values[int32_index] = reader.read_unsigned_int(
                                                                "GET_INT32 value reference"
                                                            )
                                                        get_int32 = FmiThreeWorkerGetInt32Request(
                                                            value_references=tuple(int32_reference_values),
                                                            maximum_value_count=maximum_float64_values_per_request,
                                                        )
                                                    else:
                                                        pass
    reader.ensure_finished()
    return FmiThreeWorkerRequest(
        request_id=request_id,
        kind=request_kind,
        start=start,
        initialization=initialization,
        configuration=configuration,
        configuration_uint64=configuration_uint64,
        set_float64=set_float64,
        get_float64=get_float64,
        do_step=do_step,
        set_time=set_time,
        continuous_states=continuous_states,
        completed_integrator_step=completed_integrator_step,
        model_exchange_evaluation=model_exchange_evaluation,
        set_int32=set_int32,
        get_int32=get_int32,
    )


def encode_fmi_three_worker_response(
    response: FmiThreeWorkerResponse,
    maximum_frame_size: int,
    maximum_float64_values_per_request: int,
) -> bytes:
    """Encode one typed response without serializing exceptions.

    :param response: Validated response envelope.
    :param maximum_frame_size: Maximum complete frame size.
    :param maximum_float64_values_per_request: Maximum serialized-value count.
    :return: Complete binary response frame.
    """

    validate_fmi_three_worker_float64_value_limit(
        maximum_float64_values_per_request
    )
    if response.kind == FmiThreeWorkerResponseKind.ERROR:
        failure_kind: FmiThreeWorkerFailureKind | None = response.failure_kind
        error_message: str | None = response.error_message
        if failure_kind is not None and error_message is not None:
            pass
        else:
            raise ValueError("FMI 3 ERROR response is missing its typed fields")
        body: bytes = b"".join(
            (
                struct.pack("!B", int(failure_kind)),
                _encode_protocol_text(error_message, "error message"),
            )
        )
    else:
        if response.kind in (
            FmiThreeWorkerResponseKind.FLOAT64_VALUES,
            FmiThreeWorkerResponseKind.CONTINUOUS_STATES_VALUES,
            FmiThreeWorkerResponseKind.DERIVATIVE_VALUES,
            FmiThreeWorkerResponseKind.EVENT_INDICATOR_VALUES,
            FmiThreeWorkerResponseKind.CONTINUOUS_STATE_NOMINAL_VALUES,
        ):
            float64_values: FmiThreeWorkerFloat64Values | None = (
                response.float64_values
            )
            if float64_values is not None:
                body = _encode_float64_values_body(float64_values)
            else:
                raise ValueError("FMI 3 Float64 response is missing its typed body")
        else:
            if response.kind == FmiThreeWorkerResponseKind.STEP_COMPLETED:
                do_step_result: FmiThreeWorkerDoStepResult | None = (
                    response.do_step_result
                )
                if do_step_result is not None:
                    step_flags: int = int(do_step_result.event_handling_needed)
                    step_flags |= int(do_step_result.terminate_simulation) << 1
                    step_flags |= int(do_step_result.early_return) << 2
                    body = struct.pack(
                        "!Bd",
                        step_flags,
                        do_step_result.last_successful_time,
                    )
                else:
                    raise ValueError(
                        "FMI 3 STEP_COMPLETED response is missing its typed body"
                    )
            else:
                if (
                    response.kind
                    == FmiThreeWorkerResponseKind.INTEGRATOR_STEP_COMPLETED
                ):
                    completed_integrator_step_result: (
                        FmiThreeWorkerCompletedIntegratorStepResult | None
                    ) = response.completed_integrator_step_result
                    if completed_integrator_step_result is not None:
                        integrator_step_flags: int = int(
                            completed_integrator_step_result.enter_event_mode
                        )
                        integrator_step_flags |= int(
                            completed_integrator_step_result.terminate_simulation
                        ) << 1
                        body = struct.pack("!B", integrator_step_flags)
                    else:
                        raise ValueError(
                            "FMI 3 INTEGRATOR_STEP_COMPLETED response is missing "
                            "its typed body"
                        )
                else:
                    if (
                        response.kind
                        == FmiThreeWorkerResponseKind.DISCRETE_STATES_UPDATED
                    ):
                        discrete_states_result: (
                            FmiThreeWorkerDiscreteStatesResult | None
                        ) = response.discrete_states_result
                        if discrete_states_result is not None:
                            discrete_state_flags: int = int(
                                discrete_states_result.discrete_states_need_update
                            )
                            discrete_state_flags |= int(
                                discrete_states_result.terminate_simulation
                            ) << 1
                            discrete_state_flags |= int(
                                discrete_states_result.nominals_of_continuous_states_changed
                            ) << 2
                            discrete_state_flags |= int(
                                discrete_states_result.values_of_continuous_states_changed
                            ) << 3
                            discrete_state_flags |= int(
                                discrete_states_result.next_event_time_defined
                            ) << 4
                            body = struct.pack(
                                "!Bd",
                                discrete_state_flags,
                                discrete_states_result.next_event_time,
                            )
                        else:
                            raise ValueError(
                                "FMI 3 DISCRETE_STATES_UPDATED response is missing "
                                "its typed body"
                            )
                    else:
                        if (
                            response.kind
                            == FmiThreeWorkerResponseKind.MODEL_EXCHANGE_EVALUATED
                        ):
                            evaluation_result: (
                                FmiThreeWorkerModelExchangeEvaluationResult
                                | None
                            ) = response.model_exchange_evaluation_result
                            if evaluation_result is not None:
                                evaluation_result_counts_are_valid: bool = (
                                    len(evaluation_result.derivatives.values)
                                    <= maximum_float64_values_per_request
                                    and len(
                                        evaluation_result.readable_values.values
                                    )
                                    <= maximum_float64_values_per_request
                                )
                            else:
                                evaluation_result_counts_are_valid = False
                            if (
                                evaluation_result is not None
                                and evaluation_result_counts_are_valid
                            ):
                                body = _encode_model_exchange_evaluation_result_body(
                                    evaluation_result
                                )
                            else:
                                raise ValueError(
                                    "FMI 3 MODEL_EXCHANGE_EVALUATED response is "
                                    "missing or exceeds its typed body bound"
                                )
                        else:
                            if response.kind == FmiThreeWorkerResponseKind.INT32_VALUES:
                                int32_values: FmiThreeWorkerInt32Values | None = (
                                    response.int32_values
                                )
                                if int32_values is not None:
                                    body = _encode_int32_values_body(int32_values)
                                else:
                                    raise ValueError(
                                        "FMI 3 INT32_VALUES response is missing its typed body"
                                    )
                            else:
                                body = b""
    return _encode_worker_frame(
        FmiThreeWorkerFrameDirection.RESPONSE,
        int(response.kind),
        response.request_id,
        body,
        maximum_frame_size,
    )


def decode_fmi_three_worker_response(
    frame: bytes,
    maximum_frame_size: int,
    maximum_float64_values_per_request: int,
) -> FmiThreeWorkerResponse:
    """Decode one bounded response without deserializing exceptions.

    :param frame: Complete binary response frame.
    :param maximum_frame_size: Maximum accepted frame size.
    :param maximum_float64_values_per_request: Maximum serialized-value count.
    :return: Validated typed response envelope.
    """

    validate_fmi_three_worker_float64_value_limit(
        maximum_float64_values_per_request
    )
    response_number: int
    request_id: int
    body: bytes
    response_number, request_id, body = _decode_worker_frame(
        frame,
        FmiThreeWorkerFrameDirection.RESPONSE,
        maximum_frame_size,
    )
    try:
        response_kind: FmiThreeWorkerResponseKind = FmiThreeWorkerResponseKind(
            response_number
        )
    except ValueError as error:
        raise ValueError(f"Unknown FMI 3 worker response kind {response_number}") from error
    reader: _FmiThreeWorkerBodyReader = _FmiThreeWorkerBodyReader(body)
    failure_kind: FmiThreeWorkerFailureKind | None = None
    error_message: str | None = None
    float64_values: FmiThreeWorkerFloat64Values | None = None
    do_step_result: FmiThreeWorkerDoStepResult | None = None
    completed_integrator_step_result: (
        FmiThreeWorkerCompletedIntegratorStepResult | None
    ) = None
    discrete_states_result: FmiThreeWorkerDiscreteStatesResult | None = None
    model_exchange_evaluation_result: (
        FmiThreeWorkerModelExchangeEvaluationResult | None
    ) = None
    int32_values: FmiThreeWorkerInt32Values | None = None
    if response_kind == FmiThreeWorkerResponseKind.ERROR:
        failure_number: int = reader.read_unsigned_byte("failure kind")
        try:
            failure_kind = FmiThreeWorkerFailureKind(failure_number)
        except ValueError as error:
            raise ValueError(f"Unknown FMI 3 worker failure kind {failure_number}") from error
        error_message = reader.read_text("error message")
    else:
        if response_kind in (
            FmiThreeWorkerResponseKind.FLOAT64_VALUES,
            FmiThreeWorkerResponseKind.CONTINUOUS_STATES_VALUES,
            FmiThreeWorkerResponseKind.DERIVATIVE_VALUES,
            FmiThreeWorkerResponseKind.EVENT_INDICATOR_VALUES,
            FmiThreeWorkerResponseKind.CONTINUOUS_STATE_NOMINAL_VALUES,
        ):
            value_count: int = reader.read_unsigned_int("FLOAT64_VALUES count")
            _validate_encoded_value_count(
                value_count=value_count,
                maximum_value_count=maximum_float64_values_per_request,
                remaining_body_size=len(reader.body) - reader.offset,
                bytes_per_value=8,
                allow_zero=True,
            )
            decoded_values: list[float] = [0.0] * value_count
            value_index: int
            for value_index in range(value_count):
                decoded_values[value_index] = reader.read_float64("Float64 value")
            float64_values = FmiThreeWorkerFloat64Values(
                values=tuple(decoded_values),
                maximum_value_count=maximum_float64_values_per_request,
            )
        else:
            if response_kind == FmiThreeWorkerResponseKind.STEP_COMPLETED:
                step_flags: int = reader.read_unsigned_byte("STEP_COMPLETED flags")
                if step_flags & ~7 == 0:
                    pass
                else:
                    raise ValueError(
                        "FMI 3 worker STEP_COMPLETED response has unknown flags"
                    )
                do_step_result = FmiThreeWorkerDoStepResult(
                    event_handling_needed=bool(step_flags & 1),
                    terminate_simulation=bool(step_flags & 2),
                    early_return=bool(step_flags & 4),
                    last_successful_time=reader.read_float64(
                        "last successful time"
                    ),
                )
            else:
                if (
                    response_kind
                    == FmiThreeWorkerResponseKind.INTEGRATOR_STEP_COMPLETED
                ):
                    integrator_step_flags: int = reader.read_unsigned_byte(
                        "INTEGRATOR_STEP_COMPLETED flags"
                    )
                    if integrator_step_flags & ~3 == 0:
                        pass
                    else:
                        raise ValueError(
                            "FMI 3 worker INTEGRATOR_STEP_COMPLETED response "
                            "has unknown flags"
                        )
                    completed_integrator_step_result = (
                        FmiThreeWorkerCompletedIntegratorStepResult(
                            enter_event_mode=bool(integrator_step_flags & 1),
                            terminate_simulation=bool(integrator_step_flags & 2),
                        )
                    )
                else:
                    if (
                        response_kind
                        == FmiThreeWorkerResponseKind.DISCRETE_STATES_UPDATED
                    ):
                        discrete_state_flags: int = reader.read_unsigned_byte(
                            "DISCRETE_STATES_UPDATED flags"
                        )
                        if discrete_state_flags & ~31 == 0:
                            pass
                        else:
                            raise ValueError(
                                "FMI 3 worker DISCRETE_STATES_UPDATED response "
                                "has unknown flags"
                            )
                        discrete_states_result = FmiThreeWorkerDiscreteStatesResult(
                            discrete_states_need_update=bool(
                                discrete_state_flags & 1
                            ),
                            terminate_simulation=bool(discrete_state_flags & 2),
                            nominals_of_continuous_states_changed=bool(
                                discrete_state_flags & 4
                            ),
                            values_of_continuous_states_changed=bool(
                                discrete_state_flags & 8
                            ),
                            next_event_time_defined=bool(
                                discrete_state_flags & 16
                            ),
                            next_event_time=reader.read_float64(
                                "next event time"
                            ),
                        )
                    else:
                        if (
                            response_kind
                            == FmiThreeWorkerResponseKind.MODEL_EXCHANGE_EVALUATED
                        ):
                            derivative_count: int = reader.read_unsigned_int(
                                "Model Exchange derivative count"
                            )
                            if (
                                derivative_count
                                <= maximum_float64_values_per_request
                            ):
                                pass
                            else:
                                raise ValueError(
                                    "FMI 3 Model Exchange derivative count is "
                                    "outside its bound"
                                )
                            derivative_values: list[float] = (
                                [0.0] * derivative_count
                            )
                            derivative_index: int
                            for derivative_index in range(derivative_count):
                                derivative_values[
                                    derivative_index
                                ] = reader.read_float64(
                                    "Model Exchange derivative"
                                )
                            readable_value_count: int = reader.read_unsigned_int(
                                "Model Exchange readable value count"
                            )
                            if (
                                readable_value_count
                                <= maximum_float64_values_per_request
                            ):
                                pass
                            else:
                                raise ValueError(
                                    "FMI 3 Model Exchange readable value count "
                                    "is outside its bound"
                                )
                            readable_values: list[float] = (
                                [0.0] * readable_value_count
                            )
                            readable_value_index: int
                            for readable_value_index in range(
                                readable_value_count
                            ):
                                readable_values[
                                    readable_value_index
                                ] = reader.read_float64(
                                    "Model Exchange readable value"
                                )
                            model_exchange_evaluation_result = (
                                FmiThreeWorkerModelExchangeEvaluationResult(
                                    derivatives=FmiThreeWorkerFloat64Values(
                                        values=tuple(derivative_values),
                                        maximum_value_count=(
                                            maximum_float64_values_per_request
                                        ),
                                    ),
                                    readable_values=FmiThreeWorkerFloat64Values(
                                        values=tuple(readable_values),
                                        maximum_value_count=(
                                            maximum_float64_values_per_request
                                        ),
                                    ),
                                )
                            )
                        else:
                            if response_kind == FmiThreeWorkerResponseKind.INT32_VALUES:
                                int32_value_count: int = reader.read_unsigned_int(
                                    "INT32_VALUES count"
                                )
                                _validate_encoded_value_count(
                                    value_count=int32_value_count,
                                    maximum_value_count=maximum_float64_values_per_request,
                                    remaining_body_size=len(reader.body) - reader.offset,
                                    bytes_per_value=4,
                                    allow_zero=True,
                                )
                                decoded_int32_values: list[int] = [0] * int32_value_count
                                int32_index: int
                                for int32_index in range(int32_value_count):
                                    decoded_int32_values[int32_index] = reader.read_signed_int(
                                        "Int32 value"
                                    )
                                int32_values = FmiThreeWorkerInt32Values(
                                    values=tuple(decoded_int32_values),
                                    maximum_value_count=maximum_float64_values_per_request,
                                )
                            else:
                                pass
    reader.ensure_finished()
    return FmiThreeWorkerResponse(
        request_id=request_id,
        kind=response_kind,
        failure_kind=failure_kind,
        error_message=error_message,
        float64_values=float64_values,
        do_step_result=do_step_result,
        completed_integrator_step_result=completed_integrator_step_result,
        discrete_states_result=discrete_states_result,
        model_exchange_evaluation_result=model_exchange_evaluation_result,
        int32_values=int32_values,
    )


def validate_fmi_three_worker_response_correlation(
    response: FmiThreeWorkerResponse,
    expected_request_id: int,
    expected_response_kind: FmiThreeWorkerResponseKind,
) -> None:
    """Require a response to match the outstanding request and operation.

    A typed ERROR may answer any request. Successful responses must also match
    the exact successful outcome expected by the parent state machine.

    :param response: Decoded worker response.
    :param expected_request_id: Identifier of the outstanding request.
    :param expected_response_kind: Successful outcome for that request.
    :return: None.
    """

    _validate_request_id(expected_request_id)
    if response.request_id == expected_request_id:
        pass
    else:
        raise ValueError("FMI 3 worker response request id does not match")
    if (
        response.kind == expected_response_kind
        or response.kind == FmiThreeWorkerResponseKind.ERROR
    ):
        pass
    else:
        raise ValueError("FMI 3 worker response kind does not match the operation")


def build_fmi_three_worker_staging_identity(
    receipt: FmuInspectionReceipt,
) -> FmiThreeWorkerStagingIdentity:
    """Build the wire identity from one inspected private FMU directory.

    The parent uses its authoritative staging receipt, while the child uses a
    fresh receipt obtained immediately before native construction. Both sides
    therefore share one exact mapping instead of duplicating identity rules.

    :param receipt: Inspection receipt for a private staged directory.
    :return: Typed staging identity suitable for a START request.
    :raises ValueError: If the receipt does not describe a directory tree.
    """

    if receipt.source_kind == FmuSourceKind.DIRECTORY:
        pass
    else:
        raise ValueError(
            "FMI 3 worker staging identity requires a directory inspection receipt"
        )
    identity: FmiThreeWorkerStagingIdentity = FmiThreeWorkerStagingIdentity(
        tree_sha256=receipt.sha256,
        model_description_sha256=receipt.model_description_sha256,
        tree_size=receipt.source_size,
        entry_count=receipt.entry_count,
    )
    return identity


def validate_fmi_three_worker_staging_identity(
    expected: FmiThreeWorkerStagingIdentity,
    observed_receipt: FmuInspectionReceipt,
) -> None:
    """Require a fresh child-side inspection to match the START identity.

    :param expected: Identity sent by the parent in the START request.
    :param observed_receipt: Fresh receipt produced in the worker process.
    :return: None.
    :raises ValueError: If kind, digests, size, or cardinality differ.
    """

    observed: FmiThreeWorkerStagingIdentity = (
        build_fmi_three_worker_staging_identity(observed_receipt)
    )
    identity_matches: bool = (
        observed.tree_sha256 == expected.tree_sha256
        and observed.model_description_sha256 == expected.model_description_sha256
        and observed.tree_size == expected.tree_size
        and observed.entry_count == expected.entry_count
    )
    if identity_matches:
        pass
    else:
        raise ValueError(
            "FMI 3 worker staging identity changed before native construction"
        )


def send_fmi_three_worker_frame(
    connection: Connection,
    frame: bytes,
    maximum_frame_size: int,
) -> None:
    """Send one validated bytes frame without invoking pickle.

    :param connection: Dedicated worker connection.
    :param frame: Complete encoded frame.
    :param maximum_frame_size: Maximum accepted transport size.
    :return: None.
    """

    _validate_frame_size(frame, maximum_frame_size)
    connection.send_bytes(frame)


def receive_fmi_three_worker_frame(
    connection: Connection,
    maximum_frame_size: int,
) -> bytes:
    """Receive one frame with allocation bounded inside ``Connection``.

    :param connection: Dedicated worker connection.
    :param maximum_frame_size: Maximum bytes accepted by ``recv_bytes``.
    :return: Complete bounded frame.
    """

    if maximum_frame_size > 0:
        pass
    else:
        raise ValueError("FMI 3 worker maximum frame size must be positive")
    frame: bytes = connection.recv_bytes(maxlength=maximum_frame_size)
    _validate_frame_size(frame, maximum_frame_size)
    return frame
