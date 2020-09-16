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
import time
from warnings import warn
import scipy.sparse as sp
from scipy.sparse import coo_matrix, csc_matrix
from scipy.sparse import hstack as hs, vstack as vs
from scipy.sparse.linalg import factorized, spsolve, inv
from matplotlib import pyplot as plt
from GridCal.Engine import *


def make_ptdf(circuit: SnapshotCircuit, distribute_slack=True):
    """

    :param circuit:
    :return:
    """
    Bbus, Bf = circuit.get_linear_matrices()

    n = circuit.nbus
    dP = sp.eye(n, n).tocsc()
    nb = n
    nbi = n
    noref = np.arange(1, nb)
    noslack = circuit.pqpv

    # compute the reduced susceptance matrix
    Bref = Bbus[noslack, :][:, noref].tocsc()

    # solve for change in voltage angles
    dthetha_red = spsolve(Bref,  dP[noslack, :]).toarray()  # pass to array because it is a full matrix

    # compute the PTDF matrix (H)
    H = (Bf * np.vstack((np.zeros(nbi), dthetha_red)))

    # Distribute the effect of the slack
    if distribute_slack:
        slack = circuit.vd + 1  # the +1 is to avoid zero divisions if the slack is the bus 0
        w_slack = slack / np.sum(slack)  # weighted slack
        mod = sp.eye(nb, nb).toarray() - w_slack * ones((1, nb))
        H = np.dot(H, mod)

    return H


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


def get_branch_time_series(circuit: TimeCircuit, PTDF):
    """

    :param grid:
    :return:
    """

    # option 2: call the power directly
    P = circuit.Sbus.real
    Pbr = np.dot(PTDF, P).T * circuit.Sbase

    return Pbr


def get_n_minus_1_flows(circuit: MultiCircuit):

    opt = PowerFlowOptions()
    branches = circuit.get_branches()
    m = circuit.get_branch_number()
    Pmat = np.zeros((m, m))  # monitored, contingency

    for c, branch in enumerate(branches):

        if branch.active:
            branch.active = False

            pf = PowerFlowDriver(circuit, opt)
            pf.run()
            Pmat[:, c] = pf.results.Sbranch.real

            branch.active = True

    return Pmat


def check_lodf(grid: MultiCircuit):

    Pn1_nr = get_n_minus_1_flows(grid)

    # assume 1 island
    nc = compile_snapshot_circuit(grid)
    islands = split_into_islands(nc)
    circuit = islands[0]

    PTDF = make_ptdf(circuit, distribute_slack=False)
    LODF = make_lodf(circuit, PTDF)

    Pbus = circuit.get_injections(False).real
    flows_n = np.dot(PTDF, Pbus)

    nl = circuit.nbr
    flows_n1 = np.zeros((nl, nl))
    for c in range(nl):  # branch that fails (contingency)
        for m in range(nl):  # branch to monitor
            flows_n1[m, c] = flows_n[m] + LODF[m, c] * flows_n[c]

    return Pn1_nr, flows_n1


if __name__ == '__main__':
    from GridCal.Engine import FileOpen
    import pandas as pd

    np.set_printoptions(threshold=sys.maxsize, linewidth=200000000)
    # np.set_printoptions(linewidth=2000, suppress=True)
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/lynn5buspv.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 118.xlsx'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'
    # fname = 'helm_data1.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14 PQ only.gridcal'
    # fname = 'IEEE 14 PQ only full.gridcal'
    # fname = '/home/santi/Descargas/matpower-fubm-master/data/case5.m'
    # fname = '/home/santi/Descargas/matpower-fubm-master/data/case30.m'
    grid_ = FileOpen(fname).open()

    # test_voltage(grid=grid)

    # test_sigma(grid=grid)

    nc_ = compile_snapshot_circuit(grid_)
    islands_ = split_into_islands(nc_)
    circuit_ = islands_[0]

    H_ = make_ptdf(circuit_, distribute_slack=False)
    LODF_ = make_lodf(circuit_, H_)

    if H_.shape[0] < 50:
        print('PTDF:\n', H_)
        print('LODF:\n', LODF_)

    Pn1_nr, flows_n1 = check_lodf(grid_)
    Pn1_nr_df = pd.DataFrame(data=Pn1_nr, index=nc_.branch_names, columns=nc_.branch_names)
    flows_n1_df = pd.DataFrame(data=flows_n1, index=nc_.branch_names, columns=nc_.branch_names)

    # plot N-1
    fig = plt.figure(figsize=(12, 8))
    ax1 = fig.add_subplot(221)
    ax2 = fig.add_subplot(222)
    ax3 = fig.add_subplot(223)

    Pn1_nr_df.plot(ax=ax1, legend=False)
    flows_n1_df.plot(ax=ax2, legend=False)
    diff = Pn1_nr_df - flows_n1_df
    diff.plot(ax=ax3, legend=False)

    ax1.set_title('Newton-Raphson N-1 flows')
    ax2.set_title('PTDF N-1 flows')
    ax3.set_title('Difference')

    # ------------------------------------------------------------------------------------------------------------------
    # Perform real time series
    # ------------------------------------------------------------------------------------------------------------------
    if grid_.time_profile is not None:
        grid_.ensure_profiles_exist()
        nc_ts = compile_time_circuit(grid_)
        islands_ts = split_time_circuit_into_islands(nc_ts)
        circuit_ts = islands_ts[0]

        pf_options = PowerFlowOptions()
        ts_driver = TimeSeries(grid=grid_, options=pf_options)
        ts_driver.run()
        Pbr_nr = ts_driver.results.Sbranch.real
        df_Pbr_nr = pd.DataFrame(data=Pbr_nr, columns=circuit_ts.branch_names, index=circuit_ts.time_array)

        # Compute the PTDF based flows
        Pbr_ptdf = get_branch_time_series(circuit=circuit_ts, PTDF=H_)
        df_Pbr_ptdf = pd.DataFrame(data=Pbr_ptdf, columns=circuit_ts.branch_names, index=circuit_ts.time_array)

        # plot
        fig = plt.figure(figsize=(12, 8))
        ax1 = fig.add_subplot(221)
        ax2 = fig.add_subplot(222)
        ax3 = fig.add_subplot(223)

        df_Pbr_nr.plot(ax=ax1, legend=False)
        df_Pbr_ptdf.plot(ax=ax2, legend=False)
        diff = df_Pbr_nr - df_Pbr_ptdf
        diff.plot(ax=ax3, legend=False)

        ax1.set_title('Newton-Raphson flows')
        ax2.set_title('PTDF flows')
        ax3.set_title('Difference')

    plt.show()
