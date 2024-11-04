# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from typing import Union

from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.NTC.ntc_opf import run_linear_ntc_opf_ts
from GridCalEngine.Simulations.NTC.ntc_driver import OptimalNetTransferCapacityOptions
from GridCalEngine.Simulations.NTC.ntc_ts_results import OptimalNetTransferCapacityTimeSeriesResults
from GridCalEngine.Simulations.driver_template import TimeSeriesDriverTemplate
from GridCalEngine.Simulations.Clustering.clustering_results import ClusteringResults
from GridCalEngine.basic_structures import Logger
from GridCalEngine.enumerations import SimulationTypes


class OptimalNetTransferCapacityTimeSeriesDriver(TimeSeriesDriverTemplate):
    tpe = SimulationTypes.OptimalNetTransferCapacityTimeSeries_run

    def __init__(self, grid: MultiCircuit,
                 options: OptimalNetTransferCapacityOptions,
                 time_indices: np.ndarray,
                 clustering_results: Union[ClusteringResults, None] = None):
        """

        :param grid: MultiCircuit Object
        :param options: Optimal net transfer capacity options
        :param time_indices: time index to start (optional)
        :param clustering_results: ClusteringResults (optional)
        """
        TimeSeriesDriverTemplate.__init__(
            self,
            grid=grid,
            time_indices=time_indices,
            clustering_results=clustering_results)

        # Options to use
        self.options: OptimalNetTransferCapacityOptions = options
        self.unresolved_counter = 0

        self.logger = Logger()

        self.results: Union[None, OptimalNetTransferCapacityTimeSeriesResults] = None

        self.installed_alpha = None
        self.installed_alpha_n1 = None

    def opf(self):
        """
        Run thread
        """

        self.report_progress(0)

        # Initialize results object
        self.results = OptimalNetTransferCapacityTimeSeriesResults(
            branch_names=self.grid.get_branch_names_wo_hvdc(),
            bus_names=self.grid.get_bus_names(),
            hvdc_names=self.grid.get_hvdc_names(),
            contingency_group_names=self.grid.get_contingency_group_names(),
            time_array=self.grid.time_profile[self.time_indices],
            time_indices=self.time_indices,
            clustering_results=self.clustering_results,
        )

        for t_idx, t in enumerate(self.time_indices):

            opf_vars = run_linear_ntc_opf_ts(
                grid=self.grid,
                time_indices=[t],  # only one time index at a time
                solver_type=self.options.opf_options.mip_solver,
                zonal_grouping=self.options.opf_options.zonal_grouping,
                skip_generation_limits=self.options.skip_generation_limits,
                consider_contingencies=self.options.consider_contingencies,
                contingency_groups_used=self.options.opf_options.contingency_groups_used,
                lodf_threshold=self.options.lin_options.lodf_threshold,
                bus_a1_idx=self.options.sending_bus_idx,
                bus_a2_idx=self.options.receiving_bus_idx,
                logger=self.logger,
                progress_text=None,
                progress_func=None,
                export_model_fname=self.options.opf_options.export_model_fname,
                verbose=self.options.opf_options.verbose,
                robust=self.options.opf_options.robust
            )

            if t_idx == 0:
                # one time results
                self.results.rates = opf_vars.branch_vars.rates[0, :]
                self.results.contingency_rates = opf_vars.branch_vars.contingency_rates[0, :]
                self.results.sending_bus_idx = self.options.sending_bus_idx
                self.results.receiving_bus_idx = self.options.receiving_bus_idx
                self.results.inter_space_branches = opf_vars.branch_vars.inter_space_branches
                self.results.inter_space_hvdc = opf_vars.hvdc_vars.inter_space_hvdc

            self.results.voltage[t_idx, :] = opf_vars.get_voltages()[0, :]
            self.results.Sbus[t_idx, :] = opf_vars.bus_vars.Pcalc[0, :]
            self.results.dSbus[t_idx, :] = opf_vars.bus_vars.delta_p[0, :]
            self.results.bus_shadow_prices[t_idx, :] = opf_vars.bus_vars.shadow_prices[0, :]
            self.results.load_shedding[t_idx, :] = opf_vars.bus_vars.load_shedding[0, :]

            self.results.Sf[t_idx, :] = opf_vars.branch_vars.flows[0, :]
            self.results.St[t_idx, :] = -opf_vars.branch_vars.flows[0, :]
            self.results.overloads[t_idx, :] = (opf_vars.branch_vars.flow_slacks_pos[0, :]
                                                - opf_vars.branch_vars.flow_slacks_neg[0, :])
            self.results.loading[t_idx, :] = opf_vars.branch_vars.loading[0, :]
            self.results.phase_shift[t_idx, :] = opf_vars.branch_vars.tap_angles[0, :]

            self.results.alpha[t_idx, :] = opf_vars.branch_vars.alpha[0, :]
            self.results.monitor_logic[t_idx, :] = opf_vars.branch_vars.monitor_logic[0, :]

            self.results.contingency_flows_list += opf_vars.branch_vars.contingency_flow_data

            self.results.hvdc_Pf[t_idx, :] = opf_vars.hvdc_vars.flows[0, :]
            self.results.hvdc_loading[t_idx, :] = opf_vars.hvdc_vars.loading[0, :]

            self.results.converged[t_idx] = opf_vars.acceptable_solution

            # update progress bar
            self.report_progress2(t_idx, len(self.time_indices))

            if self.progress_text is not None:
                self.report_text('Optimal net transfer capacity at ' + str(self.grid.time_profile[t]))

            else:
                print('Optimal net transfer capacity at ' + str(self.grid.time_profile[t]))

            if self.__cancel__:
                break

        self.report_text('Done!')

    def run(self):
        """

        :return:
        """
        self.tic()

        self.opf()
        self.report_text('Done!')

        self.toc()
