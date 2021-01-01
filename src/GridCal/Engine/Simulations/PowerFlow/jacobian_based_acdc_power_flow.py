# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

from scipy.sparse.linalg import spsolve
import numpy as np
import numba as nb
import os
import time
from scipy.sparse import lil_matrix, diags
import scipy.sparse as sp
from GridCal.Engine.Core.admittance_matrices import compile_y_acdc
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCal.Engine.Sparse.csc import sp_slice, csc_stack_2d_ff, sp_slice_rows


def compute_converter_losses(V, It, F, alpha1, alpha2, alpha3, iVscL):
    """
    Compute the converter losses according to the IEC 62751-2
    :param V:
    :param It:
    :param F:
    :param alpha1:
    :param alpha2:
    :param alpha3:
    :param iVscL:
    :return:
    """
    # FUBM- Standard IEC 62751-2 Ploss Correction for VSC losses
    Ivsc = np.abs(It[iVscL])
    PLoss_IEC = alpha3[iVscL] * np.power(Ivsc, 2)
    PLoss_IEC += alpha2[iVscL] * np.power(Ivsc, 2)
    PLoss_IEC += alpha1[iVscL]

    # compute G-switch
    Gsw = np.zeros(len(F))
    Gsw[iVscL] = PLoss_IEC / np.power(np.abs(V[F[iVscL]]), 2)

    return Gsw


@nb.jit(nopython=True, cache=False)
def dSbus_dV_numba_sparse_csc(Yx, Yp, Yi, V):  # pragma: no cover
    """
    Compute the power injection derivatives w.r.t the voltage module and angle
    :param Yx: data of Ybus in CSC format
    :param Yp: indptr of Ybus in CSC format
    :param Yi: indices of Ybus in CSC format
    :param V: Voltages vector
    :return: dS_dVm, dS_dVa data ordered in the CSC format to match the indices of Ybus
    """

    # init buffer vector
    n = len(Yp) - 1
    Ibus = np.zeros(n, dtype=np.complex128)
    Vnorm = V / np.abs(V)
    dS_dVm = Yx.copy()
    dS_dVa = Yx.copy()

    # pass 1
    for j in range(n):  # for each column ...
        for k in range(Yp[j], Yp[j + 1]):  # for each row ...
            # row index
            i = Yi[k]

            # Ibus = Ybus * V
            Ibus[i] += Yx[k] * V[j]  # Yx[k] -> Y(i,j)

            # Ybus * diagVnorm
            dS_dVm[k] = Yx[k] * Vnorm[j]

            # Ybus * diag(V)
            dS_dVa[k] = Yx[k] * V[j]

    # pass 2
    for j in range(n):  # for each column ...

        # set buffer variable: this cannot be done in the pass1
        # because Ibus is not fully formed, but here it is.
        buffer = np.conj(Ibus[j]) * Vnorm[j]

        for k in range(Yp[j], Yp[j + 1]):  # for each row ...

            # row index
            i = Yi[k]

            # diag(V) * conj(Ybus * diagVnorm)
            dS_dVm[k] = V[i] * np.conj(dS_dVm[k])

            if j == i:
                # diagonal elements
                dS_dVa[k] -= Ibus[j]
                dS_dVm[k] += buffer

            # 1j * diagV * conj(diagIbus - Ybus * diagV)
            dS_dVa[k] = np.conj(-dS_dVa[k]) * (1j * V[i])

    return dS_dVm, dS_dVa


def dSbus_dV_with_numba(Ybus, V):
    """
    Call the numba sparse constructor of the derivatives
    :param Ybus: Ybus in CSC format
    :param V: Voltages vector
    :return: dS_dVm, dS_dVa in CSC format
    """
    # compute the derivatives' data fast
    dS_dVm, dS_dVa = dSbus_dV_numba_sparse_csc(Ybus.data, Ybus.indptr, Ybus.indices, V)

    # generate sparse CSC matrices with computed data and return them
    return sp.csc_matrix((dS_dVa, Ybus.indices, Ybus.indptr)), sp.csc_matrix((dS_dVm, Ybus.indices, Ybus.indptr))


def dSbus_dV(Ybus, V):
    """
    Derivatives of the power injections w.r.t the voltage
    :param Ybus: Admittance matrix
    :param V: complex voltage arrays
    :return: dSbus_dVa, dSbus_dVm
    """
    diagV = diags(V)
    diagVnorm = diags(V / np.abs(V))
    Ibus = Ybus * V
    diagIbus = diags(Ibus)

    dSbus_dVa = 1j * diagV * np.conj(diagIbus - Ybus * diagV)  # dSbus / dVa
    dSbus_dVm = diagV * np.conj(Ybus * diagVnorm) + np.conj(diagIbus) * diagVnorm  # dSbus / dVm

    return dSbus_dVa, dSbus_dVm


