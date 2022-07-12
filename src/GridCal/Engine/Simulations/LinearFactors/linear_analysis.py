# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import time
import numpy as np
import numba as nb
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.snapshot_pf_data import compile_snapshot_circuit, SnapshotData
from GridCal.Engine.Simulations.PowerFlow.NumericalMethods.ac_jacobian import AC_jacobian
from GridCal.Engine.Simulations.PowerFlow.NumericalMethods.derivatives import dSf_dV_fast


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

    # compute corresponding change in branch Sf
    # Bf is a sparse matrix
    H = Bf * dTheta

    return H


def compute_acptdf(Ybus, Yf, Cf, F, V, pq, pv, distribute_slack: bool = False):
    """
    Compute the AC-PTDF
    :param Ybus: admittance matrix
    :param Yf: Admittance matrix of the buses "from"
    :param Cf: Connectivity branch - bus "from"
    :param F: array if branches "from" bus indices
    :param V: voltages array
    :param pq: array of pq node indices
    :param pv: array of pv node indices
    :param distribute_slack: distribute slack?
    :return: AC-PTDF matrix (branches, buses)
    """
    n = len(V)
    pvpq = np.r_[pv, pq]
    npq = len(pq)
    npv = len(pv)

    # compute the Jacobian
    J = AC_jacobian(Ybus, V, pvpq, pq, npv, npq)

    if distribute_slack:
        dP = np.ones((n, n)) * (-1 / (n - 1))
        for i in range(n):
            dP[i, i] = 1.0
    else:
        dP = np.eye(n, n)

    # compose the compatible array (the Q increments are considered zero
    dQ = np.zeros((npq, n))
    dS = np.r_[dP[pvpq, :], dQ]

    # solve the voltage increments
    dx = spsolve(J, dS)

    # compute branch derivatives
    Vc = np.conj(V)
    E = V / np.abs(V)
    dSf_dVa, dSf_dVm = dSf_dV_fast(Yf.tocsc(), V, Vc, E, F, Cf)

    # compose the final AC-PTDF
    dPf_dVa = dSf_dVa.real[:, pvpq]
    dPf_dVm = dSf_dVm.real[:, pq]
    PTDF = sp.hstack((dPf_dVa, dPf_dVm)) * dx

    return PTDF


def make_lodf(Cf, Ct, PTDF, correct_values=True, numerical_zero=1e-10):
    """
    Compute the LODF matrix
    :param Cf: Branch "from" -bus connectivity matrix
    :param Ct: Branch "to" -bus connectivity matrix
    :param PTDF: PTDF matrix in numpy array form (branches, buses)
    :param correct_values: correct values out of the interval
    :param numerical_zero: value considered zero in numerical terms (i.e. 1e-10)
    :return: LODF matrix of dimensions (branches, branches)
    """
    nl = PTDF.shape[0]

    # compute the connectivity matrix
    Cft = Cf - Ct
    H = PTDF * Cft.T

    # this loop avoids the divisions by zero
    # in those cases the LODF column should be zero
    LODF = np.zeros((nl, nl))
    div = 1 - H.diagonal()
    for j in range(H.shape[1]):
        if abs(div[j]) > numerical_zero:
            LODF[:, j] = H[:, j] / div[j]

    # replace the diagonal elements by -1
    # old code
    # LODF = LODF - sp.diags(LODF.diagonal()) - sp.eye(nl, nl), replaced by:
    for i in range(nl):
        LODF[i, i] = - 1.0

    if correct_values:  # TODO check more efficient way

        # correct stupid values
        i1, j1 = np.where(LODF > 1.2)
        for i, j in zip(i1, j1):
            LODF[i, j] = 0

        i2, j2 = np.where(LODF < -1.2)
        for i, j in zip(i2, j2):
            LODF[i, j] = 0

        # ensure +-1 values
        i1, j1 = np.where(LODF > 1)
        for i, j in zip(i1, j1):
            LODF[i, j] = 1

        i2, j2 = np.where(LODF < -1)
        for i, j in zip(i2, j2):
            LODF[i, j] = -1

    return LODF


