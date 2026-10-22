# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Any, List

import numpy as np

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.enumerations import (
    DeviceType,
    ParamPowerFlowReferenceType,
    VarPowerFlowReferenceType,
)
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Utils.Symbolic.block import Block


def get_gfm_emt_template(vf: VarFactory, name: str = "VSC_GridForming") -> EmtModelTemplate:
    """
    Build a three-phase EMT grid-forming VSC.

    The converter is represented as a balanced internal source behind a
    series RL. The grid-forming behaviour comes from two simple droops:

    * P-f droop: ``d_omega/dt = (omega_setpoint - omega) / tau_omega`` with
      ``omega_setpoint = omega_ref - Kdp * (Pe - P_ref)``.
    * Q-V droop: ``d_Epk/dt = (Epk_setpoint - Epk) / tau_v`` with
      ``Epk_setpoint = V_ref - Kdq * (Qe - Q_ref)``.

    The DC side is modelled as a stiff voltage input. The PF / EMT bridge
    populates the positive-sequence references ``Vpk``, ``phi_v``, ``Ipk``
    and ``phi`` (via ``_set_vsc_pf_positive_sequence``). Every initial
    value of the EMT problem is derived analytically from those four PF
    quantities so the model starts exactly on the steady-state sinusoidal
    trajectory and stays there until a disturbance arrives.

    Convention of the PF references:

    * ``Vpk`` :   peak per-phase voltage in pu  (``sqrt(2) * |V1|``).
    * ``phi_v``: phasor angle of the positive-sequence voltage.
    * ``Ipk`` :   peak per-phase current in pu  (``sqrt(2) * |I1|``).
    * ``phi``  : ``phi_I - phi_V`` with ``I = conj(S / V)`` so ``I`` is
                in the VSC branch convention "current from bus into the
                converter". For generation, ``phi`` is close to ``pi``.

    :param vf: EMT variable factory.
    :param name: Symbolic block name suffix.
    :return: Configured EMT template.
    """
    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.VscDevice
    templ.name = name
    templ.block.name = name

    # Inputs: instantaneous abc bus voltages + DC bus voltage.
    v_A = vf.add_var(name=f"v_A", reference=VarPowerFlowReferenceType.v_A)
    v_B = vf.add_var(name=f"v_B", reference=VarPowerFlowReferenceType.v_B)
    v_C = vf.add_var(name=f"v_C", reference=VarPowerFlowReferenceType.v_C)
    v_dc = vf.add_var(name=f"v_dc", reference=VarPowerFlowReferenceType.Vdc)
    inputs: List[Any] = [v_A, v_B, v_C, v_dc]

    # States: three phase currents, internal angle, frequency, EMF.
    i_A = vf.add_var(name=f"i_A", reference=VarPowerFlowReferenceType.i_A)
    i_B = vf.add_var(name=f"i_B", reference=VarPowerFlowReferenceType.i_B)
    i_C = vf.add_var(name=f"i_C", reference=VarPowerFlowReferenceType.i_C)
    theta = vf.add_var(name=f"theta")
    omega = vf.add_var(name=f"omega")
    Epk = vf.add_var(name=f"Epk")

    d_i_A = vf.add_diff_var(name=f"d_i_A", base_var=i_A)
    d_i_B = vf.add_diff_var(name=f"d_i_B", base_var=i_B)
    d_i_C = vf.add_diff_var(name=f"d_i_C", base_var=i_C)
    d_theta = vf.add_diff_var(name=f"d_theta", base_var=theta)
    d_omega = vf.add_diff_var(name=f"d_omega", base_var=omega)
    d_Epk = vf.add_diff_var(name=f"d_Epk", base_var=Epk)

    # Algebraic variables: internal EMFs, powers.
    e_A = vf.add_var(name=f"e_A")
    e_B = vf.add_var(name=f"e_B")
    e_C = vf.add_var(name=f"e_C")
    Pe = vf.add_var(name=f"Pe")
    Qe = vf.add_var(name=f"Qe")
    # DC-side current injection (branch ``if_dc`` terminal). It closes the DC
    # bus KCL when the VSC is connected to a real DC bus (e.g. through the GUI
    # branch connector). Defined by the lossless power balance below.
    i_dc = vf.add_var(name=f"i_dc", reference=VarPowerFlowReferenceType.Idc)

    # Static parameters and droop / control set-points.
    omega_base = vf.add_var(name=f"omega_base")
    R_s = vf.add_var(name=f"R_s")
    X_s = vf.add_var(name=f"X_s")
    Kdp = vf.add_var(name=f"Kdp")
    Kdq = vf.add_var(name=f"Kdq")
    tau_omega = vf.add_var(name=f"tau_omega")
    tau_v = vf.add_var(name=f"tau_v")
    omega_ref = vf.add_var(name=f"omega_ref")
    P_ref = vf.add_var(name=f"P_ref")
    Q_ref = vf.add_var(name=f"Q_ref")
    V_ref = vf.add_var(name=f"V_ref")
    Qf = vf.add_var(name=f"Qf")

    # PF positive-sequence references. The EMT bridge populates these
    # through ``_set_vsc_pf_positive_sequence`` when they are exposed in
    # the external mapping below. They are the SINGLE source of truth for
    # the EMT initialization — every initial value is derived from them.
    Vpk_ref = vf.add_var(name=f"Vpk_ref")
    phi_v_ref = vf.add_var(name=f"phi_v_ref")
    Ipk_ref = vf.add_var(name=f"Ipk_ref")
    phi_ref = vf.add_var(name=f"phi_ref")

    # Instantaneous algebraic expressions (used at runtime, NOT for init).
    # Phase currents use the system three-phase current base. The abc sum
    # is three times total three-phase per-unit power on that base.
    Pe_expr = -(i_A * v_A + i_B * v_B + i_C * v_C) / 3.0
    Qe_expr = (-(1.0 / np.sqrt(3.0)) * (
        (v_A - v_B) * i_C
        + (v_B - v_C) * i_A
        + (v_C - v_A) * i_B
    )) / 3.0

    two_pi_over_3: float = 2.0 * np.pi / 3.0

    # --------------------------------------------------------------
    # Initialization derived analytically from the PF positive-
    # sequence references.
    #
    # Sin-convention sinusoid sample at ``t = 0``:
    #     v_a(t)  = Vpk * sin(omega * t + phi_v)
    #     i_a(t)  = Ipk * sin(omega * t + phi_v + phi)
    #
    # Per-phase peak voltage and current samples at ``t = 0``:
    theta_i_init_expr = phi_v_ref + phi_ref

    v_A_init_expr = Vpk_ref * sym.sin(phi_v_ref)
    v_B_init_expr = Vpk_ref * sym.sin(phi_v_ref - two_pi_over_3)
    v_C_init_expr = Vpk_ref * sym.sin(phi_v_ref + two_pi_over_3)

    i_A_init_expr = Ipk_ref * sym.sin(theta_i_init_expr)
    i_B_init_expr = Ipk_ref * sym.sin(theta_i_init_expr - two_pi_over_3)
    i_C_init_expr = Ipk_ref * sym.sin(theta_i_init_expr + two_pi_over_3)

    # EMF peak phasor (peak units, sin convention):
    #     E_phasor_peak = V_phasor_peak - Z * I_phasor_peak
    # where Z = R + j*X and the phasors are
    #     V_phasor_peak = Vpk * exp(j * phi_v)
    #     I_phasor_peak = Ipk * exp(j * (phi_v + phi))
    V_re_expr = Vpk_ref * sym.cos(phi_v_ref)
    V_im_expr = Vpk_ref * sym.sin(phi_v_ref)
    I_re_expr = Ipk_ref * sym.cos(theta_i_init_expr)
    I_im_expr = Ipk_ref * sym.sin(theta_i_init_expr)

    ZI_re_expr = R_s * I_re_expr - X_s * I_im_expr
    ZI_im_expr = R_s * I_im_expr + X_s * I_re_expr

    E_re_expr = V_re_expr - ZI_re_expr
    E_im_expr = V_im_expr - ZI_im_expr

    c_eps = vf.add_const(1.0e-24)
    Epk_init_expr = sym.sqrt(E_re_expr * E_re_expr
                             + E_im_expr * E_im_expr + c_eps)
    theta_init_expr = sym.atan2(E_im_expr, E_re_expr)

    e_A_init_expr = Epk_init_expr * sym.sin(theta_init_expr)
    e_B_init_expr = Epk_init_expr * sym.sin(theta_init_expr - two_pi_over_3)
    e_C_init_expr = Epk_init_expr * sym.sin(theta_init_expr + two_pi_over_3)

    # Average 3-ph powers for balanced steady state in branch convention.
    # For balanced sinusoids in sin convention (sin(omega*t + phi_*)):
    #     i_a·v_a + i_b·v_b + i_c·v_c        = (3/2)·Vpk·Ipk·cos(phi)
    #     (1/√3)·Σ (v_a−v_b)·i_c            = -(3/2)·Vpk·Ipk·sin(phi)
    # Divide the abc sums by three to report total system-base power:
    #     Pe_steady = -(1/2)·Vpk·Ipk·cos(phi)
    #     Qe_steady = +(1/2)·Vpk·Ipk·sin(phi)
    # For generation, ``phi ≈ π`` so ``cos(phi) < 0`` and ``Pe > 0``;
    # the small imaginary part of the PF current phasor gives the
    # observed sign of ``Qe``.
    c_1_2 = vf.add_const(0.5)
    Pe_init_expr = -c_1_2 * Vpk_ref * Ipk_ref * sym.cos(phi_ref)
    Qe_init_expr = c_1_2 * Vpk_ref * Ipk_ref * sym.sin(phi_ref)

    # Classic droop differential equations: ``P_ref`` and ``Q_ref`` are
    # constants pinned at init to the PF operating point ``Pe_init`` /
    # ``Qe_init``. With matched load models in PF and EMT, this gives an
    # exactly flat start (droop input ``Pe - P_ref = 0`` at ``t = 0``)
    # and a textbook post-event response with permanent droop offset
    # ``Δomega = -Kdp · ΔPe``.
    state_eqs: List[Any] = [
        omega_base * (v_A - R_s * i_A - e_A) / X_s,
        omega_base * (v_B - R_s * i_B - e_B) / X_s,
        omega_base * (v_C - R_s * i_C - e_C) / X_s,
        omega_base * omega,
        ((omega_ref - Kdp * (Pe - P_ref)) - omega) / tau_omega,
        ((V_ref - Kdq * (Qe - Q_ref)) - Epk) / tau_v,
    ]
    state_vars: List[Any] = [i_A, i_B, i_C, theta, omega, Epk]

    # Algebraic equations.
    algebraic_eqs: List[Any] = [
        e_A - Epk * sym.sin(theta),
        e_B - Epk * sym.sin(theta - two_pi_over_3),
        e_C - Epk * sym.sin(theta + two_pi_over_3),
        Pe - Pe_expr,
        Qe - Qe_expr,
        # DC current enters the branch from its DC bus. Positive AC export
        # therefore requires positive DC import: v_dc * i_dc = Pe.
        i_dc * v_dc - Pe,
    ]
    algebraic_vars: List[Any] = [
        e_A, e_B, e_C,
        Pe, Qe, i_dc,
    ]

    converter_block = Block(
        state_eqs=state_eqs,
        state_vars=state_vars,
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=algebraic_vars,
        in_vars=inputs,
        out_vars=[i_A, i_B, i_C, i_dc],
    )

    converter_block.diff_vars = [d_i_A, d_i_B, d_i_C, d_theta, d_omega, d_Epk]

    # External mapping. The four ``Vpk`` / ``phi_v`` / ``Ipk`` / ``phi``
    # entries are what the EMT bridge populates from the PF positive-
    # sequence solution (see ``_set_vsc_pf_positive_sequence``).
    converter_block.external_mapping = {
        VarPowerFlowReferenceType.v_A: v_A,
        VarPowerFlowReferenceType.v_B: v_B,
        VarPowerFlowReferenceType.v_C: v_C,
        VarPowerFlowReferenceType.vt_A: v_A,
        VarPowerFlowReferenceType.vt_B: v_B,
        VarPowerFlowReferenceType.vt_C: v_C,
        VarPowerFlowReferenceType.i_A: i_A,
        VarPowerFlowReferenceType.i_B: i_B,
        VarPowerFlowReferenceType.i_C: i_C,
        VarPowerFlowReferenceType.it_A: i_A,
        VarPowerFlowReferenceType.it_B: i_B,
        VarPowerFlowReferenceType.it_C: i_C,
        VarPowerFlowReferenceType.Vdc: v_dc,
        VarPowerFlowReferenceType.Vf_dc: v_dc,
        VarPowerFlowReferenceType.Idc: i_dc,
        VarPowerFlowReferenceType.If_dc: i_dc,
        VarPowerFlowReferenceType.Qf: Qf,
        VarPowerFlowReferenceType.Vpk: Vpk_ref,
        VarPowerFlowReferenceType.phi_v: phi_v_ref,
        VarPowerFlowReferenceType.Ipk: Ipk_ref,
        VarPowerFlowReferenceType.phi: phi_ref,
        VarPowerFlowReferenceType.P: P_ref,
        VarPowerFlowReferenceType.Q: Q_ref,
        VarPowerFlowReferenceType.Pe: Pe,
        VarPowerFlowReferenceType.Qe: Qe,
    }

    # API-object mapping.
    converter_block.api_obj_mapping = {
        ParamPowerFlowReferenceType.omega_base: omega_base,
        ParamPowerFlowReferenceType.R1: R_s,
        ParamPowerFlowReferenceType.X1: X_s,
    }

    converter_block.event_dict = {
        Kdp: vf.add_const(0.05),
        Kdq: vf.add_const(0.05),
        tau_omega: vf.add_const(0.05),
        tau_v: vf.add_const(0.05),
        omega_ref: vf.add_const(1.0),
    }
    converter_block.parameters.update({
        omega_base: vf.add_const(2.0 * np.pi * 50.0),
        R_s: vf.add_const(0.01),
        X_s: vf.add_const(0.1),
    })

    # Runtime / PF-bound parameters.
    # ``Vpk_ref``, ``phi_v_ref``, ``Ipk_ref``, ``phi_ref`` are the canonical
    # PF-seeded quantities that define the full GFM EMT steady-state operating
    # point. ``P_ref``, ``Q_ref`` and ``V_ref`` are derived from them at
    # initialization time, so they must remain ordinary runtime parameters and
    # not be treated as persistent zero defaults by the EMT build path.
    converter_block.event_dict.update({
        Qf: vf.add_const(0.0),
        Vpk_ref: vf.add_const(None),
        phi_v_ref: vf.add_const(None),
        Ipk_ref: vf.add_const(None),
        phi_ref: vf.add_const(None),
        P_ref: Pe_init_expr,
        Q_ref: Qe_init_expr,
        V_ref: Epk_init_expr,
    })

    # Initialization equations.
    #
    # Everything is pinned to a function of the PF positive-sequence
    # references (``Vpk_ref``, ``phi_v_ref``, ``Ipk_ref``, ``phi_ref``).
    # These are populated by the EMT-PF bridge once per build and do not
    # change during simulation, so the consistency Newton has nothing to
    # shift — the explicit init already places the system on the exact
    # steady-state sinusoidal trajectory.
    converter_block.init_eqs = {
        # Bus AC sample at t = 0 — pin v_A/v_B/v_C so KCL sees the same
        # values that the analytical EMF formula assumes.
        v_A: v_A_init_expr,
        v_B: v_B_init_expr,
        v_C: v_C_init_expr,

        # Converter currents at t = 0 in branch convention.
        i_A: i_A_init_expr,
        i_B: i_B_init_expr,
        i_C: i_C_init_expr,

        # Internal state.
        theta: theta_init_expr,
        omega: vf.add_const(1.0),
        Epk: Epk_init_expr,

        # Internal EMF samples at t = 0.
        e_A: e_A_init_expr,
        e_B: e_B_init_expr,
        e_C: e_C_init_expr,

        Pe: Pe_init_expr,
        Qe: Qe_init_expr,

    }

    # Differential initialization equations.
    # ``d_i_A(0)`` is the analytical derivative of the steady-state
    # sinusoid at ``t = 0``:
    #     d/dt [Ipk * sin(omega_base * t + phi_v + phi)] _{t=0}
    #         = Ipk * omega_base * cos(phi_v + phi)
    d_i_A_init_expr = omega_base * Ipk_ref * sym.cos(theta_i_init_expr)
    d_i_B_init_expr = omega_base * Ipk_ref * sym.cos(theta_i_init_expr - two_pi_over_3)
    d_i_C_init_expr = omega_base * Ipk_ref * sym.cos(theta_i_init_expr + two_pi_over_3)
    converter_block.diff_init_eqs = {
        d_i_A: d_i_A_init_expr,
        d_i_B: d_i_B_init_expr,
        d_i_C: d_i_C_init_expr,
        d_theta: omega_base * vf.add_const(1.0),
        d_omega: vf.add_const(0.0),
        d_Epk: vf.add_const(0.0),
    }

    templ.block.children.append(converter_block)
    templ.block.external_mapping = converter_block.external_mapping
    templ.block.in_vars = inputs
    templ.block.out_vars = converter_block.out_vars

    return templ
