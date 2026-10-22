# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Tuple, Sequence, List

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp
from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.enumerations import (
    BlockType,
    DerivativeInactiveBehavior,
    DerivativeOrder,
    DerivativeScalingMode,
    DeviceType,
    IntegratorBoundSource,
    IntegratorHoldMode,
    IntegratorResetMode,
    IntegratorSaturationMode,
    IntegratorScalingMode,
)
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import reset, sampled_value, selfix
from VeraGridEngine.Utils.procedural_logic_contract import ProceduralLogicEntryContract



# ----------------------------------------------------------------------------------------------------------------------
# Pre defined blocks
# ----------------------------------------------------------------------------------------------------------------------

def constant(var_factory: VarFactory, item_name: str = "") -> Block:
    """

    :param var_factory:
    :param item_name:
    :return:
    """
    name: str = "const_"
    y = var_factory.add_var(name + item_name)
    param = var_factory.add_var("param_" + item_name)

    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - param],
        out_vars=[y],
        event_dict={param: var_factory.add_const(0.0)},
        name="const",
        is_decomposable=False
    )

    return blk


def gain(var_factory: VarFactory, item_name: str = "") -> Block:
    """

    :param var_factory:
    :param item_name:
    :return:
    """
    inputs = [var_factory.add_var("inp_num_" + item_name)]
    name: str = "gain"
    y = var_factory.add_var(name + item_name)
    gain_param = var_factory.add_var("gain_param_" + item_name)

    expr: sym.Expr = gain_param * inputs[0]
    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - expr],
        out_vars=[y],
        in_vars=inputs,
        event_dict={gain_param: var_factory.add_const(0.0)},
        name="gain",
        is_decomposable=False
    )
    return blk


def variable(var_factory: VarFactory, name: str = "variable_", vartype: str = "vartype_") -> Tuple[sym.Var, Block]:
    """

    :param var_factory:
    :param name:
    :param vartype:
    :return:
    """
    y = var_factory.add_var(name)
    if vartype == 'state':
        blk = Block(state_vars=[y])
    else:
        blk = Block(algebraic_vars=[y])
    return y, blk



class AdderTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf):
        super().__init__(
            vf,
            params=[
                TemplateProp(name="minuend_inputs", units="", descr="Number of positive (added) inputs.", tpe=int, value=1),
                TemplateProp(name="subtrahend_inputs", units="", descr="Number of negative (subtracted) inputs.", tpe=int, value=1)
            ]
        )

    def eval(self) -> Block:
        minuend_inputs: int = self.get_value("minuend_inputs")
        subtrahend_inputs: int = self.get_value("subtrahend_inputs")

        return adder(self.vf, minuend_inputs, subtrahend_inputs)





def adder(var_factory: VarFactory, minuend_inputs: int = 1, subtrahend_inputs: int = 1, name: str = "sum") -> Block:
    """

    :param var_factory:
    :param item_name:
    :param minuend_inputs:
    :param subtrahend_inputs:
    :return:
    """
    equation: sym.Expr | None = None
    inputs: List[sym.Var] = list()

    for i in range(minuend_inputs):
        if not equation:
            var = var_factory.add_var("add_" + str(i))
            inputs.append(var)
            equation = var

        else:
            var = var_factory.add_var("add_" + str(i))
            inputs.append(var)
            equation += var

    for i in range(subtrahend_inputs):
        if not equation:
            var = var_factory.add_var("subtract_" + str(i))
            inputs.append(var)
            equation = - var
        else:
            var = var_factory.add_var("subtract_" + str(i))
            inputs.append(var)
            equation -= var


    y = var_factory.add_var("sum_out_")


    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - equation],
        in_vars=inputs,
        out_vars=[y],
        name="sum",
        is_decomposable=False
    )

    return blk

class ProductTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf):
        super().__init__(
            vf,
            params=[
                TemplateProp(name="divident_inputs", units="", descr="Number of dividend (multiplied) inputs.", tpe=int, value=1),
                TemplateProp(name="divisor_inputs", units="", descr="Number of divisor (divided) inputs.", tpe=int, value=1)
            ]
        )

    def eval(self) -> Block:
        divident_inputs: int = self.get_value("divident_inputs")
        divisor_inputs: int = self.get_value("divisor_inputs")

        return product(self.vf, divident_inputs, divisor_inputs)


class MinimumTemplate(TemplateDefinition):
    """Structural definition of a minimum block with configurable arity."""

    __slots__ = ()

    def __init__(self, vf: VarFactory) -> None:
        """Create a minimum-block definition with two inputs by default.

        :param vf: Variable factory receiving the generated block variables.
        :return: None.
        """
        TemplateDefinition.__init__(
            self,
            vf,
            list((
                TemplateProp(
                    name="input_count",
                    units="",
                    descr="Number of signals compared by the minimum operation.",
                    tpe=int,
                    value=2,
                ),
            )),
        )

    def eval(self) -> EmtModelTemplate:
        """Build the minimum block using the configured input count.

        :return: EMT template containing a minimum block with the requested input count.
        """
        input_count: int = int(self.get_value("input_count"))
        return build_extremum_template(
            var_factory=self.vf,
            input_count=input_count,
            block_type=BlockType.MIN,
        )


