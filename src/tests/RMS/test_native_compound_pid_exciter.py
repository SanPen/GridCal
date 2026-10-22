# SPDX-License-Identifier: MPL-2.0
"""Compound supply loading and all PID limiter insertion topologies."""
from __future__ import annotations
import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.self_feedback_exciter import ExcitationLimiterLocation
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.st4c import CompoundExcitationSource, CompoundSupplementLocation
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ac8b import PidBrushlessExciterParameters, CompoundPidPowerCircuit
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ac8c import build_ac8c_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from tests.RMS.test_native_turbine_governors import initialized_values


@pytest.mark.parametrize('minimum',tuple(ExcitationLimiterLocation))
@pytest.mark.parametrize('maximum',tuple(ExcitationLimiterLocation))
@pytest.mark.parametrize('supplement',tuple(CompoundSupplementLocation))
def test_compound_pid_native_equilibrium(minimum: ExcitationLimiterLocation, maximum: ExcitationLimiterLocation,
                                        supplement: CompoundSupplementLocation) -> None:
    """Every gate location balances winding losses and all five memories.

    :param minimum: Minimum signal insertion.
    :param maximum: Maximum signal insertion.
    :param supplement: Supplement insertion.
    """
    block: Block = build_ac8c_template(VarFactory(),'compound',circuit=CompoundPidPowerCircuit(
        minimum_location=minimum,maximum_location=maximum,supplement_location=supplement)).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 5 and len(block.in_vars) == 10 and len(block.out_vars) == 5
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)


@pytest.mark.parametrize('source',tuple(CompoundExcitationSource))
def test_compound_pid_supply_uses_exciter_winding_current(source: CompoundExcitationSource) -> None:
    """Source bridge loading uses VFE rather than generator IFD, with independent analytical inversion.

    :param source: Compound or independent potential.
    """
    block: Block = build_ac8c_template(VarFactory(),'compound',PidBrushlessExciterParameters(se1=0.,se2=0.),
        CompoundPidPowerCircuit(kp=2.,ki=.3,xl=.2,theta=15.,kc1=.2,source=source)).block
    values: dict[int,float] = initialized_values(block)
    supply: Var = next(variable for variable in block.algebraic_vars if variable.name == 'SupplyPu_compound')
    equivalent: float = 1.+.577*.1+.1
    potential: float = abs(2.*np.exp(15j*np.pi/180.)*(1.+.1j)+.15j) if source == CompoundExcitationSource.TERMINAL else 2.
    expected: float = potential-.577*.2*equivalent
    assert values[supply.uid] == pytest.approx(expected)
    regulator: Var = next(variable for variable in block.state_vars if variable.name == 'RegulatorPu_compound')
    assert values[regulator.uid] == pytest.approx(equivalent/expected)


@pytest.mark.parametrize('minimum',tuple(ExcitationLimiterLocation))
@pytest.mark.parametrize('maximum',tuple(ExcitationLimiterLocation))
def test_compound_pid_disturbed_limiter_order(minimum: ExcitationLimiterLocation, maximum: ExcitationLimiterLocation) -> None:
    """Independent gate calculations verify limiter ordering before PID and before amplifier.

    :param minimum: Minimum signal insertion.
    :param maximum: Maximum signal insertion.
    """
    from tests.RMS.test_native_turbine_governors import evaluate_controller
    block: Block = build_ac8c_template(VarFactory(),'compound',PidBrushlessExciterParameters(kdr=0.),
        CompoundPidPowerCircuit(minimum_location=minimum,maximum_location=maximum)).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[1].uid] = 1.01
    values[block.in_vars[8].uid] = .02
    values[block.in_vars[9].uid] = -.005
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    integral: Var = next(variable for variable in block.state_vars if variable.name == 'IntegralPu_compound')
    regulator_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'RegulatorPu_compound')
    error: float = .01+(.02 if minimum == ExcitationLimiterLocation.REFERENCE_SUM else 0.)+(-.005 if maximum == ExcitationLimiterLocation.REFERENCE_SUM else 0.)
    if minimum == ExcitationLimiterLocation.REFERENCE_GATE:
        error = max(error,.02)
    else:
        pass
    if maximum == ExcitationLimiterLocation.REFERENCE_GATE:
        error = min(error,-.005)
    else:
        pass
    demand: float = 20.*error+values[integral.uid]
    if minimum == ExcitationLimiterLocation.OUTPUT_GATE:
        demand = max(demand,.02)
    else:
        pass
    if maximum == ExcitationLimiterLocation.OUTPUT_GATE:
        demand = min(demand,-.005)
    else:
        pass
    derivative: np.ndarray
    delivered: float
    derivative,delivered = evaluate_controller(block,values,states,1.)
    assert derivative[regulator_index] == pytest.approx((20.*demand-states[regulator_index])/.05)


def test_compound_pid_rejects_identically_zero_supply() -> None:
    """An absent potential circuit cannot initialize nonzero winding loss."""
    with pytest.raises(ValueError,match='zero potential'):
        build_ac8c_template(VarFactory(),circuit=CompoundPidPowerCircuit(kp=0.,ki=0.,source=CompoundExcitationSource.TERMINAL))
