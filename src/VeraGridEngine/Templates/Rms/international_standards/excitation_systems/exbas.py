# SPDX-License-Identifier: MPL-2.0
"""Proportional-integral brushless excitation with shaped exciter-current stabilization."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.common.brushless_exciter import build_brushless_exciter_base
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var


def build_exbas_template(vf: VarFactory, name: str | None = None) -> RmsModelTemplate:
    """Build PI voltage regulation feeding an independently supplied rotating exciter.

    Sensed-voltage error and additive supplementary signals are corrected by
    field-current rate feedback, then pass through ``KP+KI/s``, forward phase
    compensation and a non-windup first-order amplifier. Proportional and
    integral control are separate: the integral memory retains the steady
    forcing demand and is not artificially stopped by amplifier saturation.
    The voltage reference therefore equals initial sensed voltage, with zero
    steady corrected voltage error. Integral memory and forward phase memory
    initialize to Vfe0/KA rather than starting from zero.

    The rotating exciter includes resistance, quadratic saturation and live
    generator-current demagnetization. A diode-bridge commutation characteristic
    supplies generator field voltage. Internal field voltage has a zero lower
    memory stop. The stabilizing loop senses the internal field-current
    equivalent Vfe and applies
    ``KF*s*(1+s*TF1)/((1+s*TF)*(1+s*TF2))``. Its shaping memory and derivative
    memory both initialize at Vfe0, giving zero initial stabilization output.
    Independent regulator supply does not scale with terminal-bus voltage.

    Seven states store sensed voltage, PI integral memory, forward phase memory,
    amplifier output, internal field voltage, feedback shaping memory and rate-
    feedback memory. Positive sensing, forward phase, amplifier, field and both
    feedback times select this realization; KI is positive and KP is nonnegative.
    Inputs are generator field current, additive overexcitation voltage,
    stabilizing voltage, sensed voltage, reference and additive minimum-excitation
    voltage. Output is generator field voltage. Signals use connected per-unit
    bases and times are seconds. Field and amplifier limits must admit the
    initialized operating point.

    :param vf: Shared native symbolic factory.
    :param name: Optional instance label.
    :return: Native seven-state PI brushless excitation controller.
    """
    label: str = 'EXBAS' if name is None else name
    template: RmsModelTemplate = build_brushless_exciter_base(vf, label)
    block: Block = template.block
    variables: dict[str, Var] = dict((variable.name, variable) for variable in block.get_all_vars())
    variables.update((variable.name, variable) for variable in block.event_dict)
    kp: Var = vf.add_var('KP_'+label)
    ki: Var = vf.add_var('KI_'+label)
    lead: Var = vf.add_var('TF1_'+label)
    lag: Var = vf.add_var('TF2_'+label)
    integral: Var = vf.add_var('IntegralMemoryPu_'+label)
    pi_output: Var = vf.add_var('PiDemandPu_'+label)
    shaping_memory: Var = vf.add_var('FeedbackShapingMemoryPu_'+label)
    shaped: Var = vf.add_var('ShapedCurrentPu_'+label)
    block.event_dict[kp] = Const(1.0)
    block.event_dict[ki] = Const(1.0)
    block.event_dict[lead] = Const(.1)
    block.event_dict[lag] = Const(.5)
    error: Var = variables['avr.feedback.y_'+label]
    current: Var = variables['avr.add3.y_'+label]
    current_initial: Var = variables['avr.Vr0Pu_'+label]
    initial_integral: Expr = current_initial/variables['avr.Ka_'+label]
    block.event_dict[variables['avr.UsRef0Pu_'+label]] = variables['avr.Us0Pu_'+label]
    block.state_vars.append(integral)
    block.diff_vars.append(vf.add_diff_var('d_IntegralMemoryPu_'+label, base_var=integral))
    block.state_eqs.append(ki*error)
    block.init_eqs[integral] = initial_integral
    block.algebraic_vars.append(pi_output)
    block.algebraic_eqs.append(pi_output-(kp*error+integral))
    block.init_eqs[pi_output] = initial_integral
    block.state_vars.append(shaping_memory)
    block.diff_vars.append(vf.add_diff_var('d_FeedbackShapingMemoryPu_'+label, base_var=shaping_memory))
    block.state_eqs.append((current-shaping_memory)/lag)
    block.init_eqs[shaping_memory] = current_initial
    block.algebraic_vars.append(shaped)
    block.algebraic_eqs.append(shaped-(shaping_memory+lead/lag*(current-shaping_memory)))
    block.init_eqs[shaped] = current_initial
    phase_substitution: dict[Var, Expr] = dict(((error, pi_output),))
    feedback_substitution: dict[Var, Expr] = dict(((current, shaped),))
    for index, variable in enumerate(block.state_vars):
        if variable == variables['avr.leadLag.x_scaled[1]_'+label]:
            block.state_eqs[index] = block.state_eqs[index].subs(phase_substitution)
        elif variable == variables['avr.derivative.x_'+label]:
            block.state_eqs[index] = block.state_eqs[index].subs(feedback_substitution)
        else:
            pass
    for index, variable in enumerate(block.algebraic_vars):
        if variable == variables['avr.leadLag.y_'+label]:
            block.algebraic_eqs[index] = block.algebraic_eqs[index].subs(phase_substitution)
        elif variable == variables['avr.derivative.y_'+label]:
            block.algebraic_eqs[index] = block.algebraic_eqs[index].subs(feedback_substitution)
        else:
            pass
    template.comment = 'PI brushless excitation with shaped exciter-current rate feedback'
    return template
