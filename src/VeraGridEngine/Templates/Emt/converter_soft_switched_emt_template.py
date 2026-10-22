# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, Tuple

import numpy as np

import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Emt.bridge_filter_control_2level_3ph_soft_emt_template import get_bridge_filter_control_2level_3ph_soft_emt_template
from VeraGridEngine.Utils.Symbolic.block import Block, VarPowerFlowReferenceType, build_name_to_var_lookup
from VeraGridEngine.Utils.Symbolic.symbolic import BinOp, Const, Expr, Var
from VeraGridEngine.Utils.procedural_logic import startup_handover
from VeraGridEngine.enumerations import ConverterControlType, DeviceType, ParamPowerFlowReferenceType


def _converter_control_type_code(control: ConverterControlType | None) -> int:
    """
    Return the integer code used by EMT converter control-mode parameters.

    The switched converter intentionally keeps local copies of the converter helper
    routines it reuses, so this template does not depend on another converter
    template module.

    :param control: Converter control enum.
    :return: Encoded integer value.
    """
    code_dict: Dict[ConverterControlType | None, int] = {
        None: 0,
        ConverterControlType.Vm_dc: 1,
        ConverterControlType.Vm_ac: 2,
        ConverterControlType.Va_ac: 3,
        ConverterControlType.Qac: 4,
        ConverterControlType.Pdc: 5,
        ConverterControlType.Pac: 6,
        ConverterControlType.Pdc_angle_droop: 7,
        ConverterControlType.Imax: 8,
    }
    return code_dict[control]


def _converter_control_match_expr(control_var: Var, control_type: ConverterControlType | None) -> Expr:
    """
    Build one symbolic match expression for a converter control mode.

    :param control_var: Runtime control-mode variable.
    :param control_type: Requested control enum.
    :return: Boolean-like symbolic expression.
    """
    return (control_var == _converter_control_type_code(control_type)).to_expression()


def _resolve_converter_control_reference_exprs(
        control1: Var,
        control2: Var,
        control1_val: Var,
        control2_val: Var,
        p0: Var,
) -> Tuple[Expr, Expr, Expr, Expr, Expr]:
    """
    Resolve the active-power, reactive-power and DC-voltage references from control modes.

    :param control1: First control-mode code.
    :param control2: Second control-mode code.
    :param control1_val: First control target.
    :param control2_val: Second control target.
    :param p0: Scheduled active-power fallback.
    :return: Tuple ``(p_ref, q_ref, vdc_ref, regulate_vdc, regulate_q)``.
    """
    control1_is_vm_dc: Expr = _converter_control_match_expr(control1, ConverterControlType.Vm_dc)
    control2_is_vm_dc: Expr = _converter_control_match_expr(control2, ConverterControlType.Vm_dc)
    control1_is_qac: Expr = _converter_control_match_expr(control1, ConverterControlType.Qac)
    control2_is_qac: Expr = _converter_control_match_expr(control2, ConverterControlType.Qac)
    control1_is_pac: Expr = _converter_control_match_expr(control1, ConverterControlType.Pac)
    control2_is_pac: Expr = _converter_control_match_expr(control2, ConverterControlType.Pac)
    control1_is_pdc: Expr = _converter_control_match_expr(control1, ConverterControlType.Pdc)
    control2_is_pdc: Expr = _converter_control_match_expr(control2, ConverterControlType.Pdc)

    regulate_vdc: Expr = sym.max(control1_is_vm_dc, control2_is_vm_dc)
    regulate_q: Expr = sym.max(control1_is_qac, control2_is_qac)
    vdc_ref: Expr = (
        control1_is_vm_dc * control1_val
        + (Const(1.0) - control1_is_vm_dc)
        * (control2_is_vm_dc * control2_val + (Const(1.0) - control2_is_vm_dc) * Const(1.0))
    )
    q_ref: Expr = (
        control1_is_qac * control1_val
        + (Const(1.0) - control1_is_qac)
        * (control2_is_qac * control2_val + (Const(1.0) - control2_is_qac) * Const(0.0))
    )
    p_ref: Expr = (
        (control1_is_pac + control1_is_pdc) * control1_val
        + (Const(1.0) - (control1_is_pac + control1_is_pdc))
        * ((control2_is_pac + control2_is_pdc) * control2_val + (Const(1.0) - (control2_is_pac + control2_is_pdc)) * p0)
    )

    return p_ref, q_ref, vdc_ref, regulate_vdc, regulate_q


