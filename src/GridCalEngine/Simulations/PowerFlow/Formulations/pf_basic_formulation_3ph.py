# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Tuple, List
import numpy as np
from scipy.sparse import diags, lil_matrix, csc_matrix
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.Derivatives.ac_jacobian import create_J_vc_csc
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import (compute_fx_error,
                                                                                   power_flow_post_process_nonlinear)
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import (control_q_inside_method,
                                                                                    compute_slack_distribution)
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_formulation_template import PfFormulationTemplate
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import (compute_zip_power, compute_power,
                                                                                   compute_fx, polar_to_rect)
from GridCalEngine.Topology.simulation_indices import compile_types
from GridCalEngine.basic_structures import Vec, IntVec, CxVec
from GridCalEngine.Utils.Sparse.csc2 import CSC

def compute_ybus(nc: NumericalCircuit) -> Tuple[csc_matrix, csc_matrix, csc_matrix, CxVec]:
    """
    Compute admittances
    :param nc: NumericalCircuit
    :return: Ybus, Yf, Yt, Yshunt_bus
    """

    n = nc.bus_data.nbus
    m = nc.passive_branch_data.nelm
    Cf = lil_matrix((3 * m, 3 * n), dtype=int)
    Ct = lil_matrix((3 * m, 3 * n), dtype=int)
    Yf = lil_matrix((3 * m, 3 * n), dtype=complex)
    Yt = lil_matrix((3 * m, 3 * n), dtype=complex)

    idx3 = np.array([0, 1, 2])  # array that we use to generate the 3-phase indices

    R = np.zeros((m, 3), dtype=int)

    for k in range(m):
        f = nc.passive_branch_data.F[k]
        t = nc.passive_branch_data.T[k]

        f3 = 3 * f + idx3
        t3 = 3 * t + idx3
        k3 = 3 * k + idx3

        Yf[np.ix_(k3, f3)] = nc.passive_branch_data.Yff3[k3, :]
        Yf[np.ix_(k3, t3)] = nc.passive_branch_data.Yft3[k3, :]
        Yt[np.ix_(k3, f3)] = nc.passive_branch_data.Ytf3[k3, :]
        Yt[np.ix_(k3, t3)] = nc.passive_branch_data.Ytt3[k3, :]

        R[k, 0] = nc.passive_branch_data.phA[k]
        R[k, 1] = nc.passive_branch_data.phB[k]
        R[k, 2] = nc.passive_branch_data.phC[k]

        Cf[k3, f3] = 1
        Ct[k3, t3] = 1

    N = Cf @ R.T + Ct @ R.T

    Ysh_bus = np.zeros(n * 3, dtype=complex)
    for k in range(nc.shunt_data.nelm):
        f = nc.shunt_data.bus_idx[k]
        k3 = 3 * k + idx3
        f3 = 3 * f + idx3
        Ysh_bus[f3] += nc.shunt_data.Y3_star[k3]

    for k in range(nc.load_data.nelm):
        f = nc.load_data.bus_idx[k]
        k3 = 3 * k + idx3
        f3 = 3 * f + idx3
        Ysh_bus[f3] += nc.load_data.Y3_star[k3]

    Ybus = Cf.T @ Yf + Ct.T @ Yt + diags(Ysh_bus / nc.Sbase)

    return Ybus.tocsc(), Yf.tocsc(), Yt.tocsc(), Ysh_bus


def compute_Ibus(nc: NumericalCircuit) -> CxVec:
    """
    Compute the Ibus vector
    :param nc:
    :return:
    """
    n = nc.bus_data.nbus
    idx3 = np.array([0, 1, 2])
    Ibus = np.zeros(n * 3, dtype=complex)

    for k in range(nc.load_data.nelm):
        f = nc.load_data.bus_idx[k]
        k3 = 3 * k + idx3
        f3 = 3 * f + idx3
        Ibus[f3] -= nc.load_data.I3_star[k3]

    return Ibus


def compute_Sbus_star(nc: NumericalCircuit) -> CxVec:
    """
    Compute the Ibus vector
    :param nc:
    :return:
    """
    n = nc.bus_data.nbus
    idx3 = np.array([0, 1, 2])
    Sbus = np.zeros(n * 3, dtype=complex)

    for k in range(nc.load_data.nelm):
        f = nc.load_data.bus_idx[k]
        k3 = 3 * k + idx3
        f3 = 3 * f + idx3
        Sbus[f3] -= nc.load_data.S3_star[k3]

    return Sbus


