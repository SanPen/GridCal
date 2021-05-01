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
import numba as nb

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.time_series_pf_data import compile_time_circuit
import GridCal.Engine.Simulations.LinearFactors.linear_analysis as la
from GridCal.Engine.Simulations.ATC.available_transfer_capacity_driver import AvailableTransferCapacityOptions, compute_atc, compute_transfer_indices
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_model import ResultsModel
from GridCal.Engine.Simulations.results_template import ResultsTemplate
from GridCal.Engine.Simulations.driver_template import TSDriverTemplate


class AvailableTransferCapacityTimeSeriesResults(ResultsTemplate):

    def __init__(self, n_br, n_bus, time_array, br_names, bus_names, bus_types):
        """

        :param n_br:
        :param n_bus:
        :param nt:
        :param br_names:
        :param bus_names:
        :param bus_types:
        """
        ResultsTemplate.__init__(self,
                                 name='ATC Time Series Results',
                                 available_results=[ResultTypes.AvailableTransferCapacity,
                                                    ResultTypes.AvailableTransferCapacityAlpha,
                                                    ResultTypes.AvailableTransferCapacityReport
                                                    ],
                                 data_variables=['atc',
                                                 'alpha',
                                                 'worst_contingency'])
        self.n_br = n_br
        self.n_bus = n_bus
        self.nt = len(time_array)
        self.time_array = time_array
        self.br_names = br_names
        self.bus_names = bus_names
        self.bus_types = bus_types

        # available transfer capacity matrix (branch, contingency branch)

        self.atc = np.zeros((self.nt, self.n_br))
        self.alpha = np.zeros((self.nt, self.n_br))
        self.worst_contingency = np.zeros((self.nt, self.n_br), dtype=int)

        self.report = list()
        self.report_headers = ['Name', 'ATC', 'Worst Contingency']
        self.report_indices = list()

        self.available_results = [ResultTypes.AvailableTransferCapacity,
                                  ResultTypes.AvailableTransferCapacityAlpha,
                                  ResultTypes.AvailableTransferCapacityReport
                                  ]

    def get_steps(self):
        return

    def make_report(self):
        self.report = list()
        self.report_headers = ['Name', 'ATC', 'Worst Contingency']
        self.report_indices = list()

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {'atc_from': self.atc_from.tolist(),
                'atc_to': self.atc_to.tolist(),
                'atc': self.atc.tolist()}
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

        index = self.time_array

        if result_type == ResultTypes.AvailableTransferCapacityAlpha:
            data = self.alpha
            y_label = '(p.u.)'
            title, _ = result_type.value
            labels = self.br_names

        elif result_type == ResultTypes.AvailableTransferCapacity:
            data = self.atc
            y_label = '(MW)'
            title, _ = result_type.value
            labels = self.br_names

        elif result_type == ResultTypes.AvailableTransferCapacityReport:
            data = np.array(self.report)
            y_label = ''
            title, _ = result_type.value
            index = self.report_indices
            labels = self.report_headers

        else:
            raise Exception('Result type not understood:' + str(result_type))

        # assemble model
        mdl = ResultsModel(data=data,
                           index=index,
                           columns=labels,
                           title=title,
                           ylabel=y_label)
        return mdl


class AvailableTransferCapacityTimeSeriesDriver(TSDriverTemplate):
    tpe = SimulationTypes.AvailableTransferCapacityTS_run
    name = tpe.value

    def __init__(self, grid: MultiCircuit, options: AvailableTransferCapacityOptions, start_=0, end_=None):
        """
        Power Transfer Distribution Factors class constructor
        @param grid: MultiCircuit Object
        @param options: OPF options
        @:param pf_results: PowerFlowResults, this is to get the flows
        """
        TSDriverTemplate.__init__(self,
                                  grid=grid,
                                  start_=start_,
                                  end_=end_)

        # Options to use
        self.options = options

        # OPF results
        self.results = AvailableTransferCapacityTimeSeriesResults(n_br=0,
                                                                  n_bus=0,
                                                                  time_array=[],
                                                                  br_names=[],
                                                                  bus_names=[],
                                                                  bus_types=[])

    def run(self):
        """
        Run thread
        """
        start = time.time()

        self.progress_signal.emit(0)

        time_indices = self.get_time_indices()

        # declare the linear analysis
        self.progress_text.emit('Analyzing...')
        linear_analysis = la.LinearAnalysis(grid=self.grid,
                                            distributed_slack=self.options.distributed_slack,
                                            correct_values=self.options.correct_values)
        linear_analysis.run()

        ts_numeric_circuit = compile_time_circuit(self.grid)
        ne = ts_numeric_circuit.nbr
        nc = ts_numeric_circuit.nbr
        nt = len(ts_numeric_circuit.time_array)

        # declare the results
        self.results = AvailableTransferCapacityTimeSeriesResults(n_br=ts_numeric_circuit.nbr,
                                                                  n_bus=ts_numeric_circuit.nbus,
                                                                  time_array=ts_numeric_circuit.time_array,
                                                                  br_names=ts_numeric_circuit.branch_names,
                                                                  bus_names=ts_numeric_circuit.bus_names,
                                                                  bus_types=ts_numeric_circuit.bus_types)

        # compute the base flows
        P = ts_numeric_circuit.Sbus.real
        flows = linear_analysis.get_flows_time_series(P)
        rates = ts_numeric_circuit.ContingencyRates.T
        for t in time_indices:

            if self.progress_text is not None:
                self.progress_text.emit('Available transfer capacity at ' + str(self.grid.time_profile[t]))

            # get the converted bus indices
            idx1b, idx2b = compute_transfer_indices(idx1=self.options.bus_idx_from,
                                                    idx2=self.options.bus_idx_to,
                                                    bus_types=ts_numeric_circuit.bus_types_prof(t))

            # compute the ATC
            atc, alpha, worst_contingency = compute_atc(ptdf=linear_analysis.PTDF,
                                                        lodf=linear_analysis.LODF,
                                                        P0=P[:, t],
                                                        flows=flows[t, :],
                                                        rates=rates[t, :],
                                                        idx1=idx1b,
                                                        idx2=idx2b,
                                                        dT=self.options.dT)

            # assign the results
            self.results.atc[t, :] = atc
            self.results.alpha[t, :] = alpha
            self.results.worst_contingency[t, :] = worst_contingency

            if self.progress_signal is not None:
                self.progress_signal.emit((t + 1) / nt * 100)

            if self.__cancel__:
                break

        self.results.make_report()

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

    from GridCal.Engine import PowerFlowOptions, FileOpen, LinearAnalysis, PowerFlowDriver, SolverType
    fname = r'C:\Users\penversa\Git\GridCal\Grids_and_profiles\grids\IEEE 118 Bus - ntc_areas.gridcal'

    main_circuit = FileOpen(fname).open()

    simulation_ = LinearAnalysis(grid=main_circuit)
    simulation_.run()

    pf_options = PowerFlowOptions(solver_type=SolverType.NR,
                                  retry_with_other_methods=True)
    power_flow = PowerFlowDriver(main_circuit, pf_options)
    power_flow.run()

    options = AvailableTransferCapacityOptions()
    driver = AvailableTransferCapacityTimeSeriesDriver(main_circuit, options, power_flow.results)
    driver.run()

    print()

