# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from dataclasses import dataclass
from typing import Callable, Tuple
import numpy as np
import numba as nb
from matplotlib import pyplot as plt
from VeraGridEngine.basic_structures import Vec, CscMat, IntVec, CxVec


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
    f: Vec  # function increment of the equalities
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
    x: Vec  # x solution
    error: float  # method error
    converged: bool  # converged?
    iterations: int  # number of iterations
    elapsed: float  # time elapsed in seconds
    error_evolution: Vec  # array of errors to plot

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


@nb.njit(cache=True)
def find_closest_number(arr: Vec, target: float) -> Tuple[int, float]:
    """
    Find the closest number that exists in array
    :param arr: Array to be searched (must be sorted from min to max)
    :param target: Value to search for
    :return: index in the array, Closes adjusted or truncated value
    """
    if len(arr) == 0:
        # nothing to do
        return -1, target

    prev: float = arr[0]

    if target <= prev:
        return 0, prev

    last: float = arr[-1]
    if target >= last:
        return len(arr) - 1, last

    for i in range(1, len(arr)):
        val: float = arr[i]

        if val <= prev:
            # test that the values strictly increase
            raise Exception("The array must be monotonically increasing")

        if prev < target <= val:
            # the value is within the interval

            d_prev = target - prev
            d_post = val - target

            if abs(d_prev - d_post) < 1e-10:
                return i, val
            else:
                if d_prev < d_post:
                    return i - 1, prev
                else:
                    return i, val

        prev = val

    # if we reached here, something went wrong...
    return 0, arr[0]


@nb.njit(cache=True)
def make_lookup(size: int, indices: IntVec) -> IntVec:
    """
    Create a lookup array
    :param size: Size of the thing (i.e. number of buses)
    :param indices: indices to map (i.e. pq indices)
    :return: lookup array, -1 at the indices that do not match with the "indices" input array
    """
    lookup = np.full(size, -1, dtype=np.int32)
    lookup[indices] = np.arange(len(indices), dtype=np.int32)
    return lookup


@nb.njit(cache=True)
def make_complex(r: Vec, i: Vec) -> CxVec:
    """
    Fastest way to create complex arrays
    :param r:
    :param i:
    :return:
    """
    assert len(r) == len(i)
    res = np.empty(len(r), dtype=np.complex128)
    for k in range(len(r)):
        res[k] = complex(r[k], i[k])
    return res
