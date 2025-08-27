# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Callable, Any, Union, List, Dict, Tuple
from dataclasses import dataclass
import numba as nb
import numpy as np
import pandas as pd
from scipy.sparse import csc_matrix as csc
from scipy import sparse
import timeit
from matplotlib import pyplot as plt
from VeraGridEngine.basic_structures import Vec, CxVec
from VeraGridEngine.Utils.Sparse.csc import pack_3_by_4, diags
from VeraGridEngine.Utils.NumericalMethods.sparse_solve import get_linear_solver
from VeraGridEngine.enumerations import SparseSolver

linear_solver = get_linear_solver(SparseSolver.Pardiso)


def step_calculation(v: Vec, dv: Vec, tau: float = 0.99995):
    """
    This function calculates for each Lambda multiplier or its associated Slack variable
    the maximum allowed step in order to not violate the KKT condition Lambda > 0 and S > 0
    :param v: Array of multipliers or slack variables
    :param dv: Variation calculated in the Newton step
    :param tau: Factor to be not exactly 1
    :return: step size value for the given multipliers
    """
    k = np.flatnonzero(dv < 0.0)
    if len(k) > 0:
        alpha = min([tau * min(v[k] / (-dv[k] + 1e-15)), 1])
    else:
        alpha = 1

    return alpha


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


@nb.njit(cache=True)
def max_abs(x: Vec):
    """
    Compute max abs efficiently
    :param x: State vector
    :return: Inf-norm of the state vector
    """
    max_val = 0.0
    for x_val in x:
        x_abs = x_val if x_val > 0.0 else -x_val
        if x_abs > max_val:
            max_val = x_val

    return max_val


def calc_feascond(g: Vec, h: Vec, x: Vec, z: Vec):
    """
    Calculate the feasible conditions
    :param g: Equality values
    :param h: Inequality values
    :param x: State vector
    :param z: Vector of z slack variables
    :return: Feasibility condition value
    """
    return max(max_abs(g), np.max(h)) / (1.0 + max(max_abs(x), max_abs(z)))


def calc_gradcond(lx: Vec, lam: Vec, mu: Vec):
    """
    calculate the gradient conditions
    :param lx: Gradient of the lagrangian
    :param lam: Vector of lambda multipliers
    :param mu: Vector of mu multipliers
    :return: Gradient condition value
    """
    return max_abs(lx) / (1 + max(max_abs(lam), max_abs(mu)))


def calc_ccond(mu: Vec, z: Vec, x: Vec):
    """
    :param mu: Vector of mu mutipliers
    :param z: Vector of z slack variables
    :param x: State vector
    :return: Vector of ccond
    """
    return (mu @ z) / (1.0 + max_abs(x))


def calc_ocond(f: float, f_prev: float):
    """

    :param f: Value of objective funciton
    :param f_prev: Previous value of objective function
    :return: Variation of the objective function
    """
    return abs(f - f_prev) / (1.0 + abs(f_prev))


@dataclass
class IpsFunctionReturn:
    """
    Represents the returning value of the interior point evaluation
    """
    f: float  # objective function value
    G: Vec  # equalities increment vector
    H: Vec  # inequalities increment vector
    fx: Vec  # objective function Jacobian Vector
    Gx: csc  # equalities Jacobian Matrix
    Hx: csc  # inequalities Jacobian Matrix
    fxx: csc  # objective function Hessian Matrix
    Gxx: csc  # equalities Hessian Matrix
    Hxx: csc  # inequalities Hessian Matrix

    # extra data passed through for the results
    S: CxVec
    Sf: CxVec
    St: CxVec

    def get_data(self) -> List[Union[float, Vec, csc]]:
        """
        Returns the structures in a list
        :return: List of float, Vec, and csc
        """
        return [self.f, self.G, self.H, self.fx, self.Gx, self.Hx, self.fxx, self.Gxx, self.Hxx]

    @staticmethod
    def get_headers() -> List[str]:
        """
        Returns the structures' names
        :return: list of str
        """
        return ['f', 'G', 'H', 'fx', 'Gx', 'Hx', 'fxx', 'Gxx', 'Hxx']

    def compare(self, other: "IpsFunctionReturn", h: float) -> Dict[str, Union[float, Vec, csc]]:
        """
        Returns the comparison between this structure and another structure of this type
        :param other: IpsFunctionReturn
        :param h: finite differences step
        :return: Dictionary with the structure name and the difference
        """
        errors = dict()
        for i, (analytic_struct, finit_struct, name) in enumerate(zip(self.get_data(),
                                                                      other.get_data(),
                                                                      self.get_headers())):
            # if isinstance(analytic_struct, np.ndarray):
            if sparse.isspmatrix(analytic_struct):
                a = analytic_struct.toarray()
                b = finit_struct.toarray()
            else:
                a = analytic_struct
                b = finit_struct

            ok = np.allclose(a, b, atol=h * 10)

            if not ok:
                diff = a - b
                errors[name] = diff

        return errors


