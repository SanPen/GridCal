# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from enum import IntEnum

from VeraGridEngine.enumerations import (
    ConverterControlType,
    DeviceType,
    ParamPowerFlowReferenceType,
    VarPowerFlowReferenceType,
)
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Expr, find_name_in_block
import VeraGridEngine.Utils.Symbolic.symbolic as sym

from VeraGridEngine.Templates.Emt.converter_emt_template import (
    _build_pseudo_emt_converter_vsc_block,
    _build_pseudo_emt_converter_pll_block,
    _build_pseudo_emt_converter_outer_loop_block,
    _build_pseudo_emt_converter_inner_loop_block,
    _build_pseudo_emt_converter_transformer_block,
    _converter_control_type_code,
)


def _tag_connected_pair(vf: VarFactory, out_var: Var, in_var: Var, shared_name: str) -> None:
    """
    Add one shared reference to both ends of one internal child-block connection.

    The EMT editor derives visible inter-block edges from shared references on
    child ports. The runtime symbolic connection is still registered through the
    shared variable factory, but the explicit shared tag keeps the editor graph
    readable without exposing the signal at the root block.

    :param vf: Shared variable factory.
    :param out_var: Source child output.
    :param in_var: Destination child input.
    :param shared_name: Shared-reference identifier.
    :return: None.
    """
    vf.add_shared_ref_to_var(out_var, shared_name)
    vf.add_shared_ref_to_var(in_var, shared_name)


def _find_block_var(block: Block, var_name: str) -> Var:
    """
    Find one variable by name inside one block and fail loudly if missing.

    :param block: Block to inspect.
    :param var_name: Variable name.
    :return: Matching variable.
    """
    result: Var | None = find_name_in_block(var_name, block)
    if result is None:
        raise ValueError(f"Variable {var_name} not found in block {block.name}")
    return result


def _find_event_parameter(block: Block, var_name: str) -> Var:
    """Return one runtime parameter declared directly by ``block``."""
    for parameter in block.event_dict:
        if parameter.name == var_name:
            return parameter
    raise ValueError(f"Event parameter {var_name} not found in block {block.name}")


class PvEmtModelLevel(IntEnum):
    """
    Enumerate the supported PV EMT template detail levels.

    ``LEVEL_1`` is the simplified PV availability plus MPPT-lag model, while
    ``LEVEL_2`` adds the averaged PV plus DC-DC boost dynamics.

    :ivar LEVEL_1: Simplified PV availability plus MPPT-lag model.
    :ivar LEVEL_2: Averaged PV plus DC-DC boost model.
    """

    LEVEL_1 = 1
    LEVEL_2 = 2


# =============================================================================
# Shared converter assembly helpers
# =============================================================================


def _build_converter_blocks(vf: VarFactory, name: str) -> tuple[Block, Block, Block, Block, Block]:
    """
    Build the imported pseudo-EMT converter sub-blocks used by both PV levels.

    This helper intentionally reuses the existing VeraGrid converter blocks. The
    PV templates in this file add only the PV/DC-source side and then wire it to
    the imported VSC DC terminal. This keeps PLL, VSC, outer-loop, inner-loop
    and dq0/abc interface behaviour consistent with the already available
    pseudo-EMT converter template.

    :param vf: EMT symbolic variable factory.
    :param name: Symbolic model name.
    :return: Tuple with VSC, PLL, outer-loop, inner-loop and AC-interface blocks.
    """
    vsc_block: Block = _build_pseudo_emt_converter_vsc_block(vf=vf, name=name)
    pll_block: Block = _build_pseudo_emt_converter_pll_block(vf=vf, name=name)
    outer_loop_block: Block = _build_pseudo_emt_converter_outer_loop_block(vf=vf, name=name)
    inner_loop_block: Block = _build_pseudo_emt_converter_inner_loop_block(vf=vf, name=name)
    transformer_block: Block = _build_pseudo_emt_converter_transformer_block(vf=vf, name=name)

    # A PV generator is a Pac/Qac-controlled converter by construction.  Keep
    # this configuration in the reusable model instead of requiring every
    # runner to rewrite the imported converter's generic Vdc/Qac defaults.
    vsc_block.event_dict[vsc_block.api_obj_mapping[ParamPowerFlowReferenceType.converter_control_mode_1]] = vf.add_const(
        float(_converter_control_type_code(ConverterControlType.Pac))
    )
    vsc_block.event_dict[vsc_block.api_obj_mapping[ParamPowerFlowReferenceType.converter_control_mode_2]] = vf.add_const(
        float(_converter_control_type_code(ConverterControlType.Qac))
    )

    return vsc_block, pll_block, outer_loop_block, inner_loop_block, transformer_block


