

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


def make_ptdf(Bbus, Bf, pqpv, distribute_slack=True):
    """
    Build the PTDF matrix
    :param Bbus: DC-linear susceptance matrix
    :param Bf: Bus-branch "from" susceptance matrix
    :param pqpv: array of sorted pq and pv node indices
    :param distribute_slack: distribute the slack?
    :return: PTDF matrix. It is a full matrix of dimensions branches x buses
    """

    n = Bbus.shape[0]
    nb = n
    nbi = n
    noref = np.arange(1, nb)
    noslack = pqpv

    if distribute_slack:
        dP = np.ones((n, n)) * (-1 / (n - 1))
        for i in range(n):
            dP[i, i] = 1.0
    else:
        dP = np.eye(n, n)

    # solve for change in voltage angles
    dTheta = np.zeros((nb, nbi))
    Bref = Bbus[noslack, :][:, noref].tocsc()
    dtheta_ref = spsolve(Bref,  dP[noslack, :])

    if sp.issparse(dtheta_ref):
        dTheta[noref, :] = dtheta_ref.toarray()
    else:
        dTheta[noref, :] = dtheta_ref

    # compute corresponding change in branch flows
    # Bf is a sparse matrix
    H = Bf * dTheta

    return H


def make_ptdf_by_groups(Bbus, Bf, pqpv, idx1, idx2):
    """

    :param Bbus:
    :param Bf:
    :param pqpv:
    :param idx1:
    :param idx2:
    :return:
    """

    n = Bbus.shape[0]
    nbi = n
    noref = np.arange(1, n)
    noslack = pqpv

    dP = np.zeros((n, 2))

    # transfer from 1->2
    dP[idx1, 0] = 1
    dP[idx2, 0] = -1

    # transfer from 2->1
    dP[idx1, 1] = -1
    dP[idx2, 1] = 1

    # compute the reduced susceptance matrix
    # Bref = Bbus[noslack, :][:, noref].tocsc()

    # solve for change in voltage angles
    theta = spsolve(Bbus,  dP)  # pass to array because it is a full matrix

    # compute the PTDF matrix (H)
    # theta = np.vstack((np.zeros(dP.shape[1]), dthetha_red))
    PTDF = Bf * theta

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
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE14_from_raw.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/lynn5buspv.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 118.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'
    # fname = 'helm_data1.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14 PQ only.gridcal'
    # fname = 'IEEE 14 PQ only full.gridcal'
    # fname = '/home/santi/Descargas/matpower-fubm-master/data/case5.m'
    # fname = '/home/santi/Descargas/matpower-fubm-master/data/case30.m'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/PGOC_6bus.gridcal'
    grid_ = FileOpen(fname).open()

    # test_voltage(grid=grid)

    # test_sigma(grid=grid)
    name = os.path.splitext(fname.split(os.sep)[-1])[0]
    method = 'PTDF'
    nc_ = compile_snapshot_circuit(grid_)
    islands_ = nc_.split_into_islands()
    circuit_ = islands_[0]

    Hnodal = make_ptdf(Bbus=circuit_.Bbus,
                       Bf=circuit_.Bf,
                       pqpv=circuit_.pqpv)

    Hgroup = make_ptdf_by_groups(Bbus=circuit_.Bbus,
                                 Bf=circuit_.Bf,
                                 pqpv=circuit_.pqpv,
                                 idx1=[1, 2, 3],
                                 idx2=[9, 10, 11])

    print()
