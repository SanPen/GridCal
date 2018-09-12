from scipy.sparse import hstack as sphs, vstack as spvs, csc_matrix, csr_matrix
from scipy.sparse.linalg import spsolve
import numpy as np
from numpy import conj, arange


def dSbus_dV(Ybus, V):
    """
    
    :param Ybus: 
    :param V: 
    :return: 
    """

    """Computes partial derivatives of power injection w.r.t. voltage.

    Returns two matrices containing partial derivatives of the complex bus
    power injections w.r.t voltage magnitude and voltage angle respectively
    (for all buses). If C{Ybus} is a sparse matrix, the return values will be
    also. The following explains the expressions used to form the matrices::

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
    """
    nb = len(V)
    ib = arange(nb)

    Ibus = Ybus * V

    diagV = csr_matrix((V, (ib, ib)))
    diagIbus = csr_matrix((Ibus, (ib, ib)))
    diagVnorm = csr_matrix((V / abs(V), (ib, ib)))

    dS_dVm = diagV * conj(Ybus * diagVnorm) + conj(diagIbus) * diagVnorm
    dS_dVa = 1j * diagV * conj(diagIbus - Ybus * diagV)

    return dS_dVm, dS_dVa


def dSbr_dV(Yf, Yt, V, f, t):
    """
    
    :param Yf: 
    :param Yt: 
    :param V: 
    :param f: 
    :param t: 
    :return: 
    """

    """Computes partial derivatives of power flows w.r.t. voltage.

    returns four matrices containing partial derivatives of the complex
    branch power flows at "from" and "to" ends of each branch w.r.t voltage
    magnitude and voltage angle respectively (for all buses). If C{Yf} is a
    sparse matrix, the partial derivative matrices will be as well. Optionally
    returns vectors containing the power flows themselves. The following
    explains the expressions used to form the matrices::

        If = Yf * V;
        Sf = diag(Vf) * conj(If) = diag(conj(If)) * Vf

    Partials of V, Vf & If w.r.t. voltage angles::
        dV/dVa  = j * diag(V)
        dVf/dVa = sparse(range(nl), f, j*V(f)) = j * sparse(range(nl), f, V(f))
        dIf/dVa = Yf * dV/dVa = Yf * j * diag(V)

    Partials of V, Vf & If w.r.t. voltage magnitudes::
        dV/dVm  = diag(V / abs(V))
        dVf/dVm = sparse(range(nl), f, V(f) / abs(V(f))
        dIf/dVm = Yf * dV/dVm = Yf * diag(V / abs(V))

    Partials of Sf w.r.t. voltage angles::
        dSf/dVa = diag(Vf) * conj(dIf/dVa)
                        + diag(conj(If)) * dVf/dVa
                = diag(Vf) * conj(Yf * j * diag(V))
                        + conj(diag(If)) * j * sparse(range(nl), f, V(f))
                = -j * diag(Vf) * conj(Yf * diag(V))
                        + j * conj(diag(If)) * sparse(range(nl), f, V(f))
                = j * (conj(diag(If)) * sparse(range(nl), f, V(f))
                        - diag(Vf) * conj(Yf * diag(V)))

    Partials of Sf w.r.t. voltage magnitudes::
        dSf/dVm = diag(Vf) * conj(dIf/dVm)
                        + diag(conj(If)) * dVf/dVm
                = diag(Vf) * conj(Yf * diag(V / abs(V)))
                        + conj(diag(If)) * sparse(range(nl), f, V(f)/abs(V(f)))

    Derivations for "to" bus are similar.

    For more details on the derivations behind the derivative code used
    in PYPOWER information, see:

    [TN2]  R. D. Zimmerman, "AC Power Flows, Generalized OPF Costs and
    their Derivatives using Complex Matrix Notation", MATPOWER
    Technical Note 2, February 2010.
    U{http://www.pserc.cornell.edu/matpower/TN2-OPF-Derivatives.pdf}

    @author: Ray Zimmerman (PSERC Cornell)
    """
    # define
    nl = len(f)
    nb = len(V)
    il = arange(nl)
    ib = arange(nb)

    Vnorm = V / abs(V)

    # compute currents
    If = Yf * V
    It = Yt * V

    diagVf = csr_matrix((V[f], (il, il)))
    diagIf = csr_matrix((If, (il, il)))
    diagVt = csr_matrix((V[t], (il, il)))
    diagIt = csr_matrix((It, (il, il)))
    diagV  = csr_matrix((V, (ib, ib)))
    diagVnorm = csr_matrix((Vnorm, (ib, ib)))

    shape = (nl, nb)
    # Partial derivative of S w.r.t voltage phase angle.
    dSf_dVa = 1j * (conj(diagIf) * csr_matrix((V[f], (il, f)), shape) - diagVf * conj(Yf * diagV))

    dSt_dVa = 1j * (conj(diagIt) * csr_matrix((V[t], (il, t)), shape) - diagVt * conj(Yt * diagV))

    # Partial derivative of S w.r.t. voltage amplitude.
    dSf_dVm = diagVf * conj(Yf * diagVnorm) + conj(diagIf) * csr_matrix((Vnorm[f], (il, f)), shape)

    dSt_dVm = diagVt * conj(Yt * diagVnorm) + conj(diagIt) * csr_matrix((Vnorm[t], (il, t)), shape)

    # Compute power flow vectors.
    Sf = V[f] * conj(If)
    St = V[t] * conj(It)

    return dSf_dVa, dSf_dVm, dSt_dVa, dSt_dVm, Sf, St


