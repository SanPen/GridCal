# SPDX-License-Identifier: MPL-2.0
"""Independent loaded-transformer field response and forcing-capability placement checks."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.thevenin_exciter import CompoundCapabilityLocation, TheveninExciterParameters, build_thevenin_exciter
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('location',tuple(CompoundCapabilityLocation))
@pytest.mark.parametrize('frequency',(.02,.2,2.))
def test_thevenin_exciter_independent_field_loop(location: CompoundCapabilityLocation, frequency: float) -> None:
    """Both inactive-capability structures match the independently closed regulator/field/washout response.

    :param location: Physical forcing-capability location.
    :param frequency: Perturbation frequency in hertz.
    """
    block: Block = build_thevenin_exciter(VarFactory(),'compound',location).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 4
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    s: complex = 2j*np.pi*frequency
    forward: complex = 20./((1.+.05*s)*(1.+.5*s))
    feedback: complex = .05*s/(1.+s)
    expected: complex = -forward/((1.+.02*s)*(1.+forward*feedback))
    assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-8)


@pytest.mark.parametrize('location,expected',((CompoundCapabilityLocation.TOTAL_FORCING,2.),(CompoundCapabilityLocation.COMPOUND_SUPPLY,4.)))
def test_thevenin_capability_location_changes_field_forcing(location: CompoundCapabilityLocation, expected: float) -> None:
    """The compound-supply bound permits added regulator forcing while the total-forcing bound clips their sum.

    :param location: Physical capability location.
    :param expected: Independent initial field acceleration after regulator forcing changes.
    """
    block: Block = build_thevenin_exciter(VarFactory(),'compound',location,TheveninExciterParameters(tr=0.,ta=0.,kp=4.)).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 2
    values[block.in_vars[1].uid] = 1.05
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[-1] == pytest.approx(expected)
    assert output == 1.


@pytest.mark.parametrize('location',tuple(CompoundCapabilityLocation))
def test_thevenin_collapsed_supply_is_finite(location: CompoundCapabilityLocation) -> None:
    """The direct loaded-voltage radicand remains finite, including its Jacobian, at collapsed transformer potential.

    :param location: Physical capability location.
    """
    block: Block = build_thevenin_exciter(VarFactory(),'compound',location).block
    values: dict[int,float] = initialized_values(block)
    for port in block.in_vars[3:7]:
        values[port.uid] = 0.
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,1.)
    assert np.all(np.isfinite(derivative))
    loaded = next(equation for variable,equation in zip(block.algebraic_vars,block.algebraic_eqs) if variable.name == 'LoadedSupplyPu_compound')
    assert np.isfinite(loaded.diff(block.in_vars[3]).eval_uid(values))
    assert output == 1.
