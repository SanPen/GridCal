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
from scipy import sparse as sp
from scipy.sparse import csc_matrix as csc
from scipy.sparse import lil_matrix

from GridCalEngine.Utils.Sparse.csc import diags
from typing import Tuple, Union
from GridCalEngine.basic_structures import Vec, CxVec, IntVec, csr_matrix, csc_matrix
from GridCalEngine.enumerations import ReactivePowerControlMode


def x2var(x: Vec,
          nVa: int,
          nVm: int,
          nPg: int,
          nQg: int,
          npq: int,
          M: int,
          ntapm: int,
          ntapt: int,
          ndc: int) -> Tuple[Vec, Vec, Vec, Vec, Vec, Vec, Vec, Vec, Vec, Vec, Vec]:
    """
    Convert the x solution vector to its composing variables
    :param x: solution vector
    :param nVa: number of voltage angle vars
    :param nVm: number of voltage module vars
    :param nPg: number of generator active power vars
    :param nQg: number of generator reactive power vars
    :param npq:
    :param M:
    :param ntapm:
    :param ntapt:
    :param ndc:
    :return:
    """
    a = 0
    b = nVa

    Va = x[a: b]
    a = b
    b += nVm

    Vm = x[a: b]
    a = b
    b += nPg

    Pg = x[a: b]
    a = b
    b += nQg

    Qg = x[a: b]
    a = b
    b += M

    sl_sf = x[a: b]
    a = b
    b += M

    sl_st = x[a: b]
    a = b
    b += npq

    sl_vmax = x[a: b]
    a = b
    b += npq

    sl_vmin = x[a: b]
    a = b
    b += ntapm

    tapm = x[a: b]
    a = b
    b += ntapt

    tapt = x[a: b]
    a = b
    b += ndc

    Pfdc = x[a: b]

    return Va, Vm, Pg, Qg, sl_sf, sl_st, sl_vmax, sl_vmin, tapm, tapt, Pfdc


def var2x(Va: Vec,
          Vm: Vec,
          Pg: Vec,
          Qg: Vec,
          sl_sf: Vec,
          sl_st: Vec,
          sl_vmax: Vec,
          sl_vmin: Vec,
          tapm: Vec,
          tapt: Vec,
          Pfdc: Vec) -> Vec:
    """
    Compose the x vector from its components
    :param Va: Voltage angles
    :param Vm: Voltage modules
    :param Pg: Generator active powers
    :param Qg: Generator reactive powers
    :param sl_sf:
    :param sl_st:
    :param sl_vmax:
    :param sl_vmin:
    :param tapm:
    :param tapt:
    :param Pfdc:
    :return: [Va, Vm, Pg, Qg, sl_sf, sl_st, sl_vmax, sl_vmin, tapm, tapt, Pfdc]
    """
    return np.r_[Va, Vm, Pg, Qg, sl_sf, sl_st, sl_vmax, sl_vmin, tapm, tapt, Pfdc]


def compute_branch_power_derivatives(alltapm: Vec,
                                     alltapt: Vec,
                                     V: CxVec,
                                     k_m: Vec,
                                     k_tau: Vec,
                                     Cf: csc,
                                     Ct: csc,
                                     R: Vec,
                                     X: Vec) -> Tuple[csr_matrix, lil_matrix, lil_matrix, csr_matrix, lil_matrix,
lil_matrix]:
    """

    :param alltapm:
    :param alltapt:
    :param V:
    :param k_m:
    :param k_tau:
    :param Cf:
    :param Ct:
    :param R:
    :param X:
    :return: [dSbusdm, dSfdm, dStdm, dSbusdt, dSfdt, dStdt]
    """
    ys = 1.0 / (R + 1.0j * X + 1e-20)

    Vf = Cf @ V
    Vt = Ct @ V
    N = len(alltapm)
    dSfdm = lil_matrix((N, len(k_m)), dtype=complex)
    dStdm = lil_matrix((N, len(k_m)), dtype=complex)
    dSfdt = lil_matrix((N, len(k_tau)), dtype=complex)
    dStdt = lil_matrix((N, len(k_tau)), dtype=complex)

    for mod, line in enumerate(k_m):
        Vf_ = Vf[line]
        Vt_ = Vt[line]
        mp = alltapm[line]
        tau = alltapt[line]
        yk = ys[line]

        dSfdm[line, mod] = Vf_ * ((-2 * np.conj(yk * Vf_) / mp ** 3) + np.conj(yk * Vt_) / (mp ** 2 * np.exp(1j * tau)))
        dStdm[line, mod] = Vt_ * (np.conj(yk * Vf_) / (mp ** 2 * np.exp(-1j * tau)))

    for ang, line in enumerate(k_tau):
        Vf_ = Vf[line]
        Vt_ = Vt[line]
        mp = alltapm[line]
        tau = alltapt[line]
        yk = ys[line]

        dSfdt[line, ang] = Vf_ * 1j * np.conj(yk * Vt_) / (mp * np.exp(1j * tau))
        dStdt[line, ang] = Vt_ * -1j * np.conj(yk * Vf_) / (mp * np.exp(-1j * tau))

    dSbusdm = Cf.T @ dSfdm + Ct.T @ dStdm
    dSbusdt = Cf.T @ dSfdt + Ct.T @ dStdt

    return dSbusdm, dSfdm, dStdm, dSbusdt, dSfdt, dStdt


