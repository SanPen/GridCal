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
# import collections
#
# collections.Callable = collections.abc.Callable

from typing import Callable, Tuple
import numba as nb
import numpy as np
import pandas as pd
from scipy.sparse import csc_matrix as csc
from scipy import sparse
import timeit
from GridCalEngine.basic_structures import Vec
from GridCalEngine.Utils.Sparse.csc import pack_3_by_4, diags

np.set_printoptions(precision=4)


@nb.njit(cache=True)
def step_calculation(V: Vec, dV: Vec):
    """
    This function calculates for each Lambda multiplier or its associated Slack variable
    the maximum allowed step in order to not violate the KKT condition Lambda > 0 and S > 0
    :param V: Array of multipliers or slack variables
    :param dV: Variation calculated in the Newton step
    :return:
    """
    alpha = 1.0

    for i in range(len(V)):
        if dV[i] < 0:
            alpha = min(alpha, -V[i] / dV[i])

    return min(0.9999995 * alpha, 1.0)


@nb.njit(cache=True)
def split(sol: Vec, n: int):
    """
    Split the solution vector in two
    :param sol: solution vector
    :param n: integer position at whic to split the solution
    :return: A before, B after the splitting point
    """
    return sol[:n], sol[n:]


@nb.njit(cache=True)
def calc_error(dx, dz, dmu, dlmbda):
    """
    Calculate the error of the process
    :param dx: x increments array
    :param dz: z increments array
    :param dmu: mu increments array
    :param dlmbda: lambda increments array
    :return: max abs value of all of the increments
    """
    err = 0.0

    for arr in [dx, dz, dmu, dlmbda]:
        for i in range(len(arr)):
            v = abs(arr[i])
            if v > err:
                err = v

    return err


def solver(x0: Vec,
           n_x: int,
           n_eq: int,
           n_ineq: int,
           func: Callable[[csc, csc, csc, csc, csc, Vec, Vec, Vec, csc, csc, csc, csc, float],
                          Tuple[float, Vec, Vec, Vec, csc, csc, csc, csc, csc]],
           arg=(),
           max_iter=100,
           tol=1e-6,
           verbose: int = 0) -> Tuple[Vec, float, Vec, Vec]:
    """
    Solve a non-linear problem of the form:

        min: f(x)
        s.t.
            G(x)  = 0
            H(x) <= 0
            xmin <= x <= xmax

    The problem is specified by a function `f_eval`
    This function is called with (x, mu, lmbda) and
    returns (f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx)

    where:
        x: array of variables
        lambda: Lagrange Multiplier associated with the inequality constraints
        pi: Lagrange Multiplier associated with the equality constraints
        f: objective function value (float)
        G: Array of equality mismatches (vec)
        H: Array of inequality mismatches (vec)
        fx: jacobian of f(x) (vec)
        Gx: Jacobian of G(x) (CSC mat)
        Hx: Jacobian of H(x) (CSC mat)
        fxx: Hessian of f(x) (CSC mat)
        Gxx: Hessian of G(x) (CSC mat)
        Hxx: Hessian of H(x) (CSC mat)

    See: On Computational Issues of Market-Based Optimal Power Flow by
         Hongye Wang, Carlos E. Murillo-Sánchez, Ray D. Zimmerman, and Robert J. Thomas
         IEEE TRANSACTIONS ON POWER SYSTEMS, VOL. 22, NO. 3, AUGUST 2007

    :param x0: Initial solution
    :param n_x: Number of variables (size of x)
    :param n_eq: Number of equality constraints (rows of H)
    :param n_ineq: Number of inequality constraints (rows of G)
    :param func: A function pointer called with (x, mu, lmbda, *args) that returns (f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx)
    :param arg: Tuple of arguments to call func: func(x, mu, lmbda, *arg)
    :param max_iter: Maximum number of iterations
    :param tol: Expected tolerance
    :param verbose: 0 to 3 (the larger, the more verbose)
    :return: x, error, gamma, lam
    """
    START = timeit.default_timer()

    # Init iteration values
    error = 1e20
    iter_counter = 0
    f = 0.0  # objective function
    x = x0.copy()
    gamma = 1.0

    # Init multiplier values. Defaulted at 1.
    lam = np.ones(n_eq)
    mu = np.ones(n_ineq)
    z = np.ones(n_ineq)
    e = np.ones(n_ineq)
    z_inv = diags(1.0 / z)
    mu_diag = diags(mu)

    while error > gamma and iter_counter < max_iter:

        # Evaluate the functions, gradients and hessians at the current iteration.
        f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx = func(x, mu, lam, *arg)

        # compose the Jacobian
        M = fxx + Gxx + Hxx + Hx @ z_inv @ mu_diag @ Hx.T
        J = pack_3_by_4(M, Gx.tocsc(), Gx.T)

        # compose the residual
        N = fx + Hx @ mu + Hx @ z_inv @ (gamma * e + mu * H) + Gx @ lam
        r = - np.r_[N, G]

        # Find the reduced problem residuals and split them
        dx, dlam = split(sparse.linalg.spsolve(J, r), n_x)

        # TODO: Implement step control

        # Calculate the inequalities residuals using the reduced problem residuals
        dz = -H - z - Hx.T @ dx
        dmu = -mu + z_inv @ (gamma * e - mu * dz)

        # Compute the maximum step allowed
        alpha_p = step_calculation(z, dz)
        alpha_d = step_calculation(mu, dmu)

        # Update the values of the variables and multipliers
        x += dx * alpha_p
        z += dz * alpha_p
        lam += dlam * alpha_d
        mu += dmu * alpha_d
        gamma = max(0.1 * (mu @ z) / n_ineq, tol)  # Maximum tolerance requested.

        # Compute the maximum error and the new gamma value
        error = calc_error(dx, dz, dmu, dlam)

        z_inv = diags(1.0 / z)
        mu_diag = diags(mu)

        if verbose > 1:
            print(f'Iteration: {iter_counter}', "-" * 80)
            if verbose > 2:
                x_df = pd.DataFrame(data={'x': x, 'dx': dx})
                eq_df = pd.DataFrame(data={'λ': lam, 'dλ': dlam})
                ineq_df = pd.DataFrame(data={'mu': mu, 'z': z, 'dmu': dmu, 'dz': dz})

                print("x:\n", x_df)
                print("EQ:\n", eq_df)
                print("INEQ:\n", ineq_df)
            print("\tGamma:", gamma)
            print("\tErr:", error)

        # Add an iteration step
        iter_counter += 1

    END = timeit.default_timer()

    if verbose > 0:
        print(f'SOLUTION', "-" * 80)
        print("\tx:", x)
        print("\tλ:", lam)
        print("\tF.obj:", f)  # This is the old value of the function, has to be recalculated with the last iteration.
        print("\tErr:", error)
        print(f'\tIterations: {iter_counter}')
        print('\tTime elapsed (s): ', END - START)

    return x, error, gamma, lam
