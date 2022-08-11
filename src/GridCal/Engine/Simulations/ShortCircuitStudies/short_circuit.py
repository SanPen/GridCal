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