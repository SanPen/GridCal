# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.enumerations import ParamPowerFlowReferenceType, VarPowerFlowReferenceType, DeviceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate


def get_load_phasor_current_rms_template(
        vfactory: VarFactory,
        name: str = "Load phasor current RMS template",
) -> RmsModelTemplate:
    """
    Get the RMS template model of the load in current-balance phasor coordinates.

    This model behaves as a constant-power load (not a current source):
    - P = Pl0
    - Q = Ql0
    - I = conj(S / V), with S = P + jQ and V = Vr + jVi

    Sign convention follows the rest of the RMS templates:
    load consumption is represented with negative injections (Pl0 < 0, Ql0 < 0).
    
    :param vfactory: Variable factory for creating variables
    :param name: Name of the template
    :return: RmsModelTemplate with voltage-dependent load current model
    """
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name

    # Phasor inputs: Vr, Vi
    inputs = [
        vfactory.add_var("Vr", VarPowerFlowReferenceType.Vr),
        vfactory.add_var("Vi", VarPowerFlowReferenceType.Vi)
    ]

    # Constant power set-points (injection convention)
    Pl0 = vfactory.add_var("Pl0")
    Ql0 = vfactory.add_var("Ql0")

    # Current injection variables solved from terminal voltage and P/Q
    Ir = vfactory.add_var("Ir")
    Ii = vfactory.add_var("Ii")
    vr_aux = vfactory.add_var("vr_aux")
    vi_aux = vfactory.add_var("vi_aux")

    # Load.P/Q is the exclusive initial source. Runtime storage remains mutable
    # so scheduled events can replace either set-point after initialization.
    templ.block.event_dict[Pl0] = vfactory.add_const(None)
    templ.block.event_dict[Ql0] = vfactory.add_const(None)

    templ.block.algebraic_vars = [Ir, Ii, vr_aux, vi_aux]
    

    vr = inputs[0]
    vi = inputs[1]
    v2 = vr*vr_aux + vi*vi_aux
    # I = conj(S / V), written without division
    templ.block.algebraic_eqs = [
        vr_aux - vr,
        vi_aux - vi,
        Ir * v2 - (Pl0 * vr + Ql0 * vi),
        Ii * v2 - (Pl0 * vi - Ql0 * vr),
    ]

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.Vr: inputs[0],
        VarPowerFlowReferenceType.Vi: inputs[1],
        VarPowerFlowReferenceType.Ir: Ir,
        VarPowerFlowReferenceType.Ii: Ii
    }

    templ.block.api_obj_mapping = {
        ParamPowerFlowReferenceType.Pl0: Pl0,
        ParamPowerFlowReferenceType.Ql0: Ql0,
    }

    templ.block.init_eqs = {
        vr_aux: vr,
        vi_aux: vi,
    }

    templ.block.out_vars = [Ir, Ii]
    templ.block.in_vars = inputs

    templ.comment = 'Load RMS constant-power phasor-current model'
    return templ
