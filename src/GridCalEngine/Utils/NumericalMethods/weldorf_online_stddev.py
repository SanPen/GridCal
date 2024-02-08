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
from GridCalEngine.basic_structures import Mat, Vec


@nb.njit(cache=True)
def update(i: int, new_value: Vec, count: Mat, mean: Mat, M2: Mat):
    """

    :param i:
    :param new_value:
    :param count:
    :param mean:
    :param M2:
    """
    for j in range(count.shape[1]):

        if new_value[j] > 0:
            count[i, j] += 1

            delta = new_value[j] - mean[i, j]

            # only update those values with count > 0
            mean[i, j] += delta / count[i, j]

            delta2 = new_value[j] - mean[i, j]
            M2[i, j] += delta * delta2


@nb.njit(cache=True)
def finalize(count: Mat, variance: Mat, M2: Mat, std_dev: Mat, sample_variance: Mat):
    """

    :param count:
    :param variance:
    :param M2:
    :param std_dev:
    :param sample_variance:
    :return:
    """
    for i in range(count.shape[0]):
        for j in range(count.shape[1]):
            if count[i, j] > 0:
                variance[i, j] = M2[i, j] / count[i, j]
                std_dev[i, j] = np.sqrt(variance[i, j])

            if count[i, j] > 1:
                sample_variance[i, j] = M2[i, j] / (count[i, j] - 1)


class WeldorfOnlineStdDevMat:
    """
    Weldorf's algorithm for online computation of the variance
    """

    def __init__(self, nrow: int, ncol: int) -> None:
        """
        Constructor
        :param nrow:
        :param ncol:
        """
        # changed every iteration
        self.count = np.zeros((nrow, ncol), dtype=int)
        self.mean = np.zeros((nrow, ncol), dtype=float)
        self.M2 = np.zeros((nrow, ncol), dtype=float)

        self.steps = 0

        # changed on finalize
        self.variance = np.zeros((nrow, ncol), dtype=float)
        self.sample_variance = np.zeros((nrow, ncol), dtype=float)
        self.std_dev = np.zeros((nrow, ncol), dtype=float)

    def update(self, t: int, new_value: Vec):
        """
        For a new value new_value, compute the new count, new mean, the new M2.
        mean accumulates the mean of the entire dataset
        M2 aggregates the squared distance from the mean
        count aggregates the number of samples seen so far
        :param t: Row index
        :param new_value: array of column values
        """
        self.steps += 1

        update(i=t,
               new_value=new_value,
               count=self.count,
               mean=self.mean,
               M2=self.M2)

    def finalize(self) -> None:
        """
        Finalize: compute the variance and std dev
        """
        if self.steps < 2:
            return
        else:

            finalize(count=self.count,
                     variance=self.variance,
                     M2=self.M2,
                     std_dev=self.std_dev,
                     sample_variance=self.sample_variance)
