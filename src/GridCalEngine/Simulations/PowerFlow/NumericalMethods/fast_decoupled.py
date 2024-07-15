import numpy as np
from numpy import angle, conj, exp, r_, Inf
from numpy.linalg import norm
from scipy.sparse.linalg import splu
import time
import GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.enumerations import ReactivePowerControlMode
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import control_q_inside_method

np.set_printoptions(linewidth=320)


def FDPF(Vbus, S0, I0, Y0, Ybus, B1, B2, pv_, pq_, pqv_, p_, Qmin, Qmax, tol=1e-9, max_it=100,
         control_q=ReactivePowerControlMode.NoControl, ) -> NumericPowerFlowResults:
    """
    Fast decoupled power flow
    :param Vbus: array of initial voltages
    :param S0: array of power Injections
    :param I0: array of current Injections
    :param Y0: array of admittance Injections
    :param Ybus: Admittance matrix
    :param B1: B' matrix for the fast decoupled algorithm
    :param B2: B'' matrix for the fast decoupled algorithm
    :param pv_: Array with the indices of the PV buses
    :param pq_: Array with the indices of the PQ buses
    :param pqv_: Array with the indices of the PQV buses
    :param p_: Array with the indices of the P buses
    :param Qmin: Minimum voltage
    :param Qmax: Maximum voltage
    :param tol: desired tolerance
    :param max_it: maximum number of iterations
    :param control_q: Control Q method
    :return: NumericPowerFlowResults instance
    """

    start = time.time()

    # set voltage vector for the iterations
    voltage = Vbus.copy()
    Va = np.angle(voltage)
    Vm = np.abs(voltage)

    # set up indexing for updating V
    pq = pq_.copy()
    pv = pv_.copy()
    pqv = pqv_.copy()
    p = p_.copy()
    blck1_idx = np.r_[pv, pq, p, pqv]
    blck2_idx = np.r_[pq, p]
    blck3_idx = np.r_[pq, pqv]
    n_block1 = len(blck1_idx)

    # Factorize B1 and B2
    B1_factorization = splu(B1[np.ix_(blck1_idx, blck1_idx)])
    B2_factorization = splu(B2[np.ix_(blck3_idx, blck2_idx)])

    # evaluate initial mismatch
    Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)  # compute the ZIP power injection
    Scalc = voltage * np.conj(Ybus * voltage)
    mis = (Scalc - Sbus) / Vm  # complex power mismatch
    dP = mis[blck1_idx].real
    dQ = mis[blck3_idx].imag

    if n_block1 > 0:
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
            Va[blck1_idx] -= dVa
            voltage = Vm * exp(1j * Va)

            # evaluate mismatch
            # (Sbus does not change here since Vm is fixed ...)
            Scalc = cf.compute_power(Ybus, voltage)
            mis = (Scalc - Sbus) / Vm  # complex power mismatch
            dP = mis[blck1_idx].real
            dQ = mis[blck3_idx].imag
            normP = norm(dP, Inf)
            normQ = norm(dQ, Inf)

            if normP < tol and normQ < tol:
                converged = True
            else:
                # ----------------------------- Q iteration to update Vm ----------------------
                # Solve voltage modules
                dVm = B2_factorization.solve(dQ)

                # update voltage
                Vm[blck2_idx] -= dVm
                voltage = Vm * exp(1j * Va)

                # evaluate mismatch
                Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)  # compute the ZIP power injection
                Scalc = cf.compute_power(Ybus, voltage)
                mis = (Scalc - Sbus) / Vm  # complex power mismatch
                dP = mis[blck1_idx].real
                dQ = mis[blck3_idx].imag
                normP = norm(dP, Inf)
                normQ = norm(dQ, Inf)

                if normP < tol and normQ < tol:
                    converged = True

            # control of Q limits --------------------------------------------------------------------------------------
            # review reactive power limits
            # it is only worth checking Q limits with a low error
            # since with higher errors, the Q values may be far from realistic
            # finally, the Q control only makes sense if there are pv nodes
            if control_q != ReactivePowerControlMode.NoControl and normQ < 1e-2 and (len(pv) + len(p)) > 0:

                # check and adjust the reactive power
                # this function passes pv buses to pq when the limits are violated,
                # but not pq to pv because that is unstable
                changed, pv, pq, pqv, p = control_q_inside_method(Scalc, S0, pv, pq, pqv, p, Qmin, Qmax)

                if len(changed) > 0:
                    # adjust internal variables to the new pq|pv values
                    blck1_idx = np.r_[pv, pq, p, pqv]
                    blck2_idx = np.r_[pq, p]
                    blck3_idx = np.r_[pq, pqv]

                    # Factorize B1 and B2
                    B1_factorization = splu(B1[np.ix_(blck1_idx, blck1_idx)])
                    B2_factorization = splu(B2[np.ix_(blck3_idx, blck2_idx)])

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
