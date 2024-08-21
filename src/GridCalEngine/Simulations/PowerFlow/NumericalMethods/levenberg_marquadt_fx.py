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
import scipy.sparse as sp
from GridCalEngine.Utils.NumericalMethods.sparse_solve import get_linear_solver
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.pf_formulation_template import PfFormulationTemplate
from GridCalEngine.Utils.Sparse.csc2 import mat_to_scipy
from GridCalEngine.basic_structures import Logger

linear_solver = get_linear_solver()


def levenberg_marquadt_fx(problem: PfFormulationTemplate,
                          tol: float = 1e-6,
                          max_iter: int = 10,
                          trust: float = 1.0,
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

    normF = 100000
    update_jacobian = True
    converged = False
    iter_ = 0
    nu = 2.0
    lbmda = 0
    f_prev = 1e9  # very large number
    # csc_matrix identity
    H: sp.csc_matrix = sp.csc_matrix((0, 0))
    Ht: sp.csc_matrix = sp.csc_matrix((0, 0))
    A: sp.csc_matrix = sp.csc_matrix((0, 0))
    error_evolution = np.zeros(max_iter + 1)

    error, converged, x, dz = problem.update(x, update_controls=False)

    # save the error evolution
    error_evolution[iter_] = problem.error

    if verbose > 0:
        print(f'It {iter_}, error {problem.error}, converged {problem.converged}, x {x}, dx not computed yet')

    if problem.converged:
        return problem.get_solution(elapsed=time.time() - start, iterations=iter_)

    else:

        while not converged and iter_ < max_iter:

            # update iteration counter
            iter_ += 1

            if verbose > 0:
                print('-' * 200)
                print(f'Iter: {iter_}')
                print('-' * 200)

            if update_jacobian:
                H = mat_to_scipy(problem.Jacobian())
                # system matrix
                # H1 = H^t
                Ht = H.T  # .tocsr()

                # H2 = H1·H
                HtH = Ht @ H

                # set first value of lmbda
                if iter_ == 0:
                    lbmda = 1e-3 * HtH.diagonal().max()

                # compute system matrix A = H^T·H - lambda·I
                Idn = sp.diags(np.ones(H.shape[0]))
                A = (HtH + lbmda * Idn).tocsc()

            # right-hand side
            # H^t·dz
            rhs = Ht @ dz

            # compute update step
            try:

                # Solve the increment
                dx = linear_solver(A, rhs)

            except RuntimeError:
                logger.add_error(f"Levenberg-Marquardt's system matrix is singular @iter {iter_}:")
                return problem.get_solution(elapsed=time.time() - start, iterations=iter_)

            if verbose > 1:
                import pandas as pd
                print("H:\n", pd.DataFrame(H.toarray()).to_string(index=False))
                print("g:\n", rhs)
                print("h:\n", dx)

            # objective function to minimize
            f = 0.5 * dz @ dz

            # decision function
            dL = 0.5 * dx @ (lbmda * dx + rhs)
            dF = f_prev - f
            if (dL > 0.0) and (dF > 0.0):
                update_jacobian = True
                rho = dF / dL
                lbmda *= max([1.0 / 3.0, 1 - (2 * rho - 1) ** 3])
                nu = 2.0

                # update x
                x -= dx
                error, converged, x, dz = problem.update(x, update_controls=True)

            else:
                update_jacobian = False
                lbmda *= nu
                nu *= 2.0

            # save the error evolution
            error_evolution[iter_] = error

            if verbose > 0:
                if verbose == 1:
                    print(f'It {iter_}, error {error}, converged {converged}, x {x}, dx {dx}')
                else:
                    print(f'error {error}, converged {converged}, x {x}, dx {dx}')

    return problem.get_solution(elapsed=time.time() - start, iterations=iter_)
