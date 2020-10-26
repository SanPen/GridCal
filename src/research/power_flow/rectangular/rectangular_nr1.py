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


def Jrect(G, B, V, pvpq, pqpv, pq, pv):

    e = V.real
    f = V.imag
    ediag = diags(e)
    fdiag = diags(f)

    J1 = ediag * G + fdiag * B + diags(G * e - B * f)
    J2 = fdiag * G - ediag * B + diags(G * f + B * e)
    J3 = fdiag * G - ediag * B - diags(G * f + B * e)
    J4 = -ediag * G - fdiag * B + diags(G * e - B * f)
    J5 = diags(2 * e).tocsc()
    J6 = diags(2 * f).tocsc()

    J = vstack_sp([hstack_sp([J1[np.ix_(pvpq, pvpq)], J2[np.ix_(pvpq, pqpv)]]),
                   hstack_sp([J3[np.ix_(pq, pvpq)],   J4[np.ix_(pq, pqpv)]]),
                   hstack_sp([J5[np.ix_(pv, pvpq)],   J6[np.ix_(pv, pqpv)]])], format="csc")
    return J


def NRR1(Ybus, S0, V0, I0, pv, pq, vd, tol, max_it=15, gamma=0.1):
    """
    Rectangular power flow

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
    Vm2 = np.power(np.abs(V), 2)
    iterations = 0
    npv = len(pv)
    npq = len(pq)
    pqpv = np.r_[pq, pv]
    G = Ybus.real
    B = Ybus.imag

    j1 = 0
    j2 = npv + npq
    j3 = j2 + npv + npq

    # compute the calculated power injection and the error of the voltage solution
    Scalc = V * np.conj(Ybus * V - I0)
    mis = Scalc - S0  # complex power mismatch
    dvm = Vm2 - (np.power(V.real, 2) + np.power(V.imag, 2))  # voltage module mismatch
    dfx = np.r_[mis[pqpv].real, mis[pq].imag, dvm[pv]]  # concatenate again
    normF = 0.5 * np.dot(dfx, dfx)

    converged = normF < tol

    while not converged and iterations < max_it:

        # compute jacobian
        J = Jrect(G, B, V, pqpv, pqpv, pq, pv)

        # solve increment
        dx = spsolve(J, dfx)

        # update voltage
        de = dx[j1:j2]
        df = dx[j2:j3]
        V[pqpv] -= de + 1j * df

        # compute the calculated power injection and the error of the voltage solution
        Scalc = V * np.conj(Ybus * V - I0)
        mis = Scalc - S0  # complex power mismatch
        dvm = Vm2 - (np.power(V.real, 2) + np.power(V.imag, 2))  # voltage module mismatch
        dfx = np.r_[mis[pqpv].real, mis[pq].imag, dvm[pv]]  # concatenate again
        normF = 0.5 * np.dot(dfx, dfx)
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

    numeric_circuit = compile_snapshot_circuit(grid)
    islands = numeric_circuit.split_into_islands()
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

    print('NRR')
    start_time = time.time()

    V1, converged_, err, S, iter_, elapsed_ = NRR1(Ybus=circuit.Ybus,
                                                   S0=circuit.Sbus,
                                                   V0=circuit.Vbus,
                                                   I0=circuit.Ibus,
                                                   pv=circuit.pv,
                                                   pq=circuit.pq,
                                                   vd=circuit.vd,
                                                   tol=1e-6,
                                                   max_it=20,
                                                   gamma=0.1)

    print("--- %s seconds ---" % (time.time() - start_time))
    print('V:\n', np.abs(V1))
    print('error: \t', err)
