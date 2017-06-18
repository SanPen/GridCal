import numpy as np
np.set_printoptions(linewidth=320)
from numpy import angle, conj, exp, r_, Inf
from numpy.linalg import norm
from scipy.sparse.linalg import splu
import time


def FDPF(Vbus, Sbus, Ibus, Ybus, B1, B2, pq, pv, pqpv, tol=1e-9, max_it=100):
    """
    Fast decoupled power flow
    Args:
        Vbus:
        Sbus:
        Ibus:
        Ybus:
        B1:
        B2:
        pq:
        pv:
        pqpv:
        tol:

    Returns:

    """

    start = time.time()

    # set voltage vector for the iterations
    voltage = Vbus.copy()
    Va = angle(voltage)
    Vm = abs(voltage)

    # Factorize B1 and B2
    J1 = splu(B1[pqpv, :][:, pqpv])
    J2 = splu(B2[pq, :][:, pq])

    # evaluate initial mismatch
    Scalc = voltage * conj(Ybus * voltage - Ibus)
    mis = Scalc - Sbus  # complex power mismatch
    incP = mis[pqpv].real
    incQ = mis[pq].imag
    normP = norm(incP, Inf)
    normQ = norm(incQ, Inf)
    if normP < tol and normQ < tol:
        converged = True
    else:
        converged = False

    # iterate
    iter_ = 0
    while not converged and iter_ < max_it:

        iter_ += 1

        # solve voltage angles
        dVa = -J1.solve(incP)

        # update voltage
        Va[pqpv] = Va[pqpv] + dVa
        voltage = Vm * exp(1j * Va)

        # evaluate mismatch
        Scalc = voltage * conj(Ybus * voltage - Ibus)
        mis = Scalc - Sbus  # complex power mismatch
        incP = mis[pqpv].real
        incQ = mis[pq].imag
        normP = norm(incP, Inf)
        normQ = norm(incQ, Inf)

        if normP < tol and normQ < tol:
            converged = True

        else:
            # Solve voltage modules
            dVm = -J2.solve(incQ)

            # update voltage
            Vm[pq] = Vm[pq] + dVm
            voltage = Vm * exp(1j * Va)

            # evaluate mismatch
            Scalc = voltage * conj(Ybus * voltage - Ibus)
            mis = Scalc - Sbus  # complex power mismatch
            incP = mis[pqpv].real
            incQ = mis[pq].imag
            normP = norm(incP, Inf)
            normQ = norm(incQ, Inf)

            if normP < tol and normQ < tol:
                converged = True

    # evaluate F(x)
    Scalc = voltage * conj(Ybus * voltage - Ibus)
    mis = Scalc - Sbus  # complex power mismatch
    F = r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again

    # check for convergence
    normF = norm(F, Inf)

    end = time.time()
    elapsed = end - start

    return voltage, converged, normF, Scalc, iter_, elapsed