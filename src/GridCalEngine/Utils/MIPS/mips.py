# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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

from typing import Callable, Tuple
import numpy as np
from scipy.sparse import csc_matrix as csc
from scipy import sparse
import timeit
from GridCalEngine.Utils.MIPS.ipm_test import brock_eval, NLP_test
from GridCalEngine.basic_structures import Vec, Mat


def solver(x0: Vec,
           NV: int,
           NE: int,
           NI: int,
           f_eval: Callable[[Vec, csc, csc], Tuple[Vec, csc, csc, csc, csc, csc, csc, csc, csc]],
           step_calculator: Callable[[Vec, Vec, int], float],
           gamma0=10,
           max_iter=100,
           verbose: int = 0):
    """
    Solve a non-linear problem of the form:

        min: f(x)
        s.t.
            G(x)  = 0
            H(x) <= 0
            xmin <= x <= xmax

    The problem is specified by a function `f_eval`
    This function is called with (x, lambda, pi) and
    returns (f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx)

    where:
        x: array of variables
        lambda: acceleration factor
        pi: ??
        f: objective function value
        G: Array of equality mismatches
        H: Array of inequality mismatches
        fx: jacobian of f(x)
        Gx: Jacobian of G(x)
        Hx: Jacobian of H(x)
        fxx: Hessian of f(x)
        Gxx: Hessian of G(x)
        Hxx: Hessian of H(x)

    :param x0: Initial solution
    :param NV: Number of variables (size of x)
    :param NE: Number of equality constraints (rows of H)
    :param NI: Number of inequality constraints (rows of G)
    :param f_eval: A function pointer called with (x, lambda, pi) that returns (f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx)
    :param step_calculator:
    :param gamma0:
    :param max_iter:
    :param verbose:
    :return:
    """
    START = timeit.default_timer()

    # Init iteration values
    error = 1000000
    iter_counter = 0
    f = 0.0  # objective function
    x = x0.copy()
    gamma = gamma0

    # Init multiplier values. Defaulted at 1.
    PI = csc(np.ones(NE))
    LAMBDA = csc(np.ones(NI))
    LAMBDA_MAT = sparse.dia_matrix((np.ones(NI), 0), shape=(NI, NI)).tocsc()
    T = csc(np.ones(NI))
    # T_MAT = sparse.dia_matrix((np.ones(NI), 0), shape=(NI, NI)).tocsc()
    inv_T = sparse.dia_matrix((np.ones(NI), 0), shape=(NI, NI)).tocsc()
    E = csc(np.ones(NI)).transpose()

    while error > gamma and iter_counter < max_iter:

        # Evaluate the functions, gradients and hessians at the current iteration.
        f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx = f_eval(x, LAMBDA, PI)

        # Compute the submatrices of the reduced NR method
        M = fxx + Gxx + Hxx + Hx @ inv_T @ LAMBDA_MAT @ Hx.T
        N = fx + Hx @ LAMBDA.T + Hx @ inv_T @ (gamma * E + LAMBDA_MAT @ H) + Gx @ PI.T

        # Stack the submatrices and vectors
        J1 = sparse.hstack([M, Gx])
        J2 = sparse.hstack([Gx.T, csc((NE, NE))])
        J = sparse.vstack([J1, J2]).tocsc()
        r = - sparse.vstack([N, G]).tocsc()

        # Find the reduced problem residuals and split them
        dXP = sparse.linalg.spsolve(J, r)
        dX = dXP[0: NV]
        dXsp = csc(dX).T
        dP = csc(dXP[NV: NE + NV])

        # Calculate the inequalities residuals using the reduced problem residuals
        dT = - H - T.T - Hx.T @ dXsp
        dL = - LAMBDA.T + inv_T @ (gamma * E - LAMBDA_MAT @ dT)

        # Compute the maximum step allowed
        alphap = step_calculator(T.toarray(), dT.T.toarray(), NI)
        alphad = step_calculator(LAMBDA.toarray(), dL.transpose().toarray(), NI)

        # Update the values of the variables and multipliers
        x += dX * alphap
        T += dT.T * alphap
        LAMBDA += dL.T * alphad
        PI += dP * alphad
        # T_MAT = sparse.dia_matrix((T.toarray(), 0), shape=(NI, NI)).tocsc()
        inv_T = sparse.dia_matrix((1.0 / T.toarray(), 0), shape=(NI, NI)).tocsc()
        LAMBDA_MAT = sparse.dia_matrix((LAMBDA.toarray(), 0), shape=(NI, NI)).tocsc()

        # Compute the maximum error and the new gamma value
        error = max(max(abs(dX)), max(abs(dL)), max(abs(dT)), max(abs(dP)))
        newgamma = 0.1 * (T @ LAMBDA.T).toarray()[0][0] / NI
        gamma = max(newgamma, 1e-5)  # Maximum tolerance requested.

        # Add an iteration step
        iter_counter += 1

        if verbose > 0:
            print(x, error, gamma)

    END = timeit.default_timer()

    if verbose > 0:
        print('SOLUTION: ', x, f)
        print('Time elapsed (s): ', END - START)

    return x, error, gamma


def step_calculation(V: Mat, dV: Mat, NI: int):
    """

    :param V:
    :param dV:
    :param NI:
    :return:
    """
    alpha = 1.0

    for i in range(NI):
        if dV[0, i] < 0:
            alpha = min(alpha, -V[0, i] / dV[0, i])

    alpha = min(0.999995 * alpha, 1.0)

    return alpha


def test_solver():
    X = np.array([2., 1., 0.])
    solver(x0=X, NV=3, NE=1, NI=2, f_eval=NLP_test, step_calculator=step_calculation, verbose=1)

    return


if __name__ == '__main__':
    test_solver()
