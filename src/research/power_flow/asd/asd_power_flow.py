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


from numpy import array, angle, exp, linalg, r_, Inf, conj, diag, asmatrix, asarray, zeros_like, zeros, complex128, \
empty, float64, int32, arange
from scipy.sparse import issparse, csr_matrix as sparse, hstack as hstack_sp, vstack as vstack_sp, diags
from scipy.sparse.linalg import spsolve, splu
import scipy
scipy.ALLOW_THREADS = True
import time
import numpy as np

np.set_printoptions(precision=8, suppress=True, linewidth=320000)


def ASD1(Ybus, Yseries, Ysh0, S0, V0, I0, pv, pq, pqpv, vd, tol, max_it=15):
    """

    :param Ybus:
    :param S0:
    :param V0:
    :param I0:
    :param pv:
    :param pq:
    :param pqpv:
    :param vd:
    :param tol:
    :param max_it:
    :return:
    """
    start = time.time()

    # initialize
    V = V0.copy()
    Scalc = S0.copy()
    normF = 1e20
    iterations = 0
    converged = False

    # reduced system
    Y = Ybus[pqpv, :][:, pqpv]
    Sred = Scalc[pqpv]
    I0_red = I0[pqpv]

    # get the first voltage approximation V0, or simply V(l
    Ivd = Ybus[pqpv, :][:, vd].dot(V[vd])  # slack currents
    V_l = spsolve(Y, -Ivd)  # slack voltages influence

    # compute alpha
    Vabs = np.abs(V_l)
    alpha = sp.diags(np.conj(S0[pqpv]) / np.conj(Vabs * Vabs))

    # compute Y-alpha
    Y_alpha = (Y - alpha)
    Y_alpha_fact = factorized(Y_alpha)

    # compute beta as a vector
    B = Y_alpha.diagonal()
    beta = diags(B)
    Y_beta = Y - beta

    while not converged and iterations < max_it:

        # Global step
        rhs_global = np.conj(Sred) / np.conj(V_l) - alpha * V_l + I0_red + Ivd
        V_l12 = Y_alpha_fact(rhs_global)

        # local step
        A = (Y_beta * V_l12 - I0_red - Ivd) / B
        Sigma = -np.conj(Sred) / (A * np.conj(A) * B)
        U = (-1 + np.sqrt(1 - 4 * (Sigma.imag * Sigma.imag + Sigma.real))) / 2.0 - 1j * Sigma.imag
        V_l = U * A  # it is the new V_l

        # Assign the reduced solution
        V[pqpv] = V_l

        # compute the error
        error = np.max(np.abs(V_l12 - V_l))
        converged = error < tol

        # compute the calculated power injection and the error of the voltage solution
        Scalc = V * np.conj(Ybus * V - I0)
        Sred = Scalc[pqpv]

        mis = Scalc - S0  # complex power mismatch
        mismatch = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again
        normF = np.linalg.norm(mismatch, np.Inf)
        print(normF)
        iterations += 1

    end = time.time()
    elapsed = end - start

    return V, converged, normF, Scalc, iterations, elapsed


def ASD2(Ybus, Yseries, Ysh0, S0, V0, I0, pv, pq, pqpv, vd, tol, max_it=15):
    """

    :param Ybus:
    :param S0:
    :param V0:
    :param I0:
    :param pv:
    :param pq:
    :param pqpv:
    :param vd:
    :param tol:
    :param max_it:
    :return:
    """
    start = time.time()

    # initialize
    V = V0.copy()
    Scalc = S0.copy()
    normF = 1e20
    iterations = 0
    converged = False

    # reduced system
    Yred = Ybus[pqpv, :][:, pqpv]
    Sred = S0[pqpv]
    I0_red = I0[pqpv]

    # get the first voltage approximation V0, or simply V(l
    Ivd = -Ybus[pqpv, :][:, vd].dot(V[vd])  # slack currents
    V_l = spsolve(Yred, Ivd)  # slack voltages influence

    # compute alpha
    Vabs = np.abs(V_l)
    alpha = sp.diags(np.conj(Sred) / (Vabs * Vabs))

    # compute Y-alpha
    Y_alpha = (Yred - alpha)
    Y_alpha_fact = factorized(Y_alpha)

    # compute beta as a vector
    B = Y_alpha.diagonal()
    beta = diags(B)
    Y_beta = Yred - beta

    n = len(V0)
    C = np.zeros((max_it + 1, n), dtype=complex)
    C[iterations, vd] = V0[vd]
    C[iterations, pqpv] = V_l
    V = V0.copy()

    while not converged and iterations < max_it:

        iterations += 1

        # Global step
        rhs_global = np.conj(Sred) / np.conj(V_l) - alpha * V_l + I0_red + Ivd
        V_l12 = Y_alpha_fact(rhs_global)

        # local step
        A = (Y_beta * V_l12 - I0_red - Ivd) / B
        Sigma = -np.conj(Sred) / (A * np.conj(A) * B)
        U = (-1 + np.sqrt(1 - 4 * (Sigma.imag * Sigma.imag + Sigma.real))) / 2.0 - 1j * Sigma.imag
        V_l = U * A  # it is the new V_l

        # Assign the reduced solution
        C[iterations, pqpv] = V_l
        V[pqpv] -= V_l

        # compute the error
        error = np.max(np.abs(V_l12 - V_l))
        converged = error < tol

        # compute the calculated power injection and the error of the voltage solution
        # V = C.sum(axis=0)
        Scalc = V * np.conj(Ybus * V - I0)

        mis = Scalc - S0  # complex power mismatch
        mismatch = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again
        normF = np.linalg.norm(mismatch, np.Inf)
        print(normF)

    print(C)
    end = time.time()
    elapsed = end - start

    return V, converged, normF, Scalc, iterations, elapsed


