# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


import numpy as np
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_pf_positive_sequence_init_refs
from VeraGridEngine.enumerations import VarPowerFlowReferenceType, DeviceType, ParamPowerFlowReferenceType



# def get_simple_generator_emt_template(vf: VarFactory, name: str = "simple_emt_type_generator_template") -> EmtModelTemplate:
#     """
#     EMT type machine model without damping effects.
#     :param vf: grid.var_factory
#     :param name: string to identify the generator and model
#     :return: EmtModelTemplate
#     """
#
#     templ = EmtModelTemplate()
#     templ.tpe = DeviceType.GeneratorDevice
#     templ.name = name
#     templ.block.name = name
#
#     # --------------------------------------------------------------------------------------
#     # Inputs: instantaneous abc terminal voltages in pu (at bus)
#     # --------------------------------------------------------------------------------------
#     v_A = vf.add_var(name=f"v_A", reference= VarPowerFlowReferenceType.v_A)
#     v_B = vf.add_var(name=f"v_B", reference= VarPowerFlowReferenceType.v_B)
#     v_C = vf.add_var(name=f"v_C", reference= VarPowerFlowReferenceType.v_C)
#     Tm = vf.add_var(name=f"Tm")
#     v_f = vf.add_var(name=f"v_f")
#
#     # to connect complete block with gen block
#     Ipk = vf.add_var(name="Ipk", reference= VarPowerFlowReferenceType.Ipk)
#     Vpk = vf.add_var(name="Vpk", reference= VarPowerFlowReferenceType.Vpk)
#     phi = vf.add_var(name="phi", reference= VarPowerFlowReferenceType.phi)
#     phi_v = vf.add_var(name="phi_v", reference= VarPowerFlowReferenceType.phi_v)
#     inputs = [v_A, v_B, v_C]
#     # --------------------------------------------------------------------------------------
#     # States (pu, except theta [rad])
#     # --------------------------------------------------------------------------------------
#
#     theta = vf.add_var("theta_" + name)  # electrical angle [rad]
#     omega = vf.add_var(name=f"omega")  # speed [pu]
#     psi_d = vf.add_var("psi_d_" + name)  # flux linkages [pu] on psi_base = Vbase/omega_base
#     psi_q = vf.add_var("psi_q_" + name)
#     psi_f = vf.add_var("psi_f_" + name)
#     psi_0 = vf.add_var("psi_0_" + name)
#     et    = vf.add_var("et_" + name)     # PI integrator state (units: pu*s or equivalent)
#
#
#     # Diff vars (derivatives)
#     d_omega = vf.add_diff_var(name = f"d_omega", base_var=omega)
#     d_theta = vf.add_diff_var(name = f"d_theta", base_var=theta)
#     d_psi_d = vf.add_diff_var(name = f"d_psi_d", base_var=psi_d)
#     d_psi_q = vf.add_diff_var(name = f"d_psi_q", base_var=psi_q)
#     d_psi_0 = vf.add_diff_var(name = f"d_psi_0", base_var=psi_0)
#     d_psi_f = vf.add_diff_var(name = f"d_psi_f", base_var=psi_f)
#     d_et    = vf.add_diff_var(name = f"d_et", base_var=et)
#
#     # --------------------------------------------------------------------------------------
#     # Algebraic eqs
#     # --------------------------------------------------------------------------------------
#     i_A = vf.add_var(name=f"i_A", reference= VarPowerFlowReferenceType.i_A)
#     i_B = vf.add_var(name=f"i_B", reference= VarPowerFlowReferenceType.i_B)
#     i_C = vf.add_var(name=f"i_C", reference= VarPowerFlowReferenceType.i_C)
#
#     # dq0 voltages
#     v_d = vf.add_var("v_d_" + name)
#     v_q = vf.add_var("v_q_" + name)
#     v_0 = vf.add_var("v_0_" + name)
#
#     # dq0 currents
#     i_d = vf.add_var("i_d_" + name)
#     i_q = vf.add_var("i_q_" + name)
#     i_0 = vf.add_var("i_0_" + name)
#
#     # field
#     i_f = vf.add_var(name=f"i_f")
#
#     # powers/torques
#     Te = vf.add_var("Te_" + name)
#     Pe = vf.add_var("Pe_" + name)
#     Qe = vf.add_var("Qe_" + name)
#     Pm = vf.add_var("Pm_" + name)
#
#     # --------------------------------------------------------------------------------------
#     # Parameters
#     # --------------------------------------------------------------------------------------
#     omega_base = vf.add_var("omega_base")
#     H = vf.add_var("H")
#     D = vf.add_var("D")
#
#     Ra  = vf.add_var("Ra")
#     La  = vf.add_var("La")
#     Ld  = vf.add_var("Ld")
#     Lmd = vf.add_var("Lmd")
#     Lmq = vf.add_var("Lmq")
#     Lf  = vf.add_var("Lf")
#     Rf  = vf.add_var("Rf")
#     R0  = vf.add_var("R0")
#     L0  = vf.add_var("L0")
#
#     omega_ref = vf.add_var("omega_ref")  # pu
#     delta = vf.add_var("delta_" + name)  # difference between rotor angle and grid angle
#
#     Kp = vf.add_var("Kp")
#     Ki = vf.add_var("Ki")
#
#     v_f0 = vf.add_var("v_f0")  # temporary fixed exciter output
#
#     templ.block = Block(
#         # --------------------------------------------------------------------------------------
#         # STATE EQUATIONS (seconds + pu)
#         # --------------------------------------------------------------------------------------
#         state_eqs=[
#             -v_d - Ra * i_d + omega * psi_q,
#             -v_q - Ra * i_q - omega * psi_d,
#             -v_0 - R0 * i_0,
#             v_f - Rf * i_f,
#             omega_base * omega,
#             (Tm - Te - D * (omega - omega_ref)) / (2 * H),
#             omega_base * (omega_ref - omega),
#         ],
#         state_vars=[psi_d, psi_q, psi_0, psi_f, theta, omega, et],
#
#         # --------------------------------------------------------------------------------------
#         # ALGEBRAIC EQUATIONS
#         # --------------------------------------------------------------------------------------
#         algebraic_eqs=[
#             psi_d - (Lmd * i_f - (Lmd + La) * i_d),
#             psi_q - (-(Lmq + La) * i_q),
#             psi_0 - (-L0 * i_0),
#             psi_f - ((Lmd + Lf) * i_f - Lmd * i_d),
#
#             v_d - (2 / 3) * (
#                     inputs[0] * sym.sin(theta) +
#                     inputs[1] * sym.sin(theta - 2 * np.pi / 3) +
#                     inputs[2] * sym.sin(theta + 2 * np.pi / 3)),
#             v_q - (2 / 3) * (
#                     inputs[0] * sym.cos(theta) +
#                     inputs[1] * sym.cos(theta - 2 * np.pi / 3) +
#                     inputs[2] * sym.cos(theta + 2 * np.pi / 3)),
#             v_0 - (1 / 3) * (inputs[0] + inputs[1] + inputs[2]),
#
#             i_A - (i_d * sym.sin(theta) + i_q * sym.cos(theta) + i_0),
#             i_B - (i_d * sym.sin(theta - 2 * np.pi / 3) + i_q * sym.cos(theta - 2 * np.pi / 3) + i_0),
#             i_C - (i_d * sym.sin(theta + 2 * np.pi / 3) + i_q * sym.cos(theta + 2 * np.pi / 3) + i_0),
#
#             Te - (3 / 2) * (psi_q * i_d - psi_d * i_q),
#             Pe - (i_A * inputs[0] + i_B * inputs[1] + i_C * inputs[2]),
#             Qe - (1 / np.sqrt(3)) * ((inputs[0] - inputs[1]) * i_C +
#                                      (inputs[1] - inputs[2]) * i_A +
#                                      (inputs[2] - inputs[0]) * i_B),
#             Pe - Pm,
#             Tm - (Te + Kp * (omega_ref - omega) + Ki * et),
#             v_f - v_f0,
#         ],
#         algebraic_vars=[
#             i_d, i_q, i_0, i_f,
#             v_d, v_q, v_0,
#             i_A, i_B, i_C,
#             Te, Pe, Qe, Pm,Tm, v_f,
#         ],
#         in_vars=inputs,
#         out_vars=[i_A, i_B, i_C, omega],
#         # out_vars=[i_A, i_B, i_C],
#     )
#
#     templ.block.diff_vars = [d_psi_d, d_psi_q, d_psi_0, d_psi_f, d_theta, d_omega, d_et]
#
#     # --------------------------------------------------------------------------------------
#     # external mapping
#     # --------------------------------------------------------------------------------------
#
#     templ.block.external_mapping = {
#         VarPowerFlowReferenceType.v_N: None,
#         VarPowerFlowReferenceType.v_A: v_A,
#         VarPowerFlowReferenceType.v_B: v_B,
#         VarPowerFlowReferenceType.v_C: v_C,
#         VarPowerFlowReferenceType.P_N: None,
#         VarPowerFlowReferenceType.Q_N: None,
#         VarPowerFlowReferenceType.P_A: None,
#         VarPowerFlowReferenceType.Q_A: None,
#         VarPowerFlowReferenceType.P_B: None,
#         VarPowerFlowReferenceType.Q_B: None,
#         VarPowerFlowReferenceType.P_C: None,
#         VarPowerFlowReferenceType.Q_C: None,
#         VarPowerFlowReferenceType.i_N: None,
#         VarPowerFlowReferenceType.i_A: i_A,
#         VarPowerFlowReferenceType.i_B: i_B,
#         VarPowerFlowReferenceType.i_C: i_C,
#         VarPowerFlowReferenceType.phi_v: phi_v,
#         VarPowerFlowReferenceType.phi: phi,
#         VarPowerFlowReferenceType.Vpk: Vpk,
#         VarPowerFlowReferenceType.Ipk: Ipk,
#         VarPowerFlowReferenceType.d_v_N: None,
#         VarPowerFlowReferenceType.d_v_A: None,
#         VarPowerFlowReferenceType.d_v_B: None,
#         VarPowerFlowReferenceType.d_v_C: None,
#     }
#
#
#     # --------------------------------------------------------------------------------------
#     # Event dict (constants)
#     # --------------------------------------------------------------------------------------
#
#     templ.block.event_dict = {
#         H:          vf.add_const(5.0),
#         D:          vf.add_const(2.0),
#         La:         vf.add_const(0.15),
#         Lmq:        vf.add_const(1.55),
#         Lf:         vf.add_const(0.10),
#         Rf:         vf.add_const(0.017),
#         R0:         vf.add_const(0.001),
#         omega_ref:  vf.add_const(1.0),
#         Kp:         vf.add_const(2.0),
#         Ki:         vf.add_const(2.0),
#         v_f0:       vf.add_const(-0.000006702),
#         Lmd: Ld - La,
#         # init-only external auxiliary values
#         phi_v: vf.add_const(None),
#         phi: vf.add_const(None),
#         Vpk: vf.add_const(None),
#         Ipk: vf.add_const(None),
#         # delta: vf.add_const(None),
#         # delta: sym.atan(
#         #     (Ra * Ipk * sym.sin(phi) - omega * (Lmq + La) * Ipk * sym.cos(phi)) /
#         #     (Vpk + Ra * Ipk * sym.cos(phi) + omega * (Lmq + La) * Ipk * sym.sin(phi))
#         # ),
#         delta: sym.atan(
#             (Ra * Ipk * sym.sin(phi) - omega_ref * (Lmq + La) * Ipk * sym.cos(phi)) /
#             (Vpk + Ra * Ipk * sym.cos(phi) + omega_ref * (Lmq + La) * Ipk * sym.sin(phi))
#         ),
#     }
#     templ.block.api_obj_mapping = {
#         ParamPowerFlowReferenceType.omega_base : omega_base,
#         ParamPowerFlowReferenceType.R1: Ra,
#         ParamPowerFlowReferenceType.X1: Ld,
#         ParamPowerFlowReferenceType.X0: L0,
#     }
#
#     # --------------------------------------------------------------------------------------
#     # INIT EQUATIONS
#     # --------------------------------------------------------------------------------------
#
#     templ.block.init_eqs = {
#         et: vf.add_const(0.0),
#         omega: omega_ref,
#
#         theta: phi_v + delta,
#
#         v_d: 2 / 3 * (sym.sin(theta) * inputs[0] +
#                       sym.sin(theta - 2 * np.pi / 3) * inputs[1] +
#                       sym.sin(theta + 2 * np.pi / 3) * inputs[2]),
#         v_q: 2 / 3 * (sym.cos(theta) * inputs[0] +
#                       sym.cos(theta - 2 * np.pi / 3) * inputs[1] +
#                       sym.cos(theta + 2 * np.pi / 3) * inputs[2]),
#         v_0: (1 / 3) * (inputs[0] + inputs[1] + inputs[2]),
#
#         i_d: 2 / 3 * (sym.sin(theta) * i_A +
#                       sym.sin(theta - 2 * np.pi / 3) * i_B +
#                       sym.sin(theta + 2 * np.pi / 3) * i_C),
#         i_q: 2 / 3 * (sym.cos(theta) * i_A +
#                       sym.cos(theta - 2 * np.pi / 3) * i_B +
#                       sym.cos(theta + 2 * np.pi / 3) * i_C),
#         i_0: (1 / 3) * (i_A + i_B + i_C),
#
#         psi_q: (v_d + Ra * i_d),
#         psi_d: -(v_q + Ra * i_q),
#         psi_0: -L0 * i_0,
#
#         i_f: (psi_d + (Lmd + La) * i_d) / Lmd,
#         v_f: i_f * Rf,
#         psi_f: (Lmd + Lf) * i_f - Lmd * i_d,
#
#         Pe: (i_A * inputs[0] + i_B * inputs[1] + i_C * inputs[2]),
#         Qe: (1 / np.sqrt(3)) * ((inputs[0] - inputs[1]) * i_C +
#                                      (inputs[1] - inputs[2]) * i_A +
#                                      (inputs[2] - inputs[0]) * i_B),
#
#         Te: (3 / 2) * (psi_q * i_d - psi_d * i_q),
#         Pm: Pe,
#
#
#     }
#
#     # --------------------------------------------------------------------------------------
#     # DIFF INIT EQS
#     # --------------------------------------------------------------------------------------
#     c0 = vf.add_const(0.0)
#     templ.block.diff_init_eqs = {
#         d_theta: omega_base*omega,
#         d_et: (omega_ref - omega),
#         d_omega: c0,
#         d_psi_d: c0,
#         d_psi_q: c0,
#         d_psi_0: c0,
#         d_psi_f: c0,
#     }
#
#     return templ

