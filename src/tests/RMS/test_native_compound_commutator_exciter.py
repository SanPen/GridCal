# SPDX-License-Identifier: MPL-2.0
"""Compound commutator supply, PID transfer, limiter placement and directional stops."""
from __future__ import annotations
import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.dc_exciter import DcExciterParameters, RotatingLimiterLocation
from VeraGridEngine.Templates.Rms.compound_excitation_supply import CompoundSupplyParameters
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.st4c import CompoundExcitationSource
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.dc4c import build_dc4c_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from tests.RMS.test_native_turbine_governors import initialized_values, linearized_response, evaluate_controller


@pytest.mark.parametrize('minimum',tuple(RotatingLimiterLocation))
@pytest.mark.parametrize('maximum',tuple(RotatingLimiterLocation))
@pytest.mark.parametrize('source',tuple(CompoundExcitationSource))
def test_compound_commutator_equilibrium(minimum: RotatingLimiterLocation, maximum: RotatingLimiterLocation,
                                         source: CompoundExcitationSource) -> None:
    """Loaded supply and all six memories balance for every physical topology.

    :param minimum: Minimum signal location.
    :param maximum: Maximum signal location.
    :param source: Independent or terminal compound potential.
    """
    block: Block = build_dc4c_template(VarFactory(),'commutator',minimum_location=minimum,maximum_location=maximum,
        supply_parameters=CompoundSupplyParameters(kp=2.,ki=.1,xl=.2,theta=10.,kc=.1,source=source)).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 6 and len(block.in_vars) == 9 and len(block.out_vars) == 3
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)


def test_compound_commutator_independent_transfer() -> None:
    """The unsaturated supply-scaled PID loop includes delivered-field washout feedback."""
    block: Block = build_dc4c_template(VarFactory(),'commutator',DcExciterParameters(
        tr=.03,ta=.08,ka=3.,ke=1.4,te=.7,kf=.2,tf=.4,se1=0.,se2=0.,vrmax=10.,vrmin=-10.),
        kp=4.,ki=2.,kd=.3,td=.12,supply_parameters=CompoundSupplyParameters(kp=2.)).block
    values: dict[int,float] = initialized_values(block)
    for frequency in (.01,.1,1.,10.):
        s: complex = 2j*np.pi*frequency
        forward: complex = 6.*(4.+2./s+.3*s/(1.+.12*s))/((1.+.08*s)*(1.4+.7*s))
        expected: complex = -forward/((1.+.03*s)*(1.+forward*.2*s/(1.+.4*s)))
        assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-8)


def test_compound_commutator_supply_load_and_collapse() -> None:
    """Winding current loads the source bridge and zero supply preserves a decaying field memory."""
    block: Block = build_dc4c_template(VarFactory(),'commutator',DcExciterParameters(ke=1.4,se1=0.,se2=0.),
        supply_parameters=CompoundSupplyParameters(kp=2.,kc=.2,source=CompoundExcitationSource.TERMINAL)).block
    values: dict[int,float] = initialized_values(block)
    supply: Var = next(variable for variable in block.algebraic_vars if variable.name == 'SupplyPu_commutator')
    assert values[supply.uid] == pytest.approx(2.-.577*.2*1.4)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    values[block.in_vars[3].uid] = 0.
    derivative: np.ndarray
    field: float
    derivative,field = evaluate_controller(block,values,states,1.)
    field_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'EfdPu_commutator')
    assert field == pytest.approx(1.) and derivative[field_index] < 0.


def test_compound_commutator_signed_additive_maximum() -> None:
    """The maximum limiter opposes reference while the minimum limiter raises it."""
    block: Block = build_dc4c_template(VarFactory(),'commutator',DcExciterParameters(kf=0.,ka=3.,vrmin=-5.,vrmax=5.),kd=0.).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    integral_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'IntegralPu_commutator')
    values[block.in_vars[8].uid] = .1
    derivative: np.ndarray
    field: float
    derivative,field = evaluate_controller(block,values,states,1.)
    assert derivative[integral_index] == pytest.approx(-.1)
    values[block.in_vars[7].uid] = .2
    derivative,field = evaluate_controller(block,values,states,1.)
    assert derivative[integral_index] == pytest.approx(.1)
