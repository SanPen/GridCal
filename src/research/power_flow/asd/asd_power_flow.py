# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.


from numpy import linalg
from scipy.sparse import issparse, csr_matrix as sparse, hstack as hstack_sp, vstack as vstack_sp, diags
from scipy.sparse.linalg import spsolve, splu
import scipy
scipy.ALLOW_THREADS = True
import time
import numpy as np

np.set_printoptions(precision=8, suppress=True, linewidth=320000)


def convert_to_reduced(pq, pv, vd, n):
    """
    Convert the PQ and PV lists of indices to PQ and PV lists of a reduced scheme
    :param pq: Array of PQ indices
    :param pv: Array of PV indices
    :param vd: Array of slack indices
    :param n: number of buses
    :return: Pq, PV reduced arrays
    """
    nsl_counted = np.zeros(n, dtype=int)
    compt = 0
    for i in range(n):
        if i in vd:
            compt += 1
        nsl_counted[i] = compt
    pq_ = pq - nsl_counted[pq]
    pv_ = pv - nsl_counted[pv]
    return pq_, pv_


def ASD1(Ybus, S0, V0, I0, pv, pq, vd, tol, max_it=15):
    """
    Alternate Search Directions Power Flow

    As defined in the paper:

        Unified formulation of a family of iterative solvers for power system analysis
        by Domenico Borzacchiello et. Al.

    :param Ybus: Admittance matrix
    :param S0: Power injections
    :param V0: Initial Voltage Vector
    :param I0: Current injections @V=1.0 p.u.
    :param pv: Array of PV bus indices
    :param pq: Array of PQ bus indices
    :param vd: Array of Slack bus indices
    :param tol: Tolerance
    :param max_it: Maximum number of iterations
    :return: V, converged, normF, Scalc, iterations, elapsed
    """
    start = time.time()

    # initialize
    V = V0.copy()
    Vset_pv = np.abs(V0[pv])
    Scalc = S0.copy()
    Scalc[pv] = Scalc[pv].real + 0j
    normF = 1e20
    iterations = 0
    converged = False
    n = len(V0)
    npq = len(pq)
    npv = len(pv)
    pqpv = np.r_[pq, pv]

    npqpv = len(pqpv)

    # kron
    Y11 = Ybus[pq, :][:, pq]
    Y12 = Ybus[pq, :][:, pv]
    Y21 = Ybus[pv, :][:, pq]
    Y22 = Ybus[pv, :][:, pv]
    Ykron = Y22 + Y21 * (spsolve(Y11, Y12))

    # reduced system
    Yred = vstack_sp((hstack_sp((Y11, Y12)), hstack_sp((Y21, Y22))))
    Sred = S0[pqpv]
    I0_red = I0[pqpv]

    Yslack = - Ybus[np.ix_(pqpv, vd)]  # yes, it is the negative of this
    Vslack = V0[vd]

    # compute alpha
    Vabs = np.ones(npqpv)
    alpha = sp.diags(np.conj(Sred) / (Vabs * Vabs))

    # compute Y-alpha
    Y_alpha = (Yred - alpha)

    # compute beta as a vector
    B = Y_alpha.diagonal()
    beta = diags(B)
    Y_beta = Yred - beta

    # get the first voltage approximation V0, or simply V(l
    Ivd = Yslack * Vslack  # slack currents
    V_l = spsolve(Y_alpha, Ivd)  # slack voltages influence
    V_l = V0[pqpv]

    gamma = 0.5

    while not converged and iterations < max_it:

        iterations += 1

        # Global step
        rhs_global = np.conj(Sred) / np.conj(V_l) - alpha * V_l + I0_red + Ivd
        V_l12 = spsolve(Y_alpha, rhs_global)

        # PV correction
        V_pv = V_l12[npq:]
        V_pv_abs = np.abs(V_pv)
        dV_l12 = (Vset_pv - V_pv_abs) * V_pv / V_pv_abs
        dI_l12 = Ykron * dV_l12
        dQ_l12 = (V_pv * np.conj(dI_l12)).imag  # correct the reactive power
        Sred[npq:] = Sred[npq:].real + 1j * (Sred[npq:].imag + gamma * dQ_l12)  # assign the reactive power
        V_l12[npq:] += dV_l12  # correct the voltage

        # local step
        A = (Y_beta * V_l12 - I0_red - Ivd) / B
        Sigma = - np.conj(Sred) / (A * np.conj(A) * B)
        U = (-1 - np.sqrt(1 - 4 * (Sigma.imag * Sigma.imag + Sigma.real))) / 2.0 + 1j * Sigma.imag
        V_l = U * A

        # Assign the reduced solution
        V[pq] = V_l[:npq]
        V[pv] = V_l[npq:]

        # compute the calculated power injection and the error of the voltage solution
        Scalc = V * np.conj(Ybus * V - I0)
        mis = Scalc - S0  # complex power mismatch
        mismatch = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again
        normF = np.linalg.norm(mismatch, np.Inf)

        converged = normF < tol

        print(normF)

    end = time.time()
    elapsed = end - start

    return V, converged, normF, Scalc, iterations, elapsed


