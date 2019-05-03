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
from scipy.sparse import issparse, csr_matrix as sparse, hstack, vstack
from scipy.sparse.linalg import spsolve, splu
import scipy
scipy.ALLOW_THREADS = True
import time
import numpy as np

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

    if issparse(Ybus):
        Ibus = Ybus * V - I

        diagV = sparse((V, (ib, ib)))
        diagIbus = sparse((Ibus, (ib, ib)))
        diagVnorm = sparse((V / abs(V), (ib, ib)))
    else:
        Ibus = Ybus * asmatrix(V).T - I

        diagV = asmatrix(diag(V))
        diagIbus = asmatrix(diag(asarray(Ibus).flatten()))
        diagVnorm = asmatrix(diag(V / abs(V)))

    dS_dVm = diagV * conj(Ybus * diagVnorm) + conj(diagIbus) * diagVnorm
    dS_dVa = 1j * diagV * conj(diagIbus - Ybus * diagV)

    return dS_dVm, dS_dVa


def mu(Ybus, Ibus, J, incS, dV, dx, pvpq, pq):
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
    J2 = Jacobian(Ybus, dV, Ibus, pq, pvpq)

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
    Computes the system Jacobian matrix
    Args:
        Ybus: Admittance matrix
        V: Array of nodal voltages
        Ibus: Array of nodal current injections
        pq: Array with the indices of the PQ buses
        pvpq: Array with the indices of the PV and PQ buses

    Returns:
        The system Jacobian matrix
    """
    dS_dVm, dS_dVa = dSbus_dV(Ybus, V, Ibus)  # compute the derivatives

    J11 = dS_dVa[array([pvpq]).T, pvpq].real
    J12 = dS_dVm[array([pvpq]).T, pq].real
    J21 = dS_dVa[array([pq]).T, pvpq].imag
    J22 = dS_dVm[array([pq]).T, pq].imag

    J = vstack([
        hstack([J11, J12]),
        hstack([J21, J22])
    ], format="csr")

    return J


def NR_LS(Ybus, Sbus, V0, Ibus, pv, pq, tol, max_it=15):
    """
    Solves the power flow using a full Newton's method with the Iwamoto optimal step factor.
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
    Scalc = V * conj(Ybus * V - Ibus)
    dS = Scalc - Sbus  # compute the mismatch
    F = r_[dS[pv].real, dS[pq].real, dS[pq].imag]

    # check tolerance
    normF = linalg.norm(F, Inf)

    if normF < tol:
        converged = 1

    # do Newton iterations
    while not converged and iter_ < max_it:
        # update iteration counter
        iter_ += 1

        # evaluate Jacobian
        J = Jacobian(Ybus, V, Ibus, pq, pvpq)

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
        Vm -= mu_ * dVm
        Va -= mu_ * dVa
        Vnew = Vm * exp(1j * Va)

        # compute the mismatch function f(x_new)
        dS = Vnew * conj(Ybus * Vnew - Ibus) - Sbus  # complex power mismatch
        Fnew = r_[dS[pv].real, dS[pq].real, dS[pq].imag]  # concatenate to form the mismatch function
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
            dS = Vnew * conj(Ybus * Vnew - Ibus) - Sbus  # complex power mismatch
            Fnew = r_[dS[pv].real, dS[pq].real, dS[pq].imag]  # concatenate to form the mismatch function

            normFnew = linalg.norm(Fnew, Inf)
            normFnew_prev = linalg.norm(F + alpha * (F * J).dot(Fnew - F), Inf)

            cond = normFnew < normFnew_prev

            l_iter += 1
            back_track_iterations += 1

        # update calculation variables
        V = Vnew
        F = Fnew
        # normF = normFnew

        # check for convergence
        normF = linalg.norm(F, Inf)

        if normF < tol:
            converged = 1

    end = time.time()
    elapsed = end - start

    print('iter_', iter_, '  -  back_track_counter', back_track_counter,
          '  -  back_track_iterations', back_track_iterations)

    return V, converged, normF, Scalc


