# SPDX-License-Identifier: MPL-2.0
"""Independent PI/regulator/field transfer, field forcing and exact filter reductions."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.expic1 import PiCompoundFieldParameters, build_expic1_template
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, linearized_response, evaluate_controller


@pytest.mark.parametrize('field_time',(0.,.7))
@pytest.mark.parametrize('first_lag,second_lag',((.05,.03),(0.,.03),(.05,0.)))
def test_pi_compound_field_independent_transfer(field_time: float, first_lag: float, second_lag: float) -> None:
    """The proper two-pole regulator and bounded-regulator rate feedback retain their independently derived loop.

    :param field_time: Positive field time or direct forcing.
    :param first_lag: First regulator denominator time.
    :param second_lag: Second regulator denominator time.
    """
    block: Block = build_expic1_template(VarFactory(),'compound',PiCompoundFieldParameters(
        tr=.03,ka=4.,ta1=.1,ta2=first_lag,ta3=.02,ta4=second_lag,kf=.06,tf1=.8,tf2=.2,
        ke=1.4,te=field_time,se1=0.,se2=0.)).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 4+int(first_lag>0)+int(second_lag>0)+int(field_time>0)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    for frequency in (.02,.4,2.):
        s: complex = 2j*np.pi*frequency
        regulator: complex = 4.*(1.+.1*s)*(1.+.02*s)/(s*(1.+first_lag*s)*(1.+second_lag*s))
        feedback: complex = .06*s/((1.+.8*s)*(1.+.2*s))
        field: complex = 1./(1.4+field_time*s) if field_time>0 else 1.+0j
        expected: complex = -regulator*field/((1.+.03*s)*(1.+regulator*feedback))
        assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-8)


def test_pi_compound_field_forcing_limit_is_not_field_memory_limit() -> None:
    """A bounded forcing does not become a false field-memory stop when resistance is small."""
    block: Block = build_expic1_template(VarFactory(),'compound',PiCompoundFieldParameters(efdmax=2.,ke=.1,se1=0.,se2=0.)).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    field_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'EfdPu_compound')
    states[field_index] = 3.
    derivative: np.ndarray
    output: float
    derivative,output = evaluate_controller(block,values,states,1.)
    assert output == 3. and derivative[field_index] == pytest.approx((.1-.3)/.5)


def test_pi_compound_independent_pi_and_regulator_limits() -> None:
    """The PI's own stop blocks outward motion while downstream regulator clipping does not invent tracking."""
    block: Block = build_expic1_template(VarFactory(),'compound').block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    integral_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'PiIntegralPu_compound')
    states[integral_index] = 5.
    values[block.in_vars[1].uid] = 2.
    derivative: np.ndarray
    output: float
    derivative,output = evaluate_controller(block,values,states,1.)
    assert derivative[integral_index] == 0.
    values[block.in_vars[1].uid] = .99
    derivative,output = evaluate_controller(block,values,states,1.)
    assert derivative[integral_index] < 0.
    other: Block = build_expic1_template(VarFactory(),'separate',PiCompoundFieldParameters(vr1=100.,vr2=-100.,vrmax=.5,vrmin=-.5,ke=.1,se1=0.,se2=0.)).block
    bindings: dict[int,float] = initialized_values(other)
    other_states: np.ndarray = np.asarray([bindings[variable.uid] for variable in other.state_vars])
    other_integral: int = next(index for index,variable in enumerate(other.state_vars) if variable.name == 'PiIntegralPu_separate')
    regulator_index: int = next(index for index,variable in enumerate(other.state_vars) if variable.name == 'RegulatorLagPu_separate')
    other_states[regulator_index] = 5.
    bindings[other.in_vars[1].uid] = 2.
    derivative,output = evaluate_controller(other,bindings,other_states,1.)
    assert derivative[other_integral] > 0.
