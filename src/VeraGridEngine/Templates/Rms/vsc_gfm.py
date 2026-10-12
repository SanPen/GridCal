# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List
import math

from VeraGridEngine.enumerations import DeviceType, VarPowerFlowReferenceType
from VeraGridEngine.enumerations import ParamPowerFlowReferenceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import (Block, Var)
from VeraGridEngine.Utils.Symbolic.block_helpers import tf_to_block
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def build_gfm_converter_model(vfactory: VarFactory, inputs: List[Var],
                              multilinear: bool = False,
                              voltage_inputs: List[Var] | None = None,
                              power_inputs: List[Var] | None = None,
                              current_power_inputs: List[Var] | None = None,
                              reconstruct_filter_voltage: bool = False):
    """
    Build Grid Forming Converter model (Droop + voltage + current control)
    based on the provided conceptual equations.
    """
    if voltage_inputs is None:
        Vm = inputs[0]
        Va = inputs[1]
        Vm_c = Vm
        Va_c = Va
        Vm_f = None
        Va_f = None
        Vm_g = Vm
        Va_g = Va
    else:
        Vm_c = voltage_inputs[0]
        Va_c = voltage_inputs[1]
        if reconstruct_filter_voltage:
            Vm_f = None
            Va_f = None
            Vm_g = voltage_inputs[2]
            Va_g = voltage_inputs[3]
        else:
            Vm_f = voltage_inputs[2]
            Va_f = voltage_inputs[3]
            Vm_g = voltage_inputs[4]
            Va_g = voltage_inputs[5]
    Pt_vsc = inputs[2]
    Qt_vsc = inputs[3]

    algebraic_eqs = []
    algebraic_vars = []
    res_block = Block()

    # Filter elements (per-unitized on converter base)
    Rf = vfactory.add_var('Rf')  # Resistance filter
    Lf = vfactory.add_var('Lf')  # Inductance filter
    Cf = vfactory.add_var('Cf')  # Capacitance filter
    
    Rc = vfactory.add_var('Rc')  # Grid Filter
    Lc = vfactory.add_var('Lc')  # Grid Filter
    Rcap = vfactory.add_var('Rcap')  # Grid Filter
    
    # Droop gains and references
    Kdp = vfactory.add_var('Kdp')
    Kdq = vfactory.add_var('Kdq')
    omega_nom = vfactory.add_var('omega_nom')  # rad/s
    omega_ref = vfactory.add_var('omega_ref')  # p.u.
    V_ref = vfactory.add_var('V_ref')
    P_ref = vfactory.add_var('P_ref')
    Q_ref = vfactory.add_var('Q_ref')
    fn = vfactory.add_var('fn')

    # Inner loop PI gains
    Kp_icl = vfactory.add_var('Kp_icl')
    Ki_icl = vfactory.add_var('Ki_icl')

    # Filter time constants for power measurements
    tau_P = vfactory.add_var('tau_P')
    tau_Q = vfactory.add_var('tau_Q')

    # Limits
    V_max = vfactory.add_var('V_max')
    I_max = vfactory.add_var('I_max')

    #V ref variables
    vd_ref = vfactory.add_var('vd_ref')
    vq_ref = vfactory.add_var('vq_ref')
    event_dict = {
        Cf: vfactory.add_const(0.05),
        Rc: vfactory.add_const(0.01),
        Lc: vfactory.add_const(0.1),
        Rcap: vfactory.add_const(1e6),  # Large value to effectively disable damping
        Kdp: vfactory.add_const(0.05),
        Kdq: vfactory.add_const(0.05),
        omega_ref: vfactory.add_const(1.0),
        Kp_icl: vfactory.add_const(0.05),
        Ki_icl: vfactory.add_const(50.0),
        tau_P: vfactory.add_const(0.01),
        tau_Q: vfactory.add_const(0.01),
        V_max: vfactory.add_const(1.1),
        I_max: vfactory.add_const(1.2),
    }

    # Variables - P and Q represent terminal power (flowing into the grid)
    # They are linked to Pt_vsc and Qt_vsc via algebraic equations
    P = vfactory.add_var('P')
    Q = vfactory.add_var('Q')
    omega = vfactory.add_var('omega')
    theta = vfactory.add_var('theta')
    V = vfactory.add_var('V')

    vd_g = vfactory.add_var('vd_g')
    vq_g = vfactory.add_var('vq_g')
    vd_c = vfactory.add_var('vd_c')
    vq_c = vfactory.add_var('vq_c')

    def hidden_filter_voltage_from_terminals():
        """Recover the removed LCL midpoint from terminal voltages.

        The RMS dq convention used here represents a phasor as vq + j*vd.
        The reduced pi branch preserves terminal currents, but not this hidden
        midpoint, so reconstruct it from the original T-network admittances.
        """
        xf = Lf
        xc = Lc
        den_f = Rf ** 2 + xf ** 2 + vfactory.add_const(1e-12)
        den_c = Rc ** 2 + xc ** 2 + vfactory.add_const(1e-12)
        g_f = Rf / den_f
        b_f = -xf / den_f
        g_c = Rc / den_c
        b_c = -xc / den_c
        g_sh = vfactory.add_const(1.0) / Rcap
        b_sh = Cf

        g_sum = g_f + g_c + g_sh
        b_sum = b_f + b_c + b_sh
        den_sum = g_sum ** 2 + b_sum ** 2 + vfactory.add_const(1e-12)

        num_q = g_f * vq_c - b_f * vd_c + g_c * vq_g - b_c * vd_g
        num_d = g_f * vd_c + b_f * vq_c + g_c * vd_g + b_c * vq_g

        vq_mid = (num_q * g_sum + num_d * b_sum) / den_sum
        vd_mid = (num_d * g_sum - num_q * b_sum) / den_sum
        return vd_mid, vq_mid

    id_c = vfactory.add_var('id_c')
    iq_c = vfactory.add_var('iq_c')
    vd_f = vfactory.add_var('vd_f')
    vq_f = vfactory.add_var('vq_f')
    id_g = vfactory.add_var('id_g')
    iq_g = vfactory.add_var('iq_g')

    vd_c_ref = vfactory.add_var('vd_c_ref')
    vq_c_ref = vfactory.add_var('vq_c_ref')

    id_c_ref = vfactory.add_var('id_c_ref')
    iq_c_ref = vfactory.add_var('iq_c_ref')

    # Mapping physical node voltages to dq relative to internal angle theta.
    algebraic_eqs.append(vd_g - Vm_g * sym.sin(Va_g - theta))
    algebraic_eqs.append(vq_g - Vm_g * sym.cos(Va_g - theta))
    if voltage_inputs is not None:
        algebraic_eqs.append(vd_c - Vm_c * sym.sin(Va_c - theta))
        algebraic_eqs.append(vq_c - Vm_c * sym.cos(Va_c - theta))
        if reconstruct_filter_voltage:
            vd_mid, vq_mid = hidden_filter_voltage_from_terminals()
            algebraic_eqs.append(vd_f - vd_mid)
            algebraic_eqs.append(vq_f - vq_mid)
        else:
            algebraic_eqs.append(vd_f - Vm_f * sym.sin(Va_f - theta))
            algebraic_eqs.append(vq_f - Vm_f * sym.cos(Va_f - theta))

    # In the combined model the filter drops are internal equations. In the
    # separated model those drops are represented by actual network lines.
    if voltage_inputs is None:
        algebraic_eqs.append(vd_f - vd_g - (Rc*id_g - omega*Lc*iq_g))
        algebraic_eqs.append(vq_f - vq_g - (Rc*iq_g + omega*Lc*id_g))

        algebraic_eqs.append(vd_c - vd_f - (Rf*id_c - omega*Lf*iq_c))
        algebraic_eqs.append(vq_c - vq_f - (Rf*iq_c + omega*Lf*id_c))

    k = vfactory.add_const(1.5)  # Power calculation constant for dq frame
    den_g = vd_g ** 2 + vq_g ** 2 + vfactory.add_const(1e-12)
    den_c = vd_c ** 2 + vq_c ** 2 + vfactory.add_const(1e-12)

    def line_endpoint_powers(vd_from, vq_from, vd_to, vq_to, r, x):
        den = r ** 2 + x ** 2 + vfactory.add_const(1e-12)
        g = r / den
        b = -x / den
        vm_from2 = vd_from ** 2 + vq_from ** 2
        vm_to2 = vd_to ** 2 + vq_to ** 2
        dot = vq_from * vq_to + vd_from * vd_to
        sin_from_to = vd_from * vq_to - vq_from * vd_to

        p_from = g * vm_from2 - g * dot - b * sin_from_to
        q_from = -b * vm_from2 - g * sin_from_to + b * dot
        p_to = g * vm_to2 - g * dot + b * sin_from_to
        q_to = -b * vm_to2 + g * sin_from_to + b * dot
        return p_from, q_from, p_to, q_to

    def current_from_power(p, q, vd, vq, den):
        id_ = ((q / k) * vq + (p / k) * vd) / den
        iq_ = ((p / k) * vq - (q / k) * vd) / den
        return id_, iq_

    dt_vd_f = None
    dt_vq_f = None
    if current_power_inputs is None:
        if voltage_inputs is None:
            # Dynamic shunt-capacitor balance in the synchronous RMS frame.
            dt_vd_f = vfactory.add_diff_var('dt_vd_f', base_var=vd_f)
            dt_vq_f = vfactory.add_diff_var('dt_vq_f', base_var=vq_f)
            algebraic_eqs.append(id_c - id_g + Cf * omega * vq_f - vd_f / Rcap - Cf * dt_vd_f)
            algebraic_eqs.append(iq_c - iq_g - Cf * omega * vd_f - vq_f / Rcap - Cf * dt_vq_f)
        else:
            # Externally supplied filter voltages are not free capacitor states.
            algebraic_eqs.append(id_c - id_g + Cf * omega * vq_f - vd_f / Rcap)
            algebraic_eqs.append(iq_c - iq_g - Cf * omega * vd_f - vq_f / Rcap)
    else:
        if reconstruct_filter_voltage:
            P_c, Q_c, _, _ = line_endpoint_powers(vd_c, vq_c, vd_f, vq_f, Rf, Lf)
            _, _, P_t_grid, Q_t_grid = line_endpoint_powers(vd_f, vq_f, vd_g, vq_g, Rc, Lc)
            P_g = -P_t_grid
            Q_g = -Q_t_grid
        else:
            P_c = current_power_inputs[0]
            Q_c = current_power_inputs[1]
            P_g = current_power_inputs[2]
            Q_g = current_power_inputs[3]
        id_c_expr, iq_c_expr = current_from_power(P_c, Q_c, vd_c, vq_c, den_c)
        id_g_expr, iq_g_expr = current_from_power(P_g, Q_g, vd_g, vq_g, den_g)
        algebraic_eqs.append(id_c - id_c_expr)
        algebraic_eqs.append(iq_c - iq_c_expr)
        algebraic_eqs.append(id_g - id_g_expr)
        algebraic_eqs.append(iq_g - iq_g_expr)

    # Power measurement
    algebraic_eqs.append(P - k * (vq_g * iq_g + vd_g * id_g))
    algebraic_eqs.append(Q - k * (vq_g * id_g - vd_g * iq_g))

    if power_inputs is None:
        P_ctrl = P
        Q_ctrl = Q
    else:
        P_ctrl = power_inputs[0]
        Q_ctrl = power_inputs[1]

    # Droop control with Low-pass filters
    # Transfer function: 1/(tau*s + 1)
    # At steady state: output = input, derivative = 0
    block_P, P_lowpass = tf_to_block(vfactory, num=[vfactory.add_const(1)], den=[vfactory.add_const(1), tau_P], x=P_ctrl,
                                     name='P_loop')
    block_Q, Q_lowpass = tf_to_block(vfactory, num=[vfactory.add_const(1)], den=[vfactory.add_const(1), tau_Q], x=Q_ctrl,
                                     name='Q_loop')
    block_P.init_eqs = {P_lowpass: P_ctrl}
    block_Q.init_eqs = {Q_lowpass: Q_ctrl}
    res_block.add(block_P)
    res_block.add(block_Q)

    # omega = omega_ref - Kdp * (P_filt - P_ref)
    algebraic_eqs.append(omega - (omega_ref - Kdp * (P_lowpass - P_ref)))
    # V = V_ref - Kdq * (Q_filt - Q_ref)
    algebraic_eqs.append(V - (V_ref + Kdq * (-Q_lowpass + Q_ref)))

    # Internal angle integration
    # d(theta)/dt = 2*pi*fn * (omega - 1)
    dt_theta = vfactory.add_diff_var('dt_theta', base_var=theta)
    algebraic_eqs.append(dt_theta - 2 * math.pi * fn * (omega - 1))

    # Voltage control loop
    # PI controllers for voltage
    if voltage_inputs is None:
        vd_ctrl_input = vd_ref - vd_f
        vq_ctrl_input = vq_ref - vq_f
    elif reconstruct_filter_voltage:
        vd_ctrl_input = vd_ref - vd_f
        vq_ctrl_input = vq_ref + V - V_ref - vq_f
    else:
        vd_ctrl_input = -vd_f
        vq_ctrl_input = V - vq_f

    block_vd, id_hat = tf_to_block(vfactory, num=[Ki_icl, Kp_icl], den=[0, 1], x=vd_ctrl_input, name='vd_ctrl')
    block_vq, iq_hat = tf_to_block(vfactory, num=[Ki_icl, Kp_icl], den=[0, 1], x=vq_ctrl_input, name='vq_ctrl')
    res_block.add(block_vd)
    res_block.add(block_vq)

    # Current reference calculation (with feedforward and decoupling)
    i_d_ref_raw = id_hat + id_g - Cf * omega * vq_f + vd_f / Rcap
    i_q_ref_raw = iq_hat + iq_g + Cf * omega * vd_f + vq_f / Rcap

    # Current limitation with anti-windup (UPC-style back-calculation path):
    # positive feedback through LPF 1/(1+s*tau_aw), tau_aw = Kp_icl/Ki_icl.
    eps_aw = vfactory.add_const(1e-9)
    tau_aw = Kp_icl / (Ki_icl + eps_aw)
    aw_d_in = vfactory.add_var('aw_d_in')
    aw_q_in = vfactory.add_var('aw_q_in')
    block_aw_d, aw_d = tf_to_block(vfactory, num=[vfactory.add_const(1.0)], den=[vfactory.add_const(1.0), tau_aw],
                                   x=aw_d_in, name='aw_d')
    block_aw_q, aw_q = tf_to_block(vfactory, num=[vfactory.add_const(1.0)], den=[vfactory.add_const(1.0), tau_aw],
                                   x=aw_q_in, name='aw_q')
    res_block.add(block_aw_d)
    res_block.add(block_aw_q)

    i_d_ref_aw = vfactory.add_var('i_d_ref_aw')
    i_q_ref_aw = vfactory.add_var('i_q_ref_aw')
    algebraic_eqs.append(i_d_ref_aw - (i_d_ref_raw + aw_d))
    algebraic_eqs.append(i_q_ref_aw - (i_q_ref_raw + aw_q))

    # Saturation plant: q-axis first, then d-axis headroom.
    iq_for_id_lim = sym.max(iq_c, i_q_ref_aw)
    id_max = sym.sqrt(sym.max(I_max**2 - iq_for_id_lim**2, vfactory.add_const(1e-5)))
    i_d_ref_sat = sym.hard_sat(i_d_ref_aw, -id_max, id_max)
    i_q_ref_sat = sym.hard_sat(i_q_ref_aw, -I_max, I_max)

    i_d_ref_sat_var = vfactory.add_var('i_d_ref_sat')
    i_q_ref_sat_var = vfactory.add_var('i_q_ref_sat')
    algebraic_eqs.append(i_d_ref_sat_var - i_d_ref_sat)
    algebraic_eqs.append(i_q_ref_sat_var - i_q_ref_sat)
    algebraic_eqs.append(aw_d_in - (i_d_ref_sat_var - i_d_ref_aw))
    algebraic_eqs.append(aw_q_in - (i_q_ref_sat_var - i_q_ref_aw))

    algebraic_eqs.append(id_c_ref - i_d_ref_sat_var)
    algebraic_eqs.append(iq_c_ref - i_q_ref_sat_var)

    # Current loop PI controllers
    block_id, vd_hat = tf_to_block(vfactory, num=[Ki_icl, Kp_icl], den=[0, 1], x=id_c_ref - id_c, name='id_ctrl')
    block_iq, vq_hat = tf_to_block(vfactory, num=[Ki_icl, Kp_icl], den=[0, 1], x=iq_c_ref - iq_c, name='iq_ctrl')
    res_block.add(block_id)
    res_block.add(block_iq)

    # Converter voltage reference calculation
    algebraic_eqs.append(vd_c_ref - (vd_hat + vd_f - Lf * omega * iq_c))
    algebraic_eqs.append(vq_c_ref - (vq_hat + vq_f + Lf * omega * id_c))

    #Now we control the converter's voltage with an ideal voltage source.
    algebraic_eqs.append(vd_c - vd_c_ref)
    algebraic_eqs.append(vq_c - vq_c_ref)

    # Collect all variables
    algebraic_vars.extend(
         [P, Q, omega, theta, V, vd_g, vq_g, id_g, iq_g, id_c, iq_c, vd_f, vq_f, vd_c, vq_c, vd_c_ref, vq_c_ref, id_c_ref, iq_c_ref,
          i_d_ref_aw, i_q_ref_aw, i_d_ref_sat_var, i_q_ref_sat_var, aw_d_in, aw_q_in])

    if reconstruct_filter_voltage:
        vd_f_init, vq_f_init = hidden_filter_voltage_from_terminals()
    else:
        vd_f_init = Vm_f * sym.sin(Va_f - theta) if voltage_inputs is not None else vd_g + (Rc*id_g - omega*Lc*iq_g)
        vq_f_init = Vm_f * sym.cos(Va_f - theta) if voltage_inputs is not None else vq_g + (Rc*iq_g + omega*Lc*id_g)

    if current_power_inputs is None:
        p_init = -Pt_vsc
        q_init = -Qt_vsc
        id_g_init = ((q_init / k) * vq_g + (p_init / k) * vd_g) / den_g
        iq_g_init = ((p_init / k) * vq_g - (q_init / k) * vd_g) / den_g
        id_c_init = id_g - Cf * omega * vq_f + vd_f / Rcap
        iq_c_init = iq_g + Cf * omega * vd_f + vq_f / Rcap
    else:
        if reconstruct_filter_voltage:
            p_c_init, q_c_init, _, _ = line_endpoint_powers(vd_c, vq_c, vd_f_init, vq_f_init, Rf, Lf)
            _, _, p_t_grid_init, q_t_grid_init = line_endpoint_powers(vd_f_init, vq_f_init, vd_g, vq_g, Rc, Lc)
            p_init = -p_t_grid_init
            q_init = -q_t_grid_init
        else:
            p_init = current_power_inputs[2]
            q_init = current_power_inputs[3]
            p_c_init = current_power_inputs[0]
            q_c_init = current_power_inputs[1]
        id_g_init, iq_g_init = current_from_power(p_init, q_init, vd_g, vq_g, den_g)
        id_c_init, iq_c_init = current_from_power(p_c_init, q_c_init, vd_c, vq_c, den_c)

    diff_vars = [dt_theta]
    diff_init_eqs = {
        dt_theta: 2 * math.pi * fn * (omega - 1),
    }
    if dt_vd_f is not None and dt_vq_f is not None:
        diff_vars.extend([dt_vd_f, dt_vq_f])
        diff_init_eqs[dt_vd_f] = vfactory.add_const(0.0)
        diff_init_eqs[dt_vq_f] = vfactory.add_const(0.0)

    # Runtime references own their equilibrium expressions directly. The
    # explicit initializer resolves these expressions once and freezes the
    # resulting scalar values before runtime events are enabled.
    event_dict[P_ref] = P_ctrl
    event_dict[Q_ref] = Q_ctrl
    event_dict[vd_ref] = (
        vd_f
        if reconstruct_filter_voltage
        else (vfactory.add_const(0.0) if voltage_inputs is not None else vd_f)
    )
    event_dict[vq_ref] = (
        vq_f
        if reconstruct_filter_voltage
        else (V if voltage_inputs is not None else vq_f)
    )
    event_dict[V_ref] = (
        (vq_f if reconstruct_filter_voltage else Vm_f)
        if voltage_inputs is not None
        else Vm_c
    )

    core_block = Block(
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=algebraic_vars,
        diff_vars=diff_vars,
        event_dict=event_dict,
        parameters={omega_nom: vfactory.add_const(2 * math.pi * 50), fn: vfactory.add_const(50.0), Rf: vfactory.add_const(0.02), Lf: vfactory.add_const(0.15)},
        diff_init_eqs=diff_init_eqs,
        init_eqs={
            P: p_init,
            Q: q_init,
            theta: (Va_g if reconstruct_filter_voltage else Va_f) if voltage_inputs is not None else Va_c,
            omega: vfactory.add_const(1.0),
            V: V_ref if reconstruct_filter_voltage else (Vm_f if voltage_inputs is not None else Vm_c),
            vd_g: Vm_g * sym.sin(Va_g - theta),
            vq_g: Vm_g * sym.cos(Va_g - theta),
            id_g: id_g_init,
            iq_g: iq_g_init,
            vd_f: vd_f_init,
            vq_f: vq_f_init,

            # Capacitor currents (Rcap is large, so damping terms are negligible)
            id_c: id_c_init,
            iq_c: iq_c_init,
            
            # Current references match currents (PI input = 0)
            id_c_ref: id_c,
            iq_c_ref: iq_c,
            i_d_ref_aw: id_c,
            i_q_ref_aw: iq_c,
            i_d_ref_sat_var: id_c,
            i_q_ref_sat_var: iq_c,
            aw_d_in: vfactory.add_const(0.0),
            aw_q_in: vfactory.add_const(0.0),
            aw_d: vfactory.add_const(0.0),
            aw_q: vfactory.add_const(0.0),
            vd_c_ref: Vm_c * sym.sin(Va_c - theta) if voltage_inputs is not None else Rf * id_c - Lf * omega * iq_c + vd_f,
            vq_c_ref: Vm_c * sym.cos(Va_c - theta) if voltage_inputs is not None else Rf * iq_c + Lf * omega * id_c + vq_f,
            vq_c: Vm_c * sym.cos(Va_c - theta) if voltage_inputs is not None else vq_c_ref,
            vd_c: Vm_c * sym.sin(Va_c - theta) if voltage_inputs is not None else vd_c_ref,

            #control loop init
            vd_hat: (vd_c_ref) - (vd_f) + (Lf * omega * iq_c),
            vq_hat: (vq_c_ref) - (vq_f) - (Lf * omega * id_c),
            # Voltage PI controller outputs (feedforward currents)
            id_hat: id_c - id_g + Cf * omega * vq_f - vd_f / Rcap,
            iq_hat: iq_c - iq_g - Cf * omega * vd_f - vq_f / Rcap,
        },
        external_mapping={
            VarPowerFlowReferenceType.P: P,
            VarPowerFlowReferenceType.Q: Q,
        },
        api_obj_mapping={ParamPowerFlowReferenceType.omega_base: omega_nom, ParamPowerFlowReferenceType.freq: fn},
    )
    res_block.add(core_block)
    res_block.unify_blocks()

    return res_block, id_c, iq_c, P, Q, {
        "Rf": Rf,
        "Rc": Rc,
        "Rcap": Rcap,
        "id_g": id_g,
        "iq_g": iq_g,
        "vd_c": vd_c,
        "vq_c": vq_c,
        "vd_f": vd_f,
        "vq_f": vq_f,
        "L": Lf,
    }


