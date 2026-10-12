# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


import math

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowReferenceType, ParamPowerFlowReferenceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_helpers import tf_to_block
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template

def get_pll_transform_rms(vfactory: VarFactory, name: str = "Pll_transform_rms") -> RmsModelTemplate:
    """
     Pll
    """
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice

    inputs = [vfactory.add_var("Vm", reference=VarPowerFlowReferenceType.Vm),
              vfactory.add_var("Va", reference=VarPowerFlowReferenceType.Va),
              ]
    ############### phase detector block ############################

    # phase detector Variables
    vd = vfactory.add_var('vd', shared_reference="vd_reference")
    vq = vfactory.add_var('vq', shared_reference="vq_reference")
    theta_phase_detect_blk = vfactory.add_var('theta', shared_reference="theta_reference")

    phase_detector_block = Block(

        algebraic_eqs=[
            vd - inputs[0] * sym.sin(inputs[1] - theta_phase_detect_blk),
            vq - inputs[0] * sym.cos(inputs[1] - theta_phase_detect_blk),
        ],
        algebraic_vars=[vd, vq],
        init_eqs={
            theta_phase_detect_blk: inputs[1],
            vd: inputs[0] * sym.sin(inputs[1] - theta_phase_detect_blk),
            vq: inputs[0] * sym.cos(inputs[1] - theta_phase_detect_blk),
        },
        name="Phase Detector",
        out_vars=[vd, vq],
        in_vars=[inputs[0], inputs[1], theta_phase_detect_blk]
    )

    ############### loop filter block ############################

    # Parameters
    Kp_pll = vfactory.add_var('Kp_pll')
    Ki_pll = vfactory.add_var('Ki_pll')

    # variables
    vd_pi_block = vfactory.add_var('vd_pi_block', shared_reference="vd_reference")
    vq_pi_block = vfactory.add_var('vq_pi_block', shared_reference="vq_reference")

    event_dict = {
        Kp_pll: vfactory.add_const(0.001),
        Ki_pll: vfactory.add_const(0.1),
    }

    PI_block, omega = tf_to_block(vfactory,
                                  num=[Ki_pll, Kp_pll],
                                  den=[0, 1],
                                  x=vd_pi_block,
                                  name='PLL_integrator'
                                  )

    loop_filter_block = Block(
        in_vars=[vd_pi_block],
        out_vars=[omega],
        event_dict= event_dict,
        children= [PI_block],
        name="Loop filter",
        init_eqs={
            omega: vfactory.add_const(1),

        },
    )

    omega.name = "omega"
    vfactory.add_shared_ref_to_var(omega, "omega_reference")

    ############ VCO #############################################

    # Parameters
    fn = vfactory.add_var('fn')

    # variables
    omega_vco = vfactory.add_var('omega_vco', shared_reference="omega_reference")
    theta = vfactory.add_var('theta', shared_reference="theta_reference")

    event_dict = {}

    vco_block = Block(
        state_eqs=[2 * math.pi * fn * (omega_vco - 1)],
        state_vars=[theta],
        event_dict=event_dict,
        name= 'VCO',
        out_vars = [theta],
        in_vars= [omega_vco],
        api_obj_mapping={ParamPowerFlowReferenceType.freq: fn},
        parameters={fn: vfactory.add_const(50)},
    )



    templ.block.children = [phase_detector_block, loop_filter_block, vco_block]
    templ.block.in_vars = inputs
    templ.block.out_vars = [vd, vq, theta, omega]
    templ.block.name = "Phase locked loop"

    templ.comment = 'Reusable VSC phase-locked-loop RMS control block'
    return templ


