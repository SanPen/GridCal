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
from typing import Tuple, List, Callable
import numpy as np
import pandas as pd
from numba import njit
from scipy.sparse import lil_matrix, csc_matrix
from GridCalEngine.Topology.admittance_matrices import compute_admittances
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
import GridCalEngine.Simulations.Derivatives.csc_derivatives as deriv
from GridCalEngine.Topology.simulation_indices import compile_types
from GridCalEngine.Utils.Sparse.csc2 import CSC, CxCSC, sp_slice, csc_stack_2d_ff, scipy_to_mat
from GridCalEngine.Utils.NumericalMethods.common import find_closest_number
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import expand
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import compute_fx_error
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import (control_q_inside_method,
                                                                                    compute_slack_distribution)
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.pf_formulation_template import PfFormulationTemplate
from GridCalEngine.enumerations import BusMode, TapPhaseControl, TapModuleControl
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import (compute_zip_power, compute_power,
                                                                                   polar_to_rect, get_Sf, get_St,
                                                                                   get_It)
from GridCalEngine.basic_structures import Vec, IntVec, CxVec, Logger


@njit()
def adv_jacobian(nbus: int,
                 nbr: int,
                 idx_dva: IntVec,
                 idx_dvm: IntVec,
                 idx_dm: IntVec,
                 idx_dtau: IntVec,
                 idx_dbeq: IntVec,
                 idx_dP: IntVec,
                 idx_dQ: IntVec,
                 idx_dPf: IntVec,
                 idx_dQf: IntVec,
                 idx_dPt: IntVec,
                 idx_dQt: IntVec,
                 F: IntVec,
                 T: IntVec,
                 Ys: CxVec,
                 kconv: Vec,
                 complex_tap: CxVec,
                 tap_modules: Vec,
                 Bc: Vec,
                 Beq: Vec,
                 V: CxVec,
                 Vm: Vec,
                 Ybus_x: CxVec,
                 Ybus_p: IntVec,
                 Ybus_i: IntVec,
                 yff: CxVec,
                 yft: CxVec,
                 ytf: CxVec,
                 ytt: CxVec) -> CSC:
    """
    Compute the advanced jacobian
    :param nbus:
    :param nbr:
    :param idx_dva:
    :param idx_dvm:
    :param idx_dm:
    :param idx_dtau:
    :param idx_dbeq:
    :param idx_dP:
    :param idx_dQ:
    :param idx_dQf:
    :param idx_dPf:
    :param idx_dPt:
    :param idx_dQt:
    :param F:
    :param T:
    :param Ys: Series admittance 1 / (R + jX)
    :param kconv:
    :param complex_tap:
    :param tap_modules:
    :param Bc: Total changing susceptance
    :param Beq:
    :param V:
    :param Vm:
    :param Ybus_x:
    :param Ybus_p:
    :param Ybus_i:
    :param yff:
    :param yft:
    :param ytf:
    :param ytt:
    :return:
    """
    # bus-bus derivatives (always needed)
    dS_dVm_x, dS_dVa_x = deriv.dSbus_dV_numba_sparse_csc(Ybus_x, Ybus_p, Ybus_i, V, Vm)
    dS_dVm = CxCSC(nbus, nbus, len(dS_dVm_x), False).set(Ybus_i, Ybus_p, dS_dVm_x)
    dS_dVa = CxCSC(nbus, nbus, len(dS_dVa_x), False).set(Ybus_i, Ybus_p, dS_dVa_x)

    dP_dVa__ = sp_slice(dS_dVa.real, idx_dP, idx_dva)
    dQ_dVa__ = sp_slice(dS_dVa.imag, idx_dQ, idx_dva)
    dPf_dVa_ = deriv.dSf_dVa_csc(nbus, idx_dPf, idx_dva, yff, yft, V, F, T).real
    dQf_dVa_ = deriv.dSf_dVa_csc(nbus, idx_dQf, idx_dva, yff, yft, V, F, T).imag
    dPt_dVa_ = deriv.dSt_dVa_csc(nbus, idx_dPt, idx_dva, ytf, V, F, T).real
    dQt_dVa_ = deriv.dSt_dVa_csc(nbus, idx_dQt, idx_dva, ytf, V, F, T).imag

    dP_dVm__ = sp_slice(dS_dVm.real, idx_dP, idx_dvm)
    dQ_dVm__ = sp_slice(dS_dVm.imag, idx_dQ, idx_dvm)
    dPf_dVm_ = deriv.dSf_dVm_csc(nbus, idx_dPf, idx_dvm, yff, yft, V, F, T).real
    dQf_dVm_ = deriv.dSf_dVm_csc(nbus, idx_dQf, idx_dvm, yff, yft, V, F, T).imag
    dPt_dVm_ = deriv.dSt_dVm_csc(nbus, idx_dPt, idx_dvm, ytt, ytf, V, F, T).real
    dQt_dVm_ = deriv.dSt_dVm_csc(nbus, idx_dQt, idx_dvm, ytt, ytf, V, F, T).imag

    dP_dm__ = deriv.dSbus_dm_csc(nbus, idx_dP, idx_dm, F, T, Ys, Bc, Beq, kconv, complex_tap, tap_modules, V).real
    dQ_dm__ = deriv.dSbus_dm_csc(nbus, idx_dQ, idx_dm, F, T, Ys, Bc, Beq, kconv, complex_tap, tap_modules, V).imag
    dPf_dm_ = deriv.dSf_dm_csc(nbr, idx_dPf, idx_dm, F, T, Ys, Bc, Beq, kconv, complex_tap, tap_modules, V).real
    dQf_dm_ = deriv.dSf_dm_csc(nbr, idx_dQf, idx_dm, F, T, Ys, Bc, Beq, kconv, complex_tap, tap_modules, V).imag
    dPt_dm_ = deriv.dSt_dm_csc(nbr, idx_dPt, idx_dm, F, T, Ys, kconv, complex_tap, tap_modules, V).real
    dQt_dm_ = deriv.dSt_dm_csc(nbr, idx_dQt, idx_dm, F, T, Ys, kconv, complex_tap, tap_modules, V).imag

    dP_dtau__ = deriv.dSbus_dtau_csc(nbus, idx_dP, idx_dtau, F, T, Ys, kconv, complex_tap, V).real
    dQ_dtau__ = deriv.dSbus_dtau_csc(nbus, idx_dQ, idx_dtau, F, T, Ys, kconv, complex_tap, V).imag
    dPf_dtau_ = deriv.dSf_dtau_csc(nbr, idx_dPf, idx_dtau, F, T, Ys, kconv, complex_tap, V).real
    dQf_dtau_ = deriv.dSf_dtau_csc(nbr, idx_dQf, idx_dtau, F, T, Ys, kconv, complex_tap, V).imag
    dPt_dtau_ = deriv.dSt_dtau_csc(nbr, idx_dPt, idx_dtau, F, T, Ys, kconv, complex_tap, V).real
    dQt_dtau_ = deriv.dSt_dtau_csc(nbr, idx_dQt, idx_dtau, F, T, Ys, kconv, complex_tap, V).imag

    dP_dbeq__ = deriv.dSbus_dbeq_csc(nbus, idx_dP, idx_dbeq, F, kconv, tap_modules, V).real
    dQ_dbeq__ = deriv.dSbus_dbeq_csc(nbus, idx_dQ, idx_dbeq, F, kconv, tap_modules, V).imag
    dPf_dbeq_ = deriv.dSf_dbeq_csc(nbr, idx_dPf, idx_dbeq, F, kconv, tap_modules, V).real
    dQf_dbeq_ = deriv.dSf_dbeq_csc(nbr, idx_dQf, idx_dbeq, F, kconv, tap_modules, V).imag
    dPt_dbeq_ = deriv.dSt_dbeq_csc(idx_dPt, idx_dbeq).real
    dQt_dbeq_ = deriv.dSt_dbeq_csc(idx_dQt, idx_dbeq).imag

    # compose the Jacobian
    J = csc_stack_2d_ff(mats=
                        [dP_dVa__, dP_dVm__, dP_dm__, dP_dtau__, dP_dbeq__,
                         dQ_dVa__, dQ_dVm__, dQ_dm__, dQ_dtau__, dQ_dbeq__,
                         dPf_dVa_, dPf_dVm_, dPf_dm_, dPf_dtau_, dPf_dbeq_,
                         dQf_dVa_, dQf_dVm_, dQf_dm_, dQf_dtau_, dQf_dbeq_,
                         dPt_dVa_, dPt_dVm_, dPt_dm_, dPt_dtau_, dPt_dbeq_,
                         dQt_dVa_, dQt_dVm_, dQt_dm_, dQt_dtau_, dQt_dbeq_],
                        n_rows=6, n_cols=5)

    return J


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


