# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""UPC-style grid-forming VSC EMT controller with external electrical filter.

This template deliberately does not contain the converter-side or grid-side
filter differential equations. Those electrical equations must be represented by
regular EMT network elements (lines/shunts) between the converter, filter, and
grid buses. The converter itself is a controlled Norton voltage source at the
converter AC bus.
"""

from __future__ import annotations

from typing import Any, List
import math
import numpy as np

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Utils.Symbolic.block import Block, VarPowerFlowReferenceType
from VeraGridEngine.Utils.Symbolic.block_helpers import tf_to_block
from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowReferenceType


def _park_transform_block(vf: VarFactory, x_abc: List[Any], theta: Any, name: str) -> tuple[Block, tuple[Any, Any]]:
    x_a, x_b, x_c = x_abc
    x_d = vf.add_var(f"{name}_d")
    x_q = vf.add_var(f"{name}_q")
    sqrt3 = vf.add_const(np.sqrt(3.0))
    one_third = vf.add_const(1.0 / 3.0)

    block = Block(
        algebraic_eqs=[
            x_d - one_third * (
                vf.add_const(2.0) * sym.cos(theta) * x_a
                + (-sym.cos(theta) - sqrt3 * sym.sin(theta)) * x_b
                + (-sym.cos(theta) + sqrt3 * sym.sin(theta)) * x_c
            ),
            x_q - one_third * (
                vf.add_const(2.0) * sym.sin(theta) * x_a
                + (-sym.sin(theta) + sqrt3 * sym.cos(theta)) * x_b
                + (-sym.sin(theta) - sqrt3 * sym.cos(theta)) * x_c
            ),
        ],
        algebraic_vars=[x_d, x_q],
    )
    return block, (x_d, x_q)


def _inverse_park_voltage(vf: VarFactory, v_d: Any, v_q: Any, theta: Any) -> tuple[Any, Any, Any]:
    sqrt3 = vf.add_const(np.sqrt(3.0))
    half = vf.add_const(0.5)
    two = vf.add_const(2.0)
    v_a = v_d * sym.cos(theta) + v_q * sym.sin(theta)
    v_b = ((-half * v_d - (sqrt3 / two) * v_q) * sym.cos(theta)
           + ((sqrt3 / two) * v_d - half * v_q) * sym.sin(theta))
    v_c = ((-half * v_d + (sqrt3 / two) * v_q) * sym.cos(theta)
           + ((-sqrt3 / two) * v_d - half * v_q) * sym.sin(theta))
    return v_a, v_b, v_c


def get_vsc_gfm_upc_emt_template(vf: VarFactory, name: str = "GFM_UPC_EMT") -> EmtModelTemplate:
    """Build an EMT GFM controller that leaves filter equations to EMT lines."""
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.VscDevice
    templ.name = name

    # Converter bus voltage, filter bus voltage, grid bus voltage.
    vc_a = vf.add_var(f"vc_A_{name}", reference=VarPowerFlowReferenceType.v_A)
    vc_b = vf.add_var(f"vc_B_{name}", reference=VarPowerFlowReferenceType.v_B)
    vc_c = vf.add_var(f"vc_C_{name}", reference=VarPowerFlowReferenceType.v_C)
    vf_a = vf.add_var(f"vf_A_{name}")
    vf_b = vf.add_var(f"vf_B_{name}")
    vf_c = vf.add_var(f"vf_C_{name}")
    vg_a = vf.add_var(f"vg_A_{name}")
    vg_b = vf.add_var(f"vg_B_{name}")
    vg_c = vf.add_var(f"vg_C_{name}")

    # Measured line currents: converter-to-filter and filter-to-grid.
    ic_a = vf.add_var(f"ic_A_{name}")
    ic_b = vf.add_var(f"ic_B_{name}")
    ic_c = vf.add_var(f"ic_C_{name}")
    ig_a = vf.add_var(f"ig_A_{name}")
    ig_b = vf.add_var(f"ig_B_{name}")
    ig_c = vf.add_var(f"ig_C_{name}")
    v_dc = vf.add_var(f"v_dc_{name}", reference=VarPowerFlowReferenceType.Vdc)

    i_a = vf.add_var(f"i_A_{name}", reference=VarPowerFlowReferenceType.i_A)
    i_b = vf.add_var(f"i_B_{name}", reference=VarPowerFlowReferenceType.i_B)
    i_c = vf.add_var(f"i_C_{name}", reference=VarPowerFlowReferenceType.i_C)
    i_dc = vf.add_var(f"i_dc_{name}", reference=VarPowerFlowReferenceType.Idc)

    theta = vf.add_var(f"theta_{name}")
    d_theta = vf.add_diff_var(f"d_theta_{name}", base_var=theta)

    omega_base = vf.add_var(f"omega_base_{name}")
    omega_ref = vf.add_var(f"omega_ref_{name}")
    omega = vf.add_var(f"omega_{name}")
    V = vf.add_var(f"V_{name}")
    V_ref = vf.add_var(f"V_ref_{name}")
    P_ref = vf.add_var(f"P_ref_{name}")
    Q_ref = vf.add_var(f"Q_ref_{name}")
    Kdp = vf.add_var(f"Kdp_{name}")
    Kdq = vf.add_var(f"Kdq_{name}")
    Kp_icl = vf.add_var(f"Kp_icl_{name}")
    Ki_icl = vf.add_var(f"Ki_icl_{name}")
    tau_P = vf.add_var(f"tau_P_{name}")
    tau_Q = vf.add_var(f"tau_Q_{name}")
    Lf = vf.add_var(f"Lf_{name}")
    Cf = vf.add_var(f"Cf_{name}")
    Rcap = vf.add_var(f"Rcap_{name}")
    I_max = vf.add_var(f"I_max_{name}")
    g_src = vf.add_var(f"g_src_{name}")

    # PF bridge references.
    Vpk_ref = vf.add_var(f"Vpk_ref_{name}")
    phi_v_ref = vf.add_var(f"phi_v_ref_{name}")
    Ipk_ref = vf.add_var(f"Ipk_ref_{name}")
    phi_ref = vf.add_var(f"phi_ref_{name}")

    Pt_vsc = vf.add_var(f"Pt_vsc_{name}")
    Qt_vsc = vf.add_var(f"Qt_vsc_{name}")
    Pf_vsc = vf.add_var(f"Pf_vsc_{name}")
    Qf_vsc = vf.add_var(f"Qf_vsc_{name}")
    P = vf.add_var(f"P_{name}")
    Q = vf.add_var(f"Q_{name}")
    P_conv = vf.add_var(f"P_conv_{name}")

    park_theta = vf.add_const(0.0) - theta
    park_vc, (vd_c, vq_c) = _park_transform_block(vf, [vc_a, vc_b, vc_c], park_theta, f"vc_{name}")
    park_vf, (vd_f, vq_f) = _park_transform_block(vf, [vf_a, vf_b, vf_c], park_theta, f"vf_{name}")
    park_vg, (vd_g, vq_g) = _park_transform_block(vf, [vg_a, vg_b, vg_c], park_theta, f"vg_{name}")
    park_ic, (id_c, iq_c) = _park_transform_block(vf, [ic_a, ic_b, ic_c], park_theta, f"ic_{name}")
    park_ig, (id_g, iq_g) = _park_transform_block(vf, [ig_a, ig_b, ig_c], park_theta, f"ig_{name}")

    block_P, P_lp = tf_to_block(vf, num=[vf.add_const(1.0)], den=[vf.add_const(1.0), tau_P], x=P, name=f"P_lp_{name}")
    block_Q, Q_lp = tf_to_block(vf, num=[vf.add_const(1.0)], den=[vf.add_const(1.0), tau_Q], x=Q, name=f"Q_lp_{name}")
    block_P.init_eqs = {P_lp: P}
    block_Q.init_eqs = {Q_lp: Q}

    vd_ref = vf.add_var(f"vd_ref_{name}")
    vq_ref = vf.add_var(f"vq_ref_{name}")
    block_vd, id_hat = tf_to_block(vf, num=[Ki_icl, Kp_icl], den=[0, 1], x=vd_ref - vd_f, name=f"vd_ctrl_{name}")
    block_vq, iq_hat = tf_to_block(vf, num=[Ki_icl, Kp_icl], den=[0, 1], x=vq_ref - vq_f, name=f"vq_ctrl_{name}")

    i_d_ref_raw = iq_hat + iq_g - Cf * omega * vq_f
    i_q_ref_raw = id_hat + id_g + Cf * omega * vd_f
    iq_for_id_lim = sym.max(iq_c, i_q_ref_raw)
    id_max = sym.sqrt(sym.max(I_max ** 2 - iq_for_id_lim ** 2, vf.add_const(1e-5)))
    id_ref = vf.add_var(f"id_ref_{name}")
    iq_ref = vf.add_var(f"iq_ref_{name}")

    vd_cmd = vf.add_var(f"vd_cmd_{name}")
    vq_cmd = vf.add_var(f"vq_cmd_{name}")
    block_id, vd_hat = tf_to_block(vf, num=[Ki_icl, Kp_icl], den=[0, 1], x=id_ref - id_c, name=f"id_ctrl_{name}")
    block_iq, vq_hat = tf_to_block(vf, num=[Ki_icl, Kp_icl], den=[0, 1], x=iq_ref - iq_c, name=f"iq_ctrl_{name}")
    vsrc_a, vsrc_b, vsrc_c = _inverse_park_voltage(vf, vd_cmd, vq_cmd, theta)

    half = vf.add_const(0.5)
    p_expr = half * (vq_g * iq_g + vd_g * id_g)
    q_expr = half * (vq_g * id_g - vd_g * iq_g)
    p_conv_expr = (vc_a * i_a + vc_b * i_b + vc_c * i_c) / vf.add_const(3.0)

    core = Block(
        state_eqs=[omega_base * omega],
        state_vars=[theta],
        diff_vars=[d_theta],
        algebraic_eqs=[
            P - p_expr,
            Q - q_expr,
            omega - (omega_ref - Kdp * (P_lp - P_ref)),
            V - (V_ref - Kdq * (Q_lp - Q_ref)),
            vd_ref - vf.add_const(0.0),
            vq_ref - V,
            id_ref - sym.hard_sat(i_d_ref_raw, -id_max, id_max),
            iq_ref - sym.hard_sat(i_q_ref_raw, -I_max, I_max),
            vd_cmd - (vd_hat + vd_f - Lf * omega * iq_c),
            vq_cmd - (vq_hat + vq_f + Lf * omega * id_c),
            i_a - g_src * (vsrc_a - vc_a),
            i_b - g_src * (vsrc_b - vc_b),
            i_c - g_src * (vsrc_c - vc_c),
            P_conv - p_conv_expr,
            i_dc * v_dc - P_conv,
            Pt_vsc + P,
            Qt_vsc + Q,
            Pf_vsc - P_conv,
            Qf_vsc - vf.add_const(0.0),
        ],
        algebraic_vars=[
            P, Q, omega, V, vd_ref, vq_ref, id_ref, iq_ref, vd_cmd, vq_cmd,
            i_a, i_b, i_c, i_dc, P_conv, Pt_vsc, Qt_vsc, Pf_vsc, Qf_vsc,
        ],
        event_dict={
            omega_ref: vf.add_const(1.0),
            Kdp: vf.add_const(0.005),
            Kdq: vf.add_const(0.005),
            Kp_icl: vf.add_const(1.0),
            Ki_icl: vf.add_const(20.0),
            tau_P: vf.add_const(0.10),
            tau_Q: vf.add_const(0.10),
            Lf: vf.add_const(0.15),
            Cf: vf.add_const(0.05),
            Rcap: vf.add_const(1e6),
            I_max: vf.add_const(1.2),
            g_src: vf.add_const(200.0),
            Vpk_ref: vf.add_const(None),
            phi_v_ref: vf.add_const(None),
            Ipk_ref: vf.add_const(None),
            phi_ref: vf.add_const(None),
            P_ref: P,
            Q_ref: Q,
            V_ref: vq_f,
        },
        init_eqs={
            theta: phi_v_ref - vf.add_const(math.pi),
            P: p_expr,
            Q: q_expr,
            P_lp: P,
            Q_lp: Q,
            omega: vf.add_const(1.0),
            V: vq_f,
            vd_ref: vf.add_const(0.0),
            vq_ref: V,
            id_ref: id_c,
            iq_ref: iq_c,
            vd_cmd: vd_c,
            vq_cmd: vq_c,
            P_conv: p_conv_expr,
            i_dc: p_conv_expr / v_dc,
            Pt_vsc: -P,
            Qt_vsc: -Q,
            Pf_vsc: P_conv,
            Qf_vsc: vf.add_const(0.0),
        },
        diff_init_eqs={d_theta: omega_base * omega},
        in_vars=[vc_a, vc_b, vc_c, vf_a, vf_b, vf_c, vg_a, vg_b, vg_c, ic_a, ic_b, ic_c, ig_a, ig_b, ig_c, v_dc],
        out_vars=[i_a, i_b, i_c, i_dc],
        external_mapping={
            VarPowerFlowReferenceType.v_A: vc_a,
            VarPowerFlowReferenceType.v_B: vc_b,
            VarPowerFlowReferenceType.v_C: vc_c,
            VarPowerFlowReferenceType.vt_A: vc_a,
            VarPowerFlowReferenceType.vt_B: vc_b,
            VarPowerFlowReferenceType.vt_C: vc_c,
            VarPowerFlowReferenceType.i_A: i_a,
            VarPowerFlowReferenceType.i_B: i_b,
            VarPowerFlowReferenceType.i_C: i_c,
            VarPowerFlowReferenceType.it_A: i_a,
            VarPowerFlowReferenceType.it_B: i_b,
            VarPowerFlowReferenceType.it_C: i_c,
            VarPowerFlowReferenceType.Vdc: v_dc,
            VarPowerFlowReferenceType.Vf_dc: v_dc,
            VarPowerFlowReferenceType.Idc: i_dc,
            VarPowerFlowReferenceType.If_dc: i_dc,
            VarPowerFlowReferenceType.Pt: Pt_vsc,
            VarPowerFlowReferenceType.Qt: Qt_vsc,
            VarPowerFlowReferenceType.Pf: Pf_vsc,
            VarPowerFlowReferenceType.Qf: Qf_vsc,
            VarPowerFlowReferenceType.P: P,
            VarPowerFlowReferenceType.Q: Q,
            VarPowerFlowReferenceType.Vpk: Vpk_ref,
            VarPowerFlowReferenceType.phi_v: phi_v_ref,
            VarPowerFlowReferenceType.Ipk: Ipk_ref,
            VarPowerFlowReferenceType.phi: phi_ref,
        },
        parameters={omega_base: vf.add_const(2.0 * math.pi * 50.0)},
        api_obj_mapping={
            ParamPowerFlowReferenceType.omega_base: omega_base,
        },
    )

    for child in (park_vc, park_vf, park_vg, park_ic, park_ig, block_P, block_Q, block_vd, block_vq, block_id, block_iq):
        core.add(child)
    core.name = name
    core.unify_blocks()

    templ.block = core
    return templ