def ASD2(Ybus, S0, V0, I0, pv, pq, vd, tol, max_it=15):
    """
    Alternate Search Directions Power Flow

    As defined in the paper:

        Unified formulation of a family of iterative solvers for power system analysis
        by Domenico Borzacchiello et. Al.

    Modifications:
    - Better reactive power computation

    :param Ybus: Admittance matrix
    :param S0: Power injections
    :param V0: Initial Voltage Vector
    :param I0: Current injections @V=1.0 p.u.
    :param pv: Array of PV bus indices
    :param pq: Array of PQ bus indices
    :param vd: Array of Slack bus indices
    :param tol: Tolerance
    :param max_it: Maximum number of iterations
    :return: V, converged, normF, Scalc, iterations, elapsed
    """
    start = time.time()

    # initialize
    V = V0.copy()
    Vset_pv = np.abs(V0[pv])
    Scalc = S0.copy()
    Scalc[pv] = Scalc[pv].real + 0j
    normF = 1e20
    iterations = 0
    converged = False
    n = len(V0)
    npq = len(pq)
    npv = len(pv)
    pqpv = np.r_[pq, pv]

    npqpv = len(pqpv)

    # kron
    Y11 = Ybus[pq, :][:, pq]
    Y12 = Ybus[pq, :][:, pv]
    Y21 = Ybus[pv, :][:, pq]
    Y22 = Ybus[pv, :][:, pv]

    # reduced system
    Yred = vstack_sp((hstack_sp((Y11, Y12)), hstack_sp((Y21, Y22))))
    Sred = S0[pqpv]
    I0_red = I0[pqpv]

    Yslack = - Ybus[np.ix_(pqpv, vd)]  # yes, it is the negative of this
    Vslack = V0[vd]

    # compute alpha
    Vabs = np.ones(npqpv)
    alpha = sp.diags(np.conj(Sred) / (Vabs * Vabs))

    # compute Y-alpha
    Y_alpha = (Yred - alpha)

    # compute beta as a vector
    B = Y_alpha.diagonal()
    beta = diags(B)
    Y_beta = Yred - beta

    # get the first voltage approximation V0, or simply V(l
    Ivd = Yslack * Vslack  # slack currents
    V_l = spsolve(Y_alpha, Ivd)  # slack voltages influence
    V_l = V0[pqpv]

    while not converged and iterations < max_it:

        iterations += 1

        # Global step
        rhs_global = np.conj(Sred) / np.conj(V_l) - alpha * V_l + I0_red + Ivd
        V_l12 = spsolve(Y_alpha, rhs_global)

        # PV correction (using Lynn's formulation)
        V_pv = V_l12[npq:]
        V_l12[npq:] = V_pv * Vset_pv / np.abs(V_pv)
        V[pq] = V_l12[:npq]
        V[pv] = V_l12[npq:]
        Qpv = (V[pv] * np.conj((Ybus[pv, :] * V))).imag
        Sred[npq:] = Sred[npq:].real + 1j * Qpv

        # local step
        A = (Y_beta * V_l12 - I0_red - Ivd) / B
        Sigma = - np.conj(Sred) / (A * np.conj(A) * B)
        U = (-1 - np.sqrt(1 - 4 * (Sigma.imag * Sigma.imag + Sigma.real))) / 2.0 + 1j * Sigma.imag
        V_l = U * A

        # Assign the reduced solution
        V[pq] = V_l[:npq]
        V[pv] = V_l[npq:]

        # compute the calculated power injection and the error of the voltage solution
        Scalc = V * np.conj(Ybus * V - I0)
        mis = Scalc - S0  # complex power mismatch
        mismatch = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again
        normF = np.linalg.norm(mismatch, np.Inf)

        converged = normF < tol

        print(normF)

    end = time.time()
    elapsed = end - start

    return V, converged, normF, Scalc, iterations, elapsed


