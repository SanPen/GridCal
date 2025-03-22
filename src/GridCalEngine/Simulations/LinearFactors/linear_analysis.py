# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import numba as nb
import scipy.sparse as sp
from typing import Union, List, Tuple, Dict
from scipy.sparse.linalg import spsolve as scipy_spsolve

from GridCalEngine.basic_structures import Logger, Vec, IntVec, CxVec, Mat, ObjVec, CxMat
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Devices.Aggregation.contingency_group import ContingencyGroup
from GridCalEngine.Devices.Aggregation.contingency import Contingency
from GridCalEngine.Simulations.Derivatives.ac_jacobian import AC_jacobian
from GridCalEngine.Simulations.Derivatives.csc_derivatives import dSf_dV_csc
from GridCalEngine.Utils.Sparse.csc import dense_to_csc
import GridCalEngine.Utils.Sparse.csc2 as csc
from GridCalEngine.Utils.MIP.selected_interface import lpDot
from GridCalEngine.enumerations import ContingencyOperationTypes


@nb.njit()
def make_contingency_flows(base_flow: Vec,
                           lodf_factors: sp.csc_matrix,
                           ptdf_factors: sp.csc_matrix,
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
    branch_number = lodf_factors.shape[0]
    branch_contingency_number = lodf_factors.shape[1]
    injection_number = ptdf_factors.shape[1]
    flow_n1 = np.zeros(branch_number)

    if branch_number < 100:
        for m in range(branch_number):

            # copy the base flow
            flow_n1[m] = base_flow[m]

            # add the branch contingency influences
            for c in range(branch_contingency_number):
                if abs(lodf_factors[m, c]) > threshold:
                    flow_n1[m] += lodf_factors[m, c] * base_flow[c]

            # add the injection influences
            for c in range(injection_number):
                if abs(ptdf_factors[m, c]) > threshold:
                    flow_n1[m] += ptdf_factors[m, c] * injections[c]
    else:

        # parallel version

        for m in nb.prange(branch_number):

            # copy the base flow
            flow_n1[m] = base_flow[m]

            for c in range(branch_contingency_number):
                if abs(lodf_factors[m, c]) > threshold:
                    flow_n1[m] += lodf_factors[m, c] * base_flow[c]

            for c in range(injection_number):
                if abs(ptdf_factors[m, c]) > threshold:
                    flow_n1[m] += ptdf_factors[m, c] * injections[c]

    return flow_n1


def make_acptdf(Ybus: sp.csc_matrix,
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
    dx, ok = csc.spsolve_csc(J, dS)

    # compute branch derivatives
    dSf_dVm, dSf_dVa = dSf_dV_csc(Yf.tocsc(), V, F, T)

    # compose the final AC-PTDF
    dPf_dVa = csc.mat_to_scipy(dSf_dVa.real)[:, pvpq]
    dPf_dVm = csc.mat_to_scipy(dSf_dVm.real)[:, pq]
    PTDF = sp.hstack((dPf_dVa, dPf_dVm)) * dx

    return PTDF


def make_ptdf(Bpqpv: sp.csc_matrix,
              Bf: sp.csc_matrix,
              no_slack: IntVec,
              distribute_slack: bool = True) -> Mat:
    """
    Build the PTDF matrix
    :param Bpqpv: DC-linear susceptance matrix already sliced
    :param Bf: Bus-branch "from" susceptance matrix
    :param no_slack: array of sorted pq and pv node indices
    :param distribute_slack: distribute the slack?
    :return: PTDF matrix. It is a full matrix of dimensions Branches x buses
    """

    n = Bf.shape[1]
    # nb = n
    # nbi = n
    # noref = no_slack  # np.arange(1, nb)
    # noslack = no_slack

    if distribute_slack:
        dP = np.ones((n, n)) * (-1 / (n - 1))
        for i in range(n):
            dP[i, i] = 1.0
    else:
        dP = np.eye(n, n)

    # solve for change in voltage angles
    dTheta = np.zeros((n, n))
    # Bref = Bbus[noslack, :][:, noref].tocsc()
    dtheta_ref = scipy_spsolve(Bpqpv, dP[no_slack, :])

    if sp.issparse(dtheta_ref):
        dTheta[no_slack, :] = dtheta_ref.toarray()
    else:
        dTheta[no_slack, :] = dtheta_ref

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


@nb.njit(cache=True)
def create_M_numba(lodf: Mat, branch_contingency_indices) -> Mat:
    """

    :param lodf:
    :param branch_contingency_indices:
    :return:
    """
    M = np.empty((len(branch_contingency_indices), len(branch_contingency_indices)))
    for i in range(len(branch_contingency_indices)):
        for j in range(len(branch_contingency_indices)):
            if i == j:
                M[i, j] = 1.0
            else:
                M[i, j] = -lodf[branch_contingency_indices[i], branch_contingency_indices[j]]
    return M


class LinearMultiContingency:
    """
    LinearMultiContingency
    """

    def __init__(self,
                 branch_indices: IntVec,
                 bus_indices: IntVec,
                 mlodf_factors: sp.csc_matrix,
                 compensated_ptdf_factors: sp.csc_matrix,
                 injections_factor: Vec):
        """
        Linear multi contingency object
        :param branch_indices: contingency branch indices.
        :param bus_indices: contingency bus indices.

        :param mlodf_factors: MLODF factors applicable (all_branches, contingency branches).
                             Should be: MLODF[k, βδ]

        :param compensated_ptdf_factors: compensated PTDF factors applicable (all_branches, contingency buses)
                                         should be: MLODF[k, βδ] x PTDF[βδ, i] + PTDF[k, i]

        :param injections_factor: Injection contingency factors,
                                  i.e percentage to decrease an injection (len(bus indices))
        """

        assert len(bus_indices) == len(injections_factor)

        self.branch_indices: IntVec = branch_indices
        self.bus_indices: IntVec = bus_indices

        # MLODF[k, βδ]
        self.mlodf_factors: sp.csc_matrix = mlodf_factors

        # MLODF[k, βδ] x PTDF[βδ, i] + PTDF[k, i]
        self.compensated_ptdf_factors: sp.csc_matrix = compensated_ptdf_factors

        # percentage to decrease an injection, used to compute ΔP
        self.injections_factor: Vec = injections_factor

    def has_injection_contingencies(self) -> bool:
        """
        Check if this multi-contingency has bus injection modifications
        :return: true / false
        """
        return len(self.bus_indices) > 0

    def get_contingency_flows(self, base_flow: Vec, injections: Vec, tau: Vec = None) -> Vec:
        """
        Get contingency flows
        :param base_flow: Base branch flows (nbranch)
        :param injections: Bus injections increments (nbus)
        :param tau: Phase shifter angles (rad)
        :return: New flows (nbranch)
        """

        flow = base_flow.copy()

        if len(self.branch_indices):
            # MLODF[k, βδ] x Pf0[βδ]
            flow += self.mlodf_factors @ base_flow[self.branch_indices]

        if len(self.bus_indices):
            injection_delta = injections[self.bus_indices]

            # (MLODF[k, βδ] x PTDF[βδ, i] + PTDF[k, i]) x ΔP[i]
            flow += self.compensated_ptdf_factors @ injection_delta

        return flow

    def get_lp_contingency_flows(self,
                                 base_flow: ObjVec,
                                 injections: ObjVec) -> ObjVec:
        """
        Get contingency flows using the LP interface equations
        :param base_flow: Base branch flows (nbranch)
        :param injections: Bus injections (nbus)
        :return: New flows (nbranch)
        """

        flow = base_flow.copy()

        if len(self.branch_indices):
            flow += lpDot(self.mlodf_factors, base_flow[self.branch_indices])

        if len(self.bus_indices):
            injection_delta = self.injections_factor * injections[self.bus_indices]
            flow += lpDot(self.compensated_ptdf_factors, injection_delta[self.bus_indices])

        return flow


class ContingencyIndices:
    """
    Contingency indices
    """

    def __init__(self,
                 contingency_group: ContingencyGroup,
                 contingency_group_dict: Dict[str, List[Contingency]],
                 branches_dict: Dict[str, int],
                 generator_bus_index_dict: Dict[str, int]):
        """
        Contingency indices
        :param contingency_group: ContingencyGroup
        :param contingency_group_dict: dictionary to get the list of contingencies matching a contingency group
        :param branches_dict: dictionary to get the branch index by the branch idtag
        :param generator_bus_index_dict: dictionary to get the generator bus index by the generator idtag
        """

        # get the group's contingencies
        contingencies = contingency_group_dict[contingency_group.idtag]

        branch_contingency_indices_list = list()
        bus_contingency_indices_list = list()
        injections_factors_list = list()

        # apply the contingencies
        for cnt in contingencies:

            if cnt.prop == ContingencyOperationTypes.Active:

                # search for the contingency in the Branches
                br_idx = branches_dict.get(cnt.device_idtag, None)
                if br_idx is not None:
                    branch_contingency_indices_list.append(br_idx)
                else:
                    print(f"contingency branch {cnt.device_idtag} not found")

            elif cnt.prop == ContingencyOperationTypes.PowerPercentage:
                bus_idx = generator_bus_index_dict.get(cnt.device_idtag, None)
                if bus_idx is not None:
                    bus_contingency_indices_list.append(bus_idx)
                    injections_factors_list.append(cnt.value / 100.0)
                else:
                    print(f"contingency generator {cnt.device_idtag} not found")
            else:
                print(f'Unknown branch contingency property {cnt.prop} at {cnt.name} {cnt.idtag}')

        self.branch_contingency_indices = np.array(branch_contingency_indices_list)
        self.bus_contingency_indices = np.array(bus_contingency_indices_list)
        self.injections_factors = np.array(injections_factors_list)


class LinearMultiContingencies:
    """
    LinearMultiContingencies
    """

    def __init__(self, grid: MultiCircuit, contingency_groups_used: List[ContingencyGroup]):
        """
        Constructor
        :param grid: MultiCircuit
        """
        self.grid: MultiCircuit = grid

        self.contingency_groups_used = contingency_groups_used

        # auxiliary structures
        self.__contingency_group_dict = grid.get_contingency_group_dict()
        bus_index_dict = grid.get_bus_index_dict()
        self.__branches_dict = {b.idtag: i for i, b in enumerate(grid.get_branches_wo_hvdc())}
        self.__generator_bus_index_dict = {g.idtag: bus_index_dict[g.bus] for g in grid.get_generators()}

        self.contingency_indices_list = list()

        # for each contingency group
        for ic, contingency_group in enumerate(self.contingency_groups_used):
            self.contingency_indices_list.append(
                ContingencyIndices(
                    contingency_group=contingency_group,
                    contingency_group_dict=self.__contingency_group_dict,
                    branches_dict=self.__branches_dict,
                    generator_bus_index_dict=self.__generator_bus_index_dict
                )
            )

        # list of LinearMultiContingency objects that are used later to compute the contingency flows
        self.multi_contingencies: List[LinearMultiContingency] = list()

    @property
    def contingency_group_dict(self) -> Dict[str, List[Contingency]]:
        return self.__contingency_group_dict

    def get_contingency_group_names(self) -> List[str]:
        """
        Returns a list of the names of the used contingency groups
        :return:
        """
        return [elm.name for elm in self.contingency_groups_used]

    def compute(self,
                lodf: Mat,
                ptdf: Mat,
                ptdf_threshold: float = 0.0001,
                lodf_threshold: float = 0.0001) -> None:
        """
        Make the LODF with any contingency combination using the declared contingency objects
        :param lodf: original LODF matrix (nbr, nbr)
        :param ptdf: original PTDF matrix (nbr, nbus)
        :param ptdf_threshold: threshold to discard values
        :param lodf_threshold: Threshold for LODF conversion to sparse
        :return: None
        """

        self.multi_contingencies = list()

        # for each contingency group
        for ic, contingency_group in enumerate(self.contingency_groups_used):

            contingency_indices: ContingencyIndices = self.contingency_indices_list[ic]

            if len(contingency_indices.branch_contingency_indices) > 1:

                # Flow =
                #   Pf0[k]
                # + MLODF[k, bd] * Pf0[bd]
                # + MLODF[k, bd] * PTDF[bd, i] * dP[i]
                # + PTDF[k, i] * dPi

                # Compute M matrix [n, n] (lodf relating the outaged lines to each other)
                M = create_M_numba(lodf=lodf,
                                   branch_contingency_indices=contingency_indices.branch_contingency_indices)
                L = lodf[:, contingency_indices.branch_contingency_indices]

                try:
                    # Compute LODF for the multiple failure MLODF[k, βδ]
                    mlodf_factors = dense_to_csc(mat=L @ np.linalg.inv(M),
                                                 threshold=lodf_threshold)

                except np.linalg.LinAlgError:
                    # Done to capture antenna when computing multiples contingencies
                    mlodf_factors = dense_to_csc(mat=L @ np.linalg.pinv(M),
                                                 threshold=lodf_threshold)

                if len(contingency_indices.bus_contingency_indices) > 0:
                    # this is PTDF[k, i]
                    ptdf_k_i = dense_to_csc(mat=ptdf[:, contingency_indices.bus_contingency_indices],
                                            threshold=ptdf_threshold)
                    # PTDF[βδ, i]
                    ptdf_bd_i = dense_to_csc(
                        mat=ptdf[np.ix_(contingency_indices.branch_contingency_indices,
                                        contingency_indices.bus_contingency_indices)],
                        threshold=ptdf_threshold
                    )

                else:
                    ptdf_k_i = sp.csc_matrix((ptdf.shape[0], ptdf.shape[1]))

                    # PTDF[βδ, i]
                    ptdf_bd_i = dense_to_csc(mat=ptdf[contingency_indices.branch_contingency_indices, :],
                                             threshold=ptdf_threshold)

                # must compute: MLODF[k, βδ] x PTDF[βδ, i] + PTDF[k, i]
                compensated_ptdf_factors = mlodf_factors @ ptdf_bd_i + ptdf_k_i

            elif len(contingency_indices.branch_contingency_indices) == 1:

                # Pf0[k]
                # + LODF[k, c] * Pf0[c]
                # + LODF[k, c] * PTDF[c, i] * dPi
                # + PTDF[k, i] * dPi

                # append values
                mlodf_factors = dense_to_csc(mat=lodf[:, contingency_indices.branch_contingency_indices],
                                             threshold=lodf_threshold)

                if len(contingency_indices.bus_contingency_indices) > 0:
                    # single branch and single bus contingency

                    # this is PTDF[k, i]
                    ptdf_k_i = dense_to_csc(mat=ptdf[:, contingency_indices.bus_contingency_indices],
                                            threshold=ptdf_threshold)
                    # PTDF[βδ, i]
                    ptdf_bd_i = dense_to_csc(
                        mat=ptdf[np.ix_(contingency_indices.branch_contingency_indices,
                                        contingency_indices.bus_contingency_indices)],
                        threshold=ptdf_threshold
                    )

                    # must compute: MLODF[k, βδ] x PTDF[βδ, i] + PTDF[k, i]
                    compensated_ptdf_factors = mlodf_factors @ ptdf_bd_i + ptdf_k_i
                else:
                    # single branch contingency, no bus contingency
                    compensated_ptdf_factors = sp.csc_matrix(([], [], [0]), shape=(lodf.shape[0], 0))

            else:
                mlodf_factors = sp.csc_matrix(([], [], [0]), shape=(lodf.shape[0], 0))
                if len(contingency_indices.bus_contingency_indices) > 0:
                    # only bus contingencies
                    compensated_ptdf_factors = ptdf[:, contingency_indices.bus_contingency_indices]
                else:
                    # no bus or branch contingencies
                    compensated_ptdf_factors = sp.csc_matrix(([], [], [0]), shape=(lodf.shape[0], 0))

            # append values
            self.multi_contingencies.append(
                LinearMultiContingency(
                    branch_indices=contingency_indices.branch_contingency_indices,
                    bus_indices=contingency_indices.bus_contingency_indices,
                    mlodf_factors=mlodf_factors,
                    compensated_ptdf_factors=compensated_ptdf_factors,
                    injections_factor=contingency_indices.injections_factors
                )
            )


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

        self.logger: Logger = Logger()

        islands = numerical_circuit.split_into_islands()
        n_br = numerical_circuit.nbr
        n_bus = numerical_circuit.nbus

        self.PTDF = np.zeros((n_br, n_bus))
        self.LODF = np.zeros((n_br, n_br))

        # compute the PTDF per islands
        if len(islands) > 0:
            for n_island, island in enumerate(islands):

                indices = island.get_simulation_indices()

                # no slacks will make it impossible to compute the PTDF analytically
                if len(indices.vd) == 1:
                    if len(indices.no_slack) > 0:

                        adml = island.get_linear_admittance_matrices(indices=indices)

                        Bpqpv = adml.get_Bred(pqpv=indices.no_slack)

                        # compute the PTDF of the island
                        ptdf_island = make_ptdf(Bpqpv=Bpqpv,
                                                Bf=adml.Bf,
                                                no_slack=indices.no_slack,
                                                distribute_slack=distributed_slack)

                        # assign the PTDF to the main PTDF matrix
                        self.PTDF[np.ix_(island.passive_branch_data.original_idx,
                                         island.bus_data.original_idx)] = ptdf_island

                        # compute the island LODF
                        lodf_island = make_lodf(Cf=island.passive_branch_data.Cf.tocsc(),
                                                Ct=island.passive_branch_data.Ct.tocsc(),
                                                PTDF=ptdf_island,
                                                correct_values=correct_values)

                        # assign the LODF to the main LODF matrix
                        self.LODF[np.ix_(island.passive_branch_data.original_idx,
                                         island.passive_branch_data.original_idx)] = lodf_island
                    else:
                        self.logger.add_error('No PQ or PV nodes', 'Island {}'.format(n_island))

                elif len(indices.vd) == 0:
                    self.logger.add_warning('No slack bus', 'Island {}'.format(n_island))

                else:
                    self.logger.add_error('More than one slack bus', 'Island {}'.format(n_island))
        else:
            # there are no islands
            pass

    def get_transfer_limits(self, flows: np.ndarray, rates: Vec):
        """
        Compute the maximum transfer limits of each branch in normal operation
        :param flows: base Sf in MW
        :param rates: rates in MW
        :return: Max transfer limits vector (n-branch)
        """
        return make_transfer_limits(
            ptdf=self.PTDF,
            flows=flows,
            rates=rates
        )

    def get_flows(self, Sbus: Union[CxVec, CxMat]) -> Union[CxVec, CxMat]:
        """
        Compute the time series branch Sf using the PTDF
        :param Sbus: Power Injections time series array (nbus) for 1D, (time, nbus) for 2D
        :return: branch active power Sf (nbus) for 1D, (time, nbus) for 2D
        """
        if Sbus.ndim == 1:
            return np.dot(self.PTDF, Sbus.real)
        elif Sbus.ndim == 2:
            return np.dot(self.PTDF, Sbus.real.T).T
        else:
            raise Exception(f'Sbus has unsupported dimensions: {Sbus.shape}')