class MaximumTemplate(TemplateDefinition):
    """Structural definition of a maximum block with configurable arity."""

    __slots__ = ()

    def __init__(self, vf: VarFactory) -> None:
        """Create a maximum-block definition with two inputs by default.

        :param vf: Variable factory receiving the generated block variables.
        :return: None.
        """
        TemplateDefinition.__init__(
            self,
            vf,
            list((
                TemplateProp(
                    name="input_count",
                    units="",
                    descr="Number of signals compared by the maximum operation.",
                    tpe=int,
                    value=2,
                ),
            )),
        )

    def eval(self) -> EmtModelTemplate:
        """Build the maximum block using the configured input count.

        :return: EMT template containing a maximum block with the requested input count.
        """
        input_count: int = int(self.get_value("input_count"))
        return build_extremum_template(
            var_factory=self.vf,
            input_count=input_count,
            block_type=BlockType.MAX,
        )


def build_integrator_structural_properties() -> list[TemplateProp]:
    """Create the shared structural settings for canonical integrators.

    Numeric values such as ``K``, ``T`` and output bounds belong to the normal
    parameter table of the generated block. Only choices that alter ports or
    equations are exposed here as General structure options.

    :return: Fresh structural property definitions for one integrator builder.
    """
    return list((
        TemplateProp(
            name="scaling",
            units="",
            descr="Input scaling before integration: 1/s, K/s, or 1/(sT).",
            tpe=IntegratorScalingMode,
            value=IntegratorScalingMode.UNIT,
        ),
        TemplateProp(
            name="hold_input",
            units="",
            descr="Optionally freeze the state while an external hold signal is active.",
            tpe=IntegratorHoldMode,
            value=IntegratorHoldMode.NONE,
        ),
        TemplateProp(
            name="reset",
            units="",
            descr="Optionally reset the state to its initial value or to an external signal.",
            tpe=IntegratorResetMode,
            value=IntegratorResetMode.NONE,
        ),
        TemplateProp(
            name="output_saturation",
            units="",
            descr="Optional lower, upper, two-sided, or symmetric clamp on the output.",
            tpe=IntegratorSaturationMode,
            value=IntegratorSaturationMode.NONE,
        ),
        TemplateProp(
            name="bound_source",
            units="",
            descr="Read enabled output bounds from parameters or signal inputs.",
            tpe=IntegratorBoundSource,
            value=IntegratorBoundSource.PARAMETER,
        ),
        TemplateProp(
            name="scale_bounds_by_gain",
            units="",
            descr="Multiply every enabled output bound by one shared gain parameter K.",
            tpe=bool,
            value=False,
        ),
    ))


class IntegratorTemplate(TemplateDefinition):
    """Structural definition of the canonical configurable integrator."""

    __slots__ = ()

    def __init__(self, vf: VarFactory) -> None:
        """Create a unit integrator without optional control ports.

        :param vf: Variable factory receiving the generated block variables.
        :return: None.
        """
        TemplateDefinition.__init__(self, vf, build_integrator_structural_properties())

    def eval(self) -> EmtModelTemplate:
        """Build an integrator from the selected structural options.

        :return: EMT template containing the configurable integrator block.
        """
        scaling_mode: IntegratorScalingMode = self.get_value("scaling")
        hold_mode: IntegratorHoldMode = self.get_value("hold_input")
        reset_mode: IntegratorResetMode = self.get_value("reset")
        saturation_mode: IntegratorSaturationMode = self.get_value("output_saturation")
        bound_source: IntegratorBoundSource = self.get_value("bound_source")
        scale_bounds_by_gain: bool = bool(self.get_value("scale_bounds_by_gain"))
        return build_configurable_integrator_template(
            var_factory=self.vf,
            scaling_mode=scaling_mode,
            hold_mode=hold_mode,
            reset_mode=reset_mode,
            saturation_mode=saturation_mode,
            bound_source=bound_source,
            scale_bounds_by_gain=scale_bounds_by_gain,
            startup_freeze=False,
        )


class StartupFreezeIntegratorTemplate(TemplateDefinition):
    """Structural definition of an integrator frozen after initialization."""

    __slots__ = ()

    def __init__(self, vf: VarFactory) -> None:
        """Create a startup-freeze integrator with unit scaling by default.

        :param vf: Variable factory receiving the generated block variables.
        :return: None.
        """
        TemplateDefinition.__init__(self, vf, build_integrator_structural_properties())

    def eval(self) -> EmtModelTemplate:
        """Build a startup-freeze integrator from the structural options.

        :return: EMT template containing the startup-freeze integrator block.
        """
        scaling_mode: IntegratorScalingMode = self.get_value("scaling")
        hold_mode: IntegratorHoldMode = self.get_value("hold_input")
        reset_mode: IntegratorResetMode = self.get_value("reset")
        saturation_mode: IntegratorSaturationMode = self.get_value("output_saturation")
        bound_source: IntegratorBoundSource = self.get_value("bound_source")
        scale_bounds_by_gain: bool = bool(self.get_value("scale_bounds_by_gain"))
        return build_configurable_integrator_template(
            var_factory=self.vf,
            scaling_mode=scaling_mode,
            hold_mode=hold_mode,
            reset_mode=reset_mode,
            saturation_mode=saturation_mode,
            bound_source=bound_source,
            scale_bounds_by_gain=scale_bounds_by_gain,
            startup_freeze=True,
        )


