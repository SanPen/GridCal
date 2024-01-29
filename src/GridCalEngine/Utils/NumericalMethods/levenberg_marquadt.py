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
import math
from typing import Callable, Any
from GridCalEngine.basic_structures import Vec
from GridCalEngine.Utils.NumericalMethods.sparse_solve import get_linear_solver
from GridCalEngine.Utils.Sparse.csc import diagc
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Utils.NumericalMethods.common import (ConvexMethodResult, ConvexFunctionResult,
                                                         check_function_and_args)

linear_solver = get_linear_solver()


def levenberg_marquardt(func: Callable[[Vec, bool, Any], ConvexFunctionResult],
                        func_args: Any,
                        x0: Vec,
                        tol: float = 1e-6,
                        max_iter: int = 10,
                        verbose: int = 0,
                        logger: Logger = Logger()) -> ConvexMethodResult:
    """
    Levenberg-Marquardt to solve:

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
    :param verbose:  Display console information
    :param logger: Logger instance
    :return: ConvexMethodResult
    """
    start = time.time()

    if not check_function_and_args(func, func_args, 2):
        raise Exception(f'Invalid function arguments, required {", ".join(func.__code__.co_varnames)}')

    # evaluation of the initial point
    x = x0.copy()
    ret = func(x, True, *func_args)  # compute the Jacobian too
    f_error = 0.5 * (ret.f @ ret.f)
    converged = f_error < tol
    iteration = 0
    nu = 2.0
    one_third = 1.0 / 3.0

    Jt = ret.J.T
    A = Jt @ ret.J
    g = Jt @ ret.f
    Idn = diagc(n=A.shape[0], value=1.0)
    mu = 1e-3 * A.diagonal().max()

    error_evolution = np.zeros(max_iter + 1)

    # save the error evolution
    error_evolution[iteration] = f_error

    if verbose > 0:
        print(f'It {iteration}, error {f_error}, converged {converged}, x {x}, dx not computed yet')

    if converged:
        return ConvexMethodResult(x=x0,
                                  error=f_error,
                                  converged=converged,
                                  iterations=iteration,
                                  elapsed=time.time() - start,
                                  error_evolution=error_evolution)

    else:

        while not converged and iteration < max_iter:

            # compute update step
            try:
                H = (A + (mu * Idn)).tocsc()
                h = linear_solver(H, -g)

                if np.isnan(h).any():
                    logger.add_error(f"Levenberg-Marquardt's sys matrix is singular @iter {iteration}:")
                    return ConvexMethodResult(x=x,
                                              error=f_error,
                                              converged=converged,
                                              iterations=iteration,
                                              elapsed=time.time() - start,
                                              error_evolution=error_evolution)
            except RuntimeError:
                logger.add_error(f"Levenberg-Marquardt's sys matrix is singular @iter {iteration}:")
                return ConvexMethodResult(x=x,
                                          error=f_error,
                                          converged=converged,
                                          iterations=iteration,
                                          elapsed=time.time() - start,
                                          error_evolution=error_evolution)

            x_new = x + h
            h = x_new - x  # numerical correction

            dL = 0.5 * (h @ (mu * h - g))

            ret = func(x_new, False, *func_args)  # only f_new

            f_error_new = 0.5 * (ret.f @ ret.f)
            dF = f_error - f_error_new

            if (dL > 0) and (dF > 0):
                x = x_new
                f_error = f_error_new

                ret = func(x_new, True, *func_args)  # compute f + jacobian
                Jt = ret.J.T
                A = Jt @ ret.J
                g = Jt @ ret.f
                converged = f_error < tol  # or g_error < tol
                rho = dF / dL
                mu *= max(one_third, 1.0 - math.pow(2.0 * rho - 1.0, 3))
                nu = 2.0
            else:
                mu *= nu
                nu *= 2.0

            if verbose > 0:
                print(f'It {iteration}, error {f_error}, converged {converged}, x {x}, dx {h}')

            iteration += 1

            # save the error evolution
            error_evolution[iteration] = f_error

    return ConvexMethodResult(x=x,
                              error=f_error,
                              converged=converged,
                              iterations=iteration,
                              elapsed=time.time() - start,
                              error_evolution=error_evolution)
