# SPDX-License-Identifier: MPL-2.0
"""Two-axis power-law saturation and its zero-flux symbolic derivative."""
from __future__ import annotations

import math
import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.synchronous_machines.genroe import build_genroe_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const


@pytest.mark.parametrize('flux',(-.7,0.0,.7,1.0,1.2,1.6))
def test_round_rotor_power_law_saturation_samples_and_derivative(flux: float) -> None:
    """The saturation law fits both specified samples and stays differentiable at zero.

    :param flux: Resultant subtransient flux magnitude in per unit.
    """
    block: Block = build_genroe_template(VarFactory(),'round_rotor').block.children[0]
    values: dict[int,float] = dict()
    variables: dict[str,Var] = dict((variable.name,variable) for variable in block.get_all_vars())
    for collection in (block.parameters,block.event_dict):
        for variable,expression in collection.items():
            variables[variable.name] = variable
            if isinstance(expression,Const) and expression.value is not None:
                values[variable.uid] = expression.value
            else:
                pass
    exponent: float = math.log(.38/.09)/math.log(1.2)
    factor: float = .09*abs(flux)**exponent
    values[variables['psi2'].uid] = flux
    values[variables['Se'].uid] = factor
    values[variables['Se_diag_ref'].uid] = factor
    equation: Expr = next(equation for variable,equation in zip(block.algebraic_vars,block.algebraic_eqs)
        if variable.name == 'Se')
    assert equation.eval_uid(values) == pytest.approx(0,abs=1e-12)
    derivative: Expr = equation.diff(variables['psi2']).simplify()
    assert derivative.eval_uid(values) == pytest.approx(exponent*factor,abs=1e-12)
    # Both magnetic axes must consume the same resultant-flux factor.
    for variable,equation in zip(block.algebraic_vars,block.algebraic_eqs):
        if variable.name in ('XadIfd','XaqI1q'):
            assert variables['Se'] in equation.get_vars()
        else:
            pass
