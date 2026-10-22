# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from typing import List, Dict, Tuple
from VeraGridEngine.enumerations import DeviceType, ConverterControlType, ParamPowerFlowReferenceType
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import (
    Block,
    VarPowerFlowReferenceType,
)
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
import VeraGridEngine.Utils.Symbolic.symbolic as sym

"""
Standard converter template for EMT simulation.

This is an ideal converter model that connects a DC bus with an AC bus,
maintaining power balance: P_ac = P_dc

The converter takes:
- DC side: V_dc (bus DC voltage) as input
- AC side: v_A, v_B, v_C (bus AC instantaneous voltages) as inputs

And provides:
- DC side: I_dc (current flowing into the DC bus)
- AC side: i_A, i_B, i_C (instantaneous three-phase currents)

External mapping for EmtProblemDae:
- v_A, v_B, v_C: AC bus voltages
- Vdc: DC bus voltage
- it_A, it_B, it_C: AC currents at the physical to terminal
- If_dc: DC current at the physical from terminal

For KCL connection:
- static VSC topology supplies the from/to buses
- mapped current references supply terminal and conductor semantics
"""

def _converter_control_type_code(control: ConverterControlType | None) -> int:
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


def _converter_control_match_expr(control_var: Var, control_type: ConverterControlType | None) -> sym.Expr:
    return (control_var == _converter_control_type_code(control_type)).to_expression()


def _resolve_converter_control_reference_exprs(
    control1: Var,
    control2: Var,
    control1_val: Var,
    control2_val: Var,
    p0: Var,
    vdc_nom: Var,
    sbase: Var,
) -> Tuple[sym.Expr, sym.Expr, sym.Expr, sym.Expr, sym.Expr, sym.Expr]:
    control1_is_vm_dc = _converter_control_match_expr(control1, ConverterControlType.Vm_dc)
    control2_is_vm_dc = _converter_control_match_expr(control2, ConverterControlType.Vm_dc)
    control1_is_qac = _converter_control_match_expr(control1, ConverterControlType.Qac)
    control2_is_qac = _converter_control_match_expr(control2, ConverterControlType.Qac)
    control1_is_pac = _converter_control_match_expr(control1, ConverterControlType.Pac)
    control2_is_pac = _converter_control_match_expr(control2, ConverterControlType.Pac)
    control1_is_pdc = _converter_control_match_expr(control1, ConverterControlType.Pdc)
    control2_is_pdc = _converter_control_match_expr(control2, ConverterControlType.Pdc)

    regulate_vdc = sym.max(control1_is_vm_dc, control2_is_vm_dc)
    regulate_q = sym.max(control1_is_qac, control2_is_qac)
    regulate_active = sym.max(control1_is_pac + control1_is_pdc, control2_is_pac + control2_is_pdc)
    vdc_ref = (
        control1_is_vm_dc * control1_val
        + (Const(1.0) - control1_is_vm_dc)
        * (control2_is_vm_dc * control2_val + (Const(1.0) - control2_is_vm_dc) * vdc_nom)
    )
    # Converter API power targets are per unit, whereas P_ref/Q_ref use the
    # system-base power units expected by the PF-to-EMT initialization path.
    # Convert at this boundary exactly once; voltage targets remain per unit.
    q_ref_pu = (
        control1_is_qac * control1_val
        + (Const(1.0) - control1_is_qac)
        * (control2_is_qac * control2_val + (Const(1.0) - control2_is_qac) * Const(0.0))
    )
    q_ref = q_ref_pu * sbase
    # ------------------------------------------------------------------
    # Preserve the power-flow operating point when neither controller is an
    # explicit active-power mode. This is required by the EMT scripting cases
    # that regulate DC voltage and reactive power around a non-zero scheduled
    # active transfer obtained from the solved power-flow state.
    # ------------------------------------------------------------------
    p_control_ref_pu = (
        (control1_is_pac + control1_is_pdc) * control1_val
        + (Const(1.0) - (control1_is_pac + control1_is_pdc))
        * ((control2_is_pac + control2_is_pdc) * control2_val)
    )
    has_active_control = sym.max(
        control1_is_pac + control1_is_pdc,
        control2_is_pac + control2_is_pdc,
    )
    p_ref = has_active_control * p_control_ref_pu * sbase + (Const(1.0) - has_active_control) * p0

    return p_ref, q_ref, vdc_ref, regulate_vdc, regulate_q, regulate_active


