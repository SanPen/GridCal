# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from VeraGridEngine.enumerations import FmuBindingDirection

from enum import Enum
import math
from pathlib import Path
from typing import cast

from VeraGridEngine.IO.fmu.Elements.description import (
    FmiOneCoSimulationCapabilities,
    FmiThreeVariableDimension,
    FmuModelDescription,
    FmuVariableDescription,
)
from VeraGridEngine.IO.fmu.profile import (
    FmiThreeWorkerFloat64Profile,
    is_fmi_three_configuration_mode_writable,
    is_fmi_three_initialization_mode_writable,
    is_fmi_three_input_or_tunable_parameter,
    validate_fmi_three_co_simulation_worker_profile,
    validate_fmi_three_model_exchange_worker_profile,
)
from VeraGridEngine.IO.fmu.Elements.protocol import (
    validate_fmi_three_worker_float64_value_limit,
)
from VeraGridEngine.enumerations import (
    FmiVersion,
    FmuInterfaceMode,
    FmuVariableType,
    VarPowerFlowReferenceType,
)




class FmuVariableBinding:
    """Describe one logical binding between VeraGrid and an FMU variable."""

    __slots__ = ("signal_name", "variable_name", "direction", "scale", "offset")

    def __init__(
        self,
        signal_name: str,
        variable_name: str,
        direction: FmuBindingDirection,
        scale: float = 1.0,
        offset: float = 0.0,
    ) -> None:
        """Store the FMU binding metadata for one signal."""

        self.signal_name: str = signal_name
        self.variable_name: str = variable_name
        self.direction: FmuBindingDirection = direction
        self.scale: float = float(scale)
        self.offset: float = float(offset)


class FmuFloat64ParameterValue:
    """Store one finite scalar floating-point FMU parameter value.

    This runtime declaration contains no persistence identity beyond the FMU
    variable name. Persistent numeric ownership remains in ``Block.parameters``.

    :param variable_name: Non-empty FMU parameter variable name.
    :param value: Finite scalar parameter value.
    """

    __slots__ = ("variable_name", "value")

    def __init__(self, variable_name: str, value: float) -> None:
        """Validate and store one scalar FMU parameter value.

        :param variable_name: Non-empty FMU parameter variable name.
        :param value: Finite real value; booleans are not numeric source data.
        :return: None.
        """

        if isinstance(variable_name, str) and len(variable_name.strip()) > 0:
            self.variable_name: str = variable_name
        else:
            raise ValueError("FMU parameter variable name is empty")
        value_is_numeric: bool = (
            isinstance(value, (int, float)) and not isinstance(value, bool)
        )
        if value_is_numeric:
            normalized_value: float = float(value)
            if math.isfinite(normalized_value):
                self.value: float = normalized_value
            else:
                raise ValueError("FMU parameter value must be finite")
        else:
            raise ValueError("FMU parameter value must be a real scalar")


def validate_fmu_float64_parameter_values(
    parameter_values: tuple[FmuFloat64ParameterValue, ...],
    metadata: FmuModelDescription | None = None,
    reserved_variable_names: tuple[str, ...] = tuple(),
) -> None:
    """Validate a complete parameter declaration before consumer mutation.

    When metadata is supplied, the function also proves that every declaration
    targets a scalar FMI 2 Real or FMI 3 Float64 normal parameter with exact
    initialization access. Structural, calculated, array and non-floating
    declarations therefore fail before reaching a runtime boundary.

    :param parameter_values: Ordered scalar parameter declarations.
    :param metadata: Optional authoritative FMU model description.
    :param reserved_variable_names: Input or structural names unavailable to
        normal parameters in the same request.
    :return: None.
    :raises ValueError: If names or values are invalid, repeated or reserved.
    :raises ValueError: If metadata does not expose an eligible parameter.
    """

    observed_names: set[str] = set()
    reserved_names: set[str] = set(reserved_variable_names)
    parameter_value: FmuFloat64ParameterValue
    for parameter_value in parameter_values:
        if isinstance(parameter_value, FmuFloat64ParameterValue):
            pass
        else:
            raise ValueError("FMU parameter declaration has an invalid owner")
        validated_value: FmuFloat64ParameterValue = FmuFloat64ParameterValue(
            variable_name=parameter_value.variable_name,
            value=parameter_value.value,
        )
        if validated_value.variable_name in observed_names:
            raise ValueError("Duplicate FMU parameter variable name")
        else:
            observed_names.add(validated_value.variable_name)
        if validated_value.variable_name in reserved_names:
            raise ValueError(
                "FMU parameter collides with an input or structural declaration"
            )
        else:
            pass
        if metadata is None:
            pass
        else:
            try:
                variable: FmuVariableDescription = metadata.get_variable(
                    validated_value.variable_name
                )
            except KeyError as exc:
                raise ValueError(
                    f"FMU parameter {validated_value.variable_name!r} was not found"
                ) from exc
            if variable.causality == "parameter":
                pass
            else:
                raise ValueError(
                    f"FMU variable {variable.name!r} is not a normal parameter"
                )
            if len(variable.dimensions) == 0:
                pass
            else:
                raise ValueError(
                    f"FMU parameter {variable.name!r} must be scalar"
                )
            if metadata.fmi_version_family == FmiVersion.FMI_2_0:
                fmi_two_parameter_is_eligible: bool = (
                    variable.variable_type == FmuVariableType.REAL
                    and variable.variability in (None, "fixed", "tunable")
                    and variable.initial in (None, "exact")
                )
                if fmi_two_parameter_is_eligible:
                    pass
                else:
                    raise ValueError(
                        f"FMI 2 parameter {variable.name!r} is not an exact "
                        "scalar Real fixed/tunable parameter"
                    )
            else:
                if metadata.fmi_version_family == FmiVersion.FMI_3_0:
                    fmi_three_parameter_is_eligible: bool = (
                        variable.variable_type == FmuVariableType.FLOAT64
                        and variable.variability in ("fixed", "tunable")
                        and is_fmi_three_initialization_mode_writable(variable)
                    )
                    if fmi_three_parameter_is_eligible:
                        pass
                    else:
                        raise ValueError(
                            f"FMI 3 parameter {variable.name!r} is not an exact "
                            "scalar Float64 fixed/tunable parameter"
                        )
                else:
                    raise RuntimeError(
                        "FMU parameter initialization supports FMI 2 and FMI 3"
                    )


class FmuRefBinding:
    """Bind one VeraGrid reference to one scalar or selected FMU value.

    :param reference: VeraGrid external mapping reference.
    :param fmu_variable_name: FMU variable name.
    :param flat_index: Optional row-major array element index.
    """

    __slots__ = ("reference", "fmu_variable_name", "flat_index")

    def __init__(
        self,
        reference: VarPowerFlowReferenceType,
        fmu_variable_name: str,
        flat_index: int | None = None,
    ) -> None:
        """Store one external-reference to selected FMU value.

        :param reference: VeraGrid external mapping reference.
        :param fmu_variable_name: Non-empty FMU variable name.
        :param flat_index: Optional non-negative row-major element index.
        :return: None.
        """

        self.reference: VarPowerFlowReferenceType = reference
        if len(fmu_variable_name.strip()) > 0:
            self.fmu_variable_name: str = fmu_variable_name
        else:
            raise ValueError("FMU binding variable name is empty")
        if flat_index is None:
            self.flat_index: int | None = None
        else:
            # A selected element index is declarative source data. Validate its full
            # unsigned range now; the future consumer will apply cardinality.
            flat_index_is_valid: bool = (
                isinstance(flat_index, int)
                and not isinstance(flat_index, bool)
                and flat_index >= 0
                and flat_index <= 18446744073709551615
            )
            if flat_index_is_valid:
                self.flat_index = flat_index
            else:
                raise ValueError("FMU binding flat index is outside UInt64")


