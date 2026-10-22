# SPDX-License-Identifier: MPL-2.0
"""Selectable cascaded excitation gates and independently specified supply arrangements."""
from __future__ import annotations
import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.cascaded_brushless_circuit import CascadedBrushlessCircuit, CascadedLimiterLocation, CascadedPowerSupply
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.st4c import CompoundExcitationSource, CompoundSupplementLocation
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ac7b import CascadedBrushlessParameters
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ac7c import build_ac7c_template
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, linearized_response


@pytest.mark.parametrize('minimum',tuple(CascadedLimiterLocation)[:3])
@pytest.mark.parametrize('maximum',tuple(CascadedLimiterLocation))
@pytest.mark.parametrize('power_supply',tuple(CascadedPowerSupply))
def test_selectable_cascaded_native_equilibrium(minimum: CascadedLimiterLocation, maximum: CascadedLimiterLocation,
                                               power_supply: CascadedPowerSupply) -> None:
    """All native takeover locations balance the selected power source and both integral memories.

    :param minimum: Minimum location before or after voltage PID.
    :param maximum: Maximum location, including after field PI.
    :param power_supply: Potential-derived or self-excited supply.
    """
    block: Block = build_ac7c_template(VarFactory(),'selectable',circuit=CascadedBrushlessCircuit(
        kr=2.,minimum_location=minimum,maximum_location=maximum,power_supply=power_supply)).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.in_vars) == 10 and len(block.out_vars) == 6 and len(block.state_vars) == 6
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)


@pytest.mark.parametrize('power_supply',tuple(CascadedPowerSupply))
def test_selectable_cascaded_independent_transfer(power_supply: CascadedPowerSupply) -> None:
    """Self-excitation's live EFD multiplier contributes its own independently derived feedback term.

    :param power_supply: Rectified independent or self-excited power.
    """
    block: Block = build_ac7c_template(VarFactory(),'selectable',CascadedBrushlessParameters(
        kp=2.,kc=0.,kd=0.,ke=1.4,te=.7,se1=0.,se2=0.),CascadedBrushlessCircuit(
        kr=2.,power_supply=power_supply)).block
    values: dict[int,float] = initialized_values(block)
    frequency: float
    for frequency in (.01,.1,1.,10.):
        s: complex = 2j*np.pi*frequency
        outer: complex = 20.+10./s+.05*s/(1.+.05*s)
        inner: complex = 2.+5./s
        field_resistance: float = 0. if power_supply == CascadedPowerSupply.SELF_EXCITED else 1.4
        plant: complex = 2.*inner/(field_resistance+.7*s+2.*inner*(.2+.1*1.4))
        expected: complex = -outer*plant/((1.+.02*s)*(1.+outer*plant*.05*s*1.4/(1.+.1*s)))
        assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=5e-7,abs=1e-8)


@pytest.mark.parametrize('minimum',tuple(CascadedLimiterLocation)[:3])
@pytest.mark.parametrize('maximum',tuple(CascadedLimiterLocation))
@pytest.mark.parametrize('supplement',tuple(CompoundSupplementLocation))
def test_selectable_cascaded_disturbed_routes(minimum: CascadedLimiterLocation, maximum: CascadedLimiterLocation,
                                             supplement: CompoundSupplementLocation) -> None:
    """Independent stage arithmetic distinguishes all five takeover points and both supplement positions.

    :param minimum: Minimum insertion.
    :param maximum: Maximum insertion.
    :param supplement: Supplement insertion relative to input high gate.
    """
    from VeraGridEngine.Utils.Symbolic.symbolic import Var
    from tests.RMS.test_native_turbine_governors import evaluate_controller
    block: Block = build_ac7c_template(VarFactory(),'selectable',CascadedBrushlessParameters(
        kp=2.,kf1=0.,kf2=0.,kf3=0.,kdr=0.),CascadedBrushlessCircuit(
        minimum_location=minimum,maximum_location=maximum,supplement_location=supplement)).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[1].uid] = 1.01
    values[block.in_vars[2].uid] = .02
    values[block.in_vars[8].uid] = .03
    values[block.in_vars[9].uid] = .005
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    inner_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'FieldIntegralPu_selectable')
    equivalent: Var = next(variable for variable in block.algebraic_vars if variable.name == 'CurrentEquivalentPu_selectable')
    error: float = .01+(.03 if minimum == CascadedLimiterLocation.ERROR_SUM else 0.)+(.005 if maximum == CascadedLimiterLocation.ERROR_SUM else 0.)+(.02 if supplement == CompoundSupplementLocation.ERROR_SUM else 0.)
    if minimum == CascadedLimiterLocation.ERROR_GATE:
        error = max(error,.03)
    else:
        pass
    if supplement == CompoundSupplementLocation.AFTER_MINIMUM_GATE:
        error += .02
    else:
        pass
    if maximum == CascadedLimiterLocation.ERROR_GATE:
        error = min(error,.005)
    else:
        pass
    demand: float = min(5.,max(-5.,20.*error))
    if minimum == CascadedLimiterLocation.VOLTAGE_OUTPUT_GATE:
        demand = max(demand,.03)
    else:
        pass
    if maximum == CascadedLimiterLocation.VOLTAGE_OUTPUT_GATE:
        demand = min(demand,.005)
    else:
        pass
    demand = min(5.,max(-5.,2.*demand+states[inner_index]))
    if maximum == CascadedLimiterLocation.FIELD_OUTPUT_GATE:
        demand = min(demand,.005)
    else:
        pass
    expected: float = max(2.*demand,-.2*values[equivalent.uid])
    block.out_vars[0] = next(variable for variable in block.algebraic_vars if variable.name == 'FieldForcingPu_selectable')
    derivative: np.ndarray
    result: float
    derivative,result = evaluate_controller(block,values,states,1.)
    assert result == pytest.approx(expected)