def VscGfmLossBuild(vfactory: VarFactory, name: str = "Grid-forming VSC loss RMS template", current_power_inputs: List[Var] | None = None,
                    reconstruct_filter_voltage: bool = False) -> RmsModelTemplate:
    """
    VSC GFM model builder for explicit AC filter-network validations.

    This maps the VSC active powers through the converter loss equation,
    exposes controlled/filter/grid AC node voltages separately, and does not
    expose a DC-side reactive power mapping.
    """
    templ = RmsModelTemplate()
    templ.name = name
    templ.tpe = DeviceType.VscDevice

    inputs = [
        vfactory.add_var("Vm_c_"),
        vfactory.add_var("Va_c_"),
        vfactory.add_var("Vm_f_"),
        vfactory.add_var("Va_f_"),
        vfactory.add_var("Vm_g_"),
        vfactory.add_var("Va_g_"),
        vfactory.add_var("Vdc_"),
    ]
    Vm_c = inputs[0]
    Va_c = inputs[1]
    Vm_f = inputs[2]
    Va_f = inputs[3]
    Vm_g = inputs[4]
    Va_g = inputs[5]
    v_dc = inputs[6]

    # Power Flow related variables
    Pt_vsc = vfactory.add_var('Pt_vsc')
    Pf_vsc = vfactory.add_var('Pf_vsc')
    Qt_ref = vfactory.add_var('Qt_ref')

    # Optional loss parameters (following GFL pattern)
    a0 = vfactory.add_var('a0')
    a1 = vfactory.add_var('a1')
    a2 = vfactory.add_var('a2')

    event_dict = {
        Qt_ref: vfactory.add_const(0.0),
    }
    parameters = {a0: vfactory.add_const(0.0), a1: vfactory.add_const(0.0), a2: vfactory.add_const(0.1)}

    if reconstruct_filter_voltage:
        voltage_inputs = [Vm_c, Va_c, Vm_g, Va_g]
    else:
        voltage_inputs = [Vm_c, Va_c, Vm_f, Va_f, Vm_g, Va_g]

    gfm_block, i_d, i_q, P, Q, internals = build_gfm_converter_model(
        vfactory=vfactory,
        inputs=[Vm_c, Va_c, Pt_vsc, vfactory.add_const(0.0)],
        voltage_inputs=voltage_inputs,
        current_power_inputs=current_power_inputs,
        reconstruct_filter_voltage=reconstruct_filter_voltage,
    )

    Im = sym.sqrt(i_d ** 2 + i_q ** 2 + vfactory.add_const(1e-5))
    P_poly_loss = a0 + a1 * Im + a2 * Im ** 2

    vsc_wrapper = Block(
        algebraic_eqs=[
            Pf_vsc + Pt_vsc - P_poly_loss,
        ],
        algebraic_vars=[Pt_vsc, Pf_vsc],
        event_dict=event_dict,
        parameters=parameters,
        external_mapping={
            VarPowerFlowReferenceType.Vmt: Vm_c,
            VarPowerFlowReferenceType.Vat: Va_c,
            VarPowerFlowReferenceType.Vmf: Vm_g,
            VarPowerFlowReferenceType.Vaf: Va_g,
            VarPowerFlowReferenceType.Pt: Pt_vsc,
            VarPowerFlowReferenceType.Pf: Pf_vsc,
            VarPowerFlowReferenceType.Qt: Qt_ref,
            VarPowerFlowReferenceType.Vdc: v_dc,
        },
        in_vars=inputs,
        init_eqs={
            Pf_vsc: P_poly_loss - Pt_vsc,
        },
        out_vars=[Pt_vsc, Pf_vsc]
    )

    gfm_block.external_mapping.pop(VarPowerFlowReferenceType.P, None)
    gfm_block.external_mapping.pop(VarPowerFlowReferenceType.Q, None)
    vsc_wrapper.add(gfm_block)
    vsc_wrapper.name = 'gfm_block'
    vsc_wrapper.unify_blocks()  # Merge init_eqs from child blocks
    vsc_wrapper.external_mapping.pop(VarPowerFlowReferenceType.P, None)
    vsc_wrapper.external_mapping.pop(VarPowerFlowReferenceType.Q, None)
    vsc_wrapper.init_eqs[Pf_vsc] = P_poly_loss - Pt_vsc

    vsc_wrapper.api_obj_mapping.update({
        ParamPowerFlowReferenceType.R1: internals["Rf"],
        ParamPowerFlowReferenceType.X1: internals["L"],
        ParamPowerFlowReferenceType.alpha1: a0,
        ParamPowerFlowReferenceType.alpha2: a1,
        ParamPowerFlowReferenceType.alpha3: a2,
    })

    templ.block = vsc_wrapper
    templ.comment = 'VSC grid-forming loss RMS block'
    return templ


