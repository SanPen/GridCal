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
import pandas as pd
from scipy import sparse
from scipy.sparse import csc_matrix as csc
from dataclasses import dataclass
from scipy.sparse import lil_matrix

from GridCalEngine.Utils.Sparse.csc import diags
from GridCalEngine.Utils.IPS.ips import interior_point_solver, IpsFunctionReturn
import GridCalEngine.Utils.IPS.autodiff as ad
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at, NumericalCircuit
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from typing import Callable, Tuple, Union
from GridCalEngine.basic_structures import Vec, CxVec


def x2var(x: Vec, nVm: int, nVa: int, nPg: int, nQg: int) -> Tuple[Vec, Vec, Vec, Vec]:
    """
    Convert the x solution vector to its composing variables
    :param x: solution vector
    :param nVm: number of voltage module vars
    :param nVa: number of voltage angle vars
    :param nPg: number of generator active power vars
    :param nQg: number of generator reactive power vars
    :return: Vm, Va, Pg, Qg
    """
    a = 0
    b = nVm

    Vm = x[a: b]
    a = b
    b += nVa

    Va = x[a: b]
    a = b
    b += nPg

    Pg = x[a: b]
    a = b
    b += nQg

    Qg = x[a: b]

    return Vm, Va, Pg, Qg


def var2x(Vm: Vec, Va: Vec, Pg: Vec, Qg: Vec) -> Vec:
    """
    Compose the x vector from its componenets
    :param Vm: Voltage modules
    :param Va: Voltage angles
    :param Pg: Generator active powers
    :param Qg: Generator reactive powers
    :return: [Vm, Va, Pg, Qg]
    """
    return np.r_[Vm, Va, Pg, Qg]


def eval_f(x: Vec, Cg, c0: Vec, c1: Vec, c2: Vec, Sbase: float) -> Vec:
    """

    :param x:
    :param Cg:
    :param c0:
    :param c1:
    :param c2:
    :param Sbase:
    :return:
    """
    N, Ng = Cg.shape  # Check

    _, _, Pg, Qg = x2var(x, nVm=N, nVa=N, nPg=Ng, nQg=Ng)

    fval = np.sum((c0 + c1 * Pg * Sbase + c2 * np.power(Pg * Sbase, 2))) * 1e-4

    return fval


def eval_g(x, Ybus, Yf, Cg, Sd, slack) -> Vec:
    """

    :param x:
    :param Ybus:
    :param Yf:
    :param Cg:
    :param Sd:
    :param slack:
    :return:
    """
    M, N = Yf.shape
    Ng = Cg.shape[1]  # Check

    vm, va, Pg, Qg = x2var(x, nVm=N, nVa=N, nPg=Ng, nQg=Ng)

    V = vm * np.exp(1j * va)
    S = V * np.conj(Ybus @ V)

    Sg = Pg + 1j * Qg
    dS = S + Sd - (Cg @ Sg)

    gval = np.r_[dS.real, dS.imag, va[slack]]

    return gval, S


