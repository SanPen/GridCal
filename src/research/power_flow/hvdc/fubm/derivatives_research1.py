
"""
From the example: fubm_case_30_2MTDC_ctrls_vt2_pf
"""
import numpy as np
from scipy.sparse import lil_matrix, diags
import scipy.sparse as sp


def sparse_from_tripplets(m_, n_, tripplets):
    A = lil_matrix((m_, n_), dtype=int)
    for i, j, v in tripplets:
        A[i, j] = v
    return A.tocsc()


def dSbus_dV(Ybus, V):
    """
    Derivatives of the power injections w.r.t the voltage
    :param Ybus: Admittance matrix
    :param V: complex voltage arrays
    :return: dSbus_dVa, dSbus_dVm
    """
    diagV = diags(V)
    diagVnorm= diags(V / np.abs(V))
    Ibus = Ybus * V
    diagIbus = diags(Ibus)

    dSbus_dVa = 1j * diagV * np.conj(diagIbus - Ybus * diagV)  # dSbus / dVa
    dSbus_dVm = diagV * np.conj(Ybus * diagVnorm) + np.conj(diagIbus) * diagVnorm  # dSbus / dVm

    return dSbus_dVa, dSbus_dVm


def dSbr_dV(Yf, Yt, V, F, T, Cf, Ct):
    """
    Derivatives of the branch power w.r.t the branch voltage modules and angles
    :param Yf:
    :param Yt:
    :param V:
    :param F:
    :param T:
    :param Cf:
    :param Ct:
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

    CVf = Cf * V
    CVt = Ct * V
    CVnf = Cf * Vnorm
    CVnt = Ct * Vnorm

    dSf_dVa = 1j * (diagIfc * CVf - diagVf * Yfc * diagVc)
    dSf_dVm = diagVf * np.conj(Yf * diagVnorm) + diagIfc * CVnf
    dSt_dVa = 1j * (diagItc * CVt - diagVt * Ytc * diagVc)
    dSt_dVm = diagVt * np.conj(Yt * diagVnorm) + diagItc * CVnt

    return dSf_dVa, dSf_dVm, dSt_dVa, dSt_dVm


def d_dsh(nb, nl, iPxsh, F, T, Ys, k2, tap, V):
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
    dSbus_dPxsh = lil_matrix((nb, len(iPxsh)))
    dSf_dshx2 = lil_matrix(nl, len(iPxsh))
    dSt_dshx2 = lil_matrix(nl, len(iPxsh))

    for k, idx in enumerate(iPxsh):

        idx = iPxsh(k)
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


def d_dma(nb, nl, iXxma, F, T, Ys, k2, tap, ma, Bc, Beq, V):
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
    dSbus_dmax2 = lil_matrix(nb, len(iXxma))
    dSf_dmax2 = lil_matrix(nl, len(iXxma))
    dSt_dmax2 = lil_matrix(nl, len(iXxma))

    for k, idx in enumerate(iXxma):

        f = F[idx]
        t = T[idx]

        YttB = Ys[idx] + 1j * Bc[idx] / 2 + 1j * Beq[idx]

        # Partials of Ytt, Yff, Yft and Ytf w.r.t.ma
        dyff_dma = -2 * YttB[idx] / (np.power(k2[idx], 2) * np.power(ma[idx], 3))
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


def d_dBeq(nb, nl, iBeqx, F, T, V, ma, k2):
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
    dSbus_dBeqx = lil_matrix(nb, len(iBeqx))
    dSf_dBeqx = lil_matrix(nl, len(iBeqx))
    dSt_dBeqx = lil_matrix(nl, len(iBeqx))

    for k, idx in enumerate(iBeqx):

        f = F[idx]
        t = T[idx]

        # Partials of Ytt, Yff, Yft and Ytf w.r.t.Beq
        dyff_dBeq = 1j / np.power(k2(idx) * ma(idx), 2.0)
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


def droop_derivatives(dSf_dVa, dSf_dVm,
                      Kdp, dVmf_dVm,
                      dSf_dPfsh, dSf_dQfma,
                      dSf_dQtma, dSf_dVtma,
                      dSf_dBeqz, dSf_dBeqv,
                      dSf_dPfdp):
    """

    :param dSf_dVa:
    :param dSf_dVm:
    :param Kdp:
    :param dVmf_dVm:
    :param dSf_dPfsh:
    :param dSf_dQfma:
    :param dSf_dQtma:
    :param dSf_dVtma:
    :param dSf_dBeqz:
    :param dSf_dBeqv:
    :param dSf_dPfdp:
    :return:
    """
    # Voltage Droop Control Partials
    # Partials of Pfdp w.r.t. Va
    dPfdp_dVa = -dSf_dVa.real

    # Partials of Pfdp w.r.t. Vm
    dPfdp_dVm = -dSf_dVm.real + Kdp * dVmf_dVm

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

    return


def jacobian(nb, nl, iPfsh, iPfdp, iQfma, iQtma, iVtma, iBeqz, iBeqv,
             F, T, Ys, k2, tap, ma, Bc, Beq, Kdp, V, Ybus, Yf, Yt, Cf, Ct, pvpq, pq):

    # FUBM- Saves the "from" bus identifier for Vf controlled by Beq
    #  (Converters type II for Vdc control)
    VfBeqbus = F[iBeqv]

    # FUBM- Saves the "to"   bus identifier for Vt controlled by ma
    #  (Converters and Transformers)
    Vtmabus = T[iVtma]

    # compose the derivatives of the power injections w.r.t Va and Vm
    dSbus_dVa, dSbus_dVm = dSbus_dV(Ybus, V)

    # compose the derivatives of the branch flow w.r.t Va and Vm
    dSf_dVa, dSf_dVm, dSt_dVa, dSt_dVm = dSbr_dV(Yf, Yt, V, F, T, Cf, Ct)

    # compose the derivatives w.r.t theta sh
    dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh = d_dsh(nb, nl, iPfsh, F, T, Ys, k2, tap, V)
    dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp = d_dsh(nb, nl, iPfdp, F, T, Ys, k2, tap, V)

    # compose the derivative w.r.t ma
    dSbus_dQfma, dSf_dQfma, dSt_dQfma = d_dma(nb, nl, iQfma, F, T, Ys, k2, tap, ma, Bc, Beq, V)
    dSbus_dQtma, dSf_dQtma, dSt_dQtma = d_dma(nb, nl, iQtma, F, T, Ys, k2, tap, ma, Bc, Beq, V)
    dSbus_dVtma, dSf_dVtma, dSt_dVtma = d_dma(nb, nl, iVtma, F, T, Ys, k2, tap, ma, Bc, Beq, V)

    # compose the derivatives w.r.t Beq
    dSbus_dBeqz, dSf_dBeqz, dSt_dBeqz = d_dBeq(nb, nl, iBeqz, F, T, V, ma, k2)
    dSbus_dBeqv, dSf_dBeqv, dSt_dBeqv = d_dBeq(nb, nl, iBeqv, F, T, V, ma, k2)
    
    # Voltage Droop Control Partials --------------

    # Partials of Pfdp w.r.t. Va
    dPfdp_dVa = -dSf_dVa.real

    # Partials of Pfdp w.r.t. Vm
    dVmf_dVm = Cf[iPfdp, :]
    dPfdp_dVm = -dSf_dVm.real + Kdp * dVmf_dVm

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

    # Compose the Jacobian sub-matrices ---------------

    j11 = dSbus_dVa[pvpq, pvpq].real  # avoid Slack
    j12 = dSbus_dVm[pvpq, pq].real  # avoid Slack
    j13 = dSbus_dPfsh[pvpq, :].real  # avoid Slack
    j14 = dSbus_dQfma[pvpq, :].real  # avoid Slack
    j15 = dSbus_dBeqz[pvpq, :].real  # avoid Slack
    j16 = dSbus_dBeqv[pvpq, :].real  # avoid Slack
    j17 = dSbus_dVtma[pvpq, :].real  # avoid Slack
    j18 = dSbus_dQtma[pvpq, :].real  # avoid Slack
    j19 = dSbus_dPfdp[pvpq, :].real  # avoid Slack

    j21 = dSbus_dVa[pq, pvpq].imag  # avoid Slack and pv
    j22 = dSbus_dVm[pq, pq].imag  # avoid Slack and pv
    j23 = dSbus_dPfsh[pq, :].imag  # avoid Slack and pv
    j24 = dSbus_dQfma[pq, :].imag  # avoid Slack and pv
    j25 = dSbus_dBeqz[pq, :].imag  # avoid Slack and pv
    j26 = dSbus_dBeqv[pq, :].imag  # avoid Slack and pv
    j27 = dSbus_dVtma[pq, :].imag  # avoid Slack and pv
    j28 = dSbus_dQtma[pq, :].imag  # avoid Slack and pv
    j29 = dSbus_dPfdp[pq, :].imag  # avoid Slack and pv

    j31 = dSf_dVa[iPfsh, pvpq].real  # Only Pf control elements iPfsh
    j32 = dSf_dVm[iPfsh, pq].real  # Only Pf control elements iPfsh
    j33 = dSf_dPfsh[iPfsh, :].real  # Only Pf control elements iPfsh
    j34 = dSf_dQfma[iPfsh, :].real  # Only Pf control elements iPfsh
    j35 = dSf_dBeqz[iPfsh, :].real  # Only Pf control elements iPfsh
    j36 = dSf_dBeqv[iPfsh, :].real  # Only Pf control elements iPfsh
    j37 = dSf_dVtma[iPfsh, :].real  # Only Pf control elements iPfsh
    j38 = dSf_dQtma[iPfsh, :].real  # Only Pf control elements iPfsh
    j39 = dSf_dPfdp[iPfsh, :].real  # Only Pf control elements iPfsh

    j41 = dSf_dVa[iQfma, pvpq].imag  # Only Qf control elements iQfma
    j42 = dSf_dVm[iQfma, pq].imag  # Only Qf control elements iQfma
    j43 = dSf_dPfsh[iQfma, :].imag  # Only Qf control elements iQfma
    j44 = dSf_dQfma[iQfma, :].imag  # Only Qf control elements iQfma
    j45 = dSf_dBeqz[iQfma, :].imag  # Only Qf control elements iQfma
    j46 = dSf_dBeqv[iQfma, :].imag  # Only Qf control elements iQfma
    j47 = dSf_dVtma[iQfma, :].imag  # Only Qf control elements iQfma
    j48 = dSf_dQtma[iQfma, :].imag  # Only Qf control elements iQfma
    j49 = dSf_dPfdp[iQfma, :].imag  # Only Qf control elements iQfma

    j51 = dSf_dVa[iBeqz, pvpq].imag  # Only Qf control elements iQfbeq
    j52 = dSf_dVm[iBeqz, pq].imag    # Only Qf control elements iQfbeq
    j53 = dSf_dPfsh[iBeqz, :].imag   # Only Qf control elements iQfbeq
    j54 = dSf_dQfma[iBeqz, :].imag   # Only Qf control elements iQfbeq
    j55 = dSf_dBeqz[iBeqz, :].imag   # Only Qf control elements iQfbeq
    j56 = dSf_dBeqv[iBeqz, :].imag   # Only Qf control elements iQfbeq
    j57 = dSf_dVtma[iBeqz, :].imag   # Only Qf control elements iQfbeq
    j58 = dSf_dQtma[iBeqz, :].imag   # Only Qf control elements iQfbeq
    j59 = dSf_dPfdp[iBeqz, :].imag   # Only Qf control elements iQfbeq

    j61 = dSbus_dVa[VfBeqbus, pvpq].imag  # Only Vf control elements iVfbeq
    j62 = dSbus_dVm[VfBeqbus, pq].imag    # Only Vf control elements iVfbeq
    j63 = dSbus_dPfsh[VfBeqbus, :].imag   # Only Vf control elements iVfbeq
    j64 = dSbus_dQfma[VfBeqbus, :].imag   # Only Vf control elements iVfbeq
    j65 = dSbus_dBeqz[VfBeqbus, :].imag   # Only Vf control elements iVfbeq
    j66 = dSbus_dBeqv[VfBeqbus, :].imag   # Only Vf control elements iVfbeq
    j67 = dSbus_dVtma[VfBeqbus, :].imag   # Only Vf control elements iVfbeq
    j68 = dSbus_dQtma[VfBeqbus, :].imag   # Only Vf control elements iVfbeq
    j69 = dSbus_dPfdp[VfBeqbus, :].imag   # Only Vf control elements iVfbeq

    j71 = dSbus_dVa[Vtmabus, pvpq].imag  # Only Vt control elements iVtma
    j72 = dSbus_dVm[Vtmabus, pq].imag    # Only Vt control elements iVtma
    j73 = dSbus_dPfsh[Vtmabus, :].imag   # Only Vt control elements iVtma
    j74 = dSbus_dQfma[Vtmabus, :].imag   # Only Vt control elements iVtma
    j75 = dSbus_dBeqz[Vtmabus, :].imag   # Only Vt control elements iVtma
    j76 = dSbus_dBeqv[Vtmabus, :].imag   # Only Vt control elements iVtma
    j77 = dSbus_dVtma[Vtmabus, :].imag   # Only Vt control elements iVtma
    j78 = dSbus_dQtma[Vtmabus, :].imag   # Only Vt control elements iVtma
    j79 = dSbus_dPfdp[Vtmabus, :].imag   # Only Vt control elements iVtma

    j81 = dSt_dVa[iQtma, pvpq].imag  # Only Qt control elements iQtma
    j82 = dSt_dVm[iQtma, pq].imag    # Only Qt control elements iQtma
    j83 = dSt_dPfsh[iQtma, :].imag   # Only Qt control elements iQtma
    j84 = dSt_dQfma[iQtma, :].imag   # Only Qt control elements iQtma
    j85 = dSt_dBeqz[iQtma, :].imag   # Only Qt control elements iQtma
    j86 = dSt_dBeqv[iQtma, :].imag   # Only Qt control elements iQtma
    j87 = dSt_dVtma[iQtma, :].imag   # Only Qt control elements iQtma
    j88 = dSt_dQtma[iQtma, :].imag   # Only Qt control elements iQtma
    j89 = dSt_dPfdp[iQtma, :].imag   # Only Droop control elements iPfdp

    j91 = dPfdp_dVa[iPfdp, pvpq]  # Only Droop control elements iPfdp
    j92 = dPfdp_dVm[iPfdp, pq]    # Only Droop control elements iPfdp
    j93 = dPfdp_dPfsh[iPfdp, :]   # Only Droop control elements iPfdp
    j94 = dPfdp_dQfma[iPfdp, :]   # Only Droop control elements iPfdp
    j95 = dPfdp_dBeqz[iPfdp, :]   # Only Droop control elements iPfdp
    j96 = dPfdp_dBeqv[iPfdp, :]   # Only Droop control elements iPfdp
    j97 = dPfdp_dVtma[iPfdp, :]   # Only Droop control elements iPfdp
    j98 = dPfdp_dQtma[iPfdp, :]   # Only Droop control elements iPfdp
    j99 = dPfdp_dPfdp[iPfdp, :]   # Only Droop control elements iPfdp

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
    ))  # FUBM-Jacobian Matrix

    return J


def compute_fx(Ybus, Yf, Yt, V, Vm, Sbus, GSW, alpha1, alpha2, alpha3, Pfset, Qfset, Qtset, Vmfset, Kdp, F, T,
               pvpq, pq, iVscL, iPfsh, iQfma, iBeqz, iQtma, iPfdp, iBeqv, iVtma):
    """

    :param Ybus:
    :param Yf:
    :param Yt:
    :param V:
    :param Vm:
    :param Sbus:
    :param GSW:
    :param alpha1:
    :param alpha2:
    :param alpha3:
    :param Pfset:
    :param Qfset:
    :param Qtset:
    :param Vmfset:
    :param Kdp:
    :param F:
    :param T:
    :param pvpq:
    :param pq:
    :param iVscL:
    :param iPfsh:
    :param iQfma:
    :param iBeqz:
    :param iQtma:
    :param iPfdp:
    :param iBeqv:
    :param iVtma:
    :return:
    """
    #  compute branch power flows
    # br = find(branch(:, BR_STATUS].imag  # FUBM- in-service branches
    If = Yf * V  # FUBM- complex current injected at "from" bus, Yf(br, :) * V; For in-service branches
    It = Yt * V  # FUBM- complex current injected at "to"   bus, Yt(br, :) * V; For in-service branches
    Sf = V[F] * np.conj(If)  # FUBM- complex power injected at "from" bus
    St = V[T] * np.conj(It)  # FUBM- complex power injected at "to"   bus
    #  compute VSC Power Loss
    if len(iVscL):
        PLoss_IEC = alpha3[iVscL] * np.power(np.abs(It[iVscL]), 2) + alpha2[iVscL] *  np.power(np.abs(It[iVscL]), 2) + alpha1[iVscL]  # FUBM- Standard IEC 62751-2 Ploss Correction for VSC losses
        GSW[iVscL] = PLoss_IEC / np.power(np.abs(V[F[iVscL]]), 2)  # FUBM- VSC Gsw

    #  evaluate F(x0)
    # FUBM----------------------------------------------------------------------
    # FUBM- Saves the "from" bus identifier for Vf controlled by Beq
    #  (Converters type II for Vdc control)
    VfBeqbus = F[iBeqv]

    # FUBM- Saves the "to"   bus identifier for Vt controlled by ma
    #  (Converters and Transformers)
    Vtmabus = T[iVtma]

    mis = V * np.conj(Ybus * V) - Sbus  # FUBM- F1(x0) & F2(x0) Power balance mismatch

    misPbus = mis[pvpq].real                            # FUBM- F1(x0) Power balance mismatch - Va
    misQbus = mis[pq].imag                              # FUBM- F2(x0) Power balance mismatch - Vm
    misPfsh = Sf[iPfsh].real - Pfset[iPfsh]             # FUBM- F3(x0) Pf control mismatch
    misQfma = Sf[iQfma].imag - Qfset[iQfma]             # FUBM- F4(x0) Qf control mismatch
    misBeqz = Sf[iBeqz].imag - 0                        # FUBM- F5(x0) Qf control mismatch
    misBeqv = mis[VfBeqbus].imag                        # FUBM- F6(x0) Vf control mismatch
    misVtma = mis[Vtmabus].imag                         # FUBM- F7(x0) Vt control mismatch
    misQtma = St[iQtma].imag - Qtset[iQtma]             # FUBM- F8(x0) Qt control mismatch
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
               misPfdp]   # FUBM- F9(x0) Pf control    mismatch - Theta_shift Droop

    return df


def test_fubm_case_30_2MTDC_ctrls_vt2_pf():
    n = 44
    m = 60
    ys = np.array([5.00000000000000 - 15.0000000000000 * 1j,
                   1.29533678756477 - 4.92227979274612 * 1j,
                   1.84615384615385 - 5.23076923076923 * 1j,
                   5.88235294117647 - 23.5294117647059 * 1j,
                   1.17647058823529 - 4.70588235294118 * 1j,
                   1.66666666666667 - 5.00000000000000 * 1j,
                   5.88235294117647 - 23.5294117647059 * 1j,
                   2.95857988165680 - 7.10059171597633 * 1j,
                   4.10958904109589 - 10.9589041095890 * 1j,
                   5.88235294117647 - 23.5294117647059 * 1j,
                   0.00000000000000 - 4.76190476190476 * 1j,
                   0.00000000000000 - 1.78571428571429 * 1j,
                   0.00000000000000 - 4.76190476190476 * 1j,
                   0.00000000000000 - 9.09090909090909 * 1j,
                   0.00000000000000 - 3.84615384615385 * 1j,
                   0.00000000000000 - 7.14285714285714 * 1j,
                   1.46341463414634 - 3.17073170731707 * 1j,
                   3.21100917431193 - 5.96330275229358 * 1j,
                   1.87110187110187 - 4.15800415800416 * 1j,
                   2.48868778280543 - 2.26244343891403 * 1j,
                   1.88235294117647 - 4.47058823529412 * 1j,
                   1.81818181818182 - 3.63636363636364 * 1j,
                   2.92682926829268 - 6.34146341463415 * 1j,
                   5.17241379310345 - 12.0689655172414 * 1j,
                   1.72413793103448 - 4.02298850574713 * 1j,
                   4.10958904109589 - 10.9589041095890 * 1j,
                   5.17241379310345 - 12.0689655172414 * 1j,
                   2.55474452554745 - 5.47445255474453 * 1j,
                   20.0000000000000 - 40.0000000000000 * 1j,
                   2.00000000000000 - 4.00000000000000 * 1j,
                   2.56410256410256 - 3.84615384615385 * 1j,
                   1.44766146993318 - 3.00668151447661 * 1j,
                   1.31034482758621 - 2.27586206896552 * 1j,
                   1.20831319478009 - 1.83663605606573 * 1j,
                   1.95729537366548 - 3.73665480427046 * 1j,
                   0.00000000000000 - 2.50000000000000 * 1j,
                   0.978647686832740 - 1.86832740213523 * 1j,
                   0.692041522491350 - 1.29757785467128 * 1j,
                   0.922722029988466 - 1.73010380622837 * 1j,
                   1.37614678899083 - 4.58715596330275 * 1j,
                   5.00000000000000 - 15.0000000000000 * 1j,
                   0.119344464724163 - 8.91900966371912 * 1j,
                   0.119344464724163 - 8.91900966371912 * 1j,
                   0.119344464724163 - 8.91900966371912 * 1j,
                   0.119344464724163 - 8.91900966371912 * 1j,
                   0.119344464724163 - 8.91900966371912 * 1j,
                   0.119344464724163 - 8.91900966371912 * 1j,
                   0.00370445831558280 - 6.08642501250255 * 1j,
                   0.00370445831558280 - 6.08642501250255 * 1j,
                   0.00370445831558280 - 6.08642501250255 * 1j,
                   0.00370445831558280 - 6.08642501250255 * 1j,
                   0.00370445831558280 - 6.08642501250255 * 1j,
                   0.00370445831558280 - 6.08642501250255 * 1j,
                   20.0000000000000 + 0.00000000000000 * 1j,
                   20.0000000000000 + 0.00000000000000 * 1j,
                   20.0000000000000 + 0.00000000000000 * 1j,
                   20.0000000000000 + 0.00000000000000 * 1j,
                   20.0000000000000 + 0.00000000000000 * 1j,
                   20.0000000000000 + 0.00000000000000 * 1j,
                   20.0000000000000 + 0.00000000000000 * 1j])

    Cf = sparse_from_tripplets(m, n, [(0, 0, 1),
                                        (1, 0, 1),
                                        (2, 1, 1),
                                        (4, 1, 1),
                                        (5, 1, 1),
                                        (44, 1, 1),
                                        (3, 2, 1),
                                        (6, 3, 1),
                                        (14, 3, 1),
                                        (7, 4, 1),
                                        (45, 4, 1),
                                        (8, 5, 1),
                                        (9, 5, 1),
                                        (10, 5, 1),
                                        (11, 5, 1),
                                        (40, 5, 1),
                                        (46, 5, 1),
                                        (39, 7, 1),
                                        (12, 8, 1),
                                        (13, 8, 1),
                                        (24, 9, 1),
                                        (25, 9, 1),
                                        (26, 9, 1),
                                        (27, 9, 1),
                                        (15, 11, 1),
                                        (16, 11, 1),
                                        (17, 11, 1),
                                        (18, 11, 1),
                                        (41, 12, 1),
                                        (19, 13, 1),
                                        (21, 14, 1),
                                        (29, 14, 1),
                                        (42, 14, 1),
                                        (20, 15, 1),
                                        (22, 17, 1),
                                        (23, 18, 1),
                                        (28, 20, 1),
                                        (30, 21, 1),
                                        (31, 22, 1),
                                        (32, 23, 1),
                                        (33, 24, 1),
                                        (34, 24, 1),
                                        (36, 26, 1),
                                        (37, 26, 1),
                                        (35, 27, 1),
                                        (38, 28, 1),
                                        (43, 29, 1),
                                        (47, 36, 1),
                                        (53, 36, 1),
                                        (54, 36, 1),
                                        (48, 37, 1),
                                        (55, 37, 1),
                                        (49, 38, 1),
                                        (50, 39, 1),
                                        (56, 39, 1),
                                        (57, 39, 1),
                                        (51, 40, 1),
                                        (58, 40, 1),
                                        (52, 41, 1),
                                        (59, 41, 1)])

    Ct = sparse_from_tripplets(m, n, [(0, 1, 1),
                                        (1, 2, 1),
                                        (2, 3, 1),
                                        (3, 3, 1),
                                        (4, 4, 1),
                                        (5, 5, 1),
                                        (6, 5, 1),
                                        (7, 6, 1),
                                        (8, 6, 1),
                                        (9, 7, 1),
                                        (10, 8, 1),
                                        (11, 9, 1),
                                        (13, 9, 1),
                                        (12, 10, 1),
                                        (14, 11, 1),
                                        (15, 12, 1),
                                        (16, 13, 1),
                                        (17, 14, 1),
                                        (19, 14, 1),
                                        (18, 15, 1),
                                        (20, 16, 1),
                                        (25, 16, 1),
                                        (21, 17, 1),
                                        (22, 18, 1),
                                        (23, 19, 1),
                                        (24, 19, 1),
                                        (26, 20, 1),
                                        (27, 21, 1),
                                        (28, 21, 1),
                                        (29, 22, 1),
                                        (30, 23, 1),
                                        (31, 23, 1),
                                        (32, 24, 1),
                                        (33, 25, 1),
                                        (34, 26, 1),
                                        (35, 26, 1),
                                        (39, 27, 1),
                                        (40, 27, 1),
                                        (36, 28, 1),
                                        (37, 29, 1),
                                        (38, 29, 1),
                                        (41, 30, 1),
                                        (47, 30, 1),
                                        (42, 31, 1),
                                        (48, 31, 1),
                                        (43, 32, 1),
                                        (49, 32, 1),
                                        (44, 33, 1),
                                        (50, 33, 1),
                                        (45, 34, 1),
                                        (51, 34, 1),
                                        (46, 35, 1),
                                        (52, 35, 1),
                                        (53, 37, 1),
                                        (54, 38, 1),
                                        (55, 38, 1),
                                        (56, 40, 1),
                                        (57, 41, 1),
                                        (59, 42, 1),
                                        (58, 43, 1)])

    F = [0,
        0,
        1,
        2,
        1,
        1,
        3,
        4,
        5,
        5,
        5,
        5,
        8,
        8,
        3,
        11,
        11,
        11,
        11,
        13,
        15,
        14,
        17,
        18,
        9,
        9,
        9,
        9,
        20,
        14,
        21,
        22,
        23,
        24,
        24,
        27,
        26,
        26,
        28,
        7,
        5,
        12,
        14,
        29,
        1,
        4,
        5,
        36,
        37,
        38,
        39,
        40,
        41,
        36,
        36,
        37,
        39,
        39,
        40,
        41
        ]

    T = [1,
        2,
        3,
        3,
        4,
        5,
        5,
        6,
        6,
        7,
        8,
        9,
        10,
        9,
        11,
        12,
        13,
        14,
        15,
        14,
        16,
        17,
        18,
        19,
        19,
        16,
        20,
        21,
        21,
        22,
        23,
        23,
        24,
        25,
        26,
        26,
        28,
        29,
        29,
        27,
        27,
        30,
        31,
        32,
        33,
        34,
        35,
        30,
        31,
        32,
        33,
        34,
        35,
        37,
        38,
        38,
        40,
        41,
        43,
        42,
        ]

    V = np.array([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1.01, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
                  1, 1, 1, 1, 1, 1, 1, 1.05, 1, 1.1, 1, 1, 1, 1, 1.07, 1, 1]).astype(complex)

    ma = np.ones(m)
    theta = np.zeros(m)
    tap = ma * np.exp(theta * 1j)
    k2 = np.ones(m)
    iPxsh = np.array([17, 25, 49, 50, 53])

    J = jacobian(nb=n, nl=m,
                 iPfsh,
                 iPfdp,
                 iQfma,
                 iQtma,
                 iVtma,
                 iBeqz,
                 iBeqv,
                 F=F,
                 T=T,
                 Ys=ys,
                 k2=k2,
                 tap=tap,
                 ma=ma,
                 Bc,
                 Beq,
                 Kdp,
                 V,
                 Ybus,
                 Yf,
                 Yt,
                 Cf,
                 Ct,
                 pvpq,
                 pq)

    pass