def VscGfmBuild(vfactory: VarFactory, name: str = "Grid-forming VSC RMS template") -> RmsModelTemplate:
    """
    VSC GFM (Grid Forming) model template builder.
    """
    templ = RmsModelTemplate()
    templ.name = name
    templ.tpe = DeviceType.VscDevice

    inputs = [vfactory.add_var("Vm_"), vfactory.add_var("Va_"), vfactory.add_var("Vdc_")]
    Vm = inputs[0]
    Va = inputs[1]
    v_dc = inputs[2]

    # Power Flow related variables
    Pt_vsc = vfactory.add_var('Pt_vsc')
    Qt_vsc = vfactory.add_var('Qt_vsc')
    Pf_vsc = vfactory.add_var('Pf_vsc')

    # Optional loss parameters (following GFL pattern)
    a0 = vfactory.add_var('a0')
    a1 = vfactory.add_var('a1')
    a2 = vfactory.add_var('a2')
    Qf = vfactory.add_var('Qf')

    event_dict = {
        Qf: vfactory.add_const(0.0),
    }
    parameters = {a0: vfactory.add_const(0.0), a1: vfactory.add_const(0.0), a2: vfactory.add_const(0.1)}

    gfm_block, i_d, i_q, P, Q, internals = build_gfm_converter_model(vfactory=vfactory, inputs=[Vm, Va, Pt_vsc, Qt_vsc])

    Im = sym.sqrt(i_d ** 2 + i_q ** 2 + vfactory.add_const(1e-5))
    P_conv = vfactory.add_const(1.5) * (internals["vq_c"] * i_q + internals["vd_c"] * i_d)
    P_poly_loss = a0 + a1 * Im + a2 * Im ** 2

    vsc_wrapper = Block(
        algebraic_eqs=[
            Pf_vsc + P_conv,
            Pt_vsc + P,
            Qt_vsc + Q,
        ],
        algebraic_vars=[Pt_vsc, Qt_vsc, Pf_vsc],
        event_dict=event_dict,
        parameters=parameters,
        external_mapping={
            VarPowerFlowReferenceType.Vmt: inputs[0],
            VarPowerFlowReferenceType.Vat: inputs[1],
            VarPowerFlowReferenceType.Pt: Pt_vsc,
            VarPowerFlowReferenceType.Qt: Qt_vsc,
            VarPowerFlowReferenceType.Pf: Pf_vsc,
            VarPowerFlowReferenceType.Qf: Qf,
            VarPowerFlowReferenceType.Vdc: v_dc,
        },
        in_vars=inputs,
        init_eqs={
            Pt_vsc: -P,
            Qt_vsc: -Q,
            Pf_vsc: -P_conv,
        },
        out_vars=[Pt_vsc, Qt_vsc, Pf_vsc]
    )

    gfm_block.external_mapping.pop(VarPowerFlowReferenceType.P, None)
    gfm_block.external_mapping.pop(VarPowerFlowReferenceType.Q, None)
    vsc_wrapper.add(gfm_block)
    vsc_wrapper.name = 'gfm_block'
    vsc_wrapper.unify_blocks()  # Merge init_eqs from child blocks
    vsc_wrapper.external_mapping.pop(VarPowerFlowReferenceType.P, None)
    vsc_wrapper.external_mapping.pop(VarPowerFlowReferenceType.Q, None)
    vsc_wrapper.init_eqs[Pf_vsc] = -P_conv

    vsc_wrapper.api_obj_mapping.update({
        ParamPowerFlowReferenceType.R1: internals["Rf"],
        ParamPowerFlowReferenceType.X1: internals["L"],
        ParamPowerFlowReferenceType.alpha1: a0,
        ParamPowerFlowReferenceType.alpha2: a1,
        ParamPowerFlowReferenceType.alpha3: a2,
    })

    templ.block = vsc_wrapper
    templ.comment = 'VSC grid-forming RMS model'
    return templ
