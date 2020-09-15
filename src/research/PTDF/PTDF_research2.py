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

    # solve for change in voltage angles
    dTheta = np.zeros((nb, nbi))
    Bref = Bbus[noslack, :][:, noref].tocsc()
    dTheta[noref, :] = sp.linalg.spsolve(Bref,  dP[noslack, :]).toarray()

    # compute corresponding change in branch flows
    # Bf is a sparse matrix
    H = Bf * dTheta

    # normalize the slack
    if distribute_slack:
        slack = circuit.vd + 1  # the +1 is to avoid zero divisions
        w_slack = slack / np.sum(slack)
        mod = sp.eye(nb, nb).toarray() - w_slack * ones((1, nb))
        H = np.dot(H, mod)

    return H


def make_lodf(circuit: SnapshotCircuit, PTDF):
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
    LODF = H / (1 - H.diagonal())

    # replace possible nan and inf
    LODF[LODF == -np.inf] = 0
    LODF[LODF == np.inf] = 0
    LODF = np.nan_to_num(LODF)

    # replace the diagonal elements by -1
    # old code
    # LODF = LODF - sp.diags(LODF.diagonal()) - sp.eye(nl, nl), replaced by:
    for i in range(nl):
        LODF[i, i] = - 1.0

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
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'
    # fname = 'helm_data1.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14 PQ only.gridcal'
    # fname = 'IEEE 14 PQ only full.gridcal'
    # fname = '/home/santi/Descargas/matpower-fubm-master/data/case5.m'
    fname = '/home/santi/Descargas/matpower-fubm-master/data/case30.m'
    grid_ = FileOpen(fname).open()

    # test_voltage(grid=grid)

    # test_sigma(grid=grid)

    nc_ = compile_snapshot_circuit(grid_)
    islands_ = split_into_islands(nc_)
    circuit_ = islands_[0]

    H_ = make_ptdf(circuit_, distribute_slack=False)
    LODF_ = make_lodf(circuit_, H_)

    print('PTDF:\n', H_)
    print('LODF:\n', LODF_)

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
