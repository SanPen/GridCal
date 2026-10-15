# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Dict, List, Tuple
from VeraGridEngine.enumerations import (
    DeviceType,
    WindingType,
    VarPowerFlowReferenceType,
    ParamPowerFlowReferenceType,
)
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_grounding_link_emt_template
from VeraGridEngine.Templates.Emt.transformer_emt_template import _attach_transformer_editor_diagram
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Expr
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def _project_currents(
    coeffs: list[list[Expr]],
    currents: list[Expr],
    c0: Expr,
) -> list[Expr]:
    """
    Project winding-frame currents to terminal-frame currents.

    The voltage transformation used in the template is::

        v_w = C^T v_terminal

    and thus the consistent current back-projection is::

        i_terminal = C i_w

    :param coeffs: Connection matrix as symbolic expressions.
    :param currents: Winding-frame currents.
    :param c0: Zero-like symbolic constant.
    :return: Terminal-frame current expressions.
    """
    out: list[Expr] = []

    for i in range(3):
        rhs: Expr = c0
        for j in range(3):
            rhs = rhs + coeffs[i][j] * currents[j]
        out.append(rhs)

    return out


def get_xfmr_emt_template(
    vf: VarFactory,
    conn_f: WindingType | None = None,
    conn_t: WindingType | None = None,
    name: str = "xfmr_emt_template",
) -> EmtModelTemplate:
    """
    Build the EMT DAE template of a basic ATP-like transformer model.

    Overview
    --------
    This transformer model is organized as:

    1. one series leakage branch between the two transformer terminals,
    2. one magnetizing/core branch referred to the from side only,
    3. one linear core-loss branch referred to the from side only,
    4. optional terminal shunt capacitances represented through charge states.

    The model is intentionally kept close to the classical robust transformer
    equivalent used in EMT-type formulations:

    * the leakage path couples the from and to terminals,
    * the core is excited from the from-side winding voltage only,
    * the core current is injected only on the from side.

    This avoids the algebraic/numerical issues caused by splitting the magnetic
    branch symmetrically between both sides.

    Parameter ownership
    -------------------
    This template follows the requested VeraGrid architecture:

    * api_obj_mapping:
      only parameters that come from the static transformer object or are passed
      almost directly by the EMT assembler.

    * event_dict:
      parameters of the dynamic transformer model that are not explicit static
      data and can be overridden through set_parameter_in_model().

    * init_eqs:
      initialization equations of internal algebraic and state variables.

    * diff_init_eqs:
      initialization equations of internal derivatives.

    Static mapped parameters
    ------------------------
    Expected from the EMT assembler through api_obj_mapping:

    * omega_base
    * transformer_rated_power_mva
    * transformer_open_circuit_current_pct
    * transformer_open_circuit_loss_kw
    * transformer_short_circuit_voltage_pct
    * transformer_short_circuit_loss_kw
    * tap_module
    * transformer_from_connection_**
    * transformer_to_connection_**

    Dynamic local parameters
    ------------------------
    Local model parameters stored in event_dict:

    * xfmr_core_topology_code
    * xfmr_yoke_area_rel
    * xfmr_yoke_length_rel
    * xfmr_outer_leg_area_rel
    * xfmr_outer_leg_length_rel
    * xfmr_c_term
    * xfmr_use_linear_core
    * xfmr_use_piecewise_core
    * xfmr_core_knee_flux_mult
    * xfmr_core_knee_current_mult
    * xfmr_piecewise_flux_1/2
    * xfmr_piecewise_current_1/2
    * xfmr_use_fixed_initial_flux
    * xfmr_initial_flux_a/b/c
    * xfmr_sc_resistance_pct
    * xfmr_core_linear_l_pu
    * xfmr_core_a_prime
    * xfmr_core_b_prime

    Core modelling
    --------------
    The magnetic branch is referred only to the from side:

    * v_core_w = v_f_w
    * i_core is injected only at the from terminal

    This is more robust and closer to the classical transformer equivalent than
    the previous symmetric split of the core branch between both terminals.

    Capacitive path
    ---------------
    Terminal capacitances are represented through:

    * state charges q_f and q_t
    * algebraic currents i_cap_f and i_cap_t
    * q = C v
    * dq/dt = i_cap

    If xfmr_c_term = 0, these states collapse consistently to zero.

    Sign convention
    ---------------
    Exported branch currents follow the VeraGrid branch convention:
    current is positive when it leaves the bus.

    :param vf: EMT variable factory.
    :param conn_f: Optional from-side winding connection.
    :param conn_t: Optional to-side winding connection.
    :param name: Symbolic model name.
    :return: EMT transformer template.
    """

    templ = EmtModelTemplate()
    templ.tpe = DeviceType.Transformer2WDevice
    templ.name = name

    block = Block()
    block.name=name

    # ``NeutralStar`` exposes a fourth terminal conductor. ``GroundedStar``
    # instead fixes the internal star point to ground and therefore keeps the
    # external terminal contract three-phase unless the static branch itself
    # explicitly models a neutral conductor.
    if conn_f == WindingType.NeutralStar:
        from_has_neutral_port: bool = True
    else:
        from_has_neutral_port = False

    if conn_t == WindingType.NeutralStar:
        to_has_neutral_port: bool = True
    else:
        to_has_neutral_port = False

    c0: Expr = vf.add_const(0.0)
    c1: Expr = vf.add_const(1.0)
    c2: Expr = vf.add_const(2.0)
    c3: Expr = vf.add_const(3.0)
    c_eps: Expr = vf.add_const(1e-9)
    c_smooth: Expr = vf.add_const(1e-8)
    c_sqrt2: Expr = sym.sqrt(vf.add_const(2.0))

    # ------------------------------------------------------------------
    # Static parameters mapped from the transformer API object.
    # ------------------------------------------------------------------
    omega_base: Var = vf.add_var(name=f"omega_base")
    system_sbase: Var = vf.add_var(name="xfmr_system_sbase_mva")
    xfmr_s_rated_mva: Var = vf.add_var(name=f"xfmr_s_rated_mva")
    xfmr_oc_current_pct: Var = vf.add_var(name=f"xfmr_oc_current_pct")
    xfmr_oc_loss_kw: Var = vf.add_var(name=f"xfmr_oc_loss_kw")
    xfmr_sc_voltage_pct: Var = vf.add_var(name=f"xfmr_sc_voltage_pct")
    xfmr_sc_loss_kw: Var = vf.add_var(name=f"xfmr_sc_loss_kw")
    xfmr_tap_module: Var = vf.add_var(name=f"xfmr_tap_module")

    block.api_obj_mapping[ParamPowerFlowReferenceType.Sbase] = system_sbase
    # Static API-mapped values belong to the physical transformer. ``None`` is
    # intentional: it keeps each UID visible to the initializer while forcing
    # the EMT assembler to supply the real device value. A numerical fallback
    # here would silently change leakage and magnetizing branches whenever the
    # wrapper mapping was not propagated correctly.
    block.parameters[omega_base] = vf.add_const(None)
    block.parameters[system_sbase] = vf.add_const(None)
    block.parameters[xfmr_s_rated_mva] = vf.add_const(None)
    block.parameters[xfmr_oc_current_pct] = vf.add_const(None)
    block.parameters[xfmr_oc_loss_kw] = vf.add_const(None)
    block.parameters[xfmr_sc_voltage_pct] = vf.add_const(None)
    block.parameters[xfmr_sc_loss_kw] = vf.add_const(None)
    block.parameters[xfmr_tap_module] = vf.add_const(None)

    block.api_obj_mapping[ParamPowerFlowReferenceType.omega_base] = omega_base
    block.api_obj_mapping[ParamPowerFlowReferenceType.transformer_rated_power_mva] = xfmr_s_rated_mva
    block.api_obj_mapping[ParamPowerFlowReferenceType.transformer_open_circuit_current_pct] = xfmr_oc_current_pct
    block.api_obj_mapping[ParamPowerFlowReferenceType.transformer_open_circuit_loss_kw] = xfmr_oc_loss_kw
    block.api_obj_mapping[ParamPowerFlowReferenceType.transformer_short_circuit_voltage_pct] = xfmr_sc_voltage_pct
    block.api_obj_mapping[ParamPowerFlowReferenceType.transformer_short_circuit_loss_kw] = xfmr_sc_loss_kw
    block.api_obj_mapping[ParamPowerFlowReferenceType.tap_module] = xfmr_tap_module

    # ------------------------------------------------------------------
    # Mapped winding-connection matrices.
    # ------------------------------------------------------------------
    cf_enums: list[list[ParamPowerFlowReferenceType]] = [
        [
            ParamPowerFlowReferenceType.transformer_from_connection_aa,
            ParamPowerFlowReferenceType.transformer_from_connection_ab,
            ParamPowerFlowReferenceType.transformer_from_connection_ac,
        ],
        [
            ParamPowerFlowReferenceType.transformer_from_connection_ba,
            ParamPowerFlowReferenceType.transformer_from_connection_bb,
            ParamPowerFlowReferenceType.transformer_from_connection_bc,
        ],
        [
            ParamPowerFlowReferenceType.transformer_from_connection_ca,
            ParamPowerFlowReferenceType.transformer_from_connection_cb,
            ParamPowerFlowReferenceType.transformer_from_connection_cc,
        ],
    ]
    ct_enums: list[list[ParamPowerFlowReferenceType]] = [
        [
            ParamPowerFlowReferenceType.transformer_to_connection_aa,
            ParamPowerFlowReferenceType.transformer_to_connection_ab,
            ParamPowerFlowReferenceType.transformer_to_connection_ac,
        ],
        [
            ParamPowerFlowReferenceType.transformer_to_connection_ba,
            ParamPowerFlowReferenceType.transformer_to_connection_bb,
            ParamPowerFlowReferenceType.transformer_to_connection_bc,
        ],
        [
            ParamPowerFlowReferenceType.transformer_to_connection_ca,
            ParamPowerFlowReferenceType.transformer_to_connection_cb,
            ParamPowerFlowReferenceType.transformer_to_connection_cc,
        ],
    ]

    c_f_expr: list[list[Expr]] = []
    c_t_expr: list[list[Expr]] = []

    for i in range(3):
        c_f_row: list[Expr] = []
        c_t_row: list[Expr] = []

        for j in range(3):
            c_f_var: Var = vf.add_var(name=f"xfmr_cf_{i}_{j}")
            c_t_var: Var = vf.add_var(name=f"xfmr_ct_{i}_{j}")

            block.api_obj_mapping[cf_enums[i][j]] = c_f_var
            block.api_obj_mapping[ct_enums[i][j]] = c_t_var

            # The connection and clock-number mapper is the sole source of
            # these coefficients. Required placeholders prevent an identity
            # fallback from hiding a missing or lost physical-device mapping.
            block.parameters[c_f_var] = vf.add_const(None)
            block.parameters[c_t_var] = vf.add_const(None)

            c_f_row.append(c_f_var)
            c_t_row.append(c_t_var)

        c_f_expr.append(c_f_row)
        c_t_expr.append(c_t_row)

    # ------------------------------------------------------------------
    # Local dynamic-model parameters.
    # ------------------------------------------------------------------
    xfmr_core_topology_code: Var = vf.add_var(name=f"xfmr_core_topology_code")
    xfmr_yoke_area_rel: Var = vf.add_var(name=f"xfmr_yoke_area_rel")
    xfmr_yoke_length_rel: Var = vf.add_var(name=f"xfmr_yoke_length_rel")
    xfmr_outer_leg_area_rel: Var = vf.add_var(name=f"xfmr_outer_leg_area_rel")
    xfmr_outer_leg_length_rel: Var = vf.add_var(name=f"xfmr_outer_leg_length_rel")
    xfmr_c_term: Var = vf.add_var(name=f"xfmr_c_term")
    xfmr_use_linear_core: Var = vf.add_var(name=f"xfmr_use_linear_core")
    xfmr_use_piecewise_core: Var = vf.add_var(name=f"xfmr_use_piecewise_core")
    xfmr_core_knee_flux_mult: Var = vf.add_var(name=f"xfmr_core_knee_flux_mult")
    xfmr_core_knee_current_mult: Var = vf.add_var(name=f"xfmr_core_knee_current_mult")
    xfmr_piecewise_flux_1: Var = vf.add_var(name=f"xfmr_piecewise_flux_1")
    xfmr_piecewise_current_1: Var = vf.add_var(name=f"xfmr_piecewise_current_1")
    xfmr_piecewise_flux_2: Var = vf.add_var(name=f"xfmr_piecewise_flux_2")
    xfmr_piecewise_current_2: Var = vf.add_var(name=f"xfmr_piecewise_current_2")
    xfmr_use_fixed_initial_flux: Var = vf.add_var(name=f"xfmr_use_fixed_initial_flux")
    xfmr_initial_flux_a: Var = vf.add_var(name=f"xfmr_initial_flux_a")
    xfmr_initial_flux_b: Var = vf.add_var(name=f"xfmr_initial_flux_b")
    xfmr_initial_flux_c: Var = vf.add_var(name=f"xfmr_initial_flux_c")

    xfmr_sc_resistance_pct: Var = vf.add_var(name=f"xfmr_sc_resistance_pct")
    xfmr_core_linear_l_pu: Var = vf.add_var(name=f"xfmr_core_linear_l_pu")
    xfmr_core_a_prime: Var = vf.add_var(name=f"xfmr_core_a_prime")
    xfmr_core_b_prime: Var = vf.add_var(name=f"xfmr_core_b_prime")

    block.event_dict[xfmr_core_topology_code] = vf.add_const(3.0)
    block.event_dict[xfmr_yoke_area_rel] = vf.add_const(1.0)
    block.event_dict[xfmr_yoke_length_rel] = vf.add_const(1.0)
    block.event_dict[xfmr_outer_leg_area_rel] = vf.add_const(1.0)
    block.event_dict[xfmr_outer_leg_length_rel] = vf.add_const(1.0)
    block.event_dict[xfmr_c_term] = vf.add_const(1e-6)
    block.event_dict[xfmr_use_linear_core] = vf.add_const(1.0)
    block.event_dict[xfmr_use_piecewise_core] = vf.add_const(0.0)
    block.event_dict[xfmr_core_knee_flux_mult] = vf.add_const(1.50)
    block.event_dict[xfmr_core_knee_current_mult] = vf.add_const(8.0)
    block.event_dict[xfmr_piecewise_flux_1] = vf.add_const(1.2)
    block.event_dict[xfmr_piecewise_current_1] = vf.add_const(0.005)
    block.event_dict[xfmr_piecewise_flux_2] = vf.add_const(1.9)
    block.event_dict[xfmr_piecewise_current_2] = vf.add_const(0.1)
    block.event_dict[xfmr_use_fixed_initial_flux] = vf.add_const(0.0)
    block.event_dict[xfmr_initial_flux_a] = vf.add_const(0.0)
    block.event_dict[xfmr_initial_flux_b] = vf.add_const(0.0)
    block.event_dict[xfmr_initial_flux_c] = vf.add_const(0.0)

    # ------------------------------------------------------------------
    # Derived local parameters of the dynamic model.
    # ------------------------------------------------------------------
    block.event_dict[xfmr_sc_resistance_pct] = xfmr_sc_loss_kw / (vf.add_const(10.0) * xfmr_s_rated_mva + c_eps)

    # Terminal currents use the network three-phase base. Nameplate test
    # quantities are on the transformer rating; convert before injecting them.
    impedance_base_ratio: Expr = system_sbase / (xfmr_s_rated_mva + c_eps)
    admittance_base_ratio: Expr = xfmr_s_rated_mva / (system_sbase + c_eps)
    oc_loss_pu: Expr = (xfmr_oc_loss_kw / vf.add_const(1000.0)) / (xfmr_s_rated_mva + c_eps)
    oc_current_pu: Expr = xfmr_oc_current_pct / vf.add_const(100.0)
    i_mag_pu: Expr = sym.sqrt(oc_current_pu * oc_current_pu - oc_loss_pu * oc_loss_pu + c_eps) * admittance_base_ratio

    block.event_dict[xfmr_core_linear_l_pu] = c1 / (i_mag_pu + c_eps)

    # The terminal-capacitance current is a valid initialization degree of
    # freedom only when the physical capacitance exists. Use a smooth runtime-
    # parameter selector because introducing switching functions inside the
    # explicit initialization would create a nested block whose derived event
    # parameters are not available yet. At Cterm = 0 this expression is
    # exactly zero; for every practical positive capacitance it is unity to
    # numerical precision.
    capacitance_enable_epsilon: Expr = vf.add_const(1e-15)
    terminal_capacitance_enabled: Expr = (
        xfmr_c_term / (xfmr_c_term + capacitance_enable_epsilon)
    )

    lambda_nom_peak: Expr = c_sqrt2
    i_nom_peak_from_linear: Expr = lambda_nom_peak / (xfmr_core_linear_l_pu + c_eps)
    a_prime_auto: Expr = c1 / (xfmr_core_linear_l_pu + c_eps)
    lambda_knee: Expr = xfmr_core_knee_flux_mult * lambda_nom_peak
    i_knee: Expr = xfmr_core_knee_current_mult * i_nom_peak_from_linear
    b_prime_raw: Expr = (i_knee / (lambda_knee + c_eps) - a_prime_auto) / (i_knee + c_eps)
    b_prime_auto: Expr = b_prime_raw * b_prime_raw / (sym.sqrt(b_prime_raw * b_prime_raw + c_smooth) + c_eps)

    block.event_dict[xfmr_core_a_prime] = a_prime_auto
    block.event_dict[xfmr_core_b_prime] = b_prime_auto

    # ------------------------------------------------------------------
    # Leakage-branch parameters.
    # ------------------------------------------------------------------
    z_sc_pu: Expr = xfmr_sc_voltage_pct / vf.add_const(100.0) * impedance_base_ratio
    r_sc_pu: Expr = xfmr_sc_resistance_pct / vf.add_const(100.0) * impedance_base_ratio
    x_sc_pu: Expr = sym.sqrt(z_sc_pu * z_sc_pu - r_sc_pu * r_sc_pu + c_eps)
    l_sigma: Expr = x_sc_pu / (omega_base + c_eps)
    l_inv: Expr = c1 / (l_sigma + c_eps)

    # ------------------------------------------------------------------
    # Core-loss conductance from open-circuit losses.
    # ------------------------------------------------------------------
    g_core_total: Expr = (xfmr_oc_loss_kw / vf.add_const(1000.0)) / (system_sbase + c_eps)
    # Phase voltage/current bases already use Sbase/3 per phase. At balanced
    # nominal voltage, sum(v_phase*i_phase)/3 must equal total loss/Sbase.
    g_core_leg: Expr = g_core_total

    # ------------------------------------------------------------------
    # Terminal electrical interface variables in abc frame.
    # ------------------------------------------------------------------
    vf_keys: Dict[str, VarPowerFlowReferenceType] = {
        "N": VarPowerFlowReferenceType.vf_N,
        "A": VarPowerFlowReferenceType.vf_A,
        "B": VarPowerFlowReferenceType.vf_B,
        "C": VarPowerFlowReferenceType.vf_C,
    }
    vt_keys: Dict[str, VarPowerFlowReferenceType] = {
        "N": VarPowerFlowReferenceType.vt_N,
        "A": VarPowerFlowReferenceType.vt_A,
        "B": VarPowerFlowReferenceType.vt_B,
        "C": VarPowerFlowReferenceType.vt_C,
    }

    v_f_n: Var | None = None
    v_t_n: Var | None = None

    if from_has_neutral_port:
        v_f_n = vf.add_var(name=f"vf_N", reference=vf_keys["N"])
    else:
        pass

    if to_has_neutral_port:
        v_t_n = vf.add_var(name=f"vt_N", reference=vt_keys["N"])
    else:
        pass

    v_f: list[Var] = [
        vf.add_var(name=f"vf_A", reference=vf_keys["A"]),
        vf.add_var(name=f"vf_B", reference=vf_keys["B"]),
        vf.add_var(name=f"vf_C", reference=vf_keys["C"]),
    ]
    v_t: list[Var] = [
        vf.add_var(name=f"vt_A", reference=vt_keys["A"]),
        vf.add_var(name=f"vt_B", reference=vt_keys["B"]),
        vf.add_var(name=f"vt_C", reference=vt_keys["C"]),
    ]

    # ------------------------------------------------------------------
    # Dynamic states and derivatives.
    # ------------------------------------------------------------------
    i_leak: list[Var] = [vf.add_var(name=f"i_leak_{ph}") for ph in ("A", "B", "C")]
    lam_leg: list[Var] = [vf.add_var(name=f"lam_leg_{ph}") for ph in ("A", "B", "C")]
    q_f: list[Var] = [vf.add_var(name=f"qf_{ph}") for ph in ("A", "B", "C")]
    q_t: list[Var] = [vf.add_var(name=f"qt_{ph}") for ph in ("A", "B", "C")]

    di_leak: list[Var] = [vf.add_diff_var(name=f"di_leak_{ph}", base_var=i_leak[k]) for k, ph in enumerate(("A", "B", "C"))]
    dlam_leg: list[Var] = [vf.add_diff_var(name=f"dlam_leg_{ph}", base_var=lam_leg[k]) for k, ph in enumerate(("A", "B", "C"))]
    dq_f: list[Var] = [vf.add_diff_var(name=f"dqf_{ph}", base_var=q_f[k]) for k, ph in enumerate(("A", "B", "C"))]
    dq_t: list[Var] = [vf.add_diff_var(name=f"dqt_{ph}", base_var=q_t[k]) for k, ph in enumerate(("A", "B", "C"))]

    # ------------------------------------------------------------------
    # Algebraic variables.
    # ------------------------------------------------------------------
    i_leg_core: list[Var] = [vf.add_var(name=f"i_leg_core_{ph}") for ph in ("A", "B", "C")]
    i_mag: list[Var] = [vf.add_var(name=f"i_mag_{ph}") for ph in ("A", "B", "C")]
    i_loss_leg: list[Var] = [vf.add_var(name=f"i_loss_leg_{ph}") for ph in ("A", "B", "C")]
    i_cap_f: list[Var] = [vf.add_var(name=f"i_cap_f_{ph}") for ph in ("A", "B", "C")]
    i_cap_t: list[Var] = [vf.add_var(name=f"i_cap_t_{ph}") for ph in ("A", "B", "C")]
    if_act: list[Var] = [
        vf.add_var(name=f"if_A", reference=VarPowerFlowReferenceType.if_A),
        vf.add_var(name=f"if_B", reference=VarPowerFlowReferenceType.if_B),
        vf.add_var(name=f"if_C", reference=VarPowerFlowReferenceType.if_C),
    ]
    it_act: list[Var] = [
        vf.add_var(name=f"it_A", reference=VarPowerFlowReferenceType.it_A),
        vf.add_var(name=f"it_B", reference=VarPowerFlowReferenceType.it_B),
        vf.add_var(name=f"it_C", reference=VarPowerFlowReferenceType.it_C),
    ]
    if_n_act: Var | None = vf.add_var(name=f"if_N", reference=VarPowerFlowReferenceType.if_N) if from_has_neutral_port else None
    it_n_act: Var | None = vf.add_var(name=f"it_N", reference=VarPowerFlowReferenceType.it_N) if to_has_neutral_port else None
    from_ground_current: Var | None = None
    to_ground_current: Var | None = None
    from_grounding_link_block: Block | None = None
    to_grounding_link_block: Block | None = None
    i_return_path: Var = vf.add_var(name=f"i_return_path")
    i_return_total: Var = vf.add_var(name=f"i_return_total")

    input_vars: list[Var] = list()
    if v_f_n is not None:
        input_vars.append(v_f_n)
    else:
        pass

    input_vars.extend(v_f)

    if v_t_n is not None:
        input_vars.append(v_t_n)
    else:
        pass

    input_vars.extend(v_t)

    if conn_f == WindingType.GroundedStar and v_f_n is not None:
        from_grounding_link_template: EmtModelTemplate = get_grounding_link_emt_template(
            vf=vf,
            include_r=False,
            include_l=False,
            include_c=False,
            solid_connection=True,
            nested=True,
            name=name + "_from_grounding_link",
        )
        vf.add_connections(from_grounding_link_template.block.in_vars, [v_f_n])
        from_ground_current = from_grounding_link_template.block.out_vars[0]
        from_grounding_link_block = from_grounding_link_template.block
        block.add(from_grounding_link_block)
    else:
        pass

    if conn_t == WindingType.GroundedStar and v_t_n is not None:
        to_grounding_link_template: EmtModelTemplate = get_grounding_link_emt_template(
            vf=vf,
            include_r=False,
            include_l=False,
            include_c=False,
            solid_connection=True,
            nested=True,
            name=name + "_to_grounding_link",
        )
        vf.add_connections(to_grounding_link_template.block.in_vars, [v_t_n])
        to_ground_current = to_grounding_link_template.block.out_vars[0]
        to_grounding_link_block = to_grounding_link_template.block
        block.add(to_grounding_link_block)
    else:
        pass

    algebraic_vars: list[Var] = (
        i_leg_core
        + [i_return_path, i_return_total]
        + i_mag
        + i_loss_leg
        + i_cap_f
        + i_cap_t
        + if_act
        + it_act
    )

    if if_n_act is not None:
        algebraic_vars.append(if_n_act)
    else:
        pass

    if it_n_act is not None:
        algebraic_vars.append(it_n_act)
    else:
        pass

    block.in_vars = input_vars
    block.state_vars = i_leak + lam_leg + q_f + q_t
    block.diff_vars = di_leak + dlam_leg + dq_f + dq_t
    block.algebraic_vars = algebraic_vars

    v_f_term: list[Expr] = list()
    v_t_term: list[Expr] = list()
    k: int
    for k in range(3):
        if v_f_n is not None:
            v_f_term.append(v_f[k] - v_f_n)
        else:
            v_f_term.append(v_f[k])

        if v_t_n is not None:
            v_t_term.append(v_t[k] - v_t_n)
        else:
            v_t_term.append(v_t[k])

    # ------------------------------------------------------------------
    # Voltage transformation from terminal abc frame to winding frame.
    # ------------------------------------------------------------------
    c_f_expr_t: list[list[Expr]] = [[c_f_expr[j][i] for j in range(3)] for i in range(3)]
    c_t_expr_t: list[list[Expr]] = [[c_t_expr[j][i] for j in range(3)] for i in range(3)]

    v_f_w: list[Expr] = []
    v_t_w: list[Expr] = []

    for i in range(3):
        expr_vfw: Expr = c0
        expr_vtw: Expr = c0

        for j in range(3):
            expr_vfw = expr_vfw + c_f_expr_t[i][j] * v_f_term[j]
            expr_vtw = expr_vtw + c_t_expr_t[i][j] * v_t_term[j]

        v_f_w.append(expr_vfw)
        v_t_w.append(expr_vtw)

    # ------------------------------------------------------------------
    # Internal winding-side voltages.
    #
    # Leakage branch:
    #   v_leak = v_f_w - n_tap * v_t_w
    #
    # Core branch:
    #   referred only to the from side
    # ------------------------------------------------------------------
    n_tap: Expr = xfmr_tap_module
    v_leak: list[Expr] = [v_f_w[k] - n_tap * v_t_w[k] for k in range(3)]
    v_core_w: list[Expr] = [v_f_w[k] for k in range(3)]

    # ------------------------------------------------------------------
    # State equations.
    # ------------------------------------------------------------------
    state_eqs: list[Expr] = []

    # Leakage-current dynamics.
    for k in range(3):
        state_eqs.append(l_inv * (v_leak[k] - r_sc_pu * i_leak[k]))

    # Core-flux dynamics referred to the from side.
    for k in range(3):
        state_eqs.append(omega_base * v_core_w[k])

    # Charge dynamics of terminal capacitances.
    for k in range(3):
        state_eqs.append(i_cap_f[k])
    for k in range(3):
        state_eqs.append(i_cap_t[k])

    block.state_eqs = state_eqs

    # ------------------------------------------------------------------
    # Core topology selectors.
    #
    # Supported values:
    #   1.0 -> three independent single-phase magnetic cores
    #   3.0 -> three-legged core
    #   5.0 -> five-legged core
    # ------------------------------------------------------------------
    lam_return_total: Expr = -(lam_leg[0] + lam_leg[1] + lam_leg[2])
    independent_core_selector: Expr = (
        (xfmr_core_topology_code - c3) * (xfmr_core_topology_code - vf.add_const(5.0))
        / vf.add_const(8.0)
    )
    three_leg_selector: Expr = -(
        (xfmr_core_topology_code - c1) * (xfmr_core_topology_code - vf.add_const(5.0))
        / vf.add_const(4.0)
    )
    five_leg_selector: Expr = (
        (xfmr_core_topology_code - c1) * (xfmr_core_topology_code - c3)
        / vf.add_const(8.0)
    )

    yoke_area_rel: Expr = xfmr_yoke_area_rel
    yoke_length_rel: Expr = xfmr_yoke_length_rel
    outer_leg_area_rel: Expr = xfmr_outer_leg_area_rel
    outer_leg_length_rel: Expr = xfmr_outer_leg_length_rel

    yoke_linear_coeff: Expr = xfmr_core_linear_l_pu * yoke_area_rel / (yoke_length_rel + c_eps)
    outer_linear_coeff: Expr = xfmr_core_linear_l_pu * outer_leg_area_rel / (outer_leg_length_rel + c_eps)

    yoke_frolich_lam: Expr = yoke_area_rel * i_return_path / (
        xfmr_core_a_prime * yoke_length_rel
        + xfmr_core_b_prime * sym.sqrt(i_return_path * i_return_path + c_smooth)
        + c_eps
    )
    outer_frolich_lam: Expr = outer_leg_area_rel * i_return_path / (
        xfmr_core_a_prime * outer_leg_length_rel
        + xfmr_core_b_prime * sym.sqrt(i_return_path * i_return_path + c_smooth)
        + c_eps
    )

    # ------------------------------------------------------------------
    # Projection of winding-frame currents to terminal-frame currents.
    # ------------------------------------------------------------------
    i_series_from: list[Expr] = _project_currents(c_f_expr, i_leak, c0)
    i_series_to: list[Expr] = _project_currents(c_t_expr, i_leak, c0)

    # Core branch referred only to the from side.
    i_core_from_w: list[Expr] = [i_mag[k] + i_loss_leg[k] for k in range(3)]
    i_core_to_w: list[Expr] = [c0, c0, c0]

    i_core_from_term: list[Expr] = _project_currents(c_f_expr, i_core_from_w, c0)
    i_core_to_term: list[Expr] = _project_currents(c_t_expr, i_core_to_w, c0)

    # ------------------------------------------------------------------
    # Algebraic equations.
    # ------------------------------------------------------------------
    alg_eqs: list[Expr] = []

    # Leg constitutive laws.
    for k in range(3):
        linear_leg_eq: Expr = lam_leg[k] - xfmr_core_linear_l_pu * i_leg_core[k]
        nonlinear_leg_eq: Expr = lam_leg[k] - i_leg_core[k] / (
            xfmr_core_a_prime
            + xfmr_core_b_prime * sym.sqrt(i_leg_core[k] * i_leg_core[k] + c_smooth)
            + c_eps
        )
        first_segment_slope: Expr = xfmr_piecewise_current_1 / xfmr_piecewise_flux_1
        second_segment_slope: Expr = (
            (xfmr_piecewise_current_2 - xfmr_piecewise_current_1)
            / (xfmr_piecewise_flux_2 - xfmr_piecewise_flux_1)
        )
        clamped_flux: Expr = sym.max(
            -xfmr_piecewise_flux_1,
            sym.min(lam_leg[k], xfmr_piecewise_flux_1),
        )
        excess_flux: Expr = (
            sym.max(lam_leg[k] - xfmr_piecewise_flux_1, c0)
            + sym.min(lam_leg[k] + xfmr_piecewise_flux_1, c0)
        )
        piecewise_current: Expr = (
            first_segment_slope * clamped_flux
            + second_segment_slope * excess_flux
        )
        piecewise_leg_eq: Expr = i_leg_core[k] - piecewise_current
        alg_eqs.append(
            xfmr_use_linear_core * linear_leg_eq
            + (c1 - xfmr_use_linear_core) * (
                xfmr_use_piecewise_core * piecewise_leg_eq
                + (c1 - xfmr_use_piecewise_core) * nonlinear_leg_eq
            )
        )

    # Return-path constitutive law.
    five_leg_eq_linear: Expr = c0
    five_leg_eq_linear = c0
    five_leg_eq_linear = (c1 / c2) * lam_return_total - (
        c2 * yoke_linear_coeff * i_return_path + outer_linear_coeff * i_return_path
    )
    five_leg_eq_nonlinear: Expr = (c1 / c2) * lam_return_total - (
        c2 * yoke_frolich_lam + outer_frolich_lam
    )
    three_leg_eq_linear: Expr = lam_return_total - c2 * yoke_linear_coeff * i_return_path
    three_leg_eq_nonlinear: Expr = lam_return_total - c2 * yoke_frolich_lam

    alg_eqs.append(
        independent_core_selector * i_return_path
        + five_leg_selector * (
            xfmr_use_linear_core * five_leg_eq_linear
            + (c1 - xfmr_use_linear_core) * five_leg_eq_nonlinear
        )
        + three_leg_selector * (
            xfmr_use_linear_core * three_leg_eq_linear
            + (c1 - xfmr_use_linear_core) * three_leg_eq_nonlinear
        )
    )

    alg_eqs.append(
        i_return_total - (
            five_leg_selector * c2 * i_return_path
            + three_leg_selector * i_return_path
        )
    )

    # Magnetizing currents.
    for k in range(3):
        alg_eqs.append(i_mag[k] - (i_leg_core[k] - i_return_total))

    # Core-loss currents referred only to the from side.
    for k in range(3):
        alg_eqs.append(i_loss_leg[k] - g_core_leg * v_f_w[k])

    # Charge-voltage relations of terminal capacitances.
    for k in range(3):
        alg_eqs.append(q_f[k] - xfmr_c_term * v_f_term[k])
        alg_eqs.append(q_t[k] - xfmr_c_term * v_t_term[k])

    # Terminal current assembly.
    for k in range(3):
        alg_eqs.append(
            if_act[k] - (
                i_series_from[k]
                + i_core_from_term[k]
                + i_cap_f[k]
            )
        )
        alg_eqs.append(
            it_act[k] - (
                -n_tap * i_series_to[k]
                + i_cap_t[k]
            )
        )

    if if_n_act is not None:
        neutral_from_kcl: Expr = if_n_act + if_act[0] + if_act[1] + if_act[2]

        if from_ground_current is not None:
            neutral_from_kcl = neutral_from_kcl + from_ground_current
        else:
            pass

        alg_eqs.append(neutral_from_kcl)
    else:
        pass

    if it_n_act is not None:
        neutral_to_kcl: Expr = it_n_act + it_act[0] + it_act[1] + it_act[2]

        if to_ground_current is not None:
            neutral_to_kcl = neutral_to_kcl + to_ground_current
        else:
            pass

        alg_eqs.append(neutral_to_kcl)
    else:
        pass

    block.algebraic_eqs = alg_eqs
    output_vars: list[Var] = list()
    if if_n_act is not None:
        output_vars.append(if_n_act)
    else:
        pass

    output_vars.extend(if_act)

    if it_n_act is not None:
        output_vars.append(it_n_act)
    else:
        pass

    output_vars.extend(it_act)
    block.out_vars = output_vars

    # ------------------------------------------------------------------
    # External mapping.
    # ------------------------------------------------------------------
    if_keys: Dict[str, VarPowerFlowReferenceType] = {
        "N": VarPowerFlowReferenceType.if_N,
        "A": VarPowerFlowReferenceType.if_A,
        "B": VarPowerFlowReferenceType.if_B,
        "C": VarPowerFlowReferenceType.if_C,
    }
    it_keys: Dict[str, VarPowerFlowReferenceType] = {
        "N": VarPowerFlowReferenceType.it_N,
        "A": VarPowerFlowReferenceType.it_A,
        "B": VarPowerFlowReferenceType.it_B,
        "C": VarPowerFlowReferenceType.it_C,
    }
    Sf_keys: Dict[str, VarPowerFlowReferenceType] = {
        "A": VarPowerFlowReferenceType.Sf_A,
        "B": VarPowerFlowReferenceType.Sf_B,
        "C": VarPowerFlowReferenceType.Sf_C,
    }
    St_keys: Dict[str, VarPowerFlowReferenceType] = {
        "A": VarPowerFlowReferenceType.St_A,
        "B": VarPowerFlowReferenceType.St_B,
        "C": VarPowerFlowReferenceType.St_C,
    }
    d_vf_keys: Dict[str, VarPowerFlowReferenceType] = {
        "N": VarPowerFlowReferenceType.d_v_N_f,
        "A": VarPowerFlowReferenceType.d_v_A_f,
        "B": VarPowerFlowReferenceType.d_v_B_f,
        "C": VarPowerFlowReferenceType.d_v_C_f,
    }
    d_vt_keys: Dict[str, VarPowerFlowReferenceType] = {
        "N": VarPowerFlowReferenceType.d_v_N_t,
        "A": VarPowerFlowReferenceType.d_v_A_t,
        "B": VarPowerFlowReferenceType.d_v_B_t,
        "C": VarPowerFlowReferenceType.d_v_C_t,
    }

    mapping: Dict[VarPowerFlowReferenceType, Var | None] = {
        if_keys["N"]: None,
        if_keys["A"]: None,
        if_keys["B"]: None,
        if_keys["C"]: None,
        it_keys["N"]: None,
        it_keys["A"]: None,
        it_keys["B"]: None,
        it_keys["C"]: None,
        vf_keys["N"]: None,
        vf_keys["A"]: None,
        vf_keys["B"]: None,
        vf_keys["C"]: None,
        vt_keys["N"]: None,
        vt_keys["A"]: None,
        vt_keys["B"]: None,
        vt_keys["C"]: None,
    }

    mapping[vf_keys["N"]] = v_f_n
    mapping[vf_keys["A"]] = v_f[0]
    mapping[vf_keys["B"]] = v_f[1]
    mapping[vf_keys["C"]] = v_f[2]

    mapping[vt_keys["N"]] = v_t_n
    mapping[vt_keys["A"]] = v_t[0]
    mapping[vt_keys["B"]] = v_t[1]
    mapping[vt_keys["C"]] = v_t[2]

    mapping[if_keys["N"]] = if_n_act
    mapping[if_keys["A"]] = if_act[0]
    mapping[if_keys["B"]] = if_act[1]
    mapping[if_keys["C"]] = if_act[2]

    mapping[it_keys["N"]] = it_n_act
    mapping[it_keys["A"]] = it_act[0]
    mapping[it_keys["B"]] = it_act[1]
    mapping[it_keys["C"]] = it_act[2]

    block.external_mapping = mapping

    # ------------------------------------------------------------------
    # Initialization equations.
    #
    # PF-derived terminal currents if_act / it_act are initialized before
    # init_eqs through external_mapping. The magnetic branch is initialized
    # from the from-side winding voltage only.
    # ------------------------------------------------------------------
    c_inv_sqrt3: Expr = c1 / sym.sqrt(c3)

    voltage_derived_flux_init: list[Expr] = [
        -(v_f_w[2] - v_f_w[1]) * c_inv_sqrt3,
        -(v_f_w[0] - v_f_w[2]) * c_inv_sqrt3,
        -(v_f_w[1] - v_f_w[0]) * c_inv_sqrt3,
    ]
    fixed_flux_init: list[Expr] = [
        xfmr_initial_flux_a,
        xfmr_initial_flux_b,
        xfmr_initial_flux_c,
    ]
    lam_leg_init: list[Expr] = [
        xfmr_use_fixed_initial_flux * fixed_flux_init[k]
        + (c1 - xfmr_use_fixed_initial_flux) * voltage_derived_flux_init[k]
        for k in range(3)
    ]

    init_eqs: Dict[Var, Expr] = {}

    # Charge states.
    for k in range(3):
        init_eqs[q_f[k]] = xfmr_c_term * v_f_term[k]
        init_eqs[q_t[k]] = xfmr_c_term * v_t_term[k]

    # Core flux-linkage states from the from-side winding voltage set.
    for k in range(3):
        init_eqs[lam_leg[k]] = lam_leg_init[k]

    # Core leg currents from the constitutive law.
    # for k in range(3):
    #     init_eqs[i_leg_core[k]] = (
    #         xfmr_use_linear_core * (lam_leg[k] / (xfmr_core_linear_l_pu + c_eps))
    #         + (c1 - xfmr_use_linear_core) * (lam_leg[k] / (xfmr_core_a_prime + c_eps))
    #     )
    for k in range(3):
        abs_lam_k: Expr = sym.sqrt(lam_leg[k] * lam_leg[k] + c_smooth)
        i_leg_core_nl_init: Expr = (
                xfmr_core_a_prime * lam_leg[k]
                / (c1 - xfmr_core_b_prime * abs_lam_k + c_eps)
        )
        first_segment_slope_init: Expr = xfmr_piecewise_current_1 / xfmr_piecewise_flux_1
        second_segment_slope_init: Expr = (
            (xfmr_piecewise_current_2 - xfmr_piecewise_current_1)
            / (xfmr_piecewise_flux_2 - xfmr_piecewise_flux_1)
        )
        clamped_lam_init: Expr = sym.max(
            -xfmr_piecewise_flux_1,
            sym.min(lam_leg[k], xfmr_piecewise_flux_1),
        )
        excess_lam_init: Expr = (
            sym.max(lam_leg[k] - xfmr_piecewise_flux_1, c0)
            + sym.min(lam_leg[k] + xfmr_piecewise_flux_1, c0)
        )
        i_leg_core_piecewise_init: Expr = (
            first_segment_slope_init * clamped_lam_init
            + second_segment_slope_init * excess_lam_init
        )

        init_eqs[i_leg_core[k]] = (
                xfmr_use_linear_core * (lam_leg[k] / (xfmr_core_linear_l_pu + c_eps))
                + (c1 - xfmr_use_linear_core) * (
                    xfmr_use_piecewise_core * i_leg_core_piecewise_init
                    + (c1 - xfmr_use_piecewise_core) * i_leg_core_nl_init
                )
        )

    # Return-path currents from initialized fluxes.
    init_eqs[i_return_path] = (
        independent_core_selector * c0
        + five_leg_selector * (lam_return_total / (c2 * yoke_linear_coeff + outer_linear_coeff + c_eps))
        + three_leg_selector * (lam_return_total / (c2 * yoke_linear_coeff + c_eps))
    )
    init_eqs[i_return_total] = (
        five_leg_selector * c2 * i_return_path
        + three_leg_selector * i_return_path
    )

    # Net magnetizing currents.
    for k in range(3):
        init_eqs[i_mag[k]] = i_leg_core[k] - i_return_total

    # Core-loss currents referred to the from side.
    for k in range(3):
        init_eqs[i_loss_leg[k]] = g_core_leg * v_f_w[k]

    # Balanced fundamental seeds, consistent with the voltage-derived core
    # flux above: capacitance current is C*dV/dt, not a KCL residual absorbing
    # the core current. Project terminal current back to the winding frame
    # and subtract the parallel core and capacitor currents from leakage.
    for k in range(3):
        next_phase = (k + 1) % 3
        previous_phase = (k + 2) % 3
        init_eqs[i_cap_f[k]] = xfmr_c_term * omega_base * (
            v_f_term[previous_phase] - v_f_term[next_phase]) * c_inv_sqrt3
        init_eqs[i_cap_t[k]] = xfmr_c_term * omega_base * (
            v_t_term[previous_phase] - v_t_term[next_phase]) * c_inv_sqrt3
        init_eqs[i_leak[k]] = sum(
            (c_f_expr[j][k] * (if_act[j] - i_cap_f[j]) for j in range(3)), c0
        ) - i_mag[k] - i_loss_leg[k]

    block.init_eqs = init_eqs

    # ------------------------------------------------------------------
    # Differential initialization equations.
    # ------------------------------------------------------------------
    diff_init_eqs: Dict[Var, Expr] = {}

    for k in range(3):
        diff_init_eqs[di_leak[k]] = l_inv * (v_leak[k] - r_sc_pu * i_leak[k])
        diff_init_eqs[dlam_leg[k]] = omega_base * v_f_w[k]
        diff_init_eqs[dq_f[k]] = i_cap_f[k]
        diff_init_eqs[dq_t[k]] = i_cap_t[k]

    block.diff_init_eqs = diff_init_eqs

    grounding_pairs: List[Tuple[Var, Block]] = list()
    if v_f_n is not None and from_grounding_link_block is not None:
        grounding_pairs.append((v_f_n, from_grounding_link_block))
    else:
        pass

    if v_t_n is not None and to_grounding_link_block is not None:
        grounding_pairs.append((v_t_n, to_grounding_link_block))
    else:
        pass

    _attach_transformer_editor_diagram(
        root_block=block,
        input_vars=input_vars,
        output_vars=output_vars,
        grounding_pairs=grounding_pairs,
    )

    templ.block.children.append(block)
    templ.block.external_mapping = block.external_mapping
    templ.block.in_vars = block.in_vars
    templ.block.out_vars = block.out_vars

    return templ


class XfmrEmtTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf):
        super().__init__(
            vf,
            params=[
                TemplateProp(name="conn_f", units="", descr="From-side winding connection.", tpe=WindingType, value=None),
                TemplateProp(name="conn_t", units="", descr="To-side winding connection.", tpe=WindingType, value=None),
                TemplateProp(name="name", units="", descr="Name of the emt model.", tpe=str, value="xfmr_emt_template"),
            ]
        )

    def eval(self) -> EmtModelTemplate:
        return get_xfmr_emt_template(
            self.vf,
            conn_f=self.get_value("conn_f"),
            conn_t=self.get_value("conn_t"),
            name=self.get_value("name"),
        )