def _connect_imported_converter_blocks(
    vf: VarFactory,
    name: str,
    v_A: Var,
    v_B: Var,
    v_C: Var,
    dc_voltage_source: Var,
    vsc_block: Block,
    pll_block: Block,
    outer_loop_block: Block,
    inner_loop_block: Block,
    transformer_block: Block,
) -> None:
    """
    Wire the imported pseudo-EMT converter blocks to one internal DC source.

    The wiring mirrors ``get_full_pseudo_emt_converter`` except that the VSC
    DC-terminal voltage is not an external DC bus. Instead it is supplied by the
    PV-side block of the current template. The VSC DC current output is also
    exposed to the PV-side block so that the PV/DC stage can compute its own DC
    power and internal dynamics.

    :param v_A: Phase-A terminal voltage input.
    :param v_B: Phase-B terminal voltage input.
    :param v_C: Phase-C terminal voltage input.
    :param dc_voltage_source: Internal DC terminal voltage supplied to the VSC.
    :param vsc_block: Imported VSC/DC-link block.
    :param pll_block: Imported PLL block.
    :param outer_loop_block: Imported outer-loop block.
    :param inner_loop_block: Imported inner-loop block.
    :param transformer_block: Imported AC-side dq0/abc interface block.
    :return: None.
    """
    transformer_i_A = _find_block_var(transformer_block, "i_A")
    transformer_i_B = _find_block_var(transformer_block, "i_B")
    transformer_i_C = _find_block_var(transformer_block, "i_C")
    transformer_v_d = _find_block_var(transformer_block, "v_d")
    transformer_v_q = _find_block_var(transformer_block, "v_q")
    transformer_v_0 = _find_block_var(transformer_block, "v_0")
    transformer_i_d = _find_block_var(transformer_block, "i_d")
    transformer_i_q = _find_block_var(transformer_block, "i_q")
    transformer_i_0 = _find_block_var(transformer_block, "i_0")

    vsc_v_dc = _find_block_var(vsc_block, "v_dc")
    vsc_i_dc = _find_block_var(vsc_block, "i_dc")
    vsc_P = _find_block_var(vsc_block, "P")
    vsc_Q = _find_block_var(vsc_block, "Q")
    vsc_sbase = _find_block_var(vsc_block, "sbase")
    vsc_P_ref = _find_block_var(vsc_block, "P_ref")
    vsc_Q_ref = _find_block_var(vsc_block, "Q_ref")
    vsc_Vdc_ref = _find_block_var(vsc_block, "Vdc_ref")
    vsc_omega_base = _find_block_var(vsc_block, "omega_base")
    vsc_phi_v = _find_block_var(vsc_block, "phi_v")
    vsc_Vpk = _find_block_var(vsc_block, "Vpk")
    vsc_R_eq = _find_block_var(vsc_block, "R_eq")
    vsc_L_eq = _find_block_var(vsc_block, "L_eq")
    vsc_pll_kp = _find_block_var(vsc_block, "pll_kp")
    vsc_pll_ki = _find_block_var(vsc_block, "pll_ki")
    vsc_i_kp = _find_block_var(vsc_block, "i_kp")
    vsc_i_ki = _find_block_var(vsc_block, "i_ki")
    vsc_vdc_kp = _find_block_var(vsc_block, "vdc_kp")
    vsc_vdc_ki = _find_block_var(vsc_block, "vdc_ki")
    vsc_q_kp = _find_block_var(vsc_block, "q_kp")
    vsc_q_ki = _find_block_var(vsc_block, "q_ki")
    vsc_i_max = _find_block_var(vsc_block, "i_max")
    vsc_m_max = _find_block_var(vsc_block, "m_max")
    vsc_P_loss = _find_block_var(vsc_block, "P_loss")
    vsc_tau_meas = _find_block_var(vsc_block, "tau_meas")
    vsc_aw_gain = _find_block_var(vsc_block, "aw_gain")
    vsc_vdc_floor = _find_block_var(vsc_block, "vdc_floor")
    vsc_i_dc_conv = _find_block_var(vsc_block, "i_dc_conv")
    vsc_regulate_vdc = _find_block_var(vsc_block, "regulate_vdc_mode")
    vsc_regulate_q = _find_block_var(vsc_block, "regulate_q_mode")
    vsc_regulate_active = _find_block_var(vsc_block, "regulate_active_mode")

    pll_theta = _find_block_var(pll_block, "theta_pll")
    pll_omega = _find_block_var(pll_block, "omega_pll")

    outer_P_f = _find_block_var(outer_loop_block, "P_f")
    outer_Q_f = _find_block_var(outer_loop_block, "Q_f")
    outer_i_0_ref = _find_block_var(outer_loop_block, "i_0_ref")
    outer_i_d_ref = _find_block_var(outer_loop_block, "i_d_ref")
    outer_i_q_ref = _find_block_var(outer_loop_block, "i_q_ref")

    inner_v_cmd_d = _find_block_var(inner_loop_block, "v_cmd_d")
    inner_v_cmd_q = _find_block_var(inner_loop_block, "v_cmd_q")
    inner_v_cmd_0 = _find_block_var(inner_loop_block, "v_cmd_0")
    inner_k_v_conv = _find_block_var(inner_loop_block, "k_v_conv")

    vf.add_connections(transformer_block.in_vars[0:3], [v_A, v_B, v_C])
    vf.add_connections([vsc_block.in_vars[6]], [dc_voltage_source])
    _tag_connected_pair(vf, dc_voltage_source, vsc_block.in_vars[6], f"{vsc_block.name}_vdc_src")

    vf.add_connections(vsc_block.in_vars[0:3], [transformer_v_d, transformer_v_q, transformer_v_0])
    vf.add_connections(vsc_block.in_vars[3:6], [transformer_i_d, transformer_i_q, transformer_i_0])
    vf.add_connections([pll_block.in_vars[0]], [transformer_v_q])
    vf.add_connections(outer_loop_block.in_vars[0:3], [transformer_v_d, transformer_v_q, transformer_v_0])
    vf.add_connections(outer_loop_block.in_vars[3:6], [transformer_i_d, transformer_i_q, transformer_i_0])
    vf.add_connections(inner_loop_block.in_vars[0:3], [transformer_v_d, transformer_v_q, transformer_v_0])
    vf.add_connections(inner_loop_block.in_vars[3:6], [transformer_i_d, transformer_i_q, transformer_i_0])
    for idx, shared_name in enumerate(["v_d", "v_q", "v_0"]):
        _tag_connected_pair(vf, [transformer_v_d, transformer_v_q, transformer_v_0][idx], vsc_block.in_vars[idx], f"{name}_{shared_name}_vsc")
        _tag_connected_pair(vf, [transformer_v_d, transformer_v_q, transformer_v_0][idx], outer_loop_block.in_vars[idx], f"{name}_{shared_name}_outer")
        _tag_connected_pair(vf, [transformer_v_d, transformer_v_q, transformer_v_0][idx], inner_loop_block.in_vars[idx], f"{name}_{shared_name}_inner")
    for idx, shared_name in enumerate(["i_d", "i_q", "i_0"]):
        _tag_connected_pair(vf, [transformer_i_d, transformer_i_q, transformer_i_0][idx], vsc_block.in_vars[3 + idx], f"{name}_{shared_name}_vsc")
        _tag_connected_pair(vf, [transformer_i_d, transformer_i_q, transformer_i_0][idx], outer_loop_block.in_vars[3 + idx], f"{name}_{shared_name}_outer")
        _tag_connected_pair(vf, [transformer_i_d, transformer_i_q, transformer_i_0][idx], inner_loop_block.in_vars[3 + idx], f"{name}_{shared_name}_inner")
    _tag_connected_pair(vf, transformer_v_q, pll_block.in_vars[0], f"{name}_v_q_pll_in")

    vf.add_connections(
        pll_block.in_vars[1:5],
        [vsc_omega_base, vsc_pll_kp, vsc_pll_ki, vsc_phi_v],
    )
    for idx, shared_name in enumerate(["omega_base", "pll_kp", "pll_ki", "phi_v"]):
        _tag_connected_pair(vf, [vsc_omega_base, vsc_pll_kp, vsc_pll_ki, vsc_phi_v][idx], pll_block.in_vars[1 + idx], f"{name}_{shared_name}_pll")
    vf.add_connections(
        [outer_loop_block.in_vars[6], outer_loop_block.in_vars[7], outer_loop_block.in_vars[8]],
        [vsc_v_dc, vsc_P, vsc_Q],
    )
    for in_idx, out_var, shared_name in [(6, vsc_v_dc, "v_dc_outer"), (7, vsc_P, "p_outer"), (8, vsc_Q, "q_outer")]:
        _tag_connected_pair(vf, out_var, outer_loop_block.in_vars[in_idx], f"{name}_{shared_name}")
    vf.add_connections(
        outer_loop_block.in_vars[9:25],
        [
            vsc_sbase, vsc_P_ref, vsc_Q_ref, vsc_Vdc_ref, vsc_Vpk,
            vsc_P_loss, vsc_vdc_kp, vsc_vdc_ki, vsc_q_kp, vsc_q_ki,
            vsc_i_max, vsc_tau_meas, vsc_aw_gain, vsc_regulate_vdc, vsc_regulate_q, vsc_regulate_active,
        ],
    )
    for offset, out_var in enumerate([vsc_sbase, vsc_P_ref, vsc_Q_ref, vsc_Vdc_ref, vsc_Vpk,
                                      vsc_P_loss, vsc_vdc_kp, vsc_vdc_ki, vsc_q_kp, vsc_q_ki,
                                      vsc_i_max, vsc_tau_meas, vsc_aw_gain, vsc_regulate_vdc, vsc_regulate_q, vsc_regulate_active]):
        _tag_connected_pair(vf, out_var, outer_loop_block.in_vars[9 + offset], f"{name}_outer_aux_{offset}")
    vf.add_connections(
        [inner_loop_block.in_vars[6], inner_loop_block.in_vars[7], inner_loop_block.in_vars[8], inner_loop_block.in_vars[9]],
        [pll_omega, vsc_omega_base, vsc_R_eq, vsc_L_eq],
    )
    _tag_connected_pair(vf, pll_omega, inner_loop_block.in_vars[6], f"{name}_omega_pll_to_inner")
    _tag_connected_pair(vf, vsc_omega_base, inner_loop_block.in_vars[7], f"{name}_omega_base_inner")
    _tag_connected_pair(vf, vsc_R_eq, inner_loop_block.in_vars[8], f"{name}_r_eq_inner")
    _tag_connected_pair(vf, vsc_L_eq, inner_loop_block.in_vars[9], f"{name}_l_eq_inner")
    vf.add_connections(inner_loop_block.in_vars[10:13], [outer_i_0_ref, outer_i_d_ref, outer_i_q_ref])
    for idx, shared_name in enumerate(["v_cmd_d", "v_cmd_q", "v_cmd_0"]):
        _tag_connected_pair(vf, [outer_i_0_ref, outer_i_d_ref, outer_i_q_ref][idx], inner_loop_block.in_vars[10 + idx], f"{name}_{shared_name}")
    vf.add_connections(
        inner_loop_block.in_vars[13:25],
        [
            vsc_i_kp, vsc_i_ki, vsc_aw_gain, vsc_m_max,
            vsc_Vdc_ref, vsc_v_dc, vsc_vdc_floor, vsc_sbase,
            vsc_P_ref, vsc_Q_ref, vsc_P_loss, vsc_Vpk,
        ],
    )
    for offset, out_var in enumerate([vsc_i_kp, vsc_i_ki, vsc_aw_gain, vsc_m_max,
                                      vsc_Vdc_ref, vsc_v_dc, vsc_vdc_floor, vsc_sbase,
                                      vsc_P_ref, vsc_Q_ref, vsc_P_loss, vsc_Vpk]):
        _tag_connected_pair(vf, out_var, inner_loop_block.in_vars[13 + offset], f"{name}_inner_aux_{offset}")

    vf.add_connections([transformer_block.in_vars[3], transformer_block.in_vars[4]], [pll_theta, pll_omega])
    _tag_connected_pair(vf, pll_theta, transformer_block.in_vars[3], f"{name}_theta_pll")
    _tag_connected_pair(vf, pll_omega, transformer_block.in_vars[4], f"{name}_omega_pll")
    vf.add_connections(
        transformer_block.in_vars[5:8],
        [vsc_omega_base, vsc_R_eq, vsc_L_eq],
    )
    for idx, shared_name in enumerate(["omega_base_tf", "r_eq_tf", "l_eq_tf"]):
        _tag_connected_pair(vf, [vsc_omega_base, vsc_R_eq, vsc_L_eq][idx], transformer_block.in_vars[5 + idx], f"{name}_{shared_name}")
    vf.add_connections(transformer_block.in_vars[8:11], [inner_v_cmd_d, inner_v_cmd_q, inner_v_cmd_0])
    for idx, shared_name in enumerate(["v_cmd_d_tf", "v_cmd_q_tf", "v_cmd_0_tf"]):
        _tag_connected_pair(vf, [inner_v_cmd_d, inner_v_cmd_q, inner_v_cmd_0][idx], transformer_block.in_vars[8 + idx], f"{name}_{shared_name}")
    vf.add_connections(
        transformer_block.in_vars[11:16],
        [vsc_sbase, vsc_P_ref, vsc_Q_ref, vsc_P_loss, vsc_Vpk],
    )
    for offset, out_var in enumerate([vsc_sbase, vsc_P_ref, vsc_Q_ref, vsc_P_loss, vsc_Vpk]):
        _tag_connected_pair(vf, out_var, transformer_block.in_vars[11 + offset], f"{name}_tf_aux_{offset}")


