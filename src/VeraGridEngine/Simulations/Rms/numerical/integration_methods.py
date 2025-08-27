# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import pdb
import sys
import numpy as np
from scipy.sparse import bmat, identity, csc_matrix
from scipy.sparse.linalg import spsolve
from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.Simulations.Rms.problems.rms_problem import RmsProblem


class Integration:
    """
    Base class for implicit iterative methods.
    """

    @staticmethod
    def calc_jac(dae: RmsProblem, dt: float) -> csc_matrix:
        """
        Calculates the Jacobian according to integration method.
        :param dae: DAE class
        :param dt: time interval
        :return:
        """
        raise NotImplementedError("You need to implement calc_jac")

    @staticmethod
    def calc_f_res(x: Vec, f: Vec, Tf: csc_matrix, h: float, x0: Vec, f0: Vec) -> Vec:
        """
        Calculates the state residual according to integration method.
        :param x: states variables values array
        :param f: states functions values array
        :param Tf: Tf
        :param h: integration step size
        :param x0: initial states variables values array
        :param f0: initial states functions values array
        :return:
        """
        raise NotImplementedError("You need to implement calc_f_res")

    def step(self, dae: RmsProblem, dt: float, tol: float, max_iter: int):
        """
        Perform an implicit integration step with Newton-Raphson
        :param dae: DAE class
        :param dt: time interval
        :param tol: tolerance
        :param max_iter: maximum of iterations
        :return:
        """
        x0, y0, f0 = dae.x.copy(), dae.y.copy(), dae.f.copy()

        for iteration in range(max_iter):
            # Compute Jacobian and residual
            jac = self.calc_jac(dae, dt)
            f_residual = self.calc_f_res(dae.x, dae.f, dae.Tf, dt, x0, f0)
            residual = np.vstack((f_residual.reshape(-1, 1), dae.g.reshape(-1, 1)))  # Include algebraic residuals

            # Solve linear system
            dx = spsolve(jac, -residual)

            # Update state and algebraic variables
            dae.x += 0.5 * dx[:dae.nx]
            dae.y += 0.5 * dx[dae.nx:]

            # Recompute f and g
            dae.update_fg()

            # Check convergence
            residual_error = np.linalg.norm(residual, np.inf)
            if residual_error < tol:
                return True

        # Restore previous values if not converged
        dae.x, dae.y, dae.f = x0, y0, f0
        return False

    def steadystate(self, dae: RmsProblem, tol=1e-2, max_iter=10):
        """
        Perform an implicit integration step with Newton-Raphson.
        :param dae: DAE class
        :param method: iterative method
        :param tol: tolerance
        :param max_iter: maximum of iterations
        :return:
        """

        for iteration in range(max_iter):
            jac = self.calc_jac(dae, dt=1.0)
            residual = np.vstack((dae.f.reshape(-1, 1), dae.g.reshape(-1, 1)))

            pdb.set_trace()

            # Solve linear system
            inc = spsolve(jac, -residual)

            # Update variables
            dae.x += 0.5 * inc[:dae.nx]
            dae.y += 0.5 * inc[dae.nx:]

            # Recompute f and g
            dae.update_fg()
            np.set_printoptions(threshold=sys.maxsize)

            # Check convergence
            residual_error = np.linalg.norm(residual, np.inf)
            if residual_error < tol:
                return True

        return False


class BackEuler(Integration):
    """
    Backward Euler method.
    """

    @staticmethod
    def calc_jac(dae: RmsProblem, dt: float) -> csc_matrix:
        """
        Builds Jacobian
        :param dae: DAE class
        :param dt: time interval
        :return: Jacobian in csc format
        """
        return bmat([[identity(dae.nx) - dt * dae.dfx, -dt * dae.dfy],
                     [dae.dgx, dae.dgy]], format='csc')

    @staticmethod
    def calc_f_res(x: Vec, f: Vec, Tf: csc_matrix, h: float, x0: Vec, f0: Vec) -> Vec:
        """
        Calculates f residuals
        :param x: states variables values array
        :param f: states functions values array
        :param Tf: Tf
        :param h: integration step size
        :param x0: initial states variables values array
        :param f0: initial states functions values array
        :return: f residuals array
        """
        return Tf @ (x - x0) - h * f


class Trapezoid(Integration):
    """
    Trapezoidal integration method.
    """

    @staticmethod
    def calc_jac(dae: RmsProblem, dt: float) -> csc_matrix:
        """
        Builds Jacobian
        :param dae: DAE class
        :param dt: time interval
        :return: Jacobian in csc format
        """
        return bmat([[identity(dae.nx) - 0.5 * dt * dae.dfx, -0.5 * dt * dae.dfy],
                     [dae.dgx, dae.dgy]],
                    format='csc')

    @staticmethod
    def calc_f_res(x: Vec, f: Vec, Tf: csc_matrix, h: float, x0: Vec, f0: Vec) -> Vec:
        """
        Calculates f residuals
        :param x: states variables values array
        :param f: states functions values array
        :param Tf: Tf
        :param h: integration step size
        :param x0: initial states variables values array
        :param f0: initial states functions values array
        :return: f residuals array
        """
        return Tf @ (x - x0) - 0.5 * h * (f + f0)


class SteadyState(Integration):
    """
    Steady-state computation.
    """

    @staticmethod
    def calc_jac(dae, dt=0.0) -> csc_matrix:
        """
        Builds Jacobian
        :param dae: DAE class
        :param dt: time interval
        :return: Jacobian in bmat format
        """
        return bmat([[dae.dfx, dae.dfy],
                     [dae.dgx, dae.dgy]], format='csc')

    @staticmethod
    def calc_f_res(x, f, Tf, dt, x0, f0) -> Vec:
        pass
