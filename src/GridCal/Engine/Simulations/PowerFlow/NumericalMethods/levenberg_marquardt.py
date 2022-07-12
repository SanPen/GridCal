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

from GridCal.Engine.Simulations.sparse_solve import get_sparse_type, get_linear_solver
from GridCal.Engine.Simulations.PowerFlow.NumericalMethods.ac_jacobian import AC_jacobian
from GridCal.Engine.Simulations.PowerFlow.NumericalMethods.common_functions import *
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCal.Engine.basic_structures import ReactivePowerControlMode
from GridCal.Engine.Simulations.PowerFlow.NumericalMethods.discrete_controls import control_q_inside_method
from GridCal.Engine.basic_structures import Logger

linear_solver = get_linear_solver()
sparse = get_sparse_type()
scipy.ALLOW_THREADS = True
np.set_printoptions(precision=8, suppress=True, linewidth=320)


def levenberg_marquardt_pf(Ybus, S0, V0, I0, Y0, pv_, pq_, Qmin, Qmax, tol, max_it=50,
                           control_q=ReactivePowerControlMode.NoControl,
                           verbose=False, logger: Logger = None) -> NumericPowerFlowResults:
    """
    Solves the power flow problem by the Levenberg-Marquardt power flow algorithm.
    It is usually better than Newton-Raphson, but it takes an order of magnitude more time to converge.
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
    :param control_q: Type of reactive power control
    :param verbose: Display console information
    :param logger: Logger instance
    :return: NumericPowerFlowResults instance
    """
    start = time.time()

    # initialize
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
    npvpq = npq + npv

    if npvpq > 0:
        normF = 100000
        update_jacobian = True
        converged = False
        iter_ = 0
        nu = 2.0
        lbmda = 0
        f_prev = 1e9  # very large number
        nn = 2 * npq + npv
        Idn = sp.diags(np.ones(nn))  # csc_matrix identity
        H: sp.csc_matrix = sp.csc_matrix((0, 0))
        H1: sp.csc_matrix = sp.csc_matrix((0, 0))
        H2: sp.csc_matrix = sp.csc_matrix((0, 0))
        Scalc = S0  # is updated later

        if verbose > 1:
            logger.add_debug('LM previous values ' + '-' * 200)
            logger.add_debug('Y (real):\n', Ybus.real.toarray())
            logger.add_debug('Y (imag):\n', Ybus.imag.toarray())
            logger.add_debug('pvpq:\n', pvpq)
            logger.add_debug('pq:\n', pq)
            logger.add_debug('Vm:\n', Vm)
            logger.add_debug('Va:\n', Va)

        while not converged and iter_ < max_it:

            if verbose:
                logger.add_debug('LM Iteration {0}'.format(iter_) + '-' * 200)

            # evaluate Jacobian
            if update_jacobian:
                H = AC_jacobian(Ybus, V, pvpq, pq, npv, npq)

                # system matrix
                # H1 = H^t
                H1 = H.transpose()  # .tocsr()

                # H2 = H1·H
                H2 = H1.dot(H)

            # evaluate the solution error F(x0)
            Sbus = compute_zip_power(S0, I0, Y0, Vm)
            Scalc = compute_power(Ybus, V)
            dz = compute_fx(Scalc, Sbus, pvpq, pq)

            # set first value of lmbda
            if iter_ == 0:
                lbmda = 1e-3 * H2.diagonal().max()

            # compute system matrix A = H^T·H - lambda·I
            A = H2 + lbmda * Idn

            # right-hand side
            # H^t·dz
            rhs = H1.dot(dz)

            # Solve the increment
            dx = linear_solver(A, rhs)

            # objective function to minimize
            f = 0.5 * dz.dot(dz)

            # decision function
            val = dx.dot(lbmda * dx + rhs)
            if val > 0.0:
                rho = (f_prev - f) / (0.5 * val)
            else:
                rho = -1.0

            if verbose > 1:
                logger.add_debug('rho:', rho)

            # lambda update
            if rho >= 0:
                update_jacobian = True
                lbmda *= max([1.0 / 3.0, 1 - (2 * rho - 1) ** 3])
                nu = 2.0

                # reassign the solution vector
                dVa[pvpq] = dx[:npvpq]
                dVm[pq] = dx[npvpq:]

                # update Vm and Va again in case we wrapped around with a negative Vm
                Vm -= dVm
                Va -= dVa
                V = polar_to_rect(Vm, Va)

                if verbose > 1:
                    logger.add_debug('J:\n', H.toarray())
                    logger.add_debug('f:\n', rhs)
                    logger.add_debug('Vm:\n', Vm)
                    logger.add_debug('Va:\n', Va)

            else:
                update_jacobian = False
                lbmda *= nu
                nu *= 2.0

            # check convergence
            Sbus = compute_zip_power(S0, I0, Y0, Vm)
            Scalc = compute_power(Ybus, V)
            e = compute_fx(Scalc, Sbus, pvpq, pq)
            normF = compute_fx_error(e)

            if verbose:
                logger.add_debug('error', normF)

            # review reactive power limits
            # it is only worth checking Q limits with a low error
            # since with higher errors, the Q values may be far from realistic
            # finally, the Q control only makes sense if there are pv nodes
            if control_q != ReactivePowerControlMode.NoControl and normF < 1e-2 and npv > 0:

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
                    pvpq_lookup = np.zeros(Ybus.shape[0], dtype=int)
                    pvpq_lookup[pvpq] = np.arange(npvpq)

                    nn = 2 * npq + npv
                    ii = np.linspace(0, nn - 1, nn)
                    Idn = sparse((np.ones(nn), (ii, ii)), shape=(nn, nn))  # csc_matrix identity

                    # recompute the error based on the new Sbus
                    e = compute_fx(Scalc, Sbus, pvpq, pq)
                    normF = compute_fx_error(e)

                    if verbose > 0:
                        for sense, idx, var in messages:
                            msg = "Bus " + str(idx) + " changed to PQ, limited to " + str(var * 100) + " MVAr"
                            logger.add_debug(msg)

            converged = normF < tol
            f_prev = f

            # update iteration counter
            iter_ += 1
    else:
        normF = 0
        converged = True
        Scalc = compute_zip_power(S0, I0, Y0, Vm)  # compute the ZIP power injection
        iter_ = 0

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V, converged, normF, Scalc, None, None, None, None, None, None, iter_, elapsed)

