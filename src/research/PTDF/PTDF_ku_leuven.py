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
import GridCal.Engine as gce
from GridCal.Engine.Simulations.PowerFlow.derivatives import derivatives_sh


def getPTDF1(circuit: gce.SnapshotData):
    """
    PTDF according to: https://www.mech.kuleuven.be/en/tme/research/energy_environment/Pdf/wpen2014-12.pdf
    formula 3.8, this is exactly as the document describes
    :param circuit: SnapshotData instance
    :return: Power Transfer Distribution Factors matrix (branch, bus)
    """
    pqpv = np.sort(circuit.pqpv)
    Bd = sp.diags(circuit.branch_data.X)
    A = circuit.A
    M1 = Bd * A  # Equivalent of Bf
    M2 = A.T * M1  # Equivalent of Bbus

    M1p = M1[:, pqpv]
    M2p = M2[np.ix_(pqpv, pqpv)].tocsc()

    PTDF = np.zeros((circuit.nbr, circuit.nbus))
    PTDF[:, pqpv] = (M1p * sp.linalg.inv(M2p)).toarray()

    return PTDF


def getPTDF(circuit: gce.SnapshotData):
    """
    PTDF according to: https://www.mech.kuleuven.be/en/tme/research/energy_environment/Pdf/wpen2014-12.pdf
    formula 3.8, modified to use GridCal's pre-computed matrices
    :param circuit: SnapshotData instance
    :return: Power Transfer Distribution Factors matrix (branch, bus)
    """
    pqpv = np.sort(circuit.pqpv)
    M1p = circuit.Bf[:, pqpv]
    M2p = circuit.Bbus[np.ix_(pqpv, pqpv)].tocsc()  # csc is more efficient for SPLU

    PTDF = np.zeros((circuit.nbr, circuit.nbus))
    PTDF[:, pqpv] = (M1p * sp.linalg.inv(M2p)).toarray()

    return PTDF


def getPTDF2(circuit: gce.SnapshotData):
    """
    PTDF according to: https://www.mech.kuleuven.be/en/tme/research/energy_environment/Pdf/wpen2014-12.pdf
    formula 3.8, modified to use GridCal's pre-computed matrices
    :param circuit: SnapshotData instance
    :return: Power Transfer Distribution Factors matrix (branch, bus)
    """
    pqpv = np.sort(circuit.pqpv)
    M1p = circuit.Bf[:, pqpv]
    M2p = circuit.Bbus[np.ix_(pqpv, pqpv)].tocsc()  # csc is more efficient for SPLU
    dP = sp.diags(np.ones(len(circuit.pqpv)))
    PTDF = np.zeros((circuit.nbr, circuit.nbus))
    PTDF[:, pqpv] = (M1p * spsolve(M2p, dP)).toarray()

    return PTDF


def getPTDF_distributed(circuit: gce.SnapshotData):
    """
    PTDF according to: https://www.mech.kuleuven.be/en/tme/research/energy_environment/Pdf/wpen2014-12.pdf
    formula 3.8, modified to use GridCal's pre-computed matrices
    :param circuit: SnapshotData instance
    :return: Power Transfer Distribution Factors matrix (branch, bus)
    """
    n = circuit.nbus
    pqpv = np.sort(circuit.pqpv)
    Bbus_red = circuit.Bbus[np.ix_(pqpv, pqpv)].tocsc()  # csc is more efficient for SPLU

    # create the right-hand side
    dP = np.ones((n, n)) * (-1 / (n - 1))
    for i in range(n):
        dP[i, i] = 1.0

    # solve the angles
    dP_red = dP[pqpv, :]
    dTheta = np.zeros((n, n))
    dTheta[pqpv, :] = spsolve(Bbus_red, dP_red)

    PTDF = circuit.Bf * dTheta

    return PTDF


def getPSDF(circuit: gce.SnapshotData, PTDF):
    """
    Phase shifter distribution factors
    According to: https://www.mech.kuleuven.be/en/tme/research/energy_environment/Pdf/wpen2014-12.pdf
    formula 4.6
    :param circuit: SnapshotData instance
    :param PTDF: Power Transfer Distribution Factors matrix
    :return: Phase shifter distribution factors matrix  (branch, branch)
    """
    Bd = sp.diags(circuit.branch_data.X)
    A = circuit.A
    M1 = Bd * A

    PSDF = Bd - PTDF * M1.T

    return PSDF


if __name__ == '__main__':
    from GridCal.Engine import FileOpen
    import pandas as pd

    np.set_printoptions(linewidth=2000, suppress=True)
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14.xlsx'
    # fname = r'C:\Users\SPV86\Documents\Git\GitHub\GridCal\Grids_and_profiles\grids\IEEE 14.xlsx'
    # fname = r'C:\Users\SPV86\Documents\Git\GitHub\GridCal\Grids_and_profiles\grids\KULeuven_5node.gridcal'
    # fname = r'C:\Users\penversa\Git\Github\GridCal\Grids_and_profiles\grids\KULeuven_5node.gridcal'
    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/KULeuven_5node.gridcal'
    fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 118.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'
    # fname = 'helm_data1.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14 PQ only.gridcal'
    # fname = 'IEEE 14 PQ only full.gridcal'
    grid = FileOpen(fname).open()

    nc = gce.compile_snapshot_circuit(grid)

    PTDF_ = getPTDF(circuit=nc)
    PTDF2_ = getPTDF2(circuit=nc)
    PTDF_dis = getPTDF_distributed(circuit=nc)
    PSDF_ = getPSDF(circuit=nc, PTDF=PTDF_)

    Ys = 1 / (nc.branch_data.R + 1j * nc.branch_data.X)
    dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh = derivatives_sh(nb=nc.nbus,
                                                       nl=nc.nbr,
                                                       iPxsh=np.arange(nc.nbr),
                                                       F=nc.F,
                                                       T=nc.T,
                                                       Ys=Ys,
                                                       k2=np.ones(nc.nbr),
                                                       tap=np.ones(nc.nbr),
                                                       V=np.ones(nc.nbr))


    print("PTDF:\n", PTDF_)
    print("PTDF2:\n", PTDF2_)
    print("PTDF distributed:\n", PTDF_dis)
    print("PSDF:\n", PSDF_)
    print("PSDF (dSf_dPfsh):\n", dSf_dPfsh.toarray())