class FmiThreeFloat64SessionValueSelector:
    """Select one device-bound value from a complete FMI 3 Float64 layout.

    The selector retains only the position of the FMU variable in the
    session layout and the optional row-major element selected by source data.
    It does not duplicate model metadata or own runtime values.

    :param variable_index: Position of the FMU variable in the bound layout.
    :param flat_index: Optional row-major element index for an array variable.
    """

    __slots__ = ("variable_index", "flat_index")

    def __init__(
        self,
        variable_index: int,
        flat_index: int | None,
    ) -> None:
        """Validate and store one device-to-layout value selector.

        :param variable_index: Non-negative position in the session layout.
        :param flat_index: Optional non-negative row-major element index.
        :return: None.
        """

        variable_index_is_valid: bool = (
            isinstance(variable_index, int)
            and not isinstance(variable_index, bool)
            and variable_index >= 0
        )
        if variable_index_is_valid:
            self.variable_index: int = variable_index
        else:
            raise ValueError("FMI 3 selector variable index is invalid")
        if flat_index is None:
            self.flat_index: int | None = None
        else:
            flat_index_is_valid: bool = (
                isinstance(flat_index, int)
                and not isinstance(flat_index, bool)
                and flat_index >= 0
                and flat_index <= 18446744073709551615
            )
            if flat_index_is_valid:
                self.flat_index = flat_index
            else:
                raise ValueError("FMI 3 selector flat index is outside UInt64")

    def resolve_serialized_index(
        self,
        layout: FmiThreeFloat64BindingLayout,
    ) -> int:
        """Resolve the current absolute offset in a concatenated row-major vector.

        A missing flat index is unambiguous only for a scalar variable. Array
        cardinality is taken from the current session layout, so configured
        dimensions are validated after Configuration Mode resizing.

        :param layout: Current complete Float64 layout owned by the session.
        :return: Absolute index in the concatenated serialized value vector.
        :raises ValueError: If the variable or element is outside the layout.
        """

        if self.variable_index < len(layout.serialized_value_counts):
            variable_value_count: int = layout.serialized_value_counts[
                self.variable_index
            ]
        else:
            raise ValueError(
                "FMI 3 selected variable is outside the readable layout"
            )
        if self.flat_index is None:
            if variable_value_count == 1:
                variable_flat_index: int = 0
            else:
                raise ValueError(
                    "FMI 3 array device bindings require an explicit flat index"
                )
        else:
            if self.flat_index < variable_value_count:
                variable_flat_index = self.flat_index
            else:
                raise ValueError(
                    "FMI 3 device binding flat index exceeds array cardinality"
                )
        serialized_index: int = variable_flat_index
        preceding_variable_index: int
        for preceding_variable_index in range(self.variable_index):
            serialized_index += layout.serialized_value_counts[
                preceding_variable_index
            ]
        return serialized_index


def resolve_fmi_three_float64_session_value_selectors(
    bindings: tuple[FmuRefBinding, ...],
) -> tuple[
    tuple[str, ...],
    tuple[FmiThreeFloat64SessionValueSelector, ...],
]:
    """Resolve unique FMU names and value selectors in device-binding order.

    Repeated bindings to different elements of one FMU array share a single
    native value reference. The returned selectors remain aligned with the
    original device bindings while names retain first-occurrence order.

    :param bindings: Ordered scalar or element-selecting device bindings.
    :return: Unique FMU variable names followed by aligned value selectors.
    """

    unique_variable_names: list[str] = [""] * len(bindings)
    selectors: list[FmiThreeFloat64SessionValueSelector | None] = [None] * len(
        bindings
    )
    unique_variable_count: int = 0
    binding_index: int
    for binding_index in range(len(bindings)):
        binding: FmuRefBinding = bindings[binding_index]
        variable_index: int | None = None
        candidate_index: int
        for candidate_index in range(unique_variable_count):
            if (
                variable_index is None
                and unique_variable_names[candidate_index]
                == binding.fmu_variable_name
            ):
                variable_index = candidate_index
            else:
                pass
        if variable_index is None:
            variable_index = unique_variable_count
            unique_variable_names[unique_variable_count] = (
                binding.fmu_variable_name
            )
            unique_variable_count += 1
        else:
            pass
        selectors[binding_index] = FmiThreeFloat64SessionValueSelector(
            variable_index=variable_index,
            flat_index=binding.flat_index,
        )
    return (
        tuple(unique_variable_names[:unique_variable_count]),
        cast(
            tuple[FmiThreeFloat64SessionValueSelector, ...],
            tuple(selectors),
        ),
    )


def _reject_indexed_fmu_ref_bindings(
    input_bindings: tuple[FmuRefBinding, ...],
    output_bindings: tuple[FmuRefBinding, ...],
) -> None:
    """Keep indexed bindings fail-closed until the vector consumer exists.

    :param input_bindings: Ordered VeraGrid-to-FMU bindings.
    :param output_bindings: Ordered FMU-to-VeraGrid bindings.
    :return: None.
    """

    has_indexed_binding: bool = False
    binding_index: int
    for binding_index in range(len(input_bindings)):
        if input_bindings[binding_index].flat_index is None:
            pass
        else:
            has_indexed_binding = True
    for binding_index in range(len(output_bindings)):
        if output_bindings[binding_index].flat_index is None:
            pass
        else:
            has_indexed_binding = True
    if has_indexed_binding:
        raise RuntimeError(
            "FMI 3 indexed device bindings require a connected array consumer"
        )
    else:
        pass


class FmiThreeFloat64ConfigurationValue:
    """Declare one structural Float64 value vector by FMU variable name.

    Values retain the FMI row-major serialization order. The declaration owns
    only user-provided data; runtime cardinality and native references remain
    owned by :class:`FmiThreeNumericSession` when a consumer is connected.

    :param variable_name: Structural Float64 variable name in the FMU.
    :param values: Complete finite scalar or flattened array value vector.
    """

    __slots__ = ("variable_name", "values")

    def __init__(self, variable_name: str, values: tuple[float, ...]) -> None:
        """Validate and store one declarative Float64 configuration value.

        :param variable_name: Non-empty FMU structural-parameter name.
        :param values: Complete finite values in FMI row-major order.
        :return: None.
        """

        if len(variable_name.strip()) > 0:
            self.variable_name: str = variable_name
        else:
            raise ValueError("FMI 3 Float64 configuration variable name is empty")

        # Validate the complete provider vector before publishing any of it so
        # persistence cannot retain a partially normalized declaration.
        validated_values: list[float] = [0.0] * len(values)
        value_index: int
        for value_index in range(len(values)):
            source_value: object = values[value_index]
            value_is_numeric: bool = (
                isinstance(source_value, (int, float))
                and not isinstance(source_value, bool)
            )
            if value_is_numeric:
                value: float = float(source_value)
                if math.isfinite(value):
                    validated_values[value_index] = value
                else:
                    raise ValueError(
                        "FMI 3 Float64 configuration values must be finite"
                    )
            else:
                raise ValueError(
                    "FMI 3 Float64 configuration values must be numeric"
                )
        self.values: tuple[float, ...] = tuple(validated_values)


class FmiThreeUInt64ConfigurationValue:
    """Declare one scalar structural UInt64 value by FMU variable name.

    :param variable_name: Structural UInt64 variable name in the FMU.
    :param value: Scalar value used by Configuration Mode.
    """

    __slots__ = ("variable_name", "value")

    def __init__(self, variable_name: str, value: int) -> None:
        """Validate and store one declarative UInt64 configuration value.

        :param variable_name: Non-empty FMU structural-parameter name.
        :param value: Integer inside the UInt64 range.
        :return: None.
        """

        if len(variable_name.strip()) > 0:
            self.variable_name: str = variable_name
        else:
            raise ValueError("FMI 3 UInt64 configuration variable name is empty")

        # Boolean values are integers in Python but are not declarative UInt64
        # source data, so keep that state explicit and fail before persistence.
        value_is_uint64: bool = (
            isinstance(value, int)
            and not isinstance(value, bool)
            and value >= 0
            and value <= 18446744073709551615
        )
        if value_is_uint64:
            self.value: int = value
        else:
            raise ValueError("FMI 3 configuration value is outside UInt64")


