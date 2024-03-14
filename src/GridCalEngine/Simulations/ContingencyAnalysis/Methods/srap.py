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
from typing import Tuple
from GridCalEngine.basic_structures import Vec, IntVec, Mat


@nb.njit(cache=True)
def get_valid_negatives(sensitivities: Vec, p_available: Vec):
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
        # if sensitivities[i] < 0 and p_available[i] > 0:
        if sensitivities[i] < 0 < p_available[i]:
            idx[k] = i
            k += 1

    if k < n:
        idx = idx[:k]

    return idx


@nb.njit(cache=True)
def get_valid_positives(sensitivities: Vec, p_available: Vec):
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


@nb.njit(cache=True)
def vector_sum_used_power_srap(p_available3: Vec, sensitivities3: Vec, max_srap_power: float):
    """

    :param p_available3:
    :param sensitivities3:
    :param max_srap_power:
    :return:
    """
    # inicializar la suma parcial
    suma = 0.0
    max_srap_power = np.abs(max_srap_power)
    sensitivities3 = np.abs(sensitivities3)

    p_used = np.zeros(len(p_available3))

    # recorrer los elementos de p_available3
    for i in range(len(p_available3)):

        if suma + p_available3[i] * sensitivities3[i] <= max_srap_power:
            suma += p_available3[i] * sensitivities3[i]
            p_used[i] = p_available3[i]

        else:
            p_used[i] = (max_srap_power - suma) / sensitivities3[i]
            suma += p_used[i] * sensitivities3[i]

            return p_used

    return p_used


@nb.njit(cache=True)
def vector_sum_srap(p_available3: Vec, sensitivities3: Vec, srap_pmax_mw: float):
    """

    :param p_available3:
    :param sensitivities3:
    :param srap_pmax_mw:
    :return:
    """
    # inicializar la suma parcial
    suma = 0.0
    max_srap_power = 0.0
    # p_used = np.zeros(len(p_available3))

    # recorrer los elementos de p_available3
    for i in range(len(p_available3)):

        # si la suma más el elemento actual es menor o igual que srap_pmax_mw
        if suma + p_available3[i] <= srap_pmax_mw:
            # asignar el elemento a b
            # p_available_red[i] = p_available3[i]
            max_srap_power += p_available3[i] * sensitivities3[i]
            # p_used[i] = p_available3[i]
            # actualizar la suma
            suma += p_available3[i]

        # si la suma más el elemento actual es mayor que srap_pmax_mw
        else:
            # asignar la diferencia entre srap_pmax_mw y la suma
            # p_available_red[i] = srap_pmax_mw - suma
            max_srap_power += (srap_pmax_mw - suma) * sensitivities3[i]
            # p_used[i] = srap_pmax_mw - suma
            # p_used_unit = p_used/p_available3
            # salir del bucle
            # break
            # return max_srap_power, p_used
            return max_srap_power

    # max_srap_power = np.sum(p_available_red * sensitivities3)
    # p_used_unit = p_used / p_available3

    # return max_srap_power, p_used
    return max_srap_power


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

    def is_solvable(self,
                    c_flow: float,
                    rating: float,
                    srap_pmax_mw: float,
                    available_power: Vec,
                    srap_used_power: Mat,
                    branch_idx: int,
                    top_n: int = 1000) -> Tuple[bool, float]:

        """
        Get the maximum amount of power (MW) to dispatch using SRAP
        :param c_flow: Contingency flow (MW)
        :param rating: Branch rating (MVA)
        :param srap_pmax_mw: SRAP limit in MW
        :param available_power: Array of available power per bus
        :param srap_used_power: Matrix including power used in SRAP (nbranch,nbus)
        :param branch_idx: overloaded branch
        :param top_n: maximum number of nodes affecting the oveload
        :return: min(srap_limit, sum(p_available))
        """

        p_available = available_power[self.bus_indices]
        srap_gen_used = self.bus_indices

        if c_flow > 0:

            # positive flow, ov is positive
            overload = c_flow - rating

            # slice the positive values
            positive_idx = get_valid_positives(self.sensitivities, p_available)

            if len(positive_idx):
                p_available2 = p_available[positive_idx]
                sensitivities2 = self.sensitivities[positive_idx]
                srap_gen_used2 = srap_gen_used[positive_idx]

                # sort greater to lower, more positive first
                idx = np.argsort(-sensitivities2)
                idx2 = idx[:top_n]
                p_available3 = p_available2[idx2]
                sensitivities3 = sensitivities2[idx2]
                srap_gen_used3 = srap_gen_used2[idx2]

                # interpolate the srap limit, to get the maximum srap power
                max_srap_power = vector_sum_srap(p_available3, sensitivities3, srap_pmax_mw)

                # if the max srap power is less than the overload we cannot solve
                solved = max_srap_power >= overload

                if solved:
                    max_srap_power = c_flow - rating
                    p_used = vector_sum_used_power_srap(p_available3, sensitivities3, max_srap_power)
                    srap_used_power[branch_idx, srap_gen_used3] += p_used

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
                srap_gen_used2 = srap_gen_used[negative_idx]

                # sort lower to greater, more negative first
                idx = np.argsort(sensitivities2)
                idx2 = idx[:top_n]
                p_available3 = p_available2[idx2]
                sensitivities3 = sensitivities2[idx2]
                srap_gen_used3 = srap_gen_used2[idx2]

                # interpolate the srap limit, to get the minimum srap power
                max_srap_power = vector_sum_srap(p_available3, sensitivities3, srap_pmax_mw)

                # if the value is grater than the overload we cannot solve
                solved = max_srap_power <= overload

                if solved:
                    max_srap_power = c_flow + rating
                    p_used = vector_sum_used_power_srap(p_available3, sensitivities3, max_srap_power)
                    srap_used_power[branch_idx, srap_gen_used3] += p_used

            else:
                solved = False
                max_srap_power = 0.0

        return solved, max_srap_power
