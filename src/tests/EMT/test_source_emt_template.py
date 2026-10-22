# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import numpy as np
import pytest

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Emt.balanced_source_emt_template import get_balanced_3ph_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.source_emt_template import get_controlled_current_source_emt_template
from VeraGridEngine.Templates.Emt.source_emt_template import get_controlled_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.source_emt_template import get_current_source_emt_template
from VeraGridEngine.Templates.Emt.source_emt_template import get_voltage_source_emt_template
from VeraGridEngine.enumerations import VarPowerFlowReferenceType
from VeraGridEngine.Utils.Symbolic.block import Expr, Var


def _evaluate_seeded_source(template: EmtModelTemplate,
                            input_values: np.ndarray,
                            event_overrides: tuple[tuple[str, float], ...] = ()) -> tuple[np.ndarray, float]:
    """Evaluate declared source seeds and their actual algebraic residual.

    These source blocks seed their angle independently of the output currents.
    Evaluate that declared state seed first, as the EMT initializer resolves
    dependencies, rather than assuming the dictionary insertion order is valid.

    :param template: Canonical source factory output whose equations are evaluated.
    :param input_values: Bus voltages and commands in the block's input order.
    :param event_overrides: Explicit event values keyed by registered symbol name.
    :return: Seeded output currents and the algebraic residual infinity norm.
    """
    assert len(input_values) == len(template.block.in_vars)
    bindings: dict[int, float] = dict()
    variable: Var
    expression: Expr
    event_name: str
    event_value: float
    index: int
    for variable, expression in template.block.parameters.items():
        bindings[variable.uid] = float(expression.eval_uid(bindings))
    for variable, expression in template.block.event_dict.items():
        bindings[variable.uid] = float(expression.eval_uid(bindings))

    # Override only registered events, so a misspelled test input fails visibly.
    for event_name, event_value in event_overrides:
        matches: tuple[Var, ...] = tuple(variable for variable in template.block.event_dict
                                         if variable.name == event_name)
        assert len(matches) == 1
        bindings[matches[0].uid] = event_value
    for index, variable in enumerate(template.block.in_vars):
        bindings[variable.uid] = float(input_values[index])

    # Use the block's state seed before evaluating current seeds that depend on it.
    for variable in template.block.state_vars:
        bindings[variable.uid] = float(template.block.init_eqs[variable].eval_uid(bindings))
    for variable in template.block.algebraic_vars:
        bindings[variable.uid] = float(template.block.init_eqs[variable].eval_uid(bindings))

    currents: np.ndarray = np.empty(len(template.block.out_vars), dtype=float)
    residuals: np.ndarray = np.empty(len(template.block.algebraic_eqs), dtype=float)
    for index, variable in enumerate(template.block.out_vars):
        currents[index] = bindings[variable.uid]
    for index, expression in enumerate(template.block.algebraic_eqs):
        residuals[index] = float(expression.eval_uid(bindings))
    return currents, float(np.linalg.norm(residuals, ord=np.inf))


def test_current_source_emt_template_exposes_phase_inputs_outputs_and_event_values() -> None:
    vf: VarFactory = VarFactory()
    templ = get_current_source_emt_template(vf=vf, phN=False, phA=True, phB=False, phC=True, name="CurrentSourceCase")
    resolved_name: str = "CurrentSourceCase_2ph"

    assert [var.name for var in templ.block.in_vars] == ["v_A", "v_C"]
    assert [var.name for var in templ.block.out_vars] == ["i_A", "i_C"]
    assert sorted(var.name for var in templ.block.event_dict.keys()) == [
        "I_amp_A",
        "I_amp_C",
        "I_offset_A",
        "I_offset_C",
        "f_src",
        "phi_deg_A",
        "phi_deg_C",
    ]
    assert templ.block.external_mapping[VarPowerFlowReferenceType.v_A].name == "v_A"
    assert templ.block.external_mapping[VarPowerFlowReferenceType.i_C].name == "i_C"