def _build_pseudo_emt_converter_vsc_block(vf: VarFactory, name: str) -> Block:
    """
    Build the averaged converter electrical/DC block reused by the switched template.

    This is a local copy on purpose: the switched converter may reuse the validated
    DC-side model, but it should not import private helpers from another converter
    template module.

    :param vf: Shared EMT variable factory.
    :param name: Symbolic model name suffix.
    :return: VSC/DC block.
    """
    v_d: Var = vf.add_var(name=f"v_d_in")
    v_q: Var = vf.add_var(name=f"v_q_in")
    v_0: Var = vf.add_var(name=f"v_0_in")
    i_d: Var = vf.add_var(name=f"i_d_in")
    i_q: Var = vf.add_var(name=f"i_q_in")
    i_0: Var = vf.add_var(name=f"i_0_in")
    v_dc_bus: Var = vf.add_var(name=f"v_dc_bus_in", reference=VarPowerFlowReferenceType.Vdc)

    v_dc: Var = vf.add_var(name=f"v_dc")
    d_v_dc: Var = vf.add_diff_var(name=f"d_v_dc", base_var=v_dc)

    i_dc: Var = vf.add_var(name=f"i_dc", reference=VarPowerFlowReferenceType.Idc)
    P: Var = vf.add_var(name=f"P", reference=VarPowerFlowReferenceType.P)
    Q: Var = vf.add_var(name=f"Q", reference=VarPowerFlowReferenceType.Q)
    i_mag: Var = vf.add_var(name=f"i_mag")
    P_loss: Var = vf.add_var(name=f"P_loss")
    i_dc_conv: Var = vf.add_var(name=f"i_dc_conv")

    sbase: Var = vf.add_var(name=f"sbase")
    P_ref: Var = vf.add_var(name=f"P_ref")
    Q_ref: Var = vf.add_var(name=f"Q_ref")
    Vdc_ref: Var = vf.add_var(name=f"Vdc_ref")
    P0_sched: Var = vf.add_var(name=f"P0")
    control1: Var = vf.add_var(name=f"control1")
    control2: Var = vf.add_var(name=f"control2")
    control1_val: Var = vf.add_var(name=f"control1_val")
    control2_val: Var = vf.add_var(name=f"control2_val")
    omega_base: Var = vf.add_var(name=f"omega_base")
    phi_v: Var = vf.add_var(name=f"phi_v")
    Vpk: Var = vf.add_var(name=f"Vpk")
    R_eq: Var = vf.add_var(name=f"R_eq")
    L_eq: Var = vf.add_var(name=f"L_eq")
    C_dc: Var = vf.add_var(name=f"C_dc")
    R_dc: Var = vf.add_var(name=f"R_dc")
    R_dc_term: Var = vf.add_var(name=f"R_dc_term")
    pll_kp: Var = vf.add_var(name=f"pll_kp")
    pll_ki: Var = vf.add_var(name=f"pll_ki")
    i_kp: Var = vf.add_var(name=f"i_kp")
    i_ki: Var = vf.add_var(name=f"i_ki")
    vdc_kp: Var = vf.add_var(name=f"vdc_kp")
    vdc_ki: Var = vf.add_var(name=f"vdc_ki")
    q_kp: Var = vf.add_var(name=f"q_kp")
    q_ki: Var = vf.add_var(name=f"q_ki")
    i_max: Var = vf.add_var(name=f"i_max")
    m_max: Var = vf.add_var(name=f"m_max")
    P_loss0: Var = vf.add_var(name=f"P_loss0")
    P_loss_i1: Var = vf.add_var(name=f"P_loss_i1")
    P_loss_i2: Var = vf.add_var(name=f"P_loss_i2")
    tau_meas: Var = vf.add_var(name=f"tau_meas")
    aw_gain: Var = vf.add_var(name=f"aw_gain")
    vdc_floor: Var = vf.add_var(name=f"vdc_floor")

    p_ref_expr: Expr
    q_ref_expr: Expr
    vdc_ref_expr: Expr
    _unused_regulate_vdc: Expr
    _unused_regulate_q: Expr
    p_ref_expr, q_ref_expr, vdc_ref_expr, _unused_regulate_vdc, _unused_regulate_q = _resolve_converter_control_reference_exprs(
        control1=control1,
        control2=control2,
        control1_val=control1_val,
        control2_val=control2_val,
        p0=P0_sched,
    )

    eps: Const = vf.add_const(1e-10)
    c0: Const = vf.add_const(0.0)
    c1: Const = vf.add_const(1.0)
    c3: Const = vf.add_const(3.0)
    c32: Const = vf.add_const(1.5)

    P_loss0_pu: Expr = P_loss0 / sbase
    P_loss_i1_pu: Expr = P_loss_i1 / sbase
    P_loss_i2_pu: Expr = P_loss_i2 / sbase
    i_leak: Expr = v_dc / R_dc
    v_dc_eff: Expr = sym.max(v_dc, vdc_floor)

    i_d0: Expr = (Const(2.0 / 3.0) * ((P_ref / sbase) + (P_loss0 / sbase))) / (Vpk + eps)
    i_q0: Expr = (Const(2.0 / 3.0) * (Q_ref / sbase)) / (Vpk + eps)
    i_mag0: Expr = sym.sqrt(i_d0 * i_d0 + i_q0 * i_q0 + eps)
    P0: Expr = c32 * Vpk * i_d0
    Q0: Expr = c32 * Vpk * i_q0
    P_loss0_expr: Expr = P_loss0_pu + P_loss_i1_pu * i_mag0 + P_loss_i2_pu * i_mag0 * i_mag0
    i_dc_conv0: Expr = -(P0 - P_loss0_expr) / (Vdc_ref + eps)
    i_dc0: Expr = (i_dc_conv0 + v_dc_bus / R_dc) / (c1 + R_dc_term / R_dc)
    v_dc0: Expr = v_dc_bus - R_dc_term * i_dc0

    block: Block = Block(
        state_eqs=list([
            (i_dc - i_dc_conv - i_leak) / C_dc,
        ]),
        state_vars=list([v_dc]),
        diff_vars=list([d_v_dc]),
        algebraic_eqs=list([
            P_ref - p_ref_expr,
            Q_ref - q_ref_expr,
            Vdc_ref - vdc_ref_expr,
            P - (c32 * (v_d * i_d + v_q * i_q) + c3 * v_0 * i_0),
            Q - c32 * (v_d * i_q - v_q * i_d),
            i_mag - sym.sqrt(i_d * i_d + i_q * i_q + c3 * i_0 * i_0 + eps),
            P_loss - (P_loss0_pu + P_loss_i1_pu * i_mag + P_loss_i2_pu * i_mag * i_mag),
            i_dc_conv + (P - P_loss) / v_dc_eff,
            i_dc - (v_dc_bus - v_dc) / R_dc_term,
        ]),
        algebraic_vars=list([P_ref, Q_ref, Vdc_ref, i_dc, P, Q, i_mag, P_loss, i_dc_conv]),
        event_dict=dict([
            (control1, vf.add_const(float(_converter_control_type_code(ConverterControlType.Vm_dc)))),
            (control2, vf.add_const(float(_converter_control_type_code(ConverterControlType.Qac)))),
            (control1_val, vf.add_const(1.0)),
            (control2_val, vf.add_const(0.0)),
            (P0_sched, vf.add_const(0.0)),
            (phi_v, vf.add_const(0.0)),
            (Vpk, vf.add_const(np.sqrt(2.0))),
            (R_eq, vf.add_const(max(0.02, 1e-9))),
            (L_eq, vf.add_const(max(0.08, 1e-9))),
            (C_dc, vf.add_const(max(0.05, 1e-9))),
            (R_dc, vf.add_const(max(1e6, 1e-9))),
            (R_dc_term, vf.add_const(max(0.0001, 1e-9))),
            (pll_kp, vf.add_const(40.0)),
            (pll_ki, vf.add_const(400.0)),
            (i_kp, vf.add_const(0.5)),
            (i_ki, vf.add_const(40.0)),
            (vdc_kp, vf.add_const(1.5)),
            (vdc_ki, vf.add_const(30.0)),
            (q_kp, vf.add_const(0.6)),
            (q_ki, vf.add_const(25.0)),
            (i_max, vf.add_const(max(1.2, 1e-6))),
            (m_max, vf.add_const(max(0.95, 1e-6))),
            (P_loss_i1, vf.add_const(0.01)),
            (P_loss_i2, vf.add_const(0.01)),
            (tau_meas, vf.add_const(max(0.01, 1e-6))),
            (aw_gain, vf.add_const(1.0)),
            (vdc_floor, vf.add_const(max(0.05, 1e-6))),
        ]),
        parameters={
            sbase: vf.add_const(1.0),
            omega_base: vf.add_const(2.0 * np.pi * 50.0),
            P_loss0: vf.add_const(0.0),
        },
        init_eqs=dict([
            (v_dc, v_dc0),
            (P_ref, p_ref_expr),
            (Q_ref, q_ref_expr),
            (Vdc_ref, vdc_ref_expr),
            (i_dc, i_dc0),
            (P, P0),
            (Q, Q0),
            (i_mag, i_mag0),
            (P_loss, P_loss0_expr),
            (i_dc_conv, i_dc_conv0),
        ]),
        diff_init_eqs=dict([
            (d_v_dc, c0),
        ]),
        in_vars=list([v_d, v_q, v_0, i_d, i_q, i_0, v_dc_bus]),
        out_vars=list([
            v_dc, i_dc, P, Q,
            sbase, P_ref, Q_ref, Vdc_ref, omega_base, phi_v, Vpk,
            R_eq, L_eq, C_dc, R_dc, R_dc_term,
            pll_kp, pll_ki, i_kp, i_ki,
            vdc_kp, vdc_ki, q_kp, q_ki,
            i_max, m_max, P_loss0, P_loss_i1, P_loss_i2, tau_meas, aw_gain, vdc_floor,
        ]),
        name=f"{name}_vsc",
    )
    block.api_obj_mapping = dict([
        (ParamPowerFlowReferenceType.Sbase, sbase),
        (ParamPowerFlowReferenceType.P0, P0_sched),
        (ParamPowerFlowReferenceType.alpha1, P_loss0),
        (ParamPowerFlowReferenceType.alpha2, P_loss_i1),
        (ParamPowerFlowReferenceType.alpha3, P_loss_i2),
        (ParamPowerFlowReferenceType.omega_base, omega_base),
        (ParamPowerFlowReferenceType.converter_control_mode_1, control1),
        (ParamPowerFlowReferenceType.converter_control_mode_2, control2),
        (ParamPowerFlowReferenceType.converter_control_target_1, control1_val),
        (ParamPowerFlowReferenceType.converter_control_target_2, control2_val),
    ])
    return block


