# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List
import numpy as np
import math

from VeraGridEngine.enumerations import ParamPowerFlowReferenceType
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowReferenceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import (Block, find_name_in_block)
from VeraGridEngine.Utils.Symbolic.block_helpers import tf_to_block, tf_to_diffblock_with_output, \
    tf_to_block_with_states, to_implicit, integrator_with_non_windup, integrator_with_windup
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
import VeraGridEngine.Utils.Symbolic.symbolic as sym
import VeraGridEngine.Utils.Symbolic.symbolic_ml as sym_ml


def _build_hard_sat_block(vfactory: VarFactory, x, xmin, xmax, mode: str = "ml", name: str = ""):
    sat_mode = mode.lower()
    if sat_mode == "none":
        return Block(), x
    if sat_mode == "normal":
        y = vfactory.add_var(f"hs_{name}" if name else "hs")
        blk = Block(
            algebraic_eqs=[y - sym.hard_sat(x, xmin, xmax)],
            algebraic_vars=[y],
            init_eqs={y: sym.hard_sat(x, xmin, xmax)},
        )
        return blk, y
    if sat_mode == "mti":
        return sym_ml.mti_hard_sat(vfactory, x, xmin, xmax, xmin, xmax, name=name)
    if sat_mode == "ml":
        return sym_ml.ml_hard_sat(vfactory, x, xmin, xmax)
    raise ValueError(f"Unsupported hard_sat_type '{mode}'. Use: normal, ml, mti, none")


def _build_trig_transform_block(vfactory: VarFactory, x, mode: str = "ml"):
    if mode.lower() == "ml":
        return sym_ml.trig_transform(vfactory, x)
    u_cos = vfactory.add_var("u_cos")
    u_sin = vfactory.add_var("u_sin")
    blk = Block(
        algebraic_eqs=[u_cos - sym.cos(x), u_sin - sym.sin(x)],
        algebraic_vars=[u_cos, u_sin],
        init_eqs={u_cos: sym.cos(x), u_sin: sym.sin(x)},
    )
    return blk, u_cos, u_sin


def _build_positive_part_block(vfactory: VarFactory, x, mode: str = "ml", name: str = ""):
    if mode.lower() == "ml":
        return sym_ml.ml_positive_part(vfactory, x, name=name)
    x_plus = vfactory.add_var(f"x_plus_{name}" if name else "x_plus")
    x_minus = vfactory.add_var(f"x_minus_{name}" if name else "x_minus")
    blk = Block(
        algebraic_eqs=[x_plus - sym.max(x, vfactory.add_const(0.0)), x_minus - sym.max(-x, vfactory.add_const(0.0))],
        algebraic_vars=[x_plus, x_minus],
        init_eqs={
            x_plus: sym.max(x, vfactory.add_const(0.0)),
            x_minus: sym.max(-x, vfactory.add_const(0.0)),
        },
    )
    return blk, x_plus, x_minus


def _build_exponential_block(vfactory: VarFactory, x, mode: str = "ml"):
    if mode.lower() == "ml":
        return sym_ml.exponential_ml(vfactory, x)
    y = vfactory.add_var("exp_y")
    blk = Block(
        algebraic_eqs=[y - sym.exp(x)],
        algebraic_vars=[y],
        init_eqs={y: sym.exp(x)},
    )
    return blk, y


def _build_heaviside_block(vfactory: VarFactory, x, mode: str = "ml"):
    if mode.lower() == "ml":
        return sym_ml.ml_heaviside(vfactory, x)
    y = vfactory.add_var("hv_y")
    blk = Block(
        algebraic_eqs=[y - sym.heaviside(x)],
        algebraic_vars=[y],
        init_eqs={y: sym.heaviside(x)},
    )
    return blk, y


def _build_f_exc_block(vfactory: VarFactory, x, mode: str = "ml"):
    if mode.lower() == "ml":
        return sym_ml.ml_f_exc(vfactory, x)
    y = vfactory.add_var("f_exc_y")
    blk = Block(
        algebraic_eqs=[y - sym.f_exc(x)],
        algebraic_vars=[y],
        init_eqs={y: sym.f_exc(x)},
    )
    return blk, y


