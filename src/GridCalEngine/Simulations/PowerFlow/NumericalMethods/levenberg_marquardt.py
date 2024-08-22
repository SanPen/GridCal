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
import scipy.sparse as sp
from GridCalEngine.Utils.NumericalMethods.sparse_solve import get_sparse_type, get_linear_solver
from GridCalEngine.Simulations.Derivatives.ac_jacobian import AC_jacobianVc
import GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import control_q_inside_method
from GridCalEngine.basic_structures import Logger
import GridCalEngine.Utils.Sparse.csc2 as csc

linear_solver = get_linear_solver()
sparse = get_sparse_type()
scipy.ALLOW_THREADS = True
np.set_printoptions(precision=8, suppress=True, linewidth=320)


def levenberg_marquardt_pf(Ybus, S0, V0, I0, Y0, pv_, pq_, pqv_, p_, Qmin, Qmax, tol, max_it=50,
                           control_q=False, verbose=False, logger: Logger = None) -> NumericPowerFlowResults:
    """
    Solves the power flow problem by the Levenberg-Marquardt power flow algorithm.
    It is usually better than Newton-Raphson, but it takes an order of magnitude more time to converge.
    @Author: Santiago Peñate Vera
    :param Ybus: Admittance matrix
    :param S0: Array of nodal power Injections (ZIP)
    :param V0: Array of nodal voltages (initial solution)
    :param I0: Array of nodal current Injections (ZIP)
    :param Y0: Array of nodal admittance Injections (ZIP)
    :param pv_: Array with the indices of the PV buses
    :param pq_: Array with the indices of the PQ buses
    :param pqv_: Array with the indices of the PQV buses
    :param p_: Array with the indices of the P buses
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
    pqv = pqv_.copy()
    p = p_.copy()
    blck1_idx = np.r_[pv, pq, p, pqv]
    blck2_idx = np.r_[pq, p]
    blck3_idx = np.r_[pq, pqv]
    n_block1 = len(blck1_idx)
    n_block2 = len(blck2_idx)

    if n_block1 > 0:
        normF = 100000
        update_jacobian = True
        converged = False
        iter_ = 0
        nu = 2.0
        lbmda = 0
        f_prev = 1e9  # very large number
        nn = n_block1 + n_block2
        Idn = sp.diags(np.ones(nn))  # csc_matrix identity
        H: sp.csc_matrix = sp.csc_matrix((0, 0))
        Ht: sp.csc_matrix = sp.csc_matrix((0, 0))
        HtH: sp.csc_matrix = sp.csc_matrix((0, 0))
        Scalc = S0  # is updated later

        if verbose > 1:
            logger.add_debug('LM previous values ' + '-' * 200)
            logger.add_debug('Y (real):\n', Ybus.real.toarray())
            logger.add_debug('Y (imag):\n', Ybus.imag.toarray())
            logger.add_debug('pv:\n', pv)
            logger.add_debug('pq:\n', pq)
            logger.add_debug('Vm:\n', Vm)
            logger.add_debug('Va:\n', Va)

        while not converged and iter_ < max_it:

            if verbose:
                logger.add_debug('LM Iteration {0}'.format(iter_) + '-' * 200)

            # evaluate Jacobian
            if update_jacobian:
                H = csc.mat_to_scipy(AC_jacobianVc(Ybus, V, blck1_idx, blck2_idx, blck3_idx))

                # system matrix
                # H1 = H^t
                Ht = H.transpose()  # .tocsr()

                # H2 = H1·H
                HtH = Ht @ H

            # evaluate the solution error F(x0)
            Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)
            Scalc = cf.compute_power(Ybus, V)
            dz = cf.compute_fx(Scalc, Sbus, blck1_idx, blck3_idx)

            # set first value of lmbda
            if iter_ == 0:
                lbmda = 1e-3 * HtH.diagonal().max()

            # compute system matrix A = H^T·H - lambda·I
            A = (HtH + lbmda * Idn).tocsc()

            # right-hand side
            # H^t·dz
            rhs = Ht.dot(dz)

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
                dVa[blck1_idx] = dx[:n_block1]
                dVm[blck2_idx] = dx[n_block1:]

                # update Vm and Va again in case we wrapped around with a negative Vm
                Vm -= dVm
                Va -= dVa
                V = cf.polar_to_rect(Vm, Va)

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
            Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)
            Scalc = cf.compute_power(Ybus, V)
            e = cf.compute_fx(Scalc, Sbus, blck1_idx, blck3_idx)
            normF = cf.compute_fx_error(e)

            if verbose:
                logger.add_debug('error', normF)

            # review reactive power limits
            # it is only worth checking Q limits with a low error
            # since with higher errors, the Q values may be far from realistic
            # finally, the Q control only makes sense if there are pv nodes
            if control_q and normF < 1e-2 and (len(pv) + len(p)) > 0:

                # check and adjust the reactive power
                # this function passes pv buses to pq when the limits are violated,
                # but not pq to pv because that is unstable
                changed, pv, pq, pqv, p = control_q_inside_method(Scalc, S0, pv, pq, pqv, p, Qmin, Qmax)

                if len(changed) > 0:
                    # adjust internal variables to the new pq|pv values
                    blck1_idx = np.r_[pv, pq, p, pqv]
                    blck2_idx = np.r_[pq, p]
                    blck3_idx = np.r_[pq, pqv]
                    n_block1 = len(blck1_idx)

                    nn = len(blck1_idx) + len(blck2_idx)
                    ii = np.linspace(0, nn - 1, nn)
                    Idn = sparse((np.ones(nn), (ii, ii)), shape=(nn, nn))  # csc_matrix identity

                    # recompute the error based on the new Sbus
                    e = cf.compute_fx(Scalc, Sbus, blck1_idx, blck3_idx)
                    normF = cf.compute_fx_error(e)

            converged = normF < tol
            f_prev = f

            # update iteration counter
            iter_ += 1
    else:
        normF = 0
        converged = True
        Scalc = cf.compute_zip_power(S0, I0, Y0, Vm)  # compute the ZIP power injection
        iter_ = 0

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V=V, converged=converged, norm_f=normF,
                                   Scalc=Scalc, m=None, tau=None, Beq=None,
                                   Ybus=None, Yf=None, Yt=None,
                                   iterations=iter_, elapsed=elapsed)