def test_controlled_current_source_emt_template_exposes_command_inputs() -> None:
    vf: VarFactory = VarFactory()
    templ = get_controlled_current_source_emt_template(vf=vf, phN=True, phA=True, phB=False, phC=False, name="ControlledCurrentCase")
    resolved_name: str = "ControlledCurrentCase_2ph"

    assert [var.name for var in templ.block.in_vars] == ["v_N", "i_amp_cmd_N", "v_A", "i_amp_cmd_A"]
    assert [var.name for var in templ.block.out_vars] == ["i_N", "i_A"]
    assert sorted(var.name for var in templ.block.event_dict.keys()) == [
        "I_offset_A",
        "I_offset_N",
        "f_src",
        "phi_deg_A",
        "phi_deg_N",
    ]


def test_voltage_source_emt_template_exposes_source_parameters_and_norton_outputs() -> None:
    vf: VarFactory = VarFactory()
    templ = get_voltage_source_emt_template(vf=vf, phN=False, phA=True, phB=True, phC=False, name="VoltageSourceCase")
    resolved_name: str = "VoltageSourceCase_2ph"

    assert [var.name for var in templ.block.in_vars] == ["v_A", "v_B"]
    assert [var.name for var in templ.block.out_vars] == ["i_A", "i_B"]
    assert sorted(var.name for var in templ.block.event_dict.keys()) == [
        "V_amp_A",
        "V_amp_B",
        "V_offset_A",
        "V_offset_B",
        "f_src",
        "g_src",
        "phi_deg_A",
        "phi_deg_B",
    ]


def test_controlled_voltage_source_emt_template_exposes_command_inputs_and_conductance_param() -> None:
    vf: VarFactory = VarFactory()
    templ = get_controlled_voltage_source_emt_template(vf=vf, phN=False, phA=False, phB=True, phC=True, name="ControlledVoltageCase")
    resolved_name: str = "ControlledVoltageCase_2ph"

    assert [var.name for var in templ.block.in_vars] == ["v_B", "v_amp_cmd_B", "v_C", "v_amp_cmd_C"]
    assert [var.name for var in templ.block.out_vars] == ["i_B", "i_C"]
    assert sorted(var.name for var in templ.block.event_dict.keys()) == [
        "V_offset_B",
        "V_offset_C",
        "f_src",
        "g_src",
        "phi_deg_B",
        "phi_deg_C",
    ]


@pytest.mark.parametrize("amplitude_scale, angle_scale", ((1.0, 1.0), (1.0, 0.0), (0.0, 1.0)))
def test_phase_selective_voltage_source_initialization_matches_waveform(amplitude_scale: float,
                                                                       angle_scale: float) -> None:
    """Check independent NABC voltage-source seeds against the Norton law.

    :param amplitude_scale: Scale for independent phase amplitudes, including zero.
    :param angle_scale: Scale for phase offsets, including the zero-angle control.
    :return: None; currents and residuals are checked against an analytic oracle.
    """
    template: EmtModelTemplate = get_voltage_source_emt_template(
        vf=VarFactory(), phN=True, source_conductance_value=3.0)
    labels: tuple[str, ...] = ("N", "A", "B", "C")
    amplitudes: np.ndarray = amplitude_scale * np.array((0.4, 2.0, 1.0, 3.0))
    angles: np.ndarray = angle_scale * np.array((45.0, 30.0, -80.0, 155.0))
    offsets: np.ndarray = np.array((0.1, 0.25, -0.15, 0.4))
    voltages: np.ndarray = np.array((0.07, 0.2, -0.35, 0.9))
    prefixes: tuple[str, ...] = ("V_amp", "phi_deg", "V_offset")
    event_values: np.ndarray = np.vstack((amplitudes, angles, offsets))
    row: int
    index: int
    prefix: str
    label: str
    overrides: tuple[tuple[str, float], ...] = tuple(
        (f"{prefix}_{label}", float(event_values[row, index]))
        for row, prefix in enumerate(prefixes) for index, label in enumerate(labels))
    current: np.ndarray
    residual: float
    current, residual = _evaluate_seeded_source(template, voltages, overrides)

    # This independent numeric oracle also detects a consistently wrong seed/residual pair.
    expected: np.ndarray = 3.0 * (offsets + amplitudes * np.sin(np.deg2rad(angles)) - voltages)
    np.testing.assert_allclose(current, expected, atol=1.0e-12, rtol=1.0e-12)
    assert residual < 1.0e-12


