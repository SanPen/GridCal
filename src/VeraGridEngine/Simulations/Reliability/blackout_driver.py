# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import pandas as pd
import numpy as np

from VeraGridEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Simulations.Stochastic.stochastic_power_flow_results import StochasticPowerFlowResults
from VeraGridEngine.Simulations.Stochastic.stochastic_power_flow_driver import StochasticPowerFlowDriver
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at, NumericalCircuit
from VeraGridEngine.enumerations import SimulationTypes, CascadeType
from VeraGridEngine.Simulations.driver_template import DriverTemplate


class CascadingReportElement:

    def __init__(self, removed_idx, pf_results, criteria):
        """
        CascadingReportElement constructor
        :param removed_idx: list of removed branch indices
        :param pf_results: power flow results object
        :param criteria: criteria used in the end
        """
        self.removed_idx = removed_idx
        self.pf_results = pf_results
        self.criteria = criteria


class CascadingResults:

    # TODO: refactor this class

    def __init__(self, cascade_type: CascadeType):
        """
        Cascading results constructor
        :param cascade_type: Cascade type
        """
        self.cascade_type = cascade_type

        self.events = list()

    def get_failed_idx(self):
        """
        Return the array of all failed Branches
        Returns:
            array of all failed Branches
        """
        res = None
        for i in range(len(self.events)):
            if i == 0:
                res = self.events[i][0]
            else:
                res = np.r_[res, self.events[i][0]]

        return res

    def get_table(self):
        """
        Get DataFrame of the failed elements
        :return: DataFrame
        """
        dta = list()
        for i in range(len(self.events)):
            dta.append(['Step ' + str(i + 1), len(self.events[i].removed_idx), self.events[i].criteria])

        return pd.DataFrame(data=dta, columns=['Cascade step', 'Elements failed', 'Criteria'])

    def plot(self):

        # TODO: implement cascading plot
        pass


