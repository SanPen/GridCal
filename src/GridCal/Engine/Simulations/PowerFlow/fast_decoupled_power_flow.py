import numpy as np
np.set_printoptions(linewidth=320)
from numpy import angle, conj, exp, r_, Inf
from numpy.linalg import norm
from scipy.sparse.linalg import splu
import time


def FDPF(bus_voltages, complex_bus_powers, current_injections_and_extractions, bus_admittances, B1, B2, pq_bus_indices, pv_bus_indices, pq_and_pv_bus_indices, tolerance=1e-9, max_iterations=100):
    """
    Fast decoupled power flow
    Args:
        bus_voltages:
        complex_bus_powers:
        current_injections_and_extractions:
        bus_admittances:
        B1:
        B2:
        pq_bus_indices:
        pv_bus_indices:
        pq_and_pv_bus_indices:
        tolerance:

    Returns:

    """

    start = time.time()

    # set voltage vector for the iterations
    voltage = bus_voltages.copy()
    Va = angle(voltage)
    Vm = abs(voltage)

    # Factorize B1 and B2
    J1 = splu(B1[pq_and_pv_bus_indices, :][:, pq_and_pv_bus_indices])
    J2 = splu(B2[pq_bus_indices, :][:, pq_bus_indices])

    # evaluate initial mismatch
    Scalc = voltage * conj(bus_admittances * voltage - current_injections_and_extractions)
    mis = Scalc - complex_bus_powers  # complex power mismatch
    incP = mis[pq_and_pv_bus_indices].real
    incQ = mis[pq_bus_indices].imag

    if len(pq_and_pv_bus_indices) > 0:
        normP = norm(incP, Inf)
        normQ = norm(incQ, Inf)
        if normP < tolerance and normQ < tolerance:
            converged = True
        else:
            converged = False

        # iterate
        iter_ = 0
        while not converged and iter_ < max_iterations:

            iter_ += 1

            # solve voltage angles
            dVa = -J1.solve(incP)

            # update voltage
            Va[pq_and_pv_bus_indices] = Va[pq_and_pv_bus_indices] + dVa
            voltage = Vm * exp(1j * Va)

            # evaluate mismatch
            Scalc = voltage * conj(bus_admittances * voltage - current_injections_and_extractions)
            mis = Scalc - complex_bus_powers  # complex power mismatch
            incP = mis[pq_and_pv_bus_indices].real
            incQ = mis[pq_bus_indices].imag
            normP = norm(incP, Inf)
            normQ = norm(incQ, Inf)

            if normP < tolerance and normQ < tolerance:
                converged = True

            else:
                # Solve voltage modules
                dVm = -J2.solve(incQ)

                # update voltage
                Vm[pq_bus_indices] = Vm[pq_bus_indices] + dVm
                voltage = Vm * exp(1j * Va)

                # evaluate mismatch
                Scalc = voltage * conj(bus_admittances * voltage - current_injections_and_extractions)
                mis = Scalc - complex_bus_powers  # complex power mismatch
                incP = mis[pq_and_pv_bus_indices].real
                incQ = mis[pq_bus_indices].imag
                normP = norm(incP, Inf)
                normQ = norm(incQ, Inf)

                if normP < tolerance and normQ < tolerance:
                    converged = True

        # evaluate F(x)
        Scalc = voltage * conj(bus_admittances * voltage - current_injections_and_extractions)
        mis = Scalc - complex_bus_powers  # complex power mismatch
        F = r_[mis[pv_bus_indices].real, mis[pq_bus_indices].real, mis[pq_bus_indices].imag]  # concatenate again

        # check for convergence
        normF = norm(F, Inf)
    else:
        normF = 0
        converged = True
        iter_ = 0

    end = time.time()
    elapsed = end - start

    return voltage, converged, normF, Scalc, iter_, elapsed
