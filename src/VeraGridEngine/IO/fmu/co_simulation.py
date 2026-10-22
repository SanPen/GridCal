# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
from VeraGridEngine.enumerations import FmuDeviceDomain as FmuCsDomain

from typing import Any, Optional

import numpy as np

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Parents.branch_parent import BranchParent
from VeraGridEngine.Devices.Parents.injection_parent import InjectionParent
from VeraGridEngine.enumerations import DeviceType, FmiVersion, ParamPowerFlowReferenceType, VarPowerFlowReferenceType
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
    FmuCsDeviceConfigRecord, build_import_config_from_record,
    load_fmu_cs_device_config, _resolve_parameter_values_from_block,
)
from VeraGridEngine.IO.fmu.model_description import (
    FmuInterfaceMode,
    FmuModelDescription,
    FmuVariableDescription,
    read_fmu_model_description,
)
from VeraGridEngine.IO.fmu.host import FmuRuntimeHost, open_fmu_runtime_host
from VeraGridEngine.IO.fmu.profile import (
    FmiThreeWorkerFloat64Profile,
    resolve_fmi_three_worker_float64_profile,
    validate_fmi_three_co_simulation_worker_profile,
)
from VeraGridEngine.IO.fmu.Elements.protocol import (
    FmiThreeWorkerDoStepResult,
)
from VeraGridEngine.IO.fmu.Elements.session import (
    FmiThreeNumericSession,
    open_fmi_three_numeric_session,
)
from VeraGridEngine.IO.fmu.worker_host import (
    FmiThreeWorkerHostLimits,
)




class FmuCsDeviceSpec:
    """Store the runtime data required to execute one FMU CS device.

    :param domain: VeraGrid domain using the FMU.
    :param config: Runtime configuration for the FMU.
    :param device_tpe: VeraGrid device type.
    :param input_bindings: VeraGrid-to-FMU bindings.
    :param output_bindings: FMU-to-VeraGrid bindings.
    :param output_defaults: Default output values before the FMU is stepped.
    :param output_param_uids: Event-parameter UIDs backing the FMU outputs.
    :param worker_limits: Explicit FMI 3 worker supervision policy, when used.
    :param float64_profile: Derived FMI 3 worker shape profile, when used.
    :param configuration_float64_values: Structural Float64 declarations.
    :param configuration_uint64_values: Structural UInt64 declarations.
    """

    __slots__ = (
        "domain",
        "config",
        "device_tpe",
        "input_bindings",
        "output_bindings",
        "output_defaults",
        "output_param_uids",
        "worker_limits",
        "float64_profile",
        "configuration_float64_values",
        "configuration_uint64_values",
        "parameter_values",
    )

    def __init__(
        self,
        domain: FmuCsDomain,
        config: FmuImportConfig,
        device_tpe: DeviceType,
        input_bindings: tuple[FmuRefBinding, ...],
        output_bindings: tuple[FmuRefBinding, ...],
        output_defaults: dict[VarPowerFlowReferenceType, float],
        output_param_uids: dict[VarPowerFlowReferenceType, int],
        worker_limits: FmiThreeWorkerHostLimits | None,
        float64_profile: FmiThreeWorkerFloat64Profile | None,
        configuration_float64_values: tuple[
            FmiThreeFloat64ConfigurationValue, ...
        ] = tuple(),
        configuration_uint64_values: tuple[
            FmiThreeUInt64ConfigurationValue, ...
        ] = tuple(),
        parameter_values: tuple[FmuFloat64ParameterValue, ...] = tuple(),
    ) -> None:
        """Store the runtime FMU device specification.

        :param domain: VeraGrid domain using the FMU.
        :param config: Runtime configuration for the FMU.
        :param device_tpe: VeraGrid device type.
        :param input_bindings: VeraGrid-to-FMU bindings.
        :param output_bindings: FMU-to-VeraGrid bindings.
        :param output_defaults: Default values before the first FMU sample.
        :param output_param_uids: Runtime output-parameter identifiers.
        :param worker_limits: Explicit FMI 3 worker supervision policy.
        :param float64_profile: Derived FMI 3 worker shape profile.
        :param configuration_float64_values: Structural Float64 declarations.
        :param configuration_uint64_values: Structural UInt64 declarations.
        :param parameter_values: Ephemeral values resolved from Block.parameters.
        :return: None.
        """

        self.domain: FmuCsDomain = domain
        self.config: FmuImportConfig = config
        self.device_tpe: DeviceType = device_tpe
        self.input_bindings: tuple[FmuRefBinding, ...] = input_bindings
        self.output_bindings: tuple[FmuRefBinding, ...] = output_bindings
        self.output_defaults: dict[VarPowerFlowReferenceType, float] = output_defaults
        self.output_param_uids: dict[VarPowerFlowReferenceType, int] = output_param_uids
        self.worker_limits: FmiThreeWorkerHostLimits | None = worker_limits
        self.float64_profile: FmiThreeWorkerFloat64Profile | None = float64_profile
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