def compute_branch_power_second_derivatives(alltapm: Vec,
                                            alltapt: Vec,
                                            vm: Vec,
                                            va: Vec,
                                            k_m: Vec,
                                            k_tau: Vec,
                                            il: Vec,
                                            Cf: csc,
                                            Ct: csc,
                                            R: Vec,
                                            X: Vec,
                                            F: Vec,
                                            T: Vec,
                                            lam: Vec,
                                            mu: Vec,
                                            Sf: CxVec,
                                            St: CxVec) -> Tuple[lil_matrix, lil_matrix, lil_matrix,
lil_matrix, lil_matrix, lil_matrix,
lil_matrix, lil_matrix, lil_matrix,
lil_matrix, lil_matrix, lil_matrix,
lil_matrix, lil_matrix, lil_matrix,
lil_matrix, lil_matrix, lil_matrix,
lil_matrix, lil_matrix, lil_matrix]:
    """
    :param alltapm:
    :param alltapt:
    :param vm:
    :param va:
    :param k_m:
    :param k_tau:
    :param il:
    :param Cf:
    :param Ct:
    :param R:
    :param X:
    :param F:
    :param T:
    :param lam:
    :param mu:
    :param Sf:
    :param St:
    :return:
    """
    ys = 1.0 / (R + 1.0j * X + 1e-20)
    V = vm * np.exp(1j * va)
    Vf = Cf @ V
    Vt = Ct @ V
    N = len(vm)
    M = len(il)
    ntapm = len(k_m)
    ntapt = len(k_tau)

    dSbusdmdm = lil_matrix((ntapm, ntapm))
    dSfdmdm = lil_matrix((ntapm, ntapm), dtype=complex)
    dStdmdm = lil_matrix((ntapm, ntapm), dtype=complex)

    dSbusdmdva = lil_matrix((N, ntapm))
    dSfdmdva = lil_matrix((N, ntapm), dtype=complex)
    dStdmdva = lil_matrix((N, ntapm), dtype=complex)

    dSbusdmdvm = lil_matrix((N, ntapm))
    dSfdmdvm = lil_matrix((N, ntapm), dtype=complex)
    dStdmdvm = lil_matrix((N, ntapm), dtype=complex)

    dSbusdtdt = lil_matrix((ntapt, ntapt))
    dSfdtdt = lil_matrix((ntapt, ntapt), dtype=complex)
    dStdtdt = lil_matrix((ntapt, ntapt), dtype=complex)

    dSbusdtdva = lil_matrix((N, ntapt))
    dSfdtdva = lil_matrix((N, ntapt), dtype=complex)
    dStdtdva = lil_matrix((N, ntapt), dtype=complex)

    dSbusdtdvm = lil_matrix((N, ntapt))
    dSfdtdvm = lil_matrix((N, ntapt), dtype=complex)
    dStdtdvm = lil_matrix((N, ntapt), dtype=complex)

    dSbusdmdt = lil_matrix((ntapt, ntapm))
    dSfdmdt = lil_matrix((ntapt, ntapm), dtype=complex)
    dStdmdt = lil_matrix((ntapt, ntapm), dtype=complex)

    for mod, line in enumerate(k_m):
        Vf_ = Vf[line]
        Vt_ = Vt[line]
        mp = alltapm[line]
        tau = alltapt[line]
        yk = ys[line]

        f = F[line]
        t = T[line]

        dSfdmdm_ = Vf_ * ((6 * np.conj(yk * Vf_) / mp ** 4) - 2 * np.conj(yk * Vt_) / (mp ** 3 * np.exp(1j * tau)))
        dStdmdm_ = - Vt_ * 2 * np.conj(yk * Vf_) / (mp ** 3 * np.exp(-1j * tau))

        dSfdmdva_f = Vf_ * 1j * np.conj(yk * Vt_) / (mp ** 2 * np.exp(1j * tau))
        dSfdmdva_t = - Vf_ * 1j * np.conj(yk * Vt_) / (mp ** 2 * np.exp(1j * tau))

        dStdmdva_f = - Vt_ * 1j * np.conj(yk * Vf_) / (mp ** 2 * np.exp(-1j * tau))
        dStdmdva_t = Vt_ * 1j * np.conj(yk * Vf_) / (mp ** 2 * np.exp(-1j * tau))

        dSfdmdvm_f = Vf_ * (1 / vm[f]) * ((-4 * np.conj(yk * Vf_) / mp ** 3)
                                          + np.conj(yk * Vt_) / (mp ** 2 * np.exp(1j * tau)))
        dSfdmdvm_t = Vf_ * (1 / vm[t]) * np.conj(yk * Vt_) / (mp ** 2 * np.exp(1j * tau))

        dStdmdvm_f = Vt_ * (1 / vm[f]) * np.conj(yk * Vf_) / (mp ** 2 * np.exp(-1j * tau))
        dStdmdvm_t = Vt_ * (1 / vm[t]) * np.conj(yk * Vf_) / (mp ** 2 * np.exp(-1j * tau))

        l = np.where(k_tau == line)[0]
        if len(l) != 0:
            ang = l[0]

            dSfdmdt_ = - Vf_ * 1j * (np.conj(yk * Vt_) / (mp ** 2 * np.exp(1j * tau)))
            dStdmdt_ = Vt_ * 1j * (np.conj(yk * Vf_) / (mp ** 2 * np.exp(-1j * tau)))

            dSbusdmdt[ang, mod] = ((dSfdmdt_ * lam[f]).real + (dSfdmdt_ * lam[f + N]).imag
                                   + (dStdmdt_ * lam[t]).real + (dStdmdt_ * lam[t + N]).imag)
            if line in il:
                li = np.where(il == line)[0]
                dSfdmdt[ang, mod] = dSfdmdt_ * Sf[li].conj() * mu[li]
                dStdmdt[ang, mod] = dStdmdt_ * St[li].conj() * mu[li + M]

        dSbusdmdm[mod, mod] = ((dSfdmdm_ * lam[f]).real + (dSfdmdm_ * lam[f + N]).imag
                               + (dStdmdm_ * lam[t]).real + (dStdmdm_ * lam[t + N]).imag)
        dSbusdmdva[f, mod] = ((dSfdmdva_f * lam[f]).real + (dSfdmdva_f * lam[f + N]).imag
                              + (dStdmdva_f * lam[t]).real + (dStdmdva_f * lam[t + N]).imag)
        dSbusdmdva[t, mod] = ((dSfdmdva_t * lam[f]).real + (dSfdmdva_t * lam[f + N]).imag
                              + (dStdmdva_t * lam[t]).real + (dStdmdva_t * lam[t + N]).imag)
        dSbusdmdvm[f, mod] = ((dSfdmdvm_f * lam[f]).real + (dSfdmdvm_f * lam[f + N]).imag
                              + (dStdmdvm_f * lam[t]).real + (dStdmdvm_f * lam[t + N]).imag)
        dSbusdmdvm[t, mod] = ((dSfdmdvm_t * lam[f]).real + (dSfdmdvm_t * lam[f + N]).imag
                              + (dStdmdvm_t * lam[t]).real + (dStdmdvm_t * lam[t + N]).imag)

        if line in il:
            li = np.where(il == line)[0]
            dSfdmdm[mod, mod] = dSfdmdm_ * Sf[li].conj() * mu[li]
            dStdmdm[mod, mod] = dStdmdm_ * St[li].conj() * mu[li + M]
            dSfdmdva[f, mod] = dSfdmdva_f * Sf[li].conj() * mu[li]
            dStdmdva[f, mod] = dStdmdva_f * St[li].conj() * mu[li + M]
            dSfdmdva[t, mod] = dSfdmdva_t * Sf[li].conj() * mu[li]
            dStdmdva[t, mod] = dStdmdva_t * St[li].conj() * mu[li + M]
            dSfdmdvm[f, mod] = dSfdmdvm_f * Sf[li].conj() * mu[li]
            dStdmdvm[f, mod] = dStdmdvm_f * St[li].conj() * mu[li + M]
            dSfdmdvm[t, mod] = dSfdmdvm_t * Sf[li].conj() * mu[li]
            dStdmdvm[t, mod] = dStdmdvm_t * St[li].conj() * mu[li + M]

    for ang, line in enumerate(k_tau):
        Vf_ = Vf[line]
        Vt_ = Vt[line]
        mp = alltapm[line]
        tau = alltapt[line]
        yk = ys[line]

        f = F[line]
        t = T[line]

        dSfdtdt_ = Vf_ * np.conj(yk * Vt_) / (mp * np.exp(1j * tau))
        dStdtdt_ = Vt_ * np.conj(yk * Vf_) / (mp * np.exp(-1j * tau))

        dSfdtdva_f = - Vf_ * np.conj(yk * Vt_) / (mp * np.exp(1j * tau))
        dSfdtdva_t = Vf_ * np.conj(yk * Vt_) / (mp * np.exp(1j * tau))

        dStdtdva_f = - Vt_ * np.conj(yk * Vf_) / (mp * np.exp(-1j * tau))
        dStdtdva_t = Vt_ * np.conj(yk * Vf_) / (mp * np.exp(-1j * tau))

        dSfdtdvm_f = 1j * Vf_ / abs(Vf_) * np.conj(yk * Vt_) / (mp * np.exp(1j * tau))
        dSfdtdvm_t = 1j * Vf_ / abs(Vt_) * np.conj(yk * Vt_) / (mp * np.exp(1j * tau))

        dStdtdvm_f = -1j * Vt_ / abs(Vf_) * np.conj(yk * Vf_) / (mp * np.exp(-1j * tau))
        dStdtdvm_t = -1j * Vt_ / abs(Vt_) * np.conj(yk * Vf_) / (mp * np.exp(-1j * tau))

        # Merge Sf and St in Sbus
        dSbusdtdt[ang, ang] = ((dSfdtdt_ * lam[f]).real + (dSfdtdt_ * lam[f + N]).imag
                               + (dStdtdt_ * lam[t]).real + (dStdtdt_ * lam[t + N]).imag)
        dSbusdtdva[f, ang] = ((dSfdtdva_f * lam[f]).real + (dSfdtdva_f * lam[f + N]).imag
                              + (dStdtdva_f * lam[t]).real + (dStdtdva_f * lam[t + N]).imag)
        dSbusdtdva[t, ang] = ((dSfdtdva_t * lam[f]).real + (dSfdtdva_t * lam[f + N]).imag
                              + (dStdtdva_t * lam[t]).real + (dStdtdva_t * lam[t + N]).imag)
        dSbusdtdvm[f, ang] = ((dSfdtdvm_f * lam[f]).real + (dSfdtdvm_f * lam[f + N]).imag
                              + (dStdtdvm_f * lam[t]).real + (dStdtdvm_f * lam[t + N]).imag)
        dSbusdtdvm[t, ang] = ((dSfdtdvm_t * lam[f]).real + (dSfdtdvm_t * lam[f + N]).imag
                              + (dStdtdvm_t * lam[t]).real + (dStdtdvm_t * lam[t + N]).imag)
        dSbusdtdt[ang, ang] = ((dSfdtdt_ * lam[f]).real + (dSfdtdt_ * lam[f + N]).imag
                               + (dStdtdt_ * lam[t]).real + (dStdtdt_ * lam[t + N]).imag)

        if line in il:
            li = np.where(il == line)[0]
            dSfdtdt[ang, ang] = dSfdtdt_ * Sf[li].conj() * mu[li]
            dStdtdt[ang, ang] = dStdtdt_ * St[li].conj() * mu[li + M]
            dSfdtdva[f, ang] = dSfdtdva_f * Sf[li].conj() * mu[li]
            dStdtdva[f, ang] = dStdtdva_f * St[li].conj() * mu[li + M]
            dSfdtdva[t, ang] = dSfdtdva_t * Sf[li].conj() * mu[li]
            dStdtdva[t, ang] = dStdtdva_t * St[li].conj() * mu[li + M]
            dSfdtdvm[f, ang] = dSfdtdvm_f * Sf[li].conj() * mu[li]
            dStdtdvm[f, ang] = dStdtdvm_f * St[li].conj() * mu[li + M]
            dSfdtdvm[t, ang] = dSfdtdvm_t * Sf[li].conj() * mu[li]
            dStdtdvm[t, ang] = dStdtdvm_t * St[li].conj() * mu[li + M]
            dSfdtdt[ang, ang] = dSfdtdt_ * Sf[li].conj() * mu[li]
            dStdtdt[ang, ang] = dStdtdt_ * St[li].conj() * mu[li + M]

    return (dSbusdmdm, dSfdmdm, dStdmdm,
            dSbusdmdvm, dSfdmdvm, dStdmdvm,
            dSbusdmdva, dSfdmdva, dStdmdva,
            dSbusdmdt, dSfdmdt, dStdmdt,
            dSbusdtdt, dSfdtdt, dStdtdt,
            dSbusdtdvm, dSfdtdvm, dStdtdvm,
            dSbusdtdva, dSfdtdva, dStdtdva)


