# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import time

from scipy.sparse import hstack as sphs, vstack as spvs, csc_matrix, csr_matrix
from scipy.sparse.linalg import spsolve
import numpy as np
from numpy import conj, arange
from GridCalEngine.Simulations.StateEstimation.state_estimation_inputs import StateEstimationInput
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import power_flow_post_process_nonlinear
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.basic_structures import CscMat, IntVec, CxVec


def dSbus_dV(Ybus, V):
    """
    
    :param Ybus: 
    :param V: 
    :return: 
    """

    """Computes partial derivatives of power injection w.r.t. voltage.

    Returns two matrices containing partial derivatives of the complex bus
    power Injections w.r.t voltage magnitude and voltage angle respectively
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

    """Computes partial derivatives of power Sf w.r.t. voltage.

    returns four matrices containing partial derivatives of the complex
    branch power Sf at "from" and "to" ends of each branch w.r.t voltage
    magnitude and voltage angle respectively (for all buses). If C{Yf} is a
    sparse matrix, the partial derivative matrices will be as well. Optionally
    returns vectors containing the power Sf themselves. The following
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
    diagV = csr_matrix((V, (ib, ib)))
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
    dPf_dVa = dSf_dVa[np.ix_(inputs.pf_idx, pvpq)].real
    dPf_dVm = dSf_dVm[inputs.pf_idx, :].real

    dP_dVa = dS_dVa[np.ix_(inputs.p_idx, pvpq)].real
    dP_dVm = dS_dVm[inputs.p_idx, :].real

    dQf_dVa = dSf_dVa[np.ix_(inputs.qf_idx, pvpq)].imag
    dQf_dVm = dSf_dVm[inputs.qf_idx, :].imag

    dQ_dVa = dS_dVa[np.ix_(inputs.q_idx, pvpq)].imag
    dQ_dVm = dS_dVm[inputs.q_idx, :].imag

    dIf_dVa = np.abs(dIf_dVa[np.ix_(inputs.i_flow_idx, pvpq)])
    dIf_dVm = np.abs(dIf_dVm[inputs.i_flow_idx, :])

    dVm_dVa = csc_matrix(np.zeros((len(inputs.vm_m_idx), len(pvpq))))
    dVm_dVm = csc_matrix(np.diag(np.ones(n))[inputs.vm_m_idx, :])

    # pack the Jacobian
    H = spvs([sphs([dPf_dVa, dPf_dVm]),
              sphs([dP_dVa, dP_dVm]),
              sphs([dQf_dVa, dQf_dVm]),
              sphs([dQ_dVa, dQ_dVm]),
              sphs([dIf_dVa, dIf_dVm]),
              sphs([dVm_dVa, dVm_dVm])])

    # form the sub-mismatch vectors

    # pack the mismatch vector
    h = np.r_[
        Sf[inputs.pf_idx].real,
        S[inputs.p_idx].real,
        Sf[inputs.qf_idx].imag,
        S[inputs.q_idx].imag,
        np.abs(If[inputs.i_flow_idx]),
        np.abs(V[inputs.vm_m_idx])
    ]

    return H, h, S


def solve_se_lm(nc: NumericalCircuit,
                Ybus: CscMat, Yf: CscMat, Yt: CscMat, Yshunt_bus: CxVec,
                F: IntVec, T: IntVec, se_input: StateEstimationInput,
                vd: IntVec, pq: IntVec, pv: IntVec) -> NumericPowerFlowResults:
    """
    Solve the state estimation problem using the Levenberg-Marquadt method
    :param nc: instance of NumericalCircuit
    :param Ybus: Admittance matrix
    :param Yf: Admittance matrix of the from Branches
    :param Yt: Admittance matrix of the to Branches
    :param F: array with the from bus indices of all the Branches
    :param T: array with the to bus indices of all the Branches
    :param se_input: state estimation input instance (contains the measurements)
    :param vd: array of slack node indices
    :param pq: array of pq node indices
    :param pv: array of pv node indices
    :return: NumericPowerFlowResults instance
    """
    start_time = time.time()
    pvpq = np.r_[pv, pq]
    npvpq = len(pvpq)
    npq = len(pq)
    nvd = len(vd)
    n = Ybus.shape[0]
    V = np.ones(n, dtype=complex)

    # pick the measurements and uncertainties
    z, sigma = se_input.get_measurements_and_deviations()

    # compute the weights matrix
    W = csc_matrix(np.diag(1.0 / np.power(sigma, 2.0)))

    # Levenberg-Marquardt method
    tol = 1e-9
    max_iter = 100
    iter_ = 0
    Idn = csc_matrix(np.identity(2 * n - nvd))  # identity matrix
    Va = np.angle(V)
    Vm = np.abs(V)
    lbmda = 0  # any large number
    f_obj_prev = 1e9  # very large number

    converged = False
    norm_f = 1e20
    nu = 2.0

    # first computation of the jacobian and free term
    H, h, Scalc = Jacobian_SE(Ybus, Yf, Yt, V, F, T, se_input, pvpq)

    while not converged and iter_ < max_iter:

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

        # lambda update
        if rho > 0:
            lbmda = lbmda * max([1.0 / 3.0, 1 - (2 * rho - 1) ** 3])
            nu = 2.0

            # modify the solution
            dVa = dx[:npvpq]
            dVm = dx[npvpq:]
            Va[pvpq] += dVa
            Vm += dVm  # yes, this is for all the buses
            V = Vm * np.exp(1j * Va)

            # update Jacobian
            H, h, Scalc = Jacobian_SE(Ybus, Yf, Yt, V, F, T, se_input, pvpq)

        else:
            lbmda = lbmda * nu
            nu = nu * 2

        # compute the convergence
        norm_f = np.linalg.norm(dx, np.inf)
        converged = norm_f < tol

        # update loops
        f_obj_prev = f_obj
        iter_ += 1

    elapsed = time.time() - start_time

    # Compute the Branches power and the slack buses power
    Sf, St, If, It, Vbranch, loading, losses, Sbus = power_flow_post_process_nonlinear(
        Sbus=Scalc,
        V=V,
        F=nc.passive_branch_data.F,
        T=nc.passive_branch_data.T,
        pv=pv,
        vd=vd,
        Ybus=Ybus,
        Yf=Yf,
        Yt=Yt,
        Yshunt_bus=Yshunt_bus,
        branch_rates=nc.passive_branch_data.rates,
        Sbase=nc.Sbase)

    return NumericPowerFlowResults(V=V,
                                   Scalc=Scalc,
                                   m=np.ones(nc.nbr, dtype=float),
                                   tau=np.zeros(nc.nbr, dtype=float),
                                   Sf=Sf,
                                   St=St,
                                   If=If,
                                   It=It,
                                   loading=loading,
                                   losses=losses,
                                   Pf_vsc=np.zeros(nc.nvsc, dtype=float),
                                   St_vsc=np.zeros(nc.nvsc, dtype=complex),
                                   If_vsc=np.zeros(nc.nvsc, dtype=float),
                                   It_vsc=np.zeros(nc.nvsc, dtype=complex),
                                   losses_vsc=np.zeros(nc.nvsc, dtype=float),
                                   loading_vsc=np.zeros(nc.nvsc, dtype=float),
                                   Sf_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                   St_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                   losses_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                   loading_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                   norm_f=norm_f,
                                   converged=converged,
                                   iterations=iter_,
                                   elapsed=elapsed)
