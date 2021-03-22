# Copyright (c) 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE_MATPOWER file.

# Copyright 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

# Copyright (c) 2016-2017 by University of Kassel and Fraunhofer Institute for Wind Energy and
# Energy System Technology (IWES), Kassel. All rights reserved. Use of this source code is governed
# by a BSD-style license that can be found in the LICENSE file.

# The file has been modified from Pypower.
# The function mu() has been added to the solver in order to provide an optimal iteration control
#
# Copyright (c) 2018 Santiago Peñate Vera
#
# This file retains the BSD-Style license

import time
import scipy
import scipy.sparse as sp
import numpy as np

from GridCal.Engine.Simulations.sparse_solve import get_sparse_type, get_linear_solver
from GridCal.Engine.Simulations.PowerFlow.numba_functions import calc_power_csr_numba, diag
from GridCal.Engine.Simulations.PowerFlow.high_speed_jacobian import AC_jacobian
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCal.Engine.basic_structures import ReactivePowerControlMode
from GridCal.Engine.Simulations.PowerFlow.discrete_controls import control_q_inside_method

linear_solver = get_linear_solver()
sparse = get_sparse_type()
scipy.ALLOW_THREADS = True
np.set_printoptions(precision=8, suppress=True, linewidth=320)


def dSbus_dV(Ybus, V, I):
    """
    Computes partial derivatives of power injection w.r.t. voltage.
    :param Ybus: Admittance matrix
    :param V: Bus voltages array
    :param I: Bus current injections array
    :return:
    """
    '''
    Computes partial derivatives of power injection w.r.t. voltage.

    Returns two matrices containing partial derivatives of the complex bus
    power injections w.r.t voltage magnitude and voltage angle respectively
    (for all buses). If C{Ybus} is a sparse matrix, the return values will be
    also. The following explains the expressions used to form the matrices::

        Ibus = Ybus * V - I

        S = diag(V) * conj(Ibus) = diag(conj(Ibus)) * V

    Partials of V & Ibus w.r.t. voltage magnitudes::
        dV/dVm = diag(V / abs(V))
        dI/dVm = Ybus * dV/dVm = Ybus * diag(V / abs(V))

    Partials of V & Ibus w.r.t. voltage angles::
        dV/dVa = j * diag(V)
        dI/dVa = Ybus * dV/dVa = Ybus * j * diag(V)

    Partials of S w.r.t. voltage magnitudes::
        dS/dVm = diag(V) * conj(dI/dVm) + diag(conj(Ibus)) * dV/dVm
               = diag(V) * conj(Ybus * diag(V / abs(V)))
                                        + conj(diag(Ibus)) * diag(V / abs(V))

    Partials of S w.r.t. voltage angles::
        dS/dVa = diag(V) * conj(dI/dVa) + diag(conj(Ibus)) * dV/dVa
               = diag(V) * conj(Ybus * j * diag(V))
                                        + conj(diag(Ibus)) * j * diag(V)
               = -j * diag(V) * conj(Ybus * diag(V))
                                        + conj(diag(Ibus)) * j * diag(V)
               = j * diag(V) * conj(diag(Ibus) - Ybus * diag(V))

    For more details on the derivations behind the derivative code used
    in PYPOWER information, see:

    [TN2]  R. D. Zimmerman, "AC Power Flows, Generalized OPF Costs and
    their Derivatives using Complex Matrix Notation", MATPOWER
    Technical Note 2, February 2010.
    U{http://www.pserc.cornell.edu/matpower/TN2-OPF-Derivatives.pdf}

    @author: Ray Zimmerman (PSERC Cornell)
    '''

    ib = range(len(V))

    Ibus = Ybus * V - I
    diagV = sparse((V, (ib, ib)))
    diagIbus = sparse((Ibus, (ib, ib)))
    diagVnorm = sparse((V / np.abs(V), (ib, ib)))

    dS_dVm = diagV * np.conj(Ybus * diagVnorm) + np.conj(diagIbus) * diagVnorm
    dS_dVa = 1.0j * diagV * np.conj(diagIbus - Ybus * diagV)

    return dS_dVm, dS_dVa