def dIbr_dV(Yf, Yt, V):
    """
    Computes partial derivatives of branch currents w.r.t. voltage
    :param Yf: 
    :param Yt: 
    :param V: 
    :return: 
    """
    """Computes partial derivatives of branch currents w.r.t. voltage.

    Returns four matrices containing partial derivatives of the complex
    branch currents at "from" and "to" ends of each branch w.r.t voltage
    magnitude and voltage angle respectively (for all buses). If C{Yf} is a
    sparse matrix, the partial derivative matrices will be as well. Optionally
    returns vectors containing the currents themselves. The following
    explains the expressions used to form the matrices::

        If = Yf * V

    Partials of V, Vf & If w.r.t. voltage angles::
        dV/dVa  = j * diag(V)
        dVf/dVa = sparse(range(nl), f, j*V(f)) = j * sparse(range(nl), f, V(f))
        dIf/dVa = Yf * dV/dVa = Yf * j * diag(V)

    Partials of V, Vf & If w.r.t. voltage magnitudes::
        dV/dVm  = diag(V / abs(V))
        dVf/dVm = sparse(range(nl), f, V(f) / abs(V(f))
        dIf/dVm = Yf * dV/dVm = Yf * diag(V / abs(V))

    Derivations for "to" bus are similar.

    @author: Ray Zimmerman (PSERC Cornell)
    """
    nb = len(V)
    ib = arange(nb)

    Vnorm = V / np.abs(V)

    diagV = csr_matrix((V, (ib, ib)))
    diagVnorm = csr_matrix((Vnorm, (ib, ib)))

    dIf_dVa = Yf * 1j * diagV
    dIf_dVm = Yf * diagVnorm
    dIt_dVa = Yt * 1j * diagV
    dIt_dVm = Yt * diagVnorm

    # Compute currents.
    If = Yf * V
    It = Yt * V

    return dIf_dVa, dIf_dVm, dIt_dVa, dIt_dVm, If, It


