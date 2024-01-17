# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
from typing import List, Tuple

from GridCalEngine.basic_structures import Vec, Mat, IntVec
from GridCalEngine.Utils.Sparse.csc_numba import get_sparse_array_numba


@nb.njit(cache=True)
def get_valid_negatives(sensitivities, p_available):
    """

    :param sensitivities:
    :param p_available:
    :return:
    """
    assert len(sensitivities) == len(p_available)
    n = len(sensitivities)
    idx = np.empty(n, nb.int32)
    k = 0
    for i in range(n):
        if sensitivities[i] < 0 and p_available[i] > 0:
            idx[k] = i
            k += 1

    if k < n:
        idx = idx[:k]

    return idx


@nb.njit(cache=True)
def get_valid_positives(sensitivities, p_available):
    """

    :param sensitivities:
    :param p_available:
    :return:
    """
    assert len(sensitivities) == len(p_available)
    n = len(sensitivities)
    idx = np.empty(n, nb.int32)
    k = 0
    for i in range(n):
        if sensitivities[i] > 0 and p_available[i] > 0:
            idx[k] = i
            k += 1

    if k < n:
        idx = idx[:k]

    return idx


class BusesForSrap:
    """
    Buses information for SRAP over a particular branch
    """

    def __init__(self,
                 branch_idx: int,
                 bus_indices: IntVec,
                 sensitivities: Vec):
        """

        :param branch_idx:
        :param bus_indices:
        :param sensitivities:
        """
        self.branch_idx = branch_idx
        self.bus_indices = bus_indices
        self.sensitivities = sensitivities

    def is_solvable(self, c_flow: float, rating: float, srap_pmax_mw: float,
                    available_power: Vec, top_n: int = 1000) -> Tuple[bool, float]:
        """
        Get the maximum amount of power (MW) to dispatch using SRAP
        :param c_flow: Contingency flow (MW)
        :param rating: Branch rating (MVA)
        :param srap_pmax_mw: SRAP limit in MW
        :param available_power: Array of available power per bus
        :param top_n: maximum number of nodes affecting the oveload
        :return: min(srap_limit, sum(p_available))
        """

        p_available = available_power[self.bus_indices]

        if c_flow > 0:

            # positive flow, ov is positive
            overload = c_flow - rating

            # slice the positive values
            positive_idx = get_valid_positives(self.sensitivities, p_available)

            if len(positive_idx):
                p_available2 = p_available[positive_idx]
                sensitivities2 = self.sensitivities[positive_idx]

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
                solved = False
                max_srap_power = 0.0
        else:

            # negative flow, ov is negative
            overload = c_flow + rating

            # slice the negative values
            negative_idx = get_valid_negatives(self.sensitivities, p_available)

            if len(negative_idx):
                p_available2 = p_available[negative_idx]
                sensitivities2 = self.sensitivities[negative_idx]

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
            else:
                solved = False
                max_srap_power = 0.0

        return solved, max_srap_power


def get_buses_for_srap_list(PTDF: Mat, threshold=1e-3) -> List[BusesForSrap]:
    """
    Generate the structues to compute the SRAP
    :param PTDF: dense PTDF
    :param threshold: Threshold to convert the PTDF to sparse
    :return: List[BusesForSrap]
    """
    # columns: number of branches, rows: number of nodes
    n_br, n_bus = PTDF.shape
    buses_for_srap_list = list()
    for i in range(n_br):  # para cada columna i
        sensitivities, indices = get_sparse_array_numba(PTDF[i, :], threshold=threshold)
        buses_for_srap_list.append(BusesForSrap(branch_idx=i,
                                                bus_indices=indices,
                                                sensitivities=sensitivities))
    return buses_for_srap_list

