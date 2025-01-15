# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Union, List, Dict
from dataclasses import dataclass
import numba as nb
import numpy as np
import pandas as pd
from scipy.sparse import csc_matrix as csc
from scipy import sparse
import timeit
from matplotlib import pyplot as plt
from GridCalEngine.basic_structures import Vec, CxVec
from GridCalEngine.Utils.Sparse.csc import pack_3_by_4, diags
from GridCalEngine.Utils.NumericalMethods.sparse_solve import get_linear_solver
from GridCalEngine.enumerations import SparseSolver


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
def calc_error(dx: Vec, dz: Vec, dmu: Vec, dlmbda: Vec) -> float:
    """
    Calculate the error of the process
    :param dx: x increments array
    :param dz: z increments array
    :param dmu: mu increments array
    :param dlmbda: lambda increments array
    :return: max abs value of all the increments
    """
    err = 0.0

    for arr in [dx, dz, dmu, dlmbda]:
        for i in range(len(arr)):
            v = abs(arr[i])
            if v > err:
                err = v

    return err


@nb.njit(cache=True)
def max_abs(x: Vec) -> float:
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


def calc_feas_cond(g: Vec, h: Vec, x: Vec, z: Vec) -> float:
    """
    Calculate the feasible conditions
    :param g: Equality values
    :param h: Inequality values
    :param x: State vector
    :param z: Vector of z slack variables
    :return: Feasibility condition value
    """
    return max(max_abs(g), np.max(h)) / (1.0 + max(max_abs(x), max_abs(z)))


def calc_grad_cond(lx: Vec, lam: Vec, mu: Vec) -> float:
    """
    calculate the gradient conditions
    :param lx: Gradient of the lagrangian
    :param lam: Vector of lambda multipliers
    :param mu: Vector of mu multipliers
    :return: Gradient condition value
    """
    return max_abs(lx) / (1 + max(max_abs(lam), max_abs(mu)))


def calc_c_cond(mu: Vec, z: Vec, x: Vec) -> float:
    """
    :param mu: Vector of mu multipliers
    :param z: Vector of z slack variables
    :param x: State vector
    :return: Vector of c-cond
    """
    return float(mu @ z) / (1.0 + max_abs(x))


