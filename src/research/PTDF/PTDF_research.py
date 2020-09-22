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

import numpy as np
import pandas as pd
import numba as nb
import time
from warnings import warn
import scipy.sparse as sp
from scipy.sparse import coo_matrix, csc_matrix
from scipy.sparse import hstack as hs, vstack as vs
from scipy.sparse.linalg import factorized, spsolve, inv
from matplotlib import pyplot as plt
from GridCal.Engine import *


def Jacobian(Ybus, V, Ibus, pq, pvpq):
    """
    Computes the system Jacobian matrix in polar coordinates
    Args:
        Ybus: Admittance matrix
        V: Array of nodal voltages
        Ibus: Array of nodal current injections
        pq: Array with the indices of the PQ buses
        pvpq: Array with the indices of the PV and PQ buses

    Returns:
        The system Jacobian matrix
    """
    I = Ybus * V - Ibus
    Vdiag = sp.diags(V)
    Idiag = sp.diags(I)
    Ediag = sp.diags(V / np.abs(V))

    dS_dVm = Vdiag * np.conj(Ybus * Ediag) + np.conj(Idiag) * Ediag
    dS_dVa = 1.0j * Vdiag * np.conj(Idiag - Ybus * Vdiag)

    J = sp.vstack([sp.hstack([dS_dVa[np.ix_(pvpq, pvpq)].real, dS_dVm[np.ix_(pvpq, pq)].real]),
                   sp.hstack([dS_dVa[np.ix_(pq, pvpq)].imag,   dS_dVm[np.ix_(pq, pq)].imag])], format="csc")

    return J


def compute_ptdf(Ybus, Yf, Yt, Cf, Ct, V, Ibus, Sbus, pq, pv):
    """

    :param Ybus:
    :param Yf:
    :param Yt:
    :param Cf:
    :param Ct:
    :param V:
    :param Ibus:
    :param Sbus:
    :param pq:
    :param pv:
    :return:
    """
    n = len(V)
    # set up indexing for updating V
    pvpq = np.r_[pv, pq]
    npv = len(pv)
    npq = len(pq)
    npqpv = npq + npv
    # j1:j2 - V angle of pv and pq buses
    j1 = 0
    j2 = npv + npq
    # j2:j3 - V mag of pq buses
    j3 = j2 + npq

    # compute the Jacobian
    J = Jacobian(Ybus, V, Ibus, pq, pvpq)

    # compute the power increment (f)
    # Scalc = V * np.conj(Ybus * V - Ibus)
    # dS = Scalc - Sbus
    C = Cf - Ct  # branch bus connectivity
    A = C * C.T  # node adjacency matrix
    # f = np.r_[A[:, pvpq].toarray(), A[:, pq].toarray()]

    e = Cf * Cf.T
    e = e.toarray().astype(bool).astype(int)
    e1 = e[np.ix_(pvpq, pvpq)]
    e2 = e[np.ix_(pvpq, pq)]
    e3 = e[np.ix_(pq, pvpq)]
    e4 = e[np.ix_(pq, pq)]
    f = np.vstack((np.hstack((e1, e2)),
                   np.hstack((e3, e4))))

    # f = np.eye(*J.shape)
    # solve the voltage increment
    dx = spsolve(J, f)

    # reassign the solution vector
    # dVa = np.zeros(n)
    # dVm = np.zeros(n)
    # dVa[pvpq] = dx[j1:j2]
    # dVm[pq] = dx[j2:j3]

    # compute branch derivatives

    If = Yf * V
    It = Yt * V
    E = V / np.abs(V)
    Vdiag = sp.diags(V)
    Vdiag_conj = sp.diags(np.conj(V))
    Ediag = sp.diags(E)
    Ediag_conj = sp.diags(np.conj(E))
    If_diag_conj = sp.diags(np.conj(If))
    It_diag_conj = sp.diags(np.conj(It))
    Yf_conj = Yf.copy()
    Yf_conj.data = np.conj(Yf_conj.data)
    Yt_conj = Yt.copy()
    Yt_conj.data = np.conj(Yt_conj.data)

    dSf_dVa = 1j * (If_diag_conj * Cf * Vdiag - sp.diags(Cf * V) * Yf_conj * Vdiag_conj)
    dSf_dVm = If_diag_conj * Cf * Ediag - sp.diags(Cf * V) * Yf_conj * Ediag_conj

    dSt_dVa = 1j * (It_diag_conj * Ct * Vdiag - sp.diags(Ct * V) * Yt_conj * Vdiag_conj)
    dSt_dVm = It_diag_conj * Ct * Ediag - sp.diags(Ct * V) * Yt_conj * Ediag_conj

    PTDF = np.dot(np.c_[dSf_dVa.real[:, pvpq].toarray(), dSf_dVm.real[:, pq].toarray()], dx)

    # compute the PTDF

    # dVmf = Cf * dVm
    # dVaf = Cf * dVa
    # dPf_dVa = dSf_dVa.real
    # dPf_dVm = dSf_dVm.real
    #
    # dVmt = Ct * dVm
    # dVat = Ct * dVa
    # dPt_dVa = dSt_dVa.real
    # dPt_dVm = dSt_dVm.real
    #
    # PTDF = sp.diags(dVmf) * dPf_dVm + sp.diags(dVmt) * dPt_dVm + sp.diags(dVaf) * dPf_dVa + sp.diags(dVat) * dPt_dVa

    return PTDF, J


