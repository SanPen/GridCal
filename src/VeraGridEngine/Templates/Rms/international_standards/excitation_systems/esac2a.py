# SPDX-License-Identifier: MPL-2.0
"""High-response brushless excitation with takeover gates and a rotating-field current stop."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.common.brushless_field_limits import limit_brushless_field
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.esac1a import build_esac1a_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def build_esac2a_template(vf: VarFactory, name: str | None = None) -> RmsModelTemplate:
    """Build high-response alternator excitation with an internal field-current ceiling.

    A sensed-voltage lag, phase compensator and bounded amplifier drive the
    proportional inner loop ``KB*(Va-KH*Vfe)``. Minimum-excitation and maximum-
    excitation takeover gates act after that loop, followed by independent
    forcing limits. The field integrator has a zero lower voltage stop and an
    upper stop determined by Vfe reaching VFEMAX. Vfe includes linear resistance,
    excess-field saturation and live generator-current demagnetization. These
    directional stops block outward motion and permit inward recovery; they do
    not reset continuous field memory when the current-dependent ceiling moves.

    A diode bridge converts internal exciter voltage to generator field voltage
    through its live-current commutation characteristic. Filtered derivative
    feedback senses Vfe. Five states store voltage sensing, phase memory,
    amplifier output, internal field voltage and feedback memory. Initial
    amplifier demand is ``Vfe0*(KH+1/KB)``; gate demands and feedback memory
    initialize to Vfe0. The current stop and both takeover gates must admit this
    operating point. Positive resistance and nonnegative saturation make the
    field-current ceiling equivalent to the voltage bound
    ``(VFEMAX-KD*Ifd)/(KE+SE(VE))`` without dividing by its denominator.

    Inputs are generator field current, overexcitation takeover demand,
    supplementary voltage, sensed voltage, reference and minimum-excitation
    takeover demand. Outputs are field voltage, inner-loop demand before either
    gate and demand between gates. Absent limiters connect to their preceding
    live demand. Voltages use connected per-unit bases and times are seconds.
    Positive sensing, phase, amplifier, field and feedback times select this
    realization; KB and KE are positive and KH/KD are nonnegative.

    :param vf: Shared native symbolic factory.
    :param name: Optional instance label.
    :return: Native five-state high-response brushless excitation controller.
    """
    label: str = 'ESAC2A' if name is None else name
    template: RmsModelTemplate = build_esac1a_template(vf, label)
    block: Block = template.block
    variables: dict[str, Var] = dict((variable.name, variable) for variable in block.get_all_vars())
    variables.update((variable.name, variable) for variable in block.event_dict)
    kb: Var = vf.add_var('KB_'+label)
    kh: Var = vf.add_var('KH_'+label)
    initial_amplifier: Var = vf.add_var('Amplifier0Pu_'+label)
    demand: Var = vf.add_var('InnerDemandPu_'+label)
    block.event_dict[kb] = Const(10.0)
    block.event_dict[kh] = Const(.2)
    current_initial: Var = variables['avr.Vr0Pu_'+label]
    block.event_dict[initial_amplifier] = current_initial*(kh+Const(1.0)/kb)
    block.event_dict[variables['avr.limitedFirstOrder.Y0_'+label]] = initial_amplifier
    block.event_dict[variables['avr.leadLag.x_start[1]_'+label]] = initial_amplifier/variables['avr.Ka_'+label]
    block.event_dict[variables['avr.leadLag.y_start_'+label]] = initial_amplifier/variables['avr.Ka_'+label]
    block.event_dict[variables['avr.UsRef0Pu_'+label]] = variables['avr.Us0Pu_'+label]+initial_amplifier/variables['avr.Ka_'+label]
    block.algebraic_vars.append(demand)
    block.algebraic_eqs.append(demand-kb*(variables['avr.limitedFirstOrder.y_'+label]-kh*variables['avr.add3.y_'+label]))
    block.init_eqs[demand] = current_initial
    gated: Var = variables['MinimumGatePu_'+label]
    for index, variable in enumerate(block.algebraic_vars):
        if variable == gated:
            block.algebraic_eqs[index] = gated-sym.max(demand, block.in_vars[5])
        else:
            pass
    limit_brushless_field(block, vf, label, variables['FieldForcingPu_'+label], variables)
    block.out_vars[1] = demand
    template.comment = 'High-response brushless excitation with takeover gates and an internal field-current stop'
    return template
