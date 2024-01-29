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
import time
import numpy as np
from typing import Callable, Any
from GridCalEngine.basic_structures import Vec
from GridCalEngine.Utils.NumericalMethods.sparse_solve import get_linear_solver
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Utils.NumericalMethods.common import (ConvexMethodResult, ConvexFunctionResult, norm, max_abs,
                                                         check_function_and_args)

linear_solver = get_linear_solver()


def compute_beta(a: Vec, b: Vec, delta):
    """
    compute the beta parameter
    :param a: alpha + hsd
    :param b: hgn
    :param delta:
    :return:
    """
    ba = b - a
    c = a @ ba
    norm2_a = a @ a
    norm2_ba = ba @ ba
    delta2_norm2a = (delta * delta - norm2_a)
    if c <= 0.0:
        return (-c + np.sqrt(c * c + norm2_ba * delta2_norm2a)) / norm2_ba
    else:
        return delta2_norm2a / (c + np.sqrt(c * c + norm2_ba * delta2_norm2a))


def compute_hdl(hgn: Vec, hsd: Vec, g: Vec, alpha: float, delta: float, f_error: float) -> Vec:
    """
    Compute the Hdl vector
    :param hgn: Hgn vector
    :param hsd: Hsd vector
    :param g: g vector
    :param alpha: alpha parameter
    :param delta: delta parameter (trust region size)
    :param f_error: error of the function top optimize
    :return: Hdl Vector, L(0) - L(hdl)
    """
    if norm(hgn) <= delta:
        return hgn, f_error
    elif norm(hsd * alpha) >= delta:
        hdl = (delta / norm(hsd)) * hsd
        val = (delta * (2 * norm(alpha * g) - delta)) / (2 * alpha)
        return hdl, val
    else:
        beta = compute_beta(a=hsd * alpha, b=hgn, delta=delta)
        hdl = alpha * hsd + beta * (hgn - alpha * hsd)
        val = 0.5 * alpha * (1.0 - beta) ** 2 + (g @ g) + beta * (2.0 - beta) * f_error
        return hdl, val


def powell_dog_leg(func: Callable[[Vec, bool, Any], ConvexFunctionResult],
                   func_args: Any,
                   x0: Vec,
                   tol: float = 1e-6,
                   max_iter: int = 10,
                   trust_region_radius: float = 10.0,
                   verbose: int = 0,
                   logger: Logger = Logger()) -> ConvexMethodResult:
    """
    Powell's Dog leg algorithm to solve:

        min: error(f(x))
        s.t.
            f(x) = 0

    From METHODS FOR NON-LINEAR LEAST SQUARES PROBLEMS by K. Madsen, H.B. Nielsen, O. Tingleff

    :param func: function to optimize, it may or may not include the Jacobian matrix
                the function must have x: Vec and calc_jacobian: bool as the first arguments
                the function must return an instance of ConvexFunctionResult that contains
                the function vector and optionally the derivative when calc_jacobian=True
    :param func_args: Tuple of static arguments to call the evaluation function
    :param x0: Array of initial solutions
    :param tol: Error tolerance
    :param max_iter: Maximum number of iterations
    :param trust_region_radius: radius of the trust region (i.e. 1.0)
    :param verbose:  Display console information
    :param logger: Logger instance
    :return: ConvexMethodResult
    """
    start = time.time()

    if not check_function_and_args(func, func_args, 2):
        raise Exception(f'Invalid function arguments, required {", ".join(func.__code__.co_varnames)}')

    # evaluation of the initial point
    x = x0.copy()
    delta = trust_region_radius
    ret = func(x, True, *func_args)  # compute the Jacobian too
    g = ret.J.T @ ret.f
    f_error = max_abs(ret.f)
    converged = f_error < tol

    iteration = 0
    error_evolution = np.zeros(max_iter + 1)

    # save the error evolution
    error_evolution[iteration] = f_error

    while not converged and iteration < max_iter:

        # compute alpha (3.19)
        g_proy = ret.J @ g
        alpha = (g @ g) / (g_proy @ g_proy)
        hsd = -alpha * g

        # compute update step
        try:

            # compute update step: J x Δx = Δg
            hgn = linear_solver(ret.J, -ret.f)

            if np.isnan(hgn).any():
                logger.add_error(f"Powell's Jacobian is singular @iter {iteration}:")
                return ConvexMethodResult(x=x,
                                          error=f_error,
                                          converged=converged,
                                          iterations=iteration,
                                          elapsed=time.time() - start,
                                          error_evolution=error_evolution)
        except RuntimeError:
            logger.add_error(f"Powell's Jacobian is singular @iter {iteration}:")
            return ConvexMethodResult(x=x,
                                      error=f_error,
                                      converged=converged,
                                      iterations=iteration,
                                      elapsed=time.time() - start,
                                      error_evolution=error_evolution)

        # compute hdl (3.20)
        hdl, L0_Lhdl = compute_hdl(hgn=hgn, hsd=hsd, g=g, alpha=alpha, delta=delta, f_error=f_error)

        tol2 = tol * (norm(x) + tol)

        if norm(hdl) <= tol2:
            converged = True
        else:
            x_new = x + hdl

            ret_new = func(x_new, False, *func_args)  # only f_new
            f_error_new = max_abs(ret_new.f)

            if L0_Lhdl > 0:
                rho = (f_error - f_error_new) / L0_Lhdl
            else:
                rho = -1.0

            if rho > 0.0:
                x = x_new
                ret = func(x, True, *func_args)  # compute the Jacobian too
                g = ret.J.T @ ret.f
                f_error = max_abs(ret.f)
                converged = f_error < tol

            elif rho > 0.75:
                delta = max(delta, 3.0 * norm(hdl))

            elif rho < 0.25:
                delta *= 0.5

            else:
                raise Exception(f'Unhandled rho {rho}')

        if verbose > 0:
            print(f'It {iteration}, error {f_error}, converged {converged}, x {x}')

        # save the error evolution
        error_evolution[iteration] = f_error

        iteration += 1

    return ConvexMethodResult(x=x,
                              error=f_error,
                              converged=converged,
                              iterations=iteration,
                              elapsed=time.time() - start,
                              error_evolution=error_evolution)
