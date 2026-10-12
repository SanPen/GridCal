# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pathlib import Path
import warnings

from VeraGridEngine.IO.fmu.Elements.inspection import FmuInspectionReceipt
from VeraGridEngine.IO.fmu.config import parse_declared_fmi_version
from VeraGridEngine.enumerations import FmiVersion, FmuInterfaceMode, FmuVariableType


class FmiThreeVariableDimension:
    """Store one constant or value-reference-controlled FMI 3 dimension.

    :param constant_size: Positive constant UInt64 size, or ``None``.
    :param value_reference: Controlling UInt64 variable reference, or ``None``.
    """

    __slots__ = ("constant_size", "value_reference")

    def __init__(
        self,
        constant_size: int | None,
        value_reference: int | None,
    ) -> None:
        """Validate and store exactly one dimension source.

        :param constant_size: Positive constant UInt64 size, or ``None``.
        :param value_reference: Controlling UInt64 variable reference, or ``None``.
        :return: None.
        """

        if constant_size is not None and value_reference is None:
            if constant_size > 0 and constant_size <= 18446744073709551615:
                pass
            else:
                raise ValueError(
                    "FMI 3 constant array dimension must fit positive UInt64"
                )
        else:
            if constant_size is None and value_reference is not None:
                if value_reference >= 0 and value_reference <= 4294967295:
                    pass
                else:
                    raise ValueError(
                        "FMI 3 dimension value reference must fit UInt32"
                    )
            else:
                raise ValueError(
                    "FMI 3 dimension must own one constant size or value reference"
                )
        self.constant_size: int | None = constant_size
        self.value_reference: int | None = value_reference


class FmuVariableDescription:
    """Store the metadata for one FMU variable.

    :param name: FMI variable name.
    :param value_reference: FMI value reference.
    :param variable_type: FMI primitive element type.
    :param causality: FMI causality string.
    :param variability: FMI variability string.
    :param initial: FMI initial string.
    :param start: FMI start value string.
    :param derivative_index: FMI 1 or FMI 2 derivative index if available.
    :param state_value_reference: FMI 3 state referenced by this derivative.
    :param dimensions: Ordered FMI 3 dimensions, or an empty tuple for scalar
        and FMI 1/2 variables.
    """

    __slots__ = (
        "name",
        "value_reference",
        "variable_type",
        "causality",
        "variability",
        "initial",
        "start",
        "derivative_index",
        "state_value_reference",
        "dimensions",
    )

    def __init__(
        self,
        name: str,
        value_reference: int,
        variable_type: FmuVariableType,
        causality: str | None,
        variability: str | None,
        initial: str | None,
        start: str | None,
        derivative_index: int | None,
        state_value_reference: int | None = None,
        dimensions: tuple[FmiThreeVariableDimension, ...] = tuple(),
    ) -> None:
        """Store the parsed variable metadata.

        :param name: FMI variable name.
        :param value_reference: FMI value reference.
        :param variable_type: FMI primitive type.
        :param causality: Effective FMI causality.
        :param variability: Effective FMI variability.
        :param initial: Effective FMI initial condition.
        :param start: FMI start value text, when represented by the parser.
        :param derivative_index: FMI 1 or FMI 2 derivative index.
        :param state_value_reference: FMI 3 state referenced by this derivative.
        :param dimensions: Ordered constant or referenced FMI 3 dimensions.
        :return: None.
        """

        self.name: str = name
        self.value_reference: int = value_reference
        self.variable_type: FmuVariableType = variable_type
        self.causality: str | None = causality
        self.variability: str | None = variability
        self.initial: str | None = initial
        self.start: str | None = start
        self.derivative_index: int | None = derivative_index
        self.state_value_reference: int | None = state_value_reference
        dimension: FmiThreeVariableDimension
        for dimension in dimensions:
            if isinstance(dimension, FmiThreeVariableDimension):
                pass
            else:
                raise ValueError("FMI 3 variable dimension owner is invalid")
        self.dimensions: tuple[FmiThreeVariableDimension, ...] = tuple(dimensions)