def get_simple_generator_emt_template(vf: VarFactory, name: str = "simple_emt_type_generator_template") -> EmtModelTemplate:
    """
    EMT type machine model without damping effects.
    :param vf: grid.var_factory
    :param name: string to identify the generator and model
    :return: EmtModelTemplate
    """

    templ = EmtModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name
    templ.block.name = name

    # --------------------------------------------------------------------------------------
    # Inputs: instantaneous abc terminal voltages in pu (at bus)
    # --------------------------------------------------------------------------------------
    v_A = vf.add_var(name=f"v_A", reference= VarPowerFlowReferenceType.v_A)
    v_B = vf.add_var(name=f"v_B", reference= VarPowerFlowReferenceType.v_B)
    v_C = vf.add_var(name=f"v_C", reference= VarPowerFlowReferenceType.v_C)
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
    inputs = [v_A, v_B, v_C]
    # --------------------------------------------------------------------------------------
    # States (pu, except theta [rad])
    # --------------------------------------------------------------------------------------

    theta = vf.add_var("theta_" + name)  # electrical angle [rad]
    omega = vf.add_var(name=f"omega")  # speed [pu]
    psi_d = vf.add_var("psi_d_" + name)  # flux linkages [pu] on psi_base = Vbase/omega_base
    psi_q = vf.add_var("psi_q_" + name)
    psi_f = vf.add_var("psi_f_" + name)
    psi_0 = vf.add_var("psi_0_" + name)
    et    = vf.add_var("et_" + name)     # PI integrator state (units: pu*s or equivalent)


    # Diff vars (derivatives)
    d_omega = vf.add_diff_var(name = f"d_omega", base_var=omega)
    d_theta = vf.add_diff_var(name = f"d_theta", base_var=theta)
    d_psi_d = vf.add_diff_var(name = f"d_psi_d", base_var=psi_d)
    d_psi_q = vf.add_diff_var(name = f"d_psi_q", base_var=psi_q)
    d_psi_0 = vf.add_diff_var(name = f"d_psi_0", base_var=psi_0)
    d_psi_f = vf.add_diff_var(name = f"d_psi_f", base_var=psi_f)
    d_et    = vf.add_diff_var(name = f"d_et", base_var=et)

    # --------------------------------------------------------------------------------------
    # Algebraic eqs
    # --------------------------------------------------------------------------------------
    i_A = vf.add_var(name=f"i_A", reference= VarPowerFlowReferenceType.i_A)
    i_B = vf.add_var(name=f"i_B", reference= VarPowerFlowReferenceType.i_B)
    i_C = vf.add_var(name=f"i_C", reference= VarPowerFlowReferenceType.i_C)

    # dq0 voltages
    v_d = vf.add_var("v_d_" + name)
    v_q = vf.add_var("v_q_" + name)
    v_0 = vf.add_var("v_0_" + name)

    # dq0 currents
    i_d = vf.add_var("i_d_" + name)
    i_q = vf.add_var("i_q_" + name)
    i_0 = vf.add_var("i_0_" + name)

    # field
    i_f = vf.add_var(name=f"i_f")

    # powers/torques
    Te = vf.add_var("Te_" + name)
    Pe = vf.add_var("Pe_" + name)
    Qe = vf.add_var("Qe_" + name)
    Pm = vf.add_var("Pm_" + name)

    # --------------------------------------------------------------------------------------
    # Parameters
    # --------------------------------------------------------------------------------------
    omega_base = vf.add_var("omega_base_" + name)
    H = vf.add_var("H_" + name)
    D = vf.add_var("D_" + name)

    Ra  = vf.add_var("Ra_" + name)
    La  = vf.add_var("La_" + name)
    Ld  = vf.add_var("Ld_" + name)
    Lmd = vf.add_var("Lmd_" + name)
    Lmq = vf.add_var("Lmq_" + name)
    Lf  = vf.add_var("Lf_" + name)
    Rf  = vf.add_var("Rf_" + name)
    R0  = vf.add_var("R0_" + name)
    L0  = vf.add_var("L0_" + name)

    omega_ref = vf.add_var("omega_ref_" + name)  # pu
    delta = vf.add_var("delta_" + name)  # difference between rotor angle and grid angle

    # These symbolic expressions reconstruct the PF-consistent phasor quantities
    # from the seeded EMT voltage and power references. The expressions are used
    # later in ``init_eqs`` so runtime-parameter initialization does not depend on
    # bus algebraic variables that are not available yet.
    phi_v_init: sym.Expr
    phi_init: sym.Expr
    vpk_init: sym.Expr
    ipk_init: sym.Expr
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

    # These placeholders store the PF-consistent phasor quantities as runtime
    # parameters first. The initialization stage then resolves ``delta`` from the
    # stored values, which keeps the generator compatible with the EMT builder
    # ordering where bus voltages are initialized after runtime parameters.
    phi_v = vf.add_var("phi_v_" + name)
    phi = vf.add_var("phi_" + name)
    Vpk = vf.add_var("Vpk_" + name)
    Ipk = vf.add_var("Ipk_" + name)

    Kp = vf.add_var("Kp_" + name)
    Ki = vf.add_var("Ki_" + name)

    # v_f0 = vf.add_var("v_f0" + name)  # temporary fixed exciter output
    P_share_ref = vf.add_var("p_share_ref_" + name)
    Q_share_ref = vf.add_var("q_share_ref_" + name)
    Kq_share = vf.add_var("Kq_share_" + name)

    templ.block = Block(
        # --------------------------------------------------------------------------------------
        # STATE EQUATIONS (seconds + pu)
        # --------------------------------------------------------------------------------------
        state_eqs=[
            -v_d - Ra * i_d + omega * psi_q,
            -v_q - Ra * i_q - omega * psi_d,
            -v_0 - R0 * i_0,
            v_f - Rf * i_f,
            omega_base * omega,
            (Tm - Te - D * (omega - omega_ref)) / (2 * H),
            # omega_base * (omega_ref - omega),
            (omega_ref - omega),
        ],
        state_vars=[psi_d, psi_q, psi_0, psi_f, theta, omega, et],

        # --------------------------------------------------------------------------------------
        # ALGEBRAIC EQUATIONS
        # --------------------------------------------------------------------------------------
        algebraic_eqs=[
            psi_d - (Lmd * i_f - (Lmd + La) * i_d),
            psi_q - (-(Lmq + La) * i_q),
            psi_0 - (-L0 * i_0),
            psi_f - ((Lmd + Lf) * i_f - Lmd * i_d),

            v_d - (2 / 3) * (
                    inputs[0] * sym.sin(theta) +
                    inputs[1] * sym.sin(theta - 2 * np.pi / 3) +
                    inputs[2] * sym.sin(theta + 2 * np.pi / 3)),
            v_q - (2 / 3) * (
                    inputs[0] * sym.cos(theta) +
                    inputs[1] * sym.cos(theta - 2 * np.pi / 3) +
                    inputs[2] * sym.cos(theta + 2 * np.pi / 3)),
            v_0 - (1 / 3) * (inputs[0] + inputs[1] + inputs[2]),

            i_A - (i_d * sym.sin(theta) + i_q * sym.cos(theta) + i_0),
            i_B - (i_d * sym.sin(theta - 2 * np.pi / 3) + i_q * sym.cos(theta - 2 * np.pi / 3) + i_0),
            i_C - (i_d * sym.sin(theta + 2 * np.pi / 3) + i_q * sym.cos(theta + 2 * np.pi / 3) + i_0),

            # The EMT phase currents use the standard three-phase system base.
            # Divide the amplitude-preserving dq torque by three so it remains
            # on the same system power base as the mechanical-power reference.
            Te - (1 / 2) * (psi_q * i_d - psi_d * i_q),

            # Averaged active and reactive powers in the synchronous dq frame.
            # The raw abc/dq products are three times the per-unit power because
            # phase quantities use the total three-phase Sbase.
            Pe - ((1 / 2) * (v_d * i_d + v_q * i_q) + v_0 * i_0),
            Qe - ((1 / 2) * (v_q * i_d - v_d * i_q)),

            # Active-power sharing: the mechanical power setpoint is the assigned share.
            Pm - P_share_ref,

            # Governor acting around the assigned active-power share.
            Tm - (Pm + Kp * (omega_ref - omega) + Ki * et),

            # Reactive-power sharing through the excitation voltage.
            # At equilibrium, if Qe == Q_share_ref, then v_f = Rf * i_f and d_psi_f = 0.
            v_f - (Rf * i_f + Kq_share * (Q_share_ref - Qe)),
        ],
        algebraic_vars=[
            i_d, i_q, i_0, i_f,
            v_d, v_q, v_0,
            i_A, i_B, i_C,
            Te, Pe, Qe, Pm,Tm, v_f,
        ],
        in_vars=inputs,
        out_vars=[i_A, i_B, i_C, omega],
        # out_vars=[i_A, i_B, i_C],
    )

    templ.block.diff_vars = [d_psi_d, d_psi_q, d_psi_0, d_psi_f, d_theta, d_omega, d_et]

    # --------------------------------------------------------------------------------------
    # external mapping
    # --------------------------------------------------------------------------------------

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: v_A,
        VarPowerFlowReferenceType.v_B: v_B,
        VarPowerFlowReferenceType.v_C: v_C,
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
        VarPowerFlowReferenceType.phi_v: phi_v,
        VarPowerFlowReferenceType.phi: phi,
        VarPowerFlowReferenceType.Vpk: Vpk,
        VarPowerFlowReferenceType.Ipk: Ipk,
    }


    # --------------------------------------------------------------------------------------
    # Event dict (constants)
    # --------------------------------------------------------------------------------------

    templ.block.event_dict = {
        H:          vf.add_const(5.0),
        D:          vf.add_const(2.0),
        La:         vf.add_const(0.15),
        Lmq:        vf.add_const(1.55),
        Lf:         vf.add_const(0.10),
        Rf:         vf.add_const(0.017),
        omega_ref:  vf.add_const(1.0),
        Kp:         vf.add_const(2.0),
        Ki:         vf.add_const(2.0),
        # v_f0:       v_f,
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
        # PF-derived phasor expressions initialize their runtime parameters
        # before ``delta`` is consumed.
        phi_v: phi_v_init,
        phi: phi_init,
        Vpk: vpk_init,
        Ipk: ipk_init,
        # ``delta`` belongs to the runtime-parameter initialization graph and
        # depends on the PF-derived phasor expressions above.
        delta: sym.atan(
            (Ra * Ipk * sym.sin(phi) - omega_ref * (Lmq + La) * Ipk * sym.cos(phi)) /
            (Vpk + Ra * Ipk * sym.cos(phi) + omega_ref * (Lmq + La) * Ipk * sym.sin(phi))
        ),
        Kq_share: vf.add_const(0.2),
        # Sharing references are operating-point values, not static generator
        # attributes. The EMT seed path resolves both placeholders after PF.
        P_share_ref: vf.add_const(None),
        Q_share_ref: vf.add_const(None),
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
        ParamPowerFlowReferenceType.omega_base : omega_base,
        ParamPowerFlowReferenceType.R1: Ra,
        ParamPowerFlowReferenceType.X1: Ld,
        ParamPowerFlowReferenceType.X0: L0,
        ParamPowerFlowReferenceType.generator_share_p_ref: P_share_ref,
        ParamPowerFlowReferenceType.generator_share_q_ref: Q_share_ref,
    }

    # --------------------------------------------------------------------------------------
    # INIT EQUATIONS
    # --------------------------------------------------------------------------------------

    templ.block.init_eqs = {
        et: vf.add_const(0.0),
        omega: omega_ref,

        # The Park transform below defines the d axis with sine and the q axis
        # with cosine. Rotate the PF-derived electrical angle by 90 degrees so
        # the initialized dq fluxes satisfy the generator algebraic equations.
        theta: phi_v + delta + np.pi / 2.0,


        v_d: 2 / 3 * (sym.sin(theta) * inputs[0] +
                      sym.sin(theta - 2 * np.pi / 3) * inputs[1] +
                      sym.sin(theta + 2 * np.pi / 3) * inputs[2]),
        v_q: 2 / 3 * (sym.cos(theta) * inputs[0] +
                      sym.cos(theta - 2 * np.pi / 3) * inputs[1] +
                      sym.cos(theta + 2 * np.pi / 3) * inputs[2]),
        v_0: (1 / 3) * (inputs[0] + inputs[1] + inputs[2]),

        i_d: 2 / 3 * (sym.sin(theta) * i_A +
                      sym.sin(theta - 2 * np.pi / 3) * i_B +
                      sym.sin(theta + 2 * np.pi / 3) * i_C),
        i_q: 2 / 3 * (sym.cos(theta) * i_A +
                      sym.cos(theta - 2 * np.pi / 3) * i_B +
                      sym.cos(theta + 2 * np.pi / 3) * i_C),
        i_0: (1 / 3) * (i_A + i_B + i_C),

        psi_q: (v_d + Ra * i_d),
        psi_d: -(v_q + Ra * i_q),
        psi_0: -L0 * i_0,

        i_f: (psi_d + (Lmd + La) * i_d) / Lmd,
        # v_f: i_f * Rf,
        psi_f: (Lmd + Lf) * i_f - Lmd * i_d,

        # Use the same three-phase-base normalization as the runtime equations
        # so explicit initialization starts with Pe/Pm and Qe/Qref aligned.
        Pe: ((1 / 2) * (v_d * i_d + v_q * i_q) + v_0 * i_0),
        Qe: ((1 / 2) * (v_q * i_d - v_d * i_q)),
        Pm: P_share_ref,

        Te: (1 / 2) * (psi_q * i_d - psi_d * i_q),
        v_f: (Rf * i_f + Kq_share * (Q_share_ref - Qe)),
    }

    # --------------------------------------------------------------------------------------
    # DIFF INIT EQS
    # --------------------------------------------------------------------------------------
    c0 = vf.add_const(0.0)
    templ.block.diff_init_eqs = {
        d_theta: omega_base*omega,
        d_et: (omega_ref - omega),
        d_omega: c0,
        d_psi_d: c0,
        d_psi_q: c0,
        d_psi_0: c0,
        d_psi_f: c0,
    }

    return templ