class FmiThreeConfigurationSessionValues:
    """Own the ordered Configuration Mode payload required by one session.

    Structured declarations remain the persistence representation. This light
    runtime value object stores only their ordered variable names and flattened
    values so Co-Simulation and Model Exchange apply identical conversion.

    :param float64_variable_names: Ordered structural Float64 variable names.
    :param float64_values: Concatenated Float64 values in FMI row-major order.
    :param uint64_variable_names: Ordered structural UInt64 variable names.
    :param uint64_values: Ordered scalar UInt64 values.
    """

    __slots__ = (
        "float64_variable_names",
        "float64_values",
        "uint64_variable_names",
        "uint64_values",
    )

    def __init__(
        self,
        float64_variable_names: tuple[str, ...],
        float64_values: tuple[float, ...],
        uint64_variable_names: tuple[str, ...],
        uint64_values: tuple[int, ...],
    ) -> None:
        """Store one validated session-ready configuration payload.

        :param float64_variable_names: Ordered structural Float64 names.
        :param float64_values: Concatenated row-major Float64 values.
        :param uint64_variable_names: Ordered structural UInt64 names.
        :param uint64_values: Ordered UInt64 scalar values.
        :return: None.
        """

        self.float64_variable_names: tuple[str, ...] = float64_variable_names
        self.float64_values: tuple[float, ...] = float64_values
        self.uint64_variable_names: tuple[str, ...] = uint64_variable_names
        self.uint64_values: tuple[int, ...] = uint64_values


def _build_fmi_three_configuration_session_values(
    configuration_float64_values: tuple[
        FmiThreeFloat64ConfigurationValue, ...
    ],
    configuration_uint64_values: tuple[
        FmiThreeUInt64ConfigurationValue, ...
    ],
) -> FmiThreeConfigurationSessionValues:
    """Convert declarations into one ordered session-ready payload.

    UInt64 declarations remain separate because they must be applied first to
    settle configurable dimensions. Float64 arrays are concatenated in their
    declared FMI row-major order without changing ownership of source data.

    :param configuration_float64_values: Structural Float64 declarations.
    :param configuration_uint64_values: Structural UInt64 declarations.
    :return: Names and values ordered for the isolated runtime session.
    """

    _validate_fmi_three_configuration_values(
        configuration_float64_values=configuration_float64_values,
        configuration_uint64_values=configuration_uint64_values,
    )

    float64_variable_names: list[str] = [""] * len(
        configuration_float64_values
    )
    float64_value_count: int = 0
    configuration_index: int
    for configuration_index in range(len(configuration_float64_values)):
        float64_configuration: FmiThreeFloat64ConfigurationValue = (
            configuration_float64_values[configuration_index]
        )
        float64_variable_names[configuration_index] = (
            float64_configuration.variable_name
        )
        float64_value_count += len(float64_configuration.values)

    float64_values: list[float] = [0.0] * float64_value_count
    float64_value_index: int = 0
    for configuration_index in range(len(configuration_float64_values)):
        float64_configuration = configuration_float64_values[configuration_index]
        declared_value_index: int
        for declared_value_index in range(len(float64_configuration.values)):
            float64_values[float64_value_index] = (
                float64_configuration.values[declared_value_index]
            )
            float64_value_index += 1

    uint64_variable_names: list[str] = [""] * len(
        configuration_uint64_values
    )
    uint64_values: list[int] = [0] * len(configuration_uint64_values)
    for configuration_index in range(len(configuration_uint64_values)):
        uint64_configuration: FmiThreeUInt64ConfigurationValue = (
            configuration_uint64_values[configuration_index]
        )
        uint64_variable_names[configuration_index] = (
            uint64_configuration.variable_name
        )
        uint64_values[configuration_index] = uint64_configuration.value

    return FmiThreeConfigurationSessionValues(
        float64_variable_names=tuple(float64_variable_names),
        float64_values=tuple(float64_values),
        uint64_variable_names=tuple(uint64_variable_names),
        uint64_values=tuple(uint64_values),
    )


def _validate_fmi_three_configuration_values(
    configuration_float64_values: tuple[
        FmiThreeFloat64ConfigurationValue, ...
    ],
    configuration_uint64_values: tuple[
        FmiThreeUInt64ConfigurationValue, ...
    ],
) -> None:
    """Validate complete and unique Configuration Mode declarations.

    Validation is repeated at each persistence boundary because these light
    declaration objects expose their data for the established importer API.

    :param configuration_float64_values: Structural Float64 declarations.
    :param configuration_uint64_values: Structural UInt64 declarations.
    :return: None.
    """

    configured_variable_names: set[str] = set()
    float64_configuration: FmiThreeFloat64ConfigurationValue
    for float64_configuration in configuration_float64_values:
        validated_float64_configuration: FmiThreeFloat64ConfigurationValue = (
            FmiThreeFloat64ConfigurationValue(
                variable_name=float64_configuration.variable_name,
                values=float64_configuration.values,
            )
        )
        if (
            validated_float64_configuration.variable_name
            in configured_variable_names
        ):
            raise ValueError("Duplicate FMI 3 Configuration Mode variable name")
        else:
            configured_variable_names.add(
                validated_float64_configuration.variable_name
            )
    uint64_configuration: FmiThreeUInt64ConfigurationValue
    for uint64_configuration in configuration_uint64_values:
        validated_uint64_configuration: FmiThreeUInt64ConfigurationValue = (
            FmiThreeUInt64ConfigurationValue(
                variable_name=uint64_configuration.variable_name,
                value=uint64_configuration.value,
            )
        )
        if (
            validated_uint64_configuration.variable_name
            in configured_variable_names
        ):
            raise ValueError("Duplicate FMI 3 Configuration Mode variable name")
        else:
            configured_variable_names.add(
                validated_uint64_configuration.variable_name
            )


class FmiThreeFloat64VariableCardinalityPlan:
    """Retain the minimal dimensions needed to size one Float64 variable.

    The plan contains no variable names or complete model metadata. Constant
    dimensions keep a ``None`` controller while referenced dimensions retain
    only the controlling UInt64 value reference and their current size.

    :param value_reference: Float64 variable value reference.
    :param dimension_sizes: Current dimension sizes in declaration order.
    :param dimension_value_references: Optional UInt64 controller per dimension.
    """

    __slots__ = (
        "value_reference",
        "dimension_sizes",
        "dimension_value_references",
    )

    def __init__(
        self,
        value_reference: int,
        dimension_sizes: tuple[int, ...],
        dimension_value_references: tuple[int | None, ...],
    ) -> None:
        """Validate and store one scalar or array cardinality plan.

        :param value_reference: Float64 variable value reference.
        :param dimension_sizes: Current non-negative dimension sizes.
        :param dimension_value_references: Optional UInt64 controller per dimension.
        :return: None.
        """

        if value_reference >= 0 and value_reference <= 4294967295:
            pass
        else:
            raise ValueError("FMI 3 cardinality-plan reference is outside UInt32")
        if len(dimension_sizes) == len(dimension_value_references):
            pass
        else:
            raise ValueError("FMI 3 cardinality-plan dimensions must align")
        dimension_index: int
        for dimension_index in range(len(dimension_sizes)):
            dimension_size: int = dimension_sizes[dimension_index]
            dimension_value_reference: int | None = (
                dimension_value_references[dimension_index]
            )
            if dimension_value_reference is None:
                if dimension_size > 0 and dimension_size <= 18446744073709551615:
                    pass
                else:
                    raise ValueError(
                        "FMI 3 constant cardinality-plan dimensions must be positive UInt64"
                    )
            else:
                if (
                    dimension_value_reference >= 0
                    and dimension_value_reference <= 4294967295
                    and dimension_size >= 0
                    and dimension_size <= 18446744073709551615
                ):
                    pass
                else:
                    raise ValueError(
                        "FMI 3 configured cardinality-plan dimensions are invalid"
                    )
        self.value_reference: int = value_reference
        self.dimension_sizes: tuple[int, ...] = tuple(dimension_sizes)
        self.dimension_value_references: tuple[int | None, ...] = tuple(
            dimension_value_references
        )

    def resolve_serialized_value_count(
        self,
        maximum_serialized_value_count: int,
    ) -> int:
        """Return the current flattened cardinality within the caller's bound.

        :param maximum_serialized_value_count: Maximum values in one native call.
        :return: One for a scalar or the row-major product of current dimensions.
        :raises ValueError: If the current cardinality exceeds the bound.
        """

        validate_fmi_three_worker_float64_value_limit(
            maximum_serialized_value_count
        )
        has_vanished_dimension: bool = False
        dimension_size: int
        for dimension_size in self.dimension_sizes:
            if dimension_size == 0:
                has_vanished_dimension = True
            else:
                pass
        if has_vanished_dimension:
            return 0
        else:
            pass
        serialized_value_count: int = 1
        for dimension_size in self.dimension_sizes:
            if (
                serialized_value_count
                <= maximum_serialized_value_count // dimension_size
            ):
                serialized_value_count *= dimension_size
            else:
                raise ValueError(
                    "FMI 3 Float64 variable exceeds the serialized value bound"
                )
        return serialized_value_count

    def configure_uint64(
        self,
        value_references: tuple[int, ...],
        values: tuple[int, ...],
        maximum_serialized_value_count: int,
    ) -> FmiThreeFloat64VariableCardinalityPlan:
        """Return a bounded plan after applying structural UInt64 values.

        Unmentioned structural parameters retain their current sizes so several
        Configuration Mode calls compose without reusing invalidated start data.

        :param value_references: Ordered configured UInt64 value references.
        :param values: UInt64 values aligned with ``value_references``.
        :param maximum_serialized_value_count: Maximum values in one native call.
        :return: New plan containing the prospective current dimensions.
        """

        if len(value_references) == len(values):
            pass
        else:
            raise ValueError("FMI 3 configured UInt64 references and values must align")
        configured_values_by_reference: dict[int, int] = dict()
        configured_index: int
        for configured_index in range(len(value_references)):
            configured_reference: int = value_references[configured_index]
            configured_value: int = values[configured_index]
            if configured_reference in configured_values_by_reference:
                raise ValueError("FMI 3 configured UInt64 references must be unique")
            else:
                pass
            if (
                configured_reference >= 0
                and configured_reference <= 4294967295
                and configured_value >= 0
                and configured_value <= 18446744073709551615
            ):
                configured_values_by_reference[configured_reference] = configured_value
            else:
                raise ValueError("FMI 3 configured UInt64 value is outside its bound")
        configured_dimension_sizes: list[int] = list(self.dimension_sizes)
        dimension_index: int
        for dimension_index in range(len(self.dimension_value_references)):
            dimension_value_reference: int | None = (
                self.dimension_value_references[dimension_index]
            )
            if dimension_value_reference is not None:
                configured_dimension_size: int | None = (
                    configured_values_by_reference.get(
                        dimension_value_reference,
                        None,
                    )
                )
                if configured_dimension_size is not None:
                    configured_dimension_sizes[dimension_index] = (
                        configured_dimension_size
                    )
                else:
                    pass
            else:
                pass
        configured_plan: FmiThreeFloat64VariableCardinalityPlan = (
            FmiThreeFloat64VariableCardinalityPlan(
                value_reference=self.value_reference,
                dimension_sizes=tuple(configured_dimension_sizes),
                dimension_value_references=self.dimension_value_references,
            )
        )
        configured_plan.resolve_serialized_value_count(
            maximum_serialized_value_count
        )
        return configured_plan


