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

import pandas as pd
import numpy as np
import time
from PySide2.QtCore import QThread, Signal

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.basic_structures import TimeGrouping, get_time_groups
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import SolverType
from GridCal.Engine.Simulations.OPF.opf_driver import OptimalPowerFlowResults, OptimalPowerFlowOptions
from GridCal.Engine.Simulations.OPF.dc_opf_ts import OpfDcTimeSeries
from GridCal.Engine.Simulations.OPF.ac_opf_ts import OpfAcTimeSeries
from GridCal.Gui.GuiFunctions import ResultsModel
from GridCal.Engine.Simulations.result_types import ResultTypes


class OptimalPowerFlowTimeSeriesResults:

    def __init__(self, n, m, nt, ngen=0, nbat=0, nload=0, time=None):
        """
        OPF Time Series results constructor
        :param n: number of buses
        :param m: number of branches
        :param nt: number of time steps
        :param ngen:
        :param nbat:
        :param nload:
        :param time: Time array (optional)
        """
        self.name = 'OPF time series'

        self.n = n

        self.m = m

        self.nt = nt

        self.time = time

        self.voltage = np.zeros((nt, n), dtype=complex)

        self.load_shedding = np.zeros((nt, nload), dtype=float)

        self.loading = np.zeros((nt, m), dtype=float)

        self.losses = np.zeros((nt, m), dtype=float)

        self.overloads = np.zeros((nt, m), dtype=float)

        self.Sbus = np.zeros((nt, n), dtype=complex)

        self.shadow_prices = np.zeros((nt, n), dtype=float)

        self.Sbranch = np.zeros((nt, m), dtype=complex)

        self.bus_types = np.zeros(n, dtype=int)

        self.available_results = [ResultTypes.BusVoltageModule,
                                  ResultTypes.BusVoltageAngle,
                                  ResultTypes.ShadowPrices,
                                  ResultTypes.BranchPower,
                                  ResultTypes.BranchLoading,
                                  ResultTypes.BranchOverloads,
                                  ResultTypes.LoadShedding,
                                  ResultTypes.ControlledGeneratorShedding,
                                  ResultTypes.ControlledGeneratorPower,
                                  ResultTypes.BatteryPower,
                                  ResultTypes.BatteryEnergy]

        self.controlled_generator_power = np.zeros((nt, ngen), dtype=float)

        self.controlled_generator_shedding = np.zeros((nt, ngen), dtype=float)

        self.battery_power = np.zeros((nt, nbat), dtype=float)

        self.battery_energy = np.zeros((nt, nbat), dtype=float)

        self.converged = np.empty(nt, dtype=bool)

    def init_object_results(self, ngen, nbat):
        """
        declare the generator results. This is done separately since these results are known at the end of the simulation
        :param ngen: number of generators
        :param nbat: number of batteries
        """
        self.controlled_generator_power = np.zeros((self.nt, ngen), dtype=float)

        self.battery_power = np.zeros((self.nt, nbat), dtype=float)

    def set_at(self, t, res: OptimalPowerFlowResults):
        """
        Set the results
        :param t: time index
        :param res: OptimalPowerFlowResults instance
        """

        self.voltage[t, :] = res.voltage

        self.load_shedding[t, :] = res.load_shedding

        self.loading[t, :] = np.abs(res.loading)

        self.overloads[t, :] = np.abs(res.overloads)

        self.losses[t, :] =np.abs(res.losses)

        self.Sbus[t, :] = res.Sbus

        self.Sbranch[t, :] = res.Sbranch

    def mdl(self, result_type, indices=None, names=None) -> "ResultsModel":
        """
        Plot the results
        :param result_type:
        :param ax:
        :param indices:
        :param names:
        :return:
        """

        if indices is None:
            indices = np.array(range(len(names)))

        if len(indices) > 0:
            labels = names[indices]
            y_label = ''
            title = ''
            if result_type == ResultTypes.BusVoltageModule:
                y = np.abs(self.voltage[:, indices])
                y_label = '(p.u.)'
                title = 'Bus voltage module'

            elif result_type == ResultTypes.BusVoltageAngle:
                y = np.angle(self.voltage[:, indices])
                y_label = '(Radians)'
                title = 'Bus voltage angle'

            elif result_type == ResultTypes.ShadowPrices:
                y = self.shadow_prices[:, indices]
                y_label = '(currency)'
                title = 'Bus shadow prices'

            elif result_type == ResultTypes.BranchPower:
                y = self.Sbranch[:, indices].real
                y_label = '(MW)'
                title = 'Branch power '

            elif result_type == ResultTypes.BusPower:
                y = self.Sbus[:, indices].real
                y_label = '(MW)'
                title = 'Bus power '

            elif result_type == ResultTypes.BranchLoading:
                y = np.abs(self.loading[:, indices] * 100.0)
                y_label = '(%)'
                title = 'Branch loading '

            elif result_type == ResultTypes.BranchOverloads:
                y = np.abs(self.overloads[:, indices])
                y_label = '(MW)'
                title = 'Branch overloads '

            elif result_type == ResultTypes.BranchLosses:
                y = self.losses[:, indices].real
                y_label = '(MW)'
                title = 'Branch losses '

            elif result_type == ResultTypes.LoadShedding:
                y = self.load_shedding[:, indices]
                y_label = '(MW)'
                title = 'Load shedding'

            elif result_type == ResultTypes.ControlledGeneratorPower:
                y = self.controlled_generator_power[:, indices]
                y_label = '(MW)'
                title = 'Controlled generator power'

            elif result_type == ResultTypes.ControlledGeneratorShedding:
                y = self.controlled_generator_shedding[:, indices]
                y_label = '(MW)'
                title = 'Controlled generator power'

            elif result_type == ResultTypes.BatteryPower:
                y = self.battery_power[:, indices]
                y_label = '(MW)'
                title = 'Battery power'

            elif result_type == ResultTypes.BatteryEnergy:
                y = self.battery_energy[:, indices]
                y_label = '(MWh)'
                title = 'Battery energy'

            else:
                print(str(result_type) + ' not understood.')

            # if self.time is not None:
            #     df = pd.DataFrame(data=y, columns=labels, index=self.time)
            # else:
            #     df = pd.DataFrame(data=y, columns=labels)
            #
            # df.fillna(0, inplace=True)
            #
            # if len(df.columns) > 10:
            #     df.plot(ax=ax, linewidth=LINEWIDTH, legend=False)
            # else:
            #     df.plot(ax=ax, linewidth=LINEWIDTH, legend=True)
            #
            # ax.set_title(title)
            # ax.set_ylabel(y_label)
            # ax.set_xlabel('Time')
            #
            # return df

            if self.time is not None:
                index = self.time
            else:
                index = np.arange(0, y.shape[0], 1)

            mdl = ResultsModel(data=y, index=index, columns=labels, title=title,
                               ylabel=y_label, xlabel='')
            return mdl

        else:
            return None


