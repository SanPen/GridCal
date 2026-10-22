# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List
import numpy as np
from VeraGridEngine.enumerations import ParamPowerFlowReferenceType
import math

from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import (Block, Var, VarPowerFlowReferenceType)
from VeraGridEngine.Utils.Symbolic.block_helpers import tf_to_block
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.enumerations import ConverterControlType


def inverse_park_transform_block(vfactory: VarFactory, v_dq: list[Var], theta: Var, aux_vars = None, multilinear: bool = False, name:str =''):
    """
    Create a symbolic inverse Park transform (dq → abc) block for voltages.

    v_dq = [v_d_c, v_q_c]
    theta : grid angle (from PLL)
    multilinear : if True, use u_cos/u_sin auxiliary variables (for multilinearization)
    """

    v_d_c, v_q_c = v_dq

    # abc variables
    va_c = Var(name[0]+'a_'+name[-1])
    vb_c = Var(name[0]+'b_'+name[-1])
    vc_c = Var(name[0]+'c_'+name[-1])

    sqrt3 = vfactory.add_const(np.sqrt(3))
    reformulated_vars = []
    if not multilinear:
        # Non-multilinear form (explicit cos/sin)
        algebraic_eqs = [
            va_c - (v_d_c * sym.cos(theta) + v_q_c * sym.sin(theta)),

            vb_c - ((-vfactory.add_const(0.5) * v_d_c - (sqrt3 / vfactory.add_const(2)) * v_q_c) * sym.cos(theta)
                    + ((sqrt3 / vfactory.add_const(2)) * v_d_c - vfactory.add_const(0.5) * v_q_c) * sym.sin(theta)),

            vc_c - ((-vfactory.add_const(0.5) * v_d_c + (sqrt3 / vfactory.add_const(2)) * v_q_c) * sym.cos(theta)
                    + ((-sqrt3 / vfactory.add_const(2)) * v_d_c - vfactory.add_const(0.5) * v_q_c) * sym.sin(theta)),
        ]
        algebraic_vars = [va_c, vb_c, vc_c]
        trig_block = Block()
        aux_vars = None

    inv_park_block = Block(
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=algebraic_vars,
        reformulated_vars=reformulated_vars,
        init_eqs={
            va_c: v_d_c * sym.cos(theta) + v_q_c * sym.sin(theta),
            vb_c: ((-vfactory.add_const(0.5) * v_d_c - (sqrt3 / vfactory.add_const(2)) * v_q_c) * sym.cos(theta)
                   + ((sqrt3 / vfactory.add_const(2)) * v_d_c - vfactory.add_const(0.5) * v_q_c) * sym.sin(theta)),
            vc_c: ((-vfactory.add_const(0.5) * v_d_c + (sqrt3 / vfactory.add_const(2)) * v_q_c) * sym.cos(theta)
                   + ((-sqrt3 / vfactory.add_const(2)) * v_d_c - vfactory.add_const(0.5) * v_q_c) * sym.sin(theta)),
        },
    )
    inv_park_block.add(trig_block)

    return inv_park_block, (va_c, vb_c, vc_c), aux_vars

def park_transform_block(vfactory: VarFactory, v_abc: list[Var], theta: Var, multilinear:bool = False, aux_vars = None, name:str = ''):
    """
    Create a symbolic Park transform (abc → dq) block for voltages and currents.

    i_abc = [i_a, i_b, i_c]
    v_abc = [v_a, v_b, v_c]
    theta : grid angle (from PLL)
    """

    v_a, v_b, v_c = v_abc

    # dq variables
    x_d = Var(name + '_d')
    x_q = Var(name + '_q')

    if not multilinear:
        x_d_expr = vfactory.add_const(1/3) * (
            (vfactory.add_const(2) * sym.cos(theta) * v_a)
            + (-sym.cos(theta) - vfactory.add_const(np.sqrt(3)) * sym.sin(theta)) * v_b
            + (-sym.cos(theta) + vfactory.add_const(np.sqrt(3)) * sym.sin(theta)) * v_c
        )
        x_q_expr = vfactory.add_const(1/3) * (
            (vfactory.add_const(2) * sym.sin(theta) * v_a)
            + (-sym.sin(theta) + vfactory.add_const(np.sqrt(3)) * sym.cos(theta)) * v_b
            + (-sym.sin(theta) - vfactory.add_const(np.sqrt(3)) * sym.cos(theta)) * v_c
        )
        algebraic_eqs = [
            # dq voltages
            x_d - x_d_expr,

            x_q - x_q_expr,
        ]
        algebraic_vars = [x_d, x_q]
        trig_block = Block()
        aux_vars = None


    park_block = Block(
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=algebraic_vars,
        init_eqs={x_d: x_d_expr, x_q: x_q_expr},
    )
    park_block.add(trig_block)

    return park_block, (x_d, x_q), aux_vars

