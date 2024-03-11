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
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults

linear_solver = get_linear_solver()
sparse = get_sparse_type()
scipy.ALLOW_THREADS = True
np.set_printoptions(precision=8, suppress=True, linewidth=320)


def F(V, Ybus, S, I, pq, pvpq):
    """

    :param V:
    :param Ybus:
    :param S:
    :param I:
    :param pq:
    :param pvpq:
    :return:
    """
    # compute the mismatch function f(x_new)
    dS = V * np.conj(Ybus * V - I) - S  # complex power mismatch
    return np.r_[dS[pvpq].real, dS[pq].imag]  # concatenate to form the mismatch function


def compute_fx(x, Ybus, S, I, pq, pv, pvpq, j1, j2, j3, j4, j5, j6, Va, Vm):
    """

    :param x:
    :param Ybus:
    :param S:
    :param I:
    :param pq:
    :param pv:
    :param pvpq:
    :param j1:
    :param j2:
    :param j3:
    :param j4:
    :param j5:
    :param j6:
    :param Va:
    :param Vm:
    :return:
    """
    n = len(S)
    npv = len(pv)
    npq = len(pq)

    # reassign the solution vector
    if npv:
        Va[pv] = x[j1:j2]
    if npq:
        Va[pq] = x[j3:j4]
        Vm[pq] = x[j5:j6]

    V = Vm * np.exp(1j * Va)  # voltage mismatch

    # right hand side
    g = F(V, Ybus, S, I, pq, pvpq)

    # jacobian
    gx = AC_jacobian(Ybus, V, pvpq, pq)

    # return the increment of x
    return linear_solver(gx, g)


def ContinuousNR(Ybus, Sbus, V0, Ibus, pv, pq, tol, max_it=15) -> NumericPowerFlowResults:
    """
    Solves the power flow using a full Newton's method with the backtrack improvement algorithm
    Args:
        Ybus: Admittance matrix
        Sbus: Array of nodal power Injections
        V0: Array of nodal voltages (initial solution)
        Ibus: Array of nodal current Injections
        pv: Array with the indices of the PV buses
        pq: Array with the indices of the PQ buses
        tol: Tolerance
        max_it: Maximum number of iterations
    Returns:
        Voltage solution, converged?, error, calculated power Injections

    @author: Ray Zimmerman (PSERC Cornell)
    @Author: Santiago Penate Vera
    """

    start = time.time()

    # initialize
    converged = 0
    iter_ = 0
    V = V0.copy()

    # set up indexing for updating V
    pvpq = np.r_[pv, pq]
    npv = len(pv)
    npq = len(pq)

    # j1:j2 - V angle of pv buses
    j1 = 0
    j2 = npv
    # j3:j4 - V angle of pq buses
    j3 = j2
    j4 = j2 + npq
    # j5:j6 - V mag of pq buses
    j5 = j4
    j6 = j4 + npq

    # evaluate F(x0)
    Scalc = V * np.conj(Ybus * V - Ibus)
    mis = Scalc - Sbus  # compute the mismatch
    fx = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]

    # check tolerance
    normF = np.linalg.norm(fx, np.Inf)
    converged = normF < tol
    dt = 1.0

    # Compose x
    x = np.zeros(2 * npq + npv)
    Va = np.angle(V)
    Vm = np.abs(V)

    # do Newton iterations
    while not converged and iter_ < max_it:
        # update iteration counter
        iter_ += 1

        x[j1:j4] = Va[pvpq]
        x[j5:j6] = Vm[pq]

        # Compute the Runge-Kutta steps
        k1 = compute_fx(x,
                        Ybus, Sbus, Ibus, pq, pv, pvpq, j1, j2, j3, j4, j5, j6, Va, Vm)

        k2 = compute_fx(x + 0.5 * dt * k1,
                        Ybus, Sbus, Ibus, pq, pv, pvpq, j1, j2, j3, j4, j5, j6, Va, Vm)

        k3 = compute_fx(x + 0.5 * dt * k2,
                        Ybus, Sbus, Ibus, pq, pv, pvpq, j1, j2, j3, j4, j5, j6, Va, Vm)

        k4 = compute_fx(x + dt * k3,
                        Ybus, Sbus, Ibus, pq, pv, pvpq, j1, j2, j3, j4, j5, j6, Va, Vm)

        x -= dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0

        # reassign the solution vector
        Va[pvpq] = x[j1:j4]
        Vm[pq] = x[j5:j6]
        V = Vm * np.exp(1j * Va)  # voltage mismatch

        # evaluate F(x)
        Scalc = V * np.conj(Ybus * V - Ibus)
        mis = Scalc - Sbus  # complex power mismatch
        fx = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again

        # check for convergence
        normF = np.linalg.norm(fx, np.Inf)

        if normF > 0.01:
            dt = max(dt * 0.985, 0.75)
        else:
            dt = min(dt * 1.015, 0.75)

        print(dt)
        converged = normF < tol

    end = time.time()
    elapsed = end - start

    # return NumericPowerFlowResults(V, converged, normF, Scalc, None, None, None, None, None, None, iter_, elapsed)
    return NumericPowerFlowResults(V=V, converged=converged, norm_f=normF,
                                   Scalc=Scalc, ma=None, theta=None, Beq=None,
                                   Ybus=None, Yf=None, Yt=None,
                                   iterations=iter_, elapsed=elapsed)