def get_emt_ideal_converter(
    vf: VarFactory,
    name: str = "ideal_converter_emt",
) -> EmtModelTemplate:
    """
    Build an idealized averaged EMT converter model current injection type with DC power balance.

    It does not represent:
    switching,
    PLL,
    inner current loop,
    L filter,
    DC capacitor,
    Current or voltage dependent losses
    Transformer
    Snubbers or filters

    AC voltages use the phase voltage base Vbase_LL/sqrt(3), and currents
    use Sbase/(sqrt(3)*Vbase_LL). Consequently, instantaneous three-phase
    power is sum(v_phase*i_phase)/3 on the total system power base.

    The AC-side current reference is synthesized from fundamental-frequency P/Q
    commands in a synchronized rotating frame. This is a better physical approximation of a grid-following
    converter than an instantaneous constant-power current source.

    ``P_ref``, ``Q_ref`` and ``P_loss`` are interpreted in system-base units
    (MW / MVAr on ``sbase``), because that is the convention used by the EMT
    initialization layer when it maps power-flow values into external references.

   :param vf: Variable factory for creating symbolic variables
   :param name: Name for the converter model
    :return: EmtModelTemplate with the converter block
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.VscDevice
    templ.name = name
    templ.block.name = name

    # =================================================================
    # INPUT VARIABLES (from buses)
    # =================================================================
    # AC side voltages from the AC bus
    v_A = vf.add_var(name=f"v_A", reference=VarPowerFlowReferenceType.v_A)
    v_B = vf.add_var(name=f"v_B", reference=VarPowerFlowReferenceType.v_B)
    v_C = vf.add_var(name=f"v_C", reference=VarPowerFlowReferenceType.v_C)

    # DC side voltage from the DC bus
    v_dc = vf.add_var(name=f"v_dc", reference=VarPowerFlowReferenceType.Vdc)

    inputs = [v_A, v_B, v_C, v_dc]

    # =================================================================
    # OUTPUT VARIABLES (to buses)
    # =================================================================
    i_A = vf.add_var(name=f"i_A", reference=VarPowerFlowReferenceType.i_A)
    i_B = vf.add_var(name=f"i_B", reference=VarPowerFlowReferenceType.i_B)
    i_C = vf.add_var(name=f"i_C", reference=VarPowerFlowReferenceType.i_C)
    theta = vf.add_var(name=f"theta")

    d_theta = vf.add_diff_var(name=f"d_theta", base_var=theta)

    i_dc = vf.add_var(name=f"i_dc", reference=VarPowerFlowReferenceType.Idc)
    P = vf.add_var(name=f"P", reference=VarPowerFlowReferenceType.P)
    Q = vf.add_var(name=f"Q", reference=VarPowerFlowReferenceType.Q)

    # =================================================================
    # INTERNAL VARIABLES
    # =================================================================
    P_ref = vf.add_var(name=f"P_ref")
    Q_ref = vf.add_var(name=f"Q_ref")
    Vdc_ref = vf.add_var(name=f"Vdc_ref")
    P_loss = vf.add_var(name=f"P_loss")
    P0 = vf.add_var(name=f"P0")
    omega_base = vf.add_var(name=f"omega_base")
    sbase = vf.add_var(name=f"sbase")
    control1 = vf.add_var(name=f"control1")
    control2 = vf.add_var(name=f"control2")
    control1_val = vf.add_var(name=f"control1_val")
    control2_val = vf.add_var(name=f"control2_val")
    phi_v = vf.add_var(name=f"phi_v")
    Vpk = vf.add_var(name=f"Vpk")
    Vdc_nom = vf.add_var(name=f"Vdc_nom")

    # =================================================================
    # PARAMETERS
    # =================================================================

    p_ref_expr, q_ref_expr, vdc_ref_expr, regulate_vdc, regulate_q, _ = _resolve_converter_control_reference_exprs(
        control1=control1,
        control2=control2,
        control1_val=control1_val,
        control2_val=control2_val,
        p0=P0,
        vdc_nom=Vdc_nom,
        sbase=sbase,
    )

    eps = vf.add_const(1e-10)
    c_two = vf.add_const(2.0)
    c_third = vf.add_const(1.0 / 3.0)
    c_sqrt3_over_two = vf.add_const(np.sqrt(3.0) / 2.0)
    c_half = vf.add_const(0.5)
    sbase_eff = sym.max(sbase, eps)
    event_dict = {
        P_loss: vf.add_const(0.0),
        P0: vf.add_const(0.0),
        control1: vf.add_const(float(_converter_control_type_code(None))),
        control2: vf.add_const(float(_converter_control_type_code(None))),
        control1_val: vf.add_const(0.0),
        control2_val: vf.add_const(0.0),
        phi_v: vf.add_const(0.0),
        Vpk: vf.add_const(np.sqrt(2.0)),
        Vdc_nom: vf.add_const(1.0),
    }

    # =================================================================
    # CURRENT REFERENCE EQUATIONS
    # =================================================================
    P_dc_cmd = P_ref + vf.add_const(2.0) * (v_dc - Vdc_ref) * regulate_vdc
    Q_cmd = Q_ref * regulate_q
    P_dc_cmd_pu = P_dc_cmd / sbase_eff
    Q_cmd_pu = Q_cmd / sbase_eff
    P_ac_cmd_pu = P_dc_cmd_pu + P_loss / sbase_eff

    i_d_cmd = -c_two * Q_cmd_pu / sym.max(Vpk, eps)
    i_q_cmd = c_two * P_ac_cmd_pu / sym.max(Vpk, eps)

    i_A_cmd = i_d_cmd * sym.cos(theta) + i_q_cmd * sym.sin(theta)
    i_B_cmd = ((-c_half * i_d_cmd - c_sqrt3_over_two * i_q_cmd) * sym.cos(theta)
               + ((c_sqrt3_over_two * i_d_cmd) - c_half * i_q_cmd) * sym.sin(theta))
    i_C_cmd = ((-c_half * i_d_cmd + c_sqrt3_over_two * i_q_cmd) * sym.cos(theta)
               + ((-c_sqrt3_over_two * i_d_cmd) - c_half * i_q_cmd) * sym.sin(theta))

    Q_init_pu = Q_ref * regulate_q / sbase_eff
    P_dc_init_pu = P_ref / sbase_eff
    P_ac_init_pu = P_dc_init_pu + P_loss / sbase_eff
    # With v = Vpk*sin(theta), positive absorbed Q requires -cos(theta) current.
    i_d_init = -c_two * Q_init_pu / sym.max(Vpk, eps)
    i_q_init = c_two * P_ac_init_pu / sym.max(Vpk, eps)
    i_A_init = i_d_init * sym.cos(phi_v) + i_q_init * sym.sin(phi_v)
    i_B_init = ((-c_half * i_d_init - c_sqrt3_over_two * i_q_init) * sym.cos(phi_v)
                + ((c_sqrt3_over_two * i_d_init) - c_half * i_q_init) * sym.sin(phi_v))
    i_C_init = ((-c_half * i_d_init + c_sqrt3_over_two * i_q_init) * sym.cos(phi_v)
                + ((-c_sqrt3_over_two * i_d_init) - c_half * i_q_init) * sym.sin(phi_v))

    state_eqs = [omega_base]

    algebraic_eqs = [
        P_ref - p_ref_expr,
        Q_ref - q_ref_expr,
        Vdc_ref - vdc_ref_expr,
        i_A - i_A_cmd,
        i_B - i_B_cmd,
        i_C - i_C_cmd,
        v_dc * i_dc + P_dc_cmd_pu,
        P - c_third * (v_A * i_A + v_B * i_B + v_C * i_C),
        Q - c_third * (1 / np.sqrt(3.0)) * ((v_A - v_B) * i_C + (v_B - v_C) * i_A + (v_C - v_A) * i_B),
    ]

    # =================================================================
    # ALGEBRAIC VARIABLES
    # =================================================================
    algebraic_vars = [P_ref, Q_ref, Vdc_ref, i_A, i_B, i_C, i_dc, P, Q]

    # =================================================================
    # INITIALIZATION EQUATIONS
    # =================================================================
    init_eqs = {
        P_ref: p_ref_expr,
        Q_ref: q_ref_expr,
        Vdc_ref: vdc_ref_expr,
        i_A: i_A_init,
        i_B: i_B_init,
        i_C: i_C_init,
        i_dc: -P_dc_init_pu / sym.max(Vdc_ref, eps),
        P: P_ac_init_pu,
        Q: Q_init_pu,
        theta: phi_v,
    }

    # =================================================================
    # BUILD THE BLOCK
    # =================================================================
    converter_block = Block(
        state_eqs=state_eqs,
        state_vars=[theta],
        diff_vars=[d_theta],
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=algebraic_vars,
        event_dict=event_dict,
        parameters={
            omega_base: vf.add_const(2.0 * np.pi * 50.0),
            sbase: vf.add_const(1.0),
        },
        init_eqs=init_eqs,
        diff_init_eqs={d_theta: omega_base},
        in_vars=inputs,
        out_vars=[i_A, i_B, i_C, i_dc],
    )
    converter_block.api_obj_mapping = {
        ParamPowerFlowReferenceType.Sbase: sbase,
        # Voltage control starts from the active transfer solved by power flow.
        ParamPowerFlowReferenceType.P0: P0,
        ParamPowerFlowReferenceType.omega_base: omega_base,
        ParamPowerFlowReferenceType.converter_control_mode_1: control1,
        ParamPowerFlowReferenceType.converter_control_mode_2: control2,
        ParamPowerFlowReferenceType.converter_control_target_1: control1_val,
        ParamPowerFlowReferenceType.converter_control_target_2: control2_val,
    }

    # =================================================================
    # EXTERNAL MAPPING
    # =================================================================
    # This mapping tells EmtProblemDae how to connect the converter
    # to the buses based on the device configuration
    converter_block.external_mapping = {
        VarPowerFlowReferenceType.v_A: v_A,
        VarPowerFlowReferenceType.v_B: v_B,
        VarPowerFlowReferenceType.v_C: v_C,
        VarPowerFlowReferenceType.vt_A: v_A,
        VarPowerFlowReferenceType.vt_B: v_B,
        VarPowerFlowReferenceType.vt_C: v_C,

        VarPowerFlowReferenceType.Vdc: v_dc,
        VarPowerFlowReferenceType.Vf_dc: v_dc,

        VarPowerFlowReferenceType.it_A: i_A,
        VarPowerFlowReferenceType.it_B: i_B,
        VarPowerFlowReferenceType.it_C: i_C,

        # For KCL at DC bus (bus_from)
        VarPowerFlowReferenceType.If_dc: i_dc,
        VarPowerFlowReferenceType.P: P,
        VarPowerFlowReferenceType.Q: Q,
        VarPowerFlowReferenceType.phi_v: phi_v,
        VarPowerFlowReferenceType.Vpk: Vpk,
    }

    converter_block.name = name
    templ.block.children.append(converter_block)
    templ.block.external_mapping = converter_block.external_mapping
    templ.block.in_vars = inputs
    templ.block.out_vars = converter_block.out_vars
    return templ


############################################################################


def _build_pseudo_emt_converter_vsc_block(
    vf: VarFactory,
    name: str,
) -> Block:
    """VSC electrical/DC block with converter parameters and power/loss equations."""
    v_d = vf.add_var(name=f"v_d_in", shared_reference="v_d_reference")
    v_q = vf.add_var(name=f"v_q_in", shared_reference="v_q_reference")
    v_0 = vf.add_var(name=f"v_0_in", shared_reference="v_0_reference")
    i_d = vf.add_var(name=f"i_d_in", shared_reference="i_d_reference")
    i_q = vf.add_var(name=f"i_q_in", shared_reference="i_q_reference")
    i_0 = vf.add_var(name=f"i_0_in", shared_reference="i_0_reference")
    v_dc_bus = vf.add_var(name=f"v_dc_bus_in", reference=VarPowerFlowReferenceType.Vdc, shared_reference="v_dc_bus_reference")

    v_dc = vf.add_var(name=f"v_dc", shared_reference="v_dc_reference")
    d_v_dc = vf.add_diff_var(name=f"d_v_dc", base_var=v_dc)

    i_dc = vf.add_var(name=f"i_dc", reference=VarPowerFlowReferenceType.Idc, shared_reference="i_dc_reference")
    P = vf.add_var(name=f"P", reference=VarPowerFlowReferenceType.P, shared_reference="P_reference")
    Q = vf.add_var(name=f"Q", reference=VarPowerFlowReferenceType.Q, shared_reference="Q_reference")
    i_mag = vf.add_var(name=f"i_mag")
    P_loss = vf.add_var(name=f"P_loss")
    i_dc_conv = vf.add_var(name=f"i_dc_conv", shared_reference="i_dc_conv_reference")

    sbase = vf.add_var(name=f"sbase", shared_reference="sbase_reference")
    P_ref = vf.add_var(name=f"P_ref", shared_reference="P_ref_reference")
    Q_ref = vf.add_var(name=f"Q_ref", shared_reference="Q_ref_reference")
    Vdc_ref = vf.add_var(name=f"Vdc_ref", shared_reference="Vdc_ref_reference")
    P0_sched = vf.add_var(name=f"P0")
    control1 = vf.add_var(name=f"control1")
    control2 = vf.add_var(name=f"control2")
    control1_val = vf.add_var(name=f"control1_val")
    control2_val = vf.add_var(name=f"control2_val")
    omega_base = vf.add_var(name=f"omega_base", shared_reference="omega_base_reference")
    phi_v = vf.add_var(name=f"phi_v", shared_reference="phi_v_reference")
    Vpk = vf.add_var(name=f"Vpk", shared_reference="Vpk_reference")
    R_eq = vf.add_var(name=f"R_eq", shared_reference="R_eq_reference")
    L_eq = vf.add_var(name=f"L_eq", shared_reference="L_eq_reference")
    C_dc = vf.add_var(name=f"C_dc", shared_reference="C_dc_reference")
    R_dc = vf.add_var(name=f"R_dc", shared_reference="R_dc_reference")
    R_dc_term = vf.add_var(name=f"R_dc_term", shared_reference="R_dc_term_reference")
    pll_kp = vf.add_var(name=f"pll_kp", shared_reference="pll_kp_reference")
    pll_ki = vf.add_var(name=f"pll_ki", shared_reference="pll_ki_reference")
    i_kp = vf.add_var(name=f"i_kp", shared_reference="i_kp_reference")
    i_ki = vf.add_var(name=f"i_ki", shared_reference="i_ki_reference")
    vdc_kp = vf.add_var(name=f"vdc_kp", shared_reference="vdc_kp_reference")
    vdc_ki = vf.add_var(name=f"vdc_ki", shared_reference="vdc_ki_reference")
    q_kp = vf.add_var(name=f"q_kp", shared_reference="q_kp_reference")
    q_ki = vf.add_var(name=f"q_ki", shared_reference="q_ki_reference")
    i_max = vf.add_var(name=f"i_max", shared_reference="i_max_reference")
    m_max = vf.add_var(name=f"m_max", shared_reference="m_max_reference")
    P_loss0 = vf.add_var(name=f"P_loss0", shared_reference="P_loss0_reference")
    P_loss_i1 = vf.add_var(name=f"P_loss_i1", shared_reference="P_loss_i1_reference")
    P_loss_i2 = vf.add_var(name=f"P_loss_i2", shared_reference="P_loss_i2_reference")
    tau_meas = vf.add_var(name=f"tau_meas", shared_reference="tau_meas_reference")
    aw_gain = vf.add_var(name=f"aw_gain", shared_reference="aw_gain_reference")
    vdc_floor = vf.add_var(name=f"vdc_floor", shared_reference="vdc_floor_reference")
    Vdc_nom = vf.add_var(name=f"Vdc_nom", shared_reference="Vdc_nom_reference")
    regulate_vdc_mode = vf.add_var(name=f"regulate_vdc_mode", shared_reference="regulate_vdc_reference")
    regulate_q_mode = vf.add_var(name=f"regulate_q_mode", shared_reference="regulate_q_reference")
    regulate_active_mode = vf.add_var(name=f"regulate_active_mode", shared_reference="regulate_active_reference")

    p_ref_expr, q_ref_expr, vdc_ref_expr, regulate_vdc, regulate_q, regulate_active = _resolve_converter_control_reference_exprs(
        control1=control1,
        control2=control2,
        control1_val=control1_val,
        control2_val=control2_val,
        p0=P0_sched,
        vdc_nom=Vdc_nom,
        sbase=sbase,
    )

    eps = vf.add_const(1e-10)
    c0 = vf.add_const(0.0)
    c1 = vf.add_const(1.0)
    c3 = vf.add_const(3.0)
    c_half_power = vf.add_const(0.5)
    c2 = vf.add_const(2.0)
    loss_current_scale = vf.add_const(3.0 / np.sqrt(2.0))

    sbase_eff = sym.max(sbase, eps)
    R_dc_eff = sym.max(R_dc, eps)
    R_dc_term_eff = sym.max(R_dc_term, eps)
    C_dc_eff = sym.max(C_dc, eps)
    # VSC alpha1/alpha2/alpha3 are stored on the system per-unit base already.
    P_loss0_pu = P_loss0
    P_loss_i1_pu = P_loss_i1
    P_loss_i2_pu = P_loss_i2
    i_leak = v_dc / R_dc_eff
    v_dc_eff = sym.max(v_dc, vdc_floor)

    i_q0 = (c2 * (Q_ref / sbase_eff)) / (Vpk + eps)
    # Fixed explicit predictor passes keep initialization acyclic while making
    # the nonlinear current-dependent loss and the seeded d-axis current
    # mutually consistent at the PF operating point.
    i_d0_seed = (c2 * ((P_ref / sbase_eff) + P_loss0_pu)) / (Vpk + eps)
    i_mag0_seed = sym.sqrt(i_d0_seed * i_d0_seed + i_q0 * i_q0 + eps)
    loss_current0_seed = loss_current_scale * i_mag0_seed
    P_loss0_seed = (P_loss0_pu + P_loss_i1_pu * loss_current0_seed
                    + P_loss_i2_pu * loss_current0_seed * loss_current0_seed)
    i_d0_predict1 = (c2 * ((P_ref / sbase_eff) + P_loss0_seed)) / (Vpk + eps)
    i_mag0_predict1 = sym.sqrt(i_d0_predict1 * i_d0_predict1 + i_q0 * i_q0 + eps)
    loss_current0_predict1 = loss_current_scale * i_mag0_predict1
    P_loss0_predict1 = (P_loss0_pu + P_loss_i1_pu * loss_current0_predict1
                        + P_loss_i2_pu * loss_current0_predict1 * loss_current0_predict1)
    i_d0_predict2 = (c2 * ((P_ref / sbase_eff) + P_loss0_predict1)) / (Vpk + eps)
    i_mag0_predict2 = sym.sqrt(i_d0_predict2 * i_d0_predict2 + i_q0 * i_q0 + eps)
    loss_current0_predict2 = loss_current_scale * i_mag0_predict2
    P_loss0_predict2 = (P_loss0_pu + P_loss_i1_pu * loss_current0_predict2
                        + P_loss_i2_pu * loss_current0_predict2 * loss_current0_predict2)
    i_d0 = (c2 * ((P_ref / sbase_eff) + P_loss0_predict2)) / (Vpk + eps)
    i_mag0 = sym.sqrt(i_d0 * i_d0 + i_q0 * i_q0 + eps)
    P0 = c_half_power * Vpk * i_d0
    Q0 = c_half_power * Vpk * i_q0
    loss_current0 = loss_current_scale * i_mag0
    P_loss0_expr = P_loss0_pu + P_loss_i1_pu * loss_current0 + P_loss_i2_pu * loss_current0 * loss_current0
    # Positive AC power includes the power dissipated in the converter. Only
    # the remainder is exchanged with the DC terminal.
    i_dc_conv0 = -(P0 - P_loss0_expr) / (Vdc_ref + eps)
    i_dc0 = (i_dc_conv0 + v_dc_bus / R_dc_eff) / (c1 + R_dc_term_eff / R_dc_eff)
    v_dc0 = v_dc_bus - R_dc_term * i_dc0

    block = Block(
        # DC-side physical model and converter power/loss balance.
        state_eqs=[
            # DC-link capacitor dynamics.
            (i_dc - i_dc_conv - i_leak) / C_dc_eff,
        ],
        state_vars=[v_dc],
        diff_vars=[d_v_dc],
        algebraic_eqs=[
            P_ref - p_ref_expr,
            Q_ref - q_ref_expr,
            Vdc_ref - vdc_ref_expr,
            # Instantaneous active power in dq0 coordinates.
            P - (c_half_power * (v_d * i_d + v_q * i_q) + v_0 * i_0),
            # Instantaneous reactive power in dq coordinates.
            Q - c_half_power * (v_d * i_q - v_q * i_d),
            # Converter current magnitude used by the loss model.
            i_mag - sym.sqrt(i_d * i_d + i_q * i_q + c3 * i_0 * i_0 + eps),
            # Current-dependent converter loss model.
            P_loss - (P_loss0_pu
                      + P_loss_i1_pu * loss_current_scale * i_mag
                      + P_loss_i2_pu * loss_current_scale * loss_current_scale * i_mag * i_mag),
            # AC-to-DC bridge current implied by power transfer and losses.
            i_dc_conv + (P - P_loss) / v_dc_eff,
            # Resistive coupling between the DC bus and the internal capacitor node.
            # Write the terminal resistor constraint in voltage form.  This is
            # physically identical to i=(v_bus-v_dc)/R, but avoids a 1/R
            # Jacobian coefficient (1e10 for an almost ideal DC connection)
            # that amplifies roundoff into visible AC-power ripple.
            (v_dc_bus - v_dc) - R_dc_term_eff * i_dc,
            # Expose mode-selection flags so outer loops can gate themselves.
            regulate_vdc_mode - regulate_vdc,
            regulate_q_mode - regulate_q,
            regulate_active_mode - regulate_active,
        ],
        algebraic_vars=[P_ref, Q_ref, Vdc_ref, i_dc, P, Q, i_mag, P_loss, i_dc_conv, regulate_vdc_mode, regulate_q_mode, regulate_active_mode],
        event_dict={
            control1: vf.add_const(float(_converter_control_type_code(ConverterControlType.Vm_dc))),
            control2: vf.add_const(float(_converter_control_type_code(ConverterControlType.Qac))),
            control1_val: vf.add_const(1.0),
            control2_val: vf.add_const(0.0),
            P0_sched: vf.add_const(0.0),
            phi_v: vf.add_const(0.0),
            Vpk: vf.add_const(np.sqrt(2.0)),
            Vdc_nom: vf.add_const(1.0),
            R_eq: vf.add_const(max(0.05, 1e-9)),
            L_eq: vf.add_const(max(0.20, 1e-9)),
            C_dc: vf.add_const(max(0.20, 1e-9)),
            R_dc: vf.add_const(max(1e12, 1e-9)),
            R_dc_term: vf.add_const(max(1e-10, 1e-12)),
            pll_kp: vf.add_const(10.0),
            pll_ki: vf.add_const(100.0),
            i_kp: vf.add_const(0.3),
            i_ki: vf.add_const(20.0),
            vdc_kp: vf.add_const(0.01),
            vdc_ki: vf.add_const(0.10),
            q_kp: vf.add_const(0.02),
            q_ki: vf.add_const(0.5),
            i_max: vf.add_const(max(1.2, 1e-6)),
            m_max: vf.add_const(max(0.95, 1e-6)),
            tau_meas: vf.add_const(max(0.02, 1e-6)),
            aw_gain: vf.add_const(0.2),
            vdc_floor: vf.add_const(max(0.05, 1e-6)),
        },
        parameters={
            omega_base: vf.add_const(2.0 * np.pi * 50.0),
            sbase: vf.add_const(1.0),
            P_loss0: vf.add_const(0.0),
            P_loss_i1: vf.add_const(0.0),
            P_loss_i2: vf.add_const(0.0),
        },
        init_eqs={
            v_dc: v_dc0,
            P_ref: p_ref_expr,
            Q_ref: q_ref_expr,
            Vdc_ref: vdc_ref_expr,
            i_dc: i_dc0,
            P: P0,
            Q: Q0,
            i_mag: i_mag0,
            P_loss: P_loss0_expr,
            i_dc_conv: i_dc_conv0,
            regulate_vdc_mode: regulate_vdc,
            regulate_q_mode: regulate_q,
            regulate_active_mode: regulate_active,
        },
        diff_init_eqs={d_v_dc: c0},
        in_vars=[v_d, v_q, v_0, i_d, i_q, i_0, v_dc_bus],
        out_vars=[
            v_dc, i_dc, P, Q,
            sbase, P_ref, Q_ref, Vdc_ref, omega_base, phi_v, Vpk,
            R_eq, L_eq, C_dc, R_dc, R_dc_term,
        pll_kp, pll_ki, i_kp, i_ki,
            vdc_kp, vdc_ki, q_kp, q_ki,
        # Feed the complete operating-point loss to the controller hierarchy;
        # using only alpha1 leaves its integrators inconsistent when alpha2 or
        # alpha3 is non-zero.
        i_max, m_max, P_loss, P_loss_i1, P_loss_i2, tau_meas, aw_gain, vdc_floor, Vdc_nom,
            i_dc_conv,
            regulate_vdc_mode, regulate_q_mode, regulate_active_mode,
        ],
        name=f"{name}_vsc",
    )
    block.api_obj_mapping = {
        ParamPowerFlowReferenceType.Sbase: sbase,
        ParamPowerFlowReferenceType.P0: P0_sched,
        ParamPowerFlowReferenceType.alpha1: P_loss0,
        ParamPowerFlowReferenceType.alpha2: P_loss_i1,
        ParamPowerFlowReferenceType.alpha3: P_loss_i2,
        ParamPowerFlowReferenceType.omega_base: omega_base,
        ParamPowerFlowReferenceType.converter_control_mode_1: control1,
        ParamPowerFlowReferenceType.converter_control_mode_2: control2,
        ParamPowerFlowReferenceType.converter_control_target_1: control1_val,
        ParamPowerFlowReferenceType.converter_control_target_2: control2_val,
    }
    return block
def _build_pseudo_emt_converter_pll_block(vf: VarFactory, name: str) -> Block:
    """SRF-PLL aligned with the q-axis voltage error convention used by the converter."""
    v_q = vf.add_var(name=f"v_q_pll_in", shared_reference="v_q_pll_reference")
    omega_base = vf.add_var(name=f"omega_base_pll_in", shared_reference="omega_base_reference")
    pll_kp = vf.add_var(name=f"pll_kp_in", shared_reference="pll_kp_reference")
    pll_ki = vf.add_var(name=f"pll_ki_in", shared_reference="pll_ki_reference")
    phi_v = vf.add_var(name=f"phi_v_pll_in", shared_reference="phi_v_reference")

    theta_pll = vf.add_var(name=f"theta_pll")
    xi_pll = vf.add_var(name=f"xi_pll")
    omega_pll = vf.add_var(name=f"omega_pll", shared_reference="omega_pll_reference")

    d_theta_pll = vf.add_diff_var(name=f"d_theta_pll", base_var=theta_pll)
    d_xi_pll = vf.add_diff_var(name=f"d_xi_pll", base_var=xi_pll)
    c0 = vf.add_const(0.0)

    return Block(
        state_eqs=[
            # PLL angle dynamics.
            omega_pll,
            # PLL integrator dynamics driven by q-axis voltage.
            -pll_ki * v_q,
        ],
        state_vars=[theta_pll, xi_pll],
        diff_vars=[d_theta_pll, d_xi_pll],
        algebraic_eqs=[
            # PLL frequency output from proportional and integral action.
            omega_pll - (omega_base - pll_kp * v_q + xi_pll),
        ],
        algebraic_vars=[omega_pll],
        init_eqs={theta_pll: phi_v, xi_pll: c0, omega_pll: omega_base},
        diff_init_eqs={d_theta_pll: omega_base, d_xi_pll: c0},
        in_vars=[v_q, omega_base, pll_kp, pll_ki, phi_v],
        out_vars=[theta_pll, omega_pll],
        name=f"{name}_pll",
    )


def _build_pseudo_emt_converter_outer_loop_block(vf: VarFactory, name: str) -> Block:
    """Outer control hierarchy: measurements, DC-voltage loop, Q loop, and current limits."""
    v_d = vf.add_var(name=f"v_d_outer_in", shared_reference="v_d_reference")
    v_q = vf.add_var(name=f"v_q_outer_in", shared_reference="v_q_reference")
    v_0 = vf.add_var(name=f"v_0_outer_in", shared_reference="v_0_reference")
    i_d = vf.add_var(name=f"i_d_outer_in", shared_reference="i_d_reference")
    i_q = vf.add_var(name=f"i_q_outer_in", shared_reference="i_q_reference")
    i_0 = vf.add_var(name=f"i_0_outer_in", shared_reference="i_0_reference")
    v_dc = vf.add_var(name=f"v_dc_outer_in", shared_reference="v_dc_reference")
    P = vf.add_var(name=f"P_outer_in", shared_reference="P_reference")
    Q = vf.add_var(name=f"Q_outer_in", shared_reference="Q_reference")
    sbase = vf.add_var(name=f"sbase_outer_in", shared_reference="sbase_reference")
    P_ref = vf.add_var(name=f"P_ref_outer_in", shared_reference="P_ref_reference")
    Q_ref = vf.add_var(name=f"Q_ref_outer_in", shared_reference="Q_ref_reference")
    Vdc_ref = vf.add_var(name=f"Vdc_ref_outer_in", shared_reference="Vdc_ref_reference")
    Vpk = vf.add_var(name=f"Vpk_outer_in", shared_reference="Vpk_reference")
    P_loss = vf.add_var(name=f"P_loss_outer_in", shared_reference="P_loss_reference")
    vdc_kp = vf.add_var(name=f"vdc_kp_outer_in", shared_reference="vdc_kp_reference")
    vdc_ki = vf.add_var(name=f"vdc_ki_outer_in", shared_reference="vdc_ki_reference")
    q_kp = vf.add_var(name=f"q_kp_outer_in", shared_reference="q_kp_reference")
    q_ki = vf.add_var(name=f"q_ki_outer_in", shared_reference="q_ki_reference")
    i_max = vf.add_var(name=f"i_max_outer_in", shared_reference="i_max_reference")
    tau_meas = vf.add_var(name=f"tau_meas_outer_in", shared_reference="tau_meas_reference")
    aw_gain = vf.add_var(name=f"aw_gain_outer_in", shared_reference="aw_gain_reference")
    regulate_vdc_mode = vf.add_var(name=f"regulate_vdc_mode_outer_in", shared_reference="regulate_vdc_reference")
    regulate_q_mode = vf.add_var(name=f"regulate_q_mode_outer_in", shared_reference="regulate_q_reference")
    regulate_active_mode = vf.add_var(name=f"regulate_active_mode_outer_in", shared_reference="regulate_active_reference")

    xi_vdc = vf.add_var(name=f"xi_vdc")
    xi_q = vf.add_var(name=f"xi_q")
    P_f = vf.add_var(name=f"P_f")
    Q_f = vf.add_var(name=f"Q_f")

    d_xi_vdc = vf.add_diff_var(name=f"d_xi_vdc", base_var=xi_vdc)
    d_xi_q = vf.add_diff_var(name=f"d_xi_q", base_var=xi_q)
    d_P_f = vf.add_diff_var(name=f"d_P_f", base_var=P_f)
    d_Q_f = vf.add_diff_var(name=f"d_Q_f", base_var=Q_f)

    v_mag = vf.add_var(name=f"v_mag")
    i_d_ff = vf.add_var(name=f"i_d_ff")
    i_q_ff = vf.add_var(name=f"i_q_ff")
    i_0_ref_u = vf.add_var(name=f"i_0_ref_u")
    i_d_ref_u = vf.add_var(name=f"i_d_ref_u")
    i_q_ref_u = vf.add_var(name=f"i_q_ref_u")
    i_0_ref = vf.add_var(name=f"i_0_ref", shared_reference="i_0_ref_reference")
    i_d_ref = vf.add_var(name=f"i_d_ref", shared_reference="i_d_ref_reference")
    i_q_ref = vf.add_var(name=f"i_q_ref", shared_reference="i_q_ref_reference")

    eps = vf.add_const(1e-10)
    c0 = vf.add_const(0.0)
    c2 = vf.add_const(2.0)
    c3 = vf.add_const(3.0)
    c_half_power = vf.add_const(0.5)

    sbase_eff = sym.max(sbase, eps)
    tau_meas_eff = sym.max(tau_meas, eps)
    P_ref_pu = P_ref / sbase_eff
    Q_ref_pu = Q_ref / sbase_eff
    P_ac_ff_pu = P_ref_pu + P_loss
    # Pdc control acts on the DC-transferred power.  The measured AC power
    # includes converter loss, so subtract the live loss before comparison.
    active_control_error = (
        regulate_vdc_mode * (Vdc_ref - v_dc)
        + regulate_active_mode * (P_ref_pu - (P_f - P_loss))
    )

    i_d0 = c2 * P_ac_ff_pu / (Vpk + eps)
    q_ref_enabled_pu = Q_ref_pu * regulate_q_mode
    i_q0 = c2 * q_ref_enabled_pu / (Vpk + eps)
    Q0 = c_half_power * Vpk * i_q0

    i_d_cap = sym.hard_sat(i_d_ref_u, -i_max, i_max)
    i_q_cap = sym.sqrt(sym.max(i_max * i_max - i_d_ref * i_d_ref, eps))
    i_0_cap = sym.sqrt(sym.max((i_max * i_max - i_d_ref * i_d_ref - i_q_ref * i_q_ref) / c3, eps / c3))

    return Block(
        state_eqs=[
            # Shared active-axis outer-loop integrator. In `Vm_dc` mode it
            # regulates the DC-link voltage. In `Pac/Pdc` mode it regulates the
            # active-power transfer around the scheduled feedforward term.
            (regulate_vdc_mode + regulate_active_mode) * vdc_ki * (active_control_error + aw_gain * (i_d_ref - i_d_ref_u)),
            # Reactive-power outer-loop integrator with anti-windup feedback.
            regulate_q_mode * q_ki * ((q_ref_enabled_pu - Q_f) + aw_gain * (i_q_ref - i_q_ref_u)),
            # Active-power measurement filter.
            (P - P_f) / tau_meas_eff,
            # Reactive-power measurement filter.
            (Q - Q_f) / tau_meas_eff,
        ],
        state_vars=[xi_vdc, xi_q, P_f, Q_f],
        diff_vars=[d_xi_vdc, d_xi_q, d_P_f, d_Q_f],
        algebraic_eqs=[
            # AC voltage magnitude used by the feedforward terms.
            v_mag - sym.sqrt(v_d * v_d + v_q * v_q + eps),
            # Active-current feedforward from scheduled active power and base losses.
            i_d_ff - c2 * P_ac_ff_pu / (v_mag + eps),
            # Reactive-current feedforward from scheduled reactive power.
            i_q_ff - c2 * q_ref_enabled_pu / (v_mag + eps),
            # Zero-sequence reference schedule for the balanced operating mode.
            i_0_ref_u,
            # Unsaturated d-axis current reference from the gated active loop.
            i_d_ref_u - (i_d_ff + (regulate_vdc_mode + regulate_active_mode) * (vdc_kp * active_control_error + xi_vdc)),
            # Priority-limited d-axis current reference.
            i_d_ref - i_d_cap,
            # Unsaturated q-axis current reference from reactive-power control.
            i_q_ref_u - (i_q_ff + regulate_q_mode * (q_kp * (q_ref_enabled_pu - Q_f) + xi_q)),
            # Residual-current-limited q-axis current reference.
            i_q_ref - sym.hard_sat(i_q_ref_u, -i_q_cap, i_q_cap),
            # Residual-current-limited zero-sequence current reference.
            i_0_ref - sym.hard_sat(i_0_ref_u, -i_0_cap, i_0_cap),
        ],
        algebraic_vars=[v_mag, i_d_ff, i_q_ff, i_0_ref_u, i_d_ref_u, i_q_ref_u, i_0_ref, i_d_ref, i_q_ref],
        init_eqs={
            xi_vdc: (regulate_vdc_mode + regulate_active_mode) * (i_d0 - (c2 * P_ac_ff_pu / (Vpk + eps)) - vdc_kp * active_control_error),
            xi_q: regulate_q_mode * (i_q0 - (c2 * q_ref_enabled_pu / (Vpk + eps)) - q_kp * (q_ref_enabled_pu - Q0)),
            P_f: P,
            Q_f: Q0,
            v_mag: Vpk,
            i_d_ff: c2 * P_ac_ff_pu / (Vpk + eps),
            i_q_ff: c2 * q_ref_enabled_pu / (Vpk + eps),
            i_0_ref_u: c0,
            i_d_ref_u: i_d0,
            i_q_ref_u: i_q0,
            i_0_ref: c0,
            i_d_ref: i_d0,
            i_q_ref: i_q0,
        },
        diff_init_eqs={d_xi_vdc: c0, d_xi_q: c0, d_P_f: c0, d_Q_f: c0},
        in_vars=[
            v_d, v_q, v_0, i_d, i_q, i_0, v_dc, P, Q,
            sbase, P_ref, Q_ref, Vdc_ref, Vpk, P_loss,
            vdc_kp, vdc_ki, q_kp, q_ki, i_max, tau_meas, aw_gain,
            regulate_vdc_mode, regulate_q_mode, regulate_active_mode,
        ],
        out_vars=[P_f, Q_f, i_0_ref, i_d_ref, i_q_ref],
        name=f"{name}_outer_loop",
    )


def _build_pseudo_emt_converter_inner_loop_block(vf: VarFactory, name: str) -> Block:
    """Inner dq0 current controller and modulation-limited voltage command generation."""
    v_d = vf.add_var(name=f"v_d_inner_in", shared_reference="v_d_reference")
    v_q = vf.add_var(name=f"v_q_inner_in", shared_reference="v_q_reference")
    v_0 = vf.add_var(name=f"v_0_inner_in", shared_reference="v_0_reference")
    i_d = vf.add_var(name=f"i_d_inner_in", shared_reference="i_d_reference")
    i_q = vf.add_var(name=f"i_q_inner_in", shared_reference="i_q_reference")
    i_0 = vf.add_var(name=f"i_0_inner_in", shared_reference="i_0_reference")
    omega_pll = vf.add_var(name=f"omega_pll_inner_in", shared_reference="omega_pll_reference")
    omega_base = vf.add_var(name=f"omega_base_inner_in", shared_reference="omega_base_reference")
    R_eq = vf.add_var(name=f"R_eq_inner_in", shared_reference="R_eq_reference")
    L_eq = vf.add_var(name=f"L_eq_inner_in", shared_reference="L_eq_reference")
    i_0_ref = vf.add_var(name=f"i_0_ref_inner_in", shared_reference="i_0_ref_reference")
    i_d_ref = vf.add_var(name=f"i_d_ref_inner_in", shared_reference="i_d_ref_reference")
    i_q_ref = vf.add_var(name=f"i_q_ref_inner_in", shared_reference="i_q_ref_reference")
    i_kp = vf.add_var(name=f"i_kp_inner_in", shared_reference="i_kp_reference")
    i_ki = vf.add_var(name=f"i_ki_inner_in", shared_reference="i_ki_reference")
    aw_gain = vf.add_var(name=f"aw_gain_inner_in", shared_reference="aw_gain_reference")
    m_max = vf.add_var(name=f"m_max_inner_in", shared_reference="m_max_reference")
    Vdc_ref = vf.add_var(name=f"Vdc_ref_inner_in", shared_reference="Vdc_ref_reference")
    v_dc = vf.add_var(name=f"v_dc_inner_in", shared_reference="v_dc_reference")
    vdc_floor = vf.add_var(name=f"vdc_floor_inner_in", shared_reference="vdc_floor_reference")
    sbase = vf.add_var(name=f"sbase_inner_in", shared_reference="sbase_reference")
    P_ref = vf.add_var(name=f"P_ref_inner_in", shared_reference="P_ref_reference")
    Q_ref = vf.add_var(name=f"Q_ref_inner_in", shared_reference="Q_ref_reference")
    P_loss = vf.add_var(name=f"P_loss_inner_in", shared_reference="P_loss_reference")
    Vpk = vf.add_var(name=f"Vpk_inner_in", shared_reference="Vpk_reference")

    xi_id = vf.add_var(name=f"xi_id")
    xi_iq = vf.add_var(name=f"xi_iq")
    xi_i0 = vf.add_var(name=f"xi_i0")
    d_xi_id = vf.add_diff_var(name=f"d_xi_id", base_var=xi_id)
    d_xi_iq = vf.add_diff_var(name=f"d_xi_iq", base_var=xi_iq)
    d_xi_i0 = vf.add_diff_var(name=f"d_xi_i0", base_var=xi_i0)

    v_pi_d_u = vf.add_var(name=f"v_pi_d_u")
    v_pi_q_u = vf.add_var(name=f"v_pi_q_u")
    v_pi_0_u = vf.add_var(name=f"v_pi_0_u")
    v_cmd_d_u = vf.add_var(name=f"v_cmd_d_u")
    v_cmd_q_u = vf.add_var(name=f"v_cmd_q_u")
    v_cmd_0_u = vf.add_var(name=f"v_cmd_0_u")
    k_v_conv = vf.add_var(name=f"k_v_conv", shared_reference="k_v_conv_reference")
    v_lim = vf.add_var(name=f"v_lim")
    v_cmd_d = vf.add_var(name=f"v_cmd_d", shared_reference="v_cmd_d_reference")
    v_cmd_q = vf.add_var(name=f"v_cmd_q", shared_reference="v_cmd_q_reference")
    v_cmd_0 = vf.add_var(name=f"v_cmd_0", shared_reference="v_cmd_0_reference")

    eps = vf.add_const(1e-10)
    c0 = vf.add_const(0.0)
    c2 = vf.add_const(2.0)
    initial_modulation_utilization = vf.add_const(0.90)
    sbase_eff = sym.max(sbase, eps)
    vdc_floor_eff = sym.max(vdc_floor, eps)
    v_dc_eff = sym.max(v_dc, vdc_floor_eff)
    omega_ratio = omega_pll / (omega_base + eps)

    i_d0 = c2 * ((P_ref / sbase_eff) + P_loss) / (Vpk + eps)
    i_q0 = c2 * (Q_ref / sbase_eff) / (Vpk + eps)
    # Match the switched-converter branch-drop convention used by the EMT seed
    # helper so the pseudo model starts from the same commanded dq voltage.
    v_cmd_d0 = Vpk - R_eq * i_d0 + L_eq * i_q0
    v_cmd_q0 = -R_eq * i_q0 - L_eq * i_d0
    v_d_cap = sym.hard_sat(v_cmd_d_u, -v_lim, v_lim)
    v_q_cap = sym.sqrt(sym.max(v_lim * v_lim - v_cmd_d * v_cmd_d, eps))
    v_0_cap = sym.sqrt(sym.max((v_lim * v_lim - v_cmd_d * v_cmd_d - v_cmd_q * v_cmd_q) / vf.add_const(3.0), eps / vf.add_const(3.0)))

    return Block(
        state_eqs=[
            # d-axis current-controller integrator with anti-windup feedback.
            i_ki * ((i_d_ref - i_d) + aw_gain * (v_cmd_d - v_cmd_d_u)),
            # q-axis current-controller integrator with anti-windup feedback.
            i_ki * ((i_q_ref - i_q) + aw_gain * (v_cmd_q - v_cmd_q_u)),
            # 0-axis current-controller integrator with anti-windup feedback.
            i_ki * ((i_0_ref - i_0) + aw_gain * (v_cmd_0 - v_cmd_0_u)),
        ],
        state_vars=[xi_id, xi_iq, xi_i0],
        diff_vars=[d_xi_id, d_xi_iq, d_xi_i0],
        algebraic_eqs=[
            # Unsaturated d-axis PI output.
            v_pi_d_u - (i_kp * (i_d_ref - i_d) + xi_id),
            # Unsaturated q-axis PI output.
            v_pi_q_u - (i_kp * (i_q_ref - i_q) + xi_iq),
            # Unsaturated 0-axis PI output.
            v_pi_0_u - (i_kp * (i_0_ref - i_0) + xi_i0),
            # Unsaturated d-axis converter voltage command with decoupling.
            v_cmd_d_u - (v_d - R_eq * i_d + omega_ratio * L_eq * i_q - v_pi_d_u),
            # Unsaturated q-axis converter voltage command with decoupling.
            v_cmd_q_u - (v_q - R_eq * i_q - omega_ratio * L_eq * i_d - v_pi_q_u),
            # Unsaturated 0-axis converter voltage command.
            v_cmd_0_u - (v_0 - R_eq * i_0 - v_pi_0_u),
            # Modulation-limit gain based on the nominal operating-point command.
            k_v_conv - (sym.sqrt(v_cmd_d0 * v_cmd_d0 + v_cmd_q0 * v_cmd_q0 + eps)
                        / (initial_modulation_utilization * m_max * (Vdc_ref + eps))),
            # Available converter voltage magnitude from modulation and DC voltage.
            v_lim - (k_v_conv * m_max * v_dc_eff),
            # Saturated d-axis converter voltage command.
            v_cmd_d - v_d_cap,
            # Saturated q-axis converter voltage command.
            v_cmd_q - sym.hard_sat(v_cmd_q_u, -v_q_cap, v_q_cap),
            # Saturated 0-axis converter voltage command.
            v_cmd_0 - sym.hard_sat(v_cmd_0_u, -v_0_cap, v_0_cap),
        ],
        algebraic_vars=[v_pi_d_u, v_pi_q_u, v_pi_0_u, v_cmd_d_u, v_cmd_q_u, v_cmd_0_u, k_v_conv, v_lim, v_cmd_d, v_cmd_q, v_cmd_0],
        init_eqs={
            xi_id: c0,
            xi_iq: c0,
            xi_i0: c0,
            v_pi_d_u: c0,
            v_pi_q_u: c0,
            v_pi_0_u: c0,
            v_cmd_d_u: v_cmd_d0,
            v_cmd_q_u: v_cmd_q0,
            v_cmd_0_u: c0,
            k_v_conv: sym.sqrt(v_cmd_d0 * v_cmd_d0 + v_cmd_q0 * v_cmd_q0 + eps) / (initial_modulation_utilization * m_max * (Vdc_ref + eps)),
            v_lim: sym.sqrt(v_cmd_d0 * v_cmd_d0 + v_cmd_q0 * v_cmd_q0 + eps) * v_dc / (initial_modulation_utilization * (Vdc_ref + eps)),
            v_cmd_d: v_cmd_d0,
            v_cmd_q: v_cmd_q0,
            v_cmd_0: c0,
        },
        diff_init_eqs={d_xi_id: c0, d_xi_iq: c0, d_xi_i0: c0},
        in_vars=[
            v_d, v_q, v_0, i_d, i_q, i_0, omega_pll, omega_base, R_eq, L_eq,
            i_0_ref, i_d_ref, i_q_ref, i_kp, i_ki, aw_gain, m_max, Vdc_ref, v_dc, vdc_floor,
            sbase, P_ref, Q_ref, P_loss, Vpk,
        ],
        out_vars=[v_cmd_d, v_cmd_q, v_cmd_0, k_v_conv],
        name=f"{name}_inner_loop",
    )


def _build_pseudo_emt_converter_transformer_block(vf: VarFactory, name: str) -> Block:
    """AC-side interface branch with dq0 current dynamics and abc coupling."""
    v_A = vf.add_var(name=f"v_A_in_tr")
    v_B = vf.add_var(name=f"v_B_in_tr")
    v_C = vf.add_var(name=f"v_C_in_tr")
    theta_pll = vf.add_var(name=f"theta_pll_in_tr", shared_reference="theta_pll_reference")
    omega_pll = vf.add_var(name=f"omega_pll_in_tr", shared_reference="omega_pll_reference")
    omega_base = vf.add_var(name=f"omega_base_in_tr", shared_reference="omega_base_reference")
    R_eq = vf.add_var(name=f"R_eq_in_tr", shared_reference="R_eq_reference")
    L_eq = vf.add_var(name=f"L_eq_in_tr", shared_reference="L_eq_reference")
    v_cmd_d = vf.add_var(name=f"v_cmd_d_in_tr", shared_reference="v_cmd_d_reference")
    v_cmd_q = vf.add_var(name=f"v_cmd_q_in_tr", shared_reference="v_cmd_q_reference")
    v_cmd_0 = vf.add_var(name=f"v_cmd_0_in_tr", shared_reference="v_cmd_0_reference")
    sbase = vf.add_var(name=f"sbase_in_tr", shared_reference="sbase_reference")
    P_ref = vf.add_var(name=f"P_ref_in_tr", shared_reference="P_ref_reference")
    Q_ref = vf.add_var(name=f"Q_ref_in_tr", shared_reference="Q_ref_reference")
    P_loss = vf.add_var(name=f"P_loss_in_tr", shared_reference="P_loss_reference")
    Vpk = vf.add_var(name=f"Vpk_in_tr", shared_reference="Vpk_reference")

    i_d = vf.add_var(name=f"i_d")
    i_q = vf.add_var(name=f"i_q")
    i_0 = vf.add_var(name=f"i_0")
    d_i_d = vf.add_diff_var(name=f"d_i_d", base_var=i_d)
    d_i_q = vf.add_diff_var(name=f"d_i_q", base_var=i_q)
    d_i_0 = vf.add_diff_var(name=f"d_i_0", base_var=i_0)

    i_A = vf.add_var(name=f"i_A", reference=VarPowerFlowReferenceType.i_A)
    i_B = vf.add_var(name=f"i_B", reference=VarPowerFlowReferenceType.i_B)
    i_C = vf.add_var(name=f"i_C", reference=VarPowerFlowReferenceType.i_C)
    v_d = vf.add_var(name=f"v_d", shared_reference="v_d_reference")
    v_q = vf.add_var(name=f"v_q", shared_reference="v_q_reference")
    v_0 = vf.add_var(name=f"v_0", shared_reference="v_0_reference")

    eps = vf.add_const(1e-10)
    c0 = vf.add_const(0.0)
    c13 = vf.add_const(1.0 / 3.0)
    c23 = vf.add_const(2.0 / 3.0)
    c2 = vf.add_const(2.0)
    shift = vf.add_const(2.0 * np.pi / 3.0)
    theta_b = theta_pll - shift
    theta_c = theta_pll + shift
    omega_ratio = omega_pll / (omega_base + eps)
    sbase_eff = sym.max(sbase, eps)

    i_d0 = c2 * ((P_ref / sbase_eff) + P_loss) / (Vpk + eps)
    i_q0 = c2 * (Q_ref / sbase_eff) / (Vpk + eps)
    i_0_decay = vf.add_const(1.0)

    return Block(
        state_eqs=[
            # Match the switched-converter RL branch sign convention so the pseudo
            # interface current dynamics use the same physical voltage drop model.
            (omega_base * (v_d - v_cmd_d - R_eq * i_d + omega_ratio * L_eq * i_q)) / L_eq,
            (omega_base * (v_q - v_cmd_q - R_eq * i_q - omega_ratio * L_eq * i_d)) / L_eq,
            # Balanced three-wire operation has no neutral return path, so the
            # pseudo-EMT converter must not build up a zero-sequence current.
            # Keep the 0-axis state explicitly damped to zero.
            -(omega_base * i_0_decay * i_0) / L_eq,
        ],
        state_vars=[i_d, i_q, i_0],
        diff_vars=[d_i_d, d_i_q, d_i_0],
        algebraic_eqs=[
            # abc-to-d transformation in the PLL reference frame.
            v_d - c23 * (sym.sin(theta_pll) * v_A + sym.sin(theta_b) * v_B + sym.sin(theta_c) * v_C),
            # abc-to-q transformation in the PLL reference frame.
            v_q + c23 * (sym.cos(theta_pll) * v_A + sym.cos(theta_b) * v_B + sym.cos(theta_c) * v_C),
            # abc-to-0 transformation for zero-sequence voltage.
            v_0 - c13 * (v_A + v_B + v_C),
            # dq0-to-abc reconstruction of phase currents.
            i_A - (i_d * sym.sin(theta_pll) - i_q * sym.cos(theta_pll)),
            i_B - (i_d * sym.sin(theta_b) - i_q * sym.cos(theta_b)),
            i_C - (i_d * sym.sin(theta_c) - i_q * sym.cos(theta_c)),
        ],
        algebraic_vars=[i_A, i_B, i_C, v_d, v_q, v_0],
        init_eqs={i_d: i_d0, i_q: i_q0, i_0: c0, v_d: Vpk, v_q: c0, v_0: c0},
        diff_init_eqs={d_i_d: c0, d_i_q: c0, d_i_0: c0},
        in_vars=[v_A, v_B, v_C, theta_pll, omega_pll, omega_base, R_eq, L_eq, v_cmd_d, v_cmd_q, v_cmd_0, sbase, P_ref, Q_ref, P_loss, Vpk],
        out_vars=[i_A, i_B, i_C, i_d, i_q, i_0, v_d, v_q, v_0],
        name=f"{name}_transformer",
    )
def get_full_pseudo_emt_converter(
    vf: VarFactory,
    name: str = "pseudo_converter_emt",
) -> EmtModelTemplate:
    """Assemble the pseudo-EMT converter from meaningful electrical and control sub-blocks."""
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.VscDevice
    templ.name = name
    templ.block.name = name

    v_A = vf.add_var(name=f"v_A", reference=VarPowerFlowReferenceType.v_A)
    v_B = vf.add_var(name=f"v_B", reference=VarPowerFlowReferenceType.v_B)
    v_C = vf.add_var(name=f"v_C", reference=VarPowerFlowReferenceType.v_C)
    # AC/DC physical converter block: parameters, DC link, power, losses, and DC terminal relation.
    vsc_block = _build_pseudo_emt_converter_vsc_block(
        vf=vf,
        name=name,
    )
    # Reuse the physical VSC block DC-bus input directly at the template root.
    # Creating an extra wrapper variable here leaves one free symbolic node in the
    # unified equations, which later confuses the structural compiled backend.
    v_dc_bus = vsc_block.in_vars[6]

    # Control hierarchy blocks.
    pll_block = _build_pseudo_emt_converter_pll_block(vf=vf, name=name)
    outer_loop_block = _build_pseudo_emt_converter_outer_loop_block(vf=vf, name=name)
    inner_loop_block = _build_pseudo_emt_converter_inner_loop_block(vf=vf, name=name)

    # AC-side transformer/interface block with dq0 current dynamics.
    transformer_block = _build_pseudo_emt_converter_transformer_block(vf=vf, name=name)

    # Direct network wiring: the terminal pass-through block is intentionally removed.
    vf.add_connections(transformer_block.in_vars[0:3], [v_A, v_B, v_C])
    vsc_block.in_vars[6] = v_dc_bus

    # Transformer provides dq0 measurements and interface currents to the VSC/control hierarchy.
    vf.add_connections(vsc_block.in_vars[0:3], transformer_block.out_vars[6:9])
    vf.add_connections(vsc_block.in_vars[3:6], transformer_block.out_vars[3:6])
    vf.add_connections([pll_block.in_vars[0]], [transformer_block.out_vars[7]])
    vf.add_connections(outer_loop_block.in_vars[0:3], transformer_block.out_vars[6:9])
    vf.add_connections(outer_loop_block.in_vars[3:6], transformer_block.out_vars[3:6])
    vf.add_connections(inner_loop_block.in_vars[0:3], transformer_block.out_vars[6:9])
    vf.add_connections(inner_loop_block.in_vars[3:6], transformer_block.out_vars[3:6])

    # VSC block exports physical quantities and parameters used by the controls.
    vf.add_connections(
        pll_block.in_vars[1:5],
        [vsc_block.out_vars[8], vsc_block.out_vars[16], vsc_block.out_vars[17], vsc_block.out_vars[9]],
    )
    vf.add_connections(
        [outer_loop_block.in_vars[6], outer_loop_block.in_vars[7], outer_loop_block.in_vars[8]],
        [vsc_block.out_vars[0], vsc_block.out_vars[2], vsc_block.out_vars[3]],
    )
    vf.add_connections(outer_loop_block.in_vars[9:25], [
        vsc_block.out_vars[4], vsc_block.out_vars[5], vsc_block.out_vars[6], vsc_block.out_vars[7], vsc_block.out_vars[10],
        vsc_block.out_vars[26], vsc_block.out_vars[20], vsc_block.out_vars[21], vsc_block.out_vars[22], vsc_block.out_vars[23],
        vsc_block.out_vars[24], vsc_block.out_vars[29], vsc_block.out_vars[30], vsc_block.out_vars[34], vsc_block.out_vars[35], vsc_block.out_vars[36],
    ])
    vf.add_connections([inner_loop_block.in_vars[6], inner_loop_block.in_vars[7], inner_loop_block.in_vars[8], inner_loop_block.in_vars[9]], [
        pll_block.out_vars[1], vsc_block.out_vars[8], vsc_block.out_vars[11], vsc_block.out_vars[12],
    ])
    vf.add_connections(inner_loop_block.in_vars[10:13], outer_loop_block.out_vars[2:5])
    vf.add_connections(inner_loop_block.in_vars[13:25], [
        vsc_block.out_vars[18], vsc_block.out_vars[19], vsc_block.out_vars[30], vsc_block.out_vars[25], vsc_block.out_vars[7],
        vsc_block.out_vars[0], vsc_block.out_vars[31], vsc_block.out_vars[4], vsc_block.out_vars[5], vsc_block.out_vars[6],
        vsc_block.out_vars[26], vsc_block.out_vars[10],
    ])

    # Controller outputs drive the AC interface dynamics.
    vf.add_connections([transformer_block.in_vars[3], transformer_block.in_vars[4]], pll_block.out_vars)
    vf.add_connections(transformer_block.in_vars[5:8], [vsc_block.out_vars[8], vsc_block.out_vars[11], vsc_block.out_vars[12]])
    vf.add_connections(transformer_block.in_vars[8:11], inner_loop_block.out_vars)
    vf.add_connections(transformer_block.in_vars[11:16], [
        vsc_block.out_vars[4], vsc_block.out_vars[5], vsc_block.out_vars[6], vsc_block.out_vars[26], vsc_block.out_vars[10],
    ])

    templ.block.children.extend([vsc_block, pll_block, inner_loop_block, outer_loop_block, transformer_block])
    templ.block.in_vars = [v_A, v_B, v_C, v_dc_bus]
    templ.block.out_vars = [
        transformer_block.out_vars[0],
        transformer_block.out_vars[1],
        transformer_block.out_vars[2],
        vsc_block.out_vars[1],
    ]

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_N: None,
        VarPowerFlowReferenceType.v_A: v_A,
        VarPowerFlowReferenceType.v_B: v_B,
        VarPowerFlowReferenceType.v_C: v_C,
        VarPowerFlowReferenceType.vt_A: v_A,
        VarPowerFlowReferenceType.vt_B: v_B,
        VarPowerFlowReferenceType.vt_C: v_C,
        VarPowerFlowReferenceType.Vdc: v_dc_bus,
        VarPowerFlowReferenceType.Vf_dc: v_dc_bus,
        VarPowerFlowReferenceType.i_N: None,
        VarPowerFlowReferenceType.it_A: transformer_block.out_vars[0],
        VarPowerFlowReferenceType.it_B: transformer_block.out_vars[1],
        VarPowerFlowReferenceType.it_C: transformer_block.out_vars[2],
        VarPowerFlowReferenceType.if_N: None,
        VarPowerFlowReferenceType.if_A: None,
        VarPowerFlowReferenceType.if_B: None,
        VarPowerFlowReferenceType.if_C: None,
        VarPowerFlowReferenceType.it_N: None,
        VarPowerFlowReferenceType.Sf_A: None,
        VarPowerFlowReferenceType.Sf_B: None,
        VarPowerFlowReferenceType.Sf_C: None,
        VarPowerFlowReferenceType.St_A: None,
        VarPowerFlowReferenceType.St_B: None,
        VarPowerFlowReferenceType.St_C: None,
        VarPowerFlowReferenceType.d_v_N_f: None,
        VarPowerFlowReferenceType.d_v_A_f: None,
        VarPowerFlowReferenceType.d_v_B_f: None,
        VarPowerFlowReferenceType.d_v_C_f: None,
        VarPowerFlowReferenceType.d_v_N_t: None,
        VarPowerFlowReferenceType.d_v_A_t: None,
        VarPowerFlowReferenceType.d_v_B_t: None,
        VarPowerFlowReferenceType.d_v_C_t: None,
        VarPowerFlowReferenceType.If_dc: vsc_block.out_vars[1],
        VarPowerFlowReferenceType.P: vsc_block.out_vars[2],
        VarPowerFlowReferenceType.Q: vsc_block.out_vars[3],
        VarPowerFlowReferenceType.phi_v: vsc_block.out_vars[9],
        VarPowerFlowReferenceType.Vpk: vsc_block.out_vars[10],
    }
    return templ
