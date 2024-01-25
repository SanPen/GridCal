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
from dataclasses import dataclass
import numpy as np
from matplotlib import pyplot as plt
from GridCalEngine.basic_structures import Vec, CscMat


def compute_g_error(fx) -> float:
    """
    Compute the infinite norm of fx
    this is the same as max(abs(fx))
    :param fx: vector
    :return: infinite norm
    """
    return np.linalg.norm(fx, np.inf)


@dataclass
class ConvexFunctionResult:
    """
    Result of the convex function evaluated iterativelly for a given method
    """
    g: Vec      # function increment of the equalities
    Gx: CscMat  # Jacobian matrix

    @property
    def error(self):
        """
        Compute the error of the increments g
        :return: max(abs(G))
        """
        return compute_g_error(self.g)


@dataclass
class ConvexMethodResult:
    """
    Iterative convex method result
    """
    x: Vec              # x solution
    error: float        # method error
    converged: bool     # converged?
    iterations: int     # number of iterations
    elapsed: float      # time elapsed in seconds
    error_evolution: Vec    # array of errors to plot

    def plot_error(self):
        """
        Plot the IPS error
        """
        plt.figure()
        plt.plot(self.error_evolution, )
        plt.xlabel("Iterations")
        plt.ylabel("Error")
        plt.yscale('log')
        plt.show()


