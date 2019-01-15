# Copyright (c) 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE_MATPOWER file.

# The file has been modified from Pypower.
# The function mu() has been added to the solver in order to provide an optimal iteration control
# Copyright (c) 2016 Santiago Peñate Vera
# This file retains the BSD-Style license

import numpy as np
from numpy import array, angle, exp, linalg, r_, Inf, conj, diag, asmatrix, asarray, zeros_like
from scipy.sparse import issparse, csr_matrix as sparse, hstack, vstack
from scipy.sparse.linalg import spsolve
import scipy
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


def LevenbergMarquardtPF(Ybus, Sbus, V0, Ibus, pv, pq, tol, max_it):
    """
    Solves the power flow problem by the Levenberg-Marquardt power flow algorithm
    Args:
        Ybus: Admittance matrix
        Sbus: Array of nodal power injections
        V0: Array of nodal voltages (initial solution)
        Ibus: Array of nodal current injections
        ref: Array with the indices of the slack buses
        pv: Array with the indices of the PV buses
        pq: Array with the indices of the PQ buses
        tol: Tolerance
        max_it: Maximum number of iterations
        verbose: Boolean variable for the verbose mode activation
    Returns:
    @Author: Santiago Penate Vera
    """

    # initialize
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

    update_H = True
    converged = False
    iter_ = 0
    nu = 2.0
    lbmda = 0
    f_prev = 1e9  # very large number
    Idn = np.identity(2 * npq + npv)

    # do Newton iterations
    while not converged and iter_ < max_it:

        # evaluate Jacobian
        if update_H:
            H = Jacobian(Ybus, V, Ibus, pq, pvpq)

        # evaluate the solution error F(x0)
        Scalc = V * conj(Ybus * V - Ibus)
        mis = Scalc - Sbus  # compute the mismatch
        dz = r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # mismatch in the Jacobian order

        # system matrix
        # H1 = H^t·W
        H1 = H.transpose()
        # H2 = H1·H
        H2 = H1.dot(H)

        # set first value of lmbda
        if iter_ == 0:
            lbmda = 1e-3 * H2.diagonal().max()

        # compute system matrix
        A = H2 + lbmda * Idn

        # right hand side
        # H^t·W·dz
        rhs = H1.dot(dz)

        # Solve the increment
        dx = np.linalg.solve(A, rhs)

        # objective function
        f = 0.5 * dz.dot(dz)

        # decision function
        rho = (f_prev - f) / (0.5 * dx.dot(lbmda * dx + rhs))

        # lambda update
        if rho > 0:
            update_H = True
            lbmda *= max([1.0 / 3.0, 1 - (2 * rho - 1) ** 3])
            nu = 2.0

            # reassign the solution vector
            if npv:
                dVa[pv] = dx[j1:j2]
            if npq:
                dVa[pq] = dx[j3:j4]
                dVm[pq] = dx[j5:j6]

            Vm -= dVm
            Va -= dVa
            V = Vm * exp(1j * Va)
            Vm = abs(V)  # update Vm and Va again in case
            Va = angle(V)  # we wrapped around with a negative Vm
        else:
            update_H = False
            lbmda *= nu
            nu *= 2

        # ckeck convergence
        normF = np.linalg.norm(dx, np.Inf)
        converged = normF < tol
        f_prev = f

        # update iteration counter
        iter_ += 1

    return V, converged, normF, Scalc


if __name__ == "__main__":
    from GridCal.Engine.calculation_engine import *

    grid = MultiCircuit()
    # grid.load_file('lynn5buspq.xlsx')
    grid.load_file('IEEE30.xlsx')

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
    print('Levenberg-Marquardt')
    start_time = time.time()
    V1, converged_, err, S = LevenbergMarquardtPF(Ybus=circuit.power_flow_input.Ybus,
                                                  Sbus=circuit.power_flow_input.Sbus,
                                                  V0=circuit.power_flow_input.Vbus,
                                                  Ibus=circuit.power_flow_input.Ibus,
                                                  pv=circuit.power_flow_input.pv,
                                                  pq=circuit.power_flow_input.pq,
                                                  tol=1e-9,
                                                  max_it=100)

    print("--- %s seconds ---" % (time.time() - start_time))
    # print_coeffs(C, W, R, X, H)

    print('V module:\t', abs(V1))
    print('V angle: \t', angle(V1))
    print('error: \t', err)

    # check the HELM solution: v against the NR power flow
    print('\nNR')
    options = PowerFlowOptions(SolverType.NR, verbose=False, robust=False, tolerance=1e-9)
    power_flow = PowerFlow(grid, options)

    start_time = time.time()
    power_flow.run()
    print("--- %s seconds ---" % (time.time() - start_time))
    vnr = circuit.power_flow_results.voltage

    print('V module:\t', abs(vnr))
    print('V angle: \t', angle(vnr))
    print('error: \t', circuit.power_flow_results.error)

    # check
    print('\ndiff:\t', V1 - vnr)