def build_configurable_integrator_template(
        var_factory: VarFactory,
        scaling_mode: IntegratorScalingMode,
        hold_mode: IntegratorHoldMode,
        reset_mode: IntegratorResetMode,
        saturation_mode: IntegratorSaturationMode,
        bound_source: IntegratorBoundSource,
        scale_bounds_by_gain: bool,
        startup_freeze: bool,
) -> EmtModelTemplate:
    """Wrap one canonical configurable integrator in the builder contract.

    :param var_factory: Variable factory receiving the generated variables.
    :param scaling_mode: Input scaling applied before integration.
    :param hold_mode: Optional external hold-port selection.
    :param reset_mode: Optional reset behavior and port selection.
    :param saturation_mode: Output-only saturation selection.
    :param bound_source: Source used by enabled output bounds.
    :param scale_bounds_by_gain: Whether a shared K parameter scales the bounds.
    :param startup_freeze: Whether to freeze integration for an initial interval.
    :return: EMT template containing the requested integrator structure.
    """
    block: Block = build_configurable_integrator_block(
        var_factory=var_factory,
        scaling_mode=scaling_mode,
        hold_mode=hold_mode,
        reset_mode=reset_mode,
        saturation_mode=saturation_mode,
        bound_source=bound_source,
        scale_bounds_by_gain=scale_bounds_by_gain,
        startup_freeze=startup_freeze,
    )
    template: EmtModelTemplate = EmtModelTemplate(name=block.name)
    template.tpe = DeviceType.NoDevice
    template.block = block
    return template


