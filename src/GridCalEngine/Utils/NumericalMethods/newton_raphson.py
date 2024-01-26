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
from typing import Callable, Any, Tuple
import time
import numpy as np
from GridCalEngine.basic_structures import Vec, CscMat
from GridCalEngine.Utils.NumericalMethods.common import ConvexMethodResult, ConvexFunctionResult, compute_g_error
from GridCalEngine.Utils.NumericalMethods.sparse_solve import get_linear_solver
from GridCalEngine.basic_structures import Logger


linear_solver = get_linear_solver()


def newton_raphson(func: Callable[[Vec, bool, ...], ConvexFunctionResult],
                   func_args: Tuple[Any],
                   x0: Vec,
                   tol: float = 1e-6,
                   max_iter: int = 10,
                   mu0: float = 1.0,
                   acceleration_parameter: float = 0.05,
                   verbose: int = 0,
                   logger: Logger = Logger()) -> ConvexMethodResult:
    """
    Newton-Raphson with Line search to solve:

        min: error(g(x))
        s.t.
            g(x) = 0

    :param func: function to optimize, it may or may not include the Jacobian matrix
    :param func_args: Static arguments to call the evaluation function
    :param x0: Array of initial solutions
    :param tol: Error tolerance
    :param max_iter: Maximum number of iterations
    :param mu0: initial acceleration value
    :param acceleration_parameter: parameter used to correct the "bad" iterations, should be between 1e-3 ~ 0.5
    :param verbose:  Display console information
    :param logger: Logger instance
    :return: ConvexMethodResult
    """
    start = time.time()

    # evaluation of the initial point
    x = x0.copy()
    ret = func(x, True, *func_args)  # compute the Jacobian too
    error = ret.error
    converged = error < tol
    iteration = 0
    error_evolution = np.zeros(max_iter + 1)

    # save the error evolution
    error_evolution[iteration] = error

    if converged:
        return ConvexMethodResult(x=x0,
                                  error=error,
                                  converged=converged,
                                  iterations=iteration,
                                  elapsed=time.time() - start,
                                  error_evolution=error_evolution)

    else:

        while iteration < max_iter and not converged:

            # compute update step
            try:

                # J x Δx = Δg
                dx = linear_solver(ret.Gx, ret.g)

                if np.isnan(dx).any():
                    logger.add_error('NR Singular matrix @iter:'.format(iteration))
                    return ConvexMethodResult(x=x,
                                              error=error,
                                              converged=converged,
                                              iterations=iteration,
                                              elapsed=time.time() - start,
                                              error_evolution=error_evolution)
            except RuntimeError:
                logger.add_error('NR Singular matrix @iter:'.format(iteration))
                return ConvexMethodResult(x=x,
                                          error=error,
                                          converged=converged,
                                          iterations=iteration,
                                          elapsed=time.time() - start,
                                          error_evolution=error_evolution)

            mu = mu0
            back_track_condition = True
            l_iter = 0
            while back_track_condition and l_iter < max_iter and mu > tol:

                x2 = x - mu * dx
                ret2 = func(x2, False, *func_args)  # do not compute the Jacobian
                error2 = compute_g_error(ret2.g)

                # change mu for the next iteration
                mu *= 0.5  # acceleration_parameter

                # keep back-tracking?
                back_track_condition = error2 > error

                if not back_track_condition:
                    # accept the solution
                    x = x2

                l_iter += 1

            if l_iter > 1 and back_track_condition:
                # this means that not even the backtracking was able to correct
                # the solution, so terminate

                return ConvexMethodResult(x=x,
                                          error=error,
                                          converged=converged,
                                          iterations=iteration,
                                          elapsed=time.time() - start,
                                          error_evolution=error_evolution)

            # update equalities increment and the jacobian
            ret = func(x, True, *func_args)

            # compute error
            error = ret.error

            # determine the convergence condition
            converged = error <= tol

            # update iteration counter
            iteration += 1

            # save the error evolution
            error_evolution[iteration] = error

    return ConvexMethodResult(x=x,
                              error=error,
                              converged=converged,
                              iterations=iteration,
                              elapsed=time.time() - start,
                              error_evolution=error_evolution)