def Jacobian_SE(Ybus, Yf, Yt, V, f, t, inputs, pvpq):
    """
    
    :param Ybus: 
    :param Yf: 
    :param Yt: 
    :param V: 
    :param f: 
    :param t: 
    :param inputs: instance of StateEstimationInput
    :param pvpq: 
    :return: 
    """
    n = Ybus.shape[0]
    I = Ybus * V
    S = V * np.conj(I)
    # If = Yf * V
    # Sf = (Ct * V) * np.conj(If)
    dS_dVm, dS_dVa = dSbus_dV(Ybus, V)
    dSf_dVa, dSf_dVm, dSt_dVa, dSt_dVm, Sf, St = dSbr_dV(Yf, Yt, V, f, t)
    dIf_dVa, dIf_dVm, dIt_dVa, dIt_dVm, If, It = dIbr_dV(Yf, Yt, V)

    # for the sub-jacobians
    H11 = dSf_dVa[inputs.p_flow_idx, :][:, pvpq].real
    H12 = dSf_dVm[inputs.p_flow_idx, :][:, :].real

    H21 = dS_dVa[inputs.p_inj_idx, :][:, pvpq].real
    H22 = dS_dVm[inputs.p_inj_idx, :][:, :].real

    H31 = dSf_dVa[inputs.q_flow_idx, :][:, pvpq].imag
    H32 = dSf_dVm[inputs.q_flow_idx, :][:, :].imag

    H41 = dS_dVa[inputs.q_inj_idx, :][:, pvpq].imag
    H42 = dS_dVm[inputs.q_inj_idx, :][:, :].imag

    H51 = np.abs(dIf_dVa[inputs.i_flow_idx, :][:, pvpq])
    H52 = np.abs(dIf_dVm[inputs.i_flow_idx, :][:, :])

    H61 = csc_matrix(np.zeros((len(inputs.vm_m_idx), len(pvpq))))
    H62 = csc_matrix(np.diag(np.ones(n))[inputs.vm_m_idx, :])

    # pack the Jacobian
    H = spvs([sphs([H11, H12]),
              sphs([H21, H22]),
              sphs([H31, H32]),
              sphs([H41, H42]),
              sphs([H51, H52]),
              sphs([H61, H62])])

    # form the sub-mismatch vectors
    h1 = Sf[inputs.p_flow_idx].real
    h2 = S[inputs.p_inj_idx].real

    h3 = Sf[inputs.q_flow_idx].imag
    h4 = S[inputs.q_inj_idx].imag

    h5 = np.abs(If[inputs.i_flow_idx])
    h6 = np.abs(V[inputs.vm_m_idx])

    # pack the mismatch vector
    h = np.r_[h1, h2, h3, h4, h5, h6]

    return H, h


