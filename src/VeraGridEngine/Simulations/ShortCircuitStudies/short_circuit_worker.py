# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Tuple
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import inv
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Simulations.ShortCircuitStudies.short_circuit import short_circuit_3p, short_circuit_unbalance
from VeraGridEngine.Topology.admittance_matrices import compute_admittances
from VeraGridEngine.Simulations.ShortCircuitStudies.short_circuit_results import ShortCircuitResults
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions import polar_to_rect
from VeraGridEngine.enumerations import FaultType, MethodShortCircuit, PhasesShortCircuit
from VeraGridEngine.basic_structures import CxVec, Vec, IntVec
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation_3ph import (compute_ybus,
                                                                                        compute_Sbus_delta,
                                                                                        compute_current_loads,
                                                                                        compute_Sbus_star,
                                                                                        compute_ybus_generator,
                                                                                        expand_magnitudes,
                                                                                        expand_indices_3ph,
                                                                                        expand3ph)
from scipy.sparse import diags
from scipy.sparse.linalg import spsolve
import pandas as pd
from scipy.sparse import csc_matrix


def short_circuit_post_process(
        calculation_inputs: NumericalCircuit,
        V: CxVec,
        branch_rates: Vec,
        Yf: sp.csc_matrix,
        Yt: sp.csc_matrix
) -> Tuple[CxVec, CxVec, CxVec, CxVec, CxVec, CxVec, CxVec]:
    """
    Compute the important results for short-circuits
    :param calculation_inputs: instance of Circuit
    :param V: Voltage solution array for the circuit buses
    :param branch_rates: Array of branch ratings
    :param Yf: From admittance matrix
    :param Yt: To admittance matrix
    :return: Sf (MVA), If (p.u.), loading (p.u.), losses (MVA), Sbus(MVA)
    """

    Vf = V[calculation_inputs.passive_branch_data.F]
    Vt = V[calculation_inputs.passive_branch_data.T]

    # Branches current, loading, etc
    If = Yf * V
    It = Yt * V
    Sf = Vf * np.conj(If)
    St = Vt * np.conj(It)

    # Branch losses in MVA (not really important for short-circuits)
    losses = (Sf + St) * calculation_inputs.Sbase

    # branch voltage increment
    Vbranch = Vf - Vt

    # Branch power in MVA
    Sfb = Sf * calculation_inputs.Sbase
    Stb = St * calculation_inputs.Sbase

    # Branch loading in p.u.
    loading = Sfb / (branch_rates + 1e-9)



    return Sfb, Stb, If, It, Vbranch, loading, losses

# def expand3ph(x: np.ndarray):
#     """
#     Expands a numpy array to 3-pase copying the same values
#     :param x:
#     :return:
#     """
#     n = len(x)
#     idx3 = np.array([0, 1, 2])
#     x3 = np.zeros(3 * n, dtype=x.dtype)
#
#     for k in range(n):
#         x3[3 * k + idx3] = x[k]
#     return x3
#
# def expand_indices_3ph(x: np.ndarray) -> np.ndarray:
#     """
#     Expands a numpy array to 3-pase copying the same values
#     :param x:
#     :return:
#     """
#     n = len(x)
#     idx3 = np.array([0, 1, 2])
#     x3 = np.zeros(3 * n, dtype=x.dtype)
#
#     for k in range(n):
#         x3[3 * k + idx3] = 3 * x[k] + idx3
#
#     return x3