# =============================================================================
# Level 1 — PV AVM grid-following
# PV availability + MPPT lag + imported VSC controls
# =============================================================================


def _build_level1_pv_availability_block(vf: VarFactory, name: str) -> Block:
    """
    Build the Level-1 PV availability and MPPT-lag DC source block.

    The Level-1 PV model is intentionally equivalent in complexity to the BESS
    Level-1 block. It does not model a DC-DC converter. Instead, it aggregates
    the PV array into a DC source whose available power depends on irradiance
    and cell temperature, and whose active-power availability follows an MPPT
    first-order lag.

    The imported VSC block still owns the explicit DC-link capacitor ``C_dc``.
    Therefore this PV block supplies only the internal DC terminal voltage used
    by the VSC and computes diagnostic PV current/power quantities from the VSC
    DC current feedback.

    :param vf: EMT symbolic variable factory.
    :param name: Symbolic model name.
    :return: Level-1 PV availability block.
    """
    i_dc = vf.add_var(name=f"i_dc_pv_l1_in")
    v_dc_ctrl = vf.add_var(name=f"v_dc_ctrl_pv_l1_in")

    p_mppt = vf.add_var(name=f"p_mppt_l1")
    d_p_mppt = vf.add_diff_var(name=f"d_p_mppt_l1", base_var=p_mppt)

    v_dc_bus = vf.add_var(name=f"v_dc_bus_pv_l1", reference=VarPowerFlowReferenceType.Vdc)
    p_avail = vf.add_var(name=f"p_avail_l1")
    p_pv = vf.add_var(name=f"p_pv_l1")
    i_pv = vf.add_var(name=f"i_pv_l1")
    v_oc = vf.add_var(name=f"v_oc_pv_l1")
    p_curt = vf.add_var(name=f"p_curt_l1")

    p_rated = vf.add_var(name=f"p_rated_l1")
    irradiance = vf.add_var(name=f"irradiance_l1")
    irradiance_ref = vf.add_var(name=f"irradiance_ref_l1")
    t_cell = vf.add_var(name=f"t_cell_l1")
    t_ref = vf.add_var(name=f"t_ref_l1")
    temp_coeff_p = vf.add_var(name=f"temp_coeff_p_l1")
    t_mppt = vf.add_var(name=f"t_mppt_l1")
    v_dc_ref = vf.add_var(name=f"v_dc_ref_l1", shared_reference="Vdc_nom_reference")
    r_pv = vf.add_var(name=f"r_pv_l1")
    k_pv_power = vf.add_var(name=f"k_pv_power_l1")
    k_vdc_ctrl = vf.add_var(name=f"k_vdc_ctrl_l1")

    c0 = vf.add_const(0.0)
    eps = vf.add_const(1e-10)

    irradiance_eff: Expr = sym.max(irradiance_ref, eps)
    p_avail_raw: Expr = p_rated * (irradiance / irradiance_eff) * (vf.add_const(1.0) + temp_coeff_p * (t_cell - t_ref))
    p_avail_expr: Expr = sym.hard_sat(p_avail_raw, c0, p_rated)
    mppt_limited_power: Expr = sym.hard_sat(p_mppt, c0, p_avail)
    r_pv_eff: Expr = sym.max(r_pv, eps)
    p_pv_init: Expr = sym.hard_sat(mppt_limited_power, c0, (v_dc_ref * v_dc_ref) / (vf.add_const(4.0) * r_pv_eff))
    p_init_disc: Expr = sym.max(v_dc_ref * v_dc_ref - vf.add_const(4.0) * r_pv_eff * p_pv_init, eps)
    i_pv_init_mag: Expr = (v_dc_ref - sym.sqrt(p_init_disc)) / (vf.add_const(2.0) * r_pv_eff)
    i_pv_init: Expr = -i_pv_init_mag
    v_dc_bus_init: Expr = v_dc_ref + r_pv_eff * i_pv_init
    v_oc_ctrl_expr: Expr = v_dc_ref - k_vdc_ctrl * (v_dc_ctrl - v_dc_ref)

    return Block(
        state_eqs=[
            # Irradiance and temperature modify the available PV power. MPPT is
            # represented as a first-order lag between available power and the
            # power that the inverter can actually request from the PV array.
            (p_avail - p_mppt) / (t_mppt + eps),
        ],
        state_vars=[p_mppt],
        diff_vars=[d_p_mppt],
        algebraic_eqs=[
            p_avail - p_avail_expr,
            # PV-side DC sign convention:
            # * positive ``p_pv`` means PV power delivered to the converter,
            # * positive ``i_pv`` would mean source current delivered to the
            #   converter. The imported pseudo-EMT converter uses the same
            #   terminal-current orientation, so both currents are negative
            #   during export and must be equal at the shared internal port.
            i_pv - i_dc,
            p_pv + v_dc_bus * i_pv,
            # The Level-1 source is a Thevenin-like PV equivalent around one
            # MPPT operating voltage. A power droop term drives the delivered
            # DC power toward the irradiance-limited MPPT target without adding
            # a second internal DC storage state.
            # Local PV-side Vdc feedback trims the source open-circuit voltage so
            # the PV block can regulate the converter DC-link without modifying
            # the shared converter outer-loop implementation.
            v_oc - v_oc_ctrl_expr,
            v_dc_bus - (v_oc + r_pv * i_pv - k_pv_power * (p_pv - mppt_limited_power)),
            # Curtailment is the available PV power that is not delivered to the
            # converter. Keep it non-negative even under small numerical errors.
            p_curt - sym.max(p_avail - mppt_limited_power, c0),
        ],
        algebraic_vars=[v_dc_bus, p_avail, p_pv, i_pv, v_oc, p_curt],
        parameters={p_rated: vf.add_const(None)},
        event_dict={
            irradiance: vf.add_const(1000.0),
            irradiance_ref: vf.add_const(1000.0),
            t_cell: vf.add_const(25.0),
            t_ref: vf.add_const(25.0),
            temp_coeff_p: vf.add_const(0.0),
            t_mppt: vf.add_const(0.05),
            v_dc_ref: vf.add_const(1.0),
            r_pv: vf.add_const(0.0),
            k_pv_power: vf.add_const(2.0),
            k_vdc_ctrl: vf.add_const(0.0),
        },
        init_eqs={
            p_avail: p_avail_expr,
            p_mppt: p_avail_expr,
            p_pv: p_pv_init,
            i_pv: i_pv_init,
            v_oc: v_dc_ref,
            v_dc_bus: v_dc_bus_init,
            p_curt: p_avail_expr - p_pv_init,
        },
        diff_init_eqs={d_p_mppt: c0},
        in_vars=[i_dc, v_dc_ctrl],
        out_vars=[v_dc_bus, p_mppt],
        name=f"{name}_pv_level1",
        api_obj_mapping={ParamPowerFlowReferenceType.pv_rated_power_pu: p_rated},
    )


