#!/usr/bin/env python3

import math
from VeraGridEngine.enumerations import ParamPowerFlowReferenceType
import numpy as np

import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.Utils.Symbolic.block import Block, VarPowerFlowReferenceType
from VeraGridEngine.Utils.Symbolic.block_helpers import tf_to_block


def park_transform_block(vfactory, v_abc, theta, name: str = ""):
    v_a, v_b, v_c = v_abc
    x_d = vfactory.add_var(f"{name}_d")
    x_q = vfactory.add_var(f"{name}_q")

    algebraic_eqs = [
        x_d - (vfactory.add_const(1 / 3) * (
            (vfactory.add_const(2) * sym.cos(theta) * v_a)
            + (-sym.cos(theta) - vfactory.add_const(np.sqrt(3)) * sym.sin(theta)) * v_b
            + (-sym.cos(theta) + vfactory.add_const(np.sqrt(3)) * sym.sin(theta)) * v_c
        )),
        x_q - (vfactory.add_const(1 / 3) * (
            (vfactory.add_const(2) * sym.sin(theta) * v_a)
            + (-sym.sin(theta) + vfactory.add_const(np.sqrt(3)) * sym.cos(theta)) * v_b
            + (-sym.sin(theta) - vfactory.add_const(np.sqrt(3)) * sym.cos(theta)) * v_c
        )),
    ]
    return Block(algebraic_eqs=algebraic_eqs, algebraic_vars=[x_d, x_q]), (x_d, x_q)


def inverse_park_currents_block(vfactory, i_d, i_q, theta):
    i_a = vfactory.add_var("i_A_gfm_emt", reference=VarPowerFlowReferenceType.i_A)
    i_b = vfactory.add_var("i_B_gfm_emt", reference=VarPowerFlowReferenceType.i_B)
    i_c = vfactory.add_var("i_C_gfm_emt", reference=VarPowerFlowReferenceType.i_C)
    sqrt3 = vfactory.add_const(np.sqrt(3))
    half = vfactory.add_const(0.5)
    two = vfactory.add_const(2.0)

    eqs = [
        i_a - (i_d * sym.cos(theta) + i_q * sym.sin(theta)),
        i_b - ((-half * i_d - (sqrt3 / two) * i_q) * sym.cos(theta)
               + ((sqrt3 / two) * i_d - half * i_q) * sym.sin(theta)),
        i_c - ((-half * i_d + (sqrt3 / two) * i_q) * sym.cos(theta)
               + ((-sqrt3 / two) * i_d - half * i_q) * sym.sin(theta)),
    ]
    return Block(algebraic_eqs=eqs, algebraic_vars=[i_a, i_b, i_c]), (i_a, i_b, i_c)


