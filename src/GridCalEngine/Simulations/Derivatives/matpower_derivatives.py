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
