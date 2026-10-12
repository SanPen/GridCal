# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Fail-closed capability gates for bounded FMU runtime profiles."""

from __future__ import annotations
from VeraGridEngine.enumerations import FmiThreeWorkerFloat64Profile


from VeraGridEngine.IO.fmu.Elements.description import (
    FmiThreeCoSimulationCapabilities,
    FmiThreeModelExchangeCapabilities,
    FmuModelDescription,
    FmuVariableDescription,
)
from VeraGridEngine.enumerations import (
    FmiThreeVariableCausality,
    FmuInterfaceMode,
    FmuVariableType,
)




class FmuMeEvaluationBudget:
    """Bound runtime-boundary invocations for one FMI ME transaction.

    The counter deliberately has no reset operation. A simulation owner
    creates a new instance for initialization or for one solver step and shares
    that exact instance across every attached Model Exchange device.

    :param maximum_operations: Positive maximum number of runtime calls.
    """

    __slots__ = ("_maximum_operations", "_consumed_count")

    def __init__(self, maximum_operations: int) -> None:
        """Initialize an empty bounded counter.

        :param maximum_operations: Integer limit between 1 and 10,000,000.
        :return: None.
        """

        if (
            isinstance(maximum_operations, int)
            and not isinstance(maximum_operations, bool)
            and 1 <= maximum_operations <= 10_000_000
        ):
            self._maximum_operations: int = maximum_operations
        else:
            raise ValueError(
                "FMI ME runtime evaluation limit must be an integer between "
                "1 and 10000000"
            )
        self._consumed_count: int = 0

    def consume(self) -> None:
        """Reserve one runtime-boundary invocation before it is executed.

        :return: None.
        :raises RuntimeError: If the configured limit is already exhausted.
        """

        if self._consumed_count < self._maximum_operations:
            self._consumed_count += 1
        else:
            raise RuntimeError(
                "FMI ME runtime evaluation budget was exhausted before the "
                "next native call"
            )

    def get_consumed_count(self) -> int:
        """Return the number of runtime-boundary invocations already reserved.

        :return: Current monotonically increasing count.
        """

        return self._consumed_count


def resolve_fmi_three_worker_float64_profile(
    metadata: FmuModelDescription,
) -> FmiThreeWorkerFloat64Profile:
    """Select the narrowest worker shape profile declared by one FMI 3 model.

    Referenced dimensions require Configuration Mode because their cardinality
    can change before initialization. Models with only literal dimensions use
    the constant-array path, while models without dimensions remain scalar.

    :param metadata: Authoritative parsed FMI 3 model description.
    :return: Narrowest worker profile that preserves every declared dimension.
    """

    selected_profile: FmiThreeWorkerFloat64Profile = (
        FmiThreeWorkerFloat64Profile.SCALAR
    )
    declared_variable: FmuVariableDescription
    for declared_variable in metadata.variables:
        dimension_index: int
        for dimension_index in range(len(declared_variable.dimensions)):
            if (
                declared_variable.dimensions[dimension_index].value_reference
                is not None
            ):
                selected_profile = (
                    FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY
                )
            else:
                if selected_profile == FmiThreeWorkerFloat64Profile.SCALAR:
                    selected_profile = FmiThreeWorkerFloat64Profile.CONSTANT_ARRAY
                else:
                    pass
    return selected_profile


def is_fmi_three_input_or_tunable_parameter(
    variable: FmuVariableDescription,
) -> bool:
    """Return whether one scalar is an input or tunable parameter.

    :param variable: Parsed FMI 3 scalar-variable metadata.
    :return: ``True`` for inputs and tunable parameters, otherwise ``False``.
    """

    if variable.causality is not None:
        causality: FmiThreeVariableCausality = FmiThreeVariableCausality(
            variable.causality
        )
        return causality == FmiThreeVariableCausality.INPUT or (
            causality == FmiThreeVariableCausality.PARAMETER
            and variable.variability == "tunable"
        )
    else:
        return False


def is_fmi_three_initialization_mode_writable(
    variable: FmuVariableDescription,
) -> bool:
    """Return whether Initialization Mode permits writing one scalar.

    Structural parameters belong to Configuration Mode. For the remaining
    variables, FMI 3 permits non-constant variables whose initial value is exact
    to be set while initialization equations are active.

    :param variable: Parsed FMI 3 scalar-variable metadata.
    :return: ``True`` only for a scalar writable in Initialization Mode.
    """

    if variable.causality is not None:
        causality: FmiThreeVariableCausality = FmiThreeVariableCausality(
            variable.causality
        )
        return (
            causality != FmiThreeVariableCausality.STRUCTURAL_PARAMETER
            and variable.variability != "constant"
            and variable.initial == "exact"
        )
    else:
        return False