class FmiOneCoSimulationCapabilities:
    """Store FMI 1 Co-Simulation identity and capability values.

    :param needs_execution_tool: Whether the declaration requires its original tool.
    :param can_handle_variable_communication_step_size: Whether step sizes may differ.
    :param can_handle_events: Whether the slave can handle events internally.
    :param can_reject_steps: Whether ``fmiDoStep`` may reject a step.
    :param can_interpolate_inputs: Whether input derivatives can be used.
    :param max_output_derivative_order: Maximum output derivative order.
    :param can_run_asynchronuously: Whether execution may complete asynchronously.
    :param can_signal_events: Whether the slave can signal events.
    :param can_be_instantiated_only_once_per_process: Process-local instance limit.
    :param can_not_use_memory_management_functions: Callback allocator restriction.
    """

    __slots__ = (
        "needs_execution_tool",
        "can_handle_variable_communication_step_size",
        "can_handle_events",
        "can_reject_steps",
        "can_interpolate_inputs",
        "max_output_derivative_order",
        "can_run_asynchronuously",
        "can_signal_events",
        "can_be_instantiated_only_once_per_process",
        "can_not_use_memory_management_functions",
    )

    def __init__(
        self,
        needs_execution_tool: bool,
        can_handle_variable_communication_step_size: bool,
        can_handle_events: bool,
        can_reject_steps: bool,
        can_interpolate_inputs: bool,
        max_output_derivative_order: int,
        can_run_asynchronuously: bool,
        can_signal_events: bool,
        can_be_instantiated_only_once_per_process: bool,
        can_not_use_memory_management_functions: bool,
    ) -> None:
        """Store the validated FMI 1 capability declaration.

        :param needs_execution_tool: Whether an external tool is required.
        :param can_handle_variable_communication_step_size: Variable-step support.
        :param can_handle_events: Internal event-handling support.
        :param can_reject_steps: Step-rejection support.
        :param can_interpolate_inputs: Input-interpolation support.
        :param max_output_derivative_order: Maximum output derivative order.
        :param can_run_asynchronuously: Asynchronous-execution support.
        :param can_signal_events: Event-signalling support.
        :param can_be_instantiated_only_once_per_process: Single-instance limit.
        :param can_not_use_memory_management_functions: Callback allocator restriction.
        :return: None.
        """

        if 0 <= max_output_derivative_order <= 4294967295:
            pass
        else:
            raise ValueError("FMI 1 maximum output derivative order must fit UInt32")
        self.needs_execution_tool: bool = needs_execution_tool
        self.can_handle_variable_communication_step_size: bool = (
            can_handle_variable_communication_step_size
        )
        self.can_handle_events: bool = can_handle_events
        self.can_reject_steps: bool = can_reject_steps
        self.can_interpolate_inputs: bool = can_interpolate_inputs
        self.max_output_derivative_order: int = max_output_derivative_order
        self.can_run_asynchronuously: bool = can_run_asynchronuously
        self.can_signal_events: bool = can_signal_events
        self.can_be_instantiated_only_once_per_process: bool = (
            can_be_instantiated_only_once_per_process
        )
        self.can_not_use_memory_management_functions: bool = (
            can_not_use_memory_management_functions
        )