def mu(Ybus, Ibus, J, pvpq_lookup, incS, dV, dx, pvpq, pq, npv, npq):
    """
    Calculate the Iwamoto acceleration parameter as described in:
    "A Load Flow Calculation Method for Ill-Conditioned Power Systems" by Iwamoto, S. and Tamura, Y."
    Args:
        Ybus: Admittance matrix
        J: Jacobian matrix
        incS: mismatch vector
        dV: voltage increment (in complex form)
        dx: solution vector as calculated dx = solve(J, incS)
        pvpq: array of the pq and pv indices
        pq: array of the pq indices

    Returns:
        the Iwamoto's optimal multiplier for ill conditioned systems
    """
    # evaluate the Jacobian of the voltage derivative
    # theoretically this is the second derivative matrix
    # since the Jacobian (J2) has been calculated with dV instead of V

    # generate lookup pvpq -> index pvpq (used in createJ)
    # pvpq_lookup = np.zeros(np.max(Ybus.indices) + 1, dtype=int)
    # pvpq_lookup[pvpq] = np.arange(len(pvpq))

    J2 = AC_jacobian(Ybus, dV, pvpq, pq, pvpq_lookup, npv, npq)
    # J2 = Jacobian(Ybus, dV, Ibus, pq, pvpq)

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


def Jacobian(Ybus, V, Ibus, pq, pvpq):
    """
    Computes the system Jacobian matrix in polar coordinates
    Args:
        Ybus: Admittance matrix
        V: Array of nodal voltages
        Ibus: Array of nodal current injections
        pq: Array with the indices of the PQ buses
        pvpq: Array with the indices of the PV and PQ buses

    Returns:
        The system Jacobian matrix
    """
    I = Ybus * V - Ibus

    diagV = sp.diags(V)
    diagI = sp.diags(I)
    diagVnorm = sp.diags(V / np.abs(V))

    dS_dVm = diagV * np.conj(Ybus * diagVnorm) + np.conj(diagI) * diagVnorm
    dS_dVa = 1.0j * diagV * np.conj(diagI - Ybus * diagV)

    J = sp.vstack([sp.hstack([dS_dVa[np.ix_(pvpq, pvpq)].real, dS_dVm[np.ix_(pvpq, pq)].real]),
                   sp.hstack([dS_dVa[np.ix_(pq, pvpq)].imag,   dS_dVm[np.ix_(pq, pq)].imag])], format="csc")

    return sparse(J)


def Jacobian_cartesian(Ybus, V, Ibus, pq, pvpq):
    """
    Computes the system Jacobian matrix in cartesian coordinates
    Args:
        Ybus: Admittance matrix
        V: Array of nodal voltages
        Ibus: Array of nodal current injections
        pq: Array with the indices of the PQ buses
        pvpq: Array with the indices of the PV and PQ buses

    Returns:
        The system Jacobian matrix in cartesian coordinates
    """
    I = Ybus * V - Ibus

    diagV = sp.diags(V)
    diagI = sp.diags(I)
    VY = diagV * np.conj(Ybus)

    dS_dVr = np.conj(diagI) + VY  # dSbus / dVr
    dS_dVi = 1j * (np.conj(diagI) - VY)  # dSbus / dVi

    '''
    j11 = real(dSbus_dVr([pq; pv], pq));    j12 = real(dSbus_dVi([pq; pv], [pv; pq]));
    
    j21 = imag(dSbus_dVr(pq, pq));          j22 = imag(dSbus_dVi(pq, [pv; pq]));
    

    J = [   j11 j12;
            j21 j22;    ];
    '''

    J = sp.vstack([sp.hstack([dS_dVr[np.ix_(pvpq, pq)].real, dS_dVi[np.ix_(pvpq, pvpq)].real]),
                   sp.hstack([dS_dVr[np.ix_(pq, pq)].imag,   dS_dVi[np.ix_(pq, pvpq)].imag])], format="csc")

    return sparse(J)


