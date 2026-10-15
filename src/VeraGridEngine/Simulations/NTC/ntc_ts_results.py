# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import numpy as np
from typing import List, Tuple, Union, TYPE_CHECKING

from VeraGridEngine.Simulations.results_template import ResultsTemplate, ResultsProperty
from VeraGridEngine.enumerations import ResultTypes, StudyResultsType, SolutionState
from VeraGridEngine.Simulations.results_table import ResultsTable, DeviceType
from VeraGridEngine.Simulations.NTC.ntc_results import worst_contingency_report_table
from VeraGridEngine.basic_structures import StrVec, DateVec, Vec, IntVec, Mat, CxMat, ObjMat, BoolVec, IntMat, ObjVec

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from VeraGridEngine.Simulations.Clustering.clustering_results import ClusteringResults


class OptimalNetTransferCapacityTimeSeriesResults(ResultsTemplate):

    LOCAL_RESULTS_DECLARATIONS = (
        ResultsProperty(name='time_indices', tpe=DateVec, old_names=list(), expandable=True),
        ResultsProperty(name='bus_names', tpe=StrVec, old_names=list(), expandable=False),
        ResultsProperty(name='branch_names', tpe=StrVec, old_names=list(), expandable=False),
        ResultsProperty(name='hvdc_names', tpe=StrVec, old_names=list(), expandable=False),
        ResultsProperty(name='vsc_names', tpe=StrVec, old_names=list(), expandable=False),
        ResultsProperty(name='contingency_group_names', tpe=StrVec, old_names=list(), expandable=False),
        ResultsProperty(name='bus_types', tpe=IntVec, old_names=list(), expandable=False),
        ResultsProperty(name='voltage', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='Sbus', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='dSbus', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='bus_shadow_prices', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='load_shedding', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='nodal_balance', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='Sf', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='St', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='overloads', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='loading', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='losses', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='phase_shifter_indices', tpe=IntVec, old_names=list(), expandable=False),
        ResultsProperty(name='phase_shift', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='rates', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='contingency_rates', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='alpha', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='monitor_logic', tpe=ObjMat, old_names=list(), expandable=True),
        ResultsProperty(name='hvdc_Pf', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='hvdc_loading', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='hvdc_losses', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='vsc_Pf', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='vsc_loading', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='vsc_losses', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='sending_bus_idx', tpe=list, old_names=list(), expandable=False),
        ResultsProperty(name='receiving_bus_idx', tpe=list, old_names=list(), expandable=False),
        ResultsProperty(name='inter_space_branches', tpe=list, old_names=list(), expandable=False),
        ResultsProperty(name='inter_space_hvdc', tpe=list, old_names=list(), expandable=False),
        ResultsProperty(name='inter_space_vsc', tpe=list, old_names=list(), expandable=False),
        ResultsProperty(name='converged', tpe=BoolVec, old_names=list(), expandable=True),
        ResultsProperty(name='inter_area_flows', tpe=Vec, old_names=list(), expandable=True),
        ResultsProperty(name='transmission_reliability_margin', tpe=float, old_names=list(), expandable=False),
        ResultsProperty(name='contingency_flows_list', tpe=list, old_names=list(), expandable=False),
        ResultsProperty(name='strict_formulation', tpe=bool, old_names=list(), expandable=False),
        ResultsProperty(name='contingency_group_device_names', tpe=ObjVec, old_names=list(), expandable=False),
        ResultsProperty(name='worst_contingency_idx', tpe=IntMat, old_names=list(), expandable=True),
        ResultsProperty(name='worst_contingency_flow', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='worst_contingency_loading', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='alpha_n1_worst', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='worst_contingency_ties', tpe=list, old_names=list(), expandable=False),
        ResultsProperty(name='loading_threshold_to_report', tpe=float, old_names=list(), expandable=False),
    )

    __slots__ = (
        "branch_names",
        "bus_names",
        "hvdc_names",
        "vsc_names",
        "contingency_group_names",
        "bus_types",
        "voltage",
        "Sbus",
        "dSbus",
        "bus_shadow_prices",
        "load_shedding",
        "nodal_balance",
        "Sf",
        "St",
        "overloads",
        "loading",
        "losses",
        "phase_shift",
        "phase_shifter_indices",
        "rates",
        "contingency_rates",
        "alpha",
        "monitor_logic",
        "hvdc_Pf",
        "hvdc_loading",
        "hvdc_losses",
        "vsc_Pf",
        "vsc_loading",
        "vsc_losses",
        "sending_bus_idx",
        "receiving_bus_idx",
        "inter_space_branches",
        "inter_space_hvdc",
        "inter_space_vsc",
        "contingency_flows_list",
        "strict_formulation",
        "converged",
        "inter_area_flows",
        "transmission_reliability_margin",
        "contingency_group_device_names",
        "worst_contingency_idx",
        "worst_contingency_flow",
        "worst_contingency_loading",
        "alpha_n1_worst",
        "worst_contingency_ties",
        "loading_threshold_to_report",
    )

    def __init__(self,
                 bus_names: StrVec,
                 branch_names: StrVec,
                 hvdc_names: StrVec,
                 vsc_names: StrVec,
                 contingency_group_names: StrVec,
                 time_array: DateVec,
                 time_indices: IntVec,
                 clustering_results: Union[ClusteringResults, None] = None,
                 transmission_reliability_margin: float = 0.0):

        """

        :param bus_names:
        :param branch_names:
        :param hvdc_names:
        :param vsc_names:
        :param contingency_group_names:
        :param time_array:
        :param time_indices:
        :param clustering_results:
        :param transmission_reliability_margin: Study TRM in MW; zero when absent from older saved results.
        """
        ResultsTemplate.__init__(
            self,
            name='NTC Optimal time series results',
            available_results={
                ResultTypes.BusResults: [
                    ResultTypes.BusVoltageModule,
                    ResultTypes.BusVoltageAngle,
                    ResultTypes.BusActivePower,
                    ResultTypes.BusActivePowerIncrement,
                ],
                ResultTypes.BranchResults: [
                    ResultTypes.BranchActivePowerFrom,
                    ResultTypes.BranchLoading,
                    ResultTypes.BranchTapAngle,
                    ResultTypes.BranchMonitoring,
                    ResultTypes.AvailableTransferCapacityAlpha,
                    ResultTypes.AvailableTransferCapacityAlphaN1,
                ],
                ResultTypes.HvdcResults: [
                    ResultTypes.HvdcPowerFrom,
                ],
                ResultTypes.VscResults: [
                    ResultTypes.VscPowerFromPositive,
                ],
                ResultTypes.FlowReports: [
                    ResultTypes.NetTransferCapacity,
                    ResultTypes.NetTransferCapacitySlack,
                    ResultTypes.NetTransferCapacityStatus,
                    ResultTypes.ContingencyFlowsReport,
                    ResultTypes.InterSpaceBranchPower,
                    ResultTypes.InterSpaceBranchLoading,
                ],
            },
            time_array=time_array,
            clustering_results=clustering_results,
            study_results_type=StudyResultsType.NetTransferCapacityTimeSeries)

        if clustering_results is not None:
            self.available_results[ResultTypes.FlowReports].insert(
                self.available_results[ResultTypes.FlowReports].index(ResultTypes.ContingencyFlowsReport) + 1,
                ResultTypes.ContingencyFlowsRepresentativeReport
            )
        else:
            pass  # Representative hours exist only for clustered simulations.

        nt = len(time_indices)
        m = len(branch_names)
        n = len(bus_names)
        nhvdc = len(hvdc_names)
        nvsc = len(vsc_names)

        # self.time_array = time_array
        self.time_indices = time_indices

        self.branch_names = np.array(branch_names, dtype=object)
        self.bus_names = bus_names
        self.hvdc_names = hvdc_names
        self.vsc_names = vsc_names
        self.contingency_group_names = contingency_group_names
        self.bus_types = np.ones(n, dtype=int)

        self.voltage = np.zeros((nt, n), dtype=complex)
        self.Sbus = np.zeros((nt, n), dtype=complex)
        self.dSbus = np.zeros((nt, n), dtype=complex)
        self.bus_shadow_prices = np.zeros((nt, n), dtype=float)
        self.load_shedding = np.zeros((nt, n), dtype=float)
        self.nodal_balance = np.zeros((nt, n), dtype=float)

        self.Sf = np.zeros((nt, m), dtype=complex)
        self.St = np.zeros((nt, m), dtype=complex)
        self.overloads = np.zeros((nt, m), dtype=float)
        self.loading = np.zeros((nt, m), dtype=float)
        self.losses = np.zeros((nt, m), dtype=float)
        self.phase_shifter_indices: IntVec = np.empty(0, dtype=int)
        self.phase_shift = np.zeros((nt, m), dtype=float)
        self.overloads = np.zeros((nt, m), dtype=float)
        self.rates = np.zeros(m, dtype=float)
        self.contingency_rates = np.zeros(m, dtype=float)
        self.alpha = np.zeros((nt, m), dtype=float)
        self.monitor_logic = np.zeros((nt, m), dtype=object)

        self.hvdc_Pf = np.zeros((nt, nhvdc), dtype=float)
        self.hvdc_loading = np.zeros((nt, nhvdc), dtype=float)
        self.hvdc_losses = np.zeros((nt, nhvdc), dtype=float)

        self.vsc_Pf = np.zeros((nt, nvsc), dtype=float)
        self.vsc_loading = np.zeros((nt, nvsc), dtype=float)
        self.vsc_losses = np.zeros((nt, nvsc), dtype=float)

        # indices to post process
        self.sending_bus_idx: List[int] = list()
        self.receiving_bus_idx: List[int] = list()
        self.inter_space_branches: List[tuple[int, float]] = list()  # index, sense
        self.inter_space_hvdc: List[tuple[int, float]] = list()  # index, sense
        self.inter_space_vsc: List[tuple[int, float]] = list()

        # t, m, c, contingency, negative_slack, positive_slack (non-strict)
        # t, m, c, contingency (strict)
        self.contingency_flows_list = list()

        # whether the results come from the strict formulation (no flow slacks)
        self.strict_formulation = False

        self.converged = np.zeros(nt, dtype=bool)
        self.inter_area_flows = np.zeros(nt, dtype=float)
        # A scalar study margin is shared by original and representative hours.
        self.transmission_reliability_margin: float = transmission_reliability_margin

        n_g: int = len(contingency_group_names)
        self.contingency_group_device_names = np.empty(n_g, dtype=object)
        for i_g in range(n_g):
            self.contingency_group_device_names[i_g] = ""
        self.worst_contingency_idx = np.full((nt, m), -1, dtype=int)
        self.worst_contingency_flow = np.zeros((nt, m), dtype=float)
        self.loading_threshold_to_report: float = 98.0
        self.worst_contingency_loading = np.zeros((nt, m), dtype=float)
        self.alpha_n1_worst = np.zeros((nt, m), dtype=float)
        # simulated time index, branch, group, N-1 flow (MW), N-1 loading (p.u.), alpha N-1 of the tied groups
        self.worst_contingency_ties: List[Tuple[int, int, int, float, float, float]] = list()

    def get_total_slack_mw(self) -> Vec:
        """
        Total limit-relaxation slack of each time step in MW.

        Base-case overload slacks plus post-contingency relaxation slacks.
        Strict runs have no flow slacks, so the result is zero per hour.

        :return: slack per time step in MW
        """
        total: Vec = np.sum(np.abs(self.overloads), axis=1).astype(float)
        n_total: int = int(total.shape[0])

        if self.strict_formulation:
            return total
        else:
            # Size by simulated hours, not by the last recorded contingency row:
            # a final hour with no relaxation entries still needs its zero slot.
            if self.clustering_results is not None:
                n_clustered: int = len(self.clustering_results.time_indices)
            else:
                n_clustered = n_total

            if n_clustered == 0:
                return total
            else:
                con_slack: Vec = np.zeros(n_clustered, dtype=float)
                for item in self.contingency_flows_list:
                    t_i, m_i, c_i, flow_i, neg_i, pos_i = item
                    t_int: int = int(t_i)
                    if isinstance(neg_i, float) and isinstance(pos_i, float) and 0 <= t_int < n_clustered:
                        con_slack[t_int] = con_slack[t_int] + abs(neg_i) + abs(pos_i)
                    else:
                        pass

                sample_idx: IntVec | None = self.original_sample_idx
                if n_clustered == n_total:
                    total = total + con_slack
                elif sample_idx is not None and int(sample_idx.shape[0]) == n_total:
                    h: int
                    for h in range(n_total):
                        cluster_t: int = int(sample_idx[h])
                        if 0 <= cluster_t < n_clustered:
                            total[h] = total[h] + con_slack[cluster_t]
                        else:
                            pass
                else:
                    pass

                return total

    def get_solution_states(self, slack_tol_mw: float = 0.1) -> List[SolutionState]:
        """
        Classify each time step as Optimal, Relaxed, or NotOptimal.

        Optimal: the solver converged and total slack is within tolerance.
        Relaxed: the solver converged, but only by relaxing limits.
        NotOptimal: the solver did not reach optimality.

        :param slack_tol_mw: total slack below which the hour counts as clean
        :return: one solution state per time step
        """
        slacks: Vec = self.get_total_slack_mw()
        n_time: int = len(self.converged)
        states: List[SolutionState] = list()
        t: int
        for t in range(n_time):
            if bool(self.converged[t]):
                if slacks[t] <= slack_tol_mw:
                    states.append(SolutionState.Optimal)
                else:
                    states.append(SolutionState.Relaxed)
            else:
                states.append(SolutionState.NotOptimal)
        return states

    def mdl(self, result_type) -> ResultsTable:
        """
        Plot the results
        :param result_type: type of results (string)
        :return: DataFrame of the results (or None if the result was not understood)
        """

        if result_type == ResultTypes.BusVoltageModule:
            return ResultsTable(
                data=np.abs(self.voltage),
                index=self.time_array,
                columns=self.bus_names,
                title=str(result_type.value),
                ylabel='(p.u.)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BusDevice
            )

        elif result_type == ResultTypes.BusVoltageAngle:
            return ResultsTable(
                data=np.angle(self.voltage),
                index=self.time_array,
                columns=self.bus_names,
                title=str(result_type.value),
                ylabel='(radians)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BusDevice
            )

        elif result_type == ResultTypes.BusActivePower:
            return ResultsTable(
                data=np.real(self.Sbus),
                index=self.time_array,
                columns=self.bus_names,
                title=str(result_type.value),
                ylabel='(MW)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BusDevice
            )

        elif result_type == ResultTypes.BusActivePowerIncrement:
            return ResultsTable(
                data=np.real(self.dSbus),
                index=self.time_array,
                columns=self.bus_names,
                title=str(result_type.value),
                ylabel='(MW)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BusDevice
            )

        elif result_type == ResultTypes.BranchActivePowerFrom:
            return ResultsTable(
                data=self.Sf.real,
                index=self.time_array,
                columns=self.branch_names,
                title=str(result_type.value),
                ylabel='(MW)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.BranchLoading:
            return ResultsTable(
                data=self.loading * 100.0,
                index=self.time_array,
                columns=self.branch_names,
                title=str(result_type.value),
                ylabel='(%)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.BranchLosses:
            return ResultsTable(
                data=self.losses.real,
                index=self.time_array,
                columns=self.branch_names,
                title=str(result_type.value),
                ylabel='(MW)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.BranchTapAngle:
            return ResultsTable(
                data=np.rad2deg(self.phase_shift),
                index=self.time_array,
                columns=self.branch_names,
                title=str(result_type.value),
                ylabel='(deg)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.HvdcPowerFrom:
            return ResultsTable(
                data=self.hvdc_Pf,
                index=self.time_array,
                columns=self.hvdc_names,
                title=str(result_type.value),
                ylabel='(MW)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.HVDCLineDevice
            )

        elif result_type == ResultTypes.VscPowerFromPositive:
            return ResultsTable(
                data=self.vsc_Pf,
                index=self.time_array,
                columns=self.vsc_names,
                title=str(result_type.value),
                ylabel='(MW)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.VscDevice
            )

        elif result_type == ResultTypes.AvailableTransferCapacityAlpha:
            return ResultsTable(
                data=self.alpha,
                index=self.time_array,
                columns=self.branch_names,
                title=str(result_type.value),
                ylabel='(p.u.)',
                xlabel='',
                units='',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.AvailableTransferCapacityAlphaN1:
            return ResultsTable(
                data=self.alpha_n1_worst,
                index=self.time_array,
                columns=self.branch_names,
                title=str(result_type.value),
                ylabel='(p.u.)',
                xlabel='',
                units='',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.InterSpaceBranchPower:

            nt = len(self.time_array)
            ndev = len(self.inter_space_branches) + len(self.inter_space_hvdc) + len(self.inter_space_vsc)
            data = np.empty((nt, ndev))
            cols = list()
            i = 0
            for k, sense in self.inter_space_branches:
                cols.append(self.branch_names[k])
                data[:, i] = self.Sf[:, k].real
                i += 1

            for k, sense in self.inter_space_hvdc:
                cols.append(self.hvdc_names[k])
                data[:, i] = self.hvdc_Pf[:, k]
                i += 1

            for k, sense in self.inter_space_vsc:
                cols.append(self.vsc_names[k])
                data[:, i] = self.vsc_Pf[:, k]
                i += 1

            return ResultsTable(
                data=data,
                index=self.time_array,
                columns=np.array(cols),
                title=str(result_type.value),
                ylabel='(MW)',
                xlabel='',
                units='',
                cols_device_type=DeviceType.BranchDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.InterSpaceBranchLoading:
            nt = len(self.time_array)
            ndev = len(self.inter_space_branches) + len(self.inter_space_hvdc)
            data = np.empty((nt, ndev))
            cols = list()
            i = 0
            for k, sense in self.inter_space_branches:
                cols.append(self.branch_names[k])
                data[:, i] = self.loading[:, k].real
                i += 1

            offset = len(self.inter_space_branches)
            for k, sense in self.inter_space_hvdc:
                cols.append(self.hvdc_names[k])
                data[:, i] = self.hvdc_loading[:, k]
                i += 1

            return ResultsTable(
                data=np.array(data) * 100.0,
                index=self.time_array,
                columns=np.array(cols),
                title=str(result_type.value),
                ylabel='(%)',
                xlabel='',
                units='',
                cols_device_type=DeviceType.BranchDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.BranchMonitoring:
            return ResultsTable(
                data=self.monitor_logic,
                index=self.time_array,
                columns=self.branch_names,
                title=str(result_type.value),
                ylabel='()',
                xlabel='',
                units='',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.NetTransferCapacity:
            # The optimizer returns TTC; subtract TRM only in the capacity report.
            return ResultsTable(
                data=np.column_stack((self.inter_area_flows,
                                      self.inter_area_flows - self.transmission_reliability_margin)),
                index=self.time_array,
                columns=np.array(('TTC (MW)', 'NTC (MW)')),
                title=str(result_type.value),
                ylabel='(MW)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.NoDevice
            )

        elif result_type == ResultTypes.NetTransferCapacitySlack:
            slacks: Vec = self.get_total_slack_mw()
            return ResultsTable(
                data=slacks.reshape(-1, 1),
                index=self.time_array,
                columns=np.array(['Total slack (MW)']),
                title=str(result_type.value),
                ylabel='(MW)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.NoDevice
            )

        elif result_type == ResultTypes.NetTransferCapacityStatus:
            # enum quality of each hour, kept off the float table
            states: List[SolutionState] = self.get_solution_states()
            n_time: int = len(states)
            data: np.ndarray = np.empty((n_time, 1), dtype=object)
            t: int
            for t in range(n_time):
                data[t, 0] = states[t]
            return ResultsTable(
                data=data,
                index=self.time_array,
                columns=np.array(['Status']),
                title=str(result_type.value),
                ylabel='',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.NoDevice
            )

        elif result_type == ResultTypes.ContingencyFlowsReport:
            # ties are keyed by simulated step, while expanded clustered rows are calendar hours
            if (self.clustering_results is not None
                    and len(self.inter_area_flows) != len(self.clustering_results.time_indices)):
                tie_time_keys: IntVec | None = self.original_sample_idx
            else:
                tie_time_keys = None
            return worst_contingency_report_table(
                time_array=self.time_array,
                branch_names=self.branch_names,
                group_names=self.contingency_group_names,
                group_device_names=self.contingency_group_device_names,
                worst_idx=self.worst_contingency_idx,
                worst_flow=self.worst_contingency_flow,
                worst_loading=self.worst_contingency_loading,
                alpha=self.alpha,
                alpha_n1=self.alpha_n1_worst,
                monitor_logic=self.monitor_logic,
                flow_n=np.real(self.Sf),
                loading_n=self.loading,
                ttc=self.inter_area_flows,
                transmission_reliability_margin=self.transmission_reliability_margin,
                contingency_rates=self.contingency_rates,
                loading_threshold_pct=self.loading_threshold_to_report,
                total_slack_mw=self.get_total_slack_mw(),
                vsc_names=self.vsc_names,
                vsc_power=self.vsc_Pf,
                hvdc_names=self.hvdc_names,
                hvdc_power=self.hvdc_Pf,
                phase_shifter_indices=self.phase_shifter_indices,
                phase_shift=self.phase_shift,
                tied_groups=self.worst_contingency_ties,
                tie_time_keys=tie_time_keys
            )

        elif (result_type == ResultTypes.ContingencyFlowsRepresentativeReport
              and self.clustering_results is not None):
            representative_indices: IntVec = self.clustering_results.time_indices
            # The GUI normally expands arrays to the original calendar. API callers
            # may retain reduced arrays; both must produce the same representative view.
            if len(self.inter_area_flows) == len(self.clustering_results.time_array):
                selected_rows: IntVec = representative_indices
            else:
                selected_rows = np.arange(len(representative_indices), dtype=int)
            total_slack: Vec = self.get_total_slack_mw()
            return worst_contingency_report_table(
                time_array=self.clustering_results.time_array[representative_indices],
                branch_names=self.branch_names,
                group_names=self.contingency_group_names,
                group_device_names=self.contingency_group_device_names,
                worst_idx=self.worst_contingency_idx[selected_rows],
                worst_flow=self.worst_contingency_flow[selected_rows],
                worst_loading=self.worst_contingency_loading[selected_rows],
                alpha=self.alpha[selected_rows],
                alpha_n1=self.alpha_n1_worst[selected_rows],
                monitor_logic=self.monitor_logic[selected_rows],
                flow_n=np.real(self.Sf[selected_rows]),
                loading_n=self.loading[selected_rows],
                ttc=self.inter_area_flows[selected_rows],
                transmission_reliability_margin=self.transmission_reliability_margin,
                contingency_rates=self.contingency_rates,
                loading_threshold_pct=self.loading_threshold_to_report,
                total_slack_mw=total_slack[selected_rows],
                time_percentage=self.clustering_results.sampled_probabilities * 100.0,
                original_time_indices=representative_indices,
                result_type=result_type,
                vsc_names=self.vsc_names,
                vsc_power=self.vsc_Pf[selected_rows],
                hvdc_names=self.hvdc_names,
                hvdc_power=self.hvdc_Pf[selected_rows],
                phase_shifter_indices=self.phase_shifter_indices,
                phase_shift=self.phase_shift[selected_rows],
                tied_groups=self.worst_contingency_ties
            )

        else:
            raise ValueError(f"Unknown NTC result type {result_type}")
