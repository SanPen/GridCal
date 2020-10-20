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


from numpy import array, angle, exp, linalg, r_, Inf, conj, diag, asmatrix, asarray, zeros_like, zeros, complex128, \
empty, float64, int32, arange
from scipy.sparse import issparse, csr_matrix as sparse, hstack as hstack_sp, vstack as vstack_sp, diags
from scipy.sparse.linalg import spsolve, splu
import scipy
scipy.ALLOW_THREADS = True
import time
import numpy as np

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
    dI_dVm = Ybus * diags(V / np.abs(V))
    dI_dVa = 1j * (Ybus * diags(V))

    J11 = dI_dVa[array([pvpq]).T, pvpq].real
    J12 = dI_dVm[array([pvpq]).T, pq].real
    J21 = dI_dVa[array([pq]).T, pvpq].imag
    J22 = dI_dVm[array([pq]).T, pq].imag

    J = vstack_sp([hstack_sp([J11, J12]),
                   hstack_sp([J21, J22])], format="csr")

    return J


def NR_I(Ybus, Sbus_sp, V0, Ibus_sp, pv, pq, tol, max_it=15):
    """
    Solves the power flow using a full Newton's method in current equations with current mismatch
    Args:
        Ybus: Admittance matrix
        Sbus_sp: Array of nodal specified power injections
        V0: Array of nodal voltages (initial solution)
        Ibus_sp: Array of nodal specified current injections
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
    back_track_counter = 0
    back_track_iterations = 0
    alpha = 1e-4
    converged = 0
    iter_ = 0
    V = V0
    Va = angle(V)
    Vm = abs(V)
    dVa = zeros_like(Va)
    dVm = zeros_like(Vm)

    # set up indexing for updating V
    pvpq = r_[pv, pq]
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
    dI = conj(Sbus_sp / V) - Icalc  # compute the mismatch
    F = r_[dI[pv].real, dI[pq].real, dI[pq].imag]
    normF = linalg.norm(F, Inf)  # check tolerance

    if normF < tol:
        converged = 1

    # do Newton iterations
    while not converged and iter_ < max_it:
        # update iteration counter
        iter_ += 1

        # evaluate Jacobian
        J = Jacobian_I(Ybus, V, pq, pvpq)

        # compute update step
        dx = spsolve(J, F)

        # reassign the solution vector
        if npv:
            dVa[pv] = dx[j1:j2]
        if npq:
            dVa[pq] = dx[j3:j4]
            dVm[pq] = dx[j5:j6]

        # update voltage the Newton way (mu=1)
        mu_ = 1.0
        Vm += mu_ * dVm
        Va += mu_ * dVa
        V = Vm * exp(1j * Va)

        # evaluate F(x)
        Icalc = Ybus * V - Ibus_sp
        dI = conj(Sbus_sp / V) - Icalc
        F = r_[dI[pv].real, dI[pq].real, dI[pq].imag]
        normF = linalg.norm(F, Inf)  # check tolerance

        if normF < tol:
            converged = 1

    end = time.time()
    elapsed = end - start

    print('iter_', iter_,
          '  -  back_track_counter', back_track_counter,
          '  -  back_track_iterations', back_track_iterations)

    Scalc = V * conj(Icalc)

    return V, converged, normF, Scalc


def NR_I_LS(Ybus, Sbus_sp, V0, Ibus_sp, pv, pq, tol, max_it=15):
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
    Va = angle(V)
    Vm = abs(V)
    dVa = zeros_like(Va)
    dVm = zeros_like(Vm)

    # set up indexing for updating V
    pvpq = r_[pv, pq]
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
    dI = conj(Sbus_sp / V) - Icalc  # compute the mismatch
    F = r_[dI[pv].real, dI[pq].real, dI[pq].imag]
    normF = linalg.norm(F, Inf)  # check tolerance

    if normF < tol:
        converged = 1

    # do Newton iterations
    while not converged and iter_ < max_it:
        # update iteration counter
        iter_ += 1

        # evaluate Jacobian
        J = Jacobian_I(Ybus, V, pq, pvpq)

        # compute update step
        dx = spsolve(J, F)

        # reassign the solution vector
        if npv:
            dVa[pv] = dx[j1:j2]
        if npq:
            dVa[pq] = dx[j3:j4]
            dVm[pq] = dx[j5:j6]

        # update voltage the Newton way (mu=1)
        mu_ = 1.0
        Vm += mu_ * dVm
        Va += mu_ * dVa
        Vnew = Vm * exp(1j * Va)

        # compute the mismatch function f(x_new)
        Icalc = Ybus * Vnew - Ibus_sp
        dI = conj(Sbus_sp / Vnew) - Icalc
        Fnew = r_[dI[pv].real, dI[pq].real, dI[pq].imag]

        normFprev = linalg.norm(F + alpha * (F * J).dot(Fnew - F), Inf)

        cond = normF < normFprev  # condition to back track (no improvement at all)

        if not cond:
            back_track_counter += 1

        l_iter = 0
        while not cond and l_iter < 10 and mu_ > 0.01:
            # line search back

            # to divide mu by 4 is the simplest backtracking process
            # TODO: implement the more complex mu backtrack from numerical recipes

            # update voltage with a closer value to the last value in the Jacobian direction
            mu_ *= 0.25
            Vm -= mu_ * dVm
            Va -= mu_ * dVa
            Vnew = Vm * exp(1j * Va)

            # compute the mismatch function f(x_new)
            Icalc = Ybus * Vnew - Ibus_sp
            dI = conj(Sbus_sp / Vnew) - Icalc
            Fnew = r_[dI[pv].real, dI[pq].real, dI[pq].imag]

            normFnew = linalg.norm(Fnew, Inf)
            normFnew_prev = linalg.norm(F + alpha * (F * J).dot(Fnew - F), Inf)

            cond = normFnew < normFnew_prev

            l_iter += 1
            back_track_iterations += 1

        # update calculation variables
        V = Vnew
        F = Fnew

        # check for convergence
        normF = linalg.norm(F, Inf)

        if normF < tol:
            converged = 1

    end = time.time()
    elapsed = end - start

    print('iter_', iter_,
          '  -  back_track_counter', back_track_counter,
          '  -  back_track_iterations', back_track_iterations)

    Scalc = V * conj(Icalc)

    return V, converged, normF, Scalc


def NR_I2(Ybus, Sbus_sp, V0, Ibus_sp, pv, pq, tol, max_it=15):
    """
    Solves the power flow using a full Newton's method in current equations with power mismatch
    Args:
        Ybus: Admittance matrix
        Sbus_sp: Array of nodal specified power injections
        V0: Array of nodal voltages (initial solution)
        Ibus_sp: Array of nodal specified current injections
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
    back_track_counter = 0
    back_track_iterations = 0
    alpha = 1e-4
    converged = 0
    iter_ = 0
    V = V0
    Va = angle(V)
    Vm = abs(V)
    dVa = zeros_like(Va)
    dVm = zeros_like(Vm)

    # set up indexing for updating V
    pvpq = r_[pv, pq]
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
    dI = conj(Sbus_sp / V) - Icalc  # compute the mismatch
    F = r_[dI[pv].real, dI[pq].real, dI[pq].imag]
    dS = V * conj(Icalc) - Sbus_sp  # complex power mismatch
    Fs = r_[dS[pv].real, dS[pq].real, dS[pq].imag]
    normF = linalg.norm(Fs, Inf)  # check tolerance

    if normF < tol:
        converged = 1

    # do Newton iterations
    while not converged and iter_ < max_it:
        # update iteration counter
        iter_ += 1

        # evaluate Jacobian
        J = Jacobian_I(Ybus, V, pq, pvpq)

        # compute update step
        dx = spsolve(J, F)

        # reassign the solution vector
        if npv:
            dVa[pv] = dx[j1:j2]
        if npq:
            dVa[pq] = dx[j3:j4]
            dVm[pq] = dx[j5:j6]

        # update voltage the Newton way (mu=1)
        mu_ = 1.0
        Vm += mu_ * dVm
        Va += mu_ * dVa
        V = Vm * exp(1j * Va)

        # evaluate F(x)
        Icalc = Ybus * V - Ibus_sp
        dI = conj(Sbus_sp / V) - Icalc
        F = r_[dI[pv].real, dI[pq].real, dI[pq].imag]
        dS = V * conj(Icalc) - Sbus_sp  # complex power mismatch
        Fs = r_[dS[pv].real, dS[pq].real, dS[pq].imag]
        normF = linalg.norm(Fs, Inf)  # check tolerance

        if normF < tol:
            converged = 1

    end = time.time()
    elapsed = end - start

    print('iter_', iter_,
          '  -  back_track_counter', back_track_counter,
          '  -  back_track_iterations', back_track_iterations)

    Scalc = V * conj(Icalc)

    return V, converged, normF, Scalc


