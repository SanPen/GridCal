# SPDX-License-Identifier: MPL-2.0
"""Native initialization and open-port preparation for shared brushless winding equations."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.exac1 import build_exac1_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import DeviceType


def build_brushless_exciter_base(vf: VarFactory, name: str) -> RmsModelTemplate:
    """Prepare the existing winding/rectifier realization for native controller composition.

    Initial port guesses derive from the declared operating-point parameters.
    The scaled phase-memory state stores its actual scaled equilibrium. Open
    inputs remain host-owned ports rather than extra algebraic unknowns, and
    unused diagnostic declarations are removed without changing physical equations.

    :param vf: Shared native symbolic factory.
    :param name: Unique instance label.
    :return: Five-state control component ready for feedback or limiter specialization.
    """
    template: RmsModelTemplate = build_exac1_template(vf, name)
    template.tpe = DeviceType.NoDevice
    block: Block = template.block
    variables: dict[str, Var] = dict((variable.name, variable) for variable in block.get_all_vars())
    variables.update((variable.name, variable) for variable in block.event_dict)
    block.init_eqs[block.in_vars[0]] = variables['avr.Ir0Pu_'+name]
    block.init_eqs[block.in_vars[3]] = variables['avr.Us0Pu_'+name]
    block.init_eqs[block.in_vars[4]] = variables['avr.UsRef0Pu_'+name]
    block.init_eqs[block.out_vars[0]] = variables['avr.Efd0Pu_'+name]
    block.init_eqs[variables['avr.leadLag.x_scaled[1]_'+name]] = (
        variables['avr.leadLag.a_end_'+name]*variables['avr.leadLag.x_start[1]_'+name])
    used: set[int] = set()
    for equations in (block.state_eqs, block.algebraic_eqs):
        for equation in equations:
            used.update(variable.uid for variable in equation.get_vars())
    inputs: set[int] = set(variable.uid for variable in block.in_vars)
    for variable in block.algebraic_vars:
        if variable.uid not in used and variable.uid not in inputs:
            block.init_eqs.pop(variable, None)
        else:
            pass
    block.algebraic_vars = [variable for variable in block.algebraic_vars
                            if variable.uid in used and variable.uid not in inputs]
    return template