def get_pi_current_controller(vfactory: VarFactory, name: str = "current_ctrl_iq") -> RmsModelTemplate:
    """
     Current control iq
    """
    suffix = f"_{name}" if name else ""
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice

    Kp_icl = vfactory.add_var('Kp_icl')  # proportional gain for inner current loop
    Ki_icl = vfactory.add_var('Ki_icl')  # integral gain for inner current loop

    block = Block()

    block.name = name

    event_dict = {
        Kp_icl: vfactory.add_const(0.05),
        Ki_icl: vfactory.add_const(1.0),
    }

    i_q = vfactory.add_var('i_q', shared_reference='i_q_reference')
    i_q_ref_sat = vfactory.add_var('i_q_ref_sat', shared_reference='i_q_ref_sat_reference')
    i_d = vfactory.add_var('i_d', shared_reference='i_d_reference')
    i_d_ref_sat = vfactory.add_var('i_d_ref_sat', shared_reference='i_d_ref_sat_reference')

    inputs = [i_q, i_q_ref_sat, i_d, i_d_ref_sat]

    control_block_iq, vq_hat = tf_to_block(vfactory,
                                           num=[Ki_icl, Kp_icl],
                                           den=[0, 1],
                                           x=inputs[0] - inputs[1],
                                           name='vq_hat',
                                           output_var_name = 'vq_hat'
                                           )

    control_block_iq.init_eqs = {
    }

    vfactory.add_shared_ref_to_var(vq_hat, "vq_hat_reference")

    control_block_id, vd_hat = tf_to_block(vfactory,
                                           num=[Ki_icl, Kp_icl],
                                           den=[0, 1],
                                           x=inputs[2] - inputs[3],
                                           name='vq_hat',
                                           output_var_name='vd_hat'
                                           )

    control_block_id.init_eqs = {
    }

    vfactory.add_shared_ref_to_var(vd_hat, "vd_hat_reference")

    control_block_iq.in_vars = [i_q, i_q_ref_sat]
    control_block_iq.out_vars = [vq_hat]

    control_block_id.in_vars = [i_d, i_d_ref_sat]
    control_block_id.out_vars = [vd_hat]

    block.event_dict = event_dict
    block.in_vars = inputs
    block.out_vars = [vq_hat, vd_hat]
    block.children = [control_block_iq, control_block_id]

    templ.block = block


    templ.comment = 'Reusable VSC PI current-controller RMS block'
    return templ


def get_pi_power_controller(vfactory: VarFactory, name: str = "power_ctrl") -> RmsModelTemplate:
    """
     Current control iq
    """
    suffix = f"_{name}" if name else ""
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice

    # Parameters
    Kp_pol = vfactory.add_var('Kp_pol')  # proportional gain for outer power loop
    Ki_pol = vfactory.add_var('Ki_pol')  # integral gain for outer power loop
    Ki_vdc = vfactory.add_var('ki_vdc')  # proportional gain for DC voltage control
    Kp_vdc = vfactory.add_var('Kp_vdc')  # proportional gain for DC voltage control

    # Voltage references for control modes
    Vdc_ref = vfactory.add_var('Vdc_ref')

    # inputs
    P = vfactory.add_var('P', shared_reference='P_reference')
    Q = vfactory.add_var('Q', shared_reference='Q_reference')
    i_q_ref = vfactory.add_var('i_q_ref', shared_reference='i_q_ref_reference')
    i_d_ref = vfactory.add_var('i_d_ref', shared_reference='i_d_ref_reference')
    v_dc = vfactory.add_var('v_dc', shared_reference='v_dc_reference')


    P_ref = vfactory.add_var('P_ref', shared_reference='P_ref_reference')
    Q_ref = vfactory.add_var('Q_ref', shared_reference='Q_ref_reference')

    event_dict = {
        Kp_pol: vfactory.add_const(0.05),
        Ki_pol: vfactory.add_const(1.0),
        Ki_vdc: vfactory.add_const(0.1),
        Kp_vdc: vfactory.add_const(0.01),
        Vdc_ref: v_dc,
        P_ref: P,
        Q_ref: Q,
    }

    block = Block()

    block.name = name




    inputs = [P, Q]

    control_block_1, _ = tf_to_block(vfactory,
                                     num=[Ki_pol, Kp_pol],
                                     den=[0, 1],
                                     x=P_ref - P,
                                     y=i_q_ref,
                                     name='Pac_ctrl'
                                     )
    # vfactory.add_shared_ref_to_var(control_block_1.out_vars[0], "iq_ref_ctrl_1")


    control_block_1.name = 'Pac_ctrl'
    #
    # control_block_2, _ = tf_to_block(vfactory,
    #                                  num=[Ki_vdc, Kp_vdc],
    #                                  den=[0, 1],
    #                                  x=(v_dc - Vdc_ref),
    #                                  y=i_q_ref,
    #                                  name='Vdc_ctrl'
    #                                  )
    # control_block_2.name = 'Vdc_ctrl'


    control_block_2, _ = tf_to_block(vfactory,
                                    num=[Ki_pol, Kp_pol],
                                    den=[0, 1],
                                    x=Q_ref - Q,
                                    y=i_d_ref,
                                    name='Qac_ctrl'
                                    )

    control_block_1.in_vars = [P, P_ref]
    control_block_2.in_vars = [Q, Q_ref]
    control_block_1.event_dict = event_dict
    control_block_2.event_dict = event_dict

    block.children = [control_block_1, control_block_2]

    block.in_vars = inputs
    block.out_vars = [control_block_1.out_vars[0], control_block_2.out_vars[0]]

    templ.block = block

    templ.comment = 'Reusable VSC PI power-controller RMS block'
    return templ

