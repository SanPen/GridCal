# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import time
import numpy as np
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_formulation_template import PfFormulationTemplate
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
    error0 = error
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

            # line search
            mu = trust0
            update_controls = error < (tol * 100)
            x_sol = x
            while not converged and mu > tol and error >= error0:
                error, x_sol = problem.check_error(x + dx * mu)
                mu *= 0.25

            error, converged, x, f = problem.update(x=x_sol, update_controls=update_controls)

            # save the error evolution
            error0 = error
            error_evolution[iteration] = error

            if verbose > 0:
                if verbose == 1:
                    print(f'It {iteration}, error {error}, converged {converged}, x {x}, dx {dx}')
                else:
                    print(f'error {error}, converged {converged}, x {x}, dx {dx}')

    return problem.get_solution(elapsed=time.time() - start, iterations=iteration)