class FmuCsDeviceAdapter:
    """Execute one FMU CS device inside a VeraGrid simulation step loop.

    :param problem: Owning simulation problem.
    :param device: VeraGrid device using the FMU.
    :param spec: Runtime FMU device specification.
    :param output_param_indices: Runtime-parameter indices receiving FMU outputs.
    """

    __slots__ = (
        "problem",
        "device",
        "spec",
        "output_param_indices",
        "runtime_host",
        "fmi_three_session",
        "last_time",
        "initialized",
        "last_outputs",
    )

    def __init__(
        self,
        problem: Any,
        device: Any,
        spec: FmuCsDeviceSpec,
        output_param_indices: dict[VarPowerFlowReferenceType, int],
    ) -> None:
        """Store the FMU CS runtime adapter.

        :return: None.
        """

        self.problem: Any = problem
        self.device: Any = device
        self.spec: FmuCsDeviceSpec = spec
        self.output_param_indices: dict[VarPowerFlowReferenceType, int] = output_param_indices
        self.runtime_host: FmuRuntimeHost | None = None
        self.fmi_three_session: FmiThreeNumericSession | None = None
        self.last_time: float = 0.0
        self.initialized: bool = False
        self.last_outputs: dict[VarPowerFlowReferenceType, float] = dict()

    def _build_input_values(self, x_snapshot: np.ndarray) -> dict[str, float]:
        """Collect the FMU input values from the current VeraGrid snapshot.

        :param x_snapshot: Current accepted state snapshot.
        :return: FMU input values.
        """

        input_values: dict[str, float] = dict()
        binding: FmuRefBinding
        for binding in self.spec.input_bindings:
            if self.spec.domain == FmuCsDomain.RMS:
                value: float = _get_rms_input_value(self.problem, self.device, binding.reference, x_snapshot)
            else:
                value = _get_emt_input_value(self.problem, self.device, binding.reference, x_snapshot)
            input_values[binding.fmu_variable_name] = value
        return input_values

    def _build_fmi_three_writable_values(
        self,
        x_snapshot: np.ndarray,
    ) -> tuple[float, ...]:
        """Build the ordered scalar values required by the isolated session.

        :param x_snapshot: Current accepted VeraGrid state snapshot.
        :return: Values ordered exactly like ``spec.input_bindings``.
        """

        writable_values: list[float] = [0.0] * len(self.spec.input_bindings)
        binding_index: int
        for binding_index in range(len(self.spec.input_bindings)):
            binding: FmuRefBinding = self.spec.input_bindings[binding_index]
            if self.spec.domain == FmuCsDomain.RMS:
                writable_values[binding_index] = _get_rms_input_value(
                    self.problem,
                    self.device,
                    binding.reference,
                    x_snapshot,
                )
            else:
                writable_values[binding_index] = _get_emt_input_value(
                    self.problem,
                    self.device,
                    binding.reference,
                    x_snapshot,
                )
        return tuple(writable_values)

    def _map_fmi_three_readable_values(
        self,
        readable_values: tuple[float, ...],
    ) -> dict[VarPowerFlowReferenceType, float]:
        """Map ordered isolated readings onto VeraGrid output references.

        :param readable_values: Values ordered like ``spec.output_bindings``.
        :return: Scalar readings indexed by VeraGrid reference.
        :raises RuntimeError: If the session violates the bound output shape.
        """

        if len(readable_values) == len(self.spec.output_bindings):
            pass
        else:
            raise RuntimeError(
                "FMI 3 Co-Simulation readings do not match the device bindings"
            )
        mapped_values: dict[VarPowerFlowReferenceType, float] = dict()
        binding_index: int
        for binding_index in range(len(self.spec.output_bindings)):
            binding: FmuRefBinding = self.spec.output_bindings[binding_index]
            mapped_values[binding.reference] = float(
                readable_values[binding_index]
            )
        return mapped_values

    def _ensure_runtime(self, x_snapshot: np.ndarray, start_time: float) -> None:
        """Instantiate and initialize the FMU runtime the first time it is needed.

        :param x_snapshot: Current accepted state snapshot.
        :param start_time: Current simulation time.
        :return: None.
        """

        if self.runtime_host is None and self.fmi_three_session is None:
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
                # FMI 2 retains its established in-process runtime until its
                # isolation boundary is designed as an independent increment.
                self.runtime_host = open_fmu_runtime_host(self.spec.config)
                initialization_values: dict[str, float] = dict()
                parameter_value: FmuFloat64ParameterValue
                for parameter_value in self.spec.parameter_values:
                    initialization_values[parameter_value.variable_name] = (
                        parameter_value.value
                    )
                input_values: dict[str, float] = self._build_input_values(x_snapshot)
                input_name: str
                input_value: float
                for input_name, input_value in input_values.items():
                    if input_name in initialization_values:
                        raise RuntimeError(
                            "FMU parameter collides with a Co-Simulation input"
                        )
                    else:
                        initialization_values[input_name] = input_value
                self.runtime_host.initialize(
                    start_time=start_time,
                    start_values=initialization_values,
                )
            else:
                # Writable arrays remain fail-closed because an incomplete set
                # of device signals cannot provide the full native value vector.
                _reject_indexed_fmu_ref_bindings(
                    input_bindings=self.spec.input_bindings,
                    output_bindings=tuple(),
                )
                if self.spec.worker_limits is not None:
                    worker_limits: FmiThreeWorkerHostLimits = self.spec.worker_limits
                else:
                    raise RuntimeError("FMI 3 CS device spec lost its worker limits")

                readable_variable_names: tuple[str, ...]
                readable_value_selectors: tuple[
                    FmiThreeFloat64SessionValueSelector, ...
                ]
                (
                    readable_variable_names,
                    readable_value_selectors,
                ) = resolve_fmi_three_float64_session_value_selectors(
                    self.spec.output_bindings
                )
                writable_variable_names: list[str] = [""] * len(
                    self.spec.input_bindings
                )
                binding_index: int
                for binding_index in range(len(self.spec.input_bindings)):
                    writable_variable_names[binding_index] = (
                        self.spec.input_bindings[binding_index].fmu_variable_name
                    )
                initialization_variable_names: list[str] = [""] * (
                    len(self.spec.parameter_values)
                    + len(writable_variable_names)
                )
                initial_float64_values: list[float] = [0.0] * len(
                    initialization_variable_names
                )
                parameter_index: int
                for parameter_index in range(len(self.spec.parameter_values)):
                    parameter_value = self.spec.parameter_values[parameter_index]
                    initialization_variable_names[parameter_index] = (
                        parameter_value.variable_name
                    )
                    initial_float64_values[parameter_index] = parameter_value.value
                input_start_values: tuple[float, ...] = (
                    self._build_fmi_three_writable_values(x_snapshot)
                )
                for binding_index in range(len(writable_variable_names)):
                    initialization_index: int = (
                        len(self.spec.parameter_values) + binding_index
                    )
                    initialization_variable_names[initialization_index] = (
                        writable_variable_names[binding_index]
                    )
                    initial_float64_values[initialization_index] = (
                        input_start_values[binding_index]
                    )

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

                session: FmiThreeNumericSession = open_fmi_three_numeric_session(
                    config=self.spec.config,
                    instance_name="veragrid-fmi-three-cs-device",
                    readable_variable_names=readable_variable_names,
                    writable_variable_names=tuple(writable_variable_names),
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
                    # Structural dimensions must settle before flattened
                    # Float64 structural arrays are validated and written.
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
                    readable_values: tuple[float, ...] = (
                        session.initialize_co_simulation_and_read(
                            start_time=start_time,
                            stop_time=None,
                            relative_tolerance=self.spec.config.relative_tolerance,
                            initial_writable_float64_values=tuple(
                                initial_float64_values
                            ),
                        )
                    )
                except Exception:
                    session.close()
                    raise
                self.fmi_three_session = session
                self.last_outputs = self._map_fmi_three_readable_values(
                    readable_values
                )
            self.initialized = True
            self.last_time = start_time
        else:
            pass

    def _read_outputs(self) -> dict[VarPowerFlowReferenceType, float]:
        """Read the FMU outputs or fall back to the configured defaults.

        :return: Output values indexed by VeraGrid reference.
        """

        if self.runtime_host is not None:
            variable_names: list[str] = list()
            binding: FmuRefBinding
            for binding in self.spec.output_bindings:
                variable_names.append(binding.fmu_variable_name)
            runtime_values: dict[str, float] = self.runtime_host.get_real(variable_names)

            output_values: dict[VarPowerFlowReferenceType, float] = dict()
            for binding in self.spec.output_bindings:
                output_values[binding.reference] = float(runtime_values[binding.fmu_variable_name])
            return output_values
        else:
            if self.fmi_three_session is not None:
                return dict(self.last_outputs)
            else:
                return dict(self.spec.output_defaults)

    def initialize_outputs(self, time_value: float, x_snapshot: np.ndarray) -> dict[VarPowerFlowReferenceType, float]:
        """Initialize the FMU and return its first output sample.

        :param time_value: Current simulation time.
        :param x_snapshot: Current accepted state snapshot.
        :return: Output values indexed by VeraGrid reference.
        """

        self._ensure_runtime(x_snapshot, time_value)
        outputs: dict[VarPowerFlowReferenceType, float] = self._read_outputs()
        self.last_outputs = dict(outputs)
        return outputs

    def advance(self, current_time: float, step_size: float, x_snapshot: np.ndarray) -> dict[VarPowerFlowReferenceType, float]:
        """Advance the FMU one communication step and read the outputs.

        :param current_time: Current communication time.
        :param step_size: Requested communication step.
        :param x_snapshot: Current accepted state snapshot.
        :return: Output values indexed by VeraGrid reference.
        """

        self._ensure_runtime(x_snapshot, current_time)
        if self.runtime_host is not None:
            # Inputs are refreshed from the accepted network state before stepping the FMU.
            self.runtime_host.set_real(self._build_input_values(x_snapshot))
            if current_time > self.last_time + 1e-15:
                self.last_time = current_time
            else:
                pass
            self.runtime_host.do_step(current_time=current_time, step_size=step_size)
            self.last_time = current_time + step_size
            outputs = self._read_outputs()
            self.last_outputs = dict(outputs)
            return outputs
        else:
            if self.fmi_three_session is not None:
                step_result: FmiThreeWorkerDoStepResult
                readable_values: tuple[float, ...]
                step_result, readable_values = (
                    self.fmi_three_session.advance_co_simulation(
                        current_communication_point=current_time,
                        communication_step_size=step_size,
                        writable_float64_values=(
                            self._build_fmi_three_writable_values(x_snapshot)
                        ),
                        no_set_fmu_state_prior_to_current_point=True,
                    )
                )
                outputs: dict[VarPowerFlowReferenceType, float] = (
                    self._map_fmi_three_readable_values(readable_values)
                )
                self.last_time = step_result.last_successful_time
                self.last_outputs = dict(outputs)
                # The worker already rejected Event Mode, early return, and a
                # mismatched endpoint before returning this typed result.
                if step_result.terminate_simulation:
                    raise RuntimeError(
                        "FMI 3 Co-Simulation requested simulation termination"
                    )
                else:
                    return outputs
            else:
                return dict(self.spec.output_defaults)

    def apply_outputs(self, target: np.ndarray, outputs: dict[VarPowerFlowReferenceType, float]) -> None:
        """Write the FMU outputs into VeraGrid runtime-parameter storage.

        :param target: Runtime-parameter array.
        :param outputs: FMU outputs indexed by VeraGrid reference.
        :return: None.
        """

        reference: VarPowerFlowReferenceType
        for reference, value in outputs.items():
            target[self.output_param_indices[reference]] = float(value)

    def close(self) -> None:
        """Release the FMU runtime used by the adapter.

        :return: None.
        """

        if self.runtime_host is not None:
            if len(self.last_outputs) == 0:
                self.last_outputs = self._read_outputs()
            else:
                pass
            self.runtime_host.close()
            self.runtime_host = None
        else:
            pass
        if self.fmi_three_session is not None:
            self.fmi_three_session.close()
            self.fmi_three_session = None
        else:
            pass
        self.initialized = False


class CompositeEmtBoundaryUpdater:
    """Compose VeraGrid EMT boundary updates with imported FMU CS devices.

    :param problem: Owning EMT problem.
    :param adapters: FMU CS device adapters.
    """

    __slots__ = ("problem", "adapters", "initialized")

    def __init__(self, problem: Any, adapters: list[FmuCsDeviceAdapter]) -> None:
        """Store the boundary updater wrapper.

        :return: None.
        """

        self.problem: Any = problem
        self.adapters: list[FmuCsDeviceAdapter] = adapters
        self.initialized: bool = False

    def update(self, time_value: float, x_snapshot: np.ndarray, full_params: np.ndarray) -> None:
        """Execute the native boundary update and then step imported FMUs.

        :param time_value: Current simulation time.
        :param x_snapshot: Previous accepted solution.
        :param full_params: Runtime-parameter vector.
        :return: None.
        """

        # The native EMT boundary logic always runs first because it keeps internal line histories consistent.
        self.problem.emt_boundary_update(time_value, x_snapshot, full_params)
        if len(self.adapters) > 0:
            if self.initialized:
                adapter: FmuCsDeviceAdapter
                for adapter in self.adapters:
                    step_size: float = max(float(time_value - adapter.last_time), 0.0)
                    if step_size > 0.0:
                        outputs = adapter.advance(current_time=adapter.last_time, step_size=step_size, x_snapshot=x_snapshot)
                    else:
                        outputs = adapter._read_outputs()
                    adapter.apply_outputs(full_params, outputs)
            else:
                adapter = self.adapters[0]
                for adapter in self.adapters:
                    outputs = adapter.initialize_outputs(time_value, x_snapshot)
                    adapter.apply_outputs(full_params, outputs)
                self.initialized = True
        else:
            pass

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> float | None:
        """Forward the next forced event query to the native EMT problem.

        :param t_prev: Previous accepted time.
        :param t_target: Candidate target time.
        :return: Next forced event time if any.
        """

        return self.problem.get_next_forced_event_time(t_prev=t_prev, t_target=t_target)

    def close(self) -> None:
        """Release all FMU runtimes owned by the boundary updater.

        :return: None.
        """

        adapter: FmuCsDeviceAdapter
        for adapter in self.adapters:
            adapter.close()


def build_fmu_cs_device_spec(
    domain: FmuCsDomain,
    config: FmuImportConfig,
    device_tpe: DeviceType,
    input_bindings: tuple[FmuRefBinding, ...],
    output_bindings: tuple[FmuRefBinding, ...],
    output_defaults: dict[VarPowerFlowReferenceType, float] | None = None,
    output_param_uids: dict[VarPowerFlowReferenceType, int] | None = None,
    worker_limits: FmiThreeWorkerHostLimits | None = None,
    configuration_float64_values: tuple[
        FmiThreeFloat64ConfigurationValue, ...
    ] = tuple(),
    configuration_uint64_values: tuple[
        FmiThreeUInt64ConfigurationValue, ...
    ] = tuple(),
    parameter_values: tuple[FmuFloat64ParameterValue, ...] = tuple(),
) -> FmuCsDeviceSpec:
    """Build the validated runtime specification for one CS device.

    :param domain: VeraGrid domain that consumes the FMU.
    :param config: FMU runtime configuration.
    :param device_tpe: VeraGrid device type receiving the adapter.
    :param input_bindings: VeraGrid-to-FMU bindings.
    :param output_bindings: FMU-to-VeraGrid bindings.
    :param output_defaults: Defaults used before the first FMU sample.
    :param output_param_uids: Runtime output-parameter identifiers.
    :param worker_limits: Explicit FMI 3 worker supervision policy, when used.
    :param configuration_float64_values: Structural Float64 declarations.
    :param configuration_uint64_values: Structural UInt64 declarations.
    :param parameter_values: Ephemeral values resolved from Block.parameters.
    :return: Validated runtime specification with its derived worker profile.
    """

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
            validate_fmi_three_co_simulation_worker_profile(
                metadata=metadata,
                preferred_mode=resolved_mode,
                float64_profile=float64_profile,
            )
            if worker_limits is not None:
                pass
            else:
                raise ValueError(
                    "FMI 3 Co-Simulation devices require explicit worker limits"
                )
        else:
            raise ValueError(
                f"FMI {metadata.fmi_version} execution is not supported yet"
            )
    if resolved_mode == FmuInterfaceMode.CO_SIMULATION:
        reserved_parameter_names: list[str] = [""] * (
            len(input_bindings)
            + len(configuration_float64_values)
            + len(configuration_uint64_values)
        )
        reserved_name_index: int = 0
        reserved_input_binding: FmuRefBinding
        for reserved_input_binding in input_bindings:
            reserved_parameter_names[reserved_name_index] = (
                reserved_input_binding.fmu_variable_name
            )
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
        binding: FmuRefBinding
        for binding in input_bindings:
            if binding.fmu_variable_name in available_variables:
                if float64_profile is not None:
                    input_variable: FmuVariableDescription = metadata.get_variable(
                        binding.fmu_variable_name
                    )
                    if len(input_variable.dimensions) == 0:
                        pass
                    else:
                        raise RuntimeError(
                            "FMI 3 CS device array inputs require a complete "
                            "value provider"
                        )
                else:
                    pass
            else:
                raise KeyError(f"FMU variable {binding.fmu_variable_name!r} was not found in {config.fmu_path}")
        for binding in output_bindings:
            if binding.fmu_variable_name in available_variables:
                pass
            else:
                raise KeyError(f"FMU variable {binding.fmu_variable_name!r} was not found in {config.fmu_path}")

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
        return FmuCsDeviceSpec(
            domain=domain,
            config=config,
            device_tpe=device_tpe,
            input_bindings=input_bindings,
            output_bindings=output_bindings,
            output_defaults=resolved_output_defaults,
            output_param_uids=resolved_output_param_uids,
            worker_limits=worker_limits,
            float64_profile=float64_profile,
            configuration_float64_values=configuration_float64_values,
            configuration_uint64_values=configuration_uint64_values,
            parameter_values=parameter_values,
        )
    else:
        raise ValueError(f"Co-Simulation device blocks require a Co-Simulation FMU, got {resolved_mode.value}")


def _build_output_binding_block_data(
    vfactory: VarFactory,
    name: str,
    output_bindings: tuple[FmuRefBinding, ...],
    output_defaults: dict[VarPowerFlowReferenceType, float] | None,
) -> tuple[list[Var], list[Any], dict[VarPowerFlowReferenceType, Var], dict[Var, Const]]:
    """Build the symbolic output shell used to host an imported FMU device.

    :param vfactory: Variable factory used by the owning grid.
    :param name: Template name.
    :param output_bindings: FMU-to-VeraGrid bindings.
    :param output_defaults: Default values for each output reference.
    :return: Algebraic vars, equations, external mapping and event params.
    """

    defaults: dict[VarPowerFlowReferenceType, float]
    if output_defaults is None:
        defaults = dict()
    else:
        defaults = dict(output_defaults)

    algebraic_vars: list[Var] = list()
    algebraic_eqs: list[Any] = list()
    external_mapping: dict[VarPowerFlowReferenceType, Var] = dict()
    event_dict: dict[Var, Const] = dict()

    binding: FmuRefBinding
    for binding in output_bindings:
        reference_name: str = binding.reference.value.replace("-", "_")
        output_var: Var = vfactory.add_var(name=f"fmu_{reference_name}_{name}", reference=binding.reference)
        parameter_var: Var = vfactory.add_var(name=f"fmu_param_{reference_name}_{name}")
        default_value: float = float(defaults.get(binding.reference, 0.0))

        # The FMU output is injected through an event parameter so the native solver sees a normal symbolic variable.
        event_dict[parameter_var] = vfactory.add_const(default_value)
        algebraic_vars.append(output_var)
        algebraic_eqs.append(output_var - parameter_var)
        external_mapping[binding.reference] = output_var

    return algebraic_vars, algebraic_eqs, external_mapping, event_dict


def _build_template_block(
    vfactory: VarFactory,
    name: str,
    output_bindings: tuple[FmuRefBinding, ...],
    output_defaults: dict[VarPowerFlowReferenceType, float] | None,
    input_bindings: tuple[FmuRefBinding, ...] = tuple(),
) -> Block:
    """Build the symbolic shell block for an imported FMU device.

    :param vfactory: Variable factory used by the owning grid.
    :param name: Template name.
    :param output_bindings: FMU-to-VeraGrid bindings.
    :param output_defaults: Default values for each output reference.
    :param input_bindings: VeraGrid-to-FMU bindings materialized as shell inputs.
    :return: Symbolic shell block.
    """

    # Reject ambiguous directions before any variable is allocated so a failed
    # request leaves the owning VarFactory unchanged.
    reserved_references: set[VarPowerFlowReferenceType] = set()
    output_binding: FmuRefBinding
    for output_binding in output_bindings:
        reserved_references.add(output_binding.reference)
    input_binding: FmuRefBinding
    for input_binding in input_bindings:
        if input_binding.reference in reserved_references:
            raise ValueError(
                f"FMU reference {input_binding.reference.value!r} cannot be both an input and an output"
            )
        else:
            reserved_references.add(input_binding.reference)

    algebraic_vars: list[Var]
    algebraic_eqs: list[Any]
    external_mapping: dict[VarPowerFlowReferenceType, Var]
    event_dict: dict[Var, Const]
    algebraic_vars, algebraic_eqs, external_mapping, event_dict = _build_output_binding_block_data(
        vfactory=vfactory,
        name=name,
        output_bindings=output_bindings,
        output_defaults=output_defaults,
    )
    input_vars: list[Var] = [
        vfactory.add_var(
            name=f"fmu_input_{binding.reference.value.replace('-', '_')}_{name}",
            reference=binding.reference,
        )
        for binding in input_bindings
    ]
    binding_index: int
    for binding_index in range(len(input_bindings)):
        external_mapping[input_bindings[binding_index].reference] = input_vars[binding_index]

    return Block(
        algebraic_vars=algebraic_vars,
        algebraic_eqs=algebraic_eqs,
        in_vars=input_vars,
        out_vars=list(algebraic_vars),
        event_dict=event_dict,
        external_mapping=external_mapping,
        name=name,
    )


def build_rms_fmu_cs_injection_template(
    vfactory: VarFactory,
    config: FmuImportConfig,
    input_bindings: tuple[FmuRefBinding, ...],
    output_bindings: tuple[FmuRefBinding, ...],
    name: str,
    device_tpe: DeviceType = DeviceType.LoadDevice,
    output_defaults: dict[VarPowerFlowReferenceType, float] | None = None,
    worker_limits: FmiThreeWorkerHostLimits | None = None,
) -> RmsModelTemplate:
    """Build the symbolic RMS shell for one imported FMU CS device.

    :param vfactory: Variable factory used by the owning grid.
    :param config: FMU runtime configuration.
    :param input_bindings: VeraGrid-to-FMU bindings.
    :param output_bindings: FMU-to-VeraGrid bindings.
    :param name: Template name.
    :param device_tpe: VeraGrid device type.
    :param output_defaults: Default output values.
    :param worker_limits: Explicit FMI 3 worker supervision policy, when used.
    :return: RMS template wrapping the FMU shell block.
    """

    build_fmu_cs_device_spec(
        domain=FmuCsDomain.RMS,
        config=config,
        device_tpe=device_tpe,
        input_bindings=input_bindings,
        output_bindings=output_bindings,
        output_defaults=output_defaults,
        worker_limits=worker_limits,
    )
    template: RmsModelTemplate = RmsModelTemplate(name=name)
    template.tpe = device_tpe
    template.block = _build_template_block(vfactory, name, output_bindings, output_defaults)
    return template


def build_emt_fmu_cs_injection_template(
    vfactory: VarFactory,
    config: FmuImportConfig,
    input_bindings: tuple[FmuRefBinding, ...],
    output_bindings: tuple[FmuRefBinding, ...],
    name: str,
    device_tpe: DeviceType = DeviceType.LoadDevice,
    output_defaults: dict[VarPowerFlowReferenceType, float] | None = None,
    worker_limits: FmiThreeWorkerHostLimits | None = None,
) -> EmtModelTemplate:
    """Build the symbolic EMT shell for one imported FMU CS device.

    :param vfactory: Variable factory used by the owning grid.
    :param config: FMU runtime configuration.
    :param input_bindings: VeraGrid-to-FMU bindings.
    :param output_bindings: FMU-to-VeraGrid bindings.
    :param name: Template name.
    :param device_tpe: VeraGrid device type.
    :param output_defaults: Default output values.
    :param worker_limits: Explicit FMI 3 worker supervision policy, when used.
    :return: EMT template wrapping the FMU shell block.
    """

    build_fmu_cs_device_spec(
        domain=FmuCsDomain.EMT,
        config=config,
        device_tpe=device_tpe,
        input_bindings=input_bindings,
        output_bindings=output_bindings,
        output_defaults=output_defaults,
        worker_limits=worker_limits,
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


def _ensure_emt_external_mapping_keys(block: Block) -> None:
    """Populate the EMT shell external mapping with the phase keys expected by the EMT parser.

    :param block: EMT shell block used by an imported FMU device.
    :return: None.
    """

    for reference in (
            VarPowerFlowReferenceType.Vdc,
            VarPowerFlowReferenceType.i_N,
            VarPowerFlowReferenceType.i_A,
            VarPowerFlowReferenceType.i_B,
            VarPowerFlowReferenceType.i_C,
            VarPowerFlowReferenceType.P,
            VarPowerFlowReferenceType.Q,
            VarPowerFlowReferenceType.P_N,
            VarPowerFlowReferenceType.P_A,
            VarPowerFlowReferenceType.P_B,
            VarPowerFlowReferenceType.P_C,
            VarPowerFlowReferenceType.Q_N,
            VarPowerFlowReferenceType.Q_A,
            VarPowerFlowReferenceType.Q_B,
            VarPowerFlowReferenceType.Q_C,
            VarPowerFlowReferenceType.phi,
            VarPowerFlowReferenceType.phi_v,
            VarPowerFlowReferenceType.Vpk,
            VarPowerFlowReferenceType.Ipk,
            VarPowerFlowReferenceType.d_v_N,
            VarPowerFlowReferenceType.d_v_A,
            VarPowerFlowReferenceType.d_v_B,
            VarPowerFlowReferenceType.d_v_C,
    ):
        if reference in block.external_mapping:
            pass
        else:
            block.external_mapping[reference] = None


def _get_rms_input_value(problem: Any, device: Any, reference: VarPowerFlowReferenceType, x_snapshot: np.ndarray) -> float:
    """Read one RMS FMU input from the current network snapshot.

    :param problem: RMS problem instance.
    :param device: Device using the FMU.
    :param reference: Requested VeraGrid external reference.
    :param x_snapshot: Current accepted state snapshot.
    :return: Numeric input value.
    """

    if reference in {VarPowerFlowReferenceType.Vm, VarPowerFlowReferenceType.Va, VarPowerFlowReferenceType.Vdc}:
        bus_model: Block = device.bus.rms_model
        variable: Var = bus_model.external_mapping[reference]
        return float(x_snapshot[problem.uid2idx_vars[variable.uid]])
    else:
        raise KeyError(f"Unsupported RMS FMU input reference {reference.value!r}")


def _get_emt_input_value(problem: Any, device: Any, reference: VarPowerFlowReferenceType, x_snapshot: np.ndarray) -> float:
    """Read one EMT FMU input from the current network snapshot.

    :param problem: EMT problem instance.
    :param device: Device using the FMU.
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
        raise KeyError(f"Unsupported EMT FMU input reference {reference.value!r}")


def _read_device_config(device: Any, domain: FmuCsDomain) -> Any | None:
    """Read the serialized FMU device configuration from one VeraGrid device.

    :param device: VeraGrid device instance.
    :param domain: Runtime domain using the FMU.
    :return: Parsed device configuration when available.
    """

    if domain == FmuCsDomain.RMS:
        try:
            config_text: str = device.rms_fmu_import_config
        except AttributeError:
            if isinstance(device, InjectionParent) or isinstance(device, BranchParent):
                raise
            else:
                return None
    else:
        try:
            config_text = device.emt_fmu_import_config
        except AttributeError:
            if isinstance(device, InjectionParent) or isinstance(device, BranchParent):
                raise
            else:
                return None

    return load_fmu_cs_device_config(config_text)


def _build_runtime_spec(device: Any, block: Block, domain: FmuCsDomain) -> FmuCsDeviceSpec | None:
    """Rebuild the runtime specification from the device stored configuration.

    :param device: VeraGrid device instance.
    :param block: Device block used in the active problem.
    :param domain: Runtime domain using the FMU.
    :return: Runtime device specification when available.
    """

    record = _read_device_config(device, domain)
    if record is None:
        return None
    else:
        if record.domain == domain:
            return restore_fmu_cs_spec_from_record(record, block, device.device_type)
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


def register_rms_fmu_cs_device(problem: Any, device: Any, block: Block) -> None:
    """Register one imported FMU CS RMS device in the active RMS problem.

    :param problem: RMS problem instance.
    :param device: VeraGrid device instance.
    :param block: Device RMS block used in the active problem.
    :return: None.
    """

    spec: Optional[FmuCsDeviceSpec] = _build_runtime_spec(device, block, FmuCsDomain.RMS)
    if spec is None:
        return
    else:
        adapter: FmuCsDeviceAdapter
        for adapter in problem._fmu_cs_adapters:
            if adapter.device.idtag == device.idtag:
                return
            else:
                pass

        output_param_indices: dict[VarPowerFlowReferenceType, int] = dict()
        uid_to_index = _get_event_param_index_map(problem)
        reference: VarPowerFlowReferenceType
        for reference, uid in spec.output_param_uids.items():
            output_param_indices[reference] = uid_to_index[uid]
        problem._fmu_cs_adapters.append(
            FmuCsDeviceAdapter(problem=problem, device=device, spec=spec, output_param_indices=output_param_indices)
        )
        problem._fmu_cs_initialized = False


def initialize_rms_fmu_cs_devices(problem: Any, x_snapshot: np.ndarray, time_value: float = 0.0) -> None:
    """Initialize all imported FMU CS RMS devices before the time loop starts.

    :param problem: RMS problem instance.
    :param x_snapshot: Initial accepted state snapshot.
    :param time_value: Initial simulation time.
    :return: None.
    """

    if len(problem._fmu_cs_adapters) > 0:
        adapter: FmuCsDeviceAdapter
        for adapter in problem._fmu_cs_adapters:
            outputs: dict[VarPowerFlowReferenceType, float] = adapter.initialize_outputs(time_value, x_snapshot)
            adapter.apply_outputs(problem._variable_parameters_values, outputs)
            if problem._variable_parameters_values is None:
                problem._last_variable_parameters_values = None
            else:
                problem._last_variable_parameters_values = np.array(problem._variable_parameters_values, copy=True)
        problem._fmu_cs_initialized = True
    else:
        problem._fmu_cs_initialized = True


def align_rms_fmu_cs_device_output_parameters(problem: Any, x_snapshot: np.ndarray, time_value: float = 0.0) -> None:
    """
    Align RMS FMU CS output parameters with the current FMU outputs.

    The imported RMS FMU shell represents each FMU output with one algebraic
    equation of the form ``output_var - parameter_var = 0``. The parameter is
    seeded from the power-flow operating point before the FMU has had a chance to
    report its own initial outputs. A small FMU/default mismatch then appears as
    a DAE residual during the first RMS initialization check. Re-reading the FMU
    outputs and writing them back into the runtime parameter buffer removes that
    artificial mismatch before the solver judges the initial residual.

    :param problem: RMS problem instance.
    :param x_snapshot: Initial accepted state snapshot.
    :param time_value: Initial simulation time.
    :return: None.
    """

    if len(problem._fmu_cs_adapters) > 0:
        if problem._fmu_cs_initialized:
            adapter: FmuCsDeviceAdapter
            for adapter in problem._fmu_cs_adapters:
                outputs: dict[VarPowerFlowReferenceType, float] = adapter.initialize_outputs(time_value, x_snapshot)
                adapter.apply_outputs(problem._variable_parameters_values, outputs)
                if problem._variable_parameters_values is None:
                    problem._last_variable_parameters_values = None
                else:
                    problem._last_variable_parameters_values = np.array(problem._variable_parameters_values, copy=True)
        else:
            initialize_rms_fmu_cs_devices(problem=problem, x_snapshot=x_snapshot, time_value=time_value)
    else:
        pass


def advance_rms_fmu_cs_devices(problem: Any, time_value: float, x_snapshot: np.ndarray, step_size: float) -> bool:
    """Advance all imported FMU CS RMS devices for one solver step.

    :param problem: RMS problem instance.
    :param time_value: Current simulation time.
    :param x_snapshot: Current accepted state snapshot.
    :param step_size: RMS communication step.
    :return: Whether at least one registered CS adapter completed advancement.
    """

    if len(problem._fmu_cs_adapters) > 0:
        if problem._fmu_cs_initialized:
            pass
        else:
            initialize_rms_fmu_cs_devices(problem=problem, x_snapshot=x_snapshot, time_value=time_value)

        adapter: FmuCsDeviceAdapter
        for adapter in problem._fmu_cs_adapters:
            outputs = adapter.advance(current_time=time_value, step_size=step_size, x_snapshot=x_snapshot)
            adapter.apply_outputs(problem._variable_parameters_values, outputs)
            if problem._variable_parameters_values is None:
                problem._last_variable_parameters_values = None
            else:
                problem._last_variable_parameters_values = np.array(problem._variable_parameters_values, copy=True)
        return True
    else:
        return False


def close_rms_fmu_cs_devices(problem: Any) -> None:
    """Close all imported FMU CS RMS devices.

    :param problem: RMS problem instance.
    :return: None.
    """

    adapter: FmuCsDeviceAdapter
    for adapter in problem._fmu_cs_adapters:
        adapter.close()


def register_emt_fmu_cs_device(problem: Any, device: Any, block: Block) -> None:
    """Register one imported FMU CS EMT device in the active EMT problem.

    :param problem: EMT problem instance.
    :param device: VeraGrid device instance.
    :param block: Device EMT block used in the active problem.
    :return: None.
    """

    spec: Optional[FmuCsDeviceSpec] = _build_runtime_spec(device, block, FmuCsDomain.EMT)
    if spec is None:
        return
    else:
        adapter: FmuCsDeviceAdapter
        for adapter in problem._fmu_cs_adapters:
            if adapter.device.idtag == device.idtag:
                return
            else:
                pass

        output_param_indices: dict[VarPowerFlowReferenceType, int] = dict()
        uid_to_index = _get_event_param_index_map(problem)
        reference: VarPowerFlowReferenceType
        for reference, uid in spec.output_param_uids.items():
            output_param_indices[reference] = uid_to_index[uid]
        problem._fmu_cs_adapters.append(
            FmuCsDeviceAdapter(problem=problem, device=device, spec=spec, output_param_indices=output_param_indices)
        )


def queue_emt_fmu_cs_device(problem: Any, device: Any, block: Block) -> None:
    """Queue one EMT device for FMU CS restoration after problem repartitioning.

    :param problem: EMT problem instance.
    :param device: VeraGrid device instance.
    :param block: Device EMT block used in the active problem.
    :return: None.
    """

    record = _read_device_config(device, FmuCsDomain.EMT)
    if record is None:
        return
    else:
        problem._pending_fmu_cs_devices.append((device, block))


def finalize_emt_fmu_cs_devices(problem: Any) -> None:
    """Restore all queued EMT FMU CS devices after the EMT problem is assembled.

    :param problem: EMT problem instance.
    :return: None.
    """

    pending_device: tuple[Any, Block]
    for pending_device in problem._pending_fmu_cs_devices:
        register_emt_fmu_cs_device(problem, pending_device[0], pending_device[1])


def build_emt_boundary_updater(problem: Any) -> Any:
    """Build the effective EMT boundary updater for the active problem.

    :param problem: EMT problem instance.
    :return: Native EMT problem or FMU-aware boundary wrapper.
    """

    if len(problem._fmu_cs_adapters) > 0:
        return CompositeEmtBoundaryUpdater(problem, list(problem._fmu_cs_adapters))
    else:
        return problem


def restore_fmu_cs_spec_from_record(record: FmuCsDeviceConfigRecord, block: Block, device_tpe: DeviceType) -> FmuCsDeviceSpec:
    """Rebuild the runtime FMU device specification from the stored record.

    :param record: Serialized FMU device record.
    :param block: Device block used in the active problem.
    :param device_tpe: VeraGrid device type.
    :return: Runtime FMU device specification.
    """

    parameter_values: tuple[FmuFloat64ParameterValue, ...] = (
        _resolve_parameter_values_from_block(
            parameter_bindings=record.parameter_bindings,
            block=block,
        )
    )

    event_params_by_name: dict[str, Any] = dict()
    event_parameter: Any
    for event_parameter in block.event_dict.keys():
        event_params_by_name[event_parameter.name] = event_parameter

    output_param_uids: dict[VarPowerFlowReferenceType, int] = dict()
    reference: VarPowerFlowReferenceType
    for reference, parameter_name in record.output_param_names.items():
        event_parameter = event_params_by_name.get(parameter_name, None)
        if event_parameter is None:
            raise KeyError(parameter_name)
        else:
            output_param_uids[reference] = event_parameter.uid

    return build_fmu_cs_device_spec(
        domain=record.domain,
        config=build_import_config_from_record(record),
        device_tpe=device_tpe,
        input_bindings=record.input_bindings,
        output_bindings=record.output_bindings,
        output_defaults=dict(record.output_defaults),
        output_param_uids=output_param_uids,
        worker_limits=record.worker_limits,
        configuration_float64_values=record.configuration_float64_values,
        configuration_uint64_values=record.configuration_uint64_values,
        parameter_values=parameter_values,
    )
