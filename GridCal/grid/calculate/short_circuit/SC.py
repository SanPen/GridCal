from numpy import zeros, sqrt


def short_circuit_3p(bus_idx, Zbus, Vbus, Zf, baseMVA):
    """
    Executes a 3-phase balanced short circuit study
    Args:
        bus_idx: Index of the bus at which the short circuit is being studied
        Zbus: Inverse of the admittance matrix
        Vll: line-line voltage array (equals the nominal voltages of the buses)
        Vbus: Voltages of the buses in the steady state
        Zf: Fault impedance array

    Returns: Voltages after the short circuit, Short circuit power in MVA

    """
    n = len(Vbus)
    Ipu = zeros(n, dtype=complex)
    Ipu[bus_idx] = -1 * Vbus[bus_idx] / (Zbus[bus_idx, bus_idx] + Zf[bus_idx])

    incV = Zbus.dot(Ipu)

    V = Vbus + incV

    SCC = zeros(n, dtype=float)
    SCC[bus_idx] = abs(Vbus[bus_idx]) * baseMVA / abs(Zbus[bus_idx, bus_idx])

    return V, SCC