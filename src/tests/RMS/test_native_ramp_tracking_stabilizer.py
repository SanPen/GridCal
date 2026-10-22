# SPDX-License-Identifier: MPL-2.0
"""Independent two-input transfer functions, structural bypasses and clipping checks."""
from __future__ import annotations

import json
import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.ramp_tracking_stabilizer import (
    RampStabilizerKind, RampStabilizerParameters, StabilizerInterface, build_ramp_tracking_stabilizer)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('kind', tuple(RampStabilizerKind))
@pytest.mark.parametrize('m,n', ((0, 0), (0, 5), (1, 1), (2, 2), (4, 2), (8, 1), (3, 0)))
@pytest.mark.parametrize('path', (0, 1))
@pytest.mark.parametrize('frequency', (.02, .4, 2.0))
def test_ramp_tracking_two_input_frequency_response(kind: RampStabilizerKind, m: int, n: int,
                                                   path: int, frequency: float) -> None:
    """Both measured paths match separately derived rational transfer functions.

    :param kind: Two-phase or input-limited three-phase structure.
    :param m: Denominator order of each repeated ramp stage.
    :param n: Number of repeated stages.
    :param path: Independently perturbed measured-input path.
    :param frequency: Perturbation frequency in hertz.
    """
    p: RampStabilizerParameters = RampStabilizerParameters(washout_times=(3, 0, 4, 0),
        transducer_times=(.02, .03), ks1=5, ks2=.4, ks3=.7, t8=.1, t9=.2, ramp_m=m, ramp_n=n,
        phase_times=((.2, .05), (.1, .03), (.04, .02)))
    block: Block = build_ramp_tracking_stabilizer(VarFactory(), 'tracking', kind, p).block
    values: dict[int, float] = initialized_values(block)
    if path == 1:
        block.in_vars[0], block.in_vars[1] = block.in_vars[1], block.in_vars[0]
    else:
        pass
    s: complex = 2j*np.pi*frequency
    ramp: complex = 1 if m == 0 or n == 0 else ((1+.1*s)/(1+.2*s)**m)**n
    phase: complex = (1+.2*s)*(1+.1*s)/((1+.05*s)*(1+.03*s))
    if kind != RampStabilizerKind.TWO_PHASE:
        phase *= (1+.04*s)/(1+.02*s)
    else:
        pass
    if kind == RampStabilizerKind.LIMITED_FOUR_PHASE:
        phase *= (1+.1*s)/(1+.05*s)
    else:
        pass
    expected: complex = (5*phase*ramp*3*s/((1+3*s)*(1+.02*s)) if path == 0 else
        5*phase*(.7*ramp-1)*.4*4*s/((1+4*s)*(1+.03*s)))
    assert linearized_response(block, values, 0, frequency) == pytest.approx(expected, rel=1e-7, abs=1e-9)


@pytest.mark.parametrize('kind', tuple(RampStabilizerKind))
@pytest.mark.parametrize('m,n', ((0, 7), (1, 1), (2, 2), (4, 2), (3, 0)))
@pytest.mark.parametrize('bypass', (False, True))
def test_ramp_tracking_equilibrium_and_state_count(kind: RampStabilizerKind, m: int, n: int, bypass: bool) -> None:
    """Nonzero measured inputs initialize consistently with exactly the requested memories.

    :param kind: Physical phase and input-limiting structure.
    :param m: Ramp denominator order.
    :param n: Number of repeated ramp sections.
    :param bypass: Bypass optional washouts, transducers and output phase pairs.
    """
    p: RampStabilizerParameters = RampStabilizerParameters(
        washout_times=(3, 0 if bypass else 5, 4, 0 if bypass else 6),
        transducer_times=(0, 0) if bypass else (.02, .03), ramp_m=m, ramp_n=n,
        phase_times=((0, 0), (0, 0), (0, 0)) if bypass else ((.2, .05), (.1, .03), (.04, .02)),
        fourth_phase=(0.,0.) if bypass else (.1,.05))
    block: Block = build_ramp_tracking_stabilizer(VarFactory(), 'tracking', kind, p).block
    block.init_eqs[block.in_vars[0]] = Const(.2)
    block.init_eqs[block.in_vars[1]] = Const(.4)
    values: dict[int, float] = initialized_values(block)
    expected: int = 2+m*n+(0 if bypass else (6 if kind == RampStabilizerKind.TWO_PHASE else 7))
    if kind == RampStabilizerKind.LIMITED_FOUR_PHASE and not bypass:
        expected += 1
    else:
        pass
    assert len(block.state_vars) == expected
    assert len(block.algebraic_vars) == len(block.algebraic_eqs)
    assert values[block.out_vars[0].uid] == 0
    np.testing.assert_allclose([eq.eval_uid(values) for eq in block.state_eqs], 0, atol=1e-12)
    np.testing.assert_allclose([eq.eval_uid(values) for eq in block.algebraic_eqs], 0, atol=1e-12)


def test_limited_stabilizer_input_and_output_limits_are_independent() -> None:
    """Raw measurement clipping limits the washout drive before separate voltage-output clipping."""
    p: RampStabilizerParameters = RampStabilizerParameters(washout_times=(2, 0, 2, 0),
        transducer_times=(0, 0), ks1=1, ks2=1, ks3=0, ramp_m=0, ramp_n=0,
        phase_times=((0, 0), (0, 0), (0, 0)), upper=.01, lower=-.01,
        input_limits=((-.05, .05), (-.1, .1)))
    block: Block = build_ramp_tracking_stabilizer(VarFactory(), 'tracking',
        RampStabilizerKind.LIMITED_THREE_PHASE, p).block
    values: dict[int, float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block, values, states, .2)
    assert derivative[0] == pytest.approx(.025)
    assert output == pytest.approx(.01)
    values[block.in_vars[1].uid] = -.4
    derivative, output = evaluate_controller(block, values, states, 0)
    assert derivative[1] == pytest.approx(-.05)
    assert output == pytest.approx(.01)


@pytest.mark.parametrize('interface', tuple(StabilizerInterface))
@pytest.mark.parametrize('kind', tuple(RampStabilizerKind))
def test_ramp_tracking_graph_persistence(kind: RampStabilizerKind, interface: StabilizerInterface) -> None:
    """Both public interfaces retain parameters, exact filter order and initializers through JSON.

    :param kind: Physical stabilizer structure.
    :param interface: Selected measurements or compatible shaft/reference/power ports.
    """
    block: Block = build_ramp_tracking_stabilizer(VarFactory(), 'tracking', kind,
        RampStabilizerParameters(ramp_m=2, ramp_n=2), interface).block
    payload: dict[str, object] = json.loads(json.dumps(block.to_dict()))
    restored: Block = Block.parse(payload)
    assert json.loads(json.dumps(restored.to_dict())) == payload
    assert len(restored.in_vars) == (2 if interface == StabilizerInterface.SELECTED_SIGNALS else 3)


@pytest.mark.parametrize('m,n', ((-1, 1), (1, -1), (3, 3)))
def test_ramp_tracking_invalid_orders_are_rejected(m: int, n: int) -> None:
    """Invalid allocation is rejected instead of truncating the ramp filter silently.

    :param m: Invalid denominator order.
    :param n: Invalid repeat count.
    """
    with pytest.raises(ValueError, match='orders'):
        build_ramp_tracking_stabilizer(VarFactory(), 'tracking', RampStabilizerKind.TWO_PHASE,
            RampStabilizerParameters(ramp_m=m, ramp_n=n))
