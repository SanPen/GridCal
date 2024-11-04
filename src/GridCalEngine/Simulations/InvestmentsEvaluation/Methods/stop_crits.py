# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
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
