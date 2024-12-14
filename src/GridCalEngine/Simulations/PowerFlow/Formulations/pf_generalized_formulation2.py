# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import time
from typing import Tuple, List, Callable, Union
import numpy as np
import pandas as pd
import scipy as sp

from scipy.sparse import lil_matrix
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
import GridCalEngine.Simulations.Derivatives.csc_derivatives as deriv
from GridCalEngine.Utils.Sparse.csc2 import CSC, CxCSC, scipy_to_mat, mat_to_scipy
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import expand
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import compute_fx_error
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_formulation_template import PfFormulationTemplate

from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import polar_to_rect
from GridCalEngine.enumerations import (TapPhaseControl, TapModuleControl, BusMode, HvdcControlType,
                                        ConverterControlType)
from GridCalEngine.basic_structures import Vec, IntVec, CxVec, BoolVec, Logger


def calcYbus(Cf, Ct, Yshunt_bus: CxVec,
             R: Vec, X: Vec, G: Vec, B: Vec, m: Vec, tau: Vec, vtap_f: Vec, vtap_t: Vec):
    """
    Compute passive Ybus
    :param Cf:
    :param Ct:
    :param Yshunt_bus:
    :param R:
    :param X:
    :param G:
    :param B:
    :param m:
    :param tau:
    :param vtap_f:
    :param vtap_t:
    :return:
    """
    ys = 1.0 / (R + 1.0j * X + 1e-20)  # series admittance
    bc2 = (G + 1j * B) / 2.0  # shunt admittance
    yff = (ys + bc2) / (m * m * vtap_f * vtap_f)
    yft = -ys / (m * np.exp(-1.0j * tau) * vtap_f * vtap_t)
    ytf = -ys / (m * np.exp(1.0j * tau) * vtap_t * vtap_f)
    ytt = (ys + bc2) / (vtap_t * vtap_t)

    Yf = sp.diags(yff) * Cf + sp.diags(yft) * Ct
    Yt = sp.diags(ytf) * Cf + sp.diags(ytt) * Ct
    Ybus = Cf.T * Yf + Ct.T * Yt + sp.diags(Yshunt_bus)

    return Ybus


def calcSf(k: IntVec, V: CxVec, F: IntVec, T: IntVec,
           R: Vec, X: Vec, G: Vec, B: Vec, m: Vec, tau: Vec, vtap_f: Vec, vtap_t: Vec):
    """
    Compute Sf for pi branches
    :param k:
    :param V:
    :param F:
    :param T:
    :param R:
    :param X:
    :param G:
    :param B:
    :param m:
    :param tau:
    :param vtap_f:
    :param vtap_t:
    :return:
    """
    ys = 1.0 / (R[k] + 1.0j * X[k] + 1e-20)  # series admittance
    bc2 = (G[k] + 1j * B[k]) / 2.0  # shunt admittance
    yff = (ys + bc2) / (m[k] * m[k] * vtap_f[k] * vtap_f[k])
    yft = -ys / (m * np.exp(-1.0j * tau[k]) * vtap_f[k] * vtap_t[k])

    Vf = V[F[k]]
    Vt = V[T[k]]
    Sf_cbr = (np.power(Vf, 2.0) * np.conj(yff) + Vf * Vt * np.conj(yft))

    return Sf_cbr


def calcSt(k: IntVec, V: CxVec, F: IntVec, T: IntVec,
           R: Vec, X: Vec, G: Vec, B: Vec, m: Vec, tau: Vec, vtap_f: Vec, vtap_t: Vec):
    """
    Compute St for pi branches
    :param k:
    :param V:
    :param F:
    :param T:
    :param R:
    :param X:
    :param G:
    :param B:
    :param m:
    :param tau:
    :param vtap_f:
    :param vtap_t:
    :return:
    """
    ys = 1.0 / (R[k] + 1.0j * X[k] + 1e-20)  # series admittance
    bc2 = (G[k] + 1j * B[k]) / 2.0  # shunt admittance

    ytf = -ys / (m * np.exp(1.0j * tau[k]) * vtap_t[k] * vtap_f[k])
    ytt = (ys + bc2) / (vtap_t[k] * vtap_t[k])

    Vf = V[F[k]]
    Vt = V[T[k]]

    St_cbr = (np.power(Vt, 2.0) * np.conj(ytt) + Vt * Vf * np.conj(ytf))

    return St_cbr


