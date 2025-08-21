# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from typing import Tuple
from scipy.sparse import diags, csc_matrix, vstack, hstack
from GridCalEngine.basic_structures import CxVec, IntVec, Vec


def dSbus_dV_matpower(Ybus: csc_matrix, V: CxVec) -> Tuple[csc_matrix, csc_matrix]:
    """
    Derivatives of the power Injections w.r.t the voltage
    :param Ybus: Admittance matrix
    :param V: complex voltage arrays
    :return: dSbus_dVa, dSbus_dVm
    """
    diagV = diags(V)
    diagE = diags(V / np.abs(V))
    Ibus = Ybus * V
    diagIbus = diags(Ibus)

    dSbus_dVa = 1j * diagV * np.conj(diagIbus - Ybus * diagV)  # dSbus / dVa
    dSbus_dVm = diagV * np.conj(Ybus * diagE) + np.conj(diagIbus) * diagE  # dSbus / dVm

    return dSbus_dVa.tocsc(), dSbus_dVm.tocsc()


def dSbr_dV_matpower(Yf: csc_matrix, Yt: csc_matrix, V: CxVec,
                     F: IntVec, T: IntVec,
                     Cf: csc_matrix, Ct: csc_matrix) -> Tuple[csc_matrix, csc_matrix, csc_matrix, csc_matrix]:
    """
    Derivatives of the branch power w.r.t the branch voltage modules and angles
    :param Yf: Admittances matrix of the Branches with the "from" buses
    :param Yt: Admittances matrix of the Branches with the "to" buses
    :param V: Array of voltages
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Cf: Connectivity matrix of the Branches with the "from" buses
    :param Ct: Connectivity matrix of the Branches with the "to" buses
    :return: dSf_dVa, dSf_dVm, dSt_dVa, dSt_dVm
    """
    Yfc = np.conj(Yf)
    Ytc = np.conj(Yt)
    Vc = np.conj(V)
    Ifc = Yfc * Vc  # conjugate  of "from"  current
    Itc = Ytc * Vc  # conjugate of "to" current

    diagIfc = diags(Ifc)
    diagItc = diags(Itc)
    Vf = V[F]
    Vt = V[T]
    diagVf = diags(Vf)
    diagVt = diags(Vt)
    diagVc = diags(Vc)

    Vnorm = V / np.abs(V)
    diagVnorm = diags(Vnorm)
    diagV = diags(V)

    CVf = Cf * diagV
    CVt = Ct * diagV
    CVnf = Cf * diagVnorm
    CVnt = Ct * diagVnorm

    dSf_dVa = 1j * (diagIfc * CVf - diagVf * Yfc * diagVc)
    dSf_dVm = diagVf * np.conj(Yf * diagVnorm) + diagIfc * CVnf
    dSt_dVa = 1j * (diagItc * CVt - diagVt * Ytc * diagVc)
    dSt_dVm = diagVt * np.conj(Yt * diagVnorm) + diagItc * CVnt

    return dSf_dVa.tocsc(), dSf_dVm.tocsc(), dSt_dVa.tocsc(), dSt_dVm.tocsc()


def dSf_dV_matpower(Yf: csc_matrix, V: CxVec, F: IntVec,
                    Cf: csc_matrix, Vc: CxVec,
                    diagVc: csc_matrix,
                    diagE: csc_matrix,
                    diagV: csc_matrix) -> Tuple[csc_matrix, csc_matrix]:
    """
    Derivatives of the branch power "from" w.r.t the branch voltage modules and angles
    :param Yf: Admittances matrix of the Branches with the "from" buses
    :param V: Array of voltages
    :param F: Array of branch "from" bus indices
    :param Cf: Connectivity matrix of the Branches with the "from" buses
    :param Vc: array of conjugate voltages
    :param diagVc: diagonal matrix of conjugate voltages
    :param diagE: diagonal matrix of normalized voltages
    :param diagV: diagonal matrix of voltages
    :return: dSf_dVa, dSf_dVm
    """

    Yfc = np.conj(Yf)
    Ifc = Yfc * Vc  # conjugate  of "from"  current

    diagIfc = diags(Ifc)
    Vf = V[F]
    diagVf = diags(Vf)

    CVf = Cf * diagV
    CVnf = Cf * diagE

    dSf_dVa = 1j * (diagIfc * CVf - diagVf * Yfc * diagVc)
    dSf_dVm = diagVf * np.conj(Yf * diagE) + diagIfc * CVnf

    return dSf_dVa.tocsc(), dSf_dVm.tocsc()


