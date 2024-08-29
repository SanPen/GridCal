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
from GridCalEngine.Utils.NumericalMethods.sparse_solve import get_linear_solver
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.pf_formulation_template import PfFormulationTemplate
from GridCalEngine.Utils.Sparse.csc2 import mat_to_scipy
from GridCalEngine.basic_structures import Logger, Vec
from GridCalEngine.Utils.NumericalMethods.common import norm

linear_solver = get_linear_solver()


def compute_beta(a: Vec, b: Vec, delta: float):
    """
    compute the beta parameter
    :param a: alpha + hsd
    :param b: hgn
    :param delta: trust region
    :return: beta value
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


def powell_fx(problem: PfFormulationTemplate,
              tol: float = 1e-6,
              max_iter: int = 10,
              trust: float = 1.0,
              verbose: int = 0,
              logger: Logger = Logger()) -> NumericPowerFlowResults:
    """
    Powell's Dog leg algorithm to solve:

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

    delta = trust
    f_error, converged, x, f = problem.update(x, update_controls=False)
    J = mat_to_scipy(problem.Jacobian())
    g = J.T @ f

    iteration = 0
    error_evolution = np.zeros(max_iter + 1)

    # save the error evolution
    error_evolution[iteration] = f_error

    if verbose > 0:
        print(f'It {iteration}, error {f_error}, converged {converged}, x {x}, dx not computed yet')

    if problem.converged:
        return problem.get_solution(elapsed=time.time() - start, iterations=iteration)

    else:

        while not converged and iteration < max_iter:

            # update iteration counter
            iteration += 1

            # compute alpha (3.19)
            g_proy = J @ g
            alpha = (g @ g) / (g_proy @ g_proy)
            hsd = -alpha * g

            if verbose > 0:
                print('-' * 200)
                print(f'Iter: {iteration}')
                print('-' * 200)

            # compute update step
            try:

                # compute update step: J x Δx = Δg
                hgn = linear_solver(J, -f)

            except RuntimeError:
                logger.add_error(f"Powell's system matrix is singular @iter {iteration}:")
                return problem.get_solution(elapsed=time.time() - start, iterations=iteration)

            # compute hdl (3.20)
            hdl, L0_Lhdl = compute_hdl(hgn=hgn, hsd=hsd, g=g, alpha=alpha, delta=delta, f_error=f_error)

            if verbose > 1:
                import pandas as pd
                print("H:\n", pd.DataFrame(J.toarray()).to_string(index=False))
                print("f:\n", f)
                print("dx:\n", hdl)

            tol2 = tol * (norm(x) + tol)

            f_error_new, converged, x, f = problem.update(x + hdl, update_controls=True)

            rho = (f_error - f_error_new) / L0_Lhdl if L0_Lhdl > 0 else -1.0

            if rho > 0.0 or len(f) != J.shape[0]:
                J = mat_to_scipy(problem.Jacobian())  # compute the Jacobian too
                g = J.T @ f
                f_error = f_error_new

            elif rho > 0.75:
                delta = max(delta, 3.0 * norm(hdl))

            elif rho < 0.25:
                delta *= 0.5

            else:
                raise Exception(f'Unhandled rho {rho}')

            # save the error evolution
            error_evolution[iteration] = f_error

            if verbose > 0:
                if verbose == 1:
                    print(f'It {iteration}, error {f_error}, converged {converged}, x {x}, dx {hdl}')
                else:
                    print(f'error {f_error}, converged {converged}, x {x}, dx {hdl}')

    return problem.get_solution(elapsed=time.time() - start, iterations=iteration)
