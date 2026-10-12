# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Dict

import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Emt.xfmr_emt_template import _project_currents
from VeraGridEngine.Utils.Symbolic.block import Expr, Var
from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowReferenceType, VarPowerFlowReferenceType


def get_xfmr_emt_template_multilinear(
    vf: VarFactory,
    name: str = "xfmr_emt_template_ml",
) -> EmtModelTemplate:
    """
    Build the EMT DAE template of a basic ATP-like transformer model.

    Multilinear variant notes
    -------------------------
    This function mirrors ``get_xfmr_emt_template`` structure/order/comments and
    keeps the same physics. The only intended reformulation is:

    * squared terms are represented with auxiliary variables, and
    * nonlinear constitutive equations are written in multiplied form.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.TransformerTypeDevice
    templ.name = name
    templ.block.name = name

    c0: Expr = vf.add_const(0.0)
    c1: Expr = vf.add_const(1.0)
    c2: Expr = vf.add_const(2.0)
    c3: Expr = vf.add_const(3.0)
    c10: Expr = vf.add_const(10.0)
    c100: Expr = vf.add_const(100.0)
    c1000: Expr = vf.add_const(1000.0)
    c_eps: Expr = vf.add_const(1e-9)
    c_smooth: Expr = vf.add_const(1e-8)
    c_sqrt2: Expr = sym.sqrt(vf.add_const(2.0))

    # ------------------------------------------------------------------
    # Static parameters mapped from the transformer API object.
    # ------------------------------------------------------------------
    omega_base: Var = vf.add_var(name=f"omega_base")
    xfmr_s_rated_mva: Var = vf.add_var(name=f"xfmr_s_rated_mva")
    xfmr_oc_current_pct: Var = vf.add_var(name=f"xfmr_oc_current_pct")
    xfmr_oc_loss_kw: Var = vf.add_var(name=f"xfmr_oc_loss_kw")
    xfmr_sc_voltage_pct: Var = vf.add_var(name=f"xfmr_sc_voltage_pct")
    xfmr_sc_loss_kw: Var = vf.add_var(name=f"xfmr_sc_loss_kw")
    xfmr_tap_module: Var = vf.add_var(name=f"xfmr_tap_module")

    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.omega_base] = omega_base
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.transformer_rated_power_mva] = xfmr_s_rated_mva
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.transformer_open_circuit_current_pct] = xfmr_oc_current_pct
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.transformer_open_circuit_loss_kw] = xfmr_oc_loss_kw
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.transformer_short_circuit_voltage_pct] = xfmr_sc_voltage_pct
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.transformer_short_circuit_loss_kw] = xfmr_sc_loss_kw
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.transformer_tap_ratio] = xfmr_tap_module
    templ.block.parameters.update({
        omega_base: vf.add_const(None),
        xfmr_s_rated_mva: vf.add_const(None),
        xfmr_oc_current_pct: vf.add_const(None),
        xfmr_oc_loss_kw: vf.add_const(None),
        xfmr_sc_voltage_pct: vf.add_const(None),
        xfmr_sc_loss_kw: vf.add_const(None),
        xfmr_tap_module: vf.add_const(None),
    })

    # ------------------------------------------------------------------
    # Mapped winding-connection matrices.
    # ------------------------------------------------------------------
    cf_enums: list[list[ParamPowerFlowReferenceType]] = [
        [
            ParamPowerFlowReferenceType.transformer_from_connection_aa,
            ParamPowerFlowReferenceType.transformer_from_connection_ab,
            ParamPowerFlowReferenceType.transformer_from_connection_ac,
        ],
        [
            ParamPowerFlowReferenceType.transformer_from_connection_ba,
            ParamPowerFlowReferenceType.transformer_from_connection_bb,
            ParamPowerFlowReferenceType.transformer_from_connection_bc,
        ],
        [
            ParamPowerFlowReferenceType.transformer_from_connection_ca,
            ParamPowerFlowReferenceType.transformer_from_connection_cb,
            ParamPowerFlowReferenceType.transformer_from_connection_cc,
        ],
    ]
    ct_enums: list[list[ParamPowerFlowReferenceType]] = [
        [
            ParamPowerFlowReferenceType.transformer_to_connection_aa,
            ParamPowerFlowReferenceType.transformer_to_connection_ab,
            ParamPowerFlowReferenceType.transformer_to_connection_ac,
        ],
        [
            ParamPowerFlowReferenceType.transformer_to_connection_ba,
            ParamPowerFlowReferenceType.transformer_to_connection_bb,
            ParamPowerFlowReferenceType.transformer_to_connection_bc,
        ],
        [
            ParamPowerFlowReferenceType.transformer_to_connection_ca,
            ParamPowerFlowReferenceType.transformer_to_connection_cb,
            ParamPowerFlowReferenceType.transformer_to_connection_cc,
        ],
    ]

    c_f_expr: list[list[Expr]] = []
    c_t_expr: list[list[Expr]] = []

    for i in range(3):
        c_f_row: list[Expr] = []
        c_t_row: list[Expr] = []

        for j in range(3):
            c_f_var: Var = vf.add_var(name=f"xfmr_cf_{i}_{j}")
            c_t_var: Var = vf.add_var(name=f"xfmr_ct_{i}_{j}")

            templ.block.api_obj_mapping[cf_enums[i][j]] = c_f_var
            templ.block.api_obj_mapping[ct_enums[i][j]] = c_t_var
            templ.block.parameters[c_f_var] = vf.add_const(None)
            templ.block.parameters[c_t_var] = vf.add_const(None)

            c_f_row.append(c_f_var)
            c_t_row.append(c_t_var)

        c_f_expr.append(c_f_row)
        c_t_expr.append(c_t_row)

    # ------------------------------------------------------------------
    # Local dynamic-model parameters.
    # ------------------------------------------------------------------
    xfmr_core_topology_code: Var = vf.add_var(name=f"xfmr_core_topology_code")
    xfmr_yoke_area_rel: Var = vf.add_var(name=f"xfmr_yoke_area_rel")
    xfmr_yoke_length_rel: Var = vf.add_var(name=f"xfmr_yoke_length_rel")
    xfmr_outer_leg_area_rel: Var = vf.add_var(name=f"xfmr_outer_leg_area_rel")
    xfmr_outer_leg_length_rel: Var = vf.add_var(name=f"xfmr_outer_leg_length_rel")
    xfmr_c_term: Var = vf.add_var(name=f"xfmr_c_term")
    xfmr_use_linear_core: Var = vf.add_var(name=f"xfmr_use_linear_core")
    xfmr_core_knee_flux_mult: Var = vf.add_var(name=f"xfmr_core_knee_flux_mult")
    xfmr_core_knee_current_mult: Var = vf.add_var(name=f"xfmr_core_knee_current_mult")

    xfmr_sc_resistance_pct: Var = vf.add_var(name=f"xfmr_sc_resistance_pct")
    xfmr_core_linear_l_pu: Var = vf.add_var(name=f"xfmr_core_linear_l_pu")
    xfmr_core_a_prime: Var = vf.add_var(name=f"xfmr_core_a_prime")
    xfmr_core_b_prime: Var = vf.add_var(name=f"xfmr_core_b_prime")

    templ.block.event_dict[xfmr_core_topology_code] = vf.add_const(3.0)
    templ.block.event_dict[xfmr_yoke_area_rel] = vf.add_const(1.0)
    templ.block.event_dict[xfmr_yoke_length_rel] = vf.add_const(1.0)
    templ.block.event_dict[xfmr_outer_leg_area_rel] = vf.add_const(1.0)
    templ.block.event_dict[xfmr_outer_leg_length_rel] = vf.add_const(1.0)
    templ.block.event_dict[xfmr_c_term] = vf.add_const(0.0)
    templ.block.event_dict[xfmr_use_linear_core] = vf.add_const(1.0)
    templ.block.event_dict[xfmr_core_knee_flux_mult] = vf.add_const(1.05)
    templ.block.event_dict[xfmr_core_knee_current_mult] = vf.add_const(8.0)

    # ------------------------------------------------------------------
    # Derived local parameters of the dynamic model.
    # ------------------------------------------------------------------
    templ.block.event_dict[xfmr_sc_resistance_pct] = xfmr_sc_loss_kw / (c10 * xfmr_s_rated_mva + c_eps)

    oc_loss_pu: Expr = (xfmr_oc_loss_kw / c1000) / (xfmr_s_rated_mva + c_eps)
    oc_current_pu: Expr = xfmr_oc_current_pct / c100
    i_mag_pu: Expr = sym.sqrt(oc_current_pu * oc_current_pu - oc_loss_pu * oc_loss_pu + c_eps)

    templ.block.event_dict[xfmr_core_linear_l_pu] = c1 / (i_mag_pu + c_eps)

    lambda_nom_peak: Expr = c_sqrt2
    i_nom_peak_from_linear: Expr = lambda_nom_peak / (xfmr_core_linear_l_pu + c_eps)
    a_prime_auto: Expr = c1 / (xfmr_core_linear_l_pu + c_eps)
    lambda_knee: Expr = xfmr_core_knee_flux_mult * lambda_nom_peak
    i_knee: Expr = xfmr_core_knee_current_mult * i_nom_peak_from_linear
    b_prime_raw: Expr = (i_knee / (lambda_knee + c_eps) - a_prime_auto) / (i_knee + c_eps)
    b_prime_auto: Expr = b_prime_raw * b_prime_raw / (sym.sqrt(b_prime_raw * b_prime_raw + c_smooth) + c_eps)

    templ.block.event_dict[xfmr_core_a_prime] = a_prime_auto
    templ.block.event_dict[xfmr_core_b_prime] = b_prime_auto

    # ------------------------------------------------------------------
    # Leakage-branch parameters.
    # ------------------------------------------------------------------
    z_sc_pu: Expr = xfmr_sc_voltage_pct / c100
    r_sc_pu: Expr = xfmr_sc_resistance_pct / c100
    x_sc_pu: Expr = sym.sqrt(z_sc_pu * z_sc_pu - r_sc_pu * r_sc_pu + c_eps)
    l_sigma: Expr = x_sc_pu / (omega_base + c_eps)
    l_inv: Expr = c1 / (l_sigma + c_eps)

    # ------------------------------------------------------------------
    # Core-loss conductance from open-circuit losses.
    # ------------------------------------------------------------------
    g_core_total: Expr = (xfmr_oc_loss_kw / c1000) / (xfmr_s_rated_mva + c_eps)
    g_core_leg: Expr = g_core_total / c3

    # ------------------------------------------------------------------
    # Terminal electrical interface variables in abc frame.
    # ------------------------------------------------------------------
    vf_keys: Dict[str, VarPowerFlowReferenceType] = {
        "N": VarPowerFlowReferenceType.vf_N,
        "A": VarPowerFlowReferenceType.vf_A,
        "B": VarPowerFlowReferenceType.vf_B,
        "C": VarPowerFlowReferenceType.vf_C,
    }
    vt_keys: Dict[str, VarPowerFlowReferenceType] = {
        "N": VarPowerFlowReferenceType.vt_N,
        "A": VarPowerFlowReferenceType.vt_A,
        "B": VarPowerFlowReferenceType.vt_B,
        "C": VarPowerFlowReferenceType.vt_C,
    }

    v_f: list[Var] = [
        vf.add_var(name=f"vf_A", reference=vf_keys["A"]),
        vf.add_var(name=f"vf_B", reference=vf_keys["B"]),
        vf.add_var(name=f"vf_C", reference=vf_keys["C"]),
    ]
    v_t: list[Var] = [
        vf.add_var(name=f"vt_A", reference=vt_keys["A"]),
        vf.add_var(name=f"vt_B", reference=vt_keys["B"]),
        vf.add_var(name=f"vt_C", reference=vt_keys["C"]),
    ]

    # ------------------------------------------------------------------
    # Dynamic states and derivatives.
    # ------------------------------------------------------------------
    i_leak: list[Var] = [vf.add_var(name=f"i_leak_{ph}") for ph in ("A", "B", "C")]
    lam_leg: list[Var] = [vf.add_var(name=f"lam_leg_{ph}") for ph in ("A", "B", "C")]
    q_f: list[Var] = [vf.add_var(name=f"qf_{ph}") for ph in ("A", "B", "C")]
    q_t: list[Var] = [vf.add_var(name=f"qt_{ph}") for ph in ("A", "B", "C")]

    di_leak: list[Var] = [vf.add_diff_var(name=f"di_leak_{ph}", base_var=i_leak[k]) for k, ph in enumerate(("A", "B", "C"))]
    dlam_leg: list[Var] = [vf.add_diff_var(name=f"dlam_leg_{ph}", base_var=lam_leg[k]) for k, ph in enumerate(("A", "B", "C"))]
    dq_f: list[Var] = [vf.add_diff_var(name=f"dqf_{ph}", base_var=q_f[k]) for k, ph in enumerate(("A", "B", "C"))]
    dq_t: list[Var] = [vf.add_diff_var(name=f"dqt_{ph}", base_var=q_t[k]) for k, ph in enumerate(("A", "B", "C"))]

    # ------------------------------------------------------------------
    # Algebraic variables.
    # ------------------------------------------------------------------
    i_leg_core: list[Var] = [vf.add_var(name=f"i_leg_core_{ph}") for ph in ("A", "B", "C")]
    i_mag: list[Var] = [vf.add_var(name=f"i_mag_{ph}") for ph in ("A", "B", "C")]
    i_loss_leg: list[Var] = [vf.add_var(name=f"i_loss_leg_{ph}") for ph in ("A", "B", "C")]
    i_cap_f: list[Var] = [vf.add_var(name=f"i_cap_f_{ph}") for ph in ("A", "B", "C")]
    i_cap_t: list[Var] = [vf.add_var(name=f"i_cap_t_{ph}") for ph in ("A", "B", "C")]
    if_act: list[Var] = [vf.add_var(name=f"if_{ph}") for ph in ("A", "B", "C")]
    it_act: list[Var] = [vf.add_var(name=f"it_{ph}") for ph in ("A", "B", "C")]
    i_return_path: Var = vf.add_var(name=f"i_return_path")
    i_return_total: Var = vf.add_var(name=f"i_return_total")

    # Multilinear auxiliaries.
    i_leg_core_sq_aux: list[Var] = [vf.add_var(name=f"i_leg_core_sq_aux_{ph}") for ph in ("A", "B", "C")]
    i_return_path_sq_aux: Var = vf.add_var(name=f"i_return_path_sq_aux")
    i_plus_smoothing_root: Var = vf.add_var(name=f"i_plus_smoothing_root{name}")
    i_plus_smoothing_root_aux: Var = vf.add_var(name=f"i_plus_smoothing_root_aux{name}")
    i_plus_smoothing_root_pos1: Var = vf.add_var(name=f"i_plus_smoothing_root_pos1{name}")
    i_plus_smoothing_root_pos2: Var = vf.add_var(name=f"i_plus_smoothing_root_pos2{name}")
    i_leg_plus_smoothing_sq: list[Var] = [vf.add_var(name=f"i_leg_plus_smoothing_sq_{ph}") for ph in ("A", "B", "C")]
    i_leg_plus_smoothing_sq_aux: list[Var] = [vf.add_var(name=f"i_leg_plus_smoothing_sq_aux{ph}") for ph in ("A", "B", "C")]
    i_leg_plus_smoothing_pos1: list[Var] = [vf.add_var(name=f"i_leg_plus_smoothing_pos1_{ph}_{name}") for ph in ("A", "B", "C")]
    i_leg_plus_smoothing_pos2: list[Var] = [vf.add_var(name=f"i_leg_plus_smoothing_pos2_{ph}_{name}") for ph in ("A", "B", "C")]

    templ.block.in_vars = v_f + v_t
    templ.block.state_vars = i_leak + lam_leg + q_f + q_t
    templ.block.diff_vars = di_leak + dlam_leg + dq_f + dq_t
    templ.block.algebraic_vars = (
        i_leg_core
        + [i_return_path, i_return_total]
        + i_mag
        + i_loss_leg
        + i_cap_f
        + i_cap_t
        + if_act
        + it_act
        + i_leg_core_sq_aux
        + [i_return_path_sq_aux]
        + [i_plus_smoothing_root, i_plus_smoothing_root_aux]
        + [i_plus_smoothing_root_pos1, i_plus_smoothing_root_pos2]
        + i_leg_plus_smoothing_sq
        + i_leg_plus_smoothing_sq_aux
        + i_leg_plus_smoothing_pos1
        + i_leg_plus_smoothing_pos2
    )

    # ------------------------------------------------------------------
    # Voltage transformation from terminal abc frame to winding frame.
    # ------------------------------------------------------------------
    c_f_expr_t: list[list[Expr]] = [[c_f_expr[j][i] for j in range(3)] for i in range(3)]
    c_t_expr_t: list[list[Expr]] = [[c_t_expr[j][i] for j in range(3)] for i in range(3)]

    v_f_w: list[Expr] = []
    v_t_w: list[Expr] = []

    for i in range(3):
        expr_vfw: Expr = c0
        expr_vtw: Expr = c0

        for j in range(3):
            expr_vfw = expr_vfw + c_f_expr_t[i][j] * v_f[j]
            expr_vtw = expr_vtw + c_t_expr_t[i][j] * v_t[j]

        v_f_w.append(expr_vfw)
        v_t_w.append(expr_vtw)

    # ------------------------------------------------------------------
    # Internal winding-side voltages.
    #
    # Leakage branch:
    #   v_leak = v_f_w - n_tap * v_t_w
    #
    # Core branch:
    #   referred only to the from side
    # ------------------------------------------------------------------
    n_tap: Expr = xfmr_tap_module
    v_leak: list[Expr] = [v_f_w[k] - n_tap * v_t_w[k] for k in range(3)]
    v_core_w: list[Expr] = [v_f_w[k] for k in range(3)]

    # ------------------------------------------------------------------
    # State equations.
    # ------------------------------------------------------------------
    state_eqs: list[Expr] = []

    # Leakage-current dynamics.
    for k in range(3):
        state_eqs.append(l_inv * (v_leak[k] - r_sc_pu * i_leak[k]))

    # Core-flux dynamics referred to the from side.
    for k in range(3):
        state_eqs.append(omega_base * v_core_w[k])

    # Charge dynamics of terminal capacitances.
    for k in range(3):
        state_eqs.append(i_cap_f[k])
    for k in range(3):
        state_eqs.append(i_cap_t[k])

    templ.block.state_eqs = state_eqs

    # ------------------------------------------------------------------
    # Core topology selectors.
    #
    # Supported values:
    #   3.0 -> three-legged core
    #   5.0 -> five-legged core
    # ------------------------------------------------------------------
    lam_return_total: Expr = -(lam_leg[0] + lam_leg[1] + lam_leg[2])
    five_leg_selector: Expr = (xfmr_core_topology_code - c3) / c2
    three_leg_selector: Expr = c1 - five_leg_selector

    yoke_area_rel: Expr = xfmr_yoke_area_rel
    yoke_length_rel: Expr = xfmr_yoke_length_rel
    outer_leg_area_rel: Expr = xfmr_outer_leg_area_rel
    outer_leg_length_rel: Expr = xfmr_outer_leg_length_rel

    yoke_linear_coeff: Expr = xfmr_core_linear_l_pu * yoke_area_rel / (yoke_length_rel + c_eps)
    outer_linear_coeff: Expr = xfmr_core_linear_l_pu * outer_leg_area_rel / (outer_leg_length_rel + c_eps)
    i_plus_smoothing_equation: Expr = i_plus_smoothing_root*i_plus_smoothing_root_aux - (i_return_path * i_return_path_sq_aux + c_smooth)
    
    yoke_frolich_lam_denom: Expr = (
        xfmr_core_a_prime * yoke_length_rel
        + xfmr_core_b_prime * i_plus_smoothing_root
        + c_eps
    )
    outer_frolich_lam_denom: Expr = (
        xfmr_core_a_prime * outer_leg_length_rel
        + xfmr_core_b_prime * i_plus_smoothing_root
        + c_eps
    )
    yoke_frolich_lam_nom: Expr = yoke_area_rel * i_return_path 
    outer_frolich_lam_nom: Expr = outer_leg_area_rel * i_return_path 

    # ------------------------------------------------------------------
    # Projection of winding-frame currents to terminal-frame currents.
    # ------------------------------------------------------------------
    i_series_from: list[Expr] = _project_currents(c_f_expr, i_leak, c0)
    i_series_to: list[Expr] = _project_currents(c_t_expr, i_leak, c0)

    # Core branch referred only to the from side.
    i_core_from_w: list[Expr] = [i_mag[k] + i_loss_leg[k] for k in range(3)]
    i_core_to_w: list[Expr] = [c0, c0, c0]

    i_core_from_term: list[Expr] = _project_currents(c_f_expr, i_core_from_w, c0)
    i_core_to_term: list[Expr] = _project_currents(c_t_expr, i_core_to_w, c0)

    # ------------------------------------------------------------------
    # Algebraic equations.
    # ------------------------------------------------------------------
    alg_eqs: list[Expr] = []

    # Multilinear auxiliary variable ties.
    for k in range(3):
        alg_eqs.append(i_leg_core_sq_aux[k] - i_leg_core[k])
        alg_eqs.append(i_leg_plus_smoothing_sq[k] - i_leg_plus_smoothing_sq_aux[k])
    alg_eqs.append(i_return_path_sq_aux - i_return_path)
    alg_eqs.append(i_plus_smoothing_root - i_plus_smoothing_root_aux)
    alg_eqs.append(i_plus_smoothing_root - i_plus_smoothing_root_pos1 * i_plus_smoothing_root_pos2)
    alg_eqs.append(i_plus_smoothing_root_pos1 - i_plus_smoothing_root_pos2)

    #Multilinear sqrt ties
    alg_eqs.append(i_plus_smoothing_equation)
    for k in range(3):
        alg_eqs.append(i_leg_plus_smoothing_sq[k]*i_leg_plus_smoothing_sq_aux[k] - (i_leg_core[k] * i_leg_core_sq_aux[k] + c_smooth))
        alg_eqs.append(i_leg_plus_smoothing_sq[k] - i_leg_plus_smoothing_pos1[k] * i_leg_plus_smoothing_pos2[k])
        alg_eqs.append(i_leg_plus_smoothing_pos1[k] - i_leg_plus_smoothing_pos2[k])


    # Leg constitutive laws.
    for k in range(3):
        linear_leg_eq: Expr = lam_leg[k] - xfmr_core_linear_l_pu * i_leg_core[k]
        nonlinear_leg_denom: Expr = (
            xfmr_core_a_prime
            + xfmr_core_b_prime * i_leg_plus_smoothing_sq[k]
            + c_eps
        )
        nonlinear_leg_eq: Expr = lam_leg[k] * nonlinear_leg_denom - i_leg_core[k]
        alg_eqs.append(
            xfmr_use_linear_core * linear_leg_eq
            + (c1 - xfmr_use_linear_core) * nonlinear_leg_eq
        )

    # Return-path constitutive law.
    five_leg_eq_linear: Expr = (c1 / c2) * lam_return_total - (
        c2 * yoke_linear_coeff * i_return_path + outer_linear_coeff * i_return_path
    )
    five_leg_eq_nonlinear: Expr = yoke_frolich_lam_denom*outer_frolich_lam_denom*(
        (c1 / c2) * lam_return_total) - (
        c2 * yoke_frolich_lam_nom*outer_frolich_lam_denom + outer_frolich_lam_nom*yoke_frolich_lam_denom
    )
    three_leg_eq_linear: Expr = lam_return_total - c2 * yoke_linear_coeff * i_return_path
    three_leg_eq_nonlinear: Expr = yoke_frolich_lam_denom*lam_return_total - c2 * yoke_frolich_lam_nom

    alg_eqs.append(
        five_leg_selector * (
            xfmr_use_linear_core * five_leg_eq_linear
            + (c1 - xfmr_use_linear_core) * five_leg_eq_nonlinear
        )
        + three_leg_selector * (
            xfmr_use_linear_core * three_leg_eq_linear
            + (c1 - xfmr_use_linear_core) * three_leg_eq_nonlinear
        )
    )

    alg_eqs.append(
        i_return_total - (
            five_leg_selector * c2 * i_return_path
            + three_leg_selector * i_return_path
        )
    )

    # Magnetizing currents.
    for k in range(3):
        alg_eqs.append(i_mag[k] - (i_leg_core[k] - i_return_total))

    # Core-loss currents referred only to the from side.
    for k in range(3):
        alg_eqs.append(i_loss_leg[k] - g_core_leg * v_f_w[k])

    # Charge-voltage relations of terminal capacitances.
    for k in range(3):
        alg_eqs.append(q_f[k] - xfmr_c_term * v_f[k])
        alg_eqs.append(q_t[k] - xfmr_c_term * v_t[k])

    # Terminal current assembly.
    for k in range(3):
        alg_eqs.append(
            if_act[k] - (
                i_series_from[k]
                + i_core_from_term[k]
                + i_cap_f[k]
            )
        )
        alg_eqs.append(
            it_act[k] - (
                -n_tap * i_series_to[k]
                + i_cap_t[k]
            )
        )

    templ.block.algebraic_eqs = alg_eqs
    templ.block.out_vars = if_act + it_act + i_mag

    # ------------------------------------------------------------------
    # External mapping.
    # ------------------------------------------------------------------
    if_keys: Dict[str, VarPowerFlowReferenceType] = {
        "N": VarPowerFlowReferenceType.if_N,
        "A": VarPowerFlowReferenceType.if_A,
        "B": VarPowerFlowReferenceType.if_B,
        "C": VarPowerFlowReferenceType.if_C,
    }
    it_keys: Dict[str, VarPowerFlowReferenceType] = {
        "N": VarPowerFlowReferenceType.it_N,
        "A": VarPowerFlowReferenceType.it_A,
        "B": VarPowerFlowReferenceType.it_B,
        "C": VarPowerFlowReferenceType.it_C,
    }
    Sf_keys: Dict[str, VarPowerFlowReferenceType] = {
        "A": VarPowerFlowReferenceType.Sf_A,
        "B": VarPowerFlowReferenceType.Sf_B,
        "C": VarPowerFlowReferenceType.Sf_C,
    }
    St_keys: Dict[str, VarPowerFlowReferenceType] = {
        "A": VarPowerFlowReferenceType.St_A,
        "B": VarPowerFlowReferenceType.St_B,
        "C": VarPowerFlowReferenceType.St_C,
    }
    d_vf_keys: Dict[str, VarPowerFlowReferenceType] = {
        "N": VarPowerFlowReferenceType.d_v_N_f,
        "A": VarPowerFlowReferenceType.d_v_A_f,
        "B": VarPowerFlowReferenceType.d_v_B_f,
        "C": VarPowerFlowReferenceType.d_v_C_f,
    }
    d_vt_keys: Dict[str, VarPowerFlowReferenceType] = {
        "N": VarPowerFlowReferenceType.d_v_N_t,
        "A": VarPowerFlowReferenceType.d_v_A_t,
        "B": VarPowerFlowReferenceType.d_v_B_t,
        "C": VarPowerFlowReferenceType.d_v_C_t,
    }

    mapping: Dict[VarPowerFlowReferenceType, Var | None] = {
        if_keys["N"]: None,
        if_keys["A"]: None,
        if_keys["B"]: None,
        if_keys["C"]: None,
        it_keys["N"]: None,
        it_keys["A"]: None,
        it_keys["B"]: None,
        it_keys["C"]: None,
        vf_keys["N"]: None,
        vf_keys["A"]: None,
        vf_keys["B"]: None,
        vf_keys["C"]: None,
        vt_keys["N"]: None,
        vt_keys["A"]: None,
        vt_keys["B"]: None,
        vt_keys["C"]: None,
        Sf_keys["A"]: None,
        Sf_keys["B"]: None,
        Sf_keys["C"]: None,
        St_keys["A"]: None,
        St_keys["B"]: None,
        St_keys["C"]: None,
        d_vf_keys["N"]: None,
        d_vf_keys["A"]: None,
        d_vf_keys["B"]: None,
        d_vf_keys["C"]: None,
        d_vt_keys["N"]: None,
        d_vt_keys["A"]: None,
        d_vt_keys["B"]: None,
        d_vt_keys["C"]: None,
    }

    mapping[vf_keys["A"]] = v_f[0]
    mapping[vf_keys["B"]] = v_f[1]
    mapping[vf_keys["C"]] = v_f[2]

    mapping[vt_keys["A"]] = v_t[0]
    mapping[vt_keys["B"]] = v_t[1]
    mapping[vt_keys["C"]] = v_t[2]

    mapping[if_keys["A"]] = if_act[0]
    mapping[if_keys["B"]] = if_act[1]
    mapping[if_keys["C"]] = if_act[2]

    mapping[it_keys["A"]] = it_act[0]
    mapping[it_keys["B"]] = it_act[1]
    mapping[it_keys["C"]] = it_act[2]

    templ.block.external_mapping = mapping

    # ------------------------------------------------------------------
    # Initialization equations.
    #
    # PF-derived terminal currents if_act / it_act are initialized before
    # init_eqs through external_mapping. The magnetic branch is initialized
    # from the from-side winding voltage only.
    # ------------------------------------------------------------------
    c_inv_sqrt3: Expr = c1 / sym.sqrt(c3)

    lam_leg_init: list[Expr] = [
        -(v_f_w[2] - v_f_w[1]) * c_inv_sqrt3,
        -(v_f_w[0] - v_f_w[2]) * c_inv_sqrt3,
        -(v_f_w[1] - v_f_w[0]) * c_inv_sqrt3,
    ]

    init_eqs: Dict[Var, Expr] = {}

    # Charge states.
    for k in range(3):
        init_eqs[q_f[k]] = xfmr_c_term * v_f[k]
        init_eqs[q_t[k]] = xfmr_c_term * v_t[k]

    # Core flux-linkage states from the from-side winding voltage set.
    for k in range(3):
        init_eqs[lam_leg[k]] = lam_leg_init[k]

    # Core leg currents from the constitutive law.
    for k in range(3):
        abs_lam_k: Expr = sym.sqrt(lam_leg[k] * lam_leg[k] + c_smooth)
        i_leg_core_nl_init: Expr = (
            xfmr_core_a_prime * lam_leg[k]
            / (c1 - xfmr_core_b_prime * abs_lam_k + c_eps)
        )

        init_eqs[i_leg_core[k]] = (
            xfmr_use_linear_core * (lam_leg[k] / (xfmr_core_linear_l_pu + c_eps))
            + (c1 - xfmr_use_linear_core) * i_leg_core_nl_init
        )
        init_eqs[i_leg_core_sq_aux[k]] = i_leg_core[k]

    # Return-path currents from initialized fluxes.
    init_eqs[i_return_path] = (
        five_leg_selector * (lam_return_total / (c2 * yoke_linear_coeff + outer_linear_coeff + c_eps))
        + three_leg_selector * (lam_return_total / (c2 * yoke_linear_coeff + c_eps))
    )
    init_eqs[i_return_path_sq_aux] = i_return_path
    init_eqs[i_plus_smoothing_root] = sym.sqrt(i_return_path * i_return_path_sq_aux + c_smooth)
    init_eqs[i_plus_smoothing_root_aux] = i_plus_smoothing_root
    init_eqs[i_plus_smoothing_root_pos1] = sym.sqrt(i_plus_smoothing_root)
    init_eqs[i_plus_smoothing_root_pos2] = i_plus_smoothing_root_pos1
    init_eqs[i_return_total] = (
        five_leg_selector * c2 * i_return_path
        + three_leg_selector * i_return_path
    )

    # Net magnetizing currents.
    for k in range(3):
        init_eqs[i_mag[k]] = i_leg_core[k] - i_return_total
        init_eqs[i_leg_plus_smoothing_sq[k]] = sym.sqrt(i_leg_core[k] * i_leg_core_sq_aux[k] + c_smooth)
        init_eqs[i_leg_plus_smoothing_sq_aux[k]] = i_leg_plus_smoothing_sq[k]
        init_eqs[i_leg_plus_smoothing_pos1[k]] = sym.sqrt(i_leg_plus_smoothing_sq[k])
        init_eqs[i_leg_plus_smoothing_pos2[k]] = i_leg_plus_smoothing_pos1[k]

    # Core-loss currents referred to the from side.
    for k in range(3):
        init_eqs[i_loss_leg[k]] = g_core_leg * v_f_w[k]

    # Leakage-current seed from PF-initialized from-side terminal current.
    for k in range(3):
        init_eqs[i_leak[k]] = if_act[k]

    # Capacitor-current seeds from terminal current balance.
    for k in range(3):
        init_eqs[i_cap_f[k]] = if_act[k] - (i_series_from[k] + i_core_from_term[k])
        init_eqs[i_cap_t[k]] = it_act[k] - (-n_tap * i_series_to[k])

    templ.block.init_eqs = init_eqs

    # ------------------------------------------------------------------
    # Differential initialization equations.
    # ------------------------------------------------------------------
    diff_init_eqs: Dict[Var, Expr] = {}

    for k in range(3):
        diff_init_eqs[di_leak[k]] = l_inv * (v_leak[k] - r_sc_pu * i_leak[k])
        diff_init_eqs[dlam_leg[k]] = omega_base * v_f_w[k]
        diff_init_eqs[dq_f[k]] = i_cap_f[k]
        diff_init_eqs[dq_t[k]] = i_cap_t[k]

    templ.block.diff_init_eqs = diff_init_eqs

    return templ