def get_gfl_electrical_block(vfactory: VarFactory, name: str = "gfl_electrical_eqs") -> RmsModelTemplate:
    """
    Gfl electrical equations block
    """
    suffix = f"_{name}" if name else ""
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice

    #input vars
    Pt_vsc = vfactory.add_var('Pt_vsc', shared_reference='Pt_vsc_reference')
    Qt_vsc = vfactory.add_var('Qt_vsc', shared_reference='Qt_vsc_reference')

    # variables from pll
    v_d_g = vfactory.add_var('v_d_g', shared_reference='vd_reference')
    v_q_g = vfactory.add_var('v_q_g', shared_reference='vq_reference')
    theta = vfactory.add_var('theta', shared_reference='theta_reference')
    omega = vfactory.add_var('omega', shared_reference='omega_reference')

    # variables from control
    vq_hat = vfactory.add_var('vq_hat', shared_reference='vq_hat_reference')
    vd_hat = vfactory.add_var('vd_hat', shared_reference='vd_hat_reference')

    # electrical block variables
    v_d_c = vfactory.add_var('v_d_c')
    v_q_c = vfactory.add_var('v_q_c')
    i_d = vfactory.add_var('i_d', shared_reference='i_d_reference')
    i_q = vfactory.add_var('i_q', shared_reference='i_q_reference')
    P = vfactory.add_var('P', shared_reference='P_reference')
    Q = vfactory.add_var('Q', shared_reference='Q_reference')
    dt_id = vfactory.add_diff_var('dt_id', base_var=i_d)
    dt_iq = vfactory.add_diff_var('dt_iq', base_var=i_q)

    # electrical block parameters
    R = vfactory.add_var('R')
    L = vfactory.add_var('L')

    api_obj_mapping = {
        ParamPowerFlowReferenceType.R1: R,
        ParamPowerFlowReferenceType.X1: L,

    }

    electrical_block = Block(
        algebraic_eqs=[
            v_d_c - v_d_g + (R * i_d + L * dt_id - omega * L * i_q),
            v_q_c - v_q_g + (-R * i_q + L * dt_iq - omega * L * i_d),
            v_d_c - (vd_hat + v_d_g - L * omega * i_q),
            v_q_c - (vq_hat + v_q_g + L * omega * i_d),
            P - (v_q_g * i_q + v_d_g * i_d),
            Q - (v_q_g * i_d - v_d_g * i_q)

        ],
        algebraic_vars=[v_q_c, v_d_c, i_d, i_q, P, Q, vd_hat, vq_hat],
        diff_vars=[dt_id, dt_iq],
        parameters={
            R: vfactory.add_const(0.01),
            L: vfactory.add_const(0.05),
        },
        in_vars=[v_d_g, v_q_g, theta, omega, vd_hat, vq_hat, Pt_vsc, Qt_vsc],
        out_vars=[P, Q, i_d, i_q, P],
        init_eqs={
            P: -Pt_vsc,
            Q: -Qt_vsc,
            i_q: P / v_q_g,
            i_d: Q / v_q_g,
            v_d_c: v_d_g - (R * i_d - omega * L * i_q),
            v_q_c: v_q_g - (-R * i_q - omega * L * i_d),
            vd_hat: v_d_c - (v_d_g - L * omega * i_q),
            vq_hat: v_q_c - (v_q_g + L * omega * i_d),
        },
        api_obj_mapping=api_obj_mapping,
    )

    electrical_block.name = "electrical equations"

    templ.block = electrical_block

    templ.comment = 'Grid-following converter electrical-equations RMS block'
    return templ


