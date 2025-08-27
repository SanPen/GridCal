# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import numpy as np
import numba as nb
import warnings
import scipy.sparse as sp
from typing import Union, List, Dict, Tuple, TYPE_CHECKING

from scipy.sparse import lil_matrix
from scipy.sparse.linalg import spsolve as scipy_spsolve

from VeraGridEngine import DeviceType
from VeraGridEngine.basic_structures import Logger, Vec, IntVec, CxVec, Mat, ObjVec, CxMat, BoolVec
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Devices.Aggregation.contingency_group import ContingencyGroup
from VeraGridEngine.Devices.Aggregation.contingency import Contingency
from VeraGridEngine.Simulations.Derivatives.ac_jacobian import AC_jacobian
from VeraGridEngine.Simulations.Derivatives.csc_derivatives import dSf_dV_csc
from VeraGridEngine.Utils.Sparse.csc import dense_to_csc
import VeraGridEngine.Utils.Sparse.csc2 as csc
from VeraGridEngine.Utils.MIP.selected_interface import lpDot1D_changes
from VeraGridEngine.enumerations import ContingencyOperationTypes

if TYPE_CHECKING:
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit


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


def make_jacobian_ptdf(Ybus: sp.csc_matrix,
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
    H = Bf @ dTheta

    return H


def make_acdc_ptdf(nc: NumericalCircuit, logger: Logger,
                   distribute_slack: bool = False) -> Mat:
    """
    Build the ACDC PTDF matrix
    :param nc: NumericalCircuit
    :param logger: Logger
    :param distribute_slack: distribute the slack?
    :return: PTDF matrix. It is a full matrix of dimensions Branches x buses
    """
    n = nc.nbus

    # mount the base matrix
    A = lil_matrix((n, n))
    Af = lil_matrix((nc.nbr, n))

    for k in range(nc.nbr):
        f = nc.passive_branch_data.F[k]
        t = nc.passive_branch_data.T[k]

        if nc.bus_data.is_dc[f] and nc.bus_data.is_dc[t]:
            # this is a dc branch
            ys = float(nc.passive_branch_data.active[k]) / (nc.passive_branch_data.R[k] + 1e-20)

        elif not nc.bus_data.is_dc[f] and not nc.bus_data.is_dc[t]:
            # this is an ac branch
            ys = float(nc.passive_branch_data.active[k]) / (nc.passive_branch_data.X[k] + 1e-20)

        else:
            # this is an error
            raise AttributeError(f"The branch {k} is nether fully AC not fully DC :(")

        Af[k, f] = ys
        Af[k, t] = -ys

        A[f, f] += ys
        A[f, t] -= ys
        A[t, f] -= ys
        A[t, t] += ys

    # fake impedances for converters
    for k in range(nc.nvsc):
        f = nc.vsc_data.F[k]
        t = nc.vsc_data.T[k]
        ys = 1e15
        A[f, f] += ys
        A[f, t] -= ys
        A[t, f] -= ys
        A[t, t] += ys

    # fake impedances for hvdc
    for k in range(nc.nhvdc):
        f = nc.hvdc_data.F[k]
        t = nc.hvdc_data.T[k]
        ys = 1e15
        A[f, f] += ys
        A[f, t] -= ys
        A[t, f] -= ys
        A[t, t] += ys

    # detect how to slice
    no_slack = list()
    dc_sl = list()
    ac_sl = list()
    for i in range(n):
        if nc.bus_data.is_dc[i]:
            if nc.bus_data.is_vm_controlled[i]:
                dc_sl.append(i)
            else:
                no_slack.append(i)
        else:
            if nc.bus_data.is_vm_controlled[i] and nc.bus_data.is_va_controlled[i]:
                ac_sl.append(i)
            else:
                no_slack.append(i)

    if distribute_slack:
        dP = np.ones((n, n)) * (-1 / (n - 1))
        for i in range(n):
            dP[i, i] = 1.0
    else:
        dP = np.eye(n, n)

    Ared = A[no_slack, :][:, no_slack]
    Pred = dP[no_slack, :]

    dTheta = np.zeros((n, n))

    with warnings.catch_warnings():
        warnings.filterwarnings('error')
        try:
            dtheta_ref = sp.linalg.spsolve(Ared.tocsc(), Pred)
            dTheta[no_slack, :] = dtheta_ref
        except sp.linalg.MatrixRankWarning as e:
            logger.add_error("ACDC PTDF singular matrix. Does each subgrid have a slack?")

    H = Af @ dTheta

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


class LinearAnalysis:
    """
    Linear Analysis
    """

    def __init__(self,
                 nc: NumericalCircuit,
                 distributed_slack: bool = True,
                 correct_values: bool = False,
                 logger: Logger = Logger()):
        """
        Linear Analysis constructor
        :param nc: numerical circuit instance
        :param distributed_slack: boolean to distribute slack
        :param correct_values: boolean to fix out layer values
        """

        self.logger: Logger = logger

        islands: List[NumericalCircuit] = nc.split_into_islands()
        n_br = nc.nbr
        n_bus = nc.nbus
        n_hvdc = nc.hvdc_data.nelm
        n_vsc = nc.vsc_data.nelm

        self.PTDF = np.zeros((n_br, n_bus))
        self.LODF = np.zeros((n_br, n_br))

        self.HvdcDF: Mat = np.zeros((n_br, n_hvdc))
        self.HvdcODF: Mat = np.zeros((n_br, n_hvdc))

        self.VscDF: Mat = np.zeros((n_br, n_vsc))
        self.VscODF: Mat = np.zeros((n_br, n_vsc))

        # compute the PTDF per islands
        if len(islands) > 0:
            for n_island, island in enumerate(islands):

                indices = island.get_simulation_indices()

                # no slacks will make it impossible to compute the PTDF analytically
                if len(indices.vd) == 1:
                    if len(indices.no_slack) > 0:

                        if island.bus_data.is_dc.any():
                            ptdf_island = make_acdc_ptdf(nc=island,
                                                         logger=self.logger,
                                                         distribute_slack=distributed_slack)

                        else:
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

        # compute the HVDC PTDF (HVDC lines, Buses)
        # A_hvdc = lil_matrix((n_bus, n_hvdc))
        for k in range(n_hvdc):
            f = nc.hvdc_data.F[k]
            t = nc.hvdc_data.T[k]
            # A_hvdc[f, k] = -1  # subtracts power at the "from" side
            # A_hvdc[t, k] = 1  # injects power at the "to" side
            self.HvdcDF[:, k] = self.PTDF[:, t] - self.PTDF[:, f]
            self.HvdcODF[:, k] = self.PTDF[:, f] - self.PTDF[:, t]

        # self.HvdcDF = self.PTDF @ A_hvdc

        # compute the VSC PTDF (HVDC lines, Buses)
        # A_vsc = lil_matrix((n_bus, n_vsc))
        for k in range(n_vsc):
            f = nc.vsc_data.F[k]
            t = nc.vsc_data.T[k]
            # A_vsc[f, k] = -1  # subtracts power at the "from" side
            # A_vsc[t, k] = 1  # injects power at the "to" side
            self.VscDF[:, k] = self.PTDF[:, t] - self.PTDF[:, f]
            self.VscODF[:, k] = self.PTDF[:, f] - self.PTDF[:, t]

        # self.VscDF = self.PTDF @ A_vsc

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


class LinearMultiContingency:
    """
    LinearMultiContingency
    """

    def __init__(self,
                 branch_indices: IntVec,
                 hvdc_indices: IntVec,
                 vsc_indices: IntVec,
                 bus_indices: IntVec,
                 mlodf_factors: sp.csc_matrix,
                 compensated_ptdf_factors: sp.csc_matrix,
                 hvdc_odf: sp.csc_matrix,
                 vsc_odf: sp.csc_matrix,
                 injections_factor: Vec):
        """
        Linear multi contingency object
        :param branch_indices: contingency branch indices.
        :param hvdc_indices: HvdcLine indices that belong into the contingency
        :param vsc_indices: VSC indices that belong into the contingency
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
        self.hvdc_indices: IntVec = hvdc_indices
        self.vsc_indices: IntVec = vsc_indices
        self.bus_indices: IntVec = bus_indices

        # MLODF[k, βδ]
        self.mlodf_factors: sp.csc_matrix = mlodf_factors

        # MLODF[k, βδ] x PTDF[βδ, i] + PTDF[k, i]
        self.compensated_ptdf_factors: sp.csc_matrix = compensated_ptdf_factors

        # percentage to decrease an injection, used to compute ΔP
        self.injections_factor: Vec = injections_factor

        self.hvdc_odf = hvdc_odf
        self.vsc_odf = vsc_odf

    def has_injection_contingencies(self) -> bool:
        """
        Check if this multi-contingency has bus injection modifications
        :return: true / false
        """
        return len(self.bus_indices) > 0

    def get_contingency_flows(self,
                              base_branches_flow: Vec,
                              injections: Vec,
                              hvdc_flow: Vec | None = None,
                              vsc_flow: Vec | None = None) -> Vec:
        """
        Get contingency flows
        :param base_branches_flow: Base branch flows (nbranch)
        :param injections: Bus injections increments (nbus)
        :param hvdc_flow: Base HvdcLine flows (n_hvdc)
        :param vsc_flow: Base Vsc flows (n_vsc)
        :return: New flows (nbranch)
        """

        flow = base_branches_flow.copy()

        if len(self.branch_indices):
            # MLODF[k, βδ] x Pf0[βδ]
            flow += self.mlodf_factors @ base_branches_flow[self.branch_indices]

        if len(self.hvdc_indices) and hvdc_flow is not None:
            flow += self.hvdc_odf @ hvdc_flow[self.hvdc_indices]

        if len(self.vsc_indices) and vsc_flow is not None:
            flow += self.vsc_odf @ vsc_flow[self.vsc_indices]

        if len(self.bus_indices):
            injection_delta = injections[self.bus_indices]

            # (MLODF[k, βδ] x PTDF[βδ, i] + PTDF[k, i]) x ΔP[i]
            flow += self.compensated_ptdf_factors @ injection_delta

        return flow

    def get_lp_contingency_flows(self,
                                 base_flow: ObjVec,
                                 injections: ObjVec,
                                 hvdc_flow: ObjVec | None = None,
                                 vsc_flow: ObjVec | None = None) -> Tuple[ObjVec, BoolVec, IntVec]:
        """
        Get contingency flows using the LP interface equations
        :param base_flow: Base branch flows (nbranch)
        :param injections: Bus injections (nbus)
        :param hvdc_flow: Base HvdcLine flows (n_hvdc)
        :param vsc_flow: Base Vsc flows (n_vsc)
        :return: New flows (nbranch)
        """
        mask = np.zeros(len(base_flow), dtype=bool)
        flow = base_flow.copy()
        changed_idx = np.zeros(0, dtype=int)

        if len(self.branch_indices) > 0:
            inc, changed_idx = lpDot1D_changes(self.mlodf_factors, base_flow[self.branch_indices])
            mask[changed_idx] = True
            flow[changed_idx] += inc[changed_idx]

        if len(self.hvdc_indices) > 0 and hvdc_flow is not None:
            inc, changed_idx = lpDot1D_changes(self.hvdc_odf, hvdc_flow[self.hvdc_indices])
            mask[changed_idx] = True
            flow[changed_idx] += inc[changed_idx]

        if len(self.vsc_indices) > 0 and vsc_flow is not None:
            inc, changed_idx = lpDot1D_changes(self.vsc_odf, vsc_flow[self.vsc_indices])
            mask[changed_idx] = True
            flow[changed_idx] += inc[changed_idx]

        if len(self.bus_indices) > 0:
            injection_delta = self.injections_factor * injections[self.bus_indices]
            inc, changed_idx = lpDot1D_changes(self.compensated_ptdf_factors, injection_delta[self.bus_indices])
            mask[changed_idx] = True
            flow[changed_idx] += inc[changed_idx]

        return flow, mask, changed_idx

    def get_alpha_n1(self, dP: Vec, dT: float):
        """
        Compute the N-1 sensitivities to the inter-area exchange
        :param dP: Inter-area power exchanges computed with (compute_dP)
        :param dT: Exchange amount (MW) usually a unitary increment is sufficient (use the value used to compute dP)
        :return: N-1 branch exchange sensitivities
        """

        # (MLODF[k, βδ] x PTDF[βδ, i] + PTDF[k, i]) x ΔP[i]
        dflow = self.compensated_ptdf_factors @ dP[self.bus_indices]

        # dflow_n1 = dflow[m] + lodf[m, c] * dflow[c]

        # MLODF[k, βδ] x Pf0[βδ]
        dflow_n1 = self.mlodf_factors @ dflow[self.branch_indices]

        alpha_n1 = dflow_n1 / dT

        return alpha_n1


class ContingencyIndices:
    """
    Contingency indices
    """

    def __init__(self,
                 contingency_group: ContingencyGroup,
                 contingency_group_dict: Dict[str, List[Contingency]],
                 branches_dict: Dict[str, int],
                 hvdc_dict: Dict[str, int],
                 vsc_dict: Dict[str, int],
                 generator_bus_index_dict: Dict[str, int]):
        """
        Contingency indices
        :param contingency_group: ContingencyGroup
        :param contingency_group_dict: dictionary to get the list of contingencies matching a contingency group
        :param branches_dict: dictionary to get the branch index by the branch idtag
        :param generator_bus_index_dict: dictionary to get the generator bus index by the generator idtag
        """

        # get the group's contingencies
        contingencies: List[Contingency] = contingency_group_dict[contingency_group.idtag]

        branch_contingency_indices_list = list()
        hvdc_contingency_indices_list = list()
        vsc_contingency_indices_list = list()
        bus_contingency_indices_list = list()
        injections_factors_list = list()

        # apply the contingencies
        for cnt in contingencies:

            if cnt.prop == ContingencyOperationTypes.Active:

                if cnt.tpe == DeviceType.HVDCLineDevice:
                    hvdc_idx = hvdc_dict.get(cnt.device_idtag, None)
                    if hvdc_idx is not None:
                        hvdc_contingency_indices_list.append(hvdc_idx)

                elif cnt.tpe == DeviceType.VscDevice:
                    vsc_idx = vsc_dict.get(cnt.device_idtag, None)
                    if vsc_idx is not None:
                        vsc_contingency_indices_list.append(vsc_idx)

                else:
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

        self.branch_contingency_indices = np.array(branch_contingency_indices_list, dtype=int)
        self.hvdc_contingency_indices = np.array(hvdc_contingency_indices_list, dtype=int)
        self.vsc_contingency_indices = np.array(vsc_contingency_indices_list, dtype=int)
        self.bus_contingency_indices = np.array(bus_contingency_indices_list, dtype=int)
        self.injections_factors = np.array(injections_factors_list, dtype=float)


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
        self.__branches_dict = grid.get_branches_index_dict2(add_vsc=False, add_hvdc=False, add_switch=True)
        self.__hvdc_dict = grid.get_hvdc_index_dict()
        self.__vsc_dict = grid.get_vsc_index_dict()
        self.__generator_bus_index_dict = {g.idtag: bus_index_dict[g.bus] for g in grid.get_generators()}

        self.contingency_indices_list = list()

        # for each contingency group
        for ic, contingency_group in enumerate(self.contingency_groups_used):
            self.contingency_indices_list.append(
                ContingencyIndices(
                    contingency_group=contingency_group,
                    contingency_group_dict=self.__contingency_group_dict,
                    branches_dict=self.__branches_dict,
                    hvdc_dict=self.__hvdc_dict,
                    vsc_dict=self.__vsc_dict,
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
                lin: LinearAnalysis,
                ptdf_threshold: float = 0.0001,
                lodf_threshold: float = 0.0001) -> None:
        """
        Make the LODF with any contingency combination using the declared contingency objects
        :param lin: LinearAnalysis instance
        :param ptdf_threshold: threshold to discard values
        :param lodf_threshold: Threshold for LODF conversion to sparse
        :return: None
        """

        # lodf: Mat = lin.LODF
        # ptdf: Mat = lin.PTDF
        self.multi_contingencies.clear()

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
                M = create_M_numba(lodf=lin.LODF,
                                   branch_contingency_indices=contingency_indices.branch_contingency_indices)
                L = lin.LODF[:, contingency_indices.branch_contingency_indices]

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
                    ptdf_k_i = dense_to_csc(mat=lin.PTDF[:, contingency_indices.bus_contingency_indices],
                                            threshold=ptdf_threshold)
                    # PTDF[βδ, i]
                    ptdf_bd_i = dense_to_csc(
                        mat=lin.PTDF[np.ix_(contingency_indices.branch_contingency_indices,
                                            contingency_indices.bus_contingency_indices)],
                        threshold=ptdf_threshold
                    )

                else:
                    ptdf_k_i = sp.csc_matrix((lin.PTDF.shape[0], lin.PTDF.shape[1]))

                    # PTDF[βδ, i]
                    ptdf_bd_i = dense_to_csc(mat=lin.PTDF[contingency_indices.branch_contingency_indices, :],
                                             threshold=ptdf_threshold)

                # must compute: MLODF[k, βδ] x PTDF[βδ, i] + PTDF[k, i]
                compensated_ptdf_factors = mlodf_factors @ ptdf_bd_i + ptdf_k_i

            elif len(contingency_indices.branch_contingency_indices) == 1:

                # Pf0[k]
                # + LODF[k, c] * Pf0[c]
                # + LODF[k, c] * PTDF[c, i] * dPi
                # + PTDF[k, i] * dPi

                # append values
                mlodf_factors = dense_to_csc(mat=lin.LODF[:, contingency_indices.branch_contingency_indices],
                                             threshold=lodf_threshold)

                if len(contingency_indices.bus_contingency_indices) > 0:
                    # single branch and single bus contingency

                    # this is PTDF[k, i]
                    ptdf_k_i = dense_to_csc(mat=lin.PTDF[:, contingency_indices.bus_contingency_indices],
                                            threshold=ptdf_threshold)
                    # PTDF[βδ, i]
                    ptdf_bd_i = dense_to_csc(
                        mat=lin.PTDF[np.ix_(contingency_indices.branch_contingency_indices,
                                            contingency_indices.bus_contingency_indices)],
                        threshold=ptdf_threshold
                    )

                    # must compute: MLODF[k, βδ] x PTDF[βδ, i] + PTDF[k, i]
                    compensated_ptdf_factors = mlodf_factors @ ptdf_bd_i + ptdf_k_i
                else:
                    # single branch contingency, no bus contingency
                    compensated_ptdf_factors = sp.csc_matrix(([], [], [0]), shape=(lin.LODF.shape[0], 0))

            else:
                mlodf_factors = sp.csc_matrix(([], [], [0]), shape=(lin.LODF.shape[0], 0))
                if len(contingency_indices.bus_contingency_indices) > 0:
                    # only bus contingencies
                    compensated_ptdf_factors = lin.PTDF[:, contingency_indices.bus_contingency_indices]
                else:
                    # no bus or branch contingencies
                    compensated_ptdf_factors = sp.csc_matrix(([], [], [0]), shape=(lin.LODF.shape[0], 0))

            # compute the hvdc and vsc contingency distribution factor matrices
            hvdc_odf: sp.csc_matrix = dense_to_csc(
                mat=lin.HvdcODF[:, contingency_indices.hvdc_contingency_indices],
                threshold=lodf_threshold
            )
            vsc_odf: sp.csc_matrix = dense_to_csc(
                mat=lin.VscODF[:, contingency_indices.vsc_contingency_indices],
                threshold=lodf_threshold
            )
            # append values
            self.multi_contingencies.append(
                LinearMultiContingency(
                    branch_indices=contingency_indices.branch_contingency_indices,
                    hvdc_indices=contingency_indices.hvdc_contingency_indices,
                    vsc_indices=contingency_indices.vsc_contingency_indices,
                    bus_indices=contingency_indices.bus_contingency_indices,
                    mlodf_factors=mlodf_factors,
                    compensated_ptdf_factors=compensated_ptdf_factors,
                    injections_factor=contingency_indices.injections_factors,
                    hvdc_odf=hvdc_odf,
                    vsc_odf=vsc_odf
                )
            )
