"""Diagnostics for PF power omitted by a load's EMT parameter contract."""
from types import MethodType, SimpleNamespace

import numpy as np
import pytest

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import (
    get_shunt_r_emt_template, get_shunt_l_emt_template, get_shunt_c_emt_template,
    get_shunt_rlc_combo_emt_template,
)


def _make_warning_context(logger):
    context = SimpleNamespace(logger=logger, grid=SimpleNamespace(Sbase=100.))
    context._log_unsupported_load_power = MethodType(
        EmtProblemDae._log_unsupported_load_power, context,
    )
    return context


@pytest.mark.parametrize("model_type,power,component", [
    ("R", 20+8j, "inductive reactive"),
    ("L", 20+8j, "active"),
    ("R", 20+0j, None),
    ("L", 8j, None),
    ("RL", 20+8j, None),
])
def test_load_warns_only_for_unmapped_power(model_type, power, component):
    vf = VarFactory()
    if model_type == "R":
        model = get_shunt_r_emt_template(vf).block
    elif model_type == "L":
        model = get_shunt_l_emt_template(vf, phA=True, phB=True, phC=True).block
    else:
        model = get_shunt_rlc_combo_emt_template(
            vf, include_r=True, include_l=True, include_c=False,
        ).block
    logger = Logger()
    context = _make_warning_context(logger)
    load = SimpleNamespace(name="Test load", device_type=DeviceType.LoadDevice)
    # Seed convention: consumption is negative injected power.
    phase_power = -np.array([0j, power, power, 0j]) / 100.
    EmtProblemDae._warn_unsupported_load_power(context, load, model, phase_power)
    entries = logger.entries
    if component is None:
        assert not entries
    else:
        assert len(entries) == 2
        assert all(
            entry.msg == f"EMT load model cannot provide the {component} power required by the power-flow setpoint."
            for entry in entries
        )
        assert all(entry.device == "Test load" for entry in entries)
        assert "phase A:" in entries[0].value
        assert "phase B:" in entries[1].value


@pytest.mark.parametrize("model_type,reactive_demand,unsupported_kind", [
    ("L", -8., "capacitive"),
    ("C", 8., "inductive"),
    ("L", 8., None),
    ("C", -8., None),
    ("L", 0., None),
    ("C", 0., None),
    ("RL", -8., "capacitive"),
    ("RC", 8., "inductive"),
])
def test_load_warns_for_wrong_reactive_component(model_type, reactive_demand, unsupported_kind):
    vf = VarFactory()
    if model_type == "L":
        model = get_shunt_l_emt_template(vf, phA=True, phB=True, phC=True).block
    elif model_type == "C":
        model = get_shunt_c_emt_template(vf, phA=True, phB=True, phC=True).block
    else:
        model = get_shunt_rlc_combo_emt_template(
            vf, include_r=True, include_l=model_type == "RL", include_c=model_type == "RC",
        ).block
    # Renaming the model must not change its detected physical components.
    model.name = "Renamed load"
    logger = Logger()
    context = _make_warning_context(logger)
    load = SimpleNamespace(name="Test load", device_type=DeviceType.LoadDevice)
    phase_power = np.array([0j, -1j * reactive_demand / 100., 0j, 0j])
    EmtProblemDae._warn_unsupported_load_power(context, load, model, phase_power)
    if unsupported_kind is None:
        assert not logger.entries
    else:
        assert len(logger.entries) == 1
        entry = logger.entries[0]
        assert entry.msg == (
            f"EMT load model cannot provide the {unsupported_kind} reactive power required by the power-flow setpoint."
        )
        assert entry.value == "phase A: 8 MVAr"


@pytest.mark.parametrize("storage", ["original", "copy", "serialized"])
@pytest.mark.parametrize("component", ["R", "L", "C", "RL", "RC", "RLC"])
def test_physical_component_interface_survives_renaming_and_storage(storage, component):
    from VeraGridEngine.enumerations import VarPowerFlowReferenceType
    from VeraGridEngine.Utils.Symbolic.block import Block
    from VeraGridEngine.Utils.procedural_logic import ProceduralLogicCodec

    vf = VarFactory()
    if component == "R":
        model = get_shunt_r_emt_template(vf, phA=True, phB=False, phC=True).block
    elif component == "L":
        model = get_shunt_l_emt_template(vf, phA=True, phB=False, phC=True).block
    elif component == "C":
        model = get_shunt_c_emt_template(vf, phA=True, phB=False, phC=True).block
    else:
        # Direct component values exercise models with no Pl0/Ql0 parameters.
        model = get_shunt_rlc_combo_emt_template(
            vf, include_r=True, include_l="L" in component, include_c="C" in component,
            phA=True, phB=False, phC=True,
            direct_r_value=1., direct_l_value=.1, direct_c_value=.01,
        ).block
    for block in model.get_all_blocks():
        for index, parameter in enumerate(block.event_dict):
            parameter.name = f"renamed_parameter_{index}"
    if storage == "copy":
        model = model.copy()
    elif storage == "serialized":
        model = Block.parse(data=model.to_dict(), procedural_logic_codec=ProceduralLogicCodec())
    physical_keys = {VarPowerFlowReferenceType[f"{part}_{phase}"] for part in "RLC" for phase in "ABC"}
    actual = {
        key for block in model.get_all_blocks() for key, var in block.external_mapping.items()
        if key in physical_keys and var is not None
    }
    assert actual == {VarPowerFlowReferenceType[f"{part}_{phase}"] for part in component for phase in "AC"}
    for block in model.get_all_blocks():
        for key, var in block.external_mapping.items():
            if key in actual:
                assert any(var.uid == parameter.uid for owner in model.get_all_blocks() for parameter in owner.event_dict)

    logger = Logger()
    context = _make_warning_context(logger)
    load = SimpleNamespace(name="Test load", device_type=DeviceType.LoadDevice)
    # A requests inductive consumption; C requests capacitive consumption.
    phase_power = -np.array([0j, .2+.08j, 0j, .2-.08j])
    EmtProblemDae._warn_unsupported_load_power(context, load, model, phase_power)
    expected_count = 2 * int("R" not in component) + int("L" not in component) + int("C" not in component)
    assert len(logger.entries) == expected_count


def test_unknown_load_interface_is_not_classified_from_parameter_names():
    from VeraGridEngine.Utils.Symbolic.block import Block
    from VeraGridEngine.enumerations import ParamPowerFlowReferenceType

    vf = VarFactory()
    model = Block()
    misleading_inductor = vf.add_var("L_A")
    model.event_dict[misleading_inductor] = vf.add_const(1.)
    power_parameter = vf.add_var("Pl0_A")
    model.api_obj_mapping[ParamPowerFlowReferenceType.Pl0_A] = power_parameter
    model.parameters[power_parameter] = vf.add_const(0.2)
    logger = Logger()
    context = _make_warning_context(logger)
    load = SimpleNamespace(name="Custom load", device_type=DeviceType.LoadDevice)
    EmtProblemDae._warn_unsupported_load_power(context, load, model, np.array([0j, -.2+.08j, 0j, 0j]))
    assert not logger.entries
