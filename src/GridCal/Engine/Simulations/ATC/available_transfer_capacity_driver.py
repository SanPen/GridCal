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
import time
import json
import numpy as np
from PySide2.QtCore import QThread, Signal

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.LinearFactors.linear_analysis import LinearAnalysis, make_worst_contingency_transfer_limits
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_model import ResultsModel

########################################################################################################################
# Optimal Power flow classes
########################################################################################################################


class AvailableTransferCapacityResults:

    def __init__(self, n_br, n_bus, br_names, bus_names, bus_types):
        """

        :param n_br:
        :param n_bus:
        :param br_names:
        :param bus_names:
        :param bus_types:
        """
        self.n_br = n_br
        self.n_bus = n_bus
        self.br_names = br_names
        self.bus_names = bus_names
        self.bus_types = bus_types

        # available transfer capacity matrix (branch, contingency branch)
        self.tmc = np.zeros((self.n_br, self.n_br))

        # stores the worst transfer capacities (from to) and (to from)
        self.worst_tmc = np.zeros((self.n_br, 2))

        self.available_results = [ResultTypes.AvailableTransferCapacityMatrix,
                                  ResultTypes.AvailableTransferCapacity]

    def get_steps(self):
        return

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {'worst_tmc': self.worst_tmc,
                'tmc': self.tmc.tolist()}
        return data

    def save(self, fname):
        """
        Export as json
        """
        with open(fname, "w") as output_file:
            json_str = json.dumps(self.get_results_dict())
            output_file.write(json_str)

    def mdl(self, result_type: ResultTypes):
        """
        Plot the results
        :param result_type:
        :return:
        """

        index = self.br_names

        if result_type == ResultTypes.AvailableTransferCapacityMatrix:
            data = self.tmc
            y_label = '(MW)'
            title = result_type.value
            labels = self.br_names
            # index = self.branch_names

        elif result_type == ResultTypes.AvailableTransferCapacity:
            data = self.worst_tmc
            y_label = '(MW)'
            title = result_type.value
            labels = ['From-to', 'To-from']
        else:
            raise Exception('Result type not understood:' + str(result_type))

        # assemble model
        mdl = ResultsModel(data=data,
                           index=index,
                           columns=labels,
                           title=title,
                           ylabel=y_label)
        return mdl


class AvailableTransferCapacityOptions:

    def __init__(self, distribute_slack=True, correct_values=True):
        """
        Power Transfer Distribution Factors' options
        :param distribute_slack:
        """
        self.distribute_slack = distribute_slack
        self.correct_values = correct_values


class AvailableTransferCapacityDriver(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()
    tpe = SimulationTypes.AvailableTransferCapacity_run
    name = tpe.value

    def __init__(self, grid: MultiCircuit, options: AvailableTransferCapacityOptions, pf_results):
        """
        Power Transfer Distribution Factors class constructor
        @param grid: MultiCircuit Object
        @param options: OPF options
        @:param pf_results: PowerFlowResults, this is to get the flows
        """
        QThread.__init__(self)

        # Grid to run
        self.grid = grid

        # Options to use
        self.options = options

        self.pf_results = pf_results

        # OPF results
        self.results = AvailableTransferCapacityResults(n_br=0,
                                                        n_bus=0,
                                                        br_names=[],
                                                        bus_names=[],
                                                        bus_types=[])

        # set cancel state
        self.__cancel__ = False

        self.elapsed = 0.0

        self.logger = Logger()

    def run(self):
        """
        Run thread
        """
        start = time.time()
        self.progress_text.emit('Analyzing')
        self.progress_signal.emit(0)

        # declare the linear analysis
        simulation = LinearAnalysis(grid=main_circuit)
        simulation.run()

        # declare the results
        self.results = AvailableTransferCapacityResults(n_br=simulation.results.n_br,
                                                        n_bus=simulation.results.n_bus,
                                                        br_names=simulation.results.br_names,
                                                        bus_names=simulation.results.bus_names,
                                                        bus_types=simulation.results.bus_types)

        # get normal transfer limits
        tm = simulation.get_transfer_limits(flows=self.pf_results.Sf.real)

        # get the contingency transfer limits
        tmc = simulation.get_contingency_transfer_limits(flows=self.pf_results.Sf.real)

        # post-process and store the results
        self.results.tmc = tmc
        self.results.worst_tmc = make_worst_contingency_transfer_limits(tmc)

        end = time.time()
        self.elapsed = end - start
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def get_steps(self):
        """
        Get variations list of strings
        """
        if self.results is not None:
            return [v for v in self.results.br_names]
        else:
            return list()

    def cancel(self):
        self.__cancel__ = True


if __name__ == '__main__':

    from GridCal.Engine import *
    fname = r'C:\Users\penversa\Git\GridCal\Grids_and_profiles\grids\IEEE 118 Bus - ntc_areas.gridcal'

    main_circuit = FileOpen(fname).open()

    simulation = LinearAnalysis(grid=main_circuit)
    simulation.run()

    pf_options = PowerFlowOptions(solver_type=SolverType.NR,
                                  control_q=ReactivePowerControlMode.NoControl,
                                  retry_with_other_methods=True)
    power_flow = PowerFlowDriver(main_circuit, pf_options)
    power_flow.run()

    options = AvailableTransferCapacityOptions()
    driver = AvailableTransferCapacityDriver(main_circuit, options, power_flow.results)
    driver.run()

    print()