def get_gfl_converter_line_rms_block(vfactory: VarFactory, name: str = "gfl_converter_line") -> RmsModelTemplate:
    """
    Line between converter internal AC bus (from) and grid bus (to).
    """
    templ = get_line_rms_template(vfactory=vfactory, name=name)
    block = templ.block

    vfactory.add_shared_ref_to_var(block.in_vars[0], "Vm_c_reference")
    vfactory.add_shared_ref_to_var(block.in_vars[1], "Va_c_reference")
    vfactory.add_shared_ref_to_var(block.in_vars[2], "Vm_g_reference")
    vfactory.add_shared_ref_to_var(block.in_vars[3], "Va_g_reference")

    vfactory.add_shared_ref_to_var(block.out_vars[0], "Pf_line_reference")
    vfactory.add_shared_ref_to_var(block.out_vars[1], "Pt_line_reference")
    vfactory.add_shared_ref_to_var(block.out_vars[2], "Qf_line_reference")
    vfactory.add_shared_ref_to_var(block.out_vars[3], "Qt_line_reference")

    block.name = name

    return templ


def get_gfl_converter_bus_block(vfactory: VarFactory, name: str = "gfl_converter_bus") -> RmsModelTemplate:
    """
    Define the internal converter AC bus from its dq voltage in the PLL frame.
    """
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice

    Vm_c = vfactory.add_var("Vm_c", shared_reference="Vm_c_reference")
    Va_c = vfactory.add_var("Va_c", shared_reference="Va_c_reference")
    theta = vfactory.add_var("theta_c", shared_reference="theta_reference")

    v_d_c = vfactory.add_var("v_d_c_bus", shared_reference="v_d_c_reference")
    v_q_c = vfactory.add_var("v_q_c_bus", shared_reference="v_q_c_reference")

    block = Block(
        algebraic_eqs=[
            v_d_c - Vm_c * sym.sin(Va_c - theta),
            v_q_c - Vm_c * sym.cos(Va_c - theta),
        ],
        algebraic_vars=[Vm_c, Va_c],
        init_eqs={
            Vm_c: sym.sqrt(v_d_c ** 2 + v_q_c ** 2),
            Va_c: theta + sym.atan(v_d_c / (v_q_c + vfactory.add_const(1e-11))),
        },
        in_vars=[v_d_c, v_q_c, theta],
        out_vars=[Vm_c, Va_c],
        name=name,
    )

    templ.block = block

    templ.comment = 'Grid-following converter AC-bus interface RMS block'
    return templ


def get_gfl_voltage_control_electrical_block(vfactory: VarFactory,
                                             name: str = "gfl_voltage_control_electrical") -> RmsModelTemplate:
    """
    Electrical voltage-control constraints separated from the line model.
    """
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice

    v_d_c = vfactory.add_var("v_d_c_ctrl", shared_reference="v_d_c_reference")
    v_q_c = vfactory.add_var("v_q_c_ctrl", shared_reference="v_q_c_reference")

    v_d_g = vfactory.add_var("v_d_g_ctrl", shared_reference="vd_reference")
    v_q_g = vfactory.add_var("v_q_g_ctrl", shared_reference="vq_reference")
    omega = vfactory.add_var("omega_ctrl", shared_reference="omega_reference")

    vd_hat = vfactory.add_var("vd_hat_ctrl", shared_reference="vd_hat_reference")
    vq_hat = vfactory.add_var("vq_hat_ctrl", shared_reference="vq_hat_reference")

    i_d = vfactory.add_var("i_d_ctrl", shared_reference="i_d_reference")
    i_q = vfactory.add_var("i_q_ctrl", shared_reference="i_q_reference")

    L = vfactory.add_var("L")

    block = Block(
        algebraic_eqs=[
            v_d_c - (vd_hat + v_d_g - L * omega * i_q),
            v_q_c - (vq_hat + v_q_g + L * omega * i_d),
        ],
        algebraic_vars=[v_d_c, v_q_c],
        parameters={
            L: vfactory.add_const(0.05),
        },
        in_vars=[vd_hat, vq_hat, v_d_g, v_q_g, omega, i_d, i_q],
        out_vars=[v_d_c, v_q_c],
        init_eqs={
            v_d_c: vd_hat + v_d_g - L * omega * i_q,
            v_q_c: vq_hat + v_q_g + L * omega * i_d,
        },
        api_obj_mapping={
            ParamPowerFlowReferenceType.X1: L,
        },
        name=name,
    )

    templ.block = block

    templ.comment = 'Grid-following converter voltage-control electrical RMS block'
    return templ