def eval_h(x, Yf, Yt, from_idx, to_idx, no_slack, Va_max, Va_min, Vm_max, Vm_min,
           Pg_max, Pg_min, Qg_max, Qg_min, Cg, rates) -> Vec:
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
    :return:
    """
    M, N = Yf.shape
    Ng = Cg.shape[1]  # Check

    vm, va, Pg, Qg = x2var(x, nVm=N, nVa=N, nPg=Ng, nQg=Ng)

    V = vm * np.exp(1j * va)
    If = np.conj(Yf @ V)
    Lf = If * If
    Sf = V[from_idx] * If
    St = V[to_idx] * np.conj(Yt @ V)
    Sf2 = np.conj(Sf) * Sf
    St2 = np.conj(St) * St
    hval = np.r_[Sf2.real - (rates ** 2),  # rates "lower limit"
                 St2.real - (rates ** 2),  # rates "upper limit"
                 vm - Vm_max,  # voltage module upper limit
                 Vm_min - vm,  # voltage module lower limit
                 va[no_slack] - Va_max[no_slack],  # voltage angles upper limit
                 Va_min[no_slack] - va[no_slack],  # voltage angles lower limit
                 Pg - Pg_max,  # generator P upper limits
                 Pg_min - Pg,  # generator P lower limits
                 Qg - Qg_max,  # generator Q upper limits
                 Qg_min - Qg  # generation Q lower limits
    ]

    return hval, Sf, St


def jacobians_and_hessians(x, c1, c2, Cg, Cf, Ct, Yf, Yt, Ybus, Sbase, slack, no_slack, mu, lmbda,
                           compute_jac: bool, compute_hess: bool,):
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
    :param slack:
    :param no_slack:
    :param mu:
    :param lmbda:
    :return:
    """
    M, N = Yf.shape
    Ng = Cg.shape[1]  # Check
    NV = len(x)

    vm, va, Pg, Qg = x2var(x, nVm=N, nVa=N, nPg=Ng, nQg=Ng)
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
        GSpg = -Cg
        GSqg = -1j * Cg

        GTH = lil_matrix((len(slack), len(x)), dtype=float)
        for i, ss in enumerate(slack):
            GTH[i, N + ss] = 1.

        GS = sparse.hstack([GSvm, GSva, GSpg, GSqg])
        Gx = sparse.vstack([GS.real, GS.imag, GTH]).T.tocsc()

        #############

        IfCJmat = np.conj(diags(Yf @ V))
        ItCJmat = np.conj(diags(Yt @ V))
        Sfmat = diags(diags(Cf @ V) @ np.conj(Yf @ V))
        Stmat = diags(diags(Ct @ V) @ np.conj(Yt @ V))

        Sfvm = IfCJmat @ Cf @ E + diags(Cf @ V) @ np.conj(Yf) @ np.conj(E)
        Stvm = ItCJmat @ Ct @ E + diags(Ct @ V) @ np.conj(Yt) @ np.conj(E)

        Sfva = 1j * (IfCJmat @ Cf @ Vmat - diags(Cf @ V) @ np.conj(Yf) @ np.conj(Vmat))
        Stva = 1j * (ItCJmat @ Ct @ Vmat - diags(Ct @ V) @ np.conj(Yt) @ np.conj(Vmat))

        SfX = sparse.hstack([Sfvm, Sfva, lil_matrix((M, 2 * Ng))])
        StX = sparse.hstack([Stvm, Stva, lil_matrix((M, 2 * Ng))])

        HSf = 2 * (Sfmat.real @ SfX.real + Sfmat.imag @ SfX.imag)
        HSt = 2 * (Stmat.real @ StX.real + Stmat.imag @ StX.imag)

        Hvu = np.zeros(N)
        Hvl = np.zeros(N)
        # Hvau = np.zeros(N)
        # Hval = np.zeros(N)
        Hpu = np.zeros(Ng)
        Hpl = np.zeros(Ng)
        Hqu = np.zeros(Ng)
        Hql = np.zeros(Ng)

        Hvu[0: N] = 1
        Hvl[0: N] = -1
        # Hvau[no_slack] = 1
        # Hval[no_slack] = -1
        Hvau_ = csc(([1] * (N - len(slack)), (list(range(N - len(slack))), no_slack)))
        Hval_ = csc(([-1] * (N - len(slack)), (list(range(N - len(slack))), no_slack)))

        Hpu[0: N] = 1
        Hpl[0: Ng] = -1
        Hqu[0: Ng] = 1
        Hql[0: Ng] = -1

        Hvu = sparse.hstack([diags(Hvu), lil_matrix((N, N + 2 * Ng))])
        Hvl = sparse.hstack([diags(Hvl), lil_matrix((N, N + 2 * Ng))])
        Hvau = sparse.hstack([lil_matrix((N - len(slack), N)), Hvau_, lil_matrix((N - len(slack), 2 * Ng))])
        Hval = sparse.hstack([lil_matrix((N - len(slack), N)), Hval_, lil_matrix((N - len(slack), 2 * Ng))])
        Hpu = sparse.hstack([lil_matrix((Ng, 2 * N)), diags(Hpu), lil_matrix((Ng, Ng))])
        Hpl = sparse.hstack([lil_matrix((Ng, 2 * N)), diags(Hpl), lil_matrix((Ng, Ng))])
        Hqu = sparse.hstack([lil_matrix((Ng, 2 * N + Ng)), diags(Hqu)])
        Hql = sparse.hstack([lil_matrix((Ng, 2 * N + Ng)), diags(Hql)])

        Hx = sparse.vstack([HSf, HSt, Hvu, Hvl, Hvau, Hval, Hpu, Hpl, Hqu, Hql]).T.tocsc()
    else:
        fx = None
        Gx = None
        Hx = None

    ##########

    if compute_hess:

        assert compute_jac  # we must have the jacobian values to get into here

        fxx = diags((np.r_[np.zeros(2 * N), 2 * c2 * (Sbase ** 2), np.zeros(Ng)]) * 1e-4).tocsc()

        ##########

        '''
        lmbda_mat = diags(lmbda[0 : 2 * N])
        Ad = lmbda[0 : 2 * N] * np.r_[V.real, V.imag]
        A = diags(Ad[0 : N] + 1j * Ad[N : 2 * N])
        B = Ybus @ Vmat
        C = A @ np.conj(B)
        D = np.conj(Ybus).T @ Vmat
        F = 1j * (diags(lmbda[0 : N]) @ GSva.real + 1j * diags(lmbda[N : 2 * N]) @ GSva.imag)
        DLmat = D.real @ diags(lmbda[0 : N]) + 1j * D.imag @ diags(lmbda[N : 2 * N])
        DL = D.real @ lmbda[0 : N] + 1j * D.imag @ lmbda[N : 2 * N]
        I = np.conj(Vmat) @ (DLmat - diags(DL))
    
        GSvava_d = I + F
        GSvmva_d = 1j * vm_inv @ (I - F)
        GSvavm_d = GSvmva_d.T
        GSvmvm_d = vm_inv @ (C + C.T) @ vm_inv
    
        GSvava = GSvava_d.real + GSvava_d.imag
        GSvmva = GSvmva_d.real + GSvmva_d.imag
        GSvavm = GSvavm_d.real + GSvavm_d.imag
        GSvmvm = GSvmvm_d.real + GSvmvm_d.imag
    
        G1 = sparse.hstack([GSvmvm, GSvmva, lil_matrix((N, 2 * Ng))])
        G2 = sparse.hstack([GSvavm, GSvava, lil_matrix((N, 2 * Ng))])
        Gxx = sparse.vstack([G1, G2, lil_matrix((2 * Ng, NV))])
    
        #########
        mu_mat = diags(mu[0 : M]) # Check if we have to grab just the from branches
        Af = np.conj(Yf).T @ mu_mat @ Cf
        Bf = np.conj(Vmat) @ Af @ Vmat
        Df = diags(Af @ V) @ np.conj(Vmat)
        Ef = diags(Af.T @ np.conj(V)) @ Vmat
        Ff = Bf + Bf.T
        Sfvava = Ff - Df - Ef
        Sfvmva = 1j * vm_inv @ (Bf - Bf.T - Df + Ef)
        Sfvavm = Sfvmva.T
        Sfvmvm = vm_inv @ Ff @ vm_inv
    
        Hfvava = 2 * (Sfvava @ (np.conj(Sfmat) @ mu[0 : M]) + Sfva.T @ mu_mat @ np.conj(Sfva)).real
        Hfvmva = 2 * (Sfvmva @ (np.conj(Sfmat) @ mu[0 : M]) + Sfvm.T @ mu_mat @ np.conj(Sfva)).real
        Hfvavm = 2 * (Sfvavm @ (np.conj(Sfmat) @ mu[0 : M]) + Sfva.T @ mu_mat @ np.conj(Sfvm)).real
        Hfvmvm = 2 * (Sfvmvm @ (np.conj(Sfmat) @ mu[0 : M]) + Sfvm.T @ mu_mat @ np.conj(Sfvm)).real
    
        mu_mat = diags(mu[M: 2 * M])  # Check same
        At = np.conj(Yt).T @ mu_mat @ Ct
        Bt = np.conj(Vmat) @ At @ Vmat
        Dt = diags(At @ V) @ np.conj(Vmat)
        Et = diags(At.T @ np.conj(V)) @ Vmat
        Ft = Bt + Bt.T
        Stvava = Ft - Dt - Et
        Stvmva = 1j * vm_inv @ (Bt - Bt.T - Dt + Et)
        Stvavm = Stvmva.T
        Stvmvm = vm_inv @ Ft @ vm_inv
    
        Htvava = 2 * (Stvava @ (np.conj(Stmat) @ mu[M : 2 * M]) + Stva.T @ mu_mat @ np.conj(Stva)).real
        Htvmva = 2 * (Stvmva @ (np.conj(Stmat) @ mu[M : 2 * M]) + Stvm.T @ mu_mat @ np.conj(Stva)).real
        Htvavm = 2 * (Stvavm @ (np.conj(Stmat) @ mu[M : 2 * M]) + Stva.T @ mu_mat @ np.conj(Stvm)).real
        Htvmvm = 2 * (Stvmvm @ (np.conj(Stmat) @ mu[M : 2 * M]) + Stvm.T @ mu_mat @ np.conj(Stvm)).real
    
        H1 = sparse.hstack([Hfvmvm + Htvmvm, Hfvmva + Htvmva, lil_matrix((N, 2 * Ng))])
        H2 = sparse.hstack([Hfvavm + Htvavm, Hfvava + Htvava, lil_matrix((N, 2 * Ng))])
        Hxx = sparse.vstack([H1, H2, lil_matrix((2 * Ng, NV))])
        '''

        # # Carlos G
        # lmbda_mat = diags(lmbda[0: 2 * N])
        # Ad = lmbda[0: 2 * N] * np.r_[V.real, V.imag]
        # A = diags(Ad[0: N] + 1j * Ad[N: 2 * N])
        # B = Ybus @ Vmat
        # C = A @ np.conj(B)
        # D = np.conj(Ybus).T @ Vmat
        # F = 1j * (diags(lmbda[0: N]) @ GSva.real + 1j * diags(lmbda[N: 2 * N]) @ GSva.imag)
        # DLmat = D.real @ diags(lmbda[0: N]) + 1j * D.imag @ diags(lmbda[N: 2 * N])
        # DL = D.real @ lmbda[0: N] + 1j * D.imag @ lmbda[N: 2 * N]
        # I = np.conj(Vmat) @ (DLmat - diags(DL))
        #
        # GSvava_d = I + F
        # GSvmva_d = 1j * vm_inv @ (I - F)
        # GSvavm_d = GSvmva_d.T
        # GSvmvm_d = vm_inv @ (C + C.T) @ vm_inv
        #
        # GSvava = GSvava_d.real + GSvava_d.imag
        # GSvmva = GSvmva_d.real + GSvmva_d.imag
        # GSvavm = GSvavm_d.real + GSvavm_d.imag
        # GSvmvm = GSvmvm_d.real + GSvmvm_d.imag
        #
        # G1 = sparse.hstack([GSvmvm, GSvmva, lil_matrix((N, 2 * Ng))])
        # G2 = sparse.hstack([GSvavm, GSvava, lil_matrix((N, 2 * Ng))])
        # Gxx = sparse.vstack([G1, G2, lil_matrix((2 * Ng, NV))])

        # Josep G

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
        G1 = sparse.hstack([Gvv_p.real + Gvv_q.imag, Gva_p.real + Gva_q.imag, lil_matrix((N, 2 * Ng))])
        G2 = sparse.hstack([Gav_p.real + Gav_q.imag, Gaa_p.real + Gaa_q.imag, lil_matrix((N, 2 * Ng))])
        Gxx = sparse.vstack([G1, G2, lil_matrix((2 * Ng, NV))]).tocsc()

        #########

        mu_mat = diags(np.conj(Sfmat) @ mu[0: M])  # Check if we have to grab just the from branches
        Af = np.conj(Yf).T @ mu_mat @ Cf
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

        mu_mat = diags(np.conj(Stmat) @ mu[M: 2 * M])  # Check same
        At = np.conj(Yt).T @ mu_mat @ Ct
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

        H1 = sparse.hstack([Hfvmvm + Htvmvm, Hfvmva + Htvmva, lil_matrix((N, 2 * Ng))])
        H2 = sparse.hstack([Hfvavm + Htvavm, Hfvava + Htvava, lil_matrix((N, 2 * Ng))])
        Hxx = sparse.vstack([H1, H2, lil_matrix((2 * Ng, NV))]).tocsc()
    else:
        fxx = None
        Gxx = None
        Hxx = None

    return fx, Gx, Hx, fxx, Gxx, Hxx