def pll_transform(vfactory: VarFactory, v_abc, multilinear:bool = False, name:str = ''):
    """
    EMT PLL using instantaneous three-phase voltages.
    """
    theta = Var('theta')
    omega = Var('omega')
    omega_base = vfactory.add_var('omega_base')
    Kp_pll = vfactory.add_var('Kp_pll')      # proportional gain
    Ki_pll = vfactory.add_var('Ki_pll')      # integral gain

    park_block, v_dq, aux_vars = park_transform_block(vfactory, v_abc, theta, multilinear=multilinear, name = name)
    v_d_raw, v_q = v_dq
    v_d = vfactory.add_const(0.0) - v_d_raw
    res_block = Block()
    pll_error = vfactory.add_var('u_PLL_pi')
    xi_pll = vfactory.add_var('xi_PLL')
    one = vfactory.add_const(1.0)
    d_theta = vfactory.add_diff_var(name='dt_1_theta', base_var=theta)
    d_xi_pll = vfactory.add_diff_var(name='dt_1_xi_PLL', base_var=xi_pll)
    integrator = Block(
        algebraic_eqs=[
            pll_error + v_d,
            omega - (one + Kp_pll * pll_error + Ki_pll * xi_pll),
        ],
        algebraic_vars=[pll_error, omega],
        state_eqs=[omega_base * omega, pll_error],
        state_vars=[theta, xi_pll],
        diff_vars=[d_theta, d_xi_pll],
        init_eqs={
            pll_error: vfactory.add_const(0.0) - v_d,
            xi_pll: vfactory.add_const(0.0),
            omega: one,
        },
        diff_init_eqs={d_theta: omega_base * omega, d_xi_pll: pll_error},
    )

    res_block.add(Block(event_dict={
        Kp_pll: vfactory.add_const(0.03),
        Ki_pll: vfactory.add_const(0.2),
    }, parameters={omega_base: vfactory.add_const(2.0 * math.pi * 50.0)},
        api_obj_mapping={ParamPowerFlowReferenceType.omega_base: omega_base}))
    res_block.add(integrator)
    res_block.add(park_block)
    return res_block, v_dq, omega, theta, aux_vars


