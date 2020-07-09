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
from GridCal.Engine.Simulations.PowerFlow.jacobian_based_power_flow import Jacobian
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from GridCal.Engine.Simulations.PTDF.ptdf_driver import PTDF, PTDFOptions, PtdfGroupMode
from GridCal.Gui.GuiFunctions import ResultsModel
from GridCal.Engine.Core.time_series_opf_data import compile_opf_time_circuit, split_opf_time_circuit_into_islands


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

        self.voltage = np.zeros((self.nt, n), dtype=float)

        self.S = np.zeros((self.nt, n), dtype=float)

        self.Sbranch = np.zeros((self.nt, m), dtype=float)

        self.loading = np.zeros((self.nt, m), dtype=float)

        self.losses = np.zeros((self.nt, m), dtype=float)

        self.available_results = [ResultTypes.BusVoltageModule,
                                  ResultTypes.BusActivePower,
                                  ResultTypes.BranchActivePower,
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

    def mdl(self, result_type: ResultTypes) -> "ResultsModel":
        """
        Get ResultsModel instance
        :param result_type:
        :return: ResultsModel instance
        """

        if result_type == ResultTypes.BusActivePower:
            labels = self.bus_names
            data = self.S.real
            y_label = '(MW)'
            title = 'Bus active power '

        elif result_type == ResultTypes.BusReactivePower:
            labels = self.bus_names
            data = self.S.imag
            y_label = '(MVAr)'
            title = 'Bus reactive power '

        elif result_type == ResultTypes.BranchPower:
            labels = self.branch_names
            data = self.Sbranch
            y_label = '(MVA)'
            title = 'Branch power '

        elif result_type == ResultTypes.BranchActivePower:
            labels = self.branch_names
            data = self.Sbranch.real
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


def compute_ptdf(Ybus, Yf, Yt, Cf, Ct, V, Ibus, Sbus, pq, pv):
    """

    :param Ybus:
    :param Yf:
    :param Yt:
    :param Cf:
    :param Ct:
    :param V:
    :param Ibus:
    :param Sbus:
    :param pq:
    :param pv:
    :return:
    """
    n = len(V)
    # set up indexing for updating V
    pvpq = np.r_[pv, pq]
    npv = len(pv)
    npq = len(pq)
    # j1:j2 - V angle of pv and pq buses
    j1 = 0
    j2 = npv + npq
    # j2:j3 - V mag of pq buses
    j3 = j2 + npq

    # compute the Jacobian
    J = Jacobian(Ybus, V, Ibus, pq, pvpq)

    # compute the power increment (f)
    Scalc = V * np.conj(Ybus * V - Ibus)
    dS = Scalc - Sbus
    f = np.r_[dS[pvpq].real, dS[pq].imag]

    # solve the voltage increment
    dx = spsolve(J, f)

    # reassign the solution vector
    dVa = np.zeros(n)
    dVm = np.zeros(n)
    dVa[pvpq] = dx[j1:j2]
    dVm[pq] = dx[j2:j3]

    # compute branch derivatives

    If = Yf * V
    It = Yt * V
    E = V / np.abs(V)
    Vdiag = sp.diags(V)
    Vdiag_conj = sp.diags(np.conj(V))
    Ediag = sp.diags(E)
    Ediag_conj = sp.diags(np.conj(E))
    If_diag_conj = sp.diags(np.conj(If))
    It_diag_conj = sp.diags(np.conj(It))
    Yf_conj = Yf.copy()
    Yf_conj.data = np.conj(Yf_conj.data)
    Yt_conj = Yt.copy()
    Yt_conj.data = np.conj(Yt_conj.data)

    dSf_dVa = 1j * (If_diag_conj * Cf * Vdiag - sp.diags(Cf * V) * Yf_conj * Vdiag_conj)
    dSf_dVm = If_diag_conj * Cf * Ediag - sp.diags(Cf * V) * Yf_conj * Ediag_conj

    dSt_dVa = 1j * (It_diag_conj * Ct * Vdiag - sp.diags(Ct * V) * Yt_conj * Vdiag_conj)
    dSt_dVm = It_diag_conj * Ct * Ediag - sp.diags(Ct * V) * Yt_conj * Ediag_conj

    # compute the PTDF

    dVmf = Cf * dVm
    dVaf = Cf * dVa
    dPf_dVa = dSf_dVa.real
    dPf_dVm = dSf_dVm.real

    dVmt = Ct * dVm
    dVat = Ct * dVa
    dPt_dVa = dSt_dVa.real
    dPt_dVm = dSt_dVm.real

    PTDF = sp.diags(dVmf) * dPf_dVm + sp.diags(dVmt) * dPt_dVm + sp.diags(dVaf) * dPf_dVa + sp.diags(dVat) * dPt_dVa

    return PTDF




class PtdfTimeSeries(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()
    name = 'PTDF Time Series'

    def __init__(self, grid: MultiCircuit, pf_options: PowerFlowOptions, start_=0, end_=None, power_delta=10):
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

        self.ptdf_driver = None

        self.start_ = start_

        self.end_ = end_

        self.power_delta = power_delta

        self.elapsed = 0

        self.logger = Logger()

        self.__cancel__ = False

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return [l.strftime('%d-%m-%Y %H:%M') for l in pd.to_datetime(self.grid.time_profile)]

    def run_nodal_mode(self, time_indices) -> PtdfTimeSeriesResults:
        """
        Run multi thread time series
        :return: TimeSeriesResults instance
        """

        # initialize the grid time series results, we will append the island results with another function
        nc = compile_opf_time_circuit(circuit=self.grid,
                                      apply_temperature=self.pf_options.apply_temperature_correction,
                                      branch_tolerance_mode=self.pf_options.branch_impedance_tolerance_mode)

        results = PtdfTimeSeriesResults(n=nc.nbus,
                                        m=nc.nbr,
                                        time_array=self.grid.time_profile[time_indices],
                                        bus_names=nc.bus_names,
                                        bus_types=nc.bus_types,
                                        branch_names=nc.branch_names)

        # if there are valid profiles...
        if self.grid.time_profile is not None:

            options_ = PTDFOptions(group_mode=PtdfGroupMode.ByNode,
                                   power_increment=self.power_delta,
                                   use_multi_threading=False)

            # run a node based PTDF
            self.ptdf_driver = PTDF(grid=self.grid,
                                    options=options_,
                                    pf_options=self.pf_options)
            self.ptdf_driver.progress_signal = self.progress_signal
            self.ptdf_driver.run()

            # get the PTDF matrix
            self.ptdf_driver.results.consolidate()
            ptdf = self.ptdf_driver.results.flows_sensitivity_matrix
            vtdf = self.ptdf_driver.results.voltage_sensitivity_matrix

            # compose the power injections
            Pbus = nc.get_power_injections().real

            # base magnitudes
            Pbr_0 = self.ptdf_driver.results.default_pf_results.Sbranch.real  # MW
            V_0 = np.abs(self.ptdf_driver.results.default_pf_results.voltage)  # MW
            Pbus_0 = self.ptdf_driver.results.default_pf_results.Sbus.real   # MW

            # run the PTDF time series
            for k, t_idx in enumerate(time_indices):
                dP = (Pbus_0[:] - Pbus[:, t_idx])
                results.voltage[k, :] = V_0 + np.dot(dP, vtdf)
                results.Sbranch[k, :] = Pbr_0 + np.dot(dP, ptdf)
                results.loading[k, :] = results.Sbranch[k, :] / (nc.branch_rates[t_idx, :] + 1e-9)
                results.S[k, :] = Pbus[:, t_idx]

                progress = ((t_idx - self.start_ + 1) / (self.end_ - self.start_)) * 100
                self.progress_signal.emit(progress)
                self.progress_text.emit('Simulating PTDF at ' + str(self.grid.time_profile[t_idx]))

        else:
            print('There are no profiles')
            self.progress_text.emit('There are no profiles')

        return results

    def run_illinois_mode(self, time_indices) -> PtdfTimeSeriesResults:
        """
        Run the PTDF with the illinois formulation
        :return: TimeSeriesResults instance
        """

        # initialize the grid time series results, we will append the island results with another function
        nc = compile_opf_time_circuit(circuit=self.grid,
                                      apply_temperature=self.pf_options.apply_temperature_correction,
                                      branch_tolerance_mode=self.pf_options.branch_impedance_tolerance_mode)

        results = PtdfTimeSeriesResults(n=nc.nbus,
                                        m=nc.nbr,
                                        time_array=self.grid.time_profile[time_indices],
                                        bus_names=nc.bus_names,
                                        bus_types=nc.bus_types,
                                        branch_names=nc.branch_names)

        # if there are valid profiles...
        if self.grid.time_profile is not None:

            # run a power flow to get the initial branch power and compose the second branch power with the increment
            driver = PowerFlowDriver(grid=self.grid, options=self.pf_options)
            driver.run()

            # compile the islands
            islands = split_opf_time_circuit_into_islands(nc)

            # compose the power injections
            Pbus_0 = driver.results.Sbus.real
            V_0 = np.abs(driver.results.voltage)
            Pbr_0 = driver.results.Sbranch.real

            for island in islands:

                PTDF = compute_ptdf(Ybus=island.Ybus,
                                    Yf=island.Yf,
                                    Yt=island.Yt,
                                    Cf=island.C_branch_bus_f,
                                    Ct=island.C_branch_bus_t,
                                    V=island.Vbus[0, :],
                                    Ibus=island.Ibus[:, 0],
                                    Sbus=island.Sbus[:, 0],
                                    pq=island.pq,
                                    pv=island.pv)

                # run the PTDF time series
                for k, t_idx in enumerate(time_indices):
                    dP = Pbus_0[island.original_bus_idx] - island.Sbus[:, t_idx].real
                    dP1 = island.Sbus[:, t_idx].real

                    # results.voltage[k, island.original_bus_idx] = V_0[island.original_bus_idx] + np.dot(dP, vtdf)

                    results.Sbranch[k, island.original_branch_idx] = Pbr_0[island.original_branch_idx] - (PTDF * dP) #* island.Sbase

                    results.loading[k, island.original_branch_idx] = results.Sbranch[k, island.original_branch_idx] / (nc.branch_rates[t_idx, island.original_branch_idx] + 1e-9)

                    results.S[k, island.original_bus_idx] = island.Sbus[:, t_idx].real

                    progress = ((t_idx - self.start_ + 1) / (self.end_ - self.start_)) * 100
                    self.progress_signal.emit(progress)
                    self.progress_text.emit('Simulating PTDF at ' + str(self.grid.time_profile[t_idx]))

        else:
            print('There are no profiles')
            self.progress_text.emit('There are no profiles')

        return results

    def run_jacobian_mode(self, time_indices) -> PtdfTimeSeriesResults:
        """
        Run the PTDF with the illinois formulation
        :return: TimeSeriesResults instance
        """

        # initialize the grid time series results, we will append the island results with another function
        nc = compile_opf_time_circuit(circuit=self.grid,
                                      apply_temperature=self.pf_options.apply_temperature_correction,
                                      branch_tolerance_mode=self.pf_options.branch_impedance_tolerance_mode)

        results = PtdfTimeSeriesResults(n=nc.nbus,
                                        m=nc.nbr,
                                        time_array=self.grid.time_profile[time_indices],
                                        bus_names=nc.bus_names,
                                        bus_types=nc.bus_types,
                                        branch_names=nc.branch_names)

        # if there are valid profiles...
        if self.grid.time_profile is not None:

            # run a power flow to get the initial branch power and compose the second branch power with the increment
            driver = PowerFlowDriver(grid=self.grid, options=self.pf_options)
            driver.run()

            # compile the islands
            islands = split_opf_time_circuit_into_islands(nc)

            # compose the power injections
            Sbus_0 = driver.results.Sbus
            Pbus_0 = Sbus_0.real
            V_0 = driver.results.voltage
            Pbr_0 = driver.results.Sbranch.real

            for island in islands:

                V = island.Vbus[0, :]
                Ibus = island.Ibus[:, 0]


                n = len(V)
                # set up indexing for updating V
                pvpq = np.r_[island.pv, island.pq]
                npv = len(island.pv)
                npq = len(island.pq)
                # j1:j2 - V angle of pv and pq buses
                j1 = 0
                j2 = npv + npq
                # j2:j3 - V mag of pq buses
                j3 = j2 + npq

                # compute the Jacobian
                J = Jacobian(island.Ybus, V, Ibus, island.pq, pvpq)
                Jfact = factorized(J)
                dVa = np.zeros(n)
                dVm = np.zeros(n)

                # run the PTDF time series
                for k, t_idx in enumerate(time_indices):
                    # dP = Pbus_0[island.original_bus_idx] - island.Sbus[:, t_idx].real

                    # compute the power increment (f)
                    dS = Sbus_0 - island.Sbus[:, t_idx]
                    # dS = island.Sbus[:, t_idx]
                    f = np.r_[dS[pvpq].real, dS[island.pq].imag]

                    # solve the voltage increment
                    dx = Jfact(f)

                    # reassign the solution vector
                    dVa[pvpq] = dx[j1:j2]
                    dVm[island.pq] = dx[j2:j3]
                    dV = dVm * np.exp(1j * dVa)
                    V = V_0 - dV

                    Vf = island.C_branch_bus_f * V
                    If = np.conj(island.Yf * V)
                    Sf = (Vf * If) * island.Sbase

                    results.voltage[k, island.original_bus_idx] = np.abs(V)

                    results.Sbranch[k, island.original_branch_idx] = Sf.real

                    results.loading[k, island.original_branch_idx] = Sf.real / (nc.branch_rates[t_idx, island.original_branch_idx] + 1e-9)

                    results.S[k, island.original_bus_idx] = island.Sbus[:, t_idx].real

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

        if self.end_ is None:
            self.end_ = len(self.grid.time_profile)
        time_indices = np.arange(self.start_, self.end_)

        self.results = self.run_nodal_mode(time_indices)
        # self.results = self.run_illinois_mode(time_indices)
        # self.results = self.run_jacobian_mode(time_indices)

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
    from GridCal.Engine import FileOpen, SolverType, TimeSeries

    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'
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
