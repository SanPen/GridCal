# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Bound consumer operations for one isolated FMI 3 numeric worker."""

from __future__ import annotations

from typing import cast

from VeraGridEngine.IO.fmu.Elements.bindings import (
    FmiThreeFloat64SessionValueSelector,
    FmiThreeFloat64BindingLayout,
    FmiThreeFloat64VariableCardinalityPlan,
    FmuImportConfig,
    resolve_fmi_three_configurable_float64_binding_layouts,
    resolve_fmi_three_configured_float64_binding_layout,
    resolve_fmi_three_configuration_float64_binding_layout,
    resolve_fmi_three_configuration_uint64_binding_references,
    resolve_fmi_three_initialization_float64_binding_layout,
    resolve_fmi_three_constant_float64_binding_layouts,
    resolve_fmi_three_scalar_binding_references,
    resolve_fmi_three_scalar_int32_binding_references,
)
from VeraGridEngine.IO.fmu.model_description import (
    FmuModelDescription,
    read_fmu_model_description,
)
from VeraGridEngine.IO.fmu.profile import (
    FmiThreeWorkerFloat64Profile,
    validate_fmi_three_co_simulation_worker_profile,
    validate_fmi_three_model_exchange_worker_profile,
)
from VeraGridEngine.IO.fmu.Elements.protocol import (
    FmiThreeWorkerCompletedIntegratorStepResult,
    FmiThreeWorkerDiscreteStatesResult,
    FmiThreeWorkerDoStepResult,
    FmiThreeWorkerFloat64Values,
    FmiThreeWorkerRequestKind,
    FmiThreeWorkerSetFloat64Request,
    FmiThreeWorkerSetInt32Request,
    validate_fmi_three_worker_float64_frame_capacity,
    validate_fmi_three_worker_initialization_frame_capacity,
    validate_fmi_three_worker_int32_frame_capacity,
    validate_fmi_three_worker_minimum_start_frame_capacity,
    validate_fmi_three_worker_uint64_configuration_frame_capacity,
)
from VeraGridEngine.IO.fmu.worker_host import (
    FmiThreeWorkerHost,
    FmiThreeWorkerHostLimits,
    prepare_fmi_three_worker_host,
)
from VeraGridEngine.enumerations import FmuInterfaceMode