def dIbr_dV_matpower(Yf: csc_matrix, Yt: csc_matrix, V: CxVec):
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
    ib = np.arange(nb)

    Vnorm = V / np.abs(V)

    diagV = csc_matrix((V, (ib, ib)))
    diagVnorm = csc_matrix((Vnorm, (ib, ib)))

    dIf_dVa = Yf * 1j * diagV
    dIf_dVm = Yf * diagVnorm
    dIt_dVa = Yt * 1j * diagV
    dIt_dVm = Yt * diagVnorm

    return dIf_dVa, dIf_dVm, dIt_dVa, dIt_dVm


def dSt_dV_matpower(Yt, V, T, Ct, Vc, diagVc, diagE, diagV):
    """
    Derivatives of the branch power "to" w.r.t the branch voltage modules and angles
    :param Yt: Admittances matrix of the Branches with the "to" buses
    :param V: Array of voltages
    :param T: Array of branch "to" bus indices
    :param Ct: Connectivity matrix of the Branches with the "to" buses
    :param Vc: array of conjugate voltages
    :param diagVc: diagonal matrix of conjugate voltages
    :param diagE: diagonal matrix of normalized voltages
    :param diagV: diagonal matrix of voltages
    :return: dSf_dVa, dSf_dVm, dSt_dVa, dSt_dVm
    """
    Ytc = np.conj(Yt)
    Itc = Ytc * Vc  # conjugate of "to" current

    diagItc = diags(Itc)
    Vt = V[T]
    diagVt = diags(Vt)

    CVt = Ct * diagV
    CVnt = Ct * diagE

    dSt_dVa = 1j * (diagItc * CVt - diagVt * Ytc * diagVc)
    dSt_dVm = diagVt * np.conj(Yt * diagE) + diagItc * CVnt

    return dSt_dVa.tocsc(), dSt_dVm.tocsc()


def dS_dm_matpower(V: CxVec, Cf: csc_matrix, Ct: csc_matrix,
                   R: Vec, X: Vec, B: Vec, Beq: Vec, k2: Vec, m: Vec, tau: Vec):
    """

    :param V:
    :param Cf:
    :param Ct:
    :param R:
    :param X:
    :param B:
    :param Beq:
    :param k2:
    :param m:
    :param tau:
    :return:
    """
    diagV = diags(V)
    Vf = Cf @ V
    Vt = Ct @ V
    diagVf = diags(Vf)
    diagVt = diags(Vt)

    ys = 1.0 / (R + 1j * X + 1e-20)

    dyff_dm = (-2.0 * (ys + 1.0j * B / 2.0 + 1.0j * Beq)) / (np.power(k2, 2) * np.power(m, 3))
    dyft_dm = ys / (k2 * np.power(m, 2) * np.exp(-1j * tau))
    dytf_dm = ys / (k2 * np.power(m, 2) * np.exp(1j * tau))
    dytt_dm = np.zeros(len(m))

    dYf_dm = diags(dyff_dm) @ Cf + diags(dyft_dm) @ Ct
    dYt_dm = diags(dytf_dm) @ Cf + diags(dytt_dm) @ Ct

    dY_dm = Cf.T @ dYf_dm + Ct.T @ dYt_dm

    dS_dm = diagV @ np.conj(dY_dm @ diagV)
    dSf_dm = diagVf @ diags(np.conj(dYf_dm @ V))
    dSt_dm = diagVt @ diags(np.conj(dYt_dm @ V))

    return dS_dm, dSf_dm, dSt_dm


