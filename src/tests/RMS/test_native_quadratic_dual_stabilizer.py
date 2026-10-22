# SPDX-License-Identifier: MPL-2.0
"""Independent quadratic dual-input transfer and exact zero-time equilibrium checks."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.power_system_stabilizers.pss3b import QuadraticDualStabilizerParameters, build_pss3b_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const
from tests.RMS.test_native_turbine_governors import initialized_values, linearized_response


@pytest.mark.parametrize('path',(0,1))
@pytest.mark.parametrize('common_time',(0.,.5))
@pytest.mark.parametrize('frequency',(.02,.4,2.))
def test_quadratic_dual_independent_transfer(path: int, common_time: float, frequency: float) -> None:
    """Each independent measured path retains its own gain/filter and both quadratic phase ratios.

    :param path: Independently perturbed measurement channel.
    :param common_time: Common washout time, including structural bypass.
    :param frequency: Perturbation frequency in hertz.
    """
    block: Block = build_pss3b_template(VarFactory(),'dual',QuadraticDualStabilizerParameters(washout_times=(10.,12.,common_time))).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == (8 if common_time == 0 else 9)
    if path == 1:
        block.in_vars[0],block.in_vars[1] = block.in_vars[1],block.in_vars[0]
    else:
        pass
    s: complex = 2j*np.pi*frequency
    gain: float = 1. if path == 0 else -.5
    lag: float = .02 if path == 0 else .03
    washout: float = 10. if path == 0 else 12.
    expected: complex = gain/(1.+lag*s)*washout*s/(1.+washout*s)*((1.+.1*s+.01*s*s)/(1.+.2*s+.02*s*s))**2
    if common_time > 0:
        expected *= common_time*s/(1.+common_time*s)
    else:
        pass
    assert linearized_response(block,values,0.,frequency) == pytest.approx(expected,rel=2e-7,abs=1e-9)


def test_quadratic_dual_all_time_bypasses_preserve_nonzero_constant_bias() -> None:
    """A fully bypassed measurement path initializes its real DC bias instead of inventing zero washout output."""
    block: Block = build_pss3b_template(VarFactory(),'dual',QuadraticDualStabilizerParameters(
        transducer_times=(0.,0.),washout_times=(0.,0.,0.),upper=1.,lower=-1.)).block
    block.init_eqs[block.in_vars[0]] = Const(.3)
    block.init_eqs[block.in_vars[1]] = Const(.4)
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 4
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    assert values[block.out_vars[0].uid] == pytest.approx(.1)


def test_quadratic_dual_rejects_improper_phase_polynomial() -> None:
    """A quadratic numerator cannot be retained above a first-order denominator using a fake numerical derivative."""
    with pytest.raises(ValueError,match='proper'):
        build_pss3b_template(VarFactory(),parameters=QuadraticDualStabilizerParameters(coefficients=(.1,.01,.2,0.,.1,.01,.2,.02)))
