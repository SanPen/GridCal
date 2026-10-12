# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from typing import List
import math

from VeraGridEngine.enumerations import DeviceType, VarPowerFlowReferenceType, ParamPowerFlowReferenceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import (
    Block,
    Var,
)
from VeraGridEngine.Utils.Symbolic.block_helpers import tf_to_block
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.enumerations import ConverterControlType

TYPE_CHECKING = True
if TYPE_CHECKING:
    from VeraGridEngine.Devices.Substation.bus import Bus
    from VeraGridEngine.Devices.Branches.transformer import Transformer2W, WindingType, WindingsConnection

def parse_windings_connection(conn: WindingsConnection) -> tuple[WindingType, WindingType]:
    """
    Parse a WindingsConnection enum into (conn_f, conn_t) WindingType values.
    
    WindingsConnection values are two-character strings:
    - G: GroundedStar
    - S: NeutralStar (ungrounded star)  
    - D: Delta
    
    Examples:
    - GG -> (GroundedStar, GroundedStar)
    - GD -> (GroundedStar, Delta)
    - DD -> (Delta, Delta)
    """
    conn_str = str(conn)
    if len(conn_str) != 2:
        raise ValueError(f"Invalid WindingsConnection: {conn}")
    
    char_to_winding = {
        'G': WindingType.GroundedStar,
        'S': WindingType.NeutralStar,
        'D': WindingType.Delta,
    }
    
    conn_f = char_to_winding.get(conn_str[0])
    conn_t = char_to_winding.get(conn_str[1])
    
    if conn_f is None or conn_t is None:
        raise ValueError(f"Invalid WindingsConnection characters: {conn_str}")
    
    return conn_f, conn_t

def build_vsc_rms(vfactory: VarFactory, name:str = 'vsc_rms_template'):
    """
    Build power control loop model for Grid Following Converter.
    Supports multiple control modes via ConverterControlType.
    from bus is DC
    to   bus is AC
        """

    templ = RmsModelTemplate()
    templ.tpe = DeviceType.VscDevice
    templ.name = name

    vm_t = vfactory.add_var(name="Vm_t", reference=VarPowerFlowReferenceType.Vm)
    va_t = vfactory.add_var(name="Va_t", reference=VarPowerFlowReferenceType.Va)
    vdc = vfactory.add_var(name="Vdc", reference=VarPowerFlowReferenceType.Vdc)

    inputs: List[Var] = [vm_t, va_t, vdc]

    Pf  = vfactory.add_var("Pf_vsc", VarPowerFlowReferenceType.Pf)
    Pt  = vfactory.add_var("Pt", VarPowerFlowReferenceType.Pt)
    Qt_ref = vfactory.add_var("Qt_ref", VarPowerFlowReferenceType.Qt)

    alpha1 = vfactory.add_var("alpha1")
    alpha2 = vfactory.add_var("alpha2")
    alpha3 = vfactory.add_var("alpha3")

    block = Block()
    block.parameters[alpha1] = vfactory.add_const(0.0)
    block.parameters[alpha2] = vfactory.add_const(0.0)
    block.parameters[alpha3] = vfactory.add_const(0.0)

    im = sym.sqrt(Pt * Pt + Qt_ref * Qt_ref) / (vm_t + vfactory.add_const(1e-9))
    block.algebraic_vars = [Pf, Pt]
    block.event_dict[Qt_ref] = vfactory.add_const(0.0)

    # Active power is conserved Reactive isn't
    block.algebraic_eqs  = [
        Pf + Pt - 1.0 * (alpha1 + alpha2 * im + alpha3 * im ** 2),
    ]

    block.external_mapping = {
        VarPowerFlowReferenceType.Vm: vm_t,
        VarPowerFlowReferenceType.Pf: Pf,
        VarPowerFlowReferenceType.Pt: Pt,
        VarPowerFlowReferenceType.Qt: Qt_ref,
    }

    block.api_obj_mapping= {
        ParamPowerFlowReferenceType.alpha1 : alpha1,
        ParamPowerFlowReferenceType.alpha2 : alpha2,
        ParamPowerFlowReferenceType.alpha3 : alpha3,
    }

    block.in_vars =  inputs
    templ.block.children.append(block)
    templ.block.external_mapping = block.external_mapping
    templ.block.in_vars = inputs
    templ.comment = 'VSC grid-following RMS model'
    return templ

