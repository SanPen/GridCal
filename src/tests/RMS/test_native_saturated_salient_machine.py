# SPDX-License-Identifier: MPL-2.0
"""Five-state salient-pole winding equations and resultant-flux saturation."""
from __future__ import annotations

import math
import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.synchronous_machines.gensae import build_gensae_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var, Const


@pytest.mark.parametrize('flux', (.7, 1.0, 1.2, 1.6))
def test_salient_both_axis_saturation(flux: float) -> None:
    """The single quadrature damper consumes the same power law as direct-axis excitation."""
    block: Block = build_gensae_template(VarFactory(),'salient').block.children[0]
    variables: dict[str,Var] = dict((variable.name,variable) for variable in block.get_all_vars())
    variables.update((variable.name,variable) for variable in block.event_dict)
    assert len(block.state_vars) == len(block.state_eqs) == len(block.diff_vars) == 5
    assert tuple(variable.name for variable in block.state_vars) == ('delta','omega','e1q','e2d','psi2q')
    assert not set(('e1d','e2q','XaqI1q','Xq_prime','Tq0_prime')).intersection(variables)
    values: dict[int,float] = dict((variable.uid, expression.value) for variable, expression in block.event_dict.items()
        if isinstance(expression,Const) and expression.value is not None)
    values[variables['Xq_2prime'].uid] = .23
    factor: float = .09*flux**(math.log(.38/.09)/math.log(1.2))
    values[variables['psi2'].uid] = flux
    values[variables['Se'].uid] = factor
    values[variables['Se_diag_ref'].uid] = factor
    equation: Expr = next(equation for variable,equation in zip(block.algebraic_vars,block.algebraic_eqs)
        if variable.name == 'Se')
    assert equation.eval_uid(values) == pytest.approx(0, abs=1e-12)
    values[variables['Iq'].uid] = .4
    values[variables['psi2q'].uid] = .3
    expected: float = ((1.75-.23)*.4-.3-factor*.3*(1.75-.15)/(1.8-.15))/.05
    assert block.state_eqs[-1].eval_uid(values) == pytest.approx(expected)
    direct: Expr = next(equation for variable,equation in zip(block.algebraic_vars,block.algebraic_eqs)
        if variable.name == 'XadIfd')
    assert variables['Se'] in direct.get_vars()
    assert variables['psi2d'] in direct.get_vars()


@pytest.mark.parametrize('saturation1,saturation12', ((0, .38), (.09, 0), (-.1, .3), (.3, .1)))
def test_salient_invalid_power_law(saturation1: float, saturation12: float) -> None:
    """Undefined exponents and nonphysical saturation pairs fail before activation."""
    with pytest.raises(ValueError):
        build_gensae_template(VarFactory(), saturation1=saturation1, saturation12=saturation12)