def Jacobian_decoupled(Ybus, V, Ibus, pq, pvpq):
    """
    Computes the decoupled Jacobian matrices
    Args:
        Ybus: Admittance matrix
        V: Array of nodal voltages
        Ibus: Array of nodal current injections
        pq: Array with the indices of the PQ buses
        pvpq: Array with the indices of the PV and PQ buses

    Returns: J11, J22
    """
    I = Ybus * V - Ibus

    diagV = sp.diags(V)
    diagI = sp.diags(I)
    diagVnorm = sp.diags(V / np.abs(V))

    dS_dVm = diagV * np.conj(Ybus * diagVnorm) + np.conj(diagI) * diagVnorm
    dS_dVa = 1.0j * diagV * np.conj(diagI - Ybus * diagV)

    J11 = dS_dVa[np.ix_(pvpq, pvpq)].real
    J22 = dS_dVm[np.ix_(pq, pq)].imag

    return J11, J22


def calc_power(V, Ybus, Ibus):
    """
    Compute the power from a voltage solution
    :param V: Voltages Vector
    :param Ybus: Admittance Matrix
    :param Ibus: Currents vector
    :return: Power injections
    """
    # S = V * np.conj(Ybus * V - Ibus)
    # Y = Ybus.tocsr()
    # return S
    return calc_power_csr_numba(n=V.shape[0], Yp=Ybus.indptr, Yj=Ybus.indices, Yx=Ybus.data, V=V, I=Ibus, n_par=500)


