import numpy as np
from numpy import angle, conj, exp, r_, Inf
from numpy.linalg import norm
from scipy.sparse.linalg import splu
import time
import GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults

np.set_printoptions(linewidth=320)


def FDPF(Vbus, S0, I0, Y0, Ybus, B1, B2, pq, pv, pqpv, tol=1e-9, max_it=100) -> NumericPowerFlowResults:
    """
    Fast decoupled power flow
    :param Vbus: array of initial voltages
    :param S0: array of power Injections
    :param I0: array of current Injections
    :param Y0: array of admittance Injections
    :param Ybus: Admittance matrix
    :param B1: B' matrix for the fast decoupled algorithm
    :param B2: B'' matrix for the fast decoupled algorithm
    :param pq: array of pq indices
    :param pv: array of pv indices
    :param pqpv: array of pqpv indices
    :param tol: desired tolerance
    :param max_it: maximum number of iterations
    :return: NumericPowerFlowResults instance
    """

    start = time.time()
    # pvpq = np.r_[pv, pq]

    # set voltage vector for the iterations
    voltage = Vbus.copy()
    Va = np.angle(voltage)
    Vm = np.abs(voltage)

    # Factorize B1 and B2
    B1_factorization = splu(B1[np.ix_(pqpv, pqpv)])
    B2_factorization = splu(B2[np.ix_(pq, pq)])

    # evaluate initial mismatch
    Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)  # compute the ZIP power injection
    Scalc = voltage * np.conj(Ybus * voltage)
    mis = (Scalc - Sbus) / Vm  # complex power mismatch
    dP = mis[pqpv].real
    dQ = mis[pq].imag

    if len(pqpv) > 0:
        normP = norm(dP, Inf)
        normQ = norm(dQ, Inf)
        converged = normP < tol and normQ < tol

        # iterate
        iter_ = 0
        while not converged and iter_ < max_it:

            iter_ += 1

            # ----------------------------- P iteration to update Va ----------------------
            # solve voltage angles
            dVa = B1_factorization.solve(dP)

            # update voltage
            Va[pqpv] -= dVa
            voltage = Vm * exp(1j * Va)

            # evaluate mismatch
            # (Sbus does not change here since Vm is fixed ...)
            Scalc = cf.compute_power(Ybus, voltage)
            mis = (Scalc - Sbus) / Vm  # complex power mismatch
            dP = mis[pqpv].real
            dQ = mis[pq].imag
            normP = norm(dP, Inf)
            normQ = norm(dQ, Inf)

            if normP < tol and normQ < tol:
                converged = True
            else:
                # ----------------------------- Q iteration to update Vm ----------------------
                # Solve voltage modules
                dVm = B2_factorization.solve(dQ)

                # update voltage
                Vm[pq] -= dVm
                voltage = Vm * exp(1j * Va)

                # evaluate mismatch
                Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)  # compute the ZIP power injection
                Scalc = cf.compute_power(Ybus, voltage)
                mis = (Scalc - Sbus) / Vm  # complex power mismatch
                dP = mis[pqpv].real
                dQ = mis[pq].imag
                normP = norm(dP, Inf)
                normQ = norm(dQ, Inf)

                if normP < tol and normQ < tol:
                    converged = True

        F = r_[dP, dQ]  # concatenate again
        normF = norm(F, Inf)

    else:
        converged = True
        iter_ = 0
        normF = 0

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V=voltage,
                                   converged=converged,
                                   norm_f=normF,
                                   Scalc=Scalc,
                                   ma=None,
                                   theta=None,
                                   Beq=None,
                                   Ybus=None, Yf=None, Yt=None,
                                   iterations=iter_,
                                   elapsed=elapsed)


