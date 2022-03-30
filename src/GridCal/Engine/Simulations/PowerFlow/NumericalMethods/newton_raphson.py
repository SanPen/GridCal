# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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
import scipy.sparse as sp
import numpy as np

from GridCal.Engine.Simulations.sparse_solve import get_sparse_type, get_linear_solver
from GridCal.Engine.Simulations.PowerFlow.NumericalMethods.ac_jacobian import AC_jacobian
from GridCal.Engine.Simulations.PowerFlow.NumericalMethods.common_functions import *
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCal.Engine.basic_structures import ReactivePowerControlMode
from GridCal.Engine.Simulations.PowerFlow.discrete_controls import control_q_inside_method

linear_solver = get_linear_solver()
sparse = get_sparse_type()
scipy.ALLOW_THREADS = True
np.set_printoptions(precision=8, suppress=True, linewidth=320)


def NR_LS(Ybus, S0, V0, I0, Y0, pv_, pq_, Qmin, Qmax, tol, max_it=15, mu_0=1.0,
          acceleration_parameter=0.05, error_registry=None,
          control_q=ReactivePowerControlMode.NoControl) -> NumericPowerFlowResults:
    """
    Solves the power flow using a full Newton's method with backtrack correction.
    @Author: Santiago Peñate Vera
    :param Ybus: Admittance matrix
    :param S0: Array of nodal power injections (ZIP)
    :param V0: Array of nodal voltages (initial solution)
    :param I0: Array of nodal current injections (ZIP)
    :param Y0: Array of nodal admittance injections (ZIP)
    :param pv_: Array with the indices of the PV buses
    :param pq_: Array with the indices of the PQ buses
    :param Qmin: array of lower reactive power limits per bus
    :param Qmax: array of upper reactive power limits per bus
    :param tol: Tolerance
    :param max_it: Maximum number of iterations
    :param mu_0: initial acceleration value
    :param acceleration_parameter: parameter used to correct the "bad" iterations, should be be between 1e-3 ~ 0.5
    :param error_registry: list to store the error for plotting
    :param control_q: Control reactive power
    :return: Voltage solution, converged?, error, calculated power injections
    """
    start = time.time()

    # initialize
    iter_ = 0

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
        Sbus = compute_zip_power(S0, I0, Y0, Vm)
        Scalc = compute_power(Ybus, V)
        f = compute_fx(Scalc, Sbus, pvpq, pq)
        norm_f = compute_fx_error(f)
        converged = norm_f < tol

        if error_registry is not None:
            error_registry.append(norm_f)

        # to be able to compare
        # Ybus.sort_indices()

        # do Newton iterations
        while not converged and iter_ < max_it:
            # update iteration counter
            iter_ += 1

            # evaluate Jacobian
            J = AC_jacobian(Ybus, V, pvpq, pq, npv, npq)

            # compute update step
            dx = linear_solver(J, f)

            # reassign the solution vector
            dVa[pvpq] = dx[:npvpq]
            dVm[pq] = dx[npvpq:]

            # set the restoration values
            prev_Vm = Vm.copy()
            prev_Va = Va.copy()

            # set the values and correct with an adaptive mu if needed
            mu = mu_0  # ideally 1.0
            back_track_condition = True
            l_iter = 0
            norm_f_new = 0.0
            while back_track_condition and l_iter < max_it and mu > tol:

                # restore the previous values if we are backtracking (the first iteration is the normal NR procedure)
                if l_iter > 0:
                    Va = prev_Va.copy()
                    Vm = prev_Vm.copy()

                # update voltage the Newton way
                Vm -= mu * dVm
                Va -= mu * dVa
                V = Vm * np.exp(1.0j * Va)

                # compute the mismatch function f(x_new)
                Sbus = compute_zip_power(S0, I0, Y0, Vm)
                Scalc = compute_power(Ybus, V)
                f = compute_fx(Scalc, Sbus, pvpq, pq)
                norm_f_new = compute_fx_error(f)

                back_track_condition = norm_f_new > norm_f
                mu *= acceleration_parameter
                l_iter += 1

            if l_iter > 1 and back_track_condition:
                # this means that not even the backtracking was able to correct the solution so, restore and end
                Va = prev_Va.copy()
                Vm = prev_Vm.copy()
                V = Vm * np.exp(1.0j * Va)

                end = time.time()
                elapsed = end - start
                return NumericPowerFlowResults(V, converged, norm_f_new, Scalc, None, None, None, None, None, None,
                                               iter_, elapsed)
            else:
                norm_f = norm_f_new

            # review reactive power limits
            # it is only worth checking Q limits with a low error
            # since with higher errors, the Q values may be far from realistic
            # finally, the Q control only makes sense if there are pv nodes
            if control_q != ReactivePowerControlMode.NoControl and norm_f < 1e-2 and npv > 0:

                # check and adjust the reactive power
                # this function passes pv buses to pq when the limits are violated,
                # but not pq to pv because that is unstable
                n_changes, Scalc, S0, pv, pq, pvpq = control_q_inside_method(Scalc, S0, pv, pq, pvpq, Qmin, Qmax)

                if n_changes > 0:
                    # adjust internal variables to the new pq|pv values
                    npv = len(pv)
                    npq = len(pq)
                    npvpq = npv + npq

                    # recompute the error based on the new Scalc and S0
                    Sbus = compute_zip_power(S0, I0, Y0, Vm)
                    fx = compute_fx(Scalc, Sbus, pvpq, pq)
                    norm_f = np.linalg.norm(fx, np.inf)

            if error_registry is not None:
                error_registry.append(norm_f)

            converged = norm_f < tol

    else:
        norm_f = 0
        converged = True
        Scalc = compute_zip_power(S0, I0, Y0, Vm)  # compute the ZIP power injection

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V, converged, norm_f, Scalc, None, None, None, None, None, None, iter_, elapsed)