########################################################################################################################
#  MAIN
########################################################################################################################
if __name__ == "__main__":
    from GridCal.Engine import *

    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE14_from_raw.gridcal'
    grid = FileOpen(fname).open()

    nc = compile_snapshot_circuit(grid)
    islands = nc.split_into_islands()
    circuit = islands[0]

    print('\nYbus:\n', circuit.Ybus.todense())
    print('\nYseries:\n', circuit.Yseries.todense())
    print('\nYshunt:\n', circuit.Yshunt)
    print('\nSbus:\n', circuit.Sbus)
    print('\nIbus:\n', circuit.Ibus)
    print('\nVbus:\n', circuit.Vbus)
    print('\ntypes:\n', circuit.bus_types)
    print('\npq:\n', circuit.pq)
    print('\npv:\n', circuit.pv)
    print('\nvd:\n', circuit.vd)

    import time
    print('Newton-Raphson-current')
    start_time = time.time()
    # V, converged, normF, Scalc, iter_, elapsed
    V1, converged_, err, S, iter_, elapsed_ = NR_I_LS(Ybus=circuit.Ybus,
                                                      Sbus_sp=circuit.Sbus,
                                                      V0=circuit.Vbus,
                                                      Ibus_sp=circuit.Ibus,
                                                      pv=circuit.pv,
                                                      pq=circuit.pq,
                                                      tol=1e-9,
                                                      max_it=100)

    print("--- %s seconds ---" % (time.time() - start_time))
    # print_coeffs(C, W, R, X, H)

    # print('V module:\t', abs(V1))
    # print('V angle: \t', angle(V1))
    print('error: \t', err)

    # check the HELM solution: v against the NR power flow
    print('\nNR standard')
    options = PowerFlowOptions(SolverType.NR, verbose=False, tolerance=1e-9, control_q=False)
    power_flow = PowerFlowDriver(grid, options)

    start_time = time.time()
    power_flow.run()
    print("--- %s seconds ---" % (time.time() - start_time))
    vnr = power_flow.results.voltage

    # print('V module:\t', abs(vnr))
    # print('V angle: \t', angle(vnr))
    print('error: \t', power_flow.results.error())

    data = c_[np.abs(V1), angle(V1), np.abs(vnr), angle(vnr),  np.abs(V1 - vnr)]
    cols = ['|V|', 'angle', '|V| benchmark NR', 'angle benchmark NR', 'Diff']
    df = pd.DataFrame(data, columns=cols)

    print()
    print(df)