def dS_dtau_matpower(V: CxVec, Cf: csc_matrix, Ct: csc_matrix,
                     R: Vec, X: Vec, k2: Vec, m: Vec, tau: Vec):
    """
    Ybus = Cf' * Yf + Ct' * Yt + diag(Ysh)

    Yf = Yff * Cf + Yft * Ct
    Yt = Ytf * Cf + Ytt * Ct

    Ytt = Ys + 1j*Bc/2
    Yff = Gsw+( (Ytt+1j*Beq) ./ ((k2.^2).*tap .* conj(tap))  ) %%<<AAB- FUBM formulation- Original: Yff = Ytt ./ (tap .* conj(tap));
    Yft = - Ys ./ conj(tap)
    Ytf = - Ys ./ tap

    Polar coordinates:
    Partials of Ytt, Yff, Yft and Ytf w.r.t. Theta_shift
      dYtt/dsh = zeros(nl,1)
      dYff/dsh = zeros(nl,1)
      dYft/dsh = -Ys./(-1j*k2.*conj(tap))
      dYtf/dsh = -Ys./( 1j*k2.*tap      )

    Partials of Yf, Yt, Ybus w.r.t. Theta_shift
      dYf/dsh = dYff/dsh * Cf + dYft/dsh * Ct
      dYt/dsh = dYtf/dsh * Cf + dYtt/dsh * Ct

      dYbus/dsh = Cf' * dYf/dsh + Ct' * dYt/dsh

    Partials of Sbus w.r.t. shift angle
      dSbus/dsh = diag(V) * conj(dYbus/dsh * V)
    :param V:
    :param Cf:
    :param Ct:
    :param R:
    :param X:
    :param k2:
    :param m:
    :param tau:
    :return:
    """
    diagV = diags(V)
    Vf = Cf @ V
    Vt = Ct @ V
    diagVf = diags(Vf)
    diagVt = diags(Vt)

    ys = 1.0 / (R + 1j * X + 1e-20)
    tap = m * np.exp(1j * tau)

    dyff_dtau = np.zeros(len(m))
    dyft_dtau = (-1j * ys) / (k2 * np.conj(tap))
    dytf_dtau = (1j * ys) / (k2 * tap)
    dytt_dtau = np.zeros(len(m))

    dYf_dtau = diags(dyff_dtau) @ Cf + diags(dyft_dtau) @ Ct
    dYt_dtau = diags(dytf_dtau) @ Cf + diags(dytt_dtau) @ Ct

    dY_dtau = Cf.T @ dYf_dtau + Ct.T @ dYt_dtau

    dS_dtau = diagV @ np.conj(dY_dtau @ diagV)
    dSf_dtau = diagVf @ diags(np.conj(dYf_dtau @ V))
    dSt_dtau = diagVt @ diags(np.conj(dYt_dtau @ V))

    return dS_dtau, dSf_dtau, dSt_dtau


def dS_dbeq_matpower(V: CxVec, Cf: csc_matrix, Ct: csc_matrix, k2: Vec, m: Vec):
    """

    :param V:
    :param Cf:
    :param Ct:
    :param k2:
    :param m:
    :return:
    """
    diagV = diags(V)
    Vf = Cf @ V
    Vt = Ct @ V
    diagVf = diags(Vf)
    diagVt = diags(Vt)

    dyff_dbeq = 1.0j / np.power(k2 * m, 2)
    dyft_dbeq = np.zeros(len(m))
    dytf_dbeq = np.zeros(len(m))
    dytt_dbeq = np.zeros(len(m))

    dYf_dbeq = diags(dyff_dbeq) @ Cf + diags(dyft_dbeq) @ Ct
    dYt_dbeq = diags(dytf_dbeq) @ Cf + diags(dytt_dbeq) @ Ct

    dY_dbeq = Cf.T @ dYf_dbeq + Ct.T @ dYt_dbeq

    dS_dbeq = diagV @ np.conj(dY_dbeq @ diagV)
    dSf_dbeq = diagVf @ diags(np.conj(dYf_dbeq @ V))
    dSt_dbeq = diagVt @ diags(np.conj(dYt_dbeq @ V))

    return dS_dbeq, dSf_dbeq, dSt_dbeq


def Jacobian(Ybus, V: CxVec, idx_dP: IntVec, idx_dQ: IntVec, idx_dVa: IntVec, idx_dVm: IntVec) -> csc_matrix:
    """
    Computes the system Jacobian matrix in polar coordinates
    Args:
    :param Ybus: Admittance matrix
    :param V: Array of nodal voltages
    :param idx_dVa: vector of indices of PV|PQ|PQV|P buses
    :param idx_dVm: vector of indices of PQ|P buses
    :param idx_dP: vector of indices of PV|PQ|PQV|P buses
    :param idx_dQ: vector of indices of PQ|PQV buses

    Returns:
        The system Jacobian matrix
    """
    assert np.all(idx_dP == idx_dVa)

    dS_dVa, dS_dVm = dSbus_dV_matpower(Ybus, V)

    J11 = dS_dVa[np.ix_(idx_dP, idx_dVa)].real
    J12 = dS_dVm[np.ix_(idx_dP, idx_dVm)].real
    J21 = dS_dVa[np.ix_(idx_dQ, idx_dVa)].imag
    J22 = dS_dVm[np.ix_(idx_dQ, idx_dVm)].imag

    J = vstack([hstack([J11, J12]),
                hstack([J21, J22])], format="csc")

    return csc_matrix(J)