def NR_LS(Ybus, Sbus_, V0, Ibus, pv_, pq_, Qmin, Qmax, tol, max_it=15, mu_0=1.0,
          acceleration_parameter=0.05, error_registry=None,
          control_q=ReactivePowerControlMode.NoControl) -> NumericPowerFlowResults:
    """
    Solves the power flow using a full Newton's method with backtrack correction.
    @Author: Santiago Peñate Vera
    :param Ybus: Admittance matrix
    :param Sbus: Array of nodal power injections
    :param V0: Array of nodal voltages (initial solution)
    :param Ibus: Array of nodal current injections
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
    Sbus = Sbus_.copy()
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

    # j1 = 0
    # j2 = npv + npq  # j1:j2 - V angle of pv and pq buses
    # j3 = j2 + npq  # j2:j3 - V mag of pq buses

    if npvpq > 0:

        # generate lookup pvpq -> index pvpq (used in createJ)
        pvpq_lookup = np.zeros(np.max(Ybus.indices) + 1, dtype=int)
        pvpq_lookup[pvpq] = np.arange(npvpq)

        # evaluate F(x0)
        Scalc = V * np.conj(Ybus * V - Ibus)
        dS = Scalc - Sbus  # compute the mismatch
        f = np.r_[dS[pvpq].real, dS[pq].imag]
        norm_f = np.linalg.norm(f, np.inf)
        converged = norm_f < tol

        if error_registry is not None:
            error_registry.append(norm_f)

        # to be able to compare
        Ybus.sort_indices()

        # do Newton iterations
        while not converged and iter_ < max_it:
            # update iteration counter
            iter_ += 1

            # evaluate Jacobian
            # J = Jacobian(Ybus, V, Ibus, pq, pvpq)
            J = AC_jacobian(Ybus, V, pvpq, pq, pvpq_lookup, npv, npq)

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
                Scalc = V * np.conj(Ybus * V - Ibus)
                dS = Scalc - Sbus  # complex power mismatch
                f = np.r_[dS[pvpq].real, dS[pq].imag]  # concatenate to form the mismatch function
                norm_f_new = np.linalg.norm(f, np.inf)

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
                return NumericPowerFlowResults(V, converged, norm_f_new, Scalc, None, None, None, iter_, elapsed)
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
                n_changes, Scalc, Sbus, pv, pq, pvpq = control_q_inside_method(Scalc, Sbus, pv, pq, pvpq, Qmin, Qmax)

                if n_changes > 0:

                    # adjust internal variables to the new pq|pv values
                    npv = len(pv)
                    npq = len(pq)
                    npvpq = npv + npq
                    pvpq_lookup = np.zeros(np.max(Ybus.indices) + 1, dtype=int)
                    pvpq_lookup[pvpq] = np.arange(npvpq)

                    # recompute the error based on the new Sbus
                    dS = Scalc - Sbus  # complex power mismatch
                    f = np.r_[dS[pvpq].real, dS[pq].imag]  # concatenate to form the mismatch function
                    norm_f = np.linalg.norm(f, np.inf)

            if error_registry is not None:
                error_registry.append(norm_f)

            converged = norm_f < tol

    else:
        norm_f = 0
        converged = True
        Scalc = Sbus

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V, converged, norm_f, Scalc, None, None, None, iter_, elapsed)


def NRD_LS(Ybus, Sbus, V0, Ibus, pv, pq, tol, max_it=15,
           acceleration_parameter=0.5, error_registry=None) -> NumericPowerFlowResults:
    """
    Solves the power flow using a full Newton's method with backtrack correction.
    @Author: Santiago Peñate Vera
    :param Ybus: Admittance matrix
    :param Sbus: Array of nodal power injections
    :param V0: Array of nodal voltages (initial solution)
    :param Ibus: Array of nodal current injections
    :param pv: Array with the indices of the PV buses
    :param pq: Array with the indices of the PQ buses
    :param tol: Tolerance
    :param max_it: Maximum number of iterations
    :param acceleration_parameter: parameter used to correct the "bad" iterations, typically 0.5
    :param error_registry: list to store the error for plotting
    :return: Voltage solution, converged?, error, calculated power injections
    """

    start = time.time()

    use_norm_error = True

    # initialize
    back_track_counter = 0
    back_track_iterations = 0
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

    # evaluate F(x0)
    Scalc = V * np.conj(Ybus * V - Ibus)
    dS = Scalc - Sbus  # compute the mismatch
    f = np.r_[dS[pvpq].real, dS[pq].imag]

    # check tolerance
    if use_norm_error:
        norm_f = np.linalg.norm(f, np.Inf)
    else:
        norm_f = 0.5 * f.dot(f)

    if error_registry is not None:
        error_registry.append(norm_f)

    if norm_f < tol:
        converged = 1

    # do Newton iterations
    while not converged and iter_ < max_it:
        # update iteration counter
        iter_ += 1

        # evaluate Jacobian
        J1, J4 = Jacobian_decoupled(Ybus, V, Ibus, pq, pvpq)

        # compute update step and reassign the solution vector
        dVa[pvpq] = linear_solver(J1, f[pvpq])
        dVm[pq] = linear_solver(J4, f[pq])

        # update voltage the Newton way (mu=1)
        mu_ = 1.0
        Vm -= mu_ * dVm
        Va -= mu_ * dVa
        Vnew = Vm * np.exp(1.0j * Va)

        # compute the mismatch function f(x_new)
        dS = Vnew * np.conj(Ybus * Vnew - Ibus) - Sbus  # complex power mismatch
        f_new = np.r_[dS[pvpq].real, dS[pq].imag]  # concatenate to form the mismatch function

        if use_norm_error:
            norm_f_new = np.linalg.norm(f_new, np.Inf)
        else:
            norm_f_new = 0.5 * f_new.dot(f_new)

        if error_registry is not None:
            error_registry.append(norm_f_new)

        cond = norm_f_new > norm_f  # condition to back track (no improvement at all)

        if not cond:
            back_track_counter += 1

        l_iter = 0
        while not cond and l_iter < 10 and mu_ > 0.01:
            # line search back
            # update voltage with a closer value to the last value in the Jacobian direction
            mu_ *= acceleration_parameter
            Vm -= mu_ * dVm
            Va -= mu_ * dVa
            Vnew = Vm * np.exp(1.0j * Va)

            # compute the mismatch function f(x_new)
            dS = Vnew * np.conj(Ybus * Vnew - Ibus) - Sbus  # complex power mismatch
            f_new = np.r_[dS[pvpq].real, dS[pq].imag]  # concatenate to form the mismatch function

            if use_norm_error:
                norm_f_new = np.linalg.norm(f_new, np.Inf)
            else:
                norm_f_new = 0.5 * f_new.dot(f_new)

            cond = norm_f_new > norm_f

            if error_registry is not None:
                error_registry.append(norm_f_new)

            l_iter += 1
            back_track_iterations += 1

        # update calculation variables
        V = Vnew
        f = f_new

        # check for convergence
        if use_norm_error:
            norm_f = np.linalg.norm(f_new, np.Inf)
        else:
            norm_f = 0.5 * f_new.dot(f_new)

        if error_registry is not None:
            error_registry.append(norm_f)

        if norm_f < tol:
            converged = 1

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V, converged, norm_f, Scalc, None, None, None, iter_, elapsed)


def IwamotoNR(Ybus, Sbus_, V0, Ibus, pv_, pq_, Qmin, Qmax, tol, max_it=15,
              control_q=ReactivePowerControlMode.NoControl, robust=False) -> NumericPowerFlowResults:
    """
    Solves the power flow using a full Newton's method with the Iwamoto optimal step factor.
    Args:
        Ybus: Admittance matrix
        Sbus_: Array of nodal power injections
        V0: Array of nodal voltages (initial solution)
        Ibus: Array of nodal current injections
        pv_: Array with the indices of the PV buses
        pq_: Array with the indices of the PQ buses
        tol: Tolerance
        max_it: Maximum number of iterations
        robust: use of the Iwamoto optimal step factor?.
    Returns:
        Voltage solution, converged?, error, calculated power injections

    @Author: Santiago Penate Vera
    """
    start = time.time()

    # initialize
    Sbus = Sbus_.copy()
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

        # generate lookup pvpq -> index pvpq (used in createJ)
        pvpq_lookup = np.zeros(np.max(Ybus.indices) + 1, dtype=int)
        pvpq_lookup[pvpq] = np.arange(len(pvpq))

        # evaluate F(x0)
        Scalc = V * np.conj(Ybus * V - Ibus)
        mis = Scalc - Sbus  # compute the mismatch
        f = np.r_[mis[pvpq].real, mis[pq].imag]

        # check tolerance
        norm_f = np.linalg.norm(f, np.Inf)
        converged = norm_f < tol

        # do Newton iterations
        while not converged and iter_ < max_it:
            # update iteration counter
            iter_ += 1

            # evaluate Jacobian
            # J = Jacobian(Ybus, V, Ibus, pq, pvpq)
            J = AC_jacobian(Ybus, V, pvpq, pq, pvpq_lookup, npv, npq)

            # compute update step
            try:
                dx = linear_solver(J, f)
            except:
                print(J)
                converged = False
                iter_ = max_it + 1  # exit condition
                end = time.time()
                elapsed = end - start
                return NumericPowerFlowResults(V, converged, norm_f, Scalc, None, None, None, iter_, elapsed)

            # assign the solution vector
            dVa[pvpq] = dx[:npvpq]
            dVm[pq] = dx[npvpq:]
            dV = dVm * np.exp(1j * dVa)  # voltage mismatch

            # update voltage
            if robust:
                # if dV contains zeros will crash the second Jacobian derivative
                if not (dV == 0.0).any():
                    # calculate the optimal multiplier for enhanced convergence
                    mu_ = mu(Ybus, Ibus, J, pvpq_lookup, f, dV, dx, pvpq, pq, npv, npq)
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
            Scalc = V * np.conj(Ybus * V - Ibus)
            mis = Scalc - Sbus  # complex power mismatch
            f = np.r_[mis[pvpq].real, mis[pq].imag]  # concatenate again

            # check for convergence
            norm_f = np.linalg.norm(f, np.Inf)

            # review reactive power limits
            # it is only worth checking Q limits with a low error
            # since with higher errors, the Q values may be far from realistic
            # finally, the Q control only makes sense if there are pv nodes
            if control_q != ReactivePowerControlMode.NoControl and norm_f < 1e-2 and npv > 0:

                # check and adjust the reactive power
                # this function passes pv buses to pq when the limits are violated,
                # but not pq to pv because that is unstable
                n_changes, Scalc, Sbus, pv, pq, pvpq = control_q_inside_method(Scalc, Sbus, pv, pq, pvpq, Qmin, Qmax)

                if n_changes > 0:
                    # adjust internal variables to the new pq|pv values
                    npv = len(pv)
                    npq = len(pq)
                    npvpq = npv + npq
                    pvpq_lookup = np.zeros(np.max(Ybus.indices) + 1, dtype=int)
                    pvpq_lookup[pvpq] = np.arange(npvpq)

                    # recompute the error based on the new Sbus
                    dS = Scalc - Sbus  # complex power mismatch
                    f = np.r_[dS[pvpq].real, dS[pq].imag]  # concatenate to form the mismatch function
                    norm_f = np.linalg.norm(f, np.inf)

            # check convergence
            converged = norm_f < tol

    else:
        norm_f = 0
        converged = True
        Scalc = Sbus

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V, converged, norm_f, Scalc, None, None, None, iter_, elapsed)


def levenberg_marquardt_pf(Ybus, Sbus_, V0, Ibus, pv_, pq_, Qmin, Qmax, tol, max_it=50,
                           control_q=ReactivePowerControlMode.NoControl) -> NumericPowerFlowResults:
    """
    Solves the power flow problem by the Levenberg-Marquardt power flow algorithm.
    It is usually better than Newton-Raphson, but it takes an order of magnitude more time to converge.
    Args:
        Ybus: Admittance matrix
        Sbus_: Array of nodal power injections
        V0: Array of nodal voltages (initial solution)
        Ibus: Array of nodal current injections
        pv_: Array with the indices of the PV buses
        pq_: Array with the indices of the PQ buses
        Qmin:
        Qmax:
        tol: Tolerance
        max_it: Maximum number of iterations
        control_q: Type of reactive power control
    Returns:
        Voltage solution, converged?, error, calculated power injections

    @Author: Santiago Peñate Vera
    """
    start = time.time()

    # initialize
    Sbus = Sbus_.copy()
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

        # generate lookup pvpq -> index pvpq (used in createJ)
        pvpq_lookup = np.zeros(np.max(Ybus.indices) + 1, dtype=int)
        pvpq_lookup[pvpq] = np.arange(len(pvpq))

        while not converged and iter_ < max_it:

            # evaluate Jacobian
            if update_jacobian:
                H = AC_jacobian(Ybus, V, pvpq, pq, pvpq_lookup, npv, npq)
                # H = Jacobian(Ybus, V, Ibus, pq, pvpq)

            # evaluate the solution error F(x0)
            Scalc = V * np.conj(Ybus * V - Ibus)
            mis = Scalc - Sbus  # compute the mismatch
            dz = np.r_[mis[pvpq].real, mis[pq].imag]  # mismatch in the Jacobian order

            # system matrix
            # H1 = H^t
            H1 = H.transpose().tocsr()

            # H2 = H1·H
            H2 = H1.dot(H)

            # set first value of lmbda
            if iter_ == 0:
                lbmda = 1e-3 * H2.diagonal().max()

            # compute system matrix A = H^T·H - lambda·I
            A = H2 + lbmda * Idn

            # right hand side
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
                V = Vm * np.exp(1.0j * Va)

            else:
                update_jacobian = False
                lbmda *= nu
                nu *= 2.0

            # check convergence
            Scalc = V * np.conj(Ybus.dot(V))
            ds = Sbus - Scalc
            e = np.r_[ds[pvpq].real, ds[pq].imag]
            normF = 0.5 * np.dot(e, e)

            # review reactive power limits
            # it is only worth checking Q limits with a low error
            # since with higher errors, the Q values may be far from realistic
            # finally, the Q control only makes sense if there are pv nodes
            if control_q != ReactivePowerControlMode.NoControl and normF < 1e-2 and npv > 0:

                # check and adjust the reactive power
                # this function passes pv buses to pq when the limits are violated,
                # but not pq to pv because that is unstable
                n_changes, Scalc, Sbus, pv, pq, pvpq = control_q_inside_method(Scalc, Sbus, pv, pq, pvpq, Qmin, Qmax)

                if n_changes > 0:
                    # adjust internal variables to the new pq|pv values
                    npv = len(pv)
                    npq = len(pq)
                    npvpq = npv + npq
                    pvpq_lookup = np.zeros(np.max(Ybus.indices) + 1, dtype=int)
                    pvpq_lookup[pvpq] = np.arange(npvpq)

                    nn = 2 * npq + npv
                    ii = np.linspace(0, nn - 1, nn)
                    Idn = sparse((np.ones(nn), (ii, ii)), shape=(nn, nn))  # csc_matrix identity

                    # recompute the error based on the new Sbus
                    ds = Sbus - Scalc
                    e = np.r_[ds[pvpq].real, ds[pq].imag]
                    normF = 0.5 * np.dot(e, e)

            converged = normF < tol
            f_prev = f

            # update iteration counter
            iter_ += 1
    else:
        normF = 0
        converged = True
        Scalc = Sbus  # V * np.conj(Ybus * V - Ibus)
        iter_ = 0

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V, converged, normF, Scalc, None, None, None, iter_, elapsed)


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


def condition_number(J):
    """
    Computes the condition number of a sparse matrix
    :param J: sparse matrix like the Jacobian
    :return:
    """
    norm_A = scipy.sparse.linalg.norm(J)
    norm_invA = scipy.sparse.linalg.norm(scipy.sparse.linalg.inv(J))
    cond = norm_A * norm_invA
    return cond


def NR_I_LS(Ybus, Sbus_sp, V0, Ibus_sp, pv, pq, tol, max_it=15, acceleration_parameter=0.5) -> NumericPowerFlowResults:
    """
    Solves the power flow using a full Newton's method in current equations with current mismatch with line search
    Args:
        Ybus: Admittance matrix
        Sbus_sp: Array of nodal specified power injections
        V0: Array of nodal voltages (initial solution)
        Ibus_sp: Array of nodal specified current injections
        pv: Array with the indices of the PV buses
        pq: Array with the indices of the PQ buses
        tol: Tolerance
        max_it: Maximum number of iterations
        acceleration_parameter: value used to correct bad iterations
    Returns:
        Voltage solution, converged?, error, calculated power injections

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

    if normF < tol:
        converged = 1

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

        if normF < tol:
            converged = 1

    end = time.time()
    elapsed = end - start

    Scalc = V * np.conj(Icalc)

    return NumericPowerFlowResults(V, converged, normF, Scalc, None, None, None, iter_, elapsed)