class FmiThreeCoSimulationCapabilities:
    """Store FMI 3 Co-Simulation capabilities that control host lifecycle.

    :param needs_execution_tool: Whether an external execution tool is required.
    :param can_be_instantiated_only_once_per_process: Whether one process may
        instantiate the FMU only once.
    :param can_get_and_set_fmu_state: Whether native state checkpoints are
        supported.
    :param can_serialize_fmu_state: Whether native state checkpoints can be
        serialized.
    :param can_handle_variable_communication_step_size: Whether communication
        step sizes may vary between calls.
    :param provides_intermediate_update: Whether Intermediate Update is provided.
    :param might_return_early_from_do_step: Whether ``doStep`` may return early.
    :param can_return_early_after_intermediate_update: Whether an intermediate
        callback may request an early return.
    :param has_event_mode: Whether Co-Simulation Event Mode is available.
    :param fixed_internal_step_size: Optional declared fixed internal step size.
    """

    __slots__ = (
        "needs_execution_tool",
        "can_be_instantiated_only_once_per_process",
        "can_get_and_set_fmu_state",
        "can_serialize_fmu_state",
        "can_handle_variable_communication_step_size",
        "provides_intermediate_update",
        "might_return_early_from_do_step",
        "can_return_early_after_intermediate_update",
        "has_event_mode",
        "fixed_internal_step_size",
    )

    def __init__(
        self,
        needs_execution_tool: bool,
        can_be_instantiated_only_once_per_process: bool,
        can_get_and_set_fmu_state: bool,
        can_serialize_fmu_state: bool,
        can_handle_variable_communication_step_size: bool,
        provides_intermediate_update: bool,
        might_return_early_from_do_step: bool,
        can_return_early_after_intermediate_update: bool,
        has_event_mode: bool,
        fixed_internal_step_size: float | None,
    ) -> None:
        """Store the validated lifecycle-relevant capability values.

        :param needs_execution_tool: Whether an external execution tool is required.
        :param can_be_instantiated_only_once_per_process: Whether one process may
            instantiate the FMU only once.
        :param can_get_and_set_fmu_state: Whether Get/Set/FreeFMUState is
            available.
        :param can_serialize_fmu_state: Whether FMI state byte serialization is
            available.
        :param can_handle_variable_communication_step_size: Whether communication
            step sizes may vary between calls.
        :param provides_intermediate_update: Whether Intermediate Update is provided.
        :param might_return_early_from_do_step: Whether ``doStep`` may return early.
        :param can_return_early_after_intermediate_update: Whether an intermediate
            callback may request an early return.
        :param has_event_mode: Whether Co-Simulation Event Mode is available.
        :param fixed_internal_step_size: Optional fixed internal step size.
        :return: None.
        """

        self.needs_execution_tool: bool = needs_execution_tool
        self.can_be_instantiated_only_once_per_process: bool = (
            can_be_instantiated_only_once_per_process
        )
        self.can_get_and_set_fmu_state: bool = can_get_and_set_fmu_state
        self.can_serialize_fmu_state: bool = can_serialize_fmu_state
        self.can_handle_variable_communication_step_size: bool = (
            can_handle_variable_communication_step_size
        )
        self.provides_intermediate_update: bool = provides_intermediate_update
        self.might_return_early_from_do_step: bool = might_return_early_from_do_step
        self.can_return_early_after_intermediate_update: bool = (
            can_return_early_after_intermediate_update
        )
        self.has_event_mode: bool = has_event_mode
        self.fixed_internal_step_size: float | None = fixed_internal_step_size


class FmiThreeModelExchangeCapabilities:
    """Store FMI 3 Model Exchange capabilities that control host lifecycle.

    :param needs_execution_tool: Whether an external execution tool is required.
    :param can_be_instantiated_only_once_per_process: Whether one process may
        instantiate the FMU only once.
    :param can_get_and_set_fmu_state: Whether native state checkpoints are
        supported.
    :param can_serialize_fmu_state: Whether native state checkpoints can be
        serialized.
    :param needs_completed_integrator_step: Whether the importer must call
        ``completedIntegratorStep`` after successful integrator steps.
    :param provides_evaluate_discrete_states: Whether the FMU provides the
        optional discrete-state evaluation function.
    """

    __slots__ = (
        "needs_execution_tool",
        "can_be_instantiated_only_once_per_process",
        "can_get_and_set_fmu_state",
        "can_serialize_fmu_state",
        "needs_completed_integrator_step",
        "provides_evaluate_discrete_states",
    )

    def __init__(
        self,
        needs_execution_tool: bool,
        can_be_instantiated_only_once_per_process: bool,
        can_get_and_set_fmu_state: bool,
        can_serialize_fmu_state: bool,
        needs_completed_integrator_step: bool,
        provides_evaluate_discrete_states: bool,
    ) -> None:
        """Store the validated lifecycle-relevant capability values.

        :param needs_execution_tool: Whether an external execution tool is required.
        :param can_be_instantiated_only_once_per_process: Whether one process may
            instantiate the FMU only once.
        :param can_get_and_set_fmu_state: Whether Get/Set/FreeFMUState is
            available.
        :param can_serialize_fmu_state: Whether FMI state byte serialization is
            available.
        :param needs_completed_integrator_step: Whether completed integrator-step
            notification is required.
        :param provides_evaluate_discrete_states: Whether direct discrete-state
            evaluation is available.
        :return: None.
        """

        self.needs_execution_tool: bool = needs_execution_tool
        self.can_be_instantiated_only_once_per_process: bool = (
            can_be_instantiated_only_once_per_process
        )
        self.can_get_and_set_fmu_state: bool = can_get_and_set_fmu_state
        self.can_serialize_fmu_state: bool = can_serialize_fmu_state
        self.needs_completed_integrator_step: bool = needs_completed_integrator_step
        self.provides_evaluate_discrete_states: bool = provides_evaluate_discrete_states


