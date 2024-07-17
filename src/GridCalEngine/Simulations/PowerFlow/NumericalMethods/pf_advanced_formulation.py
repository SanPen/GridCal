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
from typing import Tuple
import numpy as np
from numba import njit
from GridCalEngine.Topology.admittance_matrices import AdmittanceMatrices
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.enumerations import ReactivePowerControlMode
import GridCalEngine.Simulations.derivatives.csc_derivatives as deriv
from GridCalEngine.Utils.Sparse.csc2 import CSC, CxCSC, sp_slice, csc_stack_2d_ff, spsolve_csc
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import compute_fx_error
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import control_q_inside_method
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.pf_formulation_template import PfFormulationTemplate
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import (compute_zip_power, compute_power,
                                                                                   compute_fx, polar_to_rect)
from GridCalEngine.basic_structures import Vec, IntVec, CxVec


# @njit()
def adv_jacobian(nbus: int,
                 idx_dtheta: IntVec,
                 idx_dvm: IntVec,
                 idx_dm: IntVec,
                 idx_dtau: IntVec,
                 idx_dbeq: IntVec,
                 idx_dP: IntVec,
                 idx_dQ: IntVec,
                 idx_dQf: IntVec,
                 idx_dPf: IntVec,
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
                 yft: CxVec) -> CSC:
    """

    :param nbus:
    :param idx_dtheta:
    :param idx_dvm:
    :param idx_dm:
    :param idx_dtau:
    :param idx_dbeq:
    :param idx_dP:
    :param idx_dQ:
    :param idx_dQf:
    :param idx_dPf:
    :param F:
    :param T:
    :param Ys:
    :param kconv:
    :param complex_tap:
    :param tap_modules:
    :param Bc:
    :param Beq:
    :param V:
    :param Vm:
    :param Ybus_x:
    :param Ybus_p:
    :param Ybus_i:
    :param yff:
    :param yft:
    :return:
    """
    # bus-bus derivatives (always needed)
    dS_dVm_x, dS_dVa_x = deriv.dSbus_dV_numba_sparse_csc(Ybus_x, Ybus_p, Ybus_i, V, Vm)

    dS_dVm = CxCSC(nbus, nbus, len(dS_dVm_x), False)
    dS_dVm.set(Ybus_i, Ybus_p, dS_dVm_x)

    dS_dVa = CxCSC(nbus, nbus, len(dS_dVa_x), False)
    dS_dVa.set(Ybus_i, Ybus_p, dS_dVa_x)

    dP_dVa__ = sp_slice(dS_dVa.real, idx_dP, idx_dtheta)
    dQ_dVa__ = sp_slice(dS_dVa.imag, idx_dQ, idx_dtheta)
    dQf_dVa_ = deriv.dSf_dVa_csc(nbus, idx_dQf, idx_dtheta, yff, yft, V, F, T).imag
    dPf_dVa_ = deriv.dSf_dVa_csc(nbus, idx_dPf, idx_dtheta, yff, yft, V, F, T).real

    dP_dVm__ = sp_slice(dS_dVm.real, idx_dP, idx_dvm)
    dQ_dVm__ = sp_slice(dS_dVm.imag, idx_dQ, idx_dvm)
    dQf_dVm_ = deriv.dSf_dVm_csc(nbus, idx_dQf, idx_dtheta, yff, yft, V, F, T).imag
    dPf_dVm_ = deriv.dSf_dVm_csc(nbus, idx_dPf, idx_dtheta, yff, yft, V, F, T).real

    dP_dbeq__ = deriv.dSbus_dbeq_csc(nbus, idx_dP, idx_dbeq, F, kconv, tap_modules, V).real
    dQ_dbeq__ = deriv.dSbus_dbeq_csc(nbus, idx_dQ, idx_dbeq, F, kconv, tap_modules, V).imag
    dQf_dbeq_ = deriv.dSf_dbeq_csc(idx_dQ, idx_dbeq, F, kconv, tap_modules, V).imag
    dPf_dbeq_ = deriv.dSf_dbeq_csc(idx_dPf, idx_dbeq, F, kconv, tap_modules, V).real

    dP_dm__ = deriv.dSbus_dm_csc(nbus, idx_dP, idx_dm, F, T, Ys, Bc, Beq, kconv, complex_tap, tap_modules, V).real
    dQ_dm__ = deriv.dSbus_dm_csc(nbus, idx_dQ, idx_dm, F, T, Ys, Bc, Beq, kconv, complex_tap, tap_modules, V).imag
    dQf_dm_ = deriv.dSf_dm_csc(idx_dQf, idx_dm, F, T, Ys, Bc, Beq, kconv, complex_tap, tap_modules, V).imag
    dPf_dm_ = deriv.dSf_dm_csc(idx_dPf, idx_dm, F, T, Ys, Bc, Beq, kconv, complex_tap, tap_modules, V).real

    dP_dtau__ = deriv.dSbus_dtau_csc(nbus, idx_dP, idx_dtau, F, T, Ys, kconv, complex_tap, V).real
    dQ_dtau__ = deriv.dSbus_dtau_csc(nbus, idx_dQ, idx_dtau, F, T, Ys, kconv, complex_tap, V).imag
    dQf_dtau_ = deriv.dSf_dtau_csc(idx_dQf, idx_dtau, F, T, Ys, kconv, complex_tap, V).imag
    dPf_dtau_ = deriv.dSf_dtau_csc(idx_dPf, idx_dtau, F, T, Ys, kconv, complex_tap, V).real

    # compose the Jacobian
    J = csc_stack_2d_ff(mats=
                        [dP_dVa__, dP_dVm__, dP_dbeq__, dP_dm__, dP_dtau__,
                         dQ_dVa__, dQ_dVm__, dQ_dbeq__, dQ_dm__, dQ_dtau__,
                         dQf_dVa_, dQf_dVm_, dQf_dbeq_, dQf_dm_, dQf_dtau_,
                         dPf_dVa_, dPf_dVm_, dPf_dbeq_, dPf_dm_, dPf_dtau_],
                        n_rows=4, n_cols=5)

    return J


