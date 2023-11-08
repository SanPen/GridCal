# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
import numpy as np
from enum import Enum

from GridCalEngine.basic_structures import Logger
from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCalEngine.Simulations.Stochastic.stochastic_power_flow_results import StochasticPowerFlowResults
from GridCalEngine.Simulations.Stochastic.stochastic_power_flow_input import StochasticPowerFlowInput
from GridCalEngine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at, BranchImpedanceMode
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions, multi_island_pf_nc

from GridCalEngine.Simulations.driver_types import SimulationTypes
from GridCalEngine.Simulations.driver_template import DriverTemplate


########################################################################################################################
# Monte Carlo classes
########################################################################################################################


class StochasticPowerFlowType(Enum):
    MonteCarlo = 'Monte Carlo'
    LatinHypercube = 'Latin Hypercube'


class StochasticPowerFlowDriver(DriverTemplate):
    name = 'Stochastic Power Flow'
    tpe = SimulationTypes.StochasticPowerFlow

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, mc_tol=1e-3, batch_size=100,
                 sampling_points=10000,
                 opf_time_series_results=None,
                 simulation_type: StochasticPowerFlowType = StochasticPowerFlowType.LatinHypercube):
        """
        Monte Carlo simulation constructor
        :param grid: MultiGrid instance
        :param options: Power flow options
        :param mc_tol: monte carlo std.dev tolerance
        :param batch_size: size of the batch
        :param sampling_points: maximum monte carlo iterations in case of not reach the precission
        :param simulation_type: Type of sampling method
        """
        DriverTemplate.__init__(self, grid=grid)

        self.options = options

        self.opf_time_series_results = opf_time_series_results

        self.mc_tol = mc_tol

        self.batch_size = batch_size

        self.max_sampling_points = sampling_points

        self.simulation_type = simulation_type

        self.results = None

        self.logger = Logger()

        self.pool = None

        self.returned_results = list()

        self.__cancel__ = False

    def get_steps(self):
        """
        Get time steps list of strings
        """
        p = self.results.points_number
        return ['point:' + str(l) for l in range(p)]

    def update_progress_mt(self, res):
        """
        """
        t, _ = res
        progress = (t + 1) / self.max_sampling_points * 100
        self.progress_signal.emit(progress)
        self.returned_results.append(res)

    def run_single_thread_mc(self, use_lhs=False):
        """

        :param use_lhs:
        :return:
        """
        self.__cancel__ = False

        # initialize the grid time series results
        # we will append the island results with another function

        # batch_size = self.sampling_points

        self.progress_signal.emit(0.0)
        self.progress_text.emit('Running Monte Carlo Sampling...')

        # compile the multi-circuit, we'll hack it later
        numerical_circuit = compile_numerical_circuit_at(circuit=self.grid,
                                                         t_idx=None,
                                                         apply_temperature=False,
                                                         branch_tolerance_mode=BranchImpedanceMode.Specified,
                                                         opf_results=self.opf_time_series_results)

        mc_results = StochasticPowerFlowResults(n=numerical_circuit.nbus,
                                                m=numerical_circuit.nbr,
                                                p=self.max_sampling_points,
                                                bus_names=numerical_circuit.bus_names,
                                                branch_names=numerical_circuit.branch_names,
                                                bus_types=numerical_circuit.bus_types,
                                                name='Monte Carlo')

        avg_res = PowerFlowResults(n=numerical_circuit.nbus,
                                   m=numerical_circuit.nbr,
                                   n_hvdc=numerical_circuit.nhvdc,
                                   bus_names=numerical_circuit.bus_names,
                                   branch_names=numerical_circuit.branch_names,
                                   hvdc_names=numerical_circuit.hvdc_names,
                                   bus_types=numerical_circuit.bus_types)

        variance_sum = 0.0
        v_sum = np.zeros(numerical_circuit.nbus, dtype=complex)

        # build inputs
        monte_carlo_input = StochasticPowerFlowInput(self.grid)

        # get the power injections in p.u.
        S_combinations = monte_carlo_input.get(self.max_sampling_points, use_latin_hypercube=use_lhs) / self.grid.Sbase

        # run the time series
        for i in range(self.max_sampling_points):

            # Run the set monte carlo point at 't'
            res = multi_island_pf_nc(nc=numerical_circuit,
                                     options=self.options,
                                     Sbus_input=S_combinations[i, :])

            # Gather the results
            mc_results.S_points[i, :] = S_combinations[i, :]
            mc_results.V_points[i, :] = res.voltage
            mc_results.Sbr_points[i, :] = res.Sf
            mc_results.loading_points[i, :] = res.loading
            mc_results.losses_points[i, :] = res.losses

            # determine when to stop
            if i > 1:
                v_sum += mc_results.get_voltage_sum()
                v_avg = v_sum / i
                v_variance = np.abs((np.power(mc_results.V_points - v_avg, 2.0) / (i - 1)).min())

                # progress
                variance_sum += v_variance
                err = variance_sum / i
                if err == 0:
                    err = 1e-200  # to avoid division by zeros
                mc_results.error_series.append(err)

                # emmit the progress signal
                std_dev_progress = 100 * self.mc_tol / err
                if std_dev_progress > 100:
                    std_dev_progress = 100
                self.progress_signal.emit(max((std_dev_progress, i / self.max_sampling_points * 100)))

            if self.__cancel__:
                break

        mc_results.compile()

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

        return mc_results

    def run(self):
        """
        Run the monte carlo simulation
        @return:
        """
        self.tic()
        self.__cancel__ = False

        if self.simulation_type == StochasticPowerFlowType.MonteCarlo:
            self.results = self.run_single_thread_mc(use_lhs=False)
        elif self.simulation_type == StochasticPowerFlowType.LatinHypercube:
            self.results = self.run_single_thread_mc(use_lhs=True)

        self.toc()

    def cancel(self):
        """
        Cancel the simulation
        :return:
        """
        self.__cancel__ = True
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled')
        self.done_signal.emit()