def get_pv_avm_grid_following_emt_template(
    vf: VarFactory,
    name: str = "pv_avm_grid_following_emt",
) -> EmtModelTemplate:
    """
    Build the Level-1 PV averaged-value grid-following EMT template.

    This model is the PV counterpart of the Level-1 BESS model. It can replace
    the BESS template in the same AC EMT examples because the external network
    interface is the same: three AC phase voltages as inputs and three AC phase
    currents as outputs.

    Structure
    ---------
    The assembled model is::

        PV availability from irradiance and temperature
            -> first-order MPPT power availability
            -> internal DC terminal voltage
            -> imported VSC/DC-link block
            -> imported SRF-PLL
            -> imported outer P/Q or Vdc/Q loop
            -> imported inner dq0 current controller
            -> imported AC-side dq0/abc interface
            -> abc current injection into the EMT network

    Included behaviour
    ------------------
    * Irradiance-dependent available active power.
    * Cell-temperature active-power correction.
    * MPPT first-order lag.
    * PV curtailment diagnostic channel.
    * Existing averaged VSC power balance and DC-link dynamics.
    * Existing PLL, dq0 current control, current limiting and modulation limit.

    Not included
    ------------
    * Explicit PV diode equation or cell-level model.
    * Explicit averaged boost converter.
    * Switching-level PWM or semiconductor devices.
    * Plant-level PPC beyond the imported converter control interface.

    :param vf: EMT symbolic variable factory.
    :param name: Symbolic model name.
    :return: Fully assembled Level-1 PV EMT template.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name
    templ.block.name = name

    v_A: Var = vf.add_var(name=f"v_A", reference=VarPowerFlowReferenceType.v_A)
    v_B: Var = vf.add_var(name=f"v_B", reference=VarPowerFlowReferenceType.v_B)
    v_C: Var = vf.add_var(name=f"v_C", reference=VarPowerFlowReferenceType.v_C)

    vsc_block, pll_block, outer_loop_block, inner_loop_block, transformer_block = _build_converter_blocks(
        vf=vf,
        name=name,
    )
    pv_block: Block = _build_level1_pv_availability_block(vf=vf, name=name)

    # AC power flow contains no DC voltage. Use the PV reference as the one
    # model-owned DC nominal value and connect the imported VSC to it.
    vf.add_connections(
        [_find_event_parameter(vsc_block, "Vdc_nom")],
        [_find_event_parameter(pv_block, "v_dc_ref_l1")],
    )

    _connect_imported_converter_blocks(
        vf=vf,
        name=name,
        v_A=v_A,
        v_B=v_B,
        v_C=v_C,
        dc_voltage_source=pv_block.out_vars[0],
        vsc_block=vsc_block,
        pll_block=pll_block,
        outer_loop_block=outer_loop_block,
        inner_loop_block=inner_loop_block,
        transformer_block=transformer_block,
    )
    vf.add_connections(pv_block.in_vars[0:2], [vsc_block.out_vars[1], vsc_block.out_vars[0]])
    _tag_connected_pair(vf, vsc_block.out_vars[1], pv_block.in_vars[0], f"{name}_i_dc_feedback")
    _tag_connected_pair(vf, vsc_block.out_vars[0], pv_block.in_vars[1], f"{name}_v_dc_feedback")

    templ.block.children.extend([pv_block, vsc_block, pll_block, inner_loop_block, outer_loop_block, transformer_block])
    templ.block.in_vars = [v_A, v_B, v_C]
    templ.block.out_vars = [
        transformer_block.out_vars[0],
        transformer_block.out_vars[1],
        transformer_block.out_vars[2],
    ]

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: v_A,
        VarPowerFlowReferenceType.v_B: v_B,
        VarPowerFlowReferenceType.v_C: v_C,
        VarPowerFlowReferenceType.i_A: transformer_block.out_vars[0],
        VarPowerFlowReferenceType.i_B: transformer_block.out_vars[1],
        VarPowerFlowReferenceType.i_C: transformer_block.out_vars[2],
        VarPowerFlowReferenceType.P: vsc_block.out_vars[2],
        VarPowerFlowReferenceType.Q: vsc_block.out_vars[3],
        VarPowerFlowReferenceType.phi_v: vsc_block.out_vars[9],
        VarPowerFlowReferenceType.Vpk: vsc_block.out_vars[10],
    }

    # The controller targets are owned by the VSC child. Publish the generator
    # sharing aliases there so recursive mapping does not require root copies.
    vsc_block.api_obj_mapping[ParamPowerFlowReferenceType.generator_share_p_ref] = (
        vsc_block.api_obj_mapping[ParamPowerFlowReferenceType.converter_control_target_1]
    )
    vsc_block.api_obj_mapping[ParamPowerFlowReferenceType.generator_share_q_ref] = (
        vsc_block.api_obj_mapping[ParamPowerFlowReferenceType.converter_control_target_2]
    )

    return templ


# =============================================================================
# Level 2 — PV + averaged DC-DC
# PV array + boost converter average + DC-link + VSC
# =============================================================================


def _build_level2_pv_boost_block(vf: VarFactory, name: str) -> Block:
    """
    Build the Level-2 PV array plus averaged boost-converter DC source block.

    This block adds an explicit averaged boost stage between the PV array and
    the imported VSC DC terminal. It remains an aggregated network EMT model,
    not a switching model. The PV array is represented by an irradiance and
    temperature dependent MPP voltage/current pair. The boost duty cycle follows
    a PI MPPT control law and determines the PV-side voltage through the average
    boost relation::

        v_pv = (1 - duty) * v_dc_bus

    The block still does not duplicate the VSC internal DC-link capacitor. The
    imported VSC block owns that state. This block supplies a controlled DC
    terminal voltage and exposes PV-side diagnostics such as ``v_pv``, ``duty``,
    ``p_src`` and ``p_curt``.

    :param vf: EMT symbolic variable factory.
    :param name: Symbolic model name.
    :return: Level-2 PV averaged boost block.
    """
    i_dc = vf.add_var(name=f"i_dc_pv_l2_in")
    v_dc_ctrl = vf.add_var(name=f"v_dc_ctrl_pv_l2_in")

    xi_mppt = vf.add_var(name=f"xi_mppt_l2")
    duty = vf.add_var(name=f"duty_l2")
    d_xi_mppt = vf.add_diff_var(name=f"d_xi_mppt_l2", base_var=xi_mppt)
    d_duty = vf.add_diff_var(name=f"d_duty_l2", base_var=duty)

    v_dc_bus = vf.add_var(name=f"v_dc_bus_pv_l2", reference=VarPowerFlowReferenceType.Vdc)
    v_mp = vf.add_var(name=f"v_mp_l2")
    i_mp = vf.add_var(name=f"i_mp_l2")
    p_avail = vf.add_var(name=f"p_avail_l2")
    v_pv = vf.add_var(name=f"v_pv_l2")
    p_src = vf.add_var(name=f"p_src_l2")
    p_to_vsc = vf.add_var(name=f"p_to_vsc_l2")
    i_pv = vf.add_var(name=f"i_pv_l2")
    duty_ref = vf.add_var(name=f"duty_ref_l2")
    p_curt = vf.add_var(name=f"p_curt_l2")

    p_rated = vf.add_var(name=f"p_rated_l2")
    irradiance = vf.add_var(name=f"irradiance_l2")
    irradiance_ref = vf.add_var(name=f"irradiance_ref_l2")
    t_cell = vf.add_var(name=f"t_cell_l2")
    t_ref = vf.add_var(name=f"t_ref_l2")
    v_mp_ref = vf.add_var(name=f"v_mp_ref_l2")
    i_mp_ref = vf.add_var(name=f"i_mp_ref_l2")
    temp_coeff_v = vf.add_var(name=f"temp_coeff_v_l2")
    temp_coeff_i = vf.add_var(name=f"temp_coeff_i_l2")
    v_dc_ref = vf.add_var(name=f"v_dc_ref_l2")
    r_dc = vf.add_var(name=f"r_dc_l2")
    d0 = vf.add_var(name=f"d0_l2")
    d_min = vf.add_var(name=f"d_min_l2")
    d_max = vf.add_var(name=f"d_max_l2")
    kp_mppt = vf.add_var(name=f"kp_mppt_l2")
    ki_mppt = vf.add_var(name=f"ki_mppt_l2")
    t_duty = vf.add_var(name=f"t_duty_l2")
    eta_boost = vf.add_var(name=f"eta_boost_l2")
    k_src = vf.add_var(name=f"k_src_l2")
    k_boost_power = vf.add_var(name=f"k_boost_power_l2")
    k_vdc_ctrl = vf.add_var(name=f"k_vdc_ctrl_l2")

    c0 = vf.add_const(0.0)
    c1 = vf.add_const(1.0)
    eps = vf.add_const(1e-10)

    irradiance_eff: Expr = sym.max(irradiance_ref, eps)
    v_mp_expr: Expr = sym.max(v_mp_ref * (c1 + temp_coeff_v * (t_cell - t_ref)), eps)
    i_mp_expr: Expr = sym.max(i_mp_ref * (irradiance / irradiance_eff) * (c1 + temp_coeff_i * (t_cell - t_ref)), c0)
    p_avail_expr: Expr = sym.hard_sat(v_mp_expr * i_mp_expr, c0, p_rated)

    v_pv_expr: Expr = sym.max((c1 - duty) * v_dc_bus, eps)
    mppt_error: Expr = v_mp - v_pv
    duty_ref_expr: Expr = sym.hard_sat(d0 + kp_mppt * mppt_error + ki_mppt * xi_mppt, d_min, d_max)
    p_src_raw: Expr = p_avail - k_src * (v_pv - v_mp) * (v_pv - v_mp)
    p_src_expr: Expr = sym.hard_sat(p_src_raw, c0, p_avail)
    p_to_vsc_expr: Expr = eta_boost * p_src
    r_dc_eff: Expr = sym.max(r_dc, eps)
    v_dc_src_ctrl_expr: Expr = v_dc_ref - k_vdc_ctrl * (v_dc_ctrl - v_dc_ref)
    p_to_vsc_init_disc: Expr = sym.max(v_dc_ref * v_dc_ref + vf.add_const(4.0) * r_dc_eff * p_to_vsc_expr, eps)
    i_pv_init: Expr = (v_dc_ref - sym.sqrt(p_to_vsc_init_disc)) / (vf.add_const(2.0) * r_dc_eff)
    v_dc_bus_init: Expr = v_dc_ref - r_dc_eff * i_pv_init

    return Block(
        state_eqs=[
            # MPPT PI integrator driven by the PV voltage error.
            mppt_error,
            # Averaged duty-cycle actuator.
            (duty_ref - duty) / (t_duty + eps),
        ],
        state_vars=[xi_mppt, duty],
        diff_vars=[d_xi_mppt, d_duty],
        algebraic_eqs=[
            v_mp - v_mp_expr,
            i_mp - i_mp_expr,
            p_avail - p_avail_expr,
            v_pv - v_pv_expr,
            duty_ref - duty_ref_expr,
            p_src - p_src_expr,
            # PV-side DC sign convention matches Level 1 and the imported VSC
            # terminal current convention during export: positive PV power
            # delivery to the converter is represented with ``i_pv < 0`` while
            # the imported VSC reports the shared terminal current with the
            # opposite sign. Therefore the common internal port satisfies
            # ``i_pv + i_dc = 0`` during export.
            i_pv + i_dc,
            # Keep ``p_to_vsc`` positive when PV power is delivered from the
            # source side into the converter interface.
            p_to_vsc + v_dc_bus * i_pv,
            # The boost output is represented as a controlled Thevenin-like DC
            # source around v_dc_ref. A power droop term drives the delivered
            # power toward the MPPT/boost target while the imported VSC block
            # keeps the explicit converter DC-link state.
            v_dc_bus - (v_dc_src_ctrl_expr - r_dc * i_pv - k_boost_power * (p_to_vsc - p_to_vsc_expr)),
            p_curt - (p_avail - p_src),
        ],
        algebraic_vars=[v_dc_bus, v_mp, i_mp, p_avail, v_pv, p_src, p_to_vsc, i_pv, duty_ref, p_curt],
        event_dict={
            p_rated: vf.add_const(1.0),
            irradiance: vf.add_const(1000.0),
            irradiance_ref: vf.add_const(1000.0),
            t_cell: vf.add_const(25.0),
            t_ref: vf.add_const(25.0),
            v_mp_ref: vf.add_const(0.80),
            i_mp_ref: vf.add_const(1.0),
            temp_coeff_v: vf.add_const(-0.002),
            temp_coeff_i: vf.add_const(0.0005),
            v_dc_ref: vf.add_const(1.0),
            r_dc: vf.add_const(0.02),
            d0: vf.add_const(0.0000001),#0.20),
            d_min: vf.add_const(0.0),
            d_max: vf.add_const(0.95),
            kp_mppt: vf.add_const(0.5),
            ki_mppt: vf.add_const(1.0),
            t_duty: vf.add_const(0.05),
            eta_boost: vf.add_const(0.98),
            k_src: vf.add_const(1.0),
            k_boost_power: vf.add_const(10.0),
            k_vdc_ctrl: vf.add_const(1.0),
        },
        init_eqs={
            xi_mppt: c0,
            duty: d0,
            v_mp: v_mp_expr,
            i_mp: i_mp_expr,
            p_avail: p_avail_expr,
            v_pv:  v_dc_ref, #(c1 - d0) * v_dc_ref,
            duty_ref: d0,
            p_src: p_avail_expr,
            p_to_vsc: p_to_vsc_expr,
            i_pv: i_pv_init,
            v_dc_bus: v_dc_bus_init,
            p_curt: c0,
        },
        diff_init_eqs={d_xi_mppt: c0, d_duty: c0},
        in_vars=[i_dc, v_dc_ctrl],
        out_vars=[v_dc_bus, p_avail, p_src, p_to_vsc, v_pv, duty, v_mp, i_mp, p_curt],
        name=f"{name}_pv_level2_boost",
    )


def get_pv_avm_boost_grid_following_emt_template(
    vf: VarFactory,
    name: str = "pv_avm_boost_grid_following_emt",
) -> EmtModelTemplate:
    """
    Build the Level-2 PV averaged DC-DC plus grid-following VSC EMT template.

    Structure
    ---------
    The assembled model is::

        PV array equivalent from irradiance and temperature
            -> averaged boost converter with MPPT duty-cycle dynamics
            -> internal DC terminal voltage
            -> imported VSC/DC-link block
            -> imported SRF-PLL
            -> imported outer P/Q or Vdc/Q loop
            -> imported inner dq0 current controller
            -> imported AC-side dq0/abc interface
            -> abc current injection into the EMT network

    Compared with Level 1
    ---------------------
    Level 1 only computes available PV power and applies an MPPT lag. Level 2
    adds explicit averaged boost-converter variables: PV MPP voltage/current,
    PV-side voltage, duty-cycle state, MPPT PI integrator and boost efficiency.

    Not included
    ------------
    * Switching-level DC-DC or PWM detail.
    * Semiconductor device models.
    * Cell-level diode equations.
    * Plant-level PPC beyond the imported converter control interface.

    :param vf: EMT symbolic variable factory.
    :param name: Symbolic model name.
    :return: Fully assembled Level-2 PV EMT template.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name
    templ.block.name = name

    v_A: Var = vf.add_var(name=f"v_A", reference=VarPowerFlowReferenceType.v_A)
    v_B: Var = vf.add_var(name=f"v_B", reference=VarPowerFlowReferenceType.v_B)
    v_C: Var = vf.add_var(name=f"v_C", reference=VarPowerFlowReferenceType.v_C)

    vsc_block, pll_block, outer_loop_block, inner_loop_block, transformer_block = _build_converter_blocks(vf=vf, name=name)
    pv_boost_block: Block = _build_level2_pv_boost_block(vf=vf, name=name)

    _connect_imported_converter_blocks(
        vf=vf,
        name=name,
        v_A=v_A,
        v_B=v_B,
        v_C=v_C,
        dc_voltage_source=pv_boost_block.out_vars[0],
        vsc_block=vsc_block,
        pll_block=pll_block,
        outer_loop_block=outer_loop_block,
        inner_loop_block=inner_loop_block,
        transformer_block=transformer_block,
    )
    vf.add_connections(pv_boost_block.in_vars[0:2], [vsc_block.out_vars[1], vsc_block.out_vars[0]])
    _tag_connected_pair(vf, vsc_block.out_vars[1], pv_boost_block.in_vars[0], f"{name}_i_dc_feedback")
    _tag_connected_pair(vf, vsc_block.out_vars[0], pv_boost_block.in_vars[1], f"{name}_v_dc_feedback")

    templ.block.children.extend([
        pv_boost_block,
        vsc_block,
        pll_block,
        inner_loop_block,
        outer_loop_block,
        transformer_block,
    ])
    templ.block.in_vars = [v_A, v_B, v_C]
    templ.block.out_vars = [
        transformer_block.out_vars[0],
        transformer_block.out_vars[1],
        transformer_block.out_vars[2],
    ]

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: v_A,
        VarPowerFlowReferenceType.v_B: v_B,
        VarPowerFlowReferenceType.v_C: v_C,
        VarPowerFlowReferenceType.i_A: transformer_block.out_vars[0],
        VarPowerFlowReferenceType.i_B: transformer_block.out_vars[1],
        VarPowerFlowReferenceType.i_C: transformer_block.out_vars[2],
        VarPowerFlowReferenceType.P: vsc_block.out_vars[2],
        VarPowerFlowReferenceType.Q: vsc_block.out_vars[3],
        VarPowerFlowReferenceType.phi_v: vsc_block.out_vars[9],
        VarPowerFlowReferenceType.Vpk: vsc_block.out_vars[10],
    }

    return templ


def get_pv_grid_following_emt_template(
    vf: VarFactory,
    level: PvEmtModelLevel | int,
    name: str,
) -> EmtModelTemplate:
    """
    Build one PV EMT template from the requested model-detail level.

    This helper keeps the Level-1 and Level-2 public constructors unchanged
    while giving scripts one typed selection point for level-aware examples.

    :param vf: EMT symbolic variable factory.
    :param level: Requested PV model-detail level.
    :param name: Symbolic model name.
    :return: Fully assembled PV EMT template for the requested level.
    :raises ValueError: If the requested level is not supported.
    """
    pv_level: PvEmtModelLevel = PvEmtModelLevel(level)

    if pv_level == PvEmtModelLevel.LEVEL_1:
        return get_pv_avm_grid_following_emt_template(vf=vf, name=name)
    if pv_level == PvEmtModelLevel.LEVEL_2:
        return get_pv_avm_boost_grid_following_emt_template(vf=vf, name=name)

    raise ValueError(f"Unsupported PV EMT model level: {level}")
