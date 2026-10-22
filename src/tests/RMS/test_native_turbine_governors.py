# SPDX-License-Identifier: MPL-2.0
"""Check physical governor realizations independently of file import."""
from __future__ import annotations

import numpy as np
import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards import build_international_standard_template
from VeraGridEngine.Templates.Rms.international_standards.governors.gast import GasGovernorParameters, build_gast_template
from VeraGridEngine.Templates.Rms.international_standards.governors.ieesgo import SteamGovernorParameters, build_ieesgo_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, Expr, BinOp
from VeraGridEngine.enumerations import InternationalStandardModel


def initialized_values(block: Block) -> dict[int, float]:
    """Resolve the declared equilibrium from parameters and input guesses.

    :param block: Native controller with explicit initial expressions.
    :return: Values indexed by symbolic UID.
    """
    values: dict[int, float] = dict()
    expressions: dict[Var,Expr] = dict(block.parameters)
    expressions.update(block.event_dict)
    expressions.update(block.init_eqs)
    for iteration in range(len(expressions) + 1):
        for variable, expression in expressions.items():
            if variable.uid not in values and all(item.uid in values for item in expression.get_vars()):
                values[variable.uid] = expression.eval_uid(values)
            else:
                pass
    assert all(variable.uid in values for variable in expressions)
    return values


def evaluate_controller(block: Block, values: dict[int, float], states: np.ndarray,
                        speed: float) -> tuple[np.ndarray, float]:
    """Evaluate the actual symbolic equations for a supplied operating state.

    :param block: Explicit governor realization.
    :param values: Initial input/parameter bindings.
    :param states: Ordered continuous-state values.
    :param speed: Absolute per-unit shaft speed.
    :return: State derivatives and mechanical output.
    """
    bindings: dict[int, float] = dict(values)
    bindings[block.in_vars[0].uid] = speed
    for variable, value in zip(block.state_vars, states):
        bindings[variable.uid] = float(value)
    # Declaration order need not match equation order in materialized graphs.
    for iteration in range(len(block.algebraic_eqs)+1):
        for equation in block.algebraic_eqs:
            assert isinstance(equation,BinOp) and equation.op == '-' and isinstance(equation.left,Var)
            bindings[equation.left.uid] = equation.right.eval_uid(bindings)
    derivative: np.ndarray = np.asarray([equation.eval_uid(bindings) for equation in block.state_eqs])
    return derivative, bindings[block.out_vars[0].uid]


def linearized_response(block: Block, values: dict[int,float], input_equilibrium: float,
                         frequency: float) -> complex:
    """Measure a controller's transfer response from its running symbolic equations.

    :param block: Native explicit state realization with one perturbed first input.
    :param values: Consistent parameter/input equilibrium bindings.
    :param input_equilibrium: First input's steady value.
    :param frequency: Test frequency in hertz.
    :return: Complex small-signal output/first-input response.
    """
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    step: float = 1e-6
    a: np.ndarray = np.zeros((states.size,states.size))
    c: np.ndarray = np.zeros(states.size)
    for column in range(states.size):
        perturbation: np.ndarray = np.zeros(states.size)
        perturbation[column] = step
        plus, plus_power = evaluate_controller(block,values,states+perturbation,input_equilibrium)
        minus, minus_power = evaluate_controller(block,values,states-perturbation,input_equilibrium)
        a[:,column] = (plus-minus)/(2*step)
        c[column] = (plus_power-minus_power)/(2*step)
    plus, plus_power = evaluate_controller(block,values,states,input_equilibrium+step)
    minus, minus_power = evaluate_controller(block,values,states,input_equilibrium-step)
    b: np.ndarray = (plus-minus)/(2*step)
    d: float = (plus_power-minus_power)/(2*step)
    s: complex = 2j*np.pi*frequency
    return c@np.linalg.solve(s*np.eye(states.size)-a,b)+d


@pytest.mark.parametrize('model,state_count', ((InternationalStandardModel.GAST, 3), (InternationalStandardModel.IEESGO, 5)))
def test_governor_catalogue_equilibrium(model: InternationalStandardModel, state_count: int) -> None:
    """Catalogue dispatch returns square native graphs at physical equilibrium."""
    block: Block = build_international_standard_template(model, VarFactory(), 'turbine').block
    values: dict[int, float] = initialized_values(block)
    assert len(block.state_vars) == state_count
    assert len(block.algebraic_vars) == len(block.algebraic_eqs)
    assert len(block.diff_vars) == state_count
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs], 0, atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs], 0, atol=1e-12)
    assert values[block.out_vars[0].uid] == pytest.approx(.5)