def compute_Sbus_delta(bus_idx: IntVec, Sdelta: CxVec, V: CxVec) -> CxVec:
    """

    :param bus_idx:
    :param Sdelta:
    :param V:
    :return:
    """
    n = len(V)
    nelm = len(bus_idx)
    S = np.zeros(n, dtype=complex)
    for k in range(nelm):
        f = bus_idx[k]

        a = 3 * f + 0
        b = 3 * f + 1
        c = 3 * f + 2

        ab = 3 * k + 0
        bc = 3 * k + 1
        ca = 3 * k + 2

        S[a] = -1 * ((V[a] * Sdelta[ab]) / (V[a] - V[b]) - (V[a] * Sdelta[ca]) / (V[c] - V[a]))
        S[b] = -1 * ((V[b] * Sdelta[bc]) / (V[b] - V[c]) - (V[b] * Sdelta[ab]) / (V[a] - V[b]))
        S[c] = -1 * ((V[c] * Sdelta[ca]) / (V[c] - V[a]) - (V[c] * Sdelta[bc]) / (V[b] - V[c]))

    return S


def expand3ph(x: np.ndarray):
    """
    Expands a numpy array to 3-pase copying the same values
    :param x:
    :return:
    """
    n = len(x)
    idx3 = np.array([0, 1, 2])
    x3 = np.zeros(3 * n, dtype=x.dtype)

    for k in range(n):
        x3[3 * k + idx3] = x[k]
    return x3

def expand_indices_3ph(x: np.ndarray):
    """
    Expands a numpy array to 3-pase copying the same values
    :param x:
    :return:
    """
    n = len(x)
    idx3 = np.array([0, 1, 2])
    x3 = np.zeros(3 * n, dtype=x.dtype)

    for k in range(n):
        x3[3 * k + idx3] = 3 * x[k] + idx3
    return x3

def expandVoltage3ph(V0: CxVec):
    """
    Expands a numpy array to 3-pase copying the same values
    :param V0:
    :return:
    """
    n = len(V0)
    idx3 = np.array([0, 1, 2])
    angles = np.array([0, -2 * np.pi / 3, 2 * np.pi / 3])
    Vm = np.abs(V0)
    Va = np.angle(V0)
    x3 = np.zeros(3 * n, dtype=complex)

    for k in range(n):
        x3[3 * k + idx3] = Vm[k] * np.exp(1j * (Va[k] + angles))
    return x3


