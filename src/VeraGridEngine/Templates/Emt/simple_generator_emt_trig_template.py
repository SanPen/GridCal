# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Utils.Symbolic.block import Block, find_name_in_block
from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowReferenceType, VarPowerFlowReferenceType
from VeraGridEngine.Templates.Emt.generator_emt_type_template import (
    get_exciter_emt,
    get_governor_emt,
    get_stabilizer_emt,
)


def get_simple_generator_emt_template_trig_transform(
    vf: VarFactory,
    name: str = "simple_emt_type_generator_template_ml",
) -> EmtModelTemplate:
    """
    Multilinear reformulation variant of get_simple_generator_emt_template.

    This function is intentionally kept equivalent to
    `Templates/Emt/simple_generator_emt_template.py:get_simple_generator_emt_template`
    except for replacing direct `sin/cos(theta +/- 2pi/3)` calls with auxiliary
    `u_sin/u_cos` state variables and trig-identity combinations.
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

    Ipk = vf.add_var(name="Ipk", reference=VarPowerFlowReferenceType.Ipk)
    Vpk = vf.add_var(name="Vpk", reference=VarPowerFlowReferenceType.Vpk)
    phi = vf.add_var(name="phi", reference=VarPowerFlowReferenceType.phi)
    phi_v = vf.add_var(name="phi_v", reference=VarPowerFlowReferenceType.phi_v)
    inputs = [v_A, v_B, v_C]

    theta = vf.add_var("theta_" + name)
    omega = vf.add_var(name=f"omega")
    psi_d = vf.add_var("psi_d_" + name)
    psi_q = vf.add_var("psi_q_" + name)
    psi_f = vf.add_var("psi_f_" + name)
    psi_0 = vf.add_var("psi_0_" + name)
    et = vf.add_var("et_" + name)

    d_omega = vf.add_diff_var(name=f"d_omega", base_var=omega)
    d_theta = vf.add_diff_var(name=f"d_theta", base_var=theta)
    d_psi_d = vf.add_diff_var(name=f"d_psi_d", base_var=psi_d)
    d_psi_q = vf.add_diff_var(name=f"d_psi_q", base_var=psi_q)
    d_psi_0 = vf.add_diff_var(name=f"d_psi_0", base_var=psi_0)
    d_psi_f = vf.add_diff_var(name=f"d_psi_f", base_var=psi_f)
    d_et = vf.add_diff_var(name=f"d_et", base_var=et)

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
    Kp = vf.add_var("Kp")
    Ki = vf.add_var("Ki")
    v_f0 = vf.add_var("v_f0")

    u_cos = vf.add_var("u_cos")
    u_sin = vf.add_var("u_sin")
    d_u_cos = vf.add_diff_var("d_u_cos", base_var=u_cos)
    d_u_sin = vf.add_diff_var("d_u_sin", base_var=u_sin)
    c120 = np.cos(2.0 * np.pi / 3.0)
    s120 = np.sin(2.0 * np.pi / 3.0)

    sin_t_m120 = u_sin * c120 - u_cos * s120
    cos_t_m120 = u_cos * c120 + u_sin * s120
    sin_t_p120 = u_sin * c120 + u_cos * s120
    cos_t_p120 = u_cos * c120 - u_sin * s120

    templ.block = Block(
        state_eqs=[
            -v_d - Ra * i_d + omega * psi_q,
            -v_q - Ra * i_q - omega * psi_d,
            -v_0 - R0 * i_0,
            v_f - Rf * i_f,
            omega_base * omega,
            (Tm - Te - D * (omega - omega_ref)) / (2 * H),
            omega_base * (omega_ref - omega),
            -(omega_base * omega) * u_sin,
            (omega_base * omega) * u_cos,
        ],
        state_vars=[psi_d, psi_q, psi_0, psi_f, theta, omega, et, u_cos, u_sin],
        algebraic_eqs=[
            psi_d - (Lmd * i_f - (Lmd + La) * i_d),
            psi_q - (-(Lmq + La) * i_q),
            psi_0 - (-L0 * i_0),
            psi_f - ((Lmd + Lf) * i_f - Lmd * i_d),
            v_d - (2 / 3) * (inputs[0] * u_sin + inputs[1] * sin_t_m120 + inputs[2] * sin_t_p120),
            v_q - (2 / 3) * (inputs[0] * u_cos + inputs[1] * cos_t_m120 + inputs[2] * cos_t_p120),
            v_0 - (1 / 3) * (inputs[0] + inputs[1] + inputs[2]),
            i_A - (i_d * u_sin + i_q * u_cos + i_0),
            i_B - (i_d * sin_t_m120 + i_q * cos_t_m120 + i_0),
            i_C - (i_d * sin_t_p120 + i_q * cos_t_p120 + i_0),
            Te - (3 / 2) * (psi_q * i_d - psi_d * i_q),
            Pe - (i_A * inputs[0] + i_B * inputs[1] + i_C * inputs[2]),
            Qe - (1 / np.sqrt(3)) * ((inputs[0] - inputs[1]) * i_C + (inputs[1] - inputs[2]) * i_A + (inputs[2] - inputs[0]) * i_B),
            Pe - Pm,
            Tm - (Te + Kp * (omega_ref - omega) + Ki * et),
            v_f - v_f0,
        ],
        algebraic_vars=[i_d, i_q, i_0, i_f, v_d, v_q, v_0, i_A, i_B, i_C, Te, Pe, Qe, Pm, Tm, v_f],
        in_vars=inputs,
        out_vars=[i_A, i_B, i_C, omega],
    )

    templ.block.diff_vars = [d_psi_d, d_psi_q, d_psi_0, d_psi_f, d_theta, d_omega, d_et, d_u_cos, d_u_sin]

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.P_N: None,
        VarPowerFlowReferenceType.Q_N: None,
        VarPowerFlowReferenceType.P_A: None,
        VarPowerFlowReferenceType.Q_A: None,
        VarPowerFlowReferenceType.P_B: None,
        VarPowerFlowReferenceType.Q_B: None,
        VarPowerFlowReferenceType.P_C: None,
        VarPowerFlowReferenceType.Q_C: None,
        VarPowerFlowReferenceType.i_N: None,
        VarPowerFlowReferenceType.i_A: i_A,
        VarPowerFlowReferenceType.i_B: i_B,
        VarPowerFlowReferenceType.i_C: i_C,
        VarPowerFlowReferenceType.phi_v: phi_v,
        VarPowerFlowReferenceType.phi: phi,
        VarPowerFlowReferenceType.Vpk: Vpk,
        VarPowerFlowReferenceType.Ipk: Ipk,
        VarPowerFlowReferenceType.d_v_N: None,
        VarPowerFlowReferenceType.d_v_A: None,
        VarPowerFlowReferenceType.d_v_B: None,
        VarPowerFlowReferenceType.d_v_C: None,
    }

    templ.block.event_dict = {
        H: vf.add_const(5.0),
        D: vf.add_const(2.0),
        La: vf.add_const(0.15),
        Lmq: vf.add_const(1.55),
        Lf: vf.add_const(0.10),
        Rf: vf.add_const(0.017),
        omega_ref: vf.add_const(1.0),
        Kp: vf.add_const(2.0),
        Ki: vf.add_const(2.0),
        v_f0: vf.add_const(-0.000006702),
        Lmd: Ld - La,
        phi_v: vf.add_const(None),
        phi: vf.add_const(None),
        Vpk: vf.add_const(None),
        Ipk: vf.add_const(None),
        delta: sym.atan((Ra * Ipk * sym.sin(phi) - omega * (Lmq + La) * Ipk * sym.cos(phi)) / (Vpk + Ra * Ipk * sym.cos(phi) + omega * (Lmq + La) * Ipk * sym.sin(phi))),
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
        et: vf.add_const(0.0),
        omega: omega_ref,
        theta: phi_v + delta,
        u_cos: sym.cos(theta),
        u_sin: sym.sin(theta),
        v_d: 2 / 3 * (u_sin * inputs[0] + sin_t_m120 * inputs[1] + sin_t_p120 * inputs[2]),
        v_q: 2 / 3 * (u_cos * inputs[0] + cos_t_m120 * inputs[1] + cos_t_p120 * inputs[2]),
        v_0: (1 / 3) * (inputs[0] + inputs[1] + inputs[2]),
        i_d: 2 / 3 * (u_sin * i_A + sin_t_m120 * i_B + sin_t_p120 * i_C),
        i_q: 2 / 3 * (u_cos * i_A + cos_t_m120 * i_B + cos_t_p120 * i_C),
        i_0: (1 / 3) * (i_A + i_B + i_C),
        psi_q: (v_d + Ra * i_d),
        psi_d: -(v_q + Ra * i_q),
        psi_0: -L0 * i_0,
        i_f: (psi_d + (Lmd + La) * i_d) / Lmd,
        v_f: i_f * Rf,
        psi_f: (Lmd + Lf) * i_f - Lmd * i_d,
        Pe: (i_A * inputs[0] + i_B * inputs[1] + i_C * inputs[2]),
        Qe: (1 / np.sqrt(3)) * ((inputs[0] - inputs[1]) * i_C + (inputs[1] - inputs[2]) * i_A + (inputs[2] - inputs[0]) * i_B),
        Te: (3 / 2) * (psi_q * i_d - psi_d * i_q),
        Pm: Pe,
    }

    c0 = vf.add_const(0.0)
    templ.block.diff_init_eqs = {
        d_theta: omega_base * omega,
        d_et: (omega_ref - omega),
        d_omega: c0,
        d_psi_d: c0,
        d_psi_q: c0,
        d_psi_0: c0,
        d_psi_f: c0,
        d_u_cos: -(omega_base * omega) * u_sin,
        d_u_sin: (omega_base * omega) * u_cos,
    }

    return templ


def get_simple_multilinear_generator_reference_template(
    vf: VarFactory,
    name: str = "complete_generator_emt_template_ml",
) -> EmtModelTemplate:
    templ = EmtModelTemplate(name=name)
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name
    templ.block.name = name

    gen_mdl = get_simple_generator_emt_template_trig_transform(vf=vf).block
    exciter_mdl = get_exciter_emt(vf=vf).block
    governor_mdl = get_governor_emt(vf=vf).block
    stabilizer_mdl = get_stabilizer_emt(vf=vf).block

    gen_i_f = find_name_in_block("i_f", gen_mdl)
    gen_te = find_name_in_block("Te", gen_mdl)
    gen_omega = find_name_in_block("omega", gen_mdl)

    vf.add_connections([gen_mdl.in_vars[4]], [exciter_mdl.out_vars[0]])
    vf.add_connections([exciter_mdl.in_vars[0]], [gen_i_f])
    vf.add_connections([exciter_mdl.in_vars[1]], [gen_mdl.in_vars[0]])
    vf.add_connections([exciter_mdl.in_vars[2]], [gen_mdl.in_vars[1]])
    vf.add_connections([exciter_mdl.in_vars[3]], [gen_mdl.in_vars[2]])
    vf.add_connections([exciter_mdl.in_vars[4]], [stabilizer_mdl.out_vars[0]])

    vf.add_connections([stabilizer_mdl.in_vars[0]], [gen_omega])

    vf.add_connections([gen_mdl.in_vars[3]], [governor_mdl.out_vars[0]])
    vf.add_connections([governor_mdl.in_vars[0]], [gen_omega])
    vf.add_connections([governor_mdl.in_vars[1]], [gen_te])

    templ.block.children.append(gen_mdl)
    templ.block.children.append(governor_mdl)
    templ.block.children.append(stabilizer_mdl)
    templ.block.children.append(exciter_mdl)
    templ.block.unify_blocks()

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_N: None,
        VarPowerFlowReferenceType.v_A: gen_mdl.in_vars[0],
        VarPowerFlowReferenceType.v_B: gen_mdl.in_vars[1],
        VarPowerFlowReferenceType.v_C: gen_mdl.in_vars[2],
        VarPowerFlowReferenceType.P_N: None,
        VarPowerFlowReferenceType.Q_N: None,
        VarPowerFlowReferenceType.P_A: None,
        VarPowerFlowReferenceType.Q_A: None,
        VarPowerFlowReferenceType.P_B: None,
        VarPowerFlowReferenceType.Q_B: None,
        VarPowerFlowReferenceType.P_C: None,
        VarPowerFlowReferenceType.Q_C: None,
        VarPowerFlowReferenceType.i_N: None,
        VarPowerFlowReferenceType.i_A: gen_mdl.out_vars[0],
        VarPowerFlowReferenceType.i_B: gen_mdl.out_vars[1],
        VarPowerFlowReferenceType.i_C: gen_mdl.out_vars[2],
        VarPowerFlowReferenceType.phi_v: gen_mdl.in_vars[5],
        VarPowerFlowReferenceType.phi: gen_mdl.in_vars[6],
        VarPowerFlowReferenceType.Vpk: gen_mdl.in_vars[7],
        VarPowerFlowReferenceType.Ipk: gen_mdl.in_vars[8],
        VarPowerFlowReferenceType.d_v_N: None,
        VarPowerFlowReferenceType.d_v_A: None,
        VarPowerFlowReferenceType.d_v_B: None,
        VarPowerFlowReferenceType.d_v_C: None,
    }

    templ.block.in_vars = [gen_mdl.in_vars[0], gen_mdl.in_vars[1], gen_mdl.in_vars[2]]
    templ.block.out_vars = [gen_mdl.out_vars[0], gen_mdl.out_vars[1], gen_mdl.out_vars[2]]

    return templ


def get_complete_generator_template_emt_trig_transform(
    vf: VarFactory,
    name: str = "complete_generator_emt_template_ml",
) -> EmtModelTemplate:
    """
    Backward-compatible alias for multilinear reference complete generator.
    """
    return get_simple_multilinear_generator_reference_template(vf=vf, name=name)