def GenqecBuild(vfactory: VarFactory, name: str = "GENQEC RMS template", hard_sat_type: str = "ml") -> RmsModelTemplate:
    """Build the GENQEC synchronous-generator RMS model.

    :param vfactory: Factory that owns the model's symbolic variables.
    :param name: Name assigned to the generated RMS model template.
    :param hard_sat_type: Saturation-block implementation used by the model.
    :return: Configured GENQEC RMS model template.
    """
    pi = math.pi
    templ = RmsModelTemplate(name=name)
    templ.name = name
    templ.tpe = DeviceType.GeneratorDevice

    # Inputs
    # Vm: Bus voltage module
    # Va: Bus voltage angle
    # Tm: mechanical torque (from governor)
    # Vf: excitation voltage (from exciter)

    algebraic_eqs = []
    algebraic_vars = []
    inputs = [vfactory.add_var("Vm"),
              vfactory.add_var("Va"),
              vfactory.add_var("Tm"),
              vfactory.add_var("Vf")]

    # ______________________________________________________________________________________
    #                                    variables
    # ______________________________________________________________________________________

    # State variables
    delta = vfactory.add_var("delta")  # rotor angle
    omega = vfactory.add_var("omega")  # rotor electrical speed
    Eq1 = vfactory.add_var("Eq1")  # internal emf behind Xd'
    Ed1 = vfactory.add_var("Ed1")
    Eq_prime = vfactory.add_var("Eq_prime")  # transient voltage q-axis
    Ed_prime = vfactory.add_var("Ed_prime")  # transient voltage d-axis
    Psid_prime = vfactory.add_var("Psid_prime")  # transient voltage d-axis
    Psiq_prime = vfactory.add_var("Psiq_prime")  # transient voltage d-axis

    # Algebraic variables
    Pg = vfactory.add_var('Pg')
    Qg = vfactory.add_var('Qg')
    Id = vfactory.add_var("Id")
    Iq = vfactory.add_var("Iq")
    Vd = vfactory.add_var("Vd")
    Vq = vfactory.add_var("Vq")
    Psid = vfactory.add_var("Psid")
    Psiq = vfactory.add_var("Psiq")
    Te = vfactory.add_var("Te")
    IRPu = vfactory.add_var("IRPu")

    # Auxiliary Variables
    V_dag_aux = vfactory.add_var('V_dag_aux')
    V_qag_aux = vfactory.add_var('V_qag_aux')
    Psi_sqrt1 = vfactory.add_var('Psi_sqrt1')
    Psi_sqrt2 = vfactory.add_var('Psi_sqrt2')

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
    H = vfactory.add_var('H')  # inertia constant
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
        H: vfactory.add_const(1) / M,
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
        Xdaux: ((Xd_prime - Xd_2prime) / (Xd_prime_minus_Xl) ** 2),
        Xdaux2: ((Xd_prime - Xd_2prime) / (Xd_prime_minus_Xl)),
        Xdaux3: ((Xd_2prime - Xl) / (Xd_prime_minus_Xl)),
        Xqaux: ((Xq_prime - Xq_2prime) / (Xq_prime_minus_Xl) ** 2),
        Xqaux2: (Xq_prime - Xq_2prime) / (Xq_prime_minus_Xl),
        Xqaux3: ((Xq_2prime - Xl) / (Xq_prime_minus_Xl)),
        A: vfactory.add_const(2.0),
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

    # we call trig_transform to get cos(Vm-delta) and siN(Vm-delta)
    ml_trig_block, u_cos, u_sin = _build_trig_transform_block(vfactory, inputs[1] - delta, mode=hard_sat_type)

    # We call ml_postive_part to ge (Psi_ag-B)^+ := max(Psi_ag-B, 0)
    ml_positive_part, Psi_plus, Psi_minus = _build_positive_part_block(vfactory, Psi_ag - B, mode=hard_sat_type, name='Psi_plus')

    templ.block = Block(
        state_eqs=[
            (omega - vfactory.add_const(1)) * ws,  # dδ/dt
            (inputs[2] - Te - D * (omega - vfactory.add_const(1))) * (H),  # dω/dt
            (inputs[3] - Sat * Eq1) / Td0_prime,  # dEq'/dt
            -Sat * Ed1 / Tq0_prime,  # dEd'/dt
            (-Psiq_prime + Iq_sat * Xq_prime_minus_Xl + Ed_prime),  # dPsiq'/dt
            (-Psid_prime - Id_sat * Xd_prime_minus_Xl + Eq_prime),  # dPsid'/dt
        ],
        state_vars=[delta, omega, Eq_prime, Ed_prime, Psiq_prime, Psid_prime],
        algebraic_eqs=[
            Vd - (-inputs[0] * u_sin),  # from input block
            Vq - (inputs[0] * u_cos),  # from input block
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
            Psi_sqrt1 - Psi_sqrt2,
            V_qag_aux - V_qag,
            V_dag_aux - V_dag,
            Psi_sqrt1 * Psi_sqrt2 - (V_qag_aux * V_qag + V_dag * V_dag_aux),
            omega * Psi_ag - Psi_sqrt1,
            # saturations (quadratic)
            Sa - A * Psi_plus,

            # Eq1, Eq2, Ed1, Ed2 exciter
            IRPu - Eq1 * Sat,
        ],
        algebraic_vars=[Pg, Qg, Vd, Vq, Psid, Psiq, Te, Ed1, Eq1, Id, Iq,
                        # saturated resistance
                        Xq_2prime_sat, Xd_2prime_sat, Id_sat, Iq_sat,
                        # flux
                        Sa, Sat, V_dag, V_qag, Psi_ag, IRPu,
                        # auxiliary variables
                        Psi_sqrt1, Psi_sqrt2, V_qag_aux, V_dag_aux
                        ],
        init_eqs={
            # Air Gap Voltages and delta
            omega: vfactory.add_const(1),
            Psi_ag: sym.sqrt(Viag_expr ** 2 + Vrag_expr ** 2),
            Sa: A * sym.max(Psi_ag - B, vfactory.add_const(0)),
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

            Psi_sqrt1: Psi_ag,
            Psi_sqrt2: Psi_sqrt1,
            V_qag_aux: V_qag,
            V_dag_aux: V_dag,
            # We initialize some specific parameters:
        },
        # external_mapping={
        #     VarPowerFlowReferenceType.P: Pg,
        #     VarPowerFlowReferenceType.Q: Qg,
        #     VarPowerFlowReferenceType.Vm: inputs[0],
        #     VarPowerFlowReferenceType.Va: inputs[1],
        # },
        out_vars=[Pg, Qg, omega, IRPu, Te],
        in_vars=inputs,
        event_dict=event_dict,
        children=[ml_positive_part, ml_trig_block],
        name="genqec",
        api_obj_mapping={ParamPowerFlowReferenceType.freq: fn, ParamPowerFlowReferenceType.omega_base: ws},
        parameters={fn: vfactory.add_const(50.0), ws: vfactory.add_const(2 * pi * 50)},
    )

    templ.comment = 'Generator GENQEC RMS model'
    return templ