def build_vsc_transformer_control(vf: VarFactory, Vm: Var, vdc: Var, name: str = ''):
    suffix = f"_{name}" if name else ""

    # Variables
    am = vf.add_var(f"am{suffix}")
    phi = vf.add_var(f"phi{suffix}")

    # Reference Values
    v_ref = vf.add_var(f"v_ref{suffix}")
    vdc_ref = vf.add_var(f"vdc_ref{suffix}")

    # Controller Parameters
    Kp = vf.add_var(f"Kp{suffix}")
    Ki = vf.add_var(f"Ki{suffix}")
    Km = vf.add_var(f"Km{suffix}")
    Tm = vf.add_var(f"Tm{suffix}")

    block = Block()
    block.event_dict = {
        Kp: vf.add_const(1.0),
        Ki: vf.add_const(10.0),
        Km: vf.add_const(1.0),
        Tm: vf.add_const(0.05),
        v_ref: Vm + am / Km,
        vdc_ref: vdc,
    }

    voltage_control_block, _ = tf_to_block(
        var_factory= vf,
        num = [Km],
        den = [1, Tm],
        x = v_ref - Vm,
        y = am,
        name = f"v_ctrl{suffix}",
    )         

    power_control_block, _ = tf_to_block(
        var_factory= vf,
        num = [Ki, Kp],
        den = [0, 1],
        x = vdc_ref - vdc,
        y = phi,
        name = f"dc_ctrl{suffix}",
    )         

    block.children = [voltage_control_block, power_control_block]
    block.in_vars = [Vm, vdc]
    block.out_vars = [am, phi]
    return block, am, phi