@pytest.mark.parametrize("amplitude_scale, angle_scale", ((1.0, 1.0), (1.0, 0.0), (0.0, 1.0)))
def test_phase_selective_current_source_initialization_matches_waveform(amplitude_scale: float,
                                                                       angle_scale: float) -> None:
    """Check independently prescribed ABC currents at the declared angle seed.

    :param amplitude_scale: Scale for phase-current amplitudes, including zero.
    :param angle_scale: Scale for phase offsets, including the zero-angle control.
    :return: None; the sinusoidal current and actual algebraic residual are checked.
    """
    template: EmtModelTemplate = get_current_source_emt_template(vf=VarFactory())
    labels: tuple[str, ...] = ("A", "B", "C")
    amplitudes: np.ndarray = amplitude_scale * np.array((2.0, 1.0, 3.0))
    angles: np.ndarray = angle_scale * np.array((30.0, -80.0, 155.0))
    offsets: np.ndarray = np.array((0.25, -0.15, 0.4))
    voltages: np.ndarray = np.array((0.2, -0.35, 0.9))
    prefixes: tuple[str, ...] = ("I_amp", "phi_deg", "I_offset")
    event_values: np.ndarray = np.vstack((amplitudes, angles, offsets))
    row: int
    index: int
    prefix: str
    label: str
    overrides: tuple[tuple[str, float], ...] = tuple(
        (f"{prefix}_{label}", float(event_values[row, index]))
        for row, prefix in enumerate(prefixes) for index, label in enumerate(labels))
    current: np.ndarray
    residual: float
    current, residual = _evaluate_seeded_source(template, voltages, overrides)

    # A prescribed current is independent of bus voltage, including at startup.
    expected: np.ndarray = offsets + amplitudes * np.sin(np.deg2rad(angles))
    np.testing.assert_allclose(current, expected, atol=1.0e-12, rtol=1.0e-12)
    assert residual < 1.0e-12


@pytest.mark.parametrize("amplitude_scale, angle_scale", ((1.0, 1.0), (1.0, 0.0), (0.0, 1.0)))
def test_controlled_phase_selective_voltage_source_initialization_matches_waveform(amplitude_scale: float,
                                                                                  angle_scale: float) -> None:
    """Check Norton seeds with external amplitude commands and selected NAC terminals.

    :param amplitude_scale: Scale for external amplitude commands, including zero.
    :param angle_scale: Scale for phase offsets, including the zero-angle control.
    :return: None; the commanded waveform and actual residual are checked.
    """
    template: EmtModelTemplate = get_controlled_voltage_source_emt_template(
        vf=VarFactory(), phN=True, phB=False, source_conductance_value=3.0)
    labels: tuple[str, ...] = ("N", "A", "C")
    commands: np.ndarray = amplitude_scale * np.array((0.4, 2.0, 3.0))
    angles: np.ndarray = angle_scale * np.array((45.0, 30.0, 155.0))
    offsets: np.ndarray = np.array((0.1, 0.25, 0.4))
    voltages: np.ndarray = np.array((0.07, 0.2, 0.9))
    inputs: np.ndarray = np.column_stack((voltages, commands)).ravel()
    prefixes: tuple[str, ...] = ("phi_deg", "V_offset")
    event_values: np.ndarray = np.vstack((angles, offsets))
    row: int
    index: int
    prefix: str
    label: str
    overrides: tuple[tuple[str, float], ...] = tuple(
        (f"{prefix}_{label}", float(event_values[row, index]))
        for row, prefix in enumerate(prefixes) for index, label in enumerate(labels))
    current: np.ndarray
    residual: float
    current, residual = _evaluate_seeded_source(template, inputs, overrides)

    # Commands enter the same instantaneous Norton law as event-defined amplitudes.
    expected: np.ndarray = 3.0 * (offsets + commands * np.sin(np.deg2rad(angles)) - voltages)
    np.testing.assert_allclose(current, expected, atol=1.0e-12, rtol=1.0e-12)
    assert residual < 1.0e-12


