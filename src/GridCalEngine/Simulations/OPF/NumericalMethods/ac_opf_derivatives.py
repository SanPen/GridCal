
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse import csc_matrix as csc
from scipy.sparse import csr_matrix as csr
from dataclasses import dataclass
from scipy.sparse import lil_matrix

from GridCalEngine.Utils.Sparse.csc import diags
import GridCalEngine.Utils.NumericalMethods.autodiff as ad
from typing import Tuple, Union
from GridCalEngine.basic_structures import Vec, CxVec, IntVec


def x2var(x: Vec, nVa: int, nVm: int, nPg: int, nQg: int) -> Tuple[Vec, Vec, Vec, Vec]:
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

    return Va, Vm, Pg, Qg


def var2x(Va: Vec, Vm: Vec, Pg: Vec, Qg: Vec) -> Vec:
    """
    Compose the x vector from its componenets
    :param Va: Voltage angles
    :param Vm: Voltage modules
    :param Pg: Generator active powers
    :param Qg: Generator reactive powers
    :return: [Vm, Va, Pg, Qg]
    """
    return np.r_[Va, Vm, Pg, Qg]


def compute_analytic_admittances(nc):
    k_m = nc.k_m
    k_tau = nc.k_tau
    k_mtau = nc.k_mtau

    tapm = nc.branch_data.tap_module
    tapt = nc.branch_data.tap_angle

    Cf = nc.Cf
    Ct = nc.Ct
    ys = 1.0 / (nc.branch_data.R + 1.0j * nc.branch_data.X + 1e-20)

    # First partial derivative with respect to tap module
    mp = tapm[k_m]
    tau = tapt[k_m]
    ylin = ys[k_m]

    dYffdm = np.zeros(len(tapm), dtype=complex)
    dYftdm = np.zeros(len(tapm), dtype=complex)
    dYtfdm = np.zeros(len(tapm), dtype=complex)
    dYttdm = np.zeros(len(tapm), dtype=complex)

    dYffdm[k_m] = -2 * ylin / (mp * mp * mp)
    dYftdm[k_m] = ylin / (mp * mp * np.exp(-1.0j * tau))
    dYtfdm[k_m] = ylin / (mp * mp * np.exp(1.0j * tau))

    dYfdm = sp.diags(dYffdm) * Cf + sp.diags(dYftdm) * Ct
    dYtdm = sp.diags(dYtfdm) * Cf + sp.diags(dYttdm) * Ct

    dYbusdm = Cf.T * dYfdm + Ct.T * dYtdm  # Cf_m.T and Ct_m.T included earlier

    # First partial derivative with respect to tap angle
    mp = tapm[k_tau]
    tau = tapt[k_tau]
    ylin = ys[k_tau]

    dYffdt = np.zeros(len(tapm), dtype=complex)
    dYftdt = np.zeros(len(tapm), dtype=complex)
    dYtfdt = np.zeros(len(tapm), dtype=complex)
    dYttdt = np.zeros(len(tapm), dtype=complex)

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


