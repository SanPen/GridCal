# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
from VeraGridEngine.enumerations import FmuDeviceDomain as FmuMeDomain

import math
from typing import TYPE_CHECKING, Any, Optional

import numpy as np

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Parents.branch_parent import BranchParent
from VeraGridEngine.Devices.Parents.injection_parent import InjectionParent
from VeraGridEngine.enumerations import (
    DeviceType,
    DynamicIntegrationMethod,
    FmiVersion,
    ParamPowerFlowReferenceType,
    VarPowerFlowReferenceType,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var

from VeraGridEngine.IO.fmu.Elements.bindings import (
    FmiThreeConfigurationSessionValues,
    FmiThreeFloat64ConfigurationValue,
    FmiThreeFloat64SessionValueSelector,
    FmiThreeUInt64ConfigurationValue,
    FmuFloat64ParameterValue,
    FmuImportConfig,
    FmuRefBinding,
    _build_fmi_three_configuration_session_values,
    _reject_indexed_fmu_ref_bindings,
    _validate_fmi_three_configuration_values,
    validate_fmu_float64_parameter_values,
    resolve_fmi_three_float64_session_value_selectors,
)
from VeraGridEngine.IO.fmu.Elements.device_configuration import (
    FmuCsDeviceConfigRecord, FmuMeDeviceConfigRecord, build_import_config_from_record,
    load_fmu_me_device_config, _resolve_parameter_values_from_block,
)
from VeraGridEngine.IO.fmu.co_simulation import (
    _build_template_block,
    _ensure_emt_external_mapping_keys,
)
from VeraGridEngine.IO.fmu.model_description import FmuInterfaceMode, FmuModelDescription, FmuVariableDescription, read_fmu_model_description
from VeraGridEngine.IO.fmu.host import (
    FmiOneEventUpdate,
    FmiTwoEventUpdate,
    FmuRuntimeHost,
    open_fmu_runtime_host,
)
from VeraGridEngine.IO.fmu.profile import (
    FmuMeEvaluationBudget,
    FmiThreeWorkerFloat64Profile,
    resolve_fmi_three_worker_float64_profile,
    validate_fmi_three_model_exchange_worker_profile,
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

if TYPE_CHECKING:
    from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
    from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
else:
    pass




class FmuMeSolverPolicy:
    """Store the simulation-owned numerical limits for one FMI ME adapter.

    :param integration_method: Integration method selected by the simulation.
    :param absolute_tolerance: Absolute Backward Euler Newton scale.
    :param relative_tolerance: Relative Backward Euler Newton scale.
    :param maximum_newton_iterations: Maximum number of Newton updates.
    :param maximum_continuous_states: Maximum dense state-vector dimension.
    """

    __slots__ = (
        "integration_method",
        "absolute_tolerance",
        "relative_tolerance",
        "maximum_newton_iterations",
        "maximum_continuous_states",
    )

    def __init__(
        self,
        integration_method: DynamicIntegrationMethod,
        absolute_tolerance: float,
        relative_tolerance: float,
        maximum_newton_iterations: int,
        maximum_continuous_states: int,
    ) -> None:
        """Validate and store one immutable-by-interface solver policy.

        :param integration_method: Simulation integration method.
        :param absolute_tolerance: Finite positive absolute tolerance.
        :param relative_tolerance: Finite positive relative tolerance.
        :param maximum_newton_iterations: Integer limit from 1 through 100.
        :param maximum_continuous_states: Integer limit from 1 through 128.
        :return: None.
        """

        if integration_method == DynamicIntegrationMethod.DaeBackEuler:
            self.integration_method: DynamicIntegrationMethod = integration_method
        else:
            raise RuntimeError(
                "Attached FMI Model Exchange devices currently require "
                "DynamicIntegrationMethod.DaeBackEuler"
            )
        if math.isfinite(absolute_tolerance) and absolute_tolerance > 0.0:
            self.absolute_tolerance: float = float(absolute_tolerance)
        else:
            raise ValueError(
                "FMI ME Newton absolute tolerance must be finite and positive"
            )
        if math.isfinite(relative_tolerance) and relative_tolerance > 0.0:
            self.relative_tolerance: float = float(relative_tolerance)
        else:
            raise ValueError(
                "FMI ME Newton relative tolerance must be finite and positive"
            )
        if (
            isinstance(maximum_newton_iterations, int)
            and not isinstance(maximum_newton_iterations, bool)
            and 1 <= maximum_newton_iterations <= 100
        ):
            self.maximum_newton_iterations: int = maximum_newton_iterations
        else:
            raise ValueError(
                "FMI ME Newton iteration limit must be an integer between 1 and 100"
            )
        if (
            isinstance(maximum_continuous_states, int)
            and not isinstance(maximum_continuous_states, bool)
            and 1 <= maximum_continuous_states <= 128
        ):
            self.maximum_continuous_states: int = maximum_continuous_states
        else:
            raise ValueError(
                "FMI ME state limit must be an integer between 1 and 128"
            )


class FmuMeDeviceSpec:
    """Store the runtime metadata required to execute one FMU ME device.

    :param domain: VeraGrid domain that will consume the FMU.
    :param config: FMU runtime configuration.
    :param device_tpe: VeraGrid device type.
    :param input_variable_names: Ordered FMU input names.
    :param output_variable_names: Ordered FMU output names.
    :param state_variable_names: Ordered FMU continuous-state names.
    :param derivative_variable_names: Ordered FMU derivative names.
    :param worker_limits: Explicit FMI 3 worker supervision policy, when used.
    :param float64_profile: Derived FMI 3 worker shape profile, when used.
    :param maximum_event_iterations: Positive Event Mode convergence bound.
    :param configuration_float64_values: Structural Float64 declarations.
    :param configuration_uint64_values: Structural UInt64 declarations.
    """

    __slots__ = (
        "domain",
        "config",
        "device_tpe",
        "input_variable_names",
        "output_variable_names",
        "state_variable_names",
        "derivative_variable_names",
        "worker_limits",
        "float64_profile",
        "maximum_event_iterations",
        "input_bindings",
        "output_bindings",
        "output_defaults",
        "output_param_uids",
        "configuration_float64_values",
        "configuration_uint64_values",
        "parameter_values",
    )

    def __init__(
        self,
        domain: FmuMeDomain,
        config: FmuImportConfig,
        device_tpe: DeviceType,
        input_variable_names: tuple[str, ...],
        output_variable_names: tuple[str, ...],
        state_variable_names: tuple[str, ...],
        derivative_variable_names: tuple[str, ...],
        worker_limits: FmiThreeWorkerHostLimits | None,
        float64_profile: FmiThreeWorkerFloat64Profile | None,
        input_bindings: tuple[FmuRefBinding, ...],
        output_bindings: tuple[FmuRefBinding, ...],
        output_defaults: dict[VarPowerFlowReferenceType, float],
        output_param_uids: dict[VarPowerFlowReferenceType, int],
        maximum_event_iterations: int = 32,
        configuration_float64_values: tuple[
            FmiThreeFloat64ConfigurationValue, ...
        ] = tuple(),
        configuration_uint64_values: tuple[
            FmiThreeUInt64ConfigurationValue, ...
        ] = tuple(),
        parameter_values: tuple[FmuFloat64ParameterValue, ...] = tuple(),
    ) -> None:
        """Store the runtime FMU ME specification.

        :param domain: VeraGrid domain that consumes the FMU.
        :param config: Source and runtime import configuration.
        :param device_tpe: VeraGrid device type receiving the adapter.
        :param input_variable_names: Ordered FMU input names.
        :param output_variable_names: Ordered FMU output names.
        :param state_variable_names: Ordered continuous-state names.
        :param derivative_variable_names: Ordered continuous-derivative names.
        :param worker_limits: Explicit FMI 3 worker supervision policy.
        :param float64_profile: Derived FMI 3 worker shape profile.
        :param maximum_event_iterations: Positive Event Mode convergence bound.
        :param input_bindings: Ordered VeraGrid-to-FMU bindings.
        :param output_bindings: Ordered FMU-to-VeraGrid bindings.
        :param output_defaults: Output fallbacks used before the first sample.
        :param output_param_uids: Runtime output-parameter identifiers.
        :param configuration_float64_values: Structural Float64 declarations.
        :param configuration_uint64_values: Structural UInt64 declarations.
        :param parameter_values: Ephemeral values resolved from Block.parameters.
        :return: None.
        """

        self.domain: FmuMeDomain = domain
        self.config: FmuImportConfig = config
        self.device_tpe: DeviceType = device_tpe
        self.input_variable_names: tuple[str, ...] = input_variable_names
        self.output_variable_names: tuple[str, ...] = output_variable_names
        self.state_variable_names: tuple[str, ...] = state_variable_names
        self.derivative_variable_names: tuple[str, ...] = derivative_variable_names
        self.worker_limits: FmiThreeWorkerHostLimits | None = worker_limits
        self.float64_profile: FmiThreeWorkerFloat64Profile | None = float64_profile
        if (
            isinstance(maximum_event_iterations, int)
            and not isinstance(maximum_event_iterations, bool)
            and 1 <= maximum_event_iterations <= 1024
        ):
            self.maximum_event_iterations: int = maximum_event_iterations
        else:
            raise ValueError(
                "FMI ME maximum Event Mode iterations must be an integer between 1 and 1024"
            )
        self.input_bindings: tuple[FmuRefBinding, ...] = input_bindings
        self.output_bindings: tuple[FmuRefBinding, ...] = output_bindings
        self.output_defaults: dict[VarPowerFlowReferenceType, float] = output_defaults
        self.output_param_uids: dict[VarPowerFlowReferenceType, int] = output_param_uids
        _validate_fmi_three_configuration_values(
            configuration_float64_values=configuration_float64_values,
            configuration_uint64_values=configuration_uint64_values,
        )
        self.configuration_float64_values: tuple[
            FmiThreeFloat64ConfigurationValue, ...
        ] = tuple(configuration_float64_values)
        self.configuration_uint64_values: tuple[
            FmiThreeUInt64ConfigurationValue, ...
        ] = tuple(configuration_uint64_values)
        validate_fmu_float64_parameter_values(parameter_values=parameter_values)
        self.parameter_values: tuple[FmuFloat64ParameterValue, ...] = tuple(
            parameter_values
        )


class FmuMeDeviceAdapter:
    """Execute one FMU ME device with simulation-owned Backward Euler.

    :param spec: Runtime specification of the FMU ME device.
    :param solver_policy: Numerical policy copied from simulation options.
    """

    __slots__ = (
        "spec",
        "solver_policy",
        "runtime_host",
        "fmi_three_coordinator",
        "state_vector",
        "pending_time",
        "pending_candidate_state_values",
        "pending_candidate_input_values",
        "pending_candidate_derivative_values",
        "pending_candidate_readable_values",
        "pending_candidate_event_indicators",
        "pending_accepted_time",
        "pending_accepted_state_values",
        "pending_accepted_input_values",
        "pending_accepted_derivative_values",
        "pending_accepted_readable_values",
        "pending_accepted_event_indicators",
        "localized_state_event_time",
        "_fmi_one_state_value_references",
        "fmi_two_next_event_time",
        "fmi_two_accepted_input_values",
        "fmi_two_accepted_derivative_values",
        "fmi_two_accepted_readable_values",
        "fmi_two_accepted_event_indicators",
        "initialized",
    )

    def __init__(
        self,
        spec: FmuMeDeviceSpec,
        solver_policy: FmuMeSolverPolicy,
    ) -> None:
        """Store the FMU ME runtime adapter.

        :param spec: Validated runtime FMU specification.
        :param solver_policy: Simulation-owned Backward Euler policy.
        :return: None.
        """

        self.spec: FmuMeDeviceSpec = spec
        if solver_policy.integration_method == DynamicIntegrationMethod.DaeBackEuler:
            self.solver_policy: FmuMeSolverPolicy = solver_policy
        else:
            raise RuntimeError(
                "Attached FMI Model Exchange devices require Backward Euler"
            )
        state_count: int = len(spec.state_variable_names)
        if state_count <= solver_policy.maximum_continuous_states:
            pass
        else:
            raise RuntimeError(
                "FMI ME continuous-state count exceeds the configured dense "
                "Backward Euler limit"
            )
        self.runtime_host: Optional[FmuRuntimeHost] = None
        self.fmi_three_coordinator: FmiThreeModelExchangeCoordinator | None = None
        self.state_vector: Optional[np.ndarray] = None
        self.pending_time: float | None = None
        self.pending_candidate_state_values: tuple[float, ...] | None = None
        self.pending_candidate_input_values: tuple[float, ...] | None = None
        self.pending_candidate_derivative_values: tuple[float, ...] | None = None
        self.pending_candidate_readable_values: tuple[float, ...] | None = None
        self.pending_candidate_event_indicators: tuple[float, ...] | None = None
        self.pending_accepted_time: float | None = None
        self.pending_accepted_state_values: tuple[float, ...] | None = None
        self.pending_accepted_input_values: tuple[float, ...] | None = None
        self.pending_accepted_derivative_values: tuple[float, ...] | None = None
        self.pending_accepted_readable_values: tuple[float, ...] | None = None
        self.pending_accepted_event_indicators: tuple[float, ...] | None = None
        self.localized_state_event_time: float | None = None
        self._fmi_one_state_value_references: tuple[int, ...] = tuple()
        self.fmi_two_next_event_time: float | None = None
        self.fmi_two_accepted_input_values: tuple[float, ...] | None = None
        self.fmi_two_accepted_derivative_values: tuple[float, ...] | None = None
        self.fmi_two_accepted_readable_values: tuple[float, ...] | None = None
        self.fmi_two_accepted_event_indicators: tuple[float, ...] | None = None
        self.initialized: bool = False

    def _clear_pending_state_event_data(self) -> None:
        """Clear candidate data used only by state-event localization.

        :return: None.
        """

        self.pending_time = None
        self.pending_candidate_state_values = None
        self.pending_candidate_input_values = None
        self.pending_candidate_derivative_values = None
        self.pending_candidate_readable_values = None
        self.pending_candidate_event_indicators = None
        self.pending_accepted_time = None
        self.pending_accepted_state_values = None
        self.pending_accepted_input_values = None
        self.pending_accepted_derivative_values = None
        self.pending_accepted_readable_values = None
        self.pending_accepted_event_indicators = None

    def has_pending_candidate(self) -> bool:
        """Return whether one complete solver-owned candidate is pending.

        The local snapshot and the FMI 3 coordinator must agree because a
        disagreement would make acceptance or rollback ambiguous.

        :return: True only when every candidate and accepted-point field is
            present.
        :raises RuntimeError: If candidate state is partial or disagrees with
            the FMI 3 coordinator.
        """

        local_candidate_present: bool = (
            self.pending_time is not None
            or self.pending_candidate_state_values is not None
            or self.pending_candidate_input_values is not None
            or self.pending_candidate_derivative_values is not None
            or self.pending_candidate_readable_values is not None
            or self.pending_candidate_event_indicators is not None
            or self.pending_accepted_time is not None
            or self.pending_accepted_state_values is not None
            or self.pending_accepted_input_values is not None
            or self.pending_accepted_derivative_values is not None
            or self.pending_accepted_readable_values is not None
            or self.pending_accepted_event_indicators is not None
        )
        local_candidate_complete: bool = (
            self.pending_time is not None
            and self.pending_candidate_state_values is not None
            and self.pending_candidate_input_values is not None
            and self.pending_candidate_derivative_values is not None
            and self.pending_candidate_readable_values is not None
            and self.pending_candidate_event_indicators is not None
            and self.pending_accepted_time is not None
            and self.pending_accepted_state_values is not None
            and self.pending_accepted_input_values is not None
            and self.pending_accepted_derivative_values is not None
            and self.pending_accepted_readable_values is not None
            and self.pending_accepted_event_indicators is not None
        )
        coordinator: FmiThreeModelExchangeCoordinator | None = (
            self.fmi_three_coordinator
        )
        if coordinator is None:
            coordinator_candidate_present: bool = False
        else:
            coordinator_candidate_present = coordinator.has_pending_candidate()
        if local_candidate_present:
            if local_candidate_complete:
                if coordinator is None or coordinator_candidate_present:
                    return True
                else:
                    raise RuntimeError(
                        "FMI 3 ME local candidate has no coordinator candidate"
                    )
            else:
                raise RuntimeError("FMI ME pending candidate snapshot is partial")
        else:
            if coordinator_candidate_present:
                raise RuntimeError(
                    "FMI 3 ME coordinator candidate has no local candidate"
                )
            else:
                return False

    def _build_ordered_writable_values(
        self,
        input_values: dict[str, float],
    ) -> tuple[float, ...]:
        """Order a complete scalar input vector for one bound ME runtime.

        :param input_values: Scalar values indexed by the bound FMU input names.
        :return: Values ordered exactly like ``spec.input_variable_names``.
        :raises KeyError: If one required bound input is absent.
        :raises ValueError: If an unbound input name is present.
        """

        ordered_values: list[float] = [0.0] * len(self.spec.input_variable_names)
        input_index: int
        for input_index in range(len(self.spec.input_variable_names)):
            input_name: str = self.spec.input_variable_names[input_index]
            input_value: float | None = input_values.get(input_name, None)
            if input_value is not None:
                ordered_values[input_index] = float(input_value)
            else:
                raise KeyError(
                    f"FMI Model Exchange input {input_name!r} has no value"
                )
        if len(input_values) == len(self.spec.input_variable_names):
            pass
        else:
            raise ValueError(
                "FMI Model Exchange initialization contains an unbound input"
            )
        return tuple(ordered_values)

    def _map_named_output_values(
        self,
        readable_values: tuple[float, ...],
    ) -> dict[str, float]:
        """Map ordered readings to the adapter's existing named API.

        :param readable_values: Values ordered like ``spec.output_variable_names``.
        :return: Scalar readings indexed by bound FMU output name.
        """

        if len(readable_values) == len(self.spec.output_variable_names):
            pass
        else:
            raise RuntimeError(
                "Model Exchange readings do not match the declared output names"
            )
        unique_output_names: set[str] = set(self.spec.output_variable_names)
        if len(unique_output_names) == len(self.spec.output_variable_names):
            pass
        else:
            raise RuntimeError(
                "The named ME output API cannot represent repeated "
                "array-variable bindings"
            )
        mapped_values: dict[str, float] = dict()
        output_index: int
        for output_index in range(len(self.spec.output_variable_names)):
            mapped_values[self.spec.output_variable_names[output_index]] = float(
                readable_values[output_index]
            )
        return mapped_values

    def map_bound_output_values(
        self,
        output_values: tuple[float, ...],
    ) -> dict[VarPowerFlowReferenceType, float]:
        """Map ordered runtime values onto the declared VeraGrid references.

        :param output_values: Values ordered exactly like ``spec.output_bindings``.
        :return: Scalar readings indexed by VeraGrid output reference.
        :raises RuntimeError: If runtime and binding cardinalities differ.
        """

        if len(output_values) == len(self.spec.output_bindings):
            pass
        else:
            raise RuntimeError(
                "FMU Model Exchange readings do not match the output bindings"
            )
        mapped_values: dict[VarPowerFlowReferenceType, float] = dict()
        binding_index: int
        for binding_index in range(len(self.spec.output_bindings)):
            binding: FmuRefBinding = self.spec.output_bindings[binding_index]
            mapped_values[binding.reference] = float(output_values[binding_index])
        return mapped_values

    def _evaluate_ordered_output_values(
        self,
        time_value: float,
        input_values: dict[str, float],
        evaluation_budget: FmuMeEvaluationBudget | None = None,
    ) -> tuple[float, ...]:
        """Evaluate outputs while preserving their declared binding order.

        :param time_value: Current evaluation time.
        :param input_values: Complete scalar FMU input values.
        :param evaluation_budget: Optional owner-provided runtime-call budget.
        :return: Output values aligned with names or selected device bindings.
        """

        if evaluation_budget is not None:
            evaluation_budget.consume()
        else:
            pass
        if self.runtime_host is not None:
            self.runtime_host.set_time(time_value)
            self._apply_inputs(input_values)
            if self.state_vector is not None:
                self.runtime_host.set_continuous_states(self.state_vector.tolist())
            else:
                pass
            named_values: dict[str, float] = self.runtime_host.get_real(
                list(self.spec.output_variable_names)
            )
            ordered_values: list[float] = [0.0] * len(
                self.spec.output_variable_names
            )
            output_index: int
            for output_index in range(len(self.spec.output_variable_names)):
                output_name: str = self.spec.output_variable_names[output_index]
                ordered_values[output_index] = float(named_values[output_name])
            return tuple(ordered_values)
        else:
            if self.fmi_three_coordinator is not None:
                state_values: tuple[float, ...] = self._get_fmi_three_state_values()
                derivative_values: tuple[float, ...]
                readable_values: tuple[float, ...]
                derivative_values, readable_values = (
                    self.fmi_three_coordinator.evaluate_probe(
                        time_value=time_value,
                        continuous_state_values=state_values,
                        writable_values=(
                            self._build_ordered_writable_values(input_values)
                        ),
                    )
                )
                return readable_values
            else:
                raise RuntimeError(
                    "FMU ME adapter must be initialized before output evaluation"
                )

    def _get_fmi_three_state_values(self) -> tuple[float, ...]:
        """Copy the accepted NumPy state into the isolated session format.

        :return: Complete continuous-state vector owned by the adapter.
        :raises RuntimeError: If initialized FMI 3 state ownership was lost.
        """

        if self.state_vector is not None:
            pass
        else:
            raise RuntimeError("FMI 3 ME adapter lost its state vector")
        state_values: list[float] = [0.0] * self.state_vector.size
        state_index: int
        for state_index in range(self.state_vector.size):
            state_values[state_index] = float(self.state_vector[state_index])
        return tuple(state_values)

    def _settle_fmi_two_event_mode(
        self,
        entry_time: float,
        evaluation_budget: FmuMeEvaluationBudget,
    ) -> None:
        """Converge FMI 2 Event Mode and enter Continuous-Time Mode.

        :param entry_time: Exact time at which Event Mode was entered.
        :param evaluation_budget: Shared initialization or step call budget.
        :return: None.
        :raises RuntimeError: If the FMU requests termination.
        :raises RuntimeError: If the event fixpoint or next time is invalid.
        """

        if self.runtime_host is not None:
            runtime_host: FmuRuntimeHost = self.runtime_host
        else:
            raise RuntimeError("FMI 2 Event Mode requires an initialized host")
        normalized_entry_time: float = float(entry_time)
        if math.isfinite(normalized_entry_time):
            pass
        else:
            raise ValueError("FMI 2 Event Mode entry time must be finite")

        converged: bool = False
        event_iteration: int
        for event_iteration in range(self.spec.maximum_event_iterations):
            evaluation_budget.consume()
            event_update: FmiTwoEventUpdate = runtime_host.new_discrete_states()
            if event_update.terminate_simulation:
                raise RuntimeError(
                    "FMI 2 Model Exchange requested termination in Event Mode"
                )
            else:
                pass
            if event_update.next_event_time is not None:
                normalized_next_event_time: float = float(
                    event_update.next_event_time
                )
                if (
                    math.isfinite(normalized_next_event_time)
                    and normalized_next_event_time > normalized_entry_time
                ):
                    self.fmi_two_next_event_time = normalized_next_event_time
                else:
                    raise RuntimeError(
                        "FMI 2 nextEventTime must be finite and follow Event Mode entry"
                    )
            else:
                self.fmi_two_next_event_time = None
            if event_update.discrete_states_need_update:
                pass
            else:
                converged = True
                break
        if converged:
            evaluation_budget.consume()
            runtime_host.enter_continuous_time_mode()
        else:
            raise RuntimeError(
                "FMI 2 Model Exchange Event Mode exceeded its iteration bound"
            )

    def _apply_fmi_one_event_update(
        self,
        event_update: FmiOneEventUpdate,
        entry_time: float,
        evaluation_budget: FmuMeEvaluationBudget,
    ) -> bool:
        """Apply one complete FMI 1 event-info result to adapter state.

        :param event_update: Detached FMI 1 event information.
        :param entry_time: Exact time at which event iteration started.
        :param evaluation_budget: Shared initialization or step call budget.
        :return: Whether the FMI 1 event iteration has converged.
        :raises RuntimeError: If the FMU requests termination.
        :raises RuntimeError: If refreshed state metadata is inconsistent.
        """

        if self.runtime_host is not None:
            runtime_host: FmuRuntimeHost = self.runtime_host
        else:
            raise RuntimeError("FMI 1 event update requires an initialized host")
        normalized_entry_time: float = float(entry_time)
        if math.isfinite(normalized_entry_time):
            pass
        else:
            raise ValueError("FMI 1 event entry time must be finite")
        if event_update.terminate_simulation:
            # Termination is terminal in the owning simulation. Release the
            # native instance immediately so no later solver probe can use it.
            runtime_host.close()
            self.runtime_host = None
            raise RuntimeError(
                "FMI 1 Model Exchange requested simulation termination"
            )
        else:
            pass
        if event_update.state_value_references_changed:
            evaluation_budget.consume()
            refreshed_references: tuple[int, ...] = (
                runtime_host.get_state_value_references()
            )
            if len(refreshed_references) == len(self.spec.state_variable_names):
                self._fmi_one_state_value_references = refreshed_references
            else:
                raise RuntimeError(
                    "FMI 1 refreshed state references do not match the "
                    "declared continuous-state count"
                )
        else:
            pass
        if event_update.state_values_changed:
            evaluation_budget.consume()
            refreshed_state_values: np.ndarray = np.array(
                runtime_host.get_continuous_states(),
                dtype=float,
            )
            states_are_valid: bool = (
                refreshed_state_values.size == len(self.spec.state_variable_names)
                and bool(np.all(np.isfinite(refreshed_state_values)))
            )
            if states_are_valid:
                self.state_vector = refreshed_state_values
            else:
                raise RuntimeError(
                    "FMI 1 refreshed continuous states are not finite or do "
                    "not match the declared state count"
                )
        else:
            pass
        if event_update.next_event_time is not None:
            normalized_next_event_time: float = float(event_update.next_event_time)
            if (
                math.isfinite(normalized_next_event_time)
                and normalized_next_event_time > normalized_entry_time
            ):
                self.fmi_two_next_event_time = normalized_next_event_time
            else:
                raise RuntimeError(
                    "FMI 1 nextEventTime must be finite and follow event entry"
                )
        else:
            self.fmi_two_next_event_time = None
        return event_update.iteration_converged

    def _settle_fmi_one_event(
        self,
        event_update: FmiOneEventUpdate,
        entry_time: float,
        evaluation_budget: FmuMeEvaluationBudget,
    ) -> None:
        """Converge one FMI 1 initialization or event-update sequence.

        :param event_update: First FMI 1 event-info result in the sequence.
        :param entry_time: Exact time at which the sequence started.
        :param evaluation_budget: Shared initialization or step call budget.
        :return: None.
        :raises RuntimeError: If the event fixpoint exceeds its bound.
        """

        active_update: FmiOneEventUpdate = event_update
        converged: bool = False
        event_iteration: int
        for event_iteration in range(self.spec.maximum_event_iterations):
            converged = self._apply_fmi_one_event_update(
                event_update=active_update,
                entry_time=entry_time,
                evaluation_budget=evaluation_budget,
            )
            if converged:
                break
            else:
                if self.runtime_host is not None:
                    evaluation_budget.consume()
                    active_update = self.runtime_host.event_update_fmi_one()
                else:
                    raise RuntimeError(
                        "FMI 1 event iteration lost its initialized host"
                    )
        if converged:
            pass
        else:
            raise RuntimeError(
                "FMI 1 Model Exchange event update exceeded its iteration bound"
            )

    def initialize(
        self,
        start_time: float,
        input_values: dict[str, float] | None = None,
        start_values: dict[str, float] | None = None,
        evaluation_budget: FmuMeEvaluationBudget | None = None,
    ) -> None:
        """Open and initialize the FMU ME runtime.

        :param start_time: Initial simulation time.
        :param input_values: FMU input values applied during initialization.
        :param start_values: Additional FMU start values.
        :param evaluation_budget: Optional owner-provided initialization budget.
        :return: None.
        """

        if evaluation_budget is None:
            active_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(100000)
        else:
            active_budget = evaluation_budget

        start_values_payload: dict[str, float] = dict()
        parameter_names: set[str] = set()
        parameter_value: FmuFloat64ParameterValue
        for parameter_value in self.spec.parameter_values:
            start_values_payload[parameter_value.variable_name] = (
                parameter_value.value
            )
            parameter_names.add(parameter_value.variable_name)
        if start_values is not None:
            start_value_name: str
            start_value: float
            for start_value_name, start_value in start_values.items():
                if start_value_name in parameter_names:
                    raise ValueError(
                        "FMU ME start value cannot override a Block parameter"
                    )
                else:
                    start_values_payload[start_value_name] = start_value
        else:
            pass
        if input_values is not None:
            input_value_name: str
            input_value: float
            for input_value_name, input_value in input_values.items():
                if input_value_name in parameter_names:
                    raise ValueError(
                        "FMU ME input value cannot override a Block parameter"
                    )
                else:
                    start_values_payload[input_value_name] = input_value
        else:
            pass

        if self.initialized:
            raise RuntimeError("FMU ME adapter is already initialized")
        else:
            pass
        if self.spec.float64_profile is None:
            has_fmi_three_configuration: bool = (
                len(self.spec.configuration_float64_values) > 0
                or len(self.spec.configuration_uint64_values) > 0
            )
            if has_fmi_three_configuration:
                raise RuntimeError(
                    "FMI 3 Configuration Mode declarations require FMI 3"
                )
            else:
                pass
            _reject_indexed_fmu_ref_bindings(
                input_bindings=self.spec.input_bindings,
                output_bindings=self.spec.output_bindings,
            )
            # FMI 1/2 keep the established in-process runtime until their own
            # isolation increment is explicitly designed.
            self.runtime_host = open_fmu_runtime_host(self.spec.config)
            active_budget.consume()
            initial_event_update: FmiOneEventUpdate | None = (
                self.runtime_host.initialize(
                    start_time=start_time,
                    start_values=start_values_payload,
                )
            )
            if self.runtime_host.metadata.fmi_version_family == FmiVersion.FMI_1_0:
                if initial_event_update is not None:
                    active_budget.consume()
                    initial_state_references: tuple[int, ...] = (
                        self.runtime_host.get_state_value_references()
                    )
                    if len(initial_state_references) == len(
                        self.spec.state_variable_names
                    ):
                        self._fmi_one_state_value_references = (
                            initial_state_references
                        )
                    else:
                        raise RuntimeError(
                            "FMI 1 initial state references do not match the "
                            "declared continuous-state count"
                        )
                    self._settle_fmi_one_event(
                        event_update=initial_event_update,
                        entry_time=start_time,
                        evaluation_budget=active_budget,
                    )
                else:
                    raise RuntimeError(
                        "FMI 1 Model Exchange initialization lost event information"
                    )
            else:
                self._settle_fmi_two_event_mode(
                    entry_time=start_time,
                    evaluation_budget=active_budget,
                )
            active_budget.consume()
            self.state_vector = np.array(
                self.runtime_host.get_continuous_states(),
                dtype=float,
            )
            initial_input_values: dict[str, float] = dict()
            initial_input_name: str
            for initial_input_name in self.spec.input_variable_names:
                initial_input_value: float | None = start_values_payload.get(
                    initial_input_name,
                    None,
                )
                if initial_input_value is not None:
                    initial_input_values[initial_input_name] = initial_input_value
                else:
                    pass
            self.fmi_two_accepted_input_values = (
                self._build_ordered_writable_values(initial_input_values)
            )
            initial_derivatives: np.ndarray
            initial_readable_values: tuple[float, ...] | None
            initial_derivatives, initial_readable_values = (
                self._evaluate_derivatives_for_state(
                    time_value=start_time,
                    state_values=self.state_vector,
                    input_values=initial_input_values,
                    evaluation_budget=active_budget,
                )
            )
            if initial_readable_values is not None:
                pass
            else:
                raise RuntimeError("FMI 2 initialization lost readable values")
            active_budget.consume()
            initial_event_indicators: tuple[float, ...] = tuple(
                self.runtime_host.get_event_indicators()
            )
            self.fmi_two_accepted_derivative_values = tuple(
                initial_derivatives.tolist()
            )
            self.fmi_two_accepted_readable_values = initial_readable_values
            self.fmi_two_accepted_event_indicators = initial_event_indicators
        else:
            # A device scalar cannot provide an incomplete native input array.
            # Output arrays are safe because the session reads their complete
            # vectors before selecting device-bound row-major elements.
            _reject_indexed_fmu_ref_bindings(
                input_bindings=self.spec.input_bindings,
                output_bindings=tuple(),
            )
            if self.spec.worker_limits is not None:
                worker_limits: FmiThreeWorkerHostLimits = self.spec.worker_limits
            else:
                raise RuntimeError("FMI 3 ME device spec lost its worker limits")

            readable_variable_names: tuple[str, ...]
            readable_value_selectors: tuple[
                FmiThreeFloat64SessionValueSelector, ...
            ]
            if len(self.spec.output_bindings) > 0:
                (
                    readable_variable_names,
                    readable_value_selectors,
                ) = resolve_fmi_three_float64_session_value_selectors(
                    self.spec.output_bindings
                )
            else:
                # Preserve the established direct adapter API when no device
                # bindings exist; this path remains scalar-name based.
                readable_variable_names = self.spec.output_variable_names
                readable_value_selectors = tuple()

            configuration_session_values: (
                FmiThreeConfigurationSessionValues
            ) = _build_fmi_three_configuration_session_values(
                configuration_float64_values=(
                    self.spec.configuration_float64_values
                ),
                configuration_uint64_values=(
                    self.spec.configuration_uint64_values
                ),
            )
            initialization_variable_names: list[str] = [""] * (
                len(self.spec.parameter_values)
                + len(self.spec.input_variable_names)
            )
            initial_values: list[float] = [0.0] * len(
                initialization_variable_names
            )
            parameter_index: int
            for parameter_index in range(len(self.spec.parameter_values)):
                parameter_value = self.spec.parameter_values[parameter_index]
                initialization_variable_names[parameter_index] = (
                    parameter_value.variable_name
                )
                initial_values[parameter_index] = parameter_value.value
            initial_input_values = dict()
            initial_input_name: str
            for initial_input_name, initial_input_value in start_values_payload.items():
                if initial_input_name in parameter_names:
                    pass
                else:
                    initial_input_values[initial_input_name] = initial_input_value
            ordered_input_values: tuple[float, ...] = (
                self._build_ordered_writable_values(initial_input_values)
            )
            input_index: int
            for input_index in range(len(self.spec.input_variable_names)):
                initialization_index: int = (
                    len(self.spec.parameter_values) + input_index
                )
                initialization_variable_names[initialization_index] = (
                    self.spec.input_variable_names[input_index]
                )
                initial_values[initialization_index] = ordered_input_values[
                    input_index
                ]
            initial_writable_values: tuple[float, ...] = tuple(initial_values)
            session: FmiThreeNumericSession = open_fmi_three_numeric_session(
                config=self.spec.config,
                instance_name="veragrid-fmi-three-me-device",
                readable_variable_names=readable_variable_names,
                writable_variable_names=self.spec.input_variable_names,
                initialization_variable_names=tuple(
                    initialization_variable_names
                ),
                limits=worker_limits,
                float64_profile=self.spec.float64_profile,
                configuration_variable_names=(
                    configuration_session_values.float64_variable_names
                ),
                configuration_uint64_variable_names=(
                    configuration_session_values.uint64_variable_names
                ),
                readable_value_selectors=readable_value_selectors,
            )
            try:
                # Dimension controllers settle before row-major Float64
                # declarations and output selectors are validated.
                session.configure_uint64(
                    configuration_uint64_values=(
                        configuration_session_values.uint64_values
                    )
                )
                session.configure(
                    configuration_float64_values=(
                        configuration_session_values.float64_values
                    )
                )
                coordinator: FmiThreeModelExchangeCoordinator = (
                    FmiThreeModelExchangeCoordinator(
                        session=session,
                        maximum_event_iterations=(
                            self.spec.maximum_event_iterations
                        ),
                    )
                )
                state_values: tuple[float, ...]
                readable_values: tuple[float, ...]
                state_values, readable_values = coordinator.initialize(
                    start_time=start_time,
                    stop_time=None,
                    relative_tolerance=self.spec.config.relative_tolerance,
                    initial_writable_values=initial_writable_values,
                    evaluation_budget=active_budget,
                )
            except Exception:
                session.close()
                raise
            self.fmi_three_coordinator = coordinator
            self.state_vector = np.array(state_values, dtype=float)
        self.initialized = True

    def get_state_vector(self) -> np.ndarray:
        """Return a copy of the current continuous-state vector.

        :return: Copy of the current state vector.
        """

        if self.state_vector is None:
            return np.zeros(0, dtype=float)
        else:
            return np.array(self.state_vector, dtype=float)

    def set_state_vector(self, values: np.ndarray) -> None:
        """Replace the adapter continuous-state vector and propagate it to the FMU.

        FMI 2 propagates the vector immediately. The isolated FMI 3 session
        receives it with time and inputs at the next evaluation point.

        :param values: New continuous-state vector.
        :return: None.
        """

        if self.runtime_host is not None:
            state_values: np.ndarray = np.array(values, dtype=float)
            self.runtime_host.set_continuous_states(state_values.tolist())
            self.state_vector = state_values
        else:
            if self.fmi_three_coordinator is not None:
                # The isolated session receives the complete accepted state at
                # the next evaluation point, together with time and inputs.
                self.state_vector = np.array(values, dtype=float)
            else:
                raise RuntimeError(
                    "FMU ME adapter must be initialized before setting states"
                )

    def _apply_inputs(self, input_values: dict[str, float]) -> None:
        """Apply one input vector to the FMU runtime.

        :param input_values: FMU input values.
        :return: None.
        """

        if self.runtime_host is None:
            raise RuntimeError("FMU ME adapter must be initialized before applying inputs")
        else:
            if len(input_values) > 0:
                self.runtime_host.set_real(input_values)
            else:
                pass

    def evaluate_derivatives(self, time_value: float, input_values: dict[str, float]) -> np.ndarray:
        """Evaluate the FMU derivative vector at the provided time and inputs.

        :param time_value: Current evaluation time.
        :param input_values: FMU input values.
        :return: Derivative vector.
        """

        if self.runtime_host is not None:
            self.runtime_host.set_time(time_value)
            self._apply_inputs(input_values)
            if self.state_vector is not None:
                self.runtime_host.set_continuous_states(self.state_vector.tolist())
            else:
                pass
            derivative_values: list[float] = self.runtime_host.get_derivatives()
            return np.array(derivative_values, dtype=float)
        else:
            if self.fmi_three_coordinator is not None:
                state_values: tuple[float, ...] = (
                    self._get_fmi_three_state_values()
                )
                derivative_values_tuple: tuple[float, ...]
                readable_values: tuple[float, ...]
                derivative_values_tuple, readable_values = (
                    self.fmi_three_coordinator.evaluate_probe(
                        time_value=time_value,
                        continuous_state_values=state_values,
                        writable_values=(
                            self._build_ordered_writable_values(input_values)
                        ),
                    )
                )
                return np.array(derivative_values_tuple, dtype=float)
            else:
                raise RuntimeError(
                    "FMU ME adapter must be initialized before derivative evaluation"
                )

    def evaluate_outputs(
        self,
        time_value: float,
        input_values: dict[str, float],
        evaluation_budget: FmuMeEvaluationBudget | None = None,
    ) -> dict[str, float]:
        """Evaluate the FMU output vector at the provided time and inputs.

        :param time_value: Current evaluation time.
        :param input_values: FMU input values.
        :param evaluation_budget: Optional owner-provided runtime-call budget.
        :return: Output values indexed by FMU variable name.
        """

        ordered_values: tuple[float, ...] = self._evaluate_ordered_output_values(
            time_value=time_value,
            input_values=input_values,
            evaluation_budget=evaluation_budget,
        )
        return self._map_named_output_values(ordered_values)

    def _evaluate_bound_outputs(
        self,
        time_value: float,
        input_values: dict[str, float],
        evaluation_budget: FmuMeEvaluationBudget | None = None,
    ) -> dict[VarPowerFlowReferenceType, float]:
        """Evaluate outputs aligned with the owning device bindings.

        Unlike the compatibility API keyed by FMU name, this path can retain
        multiple selected elements from the same FMU array.

        :param time_value: Current evaluation time.
        :param input_values: Complete scalar FMU input values.
        :param evaluation_budget: Optional owner-provided runtime-call budget.
        :return: Output values indexed by VeraGrid reference.
        """

        ordered_values: tuple[float, ...] = self._evaluate_ordered_output_values(
            time_value=time_value,
            input_values=input_values,
            evaluation_budget=evaluation_budget,
        )
        return self.map_bound_output_values(ordered_values)

    def _validate_finite_vector(
        self,
        values: np.ndarray,
        expected_size: int,
        vector_name: str,
    ) -> None:
        """Require one finite one-dimensional vector with exact cardinality.

        :param values: Candidate numeric vector.
        :param expected_size: Exact required element count.
        :param vector_name: Stable diagnostic name.
        :return: None.
        :raises RuntimeError: If shape, size, or finiteness is invalid.
        """

        if (
            values.ndim == 1
            and values.size == expected_size
            and bool(np.all(np.isfinite(values)))
        ):
            pass
        else:
            raise RuntimeError(
                f"FMI ME {vector_name} must contain exactly {expected_size} "
                "finite values"
            )

    def _evaluate_derivatives_for_state(
        self,
        time_value: float,
        state_values: np.ndarray,
        input_values: dict[str, float],
        evaluation_budget: FmuMeEvaluationBudget,
    ) -> tuple[np.ndarray, tuple[float, ...] | None]:
        """Evaluate derivatives at one solver-provided continuous point.

        One budget unit represents this complete product boundary invocation,
        including the coalesced FMI calls needed to present the point.

        :param time_value: Finite evaluation time.
        :param state_values: Complete solver-provided state vector.
        :param input_values: Frozen scalar FMU input values.
        :param evaluation_budget: Shared owner-provided call budget.
        :return: Derivatives and FMI 3 coalesced readable values when available.
        """

        normalized_time: float = float(time_value)
        expected_size: int = state_values.size
        if math.isfinite(normalized_time):
            pass
        else:
            raise RuntimeError("FMI ME derivative evaluation time must be finite")
        self._validate_finite_vector(
            values=state_values,
            expected_size=expected_size,
            vector_name="state vector",
        )

        evaluation_budget.consume()
        if self.runtime_host is not None:
            self.runtime_host.set_time(normalized_time)
            self._apply_inputs(input_values)
            self.runtime_host.set_continuous_states(state_values.tolist())
            derivative_values: np.ndarray = np.array(
                self.runtime_host.get_derivatives(),
                dtype=float,
            )
            # FMI 2 does not provide the FMI 3 worker's coalesced transaction,
            # so capture the bound outputs immediately after the derivatives.
            # This makes both vectors describe the same solver-presented point.
            named_readable_values: dict[str, float] = self.runtime_host.get_real(
                list(self.spec.output_variable_names)
            )
            ordered_readable_values: list[float] = [0.0] * len(
                self.spec.output_variable_names
            )
            output_index: int
            for output_index in range(len(self.spec.output_variable_names)):
                output_name: str = self.spec.output_variable_names[output_index]
                ordered_readable_values[output_index] = float(
                    named_readable_values[output_name]
                )
            readable_values: tuple[float, ...] | None = tuple(
                ordered_readable_values
            )
        else:
            if self.fmi_three_coordinator is not None:
                derivative_tuple: tuple[float, ...]
                fmi_three_readable_values: tuple[float, ...]
                derivative_tuple, fmi_three_readable_values = (
                    self.fmi_three_coordinator.evaluate_probe(
                        time_value=normalized_time,
                        continuous_state_values=tuple(state_values.tolist()),
                        writable_values=(
                            self._build_ordered_writable_values(input_values)
                        ),
                    )
                )
                derivative_values = np.array(derivative_tuple, dtype=float)
                readable_values = fmi_three_readable_values
            else:
                raise RuntimeError(
                    "FMU ME adapter must be initialized before derivative evaluation"
                )
        self._validate_finite_vector(
            values=derivative_values,
            expected_size=expected_size,
            vector_name="derivative vector",
        )
        if readable_values is not None:
            readable_array: np.ndarray = np.array(readable_values, dtype=float)
            self._validate_finite_vector(
                values=readable_array,
                expected_size=len(self.spec.output_variable_names),
                vector_name="readable output vector",
            )
        else:
            pass
        return derivative_values, readable_values

    def _evaluate_backward_euler_residual(
        self,
        target_time: float,
        step_size: float,
        accepted_state_values: np.ndarray,
        candidate_state_values: np.ndarray,
        input_values: dict[str, float],
        evaluation_budget: FmuMeEvaluationBudget,
    ) -> tuple[np.ndarray, np.ndarray, tuple[float, ...] | None]:
        """Evaluate the unscaled Backward Euler residual at one candidate.

        :param target_time: End time of the shortened or full solver step.
        :param step_size: Positive step length measured from acceptance.
        :param accepted_state_values: Accepted state x_n.
        :param candidate_state_values: Newton candidate y.
        :param input_values: Inputs frozen at u_n.
        :param evaluation_budget: Shared runtime-call budget.
        :return: Residual, derivatives, and coalesced FMI 3 readable values.
        """

        derivative_values: np.ndarray
        readable_values: tuple[float, ...] | None
        derivative_values, readable_values = self._evaluate_derivatives_for_state(
            time_value=target_time,
            state_values=candidate_state_values,
            input_values=input_values,
            evaluation_budget=evaluation_budget,
        )
        residual_values: np.ndarray = (
            candidate_state_values
            - accepted_state_values
            - step_size * derivative_values
        )
        self._validate_finite_vector(
            values=residual_values,
            expected_size=accepted_state_values.size,
            vector_name="Backward Euler residual",
        )
        return residual_values, derivative_values, readable_values

    def _evaluate_forward_difference_jacobian(
        self,
        target_time: float,
        step_size: float,
        accepted_state_values: np.ndarray,
        candidate_state_values: np.ndarray,
        base_residual_values: np.ndarray,
        input_values: dict[str, float],
        evaluation_budget: FmuMeEvaluationBudget,
    ) -> np.ndarray:
        """Build the unscaled forward-difference residual Jacobian.

        :param target_time: End time of the current Backward Euler solve.
        :param step_size: Positive integration step.
        :param accepted_state_values: Accepted state x_n.
        :param candidate_state_values: Current Newton iterate y.
        :param base_residual_values: Already evaluated unscaled R(y).
        :param input_values: Inputs frozen at u_n.
        :param evaluation_budget: Shared runtime-call budget.
        :return: Dense square residual Jacobian.
        """

        state_count: int = candidate_state_values.size
        jacobian: np.ndarray = np.empty(
            (state_count, state_count),
            dtype=float,
        )
        square_root_epsilon: float = math.sqrt(np.finfo(np.float64).eps)
        state_index: int
        for state_index in range(state_count):
            perturbation: float = square_root_epsilon * max(
                1.0,
                abs(float(candidate_state_values[state_index])),
            )
            perturbed_state_values: np.ndarray = np.array(
                candidate_state_values,
                copy=True,
            )
            perturbed_state_values[state_index] += perturbation
            perturbed_residual_values: np.ndarray
            ignored_derivatives: np.ndarray
            ignored_readable_values: tuple[float, ...] | None
            (
                perturbed_residual_values,
                ignored_derivatives,
                ignored_readable_values,
            ) = self._evaluate_backward_euler_residual(
                target_time=target_time,
                step_size=step_size,
                accepted_state_values=accepted_state_values,
                candidate_state_values=perturbed_state_values,
                input_values=input_values,
                evaluation_budget=evaluation_budget,
            )
            jacobian[:, state_index] = (
                perturbed_residual_values - base_residual_values
            ) / perturbation
        self._validate_finite_vector(
            values=jacobian.reshape(state_count * state_count),
            expected_size=state_count * state_count,
            vector_name="Backward Euler Jacobian",
        )
        return jacobian

    def _solve_backward_euler_candidate(
        self,
        current_time: float,
        step_size: float,
        accepted_state_values: np.ndarray,
        input_values: dict[str, float],
        evaluation_budget: FmuMeEvaluationBudget,
    ) -> tuple[np.ndarray, np.ndarray, tuple[float, ...] | None]:
        """Solve one bounded Backward Euler candidate without accepting it.

        :param current_time: Finite accepted time t_n.
        :param step_size: Finite positive interval length h.
        :param accepted_state_values: Accepted continuous state x_n.
        :param input_values: Inputs frozen at the accepted network point.
        :param evaluation_budget: Shared runtime-call budget.
        :return: Converged candidate, endpoint derivatives, and FMI 3 outputs.
        :raises RuntimeError: If dimensions, data, linear solve, or convergence fail.
        """

        normalized_time: float = float(current_time)
        normalized_step: float = float(step_size)
        state_count: int = accepted_state_values.size
        if math.isfinite(normalized_time):
            pass
        else:
            raise RuntimeError("FMI ME accepted time must be finite")
        if math.isfinite(normalized_step) and normalized_step > 0.0:
            pass
        else:
            raise RuntimeError("FMI ME Backward Euler step must be finite and positive")
        self._validate_finite_vector(
            values=accepted_state_values,
            expected_size=state_count,
            vector_name="accepted state vector",
        )
        if state_count <= self.solver_policy.maximum_continuous_states:
            pass
        else:
            raise RuntimeError(
                "FMI ME continuous-state count exceeds the configured dense "
                "Backward Euler limit"
            )

        target_time: float = normalized_time + normalized_step
        if math.isfinite(target_time):
            pass
        else:
            raise RuntimeError("FMI ME Backward Euler target time must be finite")
        if state_count == 0:
            endpoint_derivatives: np.ndarray
            endpoint_readable_values: tuple[float, ...] | None
            endpoint_derivatives, endpoint_readable_values = (
                self._evaluate_derivatives_for_state(
                    time_value=target_time,
                    state_values=np.zeros(0, dtype=float),
                    input_values=input_values,
                    evaluation_budget=evaluation_budget,
                )
            )
            return (
                np.zeros(0, dtype=float),
                endpoint_derivatives,
                endpoint_readable_values,
            )
        else:
            pass

        start_derivatives: np.ndarray
        ignored_start_readable_values: tuple[float, ...] | None
        start_derivatives, ignored_start_readable_values = (
            self._evaluate_derivatives_for_state(
                time_value=normalized_time,
                state_values=accepted_state_values,
                input_values=input_values,
                evaluation_budget=evaluation_budget,
            )
        )
        candidate_state_values: np.ndarray = (
            accepted_state_values + normalized_step * start_derivatives
        )
        self._validate_finite_vector(
            values=candidate_state_values,
            expected_size=state_count,
            vector_name="Backward Euler predictor",
        )

        residual_values: np.ndarray
        endpoint_derivatives = np.zeros(state_count, dtype=float)
        endpoint_readable_values = None
        (
            residual_values,
            endpoint_derivatives,
            endpoint_readable_values,
        ) = self._evaluate_backward_euler_residual(
            target_time=target_time,
            step_size=normalized_step,
            accepted_state_values=accepted_state_values,
            candidate_state_values=candidate_state_values,
            input_values=input_values,
            evaluation_budget=evaluation_budget,
        )
        residual_scale: np.ndarray = (
            self.solver_policy.absolute_tolerance
            + self.solver_policy.relative_tolerance
            * np.maximum(
                np.abs(accepted_state_values),
                np.abs(candidate_state_values),
            )
        )
        scaled_residual_norm: float = float(
            np.max(np.abs(residual_values) / residual_scale)
        )
        converged: bool = scaled_residual_norm <= 1.0
        iteration_index: int = 0
        while (
            not converged
            and iteration_index < self.solver_policy.maximum_newton_iterations
        ):
            jacobian: np.ndarray = self._evaluate_forward_difference_jacobian(
                target_time=target_time,
                step_size=normalized_step,
                accepted_state_values=accepted_state_values,
                candidate_state_values=candidate_state_values,
                base_residual_values=residual_values,
                input_values=input_values,
                evaluation_budget=evaluation_budget,
            )
            try:
                correction_values: np.ndarray = np.linalg.solve(
                    jacobian,
                    -residual_values,
                )
            except np.linalg.LinAlgError as linear_error:
                raise RuntimeError(
                    "FMI ME Backward Euler residual Jacobian is singular"
                ) from linear_error
            self._validate_finite_vector(
                values=correction_values,
                expected_size=state_count,
                vector_name="Backward Euler correction",
            )
            candidate_state_values = candidate_state_values + correction_values
            self._validate_finite_vector(
                values=candidate_state_values,
                expected_size=state_count,
                vector_name="Backward Euler Newton iterate",
            )
            (
                residual_values,
                endpoint_derivatives,
                endpoint_readable_values,
            ) = self._evaluate_backward_euler_residual(
                target_time=target_time,
                step_size=normalized_step,
                accepted_state_values=accepted_state_values,
                candidate_state_values=candidate_state_values,
                input_values=input_values,
                evaluation_budget=evaluation_budget,
            )
            residual_scale = (
                self.solver_policy.absolute_tolerance
                + self.solver_policy.relative_tolerance
                * np.maximum(
                    np.abs(accepted_state_values),
                    np.abs(candidate_state_values),
                )
            )
            scaled_residual_norm = float(
                np.max(np.abs(residual_values) / residual_scale)
            )
            converged = scaled_residual_norm <= 1.0
            iteration_index += 1
        if converged:
            return (
                candidate_state_values,
                endpoint_derivatives,
                endpoint_readable_values,
            )
        else:
            raise RuntimeError(
                "FMI ME Backward Euler Newton iteration limit was exhausted"
            )

    def _restore_fmi_two_pending_point(
        self,
        evaluation_budget: FmuMeEvaluationBudget,
    ) -> tuple[float, ...]:
        """Restore one FMI 2 ME point after a coupled substep is rejected.

        :param evaluation_budget: Shared owner-provided runtime-call budget.
        :return: Readable values recomputed at the restored accepted point.
        :raises RuntimeError: If the minimal pending snapshot is incomplete.
        """

        accepted_time: float | None = self.pending_accepted_time
        accepted_states: tuple[float, ...] | None = (
            self.pending_accepted_state_values
        )
        accepted_inputs: tuple[float, ...] | None = (
            self.pending_accepted_input_values
        )
        accepted_derivatives: tuple[float, ...] | None = (
            self.pending_accepted_derivative_values
        )
        accepted_readable_values: tuple[float, ...] | None = (
            self.pending_accepted_readable_values
        )
        accepted_event_indicators: tuple[float, ...] | None = (
            self.pending_accepted_event_indicators
        )
        if (
            self.runtime_host is not None
            and accepted_time is not None
            and accepted_states is not None
            and accepted_inputs is not None
            and accepted_derivatives is not None
            and accepted_readable_values is not None
            and accepted_event_indicators is not None
            and len(accepted_inputs) == len(self.spec.input_variable_names)
        ):
            pass
        else:
            raise RuntimeError(
                "FMI 2 ME rollback requires a complete accepted point"
            )

        restored_inputs: dict[str, float] = dict()
        input_index: int
        for input_index in range(len(self.spec.input_variable_names)):
            restored_inputs[self.spec.input_variable_names[input_index]] = (
                accepted_inputs[input_index]
            )
        restored_state_values: np.ndarray = np.array(accepted_states, dtype=float)
        restored_derivatives: np.ndarray
        restored_readable_values: tuple[float, ...] | None
        restored_derivatives, restored_readable_values = (
            self._evaluate_derivatives_for_state(
                time_value=accepted_time,
                state_values=restored_state_values,
                input_values=restored_inputs,
                evaluation_budget=evaluation_budget,
            )
        )
        evaluation_budget.consume()
        restored_event_indicators: tuple[float, ...] = tuple(
            self.runtime_host.get_event_indicators()
        )
        # Re-solving algebraic outputs may change the last few binary digits
        # even when the visible FMI point is identical.  Validate the rebuilt
        # vectors against the same explicit ME policy that bounded their solve.
        rollback_relative_tolerance: float = (
            self.solver_policy.relative_tolerance
        )
        rollback_absolute_tolerance: float = self.solver_policy.absolute_tolerance
        derivatives_match: bool = (
            restored_derivatives.size == len(accepted_derivatives)
            and bool(np.all(np.isfinite(restored_derivatives)))
            and bool(np.allclose(
                restored_derivatives,
                np.asarray(accepted_derivatives, dtype=float),
                rtol=rollback_relative_tolerance,
                atol=rollback_absolute_tolerance,
            ))
        )
        readable_values_match: bool = (
            restored_readable_values is not None
            and len(restored_readable_values) == len(accepted_readable_values)
            and bool(np.all(np.isfinite(restored_readable_values)))
            and bool(np.allclose(
                np.asarray(restored_readable_values, dtype=float),
                np.asarray(accepted_readable_values, dtype=float),
                rtol=rollback_relative_tolerance,
                atol=rollback_absolute_tolerance,
            ))
        )
        event_indicators_match: bool = (
            len(restored_event_indicators) == len(accepted_event_indicators)
            and bool(np.all(np.isfinite(restored_event_indicators)))
            and bool(np.allclose(
                np.asarray(restored_event_indicators, dtype=float),
                np.asarray(accepted_event_indicators, dtype=float),
                rtol=rollback_relative_tolerance,
                atol=rollback_absolute_tolerance,
            ))
        )
        if derivatives_match and readable_values_match and event_indicators_match:
            self.state_vector = restored_state_values
        else:
            raise RuntimeError(
                "FMI 2 visible rollback did not reproduce the accepted point "
                f"(derivatives={derivatives_match}, "
                f"readable_values={readable_values_match}, "
                f"event_indicators={event_indicators_match})"
            )
        self._clear_pending_state_event_data()
        return accepted_readable_values

    def resolve_pending_step(
        self,
        accepted: bool,
        importer_detected_event: bool = False,
        evaluation_budget: FmuMeEvaluationBudget | None = None,
    ) -> tuple[float, ...] | None:
        """Accept or reject one prepared Model Exchange candidate.

        :param accepted: Whether the owning numerical solver accepted the step.
        :param importer_detected_event: Whether an event was localized here.
        :param evaluation_budget: Optional owner-provided runtime-call budget.
        :return: Restored FMI 2 or resolved FMI 3 readings when applicable.
        """

        coordinator: FmiThreeModelExchangeCoordinator | None = (
            self.fmi_three_coordinator
        )
        localized_event_is_due: bool = (
            self.localized_state_event_time is not None
            and self.pending_time is not None
            and self.pending_time >= self.localized_state_event_time
        )
        if coordinator is not None and coordinator.has_pending_candidate():
            resolved_states: tuple[float, ...]
            resolved_readable_values: tuple[float, ...]
            if accepted:
                next_event_time: float | None = coordinator.get_next_event_time()
                time_event_is_due: bool = (
                    next_event_time is not None
                    and self.pending_time is not None
                    and self.pending_time >= next_event_time
                )
                resolved_states, resolved_readable_values = (
                    coordinator.accept_candidate(
                        importer_detected_event=(
                            importer_detected_event
                            or localized_event_is_due
                            or time_event_is_due
                        ),
                        evaluation_budget=evaluation_budget,
                    )
                )
            else:
                coordinator.reject_candidate(
                    evaluation_budget=evaluation_budget
                )
                accepted_point: tuple[
                    float,
                    tuple[float, ...],
                    tuple[float, ...],
                    tuple[float, ...],
                    tuple[float, ...],
                    tuple[float, ...],
                    tuple[float, ...],
                ] = coordinator.get_accepted_point()
                resolved_states = accepted_point[1]
                resolved_readable_values = accepted_point[3]
            self.state_vector = np.array(resolved_states, dtype=float)
            if accepted:
                self.localized_state_event_time = None
            else:
                pass
            self._clear_pending_state_event_data()
            return resolved_readable_values
        else:
            if (
                self.runtime_host is not None
                and self.pending_accepted_time is not None
            ):
                if accepted:
                    if evaluation_budget is not None:
                        active_budget: FmuMeEvaluationBudget = evaluation_budget
                    else:
                        active_budget = FmuMeEvaluationBudget(100000)
                    runtime_host: FmuRuntimeHost = self.runtime_host
                    candidate_input_values: tuple[float, ...] | None = (
                        self.pending_candidate_input_values
                    )
                    if candidate_input_values is not None:
                        pass
                    else:
                        raise RuntimeError(
                            "FMI 2 acceptance lost its candidate input vector"
                        )
                    completed_step_requested_event: bool = False
                    if runtime_host.needs_completed_integrator_step():
                        active_budget.consume()
                        enter_event_mode: bool
                        terminate_simulation: bool
                        (
                            enter_event_mode,
                            terminate_simulation,
                        ) = runtime_host.completed_integrator_step()
                        if terminate_simulation:
                            raise RuntimeError(
                                "FMI 2 Model Exchange requested simulation termination"
                            )
                        else:
                            completed_step_requested_event = enter_event_mode
                    else:
                        pass
                    runtime_is_fmi_one: bool = (
                        runtime_host.metadata.fmi_version_family
                        == FmiVersion.FMI_1_0
                    )
                    time_event_is_due: bool = (
                        self.fmi_two_next_event_time is not None
                        and self.pending_time is not None
                        and self.pending_time >= self.fmi_two_next_event_time
                    )
                    event_is_required: bool = (
                        importer_detected_event
                        or localized_event_is_due
                        or completed_step_requested_event
                        or time_event_is_due
                    )
                    resolved_readable_values: tuple[float, ...] | None = (
                        self.pending_candidate_readable_values
                    )
                    if event_is_required:
                        if self.pending_time is not None:
                            accepted_event_time: float = self.pending_time
                        else:
                            raise RuntimeError(
                                "FMI 2 event acceptance lost its candidate time"
                            )
                        if runtime_is_fmi_one:
                            active_budget.consume()
                            first_event_update: FmiOneEventUpdate = (
                                runtime_host.event_update_fmi_one()
                            )
                            self._settle_fmi_one_event(
                                event_update=first_event_update,
                                entry_time=accepted_event_time,
                                evaluation_budget=active_budget,
                            )
                        else:
                            active_budget.consume()
                            runtime_host.enter_event_mode()
                            self._settle_fmi_two_event_mode(
                                entry_time=accepted_event_time,
                                evaluation_budget=active_budget,
                            )
                        active_budget.consume()
                        post_event_states: np.ndarray = np.array(
                            runtime_host.get_continuous_states(),
                            dtype=float,
                        )
                        candidate_inputs: dict[str, float] = dict()
                        input_index: int
                        for input_index in range(len(self.spec.input_variable_names)):
                            candidate_inputs[self.spec.input_variable_names[input_index]] = (
                                candidate_input_values[input_index]
                            )
                        post_event_derivatives: np.ndarray
                        post_event_readable_values: tuple[float, ...] | None
                        (
                            post_event_derivatives,
                            post_event_readable_values,
                        ) = self._evaluate_derivatives_for_state(
                            time_value=accepted_event_time,
                            state_values=post_event_states,
                            input_values=candidate_inputs,
                            evaluation_budget=active_budget,
                        )
                        active_budget.consume()
                        post_event_indicators: tuple[float, ...] = tuple(
                            runtime_host.get_event_indicators()
                        )
                        self.state_vector = post_event_states
                        self.fmi_two_accepted_derivative_values = tuple(
                            post_event_derivatives.tolist()
                        )
                        self.fmi_two_accepted_readable_values = (
                            post_event_readable_values
                        )
                        self.fmi_two_accepted_event_indicators = (
                            post_event_indicators
                        )
                        resolved_readable_values = post_event_readable_values
                    else:
                        self.fmi_two_accepted_derivative_values = (
                            self.pending_candidate_derivative_values
                        )
                        self.fmi_two_accepted_readable_values = (
                            self.pending_candidate_readable_values
                        )
                        self.fmi_two_accepted_event_indicators = (
                            self.pending_candidate_event_indicators
                        )
                    if resolved_readable_values is not None:
                        pass
                    else:
                        raise RuntimeError(
                            "FMI 2 acceptance lost its candidate readable values"
                        )
                    # Promote inputs only after the complete candidate,
                    # including Event Mode, is successfully accepted.
                    self.fmi_two_accepted_input_values = candidate_input_values
                    self.localized_state_event_time = None
                    self._clear_pending_state_event_data()
                    return resolved_readable_values
                else:
                    if evaluation_budget is not None:
                        return self._restore_fmi_two_pending_point(
                            evaluation_budget=evaluation_budget
                        )
                    else:
                        fallback_budget: FmuMeEvaluationBudget = (
                            FmuMeEvaluationBudget(100000)
                        )
                        return self._restore_fmi_two_pending_point(
                            evaluation_budget=fallback_budget
                        )
            else:
                return None

    def get_pending_state_event_time(
        self,
        time_tolerance: float,
        maximum_iterations: int,
        evaluation_budget: FmuMeEvaluationBudget,
    ) -> float | None:
        """Locate the first method-consistent event inside a pending candidate.

        :param time_tolerance: Positive absolute event-time tolerance in seconds.
        :param maximum_iterations: Positive bisection iteration bound.
        :param evaluation_budget: Shared owner-provided runtime-call budget.
        :return: Earliest localized event time, or ``None`` without a crossing.
        """

        normalized_tolerance: float = float(time_tolerance)
        if math.isfinite(normalized_tolerance) and normalized_tolerance > 0.0:
            pass
        else:
            raise ValueError(
                "FMI ME state-event time tolerance must be finite and positive"
            )
        if (
            isinstance(maximum_iterations, int)
            and not isinstance(maximum_iterations, bool)
            and maximum_iterations > 0
        ):
            pass
        else:
            raise ValueError(
                "FMI ME state-event iteration bound must be a positive integer"
            )

        candidate_time: float | None = self.pending_time
        candidate_states: tuple[float, ...] | None = (
            self.pending_candidate_state_values
        )
        candidate_inputs: tuple[float, ...] | None = (
            self.pending_candidate_input_values
        )
        candidate_derivatives: tuple[float, ...] | None = (
            self.pending_candidate_derivative_values
        )
        candidate_readable_values: tuple[float, ...] | None = (
            self.pending_candidate_readable_values
        )
        candidate_indicators: tuple[float, ...] | None = (
            self.pending_candidate_event_indicators
        )
        accepted_time: float | None = self.pending_accepted_time
        accepted_states: tuple[float, ...] | None = (
            self.pending_accepted_state_values
        )
        accepted_inputs: tuple[float, ...] | None = (
            self.pending_accepted_input_values
        )
        accepted_indicators: tuple[float, ...] | None = (
            self.pending_accepted_event_indicators
        )
        if (
            candidate_time is not None
            and candidate_states is not None
            and candidate_inputs is not None
            and candidate_derivatives is not None
            and candidate_readable_values is not None
            and candidate_indicators is not None
            and accepted_time is not None
            and accepted_states is not None
            and accepted_inputs is not None
            and accepted_indicators is not None
            and (
                (
                    self.fmi_three_coordinator is not None
                    and self.fmi_three_coordinator.has_pending_candidate()
                )
                or self.runtime_host is not None
            )
        ):
            pass
        else:
            return None
        interval_width: float = candidate_time - accepted_time
        if (
            len(accepted_states) == len(candidate_states)
            and len(accepted_indicators) == len(candidate_indicators)
            and len(accepted_inputs) == len(candidate_inputs)
            and len(candidate_inputs) == len(self.spec.input_variable_names)
            and math.isfinite(accepted_time)
            and math.isfinite(candidate_time)
            and math.isfinite(interval_width)
            and interval_width > 0.0
        ):
            pass
        else:
            raise RuntimeError(
                "FMI ME state-event localization requires a finite positive-width "
                "candidate interval"
            )

        time_scale: float = max(abs(accepted_time), abs(candidate_time), 1.0)
        effective_tolerance: float = max(
            normalized_tolerance,
            16.0 * math.ulp(time_scale),
        )
        if math.isfinite(effective_tolerance) and effective_tolerance > 0.0:
            pass
        else:
            raise ValueError(
                "FMI ME effective state-event tolerance must be finite and positive"
            )

        # Determine the exact binary bisection count without forming a width to
        # tolerance ratio that could overflow or underflow.  Insufficient
        # bounds fail before any worker probe changes native state.
        required_iterations: int = 0
        if interval_width > effective_tolerance:
            width_mantissa: float
            width_exponent: int
            tolerance_mantissa: float
            tolerance_exponent: int
            width_mantissa, width_exponent = math.frexp(interval_width)
            tolerance_mantissa, tolerance_exponent = math.frexp(
                effective_tolerance
            )
            required_iterations = width_exponent - tolerance_exponent
            if width_mantissa > tolerance_mantissa:
                required_iterations += 1
            else:
                pass
        else:
            pass
        if required_iterations <= maximum_iterations:
            pass
        else:
            raise RuntimeError(
                "FMI ME state-event localization bound cannot meet its tolerance"
            )

        crossing_indices: tuple[int, ...] = (
            self._get_pending_state_event_crossing_indices(
                accepted_indicators=accepted_indicators,
                candidate_indicators=candidate_indicators,
            )
        )
        crossing_count: int = len(crossing_indices)
        if crossing_count == 0:
            return None
        else:
            pass

        # Each indicator owns its bracket.  A shortened Backward Euler solve
        # establishes every midpoint so localization uses the same method as
        # the accepted integration path.
        earliest_event_time: float | None = None
        crossing_position: int
        for crossing_position in range(crossing_count):
            event_indicator_index: int = crossing_indices[crossing_position]
            accepted_is_positive: bool = (
                accepted_indicators[event_indicator_index] > 0.0
            )
            lower_time: float = accepted_time
            upper_time: float = candidate_time
            iteration_index: int = 0
            while iteration_index < required_iterations:
                bracket_width: float = upper_time - lower_time
                midpoint_time: float = lower_time + bracket_width * 0.5
                if lower_time < midpoint_time < upper_time:
                    raw_fraction: float = (
                        (midpoint_time - accepted_time) / interval_width
                    )
                    interpolation_fraction: float = min(
                        max(raw_fraction, 0.0),
                        1.0,
                    )
                    midpoint_input_values: dict[str, float] = dict()
                    input_index: int
                    for input_index in range(len(self.spec.input_variable_names)):
                        accepted_input_value: float = accepted_inputs[input_index]
                        candidate_input_value: float = candidate_inputs[input_index]
                        midpoint_input_values[
                            self.spec.input_variable_names[input_index]
                        ] = accepted_input_value + interpolation_fraction * (
                            candidate_input_value - accepted_input_value
                        )
                    midpoint_states: np.ndarray
                    ignored_midpoint_derivatives: np.ndarray
                    ignored_midpoint_readable_values: tuple[float, ...] | None
                    (
                        midpoint_states,
                        ignored_midpoint_derivatives,
                        ignored_midpoint_readable_values,
                    ) = self._solve_backward_euler_candidate(
                        current_time=accepted_time,
                        step_size=midpoint_time - accepted_time,
                        accepted_state_values=np.array(
                            accepted_states,
                            dtype=float,
                        ),
                        input_values=midpoint_input_values,
                        evaluation_budget=evaluation_budget,
                    )
                    if self.fmi_three_coordinator is not None:
                        midpoint_indicators: tuple[float, ...] = (
                            self.fmi_three_coordinator.evaluate_event_indicators_probe(
                                time_value=midpoint_time,
                                continuous_state_values=tuple(
                                    midpoint_states.tolist()
                                ),
                                point_is_presented=True,
                                evaluation_budget=evaluation_budget,
                            )
                        )
                    else:
                        if self.runtime_host is not None:
                            evaluation_budget.consume()
                            midpoint_indicators = tuple(
                                self.runtime_host.get_event_indicators()
                            )
                            candidate_input_values: dict[str, float] = dict()
                            for input_index in range(
                                len(self.spec.input_variable_names)
                            ):
                                candidate_input_values[
                                    self.spec.input_variable_names[input_index]
                                ] = candidate_inputs[input_index]
                            restored_derivatives: np.ndarray
                            restored_readable_values: tuple[float, ...] | None
                            (
                                restored_derivatives,
                                restored_readable_values,
                            ) = self._evaluate_derivatives_for_state(
                                time_value=candidate_time,
                                state_values=np.array(
                                    candidate_states,
                                    dtype=float,
                                ),
                                input_values=candidate_input_values,
                                evaluation_budget=evaluation_budget,
                            )
                            evaluation_budget.consume()
                            restored_indicators: tuple[float, ...] = tuple(
                                self.runtime_host.get_event_indicators()
                            )
                            if (
                                tuple(restored_derivatives.tolist())
                                == candidate_derivatives
                                and restored_readable_values
                                == candidate_readable_values
                                and restored_indicators == candidate_indicators
                            ):
                                pass
                            else:
                                raise RuntimeError(
                                    "FMI 2 event localization did not restore "
                                    "the pending endpoint"
                                )
                        else:
                            raise RuntimeError(
                                "FMI ME localization lost its runtime"
                            )
                    if len(midpoint_indicators) == len(accepted_indicators):
                        pass
                    else:
                        raise RuntimeError(
                            "FMI ME event-indicator cardinality changed during localization"
                        )
                    midpoint_is_positive: bool = (
                        midpoint_indicators[event_indicator_index] > 0.0
                    )
                    if midpoint_is_positive != accepted_is_positive:
                        upper_time = midpoint_time
                    else:
                        lower_time = midpoint_time
                else:
                    lower_time = upper_time
                iteration_index += 1
            if (upper_time - lower_time) <= effective_tolerance:
                if (
                    earliest_event_time is None
                    or upper_time < earliest_event_time
                ):
                    earliest_event_time = upper_time
                else:
                    pass
            else:
                raise RuntimeError(
                    "FMI ME state-event localization exceeded its iteration bound"
                )
        return earliest_event_time

    def _get_pending_state_event_crossing_indices(
        self,
        accepted_indicators: tuple[float, ...] | None = None,
        candidate_indicators: tuple[float, ...] | None = None,
    ) -> tuple[int, ...]:
        """Return indicators whose FMI sign domains differ at the endpoints.

        :param accepted_indicators: Optional accepted indicators already read by
            the localization caller.
        :param candidate_indicators: Optional candidate indicators already read
            by the localization caller.
        :return: Ordered indices changing between ``z > 0`` and ``z <= 0``.
        """

        if accepted_indicators is None:
            accepted_indicators = self.pending_accepted_event_indicators
        else:
            pass
        if candidate_indicators is None:
            candidate_indicators = self.pending_candidate_event_indicators
        else:
            pass
        if accepted_indicators is not None and candidate_indicators is not None:
            pass
        else:
            raise RuntimeError(
                "FMI ME state-event detection lost its candidate indicators"
            )
        if len(accepted_indicators) == len(candidate_indicators):
            pass
        else:
            raise RuntimeError(
                "FMI ME event-indicator cardinality changed inside one step"
            )

        crossing_indices: list[int] = [0] * len(accepted_indicators)
        crossing_count: int = 0
        indicator_index: int
        for indicator_index in range(len(accepted_indicators)):
            accepted_is_positive: bool = accepted_indicators[indicator_index] > 0.0
            candidate_is_positive: bool = candidate_indicators[indicator_index] > 0.0
            if accepted_is_positive != candidate_is_positive:
                crossing_indices[crossing_count] = indicator_index
                crossing_count += 1
            else:
                pass
        return tuple(crossing_indices[:crossing_count])

    def prepare_state_event_retry(
        self,
        event_time: float | None,
        evaluation_budget: FmuMeEvaluationBudget,
    ) -> tuple[float, ...]:
        """Reject the pending endpoint and optionally arm a localized event.

        :param event_time: Global retry time for a source event, or ``None``
            when this FMU only participates in the global rollback.
        :param evaluation_budget: Shared owner-provided runtime-call budget.
        :return: Readable values restored from the accepted point.
        """

        coordinator: FmiThreeModelExchangeCoordinator | None = (
            self.fmi_three_coordinator
        )
        accepted_time: float | None = self.pending_accepted_time
        restored_readable_values: tuple[float, ...] | None
        if coordinator is not None and coordinator.has_pending_candidate():
            restored_readable_values = self.resolve_pending_step(
                accepted=False,
                evaluation_budget=evaluation_budget,
            )
        else:
            if self.runtime_host is not None:
                restored_readable_values = self._restore_fmi_two_pending_point(
                    evaluation_budget=evaluation_budget
                )
            else:
                raise RuntimeError(
                    "FMI ME state-event retry requires a pending candidate"
                )
        if restored_readable_values is not None:
            pass
        else:
            raise RuntimeError(
                "FMI ME state-event retry did not restore readable values"
            )
        if event_time is None:
            self.localized_state_event_time = None
        else:
            normalized_event_time: float = float(event_time)
            if (
                accepted_time is not None
                and
                math.isfinite(normalized_event_time)
                and normalized_event_time > accepted_time
            ):
                self.localized_state_event_time = normalized_event_time
            else:
                raise ValueError(
                    "FMI ME localized state event must follow the accepted time"
                )
        return restored_readable_values

    def get_next_event_time(self) -> float | None:
        """Return the next accepted FMI time-event request.

        :return: Absolute FMI event time or ``None`` when undefined.
        """

        if self.fmi_three_coordinator is not None:
            scheduled_event_time: float | None = (
                self.fmi_three_coordinator.get_next_event_time()
            )
            localized_event_time: float | None = self.localized_state_event_time
            if scheduled_event_time is None:
                return localized_event_time
            else:
                if (
                    localized_event_time is not None
                    and localized_event_time < scheduled_event_time
                ):
                    return localized_event_time
                else:
                    return scheduled_event_time
        else:
            if self.runtime_host is not None:
                scheduled_event_time = self.fmi_two_next_event_time
                localized_event_time = self.localized_state_event_time
                if scheduled_event_time is None:
                    return localized_event_time
                else:
                    if (
                        localized_event_time is not None
                        and localized_event_time < scheduled_event_time
                    ):
                        return localized_event_time
                    else:
                        return scheduled_event_time
            else:
                return None

    def prepare_step(
        self,
        current_time: float,
        step_size: float,
        input_values: dict[str, float],
        evaluation_budget: FmuMeEvaluationBudget | None = None,
    ) -> dict[str, float]:
        """Prepare and immediately resolve one direct Backward Euler step.

        The direct API cannot coordinate a network retry.  It therefore rejects
        state events and directs coupled users to the RMS or EMT boundary.

        :param current_time: Current accepted integration time.
        :param step_size: Positive Backward Euler step length.
        :param input_values: Complete frozen FMU input values.
        :param evaluation_budget: Optional caller-owned runtime-call budget.
        :return: Output values at the accepted endpoint.
        """

        if evaluation_budget is None:
            active_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(100000)
        else:
            active_budget = evaluation_budget
        candidate_input_values: tuple[float, ...] = (
            self._build_ordered_writable_values(input_values)
        )
        accepted_state_values: np.ndarray = self.get_state_vector()
        self.pending_accepted_time = float(current_time)
        self.pending_accepted_state_values = tuple(
            accepted_state_values.tolist()
        )
        if self.fmi_three_coordinator is not None:
            accepted_point = self.fmi_three_coordinator.get_accepted_point()
            self.pending_accepted_input_values = accepted_point[2]
            self.pending_accepted_derivative_values = accepted_point[6]
            self.pending_accepted_readable_values = accepted_point[3]
            self.pending_accepted_event_indicators = accepted_point[4]
        else:
            self.pending_accepted_input_values = (
                self.fmi_two_accepted_input_values
            )
            self.pending_accepted_derivative_values = (
                self.fmi_two_accepted_derivative_values
            )
            self.pending_accepted_readable_values = (
                self.fmi_two_accepted_readable_values
            )
            self.pending_accepted_event_indicators = (
                self.fmi_two_accepted_event_indicators
            )
        candidate_state_values: np.ndarray
        candidate_derivatives: np.ndarray
        candidate_readable_values: tuple[float, ...] | None
        (
            candidate_state_values,
            candidate_derivatives,
            candidate_readable_values,
        ) = self._solve_backward_euler_candidate(
            current_time=current_time,
            step_size=step_size,
            accepted_state_values=accepted_state_values,
            input_values=input_values,
            evaluation_budget=active_budget,
        )
        candidate_time: float = current_time + step_size
        self.state_vector = np.array(candidate_state_values, copy=True)
        self.pending_time = candidate_time
        self.pending_candidate_state_values = tuple(
            candidate_state_values.tolist()
        )
        self.pending_candidate_input_values = candidate_input_values
        self.pending_candidate_derivative_values = tuple(
            candidate_derivatives.tolist()
        )
        self.pending_candidate_readable_values = candidate_readable_values

        if self.fmi_three_coordinator is not None:
            active_budget.consume()
            candidate_result: tuple[
                tuple[float, ...],
                tuple[float, ...],
                tuple[float, ...],
            ] = self.fmi_three_coordinator.evaluate_candidate(
                time_value=candidate_time,
                continuous_state_values=tuple(candidate_state_values.tolist()),
                writable_values=candidate_input_values,
                presented_derivative_values=tuple(
                    candidate_derivatives.tolist()
                ),
                presented_readable_values=candidate_readable_values,
            )
            readable_values: tuple[float, ...] = candidate_result[1]
            self.pending_candidate_event_indicators = candidate_result[2]
        else:
            if self.runtime_host is not None:
                active_budget.consume()
                named_outputs: dict[str, float] = self.runtime_host.get_real(
                    list(self.spec.output_variable_names)
                )
                ordered_outputs: list[float] = [0.0] * len(
                    self.spec.output_variable_names
                )
                output_index: int
                for output_index in range(len(self.spec.output_variable_names)):
                    output_name: str = self.spec.output_variable_names[
                        output_index
                    ]
                    ordered_outputs[output_index] = float(
                        named_outputs[output_name]
                    )
                readable_values = tuple(ordered_outputs)
                self.pending_candidate_readable_values = readable_values
                active_budget.consume()
                self.pending_candidate_event_indicators = tuple(
                    self.runtime_host.get_event_indicators()
                )
            else:
                raise RuntimeError(
                    "FMU ME adapter must be initialized before preparing a step"
                )

        crossing_indices: tuple[int, ...] = (
            self._get_pending_state_event_crossing_indices()
        )
        if len(crossing_indices) == 0:
            resolved_readable_values: tuple[float, ...] | None = (
                self.resolve_pending_step(
                    accepted=True,
                    evaluation_budget=active_budget,
                )
            )
            if resolved_readable_values is not None:
                return self._map_named_output_values(resolved_readable_values)
            else:
                return self._map_named_output_values(readable_values)
        else:
            self.resolve_pending_step(
                accepted=False,
                evaluation_budget=active_budget,
            )
            raise RuntimeError(
                "Direct FMI ME stepping cannot accept a state event; use the "
                "RMS or EMT solver-owned localization path"
            )

    def _prepare_bound_step(
        self,
        current_time: float,
        step_size: float,
        input_values: dict[str, float],
        evaluation_budget: FmuMeEvaluationBudget,
    ) -> dict[VarPowerFlowReferenceType, float]:
        """Prepare one solver-owned Backward Euler candidate.

        :param current_time: Current accepted integration time.
        :param step_size: Integration step length.
        :param input_values: Complete scalar FMU input values.
        :param evaluation_budget: Shared owner-provided runtime-call budget.
        :return: Candidate outputs indexed by VeraGrid reference.
        """

        candidate_input_values: tuple[float, ...] = (
            self._build_ordered_writable_values(input_values)
        )
        accepted_state_values: np.ndarray = self.get_state_vector()
        self.pending_accepted_time = float(current_time)
        self.pending_accepted_state_values = tuple(
            accepted_state_values.tolist()
        )
        if self.fmi_three_coordinator is not None:
            accepted_point = self.fmi_three_coordinator.get_accepted_point()
            self.pending_accepted_input_values = accepted_point[2]
            self.pending_accepted_derivative_values = accepted_point[6]
            self.pending_accepted_readable_values = accepted_point[3]
            self.pending_accepted_event_indicators = accepted_point[4]
        else:
            self.pending_accepted_input_values = (
                self.fmi_two_accepted_input_values
            )
            self.pending_accepted_derivative_values = (
                self.fmi_two_accepted_derivative_values
            )
            self.pending_accepted_readable_values = (
                self.fmi_two_accepted_readable_values
            )
            self.pending_accepted_event_indicators = (
                self.fmi_two_accepted_event_indicators
            )
        candidate_state_values: np.ndarray
        candidate_derivatives: np.ndarray
        candidate_readable_values: tuple[float, ...] | None
        (
            candidate_state_values,
            candidate_derivatives,
            candidate_readable_values,
        ) = self._solve_backward_euler_candidate(
            current_time=current_time,
            step_size=step_size,
            accepted_state_values=accepted_state_values,
            input_values=input_values,
            evaluation_budget=evaluation_budget,
        )
        candidate_time: float = current_time + step_size
        self.state_vector = np.array(candidate_state_values, copy=True)
        self.pending_time = candidate_time
        self.pending_candidate_state_values = tuple(
            candidate_state_values.tolist()
        )
        self.pending_candidate_input_values = candidate_input_values
        self.pending_candidate_derivative_values = tuple(
            candidate_derivatives.tolist()
        )
        self.pending_candidate_readable_values = candidate_readable_values

        if self.fmi_three_coordinator is not None:
            evaluation_budget.consume()
            candidate_result: tuple[
                tuple[float, ...],
                tuple[float, ...],
                tuple[float, ...],
            ] = self.fmi_three_coordinator.evaluate_candidate(
                time_value=candidate_time,
                continuous_state_values=tuple(candidate_state_values.tolist()),
                writable_values=candidate_input_values,
                presented_derivative_values=tuple(
                    candidate_derivatives.tolist()
                ),
                presented_readable_values=candidate_readable_values,
            )
            readable_values: tuple[float, ...] = candidate_result[1]
            self.pending_candidate_event_indicators = candidate_result[2]
        else:
            if self.runtime_host is not None:
                evaluation_budget.consume()
                named_outputs: dict[str, float] = self.runtime_host.get_real(
                    list(self.spec.output_variable_names)
                )
                ordered_outputs: list[float] = [0.0] * len(
                    self.spec.output_variable_names
                )
                output_index: int
                for output_index in range(len(self.spec.output_variable_names)):
                    output_name: str = self.spec.output_variable_names[
                        output_index
                    ]
                    ordered_outputs[output_index] = float(
                        named_outputs[output_name]
                    )
                readable_values = tuple(ordered_outputs)
                self.pending_candidate_readable_values = readable_values
                evaluation_budget.consume()
                self.pending_candidate_event_indicators = tuple(
                    self.runtime_host.get_event_indicators()
                )
            else:
                raise RuntimeError(
                    "FMU ME adapter must be initialized before preparing a step"
                )
        return self.map_bound_output_values(readable_values)

    def close(self) -> None:
        """Release the FMU runtime used by the adapter.

        :return: None.
        """

        if self.runtime_host is not None:
            self.runtime_host.close()
            self.runtime_host = None
        else:
            pass
        if self.fmi_three_coordinator is not None:
            self.fmi_three_coordinator.close()
            self.fmi_three_coordinator = None
        else:
            pass
        self.initialized = False
        self.localized_state_event_time = None
        self.fmi_two_next_event_time = None
        self.fmi_two_accepted_input_values = None
        self.fmi_two_accepted_derivative_values = None
        self.fmi_two_accepted_readable_values = None
        self.fmi_two_accepted_event_indicators = None
        self._clear_pending_state_event_data()


def _build_state_variable_names(metadata: FmuModelDescription) -> tuple[str, ...]:
    """Recover the ordered continuous-state variable names from derivative metadata.

    :param metadata: Parsed FMU metadata.
    :return: Ordered continuous-state variable names.
    """

    state_variable_names: list[str] = list()
    if metadata.fmi_version_family == FmiVersion.FMI_1_0:
        state_index: int
        for state_index in range(metadata.number_of_continuous_states):
            # FMI 1 owns state identity through the runtime
            # fmiGetStateValueReferences call, not through XML derivative links.
            state_variable_names.append(f"__fmi_one_state_{state_index}")
    else:
        if metadata.fmi_version_family == FmiVersion.FMI_3_0:
            state_variable: FmuVariableDescription
            for state_variable in metadata.get_state_variables():
                # FMI 3 resolves the derivative relationship through the state's
                # value reference while parsing the authoritative metadata.
                state_variable_names.append(state_variable.name)
        else:
            derivative_variable: FmuVariableDescription
            for derivative_variable in metadata.get_derivative_variables():
                derivative_index: int | None = derivative_variable.derivative_index
                if derivative_index is not None:
                    # FMI 2 derivative indices are 1-based positions in the
                    # ordered model-variable sequence.
                    state_variable_names.append(
                        metadata.variables[derivative_index - 1].name
                    )
                else:
                    pass
    return tuple(state_variable_names)


def build_fmu_me_device_spec(
    domain: FmuMeDomain,
    config: FmuImportConfig,
    device_tpe: DeviceType,
    input_variable_names: tuple[str, ...],
    output_variable_names: tuple[str, ...],
    worker_limits: FmiThreeWorkerHostLimits | None = None,
    maximum_event_iterations: int = 32,
    input_bindings: tuple[FmuRefBinding, ...] | None = None,
    output_bindings: tuple[FmuRefBinding, ...] | None = None,
    output_defaults: dict[VarPowerFlowReferenceType, float] | None = None,
    output_param_uids: dict[VarPowerFlowReferenceType, int] | None = None,
    configuration_float64_values: tuple[
        FmiThreeFloat64ConfigurationValue, ...
    ] = tuple(),
    configuration_uint64_values: tuple[
        FmiThreeUInt64ConfigurationValue, ...
    ] = tuple(),
    parameter_values: tuple[FmuFloat64ParameterValue, ...] = tuple(),
) -> FmuMeDeviceSpec:
    """Build the validated runtime specification for one FMU ME device.

    :param domain: VeraGrid domain that will consume the FMU.
    :param config: FMU runtime configuration.
    :param device_tpe: VeraGrid device type.
    :param input_variable_names: Ordered FMU input names.
    :param output_variable_names: Ordered FMU output names.
    :param worker_limits: Explicit FMI 3 worker supervision policy, when used.
    :param maximum_event_iterations: Positive Event Mode convergence bound.
    :param input_bindings: Optional typed bindings aligned with input names.
    :param output_bindings: Optional typed bindings aligned with output names.
    :param output_defaults: Optional output fallbacks before the first sample.
    :param output_param_uids: Optional runtime output-parameter identifiers.
    :param configuration_float64_values: Structural Float64 declarations.
    :param configuration_uint64_values: Structural UInt64 declarations.
    :param parameter_values: Ephemeral values resolved from Block.parameters.
    :return: Runtime FMU ME device specification.
    """

    resolved_input_bindings: tuple[FmuRefBinding, ...]
    if input_bindings is None:
        resolved_input_bindings = tuple()
    else:
        resolved_input_bindings = tuple(input_bindings)
        bound_input_names_list: list[str] = [""] * len(resolved_input_bindings)
        binding_index: int
        for binding_index in range(len(resolved_input_bindings)):
            bound_input_names_list[binding_index] = (
                resolved_input_bindings[binding_index].fmu_variable_name
            )
        bound_input_names: tuple[str, ...] = tuple(bound_input_names_list)
        if bound_input_names == input_variable_names:
            pass
        else:
            raise ValueError(
                "FMU ME input bindings do not match the declared variable names"
            )
    resolved_output_bindings: tuple[FmuRefBinding, ...]
    if output_bindings is None:
        resolved_output_bindings = tuple()
    else:
        resolved_output_bindings = tuple(output_bindings)
        bound_output_names_list: list[str] = [""] * len(
            resolved_output_bindings
        )
        for binding_index in range(len(resolved_output_bindings)):
            bound_output_names_list[binding_index] = (
                resolved_output_bindings[binding_index].fmu_variable_name
            )
        bound_output_names: tuple[str, ...] = tuple(bound_output_names_list)
        if bound_output_names == output_variable_names:
            pass
        else:
            raise ValueError(
                "FMU ME output bindings do not match the declared variable names"
            )
    resolved_output_defaults: dict[VarPowerFlowReferenceType, float]
    if output_defaults is None:
        resolved_output_defaults = dict()
    else:
        resolved_output_defaults = dict(output_defaults)
    resolved_output_param_uids: dict[VarPowerFlowReferenceType, int]
    if output_param_uids is None:
        resolved_output_param_uids = dict()
    else:
        resolved_output_param_uids = dict(output_param_uids)

    metadata: FmuModelDescription = read_fmu_model_description(config.fmu_path)
    float64_profile: FmiThreeWorkerFloat64Profile | None
    if metadata.fmi_version_family in (
        FmiVersion.FMI_1_0,
        FmiVersion.FMI_2_0,
    ):
        resolved_mode: FmuInterfaceMode = config.resolve_execution_mode(metadata)
        float64_profile = None
        has_fmi_three_configuration: bool = (
            len(configuration_float64_values) > 0
            or len(configuration_uint64_values) > 0
        )
        if has_fmi_three_configuration:
            raise RuntimeError(
                "FMI 3 Configuration Mode declarations require FMI 3"
            )
        else:
            pass
    else:
        if metadata.fmi_version_family == FmiVersion.FMI_3_0:
            resolved_mode = config.resolve_execution_mode(metadata)
            float64_profile = resolve_fmi_three_worker_float64_profile(metadata)
            validate_fmi_three_model_exchange_worker_profile(
                metadata=metadata,
                preferred_mode=resolved_mode,
                float64_profile=float64_profile,
            )
            if worker_limits is not None:
                pass
            else:
                raise ValueError(
                    "FMI 3 Model Exchange devices require explicit worker limits"
                )
        else:
            raise ValueError(
                f"FMI {metadata.fmi_version} execution is not supported yet"
            )
    if resolved_mode == FmuInterfaceMode.MODEL_EXCHANGE:
        reserved_parameter_names: list[str] = [""] * (
            len(input_variable_names)
            + len(configuration_float64_values)
            + len(configuration_uint64_values)
        )
        reserved_name_index: int = 0
        reserved_input_name: str
        for reserved_input_name in input_variable_names:
            reserved_parameter_names[reserved_name_index] = reserved_input_name
            reserved_name_index += 1
        float64_configuration: FmiThreeFloat64ConfigurationValue
        for float64_configuration in configuration_float64_values:
            reserved_parameter_names[reserved_name_index] = (
                float64_configuration.variable_name
            )
            reserved_name_index += 1
        uint64_configuration: FmiThreeUInt64ConfigurationValue
        for uint64_configuration in configuration_uint64_values:
            reserved_parameter_names[reserved_name_index] = (
                uint64_configuration.variable_name
            )
            reserved_name_index += 1
        validate_fmu_float64_parameter_values(
            parameter_values=parameter_values,
            metadata=metadata,
            reserved_variable_names=tuple(reserved_parameter_names),
        )
        available_variables: set[str] = set(metadata.get_variable_names())
        input_variable_name: str
        for input_variable_name in input_variable_names:
            if input_variable_name in available_variables:
                input_variable: FmuVariableDescription = metadata.get_variable(
                    input_variable_name
                )
                input_causality: str = input_variable.causality or "local"
                if metadata.fmi_version_family in (
                    FmiVersion.FMI_1_0,
                    FmiVersion.FMI_2_0,
                ):
                    input_variability: str = (
                        input_variable.variability or "continuous"
                    )
                else:
                    if input_variable.variability is not None:
                        input_variability = input_variable.variability
                    else:
                        raise RuntimeError(
                            "FMI 3 ME input metadata lost its effective variability"
                        )
                if (
                    input_causality == "input"
                    and input_variability == "continuous"
                ):
                    pass
                else:
                    raise RuntimeError(
                        "FMI ME runtime input must be continuous input "
                        f"{input_variable_name!r} "
                        f"(causality={input_causality!r}, "
                        f"variability={input_variability!r})"
                    )
                if len(input_variable.dimensions) == 0:
                    pass
                else:
                    raise RuntimeError(
                        "FMI 3 ME device array inputs require a complete "
                        "value provider"
                    )
            else:
                raise KeyError(f"FMU variable {input_variable_name!r} was not found in {config.fmu_path}")
        output_variable_name: str
        for output_variable_name in output_variable_names:
            if output_variable_name in available_variables:
                if float64_profile is not None:
                    output_variable: FmuVariableDescription = metadata.get_variable(
                        output_variable_name
                    )
                    if len(output_variable.dimensions) == 0:
                        pass
                    else:
                        has_typed_output_bindings: bool = (
                            len(resolved_output_bindings) > 0
                        )
                        if has_typed_output_bindings:
                            pass
                        else:
                            raise RuntimeError(
                                "FMI 3 ME array outputs require typed device "
                                "bindings"
                            )
                else:
                    pass
            else:
                raise KeyError(f"FMU variable {output_variable_name!r} was not found in {config.fmu_path}")

        state_variable_names: tuple[str, ...] = _build_state_variable_names(metadata)
        derivative_variables: list[FmuVariableDescription] = (
            metadata.get_derivative_variables()
        )
        derivative_variable_names_list: list[str] = [""] * len(
            derivative_variables
        )
        derivative_index: int
        for derivative_index in range(len(derivative_variables)):
            derivative_variable_names_list[derivative_index] = (
                derivative_variables[derivative_index].name
            )
        derivative_variable_names: tuple[str, ...] = tuple(
            derivative_variable_names_list
        )
        return FmuMeDeviceSpec(
            domain=domain,
            config=config,
            device_tpe=device_tpe,
            input_variable_names=input_variable_names,
            output_variable_names=output_variable_names,
            state_variable_names=state_variable_names,
            derivative_variable_names=derivative_variable_names,
            worker_limits=worker_limits,
            float64_profile=float64_profile,
            maximum_event_iterations=maximum_event_iterations,
            input_bindings=resolved_input_bindings,
            output_bindings=resolved_output_bindings,
            output_defaults=resolved_output_defaults,
            output_param_uids=resolved_output_param_uids,
            configuration_float64_values=configuration_float64_values,
            configuration_uint64_values=configuration_uint64_values,
            parameter_values=parameter_values,
        )
    else:
        raise ValueError(f"FMU ME device specs require a Model Exchange FMU, got {resolved_mode.value}")


def build_rms_fmu_me_injection_template(
    vfactory: VarFactory,
    config: FmuImportConfig,
    input_bindings: tuple[FmuRefBinding, ...],
    output_bindings: tuple[FmuRefBinding, ...],
    name: str,
    device_tpe: DeviceType = DeviceType.LoadDevice,
    output_defaults: dict[VarPowerFlowReferenceType, float] | None = None,
    worker_limits: FmiThreeWorkerHostLimits | None = None,
    maximum_event_iterations: int = 32,
) -> RmsModelTemplate:
    """Build the symbolic RMS shell for an imported FMU ME device.

    :param vfactory: Variable factory used by the owning grid.
    :param config: FMU runtime configuration.
    :param input_bindings: VeraGrid-to-FMU bindings.
    :param output_bindings: FMU-to-VeraGrid bindings.
    :param name: Template name.
    :param device_tpe: VeraGrid device type.
    :param output_defaults: Default output values before the first FMU step.
    :param worker_limits: Explicit FMI 3 worker supervision policy, when used.
    :param maximum_event_iterations: Positive Event Mode convergence bound.
    :return: RMS template wrapping the FMU shell block.
    """

    input_variable_names: list[str] = [""] * len(input_bindings)
    binding_index: int
    for binding_index in range(len(input_bindings)):
        input_variable_names[binding_index] = (
            input_bindings[binding_index].fmu_variable_name
        )
    output_variable_names: list[str] = [""] * len(output_bindings)
    for binding_index in range(len(output_bindings)):
        output_variable_names[binding_index] = (
            output_bindings[binding_index].fmu_variable_name
        )

    # The FMU metadata is validated before the symbolic shell block is created.
    build_fmu_me_device_spec(
        domain=FmuMeDomain.RMS,
        config=config,
        device_tpe=device_tpe,
        input_variable_names=tuple(input_variable_names),
        output_variable_names=tuple(output_variable_names),
        worker_limits=worker_limits,
        maximum_event_iterations=maximum_event_iterations,
        input_bindings=input_bindings,
        output_bindings=output_bindings,
    )

    template: RmsModelTemplate = RmsModelTemplate(name=name)
    template.tpe = device_tpe
    template.block = _build_template_block(vfactory, name, output_bindings, output_defaults)
    return template


def build_emt_fmu_me_injection_template(
    vfactory: VarFactory,
    config: FmuImportConfig,
    input_bindings: tuple[FmuRefBinding, ...],
    output_bindings: tuple[FmuRefBinding, ...],
    name: str,
    device_tpe: DeviceType = DeviceType.LoadDevice,
    output_defaults: dict[VarPowerFlowReferenceType, float] | None = None,
    worker_limits: FmiThreeWorkerHostLimits | None = None,
    maximum_event_iterations: int = 32,
) -> EmtModelTemplate:
    """Build the symbolic EMT shell for an imported FMU ME device.

    :param vfactory: Variable factory used by the owning grid.
    :param config: FMU runtime configuration.
    :param input_bindings: VeraGrid-to-FMU bindings.
    :param output_bindings: FMU-to-VeraGrid bindings.
    :param name: Template name.
    :param device_tpe: VeraGrid device type.
    :param output_defaults: Default output values before the first FMU step.
    :param worker_limits: Explicit FMI 3 worker supervision policy, when used.
    :param maximum_event_iterations: Positive Event Mode convergence bound.
    :return: EMT template wrapping the FMU shell block.
    """

    input_variable_names: list[str] = [""] * len(input_bindings)
    binding_index: int
    for binding_index in range(len(input_bindings)):
        input_variable_names[binding_index] = (
            input_bindings[binding_index].fmu_variable_name
        )
    output_variable_names: list[str] = [""] * len(output_bindings)
    for binding_index in range(len(output_bindings)):
        output_variable_names[binding_index] = (
            output_bindings[binding_index].fmu_variable_name
        )

    build_fmu_me_device_spec(
        domain=FmuMeDomain.EMT,
        config=config,
        device_tpe=device_tpe,
        input_variable_names=tuple(input_variable_names),
        output_variable_names=tuple(output_variable_names),
        worker_limits=worker_limits,
        maximum_event_iterations=maximum_event_iterations,
        input_bindings=input_bindings,
        output_bindings=output_bindings,
    )

    template: EmtModelTemplate = EmtModelTemplate(name=name)
    template.tpe = device_tpe
    template.block = _build_template_block(
        vfactory=vfactory,
        name=name,
        output_bindings=output_bindings,
        output_defaults=output_defaults,
        input_bindings=input_bindings,
    )
    _ensure_emt_external_mapping_keys(template.block)
    template.block.api_obj_mapping = dict()
    template.block.api_obj_mapping[ParamPowerFlowReferenceType.Pl0_A] = None
    template.block.api_obj_mapping[ParamPowerFlowReferenceType.Pl0_B] = None
    template.block.api_obj_mapping[ParamPowerFlowReferenceType.Pl0_C] = None
    template.block.api_obj_mapping[ParamPowerFlowReferenceType.Ql0_A] = None
    template.block.api_obj_mapping[ParamPowerFlowReferenceType.Ql0_B] = None
    template.block.api_obj_mapping[ParamPowerFlowReferenceType.Ql0_C] = None
    template.block.api_obj_mapping[ParamPowerFlowReferenceType.omega_base] = None
    return template


def _read_rms_me_device_config(device: Any) -> Any | None:
    """Read the serialized FMU ME configuration stored on one device.

    :param device: VeraGrid device instance.
    :return: Parsed device configuration when available.
    """

    try:
        config_text: str = device.rms_fmu_me_import_config
    except AttributeError:
        if isinstance(device, InjectionParent) or isinstance(device, BranchParent):
            raise
        else:
            return None
    return load_fmu_me_device_config(config_text)


def _read_emt_me_device_config(device: Any) -> Any | None:
    """Read the serialized FMU ME configuration stored on one EMT device.

    :param device: VeraGrid device instance.
    :return: Parsed device configuration when available.
    """

    try:
        config_text: str = device.emt_fmu_me_import_config
    except AttributeError:
        if isinstance(device, InjectionParent) or isinstance(device, BranchParent):
            raise
        else:
            return None
    return load_fmu_me_device_config(config_text)


def _build_rms_me_runtime_spec(device: Any, block: Block) -> Any | None:
    """Rebuild the FMU ME runtime specification from the stored device config.

    :param device: VeraGrid device instance.
    :param block: Device block used in the active RMS problem.
    :return: Runtime FMU ME specification when available.
    """

    record = _read_rms_me_device_config(device)
    if record is None:
        return None
    else:
        if record.domain == FmuMeDomain.RMS:
            return restore_fmu_me_spec_from_record(record, block, device.device_type)
        else:
            return None


def _build_emt_me_runtime_spec(device: Any, block: Block) -> Any | None:
    """Rebuild the FMU ME runtime specification from the stored EMT device config.

    :param device: VeraGrid device instance.
    :param block: Device block used in the active EMT problem.
    :return: Runtime FMU ME specification when available.
    """

    record = _read_emt_me_device_config(device)
    if record is None:
        return None
    else:
        if record.domain == FmuMeDomain.EMT:
            return restore_fmu_me_spec_from_record(record, block, device.device_type)
        else:
            return None


def _get_event_param_index_map(problem: Any) -> dict[int, int]:
    """
    Return the runtime event-parameter index map exposed by the active problem.

    :param problem: Runtime problem wrapper.
    :return: UID-to-index event-parameter map.
    """

    try:
        return problem._uid2idx_event_params
    except AttributeError:
        return problem.uid2idx_event_params


def _get_rms_me_input_value(problem: Any, device: Any, reference: VarPowerFlowReferenceType, x_snapshot: np.ndarray) -> float:
    """Read one RMS FMU ME input from the current network snapshot.

    :param problem: RMS problem instance.
    :param device: VeraGrid device instance.
    :param reference: Requested VeraGrid external reference.
    :param x_snapshot: Current accepted state snapshot.
    :return: Numeric input value.
    """

    if reference in {VarPowerFlowReferenceType.Vm, VarPowerFlowReferenceType.Va, VarPowerFlowReferenceType.Vdc}:
        bus_model: Block = device.bus.rms_model
        variable: Var = bus_model.external_mapping[reference]
        return float(x_snapshot[problem.uid2idx_vars[variable.uid]])
    else:
        raise KeyError(f"Unsupported RMS FMU ME input reference {reference.value!r}")


def _get_emt_me_input_value(problem: Any, device: Any, reference: VarPowerFlowReferenceType, x_snapshot: np.ndarray) -> float:
    """Read one EMT FMU ME input from the current network snapshot.

    :param problem: EMT problem instance.
    :param device: VeraGrid device instance.
    :param reference: Requested VeraGrid external reference.
    :param x_snapshot: Current accepted state snapshot.
    :return: Numeric input value.
    """

    if reference in {
        VarPowerFlowReferenceType.v_N,
        VarPowerFlowReferenceType.v_A,
        VarPowerFlowReferenceType.v_B,
        VarPowerFlowReferenceType.v_C,
        VarPowerFlowReferenceType.Vdc,
    }:
        bus_model: Block = device.bus.emt_model
        variable: Var = bus_model.external_mapping[reference]
        return float(x_snapshot[problem.uid2idx_vars[variable.uid]])
    else:
        raise KeyError(f"Unsupported EMT FMU ME input reference {reference.value!r}")


class RmsFmuMeDeviceAdapter:
    """Adapt one imported FMU ME device to the RMS communication-step loop.

    :param problem: RMS problem instance.
    :param device: VeraGrid device instance.
    :param spec: Runtime FMU ME specification.
    :param output_param_indices: Runtime-parameter indices receiving FMU outputs.
    """

    __slots__ = ("problem", "device", "spec", "output_param_indices", "runtime_adapter", "last_outputs")

    def __init__(
        self,
        problem: Any,
        device: Any,
        spec: FmuMeDeviceSpec,
        output_param_indices: dict[VarPowerFlowReferenceType, int],
        solver_policy: FmuMeSolverPolicy,
    ) -> None:
        """Store the RMS FMU ME runtime adapter.

        :return: None.
        """

        self.problem: Any = problem
        self.device: Any = device
        self.spec: FmuMeDeviceSpec = spec
        self.output_param_indices: dict[VarPowerFlowReferenceType, int] = output_param_indices
        self.runtime_adapter: FmuMeDeviceAdapter = FmuMeDeviceAdapter(
            spec=spec,
            solver_policy=solver_policy,
        )
        self.last_outputs: dict[VarPowerFlowReferenceType, float] = dict()

    def _build_input_values(self, x_snapshot: np.ndarray) -> dict[str, float]:
        """Collect the FMU ME input values from the current RMS snapshot.

        :param x_snapshot: Current accepted state snapshot.
        :return: FMU input values.
        """

        input_values: dict[str, float] = dict()
        binding: FmuRefBinding
        for binding in self.spec.input_bindings:
            input_values[binding.fmu_variable_name] = _get_rms_me_input_value(self.problem, self.device, binding.reference, x_snapshot)
        return input_values

    def initialize_outputs(
        self,
        time_value: float,
        x_snapshot: np.ndarray,
        evaluation_budget: FmuMeEvaluationBudget,
    ) -> dict[VarPowerFlowReferenceType, float]:
        """Initialize the FMU ME runtime and return its first output sample.

        :param time_value: Current simulation time.
        :param x_snapshot: Current accepted state snapshot.
        :param evaluation_budget: Shared initialization runtime-call budget.
        :return: FMU outputs indexed by VeraGrid reference.
        """

        self.runtime_adapter.initialize(
            start_time=time_value,
            input_values=self._build_input_values(x_snapshot),
            evaluation_budget=evaluation_budget,
        )
        outputs: dict[VarPowerFlowReferenceType, float] = (
            self.runtime_adapter._evaluate_bound_outputs(
                time_value,
                self._build_input_values(x_snapshot),
                evaluation_budget=evaluation_budget,
            )
        )
        self.last_outputs = dict(outputs)
        return outputs

    def advance(
        self,
        current_time: float,
        step_size: float,
        x_snapshot: np.ndarray,
        evaluation_budget: FmuMeEvaluationBudget,
    ) -> dict[VarPowerFlowReferenceType, float]:
        """Advance the FMU ME runtime for one RMS communication step.

        :param current_time: Current simulation time.
        :param step_size: RMS communication step.
        :param x_snapshot: Current accepted state snapshot.
        :param evaluation_budget: Shared solver-step runtime-call budget.
        :return: FMU outputs indexed by VeraGrid reference.
        """

        outputs: dict[VarPowerFlowReferenceType, float] = (
            self.runtime_adapter._prepare_bound_step(
                current_time=current_time,
                step_size=step_size,
                input_values=self._build_input_values(x_snapshot),
                evaluation_budget=evaluation_budget,
            )
        )
        self.last_outputs = dict(outputs)
        return outputs

    def resolve_step(
        self,
        accepted: bool,
        evaluation_budget: FmuMeEvaluationBudget,
    ) -> dict[VarPowerFlowReferenceType, float]:
        """Resolve the pending FMI 3 candidate after the RMS solve.

        :param accepted: Whether the RMS numerical step converged.
        :param evaluation_budget: Shared solver-step runtime-call budget.
        :return: Outputs belonging to the resolved accepted point.
        """

        readable_values: tuple[float, ...] | None = (
            self.runtime_adapter.resolve_pending_step(
                accepted=accepted,
                evaluation_budget=evaluation_budget,
            )
        )
        if readable_values is not None:
            resolved_outputs: dict[VarPowerFlowReferenceType, float] = (
                self.runtime_adapter.map_bound_output_values(readable_values)
            )
            self.last_outputs = dict(resolved_outputs)
        else:
            resolved_outputs = dict(self.last_outputs)
        return resolved_outputs

    def prepare_state_event_retry(
        self,
        event_time: float | None,
        evaluation_budget: FmuMeEvaluationBudget,
    ) -> dict[VarPowerFlowReferenceType, float]:
        """Restore this device's accepted outputs for a coordinated event retry.

        :param event_time: Global localized time when this device must arm its event.
        :param evaluation_budget: Existing shared runtime-call budget.
        :return: Restored outputs without evaluating the FMU again.
        """
        # The runtime restores the transaction; mapping consumes its cached values.
        restored_values: tuple[float, ...] = self.runtime_adapter.prepare_state_event_retry(
            event_time=event_time, evaluation_budget=evaluation_budget,
        )
        restored_outputs: dict[VarPowerFlowReferenceType, float] = (
            self.runtime_adapter.map_bound_output_values(restored_values)
        )
        self.last_outputs = dict(restored_outputs)
        return restored_outputs

    def apply_outputs(self, target: np.ndarray, outputs: dict[VarPowerFlowReferenceType, float]) -> None:
        """Write the FMU ME outputs into VeraGrid runtime-parameter storage.

        :param target: Runtime-parameter array.
        :param outputs: FMU outputs indexed by VeraGrid reference.
        :return: None.
        """

        reference: VarPowerFlowReferenceType
        for reference, value in outputs.items():
            target[self.output_param_indices[reference]] = float(value)

    def close(self) -> None:
        """Release the FMU ME runtime used by the adapter.

        :return: None.
        """

        self.runtime_adapter.close()


class EmtFmuMeDeviceAdapter:
    """Adapt one imported FMU ME device to the EMT boundary-update loop.

    :param problem: EMT problem instance.
    :param device: VeraGrid device instance.
    :param spec: Runtime FMU ME specification.
    :param output_param_indices: Runtime-parameter indices receiving FMU outputs.
    """

    __slots__ = (
        "problem",
        "device",
        "spec",
        "output_param_indices",
        "runtime_adapter",
        "last_time",
        "initialized",
        "last_outputs",
        "pending_previous_time",
    )

    def __init__(
        self,
        problem: Any,
        device: Any,
        spec: FmuMeDeviceSpec,
        output_param_indices: dict[VarPowerFlowReferenceType, int],
        solver_policy: FmuMeSolverPolicy,
    ) -> None:
        """Store the EMT FMU ME runtime adapter.

        :return: None.
        """

        self.problem: Any = problem
        self.device: Any = device
        self.spec: FmuMeDeviceSpec = spec
        self.output_param_indices: dict[VarPowerFlowReferenceType, int] = output_param_indices
        self.runtime_adapter: FmuMeDeviceAdapter = FmuMeDeviceAdapter(
            spec=spec,
            solver_policy=solver_policy,
        )
        self.last_time: float = 0.0
        self.initialized: bool = False
        self.last_outputs: dict[VarPowerFlowReferenceType, float] = dict()
        self.pending_previous_time: float | None = None

    def _build_input_values(self, x_snapshot: np.ndarray) -> dict[str, float]:
        """Collect the FMU ME input values from the current EMT snapshot.

        :param x_snapshot: Current accepted state snapshot.
        :return: FMU input values.
        """

        input_values: dict[str, float] = dict()
        binding: FmuRefBinding
        for binding in self.spec.input_bindings:
            input_values[binding.fmu_variable_name] = _get_emt_me_input_value(self.problem, self.device, binding.reference, x_snapshot)
        return input_values

    def initialize_outputs(
        self,
        time_value: float,
        x_snapshot: np.ndarray,
        evaluation_budget: FmuMeEvaluationBudget,
    ) -> dict[VarPowerFlowReferenceType, float]:
        """Initialize the FMU ME runtime and return its first output sample.

        :param time_value: Current simulation time.
        :param x_snapshot: Current accepted state snapshot.
        :param evaluation_budget: Shared initialization runtime-call budget.
        :return: FMU outputs indexed by VeraGrid reference.
        """

        self.runtime_adapter.initialize(
            start_time=time_value,
            input_values=self._build_input_values(x_snapshot),
            evaluation_budget=evaluation_budget,
        )
        self.initialized = True
        self.last_time = time_value
        outputs: dict[VarPowerFlowReferenceType, float] = (
            self.runtime_adapter._evaluate_bound_outputs(
            time_value,
            self._build_input_values(x_snapshot),
            evaluation_budget=evaluation_budget,
        )
        )
        self.last_outputs = dict(outputs)
        return outputs

    def advance(
        self,
        current_time: float,
        step_size: float,
        x_snapshot: np.ndarray,
        evaluation_budget: FmuMeEvaluationBudget,
    ) -> dict[VarPowerFlowReferenceType, float]:
        """Advance the FMU ME runtime for one EMT communication step.

        :param current_time: Current simulation time.
        :param step_size: EMT communication step.
        :param x_snapshot: Current accepted state snapshot.
        :param evaluation_budget: Shared solver-step runtime-call budget.
        :return: FMU outputs indexed by VeraGrid reference.
        """

        outputs: dict[VarPowerFlowReferenceType, float] = (
            self.runtime_adapter._prepare_bound_step(
                current_time=current_time,
                step_size=step_size,
                input_values=self._build_input_values(x_snapshot),
                evaluation_budget=evaluation_budget,
            )
        )
        self.pending_previous_time = current_time
        self.last_time = current_time + step_size
        self.last_outputs = dict(outputs)
        return outputs

    def resolve_step(
        self,
        accepted: bool,
        evaluation_budget: FmuMeEvaluationBudget,
    ) -> dict[VarPowerFlowReferenceType, float]:
        """Resolve the pending FMI 3 candidate after the EMT solve.

        :param accepted: Whether the EMT numerical step converged.
        :param evaluation_budget: Shared solver-step runtime-call budget.
        :return: Outputs belonging to the resolved accepted point.
        """

        readable_values: tuple[float, ...] | None = (
            self.runtime_adapter.resolve_pending_step(
                accepted=accepted,
                evaluation_budget=evaluation_budget,
            )
        )
        if readable_values is not None:
            resolved_outputs: dict[VarPowerFlowReferenceType, float] = (
                self.runtime_adapter.map_bound_output_values(readable_values)
            )
            self.last_outputs = dict(resolved_outputs)
        else:
            resolved_outputs = dict(self.last_outputs)
        if readable_values is not None and not accepted:
            if self.pending_previous_time is not None:
                self.last_time = self.pending_previous_time
            else:
                pass
        else:
            pass
        self.pending_previous_time = None
        return resolved_outputs

    def prepare_state_event_retry(
        self,
        event_time: float | None,
        evaluation_budget: FmuMeEvaluationBudget,
    ) -> dict[VarPowerFlowReferenceType, float]:
        """Restore this device's accepted outputs for a coordinated event retry.

        :param event_time: Global localized time when this device must arm its event.
        :param evaluation_budget: Existing shared runtime-call budget.
        :return: Restored outputs without evaluating the FMU again.
        """
        # The runtime restores the transaction; mapping consumes its cached values.
        restored_values: tuple[float, ...] = self.runtime_adapter.prepare_state_event_retry(
            event_time=event_time, evaluation_budget=evaluation_budget,
        )
        restored_outputs: dict[VarPowerFlowReferenceType, float] = (
            self.runtime_adapter.map_bound_output_values(restored_values)
        )
        # Restore the device communication clock to the same accepted point.
        if self.pending_previous_time is not None:
            self.last_time = self.pending_previous_time
        else:
            pass
        self.pending_previous_time = None
        self.last_outputs = dict(restored_outputs)
        return restored_outputs

    def apply_outputs(self, target: np.ndarray, outputs: dict[VarPowerFlowReferenceType, float]) -> None:
        """Write the FMU ME outputs into VeraGrid runtime-parameter storage.

        :param target: Runtime-parameter array.
        :param outputs: FMU outputs indexed by VeraGrid reference.
        :return: None.
        """

        reference: VarPowerFlowReferenceType
        for reference, value in outputs.items():
            target[self.output_param_indices[reference]] = float(value)

    def close(self) -> None:
        """Release the FMU ME runtime used by the adapter.

        :return: None.
        """

        self.runtime_adapter.close()


def _build_fmu_me_solver_policy(
    options: RmsOptions | EmtOptions,
) -> FmuMeSolverPolicy:
    """Copy the owning simulation's FMI ME numerical policy.

    :param options: Validated RMS or EMT simulation options.
    :return: Immutable-by-interface policy for attached ME adapters.
    """

    return FmuMeSolverPolicy(
        integration_method=options.integration_method,
        absolute_tolerance=options.fmi_me_newton_absolute_tolerance,
        relative_tolerance=options.fmi_me_newton_relative_tolerance,
        maximum_newton_iterations=options.fmi_me_newton_max_iterations,
        maximum_continuous_states=options.fmi_me_max_continuous_states,
    )


def register_rms_fmu_me_device(problem: Any, device: Any, block: Block) -> None:
    """Register one imported FMU ME device in the active RMS problem.

    :param problem: RMS problem instance.
    :param device: VeraGrid device instance.
    :param block: Device RMS block used in the active problem.
    :return: None.
    """

    spec: Optional[FmuMeDeviceSpec] = _build_rms_me_runtime_spec(device, block)
    if spec is None:
        return
    else:
        adapter: RmsFmuMeDeviceAdapter
        for adapter in problem._fmu_me_adapters:
            if adapter.device.idtag == device.idtag:
                return
            else:
                pass

        output_param_indices: dict[VarPowerFlowReferenceType, int] = dict()
        uid_to_index = _get_event_param_index_map(problem)
        reference: VarPowerFlowReferenceType
        for reference, uid in spec.output_param_uids.items():
            output_param_indices[reference] = uid_to_index[uid]

        solver_policy: FmuMeSolverPolicy = _build_fmu_me_solver_policy(
            problem.options
        )
        problem._fmu_me_adapters.append(
            RmsFmuMeDeviceAdapter(
                problem=problem,
                device=device,
                spec=spec,
                output_param_indices=output_param_indices,
                solver_policy=solver_policy,
            )
        )
        problem._fmu_me_initialized = False


def initialize_rms_fmu_me_devices(problem: Any, x_snapshot: np.ndarray, time_value: float = 0.0) -> None:
    """Initialize all imported FMU ME devices before the RMS loop starts.

    :param problem: RMS problem instance.
    :param x_snapshot: Initial accepted state snapshot.
    :param time_value: Initial simulation time.
    :return: None.
    """

    if len(problem._fmu_me_adapters) > 0:
        initialization_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(
            problem.options.fmi_me_max_runtime_evaluations_per_step
        )
        adapter: RmsFmuMeDeviceAdapter
        for adapter in problem._fmu_me_adapters:
            outputs = adapter.initialize_outputs(
                time_value,
                x_snapshot,
                evaluation_budget=initialization_budget,
            )
            adapter.apply_outputs(problem._variable_parameters_values, outputs)
            if problem._variable_parameters_values is None:
                problem._last_variable_parameters_values = None
            else:
                problem._last_variable_parameters_values = np.array(problem._variable_parameters_values, copy=True)
        problem._fmu_me_initialized = True
    else:
        problem._fmu_me_initialized = True


def advance_rms_fmu_me_devices(problem: Any, time_value: float, x_snapshot: np.ndarray, step_size: float) -> None:
    """Prepare or replace all FMU ME candidates for one RMS local step.

    :param problem: RMS problem instance.
    :param time_value: Current simulation time.
    :param x_snapshot: Current accepted state snapshot.
    :param step_size: RMS communication step.
    :return: None.
    """

    if len(problem._fmu_me_adapters) > 0:
        if problem._fmu_me_initialized:
            pass
        else:
            initialize_rms_fmu_me_devices(problem=problem, x_snapshot=x_snapshot, time_value=time_value)

        existing_budget: FmuMeEvaluationBudget | None = (
            problem._fmu_me_evaluation_budget
        )
        if existing_budget is None:
            evaluation_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(
                problem.options.fmi_me_max_runtime_evaluations_per_step
            )
            problem._fmu_me_evaluation_budget = evaluation_budget
        else:
            evaluation_budget = existing_budget
        adapter: RmsFmuMeDeviceAdapter
        # First restore every FMU to the common accepted point.  Only then may
        # the corrected network snapshot replace the complete candidate set.
        for adapter in problem._fmu_me_adapters:
            if adapter.runtime_adapter.has_pending_candidate():
                restored_outputs: dict[VarPowerFlowReferenceType, float] = (
                    adapter.resolve_step(
                        accepted=False,
                        evaluation_budget=evaluation_budget,
                    )
                )
                adapter.apply_outputs(
                    problem._variable_parameters_values,
                    restored_outputs,
                )
            else:
                pass
        for adapter in problem._fmu_me_adapters:
            outputs = adapter.advance(
                current_time=time_value,
                step_size=step_size,
                x_snapshot=x_snapshot,
                evaluation_budget=evaluation_budget,
            )
            adapter.apply_outputs(problem._variable_parameters_values, outputs)
        if problem._variable_parameters_values is None:
            problem._last_variable_parameters_values = None
        else:
            problem._last_variable_parameters_values = np.array(
                problem._variable_parameters_values,
                copy=True,
            )
    else:
        pass


def resolve_rms_fmu_me_devices(
    problem: Any,
    accepted: bool,
) -> float | None:
    """Accept or reject every prepared RMS FMU ME step in registration order.

    :param problem: RMS problem owning the imported FMU adapters.
    :param accepted: Whether the owning RMS numerical step converged.
    :return: Always ``None`` because localization happens before Co-Simulation.
    """

    evaluation_budget: FmuMeEvaluationBudget | None = (
        problem._fmu_me_evaluation_budget
    )
    if evaluation_budget is not None:
        pass
    else:
        raise RuntimeError("RMS FMI ME step lost its evaluation budget")
    adapter: RmsFmuMeDeviceAdapter
    for adapter in problem._fmu_me_adapters:
        outputs: dict[VarPowerFlowReferenceType, float] = adapter.resolve_step(
            accepted=accepted,
            evaluation_budget=evaluation_budget,
        )
        adapter.apply_outputs(problem._variable_parameters_values, outputs)
    if problem._variable_parameters_values is None:
        problem._last_variable_parameters_values = None
    else:
        problem._last_variable_parameters_values = np.array(
            problem._variable_parameters_values,
            copy=True,
        )
    problem._fmu_me_evaluation_budget = None
    return None


def _prepare_rms_fmu_me_state_event_retry(
    problem: Any,
    state_event_time_tolerance: float,
    state_event_max_iterations: int,
) -> float | None:
    """Localize the global first ME event before any CS device advances.

    Every ME candidate is inspected before the solver mutates a Co-Simulation
    FMU.  When a crossing exists, all ME candidates return to the accepted
    point and only simultaneous sources are armed for the shortened retry.

    :param problem: RMS problem owning the imported FMU adapters.
    :param state_event_time_tolerance: Positive event-time tolerance in seconds.
    :param state_event_max_iterations: Positive bisection iteration bound.
    :return: Global retry time when a state event precedes the candidate end.
    """

    adapter_count: int = len(problem._fmu_me_adapters)
    evaluation_budget: FmuMeEvaluationBudget | None = (
        problem._fmu_me_evaluation_budget
    )
    if evaluation_budget is not None:
        pass
    else:
        raise RuntimeError("RMS FMI ME localization lost its evaluation budget")
    localized_times: list[float | None] = [None] * adapter_count
    earliest_event_time: float | None = None
    adapter_index: int
    for adapter_index in range(adapter_count):
        adapter: RmsFmuMeDeviceAdapter = problem._fmu_me_adapters[
            adapter_index
        ]
        localized_time: float | None = (
            adapter.runtime_adapter.get_pending_state_event_time(
                time_tolerance=state_event_time_tolerance,
                maximum_iterations=state_event_max_iterations,
                evaluation_budget=evaluation_budget,
            )
        )
        localized_times[adapter_index] = localized_time
        if (
            localized_time is not None
            and (
                earliest_event_time is None
                or localized_time < earliest_event_time
            )
        ):
            earliest_event_time = localized_time
        else:
            pass

    if earliest_event_time is not None:
        # A shortened retry must start from one coherent accepted system point.
        for adapter_index in range(adapter_count):
            adapter = problem._fmu_me_adapters[adapter_index]
            adapter_event_time: float | None = localized_times[adapter_index]
            source_is_simultaneous: bool = (
                adapter_event_time is not None
                and (adapter_event_time - earliest_event_time)
                <= state_event_time_tolerance
            )
            if source_is_simultaneous:
                retry_event_time: float | None = earliest_event_time
            else:
                retry_event_time = None
            restored_outputs: dict[VarPowerFlowReferenceType, float] = (
                adapter.prepare_state_event_retry(retry_event_time, evaluation_budget)
            )
            adapter.apply_outputs(
                problem._variable_parameters_values,
                restored_outputs,
            )
        if problem._variable_parameters_values is None:
            problem._last_variable_parameters_values = None
        else:
            problem._last_variable_parameters_values = np.array(
                problem._variable_parameters_values,
                copy=True,
            )
    else:
        pass
    return earliest_event_time


def get_next_rms_fmu_me_event_time(
    problem: Any,
    t_prev: float,
    t_target: float,
) -> float | None:
    """Return the earliest FMI ME time event inside one RMS interval.

    :param problem: RMS problem owning the imported FMU adapters.
    :param t_prev: Previous accepted RMS time.
    :param t_target: Candidate RMS target time.
    :return: Earliest FMI event in ``(t_prev, t_target]`` or ``None``.
    """

    next_event_time: float | None = None
    adapter: RmsFmuMeDeviceAdapter
    for adapter in problem._fmu_me_adapters:
        adapter_event_time: float | None = (
            adapter.runtime_adapter.get_next_event_time()
        )
        if (
            adapter_event_time is not None
            and t_prev < adapter_event_time <= t_target
        ):
            if next_event_time is None or adapter_event_time < next_event_time:
                next_event_time = adapter_event_time
            else:
                pass
        else:
            pass
    return next_event_time


def close_rms_fmu_me_devices(problem: Any) -> None:
    """Close all imported FMU ME devices.

    :param problem: RMS problem instance.
    :return: None.
    """

    adapter: RmsFmuMeDeviceAdapter
    for adapter in problem._fmu_me_adapters:
        adapter.close()


def register_emt_fmu_me_device(problem: Any, device: Any, block: Block) -> None:
    """Register one imported FMU ME device in the active EMT problem.

    :param problem: EMT problem instance.
    :param device: VeraGrid device instance.
    :param block: Device EMT block used in the active problem.
    :return: None.
    """

    spec: Optional[FmuMeDeviceSpec] = _build_emt_me_runtime_spec(device, block)
    if spec is None:
        return
    else:
        adapter: EmtFmuMeDeviceAdapter
        for adapter in problem._fmu_me_adapters:
            if adapter.device.idtag == device.idtag:
                return
            else:
                pass

        output_param_indices: dict[VarPowerFlowReferenceType, int] = dict()
        uid_to_index = _get_event_param_index_map(problem)
        reference: VarPowerFlowReferenceType
        for reference, uid in spec.output_param_uids.items():
            output_param_indices[reference] = uid_to_index[uid]

        solver_policy: FmuMeSolverPolicy = _build_fmu_me_solver_policy(
            problem.options
        )
        problem._fmu_me_adapters.append(
            EmtFmuMeDeviceAdapter(
                problem=problem,
                device=device,
                spec=spec,
                output_param_indices=output_param_indices,
                solver_policy=solver_policy,
            )
        )


def queue_emt_fmu_me_device(problem: Any, device: Any, block: Block) -> None:
    """Queue one EMT device for FMU ME restoration after problem repartitioning.

    :param problem: EMT problem instance.
    :param device: VeraGrid device instance.
    :param block: Device EMT block used in the active problem.
    :return: None.
    """

    record = _read_emt_me_device_config(device)
    if record is None:
        return
    else:
        problem._pending_fmu_me_devices.append((device, block))


def finalize_emt_fmu_me_devices(problem: Any) -> None:
    """Restore all queued EMT FMU ME devices after the EMT problem is assembled.

    :param problem: EMT problem instance.
    :return: None.
    """

    pending_device: tuple[Any, Block]
    for pending_device in problem._pending_fmu_me_devices:
        register_emt_fmu_me_device(problem, pending_device[0], pending_device[1])


def restore_fmu_me_spec_from_record(record: FmuMeDeviceConfigRecord, block: Block, device_tpe: DeviceType) -> FmuMeDeviceSpec:
    """Rebuild the runtime FMU ME device specification from the stored record.

    :param record: Serialized FMU ME device record.
    :param block: Device block used in the active problem.
    :param device_tpe: VeraGrid device type.
    :return: Runtime FMU ME device specification.
    """

    parameter_values: tuple[FmuFloat64ParameterValue, ...] = (
        _resolve_parameter_values_from_block(
            parameter_bindings=record.parameter_bindings,
            block=block,
        )
    )
    event_params_by_name: dict[str, Var] = dict()
    event_parameter: Var
    for event_parameter in block.event_dict.keys():
        event_params_by_name[event_parameter.name] = event_parameter
    output_param_uids: dict[VarPowerFlowReferenceType, int] = dict()
    reference: VarPowerFlowReferenceType
    parameter_name: str
    for reference, parameter_name in record.output_param_names.items():
        resolved_event_parameter: Var | None = event_params_by_name.get(
            parameter_name,
            None,
        )
        if resolved_event_parameter is None:
            raise KeyError(parameter_name)
        else:
            output_param_uids[reference] = resolved_event_parameter.uid

    input_variable_names: list[str] = [""] * len(record.input_bindings)
    binding_index: int
    for binding_index in range(len(record.input_bindings)):
        input_variable_names[binding_index] = (
            record.input_bindings[binding_index].fmu_variable_name
        )
    output_variable_names: list[str] = [""] * len(record.output_bindings)
    for binding_index in range(len(record.output_bindings)):
        output_variable_names[binding_index] = (
            record.output_bindings[binding_index].fmu_variable_name
        )

    return build_fmu_me_device_spec(
        domain=FmuMeDomain(record.domain.value),
        config=build_import_config_from_record(
            FmuCsDeviceConfigRecord(
                domain=record.domain,
                fmu_path=record.fmu_path,
                preferred_mode=record.preferred_mode,
                input_bindings=record.input_bindings,
                output_bindings=record.output_bindings,
                output_defaults=record.output_defaults,
                output_param_names=record.output_param_names,
                extraction_root=record.extraction_root,
                communication_step=None,
                relative_tolerance=record.relative_tolerance,
                debug_logging=record.debug_logging,
            )
        ),
        device_tpe=device_tpe,
        input_variable_names=tuple(input_variable_names),
        output_variable_names=tuple(output_variable_names),
        worker_limits=record.worker_limits,
        maximum_event_iterations=record.maximum_event_iterations,
        input_bindings=record.input_bindings,
        output_bindings=record.output_bindings,
        output_defaults=record.output_defaults,
        output_param_uids=output_param_uids,
        configuration_float64_values=record.configuration_float64_values,
        configuration_uint64_values=record.configuration_uint64_values,
        parameter_values=parameter_values,
    )
