# SPDX-License-Identifier: MPL-2.0
"""Lower field-memory stopping and recovery under negative rheostat forcing."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.electromechanical_exciter import ElectromechanicalExciterParameters
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.dc3a import build_dc3a_template
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller


def test_rheostat_field_stop_and_recovery() -> None:
    """The lower stop suppresses outward field motion without stopping separate rheostat travel."""
    block: Block = build_dc3a_template(VarFactory(),'rheostat',ElectromechanicalExciterParameters(
        tr=0.,fast_band=.125,se1=0.,se2=0.,field_min=-.5)).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([-1.,-.5])
    derivative: np.ndarray
    output: float
    derivative, output = evaluate_controller(block,values,states,1.25)
    assert output == -.5 and derivative[1] == 0.
    assert derivative[0] < 0.
    derivative: np.ndarray
    output: float
    derivative, output = evaluate_controller(block,values,states,.75)
    assert output == -.5 and derivative[1] > 0.
    states[1] = -.25
    derivative: np.ndarray
    output: float
    derivative, output = evaluate_controller(block,values,states,1.25)
    assert derivative[1] == pytest.approx((-5.+.25)/.5)
