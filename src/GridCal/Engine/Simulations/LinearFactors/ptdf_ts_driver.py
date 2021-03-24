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

import json
import pandas as pd
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve, factorized
import time

from PySide2.QtCore import QThread, Signal

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCal.Engine.Simulations.LinearFactors.analytic_ptdf import LinearAnalysis
from GridCal.Engine.Simulations.LinearFactors.analytic_ptdf_driver import LinearAnalysisOptions
from GridCal.Engine.Simulations.results_model import ResultsModel
from GridCal.Engine.Core.time_series_pf_data import compile_time_circuit


class PtdfTimeSeriesResults:

    def __init__(self, n, m, time_array, bus_names, bus_types, branch_names):
        """
        TimeSeriesResults constructor
        @param n: number of buses
        @param m: number of branches
        @param nt: number of time steps
        """
        self.name = 'PTDF Time series'
        self.nt = len(time_array)
        self.m = m
        self.n = n
        self.time = time_array

        self.bus_names = bus_names

        self.bus_types = bus_types

        self.branch_names = branch_names

        self.voltage = np.ones((self.nt, n), dtype=float)

        self.S = np.zeros((self.nt, n), dtype=float)

        self.Sf = np.zeros((self.nt, m), dtype=float)

        self.loading = np.zeros((self.nt, m), dtype=float)

        self.losses = np.zeros((self.nt, m), dtype=float)

        self.available_results = [
                                  # ResultTypes.BusVoltageModule,
                                  ResultTypes.BusActivePower,
                                  ResultTypes.BranchActivePowerFrom,
                                  ResultTypes.BranchLoading
                                 ]

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {'V': self.voltage.tolist(),
                'P': self.S.real.tolist(),
                'Q': self.S.imag.tolist(),
                'Sbr_real': self.Sf.real.tolist(),
                'Sbr_imag': self.Sf.imag.tolist(),
                'loading': np.abs(self.loading).tolist()}
        return data

    def save(self, file_name):
        """
        Export as json
        :param file_name: Name of the file
        """

        with open(file_name, "wb") as output_file:
            json_str = json.dumps(self.get_results_dict())
            output_file.write(json_str)

    def mdl(self, result_type: ResultTypes) -> "ResultsModel":
        """
        Get ResultsModel instance
        :param result_type:
        :return: ResultsModel instance
        """

        if result_type == ResultTypes.BusActivePower:
            labels = self.bus_names
            data = self.S
            y_label = '(MW)'
            title = 'Bus active power '

        elif result_type == ResultTypes.BranchActivePowerFrom:
            labels = self.branch_names
            data = self.Sf.real
            y_label = '(MW)'
            title = 'Branch power '

        elif result_type == ResultTypes.BranchLoading:
            labels = self.branch_names
            data = self.loading * 100
            y_label = '(%)'
            title = 'Branch loading '

        elif result_type == ResultTypes.BranchLosses:
            labels = self.branch_names
            data = self.losses
            y_label = '(MVA)'
            title = 'Branch losses'

        elif result_type == ResultTypes.BusVoltageModule:
            labels = self.bus_names
            data = self.voltage
            y_label = '(p.u.)'
            title = 'Bus voltage'

        else:
            raise Exception('Result type not understood:' + str(result_type))

        if self.time is not None:
            index = self.time
        else:
            index = list(range(data.shape[0]))

        # assemble model
        return ResultsModel(data=data, index=index, columns=labels, title=title, ylabel=y_label, units=y_label)


