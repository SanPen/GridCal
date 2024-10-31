# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from enum import Enum

from GridCalEngine.basic_structures import Logger
from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCalEngine.Simulations.Stochastic.stochastic_power_flow_results import StochasticPowerFlowResults
from GridCalEngine.Simulations.Stochastic.stochastic_power_flow_input import StochasticPowerFlowInput
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at, BranchImpedanceMode
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions, multi_island_pf_nc
from GridCalEngine.enumerations import SimulationTypes
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

        self.results = StochasticPowerFlowResults(n=self.grid.get_bus_number(),
                                                  m=self.grid.get_branch_number_wo_hvdc(),
                                                  p=self.max_sampling_points,
                                                  bus_names=self.grid.get_bus_names(),
                                                  branch_names=self.grid.get_branch_names_wo_hvdc(),
                                                  bus_types=np.ones(self.grid.get_bus_number()))

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
        self.report_progress2(t, self.max_sampling_points)
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

        self.report_progress(0.0)
        self.report_text('Running Monte Carlo Sampling...')

        # compile the multi-circuit, we'll hack it later
        numerical_circuit = compile_numerical_circuit_at(circuit=self.grid,
                                                         t_idx=None,
                                                         apply_temperature=False,
                                                         branch_tolerance_mode=BranchImpedanceMode.Specified,
                                                         opf_results=self.opf_time_series_results,
                                                         logger=self.logger)

        mc_results = StochasticPowerFlowResults(n=numerical_circuit.nbus,
                                                m=numerical_circuit.nbr,
                                                p=self.max_sampling_points,
                                                bus_names=numerical_circuit.bus_names,
                                                branch_names=numerical_circuit.branch_names,
                                                bus_types=numerical_circuit.bus_types)

        avg_res = PowerFlowResults(n=numerical_circuit.nbus,
                                   m=numerical_circuit.nbr,
                                   n_hvdc=numerical_circuit.nhvdc,
                                   n_gen=numerical_circuit.ngen,
                                   n_batt=numerical_circuit.nbatt,
                                   n_sh=numerical_circuit.nshunt,
                                   bus_names=numerical_circuit.bus_names,
                                   branch_names=numerical_circuit.branch_names,
                                   hvdc_names=numerical_circuit.hvdc_names,
                                   gen_names=numerical_circuit.generator_names,
                                   batt_names=numerical_circuit.battery_names,
                                   sh_names=numerical_circuit.shunt_names,
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
                self.report_progress(max((std_dev_progress, i / self.max_sampling_points * 100)))

            if self.__cancel__:
                break

        mc_results.compile()

        # send the finnish signal
        self.report_done()

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
        self.report_done("Cancelled!")
