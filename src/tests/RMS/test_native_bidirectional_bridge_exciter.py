# SPDX-License-Identifier: MPL-2.0
"""Independent limited-regulator feedback, amplifier windup and actual supply scaling."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.exni import BridgeExcitationSupply, build_exni_template
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('supply',tuple(BridgeExcitationSupply))
def test_bidirectional_bridge_independent_transfer(supply: BridgeExcitationSupply) -> None:
    """Limited regulator feedback retains both filter poles and the separate sensing pole.

    :param supply: Terminal-fed or independent bridge.
    """
    block: Block = build_exni_template(VarFactory(),'bridge',tr=.03,ka=4.,ta=.07,kf=.06,tf1=.8,tf2=.2,supply=supply).block
    values: dict[int,float] = initialized_values(block)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    assert len(block.state_vars) == 4
    for frequency in (.02,.4,2.):
        s: complex = 2j*np.pi*frequency
        forward: complex = 4./(1.+.07*s)
        feedback: complex = .06*s/((1.+.8*s)*(1.+.2*s))
        expected: complex = -forward/((1.+.03*s)*(1.+forward*feedback))
        assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-8)


@pytest.mark.parametrize('supply',tuple(BridgeExcitationSupply))
@pytest.mark.parametrize('terminal',(0.,.6,1.3))
def test_bidirectional_bridge_live_supply(supply: BridgeExcitationSupply, terminal: float) -> None:
    """Only the terminal-powered output scales with actual terminal supply; regulator feedback stays upstream.

    :param supply: Explicit bridge supply.
    :param terminal: Actual terminal voltage after the event.
    """
    block: Block = build_exni_template(VarFactory(),'bridge',supply=supply).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[4].uid] = terminal
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    derivative: np.ndarray
    output: float
    derivative,output = evaluate_controller(block,values,states,1.)
    assert output == pytest.approx(terminal if supply == BridgeExcitationSupply.TERMINAL else 1.)
    np.testing.assert_allclose(derivative,0.,atol=1e-12)


def test_bidirectional_bridge_external_clip_preserves_windup() -> None:
    """An output clip limits field forcing without freezing the distinct raw amplifier memory."""
    block: Block = build_exni_template(VarFactory(),'bridge').block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'RawRegulatorPu_bridge')
    states[index] = 5.
    values[block.in_vars[1].uid] = 2.
    derivative: np.ndarray
    output: float
    derivative,output = evaluate_controller(block,values,states,0.)
    assert output == 5. and derivative[index] > 0.
    values[block.in_vars[1].uid] = .9
    derivative,output = evaluate_controller(block,values,states,1.)
    assert derivative[index] < 0.