def NR_LS2(Ybus, Sbus, V0, Ibus, pv, pq, tol, max_it=15):
    """
    Solves the power flow using a full Newton's method with the Iwamoto optimal step factor.
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
    Scalc = V * conj(Ybus * V - Ibus)
    dS = Scalc - Sbus  # compute the mismatch
    F = r_[dS[pv].real, dS[pq].real, dS[pq].imag]

    # check tolerance
    normF = 0.5 * F.dot(F)

    if normF < tol:
        converged = 1

    # do Newton iterations
    while not converged and iter_ < max_it:
        # update iteration counter
        iter_ += 1

        # evaluate Jacobian
        J = Jacobian(Ybus, V, Ibus, pq, pvpq)

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
        Vm -= mu_ * dVm
        Va -= mu_ * dVa
        Vnew = Vm * exp(1j * Va)

        # compute the mismatch function f(x_new)
        dS = Vnew * conj(Ybus * Vnew - Ibus) - Sbus  # complex power mismatch
        Fnew = r_[dS[pv].real, dS[pq].real, dS[pq].imag]  # concatenate to form the mismatch function
        normFnew = 0.5 * Fnew.dot(Fnew)

        cond = normFnew > normF  # condition to back track (no improvement at all)

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
            dS = Vnew * conj(Ybus * Vnew - Ibus) - Sbus  # complex power mismatch
            Fnew = r_[dS[pv].real, dS[pq].real, dS[pq].imag]  # concatenate to form the mismatch function

            normFnew = 0.5 * Fnew.dot(Fnew)

            cond = normFnew > normF

            l_iter += 1
            back_track_iterations += 1

        # update calculation variables
        V = Vnew
        F = Fnew
        # normF = normFnew

        # check for convergence
        normF = 0.5 * Fnew.dot(Fnew)

        if normF < tol:
            converged = 1

    end = time.time()
    elapsed = end - start

    print('iter_', iter_, '  -  back_track_counter', back_track_counter,
          '  -  back_track_iterations', back_track_iterations)

    return V, converged, normF, Scalc


########################################################################################################################
#  MAIN
########################################################################################################################
if __name__ == "__main__":
    from GridCal.Engine.calculation_engine import MultiCircuit, PowerFlowOptions, PowerFlow, SolverType
    import pandas as pd

    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)

    grid = MultiCircuit()
    # grid.load_file('lynn5buspq.xlsx')
    grid.load_file('IEEE30.xlsx')
    # grid.load_file('/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 145 Bus.xlsx')
    grid.compile()

    circuit = grid.circuits[0]

    print('\nYbus:\n', circuit.power_flow_input.Ybus.todense())
    print('\nYseries:\n', circuit.power_flow_input.Yseries.todense())
    print('\nYshunt:\n', circuit.power_flow_input.Yshunt)
    print('\nSbus:\n', circuit.power_flow_input.Sbus)
    print('\nIbus:\n', circuit.power_flow_input.Ibus)
    print('\nVbus:\n', circuit.power_flow_input.Vbus)
    print('\ntypes:\n', circuit.power_flow_input.types)
    print('\npq:\n', circuit.power_flow_input.pq)
    print('\npv:\n', circuit.power_flow_input.pv)
    print('\nvd:\n', circuit.power_flow_input.ref)

    import time
    print('Newton-Raphson-Line-search')
    start_time = time.time()
    # Ybus, Sbus, V0, Ibus, pv, pq, tol, max_it=15
    V1, converged_, err, S = NR_LS2(Ybus=circuit.power_flow_input.Ybus,
                                   Sbus=circuit.power_flow_input.Sbus,
                                   V0=circuit.power_flow_input.Vbus,
                                   Ibus=circuit.power_flow_input.Ibus,
                                   pv=circuit.power_flow_input.pv,
                                   pq=circuit.power_flow_input.pq,
                                   tol=1e-9,
                                   max_it=100)

    print("--- %s seconds ---" % (time.time() - start_time))
    # print_coeffs(C, W, R, X, H)

    print('error: \t', err)

    # check the HELM solution: v against the NR power flow
    print('\nNR standard')
    options = PowerFlowOptions(SolverType.IWAMOTO, verbose=False, robust=False, tolerance=1e-9, control_q=False)
    power_flow = PowerFlow(grid, options)

    start_time = time.time()
    power_flow.run()
    print("--- %s seconds ---" % (time.time() - start_time))
    vnr = circuit.power_flow_results.voltage

    print('error: \t', circuit.power_flow_results.error)

    # check

    data = np.c_[np.abs(V1), angle(V1), np.abs(vnr), angle(vnr),  np.abs(V1 - vnr)]
    cols = ['|V|', 'angle', '|V| benchmark NR', 'angle benchmark NR', 'Diff']
    df = pd.DataFrame(data, columns=cols)

    print()
    print(df)