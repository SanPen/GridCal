#!/usr/bin/env python3

import math
import numpy as np

import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.Utils.Symbolic.block import Block, VarPowerFlowReferenceType
from VeraGridEngine.enumerations import ConverterControlType, ParamPowerFlowReferenceType


def park_transform_block(vf, v_abc, theta, name: str):
    v_a, v_b, v_c = v_abc
    v_d = vf.add_var(f"vd")
    v_q = vf.add_var(f"vq")
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
    i_a = vf.add_var(f"i_A", reference=VarPowerFlowReferenceType.i_A)
    i_b = vf.add_var(f"i_B", reference=VarPowerFlowReferenceType.i_B)
    i_c = vf.add_var(f"i_C", reference=VarPowerFlowReferenceType.i_C)
    sqrt3 = vf.add_const(np.sqrt(3.0))
    half = vf.add_const(0.5)
    two = vf.add_const(2.0)

    eqs = [
        i_a - (i_d * sym.cos(theta) + i_q * sym.sin(theta)),
        i_b - ((-half * i_d - (sqrt3 / two) * i_q) * sym.cos(theta)
               + ((sqrt3 / two) * i_d - half * i_q) * sym.sin(theta)),
        i_c - ((-half * i_d + (sqrt3 / two) * i_q) * sym.cos(theta)
               + ((-sqrt3 / two) * i_d - half * i_q) * sym.sin(theta)),
    ]
    return Block(algebraic_eqs=eqs, algebraic_vars=[i_a, i_b, i_c]), (i_a, i_b, i_c)


