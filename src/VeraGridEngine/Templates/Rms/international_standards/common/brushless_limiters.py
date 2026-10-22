# SPDX-License-Identifier: MPL-2.0
"""Selectable additive and takeover limiter insertion for brushless winding controls."""
from __future__ import annotations

from VeraGridEngine.Templates.Rms.dc_exciter import RotatingLimiterLocation
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var, BinOp
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def configure_brushless_limiters(block: Block, label: str,
                                 minimum_location: RotatingLimiterLocation,
                                 maximum_location: RotatingLimiterLocation) -> None:
    """Select signed error summation or cascaded takeover gates on a fresh graph.

    :param block: Fresh winding controller with six shared brushless ports.
    :param label: Instance label before public-name normalization.
    :param minimum_location: Additive error input or downstream high gate.
    :param maximum_location: Additive error input or downstream low gate.
    :raises ValueError: Invalid limiter insertion selector.
    """
    if not isinstance(minimum_location,RotatingLimiterLocation) or not isinstance(maximum_location,RotatingLimiterLocation):
        raise ValueError('Brushless limiter insertion requires an explicit selector')
    else:
        pass
    variables: dict[str,Var] = dict((variable.name,variable) for variable in block.get_all_vars())
    minimum: Var = block.in_vars[5]
    maximum: Var = block.in_vars[1]
    summation: Var = variables['avr.sum1.y_'+label]
    delivered_internal: Var = variables['avr.limiter.y_'+label]
    field: Var = variables['avr.integrator.y_'+label]
    minimum_gate: Var = variables['MinimumGatePu_'+label]
    forcing: Var = variables['FieldForcingPu_'+label]
    pre_gate: Var = block.out_vars[1]
    additive: Expr = Const(0.)
    if minimum_location == RotatingLimiterLocation.SUMMATION:
        additive = additive+minimum
        block.init_eqs[minimum] = Const(0.)
    else:
        pass
    if maximum_location == RotatingLimiterLocation.SUMMATION:
        additive = additive+maximum
        block.init_eqs[maximum] = Const(0.)
    else:
        pass
    for index,variable in enumerate(block.algebraic_vars):
        if variable == delivered_internal:
            # The physical upper stop is Vfe-based; remove the legacy stand-alone display ceiling.
            block.algebraic_eqs[index] = delivered_internal-sym.max(field,Const(0.))
        elif variable == summation:
            equation: Expr = block.algebraic_eqs[index]
            if isinstance(equation,BinOp) and equation.op == '-':
                block.algebraic_eqs[index] = summation-(equation.right+additive)
            else:
                raise ValueError('Brushless summation must be an explicit signal equation')
        elif variable == minimum_gate and minimum_location == RotatingLimiterLocation.SUMMATION:
            block.algebraic_eqs[index] = minimum_gate-pre_gate
        elif variable == forcing and maximum_location == RotatingLimiterLocation.SUMMATION:
            block.algebraic_eqs[index] = block.algebraic_eqs[index].subs(dict(((maximum,minimum_gate),)))
        else:
            pass