@nb.njit(cache=True)
def make_otdf(ptdf, lodf, j):
    """
    Outage sensitivity of the branches when transferring power from the bus j to the slack
        LODF: outage transfer distribution factors
    :param ptdf: power transfer distribution factors matrix (n-branch, n-bus)
    :param lodf: line outage distribution factors matrix (n-branch, n-branch)
    :param j: index of the bus injection
    :return: LODF matrix (n-branch, n-branch)
    """
    nk = ptdf.shape[0]
    nl = nk
    otdf = np.empty((nk, nl))

    for k in range(nk):
        for l in range(nl):
            otdf[k, l] = ptdf[k, j] + lodf[k, l] * ptdf[l, j]

    return otdf


@nb.njit(parallel=True)
def make_otdf_max(ptdf, lodf):
    """
    Maximum Outage sensitivity of the branches when transferring power from any bus to the slack
        LODF: outage transfer distribution factors
    :param ptdf: power transfer distribution factors matrix (n-branch, n-bus)
    :param lodf: line outage distribution factors matrix (n-branch, n-branch)
    :return: LODF matrix (n-branch, n-branch)
    """
    nj = ptdf.shape[1]
    nk = ptdf.shape[0]
    nl = nk
    otdf = np.zeros((nk, nl))

    if nj < 500:
        for j in range(nj):
            for k in range(nk):
                for l in range(nl):
                    val = ptdf[k, j] + lodf[k, l] * ptdf[l, j]
                    if abs(val) > abs(otdf[k, l]):
                        otdf[k, l] = val
    else:
        for j in nb.prange(nj):
            for k in range(nk):
                for l in range(nl):
                    val = ptdf[k, j] + lodf[k, l] * ptdf[l, j]
                    if abs(val) > abs(otdf[k, l]):
                        otdf[k, l] = val
    return otdf


@nb.njit(cache=True)
def make_contingency_flows(lodf, flows):
    """
    Make contingency Sf matrix
    :param lodf: line outage distribution factors
    :param flows: base Sf in MW
    :return: outage Sf for every line after each contingency (n-branch, n-branch[outage])
    """
    nbr = lodf.shape[0]
    omw = np.zeros((nbr, nbr))

    for m in range(nbr):
        for c in range(nbr):
            if m != c:
                omw[m, c] = flows[m] + lodf[m, c] * flows[c]

    return omw


@nb.njit(cache=True)
def make_transfer_limits(ptdf, flows, rates):
    """
    Compute the maximum transfer limits of each branch in normal operation
    :param ptdf: power transfer distribution factors matrix (n-branch, n-bus)
    :param flows: base Sf in MW
    :param rates: array of branch rates
    :return: Max transfer limits vector  (n-branch)
    """
    nbr = ptdf.shape[0]
    nbus = ptdf.shape[1]
    tmc = np.zeros(nbr)

    for m in range(nbr):
        for i in range(nbus):

            if ptdf[m, i] != 0.0:
                val = (rates[m] - flows[m]) / ptdf[m, i]  # I want it with sign

                # update the transference value
                if abs(val) > abs(tmc[m]):
                    tmc[m] = val

    return tmc


@nb.njit(parallel=True)
def make_contingency_transfer_limits(otdf_max, lodf, flows, rates):
    """
    Compute the maximum transfer limits after contingency of each branch
    :param otdf_max: Maximum Outage sensitivity of the branches when transferring power
                     from any bus to the slack  (n-branch, n-branch)
    :param omw: contingency Sf matrix (n-branch, n-branch)
    :param rates: array of branch rates
    :return: Max transfer limits matrix  (n-branch, n-branch)
    """
    nbr = otdf_max.shape[0]
    tmc = np.zeros((nbr, nbr))

    if nbr < 500:
        for m in range(nbr):
            for c in range(nbr):
                if m != c:
                    if otdf_max[m, c] != 0.0:
                        omw = flows[m] + lodf[m, c] * flows[c]  # compute the contingency flow
                        tmc[m, c] = (rates[m] - omw) / otdf_max[m, c]  # i want it with sign
    else:
        for m in nb.prange(nbr):
            for c in range(nbr):
                if m != c:
                    if otdf_max[m, c] != 0.0:
                        omw = flows[m] + lodf[m, c] * flows[c]  # compute the contingency flow
                        tmc[m, c] = (rates[m] - omw) / otdf_max[m, c]  # i want it with sign

    return tmc


