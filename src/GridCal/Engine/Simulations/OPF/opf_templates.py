# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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

import platform

from GridCal.Engine.Core.snapshot_opf_data import SnapshotOpfData
from GridCal.Engine.Core.time_series_opf_data import OpfTimeCircuit
from GridCal.Engine.basic_structures import MIPSolvers
from GridCal.ThirdParty.pulp import *
from GridCal.Engine.basic_structures import Logger

try:
    from ortools.linear_solver import pywraplp
except ModuleNotFoundError:
    print('ORTOOLS not found :(')


class Opf:

    def __init__(self, numerical_circuit: SnapshotOpfData,
                 solver_type: MIPSolvers = MIPSolvers.CBC, ortools=False):
        """
        Optimal power flow template class
        :param numerical_circuit: NumericalCircuit instance
        """
        self.numerical_circuit = numerical_circuit

        self.logger = Logger()

        self.theta = None
        self.Pg = None
        self.Pb = None
        self.Pl = None

        self.Pinj = None
        self.hvdc_flow = None

        self.phase_shift = None

        self.E = None
        self.s_from = None

        self.s_to = None
        self.overloads = None
        self.rating = None
        self.load_shedding = None
        self.nodal_restrictions = None

        self.contingency_flows_list = list()
        self.contingency_indices_list = list()  # [(m, c), ...]
        self.contingency_flows_slacks_list = list()

        self.contingency_gen_flows_list = list()

        self.contingency_hvdc_flows_list = list()

        self.solver_type = solver_type

        self.status = 100000  # a number that is not likely to be an enumeration value so converged returns false

        if ortools:
            if platform.system() == 'Darwin':
                self.solver = pywraplp.Solver.CreateSolver("GLOP")
                print('Forced the use of GLOP')
            else:
                self.solver = pywraplp.Solver.CreateSolver(self.solver_type.value)

        else:
            self.solver = solver_type

        self.problem = None

    def formulate(self):
        """
        Formulate the AC OPF time series in the non-sequential fashion (all to the solver_type at once)
        :return: PuLP Problem instance
        """

        # declare problem
        problem = LpProblem(name='DC_OPF_Time_Series')

        return problem

    def solve(self, msg=True):
        """
        Call PuLP to solve the problem
        """
        # self.problem.writeLP('OPF.lp')
        if self.solver_type == MIPSolvers.CBC:
            params = PULP_CBC_CMD(fracGap=0.00001, threads=None, msg=msg)

        elif self.solver_type == MIPSolvers.SCIP:
            params = SCIP_CMD(msg=msg)

        elif self.solver_type == MIPSolvers.CPLEX:
            params = CPLEX_CMD(msg=msg)

        elif self.solver_type == MIPSolvers.HiGS:
            params = HiGHS_CMD(msg=msg)

        elif self.solver_type == MIPSolvers.GUROBI:
            params = GUROBI_CMD(msg=msg)

        elif self.solver_type == MIPSolvers.XPRESS:
            params = XPRESS(msg=msg)

        else:
            raise Exception('Solver not supported! ' + str(self.solver_type))

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
            if isinstance(arr[i], int) or isinstance(arr[i], float):
                val[i] = arr[i]
            else:
                val[i] = arr[i].value()
        if make_abs:
            val = np.abs(val)

        return val

    def extract_list(self, lst):
        val = np.zeros(len(lst))
        for i in range(val.shape[0]):
            if isinstance(lst[i], int) or isinstance(lst[i], float):
                val[i] = lst[i]
            else:
                val[i] = lst[i].value()
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

    def get_power_injections(self):
        """
        return the branch overloads (time, device)
        :return: 2D array
        """
        return self.extract(self.Pinj) * self.numerical_circuit.Sbase

    def get_phase_shifts(self):
        """
        return the branch phase_shifts (time, device)
        :return: 2D array
        """
        return self.extract(self.phase_shift)

    def get_hvdc_flows(self):
        """
        return the branch overloads (time, device)
        :return: 2D array
        """
        return self.extract(self.hvdc_flow) * self.numerical_circuit.Sbase

    def get_loading(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.s_from, make_abs=False) / (self.rating + 1e-20)

    def get_branch_power_from(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.s_from, make_abs=False) * self.numerical_circuit.Sbase

    def get_branch_power_to(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.s_to, make_abs=False) * self.numerical_circuit.Sbase

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

    def get_contingency_flows_list(self):
        """
        return the load shedding (time, device)
        :return: 2D array
        """
        return self.extract_list(self.contingency_flows_list) * self.numerical_circuit.Sbase

    def get_contingency_flows_slacks_list(self):
        """
        return the load shedding (time, device)
        :return: 2D array
        """
        return self.extract_list(self.contingency_flows_slacks_list) * self.numerical_circuit.Sbase

    def get_shadow_prices(self):
        """
        Extract values fro the 2D array of LP variables
        :return: 2D numpy array
        """
        val = np.zeros(self.nodal_restrictions.shape)
        for i in range(val.shape[0]):
            if self.nodal_restrictions[i] is not None:
                if self.nodal_restrictions[i].pi is not None:
                    val[i] = - self.nodal_restrictions[i].pi
        return val.transpose()

    def converged(self):
        return True


    def get_contingency_gen_flows_list(self):
        """
        return the load shedding (time, device)
        :return: 2D array
        """
        return self.extract_list(self.contingency_gen_flows_list) * self.numerical_circuit.Sbase

    def get_contingency_hvdc_flows_list(self):
        """
        return the load shedding (time, device)
        :return: 2D array
        """
        return self.extract_list(self.contingency_hvdc_flows_list) * self.numerical_circuit.Sbase