def _build_pseudo_emt_converter_outer_loop_block(vf: VarFactory, name: str) -> Block:
    """
    Build the averaged converter outer-loop block reused by the switched template.

    This local copy is kept in sync intentionally so the switched converter does not
    import private helpers from another converter template module.

    :param vf: Shared EMT variable factory.
    :param name: Symbolic model name suffix.
    :return: Outer-loop block.
    """
    v_d: Var = vf.add_var(name=f"v_d_outer_in")
    v_q: Var = vf.add_var(name=f"v_q_outer_in")
    v_0: Var = vf.add_var(name=f"v_0_outer_in")
    i_d: Var = vf.add_var(name=f"i_d_outer_in")
    i_q: Var = vf.add_var(name=f"i_q_outer_in")
    i_0: Var = vf.add_var(name=f"i_0_outer_in")
    v_dc: Var = vf.add_var(name=f"v_dc_outer_in")
    P: Var = vf.add_var(name=f"P_outer_in")
    Q: Var = vf.add_var(name=f"Q_outer_in")
    sbase: Var = vf.add_var(name=f"sbase_outer_in")
    P_ref: Var = vf.add_var(name=f"P_ref_outer_in")
    Q_ref: Var = vf.add_var(name=f"Q_ref_outer_in")
    Vdc_ref: Var = vf.add_var(name=f"Vdc_ref_outer_in")
    Vpk: Var = vf.add_var(name=f"Vpk_outer_in")
    P_loss0: Var = vf.add_var(name=f"P_loss0_outer_in")
    vdc_kp: Var = vf.add_var(name=f"vdc_kp_outer_in")
    vdc_ki: Var = vf.add_var(name=f"vdc_ki_outer_in")
    q_kp: Var = vf.add_var(name=f"q_kp_outer_in")
    q_ki: Var = vf.add_var(name=f"q_ki_outer_in")
    i_max: Var = vf.add_var(name=f"i_max_outer_in")
    tau_meas: Var = vf.add_var(name=f"tau_meas_outer_in")
    aw_gain: Var = vf.add_var(name=f"aw_gain_outer_in")

    xi_vdc: Var = vf.add_var(name=f"xi_vdc")
    xi_q: Var = vf.add_var(name=f"xi_q")
    P_f: Var = vf.add_var(name=f"P_f")
    Q_f: Var = vf.add_var(name=f"Q_f")

    d_xi_vdc: Var = vf.add_diff_var(name=f"d_xi_vdc", base_var=xi_vdc)
    d_xi_q: Var = vf.add_diff_var(name=f"d_xi_q", base_var=xi_q)
    d_P_f: Var = vf.add_diff_var(name=f"d_P_f", base_var=P_f)
    d_Q_f: Var = vf.add_diff_var(name=f"d_Q_f", base_var=Q_f)

    v_mag: Var = vf.add_var(name=f"v_mag")
    i_d_ff: Var = vf.add_var(name=f"i_d_ff")
    i_q_ff: Var = vf.add_var(name=f"i_q_ff")
    i_0_ref_u: Var = vf.add_var(name=f"i_0_ref_u")
    i_d_ref_u: Var = vf.add_var(name=f"i_d_ref_u")
    i_q_ref_u: Var = vf.add_var(name=f"i_q_ref_u")
    i_0_ref: Var = vf.add_var(name=f"i_0_ref")
    i_d_ref: Var = vf.add_var(name=f"i_d_ref")
    i_q_ref: Var = vf.add_var(name=f"i_q_ref")

    eps: Const = vf.add_const(1e-10)
    c0: Const = vf.add_const(0.0)
    c23: Const = vf.add_const(2.0 / 3.0)
    c3: Const = vf.add_const(3.0)
    c32: Const = vf.add_const(1.5)

    P_ref_pu: Expr = P_ref / sbase
    Q_ref_pu: Expr = Q_ref / sbase
    P_ac_ff_pu: Expr = P_ref_pu + P_loss0 / sbase

    i_d0: Expr = c23 * P_ac_ff_pu / (Vpk + eps)
    i_q0: Expr = c23 * Q_ref_pu / (Vpk + eps)
    Q0: Expr = c32 * Vpk * i_q0

    i_d_cap: Expr = sym.hard_sat(i_d_ref_u, -i_max, i_max)
    i_q_cap: Expr = sym.sqrt(sym.max(i_max * i_max - i_d_ref * i_d_ref, eps))
    i_0_cap: Expr = sym.sqrt(sym.max((i_max * i_max - i_d_ref * i_d_ref - i_q_ref * i_q_ref) / c3, eps / c3))

    return Block(
        state_eqs=list([
            vdc_ki * ((Vdc_ref - v_dc) + aw_gain * (i_d_ref - i_d_ref_u)),
            q_ki * ((Q_ref_pu - Q_f) + aw_gain * (i_q_ref - i_q_ref_u)),
            (P - P_f) / tau_meas,
            (Q - Q_f) / tau_meas,
        ]),
        state_vars=list([xi_vdc, xi_q, P_f, Q_f]),
        diff_vars=list([d_xi_vdc, d_xi_q, d_P_f, d_Q_f]),
        algebraic_eqs=list([
            v_mag - sym.sqrt(v_d * v_d + v_q * v_q + eps),
            i_d_ff - c23 * P_ac_ff_pu / (v_mag + eps),
            i_q_ff - c23 * Q_ref_pu / (v_mag + eps),
            i_0_ref_u,
            i_d_ref_u - (i_d_ff + vdc_kp * (Vdc_ref - v_dc) + xi_vdc),
            i_d_ref - i_d_cap,
            i_q_ref_u - (i_q_ff + q_kp * (Q_ref_pu - Q_f) + xi_q),
            i_q_ref - sym.hard_sat(i_q_ref_u, -i_q_cap, i_q_cap),
            i_0_ref - sym.hard_sat(i_0_ref_u, -i_0_cap, i_0_cap),
        ]),
        algebraic_vars=list([v_mag, i_d_ff, i_q_ff, i_0_ref_u, i_d_ref_u, i_q_ref_u, i_0_ref, i_d_ref, i_q_ref]),
        init_eqs=dict([
            (xi_vdc, i_d0 - (c23 * P_ac_ff_pu / (Vpk + eps)) - vdc_kp * (Vdc_ref - v_dc)),
            (xi_q, i_q0 - (c23 * Q_ref_pu / (Vpk + eps)) - q_kp * (Q_ref_pu - Q0)),
            (P_f, P),
            (Q_f, Q0),
            (v_mag, Vpk),
            (i_d_ff, c23 * P_ac_ff_pu / (Vpk + eps)),
            (i_q_ff, c23 * Q_ref_pu / (Vpk + eps)),
            (i_0_ref_u, c0),
            (i_d_ref_u, i_d0),
            (i_q_ref_u, i_q0),
            (i_0_ref, c0),
            (i_d_ref, i_d0),
            (i_q_ref, i_q0),
        ]),
        diff_init_eqs=dict([
            (d_xi_vdc, c0),
            (d_xi_q, c0),
            (d_P_f, c0),
            (d_Q_f, c0),
        ]),
        in_vars=list([
            v_d, v_q, v_0, i_d, i_q, i_0, v_dc, P, Q,
            sbase, P_ref, Q_ref, Vdc_ref, Vpk, P_loss0,
            vdc_kp, vdc_ki, q_kp, q_ki, i_max, tau_meas, aw_gain,
        ]),
        out_vars=list([P_f, Q_f, i_0_ref, i_d_ref, i_q_ref]),
        name=f"{name}_outer_loop",
    )