class PfAdvancedFormulation(PfFormulationTemplate):

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
        :param Qmin: Minimum reactive power per bus
        :param Qmax: Maximum reactive power per bus
        :param nc: NumericalCircuit
        :param options: PowerFlowOptions
        :param logger: Logger (modified in-place)
        """
        PfFormulationTemplate.__init__(self, V0=V0, options=options)

        self.nc: NumericalCircuit = nc

        self.logger: Logger = logger

        self.S0: CxVec = S0
        self.I0: CxVec = I0
        self.Y0: CxVec = Y0

        self.Qmin = Qmin
        self.Qmax = Qmax

        self.bus_types = self.nc.bus_data.bus_types.copy()
        self.tap_module_control_mode = self.nc.branch_data.tap_module_control_mode.copy()
        self.tap_phase_control_mode = self.nc.branch_data.tap_phase_control_mode.copy()

        self.pq = np.array(0, dtype=int)
        self.pv = np.array(0, dtype=int)
        self.pqv = np.array(0, dtype=int)
        self.p = np.array(0, dtype=int)
        self.idx_conv = np.array(0, dtype=int)

        self.idx_dVa = np.array(0, dtype=int)
        self.idx_dVm = np.array(0, dtype=int)
        self.idx_dP = np.array(0, dtype=int)
        self.idx_dQ = np.array(0, dtype=int)

        self.idx_dm = np.array(0, dtype=int)
        self.idx_dtau = np.array(0, dtype=int)
        self.idx_dbeq = np.array(0, dtype=int)

        self.idx_dPf = np.array(0, dtype=int)
        self.idx_dQf = np.array(0, dtype=int)

        self.idx_dPt = np.array(0, dtype=int)
        self.idx_dQt = np.array(0, dtype=int)

        k_v_m = self.analyze_branch_controls()  # this fills the indices above
        self.vd, pq, pv, pqv, p, self.no_slack = compile_types(
            Pbus=self.nc.Sbus.real,
            types=self.bus_types
        )
        self.update_bus_types(pq=pq, pv=pv, pqv=pqv, p=p)

        self.m: Vec = self.nc.branch_data.tap_module[self.idx_dm]
        self.tau: Vec = self.nc.branch_data.tap_angle[self.idx_dtau]
        self.beq: Vec = self.nc.branch_data.Beq[self.idx_dbeq]

        self.Gsw = self.nc.branch_data.G0sw[self.idx_conv]

        self.Ys: CxVec = self.nc.branch_data.get_series_admittance()

        self.adm = compute_admittances(
            R=self.nc.branch_data.R,
            X=self.nc.branch_data.X,
            G=self.nc.branch_data.G,
            B=self.nc.branch_data.B,
            k=self.nc.branch_data.k,
            tap_module=expand(self.nc.nbr, self.m, self.idx_dm, 1.0),
            vtap_f=self.nc.branch_data.virtual_tap_f,
            vtap_t=self.nc.branch_data.virtual_tap_t,
            tap_angle=expand(self.nc.nbr, self.tau, self.idx_dtau, 0.0),
            Beq=expand(self.nc.nbr, self.beq, self.idx_dbeq, 0.0),
            Cf=self.nc.Cf,
            Ct=self.nc.Ct,
            Gsw=expand(self.nc.nbr, self.Gsw, self.idx_conv, 0.0),
            Yshunt_bus=self.nc.Yshunt_from_devices,
            conn=self.nc.branch_data.conn,
            seq=1,
            add_windings_phase=False
        )

        if not len(self.pqv) >= len(k_v_m):
            raise ValueError("k_v_m indices must be the same size as pqv indices!")

    def update_bus_types(self, pq: IntVec, pv: IntVec, pqv: IntVec, p: IntVec) -> None:
        """
        Update the bus types
        :param pq: Array of PQ indices
        :param pv: Array of PV indices
        :param pqv: Array of PQV indices
        :param p: Array of P indices
        """
        self.pq = pq
        self.pv = pv
        self.pqv = pqv
        self.p = p

        self.idx_dVa = np.r_[self.pqv, self.pv, self.pq, self.p]
        self.idx_dVm = np.r_[self.pq, self.p]
        self.idx_dP = self.idx_dVa
        self.idx_dQ = np.r_[self.pq, self.pqv]

    def analyze_branch_controls(self) -> List[int]:
        """
        Analyze the control branches and compute the indices
        :return: k_v_m for later comparison with pqv
        """
        k_pf_tau = list()
        k_pt_tau = list()
        k_qf_m = list()
        k_qt_m = list()
        k_qfzero_beq = list()
        k_v_m = list()
        k_v_beq = list()
        k_vsc = list()

        nbr = len(self.tap_phase_control_mode)
        for k in range(nbr):

            ctrl_m = self.tap_module_control_mode[k]
            ctrl_tau = self.tap_phase_control_mode[k]
            is_conv = self.nc.branch_data.is_converter[k]

            conv_type = 1 if is_conv else 0

            # analyze tap-module controls
            if ctrl_m == TapModuleControl.Vm:

                # Every bus controlled by m has to become a PQV bus
                bus_idx = self.nc.branch_data.tap_controlled_buses[k]
                self.bus_types[bus_idx] = BusMode.PQV_tpe.value

                if is_conv and bus_idx == self.nc.branch_data.F[k]:
                    # if this is a converter,
                    # the voltage can be managed with Beq
                    # if the control bus is the "From" bus
                    k_v_beq.append(k)
                    conv_type = 2
                else:
                    # In any other case, the voltage is managed by the tap module
                    k_v_m.append(k)

            elif ctrl_m == TapModuleControl.Qf:

                if not is_conv:
                    k_qf_m.append(k)

            elif ctrl_m == TapModuleControl.Qt:
                k_qt_m.append(k)

            elif ctrl_m == TapModuleControl.fixed:
                pass

            elif ctrl_m == 0:
                pass

            else:
                raise Exception(f"Unknown tap phase module mode {ctrl_m}")

            # analyze tap-phase controls
            if ctrl_tau == TapPhaseControl.Pf:
                k_pf_tau.append(k)
                # conv_type = 1

            elif ctrl_tau == TapPhaseControl.Pt:
                k_pt_tau.append(k)
                # conv_type = 1

            elif ctrl_tau == TapPhaseControl.fixed:
                if ctrl_m == TapModuleControl.fixed:
                    conv_type = 1

            # elif ctrl_tau == TapPhaseControl.Droop:
            #     pass

            elif ctrl_tau == 0:
                pass

            else:
                raise Exception(f"Unknown tap phase control mode {ctrl_tau}")

            # Beq->qf=0
            if conv_type == 1:
                k_qfzero_beq.append(k)

            if is_conv:
                k_vsc.append(k)

        # turn the lists into the final arrays
        self.idx_conv = np.array(k_vsc, dtype=int)

        self.idx_dm = np.r_[k_v_m, k_qf_m, k_qt_m].astype(int)
        self.idx_dtau = np.r_[k_pf_tau, k_pt_tau].astype(int)
        self.idx_dbeq = np.r_[k_qfzero_beq, k_v_beq].astype(int)

        self.idx_dPf = np.array(k_pf_tau, dtype=int)
        self.idx_dQf = np.r_[k_qf_m, k_qfzero_beq].astype(int)

        self.idx_dPt = np.array(k_pt_tau, dtype=int)
        self.idx_dQt = np.array(k_qt_m, dtype=int)

        self.m: Vec = self.nc.branch_data.tap_module[self.idx_dm]
        self.tau: Vec = self.nc.branch_data.tap_angle[self.idx_dtau]
        self.beq: Vec = self.nc.branch_data.Beq[self.idx_dbeq]

        self.Gsw = self.nc.branch_data.G0sw[self.idx_conv]

        return k_v_m

    def x2var(self, x: Vec) -> None:
        """
        Convert X to decission variables
        :param x: solution vector
        """
        a = len(self.idx_dVa)
        b = a + len(self.idx_dVm)
        c = b + len(self.idx_dm)
        d = c + len(self.idx_dtau)
        e = d + len(self.idx_dbeq)

        # update the vectors
        self.Va[self.idx_dVa] = x[0:a]
        self.Vm[self.idx_dVm] = x[a:b]
        self.m = x[b:c]
        self.tau = x[c:d]
        self.beq = x[d:e]

    def var2x(self) -> Vec:
        """
        Convert the internal decission variables into the vector
        :return: Vector
        """
        return np.r_[
            self.Va[self.idx_dVa],
            self.Vm[self.idx_dVm],
            self.m,
            self.tau,
            self.beq,
        ]

    def size(self) -> int:
        """
        Size of the jacobian matrix
        :return:
        """
        return (len(self.idx_dVa)
                + len(self.idx_dVm)
                + len(self.idx_dm)
                + len(self.idx_dtau)
                + len(self.idx_dbeq))

    def update(self, x: Vec, update_controls: bool = False) -> Tuple[float, bool, Vec, Vec]:
        """
        Update step
        :param x: Solution vector
        :param update_controls:
        :return: error, converged?, x, fx
        """
        # set the problem state
        self.x2var(x)

        # recompute admittances
        self.adm = compute_admittances(
            R=self.nc.branch_data.R,
            X=self.nc.branch_data.X,
            G=self.nc.branch_data.G,
            B=self.nc.branch_data.B,
            k=self.nc.branch_data.k,
            tap_module=expand(self.nc.nbr, self.m, self.idx_dm, 1.0),
            vtap_f=self.nc.branch_data.virtual_tap_f,
            vtap_t=self.nc.branch_data.virtual_tap_t,
            tap_angle=expand(self.nc.nbr, self.tau, self.idx_dtau, 0.0),
            Beq=expand(self.nc.nbr, self.beq, self.idx_dbeq, 0.0),
            Cf=self.nc.Cf,
            Ct=self.nc.Ct,
            Gsw=expand(self.nc.nbr, self.Gsw, self.idx_conv, 0.0),
            Yshunt_bus=self.nc.Yshunt_from_devices,
            conn=self.nc.branch_data.conn,
            seq=1,
            add_windings_phase=False,
            verbose=self.options.verbose,
        )

        # compute the complex voltage
        self.V = polar_to_rect(self.Vm, self.Va)

        # Update converter losses
        It = get_It(k=self.idx_conv, V=self.V, ytf=self.adm.ytf, ytt=self.adm.ytt, F=self.nc.F, T=self.nc.T)
        Itm = np.abs(It)
        Itm2 = Itm * Itm
        PLoss_IEC = (self.nc.branch_data.alpha3[self.idx_conv] * Itm2
                     + self.nc.branch_data.alpha2[self.idx_conv] * Itm2
                     + self.nc.branch_data.alpha1[self.idx_conv])

        self.Gsw = PLoss_IEC / np.power(self.Vm[self.nc.F[self.idx_conv]], 2.0)

        # compute the function residual
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
            Pf - self.nc.branch_data.Pset[self.idx_dPf],
            Qf - self.nc.branch_data.Qset[self.idx_dQf],
            Pt - self.nc.branch_data.Pset[self.idx_dPt],
            Qt - self.nc.branch_data.Qset[self.idx_dQt]
        ]

        # compute the rror
        self._error = compute_fx_error(self._f)

        if self.options.verbose > 1:
            print("Vm:", self.Vm)
            print("Va:", self.Va)
            print("tau:", self.tau)
            print("beq:", self.beq)
            print("m:", self.m)
            print("Gsw:", self.Gsw)

        # Update controls only below a certain error
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

                # compute the rror
                self._error = compute_fx_error(self._f)

        # converged?
        self._converged = self._error < self.options.tolerance

        return self._error, self._converged, x, self.f

    def fx(self) -> Vec:
        """

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
            Pf - self.nc.branch_data.Pset[self.idx_dPf],
            Qf - self.nc.branch_data.Qset[self.idx_dQf],
            Pt - self.nc.branch_data.Pset[self.idx_dPt],
            Qt - self.nc.branch_data.Qset[self.idx_dQt]
        ]
        return self._f

    def fx_diff(self, x: Vec) -> Vec:
        """
        Fx for autodiff
        :param x: solutions vector
        :return: f(x)
        """
        a = len(self.idx_dVa)
        b = a + len(self.idx_dVm)
        c = b + len(self.idx_dm)
        d = c + len(self.idx_dtau)
        e = d + len(self.idx_dbeq)

        # update the vectors
        Va = self.Va.copy()
        Vm = self.Vm.copy()
        m = np.ones(self.nc.nbr, dtype=float)
        tau = np.zeros(self.nc.nbr, dtype=float)
        beq = np.zeros(self.nc.nbr, dtype=float)

        Va[self.idx_dVa] = x[0:a]
        Vm[self.idx_dVm] = x[a:b]
        m[self.idx_dm] = x[b:c]
        tau[self.idx_dtau] = x[c:d]
        beq[self.idx_dbeq] = x[d:e]

        # compute the complex voltage
        V = polar_to_rect(Vm, Va)

        adm = compute_admittances(
            R=self.nc.branch_data.R,
            X=self.nc.branch_data.X,
            G=self.nc.branch_data.G,
            B=self.nc.branch_data.B,
            k=self.nc.branch_data.k,
            tap_module=m,
            vtap_f=self.nc.branch_data.virtual_tap_f,
            vtap_t=self.nc.branch_data.virtual_tap_t,
            tap_angle=tau,
            Beq=beq,
            Cf=self.nc.Cf,
            Ct=self.nc.Ct,
            Gsw=expand(self.nc.nbr, self.Gsw, self.idx_conv, 0.0),
            Yshunt_bus=self.nc.Yshunt_from_devices,
            conn=self.nc.branch_data.conn,
            seq=1,
            add_windings_phase=False
        )

        Sbus = compute_zip_power(self.S0, self.I0, self.Y0, Vm)
        Scalc = compute_power(adm.Ybus, V)

        dS = Scalc - Sbus  # compute the mismatch

        Pf = get_Sf(k=self.idx_dPf, Vm=Vm, V=V, yff=adm.yff, yft=adm.yft, F=self.nc.F, T=self.nc.T).real
        Qf = get_Sf(k=self.idx_dQf, Vm=Vm, V=V, yff=adm.yff, yft=adm.yft, F=self.nc.F, T=self.nc.T).real
        Pt = get_St(k=self.idx_dPt, Vm=Vm, V=V, ytf=adm.ytf, ytt=adm.ytt, F=self.nc.F, T=self.nc.T).real
        Qt = get_St(k=self.idx_dQt, Vm=Vm, V=V, ytf=adm.ytf, ytt=adm.ytt, F=self.nc.F, T=self.nc.T).real

        f = np.r_[
            dS[self.idx_dP].real,
            dS[self.idx_dQ].imag,
            Pf - self.nc.branch_data.Pset[self.idx_dPf],
            Qf - self.nc.branch_data.Qset[self.idx_dQf],
            Pt - self.nc.branch_data.Pset[self.idx_dPt],
            Qt - self.nc.branch_data.Qset[self.idx_dQt]
        ]
        return f

    def Jacobian(self, autodiff: bool = False) -> CSC:
        """
        Get the Jacobian
        :return:
        """
        if autodiff:
            J = calc_autodiff_jacobian(func=self.fx_diff, x=self.var2x(), h=1e-12)
            return scipy_to_mat(J)
        else:
            n_rows = (len(self.idx_dP)
                      + len(self.idx_dQ)
                      + len(self.idx_dPf)
                      + len(self.idx_dQf)
                      + len(self.idx_dPt)
                      + len(self.idx_dQt))

            n_cols = (len(self.idx_dVa)
                      + len(self.idx_dVm)
                      + len(self.idx_dm)
                      + len(self.idx_dtau)
                      + len(self.idx_dbeq))

            if n_cols != n_rows:
                raise ValueError("Incorrect J indices!")

            tap_modules = expand(self.nc.nbr, self.m, self.idx_dm, 1.0)
            tap_angles = expand(self.nc.nbr, self.tau, self.idx_dtau, 0.0)
            tap = polar_to_rect(tap_modules, tap_angles)

            J = adv_jacobian(nbus=self.nc.nbus,
                             nbr=self.nc.nbr,
                             idx_dva=self.idx_dVa,
                             idx_dvm=self.idx_dVm,
                             idx_dm=self.idx_dm,
                             idx_dtau=self.idx_dtau,
                             idx_dbeq=self.idx_dbeq,
                             idx_dP=self.idx_dP,
                             idx_dQ=self.idx_dQ,
                             idx_dPf=self.idx_dPf,
                             idx_dQf=self.idx_dQf,
                             idx_dPt=self.idx_dPt,
                             idx_dQt=self.idx_dQt,
                             F=self.nc.F,
                             T=self.nc.T,
                             Ys=self.Ys,
                             kconv=self.nc.branch_data.k,
                             complex_tap=tap,
                             tap_modules=tap_modules,
                             Bc=self.nc.branch_data.B,
                             Beq=expand(self.nc.nbr, self.beq, self.idx_dbeq, 0.0),
                             V=self.V,
                             Vm=self.Vm,
                             Ybus_x=self.adm.Ybus.data,
                             Ybus_p=self.adm.Ybus.indptr,
                             Ybus_i=self.adm.Ybus.indices,
                             yff=self.adm.yff,
                             yft=self.adm.yft,
                             ytf=self.adm.ytf,
                             ytt=self.adm.ytt)

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
        rows = [f'dP {i}' for i in self.idx_dP]
        rows += [f'dQ {i}' for i in self.idx_dQ]
        rows += [f'dPf {i}' for i in self.idx_dPf]
        rows += [f'dQf {i}' for i in self.idx_dQf]
        rows += [f'dPt {i}' for i in self.idx_dPt]
        rows += [f'dQt {i}' for i in self.idx_dQt]

        return rows

    def get_jacobian_df(self, autodiff=True) -> pd.DataFrame:
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
        return NumericPowerFlowResults(V=self.V,
                                       converged=self.converged,
                                       norm_f=self.error,
                                       Scalc=self.Scalc,
                                       m=expand(self.nc.nbr, self.m, self.idx_dm, 1.0),
                                       tau=expand(self.nc.nbr, self.tau, self.idx_dtau, 0.0),
                                       Beq=expand(self.nc.nbr, self.beq, self.idx_dbeq, 0.0),
                                       Ybus=self.adm.Ybus,
                                       Yf=self.adm.Yf,
                                       Yt=self.adm.Yt,
                                       iterations=iterations,
                                       elapsed=elapsed)
