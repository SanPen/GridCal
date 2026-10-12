# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowReferenceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import VarPowerFlowReferenceType, Block
from VeraGridEngine.Utils.Symbolic.symbolic import cos, sin, exp, imag, log, conj, real, abs


def get_genrow_rms_template(vfactory: VarFactory, name="Genrow rms template") -> RmsModelTemplate:
    """
    Get the RMS template model of the Genrow
    :return: RmsModelTemplate
    """
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name

    inputs = [vfactory.add_var("Vm", reference=VarPowerFlowReferenceType.Vm),
              vfactory.add_var("Va", reference=VarPowerFlowReferenceType.Va)]

    P_g = vfactory.add_var('P_g', reference=VarPowerFlowReferenceType.P)
    Q_g = vfactory.add_var('Q_g', reference=VarPowerFlowReferenceType.Q)

    delta = vfactory.add_var("delta")
    omega = vfactory.add_var("omega")
    psid = vfactory.add_var("psid")
    psiq = vfactory.add_var("psiq")
    i_d = vfactory.add_var("i_d")
    i_q = vfactory.add_var("i_q")
    v_d = vfactory.add_var("v_d")
    v_q = vfactory.add_var("v_q")
    te = vfactory.add_var("te")
    et = vfactory.add_var("et")
    tm = vfactory.add_var("tm")

    # Parameters
    R1 = vfactory.add_var("R1")
    X1 = vfactory.add_var("X1")
    freq = vfactory.add_var("frequ")
    M = vfactory.add_var("M")
    D = vfactory.add_var("D")
    omega_ref = vfactory.add_var("omega_ref")
    Kp = vfactory.add_var("Kp")
    Ki = vfactory.add_var("Ki")

    vf = vfactory.add_var("vf")
    tm0 = vfactory.add_var("tm0")

    block = Block()
    block.name = name

    block.parameters[R1] = vfactory.add_const(0.3)
    block.parameters[X1] = vfactory.add_const(0.86138701)
    block.parameters[freq] = vfactory.add_const(50.0)
    block.event_dict[M] = vfactory.add_const(4.0)
    block.event_dict[D] = vfactory.add_const(1.0)
    block.event_dict[omega_ref] = vfactory.add_const(1.0)
    block.event_dict[Kp] = vfactory.add_const(0.0)
    block.event_dict[Ki] = vfactory.add_const(0.0)
    block.event_dict[vf] = psid + X1 * i_d
    block.event_dict[tm0] = tm

    block.algebraic_vars = [P_g, Q_g, v_d, v_q, i_d, i_q, psid, psiq, te, tm, et]

    block.algebraic_eqs = [
        psid - (R1 * i_q + v_q),
        psiq + (R1 * i_d + v_d),
        0 - (psid + X1 * i_d - vf),
        0 - (psiq + X1 * i_q),
        v_d - (inputs[0] * sin(delta - inputs[1])),
        v_q - (inputs[0] * cos(delta - inputs[1])),
        te - (psid * i_q - psiq * i_d),
        P_g - (v_d * i_d + v_q * i_q),
        Q_g - (v_q * i_d - v_d * i_q),
        tm - (tm0 + Kp * (omega - omega_ref) + Ki * et),
        2 * np.pi * freq * et - delta,
    ]

    block.state_vars = [delta, omega]
    block.state_eqs = [
        (2 * np.pi * freq) * (omega - omega_ref),
        (tm - te - D * (omega - omega_ref)) / M,
    ]

    block.init_eqs = {
        delta: imag(
            log((inputs[0] * exp(1j * inputs[1]) + (R1 + 1j * X1) * (
                conj((P_g + 1j * Q_g) / (inputs[0] * exp(1j * inputs[1]))))) / (
                    abs(inputs[0] * exp(1j * inputs[1]) + (R1 + 1j * X1) * (
                        conj((P_g + 1j * Q_g) / (inputs[0] * exp(1j * inputs[1])))))))),
        omega: omega_ref,
        v_d: real((inputs[0] * exp(1j * inputs[1])) * exp(-1j * (delta - np.pi / 2))),
        v_q: imag((inputs[0] * exp(1j * inputs[1])) * exp(-1j * (delta - np.pi / 2))),
        i_d: real(
            conj((P_g + 1j * Q_g) / (inputs[0] * exp(1j * inputs[1]))) * exp(-1j * (delta - np.pi / 2))),
        i_q: imag(
            conj((P_g + 1j * Q_g) / (inputs[0] * exp(1j * inputs[1]))) * exp(-1j * (delta - np.pi / 2))),
        psid: R1 * i_q + v_q,
        psiq: -R1 * i_d - v_d,
        te: psid * i_q - psiq * i_d,
        tm: te,
        et: delta / (2 * np.pi * freq),
    }

    block.in_vars = inputs
    block.out_vars = [P_g, Q_g]

    templ.block.children.append(block)

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.Vm: inputs[0],
        VarPowerFlowReferenceType.Va: inputs[1],
        VarPowerFlowReferenceType.P: P_g,
        VarPowerFlowReferenceType.Q: Q_g
    }

    # Static generator mappings stay on the physical model block which declares
    # their parameter targets. Recursive initialization reaches this child
    # directly, so the editor-owned root only needs the external interface.
    block.api_obj_mapping = {
        # Electrical parameters
        ParamPowerFlowReferenceType.R1: R1,
        ParamPowerFlowReferenceType.X1: X1,
        ParamPowerFlowReferenceType.freq: freq,
    }

    templ.block.in_vars = inputs
    templ.block.out_vars = [P_g, Q_g]

    templ.comment = 'Generator GENROU/GENROW RMS model'
    return templ
