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
    Bbus, Bf, reactances = circuit.get_linear_matrices()
    nbr = circuit.nbr
    nbus = circuit.nbus
    PTDF = np.zeros((nbr, nbus))
    vd = circuit.vd
    Bbus[np.ix_(circuit.pqpv, circuit.vd)] = 0
    Bbus[np.ix_(circuit.vd, circuit.pqpv)] = 0
    Bbus[np.ix_(circuit.vd, circuit.vd)] = 1

    for i in range(nbr):
        f = circuit.F[i]
        t = circuit.T[i]
        a_alpha = np.zeros(nbus)
        a_alpha[f] = 1
        a_alpha[t] = -1

        for j in circuit.pqpv:
            a = np.zeros(nbus)
            a[j] = 1
            a[vd] = -1
            PTDF[i, j] = np.dot((a_alpha / reactances[i]), spsolve(Bbus, a))

    return PTDF


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
    fname = '/home/santi/Descargas/matpower-fubm-master/data/case5.m'
    # fname = '/home/santi/Descargas/matpower-fubm-master/data/case30.m'
    grid_ = FileOpen(fname).open()

    # test_voltage(grid=grid)

    # test_sigma(grid=grid)

    nc_ = compile_snapshot_circuit(grid_)
    islands_ = split_into_islands(nc_)
    circuit_ = islands_[0]

    H_ = make_ptdf(circuit_, distribute_slack=False)
    print(H_)