@pytest.mark.parametrize("amplitude_scale, angle_scale", ((1.0, 1.0), (1.0, 0.0), (0.0, 1.0)))
def test_controlled_phase_selective_current_source_initialization_matches_waveform(amplitude_scale: float,
                                                                                  angle_scale: float) -> None:
    """Check commanded current seeds with only the BC terminals enabled.

    :param amplitude_scale: Scale for external current commands, including zero.
    :param angle_scale: Scale for phase offsets, including the zero-angle control.
    :return: None; the prescribed currents and actual algebraic residual are checked.
    """
    template: EmtModelTemplate = get_controlled_current_source_emt_template(vf=VarFactory(), phA=False)
    labels: tuple[str, ...] = ("B", "C")
    commands: np.ndarray = amplitude_scale * np.array((1.0, 3.0))
    angles: np.ndarray = angle_scale * np.array((-80.0, 155.0))
    offsets: np.ndarray = np.array((-0.15, 0.4))
    voltages: np.ndarray = np.array((-0.35, 0.9))
    inputs: np.ndarray = np.column_stack((voltages, commands)).ravel()
    prefixes: tuple[str, ...] = ("phi_deg", "I_offset")
    event_values: np.ndarray = np.vstack((angles, offsets))
    row: int
    index: int
    prefix: str
    label: str
    overrides: tuple[tuple[str, float], ...] = tuple(
        (f"{prefix}_{label}", float(event_values[row, index]))
        for row, prefix in enumerate(prefixes) for index, label in enumerate(labels))
    current: np.ndarray
    residual: float
    current, residual = _evaluate_seeded_source(template, inputs, overrides)

    # Evaluate the independent waveform rather than rebuilding symbolic equations.
    expected: np.ndarray = offsets + commands * np.sin(np.deg2rad(angles))
    np.testing.assert_allclose(current, expected, atol=1.0e-12, rtol=1.0e-12)
    assert residual < 1.0e-12


@pytest.mark.parametrize("amplitude_value, phase_a_deg", ((2.0, 30.0), (2.0, 0.0), (0.0, 30.0)))
def test_balanced_voltage_source_initialization_control(amplitude_value: float, phase_a_deg: float) -> None:
    """Control the evaluator with the existing balanced ABC voltage source.

    :param amplitude_value: Common sinusoidal amplitude, including the zero control.
    :param phase_a_deg: Phase-A offset; B and C remain separated by 120 degrees.
    :return: None; the unchanged balanced source must satisfy the same Norton law.
    """
    template: EmtModelTemplate = get_balanced_3ph_voltage_source_emt_template(
        vf=VarFactory(), amplitude_value=amplitude_value, phase_a_deg=phase_a_deg,
        offset_value=0.25, source_conductance_value=3.0)
    voltages: np.ndarray = np.array((0.2, -0.35, 0.9))
    current: np.ndarray
    residual: float
    current, residual = _evaluate_seeded_source(template, voltages)

    # The existing balanced family is a control for angle and injection conventions.
    angles: np.ndarray = phase_a_deg + np.array((0.0, -120.0, 120.0))
    expected: np.ndarray = 3.0 * (0.25 + amplitude_value * np.sin(np.deg2rad(angles)) - voltages)
    np.testing.assert_allclose(current, expected, atol=1.0e-12, rtol=1.0e-12)
    assert residual < 1.0e-12