def short_circuit_post_process_phases_abc(
        calculation_inputs: NumericalCircuit,
        V_expanded: CxVec,
        branch_rates_expanded: Vec,
        Yf: sp.csc_matrix,
        Yt: sp.csc_matrix,
        F_expanded: IntVec,
        T_expanded: IntVec,
        mask,
        branch_lookup
) -> Tuple[CxVec, CxVec, CxVec, CxVec, CxVec, CxVec, CxVec]:
    """
    Compute the important results for short-circuits
    :param calculation_inputs: instance of Circuit
    :param V: Voltage solution array for the circuit buses
    :param branch_rates: Array of branch ratings
    :param Yf: From admittance matrix
    :param Yt: To admittance matrix
    :param F_expanded:
    :param T_expanded:
    :return: Sf (MVA), If (p.u.), loading (p.u.), losses (MVA), Sbus(MVA)
    """

    Vf_expanded = V_expanded[F_expanded]
    Vt_expanded = V_expanded[T_expanded]

    V = V_expanded[mask]

    # Branches current, loading, etc
    If = Yf @ V
    It = Yt @ V

    If_expanded  = expand_magnitudes(If, branch_lookup)
    It_expanded  = expand_magnitudes(It, branch_lookup)

    Sf_expanded  = Vf_expanded * np.conj(If_expanded )
    St_expanded  = Vt_expanded  * np.conj(It_expanded )

    # Branch losses in MVA (not really important for short-circuits)
    losses_expanded = (Sf_expanded  + St_expanded) * calculation_inputs.Sbase

    # branch voltage increment
    Vbranch_expanded  = Vf_expanded  - Vt_expanded

    # Branch power in MVA
    Sfb_expanded  = Sf_expanded  * calculation_inputs.Sbase
    Stb_expanded  = St_expanded  * calculation_inputs.Sbase

    # Branch loading in p.u.
    loading_expanded  = Sfb_expanded / (branch_rates_expanded + 1e-9)

    return Sfb_expanded, Stb_expanded, If_expanded, It_expanded, Vbranch_expanded, loading_expanded, losses_expanded

def short_circuit_post_process_phases(
        calculation_inputs: NumericalCircuit,
        V: CxVec,
        branch_rates: Vec,
        Yf: sp.csc_matrix,
        Yt: sp.csc_matrix
) -> Tuple[CxVec, CxVec, CxVec, CxVec, CxVec, CxVec, CxVec]:
    """
    Compute the important results for short-circuits
    :param calculation_inputs: instance of Circuit
    :param V: Voltage solution array for the circuit buses
    :param branch_rates: Array of branch ratings
    :param Yf: From admittance matrix
    :param Yt: To admittance matrix
    :return: Sf (MVA), If (p.u.), loading (p.u.), losses (MVA), Sbus(MVA)
    """

    Vf = V[calculation_inputs.passive_branch_data.F]
    Vt = V[calculation_inputs.passive_branch_data.T]

    # Branches current, loading, etc
    If = Yf * V
    It = Yt * V
    Sf = Vf * np.conj(If)
    St = Vt * np.conj(It)

    # Branch losses in MVA (not really important for short-circuits)
    losses = (Sf + St) * calculation_inputs.Sbase

    # branch voltage increment
    Vbranch = Vf - Vt

    # Branch power in MVA
    Sfb = Sf * calculation_inputs.Sbase
    Stb = St * calculation_inputs.Sbase

    # Branch loading in p.u.
    loading = Sfb / (branch_rates + 1e-9)

    return Sfb, Stb, If, It, Vbranch, loading, losses


def short_circuit_ph3(nc: NumericalCircuit, Vpf: CxVec, Zf: CxVec, bus_index: int):
    """
    Run a 3-phase short circuit simulation for a single island
    :param nc: NumericalCircuit
    :param Vpf: Power flow voltage vector applicable to the island
    :param Zf: Short circuit impedance vector applicable to the island
    :param bus_index: Bus index
    :return: short circuit results
    """
    adm = nc.get_admittance_matrices()
    Y_gen = nc.generator_data.get_Yshunt(seq=1)
    Y_batt = nc.battery_data.get_Yshunt(seq=1)
    Ybus_gen_batt = adm.Ybus + sp.diags(Y_gen) + sp.diags(Y_batt)

    # Compute the short circuit
    V, SCpower, ICurrent = short_circuit_3p(bus_idx=bus_index,
                                            Ybus=Ybus_gen_batt,
                                            Vbus=Vpf,
                                            Vnom=nc.bus_data.Vnom,
                                            Zf=Zf,
                                            baseMVA=nc.Sbase)

    (Sfb, Stb, If, It, Vbranch,
     loading, losses) = short_circuit_post_process(calculation_inputs=nc,
                                                   V=V,
                                                   branch_rates=nc.passive_branch_data.rates,
                                                   Yf=adm.Yf,
                                                   Yt=adm.Yt)

    # voltage, Sf, loading, losses, error, converged, Qpv
    results = ShortCircuitResults(n=nc.nbus,
                                  m=nc.nbr,
                                  n_hvdc=nc.nhvdc,
                                  bus_names=nc.bus_data.names,
                                  branch_names=nc.passive_branch_data.names,
                                  hvdc_names=nc.hvdc_data.names,
                                  bus_types=nc.bus_data.bus_types,
                                  area_names=None)

    results.SCpower = SCpower
    results.ICurrent = ICurrent
    results.Sbus1 = nc.get_power_injections_pu() * nc.Sbase  # MVA
    results.voltage1 = V
    results.Sf1 = Sfb  # in MVA already
    results.St1 = Stb  # in MVA already
    results.If1 = If  # in p.u.
    results.It1 = It  # in p.u.
    results.Vbranch1 = Vbranch
    results.loading1 = loading
    results.losses1 = losses

    return results


