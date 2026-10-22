# SPDX-License-Identifier: MPL-2.0
"""Directional rotating-field stops expressed through a monotone field-current equivalent."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def limit_brushless_field(block: Block, vf: VarFactory, label: str,
                          forcing: Var, variables: dict[str, Var]) -> None:
    """Apply non-windup lower voltage and upper field-current stops.

    For positive resistance and nonnegative excess-field saturation, the upper
    voltage bound ``(VFEMAX-KD*Ifd)/(KE+SE(VE))`` is equivalently detected by
    ``Vfe >= VFEMAX``. This form avoids division by a disabled saturation term.
    A current jump can move the ceiling past continuous field memory; outward
    motion is then blocked and inward recovery remains active. This directional
    stop does not introduce a discontinuous field-memory reset.

    :param block: Native brushless controller with an owned rotating-field state.
    :param vf: Shared symbolic factory.
    :param label: Instance label used by the common field circuit.
    :param forcing: Selected regulator forcing before field losses.
    :param variables: Explicit lookup of common field symbols and event parameters.
    """
    lower: Var = vf.add_var('VEMIN_'+label)
    upper: Var = vf.add_var('VFEMAX_'+label)
    block.event_dict[lower] = Const(0.0)
    block.event_dict[upper] = Const(5.0)
    field: Var = variables['avr.integrator.y_'+label]
    current_equivalent: Var = variables['avr.add3.y_'+label]
    raw: Expr = (forcing-current_equivalent)*variables['avr.integrator.k_'+label]
    lower_stop: Expr = (Const(1.0)-sym.heaviside(field-lower))*sym.heaviside(-raw)
    upper_stop: Expr = (Const(1.0)-sym.heaviside(upper-current_equivalent))*sym.heaviside(raw)
    for index, variable in enumerate(block.state_vars):
        if variable == field:
            block.state_eqs[index] = raw*(Const(1.0)-lower_stop)*(Const(1.0)-upper_stop)
        else:
            pass
