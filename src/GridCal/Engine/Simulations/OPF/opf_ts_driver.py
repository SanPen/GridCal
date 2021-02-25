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
import time
from PySide2.QtCore import QThread, Signal

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.basic_structures import TimeGrouping, get_time_groups
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.basic_structures import SolverType
from GridCal.Engine.Simulations.OPF.opf_driver import OptimalPowerFlowOptions
from GridCal.Engine.Simulations.OPF.dc_opf_ts import OpfDcTimeSeries
from GridCal.Engine.Simulations.OPF.ac_opf_ts import OpfAcTimeSeries
from GridCal.Engine.Simulations.OPF.simple_dispatch_ts import OpfSimpleTimeSeries
from GridCal.Engine.Core.time_series_opf_data import compile_opf_time_circuit
from GridCal.Engine.Simulations.OPF.opf_ts_results import OptimalPowerFlowTimeSeriesResults


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

        # Options to use
        self.options = options

        # power flow options
        self.pf_options = options.power_flow_options

        # compile the circuit into a numerical equivalent for this simulation
        self.numerical_circuit = compile_opf_time_circuit(circuit=self.grid,
                                                          apply_temperature=self.pf_options.apply_temperature_correction,
                                                          branch_tolerance_mode=self.pf_options.branch_impedance_tolerance_mode)

        # OPF results
        self.results = OptimalPowerFlowTimeSeriesResults(bus_names=self.numerical_circuit.bus_names,
                                                         branch_names=self.numerical_circuit.branch_names,
                                                         load_names=self.numerical_circuit.load_names,
                                                         generator_names=self.numerical_circuit.generator_names,
                                                         battery_names=self.numerical_circuit.battery_names,
                                                         n=self.grid.get_bus_number(),
                                                         m=self.grid.get_branch_number(),
                                                         nt=len(self.grid.time_profile),
                                                         ngen=len(self.grid.get_generators()),
                                                         nbat=len(self.grid.get_batteries()),
                                                         nload=len(self.grid.get_loads()),
                                                         time=self.grid.time_profile,
                                                         bus_types=self.numerical_circuit.bus_types)

        self.start_ = start_

        if end_ is not None:
            self.end_ = end_
        else:
            self.end_ = len(self.grid.time_profile)

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
        self.results = OptimalPowerFlowTimeSeriesResults(bus_names=self.numerical_circuit.bus_names,
                                                         branch_names=self.numerical_circuit.branch_names,
                                                         load_names=self.numerical_circuit.load_names,
                                                         generator_names=self.numerical_circuit.generator_names,
                                                         battery_names=self.numerical_circuit.battery_names,
                                                         n=self.grid.get_bus_number(),
                                                         m=self.grid.get_branch_number(),
                                                         nt=len(self.grid.time_profile),
                                                         ngen=len(self.grid.get_generators()),
                                                         nbat=len(self.grid.get_batteries()),
                                                         nload=len(self.grid.get_loads()),
                                                         time=self.grid.time_profile,
                                                         bus_types=self.numerical_circuit.bus_types)

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
            self.progress_text.emit('Formulating problem...')

        if self.options.solver == SolverType.DC_OPF:

            # DC optimal power flow
            problem = OpfDcTimeSeries(numerical_circuit=self.numerical_circuit,
                                      start_idx=start_,
                                      end_idx=end_,
                                      solver=self.options.mip_solver,
                                      batteries_energy_0=batteries_energy_0)

        elif self.options.solver == SolverType.AC_OPF:

            # AC optimal power flow
            problem = OpfAcTimeSeries(numerical_circuit=self.numerical_circuit,
                                      start_idx=start_,
                                      end_idx=end_,
                                      solver=self.options.mip_solver,
                                      batteries_energy_0=batteries_energy_0)

        elif self.options.solver == SolverType.Simple_OPF:

            # AC optimal power flow
            problem = OpfSimpleTimeSeries(numerical_circuit=self.numerical_circuit,
                                          start_idx=start_, end_idx=end_,
                                          solver=self.options.mip_solver,
                                          batteries_energy_0=batteries_energy_0,
                                          text_prog=self.progress_text.emit,
                                          prog_func=self.progress_signal.emit)

        else:
            self.logger.add_error('Solver not supported in this mode', str(self.options.solver))
            return

        if not remote:
            self.progress_signal.emit(0.0)
            self.progress_text.emit('Running all in an external solver, this may take a while...')

        # solve the problem
        status = problem.solve()
        print("Status:", status)

        a = start_
        b = end_
        self.results.voltage[a:b, :] = problem.get_voltage()
        self.results.load_shedding[a:b, :] = problem.get_load_shedding()
        self.results.battery_power[a:b, :] = problem.get_battery_power()
        self.results.battery_energy[a:b, :] = problem.get_battery_energy()
        self.results.generator_power[a:b, :] = problem.get_generator_power()
        self.results.Sf[a:b, :] = problem.get_branch_power()
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
                self.opf(start_=start_, end_=end_ + 1, remote=True, batteries_energy_0=energy_0)

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