def compute_autodiff_structures(x, mu, lam, compute_jac: bool, compute_hess: bool,
                                Ybus, Yf, Cg, Sd, slack, no_slack, Yt, from_idx, to_idx,
                                Va_max, Va_min, Vm_max, Vm_min, Pg_max, Pg_min, Qg_max, Qg_min,
                                c0, c1, c2, Sbase, rates, h=1e-5) -> IpsFunctionReturn:
    """

    :param x:
    :param mu:
    :param lmbda:
    :param Ybus:
    :param Yf:
    :param Cg:
    :param Sd:
    :param slack:
    :param no_slack:
    :param Yt:
    :param from_idx:
    :param to_idx:
    :param Va_max:
    :param Va_min:
    :param Vm_max:
    :param Vm_min:
    :param Pg_max:
    :param Pg_min:
    :param Qg_max:
    :param Qg_min:
    :param c0:
    :param c1:
    :param c2:
    :param Sbase:
    :param rates:
    :param h:
    :return:
    """
    f = eval_f(x=x, Cg=Cg, c0=c0, c1=c1, c2=c2, Sbase=Sbase)
    G, Scalc = eval_g(x=x, Ybus=Ybus, Yf=Yf, Cg=Cg, Sd=Sd, slack=slack)
    H, Sf, St = eval_h(x=x, Yf=Yf, Yt=Yt, from_idx=from_idx, to_idx=to_idx, no_slack=no_slack, Va_max=Va_max,
                       Va_min=Va_min, Vm_max=Vm_max, Vm_min=Vm_min, Pg_max=Pg_max, Pg_min=Pg_min,
                       Qg_max=Qg_max, Qg_min=Qg_min, Cg=Cg,
                       rates=rates)

    if compute_jac:
        fx = ad.calc_autodiff_jacobian_f_obj(func=eval_f, x=x, arg=(Cg, c0, c1, c2, Sbase), h=h).tocsc()
        Gx = ad.calc_autodiff_jacobian(func=eval_g, x=x, arg=(Ybus, Yf, Cg, Sd, slack)).T.tocsc()
        Hx = ad.calc_autodiff_jacobian(func=eval_h, x=x, arg=(Yf, Yt, from_idx, to_idx, no_slack, Va_max, Va_min,
                                                              Vm_max, Vm_min, Pg_max, Pg_min, Qg_max, Qg_min, Cg, rates)).T.tocsc()
    else:
        fx = None
        Gx = None
        Hx = None

    if compute_hess:
        fxx = ad.calc_autodiff_hessian_f_obj(func=eval_f, x=x, arg=(Cg, c0, c1, c2, Sbase), h=h).tocsc()
        Gxx = ad.calc_autodiff_hessian(func=eval_g, x=x, mult=lam, arg=(Ybus, Yf, Cg, Sd, slack)).tocsc()
        Hxx = ad.calc_autodiff_hessian(func=eval_h, x=x, mult=mu, arg=(Yf, Yt, from_idx, to_idx, no_slack, Va_max,
                                                                       Va_min, Vm_max, Vm_min, Pg_max, Pg_min,
                                                                       Qg_max, Qg_min, Cg, rates)).tocsc()
    else:
        fxx = None
        Gxx = None
        Hxx = None

    # approximate the Hessian using the Gauss-Newton matrix
    # Gxx = Gx @ Gx.T
    # Hxx = Hx @ Hx.T

    return IpsFunctionReturn(f=f, G=G, H=H,
                             fx=fx, Gx=Gx, Hx=Hx,
                             fxx=fxx, Gxx=Gxx, Hxx=Hxx,
                             S=Scalc, St=St, Sf=Sf)


