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
from typing import Callable, Union, Tuple, List, Any
import numpy as np
from scipy.sparse import csc_matrix as csc
from scipy.sparse import lil_matrix
from GridCalEngine.basic_structures import Vec


def unpack(ret: Union[Vec, Tuple[Vec, ...]]) -> Vec:
    """
    Unpack the returning vector depending if ret is the vector or a tuple including the vector
    :param ret: Tuple with the vector or vector directly
    :return: Vector
    """
    if isinstance(ret, tuple):
        f0 = ret[0]
    else:
        f0 = ret
    return f0


def calc_autodiff_jacobian_f_obj(func: Callable[[Vec, ...], float], x: Vec, arg=(), h=1e-5) -> Vec:
    """
    Compute the Jacobian matrix of `func` at `x` using finite differences.
    This considers that the output is a single value, such as is the case of the objective function f
    :param func: objective function accepting `x` and `arg` and returning a float.
    :param x: Point at which to evaluate the Jacobian (numpy array).
    :param arg: Tuple of arguments to call func aside from x [func(x, *arg)]
    :param h: Small step for finite difference.
    :return: Jacobian as a vector, because the objective function is a single value.
    """
    nx = len(x)
    f0 = func(x, *arg)

    jac = np.zeros(nx)

    for j in range(nx):
        x_plus_h = np.copy(x)
        x_plus_h[j] += h
        f_plus_h = func(x_plus_h, *arg)
        jac[j] = (f_plus_h - f0) / h

    return jac


def calc_autodiff_jacobian(func: Callable[[Vec, Any], Union[Vec, Tuple[Vec, Any]]], x: Vec, arg=(), h=1e-8) -> csc:
    """
    Compute the Jacobian matrix of `func` at `x` using finite differences.

    :param func: function accepting a vector x and args, and returning either a vector or a
                 tuple where the first argument is a vector and the second.
    :param x: Point at which to evaluate the Jacobian (numpy array).
    :param arg: Tuple of arguments to call func aside from x [func(x, *arg)]
    :param h: Small step for finite difference.
    :return: Jacobian matrix as a CSC matrix.
    """
    nx = len(x)
    f0 = unpack(func(x, *arg))

    n_rows = len(f0)

    jac = lil_matrix((n_rows, nx))

    for j in range(nx):
        x_plus_h = np.copy(x)
        x_plus_h[j] += h
        f_plus_h = unpack(func(x_plus_h, *arg))
        row = (f_plus_h - f0) / h
        for i in range(n_rows):
            if row[i] != 0.0:
                jac[i, j] = row[i]

    return jac.tocsc()


def calc_autodiff_hessian_f_obj(func: Callable[[Vec, Any], float], x: Vec, arg=(), h=1e-5) -> csc:
    """
    Compute the Hessian matrix of `func` at `x` using finite differences.
    This considers that the output is a single value, such as is the case of the objective function f

    :param func: objective function accepting `x` and `arg` and returning a float.
    :param x: Point at which to evaluate the Hessian (numpy array).
    :param arg: Tuple of arguments to call func aside from x [func(x, *arg)]
    :param h: Small step for finite difference.
    :return: Hessian matrix as a CSC matrix.
    """
    n = len(x)
    hessian = lil_matrix((n, n))
    for i in range(n):
        for j in range(n):
            x_ijp = np.copy(x)
            x_ijp[i] += h
            x_ijp[j] += h
            f_ijp = func(x_ijp, *arg)

            x_ijm = np.copy(x)
            x_ijm[i] += h
            x_ijm[j] -= h
            f_ijm = func(x_ijm, *arg)

            x_jim = np.copy(x)
            x_jim[i] -= h
            x_jim[j] += h
            f_jim = func(x_jim, *arg)

            x_jjm = np.copy(x)
            x_jjm[i] -= h
            x_jjm[j] -= h
            f_jjm = func(x_jjm, *arg)

            a = (f_ijp - f_ijm - f_jim + f_jjm) / (4 * np.power(h, 2))

            if a != 0.0:
                hessian[i, j] = a

    return hessian.tocsc()


def calc_autodiff_hessian(func: Callable[[Vec, Any], Union[Vec, Tuple[Vec, Any]]],
                          x: Vec, mult: Vec, arg=(), h=1e-5) -> csc:
    """
    Compute the Hessian matrix of `func` at `x` using finite differences.

    :param func: function accepting a vector x and args, and returning either a vector or a
                 tuple where the first argument is a vector and the second.
    :param x: Point at which to evaluate the Hessian (numpy array).
    :param mult: Array of multipliers associated with the functions. The objective function passes value 1 (no action)
    :param arg: Tuple of arguments to call func aside from x [func(x, *arg)]
    :param h: Small step for finite difference.
    :return: Hessian matrix as a CSC matrix.
    """

    n = len(x)
    const = len(unpack(func(x, *arg)))  # For objective function, it will be passed as 1. The MULT will be 1 aswell.
    hessians = lil_matrix((n, n))

    for eq in range(const):
        hessian = lil_matrix((n, n))
        for i in range(n):
            for j in range(n):
                x_ijp = np.copy(x)
                x_ijp[i] += h
                x_ijp[j] += h
                f_ijp = unpack(func(x_ijp, *arg))[eq]

                x_ijm = np.copy(x)
                x_ijm[i] += h
                x_ijm[j] -= h
                f_ijm = unpack(func(x_ijm, *arg))[eq]

                x_jim = np.copy(x)
                x_jim[i] -= h
                x_jim[j] += h
                f_jim = unpack(func(x_jim, *arg))[eq]

                x_jjm = np.copy(x)
                x_jjm[i] -= h
                x_jjm[j] -= h
                f_jjm = unpack(func(x_jjm, *arg))[eq]

                a = mult[eq] * (f_ijp - f_ijm - f_jim + f_jjm) / (4 * np.power(h, 2))

                if a != 0.0:
                    hessian[i, j] = a

        hessians += hessian

    return hessians.tocsc()
