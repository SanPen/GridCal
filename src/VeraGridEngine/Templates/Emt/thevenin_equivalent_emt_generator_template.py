# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


import numpy as np
from typing import List, Any
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import VarPowerFlowReferenceType, DeviceType, ParamPowerFlowReferenceType
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_pf_positive_sequence_init_refs


def get_thevenin_internal_shared_references() -> tuple[str, str, str, str]:
    """
    Return the stable shared-reference contract of the Thevenin seed variables.

    :return: Shared references for ``theta``, ``e_A``, ``e_B`` and ``e_C``.
    :rtype: tuple[str, str, str, str]
    """
    return (
        "thevenin_theta_internal",
        "thevenin_e_a_internal",
        "thevenin_e_b_internal",
        "thevenin_e_c_internal",
    )

def get_generator_thevenin_rl_emt_template_with_ref(
        vf: VarFactory,
        name: str = "emt_thevenin_eq_generator_template",
) -> EmtModelTemplate:
    """
    Build the ref-capable three-phase EMT Thevenin generator.

    The dynamic equations intentionally preserve the original passive Thevenin
    source behaviour that older EMT examples and snapshots rely on. The extra
    sharing references are exposed only through the symbolic mappings so
    ``EmtProblemDae`` can assign them consistently across devices without
    altering the local Thevenin source dynamics.

    Inputs
    ------
    ``v_A``, ``v_B``, ``v_C``:
        Instantaneous bus terminal voltages in pu.

    States
    ------
    ``i_A``, ``i_B``, ``i_C``:
        Phase currents injected into the bus in pu.

    ``theta``:
        Absolute electrical angle of the internal balanced source in rad.

    The optional sharing references are exposed through the mappings, but they do
    not introduce extra EMT states or controller dynamics inside the template
    itself.

    Parameters
    ----------
    Static generator parameters:
        ``omega_base``, ``R_s``, ``X_s``

    PF-derived initialization parameters:
        ``phi_v``, ``phi``, ``Vpk``, ``Ipk``

    Optional sharing references:
        ``share_enable``, ``P_share_ref``, ``Q_share_ref``

    Event parameters:
        ``phi_v``, ``phi``, ``Vpk``, ``Ipk``, ``E_scale``

    Initialization
    --------------
    The PF initialization reconstructs the positive-sequence internal emf using:

    .. math::

        E = V + (R + jX) I

    and then initializes:

    * ``theta = phi_v + delta``

    so that the passive Thevenin source starts exactly from the PF operating
    point used by the legacy EMT examples.

    :param vf: EMT variable factory.
    :param name: Symbolic block name.
    :return: Configured EMT template.
    """
    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name
    theta_internal_reference: str
    e_a_internal_reference: str
    e_b_internal_reference: str
    e_c_internal_reference: str
    theta_internal_reference, e_a_internal_reference, e_b_internal_reference, e_c_internal_reference = get_thevenin_internal_shared_references()

    # ------------------------------------------------------------------
    # Constants used in symbolic expressions.
    # ------------------------------------------------------------------
    c05 = vf.add_const(0.5)
    c_eps_emf = vf.add_const(1.0e-24)
    c0 = vf.add_const(0.0)

    # ------------------------------------------------------------------
    # Inputs: terminal bus voltages in abc.
    # ------------------------------------------------------------------
    v_A = vf.add_var(name=f"v_A", reference=VarPowerFlowReferenceType.v_A)
    v_B = vf.add_var(name=f"v_B", reference=VarPowerFlowReferenceType.v_B)
    v_C = vf.add_var(name=f"v_C", reference=VarPowerFlowReferenceType.v_C)
    inputs: List[Any] = list([v_A, v_B, v_C])

    # ------------------------------------------------------------------
    # States:
    # - current dynamics
    # - absolute synchronous angle
    # ------------------------------------------------------------------
    i_A = vf.add_var(name=f"i_A", reference=VarPowerFlowReferenceType.i_A)
    i_B = vf.add_var(name=f"i_B", reference=VarPowerFlowReferenceType.i_B)
    i_C = vf.add_var(name=f"i_C", reference=VarPowerFlowReferenceType.i_C)

    theta = vf.add_var(name=f"theta", shared_reference=theta_internal_reference)
    # parameter to create a phase jump
    theta_deviation_param = vf.add_var(name=f"theta_deviation_param")
    # parameter to create RoCoF
    w_scale = vf.add_var(name=f"f_scale")

    d_i_A = vf.add_diff_var(name=f"d_i_A", base_var=i_A)
    d_i_B = vf.add_diff_var(name=f"d_i_B", base_var=i_B)
    d_i_C = vf.add_diff_var(name=f"d_i_C", base_var=i_C)
    d_theta = vf.add_diff_var(name=f"d_theta", base_var=theta)

    # ------------------------------------------------------------------
    # Algebraic variables:
    # - internal phase emfs
    # - measured active/reactive power
    # ------------------------------------------------------------------
    e_A = vf.add_var(name=f"e_A", shared_reference=e_a_internal_reference)
    e_B = vf.add_var(name=f"e_B", shared_reference=e_b_internal_reference)
    e_C = vf.add_var(name=f"e_C", shared_reference=e_c_internal_reference)
    Pe = vf.add_var(name=f"Pe")
    Qe = vf.add_var(name=f"Qe")

    # ------------------------------------------------------------------
    # Static parameters and PF-derived initialization parameters.
    # ------------------------------------------------------------------
    omega_base = vf.add_var(name=f"omega_base")
    R_s = vf.add_var(name=f"R_s")
    X_s = vf.add_var(name=f"X_s")

    phi_v = vf.add_var(name=f"phi_v")
    phi = vf.add_var(name=f"phi")
    Vpk = vf.add_var(name=f"Vpk")
    Ipk = vf.add_var(name=f"Ipk")

    # ------------------------------------------------------------------
    # Optional sharing references.
    # The references are exposed for higher-level orchestration only. The passive
    # Thevenin source does not use them internally.
    # ------------------------------------------------------------------
    share_enable = vf.add_var(name=f"share_enable")
    P_share_ref = vf.add_var(name=f"P_share_ref")
    Q_share_ref = vf.add_var(name=f"Q_share_ref")
    E_scale = vf.add_var(name=f"E_scale")

    # ------------------------------------------------------------------
    # PF-consistent positive-sequence internal emf.
    # This part remains identical in spirit to the original Thevenin model.
    # ------------------------------------------------------------------
    E_re = Vpk + R_s * Ipk * sym.cos(phi) - X_s * Ipk * sym.sin(phi)
    E_im = R_s * Ipk * sym.sin(phi) + X_s * Ipk * sym.cos(phi)
    # ``atan2`` keeps the reconstructed emf angle consistent across quadrants and
    # avoids undefined divisions when the steady-state real component is zero.
    delta_expr = sym.atan2(E_im, E_re)
    Epk_expr = (E_re ** 2 + E_im ** 2 + c_eps_emf) ** c05

    # ------------------------------------------------------------------
    # The ref-capable variant preserves the original passive Thevenin source.
    # The exposed reference variables are mapped for higher-level orchestration,
    # but they do not change the local source equations.
    # ------------------------------------------------------------------
    theta_speed = omega_base

    # ------------------------------------------------------------------
    # Build the EMT block.
    # ------------------------------------------------------------------
    state_eqs: List[Any] = list([
        omega_base * (e_A - R_s * i_A - v_A) / X_s,
        omega_base * (e_B - R_s * i_B - v_B) / X_s,
        omega_base * (e_C - R_s * i_C - v_C) / X_s,
        theta_speed * w_scale,
    ])

    state_vars: List[Any] = list([
        i_A,
        i_B,
        i_C,
        theta,
    ])

    algebraic_eqs: List[Any] = list([
        e_A - E_scale * Epk_expr * sym.sin(theta + theta_deviation_param),
        e_B - E_scale * Epk_expr * sym.sin(theta - 2.0 * np.pi / 3.0 + theta_deviation_param),
        e_C - E_scale * Epk_expr * sym.sin(theta + 2.0 * np.pi / 3.0 + theta_deviation_param),
        Pe - (i_A * v_A + i_B * v_B + i_C * v_C),
        Qe - (1.0 / np.sqrt(3.0)) * (
            (v_A - v_B) * i_C +
            (v_B - v_C) * i_A +
            (v_C - v_A) * i_B
        ),
    ])

    algebraic_vars: List[Any] = list([e_A, e_B, e_C, Pe, Qe])

    block = Block(
        state_eqs=state_eqs,
        state_vars=state_vars,
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=algebraic_vars,
        in_vars=inputs,
        out_vars=list([i_A, i_B, i_C]),
    )

    # The electrical values come directly from the static generator and are
    # therefore required. Using a fallback source impedance would change the
    # first EMT derivative and hide a physical-device mapping regression.
    block.parameters[omega_base] = vf.add_const(None)
    block.parameters[R_s] = vf.add_const(None)
    block.parameters[X_s] = vf.add_const(None)

    block.diff_vars = list([
        d_i_A,
        d_i_B,
        d_i_C,
        d_theta,
    ])

    # ------------------------------------------------------------------
    # External mapping:
    # keep the original EMT injection interface intact.
    # ------------------------------------------------------------------
    block.external_mapping = dict({
        VarPowerFlowReferenceType.v_A: v_A,
        VarPowerFlowReferenceType.v_B: v_B,
        VarPowerFlowReferenceType.v_C: v_C,
        VarPowerFlowReferenceType.i_A: i_A,
        VarPowerFlowReferenceType.i_B: i_B,
        VarPowerFlowReferenceType.i_C: i_C,
        VarPowerFlowReferenceType.phi_v: phi_v,
        VarPowerFlowReferenceType.phi: phi,
        VarPowerFlowReferenceType.Vpk: Vpk,
        VarPowerFlowReferenceType.Ipk: Ipk,
        VarPowerFlowReferenceType.d_v_A: None,
        VarPowerFlowReferenceType.d_v_B: None,
        VarPowerFlowReferenceType.d_v_C: None,
        VarPowerFlowReferenceType.P_A: None,
        VarPowerFlowReferenceType.Q_A: None,
        VarPowerFlowReferenceType.P_B: None,
        VarPowerFlowReferenceType.Q_B: None,
        VarPowerFlowReferenceType.P_C: None,
        VarPowerFlowReferenceType.Q_C: None,
    })

    # ------------------------------------------------------------------
    # API-object mapping:
    # static generator parameters plus optional sharing references assigned
    # by EmtProblemDae.
    # ------------------------------------------------------------------
    block.api_obj_mapping = dict({
        ParamPowerFlowReferenceType.omega_base: omega_base,
        ParamPowerFlowReferenceType.R1: R_s,
        ParamPowerFlowReferenceType.X1: X_s,
        ParamPowerFlowReferenceType.generator_share_enable: share_enable,
        ParamPowerFlowReferenceType.generator_share_p_ref: P_share_ref,
        ParamPowerFlowReferenceType.generator_share_q_ref: Q_share_ref,
    })

    # ------------------------------------------------------------------
    # Event parameters:
    # PF-derived phasor quantities plus local controller gains.
    # The gains are intentionally conservative compared with the version
    # that acted directly on dtheta/dt.
    # ------------------------------------------------------------------
    block.event_dict = dict({
        phi_v: vf.add_const(None),
        phi: vf.add_const(None),
        Vpk: vf.add_const(None),
        Ipk: vf.add_const(None),
        # This remains a pure event/runtime parameter so scripts and EMT events
        # can scale the Thevenin source magnitude from outside the model.
        E_scale: vf.add_const(1.0),
        theta_deviation_param: vf.add_const(0.0),
        w_scale: vf.add_const(1.0),
        # Sharing data depends on the solved operating point and bus topology.
        # Required runtime placeholders prevent a static fallback from hiding a
        # missing PF seed while keeping the static parameter contract physical.
        share_enable: vf.add_const(None),
        P_share_ref: vf.add_const(None),
        Q_share_ref: vf.add_const(None),
    })

    # ------------------------------------------------------------------
    # Initialization equations:
    # the sharing controller starts exactly from the PF-consistent open-loop
    # operating point, so it does not create a jump at t = 0.
    # ------------------------------------------------------------------
    block.init_eqs = dict({
        theta: phi_v + delta_expr,
        e_A: E_scale * Epk_expr * sym.sin(theta + theta_deviation_param),
        e_B: E_scale * Epk_expr * sym.sin(theta - 2.0 * np.pi / 3.0 + theta_deviation_param),
        e_C: E_scale * Epk_expr * sym.sin(theta + 2.0 * np.pi / 3.0 + theta_deviation_param),
        Pe: (i_A * v_A + i_B * v_B + i_C * v_C),
        Qe: (1.0 / np.sqrt(3.0)) * (
            (v_A - v_B) * i_C +
            (v_B - v_C) * i_A +
            (v_C - v_A) * i_B
        ),
    })

    # ------------------------------------------------------------------
    # Differential initialization equations:
    # these keep the standard EMT explicit-init semantics.
    # ------------------------------------------------------------------
    block.diff_init_eqs = dict({
        d_i_A: omega_base * (e_A - R_s * i_A - v_A) / X_s,
        d_i_B: omega_base * (e_B - R_s * i_B - v_B) / X_s,
        d_i_C: omega_base * (e_C - R_s * i_C - v_C) / X_s,
        d_theta: theta_speed * w_scale,
    })

    templ.block.children.append(block)
    templ.block.external_mapping = block.external_mapping
    templ.block.in_vars = inputs
    templ.block.out_vars = block.out_vars

    return templ