def is_fmi_three_configuration_mode_writable(
    variable: FmuVariableDescription,
) -> bool:
    """Return whether Configuration Mode permits writing one variable.

    :param variable: Parsed FMI 3 variable metadata.
    :return: ``True`` only for a declared structural parameter.
    """

    if variable.causality is not None:
        causality: FmiThreeVariableCausality = FmiThreeVariableCausality(
            variable.causality
        )
        return causality == FmiThreeVariableCausality.STRUCTURAL_PARAMETER
    else:
        return False


def resolve_fmi_three_configuration_float64_writable_references(
    metadata: FmuModelDescription,
) -> frozenset[int]:
    """Resolve the Float64 ACL required during Configuration Mode.

    :param metadata: Parsed FMI 3 model description.
    :return: Immutable structural-parameter value references.
    """

    writable_count: int = 0
    declared_variable: FmuVariableDescription
    for declared_variable in metadata.variables:
        if (
            is_fmi_three_configuration_mode_writable(declared_variable)
            and declared_variable.variable_type == FmuVariableType.FLOAT64
        ):
            writable_count += 1
        else:
            pass
    writable_references: list[int] = [0] * writable_count
    writable_index: int = 0
    for declared_variable in metadata.variables:
        if (
            is_fmi_three_configuration_mode_writable(declared_variable)
            and declared_variable.variable_type == FmuVariableType.FLOAT64
        ):
            writable_references[writable_index] = declared_variable.value_reference
            writable_index += 1
        else:
            pass
    return frozenset(writable_references)


def resolve_fmi_three_configuration_uint64_writable_references(
    metadata: FmuModelDescription,
) -> frozenset[int]:
    """Resolve the scalar UInt64 ACL required during Configuration Mode.

    :param metadata: Parsed FMI 3 model description.
    :return: Immutable structural UInt64 parameter value references.
    """

    writable_count: int = 0
    declared_variable: FmuVariableDescription
    for declared_variable in metadata.variables:
        if (
            is_fmi_three_configuration_mode_writable(declared_variable)
            and declared_variable.variable_type == FmuVariableType.UINT64
            and len(declared_variable.dimensions) == 0
        ):
            writable_count += 1
        else:
            pass
    writable_references: list[int] = [0] * writable_count
    writable_index: int = 0
    for declared_variable in metadata.variables:
        if (
            is_fmi_three_configuration_mode_writable(declared_variable)
            and declared_variable.variable_type == FmuVariableType.UINT64
            and len(declared_variable.dimensions) == 0
        ):
            writable_references[writable_index] = declared_variable.value_reference
            writable_index += 1
        else:
            pass
    return frozenset(writable_references)


def resolve_fmi_three_initialization_writable_references(
    metadata: FmuModelDescription,
) -> frozenset[int]:
    """Resolve the minimal scalar ACL needed during Initialization Mode.

    Parent and child call this function on independently parsed metadata. Only
    immutable value references cross later lifecycle layers.

    :param metadata: Parsed FMI 3 model description.
    :return: Immutable references writable while initialization is active.
    """

    writable_count: int = 0
    declared_variable: FmuVariableDescription
    for declared_variable in metadata.variables:
        if is_fmi_three_initialization_mode_writable(declared_variable):
            writable_count += 1
        else:
            pass
    writable_references: list[int] = [0] * writable_count
    writable_index: int = 0
    for declared_variable in metadata.variables:
        if is_fmi_three_initialization_mode_writable(declared_variable):
            writable_references[writable_index] = declared_variable.value_reference
            writable_index += 1
        else:
            pass
    return frozenset(writable_references)


def _validate_fmi_three_worker_variable_profile(
    metadata: FmuModelDescription,
    float64_profile: FmiThreeWorkerFloat64Profile,
) -> None:
    """Validate the shared bounded primitive and array-shape profile.

    :param metadata: Parsed FMI 3 model description.
    :param float64_profile: Bounded scalar, constant-array, or configurable-array
        shape.
    :return: None.
    :raises RuntimeError: If a variable cannot use the bounded worker transport.
    """

    # Every currently executable variable must use the one bounded primitive
    # transported by this profile. Constant dimensions are validated separately.
    dimension_source_references: set[int] = set()
    dimension_owner_variable: FmuVariableDescription
    for dimension_owner_variable in metadata.variables:
        dimension_index: int
        for dimension_index in range(len(dimension_owner_variable.dimensions)):
            dimension_value_reference: int | None = (
                dimension_owner_variable.dimensions[dimension_index].value_reference
            )
            if dimension_value_reference is not None:
                dimension_source_references.add(dimension_value_reference)
            else:
                pass
    declared_variable: FmuVariableDescription
    for declared_variable in metadata.variables:
        if float64_profile == FmiThreeWorkerFloat64Profile.SCALAR:
            if len(declared_variable.dimensions) == 0:
                pass
            else:
                raise RuntimeError(
                    "FMI 3 arrays are outside the initial scalar worker profile"
                )
        else:
            if float64_profile == FmiThreeWorkerFloat64Profile.CONSTANT_ARRAY:
                dimensions_are_constant: bool = True
                dimension_index: int
                for dimension_index in range(len(declared_variable.dimensions)):
                    if (
                        declared_variable.dimensions[dimension_index].constant_size
                        is not None
                    ):
                        pass
                    else:
                        dimensions_are_constant = False
                if dimensions_are_constant:
                    pass
                else:
                    raise RuntimeError(
                        "FMI 3 dimensions controlled by valueReference remain "
                        "outside the constant-array worker profile"
                    )
            else:
                if (
                    float64_profile
                    == FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY
                ):
                    pass
                else:
                    raise RuntimeError("Unsupported FMI 3 worker Float64 profile")
        if declared_variable.variable_type == FmuVariableType.FLOAT64:
            pass
        else:
            int32_is_supported: bool = (
                declared_variable.variable_type == FmuVariableType.INT32
                and len(declared_variable.dimensions) == 0
            )
            uint64_is_supported: bool = (
                declared_variable.variable_type == FmuVariableType.UINT64
                and len(declared_variable.dimensions) == 0
                and (
                    is_fmi_three_configuration_mode_writable(declared_variable)
                    or (
                        float64_profile
                        == FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY
                        and declared_variable.variability == "constant"
                        and declared_variable.value_reference
                        in dimension_source_references
                    )
                )
            )
            if int32_is_supported or uint64_is_supported:
                pass
            else:
                raise RuntimeError(
                    "The FMI 3 worker profile supports Float64 variables, "
                    "scalar Int32 variables, and scalar structural UInt64 "
                    "parameters"
                )


