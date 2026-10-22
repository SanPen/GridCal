# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import numpy as np

import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Emt.converter_emt_template import (
    _converter_control_type_code,
    _resolve_converter_control_reference_exprs,
)
from VeraGridEngine.Utils.Symbolic.block import VarPowerFlowReferenceType
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var
from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowReferenceType


def get_emt_ideal_converter_multilinear(
    vf: VarFactory,
    name: str = "ideal_converter_emt_ml",
) -> EmtModelTemplate:
    """
    Build one averaged EMT converter model using trig-transform states.

    This variant keeps the exact averaged converter equations from
    ``get_emt_ideal_converter`` and only replaces direct ``sin(theta)`` and
    ``cos(theta)`` occurrences with ``symbolic_ml.trig_transform`` variables.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.VscDevice
    templ.name = name
    templ.block.name = name

    v_A: Var = vf.add_var(name=f"v_A", reference=VarPowerFlowReferenceType.v_A)
    v_B: Var = vf.add_var(name=f"v_B", reference=VarPowerFlowReferenceType.v_B)
    v_C: Var = vf.add_var(name=f"v_C", reference=VarPowerFlowReferenceType.v_C)
    v_dc: Var = vf.add_var(name=f"v_dc", reference=VarPowerFlowReferenceType.Vdc)

    i_A: Var = vf.add_var(name=f"i_A", reference=VarPowerFlowReferenceType.i_A)
    i_B: Var = vf.add_var(name=f"i_B", reference=VarPowerFlowReferenceType.i_B)
    i_C: Var = vf.add_var(name=f"i_C", reference=VarPowerFlowReferenceType.i_C)
    i_dc: Var = vf.add_var(name=f"i_dc", reference=VarPowerFlowReferenceType.Idc)
    P: Var = vf.add_var(name=f"P", reference=VarPowerFlowReferenceType.P)
    Q: Var = vf.add_var(name=f"Q", reference=VarPowerFlowReferenceType.Q)

    theta: Var = vf.add_var(name=f"theta")
    d_theta: Var = vf.add_diff_var(name=f"d_theta", base_var=theta)

    P_ref: Var = vf.add_var(name=f"P_ref")
    Q_ref: Var = vf.add_var(name=f"Q_ref")
    Vdc_ref: Var = vf.add_var(name=f"Vdc_ref")
    P_loss: Var = vf.add_var(name=f"P_loss")
    P0: Var = vf.add_var(name=f"P0")
    omega_base: Var = vf.add_var(name=f"omega_base")
    sbase: Var = vf.add_var(name=f"sbase")
    control1: Var = vf.add_var(name=f"control1")
    control2: Var = vf.add_var(name=f"control2")
    control1_val: Var = vf.add_var(name=f"control1_val")
    control2_val: Var = vf.add_var(name=f"control2_val")
    phi_v: Var = vf.add_var(name=f"phi_v")
    Vpk: Var = vf.add_var(name=f"Vpk")
    Vdc_nom: Var = vf.add_var(name=f"Vdc_nom")

    p_ref_expr: Expr
    q_ref_expr: Expr
    vdc_ref_expr: Expr
    regulate_vdc: Expr
    regulate_q: Expr
    _unused_regulate_active: Expr
    p_ref_expr, q_ref_expr, vdc_ref_expr, regulate_vdc, regulate_q, _unused_regulate_active = _resolve_converter_control_reference_exprs(
        control1=control1,
        control2=control2,
        control1_val=control1_val,
        control2_val=control2_val,
        p0=P0,
        vdc_nom=Vdc_nom,
        sbase=sbase,
    )

    eps = vf.add_const(1e-10)
    c0 = vf.add_const(0.0)
    c_half = vf.add_const(0.5)
    c_two = vf.add_const(2.0)
    c_third = vf.add_const(1.0 / 3.0)
    c_sqrt3_over_two = vf.add_const(np.sqrt(3.0) / 2.0)
    i_d_cmd: Var = vf.add_var(name=f"i_d_cmd")
    i_q_cmd: Var = vf.add_var(name=f"i_q_cmd")

    u_cos: Var = vf.add_var(name=f"u_cos")
    u_sin: Var = vf.add_var(name=f"u_sin")
    d_u_cos_var: Var = vf.add_diff_var(name=f"d_u_cos", base_var=u_cos)
    d_u_sin_var: Var = vf.add_diff_var(name=f"d_u_sin", base_var=u_sin)
    P_dc_cmd = P_ref + vf.add_const(2.0) * (v_dc - Vdc_ref) * regulate_vdc
    Q_cmd = Q_ref * regulate_q
    P_dc_cmd_pu = P_dc_cmd / (sbase + eps)
    Q_cmd_pu = Q_cmd / (sbase + eps)
    P_ac_cmd_pu = P_dc_cmd_pu + P_loss / (sbase + eps)

    i_A_cmd = i_d_cmd * u_cos + i_q_cmd * u_sin
    i_B_cmd = ((-c_half * i_d_cmd - c_sqrt3_over_two * i_q_cmd) * u_cos
               + ((c_sqrt3_over_two * i_d_cmd) - c_half * i_q_cmd) * u_sin)
    i_C_cmd = ((-c_half * i_d_cmd + c_sqrt3_over_two * i_q_cmd) * u_cos
               + ((-c_sqrt3_over_two * i_d_cmd) - c_half * i_q_cmd) * u_sin)

    Q_init_pu = q_ref_expr * regulate_q / (sbase + eps)
    P_dc_init_pu = p_ref_expr / (sbase + eps)
    P_ac_init_pu = P_dc_init_pu + P_loss / (sbase + eps)
    # With v = Vpk*sin(theta), positive absorbed Q requires -cos(theta) current.
    i_d_init = -c_two * Q_init_pu / sym.max(Vpk, eps)
    i_q_init = c_two * P_ac_init_pu / sym.max(Vpk, eps)
    i_A_init = i_d_init * sym.cos(phi_v) + i_q_init * sym.sin(phi_v)
    i_B_init = ((-c_half * i_d_init - c_sqrt3_over_two * i_q_init) * sym.cos(phi_v)
                + ((c_sqrt3_over_two * i_d_init) - c_half * i_q_init) * sym.sin(phi_v))
    i_C_init = ((-c_half * i_d_init + c_sqrt3_over_two * i_q_init) * sym.cos(phi_v)
                + ((-c_sqrt3_over_two * i_d_init) - c_half * i_q_init) * sym.sin(phi_v))

    templ.block.state_eqs = [
        omega_base,
        -(omega_base * u_sin),
        omega_base * u_cos,
    ]
    templ.block.state_vars = [theta, u_cos, u_sin]
    templ.block.diff_vars = [d_theta, d_u_cos_var, d_u_sin_var]
    templ.block.algebraic_vars = [
        P_ref,
        Q_ref,
        Vdc_ref,
        i_A,
        i_B,
        i_C,
        i_dc,
        P,
        Q,
        i_d_cmd,
        i_q_cmd,
    ]
    templ.block.algebraic_eqs = [
        P_ref - p_ref_expr,
        Q_ref - q_ref_expr,
        Vdc_ref - vdc_ref_expr,
        i_d_cmd + c_two * Q_cmd_pu / sym.max(Vpk, eps),
        i_q_cmd - c_two * P_ac_cmd_pu / sym.max(Vpk, eps),
        i_A - i_A_cmd,
        i_B - i_B_cmd,
        i_C - i_C_cmd,
        v_dc * i_dc + P_dc_cmd_pu,
        P - c_third * (v_A * i_A + v_B * i_B + v_C * i_C),
        Q - c_third * (1 / np.sqrt(3.0)) * ((v_A - v_B) * i_C + (v_B - v_C) * i_A + (v_C - v_A) * i_B),
    ]

    templ.block.init_eqs = {
        theta: phi_v,
        i_A: i_A_init,
        i_B: i_B_init,
        i_C: i_C_init,
        u_cos: sym.cos(phi_v),
        u_sin: sym.sin(phi_v),
        i_d_cmd: i_d_init,
        i_q_cmd: i_q_init,
        i_dc: -P_dc_init_pu / sym.max(Vdc_ref, eps),
        P_ref: p_ref_expr,
        Q_ref: q_ref_expr,
        Vdc_ref: vdc_ref_expr,
        P: P_ac_init_pu,
        Q: Q_init_pu,
    }
    templ.block.diff_init_eqs = {
        d_theta: omega_base,
        d_u_cos_var: -(omega_base * u_sin),
        d_u_sin_var: omega_base * u_cos,
    }

    templ.block.in_vars = [v_A, v_B, v_C, v_dc]
    templ.block.out_vars = [i_A, i_B, i_C, i_dc]
    templ.block.children = []
    templ.block.event_dict.update({
        P_loss: vf.add_const(0.0),
        P0: vf.add_const(0.0),
        phi_v: vf.add_const(0.0),
        Vpk: vf.add_const(np.sqrt(2.0)),
        Vdc_nom: vf.add_const(1.0),
    })
    templ.block.parameters[omega_base] = vf.add_const(2.0 * np.pi * 50.0)
    templ.block.parameters[sbase] = vf.add_const(1.0)
    templ.block.event_dict[control1] = vf.add_const(float(_converter_control_type_code(None)))
    templ.block.event_dict[control2] = vf.add_const(float(_converter_control_type_code(None)))
    templ.block.event_dict[control1_val] = vf.add_const(0.0)
    templ.block.event_dict[control2_val] = vf.add_const(0.0)

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: v_A,
        VarPowerFlowReferenceType.v_B: v_B,
        VarPowerFlowReferenceType.v_C: v_C,
        VarPowerFlowReferenceType.Vdc: v_dc,
        # VSC branches connect the DC from-terminal to the AC to-terminal.
        VarPowerFlowReferenceType.Vf_dc: v_dc,
        VarPowerFlowReferenceType.vt_A: v_A,
        VarPowerFlowReferenceType.vt_B: v_B,
        VarPowerFlowReferenceType.vt_C: v_C,
        VarPowerFlowReferenceType.If_dc: i_dc,
        VarPowerFlowReferenceType.it_A: i_A,
        VarPowerFlowReferenceType.it_B: i_B,
        VarPowerFlowReferenceType.it_C: i_C,
        VarPowerFlowReferenceType.i_A: i_A,
        VarPowerFlowReferenceType.i_B: i_B,
        VarPowerFlowReferenceType.i_C: i_C,
        VarPowerFlowReferenceType.Idc: i_dc,
        VarPowerFlowReferenceType.P: P,
        VarPowerFlowReferenceType.Q: Q,
        VarPowerFlowReferenceType.phi_v: phi_v,
        VarPowerFlowReferenceType.Vpk: Vpk,
    }

    templ.block.api_obj_mapping = {
        ParamPowerFlowReferenceType.Sbase: sbase,
        # Voltage control starts from the active transfer solved by power flow.
        ParamPowerFlowReferenceType.P0: P0,
        ParamPowerFlowReferenceType.omega_base: omega_base,
        ParamPowerFlowReferenceType.converter_control_mode_1: control1,
        ParamPowerFlowReferenceType.converter_control_mode_2: control2,
        ParamPowerFlowReferenceType.converter_control_target_1: control1_val,
        ParamPowerFlowReferenceType.converter_control_target_2: control2_val,
    }

    return templ