def dSbr_dV(Yf, Yt, V, F, T, Cf, Ct):
    """
    Derivatives of the branch power w.r.t the branch voltage modules and angles
    :param Yf: Admittances matrix of the branches with the "from" buses
    :param Yt: Admittances matrix of the branches with the "to" buses
    :param V: Array of voltages
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Cf: Connectivity matrix of the branches with the "from" buses
    :param Ct: Connectivity matrix of the branches with the "to" buses
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


def dSf_dV(Yf, V, F, Cf, Vc, diagVc, diagVnorm, diagV):
    """
    Derivatives of the branch power w.r.t the branch voltage modules and angles
    :param Yf: Admittances matrix of the branches with the "from" buses
    :param V: Array of voltages
    :param F: Array of branch "from" bus indices
    :param Cf: Connectivity matrix of the branches with the "from" buses
    :return: dSf_dVa, dSf_dVm
    """
    Yfc = np.conj(Yf)
    # Vc = np.conj(V)
    Ifc = Yfc * Vc  # conjugate  of "from"  current

    diagIfc = diags(Ifc)
    Vf = V[F]
    diagVf = diags(Vf)
    # diagVc = diags(Vc)

    # Vnorm = V / np.abs(V)
    # diagVnorm = diags(Vnorm)
    # diagV = diags(V)

    CVf = Cf * diagV
    CVnf = Cf * diagVnorm

    dSf_dVa = 1j * (diagIfc * CVf - diagVf * Yfc * diagVc)
    dSf_dVm = diagVf * np.conj(Yf * diagVnorm) + diagIfc * CVnf

    return dSf_dVa.tocsc(), dSf_dVm.tocsc()


def dSt_dV(Yt, V, T, Ct, Vc, diagVc, diagVnorm, diagV):
    """
    Derivatives of the branch power w.r.t the branch voltage modules and angles
    :param Yt: Admittances matrix of the branches with the "to" buses
    :param V: Array of voltages
    :param T: Array of branch "to" bus indices
    :param Ct: Connectivity matrix of the branches with the "to" buses
    :return: dSf_dVa, dSf_dVm, dSt_dVa, dSt_dVm
    """
    Ytc = np.conj(Yt)
    # Vc = np.conj(V)
    Itc = Ytc * Vc  # conjugate of "to" current

    diagItc = diags(Itc)
    Vt = V[T]
    diagVt = diags(Vt)
    # diagVc = diags(Vc)

    # Vnorm = V / np.abs(V)
    # diagVnorm = diags(Vnorm)
    # diagV = diags(V)

    CVt = Ct * diagV
    CVnt = Ct * diagVnorm

    dSt_dVa = 1j * (diagItc * CVt - diagVt * Ytc * diagVc)
    dSt_dVm = diagVt * np.conj(Yt * diagVnorm) + diagItc * CVnt

    return dSt_dVa.tocsc(), dSt_dVm.tocsc()


def derivatives_sh(nb, nl, iPxsh, F, T, Ys, k2, tap, V):
    """
    This function computes the derivatives of Sbus, Sf and St w.r.t. Ɵsh
    - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
    - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp

    :param nb: number of buses
    :param nl: number of branches
    :param iPxsh: array of indices {iPfsh or iPfdp}
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Ys: Array of branch series admittances
    :param k2: Array of "k2" parameters
    :param tap: Array of branch complex taps (ma * exp(1j * theta_sh)
    :param V: Array of complex voltages
    :return:
        - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
        - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp
    """
    dSbus_dPxsh = lil_matrix((nb, len(iPxsh)), dtype=complex)
    dSf_dshx2 = lil_matrix((nl, len(iPxsh)), dtype=complex)
    dSt_dshx2 = lil_matrix((nl, len(iPxsh)), dtype=complex)

    for k, idx in enumerate(iPxsh):
        f = F[idx]
        t = T[idx]

        # Partials of Ytt, Yff, Yft and Ytf w.r.t. Ɵ shift
        ytt_dsh = 0.0
        yff_dsh = 0.0
        yft_dsh = -Ys[idx] / (-1j * k2[idx] * np.conj(tap[idx]))
        ytf_dsh = -Ys[idx] / (1j * k2[idx] * tap[idx])

        # Partials of S w.r.t. Ɵ shift
        val_f = V[f] * np.conj(yft_dsh * V[t])
        val_t = V[t] * np.conj(ytf_dsh * V[f])

        dSbus_dPxsh[f, k] = val_f
        dSbus_dPxsh[t, k] = val_t

        # Partials of Sf w.r.t. Ɵ shift (makes sense that this is ∂Sbus/∂Pxsh assigned to the "from" bus)
        dSf_dshx2[idx, k] = val_f

        # Partials of St w.r.t. Ɵ shift (makes sense that this is ∂Sbus/∂Pxsh assigned to the "to" bus)
        dSt_dshx2[idx, k] = val_t

    return dSbus_dPxsh.tocsc(), dSf_dshx2.tocsc(), dSt_dshx2.tocsc()


def derivatives_ma(nb, nl, iXxma, F, T, Ys, k2, tap, ma, Bc, Beq, V):
    """
    Useful for the calculation of
    - dSbus_dQfma, dSf_dQfma, dSt_dQfma  -> wih iXxma=iQfma
    - dSbus_dQtma, dSf_dQtma, dSt_dQtma  -> wih iXxma=iQtma
    - dSbus_dVtma, dSf_dVtma, dSt_dVtma  -> wih iXxma=iVtma

    :param nb: Number of buses
    :param nl: Number of branches
    :param iXxma: Array of indices {iQfma, iQtma, iVtma}
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Ys: Array of branch series admittances
    :param k2: Array of "k2" parameters
    :param tap: Array of branch complex taps (ma * exp(1j * theta_sh)
    :param ma: Array of tap modules (this is to avoid extra calculations)
    :param Bc: Array of branch total shunt susceptance values (sum of the two legs)
    :param Beq: Array of regulation susceptance of the FUBM model
    :param V:Array of complex voltages

    :return:
    - dSbus_dQfma, dSf_dQfma, dSt_dQfma  -> if iXxma=iQfma
    - dSbus_dQtma, dSf_dQtma, dSt_dQtma  -> if iXxma=iQtma
    - dSbus_dVtma, dSf_dVtma, dSt_dVtma  -> if iXxma=iVtma
    """
    # Declare the derivative
    dSbus_dmax2 = lil_matrix((nb, len(iXxma)), dtype=complex)
    dSf_dmax2 = lil_matrix((nl, len(iXxma)), dtype=complex)
    dSt_dmax2 = lil_matrix((nl, len(iXxma)), dtype=complex)

    for k, idx in enumerate(iXxma):
        f = F[idx]
        t = T[idx]

        YttB = Ys[idx] + 1j * Bc[idx] / 2 + 1j * Beq[idx]

        # Partials of Ytt, Yff, Yft and Ytf w.r.t.ma
        dyff_dma = -2 * YttB / (np.power(k2[idx], 2) * np.power(ma[idx], 3))
        dyft_dma = Ys[idx] / (k2[idx] * ma[idx] * np.conj(tap[idx]))
        dytf_dma = Ys[idx] / (k2[idx] * ma[idx] * tap[idx])
        dytt_dma = 0

        # Partials of S w.r.t.ma
        val_f = V[f] * np.conj(dyff_dma * V[f] + dyft_dma * V[t])
        val_t = V[t] * np.conj(dytf_dma * V[f] + dytt_dma * V[t])
        dSbus_dmax2[f, k] = val_f
        dSbus_dmax2[t, k] = val_t

        dSf_dmax2[idx, k] = val_f
        dSt_dmax2[idx, k] = val_f

    return dSbus_dmax2.tocsc(), dSf_dmax2.tocsc(), dSt_dmax2.tocsc()


def derivatives_Beq(nb, nl, iBeqx, F, T, V, ma, k2):
    """
    Compute the derivatives of:
    - dSbus_dBeqz, dSf_dBeqz, dSt_dBeqz -> iBeqx=iBeqz
    - dSbus_dBeqv, dSf_dBeqv, dSt_dBeqv -> iBeqx=iBeqv

    :param nb: Number of buses
    :param nl: Number of branches
    :param iBeqx: array of indices {iBeqz, iBeqv}
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param V:Array of complex voltages
    :param ma: Array of branch taps modules
    :param k2: Array of "k2" parameters

    :return:
    - dSbus_dBeqz, dSf_dBeqz, dSt_dBeqz -> if iBeqx=iBeqz
    - dSbus_dBeqv, dSf_dBeqv, dSt_dBeqv -> if iBeqx=iBeqv
    """
    # Declare the derivative
    dSbus_dBeqx = lil_matrix((nb, len(iBeqx)), dtype=complex)
    dSf_dBeqx = lil_matrix((nl, len(iBeqx)), dtype=complex)
    dSt_dBeqx = lil_matrix((nl, len(iBeqx)), dtype=complex)

    for k, idx in enumerate(iBeqx):
        f = F[idx]
        t = T[idx]

        # Partials of Ytt, Yff, Yft and Ytf w.r.t.Beq
        dyff_dBeq = 1j / np.power(k2[idx] * ma[idx], 2.0)
        dyft_dBeq = 0
        dytf_dBeq = 0
        dytt_dBeq = 0

        # Partials of S w.r.t.Beq
        val_f = V[f] * np.conj(dyff_dBeq * V[f] + dyft_dBeq * V[t])
        val_t = V[t] * np.conj(dytf_dBeq * V[f] + dytt_dBeq * V[t])

        dSbus_dBeqx[f, k] = val_f
        dSbus_dBeqx[t, k] = val_t

        # Partials of Sf w.r.t.Beq
        dSf_dBeqx[idx, k] = val_f

        # Partials of St w.r.t.Beq
        dSt_dBeqx[idx, k] = val_t

    return dSbus_dBeqx.tocsc(), dSf_dBeqx.tocsc(), dSt_dBeqx.tocsc()


def fubm_jacobianA(nb, nl, iPfsh, iPfdp, iQfma, iQtma, iVtma, iBeqz, iBeqv, VfBeqbus, Vtmabus,
                  F, T, Ys, k2, tap, ma, Bc, Beq, Kdp, V, Ybus, Yf, Yt, Cf, Ct, pvpq, pq):
    """
    Compute the FUBM jacobian
    :param nb: number of buses
    :param nl: Number of lines
    :param iPfsh: indices of the Pf controlled branches
    :param iPfdp: indices of the droop controlled branches
    :param iQfma: indices of the Qf controlled branches
    :param iQtma: Indices of the Qt controlled branches
    :param iVtma: Indices of the Vt controlled branches
    :param iBeqz: Indices of the Qf controlled branches
    :param iBeqv: Indices of the Vf Controlled branches
    :param F: Array of "from" bus indices
    :param T: Array of "to" bus indices
    :param Ys: Array of branch series admittances
    :param k2: Array of branch converter losses
    :param tap: Array of complex tap values {remember tap = ma * exp(1j * theta) }
    :param ma: Array of tap modules
    :param Bc: Array of branch full susceptances
    :param Beq: Array of brach equivalent (variable) susceptances
    :param Kdp: Array of branch converter droop constants
    :param V: Array of complex bus voltages
    :param Ybus: Admittance matrix
    :param Yf: Admittances matrix of the branches with the "from" buses
    :param Yt: Admittances matrix of the branches with the "to" buses
    :param Cf: Connectivity matrix of the branches with the "from" buses
    :param Ct: Connectivity matrix of the branches with the "to" buses
    :param pvpq: Array of pv and then pq bus indices (not sorted)
    :param pq: Array of PQ bus indices
    :return: FUBM Jacobian matrix
    """

    # compose the derivatives of the power injections w.r.t Va and Vm
    # dSbus_dVa, dSbus_dVm = dSbus_dV(Ybus, V)
    dSbus_dVa, dSbus_dVm = dSbus_dV_with_numba(Ybus, V)

    # compose the derivatives of the branch flow w.r.t Va and Vm
    dSf_dVa, dSf_dVm, dSt_dVa, dSt_dVm = dSbr_dV(Yf, Yt, V, F, T, Cf, Ct)

    # compose the derivatives w.r.t theta sh
    dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh = derivatives_sh(nb, nl, iPfsh, F, T, Ys, k2, tap, V)
    dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp = derivatives_sh(nb, nl, iPfdp, F, T, Ys, k2, tap, V)

    # compose the derivative w.r.t ma
    dSbus_dQfma, dSf_dQfma, dSt_dQfma = derivatives_ma(nb, nl, iQfma, F, T, Ys, k2, tap, ma, Bc, Beq, V)
    dSbus_dQtma, dSf_dQtma, dSt_dQtma = derivatives_ma(nb, nl, iQtma, F, T, Ys, k2, tap, ma, Bc, Beq, V)
    dSbus_dVtma, dSf_dVtma, dSt_dVtma = derivatives_ma(nb, nl, iVtma, F, T, Ys, k2, tap, ma, Bc, Beq, V)

    # compose the derivatives w.r.t Beq
    dSbus_dBeqz, dSf_dBeqz, dSt_dBeqz = derivatives_Beq(nb, nl, iBeqz, F, T, V, ma, k2)
    dSbus_dBeqv, dSf_dBeqv, dSt_dBeqv = derivatives_Beq(nb, nl, iBeqv, F, T, V, ma, k2)

    # Voltage Droop Control Partials (it is more convenient to have them here...) --------------

    # Partials of Pfdp w.r.t. Va
    dPfdp_dVa = -dSf_dVa.real

    # Partials of Pfdp w.r.t. Vm
    dVmf_dVm = lil_matrix((nl, nb))
    dVmf_dVm[iPfdp, :] = Cf[iPfdp, :]
    dPfdp_dVm = -dSf_dVm.real + diags(Kdp) * dVmf_dVm

    # Partials of Pfdp w.r.t. ThetaSh for PST, VSCI and VSCII
    dPfdp_dPfsh = -dSf_dPfsh.real

    # Partials of Pfdp w.r.t. ma
    dPfdp_dQfma = -dSf_dQfma.real
    dPfdp_dQtma = -dSf_dQtma.real
    dPfdp_dVtma = -dSf_dVtma.real

    # Partials of Pfdp w.r.t. Beq
    dPfdp_dBeqz = -dSf_dBeqz.real
    dPfdp_dBeqv = -dSf_dBeqv.real

    # Partials of Pfdp w.r.t. ThetaSh for VSCIII
    dPfdp_dPfdp = -dSf_dPfdp.real

    # Compose the Jacobian sub-matrices (slicing) ---------------

    j11 = dSbus_dVa[np.ix_(pvpq, pvpq)].real  # avoid Slack
    j12 = dSbus_dVm[np.ix_(pvpq, pq)].real  # avoid Slack
    j13 = dSbus_dPfsh[pvpq, :].real  # avoid Slack
    j14 = dSbus_dQfma[pvpq, :].real  # avoid Slack
    j15 = dSbus_dBeqz[pvpq, :].real  # avoid Slack
    j16 = dSbus_dBeqv[pvpq, :].real  # avoid Slack
    j17 = dSbus_dVtma[pvpq, :].real  # avoid Slack
    j18 = dSbus_dQtma[pvpq, :].real  # avoid Slack
    j19 = dSbus_dPfdp[pvpq, :].real  # avoid Slack

    j21 = dSbus_dVa[np.ix_(pq, pvpq)].imag  # avoid Slack and pv
    j22 = dSbus_dVm[np.ix_(pq, pq)].imag  # avoid Slack and pv
    j23 = dSbus_dPfsh[pq, :].imag  # avoid Slack and pv
    j24 = dSbus_dQfma[pq, :].imag  # avoid Slack and pv
    j25 = dSbus_dBeqz[pq, :].imag  # avoid Slack and pv
    j26 = dSbus_dBeqv[pq, :].imag  # avoid Slack and pv
    j27 = dSbus_dVtma[pq, :].imag  # avoid Slack and pv
    j28 = dSbus_dQtma[pq, :].imag  # avoid Slack and pv
    j29 = dSbus_dPfdp[pq, :].imag  # avoid Slack and pv

    j31 = dSf_dVa[np.ix_(iPfsh, pvpq)].real  # Only Pf control elements iPfsh
    j32 = dSf_dVm[np.ix_(iPfsh, pq)].real  # Only Pf control elements iPfsh
    j33 = dSf_dPfsh[iPfsh, :].real  # Only Pf control elements iPfsh
    j34 = dSf_dQfma[iPfsh, :].real  # Only Pf control elements iPfsh
    j35 = dSf_dBeqz[iPfsh, :].real  # Only Pf control elements iPfsh
    j36 = dSf_dBeqv[iPfsh, :].real  # Only Pf control elements iPfsh
    j37 = dSf_dVtma[iPfsh, :].real  # Only Pf control elements iPfsh
    j38 = dSf_dQtma[iPfsh, :].real  # Only Pf control elements iPfsh
    j39 = dSf_dPfdp[iPfsh, :].real  # Only Pf control elements iPfsh

    j41 = dSf_dVa[np.ix_(iQfma, pvpq)].imag  # Only Qf control elements iQfma
    j42 = dSf_dVm[np.ix_(iQfma, pq)].imag  # Only Qf control elements iQfma
    j43 = dSf_dPfsh[iQfma, :].imag  # Only Qf control elements iQfma
    j44 = dSf_dQfma[iQfma, :].imag  # Only Qf control elements iQfma
    j45 = dSf_dBeqz[iQfma, :].imag  # Only Qf control elements iQfma
    j46 = dSf_dBeqv[iQfma, :].imag  # Only Qf control elements iQfma
    j47 = dSf_dVtma[iQfma, :].imag  # Only Qf control elements iQfma
    j48 = dSf_dQtma[iQfma, :].imag  # Only Qf control elements iQfma
    j49 = dSf_dPfdp[iQfma, :].imag  # Only Qf control elements iQfma

    j51 = dSf_dVa[np.ix_(iBeqz, pvpq)].imag  # Only Qf control elements iQfbeq
    j52 = dSf_dVm[np.ix_(iBeqz, pq)].imag  # Only Qf control elements iQfbeq
    j53 = dSf_dPfsh[iBeqz, :].imag  # Only Qf control elements iQfbeq
    j54 = dSf_dQfma[iBeqz, :].imag  # Only Qf control elements iQfbeq
    j55 = dSf_dBeqz[iBeqz, :].imag  # Only Qf control elements iQfbeq
    j56 = dSf_dBeqv[iBeqz, :].imag  # Only Qf control elements iQfbeq
    j57 = dSf_dVtma[iBeqz, :].imag  # Only Qf control elements iQfbeq
    j58 = dSf_dQtma[iBeqz, :].imag  # Only Qf control elements iQfbeq
    j59 = dSf_dPfdp[iBeqz, :].imag  # Only Qf control elements iQfbeq

    j61 = dSbus_dVa[np.ix_(VfBeqbus, pvpq)].imag  # Only Vf control elements iVfbeq
    j62 = dSbus_dVm[np.ix_(VfBeqbus, pq)].imag  # Only Vf control elements iVfbeq
    j63 = dSbus_dPfsh[VfBeqbus, :].imag  # Only Vf control elements iVfbeq
    j64 = dSbus_dQfma[VfBeqbus, :].imag  # Only Vf control elements iVfbeq
    j65 = dSbus_dBeqz[VfBeqbus, :].imag  # Only Vf control elements iVfbeq
    j66 = dSbus_dBeqv[VfBeqbus, :].imag  # Only Vf control elements iVfbeq
    j67 = dSbus_dVtma[VfBeqbus, :].imag  # Only Vf control elements iVfbeq
    j68 = dSbus_dQtma[VfBeqbus, :].imag  # Only Vf control elements iVfbeq
    j69 = dSbus_dPfdp[VfBeqbus, :].imag  # Only Vf control elements iVfbeq

    j71 = dSbus_dVa[np.ix_(Vtmabus, pvpq)].imag  # Only Vt control elements iVtma
    j72 = dSbus_dVm[np.ix_(Vtmabus, pq)].imag  # Only Vt control elements iVtma
    j73 = dSbus_dPfsh[Vtmabus, :].imag  # Only Vt control elements iVtma
    j74 = dSbus_dQfma[Vtmabus, :].imag  # Only Vt control elements iVtma
    j75 = dSbus_dBeqz[Vtmabus, :].imag  # Only Vt control elements iVtma
    j76 = dSbus_dBeqv[Vtmabus, :].imag  # Only Vt control elements iVtma
    j77 = dSbus_dVtma[Vtmabus, :].imag  # Only Vt control elements iVtma
    j78 = dSbus_dQtma[Vtmabus, :].imag  # Only Vt control elements iVtma
    j79 = dSbus_dPfdp[Vtmabus, :].imag  # Only Vt control elements iVtma

    j81 = dSt_dVa[np.ix_(iQtma, pvpq)].imag  # Only Qt control elements iQtma
    j82 = dSt_dVm[np.ix_(iQtma, pq)].imag  # Only Qt control elements iQtma
    j83 = dSt_dPfsh[iQtma, :].imag  # Only Qt control elements iQtma
    j84 = dSt_dQfma[iQtma, :].imag  # Only Qt control elements iQtma
    j85 = dSt_dBeqz[iQtma, :].imag  # Only Qt control elements iQtma
    j86 = dSt_dBeqv[iQtma, :].imag  # Only Qt control elements iQtma
    j87 = dSt_dVtma[iQtma, :].imag  # Only Qt control elements iQtma
    j88 = dSt_dQtma[iQtma, :].imag  # Only Qt control elements iQtma
    j89 = dSt_dPfdp[iQtma, :].imag  # Only Droop control elements iPfdp

    j91 = dPfdp_dVa[np.ix_(iPfdp, pvpq)]  # Only Droop control elements iPfdp
    j92 = dPfdp_dVm[np.ix_(iPfdp, pq)]  # Only Droop control elements iPfdp
    j93 = dPfdp_dPfsh[iPfdp, :]  # Only Droop control elements iPfdp
    j94 = dPfdp_dQfma[iPfdp, :]  # Only Droop control elements iPfdp
    j95 = dPfdp_dBeqz[iPfdp, :]  # Only Droop control elements iPfdp
    j96 = dPfdp_dBeqv[iPfdp, :]  # Only Droop control elements iPfdp
    j97 = dPfdp_dVtma[iPfdp, :]  # Only Droop control elements iPfdp
    j98 = dPfdp_dQtma[iPfdp, :]  # Only Droop control elements iPfdp
    j99 = dPfdp_dPfdp[iPfdp, :]  # Only Droop control elements iPfdp

    # Jacobian
    J = sp.vstack((
        sp.hstack((j11, j12, j13, j14, j15, j16, j17, j18, j19)),
        sp.hstack((j21, j22, j23, j24, j25, j26, j27, j28, j29)),
        sp.hstack((j31, j32, j33, j34, j35, j36, j37, j38, j39)),
        sp.hstack((j41, j42, j43, j44, j45, j46, j47, j48, j49)),
        sp.hstack((j51, j52, j53, j54, j55, j56, j57, j58, j59)),
        sp.hstack((j61, j62, j63, j64, j65, j66, j67, j68, j69)),
        sp.hstack((j71, j72, j73, j74, j75, j76, j77, j78, j79)),
        sp.hstack((j81, j82, j83, j84, j85, j86, j87, j88, j89)),
        sp.hstack((j91, j92, j93, j94, j95, j96, j97, j98, j99))
    ), format='csc')  # FUBM-Jacobian Matrix

    return J


def fubm_jacobian(nb, nl, iPfsh, iPfdp, iQfma, iQtma, iVtma, iBeqz, iBeqv, VfBeqbus, Vtmabus,
                  F, T, Ys, k2, tap, ma, Bc, Beq, Kdp, V, Ybus, Yf, Yt, Cf, Ct, pvpq, pq):
    """
    Compute the FUBM jacobian in a dynamic fashion by only computing the derivatives that are needed
    :param nb: number of buses
    :param nl: Number of lines
    :param iPfsh: indices of the Pf controlled branches
    :param iPfdp: indices of the droop controlled branches
    :param iQfma: indices of the Qf controlled branches
    :param iQtma: Indices of the Qt controlled branches
    :param iVtma: Indices of the Vt controlled branches
    :param iBeqz: Indices of the Qf controlled branches
    :param iBeqv: Indices of the Vf Controlled branches
    :param F: Array of "from" bus indices
    :param T: Array of "to" bus indices
    :param Ys: Array of branch series admittances
    :param k2: Array of branch converter losses
    :param tap: Array of complex tap values {remember tap = ma * exp(1j * theta) }
    :param ma: Array of tap modules
    :param Bc: Array of branch full susceptances
    :param Beq: Array of brach equivalent (variable) susceptances
    :param Kdp: Array of branch converter droop constants
    :param V: Array of complex bus voltages
    :param Ybus: Admittance matrix
    :param Yf: Admittances matrix of the branches with the "from" buses
    :param Yt: Admittances matrix of the branches with the "to" buses
    :param Cf: Connectivity matrix of the branches with the "from" buses
    :param Ct: Connectivity matrix of the branches with the "to" buses
    :param pvpq: Array of pv and then pq bus indices (not sorted)
    :param pq: Array of PQ bus indices
    :return: FUBM Jacobian matrix
    """
    nPfsh = len(iPfsh)
    nPfdp = len(iPfdp)
    nQfma = len(iQfma)
    nQtma = len(iQtma)
    nVtma = len(iVtma)
    nBeqz = len(iBeqz)
    nBeqv = len(iBeqv)
    npq = len(pq)
    npvpq = len(pvpq)

    # compose the derivatives of the power injections w.r.t Va and Vm
    dSbus_dVa, dSbus_dVm = dSbus_dV_with_numba(Ybus, V)

    # compose the derivatives of the branch flow w.r.t Va and Vm
    Vc = np.conj(V)
    diagVc = diags(Vc)
    Vnorm = V / np.abs(V)
    diagVnorm = diags(Vnorm)
    diagV = diags(V)
    dSf_dVa, dSf_dVm = dSf_dV(Yf, V, F, Cf, Vc, diagVc, diagVnorm, diagV)

    if nQtma:
        dSt_dVa, dSt_dVm = dSt_dV(Yt, V, T, Ct, Vc, diagVc, diagVnorm, diagV)

    # compose the number of columns and rows of the jacobian super structure "mats"
    cols = bool(npvpq) + bool(npq) + bool(nPfsh) + bool(nQfma) + bool(nBeqz)
    cols += bool(nBeqv) + bool(nVtma) + bool(nQtma) + bool(nPfdp)
    rows = cols

    j11 = sp_slice(dSbus_dVa.real, pvpq, pvpq)
    j21 = sp_slice(dSbus_dVa.imag, pq, pvpq)
    mats = [j11, j21]
    if nPfsh:
        j31 = sp_slice(dSf_dVa.real, iPfsh, pvpq)
        mats.append(j31)
    if nQfma:
        j41 = sp_slice(dSf_dVa.imag, iQfma, pvpq)
        mats.append(j41)
    if nBeqz:
        j51 = sp_slice(dSf_dVa.imag, iBeqz, pvpq)
        mats.append(j51)
    if len(VfBeqbus):
        j61 = sp_slice(dSbus_dVa.imag, VfBeqbus, pvpq)
        mats.append(j61)
    if len(Vtmabus):
        j71 = sp_slice(dSbus_dVa.imag, Vtmabus, pvpq)
        mats.append(j71)
    if nQtma:
        j81 = sp_slice(dSt_dVa.imag, iQtma, pvpq)
        mats.append(j81)
    if nPfdp:
        dPfdp_dVa = -dSf_dVa.real
        j91 = sp_slice(dPfdp_dVa, iPfdp, pvpq)
        mats.append(j91)

    j12 = sp_slice(dSbus_dVm.real, pvpq, pq)
    j22 = sp_slice(dSbus_dVm.imag, pq, pq)
    mats += [j12, j22]
    if nPfsh:
        j32 = sp_slice(dSf_dVm.real, iPfsh, pq)
        mats.append(j32)
    if nQfma:
        j42 = sp_slice(dSf_dVm.imag, iQfma, pq)
        mats.append(j42)
    if nBeqz:
        j52 = sp_slice(dSf_dVm.imag, iBeqz, pq)
        mats.append(j52)
    if len(VfBeqbus):
        j62 = sp_slice(dSbus_dVm.imag, VfBeqbus, pq)
        mats.append(j62)
    if len(Vtmabus):
        j72 = sp_slice(dSbus_dVm.imag, Vtmabus, pq)
        mats.append(j72)
    if nQtma:
        j82 = sp_slice(dSt_dVm.imag, iQtma, pq)
        mats.append(j82)
    if nPfdp:
        dVmf_dVm = lil_matrix((nl, nb))
        dVmf_dVm[iPfdp, :] = Cf[iPfdp, :]
        dPfdp_dVm = -dSf_dVm.real + diags(Kdp) * dVmf_dVm
        j92 = sp_slice(dPfdp_dVm, iPfdp, pq)
        mats.append(j92)

    # compose the derivatives w.r.t theta sh
    if nPfsh > 0:
        dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh = derivatives_sh(nb, nl, iPfsh, F, T, Ys, k2, tap, V)

        dPfdp_dPfsh = -dSf_dPfsh.real

        j13 = sp_slice_rows(dSbus_dPfsh.real, pvpq)
        j23 = sp_slice_rows(dSbus_dPfsh.imag, pq)
        mats += [j13, j23]
        if nPfsh:
            j33 = sp_slice_rows(dSf_dPfsh.real, iPfsh)
            mats.append(j33)
        if nQfma:
            j43 = sp_slice_rows(dSf_dPfsh.imag, iQfma)
            mats.append(j43)
        if nBeqz:
            j53 = sp_slice_rows(dSf_dPfsh.imag, iBeqz)
            mats.append(j53)
        if nBeqv:
            j63 = sp_slice_rows(dSbus_dPfsh.imag, VfBeqbus)
            mats.append(j63)
        if nVtma:
            j73 = sp_slice_rows(dSbus_dPfsh.imag, Vtmabus)
            mats.append(j73)
        if nQtma:
            j83 = sp_slice_rows(dSt_dPfsh.imag, iQtma)
            mats.append(j83)
        if nPfdp:
            j93 = sp_slice_rows(dPfdp_dPfsh, iPfdp)
            mats.append(j93)

    # compose the derivative w.r.t ma
    if nQfma > 0:
        dSbus_dQfma, dSf_dQfma, dSt_dQfma = derivatives_ma(nb, nl, iQfma, F, T, Ys, k2, tap, ma, Bc, Beq, V)

        dPfdp_dQfma = -dSf_dQfma.real

        j14 = sp_slice_rows(dSbus_dQfma.real, pvpq)
        j24 = sp_slice_rows(dSbus_dQfma.imag, pq)
        mats += [j14, j24]
        if nPfsh:
            j34 = sp_slice_rows(dSf_dQfma.real, iPfsh)
            mats.append(j34)
        if nQfma:
            j44 = sp_slice_rows(dSf_dQfma.imag, iQfma)
            mats.append(j44)
        if nBeqz:
            j54 = sp_slice_rows(dSf_dQfma.imag, iBeqz)
            mats.append(j54)
        if nBeqv:
            j64 = sp_slice_rows(dSbus_dQfma.imag, VfBeqbus)
            mats.append(j64)
        if nVtma:
            j74 = sp_slice_rows(dSbus_dQfma.imag, Vtmabus)
            mats.append(j74)
        if nQtma:
            j84 = sp_slice_rows(dSt_dQfma.imag, iQtma)
            mats.append(j84)
        if nPfdp:
            j94 = sp_slice_rows(dPfdp_dQfma, iPfdp)
            mats.append(j94)

    # compose the derivatives w.r.t Beq
    if nBeqz > 0:
        dSbus_dBeqz, dSf_dBeqz, dSt_dBeqz = derivatives_Beq(nb, nl, iBeqz, F, T, V, ma, k2)

        dPfdp_dBeqz = -dSf_dBeqz.real

        j15 = sp_slice_rows(dSbus_dBeqz.real, pvpq)
        j25 = sp_slice_rows(dSbus_dBeqz.imag, pq)
        mats += [j15, j25]
        if nPfsh:
            j35 = sp_slice_rows(dSf_dBeqz.real, iPfsh)
            mats.append(j35)
        if nQfma:
            j45 = sp_slice_rows(dSf_dBeqz.imag, iQfma)
            mats.append(j45)
        if nBeqz:
            j55 = sp_slice_rows(dSf_dBeqz.imag, iBeqz)
            mats.append(j55)
        if nBeqv:
            j65 = sp_slice_rows(dSbus_dBeqz.imag, VfBeqbus)
            mats.append(j65)
        if nVtma:
            j75 = sp_slice_rows(dSbus_dBeqz.imag, Vtmabus)
            mats.append(j75)
        if nQtma:
            j85 = sp_slice_rows(dSt_dBeqz.imag, iQtma)
            mats.append(j85)
        if nPfdp:
            j95 = sp_slice_rows(dPfdp_dBeqz, iPfdp)
            mats.append(j95)

    if nBeqv > 0:
        dSbus_dBeqv, dSf_dBeqv, dSt_dBeqv = derivatives_Beq(nb, nl, iBeqv, F, T, V, ma, k2)

        dPfdp_dBeqv = -dSf_dBeqv.real

        j16 = sp_slice_rows(dSbus_dBeqv.real, pvpq)
        j26 = sp_slice_rows(dSbus_dBeqv.imag, pq)
        mats += [j16, j26]
        if nPfsh:
            j36 = sp_slice_rows(dSf_dBeqv.real, iPfsh)
            mats.append(j36)
        if nQfma:
            j46 = sp_slice_rows(dSf_dBeqv.imag, iQfma)
            mats.append(j46)
        if nBeqz:
            j56 = sp_slice_rows(dSf_dBeqv.imag, iBeqz)
            mats.append(j56)
        if nBeqv:
            j66 = sp_slice_rows(dSbus_dBeqv.imag, VfBeqbus)
            mats.append(j66)
        if nVtma:
            j76 = sp_slice_rows(dSbus_dBeqv.imag, Vtmabus)
            mats.append(j76)
        if nQtma:
            j86 = sp_slice_rows(dSt_dBeqv.imag, iQtma)
            mats.append(j86)
        if nPfdp:
            j96 = sp_slice_rows(dPfdp_dBeqv, iPfdp)
            mats.append(j96)

    if nVtma > 0:
        dSbus_dVtma, dSf_dVtma, dSt_dVtma = derivatives_ma(nb, nl, iVtma, F, T, Ys, k2, tap, ma, Bc, Beq, V)

        dPfdp_dVtma = -dSf_dVtma.real

        j17 = sp_slice_rows(dSbus_dVtma.real, pvpq)
        j27 = sp_slice_rows(dSbus_dVtma.imag, pq)
        mats += [j17, j27]
        if nPfsh:
            j37 = sp_slice_rows(dSf_dVtma.real, iPfsh)
            mats.append(j37)
        if nQfma:
            j47 = sp_slice_rows(dSf_dVtma.imag, iQfma)
            mats.append(j47)
        if nBeqz:
            j57 = sp_slice_rows(dSf_dVtma.imag, iBeqz)
            mats.append(j57)
        if nBeqv:
            j67 = sp_slice_rows(dSbus_dVtma.imag, VfBeqbus)
            mats.append(j67)
        if nVtma:
            j77 = sp_slice_rows(dSbus_dVtma.imag, Vtmabus)
            mats.append(j77)
        if nQtma:
            j87 = sp_slice_rows(dSt_dVtma.imag, iQtma)
            mats.append(j87)
        if nPfdp:
            j97 = sp_slice_rows(dPfdp_dVtma, iPfdp)
            mats.append(j97)

    if nQtma > 0:
        dSbus_dQtma, dSf_dQtma, dSt_dQtma = derivatives_ma(nb, nl, iQtma, F, T, Ys, k2, tap, ma, Bc, Beq, V)

        dPfdp_dQtma = -dSf_dQtma.real

        j18 = sp_slice_rows(dSbus_dQtma.real, pvpq)
        j28 = sp_slice_rows(dSbus_dQtma.imag, pq)
        mats += [j18, j28]
        if nPfsh:
            j38 = sp_slice_rows(dSf_dQtma.real, iPfsh)
            mats.append(j38)
        if nQfma:
            j48 = sp_slice_rows(dSf_dQtma.imag, iQfma)
            mats.append(j48)
        if nBeqz:
            j58 = sp_slice_rows(dSf_dQtma.imag, iBeqz)
            mats.append(j58)
        if nBeqv:
            j68 = sp_slice_rows(dSbus_dQtma.imag, VfBeqbus)
            mats.append(j68)
        if nVtma:
            j78 = sp_slice_rows(dSbus_dQtma.imag, Vtmabus)
            mats.append(j78)
        if nQtma:
            j88 = sp_slice_rows(dSt_dQtma.imag, iQtma)
            mats.append(j88)
        if nPfdp:
            j98 = sp_slice_rows(dPfdp_dQtma, iPfdp)
            mats.append(j98)

    if nPfdp > 0:
        dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp = derivatives_sh(nb, nl, iPfdp, F, T, Ys, k2, tap, V)

        dPfdp_dPfdp = -dSf_dPfdp.real

        j19 = sp_slice_rows(dSbus_dPfdp.real, pvpq)
        j29 = sp_slice_rows(dSbus_dPfdp.imag, pq)
        mats += [j19, j29]
        if nPfsh:
            j39 = sp_slice_rows(dSf_dPfdp.real, iPfsh)
            mats.append(j39)
        if nQfma:
            j49 = sp_slice_rows(dSf_dPfdp.imag, iQfma)
            mats.append(j49)
        if nBeqz:
            j59 = sp_slice_rows(dSf_dPfdp.imag, iBeqz)
            mats.append(j59)
        if nBeqv:
            j69 = sp_slice_rows(dSbus_dPfdp.imag, VfBeqbus)
            mats.append(j69)
        if nVtma:
            j79 = sp_slice_rows(dSbus_dPfdp.imag, Vtmabus)
            mats.append(j79)
        if nQtma:
            j89 = sp_slice_rows(dSt_dPfdp.imag, iQtma)
            mats.append(j89)
        if nPfdp:
            j99 = sp_slice_rows(dPfdp_dPfdp, iPfdp)
            mats.append(j99)

    # compose Jacobian from the submatrices
    J = csc_stack_2d_ff(mats, rows, cols, row_major=False)

    return J


def compute_fx(Ybus, V, Vm, Sbus, Sf, St, Pfset, Qfset, Qtset, Vmfset, Kdp, F,
               pvpq, pq, iPfsh, iQfma, iBeqz, iQtma, iPfdp, VfBeqbus, Vtmabus):
    """
    Compute the increments vector
    :param Ybus: Admittance matrix
    :param V: Voltages array
    :param Vm: Voltages module array
    :param Sbus: Array of bus power matrix
    :param Pfset: Array of Pf set values per branch
    :param Qfset: Array of Qf set values per branch
    :param Qtset: Array of Qt set values per branch
    :param Vmfset: Array of Vf set values per branch
    :param Kdp: Array of branch droop value per branch
    :param F:
    :param T:
    :param pvpq:
    :param pq:
    :param iPfsh:
    :param iQfma:
    :param iBeqz:
    :param iQtma:
    :param iPfdp:
    :param iBeqv:
    :param iVtma:
    :return:
    """
    Scalc = V * np.conj(Ybus * V)
    mis = Scalc - Sbus  # FUBM- F1(x0) & F2(x0) Power balance mismatch

    misPbus = mis[pvpq].real  # FUBM- F1(x0) Power balance mismatch - Va
    misQbus = mis[pq].imag  # FUBM- F2(x0) Power balance mismatch - Vm
    misPfsh = Sf[iPfsh].real - Pfset[iPfsh]  # FUBM- F3(x0) Pf control mismatch
    misQfma = Sf[iQfma].imag - Qfset[iQfma]  # FUBM- F4(x0) Qf control mismatch
    misBeqz = Sf[iBeqz].imag - 0  # FUBM- F5(x0) Qf control mismatch
    misBeqv = mis[VfBeqbus].imag  # FUBM- F6(x0) Vf control mismatch
    misVtma = mis[Vtmabus].imag  # FUBM- F7(x0) Vt control mismatch
    misQtma = St[iQtma].imag - Qtset[iQtma]  # FUBM- F8(x0) Qt control mismatch
    misPfdp = -Sf[iPfdp].real + Pfset[iPfdp] + Kdp[iPfdp] * (Vm[F[iPfdp]] - Vmfset[iPfdp])  # FUBM- F9(x0) Pf control mismatch, Droop Pf - Pfset = Kdp*(Vmf - Vmfset)
    # -------------------------------------------------------------------------

    #  Create F vector
    # FUBM----------------------------------------------------------------------
    df = np.r_[misPbus,  # FUBM- F1(x0) Power balance mismatch - Va
               misQbus,  # FUBM- F2(x0) Power balance mismatch - Vm
               misPfsh,  # FUBM- F3(x0) Pf control    mismatch - Theta_shift
               misQfma,  # FUBM- F4(x0) Qf control    mismatch - ma
               misBeqz,  # FUBM- F5(x0) Qf control    mismatch - Beq
               misBeqv,  # FUBM- F6(x0) Vf control    mismatch - Beq
               misVtma,  # FUBM- F7(x0) Vt control    mismatch - ma
               misQtma,  # FUBM- F8(x0) Qt control    mismatch - ma
               misPfdp]  # FUBM- F9(x0) Pf control    mismatch - Theta_shift Droop

    return df, Scalc


def NR_LS_ACDC(nc: "SnapshotData", tolerance=1e-6, max_iter=4, mu_0=1.0, acceleration_parameter=0.05,
               verbose=False) -> NumericPowerFlowResults:
    """
    Newton-Raphson Line search with the FUBM formulation
    :param nc: SnapshotData instance
    :param tolerance: maximum error allowed
    :param max_iter: maximum number of iterations
    :param mu_0:
    :param acceleration_parameter:
    :return:
    """
    start = time.time()

    # initialize the variables
    nb = nc.nbus
    nl = nc.nbr
    V = nc.Vbus
    S0 = nc.Sbus
    Va = np.angle(V)
    Vm = np.abs(V)
    Vmfset = nc.branch_data.vf_set[:, 0]
    m = nc.branch_data.m[:, 0].copy()
    theta = nc.branch_data.theta[:, 0].copy()
    Beq = nc.branch_data.Beq[:, 0].copy()
    Gsw = nc.branch_data.G0[:, 0]
    Pfset = nc.branch_data.Pfset[:, 0] / nc.Sbase
    Qfset = nc.branch_data.Qfset[:, 0] / nc.Sbase
    Qtset = nc.branch_data.Qfset[:, 0] / nc.Sbase
    Kdp = nc.branch_data.Kdp
    k2 = nc.branch_data.k
    Cf = nc.Cf
    Ct = nc.Ct
    F = nc.F
    T = nc.T
    Ys = 1.0 / (nc.branch_data.R + 1j * nc.branch_data.X)
    Bc = nc.branch_data.B
    pq = nc.pq.copy().astype(int)
    pvpq_orig = np.r_[nc.pv, pq].astype(int)
    pvpq_orig.sort()

    # the elements of PQ that exist in the control indices Ivf and Ivt must be passed from the PQ to the PV list
    # otherwise those variables would be in two sets of equations
    i_ctrl_v = np.unique(np.r_[nc.VfBeqbus, nc.Vtmabus])
    for val in pq:
        if val in i_ctrl_v:
            pq = pq[pq != val]

    # compose the new pvpq indices à la NR
    pv = np.unique(np.r_[i_ctrl_v, nc.pv]).astype(int)
    pv.sort()
    pvpq = np.r_[pv, pq].astype(int)
    npv = len(pv)
    npq = len(pq)

    # --------------------------------------------------------------------------
    # variables dimensions in Jacobian
    a0 = 0
    a1 = a0 + npq + npv
    a2 = a1 + npq
    a3 = a2 + len(nc.iPfsh)
    a4 = a3 + len(nc.iQfma)
    a5 = a4 + len(nc.iBeqz)
    a6 = a5 + len(nc.VfBeqbus)
    a7 = a6 + len(nc.Vtmabus)
    a8 = a7 + len(nc.iQtma)
    a9 = a8 + len(nc.iPfdp)
    # -------------------------------------------------------------------------
    # compute initial admittances
    Ybus, Yf, Yt, tap = compile_y_acdc(Cf=Cf, Ct=Ct,
                                       C_bus_shunt=nc.shunt_data.C_bus_shunt,
                                       shunt_admittance=nc.shunt_data.shunt_admittance[:, 0],
                                       shunt_active=nc.shunt_data.shunt_active[:, 0],
                                       ys=Ys,
                                       B=Bc,
                                       Sbase=nc.Sbase,
                                       m=m, theta=theta, Beq=Beq, Gsw=Gsw,
                                       mf=nc.branch_data.tap_f,
                                       mt=nc.branch_data.tap_t)

    #  compute branch power flows
    If = Yf * V  # FUBM- complex current injected at "from" bus, Yf(br, :) * V; For in-service branches
    It = Yt * V  # FUBM- complex current injected at "to"   bus, Yt(br, :) * V; For in-service branches
    Sf = V[F] * np.conj(If)  # FUBM- complex power injected at "from" bus
    St = V[T] * np.conj(It)  # FUBM- complex power injected at "to"   bus

    # compute converter losses
    Gsw = compute_converter_losses(V=V, It=It, F=F,
                                   alpha1=nc.branch_data.alpha1,
                                   alpha2=nc.branch_data.alpha2,
                                   alpha3=nc.branch_data.alpha3,
                                   iVscL=nc.iVscL)

    # compute total mismatch
    fx, Scalc = compute_fx(Ybus=Ybus,
                           V=V,
                           Vm=Vm,
                           Sbus=S0,
                           Sf=Sf,
                           St=St,
                           Pfset=Pfset,
                           Qfset=Qfset,
                           Qtset=Qtset,
                           Vmfset=Vmfset,
                           Kdp=Kdp,
                           F=F,
                           pvpq=pvpq,
                           pq=pq,
                           iPfsh=nc.iPfsh,
                           iQfma=nc.iQfma,
                           iBeqz=nc.iBeqz,
                           iQtma=nc.iQtma,
                           iPfdp=nc.iPfdp,
                           VfBeqbus=nc.VfBeqbus,
                           Vtmabus=nc.Vtmabus)

    norm_f = np.max(np.abs(fx))

    # -------------------------------------------------------------------------
    converged = norm_f < tolerance
    iterations = 0
    back_track_counter = 0
    while not converged and iterations < max_iter:

        # compute the Jacobian
        J = fubm_jacobian(nb, nl, nc.iPfsh, nc.iPfdp, nc.iQfma, nc.iQtma, nc.iVtma, nc.iBeqz, nc.iBeqv,
                          nc.VfBeqbus, nc.Vtmabus,
                          F, T, Ys, k2, tap, m, Bc, Beq, Kdp, V, Ybus, Yf, Yt, Cf, Ct, pvpq, pq)

        # J = fubm_jacobianA(nb, nl, nc.iPfsh, nc.iPfdp, nc.iQfma, nc.iQtma, nc.iVtma, nc.iBeqz, nc.iBeqv,
        #                    nc.VfBeqbus, nc.Vtmabus,
        #                    F, T, Ys, k2, tap, m, Bc, Beq, Kdp, V, Ybus, Yf, Yt, Cf, Ct, pvpq, pq)

        # solve the linear system
        dx = sp.linalg.spsolve(J, -fx)
        # dxa = sp.linalg.spsolve(Ja, -fx)

        # split the solution
        dVa = dx[a0:a1]
        dVm = dx[a1:a2]
        dtheta_Pf = dx[a2:a3]
        dma_Qf = dx[a3:a4]
        dBeq_z = dx[a4:a5]
        dBeq_v = dx[a5:a6]
        dma_Vt = dx[a6:a7]
        dma_Qt = dx[a7:a8]
        dtheta_Pd = dx[a8:a9]

        # set the restoration values
        prev_Vm = Vm.copy()
        prev_Va = Va.copy()
        prev_m = m.copy()
        prev_theta = theta.copy()
        prev_Beq = Beq.copy()
        prev_Scalc = Scalc.copy()

        mu = mu_0  # ideally 1.0
        cond = True
        l_iter = 0
        norm_f_new = 0.0
        while cond and l_iter < max_iter and mu > tolerance:  # backtracking: if all goes well it is only done 1 time

            # restore the previous values if we are backtracking (the first iteration is the normal NR procedure)
            if l_iter > 0:
                Va = prev_Va.copy()
                Vm = prev_Vm.copy()
                m = prev_m.copy()
                theta = prev_theta.copy()
                Beq = prev_Beq.copy()

            # assign the new values
            Va[pvpq] += dVa * mu
            Vm[pq] += dVm * mu
            theta[nc.iPfsh] += dtheta_Pf * mu
            theta[nc.iPfdp] += dtheta_Pd * mu
            m[nc.iQfma] += dma_Qf * mu
            m[nc.iQtma] += dma_Qt * mu
            m[nc.iVtma] += dma_Vt * mu
            Beq[nc.iBeqz] += dBeq_z * mu
            Beq[nc.iBeqv] += dBeq_v * mu
            V = Vm * np.exp(1j * Va)

            for idx in nc.iVscL:
                # correct m (tap modules)
                if m[idx] < nc.branch_data.m_min[idx]:
                    m[idx] = nc.branch_data.m_min[idx]
                elif m[idx] > nc.branch_data.m_max[idx]:
                    m[idx] = nc.branch_data.m_max[idx]

                # correct theta (tap angles)
                if theta[idx] < nc.branch_data.theta_min[idx]:
                    theta[idx] = nc.branch_data.theta_min[idx]
                elif theta[idx] > nc.branch_data.theta_max[idx]:
                    theta[idx] = nc.branch_data.theta_max[idx]

            # compute admittances
            Ybus, Yf, Yt, tap = compile_y_acdc(Cf=Cf, Ct=Ct,
                                               C_bus_shunt=nc.shunt_data.C_bus_shunt,
                                               shunt_admittance=nc.shunt_data.shunt_admittance[:, 0],
                                               shunt_active=nc.shunt_data.shunt_active[:, 0],
                                               ys=Ys,
                                               B=Bc,
                                               Sbase=nc.Sbase,
                                               m=m, theta=theta, Beq=Beq, Gsw=Gsw,
                                               mf=nc.branch_data.tap_f,
                                               mt=nc.branch_data.tap_t)

            #  compute branch power flows
            If = Yf * V  # complex current injected at "from" bus
            It = Yt * V  # complex current injected at "to" bus
            Sf = V[F] * np.conj(If)  # complex power injected at "from" bus
            St = V[T] * np.conj(It)  # complex power injected at "to"   bus

            # compute converter losses
            Gsw = compute_converter_losses(V=V, It=It, F=F,
                                           alpha1=nc.branch_data.alpha1,
                                           alpha2=nc.branch_data.alpha2,
                                           alpha3=nc.branch_data.alpha3,
                                           iVscL=nc.iVscL)

            # compute total mismatch
            fx, Scalc = compute_fx(Ybus=Ybus,
                                   V=V,
                                   Vm=Vm,
                                   Sbus=S0,
                                   Sf=Sf,
                                   St=St,
                                   Pfset=Pfset,
                                   Qfset=Qfset,
                                   Qtset=Qtset,
                                   Vmfset=Vmfset,
                                   Kdp=Kdp,
                                   F=F,
                                   pvpq=pvpq,
                                   pq=pq,
                                   iPfsh=nc.iPfsh,
                                   iQfma=nc.iQfma,
                                   iBeqz=nc.iBeqz,
                                   iQtma=nc.iQtma,
                                   iPfdp=nc.iPfdp,
                                   VfBeqbus=nc.VfBeqbus,
                                   Vtmabus=nc.Vtmabus)

            norm_f_new = np.max(np.abs(fx))
            cond = norm_f_new > norm_f  # condition to back track (no improvement at all)

            mu *= acceleration_parameter
            back_track_counter += 1
            l_iter += 1

        if l_iter > 1:
            # this means that not even the backtracking was able to correct the solution so, restore and end
            Va = prev_Va.copy()
            Vm = prev_Vm.copy()
            m = prev_m.copy()
            theta = prev_theta.copy()
            Beq = prev_Beq.copy()
            V = Vm * np.exp(1j * Va)

            end = time.time()
            elapsed = end - start

            # set the state for the next solver
            nc.branch_data.m[:, 0] = m
            nc.branch_data.theta[:, 0] = theta
            nc.branch_data.Beq[:, 0] = Beq

            return NumericPowerFlowResults(V, converged, norm_f, prev_Scalc, m, theta, Beq, iterations, elapsed)
        else:
            norm_f = norm_f_new

        if verbose:
            print('dx:', dx)
            print('Va:', Va)
            print('Vm:', Vm)
            print('theta:', theta)
            print('ma:', m)
            print('Beq:', Beq)
            print('norm_f:', norm_f)

        iterations += 1
        converged = norm_f <= tolerance

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V, converged, norm_f, Scalc, m, theta, Beq, iterations, elapsed)


def LM_ACDC(nc: "SnapshotData", tolerance=1e-6, max_iter=4, verbose=False) -> NumericPowerFlowResults:
    """
    Solves the power flow problem by the Levenberg-Marquardt power flow algorithm.
    It is usually better than Newton-Raphson, but it takes an order of magnitude more time to converge.

    :param nc: SnapshotData instance
    :param tolerance: maximum error allowed
    :param max_iter: maximum number of iterations
    :return:
    """
    start = time.time()

    # initialize the variables
    nb = nc.nbus
    nl = nc.nbr
    V = nc.Vbus
    S0 = nc.Sbus
    Va = np.angle(V)
    Vm = np.abs(V)
    Vmfset = nc.branch_data.vf_set[:, 0]
    m = nc.branch_data.m[:, 0].copy()
    theta = nc.branch_data.theta[:, 0].copy()
    Beq = nc.branch_data.Beq[:, 0].copy()
    Gsw = nc.branch_data.G0[:, 0]
    Pfset = nc.branch_data.Pfset[:, 0] / nc.Sbase
    Qfset = nc.branch_data.Qfset[:, 0] / nc.Sbase
    Qtset = nc.branch_data.Qfset[:, 0] / nc.Sbase
    Kdp = nc.branch_data.Kdp
    k2 = nc.branch_data.k
    Cf = nc.Cf
    Ct = nc.Ct
    F = nc.F
    T = nc.T
    Ys = 1.0 / (nc.branch_data.R + 1j * nc.branch_data.X)
    Bc = nc.branch_data.B
    pq = nc.pq.copy().astype(int)
    pvpq_orig = np.r_[nc.pv, pq].astype(int)
    pvpq_orig.sort()

    # the elements of PQ that exist in the control indices Ivf and Ivt must be passed from the PQ to the PV list
    # otherwise those variables would be in two sets of equations
    i_ctrl_v = np.unique(np.r_[nc.VfBeqbus, nc.Vtmabus])
    for val in pq:
        if val in i_ctrl_v:
            pq = pq[pq != val]

    # compose the new pvpq indices à la NR
    pv = np.unique(np.r_[i_ctrl_v, nc.pv]).astype(int)
    pv.sort()
    pvpq = np.r_[pv, pq].astype(int)
    npv = len(pv)
    npq = len(pq)

    if (npq + npv) > 0:
        # --------------------------------------------------------------------------
        # variables dimensions in Jacobian
        a0 = 0
        a1 = a0 + npq + npv
        a2 = a1 + npq
        a3 = a2 + len(nc.iPfsh)
        a4 = a3 + len(nc.iQfma)
        a5 = a4 + len(nc.iBeqz)
        a6 = a5 + len(nc.VfBeqbus)
        a7 = a6 + len(nc.Vtmabus)
        a8 = a7 + len(nc.iQtma)
        a9 = a8 + len(nc.iPfdp)
        # -------------------------------------------------------------------------
        # compute initial admittances
        Ybus, Yf, Yt, tap = compile_y_acdc(Cf=Cf, Ct=Ct,
                                           C_bus_shunt=nc.shunt_data.C_bus_shunt,
                                           shunt_admittance=nc.shunt_data.shunt_admittance[:, 0],
                                           shunt_active=nc.shunt_data.shunt_active[:, 0],
                                           ys=Ys,
                                           B=Bc,
                                           Sbase=nc.Sbase,
                                           m=m, theta=theta, Beq=Beq, Gsw=Gsw,
                                           mf=nc.branch_data.tap_f,
                                           mt=nc.branch_data.tap_t)

        #  compute branch power flows
        If = Yf * V  # complex current injected at "from" bus, Yf(br, :) * V; For in-service branches
        It = Yt * V  # complex current injected at "to"   bus, Yt(br, :) * V; For in-service branches
        Sf = V[F] * np.conj(If)  # complex power injected at "from" bus
        St = V[T] * np.conj(It)  # complex power injected at "to"   bus

        # compute converter losses
        Gsw = compute_converter_losses(V=V, It=It, F=F,
                                       alpha1=nc.branch_data.alpha1,
                                       alpha2=nc.branch_data.alpha2,
                                       alpha3=nc.branch_data.alpha3,
                                       iVscL=nc.iVscL)

        # compute total mismatch
        dz, Scalc = compute_fx(Ybus=Ybus,
                               V=V,
                               Vm=Vm,
                               Sbus=S0,
                               Sf=Sf,
                               St=St,
                               Pfset=Pfset,
                               Qfset=Qfset,
                               Qtset=Qtset,
                               Vmfset=Vmfset,
                               Kdp=Kdp,
                               F=F,
                               pvpq=pvpq,
                               pq=pq,
                               iPfsh=nc.iPfsh,
                               iQfma=nc.iQfma,
                               iBeqz=nc.iBeqz,
                               iQtma=nc.iQtma,
                               iPfdp=nc.iPfdp,
                               VfBeqbus=nc.VfBeqbus,
                               Vtmabus=nc.Vtmabus)

        norm_f = np.max(np.abs(dz))

        update_jacobian = True
        converged = norm_f < tolerance
        iter_ = 0
        nu = 2.0
        lbmda = 0
        f_prev = 1e9  # very large number

        # generate lookup pvpq -> index pvpq (used in createJ)
        pvpq_lookup = np.zeros(np.max(Ybus.indices) + 1, dtype=int)
        pvpq_lookup[pvpq] = np.arange(len(pvpq))

        while not converged and iter_ < max_iter:

            # evaluate Jacobian
            if update_jacobian:
                H = fubm_jacobian(nb, nl, nc.iPfsh, nc.iPfdp, nc.iQfma, nc.iQtma, nc.iVtma, nc.iBeqz, nc.iBeqv,
                                  nc.VfBeqbus, nc.Vtmabus,
                                  F, T, Ys, k2, tap, m, Bc, Beq, Kdp, V, Ybus, Yf, Yt, Cf, Ct, pvpq, pq)

                if iter_ == 0:
                    # compute this identity only once
                    Idn = sp.diags(np.ones(H.shape[0]))  # csc_matrix identity

                # system matrix
                # H1 = H^t
                H1 = H.transpose()

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
            dx = spsolve(A, rhs)

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

                # split the solution
                dVa = dx[a0:a1]
                dVm = dx[a1:a2]
                dtheta_Pf = dx[a2:a3]
                dma_Qf = dx[a3:a4]
                dBeq_z = dx[a4:a5]
                dBeq_v = dx[a5:a6]
                dma_Vt = dx[a6:a7]
                dma_Qt = dx[a7:a8]
                dtheta_Pd = dx[a8:a9]

                # assign the new values
                Va[pvpq] -= dVa
                Vm[pq] -= dVm
                theta[nc.iPfsh] -= dtheta_Pf
                theta[nc.iPfdp] -= dtheta_Pd
                m[nc.iQfma] -= dma_Qf
                m[nc.iQtma] -= dma_Qt
                m[nc.iVtma] -= dma_Vt
                Beq[nc.iBeqz] -= dBeq_z
                Beq[nc.iBeqv] -= dBeq_v
                V = Vm * np.exp(1.0j * Va)

            else:
                update_jacobian = False
                lbmda *= nu
                nu *= 2.0

            # compute initial admittances
            Ybus, Yf, Yt, tap = compile_y_acdc(Cf=Cf, Ct=Ct,
                                               C_bus_shunt=nc.shunt_data.C_bus_shunt,
                                               shunt_admittance=nc.shunt_data.shunt_admittance[:, 0],
                                               shunt_active=nc.shunt_data.shunt_active[:, 0],
                                               ys=Ys,
                                               B=Bc,
                                               Sbase=nc.Sbase,
                                               m=m, theta=theta, Beq=Beq, Gsw=Gsw,
                                               mf=nc.branch_data.tap_f,
                                               mt=nc.branch_data.tap_t)

            #  compute branch power flows
            If = Yf * V  # FUBM- complex current injected at "from" bus, Yf(br, :) * V; For in-service branches
            It = Yt * V  # FUBM- complex current injected at "to"   bus, Yt(br, :) * V; For in-service branches
            Sf = V[F] * np.conj(If)  # FUBM- complex power injected at "from" bus
            St = V[T] * np.conj(It)  # FUBM- complex power injected at "to"   bus

            # compute converter losses
            Gsw = compute_converter_losses(V=V, It=It, F=F,
                                           alpha1=nc.branch_data.alpha1,
                                           alpha2=nc.branch_data.alpha2,
                                           alpha3=nc.branch_data.alpha3,
                                           iVscL=nc.iVscL)

            # check convergence
            dz, Scalc = compute_fx(Ybus=Ybus,
                                   V=V,
                                   Vm=Vm,
                                   Sbus=S0,
                                   Sf=Sf,
                                   St=St,
                                   Pfset=Pfset,
                                   Qfset=Qfset,
                                   Qtset=Qtset,
                                   Vmfset=Vmfset,
                                   Kdp=Kdp,
                                   F=F,
                                   pvpq=pvpq,
                                   pq=pq,
                                   iPfsh=nc.iPfsh,
                                   iQfma=nc.iQfma,
                                   iBeqz=nc.iBeqz,
                                   iQtma=nc.iQtma,
                                   iPfdp=nc.iPfdp,
                                   VfBeqbus=nc.VfBeqbus,
                                   Vtmabus=nc.Vtmabus)
            norm_f = np.max(np.abs(dz))
            converged = norm_f < tolerance
            f_prev = f

            if verbose:
                print('dx:', dx)
                print('Va:', Va)
                print('Vm:', Vm)
                print('theta:', theta)
                print('ma:', m)
                print('Beq:', Beq)
                print('norm_f:', norm_f)

            # update iteration counter
            iter_ += 1
    else:
        norm_f = 0
        converged = True
        Scalc = S0  # V * np.conj(Ybus * V - Ibus)
        iter_ = 0

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V, converged, norm_f, Scalc, m, theta, Beq, iter_, elapsed)


if __name__ == "__main__":
    from GridCal.Engine import FileOpen, compile_snapshot_circuit
    np.set_printoptions(precision=4, linewidth=100000)
    # np.set_printoptions(linewidth=10000)

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/LineHVDCGrid.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE57+IEEE14 DC grid.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/ACDC_example_grid.gridcal'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/fubm_caseHVDC_vt.gridcal'
    grid = FileOpen(fname).open()

    ####################################################################################################################
    # Compile
    ####################################################################################################################
    nc_ = compile_snapshot_circuit(grid)

    res = NR_LS_ACDC(nc=nc_, tolerance=1e-4, max_iter=20, verbose=True)

    res2 = LM_ACDC(nc=nc_, tolerance=1e-4, max_iter=20, verbose=True)

    print()
