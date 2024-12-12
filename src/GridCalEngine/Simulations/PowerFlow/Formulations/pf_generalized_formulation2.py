# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import time
from typing import Tuple, List, Callable, Union
import numpy as np
import pandas as pd
import scipy as sp
from GridCalEngine.Topology.generalized_simulation_indices_new import GeneralizedSimulationIndices
from scipy.sparse import lil_matrix, csc_matrix, hstack, vstack, csr_matrix
from GridCalEngine.Topology.admittance_matrices import compute_admittances
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
import GridCalEngine.Simulations.Derivatives.csc_derivatives as deriv
from GridCalEngine.Utils.Sparse.csc2 import CSC, CxCSC, scipy_to_mat, mat_to_scipy
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import expand
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import compute_fx_error
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_formulation_template import PfFormulationTemplate
from GridCalEngine.enumerations import BusMode
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import (compute_zip_power, compute_power,
                                                                                   polar_to_rect, get_Sf, get_St)
from GridCalEngine.basic_structures import Vec, IntVec, CxVec, Logger


def recompute_controllable_power(V_f: CxVec,
                                 V_t: CxVec,
                                 R: Vec,
                                 X: Vec,
                                 G: Vec,
                                 B: Vec,
                                 tap_module: Vec,
                                 vtap_f: Vec,
                                 vtap_t: Vec,
                                 tap_angle: Vec) -> Tuple[Vec, Vec, Vec, Vec]:
    """
    Compute the complete admittance matrices for the general power flow methods (Newton-Raphson based)

    :param V_f: From voltages array
    :param V_t: To voltages array
    :param R: array of branch resistance (p.u.)
    :param X: array of branch reactance (p.u.)
    :param G: array of branch conductance (p.u.)
    :param B: array of branch susceptance (p.u.)
    :param k: array of converter values: 1 for regular Branches, sqrt(3) / 2 for VSC
    :param tap_module: array of tap modules (for all Branches, regardless of their type)
    :param vtap_f: array of virtual taps at the "from" side
    :param vtap_t: array of virtual taps at the "to" side
    :param tap_angle: array of tap angles (for all Branches, regardless of their type)
    :return: Pf, Qf, Pt, Qt
    """

    # form the admittance matrices
    ys = 1.0 / (R + 1.0j * X + 1e-20)  # series admittance
    bc2 = (G + 1j * B) / 2.0  # shunt admittance
    mp = tap_module

    Yff = (ys + bc2) / (mp * mp * vtap_f * vtap_f)
    Yft = -ys / (mp * np.exp(-1.0j * tap_angle) * vtap_f * vtap_t)
    Ytf = -ys / (mp * np.exp(1.0j * tap_angle) * vtap_t * vtap_f)
    Ytt = (ys + bc2) / (vtap_t * vtap_t)

    Sf: CxVec = V_f * np.conj(V_f * Yff) + V_f * np.conj(V_t * Yft)
    St: CxVec = V_t * np.conj(V_t * Ytt) + V_t * np.conj(V_f * Ytf)

    return Sf.real, Sf.imag, St.real, St.imag


def calc_autodiff_jacobian(func: Callable[[Vec], Vec], x: Vec, h=1e-8) -> csc_matrix:
    """
    Compute the Jacobian matrix of `func` at `x` using finite differences.

    :param func: function accepting a vector x and args, and returning either a vector or a
                 tuple where the first argument is a vector and the second.
    :param x: Point at which to evaluate the Jacobian (numpy array).
    :param h: Small step for finite difference.
    :return: Jacobian matrix as a CSC matrix.
    """
    nx = len(x)
    f0 = func(x)

    n_rows = len(f0)

    jac = lil_matrix((n_rows, nx))

    for j in range(nx):
        x_plus_h = np.copy(x)
        x_plus_h[j] += h
        f_plus_h = func(x_plus_h)
        row = (f_plus_h - f0) / h
        for i in range(n_rows):
            if row[i] != 0.0:
                jac[i, j] = row[i]

    return jac.tocsc()