def make_lodf(circuit: SnapshotCircuit, PTDF, correct_values=True):
    """

    :param circuit:
    :param PTDF: PTDF matrix in numpy array form
    :return:
    """
    nl = circuit.nbr

    # compute the connectivity matrix
    Cft = circuit.C_branch_bus_f - circuit.C_branch_bus_t

    H = PTDF * Cft.T

    # old code
    # h = sp.diags(H.diagonal())
    # LODF = H / (np.ones((nl, nl)) - h * np.ones(nl))

    # divide each row of H by the vector 1 - H.diagonal
    # LODF = H / (1 - H.diagonal())
    # replace possible nan and inf
    # LODF[LODF == -np.inf] = 0
    # LODF[LODF == np.inf] = 0
    # LODF = np.nan_to_num(LODF)

    # this loop avoids the divisions by zero
    # in those cases the LODF column should be zero
    LODF = np.zeros((nl, nl))
    div = 1 - H.diagonal()
    for j in range(H.shape[1]):
        if div[j] != 0:
            LODF[:, j] = H[:, j] / div[j]

    # replace the diagonal elements by -1
    # old code
    # LODF = LODF - sp.diags(LODF.diagonal()) - sp.eye(nl, nl), replaced by:
    for i in range(nl):
        LODF[i, i] = - 1.0

    if correct_values:
        i1, j1 = np.where(LODF > 1)
        for i, j in zip(i1, j1):
            LODF[i, j] = 1

        i2, j2 = np.where(LODF < -1)
        for i, j in zip(i2, j2):
            LODF[i, j] = -1

    return LODF


def test_ptdf(grid):
    """
    Sigma-distances test
    :param grid:
    :return:
    """
    nc = compile_snapshot_circuit(grid)
    islands = split_into_islands(nc)
    inputs = islands[0]  # pick the first island

    PTDF, J = compute_ptdf(Ybus=inputs.Ybus,
                           Yf=inputs.Yf,
                           Yt=inputs.Yt,
                           Cf=inputs.C_branch_bus_f,
                           Ct=inputs.C_branch_bus_t,
                           V=inputs.Vbus,
                           Ibus=inputs.Ibus,
                           Sbus=inputs.Sbus,
                           pq=inputs.pq,
                           pv=inputs.pv)

    print('PTDF:')
    print(PTDF)

    # compose some made up situation
    # delta = 2.0
    # S2 = inputs.Sbus * delta  # new power
    # dS = S2 - inputs.Sbus  # power increment
    # dSbr = (PTDF * dS) * inputs.Sbase  # increment of branch power
    #
    # # run a power flow to get the initial branch power and compose the second branch power with the increment
    # driver = PowerFlowDriver(grid=grid, options=PowerFlowOptions())
    # driver.run()
    #
    # Sbr0 = driver.results.Sbranch
    # Sbr2 = Sbr0 + dSbr
    # # Sbr2 = PTDF * S2
    #
    # # run a power flow to get the initial branch power and compose the second branch power with the increment
    # grid.scale_power(delta)
    # driver = PowerFlowDriver(grid=grid, options=PowerFlowOptions())
    # driver.run()
    #
    # #
    # Sbr3 = driver.results.Sbranch
    #
    # # PTDFsq = PTDF * PTDF.T
    # # LODF = PTDFsq * inv(sp.diags(ones(PTDF.shape[0])) - PTDFsq).toarray()
    #
    # print('PTDF:')
    # print(PTDF.toarray())
    # print()
    # print('Sbr0')
    # print(Sbr0)
    #
    # print('Sbr2')
    # print(Sbr2)
    # print('Sbr3')
    # print(Sbr3)


if __name__ == '__main__':
    from GridCal.Engine import FileOpen
    import pandas as pd

    np.set_printoptions(linewidth=2000, suppress=True)
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/lynn5buspv.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 118.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'
    # fname = 'helm_data1.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14 PQ only.gridcal'
    # fname = 'IEEE 14 PQ only full.gridcal'
    fname = '/home/santi/Descargas/matpower-fubm-master/data/case5.m'
    grid = FileOpen(fname).open()

    # test_voltage(grid=grid)

    # test_sigma(grid=grid)

    test_ptdf(grid)