def build_emt_gfm_aggregated_model(
    vf,
    name: str = "gfm_agg_emt",
    control1: ConverterControlType = ConverterControlType.Pac,
    control2: ConverterControlType = ConverterControlType.Qac,
) -> Block:
    _ = control1
    _ = control2

    v_a = vf.add_var(f"v_A", reference=VarPowerFlowReferenceType.v_A)
    v_b = vf.add_var(f"v_B", reference=VarPowerFlowReferenceType.v_B)
    v_c = vf.add_var(f"v_C", reference=VarPowerFlowReferenceType.v_C)

    theta = vf.add_var(f"theta")
    omega = vf.add_var(f"omega")
    dtheta = vf.add_diff_var(f"dtheta", base_var=theta)

    pt = vf.add_var(f"Pt_vsc")
    qt = vf.add_var(f"Qt_vsc")
    pf = vf.add_var(f"Pf_vsc")
    qf = vf.add_var(f"Qf_vsc")
    d_v_a = vf.add_var(f"d_v_A")
    d_v_b = vf.add_var(f"d_v_B")
    d_v_c = vf.add_var(f"d_v_C")

    vd_g = vf.add_var(f"vd_g")
    vq_g = vf.add_var(f"vq_g")
    vd_f = vf.add_var(f"vd_f")
    vq_f = vf.add_var(f"vq_f")
    vd_c = vf.add_var(f"vd_c")
    vq_c = vf.add_var(f"vq_c")

    id_g = vf.add_var(f"id_g")
    iq_g = vf.add_var(f"iq_g")
    id_c = vf.add_var(f"id_c")
    iq_c = vf.add_var(f"iq_c")

    p = vf.add_var(f"P")
    q = vf.add_var(f"Q")
    p_a = vf.add_var(f"P_A")
    p_b = vf.add_var(f"P_B")
    p_c = vf.add_var(f"P_C")
    q_a = vf.add_var(f"Q_A")
    q_b = vf.add_var(f"Q_B")
    q_c = vf.add_var(f"Q_C")
    p_ref = vf.add_var(f"P_ref")
    q_ref = vf.add_var(f"Q_ref")
    v_ref = vf.add_var(f"V_ref")
    v_mag = vf.add_var(f"V")
    vd_ref = vf.add_var(f"vd_ref")
    vq_ref = vf.add_var(f"vq_ref")

    id_ref = vf.add_var(f"id_ref")
    iq_ref = vf.add_var(f"iq_ref")
    id_ref_sat = vf.add_var(f"id_ref_sat")
    iq_ref_sat = vf.add_var(f"iq_ref_sat")
    vd_ctrl_out = vf.add_var(f"vd_ctrl_out")
    vq_ctrl_out = vf.add_var(f"vq_ctrl_out")
    vd_c_ref = vf.add_var(f"vd_c_ref")
    vq_c_ref = vf.add_var(f"vq_c_ref")

    p_lp = vf.add_var(f"y_p_lp")
    q_lp = vf.add_var(f"y_q_lp")
    z_vd = vf.add_var(f"z_vd_loop")
    z_vq = vf.add_var(f"z_vq_loop")
    z_id = vf.add_var(f"z_id_loop")
    z_iq = vf.add_var(f"z_iq_loop")

    d_p_lp = vf.add_diff_var(f"d_y_p_lp", base_var=p_lp)
    d_q_lp = vf.add_diff_var(f"d_y_q_lp", base_var=q_lp)
    d_z_vd = vf.add_diff_var(f"d_z_vd_loop", base_var=z_vd)
    d_z_vq = vf.add_diff_var(f"d_z_vq_loop", base_var=z_vq)
    d_z_id = vf.add_diff_var(f"d_z_id_loop", base_var=z_id)
    d_z_iq = vf.add_diff_var(f"d_z_iq_loop", base_var=z_iq)

    Rf = vf.add_var(f"Rf")
    Lf = vf.add_var(f"Lf")
    Rc = vf.add_var(f"Rc")
    Lc = vf.add_var(f"Lc")
    Cf = vf.add_var(f"Cf")
    Rcap = vf.add_var(f"Rcap")
    Kdp = vf.add_var(f"Kdp")
    Kdq = vf.add_var(f"Kdq")
    fn = vf.add_var(f"fn")
    omega_base = vf.add_var(f"omega_base")
    Kp = vf.add_var(f"Kp_icl")
    Ki = vf.add_var(f"Ki_icl")
    tau_p = vf.add_var(f"tau_P")
    tau_q = vf.add_var(f"tau_Q")
    i_max = vf.add_var(f"I_max")
    a0 = vf.add_var(f"a0")
    a1 = vf.add_var(f"a1")
    a2 = vf.add_var(f"a2")

    park_v_block, (vd_bus, vq_bus) = park_transform_block(vf, [v_a, v_b, v_c], theta, name=f"{name}_bus")
    inv_i_block, (i_a, i_b, i_c) = inverse_park_currents_block(vf, id_g, iq_g, theta, name=name)

    eqs = [
        vd_g - vd_bus,
        vq_g - vq_bus,
        vd_f - vd_g - (Rc * id_g - omega * Lc * iq_g),
        vq_f - vq_g - (Rc * iq_g + omega * Lc * id_g),
        vd_c - vd_f - (Rf * id_c - omega * Lf * iq_c),
        vq_c - vq_f - (Rf * iq_c + omega * Lf * id_c),
        iq_c - iq_g - (-Cf * omega * vq_f + vd_f / Rcap),
        id_c - id_g - (Cf * omega * vd_f + vq_f / Rcap),
        p_a - (v_a * i_a),
        p_b - (v_b * i_b),
        p_c - (v_c * i_c),
        q_a - (vd_g * iq_g),
        q_b - (vf.add_const(-0.5) * vd_g * iq_g + vf.add_const(np.sqrt(3.0) / 2.0) * vq_g * iq_g),
        q_c - (vf.add_const(-0.5) * vd_g * iq_g - vf.add_const(np.sqrt(3.0) / 2.0) * vq_g * iq_g),
        p - (p_a + p_b + p_c),
        q - (q_a + q_b + q_c),
    ]

    eqs += [
        omega - (vf.add_const(1.0) - Kdp * (p_lp - p_ref)),
        v_mag - (v_ref - Kdq * (q_lp - q_ref)),
        vd_ref - vf.add_const(0.0),
        vq_ref - v_mag,
    ]

    id_hat = Kp * (vd_ref - vd_f) + Ki * z_vd
    iq_hat = Kp * (vq_ref - vq_f) + Ki * z_vq

    id_raw = iq_hat + iq_g - Cf * omega * vq_f
    iq_raw = id_hat + id_g + Cf * omega * vd_f
    iq_for_lim = sym.max(iq_c, iq_raw)
    id_lim = sym.sqrt(sym.max(i_max ** 2 - iq_for_lim ** 2, vf.add_const(1e-5)))

    eqs += [
        id_ref_sat - sym.hard_sat(id_raw, -id_lim, id_lim),
        iq_ref_sat - sym.hard_sat(iq_raw, -i_max, i_max),
        id_ref - id_ref_sat,
        iq_ref - iq_ref_sat,
    ]

    vd_hat = vd_ctrl_out
    vq_hat = vq_ctrl_out

    eqs += [
        vd_ctrl_out - (Kp * (id_ref - id_c) + Ki * z_id),
        vq_ctrl_out - (Kp * (iq_ref - iq_c) + Ki * z_iq),
        vd_c_ref - (vd_hat + vd_f - Lf * omega * iq_c),
        vq_c_ref - (vq_hat + vq_f + Lf * omega * id_c),
        vd_c - vd_c_ref,
        vq_c - vq_c_ref,
        pt + p,
        qt + q,
    ]

    im = sym.sqrt(id_c ** 2 + iq_c ** 2 + vf.add_const(1e-5))
    p_loss = a0 + a1 * im + a2 * im ** 2
    p_conv = vf.add_const(1.5) * (vq_c * iq_c + vd_c * id_c)
    eqs += [
        pf + p_conv - p_loss,
        qf - vf.add_const(0.0),
        d_v_a - vf.add_const(0.0),
        d_v_b - vf.add_const(0.0),
        d_v_c - vf.add_const(0.0),
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
        ],
        state_vars=[theta, p_lp, q_lp, z_vd, z_vq, z_id, z_iq],
        algebraic_eqs=eqs,
        algebraic_vars=[
            pt, qt, pf, qf, d_v_a, d_v_b, d_v_c, p, q, omega, v_mag,
            p_a, p_b, p_c, q_a, q_b, q_c,
            vd_ref, vq_ref, vd_g, vq_g, vd_f, vq_f, vd_c, vq_c,
            id_g, iq_g, id_c, iq_c, id_ref, iq_ref, id_ref_sat, iq_ref_sat,
            vd_ctrl_out, vq_ctrl_out, vd_c_ref, vq_c_ref,
        ],
        diff_vars=[dtheta, d_p_lp, d_q_lp, d_z_vd, d_z_vq, d_z_id, d_z_iq],
        event_dict={
            Rf: vf.add_const(0.02), Lf: vf.add_const(0.15), Rc: vf.add_const(0.01), Lc: vf.add_const(0.1),
            Cf: vf.add_const(0.05), Rcap: vf.add_const(1e6), Kdp: vf.add_const(0.05), Kdq: vf.add_const(0.05),
            Kp: vf.add_const(0.05), Ki: vf.add_const(50.0), tau_p: vf.add_const(0.01),
            tau_q: vf.add_const(0.01), i_max: vf.add_const(1.2),
            p_ref: p, q_ref: q, v_ref: vf.add_const(1.0),
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
            p: -pt, q: -qt,
            p_lp: p, q_lp: q,
            z_vd: vf.add_const(0.0), z_vq: vf.add_const(0.0),
            z_id: vf.add_const(0.0), z_iq: vf.add_const(0.0),
            p_a: vf.add_const(0.0), p_b: vf.add_const(0.0), p_c: vf.add_const(0.0),
            q_a: vf.add_const(0.0), q_b: vf.add_const(0.0), q_c: vf.add_const(0.0),
            v_mag: vf.add_const(1.0),
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
            d_v_a: vf.add_const(0.0), d_v_b: vf.add_const(0.0), d_v_c: vf.add_const(0.0),
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
    model.add(inv_i_block)
    model.unify_blocks()
    return model
