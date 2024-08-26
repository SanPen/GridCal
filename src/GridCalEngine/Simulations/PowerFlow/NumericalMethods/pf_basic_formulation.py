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
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Topology.admittance_matrices import AdmittanceMatrices
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.Derivatives.ac_jacobian import create_J_vc_csc
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import compute_fx_error
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import (control_q_inside_method,
                                                                                    compute_slack_distribution)
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.pf_formulation_template import PfFormulationTemplate
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import (compute_zip_power, compute_power,
                                                                                   compute_fx, polar_to_rect)
from GridCalEngine.Topology.simulation_indices import compile_types
from GridCalEngine.basic_structures import Vec, IntVec, CxVec
from GridCalEngine.Utils.Sparse.csc2 import CSC


class PfBasicFormulation(PfFormulationTemplate):

    def __init__(self, V0: CxVec, S0: CxVec, I0: CxVec, Y0: CxVec, Qmin: Vec, Qmax: Vec,
                 nc: NumericalCircuit, options: PowerFlowOptions):
        """

        :param V0:
        :param S0:
        :param I0:
        :param Y0:
        :param Qmin:
        :param Qmax:
        :param options:
        """
        PfFormulationTemplate.__init__(self, V0=V0, options=options)

        self.nc = nc
        self.adm: AdmittanceMatrices = nc.admittances_

        self.S0: CxVec = S0
        self.I0: CxVec = I0
        self.Y0: CxVec = Y0

        self.Qmin = Qmin
        self.Qmax = Qmax

        self.vd, self.pq, self.pv, self.pqv, self.p, self.no_slack = compile_types(
            Pbus=self.nc.Sbus.real,
            types=self.nc.bus_data.bus_types
        )

        self.idx_dVa = np.r_[self.pv, self.pq, self.pqv, self.p]
        self.idx_dVm = np.r_[self.pq, self.p]
        self.idx_dP = self.idx_dVa
        self.idx_dQ = np.r_[self.pq, self.pqv]

    def x2var(self, x: Vec):
        """
        Convert X to decission variables
        :param x: solution vector
        """
        a = len(self.idx_dVa)
        b = a + len(self.idx_dVm)

        # update the vectors
        self.Va[self.idx_dVa] = x[0:a]
        self.Vm[self.idx_dVm] = x[a:b]

    def var2x(self) -> Vec:
        """
        Convert the internal decission variables into the vector
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
        Sbus = compute_zip_power(self.S0, self.I0, self.Y0, self.Vm)
        self.Scalc = compute_power(self.adm.Ybus, self.V)
        dS = self.Scalc - Sbus  # compute the mismatch
        self._f = np.r_[
            dS[self.idx_dP].real,
            dS[self.idx_dQ].imag
        ]
        # self._f = compute_fx(self.Scalc, Sbus, self.idx_dP, self.idx_dQ)

        # compute the rror
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
                                                       bus_installed_power=self.nc.bus_installed_power)
                if ok:
                    any_change = True
                    # Update the objective power to reflect the slack distribution
                    self.S0 += delta

            if any_change:
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
        self._f = compute_fx(self.Scalc, Sbus, self.idx_dP, self.idx_dQ)
        return self._f

    def Jacobian(self) -> CSC:
        """

        :return:
        """
        # Assumes the internal vars were updated already with self.x2var()
        if self.adm.Ybus.format != 'csc':
            self.adm.Ybus = self.adm.Ybus.tocsc()

        nbus = self.adm.Ybus.shape[0]

        # Create J in CSC order
        J = create_J_vc_csc(nbus, self.adm.Ybus.data, self.adm.Ybus.indptr, self.adm.Ybus.indices,
                            self.V, self.idx_dVa, self.idx_dVm, self.idx_dP, self.idx_dQ)

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