def validate_fmi_three_co_simulation_worker_profile(
    metadata: FmuModelDescription,
    preferred_mode: FmuInterfaceMode | None,
    float64_profile: FmiThreeWorkerFloat64Profile = (
        FmiThreeWorkerFloat64Profile.SCALAR
    ),
) -> None:
    """Validate the bounded FMI 3 Co-Simulation worker profile.

    External execution tools remain outside this lifecycle. Optional
    Intermediate Update, Event Mode, and early-return capabilities may be
    advertised because worker construction explicitly declines them and the
    completed-step validator rejects any unnegotiated result. Variable and
    array bounds are shared with Model Exchange through one profile owner.

    :param metadata: Parsed FMI 3 model description.
    :param preferred_mode: Optional interface requested by the caller.
    :param float64_profile: Bounded scalar, constant-array, or configurable-array
        shape.
    :return: None.
    :raises RuntimeError: If the FMU requires an unsupported worker capability.
    """

    selected_mode: FmuInterfaceMode = metadata.select_declared_interface(preferred_mode)
    if selected_mode == FmuInterfaceMode.CO_SIMULATION:
        pass
    else:
        raise RuntimeError(
            "The initial FMI 3 worker profile supports only Co-Simulation"
        )
    capabilities: FmiThreeCoSimulationCapabilities | None = (
        metadata.fmi_three_co_simulation_capabilities
    )
    if capabilities is not None:
        pass
    else:
        raise RuntimeError("FMI 3 Co-Simulation capabilities are unavailable")
    if capabilities.needs_execution_tool:
        raise RuntimeError(
            "FMI 3 FMUs that need an external execution tool are not supported"
        )
    else:
        pass
    # Event-indicator declarations are shared metadata for dual-interface FMUs.
    # They do not require a Co-Simulation importer to activate optional Event
    # Mode; that negotiation remains explicit at native construction.
    _validate_fmi_three_worker_variable_profile(metadata, float64_profile)


def validate_fmi_three_model_exchange_worker_profile(
    metadata: FmuModelDescription,
    preferred_mode: FmuInterfaceMode | None,
    float64_profile: FmiThreeWorkerFloat64Profile = (
        FmiThreeWorkerFloat64Profile.SCALAR
    ),
) -> None:
    """Validate the bounded FMI 3 Model Exchange worker profile.

    The isolated Model Exchange lifecycle supports bounded state, derivative,
    event-indicator, nominal, and Event Mode operations. FMUs requiring an
    external execution tool remain outside this profile.

    :param metadata: Parsed FMI 3 model description.
    :param preferred_mode: Optional interface requested by the caller.
    :param float64_profile: Bounded scalar, constant-array, or configurable-array
        shape.
    :return: None.
    :raises RuntimeError: If the FMU requires an unsupported worker capability.
    """

    selected_mode: FmuInterfaceMode = metadata.select_declared_interface(preferred_mode)
    if selected_mode == FmuInterfaceMode.MODEL_EXCHANGE:
        pass
    else:
        raise RuntimeError("The FMI 3 worker profile requires Model Exchange")
    capabilities: FmiThreeModelExchangeCapabilities | None = (
        metadata.fmi_three_model_exchange_capabilities
    )
    if capabilities is not None:
        pass
    else:
        raise RuntimeError("FMI 3 Model Exchange capabilities are unavailable")
    if capabilities.needs_execution_tool:
        raise RuntimeError(
            "FMI 3 FMUs that need an external execution tool are not supported"
        )
    else:
        pass
    _validate_fmi_three_worker_variable_profile(metadata, float64_profile)