def _build_switched_converter_data_block(vf: VarFactory, name: str) -> Block:
    """
    Build the parameter and DC-link block of the switched EMT converter.

    The switched converter must preserve the validated pseudo-EMT DC-side model.
    The hybrid handover is introduced only in the converter-current forcing term:
    before the exact handover time the DC-link uses the averaged converter current,
    and after the handover time it uses the switched bridge current.

    :param vf: Shared EMT variable factory.
    :param name: Symbolic model name suffix.
    :return: Data and DC-link block.
    """
    block: Block = _build_pseudo_emt_converter_vsc_block(vf=vf, name=name)
    v_d: Var = _find_var_anywhere_in_block(block=block, variable_name=f"v_d_in")
    v_q: Var = _find_var_anywhere_in_block(block=block, variable_name=f"v_q_in")
    v_0: Var = _find_var_anywhere_in_block(block=block, variable_name=f"v_0_in")
    i_d: Var = _find_var_anywhere_in_block(block=block, variable_name=f"i_d_in")
    i_q: Var = _find_var_anywhere_in_block(block=block, variable_name=f"i_q_in")
    i_0: Var = _find_var_anywhere_in_block(block=block, variable_name=f"i_0_in")
    i_A: Var = vf.add_var(name=f"i_A_in")
    i_B: Var = vf.add_var(name=f"i_B_in")
    i_C: Var = vf.add_var(name=f"i_C_in")
    gate_a: Var = vf.add_var(name=f"gate_a_in")
    gate_b: Var = vf.add_var(name=f"gate_b_in")
    gate_c: Var = vf.add_var(name=f"gate_c_in")
    v_dc_bus: Var = _find_var_anywhere_in_block(block=block, variable_name=f"v_dc_bus_in")
    switching_enabled: Var = vf.add_var(name=f"switching_enabled_in")

    v_dc: Var = _find_var_anywhere_in_block(block=block, variable_name=f"v_dc")
    i_dc: Var = _find_var_anywhere_in_block(block=block, variable_name=f"i_dc")
    P: Var = _find_var_anywhere_in_block(block=block, variable_name=f"P")
    Q: Var = _find_var_anywhere_in_block(block=block, variable_name=f"Q")
    i_mag: Var = _find_var_anywhere_in_block(block=block, variable_name=f"i_mag")
    P_loss: Var = _find_var_anywhere_in_block(block=block, variable_name=f"P_loss")
    i_dc_conv: Var = _find_var_anywhere_in_block(block=block, variable_name=f"i_dc_conv")
    k_v_conv_nom: Var = vf.add_var(name=f"k_v_conv_nom")
    P_ref: Var = _find_var_anywhere_in_block(block=block, variable_name=f"P_ref")
    Q_ref: Var = _find_var_anywhere_in_block(block=block, variable_name=f"Q_ref")
    Vdc_ref: Var = _find_var_anywhere_in_block(block=block, variable_name=f"Vdc_ref")

    sbase: Var = _find_var_anywhere_in_block(block=block, variable_name=f"sbase")
    P0_sched: Var = _find_var_anywhere_in_block(block=block, variable_name=f"P0")
    control1: Var = _find_var_anywhere_in_block(block=block, variable_name=f"control1")
    control2: Var = _find_var_anywhere_in_block(block=block, variable_name=f"control2")
    control1_val: Var = _find_var_anywhere_in_block(block=block, variable_name=f"control1_val")
    control2_val: Var = _find_var_anywhere_in_block(block=block, variable_name=f"control2_val")
    omega_base: Var = _find_var_anywhere_in_block(block=block, variable_name=f"omega_base")
    phi_v: Var = _find_var_anywhere_in_block(block=block, variable_name=f"phi_v")
    Vpk: Var = _find_var_anywhere_in_block(block=block, variable_name=f"Vpk")
    R_eq: Var = _find_var_anywhere_in_block(block=block, variable_name=f"R_eq")
    L_eq: Var = _find_var_anywhere_in_block(block=block, variable_name=f"L_eq")
    C_dc: Var = _find_var_anywhere_in_block(block=block, variable_name=f"C_dc")
    R_dc: Var = _find_var_anywhere_in_block(block=block, variable_name=f"R_dc")
    R_dc_term: Var = _find_var_anywhere_in_block(block=block, variable_name=f"R_dc_term")
    pll_kp: Var = _find_var_anywhere_in_block(block=block, variable_name=f"pll_kp")
    pll_ki: Var = _find_var_anywhere_in_block(block=block, variable_name=f"pll_ki")
    i_kp: Var = _find_var_anywhere_in_block(block=block, variable_name=f"i_kp")
    i_ki: Var = _find_var_anywhere_in_block(block=block, variable_name=f"i_ki")
    vdc_kp: Var = _find_var_anywhere_in_block(block=block, variable_name=f"vdc_kp")
    vdc_ki: Var = _find_var_anywhere_in_block(block=block, variable_name=f"vdc_ki")
    q_kp: Var = _find_var_anywhere_in_block(block=block, variable_name=f"q_kp")
    q_ki: Var = _find_var_anywhere_in_block(block=block, variable_name=f"q_ki")
    i_max: Var = _find_var_anywhere_in_block(block=block, variable_name=f"i_max")
    m_max: Var = _find_var_anywhere_in_block(block=block, variable_name=f"m_max")
    P_loss0: Var = _find_var_anywhere_in_block(block=block, variable_name=f"P_loss0")
    P_loss_i1: Var = _find_var_anywhere_in_block(block=block, variable_name=f"P_loss_i1")
    P_loss_i2: Var = _find_var_anywhere_in_block(block=block, variable_name=f"P_loss_i2")
    tau_meas: Var = _find_var_anywhere_in_block(block=block, variable_name=f"tau_meas")
    aw_gain: Var = _find_var_anywhere_in_block(block=block, variable_name=f"aw_gain")
    vdc_floor: Var = _find_var_anywhere_in_block(block=block, variable_name=f"vdc_floor")
    omega_sw: Var = vf.add_var(name=f"omega_sw")
    carrier_phase: Var = vf.add_var(name=f"carrier_phase")

    if v_d is None or v_q is None or v_0 is None or i_d is None or i_q is None or i_0 is None or v_dc_bus is None or v_dc is None or i_dc is None or P is None or Q is None or i_mag is None or P_loss is None or i_dc_conv is None or P_ref is None or Q_ref is None or Vdc_ref is None or sbase is None or P0_sched is None or control1 is None or control2 is None or control1_val is None or control2_val is None or omega_base is None or phi_v is None or Vpk is None or R_eq is None or L_eq is None or C_dc is None or R_dc is None or R_dc_term is None or pll_kp is None or pll_ki is None or i_kp is None or i_ki is None or vdc_kp is None or vdc_ki is None or q_kp is None or q_ki is None or i_max is None or m_max is None or P_loss0 is None or P_loss_i1 is None or P_loss_i2 is None or tau_meas is None or aw_gain is None or vdc_floor is None:
        raise KeyError(f"The switched EMT converter data block '{name}' could not resolve one or more pseudo-EMT variables")
    else:
        pass

    p_ref_expr: Expr
    q_ref_expr: Expr
    vdc_ref_expr: Expr
    _unused_regulate_vdc: Expr
    _unused_regulate_q: Expr
    p_ref_expr, q_ref_expr, vdc_ref_expr, _unused_regulate_vdc, _unused_regulate_q = _resolve_converter_control_reference_exprs(
        control1=control1,
        control2=control2,
        control1_val=control1_val,
        control2_val=control2_val,
        p0=P0_sched,
    )

    eps: Const = Const(1.0e-10)
    c23: Const = Const(2.0 / 3.0)
    c_one: Const = Const(1.0)
    c_two: Const = Const(2.0)
    c_three: Const = Const(3.0)
    sbase_eff: Expr = sym.max(sbase, eps)
    v_dc_eff: Expr = sym.max(v_dc, vdc_floor)
    gate_current_sum_expr: Expr = gate_a * i_A + gate_b * i_B + gate_c * i_C
    gate_sum_expr: Expr = gate_a + gate_b + gate_c
    phase_current_sum_expr: Expr = i_A + i_B + i_C
    # The switched bridge does not use physical pole voltages of ``+-v_dc/2``. Instead, each retained
    # leg is scaled as ``(2 * gate - 1) * k_v_conv * v_dc`` so the bridge reproduces the averaged
    # converter fundamental. The DC current reconstruction must therefore follow the instantaneous
    # bridge power balance rather than the unscaled gated-current sum.
    i_dc_sw_expr: Expr = -c_two * k_v_conv_nom * (
        gate_current_sum_expr - (gate_sum_expr * phase_current_sum_expr) / c_three
    )
    p_loss0_pu_expr: Expr = P_loss0 / sbase_eff
    i_dc_avg_expr: Expr = -(P - P_loss) / v_dc_eff
    i_dc_conv_eff_expr: Expr = (c_one - switching_enabled) * i_dc_avg_expr + switching_enabled * i_dc_sw_expr

    # The hybrid switched path must preserve the same nominal voltage ceiling used by the
    # validated pseudo-EMT inner loop. Rebuilding that operating-point command here keeps the
    # current controller limit aligned across the averaged and switched templates.
    i_d_nom_expr: Expr = c23 * ((P_ref / sbase_eff) + p_loss0_pu_expr) / (Vpk + eps)
    i_q_nom_expr: Expr = c23 * (Q_ref / sbase_eff) / (Vpk + eps)
    v_cmd_d_nom_expr: Expr = Vpk - R_eq * i_d_nom_expr + L_eq * i_q_nom_expr
    v_cmd_q_nom_expr: Expr = -R_eq * i_q_nom_expr - L_eq * i_d_nom_expr
    k_v_conv_nom_expr: Expr = (
        sym.sqrt(v_cmd_d_nom_expr * v_cmd_d_nom_expr + v_cmd_q_nom_expr * v_cmd_q_nom_expr + eps)
        / (m_max * sym.max(Vdc_ref, vdc_floor) + eps)
    )

    i_dc_conv_eq_index: int = _find_algebraic_equation_index_for_var(block=block, target_var=i_dc_conv)

    # The validated pseudo-EMT DC-link dynamics are preserved. Only the effective converter current
    # forcing term becomes hybrid, while the pure switched bridge current can be reconstructed outside.
    block.algebraic_eqs[i_dc_conv_eq_index] = i_dc_conv - i_dc_conv_eff_expr
    block.init_eqs[i_dc_conv] = i_dc_conv_eff_expr

    # The plant controller still needs the nominal voltage ceiling used to scale modulation commands.
    block.algebraic_eqs.append(k_v_conv_nom - k_v_conv_nom_expr)
    block.algebraic_vars.append(k_v_conv_nom)
    block.init_eqs[k_v_conv_nom] = k_v_conv_nom_expr

    # PWM timing remains a runtime parameter owned by the converter data block.
    block.event_dict[omega_sw] = Const(2.0 * np.pi * 1000.0)
    block.event_dict[carrier_phase] = Const(0.0)

    # The parent block connects dq measurements first, then the bridge currents and retained gates.
    block.in_vars = list([
        v_d,
        v_q,
        v_0,
        i_d,
        i_q,
        i_0,
        i_A,
        i_B,
        i_C,
        gate_a,
        gate_b,
        gate_c,
        v_dc_bus,
        switching_enabled,
    ])
    block.out_vars = list([
        v_dc,
        i_dc,
        P,
        Q,
        k_v_conv_nom,
        sbase,
        P_ref,
        Q_ref,
        Vdc_ref,
        omega_base,
        phi_v,
        Vpk,
        R_eq,
        L_eq,
        C_dc,
        R_dc,
        R_dc_term,
        pll_kp,
        pll_ki,
        i_kp,
        i_ki,
        vdc_kp,
        vdc_ki,
        q_kp,
        q_ki,
        i_max,
        m_max,
        P_loss0,
        P_loss_i1,
        P_loss_i2,
        tau_meas,
        aw_gain,
        vdc_floor,
        omega_sw,
        carrier_phase,
    ])
    block.name = f"{name}_switched_data"

    return block


