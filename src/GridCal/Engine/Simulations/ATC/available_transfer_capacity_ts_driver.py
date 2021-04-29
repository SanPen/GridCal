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
from PySide2.QtCore import QThread, Signal

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.time_series_pf_data import compile_time_circuit
import GridCal.Engine.Simulations.LinearFactors.linear_analysis as la
from GridCal.Engine.Simulations.ATC.available_transfer_capacity_driver import AvailableTransferCapacityOptions
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_model import ResultsModel


@nb.njit(parallel=True)
def calculate_branch_atc_full(m, ptdf, lodf, flows, rates, thr=0.2):
    """

    :param m: branch to inspect
    :param ptdf: PTDF matrix (n-branch, n-bus)
    :param lodf: LODF matrox (n-branch, n-branch)
    :param flows: Flows profiles (n-time, n-branch)
    :param rates: Rates profiles (n-time, n-branch)
    :param thr: threshold
    :return:
    """

    nbr = ptdf.shape[0]
    nbus = ptdf.shape[1]
    nt = flows.shape[0]
    atc = np.zeros(nt) + 1e20

    # compute OTDF for the line m
    otdf = np.zeros((nbr, nbus))
    for c in range(nbr):
        for j in range(nbus):
            if abs(ptdf[m, j]) > thr:
                otdf[c, j] = ptdf[m, j] + lodf[m, c] * ptdf[c, j]

    for t in nb.prange(nt):
        for c in range(nbr):
            for j in range(nbus):

                if abs(otdf[c, j]) > thr:
                    omw = flows[t, m] + lodf[m, c] * flows[t, c]

                    if ptdf[m, j] > 0:
                        T_normal = (rates[t, m] - flows[t, m]) / ptdf[m, j]
                    elif ptdf[m, j] < 0:
                        T_normal = (-rates[t, m] - flows[t, m]) / ptdf[m, j]
                    else:
                        T_normal = 1e20  # numerical infinite

                    if otdf[c, j] > 0:
                        T_contingency = (rates[t, m] - omw) / otdf[c, j]
                    elif otdf[c, j] < 0:
                        T_contingency = (-rates[t, m] - omw) / otdf[c, j]
                    else:
                        T_contingency = 1e20  # numerical infinite

                    atc_val = min(T_normal, T_contingency)
                    atc[t] = min(atc[t], atc_val)

    return atc


class AvailableTransferCapacityTimeSeriesResults:

    def __init__(self, n_br, n_bus, time_array, br_names, bus_names, bus_types):
        """

        :param n_br:
        :param n_bus:
        :param nt:
        :param br_names:
        :param bus_names:
        :param bus_types:
        """
        self.n_br = n_br
        self.n_bus = n_bus
        self.nt = len(time_array)
        self.time_array = time_array
        self.br_names = br_names
        self.bus_names = bus_names
        self.bus_types = bus_types

        # available transfer capacity matrix (branch, contingency branch)
        self.atc_from = np.zeros((self.nt, self.n_br))
        self.atc_to = np.zeros((self.nt, self.n_br))
        self.worst_atc = np.zeros((self.nt, self.n_br))

        self.available_results = [ResultTypes.AvailableTransferCapacity,
                                  ResultTypes.AvailableTransferCapacityFrom,
                                  ResultTypes.AvailableTransferCapacityTo]

    def get_steps(self):
        return

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {'atc_from': self.atc_from.tolist(),
                'atc_to': self.atc_to.tolist(),
                'worst_atc': self.worst_atc.tolist()}
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

        if result_type == ResultTypes.AvailableTransferCapacityFrom:
            data = self.atc_from
            y_label = '(MW)'
            title, _ = result_type.value
            labels = self.br_names

        elif result_type == ResultTypes.AvailableTransferCapacityTo:
            data = self.atc_to
            y_label = '(MW)'
            title, _ = result_type.value
            labels = self.br_names

        elif result_type == ResultTypes.AvailableTransferCapacity:
            data = self.worst_atc
            y_label = '(MW)'
            title, _ = result_type.value
            labels = self.br_names
        else:
            raise Exception('Result type not understood:' + str(result_type))

        # assemble model
        mdl = ResultsModel(data=data,
                           index=index,
                           columns=labels,
                           title=title,
                           ylabel=y_label)
        return mdl


@nb.njit()
def fill_atc_results(t, tmc, atc_from, atc_to, atc_worst):

    nbr = tmc.shape[0]

    for i in range(nbr):  # traverse branches
        mn_ = 1e20
        mx_ = -1e20
        worst = 0
        for j in range(nbr): # traverse contingencies
            if tmc[i, j] > mx_:
                atc_from[t, i] = tmc[i, j]
                mx_ = tmc[i, j]

            if tmc[i, j] < mn_:
                atc_to[t, i] = tmc[i, j]
                mn_ = tmc[i, j]

            if abs(atc_from[t, i]) > abs(atc_to[t, i]):
                atc_worst[t, i] = atc_from[t, i]
            else:
                atc_worst[t, i] = atc_to[t, i]


class AvailableTransferCapacityTimeSeriesDriver(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()
    tpe = SimulationTypes.AvailableTransferCapacityTS_run
    name = tpe.value

    def __init__(self, grid: MultiCircuit, options: AvailableTransferCapacityOptions, start_=0, end_=None):
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

        self.start_ = start_

        self.end_ = end_

        self.indices = self.grid.time_profile

        # OPF results
        self.results = AvailableTransferCapacityTimeSeriesResults(n_br=0,
                                                                  n_bus=0,
                                                                  time_array=[],
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

        self.progress_signal.emit(0)

        if self.end_ is None:
            self.end_ = len(self.grid.time_profile)
        time_indices = np.arange(self.start_, self.end_ + 1)

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
        rates = ts_numeric_circuit.Rates.T
        for m in range(ne):

            if self.progress_text is not None:
                self.progress_text.emit('Available transfer capacity for ' + ts_numeric_circuit.branch_names[m])

            self.results.worst_atc[:, m] = calculate_branch_atc_full(m=m,
                                                                     ptdf=linear_analysis.PTDF,
                                                                     lodf=linear_analysis.LODF,
                                                                     flows=flows,
                                                                     rates=rates)

            if self.progress_signal is not None:
                self.progress_signal.emit((m + 1) / ne * 100)

            if self.__cancel__:
                break

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

