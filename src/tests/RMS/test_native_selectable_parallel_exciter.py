# SPDX-License-Identifier: MPL-2.0
"""Independent sum/gate choices must select channels only on strict takeover."""
from __future__ import annotations
import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.self_feedback_exciter import ExcitationLimiterLocation
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.st5b import ParallelChannelExciterParameters
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.st5c import build_st5c_template
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller


@pytest.mark.parametrize('minimum,maximum,expected',((1,1,.0425),(1,2,.17),(2,1,.1),(2,2,.17)))
def test_selectable_parallel_channels(minimum: int, maximum: int, expected: float) -> None:
    """Summed signals change common demand while only gates select limiter memories.

    :param minimum: Minimum signal location.
    :param maximum: Maximum signal location.
    :param expected: Independently calculated selected channel demand.
    """
    block: Block = build_st5c_template(VarFactory(),'selectable',ParallelChannelExciterParameters(
        minimum_location=ExcitationLimiterLocation(minimum),maximum_location=ExcitationLimiterLocation(maximum))).block
    values: dict[int,float] = initialized_values(block)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    values[block.in_vars[1].uid] = 1.05
    values[block.in_vars[5].uid] = .1
    values[block.in_vars[6].uid] = .02
    states: np.ndarray = np.asarray([0. if variable.name.startswith('Normal') else .1 if variable.name.startswith('Minimum') else
        .2 if variable.name.startswith('Maximum') else values[variable.uid] for variable in block.state_vars])
    block.out_vars[0] = next(variable for variable in block.algebraic_vars if variable.name == 'SelectedDemandPu_selectable')
    derivative: np.ndarray
    result: float
    derivative,result = evaluate_controller(block,values,states,1.)
    assert result == pytest.approx(expected)
