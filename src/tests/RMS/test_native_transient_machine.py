# SPDX-License-Identifier: MPL-2.0
"""Independent phasor and field-balance checks for a field-transient machine."""
from __future__ import annotations

import numpy as np
import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.synchronous_machines.gentra import build_gentra_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const
from tests.RMS.test_native_turbine_governors import initialized_values


@pytest.mark.parametrize('saturation', (False,True))
@pytest.mark.parametrize('active,reactive,angle', ((.8,.2,.0),(-.3,-.1,.7),(.6,-.2,-.4)))
def test_transient_machine_phasor_equilibrium(saturation: bool, active: float,
                                            reactive: float, angle: float) -> None:
    """Field saturation, copper torque and rotor orientation agree with phasor calculations.

    :param saturation: Whether the quadratic field characteristic is enabled.
    :param active: Terminal active power on the common base.
    :param reactive: Terminal reactive power on the common base.
    :param angle: Terminal voltage angle in electrical radians.
    """
    block: Block = build_gentra_template(VarFactory(),resistance=.02,
        saturation_10=.09 if saturation else 0,saturation_12=.38 if saturation else 0).block.children[0]
    block.init_eqs[block.in_vars[0]] = Const(1.03)
    block.init_eqs[block.in_vars[1]] = Const(angle)
    block.init_eqs[block.out_vars[0]] = Const(active)
    block.init_eqs[block.out_vars[1]] = Const(reactive)
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 3
    assert len(block.algebraic_vars) == len(block.algebraic_eqs)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0,atol=1e-12)
    voltage: complex = 1.03*np.exp(1j*angle)
    current: complex = np.conj((active+1j*reactive)/voltage)
    rotor_angle: float = float(np.angle(voltage+(.02+1.7j)*current))
    rotor_current: complex = current*np.exp(-1j*rotor_angle)
    direct_current: float = float(-rotor_current.imag)
    flux: float = float((voltage*np.exp(-1j*rotor_angle)).real+.02*rotor_current.real+.3*direct_current)
    field: float = flux+1.5*direct_current
    if saturation:
        # Fit the two open-circuit excess-field samples independently.
        ratio: float = float(np.sqrt(.09/(1.2*.38)))
        threshold: float = (1-1.2*ratio)/(1-ratio)
        gain: float = .09/(1-threshold)**2
        field += gain*max(flux-threshold,0)**2
    else:
        pass
    assert values[block.state_vars[0].uid] == pytest.approx(rotor_angle)
    assert values[block.out_vars[3].uid] == pytest.approx(field)
    assert values[block.out_vars[4].uid] == pytest.approx(active+.02*abs(current)**2)
    # A live torque or field perturbation must reach the correct rotor state.
    values[block.in_vars[2].uid] += .08
    values[block.in_vars[3].uid] += .6
    assert block.state_eqs[1].eval_uid(values) == pytest.approx(.01)
    assert block.state_eqs[2].eval_uid(values) == pytest.approx(.1)


@pytest.mark.parametrize('first,second',((0,.38),(.09,0),(.2,.1),(-.1,.3)))
def test_transient_machine_rejects_undefined_saturation_contract(first: float, second: float) -> None:
    """Unreviewed single-zero and invalid fits cannot silently discard source data.

    :param first: Saturation factor at unit transient flux.
    :param second: Saturation factor at transient flux 1.2 pu.
    """
    with pytest.raises(ValueError):
        build_gentra_template(VarFactory(),saturation_10=first,saturation_12=second)