def build_configurable_integrator_block(
        var_factory: VarFactory,
        scaling_mode: IntegratorScalingMode,
        hold_mode: IntegratorHoldMode,
        reset_mode: IntegratorResetMode,
        saturation_mode: IntegratorSaturationMode,
        bound_source: IntegratorBoundSource,
        scale_bounds_by_gain: bool,
        startup_freeze: bool,
) -> Block:
    """Build one integrator covering the useful legacy structural variants.

    Saturation deliberately clamps only the exposed output. The internal state
    continues integrating, matching the existing catalogue behavior; this is
    not an anti-windup or state-limited integrator. A time-constant structure
    uses the direct equation ``dx/dt = u/T`` and therefore makes invalid zero
    values visible instead of silently changing the requested dynamics.

    :param var_factory: Variable factory receiving the generated variables.
    :param scaling_mode: Input scaling applied before integration.
    :param hold_mode: Optional external hold-port selection.
    :param reset_mode: Optional reset behavior and port selection.
    :param saturation_mode: Output-only saturation selection.
    :param bound_source: Source used by enabled output bounds.
    :param scale_bounds_by_gain: Whether a shared K parameter scales the bounds.
    :param startup_freeze: Whether to freeze integration for an initial interval.
    :return: Configured ordinary symbolic block.
    """
    # The primary signal and state retain stable names so structural rebuilds
    # preserve existing connections when an independent option changes.
    input_signal: sym.Var = var_factory.add_var("integrator_input")
    state: sym.Var = var_factory.add_var("integrator_state")
    state_derivative: sym.Var = var_factory.add_diff_var(
        "d_integrator_state",
        base_var=state,
    )
    output_signal: sym.Var = var_factory.add_var("integrator_output")

    input_variables: List[sym.Var] = list((input_signal,))
    event_parameters: dict[sym.Var, sym.Expr | sym.Const] = dict()
    mode_parameters: dict[sym.Var, sym.Expr | sym.Const] = dict()
    initial_equations: dict[sym.Var, sym.Expr] = dict()
    procedural_logic_entries: list[ProceduralLogicEntryContract[sym.Expr]] = list()

    # Scaling changes the differential equation while keeping the external
    # signal interface stable. K and T remain normal editable parameters.
    if scaling_mode == IntegratorScalingMode.UNIT:
        state_equation: sym.Expr = input_signal
    elif scaling_mode == IntegratorScalingMode.GAIN:
        gain_parameter: sym.Var = var_factory.add_var("integrator_gain_K")
        event_parameters[gain_parameter] = var_factory.add_const(1.0, name="K")
        state_equation = gain_parameter * input_signal
    elif scaling_mode == IntegratorScalingMode.TIME_CONSTANT:
        time_constant: sym.Var = var_factory.add_var("integrator_time_constant_T")
        event_parameters[time_constant] = var_factory.add_const(1.0, name="T")
        state_equation = input_signal / time_constant
    else:
        raise ValueError("Unsupported integrator scaling mode")

    # A sampled hold flag makes the state derivative exactly zero while the
    # external hold command is active.
    if hold_mode == IntegratorHoldMode.SIGNAL:
        hold_signal: sym.Var = var_factory.add_var("integrator_hold")
        hold_mode_variable: sym.Var = var_factory.add_var("integrator_hold_active")
        input_variables.append(hold_signal)
        mode_parameters[hold_mode_variable] = var_factory.add_const(0.0)
        procedural_logic_entries.append(sampled_value(
            output=hold_mode_variable,
            source=sym.Comparison(lhs=hold_signal, op=sym.CmpOp.GE, rhs=0.5),
        ))
        state_equation = (sym.Const(1.0) - hold_mode_variable) * state_equation
    elif hold_mode == IntegratorHoldMode.NONE:
        pass
    else:
        raise ValueError("Unsupported integrator hold mode")

    # Startup freeze uses the same global-time convention as the imported
    # catalogue blocks, but exposes one clear duration parameter.
    if startup_freeze:
        global_time: sym.Var = var_factory.add_var("glob_time")
        startup_time: sym.Var = var_factory.add_var("integrator_startup_time")
        freeze_duration: sym.Var = var_factory.add_var("integrator_freeze_duration")
        freeze_mode_variable: sym.Var = var_factory.add_var("integrator_freeze_active")
        event_parameters[freeze_duration] = var_factory.add_const(0.0, name="freeze_duration")
        # The start-time snapshot is consumed by runtime procedural logic, so
        # it belongs to the mode vector. An init equation can only target a DAE
        # state, algebraic variable, derivative, or declared event parameter.
        mode_parameters[startup_time] = global_time
        mode_parameters[freeze_mode_variable] = var_factory.add_const(0.0)
        procedural_logic_entries.append(sampled_value(
            output=freeze_mode_variable,
            source=sym.Comparison(
                lhs=global_time - startup_time,
                op=sym.CmpOp.LT,
                rhs=freeze_duration,
            ),
        ))
        state_equation = (sym.Const(1.0) - freeze_mode_variable) * state_equation
    else:
        pass

    # Reset logic is edge-triggered. The initial-state option captures the
    # actual initialized state, while the signal option exposes its target.
    if reset_mode == IntegratorResetMode.NONE:
        pass
    elif reset_mode == IntegratorResetMode.INITIAL_STATE:
        reset_signal: sym.Var = var_factory.add_var("integrator_reset")
        initial_state: sym.Var = var_factory.add_var("integrator_initial_state")
        input_variables.append(reset_signal)
        # Reset logic needs a persistent snapshot of the initialized state.
        # Mode variables are initialized by the same dependency graph and stay
        # available to the edge-triggered procedural operation at runtime.
        mode_parameters[initial_state] = state
        procedural_logic_entries.append(reset(state, reset_signal, initial_state))
    elif reset_mode == IntegratorResetMode.SIGNAL:
        reset_value_signal: sym.Var = var_factory.add_var("integrator_reset_value")
        reset_signal = var_factory.add_var("integrator_reset")
        input_variables.append(reset_value_signal)
        input_variables.append(reset_signal)
        procedural_logic_entries.append(reset(state, reset_signal, reset_value_signal))
    else:
        raise ValueError("Unsupported integrator reset mode")

    # Bounds are created only when they participate in the selected output
    # equation, avoiding fake large limits and unused ports or parameters.
    output_expression: sym.Expr = state
    if saturation_mode != IntegratorSaturationMode.NONE and scale_bounds_by_gain:
        bound_gain_parameter: sym.Var = var_factory.add_var("integrator_bound_gain_K")
        event_parameters[bound_gain_parameter] = var_factory.add_const(1.0, name="bound_gain_K")
        bound_gain_expression: sym.Expr = bound_gain_parameter
    else:
        bound_gain_expression = sym.Const(1.0)
    if saturation_mode == IntegratorSaturationMode.NONE:
        pass
    elif saturation_mode == IntegratorSaturationMode.LOWER:
        lower_bound: sym.Var = var_factory.add_var("integrator_lower_bound")
        if bound_source == IntegratorBoundSource.PARAMETER:
            event_parameters[lower_bound] = var_factory.add_const(-1.0, name="lower_bound")
        elif bound_source == IntegratorBoundSource.SIGNAL:
            input_variables.append(lower_bound)
        else:
            raise ValueError("Unsupported integrator bound source")
        output_expression = sym.max(state, lower_bound * bound_gain_expression)
    elif saturation_mode == IntegratorSaturationMode.UPPER:
        upper_bound: sym.Var = var_factory.add_var("integrator_upper_bound")
        if bound_source == IntegratorBoundSource.PARAMETER:
            event_parameters[upper_bound] = var_factory.add_const(1.0, name="upper_bound")
        elif bound_source == IntegratorBoundSource.SIGNAL:
            input_variables.append(upper_bound)
        else:
            raise ValueError("Unsupported integrator bound source")
        output_expression = sym.min(state, upper_bound * bound_gain_expression)
    elif saturation_mode == IntegratorSaturationMode.BOTH:
        lower_bound = var_factory.add_var("integrator_lower_bound")
        upper_bound = var_factory.add_var("integrator_upper_bound")
        if bound_source == IntegratorBoundSource.PARAMETER:
            event_parameters[lower_bound] = var_factory.add_const(-1.0, name="lower_bound")
            event_parameters[upper_bound] = var_factory.add_const(1.0, name="upper_bound")
        elif bound_source == IntegratorBoundSource.SIGNAL:
            input_variables.append(lower_bound)
            input_variables.append(upper_bound)
        else:
            raise ValueError("Unsupported integrator bound source")
        output_expression = sym.min(
            sym.max(state, lower_bound * bound_gain_expression),
            upper_bound * bound_gain_expression,
        )
    elif saturation_mode == IntegratorSaturationMode.SYMMETRIC:
        symmetric_bound: sym.Var = var_factory.add_var("integrator_symmetric_bound")
        if bound_source == IntegratorBoundSource.PARAMETER:
            event_parameters[symmetric_bound] = var_factory.add_const(1.0, name="symmetric_bound")
        elif bound_source == IntegratorBoundSource.SIGNAL:
            input_variables.append(symmetric_bound)
        else:
            raise ValueError("Unsupported integrator bound source")
        absolute_bound: sym.Expr = sym.abs(symmetric_bound * bound_gain_expression)
        output_expression = sym.min(sym.max(state, -absolute_bound), absolute_bound)
    else:
        raise ValueError("Unsupported integrator saturation mode")

    block_name: str
    if startup_freeze:
        block_name = "integrator_with_startup_freeze"
    else:
        block_name = "integrator"
    block: Block = Block(
        state_vars=list((state,)),
        state_eqs=list((state_equation,)),
        algebraic_vars=list((output_signal,)),
        algebraic_eqs=list((output_signal - output_expression,)),
        diff_vars=list((state_derivative,)),
        init_eqs=initial_equations,
        in_vars=input_variables,
        out_vars=list((output_signal,)),
        event_dict=event_parameters,
        mode_dict=mode_parameters,
        procedural_logic=procedural_logic_entries,
        name=block_name,
        is_decomposable=False,
    )

    # Persist the user's exact structural choices in the block contract.
    # Block Properties can restore them after reopening the file without
    # reverse-engineering expanded symbolic equations or variable names.
    configuration: dict[str, object] = dict()
    configuration["scaling"] = scaling_mode.name
    configuration["hold_input"] = hold_mode.name
    configuration["reset"] = reset_mode.name
    configuration["output_saturation"] = saturation_mode.name
    configuration["bound_source"] = bound_source.name
    configuration["scale_bounds_by_gain"] = scale_bounds_by_gain
    if startup_freeze:
        block.modal_template_kind = "startup_freeze_integrator"
    else:
        block.modal_template_kind = "configurable_integrator"
    block.modal_template_config = configuration
    return block


