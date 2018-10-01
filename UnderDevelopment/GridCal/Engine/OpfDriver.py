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

from warnings import warn
from PyQt5.QtCore import QRunnable
import numpy as np

from GridCal.Engine.IoStructures import CalculationInputs, OptimalPowerFlowResults
from GridCal.Engine.CalculationEngine import MultiCircuit
from GridCal.Engine.PlotConfig import LINEWIDTH
from GridCal.Engine.Numerical.MIP_OPF import AcOpf, DcOpf
from GridCal.Engine.PowerFlowDriver import PowerFlowMP, SolverType
from GridCal.Engine.Numerical.BlackBoxOPF import AcOPFBlackBox, solve_opf_dycors_serial

########################################################################################################################
# Optimal Power flow classes
########################################################################################################################


class OptimalPowerFlowOptions:

    def __init__(self, verbose=False, load_shedding=False, solver=SolverType.DC_OPF, realistic_results=False,
                 faster_less_accurate=False):
        """
        OPF options constructor
        :param verbose:
        :param load_shedding:
        :param solver:
        :param realistic_results:
        """
        self.verbose = verbose

        self.load_shedding = load_shedding

        self.solver = solver

        self.realistic_results = realistic_results

        self.faster_less_accurate = faster_less_accurate


class OptimalPowerFlow(QRunnable):
    # progress_signal = pyqtSignal(float)
    # progress_text = pyqtSignal(str)
    # done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: OptimalPowerFlowOptions):
        """
        PowerFlow class constructor
        @param grid: MultiCircuit Object
        @param options: OPF options
        """
        QRunnable.__init__(self)

        # Grid to run a power flow in
        self.grid = grid

        # Options to use
        self.options = options

        # OPF results
        self.results = None

        # set cancel state
        self.__cancel__ = False

        self.all_solved = True

    def island_mip_opf(self, calculation_input: CalculationInputs, buses, branches, t_idx=None):
        """
        Run a power flow simulation for a single circuit
        @param calculation_input: Single island circuit
        @param t_idx: time index, if none the default values are taken
        @return: OptimalPowerFlowResults object
        """

        # declare LP problem
        if self.options.solver == SolverType.DC_OPF:
            problem = DcOpf(calculation_input, buses, branches, self.options)

        elif self.options.solver == SolverType.AC_OPF:
            problem = AcOpf(calculation_input, buses, branches, self.options)

        else:
            raise Exception('Not implemented method ' + str(self.options.solver))

        # results
        problem.build(t_idx=t_idx)
        problem.set_loads(t_idx=t_idx)
        problem.solve()
        res = problem.get_results(t_idx=t_idx, realistic=self.options.realistic_results)

        return res, problem.solved

    def opf(self, t_idx=None, collect=True):
        """
        Run a power flow for every circuit
        @return: OptimalPowerFlowResults object
        """
        # print('PowerFlow at ', self.grid.name)

        # self.progress_signal.emit(0.0)

        if self.options.solver == SolverType.DYCORS_OPF:
            # the AcOPFBlackBox is formulated to take into account the islands already
            problem = AcOPFBlackBox(self.grid, verbose=False)

            # set the profile values if applicable
            if t_idx is not None:
                problem.set_loads(t_idx)

            # solve the problem
            val_opt, x_opt = solve_opf_dycors_serial(problem,
                                                     verbose=True,
                                                     stop_at=self.options.faster_less_accurate,
                                                     stop_value=0)

            # collect the OPF results
            self.results = problem.interpret_x(x_opt)
        else:
            n = len(self.grid.buses)
            m = len(self.grid.branches)
            self.results = OptimalPowerFlowResults()
            self.results.initialize(n, m)

            self.all_solved = True

            print('Compiling...', end='')
            numerical_circuit = self.grid.compile()
            calculation_inputs = numerical_circuit.compute()

            if len(calculation_inputs) > 1:

                for calculation_input in calculation_inputs:

                    buses = [self.grid.buses[i] for i in calculation_input.original_bus_idx]
                    branches = [self.grid.branches[i] for i in calculation_input.original_branch_idx]

                    if self.options.verbose:
                        print('Solving ' + calculation_input.name)

                    # run OPF
                    if len(calculation_input.ref) > 0:
                        optimal_power_flow_results, solved = self.island_mip_opf(calculation_input, buses,
                                                                                 branches, t_idx=t_idx)
                    else:
                        optimal_power_flow_results = OptimalPowerFlowResults(is_dc=True)
                        optimal_power_flow_results.initialize(calculation_input.nbus, calculation_input.nbr)
                        solved = True  # couldn't solve because it was impossible to formulate the problem so we skip it...
                        warn('The island does not have any slack...')

                    # assert the total solvability
                    self.all_solved = self.all_solved and solved

                    # merge island results
                    self.results.apply_from_island(optimal_power_flow_results,
                                                   calculation_input.original_bus_idx,
                                                   calculation_input.original_branch_idx)
            else:
                # only one island ...
                calculation_input = calculation_inputs[0]

                if self.options.verbose:
                    print('Solving ' + calculation_input.name)

                # run OPF
                optimal_power_flow_results, solved = self.island_mip_opf(calculation_input, self.grid.buses,
                                                                         self.grid.branches, t_idx=t_idx)

                # assert the total solvability
                self.all_solved = self.all_solved and solved

                # merge island results
                self.results.apply_from_island(optimal_power_flow_results,
                                               calculation_input.original_bus_idx,
                                               calculation_input.original_branch_idx)

            # collect results per generator
            if collect:
                print('Collecting generator results')
                self.results.controlled_generator_power = list()
                self.results.battery_power = list()

                for bus in self.grid.buses:
                    # Generators
                    for elm in bus.controlled_generators:
                        if elm.active and elm.enabled_dispatch:
                            self.results.controlled_generator_power.append(elm.LPVar_P.value())
                        else:
                            self.results.controlled_generator_power.append(0)

                    # batteries
                    for elm in bus.batteries:
                        if elm.active and elm.enabled_dispatch:
                            self.results.battery_power.append(elm.LPVar_P.value())
                        else:
                            self.results.battery_power.append(0)

                # convert the results to a numpy array
                self.results.controlled_generator_power = np.array(self.results.controlled_generator_power)
                self.results.battery_power = np.array(self.results.battery_power)

        return self.results

    def run(self):
        """

        :return:
        """
        self.opf(collect=True)

    def run_at(self, t):
        """
        Run power flow at the time series object index t
        @param t: time index
        @return: OptimalPowerFlowResults object
        """

        res = self.opf(t, collect=False)  # the collection of results is done in the OpfTimeSeriesDriver

        return res

    def cancel(self):
        self.__cancel__ = True

