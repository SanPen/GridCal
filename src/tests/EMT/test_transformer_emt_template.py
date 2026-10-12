from __future__ import annotations

import numpy as np
import pytest
from scipy.sparse import csc_matrix

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.static_parameter_mapping_unified import assign_static_api_object_mapping_for_device
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Templates.Emt.transformer_emt_template import get_series_transformer_emt_template
from VeraGridEngine.Topology.admittance_matrices import AdmittanceMatrices, compute_admittances
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var, eval_uid
from VeraGridEngine.enumerations import ParamPowerFlowReferenceType


@pytest.mark.parametrize("tap_module", (0.9, 1.0, 1.1))
@pytest.mark.parametrize("frequency", (50.0, 60.0))
@pytest.mark.parametrize("mapped_parameters", (False, True))
def test_series_transformer_matches_static_fixed_tap(
        tap_module: float, frequency: float, mapped_parameters: bool,
) -> None:
    """Check terminal powers and periodic initialization against the static equivalent.

    :param tap_module: Fixed transformer magnitude tap.
    :param frequency: Network frequency in Hz.
    :param mapped_parameters: Resolve R/X/tap through the real static-device mapper.
    :return: None.
    """
    # Equal voltage bases isolate the existing fixed magnitude tap convention.
    grid: MultiCircuit = MultiCircuit(Sbase=100.0, fbase=frequency)
    source: Bus = grid.add_bus(Bus(name="Source", Vnom=20.0))
    target: Bus = grid.add_bus(Bus(name="Target", Vnom=20.0))
    transformer: Transformer2W = Transformer2W(
        bus_from=source, bus_to=target, HV=20.0, LV=20.0,
        r=0.01, x=0.1, g=0.0, b=0.0, tap_module=tap_module, tap_phase=0.0,
    )
    grid.add_transformer2w(transformer)
    factory: VarFactory = VarFactory()
    template: EmtModelTemplate = get_series_transformer_emt_template(
        vf=factory, r=None if mapped_parameters else transformer.R,
        x=None if mapped_parameters else transformer.X,
        tap_module=None if mapped_parameters else tap_module,
    )
    mapping: dict[Var, Const] = dict()
    assign_static_api_object_mapping_for_device(
        grid=grid, device=transformer, mdl=template.block,
        problem_mapping=mapping, logger=Logger(),
    )
    bindings: dict[int, float | complex] = dict()
    variable: Var
    constant: Const
    for variable, constant in mapping.items():
        assert constant.value is not None
        bindings[variable.uid] = float(constant.value)
    omega: float = 2.0 * np.pi * frequency
    assert bindings[template.block.api_obj_mapping[ParamPowerFlowReferenceType.omega_base].uid] == omega

    # The analytical oracle does not reuse the symbolic R/L expression.
    voltage_from: complex = 1.0 + 0.1j
    voltage_to: complex = 0.96 - 0.1j
    expected_from: complex = (voltage_from - tap_module * voltage_to) / (tap_module * tap_module * complex(0.01, 0.1))
    expected_to: complex = -tap_module * expected_from
    static: AdmittanceMatrices = compute_admittances(
        R=np.array((0.01,)), X=np.array((0.1,)), G=np.zeros(1), B=np.zeros(1),
        tap_module=np.array((tap_module,)), vtap_f=np.ones(1), vtap_t=np.ones(1),
        tap_angle=np.zeros(1), Cf=csc_matrix(np.array(((1.0, 0.0),))),
        Ct=csc_matrix(np.array(((0.0, 1.0),))), Yshunt_bus=np.zeros(2, dtype=complex),
        conn=np.zeros(1, dtype=int), seq=1,
    )
    static_voltages: np.ndarray = np.array((voltage_from, voltage_to))
    np.testing.assert_allclose(static.Yf @ static_voltages, np.array((expected_from,)), rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(static.Yt @ static_voltages, np.array((expected_to,)), rtol=1e-10, atol=1e-12)
    phase_factors: np.ndarray = np.exp(1j * np.array((0.0, -2.0 * np.pi / 3.0, 2.0 * np.pi / 3.0)))
    voltage_phasors: np.ndarray = np.concatenate((voltage_from * phase_factors, voltage_to * phase_factors))
    assert len(template.block.state_vars) == len(template.block.diff_vars) == 3
    assert len(template.block.in_vars) == len(template.block.out_vars) == 6
    assert tuple(variable.name for variable in template.block.state_vars) == ("i_ser_A", "i_ser_B", "i_ser_C")
    assert tuple(variable.name for variable in template.block.out_vars) == ("if_A", "if_B", "if_C", "it_A", "it_B", "it_C")
    assert tuple(template.block.init_eqs) == tuple(template.block.state_vars)
    assert tuple(template.block.diff_init_eqs) == tuple(template.block.diff_vars)

    # Extract the linear frequency response from the actual symbolic equations.
    index: int
    expression: Expr
    for variable in template.block.state_vars:
        bindings[variable.uid] = 0.0
    for variable in template.block.algebraic_vars:
        bindings[variable.uid] = 0.0
    for index, variable in enumerate(template.block.in_vars):
        bindings[variable.uid] = complex(voltage_phasors[index])
    forcing: np.ndarray = np.empty(3, dtype=complex)
    damping: np.ndarray = np.empty(3, dtype=complex)
    for index, expression in enumerate(template.block.state_eqs):
        forcing[index] = eval_uid(expression, bindings)
    for variable in template.block.in_vars:
        bindings[variable.uid] = 0.0
    for variable in template.block.state_vars:
        bindings[variable.uid] = 1.0
    for index, expression in enumerate(template.block.state_eqs):
        damping[index] = eval_uid(expression, bindings)
    state_phasors: np.ndarray = forcing / (1j * omega - damping)
    for index, variable in enumerate(template.block.state_vars):
        bindings[variable.uid] = complex(state_phasors[index])
    terminal_phasors: np.ndarray = np.empty(6, dtype=complex)
    for index, expression in enumerate(template.block.algebraic_eqs):
        terminal_phasors[index] = -eval_uid(expression, bindings)
    expected_terminals: np.ndarray = np.concatenate((expected_from * phase_factors, expected_to * phase_factors))
    np.testing.assert_allclose(terminal_phasors, expected_terminals, rtol=1e-8, atol=1e-8)
    from_power: complex = complex(np.vdot(terminal_phasors[:3], voltage_phasors[:3]) / 3.0)
    to_power: complex = complex(np.vdot(terminal_phasors[3:], voltage_phasors[3:]) / 3.0)
    np.testing.assert_allclose(from_power, voltage_from * np.conj(expected_from), rtol=1e-8, atol=1e-8)
    np.testing.assert_allclose(to_power, voltage_to * np.conj(expected_to), rtol=1e-8, atol=1e-8)
    np.testing.assert_allclose((from_power + to_power).real, 0.01 * abs(tap_module * expected_from) ** 2, rtol=1e-8, atol=1e-8)

    # Static periodic currents must satisfy initialization and the ODE throughout a cycle.
    angle: float
    rotation: complex
    periodic_currents: np.ndarray
    periodic_derivatives: np.ndarray
    actual_derivatives: np.ndarray = np.empty(3)
    algebraic_residual: np.ndarray = np.empty(6)
    for angle in (0.0, 0.37, 1.14, 2.4):
        rotation = complex(np.exp(1j * angle))
        periodic_currents = np.sqrt(2.0) * np.imag(expected_terminals * rotation)
        periodic_derivatives = omega * np.sqrt(2.0) * np.real(expected_from * phase_factors * rotation)
        for index, variable in enumerate(template.block.in_vars):
            bindings[variable.uid] = float(np.sqrt(2.0) * np.imag(voltage_phasors[index] * rotation))
        for index, variable in enumerate(template.block.algebraic_vars):
            bindings[variable.uid] = float(periodic_currents[index])
        for index, variable in enumerate(template.block.state_vars):
            bindings[variable.uid] = float(periodic_currents[index])
            np.testing.assert_allclose(eval_uid(template.block.init_eqs[variable], bindings),
                                       periodic_currents[index], rtol=1e-10, atol=1e-11)
        for index, expression in enumerate(template.block.state_eqs):
            actual_derivatives[index] = eval_uid(expression, bindings)
            np.testing.assert_allclose(eval_uid(template.block.diff_init_eqs[template.block.diff_vars[index]], bindings),
                                       actual_derivatives[index], rtol=0.0, atol=0.0)
        for index, expression in enumerate(template.block.algebraic_eqs):
            algebraic_residual[index] = eval_uid(expression, bindings)
        np.testing.assert_allclose(algebraic_residual, 0.0, rtol=0.0, atol=1e-12)
        np.testing.assert_allclose(actual_derivatives, periodic_derivatives, rtol=1e-8, atol=1e-5)
    assert transformer.R == 0.01 and transformer.X == 0.1 and transformer.tap_module == tap_module



# def test_transformer_emt_template_exposes_neutral_ports_for_grounded_star_sides() -> None:
#     vf = VarFactory()
#     templ = get_transformer_emt_template(
#         vf=vf,
#         conn_f=WindingType.GroundedStar,
#         conn_t=WindingType.GroundedStar,
#         name="trafo_yg_yg",
#     )
#     input_names = [var.name for var in templ.block.in_vars]
#     output_names = [var.name for var in templ.block.out_vars]
#
#     assert input_names[:4] == ["vf_N_trafo_yg_yg", "vf_A_trafo_yg_yg", "vf_B_trafo_yg_yg", "vf_C_trafo_yg_yg"]
#     assert input_names[4:] == ["vt_N_trafo_yg_yg", "vt_A_trafo_yg_yg", "vt_B_trafo_yg_yg", "vt_C_trafo_yg_yg"]
#     assert output_names[0] == "if_trafo_yg_yg_N"
#     assert output_names[4] == "it_trafo_yg_yg_N"
#     assert templ.block.external_mapping[VarPowerFlowReferenceType.vf_N] is templ.block.in_vars[0]
#     assert templ.block.external_mapping[VarPowerFlowReferenceType.vt_N] is templ.block.in_vars[4]
#     assert templ.block.external_mapping[VarPowerFlowReferenceType.if_N] is templ.block.out_vars[0]
#     assert templ.block.external_mapping[VarPowerFlowReferenceType.it_N] is templ.block.out_vars[4]
#     assert any(node.tpe == BlockType.GROUNDING_LINK_EMT.name for node in templ.block.diagram.node_data.values())
#
#
# def test_transformer_emt_template_exposes_neutral_only_on_star_side_of_delta_wye() -> None:
#     vf = VarFactory()
#     templ = get_transformer_emt_template(
#         vf=vf,
#         conn_f=WindingType.Delta,
#         conn_t=WindingType.GroundedStar,
#         name="trafo_d_yg",
#     )
#     input_names = [var.name for var in templ.block.in_vars]
#     output_names = [var.name for var in templ.block.out_vars]
#
#     assert input_names[:3] == ["vf_A_trafo_d_yg", "vf_B_trafo_d_yg", "vf_C_trafo_d_yg"]
#     assert input_names[3:] == ["vt_N_trafo_d_yg", "vt_A_trafo_d_yg", "vt_B_trafo_d_yg", "vt_C_trafo_d_yg"]
#     assert output_names[0] == "if_trafo_d_yg_A"
#     assert output_names[3] == "it_trafo_d_yg_N"
#     assert templ.block.external_mapping[VarPowerFlowReferenceType.vf_N] is None
#     assert templ.block.external_mapping[VarPowerFlowReferenceType.if_N] is None
#     assert templ.block.external_mapping[VarPowerFlowReferenceType.vt_N] is templ.block.in_vars[3]
#     assert templ.block.external_mapping[VarPowerFlowReferenceType.it_N] is templ.block.out_vars[3]
#
#
# def test_transformer_emt_template_treats_zigzag_as_one_non_neutral_side() -> None:
#     vf = VarFactory()
#     templ = get_transformer_emt_template(
#         vf=vf,
#         conn_f=WindingType.ZigZag,
#         conn_t=WindingType.GroundedStar,
#         name="trafo_z_yg",
#     )
#     input_names = [var.name for var in templ.block.in_vars]
#
#     assert input_names[:3] == ["vf_A_trafo_z_yg", "vf_B_trafo_z_yg", "vf_C_trafo_z_yg"]
#     assert templ.block.external_mapping[VarPowerFlowReferenceType.vf_N] is None
#     assert templ.block.external_mapping[VarPowerFlowReferenceType.if_N] is None