class FmiThreeFloat64BindingLayout:
    """Retain one ordered FMI 3 Float64 batch without model metadata.

    :param value_references: Ordered unique scalar or array references.
    :param variable_cardinality_plans: Per-reference current dimension plans.
    :param serialized_value_counts: Row-major value count for each reference.
    :param serialized_value_count: Total concatenated value count.
    """

    __slots__ = (
        "value_references",
        "variable_cardinality_plans",
        "serialized_value_counts",
        "serialized_value_count",
    )

    def __init__(
        self,
        value_references: tuple[int, ...],
        variable_cardinality_plans: tuple[
            FmiThreeFloat64VariableCardinalityPlan, ...
        ],
        serialized_value_counts: tuple[int, ...],
        serialized_value_count: int,
    ) -> None:
        """Store one already validated, bounded binding layout.

        :param value_references: Ordered unique scalar or array references.
        :param variable_cardinality_plans: Per-reference current dimension plans.
        :param serialized_value_counts: Per-reference serialized counts.
        :param serialized_value_count: Total concatenated value count.
        :return: None.
        """

        if (
            len(value_references) == len(serialized_value_counts)
            and len(value_references) == len(variable_cardinality_plans)
        ):
            pass
        else:
            raise ValueError("FMI 3 binding layout references and counts must align")
        observed_references: set[int] = set()
        computed_value_count: int = 0
        layout_index: int
        for layout_index in range(len(value_references)):
            value_reference: int = value_references[layout_index]
            cardinality_plan: FmiThreeFloat64VariableCardinalityPlan = (
                variable_cardinality_plans[layout_index]
            )
            variable_value_count: int = serialized_value_counts[layout_index]
            if value_reference >= 0 and value_reference <= 4294967295:
                pass
            else:
                raise ValueError("FMI 3 binding layout reference is outside UInt32")
            if value_reference in observed_references:
                raise ValueError("FMI 3 binding layout references must be unique")
            else:
                observed_references.add(value_reference)
            if cardinality_plan.value_reference == value_reference:
                pass
            else:
                raise ValueError(
                    "FMI 3 binding layout cardinality plan has a different reference"
                )
            expected_variable_value_count: int = 1
            dimension_size: int
            for dimension_size in cardinality_plan.dimension_sizes:
                expected_variable_value_count *= dimension_size
            if variable_value_count == expected_variable_value_count:
                computed_value_count += variable_value_count
            else:
                raise ValueError(
                    "FMI 3 binding layout count differs from its cardinality plan"
                )
        if computed_value_count == serialized_value_count:
            pass
        else:
            raise ValueError("FMI 3 binding layout total is inconsistent")
        self.value_references: tuple[int, ...] = tuple(value_references)
        self.variable_cardinality_plans: tuple[
            FmiThreeFloat64VariableCardinalityPlan, ...
        ] = tuple(variable_cardinality_plans)
        self.serialized_value_counts: tuple[int, ...] = tuple(
            serialized_value_counts
        )
        self.serialized_value_count: int = serialized_value_count


class _FmiThreeFloat64BindingAccess(Enum):
    """Select the lifecycle access required by one Float64 binding layout."""

    READABLE = 1
    STEP_WRITABLE = 2
    CONFIGURATION_WRITABLE = 3
    INITIALIZATION_WRITABLE = 4


class FmuImportConfig:
    """Store the runtime configuration required to execute an imported FMU."""

    __slots__ = (
        "fmu_path",
        "preferred_mode",
        "bindings",
        "communication_step",
        "relative_tolerance",
        "extraction_root",
        "visible",
        "debug_logging",
    )

    def __init__(
        self,
        fmu_path: str | Path,
        preferred_mode: FmuInterfaceMode | None = None,
        bindings: tuple[FmuVariableBinding, ...] = tuple(),
        communication_step: float | None = None,
        relative_tolerance: float | None = None,
        extraction_root: str | Path | None = None,
        visible: bool = False,
        debug_logging: bool = False,
    ) -> None:
        """Store the runtime options for the imported FMU host."""

        self.fmu_path: Path = Path(fmu_path).expanduser()
        self.preferred_mode: FmuInterfaceMode | None = preferred_mode
        self.bindings: tuple[FmuVariableBinding, ...] = bindings
        if communication_step is None:
            self.communication_step = None
        else:
            if communication_step > 0.0:
                self.communication_step = float(communication_step)
            else:
                raise ValueError("communication_step must be positive when provided")
        if relative_tolerance is None:
            self.relative_tolerance = None
        else:
            if relative_tolerance > 0.0:
                self.relative_tolerance = float(relative_tolerance)
            else:
                raise ValueError("relative_tolerance must be positive when provided")
        if extraction_root is None:
            self.extraction_root = None
        else:
            self.extraction_root = Path(extraction_root).expanduser()
        self.visible: bool = bool(visible)
        self.debug_logging: bool = bool(debug_logging)

    def resolve_execution_mode(
        self,
        metadata: FmuModelDescription,
    ) -> FmuInterfaceMode:
        """Return the declared FMI execution mode selected by this configuration.

        :param metadata: Parsed FMU model description.
        :return: Selected Co-Simulation or Model Exchange interface.
        :raises RuntimeError: If the FMI version family is unsupported.
        """

        if metadata.fmi_version_family == FmiVersion.FMI_1_0:
            interface_mode: FmuInterfaceMode = metadata.select_declared_interface(
                self.preferred_mode
            )
            if interface_mode == FmuInterfaceMode.CO_SIMULATION:
                capabilities: FmiOneCoSimulationCapabilities | None = (
                    metadata.fmi_one_co_simulation_capabilities
                )
                if capabilities is None:
                    raise RuntimeError(
                        "FMI 1 Co-Simulation execution requires capability metadata"
                    )
                else:
                    pass
                if capabilities.needs_execution_tool:
                    raise RuntimeError(
                        "FMI 1 CoSimulation_Tool execution requires the original external tool"
                    )
                else:
                    pass
                if capabilities.can_handle_variable_communication_step_size:
                    pass
                else:
                    raise RuntimeError(
                        "FMI 1 Co-Simulation execution requires variable communication step support"
                    )
                if capabilities.can_run_asynchronuously:
                    raise RuntimeError(
                        "FMI 1 asynchronous Co-Simulation execution is not supported"
                    )
                else:
                    pass
            else:
                pass
            return interface_mode
        else:
            if (
                metadata.fmi_version_family == FmiVersion.FMI_2_0
                or metadata.fmi_version_family == FmiVersion.FMI_3_0
            ):
                return metadata.select_declared_interface(self.preferred_mode)
            else:
                raise RuntimeError(
                    f"FMI {metadata.fmi_version} execution is not supported yet"
                )