def calc_autodiff_jacobian(func: Callable[[Vec], Vec], x: Vec, h=1e-8) -> CSC:
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

    return scipy_to_mat(jac.tocsc())


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

        # arrays for branch control types (nbr)
        self.tap_module_control_mode = nc.active_branch_data.tap_module_control_mode
        self.tap_controlled_buses = nc.active_branch_data.tap_phase_control_mode
        self.tap_phase_control_mode = nc.active_branch_data.tap_controlled_buses
        self.F = nc.passive_branch_data.F
        self.T = nc.passive_branch_data.T

        # Indices ------------------------------------------------------------------------------------------------------

        # Bus indices
        self.bus_types = nc.bus_data.bus_types.copy()
        self.is_p_controlled = nc.bus_data.is_p_controlled.copy()
        self.is_q_controlled = nc.bus_data.is_q_controlled.copy()
        self.is_vm_controlled = nc.bus_data.is_vm_controlled.copy()
        self.is_va_controlled = nc.bus_data.is_va_controlled.copy()
        self.i_u_vm = np.where(self.is_vm_controlled == 0)[0]
        self.i_u_va = np.where(self.is_va_controlled == 0)[0]
        self.i_k_p = np.where(self.is_p_controlled == 1)[0]
        self.i_k_q = np.where(self.is_q_controlled == 1)[0]

        # Controllable Branch Indices
        self.u_cbr_m = np.zeros(0, dtype=int)
        self.u_cbr_tau = np.zeros(0, dtype=int)
        self.cbr = np.zeros(0, dtype=int)
        self.k_cbr_pf = np.zeros(0, dtype=int)
        self.k_cbr_pt = np.zeros(0, dtype=int)
        self.k_cbr_qf = np.zeros(0, dtype=int)
        self.k_cbr_qt = np.zeros(0, dtype=int)
        self.cbr_pf_set = np.zeros(0, dtype=float)
        self.cbr_pt_set = np.zeros(0, dtype=float)
        self.cbr_qf_set = np.zeros(0, dtype=float)
        self.cbr_qt_set = np.zeros(0, dtype=float)
        self.analyze_branch_controls()

        # VSC Indices
        # self.vsc = np.zeros(0, dtype=int)
        self.u_vsc_pf = np.zeros(0, dtype=int)
        self.u_vsc_pt = np.zeros(0, dtype=int)
        self.u_vsc_qt = np.zeros(0, dtype=int)
        self.k_vsc_pf = np.zeros(0, dtype=int)
        self.k_vsc_pt = np.zeros(0, dtype=int)
        self.k_vsc_qt = np.zeros(0, dtype=int)
        self.vsc_pf_set = np.zeros(0, dtype=float)
        self.vsc_pt_set = np.zeros(0, dtype=float)
        self.vsc_qt_set = np.zeros(0, dtype=float)
        self.analyze_vsc_controls()

        # HVDC Indices
        self.hvdc_droop_idx = np.zeros(0, dtype=int)
        self.analyze_hvdc_controls()

        # Unknowns -----------------------------------------------------------------------------------------------------
        self._Vm = np.zeros(nc.bus_data.nbus)
        self._Va = np.zeros(nc.bus_data.nbus)
        self.Pf_vsc = np.zeros(nc.vsc_data.nelm)
        self.Pt_vsc = np.zeros(nc.vsc_data.nelm)
        self.Qt_vsc = np.zeros(nc.vsc_data.nelm)
        self.Pf_hvdc = np.zeros(nc.hvdc_data.nelm)
        self.Qf_hvdc = np.zeros(nc.hvdc_data.nelm)
        self.Pt_hvdc = np.zeros(nc.hvdc_data.nelm)
        self.Qt_hvdc = np.zeros(nc.hvdc_data.nelm)
        self.m = np.zeros(len(self.u_cbr_m))
        self.tau = np.zeros(len(self.u_cbr_tau))

        # seth the VSC setpoints
        self.Pf_vsc[self.k_vsc_pf] = self.vsc_pf_set
        self.Pt_vsc[self.k_vsc_pt] = self.vsc_pt_set
        self.Qt_vsc[self.k_vsc_qt] = self.vsc_qt_set

        # Controllable branches ----------------------------------------------------------------------------------------
        ys = 1.0 / (nc.passive_branch_data.R[self.cbr]
                    + 1.0j * nc.passive_branch_data.X[self.cbr] + 1e-20)  # series admittance
        bc2 = (nc.passive_branch_data.G[self.cbr] + 1j * nc.passive_branch_data.B[self.cbr]) / 2.0  # shunt admittance
        vtap_f = nc.passive_branch_data.virtual_tap_f[self.cbr]
        vtap_t = nc.passive_branch_data.virtual_tap_t[self.cbr]
        self.yff_cbr = ys / (vtap_f * vtap_f)
        self.yft_cbr = -ys / (vtap_f * vtap_t)
        self.ytf_cbr = -ys / (vtap_t * vtap_f)
        self.ytt_cbr = (ys + bc2) / (vtap_t * vtap_t)
        self.F_cbr = self.nc.passive_branch_data.F[self.cbr]
        self.T_cbr = self.nc.passive_branch_data.T[self.cbr]

    def analyze_branch_controls(self) -> None:
        """
        Analyze the control branches and compute the indices
        :return: None
        """
        # Controllable Branch Indices
        u_cbr_m = list()
        u_cbr_tau = list()
        cbr = list()
        k_cbr_pf = list()
        k_cbr_pt = list()
        k_cbr_qf = list()
        k_cbr_qt = list()
        cbr_pf_set = list()
        cbr_pt_set = list()
        cbr_qf_set = list()
        cbr_qt_set = list()

        # CONTROLLABLE BRANCH LOOP
        for k in range(self.nc.passive_branch_data.nelm):

            ctrl_m = self.tap_module_control_mode[k]
            ctrl_tau = self.tap_phase_control_mode[k]

            # analyze tap-module controls
            if ctrl_m == TapModuleControl.Vm:

                # Every bus controlled by m has to become a PQV bus
                bus_idx = self.tap_controlled_buses[k]
                # self.is_p_controlled[bus_idx] = True
                # self.is_q_controlled[bus_idx] = True
                self.is_vm_controlled[bus_idx] = True
                # self.is_va_controlled[bus_idx] = True
                u_cbr_m.append(k)

            elif ctrl_m == TapModuleControl.Qf:
                u_cbr_m.append(k)
                k_cbr_qf.append(k)
                cbr_qf_set.append(self.nc.active_branch_data.Qset[k])

            elif ctrl_m == TapModuleControl.Qt:
                u_cbr_m.append(k)
                k_cbr_qt.append(k)
                cbr_qt_set.append(self.nc.active_branch_data.Qset[k])

            elif ctrl_m == TapModuleControl.fixed:
                pass

            elif ctrl_m == 0:
                pass

            else:
                raise Exception(f"Unknown tap phase module mode {ctrl_m}")

            # analyze tap-phase controls
            if ctrl_tau == TapPhaseControl.Pf:
                u_cbr_tau.append(k)
                k_cbr_pf.append(k)
                cbr_pf_set.append(self.nc.active_branch_data.Pset[k])

            elif ctrl_tau == TapPhaseControl.Pt:
                u_cbr_tau.append(k)
                k_cbr_pt.append(k)
                cbr_pt_set.append(self.nc.active_branch_data.Pset[k])

            elif ctrl_tau == TapPhaseControl.fixed:
                pass

            elif ctrl_tau == 0:
                pass

            else:
                raise Exception(f"Unknown tap phase control mode {ctrl_tau}")

        self.u_cbr_m = np.array(u_cbr_m, dtype=int)
        self.u_cbr_tau = np.array(u_cbr_tau, dtype=int)
        self.cbr = np.array(cbr, dtype=int)
        self.k_cbr_pf = np.array(k_cbr_pf, dtype=int)
        self.k_cbr_pt = np.array(k_cbr_pt, dtype=int)
        self.k_cbr_qf = np.array(k_cbr_qf, dtype=int)
        self.k_cbr_qt = np.array(k_cbr_qt, dtype=int)
        self.cbr_pf_set = np.array(cbr_pf_set, dtype=float)
        self.cbr_pt_set = np.array(cbr_pt_set, dtype=float)
        self.cbr_qf_set = np.array(cbr_qf_set, dtype=float)
        self.cbr_qt_set = np.array(cbr_qt_set, dtype=float)

    def analyze_vsc_controls(self) -> None:
        """
        Analyze the control branches and compute the indices
        :return: None
        """

        # VSC Indices
        # vsc = list()
        u_vsc_pf = list()
        u_vsc_pt = list()
        u_vsc_qt = list()
        k_vsc_pf = list()
        k_vsc_pt = list()
        k_vsc_qt = list()
        vsc_pf_set = list()
        vsc_pt_set = list()
        vsc_qt_set = list()

        # VSC LOOP
        for k in range(self.nc.vsc_data.nelm):
            # vsc.append(i)
            control1 = self.nc.vsc_data.control1[k]
            control2 = self.nc.vsc_data.control2[k]
            assert control1 != control2, f"VSC control types must be different for VSC indexed at {k}"
            control1_magnitude = self.nc.vsc_data.control1_val[k]
            control2_magnitude = self.nc.vsc_data.control2_val[k]
            control1_bus_device = self.nc.vsc_data.control1_bus_idx[k]
            control2_bus_device = self.nc.vsc_data.control2_bus_idx[k]
            control1_branch_device = self.nc.vsc_data.control1_branch_idx[k]
            control2_branch_device = self.nc.vsc_data.control2_branch_idx[k]

            """"    

            Vm_dc = 'Vm_dc'
            Vm_ac = 'Vm_ac'
            Va_ac = 'Va_ac'
            Qac = 'Q_ac'
            Pdc = 'P_dc'
            Pac = 'P_ac'


            """
            if control1 == ConverterControlType.Vm_dc:
                if control2 == ConverterControlType.Vm_dc:
                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")
                elif control2 == ConverterControlType.Vm_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                elif control2 == ConverterControlType.Va_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        self.is_va_controlled[control2_bus_device] = True
                elif control2 == ConverterControlType.Qac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass

                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass

                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pdc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass

                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass

                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                else:
                    raise Exception(f"Unknown control type {control2}")

            elif control1 == ConverterControlType.Vm_ac:
                if control2 == ConverterControlType.Vm_dc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                elif control2 == ConverterControlType.Vm_ac:
                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")

                elif control2 == ConverterControlType.Va_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        self.is_va_controlled[control2_bus_device] = True

                elif control2 == ConverterControlType.Qac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pdc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                else:
                    raise Exception(f"Unknown control type {control2}")

            elif control1 == ConverterControlType.Va_ac:
                if control2 == ConverterControlType.Vm_dc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True

                elif control2 == ConverterControlType.Vm_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True

                elif control2 == ConverterControlType.Va_ac:
                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")

                elif control2 == ConverterControlType.Qac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pdc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                else:
                    raise Exception(f"Unknown control type {control2}")

            elif control1 == ConverterControlType.Qac:
                if control2 == ConverterControlType.Vm_dc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass


                elif control2 == ConverterControlType.Vm_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass

                elif control2 == ConverterControlType.Va_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Qac:
                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")
                elif control2 == ConverterControlType.Pdc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Pac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                else:
                    raise Exception(f"Unknown control type {control2}")

            elif control1 == ConverterControlType.Pdc:
                if control2 == ConverterControlType.Vm_dc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Vm_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Va_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Qac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pdc:
                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")
                elif control2 == ConverterControlType.Pac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                else:
                    raise Exception(f"Unknown control type {control2}")

            elif control1 == ConverterControlType.Pac:
                if control2 == ConverterControlType.Vm_dc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Vm_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Va_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Qac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        vsc_qt_set.append(control2_magnitude)
                elif control2 == ConverterControlType.Pdc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pac:
                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")
                else:
                    raise Exception(f"Unknown control type {control2}")

            else:
                raise Exception(f"Unknown control type {control1}")

        # self.vsc = np.array(vsc, dtype=int)
        self.u_vsc_pf = np.array(u_vsc_pf, dtype=int)
        self.u_vsc_pt = np.array(u_vsc_pt, dtype=int)
        self.u_vsc_qt = np.array(u_vsc_qt, dtype=int)
        self.k_vsc_pf = np.array(k_vsc_pf, dtype=int)
        self.k_vsc_pt = np.array(k_vsc_pt, dtype=int)
        self.k_vsc_qt = np.array(k_vsc_qt, dtype=int)
        self.vsc_pf_set = np.array(vsc_pf_set, dtype=float)
        self.vsc_pt_set = np.array(vsc_pt_set, dtype=float)
        self.vsc_qt_set = np.array(vsc_qt_set, dtype=float)

    def analyze_hvdc_controls(self) -> None:
        """
        Analyze the control branches and compute the indices
        :return: None
        """

        # HVDC Indices
        # hvdc = list()
        hvdc_droop_idx = list()

        # HVDC LOOP
        for k in range(self.nc.hvdc_data.nelm):
            # hvdc.append(k)
            if self.nc.hvdc_data.control_mode[k] == HvdcControlType.type_0_free:
                hvdc_droop_idx.append(k)

        # self.hvdc = np.array(hvdc, dtype=int)
        self.hvdc_droop_idx = np.array(hvdc_droop_idx)

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
        f = e + self.nc.hvdc_data.nelm
        g = f + self.nc.hvdc_data.nelm
        h = g + self.nc.hvdc_data.nelm
        i = h + self.nc.hvdc_data.nelm
        j = i + len(self.u_cbr_m)
        k = j + len(self.u_cbr_tau)

        # update the vectors
        self.Vm[self.i_u_vm] = x[0:a]
        self.Va[self.i_u_va] = x[a:b]
        self.Pf_vsc[self.u_vsc_pf] = x[b:c]
        self.Pt_vsc[self.u_vsc_pt] = x[c:d]
        self.Qt_vsc[self.u_vsc_qt] = x[d:e]
        self.Pf_hvdc = x[e:f]
        self.Pt_hvdc = x[f:g]
        self.Qf_hvdc = x[g:h]
        self.Qt_hvdc = x[h:i]
        self.m = x[i:j]
        self.tau = x[j:k]

    def var2x(self) -> Vec:
        """
        Convert the internal decision variables into the vector
        :return: Vector
        """
        return np.r_[
            self.Vm[self.i_u_vm],
            self.Va[self.i_u_va],
            self.Pf_vsc[self.u_vsc_pf],
            self.Pt_vsc[self.u_vsc_pt],
            self.Qt_vsc[self.u_vsc_qt],
            self.Pf_hvdc,
            self.Pt_hvdc,
            self.Qf_hvdc,
            self.Qt_hvdc,
            self.m,
            self.tau
        ]

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
                + self.nc.hvdc_data.nelm
                + self.nc.hvdc_data.nelm
                + self.nc.hvdc_data.nelm
                + self.nc.hvdc_data.nelm
                + len(self.u_cbr_m)
                + len(self.u_cbr_tau))

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
        f = e + self.nc.hvdc_data.nelm
        g = f + self.nc.hvdc_data.nelm
        h = g + self.nc.hvdc_data.nelm
        i = h + self.nc.hvdc_data.nelm
        j = i + len(self.u_cbr_m)
        k = j + len(self.u_cbr_tau)

        # copy the sliceable vectors
        Vm = self.Vm.copy()
        Va = self.Va.copy()
        V = polar_to_rect(Vm, Va)
        Pf_vsc = self.Pf_vsc.copy()
        Pt_vsc = self.Pt_vsc.copy()
        Qt_vsc = self.Qt_vsc.copy()

        # update the vectors
        Vm[self.i_u_vm] = x[0:a]
        Va[self.i_u_va] = x[a:b]
        Pf_vsc[self.u_vsc_pf] = x[b:c]
        Pt_vsc[self.u_vsc_pt] = x[c:d]
        Qt_vsc[self.u_vsc_qt] = x[d:e]
        Pf_hvdc = x[e:f]
        Pt_hvdc = x[f:g]
        Qf_hvdc = x[g:h]
        Qt_hvdc = x[h:i]
        m = x[i:j]
        tau = x[j:k]

        # Controllable branches ----------------------------------------------------------------------------------------

        yff = (self.yff_cbr * (m * m) / (m * m))
        yft = self.yft_cbr * (m * np.exp(-1.0j * tau)) / (m * np.exp(-1.0j * tau))
        ytf = self.ytf_cbr * (m * np.exp(1.0j * tau)) / (m * np.exp(1.0j * tau))
        ytt = self.ytt_cbr
        Vf_cbr = V[self.F_cbr]
        Vt_cbr = V[self.T_cbr]
        Sf_cbr = (np.power(Vf_cbr, 2.0) * np.conj(yff) + Vf_cbr * Vt_cbr * np.conj(yft))
        St_cbr = (np.power(Vt_cbr, 2.0) * np.conj(ytt) + Vt_cbr * Vf_cbr * np.conj(ytf))
        Scalc_cbr = (self.nc.passive_branch_data.C_branch_bus_f @ Sf_cbr
                     + self.nc.passive_branch_data.C_branch_bus_t @ St_cbr)

        #
        m2 = self.nc.active_branch_data.tap_module.copy()
        m2[self.u_cbr_m] = m
        tau2 = self.nc.active_branch_data.tap_angle.copy()
        tau2[self.u_cbr_m] = tau
        Pf_cbr = calcSf(k=self.k_cbr_pf, V=V,
                        F=self.nc.passive_branch_data.F,
                        T=self.nc.passive_branch_data.T,
                        R=self.nc.passive_branch_data.R,
                        X=self.nc.passive_branch_data.X,
                        G=self.nc.passive_branch_data.G,
                        B=self.nc.passive_branch_data.B,
                        m=m2,
                        tau=tau2,
                        vtap_f=self.nc.passive_branch_data.virtual_tap_f,
                        vtap_t=self.nc.passive_branch_data.virtual_tap_t).real

        Pt_cbr = calcSt(k=self.k_cbr_pt, V=V,
                        F=self.nc.passive_branch_data.F,
                        T=self.nc.passive_branch_data.T,
                        R=self.nc.passive_branch_data.R,
                        X=self.nc.passive_branch_data.X,
                        G=self.nc.passive_branch_data.G,
                        B=self.nc.passive_branch_data.B,
                        m=m2,
                        tau=tau2,
                        vtap_f=self.nc.passive_branch_data.virtual_tap_f,
                        vtap_t=self.nc.passive_branch_data.virtual_tap_t).real

        Qf_cbr = calcSf(k=self.k_cbr_qf, V=V,
                        F=self.nc.passive_branch_data.F,
                        T=self.nc.passive_branch_data.T,
                        R=self.nc.passive_branch_data.R,
                        X=self.nc.passive_branch_data.X,
                        G=self.nc.passive_branch_data.G,
                        B=self.nc.passive_branch_data.B,
                        m=m2,
                        tau=tau2,
                        vtap_f=self.nc.passive_branch_data.virtual_tap_f,
                        vtap_t=self.nc.passive_branch_data.virtual_tap_t).imag

        Qt_cbr = calcSt(k=self.k_cbr_qt, V=V,
                        F=self.nc.passive_branch_data.F,
                        T=self.nc.passive_branch_data.T,
                        R=self.nc.passive_branch_data.R,
                        X=self.nc.passive_branch_data.X,
                        G=self.nc.passive_branch_data.G,
                        B=self.nc.passive_branch_data.B,
                        m=m2,
                        tau=tau2,
                        vtap_f=self.nc.passive_branch_data.virtual_tap_f,
                        vtap_t=self.nc.passive_branch_data.virtual_tap_t).imag

        Ybus = calcYbus(Cf=self.nc.passive_branch_data.C_branch_bus_f,
                        Ct=self.nc.passive_branch_data.C_branch_bus_t,
                        Yshunt_bus=self.nc.shunt_data.Y / self.nc.Sbase,  # TODO: Check p.u.
                        R=self.nc.passive_branch_data.R,
                        X=self.nc.passive_branch_data.X,
                        G=self.nc.passive_branch_data.G,
                        B=self.nc.passive_branch_data.B,
                        m=m2,
                        tau=tau2,
                        vtap_f=self.nc.passive_branch_data.virtual_tap_f,
                        vtap_t=self.nc.passive_branch_data.virtual_tap_t)

        # vsc ----------------------------------------------------------------------------------------------------------

        T_vsc = self.nc.vsc_data.T
        It = np.sqrt(Pt_vsc * Pt_vsc + Qt_vsc * Qt_vsc) / Vm[T_vsc]
        It2 = It * It
        PLoss_IEC = (self.nc.vsc_data.alpha3 * It2
                     + self.nc.vsc_data.alpha2 * It
                     + self.nc.vsc_data.alpha1)

        loss_vsc = PLoss_IEC - Pt_vsc - Pf_vsc
        St_vsc = Pt_vsc + 1j * Qt_vsc

        Scalc_vsc = self.nc.vsc_data.C_branch_bus_f @ Pf_vsc + self.nc.vsc_data.C_branch_bus_t @ St_vsc

        # HVDC ---------------------------------------------------------------------------------------------------------
        Vmf_hvdc = Vm[self.nc.hvdc_data.F]

        loss_hvdc = self.nc.hvdc_data.r * np.power(Pf_hvdc / Vmf_hvdc, 2.0)  # TODO: check compatible units!

        inj_hvdc = self.nc.hvdc_data.Pset
        if len(self.hvdc_droop_idx):
            Vaf_hvdc = Vm[self.nc.hvdc_data.F[self.hvdc_droop_idx]]
            Vat_hvdc = Vm[self.nc.hvdc_data.T[self.hvdc_droop_idx]]
            inj_hvdc[self.hvdc_droop_idx] += self.nc.hvdc_data.angle_droop[self.hvdc_droop_idx] * (Vaf_hvdc - Vat_hvdc)

        Sf_hvdc = Pf_hvdc + 1j * Qf_hvdc
        St_hvdc = Pt_hvdc + 1j * Qt_hvdc
        Scalc_hvdc = self.nc.hvdc_data.C_hvdc_bus_f @ Sf_hvdc + self.nc.hvdc_data.C_hvdc_bus_t @ St_hvdc

        # total nodal power --------------------------------------------------------------------------------------------
        Scalc_passive = V * np.conj(Ybus @ V)
        Scalc = Scalc_passive + Scalc_cbr + Scalc_vsc + Scalc_hvdc

        # compose the residuals vector ---------------------------------------------------------------------------------

        _f = np.r_[
            Scalc[self.i_k_p].real,
            Scalc[self.i_k_q].real,
            loss_vsc,
            loss_hvdc,
            inj_hvdc,
            Pf_cbr,
            Pt_cbr,
            Qf_cbr,
            Qt_cbr
        ]

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

        return self._f

    def Jacobian(self, autodiff: bool = True) -> CSC:
        """
        Get the Jacobian
        :return:
        """
        if autodiff:
            J = calc_autodiff_jacobian(func=self.compute_f,
                                       x=self.var2x(),
                                       h=self.options.tolerance / 100.0)

            if self.options.verbose > 1:
                print("(pf_generalized_formulation.py) J: ")
                print(J)
                print("J shape: ", J.shape)

            # Jdense = np.array(J.todense())
            # dff = pd.DataFrame(Jdense)
            # dff.to_excel("Jacobian_autodiff.xlsx")
            return J
        else:
            J = None

            # Jdense = np.array(J.todense())
            # dff = pd.DataFrame(Jdense)
            # dff.to_excel("Jacobian_symbolic.xlsx")
            return J

    def get_x_names(self) -> List[str]:
        """
        Names matching x
        :return:
        """
        cols = [f'dVm {i}' for i in self.i_u_vm]
        cols += [f'dVa {i}' for i in self.i_u_va]

        cols += [f'dPf_var_vsc {i}' for i in self.u_vsc_pf]
        cols += [f'dPt_var_vsc {i}' for i in self.u_vsc_pt]
        cols += [f'dQt_var_vsc {i}' for i in self.u_vsc_qt]

        cols += [f'dPf_hvdc {i}' for i in range(self.nc.hvdc_data.nelm)]
        cols += [f'dPt_hvdc {i}' for i in range(self.nc.hvdc_data.nelm)]
        cols += [f'dQf_hvdc {i}' for i in range(self.nc.hvdc_data.nelm)]
        cols += [f'dQt_hvdc {i}' for i in range(self.nc.hvdc_data.nelm)]

        cols += [f'dm {i}' for i in self.u_cbr_m]
        cols += [f'dtau {i}' for i in self.u_cbr_tau]

        return cols

    def get_fx_names(self) -> List[str]:
        """
        Names matching fx
        :return:
        """

        rows = [f'dP {i}' for i in self.i_k_p]
        rows += [f'dQ {i}' for i in self.i_k_q]
        rows += [f'dloss_vsc {i}' for i in range(self.nc.vsc_data.nelm)]
        rows += [f'dloss_hvdc {i}' for i in range(self.nc.hvdc_data.nelm)]
        rows += [f'dinj_hvdc {i}' for i in range(self.nc.hvdc_data.nelm)]

        rows += [f'dPf {i}' for i in self.k_cbr_pf]
        rows += [f'dPt {i}' for i in self.k_cbr_pt]
        rows += [f'dQf {i}' for i in self.k_cbr_qf]
        rows += [f'dQt {i}' for i in self.k_cbr_qt]

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

        # Branches -----------------------------------------------------------------------------------------------------
        # compute the flows, currents, losses for all branches

        V = self.Vm * np.exp(1j * self.Va)
        Vf = V[self.nc.passive_branch_data.F]
        Vt = V[self.nc.passive_branch_data.T]

        # compose all taps (m and tau)
        m = self.nc.active_branch_data.tap_module.copy()
        m[self.u_cbr_m] = self.m
        tau = self.nc.active_branch_data.tap_angle.copy()
        tau[self.u_cbr_m] = self.tau

        R = self.nc.passive_branch_data.R
        X = self.nc.passive_branch_data.X
        G = self.nc.passive_branch_data.G
        B = self.nc.passive_branch_data.B
        vtap_f = self.nc.passive_branch_data.virtual_tap_f
        vtap_t = self.nc.passive_branch_data.virtual_tap_t

        ys = 1.0 / (R + 1.0j * X + 1e-20)  # series admittance
        bc2 = (G + 1j * B) / 2.0  # shunt admittance
        yff = (ys + bc2) / (m * m * vtap_f * vtap_f)
        yft = -ys / (m * np.exp(-1.0j * tau) * vtap_f * vtap_t)
        ytf = -ys / (m * np.exp(1.0j * tau) * vtap_t * vtap_f)
        ytt = (ys + bc2) / (vtap_t * vtap_t)

        If = Vf * np.conj(yff) + Vt * np.conj(yft)  # TODO: review if this must be conj
        It = Vt * np.conj(ytt) + Vf * np.conj(ytf)  # TODO: review if this must be conj
        Sf = Vf * np.conj(If)
        St = Vt * np.conj(It)

        # Branch losses in MVA
        losses = (Sf + St) * self.nc.Sbase

        # branch voltage increment
        Vbranch = Vf - Vt

        # Branch loading in p.u.
        loading = Sf * self.nc.Sbase / (self.nc.passive_branch_data.rates + 1e-9)

        # VSC ----------------------------------------------------------------------------------------------------------
        Pf_vsc = self.Pf_hvdc
        St_vsc = (self.Pt_vsc + 1j * self.Qt_vsc)
        If_vsc = Pf_vsc / np.abs(V[self.nc.vsc_data.F])
        It_vsc = St_vsc / np.conj(V[self.nc.vsc_data.T])
        loading_vsc = abs(St_vsc) / (self.nc.vsc_data.rates + 1e-20) * self.nc.Sbase

        # HVDC ---------------------------------------------------------------------------------------------------------
        Sf_hvdc = (self.Pf_hvdc + 1j * self.Qf_hvdc) * self.nc.Sbase
        St_hvdc = (self.Pt_hvdc + 1j * self.Qt_hvdc) * self.nc.Sbase
        loading_hvdc = Sf_hvdc.real / (self.nc.hvdc_data.rate + 1e-20)

        return NumericPowerFlowResults(
            V=self.V,
            Scalc=self.Scalc,
            m=expand(self.nc.nbr, self.m, self.u_cbr_m, 1.0),
            tau=expand(self.nc.nbr, self.tau, self.u_cbr_tau, 0.0),
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