def compute_analytic_admittances_2dev(nc):
    k_m = np.r_[nc.k_m, nc.k_mtau]
    k_tau = np.r_[nc.k_tau, nc.k_mtau]
    k_mtau = nc.k_mtau

    tapm = nc.branch_data.tap_module
    tapt = nc.branch_data.tap_angle

    Cf = nc.Cf
    Ct = nc.Ct
    ys = 1.0 / (nc.branch_data.R + 1.0j * nc.branch_data.X + 1e-20)

    # Second partial derivative with respect to tap module
    mp = tapm[k_m]
    tau = tapt[k_m]
    ylin = ys[k_m]

    dYffdmdm = np.zeros(len(tapm), dtype=complex)
    dYftdmdm = np.zeros(len(tapm), dtype=complex)
    dYtfdmdm = np.zeros(len(tapm), dtype=complex)
    dYttdmdm = np.zeros(len(tapm), dtype=complex)

    dYffdmdm[k_m] = 6 * ylin / (mp * mp * mp * mp)
    dYftdmdm[k_m] = -2 * ylin / (mp * mp * mp * np.exp(-1.0j * tau))
    dYtfdmdm[k_m] = -2 * ylin / (mp * mp * mp * np.exp(1.0j * tau))

    dYfdmdm = (sp.diags(dYffdmdm) * Cf + sp.diags(dYftdmdm) * Ct)
    dYtdmdm = (sp.diags(dYtfdmdm) * Cf + sp.diags(dYttdmdm) * Ct)

    dYbusdmdm = (Cf.T * dYfdmdm + Ct.T * dYtdmdm)

    # Second partial derivative with respect to tap angle
    mp = tapm[k_tau]
    tau = tapt[k_tau]
    ylin = ys[k_tau]

    dYffdtdt = np.zeros(len(tapm), dtype=complex)
    dYftdtdt = np.zeros(len(tapm), dtype=complex)
    dYtfdtdt = np.zeros(len(tapm), dtype=complex)
    dYttdtdt = np.zeros(len(tapm), dtype=complex)

    dYftdtdt[k_tau] = ylin / (mp * np.exp(-1.0j * tau))
    dYtfdtdt[k_tau] = ylin / (mp * np.exp(1.0j * tau))

    dYfdtdt = sp.diags(dYffdtdt) * Cf + sp.diags(dYftdtdt) * Ct
    dYtdtdt = sp.diags(dYtfdtdt) * Cf + sp.diags(dYttdtdt) * Ct

    dYbusdtdt = Cf.T * dYfdtdt + Ct.T * dYtdtdt

    # Second partial derivative with respect to both tap module and angle
    mp = tapm[k_mtau]
    tau = tapt[k_mtau]
    ylin = ys[k_mtau]

    dYffdmdt = np.zeros(len(tapm), dtype=complex)
    dYftdmdt = np.zeros(len(tapm), dtype=complex)
    dYtfdmdt = np.zeros(len(tapm), dtype=complex)
    dYttdmdt = np.zeros(len(tapm), dtype=complex)

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


def eval_f(x: Vec, Cg, c0: Vec, c1: Vec, c2: Vec, ig: Vec, Sbase: float) -> Vec:
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

    _, _, Pg, Qg = x2var(x, nVa=N, nVm=N, nPg=Ng, nQg=Ng)

    fval = np.sum((c0 + c1 * Pg * Sbase + c2 * np.power(Pg * Sbase, 2))) * 1e-4

    return fval


def eval_g(x, Ybus, Yf, Cg, Sd, ig, nig, pv, Vm_max, Sg_undis, slack) -> Vec:
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

    va, vm, Pg_dis, Qg_dis = x2var(x, nVa=N, nVm=N, nPg=Ng, nQg=Ng)

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

    va, vm, Pg, Qg = x2var(x, nVa=N, nVm=N, nPg=Ng, nQg=Ng)

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
                 Qg_min[ig] - Qg  # generation Q lower limits
    ]

    # Sftot = V[from_idx[il]] * np.conj(Yf[il, :] @ V)
    # Sttot = V[to_idx[il]] * np.conj(Yt[il, :] @ V)

    # return hval, Sftot, Sttot
    return hval, Sf, St