def short_circuit_unbalanced(nc: NumericalCircuit,
                             Vpf: CxVec,
                             Zf: CxVec,
                             bus_index: int,
                             fault_type: FaultType) -> ShortCircuitResults:
    """
    Run an unbalanced short circuit simulation for a single island
    :param nc:
    :param Vpf: Power flow voltage vector applicable to the island
    :param Zf: Short circuit impedance vector applicable to the island
    :param bus_index: Index of the failed bus
    :param fault_type: FaultType
    :return: short circuit results
    """

    # build Y0, Y1, Y2
    nbr = nc.nbr
    nbus = nc.nbus

    Y_gen0 = nc.generator_data.get_Yshunt(seq=0)
    Y_batt0 = nc.battery_data.get_Yshunt(seq=0)
    Yshunt_bus0 = Y_gen0 + Y_batt0

    Cf = nc.passive_branch_data.Cf.tocsc()
    Ct = nc.passive_branch_data.Ct.tocsc()

    adm0 = compute_admittances(R=nc.passive_branch_data.R0,
                               X=nc.passive_branch_data.X0,
                               G=nc.passive_branch_data.G0,  # renamed, it was overwritten
                               B=nc.passive_branch_data.B0,
                               tap_module=nc.active_branch_data.tap_module,
                               vtap_f=nc.passive_branch_data.virtual_tap_f,
                               vtap_t=nc.passive_branch_data.virtual_tap_t,
                               tap_angle=nc.active_branch_data.tap_angle,
                               Cf=Cf,
                               Ct=Ct,
                               Yshunt_bus=Yshunt_bus0,
                               conn=nc.passive_branch_data.conn,
                               seq=0,
                               add_windings_phase=True)

    Y_gen1 = nc.generator_data.get_Yshunt(seq=1)
    Y_batt1 = nc.battery_data.get_Yshunt(seq=1)
    Yshunt_bus1 = nc.get_Yshunt_bus_pu() + Y_gen1 + Y_batt1

    adm1 = compute_admittances(R=nc.passive_branch_data.R,
                               X=nc.passive_branch_data.X,
                               G=nc.passive_branch_data.G,
                               B=nc.passive_branch_data.B,
                               tap_module=nc.active_branch_data.tap_module,
                               vtap_f=nc.passive_branch_data.virtual_tap_f,
                               vtap_t=nc.passive_branch_data.virtual_tap_t,
                               tap_angle=nc.active_branch_data.tap_angle,
                               Cf=Cf,
                               Ct=Ct,
                               Yshunt_bus=Yshunt_bus1,
                               conn=nc.passive_branch_data.conn,
                               seq=1,
                               add_windings_phase=True)

    Y_gen2 = nc.generator_data.get_Yshunt(seq=2)
    Y_batt2 = nc.battery_data.get_Yshunt(seq=2)
    Yshunt_bus2 = Y_gen2 + Y_batt2

    adm2 = compute_admittances(R=nc.passive_branch_data.R2,
                               X=nc.passive_branch_data.X2,
                               G=nc.passive_branch_data.G2,
                               B=nc.passive_branch_data.B2,
                               tap_module=nc.active_branch_data.tap_module,
                               vtap_f=nc.passive_branch_data.virtual_tap_f,
                               vtap_t=nc.passive_branch_data.virtual_tap_t,
                               tap_angle=nc.active_branch_data.tap_angle,
                               Cf=Cf,
                               Ct=Ct,
                               Yshunt_bus=Yshunt_bus2,
                               conn=nc.passive_branch_data.conn,
                               seq=2,
                               add_windings_phase=True)

    """
    Initialize Vpf introducing phase shifts
    No search algo is needed. Instead, we need to solve YV=0,
    get the angle of the voltages from here and add them to the
    original Vpf. Y should be Yseries (avoid shunts).
    In more detail:
    -----------------   -----   -----
    |   |           |   |Vvd|   |   |
    -----------------   -----   -----
    |   |           |   |   |   |   |
    |   |           | x |   | = |   |
    | Yu|     Yx    |   | V |   | 0 |
    |   |           |   |   |   |   |
    |   |           |   |   |   |   |
    -----------------   -----   -----

    where Yu = Y1.Ybus[pqpv, vd], Yx = Y1.Ybus[pqpv, pqpv], so:
    V = - inv(Yx) Yu Vvd
    ph_add = np.angle(V)
    Vpf[pqpv] *= np.exp(1j * ph_add)
    """

    adm_series = compute_admittances(R=nc.passive_branch_data.R,
                                     X=nc.passive_branch_data.X,
                                     G=np.zeros(nbr),
                                     B=np.zeros(nbr),
                                     tap_module=nc.active_branch_data.tap_module,
                                     vtap_f=nc.passive_branch_data.virtual_tap_f,
                                     vtap_t=nc.passive_branch_data.virtual_tap_t,
                                     tap_angle=nc.active_branch_data.tap_angle,
                                     Cf=Cf,
                                     Ct=Ct,
                                     Yshunt_bus=np.zeros(nbus, dtype=complex),
                                     conn=nc.passive_branch_data.conn,
                                     seq=1,
                                     add_windings_phase=True)

    indices = nc.get_simulation_indices()

    vd = indices.vd
    pqpv = indices.no_slack

    # Y1_arr = np.array(adm_series.Ybus.todense())
    # Yu = Y1_arr[np.ix_(pqpv, vd)]
    # Yx = Y1_arr[np.ix_(pqpv, pqpv)]
    #
    # I_vd = Yu * np.array(Vpf[vd])
    # Vpqpv_ph = - np.linalg.inv(Yx) @ I_vd

    # add the voltage phase due to the slack, to the rest of the nodes
    I_vd = adm_series.Ybus[np.ix_(pqpv, vd)] * Vpf[vd]
    Vpqpv_ph = - sp.linalg.spsolve(adm_series.Ybus[np.ix_(pqpv, pqpv)], I_vd)
    ph_add = np.angle(Vpqpv_ph)
    Vpf[pqpv] = polar_to_rect(np.abs(Vpf[pqpv]), np.angle(Vpf[pqpv]) + ph_add.T)

    # solve the fault
    V0, V1, V2, SCC, ICC = short_circuit_unbalance(bus_idx=bus_index,
                                                   Y0=adm0.Ybus,
                                                   Y1=adm1.Ybus,
                                                   Y2=adm2.Ybus,
                                                   Vnom=nc.bus_data.Vnom,
                                                   Vbus=Vpf,
                                                   Zf=Zf,
                                                   fault_type=fault_type,
                                                   baseMVA=nc.Sbase)

    # process results in the sequences
    (Sfb0, Stb0, If0, It0, Vbranch0,
     loading0, losses0) = short_circuit_post_process(calculation_inputs=nc,
                                                     V=V0,
                                                     branch_rates=nc.passive_branch_data.rates,
                                                     Yf=adm0.Yf,
                                                     Yt=adm0.Yt)

    (Sfb1, Stb1, If1, It1, Vbranch1,
     loading1, losses1) = short_circuit_post_process(calculation_inputs=nc,
                                                     V=V1,
                                                     branch_rates=nc.passive_branch_data.rates,
                                                     Yf=adm1.Yf,
                                                     Yt=adm1.Yt)

    (Sfb2, Stb2, If2, It2, Vbranch2,
     loading2, losses2) = short_circuit_post_process(calculation_inputs=nc,
                                                     V=V2,
                                                     branch_rates=nc.passive_branch_data.rates,
                                                     Yf=adm2.Yf,
                                                     Yt=adm2.Yt)

    # voltage, Sf, loading, losses, error, converged, Qpv
    results = ShortCircuitResults(n=nc.nbus,
                                  m=nc.nbr,
                                  n_hvdc=nc.nhvdc,
                                  bus_names=nc.bus_data.names,
                                  branch_names=nc.passive_branch_data.names,
                                  hvdc_names=nc.hvdc_data.names,
                                  bus_types=nc.bus_data.bus_types,
                                  area_names=None)

    results.SCpower = SCC
    results.ICurrent = ICC

    results.voltage0 = V0
    results.Sf0 = Sfb0  # in MVA already
    results.St0 = Stb0  # in MVA already
    results.If0 = If0  # in p.u.
    results.It0 = It0  # in p.u.
    results.Vbranch0 = Vbranch0
    results.loading0 = loading0
    results.losses0 = losses0

    results.voltage1 = V1
    results.Sf1 = Sfb1  # in MVA already
    results.St1 = Stb1  # in MVA already
    results.If1 = If1  # in p.u.
    results.It1 = It1  # in p.u.
    results.Vbranch1 = Vbranch1
    results.loading1 = loading1
    results.losses1 = losses1

    results.voltage2 = V2
    results.Sf2 = Sfb2  # in MVA already
    results.St2 = Stb2  # in MVA already
    results.If2 = If2  # in p.u.
    results.It2 = It2  # in p.u.
    results.Vbranch2 = Vbranch2
    results.loading2 = loading2
    results.losses2 = losses2

    return results