class OptimalPowerFlowTimeSeries(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()
    name = 'Optimal power flow time series'

    def __init__(self, grid: MultiCircuit, options: OptimalPowerFlowOptions, start_=0, end_=None):
        """
        PowerFlowDriver class constructor
        @param grid: MultiCircuit Object
        @param options: OPF options
        """
        QThread.__init__(self)

        # Grid to run a power flow in
        self.grid = grid

        self.numerical_circuit = self.grid.compile()

        # Options to use
        self.options = options

        # OPF results
        self.results = OptimalPowerFlowTimeSeriesResults(n=len(self.grid.buses),
                                                         m=len(self.grid.branches),
                                                         nt=len(self.grid.time_profile),
                                                         ngen=len(self.grid.get_generators()),
                                                         nbat=len(self.grid.get_batteries()),
                                                         nload=len(self.grid.get_loads()),
                                                         time=self.grid.time_profile)

        self.start_ = start_

        self.end_ = end_

        self.logger = Logger()

        # set cancel state
        self.__cancel__ = False

        self.all_solved = True

        self.elapsed = 0.0

    def reset_results(self):
        """
        Clears the results
        """
        # reinitialize
        self.results = OptimalPowerFlowTimeSeriesResults(n=len(self.grid.buses),
                                                         m=len(self.grid.branches),
                                                         nt=len(self.grid.time_profile),
                                                         ngen=len(self.grid.get_generators()),
                                                         nbat=len(self.grid.get_batteries()),
                                                         nload=len(self.grid.get_loads()),
                                                         time=self.grid.time_profile)

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return [l.strftime('%d-%m-%Y %H:%M') for l in pd.to_datetime(self.grid.time_profile)]

    def opf(self, start_, end_, remote=False, batteries_energy_0=None):
        """
        Run a power flow for every circuit
        :param start_: start index
        :param end_: end index
        :param remote: is this function being called from the time series?
        :param batteries_energy_0: initial state of the batteries, if None the default values are taken
        :return: OptimalPowerFlowResults object
        """

        if not remote:
            self.progress_signal.emit(0.0)
            self.progress_text.emit('Running all in an external solver, this may take a while...')

        if self.options.solver == SolverType.DC_OPF:

            # DC optimal power flow
            problem = OpfDcTimeSeries(numerical_circuit=self.numerical_circuit,
                                      start_idx=start_, end_idx=end_,
                                      solver=self.options.mip_solver, batteries_energy_0=batteries_energy_0)

        elif self.options.solver == SolverType.AC_OPF:

            # AC optimal power flow
            problem = OpfAcTimeSeries(numerical_circuit=self.numerical_circuit,
                                      start_idx=start_, end_idx=end_,
                                      solver=self.options.mip_solver, batteries_energy_0=batteries_energy_0)

        else:
            self.logger.append('Solver not supported in this mode: ' + str(self.options.solver))
            return

        # solve the problem
        status = problem.solve()
        # print("Status:", status)

        a = start_
        b = end_
        self.results.voltage[a:b, :] = problem.get_voltage()
        self.results.load_shedding[a:b, :] = problem.get_load_shedding()
        self.results.battery_power[a:b, :] = problem.get_battery_power()
        self.results.battery_energy[a:b, :] = problem.get_battery_energy()
        self.results.controlled_generator_power[a:b, :] = problem.get_generator_power()
        self.results.Sbranch[a:b, :] = problem.get_branch_power()
        self.results.overloads[a:b, :] = problem.get_overloads()
        self.results.loading[a:b, :] = problem.get_loading()
        self.results.shadow_prices[a:b, :] = problem.get_shadow_prices()

        return self.results

    def opf_by_groups(self):
        """
        Run the OPF by groups
        """

        self.progress_signal.emit(0.0)
        self.progress_text.emit('Making groups...')

        # get the partition points of the time series
        groups = get_time_groups(t_array=self.grid.time_profile, grouping=self.options.grouping)

        n = len(groups)
        i = 1
        energy_0 = None
        while i < n and not self.__cancel__:

            start_ = groups[i - 1]
            end_ = groups[i]

            print(start_, ':', end_, ' [', end_ - start_, ']')

            if start_ >= self.start_ and end_ <= self.end_:

                # run an opf for the group interval only if the group is within the start:end boundaries
                self.opf(start_=start_, end_=end_, remote=True, batteries_energy_0=energy_0)

            energy_0 = self.results.battery_energy[end_ - 1, :]

            self.progress_text.emit('Running OPF for the time group ' + str(i) + ' in external solver...')
            progress = ((start_ - self.start_ + 1) / (self.end_ - self.start_)) * 100
            self.progress_signal.emit(progress)

            i += 1

    def run(self):
        """

        :return:
        """

        start = time.time()

        if self.options.grouping == TimeGrouping.NoGrouping:
            self.opf(start_=self.start_, end_=self.end_)
        else:
            self.opf_by_groups()

        end = time.time()
        self.elapsed = end - start

        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled!')
        self.done_signal.emit()