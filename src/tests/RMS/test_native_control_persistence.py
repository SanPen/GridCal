# SPDX-License-Identifier: MPL-2.0
"""Verify native control equations and signal ports survive declarative persistence."""
from __future__ import annotations

import json
import numpy as np
import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards import build_international_standard_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const
from VeraGridEngine.enumerations import InternationalStandardModel


@pytest.mark.parametrize('model',(InternationalStandardModel.GAST,InternationalStandardModel.IEESGO,
    InternationalStandardModel.STAB1,InternationalStandardModel.STAB2A,InternationalStandardModel.STAB3,
    InternationalStandardModel.STAB4,InternationalStandardModel.STABNI,InternationalStandardModel.IVOST,InternationalStandardModel.IVOGO,
    InternationalStandardModel.IEEEST,InternationalStandardModel.IEE2ST,InternationalStandardModel.COMP,
    InternationalStandardModel.COMPCC,InternationalStandardModel.CCOMP4A,InternationalStandardModel.REMCMP,
    InternationalStandardModel.MNLEX1,InternationalStandardModel.MNLEX2,InternationalStandardModel.MNLEX3,
    InternationalStandardModel.EXST2,InternationalStandardModel.EXST2A,InternationalStandardModel.ESST2A,InternationalStandardModel.GENTRA,InternationalStandardModel.SCRX,
    InternationalStandardModel.IEEET1,InternationalStandardModel.IEEEX1,InternationalStandardModel.ESDC1A,
    InternationalStandardModel.ESDC2A,InternationalStandardModel.EXDC2,InternationalStandardModel.GENROE,
    InternationalStandardModel.IEEET2,InternationalStandardModel.IEEEX2,InternationalStandardModel.IEEX2A,
    InternationalStandardModel.EXPIC1,InternationalStandardModel.EXNI,InternationalStandardModel.IEET1B,InternationalStandardModel.ST4B,InternationalStandardModel.ST4C,InternationalStandardModel.ST5B,InternationalStandardModel.ST5C,InternationalStandardModel.ST6C,InternationalStandardModel.ST7B,InternationalStandardModel.ST7C,InternationalStandardModel.ST1C,InternationalStandardModel.AC5C,InternationalStandardModel.AC8B,InternationalStandardModel.AC7B,InternationalStandardModel.AC7C,InternationalStandardModel.AC8C,InternationalStandardModel.AC1C,InternationalStandardModel.AC2C,InternationalStandardModel.DC4B,InternationalStandardModel.DC4C,InternationalStandardModel.DC3A,InternationalStandardModel.AC4C,InternationalStandardModel.DC1C,InternationalStandardModel.DC2C,InternationalStandardModel.IEEET3,InternationalStandardModel.IEEEX3,InternationalStandardModel.ESST1A,InternationalStandardModel.BUDCZT,InternationalStandardModel.BBSEX1,InternationalStandardModel.ESAC8B,InternationalStandardModel.ESAC5A,InternationalStandardModel.EXAC4,InternationalStandardModel.ESAC4A,
    InternationalStandardModel.GENSAE,InternationalStandardModel.EXAC1A,InternationalStandardModel.ESAC1A,
    InternationalStandardModel.EXAC2,InternationalStandardModel.EXAC3,InternationalStandardModel.IEET1A,
    InternationalStandardModel.IEEET4,InternationalStandardModel.IEEET5,InternationalStandardModel.IEEEX4,InternationalStandardModel.IEET5A,
    InternationalStandardModel.ESAC2A,InternationalStandardModel.ESAC3A,InternationalStandardModel.EXBAS,
    InternationalStandardModel.IEEEG3,InternationalStandardModel.IEEEG3D,
    InternationalStandardModel.PSS2A,InternationalStandardModel.PSS2B,InternationalStandardModel.PSS2C,InternationalStandardModel.PSS3B,
    InternationalStandardModel.IEEEG1,InternationalStandardModel.IEEEG1D,InternationalStandardModel.LCFB1,
    InternationalStandardModel.GGOV1,InternationalStandardModel.GGOV1D,
    InternationalStandardModel.GASTD,InternationalStandardModel.IEESGOD,InternationalStandardModel.HYGOV,
    InternationalStandardModel.PIDGOV,InternationalStandardModel.PIDGOVD,InternationalStandardModel.HYGOVD,InternationalStandardModel.HYGOV2,InternationalStandardModel.HYGOV2D,InternationalStandardModel.TGOV1D))
def test_native_control_graph_round_trip(model: InternationalStandardModel) -> None:
    """Restore actual states, expressions, initializers and ports through native JSON data."""
    source: Block = build_international_standard_template(model,VarFactory(),'persistent_control').block
    payload: dict[str,object] = json.loads(json.dumps(source.to_dict()))
    restored: Block = Block.parse(payload)
    assert json.loads(json.dumps(restored.to_dict())) == payload
    assert len(restored.state_vars) == len(source.state_vars)
    assert tuple(variable.uid for variable in restored.in_vars) == tuple(variable.uid for variable in source.in_vars)
    assert tuple(variable.uid for variable in restored.out_vars) == tuple(variable.uid for variable in source.out_vars)
    assert [str(equation) for equation in restored.state_eqs] == [str(equation) for equation in source.state_eqs]
    assert [str(equation) for equation in restored.algebraic_eqs] == [str(equation) for equation in source.algebraic_eqs]
    assert all(np.isfinite(value.value) for value in restored.event_dict.values() if isinstance(value,Const))


