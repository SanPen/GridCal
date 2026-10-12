# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowReferenceType, ParamPowerFlowReferenceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate



def get_genrow1_rms_template(var_factory: VarFactory, name="Genrow rms template") -> RmsModelTemplate:
    """
    Get the RMS template model of the Genrow
    :return: RmsModelTemplate
    """
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name

    inputs = [var_factory.add_var("Vm", reference=VarPowerFlowReferenceType.Vm),
              var_factory.add_var("Va", reference=VarPowerFlowReferenceType.Va)]

    P_g = var_factory.add_var('P_g')
    Q_g = var_factory.add_var('Q_g')

    delta = var_factory.add_var("delta")
    omega = var_factory.add_var("omega")
    psid = var_factory.add_var("psid")
    psiq = var_factory.add_var("psiq")
    i_d = var_factory.add_var("i_d")
    i_q = var_factory.add_var("i_q")
    v_d = var_factory.add_var("v_d")
    v_q = var_factory.add_var("v_q")
    te = var_factory.add_var("te")
    et = var_factory.add_var("et")
    tm = var_factory.add_var("tm")

    R1 = var_factory.add_var("R1")
    X1 = var_factory.add_var("X1")
    freq = var_factory.add_var("frequ")
    M = var_factory.add_var("M")
    D = var_factory.add_var("D")
    omega_ref = var_factory.add_var("omega_ref")
    Kp = var_factory.add_var("Kp")
    Ki = var_factory.add_var("Ki")

    vf = var_factory.add_var("vf")
    tm0 = var_factory.add_var("tm0")

    templ.block.parameters[R1] = var_factory.add_const(0.0)
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.R1] = R1
    templ.block.parameters[X1] = var_factory.add_const(0.3 * 100.0 / 900.0)
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.X1] = X1
    templ.block.parameters[freq] = var_factory.add_const(60.0)
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.freq] = freq
    templ.block.event_dict[M] = var_factory.add_const(13.0 * 9.0)
    templ.block.event_dict[D] = var_factory.add_const(10.0 * 9.0)
    templ.block.event_dict[omega_ref] = var_factory.add_const(1.0)
    templ.block.event_dict[Kp] = var_factory.add_const(0.0)
    templ.block.event_dict[Ki] = var_factory.add_const(0.0)
    templ.block.event_dict[vf] = psid + X1 * i_d
    templ.block.event_dict[tm0] = tm

    templ.block.algebraic_vars = [P_g, Q_g, v_d, v_q, i_d, i_q, psid, psiq, te, tm, et]

    templ.block.algebraic_eqs = [
        psid - (R1 * i_q + v_q),
        psiq + (R1 * i_d + v_d),
        0 - (psid + X1 * i_d - vf),
        0 - (psiq + X1 * i_q),
        v_d - (inputs[0] * sym.sin(delta - inputs[1])),
        v_q - (inputs[0] * sym.cos(delta - inputs[1])),
        te - (psid * i_q - psiq * i_d),
        P_g - (v_d * i_d + v_q * i_q),
        Q_g - (v_q * i_d - v_d * i_q),
        tm - (tm0 + Kp * (omega - omega_ref) + Ki * et),
        2 * np.pi * freq * et - delta,
    ]

    templ.block.state_vars = [delta, omega]
    templ.block.state_eqs = [
        (2 * np.pi * freq) * (omega - omega_ref),
        (tm - te - D * (omega - omega_ref)) / M,
    ]

    templ.block.init_eqs = {
        delta: sym.imag(
            sym.log((inputs[0] * sym.exp(1j * inputs[1]) + (R1 + 1j * X1) * (
                sym.conj((P_g + 1j * Q_g) / (inputs[0] * sym.exp(1j * inputs[1]))))) / (
                        sym.abs(inputs[0] * sym.exp(1j * inputs[1]) + (R1 + 1j * X1) * (
                            sym.conj((P_g + 1j * Q_g) / (inputs[0] * sym.exp(1j * inputs[1])))))))),
        omega: omega_ref,
        v_d: sym.real((inputs[0] * sym.exp(1j * inputs[1])) * sym.exp(-1j * (delta - np.pi / 2))),
        v_q: sym.imag((inputs[0] * sym.exp(1j * inputs[1])) * sym.exp(-1j * (delta - np.pi / 2))),
        i_d: sym.real(
            sym.conj((P_g + 1j * Q_g) / (inputs[0] * sym.exp(1j * inputs[1]))) * sym.exp(-1j * (delta - np.pi / 2))),
        i_q: sym.imag(
            sym.conj((P_g + 1j * Q_g) / (inputs[0] * sym.exp(1j * inputs[1]))) * sym.exp(-1j * (delta - np.pi / 2))),
        psid: R1 * i_q + v_q,
        psiq: -R1 * i_d - v_d,
        te: psid * i_q - psiq * i_d,
        tm: te,
        et: delta / (2 * np.pi * freq),
    }

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.Vm: inputs[0],
        VarPowerFlowReferenceType.Va: inputs[1],
        VarPowerFlowReferenceType.P: P_g,
        VarPowerFlowReferenceType.Q: Q_g
    }

    templ.block.in_vars = inputs
    templ.block.out_vars = [P_g, Q_g]

    templ.comment = 'Generator GENROW1 RMS model'
    return templ
