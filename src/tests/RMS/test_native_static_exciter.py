# SPDX-License-Identifier: MPL-2.0
"""Compound-source rectifier behavior and bounded static-exciter dynamics."""
from __future__ import annotations

import numpy as np
import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards import build_international_standard_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.exst2 import CompoundExciterKind, build_exst2_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const
from VeraGridEngine.enumerations import InternationalStandardModel
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller


def test_compound_exciter_initial_field_balance() -> None:
    """The actual bridge supply determines regulator and voltage-reference initialization."""
    block: Block = build_international_standard_template(InternationalStandardModel.EXST2,VarFactory(),'static').block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 4
    assert len(block.algebraic_vars) == len(block.algebraic_eqs)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0,atol=1e-12)
    assert values[block.out_vars[0].uid] == 1.0


@pytest.mark.parametrize('loading,bridge',((-.1,1.0),(0,1.0),(.2,.8846),(.433,.750159),
    (.5,np.sqrt(.5)),(.75,.433),(.9,.1732),(1.0,0.0),(1.2,0.0)))
def test_rectifier_loading_regions_drive_field_equation(loading: float,bridge: float) -> None:
    """All five rectifier regions, including exact boundaries, act on the field integrator."""
    block: Block = build_exst2_template(VarFactory(),commutation_gain=1.0).block
    # Unit loading gain makes exact branch-boundary inputs survive floating-point evaluation.
    block.init_eqs[block.in_vars[7]] = Const(.1)
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[7].uid] = loading
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,1.0)
    assert derivative[-1] == pytest.approx((states[-2]+bridge-1)/.5,abs=1e-12)
    assert output == 1


def test_collapsed_compound_supply_remains_finite() -> None:
    """A zero potential produces zero bridge voltage without singular loading arithmetic."""
    block: Block = build_exst2_template(VarFactory()).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[3].uid] = 0
    values[block.in_vars[4].uid] = 0
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,1.0)
    assert np.all(np.isfinite(derivative))
    assert derivative[-1] == pytest.approx((states[-2]-1.)/.5)
    assert output == 1
    # The symbolic norm derivative must also remain usable by Newton at zero.
    potential_equation = next(equation for variable,equation in zip(block.algebraic_vars,block.algebraic_eqs)
        if variable.name.startswith('PotentialPu_'))
    assert np.isfinite(potential_equation.diff(block.in_vars[3]).eval_uid(values))


def test_independent_supply_and_zero_lag_structures() -> None:
    """A declared independent source stays at unity when terminal voltage collapses."""
    block: Block = build_exst2_template(VarFactory(),transducer_time=0,regulator_time=0,
        potential_gain=0,current_gain=0).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 2
    values[block.in_vars[3].uid] = 0
    values[block.in_vars[4].uid] = 0
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,1.0)
    np.testing.assert_allclose(derivative,0,atol=1e-12)
    assert output == 1


@pytest.mark.parametrize('kind',tuple(CompoundExciterKind))
@pytest.mark.parametrize('frequency',(.01,.1,1.,10.))
def test_compound_coupling_has_independent_closed_loop_response(kind: CompoundExciterKind, frequency: float) -> None:
    """Addition and multiplication realize different amplifier gains inside the field-rate feedback loop.

    :param kind: Explicit bridge coupling and limiter structure.
    :param frequency: Small-signal perturbation frequency in hertz.
    """
    from tests.RMS.test_native_turbine_governors import linearized_response
    block: Block = build_exst2_template(VarFactory(),potential_gain=2.,current_gain=.2,
        commutation_gain=.1,kind=kind).block
    values: dict[int,float] = initialized_values(block)
    # An absent high-value limiter must be strictly inactive for linearization.
    if kind == CompoundExciterKind.GATED_MULTIPLICATIVE_BRIDGE:
        values[block.in_vars[8].uid] = -10.
    else:
        pass
    s: complex = 2j*np.pi*frequency
    potential: float = np.sqrt(4.+.01)
    bridge: float = potential*(1.-.577*.1/potential)
    coupling: float = 1. if kind == CompoundExciterKind.ADDITIVE_BRIDGE else bridge
    forward: complex = coupling*20./((1.+.05*s)*(1.+.5*s))
    feedback: complex = .05*s/(1.+s)
    expected: complex = -forward/((1.+.02*s)*(1.+forward*feedback))
    assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=2e-7,abs=1e-8)


def test_gated_compound_limiter_acts_before_regulator() -> None:
    """Minimum excitation selects a voltage-error demand rather than adding a supplementary bias."""
    block: Block = build_exst2_template(VarFactory(),regulator_gain=2.,transducer_time=0.,
        regulator_time=0.,potential_gain=0.,current_gain=0.,kind=CompoundExciterKind.GATED_MULTIPLICATIVE_BRIDGE).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[2].uid] = .1
    values[block.in_vars[8].uid] = .8
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[-1] == pytest.approx(1.2)
    assert output == 1.