def build_derivative_structural_properties() -> list[TemplateProp]:
    """Create the General Structure settings for a filtered derivative.

    The derivative is deliberately filtered because an ideal differentiator
    is improper and cannot be represented by the ordinary state-space block
    contract. Numeric gains and time constants remain normal block parameters.

    :return: Fresh structural property definitions for one derivative builder.
    """
    return list((
        TemplateProp(
            name="order",
            units="",
            descr="Order of the filtered derivative denominator.",
            tpe=DerivativeOrder,
            value=DerivativeOrder.FIRST,
        ),
        TemplateProp(
            name="scaling",
            units="",
            descr="Numerator scaling: s, K s, T s, K T s, or K Td s.",
            tpe=DerivativeScalingMode,
            value=DerivativeScalingMode.UNIT,
        ),
        TemplateProp(
            name="non_positive_time",
            units="",
            descr="Behavior used when the denominator time constant T is zero or negative.",
            tpe=DerivativeInactiveBehavior,
            value=DerivativeInactiveBehavior.STRICT,
        ),
    ))


class DerivativeTemplate(TemplateDefinition):
    """Structural definition of the canonical configurable derivative."""

    __slots__ = ()

    def __init__(self, vf: VarFactory) -> None:
        """Create a first-order unit filtered derivative by default.

        :param vf: Variable factory receiving the generated block variables.
        :return: None.
        """
        TemplateDefinition.__init__(self, vf, build_derivative_structural_properties())

    def eval(self) -> EmtModelTemplate:
        """Build a derivative from the selected structural options.

        :return: EMT template containing the configurable derivative block.
        """
        derivative_order: DerivativeOrder = self.get_value("order")
        scaling_mode: DerivativeScalingMode = self.get_value("scaling")
        inactive_behavior: DerivativeInactiveBehavior = self.get_value("non_positive_time")
        return build_configurable_derivative_template(
            var_factory=self.vf,
            derivative_order=derivative_order,
            scaling_mode=scaling_mode,
            inactive_behavior=inactive_behavior,
        )


def build_configurable_derivative_template(
        var_factory: VarFactory,
        derivative_order: DerivativeOrder,
        scaling_mode: DerivativeScalingMode,
        inactive_behavior: DerivativeInactiveBehavior,
) -> EmtModelTemplate:
    """Wrap one canonical configurable derivative in the builder contract.

    :param var_factory: Variable factory receiving the generated variables.
    :param derivative_order: First- or second-order filtered derivative.
    :param scaling_mode: Numerator scaling applied to the derivative signal.
    :param inactive_behavior: Response to a non-positive denominator time.
    :return: EMT template containing the requested derivative structure.
    """
    block: Block = build_configurable_derivative_block(
        var_factory=var_factory,
        derivative_order=derivative_order,
        scaling_mode=scaling_mode,
        inactive_behavior=inactive_behavior,
    )
    template: EmtModelTemplate = EmtModelTemplate(name=block.name)
    template.tpe = DeviceType.NoDevice
    template.block = block
    return template


