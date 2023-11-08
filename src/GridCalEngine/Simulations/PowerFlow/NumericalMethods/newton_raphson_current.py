# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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

from GridCalEngine.Simulations.sparse_solve import get_sparse_type, get_linear_solver
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults

linear_solver = get_linear_solver()
sparse = get_sparse_type()
scipy.ALLOW_THREADS = True
np.set_printoptions(precision=8, suppress=True, linewidth=320)


def Jacobian_I(Ybus, V, pq, pvpq):
    """
    Computes the system Jacobian matrix
    Args:
        Ybus: Admittance matrix
        V: Array of nodal voltages
        pq: Array with the indices of the PQ buses
        pvpq: Array with the indices of the PV and PQ buses

    Returns:
        The system Jacobian matrix in current equations
    """
    dI_dVm = Ybus * sp.diags(V / np.abs(V))
    dI_dVa = 1j * (Ybus * sp.diags(V))

    J11 = dI_dVa[np.array([pvpq]).T, pvpq].real
    J12 = dI_dVm[np.array([pvpq]).T, pq].real
    J21 = dI_dVa[np.array([pq]).T, pvpq].imag
    J22 = dI_dVm[np.array([pq]).T, pq].imag

    J = sp.vstack([sp.hstack([J11, J12]),
                   sp.hstack([J21, J22])], format="csr")

    return J


def NR_I_LS(Ybus, Sbus_sp, V0, Ibus_sp, pv, pq, tol, max_it=15, acceleration_parameter=0.5) -> NumericPowerFlowResults:
    """
    Solves the power flow using a full Newton's method in current equations with current mismatch with line search
    Args:
        Ybus: Admittance matrix
        Sbus_sp: Array of nodal specified power Injections
        V0: Array of nodal voltages (initial solution)
        Ibus_sp: Array of nodal specified current Injections
        pv: Array with the indices of the PV buses
        pq: Array with the indices of the PQ buses
        tol: Tolerance
        max_it: Maximum number of iterations
        acceleration_parameter: value used to correct bad iterations
    Returns:
        Voltage solution, converged?, error, calculated power Injections

    @Author: Santiago Penate Vera
    """
    start = time.time()

    # initialize
    back_track_counter = 0
    back_track_iterations = 0
    alpha = 1e-4
    converged = 0
    iter_ = 0
    V = V0
    Va = np.angle(V)
    Vm = np.abs(V)
    dVa = np.zeros_like(Va)
    dVm = np.zeros_like(Vm)

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
    Icalc = Ybus * V - Ibus_sp
    dI = np.conj(Sbus_sp / V) - Icalc  # compute the mismatch
    F = np.r_[dI[pvpq].real, dI[pq].imag]
    normF = np.linalg.norm(F, np.Inf)  # check tolerance

    converged = normF < tol

    # do Newton iterations
    while not converged and iter_ < max_it:
        # update iteration counter
        iter_ += 1

        # evaluate Jacobian
        J = Jacobian_I(Ybus, V, pq, pvpq)

        # compute update step
        dx = linear_solver(J, F)

        # reassign the solution vector
        dVa[pvpq] = dx[j1:j4]
        dVm[pq] = dx[j5:j6]

        # update voltage the Newton way (mu=1)
        mu_ = 1.0
        Vm += mu_ * dVm
        Va += mu_ * dVa
        Vnew = Vm * np.exp(1j * Va)

        # compute the mismatch function f(x_new)
        Icalc = Ybus * Vnew - Ibus_sp
        dI = np.conj(Sbus_sp / Vnew) - Icalc
        Fnew = np.r_[dI[pvpq].real, dI[pq].imag]

        normFnew = np.linalg.norm(Fnew, np.Inf)

        cond = normF < normFnew  # condition to back track (no improvement at all)

        if not cond:
            back_track_counter += 1

        l_iter = 0
        while cond and l_iter < max_it and mu_ > tol:
            # line search back

            # reset voltage
            Va = np.angle(V)
            Vm = np.abs(V)

            # update voltage with a closer value to the last value in the Jacobian direction
            mu_ *= acceleration_parameter
            Vm -= mu_ * dVm
            Va -= mu_ * dVa
            Vnew = Vm * np.exp(1j * Va)

            # compute the mismatch function f(x_new)
            Icalc = Ybus * Vnew - Ibus_sp
            dI = np.conj(Sbus_sp / Vnew) - Icalc
            Fnew = np.r_[dI[pvpq].real, dI[pq].imag]

            normFnew = np.linalg.norm(Fnew, np.Inf)
            cond = normF < normFnew

            l_iter += 1
            back_track_iterations += 1

        # update calculation variables
        V = Vnew
        F = Fnew

        # check for convergence
        normF = normFnew

        converged = normF < tol

    end = time.time()
    elapsed = end - start

    Scalc = V * np.conj(Icalc)

    # return NumericPowerFlowResults(V, converged, normF, Scalc, None, None, None, None, None, None, iter_, elapsed)
    return NumericPowerFlowResults(V=V, converged=converged, norm_f=normF,
                                   Scalc=Scalc, ma=None, theta=None, Beq=None,
                                   Ybus=None, Yf=None, Yt=None,
                                   iterations=iter_, elapsed=elapsed)