class PfBasicFormulation3Ph(PfFormulationTemplate):

    def __init__(self, V0: CxVec, S0: CxVec, Qmin: Vec, Qmax: Vec,
                 nc: NumericalCircuit, options: PowerFlowOptions):
        """
        PfBasicFormulation3Ph
        :param V0: Array of nodal initial solution (N, not 3N)
        :param Qmin: Array of bus reactive power upper limit (N, not 3N)
        :param Qmax: Array of bus reactive power lower limit (N, not 3N)
        :param nc: NumericalCircuit
        :param options: PowerFlowOptions
        """
        PfFormulationTemplate.__init__(self, V0=expandVoltage3ph(V0).astype(complex), options=options)

        self.nc = nc

        self.S0: CxVec = compute_Sbus_star(nc) / (nc.Sbase / 3)
        self.I0: CxVec = compute_Ibus(nc) / (nc.Sbase / 3)

        self.Ybus, self.Yf, self.Yt, self.Yshunt_bus = compute_ybus(nc)

        self.Qmin = expand3ph(Qmin)
        self.Qmax = expand3ph(Qmax)

        vd, pq, pv, pqv, p, no_slack = compile_types(
            Pbus=S0.real,
            types=self.nc.bus_data.bus_types
        )

        self.vd = expand_indices_3ph(vd)
        self.pq = expand_indices_3ph(pq)
        self.pv = expand_indices_3ph(pv)
        self.pqv = expand_indices_3ph(pqv)
        self.p = expand_indices_3ph(p)
        self.no_slack = expand_indices_3ph(no_slack)

        self.idx_dVa = np.r_[self.pv, self.pq, self.pqv, self.p]
        self.idx_dVm = np.r_[self.pq, self.p]
        self.idx_dP = self.idx_dVa
        self.idx_dQ = np.r_[self.pq, self.pqv]

    def x2var(self, x: Vec):
        """
        Convert X to decision variables
        :param x: solution vector
        """
        a = len(self.idx_dVa)
        b = a + len(self.idx_dVm)

        # update the vectors
        self.Va[self.idx_dVa] = x[0:a]
        self.Vm[self.idx_dVm] = x[a:b]

    def var2x(self) -> Vec:
        """
        Convert the internal decision variables into the vector
        :return: Vector
        """
        return np.r_[
            self.Va[self.idx_dVa],
            self.Vm[self.idx_dVm]
        ]

    def update_bus_types(self, pq: IntVec, pv: IntVec, pqv: IntVec, p: IntVec):
        """

        :param pq:
        :param pv:
        :param pqv:
        :param p:
        :return:
        """
        self.pq = pq
        self.pv = pv
        self.pqv = pqv
        self.p = p

        self.idx_dVa = np.r_[self.pv, self.pq, self.pqv, self.p]
        self.idx_dVm = np.r_[self.pq, self.p]
        self.idx_dP = self.idx_dVa
        self.idx_dQ = np.r_[self.pq, self.pqv]

    def size(self) -> int:
        """
        Size of the jacobian matrix
        :return:
        """
        return len(self.idx_dVa) + len(self.idx_dVm)

    def check_error(self, x: Vec) -> Tuple[float, Vec]:
        """
        Check error of the solution without affecting the problem
        :param x: Solution vector
        :return: error
        """
        a = len(self.idx_dVa)
        b = a + len(self.idx_dVm)

        # update the vectors
        Va = self.Va.copy()
        Vm = self.Vm.copy()
        Va[self.idx_dVa] = x[0:a]
        Vm[self.idx_dVm] = x[a:b]

        # compute the complex voltage
        V = polar_to_rect(Vm, Va)

        # compute the function residual
        # Assumes the internal vars were updated already with self.x2var()
        Sdelta2star = compute_Sbus_delta(bus_idx=self.nc.load_data.bus_idx,
                                         Sdelta=self.nc.load_data.S3_delta,
                                         V=V)
        Sbus = self.S0 + Sdelta2star
        Scalc = compute_power(self.Ybus, V)
        dS = Scalc - Sbus  # compute the mismatch
        _f = np.r_[
            dS[self.idx_dP].real,
            dS[self.idx_dQ].imag
        ]

        # compute the error
        return compute_fx_error(_f), x

    def update(self, x: Vec, update_controls: bool = False) -> Tuple[float, bool, Vec, Vec]:
        """
        Update step
        :param x: Solution vector
        :param update_controls:
        :return: error, converged?, x
        """
        # set the problem state
        self.x2var(x)

        # compute the complex voltage
        self.V = polar_to_rect(self.Vm, self.Va)

        # compute the function residual
        # Assumes the internal vars were updated already with self.x2var()
        Sdelta2star = compute_Sbus_delta(bus_idx=self.nc.load_data.bus_idx,
                                         Sdelta=self.nc.load_data.S3_delta,
                                         V=self.V)
        Sbus = self.S0 + Sdelta2star
        self.Scalc = compute_power(self.Ybus, self.V)
        dS = self.Scalc - Sbus  # compute the mismatch
        self._f = np.r_[
            dS[self.idx_dP].real,
            dS[self.idx_dQ].imag
        ]
        # self._f = compute_fx(self.Scalc, Sbus, self.idx_dP, self.idx_dQ)

        # compute the error
        self._error = compute_fx_error(self._f)

        # review reactive power limits
        # it is only worth checking Q limits with a low error
        # since with higher errors, the Q values may be far from realistic
        # finally, the Q control only makes sense if there are pv nodes
        if update_controls and self._error < self._controls_tol:
            any_change = False

            # update Q limits control
            if self.options.control_Q and (len(self.pv) + len(self.p)) > 0:

                # check and adjust the reactive power
                # this function passes pv buses to pq when the limits are violated,
                # but not pq to pv because that is unstable
                changed, pv, pq, pqv, p = control_q_inside_method(self.Scalc, self.S0,
                                                                  self.pv, self.pq,
                                                                  self.pqv, self.p,
                                                                  self.Qmin,
                                                                  self.Qmax)

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
                                                       bus_installed_power=self.nc.bus_data.installed_power)
                if ok:
                    any_change = True
                    # Update the objective power to reflect the slack distribution
                    self.S0 += delta

            if any_change:
                # recompute the error based on the new Scalc and S0
                self._f = self.fx()

                # compute the error
                self._error = compute_fx_error(self._f)

        # converged?
        self._converged = self._error < self.options.tolerance

        return self._error, self._converged, x, self.f

    def fx(self) -> Vec:
        """
        # Scalc = V · (Y x V - I)^*
        # Sbus = S0 + I0*Vm + Y0*Vm^2
        :return:
        """

        # NOTE: Assumes the internal vars were updated already with self.x2var()

        Sdelta2star = compute_Sbus_delta(bus_idx=self.nc.load_data.bus_idx,
                                         Sdelta=self.nc.load_data.S3_delta,
                                         V=self.V)
        Sbus = self.S0 + Sdelta2star
        self.Scalc = self.V * np.conj(self.Ybus @ self.V - self.I0)

        self._f = compute_fx(self.Scalc, Sbus, self.idx_dP, self.idx_dQ)
        return self._f

    def Jacobian(self) -> CSC:
        """

        :return:
        """
        # Assumes the internal vars were updated already with self.x2var()
        if self.Ybus.format != 'csc':
            self.Ybus = self.Ybus.tocsc()

        nbus = self.Ybus.shape[0]

        # Create J in CSC order
        J = create_J_vc_csc(nbus, self.Ybus.data, self.Ybus.indptr, self.Ybus.indices,
                            self.V, self.idx_dVa, self.idx_dVm, self.idx_dP, self.idx_dQ)

        return J

    def get_x_names(self) -> List[str]:
        """
        Names matching x
        :return:
        """
        cols = [f'dVa {i}' for i in self.idx_dVa]
        cols += [f'dVm {i}' for i in self.idx_dVm]

        return cols

    def get_fx_names(self) -> List[str]:
        """
        Names matching fx
        :return:
        """
        rows = [f'dP {i}' for i in self.idx_dP]
        rows += [f'dQ {i}' for i in self.idx_dQ]

        return rows

    def get_solution(self, elapsed: float, iterations: int) -> NumericPowerFlowResults:
        """
        Get the problem solution
        :param elapsed: Elapsed seconds
        :param iterations: Iteration number
        :return: NumericPowerFlowResults
        """
        # Compute the Branches power and the slack buses power
        Sf, St, If, It, Vbranch, loading, losses, Sbus = power_flow_post_process_nonlinear(
            Sbus=self.Scalc,
            V=self.V,
            F=expand_indices_3ph(self.nc.passive_branch_data.F),
            T=expand_indices_3ph(self.nc.passive_branch_data.T),
            pv=self.pv,
            vd=self.vd,
            Ybus=self.Ybus,
            Yf=self.Yf,
            Yt=self.Yt,
            Yshunt_bus=self.Yshunt_bus,
            branch_rates=expand3ph(self.nc.passive_branch_data.rates),
            Sbase=self.nc.Sbase
        )

        return NumericPowerFlowResults(V=self.V,
                                       Scalc=Sbus * self.nc.Sbase,
                                       m=np.ones(self.nc.nbr, dtype=float),
                                       tau=np.zeros(self.nc.nbr, dtype=float),
                                       Sf=Sf,
                                       St=St,
                                       If=If,
                                       It=It,
                                       loading=loading,
                                       losses=losses,
                                       Pf_vsc=np.zeros(self.nc.nvsc, dtype=float),
                                       St_vsc=np.zeros(self.nc.nvsc, dtype=complex),
                                       If_vsc=np.zeros(self.nc.nvsc, dtype=float),
                                       It_vsc=np.zeros(self.nc.nvsc, dtype=complex),
                                       losses_vsc=np.zeros(self.nc.nvsc, dtype=float),
                                       loading_vsc=np.zeros(self.nc.nvsc, dtype=float),
                                       Sf_hvdc=np.zeros(self.nc.nhvdc, dtype=complex),
                                       St_hvdc=np.zeros(self.nc.nhvdc, dtype=complex),
                                       losses_hvdc=np.zeros(self.nc.nhvdc, dtype=complex),
                                       loading_hvdc=np.zeros(self.nc.nhvdc, dtype=complex),
                                       norm_f=self.error,
                                       converged=self.converged,
                                       iterations=iterations,
                                       elapsed=elapsed)