class CascadingDriver(DriverTemplate):
    tpe = SimulationTypes.Cascade_run

    # TODO: re-make this simulation class

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, triggering_idx=None, max_additional_islands=1,
                 cascade_type_: CascadeType = CascadeType.LatinHypercube, n_lhs_samples_=1000):
        """
        Constructor
        Args:
            grid: MultiCircuit instance to cascade
            options: Power flow Options
            triggering_idx: branch indices to trigger first
            max_additional_islands: number of islands that shall be formed to consider a blackout
            cascade_type_: Cascade simulation kind
            n_lhs_samples_: number of latin hypercube samples if using LHS cascade
        """

        DriverTemplate.__init__(self, grid=grid)

        self.name = 'Cascading'

        self.options = options

        self.triggering_idx = triggering_idx

        self.__cancel__ = False

        self.current_step = 0

        self.max_additional_islands = max_additional_islands

        self.cascade_type = cascade_type_

        self.n_lhs_samples = n_lhs_samples_

        self.results = CascadingResults(self.cascade_type)

    @staticmethod
    def remove_elements(circuit: MultiCircuit, loading_vector, idx=None):
        """
        Remove Branches based on loading
        Returns:
            Nothing
        """
        criteria = 'None'
        if idx is None:
            load = abs(loading_vector)
            idx = np.where(load > 1.0)[0]

            if len(idx) == 0:
                criteria = 'Loading'
                idx = np.where(load >= load.max())[0]

        # disable the selected Branches
        # print('Removing:', idx, load[idx])
        branches = circuit.get_branches()
        for i in idx:
            branches[i].active = False

        return idx, criteria

    @staticmethod
    def remove_probability_based(numerical_circuit: NumericalCircuit,
                                 results: StochasticPowerFlowResults,
                                 max_val,
                                 min_prob):
        """
        Remove Branches based on their chance of overload
        :param numerical_circuit:
        :param results:
        :param max_val:
        :param min_prob:
        :return: list of indices actually removed
        """
        idx, val, prob, loading = results.get_index_loading_cdf(max_val=max_val)

        any_removed = False
        indices = list()
        criteria = 'None'

        for i, idx_val in enumerate(idx):
            if prob[i] >= min_prob:
                any_removed = True
                numerical_circuit.passive_branch_data.active[idx_val] = False
                indices.append(idx_val)
                criteria = 'Overload probability > ' + str(min_prob)

        if not any_removed:

            if len(loading) > 0:
                if len(idx) > 0:
                    # pick a random value
                    idx_val = np.random.randint(0, len(idx))
                    criteria = 'Random with overloads'

                else:
                    # pick the most loaded
                    idx_val = int(np.where(loading == max(loading))[0][0])
                    criteria = 'Max loading, Overloads not seen'

                numerical_circuit.passive_branch_data.active[idx_val] = False
                indices.append(idx_val)
            else:
                indices = []
                criteria = 'No Branches'

        return indices, criteria

    def perform_step_run(self):
        """
        Perform only one step cascading
        Returns:
            Nothing
        """

        # initialize the simulator
        if self.cascade_type is CascadeType.PowerFlow:
            model_simulator = PowerFlowDriver(self.grid, self.options)

        elif self.cascade_type is CascadeType.LatinHypercube:
            model_simulator = StochasticPowerFlowDriver(self.grid,
                                                        self.options,
                                                        sampling_points=self.n_lhs_samples)

        else:
            model_simulator = PowerFlowDriver(self.grid, self.options)

        # For every circuit, run a power flow
        # for c in self.grid.circuits:
        model_simulator.run()

        if self.current_step == 0:
            # the first iteration try to trigger the selected indices, if any
            idx, criteria = self.remove_elements(self.grid, idx=self.triggering_idx,
                                                 loading_vector=model_simulator.results.loading)
        else:
            # cascade normally
            idx, criteria = self.remove_elements(self.grid, loading_vector=model_simulator.results.loading)

        # store the removed indices and the results
        entry = CascadingReportElement(idx, model_simulator.results, criteria)
        self.results.events.append(entry)

        # increase the step number
        self.current_step += 1

        # print(model_simulator.results.get_convergence_report())

        # send the finnish signal
        self.report_done()

    def run(self):
        """
        Run the monte carlo simulation
        @return:
        """
        self.tic()
        self.__cancel__ = False

        # compile
        # print('Compiling...', end='')
        nc = compile_numerical_circuit_at(self.grid, t_idx=None, logger=self.logger)
        calculation_inputs = nc.split_into_islands(ignore_single_node_islands=self.options.ignore_single_node_islands)

        self.results = CascadingResults(self.cascade_type)

        # initialize the simulator
        if self.cascade_type is CascadeType.PowerFlow:
            model_simulator = PowerFlowDriver(self.grid, self.options)

        elif self.cascade_type is CascadeType.LatinHypercube:
            model_simulator = StochasticPowerFlowDriver(self.grid,
                                                        self.options,
                                                        sampling_points=self.n_lhs_samples)

        else:
            model_simulator = PowerFlowDriver(self.grid, self.options)

        self.report_progress(0.0)
        self.report_text('Running cascading failure...')

        n_grids = len(calculation_inputs) + self.max_additional_islands
        if n_grids > len(self.grid.buses):  # safety check
            n_grids = len(self.grid.buses) - 1

        # print('n grids: ', n_grids)

        it = 0
        while len(calculation_inputs) <= n_grids and it <= n_grids:

            # For every circuit, run the model (time series, lhs, or whatever)
            model_simulator.run()

            # delete grid elements (Branches)
            idx, criteria = self.remove_probability_based(nc, model_simulator.results,
                                                          max_val=1.0, min_prob=0.1)

            # store the removed indices and the results
            entry = CascadingReportElement(idx, model_simulator.results, criteria)
            self.results.events.append(entry)

            # recompile grid
            calculation_inputs = nc.split_into_islands(
                ignore_single_node_islands=self.options.ignore_single_node_islands)

            it += 1

            prog = max(len(calculation_inputs) / (n_grids + 1), it / (n_grids + 1))
            self.report_progress(prog * 100.0)

            if self.__cancel__:
                break

        self.logger.add_info("Info",
                             device="Number of grids split",
                             value=len(calculation_inputs))
        self.logger.add_info("Info",
                             device="Steps",
                             value=it)
        self.toc()

    def get_failed_idx(self):
        """
        Return the array of all failed Branches
        Returns:
            array of all failed Branches
        """
        return self.results.get_failed_idx()

    def get_table(self):
        """
        Get DataFrame of the failed elements
        :return: DataFrame
        """
        return self.results.get_table()

    def cancel(self):
        """
        Cancel the simulation
        :return:
        """
        self.__cancel__ = True
        self.report_done(txt="Cancelled", val=0.0)