class FmiThreeNumericSession:
    """Bind Float64 layouts and scalar Int32 references to one FMI 3 worker.

    The session retains only ordered value references and the worker owner.
    Model-description names are resolved once by
    :func:`open_fmi_three_numeric_session` and are not carried
    into the numerical loop.

    :param worker_host: Prepared worker host that owns process and staging state.
    :param configuration_layout: Ordered structural values applied before initialization.
    :param initialization_layout: Ordered parameters and inputs applied only during initialization.
    :param readable_layout: Ordered values sampled after stable transitions.
    :param readable_value_selectors: Optional device selections from the full
        readable vector.
    :param writable_layout: Ordered values applied before each step.
    :param initialization_int32_value_references: Ordered scalar Int32
        references applied during Initialization Mode.
    :param readable_int32_value_references: Ordered scalar Int32 references
        sampled in readable lifecycle states.
    :param writable_int32_value_references: Ordered scalar Int32 references
        applied before Co-Simulation steps or in Model Exchange Event Mode.
    """

    __slots__ = (
        "_worker_host",
        "_configuration_layout",
        "_initialization_layout",
        "_configuration_uint64_value_references",
        "_readable_layout",
        "_readable_value_selectors",
        "_writable_layout",
        "_initialization_int32_value_references",
        "_readable_int32_value_references",
        "_writable_int32_value_references",
        "_maximum_serialized_value_count",
    )

    def __init__(
        self,
        worker_host: FmiThreeWorkerHost,
        configuration_layout: FmiThreeFloat64BindingLayout,
        initialization_layout: FmiThreeFloat64BindingLayout,
        configuration_uint64_value_references: tuple[int, ...],
        readable_layout: FmiThreeFloat64BindingLayout,
        readable_value_selectors: tuple[
            FmiThreeFloat64SessionValueSelector, ...
        ],
        writable_layout: FmiThreeFloat64BindingLayout,
        maximum_serialized_value_count: int,
        initialization_int32_value_references: tuple[int, ...] = tuple(),
        readable_int32_value_references: tuple[int, ...] = tuple(),
        writable_int32_value_references: tuple[int, ...] = tuple(),
    ) -> None:
        """Store one bound worker without duplicating model metadata.

        :param worker_host: Worker host that owns process and staging state.
        :param configuration_layout: Ordered Configuration Mode write layout.
        :param initialization_layout: Ordered Initialization Mode write layout.
        :param configuration_uint64_value_references: Ordered structural UInt64
            references applied before initialization.
        :param readable_layout: Ordered scalar or array read layout.
        :param readable_value_selectors: Optional device value selectors aligned with
            the values returned to the consumer.
        :param writable_layout: Ordered scalar or array step-write layout.
        :param maximum_serialized_value_count: Maximum values in one native call.
        :param initialization_int32_value_references: Ordered scalar Int32
            initialization references.
        :param readable_int32_value_references: Ordered scalar Int32 read
            references.
        :param writable_int32_value_references: Ordered scalar Int32 runtime
            write references.
        :return: None.
        """

        self._worker_host: FmiThreeWorkerHost = worker_host
        self._configuration_layout: FmiThreeFloat64BindingLayout = (
            configuration_layout
        )
        self._initialization_layout: FmiThreeFloat64BindingLayout = (
            initialization_layout
        )
        self._configuration_uint64_value_references: tuple[int, ...] = tuple(
            configuration_uint64_value_references
        )
        self._readable_layout: FmiThreeFloat64BindingLayout = readable_layout
        self._readable_value_selectors: tuple[
            FmiThreeFloat64SessionValueSelector, ...
        ] = tuple(readable_value_selectors)
        self._writable_layout: FmiThreeFloat64BindingLayout = writable_layout
        self._initialization_int32_value_references: tuple[int, ...] = tuple(
            initialization_int32_value_references
        )
        self._readable_int32_value_references: tuple[int, ...] = tuple(
            readable_int32_value_references
        )
        self._writable_int32_value_references: tuple[int, ...] = tuple(
            writable_int32_value_references
        )
        self._maximum_serialized_value_count: int = (
            maximum_serialized_value_count
        )

    def supports_fmu_state_checkpoint(self) -> bool:
        """Return whether this session can save and restore native FMU state.

        :return: ``True`` when Get/Set/FreeFMUState is authenticated.
        """

        return self._worker_host.supports_fmu_state_checkpoint()

    def supports_serialized_fmu_state(self) -> bool:
        """Return whether this session declares FMI state serialization.

        :return: ``True`` when state byte serialization is authenticated.
        """

        return self._worker_host.supports_serialized_fmu_state()

    def needs_completed_integrator_step(self) -> bool:
        """Return the Model Exchange completed-step notification requirement.

        :return: Whether every accepted integrator step needs notification.
        :raises RuntimeError: If this session owns Co-Simulation.
        """

        return self._worker_host.needs_completed_integrator_step()

    def _validate_readable_value_selectors(
        self,
        readable_layout: FmiThreeFloat64BindingLayout,
    ) -> None:
        """Validate every selector against one prospective readable layout.

        :param readable_layout: Current or prospective complete session layout.
        :return: None.
        """

        selector_index: int
        for selector_index in range(len(self._readable_value_selectors)):
            self._readable_value_selectors[
                selector_index
            ].resolve_serialized_index(readable_layout)

    def _read_bound_values(self) -> tuple[float, ...]:
        """Read the fixed consumer layout after a stable transition.

        :return: Ordered finite Float64 values, or an empty tuple when the
            consumer declared no readable bindings.
        """

        if len(self._readable_layout.value_references) > 0:
            serialized_values: tuple[float, ...] = self._worker_host.get_float64(
                value_references=self._readable_layout.value_references,
                serialized_value_count=self._readable_layout.serialized_value_count,
            )
        else:
            serialized_values = tuple()
        return self._select_bound_readable_values(serialized_values)

    def read_int32_values(self) -> tuple[int, ...]:
        """Read the ordered scalar Int32 bindings from the shared worker.

        :return: Signed Int32 values in configured consumer order, or an empty
            tuple when the session has no readable Int32 binding.
        """

        if len(self._readable_int32_value_references) > 0:
            return self._worker_host.get_int32(
                value_references=self._readable_int32_value_references
            )
        else:
            return tuple()

    def write_int32_values(self, values: tuple[int, ...]) -> None:
        """Write the complete ordered scalar Int32 binding batch.

        The worker host enforces Co-Simulation Step Mode or Model Exchange
        Event Mode. Empty bindings accept only an empty value tuple.

        :param values: Signed values aligned with the bound writable Int32
            references.
        :return: None.
        """

        if len(self._writable_int32_value_references) > 0:
            validated_write: FmiThreeWorkerSetInt32Request = (
                FmiThreeWorkerSetInt32Request(
                    value_references=self._writable_int32_value_references,
                    values=values,
                    maximum_value_count=self._maximum_serialized_value_count,
                )
            )
            self._worker_host.set_int32(
                value_references=validated_write.value_references,
                values=validated_write.values,
            )
        else:
            if len(values) == 0:
                pass
            else:
                raise ValueError(
                    "FMI 3 session has no writable scalar Int32 bindings"
                )

    def _select_bound_readable_values(
        self,
        serialized_values: tuple[float, ...],
    ) -> tuple[float, ...]:
        """Apply configured consumer selectors to one complete native read.

        :param serialized_values: Values aligned with the readable layout.
        :return: Complete values or the configured selected subset.
        """

        if len(serialized_values) == self._readable_layout.serialized_value_count:
            pass
        else:
            raise ValueError(
                "FMI 3 readable value count differs from the bound layout"
            )
        if len(self._readable_value_selectors) > 0:
            selected_values: list[float] = [0.0] * len(
                self._readable_value_selectors
            )
            selector_index: int
            for selector_index in range(len(self._readable_value_selectors)):
                serialized_index: int = self._readable_value_selectors[
                    selector_index
                ].resolve_serialized_index(self._readable_layout)
                selected_values[selector_index] = serialized_values[
                    serialized_index
                ]
            return tuple(selected_values)
        else:
            return serialized_values

    def configure(self, configuration_float64_values: tuple[float, ...]) -> None:
        """Apply bound structural values before initialization.

        :param configuration_float64_values: Values aligned with the bound
            structural-parameter references.
        :return: None.
        """

        if len(self._configuration_layout.value_references) > 0:
            self._worker_host.configure_float64(
                value_references=self._configuration_layout.value_references,
                values=configuration_float64_values,
            )
        else:
            if len(configuration_float64_values) == 0:
                pass
            else:
                raise ValueError(
                    "FMI 3 session has no configured structural Float64 bindings"
                )

    def configure_uint64(
        self,
        configuration_uint64_values: tuple[int, ...],
    ) -> None:
        """Apply bound scalar UInt64 structural values before initialization.

        :param configuration_uint64_values: Values aligned with the bound
            structural UInt64 references.
        :return: None.
        """

        if len(self._configuration_uint64_value_references) > 0:
            # Resolve every consumer layout before entering native Configuration
            # Mode so an oversized requested shape cannot partially change the FMU.
            configured_configuration_layout: FmiThreeFloat64BindingLayout = (
                resolve_fmi_three_configured_float64_binding_layout(
                    layout=self._configuration_layout,
                    configuration_uint64_value_references=(
                        self._configuration_uint64_value_references
                    ),
                    configuration_uint64_values=configuration_uint64_values,
                    maximum_serialized_value_count=(
                        self._maximum_serialized_value_count
                    ),
                )
            )
            configured_readable_layout: FmiThreeFloat64BindingLayout = (
                resolve_fmi_three_configured_float64_binding_layout(
                    layout=self._readable_layout,
                    configuration_uint64_value_references=(
                        self._configuration_uint64_value_references
                    ),
                    configuration_uint64_values=configuration_uint64_values,
                    maximum_serialized_value_count=(
                        self._maximum_serialized_value_count
                    ),
                )
            )
            configured_initialization_layout: FmiThreeFloat64BindingLayout = (
                resolve_fmi_three_configured_float64_binding_layout(
                    layout=self._initialization_layout,
                    configuration_uint64_value_references=(
                        self._configuration_uint64_value_references
                    ),
                    configuration_uint64_values=configuration_uint64_values,
                    maximum_serialized_value_count=(
                        self._maximum_serialized_value_count
                    ),
                )
            )
            configured_writable_layout: FmiThreeFloat64BindingLayout = (
                resolve_fmi_three_configured_float64_binding_layout(
                    layout=self._writable_layout,
                    configuration_uint64_value_references=(
                        self._configuration_uint64_value_references
                    ),
                    configuration_uint64_values=configuration_uint64_values,
                    maximum_serialized_value_count=(
                        self._maximum_serialized_value_count
                    ),
                )
            )
            self._validate_readable_value_selectors(configured_readable_layout)
            self._worker_host.configure_uint64(
                value_references=self._configuration_uint64_value_references,
                values=configuration_uint64_values,
            )
            # Publish the prospective layouts only after the child confirms that
            # native exit from Configuration Mode completed successfully.
            self._configuration_layout = configured_configuration_layout
            self._initialization_layout = configured_initialization_layout
            self._readable_layout = configured_readable_layout
            self._writable_layout = configured_writable_layout
        else:
            if len(configuration_uint64_values) == 0:
                pass
            else:
                raise ValueError(
                    "FMI 3 session has no configured structural UInt64 bindings"
                )

    def _validate_bound_writable_values(
        self,
        writable_float64_values: tuple[float, ...],
    ) -> tuple[float, ...]:
        """Validate a complete bound write before any native side effect.

        :param writable_float64_values: Values aligned with the writable layout.
        :return: Finite values approved by the shared protocol body validator.
        """

        if (
            len(writable_float64_values)
            == self._writable_layout.serialized_value_count
        ):
            pass
        else:
            raise ValueError(
                "FMI 3 session writable Float64 values do not match the bound layout"
            )
        if len(self._writable_layout.value_references) > 0:
            validated_write: FmiThreeWorkerSetFloat64Request = (
                FmiThreeWorkerSetFloat64Request(
                    value_references=self._writable_layout.value_references,
                    values=writable_float64_values,
                    maximum_value_count=self._maximum_serialized_value_count,
                )
            )
            validated_values: tuple[float, ...] = validated_write.values
        else:
            validated_values = tuple()
        return validated_values

    def _initialize_bound_values(
        self,
        start_time: float,
        stop_time: float | None,
        relative_tolerance: float | None,
        initial_writable_float64_values: tuple[float, ...],
        initial_writable_int32_values: tuple[int, ...],
    ) -> None:
        """Enter the selected stable mode with prevalidated bound values.

        :param start_time: Finite simulation start time.
        :param stop_time: Optional finite stop time greater than start time.
        :param relative_tolerance: Optional finite positive relative tolerance.
        :param initial_writable_float64_values: Values aligned with writable bindings.
        :param initial_writable_int32_values: Signed values aligned with the
            initialization Int32 bindings.
        :return: None.
        """

        validated_values: tuple[float, ...] = self._validate_initialization_values(
            initial_writable_float64_values
        )
        if len(self._initialization_int32_value_references) > 0:
            validated_int32_write: FmiThreeWorkerSetInt32Request = (
                FmiThreeWorkerSetInt32Request(
                    value_references=(
                        self._initialization_int32_value_references
                    ),
                    values=initial_writable_int32_values,
                    maximum_value_count=self._maximum_serialized_value_count,
                )
            )
            validated_int32_values: tuple[int, ...] = (
                validated_int32_write.values
            )
        else:
            if len(initial_writable_int32_values) == 0:
                validated_int32_values = tuple()
            else:
                raise ValueError(
                    "FMI 3 session has no initialization scalar Int32 bindings"
                )
        self._worker_host.initialize(
            start_time=start_time,
            stop_time=stop_time,
            relative_tolerance=relative_tolerance,
            initial_float64_value_references=self._initialization_layout.value_references,
            initial_float64_values=validated_values,
            initial_int32_value_references=(
                self._initialization_int32_value_references
            ),
            initial_int32_values=validated_int32_values,
        )

    def _validate_initialization_values(
        self,
        initial_float64_values: tuple[float, ...],
    ) -> tuple[float, ...]:
        """Validate the complete Initialization Mode vector before native work.

        :param initial_float64_values: Parameters followed by initial inputs,
            aligned with the dedicated initialization layout.
        :return: Finite values approved by the shared protocol validator.
        """

        if (
            len(initial_float64_values)
            == self._initialization_layout.serialized_value_count
        ):
            pass
        else:
            raise ValueError(
                "FMI 3 session initialization values do not match the bound layout"
            )
        if len(self._initialization_layout.value_references) > 0:
            validated_request: FmiThreeWorkerSetFloat64Request = (
                FmiThreeWorkerSetFloat64Request(
                    value_references=(
                        self._initialization_layout.value_references
                    ),
                    values=initial_float64_values,
                    maximum_value_count=self._maximum_serialized_value_count,
                )
            )
            return validated_request.values
        else:
            return tuple()

    def initialize_co_simulation_and_read(
        self,
        start_time: float,
        stop_time: float | None,
        relative_tolerance: float | None,
        initial_writable_float64_values: tuple[float, ...],
        initial_writable_int32_values: tuple[int, ...] = tuple(),
    ) -> tuple[float, ...]:
        """Initialize Co-Simulation and return the initial readable sample.

        :param start_time: Finite simulation start time.
        :param stop_time: Optional finite stop time greater than start time.
        :param relative_tolerance: Optional finite positive relative tolerance.
        :param initial_writable_float64_values: Values aligned with the bound
            writable references.
        :param initial_writable_int32_values: Signed values aligned with the
            initialization Int32 references.
        :return: Initial readable values in consumer binding order.
        """

        if self._worker_host.get_interface_mode() == FmuInterfaceMode.CO_SIMULATION:
            pass
        else:
            raise RuntimeError(
                "FMI 3 session Co-Simulation initialization requires Co-Simulation"
            )
        self._initialize_bound_values(
            start_time=start_time,
            stop_time=stop_time,
            relative_tolerance=relative_tolerance,
            initial_writable_float64_values=initial_writable_float64_values,
            initial_writable_int32_values=initial_writable_int32_values,
        )
        return self._read_bound_values()

    def initialize_model_exchange_and_read(
        self,
        start_time: float,
        stop_time: float | None,
        relative_tolerance: float | None,
        initial_writable_float64_values: tuple[float, ...],
        initial_writable_int32_values: tuple[int, ...] = tuple(),
    ) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """Initialize Model Exchange and return states plus bound readings.

        :param start_time: Finite simulation start time.
        :param stop_time: Optional finite stop time greater than start time.
        :param relative_tolerance: Optional finite positive relative tolerance.
        :param initial_writable_float64_values: Values aligned with writable bindings.
        :param initial_writable_int32_values: Signed values aligned with the
            initialization Int32 references.
        :return: Continuous states followed by readable consumer values.
        """

        self.initialize_model_exchange(
            start_time=start_time,
            stop_time=stop_time,
            relative_tolerance=relative_tolerance,
            initial_writable_float64_values=initial_writable_float64_values,
            initial_writable_int32_values=initial_writable_int32_values,
        )
        # Preserve the historical continuous-only convenience API with one
        # mandatory initial update. Consumers that opt into bounded Event Mode
        # use the unit operations below and own the complete iteration.
        discrete_states_result: FmiThreeWorkerDiscreteStatesResult = (
            self.update_model_exchange_discrete_states()
        )
        if discrete_states_result.terminate_simulation:
            raise RuntimeError(
                "FMI 3 Model Exchange requested termination during initialization"
            )
        else:
            pass
        if discrete_states_result.discrete_states_need_update:
            raise RuntimeError(
                "FMI 3 Model Exchange requires multiple initial discrete-state iterations"
            )
        else:
            pass
        if discrete_states_result.next_event_time_defined:
            raise RuntimeError(
                "FMI 3 Model Exchange scheduled an unsupported time event"
            )
        else:
            pass
        self.enter_model_exchange_continuous_time_mode()
        return self.read_model_exchange_state_and_values()

    def initialize_model_exchange(
        self,
        start_time: float,
        stop_time: float | None,
        relative_tolerance: float | None,
        initial_writable_float64_values: tuple[float, ...],
        initial_writable_int32_values: tuple[int, ...] = tuple(),
    ) -> None:
        """Initialize Model Exchange and remain in its initial Event Mode.

        :param start_time: Finite simulation start time.
        :param stop_time: Optional finite stop time greater than start time.
        :param relative_tolerance: Optional finite positive relative tolerance.
        :param initial_writable_float64_values: Values aligned with writable bindings.
        :param initial_writable_int32_values: Signed values aligned with the
            initialization Int32 references.
        :return: None.
        """

        if self._worker_host.get_interface_mode() == FmuInterfaceMode.MODEL_EXCHANGE:
            pass
        else:
            raise RuntimeError(
                "FMI 3 session Model Exchange initialization requires Model Exchange"
            )
        self._initialize_bound_values(
            start_time=start_time,
            stop_time=stop_time,
            relative_tolerance=relative_tolerance,
            initial_writable_float64_values=initial_writable_float64_values,
            initial_writable_int32_values=initial_writable_int32_values,
        )

    def read_model_exchange_state_and_values(
        self,
    ) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """Read accepted states and bound values in Continuous-Time Mode.

        :return: Continuous states followed by readable consumer values.
        """

        if self._worker_host.get_interface_mode() == FmuInterfaceMode.MODEL_EXCHANGE:
            pass
        else:
            raise RuntimeError("FMI 3 session state read requires Model Exchange")
        state_values: tuple[float, ...] = self._worker_host.get_continuous_states()
        readable_values: tuple[float, ...] = self._read_bound_values()
        return state_values, readable_values

    def enter_model_exchange_event_mode(self) -> None:
        """Enter Event Mode for an event detected by the owning coordinator.

        :return: None.
        """

        if self._worker_host.get_interface_mode() == FmuInterfaceMode.MODEL_EXCHANGE:
            self._worker_host.enter_event_mode()
        else:
            raise RuntimeError("FMI 3 session Event Mode requires Model Exchange")

    def get_model_exchange_event_indicators(self) -> tuple[float, ...]:
        """Read event indicators for sign-change localization.

        :return: Ordered event-indicator values in model-description order.
        """

        if self._worker_host.get_interface_mode() == FmuInterfaceMode.MODEL_EXCHANGE:
            return self._worker_host.get_event_indicators()
        else:
            raise RuntimeError(
                "FMI 3 session event-indicator read requires Model Exchange"
            )

    def get_model_exchange_continuous_state_nominals(self) -> tuple[float, ...]:
        """Read continuous-state nominals for solver error scaling.

        :return: Ordered state nominal values.
        """

        if self._worker_host.get_interface_mode() == FmuInterfaceMode.MODEL_EXCHANGE:
            return self._worker_host.get_nominals_of_continuous_states()
        else:
            raise RuntimeError(
                "FMI 3 session state-nominal read requires Model Exchange"
            )

    def update_model_exchange_discrete_states(
        self,
    ) -> FmiThreeWorkerDiscreteStatesResult:
        """Execute one exact discrete-state transition in Event Mode.

        :return: Six-field native transition result.
        """

        if self._worker_host.get_interface_mode() == FmuInterfaceMode.MODEL_EXCHANGE:
            return self._worker_host.update_discrete_states()
        else:
            raise RuntimeError(
                "FMI 3 session discrete-state update requires Model Exchange"
            )

    def enter_model_exchange_continuous_time_mode(self) -> None:
        """Leave Model Exchange Event Mode after discrete-state convergence.

        :return: None.
        """

        if self._worker_host.get_interface_mode() == FmuInterfaceMode.MODEL_EXCHANGE:
            self._worker_host.enter_continuous_time_mode()
        else:
            raise RuntimeError(
                "FMI 3 session Continuous-Time Mode requires Model Exchange"
            )

    def evaluate_model_exchange(
        self,
        time_value: float,
        continuous_state_values: tuple[float, ...],
        writable_float64_values: tuple[float, ...],
    ) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """Evaluate derivatives and bound readings at one external solver point.

        This method does not advance time or integrate states. The caller owns
        the numerical method and supplies the complete accepted state vector.

        :param time_value: Finite time presented to the Model Exchange FMU.
        :param continuous_state_values: Complete continuous-state vector.
        :param writable_float64_values: Values aligned with writable bindings.
        :return: Derivatives followed by readable consumer values.
        """

        if self._worker_host.get_interface_mode() == FmuInterfaceMode.MODEL_EXCHANGE:
            pass
        else:
            raise RuntimeError(
                "FMI 3 session evaluation requires Model Exchange"
            )
        validated_states: FmiThreeWorkerFloat64Values = FmiThreeWorkerFloat64Values(
            values=continuous_state_values,
            maximum_value_count=self._maximum_serialized_value_count,
        )
        validated_writable_values: tuple[float, ...] = (
            self._validate_bound_writable_values(writable_float64_values)
        )
        # One child transaction preserves the native order while removing four
        # avoidable transport acknowledgements from every solver evaluation.
        derivative_values: tuple[float, ...]
        serialized_readable_values: tuple[float, ...]
        derivative_values, serialized_readable_values = (
            self._worker_host.evaluate_model_exchange(
                time_value=time_value,
                continuous_state_values=validated_states.values,
                writable_value_references=(
                    self._writable_layout.value_references
                ),
                writable_values=validated_writable_values,
                readable_value_references=(
                    self._readable_layout.value_references
                ),
                readable_value_count=(
                    self._readable_layout.serialized_value_count
                ),
            )
        )
        readable_values: tuple[float, ...] = self._select_bound_readable_values(
            serialized_readable_values
        )
        return derivative_values, readable_values

    def complete_model_exchange_integrator_step(
        self,
        no_set_fmu_state_prior_to_current_point: bool,
    ) -> FmiThreeWorkerCompletedIntegratorStepResult:
        """Forward one completed-step notification from the external solver.

        :param no_set_fmu_state_prior_to_current_point: FMI rollback guarantee.
        :return: Exact event-mode and termination requests from the FMU.
        """

        if self._worker_host.get_interface_mode() == FmuInterfaceMode.MODEL_EXCHANGE:
            pass
        else:
            raise RuntimeError(
                "FMI 3 session integrator notification requires Model Exchange"
            )
        completed_result: FmiThreeWorkerCompletedIntegratorStepResult = (
            self._worker_host.completed_integrator_step(
                no_set_fmu_state_prior_to_current_point=(
                    no_set_fmu_state_prior_to_current_point
                )
            )
        )
        return completed_result

    def advance_co_simulation(
        self,
        current_communication_point: float,
        communication_step_size: float,
        writable_float64_values: tuple[float, ...],
        no_set_fmu_state_prior_to_current_point: bool,
        writable_int32_values: tuple[int, ...] = tuple(),
    ) -> tuple[FmiThreeWorkerDoStepResult, tuple[float, ...]]:
        """Write bound values, complete one step, and return readable values.

        The native termination flag remains in the returned step result. This
        session deliberately does not decide whether one device request should
        stop the containing RMS or EMT simulation.

        :param current_communication_point: Exact accepted consumer time.
        :param communication_step_size: Positive requested communication step.
        :param writable_float64_values: Values aligned with writable bindings.
        :param writable_int32_values: Signed values aligned with the scalar
            Int32 writable bindings.
        :param no_set_fmu_state_prior_to_current_point: Consumer rollback
            guarantee passed unchanged to ``fmi3DoStep``.
        :return: Exact step result and readable values after the transition.
        """

        validated_values: tuple[float, ...] = self._validate_bound_writable_values(
            writable_float64_values
        )
        if len(self._writable_int32_value_references) > 0:
            validated_int32_write: FmiThreeWorkerSetInt32Request = (
                FmiThreeWorkerSetInt32Request(
                    value_references=self._writable_int32_value_references,
                    values=writable_int32_values,
                    maximum_value_count=self._maximum_serialized_value_count,
                )
            )
            validated_int32_values: tuple[int, ...] = (
                validated_int32_write.values
            )
        else:
            if len(writable_int32_values) == 0:
                validated_int32_values = tuple()
            else:
                raise ValueError(
                    "FMI 3 session has no writable scalar Int32 bindings"
                )
        step_result: FmiThreeWorkerDoStepResult = (
            self._worker_host.set_numeric_values_and_do_step(
                float64_value_references=(
                    self._writable_layout.value_references
                ),
                float64_values=validated_values,
                int32_value_references=self._writable_int32_value_references,
                int32_values=validated_int32_values,
                current_communication_point=current_communication_point,
                communication_step_size=communication_step_size,
                no_set_fmu_state_prior_to_current_point=(
                    no_set_fmu_state_prior_to_current_point
                ),
            )
        )
        readable_values: tuple[float, ...] = self._read_bound_values()
        return step_result, readable_values

    def close(self) -> None:
        """Release the worker process and private staging idempotently.

        :return: None.
        """

        self._worker_host.close()

    def save_checkpoint(self) -> None:
        """Replace the sole native checkpoint at the accepted stable point.

        :return: None.
        """

        self._worker_host.save_checkpoint()

    def restore_checkpoint(self) -> None:
        """Restore the sole native checkpoint without consuming it.

        :return: None.
        """

        self._worker_host.restore_checkpoint()

    def discard_checkpoint(self) -> None:
        """Free the sole native checkpoint without changing live FMU state.

        :return: None.
        """

        self._worker_host.discard_checkpoint()


