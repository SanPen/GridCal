# SPDX-License-Identifier: MPL-2.0
"""Loaded diode inversion, independent PID transfer and winding current stops."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ac8b import PidBrushlessExciterParameters, initial_internal_exciter_voltage, build_ac8b_template
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import _esst3a_fex
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr
from tests.RMS.test_native_turbine_governors import initialized_values, linearized_response, evaluate_controller


@pytest.mark.parametrize('loading',(-.1,0.,.1,1.,3.))
def test_loaded_diode_inverse_each_conducting_region(loading: float) -> None:
    """Independent bridge reconstruction recovers the requested field in all open conducting regions.

    :param loading: Commutation loading from unloaded through final linear region.
    """
    voltage: Expr = initial_internal_exciter_voltage(Const(1.),Const(loading))
    internal: float = voltage.eval_uid(dict())
    delivered: Expr = voltage*_esst3a_fex(Const(loading)/voltage)
    assert delivered.eval_uid(dict()) == pytest.approx(1.,abs=1e-12)
    if loading == 1.:
        assert .433 < loading/internal < .75
    elif loading == 3.:
        assert .75 < loading/internal < 1.
    else:
        assert loading/internal <= .433


@pytest.mark.parametrize('integral,derivative,ta',((2.,.1,.07),(0.,.1,.07),(2.,0.,0.)))
def test_pid_brushless_independent_transfer(integral: float, derivative: float, ta: float) -> None:
    """The PID measures voltage error and drives independent amplifier and winding poles.

    :param integral: Integral gain or exact disabled channel.
    :param derivative: Filtered derivative gain or disabled channel.
    :param ta: Positive amplifier time or exact algebraic stage.
    """
    block: Block = build_ac8b_template(VarFactory(),'brushless',PidBrushlessExciterParameters(
        tr=.03,kpr=3.,kir=integral,kdr=derivative,tdr=.1,ka=4.,ta=ta,kc=0.,kd=0.,ke=1.4,te=.7,se1=0.,se2=0.)).block
    values: dict[int,float] = initialized_values(block)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    for frequency in (.02,.4,2.):
        s: complex = 2j*np.pi*frequency
        expected: complex = -(3.+integral/s+derivative*s/(1.+.1*s))*4./((1.+.03*s)*(1.+ta*s)*(1.4+.7*s))
        assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-7)


@pytest.mark.parametrize('commutation',(.1,1.,3.))
def test_pid_brushless_loaded_winding_equilibrium(commutation: float) -> None:
    """Delivered and internal field voltages remain distinct throughout bridge loading.

    :param commutation: Coefficient selecting each conducting region at initial unit current.
    """
    block: Block = build_ac8b_template(VarFactory(),'brushless',PidBrushlessExciterParameters(
        kc=commutation,vfemax=50.,vrmax=50.,vpidmax=50.,se1=0.,se2=0.)).block
    values: dict[int,float] = initialized_values(block)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    assert values[block.out_vars[0].uid] == 1.


def test_pid_brushless_current_dependent_winding_stop() -> None:
    """A current jump moves the ceiling without resetting continuous winding memory."""
    block: Block = build_ac8b_template(VarFactory(),'brushless',PidBrushlessExciterParameters(
        kd=1.,ke=1.,vfemax=3.,se1=0.,se2=0.)).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    winding: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'InternalVoltagePu_brushless')
    amplifier: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'RegulatorPu_brushless')
    states[winding] = 2.
    values[block.in_vars[3].uid] = 2.
    states[amplifier] = 5.
    derivative: np.ndarray
    field: float
    derivative,field = evaluate_controller(block,values,states,1.)
    assert derivative[winding] == 0.
    states[amplifier] = 0.
    derivative,field = evaluate_controller(block,values,states,1.)
    assert derivative[winding] < 0.


@pytest.mark.parametrize('voltage,saturation',((3.,.1),(4.,.3)))
def test_pid_brushless_magnetic_sample_losses(voltage: float, saturation: float) -> None:
    """Quadratic magnetic excess reproduces both independent calibration losses.

    :param voltage: Published internal-voltage sample.
    :param saturation: Corresponding excess-field factor.
    """
    block: Block = build_ac8b_template(VarFactory(),'brushless',PidBrushlessExciterParameters(vfemax=50.)).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    winding: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'InternalVoltagePu_brushless')
    states[winding] = voltage
    block.out_vars[0],block.out_vars[1] = block.out_vars[1],block.out_vars[0]
    derivative: np.ndarray
    equivalent: float
    derivative,equivalent = evaluate_controller(block,values,states,1.)
    assert equivalent == pytest.approx(voltage*(1.+saturation)+.1)


def test_pid_brushless_independent_pid_and_amplifier_stops() -> None:
    """The PID integral can recover before the separate amplifier leaves its upper stop."""
    block: Block = build_ac8b_template(VarFactory(),'brushless').block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    integral: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'IntegralPu_brushless')
    amplifier: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'RegulatorPu_brushless')
    states[integral] = 10.
    states[amplifier] = 5.
    values[block.in_vars[1].uid] = 2.
    derivative: np.ndarray
    field: float
    derivative,field = evaluate_controller(block,values,states,1.)
    assert derivative[integral] == 0. and derivative[amplifier] == 0.
    values[block.in_vars[1].uid] = .99
    derivative,field = evaluate_controller(block,values,states,1.)
    assert derivative[integral] < 0. and derivative[amplifier] == 0.
    states[integral] = 0.
    derivative,field = evaluate_controller(block,values,states,1.)
    assert derivative[amplifier] < 0.
