# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
import time
from typing import Union

from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.Simulations.NTC.ntc_opf import run_linear_ntc_opf_ts
from GridCalEngine.Simulations.NTC.ntc_driver import OptimalNetTransferCapacityOptions
from GridCalEngine.Simulations.NTC.ntc_ts_results import OptimalNetTransferCapacityTimeSeriesResults
from GridCalEngine.Simulations.driver_template import TimeSeriesDriverTemplate
from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearAnalysis
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

        if self.progress_text is not None:
            self.report_text('Compiling circuit...')
        else:
            print('Compiling cicuit...')

        tm0 = time.time()
        nc = compile_numerical_circuit_at(self.grid, t_idx=None, logger=self.logger)
        self.logger.add_info(f'Time circuit compiled in {time.time() - tm0:.2f} scs')
        print(f'Time circuit compiled in {time.time() - tm0:.2f} scs')

        # declare the linear analysis
        if self.progress_text is not None:
            self.report_text('Computing linear analysis...')
        else:
            print('Computing linear analysis...')

        linear = LinearAnalysis(numerical_circuit=nc,
                                distributed_slack=self.options.lin_options.distribute_slack,
                                correct_values=self.options.lin_options.correct_values)

        tm0 = time.time()
        linear.run()

        self.logger.add_info(f'Linear analysis computed in {time.time() - tm0:.2f} scs.')
        print(f'Linear analysis computed in {time.time() - tm0:.2f} scs.')

        # Initialize results object
        self.results = OptimalNetTransferCapacityTimeSeriesResults(
            branch_names=self.grid.get_branch_names_wo_hvdc(),
            bus_names=self.grid.get_bus_names(),
            hvdc_names=linear.numerical_circuit.hvdc_names,
            time_array=self.grid.time_profile[self.time_indices],
            time_indices=self.time_indices,
            trm=self.options.transmission_reliability_margin,
            loading_threshold_to_report=self.options.loading_threshold_to_report,
            ntc_load_rule=self.options.branch_rating_contribution
        )

        for t_idx, t in enumerate(self.time_indices):

            opf_vars = run_linear_ntc_opf_ts(grid=self.grid,
                                             time_indices=[t],  # only one time index at a time
                                             solver_type=self.options.opf_options.mip_solver,
                                             zonal_grouping=self.options.opf_options.zonal_grouping,
                                             skip_generation_limits=self.options.skip_generation_limits,
                                             consider_contingencies=self.options.consider_contingencies,
                                             lodf_threshold=self.options.lin_options.lodf_threshold,
                                             buses_areas_1=self.options.area_from_bus_idx,
                                             buses_areas_2=self.options.area_to_bus_idx,
                                             logger=self.logger,
                                             progress_text=None,
                                             progress_func=None,
                                             export_model_fname=self.options.opf_options.export_model_fname)

            self.results.voltage[t_idx, :] = np.ones(opf_vars.nbus) * np.exp(1j * opf_vars.bus_vars.theta)
            self.results.bus_shadow_prices[t_idx, :] = opf_vars.bus_vars.shadow_prices
            self.results.Sbus[t_idx, :] = opf_vars.bus_vars.Pcalc

            self.results.Sf[t_idx, :] = opf_vars.branch_vars.flows
            self.results.St[t_idx, :] = -opf_vars.branch_vars.flows
            self.results.overloads[t_idx, :] = opf_vars.branch_vars.get_total_flow_slack()
            self.results.loading[t_idx, :] = opf_vars.branch_vars.loading
            self.results.phase_shift[t_idx, :] = opf_vars.branch_vars.tap_angles

            self.results.hvdc_Pf[t_idx, :] = opf_vars.hvdc_vars.flows
            self.results.hvdc_loading[t_idx, :] = opf_vars.hvdc_vars.loading

            self.results.monitor[t_idx, :] = opf_vars.branch_vars.monitor
            self.results.monitor_type[t_idx, :] = opf_vars.branch_vars.monitor_type

            # TODO: Create analize function to create the massive report

            # update progress bar
            self.report_progress2(t_idx, len(self.time_indices))

            if self.progress_text is not None:
                self.report_text('Optimal net transfer capacity at ' + str(self.grid.time_profile[t]))

            else:
                print('Optimal net transfer capacity at ' + str(self.grid.time_profile[t]))

            if self.__cancel__:
                break

        self.report_text('Creating final reports...')

        self.results.create_all_reports(loading_threshold=self.options.loading_threshold_to_report, reverse=False)

        self.report_text('Done!')

        self.logger.add_info('Ejecutado en {0:.2f} scs. para {1} casos'.format(
            time.time() - tm0, len(self.results.time_array)))

    def run(self):
        """

        :return:
        """
        self.tic()

        self.opf()
        self.report_text('Done!')

        self.toc()
