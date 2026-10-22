# SPDX-License-Identifier: MPL-2.0
"""Brushless excitation with independent amplifier bounds and cascaded capability gates."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.common.brushless_exciter import build_brushless_exciter_base
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def build_esac1a_template(vf: VarFactory, name: str | None = None) -> RmsModelTemplate:
    """Build a brushless exciter with separate amplifier and field-forcing limits.

    Voltage sensing, additive stabilizing voltage and field-current rate feedback
    feed a phase lead-lag and a non-windup amplifier. Its own upper/lower bounds
    limit amplifier memory. A minimum-excitation high-value gate then precedes
    an overexcitation low-value gate. Separate field-forcing bounds clip the gated
    signal before the rotating exciter field circuit; these downstream limits do
    not replace the amplifier's own state limits.

    The rotating alternator includes saturation and field-current demagnetization.
    Its nonnegative internal field voltage feeds a diode-bridge commutation curve
    to produce generator field voltage. The rate-feedback sensor measures the
    internal exciter field-current equivalent, including saturation, resistive
    and demagnetizing contributions. Independent regulator power is not scaled
    by instantaneous bus voltage.

    Five states store sensing, phase, amplifier, field and feedback memories.
    Initialization balances the field circuit and rectifier at the operating
    point; both capability gates must permit that forcing. Inputs are generator
    field current, low-value overexcitation demand, stabilizing voltage, sensed
    voltage, reference voltage and high-value minimum-excitation demand. Outputs
    are field voltage, amplifier demand before both gates and demand between the
    gates. Connecting an absent limiter to its preceding demand bypasses it
    exactly. Signals are per unit on their connected bases, and times are seconds.
    Positive sensing, phase, amplifier, field and feedback times select this
    realization.

    :param vf: Shared native symbolic factory.
    :param name: Optional instance label.
    :return: Native brushless exciter with two limiter-gate bypass outputs.
    """
    label: str = 'ESAC1A' if name is None else name
    template: RmsModelTemplate = build_brushless_exciter_base(vf, label)
    block: Block = template.block
    variables: dict[str, Var] = dict((variable.name, variable) for variable in block.get_all_vars())
    variables.update((variable.name, variable) for variable in block.event_dict)
    amplifier: Var = variables['avr.limitedFirstOrder.y_'+label]
    uel: Var = block.in_vars[5]
    oel: Var = block.in_vars[1]
    upper: Var = vf.add_var('BridgeVRMAX_'+label)
    lower: Var = vf.add_var('BridgeVRMIN_'+label)
    gated: Var = vf.add_var('MinimumGatePu_'+label)
    forcing: Var = vf.add_var('FieldForcingPu_'+label)
    initial_forcing: Var = variables['avr.Vr0Pu_'+label]
    block.event_dict[upper] = Const(5.0)
    block.event_dict[lower] = Const(-5.0)
    block.algebraic_vars.append(gated)
    block.algebraic_eqs.append(gated-sym.max(amplifier, uel))
    block.algebraic_vars.append(forcing)
    block.algebraic_eqs.append(forcing-sym.hard_sat(sym.min(gated, oel), lower, upper))
    block.init_eqs[gated] = initial_forcing
    block.init_eqs[forcing] = initial_forcing
    block.init_eqs[uel] = initial_forcing
    block.init_eqs[oel] = initial_forcing
    # Capability limiters act after the amplifier, rather than adding voltage
    # error before phase compensation as in the ungated forward circuit.
    summation: Var = variables['avr.sum1.y_'+label]
    field_balance: Var = variables['avr.feedback1.y_'+label]
    remove_additive_limits: dict[Var, Expr] = dict(((uel, Const(0.0)), (oel, Const(0.0))))
    block.init_eqs[summation] = block.init_eqs[summation].subs(remove_additive_limits)
    insert_forcing: dict[Var, Expr] = dict(((amplifier, forcing),))
    for index, variable in enumerate(block.algebraic_vars):
        if variable == summation:
            block.algebraic_eqs[index] = block.algebraic_eqs[index].subs(remove_additive_limits)
        elif variable == field_balance:
            block.algebraic_eqs[index] = block.algebraic_eqs[index].subs(insert_forcing)
        else:
            pass
    block.out_vars = list((block.out_vars[0], amplifier, gated))
    template.comment = 'Brushless excitation with amplifier limits and cascaded capability gates'
    return template
