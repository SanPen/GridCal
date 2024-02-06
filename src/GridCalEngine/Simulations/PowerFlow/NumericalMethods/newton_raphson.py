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
import scipy
import numpy as np
from GridCalEngine.Utils.NumericalMethods.sparse_solve import get_sparse_type, get_linear_solver
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.ac_jacobian import AC_jacobian
import GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.enumerations import ReactivePowerControlMode
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import control_q_inside_method
from GridCalEngine.basic_structures import Logger

linear_solver = get_linear_solver()
sparse = get_sparse_type()
scipy.ALLOW_THREADS = True
np.set_printoptions(precision=8, suppress=True, linewidth=320)


def NR_LS(Ybus, S0, V0, I0, Y0, pv_, pq_, Qmin, Qmax, tol, max_it=15, mu_0=1.0,
          acceleration_parameter=0.05, control_q=ReactivePowerControlMode.NoControl,
          verbose=False, logger: Logger = None) -> NumericPowerFlowResults:
    """
    Solves the power flow using a full Newton's method with backtracking correction.
    @Author: Santiago Peñate-Vera
    :param Ybus: Admittance matrix
    :param S0: Array of nodal power Injections (ZIP)
    :param V0: Array of nodal voltages (initial solution)
    :param I0: Array of nodal current Injections (ZIP)
    :param Y0: Array of nodal admittance Injections (ZIP)
    :param pv_: Array with the indices of the PV buses
    :param pq_: Array with the indices of the PQ buses
    :param Qmin: array of lower reactive power limits per bus
    :param Qmax: array of upper reactive power limits per bus
    :param tol: Tolerance
    :param max_it: Maximum number of iterations
    :param mu_0: initial acceleration value
    :param acceleration_parameter: parameter used to correct the "bad" iterations, should be between 1e-3 ~ 0.5
    :param control_q: Control reactive power
    :param verbose: Display console information
    :param logger: Logger instance
    :return: NumericPowerFlowResults instance
    """
    start = time.time()

    # initialize
    iteration = 0
    V = V0
    Va = np.angle(V)
    Vm = np.abs(V)
    dVa = np.zeros_like(Va)
    dVm = np.zeros_like(Vm)

    # set up indexing for updating V
    pq = pq_.copy()
    pv = pv_.copy()
    pvpq = np.r_[pv, pq]
    npv = len(pv)
    npq = len(pq)
    npvpq = npv + npq

    if npvpq > 0:

        # evaluate F(x0)
        Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)
        Scalc = cf.compute_power(Ybus, V)
        f = cf.compute_fx(Scalc, Sbus, pvpq, pq)
        norm_f = cf.compute_fx_error(f)
        converged = norm_f < tol

        if verbose:
            logger.add_debug('NR Iteration {0}'.format(iteration) + '-' * 200)
            logger.add_debug('error', norm_f)

        # do Newton iterations
        while not converged and iteration < max_it:
            # update iteration counter
            iteration += 1

            # evaluate Jacobian
            J = AC_jacobian(Ybus, V, pvpq, pq)

            # compute update step
            try:
                dx = linear_solver(J, f)

                if np.isnan(dx).any():
                    end = time.time()
                    elapsed = end - start
                    logger.add_error('NR Singular matrix @iter:'.format(iteration))

                    return NumericPowerFlowResults(V=V0, converged=converged, norm_f=norm_f,
                                                   Scalc=S0, ma=None, theta=None, Beq=None,
                                                   Ybus=None, Yf=None, Yt=None,
                                                   iterations=iteration, elapsed=elapsed)
            except RuntimeError:
                end = time.time()
                elapsed = end - start

                logger.add_error('NR Singular matrix @iter:'.format(iteration))

                return NumericPowerFlowResults(V=V0, converged=converged, norm_f=norm_f,
                                               Scalc=S0, ma=None, theta=None, Beq=None,
                                               Ybus=None, Yf=None, Yt=None,
                                               iterations=iteration, elapsed=elapsed)

            if verbose:
                logger.add_debug('NR Iteration {0}'.format(iteration) + '-' * 200)

                if verbose > 1:
                    logger.add_debug('J:\n', J.toarray())
                    logger.add_debug('f:\n', f)
                    logger.add_debug('dx:\n', dx)
                    logger.add_debug('Vm:\n', Vm)
                    logger.add_debug('Va:\n', Va)

            # reassign the solution vector
            dVa[pvpq] = dx[:npvpq]
            dVm[pq] = dx[npvpq:]

            # set the values and correct with an adaptive mu if needed
            mu = mu_0  # ideally 1.0
            back_track_condition = True
            l_iter = 0
            norm_f_new = 0.0
            while back_track_condition and l_iter < max_it and mu > tol:

                # update voltage the Newton way
                Vm2 = Vm - mu * dVm
                Va2 = Va - mu * dVa
                V2 = cf.polar_to_rect(Vm2, Va2)

                # compute the mismatch function f(x_new)
                Sbus = cf.compute_zip_power(S0, I0, Y0, Vm2)
                Scalc = cf.compute_power(Ybus, V2)
                f = cf.compute_fx(Scalc, Sbus, pvpq, pq)
                norm_f_new = cf.compute_fx_error(f)

                # change mu for the next iteration
                mu *= acceleration_parameter

                # keep back-tracking?
                back_track_condition = norm_f_new > norm_f

                if not back_track_condition:
                    # accept the solution
                    Vm = Vm2
                    Va = Va2
                    V = V2
                    norm_f = norm_f_new

                if verbose > 1:
                    if l_iter == 0:
                        logger.add_debug('error', norm_f_new)
                    else:
                        logger.add_debug('Backtrcking, mu=', mu, 'error', norm_f_new)

                l_iter += 1

            if l_iter > 1 and back_track_condition:
                # this means that not even the backtracking was able to correct
                # the solution, so terminate

                end = time.time()
                elapsed = end - start
                # return NumericPowerFlowResults(V, converged, norm_f_new, Scalc,
                #                                None, None, None, None, None, None,
                #                                iteration, elapsed)
                return NumericPowerFlowResults(V=V, converged=converged, norm_f=norm_f,
                                               Scalc=Scalc, ma=None, theta=None, Beq=None,
                                               Ybus=None, Yf=None, Yt=None,
                                               iterations=iteration, elapsed=elapsed)

            # review reactive power limits
            # it is only worth checking Q limits with a low error
            # since with higher errors, the Q values may be far from realistic
            # finally, the Q control only makes sense if there are pv nodes
            if control_q != ReactivePowerControlMode.NoControl and norm_f < 1e-2 and npv > 0:

                # check and adjust the reactive power
                # this function passes pv buses to pq when the limits are violated,
                # but not pq to pv because that is unstable
                n_changes, Scalc, S0, pv, pq, pvpq, messages = control_q_inside_method(Scalc, S0, pv, pq,
                                                                                       pvpq, Qmin, Qmax)

                if n_changes > 0:
                    # adjust internal variables to the new pq|pv values
                    npv = len(pv)
                    npq = len(pq)
                    npvpq = npv + npq

                    # recompute the error based on the new Scalc and S0
                    Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)
                    f = cf.compute_fx(Scalc, Sbus, pvpq, pq)
                    norm_f = np.linalg.norm(f, np.inf)

                    if verbose > 0:
                        for sense, idx, var in messages:
                            msg = "Bus i=" + str(idx) + " changed to PQ, limited to " + str(var * 100) + " MVAr"
                            logger.add_debug(msg)

            # determine the convergence condition
            converged = norm_f <= tol

    else:
        norm_f = 0
        converged = True
        Scalc = cf.compute_zip_power(S0, I0, Y0, Vm)  # compute the ZIP power injection

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V=V, converged=converged, norm_f=norm_f,
                                   Scalc=Scalc, ma=None, theta=None, Beq=None,
                                   Ybus=None, Yf=None, Yt=None,
                                   iterations=iteration, elapsed=elapsed)
