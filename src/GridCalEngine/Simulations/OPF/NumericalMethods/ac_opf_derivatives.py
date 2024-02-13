
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


def compute_analytic_admittances_2dev(alltapm, alltapt, k_m, k_tau, k_mtau, Cf, Ct, R, X):

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
           Pg_max, Pg_min, Qg_max, Qg_min, tapm_max, tapm_min, tapt_max, tapt_min, Cg, rates, il, ig) -> Vec:
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
                 tapt_min - tapt
    ]

    # Sftot = V[from_idx[il]] * np.conj(Yf[il, :] @ V)
    # Sttot = V[to_idx[il]] * np.conj(Yt[il, :] @ V)

    # return hval, Sftot, Sttot
    return hval, Sf, St


def jacobians_and_hessians(x, c1, c2, Cg, Cf, Ct, Yf, Yt, Ybus, Sbase, il, ig, nig, slack, no_slack, pq, pv, alltapm,
                           alltapt, k_m, k_tau, k_mtau, mu, lmbda, from_idx, to_idx, compute_jac: bool,
                           compute_hess: bool):
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

        if ntapm + ntapt != 0:  # Check if there are tap variables that can affect the admittances

            (dYbusdm, dYfdm, dYtdm,
             dYbusdt, dYfdt, dYtdt) = compute_analytic_admittances(alltapm, alltapt, k_m, k_tau, k_mtau, Cf, Ct, R, X)

            Gtapm = Vmat * np.conj(dYbusdm * V)
            Gtapt = Vmat * np.conj(dYbusdt * V)

            GS = sp.hstack([GSva, GSvm, GSpg, GSqg, Gtapm, Gtapt])
            Gx = sp.vstack([GS.real, GS.imag, GTH, Gvm]).T.tocsc()

        else:
            GS = sp.hstack([GSva, GSvm, GSpg, GSqg])
            Gx = sp.vstack([GS.real, GS.imag, GTH, Gvm]).T.tocsc()

        ######### INEQUALITY CONSTRAINTS GRAD

        Vfmat = diags(Cf[il, :] @ V)
        Vtmat = diags(Ct[il, :] @ V)

        IfCJmat = np.conj(diags(Yf[il, :] @ V))
        ItCJmat = np.conj(diags(Yt[il, :] @ V))
        Sfmat = diags(Vfmat @ np.conj(Yf[il, :] @ V))
        Stmat = diags(Vtmat @ np.conj(Yt[il, :] @ V))

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

        Hvu = sp.hstack([lil_matrix((len(pq), N)), Hvmu_, lil_matrix((len(pq), 2 * Ng))])
        Hvl = sp.hstack([lil_matrix((len(pq), N)), Hvml_, lil_matrix((len(pq), 2 * Ng))])

        Hpu = sp.hstack([lil_matrix((Ng, 2 * N)), diags(Hpu), lil_matrix((Ng, Ng))])
        Hpl = sp.hstack([lil_matrix((Ng, 2 * N)), diags(Hpl), lil_matrix((Ng, Ng))])
        Hqu = sp.hstack([lil_matrix((Ng, 2 * N + Ng)), diags(Hqu)])
        Hql = sp.hstack([lil_matrix((Ng, 2 * N + Ng)), diags(Hql)])

        if ntapm + ntapt != 0:

            Sftapm = Vfmat @ np.conj(dYbusdm @ V)
            Sftapt = Vtmat @ np.conj(dYbusdm @ V)
            Sttapm = Vfmat @ np.conj(dYbusdt @ V)
            Sttapt = Vtmat @ np.conj(dYbusdt @ V)

            SfX = sp.hstack([Sfva, Sfvm, lil_matrix((M, 2 * Ng)), Sftapm, Sftapt])
            StX = sp.hstack([Stva, Stvm, lil_matrix((M, 2 * Ng)), Sttapm, Sttapt])

            HSf = 2 * (Sfmat.real @ SfX.real + Sfmat.imag @ SfX.imag)
            HSt = 2 * (Stmat.real @ StX.real + Stmat.imag @ StX.imag)

            if ntapm != 0:
                Htapmu_ = csc(([1] * ntapm, (list(range(ntapm)), k_m)))
                Htapml_ = csc(([-1] * ntapm, (list(range(ntapm)), k_m)))
                Htapmu = sp.hstack([lil_matrix((ntapm, 2 * N + 2 * Ng)), Htapmu_, lil_matrix((ntapm, ntapt))])
                Htapml = sp.hstack([lil_matrix((ntapm, 2 * N + 2 * Ng)), Htapml_, lil_matrix((ntapm, ntapt))])

            if ntapt != 0:
                Htaptu_ = csc(([1] * ntapt, (list(range(ntapt)), k_tau)))
                Htaptl_ = csc(([-1] * ntapt, (list(range(ntapt)), k_tau)))
                Htaptu = sp.hstack([lil_matrix((ntapt, 2 * N + 2 * Ng + ntapm)), Htaptu_])
                Htaptl = sp.hstack([lil_matrix((ntapt, 2 * N + 2 * Ng + ntapm)), Htaptl_])

        else:

            SfX = sp.hstack([Sfva, Sfvm, lil_matrix((M, 2 * Ng))])
            StX = sp.hstack([Stva, Stvm, lil_matrix((M, 2 * Ng))])

            HSf = 2 * (Sfmat.real @ SfX.real + Sfmat.imag @ SfX.imag)
            HSt = 2 * (Stmat.real @ StX.real + Stmat.imag @ StX.imag)

        Hx = sp.vstack([HSf, HSt, Hvu, Hpu, Hqu, Hvl, Hpl, Hql]).T.tocsc()

    else:
        fx = None
        Gx = None
        Hx = None

    ########## HESSIANS

    if compute_hess:

        assert compute_jac  # we must have the jacobian values to get into here

        ######## OBJECTIVE FUNCITON HESS

        fxx = diags((np.r_[np.zeros(2 * N), 2 * c2 * (Sbase ** 2), np.zeros(Ng)]) * 1e-4).tocsc()

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

            (dYbusdmdm, dYfdmdm, dYtdmdm,
             dYbusdmdt, dYfdmdt, dYtdmdt,
             dYbusdtdm, dYfdtdm, dYtdtdm,
             dYbusdtdt, dYfdtdt, dYtdtdt) = compute_analytic_admittances_2dev(alltapm, alltapt, k_m, k_tau,
                                                                              k_mtau, Cf, Ct, R, X)

            Gtapmvm_p = (E @ np.conj(dYbusdm @ V) + Vmat @ np.conj(dYbusdm @ E)).T @ lam_p
            Gtapmvm_q = (E @ np.conj(dYbusdm @ V) + Vmat @ np.conj(dYbusdm @ E)).T @ lam_q
            Gtapmvm = Gtapmvm_p.real + Gtapmvm_q.imag
            Gvmtapm = Gtapmvm.T

            Gtapmva_p = (Vva @ np.conj(dYbusdm @ V) + Vmat @ np.conj(dYbusdm @ Vva)).T @ lam_p
            Gtapmva_q = (Vva @ np.conj(dYbusdm @ V) + Vmat @ np.conj(dYbusdm @ Vva)).T @ lam_q
            Gtapmva = Gtapmva_p.real + Gtapmva_q.imag
            Gvatapm = Gtapmva.T

            Gtaptvm_p = (E @ np.conj(dYbusdt @ V) + Vmat @ np.conj(dYbusdt @ E)).T @ lam_p
            Gtaptvm_q = (E @ np.conj(dYbusdt @ V) + Vmat @ np.conj(dYbusdt @ E)).T @ lam_q
            Gtaptvm = Gtaptvm_p.real + Gtaptvm_q.imag
            Gvmtapt = Gtaptvm.T

            Gtaptva_p = (Vva @ np.conj(dYbusdt @ V) + Vmat @ np.conj(dYbusdt @ Vva)).T @ lam_p
            Gtaptva_q = (Vva @ np.conj(dYbusdt @ V) + Vmat @ np.conj(dYbusdt @ Vva)).T @ lam_q
            Gtaptva = Gtaptva_p.real + Gtaptva_q.imag
            Gvatapt = Gtaptva.T

            Gtapmtapm_p = (Vmat @ np.conj(dYbusdmdm @ V)).T @ lam_p
            Gtapmtapm_q = (Vmat @ np.conj(dYbusdmdm @ V)).T @ lam_q
            Gtapmtapm = Gtapmtapm_p.real + Gtapmtapm_q.imag

            Gtapttapt_p = (Vmat @ np.conj(dYbusdtdt @ V)).T @ lam_p
            Gtapttapt_q = (Vmat @ np.conj(dYbusdtdt @ V)).T @ lam_q
            Gtapttapt = Gtapttapt_p.real + Gtapttapt_q.imag

            Gtapmtapt_p = (Vmat @ np.conj(dYbusdmdt @ V)).T @ lam_p
            Gtapmtapt_q = (Vmat @ np.conj(dYbusdmdt @ V)).T @ lam_q
            Gtapmtapt = Gtapmtapt_p.real + Gtapmtapt_q.imag
            Gtapttapm = Gtapmtapt.T

            G1 = sp.hstack([Gaa, Gav, lil_matrix((N, 2 * Ng)), Gvatapm, Gvatapt])
            G2 = sp.hstack([Gva, Gvv, lil_matrix((N, 2 * Ng)), Gvmtapm, Gvmtapt])
            G3 = sp.hstack([Gtapmva, Gtapmvm, lil_matrix((N, 2 * Ng)), Gtapmtapm, Gtapmtapt])
            G4 = sp.hstack([Gtaptva, Gtaptva, lil_matrix((N, 2 * Ng)), Gtapttapm, Gtapttapt])

            Gxx = sp.vstack([G1, G2, lil_matrix((2 * Ng, NV)), G3, G4]).tocsc()

        else:
            G1 = sp.hstack([Gaa, Gav, lil_matrix((N, 2 * Ng))])
            G2 = sp.hstack([Gva, Gvv, lil_matrix((N, 2 * Ng))])
            Gxx = sp.vstack([G1, G2, lil_matrix((2 * Ng, NV))]).tocsc()


        ######### INEQUALITY CONSTRAINTS HESS
        muf = mu[0: N]
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

            Sftapmva = (Vfmat @ np.conj(dYbusdm @ Vva) + Cf @ diags(Cf @ Vva) @ np.conj(dYbusdm @ V)).T @ muf
            Sttapmva = (Vtmat @ np.conj(dYbusdm @ Vva) + Ct @ diags(Ct @ Vva) @ np.conj(dYbusdm @ V)).T @ mut

            Sftapmvm = (Vfmat @ np.conj(dYbusdm @ E) + Cf @ diags(Cf @ E) @ np.conj(dYbusdm @ V)).T @ muf
            Sttapmvm = (Vtmat @ np.conj(dYbusdm @ E) + Ct @ diags(Ct @ E) @ np.conj(dYbusdm @ V)).T @ mut

            Sftaptva = (Vfmat @ np.conj(dYbusdt @ Vva) + Cf @ diags(Cf @ Vva) @ np.conj(dYbusdt @ V)).T @ muf
            Sttaptva = (Vtmat @ np.conj(dYbusdt @ Vva) + Ct @ diags(Ct @ Vva) @ np.conj(dYbusdt @ V)).T @ mut

            Sftaptvm = (Vfmat @ np.conj(dYbusdt @ E) + Cf @ diags(Cf @ E) @ np.conj(dYbusdt @ V)).T @ muf
            Sttaptvm = (Vtmat @ np.conj(dYbusdt @ E) + Ct @ diags(Ct @ E) @ np.conj(dYbusdt @ V)).T @ mut

            Sftapmtapm = (Vfmat @ np.conj(dYbusdmdm @ V)).T @ muf
            Sttapmtapm = (Vtmat @ np.conj(dYbusdmdm @ V)).T @ mut

            Sftapttapt = (Vfmat @ np.conj(dYbusdmdm @ V)).T @ muf
            Sttapttapt = (Vtmat @ np.conj(dYbusdtdt @ V)).T @ mut

            Sftapmtapt = (Vfmat @ np.conj(dYbusdmdt @ V)).T @ muf
            Sttapmtapt = (Vtmat @ np.conj(dYbusdmdt @ V)).T @ mut

            Hftapmva = 2 * (Sftapmva + Sftapm.T @ muf_mat @ np.conj(Sfva)).real
            Hftapmvm = 2 * (Sftapmvm + Sftapm.T @ muf_mat @ np.conj(Sfvm)).real
            Hftaptva = 2 * (Sftaptva + Sftapt.T @ muf_mat @ np.conj(Sfva)).real
            Hftaptvm = 2 * (Sftaptvm + Sftapt.T @ muf_mat @ np.conj(Sfvm)).real
            Hftapmtapm = 2 * (Sftapmtapm + Sftapm.T @ muf_mat @ np.conj(Sftapm)).real
            Hftapttapt = 2 * (Sftapttapt + Sftapt.T @ muf_mat @ np.conj(Sftapt)).real
            Hftapmtapt = 2 * (Sftapmtapt + Sftapm.T @ muf_mat @ np.conj(Sftapt)).real

            Httapmva = 2 * (Sttapmva + Sttapm.T @ mut_mat @ np.conj(Stva)).real
            Httapmvm = 2 * (Sttapmvm + Sttapm.T @ mut_mat @ np.conj(Stvm)).real
            Httaptva = 2 * (Sttaptva + Sttapt.T @ mut_mat @ np.conj(Stva)).real
            Httaptvm = 2 * (Sttaptvm + Sttapt.T @ mut_mat @ np.conj(Stvm)).real
            Httapmtapm = 2 * (Sttapmtapm + Sttapm.T @ mut_mat @ np.conj(Sttapm)).real
            Httapttapt = 2 * (Sttapttapt + Sttapt.T @ mut_mat @ np.conj(Sttapt)).real
            Httapmtapt = 2 * (Sttapmtapt + Sttapm.T @ mut_mat @ np.conj(Sttapt)).real

        H1 = sp.hstack([Hfvava + Htvava, Hfvavm + Htvavm, lil_matrix((N, 2 * Ng))])
        H2 = sp.hstack([Hfvmva + Htvmva, Hfvmvm + Htvmvm, lil_matrix((N, 2 * Ng))])
        Hxx = sp.vstack([H1, H2, lil_matrix((2 * Ng, NV))]).tocsc()

    else:
        fxx = None
        Gxx = None
        Hxx = None

    return fx, Gx, Hx, fxx, Gxx, Hxx
