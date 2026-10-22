# SPDX-License-Identifier: MPL-2.0
"""Live bridge-supply and reverse-field-current behavior of a static exciter."""
from __future__ import annotations

import numpy as np
import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.scrx import build_scrx_template
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller


@pytest.mark.parametrize('independent', (0.0,1.0))
@pytest.mark.parametrize('terminal_voltage', (0.0,.6,1.3))
@pytest.mark.parametrize('field_current,resistance', ((1.0,0.0),(-.2,0.0),(1.0,10.0),(-.2,10.0),(0.0,10.0)))
def test_rectifier_source_selection_and_crowbar(independent: float, terminal_voltage: float,
                                               field_current: float, resistance: float) -> None:
    """Supply sag scales the bridge, while negative current selects the discharge path.

    :param independent: Unity for independent supply; zero for terminal-bus supply.
    :param terminal_voltage: Live terminal voltage, including complete collapse.
    :param field_current: Air-gap field-current equivalent.
    :param resistance: Crowbar-to-field resistance ratio; zero allows reverse current.
    """
    block: Block = build_scrx_template(VarFactory(),'bridge').block
    values: dict[int,float] = initialized_values(block)
    for variable in block.event_dict:
        if variable.name == 'avr.CSwitch_bridge':
            values[variable.uid] = independent
        elif variable.name == 'avr.RcToRfd_bridge':
            values[variable.uid] = resistance
        else:
            pass
    values[block.in_vars[6].uid] = terminal_voltage
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,field_current)
    expected: float
    if resistance > 0 and field_current <= 0:
        expected = -resistance*field_current
    else:
        expected = states[0]*(independent+(1-independent)*terminal_voltage)
    assert output == pytest.approx(expected)
    assert np.all(np.isfinite(derivative))


def test_instantaneous_rectifier_regulator_has_no_inverse_time() -> None:
    """The zero-time regulator removes one state without an epsilon approximation."""
    block: Block = build_scrx_template(VarFactory(),'bridge',exciter_time=0).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,1.0)
    assert len(block.state_vars) == 1
    assert output == pytest.approx(1.0)
    np.testing.assert_allclose(derivative,0,atol=1e-12)


@pytest.mark.parametrize('loading,expected,slope', (
    (-1.0, 1.0, 0.0), (0.0, 1.0, 0.0), (.2, 1-.577*.2, -.577),
    (.433, 1-.577*.433, -.577), (.5, np.sqrt(.5), -.5/np.sqrt(.5)),
    (.75, .433, -1.732), (.9, .1732, -1.732), (1.0, 0.0, -1.732),
    (1.1, 0.0, 0.0), (10000.0, 0.0, 0.0),
))
def test_rectifier_curve_and_jacobian_all_regions(loading: float, expected: float, slope: float) -> None:
    """Blocked square-root branches remain finite in both function and symbolic Jacobian."""
    from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import _esst3a_fex
    from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var
    current: Var = VarFactory().add_var('NormalizedCurrent')
    factor: Expr = _esst3a_fex(current)
    derivative: Expr = factor.diff(current).simplify()
    values: dict[int,float] = dict(((current.uid, loading),))
    assert factor.eval_uid(values) == pytest.approx(expected, abs=1e-12)
    assert derivative.eval_uid(values) == pytest.approx(slope, abs=1e-12)
