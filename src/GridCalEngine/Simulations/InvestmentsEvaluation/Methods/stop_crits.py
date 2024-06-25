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
import math
import numpy as np
from scipy import stats


class StopCriterion:
    """
    StopCriterion:
    """

    def add(self, x):
        """
        Updates the criterion result based on a new observation.
        :param x: the observation
        """
        raise NotImplementedError()

    def __bool__(self):
        """
        Returns `True` if the approximation is deemed "good" enough, and
        the iterative method should stop.
        """
        raise NotImplementedError()


# This is a toy criterion and should only be used in tests. Otherwise, prefer
# a simple `for _ in range(iters)` loop.
class MaxItersStopCriterion(StopCriterion):
    def __init__(self, iters):
        """
        A stopping criterion that stops after `max_iters` observations
        have been produced.
        :param iters: the number of iterations to run the method for.
        """
        self.curr = 0
        self.iters = iters

    def add(self, x):
        self.curr += 1

    def __bool__(self):
        return self.curr >= self.iters


class StochStopCriterion(StopCriterion):
    def __init__(self, dist, p=0.95):
        """
        An online algorithm for implementing a stopping criterion that guarantees
        that the sample mean of a random variable X is within `dist` units of the
        expectation of X with probability `p`.
        """
        self.n = 0
        self.mean = 0  # Sample mean
        self.sum_squares = 0  # For n > 1, equal to the quasi-variance times (n - 1)
        self.dist = dist
        self.z = float(stats.norm.ppf((1 + p) / 2))  # two-tailed z-score

    def add(self, x):
        # Numerically stable algorithm due to Welford.
        # https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance#Welford's_online_algorithm
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        self.sum_squares += delta * (x - self.mean)

    def __bool__(self):
        if self.n < 2:
            return False
        var = self.sum_squares / (self.n - 1)  # Quasi-variance
        # if self.n % 50 == 0:
        #     print(f'SAMPLE SIZE = {self.n}; VALUE = {self.z * math.sqrt(var / self.n)}; THRESHOLD = {self.dist}')
        return self.z * math.sqrt(var / self.n) < self.dist


# if __name__ == '__main__':
#     crit = StochStopCriterion(0.01)
#     assert math.isclose(crit.z, 1.96, abs_tol=1e-3)
#
#     for i in range(10):
#         x = 0.12 + np.random.random() * 1e-3
#         crit.add(x)
#     assert bool(crit)  # typically the residual is approx. 1e-4; shouldn't cause spurious fails
