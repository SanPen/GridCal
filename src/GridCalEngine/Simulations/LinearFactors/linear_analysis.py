# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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

import numpy as np
import numba as nb
import scipy.sparse as sp
from typing import Dict, Union, List
from scipy.sparse.linalg import spsolve

import GridCalEngine.Core.Devices as dev
from GridCalEngine.basic_structures import Logger, Vec, IntVec, CxVec, Mat
from GridCalEngine.Core.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.ac_jacobian import AC_jacobian
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.derivatives import dSf_dV_csc


@nb.njit()
def make_contingency_flows(base_flow: Vec,
                           lodf_factors: Mat,
                           ptdf_factors: Mat,
                           injections: Vec,
                           threshold):
    """
    Compute the general contingency flows
    :param base_flow: base flow (number of branches)
    :param lodf_factors: LODF factors (number of branches, number of branch contingencies)
    :param ptdf_factors: PTDF factors (number of branches, number of injection contingencies)
    :param injections: Array of contingency injections)
    :param threshold: PTDF and LODF threshold
    :return: contingency flows (number of branches)
    """
    nm = lodf_factors.shape[0]
    nc = lodf_factors.shape[1]
    ni = ptdf_factors.shape[1]
    flow_n1 = np.zeros(nm)

    if nm < 100:
        for m in range(nm):
            for c in range(nc):
                if abs(lodf_factors[m, c]) > threshold:
                    flow_n1[m] = base_flow[m] + lodf_factors[m, c] * base_flow[c]

        for m in range(nm):
            for c in range(ni):
                if abs(ptdf_factors[m, c]) > threshold:
                    flow_n1[m] = base_flow[m] + ptdf_factors[m, c] * injections[c]
    else:
        for m in nb.prange(nm):
            for c in range(nc):
                if abs(lodf_factors[m, c]) > threshold:
                    flow_n1[m] = base_flow[m] + lodf_factors[m, c] * base_flow[c]

        for m in nb.prange(nm):
            for c in range(ni):
                if abs(ptdf_factors[m, c]) > threshold:
                    flow_n1[m] = base_flow[m] + ptdf_factors[m, c] * injections[c]

    return flow_n1


class LinearMultiContingency:
    """
    LinearMultiContingency
    """

    def __init__(
            self,
            branch_indices: IntVec,
            bus_indices: IntVec,
            lodf_factors: Mat,
            ptdf_factors: Mat,
            injections_factor: Vec):
        """
        Linear multi contingency object
        :param branch_indices: contingency branch indices.
        :param bus_indices: contingency bus indices.
        :param lodf_factors: LODF factors applicable (all_branches, contingency branches).
        :param ptdf_factors: PTDF factors applicable (all_branches, contingency buses)
        :param injections_factor: Injection contingency factors (len(bus indices))
        """

        assert len(bus_indices) == len(injections_factor)

        self.branch_indices: IntVec = branch_indices
        self.bus_indices: IntVec = bus_indices
        self.lodf_factors: Mat = lodf_factors
        self.ptdf_factors: Mat = ptdf_factors
        self.injections_factor: Vec = injections_factor

    def has_injection_contingencies(self) -> bool:
        """
        Check if this multi-contingency has bus injection modifications
        :return: true / false
        """
        return len(self.bus_indices) > 0

    def get_contingency_flows(self, base_flow: Vec, injections: Union[None, Vec], threshold: float = 1e-5):
        """
        Get contingency flows
        :param base_flow: Base branch flows (nbranch)
        :param injections: Bus injections increments (nbus)
        :return: New flows (nbranch)
        """
        # res = base_flow.copy()
        #
        # if len(self.branch_indices):
        #     res += self.lodf_factors @ base_flow[self.branch_indices]
        #
        # if len(self.bus_indices):
        #     res += self.ptdf_factors @ (self.injections_factor * injections[self.bus_indices])
        #
        # return res

        if len(self.bus_indices):
            injections = self.injections_factor * injections[self.bus_indices]
        else:
            injections = np.zeros(self.ptdf_factors.shape[1])

        return make_contingency_flows(base_flow=base_flow,
                                      lodf_factors=self.lodf_factors,
                                      ptdf_factors=self.ptdf_factors,
                                      injections=injections,
                                      threshold=threshold)


