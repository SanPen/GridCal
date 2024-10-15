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
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.NTC.ntc_opf import run_linear_ntc_opf_ts
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.Simulations.NTC.ntc_options import OptimalNetTransferCapacityOptions
from GridCalEngine.Simulations.NTC.ntc_results import OptimalNetTransferCapacityResults
from GridCalEngine.basic_structures import Logger
from GridCalEngine.enumerations import SimulationTypes


class OptimalNetTransferCapacityDriver(DriverTemplate):
    name = 'Optimal net transfer capacity'
    tpe = SimulationTypes.OPF_NTC_run

    def __init__(self,
                 grid: MultiCircuit,
                 options: OptimalNetTransferCapacityOptions):
        """
        PowerFlowDriver class constructor
        :param grid: MultiCircuit Object
        :param options: OptimalNetTransferCapacityOptions
        """
        DriverTemplate.__init__(self, grid=grid)

        # Options to use
        self.options: OptimalNetTransferCapacityOptions = options

        self.all_solved = True

        self.logger = Logger()

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return list()

    def opf(self) -> OptimalNetTransferCapacityResults:
        """
        Run a power flow for every circuit
        @return: OptimalPowerFlowResults object
        """

        self.report_text('Compiling...')

        self.report_text('Formulating NTC OPF...')

        opf_vars = run_linear_ntc_opf_ts(
            grid=self.grid,
            time_indices=None,
            solver_type=self.options.opf_options.mip_solver,
            zonal_grouping=self.options.opf_options.zonal_grouping,
            skip_generation_limits=self.options.skip_generation_limits,
            consider_contingencies=self.options.consider_contingencies,
            contingency_groups_used=self.options.opf_options.contingency_groups_used,
            lodf_threshold=self.options.lin_options.lodf_threshold,
            bus_idx_from=self.options.area_from_bus_idx,
            bus_idx_to=self.options.area_to_bus_idx,
            transfer_method=self.options.transfer_method,
            monitor_only_ntc_load_rule_branches=self.options.use_branch_rating_contribution,
            alpha_threshold=self.options.branch_exchange_sensitivity,
            monitor_only_sensitive_branches=self.options.use_branch_exchange_sensitivity,
            ntc_load_rule=self.options.branch_rating_contribution,
            logger=self.logger,
            progress_text=self.report_text,
            progress_func=self.report_progress,
            export_model_fname=self.options.opf_options.export_model_fname,
            verbose=self.options.opf_options.verbose,
            robust=self.options.opf_options.robust
        )

        # pack the results
        self.results = OptimalNetTransferCapacityResults(
            bus_names=self.grid.get_bus_names(),
            branch_names=self.grid.get_branch_names_wo_hvdc(),
            hvdc_names=self.grid.get_hvdc_names(),
        )

        self.results.voltage = opf_vars.get_voltages()[0, :]
        self.results.Sbus = opf_vars.bus_vars.Pcalc[0, :]
        self.results.bus_shadow_prices = opf_vars.bus_vars.shadow_prices[0, :]
        self.results.load_shedding = opf_vars.bus_vars.load_shedding[0, :]

        self.results.Sf = opf_vars.branch_vars.flows[0, :]
        self.results.St = -opf_vars.branch_vars.flows[0, :]
        self.results.overloads = opf_vars.branch_vars.flow_slacks_pos[0, :] - opf_vars.branch_vars.flow_slacks_neg[0, :]
        self.results.loading = opf_vars.branch_vars.loading[0, :]
        self.results.phase_shift = opf_vars.branch_vars.tap_angles[0, :]
        self.results.rates = opf_vars.branch_vars.rates[0, :]
        self.results.contingency_rates = opf_vars.branch_vars.contingency_rates[0, :]

        self.results.hvdc_Pf = opf_vars.hvdc_vars.flows[0, :]
        self.results.hvdc_loading = opf_vars.hvdc_vars.loading[0, :]

        self.results.inter_space_branches = self.grid.get_inter_areas_branches(a1=self.options.area_from_bus_idx,
                                                                               a2=self.options.area_to_bus_idx)

        self.results.inter_space_hvdc = self.grid.get_inter_areas_hvdc_branches(a1=self.options.area_from_bus_idx,
                                                                                a2=self.options.area_to_bus_idx)

        self.report_text('Done!')

        return self.results

    def run(self):
        """

        :return:
        """
        self.tic()

        self.opf()

        self.toc()