def get_gfl_line_current_measurement_block(vfactory: VarFactory,
                                           name: str = "gfl_line_current_measurement") -> RmsModelTemplate:
    """
    Derive dq current feedback from the grid-side line power.
    """
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice

    Pt_line = vfactory.add_var("Pt_line", shared_reference="Pt_line_reference")
    Qt_line = vfactory.add_var("Qt_line", shared_reference="Qt_line_reference")

    v_d_g = vfactory.add_var("v_d_g_power", shared_reference="vd_reference")
    v_q_g = vfactory.add_var("v_q_g_power", shared_reference="vq_reference")

    i_d = vfactory.add_var("i_d", shared_reference="i_d_reference")
    i_q = vfactory.add_var("i_q", shared_reference="i_q_reference")

    eps = vfactory.add_const(1e-11)
    v2 = v_d_g ** 2 + v_q_g ** 2 + eps
    P = -Pt_line
    Q = -Qt_line

    block = Block(
        algebraic_eqs=[
            i_d - (P * v_d_g + Q * v_q_g) / v2,
            i_q - (P * v_q_g - Q * v_d_g) / v2,
        ],
        algebraic_vars=[i_d, i_q],
        in_vars=[Pt_line, Qt_line, v_d_g, v_q_g],
        out_vars=[i_d, i_q],
        init_eqs={
            i_d: (P * v_d_g + Q * v_q_g) / v2,
            i_q: (P * v_q_g - Q * v_d_g) / v2,
        },
        name=name,
    )

    templ.block = block

    templ.comment = 'Grid-following converter line-current measurement RMS block'
    return templ


def get_pi_power_controller_from_line(vfactory: VarFactory, name: str = "power_ctrl_line") -> RmsModelTemplate:
    """
    Power controller using converter power directly from line Pt/Qt.
    """
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice

    Kp_pol = vfactory.add_var('Kp_pol')
    Ki_pol = vfactory.add_var('Ki_pol')
    Ki_vdc = vfactory.add_var('ki_vdc')
    Kp_vdc = vfactory.add_var('Kp_vdc')
    Vdc_ref = vfactory.add_var('Vdc_ref')

    Pt_line = vfactory.add_var('Pt_line_ctrl', shared_reference='Pt_line_reference')
    Qt_line = vfactory.add_var('Qt_line_ctrl', shared_reference='Qt_line_reference')
    i_q_ref = vfactory.add_var('i_q_ref', shared_reference='i_q_ref_reference')
    i_d_ref = vfactory.add_var('i_d_ref', shared_reference='i_d_ref_reference')
    v_dc = vfactory.add_var('v_dc', shared_reference='v_dc_reference')

    P_ref = vfactory.add_var('P_ref', shared_reference='P_ref_reference')
    Q_ref = vfactory.add_var('Q_ref', shared_reference='Q_ref_reference')

    event_dict = {
        Kp_pol: vfactory.add_const(0.05),
        Ki_pol: vfactory.add_const(1.0),
        Ki_vdc: vfactory.add_const(0.1),
        Kp_vdc: vfactory.add_const(0.01),
        Vdc_ref: v_dc,
        P_ref: -Pt_line,
        Q_ref: -Qt_line,
    }

    control_block_1, _ = tf_to_block(vfactory,
                                     num=[Ki_pol, Kp_pol],
                                     den=[0, 1],
                                     x=P_ref + Pt_line,
                                     y=i_q_ref,
                                     name='Pac_ctrl_line'
                                     )

    control_block_2, _ = tf_to_block(vfactory,
                                     num=[Ki_pol, Kp_pol],
                                     den=[0, 1],
                                     x=Q_ref + Qt_line,
                                     y=i_d_ref,
                                     name='Qac_ctrl_line'
                                     )

    control_block_1.in_vars = [Pt_line, P_ref]
    control_block_2.in_vars = [Qt_line, Q_ref]
    control_block_1.event_dict = event_dict
    control_block_2.event_dict = event_dict

    block = Block(
        children=[control_block_1, control_block_2],
        in_vars=[Pt_line, Qt_line],
        out_vars=[control_block_1.out_vars[0], control_block_2.out_vars[0]],
        name=name,
    )

    templ.block = block

    templ.comment = 'Grid-following converter line power-controller RMS block'
    return templ