def build_gfl_converter_model_emt(vfactory: VarFactory, inputs, 
                                  control1: ConverterControlType = ConverterControlType.Pac, 
                                  control2: ConverterControlType = ConverterControlType.Qac,
                                  multilinear:bool = False,
                                  frozen_voltage_source: bool = False):
    """
    Build power control loop model for Grid Following Converter for EMT simulation.
    Supports multiple control modes via ConverterControlType.

    :param vfactory: Variable factory used to construct the symbolic model.
    :param inputs: Converter voltages, currents, references, and initial power values.
    :param control1: First control mode, typically related to active power or DC voltage.
    :param control2: Second control mode, typically related to reactive power or AC voltage.
    :param multilinear: Whether to use multilinearized Park transforms.
    :param frozen_voltage_source: Whether to keep the converter voltage source fixed.
    :return: Converter block together with its active and reactive power measurements.
    """
    vc_a   = inputs[0]
    vc_b   = inputs[1]
    vc_c   = inputs[2]
    vg_a   = inputs[3]
    vg_b   = inputs[4]
    vg_c   = inputs[5]
    i_a_line = inputs[6]
    i_b_line = inputs[7]
    i_c_line = inputs[8]
    v_dc   = inputs[9]
    Pt_vsc = inputs[10]  # Power flow initial values
    Qt_vsc = inputs[11]
    Vpk_ref = inputs[12]
    phi_v_ref = inputs[13]

    algebraic_eqs = []
    algebraic_vars = []
    gfl_block = Block()
    control_blocks = []
    
    # ==============================
    # Inputs and variables
    # ==============================

    vc_abc = [vc_a, vc_b, vc_c]
    vg_abc = [vg_a, vg_b, vg_c]
    i_abc = [i_a_line, i_b_line, i_c_line]

    pll_block, v_dq, omega, theta, aux_vars = pll_transform(vfactory, vg_abc, multilinear=multilinear, name = 'vg')
    v_d_g_raw = v_dq[0]
    v_d_g = vfactory.add_const(0.0) - v_d_g_raw
    v_q_g_raw = v_dq[1]
    v_q_g = vfactory.add_const(0.0) - v_q_g_raw
    i_park_block, i_dq, _ = park_transform_block(vfactory, i_abc, theta, multilinear=multilinear, name='i_line')
    i_d_line_raw = i_dq[0]
    i_d_line = vfactory.add_const(0.0) - i_d_line_raw
    i_q_line_raw = i_dq[1]
    i_q_line = vfactory.add_const(0.0) - i_q_line_raw
    vc_park_block, vc_dq, _ = park_transform_block(vfactory, vc_abc, theta, multilinear=multilinear, name='vc')
    vc_d_raw = vc_dq[0]
    vc_d = vfactory.add_const(0.0) - vc_d_raw
    vc_q_raw = vc_dq[1]
    vc_q = vfactory.add_const(0.0) - vc_q_raw

    # Parameters
    Kp_icl = vfactory.add_var('Kp_icl')     # proportional gain for inner current loop
    Ki_icl = vfactory.add_var('Ki_icl')     # integral gain for inner current loop
    Kp_pol = vfactory.add_var('Kp_pol')     # proportional gain for outer power loop
    Ki_pol = vfactory.add_var('Ki_pol')     # integral gain for outer power loop
    Kp_vac = vfactory.add_var('Kp_vac')     # proportional gain for AC voltage control
    Ki_vac = vfactory.add_var('Ki_vac')     # integral gain for AC voltage control
    L = vfactory.add_var('L') 

    # Current measurements come directly from the external line current inputs.
    i_d = i_d_line
    i_q = i_q_line
    i_d_ref = vfactory.add_var('i_d_ref')
    i_q_ref = vfactory.add_var('i_q_ref')
    
    # POWER LOOP 
    P = vfactory.add_var('P')
    Q = vfactory.add_var('Q') 
    P_ref = vfactory.add_var('P_ref') 
    Q_ref = vfactory.add_var('Q_ref') 
    
    # Voltage references for control modes
    Vm_ac_ref = vfactory.add_var('Vm_ac_ref')
    
    v_d_c = vfactory.add_var('v_d_c')
    v_q_c = vfactory.add_var('v_q_c')
    v_d_c_ref = vfactory.add_var('v_d_c_ref')
    v_q_c_ref = vfactory.add_var('v_q_c_ref')

    event_dict = {
        Kp_icl: vfactory.add_const(0.05),
        Ki_icl: vfactory.add_const(1.0),
        Kp_pol: vfactory.add_const(0.05),
        Ki_pol: vfactory.add_const(1.0),
        Kp_vac: vfactory.add_const(0.1),
        Ki_vac: vfactory.add_const(2.0),
        L: vfactory.add_const(0.1),
        P_ref: vfactory.add_const(0.0),
        Q_ref: vfactory.add_const(0.0),
        Vm_ac_ref: vfactory.add_const(1.0),
    }
    if frozen_voltage_source:
        event_dict[v_d_c_ref] = vfactory.add_const(0.0)
        event_dict[v_q_c_ref] = vfactory.add_const(1.0)

    # P and Q at the grid-side point of common coupling.
    algebraic_eqs.append(P - vfactory.add_const(1/2)*(v_q_g*i_q + v_d_g*i_d))
    algebraic_eqs.append(Q - vfactory.add_const(1/2)*(v_q_g*i_d - v_d_g*i_q))
    algebraic_vars.append(P)
    algebraic_vars.append(Q)

    # ==============================
    # CONTROL 1: Active Power Axis (i_q_ref)
    # ==============================
    # Control1 maps to i_q_ref (q-axis current controls active power)
    
    if control1 == ConverterControlType.Pac:
        # Active power control at AC side
        control_block_1, _ = tf_to_block(vfactory,
            num=[Ki_pol, Kp_pol],
            den=[0, 1],
            x= P_ref - P,
            y = i_q_ref,
            name='Pac_ctrl'
        )
        control_blocks.append(control_block_1)
        
    elif control1 == ConverterControlType.Pdc:
        # Active power control at DC side (Pdc ~ Pac in steady state)
        # For simplicity, we control Pac which is approximately Pdc
        control_block_1, _ = tf_to_block(vfactory,
            num=[Ki_pol, Kp_pol],
            den=[0, 1],
            x= -(P_ref - P),  # P_ref represents desired Pdc
            y = i_q_ref,
            name='Pdc_ctrl'
        )
        control_blocks.append(control_block_1)

    else:
        raise ValueError(f"Control1 type {control1} not supported for GFL converter. "
                        f"Supported: Pac, Pdc")

    # ==============================
    # CONTROL 2: Reactive Power Axis (i_d_ref)
    # ==============================
    # Control2 maps to i_d_ref (d-axis current controls reactive power)
    
    if control2 == ConverterControlType.Qac or True:
        # Reactive power control
        control_block_2, _ = tf_to_block(vfactory,
            num=[Ki_pol, Kp_pol],
            den=[0, 1],
            x= Q_ref - Q,
            y = i_d_ref,
            name='Qac_ctrl'
        )
        control_blocks.append(control_block_2)
        

    # Physical Current Limits, TODO add AntiWindup
    I_max = vfactory.add_const(1.2)
    operation = 'normal'
    if operation == 'normal':
        id_max = sym.sqrt(sym.max(I_max**2 - sym.max(i_q, i_q_ref)**2, vfactory.add_const(1e-5)))     
        i_d_ref_sat = sym.hard_sat(i_d_ref, -id_max, id_max)
        i_q_ref_sat = sym.hard_sat(i_q_ref, -I_max, I_max)

    # Voltage Control Loop (Inner Current Loop)
    control_block_iq , vq_hat = tf_to_block(vfactory,
        num=[Ki_icl, Kp_icl],
        den=[0, 1],
        x= i_q - i_q_ref_sat,
        name='vq_hat'
    )
    control_block_id , vd_hat = tf_to_block(vfactory,
        num=[Ki_icl, Kp_icl],
        den=[0, 1],
        x= i_d - i_d_ref_sat,
        name='vd_hat'
    )

    if frozen_voltage_source:
        algebraic_eqs.append(v_d_c - v_d_c_ref)
        algebraic_eqs.append(v_q_c - v_q_c_ref)
    else:
        algebraic_eqs.append(v_d_c - (vd_hat + v_d_g - L*(omega)*i_q))
        algebraic_eqs.append(v_q_c - (vq_hat + v_q_g + L*(omega)*i_d))
    algebraic_eqs.append(vc_d - v_d_c)
    algebraic_eqs.append(vc_q - v_q_c)
    algebraic_eqs.append(vc_a + vc_b + vc_c)
    algebraic_vars.extend([v_d_c, v_q_c])

    sqrt3 = vfactory.add_const(np.sqrt(3.0))
    one_third = vfactory.add_const(1.0 / 3.0)
    two = vfactory.add_const(2.0)
    vc_d_raw_init = one_third * (
        two * sym.cos(theta) * vc_a
        + (-sym.cos(theta) - sqrt3 * sym.sin(theta)) * vc_b
        + (-sym.cos(theta) + sqrt3 * sym.sin(theta)) * vc_c
    )
    vc_d_init = vfactory.add_const(0.0) - vc_d_raw_init
    vc_q_raw_init = one_third * (
        two * sym.sin(theta) * vc_a
        + (-sym.sin(theta) + sqrt3 * sym.cos(theta)) * vc_b
        + (-sym.sin(theta) - sqrt3 * sym.cos(theta)) * vc_c
    )
    vc_q_init = vfactory.add_const(0.0) - vc_q_raw_init

    # Build initialization equations based on control modes. P and Q are seeded
    # from power-flow results via external mapping; making them depend on the
    # currents here creates a P <-> i_q and Q <-> i_d explicit-init cycle.
    init_eqs = {
        theta: phi_v_ref - vfactory.add_const(np.pi),
        omega: vfactory.add_const(1),
        v_d_g_raw: vfactory.add_const(0),
        v_q_g_raw: vfactory.add_const(0.0) - Vpk_ref,
        i_q_line_raw: vfactory.add_const(0.0) - (vfactory.add_const(2.0) * P / v_q_g),
        i_d_line_raw: vfactory.add_const(0.0) - (vfactory.add_const(2.0) * Q / v_q_g),
        i_q_ref: vfactory.add_const(2.0) * P / v_q_g,
        i_d_ref: i_d,
        v_d_c: vc_d_init,
        v_q_c: vc_q_init,
        vc_d_raw: vc_d_raw_init,
        vc_q_raw: vc_q_raw_init,
        vd_hat: v_d_c - (v_d_g - L*(omega)*i_q),
        vq_hat: v_q_c - (v_q_g + L*(omega)*i_d),
    }
    
    # Each selected control reference owns its power-flow-derived event
    # initialization expression.
    if control1 in [ConverterControlType.Pac, ConverterControlType.Pdc]:
        event_dict[P_ref] = P

    if control2 == ConverterControlType.Qac:
        event_dict[Q_ref] = Q
    elif control2 == ConverterControlType.Vm_ac:
        event_dict[Vm_ac_ref] = v_q_g
        # For AC voltage control, initialize i_d_ref based on initial reactive power
        init_eqs[i_d_ref] = vfactory.add_const(2.0) * Q / v_q_g

    gfl_block_aux = Block(
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=algebraic_vars,
        event_dict= event_dict,
        init_eqs=init_eqs,
        external_mapping={
            VarPowerFlowReferenceType.P:P,
            VarPowerFlowReferenceType.Q:Q,
        }
    )
    gfl_block.add(gfl_block_aux)

    # Add all control blocks
    for ctrl_block in control_blocks:
        gfl_block.add(ctrl_block)
    gfl_block.add(control_block_id)
    gfl_block.add(control_block_iq)

    gfl_block.add(pll_block)
    gfl_block.add(i_park_block)
    gfl_block.add(vc_park_block)
    gfl_block.unify_blocks()

    return gfl_block, P, Q

