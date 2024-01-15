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
from typing import List, Tuple, Union
from scipy import sparse
from scipy.sparse import csc_matrix

from GridCalEngine.basic_structures import Vec, Mat, IntVec
from GridCalEngine.Utils.Sparse.csc import dense_to_csc


class BusesForSrap:
    """
    Buses information for SRAP over a particular branch
    """

    def __init__(self,
                 branch_idx: int,
                 bus_indices: IntVec,
                 sensitivities: Vec,
                 p_available: Vec):
        """

        :param branch_idx:
        :param bus_indices:
        :param sensitivities:
        :param p_available:
        """
        self.branch_idx = branch_idx
        self.bus_indices = bus_indices
        self.sensitivities = sensitivities
        self.p_available = p_available

    def is_solvable(self, overload: float, srap_pmax_mw: float, top_n: int = 1000) -> Tuple[bool, float]:
        """
        Get the maximum amount of power (MW) to dispatch using SRAP
        :param srap_pmax_mw: SRAP limit in MW
        :param overload: Line overload
        :param top_n: maximum number of nodes affecting the oveload
        :return: min(srap_limit, sum(p_available))
        """

        if overload > 0:

            # slice the positive values
            positives = np.where(self.sensitivities >= 0)[0]
            p_available2 = self.p_available[positives]
            sensitivities2 = self.sensitivities[positives]

            # sort greater to lower, more positive first
            idx = np.argsort(-sensitivities2)
            idx2 = idx[:top_n]
            p_available3 = p_available2[idx2]
            sensitivities3 = sensitivities2[idx2]

            # interpolate the srap limit, to get the maximum srap power
            xp = np.cumsum(p_available3)
            fp = np.cumsum(p_available3 * sensitivities3)
            max_srap_power = np.interp(srap_pmax_mw, xp, fp)

            # if the max srap power is less than the overload we cannot solve
            solved = max_srap_power >= overload
        else:

            # slice the negative values
            negatives = np.where(self.sensitivities <= 0)[0]
            p_available2 = self.p_available[negatives]
            sensitivities2 = self.sensitivities[negatives]

            # sort lower to greater, more negative first
            idx = np.argsort(sensitivities2)
            idx2 = idx[:top_n]
            p_available3 = p_available2[idx2]
            sensitivities3 = sensitivities2[idx2]

            # interpolate the srap limit, to get the minimum srap power
            xp = np.cumsum(p_available3)
            fp = np.cumsum(p_available3 * sensitivities3)
            max_srap_power = np.interp(srap_pmax_mw, xp, fp)

            # if the value is grater than the overload we cannot solve
            solved = max_srap_power <= overload

        return solved, max_srap_power


def get_buses_for_srap_list(PTDF: Mat, p_available_per_bus, threshold=1e-3) -> List[BusesForSrap]:
    """
    Generate the structues to compute the SRAP
    :param PTDF: dense PTDF
    :param p_available_per_bus: available power per bus
    :param threshold: Threshold to convert the PTDF to sparse
    :return: List[BusesForSrap]
    """
    PTDFt = dense_to_csc(PTDF, threshold=threshold).tocsr()

    # columns: number of branches, rows: number of nodes
    n_bus, n_br = PTDFt.shape
    buses_for_srap_list = list()
    for i in range(n_br):  # para cada columna i
        a = PTDFt.indptr[i]
        b = PTDFt.indptr[i + 1]
        indices = PTDFt.indices[a:b]
        sensitivities = PTDFt.data[a:b]
        buses_for_srap_list.append(BusesForSrap(branch_idx=i,
                                                bus_indices=indices,
                                                sensitivities=sensitivities,
                                                p_available=p_available_per_bus[indices]))
    return buses_for_srap_list


def product_sparse(a: Mat, b: Mat) -> Mat:
    a = sparse.csr_matrix(a, dtype=np.float16)
    c = a.dot(b)
    return c