def eval_f(x: Vec, Cg: csr_matrix, k_m: Vec, k_tau: Vec, nll: int, c0: Vec, c1: Vec, c2: Vec, c_s: Vec,
           c_v: Vec, ig: Vec, npq: int, ndc: int, Sbase: float) -> float:
    """

    :param x:
    :param Cg:
    :param k_m:
    :param k_tau:
    :param nll:
    :param c0:
    :param c1:
    :param c2:
    :param c_s:
    :param c_v:
    :param ig:
    :param npq:
    :param ndc:
    :param Sbase:
    :return:
    """
    N, _ = Cg.shape  # Check
    Ng = len(ig)
    ntapm = len(k_m)
    ntapt = len(k_tau)

    _, _, Pg, Qg, sl_sf, sl_st, sl_vmax, sl_vmin, _, _, _ = x2var(x, nVa=N, nVm=N, nPg=Ng, nQg=Ng, npq=npq,
                                                                  M=nll, ntapm=ntapm, ntapt=ntapt, ndc=ndc)

    fval = 1e-4 * (np.sum((c0 + c1 * Pg * Sbase + c2 * np.power(Pg * Sbase, 2)))
                   + np.sum(c_s * (sl_sf + sl_st)) + np.sum(c_v * (sl_vmax + sl_vmin)))

    return fval


