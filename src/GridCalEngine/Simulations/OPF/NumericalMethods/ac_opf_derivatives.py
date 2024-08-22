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
import timeit

import numpy as np
from scipy import sparse as sp
from scipy.sparse import csc_matrix as csc
from scipy.sparse import lil_matrix

from GridCalEngine.Utils.Sparse.csc import diags
from typing import Tuple
from GridCalEngine.basic_structures import Vec, CxVec, IntVec, csr_matrix, csc_matrix
from GridCalEngine.enumerations import AcOpfMode


def x2var(x: Vec,
          nVa: int,
          nVm: int,
          nPg: int,
          nQg: int,
          npq: int,
          M: int,
          ntapm: int,
          ntapt: int,
          ndc: int,
          nslcap: int,
          acopf_mode: AcOpfMode) -> Tuple[Vec, Vec, Vec, Vec, Vec, Vec, Vec, Vec, Vec, Vec, Vec, Vec]:
    """
    Convert the x solution vector to its composing variables
    :param x: solution vector
    :param nVa: number of voltage angle vars
    :param nVm: number of voltage module vars
    :param nPg: number of generator active power vars
    :param nQg: number of generator reactive power vars
    :param npq: number of PQ buses
    :param M: number of monitored lines
    :param ntapm: number of module controlled transformers
    :param ntapt: number of phase controlled transformers
    :param ndc: number of dispatchable DC links
    :param nslcap:
    :param acopf_mode: AcOpfMode
    :return: Tuple of sliced variables
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

    if acopf_mode == AcOpfMode.ACOPFslacks:
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
        b += nslcap

    else:
        b += nslcap
        # Create empty arrays for not used variables
        sl_sf = np.array([])
        sl_st = np.array([])
        sl_vmax = np.array([])
        sl_vmin = np.array([])

    slcap = x[a:b]
    a = b
    b += ntapm

    tapm = x[a: b]
    a = b
    b += ntapt

    tapt = x[a: b]
    a = b
    b += ndc

    Pfdc = x[a: b]

    return Va, Vm, Pg, Qg, sl_sf, sl_st, sl_vmax, sl_vmin, slcap, tapm, tapt, Pfdc


def var2x(Va: Vec,
          Vm: Vec,
          Pg: Vec,
          Qg: Vec,
          sl_sf: Vec,
          sl_st: Vec,
          sl_vmax: Vec,
          sl_vmin: Vec,
          slcap: Vec,
          tapm: Vec,
          tapt: Vec,
          Pfdc: Vec) -> Vec:
    """
    Compose the x vector from its components
    :param Va: Voltage angles
    :param Vm: Voltage modules
    :param Pg: Generator active powers
    :param Qg: Generator reactive powers
    :param sl_sf: Bound slacks for the 'from' power through a line
    :param sl_st: Bound slacks for the 'to' power through a line
    :param sl_vmax: Bound slacks for the maximum voltage of the buses
    :param sl_vmin: Bound slacks for the minimum voltage of the buses
    :param slcap:
    :param tapm: Tap modules
    :param tapt: Tap phases
    :param Pfdc: From power of the dispatchable DC links
    :return: The stacked state vector [Va, Vm, Pg, Qg, sl_sf, sl_st, sl_vmax, sl_vmin, tapm, tapt, Pfdc]
    """
    return np.r_[Va, Vm, Pg, Qg, sl_sf, sl_st, sl_vmax, sl_vmin, slcap, tapm, tapt, Pfdc]


def compute_branch_power_derivatives(all_tap_m: Vec,
                                     all_tap_tau: Vec,
                                     V: CxVec,
                                     k_m: Vec,
                                     k_tau: Vec,
                                     Cf: csc,
                                     Ct: csc,
                                     F: IntVec,
                                     T: IntVec,
                                     R: Vec,
                                     X: Vec) -> Tuple[
    csr_matrix, lil_matrix, lil_matrix, csr_matrix, lil_matrix, lil_matrix]:
    """

    :param all_tap_m: Vector with all the tap module, including the non-controlled ones
    :param all_tap_tau: Vector with all the tap phases, including the non-controlled ones
    :param V: Complex voltages
    :param k_m: List with the index of the module controlled transformers
    :param k_tau: List with the index of the phase controlled transformers
    :param Cf: From connectivity matrix
    :param Ct: To connectivity matrix
    :param F: Array of "from" buses of each branch
    :param T: Array of "to" buses of each branch
    :param R: Line resistances
    :param X: Line inductances
    :return: First power derivatives with respect to the tap variables
            [dSbusdm, dSfdm, dStdm, dSbusdt, dSfdtau, dStdtau]
    """
    ys = 1.0 / (R + 1.0j * X + 1e-20)

    nbr = len(all_tap_m)
    dSfdm = lil_matrix((nbr, len(k_m)), dtype=complex)
    dStdm = lil_matrix((nbr, len(k_m)), dtype=complex)
    dSfdtau = lil_matrix((nbr, len(k_tau)), dtype=complex)
    dStdtau = lil_matrix((nbr, len(k_tau)), dtype=complex)

    for k_pos, k in enumerate(k_m):
        Vf = V[F[k]]
        Vt = V[T[k]]
        mp = all_tap_m[k]
        tau = all_tap_tau[k]
        yk = ys[k]
        mp2 = np.power(mp, 2)

        # First derivatives with respect to the tap module.
        # Each branch is computed individually and stored
        dSfdm[k, k_pos] = Vf * ((-2 * np.conj(yk * Vf) / np.power(mp, 3)) + np.conj(yk * Vt) / (mp2 * np.exp(1j * tau)))
        dStdm[k, k_pos] = Vt * (np.conj(yk * Vf) / (mp2 * np.exp(-1j * tau)))

    for k_pos, k in enumerate(k_tau):
        Vf = V[F[k]]
        Vt = V[T[k]]
        mp = all_tap_m[k]
        tau = all_tap_tau[k]
        yk = ys[k]

        # First derivatives with respect to the tap phase.
        # Each branch is computed individually and stored
        dSfdtau[k, k_pos] = Vf * 1j * np.conj(yk * Vt) / (mp * np.exp(1j * tau))
        dStdtau[k, k_pos] = Vt * -1j * np.conj(yk * Vf) / (mp * np.exp(-1j * tau))

    # Bus power injection is computed using the 'from' and 'to' powers and their connectivity matrices
    dSbusdm = Cf.T @ dSfdm + Ct.T @ dStdm
    dSbusdt = Cf.T @ dSfdtau + Ct.T @ dStdtau

    return dSbusdm, dSfdm, dStdm, dSbusdt, dSfdtau, dStdtau


def compute_branch_power_second_derivatives(all_tap_m: Vec,
                                            all_tap_tau: Vec,
                                            vm: Vec,
                                            va: Vec,
                                            k_m: IntVec,
                                            k_tau: IntVec,
                                            mon_idx: IntVec,
                                            R: Vec,
                                            X: Vec,
                                            F: IntVec,
                                            T: IntVec,
                                            lam: Vec,
                                            mu: Vec,
                                            Sf: CxVec,
                                            St: CxVec) -> Tuple[
    lil_matrix, lil_matrix, lil_matrix,
    lil_matrix, lil_matrix, lil_matrix,
    lil_matrix, lil_matrix, lil_matrix,
    lil_matrix, lil_matrix, lil_matrix,
    lil_matrix, lil_matrix, lil_matrix,
    lil_matrix, lil_matrix, lil_matrix,
    lil_matrix, lil_matrix, lil_matrix]:
    """
    :param all_tap_m: Vector with all the tap module, including the non-controlled ones
    :param all_tap_tau: Vector with all the tap phase, including the non-controlled ones
    :param vm: Voltage modules
    :param va: Voltage angles
    :param k_m: List with the index of the module controlled transformers
    :param k_tau: List with the index of the phase controlled transformers
    :param mon_idx: List with the index of the monitored lines
    :param R: Line resistances
    :param X: Line inductances
    :param F: Indexes of the 'from' buses
    :param T: Indexes of the 'to' buses
    :param lam: Lambda multiplier
    :param mu: Mu multiplier
    :param Sf: From powers
    :param St: To powers
    :return: Power second derivatives with respect to tap variables
    """
    ys = 1.0 / (R + 1.0j * X + 1e-20)
    V = vm * np.exp(1j * va)

    N = len(vm)
    M = len(mon_idx)
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

    for k_pos, k in enumerate(k_m):
        f = F[k]
        t = T[k]
        Vf = V[f]
        Vt = V[t]
        mp = all_tap_m[k]
        tau = all_tap_tau[k]
        yk = ys[k]
        tap_unit = np.exp(1j * tau)
        tap_unit_c = np.exp(-1j * tau)

        # For each line with a module controlled transformer, compute its second derivatives w.r.t. the tap module and
        # the rest of the variables.
        mp2 = mp * mp
        mp3 = mp2 * mp
        mp4 = mp3 * mp
        dSfdmdm_ = Vf * ((6 * np.conj(yk * Vf) / mp4) - 2 * np.conj(yk * Vt) / (mp3 * tap_unit))
        dStdmdm_ = - Vt * 2 * np.conj(yk * Vf) / (mp3 * tap_unit_c)

        dSfdmdva_f = Vf * 1j * np.conj(yk * Vt) / (mp2 * tap_unit)
        dSfdmdva_t = - Vf * 1j * np.conj(yk * Vt) / (mp2 * tap_unit)

        dStdmdva_f = - Vt * 1j * np.conj(yk * Vf) / (mp2 * tap_unit_c)
        dStdmdva_t = Vt * 1j * np.conj(yk * Vf) / (mp2 * tap_unit_c)

        dSfdmdvm_f = Vf * (1 / vm[f]) * ((-4 * np.conj(yk * Vf) / mp3) + np.conj(yk * Vt) / (mp2 * tap_unit))
        dSfdmdvm_t = Vf * (1 / vm[t]) * np.conj(yk * Vt) / (mp2 * tap_unit)

        dStdmdvm_f = Vt * (1 / vm[f]) * np.conj(yk * Vf) / (mp2 * tap_unit_c)
        dStdmdvm_t = Vt * (1 / vm[t]) * np.conj(yk * Vf) / (mp2 * tap_unit_c)

        lin = np.where(k_tau == k)[0]  # TODO: should pass along the control type and check that instead

        if len(lin) != 0:
            k_pos = lin[0]
            # If the trafo is controlled for both module and phase, compute these derivatives. Otherwise, they are 0
            dSfdmdt_ = - Vf * 1j * (np.conj(yk * Vt) / (mp2 * tap_unit))
            dStdmdt_ = Vt * 1j * (np.conj(yk * Vf) / (mp2 * tap_unit_c))

            dSbusdmdt[k_pos, k_pos] = ((dSfdmdt_ * lam[f]).real + (dSfdmdt_ * lam[f + N]).imag
                                       + (dStdmdt_ * lam[t]).real + (dStdmdt_ * lam[t + N]).imag)
            if k in mon_idx:
                # This is only included if the branch is monitored.
                li = np.where(mon_idx == k)[0]  # TODO: Why is this here?
                dSfdmdt[k_pos, k_pos] = dSfdmdt_ * Sf[li].conj() * mu[li]
                dStdmdt[k_pos, k_pos] = dStdmdt_ * St[li].conj() * mu[li + M]

        # Compute the hessian terms merging Sf and St into Sbus
        dSbusdmdm[k_pos, k_pos] = ((dSfdmdm_ * lam[f]).real + (dSfdmdm_ * lam[f + N]).imag
                                   + (dStdmdm_ * lam[t]).real + (dStdmdm_ * lam[t + N]).imag)
        dSbusdmdva[f, k_pos] = ((dSfdmdva_f * lam[f]).real + (dSfdmdva_f * lam[f + N]).imag
                                + (dStdmdva_f * lam[t]).real + (dStdmdva_f * lam[t + N]).imag)
        dSbusdmdva[t, k_pos] = ((dSfdmdva_t * lam[f]).real + (dSfdmdva_t * lam[f + N]).imag
                                + (dStdmdva_t * lam[t]).real + (dStdmdva_t * lam[t + N]).imag)
        dSbusdmdvm[f, k_pos] = ((dSfdmdvm_f * lam[f]).real + (dSfdmdvm_f * lam[f + N]).imag
                                + (dStdmdvm_f * lam[t]).real + (dStdmdvm_f * lam[t + N]).imag)
        dSbusdmdvm[t, k_pos] = ((dSfdmdvm_t * lam[f]).real + (dSfdmdvm_t * lam[f + N]).imag
                                + (dStdmdvm_t * lam[t]).real + (dStdmdvm_t * lam[t + N]).imag)

        if k in mon_idx:
            # Hessian terms, only for monitored lines
            li = np.where(mon_idx == k)[0]  # TODO: Why is this here?
            dSfdmdm[k_pos, k_pos] = dSfdmdm_ * Sf[li].conj() * mu[li]
            dStdmdm[k_pos, k_pos] = dStdmdm_ * St[li].conj() * mu[li + M]
            dSfdmdva[f, k_pos] = dSfdmdva_f * Sf[li].conj() * mu[li]
            dStdmdva[f, k_pos] = dStdmdva_f * St[li].conj() * mu[li + M]
            dSfdmdva[t, k_pos] = dSfdmdva_t * Sf[li].conj() * mu[li]
            dStdmdva[t, k_pos] = dStdmdva_t * St[li].conj() * mu[li + M]
            dSfdmdvm[f, k_pos] = dSfdmdvm_f * Sf[li].conj() * mu[li]
            dStdmdvm[f, k_pos] = dStdmdvm_f * St[li].conj() * mu[li + M]
            dSfdmdvm[t, k_pos] = dSfdmdvm_t * Sf[li].conj() * mu[li]
            dStdmdvm[t, k_pos] = dStdmdvm_t * St[li].conj() * mu[li + M]

    for k_pos, k in enumerate(k_tau):
        f = F[k]
        t = T[k]
        Vf = V[f]
        Vt = V[t]
        Vmf = abs(Vf)
        Vmt = abs(Vt)
        mp = all_tap_m[k]
        tau = all_tap_tau[k]
        yk = ys[k]
        tap = mp * np.exp(1j * tau)
        tap_c = mp * np.exp(-1j * tau)

        # Same procedure for phase controlled transformers
        dSfdtdt_ = Vf * np.conj(yk * Vt) / tap
        dStdtdt_ = Vt * np.conj(yk * Vf) / tap_c

        dSfdtdva_f = - Vf * np.conj(yk * Vt) / tap
        dSfdtdva_t = Vf * np.conj(yk * Vt) / tap

        dStdtdva_f = - Vt * np.conj(yk * Vf) / tap_c
        dStdtdva_t = Vt * np.conj(yk * Vf) / tap_c

        dSfdtdvm_f = 1.0j * Vf / Vmf * np.conj(yk * Vt) / tap
        dSfdtdvm_t = 1.0j * Vf / Vmt * np.conj(yk * Vt) / tap

        dStdtdvm_f = -1.0j * Vt / Vmf * np.conj(yk * Vf) / tap_c
        dStdtdvm_t = -1.0j * Vt / Vmt * np.conj(yk * Vf) / tap_c

        # Merge Sf and St in Sbus
        dSbusdtdt[k_pos, k_pos] = ((dSfdtdt_ * lam[f]).real + (dSfdtdt_ * lam[f + N]).imag
                                   + (dStdtdt_ * lam[t]).real + (dStdtdt_ * lam[t + N]).imag)
        dSbusdtdva[f, k_pos] = ((dSfdtdva_f * lam[f]).real + (dSfdtdva_f * lam[f + N]).imag
                                + (dStdtdva_f * lam[t]).real + (dStdtdva_f * lam[t + N]).imag)
        dSbusdtdva[t, k_pos] = ((dSfdtdva_t * lam[f]).real + (dSfdtdva_t * lam[f + N]).imag
                                + (dStdtdva_t * lam[t]).real + (dStdtdva_t * lam[t + N]).imag)
        dSbusdtdvm[f, k_pos] = ((dSfdtdvm_f * lam[f]).real + (dSfdtdvm_f * lam[f + N]).imag
                                + (dStdtdvm_f * lam[t]).real + (dStdtdvm_f * lam[t + N]).imag)
        dSbusdtdvm[t, k_pos] = ((dSfdtdvm_t * lam[f]).real + (dSfdtdvm_t * lam[f + N]).imag
                                + (dStdtdvm_t * lam[t]).real + (dStdtdvm_t * lam[t + N]).imag)
        dSbusdtdt[k_pos, k_pos] = ((dSfdtdt_ * lam[f]).real + (dSfdtdt_ * lam[f + N]).imag
                                   + (dStdtdt_ * lam[t]).real + (dStdtdt_ * lam[t + N]).imag)

        if k in mon_idx:
            li = np.where(mon_idx == k)[0]  # TODO: Why is this here?
            dSfdtdt[k_pos, k_pos] = dSfdtdt_ * Sf[li].conj() * mu[li]
            dStdtdt[k_pos, k_pos] = dStdtdt_ * St[li].conj() * mu[li + M]
            dSfdtdva[f, k_pos] = dSfdtdva_f * Sf[li].conj() * mu[li]
            dStdtdva[f, k_pos] = dStdtdva_f * St[li].conj() * mu[li + M]
            dSfdtdva[t, k_pos] = dSfdtdva_t * Sf[li].conj() * mu[li]
            dStdtdva[t, k_pos] = dStdtdva_t * St[li].conj() * mu[li + M]
            dSfdtdvm[f, k_pos] = dSfdtdvm_f * Sf[li].conj() * mu[li]
            dStdtdvm[f, k_pos] = dStdtdvm_f * St[li].conj() * mu[li + M]
            dSfdtdvm[t, k_pos] = dSfdtdvm_t * Sf[li].conj() * mu[li]
            dStdtdvm[t, k_pos] = dStdtdvm_t * St[li].conj() * mu[li + M]
            dSfdtdt[k_pos, k_pos] = dSfdtdt_ * Sf[li].conj() * mu[li]
            dStdtdt[k_pos, k_pos] = dStdtdt_ * St[li].conj() * mu[li + M]

    return (dSbusdmdm, dSfdmdm, dStdmdm,
            dSbusdmdvm, dSfdmdvm, dStdmdvm,
            dSbusdmdva, dSfdmdva, dStdmdva,
            dSbusdmdt, dSfdmdt, dStdmdt,
            dSbusdtdt, dSfdtdt, dStdtdt,
            dSbusdtdvm, dSfdtdvm, dStdtdvm,
            dSbusdtdva, dSfdtdva, dStdtdva)


def eval_f(x: Vec, Cg: csc_matrix, k_m: Vec, k_tau: Vec, nll: int, c0: Vec, c1: Vec,
           c2: Vec, c_s: Vec, nslcap: int, nodal_capacity_sign: float,
           c_v: Vec, ig: Vec, npq: int, ndc: int, Sbase: float, acopf_mode: AcOpfMode) -> float:
    """
    Calculates the value of the objective function at the current state (given by x)
    :param x: State vector
    # //////////////////////////////////////////////////////
    :param Cg: Generation connectivity matrix
    :param k_m: List with the index of the module controlled transformers
    :param k_tau: List with the index of the phase controlled transformers
    :param nll: Number of monitored lines
    :param c0: Base cost of generators
    :param c1: Linear cost of generators
    :param c2: Quadratic cost of generators
    :param c_s: Cost of overloading a line
    :param nslcap:
    :param nodal_capacity_sign:
    :param c_v: Cost of over or undervoltages
    :param ig: Dispatchable generators
    :param npq: Number of pq buses
    :param ndc: Number of dispatchable DC links
    :param Sbase: Base power (per unit reference)
    :param acopf_mode: AcOpfMode
    :return: Scalar value: Cost of operation (objective function)
    """
    N, _ = Cg.shape  # Check
    Ng = len(ig)
    ntapm = len(k_m)
    ntapt = len(k_tau)

    _, _, Pg, Qg, sl_sf, sl_st, sl_vmax, sl_vmin, slcap, _, _, _ = x2var(x, nVa=N, nVm=N, nPg=Ng, nQg=Ng, npq=npq,
                                                                         M=nll, ntapm=ntapm, ntapt=ntapt, ndc=ndc,
                                                                         nslcap=nslcap, acopf_mode=acopf_mode)
    # Obj. function:  Active power generation costs plus overloads and voltage deviation penalties

    fval = 1e-4 * (np.sum((c0 + c1 * Pg * Sbase + c2 * np.power(Pg * Sbase, 2)))
                   + np.sum(c_s * (sl_sf + sl_st)) + np.sum(c_v * (sl_vmax + sl_vmin))
                   + np.sum(nodal_capacity_sign * slcap))

    return fval


def eval_g(x: Vec, Ybus: csc_matrix, Yf: csc_matrix, Cg: csc_matrix, Sd: CxVec, ig: Vec, nig: Vec, nll: int,
           nslcap: int, nodal_capacity_sign: float, capacity_nodes_idx: IntVec, npq: int,
           pv: Vec, f_nd_dc: Vec, t_nd_dc: Vec, fdc: Vec, tdc: Vec, Pf_nondisp: Vec, k_m: Vec, k_tau: Vec, Vm_max: Vec,
           Sg_undis: CxVec, slack: Vec, acopf_mode: AcOpfMode) -> Tuple[Vec, Vec]:
    """
    Calculates the equality constraints at the current state (given by x)
    :param x: State vector
    :param Ybus: Bus admittance matrix
    :param Yf: From admittance matrix
    :param Cg: Generators connectivity matrix
    :param Sd: Loads vector
    :param ig: indices of dispatchable gens
    :param nig: indices of non dispatchable gens
    :param nll: Number of monitored lines
    :param nslcap:
    :param nodal_capacity_sign:
    :param capacity_nodes_idx:
    :param npq: Number of pq buses
    :param pv: Index of PV buses
    :param f_nd_dc: Index of 'from' buses of non dispatchable DC links
    :param t_nd_dc: Index of 'to' buses of non dispatchable DC links
    :param fdc: Index of 'from' buses of dispatchable DC links
    :param tdc: Index of 'to' buses of dispatchable DC links
    :param Pf_nondisp:
    :param k_m: Index of module controlled transformers
    :param k_tau: Index of phase controlled transformers
    :param Vm_max: Maximum bound for voltage
    :param Sg_undis: undispatchable complex power
    :param slack: Index of slack buses
    :param acopf_mode:
    :return: Vector with the value of each equality constraint G = [g1(x), ... gn(x)] s.t. gi(x) = 0.
             It also returns the value of the power injections S
    """
    M, N = Yf.shape
    Ng = len(ig)
    ntapm = len(k_m)
    ntapt = len(k_tau)
    ndc = len(fdc)

    va, vm, Pg_dis, Qg_dis, sl_sf, sl_st, sl_vmax, sl_vmin, slcap, _, _, Pfdc = x2var(x, nVa=N, nVm=N, nPg=Ng, nQg=Ng,
                                                                                      npq=npq, M=nll, ntapm=ntapm,
                                                                                      ntapt=ntapt, ndc=ndc,
                                                                                      nslcap=nslcap,
                                                                                      acopf_mode=acopf_mode)

    V = vm * np.exp(1j * va)
    S = V * np.conj(Ybus @ V)
    S_dispatch = Cg[:, ig] @ (Pg_dis + 1j * Qg_dis)  # Variable generation
    S_undispatch = Cg[:, nig] @ Sg_undis  # Fixed generation
    dS = S + Sd - S_dispatch - S_undispatch  # Nodal power balance
    if nslcap != 0:
        dS[capacity_nodes_idx] -= slcap  # Nodal capacity slack generator addition

    for link in range(len(Pfdc)):
        dS[fdc[link]] += Pfdc[link]  # Variable DC links. Lossless model (Pdc_From = Pdc_To)
        dS[tdc[link]] -= Pfdc[link]
    for nd_link in range(len(Pf_nondisp)):
        dS[f_nd_dc[nd_link]] += Pf_nondisp[nd_link]  # Fixed DC links
        dS[t_nd_dc[nd_link]] -= Pf_nondisp[nd_link]

    gval = np.r_[dS.real, dS.imag, va[slack], vm[pv] - Vm_max[pv]]

    return gval, S


def eval_h(x: Vec, Yf: csc_matrix, Yt: csc_matrix, from_idx: Vec, to_idx: Vec, nslcap: int,
           pq: Vec, k_m: Vec, k_tau: Vec,
           Vm_max: Vec, Vm_min: Vec, Pg_max: Vec, Pg_min: Vec, Qg_max: Vec, Qg_min: Vec, tapm_max: Vec,
           tapm_min: Vec, tapt_max: Vec, tapt_min: Vec, Pdcmax: Vec, rates: Vec, il: Vec, ig: Vec,
           tanmax: Vec, ctQ: bool, acopf_mode: AcOpfMode) -> Tuple[Vec, CxVec, CxVec]:
    """
    Calculates the inequality constraints at the current state (given by x)
    :param x: State vector
    :param Yf: From admittance matrix
    :param Yt: To admittance matrix
    :param from_idx: Vector with the indices of the 'from' buses for each line
    :param to_idx: Vector with the indices of the 'from' buses for each line
    :param nslcap:
    :param pq: Index of PQ buses
    :param k_m: Index of module controlled transformers
    :param k_tau: Index of phase controlles transformers
    :param Vm_max: upper bound for voltage module per bus
    :param Vm_min: lower bound for voltage module per bus
    :param Pg_max: upper bound for active power generation per generator
    :param Pg_min: lower bound for active power generation per generator
    :param Qg_max: upper bound for reactive power generation per generator
    :param Qg_min: lower bound for reactive power generation per generator
    :param tapm_max: Upper bound for tap module per transformer
    :param tapm_min: Lower bound for tap module per transformer
    :param tapt_max: Upper bound for tap phase per transformer
    :param tapt_min: Lower bound for tap phase per transformer
    :param Pdcmax: Bound for power transmission in a DC link
    :param rates: Rates for branch power at each line
    :param il: Index of monitored lines
    :param ig: Index of dispatchable generators
    :param tanmax: Maximum value of tan(phi), where phi is the angle of the complex generation, for each generator
    :param ctQ: Boolean indicating if limits to reactive power generation realted to active generation apply
    :param acopf_mode: AcOpfMode
    :return: Vector with the value of each inequality constraint
             H = [h1(x), ... hn(x)] s.t. hi(x) <= 0
             and the calculated from and to branch powers.
    """

    M, N = Yf.shape
    Ng = len(ig)
    ntapm = len(k_m)
    ntapt = len(k_tau)
    ndc = len(Pdcmax)
    npq = len(pq)
    nll = len(il)

    va, vm, Pg, Qg, sl_sf, sl_st, sl_vmax, sl_vmin, slcap, tapm, tapt, Pfdc = x2var(x, nVa=N, nVm=N, nPg=Ng, nQg=Ng,
                                                                                    npq=npq, M=nll, ntapm=ntapm,
                                                                                    ntapt=ntapt, ndc=ndc, nslcap=nslcap,
                                                                                    acopf_mode=acopf_mode)

    V = vm * np.exp(1j * va)
    Sf = V[from_idx[il]] * np.conj(Yf[il, :] @ V)
    St = V[to_idx[il]] * np.conj(Yt[il, :] @ V)

    Sftot = V[from_idx] * np.conj(Yf @ V)
    Sttot = V[to_idx] * np.conj(Yt @ V)

    Sf2 = np.conj(Sf) * Sf
    St2 = np.conj(St) * St
    rates2 = np.power(rates[il], 2.0)

    if acopf_mode == AcOpfMode.ACOPFslacks:
        hval = np.r_[
            Sf2.real - rates2 - sl_sf,  # rates "lower limit"
            St2.real - rates2 - sl_st,  # rates "upper limit"
            vm[pq] - Vm_max[pq] - sl_vmax,  # voltage module upper limit
            Pg - Pg_max[ig],  # generator P upper limits
            Qg - Qg_max[ig],  # generator Q upper limits
            Vm_min[pq] - vm[pq] - sl_vmin,  # voltage module lower limit
            Pg_min[ig] - Pg,  # generator P lower limits
            Qg_min[ig] - Qg,  # generation Q lower limits
            - sl_sf,  # Slack variable for Sf >0
            - sl_st,  # Slack variable for St >0
            - sl_vmax,  # Slack variable for Vmax >0
            - sl_vmin,  # Slack variable for Vmin >0
            tapm - tapm_max,  # Tap module upper bound
            tapm_min - tapm,  # Tap module lower bound
            tapt - tapt_max,  # Tap module lower bound
            tapt_min - tapt  # Tap phase lower bound
        ]
    else:
        hval = np.r_[
            Sf2.real - rates2,  # rates "lower limit"
            St2.real - rates2,  # rates "upper limit"
            vm[pq] - Vm_max[pq],  # voltage module upper limit
            Pg - Pg_max[ig],  # generator P upper limits
            Qg - Qg_max[ig],  # generator Q upper limits
            Vm_min[pq] - vm[pq],  # voltage module lower limit
            Pg_min[ig] - Pg,  # generator P lower limits
            Qg_min[ig] - Qg,  # generation Q lower limits
            tapm - tapm_max,  # Tap module upper bound
            tapm_min - tapm,  # Tap module lower bound
            tapt - tapt_max,  # Tap module lower bound
            tapt_min - tapt  # Tap phase lower bound
        ]

    if ctQ:  # if reactive power control...
        hval = np.r_[hval, np.power(Qg, 2.0) - np.power(tanmax, 2.0) * np.power(Pg, 2.0)]

    if ndc != 0:
        hval = np.r_[hval, Pfdc - Pdcmax, - Pdcmax - Pfdc]

    return hval, Sftot, Sttot


def jacobians_and_hessians(x: Vec, c1: Vec, c2: Vec, c_s: Vec, c_v: Vec, Cg: csc_matrix, Cf: csc, Ct: csc,
                           Yf: csc_matrix, Yt: csc_matrix, Ybus: csc_matrix, Sbase: float, mon_br_idx: IntVec, ig: IntVec,
                           slack: Vec, nslcap: int, nodal_capacity_sign: float, capacity_nodes_idx: IntVec, pq: IntVec,
                           pv: IntVec, tanmax: Vec, alltapm: Vec, alltapt: Vec, F_hvdc: IntVec, T_hvdc: IntVec,
                           k_m: IntVec, k_tau: IntVec, mu, lmbda, R: Vec, X: Vec, F: IntVec, T: IntVec,
                           ctQ: bool, acopf_mode: AcOpfMode, compute_jac: bool,
                           compute_hess: bool) -> Tuple[Vec, csc, csc, csc, csc, csc, Vec]:
    """
    Calculates the jacobians and hessians of the objective function and the equality and inequality constraints
    at the current state given by x
    :param x: State vector
    :param c1: Linear cost of each generator
    :param c2: Quadratic cost of each generator
    :param c_s: Cost of overloading each line
    :param c_v: Cost of over or undervoltage for each bus
    :param Cg: Generator connectivity matrix
    :param Cf: From connectivity matrix
    :param Ct:To connectivity matrix
    :param Yf: From admittance matrix
    :param Yt: To admittance matrix
    :param Ybus: Bus admittance matrix
    :param Sbase: Base power
    :param mon_br_idx: Index of monitored branches
    :param ig: Index of dispatchable generators
    :param slack: Index of slack buses
    :param nslcap:
    :param nodal_capacity_sign:
    :param capacity_nodes_idx:
    :param pq: Index of PQ buses
    :param pv: Index of PV buses
    :param tanmax: Maximum value of tan(phi), where phi is the angle of the complex generation, for each generator
    :param alltapm: value of all the tap modules, including the non controlled ones
    :param alltapt: value of all the tap phases, including the non controlled ones
    :param F_hvdc: Index of the 'from' buses for the dispatchable DC links
    :param T_hvdc: Index of the 'to' buses for the dispatchable DC links
    :param k_m: Index of the module controlled transformers
    :param k_tau: Index of the phase controlled transformers
    :param mu: Vector of mu multipliers
    :param lmbda: Vector of lambda multipliers
    :param R: Line Resistance
    :param X: Line inductance
    :param F: Index of the 'form' bus for each line
    :param T: Index of the 'to' bus for each line
    :param ctQ: Boolean that indicates if the Reactive control applies
    :param acopf_mode: AcOpfMode
    :param compute_jac: Boolean that indicates if the Jacobians have to be calculated
    :param compute_hess: Boolean that indicates if the Hessians have to be calculated
    :return: Jacobians and hessians matrices for the objective function and the equality and inequality constraints
    """
    Mm, N = Yf.shape
    M = len(mon_br_idx)
    Ng = len(ig)
    NV = len(x)
    ntapm = len(k_m)
    ntapt = len(k_tau)
    ndc = len(F_hvdc)
    npq = len(pq)

    if ctQ:  # if reactive power control...
        nqct = Ng
    else:
        nqct = 0

    va, vm, Pg, Qg, sl_sf, sl_st, sl_vmax, sl_vmin, slcap, tapm, tapt, Pfdc = x2var(x, nVa=N, nVm=N, nPg=Ng, nQg=Ng,
                                                                                    npq=npq, M=M, ntapm=ntapm,
                                                                                    ntapt=ntapt, ndc=ndc, nslcap=nslcap,
                                                                                    acopf_mode=acopf_mode)

    if acopf_mode == AcOpfMode.ACOPFslacks:
        nsl = 2 * npq + 2 * M  # Number of slacks
    else:
        nsl = 0

    npfvar = 2 * N + 2 * Ng  # Number of variables of the typical power flow (V, th, P, Q). Used to ease readability

    V = vm * np.exp(1j * va)
    Vmat = diags(V)
    vm_inv = diags(1 / vm)
    E = Vmat @ vm_inv
    Ibus = Ybus @ V
    IbusCJmat = diags(np.conj(Ibus))
    alltapm[k_m] = tapm  # Update vector of all tap modules with the new modules for controlled transformers
    alltapt[k_tau] = tapt  # Update vector of all tap phases with the new phases for controlled transformers

    if compute_jac:

        # OBJECTIVE FUNCTION GRAD --------------------------------------------------------------------------------------
        ts_fx = timeit.default_timer()
        fx = np.zeros(NV)
        if nslcap == 0:
            fx[2 * N: 2 * N + Ng] = (2 * c2 * Pg * (Sbase * Sbase) + c1 * Sbase) * 1e-4

            if acopf_mode == AcOpfMode.ACOPFslacks:
                fx[npfvar: npfvar + M] = c_s
                fx[npfvar + M: npfvar + 2 * M] = c_s
                fx[npfvar + 2 * M: npfvar + 2 * M + npq] = c_v
                fx[npfvar + 2 * M + npq: npfvar + 2 * M + 2 * npq] = c_v
        else:
            fx[npfvar + nsl: npfvar + nsl + nslcap] = nodal_capacity_sign

        te_fx = timeit.default_timer()
        # EQUALITY CONSTRAINTS GRAD ------------------------------------------------------------------------------------
        """
        The following comments illustrate the shapes of the equality constraints gradients:
        Gx = 
            NV
        +---------+
        | GS.real | N 
        +---------+
        | GS.imag | N 
        +---------+
        | GTH     | nslack
        +---------+
        | Gvm     | npv
        +---------+
        
        where Gx has shape (N + N + nslack + npv, N + N + Ng + Ng + nsl + ntapm + ntapt + ndc), where nslack is
        the number of slack buses, and nsl the number of slack variables.
        Each submatrix is composed as:
        
        GS = 
            N     N      Ng     Ng      nsl     ntapm    ntapt    ndc
        +------+------+------+------+---------+--------+--------+------+
        | GSva | GSvm | GSpg | GSqg | GSslack | GStapm | GStapt | GSdc | N
        +------+------+------+------+---------+--------+--------+------+
        
        GTH = 
           N      N    Ng    Ng    nsl  ntapm ntapt  ndc
        +------+-----+-----+-----+-----+-----+-----+-----+
        | GTHx |  0  |  0  |  0  |  0  |  0  |  0  |  0  |
        +------+-----+-----+-----+-----+-----+-----+-----+
        
        Gvm = 
        
           N     N     Ng    Ng    nsl  ntapm ntapt  ndc
        +-----+------+-----+-----+-----+-----+-----+-----+
        |  0  | Gvmx |  0  |  0  |  0  |  0  |  0  |  0  |
        +-----+------+-----+-----+-----+-----+-----+-----+
     
        """

        ts_gx = timeit.default_timer()

        Vva = 1j * Vmat

        GSvm = Vmat @ (IbusCJmat + np.conj(Ybus) @ np.conj(Vmat)) @ vm_inv  # N x N matrix
        GSva = Vva @ (IbusCJmat - np.conj(Ybus) @ np.conj(Vmat))
        GSpg = -Cg[:, ig]
        GSqg = -1j * Cg[:, ig]

        GTH = lil_matrix((len(slack), NV))
        for i, ss in enumerate(slack):
            GTH[i, ss] = 1.

        Gvm = lil_matrix((len(pv), NV))
        for i, ss in enumerate(pv):
            Gvm[i, N + ss] = 1.

        (dSbusdm, dSfdm, dStdm,
         dSbusdt, dSfdt, dStdt) = compute_branch_power_derivatives(alltapm, alltapt, V, k_m, k_tau, Cf, Ct, F, T, R, X)

        if ntapm > 0:
            Gtapm = dSbusdm.copy()
        else:
            Gtapm = lil_matrix((N, ntapm), dtype=complex)

        if ntapt > 0:
            Gtapt = dSbusdt.copy()
        else:
            Gtapt = lil_matrix((N, ntapt), dtype=complex)

        GSpfdc = lil_matrix((N, ndc), dtype=complex)
        for k_link in range(ndc):
            GSpfdc[F_hvdc[k_link], k_link] = 1.0  # TODO: check that this is correct
            GSpfdc[T_hvdc[k_link], k_link] = -1.0  # TODO: check that this is correct

        Gslack = lil_matrix((N, nsl), dtype=complex)

        Gslcap = lil_matrix((N, nslcap), dtype=complex)

        if nslcap != 0:
            for idslcap, capbus in enumerate(capacity_nodes_idx):
                Gslcap[capbus, idslcap] = -1

        GS = sp.hstack([GSva, GSvm, GSpg, GSqg, Gslack, Gslcap, Gtapm, Gtapt, GSpfdc])

        Gx = sp.vstack([GS.real, GS.imag, GTH, Gvm]).tocsc()

        te_gx = timeit.default_timer()

        # INEQUALITY CONSTRAINTS GRAD ----------------------------------------------------------------------------------

        """
        The following comments illustrate the shapes of the equality constraints gradients:
        
        Hx =
            NV
        +---------+
        | HSf     | M
        +---------+
        | HSt     | M
        +---------+
        | Hvu     | N
        +---------+
        | Hpu     | Ng
        +---------+
        | Hqu     | Ng
        +---------+
        | Hvl     | N
        +---------+
        | Hpl     | Ng
        +---------+
        | Hql     | Ng
        +---------+
        | Hslsf   | M
        +---------+
        | Hslst   | M
        +---------+
        | Hslvmax | npq
        +---------+
        | Hslvmin | npq
        +---------+
        | Htapmu  | ntapm
        +---------+
        | Htapml  | ntapm
        +---------+
        | Htaptu  | ntapt
        +---------+
        | Htaptl  | ntapt
        +---------+
        | Hqmax   | Ng (if ctQ==True), 0 else
        +---------+
        | Hdcu    | ndc
        +---------+
        | Hdcl    | ndc
        +---------+
        """
        ts_hx = timeit.default_timer()

        Vfmat = diags(Cf[mon_br_idx, :] @ V)
        Vtmat = diags(Ct[mon_br_idx, :] @ V)

        IfCJmat = np.conj(diags(Yf[mon_br_idx, :] @ V))
        ItCJmat = np.conj(diags(Yt[mon_br_idx, :] @ V))
        Sf = Vfmat @ np.conj(Yf[mon_br_idx, :] @ V)
        St = Vtmat @ np.conj(Yt[mon_br_idx, :] @ V)

        allSf = diags(Cf @ V) @ np.conj(Yf @ V)
        allSt = diags(Ct @ V) @ np.conj(Yt @ V)

        Sfmat = diags(Sf)
        Stmat = diags(St)

        Sfvm = (IfCJmat @ Cf[mon_br_idx, :] @ E + Vfmat @ np.conj(Yf[mon_br_idx, :]) @ np.conj(E))
        Stvm = (ItCJmat @ Ct[mon_br_idx, :] @ E + Vtmat @ np.conj(Yt[mon_br_idx, :]) @ np.conj(E))

        Sfva = (1j * (IfCJmat @ Cf[mon_br_idx, :] @ Vmat - Vfmat @ np.conj(Yf[mon_br_idx, :]) @ np.conj(Vmat)))
        Stva = (1j * (ItCJmat @ Ct[mon_br_idx, :] @ Vmat - Vtmat @ np.conj(Yt[mon_br_idx, :]) @ np.conj(Vmat)))

        Hpu = sp.hstack([lil_matrix((Ng, 2 * N)), diags(np.ones(Ng)), lil_matrix((Ng, NV - 2 * N - Ng))])
        Hpl = sp.hstack([lil_matrix((Ng, 2 * N)), diags(- np.ones(Ng)), lil_matrix((Ng, NV - 2 * N - Ng))])
        Hqu = sp.hstack([lil_matrix((Ng, 2 * N + Ng)), diags(np.ones(Ng)), lil_matrix((Ng, NV - 2 * N - 2 * Ng))])
        Hql = sp.hstack([lil_matrix((Ng, 2 * N + Ng)), diags(- np.ones(Ng)), lil_matrix((Ng, NV - 2 * N - 2 * Ng))])

        if acopf_mode == AcOpfMode.ACOPFslacks:

            Hvu = sp.hstack([lil_matrix((npq, N)), diags(np.ones(N))[pq, :], lil_matrix((npq, 2 * Ng + 2 * M)),
                             diags(- np.ones(npq)), lil_matrix((npq, npq + nslcap + ntapm + ntapt + ndc))])

            Hvl = sp.hstack([lil_matrix((npq, N)), diags(- np.ones(N))[pq, :], lil_matrix((npq, 2 * Ng + 2 * M + npq)),
                             diags(- np.ones(npq)), lil_matrix((npq, nslcap + ntapm + ntapt + ndc))])

            Hslsf = sp.hstack([lil_matrix((M, npfvar)), diags(- np.ones(M)),
                               lil_matrix((M, M + 2 * npq + nslcap + ntapm + ntapt + ndc))])

            Hslst = sp.hstack([lil_matrix((M, npfvar + M)), diags(- np.ones(M)),
                               lil_matrix((M, 2 * npq + nslcap + ntapm + ntapt + ndc))])

            Hslvmax = sp.hstack([lil_matrix((npq, npfvar + 2 * M)), diags(- np.ones(npq)),
                                 lil_matrix((npq, npq + nslcap + ntapm + ntapt + ndc))])

            Hslvmin = sp.hstack([lil_matrix((npq, npfvar + 2 * M + npq)), diags(- np.ones(npq)),
                                 lil_matrix((npq, nslcap + ntapm + ntapt + ndc))])

        else:
            Hvu = sp.hstack([lil_matrix((npq, N)), diags(np.ones(npq)), lil_matrix((npq, NV - 2 * N))])
            Hvl = sp.hstack([lil_matrix((npq, N)), diags(- np.ones(npq)), lil_matrix((npq, NV - 2 * N))])
            Hslsf = lil_matrix((0, NV))
            Hslst = lil_matrix((0, NV))
            Hslvmax = lil_matrix((0, NV))
            Hslvmin = lil_matrix((0, NV))

        if (ntapm + ntapt) != 0:

            Sftapm = dSfdm[mon_br_idx, :].copy()
            Sftapt = dSfdt[mon_br_idx, :].copy()
            Sttapm = dStdm[mon_br_idx, :].copy()
            Sttapt = dStdt[mon_br_idx, :].copy()

            SfX = sp.hstack([Sfva, Sfvm, lil_matrix((M, 2 * Ng + nsl + nslcap)), Sftapm, Sftapt, lil_matrix((M, ndc))])
            StX = sp.hstack([Stva, Stvm, lil_matrix((M, 2 * Ng + nsl + nslcap)), Sttapm, Sttapt, lil_matrix((M, ndc))])

            if acopf_mode == AcOpfMode.ACOPFslacks:
                HSf = 2 * (Sfmat.real @ SfX.real + Sfmat.imag @ SfX.imag) + Hslsf
                HSt = 2 * (Stmat.real @ StX.real + Stmat.imag @ StX.imag) + Hslst
            else:
                HSf = 2 * (Sfmat.real @ SfX.real + Sfmat.imag @ SfX.imag)
                HSt = 2 * (Stmat.real @ StX.real + Stmat.imag @ StX.imag)

            if ntapm != 0:
                Htapmu = sp.hstack([lil_matrix((ntapm, npfvar + nsl + nslcap)), diags(np.ones(ntapm)),
                                    lil_matrix((ntapm, ntapt + ndc))])

                Htapml = sp.hstack([lil_matrix((ntapm, npfvar + nsl + nslcap)), diags(- np.ones(ntapm)),
                                    lil_matrix((ntapm, ntapt + ndc))])

            else:
                Htapmu = lil_matrix((0, NV))
                Htapml = lil_matrix((0, NV))

            if ntapt != 0:
                Htaptu = sp.hstack([lil_matrix((ntapt, npfvar + nsl + nslcap + ntapm)), diags(np.ones(ntapt)),
                                    lil_matrix((ntapt, ndc))])
                Htaptl = sp.hstack([lil_matrix((ntapt, npfvar + nsl + nslcap + ntapm)), diags(- np.ones(ntapt)),
                                    lil_matrix((ntapt, ndc))])

            else:
                Htaptu = lil_matrix((0, NV))
                Htaptl = lil_matrix((0, NV))

        else:
            Sftapm = lil_matrix((M, ntapm))
            Sttapm = lil_matrix((M, ntapm))
            Sftapt = lil_matrix((M, ntapt))
            Sttapt = lil_matrix((M, ntapt))
            Htapmu = lil_matrix((ntapm, NV))
            Htapml = lil_matrix((ntapm, NV))
            Htaptu = lil_matrix((ntapt, NV))
            Htaptl = lil_matrix((ntapt, NV))

            SfX = sp.hstack([Sfva, Sfvm, lil_matrix((M, 2 * Ng + nsl + nslcap + ndc))])
            StX = sp.hstack([Stva, Stvm, lil_matrix((M, 2 * Ng + nsl + nslcap + ndc))])

            if acopf_mode == AcOpfMode.ACOPFslacks:
                HSf = 2 * (Sfmat.real @ SfX.real + Sfmat.imag @ SfX.imag) + Hslsf
                HSt = 2 * (Stmat.real @ StX.real + Stmat.imag @ StX.imag) + Hslst
            else:
                HSf = 2 * (Sfmat.real @ SfX.real + Sfmat.imag @ SfX.imag)
                HSt = 2 * (Stmat.real @ StX.real + Stmat.imag @ StX.imag)

        if ctQ:  # if reactive power control...
            # tanmax curves (simplified capability curves of generators)
            Hqmaxp = - 2 * np.power(tanmax, 2) * Pg
            Hqmaxq = 2 * Qg

            Hqmax = sp.hstack([lil_matrix((nqct, 2 * N)), diags(Hqmaxp), diags(Hqmaxq),
                               lil_matrix((nqct, nsl + nslcap + ntapm + ntapt + ndc))])
        else:
            Hqmax = lil_matrix((nqct, NV))

        Hdcu = sp.hstack([lil_matrix((ndc, NV - ndc)), diags(np.ones(ndc))])
        Hdcl = sp.hstack([lil_matrix((ndc, NV - ndc)), diags(- np.ones(ndc))])

        Hx = sp.vstack([HSf, HSt, Hvu, Hpu, Hqu, Hvl, Hpl, Hql, Hslsf, Hslst, Hslvmax,
                        Hslvmin, Htapmu, Htapml, Htaptu, Htaptl, Hqmax, Hdcu, Hdcl])

        Hx = Hx.tocsc()
        te_hx = timeit.default_timer()
    else:
        # Returns empty structures
        fx = np.zeros(NV)
        Gx = csc((NV, N))
        Hx = csc((NV, 2 * M + 2 * N + 4 * Ng + nsl + nqct + 2 * (ntapm + ntapt) + 2 * ndc))

        te_fx = 0
        ts_fx = 0
        te_gx = 0
        ts_gx = 0
        te_hx = 0
        ts_hx = 0

        allSf = lil_matrix((M, 1))
        allSt = lil_matrix((M, 1))
        Sfmat = lil_matrix((M, M))
        Stmat = lil_matrix((M, M))
        Sfva = lil_matrix((M, N))
        Stva = lil_matrix((M, N))
        Sfvm = lil_matrix((M, N))
        Stvm = lil_matrix((M, N))
        Sftapm = lil_matrix((M, ntapm))
        Sttapm = lil_matrix((M, ntapm))
        Sftapt = lil_matrix((M, ntapt))
        Sttapt = lil_matrix((M, ntapt))

    # HESSIANS ---------------------------------------------------------------------------------------------------------

    if compute_hess:

        assert compute_jac  # we must have the jacobian values to get into here

        # OBJECTIVE FUNCTION HESS --------------------------------------------------------------------------------------
        ts_fxx = timeit.default_timer()
        if nslcap == 0:
            fxx = diags((np.r_[
                np.zeros(2 * N),
                2 * c2 * (Sbase * Sbase),
                np.zeros(Ng + nsl + nslcap + ntapm + ntapt + ndc)
            ]) * 1e-4).tocsc()
        else:
            fxx = csc((NV, NV))

        te_fxx = timeit.default_timer()
        # EQUALITY CONSTRAINTS HESS ------------------------------------------------------------------------------------
        '''
        The following matrix represents the structure of the hessian matrix for the equality constraints
            
                     N         N         Ng        Ng       nsl       ntapm       ntapt       ndc
                +---------+---------+---------+---------+---------+-----------+-----------+----------+
           N    |  Gvava  |  Gvavm  |  Gvapg  |  Gvaqg  |  Gvasl  |  Gvatapm  |  Gvatapt  |  Gvapdc  |
                +---------+---------+---------+---------+---------+-----------+-----------+----------+
           N    |  Gvmva  |  Gvmvm  |  Gvmpg  |  Gvmqg  |  Gvmsl  |  Gvmtapm  |  Gvmtapt  |  Gvmpdc  |
                +---------+---------+---------+---------+---------+-----------+-----------+----------+
           Ng   |  Gpgva  |  Gpgvm  |  Gpgpg  |  Gpgqg  |  Gpgsl  |  Gpgtapm  |  Gpgtapt  |  Gpgpdc  |
                +---------+---------+---------+---------+---------+-----------+-----------+----------+
           Ng   |  Gqgva  |  Gqgvm  |  Gqgpg  |  Gqgqg  |  Gqgsl  |  Gqgtapm  |  Gqgtapt  |  Gqgpdc  |
                +---------+---------+---------+---------+---------+-----------+-----------+----------+
           nsl  |  Gslva  |  Gslvm  |  Gslpg  |  Gslqg  |  Gslsl  |  Gsltapm  |  Gsltapt  |  Gslpdc  |
                +---------+---------+---------+---------+---------+-----------+-----------+----------+
          ntapm | Gtapmva | Gtapmvm | Gtapmpg | Gtapmqg | Gtapmsl | Gtapmtapm | Gtapmtapt | Gtapmpdc |
                +---------+---------+---------+---------+---------+-----------+-----------+----------+
          ntapt | Gtaptva | Gtaptvm | Gtaptpg | Gtaptqg | Gtaptsl | Gtapttapm | Gtapttapt | Gtaptpdc |
                +---------+---------+---------+---------+---------+-----------+-----------+----------+
           ndc  | Gpdcva  | Gpdcvm  | Gpdcpg  | Gpdcqg  | Gpdcsl  | Gpdctapm  | Gpdctapt  | Gpdcpdc  |
                +---------+---------+---------+---------+---------+-----------+-----------+----------+
            
        
        '''
        ts_gxx = timeit.default_timer()
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

        (GSdmdm, dSfdmdm, dStdmdm,
         GSdmdvm, dSfdmdvm, dStdmdvm,
         GSdmdva, dSfdmdva, dStdmdva,
         GSdmdt, dSfdmdt, dStdmdt,
         GSdtdt, dSfdtdt, dStdtdt,
         GSdtdvm, dSfdtdvm, dStdtdvm,
         GSdtdva, dSfdtdva, dStdtdva) = compute_branch_power_second_derivatives(alltapm, alltapt, vm, va, k_m,
                                                                                k_tau, mon_br_idx, R, X, F, T,
                                                                                lmbda[0: 2 * N], mu[0: 2 * M],
                                                                                allSf, allSt)

        if ntapm + ntapt != 0:
            G1 = sp.hstack([Gaa, Gav, lil_matrix((N, 2 * Ng + nsl + nslcap)), GSdmdva, GSdtdva, lil_matrix((N, ndc))])
            G2 = sp.hstack([Gva, Gvv, lil_matrix((N, 2 * Ng + nsl + nslcap)), GSdmdvm, GSdtdvm, lil_matrix((N, ndc))])
            G3 = sp.hstack([GSdmdva.T, GSdmdvm.T, lil_matrix((ntapm, 2 * Ng + nsl + nslcap)),
                            GSdmdm, GSdmdt.T, lil_matrix((ntapm, ndc))])
            G4 = sp.hstack([GSdtdva.T, GSdtdvm.T, lil_matrix((ntapt, 2 * Ng + nsl + nslcap)),
                            GSdmdt, GSdtdt, lil_matrix((ntapt, ndc))])

            Gxx = sp.vstack([G1, G2, lil_matrix((2 * Ng + nsl + nslcap, NV)), G3, G4, lil_matrix((ndc, NV))]).tocsc()

        else:
            G1 = sp.hstack([Gaa, Gav, lil_matrix((N, 2 * Ng + nsl + nslcap + ndc))])
            G2 = sp.hstack([Gva, Gvv, lil_matrix((N, 2 * Ng + nsl + nslcap + ndc))])
            Gxx = sp.vstack([G1, G2, lil_matrix((2 * Ng + nsl + nslcap + ndc, npfvar + nsl + nslcap + ndc))]).tocsc()

        te_gxx = timeit.default_timer()
        # INEQUALITY CONSTRAINTS HESS ----------------------------------------------------------------------------------
        '''
        The following matrix represents the structure of the hessian matrix for the inequality constraints

                    N         N         Ng        Ng       nsl       ntapm       ntapt       ndc
               +---------+---------+---------+---------+---------+-----------+-----------+----------+
          N    |  Hvava  |  Hvavm  |  Hvapg  |  Hvaqg  |  Hvasl  |  Hvatapm  |  Hvatapt  |  Hvapdc  |
               +---------+---------+---------+---------+---------+-----------+-----------+----------+
          N    |  Hvmva  |  Hvmvm  |  Hvmpg  |  Hvmqg  |  Hvmsl  |  Hvmtapm  |  Hvmtapt  |  Hvmpdc  |
               +---------+---------+---------+---------+---------+-----------+-----------+----------+
          Ng   |  Hpgva  |  Hpgvm  |  Hpgpg  |  Hpgqg  |  Hpgsl  |  Hpgtapm  |  Hpgtapt  |  Hpgpdc  |
               +---------+---------+---------+---------+---------+-----------+-----------+----------+
          Ng   |  Hqgva  |  Hqgvm  |  Hqgpg  |  Hqgqg  |  Hqgsl  |  Hqgtapm  |  Hqgtapt  |  Hqgpdc  |
               +---------+---------+---------+---------+---------+-----------+-----------+----------+
          nsl  |  Hslva  |  Hslvm  |  Hslpg  |  Hslqg  |  Hslsl  |  Hsltapm  |  Hsltapt  |  Hslpdc  |
               +---------+---------+---------+---------+---------+-----------+-----------+----------+
         ntapm | Htapmva | Htapmvm | Htapmpg | Htapmqg | Htapmsl | Htapmtapm | Htapmtapt | Htapmpdc |
               +---------+---------+---------+---------+---------+-----------+-----------+----------+
         ntapt | Htaptva | Htaptvm | Htaptpg | Htaptqg | Htaptsl | Htapttapm | Htapttapt | Htaptpdc |
               +---------+---------+---------+---------+---------+-----------+-----------+----------+
          ndc  | Hpdcva  | Hpdcvm  | Hpdcpg  | Hpdcqg  | Hpdcsl  | Hpdctapm  | Hpdctapt  | Hpdcpdc  |
               +---------+---------+---------+---------+---------+-----------+-----------+----------+

           '''

        ts_hxx = timeit.default_timer()

        muf = mu[0: M]
        mut = mu[M: 2 * M]
        muf_mat = diags(muf)
        mut_mat = diags(mut)
        Smuf_mat = diags(Sfmat.conj() @ muf)
        Smut_mat = diags(Stmat.conj() @ mut)

        Af = np.conj(Yf[mon_br_idx, :]).T @ Smuf_mat @ Cf[mon_br_idx, :]
        Bf = np.conj(Vmat) @ Af @ Vmat
        Df = diags(Af @ V) @ np.conj(Vmat)
        Ef = diags(Af.T @ np.conj(V)) @ Vmat
        Ff = Bf + Bf.T
        Sfvava = Ff - Df - Ef
        Sfvmva = 1j * vm_inv @ (Bf - Bf.T - Df + Ef)
        Sfvavm = Sfvmva.T
        Sfvmvm = vm_inv @ Ff @ vm_inv

        if ctQ:  # using reactive power control
            Hqpgpg = diags(-2 * np.power(tanmax, 2) * mu[-Ng:])
            Hqqgqg = diags(np.array([2] * Ng) * mu[-Ng:])
        else:
            Hqpgpg = lil_matrix((Ng, Ng))
            Hqqgqg = lil_matrix((Ng, Ng))

        Hfvava = 2 * (Sfvava + Sfva.T @ muf_mat @ np.conj(Sfva)).real
        Hfvmva = 2 * (Sfvmva + Sfvm.T @ muf_mat @ np.conj(Sfva)).real
        Hfvavm = 2 * (Sfvavm + Sfva.T @ muf_mat @ np.conj(Sfvm)).real
        Hfvmvm = 2 * (Sfvmvm + Sfvm.T @ muf_mat @ np.conj(Sfvm)).real

        At = np.conj(Yt[mon_br_idx, :]).T @ Smut_mat @ Ct[mon_br_idx, :]
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
                            lil_matrix((N, 2 * Ng + nsl + nslcap)),
                            Hftapmva.T + Httapmva.T,
                            Hftaptva.T + Httaptva.T,
                            lil_matrix((N, ndc))])

            H2 = sp.hstack([Hfvmva + Htvmva,
                            Hfvmvm + Htvmvm,
                            lil_matrix((N, 2 * Ng + nsl + nslcap)),
                            Hftapmvm.T + Httapmvm.T,
                            Hftaptvm.T + Httaptvm.T,
                            lil_matrix((N, ndc))])

            H3 = sp.hstack([lil_matrix((Ng, 2 * N)), Hqpgpg, lil_matrix((Ng, Ng + nsl + nslcap + ntapm + ntapt + ndc))])

            H4 = sp.hstack([lil_matrix((Ng, 2 * N + Ng)), Hqqgqg, lil_matrix((Ng, nsl + nslcap + ntapm + ntapt + ndc))])

            H5 = sp.hstack([Hftapmva + Httapmva, Hftapmvm + Httapmvm, lil_matrix((ntapm, 2 * Ng + nsl + nslcap)),
                            Hftapmtapm + Httapmtapm, Hftapmtapt + Httapmtapt, lil_matrix((ntapm, ndc))])

            H6 = sp.hstack([Hftaptva + Httaptva,
                            Hftaptvm + Httaptvm,
                            lil_matrix((ntapt, 2 * Ng + nsl + nslcap)),
                            Hftapmtapt.T + Httapmtapt.T,
                            Hftapttapt + Httapttapt,
                            lil_matrix((ntapt, ndc))])

            Hxx = sp.vstack([H1, H2, H3, H4, lil_matrix((nsl + nslcap, NV)), H5, H6, lil_matrix((ndc, NV))]).tocsc()

        else:
            H1 = sp.hstack([Hfvava + Htvava, Hfvavm + Htvavm, lil_matrix((N, 2 * Ng + nsl + nslcap + ndc))])
            H2 = sp.hstack([Hfvmva + Htvmva, Hfvmvm + Htvmvm, lil_matrix((N, 2 * Ng + nsl + nslcap + ndc))])
            H3 = sp.hstack([lil_matrix((Ng, 2 * N)), Hqpgpg, lil_matrix((Ng, Ng + nsl + nslcap + ndc))])
            H4 = sp.hstack([lil_matrix((Ng, 2 * N + Ng)), Hqqgqg, lil_matrix((Ng, nsl + nslcap + ndc))])

            Hxx = sp.vstack([H1, H2, H3, H4, lil_matrix((nsl + nslcap + ndc, NV))]).tocsc()

        te_hxx = timeit.default_timer()
    else:
        # Return empty structures
        fxx = csc((NV, NV))
        Gxx = csc((NV, NV))
        Hxx = csc((NV, NV))
        ts_fxx = 0
        te_fxx = 0
        ts_gxx = 0
        te_gxx = 0
        ts_hxx = 0
        te_hxx = 0

    der_times = np.array([te_fx - ts_fx,
                          te_gx - ts_gx,
                          te_hx - ts_hx,
                          te_fxx - ts_fxx,
                          te_gxx - ts_gxx,
                          te_hxx - ts_hxx])

    return fx, Gx, Hx, fxx, Gxx, Hxx, der_times
