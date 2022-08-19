import numpy as np
import scipy.sparse as sp
from GridCal.Engine.Devices.enumerations import FaultType


def short_circuit_3p(bus_idx, Ybus, Vbus, Zf, baseMVA):
    """
    Executes a 3-phase balanced short circuit study
    Args:
        bus_idx: Index of the bus at which the short circuit is being studied
        Ybus: Admittance matrix
        Vbus: Voltages of the buses in the steady state
        Zf: Fault impedance array

    Returns: Voltages after the short circuit (p.u.), Short circuit power in MVA
    Computed as V = Vpre + V increment, where Vpre is the power flow solution and
    V increment is the fault contribution
    The short-circuit power is V_i^2 / Z[i,i], it will tend to infinity if the
    generator is ideal (r1 and x1 approach 0)

    """
    n = len(Vbus)

    # to compute the complete inverse is unnecessary
    # Zbus = inv(Ybus_gen_batt.tocsc()).toarray()

    tmp = np.zeros(n)
    tmp[bus_idx] = 1
    Zcol = sp.linalg.spsolve(Ybus, tmp)
    Zii = Zcol[bus_idx]

    Ifvec = np.zeros(n, dtype=complex)
    Ifvec[bus_idx] = Vbus[bus_idx] / (Zii + Zf[bus_idx])
    
    Av = - sp.linalg.spsolve(Ybus, Ifvec)
    V = Vbus + Av

    idx_buses = range(n)
    SCC = baseMVA * Vbus[idx_buses] * Vbus[idx_buses] / Zii

    return V, SCC


def short_circuit_unbalance(bus_idx, Y0, Y1, Y2, Vbus, Zf, fault_type):
    """
    Executes the unbalanced short circuits (LG, LL, LLG types)

    :param bus_idx: bus where the fault is caused
    :param Y0: Admittance matrix for the zero sequence
    :param Y1: Admittance matrix for the positive sequence
    :param Y2: Admittance matrix for the negative sequence
    :param Vbus: pre-fault voltage (positive sequence)
    :param Zf: fault impedance
    :param fault_type: type of unbalanced fault
    :return: V0, V1, V2 for all buses
    """

    n = len(Vbus)

    # solve the fault
    Vpr = Vbus[bus_idx]

    tmp = np.zeros(n)
    tmp[bus_idx] = 1
    Zth0 = sp.linalg.spsolve(Y0, tmp)[bus_idx]
    Zth1 = sp.linalg.spsolve(Y1, tmp)[bus_idx]
    Zth2 = sp.linalg.spsolve(Y2, tmp)[bus_idx]

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

    V0_fin = - sp.linalg.spsolve(Y0, I0_vec)
    V1_fin = Vbus - sp.linalg.spsolve(Y1, I1_vec)
    V2_fin = - sp.linalg.spsolve(Y2, I2_vec)
    
    return V0_fin, V1_fin, V2_fin