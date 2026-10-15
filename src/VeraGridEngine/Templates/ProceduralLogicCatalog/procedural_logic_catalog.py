# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Typed catalogue of standalone blocks backed by procedural logic."""

from __future__ import annotations

from typing import Dict, List, Sequence

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.enumerations import DeviceType, ProceduralLogicType
from VeraGridEngine.Utils.procedural_logic import (
    ConditionalDiagnosticLogic,
    DelayedSwitchEventLogic,
    DelayedThresholdLatchLogic,
    ProceduralLogicBase,
    ThreePhaseCarrierPwmLogic,
    ThreePhaseCarrierSampledModulationLogic,
    ValveStateLogic,
    aflipflop,
    delay,
    fixed_sample,
    flipflop,
    gradlim_const,
    hard_saturation,
    movingavg,
    pickup_dropoff,
    reset,
    sampled_value,
    startup_handover,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var


class ProceduralBlockParameterSpec:
    """Describe one editable numeric parameter owned by a procedural block.

    __slots__ keeps the catalogue metadata immutable in shape while normal
    properties expose the values without coupling the Engine to Qt models.
    """

    __slots__ = ("_name", "_default_value")

    def __init__(self, name: str, default_value: float) -> None:
        """Store one numeric parameter definition.

        :param name: Stable symbolic parameter name.
        :param default_value: Numeric value assigned to a fresh block.
        :return: None.
        """
        self._name: str = name
        self._default_value: float = default_value

    @property
    def name(self) -> str:
        """Return the stable symbolic parameter name.

        :return: Parameter name.
        """
        return self._name

    @property
    def default_value(self) -> float:
        """Return the value assigned when materializing a block.

        :return: Default numeric value.
        """
        return self._default_value


def build_procedural_block_description(logic_tpe: ProceduralLogicType) -> str:
    """Return the functional description of one procedural-logic type.

    :param logic_tpe: Procedural behaviour represented by a Library block.
    :return: Human-facing explanation of the retained or event-driven action.
    """
    if logic_tpe == ProceduralLogicType.FixedSample:
        description: str = "Samples a Boolean condition once during initialization and retains that result."
    elif logic_tpe == ProceduralLogicType.SampledValue:
        description = "Stores the latest input value and exposes it as a retained output."
    elif logic_tpe == ProceduralLogicType.TimeDelay:
        description = "Outputs the input value from a configurable amount of time in the past."
    elif logic_tpe == ProceduralLogicType.MovingAverage:
        description = "Averages the input over a configurable historical time window."
    elif logic_tpe == ProceduralLogicType.HardSaturation:
        description = "Clamps the input between configurable minimum and maximum values."
    elif logic_tpe == ProceduralLogicType.GradientLimiter:
        description = "Limits the input rate of change between configurable falling and rising rates."
    elif logic_tpe == ProceduralLogicType.FlipFlop:
        description = "Stores a Boolean state controlled by separate set and reset inputs."
    elif logic_tpe == ProceduralLogicType.AnalogFlipFlop:
        description = "Stores an analog input value when set and clears it when reset."
    elif logic_tpe == ProceduralLogicType.PickupDropoff:
        description = "Delays Boolean activation and deactivation by independent pickup and dropoff times."
    elif logic_tpe == ProceduralLogicType.DelayedThresholdLatch:
        description = "Latches a threshold comparison after its configured delay has elapsed."
    elif logic_tpe == ProceduralLogicType.ConditionalDiagnostic:
        description = "Emits a configured diagnostic event while its Boolean condition is active."
    elif logic_tpe == ProceduralLogicType.DelayedSwitchEvent:
        description = "Changes an external switch state after a guarded trigger and configurable delay."
    elif logic_tpe == ProceduralLogicType.ResetOnRisingEdge:
        description = "Captures the supplied reset value when the condition has a rising edge."
    elif logic_tpe == ProceduralLogicType.StartupHandover:
        description = "Changes from startup to enabled operation at a configurable simulation time."
    elif logic_tpe == ProceduralLogicType.ValveState:
        description = "Determines a semiconductor valve state from voltage, current, gate, and valve configuration."
    elif logic_tpe == ProceduralLogicType.ThreePhaseCarrierPwm:
        description = "Compares three modulation signals with a carrier to produce three PWM gate signals."
    elif logic_tpe == ProceduralLogicType.ThreePhaseCarrierSampledModulation:
        description = "Samples three modulation signals synchronously with the configured switching carrier."
    else:
        description = f"Applies the {logic_tpe.value} procedural-logic behaviour."
    return description


class ProceduralBlockTemplateDescriptor:
    """Describe one native, draggable procedural-logic block template."""

    __slots__ = (
        "_logic_tpe",
        "_display_label",
        "_category_path",
        "_input_names",
        "_output_names",
        "_parameter_specs",
        "_requires_configuration",
        "_description",
    )

    def __init__(
            self,
            logic_tpe: ProceduralLogicType,
            display_label: str,
            category_path: Sequence[str],
            input_names: Sequence[str],
            output_names: Sequence[str],
            parameter_specs: Sequence[ProceduralBlockParameterSpec],
            requires_configuration: bool = False,
            description: str = "",
    ) -> None:
        """Store the immutable public surface of one block template.

        :param logic_tpe: Engine behavior implemented by the block.
        :param display_label: Human-facing Library label.
        :param category_path: Nested category path below ``Procedural logic``.
        :param input_names: Ordered visible input-port names.
        :param output_names: Ordered visible output-port names.
        :param parameter_specs: Ordered editable numeric parameters.
        :param requires_configuration: Whether Python code needs external identifiers.
        :param description: Human-facing explanation of the procedural behaviour.
        :return: None.
        """
        self._logic_tpe: ProceduralLogicType = logic_tpe
        self._display_label: str = display_label
        self._category_path: tuple[str, ...] = tuple(category_path)
        self._input_names: tuple[str, ...] = tuple(input_names)
        self._output_names: tuple[str, ...] = tuple(output_names)
        self._parameter_specs: tuple[ProceduralBlockParameterSpec, ...] = tuple(parameter_specs)
        self._requires_configuration: bool = requires_configuration
        if len(description) > 0:
            self._description: str = description
        else:
            self._description = build_procedural_block_description(logic_tpe=logic_tpe)

    @property
    def logic_tpe(self) -> ProceduralLogicType:
        """Return the concrete Engine procedural type.

        :return: Procedural logic type.
        """
        return self._logic_tpe

    @property
    def display_label(self) -> str:
        """Return the Library label.

        :return: Human-facing label.
        """
        return self._display_label

    @property
    def category_path(self) -> Sequence[str]:
        """Return the Library category path.

        :return: Immutable category sequence.
        """
        return self._category_path

    @property
    def input_names(self) -> Sequence[str]:
        """Return the ordered visible input names.

        :return: Immutable input-name sequence.
        """
        return self._input_names

    @property
    def output_names(self) -> Sequence[str]:
        """Return the ordered visible output names.

        :return: Immutable output-name sequence.
        """
        return self._output_names

    @property
    def parameter_specs(self) -> Sequence[ProceduralBlockParameterSpec]:
        """Return the ordered numeric parameter definitions.

        :return: Immutable parameter sequence.
        """
        return self._parameter_specs

    @property
    def requires_configuration(self) -> bool:
        """Return whether external identifiers must be completed by the user.

        :return: ``True`` for blocks that cannot infer external targets.
        """
        return self._requires_configuration

    @property
    def description(self) -> str:
        """Return the human-facing procedural behaviour description.

        :return: Functional description, or an empty string when unspecified.
        """
        return self._description

    @property
    def template_key(self) -> str:
        """Return the stable semantic identifier used by the editor.

        :return: Procedural logic code name.
        """
        return self._logic_tpe.value

    @property
    def search_text(self) -> str:
        """Return searchable labels, code names and port names.

        :return: Space-separated search text.
        """
        input_text: str = " ".join(self._input_names)
        output_text: str = " ".join(self._output_names)
        return (
            f"{self._display_label} {self._logic_tpe.value} {input_text} "
            f"{output_text} {self._description}"
        ).strip()

    @property
    def documentation_relative_path(self) -> str:
        """Return the documentation path relative to ``dyn_templates``.

        :return: Markdown documentation path.
        """
        return f"procedural_logic/{self._logic_tpe.value}.md"


def _build_procedural_logic_entry(
        logic_tpe: ProceduralLogicType,
        input_variables: Sequence[Var],
        retained_modes: Sequence[Var],
        parameter_variables: Sequence[Var],
) -> ProceduralLogicBase:
    """Build the Engine entry represented by one catalogue descriptor.

    :param logic_tpe: Concrete behavior being materialized.
    :param input_variables: Ordered block input variables.
    :param retained_modes: Ordered internal mode variables.
    :param parameter_variables: Ordered numeric runtime parameters.
    :return: Concrete procedural logic entry.
    """
    logic_entry: ProceduralLogicBase
    if logic_tpe == ProceduralLogicType.FixedSample:
        logic_entry = fixed_sample(output=retained_modes[0], when=input_variables[0])
    elif logic_tpe == ProceduralLogicType.SampledValue:
        logic_entry = sampled_value(output=retained_modes[0], source=input_variables[0])
    elif logic_tpe == ProceduralLogicType.HardSaturation:
        logic_entry = hard_saturation(
            output=retained_modes[0],
            u=input_variables[0],
            u_min=parameter_variables[0],
            u_max=parameter_variables[1],
        )
    elif logic_tpe == ProceduralLogicType.TimeDelay:
        logic_entry = delay(
            input_expr=input_variables[0],
            T=parameter_variables[0],
            output=retained_modes[0],
        )
    elif logic_tpe == ProceduralLogicType.MovingAverage:
        logic_entry = movingavg(
            input_expr=input_variables[0],
            Tdel=parameter_variables[0],
            Tlength=parameter_variables[1],
            output=retained_modes[0],
        )
    elif logic_tpe == ProceduralLogicType.GradientLimiter:
        logic_entry = gradlim_const(
            input_expr=input_variables[0],
            gradmin=parameter_variables[0],
            gradmax=parameter_variables[1],
            output=retained_modes[0],
        )
    elif logic_tpe == ProceduralLogicType.FlipFlop:
        logic_entry = flipflop(
            boolset=input_variables[0],
            boolreset=input_variables[1],
            output=retained_modes[0],
        )
    elif logic_tpe == ProceduralLogicType.AnalogFlipFlop:
        logic_entry = aflipflop(
            x=input_variables[0],
            boolset=input_variables[1],
            boolreset=input_variables[2],
            output=retained_modes[0],
        )
    elif logic_tpe == ProceduralLogicType.PickupDropoff:
        logic_entry = pickup_dropoff(
            output=retained_modes[0],
            boolexpr=input_variables[0],
            Tpick=parameter_variables[0],
            Tdrop=parameter_variables[1],
        )
    elif logic_tpe == ProceduralLogicType.ResetOnRisingEdge:
        logic_entry = reset(
            var=retained_modes[0],
            rst=input_variables[0],
            val=input_variables[1],
        )
    elif logic_tpe == ProceduralLogicType.DelayedThresholdLatch:
        logic_entry = DelayedThresholdLatchLogic(
            monitored_var_name=input_variables[0].name,
            mode_var_name=retained_modes[0].name,
            threshold=0.0,
            delay=0.0,
            reset_delay=None,
            name=retained_modes[0].name,
        )
    elif logic_tpe == ProceduralLogicType.StartupHandover:
        logic_entry = startup_handover(
            mode=retained_modes[0],
            t_enable=parameter_variables[0],
        )
    elif logic_tpe == ProceduralLogicType.ConditionalDiagnostic:
        logic_entry = ConditionalDiagnosticLogic(
            condition_expr=input_variables[0],
            message="Diagnostic condition became true.",
            initialization_only=False,
            name="conditional_diagnostic",
        )
    elif logic_tpe == ProceduralLogicType.DelayedSwitchEvent:
        logic_entry = DelayedSwitchEventLogic(
            output_var_name=retained_modes[0].name,
            guard_expr=input_variables[0],
            trigger_expr=input_variables[1],
            delay_expr=parameter_variables[0],
            target_device_idtag="",
            target_switch_idtag="",
            target_terminal_index=0,
            initial_closed=False,
            command_closed=True,
            name="delayed_switch_event",
        )
    elif logic_tpe == ProceduralLogicType.ValveState:
        logic_entry = ValveStateLogic(
            mode_var_name=retained_modes[0].name,
            valve_type_var_name=parameter_variables[0].name,
            gate_var_name=parameter_variables[1].name,
            antiparallel_var_name=parameter_variables[2].name,
            voltage_eps_var_name=parameter_variables[3].name,
            current_eps_var_name=parameter_variables[4].name,
            valve_voltage_var_name=input_variables[0].name,
            valve_current_var_name=input_variables[1].name,
            name=retained_modes[0].name,
        )
    elif logic_tpe == ProceduralLogicType.ThreePhaseCarrierPwm:
        logic_entry = ThreePhaseCarrierPwmLogic(
            mod_a_var_name=input_variables[0].name,
            mod_b_var_name=input_variables[1].name,
            mod_c_var_name=input_variables[2].name,
            gate_a_mode_var_name=retained_modes[0].name,
            gate_b_mode_var_name=retained_modes[1].name,
            gate_c_mode_var_name=retained_modes[2].name,
            omega_sw_var_name=parameter_variables[0].name,
            carrier_phase_var_name=parameter_variables[1].name,
            name="three_phase_carrier_pwm",
        )
    elif logic_tpe == ProceduralLogicType.ThreePhaseCarrierSampledModulation:
        logic_entry = ThreePhaseCarrierSampledModulationLogic(
            mod_a_var_name=input_variables[0].name,
            mod_b_var_name=input_variables[1].name,
            mod_c_var_name=input_variables[2].name,
            sample_a_mode_var_name=retained_modes[0].name,
            sample_b_mode_var_name=retained_modes[1].name,
            sample_c_mode_var_name=retained_modes[2].name,
            omega_sw_var_name=parameter_variables[0].name,
            carrier_phase_var_name=parameter_variables[1].name,
            name="three_phase_carrier_sampled_modulation",
        )
    else:
        raise ValueError(f"Unsupported procedural block type '{logic_tpe.value}'")
    return logic_entry


def build_procedural_block_catalog_template(
        descriptor: ProceduralBlockTemplateDescriptor,
        var_factory: VarFactory,
        name: str | None = None,
) -> EmtModelTemplate:
    """Materialize a fresh standalone block from one procedural descriptor.

    Procedural outputs are runtime modes. Each visible output is therefore an
    algebraic alias of its internal mode, matching the established generated
    Basic Block Catalog pattern while keeping connection ports ordinary DAE
    variables.

    :param descriptor: Typed procedural block definition.
    :param var_factory: Factory allocating fresh symbolic identities.
    :param name: Optional explicit template name.
    :return: Materialized template ready for the Dynamic Editor canvas.
    """
    if name is None:
        template_name: str = descriptor.template_key
    else:
        template_name = name

    # Allocate all visible ports before building the retained output surface.
    input_variables: List[Var] = list()
    input_name: str
    for input_name in descriptor.input_names:
        input_variables.append(var_factory.add_var(f"{input_name}_{template_name}"))

    output_variables: List[Var] = list()
    retained_modes: List[Var] = list()
    output_name: str
    for output_name in descriptor.output_names:
        output_variables.append(var_factory.add_var(f"{output_name}_{template_name}"))
        retained_modes.append(var_factory.add_var(f"retained_{output_name}_{template_name}"))

    # Numeric configuration belongs to event_dict so Block Properties exposes
    # it as an editable parameter instead of embedding values in GUI code.
    parameter_variables: List[Var] = list()
    event_parameters: Dict[Var, Expr | Const] = dict()
    parameter_spec: ProceduralBlockParameterSpec
    for parameter_spec in descriptor.parameter_specs:
        parameter_var: Var = var_factory.add_var(f"{parameter_spec.name}_{template_name}")
        parameter_variables.append(parameter_var)
        event_parameters[parameter_var] = var_factory.add_const(parameter_spec.default_value)

    # Every retained output starts from a deterministic value. The procedural
    # updater may replace it after the first accepted solver boundary.
    mode_parameters: Dict[Var, Expr | Const] = dict()
    retained_mode: Var
    for retained_mode in retained_modes:
        mode_parameters[retained_mode] = var_factory.add_const(0.0)

    # Expose retained values through normal algebraic output variables so all
    # existing graphical wiring and serialization paths remain unchanged.
    algebraic_equations: List[Expr] = list()
    output_index: int
    for output_index in range(len(output_variables)):
        algebraic_equations.append(output_variables[output_index] - retained_modes[output_index])

    logic_entry: ProceduralLogicBase = _build_procedural_logic_entry(
        logic_tpe=descriptor.logic_tpe,
        input_variables=input_variables,
        retained_modes=retained_modes,
        parameter_variables=parameter_variables,
    )

    # The same symbolic template container is already used by the Basic branch
    # in RMS and EMT editors. DeviceType.NoDevice keeps the block mode-agnostic.
    template: EmtModelTemplate = EmtModelTemplate()
    template.tpe = DeviceType.NoDevice
    template.name = template_name
    template.block = Block(
        state_vars=list(),
        state_eqs=list(),
        algebraic_vars=list(output_variables),
        algebraic_eqs=algebraic_equations,
        diff_vars=list(),
        init_eqs=dict(),
        diff_init_eqs=dict(),
        in_vars=input_variables,
        out_vars=output_variables,
        event_dict=event_parameters,
        mode_dict=mode_parameters,
        procedural_logic=list((logic_entry,)),
        name=template_name,
    )
    return template
