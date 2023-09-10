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



from GridCalEngine.basic_structures import TimeGrouping, MIPSolvers
from GridCalEngine.Simulations.NTC.ntc_opf import GenerationNtcFormulation
from GridCalEngine.Simulations.ATC.available_transfer_capacity_driver import AvailableTransferMode


class OptimalNetTransferCapacityOptions:

    def __init__(self,
                 area_from_bus_idx,
                 area_to_bus_idx,
                 verbose=False,
                 grouping: TimeGrouping = TimeGrouping.NoGrouping,
                 mip_solver=MIPSolvers.CBC,
                 generation_formulation: GenerationNtcFormulation = GenerationNtcFormulation.Proportional,
                 monitor_only_sensitive_branches=True,
                 monitor_only_ntc_rule_branches=False,
                 branch_sensitivity_threshold=0.05,
                 skip_generation_limits=True,
                 perform_previous_checks=False,
                 dispatch_all_areas=False,
                 tolerance=1e-2,
                 sensitivity_dT=100.0,
                 weight_power_shift=1e0,
                 weight_generation_cost=1e-2,
                 time_limit_ms=1e4,
                 consider_contingencies=True,
                 consider_hvdc_contingencies=False,
                 consider_gen_contingencies=False,
                 consider_nx_contingencies=False,
                 generation_contingency_threshold=0,
                 match_gen_load=True,
                 trm=0,
                 ntc_load_rule=0,
                 n1_consideration=True,
                 loading_threshold_to_report=0.98,
                 transfer_method: AvailableTransferMode = AvailableTransferMode.InstalledPower,
                 reversed_sort_loading=True,
                 ):
        """

        :param area_from_bus_idx:
        :param area_to_bus_idx:
        :param verbose:
        :param grouping:
        :param mip_solver:
        :param generation_formulation:
        :param monitor_only_sensitive_branches:
        :param branch_sensitivity_threshold:
        :param skip_generation_limits:
        :param consider_contingencies:
        :param consider_nx_contingencies:
        :param tolerance:
        :param sensitivity_dT:
        :param weight_power_shift:
        :param weight_generation_cost:
        :param time_limit_ms:
        :param generation_contingency_threshold:
        :param trm:
        :param ntc_load_rule:
        :param n1_consideration:
        :param transfer_method:
        :param reverse_sorted_loading:
        """
        self.verbose = verbose

        self.grouping = grouping

        self.mip_solver = mip_solver

        self.area_from_bus_idx = area_from_bus_idx

        self.area_to_bus_idx = area_to_bus_idx

        self.generation_formulation = generation_formulation

        self.monitor_only_sensitive_branches = monitor_only_sensitive_branches
        self.monitor_only_ntc_load_rule_branches = monitor_only_ntc_rule_branches

        self.branch_sensitivity_threshold = branch_sensitivity_threshold

        self.skip_generation_limits = skip_generation_limits

        self.dispatch_all_areas = dispatch_all_areas

        self.tolerance = tolerance

        self.sensitivity_dT = sensitivity_dT

        self.transfer_method = transfer_method

        self.perform_previous_checks = perform_previous_checks

        self.weight_power_shift = weight_power_shift
        self.weight_generation_cost = weight_generation_cost

        self.consider_contingencies = consider_contingencies
        self.consider_hvdc_contingencies = consider_hvdc_contingencies
        self.consider_gen_contingencies = consider_gen_contingencies
        self.consider_nx_contingencies = consider_nx_contingencies

        self.generation_contingency_threshold = generation_contingency_threshold

        self.time_limit_ms = time_limit_ms
        self.loading_threshold_to_report = loading_threshold_to_report

        self.match_gen_load = match_gen_load

        self.trm = trm
        self.ntc_load_rule = ntc_load_rule
        self.n1_consideration = n1_consideration
        self.reversed_sort_loading = reversed_sort_loading
