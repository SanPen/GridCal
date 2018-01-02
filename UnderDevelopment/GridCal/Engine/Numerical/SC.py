from numpy import zeros, sqrt, diag


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
    Z = diag(Zbus)
    # Voltage Source Contribution
    I_kI = zeros(n, dtype=complex)
    I_kI[bus_idx] = -1 * Vbus[bus_idx] / (Z[bus_idx] + Zf[bus_idx])

    # Current source contribution
    # I_kII = -1 * Zbus.dot(I_kC / Z[bus_idx])

    # Total current contribution
    # I_k = I_kI + I_kII
    I_k = I_kI
    # print(I_k)

    # voltage increment due to these currents
    incV = Zbus.dot(I_k) / len(bus_idx)

    V = Vbus + incV

    # Short circuit power in MVA
    # SCC = zeros(n, dtype=float)
    # SCC[bus_idx] = abs(Vbus[bus_idx]) * baseMVA / abs(Z[bus_idx])
    SCC = -I_k * Vbus * baseMVA

    return V, SCC