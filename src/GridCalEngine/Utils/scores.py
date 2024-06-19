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
from typing import Union
from GridCalEngine.basic_structures import Vec, CxVec, CxMat


@nb.njit(cache=True)
def get_overload_score(loading: Union[CxMat, CxVec], branches_cost: Vec, threshold=1.0) -> float:
    """
    Compute overload score by multiplying the loadings above 100% by the associated branch cost.
    :param loading: load results
    :param branches_cost: all branch elements from studied grid
    :param threshold: threshold for overload
    :return: sum of all costs associated to branch overloads
    """
    cost_ = float(0.0)

    if loading.ndim == 1:
        for i in range(loading.shape[0]):
            absloading = np.abs(loading[i])
            if absloading > threshold:
                cost_ += (absloading - threshold) * float(branches_cost[i])

    elif loading.ndim == 2:

        for i in range(loading.shape[0]):
            for j in range(loading.shape[1]):
                absloading = np.abs(loading[i, j])
                if absloading > threshold:
                    cost_ += (absloading - threshold) * branches_cost[j]

    return cost_


@nb.njit(cache=True)
def get_voltage_module_score(voltage: Union[CxVec, CxMat], vm_cost: Vec, vm_max: Vec, vm_min: Vec) -> float:
    """
    Compute voltage module score by multiplying the voltages outside limits by the associated bus costs.
    :param voltage: voltage results
    :param vm_cost: Vm cost array
    :param vm_max: maximum voltage
    :param vm_min: minimum voltage
    :return: sum of all costs associated to voltage module deviation
    """
    cost_ = 0.0

    if voltage.ndim == 1:
        for i in range(voltage.shape[0]):
            vm = np.abs(voltage[i])
            if vm < vm_min[i]:
                cost_ += vm_cost[i] * (vm_min[i] - vm)
            elif vm > vm_max[i]:
                cost_ += vm_cost[i] * (vm - vm_max[i])
    elif voltage.ndim == 2:
        for i in range(voltage.shape[0]):
            for j in range(voltage.shape[1]):
                vm = np.abs(voltage[i, j])
                if vm < vm_min[j]:
                    cost_ += vm_cost[j] * (vm_min[j] - vm)
                elif vm > vm_max[j]:
                    cost_ += vm_cost[j] * (vm - vm_max[j])

    return cost_


@nb.njit(cache=True)
def get_voltage_phase_score(voltage: Union[CxMat, CxVec], va_cost: Vec, va_max: Vec, va_min: Vec) -> float:
    """
    Compute voltage phase score by multiplying the phases outside limits by the associated bus costs.
    :param voltage: voltage results
    :param va_cost: array of bus angles costs
    :param va_max: maximum voltage angles
    :param va_min: minimum voltage angles
    :return: sum of all costs associated to voltage module deviation
    """
    cost_ = 0.0

    if voltage.ndim == 1:
        for i in range(voltage.shape[0]):
            va = np.angle(voltage[i])
            if va < va_min[i]:
                cost_ += va_cost[i] * (va_min[i] - va)
            elif va > va_max[i]:
                cost_ += va_cost[i] * (va - va_max[i])

    elif voltage.ndim == 2:
        for i in range(voltage.shape[0]):
            for j in range(voltage.shape[1]):
                va = np.angle(voltage[i, j])
                if va < va_min[j]:
                    cost_ += va_cost[j] * (va_min[j] - va)
                elif va > va_max[j]:
                    cost_ += va_cost[j] * (va - va_max[j])

    return cost_