def open_fmi_three_numeric_session(
    config: FmuImportConfig,
    instance_name: str,
    readable_variable_names: tuple[str, ...],
    writable_variable_names: tuple[str, ...],
    limits: FmiThreeWorkerHostLimits,
    float64_profile: FmiThreeWorkerFloat64Profile,
    initialization_variable_names: tuple[str, ...] | None = None,
    configuration_variable_names: tuple[str, ...] = tuple(),
    configuration_uint64_variable_names: tuple[str, ...] = tuple(),
    early_return_allowed: bool = False,
    readable_value_selectors: tuple[
        FmiThreeFloat64SessionValueSelector, ...
    ] = tuple(),
    readable_int32_variable_names: tuple[str, ...] = tuple(),
    writable_int32_variable_names: tuple[str, ...] = tuple(),
    initialization_int32_variable_names: tuple[str, ...] | None = None,
) -> FmiThreeNumericSession:
    """Resolve, stage, and start one bound FMI 3 numeric session.

    Binding validation completes before private staging is allocated. The same
    authoritative metadata instance is used for binding resolution and worker
    preparation, then discarded when only the ordered references remain.

    :param config: Source, interface preference, staging, and native options.
    :param instance_name: Non-empty identity passed to native instantiation.
    :param readable_variable_names: Ordered names sampled after transitions.
    :param writable_variable_names: Ordered input or tunable-parameter names.
    :param limits: Explicit finite worker supervision policy.
    :param float64_profile: Scalar, constant-array, or configurable-array
        profile.
    :param initialization_variable_names: Ordered parameters followed by inputs;
        ``None`` preserves the historical input-only initialization behavior.
    :param configuration_variable_names: Ordered structural Float64 names to
        assign through Configuration Mode before initialization.
    :param configuration_uint64_variable_names: Ordered structural UInt64 names
        to assign through Configuration Mode before initialization.
    :param early_return_allowed: Whether the session consumer can resume from
        a partial Co-Simulation step. Model Exchange must leave this disabled.
    :param readable_value_selectors: Optional selectors applied to the complete
        readable vector before it is returned to a device consumer.
    :param readable_int32_variable_names: Ordered scalar Int32 names sampled
        from the same native instance.
    :param writable_int32_variable_names: Ordered scalar Int32 input or tunable
        parameter names.
    :param initialization_int32_variable_names: Ordered scalar Int32 names for
        Initialization Mode; ``None`` reuses the writable Int32 names.
    :return: Started session in READY state. Any acquired worker ownership is
        closed before a START failure is propagated.
    """

    metadata: FmuModelDescription = read_fmu_model_description(config.fmu_path)
    interface_mode: FmuInterfaceMode = config.resolve_execution_mode(metadata)
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
            raise RuntimeError("FMI 3 session interface mode is unsupported")
    if metadata.instantiation_token is not None:
        instantiation_token: str = metadata.instantiation_token
    else:
        raise ValueError("FMI 3 worker metadata has no instantiation token")
    model_identifier: str = metadata.get_model_identifier(
        interface_mode
    )
    validate_fmi_three_worker_minimum_start_frame_capacity(
        instantiation_token=instantiation_token,
        model_identifier=model_identifier,
        instance_name=instance_name,
        interface_mode=interface_mode,
        maximum_frame_size=limits.maximum_frame_size,
    )
    readable_layout: FmiThreeFloat64BindingLayout
    writable_layout: FmiThreeFloat64BindingLayout
    configuration_layout: FmiThreeFloat64BindingLayout = (
        resolve_fmi_three_configuration_float64_binding_layout(
            metadata=metadata,
            configuration_variable_names=configuration_variable_names,
            maximum_serialized_value_count=(
                limits.maximum_float64_values_per_request
            ),
            float64_profile=float64_profile,
            interface_mode=interface_mode,
        )
    )
    configuration_uint64_value_references: tuple[int, ...] = (
        resolve_fmi_three_configuration_uint64_binding_references(
            metadata=metadata,
            configuration_variable_names=configuration_uint64_variable_names,
            float64_profile=float64_profile,
            interface_mode=interface_mode,
        )
    )
    if initialization_variable_names is None:
        resolved_initialization_variable_names: tuple[str, ...] = (
            writable_variable_names
        )
    else:
        resolved_initialization_variable_names = tuple(
            initialization_variable_names
        )
    initialization_layout: FmiThreeFloat64BindingLayout = (
        resolve_fmi_three_initialization_float64_binding_layout(
            metadata=metadata,
            initialization_variable_names=(
                resolved_initialization_variable_names
            ),
            maximum_serialized_value_count=(
                limits.maximum_float64_values_per_request
            ),
            float64_profile=float64_profile,
            interface_mode=interface_mode,
        )
    )
    if initialization_int32_variable_names is None:
        resolved_initialization_int32_variable_names: tuple[str, ...] = (
            writable_int32_variable_names
        )
    else:
        resolved_initialization_int32_variable_names = tuple(
            initialization_int32_variable_names
        )
    initialization_int32_value_references: tuple[int, ...]
    readable_int32_value_references: tuple[int, ...]
    writable_int32_value_references: tuple[int, ...]
    (
        initialization_int32_value_references,
        readable_int32_value_references,
        writable_int32_value_references,
    ) = resolve_fmi_three_scalar_int32_binding_references(
        metadata=metadata,
        initialization_variable_names=(
            resolved_initialization_int32_variable_names
        ),
        readable_variable_names=readable_int32_variable_names,
        writable_variable_names=writable_int32_variable_names,
        float64_profile=float64_profile,
        interface_mode=interface_mode,
    )
    if float64_profile == FmiThreeWorkerFloat64Profile.SCALAR:
        readable_value_references: tuple[int, ...]
        writable_value_references: tuple[int, ...]
        readable_value_references, writable_value_references = (
            resolve_fmi_three_scalar_binding_references(
                metadata=metadata,
                readable_variable_names=readable_variable_names,
                writable_variable_names=writable_variable_names,
                interface_mode=interface_mode,
            )
        )
        readable_cardinality_plans: list[
            FmiThreeFloat64VariableCardinalityPlan | None
        ] = [None] * len(readable_value_references)
        readable_index: int
        for readable_index in range(len(readable_value_references)):
            readable_cardinality_plans[readable_index] = (
                FmiThreeFloat64VariableCardinalityPlan(
                    value_reference=readable_value_references[readable_index],
                    dimension_sizes=tuple(),
                    dimension_value_references=tuple(),
                )
            )
        writable_cardinality_plans: list[
            FmiThreeFloat64VariableCardinalityPlan | None
        ] = [None] * len(writable_value_references)
        writable_index: int
        for writable_index in range(len(writable_value_references)):
            writable_cardinality_plans[writable_index] = (
                FmiThreeFloat64VariableCardinalityPlan(
                    value_reference=writable_value_references[writable_index],
                    dimension_sizes=tuple(),
                    dimension_value_references=tuple(),
                )
            )
        readable_layout = FmiThreeFloat64BindingLayout(
            value_references=readable_value_references,
            variable_cardinality_plans=cast(
                tuple[FmiThreeFloat64VariableCardinalityPlan, ...],
                tuple(readable_cardinality_plans),
            ),
            serialized_value_counts=(1,) * len(readable_value_references),
            serialized_value_count=len(readable_value_references),
        )
        writable_layout = FmiThreeFloat64BindingLayout(
            value_references=writable_value_references,
            variable_cardinality_plans=cast(
                tuple[FmiThreeFloat64VariableCardinalityPlan, ...],
                tuple(writable_cardinality_plans),
            ),
            serialized_value_counts=(1,) * len(writable_value_references),
            serialized_value_count=len(writable_value_references),
        )
    else:
        if float64_profile == FmiThreeWorkerFloat64Profile.CONSTANT_ARRAY:
            readable_layout, writable_layout = (
                resolve_fmi_three_constant_float64_binding_layouts(
                    metadata=metadata,
                    readable_variable_names=readable_variable_names,
                    writable_variable_names=writable_variable_names,
                    maximum_serialized_value_count=(
                        limits.maximum_float64_values_per_request
                    ),
                    interface_mode=interface_mode,
                )
            )
        else:
            if float64_profile == FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY:
                readable_layout, writable_layout = (
                    resolve_fmi_three_configurable_float64_binding_layouts(
                        metadata=metadata,
                        readable_variable_names=readable_variable_names,
                        writable_variable_names=writable_variable_names,
                        maximum_serialized_value_count=(
                            limits.maximum_float64_values_per_request
                        ),
                        interface_mode=interface_mode,
                    )
                )
            else:
                raise ValueError("Unsupported FMI 3 worker Float64 profile")
    validate_fmi_three_worker_initialization_frame_capacity(
        float64_value_reference_count=len(
            initialization_layout.value_references
        ),
        float64_serialized_value_count=(
            initialization_layout.serialized_value_count
        ),
        int32_value_reference_count=len(
            initialization_int32_value_references
        ),
        int32_value_count=len(initialization_int32_value_references),
        maximum_frame_size=limits.maximum_frame_size,
        maximum_value_count=limits.maximum_float64_values_per_request,
    )
    if len(configuration_layout.value_references) > 0:
        validate_fmi_three_worker_float64_frame_capacity(
            request_kind=FmiThreeWorkerRequestKind.CONFIGURE_FLOAT64,
            value_reference_count=len(configuration_layout.value_references),
            serialized_value_count=configuration_layout.serialized_value_count,
            maximum_frame_size=limits.maximum_frame_size,
            maximum_value_count=limits.maximum_float64_values_per_request,
        )
    else:
        pass
    if len(configuration_uint64_value_references) > 0:
        validate_fmi_three_worker_uint64_configuration_frame_capacity(
            value_count=len(configuration_uint64_value_references),
            maximum_frame_size=limits.maximum_frame_size,
            maximum_value_count=limits.maximum_float64_values_per_request,
        )
    else:
        pass
    if len(writable_layout.value_references) > 0:
        validate_fmi_three_worker_float64_frame_capacity(
            request_kind=FmiThreeWorkerRequestKind.SET_FLOAT64,
            value_reference_count=len(writable_layout.value_references),
            serialized_value_count=writable_layout.serialized_value_count,
            maximum_frame_size=limits.maximum_frame_size,
            maximum_value_count=limits.maximum_float64_values_per_request,
        )
    else:
        pass
    if len(readable_layout.value_references) > 0:
        validate_fmi_three_worker_float64_frame_capacity(
            request_kind=FmiThreeWorkerRequestKind.GET_FLOAT64,
            value_reference_count=len(readable_layout.value_references),
            serialized_value_count=readable_layout.serialized_value_count,
            maximum_frame_size=limits.maximum_frame_size,
            maximum_value_count=limits.maximum_float64_values_per_request,
        )
    else:
        pass
    if len(writable_int32_value_references) > 0:
        validate_fmi_three_worker_int32_frame_capacity(
            request_kind=FmiThreeWorkerRequestKind.SET_INT32,
            value_count=len(writable_int32_value_references),
            maximum_frame_size=limits.maximum_frame_size,
            maximum_value_count=limits.maximum_float64_values_per_request,
        )
    else:
        pass
    if len(readable_int32_value_references) > 0:
        validate_fmi_three_worker_int32_frame_capacity(
            request_kind=FmiThreeWorkerRequestKind.GET_INT32,
            value_count=len(readable_int32_value_references),
            maximum_frame_size=limits.maximum_frame_size,
            maximum_value_count=limits.maximum_float64_values_per_request,
        )
    else:
        pass
    if len(configuration_uint64_value_references) == 0:
        selector_index: int
        for selector_index in range(len(readable_value_selectors)):
            readable_value_selectors[selector_index].resolve_serialized_index(
                readable_layout
            )
    else:
        # Referenced dimensions can make a currently invalid selector valid.
        # The session validates the resized layout before the native write.
        pass
    worker_host: FmiThreeWorkerHost = (
        prepare_fmi_three_worker_host(
            metadata=metadata,
            interface_mode=interface_mode,
            staging_parent=config.extraction_root,
            limits=limits,
            float64_profile=float64_profile,
            early_return_allowed=early_return_allowed,
        )
    )
    session: FmiThreeNumericSession = (
        FmiThreeNumericSession(
            worker_host=worker_host,
            configuration_layout=configuration_layout,
            initialization_layout=initialization_layout,
            configuration_uint64_value_references=(
                configuration_uint64_value_references
            ),
            readable_layout=readable_layout,
            readable_value_selectors=readable_value_selectors,
            writable_layout=writable_layout,
            initialization_int32_value_references=(
                initialization_int32_value_references
            ),
            readable_int32_value_references=readable_int32_value_references,
            writable_int32_value_references=writable_int32_value_references,
            maximum_serialized_value_count=(
                limits.maximum_float64_values_per_request
            ),
        )
    )
    try:
        worker_host.start(
            instance_name=instance_name,
            visible=config.visible,
            debug_logging=config.debug_logging,
        )
        return session
    except BaseException:
        # A close failure means process death or staging cleanup is uncertain.
        # Let that diagnostic replace the START error instead of reporting a
        # clean factory rollback that the parent could not actually prove.
        session.close()
        raise
