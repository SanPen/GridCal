import numpy as np


def short_circuit_3p(bus_idx, Zbus, Vbus, Zf, baseMVA):
    """
    Executes a 3-phase balanced short circuit study
    Args:
        bus_idx: Index of the bus at which the short circuit is being studied
        Zbus: Inverse of the admittance matrix
        Vbus: Voltages of the buses in the steady state
        Zf: Fault impedance array

    Returns: Voltages after the short circuit (p.u.), Short circuit power in MVA
    Computed as V = Vpre + V increment, where Vpre is the power flow solution and
    V increment is the fault contribution
    The short-circuit power is V_i^2 / Z[i,i], it will tend to infinity if the
    generator is ideal (r1 and x1 approach 0)

    """
    n = len(Vbus)

    Ifvec = np.zeros(n, dtype=complex)
    Ifvec[bus_idx] = Vbus[bus_idx] / (Zbus[bus_idx, bus_idx] + Zf[bus_idx])
    
    Av = - Zbus @ Ifvec
    V = Vbus + Av

    idx_buses = range(n)
    SCC = baseMVA * np.power(np.abs(Vbus[idx_buses]), 2) / np.abs(Zbus[idx_buses, idx_buses])

    return V, SCC


def short_circuit_unbalance(bus_idx, Z0, Z1, Z2, Vbus, Zf, fault_type):
    """
    Executes the unbalanced short circuits (LG, LL, LLG types)

    :param bus_idx: bus where the fault is caused
    :param Z0: impedance matrix for the zero sequence
    :param Z1: impedance matrix for the positive sequence
    :param Z2: impedance matrix for the negative sequence
    :param Vbus: prefault voltage (positive sequence)
    :param Zf: fault impedance
    :return: V0, V1, V2 for all buses
    """

    n = len(Vbus)

    # solve the fault
    Vpr = Vbus[bus_idx]
    Zth0 = Z0[bus_idx, bus_idx]
    Zth1 = Z1[bus_idx, bus_idx]
    Zth2 = Z2[bus_idx, bus_idx]

    if fault_type == 'LG':
        I0 = Vpr / (Zth0 + Zth1 + Zth2 + 3 * Zf)
        I1 = I0
        I2 = I0
    elif fault_type == 'LL':  # between phases b and c
        I0 = 0
        I1 = Vpr / (Zth1 + Zth2 + Zf)
        I2 = - I1
    elif fault_type == 'LLG':  # between phases b and c
        I1 = Vpr / (Zth1 + Zth2 * (Zth0 + 3 * Zf) / (Zth2 + Zth0 + 3 * Zf))
        I0 = -I1 * Zth2 / (Zth2 + Zth0 + 3 * Zf)
        I2 = -I1 * (Zth0 + 3 * Zf) / (Zth2 + Zth0 + 3 * Zf)
    else:
        print('Unknown fault type')
    
    # obtain the post fault voltages
    Vpre_ok = np.zeros((n, 1), dtype=complex)
    I0_vec = np.zeros((n, 1), dtype=complex)
    I1_vec = np.zeros((n, 1), dtype=complex)
    I2_vec = np.zeros((n, 1), dtype=complex)

    Vpre_ok[:, 0] = Vbus
    I0_vec[bus_idx, 0] = I0
    I1_vec[bus_idx, 0] = I1
    I2_vec[bus_idx, 0] = I2

    V0_fin = - Z0 @ I0_vec
    V1_fin = Vpre_ok - Z1 @ I1_vec
    V2_fin = - Z2 @ I2_vec
    
    return V0_fin, V1_fin, V2_fin