def ASD3(Ybus, S0, V0, I0, pv, pq, vd, tol, max_it=15):
    """
    Alternate Search Directions Power Flow

    As defined in the paper:

        Unified formulation of a family of iterative solvers for power system analysis
        by Domenico Borzacchiello et. Al.

    Modifications:
    - Better reactive power computation
    - No need to partition the buses in PQ|PV
    - No need to perform the partitioning of Y, nor the Kron reduction for the PV buses correction

    :param Ybus: Admittance matrix
    :param S0: Power injections
    :param V0: Initial Voltage Vector
    :param I0: Current injections @V=1.0 p.u.
    :param pv: Array of PV bus indices
    :param pq: Array of PQ bus indices
    :param vd: Array of Slack bus indices
    :param tol: Tolerance
    :param max_it: Maximum number of iterations
    :return: V, converged, normF, Scalc, iterations, elapsed
    """
    start = time.time()

    # initialize
    V = V0.copy()
    Vset_pv = np.abs(V0[pv])
    Scalc = S0.copy()
    normF = 1e20
    iterations = 0
    converged = False
    n = len(V0)
    pqpv = np.r_[pq, pv]
    pqpv.sort()

    # Create the zero-based indices in the internal reduced scheme
    pq_, pv_ = convert_to_reduced(pq, pv, vd, n)

    # reduced system
    Yred = Ybus[np.ix_(pqpv, pqpv)]
    Sred = S0[pqpv]
    I0_red = I0[pqpv]

    Yslack = - Ybus[np.ix_(pqpv, vd)]  # yes, it is the negative of this
    Vslack = V0[vd]

    # compute alpha
    # Vabs = np.abs(Vslack)
    # alpha = sp.diags(np.conj(Sred) / (Vabs * Vabs))
    alpha = -sp.linalg.inv(sp.diags(Yred.diagonal()).tocsc())

    # compute Y-alpha
    Y_alpha = (Yred - alpha).tocsc()

    # compute beta as a vector
    B = Yred.diagonal()
    beta = diags(B)
    Y_beta = Yred - beta

    # get the first voltage approximation V0, or simply V(l
    Ivd = Yslack * Vslack  # slack currents
    V_l = spsolve(Y_alpha, Ivd)  # slack voltages influence

    while not converged and iterations < max_it:

        # Global step
        rhs_global = np.conj(Sred) / np.conj(V_l) - alpha * V_l + I0_red + Ivd
        V_l12 = spsolve(Y_alpha, rhs_global)

        # Better PV correction than the paper, using Lynn's formulation
        V_pv = V_l12[pv_]
        V_l12[pv_] = V_pv * Vset_pv / np.abs(V_pv)  # compute the corrected bus voltage
        V[pqpv] = V_l12  # Assign the reduced solution

        # compute the reactive power at the PV nodes (actual scheme)
        Qpv = (V[pv] * np.conj((Ybus[pv, :] * V - I0[pv]))).imag
        Sred[pv_] = Sred[pv_].real + 1j * Qpv  # assign the PV reactive power in the reduced scheme

        # local step
        A = (Y_beta * V_l12 - I0_red - Ivd) / B
        Sigma = - np.conj(Sred) / (A * np.conj(A) * B)
        U = (-1.0 - np.sqrt(1.0 - 4.0 * (Sigma.imag * Sigma.imag + Sigma.real))) / 2.0 + 1.0j * Sigma.imag
        V_l = U * A

        # Assign the reduced solution
        V[pqpv] = V_l

        # compute the calculated power injection and the error of the voltage solution
        Scalc = V * np.conj(Ybus * V - I0)
        mis = Scalc - S0  # complex power mismatch
        mismatch = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again
        normF = 0.5 * np.dot(mismatch, mismatch)  #np.linalg.norm(mismatch, np.Inf)

        converged = normF < tol

        print(normF)
        iterations += 1

    end = time.time()
    elapsed = end - start

    return V, converged, normF, Scalc, iterations, elapsed


########################################################################################################################
#  MAIN
########################################################################################################################
if __name__ == "__main__":
    from GridCal.Engine import *

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE14_from_raw.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 30 Bus.gridcal'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
    # fname ='/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Brazil11_loading05.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 5 Bus.xlsx'

    grid = FileOpen(fname).open()

    nc = compile_snapshot_circuit(grid)
    islands = split_into_islands(nc)
    circuit = islands[0]

    print('\nYbus:\n', circuit.Ybus.todense())
    print('\nYseries:\n', circuit.Yseries.todense())
    print('\nYshunt:\n', circuit.Yshunt)
    print('\nSbus:\n', circuit.Sbus)
    print('\nIbus:\n', circuit.Ibus)
    print('\nVbus:\n', circuit.Vbus)
    print('\ntypes:\n', circuit.bus_types)
    print('\npq:\n', circuit.pq)
    print('\npv:\n', circuit.pv)
    print('\nvd:\n', circuit.vd)

    import time
    print('ASD')
    start_time = time.time()
    V1, converged_, err, S, iter_, elapsed_ = ASD3(Ybus=circuit.Ybus,
                                                   S0=circuit.Sbus,
                                                   V0=circuit.Vbus,
                                                   I0=circuit.Ibus,
                                                   pv=circuit.pv,
                                                   pq=circuit.pq,
                                                   vd=circuit.vd,
                                                   tol=1e-9,
                                                   max_it=20)

    print("--- %s seconds ---" % (time.time() - start_time))
    print('V:\n', np.abs(V1))
    print('error: \t', err)
