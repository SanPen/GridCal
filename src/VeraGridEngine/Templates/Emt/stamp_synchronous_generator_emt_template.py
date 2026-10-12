# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""STAMP-style sixth-order synchronous-generator EMT template."""

import numpy as np

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowReferenceType, VarPowerFlowReferenceType
from VeraGridEngine.Templates.Emt.generator_emt_type_template import (
    get_pf_positive_sequence_init_refs,
)


def get_stamp_synchronous_machine_6th_order_emt_template(
        vf: VarFactory,
        name: str = "stamp_sg_6th_order_machine",
) -> EmtModelTemplate:
    """
    Build the STAMP-like sixth-order subtransient synchronous machine.

    Dynamic states are ``delta``, ``omega``, ``e_qp``, ``e_dp``, ``psi_pp_d`` and
    ``psi_pp_q``. ``theta_abs`` is an extra EMT kinematic angle used only for the
    instantaneous abc/dq interface. Stator transients are neglected, as in the
    standard sixth-order phasor-domain synchronous generator used by STAMP's
    small-signal model.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name
    templ.block.name = name

    c0 = vf.add_const(0.0)
    c1 = vf.add_const(1.0)
    two_pi_over_3 = 2.0 * np.pi / 3.0

    v_a = vf.add_var(f"v_A_{name}", reference=VarPowerFlowReferenceType.v_A)
    v_b = vf.add_var(f"v_B_{name}", reference=VarPowerFlowReferenceType.v_B)
    v_c = vf.add_var(f"v_C_{name}", reference=VarPowerFlowReferenceType.v_C)
    tm = vf.add_var(f"Tm_{name}", shared_reference="Tm_reference")
    v_f = vf.add_var(f"v_f_{name}", shared_reference="v_f_reference")

    d_v_a = vf.add_var(f"d_v_A_{name}", reference=VarPowerFlowReferenceType.d_v_A)
    d_v_b = vf.add_var(f"d_v_B_{name}", reference=VarPowerFlowReferenceType.d_v_B)
    d_v_c = vf.add_var(f"d_v_C_{name}", reference=VarPowerFlowReferenceType.d_v_C)
    p_a = vf.add_var(f"P_A_{name}", reference=VarPowerFlowReferenceType.P_A)
    q_a = vf.add_var(f"Q_A_{name}", reference=VarPowerFlowReferenceType.Q_A)
    p_b = vf.add_var(f"P_B_{name}", reference=VarPowerFlowReferenceType.P_B)
    q_b = vf.add_var(f"Q_B_{name}", reference=VarPowerFlowReferenceType.Q_B)
    p_c = vf.add_var(f"P_C_{name}", reference=VarPowerFlowReferenceType.P_C)
    q_c = vf.add_var(f"Q_C_{name}", reference=VarPowerFlowReferenceType.Q_C)
    inputs = [v_a, v_b, v_c, tm, v_f]

    theta_abs = vf.add_var(f"theta_abs_{name}")
    delta = vf.add_var(f"delta_{name}")
    omega = vf.add_var(f"omega_{name}", shared_reference="omega_reference")
    e_qp = vf.add_var(f"e_qp_{name}")
    e_dp = vf.add_var(f"e_dp_{name}")
    psi_pp_d = vf.add_var(f"psi_pp_d_{name}")
    psi_pp_q = vf.add_var(f"psi_pp_q_{name}")

    d_theta_abs = vf.add_diff_var(name=f"d_theta_abs_{name}", base_var=theta_abs)
    d_delta = vf.add_diff_var(name=f"d_delta_{name}", base_var=delta)
    d_omega = vf.add_diff_var(name=f"d_omega_{name}", base_var=omega)
    d_e_qp = vf.add_diff_var(name=f"d_e_qp_{name}", base_var=e_qp)
    d_e_dp = vf.add_diff_var(name=f"d_e_dp_{name}", base_var=e_dp)
    d_psi_pp_d = vf.add_diff_var(name=f"d_psi_pp_d_{name}", base_var=psi_pp_d)
    d_psi_pp_q = vf.add_diff_var(name=f"d_psi_pp_q_{name}", base_var=psi_pp_q)

    v_d = vf.add_var(f"v_d_{name}")
    v_q = vf.add_var(f"v_q_{name}")
    v_0 = vf.add_var(f"v_0_{name}")
    i_d = vf.add_var(f"i_d_{name}")
    i_q = vf.add_var(f"i_q_{name}")
    i_0 = vf.add_var(f"i_0_{name}")
    psi_d = vf.add_var(f"psi_d_{name}")
    psi_q = vf.add_var(f"psi_q_{name}")
    i_a = vf.add_var(f"i_A_{name}", reference=VarPowerFlowReferenceType.i_A)
    i_b = vf.add_var(f"i_B_{name}", reference=VarPowerFlowReferenceType.i_B)
    i_c = vf.add_var(f"i_C_{name}", reference=VarPowerFlowReferenceType.i_C)
    te = vf.add_var(f"Te_{name}", shared_reference="Te_reference")
    p_e = vf.add_var(f"p_e_{name}")
    q_e = vf.add_var(f"q_e_{name}")
    i_rpu = vf.add_var(f"IRPu_{name}", shared_reference="IRPu_reference")

    ra = vf.add_var(f"ra_{name}")
    xd = vf.add_var(f"xd_{name}")
    xq = vf.add_var(f"xq_{name}")
    xdp = vf.add_var(f"xdp_{name}")
    xqp = vf.add_var(f"xqp_{name}")
    xdpp = vf.add_var(f"xdpp_{name}")
    xqpp = vf.add_var(f"xqpp_{name}")
    xl = vf.add_var(f"xl_{name}")
    x0 = vf.add_var(f"x0_{name}")
    td0p = vf.add_var(f"Td0p_{name}")
    tq0p = vf.add_var(f"Tq0p_{name}")
    td0pp = vf.add_var(f"Td0pp_{name}")
    tq0pp = vf.add_var(f"Tq0pp_{name}")
    gamma_d1 = vf.add_var(f"gamma_d1_{name}")
    gamma_q1 = vf.add_var(f"gamma_q1_{name}")
    gamma_d2 = vf.add_var(f"gamma_d2_{name}")
    gamma_q2 = vf.add_var(f"gamma_q2_{name}")
    h = vf.add_var(f"H_{name}")
    d = vf.add_var(f"D_{name}")
    omega_b = vf.add_var(f"omega_b_{name}")
    omega_s = vf.add_var(f"omega_s_{name}")

    phi_v_init, phi_init, vpk_init, ipk_init = get_pf_positive_sequence_init_refs(
        v_a=v_a, v_b=v_b, v_c=v_c,
        d_v_a=d_v_a, d_v_b=d_v_b, d_v_c=d_v_c,
        p_a=p_a, q_a=q_a, p_b=p_b, q_b=q_b, p_c=p_c, q_c=q_c,
        omega_base=omega_b,
    )

    templ.block = Block(
        state_eqs=[
            omega_b * omega,
            omega_b * (omega - omega_s),
            (tm - te - d * (omega - omega_s)) / (2.0 * h),
            (-i_rpu + v_f) / td0p,
            (-e_dp + (xq - xqp) * (gamma_q1 * i_q - gamma_q2 * psi_pp_q - gamma_q2 * e_dp)) / tq0p,
            (-psi_pp_d + e_qp - (xdp - xl) * i_d) / td0pp,
            (-psi_pp_q - e_dp - (xqp - xl) * i_q) / tq0pp,
        ],
        state_vars=[theta_abs, delta, omega, e_qp, e_dp, psi_pp_d, psi_pp_q],
        diff_vars=[d_theta_abs, d_delta, d_omega, d_e_qp, d_e_dp, d_psi_pp_d, d_psi_pp_q],
        algebraic_eqs=[
            v_d + (2.0 / 3.0) * (
                sym.cos(theta_abs) * v_a
                + sym.cos(theta_abs - two_pi_over_3) * v_b
                + sym.cos(theta_abs + two_pi_over_3) * v_c
            ),
            v_q - (2.0 / 3.0) * (
                sym.sin(theta_abs) * v_a
                + sym.sin(theta_abs - two_pi_over_3) * v_b
                + sym.sin(theta_abs + two_pi_over_3) * v_c
            ),
            v_0 - (1.0 / 3.0) * (v_a + v_b + v_c),
            v_d + ra * i_d + omega * psi_q,
            v_q + ra * i_q - omega * psi_d,
            psi_d + xdpp * i_d - gamma_d1 * e_qp - (c1 - gamma_d1) * psi_pp_d,
            psi_q + xqpp * i_q + gamma_q1 * e_dp - (c1 - gamma_q1) * psi_pp_q,
            i_0 + v_0 / x0,
            i_a - (i_q * sym.sin(theta_abs) - i_d * sym.cos(theta_abs) + i_0),
            i_b - (
                i_q * sym.sin(theta_abs - two_pi_over_3)
                - i_d * sym.cos(theta_abs - two_pi_over_3)
                + i_0
            ),
            i_c - (
                i_q * sym.sin(theta_abs + two_pi_over_3)
                - i_d * sym.cos(theta_abs + two_pi_over_3)
                + i_0
            ),
            te - 1.5 * (psi_d * i_q - psi_q * i_d),
            p_e - (v_a * i_a + v_b * i_b + v_c * i_c),
            q_e - (1.0 / np.sqrt(3.0)) * ((v_a - v_b) * i_c + (v_b - v_c) * i_a + (v_c - v_a) * i_b),
            i_rpu - (e_qp + (xd - xdp) * (gamma_d1 * i_d - gamma_d2 * psi_pp_d + gamma_d2 * e_qp)),
        ],
        algebraic_vars=[v_d, v_q, v_0, i_d, i_q, i_0, psi_d, psi_q, i_a, i_b, i_c, te, p_e, q_e, i_rpu],
        in_vars=inputs,
        out_vars=[i_a, i_b, i_c, omega, i_rpu, te],
    )
    templ.block.name = name

    templ.block.event_dict = {
        h: vf.add_const(6.5),
        omega_s: vf.add_const(1.0),
        gamma_d1: (xdpp - xl) / (xdp - xl),
        gamma_q1: (xqpp - xl) / (xqp - xl),
        gamma_d2: (xdp - xdpp) / ((xdp - xl) ** 2),
        gamma_q2: (xqp - xqpp) / ((xqp - xl) ** 2),
        d_v_a: vf.add_const(None),
        d_v_b: vf.add_const(None),
        d_v_c: vf.add_const(None),
        p_a: vf.add_const(None),
        q_a: vf.add_const(None),
        p_b: vf.add_const(None),
        q_b: vf.add_const(None),
        p_c: vf.add_const(None),
        q_c: vf.add_const(None),
    }
    templ.block.parameters.update({
        omega_b: vf.add_const(None),
        ra: vf.add_const(None),
        xd: vf.add_const(None),
        xq: vf.add_const(1.70),
        xdp: vf.add_const(0.30),
        xqp: vf.add_const(0.55),
        xdpp: vf.add_const(0.25),
        xqpp: vf.add_const(0.25),
        xl: vf.add_const(0.20),
        x0: vf.add_const(0.14),
        td0p: vf.add_const(8.0),
        tq0p: vf.add_const(0.4),
        td0pp: vf.add_const(0.03),
        tq0pp: vf.add_const(0.05),
        d: vf.add_const(0.0),
    })

    templ.block.api_obj_mapping = {
        ParamPowerFlowReferenceType.omega_base: omega_b,
        ParamPowerFlowReferenceType.R1: ra,
        ParamPowerFlowReferenceType.X1: xd,
        ParamPowerFlowReferenceType.X0: x0,
        ParamPowerFlowReferenceType.Ra: ra,
        ParamPowerFlowReferenceType.Rs: ra,
        ParamPowerFlowReferenceType.Xd: xd,
        ParamPowerFlowReferenceType.Xq: xq,
        ParamPowerFlowReferenceType.Xd_prime: xdp,
        ParamPowerFlowReferenceType.Xq_prime: xqp,
        ParamPowerFlowReferenceType.Xd_2prime: xdpp,
        ParamPowerFlowReferenceType.Xq_2prime: xqpp,
        ParamPowerFlowReferenceType.Xl: xl,
        ParamPowerFlowReferenceType.Td0_prime: td0p,
        ParamPowerFlowReferenceType.Tq0_prime: tq0p,
        ParamPowerFlowReferenceType.Td0_2prime: td0pp,
        ParamPowerFlowReferenceType.Tq0_2prime: tq0pp,
        ParamPowerFlowReferenceType.D: d,
    }

    # STAMP initializes the rotor angle from the internal voltage computed with Xq:
    # E = V + (Rs + j Xq) I. This makes the q-axis steady-state flux relations
    # consistent with the sixth-order subtransient states below.
    e_re = vpk_init * sym.cos(phi_v_init) + ra * ipk_init * sym.cos(phi_init) - xq * ipk_init * sym.sin(phi_init)
    e_im = vpk_init * sym.sin(phi_v_init) + ra * ipk_init * sym.sin(phi_init) + xq * ipk_init * sym.cos(phi_init)

    templ.block.init_eqs = {
        omega: omega_s,
        theta_abs: sym.atan(e_im / e_re),
        delta: theta_abs,
        v_d: vpk_init * sym.sin(theta_abs - phi_v_init),
        v_q: vpk_init * sym.cos(theta_abs - phi_v_init),
        v_0: c0,
        i_d: ipk_init * sym.sin(theta_abs - phi_init),
        i_q: ipk_init * sym.cos(theta_abs - phi_init),
        i_0: c0,
        psi_d: v_q + ra * i_q,
        psi_q: -v_d - ra * i_d,
        e_qp: psi_d + xdp * i_d,
        e_dp: (xq - xqp) * i_q,
        psi_pp_d: e_qp - (xdp - xl) * i_d,
        psi_pp_q: -(xq - xl) * i_q,
        i_a: i_q * sym.sin(theta_abs) - i_d * sym.cos(theta_abs) + i_0,
        i_b: i_q * sym.sin(theta_abs - two_pi_over_3) - i_d * sym.cos(theta_abs - two_pi_over_3) + i_0,
        i_c: i_q * sym.sin(theta_abs + two_pi_over_3) - i_d * sym.cos(theta_abs + two_pi_over_3) + i_0,
        i_rpu: e_qp + (xd - xdp) * (gamma_d1 * i_d - gamma_d2 * psi_pp_d + gamma_d2 * e_qp),
        te: 1.5 * (psi_d * i_q - psi_q * i_d),
        v_f: i_rpu,
        p_e: v_a * i_a + v_b * i_b + v_c * i_c,
        q_e: (1.0 / np.sqrt(3.0)) * ((v_a - v_b) * i_c + (v_b - v_c) * i_a + (v_c - v_a) * i_b),
    }

    templ.block.diff_init_eqs = {
        d_theta_abs: omega_b * c1,
        d_delta: c0,
        d_omega: c0,
        d_e_qp: c0,
        d_e_dp: c0,
        d_psi_pp_d: c0,
        d_psi_pp_q: c0,
    }

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.i_A: i_a,
        VarPowerFlowReferenceType.i_B: i_b,
        VarPowerFlowReferenceType.i_C: i_c,
        VarPowerFlowReferenceType.d_v_A: d_v_a,
        VarPowerFlowReferenceType.d_v_B: d_v_b,
        VarPowerFlowReferenceType.d_v_C: d_v_c,
        VarPowerFlowReferenceType.P_A: p_a,
        VarPowerFlowReferenceType.Q_A: q_a,
        VarPowerFlowReferenceType.P_B: p_b,
        VarPowerFlowReferenceType.Q_B: q_b,
        VarPowerFlowReferenceType.P_C: p_c,
        VarPowerFlowReferenceType.Q_C: q_c,
    }

    return templ


def get_stamp_ieeeg1_governor_emt(vf: VarFactory, name: str = "stamp_ieeeg1_governor") -> EmtModelTemplate:
    """Build the STAMP IEEEG1 governor/turbine EMT block."""
    templ = EmtModelTemplate(name=name)
    templ.block.name = name

    omega = vf.add_var(f"omega_{name}", shared_reference="omega_reference")
    te = vf.add_var(f"Te_{name}", shared_reference="Te_reference")
    tm = vf.add_var(f"Tm_{name}", shared_reference="Tm_reference")
    pref = vf.add_var(f"Pref_{name}")
    wref = vf.add_var(f"omega_ref_{name}")
    cv = vf.add_var(f"SG_cv_{name}")

    gov_x1 = vf.add_var(f"gov_x1_{name}")
    gov_x2 = vf.add_var(f"gov_x2_{name}")
    turb4 = vf.add_var(f"turb_T4_{name}")
    turb5 = vf.add_var(f"turb_T5_{name}")
    turb6 = vf.add_var(f"turb_T6_{name}")
    turb7 = vf.add_var(f"turb_T7_{name}")

    d_gov_x1 = vf.add_diff_var(name=f"d_gov_x1_{name}", base_var=gov_x1)
    d_gov_x2 = vf.add_diff_var(name=f"d_gov_x2_{name}", base_var=gov_x2)
    d_turb4 = vf.add_diff_var(name=f"d_turb_T4_{name}", base_var=turb4)
    d_turb5 = vf.add_diff_var(name=f"d_turb_T5_{name}", base_var=turb5)
    d_turb6 = vf.add_diff_var(name=f"d_turb_T6_{name}", base_var=turb6)
    d_turb7 = vf.add_diff_var(name=f"d_turb_T7_{name}", base_var=turb7)

    r = vf.add_var(f"R_{name}")
    t1 = vf.add_var(f"T1_gov_{name}")
    t2 = vf.add_var(f"T2_gov_{name}")
    t3 = vf.add_var(f"T3_gov_{name}")
    dt = vf.add_var(f"Dt_gov_{name}")
    k1 = vf.add_var(f"K1_turb_{name}")
    k2 = vf.add_var(f"K2_turb_{name}")
    k3 = vf.add_var(f"K3_turb_{name}")
    k4 = vf.add_var(f"K4_turb_{name}")
    k5 = vf.add_var(f"K5_turb_{name}")
    k6 = vf.add_var(f"K6_turb_{name}")
    k7 = vf.add_var(f"K7_turb_{name}")
    k8 = vf.add_var(f"K8_turb_{name}")
    tt4 = vf.add_var(f"T4_turb_{name}")
    tt5 = vf.add_var(f"T5_turb_{name}")
    tt6 = vf.add_var(f"T6_turb_{name}")
    tt7 = vf.add_var(f"T7_turb_{name}")

    templ.block = Block(
        state_eqs=[
            gov_x2,
            pref + wref / r - omega / r - gov_x1 / (t1 * t3) - gov_x2 * (t1 + t3) / (t1 * t3),
            (cv - turb4) / tt4,
            (turb4 - turb5) / tt5,
            (turb5 - turb6) / tt6,
            (turb6 - turb7) / tt7,
        ],
        state_vars=[gov_x1, gov_x2, turb4, turb5, turb6, turb7],
        diff_vars=[d_gov_x1, d_gov_x2, d_turb4, d_turb5, d_turb6, d_turb7],
        algebraic_eqs=[
            cv - (gov_x1 / (t1 * t3) + t2 * gov_x2 / (t1 * t3) + dt * (wref - omega)),
            tm - ((k1 + k2) * turb4 + (k3 + k4) * turb5 + (k5 + k6) * turb6 + (k7 + k8) * turb7),
        ],
        algebraic_vars=[cv, tm],
        in_vars=[omega, te],
        out_vars=[tm],
        event_dict={
            pref: vf.add_const(None),
            wref: vf.add_const(1.0),
            r: vf.add_const(0.05),
            t1: vf.add_const(7.5),
            t2: vf.add_const(2.8),
            t3: vf.add_const(0.1),
            dt: vf.add_const(0.0),
            k1: vf.add_const(0.22),
            k2: vf.add_const(0.0),
            k3: vf.add_const(0.0),
            k4: vf.add_const(0.22),
            k5: vf.add_const(0.14),
            k6: vf.add_const(0.14),
            k7: vf.add_const(0.14),
            k8: vf.add_const(0.14),
            tt4: vf.add_const(0.25),
            tt5: vf.add_const(7.5),
            tt6: vf.add_const(7.5),
            tt7: vf.add_const(0.4),
        },
        init_eqs={
            gov_x1: pref * t1 * t3,
            gov_x2: vf.add_const(0.0),
            cv: pref,
            turb4: pref,
            turb5: pref,
            turb6: pref,
            turb7: pref,
            tm: pref,
        },
        api_obj_mapping={
            ParamPowerFlowReferenceType.generator_share_p_ref: pref,
        },
        name=name,
    )
    return templ


def get_stamp_pss2a_emt(vf: VarFactory, name: str = "stamp_pss2a") -> EmtModelTemplate:
    """Build a STAMP PSS-2A-style speed stabilizer EMT block."""
    templ = EmtModelTemplate(name=name)
    templ.block.name = name

    omega = vf.add_var(f"omega_{name}", shared_reference="omega_reference")
    vpss = vf.add_var(f"V_pss_{name}", shared_reference="V_pss_reference")
    x_lp = vf.add_var(f"pss_lp_{name}")
    x_w1 = vf.add_var(f"pss_w1_{name}")
    x_w2 = vf.add_var(f"pss_w2_{name}")
    x_ll1 = vf.add_var(f"pss_ll1_{name}")
    x_ll2 = vf.add_var(f"pss_ll2_{name}")
    y1 = vf.add_var(f"pss_y1_{name}")
    y2 = vf.add_var(f"pss_y2_{name}")
    y3 = vf.add_var(f"pss_y3_{name}")

    d_x_lp = vf.add_diff_var(name=f"d_pss_lp_{name}", base_var=x_lp)
    d_x_w1 = vf.add_diff_var(name=f"d_pss_w1_{name}", base_var=x_w1)
    d_x_w2 = vf.add_diff_var(name=f"d_pss_w2_{name}", base_var=x_w2)
    d_x_ll1 = vf.add_diff_var(name=f"d_pss_ll1_{name}", base_var=x_ll1)
    d_x_ll2 = vf.add_diff_var(name=f"d_pss_ll2_{name}", base_var=x_ll2)

    ks1 = vf.add_var(f"Ks1_{name}")
    tw1 = vf.add_var(f"Tw1_{name}")
    tw2 = vf.add_var(f"Tw2_{name}")
    t1 = vf.add_var(f"T1_pss_{name}")
    t2 = vf.add_var(f"T2_pss_{name}")
    t3 = vf.add_var(f"T3_pss_{name}")
    t4 = vf.add_var(f"T4_pss_{name}")
    t6 = vf.add_var(f"T6_pss_{name}")
    vmax = vf.add_var(f"VPssMaxPu_{name}")
    vmin = vf.add_var(f"VPssMinPu_{name}")
    speed_dev = omega - vf.add_const(1.0)

    washout1 = x_lp - x_w1
    washout2 = washout1 - x_w2
    lead1 = x_ll1 + (t1 / t2) * (ks1 * washout2 - x_ll1)
    lead2 = x_ll2 + (t3 / t4) * (lead1 - x_ll2)

    templ.block = Block(
        state_eqs=[
            (speed_dev - x_lp) / t6,
            (x_lp - x_w1) / tw1,
            (washout1 - x_w2) / tw2,
            (ks1 * washout2 - x_ll1) / t2,
            (lead1 - x_ll2) / t4,
        ],
        state_vars=[x_lp, x_w1, x_w2, x_ll1, x_ll2],
        diff_vars=[d_x_lp, d_x_w1, d_x_w2, d_x_ll1, d_x_ll2],
        algebraic_eqs=[
            y1 - washout1,
            y2 - washout2,
            y3 - lead2,
            vpss - sym.hard_sat(y3, vmin, vmax),
        ],
        algebraic_vars=[y1, y2, y3, vpss],
        in_vars=[omega],
        out_vars=[vpss],
        event_dict={
            ks1: vf.add_const(10.0),
            tw1: vf.add_const(2.0),
            tw2: vf.add_const(2.0),
            t1: vf.add_const(0.25),
            t2: vf.add_const(0.03),
            t3: vf.add_const(0.15),
            t4: vf.add_const(0.015),
            t6: vf.add_const(0.01),
            vmax: vf.add_const(1.0),
            vmin: vf.add_const(-1.0),
        },
        init_eqs={
            x_lp: vf.add_const(0.0),
            x_w1: vf.add_const(0.0),
            x_w2: vf.add_const(0.0),
            x_ll1: vf.add_const(0.0),
            x_ll2: vf.add_const(0.0),
            y1: vf.add_const(0.0),
            y2: vf.add_const(0.0),
            y3: vf.add_const(0.0),
            vpss: vf.add_const(0.0),
        },
        name=name,
    )
    return templ


def get_stamp_ac4a_exciter_emt(vf: VarFactory, name: str = "stamp_ac4a_exciter") -> EmtModelTemplate:
    """Build a STAMP AC4A/ST1-style AVR/exciter EMT block."""
    templ = EmtModelTemplate(name=name)
    templ.block.name = name

    irpu = vf.add_var(f"IRPu_{name}", shared_reference="IRPu_reference")
    v_a = vf.add_var(f"v_A_{name}", reference=VarPowerFlowReferenceType.v_A)
    v_b = vf.add_var(f"v_B_{name}", reference=VarPowerFlowReferenceType.v_B)
    v_c = vf.add_var(f"v_C_{name}", reference=VarPowerFlowReferenceType.v_C)
    vpss = vf.add_var(f"V_pss_{name}", shared_reference="V_pss_reference")
    vf_out = vf.add_var(f"Vf_{name}", shared_reference="v_f_reference")
    vm = vf.add_var(f"Vm_{name}")
    vc = vf.add_var(f"Vc_{name}")
    verr = vf.add_var(f"Verr_{name}")
    y_ll = vf.add_var(f"exc_leadlag_y_{name}")
    y_fb = vf.add_var(f"exc_field_feedback_{name}")

    x_tr = vf.add_var(f"exc_tr_{name}")
    x_ll = vf.add_var(f"exc_leadlag_x_{name}")
    x_avr = vf.add_var(f"exc_avr_{name}")

    d_x_tr = vf.add_diff_var(name=f"d_exc_tr_{name}", base_var=x_tr)
    d_x_ll = vf.add_diff_var(name=f"d_exc_leadlag_x_{name}", base_var=x_ll)
    d_x_avr = vf.add_diff_var(name=f"d_exc_avr_{name}", base_var=x_avr)
    d_y_fb = vf.add_diff_var(name=f"d_exc_field_feedback_{name}", base_var=y_fb)

    us_ref = vf.add_var(f"UsRefPu_{name}")
    ka = vf.add_var(f"KA_{name}")
    ta = vf.add_var(f"TA_{name}")
    tb = vf.add_var(f"TB_{name}")
    tc = vf.add_var(f"TC_{name}")
    tr = vf.add_var(f"TR_{name}")
    kf = vf.add_var(f"KF_{name}")
    tf = vf.add_var(f"TF_{name}")
    vrmin = vf.add_var(f"VRmin_{name}")
    vrmax = vf.add_var(f"VRmax_{name}")

    measured_vm = sym.sqrt((v_a * v_a + v_b * v_b + v_c * v_c) / 3.0)

    templ.block = Block(
        state_eqs=[
            (vm - x_tr) / tr,
            (kf * vf_out - y_fb) / tf,
            (verr - x_ll) / tb,
            (ka * y_ll - x_avr) / ta,
        ],
        state_vars=[x_tr, y_fb, x_ll, x_avr],
        diff_vars=[d_x_tr, d_y_fb, d_x_ll, d_x_avr],
        algebraic_eqs=[
            vm - measured_vm,
            vc - x_tr,
            verr - (us_ref + vpss - vc - y_fb),
            y_ll - (x_ll + (tc / tb) * (verr - x_ll)),
            vf_out - sym.hard_sat(x_avr, vrmin, vrmax),
        ],
        algebraic_vars=[vm, vc, verr, y_ll, vf_out],
        in_vars=[irpu, v_a, v_b, v_c, vpss],
        out_vars=[vf_out],
        event_dict={
            us_ref: vc + y_fb - vpss + verr,
            ka: vf.add_const(200.0),
            ta: vf.add_const(0.015),
            tb: vf.add_const(10.0),
            tc: vf.add_const(1.0),
            tr: vf.add_const(0.02),
            kf: vf.add_const(0.03),
            tf: vf.add_const(1.0),
            vrmin: vf.add_const(-4.53),
            vrmax: vf.add_const(5.64),
        },
        init_eqs={
            vm: measured_vm,
            x_tr: vm,
            vc: x_tr,
            vpss: vf.add_const(0.0),
            vf_out: irpu,
            y_fb: kf * vf_out,
            x_avr: vf_out,
            y_ll: x_avr / ka,
            x_ll: y_ll,
            verr: y_ll,
        },
        name=name,
    )
    return templ


def get_stamp_synchronous_generator_emt_template(
        vf: VarFactory,
        name: str = "stamp_synchronous_generator_emt_template",
) -> EmtModelTemplate:
    """Build a complete STAMP sixth-order SG with exciter, PSS and governor."""
    templ = EmtModelTemplate(name=name)
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name
    templ.block.name = name

    v_a_in = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowReferenceType.v_A)
    v_b_in = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowReferenceType.v_B)
    v_c_in = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowReferenceType.v_C)

    gen_mdl = get_stamp_synchronous_machine_6th_order_emt_template(vf=vf, name=f"{name}_gen").block
    exciter_mdl = get_stamp_ac4a_exciter_emt(vf=vf, name=f"{name}_exciter").block
    governor_mdl = get_stamp_ieeeg1_governor_emt(vf=vf, name=f"{name}_governor").block
    stabilizer_mdl = get_stamp_pss2a_emt(vf=vf, name=f"{name}_stabilizer").block

    gen_mdl.update_model(gen_mdl.in_vars[0], v_a_in)
    gen_mdl.update_model(gen_mdl.in_vars[1], v_b_in)
    gen_mdl.update_model(gen_mdl.in_vars[2], v_c_in)
    exciter_mdl.update_model(exciter_mdl.in_vars[1], v_a_in)
    exciter_mdl.update_model(exciter_mdl.in_vars[2], v_b_in)
    exciter_mdl.update_model(exciter_mdl.in_vars[3], v_c_in)

    vf.add_connections([gen_mdl.in_vars[4]], [exciter_mdl.out_vars[0]])
    vf.add_connections([exciter_mdl.in_vars[0]], [gen_mdl.out_vars[4]])
    vf.add_connections([exciter_mdl.in_vars[4]], [stabilizer_mdl.out_vars[0]])
    vf.add_connections([stabilizer_mdl.in_vars[0]], [gen_mdl.out_vars[3]])
    vf.add_connections([gen_mdl.in_vars[3]], [governor_mdl.out_vars[0]])
    vf.add_connections([governor_mdl.in_vars[0]], [gen_mdl.out_vars[3]])
    vf.add_connections([governor_mdl.in_vars[1]], [gen_mdl.out_vars[5]])

    templ.block.children.append(gen_mdl)
    templ.block.children.append(governor_mdl)
    templ.block.children.append(stabilizer_mdl)
    templ.block.children.append(exciter_mdl)
    templ.block.in_vars = [v_a_in, v_b_in, v_c_in]
    templ.block.out_vars = [gen_mdl.out_vars[0], gen_mdl.out_vars[1], gen_mdl.out_vars[2]]

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: v_a_in,
        VarPowerFlowReferenceType.v_B: v_b_in,
        VarPowerFlowReferenceType.v_C: v_c_in,
        VarPowerFlowReferenceType.i_A: gen_mdl.out_vars[0],
        VarPowerFlowReferenceType.i_B: gen_mdl.out_vars[1],
        VarPowerFlowReferenceType.i_C: gen_mdl.out_vars[2],
        VarPowerFlowReferenceType.d_v_A: gen_mdl.external_mapping[VarPowerFlowReferenceType.d_v_A],
        VarPowerFlowReferenceType.d_v_B: gen_mdl.external_mapping[VarPowerFlowReferenceType.d_v_B],
        VarPowerFlowReferenceType.d_v_C: gen_mdl.external_mapping[VarPowerFlowReferenceType.d_v_C],
        VarPowerFlowReferenceType.P_A: gen_mdl.external_mapping[VarPowerFlowReferenceType.P_A],
        VarPowerFlowReferenceType.Q_A: gen_mdl.external_mapping[VarPowerFlowReferenceType.Q_A],
        VarPowerFlowReferenceType.P_B: gen_mdl.external_mapping[VarPowerFlowReferenceType.P_B],
        VarPowerFlowReferenceType.Q_B: gen_mdl.external_mapping[VarPowerFlowReferenceType.Q_B],
        VarPowerFlowReferenceType.P_C: gen_mdl.external_mapping[VarPowerFlowReferenceType.P_C],
        VarPowerFlowReferenceType.Q_C: gen_mdl.external_mapping[VarPowerFlowReferenceType.Q_C],
    }

    return templ
