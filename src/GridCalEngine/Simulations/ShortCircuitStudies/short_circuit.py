# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
from typing import Tuple
from scipy.sparse.linalg import spsolve
from scipy.sparse.linalg import inv
from scipy.sparse import csc_matrix
from GridCalEngine.enumerations import FaultType
from GridCalEngine.basic_structures import CxVec, Vec


def short_circuit_3p(bus_idx: int, Ybus: csc_matrix, Vbus: CxVec, Vnom: Vec, Zf: CxVec, baseMVA: float) -> Tuple[
    CxVec, float, float]:
    """
    Executes a 3-phase balanced short circuit study
    :param bus_idx: Index of the bus at which the short circuit is being studied
    :param Ybus: Admittance matrix
    :param Vbus: Voltages of the buses in the steady state
    :param Vnom: Nominal Voltages of the buses (kV)
    :param Zf: Fault impedance array
    :param baseMVA: 
    :return: Voltages after the short circuit (p.u.), Short circuit power in MVA
    Computed as V = Vpre + V increment, where Vpre is the power flow solution and
    V increment is the fault contribution
    The short-circuit power is V_i^2 / Z[i,i], it will tend to infinity if the
    generator is ideal (r1 and x1 approach 0)
    """

    n = len(Vbus)

    tmp = np.zeros(n)
    tmp[bus_idx] = 1
    Zcol = spsolve(Ybus, tmp)
    Zii = Zcol[bus_idx]

    Ifvec = np.zeros(n, dtype=complex)
    Ifvec[bus_idx] = Vbus[bus_idx] / (Zii + Zf[bus_idx])

    Av = - spsolve(Ybus, Ifvec)
    V = Vbus + Av

    idx_buses = range(n)
    Ibase = baseMVA / Vnom[idx_buses]
    ICC = Ibase * Vbus[idx_buses] / Zii
    SCC = baseMVA * Vbus[idx_buses] * Vbus[idx_buses] / Zii

    return V, SCC, ICC


def short_circuit_unbalance(bus_idx: int,
                            Y0: csc_matrix,
                            Y1: csc_matrix,
                            Y2: csc_matrix,
                            Vbus: CxVec,
                            Vnom: Vec,
                            Zf: CxVec,
                            fault_type: FaultType,
                            baseMVA) -> Tuple[CxVec, CxVec, CxVec, CxVec, CxVec]:
    """
    Executes the unbalanced short circuits (LG, LL, LLG types)

    :param bus_idx: bus where the fault is caused
    :param Y0: Admittance matrix for the zero sequence
    :param Y1: Admittance matrix for the positive sequence
    :param Y2: Admittance matrix for the negative sequence
    :param Vbus: pre-fault voltage (positive sequence)
    :param Vnom: nominal voltage (kV)
    :param Zf: fault impedance
    :param fault_type: type of unbalanced fault
    :param baseMVA: base MVA (100 MVA)
    :return: V0, V1, V2 for all buses
    """

    n = len(Vbus)

    # solve the fault
    Vpr = Vbus[bus_idx]

    tmp = np.zeros(n)
    tmp[bus_idx] = 1
    Zth0 = spsolve(Y0, tmp)[bus_idx]
    Zth1 = spsolve(Y1, tmp)[bus_idx]
    Zth2 = spsolve(Y2, tmp)[bus_idx]

    Zflt = Zf[bus_idx]

    if fault_type == FaultType.LG:
        I0 = Vpr / (Zth0 + Zth1 + Zth2 + 3 * Zflt)
        I1 = I0
        I2 = I0
    elif fault_type == FaultType.LL:  # between phases b and c
        I0 = 0
        I1 = Vpr / (Zth1 + Zth2 + Zflt)
        I2 = - I1
    elif fault_type == FaultType.LLG:  # between phases b and c
        I1 = Vpr / (Zth1 + Zth2 * (Zth0 + 3 * Zflt) / (Zth2 + Zth0 + 3 * Zflt))
        I0 = -I1 * Zth2 / (Zth2 + Zth0 + 3 * Zflt)
        I2 = -I1 * (Zth0 + 3 * Zflt) / (Zth2 + Zth0 + 3 * Zflt)
    else:
        raise Exception('Unknown unbalanced fault type')

    # obtain the post fault voltages
    I0_vec = np.zeros(n, dtype=complex)
    I1_vec = np.zeros(n, dtype=complex)
    I2_vec = np.zeros(n, dtype=complex)

    I0_vec[bus_idx] = I0
    I1_vec[bus_idx] = I1
    I2_vec[bus_idx] = I2

    V0_fin = - spsolve(Y0, I0_vec)
    V1_fin = Vbus - spsolve(Y1, I1_vec)
    V2_fin = - spsolve(Y2, I2_vec)

    SCC = np.zeros_like(Vbus)
    ICC = np.zeros_like(Vbus)
    Ibase = baseMVA / Vnom[bus_idx]
    ICC[bus_idx] = Ibase * V1_fin[bus_idx] / Zth1
    SCC[bus_idx] = baseMVA * V1_fin[bus_idx] * V1_fin[bus_idx] / Zth1

    return V0_fin, V1_fin, V2_fin, SCC, ICC


# def short_circuit_phases():
#