def _find_child_block_by_name(root_block: Block, block_name: str) -> Block | None:
    """
    Return one nested child block by its symbolic name.

    :param root_block: Root block to inspect.
    :param block_name: Requested block name.
    :return: Matching child block or ``None``.
    """
    child_block: Block
    nested_block: Block | None

    for child_block in root_block.children:
        if child_block.name == block_name:
            return child_block
        else:
            pass

        nested_block = _find_child_block_by_name(root_block=child_block, block_name=block_name)
        if nested_block is not None:
            return nested_block
        else:
            pass

    return None


def _find_var_anywhere_in_block(block: Block, variable_name: str) -> Var | None:
    """
    Return one symbolic variable from a block, including runtime and constant parameter stores.

    The generic ``find_name_in_block()`` helper only scans state/algebraic/input/output variables.
    The switched converter data-block reuse also needs access to event, mode and parameter symbols
    owned by the pseudo-EMT DC-side block.

    :param block: Block to inspect.
    :param variable_name: Requested symbolic-variable name.
    :return: Matching variable or ``None``.
    """
    variable_groups: list[list[Var]] = list([
        block.in_vars,
        block.out_vars,
        block.algebraic_vars,
        block.state_vars,
        block.diff_vars,
        list(block.event_dict.keys()),
        list(block.mode_dict.keys()),
        list(block.parameters.keys()),
    ])
    variable_group: list[Var]
    variable: Var
    child_block: Block
    nested_result: Var | None

    # The switched template must access pseudo-EMT runtime and parameter symbols in addition to state variables.
    for variable_group in variable_groups:
        for variable in variable_group:
            if variable.name == variable_name:
                return variable
            else:
                pass

    for child_block in block.children:
        nested_result = _find_var_anywhere_in_block(block=child_block, variable_name=variable_name)
        if nested_result is not None:
            return nested_result
        else:
            pass

    return None


