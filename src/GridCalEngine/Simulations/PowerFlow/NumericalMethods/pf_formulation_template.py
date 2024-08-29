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
import pandas as pd
from GridCalEngine.basic_structures import Vec, CxVec
from GridCalEngine.Utils.Sparse.csc2 import CSC, spsolve_csc
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions

pd.set_option('display.float_format', '{:.4f}'.format)


class PfFormulationTemplate:
    """
    Base Power Flow Formulation class
    """

    def __init__(self, V0: CxVec, options: PowerFlowOptions):
        """

        :param V0:
        :param options:
        """
        self.V = V0

        self._Vm = np.abs(V0)
        self._Va = np.angle(V0)

        self.Scalc: CxVec = np.zeros(len(V0), dtype=complex)

        self.options: PowerFlowOptions = options

        self._f: Vec = np.zeros(0)

        self._error: float = 0.0

        self._converged: bool = False

        self._controls_tol: float = 1.0e-2  # min(1e-2, self.options.tolerance * 100.0)

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

    def update(self, x: Vec, update_controls: bool = False) -> Tuple[float, bool, Vec, Vec]:
        """
        Update the problem
        :param x: Solution vector
        :param update_controls: Update controls
        :return: error, converged, x, f
        """
        return self.error, self.converged, self.var2x(), self._f

    def size(self) -> int:
        """
        Size of the jacobian matrix
        :return:
        """
        return 0

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

        if self.options.verbose > 1:
            cols = np.array([0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 7])
            rows = np.array([0, 1, 2, 3, 4, 5, 6, 9, 10, 8, 7])
            # print("J original:\n", pd.DataFrame(J.toarray()))
            print("J mod:\n", pd.DataFrame(J.toarray()[:, cols][rows, :]).to_string(index=False))
            print("F:\n", f[rows])
            print("dx:\n", dx[cols])
            if self.options.verbose > 2:
                Jdf = pd.DataFrame(J.toarray())
                Jdf.to_csv(f'J.csv', index=False, float_format='%.4f')

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
