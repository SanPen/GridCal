"""
N phase calculation engine
(c) Santiago Peñate Vera, 2018
"""

import numpy as np
from scipy.sparse.linalg import spsolve
from scipy.sparse import csc_matrix, hstack, vstack
from scipy.sparse.linalg import factorized
from scipy.sparse.linalg import splu


def gauss_seidel_power_flow(Vbus, Sbus, Ibus, Ybus,
                            P0, Q0, exp_p, exp_q, V0,
                            A, B, C,
                            pq, pv, tol, max_iter, verbose=False):
    """
    Gauss-Seidel power flow
    :param Vbus: Bus voltage complex vector
    :param Sbus: Bus complex power injections vector
    :param Ibus: Bus complex current injections vector
    :param Ybus: Nodal admittance matrix (complex and sparse)
    :param P0: Exponential load parameter P0
    :param Q0: Exponential load parameter Q0
    :param exp_p: Exponential load parameter exp_p
    :param exp_q: Exponential load parameter exp_q
    :param V0: Exponential load parameter V0
    :param A: Polynomial load parameter A
    :param B: Polynomial load parameter B
    :param C: Polynomial load parameter C
    :param pq: list of pq marked nodes
    :param pv: list of pv marked nodes
    :param tol: tolerance of the solution
    :param max_iter: Maximum number of iterations
    :return: Voltage vector (solution), converged?, power error
    """

    factor = 0.9

    V = Vbus.copy()
    Vm = np.abs(V)

    # compute error
    mis = V * np.conj(Ybus * V - Ibus) - Sbus
    F = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]
    error = np.linalg.norm(F, np.Inf)

    # check convergence
    converged = error < tol

    # Gauss-Seidel
    iter_ = 0
    while not converged and iter_ < max_iter:

        # compute the exponential load model injection
        Vm = np.abs(V)
        Pexp = P0 / (np.power(V0, exp_p)) * np.power(Vm, exp_p)
        Qexp = Q0 / (np.power(V0, exp_q)) * np.power(Vm, exp_q)
        Sexp = Pexp + 1j * Qexp

        # compute the polynomial load model
        Spoly = A + B * Vm + C * np.power(Vm, 2.0)

        for k in pq:
            V[k] += factor * (np.conj((Sbus[k] - Sexp[k] - Spoly[k]) / V[k] + Ibus[k]) - Ybus[k, :] * V) / Ybus[k, k]  # compute the voltage

        for k in pv:
            # get the reactive power
            Q = (V[k] * np.conj(Ybus[k, :] * V - Ibus[k])).imag
            # compose the new complex power
            Sbus[k] = Sbus[k].real + 1j * Q
            # compute the voltage
            V[k] += factor * (np.conj((Sbus[k] - Sexp[k] - Spoly[k]) / V[k]) - Ybus[k, :] * V) / Ybus[k, k]
            # correct the voltage with the specified module of the voltage
            V[k] *= Vm[k] / np.abs(V[k])

        # compute error
        Scalc = V * np.conj(Ybus * V - Ibus)  # computed nodal power
        mis = Scalc - (Sbus - Sexp - Spoly)  # power mismatch
        F = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # array of particular mismatch values
        error = np.linalg.norm(F, np.Inf)  # infinite norm of the mismatch vector

        # check convergence
        converged = error < tol

        iter_ += 1
        if verbose:
            print('V: iter:', iter_, 'err:', error)
            print(np.abs(V))

    return V, converged, error


