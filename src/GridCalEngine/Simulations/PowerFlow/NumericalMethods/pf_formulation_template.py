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
from GridCalEngine.basic_structures import Vec, IntVec, CxVec
from GridCalEngine.Utils.Sparse.csc2 import CSC, spsolve_csc
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions


class PfFormulationTemplate:
    """
    Base Power Flow Formulation class
    """

    def __init__(self, V0: CxVec, pq: IntVec, pv: IntVec, pqv: IntVec, p: IntVec, options: PowerFlowOptions):
        """

        :param V0:
        :param pq:
        :param pv:
        :param pqv:
        :param p:
        :param options:
        """
        self.V = V0

        self._Vm = np.abs(V0)
        self._Va = np.angle(V0)

        self.Scalc = np.zeros(len(V0), dtype=complex)

        self.options = options

        self.pq = pq
        self.pv = pv
        self.pqv = pqv
        self.p = p

        self._idx_dVa = np.r_[self.pv, self.pq, self.pqv, self.p]
        self._idx_dVm = np.r_[self.pq, self.p]
        self._idx_dP = self._idx_dVa
        self._idx_dQ = np.r_[self.pq, self.pqv]

        self._f = np.zeros(0)

        self._error: float = 0.0

        self._converged: bool = False

    def update_types(self, pq: IntVec, pv: IntVec, pqv: IntVec, p: IntVec):
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

        self._idx_dVa = np.r_[self.pv, self.pq, self.pqv, self.p]
        self._idx_dVm = np.r_[self.pq, self.p]
        self._idx_dP = self._idx_dVa
        self._idx_dQ = np.r_[self.pq, self.pqv]

    @property
    def converged(self) -> bool:
        """
        Converged?
        :return:
        """
        return self._converged

    @property
    def error(self) -> float:
        """
        Converged?
        :return:
        """
        return self._error

    @property
    def f(self) -> Vec:
        """
        Converged?
        :return:
        """
        return self._f

    @property
    def idx_dVa(self) -> IntVec:
        """
        Indices for the increments of Va
        :return:
        """
        return self._idx_dVa

    @property
    def idx_dVm(self) -> IntVec:
        """
        indices for the increment of Vm
        :return:
        """
        return self._idx_dVm

    @property
    def idx_dP(self) -> IntVec:
        """
        indices for the increment of P
        :return:
        """
        return self._idx_dP

    @property
    def idx_dQ(self) -> IntVec:
        """
        Indices for the increment of Q
        :return:
        """
        return self._idx_dQ

    @property
    def Va(self) -> Vec:
        """
        Voltage angles
        :return:
        """
        return self._Va

    @property
    def Vm(self) -> Vec:
        """
        Voltage modules
        :return:
        """
        return self._Vm

    def x2var(self, x: Vec):
        """
        Convert X to decission variables
        :param x: solution vector
        """
        pass

    def var2x(self) -> Vec:
        """
        Convert the internal decission variables into the vector
        """
        pass

    def update(self, x: Vec, update_controls: bool = False) -> Tuple[float, bool, Vec]:
        """
        Update the problem
        :param x: Solution vector
        :param update_controls: Update controls
        :return: error, converged, x
        """
        return self.error, self.converged, np.zeros(len(self.V))

    def fx(self) -> Vec:
        """

        :return:
        """
        pass

    def Jacobian(self) -> CSC:
        """

        :return:
        """
        pass

    def solve_step_from_f(self, f: Vec) -> Tuple[Vec, bool]:
        """

        :param f: Function residual
        :return:
        """
        # Compute the Jacobian
        J = self.Jacobian()  # Assumes the internal vars were updated already with self.x2var()

        # Solve the sparse system
        dx, ok = spsolve_csc(J, f)

        return dx, ok

    def solve_step(self) -> Tuple[Vec, bool]:
        """

        :return:
        """

        # Solve the sparse system
        dx, ok = self.solve_step_from_f(self._f)

        return dx, ok

    def get_solution(self, elapsed: float, iterations: int) -> NumericPowerFlowResults:
        """

        :return:
        """
        pass