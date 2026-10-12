# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Detailed averaged EMT GFM VSC based on the Colib UPC control structure.

The model contains an LCL filter, active/reactive-power droops, voltage and
current PI loops, and balanced phase-domain Park/inverse-Park interfaces.
"""

import math
import numpy as np

import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.Utils.Symbolic.block import Block, VarPowerFlowReferenceType
from VeraGridEngine.enumerations import ConverterControlType, ParamPowerFlowReferenceType


def park_transform_block(vf, v_abc, theta, name: str):
    v_a, v_b, v_c = v_abc
    v_d = vf.add_var(f"vd_{name}")
    v_q = vf.add_var(f"vq_{name}")
    sqrt3 = vf.add_const(np.sqrt(3.0))
    c13 = vf.add_const(1.0 / 3.0)

    eqs = [
        v_d - c13 * (
            vf.add_const(2.0) * sym.cos(theta) * v_a
            + (-sym.cos(theta) - sqrt3 * sym.sin(theta)) * v_b
            + (-sym.cos(theta) + sqrt3 * sym.sin(theta)) * v_c
        ),
        v_q - c13 * (
            vf.add_const(2.0) * sym.sin(theta) * v_a
            + (-sym.sin(theta) + sqrt3 * sym.cos(theta)) * v_b
            + (-sym.sin(theta) - sqrt3 * sym.cos(theta)) * v_c
        ),
    ]
    return Block(algebraic_eqs=eqs, algebraic_vars=[v_d, v_q]), (v_d, v_q)


def inverse_park_currents_block(vf, i_d, i_q, theta, name: str):
    i_a = vf.add_var(f"i_A_{name}", reference=VarPowerFlowReferenceType.i_A)
    i_b = vf.add_var(f"i_B_{name}", reference=VarPowerFlowReferenceType.i_B)
    i_c = vf.add_var(f"i_C_{name}", reference=VarPowerFlowReferenceType.i_C)
    sqrt3 = vf.add_const(np.sqrt(3.0))
    half = vf.add_const(0.5)
    two = vf.add_const(2.0)

    eqs = [
        i_a - (i_d * sym.cos(theta) + i_q * sym.sin(theta)),
        i_b - (i_d * (-half * sym.cos(theta) - (sqrt3 / two) * sym.sin(theta))
               + i_q * (-half * sym.sin(theta) + (sqrt3 / two) * sym.cos(theta))),
        i_c - (i_d * (-half * sym.cos(theta) + (sqrt3 / two) * sym.sin(theta))
               + i_q * (-half * sym.sin(theta) - (sqrt3 / two) * sym.cos(theta))),
    ]
    return Block(algebraic_eqs=eqs, algebraic_vars=[i_a, i_b, i_c]), (i_a, i_b, i_c)


def inverse_park_values_block(vf, x_d, x_q, theta, name: str):
    x_a = vf.add_var(f"A_{name}")
    x_b = vf.add_var(f"B_{name}")
    x_c = vf.add_var(f"C_{name}")
    sqrt3 = vf.add_const(np.sqrt(3.0))
    half = vf.add_const(0.5)
    two = vf.add_const(2.0)

    eqs = [
        x_a - (x_d * sym.cos(theta) + x_q * sym.sin(theta)),
        x_b - (x_d * (-half * sym.cos(theta) - (sqrt3 / two) * sym.sin(theta))
               + x_q * (-half * sym.sin(theta) + (sqrt3 / two) * sym.cos(theta))),
        x_c - (x_d * (-half * sym.cos(theta) + (sqrt3 / two) * sym.sin(theta))
               + x_q * (-half * sym.sin(theta) - (sqrt3 / two) * sym.cos(theta))),
    ]
    return Block(algebraic_eqs=eqs, algebraic_vars=[x_a, x_b, x_c]), (x_a, x_b, x_c)


def build_emt_gfm_aggregated_model(
    vf,
    name: str = "gfm_agg_emt",
    control1: ConverterControlType = ConverterControlType.Pac,
    control2: ConverterControlType = ConverterControlType.Qac,
) -> Block:
    _ = control1
    _ = control2

    v_a = vf.add_var(f"v_A_{name}", reference=VarPowerFlowReferenceType.v_A)
    v_b = vf.add_var(f"v_B_{name}", reference=VarPowerFlowReferenceType.v_B)
    v_c = vf.add_var(f"v_C_{name}", reference=VarPowerFlowReferenceType.v_C)

    theta = vf.add_var(f"theta_{name}")
    omega = vf.add_var(f"omega_{name}")
    dtheta = vf.add_diff_var(f"dtheta_{name}", base_var=theta)

    pt = vf.add_var(f"Pt_vsc_{name}")
    qt = vf.add_var(f"Qt_vsc_{name}")
    pf = vf.add_var(f"Pf_vsc_{name}")
    qf = vf.add_var(f"Qf_vsc_{name}")
    d_v_a = vf.add_var(f"d_v_A_{name}")
    d_v_b = vf.add_var(f"d_v_B_{name}")
    d_v_c = vf.add_var(f"d_v_C_{name}")

    vd_g = vf.add_var(f"vd_g_{name}")
    vq_g = vf.add_var(f"vq_g_{name}")
    vd_f = vf.add_var(f"vd_f_{name}")
    vq_f = vf.add_var(f"vq_f_{name}")
    vd_c = vf.add_var(f"vd_c_{name}")
    vq_c = vf.add_var(f"vq_c_{name}")

    id_g = vf.add_var(f"id_g_{name}")
    iq_g = vf.add_var(f"iq_g_{name}")
    id_c = vf.add_var(f"id_c_{name}")
    iq_c = vf.add_var(f"iq_c_{name}")

    i_g_a = vf.add_var(f"i_g_A_{name}")
    i_g_b = vf.add_var(f"i_g_B_{name}")
    i_g_c = vf.add_var(f"i_g_C_{name}")
    i_c_a = vf.add_var(f"i_c_A_{name}")
    i_c_b = vf.add_var(f"i_c_B_{name}")
    i_c_c = vf.add_var(f"i_c_C_{name}")
    v_f_a = vf.add_var(f"v_f_A_{name}")
    v_f_b = vf.add_var(f"v_f_B_{name}")
    v_f_c = vf.add_var(f"v_f_C_{name}")
    d_i_g_a = vf.add_diff_var(f"d_i_g_A_{name}", base_var=i_g_a)
    d_i_g_b = vf.add_diff_var(f"d_i_g_B_{name}", base_var=i_g_b)
    d_i_g_c = vf.add_diff_var(f"d_i_g_C_{name}", base_var=i_g_c)
    d_i_c_a = vf.add_diff_var(f"d_i_c_A_{name}", base_var=i_c_a)
    d_i_c_b = vf.add_diff_var(f"d_i_c_B_{name}", base_var=i_c_b)
    d_i_c_c = vf.add_diff_var(f"d_i_c_C_{name}", base_var=i_c_c)
    d_v_f_a = vf.add_diff_var(f"d_v_f_A_{name}", base_var=v_f_a)
    d_v_f_b = vf.add_diff_var(f"d_v_f_B_{name}", base_var=v_f_b)
    d_v_f_c = vf.add_diff_var(f"d_v_f_C_{name}", base_var=v_f_c)

    i_a = vf.add_var(f"i_A_{name}", reference=VarPowerFlowReferenceType.i_A)
    i_b = vf.add_var(f"i_B_{name}", reference=VarPowerFlowReferenceType.i_B)
    i_c = vf.add_var(f"i_C_{name}", reference=VarPowerFlowReferenceType.i_C)

    p = vf.add_var(f"P_{name}")
    q = vf.add_var(f"Q_{name}")
    p_a = vf.add_var(f"P_A_{name}")
    p_b = vf.add_var(f"P_B_{name}")
    p_c = vf.add_var(f"P_C_{name}")
    q_a = vf.add_var(f"Q_A_{name}")
    q_b = vf.add_var(f"Q_B_{name}")
    q_c = vf.add_var(f"Q_C_{name}")
    p_ref = vf.add_var(f"P_ref_{name}")
    q_ref = vf.add_var(f"Q_ref_{name}")
    v_ref = vf.add_var(f"V_ref_{name}")
    v_mag = vf.add_var(f"V_{name}")
    vd_ref = vf.add_var(f"vd_ref_{name}")
    vq_ref = vf.add_var(f"vq_ref_{name}")

    id_ref = vf.add_var(f"id_ref_{name}")
    iq_ref = vf.add_var(f"iq_ref_{name}")
    id_ref_sat = vf.add_var(f"id_ref_sat_{name}")
    iq_ref_sat = vf.add_var(f"iq_ref_sat_{name}")
    vd_ctrl_out = vf.add_var(f"vd_ctrl_out_{name}")
    vq_ctrl_out = vf.add_var(f"vq_ctrl_out_{name}")
    vd_c_ref = vf.add_var(f"vd_c_ref_{name}")
    vq_c_ref = vf.add_var(f"vq_c_ref_{name}")

    p_lp = vf.add_var(f"y_p_lp_{name}")
    q_lp = vf.add_var(f"y_q_lp_{name}")
    z_vd = vf.add_var(f"z_vd_loop_{name}")
    z_vq = vf.add_var(f"z_vq_loop_{name}")
    z_id = vf.add_var(f"z_id_loop_{name}")
    z_iq = vf.add_var(f"z_iq_loop_{name}")

    d_p_lp = vf.add_diff_var(f"d_y_p_lp_{name}", base_var=p_lp)
    d_q_lp = vf.add_diff_var(f"d_y_q_lp_{name}", base_var=q_lp)
    d_z_vd = vf.add_diff_var(f"d_z_vd_loop_{name}", base_var=z_vd)
    d_z_vq = vf.add_diff_var(f"d_z_vq_loop_{name}", base_var=z_vq)
    d_z_id = vf.add_diff_var(f"d_z_id_loop_{name}", base_var=z_id)
    d_z_iq = vf.add_diff_var(f"d_z_iq_loop_{name}", base_var=z_iq)

    Rf = vf.add_var(f"Rf_{name}")
    Lf = vf.add_var(f"Lf_{name}")
    Rc = vf.add_var(f"Rc_{name}")
    Lc = vf.add_var(f"Lc_{name}")
    Cf = vf.add_var(f"Cf_{name}")
    Rcap = vf.add_var(f"Rcap_{name}")
    Kdp = vf.add_var(f"Kdp_{name}")
    Kdq = vf.add_var(f"Kdq_{name}")
    fn = vf.add_var(f"fn_{name}")
    omega_base = vf.add_var(f"omega_base_{name}")
    Kp_vcl = vf.add_var(f"Kp_vcl_{name}")
    Ki_vcl = vf.add_var(f"Ki_vcl_{name}")
    Kp_icl = vf.add_var(f"Kp_icl_{name}")
    Ki_icl = vf.add_var(f"Ki_icl_{name}")
    tau_p = vf.add_var(f"tau_P_{name}")
    tau_q = vf.add_var(f"tau_Q_{name}")
    i_max = vf.add_var(f"I_max_{name}")
    a0 = vf.add_var(f"a0_{name}")
    a1 = vf.add_var(f"a1_{name}")
    a2 = vf.add_var(f"a2_{name}")

    park_v_block, (vd_bus, vq_bus) = park_transform_block(vf, [v_a, v_b, v_c], theta, name=f"{name}_bus")
    park_ig_block, (id_g_park, iq_g_park) = park_transform_block(vf, [i_g_a, i_g_b, i_g_c], theta, name=f"{name}_ig")
    park_ic_block, (id_c_park, iq_c_park) = park_transform_block(vf, [i_c_a, i_c_b, i_c_c], theta, name=f"{name}_ic")
    park_vf_block, (vd_f_park, vq_f_park) = park_transform_block(vf, [v_f_a, v_f_b, v_f_c], theta, name=f"{name}_vf")
    inv_vc_block, (v_c_a, v_c_b, v_c_c) = inverse_park_values_block(vf, vd_c, vq_c, theta, name=f"v_c_{name}")

    eqs = [
        vd_g - vd_bus,
        vq_g - vq_bus,
        id_g - id_g_park,
        iq_g - iq_g_park,
        id_c - id_c_park,
        iq_c - iq_c_park,
        vd_f - vd_f_park,
        vq_f - vq_f_park,
        i_a - i_g_a,
        i_b - i_g_b,
        i_c - i_g_c,
        p_a - (v_a * i_a),
        p_b - (v_b * i_b),
        p_c - (v_c * i_c),
        q_a - ((v_b - v_c) * i_a),
        q_b - ((v_c - v_a) * i_b),
        q_c - ((v_a - v_b) * i_c),
        p - (p_a + p_b + p_c) / vf.add_const(3.0),
        q - (q_a + q_b + q_c) / vf.add_const(3.0 * np.sqrt(3.0)),
    ]

    eqs += [
        omega - (vf.add_const(1.0) - Kdp * (p_lp - p_ref)),
        v_mag - (v_ref - Kdq * (q_lp - q_ref)),
        vd_ref - vf.add_const(0.0),
        vq_ref - v_mag,
    ]

    id_hat = Kp_vcl * (vd_ref - vd_f) + Ki_vcl * z_vd
    iq_hat = Kp_vcl * (vq_ref - vq_f) + Ki_vcl * z_vq

    id_raw = id_hat + id_g + Cf * omega * vq_f
    iq_raw = iq_hat + iq_g - Cf * omega * vd_f
    eqs += [
        id_ref_sat - id_raw,
        iq_ref_sat - iq_raw,
        id_ref - id_ref_sat,
        iq_ref - iq_ref_sat,
    ]

    vd_hat = vd_ctrl_out
    vq_hat = vq_ctrl_out

    eqs += [
        vd_ctrl_out - (Kp_icl * (id_ref - id_c) + Ki_icl * z_id),
        vq_ctrl_out - (Kp_icl * (iq_ref - iq_c) + Ki_icl * z_iq),
        vd_c_ref - (vd_hat + vd_f + Lf * omega * iq_c),
        vq_c_ref - (vq_hat + vq_f - Lf * omega * id_c),
        vd_c - vd_c_ref,
        vq_c - vq_c_ref,
        pt + p,
        qt + q,
    ]

    im = sym.sqrt(id_c ** 2 + iq_c ** 2 + vf.add_const(1e-5))
    p_loss = a0 + a1 * im + a2 * im ** 2
    p_conv = vf.add_const(0.5) * (vq_c * iq_c + vd_c * id_c)
    sqrt3 = vf.add_const(np.sqrt(3.0))
    eqs += [
        pf + p_conv - p_loss,
        qf - vf.add_const(0.0),
        d_v_a - omega_base * (v_c - v_b) / sqrt3,
        d_v_b - omega_base * (v_a - v_c) / sqrt3,
        d_v_c - omega_base * (v_b - v_a) / sqrt3,
    ]

    model = Block(
        state_eqs=[
            omega_base * omega,
            (p - p_lp) / tau_p,
            (q - q_lp) / tau_q,
            vd_ref - vd_f,
            vq_ref - vq_f,
            id_ref - id_c,
            iq_ref - iq_c,
            omega_base * (v_f_a - v_a - Rc * i_g_a) / Lc,
            omega_base * (v_f_b - v_b - Rc * i_g_b) / Lc,
            omega_base * (v_f_c - v_c - Rc * i_g_c) / Lc,
            omega_base * (v_c_a - v_f_a - Rf * i_c_a) / Lf,
            omega_base * (v_c_b - v_f_b - Rf * i_c_b) / Lf,
            omega_base * (v_c_c - v_f_c - Rf * i_c_c) / Lf,
            omega_base * (i_c_a - i_g_a - v_f_a / Rcap) / Cf,
            omega_base * (i_c_b - i_g_b - v_f_b / Rcap) / Cf,
            omega_base * (i_c_c - i_g_c - v_f_c / Rcap) / Cf,
        ],
        state_vars=[theta, p_lp, q_lp, z_vd, z_vq, z_id, z_iq, i_g_a, i_g_b, i_g_c, i_c_a, i_c_b, i_c_c, v_f_a, v_f_b, v_f_c],
        algebraic_eqs=eqs,
        algebraic_vars=[
            pt, qt, pf, qf, d_v_a, d_v_b, d_v_c, p, q, omega, v_mag,
            p_a, p_b, p_c, q_a, q_b, q_c,
            vd_ref, vq_ref, vd_g, vq_g, vd_f, vq_f, vd_c, vq_c,
            id_g, iq_g, id_c, iq_c, id_ref, iq_ref, id_ref_sat, iq_ref_sat,
            vd_ctrl_out, vq_ctrl_out, vd_c_ref, vq_c_ref, i_a, i_b, i_c,
        ],
        diff_vars=[dtheta, d_p_lp, d_q_lp, d_z_vd, d_z_vq, d_z_id, d_z_iq, d_i_g_a, d_i_g_b, d_i_g_c, d_i_c_a, d_i_c_b, d_i_c_c, d_v_f_a, d_v_f_b, d_v_f_c],
        event_dict={
            Rf: vf.add_const(0.02), Lf: vf.add_const(0.15), Rc: vf.add_const(0.01), Lc: vf.add_const(0.1),
            Cf: vf.add_const(0.05), Rcap: vf.add_const(1e6), Kdp: vf.add_const(0.1), Kdq: vf.add_const(0.005),
            Kp_vcl: vf.add_const(0.00075), Ki_vcl: vf.add_const(0.2),
            Kp_icl: vf.add_const(0.00075), Ki_icl: vf.add_const(0.2), tau_p: vf.add_const(0.01),
            tau_q: vf.add_const(0.01), i_max: vf.add_const(1.2),
            p_ref: vf.add_const(None), q_ref: vf.add_const(None), v_ref: vf.add_const(None),
        },
        parameters={
            fn: vf.add_const(50.0),
            omega_base: vf.add_const(2.0 * math.pi * 50.0),
            a0: vf.add_const(0.0),
            a1: vf.add_const(0.0),
            a2: vf.add_const(0.0),
        },
        init_eqs={
            theta: vf.add_const(0.0), omega: vf.add_const(1.0),
            p: -pt, q: -qt, p_ref: p, q_ref: q,
            p_lp: p, q_lp: q,
            z_vd: vf.add_const(0.0), z_vq: vf.add_const(0.0),
            z_id: vf.add_const(0.0), z_iq: vf.add_const(0.0),
            p_a: vf.add_const(0.0), p_b: vf.add_const(0.0), p_c: vf.add_const(0.0),
            q_a: vf.add_const(0.0), q_b: vf.add_const(0.0), q_c: vf.add_const(0.0),
            v_ref: vf.add_const(1.0), v_mag: vf.add_const(1.0),
            vd_ref: vf.add_const(0.0), vq_ref: v_mag,
            id_g: vf.add_const(0.0), iq_g: vf.add_const(0.0),
            vd_g: vd_bus, vq_g: vq_bus,
            vd_f: vd_g, vq_f: vq_g,
            id_c: id_g, iq_c: iq_g,
            id_ref: id_c, iq_ref: iq_c,
            id_ref_sat: id_c, iq_ref_sat: iq_c,
            vd_ctrl_out: vf.add_const(0.0), vq_ctrl_out: vf.add_const(0.0),
            vd_c_ref: vd_f, vq_c_ref: vq_f,
            vd_c: vd_c_ref, vq_c: vq_c_ref,
            pf: -p_conv + p_loss, qf: vf.add_const(0.0),
            d_v_a: omega_base * (v_c - v_b) / sqrt3,
            d_v_b: omega_base * (v_a - v_c) / sqrt3,
            d_v_c: omega_base * (v_b - v_a) / sqrt3,
        },
        in_vars=[v_a, v_b, v_c],
        out_vars=[i_a, i_b, i_c],
        external_mapping={
            VarPowerFlowReferenceType.v_A: v_a,
            VarPowerFlowReferenceType.v_B: v_b,
            VarPowerFlowReferenceType.v_C: v_c,
            VarPowerFlowReferenceType.i_A: i_a,
            VarPowerFlowReferenceType.i_B: i_b,
            VarPowerFlowReferenceType.i_C: i_c,
            VarPowerFlowReferenceType.Pt: pt,
            VarPowerFlowReferenceType.Qt: qt,
            VarPowerFlowReferenceType.Pf: pf,
            VarPowerFlowReferenceType.Qf: qf,
            VarPowerFlowReferenceType.P_A: p_a,
            VarPowerFlowReferenceType.Q_A: q_a,
            VarPowerFlowReferenceType.P_B: p_b,
            VarPowerFlowReferenceType.Q_B: q_b,
            VarPowerFlowReferenceType.P_C: p_c,
            VarPowerFlowReferenceType.Q_C: q_c,
            VarPowerFlowReferenceType.d_v_A: d_v_a,
            VarPowerFlowReferenceType.d_v_B: d_v_b,
            VarPowerFlowReferenceType.d_v_C: d_v_c,
        },
        api_obj_mapping={
            ParamPowerFlowReferenceType.freq: fn,
            ParamPowerFlowReferenceType.omega_base: omega_base,
            ParamPowerFlowReferenceType.alpha1: a0,
            ParamPowerFlowReferenceType.alpha2: a1,
            ParamPowerFlowReferenceType.alpha3: a2,
        },
    )

    model.add(park_v_block)
    model.add(park_ig_block)
    model.add(park_ic_block)
    model.add(park_vf_block)
    model.add(inv_vc_block)
    model.unify_blocks()
    return model