class PfAdvancedFormulation(PfFormulationTemplate):

    def __init__(self, V0: CxVec, S0: CxVec, I0: CxVec, Y0: CxVec, Qmin: Vec, Qmax: Vec,
                 pq: IntVec, pv: IntVec, pqv: IntVec, p: IntVec, k_pf_tau: IntVec, k_v_m: IntVec, k_beq_zero: IntVec,
                 nc: NumericalCircuit, options: PowerFlowOptions):
        """

        :param V0:
        :param S0:
        :param I0:
        :param Y0:
        :param Qmin:
        :param Qmax:
        :param pq:
        :param pv:
        :param pqv:
        :param p:
        :param k_pf_tau:
        :param k_v_m:
        :param k_beq_zero:
        :param nc:
        :param options:
        """
        PfFormulationTemplate.__init__(self, V0=V0, pq=pq, pv=pv, pqv=pqv, p=p, options=options)

        self.nc: NumericalCircuit = nc

        self.S0: CxVec = S0
        self.I0: CxVec = I0
        self.Y0: CxVec = Y0

        self.Qmin = Qmin
        self.Qmax = Qmax

        self.k_pf_tau: IntVec = k_pf_tau
        self.k_v_m: IntVec = k_v_m
        self.k_beq_zero: IntVec = k_beq_zero

        self.idx_dQf = self.k_beq_zero
        self.idx_dbeq = self.k_beq_zero
        self.idx_dPf = self.k_pf_tau
        self.idx_dtau = self.k_pf_tau
        self.idx_dm = self.k_v_m

        self.m: Vec = np.zeros(len(pqv))
        self.tau: Vec = np.zeros(len(k_pf_tau))
        self.beq: Vec = np.zeros(len(k_beq_zero))

        if not len(self.k_v_m) == len(self.pqv):
            raise ValueError("k_v_m indices must be the same size as pqv indices!")

        if not np.all(self.idx_dtau == self.idx_dPf):
            raise ValueError("Pf indices must be equal to tau indices!")

    @property
    def adm(self) -> AdmittanceMatrices:
        """

        :return:
        """
        return self.nc.admittances_

    def x2var(self, x: Vec):
        """
        Convert X to decission variables
        :param x: solution vector
        """
        a = len(self.idx_dVa)
        b = a + len(self.idx_dVm)
        c = b + len(self.k_pf_tau)
        d = c + len(self.k_v_m)
        e = d + len(self.k_beq_zero)

        # update the vectors
        self.Va[self.idx_dVa] = x[0:a]
        self.Vm[self.idx_dVm] = x[a:b]
        self.tau = x[b:c]
        self.m = x[c:d]
        self.beq = x[d:e]

        # compute the complex voltage
        self.V = polar_to_rect(self.Vm, self.Va)

    def var2x(self) -> Vec:
        """
        Convert the internal decission variables into the vector
        :return: Vector
        """
        return np.r_[
            self.Va[self.idx_dVa],
            self.Vm[self.idx_dVm],
            self.tau,
            self.m,
            self.beq
        ]

    def update(self, x: Vec, update_controls: bool = False) -> Tuple[float, bool, Vec]:
        """

        :param x:
        :param update_controls:
        :return:
        """
        # set the problem state
        self.x2var(x)

        # compute the function residual
        self._f = self.fx()

        # compute the rror
        self._error = compute_fx_error(self._f)

        # converged?
        self._converged = self._error < self.options.tolerance

        # review reactive power limits
        # it is only worth checking Q limits with a low error
        # since with higher errors, the Q values may be far from realistic
        # finally, the Q control only makes sense if there are pv nodes
        if update_controls:
            if (self.options.control_Q != ReactivePowerControlMode.NoControl and
                    self._error < 1e-2
                    and (len(self.pv) + len(self.p)) > 0):

                # check and adjust the reactive power
                # this function passes pv buses to pq when the limits are violated,
                # but not pq to pv because that is unstable
                changed, pv, pq, pqv, p = control_q_inside_method(self.Scalc, self.S0,
                                                                  self.pv, self.pq,
                                                                  self.pqv, self.p,
                                                                  self.Qmin,
                                                                  self.Qmax)

                if len(changed) > 0:
                    self.update_types(pq=pq, pv=pv, pqv=pqv, p=p)

                    # recompute the error based on the new Scalc and S0
                    self._f = self.fx()

                    # compute the rror
                    self._error = compute_fx_error(self._f)

                    # the composition of x changed, so recompute
                    x = self.var2x()

        return self._error, self._converged, x

    def fx(self) -> Vec:
        """

        :return:
        """
        # Assumes the internal vars were updated already with self.x2var()
        Sbus = compute_zip_power(self.S0, self.I0, self.Y0, self.Vm)
        self.Scalc = compute_power(self.adm.Ybus, self.V)
        self._f = compute_fx(self.Scalc, Sbus, self.idx_dP, self.idx_dQ)
        return self._f

    def Jacobian(self) -> CSC:
        """

        :return:
        """
        # Assumes the internal vars were updated already with self.x2var()
        if self.adm.Ybus.format != 'csc':
            self.adm.Ybus = self.adm.Ybus.tocsc()

        n_rows = len(self.idx_dP) + len(self.idx_dQ) + len(self.idx_dQf) + len(self.idx_dPf)
        n_cols = len(self.idx_dVa) + len(self.idx_dVm) + len(self.idx_dm) + len(self.idx_dtau) + len(self.idx_dbeq)

        if n_cols != n_rows:
            raise ValueError("Incorrect J indices!")

        # NOTE: beq, m, and tau are not of size nbranch

        J = adv_jacobian(nbus=self.nc.nbus,
                         idx_dtheta=self.idx_dVa,
                         idx_dvm=self.idx_dVm,
                         idx_dm=self.idx_dm,
                         idx_dtau=self.idx_dtau,
                         idx_dbeq=self.idx_dtau,
                         idx_dP=self.idx_dP,
                         idx_dQ=self.idx_dQ,
                         idx_dQf=self.idx_dQf,
                         idx_dPf=self.idx_dPf,
                         F=self.nc.F,
                         T=self.nc.T,
                         Ys=1.0 / (self.nc.branch_data.R + 1j * self.nc.branch_data.X),
                         kconv=self.nc.branch_data.k,
                         complex_tap=polar_to_rect(self.m, self.tau),
                         tap_modules=self.m,
                         Bc=self.nc.branch_data.B,
                         Beq=self.beq,
                         V=self.V,
                         Vm=self.Vm,
                         Ybus_x=self.adm.Ybus.data,
                         Ybus_p=self.adm.Ybus.indptr,
                         Ybus_i=self.adm.Ybus.indices,
                         yff=self.adm.yff,
                         yft=self.adm.yft)

        return J

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
                                       m=None,
                                       tau=None,
                                       Beq=None,
                                       Ybus=self.adm.Ybus,
                                       Yf=self.adm.Yf,
                                       Yt=self.adm.Yt,
                                       iterations=iterations,
                                       elapsed=elapsed)
