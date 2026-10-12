# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Multilinear simple synchronous-generator EMT template."""

from __future__ import annotations

import numpy as np

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_pf_positive_sequence_init_refs
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowReferenceType, VarPowerFlowReferenceType


def get_simple_generator_emt_multilinear_template(
    vf: VarFactory,
    name: str = "simple_emt_type_generator_template_ml",
) -> EmtModelTemplate:
    """Build the simple EMT generator with runtime trig calls reformulated.

    The external interface and initialization equations match
    ``get_simple_generator_emt_template``. Runtime ``sin(theta +/- 2pi/3)`` and
    ``cos(theta +/- 2pi/3)`` terms are replaced by the multilinear trig-transform
    auxiliary variables.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name
    templ.block.name = name

    v_A = vf.add_var(name=f"v_A", reference=VarPowerFlowReferenceType.v_A)
    v_B = vf.add_var(name=f"v_B", reference=VarPowerFlowReferenceType.v_B)
    v_C = vf.add_var(name=f"v_C", reference=VarPowerFlowReferenceType.v_C)
    Tm = vf.add_var(name=f"Tm")
    v_f = vf.add_var(name=f"v_f")

    d_v_A = vf.add_var(name=f"d_v_A", reference=VarPowerFlowReferenceType.d_v_A)
    d_v_B = vf.add_var(name=f"d_v_B", reference=VarPowerFlowReferenceType.d_v_B)
    d_v_C = vf.add_var(name=f"d_v_C", reference=VarPowerFlowReferenceType.d_v_C)
    p_A = vf.add_var(name=f"P_A", reference=VarPowerFlowReferenceType.P_A)
    q_A = vf.add_var(name=f"Q_A", reference=VarPowerFlowReferenceType.Q_A)
    p_B = vf.add_var(name=f"P_B", reference=VarPowerFlowReferenceType.P_B)
    q_B = vf.add_var(name=f"Q_B", reference=VarPowerFlowReferenceType.Q_B)
    p_C = vf.add_var(name=f"P_C", reference=VarPowerFlowReferenceType.P_C)
    q_C = vf.add_var(name=f"Q_C", reference=VarPowerFlowReferenceType.Q_C)
    inputs = [v_A, v_B, v_C, Tm, v_f]

    theta = vf.add_var("theta_" + name)
    omega = vf.add_var(name=f"omega")
    psi_d = vf.add_var("psi_d_" + name)
    psi_q = vf.add_var("psi_q_" + name)
    psi_f = vf.add_var("psi_f_" + name)
    psi_0 = vf.add_var("psi_0_" + name)

    d_omega = vf.add_diff_var(name=f"d_omega", base_var=omega)
    d_theta = vf.add_diff_var(name=f"d_theta", base_var=theta)
    d_psi_d = vf.add_diff_var(name=f"d_psi_d", base_var=psi_d)
    d_psi_q = vf.add_diff_var(name=f"d_psi_q", base_var=psi_q)
    d_psi_0 = vf.add_diff_var(name=f"d_psi_0", base_var=psi_0)
    d_psi_f = vf.add_diff_var(name=f"d_psi_f", base_var=psi_f)

    i_A = vf.add_var(name=f"i_A", reference=VarPowerFlowReferenceType.i_A)
    i_B = vf.add_var(name=f"i_B", reference=VarPowerFlowReferenceType.i_B)
    i_C = vf.add_var(name=f"i_C", reference=VarPowerFlowReferenceType.i_C)
    v_d = vf.add_var("v_d_" + name)
    v_q = vf.add_var("v_q_" + name)
    v_0 = vf.add_var("v_0_" + name)
    i_d = vf.add_var("i_d_" + name)
    i_q = vf.add_var("i_q_" + name)
    i_0 = vf.add_var("i_0_" + name)
    i_f = vf.add_var(name=f"i_f")
    Te = vf.add_var("Te_" + name)
    Pe = vf.add_var("Pe_" + name)
    Qe = vf.add_var("Qe_" + name)
    Pm = vf.add_var("Pm_" + name)

    omega_base = vf.add_var("omega_base")
    H = vf.add_var("H")
    D = vf.add_var("D")
    Ra = vf.add_var("Ra")
    La = vf.add_var("La")
    Ld = vf.add_var("Ld")
    Lmd = vf.add_var("Lmd")
    Lmq = vf.add_var("Lmq")
    Lf = vf.add_var("Lf")
    Rf = vf.add_var("Rf")
    R0 = vf.add_var("R0")
    L0 = vf.add_var("L0")
    omega_ref = vf.add_var("omega_ref")
    delta = vf.add_var("delta_" + name)

    phi_v_init, phi_init, vpk_init, ipk_init = get_pf_positive_sequence_init_refs(
        v_a=v_A,
        v_b=v_B,
        v_c=v_C,
        d_v_a=d_v_A,
        d_v_b=d_v_B,
        d_v_c=d_v_C,
        p_a=p_A,
        q_a=q_A,
        p_b=p_B,
        q_b=q_B,
        p_c=p_C,
        q_c=q_C,
        omega_base=omega_base,
    )

    cos_theta = vf.add_var(name=f"u_cos")
    sin_theta = vf.add_var(name=f"u_sin")
    d_cos_theta = vf.add_diff_var(name=f"d_u_cos", base_var=cos_theta)
    d_sin_theta = vf.add_diff_var(name=f"d_u_sin", base_var=sin_theta)
    c120 = np.cos(2.0 * np.pi / 3.0)
    s120 = np.sin(2.0 * np.pi / 3.0)
    sin_t_m120 = sin_theta * c120 - cos_theta * s120
    cos_t_m120 = cos_theta * c120 + sin_theta * s120
    sin_t_p120 = sin_theta * c120 + cos_theta * s120
    cos_t_p120 = cos_theta * c120 - sin_theta * s120

    templ.block = Block(
        state_eqs=[
            -v_d - Ra * i_d + omega * psi_q,
            -v_q - Ra * i_q - omega * psi_d,
            -v_0 - R0 * i_0,
            v_f - Rf * i_f,
            omega_base * omega,
            (Tm - Te - D * (omega - omega_ref)) / (2 * H),
            -(omega_base * omega) * sin_theta,
            (omega_base * omega) * cos_theta,
        ],
        state_vars=[psi_d, psi_q, psi_0, psi_f, theta, omega, cos_theta, sin_theta],
        algebraic_eqs=[
            psi_d - (Lmd * i_f - (Lmd + La) * i_d),
            psi_q - (-(Lmq + La) * i_q),
            psi_0 - (-L0 * i_0),
            psi_f - ((Lmd + Lf) * i_f - Lmd * i_d),
            v_d - (2 / 3) * (inputs[0] * sin_theta + inputs[1] * sin_t_m120 + inputs[2] * sin_t_p120),
            v_q - (2 / 3) * (inputs[0] * cos_theta + inputs[1] * cos_t_m120 + inputs[2] * cos_t_p120),
            v_0 - (1 / 3) * (inputs[0] + inputs[1] + inputs[2]),
            i_A - (i_d * sin_theta + i_q * cos_theta + i_0),
            i_B - (i_d * sin_t_m120 + i_q * cos_t_m120 + i_0),
            i_C - (i_d * sin_t_p120 + i_q * cos_t_p120 + i_0),
            Te - (3 / 2) * (psi_q * i_d - psi_d * i_q),
            Pe - (i_A * inputs[0] + i_B * inputs[1] + i_C * inputs[2]),
            Qe - (1 / np.sqrt(3)) * ((inputs[0] - inputs[1]) * i_C + (inputs[1] - inputs[2]) * i_A + (inputs[2] - inputs[0]) * i_B),
            Pe - Pm,
        ],
        algebraic_vars=[i_d, i_q, i_0, i_f, v_d, v_q, v_0, i_A, i_B, i_C, Te, Pe, Qe, Pm],
        in_vars=inputs,
        out_vars=[i_A, i_B, i_C, omega, i_f, Te],
    )
    templ.block.diff_vars = [d_psi_d, d_psi_q, d_psi_0, d_psi_f, d_theta, d_omega, d_cos_theta, d_sin_theta]

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.i_A: i_A,
        VarPowerFlowReferenceType.i_B: i_B,
        VarPowerFlowReferenceType.i_C: i_C,
        VarPowerFlowReferenceType.d_v_A: d_v_A,
        VarPowerFlowReferenceType.d_v_B: d_v_B,
        VarPowerFlowReferenceType.d_v_C: d_v_C,
        VarPowerFlowReferenceType.P_A: p_A,
        VarPowerFlowReferenceType.Q_A: q_A,
        VarPowerFlowReferenceType.P_B: p_B,
        VarPowerFlowReferenceType.Q_B: q_B,
        VarPowerFlowReferenceType.P_C: p_C,
        VarPowerFlowReferenceType.Q_C: q_C,
    }
    templ.block.event_dict = {
        H: vf.add_const(5.0),
        D: vf.add_const(2.0),
        La: vf.add_const(0.15),
        Lmq: vf.add_const(1.55),
        Lf: vf.add_const(0.10),
        Rf: vf.add_const(0.017),
        omega_ref: vf.add_const(1.0),
        Lmd: Ld - La,
        d_v_A: vf.add_const(None),
        d_v_B: vf.add_const(None),
        d_v_C: vf.add_const(None),
        p_A: vf.add_const(None),
        q_A: vf.add_const(None),
        p_B: vf.add_const(None),
        q_B: vf.add_const(None),
        p_C: vf.add_const(None),
        q_C: vf.add_const(None),
        delta: sym.atan(
            (Ra * ipk_init * sym.sin(phi_init) - omega * (Lmq + La) * ipk_init * sym.cos(phi_init))
            / (vpk_init + Ra * ipk_init * sym.cos(phi_init) + omega * (Lmq + La) * ipk_init * sym.sin(phi_init))
        ),
    }
    templ.block.parameters.update({
        R0: vf.add_const(0.001),
        omega_base: vf.add_const(None),
        Ra: vf.add_const(None),
        Ld: vf.add_const(None),
        L0: vf.add_const(None),
    })
    templ.block.api_obj_mapping = {
        ParamPowerFlowReferenceType.generator_r0_pu: R0,
        ParamPowerFlowReferenceType.omega_base: omega_base,
        ParamPowerFlowReferenceType.R1: Ra,
        ParamPowerFlowReferenceType.X1: Ld,
        ParamPowerFlowReferenceType.X0: L0,
    }

    templ.block.init_eqs = {
        omega: omega_ref,
        theta: phi_v_init + delta,
        cos_theta: sym.cos(theta),
        sin_theta: sym.sin(theta),
        v_d: 2 / 3 * (sym.sin(theta) * inputs[0] + sym.sin(theta - 2 * np.pi / 3) * inputs[1] + sym.sin(theta + 2 * np.pi / 3) * inputs[2]),
        v_q: 2 / 3 * (sym.cos(theta) * inputs[0] + sym.cos(theta - 2 * np.pi / 3) * inputs[1] + sym.cos(theta + 2 * np.pi / 3) * inputs[2]),
        v_0: (1 / 3) * (inputs[0] + inputs[1] + inputs[2]),
        i_d: 2 / 3 * (sym.sin(theta) * i_A + sym.sin(theta - 2 * np.pi / 3) * i_B + sym.sin(theta + 2 * np.pi / 3) * i_C),
        i_q: 2 / 3 * (sym.cos(theta) * i_A + sym.cos(theta - 2 * np.pi / 3) * i_B + sym.cos(theta + 2 * np.pi / 3) * i_C),
        i_0: (1 / 3) * (i_A + i_B + i_C),
        psi_q: (v_d + Ra * i_d),
        psi_d: -(v_q + Ra * i_q),
        psi_0: -L0 * i_0,
        i_f: (psi_d + (Lmd + La) * i_d) / Lmd,
        psi_f: (Lmd + Lf) * i_f - Lmd * i_d,
        Pe: (i_A * inputs[0] + i_B * inputs[1] + i_C * inputs[2]),
        Qe: (1 / np.sqrt(3)) * ((inputs[0] - inputs[1]) * i_C + (inputs[1] - inputs[2]) * i_A + (inputs[2] - inputs[0]) * i_B),
        Te: (3 / 2) * (psi_q * i_d - psi_d * i_q),
        Pm: Pe,
    }

    c0 = vf.add_const(0.0)
    templ.block.diff_init_eqs = {
        d_theta: omega_base * omega,
        d_omega: c0,
        d_psi_d: c0,
        d_psi_q: c0,
        d_psi_0: c0,
        d_psi_f: c0,
        d_cos_theta: -(omega_base * omega) * sin_theta,
        d_sin_theta: (omega_base * omega) * cos_theta,
    }

    return templ