def jacobian(Ybus, Vbus, Ibus, pq, pvpq):
    """
    Computes the system Jacobian matrix
    Args:
        Ybus: Admittance matrix
        Vbus: Array of nodal voltages
        Ibus: Array of nodal current injections
        pq: Array with the indices of the PQ buses
        pvpq: Array with the indices of the PV and PQ buses in that precise order
    Returns:
        The system Jacobian matrix
    """
    ib = range(len(Vbus))
    Ibus = Ybus * Vbus - Ibus

    diagV = csc_matrix((Vbus, (ib, ib)))
    diagIbus = csc_matrix((Ibus, (ib, ib)))
    diagVnorm = csc_matrix((Vbus / np.abs(Vbus), (ib, ib)))

    dS_dVm = diagV * np.conj(Ybus * diagVnorm) + np.conj(diagIbus) * diagVnorm
    dS_dVa = 1j * diagV * np.conj(diagIbus - Ybus * diagV)

    J11 = dS_dVa[np.array([pvpq]).T, pvpq].real
    J12 = dS_dVm[np.array([pvpq]).T, pq].real
    J21 = dS_dVa[np.array([pq]).T, pvpq].imag
    J22 = dS_dVm[np.array([pq]).T, pq].imag

    J = vstack([hstack([J11, J12]),
                hstack([J21, J22])], format="csr")

    return J


