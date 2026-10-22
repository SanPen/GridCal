# SPDX-License-Identifier: MPL-2.0
"""Brushless excitation with shaped exciter-field feedback and selectable limiters."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.dc_exciter import RotatingLimiterLocation
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.esac1a import build_esac1a_template
from VeraGridEngine.Templates.Rms.international_standards.common.brushless_field_limits import limit_brushless_field
from VeraGridEngine.Templates.Rms.international_standards.common.brushless_limiters import configure_brushless_limiters
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def build_ac5c_template(vf: VarFactory, name: str | None = None,
                        minimum_location: RotatingLimiterLocation = RotatingLimiterLocation.SUMMATION,
                        maximum_location: RotatingLimiterLocation = RotatingLimiterLocation.SUMMATION) -> RmsModelTemplate:
    """Build brushless field regulation with two-stage rate-feedback shaping.

    A voltage transducer and independently powered bounded amplifier drive a
    rotating excitation alternator. Minimum/maximum signals independently enter
    as signed voltage-error additions or as high/low takeover gates after the
    amplifier. The high gate precedes the low gate. Field forcing then balances
    linear resistance, magnetic saturation and generator-current demagnetization.
    Field memory has a lower zero stop and an upper field-current-equivalent
    ceiling; outward motion stops while inward recovery remains possible.

    A loaded diode bridge converts internal exciter voltage to delivered field
    voltage. Feedback senses resistive plus magnetic field loss before adding
    current demagnetization. Its washout KF*s/(1+s*TF1) is followed by the phase
    shaper (1+s*TF3)/(1+s*TF2). This shaper belongs in the feedback path; there is
    no forward voltage-error phase compensator. Generator-current changes thus
    affect the field balance without directly entering the feedback sensor.

    Five states store sensed voltage, amplifier output, internal field voltage,
    washout memory and feedback-shaper memory. The loaded rectifier and field
    losses determine operating-point amplifier forcing; both feedback outputs
    initialize to zero. Inputs are field current, maximum limiter, stabilizer,
    sensed voltage, reference and minimum limiter. Outputs are delivered field,
    demand before the high gate and demand before the low gate. An absent
    additive limiter supplies zero; an absent takeover uses its preceding demand.
    Signals use compatible per-unit field bases and seconds. Positive physical
    lag times select this realization; automatic source calibration is excluded.

    :param vf: Shared native symbolic factory.
    :param name: Optional unique instance label.
    :param minimum_location: Additive or high-gate minimum insertion.
    :param maximum_location: Additive or low-gate maximum insertion.
    :return: Native five-state brushless field controller.
    :raises ValueError: Invalid limiter insertion selectors.
    """
    label: str = 'AC5C' if name is None else name
    template: RmsModelTemplate = build_esac1a_template(vf,label)
    block: Block = template.block
    variables: dict[str,Var] = dict((variable.name,variable) for variable in block.get_all_vars())
    variables.update((variable.name,variable) for variable in block.event_dict)
    current_loss: Var = variables['avr.add3.y_'+label]
    derivative: Var = variables['avr.derivative.y_'+label]
    phase: Var = variables['avr.leadLag.y_'+label]
    error: Var = variables['avr.feedback.y_'+label]
    loss: Var = vf.add_var('FieldLossPu_'+label)
    kd: Var = variables['avr.Kd_'+label]
    block.algebraic_vars.append(loss)
    block.algebraic_eqs.append(loss-(current_loss-kd*block.in_vars[0]))
    loss0: Expr = variables['avr.Vr0Pu_'+label]-kd*variables['avr.Ir0Pu_'+label]
    block.init_eqs[loss] = loss0
    block.event_dict[variables['avr.derivative.x_start_'+label]] = loss0
    block.event_dict[variables['avr.leadLag.x_start[1]_'+label]] = Const(0.)
    block.event_dict[variables['avr.leadLag.y_start_'+label]] = Const(0.)
    phase_state: Var = variables['avr.leadLag.x_scaled[1]_'+label]
    block.init_eqs[phase_state] = Const(0.)
    for index,variable in enumerate(block.state_vars):
        if variable == variables['avr.derivative.x_'+label]:
            block.state_eqs[index] = block.state_eqs[index].subs(dict(((current_loss,loss),)))
        elif variable == phase_state:
            block.state_eqs[index] = block.state_eqs[index].subs(dict(((error,derivative),)))
        else:
            pass
    forcing: Var = variables['FieldForcingPu_'+label]
    minimum_gate: Var = variables['MinimumGatePu_'+label]
    for index,variable in enumerate(block.algebraic_vars):
        if variable == derivative:
            block.algebraic_eqs[index] = block.algebraic_eqs[index].subs(dict(((current_loss,loss),)))
        elif variable == phase:
            block.algebraic_eqs[index] = block.algebraic_eqs[index].subs(dict(((error,derivative),)))
        elif variable == error:
            block.algebraic_eqs[index] = error-(variables['avr.sum1.y_'+label]-phase)
        elif variable == variables['avr.limitedFirstOrder.Gk.y_'+label]:
            block.algebraic_eqs[index] = block.algebraic_eqs[index].subs(dict(((phase,error),)))
        elif variable == forcing:
            block.algebraic_eqs[index] = forcing-sym.min(minimum_gate,block.in_vars[1])
        else:
            pass
    # This circuit has amplifier bounds, without a second independent forcing clip.
    block.event_dict.pop(variables['BridgeVRMAX_'+label])
    block.event_dict.pop(variables['BridgeVRMIN_'+label])
    limit_brushless_field(block,vf,label,forcing,variables)
    configure_brushless_limiters(block,label,minimum_location,maximum_location)
    template.comment = 'Brushless excitation with shaped field feedback and selectable limiter insertion'
    return template
