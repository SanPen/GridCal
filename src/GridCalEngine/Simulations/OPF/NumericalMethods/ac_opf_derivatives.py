import numpy as np
import pandas as pd
from scipy import sparse as sp
from scipy.sparse import csc_matrix as csc
from scipy.sparse import csr_matrix as csr
from dataclasses import dataclass
from scipy.sparse import lil_matrix

from GridCalEngine.Utils.Sparse.csc import diags
import GridCalEngine.Utils.NumericalMethods.autodiff as ad
from typing import Tuple, Union
from GridCalEngine.basic_structures import Vec, CxVec, IntVec
from GridCalEngine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at, NumericalCircuit


def x2var(x: Vec, nVa: int, nVm: int, nPg: int,
          nQg: int, ntapm: int, ntapt: int) -> Tuple[Vec, Vec, Vec, Vec, Vec, Vec]:
    """
    Convert the x solution vector to its composing variables
    :param x: solution vector
    :param nVa: number of voltage angle vars
    :param nVm: number of voltage module vars
    :param nPg: number of generator active power vars
    :param nQg: number of generator reactive power vars
    :return: Va, Vm, Pg, Qg
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
    b += ntapm

    tapm = x[a: b]
    a = b
    b += ntapt

    tapt = x[a: b]

    return Va, Vm, Pg, Qg, tapm, tapt


def var2x(Va: Vec, Vm: Vec, Pg: Vec, Qg: Vec, tapm: Vec, tapt: Vec) -> Vec:
    """
    Compose the x vector from its componenets
    :param Va: Voltage angles
    :param Vm: Voltage modules
    :param Pg: Generator active powers
    :param Qg: Generator reactive powers
    :return: [Vm, Va, Pg, Qg]
    """
    return np.r_[Va, Vm, Pg, Qg, tapm, tapt]


def compute_analytic_admittances(alltapm, alltapt, k_m, k_tau, k_mtau, Cf, Ct, R, X):
    ys = 1.0 / (R + 1.0j * X + 1e-20)

    # First partial derivative with respect to tap module
    mp = alltapm[k_m]
    tau = alltapt[k_m]
    ylin = ys[k_m]
    N = len(alltapm)

    dYffdm = np.zeros(N, dtype=complex)
    dYftdm = np.zeros(N, dtype=complex)
    dYtfdm = np.zeros(N, dtype=complex)
    dYttdm = np.zeros(N, dtype=complex)

    dYffdm[k_m] = -2 * ylin / (mp * mp * mp)
    dYftdm[k_m] = ylin / (mp * mp * np.exp(-1.0j * tau))
    dYtfdm[k_m] = ylin / (mp * mp * np.exp(1.0j * tau))

    dYfdm = sp.diags(dYffdm) * Cf + sp.diags(dYftdm) * Ct
    dYtdm = sp.diags(dYtfdm) * Cf + sp.diags(dYttdm) * Ct

    dYbusdm = Cf.T * dYfdm + Ct.T * dYtdm  # Cf_m.T and Ct_m.T included earlier

    # First partial derivative with respect to tap angle
    mp = alltapm[k_tau]
    tau = alltapt[k_tau]
    ylin = ys[k_tau]

    dYffdt = np.zeros(N, dtype=complex)
    dYftdt = np.zeros(N, dtype=complex)
    dYtfdt = np.zeros(N, dtype=complex)
    dYttdt = np.zeros(N, dtype=complex)

    dYftdt[k_tau] = -1j * ylin / (mp * np.exp(-1.0j * tau))
    dYtfdt[k_tau] = 1j * ylin / (mp * np.exp(1.0j * tau))

    dYfdt = sp.diags(dYffdt) * Cf + sp.diags(dYftdt) * Ct
    dYtdt = sp.diags(dYtfdt) * Cf + sp.diags(dYttdt) * Ct

    dYbusdt = Cf.T * dYfdt + Ct.T * dYtdt

    return dYbusdm, dYfdm, dYtdm, dYbusdt, dYfdt, dYtdt


def compute_branch_power_derivatives(alltapm, alltapt, V, k_m, k_tau, k_mtau, Cf, Ct, Yf, Yt, R, X):
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


def compute_branch_power_second_derivatives(alltapm, alltapt, vm, va, k_m, k_tau, il,
                                            Cf, Ct, R, X, F, T, lam, mu, Sf, St):
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


def compute_finitediff_admittances(nc, tol=1e-6):
    k_m = nc.k_m
    k_tau = nc.k_tau

    Ybus0 = nc.Ybus
    Yf0 = nc.Yf
    Yt0 = nc.Yt

    nc.branch_data.tap_module[k_m] += tol
    nc.reset_calculations()

    dYfdm = (nc.Yf - Yf0) / tol
    dYtdm = (nc.Yt - Yt0) / tol
    dYbusdm = (nc.Ybus - Ybus0) / tol

    nc.branch_data.tap_module[k_m] -= tol

    nc.branch_data.tap_angle[k_tau] += tol
    nc.reset_calculations()

    dYfdt = (nc.Yf - Yf0) / tol
    dYtdt = (nc.Yt - Yt0) / tol
    dYbusdt = (nc.Ybus - Ybus0) / tol

    nc.branch_data.tap_angle[k_tau] -= tol
    nc.reset_calculations()

    return dYbusdm, dYfdm, dYtdm, dYbusdt, dYfdt, dYtdt


def compute_analytic_admittances_2dev(alltapm, alltapt, k_m, k_tau, Cf, Ct, R, X):
    ys = 1.0 / (R + 1.0j * X + 1e-20)
    N = len(alltapm)

    # Second partial derivative with respect to tap module
    mp = alltapm[k_m]
    tau = alltapt[k_m]
    ylin = ys[k_m]

    dYffdmdm = np.zeros(N, dtype=complex)
    dYftdmdm = np.zeros(N, dtype=complex)
    dYtfdmdm = np.zeros(N, dtype=complex)
    dYttdmdm = np.zeros(N, dtype=complex)

    dYffdmdm[k_m] = 6 * ylin / (mp * mp * mp * mp)
    dYftdmdm[k_m] = -2 * ylin / (mp * mp * mp * np.exp(-1.0j * tau))
    dYtfdmdm[k_m] = -2 * ylin / (mp * mp * mp * np.exp(1.0j * tau))

    dYfdmdm = (sp.diags(dYffdmdm) * Cf + sp.diags(dYftdmdm) * Ct)
    dYtdmdm = (sp.diags(dYtfdmdm) * Cf + sp.diags(dYttdmdm) * Ct)

    dYbusdmdm = (Cf.T * dYfdmdm + Ct.T * dYtdmdm)

    # Second partial derivative with respect to tap angle
    mp = alltapm[k_tau]
    tau = alltapt[k_tau]
    ylin = ys[k_tau]

    dYffdtdt = np.zeros(N, dtype=complex)
    dYftdtdt = np.zeros(N, dtype=complex)
    dYtfdtdt = np.zeros(N, dtype=complex)
    dYttdtdt = np.zeros(N, dtype=complex)

    dYftdtdt[k_tau] = ylin / (mp * np.exp(-1.0j * tau))
    dYtfdtdt[k_tau] = ylin / (mp * np.exp(1.0j * tau))

    dYfdtdt = sp.diags(dYffdtdt) * Cf + sp.diags(dYftdtdt) * Ct
    dYtdtdt = sp.diags(dYtfdtdt) * Cf + sp.diags(dYttdtdt) * Ct

    dYbusdtdt = Cf.T * dYfdtdt + Ct.T * dYtdtdt

    # Second partial derivative with respect to both tap module and angle
    mp = alltapm[k_mtau]
    tau = alltapt[k_mtau]
    ylin = ys[k_mtau]

    dYffdmdt = np.zeros(N, dtype=complex)
    dYftdmdt = np.zeros(N, dtype=complex)
    dYtfdmdt = np.zeros(N, dtype=complex)
    dYttdmdt = np.zeros(N, dtype=complex)

    dYftdmdt[k_mtau] = 1j * ylin / (mp * mp * np.exp(-1.0j * tau))
    dYtfdmdt[k_mtau] = -1j * ylin / (mp * mp * np.exp(1.0j * tau))

    dYfdmdt = sp.diags(dYffdmdt) * Cf + sp.diags(dYftdmdt) * Ct
    dYtdmdt = sp.diags(dYtfdmdt) * Cf + sp.diags(dYttdmdt) * Ct

    dYbusdmdt = Cf.T * dYfdmdt + Ct.T * dYtdmdt

    dYfdtdm = dYfdmdt.copy()
    dYtdtdm = dYtdmdt.copy()
    dYbusdtdm = dYbusdmdt.copy()

    return (dYbusdmdm, dYfdmdm, dYtdmdm, dYbusdmdt, dYfdmdt, dYtdmdt,
            dYbusdtdm, dYfdtdm, dYtdtdm, dYbusdtdt, dYfdtdt, dYtdtdt)


def compute_finitediff_admittances_2dev(nc, tol=1e-6):
    k_m = nc.k_m
    k_tau = nc.k_tau

    dYb0dm, dYf0dm, dYt0dm, dYb0dt, dYf0dt, dYt0dt = compute_finitediff_admittances(nc)

    nc.branch_data.tap_module[k_m] += tol
    nc.reset_calculations()

    dYbdm, dYfdm, dYtdm, dYbdt, dYfdt, dYtdt = compute_finitediff_admittances(nc)

    dYfdmdm = (dYfdm - dYf0dm) / tol
    dYtdmdm = (dYtdm - dYt0dm) / tol
    dYbusdmdm = (dYbdm - dYb0dm) / tol

    dYfdtdm = (dYfdt - dYf0dt) / tol
    dYtdtdm = (dYtdt - dYt0dt) / tol
    dYbusdtdm = (dYbdt - dYb0dt) / tol

    nc.branch_data.tap_module[k_m] -= tol

    nc.branch_data.tap_angle[k_tau] += tol
    nc.reset_calculations()

    dYbdm, dYfdm, dYtdm, dYbdt, dYfdt, dYtdt = compute_finitediff_admittances(nc)

    dYfdmdt = (dYfdm - dYf0dm) / tol
    dYtdmdt = (dYtdm - dYt0dm) / tol
    dYbusdmdt = (dYbdm - dYb0dm) / tol

    dYfdtdt = (dYfdt - dYf0dt) / tol
    dYtdtdt = (dYtdt - dYt0dt) / tol
    dYbusdtdt = (dYbdt - dYb0dt) / tol

    nc.branch_data.tap_angle[k_tau] -= tol
    nc.reset_calculations()

    return (dYbusdmdm, dYfdmdm, dYtdmdm, dYbusdmdt, dYfdmdt, dYtdmdt,
            dYbusdtdm, dYfdtdm, dYtdtdm, dYbusdtdt, dYfdtdt, dYtdtdt)


def eval_f(x: Vec, Cg, k_m: Vec, k_tau: Vec, c0: Vec, c1: Vec, c2: Vec, ig: Vec, Sbase: float) -> Vec:
    """

    :param x:
    :param Cg:
    :param c0:
    :param c1:
    :param c2:
    :param ig:
    :param Sbase:
    :return:
    """
    N, _ = Cg.shape  # Check
    Ng = len(ig)
    ntapm = len(k_m)
    ntapt = len(k_tau)

    _, _, Pg, Qg, _, _ = x2var(x, nVa=N, nVm=N, nPg=Ng, nQg=Ng, ntapm=ntapm, ntapt=ntapt)

    fval = np.sum((c0 + c1 * Pg * Sbase + c2 * np.power(Pg * Sbase, 2))) * 1e-4

    return fval


def eval_g(x, Ybus, Yf, Cg, Sd, ig, nig, pv, k_m, k_tau, Vm_max, Sg_undis, slack) -> Vec:
    """

    :param x:
    :param Ybus:
    :param Yf:
    :param Cg:
    :param Sd:
    :param ig: indices of dispatchable gens
    :param nig: indices of non dispatchable gens
    :param Sg_undis: undispatchable complex power
    :param slack:
    :return:
    """
    M, N = Yf.shape
    Ng = len(ig)
    ntapm = len(k_m)
    ntapt = len(k_tau)

    va, vm, Pg_dis, Qg_dis, _, _ = x2var(x, nVa=N, nVm=N, nPg=Ng, nQg=Ng, ntapm=ntapm, ntapt=ntapt)

    V = vm * np.exp(1j * va)
    S = V * np.conj(Ybus @ V)
    S_dispatch = Cg[:, ig] @ (Pg_dis + 1j * Qg_dis)
    S_undispatch = Cg[:, nig] @ Sg_undis
    dS = S + Sd - S_dispatch - S_undispatch

    gval = np.r_[dS.real, dS.imag, va[slack], vm[pv] - Vm_max[pv]]

    return gval, S


def eval_h(x, Yf, Yt, from_idx, to_idx, pq, no_slack, k_m, k_tau, k_mtau, Va_max, Va_min, Vm_max, Vm_min,
           Pg_max, Pg_min, Qg_max, Qg_min, tapm_max, tapm_min, tapt_max, tapt_min, Cg, rates, il, ig, tanmax) -> Vec:
    """

    :param x:
    :param Yf:
    :param Yt:
    :param from_idx:
    :param to_idx:
    :param no_slack:
    :param Va_max:
    :param Va_min:
    :param Vm_max:
    :param Vm_min:
    :param Pg_max:
    :param Pg_min:
    :param Qg_max:
    :param Qg_min:
    :param Cg:
    :param rates:
    :param il: relevant lines to check rating
    :return:
    """
    M, N = Yf.shape
    Ng = len(ig)
    ntapm = len(k_m)
    ntapt = len(k_tau)

    va, vm, Pg, Qg, tapm, tapt = x2var(x, nVa=N, nVm=N, nPg=Ng, nQg=Ng, ntapm=ntapm, ntapt=ntapt)

    V = vm * np.exp(1j * va)
    Sf = V[from_idx[il]] * np.conj(Yf[il, :] @ V)
    St = V[to_idx[il]] * np.conj(Yt[il, :] @ V)

    Sf2 = np.conj(Sf) * Sf
    St2 = np.conj(St) * St

    # hval = np.r_[Sf2.real - (rates[il] ** 2),  # rates "lower limit"
    #              St2.real - (rates[il] ** 2),  # rates "upper limit"
    #              vm[pq] - Vm_max[pq],  # voltage module upper limit
    #              Vm_min[pq] - vm[pq],  # voltage module lower limit
    #              Pg - Pg_max[ig],  # generator P upper limits
    #              Pg_min[ig] - Pg,  # generator P lower limits
    #              Qg - Qg_max[ig],  # generator Q upper limits
    #              Qg_min[ig] - Qg  # generation Q lower limits
    # ]

    hval = np.r_[Sf2.real - (rates[il] ** 2),  # rates "lower limit"
                 St2.real - (rates[il] ** 2),  # rates "upper limit"
                 vm[pq] - Vm_max[pq],  # voltage module upper limit
                 Pg - Pg_max[ig],  # generator P upper limits
                 Qg - Qg_max[ig],  # generator Q upper limits
                 Vm_min[pq] - vm[pq],  # voltage module lower limit
                 Pg_min[ig] - Pg,  # generator P lower limits
                 Qg_min[ig] - Qg,  # generation Q lower limits
                 tapm - tapm_max,
                 tapm_min - tapm,
                 tapt - tapt_max,
                 tapt_min - tapt,
                 Qg ** 2 - tanmax ** 2 * Pg ** 2
    ]

    # Sftot = V[from_idx[il]] * np.conj(Yf[il, :] @ V)
    # Sttot = V[to_idx[il]] * np.conj(Yt[il, :] @ V)

    # return hval, Sftot, Sttot
    return hval, Sf, St


def jacobians_and_hessians(x, c1, c2, Cg, Cf, Ct, Yf, Yt, Ybus, Sbase, il, ig, nig, slack, no_slack, pq, pv, tanmax,
                           alltapm, alltapt, k_m, k_tau, k_mtau, mu, lmbda, from_idx, to_idx, R, X, F, T,
                           compute_jac: bool, compute_hess: bool):
    """

    :param x:
    :param c1:
    :param c2:
    :param Cg:
    :param Cf:
    :param Ct:
    :param Yf:
    :param Yt:
    :param Ybus:
    :param Sbase:
    :param il:
    :param ig:
    :param nig:
    :param slack:
    :param no_slack:
    :param mu:
    :param lmbda:
    :return:
    """
    Mm, N = Yf.shape
    M = len(il)
    Ng = len(ig)
    NV = len(x)
    ntapm = len(k_m)
    ntapt = len(k_tau)

    va, vm, Pg, Qg, tapm, tapt = x2var(x, nVa=N, nVm=N, nPg=Ng, nQg=Ng, ntapm=ntapm, ntapt=ntapt)
    V = vm * np.exp(1j * va)
    Vmat = diags(V)
    vm_inv = diags(1 / vm)
    E = Vmat @ vm_inv
    Ibus = Ybus @ V
    IbusCJmat = diags(np.conj(Ibus))
    alltapm[k_m] = tapm
    alltapt[k_tau] = tapt

    if compute_jac:

        ######### OBJECTIVE FUNCTION GRAD

        fx = np.zeros(NV)

        fx[2 * N: 2 * N + Ng] = (2 * c2 * Pg * (Sbase ** 2) + c1 * Sbase) * 1e-4

        ######### EQUALITY CONSTRAINTS GRAD

        Vva = 1j * Vmat

        GSvm = Vmat @ (IbusCJmat + np.conj(Ybus) @ np.conj(Vmat)) @ vm_inv
        GSva = Vva @ (IbusCJmat - np.conj(Ybus) @ np.conj(Vmat))
        GSpg = -Cg[:, ig]
        GSqg = -1j * Cg[:, ig]

        GTH = lil_matrix((len(slack), len(x)), dtype=float)
        for i, ss in enumerate(slack):
            GTH[i, ss] = 1.

        Gvm = lil_matrix((len(pv), len(x)), dtype=float)
        for i, ss in enumerate(pv):
            Gvm[i, N + ss] = 1.

        GS = sp.hstack([GSva, GSvm, GSpg, GSqg])

        if ntapm + ntapt != 0:  # Check if there are tap variables that can affect the admittances

            (dSbusdm, dSfdm, dStdm,
             dSbusdt, dSfdt, dStdt) = compute_branch_power_derivatives(alltapm, alltapt, V, k_m, k_tau, k_mtau,
                                                                       Cf, Ct, Yf, Yt, R, X)

            if ntapm != 0:
                Gtapm = dSbusdm.copy()
                GS = sp.hstack([GS, Gtapm])
            if ntapt != 0:
                Gtapt = dSbusdt.copy()
                GS = sp.hstack([GS, Gtapt])

        Gx = sp.vstack([GS.real, GS.imag, GTH, Gvm]).T.tocsc()

        ######### INEQUALITY CONSTRAINTS GRAD

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

        Hpu = np.zeros(Ng)
        Hpl = np.zeros(Ng)
        Hqu = np.zeros(Ng)
        Hql = np.zeros(Ng)

        Hvmu_ = csc(([1] * (N - len(pv)), (list(range(N - len(pv))), pq)))
        Hvml_ = csc(([-1] * (N - len(pv)), (list(range(N - len(pv))), pq)))

        Hpu[0: Ng] = 1
        Hpl[0: Ng] = -1
        Hqu[0: Ng] = 1
        Hql[0: Ng] = -1

        Hvu = sp.hstack([lil_matrix((len(pq), N)), Hvmu_, lil_matrix((len(pq), 2 * Ng + ntapm + ntapt))])
        Hvl = sp.hstack([lil_matrix((len(pq), N)), Hvml_, lil_matrix((len(pq), 2 * Ng + ntapm + ntapt))])

        Hpu = sp.hstack([lil_matrix((Ng, 2 * N)), diags(Hpu), lil_matrix((Ng, Ng + ntapm + ntapt))])
        Hpl = sp.hstack([lil_matrix((Ng, 2 * N)), diags(Hpl), lil_matrix((Ng, Ng + ntapm + ntapt))])
        Hqu = sp.hstack([lil_matrix((Ng, 2 * N + Ng)), diags(Hqu), lil_matrix((Ng, ntapm + ntapt))])
        Hql = sp.hstack([lil_matrix((Ng, 2 * N + Ng)), diags(Hql), lil_matrix((Ng, ntapm + ntapt))])

        # tanmax curves (simplified capability curves of generators)
        Hqmaxp = -2 * (tanmax ** 2) * Pg
        Hqmaxq = 2 * Qg

        Hqmax = sp.hstack([lil_matrix((Ng, 2 * N)), diags(Hqmaxp), diags(Hqmaxq), lil_matrix((Ng, ntapm + ntapt))])

        if ntapm + ntapt != 0:

            Sftapm = dSfdm[il, :].copy()
            Sftapt = dSfdt[il, :].copy()
            Sttapm = dStdm[il, :].copy()
            Sttapt = dStdt[il, :].copy()

            SfX = sp.hstack([Sfva, Sfvm, lil_matrix((M, 2 * Ng)), Sftapm, Sftapt])
            StX = sp.hstack([Stva, Stvm, lil_matrix((M, 2 * Ng)), Sttapm, Sttapt])

            HSf = 2 * (Sfmat.real @ SfX.real + Sfmat.imag @ SfX.imag)
            HSt = 2 * (Stmat.real @ StX.real + Stmat.imag @ StX.imag)

            Hx = sp.vstack([HSf, HSt, Hvu, Hpu, Hqu, Hvl, Hpl, Hql])

            if ntapm != 0:
                Htapmu_ = csc(([1] * ntapm, (list(range(ntapm)), list(range(ntapm)))))
                Htapml_ = csc(([-1] * ntapm, (list(range(ntapm)), list(range(ntapm)))))
                Htapmu = sp.hstack([lil_matrix((ntapm, 2 * N + 2 * Ng)), Htapmu_, lil_matrix((ntapm, ntapt))])
                Htapml = sp.hstack([lil_matrix((ntapm, 2 * N + 2 * Ng)), Htapml_, lil_matrix((ntapm, ntapt))])
                Hx = sp.vstack([Hx, Htapmu, Htapml])

            if ntapt != 0:
                Htaptu_ = csc(([1] * ntapt, (list(range(ntapt)), list(range(ntapt)))))
                Htaptl_ = csc(([-1] * ntapt, (list(range(ntapt)), list(range(ntapt)))))
                Htaptu = sp.hstack([lil_matrix((ntapt, 2 * N + 2 * Ng + ntapm)), Htaptu_])
                Htaptl = sp.hstack([lil_matrix((ntapt, 2 * N + 2 * Ng + ntapm)), Htaptl_])
                Hx = sp.vstack([Hx, Htaptu, Htaptl])

            Hx = sp.vstack([Hx, Hqmax]).T.tocsc()

        else:

            SfX = sp.hstack([Sfva, Sfvm, lil_matrix((M, 2 * Ng))])
            StX = sp.hstack([Stva, Stvm, lil_matrix((M, 2 * Ng))])

            HSf = 2 * (Sfmat.real @ SfX.real + Sfmat.imag @ SfX.imag)
            HSt = 2 * (Stmat.real @ StX.real + Stmat.imag @ StX.imag)

            Hx = sp.vstack([HSf, HSt, Hvu, Hpu, Hqu, Hvl, Hpl, Hql, Hqmax]).T.tocsc()

    else:
        fx = None
        Gx = None
        Hx = None

    ########## HESSIANS

    if compute_hess:

        assert compute_jac  # we must have the jacobian values to get into here

        ######## OBJECTIVE FUNCITON HESS

        fxx = diags((np.r_[np.zeros(2 * N), 2 * c2 * (Sbase ** 2), np.zeros(Ng + ntapm + ntapt)]) * 1e-4).tocsc()

        ######## EQUALITY CONSTRAINTS HESS

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

            G1 = sp.hstack([Gaa, Gav, lil_matrix((N, 2 * Ng)), GSdmdva, GSdtdva])
            G2 = sp.hstack([Gva, Gvv, lil_matrix((N, 2 * Ng)), GSdmdvm, GSdtdvm])
            G3 = sp.hstack([GSdmdva.T, GSdmdvm.T, lil_matrix((ntapm, 2 * Ng)), GSdmdm, GSdmdt.T])
            G4 = sp.hstack([GSdtdva.T, GSdtdvm.T, lil_matrix((ntapt, 2 * Ng)), GSdmdt, GSdtdt])

            Gxx = sp.vstack([G1, G2, lil_matrix((2 * Ng, NV)), G3, G4]).tocsc()
            print('')

        else:
            G1 = sp.hstack([Gaa, Gav, lil_matrix((N, 2 * Ng))])
            G2 = sp.hstack([Gva, Gvv, lil_matrix((N, 2 * Ng))])
            Gxx = sp.vstack([G1, G2, lil_matrix((2 * Ng, NV))]).tocsc()

        ######### INEQUALITY CONSTRAINTS HESS
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

        Hqpgpg = diags(-2 * (tanmax ** 2) * mu[-Ng:])
        Hqqgqg = diags(np.array([2] * Ng) * mu[-Ng:])

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

            H1 = sp.hstack([Hfvava + Htvava, Hfvavm + Htvavm, lil_matrix((N, 2 * Ng)),
                            Hftapmva.T + Httapmva.T, Hftaptva.T + Httaptva.T])
            H2 = sp.hstack([Hfvmva + Htvmva, Hfvmvm + Htvmvm, lil_matrix((N, 2 * Ng)),
                            Hftapmvm.T + Httapmvm.T, Hftaptvm.T + Httaptvm.T])
            H3 = sp.hstack([lil_matrix((Ng, 2 * N)), Hqpgpg, lil_matrix((Ng, Ng + ntapm + ntapt))])
            H4 = sp.hstack([lil_matrix((Ng, 2 * N + Ng)), Hqqgqg, lil_matrix((Ng, ntapm + ntapt))])
            H5 = sp.hstack([Hftapmva + Httapmva, Hftapmvm + Httapmvm, lil_matrix((ntapm, 2 * Ng)),
                            Hftapmtapm + Httapmtapm, Hftapmtapt + Httapmtapt])
            H6 = sp.hstack([Hftaptva + Httaptva, Hftaptvm + Httaptvm, lil_matrix((ntapt, 2 * Ng)),
                            Hftapmtapt.T + Httapmtapt.T, Hftapttapt + Httapttapt])

            Hxx = sp.vstack([H1, H2, H3, H4, H5, H6]).tocsc()
        else:
            H1 = sp.hstack([Hfvava + Htvava, Hfvavm + Htvavm, lil_matrix((N, 2 * Ng))])
            H2 = sp.hstack([Hfvmva + Htvmva, Hfvmvm + Htvmvm, lil_matrix((N, 2 * Ng))])
            H3 = sp.hstack([lil_matrix((Ng, 2 * N)), Hqpgpg, lil_matrix((Ng, Ng))])
            H4 = sp.hstack([lil_matrix((Ng, 2 * N + Ng)), Hqqgqg])

            # Hxx = sp.vstack([H1, H2, lil_matrix((2 * Ng, NV))]).tocsc()
            Hxx = sp.vstack([H1, H2, H3, H4]).tocsc()

    else:
        fxx = None
        Gxx = None
        Hxx = None

    return fx, Gx, Hx, fxx, Gxx, Hxx
