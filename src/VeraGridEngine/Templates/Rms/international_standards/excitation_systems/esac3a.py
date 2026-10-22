# SPDX-License-Identifier: MPL-2.0
"""Self-excited brushless excitation with minimum-excitation takeover and internal field stops."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.common.brushless_field_limits import limit_brushless_field
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.exac3 import build_exac3_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def build_esac3a_template(vf: VarFactory, name: str | None = None) -> RmsModelTemplate:
    """Build self-excited alternator regulation with minimum-excitation takeover.

    Sensed voltage, reference and additive supplementary signals feed phase
    compensation. A high-value minimum-excitation gate precedes the bounded
    amplifier; its demand is not an additive voltage-error correction. Field
    forcing is ``KR*Efd*Va``, retaining multiplicative self-excitation from
    rectified output voltage. The internal rotating-field state has a lower
    voltage stop VEMIN and an upper current-equivalent stop VFEMAX. These stops
    block outward derivatives and allow inward recovery without discontinuously
    resetting field memory when generator current changes.

    The field circuit includes resistance, quadratic excess-field saturation,
    demagnetization and live-current diode-bridge commutation. Stabilization
    filters the continuous piecewise signal
    ``KF*Efd+(KN-KF)*max(Efd-EFDN,0)`` through ``s/(1+s*TF)``. Five states store
    sensing, phase memory, amplifier output, internal field voltage and feedback
    memory. At a positive initial field voltage, amplifier demand is
    ``Vfe0/(KR*Efd0)`` and the feedback memory stores the nonlinear feedback
    signal. Field stops and the takeover gate must admit the operating point;
    an unexcited black-start reference is outside this initialization.

    Inputs are generator field current, additive overexcitation voltage,
    stabilizing voltage, sensed voltage, reference and minimum-excitation gate
    demand. Outputs are generator field voltage and phase-compensator demand,
    allowing an absent minimum-excitation limiter to follow that live demand.
    Signals use connected per-unit bases, and times are seconds. Positive sensing,
    phase, amplifier, field and feedback times select this realization. Positive
    KE and nonnegative saturation/KD make the current stop equivalent to the
    implicit voltage ceiling ``(VFEMAX-KD*Ifd)/(KE+SE(VE))``.

    :param vf: Shared native symbolic factory.
    :param name: Optional instance label.
    :return: Native five-state self-excited brushless controller.
    """
    label: str = 'ESAC3A' if name is None else name
    template: RmsModelTemplate = build_exac3_template(vf, label)
    block: Block = template.block
    variables: dict[str, Var] = dict((variable.name, variable) for variable in block.get_all_vars())
    variables.update((variable.name, variable) for variable in block.event_dict)
    uel: Var = block.in_vars[5]
    phase: Var = variables['avr.leadLag.y_'+label]
    amplifier_drive: Var = variables['avr.limitedFirstOrder.Gk.y_'+label]
    summation: Var = variables['avr.sum1.y_'+label]
    remove_additive_uel: dict[Var, Expr] = dict(((uel, Const(0.0)),))
    block.init_eqs[summation] = block.init_eqs[summation].subs(remove_additive_uel)
    block.init_eqs[uel] = variables['Amplifier0Pu_'+label]/variables['avr.Ka_'+label]
    for index, variable in enumerate(block.algebraic_vars):
        if variable == summation:
            block.algebraic_eqs[index] = block.algebraic_eqs[index].subs(remove_additive_uel)
        elif variable == amplifier_drive:
            block.algebraic_eqs[index] = amplifier_drive-variables['avr.Ka_'+label]*sym.max(phase, uel)
        else:
            pass
    # The takeover gate replaces the autonomous minimum-voltage protection loop.
    for parameter in ('KLV_', 'VLV_'):
        obsolete: Var = variables[parameter+label]
        block.event_dict.pop(obsolete)
    limit_brushless_field(block, vf, label, variables['FieldForcingPu_'+label], variables)
    block.out_vars = list((block.out_vars[0], phase))
    template.comment = 'Self-excited brushless excitation with takeover regulation and internal field stops'
    return template
