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
from typing import Callable, List, Tuple
import numpy as np
import numba as nb
from matplotlib import pyplot as plt
from GridCalEngine.basic_structures import Vec, CscMat


def check_function_and_args(func: Callable, args: Tuple, n_used_for_solver: int) -> bool:
    """
    Checks if the number of supplied arguments matches the function signature
    :param func: Function pointer
    :param args: tuple of arguments to be passed before the mandatory arguments used by the numerical method
    :param n_used_for_solver: Number of mandatory arguments used by the numerical method
    :return: ok?
    """
    n_args = func.__code__.co_argcount

    return n_args == n_used_for_solver + len(args)


@nb.njit(cache=True)
def max_abs(x: Vec) -> float:
    """
    Compute max abs efficiently
    :param x:
    :return:
    """
    max_val = 0.0
    for x_val in x:
        x_abs = abs(x_val)
        if x_abs > max_val:
            max_val = x_abs

    return max_val


@nb.njit(cache=True)
def norm(x: Vec) -> float:
    """
    Compute max abs efficiently
    :param x:
    :return:
    """
    x_sum = 0.0
    for x_val in x:
        x_sum += x_val * x_val

    return np.sqrt(x_sum)


def compute_L(h, f, J) -> float:
    """
    1/2 · ||f + J @ h||
    :param h: some vector
    :param f: f vector
    :param J: Jacobian of f
    :return:
    """
    v = f + J @ h
    return 0.5 * (v @ v)


@dataclass
class ConvexFunctionResult:
    """
    Result of the convex function evaluated iterativelly for a given method
    """
    f: Vec      # function increment of the equalities
    J: CscMat  # Jacobian matrix

    def compute_f_error(self):
        """
        Compute the error of the increments g
        :return: max(abs(G))
        """
        return max_abs(self.f)
        # return np.max(np.abs(self.f))


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

    def plot_error(self) -> None:
        """
        Plot the IPS error
        """
        plt.figure()
        plt.plot(self.error_evolution, )
        plt.xlabel("Iterations")
        plt.ylabel("Error")
        plt.yscale('log')
        plt.show()
    
    def print_info(self):
        """
        Print information about the ConvexMethodResult
        :return: 
        """
        print("Iterations:\t", self.iterations)
        print("Converged:\t", self.converged)
        print("Error:\t", self.error)
        print("Elapsed:\t", self.elapsed, 's')