def compute_acptdf(Ybus: sp.csc_matrix,
                   Yf: sp.csc_matrix,
                   F: IntVec,
                   T: IntVec,
                   V: CxVec,
                   pq: IntVec,
                   pv: IntVec,
                   distribute_slack: bool = False) -> Mat:
    """
    Compute the AC-PTDF
    :param Ybus: admittance matrix
    :param Yf: Admittance matrix of the buses "from"
    :param F: array if Branches "from" bus indices
    :param T: array if Branches "to" bus indices
    :param V: voltages array
    :param pq: array of pq node indices
    :param pv: array of pv node indices
    :param distribute_slack: distribute slack?
    :return: AC-PTDF matrix (Branches, buses)
    """
    n = len(V)
    pvpq = np.r_[pv, pq]
    npq = len(pq)
    npv = len(pv)

    # compute the Jacobian
    J = AC_jacobian(Ybus, V, pvpq, pq)

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
    dSf_dVm, dSf_dVa = dSf_dV_csc(Yf.tocsc(), V, F, T)

    # compose the final AC-PTDF
    dPf_dVa = dSf_dVa.real[:, pvpq]
    dPf_dVm = dSf_dVm.real[:, pq]
    PTDF = sp.hstack((dPf_dVa, dPf_dVm)) * dx

    return PTDF


def make_ptdf(Bbus: sp.csc_matrix,
              Bf: sp.csc_matrix,
              pqpv: IntVec,
              distribute_slack: bool = True) -> Mat:
    """
    Build the PTDF matrix
    :param Bbus: DC-linear susceptance matrix
    :param Bf: Bus-branch "from" susceptance matrix
    :param pqpv: array of sorted pq and pv node indices
    :param distribute_slack: distribute the slack?
    :return: PTDF matrix. It is a full matrix of dimensions Branches x buses
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
    dtheta_ref = spsolve(Bref, dP[noslack, :])

    if sp.issparse(dtheta_ref):
        dTheta[noref, :] = dtheta_ref.toarray()
    else:
        dTheta[noref, :] = dtheta_ref

    # compute corresponding change in branch Sf
    # Bf is a sparse matrix
    H = Bf * dTheta

    return H


def make_lodf(Cf: sp.csc_matrix,
              Ct: sp.csc_matrix,
              PTDF: Mat,
              correct_values: bool = False,
              numerical_zero: float = 1e-10) -> Mat:
    """
    Compute the LODF matrix
    :param Cf: Branch "from" -bus connectivity matrix
    :param Ct: Branch "to" -bus connectivity matrix
    :param PTDF: PTDF matrix in numpy array form (Branches, buses)
    :param correct_values: correct values out of the interval
    :param numerical_zero: value considered zero in numerical terms (i.e. 1e-10)
    :return: LODF matrix of dimensions (Branches, Branches)
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

    if correct_values:
        LODF[LODF > 1.2] = 0
        LODF[LODF < -1.2] = 0
        # LODF[LODF > 1.] = 1.
        # LODF[LODF < -1.] = 1.

    return LODF