def compute_analytic_structures(x, mu, lmbda, compute_jac: bool, compute_hess: bool,
                                Ybus, Yf, Cg, Cf, Ct, Sd, slack, no_slack, Yt, from_idx, to_idx,
                                th_max, th_min, V_U, V_L, P_U, P_L, Q_U, Q_L,
                                c0, c1, c2, Sbase, rates) -> IpsFunctionReturn:
    """

    :param x:
    :param mu:
    :param lmbda:
    :param compute_jac
    :param Ybus:
    :param Yf:
    :param Cg:
    :param Cf:
    :param Ct:
    :param Sd:
    :param slack:
    :param no_slack:
    :param Yt:
    :param from_idx:
    :param to_idx:
    :param th_max:
    :param th_min:
    :param V_U:
    :param V_L:
    :param P_U:
    :param P_L:
    :param Q_U:
    :param Q_L:
    :param c0:
    :param c1:
    :param c2:
    :param Sbase:
    :param rates:
    :param h:
    :return:
    """
    f = eval_f(x=x, Cg=Cg, c0=c0, c1=c1, c2=c2, Sbase=Sbase)
    G, Scalc = eval_g(x=x, Ybus=Ybus, Yf=Yf, Cg=Cg, Sd=Sd, slack=slack)
    H, Sf, St = eval_h(x=x, Yf=Yf, Yt=Yt, from_idx=from_idx, to_idx=to_idx, no_slack=no_slack, Va_max=th_max,
                       Va_min=th_min, Vm_max=V_U, Vm_min=V_L, Pg_max=P_U, Pg_min=P_L, Qg_max=Q_U, Qg_min=Q_L, Cg=Cg,
                       rates=rates)

    fx, Gx, Hx, fxx, Gxx, Hxx = jacobians_and_hessians(x=x, c1=c1, c2=c2, Cg=Cg, Cf=Cf, Ct=Ct, Yf=Yf, Yt=Yt,
                                                       Ybus=Ybus, Sbase=Sbase, slack=slack, no_slack=no_slack,
                                                       mu=mu, lmbda=lmbda, compute_jac=compute_jac, compute_hess=compute_hess)


    return IpsFunctionReturn(f=f, G=G, H=H,
                             fx=fx, Gx=Gx, Hx=Hx,
                             fxx=fxx, Gxx=Gxx, Hxx=Hxx,
                             S=Scalc, St=St, Sf=Sf)


