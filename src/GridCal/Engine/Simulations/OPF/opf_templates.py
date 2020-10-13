# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

from GridCal.Engine.basic_structures import MIPSolvers
from GridCal.ThirdParty.pulp import *


class Opf:

    def __init__(self, numerical_circuit, solver: MIPSolvers = MIPSolvers.CBC):
        """
        Optimal power flow template class
        :param numerical_circuit: NumericalCircuit instance
        """
        self.numerical_circuit = numerical_circuit

        self.theta = None
        self.Pg = None
        self.Pb = None
        self.Pl = None
        self.E = None
        self.s_from = None
        self.s_to = None
        self.overloads = None
        self.rating = None
        self.load_shedding = None
        self.nodal_restrictions = None

        self.solver = solver

        self.problem = self.formulate()

    def formulate(self):
        """
        Formulate the AC OPF time series in the non-sequential fashion (all to the solver at once)
        :return: PuLP Problem instance
        """

        # declare problem
        problem = LpProblem(name='DC_OPF_Time_Series')

        return problem

    def solve(self):
        """
        Call PuLP to solve the problem
        """
        # self.problem.writeLP('OPF.lp')
        if self.solver == MIPSolvers.CBC:
            params = PULP_CBC_CMD(fracGap=0.00001, threads=None, msg=1)

        elif self.solver == MIPSolvers.SCIP:
            params = SCIP_CMD(msg=1)

        elif self.solver == MIPSolvers.CPLEX:
            params = CPLEX_CMD(msg=1)

        elif self.solver == MIPSolvers.GUROBI:
            params = GUROBI_CMD(msg=1)

        elif self.solver == MIPSolvers.XPRESS:
            params = XPRESS(msg=1)

        else:
            raise Exception('Solver not supported! ' + str(self.solver))

        self.problem.solve(params)

        return LpStatus[self.problem.status]

    @staticmethod
    def extract(arr, make_abs=False):
        """
        Extract values fro the 1D array of LP variables
        :param arr: 1D array of LP variables
        :param make_abs: substitute the result by its abs value
        :return: 1D numpy array
        """
        val = np.zeros(arr.shape)
        for i in range(val.shape[0]):
            val[i] = arr[i].value()
        if make_abs:
            val = np.abs(val)

        return val

    def get_voltage(self):
        """
        return the complex voltages (time, device)
        :return: 2D array
        """
        angles = self.extract(self.theta)
        return np.ones_like(angles) * np.exp(-1j * angles)

    def get_overloads(self):
        """
        return the branch overloads (time, device)
        :return: 2D array
        """
        return self.extract(self.overloads)

    def get_loading(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.s_from, make_abs=True) / (self.rating + 1e-12)

    def get_branch_power(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.s_from, make_abs=True) * self.numerical_circuit.Sbase

    def get_battery_power(self):
        """
        return the battery dispatch (time, device)
        :return: 2D array
        """
        return self.extract(self.Pb) * self.numerical_circuit.Sbase

    def get_generator_power(self):
        """
        return the generator dispatch (time, device)
        :return: 2D array
        """
        return self.extract(self.Pg) * self.numerical_circuit.Sbase

    def get_load_shedding(self):
        """
        return the load shedding (time, device)
        :return: 2D array
        """
        return self.extract(self.load_shedding) * self.numerical_circuit.Sbase

    def get_load_power(self):
        """
        return the load shedding (time, device)
        :return: 2D array
        """
        return self.extract(self.Pl) * self.numerical_circuit.Sbase

    def get_shadow_prices(self):
        """
        Extract values fro the 2D array of LP variables
        :return: 2D numpy array
        """
        val = np.zeros(self.nodal_restrictions.shape)
        for i in range(val.shape[0]):
            if self.nodal_restrictions[i].pi is not None:
                val[i] = - self.nodal_restrictions[i].pi
        return val.transpose()

    def converged(self):
        return True