@nb.njit(cache=True)
def make_otdf(ptdf: Mat,
              lodf: Mat,
              j: int) -> Mat:
    """
    Outage sensitivity of the Branches when transferring power from the bus j to the slack
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


@nb.njit(cache=True)
def make_transfer_limits(ptdf: Mat,
                         flows: Vec,
                         rates: Vec) -> Vec:
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


class LinearMultiContingencies:
    """
    LinearMultiContingencies
    """

    def __init__(self, grid: MultiCircuit):
        """
        Constructor
        :param grid: MultiCircuit
        """
        self.grid: MultiCircuit = grid

        # auxiliary structures
        self.__contingency_group_dict = grid.get_contingency_group_dict()
        self.__bus_index_dict = grid.get_bus_index_dict()
        self.__branches_dict = {b.idtag: i for i, b in enumerate(grid.get_branches_wo_hvdc())}
        self.__generator_dict = {g.idtag: g for g in grid.get_contingency_devices()}

        self.multi_contingencies: List[LinearMultiContingency] = list()

    def update(self, lodf: Mat, ptdf: Mat) -> None:
        """
        Make the LODF with any contingency combination using the declared contingency objects
        :param lodf: original LODF matrix (nbr, nbr)
        :param ptdf: original PTDF matrix (nbr, nbus)
        :return: None
        """

        self.multi_contingencies = list()

        # for each contingency group
        for ic, contingency_group in enumerate(self.grid.contingency_groups):

            # get the group's contingencies
            contingencies = self.__contingency_group_dict[contingency_group.idtag]

            branch_contingency_indices = list()
            bus_contingency_indices = list()
            injections_factors = list()

            # apply the contingencies
            for cnt in contingencies:

                # search for the contingency in the Branches
                if cnt.device_idtag in self.__branches_dict:
                    br_idx = self.__branches_dict.get(cnt.device_idtag, None)

                    if br_idx is not None:
                        if cnt.prop == 'active':
                            branch_contingency_indices.append(br_idx)
                        else:
                            print(f'Unknown contingency property {cnt.prop} at {cnt.name} {cnt.idtag}')
                    else:
                        gen = self.__generator_dict.get(cnt.device_idtag, None)

                        if gen is not None:
                            if cnt.prop == '%':
                                bus_contingency_indices.append(self.__bus_index_dict[gen.bus])
                                injections_factors.append(cnt.value / 100.0)
                else:
                    pass

            branch_contingency_indices = np.array(branch_contingency_indices)
            bus_contingency_indices = np.array(bus_contingency_indices)
            injections_factors = np.array(injections_factors)

            if len(branch_contingency_indices) > 1:
                # Compute M matrix [n, n] (lodf relating the outaged lines to each other)
                M = np.ones((len(branch_contingency_indices), len(branch_contingency_indices)))
                for i in range(len(branch_contingency_indices)):
                    for j in range(len(branch_contingency_indices)):
                        if not (i == j):
                            M[i, j] = -lodf[branch_contingency_indices[i], branch_contingency_indices[j]]

                # Compute LODF for the multiple failure
                lodf_factors = lodf[:, branch_contingency_indices] @ np.linalg.inv(M)

            elif len(branch_contingency_indices) == 1:
                # append values
                lodf_factors = lodf[:, branch_contingency_indices]

            else:
                lodf_factors = np.zeros((lodf.shape[0], 0))

            if len(bus_contingency_indices):
                ptdf_factors = ptdf[:, bus_contingency_indices]
            else:
                ptdf_factors = np.zeros((lodf.shape[0], 0))

            # append values
            self.multi_contingencies.append(LinearMultiContingency(branch_indices=branch_contingency_indices,
                                                                   bus_indices=bus_contingency_indices,
                                                                   lodf_factors=lodf_factors,
                                                                   ptdf_factors=ptdf_factors,
                                                                   injections_factor=injections_factors))


class LinearAnalysis:
    """
    Linear Analysis
    """

    def __init__(self,
                 numerical_circuit: NumericalCircuit,
                 distributed_slack: bool = True,
                 correct_values: bool = False):
        """
        Linear Analysis constructor
        :param numerical_circuit: numerical circuit instance
        :param distributed_slack: boolean to distribute slack
        :param correct_values: boolean to fix out layer values
        """

        self.numerical_circuit: NumericalCircuit = numerical_circuit
        self.distributed_slack: bool = distributed_slack
        self.correct_values: bool = correct_values

        self.PTDF: Union[np.ndarray, None] = None
        self.LODF: Union[np.ndarray, None] = None

        self.logger: Logger = Logger()

    def run(self):
        """
        Run the PTDF and LODF
        """

        # self.numerical_circuit = compile_snapshot_circuit(self.grid)
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

    def get_transfer_limits(self, flows: np.ndarray):
        """
        compute the normal transfer limits
        :param flows: base Sf in MW
        :return: Max transfer limits vector (n-branch)
        """
        return make_transfer_limits(
            ptdf=self.PTDF,
            flows=flows,
            rates=self.numerical_circuit.Rates
        )

    def get_flows(self, Sbus: CxVec) -> Vec:
        """
        Compute the time series branch Sf using the PTDF
        :param Sbus: Power Injections time series array
        :return: branch active power Sf time series
        """
        if len(Sbus.shape) == 1:
            return np.dot(Sbus.real, self.PTDF.T)
        elif len(Sbus.shape) == 2:
            return np.dot(self.PTDF, Sbus.real.T).T
        else:
            raise Exception(f'Sbus has wrong dimensions: {Sbus.shape}')