def solve_se_lm(Ybus, Yf, Yt, f, t, se_input, ref, pq, pv):
    """
    Solve the state estimation problem using the Levenberg-Marquadt method
    :param Ybus: 
    :param Yf: 
    :param Yt: 
    :param f: array with the from bus indices of all the branches
    :param t: array with the to bus indices of all the branches
    :param inputs: state estimation imput instance (contains the measurements)
    :param ref: 
    :param pq: 
    :param pv: 
    :return: 
    """

    pvpq = np.r_[pv, pq]
    npvpq = len(pvpq)
    npq = len(pq)
    nvd = len(ref)
    n = Ybus.shape[0]
    V = np.ones(n, dtype=complex)

    # pick the measurements and uncertainties
    z, sigma = se_input.consolidate()

    # compute the weights matrix
    W = csc_matrix(np.diag(1.0 / np.power(sigma, 2.0)))

    # Levenberg-Marquardt method
    tol = 1e-9
    max_iter = 100
    iter_ = 0
    Idn = csc_matrix(np.identity(2 * n - nvd))  # identity matrix
    x = np.r_[np.angle(V)[pvpq], np.abs(V)]
    Va = np.angle(V)
    Vm = np.abs(V)
    lbmda = 0  # any large number
    f_obj_prev = 1e9  # very large number

    update_jacobian = True
    converged = False
    nu = 2.0

    while not converged and iter_ < max_iter:

        if update_jacobian:
            H, h = Jacobian_SE(Ybus, Yf, Yt, V, f, t, se_input, pvpq)

        # measurements error
        dz = z - h

        # System matrix
        # H1 = H^t·W
        H1 = H.transpose().dot(W)
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
        dx = spsolve(A, rhs)

        # objective function
        f_obj = 0.5 * dz.dot(W * dz)

        # decision function
        rho = (f_obj_prev - f_obj) / (0.5 * dx.dot(lbmda * dx + rhs))

        # print('/' * 180)
        # print('/' * 180)
        # print('\niter ', iter_, ' >> lbmda:', lbmda, '\tfmin:', f, ' -> \ndx:', dx, '\tx', x)
        # print('H:\n', H.todense())
        # print('A:\n', A.todense())
        # print('RHS:', rhs)
        # print('z: ', z, '\nh_: ', h, '\ndz: ', dz)

        # lambda update
        if rho > 0:
            update_jacobian = True
            lbmda = lbmda * max([1.0 / 3.0, 1 - (2 * rho - 1) ** 3])
            nu = 2.0

            # modify the solution
            dVa = dx[0:npvpq]
            dVm = dx[npvpq:npvpq + npq + 1]
            Va[pvpq] += dVa
            Vm += dVm
            V = Vm * np.exp(1j * Va)

            # print('Vm: ', Vm, '\nVa: ', Va, '\nV: ', V)

        else:
            update_jacobian = False
            lbmda = lbmda * nu
            nu = nu * 2
            converged = False

        # compute the convergence
        err = np.linalg.norm(dx, np.Inf)
        converged = err < tol

        # update loops
        f_obj_prev = f_obj
        iter_ += 1

    return V, err, converged


if __name__ == '__main__':

    from GridCal.Engine.CalculationEngine import *

    np.set_printoptions(linewidth=10000)

    m_circuit = MultiCircuit()

    b1 = Bus('B1', is_slack=True)
    b2 = Bus('B2')
    b3 = Bus('B3')

    br1 = Branch(b1, b2, 'Br1', 0.01, 0.03)
    br2 = Branch(b1, b3, 'Br2', 0.02, 0.05)
    br3 = Branch(b2, b3, 'Br3', 0.03, 0.08)

    # add measurements
    br1.measurements.append(Measurement(0.888, 0.008, MeasurementType.Pflow))
    br2.measurements.append(Measurement(1.173, 0.008, MeasurementType.Pflow))

    b2.measurements.append(Measurement(-0.501, 0.01, MeasurementType.Pinj))

    br1.measurements.append(Measurement(0.568, 0.008, MeasurementType.Qflow))
    br2.measurements.append(Measurement(0.663, 0.008, MeasurementType.Qflow))

    b2.measurements.append(Measurement(-0.286, 0.01, MeasurementType.Qinj))

    b1.measurements.append(Measurement(1.006, 0.004, MeasurementType.Vmag))
    b2.measurements.append(Measurement(0.968, 0.004, MeasurementType.Vmag))

    m_circuit.add_bus(b1)
    m_circuit.add_bus(b2)
    m_circuit.add_bus(b3)

    m_circuit.add_branch(br1)
    m_circuit.add_branch(br2)
    m_circuit.add_branch(br3)

    br = [br1, br2, br3]

    m_circuit.compile()

    circuit = m_circuit.circuits[0]

    se = StateEstimation(circuit=m_circuit)

    # se.run()

    se.run()

    print()
    print('V: ', se.se_results.voltage)
    print('Vm: ', np.abs(se.se_results.voltage))
    print('Va: ', np.angle(se.se_results.voltage))

    """
    The validated output is:
    
    V:  [0.99962926+0.j         0.97392515-0.02120941j 0.94280676-0.04521561j]
    Vm:  [0.99962926 0.97415607 0.94389038]
    Va:  [ 0.        -0.0217738 -0.0479218]
    """