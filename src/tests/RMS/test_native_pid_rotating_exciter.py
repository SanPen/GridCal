# SPDX-License-Identifier: MPL-2.0
"""Independent PID/field transfer, equilibrium, state stops and windup checks."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.dc_exciter import DcExciterParameters
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.esac8b import build_esac8b_template
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('ki,kd',((0.,0.),(2.,0.),(0.,.3),(2.,.3)))
@pytest.mark.parametrize('instantaneous',(False,True))
def test_pid_field_equilibrium_and_transfer(ki: float, kd: float, instantaneous: bool) -> None:
    """The closed voltage-error loop has the specified parallel PID and linear field transfer.

    :param ki: Integral gain, including structural bypass.
    :param kd: Derivative gain, including structural bypass.
    :param instantaneous: Use exact algebraic sensing/amplification.
    """
    tr: float = 0. if instantaneous else .03
    ta: float = 0. if instantaneous else .08
    block: Block = build_esac8b_template(VarFactory(),'pid',DcExciterParameters(
        tr=tr,ta=ta,ka=3.,ke=1.4,te=.7,se1=0.,se2=0.),kp=4.,ki=ki,kd=kd,td=.12).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 1+int(ki>0)+int(kd>0)+2*int(not instantaneous)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    for frequency in (.01,.1,1.,10.):
        s: complex = 2j*np.pi*frequency
        expected: complex = -3.*(4.+ki/s+kd*s/(1.+.12*s))/((1.+tr*s)*(1.+ta*s)*(1.4+.7*s))
        assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=2e-7,abs=1e-8)


def test_pid_integral_winds_up_behind_limited_amplifier() -> None:
    """Only the amplifier state has a stop; PID integral memory continues accumulating error."""
    block: Block = build_esac8b_template(VarFactory(),'pid',DcExciterParameters(ka=2.,vrmax=3.),ki=4.).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[1].uid] = 11.
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    regulator_index: int = next(index for index,var in enumerate(block.state_vars) if var.name == 'RegulatorPu_pid')
    integral_index: int = next(index for index,var in enumerate(block.state_vars) if var.name == 'IntegralPu_pid')
    states[regulator_index] = 3.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[regulator_index] == 0.
    assert derivative[integral_index] == pytest.approx(40.)
    assert output == 1.
    # Reverse the voltage error to verify immediate inward recovery at the stop.
    values[block.in_vars[1].uid] = -9.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[regulator_index] < 0.
    assert derivative[integral_index] < 0.


def test_pid_field_lower_stop_and_saturation() -> None:
    """The field circuit balances quadratic loss and blocks only outward motion at zero field."""
    block: Block = build_esac8b_template(VarFactory(),'pid',DcExciterParameters(
        e1=.8,se1=.1,e2=1.2,se2=.4)).block
    values: dict[int,float] = initialized_values(block)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    states[-1] = 0.
    regulator_index: int = next(index for index,var in enumerate(block.state_vars) if var.name == 'RegulatorPu_pid')
    states[regulator_index] = -1.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[-1] == 0. and output == 0.
    states[regulator_index] = 1.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[-1] == pytest.approx(2.)


@pytest.mark.parametrize('kp,ki,kd,td',((0.,0.,0.,.1),(1.,1.,1.,0.),(-1.,1.,0.,.1),(1.,float('nan'),0.,.1)))
def test_pid_invalid_structure_is_rejected(kp: float, ki: float, kd: float, td: float) -> None:
    """Reject undefined steady control or improper/nonfinite derivative structures.

    :param kp: Proportional gain.
    :param ki: Integral gain.
    :param kd: Derivative gain.
    :param td: Filter time constant.
    """
    with pytest.raises(ValueError):
        build_esac8b_template(VarFactory(),kp=kp,ki=ki,kd=kd,td=td)
