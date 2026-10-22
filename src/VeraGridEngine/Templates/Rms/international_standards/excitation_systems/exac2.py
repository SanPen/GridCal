# SPDX-License-Identifier: MPL-2.0
"""High-response brushless excitation with proportional field feedback and a current override."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.common.brushless_exciter import build_brushless_exciter_base
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def build_exac2_template(vf: VarFactory, name: str | None = None) -> RmsModelTemplate:
    """Build high-initial-response alternator excitation with a finite-gain current limiter.

    Voltage sensing, phase compensation and a bounded amplifier drive an inner
    high-gain field-control loop. Direct feedback ``KH*Vfe`` subtracts from
    amplifier demand. A low-value gate compares that compensated demand against
    ``KL*(VLR-Vfe)``. The selected signal is multiplied by KB and clipped by
    independent field-forcing bounds before driving the rotating exciter.
    Amplifier bounds and downstream forcing bounds are separate capabilities.

    Vfe is the internal exciter field-current equivalent, including resistive,
    saturation and generator-current demagnetizing terms. Direct proportional
    feedback increases field-circuit bandwidth; a separate filtered derivative
    feedback also senses Vfe. The finite-gain override reduces forcing as current
    approaches its reference. It retains a dynamic field state rather than
    replacing the current-limiting loop by an instantaneous field-voltage bound.
    A rotating diode bridge supplies nonnegative generator field voltage, with
    live-current commutation loading and a zero lower field-memory stop.

    Five states store voltage sensing, phase memory, amplifier output, exciter
    field voltage and rate-feedback memory. At a consistent initial point, the
    current override permits normal regulation, field forcing equals Vfe0 and
    amplifier demand is ``Vfe0*(KH+1/KB)``. Phase memory and voltage reference
    initialize from that amplifier demand, while rate-feedback memory retains
    Vfe0. This distinction is essential for nonunit inner-loop gains.

    Inputs are generator field current, additive overexcitation voltage,
    stabilizing voltage, sensed voltage, voltage reference and additive minimum-
    excitation voltage. The output is generator field voltage. Signals use the
    connected per-unit field bases and all times are seconds. Positive sensing,
    phase, amplifier, field and rate-feedback times select this realization;
    KB is positive and KH/KL are nonnegative.

    :param vf: Shared native symbolic factory.
    :param name: Optional instance label.
    :return: Native five-state high-response brushless excitation controller.
    """
    label: str = 'EXAC2' if name is None else name
    template: RmsModelTemplate = build_brushless_exciter_base(vf, label)
    block: Block = template.block
    variables: dict[str, Var] = dict((variable.name, variable) for variable in block.get_all_vars())
    variables.update((variable.name, variable) for variable in block.event_dict)
    kb: Var = vf.add_var('KB_'+label)
    kh: Var = vf.add_var('KH_'+label)
    kl: Var = vf.add_var('KL_'+label)
    reference: Var = vf.add_var('VLR_'+label)
    upper: Var = vf.add_var('BridgeVRMAX_'+label)
    lower: Var = vf.add_var('BridgeVRMIN_'+label)
    initial_amplifier: Var = vf.add_var('Amplifier0Pu_'+label)
    forcing: Var = vf.add_var('FieldForcingPu_'+label)
    block.event_dict[kb] = Const(10.0)
    block.event_dict[kh] = Const(.2)
    block.event_dict[kl] = Const(1.0)
    block.event_dict[reference] = Const(5.0)
    block.event_dict[upper] = Const(5.0)
    block.event_dict[lower] = Const(-5.0)
    current_initial: Var = variables['avr.Vr0Pu_'+label]
    block.event_dict[initial_amplifier] = current_initial*(kh+Const(1.0)/kb)
    block.event_dict[variables['avr.limitedFirstOrder.Y0_'+label]] = initial_amplifier
    block.event_dict[variables['avr.leadLag.x_start[1]_'+label]] = initial_amplifier/variables['avr.Ka_'+label]
    block.event_dict[variables['avr.leadLag.y_start_'+label]] = initial_amplifier/variables['avr.Ka_'+label]
    block.event_dict[variables['avr.UsRef0Pu_'+label]] = variables['avr.Us0Pu_'+label]+initial_amplifier/variables['avr.Ka_'+label]
    amplifier: Var = variables['avr.limitedFirstOrder.y_'+label]
    current_equivalent: Var = variables['avr.add3.y_'+label]
    compensated: Expr = amplifier-kh*current_equivalent
    override: Expr = kl*(reference-current_equivalent)
    block.algebraic_vars.append(forcing)
    block.algebraic_eqs.append(forcing-sym.hard_sat(kb*sym.min(compensated, override), lower, upper))
    block.init_eqs[forcing] = current_initial
    field_balance: Var = variables['avr.feedback1.y_'+label]
    substitution: dict[Var, Expr] = dict(((amplifier, forcing),))
    for index, variable in enumerate(block.algebraic_vars):
        if variable == field_balance:
            block.algebraic_eqs[index] = block.algebraic_eqs[index].subs(substitution)
        else:
            pass
    template.comment = 'High-response brushless excitation with field-current feedback and a finite-gain override'
    return template