def build_configurable_derivative_block(
        var_factory: VarFactory,
        derivative_order: DerivativeOrder,
        scaling_mode: DerivativeScalingMode,
        inactive_behavior: DerivativeInactiveBehavior,
) -> Block:
    """Build a proper filtered derivative covering the useful legacy variants.

    A first-order block implements ``A*s/(1 + T*s)``. A second-order block
    implements ``A*s^2/(1 + T*s)^2``. ``A`` is selected by the scaling mode.
    Non-strict modes sample whether ``T`` is positive during initialization,
    matching the behavior of the legacy ``selfix``-based templates.

    :param var_factory: Variable factory receiving the generated variables.
    :param derivative_order: Number of cascaded filtered derivative stages.
    :param scaling_mode: Rule used to construct the numerator coefficient.
    :param inactive_behavior: Response used when ``T`` is non-positive.
    :return: Configured ordinary symbolic block.
    """
    # Stable external names let General Structure rebuild the block without
    # changing the semantic identity of its input and output ports.
    input_signal: sym.Var = var_factory.add_var("derivative_input")
    output_signal: sym.Var = var_factory.add_var("derivative_output")
    time_constant: sym.Var = var_factory.add_var("derivative_time_constant_T")

    input_variables: List[sym.Var] = list((input_signal,))
    state_variables: List[sym.Var] = list()
    state_equations: List[sym.Expr] = list()
    differential_variables: List[sym.Var] = list()
    event_parameters: dict[sym.Var, sym.Expr | sym.Const] = dict()
    mode_parameters: dict[sym.Var, sym.Expr | sym.Const] = dict()
    procedural_logic_entries: list[ProceduralLogicEntryContract[sym.Expr]] = list()
    event_parameters[time_constant] = var_factory.add_const(1.0, name="T")

    # The numerator coefficient is independent of the state realization. This
    # keeps first- and second-order variants inside one consistent builder.
    gain_parameter: sym.Var | None = None
    if scaling_mode == DerivativeScalingMode.UNIT:
        numerator_coefficient: sym.Expr = sym.Const(1.0)
    elif scaling_mode == DerivativeScalingMode.GAIN:
        gain_parameter = var_factory.add_var("derivative_gain_K")
        event_parameters[gain_parameter] = var_factory.add_const(1.0, name="K")
        numerator_coefficient = gain_parameter
    elif scaling_mode == DerivativeScalingMode.TIME_CONSTANT:
        numerator_coefficient = time_constant
    elif scaling_mode == DerivativeScalingMode.GAIN_TIME_CONSTANT:
        gain_parameter = var_factory.add_var("derivative_gain_K")
        event_parameters[gain_parameter] = var_factory.add_const(1.0, name="K")
        numerator_coefficient = gain_parameter * time_constant
    elif scaling_mode == DerivativeScalingMode.GAIN_DERIVATIVE_TIME:
        gain_parameter = var_factory.add_var("derivative_gain_K")
        derivative_time: sym.Var = var_factory.add_var("derivative_time_Td")
        event_parameters[gain_parameter] = var_factory.add_const(1.0, name="K")
        event_parameters[derivative_time] = var_factory.add_const(1.0, name="Td")
        numerator_coefficient = gain_parameter * derivative_time
    else:
        raise ValueError("Unsupported derivative scaling mode")

    # Strict mode exposes invalid T values directly. Protected modes construct
    # a non-zero effective denominator before applying their selected output
    # behavior, so T=0 never survives inside an inactive division branch.
    active_mode: sym.Var | None = None
    state_activity: sym.Expr = sym.Const(1.0)
    if inactive_behavior == DerivativeInactiveBehavior.STRICT:
        effective_time: sym.Expr = time_constant
    elif inactive_behavior in (
            DerivativeInactiveBehavior.ZERO_OUTPUT,
            DerivativeInactiveBehavior.BYPASS_INPUT,
    ):
        active_mode = var_factory.add_var("derivative_time_active")
        mode_parameters[active_mode] = var_factory.add_const(0.0)
        procedural_logic_entries.append(selfix(
            sym.Comparison(lhs=time_constant, op=sym.CmpOp.GT, rhs=0.0),
            output=active_mode,
        ))
        state_activity = active_mode
        effective_time = active_mode * time_constant + (sym.Const(1.0) - active_mode)
    elif inactive_behavior == DerivativeInactiveBehavior.FALLBACK_TIME:
        active_mode = var_factory.add_var("derivative_time_active")
        fallback_time: sym.Var = var_factory.add_var("derivative_fallback_time")
        mode_parameters[active_mode] = var_factory.add_const(0.0)
        event_parameters[fallback_time] = var_factory.add_const(0.01, name="fallback_T")
        procedural_logic_entries.append(selfix(
            sym.Comparison(lhs=time_constant, op=sym.CmpOp.GT, rhs=0.0),
            output=active_mode,
        ))
        effective_time = active_mode * time_constant + (sym.Const(1.0) - active_mode) * fallback_time
    else:
        raise ValueError("Unsupported derivative non-positive-time behavior")

    # A fallback washout must use the same effective time in its numerator and
    # denominator. Otherwise T=0 would silently turn a protected washout into
    # a zero-gain block instead of substituting the configured fallback time.
    if (
            inactive_behavior == DerivativeInactiveBehavior.FALLBACK_TIME
            and scaling_mode == DerivativeScalingMode.TIME_CONSTANT
    ):
        numerator_coefficient = effective_time
    elif (
            inactive_behavior == DerivativeInactiveBehavior.FALLBACK_TIME
            and scaling_mode == DerivativeScalingMode.GAIN_TIME_CONSTANT
    ):
        if gain_parameter is not None:
            numerator_coefficient = gain_parameter * effective_time
        else:
            raise ValueError("Gain washout requires a gain parameter")
    else:
        pass

    # Each stage is one stable first-order lag. Exposing its difference term as
    # the derivative signal gives exactly s/(1+Ts), then cascades naturally for
    # the second-order form without introducing an improper ideal derivative.
    first_state: sym.Var = var_factory.add_var("derivative_state_1")
    first_state_derivative: sym.Var = var_factory.add_diff_var(
        "d_derivative_state_1",
        base_var=first_state,
    )
    first_derivative_signal: sym.Expr = (input_signal - first_state) / effective_time
    state_variables.append(first_state)
    state_equations.append(state_activity * first_derivative_signal)
    differential_variables.append(first_state_derivative)

    if derivative_order == DerivativeOrder.FIRST:
        derivative_signal: sym.Expr = first_derivative_signal
    elif derivative_order == DerivativeOrder.SECOND:
        second_state: sym.Var = var_factory.add_var("derivative_state_2")
        second_state_derivative: sym.Var = var_factory.add_diff_var(
            "d_derivative_state_2",
            base_var=second_state,
        )
        second_derivative_signal: sym.Expr = (first_derivative_signal - second_state) / effective_time
        state_variables.append(second_state)
        state_equations.append(state_activity * second_derivative_signal)
        differential_variables.append(second_state_derivative)
        derivative_signal = second_derivative_signal
    else:
        raise ValueError("Unsupported derivative order")

    active_output: sym.Expr = numerator_coefficient * derivative_signal
    if inactive_behavior == DerivativeInactiveBehavior.ZERO_OUTPUT:
        if active_mode is not None:
            output_expression: sym.Expr = active_mode * active_output
        else:
            raise ValueError("Zero-output derivative requires an active-time mode")
    elif inactive_behavior == DerivativeInactiveBehavior.BYPASS_INPUT:
        if active_mode is not None:
            output_expression = active_mode * active_output + (sym.Const(1.0) - active_mode) * input_signal
        else:
            raise ValueError("Bypass derivative requires an active-time mode")
    else:
        output_expression = active_output

    block: Block = Block(
        state_vars=state_variables,
        state_eqs=state_equations,
        algebraic_vars=list((output_signal,)),
        algebraic_eqs=list((output_signal - output_expression,)),
        diff_vars=differential_variables,
        in_vars=input_variables,
        out_vars=list((output_signal,)),
        event_dict=event_parameters,
        mode_dict=mode_parameters,
        procedural_logic=procedural_logic_entries,
        name="derivative",
        is_decomposable=False,
    )

    # Persist exact selections for both the properties dialog and canvas item;
    # neither consumer needs to inspect mutable symbolic variable names.
    configuration: dict[str, object] = dict()
    configuration["order"] = derivative_order.name
    configuration["scaling"] = scaling_mode.name
    configuration["non_positive_time"] = inactive_behavior.name
    block.modal_template_kind = "configurable_derivative"
    block.modal_template_config = configuration
    return block