def get_gfl_losses_from_line_block(vfactory: VarFactory, name: str = "gfl_losses_line") -> RmsModelTemplate:
    """
    Losses/output block using line Pt/Qt directly.
    """
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice

    i_d = vfactory.add_var('id', shared_reference='i_d_reference')
    i_q = vfactory.add_var('iq', shared_reference='i_q_reference')
    Pt_line = vfactory.add_var('Pt_line_losses', shared_reference='Pt_line_reference')
    Qt_line = vfactory.add_var('Qt_line_losses', shared_reference='Qt_line_reference')

    Pt_vsc = vfactory.add_var('Pt_vsc', reference=VarPowerFlowReferenceType.Pt,
                              shared_reference='Pt_vsc_reference')
    Qt_vsc = vfactory.add_var('Qt_vsc', reference=VarPowerFlowReferenceType.Qt,
                              shared_reference='Qt_vsc_reference')
    Pf_vsc = vfactory.add_var('Pf_vsc', shared_reference='Pf_vsc_reference')

    bt = vfactory.add_var('bt')
    gt = vfactory.add_var('gt')
    Qf = vfactory.add_var('Qf')
    a0 = vfactory.add_var('a0')
    a1 = vfactory.add_var('a1')
    a2 = vfactory.add_var('a2')

    api_obj_mapping = {
        ParamPowerFlowReferenceType.alpha1: a0,
        ParamPowerFlowReferenceType.alpha2: a1,
        ParamPowerFlowReferenceType.alpha3: a2,
    }

    event_dict = {
        Qf: vfactory.add_const(0.0),
        bt: vfactory.add_const(0.0),
        gt: vfactory.add_const(0.1),
    }
    parameters = {a0: vfactory.add_const(0.0), a1: vfactory.add_const(0.0), a2: vfactory.add_const(0.0)}

    external_mapping = {
        VarPowerFlowReferenceType.Pt: Pt_vsc,
        VarPowerFlowReferenceType.Qt: Qt_vsc,
        VarPowerFlowReferenceType.Pf: Pf_vsc,
        VarPowerFlowReferenceType.Qf: Qf,
    }

    Im = sym.sqrt(i_d ** 2 + i_q ** 2 + vfactory.add_const(1e-11))

    block = Block(
        algebraic_eqs=[
            Pf_vsc - Pt_line - (a0 + a1 * Im + a2 * Im ** 2),
            Pt_vsc - Pt_line,
            Qt_vsc - Qt_line,
        ],
        algebraic_vars=[Pt_vsc, Qt_vsc, Pf_vsc],
        event_dict=event_dict,
        parameters=parameters,
        external_mapping=external_mapping,
        in_vars=[i_d, i_q, Pt_line, Qt_line],
        out_vars=[Pt_vsc, Qt_vsc, Pf_vsc],
        api_obj_mapping=api_obj_mapping,
        name=name,
    )

    templ.block = block

    templ.comment = 'Grid-following converter line-loss RMS block'
    return templ

