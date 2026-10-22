# SPDX-License-Identifier: MPL-2.0
"""Independent cascaded brushless transfer, initialization and physical supply limits."""
from __future__ import annotations
import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ac7b import CascadedBrushlessParameters, build_ac7b_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from tests.RMS.test_native_turbine_governors import initialized_values, linearized_response, evaluate_controller


@pytest.mark.parametrize('outer_i,inner_i',((0.,0.),(0.,5.),(10.,0.),(10.,5.)))
@pytest.mark.parametrize('independent',(False,True))
def test_cascaded_brushless_equilibrium(outer_i: float, inner_i: float, independent: bool) -> None:
    """Both active integrals and proportional-only loops balance actual field and winding loss.

    :param outer_i: Voltage integral gain.
    :param inner_i: Field integral gain.
    :param independent: Exact zero potential gain selects independent unity supply.
    """
    block: Block = build_ac7b_template(VarFactory(),'cascade',CascadedBrushlessParameters(
        kir=outer_i,kia=inner_i,kp=0. if independent else 2.)).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 4+int(outer_i>0)+int(inner_i>0)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)


def test_cascaded_brushless_independent_transfer() -> None:
    """Voltage/current feedback and winding-current rate feedback produce the independently calculated transfer."""
    block: Block = build_ac7b_template(VarFactory(),'cascade',CascadedBrushlessParameters(
        kc=0.,kd=0.,ke=1.4,te=.7,se1=0.,se2=0.,kp=2.,kf1=.2,kf2=.1,kf3=.05,tf3=.1)).block
    values: dict[int,float] = initialized_values(block)
    for frequency in (.01,.1,1.,10.):
        s: complex = 2j*np.pi*frequency
        outer: complex = 20.+10./s+.05*s/(1.+.05*s)
        inner: complex = 2.+5./s
        plant: complex = 2.*inner/(1.4+.7*s+2.*inner*(.2+.1*1.4))
        expected: complex = -outer*plant/((1.+.02*s)*(1.+outer*plant*.05*s*1.4/(1.+.1*s)))
        assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=4e-7,abs=1e-8)


@pytest.mark.parametrize('independent',(False,True))
def test_cascaded_brushless_negative_forcing_floor(independent: bool) -> None:
    """A terminal supply collapse respects the separate negative forcing floor and unity-supply bypass.

    :param independent: Bypass terminal multiplication with exact zero KP.
    """
    block: Block = build_ac7b_template(VarFactory(),'cascade',CascadedBrushlessParameters(
        kp=0. if independent else 2.,kf3=0.,kdr=0.,kl=.2,kc=0.,kd=0.,se1=0.,se2=0.)).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    integral_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'FieldIntegralPu_cascade')
    states[integral_index] = -2.
    block.out_vars[0] = next(variable for variable in block.algebraic_vars if variable.name == 'FieldForcingPu_cascade')
    derivative: np.ndarray
    forcing: float
    derivative,forcing = evaluate_controller(block,values,states,1.)
    assert forcing == pytest.approx(-.2)
    values[block.in_vars[4].uid] = 0.
    derivative,forcing = evaluate_controller(block,values,states,1.)
    assert forcing == pytest.approx(-.2 if independent else 0.)


@pytest.mark.parametrize('reverse',(False,True))
def test_cascaded_brushless_saturation_sample_order(reverse: bool) -> None:
    """Magnetic loss passes through both actual samples regardless of their record order.

    :param reverse: Present the larger voltage first.
    """
    block: Block = build_ac7b_template(VarFactory(),'cascade',CascadedBrushlessParameters(kc=0.,kd=0.,
        e1=4. if reverse else 3.,se1=.3 if reverse else .1,e2=3. if reverse else 4.,se2=.1 if reverse else .3)).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    winding_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'InternalVoltagePu_cascade')
    block.out_vars[0] = next(variable for variable in block.algebraic_vars if variable.name == 'CurrentEquivalentPu_cascade')
    for voltage,saturation in ((3.,.1),(4.,.3)):
        states[winding_index] = voltage
        derivative: np.ndarray
        equivalent: float
        derivative,equivalent = evaluate_controller(block,values,states,1.)
        assert equivalent == pytest.approx(voltage*(1.+saturation))


@pytest.mark.parametrize('upper',(False,True))
def test_cascaded_brushless_winding_stops_recover(upper: bool) -> None:
    """Internal voltage and current-equivalent stops suppress only outward winding motion.

    :param upper: Exercise current ceiling rather than internal-voltage floor.
    """
    block: Block = build_ac7b_template(VarFactory(),'cascade',CascadedBrushlessParameters(
        kc=0.,kd=0.,kf1=0.,kf2=0.,kf3=0.,kdr=0.,se1=0.,se2=0.,vfemax=1.2,vemin=.2)).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    winding_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'InternalVoltagePu_cascade')
    integral_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'FieldIntegralPu_cascade')
    states[winding_index] = 1.2 if upper else .2
    states[integral_index] = 5. if upper else -5.
    derivative: np.ndarray
    field: float
    derivative,field = evaluate_controller(block,values,states,1.)
    assert derivative[winding_index] == 0.
    states[integral_index] = -1. if upper else 1.
    derivative,field = evaluate_controller(block,values,states,1.)
    assert derivative[winding_index] < 0. if upper else derivative[winding_index] > 0.


def test_cascaded_brushless_exact_disabled_paths() -> None:
    """Disabled sensing, integral, derivative and rate channels leave only the physical field memory."""
    block: Block = build_ac7b_template(VarFactory(),'cascade',CascadedBrushlessParameters(
        tr=0.,kir=0.,kia=0.,kdr=0.,tdr=0.,kf3=0.,tf3=0.,kp=0.)).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 1
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
