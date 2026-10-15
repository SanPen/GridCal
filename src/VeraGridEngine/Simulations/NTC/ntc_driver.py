# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from typing import List, Tuple
import numpy as np
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Events.contingency_group import ContingencyGroup
from VeraGridEngine.Simulations.NTC.ntc_opf import run_linear_ntc_opf
from VeraGridEngine.Simulations.NTC.ntc_opf_strict import run_linear_ntc_opf_strict
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Simulations.NTC.ntc_options import OptimalNetTransferCapacityOptions
from VeraGridEngine.Simulations.NTC.ntc_results import OptimalNetTransferCapacityResults
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import SimulationTypes, TapPhaseControl
from VeraGridEngine.Devices.Parents.controllable_branch_parent import ControllableBranchParent
from VeraGridEngine.basic_structures import ObjVec, IntVec, BoolVec


def select_ntc_contingency_groups(grid: MultiCircuit,
                                  selected: List[ContingencyGroup]) -> List[ContingencyGroup]:
    """Resolve the same active contingency selection for both NTC drivers.

    :param grid: Circuit supplying the default contingency groups.
    :param selected: Explicit selection; an empty list selects all active groups.
    :return: Active groups in their original selection order.
    """
    candidates: List[ContingencyGroup]
    if len(selected) > 0:
        candidates = selected
    else:
        candidates = grid.get_contingency_groups()

    # Allocate once, filter by activity, and convert to the formulation's list API.
    group: ContingencyGroup
    active: BoolVec = np.fromiter((group.active for group in candidates), dtype=bool, count=len(candidates))
    groups: ObjVec = np.asarray(candidates, dtype=object)
    return list(groups[active])


def collect_phase_shifter_indices(grid: MultiCircuit, time_indices: IntVec | None = None) -> IntVec:
    """
    Select branches with phase-angle control in any simulated operating point.

    :param grid: circuit whose branch order matches the NTC results
    :param time_indices: simulated original time indices, or None for a snapshot
    :return: branch indices to expose in the control columns
    """
    # Use configuration rather than nonzero angles: an optimized angle can be zero.
    selected: np.ndarray = np.zeros(grid.get_branch_number(), dtype=bool)
    branch_index: int
    for branch_index, branch in enumerate(grid.get_branches()):
        if isinstance(branch, ControllableBranchParent):
            if time_indices is None:
                selected[branch_index] = branch.tap_phase_control_mode in (TapPhaseControl.Pf, TapPhaseControl.Pt)
            else:
                for time_index in time_indices:
                    mode: TapPhaseControl = branch.get_tap_phase_control_mode_at(int(time_index))
                    selected[branch_index] |= mode in (TapPhaseControl.Pf, TapPhaseControl.Pt)
        else:
            pass
    return np.flatnonzero(selected)


def collect_contingency_group_device_names(grid: MultiCircuit) -> ObjVec:
    """
    Join the device names of every contingency that belongs to each group.

    The order matches ``grid.get_contingency_group_names()``. The report uses this
    string to make the outaged equipment visible next to the group name.

    :param grid: circuit that owns the contingency groups and contingency objects
    :return: object array of joined device names, one entry per group
    """
    groups = grid.get_contingency_groups()
    group_dict = grid.get_contingency_group_dict()
    n_g: int = len(groups)
    names: ObjVec = np.empty(n_g, dtype=object)
    i_g: int
    for i_g in range(n_g):
        cnt_list = group_dict.get(groups[i_g].idtag, None)
        if cnt_list is None:
            names[i_g] = ""
        else:
            parts: List[str] = list()
            i_c: int
            for i_c in range(len(cnt_list)):
                parts.append(cnt_list[i_c].device_name)
            names[i_g] = "; ".join(parts)
    return names