def evaluate_power_flow_debug(x, mu, lmbda, compute_jac: bool, compute_hess: bool,
                              Ybus, Yf, Cg, Cf, Ct, Sd, slack, no_slack, Yt, from_idx, to_idx,
                              th_max, th_min, V_U, V_L, P_U, P_L, Q_U, Q_L,
                              c0, c1, c2, Sbase, rates, h=1e-5) -> IpsFunctionReturn:
    """

    :param x:
    :param mu:
    :param lmbda:
    :param Ybus:
    :param Yf:
    :param Cg:
    :param Cf:
    :param Ct:
    :param Sd:
    :param slack:
    :param no_slack:
    :param Yt:
    :param from_idx:
    :param to_idx:
    :param th_max:
    :param th_min:
    :param V_U:
    :param V_L:
    :param P_U:
    :param P_L:
    :param Q_U:
    :param Q_L:
    :param c0:
    :param c1:
    :param c2:
    :param Sbase:
    :param rates:
    :param h:
    :return:
    """

    mats_analytic = compute_analytic_structures(x, mu, lmbda, compute_jac, compute_hess,
                                                Ybus, Yf, Cg, Cf, Ct, Sd, slack, no_slack, Yt, from_idx,
                                                to_idx,
                                                th_max, th_min, V_U, V_L, P_U, P_L, Q_U, Q_L, c0, c1, c2, Sbase, rates)

    mats_finite = compute_autodiff_structures(x, mu, lmbda, compute_jac, compute_hess,
                                              Ybus, Yf, Cg, Sd, slack, no_slack, Yt, from_idx, to_idx,
                                              th_max, th_min, V_U, V_L, P_U, P_L, Q_U, Q_L, c0, c1, c2, Sbase, rates,
                                              h=h)

    errors = mats_finite.compare(mats_analytic, h=h)

    if len(errors) > 0:
        for key, struct in errors.items():
            print(key + "\n", struct)

        raise Exception('The analytic structures differ from the finite differences: {}'.format(errors))

    return mats_analytic