def build_extremum_template(
        var_factory: VarFactory,
        input_count: int,
        block_type: BlockType,
) -> EmtModelTemplate:
    """Wrap a configurable minimum or maximum block in the builder contract.

    Builder-backed Library entries return model templates so creation,
    preflight validation, and structural editing all consume the same type.
    The inner block remains an ordinary symbolic block and retains the
    configurable ``input_count`` structure.

    :param var_factory: Variable factory receiving the generated variables.
    :param input_count: Number of signals participating in the reduction.
    :param block_type: ``BlockType.MIN`` or ``BlockType.MAX``.
    :return: EMT template containing the requested extremum block.
    """
    block: Block = extremum(
        var_factory=var_factory,
        input_count=input_count,
        block_type=block_type,
    )
    template: EmtModelTemplate = EmtModelTemplate(name=block.name)
    template.tpe = DeviceType.NoDevice
    template.block = block
    return template


def extremum(var_factory: VarFactory, input_count: int, block_type: BlockType) -> Block:
    """Build a minimum or maximum reduction over a configurable number of inputs.

    The operation is represented by ordinary binary symbolic function nodes.
    Folding those nodes keeps the model proportional to the number of inputs
    instead of expanding every comparison into repeated Heaviside expressions.

    :param var_factory: Variable factory receiving the generated block variables.
    :param input_count: Number of input signals participating in the reduction.
    :param block_type: ``BlockType.MIN`` or ``BlockType.MAX``.
    :return: Structural minimum or maximum block.
    :raises ValueError: If fewer than two inputs or an unsupported block type is requested.
    """
    if input_count < 2:
        raise ValueError("Minimum and maximum blocks require at least two inputs")
    else:
        pass

    if block_type == BlockType.MIN:
        function_name: str = "min"
        block_name: str = "minimum"
    elif block_type == BlockType.MAX:
        function_name = "max"
        block_name = "maximum"
    else:
        raise ValueError("Extremum blocks support only BlockType.MIN or BlockType.MAX")

    # Create stable positional names so existing connections survive a later
    # increase or decrease of the configured input count.
    inputs: List[sym.Var] = list()
    input_index: int
    for input_index in range(input_count):
        inputs.append(var_factory.add_var("extremum_input_" + str(input_index)))

    # Reduce the inputs through native symbolic min/max nodes. Each additional
    # port contributes exactly one comparison node to the symbolic model.
    expression: sym.Expr = inputs[0]
    input_variable: sym.Var
    for input_variable in inputs[1:]:
        expression = sym.Func2(function_name, expression, input_variable)

    output_variable: sym.Var = var_factory.add_var("extremum_output_")
    block: Block = Block(
        algebraic_vars=list((output_variable,)),
        algebraic_eqs=list((output_variable - expression,)),
        in_vars=inputs,
        out_vars=list((output_variable,)),
        name=block_name,
        is_decomposable=False,
    )
    return block

def product(var_factory: VarFactory, divident_inputs: int = 1, divisor_inputs: int = 1) -> Block:
    """

    :param var_factory:
    :param item_name:
    :param divident_inputs:
    :param divisor_inputs:
    :return:
    """
    equation: sym.Expr | None = None
    inputs: List[sym.Var] = list()

    for i in range(divident_inputs):
        if equation is None:
            var = var_factory.add_var("mul_" + str(i))
            inputs.append(var)
            equation = var

        else:
            var = var_factory.add_var("mul_" + str(i))
            inputs.append(var)
            equation *= var

    for i in range(divisor_inputs):
        if equation is None:
            var = var_factory.add_var("div_" + str(i))
            inputs.append(var)
            equation = 1 / var
        else:
            var = var_factory.add_var("div_" + str(i))
            inputs.append(var)
            equation /= var


    y = var_factory.add_var("prod_out_")


    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - equation],
        in_vars=inputs,
        out_vars=[y],
        name="product",
        is_decomposable=False
    )

    return blk


