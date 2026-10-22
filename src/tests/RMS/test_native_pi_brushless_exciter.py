# SPDX-License-Identifier: MPL-2.0
"""Independent PI regulation and shaped field-current feedback checks."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import set_rms_model_parameter
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.exbas import build_exbas_template
from VeraGridEngine.Utils.Symbolic.explicit_initialization_symbolic import collect_direct_algebraic_initializers
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('frequency', (.02, .4, 2.0))
@pytest.mark.parametrize('proportional_gain', (0.0, .5))
@pytest.mark.parametrize('integral_gain', (.3, 1.2))
def test_pi_brushless_frequency_response(frequency: float, proportional_gain: float, integral_gain: float) -> None:
    """The native graph matches the independently closed PI/phase/field/shaped-feedback loop.

    :param frequency: Perturbation frequency in hertz.
    :param proportional_gain: Enable proportional-plus-integral or integral-only error regulation.
    :param integral_gain: Positive integration gain.
    """
    vf: VarFactory = VarFactory()
    block: Block = build_exbas_template(vf, 'pi').block
    for name, value in (('KP', proportional_gain), ('KI', integral_gain), ('avr.Ka', 4.0),
                        ('avr.Ke', 2.0), ('avr.tA', .07), ('avr.tB', .2), ('avr.tC', .1),
                        ('avr.tR', .03), ('avr.tF', .8), ('avr.Kf', .06)):
        set_rms_model_parameter(block, name+'_pi', value, vf)
    assignments: dict[Var, Expr] = dict()
    collect_direct_algebraic_initializers(block, assignments)
    for variable, expression in assignments.items():
        if variable not in block.init_eqs:
            block.init_eqs[variable] = expression
        else:
            pass
    values: dict[int, float] = initialized_values(block)
    np.testing.assert_allclose([eq.eval_uid(values) for eq in block.state_eqs], 0, atol=1e-12)
    block.in_vars[0], block.in_vars[3] = block.in_vars[3], block.in_vars[0]
    s: complex = 2j*np.pi*frequency
    amplifier: complex = 4*(proportional_gain+integral_gain/s)*(1+.1*s)/((1+.2*s)*(1+.07*s))
    field: complex = 1/(2+.5*s)
    feedback: complex = 2*.06*s*(1+.1*s)/((1+.8*s)*(1+.5*s))
    expected: complex = -amplifier*field/((1+amplifier*field*feedback)*(1+.03*s))
    assert linearized_response(block, values, 1, frequency) == pytest.approx(expected, rel=1e-7, abs=1e-10)


def test_pi_integral_memory_is_distinct_from_amplifier_stop() -> None:
    """Amplifier saturation does not invent anti-windup on the upstream PI integrator."""
    block: Block = build_exbas_template(VarFactory(), 'pi').block
    values: dict[int, float] = initialized_values(block)
    values[block.in_vars[4].uid] = 10
    states: np.ndarray = np.asarray([5 if var.name == 'avr.limitedFirstOrder.I.y_pi' else values[var.uid]
        for var in block.state_vars])
    derivative, output = evaluate_controller(block, values, states, 0)
    assert derivative[5] == pytest.approx(9)
    assert derivative[2] == 0
    assert output == 1