def maximum_initial_shortcircuit_current(
        nc: NumericalCircuit,
        Zf: complex,
        faulted_bus: int
):

    c_max = 1.1 # Voltage factor
    Un = nc.bus_data.Vnom[faulted_bus] * 1e3 # Nominal voltage [V]
    Zk = abs(Zf) * Un**2 / (nc.Sbase * 1e6) # Fault impedance [Ohm]

    # Current contribution only from SGs
    Ik_max_PFO = 1/Zk * c_max * Un / np.sqrt(3)
    Isk_PF = 0

    # Current contribution only from CIGs
    # sumatory
    # Isk_PF = 1/Zk * sumatory

    # Total current contribution
    Ik_max = Ik_max_PFO + Isk_PF

    return Ik_max



def short_circuit_abc(nc: NumericalCircuit,
                      Vpf: CxVec,
                      Zf: CxVec,
                      bus_index: int,
                      fault_type: FaultType,
                      method: MethodShortCircuit,
                      phases: PhasesShortCircuit,
                      Spf: CxVec) -> ShortCircuitResults:
    """
    Run a short circuit simulation in the phase domain
    :param nc:
    :param Vpf: Power flow voltage vector applicable to the island
    :param Zf: Short circuit impedance vector applicable to the island
    :param bus_index: Index of the failed bus
    :param fault_type: FaultType
    :param Spf: Bus powers Sbus
    :param method: Method to solve the short-circuit, sequence or phase domain
    :param phases: Phases where the short-circuit occurs
    :return: short circuit results
    """

    Ybus, Yf, Yt, Yshunt_bus, mask, bus_lookup, branch_lookup = compute_ybus(nc)

    Vpf_masked = Vpf[mask]

    Sstar, Y_power_star_linear = compute_Sbus_star(nc=nc,
                                                   V=Vpf_masked,
                                                   mask=mask)

    Sdelta, Y_power_delta_linear = compute_Sbus_delta(bus_idx=nc.load_data.bus_idx,
                                                      Sdelta=nc.load_data.S3_delta,
                                                      Ydelta=nc.load_data.Y3_delta,
                                                      V=Vpf_masked,
                                                      bus_lookup=bus_lookup)

    I_star_delta, Y_current_linear = compute_current_loads(bus_idx=nc.load_data.bus_idx,
                                                           bus_lookup=bus_lookup,
                                                           V=Vpf_masked,
                                                           Istar=nc.load_data.I3_star,
                                                           Idelta=nc.load_data.I3_delta)

    Y_power_star_linear /= (nc.Sbase / 3)
    Y_power_delta_linear /= (nc.Sbase / 3)
    Y_current_linear /= (nc.Sbase / 3)

    Yfault = np.zeros((len(Vpf), len(Vpf)), dtype=complex)
    a = 3 * bus_index + 0
    b = 3 * bus_index + 1
    c = 3 * bus_index + 2

    # Single Line-to-Ground (SLG)
    if fault_type == FaultType.LG:

        if phases == PhasesShortCircuit.a:
            Yfault[a, a] = 1 / (Zf[bus_index] + 1e-20)

        elif phases == PhasesShortCircuit.b:
            Yfault[b, b] = 1 / (Zf[bus_index] + 1e-20)

        elif phases == PhasesShortCircuit.c:
            Yfault[c, c] = 1 / (Zf[bus_index] + 1e-20)

    # Line-to-Line (LL)
    elif fault_type == FaultType.LL:

        if phases == PhasesShortCircuit.ab:

            Yfault[a, a] = 1 / (Zf[bus_index] + 1e-20)
            Yfault[a, b] = -1 / (Zf[bus_index] + 1e-20)
            Yfault[b, a] = -1 / (Zf[bus_index] + 1e-20)
            Yfault[b, b] = 1 / (Zf[bus_index] + 1e-20)

        elif phases == PhasesShortCircuit.bc:

            Yfault[b, b] = 1 / (Zf[bus_index] + 1e-20)
            Yfault[b, c] = -1 / (Zf[bus_index] + 1e-20)
            Yfault[c, b] = -1 / (Zf[bus_index] + 1e-20)
            Yfault[c, c] = 1 / (Zf[bus_index] + 1e-20)

        elif phases == PhasesShortCircuit.ca:

            Yfault[c, c] = 1 / (Zf[bus_index] + 1e-20)
            Yfault[c, a] = -1 / (Zf[bus_index] + 1e-20)
            Yfault[a, c] = -1 / (Zf[bus_index] + 1e-20)
            Yfault[a, a] = 1 / (Zf[bus_index] + 1e-20)

    # Double Line-to-Ground (DLG)
    elif fault_type == FaultType.LLG:

        if phases == PhasesShortCircuit.ab:
            Yfault[a, a] = 1 / (Zf[bus_index] + 1e-20)
            Yfault[b, b] = 1 / (Zf[bus_index] + 1e-20)

        elif phases == PhasesShortCircuit.bc:
            Yfault[b, b] = 1 / (Zf[bus_index] + 1e-20)
            Yfault[c, c] = 1 / (Zf[bus_index] + 1e-20)

        elif phases == PhasesShortCircuit.ca:
            Yfault[c, c] = 1 / (Zf[bus_index] + 1e-20)
            Yfault[a, a] = 1 / (Zf[bus_index] + 1e-20)

    # Three-Phase Fault (LLL)
    elif fault_type == FaultType.LLL:

        Yfault[a, a] = 2 / (Zf[bus_index] + 1e-20)
        Yfault[a, b] = -1 / (Zf[bus_index] + 1e-20)
        Yfault[a, c] = -1 / (Zf[bus_index] + 1e-20)

        Yfault[b, b] = 2 / (Zf[bus_index] + 1e-20)
        Yfault[b, a] = -1 / (Zf[bus_index] + 1e-20)
        Yfault[b, c] = -1 / (Zf[bus_index] + 1e-20)

        Yfault[c, c] = 2 / (Zf[bus_index] + 1e-20)
        Yfault[c, a] = -1 / (Zf[bus_index] + 1e-20)
        Yfault[c, b] = -1 / (Zf[bus_index] + 1e-20)

    # Three-Phase-to-Ground (LLLG)
    elif fault_type == FaultType.ph3:

        Yfault[a, a] = 1 / (Zf[bus_index] + 1e-20)
        Yfault[b, b] = 1 / (Zf[bus_index] + 1e-20)
        Yfault[c, c] = 1 / (Zf[bus_index] + 1e-20)

    else:
        raise Exception('Incorrect fault type definition.')

    Yfault_masked = Yfault[mask, :][:, mask]
    Yfault_masked = csc_matrix(Yfault_masked)

    Ybus_gen_csc, Ybus_gen = compute_ybus_generator(nc=nc)
    Ybus_gen_masked_csc = Ybus_gen_csc[mask, :][:, mask]

    Yloads = diags(Y_power_star_linear) + diags(Y_power_delta_linear) + diags(Y_current_linear)
    Ylinear = Ybus - Yloads + Yfault_masked + Ybus_gen_masked_csc

    Yloads = Y_power_star_linear + Y_power_delta_linear + Y_current_linear
    Yloads_expanded = expand_magnitudes(Yloads, bus_lookup)
    Spf_expanded = expand_magnitudes(Spf, bus_lookup)
    S = (Spf_expanded / (nc.Sbase/3) ) - Vpf * np.conj(Yloads_expanded * Vpf)
    idx3 = np.array([0, 1, 2])
    gen_idx = nc.generator_data.bus_idx
    n_buses = len(nc.generator_data.bus_idx)
    Inorton = np.zeros(shape=len(Vpf_masked), dtype=complex)
    for i in range(n_buses):
        U = Vpf[gen_idx[i] + idx3]
        Y = Ybus_gen[np.ix_(gen_idx[i] + idx3, gen_idx[i] + idx3)]
        I = np.conj( S[np.ix_(gen_idx[i] + idx3)] / U )
        E = U + np.linalg.inv(Y) @ I
        Inorton_i = Y @ E
        Inorton[np.ix_(gen_idx[i] + idx3)] = Inorton_i

    Usc = spsolve(Ylinear, Inorton)
    Usc_expanded = expand_magnitudes(Usc, bus_lookup)

    Ik_max = maximum_initial_shortcircuit_current(
        nc = nc,
        Zf = Zf[bus_index],
        faulted_bus = bus_index
    )

    """
    Results
    """
    # voltage, Sf, loading, losses, error, converged, Qpv
    results = ShortCircuitResults(n=nc.nbus,
                                  m=nc.nbr,
                                  n_hvdc=nc.nhvdc,
                                  bus_names=nc.bus_data.names,
                                  branch_names=nc.passive_branch_data.names,
                                  hvdc_names=nc.hvdc_data.names,
                                  bus_types=nc.bus_data.bus_types,
                                  area_names=None)

    Sfb, Stb, If, It, Vbranch, loading, losses = short_circuit_post_process_phases_abc(calculation_inputs=nc,
                                                                                    V_expanded=Usc_expanded,
                                                                                    branch_rates_expanded=expand3ph(nc.passive_branch_data.rates),
                                                                                    Yf=Yf,
                                                                                    Yt=Yt,
                                                                                    F_expanded=expand_indices_3ph(nc.passive_branch_data.F),
                                                                                    T_expanded=expand_indices_3ph(nc.passive_branch_data.T),
                                                                                    mask=mask,
                                                                                    branch_lookup=branch_lookup
                                                                                    )

    results.voltageA = Usc_expanded[0::3]
    results.SfA = Sfb[0::3]  # in MVA already
    results.StA = Stb[0::3]  # in MVA already
    results.IfA = If[0::3]  # in p.u.
    results.ItA = It[0::3]  # in p.u.
    results.VbranchA = Vbranch[0::3]
    results.loadingA = loading[0::3]
    results.lossesA = losses[0::3]

    results.voltageB = Usc_expanded[1::3]
    results.SfB = Sfb[1::3]  # in MVA already
    results.StB = Stb[1::3]  # in MVA already
    results.IfB = If[1::3]  # in p.u.
    results.ItB = It[1::3]  # in p.u.
    results.VbranchB = Vbranch[1::3]
    results.loadingB = loading[1::3]
    results.lossesB = losses[1::3]

    results.voltageC = Usc_expanded[2::3]
    results.SfC = Sfb[2::3]  # in MVA already
    results.StC = Stb[2::3]  # in MVA already
    results.IfC = If[2::3]  # in p.u.
    results.ItC = It[2::3]  # in p.u.
    results.VbranchC = Vbranch[2::3]
    results.loadingC = loading[2::3]
    results.lossesC = losses[2::3]

    return results