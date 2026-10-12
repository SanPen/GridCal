# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Alternative complete generator RMS template with explicit controller states.

This module keeps the generator model from the original template and only
rebuilds the controller sections with explicit state equations so the
small-signal DAE formulation exposes the controller modes as finite
eigenvalues.
"""

from __future__ import annotations
import math

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import OELBuild as OELBuildBase
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.enumerations import ParamPowerFlowReferenceType
from VeraGridEngine.enumerations import VarPowerFlowReferenceType

def get_genqec_rms(vfactory: VarFactory, name: str = "Genqec_rms_template") -> RmsModelTemplate:
    """
     generator with quadratic saturation
     :return: RmsModelTemplate
    """
    pi = math.pi

    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name

    # Inputs
    # Vm: Bus voltage module
    # Va: Bus voltage angle
    # Tm: mechanical torque (from governor)
    # Vf: excitation voltage (from exciter)

    inputs = [vfactory.add_var("Vm", reference=VarPowerFlowReferenceType.Vm),
              vfactory.add_var("Va", reference=VarPowerFlowReferenceType.Va),
              vfactory.add_var("Tm", shared_reference="tm_reference"),
              vfactory.add_var("Vf", shared_reference="vf_reference")]

    # ______________________________________________________________________________________
    #                                    variables
    # ______________________________________________________________________________________

    # State variables
    delta = vfactory.add_var("delta")  # rotor angle
    omega = vfactory.add_var("omega", shared_reference="omega_reference")  # rotor electrical speed
    Eq1 = vfactory.add_var("Eq1")  # internal emf behind Xd'
    Ed1 = vfactory.add_var("Ed1")
    Eq_prime = vfactory.add_var("Eq_prime")  # transient voltage q-axis
    Ed_prime = vfactory.add_var("Ed_prime")  # transient voltage d-axis
    Psid_prime = vfactory.add_var("Psid_prime")  # transient voltage d-axis
    Psiq_prime = vfactory.add_var("Psiq_prime")  # transient voltage d-axis

    # Algebraic variables
    Pg = vfactory.add_var('Pg', reference=VarPowerFlowReferenceType.P)
    Qg = vfactory.add_var('Qg', reference=VarPowerFlowReferenceType.Q)
    Id = vfactory.add_var("Id")
    Iq = vfactory.add_var("Iq")
    Vd = vfactory.add_var("Vd")
    Vq = vfactory.add_var("Vq")
    Psid = vfactory.add_var("Psid")
    Psiq = vfactory.add_var("Psiq")
    Te = vfactory.add_var("Te", shared_reference="te_reference")
    IRPu = vfactory.add_var("IRPu", shared_reference="irpu_reference")

    # Saturated resistances
    Xd_2prime_sat = vfactory.add_var('Xd_2prime_sat')
    Xq_2prime_sat = vfactory.add_var('Xq_2prime_sat')
    Sa = vfactory.add_var('Sa')
    Sat = vfactory.add_var('Sat')
    V_qag = vfactory.add_var('V_qag')
    V_dag = vfactory.add_var('V_dag')
    Psi_ag = vfactory.add_var('Psi_ag')

    # ______________________________________________________________________________________
    #                                    parameters
    # ______________________________________________________________________________________
    fn = vfactory.add_var('fn')  # system frequency [Hz]
    ws = vfactory.add_var('ws')  # synchronous speed [rad/s]
    M = vfactory.add_var('M')  # inertia constant
    D = vfactory.add_var('D')  # damping (optional)
    Rs = vfactory.add_var('Rs')  # stator resistance
    Ra = vfactory.add_var('Ra')  # armature resistance (if distinct)

    # Reactances
    Xd = vfactory.add_var('Xd')
    Xq = vfactory.add_var('Xq')
    Xd_prime = vfactory.add_var('Xd_prime')
    Xq_prime = vfactory.add_var('Xq_prime')
    Xd_2prime = vfactory.add_var('Xd_2prime')
    Xq_2prime = vfactory.add_var('Xq_2prime')
    Xl = vfactory.add_var('Xl')

    # Time constants
    Td0_prime = vfactory.add_var('Td0_prime')
    Tq0_prime = vfactory.add_var('Tq0_prime')
    Td0_2prime = vfactory.add_var('Td0_2prime')
    Tq0_2prime = vfactory.add_var('Tq0_2prime')

    # Auxiliary expressions
    Viag_expr = inputs[0] * sym.sin(inputs[1]) + sym.imag(
        sym.conj(Pg + 1j * Qg) / sym.conj(inputs[0] * sym.exp(1j * inputs[1]))) * Ra + sym.real(
        sym.conj(Pg + 1j * Qg) / sym.conj(inputs[0] * sym.exp(1j * inputs[1]))) * Xl
    Vrag_expr = inputs[0] * sym.cos(inputs[1]) + sym.real(
        sym.conj(Pg + 1j * Qg) / sym.conj(inputs[0] * sym.exp(1j * inputs[1]))) * Ra - sym.imag(
        sym.conj(Pg + 1j * Qg) / sym.conj(inputs[0] * sym.exp(1j * inputs[1]))) * (Xl)

    A = vfactory.add_var('A')
    B = vfactory.add_var("B")
    Xd_prime_minus_Xl = vfactory.add_var('Xd_prime_minus_Xl')
    Xq_prime_minus_Xl = vfactory.add_var('Xq_prime_minus_Xl')
    Xdaux = vfactory.add_var('Xdaux')
    Xdaux2 = vfactory.add_var('Xdaux2')
    Xdaux3 = vfactory.add_var('Xdaux3')

    Xqaux = vfactory.add_var('Xqaux')
    Xqaux2 = vfactory.add_var('Xqaux2')
    Xqaux3 = vfactory.add_var('Xqaux3')

    event_dict = {
        M: vfactory.add_const(3.5),
        D: vfactory.add_const(10.0),
        Rs: vfactory.add_const(0.003),
        Ra: vfactory.add_const(0.003),

        # Reactances
        Xd: vfactory.add_const(1.8),
        Xq: vfactory.add_const(1.7),
        Xd_prime: vfactory.add_const(0.3),
        Xq_prime: vfactory.add_const(0.55),
        Xd_2prime: vfactory.add_const(0.25),
        Xq_2prime: vfactory.add_const(0.35),
        Xl: vfactory.add_const(0.15),

        # Time constants
        Td0_prime: vfactory.add_const(8.0),
        Tq0_prime: vfactory.add_const(0.4),
        Td0_2prime: vfactory.add_const(0.03),
        Tq0_2prime: vfactory.add_const(0.05),

        Xd_prime_minus_Xl: Xd_prime - Xl,
        Xq_prime_minus_Xl: Xq_prime - Xl,
        Xdaux: ((Xd_prime - Xd_2prime) / (((Xd_prime - Xl) ** 2) + sym.Const(1e-12))),
        Xdaux2: ((Xd_prime - Xd_2prime) / ((Xd_prime - Xl) + sym.Const(1e-12))),
        Xdaux3: ((Xd_2prime - Xl) / ((Xd_prime - Xl) + sym.Const(1e-12))),
        Xqaux: ((Xq_prime - Xq_2prime) / (((Xq_prime - Xl) ** 2) + sym.Const(1e-12))),
        Xqaux2: (Xq_prime - Xq_2prime) / ((Xq_prime - Xl) + sym.Const(1e-12)),
        Xqaux3: ((Xq_2prime - Xl) / ((Xq_prime - Xl) + sym.Const(1e-12))),
        A: vfactory.add_const(5.0),
        B: vfactory.add_const(1.0)
    }
    # Xdaux = ((Xd_prime - Xd_2prime) / (Xd_prime_minus_Xl) ** 2).simplify()
    # Xdaux2 = ((Xd_prime - Xd_2prime) / (Xd_prime_minus_Xl)).simplify()
    # Xdaux3 = ((Xd_2prime - Xl) / (Xd_prime_minus_Xl)).simplify()
    #
    # Xqaux = ((Xq_prime - Xq_2prime) / (Xq_prime_minus_Xl) ** 2).simplify()
    # Xqaux2 = ((Xq_prime - Xq_2prime) / (Xq_prime_minus_Xl)).simplify()
    # Xqaux3 = ((Xq_2prime - Xl) / (Xq_prime_minus_Xl)).simplify()

    Eq_2prime_expr = Psid_prime * Xdaux2 + Eq_prime * Xdaux3
    Ed_2prime_expr = Psiq_prime * Xqaux2 + Ed_prime * Xqaux3
    Iq_sat = vfactory.add_var('Iq_sat')
    Id_sat = vfactory.add_var('Id_sat')
    # Sat = 1 + Sa
    # Xd_2prime_sat = (Xd_2prime - Xl)/Sat + Xl
    # Xq_2prime_sat = (Xq_2prime - Xl)/Sat + Xl

    block = Block(
        state_eqs=[
            (omega - vfactory.add_const(1)) * ws,  # dδ/dt
            (inputs[2] - Te - D * (omega - vfactory.add_const(1))) * (1 / M),  # dω/dt
            (inputs[3] - Sat * Eq1) / Td0_prime,  # dEq'/dt
            -Sat * Ed1 / Tq0_prime,  # dEd'/dt
            (-Psiq_prime + Iq_sat * Xq_prime_minus_Xl + Ed_prime),  # dPsiq'/dt
            (-Psid_prime - Id_sat * Xd_prime_minus_Xl + Eq_prime),  # dPsid'/dt
        ],
        state_vars=[delta, omega, Eq_prime, Ed_prime, Psiq_prime, Psid_prime],
        algebraic_eqs=[
            Vd - (-inputs[0] * sym.sin(inputs[1] - delta)),  # from input block
            Vq - (inputs[0] * sym.cos(inputs[1] - delta)),  # from input block
            Pg - (Vd * Id + Vq * Iq),  # from input block
            Qg - (Vq * Id - Vd * Iq),  # from input block
            Vd - (omega * Ed_2prime_expr + Iq * Xq_2prime_sat - Id * Ra),
            Vq - (omega * Eq_2prime_expr - Id * Xd_2prime_sat - Iq * Ra),
            Psid - (Eq_2prime_expr - Id * Xd_2prime_sat),
            Psiq - (-Ed_2prime_expr - Iq * Xq_2prime_sat),
            Te - (Psid * Iq - Psiq * Id),

            Ed1 - (Ed_prime - (Xq - Xq_prime) * (
                    Iq_sat - (Ed_prime - Psiq_prime + Iq_sat * (Xq_prime_minus_Xl)) * Xqaux)),
            Eq1 - (Eq_prime + (Xd - Xd_prime) * (
                    Id_sat + (Eq_prime - Psid_prime - Id_sat * (Xd_prime_minus_Xl)) * Xdaux)),

            # saturated resistance
            Sat - (vfactory.add_const(1) + Sa),
            Id - Id_sat * Sat,
            Iq - Iq_sat * Sat,
            Sat * Xd_2prime_sat - (Xd_2prime + Xl * Sa),
            Sat * Xq_2prime_sat - (Xq_2prime + Xl * Sa),

            # flux
            V_dag - (Vd + Id * Ra - Iq * Xl),
            V_qag - (Vq + Iq * Ra + Id * Xl),
            omega * Psi_ag - sym.sqrt(V_qag * V_qag + V_dag * V_dag),
            # saturations (quadratic)
            Sa - A / 2 * ((Psi_ag - B) + sym.sqrt((Psi_ag - B) ** 2 + vfactory.add_const(1e-5))) ** 2,

            # Eq1, Eq2, Ed1, Ed2 exciter
            IRPu - Eq1 * Sat,
        ],
        algebraic_vars=[Pg, Qg, Vd, Vq, Psid, Psiq, Te, Ed1, Eq1, Id, Iq,
                        # saturated resistance
                        Xq_2prime_sat, Xd_2prime_sat, Id_sat, Iq_sat,
                        # flux
                        Sa, Sat, V_dag, V_qag, Psi_ag,
                        IRPu],
        init_eqs={
            # Air Gap Voltages and delta
            omega: vfactory.add_const(1),
            Psi_ag: sym.sqrt(Viag_expr ** 2 + Vrag_expr ** 2),
            Sa: A / 2 * ((Psi_ag - B) + sym.sqrt((Psi_ag - B) ** 2 + vfactory.add_const(1e-5))) ** 2,
            Sat: vfactory.add_const(1) + Sa,
            delta: sym.atan(
                (inputs[0] * sym.sin(inputs[1]) + sym.imag(
                    sym.conj(Pg + 1j * Qg) / sym.conj(inputs[0] * sym.exp(1j * inputs[1]))) * Ra + sym.real(
                    sym.conj(Pg + 1j * Qg) / sym.conj(inputs[0] * sym.exp(1j * inputs[1]))) *
                 ((Xq - Xl) / (vfactory.add_const(1) + Sa) + Xl)) /
                (inputs[0] * sym.cos(inputs[1]) + sym.real(
                    sym.conj(Pg + 1j * Qg) / sym.conj(inputs[0] * sym.exp(1j * inputs[1]))) * Ra - sym.imag(
                    sym.conj(Pg + 1j * Qg) / sym.conj(inputs[0] * sym.exp(1j * inputs[1]))) *
                 ((Xq - Xl) / (vfactory.add_const(1) + Sa) + Xl))),

            # Saturated Resistances
            Xd_2prime_sat: (Xd_2prime - Xl + Xl * Sat) / Sat,
            Xq_2prime_sat: (Xq_2prime - Xl + Xl * Sat) / Sat,

            # Terminal Voltages and Intensities in dq frame
            Vd: -(inputs[0] * sym.sin(inputs[1] - delta)),
            Vq: (inputs[0] * sym.cos(inputs[1] - delta)),
            Id: (Pg * Vd + Qg * Vq) / (Vd ** 2 + Vq ** 2),
            Iq: (Pg * Vq - Qg * Vd) / (Vd ** 2 + Vq ** 2),
            V_dag: (Vd + Id * Ra - Iq * Xl),
            V_qag: (Vq + Iq * Ra + Id * Xl),

            # We initialize the states Eq', Ed', Psid', Psiq'
            Psid_prime: (Vq + Xd_2prime_sat * Id + Ra * Iq) / omega - (Xd_2prime - Xl) * Id / Sat,
            Ed_prime: (Xq - Xq_prime) * Iq / Sat,
            Psiq_prime: (Xq - Xl) * Iq / Sat,
            Eq_prime: Psid_prime + (Xd_prime - Xl) * Id / Sat,
            Ed1: (Ed_prime - (Xq - Xq_prime) * (
                    Iq / Sat - (Ed_prime - Psiq_prime + Iq * (Xq_prime - Xl) / Sat) * Xqaux)),
            Eq1: (Eq_prime + (Xd - Xd_prime) * (
                    Id / Sat + (Eq_prime - Psid_prime - Id * (Xd_prime - Xl) / Sat) * Xdaux)),

            Psid: (Eq_2prime_expr - Id * Xd_2prime_sat),
            Psiq: (-Ed_2prime_expr - Iq * Xq_2prime_sat),
            Te: (Psid * Iq - Psiq * Id),

            IRPu: Eq1 * (1 + Sa),
            Iq_sat: Iq / Sat,
            Id_sat: Id / Sat,

            # We initialize some specific parameters:
        },
        external_mapping={
            VarPowerFlowReferenceType.P: Pg,
            VarPowerFlowReferenceType.Q: Qg,
            VarPowerFlowReferenceType.Vm: inputs[0],
            VarPowerFlowReferenceType.Va: inputs[1],
        },

        api_obj_mapping={ParamPowerFlowReferenceType.freq: fn, ParamPowerFlowReferenceType.omega_base: ws},

        out_vars=[Pg, Qg, omega, IRPu, Te],
        in_vars=inputs,
        event_dict=event_dict,
        name="genqec",
        parameters={fn: vfactory.add_const(50.0), ws: vfactory.add_const(2 * pi * 50)},
    )

    templ.block.children.append(block)
    templ.block.external_mapping = block.external_mapping
    templ.block.in_vars = inputs
    templ.block.out_vars = block.out_vars

    templ.comment = 'Generator GENQEC RMS model with quadratic saturation'
    return templ

def get_governor_rms(vfactory: VarFactory, name: str = "Governor") -> RmsModelTemplate:
    """Build the governor with explicit dynamic states.

    The original template relied on helper transfer-function blocks whose
    internal dynamics were stored as derivative variables attached to
    algebraic variables. The small-signal assembler only guarantees finite
    modes for explicit ``state_vars``. This version therefore rewrites every
    dynamic governor stage as an explicit first-order state.

    :param vfactory: Shared symbolic variable factory.
    :param name: Model name.
    :return: Governor RMS template.
    """
    templ: RmsModelTemplate = RmsModelTemplate(name=name)
    parameters: dict[str, object] = {
        # Time constants
        "T1": vfactory.add_const(1.0),  # governor time constant (s)
        "T2": vfactory.add_const(1.0),  # reheater time constant (s)
        "T3": vfactory.add_const(10.0),  # crossover time constant (s)
        "T4": vfactory.add_const(0.2),  # lead/lag constant (s)
        "T5": vfactory.add_const(0.5),  # lead/lag constant (s)
        "T6": vfactory.add_const(0.1),  # lead/lag constant (s)
        "T7": vfactory.add_const(0.05),  # lead/lag constant (s)

        # Steam fractions (distribution factors)
        "K1": vfactory.add_const(0.5),
        "K2": vfactory.add_const(0.5),
        "K3": vfactory.add_const(0.0),
        "K4": vfactory.add_const(0.0),
        "K5": vfactory.add_const(0.0),
        "K6": vfactory.add_const(0.0),
        "K7": vfactory.add_const(0.0),
        "K8": vfactory.add_const(0.0),
    }

    inputs: list[Var] = list()
    inputs.append(vfactory.add_var("omega_", shared_reference="omega_reference"))
    inputs.append(vfactory.add_var("Te_", shared_reference="te_reference"))

    Tm: Var = vfactory.add_var("Tm", shared_reference="tm_reference")
    et: Var = vfactory.add_var("et")
    Pm_ref: Var = vfactory.add_var("Pm_ref")
    y1: Var = vfactory.add_var("y_gov0")
    y2_1: Var = vfactory.add_var("y_gov1_rate")
    y2_2: Var = vfactory.add_var("y_gov1")
    y2_3: Var = vfactory.add_var("y2_3_gov")
    y3_1: Var = vfactory.add_var("y_gov2")
    y3_2: Var = vfactory.add_var("y_gov3")
    y3_3: Var = vfactory.add_var("y_gov4")
    y3_4: Var = vfactory.add_var("y_gov5")
    x1: Var = vfactory.add_var("x_gov0")

    K: Var = vfactory.add_var("K")
    Pmax: Var = vfactory.add_var("Pmax")
    Pmin: Var = vfactory.add_var("Pmin")
    Uc: Var = vfactory.add_var("Uc")
    Uo: Var = vfactory.add_var("Uo")
    T_aux: Var = vfactory.add_var("T_aux")
    Kp: Var = vfactory.add_var("Kp")
    Ki: Var = vfactory.add_var("Ki")
    omega_ref: Var = vfactory.add_var("omega_ref")
    p0: Var = vfactory.add_var("p0")
    P0: Var = vfactory.add_var("P0")

    events_dict: dict[Var, Expr] = dict()
    events_dict[Pm_ref] = inputs[1]
    events_dict[Kp] = vfactory.add_const(-0.01)
    events_dict[Ki] = vfactory.add_const(-0.01)
    events_dict[p0] = vfactory.add_const(1.0)
    events_dict[P0] = vfactory.add_const(0.01)
    events_dict[omega_ref] = vfactory.add_const(1.0)
    events_dict[K] = vfactory.add_const(10.0)
    events_dict[Uc] = vfactory.add_const(-0.5)
    events_dict[Uo] = vfactory.add_const(0.5)
    events_dict[T_aux] = vfactory.add_const(0.0)

    u1: Expr = inputs[0] - omega_ref
    lead_gain: Expr = parameters["T2"] / parameters["T1"]
    lag_gain: Expr = sym.Const(1.0) - lead_gain
    turbine_sum: Expr = (
        parameters["K1"] * y3_1
        + parameters["K2"] * y3_2
        + parameters["K3"] * y3_3
        + parameters["K4"] * y3_4
    )


    templ.block = Block(
        # The explicit state equations below force every controller dynamic stage
        # to appear in ``state_vars`` so the linearized DAE produces finite modes.
        state_eqs= [(u1 - x1) / parameters["T1"],
                    y2_1,
                    (y2_3 - y3_1) / parameters["T4"],
                    (y3_1 - y3_2) / parameters["T5"],
                    (y3_2 - y3_3) / parameters["T6"],
                    (y3_3 - y3_4) / parameters["T7"]
                    ],
        state_vars=[x1, y2_2, y3_1, y3_2, y3_3, y3_4],
        # The PI reference path is kept as an algebraic placeholder so the public
        # parameter mapping remains intact without changing the original behavior.
        algebraic_eqs=[y1 - (lead_gain * u1 + lag_gain * x1),
                       y2_1 - sym.hard_sat((Pm_ref - K * y1 - y2_3) / parameters["T3"], Uc, Uo),
                       y2_3 - sym.hard_sat(y2_2, Pmin, Pmax),
                       Tm - turbine_sum,
                       et - sym.Const(0.0)],
        algebraic_vars=[y1, y2_1, y2_3, Tm, et],
        out_vars=[Tm],
        in_vars=inputs,
        event_dict=events_dict,
        parameters={Pmax: vfactory.add_const(12.0), Pmin: vfactory.add_const(-1.0)},
        name="governor_v2",
    )

    init_eqs: dict[Var, Expr] = dict()
    init_eqs[x1] = u1
    init_eqs[y1] = u1
    init_eqs[y2_1] = sym.Const(0.0)
    init_eqs[y2_2] = Pm_ref
    init_eqs[y2_3] = Pm_ref
    init_eqs[y3_1] = Pm_ref
    init_eqs[y3_2] = Pm_ref
    init_eqs[y3_3] = Pm_ref
    init_eqs[y3_4] = Pm_ref
    init_eqs[Tm] = Pm_ref
    init_eqs[et] = sym.Const(0.0)
    templ.block.init_eqs = init_eqs

    api_obj_mapping: dict[ParamPowerFlowReferenceType, Var] = dict()
    api_obj_mapping[ParamPowerFlowReferenceType.Pmax] = Pmax
    api_obj_mapping[ParamPowerFlowReferenceType.Pmin] = Pmin
    templ.block.api_obj_mapping = api_obj_mapping

    templ.comment = 'Reusable generator governor RMS control block'
    return templ


def get_stabilizer_rms(vfactory: VarFactory, name: str = "stabilizer") -> RmsModelTemplate:
    """Build the PSS with explicit dynamic states.

    The stabilizer chain is rewritten in state-space form so the transducer,
    washout, second-order notch, and two lead-lag stages are all explicit
    states visible to the small-signal formulation.

    :param vfactory: Shared symbolic variable factory.
    :param name: Model name.
    :return: Stabilizer RMS template.
    """
    templ: RmsModelTemplate = RmsModelTemplate(name=name)

    parameters: dict[str, object] = {
        # Stabilizer parameters
        "A1": vfactory.add_const(1.0),  # notch filter coefficient 1
        "A2": vfactory.add_const(1.0),  # notch filter coefficient 2
        "t1": vfactory.add_const(0.1),  # lead time constant
        "t2": vfactory.add_const(0.02),  # lag time constant
        "t3": vfactory.add_const(0.02),  # lag time constant
        "t4": vfactory.add_const(0.1),  # second lag time constant
        "t5": vfactory.add_const(10.0),  # washout time constant
        "t6": vfactory.add_const(0.02),  # transducer time constant
    }

    inputs: list[Var] = list()
    inputs.append(vfactory.add_var("omega_", shared_reference="omega_reference"))

    Ks: Var = vfactory.add_var("Ks")
    VPssMaxPu: Var = vfactory.add_var("VPssMaxPu")
    VPssMinPu: Var = vfactory.add_var("VPssMinPu")
    SNom: Var = vfactory.add_var("SNom")

    events_dict: dict[Var, Expr] = dict()
    events_dict[Ks] = vfactory.add_const(20.0)
    events_dict[VPssMaxPu] = vfactory.add_const(1.0)
    events_dict[VPssMinPu] = vfactory.add_const(-1.0)
    events_dict[SNom] = vfactory.add_const(1.0)

    Vpss: Var = vfactory.add_var("V_pss", shared_reference="vpss_reference")
    y: Var = vfactory.add_var("y_stabilizer1")
    x_wash: Var = vfactory.add_var("x_stabilizer2")
    y2: Var = vfactory.add_var("y_stabilizer2")
    y3: Var = vfactory.add_var("y_stabilizer3")
    dy3_state: Var = vfactory.add_var("dy_stabilizer3")
    x4: Var = vfactory.add_var("x_stabilizer4")
    y4: Var = vfactory.add_var("y_stabilizer4")
    x5: Var = vfactory.add_var("x_stabilizer5")
    y5: Var = vfactory.add_var("y_stabilizer5")

    lead_gain_1: Expr = parameters["t1"] / parameters["t2"]
    lag_gain_1: Expr = sym.Const(1.0) - lead_gain_1
    lead_gain_2: Expr = parameters["t3"] / parameters["t4"]
    lag_gain_2: Expr = sym.Const(1.0) - lead_gain_2

    templ.block = Block(
        state_eqs=[(inputs[0] - y) / parameters["t6"],
                   (y - x_wash) / parameters["t5"],
                   dy3_state,
                   (y2 - y3 - parameters["A1"] * dy3_state) / parameters["A2"],
                   (y3 - x4) / parameters["t2"],
                   (y4 - x5) / parameters["t4"]],
        state_vars=[y, x_wash, y3, dy3_state, x4, x5],
        algebraic_eqs=[y2 - Ks * (y - x_wash),
                       y4 - (lead_gain_1 * y3 + lag_gain_1 * x4),
                       y5 - (lead_gain_2 * y4 + lag_gain_2 * x5),
                       Vpss - sym.hard_sat(y5, VPssMinPu, VPssMaxPu)],
        algebraic_vars=[y2, y4, y5, Vpss],
        in_vars=inputs,
        out_vars=[Vpss],
        event_dict=events_dict,
        name="stabilizer_v2",
    )

    init_eqs: dict[Var, Expr] = dict()
    init_eqs[Vpss] = sym.Const(0.0)
    init_eqs[y] = inputs[0]
    init_eqs[x_wash] = inputs[0]
    init_eqs[y2] = sym.Const(0.0)
    init_eqs[y3] = sym.Const(0.0)
    init_eqs[dy3_state] = sym.Const(0.0)
    init_eqs[x4] = sym.Const(0.0)
    init_eqs[y4] = sym.Const(0.0)
    init_eqs[x5] = sym.Const(0.0)
    init_eqs[y5] = sym.Const(0.0)
    templ.block.init_eqs = init_eqs

    templ.comment = 'Reusable generator stabilizer RMS control block'
    return templ


def get_exciter_rms(vfactory: VarFactory, name: str = "exciter") -> RmsModelTemplate:
    """Build the exciter with explicit dynamic states.

    The AVR, rate feedback, and exciter field stages are rewritten as explicit
    states. This preserves the original algebraic nonlinearities while making
    the controller dynamics visible to the small-signal state matrix.

    :param vfactory: Shared symbolic variable factory.
    :param name: Model name.
    :return: Exciter RMS template.
    """
    templ: RmsModelTemplate = RmsModelTemplate(name=name)

    parameters: dict[str, object] = {
        # Exciter (AVR) parameters
        "Ka": vfactory.add_const(50.0),  # AVR gain
        "Kf": vfactory.add_const(0.03),  # exciter rate feedback gain

        # Time constants
        "tA": vfactory.add_const(0.1),  # AVR time constant (s)
        "tB": vfactory.add_const(10.0),  # lead-lag: lag time constant (s)
        "tC": vfactory.add_const(1.0),  # lead-lag: lead time constant (s)
        "tE": vfactory.add_const(0.5),  # exciter field time constant (s)
        "tF": vfactory.add_const(1.0),  # rate feedback time constant (s)
        "tR": vfactory.add_const(0.08),  # stator voltage filter time constant (s)

        # Exciter submodel parameters
        "Kc": vfactory.add_const(0.2),  # rectifier loading factor
        "Kd": vfactory.add_const(0.1),  # demagnetizing factor
        "Ke": vfactory.add_const(1.0),  # field resistance constant
        "Kfd": vfactory.add_const(0.5),  # converting factor

    }

    inputs: list[Var] = [vfactory.add_var("IRPu_", shared_reference="irpu_reference"),
                         vfactory.add_var("Vm_", reference=VarPowerFlowReferenceType.Vm),
                         vfactory.add_var("Vpss_", shared_reference="vpss_reference")]

    Vf: Var = vfactory.add_var("Vf", shared_reference="vf_reference")
    Efe: Var = vfactory.add_var("Efe")
    UsRefPu: Var = vfactory.add_var("UsRefPu")
    VeMaxPu: Var = vfactory.add_var("VeMaxPu")
    u_aux: Var = vfactory.add_var("u_aux")
    AEz: Var = vfactory.add_var("AEz")
    BEz: Var = vfactory.add_var("BEz")
    EfeMaxPu: Var = vfactory.add_var("EfeMaxPu")
    EfeMinPu: Var = vfactory.add_var("EfeMinPu")
    TolLi: Var = vfactory.add_var("TolLi")
    VaMaxPu: Var = vfactory.add_var("VaMaxPu")
    VaMinPu: Var = vfactory.add_var("VaMinPu")
    VeMinPu: Var = vfactory.add_var("VeMinPu")
    VfeMaxPu: Var = vfactory.add_var("VfeMaxPu")
    AEx: Var = vfactory.add_var("AEx")
    BEx: Var = vfactory.add_var("BEx")
    Se_threshold: Var = vfactory.add_var("Se_threshold")
    ToLLi: Var = vfactory.add_var("ToLLi")
    VeMinPu_submodel: Var = vfactory.add_var("VeMinPu_submodel")
    VfeMaxPu_submodel: Var = vfactory.add_var("VfeMaxPu_submodel")

    y1: Var = vfactory.add_var("y_exciter1")
    x2: Var = vfactory.add_var("x_exciter2")
    y2: Var = vfactory.add_var("y_exciter2")
    x3: Var = vfactory.add_var("x_exciter3")
    y3: Var = vfactory.add_var("y_exciter3")
    y4: Var = vfactory.add_var("y_exciter4")
    y6: Var = vfactory.add_var("y_exciter4_sat")
    Ve: Var = vfactory.add_var("y_subexciter1")
    f_input: Var = vfactory.add_var("f_input")
    f_output: Var = vfactory.add_var("f_output")

    events_dict: dict[Var, Expr] = dict()
    events_dict[UsRefPu] = Efe / parameters["Ka"] + inputs[1]
    events_dict[AEz] = vfactory.add_const(0.02)
    events_dict[BEz] = vfactory.add_const(1.5)
    events_dict[Se_threshold] = vfactory.add_const(1.0)
    events_dict[EfeMaxPu] = vfactory.add_const(15.0)
    events_dict[EfeMinPu] = vfactory.add_const(-5.0)
    events_dict[TolLi] = vfactory.add_const(0.05)
    events_dict[VaMaxPu] = vfactory.add_const(2.5)
    events_dict[VaMinPu] = vfactory.add_const(-2.0)
    events_dict[VeMinPu] = vfactory.add_const(-2.0)
    events_dict[VfeMaxPu] = vfactory.add_const(5.0)
    events_dict[AEx] = vfactory.add_const(0.02)
    events_dict[BEx] = vfactory.add_const(0.01)
    events_dict[ToLLi] = vfactory.add_const(0.05)
    events_dict[VeMinPu_submodel] = vfactory.add_const(-5.1)
    events_dict[VfeMaxPu_submodel] = vfactory.add_const(5.0)

    min_const: Expr = VaMinPu
    max_const: Expr = VaMaxPu
    error1: Expr = (-y1 + UsRefPu) + inputs[2]
    error2: Expr = error1 - y2
    lead_gain: Expr = parameters["tC"] / parameters["tB"]
    lag_gain: Expr = sym.Const(1.0) - lead_gain
    x1_expr: Expr = VfeMaxPu - inputs[0] * parameters["Kd"]
    # A tiny margin keeps the nominal operating point away from exact clipping
    # when the unsaturated equilibrium lies numerically on a limiter boundary.
    sat_eps: Expr = sym.Const(1e-9)
    y4_sat_min: Expr = min_const + sat_eps
    y4_sat_max: Expr = max_const - sat_eps
    Ve_linear: Expr = sym.hard_sat(Ve, VeMinPu_submodel + sat_eps, VeMaxPu - sat_eps)
    Sx: Expr = (sym.exp(BEx * (Ve_linear - Se_threshold)) - sym.Const(1.0)) * sym.heaviside(Ve_linear - Se_threshold)
    aux_expr: Expr = parameters["Ke"] * Ve_linear + AEx * Ve_linear * Sx
    f_output_res: Expr = sym.f_exc(f_input)

    templ.block = Block(
        state_eqs=[(inputs[1] - y1) / parameters["tR"],
                   (Vf - x2) / parameters["tF"],
                   (error2 - x3) / parameters["tB"],
                   (parameters["Ka"] * y3 - y6) / parameters["tA"],
                   (Efe - (inputs[0] * parameters["Kd"] + u_aux)) / parameters["tE"]],
        state_vars=[y1, x2, x3, y4, Ve],
        algebraic_eqs=[y2 - parameters["Kf"] * (Vf - x2) / parameters["tF"],
                       y3 - (lead_gain * error2 + lag_gain * x3),
                       y6 - sym.hard_sat(y4, y4_sat_min, y4_sat_max),
                       Efe - y6,
                       u_aux - aux_expr,
                       VeMaxPu * u_aux - x1_expr * Ve,
                       f_input * Ve - inputs[0] * parameters["Kc"],
                       Vf - f_output * Ve,
                       f_output_res - f_output],
        algebraic_vars=[y2, y3, y6, Efe, u_aux, VeMaxPu, Vf, f_input, f_output],
        out_vars=[Vf],
        in_vars=inputs,
        event_dict=events_dict,
        name="exciter_v2",
    )


    init_eqs: dict[Var, Expr] = dict()
    init_eqs[Vf] = inputs[0]
    init_eqs[Ve] = inputs[0] * (sym.Const(1.0) / sym.f_exc(inputs[0] * parameters["Kc"] / Ve))
    init_eqs[VeMaxPu] = (VfeMaxPu - inputs[0] * parameters["Kd"].value) / (
        parameters["Ke"] + AEx * (sym.exp(BEx * (Ve - Se_threshold)) - sym.Const(1.0)) * sym.heaviside(Ve - Se_threshold)
    )
    init_eqs[u_aux] = aux_expr
    init_eqs[Efe] = inputs[0] * parameters["Kd"] + u_aux
    init_eqs[y1] = inputs[1]
    init_eqs[x2] = Vf
    init_eqs[y2] = sym.Const(0.0)
    init_eqs[x3] = Efe / parameters["Ka"]
    init_eqs[y3] = Efe / parameters["Ka"]
    init_eqs[y4] = Efe
    init_eqs[y6] = Efe
    init_eqs[f_input] = parameters["Kc"] * inputs[0] / Ve
    init_eqs[f_output] = sym.f_exc(f_input)
    templ.block.init_eqs = init_eqs

    templ.comment = 'Reusable generator exciter RMS control block'
    return templ


def OELBuild(vfactory: VarFactory, name: str = "OEL") -> tuple[Block, Var]:
    """Return the original OEL builder.

    The complete generator template in this module does not currently wire the
    OEL into the composed model. The original implementation is therefore
    reused verbatim to avoid changing unrelated behavior.

    :param vfactory: Shared symbolic variable factory.
    :param name: Model name.
    :return: OEL block and its output variable.
    """
    result: tuple[Block, Var] = OELBuildBase(vfactory=vfactory, name=name)
    return result


def get_complete_generator_template_rms(vfactory: VarFactory, name: str = "complete_generator_rms_template") -> RmsModelTemplate:
    """Build the complete generator using the explicit-state controller variants.

    :param vfactory: Shared symbolic variable factory.
    :param name: Model name.
    :return: Complete generator RMS template.
    """
    templ: RmsModelTemplate = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name

    genqec_mdl: Block = get_genqec_rms(vfactory=vfactory).block
    exciter_mdl: Block = get_exciter_rms(vfactory=vfactory).block
    governor_mdl: Block = get_governor_rms(vfactory=vfactory).block
    stabilizer_mdl: Block = get_stabilizer_rms(vfactory=vfactory).block

    vfactory.add_connection(genqec_mdl.in_vars[3], exciter_mdl.out_vars[0])
    vfactory.add_connection(exciter_mdl.in_vars[0], genqec_mdl.out_vars[3])
    vfactory.add_connection(exciter_mdl.in_vars[1], genqec_mdl.in_vars[0])
    vfactory.add_connection(exciter_mdl.in_vars[2], stabilizer_mdl.out_vars[0])
    vfactory.add_connection(stabilizer_mdl.in_vars[0], genqec_mdl.out_vars[2])
    vfactory.add_connection(genqec_mdl.in_vars[2], governor_mdl.out_vars[0])
    vfactory.add_connection(governor_mdl.in_vars[0], genqec_mdl.out_vars[2])
    vfactory.add_connection(governor_mdl.in_vars[1], genqec_mdl.out_vars[4])

    templ.block.children.append(genqec_mdl)
    templ.block.children.append(governor_mdl)
    templ.block.children.append(stabilizer_mdl)
    templ.block.children.append(exciter_mdl)
    templ.block.external_mapping = dict()
    templ.block.external_mapping[VarPowerFlowReferenceType.Vm] = genqec_mdl.in_vars[0]
    templ.block.external_mapping[VarPowerFlowReferenceType.Va] = genqec_mdl.in_vars[1]
    templ.block.external_mapping[VarPowerFlowReferenceType.P] = genqec_mdl.out_vars[0]
    templ.block.external_mapping[VarPowerFlowReferenceType.Q] = genqec_mdl.out_vars[1]
    templ.block.in_vars = [genqec_mdl.in_vars[0], genqec_mdl.in_vars[1]]
    templ.block.out_vars = [genqec_mdl.out_vars[0], genqec_mdl.out_vars[1]]
    templ.block.name = name

    templ.comment = 'Complete generator RMS model with GENQEC, exciter, governor, and stabilizer'
    return templ