def ASD3(Ybus, Yseries, Ysh0, S0, V0, I0, pv, pq, pqpv, vd, tol, max_it=15):
    """

    :param Ybus:
    :param S0:
    :param V0:
    :param I0:
    :param pv:
    :param pq:
    :param pqpv:
    :param vd:
    :param tol:
    :param max_it:
    :return:
    """
    start = time.time()

    # initialize
    V = V0.copy()
    Scalc = S0.copy()
    normF = 1e20
    iterations = 0
    converged = False

    # reduced system
    # Yred = Ybus[pqpv, :][:, pqpv]
    Sred = S0[pqpv]
    I0_red = I0[pqpv]

    Yseries_red = Yseries[np.ix_(pqpv, pqpv)]  # admittance matrix without slack buses
    Yslack = -Yseries[np.ix_(pqpv, vd)]  # yes, it is the negative of this
    Yslack_vec = Yslack.sum(axis=1).A1
    Vslack = V0[vd]
    Ysh_red = Ysh0[pqpv]

    # get the first voltage approximation V0, or simply V(l
    Ivd = Yslack * Vslack  # slack currents
    V_l = spsolve(Yseries_red, Ivd + Ysh_red * V[pqpv])  # slack voltages influence

    # compute alpha
    Vabs = np.abs(V_l)
    alpha = sp.diags(np.conj(Sred) / (Vabs * Vabs))

    # compute Y-alpha
    Y_alpha = (Yseries_red - alpha)
    Y_alpha_fact = factorized(Y_alpha)

    # compute beta as a vector
    B = Y_alpha.diagonal()
    beta = diags(B)
    Y_beta = Yseries_red - beta

    n = len(V0)
    C = np.zeros((max_it + 1, n), dtype=complex)
    C[iterations, vd] = V0[vd]
    C[iterations, pqpv] = V_l
    V = V0.copy()

    while not converged and iterations < max_it:

        iterations += 1

        # Global step
        rhs_global = np.conj(Sred) / np.conj(V_l) - alpha * V_l + I0_red + Ivd - Ysh_red * V_l
        V_l12 = Y_alpha_fact(rhs_global)

        # local step
        A = (Y_beta * V_l12 - I0_red - Ivd + Ysh_red * V_l) / B
        Sigma = - np.conj(Sred) / (A * np.conj(A) * B)
        U = (-1 + np.sqrt(1 - 4 * (Sigma.imag * Sigma.imag + Sigma.real))) / 2.0 - 1j * Sigma.imag
        V_l = U * A  # it is the new V_l

        # Assign the reduced solution
        C[iterations, pqpv] = V_l
        V[pqpv] -= V_l

        # compute the error
        error = np.max(np.abs(V_l12 - V_l))
        converged = error < tol

        # compute the calculated power injection and the error of the voltage solution
        # V = C.sum(axis=0)
        Scalc = V * np.conj(Ybus * V - I0)

        mis = Scalc - S0  # complex power mismatch
        mismatch = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again
        normF = np.linalg.norm(mismatch, np.Inf)
        print(normF)

    print(C)
    end = time.time()
    elapsed = end - start

    return V, converged, normF, Scalc, iterations, elapsed

########################################################################################################################
#  MAIN
########################################################################################################################
if __name__ == "__main__":
    from GridCal.Engine import *

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE14_from_raw.gridcal'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
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
    # V, converged, normF, Scalc, iter_, elapsed
    V1, converged_, err, S, iter_, elapsed_ = ASD3(Ybus=circuit.Ybus,
                                                   Yseries=circuit.Yseries,
                                                   Ysh0=circuit.Yshunt,
                                                   S0=circuit.Sbus,
                                                   V0=circuit.Vbus,
                                                   I0=circuit.Ibus,
                                                   pv=circuit.pv,
                                                   pq=circuit.pq,
                                                   pqpv=circuit.pqpv,
                                                   vd=circuit.vd,
                                                   tol=1e-9,
                                                   max_it=20)

    print("--- %s seconds ---" % (time.time() - start_time))
    print('V:\n', np.abs(V1))
    print('error: \t', err)

    # check the ASD solution: v against the NR power flow
    # print('\nNR standard')
    # options = PowerFlowOptions(SolverType.NR, verbose=False, tolerance=1e-9, control_q=False)
    # power_flow = PowerFlowDriver(grid, options)
    #
    # start_time = time.time()
    # power_flow.run()
    # print("--- %s seconds ---" % (time.time() - start_time))
    # vnr = power_flow.results.voltage
    #
    # # print('V module:\t', abs(vnr))
    # # print('V angle: \t', angle(vnr))
    # print('error: \t', power_flow.results.error())
    #
    # data = c_[np.abs(V1), angle(V1), np.abs(vnr), angle(vnr),  np.abs(V1 - vnr)]
    # cols = ['|V|', 'angle', '|V| benchmark NR', 'angle benchmark NR', 'Diff']
    # df = pd.DataFrame(data, columns=cols)
    #
    # print()
    # print(df)