class OpfTimeSeries:

    def __init__(self, numerical_circuit, start_idx, end_idx, solver: MIPSolvers=MIPSolvers.CBC):
        """

        :param numerical_circuit:
        :param start_idx:
        :param end_idx:
        """
        self.numerical_circuit = numerical_circuit
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.solver = solver

        self.theta = None
        self.Pg = None
        self.Pb = None
        self.Pl = None
        self.E = None
        self.s_from = None
        self.s_to = None
        self.overloads = None
        self.rating = None
        self.load_shedding = None
        self.nodal_restrictions = None

        self.problem = self.formulate()

    def formulate(self):
        """
        Formulate the AC OPF time series in the non-sequential fashion (all to the solver at once)
        :return: PuLP Problem instance
        """

        # declare problem
        problem = LpProblem(name='DC_OPF_Time_Series')

        return problem

    def solve(self, msg=False):
        """
        Call PuLP to solve the problem
        """

        if self.solver == MIPSolvers.CBC:
            params = PULP_CBC_CMD(fracGap=0.00001, threads=None, msg=msg)

        elif self.solver == MIPSolvers.SCIP:
            params = SCIP_CMD(msg=msg)

        elif self.solver == MIPSolvers.CPLEX:
            params = CPLEX_CMD(msg=msg)

        elif self.solver == MIPSolvers.GUROBI:
            params = GUROBI_CMD(msg=msg)

        elif self.solver == MIPSolvers.XPRESS:
            params = XPRESS(msg=msg)

        else:
            raise Exception('Solver not supported! ' + str(self.solver))

        self.problem.solve(params)

        return LpStatus[self.problem.status]

    @staticmethod
    def extract2D(arr, make_abs=False):
        """
        Extract values fro the 2D array of LP variables
        :param arr: 2D array of LP variables
        :param make_abs: substitute the result by its abs value
        :return: 2D numpy array
        """
        val = np.zeros(arr.shape)
        for i, j in product(range(val.shape[0]), range(val.shape[1])):
            val[i, j] = arr[i, j].value()
        if make_abs:
            val = np.abs(val)

        return val

    def get_voltage(self):
        """
        return the complex voltages (time, device)
        :return: 2D array
        """
        angles = self.extract2D(self.theta)
        return np.ones_like(angles) * np.exp(-1j * angles)

    def get_overloads(self):
        """
        return the branch overloads (time, device)
        :return: 2D array
        """
        return self.extract2D(self.overloads)

    def get_loading(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract2D(self.s_from, make_abs=True) / self.rating

    def get_branch_power(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract2D(self.s_from, make_abs=True) * self.numerical_circuit.Sbase

    def get_battery_power(self):
        """
        return the battery dispatch (time, device)
        :return: 2D array
        """
        return self.extract2D(self.Pb) * self.numerical_circuit.Sbase

    def get_battery_energy(self):
        """
        return the battery energy (time, device)
        :return: 2D array
        """
        return self.extract2D(self.E) * self.numerical_circuit.Sbase

    def get_generator_power(self):
        """
        return the generator dispatch (time, device)
        :return: 2D array
        """
        return self.extract2D(self.Pg) * self.numerical_circuit.Sbase

    def get_load_shedding(self):
        """
        return the load shedding (time, device)
        :return: 2D array
        """
        return self.extract2D(self.load_shedding) * self.numerical_circuit.Sbase

    def get_load_power(self):
        """
        return the load shedding (time, device)
        :return: 2D array
        """
        return self.extract2D(self.Pl) * self.numerical_circuit.Sbase

    def get_shadow_prices(self):
        """
        Extract values fro the 2D array of LP variables
        :return: 2D numpy array
        """
        val = np.zeros(self.nodal_restrictions.shape)
        for i, j in product(range(val.shape[0]), range(val.shape[1])):
            if self.nodal_restrictions[i, j].pi is not None:
                val[i, j] = - self.nodal_restrictions[i, j].pi
        return val.transpose()
