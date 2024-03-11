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

linear_solver = get_linear_solver()
sparse = get_sparse_type()
scipy.ALLOW_THREADS = True
np.set_printoptions(precision=8, suppress=True, linewidth=320)


def mu(Ybus, J, incS, dV, dx, pvpq, pq):
    """
    Calculate the Iwamoto acceleration parameter as described in:
    "A Load Flow Calculation Method for Ill-Conditioned Power Systems" by Iwamoto, S. and Tamura, Y."
    :param Ybus: Admittance matrix
    :param J: Jacobian matrix
    :param incS: mismatch vector
    :param dV: voltage increment (in complex form)
    :param dx: solution vector as calculated dx = solve(J, incS)
    :param pvpq: array of the pq and pv indices
    :param pq: array of the pq indices
    :return: the Iwamoto's optimal multiplier for ill conditioned systems
    """

    # evaluate the Jacobian of the voltage derivative
    # theoretically this is the second derivative matrix
    # since the Jacobian (J2) has been calculated with dV instead of V

    J2 = AC_jacobian(Ybus, dV, pvpq, pq)

    a = incS
    b = J * dx
    c = 0.5 * dx * J2 * dx

    g0 = -a.dot(b)
    g1 = b.dot(b) + 2 * a.dot(c)
    g2 = -3.0 * b.dot(c)
    g3 = 2.0 * c.dot(c)

    roots = np.roots([g3, g2, g1, g0])
    # three solutions are provided, the first two are complex, only the real solution is valid
    return roots[2].real


def IwamotoNR(Ybus, S0, V0, I0, Y0, pv_, pq_, Qmin, Qmax, tol, max_it=15,
              control_q=ReactivePowerControlMode.NoControl, robust=False) -> NumericPowerFlowResults:
    """
    Solves the power flow using a full Newton's method with the Iwamoto optimal step factor.
    :param Ybus: Admittance matrix
    :param S0: Array of nodal power Injections
    :param V0: Array of nodal voltages (initial solution)
    :param I0: Array of nodal current Injections
    :param Y0: Array of nodal admittance Injections
    :param pv_: Array with the indices of the PV buses
    :param pq_: Array with the indices of the PQ buses
    :param Qmin: Array of nodal minimum reactive power injections
    :param Qmax: Array of nodal maximum reactive power injections
    :param tol: Tolerance
    :param max_it: Maximum number of iterations
    :param control_q: ReactivePowerControlMode
    :param robust: use of the Iwamoto optimal step factor?.
    :return: Voltage solution, converged?, error, calculated power Injections
    """
    start = time.time()

    # initialize
    converged = 0
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
        Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)
        Scalc = cf.compute_power(Ybus, V)
        f = cf.compute_fx(Scalc, Sbus, pvpq, pq)
        norm_f = cf.compute_fx_error(f)

        # check tolerance
        converged = norm_f < tol

        # do Newton iterations
        while not converged and iter_ < max_it:
            # update iteration counter
            iter_ += 1

            # evaluate Jacobian
            J = AC_jacobian(Ybus, V, pvpq, pq)

            # compute update step
            try:
                dx = linear_solver(J, f)
            except:
                print(J)
                converged = False
                iter_ = max_it + 1  # exit condition
                end = time.time()
                elapsed = end - start
                return NumericPowerFlowResults(V=V, converged=converged, norm_f=norm_f,
                                               Scalc=Scalc, ma=None, theta=None, Beq=None,
                                               Ybus=None, Yf=None, Yt=None,
                                               iterations=iter_, elapsed=elapsed)

            # assign the solution vector
            dVa[pvpq] = dx[:npvpq]
            dVm[pq] = dx[npvpq:]
            dV = dVm * np.exp(1j * dVa)  # voltage mismatch

            # update voltage
            if robust:
                # if dV contains zeros will crash the second Jacobian derivative
                if not (dV == 0.0).any():
                    # calculate the optimal multiplier for enhanced convergence
                    mu_ = mu(Ybus, J, f, dV, dx, pvpq, pq)
                else:
                    mu_ = 1.0
            else:
                mu_ = 1.0

            Vm -= mu_ * dVm
            Va -= mu_ * dVa
            V = Vm * np.exp(1j * Va)

            Vm = np.abs(V)  # update Vm and Va again in case
            Va = np.angle(V)  # we wrapped around with a negative Vm

            # evaluate F(x)
            Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)
            Scalc = cf.compute_power(Ybus, V)
            f = cf.compute_fx(Scalc, Sbus, pvpq, pq)
            norm_f = cf.compute_fx_error(f)

            # review reactive power limits
            # it is only worth checking Q limits with a low error
            # since with higher errors, the Q values may be far from realistic
            # finally, the Q control only makes sense if there are pv nodes
            if control_q != ReactivePowerControlMode.NoControl and norm_f < 1e-2 and npv > 0:

                # check and adjust the reactive power
                # this function passes pv buses to pq when the limits are violated,
                # but not pq to pv because that is unstable
                n_changes, Scalc, Sbus, pv, pq, pvpq, messages = control_q_inside_method(Scalc, Sbus, pv, pq,
                                                                                         pvpq, Qmin, Qmax)

                if n_changes > 0:
                    # adjust internal variables to the new pq|pv values
                    npv = len(pv)
                    npq = len(pq)
                    npvpq = npv + npq

                    # recompute the error based on the new Sbus
                    f = cf.compute_fx(Scalc, Sbus, pvpq, pq)
                    norm_f = cf.compute_fx_error(f)

                    # if verbose > 0:
                    #     for sense, idx, var in messages:
                    #         msg = "Bus " + str(idx) + " changed to PQ, limited to " + str(var * 100) + " MVAr"
                    #         logger.add_debug(msg)

            # check convergence
            converged = norm_f < tol

            # check for absurd values
            if np.isnan(V).any() or (Vm == 0).any():
                converged = False
                break

    else:
        norm_f = 0
        converged = True
        Scalc = S0 + I0 * Vm + Y0 * np.power(Vm, 2)  # compute the ZIP power injection

    end = time.time()
    elapsed = end - start

    # return NumericPowerFlowResults(V, converged, norm_f, Scalc, None, None, None, None, None, None, iter_, elapsed)
    return NumericPowerFlowResults(V=V, converged=converged, norm_f=norm_f,
                                   Scalc=Scalc, ma=None, theta=None, Beq=None,
                                   Ybus=None, Yf=None, Yt=None,
                                   iterations=iter_, elapsed=elapsed)