def eval_g(x: Vec, Ybus: csr_matrix, Yf: csr_matrix, Cg: csr_matrix, Sd: CxVec, ig: Vec, nig: Vec, nll: int, npq: int,
           pv: Vec, fdc: Vec, tdc: Vec, k_m: Vec, k_tau: Vec, Vm_max: Vec, Sg_undis: CxVec, slack: Vec) \
        -> Tuple[Vec, Vec]:
    """

    :param x:
    :param Ybus:
    :param Yf:
    :param Cg:
    :param Sd:
    :param ig: indices of dispatchable gens
    :param nig: indices of non dispatchable gens
    :param nll:
    :param npq:
    :param pv:
    :param fdc:
    :param tdc:
    :param k_m:
    :param k_tau:
    :param Vm_max:
    :param Sg_undis: undispatchable complex power
    :param slack:
    :return:
    """
    M, N = Yf.shape
    Ng = len(ig)
    ntapm = len(k_m)
    ntapt = len(k_tau)
    ndc = len(fdc)

    va, vm, Pg_dis, Qg_dis, sl_sf, sl_st, sl_vmax, sl_vmin, _, _, Pfdc = x2var(x, nVa=N, nVm=N, nPg=Ng, nQg=Ng, npq=npq,
                                                                               M=nll, ntapm=ntapm, ntapt=ntapt, ndc=ndc)

    V = vm * np.exp(1j * va)
    S = V * np.conj(Ybus @ V)
    S_dispatch = Cg[:, ig] @ (Pg_dis + 1j * Qg_dis)
    S_undispatch = Cg[:, nig] @ Sg_undis
    dS = S + Sd - S_dispatch - S_undispatch

    if ndc != 0:
        dS[fdc] += Pfdc  # Lossless model. Pdc_From = Pdc_To
        dS[tdc] -= Pfdc

    gval = np.r_[dS.real, dS.imag, va[slack], vm[pv] - Vm_max[pv]]

    return gval, S


def eval_h(x, Yf, Yt, from_idx, to_idx, pq, k_m, k_tau, Vm_max,
           Vm_min, Pg_max, Pg_min, Qg_max, Qg_min, tapm_max,
           tapm_min, tapt_max, tapt_min, Pdcmax, rates,
           il, ig, tanmax, ctQ: ReactivePowerControlMode) -> Tuple[Vec, Vec, Vec]:
    """

    :param x:
    :param Yf:
    :param Yt:
    :param from_idx:
    :param to_idx:
    :param pq:
    :param k_m:
    :param k_tau:
    :param Vm_max:
    :param Vm_min:
    :param Pg_max:
    :param Pg_min:
    :param Qg_max:
    :param Qg_min:
    :param tapm_max:
    :param tapm_min:
    :param tapt_max:
    :param tapt_min:
    :param Pdcmax:
    :param rates:
    :param il: relevant lines to check rating
    :param ig:
    :param tanmax:
    :param ctQ:
    :return:
    """
    M, N = Yf.shape
    Ng = len(ig)
    ntapm = len(k_m)
    ntapt = len(k_tau)
    ndc = len(Pdcmax)
    npq = len(pq)
    nll = len(il)

    va, vm, Pg, Qg, sl_sf, sl_st, sl_vmax, sl_vmin, tapm, tapt, Pfdc = x2var(x, nVa=N, nVm=N, nPg=Ng, nQg=Ng, npq=npq,
                                                                             M=nll, ntapm=ntapm, ntapt=ntapt, ndc=ndc)

    V = vm * np.exp(1j * va)
    Sf = V[from_idx[il]] * np.conj(Yf[il, :] @ V)
    St = V[to_idx[il]] * np.conj(Yt[il, :] @ V)

    Sftot = V[from_idx] * np.conj(Yf @ V)
    Sttot = V[to_idx] * np.conj(Yt @ V)

    Sf2 = np.conj(Sf) * Sf
    St2 = np.conj(St) * St

    hval = np.r_[
        Sf2.real - (rates[il] ** 2) - sl_sf,  # rates "lower limit"
        St2.real - (rates[il] ** 2) - sl_st,  # rates "upper limit"
        vm[pq] - Vm_max[pq] - sl_vmax,  # voltage module upper limit
        Pg - Pg_max[ig],  # generator P upper limits
        Qg - Qg_max[ig],  # generator Q upper limits
        Vm_min[pq] - vm[pq] - sl_vmin,  # voltage module lower limit
        Pg_min[ig] - Pg,  # generator P lower limits
        Qg_min[ig] - Qg,  # generation Q lower limits
        - sl_sf,
        - sl_st,
        - sl_vmax,
        - sl_vmin,
        tapm - tapm_max,
        tapm_min - tapm,
        tapt - tapt_max,
        tapt_min - tapt
    ]

    if ctQ != ReactivePowerControlMode.NoControl:
        hval = np.r_[hval, Qg ** 2 - tanmax ** 2 * Pg ** 2]

    if ndc != 0:
        hval = np.r_[hval, Pfdc - Pdcmax, - Pdcmax - Pfdc]

    return hval, Sftot, Sttot