def substract(var_factory: VarFactory, item_name: str = "") -> Block:
    """

    :param var_factory:
    :param item_name:
    :return:
    """
    inputs = [var_factory.add_var("minuend_" + item_name), var_factory.add_var("subtrahend_" + item_name)]
    y = var_factory.add_var("difference_" + item_name)

    expr: sym.Expr = inputs[0] - inputs[1]

    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - expr],
        in_vars=inputs,
        out_vars=[y],
        name="substraction",
        is_decomposable=False
    )

    return blk


def product_2(var_factory: VarFactory, item_name: str = "") -> Block:
    """

    :param var_factory:
    :param item_name:
    :return:
    """
    inputs = [var_factory.add_var("factor1_" + item_name),
              var_factory.add_var("factor2_" + item_name)]  # will not be specified if inputs can be more than 2
    y = var_factory.add_var("product_out_" + item_name)

    expr: sym.Expr = inputs[0] * inputs[1]

    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - expr],
        in_vars=inputs,
        out_vars=[y],
        name="product",
        is_decomposable=False
    )

    return blk


def divide(var_factory: VarFactory, item_name: str = "") -> Block:
    """

    :param var_factory:
    :param item_name:
    :return:
    """
    inputs = [var_factory.add_var("divident_" + item_name),
              var_factory.add_var("divisor_" + item_name)]  # will not be specified if inputs can be more than 2
    y = var_factory.add_var("quotient_" + item_name)

    expr: sym.Expr = inputs[0] / inputs[1]

    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - expr],
        in_vars=inputs,
        out_vars=[y],
        name="divide",
        is_decomposable=False
    )

    return blk


def absolut(var_factory: VarFactory, item_name: str = "") -> Block:
    """

    :param var_factory:
    :param item_name:
    :return:
    """
    inputs = [var_factory.add_var("inp_num_" + item_name)]  # will not be specified if inputs can be more than 2
    y = var_factory.add_var("absolut_" + item_name)

    expr: sym.Expr = sym.abs(inputs[0])

    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - expr],
        in_vars=inputs,
        out_vars=[y],
        name="abs",
        is_decomposable=False
    )

    return blk


def integrator(var_factory: VarFactory, u: sym.Var | sym.Const, name: str = "x") -> Tuple[sym.Var, Block]:
    """

    :param var_factory:
    :param u:
    :param name:
    :return:
    """
    x = var_factory.add_var(name)
    blk = Block(state_vars=[x], state_eqs=[u], is_decomposable=False)
    return x, blk


def pi_controller(var_factory: VarFactory, err: sym.Var, kp: float, ki: float, name: str = "pi") -> Block:
    """

    :param var_factory:
    :param err:
    :param kp:
    :param ki:
    :param name:
    :return:
    """
    up, blk_kp = gain(var_factory=var_factory)
    ie, blk_int = integrator(var_factory=var_factory, u=err)
    ui, blk_ki = gain(var_factory=var_factory)
    u, blk_sum = adder(var_factory=var_factory)
    return Block(name="",
                 children=[blk_kp, blk_int, blk_ki, blk_sum],
                 in_vars=[err],
                 out_vars=[u],
                 is_decomposable=False)


def signal_pair(var_factory: VarFactory, item_name: str = "") -> Tuple[Block, Block]:
    """
    Create a signal pair: one block with an input port and one block with
    an output port that share the same variable. When an external output
    is connected to the input block, the output block exposes the same
    variable automatically.

    :param var_factory:
    :param item_name:
    :return: (input_block, output_block)
    """
    v = var_factory.add_var("signal_" + item_name)

    blk_in = Block(
        in_vars=[v],
        name="From" + item_name
    )

    blk_out = Block(
        # algebraic_vars=[v],
        out_vars=[v],
        name="To" + item_name
    )

    return blk_in, blk_out


def generic(var_factory: VarFactory, 
            inputs: int,
            outputs: int,
            ) -> Block:
    """Build an empty generic block with deterministic interface initialization.

    :param var_factory: Factory that owns every new symbolic identity.
    :param inputs: Number of incoming signal variables to create.
    :param outputs: Number of outgoing signal variables to create.
    :return: Generic block whose outputs start from zero until edited.
    """
    input_variables: list[sym.Var] = list()
    input_index: int
    for input_index in range(inputs):
        input_variables.append(var_factory.add_var(f"input{input_index}"))

    output_variables: list[sym.Var] = list()
    output_index: int
    for output_index in range(outputs):
        output_variables.append(var_factory.add_var(f"output{output_index}"))

    initial_equations: dict[sym.Var, sym.Const] = dict()
    output_variable: sym.Var
    for output_variable in output_variables:
        # Generic outputs are block-owned signals even before the user writes
        # their runtime equations. Give each one a deterministic initialization
        # that remains editable from Block Properties.
        initial_equations[output_variable] = sym.Const(0.0)

    blk: Block = Block(
        name="generic",
        in_vars=input_variables,
        out_vars=output_variables,
        init_eqs=initial_equations,
    )
    return blk

