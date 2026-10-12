# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0



from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowReferenceType, VarPowerFlowReferenceType
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block

"""
EMT DC load template.

The load follows the EMT injection convention used by the rest of the
framework: current and power are positive when entering the bus. A consuming DC
load therefore has negative ``i_dc`` and negative ``p_dc``.
"""

def get_dc_load_emt_template(
    vf: VarFactory,
    name: str = "dc_load_emt_template"
) -> EmtModelTemplate:
    """
    Build an EMT DC load model.

    Device-backed initial values are provided through ``api_obj_mapping``.
    Active power remains event-capable, while conductance is immutable.

    Args:
        vf: Variable factory
        name: Name for the model

    Returns:
        EmtModelTemplate with the DC load block
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name

    p_dc_static = vf.add_var(name=f"Pl0")
    g_dc_static = vf.add_var(name=f"g")
    block = Block()
    # DC power can receive scheduled events after its device-backed baseline is
    # resolved. Conductance remains a fixed physical parameter.
    block.event_dict[p_dc_static] = vf.add_const(None)
    block.parameters[g_dc_static] = vf.add_const(None)

    v_dc = vf.add_var(name=f"v_dc", reference=VarPowerFlowReferenceType.Vdc)

    i_dc = vf.add_var(name=f"i_dc", reference=VarPowerFlowReferenceType.Idc)
    p_dc = vf.add_var(name=f"p_dc", reference=VarPowerFlowReferenceType.P)

    block.in_vars = [v_dc]
    block.algebraic_vars = [i_dc, p_dc]

    eps = vf.add_const(1e-10)
    block.algebraic_eqs = [
        i_dc + p_dc_static / (v_dc + eps) + g_dc_static * v_dc,
        p_dc - v_dc * i_dc,
    ]

    block.out_vars = [i_dc]

    block.external_mapping = {
        VarPowerFlowReferenceType.Vdc: v_dc,
        VarPowerFlowReferenceType.Idc: i_dc,
        VarPowerFlowReferenceType.P: p_dc,
    }

    block.api_obj_mapping = {
        ParamPowerFlowReferenceType.Pl0: p_dc_static,
        ParamPowerFlowReferenceType.g: g_dc_static,
    }

    block.init_eqs = {
        i_dc: -(p_dc_static / (v_dc + eps) + g_dc_static * v_dc),
        p_dc: -v_dc * (p_dc_static / (v_dc + eps) + g_dc_static * v_dc),
    }

    templ.block.children.append(block)
    templ.block.external_mapping = block.external_mapping
    templ.block.in_vars = block.in_vars
    templ.block.out_vars = block.out_vars
    return templ