class OpfTimeSeries:

    def __init__(self, numerical_circuit: OpfTimeCircuit,
                 start_idx, end_idx, solver_type: MIPSolvers=MIPSolvers.CBC,
                 skip_formulation=True, ortools=False):
        """

        :param numerical_circuit:
        :param start_idx:
        :param end_idx:
        """
        self.logger = Logger()

        self.numerical_circuit = numerical_circuit
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.solver_type = solver_type

        self.theta = None
        self.Pg = None
        self.Pb = None
        self.Pl = None

        self.Pinj = None
        self.hvdc_flow = None
        self.phase_shift = None

        self.E = None
        self.s_from = None
        self.s_to = None
        self.overloads = None
        self.rating = None
        self.load_shedding = None
        self.nodal_restrictions = None

        self.contingency_flows_list = list()
        self.contingency_indices_list = list()  # [(t, m, c), ...]
        self.contingency_flows_slacks_list = list()

        # if ortools:
        #     if platform.system() == 'Darwin':
        #         self.solver = pywraplp.Solver.CreateSolver("GLOP")
        #         print('Forced the use of GLOP')
        #     else:
        #         self.solver = pywraplp.Solver.CreateSolver(self.solver_type.value)
        #
        # else:
        #     self.solver = solver_type

        self.problem = None

    def formulate(self):
        """
        Formulate the AC OPF time series in the non-sequential fashion (all to the solver_type at once)
        :return: PuLP Problem instance
        """

        # declare problem
        problem = LpProblem(name='DC_OPF_Time_Series')

        return problem

    def solve(self, msg=False):
        """
        Call PuLP to solve the problem
        """

        if self.solver_type == MIPSolvers.CBC:
            params = PULP_CBC_CMD(fracGap=0.00001, threads=None, msg=msg)

        elif self.solver_type == MIPSolvers.HiGS:
            params = HiGHS_CMD(msg=msg)

        elif self.solver_type == MIPSolvers.SCIP:
            params = SCIP_CMD(msg=msg)

        elif self.solver_type == MIPSolvers.CPLEX:
            params = CPLEX_CMD(msg=msg)

        elif self.solver_type == MIPSolvers.GUROBI:
            params = GUROBI_CMD(msg=msg)

        elif self.solver_type == MIPSolvers.XPRESS:
            params = XPRESS(msg=msg)

        else:
            raise Exception('Solver not supported! ' + str(self.solver_type))

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
            if isinstance(arr[i, j], int) or isinstance(arr[i, j], float):
                val[i, j] = arr[i, j]
            else:
                val[i, j] = arr[i, j].value()
        if make_abs:
            val = np.abs(val)

        return val

    def extract_list(self, lst):
        val = np.zeros(len(lst))
        for i in range(val.shape[0]):
            if isinstance(lst[i], int) or isinstance(lst[i], float):
                val[i] = lst[i]
            else:
                val[i] = lst[i].value()
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
        return self.extract2D(self.s_from, make_abs=False) / (self.rating + 1e-20)

    def get_power_injections(self):
        """
        return the branch overloads (time, device)
        :return: 2D array
        """
        return self.extract2D(self.Pinj) * self.numerical_circuit.Sbase

    def get_phase_shifts(self):
        """
        return the branch phase_shifts (time, device)
        :return: 2D array
        """
        return self.extract2D(self.phase_shift)

    def get_hvdc_flows(self):
        """
        return the branch overloads (time, device)
        :return: 2D array
        """
        return self.extract2D(self.hvdc_flow) * self.numerical_circuit.Sbase

    def get_branch_power_from(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract2D(self.s_from, make_abs=False) * self.numerical_circuit.Sbase

    def get_branch_power_to(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract2D(self.s_to, make_abs=False) * self.numerical_circuit.Sbase

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

    def get_contingency_flows_list(self):
        """
        return the load shedding (time, device)
        :return: 2D array
        """
        return self.extract_list(self.contingency_flows_list) * self.numerical_circuit.Sbase

    def get_contingency_flows_slacks_list(self):
        """
        return the load shedding (time, device)
        :return: 2D array
        """
        return self.extract_list(self.contingency_flows_slacks_list) * self.numerical_circuit.Sbase

    def get_shadow_prices(self):
        """
        Extract values fro the 2D array of LP variables
        :return: 2D numpy array
        """
        val = np.zeros(self.nodal_restrictions.shape)
        for i, j in product(range(val.shape[0]), range(val.shape[1])):
            if self.nodal_restrictions[i, j] is not None:
                if self.nodal_restrictions[i, j].pi is not None:
                    val[i, j] = - self.nodal_restrictions[i, j].pi
        return val.transpose()