class FmuModelDescription:
    """Store validated model-description metadata extracted from an FMU.

    :param path: Absolute FMU path.
    :param fmi_version: FMI version string.
    :param model_name: Model name declared in the FMU.
    :param guid: FMI 1 or FMI 2 GUID; FMI 3 does not declare this attribute.
    :param variable_naming_convention: FMI naming convention.
    :param number_of_continuous_states: Validated continuous-state cardinality.
    :param number_of_event_indicators: Number of declared event indicators.
    :param interface_modes: Interfaces declared by the FMU.
    :param model_identifiers: Mapping from declared interface to model identifier.
    :param platforms: Available binary platforms.
    :param variables: Ordered variables.
    :param fmi_version_family: Canonical FMI version family.
    :param inspection_receipt: Receipt identifying the inspected source bytes.
    :param instantiation_token: Required FMI 3 model-instantiation identity.
    :param fmi_one_co_simulation_capabilities: FMI 1 Co-Simulation identity and
        capabilities when that interface is declared.
    :param fmi_three_co_simulation_capabilities: Lifecycle-relevant FMI 3
        Co-Simulation capabilities when that interface is declared.
    :param fmi_three_model_exchange_capabilities: Lifecycle-relevant FMI 3
        Model Exchange capabilities when that interface is declared.
    """

    __slots__ = (
        "path",
        "fmi_version",
        "fmi_version_family",
        "inspection_receipt",
        "model_name",
        "guid",
        "variable_naming_convention",
        "number_of_continuous_states",
        "number_of_event_indicators",
        "interface_modes",
        "model_identifiers",
        "platforms",
        "variables",
        "instantiation_token",
        "fmi_one_co_simulation_capabilities",
        "fmi_three_co_simulation_capabilities",
        "fmi_three_model_exchange_capabilities",
    )

    def __init__(
        self,
        path: Path,
        fmi_version: str,
        model_name: str,
        guid: str | None,
        variable_naming_convention: str | None,
        number_of_event_indicators: int,
        interface_modes: tuple[FmuInterfaceMode, ...],
        model_identifiers: dict[FmuInterfaceMode, str],
        platforms: tuple[str, ...],
        variables: tuple[FmuVariableDescription, ...],
        fmi_version_family: FmiVersion | None = None,
        inspection_receipt: FmuInspectionReceipt | None = None,
        instantiation_token: str | None = None,
        number_of_continuous_states: int | None = None,
        fmi_one_co_simulation_capabilities: FmiOneCoSimulationCapabilities | None = None,
        fmi_three_co_simulation_capabilities: FmiThreeCoSimulationCapabilities | None = None,
        fmi_three_model_exchange_capabilities: FmiThreeModelExchangeCapabilities | None = None,
    ) -> None:
        """Store validated model-description metadata.

        :param path: Absolute FMU path.
        :param fmi_version: Exact FMI version declared by the source.
        :param model_name: Model name declared by the FMU.
        :param guid: FMI 1 or FMI 2 GUID.
        :param variable_naming_convention: FMI variable naming convention.
        :param number_of_continuous_states: Explicit state cardinality, or
            ``None`` to derive it from derivative metadata for FMI 2/3.
        :param number_of_event_indicators: Number of declared event indicators.
        :param interface_modes: Interfaces declared by the FMU.
        :param model_identifiers: Model identifier for each declared interface.
        :param platforms: Binary platforms discovered during archive inspection.
        :param variables: Ordered variables.
        :param fmi_version_family: Canonical FMI version family.
        :param inspection_receipt: Content-bound archive inspection receipt.
        :param instantiation_token: FMI 3 instantiation token.
        :param fmi_one_co_simulation_capabilities: FMI 1 Co-Simulation
            capabilities, or ``None`` for FMI 1 ME and other families.
        :param fmi_three_co_simulation_capabilities: FMI 3 Co-Simulation
            capabilities, or ``None`` when that interface is not declared.
        :param fmi_three_model_exchange_capabilities: FMI 3 Model Exchange
            capabilities, or ``None`` when that interface is not declared.
        :return: None.
        :raises ValueError: If version, receipt, GUID, or instantiation-token
            metadata conflicts with the declared FMI family.
        """

        self.path: Path = path
        self.fmi_version: str = fmi_version
        declared_family: FmiVersion = parse_declared_fmi_version(fmi_version)
        if fmi_version_family is None:
            self.fmi_version_family: FmiVersion = declared_family
        else:
            if fmi_version_family == declared_family:
                self.fmi_version_family = fmi_version_family
            else:
                raise ValueError(
                    "The FMI version family conflicts with the source declaration"
                )
        if inspection_receipt is None or inspection_receipt.path == path:
            self.inspection_receipt: FmuInspectionReceipt | None = inspection_receipt
        else:
            raise ValueError("The FMI inspection receipt belongs to a different source path")
        self.model_name: str = model_name
        if self.fmi_version_family == FmiVersion.FMI_3_0:
            if guid is None:
                self.guid: str | None = None
            else:
                raise ValueError("FMI 3 metadata cannot declare an FMI 1 or FMI 2 GUID")
        else:
            if guid is not None and len(guid.strip()) > 0:
                self.guid = guid
            else:
                raise ValueError("FMI 1 and FMI 2 metadata require a GUID")
        self.variable_naming_convention: str | None = variable_naming_convention
        if number_of_continuous_states is None:
            derived_state_count: int = 0
            declared_variable: FmuVariableDescription
            for declared_variable in variables:
                if (
                    declared_variable.derivative_index is not None
                    or declared_variable.state_value_reference is not None
                ):
                    derived_state_count += 1
                else:
                    pass
            self.number_of_continuous_states: int = derived_state_count
        else:
            if 0 <= number_of_continuous_states <= 4294967295:
                self.number_of_continuous_states = number_of_continuous_states
            else:
                raise ValueError("FMI continuous-state count must fit UInt32")
        self.number_of_event_indicators: int = number_of_event_indicators
        self.interface_modes: tuple[FmuInterfaceMode, ...] = interface_modes
        self.model_identifiers: dict[FmuInterfaceMode, str] = model_identifiers
        self.platforms: tuple[str, ...] = platforms
        self.variables: tuple[FmuVariableDescription, ...] = variables
        if self.fmi_version_family == FmiVersion.FMI_3_0:
            pass
        else:
            variable: FmuVariableDescription
            for variable in self.variables:
                if len(variable.dimensions) == 0:
                    pass
                else:
                    raise ValueError(
                        "FMI 1 and FMI 2 variables cannot declare FMI 3 array dimensions"
                    )
        self.fmi_three_co_simulation_capabilities: (
            FmiThreeCoSimulationCapabilities | None
        ) = fmi_three_co_simulation_capabilities
        self.fmi_three_model_exchange_capabilities: (
            FmiThreeModelExchangeCapabilities | None
        ) = fmi_three_model_exchange_capabilities
        self.fmi_one_co_simulation_capabilities: (
            FmiOneCoSimulationCapabilities | None
        ) = fmi_one_co_simulation_capabilities
        if self.fmi_version_family == FmiVersion.FMI_1_0:
            if FmuInterfaceMode.CO_SIMULATION in self.interface_modes:
                if self.fmi_one_co_simulation_capabilities is not None:
                    pass
                else:
                    raise ValueError(
                        "FMI 1 Co-Simulation metadata requires its capability declaration"
                    )
            else:
                if self.fmi_one_co_simulation_capabilities is None:
                    pass
                else:
                    raise ValueError(
                        "FMI 1 Co-Simulation capabilities require that interface"
                    )
        else:
            if self.fmi_one_co_simulation_capabilities is None:
                pass
            else:
                raise ValueError(
                    "Only FMI 1 may declare FMI 1 Co-Simulation capabilities"
                )
        if self.fmi_version_family == FmiVersion.FMI_3_0:
            if instantiation_token is not None and len(instantiation_token.strip()) > 0:
                self.instantiation_token: str | None = instantiation_token
            else:
                raise ValueError("FMI 3 metadata requires an instantiation token")
            if FmuInterfaceMode.CO_SIMULATION in self.interface_modes:
                if self.fmi_three_co_simulation_capabilities is not None:
                    pass
                else:
                    raise ValueError(
                        "FMI 3 Co-Simulation metadata requires its capability declaration"
                    )
            else:
                if self.fmi_three_co_simulation_capabilities is None:
                    pass
                else:
                    raise ValueError(
                        "FMI 3 Co-Simulation capabilities require that interface"
                    )
            if FmuInterfaceMode.MODEL_EXCHANGE in self.interface_modes:
                if self.fmi_three_model_exchange_capabilities is not None:
                    pass
                else:
                    raise ValueError(
                        "FMI 3 Model Exchange metadata requires its capability declaration"
                    )
            else:
                if self.fmi_three_model_exchange_capabilities is None:
                    pass
                else:
                    raise ValueError(
                        "FMI 3 Model Exchange capabilities require that interface"
                    )
        else:
            if instantiation_token is None:
                self.instantiation_token = None
            else:
                raise ValueError("FMI 1 and FMI 2 metadata cannot declare an instantiation token")
            if (
                self.fmi_three_co_simulation_capabilities is None
                and self.fmi_three_model_exchange_capabilities is None
            ):
                pass
            else:
                raise ValueError(
                    "FMI 1 and FMI 2 metadata cannot declare FMI 3 capabilities"
                )

    def get_model_identifier(self, mode: FmuInterfaceMode) -> str:
        """Return the FMI `modelIdentifier` for the requested mode.

        :param mode: Requested FMI execution mode.
        :return: The FMI model identifier.
        :raises RuntimeError: If the FMU does not declare the requested interface.
        """

        model_identifier: str | None = self.model_identifiers.get(mode, None)
        if model_identifier is None:
            raise RuntimeError(f"The FMU does not support mode {mode.value}")
        else:
            return model_identifier

    def get_supports_co_simulation(self) -> bool:
        """Return whether the FMU declares the Co-Simulation interface.

        :return: `True` when Co-Simulation is declared.
        """

        return FmuInterfaceMode.CO_SIMULATION in self.interface_modes

    def get_supports_model_exchange(self) -> bool:
        """Return whether the FMU declares the Model Exchange interface.

        :return: `True` when Model Exchange is declared.
        """

        return FmuInterfaceMode.MODEL_EXCHANGE in self.interface_modes

    def get_variable_names(self) -> tuple[str, ...]:
        """Return the ordered variable names.

        :return: Tuple with the FMU variable names.
        """

        variable_names: list[str] = list()
        variable: FmuVariableDescription
        for variable in self.variables:
            variable_names.append(variable.name)
        return tuple(variable_names)

    def get_variable(self, name: str) -> FmuVariableDescription:
        """Return the variable metadata for the requested name.

        :param name: Requested FMU variable name.
        :return: Matching variable metadata.
        :raises KeyError: If no declared variable has the requested name.
        """

        matching_variable: FmuVariableDescription | None = None
        declared_variable: FmuVariableDescription
        for declared_variable in self.variables:
            if declared_variable.name == name:
                matching_variable = declared_variable
            else:
                pass

        if matching_variable is None:
            raise KeyError(name)
        else:
            return matching_variable

    def get_state_variables(self) -> tuple[FmuVariableDescription, ...]:
        """Return the FMI variables representing continuous states.

        :return: Tuple with the continuous-state variables.
        """

        state_variables: list[FmuVariableDescription] = list()
        if self.fmi_version_family == FmiVersion.FMI_3_0:
            variables_by_value_reference: dict[int, FmuVariableDescription] = dict()
            declared_variable: FmuVariableDescription
            for declared_variable in self.variables:
                variables_by_value_reference[declared_variable.value_reference] = declared_variable

            derivative_variable: FmuVariableDescription
            for derivative_variable in self.variables:
                state_value_reference: int | None = derivative_variable.state_value_reference
                if state_value_reference is None:
                    pass
                else:
                    state_variable: FmuVariableDescription = variables_by_value_reference[
                        state_value_reference
                    ]
                    state_variables.append(state_variable)
        else:
            variable: FmuVariableDescription
            for variable in self.variables:
                if variable.causality == "output" and variable.variability == "continuous":
                    state_variables.append(variable)
                else:
                    pass
        return tuple(state_variables)

    def get_derivative_variables(self) -> tuple[FmuVariableDescription, ...]:
        """Return the FMI variables representing continuous derivatives.

        :return: Tuple with the derivative variables.
        """

        derivative_variables: list[FmuVariableDescription] = list()
        variable: FmuVariableDescription
        for variable in self.variables:
            if self.fmi_version_family == FmiVersion.FMI_3_0:
                if variable.state_value_reference is not None:
                    derivative_variables.append(variable)
                else:
                    pass
            else:
                if variable.derivative_index is not None:
                    derivative_variables.append(variable)
                else:
                    pass
        return tuple(derivative_variables)

    def select_declared_interface(
        self,
        preferred_interface: FmuInterfaceMode | None = None,
    ) -> FmuInterfaceMode:
        """Select one interface declared by the FMU.

        This method only resolves model-description metadata. Runtime consumers
        must use ``FmuImportConfig.resolve_execution_mode`` before staging or
        allocating simulation state.

        :param preferred_interface: Preferred FMI interface, when specified.
        :return: Declared interface selected from the metadata.
        :raises RuntimeError: If the preferred interface is absent or no supported
            interface is declared.
        """

        if preferred_interface is not None:
            if preferred_interface in self.interface_modes:
                return preferred_interface
            else:
                raise RuntimeError(
                    f"The FMU does not declare preferred interface {preferred_interface.value}"
                )
        else:
            if len(self.interface_modes) == 1:
                return self.interface_modes[0]
            else:
                if FmuInterfaceMode.CO_SIMULATION in self.interface_modes:
                    return FmuInterfaceMode.CO_SIMULATION
                else:
                    if FmuInterfaceMode.MODEL_EXCHANGE in self.interface_modes:
                        return FmuInterfaceMode.MODEL_EXCHANGE
                    else:
                        raise RuntimeError("The FMU does not declare Co-Simulation or Model Exchange")

    def resolve_mode(
        self,
        preferred_mode: FmuInterfaceMode | None = None,
    ) -> FmuInterfaceMode:
        """Select a declared interface through the deprecated method name.

        This compatibility method does not approve runtime execution. New code
        must call ``select_declared_interface`` for metadata selection or
        ``FmuImportConfig.resolve_execution_mode`` at an execution boundary.

        :param preferred_mode: Preferred FMI interface, when specified.
        :return: Declared interface selected from the metadata.
        :raises RuntimeError: If the preferred interface is absent or no supported
            interface is declared.
        """

        warnings.warn(
            "FmuModelDescription.resolve_mode() is deprecated; use "
            "select_declared_interface()",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.select_declared_interface(preferred_mode)