@dataclass
class NonlinearOPFResults:
    """
    Numerical non linear OPF results
    """
    Vm: Vec
    Va: Vec
    S: CxVec
    Sf: CxVec
    St: CxVec
    loading: Vec
    Pg: Vec
    Qg: Vec
    lam_p: Vec
    lam_q: Vec
    error: float
    converged: bool
    iterations: int

    @property
    def V(self) -> CxVec:
        """
        Complex voltage
        :return: CxVec
        """
        return self.Vm * np.exp(1j * self.Va)


def ac_optimal_power_flow(nc: NumericalCircuit,
                          pf_options: PowerFlowOptions,
                          debug: bool = False,
                          use_autodiff: bool = False,
                          plot_error: bool = False) -> NonlinearOPFResults:
    """

    :param nc: NumericalCircuit
    :param pf_options: PowerFlowOptions
    :param debug: if true, the jacobians, hessians, etc are checked against finite difeerence versions of them
    :param use_autodiff: use the autodiff version of the structures
    :param plot_error:
    :return: NonlinearOPFResults
    """

    # compile the grid snapshot
    Sbase = nc.Sbase
    c0 = nc.generator_data.cost_0
    c1 = nc.generator_data.cost_1
    c2 = nc.generator_data.cost_2

    Ybus = nc.Ybus
    Yf = nc.Yf
    Yt = nc.Yt
    Cg = nc.generator_data.C_bus_elm
    Cf = nc.Cf
    Ct = nc.Ct

    # Bus identification lists
    slack = nc.vd
    no_slack = nc.pqpv
    from_idx = nc.F
    to_idx = nc.T

    # Bus and line parameters
    Sd = - nc.load_data.get_injections_per_bus() / Sbase
    Pg_max = nc.generator_data.pmax / Sbase
    Pg_min = nc.generator_data.pmin / Sbase
    Qg_max = nc.generator_data.qmax / Sbase
    Qg_min = nc.generator_data.qmin / Sbase
    Vm_max = nc.bus_data.Vmax
    Vm_min = nc.bus_data.Vmin
    rates = nc.rates / Sbase
    Va_max = nc.bus_data.angle_max
    Va_min = nc.bus_data.angle_min

    nbr = nc.branch_data.nelm
    nbus = nc.bus_data.nbus
    ngen = nc.generator_data.nelm
    n_no_slack = len(no_slack)
    n_slack = len(slack)

    # Number of equalities: Nodal power balances, the voltage module of slack and pv buses and the slack reference
    NE = 2 * nbus + n_slack

    # Number of innequalities: Line ratings, max and min angle of buses, voltage module range and
    NI = 2 * nbr + 2 * n_no_slack + 2 * nbus + 4 * ngen

    # run power flow to initialize
    pf_results = multi_island_pf_nc(nc=nc, options=pf_options)

    # ignore power from Z and I of the load
    s0gen = (pf_results.Sbus - nc.load_data.get_injections_per_bus()) / nc.Sbase
    p0gen = nc.generator_data.C_bus_elm.T @ np.real(s0gen)
    q0gen = nc.generator_data.C_bus_elm.T @ np.imag(s0gen)

    # nc.Vbus  # dummy initialization

    # compose the initial values
    x0 = var2x(Vm=np.abs(pf_results.voltage),
               Va=np.angle(pf_results.voltage),
               Pg=p0gen,
               Qg=q0gen)

    # number of variables
    NV = len(x0)

    if pf_options.verbose > 0:
        print("x0:", x0)

    if debug:
        # run the solver with the function that checks the derivatives
        # against their finite differences equivalent
        result = interior_point_solver(x0=x0, n_x=NV, n_eq=NE, n_ineq=NI,
                                       func=evaluate_power_flow_debug,
                                       arg=(Ybus, Yf, Cg, Cf, Ct, Sd, slack, no_slack, Yt,
                                            from_idx, to_idx, Va_max, Va_min, Vm_max, Vm_min,
                                            Pg_max, Pg_min, Qg_max, Qg_min,
                                            c0, c1, c2, Sbase, rates),
                                       verbose=pf_options.verbose,
                                       max_iter=pf_options.max_iter)

    else:
        if use_autodiff:
            # run the solver with the autodiff derivatives
            result = interior_point_solver(x0=x0, n_x=NV, n_eq=NE, n_ineq=NI,
                                           func=compute_autodiff_structures,
                                           arg=(Ybus, Yf, Cg, Sd, slack, no_slack, Yt, from_idx, to_idx,
                                                Va_max, Va_min, Vm_max, Vm_min, Pg_max, Pg_min, Qg_max, Qg_min,
                                                c0, c1, c2, Sbase, rates, 1e-5),
                                           verbose=pf_options.verbose,
                                           max_iter=pf_options.max_iter)
        else:
            # run the solver with the analytic derivatives
            result = interior_point_solver(x0=x0, n_x=NV, n_eq=NE, n_ineq=NI,
                                           func=compute_analytic_structures,
                                           arg=(Ybus, Yf, Cg, Cf, Ct, Sd, slack, no_slack, Yt,
                                                from_idx, to_idx, Va_max, Va_min, Vm_max, Vm_min,
                                                Pg_max, Pg_min, Qg_max, Qg_min,
                                                c0, c1, c2, Sbase, rates),
                                           verbose=pf_options.verbose,
                                           max_iter=pf_options.max_iter)

    # convert the solution to the problem variables
    Vm, Va, Pg, Qg = x2var(result.x, nVm=nbus, nVa=nbus, nPg=ngen, nQg=ngen)

    # convert the lagrange multipliers to significant ones
    lam_p, lam_q = result.lam[:nbus], result.lam[nbus:2 * nbus]

    S = result.structs.S
    Sf = result.structs.Sf
    St = result.structs.St
    loading = np.abs(Sf) / (rates + 1e-9)
    if pf_options.verbose > 0:
        df_bus = pd.DataFrame(data={'Vm (p.u.)': Vm, 'Va (rad)': Va,
                                    'dual price (€/MW)': lam_p, 'dual price (€/MVAr)': lam_q})
        df_gen = pd.DataFrame(data={'P (MW)': Pg * nc.Sbase, 'Q (MVAr)': Qg * nc.Sbase})
        print()
        print("Bus:\n", df_bus)
        print("Gen:\n", df_gen)
        print("Error", result.error)

    if plot_error:
        result.plot_error()

    return NonlinearOPFResults(Vm=Vm, Va=Va, S=S, Sf=Sf, St=St, loading=loading,
                               Pg=Pg, Qg=Qg, lam_p=lam_p, lam_q=lam_q,
                               error=result.error, converged=result.converged, iterations=result.iterations)


def run_nonlinear_opf(grid: MultiCircuit,
                      pf_options: PowerFlowOptions,
                      t_idx: Union[None, int] = None,
                      debug: bool = False,
                      use_autodiff: bool = False,
                      plot_error: bool = False) -> NonlinearOPFResults:
    """

    :param grid:
    :param pf_options:
    :param t_idx:
    :param debug:
    :param use_autodiff:
    :return:
    """
    nc = compile_numerical_circuit_at(circuit=grid, t_idx=t_idx)

    return ac_optimal_power_flow(nc=nc, pf_options=pf_options,
                                 debug=debug, use_autodiff=use_autodiff,
                                 plot_error=plot_error)