@dataclass
class IpsSolution:
    """
    Represents the returning value of the interior point solution
    """
    x: Vec
    error: float
    gamma: float
    lam: Vec
    dlam: Vec
    mu: Vec
    z: Vec
    residuals: Vec
    structs: IpsFunctionReturn
    converged: bool
    iterations: int
    error_evolution: Vec

    def plot_error(self):
        """
        Plot the IPS error
        """
        plt.figure()
        plt.plot(self.error_evolution, )
        plt.xlabel("Iterations")
        plt.ylabel("Error")
        plt.yscale('log')
        plt.show()


def interior_point_solver(x0: Vec,
                          n_x: int,
                          n_eq: int,
                          n_ineq: int,
                          func: Callable[[Vec, Vec, Vec, bool, bool, Any], IpsFunctionReturn],
                          arg=(),
                          max_iter=100,
                          tol=1e-6,
                          pf_init=False,
                          trust=0.9,
                          verbose: int = 0,
                          step_control=False) -> Tuple[IpsSolution, Vec]:
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
    :param tol: Convergence tolerance
    :param pf_init: Use the power flow solution as initial values
    :param trust: Amount of trust in the initial Newton derivative length estimation
    :param verbose: 0 to 3 (the larger, the more verbose)
    :param step_control: Use step control to improve the solution process control
    :return: IpsSolution
    """

    times = np.array([np.zeros(15)])
    t_start = timeit.default_timer()

    # Init iteration values
    error = 1e6
    iter_counter = 0
    x = x0.copy()
    gamma = 1.0
    nabla = 0.05
    rho_lower = 1.0 - nabla
    rho_upper = 1.0 + nabla
    e = np.ones(n_ineq)

    # Our init, which computes the multipliers as a solution of the KKT conditions
    if pf_init:
        z0 = 1.0
        z = z0 * np.ones(n_ineq)
        lam = np.ones(n_eq)
        mu = z.copy()
        ret = func(x, mu, lam, True, False, *arg)
        z = - ret.H
        z = np.array([1e-2 if zz < 1e-2 else zz for zz in z])
        z_inv = diags(1.0 / z)
        mu = gamma * (z_inv @ e)
        mu_diag = diags(mu)
        lam = sparse.linalg.lsqr(ret.Gx.T, -ret.fx - ret.Hx.T @ mu.T)[0]

    # PyPower-like init
    else:
        ret, _ = func(x, None, None, False, False, *arg)
        z0 = 1.0
        z = z0 * np.ones(n_ineq)
        mu = z0 * np.ones(n_ineq)
        lam = np.zeros(n_eq)
        kk = np.flatnonzero(ret.H < -z0)
        z[kk] = -ret.H[kk]
        z_inv = diags(1.0 / z)
        kk = np.flatnonzero((gamma / z) > z0)
        mu[kk] = gamma / z[kk]
        mu_diag = diags(mu)

    ret, _ = func(x, mu, lam, True, False, *arg)

    feascond = calc_feascond(g=ret.G, h=ret.H, x=x, z=z)
    converged = error <= gamma
    maxdispl = 0
    error_evolution = np.zeros(max_iter + 1)
    feascond_evolution = np.zeros(max_iter + 1)

    # record initial values
    feascond_evolution[iter_counter] = feascond
    error_evolution[0] = error
    n = np.zeros(n_x + n_eq)
    dlam = None
    while not converged and iter_counter < max_iter:
        ts_iter = timeit.default_timer()
        # Evaluate the functions, gradients and hessians at the current iteration.
        if iter_counter == 0:
            ret, new_times_0 = func(x, mu, lam, True, True, *arg)
        else:
            new_times_0 = 0
        Hx_t = ret.Hx.T
        Gx_t = ret.Gx.T
        # compose the Jacobian
        lxx = ret.fxx + ret.Gxx + ret.Hxx
        m = lxx + Hx_t @ z_inv @ mu_diag @ ret.Hx
        jac = pack_3_by_4(m.tocsc(), Gx_t.tocsc(), ret.Gx.tocsc())

        # compose the residual
        lx = ret.fx + Gx_t @ lam + Hx_t @ mu
        n = lx + Hx_t @ z_inv @ (gamma * e + mu * ret.H)
        r = - np.r_[n, ret.G]

        # Find the reduced problem residuals and split them
        ts_nrstep = timeit.default_timer()
        dx, dlam = split(linear_solver(jac, r), n_x)
        te_nrstep = timeit.default_timer()
        # Calculate the inequalities residuals using the reduced problem residuals

        ts_mult = timeit.default_timer()
        dz = - ret.H - z - ret.Hx @ dx
        dmu = - mu + z_inv @ (gamma * e - mu * dz)
        te_mult = timeit.default_timer()
        # Step control as in PyPower
        if step_control:
            l0 = ret.f + np.dot(lam, ret.G) + np.dot(mu, ret.H + z) - gamma * np.sum(np.log(z))
            alpha = trust
            for j in range(20):
                dx1 = alpha * dx
                x1 = x + dx1

                ret1 = func(x1, mu, lam, False, False, *arg)

                l1 = ret1.f + lam.T @ ret1.G + mu.T @ (ret1.H + z) - gamma * np.sum(np.log(z))
                rho = (l1 - l0) / (lx @ dx1 + 0.5 * dx1.T @ lxx @ dx1)

                if rho_lower < rho < rho_upper:
                    break
                else:
                    alpha = alpha / 2.0
                    print('Use step control!')

            dx = alpha * dx
            dz = alpha * dz
            dlam = alpha * dlam
            dmu = alpha * dmu

        # Compute the maximum step allowed
        ts_steps = timeit.default_timer()
        alpha_p = step_calculation(z, dz)
        alpha_d = step_calculation(mu, dmu)
        te_steps = timeit.default_timer()
        # Update the values of the variables and multipliers
        x += dx * alpha_p
        z += dz * alpha_p
        lam += dlam * alpha_d
        mu += dmu * alpha_d
        gamma = 0.1 * mu @ z / n_ineq

        # Update fobj, g, h, calculate next step.
        ret, new_times_i = func(x, mu, lam, True, True, *arg)

        ts_conds = timeit.default_timer()
        Hx_t = ret.Hx.T
        Gx_t = ret.Gx.T
        g_norm = np.linalg.norm(ret.G, np.inf)
        lam_norm = np.linalg.norm(lam, np.inf)
        mu_norm = np.linalg.norm(mu, np.inf)
        z_norm = np.linalg.norm(z, np.inf)

        lx = ret.fx + Hx_t @ mu + Gx_t @ lam
        feascond = max([g_norm, max(ret.H)]) / (1 + max([np.linalg.norm(x, np.inf), z_norm]))
        gradcond = np.linalg.norm(lx, np.inf) / (1 + max([lam_norm, mu_norm]))
        error = np.max([feascond, gradcond, gamma])
        maxdispl = np.max(np.r_[dx, dlam, dz, dmu])
        z_inv = diags(1.0 / z)
        mu_diag = diags(mu)
        te_conds = timeit.default_timer()
        converged = feascond < tol and gradcond < tol and gamma < tol

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
            print("\tMax Displacement:", maxdispl)

        # Add an iteration step
        iter_counter += 1

        # record evolution
        feascond_evolution[iter_counter] = feascond
        error_evolution[iter_counter] = error



        te_iter = timeit.default_timer()
        new_times = np.r_[new_times_i+new_times_0, te_nrstep - ts_nrstep, te_mult - ts_mult, te_steps - ts_steps, te_conds - ts_conds, te_iter - ts_iter]
        times_i = times.copy()
        times = np.r_[times_i, [new_times]]

    t_end = timeit.default_timer()

    if verbose > 0:
        print(f'SOLUTION', "-" * 80)
        print(f"\tx:", x)
        print(f"\tλ:", lam)
        print(f"\tF.obj: {ret.f * 1e4}")
        print(f"\tErr: {error}")
        print(f'\tIterations: {iter_counter}')
        print(f'\tMax Displacement: {maxdispl}' )
        print(f'\tTime elapsed (s): {t_end - t_start}')
        print(f'\tFeas cond: ', feascond)

    return IpsSolution(x=x, error=error, gamma=gamma, lam=lam, dlam=dlam, mu=mu, z=z, residuals=n, structs=ret,
                       converged=converged, iterations=iter_counter, error_evolution=error_evolution), times
