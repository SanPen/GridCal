# SPDX-License-Identifier: MPL-2.0
"""Check compensation signs, shared-current effects and voltage-limit placement."""
from __future__ import annotations

import numpy as np
import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards import build_international_standard_template
from VeraGridEngine.Templates.Rms.international_standards.voltage_compensators.comp import build_comp_template
from VeraGridEngine.Templates.Rms.international_standards.voltage_compensators.compcc import build_compcc_template
from VeraGridEngine.Templates.Rms.international_standards.voltage_compensators.ccomp4a import build_ccomp4a_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const
from VeraGridEngine.enumerations import InternationalStandardModel


def evaluate_measurement(block: Block, inputs: tuple[float,...]) -> tuple[float,...]:
    """Evaluate a stateless compensation block at explicit phasor measurements.

    :param block: Native algebraic compensator.
    :param inputs: Inputs in the declared public port order.
    :return: Values in the public output order.
    """
    values: dict[int,float] = dict()
    for variable,expression in block.event_dict.items():
        assert isinstance(expression,Const)
        values[variable.uid] = expression.value
    assert len(inputs) == len(block.in_vars)
    for variable,value in zip(block.in_vars,inputs):
        values[variable.uid] = value
    for variable,equation in zip(block.algebraic_vars,block.algebraic_eqs):
        values[variable.uid] = 0.0
        values[variable.uid] = -equation.eval_uid(values)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0,atol=1e-12)
    return tuple(values[variable.uid] for variable in block.out_vars)


@pytest.mark.parametrize('reactance',(-.3,0,.3))
@pytest.mark.parametrize('angle',(-1.1,0,.8))
def test_reactive_compensation_sign_and_rotation(reactance: float,angle: float) -> None:
    """Changing the phasor reference frame must preserve the compensated magnitude."""
    voltage: complex = 1.02+.1j
    current: complex = .4-.2j
    rotation: complex = np.exp(1j*angle)
    block: Block = build_comp_template(VarFactory(),reactance=reactance).block
    rotated_voltage: complex = voltage*rotation
    rotated_current: complex = current*rotation
    result: tuple[float,...] = evaluate_measurement(block,(rotated_voltage.real,rotated_voltage.imag,
        rotated_current.real,rotated_current.imag))
    assert result[0] == pytest.approx(abs(voltage-1j*reactance*current))


def test_cross_compound_paths_and_machine_exchange() -> None:
    """The common term uses both currents, but each individual term uses its own current."""
    voltage: complex = 1.03+.07j
    first: complex = .4-.1j
    second: complex = .3-.2j
    shared: complex = .02+.15j
    individual: complex = .03+.2j
    block: Block = build_compcc_template(VarFactory(),shared_resistance=shared.real,
        shared_reactance=shared.imag,individual_resistance=individual.real,
        individual_reactance=individual.imag).block
    result: tuple[float,...] = evaluate_measurement(block,(voltage.real,voltage.imag,
        first.real,first.imag,second.real,second.imag))
    assert result == pytest.approx((abs(voltage-(first+second)*shared/2+first*individual),
        abs(voltage-(first+second)*shared/2+second*individual)))
    exchanged: tuple[float,...] = evaluate_measurement(block,(voltage.real,voltage.imag,
        second.real,second.imag,first.real,first.imag))
    assert exchanged == pytest.approx(result[::-1])


@pytest.mark.parametrize('current,correction',((-.3,-.1),(.02,.04),(.3,.2)))
def test_four_unit_limits_bound_correction(current: float,correction: float) -> None:
    """The voltage bias is limited before being added to the terminal magnitude."""
    block: Block = build_ccomp4a_template(VarFactory(),gains=(1,2,0,0),overall_gain=2,
        lower_limit=-.1,upper_limit=.2).block
    result: tuple[float,...] = evaluate_measurement(block,(.95,current,0,0,0))
    assert result == pytest.approx((.95+correction,correction))


@pytest.mark.parametrize('model,inputs',((InternationalStandardModel.COMP,(1.04,.1,.3,-.1)),
    (InternationalStandardModel.COMPCC,(1.04,.1,.3,-.1,.2,-.15)),
    (InternationalStandardModel.CCOMP4A,(1.04,.1,.1,0,0)),
    (InternationalStandardModel.REMCMP,(.97,))))
def test_compensator_catalogue_ports(model: InternationalStandardModel,inputs: tuple[float,...]) -> None:
    """Public catalogue dispatch provides stateless open-port measurement components."""
    block: Block = build_international_standard_template(model,VarFactory(),'measurement').block
    assert not block.state_vars
    assert len(block.algebraic_vars) == len(block.algebraic_eqs)
    result: tuple[float,...] = evaluate_measurement(block,inputs)
    assert all(np.isfinite(value) for value in result)
    if model == InternationalStandardModel.REMCMP:
        assert result == (.97,)
    else:
        pass