def get_gfl_current_limiter_block(vfactory: VarFactory, name: str = "electrical") -> RmsModelTemplate:
    """
    Gfl electrical equations block
    """
    suffix = f"_{name}" if name else ""
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice

    # limiter block input variables
    i_d_lim = vfactory.add_var('i_d_lim', shared_reference='i_d_reference')
    i_q_lim = vfactory.add_var('i_q_lim', shared_reference='i_q_reference')

    # limiter block constants
    I_max = vfactory.add_const(1.2)

    # limiter block variables
    i_d_ref = vfactory.add_var('i_d_ref', shared_reference='i_d_ref_reference')
    i_q_ref = vfactory.add_var('i_q_ref', shared_reference='i_q_ref_reference')
    id_max = sym.sqrt(sym.max(I_max ** 2 - sym.max(i_q_lim, i_q_ref) ** 2, vfactory.add_const(1e-5)))
    i_d_ref_sat = sym.hard_sat(i_d_ref, -id_max, id_max)
    i_q_ref_sat = sym.hard_sat(i_q_ref, -I_max, I_max)
    i_d_ref_sat_var = vfactory.add_var('i_d_ref_sat')
    i_q_ref_sat_var = vfactory.add_var('i_q_ref_sat')

    current_limiter_block = Block(
        algebraic_eqs=[i_d_ref_sat_var - i_d_ref_sat,
                       i_q_ref_sat_var - i_q_ref_sat,
                       ],
        algebraic_vars=[i_d_ref_sat_var, i_q_ref_sat_var],
        out_vars=[i_d_ref, i_q_ref],
        in_vars=[i_d_lim, i_q_lim],
        init_eqs={
            i_d_ref_sat_var: i_d_ref_sat,
            i_q_ref_sat_var: i_q_ref_sat,
            i_q_ref: i_q_lim,
            i_d_ref: i_d_lim,
        }
    )

    current_limiter_block.name = "current limiters"
    templ.block = current_limiter_block

    templ.comment = 'Grid-following converter current-limiter RMS block'
    return templ

def get_gfl_losses_block(vfactory: VarFactory, name: str = "gfl_losses") -> RmsModelTemplate:
    """
    Gfl losses block
    """
    suffix = f"_{name}" if name else ""
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice

    # input vars
    i_d = vfactory.add_var('id', shared_reference='i_d_reference')
    i_q = vfactory.add_var('iq', shared_reference='i_q_reference')
    P = vfactory.add_var('P', shared_reference='P_reference')
    Q = vfactory.add_var('Q', shared_reference='Q_reference')

    # Vars:
    Pt_vsc = vfactory.add_var('Pt_vsc', reference= VarPowerFlowReferenceType.Pt, shared_reference= 'Pt_vsc_reference')
    Qt_vsc = vfactory.add_var('Qt_vsc', reference= VarPowerFlowReferenceType.Qt, shared_reference= 'Qt_vsc_reference')
    Pf_vsc = vfactory.add_var('Pf_vsc', shared_reference= 'Pf_vsc_reference')

    # Parameters:
    bt = vfactory.add_var('bt')
    gt = vfactory.add_var('gt')
    Qf = vfactory.add_var('Qf')
    a0 = vfactory.add_var('a0')
    a1 = vfactory.add_var('a1')
    a2 = vfactory.add_var('a2')

    api_obj_mapping = {
        ParamPowerFlowReferenceType.alpha1: a0,
        ParamPowerFlowReferenceType.alpha2: a1,
        ParamPowerFlowReferenceType.alpha3: a2,
    }

    event_dict = {
        Qf: vfactory.add_const(0.0),
        bt: vfactory.add_const(0.0),
        gt: vfactory.add_const(0.1),
    }
    parameters = {a0: vfactory.add_const(0.0), a1: vfactory.add_const(0.0), a2: vfactory.add_const(0.0)}

    external_mapping = {
        VarPowerFlowReferenceType.Pt: Pt_vsc,
        VarPowerFlowReferenceType.Qt: Qt_vsc,
        VarPowerFlowReferenceType.Pf: Pf_vsc,
        VarPowerFlowReferenceType.Qf: Qf,
        VarPowerFlowReferenceType.P: P,
        VarPowerFlowReferenceType.Q: Q,
    }

    Im = sym.sqrt(i_d ** 2 + i_q ** 2 + vfactory.add_const(1e-11))

    losses_block = Block(
        algebraic_eqs=[
            Pf_vsc + P - (a0 + a1 * Im + a2 * Im ** 2),
            Pt_vsc + P,
            Qt_vsc + Q,
        ],
        algebraic_vars=[Pt_vsc, Qt_vsc, Pf_vsc],
        init_eqs={
            # vsh: sym.sqrt((exp1**2 + exp2**2)/(gt**2 + bt**2))/Vm,
            # ash: sym.atan((-gt*exp1 - bt*exp2)/(bt*exp1 - gt*exp2)),
        },
        event_dict=event_dict,
        parameters=parameters,
        external_mapping=external_mapping,
        in_vars=[i_d, i_q, P, Q],
        out_vars=[Pt_vsc, Qt_vsc, Pf_vsc],
        api_obj_mapping=api_obj_mapping
    )

    losses_block.name = name

    templ.block = losses_block

    templ.comment = 'Grid-following converter loss RMS block'
    return templ






