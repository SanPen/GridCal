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
import time
import multiprocessing
from PySide2.QtCore import QThread, Signal

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_model import ResultsModel
from GridCal.Engine.Core.snapshot_pf_data import compile_snapshot_circuit


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


def make_lodf(Cf, Ct, PTDF, correct_values=True):
    """
    Compute the LODF matrix
    :param Cf: Branch "from" -bus connectivity matrix
    :param Ct: Branch "to" -bus connectivity matrix
    :param PTDF: PTDF matrix in numpy array form (branches, buses)
    :return: LODF matrix of dimensions (branches, branches)
    """
    nl = PTDF.shape[0]

    # compute the connectivity matrix
    Cft = Cf - Ct
    H = PTDF * Cft.T

    # old code
    # h = sp.diags(H.diagonal())
    # LODF = H / (np.ones((nl, nl)) - h * np.ones(nl))

    # divide each row of H by the vector 1 - H.diagonal
    # LODF = H / (1 - H.diagonal())
    #
    # # replace possible nan and inf
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


class LinearAnalysisResults:

    def __init__(self, n_br=0, n_bus=0, br_names=(), bus_names=(), bus_types=()):
        """
        PTDF and LODF results class
        :param n_br: number of branches
        :param n_bus: number of buses
        :param br_names: branch names
        :param bus_names: bus names
        :param bus_types: bus types array
        """

        self.name = 'Linear Analysis'

        # number of branches
        self.n_br = n_br

        self.n_bus = n_bus

        # names of the branches
        self.br_names = br_names

        self.bus_names = bus_names

        self.bus_types = bus_types

        self.logger = Logger()

        self.PTDF = np.zeros((n_br, n_bus))
        self.LODF = np.zeros((n_br, n_br))

        self.available_results = [ResultTypes.PTDFBranchesSensitivity,
                                  ResultTypes.OTDF]

    def mdl(self, result_type: ResultTypes) -> ResultsModel:
        """
        Plot the results.

        Arguments:

            **result_type**: ResultTypes

        Returns: ResultsModel
        """

        if result_type == ResultTypes.PTDFBranchesSensitivity:
            labels = self.bus_names
            y = self.PTDF
            y_label = '(p.u.)'
            title = 'Branches sensitivity'

        elif result_type == ResultTypes.OTDF:
            labels = self.br_names
            y = self.LODF
            y_label = '(p.u.)'
            title = 'Branch failure sensitivity'

        else:
            labels = []
            y = np.zeros(0)
            y_label = ''
            title = ''

        # assemble model
        mdl = ResultsModel(data=y,
                           index=self.br_names,
                           columns=labels,
                           title=title,
                           ylabel=y_label,
                           units=y_label)
        return mdl


class LinearAnalysis:

    def __init__(self, grid: MultiCircuit, distributed_slack=True, correct_values=True):
        """

        :param grid:
        :param distributed_slack:
        """

        self.grid = grid

        self.distributed_slack = distributed_slack

        self.correct_values = correct_values

        self.numerical_circuit = None

        self.results = LinearAnalysisResults(n_br=0,
                                             n_bus=0,
                                             br_names=[],
                                             bus_names=[],
                                             bus_types=[])

        self.logger = Logger()

    def run(self):
        """
        Run the PTDF and LODF
        """
        self.numerical_circuit = compile_snapshot_circuit(self.grid)
        islands = self.numerical_circuit.split_into_islands()

        self.results = LinearAnalysisResults(n_br=self.numerical_circuit.nbr,
                                             n_bus=self.numerical_circuit.nbus,
                                             br_names=self.numerical_circuit.branch_data.branch_names,
                                             bus_names=self.numerical_circuit.bus_data.bus_names,
                                             bus_types=self.numerical_circuit.bus_data.bus_types)

        # compute the PTDF per islands
        if len(islands) > 0:
            for n_island, island in enumerate(islands):

                # no slacks will make it impossible to compute the PTDF analytically
                if len(island.vd) == 1:
                    if len(island.pqpv) > 0:

                        # compute the PTDF of the island
                        ptdf_island = make_ptdf(Bbus=island.Bbus,
                                                Bf=island.Bf,
                                                pqpv=island.pqpv,
                                                distribute_slack=self.distributed_slack)

                        # assign the PTDF to the matrix
                        self.results.PTDF[np.ix_(island.original_branch_idx, island.original_bus_idx)] = ptdf_island

                        # compute the island LODF
                        lodf_island = make_lodf(Cf=island.Cf,
                                                Ct=island.Ct,
                                                PTDF=ptdf_island,
                                                correct_values=self.correct_values)

                        # assign the LODF to the matrix
                        self.results.LODF[np.ix_(island.original_branch_idx, island.original_branch_idx)] = lodf_island
                    else:
                        self.logger.add_error('No PQ or PV nodes', 'Island {}'.format(n_island))
                else:
                    self.logger.add_error('More than one slack bus', 'Island {}'.format(n_island))
        else:

            # there is only 1 island, compute the PTDF
            self.results.PTDF = make_ptdf(Bbus=islands[0].Bbus,
                                          Bf=islands[0].Bf,
                                          pqpv=islands[0].pqpv,
                                          distribute_slack=self.distributed_slack)

            # compute the LODF upon the PTDF
            self.results.LODF = make_lodf(Cf=islands[0].Cf,
                                          Ct=islands[0].Ct,
                                          PTDF=self.results.PTDF,
                                          correct_values=self.correct_values)

    def get_branch_time_series(self, Sbus):
        """
        Compute the time series PTDF
        :param Sbus: Power injections time series array
        :return:
        """

        # option 2: call the power directly
        P = Sbus.real
        PTDF = self.results.PTDF
        Pbr = np.dot(PTDF, P).T * self.grid.Sbase

        return Pbr
