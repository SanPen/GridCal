# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List
import numpy as np

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowReferenceType, VarPowerFlowReferenceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.symbolic import Var


def get_line_phasor_rms_template(vfactory: VarFactory, name="Line_phasor_rms_template") -> RmsModelTemplate:
    """
    Get the phasor-based RMS template model of the Line using current balance.
    
    This template uses phasor representation (Vr, Vi) for voltages and outputs
    currents directly for current balance equations:
    - Current: I = Y * (Vf - Vt) + Ysh * V
    
    Where V = Vr + j*Vi and Y = g + j*b
    
    :param vfactory: Variable factory for creating variables
    :param name: Name of the template
    :return: RmsModelTemplate with phasor-based line current equations
    """
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.LineDevice
    templ.name = name

    # Inputs: phasor voltages at from and to buses
    inputs: List[Var] = [vfactory.add_var("Vrf", VarPowerFlowReferenceType.Vrf),
                         vfactory.add_var("Vif", VarPowerFlowReferenceType.Vif),
                         vfactory.add_var("Vrt", VarPowerFlowReferenceType.Vrt),
                         vfactory.add_var("Vit", VarPowerFlowReferenceType.Vit)]

    # Outputs: currents (for current balance formulation)
    Irf = vfactory.add_var("Irf")
    Iif = vfactory.add_var("Iif")
    Irt = vfactory.add_var("Irt")
    Iit = vfactory.add_var("Iit")

    # Parameters: line admittance
    g = vfactory.add_var("g")
    b = vfactory.add_var("b")
    bsh = vfactory.add_var("bsh")
    gsh: Var = vfactory.add_var("gsh")
    vtap_f = vfactory.add_var("vtap_f")
    vtap_t = vfactory.add_var("vtap_t")

    # Set default parameter values
    templ.block.parameters[g] = vfactory.add_const(5)
    templ.block.parameters[b] = vfactory.add_const(-12)
    templ.block.parameters[bsh] = vfactory.add_const(0.03)
    templ.block.parameters[gsh] = vfactory.add_const(0.0)
    templ.block.parameters[vtap_f] = vfactory.add_const(None)
    templ.block.parameters[vtap_t] = vfactory.add_const(None)

    templ.block.algebraic_vars = [Irf, Iif, Irt, Iit]

    # Voltage variables
    Vrf = inputs[0]
    Vif = inputs[1]
    Vrt = inputs[2]
    Vit = inputs[3]
    
    # Apply existing virtual taps to both the series and physical half-shunt.
    gff = (g + gsh / 2) / (vtap_f * vtap_f)
    bff = (b + bsh / 2) / (vtap_f * vtap_f)
    gtt = (g + gsh / 2) / (vtap_t * vtap_t)
    btt = (b + bsh / 2) / (vtap_t * vtap_t)
    gft = -g / (vtap_f * vtap_t)
    bft = -b / (vtap_f * vtap_t)

    # Direct current output equations with virtual taps
    templ.block.algebraic_eqs = [
        Irf - (gff * Vrf - bff * Vif + gft * Vrt - bft * Vit),
        Iif - (bff * Vrf + gff * Vif + bft * Vrt + gft * Vit),
        Irt - (gft * Vrf - bft * Vif + gtt * Vrt - btt * Vit),
        Iit - (bft * Vrf + gft * Vif + btt * Vrt + gtt * Vit),
    ]

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.Vrf: inputs[0],
        VarPowerFlowReferenceType.Vif: inputs[1],
        VarPowerFlowReferenceType.Vrt: inputs[2],
        VarPowerFlowReferenceType.Vit: inputs[3],
        VarPowerFlowReferenceType.Irf: Irf,
        VarPowerFlowReferenceType.Iif: Iif,
        VarPowerFlowReferenceType.Irt: Irt,
        VarPowerFlowReferenceType.Iit: Iit,
    }

    templ.block.api_obj_mapping = {
        ParamPowerFlowReferenceType.g: g,
        ParamPowerFlowReferenceType.b: b,
        ParamPowerFlowReferenceType.bsh: bsh,
        ParamPowerFlowReferenceType.shunt_g_pu: gsh,
        ParamPowerFlowReferenceType.vtap_f: vtap_f,
        ParamPowerFlowReferenceType.vtap_t: vtap_t,
    }

    templ.block.in_vars = inputs

    templ.comment = 'AC line RMS phasor-current model'
    return templ