def build_vsc_gfm_emt_park(vfactory, name: str = "gfm_emt"):
    v_a = vfactory.add_var(f"v_A", reference=VarPowerFlowReferenceType.v_A)
    v_b = vfactory.add_var(f"v_B", reference=VarPowerFlowReferenceType.v_B)
    v_c = vfactory.add_var(f"v_C", reference=VarPowerFlowReferenceType.v_C)
    v_dc = vfactory.add_var(f"Vdc", reference=VarPowerFlowReferenceType.Vdc)

    Pt_vsc = vfactory.add_var(f"Pt_vsc")
    Qt_vsc = vfactory.add_var(f"Qt_vsc")

    theta = vfactory.add_var(f"theta")
    omega = vfactory.add_var(f"omega")
    dt_theta = vfactory.add_diff_var(f"dt_theta", base_var=theta)

    Rf = vfactory.add_var(f"Rf")
    Lf = vfactory.add_var(f"Lf")
    Rc = vfactory.add_var(f"Rc")
    Lc = vfactory.add_var(f"Lc")
    Cf = vfactory.add_var(f"Cf")
    Rcap = vfactory.add_var(f"Rcap")
    Kdp = vfactory.add_var(f"Kdp")
    Kdq = vfactory.add_var(f"Kdq")
    fn = vfactory.add_var(f"fn")
    Kp_icl = vfactory.add_var(f"Kp_icl")
    Ki_icl = vfactory.add_var(f"Ki_icl")
    tau_P = vfactory.add_var(f"tau_P")
    tau_Q = vfactory.add_var(f"tau_Q")
    I_max = vfactory.add_var(f"I_max")

    vd_g = vfactory.add_var(f"vd_g")
    vq_g = vfactory.add_var(f"vq_g")
    vd_f = vfactory.add_var(f"vd_f")
    vq_f = vfactory.add_var(f"vq_f")
    vd_c = vfactory.add_var(f"vd_c")
    vq_c = vfactory.add_var(f"vq_c")

    id_g = vfactory.add_var(f"id_g")
    iq_g = vfactory.add_var(f"iq_g")
    id_c = vfactory.add_var(f"id_c")
    iq_c = vfactory.add_var(f"iq_c")
    id_c_ref = vfactory.add_var(f"id_c_ref")
    iq_c_ref = vfactory.add_var(f"iq_c_ref")
    vd_c_ref = vfactory.add_var(f"vd_c_ref")
    vq_c_ref = vfactory.add_var(f"vq_c_ref")

    P = vfactory.add_var(f"P", reference=VarPowerFlowReferenceType.P)
    Q = vfactory.add_var(f"Q", reference=VarPowerFlowReferenceType.Q)
    P_ref = vfactory.add_var(f"P_ref")
    Q_ref = vfactory.add_var(f"Q_ref")
    V_ref = vfactory.add_var(f"V_ref")
    V = vfactory.add_var(f"V")

    park_block, (vd_meas, vq_meas) = park_transform_block(vfactory, [v_a, v_b, v_c], theta, name=f"v")

    eqs = [
        vd_g - vd_meas,
        vq_g - vq_meas,
        vd_f - vd_g - (Rc * id_g - omega * Lc * iq_g),
        vq_f - vq_g - (Rc * iq_g + omega * Lc * id_g),
        vd_c - vd_f - (Rf * id_c - omega * Lf * iq_c),
        vq_c - vq_f - (Rf * iq_c + omega * Lf * id_c),
        iq_c - iq_g - (-Cf * omega * vq_f + vd_f / Rcap),
        id_c - id_g - (Cf * omega * vd_f + vq_f / Rcap),
        P - vfactory.add_const(1.5) * (vq_g * iq_g + vd_g * id_g),
        Q - vfactory.add_const(1.5) * (vq_g * id_g - vd_g * iq_g),
    ]

    block_P, P_lp = tf_to_block(vfactory, num=[vfactory.add_const(1)], den=[vfactory.add_const(1), tau_P], x=P, name=f"P_lp")
    block_Q, Q_lp = tf_to_block(vfactory, num=[vfactory.add_const(1)], den=[vfactory.add_const(1), tau_Q], x=Q, name=f"Q_lp")
    block_P.init_eqs = {P_lp: P}
    block_Q.init_eqs = {Q_lp: Q}

    eqs += [
        omega - (1.0 - Kdp * (P_lp - P_ref)),
        V - (V_ref - Kdq * (Q_lp - Q_ref)),
        dt_theta - 2 * math.pi * fn * (omega - 1.0),
    ]

    vd_ref = vd_f
    vq_ref = vq_f
    block_vd, id_hat = tf_to_block(vfactory, num=[Ki_icl, Kp_icl], den=[0, 1], x=vd_ref - vd_f, name=f"vd_ctrl")
    block_vq, iq_hat = tf_to_block(vfactory, num=[Ki_icl, Kp_icl], den=[0, 1], x=vq_ref - vq_f, name=f"vq_ctrl")

    i_d_ref_raw = iq_hat + iq_g - Cf * omega * vq_f
    i_q_ref_raw = id_hat + id_g + Cf * omega * vd_f
    iq_for_lim = sym.max(iq_c, i_q_ref_raw)
    id_max = sym.sqrt(sym.max(I_max ** 2 - iq_for_lim ** 2, vfactory.add_const(1e-5)))
    i_d_ref_sat = sym.hard_sat(i_d_ref_raw, -id_max, id_max)
    i_q_ref_sat = sym.hard_sat(i_q_ref_raw, -I_max, I_max)
    i_d_ref_sat_var = vfactory.add_var(f"i_d_ref_sat")
    i_q_ref_sat_var = vfactory.add_var(f"i_q_ref_sat")

    eqs += [
        i_d_ref_sat_var - i_d_ref_sat,
        i_q_ref_sat_var - i_q_ref_sat,
        id_c_ref - i_d_ref_sat_var,
        iq_c_ref - i_q_ref_sat_var,
    ]

    block_id, vd_hat = tf_to_block(vfactory, num=[Ki_icl, Kp_icl], den=[0, 1], x=id_c_ref - id_c, name=f"id_ctrl")
    block_iq, vq_hat = tf_to_block(vfactory, num=[Ki_icl, Kp_icl], den=[0, 1], x=iq_c_ref - iq_c, name=f"iq_ctrl")
    eqs += [
        vd_c_ref - (vd_hat + vd_f - Lf * omega * iq_c),
        vq_c_ref - (vq_hat + vq_f + Lf * omega * id_c),
        vd_c - vd_c_ref,
        vq_c - vq_c_ref,
        Pt_vsc + P,
        Qt_vsc + Q,
    ]

    currents_block, (i_A, i_B, i_C) = inverse_park_currents_block(vfactory, id_g, iq_g, theta)

    core = Block(
        algebraic_eqs=eqs,
        algebraic_vars=[
            Pt_vsc, Qt_vsc, P, Q, P_ref, Q_ref, V_ref, omega, theta, V,
            vd_g, vq_g, vd_f, vq_f, vd_c, vq_c,
            id_g, iq_g, id_c, iq_c, id_c_ref, iq_c_ref, vd_c_ref, vq_c_ref,
            i_d_ref_sat_var, i_q_ref_sat_var,
        ],
        diff_vars=[dt_theta],
        event_dict={
            Rf: vfactory.add_const(0.02),
            Lf: vfactory.add_const(0.15),
            Rc: vfactory.add_const(0.01),
            Lc: vfactory.add_const(0.1),
            Cf: vfactory.add_const(0.05),
            Rcap: vfactory.add_const(1e6),
            Kdp: vfactory.add_const(0.05),
            Kdq: vfactory.add_const(0.05),
            Kp_icl: vfactory.add_const(0.05),
            Ki_icl: vfactory.add_const(50.0),
            tau_P: vfactory.add_const(0.01),
            tau_Q: vfactory.add_const(0.01),
            I_max: vfactory.add_const(1.2),
        },
        init_eqs={
            theta: vfactory.add_const(0.0),
            omega: vfactory.add_const(1.0),
            P: -Pt_vsc,
            Q: -Qt_vsc,
            P_ref: P,
            Q_ref: Q,
            V_ref: vfactory.add_const(1.0),
            V: vfactory.add_const(1.0),
            vd_g: vd_meas,
            vq_g: vq_meas,
            id_g: (2 / 3) * Q / sym.max(vq_g, vfactory.add_const(1e-6)),
            iq_g: (2 / 3) * P / sym.max(vq_g, vfactory.add_const(1e-6)),
            vd_f: vd_g + (Rc * id_g - omega * Lc * iq_g),
            vq_f: vq_g + (Rc * iq_g + omega * Lc * id_g),
            id_c: id_g + Cf * omega * vd_f + vq_f / Rcap,
            iq_c: iq_g - Cf * omega * vq_f - vd_f / Rcap,
            id_c_ref: id_c,
            iq_c_ref: iq_c,
            i_d_ref_sat_var: id_c,
            i_q_ref_sat_var: iq_c,
            vd_c_ref: Rf * id_c - Lf * omega * iq_c + vd_f,
            vq_c_ref: Rf * iq_c + Lf * omega * id_c + vq_f,
            vd_c: vd_c_ref,
            vq_c: vq_c_ref,
            vd_hat: vd_c_ref - vd_f + Lf * omega * iq_c,
            vq_hat: vq_c_ref - vq_f - Lf * omega * id_c,
            iq_hat: id_c - iq_g + Cf * vq_f,
            id_hat: iq_c - id_g - Cf * vd_f,
        },
        in_vars=[v_a, v_b, v_c, v_dc],
        out_vars=[i_A, i_B, i_C],
        external_mapping={
            VarPowerFlowReferenceType.v_A: v_a,
            VarPowerFlowReferenceType.v_B: v_b,
            VarPowerFlowReferenceType.v_C: v_c,
            VarPowerFlowReferenceType.Vdc: v_dc,
            VarPowerFlowReferenceType.i_A: i_A,
            VarPowerFlowReferenceType.i_B: i_B,
            VarPowerFlowReferenceType.i_C: i_C,
            VarPowerFlowReferenceType.Pt: Pt_vsc,
            VarPowerFlowReferenceType.Qt: Qt_vsc,
            VarPowerFlowReferenceType.Pf: P,
            VarPowerFlowReferenceType.P: P,
            VarPowerFlowReferenceType.Q: Q,
        },
        api_obj_mapping={ParamPowerFlowReferenceType.freq: fn},
        parameters={fn: vfactory.add_const(50.0)},
    )

    core.add(park_block)
    core.add(block_P)
    core.add(block_Q)
    core.add(block_vd)
    core.add(block_vq)
    core.add(block_id)
    core.add(block_iq)
    core.add(currents_block)
    core.unify_blocks()
    return core