def jacobians_and_hessians(x, c1, c2, Cg, Cf, Ct, Yf, Yt, Ybus, Sbase, il, ig, nig, slack, no_slack, pq, pv, k_m,
                           k_tau, k_mtau, mu, lmbda, from_idx, to_idx, compute_jac: bool, compute_hess: bool):
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

    va, vm, Pg, Qg = x2var(x, nVa=N, nVm=N, nPg=Ng, nQg=Ng)
    V = vm * np.exp(1j * va)
    Vmat = diags(V)
    vm_inv = diags(1 / vm)
    E = Vmat @ vm_inv
    Ibus = Ybus @ V
    IbusCJmat = diags(np.conj(Ibus))

    if compute_jac:
        fx = np.zeros(NV)

        fx[2 * N: 2 * N + Ng] = (2 * c2 * Pg * (Sbase ** 2) + c1 * Sbase) * 1e-4

        #########

        GSvm = Vmat @ (IbusCJmat + np.conj(Ybus) @ np.conj(Vmat)) @ vm_inv
        GSva = 1j * Vmat @ (IbusCJmat - np.conj(Ybus) @ np.conj(Vmat))
        GSpg = -Cg[:, ig]
        GSqg = -1j * Cg[:, ig]

        GTH = lil_matrix((len(slack), len(x)), dtype=float)
        for i, ss in enumerate(slack):
            GTH[i, ss] = 1.

        Gvm = lil_matrix((len(pv), len(x)), dtype=float)
        for i, ss in enumerate(pv):
            Gvm[i, N + ss] = 1.

        GS = sparse.hstack([GSva, GSvm, GSpg, GSqg])
        Gx = sparse.vstack([GS.real, GS.imag, GTH, Gvm]).T.tocsc()

        #############
        # Old flow derivatives
        IfCJmat = np.conj(diags(Yf[il, :] @ V))
        ItCJmat = np.conj(diags(Yt[il, :] @ V))
        Sfmat = diags(diags(Cf[il, :] @ V) @ np.conj(Yf[il, :] @ V))
        Stmat = diags(diags(Ct[il, :] @ V) @ np.conj(Yt[il, :] @ V))

        Sfvm = (IfCJmat @ Cf[il, :] @ E + diags(Cf[il, :] @ V) @ np.conj(Yf[il, :]) @ np.conj(E))
        Stvm = (ItCJmat @ Ct[il, :] @ E + diags(Ct[il, :] @ V) @ np.conj(Yt[il, :]) @ np.conj(E))

        Sfva = (1j * (IfCJmat @ Cf[il, :] @ Vmat - diags(Cf[il, :] @ V) @ np.conj(Yf[il, :]) @ np.conj(Vmat)))
        Stva = (1j * (ItCJmat @ Ct[il, :] @ Vmat - diags(Ct[il, :] @ V) @ np.conj(Yt[il, :]) @ np.conj(Vmat)))

        SfX = sparse.hstack([Sfva, Sfvm, lil_matrix((M, 2 * Ng))])
        StX = sparse.hstack([Stva, Stvm, lil_matrix((M, 2 * Ng))])

        HSf = 2 * (Sfmat.real @ SfX.real + Sfmat.imag @ SfX.imag)
        HSt = 2 * (Stmat.real @ StX.real + Stmat.imag @ StX.imag)

        # New flow derivatives
        # If = Yf[il, :] @ V
        # It = Yt[il, :] @ V
        #
        # Vnorm = V / abs(V)
        #
        # nb = len(V)
        # nl = len(il)
        # v_b = np.arange(nb)
        # v_i = np.arange(nl)
        #
        # from_idx = from_idx[il]
        # to_idx = to_idx[il]
        #
        # diagVf = csr((V[from_idx], (v_i, v_i)))
        # diagIf = csr((If, (v_i, v_i)))
        # diagVt = csr((V[to_idx], (v_i, v_i)))
        # diagIt = csr((It, (v_i, v_i)))
        # diagV  = csr((V, (v_b, v_b)))
        # diagVnorm = csr((Vnorm, (v_b, v_b)))
        #
        # shape = (nl, nb)
        # # Partial derivative of S w.r.t voltage phase angle.
        # dSf_dVa = 1j * (np.conj(diagIf) *
        #                 csr((V[from_idx], (v_i, from_idx)), shape) - diagVf * np.conj(Yf[il, :] * diagV))
        #
        # dSt_dVa = 1j * (np.conj(diagIt) *
        #                 csr((V[to_idx], (v_i, to_idx)), shape) - diagVt * np.conj(Yt[il, :] * diagV))
        #
        # # Partial derivative of S w.r.t. voltage amplitude.
        # dSf_dVm = diagVf * np.conj(Yf[il, :] * diagVnorm) + np.conj(diagIf) * \
        #           csr((Vnorm[from_idx], (v_i, from_idx)), shape)
        #
        # dSt_dVm = diagVt * np.conj(Yt[il, :] * diagVnorm) + np.conj(diagIt) * \
        #           csr((Vnorm[to_idx], (v_i, to_idx)), shape)
        #
        # Sf = V[from_idx] * np.conj(If)
        # St = V[to_idx] * np.conj(It)
        #
        # dAf_dPf = csr((2 * Sf.real, (v_i, v_i)))
        # dAf_dQf = csr((2 * Sf.imag, (v_i, v_i)))
        # dAt_dPt = csr((2 * St.real, (v_i, v_i)))
        # dAt_dQt = csr((2 * St.imag, (v_i, v_i)))
        #
        # # Partial derivative of apparent power magnitude w.r.t voltage
        # # phase angle.
        # dAf_dVa = dAf_dPf * dSf_dVa.real + dAf_dQf * dSf_dVa.imag
        # dAt_dVa = dAt_dPt * dSt_dVa.real + dAt_dQt * dSt_dVa.imag
        # # Partial derivative of apparent power magnitude w.r.t. voltage
        # # amplitude.
        # dAf_dVm = dAf_dPf * dSf_dVm.real + dAf_dQf * dSf_dVm.imag
        # dAt_dVm = dAt_dPt * dSt_dVm.real + dAt_dQt * dSt_dVm.imag
        #
        # HSf = sparse.hstack([dAf_dVa, dAf_dVm, lil_matrix((nl, 2 * Ng))])
        # HSt = sparse.hstack([dAt_dVa, dAt_dVm, lil_matrix((nl, 2 * Ng))])

        #############

        Hpu = np.zeros(Ng)
        Hpl = np.zeros(Ng)
        Hqu = np.zeros(Ng)
        Hql = np.zeros(Ng)

        Hvau_ = csc(([1] * (N - len(slack)), (list(range(N - len(slack))), no_slack)))
        Hval_ = csc(([-1] * (N - len(slack)), (list(range(N - len(slack))), no_slack)))
        Hvmu_ = csc(([1] * (N - len(pv)), (list(range(N - len(pv))), pq)))
        Hvml_ = csc(([-1] * (N - len(pv)), (list(range(N - len(pv))), pq)))

        Hpu[0: N] = 1
        Hpl[0: Ng] = -1
        Hqu[0: Ng] = 1
        Hql[0: Ng] = -1

        Hvu = sparse.hstack([lil_matrix((len(pq), N)), Hvmu_, lil_matrix((len(pq), 2 * Ng))])
        Hvl = sparse.hstack([lil_matrix((len(pq), N)), Hvml_, lil_matrix((len(pq), 2 * Ng))])

        Hvau = sparse.hstack([Hvau_, lil_matrix((N - len(slack), N + 2 * Ng))])
        Hval = sparse.hstack([Hval_, lil_matrix((N - len(slack), N + 2 * Ng))])

        Hpu = sparse.hstack([lil_matrix((Ng, 2 * N)), diags(Hpu), lil_matrix((Ng, Ng))])
        Hpl = sparse.hstack([lil_matrix((Ng, 2 * N)), diags(Hpl), lil_matrix((Ng, Ng))])
        Hqu = sparse.hstack([lil_matrix((Ng, 2 * N + Ng)), diags(Hqu)])
        Hql = sparse.hstack([lil_matrix((Ng, 2 * N + Ng)), diags(Hql)])

        # Hx = sparse.vstack([HSf, HSt, Hvu, Hvl, Hpu, Hpl, Hqu, Hql]).T.tocsc()
        Hx = sparse.vstack([HSf, HSt, Hvu, Hpu, Hqu, Hvl, Hpl, Hql]).T.tocsc()
        # Hx = sparse.vstack([HSf, HSt, Hvu, Hvl, Hvau, Hval, Hpu, Hpl, Hqu, Hql]).T.tocsc()
    else:
        fx = None
        Gx = None
        Hx = None

    ##########

    if compute_hess:

        assert compute_jac  # we must have the jacobian values to get into here

        fxx = diags((np.r_[np.zeros(2 * N), 2 * c2 * (Sbase ** 2), np.zeros(Ng)]) * 1e-4).tocsc()

        ##########

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
        Gav_p = Gva_p.T
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
        Gav_q = Gva_q.T
        Gvv_q = vm_inv @ (C_q + C_q.T) @ vm_inv

        # Add all
        # G1 = sparse.hstack([Gvv_p.real + Gvv_q.imag, Gva_p.real + Gva_q.imag, lil_matrix((N, 2 * Ng))])
        # G2 = sparse.hstack([Gav_p.real + Gav_q.imag, Gaa_p.real + Gaa_q.imag, lil_matrix((N, 2 * Ng))])

        G1 = sparse.hstack([Gaa_p.real + Gaa_q.imag, Gav_p.real + Gav_q.imag, lil_matrix((N, 2 * Ng))])
        G2 = sparse.hstack([Gva_p.real + Gva_q.imag, Gvv_p.real + Gvv_q.imag, lil_matrix((N, 2 * Ng))])
        Gxx = sparse.vstack([G1, G2, lil_matrix((2 * Ng, NV))]).tocsc()

        #########

        mu_mat = diags(Sfmat.conj() @ mu[0: M])
        Af = np.conj(Yf[il, :]).T @ mu_mat @ Cf[il, :]
        Bf = np.conj(Vmat) @ Af @ Vmat
        Df = diags(Af @ V) @ np.conj(Vmat)
        Ef = diags(Af.T @ np.conj(V)) @ Vmat
        Ff = Bf + Bf.T
        Sfvava = Ff - Df - Ef
        Sfvmva = 1j * vm_inv @ (Bf - Bf.T - Df + Ef)
        Sfvavm = Sfvmva.T
        Sfvmvm = vm_inv @ Ff @ vm_inv

        mu_mat = diags(mu[0:M])
        Hfvava = 2 * (Sfvava + Sfva.T @ mu_mat @ np.conj(Sfva)).real
        Hfvmva = 2 * (Sfvmva + Sfvm.T @ mu_mat @ np.conj(Sfva)).real
        Hfvavm = 2 * (Sfvavm + Sfva.T @ mu_mat @ np.conj(Sfvm)).real
        Hfvmvm = 2 * (Sfvmvm + Sfvm.T @ mu_mat @ np.conj(Sfvm)).real

        mu_mat = diags(Stmat.conj() @ mu[M: 2 * M])  # Check same
        At = np.conj(Yt[il, :]).T @ mu_mat @ Ct[il, :]
        Bt = np.conj(Vmat) @ At @ Vmat
        Dt = diags(At @ V) @ np.conj(Vmat)
        Et = diags(At.T @ np.conj(V)) @ Vmat
        Ft = Bt + Bt.T
        Stvava = Ft - Dt - Et
        Stvmva = 1j * vm_inv @ (Bt - Bt.T - Dt + Et)
        Stvavm = Stvmva.T
        Stvmvm = vm_inv @ Ft @ vm_inv

        mu_mat = diags(mu[M:2 * M])
        Htvava = 2 * (Stvava + Stva.T @ mu_mat @ np.conj(Stva)).real
        Htvmva = 2 * (Stvmva + Stvm.T @ mu_mat @ np.conj(Stva)).real
        Htvavm = 2 * (Stvavm + Stva.T @ mu_mat @ np.conj(Stvm)).real
        Htvmvm = 2 * (Stvmvm + Stvm.T @ mu_mat @ np.conj(Stvm)).real

        # H1 = sparse.hstack([Hfvmvm + Htvmvm, Hfvavm + Htvmva, lil_matrix((N, 2 * Ng))])
        # H2 = sparse.hstack([Hfvavm + Htvavm, Hfvava + Htvava, lil_matrix((N, 2 * Ng))])

        H1 = sparse.hstack([Hfvava + Htvava, Hfvavm + Htvavm, lil_matrix((N, 2 * Ng))])
        H2 = sparse.hstack([Hfvmva + Htvmva, Hfvmvm + Htvmvm, lil_matrix((N, 2 * Ng))])
        Hxx = sparse.vstack([H1, H2, lil_matrix((2 * Ng, NV))]).tocsc()
    else:
        fxx = None
        Gxx = None
        Hxx = None

    return fx, Gx, Hx, fxx, Gxx, Hxx