def get_PTDF_LODF_NX_sparse_f16(ptdf: Mat, lodf: Mat, failed_lines: IntVec, ov_exists: IntVec) -> Mat:
    """

    :param ptdf:
    :param lodf:
    :param failed_lines: array of failed branches indices in this contingency
    :param ov_exists: array of overloaded branch indices in this contingency
    :return:
    """

    # this is the idea:
    # df0 = ptdf * dp
    # df1 = LODF_NX * dF0 + dF0 = (LODF_NX * ptdf + ptdf) * dp =  PTDF_LODF_NX *dp
    # LODF_NX * ptdf + ptdf = PTDF_LODF_NX
    # LODF_NX = L*M^-1

    # set if I want ...
    want_ptdf_reduction = 1

    # compute a ptdf reduction just for those overloaded branches
    ptdf_reduction = ptdf[ov_exists, :]

    if len(failed_lines) == 0:  # if no lines are failed

        PTDF_LODF_NX = ptdf_reduction

    else:  # if one or more than one lines are failed

        # compute number of branches in the grid, the number of failed lines, and the number of overloads
        num_branches = lodf.shape[0]
        num_failed_lines = len(failed_lines)
        num_over = len(ov_exists)

        # Init LODF_NX
        lodf_nx = np.zeros((num_branches, num_branches), dtype=np.float32)

        # Compute L vector
        L = lodf[:, failed_lines]

        # Compute M matrix [n, n] (lodf relating the outaged lines to each other)
        M = np.ones((num_failed_lines, num_failed_lines))
        for i in range(num_failed_lines):
            for j in range(num_failed_lines):
                if not (i == j):
                    M[i, j] = -lodf[failed_lines[i], failed_lines[j]]

        # Compute LODF_NX
        lodf_nx[:, failed_lines] = np.dot(L, np.linalg.inv(M))
        lodf_nx = lodf_nx[ov_exists, :]  # only lines with overload

        # COMPUTE PTDF_LODF_NX

        if want_ptdf_reduction:
            # make the product
            PTDF_LODF_NX = product_sparse(lodf_nx, ptdf) + ptdf_reduction

        else:
            eye_red = np.zeros((num_over, num_branches))
            eye_red[np.arange(num_over), ov_exists] = 1
            lodf_nx_1 = lodf_nx + eye_red

            # make the product
            PTDF_LODF_NX = product_sparse(lodf_nx_1, ptdf)

    return PTDF_LODF_NX


def get_PTDF_LODF_NX_sparse(ptdf: Mat, lodf: Mat, failed_lines: IntVec, ov_exists: IntVec) -> Mat:
    """

    :param ptdf:
    :param lodf:
    :param failed_lines: array of failed branches indices in this contingency
    :param ov_exists: array of overloaded branch indices in this contingency
    :return:
    """

    # this is the idea:
    # df0 = ptdf * dp
    # df1 = LODF_NX * dF0 + dF0 = (LODF_NX * ptdf + ptdf) * dp =  PTDF_LODF_NX *dp
    # LODF_NX * ptdf + ptdf = PTDF_LODF_NX
    # LODF_NX = L*M^-1

    # set if I want ...
    want_ptdf_reduction = 1

    # compute a ptdf reduction just for those overloaded branches
    ptdf_reduction = ptdf[ov_exists, :]

    if len(failed_lines) == 0:  # if no lines are failed

        PTDF_LODF_NX = ptdf_reduction

    else:  # if one or more than one lines are failed

        # compute number of branches in the grid, the number of failed lines, and the number of overloads
        num_branches = lodf.shape[0]
        num_failed_lines = len(failed_lines)
        num_over = len(ov_exists)

        # Init LODF_NX
        lodf_nx = np.zeros((num_branches, num_branches))

        # Compute L vector
        L = lodf[:, failed_lines]

        # Compute M matrix [n, n] (lodf relating the outaged lines to each other)
        M = np.ones((num_failed_lines, num_failed_lines))
        for i in range(num_failed_lines):
            for j in range(num_failed_lines):
                if not (i == j):
                    M[i, j] = -lodf[failed_lines[i], failed_lines[j]]

        # Compute LODF_NX
        lodf_nx[:, failed_lines] = np.dot(L, np.linalg.inv(M))
        lodf_nx = lodf_nx[ov_exists, :]  # only lines with overload

        # COMPUTE PTDF_LODF_NX

        if want_ptdf_reduction:

            lodf_nx = sparse.csr_matrix(lodf_nx)

            # make the product
            PTDF_LODF_NX = lodf_nx.dot(ptdf) + ptdf_reduction

        else:
            eye_red = np.zeros((num_over, num_branches))
            eye_red[np.arange(num_over), ov_exists] = 1
            lodf_nx_1 = lodf_nx + eye_red
            lodf_nx_1 = sparse.csr_matrix(lodf_nx_1)

            # make the product
            PTDF_LODF_NX = lodf_nx_1.dot(ptdf)

    return PTDF_LODF_NX