def _validate_fmi_three_binding_worker_profile(
    metadata: FmuModelDescription,
    interface_mode: FmuInterfaceMode,
    float64_profile: FmiThreeWorkerFloat64Profile,
) -> None:
    """Validate one binding layout against its authenticated FMI interface.

    :param metadata: Authoritative FMI 3 model description.
    :param interface_mode: Interface selected for the isolated worker.
    :param float64_profile: Scalar or array worker profile.
    :return: None.
    """

    if interface_mode == FmuInterfaceMode.CO_SIMULATION:
        validate_fmi_three_co_simulation_worker_profile(
            metadata=metadata,
            preferred_mode=interface_mode,
            float64_profile=float64_profile,
        )
    else:
        if interface_mode == FmuInterfaceMode.MODEL_EXCHANGE:
            validate_fmi_three_model_exchange_worker_profile(
                metadata=metadata,
                preferred_mode=interface_mode,
                float64_profile=float64_profile,
            )
        else:
            raise RuntimeError("Unsupported FMI 3 binding interface")


def resolve_fmi_three_scalar_binding_references(
    metadata: FmuModelDescription,
    readable_variable_names: tuple[str, ...],
    writable_variable_names: tuple[str, ...],
    interface_mode: FmuInterfaceMode = FmuInterfaceMode.CO_SIMULATION,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Resolve ordered scalar bindings against the FMI 3 worker access policy.

    The local lookup exists only for this conversion. The returned tuples retain
    neither model-description objects nor variable names.

    :param metadata: Authoritative FMI 3 model description.
    :param readable_variable_names: Ordered names that will be read in Step Mode.
    :param writable_variable_names: Ordered names that will be written in Step Mode.
    :param interface_mode: Authenticated interface owning the scalar bindings.
    :return: Readable references followed by writable references in binding order.
    :raises ValueError: If a name is absent, repeated within one access
        direction, or not writable when requested for writing.
    :raises RuntimeError: If the FMU is outside the supported scalar worker
        profile.
    """

    _validate_fmi_three_binding_worker_profile(
        metadata=metadata,
        interface_mode=interface_mode,
        float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
    )
    variables_by_name: dict[str, FmuVariableDescription] = dict()
    declared_variable: FmuVariableDescription
    for declared_variable in metadata.variables:
        variables_by_name[declared_variable.name] = declared_variable

    writable_references: list[int] = [0] * len(writable_variable_names)
    writable_names_seen: set[str] = set()
    writable_index: int
    for writable_index in range(len(writable_variable_names)):
        writable_name: str = writable_variable_names[writable_index]
        if writable_name in writable_names_seen:
            raise ValueError(
                f"Duplicate writable FMI 3 binding for variable {writable_name!r}"
            )
        else:
            writable_names_seen.add(writable_name)
        writable_variable: FmuVariableDescription | None = variables_by_name.get(
            writable_name,
            None,
        )
        if writable_variable is not None:
            pass
        else:
            raise ValueError(
                f"FMI 3 binding variable {writable_name!r} was not found"
            )
        if is_fmi_three_input_or_tunable_parameter(writable_variable):
            writable_references[writable_index] = writable_variable.value_reference
        else:
            raise ValueError(
                f"FMI 3 binding variable {writable_name!r} is not writable in "
                "Step Mode"
            )

    readable_references: list[int] = [0] * len(readable_variable_names)
    readable_names_seen: set[str] = set()
    readable_index: int
    for readable_index in range(len(readable_variable_names)):
        readable_name: str = readable_variable_names[readable_index]
        if readable_name in readable_names_seen:
            raise ValueError(
                f"Duplicate readable FMI 3 binding for variable {readable_name!r}"
            )
        else:
            readable_names_seen.add(readable_name)
        readable_variable: FmuVariableDescription | None = variables_by_name.get(
            readable_name,
            None,
        )
        if readable_variable is not None:
            readable_references[readable_index] = readable_variable.value_reference
        else:
            raise ValueError(
                f"FMI 3 binding variable {readable_name!r} was not found"
            )
    return tuple(readable_references), tuple(writable_references)


def resolve_fmi_three_scalar_int32_binding_references(
    metadata: FmuModelDescription,
    initialization_variable_names: tuple[str, ...],
    readable_variable_names: tuple[str, ...],
    writable_variable_names: tuple[str, ...],
    float64_profile: FmiThreeWorkerFloat64Profile = (
        FmiThreeWorkerFloat64Profile.SCALAR
    ),
    interface_mode: FmuInterfaceMode = FmuInterfaceMode.CO_SIMULATION,
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    """Resolve scalar Int32 bindings for one FMI 3 numeric session.

    Names are resolved once while authoritative metadata is available. The
    numerical runtime receives only bounded value-reference tuples afterward.

    :param metadata: Authoritative FMI 3 model description.
    :param initialization_variable_names: Ordered Int32 names written during
        Initialization Mode.
    :param readable_variable_names: Ordered Int32 names readable at runtime.
    :param writable_variable_names: Ordered Int32 inputs or tunable parameters.
    :param float64_profile: Float64 scalar or array profile sharing the worker.
    :param interface_mode: Authenticated FMI interface owning the bindings.
    :return: Initialization, readable, and writable Int32 reference tuples.
    :raises ValueError: If a name is missing, repeated, mistyped, an
        array, or invalid for the requested write phase.
    :raises RuntimeError: If the complete FMU is outside the worker profile.
    """

    _validate_fmi_three_binding_worker_profile(
        metadata=metadata,
        interface_mode=interface_mode,
        float64_profile=float64_profile,
    )
    variables_by_name: dict[str, FmuVariableDescription] = dict()
    declared_variable: FmuVariableDescription
    for declared_variable in metadata.variables:
        variables_by_name[declared_variable.name] = declared_variable

    initialization_references: list[int] = [0] * len(
        initialization_variable_names
    )
    initialization_names_seen: set[str] = set()
    variable_index: int
    for variable_index in range(len(initialization_variable_names)):
        variable_name: str = initialization_variable_names[variable_index]
        if variable_name in initialization_names_seen:
            raise ValueError(
                f"Duplicate FMI 3 Int32 initialization binding {variable_name!r}"
            )
        else:
            initialization_names_seen.add(variable_name)
        variable: FmuVariableDescription | None = variables_by_name.get(
            variable_name,
            None,
        )
        if variable is not None:
            pass
        else:
            raise ValueError(
                f"FMI 3 binding variable {variable_name!r} was not found"
            )
        if variable.variable_type == FmuVariableType.INT32:
            pass
        else:
            raise ValueError(
                f"FMI 3 binding variable {variable_name!r} is not Int32"
            )
        if len(variable.dimensions) == 0:
            pass
        else:
            raise ValueError(
                f"FMI 3 Int32 binding variable {variable_name!r} is not scalar"
            )
        if is_fmi_three_initialization_mode_writable(variable):
            initialization_references[variable_index] = variable.value_reference
        else:
            raise ValueError(
                f"FMI 3 binding variable {variable_name!r} is not writable in "
                "Initialization Mode"
            )

    readable_references: list[int] = [0] * len(readable_variable_names)
    readable_names_seen: set[str] = set()
    for variable_index in range(len(readable_variable_names)):
        variable_name = readable_variable_names[variable_index]
        if variable_name in readable_names_seen:
            raise ValueError(
                f"Duplicate readable FMI 3 Int32 binding {variable_name!r}"
            )
        else:
            readable_names_seen.add(variable_name)
        variable = variables_by_name.get(variable_name, None)
        if variable is not None:
            pass
        else:
            raise ValueError(
                f"FMI 3 binding variable {variable_name!r} was not found"
            )
        if variable.variable_type == FmuVariableType.INT32:
            pass
        else:
            raise ValueError(
                f"FMI 3 binding variable {variable_name!r} is not Int32"
            )
        if len(variable.dimensions) == 0:
            readable_references[variable_index] = variable.value_reference
        else:
            raise ValueError(
                f"FMI 3 Int32 binding variable {variable_name!r} is not scalar"
            )

    writable_references: list[int] = [0] * len(writable_variable_names)
    writable_names_seen: set[str] = set()
    for variable_index in range(len(writable_variable_names)):
        variable_name = writable_variable_names[variable_index]
        if variable_name in writable_names_seen:
            raise ValueError(
                f"Duplicate writable FMI 3 Int32 binding {variable_name!r}"
            )
        else:
            writable_names_seen.add(variable_name)
        variable = variables_by_name.get(variable_name, None)
        if variable is not None:
            pass
        else:
            raise ValueError(
                f"FMI 3 binding variable {variable_name!r} was not found"
            )
        if variable.variable_type == FmuVariableType.INT32:
            pass
        else:
            raise ValueError(
                f"FMI 3 binding variable {variable_name!r} is not Int32"
            )
        if len(variable.dimensions) == 0:
            pass
        else:
            raise ValueError(
                f"FMI 3 Int32 binding variable {variable_name!r} is not scalar"
            )
        if is_fmi_three_input_or_tunable_parameter(variable):
            writable_references[variable_index] = variable.value_reference
        else:
            raise ValueError(
                f"FMI 3 binding variable {variable_name!r} is not writable in "
                "Step Mode"
            )
    return (
        tuple(initialization_references),
        tuple(readable_references),
        tuple(writable_references),
    )


def resolve_fmi_three_variable_serialized_value_count(
    variable: FmuVariableDescription,
    maximum_serialized_value_count: int,
) -> int:
    """Return one scalar or constant-array cardinality within a finite bound.

    :param variable: Parsed FMI 3 Float64 variable.
    :param maximum_serialized_value_count: Maximum values accepted by the caller.
    :return: One for a scalar or the product of ordered constant dimensions.
    :raises ValueError: If the declared cardinality exceeds the bound.
    """

    dimension_sizes: list[int] = [0] * len(variable.dimensions)
    dimension_value_references: tuple[int | None, ...] = (None,) * len(
        variable.dimensions
    )
    dimension_index: int
    for dimension_index in range(len(variable.dimensions)):
        dimension_size: int | None = variable.dimensions[
            dimension_index
        ].constant_size
        if dimension_size is not None:
            dimension_sizes[dimension_index] = dimension_size
        else:
            raise ValueError(
                f"FMI 3 binding variable {variable.name!r} requires a "
                "Configuration Mode dimension value"
            )
    cardinality_plan: FmiThreeFloat64VariableCardinalityPlan = (
        FmiThreeFloat64VariableCardinalityPlan(
            value_reference=variable.value_reference,
            dimension_sizes=tuple(dimension_sizes),
            dimension_value_references=dimension_value_references,
        )
    )
    return cardinality_plan.resolve_serialized_value_count(
        maximum_serialized_value_count
    )


def resolve_fmi_three_float64_variable_cardinality_plan(
    variable: FmuVariableDescription,
    variables_by_reference: dict[int, FmuVariableDescription],
    maximum_serialized_value_count: int,
) -> FmiThreeFloat64VariableCardinalityPlan:
    """Project one validated Float64 variable into a minimal runtime plan.

    Referenced dimensions use the already validated UInt64 owner's ``start``
    value for their initial size. The returned plan retains only integers and
    therefore does not keep source metadata alive during execution.

    :param variable: Float64 variable whose cardinality will be tracked.
    :param variables_by_reference: Import-local lookup for dimension owners.
    :param maximum_serialized_value_count: Maximum values in one native call.
    :return: Bounded initial cardinality plan.
    :raises ValueError: If metadata cannot form one bounded plan.
    """

    if variable.variable_type == FmuVariableType.FLOAT64:
        pass
    else:
        raise ValueError("FMI 3 cardinality plans require Float64 variables")
    dimension_sizes: list[int] = [0] * len(variable.dimensions)
    dimension_value_references: list[int | None] = [None] * len(
        variable.dimensions
    )
    dimension_index: int
    for dimension_index in range(len(variable.dimensions)):
        dimension: FmiThreeVariableDimension = variable.dimensions[dimension_index]
        if dimension.constant_size is not None:
            dimension_sizes[dimension_index] = dimension.constant_size
        else:
            dimension_value_reference: int | None = dimension.value_reference
            if dimension_value_reference is not None:
                pass
            else:
                raise ValueError(
                    f"FMI 3 binding variable {variable.name!r} has no dimension owner"
                )
            source_variable: FmuVariableDescription | None = (
                variables_by_reference.get(dimension_value_reference, None)
            )
            if source_variable is not None:
                pass
            else:
                raise ValueError(
                    f"FMI 3 binding variable {variable.name!r} has a missing "
                    "dimension owner"
                )
            source_is_valid: bool = (
                source_variable.variable_type == FmuVariableType.UINT64
                and len(source_variable.dimensions) == 0
                and (
                    source_variable.variability == "constant"
                    or source_variable.causality == "structuralParameter"
                )
            )
            if source_is_valid and source_variable.start is not None:
                try:
                    initial_dimension_size: int = int(source_variable.start)
                except ValueError as error:
                    raise ValueError(
                        f"FMI 3 binding variable {variable.name!r} has an invalid "
                        "dimension start"
                    ) from error
            else:
                raise ValueError(
                    f"FMI 3 binding variable {variable.name!r} has an invalid "
                    "dimension owner"
                )
            if initial_dimension_size > 0:
                dimension_sizes[dimension_index] = initial_dimension_size
                dimension_value_references[dimension_index] = (
                    dimension_value_reference
                )
            else:
                raise ValueError(
                    f"FMI 3 binding variable {variable.name!r} has a vanished "
                    "initial dimension"
                )
    cardinality_plan: FmiThreeFloat64VariableCardinalityPlan = (
        FmiThreeFloat64VariableCardinalityPlan(
            value_reference=variable.value_reference,
            dimension_sizes=tuple(dimension_sizes),
            dimension_value_references=tuple(dimension_value_references),
        )
    )
    cardinality_plan.resolve_serialized_value_count(
        maximum_serialized_value_count
    )
    return cardinality_plan


def resolve_fmi_three_configured_float64_binding_layout(
    layout: FmiThreeFloat64BindingLayout,
    configuration_uint64_value_references: tuple[int, ...],
    configuration_uint64_values: tuple[int, ...],
    maximum_serialized_value_count: int,
) -> FmiThreeFloat64BindingLayout:
    """Return one layout resized by successful UInt64 configuration values.

    :param layout: Current ordered Float64 layout.
    :param configuration_uint64_value_references: Configured structural references.
    :param configuration_uint64_values: UInt64 values aligned with the references.
    :param maximum_serialized_value_count: Maximum concatenated Float64 count.
    :return: New bounded layout whose plans retain the configured dimensions.
    """

    validate_fmi_three_worker_float64_value_limit(
        maximum_serialized_value_count
    )
    configured_plans: list[FmiThreeFloat64VariableCardinalityPlan | None] = (
        [None] * len(layout.variable_cardinality_plans)
    )
    configured_counts: list[int] = [0] * len(layout.variable_cardinality_plans)
    configured_total: int = 0
    plan_index: int
    for plan_index in range(len(layout.variable_cardinality_plans)):
        current_plan: FmiThreeFloat64VariableCardinalityPlan = (
            layout.variable_cardinality_plans[plan_index]
        )
        configured_plan: FmiThreeFloat64VariableCardinalityPlan = (
            current_plan.configure_uint64(
                value_references=configuration_uint64_value_references,
                values=configuration_uint64_values,
                maximum_serialized_value_count=maximum_serialized_value_count,
            )
        )
        configured_count: int = configured_plan.resolve_serialized_value_count(
            maximum_serialized_value_count
        )
        if configured_total <= maximum_serialized_value_count - configured_count:
            configured_total += configured_count
        else:
            raise ValueError(
                "FMI 3 configured binding layout exceeds the serialized value bound"
            )
        configured_plans[plan_index] = configured_plan
        configured_counts[plan_index] = configured_count
    return FmiThreeFloat64BindingLayout(
        value_references=layout.value_references,
        variable_cardinality_plans=cast(
            tuple[FmiThreeFloat64VariableCardinalityPlan, ...],
            tuple(configured_plans),
        ),
        serialized_value_counts=tuple(configured_counts),
        serialized_value_count=configured_total,
    )


def _build_fmi_three_float64_binding_layout(
    metadata: FmuModelDescription,
    variable_names: tuple[str, ...],
    access: _FmiThreeFloat64BindingAccess,
    maximum_serialized_value_count: int,
) -> FmiThreeFloat64BindingLayout:
    """Build one ordered, bounded scalar-and-array Float64 layout.

    :param metadata: Authoritative FMI 3 model description.
    :param variable_names: Ordered unique variable names selected by a consumer.
    :param access: Lifecycle access required for every selected variable.
    :param maximum_serialized_value_count: Maximum concatenated Float64 count.
    :return: Minimal layout containing no names or model-description objects.
    :raises ValueError: If a target is absent, repeated, inaccessible, or too large.
    """

    validate_fmi_three_worker_float64_value_limit(
        maximum_serialized_value_count
    )
    variables_by_name: dict[str, FmuVariableDescription] = dict()
    variables_by_reference: dict[int, FmuVariableDescription] = dict()
    declared_variable: FmuVariableDescription
    for declared_variable in metadata.variables:
        variables_by_name[declared_variable.name] = declared_variable
        variables_by_reference[declared_variable.value_reference] = declared_variable
    value_references: list[int] = [0] * len(variable_names)
    variable_cardinality_plans: list[
        FmiThreeFloat64VariableCardinalityPlan | None
    ] = [None] * len(variable_names)
    serialized_value_counts: list[int] = [0] * len(variable_names)
    observed_names: set[str] = set()
    serialized_value_count: int = 0
    variable_index: int
    for variable_index in range(len(variable_names)):
        variable_name: str = variable_names[variable_index]
        if variable_name in observed_names:
            raise ValueError(
                f"Duplicate FMI 3 Float64 binding for variable {variable_name!r}"
            )
        else:
            observed_names.add(variable_name)
        variable: FmuVariableDescription | None = variables_by_name.get(
            variable_name,
            None,
        )
        if variable is not None:
            pass
        else:
            raise ValueError(
                f"FMI 3 binding variable {variable_name!r} was not found"
            )
        if variable.variable_type == FmuVariableType.FLOAT64:
            pass
        else:
            raise ValueError(
                f"FMI 3 binding variable {variable_name!r} is not Float64"
            )
        if access == _FmiThreeFloat64BindingAccess.STEP_WRITABLE:
            if is_fmi_three_input_or_tunable_parameter(variable):
                pass
            else:
                raise ValueError(
                    f"FMI 3 binding variable {variable_name!r} is not writable "
                    "in Step Mode"
                )
        else:
            if access == _FmiThreeFloat64BindingAccess.CONFIGURATION_WRITABLE:
                if is_fmi_three_configuration_mode_writable(variable):
                    pass
                else:
                    raise ValueError(
                        f"FMI 3 binding variable {variable_name!r} is not a "
                        "structural parameter writable in Configuration Mode"
                    )
            else:
                if access == _FmiThreeFloat64BindingAccess.INITIALIZATION_WRITABLE:
                    if is_fmi_three_initialization_mode_writable(variable):
                        pass
                    else:
                        raise ValueError(
                            f"FMI 3 binding variable {variable_name!r} is not "
                            "writable in Initialization Mode"
                        )
                else:
                    if access == _FmiThreeFloat64BindingAccess.READABLE:
                        pass
                    else:
                        raise ValueError("Unsupported FMI 3 Float64 binding access")
        variable_cardinality_plan: FmiThreeFloat64VariableCardinalityPlan = (
            resolve_fmi_three_float64_variable_cardinality_plan(
                variable=variable,
                variables_by_reference=variables_by_reference,
                maximum_serialized_value_count=maximum_serialized_value_count,
            )
        )
        variable_value_count: int = (
            variable_cardinality_plan.resolve_serialized_value_count(
                maximum_serialized_value_count
            )
        )
        if serialized_value_count <= maximum_serialized_value_count - variable_value_count:
            serialized_value_count += variable_value_count
        else:
            raise ValueError("FMI 3 binding layout exceeds the serialized value bound")
        value_references[variable_index] = variable.value_reference
        variable_cardinality_plans[variable_index] = variable_cardinality_plan
        serialized_value_counts[variable_index] = variable_value_count
    return FmiThreeFloat64BindingLayout(
        value_references=tuple(value_references),
        variable_cardinality_plans=cast(
            tuple[FmiThreeFloat64VariableCardinalityPlan, ...],
            tuple(variable_cardinality_plans),
        ),
        serialized_value_counts=tuple(serialized_value_counts),
        serialized_value_count=serialized_value_count,
    )


def resolve_fmi_three_constant_float64_binding_layouts(
    metadata: FmuModelDescription,
    readable_variable_names: tuple[str, ...],
    writable_variable_names: tuple[str, ...],
    maximum_serialized_value_count: int,
    interface_mode: FmuInterfaceMode = FmuInterfaceMode.CO_SIMULATION,
) -> tuple[FmiThreeFloat64BindingLayout, FmiThreeFloat64BindingLayout]:
    """Resolve bounded row-major layouts for constant-size Float64 variables.

    Multiple variable values are concatenated in binding order, as required by
    the FMI 3 C API. Dimensions controlled by structural-parameter references
    remain outside this constant-shape profile.

    :param metadata: Authoritative FMI 3 Co-Simulation description.
    :param readable_variable_names: Ordered scalar or array names to read.
    :param writable_variable_names: Ordered input or tunable-parameter names.
    :param maximum_serialized_value_count: Maximum values in either layout.
    :param interface_mode: Authenticated interface owning the array bindings.
    :return: Readable layout followed by writable layout.
    """

    _validate_fmi_three_binding_worker_profile(
        metadata=metadata,
        interface_mode=interface_mode,
        float64_profile=FmiThreeWorkerFloat64Profile.CONSTANT_ARRAY,
    )
    readable_layout: FmiThreeFloat64BindingLayout = (
        _build_fmi_three_float64_binding_layout(
            metadata=metadata,
            variable_names=readable_variable_names,
            access=_FmiThreeFloat64BindingAccess.READABLE,
            maximum_serialized_value_count=maximum_serialized_value_count,
        )
    )
    writable_layout: FmiThreeFloat64BindingLayout = (
        _build_fmi_three_float64_binding_layout(
            metadata=metadata,
            variable_names=writable_variable_names,
            access=_FmiThreeFloat64BindingAccess.STEP_WRITABLE,
            maximum_serialized_value_count=maximum_serialized_value_count,
        )
    )
    return readable_layout, writable_layout


def resolve_fmi_three_configurable_float64_binding_layouts(
    metadata: FmuModelDescription,
    readable_variable_names: tuple[str, ...],
    writable_variable_names: tuple[str, ...],
    maximum_serialized_value_count: int,
    interface_mode: FmuInterfaceMode = FmuInterfaceMode.CO_SIMULATION,
) -> tuple[FmiThreeFloat64BindingLayout, FmiThreeFloat64BindingLayout]:
    """Resolve initial layouts for Float64 arrays with referenced dimensions.

    The initial referenced sizes come from their structural UInt64 ``start``
    values. Later successful Configuration Mode writes replace those sizes by
    calling :func:`resolve_fmi_three_configured_float64_binding_layout`.

    :param metadata: Authoritative FMI 3 Co-Simulation description.
    :param readable_variable_names: Ordered scalar or array names to read.
    :param writable_variable_names: Ordered input or tunable-parameter names.
    :param maximum_serialized_value_count: Maximum values in either layout.
    :param interface_mode: Authenticated interface owning the array bindings.
    :return: Initial readable layout followed by writable layout.
    """

    _validate_fmi_three_binding_worker_profile(
        metadata=metadata,
        interface_mode=interface_mode,
        float64_profile=FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY,
    )
    readable_layout: FmiThreeFloat64BindingLayout = (
        _build_fmi_three_float64_binding_layout(
            metadata=metadata,
            variable_names=readable_variable_names,
            access=_FmiThreeFloat64BindingAccess.READABLE,
            maximum_serialized_value_count=maximum_serialized_value_count,
        )
    )
    writable_layout: FmiThreeFloat64BindingLayout = (
        _build_fmi_three_float64_binding_layout(
            metadata=metadata,
            variable_names=writable_variable_names,
            access=_FmiThreeFloat64BindingAccess.STEP_WRITABLE,
            maximum_serialized_value_count=maximum_serialized_value_count,
        )
    )
    return readable_layout, writable_layout


def resolve_fmi_three_configuration_float64_binding_layout(
    metadata: FmuModelDescription,
    configuration_variable_names: tuple[str, ...],
    maximum_serialized_value_count: int,
    float64_profile: FmiThreeWorkerFloat64Profile,
    interface_mode: FmuInterfaceMode = FmuInterfaceMode.CO_SIMULATION,
) -> FmiThreeFloat64BindingLayout:
    """Resolve bounded structural parameters for Configuration Mode.

    :param metadata: Authoritative FMI 3 Co-Simulation description.
    :param configuration_variable_names: Ordered structural Float64 names.
    :param maximum_serialized_value_count: Maximum concatenated Float64 count.
    :param float64_profile: Scalar or constant-array binding profile.
    :param interface_mode: Authenticated FMI interface owning Configuration Mode.
    :return: Minimal ordered configuration layout.
    """

    _validate_fmi_three_binding_worker_profile(
        metadata=metadata,
        interface_mode=interface_mode,
        float64_profile=float64_profile,
    )
    return _build_fmi_three_float64_binding_layout(
        metadata=metadata,
        variable_names=configuration_variable_names,
        access=_FmiThreeFloat64BindingAccess.CONFIGURATION_WRITABLE,
        maximum_serialized_value_count=maximum_serialized_value_count,
    )


def resolve_fmi_three_initialization_float64_binding_layout(
    metadata: FmuModelDescription,
    initialization_variable_names: tuple[str, ...],
    maximum_serialized_value_count: int,
    float64_profile: FmiThreeWorkerFloat64Profile,
    interface_mode: FmuInterfaceMode = FmuInterfaceMode.CO_SIMULATION,
) -> FmiThreeFloat64BindingLayout:
    """Resolve values written exclusively while Initialization Mode is active.

    This layout is intentionally independent from the later step-write layout:
    fixed parameters belong here, while only inputs and tunable parameters may
    remain writable after initialization.

    :param metadata: Authoritative FMI 3 model description.
    :param initialization_variable_names: Ordered parameters followed by inputs.
    :param maximum_serialized_value_count: Maximum concatenated Float64 count.
    :param float64_profile: Authenticated scalar or array worker profile.
    :param interface_mode: FMI interface owning Initialization Mode.
    :return: Minimal ordered initialization layout.
    """

    _validate_fmi_three_binding_worker_profile(
        metadata=metadata,
        interface_mode=interface_mode,
        float64_profile=float64_profile,
    )
    return _build_fmi_three_float64_binding_layout(
        metadata=metadata,
        variable_names=initialization_variable_names,
        access=_FmiThreeFloat64BindingAccess.INITIALIZATION_WRITABLE,
        maximum_serialized_value_count=maximum_serialized_value_count,
    )


def resolve_fmi_three_configuration_uint64_binding_references(
    metadata: FmuModelDescription,
    configuration_variable_names: tuple[str, ...],
    float64_profile: FmiThreeWorkerFloat64Profile,
    interface_mode: FmuInterfaceMode = FmuInterfaceMode.CO_SIMULATION,
) -> tuple[int, ...]:
    """Resolve ordered scalar UInt64 structural-parameter references.

    :param metadata: Authoritative FMI 3 Co-Simulation description.
    :param configuration_variable_names: Ordered structural UInt64 names.
    :param float64_profile: Scalar or constant-array Float64 binding profile.
    :param interface_mode: Authenticated FMI interface owning Configuration Mode.
    :return: Minimal ordered UInt32 references with no retained names.
    :raises ValueError: If a name is absent, repeated, mistyped, or unwritable.
    """

    _validate_fmi_three_binding_worker_profile(
        metadata=metadata,
        interface_mode=interface_mode,
        float64_profile=float64_profile,
    )
    variables_by_name: dict[str, FmuVariableDescription] = dict()
    declared_variable: FmuVariableDescription
    for declared_variable in metadata.variables:
        variables_by_name[declared_variable.name] = declared_variable
    value_references: list[int] = [0] * len(configuration_variable_names)
    observed_names: set[str] = set()
    variable_index: int
    for variable_index in range(len(configuration_variable_names)):
        variable_name: str = configuration_variable_names[variable_index]
        if variable_name in observed_names:
            raise ValueError(
                f"Duplicate FMI 3 UInt64 binding for variable {variable_name!r}"
            )
        else:
            observed_names.add(variable_name)
        variable: FmuVariableDescription | None = variables_by_name.get(
            variable_name,
            None,
        )
        if variable is not None:
            pass
        else:
            raise ValueError(
                f"FMI 3 binding variable {variable_name!r} was not found"
            )
        if variable.variable_type == FmuVariableType.UINT64:
            pass
        else:
            raise ValueError(
                f"FMI 3 binding variable {variable_name!r} is not UInt64"
            )
        if len(variable.dimensions) == 0:
            pass
        else:
            raise ValueError(
                f"FMI 3 UInt64 configuration variable {variable_name!r} is not scalar"
            )
        if is_fmi_three_configuration_mode_writable(variable):
            pass
        else:
            raise ValueError(
                f"FMI 3 binding variable {variable_name!r} is not a structural "
                "parameter writable in Configuration Mode"
            )
        value_references[variable_index] = variable.value_reference
    return tuple(value_references)


def validate_bindings(metadata: FmuModelDescription, bindings: tuple[FmuVariableBinding, ...]) -> None:
    """Validate that the VeraGrid bindings respect the FMU variable causalities."""

    seen_signal_names: set[tuple[str, FmuBindingDirection]] = set()
    binding: FmuVariableBinding
    for binding in bindings:
        key: tuple[str, FmuBindingDirection] = (binding.signal_name, binding.direction)
        if key in seen_signal_names:
            raise ValueError(
                f"Duplicate FMU binding for signal {binding.signal_name!r} and direction {binding.direction.value!r}"
            )
        else:
            seen_signal_names.add(key)

        variable = metadata.get_variable(binding.variable_name)
        causality: str = variable.causality or "local"
        if binding.direction == FmuBindingDirection.INPUT:
            if causality not in {"input", "parameter"}:
                raise ValueError(
                    f"Variable {binding.variable_name!r} is not bindable as FMU input (causality={causality!r})"
                )
            else:
                pass
        else:
            if binding.direction == FmuBindingDirection.OUTPUT:
                if causality not in {"output", "local"}:
                    raise ValueError(
                        f"Variable {binding.variable_name!r} is not bindable as FMU output (causality={causality!r})"
                    )
                else:
                    pass
            else:
                if binding.direction == FmuBindingDirection.PARAMETER:
                    if causality != "parameter":
                        raise ValueError(
                            f"Variable {binding.variable_name!r} is not bindable as FMU parameter (causality={causality!r})"
                        )
                    else:
                        pass
                else:
                    raise ValueError(f"Unsupported FMU binding direction {binding.direction!r}")
