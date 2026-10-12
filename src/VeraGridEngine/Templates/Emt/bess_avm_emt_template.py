# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from VeraGridEngine.enumerations import DeviceType, VarPowerFlowReferenceType
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block, Expr
import VeraGridEngine.Utils.Symbolic.symbolic as sym

from VeraGridEngine.Templates.Emt.converter_emt_template import (
    _build_pseudo_emt_converter_vsc_block,
    _build_pseudo_emt_converter_pll_block,
    _build_pseudo_emt_converter_outer_loop_block,
    _build_pseudo_emt_converter_inner_loop_block,
    _build_pseudo_emt_converter_transformer_block,
)


def get_battery_avm_emt_template(vf: VarFactory, name: str) -> EmtModelTemplate:
    """
    Build the aggregated battery block used by the Level-1 BESS template.

    The block represents the storage side as a Thevenin battery equivalent
    connected to the DC terminal used by the existing pseudo-EMT VSC block. It
    intentionally does not include a DC-link capacitor because the imported VSC
    block already owns the internal DC-link state ``v_dc`` and its capacitance
    ``C_dc``. Duplicating that capacitor here would create two competing DC
    energy buffers.

    Electrical model
    ----------------
    The battery is represented by a smooth open-circuit voltage and a terminal
    resistance::

        v_oc  = v_min + (v_max - v_min) * soc_limited
        v_bus = v_oc - r_bat * i_bat

    where ``i_bat`` is taken as positive when the BESS discharges and delivers
    active power to the converter DC side. The DC terminal voltage ``v_bus`` is
    passed to the imported VSC block as its ``v_dc_bus`` input.

    Energy model
    ------------
    The state of charge is updated from the battery terminal power. Positive
    power discharges the battery, while negative power charges it. Separate
    charge and discharge efficiencies are used through a smooth power split.

    Scope
    -----
    This is a Level-1 network EMT approximation. It includes SoC, aggregated
    open-circuit voltage, internal resistance and efficiency. It does not include
    cell electrochemistry, balancing, thermal behaviour, degradation, a detailed
    BMS, or a bidirectional DC-DC converter. A future Level-2 model can replace
    this block by an averaged DC-DC stage while keeping the imported VSC/control
    blocks unchanged.

    :param vf: EMT symbolic variable factory.
    :param name: Symbolic model name.
    :return: Battery-side EMT template.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.BatteryDevice
    templ.name = name
    templ.block.name = name
    # ------------------------------------------------------------------
    # Inputs from the imported VSC block.
    # ------------------------------------------------------------------
    i_dc = vf.add_var(name=f"i_dc_bat_in")
    i_dc_conv_init = vf.add_var(name=f"i_dc_conv_bat_in")
    r_dc_init = vf.add_var(name=f"r_dc_bat_in")
    r_dc_term_init = vf.add_var(name=f"r_dc_term_bat_in")

    # ------------------------------------------------------------------
    # Battery state and derivative.
    # ------------------------------------------------------------------
    soc = vf.add_var(name=f"soc")
    d_soc = vf.add_diff_var(name=f"d_soc", base_var=soc)

    # ------------------------------------------------------------------
    # Algebraic battery variables.
    # ------------------------------------------------------------------
    v_dc_bus = vf.add_var(name=f"v_dc_bus_bat", reference=VarPowerFlowReferenceType.Vdc)
    v_oc = vf.add_var(name=f"v_oc_bat")
    i_bat = vf.add_var(name=f"i_bat")
    p_bat = vf.add_var(name=f"p_bat")
    p_dis = vf.add_var(name=f"p_dis_bat")
    p_ch = vf.add_var(name=f"p_ch_bat")

    # ------------------------------------------------------------------
    # Local battery parameters.
    # ------------------------------------------------------------------
    e_cap = vf.add_var(name=f"e_cap_bat")
    v_min = vf.add_var(name=f"v_min_bat")
    v_max = vf.add_var(name=f"v_max_bat")
    r_bat = vf.add_var(name=f"r_bat")
    eta_ch = vf.add_var(name=f"eta_ch_bat")
    eta_dis = vf.add_var(name=f"eta_dis_bat")
    soc_min = vf.add_var(name=f"soc_min_bat")
    soc_max = vf.add_var(name=f"soc_max_bat")
    soc0 = vf.add_var(name=f"soc0_bat")
    c0 = vf.add_const(0.0)
    c1 = vf.add_const(1.0)
    c_half = vf.add_const(0.5)
    eps = vf.add_const(1e-10)

    soc_limited: Expr = sym.hard_sat(soc, soc_min, soc_max)
    discharge_enabled: Expr = sym.heaviside(soc - soc_min)
    charge_enabled: Expr = sym.heaviside(soc_max - soc)
    p_abs: Expr = sym.sqrt(p_bat * p_bat + eps)
    p_dis_expr: Expr = c_half * (p_bat + p_abs)
    p_ch_expr: Expr = c_half * (-p_bat + p_abs)
    v_oc0: Expr = v_min + (v_max - v_min) * soc0
    # Initialize the battery variables from a closed-form solution of the
    # coupled battery/VSC DC-side steady-state equations. This avoids an
    # artificial current step at t = 0 while keeping the existing battery and
    # VSC block structure unchanged.
    i_dc0_init: Expr = (i_dc_conv_init + v_oc0 / (r_dc_init + eps)) / (c1 + (r_dc_term_init - r_bat) / (r_dc_init + eps) + eps)
    i_bat0: Expr = -i_dc0_init
    v_dc_bus0: Expr = v_oc0 - r_bat * i_bat0
    p_bat0: Expr = v_dc_bus0 * i_bat0
    p_abs0: Expr = sym.sqrt(p_bat0 * p_bat0 + eps)
    p_dis0: Expr = c_half * (p_bat0 + p_abs0)
    p_ch0: Expr = c_half * (-p_bat0 + p_abs0)

    templ.block = Block(
        state_eqs=[
            # Positive battery power discharges the battery; negative power
            # charges it. Efficiencies are applied on the energy side.
            ((-p_dis / (eta_dis + eps)) * discharge_enabled + (eta_ch * p_ch) * charge_enabled) / (e_cap + eps),
        ],
        state_vars=[soc],
        diff_vars=[d_soc],
        algebraic_eqs=[
            # Smooth SoC-dependent open-circuit voltage.
            v_oc - (v_min + (v_max - v_min) * soc_limited),
            # The imported VSC block exposes DC current as positive when the
            # converter absorbs energy from the DC source and negative when it
            # delivers DC energy into AC power. The battery model uses the
            # opposite physical convention: positive current means battery
            # discharge into the converter. The algebraic coupling therefore
            # flips the sign so both subsystems share one consistent generator
            # convention at the BESS level.
            i_bat + i_dc,
            # Resistive Thevenin terminal relation feeding the VSC DC bus.
            v_dc_bus - (v_oc - r_bat * i_bat),
            # Battery terminal power. With the current mapping above, positive
            # battery current means discharge and therefore positive battery
            # terminal power means export from the battery into the converter.
            p_bat - v_dc_bus * i_bat,
            # Smooth discharge and charge power components.
            p_dis - p_dis_expr,
            p_ch - p_ch_expr,
        ],
        algebraic_vars=[v_dc_bus, v_oc, i_bat, p_bat, p_dis, p_ch],
        event_dict={
            e_cap: vf.add_const(10.0),
            v_min: vf.add_const(0.80),
            v_max: vf.add_const(1.20),
            r_bat: vf.add_const(0.02),
            eta_ch: vf.add_const(0.96),
            eta_dis: vf.add_const(0.96),
            soc_min: vf.add_const(0.05),
            soc_max: vf.add_const(0.95),
            soc0: vf.add_const(0.50),
        },
        init_eqs={
            soc: soc0,
            v_oc: v_oc0,
            i_bat: i_bat0,
            v_dc_bus: v_dc_bus0,
            p_bat: p_bat0,
            p_dis: p_dis0,
            p_ch: p_ch0,
        },
        diff_init_eqs={d_soc: c0},
        in_vars=[i_dc, i_dc_conv_init, r_dc_init, r_dc_term_init],
        out_vars=[v_dc_bus, soc, v_oc, i_bat, p_bat, p_dis, p_ch],
        name=f"{name}_battery",
    )

    return templ


def _build_bess_outer_power_loop_block(vf: VarFactory, name: str) -> Block:
    """
    Build one BESS-specific outer loop that directly tracks active/reactive power.

    Unlike the generic pseudo-converter outer loop, the Level-1 BESS does not
    need to regulate an externally imposed DC-link voltage. The battery is the
    DC source, so the outer loop is simpler and more robust when it regulates
    the requested AC active and reactive powers directly.

    :param vf: EMT symbolic variable factory.
    :param name: Symbolic model name.
    :return: Outer-loop block.
    """
    v_d = vf.add_var(name=f"v_d_outer_in")
    v_q = vf.add_var(name=f"v_q_outer_in")
    v_0 = vf.add_var(name=f"v_0_outer_in")
    i_d = vf.add_var(name=f"i_d_outer_in")
    i_q = vf.add_var(name=f"i_q_outer_in")
    i_0 = vf.add_var(name=f"i_0_outer_in")
    P = vf.add_var(name=f"P_outer_in")
    Q = vf.add_var(name=f"Q_outer_in")
    sbase = vf.add_var(name=f"sbase_outer_in")
    P_ref = vf.add_var(name=f"P_ref_outer_in")
    Q_ref = vf.add_var(name=f"Q_ref_outer_in")
    Vpk = vf.add_var(name=f"Vpk_outer_in")
    P_loss0 = vf.add_var(name=f"P_loss0_outer_in")
    p_kp = vf.add_var(name=f"vdc_kp_outer_in")
    p_ki = vf.add_var(name=f"vdc_ki_outer_in")
    q_kp = vf.add_var(name=f"q_kp_outer_in")
    q_ki = vf.add_var(name=f"q_ki_outer_in")
    i_max = vf.add_var(name=f"i_max_outer_in")
    tau_meas = vf.add_var(name=f"tau_meas_outer_in")
    aw_gain = vf.add_var(name=f"aw_gain_outer_in")

    xi_vdc = vf.add_var(name=f"xi_vdc")
    xi_q = vf.add_var(name=f"xi_q")
    P_f = vf.add_var(name=f"P_f")
    Q_f = vf.add_var(name=f"Q_f")

    d_xi_vdc = vf.add_diff_var(name=f"d_xi_vdc", base_var=xi_vdc)
    d_xi_q = vf.add_diff_var(name=f"d_xi_q", base_var=xi_q)
    d_P_f = vf.add_diff_var(name=f"d_P_f", base_var=P_f)
    d_Q_f = vf.add_diff_var(name=f"d_Q_f", base_var=Q_f)

    v_mag = vf.add_var(name=f"v_mag")
    i_d_ff = vf.add_var(name=f"i_d_ff")
    i_q_ff = vf.add_var(name=f"i_q_ff")
    i_0_ref_u = vf.add_var(name=f"i_0_ref_u")
    i_d_ref_u = vf.add_var(name=f"i_d_ref_u")
    i_q_ref_u = vf.add_var(name=f"i_q_ref_u")
    i_0_ref = vf.add_var(name=f"i_0_ref")
    i_d_ref = vf.add_var(name=f"i_d_ref")
    i_q_ref = vf.add_var(name=f"i_q_ref")

    eps = vf.add_const(1e-10)
    c0 = vf.add_const(0.0)
    c23 = vf.add_const(2.0 / 3.0)
    c3 = vf.add_const(3.0)
    c32 = vf.add_const(1.5)

    P_ref_pu = P_ref / sbase
    Q_ref_pu = Q_ref / sbase
    P_ac_ff_pu = P_ref_pu + P_loss0 / sbase
    i_d0 = c23 * P_ac_ff_pu / (Vpk + eps)
    i_q0 = c23 * Q_ref_pu / (Vpk + eps)
    Q0 = c32 * Vpk * i_q0
    i_d_cap = sym.hard_sat(i_d_ref_u, -i_max, i_max)
    i_q_cap = sym.sqrt(sym.max(i_max * i_max - i_d_ref * i_d_ref, eps))
    i_0_cap = sym.sqrt(sym.max((i_max * i_max - i_d_ref * i_d_ref - i_q_ref * i_q_ref) / c3, eps / c3))

    return Block(
        state_eqs=[
            p_ki * ((P_ref_pu - P_f) + aw_gain * (i_d_ref - i_d_ref_u)),
            q_ki * ((Q_ref_pu - Q_f) + aw_gain * (i_q_ref - i_q_ref_u)),
            (P - P_f) / tau_meas,
            (Q - Q_f) / tau_meas,
        ],
        state_vars=[xi_vdc, xi_q, P_f, Q_f],
        diff_vars=[d_xi_vdc, d_xi_q, d_P_f, d_Q_f],
        algebraic_eqs=[
            v_mag - sym.sqrt(v_d * v_d + v_q * v_q + eps),
            i_d_ff - c23 * P_ac_ff_pu / (v_mag + eps),
            i_q_ff - c23 * Q_ref_pu / (v_mag + eps),
            i_0_ref_u,
            i_d_ref_u - (i_d_ff + p_kp * (P_ref_pu - P_f) + xi_vdc),
            i_d_ref - i_d_cap,
            i_q_ref_u - (i_q_ff + q_kp * (Q_ref_pu - Q_f) + xi_q),
            i_q_ref - sym.hard_sat(i_q_ref_u, -i_q_cap, i_q_cap),
            i_0_ref - sym.hard_sat(i_0_ref_u, -i_0_cap, i_0_cap),
        ],
        algebraic_vars=[v_mag, i_d_ff, i_q_ff, i_0_ref_u, i_d_ref_u, i_q_ref_u, i_0_ref, i_d_ref, i_q_ref],
        init_eqs={
            xi_vdc: i_d0 - (c23 * P_ac_ff_pu / (Vpk + eps)) - p_kp * (P_ref_pu - P),
            xi_q: i_q0 - (c23 * Q_ref_pu / (Vpk + eps)) - q_kp * (Q_ref_pu - Q0),
            P_f: P,
            Q_f: Q0,
            v_mag: Vpk,
            i_d_ff: c23 * P_ac_ff_pu / (Vpk + eps),
            i_q_ff: c23 * Q_ref_pu / (Vpk + eps),
            i_0_ref_u: c0,
            i_d_ref_u: i_d0,
            i_q_ref_u: i_q0,
            i_0_ref: c0,
            i_d_ref: i_d0,
            i_q_ref: i_q0,
        },
        diff_init_eqs={d_xi_vdc: c0, d_xi_q: c0, d_P_f: c0, d_Q_f: c0},
        in_vars=[
            v_d, v_q, v_0, i_d, i_q, i_0, P, Q,
            sbase, P_ref, Q_ref, Vpk, P_loss0,
            p_kp, p_ki, q_kp, q_ki, i_max, tau_meas, aw_gain,
        ],
        out_vars=[P_f, Q_f, i_0_ref, i_d_ref, i_q_ref],
        name=f"{name}_outer_loop_bess",
    )


def get_bess_avm_grid_following_emt_template(
    vf: VarFactory,
    name: str = "bess_avm_grid_following_emt",
) -> EmtModelTemplate:
    """
    Build a Level-1 averaged-value grid-following BESS EMT template.

    This template assembles an aggregated Battery Energy Storage System by
    reusing the existing pseudo-EMT converter blocks from
    ``converter_emt_template.py`` and adding only the BESS-specific storage
    block. The goal is to avoid duplicating PLL, VSC, outer-loop, inner-loop and
    dq0/abc interface logic that already exists in the standard VeraGrid
    converter template.

    Physical structure
    ------------------
    The assembled model is::

        battery Thevenin equivalent + SoC
            -> VSC DC terminal
            -> imported VSC/DC-link block
            -> imported SRF-PLL
            -> imported outer Vdc/Q or P/Q loop
            -> imported inner dq0 current controller
            -> imported AC-side L/R dq0 interface
            -> abc current injection into the EMT network

    The battery block provides the DC terminal voltage consumed by the imported
    VSC block. The imported VSC block still owns the internal DC-link capacitor
    and converter power/loss equations. This avoids having two DC-link
    capacitors in the same BESS model.

    Included behaviour
    ------------------
    * Aggregated SoC state.
    * SoC-dependent open-circuit voltage.
    * Battery internal resistance.
    * Charge/discharge efficiencies.
    * Existing averaged VSC power balance and DC-link dynamics.
    * Existing PLL, dq0 current control, current limiting and modulation limit.
    * Existing dq0-to-abc network current injection.

    Not included
    ------------
    * Switching-level PWM or semiconductor devices.
    * Cell-level electrochemistry, thermal behaviour or degradation.
    * Detailed BMS and cell balancing.
    * Bidirectional DC-DC converter stage.
    * Additional plant-level PPC logic beyond the imported converter controls.

    Sign convention
    ---------------
    Positive AC active power follows the existing pseudo-EMT converter
    convention. Positive battery power means the battery discharges into the
    converter DC side and SoC decreases.

    :param vf: EMT symbolic variable factory.
    :param name: Symbolic model name.
    :return: Fully assembled EMT BESS template.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.BatteryDevice # TODO: not sure if VSC or PV/BESS if exists
    templ.name = name
    templ.block.name = name

    # ------------------------------------------------------------------
    # Network-facing AC terminal variables. The BESS is modelled as an AC
    # device with an internal battery, so the DC bus voltage is produced by the
    # battery block rather than received from an external DC network.
    # ------------------------------------------------------------------
    v_A = vf.add_var(name=f"v_A", reference=VarPowerFlowReferenceType.v_A)
    v_B = vf.add_var(name=f"v_B", reference=VarPowerFlowReferenceType.v_B)
    v_C = vf.add_var(name=f"v_C", reference=VarPowerFlowReferenceType.v_C)

    # ------------------------------------------------------------------
    # Imported converter/control blocks.
    # ------------------------------------------------------------------
    vsc_block = _build_pseudo_emt_converter_vsc_block(vf=vf, name=name)
    pll_block = _build_pseudo_emt_converter_pll_block(vf=vf, name=name)
    outer_loop_block = _build_bess_outer_power_loop_block(vf=vf, name=name)
    inner_loop_block = _build_pseudo_emt_converter_inner_loop_block(vf=vf, name=name)
    transformer_block = _build_pseudo_emt_converter_transformer_block(vf=vf, name=name)

    # ------------------------------------------------------------------
    # New BESS-specific block.
    # ------------------------------------------------------------------
    battery_block = get_battery_avm_emt_template(vf=vf, name=name).block

    # ------------------------------------------------------------------
    # Wiring copied from the existing full pseudo-EMT converter assembly, with
    # only one change: the VSC DC terminal input is connected to the battery
    # block output instead of an external DC bus variable.
    # ------------------------------------------------------------------
    vf.add_connections(transformer_block.in_vars[0:3], [v_A, v_B, v_C])
    vf.add_connections([vsc_block.in_vars[6]], [battery_block.out_vars[0]])

    # The VSC DC terminal current is fed back to the battery block so the SoC
    # and Thevenin terminal voltage follow the converter operating point.
    vf.add_connections([battery_block.in_vars[0]], [vsc_block.out_vars[1]])
    # These additional VSC variables are only used to build a closed-form,
    # algebraically consistent battery/DC-link initialization point.
    vf.add_connections(
        battery_block.in_vars[1:4],
        [vsc_block.out_vars[33], vsc_block.out_vars[14], vsc_block.out_vars[15]],
    )

    # Transformer/interface provides dq0 voltages and currents to the VSC and
    # the control hierarchy.
    vf.add_connections(vsc_block.in_vars[0:3], transformer_block.out_vars[6:9])
    vf.add_connections(vsc_block.in_vars[3:6], transformer_block.out_vars[3:6])
    vf.add_connections([pll_block.in_vars[0]], [transformer_block.out_vars[7]])
    vf.add_connections(outer_loop_block.in_vars[0:3], transformer_block.out_vars[6:9])
    vf.add_connections(outer_loop_block.in_vars[3:6], transformer_block.out_vars[3:6])
    vf.add_connections(inner_loop_block.in_vars[0:3], transformer_block.out_vars[6:9])
    vf.add_connections(inner_loop_block.in_vars[3:6], transformer_block.out_vars[3:6])

    # VSC block exports physical quantities and parameters used by the controls.
    vf.add_connections(
        pll_block.in_vars[1:5],
        [vsc_block.out_vars[8], vsc_block.out_vars[16], vsc_block.out_vars[17], vsc_block.out_vars[9]],
    )
    vf.add_connections([outer_loop_block.in_vars[6], outer_loop_block.in_vars[7]], [vsc_block.out_vars[2], vsc_block.out_vars[3]])
    vf.add_connections(
        outer_loop_block.in_vars[8:20],
        [
            vsc_block.out_vars[4],
            vsc_block.out_vars[5],
            vsc_block.out_vars[6],
            vsc_block.out_vars[10],
            vsc_block.out_vars[26],
            vsc_block.out_vars[20],
            vsc_block.out_vars[21],
            vsc_block.out_vars[22],
            vsc_block.out_vars[23],
            vsc_block.out_vars[24],
            vsc_block.out_vars[29],
            vsc_block.out_vars[30],
        ],
    )
    vf.add_connections(
        [inner_loop_block.in_vars[6], inner_loop_block.in_vars[7], inner_loop_block.in_vars[8], inner_loop_block.in_vars[9]],
        [pll_block.out_vars[1], vsc_block.out_vars[8], vsc_block.out_vars[11], vsc_block.out_vars[12]],
    )
    vf.add_connections(inner_loop_block.in_vars[10:13], outer_loop_block.out_vars[2:5])
    vf.add_connections(
        inner_loop_block.in_vars[13:25],
        [
            vsc_block.out_vars[18],
            vsc_block.out_vars[19],
            vsc_block.out_vars[30],
            vsc_block.out_vars[25],
            vsc_block.out_vars[7],
            vsc_block.out_vars[0],
            vsc_block.out_vars[31],
            vsc_block.out_vars[4],
            vsc_block.out_vars[5],
            vsc_block.out_vars[6],
            vsc_block.out_vars[26],
            vsc_block.out_vars[10],
        ],
    )

    # Controller outputs drive the AC interface dynamics.
    vf.add_connections([transformer_block.in_vars[3], transformer_block.in_vars[4]], pll_block.out_vars)
    vf.add_connections(
        transformer_block.in_vars[5:8],
        [vsc_block.out_vars[8], vsc_block.out_vars[11], vsc_block.out_vars[12]],
    )
    vf.add_connections(transformer_block.in_vars[8:11], inner_loop_block.out_vars)
    vf.add_connections(
        transformer_block.in_vars[11:16],
        [vsc_block.out_vars[4], vsc_block.out_vars[5], vsc_block.out_vars[6], vsc_block.out_vars[26], vsc_block.out_vars[10]],
    )

    # ------------------------------------------------------------------
    # Composite editor-facing assembly.
    # ------------------------------------------------------------------
    templ.block.children.extend([
        battery_block,
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
        # vsc_block.out_vars[1],
        # battery_block.out_vars[1],
        # battery_block.out_vars[4],
    ]

    # ------------------------------------------------------------------
    # External mapping for EmtProblemDae.
    # ------------------------------------------------------------------
    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: v_A,
        VarPowerFlowReferenceType.v_B: v_B,
        VarPowerFlowReferenceType.v_C: v_C,
        # The BESS has an internal battery/DC source. Do not expose an external
        # DC-voltage network port here, otherwise the EMT assembler tries to
        # connect an additional DC-network equation to an internal algebraic
        # variable and the compiled DAE can become non-square.
        VarPowerFlowReferenceType.i_A: transformer_block.out_vars[0],
        VarPowerFlowReferenceType.i_B: transformer_block.out_vars[1],
        VarPowerFlowReferenceType.i_C: transformer_block.out_vars[2],
        # Idc is internal to the BESS battery/VSC coupling. The AC network only
        # sees the three-phase current injection.
        VarPowerFlowReferenceType.P: vsc_block.out_vars[2],
        VarPowerFlowReferenceType.Q: vsc_block.out_vars[3],
        VarPowerFlowReferenceType.phi_v: vsc_block.out_vars[9],
        VarPowerFlowReferenceType.Vpk: vsc_block.out_vars[10],
    }

    return templ