class OptimalNetTransferCapacityDriver(DriverTemplate):
    __slots__ = (
        "options",
        "all_solved",
    )

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

    def get_steps(self) -> List[int]:
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

        contingency_groups_used: List[ContingencyGroup] = select_ntc_contingency_groups(
            self.grid, self.options.opf_options.contingency_groups_used)

        if self.options.consider_contingencies:
            self.report_text(f'Formulating NTC OPF ({len(contingency_groups_used)} contingency groups)...')
        else:
            self.report_text('Formulating NTC OPF...')

        if self.options.strict_formulation:
            opf_vars, model = run_linear_ntc_opf_strict(
                grid=self.grid,
                t=None,
                solver_type=self.options.opf_options.mip_solver,
                zonal_grouping=self.options.opf_options.zonal_grouping,
                skip_generation_limits=self.options.skip_generation_limits,
                consider_contingencies=self.options.consider_contingencies,
                corrective_contingencies=self.options.corrective_contingencies,
                contingency_groups_used=contingency_groups_used,
                lodf_threshold=self.options.lin_options.lodf_threshold,
                bus_a1_idx=self.options.sending_bus_idx,
                bus_a2_idx=self.options.receiving_bus_idx,
                transfer_method=self.options.transfer_method,
                monitor_only_ntc_load_rule_branches=self.options.monitor_only_ntc_load_rule_branches,
                alpha_threshold=self.options.branch_exchange_sensitivity,
                monitor_only_sensitive_branches=self.options.use_branch_exchange_sensitivity,
                ntc_load_rule=self.options.branch_rating_contribution,
                logger=self.logger,
                progress_text=self.report_text,
                progress_func=self.report_progress,
                verbose=self.options.opf_options.verbose,
                robust=self.options.opf_options.robust,
                mip_framework=self.options.opf_options.mip_framework
            )
        else:
            opf_vars, model = run_linear_ntc_opf(
                grid=self.grid,
                t=None,
                solver_type=self.options.opf_options.mip_solver,
                zonal_grouping=self.options.opf_options.zonal_grouping,
                skip_generation_limits=self.options.skip_generation_limits,
                consider_contingencies=self.options.consider_contingencies,
                corrective_contingencies=self.options.corrective_contingencies,
                contingency_groups_used=contingency_groups_used,
                lodf_threshold=self.options.lin_options.lodf_threshold,
                bus_a1_idx=self.options.sending_bus_idx,
                bus_a2_idx=self.options.receiving_bus_idx,
                transfer_method=self.options.transfer_method,
                monitor_only_ntc_load_rule_branches=self.options.monitor_only_ntc_load_rule_branches,
                alpha_threshold=self.options.branch_exchange_sensitivity,
                monitor_only_sensitive_branches=self.options.use_branch_exchange_sensitivity,
                ntc_load_rule=self.options.branch_rating_contribution,
                logger=self.logger,
                progress_text=self.report_text,
                progress_func=self.report_progress,
                verbose=self.options.opf_options.verbose,
                robust=self.options.opf_options.robust,
                mip_framework=self.options.opf_options.mip_framework
            )

        # pack the results
        self.results = OptimalNetTransferCapacityResults(
            bus_names=self.grid.get_bus_names(),
            branch_names=self.grid.get_branch_names(add_hvdc=False, add_vsc=False, add_switch=True),
            hvdc_names=self.grid.get_hvdc_names(),
            vsc_names=self.grid.get_vsc_names(),
            contingency_group_names=self.grid.get_contingency_group_names(),
            transmission_reliability_margin=self.options.transmission_reliability_margin,
        )

        self.results.phase_shifter_indices = collect_phase_shifter_indices(self.grid)
        self.results.voltage = opf_vars.get_voltages()[0, :]
        self.results.Sbus = opf_vars.bus_vars.Pinj[0, :]
        self.results.dSbus = opf_vars.bus_vars.delta_p[0, :]
        self.results.bus_shadow_prices = opf_vars.bus_vars.shadow_prices[0, :]

        self.results.nodal_balance = opf_vars.bus_vars.Pbalance[0, :]

        self.results.Sf = opf_vars.branch_vars.flows[0, :]
        self.results.St = -opf_vars.branch_vars.flows[0, :]

        if not self.options.strict_formulation:
            self.results.load_shedding = opf_vars.bus_vars.load_shedding[0, :]
            self.results.overloads = (opf_vars.branch_vars.flow_slacks_pos[0, :]
                                      - opf_vars.branch_vars.flow_slacks_neg[0, :])

        self.results.loading = opf_vars.branch_vars.loading[0, :]
        self.results.phase_shift = opf_vars.branch_vars.tap_angles[0, :]
        self.results.rates = opf_vars.branch_vars.rates[0, :]
        self.results.contingency_rates = opf_vars.branch_vars.contingency_rates[0, :]
        self.results.alpha = opf_vars.branch_vars.alpha[0, :]
        self.results.monitor_logic = opf_vars.branch_vars.monitor_logic[0, :]
        self.results.contingency_flows_list = opf_vars.branch_vars.contingency_flow_data
        self.results.strict_formulation = self.options.strict_formulation
        self.results.loading_threshold_to_report = self.options.loading_threshold_to_report

        self.results.hvdc_Pf = opf_vars.hvdc_vars.flows[0, :]
        self.results.hvdc_loading = opf_vars.hvdc_vars.loading[0, :]

        self.results.vsc_Pf = opf_vars.vsc_vars.flows[0, :]
        self.results.vsc_loading = opf_vars.vsc_vars.loading[0, :]

        self.results.sending_bus_idx = self.options.sending_bus_idx
        self.results.receiving_bus_idx = self.options.receiving_bus_idx

        self.results.inter_space_branches = opf_vars.branch_vars.inter_space_branches
        self.results.inter_space_hvdc = opf_vars.hvdc_vars.inter_space_hvdc
        self.results.inter_space_vsc = opf_vars.vsc_vars.inter_space_vsc

        self.results.inter_area_flows = opf_vars.inter_area_flows[0]
        self.results.structural_inter_area_flows = opf_vars.structural_ntc[0]
        self.results.contingency_group_device_names = collect_contingency_group_device_names(self.grid)
        self.results.worst_contingency_idx = opf_vars.branch_vars.worst_contingency_idx[0, :]
        self.results.worst_contingency_flow = opf_vars.branch_vars.worst_contingency_flow[0, :]
        self.results.worst_contingency_loading = opf_vars.branch_vars.worst_contingency_loading[0, :]
        self.results.alpha_n1_worst = opf_vars.branch_vars.alpha_n1_worst[0, :]
        # keep only the ties of rows the report can show
        tie: Tuple[int, int, float, float, float]
        for tie in opf_vars.branch_vars.worst_contingency_ties:
            tie_branch: int = tie[0]
            row_loading_pct: float = 100.0 * max(
                float(opf_vars.branch_vars.worst_contingency_loading[0, tie_branch]),
                abs(float(opf_vars.branch_vars.loading[0, tie_branch])))
            if (opf_vars.branch_vars.monitor_logic[0, tie_branch]
                    and row_loading_pct >= self.options.loading_threshold_to_report):
                self.results.worst_contingency_ties.append((0,) + tie)
            else:
                pass  # the report never displays this branch

        self.results.converged = opf_vars.acceptable_solution

        if self.options.opf_options.report_formulation:
            self.results.report_text = model.model_as_string()

        self.report_text('Done!')

        return self.results

    def run(self) -> None:
        """
        Run this study
        """
        self.tic()
        self.report_text("Compiling and configuring...")

        self.opf()

        self.toc()