def make_worst_contingency_transfer_limits(tmc):

    nbr = tmc.shape[0]
    wtmc = np.zeros((nbr, 2))

    wtmc[:, 0] = tmc.max(axis=1)
    wtmc[:, 1] = tmc.min(axis=1)

    return wtmc


class LinearAnalysis:

    def __init__(self, grid: MultiCircuit, distributed_slack=True, correct_values=True):
        """

        :param grid:
        :param distributed_slack:
        """

        self.grid = grid

        self.distributed_slack = distributed_slack

        self.correct_values = correct_values

        self.numerical_circuit: SnapshotData = None

        self.PTDF = None

        self.LODF = None

        self.__OTDF = None

        self.logger = Logger()

    def run(self):
        """
        Run the PTDF and LODF
        """
        self.numerical_circuit = compile_snapshot_circuit(self.grid)
        islands = self.numerical_circuit.split_into_islands()
        n_br = self.numerical_circuit.nbr
        n_bus = self.numerical_circuit.nbus
        self.PTDF = np.zeros((n_br, n_bus))
        self.LODF = np.zeros((n_br, n_br))

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
                        self.PTDF[np.ix_(island.original_branch_idx, island.original_bus_idx)] = ptdf_island

                        # compute the island LODF
                        lodf_island = make_lodf(Cf=island.Cf,
                                                Ct=island.Ct,
                                                PTDF=ptdf_island,
                                                correct_values=self.correct_values)

                        # assign the LODF to the matrix
                        self.LODF[np.ix_(island.original_branch_idx, island.original_branch_idx)] = lodf_island
                    else:
                        self.logger.add_error('No PQ or PV nodes', 'Island {}'.format(n_island))
                elif len(island.vd) == 0:
                    self.logger.add_warning('No slack bus', 'Island {}'.format(n_island))
                else:
                    self.logger.add_error('More than one slack bus', 'Island {}'.format(n_island))
        else:

            # there is only 1 island, compute the PTDF
            self.PTDF = make_ptdf(Bbus=islands[0].Bbus,
                                  Bf=islands[0].Bf,
                                  pqpv=islands[0].pqpv,
                                  distribute_slack=self.distributed_slack)

            # compute the LODF upon the PTDF
            self.LODF = make_lodf(Cf=islands[0].Cf,
                                  Ct=islands[0].Ct,
                                  PTDF=self.PTDF,
                                  correct_values=self.correct_values)

    @property
    def OTDF(self):
        """
        Maximum Outage sensitivity of the branches when transferring power from any bus to the slack
        LODF: outage transfer distribution factors
        :return: Maximum LODF matrix (n-branch, n-branch)
        """
        if self.__OTDF is None:  # lazy-evaluation
            self.__OTDF = make_otdf_max(self.PTDF, self.LODF)

        return self.__OTDF

    def get_transfer_limits(self, flows):
        """
        compute the normal transfer limits
        :param flows: base Sf in MW
        :return: Max transfer limits vector (n-branch)
        """
        return make_transfer_limits(self.PTDF, flows, self.numerical_circuit.Rates)

    def get_contingency_transfer_limits(self, flows):
        """
        Compute the contingency transfer limits
        :param flows: base Sf in MW
        :return: Max transfer limits matrix (n-branch, n-branch)
        """
        return make_contingency_transfer_limits(self.OTDF, self.LODF, flows, self.numerical_circuit.Rates)

    def get_flows(self, Sbus):
        """
        Compute the time series branch Sf using the PTDF
        :param Sbus: Power injections time series array
        :return: branch active power Sf time series
        """

        # option 2: call the power directly
        Pbr = np.dot(self.PTDF, Sbus.real) * self.grid.Sbase

        return Pbr

    def get_flows_time_series(self, Sbus):
        """
        Compute the time series branch Sf using the PTDF
        :param Sbus: Power injections time series array
        :return: branch active power Sf time series
        """

        # option 2: call the power directly
        Pbr = np.dot(self.PTDF, Sbus.real).T * self.grid.Sbase

        return Pbr