def GovernorBuild(vfactory: VarFactory, name: str = "Governor RMS template", hard_sat_type: str = "ml") -> RmsModelTemplate:
    """Build the turbine-governor control model used by the generator.

    :param vfactory: Factory that owns the model's symbolic variables.
    :param name: Name assigned to the generated RMS model template.
    :param hard_sat_type: Saturation-block implementation used by the governor.
    :return: Configured turbine-governor RMS model template.
    """
    templ = RmsModelTemplate(name=name)
    templ.name = name

    parameters = {
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

    inputs = [vfactory.add_var("omega_"), vfactory.add_var('Te_')]

    # ______________________________________________________________________________________
    #                                    variables
    # ______________________________________________________________________________________

    Tm = vfactory.add_var("Tm")  # Mechanical power input (pu
    et = vfactory.add_var("et")

    # reference
    Pm_ref = vfactory.add_var('Pm_ref')
    algebraic_eqs = []
    algebraic_vars = []

    # ______________________________________________________________________________________
    #                                    parameters
    # ______________________________________________________________________________________

    # Gains and limits
    K = vfactory.add_var("K")  # governor gain (inverse droop)
    Pmax = vfactory.add_var("Pmax")  # max mechanical power (pu)
    Pmin = vfactory.add_var("Pmin")  # min mechanical power (pu)
    Uc = vfactory.add_var("Uc")  # max valve closing rate (pu/s)
    Uo = vfactory.add_var("Uo")  # max valve opening rate (pu/s)
    T_aux = vfactory.add_var("T_aux")

    # Control
    Kp = vfactory.add_var("Kp")
    Ki = vfactory.add_var("Ki")
    omega_ref = vfactory.add_var('omega_ref')
    p0 = vfactory.add_var('p0')
    P0 = vfactory.add_var('P0')

    events_dict = {
        # control parameters
        Pm_ref: inputs[1],
        Kp: vfactory.add_const(-0.01),
        Ki: vfactory.add_const(-0.01),
        p0: vfactory.add_const(1.0),
        P0: vfactory.add_const(0.01),
        omega_ref: vfactory.add_const(1),
        # Governor parameters
        K: vfactory.add_const(10.0),  # governor gain (inverse droop)
        Pmax: vfactory.add_const(200.0),  # max mechanical power (pu)
        Pmin: vfactory.add_const(-200.0),  # min mechanical power (pu)
        Uc: vfactory.add_const(-0.001),  # max valve closing rate (pu/s)
        Uo: vfactory.add_const(0.001),  # max valve opening rate (pu/s)
        T_aux: vfactory.add_const(0.0),

    }
    controller_block = Block(
        state_eqs=[
            P0 * (inputs[0] - omega_ref)
        ],
        state_vars=[et],
        algebraic_eqs=[
            T_aux - (Kp * (inputs[0] - omega_ref) + Ki * et),
        ],
        algebraic_vars=[T_aux],
    )
    controller_block = Block()

    u1 = inputs[0] - omega_ref
    lead_lag_block, y1, x1 = tf_to_diffblock_with_output(
        vfactory,
        num=np.array([1, parameters["T2"].value]),
        den=np.array([1, parameters["T1"].value]),
        x=u1,
        name='gov0',
    )

    # ==============================
    # First Feed back Loop
    y2_3 = vfactory.add_var('y2_3_gov')
    algebraic_vars.append(y2_3)
    x2 = Pm_ref - K * y1 - y2_3

    y2 = x2 * (1 / parameters["T3"].value)
    # Keep previous Gen0 behavior to avoid boolean-combinatorics blow-up in
    # legacy phasor small-signal workflows.
    if hard_sat_type.lower() == "ml":
        ml_block1, y2_1 = _build_hard_sat_block(vfactory, y2, Uc, Uo, mode=hard_sat_type, name="gov_rate")
    else:
        ml_block1, y2_1 = _build_hard_sat_block(vfactory, y2, Uc, Uo, mode=hard_sat_type, name="gov_rate")

    # y2_1 = sym.hard_sat(y2, Uc, Uo)
    tf1, y2_2, u_gov1 = tf_to_diffblock_with_output(
        vfactory,
        num=np.array([1]),
        den=np.array([0, 1]),
        x=y2_1,
        name='gov1',
    )
    ml_block2, y2_bis = _build_hard_sat_block(vfactory, y2_2, Pmin, Pmax, mode=hard_sat_type, name="gov_pow")
    algebraic_eqs.append(y2_3 - y2_bis)

    # ==============================
    # We compute different outputs for every tf
    tf2, y3_1 = tf_to_block(
        vfactory,
        num=np.array([1]),
        den=np.array([1, parameters["T4"].value]),
        x=y2_3,
        name='gov2',
    )
    tf3, y3_2 = tf_to_block(
        vfactory,
        num=np.array([1]),
        den=np.array([1, parameters["T5"].value]),
        x=y3_1,
        name='gov3',
    )
    tf4, y3_3 = tf_to_block(
        vfactory,
        num=np.array([1]),
        den=np.array([1, parameters["T6"].value]),
        x=y3_2,
        name='gov4',
    )
    tf5, y3_4 = tf_to_block(
        vfactory,
        num=np.array([1]),
        den=np.array([1, parameters["T7"].value]),
        x=y3_3,
        name='gov5',
    )

    u = parameters["K1"].value * y3_1 + parameters["K2"].value * y3_2 + parameters["K3"].value * y3_3 + \
        parameters["K4"].value * y3_4
    aux_block = Block(
        algebraic_eqs=[u - Tm] + algebraic_eqs,
        algebraic_vars=[Tm] + algebraic_vars,
    )

    templ.block = Block(
        children=[lead_lag_block, tf1, tf2, tf3, tf4, tf5, aux_block, controller_block],
        out_vars=[Tm],
        in_vars=inputs,
        event_dict=events_dict,
        name="governor",

        init_eqs={
            y1: vfactory.add_const(0.0),
            x1: inputs[0] - omega_ref,
            u_gov1: vfactory.add_const(0),
            y2_2: Pm_ref,
            y2_3: Pm_ref,
            y3_1: Pm_ref,
            y3_2: Pm_ref,
            y3_3: Pm_ref,
            y3_4: Pm_ref,
            Tm: Pm_ref
        },
    )
    templ.block.children.extend([ml_block1, ml_block2])
    templ.comment = 'Generator governor RMS control block'
    return templ


def StabilizerBuild(vfactory: VarFactory, name: str = "Stabilizer RMS template", hard_sat_type: str = "ml") -> RmsModelTemplate:
    """Build the power-system stabilizer control model.

    :param vfactory: Factory that owns the model's symbolic variables.
    :param name: Name assigned to the generated RMS model template.
    :param hard_sat_type: Saturation-block implementation used by the stabilizer.
    :return: Configured power-system stabilizer RMS model template.
    """
    templ = RmsModelTemplate(name=name)
    templ.name = name

    parameters = {
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

    # input variables
    # omega: omega from generator

    inputs = [vfactory.add_var("omega_")]

    # PSS parameters with typical values

    Ks = vfactory.add_var("Ks")  # stabilizer gain
    VPssMaxPu = vfactory.add_var("VPssMaxPu")  # max stabilizer output
    VPssMinPu = vfactory.add_var("VPssMinPu")  # min stabilizer output
    SNom = vfactory.add_var("SNom")  # nominal apparent power

    events_dict = {
        # Stabilizer parameters
        Ks: vfactory.add_const(20),  # stabilizer gain
        VPssMaxPu: vfactory.add_const(2.0),  # max stabilizer output
        VPssMinPu: vfactory.add_const(-2.0),  # min stabilizer output
        SNom: vfactory.add_const(1.0),  # nominal apparent power
    }

    # variables
    Vpss = vfactory.add_var('V_pss')

    vars_block = Block(
        algebraic_vars=[],
    )

    tf, y = tf_to_block(
        vfactory,
        num=np.array([1.0]),
        den=np.array([1, parameters["t6"].value]),
        x=inputs[0]-1,
        name='stabilizer1_' +name,
    )

    tf2, y2 = tf_to_block(
        vfactory,
        num=np.array([0, Ks * parameters["t5"].value]),
        den=np.array([1, parameters["t5"].value]),
        x=y,
        name='stabilizer2_' +name,
    )
    tf3, y3 = tf_to_block_with_states(
        vfactory,
        num=np.array([1]),
        den=np.array([1, parameters["A1"].value, parameters["A2"].value]),
        x=y2,
        name='stabilizer3_' +name,
    )
    tf4, y4 = tf_to_block(
        vfactory,
        num=np.array([1, parameters["t1"].value]),
        den=np.array([1, parameters["t2"].value]),
        x=y3,
        name='stabilizer4_' +name,
    )
    tf5, y5 = tf_to_block(
        vfactory,
        num=np.array([1, parameters["t3"].value]),
        den=np.array([1, parameters["t4"].value]),
        x=y4,
        name='stabilizer5',
    )

    ml_block, Vpss_sat = _build_hard_sat_block(vfactory, y5, VPssMinPu, VPssMaxPu, mode=hard_sat_type, name=f"pss_sat_{name}")
    algebraic_eqs = list()
    algebraic_eqs.append(Vpss_sat - Vpss)

    templ.block = Block(
        children=[tf, tf2, tf3, tf4, tf5],
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=[Vpss],
        in_vars=inputs,
        out_vars=[Vpss],
        event_dict=events_dict,
        name="stabilizer",

        init_eqs={
            Vpss: vfactory.add_const(0.0),
            y: inputs[0]-1,
            y2: vfactory.add_const(0.0),
            y3: vfactory.add_const(0.0),
            y4: vfactory.add_const(0.0),
            y5: vfactory.add_const(0.0),
        }
    )

    templ.block.add(vars_block)
    templ.block.add(ml_block)

    templ.comment = 'Generator stabilizer RMS control block'
    return templ


def ExciterBuild(vfactory: VarFactory, name: str = "Exciter RMS template", hard_sat_type: str = "ml") -> RmsModelTemplate:
    """Build the generator excitation-system control model.

    :param vfactory: Factory that owns the model's symbolic variables.
    :param name: Name assigned to the generated RMS model template.
    :param hard_sat_type: Saturation-block implementation used by the exciter.
    :return: Configured exciter RMS model template.
    """
    templ = RmsModelTemplate(name=name)
    templ.name = name

    Ka = vfactory.add_var("Ka")
    tA = vfactory.add_var("tA")

    parameters = {
        # Exciter (AVR) parameters
        "Kf": vfactory.add_const(0.03),  # exciter rate feedback gain

        # Time constants
        "tB": vfactory.add_const(10.0),  # lead-lag: lag time constant (s)
        "tC": vfactory.add_const(1.0),  # lead-lag: lead time constant (s)
        "tE": vfactory.add_const(0.5),  # exciter field time constant (s)
        "tF": vfactory.add_const(1.0),  # rate feedback time constant (s)
        "tR": vfactory.add_const(0.08),  # stator voltage filter time constant (s)

        # Exciter submodel parameters
        "Kc": vfactory.add_const(0.1),  # rectifier loading factor
        "Kd": vfactory.add_const(0.1),  # demagnetizing factor
        "Ke": vfactory.add_const(0.5),  # field resistance constant
        "Kfd": vfactory.add_const(0.5),  # converting factor

    }

    # input variables
    # IRPu: rotor current (pu) ???
    # Va: measured stator voltage (from generator) (pu)
    # Vpss: output from power system stabilizer (pu)

    inputs = [vfactory.add_var("IRPu_"), vfactory.add_var("Vm_"), vfactory.add_var("Vpss_")]

    algebraic_vars = []

    # ______________________________________________________________________________________
    #                                    variables
    # ______________________________________________________________________________________

    Vf = vfactory.add_var("Vf")
    Efe = vfactory.add_var('Efe')
    UsRefPu = vfactory.add_var("UsRefPu")  # reference voltage (pu)

    # Exciter internal variables
    VeMaxPu = vfactory.add_var('VeMaxPu')
    u_aux = vfactory.add_var('u_aux')

    # ______________________________________________________________________________________
    #                                    parameters
    # ______________________________________________________________________________________

    # ---- Exciter (AVR) parameters ----
    AEz = vfactory.add_var("AEz")  # saturation gain
    BEz = vfactory.add_var("BEz")  # saturation exponential coefficient
    EfeMaxPu = vfactory.add_var("EfeMaxPu")  # max exciter field voltage (pu)
    EfeMinPu = vfactory.add_var("EfeMinPu")  # min exciter field voltage (pu)

    # ---- Exciter (AVR) time constants and limits ----

    TolLi = vfactory.add_var("TolLi")  # limiter crossing tolerance (fraction)

    VaMaxPu = vfactory.add_var("VaMaxPu")  # AVR output max (pu)
    VaMinPu = vfactory.add_var("VaMinPu")  # AVR output min (pu)
    VeMinPu = vfactory.add_var("VeMinPu")  # min exciter output voltage (pu)
    VfeMaxPu = vfactory.add_var("VfeMaxPu")  # max exciter field current signal (pu)

    # exciter submodel parameters
    AEx = vfactory.add_var("AEx")  # Gain of saturation function
    BEx = vfactory.add_var("BEx")  # Exponential coefficient of saturation function
    Se_threshold = vfactory.add_var("Se_threshold")  # Exponential coefficient of saturation function
    ToLLi = vfactory.add_var("ToLLi")  # Tolerance on limit crossing

    events_dict = {
        # Exciter (AVR) parameters
        UsRefPu: Efe / Ka + inputs[1],  # reference voltage (pu)
        Ka: vfactory.add_const(20.0),  # AVR gain
        AEz: vfactory.add_const(0.02),  # saturation gain
        BEz: vfactory.add_const(1.5),  # saturation exponential coefficient
        Se_threshold: vfactory.add_const(1.0),  # saturation threshold
        EfeMaxPu: vfactory.add_const(25.0),  # max exciter field voltage (pu)
        EfeMinPu: vfactory.add_const(-50.0),  # min exciter field voltage (pu)

        # Time constants
        tA: vfactory.add_const(0.1),  # AVR time constant (s)
        TolLi: vfactory.add_const(0.05),  # limiter crossing tolerance (fraction)

        # Limits
        VaMaxPu: vfactory.add_const(10.0),  # AVR output max (pu)
        VaMinPu: vfactory.add_const(-55.0),  # AVR output min (pu)
        VeMinPu: vfactory.add_const(-55.0),  # min exciter output voltage (pu)
        VfeMaxPu: vfactory.add_const(20.0),  # max exciter field current signal (pu)

        # Exciter submodel parameters
        AEx: vfactory.add_const(0.00),  # saturation gain
        BEx: vfactory.add_const(0.05),  # exponential coeff of saturation function
        ToLLi: vfactory.add_const(0.05),  # tolerance on limit crossing
    }
    # ---Internal Blocks---
    tf1, y1 = tf_to_block(
        vfactory,
        num=np.array([1]),
        den=np.array([1, parameters["tR"].value]),
        x=inputs[1],
        name='exciter1_'+name,
    )  # filtered stator voltage

    # error1 = UPssPu - y + UsRefPu
    error1 = (- y1 + UsRefPu) + inputs[2]
    tf2, y2 = tf_to_block(
        vfactory,
        num=np.array([0, parameters["Kf"].value]),
        den=np.array([1, parameters["tF"].value]),
        x=Vf,
        name='exciter2_'+name,
    )
    error2 = error1 - y2

    tf3, y3 = tf_to_block(
        vfactory,
        num=np.array([1, parameters["tC"].value]),
        den=np.array([1, parameters["tB"].value]),
        x=error2,
        name='exciter3',
    )
    min_const = max(events_dict[VaMinPu].value, events_dict[EfeMinPu].value)
    min_const = -1e3
    max_const = min(events_dict[VaMaxPu].value, events_dict[EfeMaxPu].value)
    max_const = 1e3
    # TODO: Try with AnitWindup
    tf4, y4 = tf_to_block(
        vfactory,
        num=np.array([Ka]),
        den=np.array([1, tA]),
        x=y3,
        # sat_min = min_const,
        # sat_max = max_const,
        name='exciter4',
    )
    ml_block2, y6 = _build_hard_sat_block(vfactory, y4, min_const, max_const, mode=hard_sat_type, name=f'exciter_sat_{name}')

    # exciter submodel

    algebraic_eqs_submodel = []
    algebraic_vars_submodel = []

    x1 = VfeMaxPu - inputs[0] * parameters["Kd"].value
    error1 = Efe - (inputs[0] * parameters["Kd"].value + u_aux)

    tf1_sub, Ve_pre = tf_to_block(
        vfactory,
        num=np.array([1]),
        den=np.array([0, parameters["tE"].value]),
        x=error1,
        #sat_min= VeMinPu,
        #sat_max= VeMaxPu,
        name='subexciter1',
    )

    Se_threshold = parameters['Ke'].value

    ml_block1, Ve = _build_hard_sat_block(vfactory, Ve_pre, VeMinPu, VeMaxPu, mode=hard_sat_type, name=f'Ve_sat_{name}')
    ml_block_exp, V_exp = _build_exponential_block(vfactory, BEx * (Ve - Se_threshold), mode=hard_sat_type)
    ml_block_hv, V_hv = _build_heaviside_block(vfactory, Ve - Se_threshold, mode=hard_sat_type)
    Sx = (V_exp - vfactory.add_const(1)) * V_hv
    aux_expr = parameters['Ke'].value * Ve + AEx * Ve * Sx
    algebraic_eqs_submodel.append(u_aux - aux_expr)
    algebraic_eqs_submodel.append(VeMaxPu * u_aux - x1 * Ve)

    f_input = vfactory.add_var('f_input')
    f_output = vfactory.add_var('f_output')
    ml_block3, f_output_res = _build_f_exc_block(vfactory, f_input, mode=hard_sat_type)
    algebraic_vars_submodel.append(f_input)
    algebraic_vars_submodel.append(f_output)
    algebraic_eqs_submodel.append(f_input * Ve - inputs[0] * parameters["Kc"].value)

    algebraic_eqs_submodel.append(Vf - f_output * Ve)
    algebraic_eqs_submodel.append(f_output_res - f_output)

    aux_model = Block(
        algebraic_eqs=algebraic_eqs_submodel,
        algebraic_vars=[u_aux, VeMaxPu, Vf] + algebraic_vars_submodel
    )

    exciter_submodel = Block(children=[tf1_sub, aux_model])

    linking_block = Block(
        algebraic_eqs=[y6 - Efe],
        algebraic_vars=[Efe] + algebraic_vars,
    )

    u_exciter3 = find_name_in_block('u_exciter3', tf3)
    u_subexciter1 = find_name_in_block('u_subexciter1', tf1_sub)
    y_subexciter1 = find_name_in_block('y_subexciter1', tf1_sub)
    dt_y_subexciter1 = find_name_in_block('dt_1_y_subexciter1', tf1_sub)
    Ve_sat = sym.hard_sat(y_subexciter1, VeMinPu, VeMaxPu)
    Ve_expr = sym.hard_sat(y_subexciter1, VeMinPu, VeMaxPu)
    aux_expr = parameters['Ke'].value * Ve_expr + AEx * Ve_expr * Sx
    efe_init = sym.hard_sat(inputs[0] * parameters["Kd"].value + u_aux, min_const, max_const)
    templ.block = Block(
        children=[tf1, tf2, tf3, tf4, exciter_submodel, linking_block, ml_block_exp, ml_block_hv, ml_block1, ml_block2, ml_block3],
        out_vars=[Vf],
        in_vars=inputs,
        event_dict=events_dict,
        init_eqs={
            Vf: inputs[0],
            y_subexciter1: inputs[0] * (1 / sym.f_exc(inputs[0] * parameters["Kc"].value / y_subexciter1)),
            # y_subexciter1: inputs[0] * (1 / sym.f_exc(inputs[0] * parameters["Kc"].value / y_subexciter1)),
            # Ve: sym.hard_sat(y_subexciter1, VeMinPu, Const(1000)),
            # Sx: (sym.exp(BEx * (Ve - Se_threshold)) - Const(1)) * sym.heaviside(Ve - Se_threshold),
            VeMaxPu: (VfeMaxPu - inputs[0] * parameters["Kd"].value) / (
                    parameters["Ke"].value + AEx * (
                    sym.exp(BEx * (Ve_pre - Se_threshold)) - vfactory.add_const(1)) * sym.heaviside(
                Ve_pre - Se_threshold)),
            u_aux: aux_expr,
            #Efe: efe_init,
            Efe: (inputs[0] * parameters["Kd"].value + u_aux),
            y1: inputs[1],
            y2: vfactory.add_const(0.0),
            y3: -y1 + UsRefPu,
            u_exciter3: y3,
            y4: y3 * Ka,
            #y4: efe_init,
            u_subexciter1: Efe - (inputs[0] * parameters["Kd"].value + u_aux),
            f_input: parameters['Kc'].value * inputs[0] / y_subexciter1,
            f_output: sym.f_exc(parameters['Kc'].value * inputs[0] / (y_subexciter1 + 1e-8)),
        },
    )

    templ.comment = 'Generator exciter RMS control block'
    return templ


def OELBuild(vfactory: VarFactory, name: str = "OEL RMS template") -> RmsModelTemplate:
    """Build the generator over-excitation limiter control model.

    :param vfactory: Factory that owns the model's symbolic variables.
    :param name: Name assigned to the generated RMS model template.
    :return: Configured over-excitation limiter RMS model template.
    """
    templ = RmsModelTemplate(name=name)
    templ.name = name

    oel_block = Block(name='exciter_limiter_block')
    algebraic_eqs = []
    algebraic_vars = []
    differential_vars = []

    inputs = [vfactory.add_var("OEL_input")]
    Input_OEL = inputs[0]
    # OEL_input_options are Efd or I_f

    # parameters
    # time constants
    T_en = vfactory.add_var('T_en')
    T_off = vfactory.add_var('T_off')
    T_roel = vfactory.add_var('T_roel')
    T_doel = vfactory.add_var('T_doel')
    T_b1oel = vfactory.add_var('T_b1oel')
    T_c1oel = vfactory.add_var('T_c1oel')
    T_b2oel = vfactory.add_var('T_b2oel')
    T_aoel = vfactory.add_var('T_aoel')
    T_fcl = vfactory.add_var('T_fcl')

    T_min = vfactory.add_var('T_min')
    T_max = vfactory.add_var('T_max')

    # voltage limits
    V_oelmin = vfactory.add_var('V_oelmin')
    V_oelmax = vfactory.add_var('V_oelmax')
    V_invmin = vfactory.add_var('V_invmin')
    V_invmax = vfactory.add_var('V_invmax')

    # gains
    K_poel = vfactory.add_var('K_poel')
    K_ioel = vfactory.add_var('K_ioel')
    K_doel = vfactory.add_var('K_doel')
    K_ru = vfactory.add_var('K_ru')
    K_zru = vfactory.add_var('K_zru')
    K_rd = vfactory.add_var('K_rd')
    K_act = vfactory.add_var('K_act')
    K1 = vfactory.add_var('K1')
    K2 = vfactory.add_var('K2')
    Kfb = vfactory.add_var('Kfb')

    # fixed ramps
    Fixed_RU = vfactory.add_var('Fixed_RU')
    Fixed_RD = vfactory.add_var('Fixed_RD')

    # current-related parameters
    I_tfpu = vfactory.add_var('I_tfpu')
    I_THoff = vfactory.add_var('I_THoff')
    I_reset = vfactory.add_var('I_reset')
    I_inst = vfactory.add_var('I_inst')
    I_lim = vfactory.add_var('I_lim')

    # scaling and auxiliary
    K_scale = vfactory.add_var('K_scale')
    C1 = vfactory.add_var('C1')
    C2 = vfactory.add_var('C2')

    # switches
    SW1 = vfactory.add_var('SW1')

    Ierr = vfactory.add_var('Ierr')
    V_oel = vfactory.add_var('V_oel')
    Ipu = vfactory.add_var('Ipu')

    event_dict = {
        # time constants
        T_en: vfactory.add_const(1.0),
        T_off: vfactory.add_const(1.0),
        T_roel: vfactory.add_const(1.0),
        T_doel: vfactory.add_const(1.0),
        T_b1oel: vfactory.add_const(1.0),
        T_c1oel: vfactory.add_const(1.0),
        T_b2oel: vfactory.add_const(1.0),
        T_aoel: vfactory.add_const(1.0),
        T_fcl: vfactory.add_const(1.0),
        T_min: vfactory.add_const(1.0),
        T_max: vfactory.add_const(1.0),

        # voltage limits
        V_oelmin: vfactory.add_const(-1.0),
        V_oelmax: vfactory.add_const(1.0),
        V_invmin: vfactory.add_const(-1.0),
        V_invmax: vfactory.add_const(1.0),

        # gains
        K_poel: vfactory.add_const(1.0),
        K_ioel: vfactory.add_const(1.0),
        K_doel: vfactory.add_const(1.0),
        K_ru: vfactory.add_const(1.0),
        K_zru: vfactory.add_const(1.0),
        K_rd: vfactory.add_const(1.0),
        K_act: vfactory.add_const(1.0),
        K1: vfactory.add_const(1.0),
        K2: vfactory.add_const(1.0),
        Kfb: vfactory.add_const(1.0),

        # ramp limits
        Fixed_RU: vfactory.add_const(1.0),
        Fixed_RD: vfactory.add_const(1.0),

        # currents
        I_tfpu: vfactory.add_const(1.0),
        I_THoff: vfactory.add_const(1.0),
        I_reset: vfactory.add_const(1.0),
        I_inst: vfactory.add_const(1.0),
        I_lim: vfactory.add_const(0.0),

        # scaling
        K_scale: vfactory.add_const(4.6),  # Ifield rated / Ibase
        C1: vfactory.add_const(1.0),
        C2: vfactory.add_const(1.0),

        # switches
        SW1: vfactory.add_const(1.0),
    }

    oel_block.event_dict = event_dict
    # equations
    block_Ipu, Ipu = tf_to_block(
        vfactory,
        num=[K_scale],
        den=[1, T_roel],
        x=Input_OEL,
        name='exciter_limiter_Ipu',
    )
    oel_block.add(block_Ipu)
    I_errinv1 = K1 * ((Ipu / I_tfpu) ** C1 - 1)
    I_errinv2_aux = K2 * ((Ipu / I_tfpu) ** C2 - 1)

    # OEL TIMER LOGIC
    I_errinv2 = sym.hard_sat(I_errinv2_aux, V_invmin, V_invmax)
    W = I_errinv2 + sym.heaviside(I_tfpu - Ipu) * Fixed_RU + (
            vfactory.add_const(1) - sym.heaviside(I_tfpu - Ipu)) * Fixed_RD

    T = vfactory.add_var('T')
    block4, T = tf_to_block(
        vfactory,
        num=[1],
        den=[0, 1],
        x=W - Kfb * sym.hard_sat(T, T_min, T_max),
        y=T,
        name='exciter_limiter_T',
    )
    oel_block.add(block4)

    Terr = T_fcl - W - Kfb * sym.hard_sat(T, T_min, T_max)

    # OEL RAMP LOGIC
    C = (vfactory.add_const(1) - SW1) * (K_ru) + I_errinv1 * (SW1)
    D = (vfactory.add_const(1) - SW1) * (K_rd) + I_errinv1 * (SW1)
    Z = C * sym.heaviside(Terr - K_zru * T_fcl) + D * (sym.heaviside(-Terr))

    block5, I_a = tf_to_block(
        vfactory,
        num=[1],
        den=[0, 1],
        x=Z,
        name='exciter_limiter_Ipu',
    )
    oel_block.add(block5)

    I_ref = sym.hard_sat(I_a, I_lim, I_inst)

    block7, y_1 = tf_to_block(
        vfactory,
        num=[1],
        den=[1, T_aoel],
        x=I_ref,
        name='exciter_limiter_Iref',
    )
    oel_block.add(block7)

    I_act = K_act * Ipu
    x = vfactory.add_var('x')
    dx = vfactory.add_diff_var('x', base_var=x)
    algebraic_eqs.append(dx - (sym.heaviside(T_en - x) * sym.heaviside(I_act - I_ref) - (
            vfactory.add_const(1) - sym.heaviside(I_act - I_ref)) * sym.heaviside(x) * vfactory.add_const(1000)))
    b1 = (x - T_en >= 0).to_expression()
    b2 = (Terr <= 0).to_expression()  # (Terr <= 0) when comparisons are supported
    b3 = (T_en == 0).to_expression()

    y = vfactory.add_var('y')
    dy = vfactory.add_diff_var('y', base_var=y)
    algebraic_eqs.append(dy - (sym.heaviside(T_off - y) * sym.heaviside(I_ref - I_act - I_THoff) - (
            vfactory.add_const(1) - sym.heaviside(I_ref - I_act - I_THoff)) * sym.heaviside(y) * vfactory.add_const(
        1000)))
    c1 = (I_ref == I_inst).to_expression()
    c2 = sym.heaviside(y - T_off + vfactory.add_const(1e-3))

    I_bias = vfactory.add_var('I_bias')
    algebraic_eqs.append(I_bias - (1 - (1 - b1) * (1 - b2) * (1 - b3)) * (c1 * c2))
    algebraic_vars.append(x)
    algebraic_vars.append(y)
    algebraic_vars.append(I_bias)
    differential_vars.append(dx)
    differential_vars.append(dy)

    Ierr = y_1 - K_act * Ipu + I_bias

    block8, V_oel = tf_to_block(
        vfactory,
        num=[K_doel * K_poel],
        den=[0, 1, T_doel],
        x=K_poel * Ierr,
        name='exciter_limiter_Voel',
    )
    oel_block.add(block8)

    V_oel_sat = vfactory.add_var('V_oel_sat')
    algebraic_vars.append(V_oel_sat)
    algebraic_eqs.append(sym.hard_sat(V_oel, V_oelmin, V_oelmax) - V_oel_sat)

    end_block = Block(
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=algebraic_vars,
        diff_vars=differential_vars,
    )

    oel_block.add(end_block)

    oel_block.in_vars = inputs
    oel_block.out_vars = [V_oel_sat]
    templ.block = oel_block
    templ.comment = 'Generator over-excitation limiter RMS block'
    return templ


def get_complete_generator_template(vfactory: VarFactory,
                                    name: str = "complete generator rms template",
                                    implicit: bool = False,
                                    hard_sat_type: str = "ml") -> RmsModelTemplate:
    """
    
    :return: 
    """
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name

    # generate models
    genqec_mdl = GenqecBuild(vfactory, hard_sat_type=hard_sat_type).block
    exciter_mdl = ExciterBuild(vfactory, name, hard_sat_type=hard_sat_type).block
    governor_mdl = GovernorBuild(vfactory, hard_sat_type=hard_sat_type).block
    stabilizer_mdl = StabilizerBuild(vfactory, hard_sat_type=hard_sat_type).block

    # connect models
    vf = vfactory
    vf.add_connections([genqec_mdl.in_vars[3]], [exciter_mdl.out_vars[0]])
    vf.add_connections([exciter_mdl.in_vars[0]], [genqec_mdl.out_vars[3]])
    vf.add_connections([exciter_mdl.in_vars[1]], [genqec_mdl.in_vars[1]])

    vf.add_connections([stabilizer_mdl.in_vars[0]], [genqec_mdl.out_vars[2]])

    vf.add_connections([exciter_mdl.in_vars[2]], [stabilizer_mdl.out_vars[0]])

    vf.add_connections([genqec_mdl.in_vars[2]], [governor_mdl.out_vars[0]])

    vf.add_connections([governor_mdl.in_vars[0]], [genqec_mdl.out_vars[2]])

    vf.add_connections([governor_mdl.in_vars[1]], [genqec_mdl.out_vars[4]])

    templ.block.children.append(genqec_mdl)
    templ.block.children.append(governor_mdl)
    templ.block.children.append(stabilizer_mdl)
    templ.block.children.append(exciter_mdl)
    templ.block.unify_blocks()
    if implicit:
        templ.block = to_implicit(templ.block, vfactory=vfactory)
    templ.block.external_mapping = {
        VarPowerFlowReferenceType.Vm: genqec_mdl.in_vars[0],
        VarPowerFlowReferenceType.Va: genqec_mdl.in_vars[1],
        VarPowerFlowReferenceType.P: genqec_mdl.out_vars[0],
        VarPowerFlowReferenceType.Q: genqec_mdl.out_vars[1],
    }

    templ.block.in_vars = [genqec_mdl.in_vars[0], genqec_mdl.in_vars[1]]
    templ.block.out_vars = [genqec_mdl.out_vars[0], genqec_mdl.out_vars[1]]

    templ.comment = 'Complete generator RMS model'
    return templ