def calc_o_cond(f: float, f_prev: float) -> float:
    """

    :param f: Value of objective function
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
        for i, (analytic_struct, f_init_struct, name) in enumerate(zip(self.get_data(),
                                                                       other.get_data(),
                                                                       self.get_headers())):
            # if isinstance(analytic_struct, np.ndarray):
            if sparse.isspmatrix(analytic_struct):
                a = analytic_struct.toarray()
                b = f_init_struct.toarray()
            else:
                a = analytic_struct
                b = f_init_struct

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


def interior_point_solver(problem,
                          max_iter=100,
                          tol=1e-6,
                          pf_init=False,
                          trust=0.9,
                          verbose: int = 0,
                          step_control=False) -> IpsSolution:
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

    :param problem: Optimization problem structure
    :param max_iter: Maximum number of iterations
    :param tol: Convergence tolerance
    :param pf_init: Use the power flow solution as initial values
    :param trust: Amount of trust in the initial Newton derivative length estimation
    :param verbose: 0 to 3 (the larger, the more verbose)
    :param step_control: Use step control to improve the solution process control
    :return: IpsSolution
    """

    linear_solver = get_linear_solver(SparseSolver.Pardiso)

    t_start = timeit.default_timer()

    # Init iteration values
    error = 1e6
    iter_counter = 0
    x = problem.x0
    gamma = 1.0
    nabla = 0.05
    rho_lower = 1.0 - nabla
    rho_upper = 1.0 + nabla
    e = np.ones(problem.nineq)

    # Our init, which computes the multipliers as a solution of the KKT conditions
    if pf_init:
        z0 = 1.0
        z = z0 * np.ones(problem.nineq)
        lam = np.ones(problem.neq)
        mu = z.copy()
        f, G, H = problem.update(x)
        fx, Gx, Hx, _, _, _ = problem.get_jacobians_and_hessians(mu=mu, lam=lam, compute_hessians=False)
        z = - H
        z = np.array([1e-2 if zz < 1e-2 else zz for zz in z])
        z_inv = diags(1.0 / z)
        mu = gamma * (z_inv @ e)
        mu_diag = diags(mu)
        lam = sparse.linalg.lsqr(Gx.T, - fx - Hx.T @ mu.T)[0]

    # PyPower-like init
    else:
        f, G, H = problem.update(x)
        z0 = 1.0
        z = z0 * np.ones(problem.nineq)
        mu = z0 * np.ones(problem.nineq)
        lam = np.zeros(problem.neq)
        kk = np.flatnonzero(H < -z0)
        z[kk] = - H[kk]
        z_inv = diags(1.0 / z)
        kk = np.flatnonzero((gamma / z) > z0)
        mu[kk] = gamma / z[kk]
        mu_diag = diags(mu)

    fx, Gx, Hx, fxx, Gxx, Hxx = problem.get_jacobians_and_hessians(mu=mu, lam=lam, compute_hessians=True)
    feas_cond = calc_feas_cond(g=G, h=H, x=x, z=z)
    converged = error <= gamma
    max_displ = 0
    error_evolution = np.zeros(max_iter + 1)
    feas_cond_evolution = np.zeros(max_iter + 1)

    # record initial values
    feas_cond_evolution[iter_counter] = feas_cond
    error_evolution[0] = error
    n = np.zeros(problem.NV + problem.neq)
    dlam = None

    while not converged and iter_counter < max_iter:
        # Evaluate the functions, gradients and hessians at the current iteration.
        Hx_t = Hx.T
        Gx_t = Gx.T

        # compose the Jacobian
        lxx = fxx + Gxx + Hxx
        m = lxx + Hx_t @ z_inv @ mu_diag @ Hx
        jac = pack_3_by_4(m.tocsc(), Gx_t.tocsc(), Gx.tocsc())

        # compose the residual
        lx = fx + Gx_t @ lam + Hx_t @ mu
        n = lx + Hx_t @ z_inv @ (gamma * e + mu * H)
        r = - np.r_[n, G]

        # Find the reduced problem residuals and split them
        dx, dlam = split(linear_solver(jac, r), problem.NV)

        # Calculate the inequalities residuals using the reduced problem residuals
        dz = - H - z - Hx @ dx
        dmu = - mu + z_inv @ (gamma * e - mu * dz)

        # Step control as in PyPower
        if step_control:
            l0 = f + np.dot(lam, G) + np.dot(mu, H + z) - gamma * np.sum(np.log(z))
            alpha = trust
            for j in range(20):
                dx1 = alpha * dx
                x1 = x + dx1

                f, G, H = problem.update(x1)

                l1 = f + lam.T @ G + mu.T @ (H + z) - gamma * np.sum(np.log(z))
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
        alpha_p = step_calculation(z, dz)
        alpha_d = step_calculation(mu, dmu)
        # Update the values of the variables and multipliers
        x += dx * alpha_p
        z += dz * alpha_p
        lam += dlam * alpha_d
        mu += dmu * alpha_d
        gamma = 0.1 * mu @ z / problem.nineq

        # Update fobj, g, h, calculate next step.
        f, G, H = problem.update(x)
        fx, Gx, Hx, fxx, Gxx, Hxx = problem.get_jacobians_and_hessians(mu=mu, lam=lam, compute_hessians=True)

        Hx_t = Hx.T
        Gx_t = Gx.T
        g_norm = np.linalg.norm(G, np.inf)
        lam_norm = np.linalg.norm(lam, np.inf)
        mu_norm = np.linalg.norm(mu, np.inf)
        z_norm = np.linalg.norm(z, np.inf)

        lx = fx + Hx_t @ mu + Gx_t @ lam
        feas_cond = max([g_norm, max(H)]) / (1 + max([np.linalg.norm(x, np.inf), z_norm]))
        gradcond = np.linalg.norm(lx, np.inf) / (1 + max([lam_norm, mu_norm]))
        error = np.max([feas_cond, gradcond, gamma])
        max_displ = np.max(np.r_[dx, dlam, dz, dmu])
        z_inv = diags(1.0 / z)
        mu_diag = diags(mu)
        converged = feas_cond < tol and gradcond < tol and gamma < tol

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
            print("\tMax Displacement:", max_displ)

        # Add an iteration step
        iter_counter += 1

        # record evolution
        feas_cond_evolution[iter_counter] = feas_cond
        error_evolution[iter_counter] = error

    t_end = timeit.default_timer()

    if verbose > 0:
        print(f'SOLUTION', "-" * 80)
        print(f"\tx:", x)
        print(f"\tλ:", lam)
        print(f"\tF.obj: {f * 1e4}")
        print(f"\tErr: {error}")
        print(f'\tIterations: {iter_counter}')
        print(f'\tMax Displacement: {max_displ}')
        print(f'\tTime elapsed (s): {t_end - t_start}')
        print(f'\tFeas cond: ', feas_cond)

    return IpsSolution(x=x, error=error, gamma=gamma, lam=lam, dlam=dlam, mu=mu, z=z, residuals=n,
                       converged=converged, iterations=iter_counter, error_evolution=error_evolution)
