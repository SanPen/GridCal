# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
import time
import numpy as np
import scipy.sparse as sp
from GridCalEngine.Utils.NumericalMethods.sparse_solve import get_linear_solver
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_formulation_template import PfFormulationTemplate
from GridCalEngine.Utils.Sparse.csc2 import mat_to_scipy
from GridCalEngine.basic_structures import Logger

linear_solver = get_linear_solver()


def levenberg_marquardt_fx(problem: PfFormulationTemplate,
                           tol: float = 1e-6,
                           max_iter: int = 10,
                           verbose: int = 0,
                           logger: Logger = Logger()) -> NumericPowerFlowResults:
    """
    Levenberg-Marquardt to solve:

        min: error(f(x))
        s.t.
            f(x) = 0

    From METHODS FOR NON-LINEAR LEAST SQUARES PROBLEMS by K. Madsen, H.B. Nielsen, O. Tingleff

    :param problem: PfFormulationTemplate
    :param tol: Error tolerance
    :param max_iter: Maximum number of iterations
    :param verbose:  Display console information
    :param logger: Logger instance
    :return: ConvexMethodResult
    """
    start = time.time()

    # get the initial point
    x = problem.var2x()

    if len(x) == 0:
        # if the length of x is zero, means that there's nothing to solve
        # for instance there might be a single node that is a slack node
        return problem.get_solution(elapsed=time.time() - start, iterations=0)

    iter_ = 0

    # initialize the problem state
    error, converged, x, f = problem.update(x, update_controls=False)

    # save the error evolution
    error_evolution = np.zeros(max_iter + 1)
    error_evolution[iter_] = problem.error

    if verbose > 0:
        print(f'It {iter_}, error {problem.error}, converged {problem.converged}, x {x}, dx not computed yet')

    if converged:
        return problem.get_solution(elapsed=time.time() - start, iterations=iter_)

    else:

        nu = 2.0
        obj_val_prev = 1e9  # very large number

        J = mat_to_scipy(problem.Jacobian())

        if J.shape[0] != J.shape[1]:
            logger.add_error("Jacobian not square, check the controls!", "Levenberg-Marquadt")
            return problem.get_solution(elapsed=time.time() - start, iterations=iter_)

        elif J.shape[0] != len(f):
            logger.add_error("Jacobian and residuals have different sizes!", "Levenberg-Marquadt",
                             value=len(f), expected_value=J.shape[0])
            return problem.get_solution(elapsed=time.time() - start, iterations=iter_)

        # system matrix
        # H1 = H^t
        Jt = J.T

        # H2 = H1·H
        A = Jt @ J

        # set first value of mu
        mu = 1e-3 * A.diagonal().max()

        # compute system matrix A = H^T·H - lambda·I
        Idn = sp.diags(np.full(J.shape[0], mu))
        sys_mat = (A + Idn).tocsc()

        # right-hand side
        # H^t·dz
        g = Jt @ f

        # objective function to minimize
        obj_val = 0.5 * f @ f

        while not converged and iter_ < max_iter:

            # update iteration counter
            iter_ += 1

            if verbose > 0:
                print('-' * 200)
                print(f'Iter: {iter_}')
                print('-' * 200)

            try:

                # Solve the increment
                dx = linear_solver(sys_mat, g)

            except RuntimeError:
                logger.add_error(f"Levenberg-Marquardt's system matrix is singular @iter {iter_}:")
                return problem.get_solution(elapsed=time.time() - start, iterations=iter_)

            if verbose > 1:
                print("H:\n", problem.get_jacobian_df(J))
                print("F:\n", problem.get_f_df(g))
                print("dx:\n", problem.get_x_df(dx))

            # decision function
            dF = obj_val_prev - obj_val
            dL = 0.5 * dx @ (mu * dx + g)

            if (dF != 0.0) and (dL > 0.0):
                rho = dF / dL
                mu *= max([1.0 / 3.0, 1.0 - (2 * rho - 1) ** 3.0])
                nu = 2.0

                # update
                update_controls = error < (tol * 100)
                error, converged, x, f = problem.update(x - dx, update_controls=update_controls)

                # record the previous objective function value
                obj_val_prev = obj_val

                # objective function to minimize
                obj_val = 0.5 * f @ f

                # update Jacobian and system matrix
                J = mat_to_scipy(problem.Jacobian())

                if J.shape[0] != J.shape[1]:
                    logger.add_error("Jacobian not square, check the controls!", "Levenberg-Marquadt")
                    return problem.get_solution(elapsed=time.time() - start, iterations=iter_)

                elif J.shape[0] != len(f):
                    logger.add_error("Jacobian and residuals have different sizes!", "Levenberg-Marquadt",
                                     value=len(f), expected_value=J.shape[0])
                    return problem.get_solution(elapsed=time.time() - start, iterations=iter_)

                # system matrix
                # H1 = H^t
                Jt = J.T

                # H2 = H1·H
                A = Jt @ J

                # compute system matrix sys_mat = A + mu·I
                Idn = sp.diags(np.full(J.shape[0], mu))
                sys_mat = (A + Idn).tocsc()

                # update right-hand side
                g = Jt @ f

            else:
                mu *= nu
                nu *= 2.0

            # save the error evolution
            error_evolution[iter_] = error

            if verbose > 0:
                if verbose == 1:
                    print(f'It {iter_}, error {error}, converged {converged}, x {x}, dx {dx}')
                else:
                    print(f'error {error}, converged {converged}, x {x}, dx {dx}')

    return problem.get_solution(elapsed=time.time() - start, iterations=iter_)