@nb.jit(nopython=True, cache=True)
def get_PTDF_LODF_NX(ptdf: Mat, lodf: Mat, failed_lines: IntVec, ov_exists: IntVec) -> Mat:
    """

    :param ptdf:
    :param lodf:
    :param failed_lines: array of failed branches indices in this contingency
    :param ov_exists: array of overloaded branch indices in this contingency
    :return:
    """

    # this is the idea:
    # df0 = ptdf * dp
    # df1 = LODF_NX * dF0 + dF0 = (LODF_NX * ptdf + ptdf) * dp =  PTDF_LODF_NX *dp
    # LODF_NX * ptdf + ptdf = PTDF_LODF_NX
    # LODF_NX = L*M^-1

    # set if I want ...
    want_ptdf_reduction = 0

    # compute a ptdf reduction just for those overloaded branches
    ptdf_reduction = ptdf[ov_exists, :]

    if len(failed_lines) == 0:  # if no lines are failed

        PTDF_LODF_NX = ptdf_reduction

    else:  # if one or more than one lines are failed

        # compute number of branches in the grid, the number of failed lines, and the number of overloads
        num_branches = lodf.shape[0]
        num_failed_lines = len(failed_lines)
        num_over = len(ov_exists)

        # Init LODF_NX
        lodf_nx = np.zeros((num_branches, num_branches))

        # Compute L vector
        L = lodf[:, failed_lines]  # wo numba

        # Compute M matrix [n, n] (lodf relating the outaged lines to each other)
        M = np.ones((num_failed_lines, num_failed_lines))
        for i in range(num_failed_lines):
            for j in range(num_failed_lines):
                if not (i == j):
                    M[i, j] = -lodf[failed_lines[i], failed_lines[j]]

        # Compute LODF_NX
        lodf_nx[:, failed_lines] = np.dot(L, np.linalg.inv(M))
        lodf_nx = lodf_nx[ov_exists, :]  # only lines with overload

        # COMPUTE PTDF_LODF_NX
        if want_ptdf_reduction:

            PTDF_LODF_NX = np.dot(lodf_nx,
                                  ptdf) + ptdf_reduction  # (LODF_NX_red * ptdf + ptdf_red) * dp =  PTDF_LODF_NX_red *dp

        else:
            eye_red = np.zeros((num_over, num_branches))
            eye_red[0:num_over, ov_exists] = 1
            lodf_nx_1 = lodf_nx + eye_red

            PTDF_LODF_NX = np.dot(lodf_nx_1, ptdf)

    return PTDF_LODF_NX


@nb.jit(nopython=True, cache=True)
def compute_srap(p_available: Vec, ov_c: Vec, pmax: float, branch_failed: IntVec, PTDF_LODF_NX: Mat, ov_exists: IntVec):
    """

    :param p_available:
    :param ov_c:
    :param pmax:
    :param branch_failed:
    :param ptdf_lodf_nx:
    :return:
    """

    # get number of generators
    num_gen = len(p_available)

    # create an array to identify if srap is able to solve the overload. initialize to false
    ov_solved = np.zeros(len(ov_c), dtype=nb.int32)

    # we analyze each overload sepparately
    # for i_ov in nb.prange(len(ov_exists)):
    #     ov_exist = ov_exists[i_ov]
    for i_ov, ov_exist in enumerate(ov_exists):

        sens = PTDF_LODF_NX[i_ov, :]  # get PTDF_LODF_NX row of the overloaded line

        # find the sensitivity order of the buses according if theoverload is positive or negative
        if ov_c[ov_exist] > 0:
            i_sens = np.argsort(-sens)  # if the overload is positive, sort + to -
        else:
            i_sens = np.argsort(sens)  # if the overload is negative, sort - to +

        # compute the index of the last full power generator (imax) before arriving to the maximum power
        gen_in = np.cumsum(p_available[i_sens]) <= pmax  # compute the generators providing full power

        if not gen_in[0]:  # if the first generator already exceeds the power

            # compute the first generator effect
            max_correct = pmax * sens[i_sens][0]

        else:

            # computation of the index of the last generator before reaching the maximum power.
            # The first does not exceed (first part of if condition)
            imax = np.max(np.where(gen_in)[0])

            # computation of the product of the available power with its sensitivity up to the imax, both sorted
            max_correct = np.sum(p_available[i_sens][0:imax] * sens[i_sens][0:imax])

            if imax < (num_gen - 1):  # if there are any generators that have not yet reached full power output

                # compute already triggered power
                p_triggered = np.sum(p_available[i_sens][0:imax])

                # additional correction
                add_correct = (pmax - p_triggered) * sens[i_sens][imax + 1]
                max_correct += add_correct

        # compute if the correction is enough, in that case mark it as true True
        c1 = (ov_c[ov_exist] > 0) and (max_correct >= ov_c[ov_exist])  # positive ov
        c2 = (ov_c[ov_exist] < 0) and (max_correct <= ov_c[ov_exist])  # negative ov

        if c1 or c2:
            ov_solved[ov_exist] = 1

        # print(max_correct / pmax)  # avg sensitivity

    return ov_solved