class PtdfTimeSeries(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()
    name = 'PTDF Time Series'

    def __init__(self, grid: MultiCircuit, options: LinearAnalysisOptions, start_=0, end_=None):
        """
        TimeSeries constructor
        @param grid: MultiCircuit instance
        @param options: LinearAnalysisOptions instance
        """
        QThread.__init__(self)

        # reference the grid directly
        self.grid = grid

        self.options = options

        self.results = PtdfTimeSeriesResults(n=0,
                                             m=0,
                                             time_array=[],
                                             bus_names=[],
                                             bus_types=[],
                                             branch_names=[])

        self.ptdf_driver = LinearAnalysis(grid=self.grid, distributed_slack=self.options.distribute_slack)

        self.start_ = start_

        self.end_ = end_

        self.indices = pd.to_datetime(self.grid.time_profile)

        self.elapsed = 0

        self.logger = Logger()

        self.__cancel__ = False

    def get_steps(self):
        """
        Get time steps list of strings
        """

        return [l.strftime('%d-%m-%Y %H:%M') for l in self.indices]

    def run(self):
        """
        Run the time series simulation
        @return:
        """
        self.__cancel__ = False
        a = time.time()

        if self.end_ is None:
            self.end_ = len(self.grid.time_profile)
        time_indices = np.arange(self.start_, self.end_ + 1)

        ts_numeric_circuit = compile_time_circuit(self.grid)
        self.results = PtdfTimeSeriesResults(n=ts_numeric_circuit.nbus,
                                             m=ts_numeric_circuit.nbr,
                                             time_array=ts_numeric_circuit.time_array[time_indices],
                                             bus_names=ts_numeric_circuit.bus_names,
                                             bus_types=ts_numeric_circuit.bus_types,
                                             branch_names=ts_numeric_circuit.branch_names)

        self.indices = pd.to_datetime(ts_numeric_circuit.time_array[time_indices])

        self.progress_text.emit('Computing PTDF...')
        ptdf_analysis = LinearAnalysis(grid=self.grid, distributed_slack=self.options.distribute_slack)
        ptdf_analysis.run()

        self.progress_text.emit('Computing branch flows...')

        Pbus_0 = ts_numeric_circuit.Sbus.real[:, time_indices]
        self.results.Sf = ptdf_analysis.get_branch_time_series(Pbus_0)

        # compute post process
        self.results.loading = self.results.Sf / (ts_numeric_circuit.Rates[:, time_indices].T + 1e-9)
        self.results.S = Pbus_0.T

        self.elapsed = time.time() - a

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        """
        Cancel the simulation
        """
        self.__cancel__ = True
        if self.ptdf_driver is not None:
            self.ptdf_driver.cancel()

        if self.pool is not None:
            self.pool.terminate()
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled!')
        self.done_signal.emit()


if __name__ == '__main__':
    from matplotlib import pyplot as plt
    from GridCal.Engine import *

    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'
    main_circuit = FileOpen(fname).open()

    options_ = LinearAnalysisOptions()
    ptdf_driver = PtdfTimeSeries(grid=main_circuit, options=options_)
    ptdf_driver.run()

    pf_options_ = PowerFlowOptions(solver_type=SolverType.NR)
    ts_driver = TimeSeries(grid=main_circuit, options=pf_options_)
    ts_driver.run()

    fig = plt.figure()
    ax1 = fig.add_subplot(221)
    ax1.set_title('Newton-Raphson based flow')
    ax1.plot(ts_driver.results.Sf.real)

    ax2 = fig.add_subplot(222)
    ax2.set_title('PTDF based flow')
    ax2.plot(ptdf_driver.results.Sf.real)

    ax3 = fig.add_subplot(223)
    ax3.set_title('Difference')
    diff = ts_driver.results.Sf.real - ptdf_driver.results.Sf.real
    ax3.plot(diff)

    fig2 = plt.figure()
    ax1 = fig2.add_subplot(221)
    ax1.set_title('Newton-Raphson based voltage')
    ax1.plot(np.abs(ts_driver.results.voltage))

    ax2 = fig2.add_subplot(222)
    ax2.set_title('PTDF based voltage')
    ax2.plot(ptdf_driver.results.voltage)

    ax3 = fig2.add_subplot(223)
    ax3.set_title('Difference')
    diff = np.abs(ts_driver.results.voltage) - ptdf_driver.results.voltage
    ax3.plot(diff)

    plt.show()