class PfGeneralizedFormulation(PfFormulationTemplate):

    def __init__(self, V0: CxVec, S0: CxVec, I0: CxVec, Y0: CxVec,
                 Qmin: Vec, Qmax: Vec,
                 nc: NumericalCircuit,
                 options: PowerFlowOptions,
                 logger: Logger):
        """
        Constructor
        :param V0: Initial voltage solution
        :param S0: Set power injections
        :param I0: Set current injections
        :param Y0: Set admittance injections
        :param nc: NumericalCircuit
        :param options: PowerFlowOptions
        :param logger: Logger (modified in-place)
        """
        PfFormulationTemplate.__init__(self, V0=V0, options=options)

        self.nc: NumericalCircuit = nc

        self.logger: Logger = logger

        if self.options.verbose > 1:
            print("(pf_generalized_formulation.py) self.nc.passive_branch_data.nelm: ",
                  self.nc.passive_branch_data.nelm)
            print("(pf_generalized_formulation.py) self.nc.active_branch_data.nelm: ", self.nc.active_branch_data.nelm)
            print("(pf_generalized_formulation.py) self.nc.vsc_data.nelm: ", self.nc.vsc_data.nelm)

        # TODO: need to take into account every device eventually
        self.I0: CxVec = self.nc.load_data.get_current_injections_per_bus() / self.nc.Sbase
        self.Y0: CxVec = self.nc.load_data.get_admittance_injections_per_bus() / self.nc.Sbase
        self.S0: CxVec = self.nc.load_data.get_injections_per_bus() / self.nc.Sbase
        self.V0: CxVec = V0

        if self.options.verbose > 1:
            print(f"self.S0: {self.S0}")
            print(f"self.I0: {self.I0}")
            print(f"self.Y0: {self.Y0}")
            print(f"self.V0: {self.V0}")

        # QUESTION: is there a reason not to do this? I use this in var2x
        self.Sbus = compute_zip_power(self.S0, self.I0, self.Y0, self.Vm)
        self.Sf: CxVec = np.zeros(nc.active_branch_data.nelm + nc.nvsc + nc.nhvdc, dtype=np.complex128)
        self.St: CxVec = np.zeros(nc.active_branch_data.nelm + nc.nvsc + nc.nhvdc, dtype=np.complex128)
        # self.Sf: CxVec = np.zeros(nc.nbr, dtype=np.complex128)
        # self.St: CxVec = np.zeros(nc.nbr, dtype=np.complex128)

        self.Pzip = np.zeros(nc.nbus)
        self.Qzip = np.zeros(nc.nbus)
        self.Pf = np.real(self.Sf)
        self.Qf = np.imag(self.Sf)
        self.Pt = np.real(self.St)
        self.Qt = np.imag(self.St)

        if self.options.verbose > 1:
            print(f"self.Pbus: {self.Pzip}")
            print(f"self.Qbus: {self.Qzip}")
            print(f"self.Sf: {self.Sf}")
            print(f"self.Pf: {self.Pf}")
            print(f"self.Qf: {self.Qf}")
            print(f"self.St: {self.St}")
            print(f"self.Pt: {self.Pt}")
            print(f"self.Qt: {self.Qt}")

        self.bus_types = self.nc.bus_data.bus_types.copy()
        self.tap_module_control_mode = self.nc.active_branch_data.tap_module_control_mode.copy()
        self.tap_phase_control_mode = self.nc.active_branch_data.tap_phase_control_mode.copy()

        self.pq = np.array(0, dtype=int)
        self.pv = np.array(0, dtype=int)
        self.pqv = np.array(0, dtype=int)
        self.p = np.array(0, dtype=int)
        self.idx_conv = np.array(0, dtype=int)

        self.idx_dPf = np.array(0, dtype=int)
        self.idx_dQf = np.array(0, dtype=int)

        self.idx_dPt = np.array(0, dtype=int)
        self.idx_dQt = np.array(0, dtype=int)

        # Generalized indices
        start = time.perf_counter()
        self.indices = GeneralizedSimulationIndices(nc=self.nc, pf_options=options)
        end = time.perf_counter()
        execution_time = end - start
        print(f"Indices Time: {execution_time} seconds")
        self.controlled_idx = self.nc.active_branch_data.get_controlled_idx()
        self.fixed_idx = self.nc.active_branch_data.get_fixed_idx()
        self.hvdc_mode = self.indices.hvdc_mode

        # Bus indices
        self.i_u_vm = self.indices.i_u_vm
        self.i_u_va = self.indices.i_u_va
        self.i_k_p = self.indices.i_k_p
        self.i_k_q = self.indices.i_k_q

        # Controllable Branch Indices
        self.cbr_m = self.indices.cbr_m
        self.cbr_tau = self.indices.cbr_tau
        self.cbr = np.union1d(self.cbr_m, self.cbr_tau)
        self.k_cbr_pf = self.indices.k_cbr_pf
        self.k_cbr_pt = self.indices.k_cbr_pt
        self.k_cbr_qf = self.indices.k_cbr_qf
        self.k_cbr_qt = self.indices.k_cbr_qt

        # VSC Indices
        self.vsc = self.indices.vsc
        self.u_vsc_pf = self.indices.u_vsc_pf
        self.u_vsc_pt = self.indices.u_vsc_pt
        self.u_vsc_qt = self.indices.u_vsc_qt

        # HVDC Indices
        self.hvdc = self.indices.hvdc


        # Update setpoints
        self.Vm[self.indices.ck_vm] = self.indices.vm_setpoints
        self.Va[self.indices.ck_va] = self.indices.va_setpoints
        self.Pzip[self.indices.ck_pzip] = np.array(self.indices.pzip_setpoints) / nc.Sbase
        idx = np.where(nc.bus_data.bus_types == BusMode.Slack_tpe.value)[0]
        self.Pzip[idx] = self.Sbus[idx].real  # before we were grabbing the idx, seemed wrong to me
        self.Qzip[self.indices.ck_qzip] = np.array(self.indices.qzip_setpoints) / nc.Sbase
        self.Pf[self.indices.ck_pfa] = np.array(self.indices.pf_setpoints) / nc.Sbase
        self.Pt[self.indices.ck_pta] = np.array(self.indices.pt_setpoints) / nc.Sbase
        self.Qt[self.indices.ck_qta] = np.array(self.indices.qt_setpoints) / nc.Sbase

        self.m: Vec = np.ones(len(self.cbr_m))
        self.tau: Vec = np.zeros(len(self.cbr_tau))

        self.Ys: CxVec = self.nc.passive_branch_data.get_series_admittance()

        self.R = np.full(nc.nbr, 1e+20)
        self.X = np.full(nc.nbr, 1e+20)
        self.G = np.zeros(nc.nbr, dtype=float)
        self.B = np.zeros(nc.nbr, dtype=float)
        self.k = np.ones(nc.nbr, dtype=float)
        self.tap_module = np.ones(nc.nbr, dtype=float)
        self.tap_angle = np.zeros(nc.nbr, dtype=float)

        # fill the fixed indices with a small value
        self.R[self.fixed_idx] = nc.passive_branch_data.R[self.fixed_idx]
        self.X[self.fixed_idx] = nc.passive_branch_data.X[self.fixed_idx]
        self.G[self.fixed_idx] = nc.passive_branch_data.G[self.fixed_idx]
        self.B[self.fixed_idx] = nc.passive_branch_data.B[self.fixed_idx]
        self.tap_module[self.fixed_idx] = nc.active_branch_data.tap_module[self.fixed_idx]
        self.tap_angle[self.fixed_idx] = nc.active_branch_data.tap_angle[self.fixed_idx]

        self.adm = compute_admittances(
            R=self.R,
            X=self.X,
            G=self.G,
            B=self.B,
            k=self.k,
            tap_module=self.tap_module,
            vtap_f=self.nc.passive_branch_data.virtual_tap_f,
            vtap_t=self.nc.passive_branch_data.virtual_tap_t,
            tap_angle=self.tap_angle,
            Cf=self.nc.Cf,
            Ct=self.nc.Ct,
            Yshunt_bus=self.nc.Yshunt_from_devices,
            conn=self.nc.passive_branch_data.conn,
            seq=1,
            add_windings_phase=False
        )

    def x2var(self, x: Vec) -> None:
        """
        Convert X to decission variables
        :param x: solution vector
        """
        a = len(self.i_u_vm)
        b = a + len(self.i_u_va)
        c = b + len(self.u_vsc_pf)
        d = c + len(self.u_vsc_pt)
        e = d + len(self.u_vsc_qt)
        f = e + len(self.hvdc)
        g = f + len(self.hvdc)
        h = g + len(self.hvdc)
        i = h + len(self.hvdc)
        j = i + len(self.cbr_m)
        k = j + len(self.cbr_tau)

        # update the vectors
        self.Vm[self.i_u_vm] = x[0:a]
        self.Va[self.i_u_va] = x[a:b]
        self.Pf[self.u_vsc_pf] = x[b:c]
        self.Pt[self.u_vsc_pt] = x[c:d]
        self.Qt[self.u_vsc_qt] = x[d:e]
        self.Pf[self.hvdc] = x[e:f]
        self.Pt[self.hvdc] = x[f:g]
        self.Qf[self.hvdc] = x[g:h]
        self.Qt[self.hvdc] = x[h:i]
        self.m = x[i:j]
        self.tau = x[j:k]

    # DONE
    def var2x(self) -> Vec:
        """
        Convert the internal decision variables into the vector
        :return: Vector
        """
        return np.r_[
            self.Vm[self.i_u_vm],
            self.Va[self.i_u_va],
            self.Pf[self.u_vsc_pf],
            self.Pt[self.u_vsc_pt],
            self.Qt[self.u_vsc_qt],
            self.Pf[self.hvdc],
            self.Pt[self.hvdc],
            self.Qf[self.hvdc],
            self.Qt[self.hvdc],
            self.m,
            self.tau
        ]

    # DONE
    def size(self) -> int:
        """
        Size of the jacobian matrix
        :return:
        """
        return (len(self.i_u_vm)
                + len(self.i_u_va)
                + len(self.u_vsc_pf)
                + len(self.u_vsc_pt)
                + len(self.u_vsc_qt)
                + len(self.hvdc)
                + len(self.hvdc)
                + len(self.hvdc)
                + len(self.hvdc)
                + len(self.m)
                + len(self.tau))

    def compute_f(self, x: Vec) -> Vec:
        """
        Compute the residual vector
        :param x: Solution vector
        :return: Residual vector
        """

        a = len(self.i_u_vm)
        b = a + len(self.i_u_va)
        c = b + len(self.u_vsc_pf)
        d = c + len(self.u_vsc_pt)
        e = d + len(self.u_vsc_qt)
        f = e + len(self.hvdc)
        g = f + len(self.hvdc)
        h = g + len(self.hvdc)
        i = h + len(self.hvdc)
        j = i + len(self.cbr_m)
        k = j + len(self.cbr_tau)

        # update the vectors
        Vm = self.Vm.copy()
        Va = self.Va.copy()
        Pbus = self.Pzip.copy()
        Qbus = self.Qzip.copy()
        Pf = self.Pf.copy()
        Qf = self.Qf.copy()
        Pt = self.Pt.copy()
        Qt = self.Qt.copy()

        Vm[self.i_u_vm] = x[0:a]
        Va[self.i_u_va] = x[a:b]
        Pf[self.u_vsc_pf] = x[b:c]
        Pt[self.u_vsc_pt] = x[c:d]
        Qt[self.u_vsc_qt] = x[d:e]
        Pf[self.hvdc] = x[e:f]
        Pt[self.hvdc] = x[f:g]
        Qf[self.hvdc] = x[g:h]
        Qt[self.hvdc] = x[h:i]
        m = x[i:j]
        tau = x[j:k]

        # compute the complex voltage
        V = polar_to_rect(Vm, Va)

        # VSC Loss equation
        toBus = self.nc.vsc_data.T
        It = np.sqrt(Pt * Pt + Qt * Qt)[self.vsc] / Vm[toBus]
        It2 = It * It
        PLoss_IEC = (self.nc.vsc_data.alpha3 * It2
                     + self.nc.vsc_data.alpha2 * It
                     + self.nc.vsc_data.alpha1)

        Ploss_acdc = PLoss_IEC - Pt[self.vsc] - Pf[self.vsc]


        # HVDC Loss equation
        loss_hvdc = self.nc.hvdc_data.r * (Pf[self.hvdc] / Vm[self.nc.hvdc_data.F]) ** 2
        Ploss_hvdc = Pf[self.hvdc] + Pt[self.hvdc] - loss_hvdc

        # HVDC Injection equation
        dtheta = np.rad2deg(Va[self.nc.hvdc_data.F] - Va[self.nc.hvdc_data.T])
        droop_contr = self.indices.hvdc_mode * self.nc.hvdc_data.angle_droop * dtheta
        Pcalc_hvdc = self.nc.hvdc_data.Pset + droop_contr
        inj_hvdc = self.nc.hvdc_data.Pset + Pcalc_hvdc
        Pinj_hvdc = Pf[self.hvdc] - inj_hvdc/self.nc.Sbase


        # Legacy HVDC power injection (Pinj_hvdc) equation + loss (Ploss_hvdc) equation
        # Ploss_hvdc = np.zeros(self.nc.nhvdc)
        # Pinj_hvdc = np.zeros(self.nc.nhvdc)

        # for i in range(self.nc.nhvdc):
        #     dtheta = np.rad2deg(Va[self.nc.hvdc_data.F[i]] - Va[self.nc.hvdc_data.T[i]])
        #     droop_contr = self.indices.hvdc_mode[i] * self.nc.hvdc_data.angle_droop[i] * dtheta
        #     Pcalc_hvdc = self.nc.hvdc_data.Pset[i] + droop_contr
        #
        #     if Pcalc_hvdc > 0.0:
        #         ihvdcpu = Pcalc_hvdc / self.nc.Sbase / (Vm[self.nc.hvdc_data.F[i]])
        #         rpu = self.nc.hvdc_data.r[i] * self.nc.Sbase / (self.nc.hvdc_data.Vnf[i] * self.nc.hvdc_data.Vnf[i])
        #         losshvdcpu = rpu * ihvdcpu * ihvdcpu
        #         Ploss_hvdc[i] = Pt[self.cg_hvdc[i]] + Pcalc_hvdc / self.nc.Sbase - losshvdcpu
        #         Pinj_hvdc[i] = Pf[self.cg_hvdc[i]] - Pcalc_hvdc / self.nc.Sbase
        #
        #     elif Pcalc_hvdc < 0.0:
        #         ihvdcpu = Pcalc_hvdc / self.nc.Sbase / (Vm[self.nc.hvdc_data.T[i]])
        #         rpu = self.nc.hvdc_data.r[i] * self.nc.Sbase / (self.nc.hvdc_data.Vnt[i] * self.nc.hvdc_data.Vnt[i])
        #         losshvdcpu = rpu * ihvdcpu * ihvdcpu
        #         Ploss_hvdc[i] = Pcalc_hvdc / self.nc.Sbase + Pf[self.cg_hvdc[i]] - losshvdcpu
        #         Pinj_hvdc[i] = Pt[self.cg_hvdc[i]] - Pcalc_hvdc / self.nc.Sbase
        #
        #     else:
        #         Ploss_hvdc[i] = 0.0
        #         Pinj_hvdc[i] = 0.0

        # remapping of indices
        m2 = np.ones(self.nc.nbr)
        m2[self.cbr_m] = m.copy()
        tau2 = np.zeros(self.nc.nbr)
        tau2[self.cbr_tau] = tau.copy()

        # compute the function residual
        adm = compute_admittances(
            R=self.R,
            X=self.X,
            G=self.G,
            B=self.B,
            k=self.k,
            tap_module=m2,
            vtap_f=self.nc.passive_branch_data.virtual_tap_f,
            vtap_t=self.nc.passive_branch_data.virtual_tap_t,
            tap_angle=tau2,
            Cf=self.nc.Cf,
            Ct=self.nc.Ct,
            Yshunt_bus=self.nc.Yshunt_from_devices,
            conn=self.nc.passive_branch_data.conn,
            seq=1,
            add_windings_phase=False
        )


        Sbus = compute_zip_power(self.S0, self.I0, self.Y0, Vm)
        # Sbus += Pbus + 1j * Qbus
        Scalc = compute_power(adm.Ybus, V)

        dS = (
                Scalc - Sbus

                # add contribution of acdc link
                + ((Pf + 1j * Qf)[self.vsc] @ self.nc.vsc_data.C_branch_bus_f
                   + (Pt + 1j * Qt)[self.vsc] @ self.nc.vsc_data.C_branch_bus_t)

                # add contribution of HVDC link
                + ((Pf + 1j * Qf)[self.hvdc] @ self.nc.hvdc_data.C_hvdc_bus_f
                   + (Pt + 1j * Qt)[self.hvdc] @ self.nc.hvdc_data.C_hvdc_bus_t)

                # add contribution of transformer
                + ((Pf + 1j * Qf)[self.cbr] @ self.nc.passive_branch_data.C_branch_bus_f[self.cbr, :]
                   + (Pt + 1j * Qt)[self.cbr] @ self.nc.passive_branch_data.C_branch_bus_t[self.cbr, :])

        )

        V = Vm * np.exp(1j * Va)
        Pftr, Qftr, Pttr, Qttr = recompute_controllable_power(
            V_f=V[self.nc.passive_branch_data.F[self.controlled_idx]],
            V_t=V[self.nc.passive_branch_data.T[self.controlled_idx]],
            R=self.nc.passive_branch_data.R[self.controlled_idx],
            X=self.nc.passive_branch_data.X[self.controlled_idx],
            G=self.nc.passive_branch_data.G[self.controlled_idx],
            B=self.nc.passive_branch_data.B[self.controlled_idx],
            tap_module=m2[self.controlled_idx],
            vtap_f=self.nc.passive_branch_data.virtual_tap_f[self.controlled_idx],
            vtap_t=self.nc.passive_branch_data.virtual_tap_t[self.controlled_idx],
            tap_angle=tau2[self.controlled_idx]
        )

        _f = np.r_[
            dS[self.i_k_p].real,
            dS[self.i_k_q].imag,
            Ploss_acdc,
            Ploss_hvdc,
            Pinj_hvdc,
            Pf[self.k_cbr_pf] - Pftr,
            Pt[self.k_cbr_pt] - Pttr,
            Qf[self.k_cbr_qf] - Qftr,
            Qt[self.k_cbr_qt] - Qttr
        ]

        errf = compute_fx_error(_f)
        assert len(_f) == j, f"len(_f)={len(_f)} != j={j}"

        return _f

    def check_error(self, x: Vec) -> Tuple[float, Vec]:
        """
        Check error of the solution without affecting the problem
        :param x: Solution vector
        :return: error
        """
        _res = self.compute_f(x)
        err = compute_fx_error(_res)

        # compute the error
        return err, x

    def update(self, x: Vec, update_controls: bool = False) -> Tuple[float, bool, Vec, Vec]:
        """
        Update step
        :param x: Solution vector
        :param update_controls:
        :return: error, converged?, x, fx
        """
        # set the problem state
        self.x2var(x)

        # compute the complex voltage
        self.V = polar_to_rect(self.Vm, self.Va)

        # Update converter losses
        toBus = self.nc.vsc_data.T
        It = np.sqrt(self.Pt * self.Pt + self.Qt * self.Qt)[self.vsc] / self.Vm[toBus]
        It2 = It * It
        PLoss_IEC = (self.nc.vsc_data.alpha3 * It2
                     + self.nc.vsc_data.alpha2 * It
                     + self.nc.vsc_data.alpha1)

        # ACDC Power Loss Residual
        Ploss_acdc = PLoss_IEC - self.Pt[self.vsc] - self.Pf[self.vsc]

        # HVDC Loss equation
        loss_hvdc = self.nc.hvdc_data.r * (self.Pf[self.hvdc] / self.Vm[self.nc.hvdc_data.F]) ** 2
        Ploss_hvdc = self.Pf[self.hvdc] + self.Pt[self.hvdc] - loss_hvdc

        # HVDC Injection equation
        dtheta = np.rad2deg(self.Va[self.nc.hvdc_data.F] - self.Va[self.nc.hvdc_data.T])
        droop_contr = self.indices.hvdc_mode * self.nc.hvdc_data.angle_droop * dtheta
        Pcalc_hvdc = self.nc.hvdc_data.Pset + droop_contr
        inj_hvdc = self.nc.hvdc_data.Pset + Pcalc_hvdc
        Pinj_hvdc = self.Pf[self.hvdc] - inj_hvdc / self.nc.Sbase

        # Legacy HVDC power injection (Pinj_hvdc) equation + loss (Ploss_hvdc) equation
        # Ploss_hvdc = np.zeros(self.nc.nhvdc)
        # Pinj_hvdc = np.zeros(self.nc.nhvdc)
        # for i in range(self.nc.nhvdc):
        #     dtheta = np.rad2deg(self.Va[self.nc.hvdc_data.F[i]] - self.Va[self.nc.hvdc_data.T[i]])
        #     droop_contr = self.indices.hvdc_mode[i] * self.nc.hvdc_data.angle_droop[i] * dtheta
        #     Pcalc_hvdc = self.nc.hvdc_data.Pset[i] + droop_contr
        #
        #     if Pcalc_hvdc > 0.0:
        #         ihvdcpu = Pcalc_hvdc / self.nc.Sbase / (self.Vm[self.nc.hvdc_data.F[i]])
        #         rpu = self.nc.hvdc_data.r[i] * self.nc.Sbase / (self.nc.hvdc_data.Vnf[i] * self.nc.hvdc_data.Vnf[i])
        #         losshvdcpu = rpu * ihvdcpu * ihvdcpu
        #         Ploss_hvdc[i] = self.Pt[self.cg_hvdc[i]] + Pcalc_hvdc / self.nc.Sbase - losshvdcpu
        #         Pinj_hvdc[i] = self.Pf[self.cg_hvdc[i]] - Pcalc_hvdc / self.nc.Sbase
        #
        #     elif Pcalc_hvdc < 0.0:
        #         ihvdcpu = Pcalc_hvdc / self.nc.Sbase / (self.Vm[self.nc.hvdc_data.T[i]])
        #         rpu = self.nc.hvdc_data.r[i] * self.nc.Sbase / (self.nc.hvdc_data.Vnt[i] * self.nc.hvdc_data.Vnt[i])
        #         losshvdcpu = rpu * ihvdcpu * ihvdcpu
        #         Ploss_hvdc[i] = Pcalc_hvdc / self.nc.Sbase + self.Pf[self.cg_hvdc[i]] - losshvdcpu
        #         Pinj_hvdc[i] = self.Pt[self.cg_hvdc[i]] - Pcalc_hvdc / self.nc.Sbase
        #
        #     else:
        #         Ploss_hvdc[i] = 0.0
        #         Pinj_hvdc[i] = 0.0


        # remapping of indices
        m2 = np.ones(self.nc.nbr)
        m2[self.cbr_m] = self.m.copy()
        tau2 = np.zeros(self.nc.nbr)
        tau2[self.cbr_tau] = self.tau.copy()

        # compute the function residual
        self.adm = compute_admittances(
            R=self.R,
            X=self.X,
            G=self.G,
            B=self.B,
            k=self.k,
            tap_module=m2,
            vtap_f=self.nc.passive_branch_data.virtual_tap_f,
            vtap_t=self.nc.passive_branch_data.virtual_tap_t,
            tap_angle=tau2,
            Cf=self.nc.Cf,
            Ct=self.nc.Ct,
            Yshunt_bus=self.nc.Yshunt_from_devices,
            conn=self.nc.passive_branch_data.conn,
            seq=1,
            add_windings_phase=False
        )

        # compute the function residual
        Sbus = compute_zip_power(self.S0, self.I0, self.Y0, self.Vm) + self.Pzip + 1j * self.Qzip
        Scalc = compute_power(self.adm.Ybus, self.V)

        dS = (
                Scalc - Sbus

                # add contribution of acdc link
                + ((self.Pf + 1j * self.Qf)[self.vsc] @ self.nc.vsc_data.C_branch_bus_f
                   + (self.Pt + 1j * self.Qt)[self.vsc] @ self.nc.vsc_data.C_branch_bus_t)

                # add contribution of HVDC link
                + ((self.Pf + 1j * self.Qf)[self.hvdc] @ self.nc.hvdc_data.C_hvdc_bus_f
                   + (self.Pt + 1j * self.Qt)[self.hvdc] @ self.nc.hvdc_data.C_hvdc_bus_t)

                # add contribution of transformer
                + ((self.Pf + 1j * self.Qf)[self.cbr] @ self.nc.passive_branch_data.C_branch_bus_f[self.cg_pttr, :]
                   + (self.Pt + 1j * self.Qt)[self.cbr] @ self.nc.passive_branch_data.C_branch_bus_t[self.cg_pttr,
                                                              :])
        )

        # Use self.Pf...
        Pftr, Qftr, Pttr, Qttr = recompute_controllable_power(
            V_f=self.V[self.nc.passive_branch_data.F[self.controlled_idx]],
            V_t=self.V[self.nc.passive_branch_data.T[self.controlled_idx]],
            R=self.nc.passive_branch_data.R[self.controlled_idx],
            X=self.nc.passive_branch_data.X[self.controlled_idx],
            G=self.nc.passive_branch_data.G[self.controlled_idx],
            B=self.nc.passive_branch_data.B[self.controlled_idx],
            tap_module=m2[self.controlled_idx],
            vtap_f=self.nc.passive_branch_data.virtual_tap_f[self.controlled_idx],
            vtap_t=self.nc.passive_branch_data.virtual_tap_t[self.controlled_idx],
            tap_angle=tau2[self.controlled_idx]
        )
        self._f = np.r_[
            dS[self.i_k_p].real,  # TODO what does + mean here?
            dS[self.i_k_q].imag,
            Ploss_acdc,
            Ploss_hvdc,
            Pinj_hvdc,
            self.Pf[self.k_cbr_pf] - Pftr,
            self.Qf[self.k_cbr_pf] - Qftr,
            self.Pt[self.k_cbr_pf] - Pttr,
            self.Qt[self.k_cbr_pf] - Qttr
        ]

        # compute the error
        self._error = compute_fx_error(self._f)

        if self.options.verbose > 1:
            print("Vm:", self.Vm)
            print("Va:", self.Va)
            print("Pbus:", self.Pzip)
            print("Qbus:", self.Qzip)
            print("Pf:", self.Pf)
            print("Qf:", self.Qf)
            print("Pt:", self.Pt)
            print("Qt:", self.Qt)
            print("m:", self.m)
            print("tau:", self.tau)
            print("error:", self._error)

        # Update controls only below a certain error
        """
        if update_controls and self._error < self._controls_tol:
            any_change = False
            branch_ctrl_change = False

            # review reactive power limits
            # it is only worth checking Q limits with a low error
            # since with higher errors, the Q values may be far from realistic
            # finally, the Q control only makes sense if there are pv nodes
            if self.options.control_Q and (len(self.pv) + len(self.p)) > 0:

                # check and adjust the reactive power
                # this function passes pv buses to pq when the limits are violated,
                # but not pq to pv because that is unstable
                changed, pv, pq, pqv, p = control_q_inside_method(self.Scalc, self.S0,
                                                                  self.pv, self.pq,
                                                                  self.pqv, self.p,
                                                                  self.Qmin, self.Qmax)

                if len(changed) > 0:
                    any_change = True

                    # update the bus type lists
                    self.update_bus_types(pq=pq, pv=pv, pqv=pqv, p=p)

                    # the composition of x may have changed, so recompute
                    x = self.var2x()

            # update Slack control
            if self.options.distributed_slack:
                ok, delta = compute_slack_distribution(Scalc=self.Scalc,
                                                       vd=self.vd,
                                                       bus_installed_power=self.nc.bus_installed_power)
                if ok:
                    any_change = True
                    # Update the objective power to reflect the slack distribution
                    self.S0 += delta

            # update the tap module control
            if self.options.control_taps_modules:
                for i, k in enumerate(self.idx_dm):

                    m_taps = self.nc.branch_data.m_taps[i]

                    if self.options.orthogonalize_controls and m_taps is not None:
                        _, self.m[i] = find_closest_number(arr=m_taps, target=self.m[i])

                    if self.m[i] < self.nc.branch_data.tap_module_min[k]:
                        self.m[i] = self.nc.branch_data.tap_module_min[k]
                        self.tap_module_control_mode[k] = TapModuleControl.fixed
                        branch_ctrl_change = True
                        self.logger.add_info("Min tap module reached",
                                             device=self.nc.branch_data.names[k],
                                             value=self.m[i])

                    if self.m[i] > self.nc.branch_data.tap_module_max[k]:
                        self.m[i] = self.nc.branch_data.tap_module_max[k]
                        self.tap_module_control_mode[k] = TapModuleControl.fixed
                        branch_ctrl_change = True
                        self.logger.add_info("Max tap module reached",
                                             device=self.nc.branch_data.names[k],
                                             value=self.m[i])

            # update the tap phase control
            if self.options.control_taps_phase:

                for i, k in enumerate(self.idx_dtau):

                    tau_taps = self.nc.branch_data.tau_taps[i]

                    if self.options.orthogonalize_controls and tau_taps is not None:
                        _, self.tau[i] = find_closest_number(arr=tau_taps, target=self.tau[i])

                    if self.tau[i] < self.nc.branch_data.tap_angle_min[k]:
                        self.tau[i] = self.nc.branch_data.tap_angle_min[k]
                        self.tap_phase_control_mode[k] = TapPhaseControl.fixed
                        branch_ctrl_change = True
                        self.logger.add_info("Min tap phase reached",
                                             device=self.nc.branch_data.names[k],
                                             value=self.tau[i])

                    if self.tau[i] > self.nc.branch_data.tap_angle_max[k]:
                        self.tau[i] = self.nc.branch_data.tap_angle_max[k]
                        self.tap_phase_control_mode[k] = TapPhaseControl.fixed
                        branch_ctrl_change = True
                        self.logger.add_info("Max tap phase reached",
                                             device=self.nc.branch_data.names[k],
                                             value=self.tau[i])

            if branch_ctrl_change:
                k_v_m = self.analyze_branch_controls()
                vd, pq, pv, pqv, p, self.no_slack = compile_types(Pbus=self.nc.Sbus.real, types=self.bus_types)
                self.update_bus_types(pq=pq, pv=pv, pqv=pqv, p=p)

            if any_change or branch_ctrl_change:
                # recompute the error based on the new Scalc and S0
                self._f = self.fx()

                # compute the error
                self._error = compute_fx_error(self._f)
        """

        # converged?
        self._converged = self._error < self.options.tolerance

        if self.options.verbose > 1:
            print("Error:", self._error)

        return self._error, self._converged, x, self.f

    def fx(self) -> Vec:
        """
        Used? No
        :return:
        """

        # Assumes the internal vars were updated already with self.x2var()
        Sbus = compute_zip_power(self.S0, self.I0, self.Y0, self.Vm)
        self.Scalc = compute_power(self.adm.Ybus, self.V)

        dS = self.Scalc - Sbus  # compute the mismatch

        Pf = get_Sf(k=self.idx_dPf, Vm=self.Vm, V=self.V,
                    yff=self.adm.yff, yft=self.adm.yft, F=self.nc.F, T=self.nc.T).real

        Qf = get_Sf(k=self.idx_dQf, Vm=self.Vm, V=self.V,
                    yff=self.adm.yff, yft=self.adm.yft, F=self.nc.F, T=self.nc.T).imag

        Pt = get_St(k=self.idx_dPt, Vm=self.Vm, V=self.V,
                    ytf=self.adm.ytf, ytt=self.adm.ytt, F=self.nc.F, T=self.nc.T).real

        Qt = get_St(k=self.idx_dQt, Vm=self.Vm, V=self.V,
                    ytf=self.adm.ytf, ytt=self.adm.ytt, F=self.nc.F, T=self.nc.T).imag

        self._f = np.r_[
            dS[self.idx_dP].real,
            dS[self.idx_dQ].imag,
            Pf - self.nc.passive_branch_data.Pset[self.idx_dPf],
            Qf - self.nc.passive_branch_data.Qset[self.idx_dQf],
            Pt - self.nc.passive_branch_data.Pset[self.idx_dPt],
            Qt - self.nc.passive_branch_data.Qset[self.idx_dQt]
        ]
        return self._f

    def fx_diff(self, x: Vec) -> Vec:
        """
        Fx for autodiff
        :param x: solutions vector
        :return: f(x)
        """
        # print()
        ff = self.compute_f(x)
        return ff

    def Jacobian(self, autodiff: bool = True) -> CSC:
        """
        Get the Jacobian
        :return:
        """
        if autodiff:
            J = calc_autodiff_jacobian(func=self.fx_diff, x=self.var2x(), h=1e-6)

            if self.options.verbose > 1:
                print("(pf_generalized_formulation.py) J: ")
                print(J)
                print("J shape: ", J.shape)

            # Jdense = np.array(J.todense())
            # dff = pd.DataFrame(Jdense)
            # dff.to_excel("Jacobian_autodiff.xlsx")
            return scipy_to_mat(J)
        else:
            n_rows = (len(self.cg_pac)
                      + len(self.cg_qac)
                      + len(self.cg_pdc)
                      + len(self.cg_acdc)
                      + (2 * len(self.cg_hvdc))  # hvdc has 2 equations: Pinj and Ploss
                      + len(self.cg_pftr)
                      + len(self.cg_qftr)
                      + len(self.cg_pttr)
                      + len(self.cg_qttr))

            n_cols = (len(self.cx_vm)
                      + len(self.cx_va)
                      + len(self.cx_pzip)
                      + len(self.cx_qzip)
                      + len(self.cx_pfa)
                      + len(self.cx_qfa)
                      + len(self.cx_pta)
                      + len(self.cx_qta)
                      + len(self.cx_m)
                      + len(self.cx_tau))

            if n_cols != n_rows:
                raise ValueError("Incorrect J indices!")

            tap_modules = expand(self.nc.nbr, self.m, self.cg_pttr, 1.0)
            tap_angles = expand(self.nc.nbr, self.tau, self.cg_pttr, 0.0)
            tap = polar_to_rect(tap_modules, tap_angles)

            J = adv_jacobian(
                nbus=self.nc.nbus,
                nbr=self.nc.nbr,
                nvsc=len(self.cg_acdc),
                nhvdc=len(self.cg_hvdc),
                ncontbr=len(self.cg_pftr),
                ix_vm=self.indices.cx_vm,
                ix_va=self.indices.cx_va,
                ix_pzip=self.indices.cx_pzip,
                ix_qzip=self.indices.cx_qzip,
                ix_pf=self.indices.cx_pfa,
                ix_qf=self.indices.cx_qfa,
                ix_pt=self.indices.cx_pta,
                ix_qt=self.indices.cx_qta,
                ix_m=self.indices.cx_m,
                ix_tau=self.indices.cx_tau,
                ig_pbus=self.indices.cg_pac + self.indices.cg_pdc,
                ig_qbus=self.indices.cg_qac,
                ig_plossacdc=self.indices.cg_acdc,
                ig_plosshvdc=self.indices.cg_hvdc,
                ig_pinjhvdc=self.indices.cg_hvdc,
                ig_pftr=self.indices.cg_pftr,
                ig_qftr=self.indices.cg_qftr,
                ig_pttr=self.indices.cg_pttr,
                ig_qttr=self.indices.cg_qttr,
                ig_contrbr=self.indices.cg_qttr,
                Cf_acdc=self.nc.vsc_data.C_branch_bus_f,
                Ct_acdc=self.nc.vsc_data.C_branch_bus_t,
                Cf_hvdc=self.nc.hvdc_data.C_hvdc_bus_f,
                Ct_hvdc=self.nc.hvdc_data.C_hvdc_bus_t,
                Cf_contbr=self.nc.passive_branch_data.C_branch_bus_f,
                Ct_contbr=self.nc.passive_branch_data.C_branch_bus_t,
                Cf_branch=self.nc.passive_branch_data.C_branch_bus_f,
                Ct_branch=self.nc.passive_branch_data.C_branch_bus_t,
                alpha1=self.nc.vsc_data.alpha1,
                alpha2=self.nc.vsc_data.alpha2,
                alpha3=self.nc.vsc_data.alpha3,
                F_acdc=self.nc.vsc_data.F,
                T_acdc=self.nc.vsc_data.T,
                F_hvdc=self.nc.hvdc_data.F,
                T_hvdc=self.nc.hvdc_data.T,
                hvdc_mode=self.indices.hvdc_mode,
                hvdc_angle_droop=self.nc.hvdc_data.angle_droop,
                hvdc_pset=self.nc.hvdc_data.Pset,
                hvdc_r=self.nc.hvdc_data.r,
                hvdc_Vnf=self.nc.hvdc_data.Vnf,
                hvdc_Vnt=self.nc.hvdc_data.Vnt,
                Pf=self.Pf,
                Qf=self.Qf,
                Pt=self.Pt,
                Qt=self.Qt,
                Fbr=self.nc.F,
                Tbr=self.nc.T,
                Ys=self.Ys,
                R=self.nc.passive_branch_data.R,
                X=self.nc.passive_branch_data.X,
                G=self.nc.passive_branch_data.G,
                B=self.nc.passive_branch_data.B,
                vtap_f=self.nc.passive_branch_data.virtual_tap_f,
                vtap_t=self.nc.passive_branch_data.virtual_tap_t,
                kconv=self.nc.passive_branch_data.k,
                complex_tap=tap,
                tap_modules=tap_modules,
                Bc=self.nc.passive_branch_data.B,
                V=self.V,
                Vm=np.abs(self.V),
                Va=np.angle(self.V),
                Sbase=self.nc.Sbase,
                Ybus_x=self.adm.Ybus.data,
                Ybus_p=self.adm.Ybus.indptr,
                Ybus_i=self.adm.Ybus.indices,
                yff=self.adm.yff,
                yft=self.adm.yft,
                ytf=self.adm.ytf,
                ytt=self.adm.ytt)

            # Jdense = np.array(J.todense())
            # dff = pd.DataFrame(Jdense)
            # dff.to_excel("Jacobian_symbolic.xlsx")
            return J

    def get_x_names(self) -> List[str]:
        """
        Names matching x
        :return:
        """
        cols = [f'dVa {i}' for i in self.idx_dVa]
        cols += [f'dVm {i}' for i in self.idx_dVm]
        cols += [f'dm {i}' for i in self.idx_dm]
        cols += [f'dtau {i}' for i in self.idx_dtau]
        cols += [f'dBeq {i}' for i in self.idx_dbeq]

        return cols

    def get_fx_names(self) -> List[str]:
        """
        Names matching fx
        :return:
        """
        '''
        self.cg_pac = generalisedSimulationIndices.cg_pac
        self.cg_qac = generalisedSimulationIndices.cg_qac
        self.cg_pdc = generalisedSimulationIndices.cg_pdc
        self.cg_acdc = generalisedSimulationIndices.cg_acdc
        self.cg_hvdc = generalisedSimulationIndices.cg_hvdc
        self.cg_pftr = generalisedSimulationIndices.cg_pftr
        self.cg_pttr = generalisedSimulationIndices.cg_pttr
        self.cg_qftr = generalisedSimulationIndices.cg_qftr
        self.cg_qttr = generalisedSimulationIndices.cg_qttr
                    dS[self.cg_pac + self.cg_pdc].real,
            dS[self.cg_qac].imag,
            Ploss_acdc,
            Pf[self.cg_pftr] - self.nc.active_branch_data.Pset[self.cg_pftr],
            Qf[self.cg_qftr] - self.nc.active_branch_data.Qset[self.cg_qftr],
            Pt[self.cg_pttr] - self.nc.active_branch_data.Pset[self.cg_pttr],
            Qt[self.cg_qttr] - self.nc.active_branch_data.Qset[self.cg_qttr]
        '''

        rows = [f'active power balance node {i}' for i in (self.cg_pac.union(self.cg_pdc))]
        rows += [f'reactive power balance node {i}' for i in self.cg_qac]
        rows += [f'Ploss_acdc {i}' for i in self.cg_acdc]
        rows += [f'Ploss_hvdc {i}' for i in self.cg_hvdc]
        rows += [f'Pinj_hvdc {i}' for i in self.cg_hvdc]
        rows += [f'cg_pftr {i}' for i in self.cg_pttr]
        rows += [f'cg_pttr {i}' for i in self.cg_pttr]
        rows += [f'cg_qftr {i}' for i in self.cg_qftr]
        rows += [f'cg_qttr {i}' for i in self.cg_qttr]

        return rows

    def get_jacobian_df(self, autodiff=False) -> pd.DataFrame:
        """
        Get the Jacobian DataFrame
        :return: DataFrame
        """
        J = self.Jacobian(autodiff=autodiff)
        return pd.DataFrame(
            data=J.toarray(),
            columns=self.get_x_names(),
            index=self.get_fx_names(),
        )

    def get_solution(self, elapsed: float, iterations: int) -> NumericPowerFlowResults:
        """
        Get the problem solution
        :param elapsed: Elapsed seconds
        :param iterations: Iteration number
        :return: NumericPowerFlowResults
        """

        # Branches current, loading, etc
        V = self.Vm * np.exp(1j * self.Va)
        Vf = V[self.nc.passive_branch_data.F]
        Vt = V[self.nc.passive_branch_data.T]
        If = self.adm.Yf @ V
        It = self.adm.Yt @ V
        Sf = Vf * np.conj(If)
        St = Vt * np.conj(It)

        Sf_contrl_br = (self.Pf + 1j * self.Qf)[self.cg_pttr]
        St_contrl_br = (self.Pt + 1j * self.Qt)[self.cg_pttr]

        If[self.cg_pftr] = np.conj(Sf_contrl_br / Vf[self.cg_pftr])
        It[self.cg_pftr] = np.conj(St_contrl_br / Vt[self.cg_pftr])
        Sf[self.cg_pftr] = Sf_contrl_br
        St[self.cg_pftr] = St_contrl_br

        # Branch losses in MVA
        losses = (Sf + St) * self.nc.Sbase

        # branch voltage increment
        Vbranch = Vf - Vt

        # Branch loading in p.u.
        loading = Sf * self.nc.Sbase / (self.nc.passive_branch_data.rates + 1e-9)

        # VSC
        Pf_vsc = self.Pf[self.cg_acdc]
        St_vsc = (self.Pt + 1j * self.Qt)[self.cg_acdc]
        If_vsc = Pf_vsc / np.abs(V[self.nc.vsc_data.F])
        It_vsc = St_vsc / np.conj(V[self.nc.vsc_data.T])
        loading_vsc = abs(St_vsc) / (self.nc.vsc_data.rates + 1e-20) * self.nc.Sbase

        # HVDC
        Sf_hvdc = (self.Pf + 1j * self.Qf)[self.cg_hvdc] * self.nc.Sbase
        St_hvdc = (self.Pt + 1j * self.Qt)[self.cg_hvdc] * self.nc.Sbase
        loading_hvdc = Sf_hvdc.real / (self.nc.hvdc_data.rate + 1e-20)

        return NumericPowerFlowResults(
            V=self.V,
            Scalc=self.Scalc,
            m=expand(self.nc.nbr, self.m, self.cx_m, 1.0),
            tau=expand(self.nc.nbr, self.tau, self.cx_tau, 0.0),
            Sf=Sf * self.nc.Sbase,
            St=St * self.nc.Sbase,
            If=If,
            It=It,
            loading=loading,
            losses=losses,
            Pf_vsc=Pf_vsc * self.nc.Sbase,
            St_vsc=St_vsc * self.nc.Sbase,
            If_vsc=If_vsc,
            It_vsc=It_vsc,
            losses_vsc=Pf_vsc + St_vsc.real,
            loading_vsc=loading_vsc,
            Sf_hvdc=Sf_hvdc,
            St_hvdc=St_hvdc,
            losses_hvdc=Sf_hvdc + Sf_hvdc,
            loading_hvdc=loading_hvdc,
            norm_f=self.error,
            converged=self.converged,
            iterations=iterations,
            elapsed=elapsed
        )