def _find_algebraic_equation_index_for_var(block: Block, target_var: Var) -> int:
    """
    Return the algebraic-equation index whose left operand is the requested variable.

    Some legacy symbolic blocks do not keep ``algebraic_vars`` and ``algebraic_eqs`` in a perfectly
    aligned semantic order. When one equation must be replaced surgically, the robust way is to scan
    the residual expressions and locate the equation that is actually written for the requested symbol.

    :param block: Block to inspect.
    :param target_var: Variable whose residual equation must be located.
    :return: Matching algebraic-equation index.
    """
    equation_index: int = 0
    equation: Expr

    while equation_index < len(block.algebraic_eqs):
        equation = block.algebraic_eqs[equation_index]

        if isinstance(equation, BinOp):
            if isinstance(equation.left, Var):
                if equation.left.uid == target_var.uid:
                    return equation_index
                else:
                    pass
            else:
                pass
        else:
            pass

        equation_index += 1

    raise KeyError(f"The block '{block.name}' could not locate an algebraic equation for '{target_var.name}'")


def get_soft_switched_emt_converter(vf: VarFactory, name: str = "switched_converter_emt") -> EmtModelTemplate:
    """
    Assemble a hybrid soft-sign switched EMT converter with the same external interface as the averaged converter.

    The switched converter is rebuilt incrementally around the validated
    ``bridge + filter + control`` plant. The startup remains averaged until the
    exact ``t_enable_sw`` handover time, and from that point on the bridge/filter
    plant is seen electrically by the rest of the converter.

    :param vf: Shared EMT variable factory.
    :param name: Symbolic model name.
    :return: Switched EMT converter template.
    """
    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.VscDevice
    templ.name = name
    templ.block.name = name

    v_A: Var = vf.add_var(name=f"v_A", reference=VarPowerFlowReferenceType.v_A)
    v_B: Var = vf.add_var(name=f"v_B", reference=VarPowerFlowReferenceType.v_B)
    v_C: Var = vf.add_var(name=f"v_C", reference=VarPowerFlowReferenceType.v_C)
    v_dc_bus: Var = vf.add_var(name=f"v_dc_bus", reference=VarPowerFlowReferenceType.Vdc)
    switching_enabled_mode: Var = vf.add_var(name=f"switching_enabled_mode")
    t_enable_sw: Var = vf.add_var(name=f"t_enable_sw")
    i_A: Var = vf.add_var(name=f"i_A", reference=VarPowerFlowReferenceType.i_A)
    i_B: Var = vf.add_var(name=f"i_B", reference=VarPowerFlowReferenceType.i_B)
    i_C: Var = vf.add_var(name=f"i_C", reference=VarPowerFlowReferenceType.i_C)
    gate_a: Var = vf.add_var(name=f"gate_a")
    gate_b: Var = vf.add_var(name=f"gate_b")
    gate_c: Var = vf.add_var(name=f"gate_c")
    v_conv_a: Var = vf.add_var(name=f"v_conv_a")
    v_conv_b: Var = vf.add_var(name=f"v_conv_b")
    v_conv_c: Var = vf.add_var(name=f"v_conv_c")
    v_conv_d: Var = vf.add_var(name=f"v_conv_d")
    v_conv_q: Var = vf.add_var(name=f"v_conv_q")
    v_conv_0: Var = vf.add_var(name=f"v_conv_0")
    omega_sw_eff: Var = vf.add_var(name=f"omega_sw_eff")

    data_block: Block = _build_switched_converter_data_block(vf=vf, name=name)
    outer_loop_block: Block = _build_pseudo_emt_converter_outer_loop_block(vf=vf, name=name)
    plant_block: Block = get_bridge_filter_control_2level_3ph_soft_emt_template(vf=vf, name=name).block
    filter_stage_block: Block = plant_block
    data_lookup: Dict[str, Var] = build_name_to_var_lookup(data_block)
    outer_loop_lookup: Dict[str, Var] = build_name_to_var_lookup(outer_loop_block)
    plant_lookup: Dict[str, Var] = build_name_to_var_lookup(plant_block)

    data_vdc: Var | None = data_lookup.get(f"v_dc", None)
    data_idc: Var | None = data_lookup.get(f"i_dc", None)
    data_p: Var | None = data_lookup.get(f"P", None)
    data_q: Var | None = data_lookup.get(f"Q", None)
    data_sbase: Var | None = data_lookup.get(f"sbase", None)
    data_p_ref: Var | None = data_lookup.get(f"P_ref", None)
    data_q_ref: Var | None = data_lookup.get(f"Q_ref", None)
    data_vdc_ref: Var | None = data_lookup.get(f"Vdc_ref", None)
    data_omega_base: Var | None = data_lookup.get(f"omega_base", None)
    data_phi_v: Var | None = data_lookup.get(f"phi_v", None)
    data_vpk: Var | None = data_lookup.get(f"Vpk", None)
    data_r_eq: Var | None = data_lookup.get(f"R_eq", None)
    data_l_eq: Var | None = data_lookup.get(f"L_eq", None)
    data_pll_kp: Var | None = data_lookup.get(f"pll_kp", None)
    data_pll_ki: Var | None = data_lookup.get(f"pll_ki", None)
    data_i_kp: Var | None = data_lookup.get(f"i_kp", None)
    data_i_ki: Var | None = data_lookup.get(f"i_ki", None)
    data_vdc_kp: Var | None = data_lookup.get(f"vdc_kp", None)
    data_vdc_ki: Var | None = data_lookup.get(f"vdc_ki", None)
    data_q_kp: Var | None = data_lookup.get(f"q_kp", None)
    data_q_ki: Var | None = data_lookup.get(f"q_ki", None)
    data_i_max: Var | None = data_lookup.get(f"i_max", None)
    data_m_max: Var | None = data_lookup.get(f"m_max", None)
    data_p_loss0: Var | None = data_lookup.get(f"P_loss0", None)
    data_tau_meas: Var | None = data_lookup.get(f"tau_meas", None)
    data_aw_gain: Var | None = data_lookup.get(f"aw_gain", None)
    data_vdc_floor: Var | None = data_lookup.get(f"vdc_floor", None)
    data_omega_sw: Var | None = data_lookup.get(f"omega_sw", None)
    data_carrier_phase: Var | None = data_lookup.get(f"carrier_phase", None)

    def plant_var(var_name: str) -> Var | None:
        """
        Return one plant variable by exact name or by soft-bridge suffix.

        :param var_name: Unsuffixed production plant variable name.
        :return: Matching variable or ``None``.
        """
        variable: Var | None = plant_lookup.get(var_name, None)
        candidate_name: str
        candidate_var: Var

        if variable is not None:
            return variable
        else:
            pass

        for candidate_name, candidate_var in plant_lookup.items():
            if candidate_name.startswith(f"{var_name}_"):
                return candidate_var
            else:
                pass

        return None

    plant_i_A: Var | None = plant_var("i_A")
    plant_i_B: Var | None = plant_var("i_B")
    plant_i_C: Var | None = plant_var("i_C")
    plant_i_d: Var | None = plant_var("i_d")
    plant_i_q: Var | None = plant_var("i_q")
    plant_i_0: Var | None = plant_var("i_0")
    plant_v_d: Var | None = plant_var("v_d")
    plant_v_q: Var | None = plant_var("v_q")
    plant_v_0: Var | None = plant_var("v_0")
    plant_gate_a: Var | None = plant_var("gate_a")
    plant_gate_b: Var | None = plant_var("gate_b")
    plant_gate_c: Var | None = plant_var("gate_c")
    plant_v_ref_a: Var | None = plant_var("v_ref_a")
    plant_v_ref_b: Var | None = plant_var("v_ref_b")
    plant_v_ref_c: Var | None = plant_var("v_ref_c")
    plant_v_conv_a: Var | None = plant_var("v_conv_a")
    plant_v_conv_b: Var | None = plant_var("v_conv_b")
    plant_v_conv_c: Var | None = plant_var("v_conv_c")
    plant_v_conv_d: Var | None = plant_var("v_conv_d")
    plant_v_conv_q: Var | None = plant_var("v_conv_q")
    plant_v_conv_0: Var | None = plant_var("v_conv_0")
    plant_v_d_meas_f: Var | None = plant_lookup.get(f"v_d_meas_f", None)
    plant_v_q_meas_f: Var | None = plant_lookup.get(f"v_q_meas_f", None)
    plant_i_d_meas_f: Var | None = plant_lookup.get(f"i_d_meas_f", None)
    plant_i_q_meas_f: Var | None = plant_lookup.get(f"i_q_meas_f", None)
    plant_i_0_meas_f: Var | None = plant_lookup.get(f"i_0_meas_f", None)
    plant_v_0_meas_f: Var | None = plant_lookup.get(f"v_0_meas_f", None)
    plant_v_cmd_d: Var | None = plant_lookup.get(f"v_cmd_d", None)
    plant_v_cmd_q: Var | None = plant_lookup.get(f"v_cmd_q", None)
    plant_v_cmd_0: Var | None = plant_lookup.get(f"v_cmd_0", None)
    outer_i_0_ref: Var | None = outer_loop_lookup.get(f"i_0_ref", None)
    outer_i_d_ref: Var | None = outer_loop_lookup.get(f"i_d_ref", None)
    outer_i_q_ref: Var | None = outer_loop_lookup.get(f"i_q_ref", None)
    if data_vdc is None or data_idc is None or data_p is None or data_q is None or data_sbase is None or data_p_ref is None or data_q_ref is None or data_vdc_ref is None or data_omega_base is None or data_phi_v is None or data_vpk is None or data_r_eq is None or data_l_eq is None or data_pll_kp is None or data_pll_ki is None or data_i_kp is None or data_i_ki is None or data_vdc_kp is None or data_vdc_ki is None or data_q_kp is None or data_q_ki is None or data_i_max is None or data_m_max is None or data_p_loss0 is None or data_tau_meas is None or data_aw_gain is None or data_vdc_floor is None or data_omega_sw is None or data_carrier_phase is None or plant_i_A is None or plant_i_B is None or plant_i_C is None or plant_i_d is None or plant_i_q is None or plant_i_0 is None or plant_v_d is None or plant_v_q is None or plant_v_0 is None or plant_gate_a is None or plant_gate_b is None or plant_gate_c is None or plant_v_ref_a is None or plant_v_ref_b is None or plant_v_ref_c is None or plant_v_conv_a is None or plant_v_conv_b is None or plant_v_conv_c is None or plant_v_conv_d is None or plant_v_conv_q is None or plant_v_conv_0 is None or plant_v_d_meas_f is None or plant_v_q_meas_f is None or plant_v_0_meas_f is None or plant_i_d_meas_f is None or plant_i_q_meas_f is None or plant_i_0_meas_f is None or plant_v_cmd_d is None or plant_v_cmd_q is None or plant_v_cmd_0 is None or outer_i_0_ref is None or outer_i_d_ref is None or outer_i_q_ref is None:
        raise KeyError(f"The switched EMT converter '{name}' could not resolve one or more internal variables")
    else:
        pass

    one: Const = Const(1.0)
    averaged_mode: Expr = one - switching_enabled_mode

    # The bridge keeps switching procedurally from t = 0, but the RL filter only sees the discrete
    # bridge pole voltages after the exact startup handover time.
    filter_stage_block.state_eqs = list([
        equation.subs({
            plant_v_conv_a: v_conv_a,
            plant_v_conv_b: v_conv_b,
            plant_v_conv_c: v_conv_c,
        })
        for equation in filter_stage_block.state_eqs
    ])

    templ.block.algebraic_eqs.extend(list([
        i_A - plant_i_A,
        i_B - plant_i_B,
        i_C - plant_i_C,
        gate_a - plant_gate_a,
        gate_b - plant_gate_b,
        gate_c - plant_gate_c,
        v_conv_a - (averaged_mode * plant_v_ref_a + switching_enabled_mode * plant_v_conv_a),
        v_conv_b - (averaged_mode * plant_v_ref_b + switching_enabled_mode * plant_v_conv_b),
        v_conv_c - (averaged_mode * plant_v_ref_c + switching_enabled_mode * plant_v_conv_c),
        v_conv_d - (averaged_mode * plant_v_cmd_d + switching_enabled_mode * plant_v_conv_d),
        v_conv_q - (averaged_mode * plant_v_cmd_q + switching_enabled_mode * plant_v_conv_q),
        v_conv_0 - (averaged_mode * plant_v_cmd_0 + switching_enabled_mode * plant_v_conv_0),
    ]))
    templ.block.algebraic_vars.extend(list([
        i_A,
        i_B,
        i_C,
        gate_a,
        gate_b,
        gate_c,
        v_conv_a,
        v_conv_b,
        v_conv_c,
        v_conv_d,
        v_conv_q,
        v_conv_0,
    ]))
    templ.block.init_eqs.update(dict([
        (i_A, plant_i_A),
        (i_B, plant_i_B),
        (i_C, plant_i_C),
        (gate_a, plant_gate_a),
        (gate_b, plant_gate_b),
        (gate_c, plant_gate_c),
        (v_conv_a, averaged_mode * plant_v_ref_a + switching_enabled_mode * plant_v_conv_a),
        (v_conv_b, averaged_mode * plant_v_ref_b + switching_enabled_mode * plant_v_conv_b),
        (v_conv_c, averaged_mode * plant_v_ref_c + switching_enabled_mode * plant_v_conv_c),
        (v_conv_d, averaged_mode * plant_v_cmd_d + switching_enabled_mode * plant_v_conv_d),
        (v_conv_q, averaged_mode * plant_v_cmd_q + switching_enabled_mode * plant_v_conv_q),
        (v_conv_0, averaged_mode * plant_v_cmd_0 + switching_enabled_mode * plant_v_conv_0),
    ]))
    templ.block.event_dict.update(dict([
        (t_enable_sw, Const(1.0e-4)),
        # Keeping the PWM carrier frequency at zero before the handover prevents the bridge procedural
        # logic from introducing discrete switching activity while the converter is still in averaged mode.
        (omega_sw_eff, switching_enabled_mode * data_omega_sw),
    ]))
    templ.block.mode_dict.update(dict([
        (switching_enabled_mode, Const(0.0)),
    ]))
    templ.block.procedural_logic.append(
        startup_handover(
            mode=switching_enabled_mode,
            t_enable=t_enable_sw,
            name=f"startup_handover",
        )
    )

    # The data block should compute instantaneous power from the raw plant dq0 quantities. Filtering
    # ``v_dq0`` and ``i_dq0`` before forming ``P`` and ``Q`` introduces an avoidable phase bias, while
    # the outer-loop ``P_f`` / ``Q_f`` states already provide the intended low-frequency power filtering.
    data_block.connect(data_block.in_vars[0:14], list([
        plant_v_d,
        plant_v_q,
        plant_v_0,
        plant_i_d,
        plant_i_q,
        plant_i_0,
        plant_i_A,
        plant_i_B,
        plant_i_C,
        plant_gate_a,
        plant_gate_b,
        plant_gate_c,
        v_dc_bus,
        switching_enabled_mode,
    ]))

    # The outer loop must see the same filtered plant measurements as the PLL and current loop so the
    # switched converter keeps one coherent low-frequency control view across all control layers.
    outer_loop_block.connect(outer_loop_block.in_vars[0:22], list([
        plant_v_d_meas_f,
        plant_v_q_meas_f,
        plant_v_0_meas_f,
        plant_i_d_meas_f,
        plant_i_q_meas_f,
        plant_i_0_meas_f,
        data_vdc,
        data_p,
        data_q,
        data_sbase,
        data_p_ref,
        data_q_ref,
        data_vdc_ref,
        data_vpk,
        data_p_loss0,
        data_vdc_kp,
        data_vdc_ki,
        data_q_kp,
        data_q_ki,
        data_i_max,
        data_tau_meas,
        data_aw_gain,
    ]))

    # The bridge + filter + control plant closes its own PLL. The parent provides the electrical
    # references, the effective bridge PWM frequency, and the real carrier frequency used to shape
    # the measurement filters seen by the control hierarchy during and after the handover.
    plant_block.connect(plant_block.in_vars, list([
        data_omega_base,
        v_A,
        v_B,
        v_C,
        data_vdc,
        outer_i_d_ref,
        outer_i_q_ref,
        outer_i_0_ref,
        data_m_max,
        data_vdc_floor,
        omega_sw_eff,
        data_omega_sw,
        data_carrier_phase,
        switching_enabled_mode,
        data_r_eq,
        data_l_eq,
        data_pll_kp,
        data_pll_ki,
        data_i_kp,
        data_i_ki,
        data_aw_gain,
        data_phi_v,
        data_vdc_ref,
        data_sbase,
        data_p_ref,
        data_q_ref,
        data_p_loss0,
        data_vpk,
    ]))

    # Keep the connected child hierarchy intact. The current EMT initializer walks
    # those blocks to apply the power-flow seeds and block-local initialization
    # equations; flattening here left the soft converter at the zero fallback.
    templ.block.children.extend(list([data_block, outer_loop_block, plant_block]))
    templ.block.in_vars = list([v_A, v_B, v_C, v_dc_bus])
    templ.block.out_vars = list([
        i_A,
        i_B,
        i_C,
        data_idc,
        gate_a,
        gate_b,
        gate_c,
        v_conv_a,
        v_conv_b,
        v_conv_c,
        v_conv_d,
        v_conv_q,
        v_conv_0,
    ])

    templ.block.external_mapping = dict([
        (VarPowerFlowReferenceType.v_A, v_A),
        (VarPowerFlowReferenceType.v_B, v_B),
        (VarPowerFlowReferenceType.v_C, v_C),
        (VarPowerFlowReferenceType.vt_A, v_A),
        (VarPowerFlowReferenceType.vt_B, v_B),
        (VarPowerFlowReferenceType.vt_C, v_C),
        (VarPowerFlowReferenceType.Vdc, v_dc_bus),
        (VarPowerFlowReferenceType.Vf_dc, v_dc_bus),
        (VarPowerFlowReferenceType.i_A, i_A),
        (VarPowerFlowReferenceType.i_B, i_B),
        (VarPowerFlowReferenceType.i_C, i_C),
        (VarPowerFlowReferenceType.it_A, i_A),
        (VarPowerFlowReferenceType.it_B, i_B),
        (VarPowerFlowReferenceType.it_C, i_C),
        (VarPowerFlowReferenceType.Idc, data_idc),
        (VarPowerFlowReferenceType.If_dc, data_idc),
        (VarPowerFlowReferenceType.P, data_p),
        (VarPowerFlowReferenceType.Q, data_q),
        (VarPowerFlowReferenceType.phi_v, data_phi_v),
        (VarPowerFlowReferenceType.Vpk, data_vpk),
    ])

    return templ
