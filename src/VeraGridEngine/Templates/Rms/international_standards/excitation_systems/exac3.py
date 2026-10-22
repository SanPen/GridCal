# SPDX-License-Identifier: MPL-2.0
"""Self-excited brushless alternator excitation with nonlinear field-voltage stabilization."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.common.brushless_exciter import build_brushless_exciter_base
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def build_exac3_template(vf: VarFactory, name: str | None = None) -> RmsModelTemplate:
    """Build self-excited rotating excitation with field-voltage-dependent regulator power.

    Sensed-voltage error, additive stabilizing signals and nonlinear rate feedback
    pass through phase compensation. A high-value gate compares the compensated
    error with ``KLV*(VLV-Efd)`` before the bounded amplifier. Regulator forcing
    is ``KR*Efd*Va``: power is derived from the rectified exciter output, so the
    forward path retains the multiplicative self-excitation nonlinearity.

    The rotating exciter includes field resistance, saturation, generator-current
    demagnetization and a diode-bridge commutation characteristic. Its field
    memory has a zero lower stop. Stabilization filters the continuous piecewise
    signal ``Vn=KF*Efd+(KN-KF)*max(Efd-EFDN,0)`` through ``s/(1+s*TF)``.
    The incremental rate-feedback slope is KF below the field-voltage knee and
    KN above it; the two line segments meet without an output discontinuity.

    Five states store sensed voltage, phase memory, amplifier output, exciter
    field voltage and feedback memory. At a positive initial field voltage,
    amplifier output is ``Vfe0/(KR*Efd0)``. Reference and phase memory initialize
    from that amplifier demand, while feedback memory stores Vn(Efd0). The lower
    excitation gate must permit the operating demand. The unexcited black-start
    point does not determine this reference and is outside this initialization.

    Inputs are generator field current, additive overexcitation voltage,
    stabilizing voltage, sensed voltage, reference voltage and additive minimum-
    excitation voltage. The output is generator field voltage. Signals use their
    connected per-unit field bases and all times are seconds. Positive sensing,
    phase, amplifier, field and feedback times select this realization; KR and
    the field-voltage knee are positive.

    :param vf: Shared native symbolic factory.
    :param name: Optional instance label.
    :return: Native five-state self-excited brushless controller.
    """
    label: str = 'EXAC3' if name is None else name
    template: RmsModelTemplate = build_brushless_exciter_base(vf, label)
    block: Block = template.block
    variables: dict[str, Var] = dict((variable.name, variable) for variable in block.get_all_vars())
    variables.update((variable.name, variable) for variable in block.event_dict)
    kr: Var = vf.add_var('KR_'+label)
    klv: Var = vf.add_var('KLV_'+label)
    lower_reference: Var = vf.add_var('VLV_'+label)
    knee: Var = vf.add_var('EFDN_'+label)
    upper_slope: Var = vf.add_var('KN_'+label)
    initial_amplifier: Var = vf.add_var('Amplifier0Pu_'+label)
    forcing: Var = vf.add_var('FieldForcingPu_'+label)
    block.event_dict[kr] = Const(1.0)
    block.event_dict[klv] = Const(.1)
    block.event_dict[lower_reference] = Const(.5)
    block.event_dict[knee] = Const(2.0)
    block.event_dict[upper_slope] = Const(.2)
    field_initial: Var = variables['avr.Efd0Pu_'+label]
    block.event_dict[initial_amplifier] = variables['avr.Vr0Pu_'+label]/(kr*field_initial)
    block.event_dict[variables['avr.limitedFirstOrder.Y0_'+label]] = initial_amplifier
    block.event_dict[variables['avr.leadLag.x_start[1]_'+label]] = initial_amplifier/variables['avr.Ka_'+label]
    block.event_dict[variables['avr.leadLag.y_start_'+label]] = initial_amplifier/variables['avr.Ka_'+label]
    block.event_dict[variables['avr.UsRef0Pu_'+label]] = variables['avr.Us0Pu_'+label]+initial_amplifier/variables['avr.Ka_'+label]
    field: Var = block.out_vars[0]
    low_slope: Var = variables['avr.Kf_'+label]
    nonlinear: Expr = low_slope*field+(upper_slope-low_slope)*sym.max(field-knee,Const(0.0))
    nonlinear_initial: Expr = low_slope*field_initial+(upper_slope-low_slope)*sym.max(field_initial-knee,Const(0.0))
    block.event_dict[variables['avr.derivative.k_'+label]] = Const(1.0)
    block.event_dict[variables['avr.derivative.x_start_'+label]] = nonlinear_initial
    current_equivalent: Var = variables['avr.add3.y_'+label]
    feedback_substitution: dict[Var, Expr] = dict(((current_equivalent, nonlinear),))
    memory: Var = variables['avr.derivative.x_'+label]
    for index, variable in enumerate(block.state_vars):
        if variable == memory:
            block.state_eqs[index] = block.state_eqs[index].subs(feedback_substitution)
        else:
            pass
    amplifier: Var = variables['avr.limitedFirstOrder.y_'+label]
    block.algebraic_vars.append(forcing)
    block.algebraic_eqs.append(forcing-kr*field*amplifier)
    block.init_eqs[forcing] = variables['avr.Vr0Pu_'+label]
    field_balance: Var = variables['avr.feedback1.y_'+label]
    feedback: Var = variables['avr.derivative.y_'+label]
    amplifier_drive: Var = variables['avr.limitedFirstOrder.Gk.y_'+label]
    for index, variable in enumerate(block.algebraic_vars):
        if variable == field_balance:
            block.algebraic_eqs[index] = block.algebraic_eqs[index].subs(dict(((amplifier, forcing),)))
        elif variable == feedback:
            block.algebraic_eqs[index] = block.algebraic_eqs[index].subs(feedback_substitution)
        elif variable == amplifier_drive:
            block.algebraic_eqs[index] = amplifier_drive-variables['avr.Ka_'+label]*sym.max(
                variables['avr.leadLag.y_'+label],klv*(lower_reference-field))
        else:
            pass
    template.comment = 'Self-excited brushless excitation with nonlinear field-voltage rate feedback'
    return template