def jacobians_and_hessians(x, c1, c2, c_s, c_v, Cg, Cf, Ct, Yf, Yt, Ybus, Sbase, il, ig, slack, pq,
                           pv, tanmax, alltapm, alltapt, fdc, tdc, k_m, k_tau, mu, lmbda, R, X, F, T,
                           ctQ: ReactivePowerControlMode, compute_jac: bool, compute_hess: bool):
    """

    :param x:
    :param c1:
    :param c2:
    :param c_s:
    :param c_v:
    :param Cg:
    :param Cf:
    :param Ct:
    :param Yf:
    :param Yt:
    :param Ybus:
    :param Sbase:
    :param il: relevant lines to check rating
    :param ig:
    :param slack:
    :param pq:
    :param pv:
    :param tanmax:
    :param alltapm:
    :param alltapt:
    :param fdc:
    :param tdc:
    :param k_m:
    :param k_tau:
    :param mu:
    :param lmbda:
    :param R:
    :param X:
    :param F:
    :param T:
    :param ctQ:
    :param compute_jac:
    :param compute_hess:
    :return:
    """
    Mm, N = Yf.shape
    M = len(il)
    Ng = len(ig)
    NV = len(x)
    ntapm = len(k_m)
    ntapt = len(k_tau)
    ndc = len(fdc)
    npq = len(pq)

    va, vm, Pg, Qg, sl_sf, sl_st, sl_vmax, sl_vmin, tapm, tapt, Pfdc = x2var(x, nVa=N, nVm=N, nPg=Ng, nQg=Ng, npq=npq,
                                                                             M=M, ntapm=ntapm, ntapt=ntapt, ndc=ndc)
    nsl = 2 * npq + 2 * M
    npfvar = 2 * N + 2 * Ng  # Number of variables of the typical power flow (V, th, P, Q). Used to ease readability

    V = vm * np.exp(1j * va)
    Vmat = diags(V)
    vm_inv = diags(1 / vm)
    E = Vmat @ vm_inv
    Ibus = Ybus @ V
    IbusCJmat = diags(np.conj(Ibus))
    alltapm[k_m] = tapm
    alltapt[k_tau] = tapt

    if compute_jac:

        # OBJECTIVE FUNCTION GRAD --------------------------------------------------------------------------------------

        fx = np.zeros(NV)

        fx[2 * N: 2 * N + Ng] = (2 * c2 * Pg * (Sbase ** 2) + c1 * Sbase) * 1e-4

        fx[npfvar: npfvar + M] = c_s
        fx[npfvar + M: npfvar + 2 * M] = c_s
        fx[npfvar + 2 * M: npfvar + 2 * M + npq] = c_v
        fx[npfvar + 2 * M + npq: npfvar + 2 * M + 2 * npq] = c_v

        # EQUALITY CONSTRAINTS GRAD ------------------------------------------------------------------------------------

        Vva = 1j * Vmat

        GSvm = Vmat @ (IbusCJmat + np.conj(Ybus) @ np.conj(Vmat)) @ vm_inv
        GSva = Vva @ (IbusCJmat - np.conj(Ybus) @ np.conj(Vmat))
        GSpg = -Cg[:, ig]
        GSqg = -1j * Cg[:, ig]

        GTH = lil_matrix((len(slack), NV))
        for i, ss in enumerate(slack):
            GTH[i, ss] = 1.

        Gvm = lil_matrix((len(pv), NV))
        for i, ss in enumerate(pv):
            Gvm[i, N + ss] = 1.

        if ntapm + ntapt != 0:  # Check if there are tap variables that can affect the admittances

            (dSbusdm, dSfdm, dStdm,
             dSbusdt, dSfdt, dStdt) = compute_branch_power_derivatives(alltapm, alltapt, V, k_m, k_tau, Cf, Ct, R, X)

            if ntapm != 0:
                GStapm = dSbusdm.copy()
            else:
                GStapm = lil_matrix((N, 0))
                dSbusdm, dSfdm, dStdm = None, None, None  # Check

            if ntapt != 0:
                GStapt = dSbusdt.copy()
            else:
                GStapt = lil_matrix((N,0))
                dSbusdt, dSfdt, dStdt = None, None, None  # Check
        else:
            GStapm = lil_matrix((N, 0))
            GStapt = lil_matrix((N, 0))
            dSbusdm, dSfdm, dStdm, dSbusdt, dSfdt, dStdt = (None, None, None, None, None, None)

        GSpfdc = lil_matrix((N, ndc))

        for link in range(ndc):
            GSpfdc[fdc, link] = 1
            GSpfdc[tdc, link] = -1

        GS = sp.hstack([GSva, GSvm, GSpg, GSqg, lil_matrix((N, nsl)), GStapm, GStapt, GSpfdc])

        Gx = sp.vstack([GS.real, GS.imag, GTH, Gvm]).T.tocsc()

        # INEQUALITY CONSTRAINTS GRAD ----------------------------------------------------------------------------------

        Vfmat = diags(Cf[il, :] @ V)
        Vtmat = diags(Ct[il, :] @ V)

        IfCJmat = np.conj(diags(Yf[il, :] @ V))
        ItCJmat = np.conj(diags(Yt[il, :] @ V))
        Sf = Vfmat @ np.conj(Yf[il, :] @ V)
        St = Vtmat @ np.conj(Yt[il, :] @ V)

        allSf = diags(Cf @ V) @ np.conj(Yf @ V)
        allSt = diags(Ct @ V) @ np.conj(Yt @ V)

        Sfmat = diags(Sf)
        Stmat = diags(St)

        Sfvm = (IfCJmat @ Cf[il, :] @ E + Vfmat @ np.conj(Yf[il, :]) @ np.conj(E))
        Stvm = (ItCJmat @ Ct[il, :] @ E + Vtmat @ np.conj(Yt[il, :]) @ np.conj(E))

        Sfva = (1j * (IfCJmat @ Cf[il, :] @ Vmat - Vfmat @ np.conj(Yf[il, :]) @ np.conj(Vmat)))
        Stva = (1j * (ItCJmat @ Ct[il, :] @ Vmat - Vtmat @ np.conj(Yt[il, :]) @ np.conj(Vmat)))

        Hvu = sp.hstack([lil_matrix((npq, N)), diags(np.ones(npq)), lil_matrix((npq, 2 * Ng + 2 * M)),
                         diags(-np.ones(npq)), lil_matrix((npq, npq + ntapm + ntapt + ndc))])

        Hvl = sp.hstack([lil_matrix((npq, N)), diags(- np.ones(npq)), lil_matrix((npq, 2 * Ng + 2 * M + npq)),
                         diags(-np.ones(npq)), lil_matrix((npq, ntapm + ntapt + ndc))])

        Hpu = sp.hstack([lil_matrix((Ng, 2 * N)), diags(np.ones(Ng)), lil_matrix((Ng, NV - 2 * N - Ng))])
        Hpl = sp.hstack([lil_matrix((Ng, 2 * N)), diags(- np.ones(Ng)), lil_matrix((Ng, NV - 2 * N - Ng))])
        Hqu = sp.hstack([lil_matrix((Ng, 2 * N + Ng)), diags(np.ones(Ng)), lil_matrix((Ng, NV - 2 * N - 2 * Ng))])
        Hql = sp.hstack([lil_matrix((Ng, 2 * N + Ng)), diags(- np.ones(Ng)), lil_matrix((Ng, NV - 2 * N - 2 * Ng))])

        Hslsf = sp.hstack([lil_matrix((M, npfvar)), diags(- np.ones(M)),
                           lil_matrix((M, M + 2 * npq + ntapm + ntapt + ndc))])

        Hslst = sp.hstack([lil_matrix((M, npfvar + M)), diags(- np.ones(M)),
                           lil_matrix((M, 2 * npq + ntapm + ntapt + ndc))])

        Hslvmax = sp.hstack([lil_matrix((npq, npfvar + 2 * M)), diags(- np.ones(npq)),
                             lil_matrix((npq, npq + ntapm + ntapt + ndc))])

        Hslvmin = sp.hstack([lil_matrix((npq, npfvar + 2 * M + npq)), diags(- np.ones(npq)),
                             lil_matrix((npq, ntapm + ntapt + ndc))])

        if (ntapm + ntapt) != 0:

            Sftapm = dSfdm[il, :].copy()
            Sftapt = dSfdt[il, :].copy()
            Sttapm = dStdm[il, :].copy()
            Sttapt = dStdt[il, :].copy()

            SfX = sp.hstack([Sfva, Sfvm, lil_matrix((M, 2 * Ng + nsl)), Sftapm, Sftapt, lil_matrix((M, ndc))])
            StX = sp.hstack([Stva, Stvm, lil_matrix((M, 2 * Ng + nsl)), Sttapm, Sttapt, lil_matrix((M, ndc))])

            HSf = 2 * (Sfmat.real @ SfX.real + Sfmat.imag @ SfX.imag) + Hslsf
            HSt = 2 * (Stmat.real @ StX.real + Stmat.imag @ StX.imag) + Hslst

            if ntapm != 0:
                Htapmu = sp.hstack([lil_matrix((ntapm, npfvar + nsl)), diags(np.ones(ntapm)),
                                    lil_matrix((ntapm, ntapt + ndc))])

                Htapml = sp.hstack([lil_matrix((ntapm, npfvar + nsl)), diags(- np.ones(ntapm)),
                                    lil_matrix((ntapm, ntapt + ndc))])

            else:
                Htapmu = lil_matrix((0, NV))
                Htapml = lil_matrix((0, NV))

            if ntapt != 0:
                Htaptu = sp.hstack([lil_matrix((ntapt, npfvar + nsl + ntapm)), diags(np.ones(ntapt)),
                                    lil_matrix((ntapt, ndc))])
                Htaptl = sp.hstack([lil_matrix((ntapt, npfvar + nsl + ntapm)), diags(- np.ones(ntapt)),
                                    lil_matrix((ntapt, ndc))])

            else:
                Htaptu = lil_matrix((0, NV))
                Htaptl = lil_matrix((0, NV))

        else:
            Sftapm = None
            Sftapt = None
            Sttapm = None
            Sttapt = None

            Htapmu = lil_matrix((0, NV))
            Htapml = lil_matrix((0, NV))
            Htaptu = lil_matrix((0, NV))
            Htaptl = lil_matrix((0, NV))

            SfX = sp.hstack([Sfva, Sfvm, lil_matrix((M, 2 * Ng + nsl + ndc))])
            StX = sp.hstack([Stva, Stvm, lil_matrix((M, 2 * Ng + nsl + ndc))])

            HSf = 2 * (Sfmat.real @ SfX.real + Sfmat.imag @ SfX.imag)
            HSt = 2 * (Stmat.real @ StX.real + Stmat.imag @ StX.imag)

        if ctQ != ReactivePowerControlMode.NoControl:
            # tanmax curves (simplified capability curves of generators)
            Hqmaxp = -2 * (tanmax ** 2) * Pg
            Hqmaxq = 2 * Qg

            Hqmax = sp.hstack([lil_matrix((Ng, 2 * N)), diags(Hqmaxp), diags(Hqmaxq),
                               lil_matrix((Ng, nsl + ntapm + ntapt + ndc))])
        else:
            Hqmax = lil_matrix((0, NV))

        Hdcu = sp.hstack([lil_matrix((ndc, NV - ndc)), diags(np.ones(ndc))])
        Hdcl = sp.hstack([lil_matrix((ndc, NV - ndc)), diags(-np.ones(ndc))])

        Hx = sp.vstack([HSf, HSt, Hvu, Hpu, Hqu, Hvl, Hpl, Hql, Hslsf, Hslst, Hslvmax,
                        Hslvmin, Htapmu, Htapml, Htaptu, Htaptl, Hqmax, Hdcu, Hdcl])

        Hx = Hx.T.tocsc()

    else:
        fx = None
        Gx = None
        Hx = None
        allSf = None
        Sfmat = None
        allSt = None
        Stmat = None
        Sfva = None
        Sfvm = None
        Sftapm = None
        Sftapt = None
        Stva = None
        Stvm = None
        Sttapm = None
        Sttapt = None

    # HESSIANS ---------------------------------------------------------------------------------------------------------

    if compute_hess:

        assert compute_jac  # we must have the jacobian values to get into here

        # OBJECTIVE FUNCITON HESS --------------------------------------------------------------------------------------

        fxx = diags((np.r_[
            np.zeros(2 * N),
            2 * c2 * (Sbase ** 2),
            np.zeros(Ng + nsl + ntapm + ntapt + ndc)
        ]) * 1e-4).tocsc()

        # EQUALITY CONSTRAINTS HESS ------------------------------------------------------------------------------------

        # P
        lam_p = lmbda[0:N]
        lam_diag_p = diags(lam_p)

        B_p = np.conj(Ybus) @ np.conj(Vmat)
        D_p = np.conj(Ybus).T @ Vmat
        Ibus_p = Ybus @ V
        I_p = np.conj(Vmat) @ (D_p @ lam_diag_p - diags(D_p @ lam_p))
        F_p = lam_diag_p @ Vmat @ (B_p - diags(np.conj(Ibus_p)))
        C_p = lam_diag_p @ Vmat @ B_p

        Gaa_p = I_p + F_p
        Gva_p = 1j * vm_inv @ (I_p - F_p)
        Gvv_p = vm_inv @ (C_p + C_p.T) @ vm_inv

        # Q
        lam_q = lmbda[N:2 * N]
        lam_diag_q = diags(lam_q)

        B_q = np.conj(Ybus) @ np.conj(Vmat)
        D_q = np.conj(Ybus).T @ Vmat
        Ibus_q = Ybus @ V
        I_q = np.conj(Vmat) @ (D_q @ lam_diag_q - diags(D_q @ lam_q))
        F_q = lam_diag_q @ Vmat @ (B_q - diags(np.conj(Ibus_q)))
        C_q = lam_diag_q @ Vmat @ B_q

        Gaa_q = I_q + F_q
        Gva_q = 1j * vm_inv @ (I_q - F_q)
        Gvv_q = vm_inv @ (C_q + C_q.T) @ vm_inv

        Gaa = Gaa_p.real + Gaa_q.imag
        Gva = Gva_p.real + Gva_q.imag
        Gav = Gva.T
        Gvv = Gvv_p.real + Gvv_q.imag

        if ntapm + ntapt != 0:
            (GSdmdm, dSfdmdm, dStdmdm,
             GSdmdvm, dSfdmdvm, dStdmdvm,
             GSdmdva, dSfdmdva, dStdmdva,
             GSdmdt, dSfdmdt, dStdmdt,
             GSdtdt, dSfdtdt, dStdtdt,
             GSdtdvm, dSfdtdvm, dStdtdvm,
             GSdtdva, dSfdtdva, dStdtdva) = compute_branch_power_second_derivatives(alltapm, alltapt, vm, va, k_m,
                                                                                    k_tau, il, Cf, Ct, R, X, F, T,
                                                                                    lmbda[0: 2 * N], mu[0: 2 * M],
                                                                                    allSf, allSt)

            G1 = sp.hstack([Gaa, Gav, lil_matrix((N, 2 * Ng + nsl)), GSdmdva, GSdtdva, lil_matrix((N, ndc))])
            G2 = sp.hstack([Gva, Gvv, lil_matrix((N, 2 * Ng + nsl)), GSdmdvm, GSdtdvm, lil_matrix((N, ndc))])
            G3 = sp.hstack([GSdmdva.T, GSdmdvm.T, lil_matrix((ntapm, 2 * Ng + nsl)),
                            GSdmdm, GSdmdt.T, lil_matrix((ntapm, ndc))])
            G4 = sp.hstack([GSdtdva.T, GSdtdvm.T, lil_matrix((ntapt, 2 * Ng + nsl)),
                            GSdmdt, GSdtdt, lil_matrix((ntapt, ndc))])

            Gxx = sp.vstack([G1, G2, lil_matrix((2 * Ng + nsl, NV)), G3, G4, lil_matrix((ndc, NV))]).tocsc()

        else:
            (dSfdmdm, dStdmdm, dSfdmdvm, dStdmdvm, dSfdmdva, dStdmdva, dSfdmdt,
             dStdmdt, dSfdtdt, dStdtdt, dSfdtdvm, dStdtdvm, dSfdtdva, dStdtdva) = (None, None, None, None, None,
                                                                                   None, None, None, None, None,
                                                                                   None, None, None, None)

            G1 = sp.hstack([Gaa, Gav, lil_matrix((N, 2 * Ng + nsl + ndc))])
            G2 = sp.hstack([Gva, Gvv, lil_matrix((N, 2 * Ng + nsl + ndc))])
            Gxx = sp.vstack([G1, G2, lil_matrix((2 * Ng + nsl + ndc, npfvar + nsl + ndc))]).tocsc()

        # INEQUALITY CONSTRAINTS HESS ----------------------------------------------------------------------------------
        muf = mu[0: M]
        mut = mu[M: 2 * M]
        muf_mat = diags(muf)
        mut_mat = diags(mut)
        Smuf_mat = diags(Sfmat.conj() @ muf)
        Smut_mat = diags(Stmat.conj() @ mut)

        Af = np.conj(Yf[il, :]).T @ Smuf_mat @ Cf[il, :]
        Bf = np.conj(Vmat) @ Af @ Vmat
        Df = diags(Af @ V) @ np.conj(Vmat)
        Ef = diags(Af.T @ np.conj(V)) @ Vmat
        Ff = Bf + Bf.T
        Sfvava = Ff - Df - Ef
        Sfvmva = 1j * vm_inv @ (Bf - Bf.T - Df + Ef)
        Sfvavm = Sfvmva.T
        Sfvmvm = vm_inv @ Ff @ vm_inv

        if ctQ != ReactivePowerControlMode.NoControl:
            Hqpgpg = diags(-2 * (tanmax ** 2) * mu[-Ng:])
            Hqqgqg = diags(np.array([2] * Ng) * mu[-Ng:])
        else:
            Hqpgpg = lil_matrix((Ng, Ng))
            Hqqgqg = lil_matrix((Ng, Ng))

        Hfvava = 2 * (Sfvava + Sfva.T @ muf_mat @ np.conj(Sfva)).real
        Hfvmva = 2 * (Sfvmva + Sfvm.T @ muf_mat @ np.conj(Sfva)).real
        Hfvavm = 2 * (Sfvavm + Sfva.T @ muf_mat @ np.conj(Sfvm)).real
        Hfvmvm = 2 * (Sfvmvm + Sfvm.T @ muf_mat @ np.conj(Sfvm)).real

        At = np.conj(Yt[il, :]).T @ Smut_mat @ Ct[il, :]
        Bt = np.conj(Vmat) @ At @ Vmat
        Dt = diags(At @ V) @ np.conj(Vmat)
        Et = diags(At.T @ np.conj(V)) @ Vmat
        Ft = Bt + Bt.T
        Stvava = Ft - Dt - Et
        Stvmva = 1j * vm_inv @ (Bt - Bt.T - Dt + Et)
        Stvavm = Stvmva.T
        Stvmvm = vm_inv @ Ft @ vm_inv

        Htvava = 2 * (Stvava + Stva.T @ mut_mat @ np.conj(Stva)).real
        Htvmva = 2 * (Stvmva + Stvm.T @ mut_mat @ np.conj(Stva)).real
        Htvavm = 2 * (Stvavm + Stva.T @ mut_mat @ np.conj(Stvm)).real
        Htvmvm = 2 * (Stvmvm + Stvm.T @ mut_mat @ np.conj(Stvm)).real

        if ntapm + ntapt != 0:

            Hftapmva = 2 * (dSfdmdva.T + Sftapm.T @ muf_mat @ np.conj(Sfva)).real
            Hftapmvm = 2 * (dSfdmdvm.T + Sftapm.T @ muf_mat @ np.conj(Sfvm)).real
            Hftaptva = 2 * (dSfdtdva.T + Sftapt.T @ muf_mat @ np.conj(Sfva)).real
            Hftaptvm = 2 * (dSfdtdvm.T + Sftapt.T @ muf_mat @ np.conj(Sfvm)).real
            Hftapmtapm = 2 * (dSfdmdm.T + Sftapm.T @ muf_mat @ np.conj(Sftapm)).real
            Hftapttapt = 2 * (dSfdtdt.T + Sftapt.T @ muf_mat @ np.conj(Sftapt)).real
            Hftapmtapt = 2 * (dSfdmdt.T + Sftapm.T @ muf_mat @ np.conj(Sftapt)).real

            Httapmva = 2 * (dStdmdva.T + Sttapm.T @ mut_mat @ np.conj(Stva)).real
            Httapmvm = 2 * (dStdmdvm.T + Sttapm.T @ mut_mat @ np.conj(Stvm)).real
            Httaptva = 2 * (dStdtdva.T + Sttapt.T @ mut_mat @ np.conj(Stva)).real
            Httaptvm = 2 * (dStdtdvm.T + Sttapt.T @ mut_mat @ np.conj(Stvm)).real
            Httapmtapm = 2 * (dStdmdm.T + Sttapm.T @ mut_mat @ np.conj(Sttapm)).real
            Httapttapt = 2 * (dStdtdt.T + Sttapt.T @ mut_mat @ np.conj(Sttapt)).real
            Httapmtapt = 2 * (dStdmdt.T + Sttapm.T @ mut_mat @ np.conj(Sttapt)).real

            H1 = sp.hstack([Hfvava + Htvava,
                            Hfvavm + Htvavm,
                            lil_matrix((N, 2 * Ng + nsl)),
                            Hftapmva.T + Httapmva.T,
                            Hftaptva.T + Httaptva.T,
                            lil_matrix((N, ndc))])

            H2 = sp.hstack([Hfvmva + Htvmva,
                            Hfvmvm + Htvmvm,
                            lil_matrix((N, 2 * Ng + nsl)),
                            Hftapmvm.T + Httapmvm.T,
                            Hftaptvm.T + Httaptvm.T,
                            lil_matrix((N, ndc))])

            H3 = sp.hstack([lil_matrix((Ng, 2 * N)), Hqpgpg, lil_matrix((Ng, Ng + nsl + ntapm + ntapt + ndc))])

            H4 = sp.hstack([lil_matrix((Ng, 2 * N + Ng)), Hqqgqg, lil_matrix((Ng, nsl + ntapm + ntapt + ndc))])

            H5 = sp.hstack([Hftapmva + Httapmva, Hftapmvm + Httapmvm, lil_matrix((ntapm, 2 * Ng + nsl)),
                            Hftapmtapm + Httapmtapm, Hftapmtapt + Httapmtapt, lil_matrix((ntapm, ndc))])

            H6 = sp.hstack([Hftaptva + Httaptva,
                            Hftaptvm + Httaptvm,
                            lil_matrix((ntapt, 2 * Ng + nsl)),
                            Hftapmtapt.T + Httapmtapt.T,
                            Hftapttapt + Httapttapt,
                            lil_matrix((ntapt, ndc))])

            Hxx = sp.vstack([H1, H2, H3, H4, lil_matrix((nsl, NV)), H5, H6, lil_matrix((ndc, NV))]).tocsc()

        else:
            H1 = sp.hstack([Hfvava + Htvava, Hfvavm + Htvavm, lil_matrix((N, 2 * Ng + nsl + ndc))])
            H2 = sp.hstack([Hfvmva + Htvmva, Hfvmvm + Htvmvm, lil_matrix((N, 2 * Ng + nsl + ndc))])
            H3 = sp.hstack([lil_matrix((Ng, 2 * N)), Hqpgpg, lil_matrix((Ng, Ng + nsl + ndc))])
            H4 = sp.hstack([lil_matrix((Ng, 2 * N + Ng)), Hqqgqg, lil_matrix((Ng, nsl + ndc))])

            Hxx = sp.vstack([H1, H2, H3, H4, lil_matrix((nsl + ndc, NV))]).tocsc()

    else:
        fxx = None
        Gxx = None
        Hxx = None

    return fx, Gx, Hx, fxx, Gxx, Hxx