def test_gas_governor_thermal_gate_and_damping() -> None:
    """Thermal demand can override droop while damping acts directly on power."""
    settings: GasGovernorParameters = GasGovernorParameters(ambient_limit=.8, temperature_gain=2, damping=3)
    block: Block = build_gast_template(VarFactory(), parameters=settings).block
    values: dict[int, float] = initialized_values(block)
    values[block.in_vars[1].uid] = 1.1
    derivative: np.ndarray
    power: float
    derivative, power = evaluate_controller(block, values, np.array([.5, .6, 1.0]), 1.01)
    np.testing.assert_allclose(derivative, [-1, -.25, -.4 / 3], atol=1e-12)
    assert power == pytest.approx(.57)


@pytest.mark.parametrize('speed,expected', ((.9, 0.0), (1.1, -18.0)))
def test_gas_governor_valve_non_windup_recovers(speed: float, expected: float) -> None:
    """A valve at its upper stop freezes outward motion and permits inward motion."""
    block: Block = build_gast_template(VarFactory()).block
    values: dict[int, float] = initialized_values(block)
    derivative, power = evaluate_controller(block, values, np.array([.3, .3, .3]), speed)
    upper: Var = next(variable for variable in block.event_dict if variable.name.startswith('VMAX_'))
    values[upper.uid] = .3
    derivative, power = evaluate_controller(block, values, np.array([.3, .3, .3]), speed)
    assert derivative[0] == pytest.approx(expected)


def test_steam_zero_time_stages_are_algebraic() -> None:
    """Disabled delays remove states without introducing epsilon denominators."""
    settings: SteamGovernorParameters = SteamGovernorParameters(t1=0, t2=0, t4=0, t5=0, t6=0)
    block: Block = build_ieesgo_template(VarFactory(), parameters=settings).block
    values: dict[int, float] = initialized_values(block)
    assert len(block.state_vars) == 1
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs], 0, atol=1e-12)
    derivative, power = evaluate_controller(block, values, np.array([0.0]), 1.01)
    assert derivative[0] == pytest.approx(1.0)
    assert power == pytest.approx(.5)


@pytest.mark.parametrize('frequency', (.01, .3, 2.0))
def test_steam_governor_frequency_response(frequency: float) -> None:
    """Linearized equations reproduce controller and weighted turbine transfer functions."""
    settings: SteamGovernorParameters = SteamGovernorParameters(t1=.2, t2=.07)
    block: Block = build_ieesgo_template(VarFactory(), parameters=settings).block
    values: dict[int, float] = initialized_values(block)
    s: complex = 2j*np.pi*frequency
    response: complex = linearized_response(block,values,1.0,frequency)
    turbine: complex = ((1 - settings.reheat_fraction) + settings.reheat_fraction / (1 + s * settings.t5)
        * ((1 - settings.low_pressure_fraction) + settings.low_pressure_fraction / (1 + s * settings.t6))) / (1 + s * settings.t4)
    expected: complex = -settings.gain * (1 + s * settings.t2) / ((1 + s * settings.t1) * (1 + s * settings.t3)) * turbine
    assert response == pytest.approx(expected, rel=1e-7, abs=1e-9)


@pytest.mark.parametrize('model,state_count', ((InternationalStandardModel.STAB1,3),
    (InternationalStandardModel.STAB2A,6),(InternationalStandardModel.STAB3,3),(InternationalStandardModel.STAB4,6),
    (InternationalStandardModel.STABNI,5)))
@pytest.mark.parametrize('frequency', (.01,.3,2.0))
def test_stabilizer_equilibrium_and_frequency_response(model: InternationalStandardModel,
                                                       state_count: int, frequency: float) -> None:
    """Every stabilizer realizes its full transfer order, gain, sign and phase."""
    block: Block = build_international_standard_template(model,VarFactory(),'stabilizer').block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == state_count
    assert len(block.algebraic_vars) == len(block.algebraic_eqs)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0,atol=1e-12)
    s: complex = 2j*np.pi*frequency
    response: complex = linearized_response(block,values,values[block.in_vars[0].uid],frequency)
    expected: complex
    if model == InternationalStandardModel.STAB1:
        expected = 20*s/(1+10*s)*((1+.3*s)/(1+.1*s))**2
    elif model == InternationalStandardModel.STAB2A:
        expected = -(s/(1+s))**3*(1+1/(1+.1*s))/(1+.1*s)**2
    elif model == InternationalStandardModel.STAB3:
        expected = -s/((1+.02*s)*(1+.1*s)*(1+s))
    elif model == InternationalStandardModel.STAB4:
        expected = -s/((1+.02*s)*(1+s))*((1+.2*s)/(1+.1*s))**2/(1+.05*s)**2
    else:
        expected = -(1+.2*s)*s*s/((1+.1*s)*(1+s)**4)
    assert response == pytest.approx(expected,rel=1e-6,abs=1e-8)


def test_invalid_governor_dynamics_are_rejected() -> None:
    """An improper lead-lag and zero physical lag must not become fake fast dynamics."""
    with pytest.raises(ValueError):
        build_ieesgo_template(VarFactory(), parameters=SteamGovernorParameters(t1=0, t2=.1))
    with pytest.raises(ValueError):
        build_gast_template(VarFactory(), parameters=GasGovernorParameters(t1=0))
