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
import time
import multiprocessing

from PySide2.QtCore import QThread, QThreadPool, Signal

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCal.Engine.Simulations.PTDF.ptdf_driver import PTDF, PTDFOptions, PtdfGroupMode
from GridCal.Gui.GuiFunctions import ResultsModel


class PtdfTimeSeriesResults(PowerFlowResults):

    def __init__(self, n, m, nt, start, end, time_array=None):
        """
        TimeSeriesResults constructor
        @param n: number of buses
        @param m: number of branches
        @param nt: number of time steps
        """
        PowerFlowResults.__init__(self)
        self.name = 'PTDF Time series'
        self.nt = nt
        self.m = m
        self.n = n
        self.start = start
        self.end = end

        self.time = time_array

        if nt > 0:

            self.voltage = np.zeros((nt, n), dtype=float)

            self.S = np.zeros((nt, n), dtype=float)

            self.Sbranch = np.zeros((nt, m), dtype=float)

            self.loading = np.zeros((nt, m), dtype=float)

        else:

            self.voltage = None

            self.S = None

            self.Sbranch = None

            self.loading = None

        self.available_results = [ResultTypes.BusVoltageModule,
                                  ResultTypes.BusActivePower,
                                  # ResultTypes.BusReactivePower,
                                  ResultTypes.BranchPower,
                                  ResultTypes.BranchLoading]

    def set_at(self, t, results: PowerFlowResults):
        """
        Set the results at the step t
        @param t: time index
        @param results: PowerFlowResults instance
        """

        self.voltage[t, :] = results.voltage

        self.S[t, :] = results.Sbus

        self.Sbranch[t, :] = results.Sbranch

        self.loading[t, :] = results.loading

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {'V': self.voltage.tolist(),
                'P': self.S.real.tolist(),
                'Q': self.S.imag.tolist(),
                'Sbr_real': self.Sbranch.real.tolist(),
                'Sbr_imag': self.Sbranch.imag.tolist(),
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

    def mdl(self, result_type: ResultTypes, indices=None, names=None) -> "ResultsModel":
        """
        Get ResultsModel instance
        :param result_type:
        :param indices:
        :param names:
        :return: ResultsModel instance
        """

        if indices is None:
            indices = np.array(range(len(names)))

        if len(indices) > 0:

            labels = names[indices]

            if result_type == ResultTypes.BusActivePower:
                data = self.S[:, indices].real
                y_label = '(MW)'
                title = 'Bus active power '

            elif result_type == ResultTypes.BusReactivePower:
                data = self.S[:, indices].imag
                y_label = '(MVAr)'
                title = 'Bus reactive power '

            elif result_type == ResultTypes.BranchPower:
                data = self.Sbranch[:, indices]
                y_label = '(MVA)'
                title = 'Branch power '

            elif result_type == ResultTypes.BranchLoading:
                data = self.loading[:, indices] * 100
                y_label = '(%)'
                title = 'Branch loading '

            elif result_type == ResultTypes.BranchLosses:
                data = self.losses[:, indices]
                y_label = '(MVA)'
                title = 'Branch losses'

            elif result_type == ResultTypes.BusVoltageModule:
                data = self.voltage[:, indices]
                y_label = '(p.u.)'
                title = 'Bus voltage'

            elif result_type == ResultTypes.SimulationError:
                data = self.error.reshape(-1, 1)
                y_label = 'Per unit power'
                labels = [y_label]
                title = 'Error'

            else:
                raise Exception('Result type not understood:' + str(result_type))

            if self.time is not None:
                index = self.time
            else:
                index = list(range(data.shape[0]))

            # assemble model
            mdl = ResultsModel(data=data, index=index, columns=labels, title=title, ylabel=y_label)
            return mdl


class PtdfTimeSeries(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()
    name = 'PTDF Time Series'

    def __init__(self, grid: MultiCircuit, pf_options: PowerFlowOptions, start_=0, end_=None):
        """
        TimeSeries constructor
        @param grid: MultiCircuit instance
        @param pf_options: PowerFlowOptions instance
        """
        QThread.__init__(self)

        # reference the grid directly
        self.grid = grid

        self.pf_options = pf_options

        self.results = None

        self.start_ = start_

        self.end_ = end_

        self.elapsed = 0

        self.logger = Logger()

        self.__cancel__ = False

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return [l.strftime('%d-%m-%Y %H:%M') for l in pd.to_datetime(self.grid.time_profile)]

    def run_nodal_mode(self) -> PtdfTimeSeriesResults:
        """
        Run multi thread time series
        :return: TimeSeriesResults instance
        """

        # initialize the grid time series results, we will append the island results with another function
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        nt = len(self.grid.time_profile)
        results = PtdfTimeSeriesResults(n, m, nt, self.start_, self.end_, time_array=self.grid.time_profile)

        if self.end_ is None:
            self.end_ = nt

        # if there are valid profiles...
        if self.grid.time_profile is not None:

            nc = self.grid.compile()

            options_ = PTDFOptions(group_mode=PtdfGroupMode.ByNode,
                                   power_increment=10,
                                   use_multi_threading=False)

            # run a node based PTDF
            ptdf_driver = PTDF(grid=self.grid,
                               options=options_,
                               pf_options=self.pf_options)
            ptdf_driver.progress_signal = self.progress_signal
            ptdf_driver.run()

            # get the PTDF matrix
            ptdf_driver.results.consolidate()
            ptdf = ptdf_driver.results.flows_sensitivity_matrix
            vtdf = ptdf_driver.results.voltage_sensitivity_matrix

            # compose the power injections
            Pbus = nc.get_power_injections().real

            # base magnitudes
            Pbr_0 = ptdf_driver.results.default_pf_results.Sbranch.real  # MW
            V_0 = np.abs(ptdf_driver.results.default_pf_results.voltage)  # MW
            Pbus_0 = nc.C_bus_gen * nc.generator_power - nc.C_bus_load * nc.load_power.real  # MW

            # run the PTDF time series
            for k, t_idx in enumerate(range(self.start_, self.end_)):
                dP = (Pbus_0[:] - Pbus[:, t_idx])
                results.voltage[k, :] = V_0 + np.dot(dP, vtdf)
                results.Sbranch[k, :] = Pbr_0 + np.dot(dP, ptdf)
                results.loading[k, :] = results.Sbranch[k, :] / (nc.br_rates + 1e-9)
                results.S[k, :] = Pbus[:, t_idx]

                progress = ((t_idx - self.start_ + 1) / (self.end_ - self.start_)) * 100
                self.progress_signal.emit(progress)
                self.progress_text.emit('Simulating PTDF at ' + str(self.grid.time_profile[t_idx]))

        else:
            print('There are no profiles')
            self.progress_text.emit('There are no profiles')

        return results

    def run(self):
        """
        Run the time series simulation
        @return:
        """
        self.__cancel__ = False
        a = time.time()

        self.results = self.run_nodal_mode()

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
        self.pool.terminate()
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled!')
        self.done_signal.emit()


if __name__ == '__main__':
    from matplotlib import pyplot as plt
    from GridCal.Engine import FileOpen, SolverType, TimeSeries

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'
    fname = r'C:\Users\PENVERSA\OneDrive - Red Eléctrica Corporación\Escritorio\IEEE cases\WSCC 9 bus.gridcal'
    main_circuit = FileOpen(fname).open()

    pf_options_ = PowerFlowOptions(solver_type=SolverType.NR)
    ptdf_driver = PtdfTimeSeries(grid=main_circuit, pf_options=pf_options_)
    ptdf_driver.run()

    pf_options_ = PowerFlowOptions(solver_type=SolverType.NR)
    ts_driver = TimeSeries(grid=main_circuit, options=pf_options_)
    ts_driver.run()

    fig = plt.figure()
    ax1 = fig.add_subplot(221)
    ax1.set_title('Newton-Raphson based flow')
    ax1.plot(ts_driver.results.Sbranch.real)

    ax2 = fig.add_subplot(222)
    ax2.set_title('PTDF based flow')
    ax2.plot(ptdf_driver.results.Sbranch.real)

    ax3 = fig.add_subplot(223)
    ax3.set_title('Difference')
    diff = ts_driver.results.Sbranch.real - ptdf_driver.results.Sbranch.real
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