def VscGflEmtBuild(vfactory: VarFactory, name: str = "",
                   control1: ConverterControlType = ConverterControlType.Pac,
                   control2: ConverterControlType = ConverterControlType.Qac,
                   frozen_voltage_source: bool = False) -> EmtModelTemplate:
    """
    VSC GFL (Grid Following) EMT model
    with from side the DC bus and to side the AC bus
    
    Args:
        name: Model name
        control1: First control mode (Pac or Pdc)
        control2: Second control mode (Qac or Vm_ac)
    
    Supported control combinations:
        - Pac + Qac: Active and reactive power control
        - Pac + Vm_ac: Active power and AC voltage control
        - Pdc + Qac: DC power and reactive power control
        - Pdc + Vm_ac: DC power and AC voltage control
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.VscDevice
    # Inputs: converter-side voltage, grid-side voltage, measured line current, and DC voltage.
    inputs = [
        vfactory.add_var("vc_A", reference=VarPowerFlowReferenceType.v_A),
        vfactory.add_var("vc_B", reference=VarPowerFlowReferenceType.v_B),
        vfactory.add_var("vc_C", reference=VarPowerFlowReferenceType.v_C),
        vfactory.add_var("vg_A"),
        vfactory.add_var("vg_B"),
        vfactory.add_var("vg_C"),
        vfactory.add_var("i_line_A"),
        vfactory.add_var("i_line_B"),
        vfactory.add_var("i_line_C"),
        vfactory.add_var("Vdc_", reference=VarPowerFlowReferenceType.Vdc),
    ]

    # Vars:
    Pt_vsc = vfactory.add_var('Pt_vsc')
    Qt_vsc = vfactory.add_var('Qt_vsc')
    Vpk_ref = vfactory.add_var('Vpk_ref')
    phi_v_ref = vfactory.add_var('phi_v_ref')
    i_a_t = vfactory.add_var('i_a_f')
    i_b_t = vfactory.add_var('i_b_f')
    i_c_t = vfactory.add_var('i_c_f')
    i_dc = vfactory.add_var('i_dc')
    P_conv = vfactory.add_var('P_conv')
    v_dc_cap = vfactory.add_var('Vdc_cap')
    d_v_dc_cap = vfactory.add_diff_var(name='dt_1_Vdc_cap', base_var=v_dc_cap)

    # Parameters:
    bt = vfactory.add_var('bt')
    gt = vfactory.add_var('gt')
    Qf = vfactory.add_var('Qf')
    a0 = vfactory.add_var('a0')
    a1 = vfactory.add_var('a1')
    a2 = vfactory.add_var('a2')
    Cdc = vfactory.add_var('Cdc')
    
    # Build the converter model with specified control modes
    gfl_block, P, Q = build_gfl_converter_model_emt(
        vfactory=vfactory,
        inputs=[*inputs, Pt_vsc, Qt_vsc, Vpk_ref, phi_v_ref],
        control1=control1,
        control2=control2,
        frozen_voltage_source=frozen_voltage_source
    )

    event_dict = {
        Qf: vfactory.add_const(0.0),
        bt: vfactory.add_const(0.0),
        gt: vfactory.add_const(0.1),
        a0: vfactory.add_const(0.0),
        a1: vfactory.add_const(0.0),
        a2: vfactory.add_const(0.0),
        Cdc: vfactory.add_const(10.0),
        Vpk_ref: vfactory.add_const(None),
        phi_v_ref: vfactory.add_const(None),
    }
    
    # EMT model outputs three-phase currents
    p_conv_init = -(inputs[0] * i_a_t + inputs[1] * i_b_t + inputs[2] * i_c_t) / vfactory.add_const(3.0)
    eps_vdc = vfactory.add_const(1.0e-10)
    vsc_block = Block(
        algebraic_eqs=[
            Pt_vsc + P,
            Qt_vsc + Q,
            P_conv + (inputs[0] * i_a_t + inputs[1] * i_b_t + inputs[2] * i_c_t) / vfactory.add_const(3.0),
            v_dc_cap - inputs[9],
        ],
        algebraic_vars=[Pt_vsc, Qt_vsc, i_a_t, i_b_t, i_c_t, i_dc, P_conv],
        state_eqs=[(i_dc - P_conv / (v_dc_cap + eps_vdc)) / Cdc],
        state_vars=[v_dc_cap],
        diff_vars=[d_v_dc_cap],
        event_dict= event_dict,
        init_eqs={
            v_dc_cap: inputs[9],
            P_conv: p_conv_init,
            i_dc: p_conv_init / inputs[9],
        },
        diff_init_eqs={
            d_v_dc_cap: vfactory.add_const(0.0),
        },
        external_mapping={
            VarPowerFlowReferenceType.P: P,
            VarPowerFlowReferenceType.Q: Q,
        },
        in_vars= inputs,
        out_vars = []
    )
    vsc_block.external_mapping = {
        VarPowerFlowReferenceType.P: P,
        VarPowerFlowReferenceType.Q: Q,
        VarPowerFlowReferenceType.v_A: inputs[0],
        VarPowerFlowReferenceType.v_B: inputs[1],
        VarPowerFlowReferenceType.v_C: inputs[2],
        VarPowerFlowReferenceType.vt_A: inputs[0],
        VarPowerFlowReferenceType.vt_B: inputs[1],
        VarPowerFlowReferenceType.vt_C: inputs[2],
        VarPowerFlowReferenceType.Vdc: inputs[9],
        VarPowerFlowReferenceType.Vf_dc: inputs[9],
        VarPowerFlowReferenceType.Idc: i_dc,
        VarPowerFlowReferenceType.If_dc: i_dc,
        VarPowerFlowReferenceType.Pt: Pt_vsc,
        VarPowerFlowReferenceType.Qt: Qt_vsc,
        VarPowerFlowReferenceType.i_A: i_a_t,
        VarPowerFlowReferenceType.i_B: i_b_t,
        VarPowerFlowReferenceType.i_C: i_c_t,
        VarPowerFlowReferenceType.it_A: i_a_t,
        VarPowerFlowReferenceType.it_B: i_b_t,
        VarPowerFlowReferenceType.it_C: i_c_t,
        VarPowerFlowReferenceType.Vpk: Vpk_ref,
        VarPowerFlowReferenceType.phi_v: phi_v_ref,
    }

    vsc_block.add(gfl_block)
    vsc_block.name = 'gfl_block_emt'

    templ.block = vsc_block
    return templ