def newton_raphson_power_flow(Vbus, Sbus, Ibus, Ybus,
                              P0, Q0, exp_p, exp_q, V0,
                              A, B, C,
                              pq, pv, tol, max_iter, verbose=False):
    """
    Solves the power flow using a full Newton's method with the Iwamoto optimal step factor.
    Args:
        Vbus: Array of nodal voltages (initial solution)
        Sbus: Array of nodal power injections
        Ibus: Array of nodal current injections
        Ybus: Admittance matrix
        P0: Exponential load parameter P0
        Q0: Exponential load parameter Q0
        exp_p: Exponential load parameter exp_p
        exp_q: Exponential load parameter exp_q
        V0: Exponential load parameter V0
        A: Polynomial load parameter A
        B: Polynomial load parameter B
        C: Polynomial load parameter C
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
    # initialize
    converged = 0
    iter_ = 0
    V = Vbus
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
    Scalc = V * np.conj(Ybus * V - Ibus)

    # compute the exponential load model injection
    Vabs = np.abs(V)
    Pexp = P0 / (np.power(V0, exp_p)) * np.power(Vabs, exp_p)
    Qexp = Q0 / (np.power(V0, exp_q)) * np.power(Vabs, exp_q)
    Sexp = Pexp + 1j * Qexp

    # compute the polynomial load model
    Spoly = A + B * Vabs + C * np.power(Vabs, 2.0)

    mis = Scalc - Sbus - Sexp - Spoly  # compute the mismatch
    F = np.r_[mis[pv].real,
              mis[pq].real,
              mis[pq].imag]

    # check tolerance
    error = np.linalg.norm(F, np.Inf)

    if error < tol:
        converged = 1

    # do Newton iterations
    while not converged and iter_ < max_iter:
        # update iteration counter
        iter_ += 1

        # evaluate Jacobian
        J = jacobian(Ybus, V, Ibus, pq, pvpq)

        # compute update step
        dx = spsolve(J, F)

        # reassign the solution vector
        if npv:
            dVa[pv] = dx[j1:j2]
        if npq:
            dVa[pq] = dx[j3:j4]
            dVm[pq] = dx[j5:j6]
        # dV = dVm * np.exp(1j * dVa)  # voltage mismatch

        # update voltage
        Vm -= dVm
        Va -= dVa

        V = Vm * np.exp(1j * Va)

        Vm = np.abs(V)  # update Vm and Va again in case
        Va = np.angle(V)  # we wrapped around with a negative Vm

        # evaluate F(x)
        Scalc = V * np.conj(Ybus * V - Ibus)

        # compute the exponential load model injection
        Pexp = P0 / (np.power(V0, exp_p)) * np.power(Vm, exp_p)
        Qexp = Q0 / (np.power(V0, exp_q)) * np.power(Vm, exp_q)
        Sexp = Pexp + 1j * Qexp

        # compute the polynomial load model
        Spoly = A + B * Vm + C * np.power(Vm, 2.0)

        mis = Scalc - Sbus - Sexp - Spoly  # complex power mismatch
        F = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again

        # check for convergence
        error = np.linalg.norm(F, np.Inf)

        if error < tol:
            converged = 1

        if verbose:
            print('V: iter:', iter_, 'err:', error)
            print(np.abs(V))

    return V, converged, error


def levenberg_marquardt_power_flow(Vbus, Sbus, Ibus, Ybus,
                                   P0, Q0, exp_p, exp_q, V0,
                                   A, B, C,
                                   pq, pv, tol, max_iter=50, verbose=False):
    """
    Solves the power flow problem by the Levenberg-Marquardt power flow algorithm.
    It is usually better than Newton-Raphson, but it takes an order of magnitude more time to converge.
    Args:
        Vbus: Array of nodal voltages (initial solution)
        Sbus: Array of nodal power injections
        Ibus: Array of nodal current injections
        Ybus: Admittance matrix
        P0: Exponential load parameter P0
        Q0: Exponential load parameter Q0
        exp_p: Exponential load parameter exp_p
        exp_q: Exponential load parameter exp_q
        V0: Exponential load parameter V0
        A: Polynomial load parameter A
        B: Polynomial load parameter B
        C: Polynomial load parameter C
        pv: Array with the indices of the PV buses
        pq: Array with the indices of the PQ buses
        tol: Tolerance
        max_iter: Maximum number of iterations
    Returns:
        Voltage solution, converged?, error, calculated power injections

    @Author: Santiago Peñate Vera
    """
    # initialize
    V = Vbus
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

    update_jacobian = True
    converged = False
    iter_ = 0
    nu = 2.0
    lbmda = 0
    f_prev = 1e9  # very large number
    nn = 2 * npq + npv
    ii = np.linspace(0, nn-1, nn)
    Idn = csc_matrix((np.ones(nn), (ii, ii)), shape=(nn, nn))  # csr_matrix identity

    while not converged and iter_ < max_iter:

        # evaluate Jacobian
        if update_jacobian:
            H = jacobian(Ybus, V, Ibus, pq, pvpq)

        # evaluate the solution error F(x0)
        Scalc = V * np.conj(Ybus * V - Ibus)
        # compute the exponential load model injection
        Vm = np.abs(V)
        Pexp = P0 / (np.power(V0, exp_p)) * np.power(Vm, exp_p)
        Qexp = Q0 / (np.power(V0, exp_q)) * np.power(Vm, exp_q)
        Sexp = Pexp + 1j * Qexp

        # compute the polynomial load model
        Spoly = A + B * Vm + C * np.power(Vm, 2.0)

        mis = Scalc - Sbus - Sexp - Spoly  # complex power mismatch
        dz = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # mismatch in the Jacobian order

        # system matrix
        # H1 = H^t
        H1 = H.transpose().tocsr()

        # H2 = H1·H
        H2 = H1.dot(H)

        # set first value of lmbda
        if iter_ == 0:
            lbmda = 1e-3 * H2.diagonal().max()

        # compute system matrix A = H^T·H - lambda·I
        Amat = H2 + lbmda * Idn

        # right hand side
        # H^t·dz
        rhs = H1.dot(dz)

        # Solve the increment
        dx = spsolve(Amat, rhs)

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
            if npv:
                dVa[pv] = dx[j1:j2]
            if npq:
                dVa[pq] = dx[j3:j4]
                dVm[pq] = dx[j5:j6]

            Vm -= dVm
            Va -= dVa
            # update Vm and Va again in case we wrapped around with a negative Vm
            V = Vm * np.exp(1j * Va)
            Vm = np.abs(V)
            Va = np.angle(V)
        else:
            update_jacobian = False
            lbmda *= nu
            nu *= 2.0

        # check convergence
        f_prev = f

        # evaluate F(x)
        Scalc = V * np.conj(Ybus * V - Ibus)

        # compute the exponential load model injection
        Pexp = P0 / (np.power(V0, exp_p)) * np.power(Vm, exp_p)
        Qexp = Q0 / (np.power(V0, exp_q)) * np.power(Vm, exp_q)
        Sexp = Pexp + 1j * Qexp

        # compute the polynomial load model
        Spoly = A + B * Vm + C * np.power(Vm, 2.0)

        mis = Scalc - Sbus - Sexp - Spoly  # complex power mismatch
        mismatch = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again

        # check for convergence
        error = np.linalg.norm(mismatch, np.Inf)

        if error < tol:
            converged = 1

        # update iteration counter
        iter_ += 1

    return V, converged, error


def linearized_dc_power_flow(Ybus, Sbus, Ibus, V0, ref, pq, pv):
    """
    Solves a DC power flow.
    :param Ybus: Normal circuit admittance matrix
    :param Sbus: Complex power injections at all the nodes
    :param Ibus: Complex current injections at all the nodes
    :param V0: Array of complex seed voltage (it contains the ref voltages)
    :param ref: array of the indices of the slack nodes
    :param pvpq: array of the indices of the non-slack nodes
    :param pq: array of the indices of the pq nodes
    :param pv: array of the indices of the pv nodes
    :return:
        Complex voltage solution
        Converged: Always true
        Solution error
        Computed power injections given the found solution
    """

    pvpq = np.r_[pv, pq].astype(int)

    # Decompose the voltage in angle and magnitude
    Va_ref = np.angle(V0[ref])  # we only need the angles at the slack nodes
    Vm = np.abs(V0)

    # initialize result vector
    Va = np.empty(len(V0))

    # reconvert the pqpv vector to a matrix so that we can call numpy directly with it
    pvpq_ = np.matrix(pvpq)

    # Compile the reduced imaginary impedance matrix
    Bpqpv = Ybus.imag[pvpq_.T, pvpq_]
    Bref = Ybus.imag[pvpq_.T, ref]

    # compose the reduced power injections
    # Since we have removed the slack nodes, we must account their influence as injections Bref * Va_ref
    Pinj = Sbus[pvpq].real + (- Bref * Va_ref + Ibus[pvpq].real) * Vm[pvpq]

    # update angles for non-reference buses
    Va[pvpq] = spsolve(Bpqpv, Pinj)
    Va[ref] = Va_ref

    # re assemble the voltage
    V = Vm * np.exp(1j * Va)

    # compute the calculated power injection and the error of the voltage solution
    Scalc = V * np.conj(Ybus * V - Ibus)

    # compute the power mismatch between the specified power Sbus and the calculated power Scalc
    mis = Scalc - Sbus  # complex power mismatch
    F = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again

    # check for convergence
    normF = np.linalg.norm(F, np.Inf)

    return V, True, normF


def linear_ac_power_flow(Ybus, Yseries, Sbus, Ibus, Vbus, pq, pv):
    """
    Linearized AC Load Flow

    form the article:

    Linearized AC Load Flow Applied to Analysis in Electric Power Systems
        by: P. Rossoni, W. M da Rosa and E. A. Belati
    Args:
        Ybus: Admittance matrix
        Yseries: Admittance matrix of the series elements
        Sbus: Power injections vector of all the nodes
        Vbus: Set voltages of all the nodes (used for the slack and PV nodes)
        pq: list of indices of the pq nodes
        pv: list of indices of the pv nodes

    Returns: Voltage vector, converged?, error, calculated power and elapsed time
    """
    pvpq = np.r_[pv, pq].astype(int)
    npq = len(pq)
    npv = len(pv)

    # compose the system matrix
    # G = Y.real
    # B = Y.imag
    # Gp = Ys.real
    # Bp = Ys.imag

    # A11 = -Yseries.imag[pvpq, :][:, pvpq]
    # A12 = Ybus.real[pvpq, :][:, pq]
    # A21 = -Yseries.real[pq, :][:, pvpq]
    # A22 = -Ybus.imag[pq, :][:, pq]

    A11 = -Yseries.imag[np.ix_(pvpq, pvpq)]
    A12 = Ybus.real[np.ix_(pvpq, pq)]
    A21 = -Yseries.real[np.ix_(pq, pvpq)]
    A22 = -Ybus.imag[np.ix_(pq, pq)]

    Asys = vstack([hstack([A11, A12]),
                   hstack([A21, A22])], format="csc")

    # compose the right hand side (power vectors)
    rhs = np.r_[Sbus.real[pvpq], Sbus.imag[pq]]

    # solve the linear system
    x = factorized(Asys)(rhs)

    # compose the results vector
    voltages_vector = Vbus.copy()

    #  set the pv voltages
    va_pv = x[0:npv]
    vm_pv = np.abs(Vbus[pv])
    voltages_vector[pv] = vm_pv * np.exp(1j * va_pv)

    # set the PQ voltages
    va_pq = x[npv:npv+npq]
    vm_pq = np.ones(npq) + x[npv+npq::]
    voltages_vector[pq] = vm_pq * np.exp(1j * va_pq)

    # Calculate the error and check the convergence
    s_calc = voltages_vector * np.conj(Ybus * voltages_vector)
    # complex power mismatch
    power_mismatch = s_calc - Sbus
    # concatenate error by type
    mismatch = np.r_[power_mismatch[pv].real, power_mismatch[pq].real, power_mismatch[pq].imag]

    # check for convergence
    norm_f = np.linalg.norm(mismatch, np.Inf)

    return voltages_vector, True, norm_f


def z_matrix_power_flow(Vbus, Sbus, Ibus, Ybus,
                        P0, Q0, exp_p, exp_q, V0,
                        A, B, C,
                        pq, pv, ref, tol, max_iter, verbose=False):
    """
    Solves the power flow using a full Newton's method with the Iwamoto optimal step factor.
    Args:
        Vbus: Array of nodal voltages (initial solution)
        Sbus: Array of nodal power injections
        Ibus: Array of nodal current injections
        Ybus: Admittance matrix
        P0: Exponential load parameter P0
        Q0: Exponential load parameter Q0
        exp_p: Exponential load parameter exp_p
        exp_q: Exponential load parameter exp_q
        V0: Exponential load parameter V0
        A: Polynomial load parameter A
        B: Polynomial load parameter B
        C: Polynomial load parameter C
        pv: Array with the indices of the PV buses
        pq: Array with the indices of the PQ buses
        tol: Tolerance
        max_it: Maximum number of iterations
        robust: Boolean variable for the use of the Iwamoto optimal step factor.
    Returns:
        Voltage solution, converged?, error, calculated power injections

    @Author: Santiago Penate Vera
    """

    """
    From the paper:  Three-phase distribution network fast-decoupled power flow solutions
    
    |G  -B||de|   |dIr|
    |     ||  | = |   |
    |B   G||df|   |dIi|
    
    """

    pqpv = np.r_[pq, pv].astype(int)
    npq = len(pq)
    npv = len(pv)

    # reduced impedance matrix
    Zred = factorized(Ybus[pqpv, :][:, pqpv])

    # slack currents
    Ivd = Ybus[pqpv, :][:, ref].dot(Vbus[ref])
    print('Ivd', np.vstack(Ivd))

    # slack voltages influence
    Ck = Zred(Ivd)
    print('Ck', np.vstack(Ck))

    # make a copy of the voltage for convergence control
    Vprev = Vbus[pqpv].copy()

    # Voltage module in the pv nodes
    Vpv = np.abs(Vbus[pv])

    # admittance matrix to compute the reactive power
    Ybus_pv = Ybus[pv, :][:, pv]

    # approximate the currents with the current voltage solution
    Ik = np.conj(Sbus[pqpv] / Vprev) + Ibus[pqpv]
    print('Sred', np.vstack(Sbus[pqpv]))
    print('Ik', np.vstack(Ik))

    # compute the new voltage solution
    Vk = Zred(Ik) - Ck
    print('Vk', np.vstack(Vk))

    # compute the voltage solution maximum difference
    diff = np.max(np.abs(Vprev - Vk))

    iter = 1
    while diff > tol and iter < max_iter:
        # make a copy of the voltage for convergence control
        Vprev = Vk

        # approximate the currents with the current voltage solution
        Ik = np.conj(Sbus[pqpv] / Vprev) + Ibus[pqpv]

        # compute the new voltage solution
        Vk = Zred(Ik) - Ck
        print(iter, 'Vk', Vk)
        print()
        # tune PV nodes
        #  ****** USE A reduced pv, pv, pqpv mapping!
        # Vk[pv] *= Vpv / abs(Vk[pv])
        # Qpv = (Vk * conj(Ybus[pv, :][:, pv].dot(Vk) - Ibus))[pv].imag
        # Sbus[pv] = Sbus[pv].real + 1j * Qpv

        # compute the voltage solution maximum difference
        diff = np.max(np.abs(Vprev - Vk))

        # Assign the reduced voltage solution to the complete voltage solution
        # voltage = Vbus.copy()  # the slack voltages are kept
        # voltage[pqpv] = Vk
        # compute the power mismatch: this is the true equation solution check
        # Scalc = voltage * conj(Ybus * voltage - Ibus)
        # mis = Scalc - Sbus  # complex power mismatch
        # diff = linalg.norm(r_[mis[pv].real, mis[pq].real, mis[pq].imag], Inf)

        iter += 1

    # Assign the reduced voltage solution to the complete voltage solution
    voltage = Vbus.copy()  # the slack voltages are kept
    voltage[pqpv] = Vk

    print(iter, 'voltage:\n', np.vstack(voltage))
    print()

    # compute the power mismatch: this is the true equation solution check
    Scalc = voltage * np.conj(Ybus * voltage - Ibus)
    mis = Scalc - Sbus  # complex power mismatch
    norm_f = np.linalg.norm(np.r_[mis[pv].real, mis[pq].real, mis[pq].imag], np.Inf)

    return voltage, True, norm_f


def gauss_raphson_power_flow(Vbus, Sbus, Ibus, Ybus,
                             P0, Q0, exp_p, exp_q, V0,
                             A, B, C,
                             pq, pv, ref, tol, max_iter, verbose=False):
    """
    Solves the power flow using a full Newton's method with the Iwamoto optimal step factor.
    Args:
        Vbus: Array of nodal voltages (initial solution)
        Sbus: Array of nodal power injections
        Ibus: Array of nodal current injections
        Ybus: Admittance matrix
        P0: Exponential load parameter P0
        Q0: Exponential load parameter Q0
        exp_p: Exponential load parameter exp_p
        exp_q: Exponential load parameter exp_q
        V0: Exponential load parameter V0
        A: Polynomial load parameter A
        B: Polynomial load parameter B
        C: Polynomial load parameter C
        pv: Array with the indices of the PV buses
        pq: Array with the indices of the PQ buses
        tol: Tolerance
        max_it: Maximum number of iterations
        robust: Boolean variable for the use of the Iwamoto optimal step factor.
    Returns:
        Voltage solution, converged?, error, calculated power injections

    @Author: Santiago Penate Vera
    """

    """
    From the paper:  Three-phase distribution network fast-decoupled power flow solutions

    |G  -B||de|   |dIr|
    |     ||  | = |   |
    |B   G||df|   |dIi|

    """

    pvpq = np.r_[pv, pq].astype(int)
    npq = len(pq)
    npv = len(pv)
    npvpq = npv + npq

    V = Vbus.copy()
    G = Ybus.real[pvpq, :][:, pvpq]
    B = Ybus.imag[pvpq, :][:, pvpq]

    J = vstack([hstack([G, B]),
                hstack([B, G])], format="csc")

    for i in range(1):
        # complex current mismatch
        Isp = np.conj(Sbus / V)
        Icalc = Ybus * V
        dI = Isp - Icalc
        I = np.hstack((dI.real[pvpq], dI.imag[pvpq]))

        # solve the rectangular voltage increments
        # x = spsolve(J, I)
        # x = J * I

        # assign the voltage values
        dVr = spsolve(G, dI.real[pvpq])
        dVi = spsolve(G, dI.imag[pvpq])

        V[pvpq] -= dVr + 1j * dVi
        print("V: ", np.abs(V))

    # Calculate the error and check the convergence
    s_calc = V * np.conj(Ybus * V)
    # complex power mismatch
    power_mismatch = s_calc - Sbus
    # concatenate error by type
    mismatch = np.r_[power_mismatch[pv].real, power_mismatch[pq].real, power_mismatch[pq].imag]

    # check for convergence
    norm_f = np.linalg.norm(mismatch, np.Inf)

    return V, True, norm_f


def fast_decoupled_power_flow(Vbus, Sbus, Ibus, Ybus, B1, B2, pq, pv, pqpv, tol=1e-9, max_iter=100):
    """

    :param Vbus:
    :param Sbus:
    :param Ibus:
    :param Ybus:
    :param B1:
    :param B2:
    :param pq:
    :param pv:
    :param pqpv:
    :param tol:
    :param max_iter:
    :return:
    """

    # set voltage vector for the iterations
    voltage = Vbus.copy()
    Va = np.angle(voltage)
    Vm = np.abs(voltage)

    # Factorize B1 and B2
    J1 = splu(B1[pqpv, :][:, pqpv])
    J2 = splu(B2[pq, :][:, pq])

    # evaluate initial mismatch
    Scalc = voltage * np.conj(Ybus * voltage - Ibus)
    mis = Scalc - Sbus  # complex power mismatch
    incP = mis[pqpv].real
    incQ = mis[pq].imag
    normP = np.norm(incP, np.Inf)
    normQ = np.norm(incQ, np.Inf)
    if normP < tol and normQ < tol:
        converged = True
    else:
        converged = False

    # iterate
    iter_ = 0
    while not converged and iter_ < max_iter:

        iter_ += 1

        # solve voltage angles
        dVa = -J1.solve(incP)

        # update voltage
        Va[pqpv] = Va[pqpv] + dVa
        voltage = Vm * np.exp(1j * Va)

        # evaluate mismatch
        Scalc = voltage * np.conj(Ybus * voltage - Ibus)
        mis = Scalc - Sbus  # complex power mismatch
        incP = mis[pqpv].real
        incQ = mis[pq].imag
        normP = np.norm(incP, np.Inf)
        normQ = np.norm(incQ, np.Inf)

        if normP < tol and normQ < tol:
            converged = True

        else:
            # Solve voltage modules
            dVm = -J2.solve(incQ)

            # update voltage
            Vm[pq] = Vm[pq] + dVm
            voltage = Vm * np.exp(1j * Va)

            # evaluate mismatch
            Scalc = voltage * np.conj(Ybus * voltage - Ibus)
            mis = Scalc - Sbus  # complex power mismatch
            incP = mis[pqpv].real
            incQ = mis[pq].imag
            normP = np.norm(incP, np.Inf)
            normQ = np.norm(incQ, np.Inf)

            if normP < tol and normQ < tol:
                converged = True

    # evaluate F(x)
    Scalc = voltage * np.conj(Ybus * voltage - Ibus)
    mis = Scalc - Sbus  # complex power mismatch
    F = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again

    # check for convergence
    normF = np.norm(F, np.Inf)

    return voltage, converged, normF