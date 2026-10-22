# SPDX-License-Identifier: MPL-2.0
"""Independent fuel-actuator transfer, bounded output and sampled combustion history."""
from __future__ import annotations

import json
import numpy as np
import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards import build_international_standard_template
from VeraGridEngine.Templates.Rms.international_standards.governors.degov1 import DieselGovernorParameters, EngineDroopFeedback, build_degov1_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import ProceduralExpressionMode, ProceduralLogicCodec, TimeDelayLogic
from VeraGridEngine.enumerations import InternationalStandardModel
from tests.DynamicCatalog._catalog_functional_support import FunctionalRuntimeProblem
from tests.RMS.test_native_turbine_governors import initialized_values, linearized_response, evaluate_controller


@pytest.mark.parametrize('feedback',(EngineDroopFeedback.THROTTLE,EngineDroopFeedback.ELECTRICAL_POWER))
@pytest.mark.parametrize('droop',(0.,.05))
def test_engine_governor_independent_transfer(feedback: EngineDroopFeedback, droop: float) -> None:
    """The unfactored controller poles and actuator integrator retain their exact frequency response.

    :param feedback: Physical droop measurement.
    :param droop: Isochronous or permanent-droop operation.
    """
    block: Block = build_degov1_template(VarFactory(),'engine',DieselGovernorParameters(
        combustion_delay=0.,droop=droop,feedback=feedback)).block
    values: dict[int,float] = initialized_values(block)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    for frequency in (.02,.4,2.):
        s: complex = 2j*np.pi*frequency
        controller: complex = (1.+.2*s)/(1.+.01*s+.01*.02*s*s)
        actuator: complex = 20.*(1.+.25*s)/(s*(1.+.009*s)*(1.+.0384*s))
        loop: complex = controller*actuator
        denominator: complex = 1.+droop*loop if feedback == EngineDroopFeedback.THROTTLE else 1.+0j
        expected: complex = .5-loop/denominator
        assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-7)


def test_engine_electrical_feedback_measurement() -> None:
    """Power feedback includes its own transducer and does not feed back mechanical power."""
    block: Block = build_degov1_template(VarFactory(),'engine',DieselGovernorParameters(
        combustion_delay=0.,feedback=EngineDroopFeedback.ELECTRICAL_POWER)).block
    values: dict[int,float] = initialized_values(block)
    block.in_vars[0],block.in_vars[1] = block.in_vars[1],block.in_vars[0]
    for frequency in (.02,.4,2.):
        s: complex = 2j*np.pi*frequency
        expected: complex = -.05*20.*(1.+.2*s)*(1.+.25*s)/(s*(1.+.01*s+.0002*s*s)*(1.+.009*s)*(1.+.0384*s)*(1.+.1*s))
        assert linearized_response(block,values,.5,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-7)


def test_engine_output_limits_preserve_actuator_memories() -> None:
    """A fuel-flow ceiling clips torque without inventing an actuator-state reset."""
    block: Block = build_degov1_template(VarFactory(),'engine',DieselGovernorParameters(combustion_delay=0.)).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    states[2] = 2.
    states[3] = .2
    derivative: np.ndarray
    power: float
    derivative,power = evaluate_controller(block,values,states,1.)
    assert power == pytest.approx(1.1)
    assert derivative[2] == pytest.approx(.2)
    states[2] = -2.
    derivative,power = evaluate_controller(block,values,states,1.)
    assert power == 0.


@pytest.mark.parametrize('mode',(ProceduralExpressionMode.Compiled,ProceduralExpressionMode.Interpreted))
def test_engine_delay_accepted_sample_history(mode: ProceduralExpressionMode) -> None:
    """Fuel changes wait for the declared delay and retain equilibrium prehistory.

    :param mode: Both supported runtime expression evaluators.
    """
    vf: VarFactory = VarFactory()
    block: Block = build_degov1_template(vf,'engine',DieselGovernorParameters(combustion_delay=.025)).block
    values: dict[int,float] = initialized_values(block)
    problem: FunctionalRuntimeProblem = FunctionalRuntimeProblem(block,vf.add_var('time'))
    x: np.ndarray = np.zeros(len(problem.uid2idx_vars))
    params: np.ndarray = np.zeros(len(problem.uid2idx_event_params))
    for uid,index in problem.uid2idx_vars.items():
        x[index] = values.get(uid,0.)
    for uid,index in problem.uid2idx_event_params.items():
        params[index] = values[uid]
    logic: TimeDelayLogic = block.procedural_logic[0]
    assert isinstance(logic,TimeDelayLogic)
    logic.bind(problem,expression_mode=mode)
    logic.update(0.,x,params)
    assert params[logic.output_idx] == .5
    x[problem.uid2idx_vars[block.out_vars[2].uid]] = .8
    logic.update(.1,x,params)
    assert params[logic.output_idx] == .5
    logic.update(.12,x,params)
    assert params[logic.output_idx] == .5
    logic.update(.13,x,params)
    assert params[logic.output_idx] == .8


@pytest.mark.parametrize('model',(InternationalStandardModel.DEGOV,InternationalStandardModel.DEGOV1,InternationalStandardModel.DEGOV1D))
def test_engine_delay_persistence_and_runtime_clone(model: InternationalStandardModel) -> None:
    """The saved graph retains the delay expression and a clone remaps its output mode."""
    source: Block = build_international_standard_template(model,VarFactory(),'engine').block
    payload: dict[str,object] = json.loads(json.dumps(source.to_dict()))
    restored: Block = Block.parse(payload,procedural_logic_codec=ProceduralLogicCodec())
    assert json.loads(json.dumps(restored.to_dict())) == payload
    logic: TimeDelayLogic = restored.procedural_logic[0]
    assert isinstance(logic,TimeDelayLogic)
    assert logic.output_var_name == restored.out_vars[1].name
    assert len(restored.mode_dict) == 1


@pytest.mark.parametrize('speed,expected',((.997,-.001),(.999,0.),(1.,0.),(1.001,0.),(1.003,.002)))
def test_engine_asymmetric_speed_deadband(speed: float, expected: float) -> None:
    """The speed measurement removes the band continuously before permanent droop subtraction.

    :param speed: Absolute shaft speed.
    :param expected: Signed speed deviation after deadband.
    """
    block: Block = build_degov1_template(VarFactory(),'engine',DieselGovernorParameters(
        combustion_delay=0.,deadband_high=.001,deadband_low=-.002)).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    derivative: np.ndarray
    power: float
    derivative,power = evaluate_controller(block,values,states,speed)
    assert derivative[1] == pytest.approx(-expected/(.01*.02),abs=1e-10)
