# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowReferenceType, ParamPowerFlowReferenceType
from VeraGridEngine.Utils.Symbolic.block import Block
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def get_esd1_rms_template(vfactory: VarFactory, name: str = "ESD1 RMS template") -> RmsModelTemplate:
    """
    ESD1-inspired RMS battery energy storage model.

    The model provides:
    - P/Q setpoint channels (`pref0`, `pext0`, `qref0`)
    - SoC-dependent active-power availability (charge/discharge windows)
    - Current-command limiting with P/Q priority
    - First-order output current dynamics
    - SoC dynamic state with charge/discharge efficiencies

    Sign convention used here:
    - `P > 0`: battery discharging (injecting power into AC grid)
    - `P < 0`: battery charging (absorbing power from AC grid)
    """
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.BatteryDevice

    vm = vfactory.add_var("Vm", reference=VarPowerFlowReferenceType.Vm)
    va = vfactory.add_var("Va", reference=VarPowerFlowReferenceType.Va)
    inputs = [vm, va]

    p = vfactory.add_var("P_esd1", reference=VarPowerFlowReferenceType.P)
    q = vfactory.add_var("Q_esd1", reference=VarPowerFlowReferenceType.Q)

    pref = vfactory.add_var("Pref")
    pext = vfactory.add_var("Pext")
    qref = vfactory.add_var("Qref")
    p_sum = vfactory.add_var("P_sum")
    q_sum = vfactory.add_var("Q_sum")

    p_dis_av = vfactory.add_var("P_dis_av")
    p_ch_av = vfactory.add_var("P_ch_av")

    ip_cmd = vfactory.add_var("Ip_cmd")
    iq_cmd = vfactory.add_var("Iq_cmd")
    ip_max = vfactory.add_var("Ip_max")
    iq_max = vfactory.add_var("Iq_max")

    ipout = vfactory.add_var("Ipout_y")
    iqout = vfactory.add_var("Iqout_y")
    soc = vfactory.add_var("Soc")

    pref0 = vfactory.add_var("pref0")
    pext0 = vfactory.add_var("pext0")
    qref0 = vfactory.add_var("qref0")

    p_dis_max = vfactory.add_var("p_dis_max")
    p_ch_max = vfactory.add_var("p_ch_max")
    qmax = vfactory.add_var("qmax")
    qmin = vfactory.add_var("qmin")

    soc_min = vfactory.add_var("soc_min")
    soc_max = vfactory.add_var("soc_max")
    soc_db = vfactory.add_var("soc_db")
    soc0 = vfactory.add_var("soc0")
    ecap_h = vfactory.add_var("ecap_h")
    eta_ch = vfactory.add_var("eta_ch")
    eta_dis = vfactory.add_var("eta_dis")

    ialim = vfactory.add_var("ialim")
    pqflag = vfactory.add_var("pqflag")
    tip = vfactory.add_var("tip")
    tiq = vfactory.add_var("tiq")

    one = vfactory.add_const(1.0)
    zero = vfactory.add_const(0.0)
    eps_v = vfactory.add_const(0.01)
    eps_i = vfactory.add_const(1e-8)
    sec_per_hour = vfactory.add_const(3600.0)

    vm_eff = sym.max(vm, eps_v)
    soc_band = sym.max(soc_db, eps_i)

    g_dis = sym.hard_sat((soc - soc_min) / soc_band, zero, one)
    g_ch = sym.hard_sat((soc_max - soc) / soc_band, zero, one)

    p_dis_av_expr = p_dis_max * g_dis
    p_ch_av_expr = p_ch_max * g_ch

    pref_expr = pref0
    pext_expr = pext0
    qref_expr = qref0

    p_ref = pref_expr + pext_expr
    p_sum_expr = sym.hard_sat(p_ref, -p_ch_av_expr, p_dis_av_expr)
    q_sum_expr = sym.hard_sat(qref_expr, qmin, qmax)

    ip_unlimited = p_sum_expr / vm_eff
    iq_unlimited = q_sum_expr / vm_eff

    ip_cap_q = sym.sqrt(sym.max(ialim ** 2 - iq_unlimited ** 2, eps_i))
    iq_cap_p = sym.sqrt(sym.max(ialim ** 2 - ip_unlimited ** 2, eps_i))

    ip_max_expr = pqflag * ialim + (one - pqflag) * ip_cap_q
    iq_max_expr = (one - pqflag) * ialim + pqflag * iq_cap_p

    ip_cmd_expr = sym.hard_sat(ip_unlimited, -ip_max_expr, ip_max_expr)
    iq_cmd_expr = sym.hard_sat(iq_unlimited, -iq_max_expr, iq_max_expr)

    p_dis = sym.max(p, zero)
    p_ch = sym.max(-p, zero)
    ecap_sec = sym.max(ecap_h * sec_per_hour, eps_i)
    soc_dot = (-p_dis / sym.max(eta_dis, eps_i) + eta_ch * p_ch) / ecap_sec

    block = Block(
        algebraic_eqs=[
            p - vm * ipout,
            q - vm * iqout,
            pref - pref_expr,
            pext - pext_expr,
            qref - qref_expr,
            p_dis_av - p_dis_av_expr,
            p_ch_av - p_ch_av_expr,
            p_sum - p_sum_expr,
            q_sum - q_sum_expr,
            ip_max - ip_max_expr,
            iq_max - iq_max_expr,
            ip_cmd - ip_cmd_expr,
            iq_cmd - iq_cmd_expr,
        ],
        algebraic_vars=[
            p,
            q,
            pref,
            pext,
            qref,
            p_dis_av,
            p_ch_av,
            p_sum,
            q_sum,
            ip_max,
            iq_max,
            ip_cmd,
            iq_cmd,
        ],
        state_eqs=[
            (ip_cmd - ipout) / tip,
            (iq_cmd - iqout) / tiq,
            soc_dot,
        ],
        state_vars=[ipout, iqout, soc],
        in_vars=inputs,
        init_eqs={
            soc: soc0,
            pref: pref_expr,
            pext: pext_expr,
            qref: qref_expr,
            p_dis_av: p_dis_av_expr,
            p_ch_av: p_ch_av_expr,
            p_sum: p_sum_expr,
            q_sum: q_sum_expr,
            ip_max: ip_max_expr,
            iq_max: iq_max_expr,
            ip_cmd: ip_cmd_expr,
            iq_cmd: iq_cmd_expr,
            ipout: ip_cmd_expr,
            iqout: iq_cmd_expr,
        },
        event_dict={
            pref0: p,
            pext0: vfactory.add_const(0.0),
            qref0: q,
            p_dis_max: vfactory.add_const(1.0),
            p_ch_max: vfactory.add_const(1.0),
            qmax: vfactory.add_const(1.0),
            qmin: vfactory.add_const(-1.0),
            soc_db: vfactory.add_const(0.02),
            ialim: vfactory.add_const(1.3),
            pqflag: vfactory.add_const(1.0),
            tip: vfactory.add_const(0.02),
            tiq: vfactory.add_const(0.02),
        },
        parameters={
            soc_min: vfactory.add_const(0.1),
            soc_max: vfactory.add_const(0.95),
            soc0: vfactory.add_const(0.5),
            ecap_h: vfactory.add_const(2.0),
            eta_ch: vfactory.add_const(0.95),
            eta_dis: vfactory.add_const(0.95),
        },
    )

    block.name = name
    block.external_mapping = {
        VarPowerFlowReferenceType.Vm: vm,
        VarPowerFlowReferenceType.Va: va,
        VarPowerFlowReferenceType.P: p,
        VarPowerFlowReferenceType.Q: q,
    }
    block.api_obj_mapping = {
        ParamPowerFlowReferenceType.battery_enom_mwh: ecap_h,
        ParamPowerFlowReferenceType.battery_soc_0_pu: soc0,
        ParamPowerFlowReferenceType.battery_max_soc_pu: soc_max,
        ParamPowerFlowReferenceType.battery_min_soc_pu: soc_min,
        ParamPowerFlowReferenceType.battery_charge_efficiency_pu: eta_ch,
        ParamPowerFlowReferenceType.battery_discharge_efficiency_pu: eta_dis,
    }
    block.out_vars = [p, q]

    templ.block.children.append(block)
    templ.block.name = name
    templ.block.external_mapping = block.external_mapping
    templ.block.in_vars = inputs
    templ.block.out_vars = block.out_vars
    templ.comment = 'Battery ESD1 RMS model'
    return templ