def get_gfl_converter_rms(vfactory: VarFactory, name: str = "current_ctrl_iq") -> RmsModelTemplate:
    """
     Current control iq
    """
    suffix = f"_{name}" if name else ""
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice

    # input variables
    Vm = vfactory.add_var('Vm', reference= VarPowerFlowReferenceType.Vm)
    Va = vfactory.add_var('Va', reference=VarPowerFlowReferenceType.Va)
    v_dc = vfactory.add_var('v_dc', shared_reference='v_dc_reference')


    inputs = [Vm, Va, v_dc]

    pll_block = get_pll_transform_rms(vfactory).block
    pi_current_controller = get_pi_current_controller(vfactory).block
    pi_power_controller = get_pi_power_controller(vfactory).block
    electrical_eqs_block = get_gfl_electrical_block(vfactory).block
    current_limiter_block = get_gfl_current_limiter_block(vfactory).block
    losses_block = get_gfl_losses_block(vfactory).block

    out_vars = losses_block.out_vars

    block = Block()

    block.name = name

    block.children = [pll_block, pi_current_controller, pi_power_controller, electrical_eqs_block, current_limiter_block, losses_block]
    block.in_vars = inputs
    block.out_vars = out_vars
    templ.block = block

    templ.comment = 'Reusable grid-following converter RMS control block'
    return templ


def get_gfl_converter_rms_electrical(vfactory: VarFactory,
                                     name: str = "gfl_converter_rms_electrical") -> RmsModelTemplate:
    """
    GFL converter using a separate RMS line for the electrical connection.

    The line is oriented from converter internal AC bus (c) to grid bus (g).
    """
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice

    Vm = vfactory.add_var("Vm", reference=VarPowerFlowReferenceType.Vm,
                          shared_reference="Vm_g_reference")
    Va = vfactory.add_var("Va", reference=VarPowerFlowReferenceType.Va,
                          shared_reference="Va_g_reference")
    v_dc = vfactory.add_var("v_dc", shared_reference="v_dc_reference")

    inputs = [Vm, Va, v_dc]

    pll_block = get_pll_transform_rms(vfactory).block
    pi_current_controller = get_pi_current_controller(vfactory).block
    pi_power_controller = get_pi_power_controller_from_line(vfactory).block
    converter_bus_block = get_gfl_converter_bus_block(vfactory).block
    line_block = get_gfl_converter_line_rms_block(vfactory).block
    line_current_measurement_block = get_gfl_line_current_measurement_block(vfactory).block
    voltage_control_block = get_gfl_voltage_control_electrical_block(vfactory).block
    current_limiter_block = get_gfl_current_limiter_block(vfactory).block
    losses_block = get_gfl_losses_from_line_block(vfactory).block

    # PLL operates on the grid-side voltage.
    vfactory.add_connections(pll_block.in_vars, [Vm, Va])

    block = Block()
    block.name = name
    block.children = [
        pll_block,
        pi_current_controller,
        pi_power_controller,
        voltage_control_block,
        converter_bus_block,
        line_block,
        line_current_measurement_block,
        current_limiter_block,
        losses_block,
    ]
    block.in_vars = inputs
    block.out_vars = losses_block.out_vars
    block.external_mapping = {
        VarPowerFlowReferenceType.Vm: Vm,
        VarPowerFlowReferenceType.Va: Va,
        VarPowerFlowReferenceType.Pt: losses_block.out_vars[0],
        VarPowerFlowReferenceType.Qt: losses_block.out_vars[1],
        VarPowerFlowReferenceType.Pf: losses_block.out_vars[2],
    }

    templ.block = block

    templ.comment = 'Grid-following converter electrical RMS block'
    return templ
