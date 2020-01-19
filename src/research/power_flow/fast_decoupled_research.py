import numpy as np
from numpy import angle, conj, exp, r_, Inf
from numpy.linalg import norm
from scipy.sparse.linalg import splu
import time
np.set_printoptions(linewidth=320)


def FDPF(Vbus, Sbus, Ibus, Ybus, B1, B2, pq, pv, pqpv, tol=1e-9, max_it=100):
    """
    Fast decoupled power flow
    :param Vbus:
    :param Sbus:
    :param Ibus:
    :param Ybus:
    :param B1:
    :param B2:
    :param pq:
    :param pv:
    :param pqpv:
    :param tol:
    :param max_it:
    :return:
    """

    start = time.time()

    error_list = list()

    # set voltage vector for the iterations
    voltage = Vbus.copy()
    Va = np.angle(voltage)
    Vm = np.abs(voltage)

    # Factorize B1 and B2
    J1 = splu(B1[np.ix_(pqpv, pqpv)])
    J2 = splu(B2[np.ix_(pq, pq)])

    # evaluate initial mismatch
    Scalc = voltage * np.conj(Ybus * voltage - Ibus)
    mis = (Scalc - Sbus) / Vm  # complex power mismatch
    dP = mis[pqpv].real
    dQ = mis[pq].imag

    # compute and store error
    F = r_[dP, dQ]
    normF = norm(F, Inf)
    error_list.append(normF)

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
            dVa = J1.solve(dP)

            # update voltage
            Va[pqpv] -= dVa
            voltage = Vm * exp(1j * Va)

            # evaluate mismatch
            Scalc = voltage * conj(Ybus * voltage - Ibus)
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
                dVm = J2.solve(dQ)

                # update voltage
                Vm[pq] -= dVm
                voltage = Vm * exp(1j * Va)

                # evaluate mismatch
                Scalc = voltage * conj(Ybus * voltage - Ibus)
                mis = (Scalc - Sbus) / Vm  # complex power mismatch
                dP = mis[pqpv].real
                dQ = mis[pq].imag
                normP = norm(dP, Inf)
                normQ = norm(dQ, Inf)

                if normP < tol and normQ < tol:
                    converged = True

            # compute and store error
            F = r_[dP, dQ]
            normF = norm(F, Inf)
            error_list.append(normF)

    else:
        converged = True
        iter_ = 0

    F = r_[dP, dQ]  # concatenate again
    normF = norm(F, Inf)

    end = time.time()
    elapsed = end - start

    return voltage, converged, normF, Scalc, iter_, elapsed, error_list


if __name__ == '__main__':

    fname = r'/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 9 Bus.gridcal'

    from matplotlib import pyplot as plt
    from GridCal.Engine import FileOpen

    circuit = FileOpen(fname).open()
    nc = circuit.compile()
    islands = nc.compute()
    island = islands[0]

    voltage, converged, normF, Scalc, iter_, elapsed, err_lst = FDPF(Vbus=island.Vbus,
                                                                     Sbus=island.Sbus,
                                                                     Ibus=island.Ibus,
                                                                     Ybus=island.Ybus,
                                                                     B1=island.B1,
                                                                     B2=island.B2,
                                                                     pq=island.pq,
                                                                     pv=island.pv,
                                                                     pqpv=island.pqpv,
                                                                     tol=1e-9,
                                                                     max_it=100)

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.set_yscale('log')
    ax.plot(err_lst)

    print(np.abs(voltage))
    print('iter:', iter_)
    print('Error:', normF)

    plt.show()