def build_trafo_vsc(vf:VarFactory, trafo:Transformer2W, name:str = ''):
    #from bus is GRID
    #to   bus is CONVERTER

    templ = RmsModelTemplate()
    model_name = name or trafo.name
    templ.name = model_name
    vdc = vf.add_var('vdc_' + model_name, VarPowerFlowReferenceType.Vdc)
    vmf = vf.add_var('vmf_' + model_name, VarPowerFlowReferenceType.Vmf)
    vmt = vf.add_var('vmt_' + model_name, VarPowerFlowReferenceType.Vmt)
    vaf = vf.add_var('vaf_' + model_name, VarPowerFlowReferenceType.Vaf)
    vat = vf.add_var('vat_' + model_name, VarPowerFlowReferenceType.Vat)
    m = vf.add_var('m')
    inputs = [vdc, vmf, vmt, vaf, vat, m]

    k = vf.add_const(np.sqrt(3/8))
    control_block, am, phi = build_vsc_transformer_control(vf=vf, Vm=vmt, vdc=vdc, name=model_name)

    #Variables
    Qf = vf.add_var("Qf_" + model_name, VarPowerFlowReferenceType.Qf)
    Qt = vf.add_var("Qt_" + model_name, VarPowerFlowReferenceType.Qt)
    Pf = vf.add_var("Pf_" + model_name, VarPowerFlowReferenceType.Pf)
    Pt = vf.add_var("Pt_" + model_name, VarPowerFlowReferenceType.Pt)
    Im = vf.add_var("Im_" + model_name)


    #Parameters
    ys = 1.0 / complex(trafo.R, trafo.X)
    ysh = trafo.G + 1j * trafo.B
    gt  = vf.add_var("g")
    bt  = vf.add_var("b")
    gFe = vf.add_var('gFe')
    bmu = vf.add_var('bmu')
    phi0 = vf.add_var('phi0')
    Q_ref = vf.add_var('Q_ref')
    P_ref = vf.add_var('P_ref')
    vtap_f, vtap_t = trafo.get_virtual_taps()
    
    print(f"DEBUG Trafo: R={trafo.R}, X={trafo.X}, G={trafo.G}, B={trafo.B}")
    print(f"DEBUG Trafo: tap_mod={trafo.tap_module}, tap_phase={trafo.tap_phase}, vtap_f={vtap_f}, vtap_t={vtap_t}")
    print(f"vtap  p is {vtap_f}")
    print(f"vtap  t is {vtap_t}")
    print(f'ys is {ys} ysh is {ysh}')
    
    # Calculate phase displacement matching transformer_admittance logic
    # Use conn attribute (preserves user intent) instead of conn_f/conn_t (may be overwritten by template)
    conn_f, conn_t = parse_windings_connection(trafo.conn)
    conn_y_from = conn_f == WindingType.NeutralStar or conn_f == WindingType.GroundedStar
    conn_y_to = conn_t == WindingType.NeutralStar or conn_t == WindingType.GroundedStar
    if conn_f == WindingType.Delta and conn_y_to:  # Dy
        phase_displacement = np.deg2rad(60.0)
    elif conn_y_from and conn_t == WindingType.Delta:  # Yd
        phase_displacement = np.deg2rad(0.0)
    else:
        phase_displacement = 0.0

    theta_hk = vaf - vat
    block = Block(
        algebraic_vars=[Pf, Pt, Qf, Qt, Im],
        algebraic_eqs=[
            # From side: Pf = Re(Vf * (Yff*Vf + Yft*Vt)*)
            vmt - vdc*am*k,
            Pf - ((vmf ** 2 * (gFe + gt)) / (m * vtap_f) ** 2 - gt / (m * vtap_f * vtap_t) * vmf * vmt * sym.cos(
                theta_hk - phi) - bt / (m * vtap_f * vtap_t) * vmf * vmt * sym.sin(
                theta_hk - phi - phase_displacement)),
            Qf - (-vmf ** 2 * (bmu / 2 + bt) / (m * vtap_f) ** 2 - gt / (m * vtap_f * vtap_t) * vmf * vmt * sym.sin(
                theta_hk - phi) + bt / (m * vtap_f * vtap_t) * vmf * vmt * sym.cos(
                theta_hk - phi - phase_displacement)),

            # To side: Pt = Re(Vt * (Ytf*Vf + Ytt*Vt)*)
            Pt - ((vmt ** 2 * (gFe + gt)) / vtap_t ** 2 - gt / (m * vtap_f * vtap_t) * vmt * vmf * sym.cos(
                theta_hk - phi) + bt / (m * vtap_f * vtap_t) * vmt * vmf * sym.sin(
                theta_hk - phi - phase_displacement)),
            Qt - (-vmt ** 2 * (bmu / 2 + bt) / vtap_t ** 2 + gt / (m * vtap_f * vtap_t) * vmt * vmf * sym.sin(
                theta_hk - phi) + bt / (m * vtap_f * vtap_t) * vmt * vmf * sym.cos(
                theta_hk - phi - phase_displacement)),
            
            Im - sym.sqrt(Pt**2 + Qt**2)/vmf,
            (vat) - (vaf + phi0 + phi),
        ],
        init_eqs={
            am: vmt/k*vdc,
            Im: sym.sqrt(Pt**2 + Qt**2)/vmf,
        },
        event_dict={
            m      : vf.add_const(trafo.tap_module),
            P_ref   : Pf,
            phi0   : vat - vaf,
        },
        in_vars=inputs,
    )
    block.children.append(control_block)

    block.external_mapping = {
        VarPowerFlowReferenceType.Vaf: vaf,
        VarPowerFlowReferenceType.Vat: vat,
        VarPowerFlowReferenceType.Vmf: vmf,
        VarPowerFlowReferenceType.Vmt: vmt,
        VarPowerFlowReferenceType.Pf: Pf,
        VarPowerFlowReferenceType.Pt: Pt,
        VarPowerFlowReferenceType.Qf: Qf,
        VarPowerFlowReferenceType.Qt: Qt,
    }

    block.api_obj_mapping = {
        ParamPowerFlowReferenceType.g: gt,
        ParamPowerFlowReferenceType.b: bt,
        ParamPowerFlowReferenceType.bsh: bmu,
    }
    block.parameters = {
        gt:vf.add_const(ys.real),
        bt:vf.add_const(ys.imag),
        gFe:vf.add_const(ysh.real),
        bmu:vf.add_const(ysh.imag)
    }

    block.out_vars = [Im, Pt]
    templ.block = block
    return templ
