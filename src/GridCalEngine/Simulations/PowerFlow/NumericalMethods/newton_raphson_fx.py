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
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.pf_formulation_template import PfFormulationTemplate
from GridCalEngine.Utils.Sparse.csc2 import CSC, spsolve_csc
from GridCalEngine.basic_structures import Logger


def newton_raphson_fx(problem: PfFormulationTemplate,
                      tol: float = 1e-6,
                      max_iter: int = 10,
                      trust: float = 1.0,
                      verbose: int = 0,
                      logger: Logger = Logger()) -> NumericPowerFlowResults:
    """
    Newton-Raphson with Line search to solve:

        min: error(g(x))
        s.t.
            g(x) = 0

    :param problem: PfFormulationTemplate
    :param tol: Error tolerance
    :param max_iter: Maximum number of iterations
    :param trust: trust amount in the derivative length correctness
    :param verbose:  Display console information
    :param logger: Logger instance
    :return: ConvexMethodResult
    """
    start = time.time()

    # get the initial point
    x = problem.var2x()

    if len(x) == 0:
        # if the lenght of x is zero, means that there's nothing to solve
        # for instance there might be a single node that is a slack node
        return problem.get_solution(elapsed=time.time() - start, iterations=0)

    # set the problem state
    error, converged, _, f = problem.update(x, update_controls=False)

    iteration = 0
    error_evolution = np.zeros(max_iter + 1)
    trust0 = trust if trust <= 1.0 else 1.0  # trust radius in NR should not be greater than 1

    # save the error evolution
    error_evolution[iteration] = problem.error

    if verbose > 0:
        print(f'It {iteration}, error {problem.error}, converged {problem.converged}, x {x}, dx not computed yet')

    if problem.converged:
        return problem.get_solution(elapsed=time.time() - start, iterations=iteration)

    else:

        while not converged and iteration < max_iter:

            # update iteration counter
            iteration += 1

            if verbose > 0:
                print('-' * 200)
                print(f'Iter: {iteration}')
                print('-' * 200)

            # compute update step
            try:

                # compute update step: J x Δx = Δg
                J: CSC = problem.Jacobian()
                dx, ok = spsolve_csc(J, -f)
                # dx, ok = problem.solve_step()

                if verbose > 1:
                    import pandas as pd
                    print("J:\n", pd.DataFrame(J.toarray()).to_string(index=False))
                    print("F:\n", f)
                    print("dx:\n", dx)

                if not ok:
                    logger.add_error(f"Newton-Raphson's Jacobian is singular @iter {iteration}:")
                    print("(newton_raphson_fx.py) Singular Jacobian")
                    return problem.get_solution(elapsed=time.time() - start, iterations=iteration)
            except RuntimeError:
                logger.add_error(f"Newton-Raphson's Jacobian is singular @iter {iteration}:")
                print("(newton_raphson_fx.py) Singular Jacobian")
                return problem.get_solution(elapsed=time.time() - start, iterations=iteration)

            # mu = trust0
            # back_track_condition = True
            # l_iter = 0
            # while back_track_condition and mu > tol:
            #
            #     x2 = x - mu * dx
            #     error2, converged2, _ = problem.update(x2, update_controls=False)
            #
            #     # change mu for the next iteration
            #     mu *= 0.5  # acceleration_parameter
            #
            #     # keep back-tracking?
            #     back_track_condition = error2 > error
            #     l_iter += 1
            #
            #     if not back_track_condition:
            #         # accept the solution
            #         x = x2
            #
            # if back_track_condition:
            #     # this means that not even the backtracking was able to correct
            #     # the solution, so terminate
            #     logger.add_warning(f"Newton-Raphson's stagnated @iter {iteration}:")
            #     return problem.get_solution(elapsed=time.time() - start, iterations=iteration)

            x += dx

            # set the problem state
            error, converged, x, f = problem.update(x, update_controls=True)

            # save the error evolution
            error_evolution[iteration] = error

            if verbose > 0:
                if verbose == 1:
                    print(f'It {iteration}, error {error}, converged {converged}, x {x}, dx {dx}')
                else:
                    print(f'error {error}, converged {converged}, x {x}, dx {dx}')

    return problem.get_solution(elapsed=time.time() - start, iterations=iteration)