def F(V, Ybus, S, I, pq, pvpq):
    """

    :param V:
    :param Ybus:
    :param S:
    :param I:
    :param pq:
    :param pv:
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
    gx = Jacobian(Ybus, V, I, pq, pvpq)

    # return the increment of x
    return linear_solver(gx, g)


def ContinuousNR(Ybus, Sbus, V0, Ibus, pv, pq, tol, max_it=15) -> NumericPowerFlowResults:
    """
    Solves the power flow using a full Newton's method with the backtrack improvement algorithm
    Args:
        Ybus: Admittance matrix
        Sbus: Array of nodal power injections
        V0: Array of nodal voltages (initial solution)
        Ibus: Array of nodal current injections
        pv: Array with the indices of the PV buses
        pq: Array with the indices of the PQ buses
        tol: Tolerance
        max_it: Maximum number of iterations
        robust: Boolean variable for the use of the Iwamoto optimal step factor.
    Returns:
        Voltage solution, converged?, error, calculated power injections

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
    F = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]

    # check tolerance
    normF = np.linalg.norm(F, np.Inf)
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
        F = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again

        # check for convergence
        normF = np.linalg.norm(F, np.Inf)

        if normF > 0.01:
            dt = max(dt * 0.985, 0.75)
        else:
            dt = min(dt * 1.015, 0.75)

        print(dt)
        converged = normF < tol

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V, converged, normF, Scalc, None, None, None, iter_, elapsed)
