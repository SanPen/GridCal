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

    """
    n = len(Vbus)
    Z = Zbus[bus_idx, :][:, bus_idx]  # Z_B in documentation

    # Voltage Source Contribution
    I_kI = np.zeros(n, dtype=complex)
    Z.flat[::len(bus_idx) + 1] += Zf[bus_idx]  # add Zf to diagonals of Z_B
    I_kI[bus_idx] = -1 * np.linalg.solve(Z, Vbus[bus_idx])

    # Current source contribution
    # I_kII = -1 * Zbus.dot(I_kC / Z[elm_idx])

    # Total current contribution
    # I_k = I_kI + I_kII
    I_k = I_kI

    # voltage increment due to these currents
    incV = Zbus.dot(I_k)

    V = Vbus + incV

    # Short circuit power in MVA
    SCC = -I_k * Vbus * baseMVA

    return V, SCC