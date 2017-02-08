from numpy import zeros


def short_circuit_3p(bus_idx, Zbus, Vbus, Zf=0.0):
    """
    Executes a 3-phase balanced short circuit study
    Args:
        bus_idx: Index of the bus at which the short circuit is being studied
        Zbus: Inverse of the admittance matrix
        Vbus: Voltages of the buses in the steady state
        Zf: Fault impedance

    Returns: Voltages after the short circuit

    """
    n = len(Vbus)
    I = zeros(n, dtype=complex)
    I[bus_idx] = -1 * Vbus[bus_idx] / (Zbus[bus_idx, bus_idx] + Zf)

    incV = Zbus.dot(I)

    V = Vbus + incV

    return V