@pytest.mark.parametrize('model', (InternationalStandardModel.EXAC1A, InternationalStandardModel.ESAC1A, InternationalStandardModel.EXAC2, InternationalStandardModel.EXAC3, InternationalStandardModel.ESAC2A, InternationalStandardModel.ESAC3A, InternationalStandardModel.EXBAS))
@pytest.mark.parametrize('field_coefficient', (1.0, 2.0))
def test_brushless_native_graph_equilibrium(model: InternationalStandardModel, field_coefficient: float) -> None:
    """Native catalogue graphs are square and initialize consistently without an import adapter."""
    from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import set_rms_model_parameter
    from VeraGridEngine.Utils.Symbolic.explicit_initialization_symbolic import collect_direct_algebraic_initializers
    from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr
    from VeraGridEngine.enumerations import DeviceType
    from tests.RMS.test_native_turbine_governors import initialized_values
    vf: VarFactory = VarFactory()
    template = build_international_standard_template(model, vf, 'standalone')
    block: Block = template.block
    set_rms_model_parameter(block, 'avr_Ke_standalone', field_coefficient, vf)
    assert template.tpe == DeviceType.NoDevice
    assert len(block.state_vars) == (7 if model == InternationalStandardModel.EXBAS else 5)
    assert len(block.algebraic_vars) == len(block.algebraic_eqs)
    # Resolve direct algebraic assignments as the native initialization path
    # does, while retaining explicit state and operating-point initializers.
    assignments: dict[Var, Expr] = dict()
    collect_direct_algebraic_initializers(block, assignments)
    for variable, expression in assignments.items():
        if variable not in block.init_eqs:
            block.init_eqs[variable] = expression
        else:
            pass
    values: dict[int,float] = initialized_values(block)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs], 0, atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs], 0, atol=1e-12)


@pytest.mark.parametrize('model', (InternationalStandardModel.EXAC1, InternationalStandardModel.EXAC1A, InternationalStandardModel.ESAC1A))
def test_brushless_field_memory_lower_stop(model: InternationalStandardModel) -> None:
    """A discharged rotating field blocks outward motion and releases on positive forcing."""
    from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller
    block: Block = build_international_standard_template(model, VarFactory(), 'floor').block
    values: dict[int,float] = initialized_values(block)
    if model == InternationalStandardModel.ESAC1A:
        values[block.in_vars[1].uid] = 10
        values[block.in_vars[5].uid] = -10
    else:
        pass
    states: np.ndarray = np.asarray([0 if variable.name == 'avr_integrator_y_floor' else
        (-1 if variable.name == 'avr_limitedFirstOrder_I_y_floor' else values[variable.uid])
        for variable in block.state_vars])
    derivative: np.ndarray
    output: float
    derivative, output = evaluate_controller(block, values, states, 1.0)
    assert output == 0
    assert derivative[0] == 0
    for index, variable in enumerate(block.state_vars):
        if variable.name == 'avr_limitedFirstOrder_I_y_floor':
            states[index] = 1
        else:
            pass
    derivative, output = evaluate_controller(block, values, states, 1.0)
    assert output == 0
    assert derivative[0] > 0


@pytest.mark.parametrize('model', (InternationalStandardModel.EXAC1, InternationalStandardModel.EXAC1A, InternationalStandardModel.ESAC1A))
def test_brushless_native_live_current_loading(model: InternationalStandardModel) -> None:
    """Rectifier drop and field demagnetization consume live current without an import adapter."""
    from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import set_rms_model_parameter
    from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller
    vf: VarFactory = VarFactory()
    block: Block = build_international_standard_template(model, vf, 'current').block
    set_rms_model_parameter(block, 'avr_Kc_current', .2, vf)
    set_rms_model_parameter(block, 'avr_Kd_current', .3, vf)
    set_rms_model_parameter(block, 'avr_tE_current', .5, vf)
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    initial_derivative: np.ndarray
    initial_output: float
    changed_derivative: np.ndarray
    changed_output: float
    initial_derivative, initial_output = evaluate_controller(block, values, states, 1.0)
    changed_derivative, changed_output = evaluate_controller(block, values, states, 2.0)
    assert changed_derivative[0]-initial_derivative[0] == pytest.approx(-.3/.5)
    coefficient: float = next(values[variable.uid] for variable in block.event_dict if variable.name == 'avr_A1_current')
    assert changed_output-initial_output == pytest.approx(-coefficient*.2)


@pytest.mark.parametrize('model', (InternationalStandardModel.EXAC1, InternationalStandardModel.EXAC1A,
    InternationalStandardModel.ESAC1A, InternationalStandardModel.EXAC2, InternationalStandardModel.EXAC3,
    InternationalStandardModel.ESAC2A, InternationalStandardModel.ESAC3A, InternationalStandardModel.EXBAS))
@pytest.mark.parametrize('upper', (False, True))
def test_brushless_amplifier_exact_boundary_and_recovery(model: InternationalStandardModel, upper: bool) -> None:
    """All common amplifiers stop outward at exact bounds and release immediately inward.

    :param model: Reviewed native brushless controller.
    :param upper: Select upper forcing rather than lower forcing boundary.
    """
    from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller
    block: Block = build_international_standard_template(model, VarFactory(), 'boundary').block
    values: dict[int, float] = initialized_values(block)
    values[block.in_vars[5].uid] = (-100 if model in (InternationalStandardModel.ESAC1A,
        InternationalStandardModel.ESAC2A,InternationalStandardModel.ESAC3A) else 0)
    values[block.in_vars[4].uid] = 100 if upper else -100
    states: np.ndarray = np.asarray([(5 if upper else -5) if var.name == 'avr_limitedFirstOrder_I_y_boundary'
        else values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block, values, states, 1)
    assert derivative[2] == 0
    values[block.in_vars[4].uid] *= -1
    derivative, output = evaluate_controller(block, values, states, 1)
    assert derivative[2] < 0 if upper else derivative[2] > 0
