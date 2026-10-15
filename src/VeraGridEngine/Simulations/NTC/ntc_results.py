# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Dict, List, Tuple, Union
import numpy as np
import pandas as pd
from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.Simulations.results_template import ResultsTemplate, ResultsProperty
from VeraGridEngine.basic_structures import IntVec, Vec, StrVec, CxVec, ObjVec, DateVec
from VeraGridEngine.enumerations import StudyResultsType, ResultTypes, DeviceType, SolutionState


def monitored_flag_from_logic(value: object) -> bool:
    """
    Convert the stored monitor-logic cell to a boolean flag.

    The OPF writes 0/1 integers. Disk-loaded results may also store booleans.

    :param value: monitor-logic cell
    :return: True when the branch is N-state monitored
    """
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    else:
        if isinstance(value, (int, np.integer, float, np.floating)):
            return int(value) != 0
        else:
            return False


def worst_contingency_report_table(time_array: Union[DateVec, None],
                                   branch_names: StrVec,
                                   group_names: StrVec,
                                   group_device_names: ObjVec,
                                   worst_idx: np.ndarray,
                                   worst_flow: np.ndarray,
                                   worst_loading: np.ndarray,
                                   alpha: np.ndarray,
                                   alpha_n1: np.ndarray,
                                   monitor_logic: np.ndarray,
                                   flow_n: np.ndarray,
                                   loading_n: np.ndarray,
                                   ttc: np.ndarray,
                                   contingency_rates: Vec,
                                   loading_threshold_pct: float,
                                   total_slack_mw: Vec | None = None,
                                   time_percentage: Vec | None = None,
                                   original_time_indices: IntVec | None = None,
                                   result_type: ResultTypes = ResultTypes.ContingencyFlowsReport,
                                   vsc_names: StrVec | None = None,
                                   vsc_power: np.ndarray | None = None,
                                   hvdc_names: StrVec | None = None,
                                   hvdc_power: np.ndarray | None = None,
                                   phase_shifter_indices: IntVec | None = None,
                                   phase_shift: np.ndarray | None = None,
                                   transmission_reliability_margin: float = 0.0,
                                   tied_groups: List[Tuple[int, int, int, float, float, float]] | None = None,
                                   tie_time_keys: IntVec | None = None) -> ResultsTable:
    """
    Build the long form worst-contingency table with one row per kept (time, branch).

    A row is kept only when the branch is monitored and its N-1 loading or its
    N-state loading is at least ``loading_threshold_pct``, so base-case limits show
    up as rows without a contingency group. We also handle tied groups.
    That is the NTC "loading threshold to report" option. It avoids allocating
    an object cell for every branch of every hour.

    :param time_array: timestamps, or None for a snapshot
    :param branch_names: branch names
    :param group_names: contingency group names in grid order
    :param group_device_names: joined outaged-device names in the same order
    :param worst_idx: worst group index per time and branch, -1 if none
    :param worst_flow: N-1 flow (MW) of that group
    :param worst_loading: N-1 loading (p.u.) of that group
    :param alpha: N-state exchange sensitivity
    :param alpha_n1: N-1 exchange sensitivity of the worst group
    :param monitor_logic: N-state monitor flag
    :param flow_n: N-state branch flow (MW)
    :param loading_n: N-state branch loading over the normal rating (p.u.)
    :param ttc: Optimized total transfer capacity of each time index (MW).
    :param transmission_reliability_margin: Margin subtracted from TTC to report NTC (MW).
    :param contingency_rates: branch contingency ratings (MW)
    :param loading_threshold_pct: keep rows whose N-1 or N loading is at least this percent
    :param total_slack_mw: optional total thermal slack per displayed operating point
    :param time_percentage: optional cluster probabilities expressed as percentages
    :param original_time_indices: optional original-series indices for the displayed hours
    :param vsc_names: converter names, in stored power order
    :param vsc_power: base operating-point converter powers, MW (time, converter)
    :param hvdc_names: HVDC names, in stored power order
    :param hvdc_power: base operating-point HVDC powers, MW (time, HVDC)
    :param phase_shifter_indices: indices of branches configured for phase-angle control
    :param phase_shift: base operating-point branch tap angles, radians (time, branch)
    :param result_type: report title to display
    :param tied_groups: (time key, branch, group, N-1 flow MW, N-1 loading p.u., alpha N-1)
                        of the groups tied with the worst group of that time and branch
    :param tie_time_keys: per displayed time row, the time key used in ``tied_groups``
                          (None when the keys are the displayed rows themselves)
    :return: results table
    """
    n_g: int = len(group_names)
    n_dev: int = len(group_device_names)
    # The saved-results reader can restore scalar properties as one-element arrays.
    margin_mw: float = float(np.asarray(transmission_reliability_margin).item())

    if time_array is None:
        include_time: bool = False
    else:
        include_time = True

    # worst_loading is already p.u. of the contingency rate, including the N-state
    loading_pct: np.ndarray = np.asarray(worst_loading, dtype=float) * 100.0
    # the N-state uses the normal rating, which can bind while the N-1 contingency rating does not
    loading_n_pct: np.ndarray = np.abs(np.real(np.asarray(loading_n))) * 100.0
    # Apply the same per hour monitoring flags displayed in the monitored column.
    keep: np.ndarray = (((loading_pct >= float(loading_threshold_pct))
                         | (loading_n_pct >= float(loading_threshold_pct)))
                        & np.asarray(monitor_logic, dtype=bool))
    kept: np.ndarray = np.argwhere(keep)
    n_kept: int = int(kept.shape[0])

    # Tied outages per (time key, branch), so every equally critical group gets its own row
    ties_at: Dict[Tuple[int, int], List[Tuple[int, float, float, float]]] = dict()
    if tied_groups is not None:
        t_key: int
        m_tie: int
        c_tie: int
        flow_tie: float
        loading_tie: float
        alpha_tie: float
        for t_key, m_tie, c_tie, flow_tie, loading_tie, alpha_tie in tied_groups:
            ties_at.setdefault((int(t_key), int(m_tie)), list()).append(
                (int(c_tie), float(flow_tie), float(loading_tie) * 100.0, float(alpha_tie)))
    else:
        pass  # no tie information, one row per kept (time, branch)

    # Expand the kept pairs into report rows, with the worst group first, then its tied groups.
    # Each row is (time, branch, group, N-1 flow, N-1 loading %, alpha N-1)
    report_rows: List[Tuple[int, int, int, float, float, float]] = list()
    kept_i: int
    for kept_i in range(n_kept):
        h_k: int = int(kept[kept_i, 0])
        m_k: int = int(kept[kept_i, 1])
        c_k: int = int(worst_idx[h_k, m_k])
        if 0 <= c_k < n_g:
            report_rows.append((h_k, m_k, c_k, float(worst_flow[h_k, m_k]),
                                float(loading_pct[h_k, m_k]), float(alpha_n1[h_k, m_k])))
            if tie_time_keys is None:
                key_h: int = h_k
            else:
                key_h = int(tie_time_keys[h_k])
            ties_hm: Union[List[Tuple[int, float, float, float]], None] = ties_at.get((key_h, m_k), None)
            if ties_hm is not None:
                c_t: int
                flow_t: float
                loading_t: float
                alpha_t: float
                for c_t, flow_t, loading_t, alpha_t in ties_hm:
                    if 0 <= c_t < n_g:
                        report_rows.append((h_k, m_k, c_t, flow_t, loading_t, alpha_t))
                    else:
                        pass
            else:
                pass  # a single worst group for this branch
        else:
            # no outage makes N-1 worse so we report the N flow as the N-1 flow
            report_rows.append((h_k, m_k, -1, float(np.real(flow_n[h_k, m_k])),
                                float(loading_pct[h_k, m_k]), float(alpha_n1[h_k, m_k])))
    n_rows: int = len(report_rows)

    if include_time:
        n_cols: int = 14
        columns: List[str] = list((
            'Time index', 'Time',
            'Branch', 'Monitored',
            'Contingency group', 'Contingency devices',
            'TTC (MW)', 'NTC (MW)', 'Alpha', 'Alpha N-1',
            'Flow N (MW)', 'Loading N (%)', 'Flow N-1 (MW)', 'Loading N-1 (%)'
        ))
    else:
        n_cols = 12
        columns = list((
            'Branch', 'Monitored',
            'Contingency group', 'Contingency devices',
            'TTC (MW)', 'NTC (MW)', 'Alpha', 'Alpha N-1',
            'Flow N (MW)', 'Loading N (%)', 'Flow N-1 (MW)', 'Loading N-1 (%)'
        ))

    # Slack is useful for snapshots too. Probability exists only for clusters.
    detail_column: int = columns.index('NTC (MW)') + 1
    if total_slack_mw is not None:
        columns.insert(detail_column, 'Total slack (MW)')
        detail_column += 1
        n_cols += 1
    else:
        pass
    if time_percentage is not None:
        columns.insert(detail_column, 'Time percentage (%)')
        n_cols += 1
    else:
        pass

    # Controls describe the optimized N operating point, not corrective N-1 settings.
    # Keep their columns even when a solved power or angle is zero.
    control_start: int = n_cols
    if vsc_names is not None and vsc_power is not None:
        columns.extend(f'VSC {name}: P N (MW)' for name in vsc_names)
    else:
        pass
    if hvdc_names is not None and hvdc_power is not None:
        columns.extend(f'HVDC {name}: P N (MW)' for name in hvdc_names)
    else:
        pass
    if phase_shifter_indices is not None and phase_shift is not None:
        for branch_index in phase_shifter_indices:
            columns.append(f'PST {branch_names[branch_index]}: angle N (deg)')
            columns.append(f'PST {branch_names[branch_index]}: P N (MW)')
    else:
        pass
    n_cols = len(columns)
    data: np.ndarray = np.empty((n_rows, n_cols), dtype=object)
    index: np.ndarray = np.empty(n_rows, dtype=object)

    row_i: int
    h: int
    m: int
    c_star: int
    flow_n1_m: float
    loading_n1_m: float
    alpha_n1_m: float
    for row_i in range(n_rows):
        h, m, c_star, flow_n1_m, loading_n1_m, alpha_n1_m = report_rows[row_i]
        if include_time:
            time_val: str = str(time_array[h])
        else:
            time_val = ""
        ttc_h: float = float(ttc[h])
        # Apply the study margin to capacity reporting, preserving the solved flows.
        ntc_h: float = ttc_h - margin_mw
        flow_n_m: float = float(np.real(flow_n[h, m]))
        if c_star >= 0:
            c_name: str = str(group_names[c_star])
            if c_star < n_dev:
                c_dev: str = str(group_device_names[c_star])
            else:
                c_dev = ""
        else:
            c_name = ""
            c_dev = ""

        mon_flag: bool = monitored_flag_from_logic(monitor_logic[h, m])

        if include_time:
            if original_time_indices is not None:
                data[row_i, 0] = int(original_time_indices[h])
            else:
                data[row_i, 0] = h
            data[row_i, 1] = time_val
            col0: int = 2
        else:
            col0 = 0

        data[row_i, col0 + 0] = branch_names[m]
        data[row_i, col0 + 1] = mon_flag
        data[row_i, col0 + 2] = c_name
        data[row_i, col0 + 3] = c_dev
        data[row_i, col0 + 4] = np.round(ttc_h, 4)
        data[row_i, col0 + 5] = np.round(ntc_h, 4)
        next_col: int = col0 + 6
        if total_slack_mw is not None:
            data[row_i, next_col] = np.round(float(total_slack_mw[h]), 4)
            next_col += 1
        else:
            pass
        if time_percentage is not None:
            data[row_i, next_col] = np.round(float(time_percentage[h]), 6)
            next_col += 1
        else:
            pass
        data[row_i, next_col] = np.round(float(alpha[h, m]), 6)
        data[row_i, next_col + 1] = np.round(alpha_n1_m, 6)
        data[row_i, next_col + 2] = np.round(flow_n_m, 4)
        data[row_i, next_col + 3] = np.round(float(loading_n_pct[h, m]), 4)
        data[row_i, next_col + 4] = np.round(flow_n1_m, 4)
        data[row_i, next_col + 5] = np.round(loading_n1_m, 4)
        control_col: int = control_start
        if vsc_names is not None and vsc_power is not None:
            data[row_i, control_col:control_col + len(vsc_names)] = np.round(vsc_power[h], 4)
            control_col += len(vsc_names)
        else:
            pass
        if hvdc_names is not None and hvdc_power is not None:
            data[row_i, control_col:control_col + len(hvdc_names)] = np.round(hvdc_power[h], 4)
            control_col += len(hvdc_names)
        else:
            pass
        if phase_shifter_indices is not None and phase_shift is not None:
            for branch_index in phase_shifter_indices:
                data[row_i, control_col] = np.round(np.rad2deg(phase_shift[h, branch_index]), 4)
                data[row_i, control_col + 1] = np.round(flow_n[h, branch_index], 4)
                control_col += 2
        else:
            pass
        index[row_i] = ""

    return ResultsTable(
        data=data,
        index=index,
        columns=columns,
        title=str(result_type.value),
        ylabel='',
        xlabel='',
        units='',
        cols_device_type=DeviceType.NoDevice,
        idx_device_type=DeviceType.NoDevice
    )


class OptimalNetTransferCapacityResults(ResultsTemplate):
    """
    OPF results.
    Arguments:
        **Sbus**: bus power Injections
        **voltage**: bus voltages
        **load_shedding**: load shedding values
        **Sf**: branch power values
        **overloads**: branch overloading values
        **loading**: branch loading values
        **losses**: branch losses
        **converged**: converged?
    """

    LOCAL_RESULTS_DECLARATIONS = (
        ResultsProperty(name='bus_names', tpe=StrVec, old_names=list(), expandable=False),
        ResultsProperty(name='branch_names', tpe=StrVec, old_names=list(), expandable=False),
        ResultsProperty(name='hvdc_names', tpe=StrVec, old_names=list(), expandable=False),
        ResultsProperty(name='vsc_names', tpe=StrVec, old_names=list(), expandable=False),
        ResultsProperty(name='contingency_group_names', tpe=StrVec, old_names=list(), expandable=False),
        ResultsProperty(name='bus_types', tpe=IntVec, old_names=list(), expandable=False),
        ResultsProperty(name='voltage', tpe=CxVec, old_names=list(), expandable=False),
        ResultsProperty(name='Sbus', tpe=CxVec, old_names=list(), expandable=False),
        ResultsProperty(name='dSbus', tpe=CxVec, old_names=list(), expandable=False),
        ResultsProperty(name='bus_shadow_prices', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='load_shedding', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='nodal_balance', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='Sf', tpe=CxVec, old_names=list(), expandable=False),
        ResultsProperty(name='St', tpe=CxVec, old_names=list(), expandable=False),
        ResultsProperty(name='overloads', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='loading', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='losses', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='phase_shifter_indices', tpe=IntVec, old_names=list(), expandable=False),
        ResultsProperty(name='phase_shift', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='rates', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='contingency_rates', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='alpha', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='monitor_logic', tpe=ObjVec, old_names=list(), expandable=False),
        ResultsProperty(name='hvdc_Pf', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='hvdc_loading', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='hvdc_losses', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='vsc_Pf', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='vsc_loading', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='vsc_losses', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='converged', tpe=bool, old_names=list(), expandable=False),
        ResultsProperty(name='inter_area_flows', tpe=float, old_names=list(), expandable=False),
        ResultsProperty(name='transmission_reliability_margin', tpe=float, old_names=list(), expandable=False),
        ResultsProperty(name='structural_inter_area_flows', tpe=float, old_names=list(), expandable=False),
        ResultsProperty(name='contingency_flows_list', tpe=list, old_names=list(), expandable=False),
        ResultsProperty(name='strict_formulation', tpe=bool, old_names=list(), expandable=False),
        ResultsProperty(name='contingency_group_device_names', tpe=ObjVec, old_names=list(), expandable=False),
        ResultsProperty(name='worst_contingency_idx', tpe=IntVec, old_names=list(), expandable=False),
        ResultsProperty(name='worst_contingency_flow', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='worst_contingency_loading', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='alpha_n1_worst', tpe=Vec, old_names=list(), expandable=False),
        ResultsProperty(name='worst_contingency_ties', tpe=list, old_names=list(), expandable=False),
        ResultsProperty(name='loading_threshold_to_report', tpe=float, old_names=list(), expandable=False),
        ResultsProperty(name='sending_bus_idx', tpe=list, old_names=list(), expandable=False),
        ResultsProperty(name='receiving_bus_idx', tpe=list, old_names=list(), expandable=False),
        ResultsProperty(name='inter_space_branches', tpe=list, old_names=list(), expandable=False),
        ResultsProperty(name='inter_space_hvdc', tpe=list, old_names=list(), expandable=False),
        ResultsProperty(name='inter_space_vsc', tpe=list, old_names=list(), expandable=False),
    )

    __slots__ = (
        "bus_names",
        "branch_names",
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
        "structural_inter_area_flows",
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
                 transmission_reliability_margin: float = 0.0):
        """

        :param bus_names:
        :param branch_names:
        :param hvdc_names:
        :param transmission_reliability_margin: Study TRM in MW; zero when absent from older saved results.
        """

        ResultsTemplate.__init__(self,
                                 name='NTC',
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
                                         ResultTypes.BranchOverloads,
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
                                         ResultTypes.ContingencyFlowsReport,
                                         ResultTypes.InterSpaceBranchPower,
                                         ResultTypes.InterSpaceBranchLoading,
                                     ],
                                 },
                                 time_array=None,
                                 clustering_results=None,
                                 study_results_type=StudyResultsType.NetTransferCapacity
                                 )

        n = len(bus_names)
        m = len(branch_names)
        nhvdc = len(hvdc_names)
        nvsc = len(vsc_names)

        self.bus_names = bus_names
        self.branch_names = branch_names
        self.hvdc_names = hvdc_names
        self.vsc_names = vsc_names
        self.contingency_group_names = contingency_group_names
        self.bus_types = np.ones(n, dtype=int)

        self.voltage = np.zeros(n, dtype=complex)
        self.Sbus = np.zeros(n, dtype=complex)
        self.dSbus = np.zeros(n, dtype=complex)
        self.bus_shadow_prices = np.zeros(n, dtype=float)
        self.load_shedding = np.zeros(n, dtype=float)
        self.nodal_balance = np.zeros(n, dtype=float)

        self.Sf = np.zeros(m, dtype=float)
        self.St = np.zeros(m, dtype=float)
        self.overloads = np.zeros(m, dtype=float)
        self.loading = np.zeros(m, dtype=float)
        self.losses = np.zeros(m, dtype=float)
        self.phase_shifter_indices: IntVec = np.empty(0, dtype=int)
        self.phase_shift = np.zeros(m, dtype=float)
        self.rates = np.zeros(m, dtype=float)
        self.contingency_rates = np.zeros(m, dtype=float)
        self.alpha = np.zeros(m, dtype=float)
        self.monitor_logic = np.zeros(m, dtype=object)

        self.hvdc_Pf = np.zeros(nhvdc, dtype=float)
        self.hvdc_loading = np.zeros(nhvdc, dtype=float)
        self.hvdc_losses = np.zeros(nhvdc, dtype=float)

        self.vsc_Pf = np.zeros(nvsc, dtype=float)
        self.vsc_loading = np.zeros(nvsc, dtype=float)
        self.vsc_losses = np.zeros(nvsc, dtype=float)

        # indices to post process
        self.sending_bus_idx: List[int] = list()
        self.receiving_bus_idx: List[int] = list()
        self.inter_space_branches: List[tuple[int, float]] = list()  # index, sense
        self.inter_space_hvdc: List[tuple[int, float]] = list()  # index, sense
        self.inter_space_vsc: List[tuple[int, float]] = list()  # index, sense

        # t, m, c, contingency, negative_slack, positive_slack (non-strict)
        # t, m, c, contingency (strict)
        self.contingency_flows_list = list()

        # whether the results come from the strict formulation (no flow slacks)
        self.strict_formulation = False

        self.converged = False

        self.inter_area_flows = 0
        # Store the study margin with the results so saved reports remain reproducible.
        self.transmission_reliability_margin: float = transmission_reliability_margin
        self.structural_inter_area_flows = 0

        n_g: int = len(contingency_group_names)
        self.contingency_group_device_names = np.empty(n_g, dtype=object)
        i_g: int
        for i_g in range(n_g):
            self.contingency_group_device_names[i_g] = ""
        self.worst_contingency_idx = np.full(m, -1, dtype=int)
        self.worst_contingency_flow = np.zeros(m, dtype=float)
        self.worst_contingency_loading = np.zeros(m, dtype=float)
        self.alpha_n1_worst = np.zeros(m, dtype=float)
        self.worst_contingency_ties: List[Tuple[int, int, int, float, float, float]] = list()
        self.loading_threshold_to_report: float = 98.0


    def get_total_slack_mw(self: "OptimalNetTransferCapacityResults") -> float:
        """
        Total limit-relaxation slack of the solution in MW, with the base case overload
        slacks plus the post-contingency relaxation slacks. Strict contingency
        records contain no slack fields and do not contribute to the total.

        :return: total slack in MW
        """
        total: float = float(np.sum(np.abs(self.overloads)))
        if self.strict_formulation:
            pass  # Strict limits have no slacks; their four-field rows contain only flows.
        else:
            # Only the regular formulation appends negative and positive slack values.
            item: tuple[int, int, int, float, object, object]
            for item in self.contingency_flows_list:
                neg_i: object = item[4]
                pos_i: object = item[5]
                if isinstance(neg_i, float) and isinstance(pos_i, float):
                    total += abs(neg_i) + abs(pos_i)
                else:
                    pass  # Slack not evaluated to a number, nothing to add.
        return total

    def get_solution_state(self, slack_tol_mw: float = 0.1) -> SolutionState:
        """
        Classify the solution: 
        - Optimal (solved and every limit held within tolerance),
        - Relaxed (solved, but only by relaxing limits beyond the tolerance)
        - NotOptimal (the solver did not reach optimality).

        :param slack_tol_mw: total slack below which the solution counts as clean
        :return: NtcSolutionState
        """
        if bool(np.all(self.converged)):
            if self.get_total_slack_mw() <= slack_tol_mw:
                return SolutionState.Optimal
            else:
                return SolutionState.Relaxed
        else:
            return SolutionState.NotOptimal

    def get_bus_df(self) -> pd.DataFrame:
        """
        Get a DataFrame with the buses results
        :return: DataFrame
        """
        return pd.DataFrame(data={'Va': np.angle(self.voltage, deg=True),
                                  'P': self.Sbus.real,
                                  'Shadow price': self.bus_shadow_prices},
                            index=self.bus_names)

    def get_branch_df(self) -> pd.DataFrame:
        """
        Get a DataFrame with the branches results
        :return: DataFrame
        """
        return pd.DataFrame(data={'Pf': self.Sf.real,
                                  'Pt': self.St.real,
                                  'Tap angle': self.phase_shift,
                                  'loading': self.loading.real * 100.0},
                            index=self.branch_names)

    def get_hvdc_df(self) -> pd.DataFrame:
        """
        Get a DataFrame with the battery results
        :return: DataFrame
        """
        return pd.DataFrame(data={'P': self.hvdc_Pf,
                                  'Loading': self.hvdc_loading},
                            index=self.hvdc_names)

    def mdl(self, result_type) -> ResultsTable:
        """
        Plot the results
        :param result_type: type of results (string)
        :return: DataFrame of the results (or None if the result was not understood)
        """

        if result_type == ResultTypes.BusVoltageModule:
            return ResultsTable(
                data=np.abs(self.voltage),
                index=self.bus_names,
                columns=['V (p.u.)'],
                title=str(result_type.value),
                ylabel='(p.u.)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BusDevice
            )

        elif result_type == ResultTypes.BusVoltageAngle:
            return ResultsTable(
                data=np.angle(self.voltage),
                index=self.bus_names,
                columns=['V (radians)'],
                title=str(result_type.value),
                ylabel='(radians)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BusDevice
            )

        elif result_type == ResultTypes.BusActivePower:
            return ResultsTable(
                data=np.real(self.Sbus),
                index=self.bus_names,
                columns=[result_type.value],
                title=str(result_type.value),
                ylabel='(MW)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BusDevice
            )

        elif result_type == ResultTypes.BusActivePowerIncrement:
            return ResultsTable(
                data=np.real(self.dSbus),
                index=self.bus_names,
                columns=[result_type.value],
                title=str(result_type.value),
                ylabel='(MW)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BusDevice
            )

        elif result_type == ResultTypes.BranchActivePowerFrom:
            return ResultsTable(
                data=self.Sf.real,
                columns=['Sf'],
                index=self.branch_names,
                title=str(result_type.value),
                ylabel='(MW)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.BranchLoading:
            return ResultsTable(
                data=self.loading * 100.0,
                index=self.branch_names,
                columns=['Loading'],
                title=str(result_type.value),
                ylabel='(%)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.BranchLosses:
            return ResultsTable(
                data=self.losses.real,
                index=self.branch_names,
                columns=['PLosses'],
                title=str(result_type.value),
                ylabel='(MW)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.BranchTapAngle:
            return ResultsTable(
                data=np.rad2deg(self.phase_shift),
                index=self.branch_names,
                columns=['V (deg)'],
                title=str(result_type.value),
                ylabel='(deg)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.HvdcPowerFrom:
            return ResultsTable(
                data=self.hvdc_Pf,
                index=self.hvdc_names,
                columns=['Pf'],
                title=str(result_type.value),
                ylabel='(MW)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.HVDCLineDevice
            )

        elif result_type == ResultTypes.VscPowerFromPositive:
            return ResultsTable(
                data=self.vsc_Pf,
                index=self.vsc_names,
                columns=['Pf'],
                title=str(result_type.value),
                ylabel='(MW)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.VscDevice
            )

        elif result_type == ResultTypes.AvailableTransferCapacityAlpha:
            return ResultsTable(
                data=self.alpha,
                index=self.branch_names,
                title=str(result_type.value),
                columns=['Sensitivity'],
                ylabel='(p.u.)',
                xlabel='',
                units='',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.AvailableTransferCapacityAlphaN1:
            return ResultsTable(
                data=self.alpha_n1_worst,
                index=self.branch_names,
                title=str(result_type.value),
                columns=['Sensitivity N-1'],
                ylabel='(p.u.)',
                xlabel='',
                units='',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.InterSpaceBranchPower:

            data = list()
            index = list()
            for k, sense in self.inter_space_branches:
                index.append(self.branch_names[k])
                data.append(self.Sf[k].real)

            for k, sense in self.inter_space_hvdc:
                index.append(self.hvdc_names[k])
                data.append(self.hvdc_Pf[k])

            for k, sense in self.inter_space_vsc:
                index.append(self.vsc_names[k])
                data.append(self.vsc_Pf[k])

            index.append("Total")
            data.append(self.inter_area_flows)

            return ResultsTable(
                data=np.array(data),
                index=np.array(index),
                columns=['Flow (MW)'],
                title=str(result_type.value),
                ylabel='(MW)',
                xlabel='',
                units='',
                cols_device_type=DeviceType.BranchDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.InterSpaceBranchLoading:
            data = list()
            index = list()
            for k, sense in self.inter_space_branches:
                index.append(self.branch_names[k])
                data.append(self.loading[k].real)

            for k, sense in self.inter_space_hvdc:
                index.append(self.hvdc_names[k])
                data.append(self.hvdc_loading[k])

            for k, sense in self.inter_space_vsc:
                index.append(self.vsc_names[k])
                data.append(self.vsc_loading[k])

            return ResultsTable(
                data=np.array(data) * 100.0,
                index=np.array(index),
                columns=['Loading (%)'],
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
                index=self.branch_names,
                title=str(result_type.value),
                columns=['Monitoring logic'],
                ylabel='()',
                xlabel='',
                units='',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.BranchOverloads:
            return ResultsTable(
                data=self.overloads,
                index=self.branch_names,
                title=str(result_type.value),
                columns=['Overload slack (MW)'],
                ylabel='(MW)',
                xlabel='',
                units='(MW)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.ContingencyFlowsReport:
            n_br: int = len(self.branch_names)
            flow_n: np.ndarray = np.real(self.Sf).reshape(1, n_br)
            return worst_contingency_report_table(
                time_array=None,
                total_slack_mw=np.array([self.get_total_slack_mw()], dtype=float),
                branch_names=self.branch_names,
                group_names=self.contingency_group_names,
                group_device_names=self.contingency_group_device_names,
                worst_idx=self.worst_contingency_idx.reshape(1, n_br),
                worst_flow=self.worst_contingency_flow.reshape(1, n_br),
                worst_loading=self.worst_contingency_loading.reshape(1, n_br),
                alpha=self.alpha.reshape(1, n_br),
                alpha_n1=self.alpha_n1_worst.reshape(1, n_br),
                monitor_logic=self.monitor_logic.reshape(1, n_br),
                flow_n=flow_n,
                loading_n=self.loading.reshape(1, n_br),
                ttc=np.array([self.inter_area_flows], dtype=float),
                transmission_reliability_margin=self.transmission_reliability_margin,
                contingency_rates=self.contingency_rates,
                loading_threshold_pct=self.loading_threshold_to_report,
                vsc_names=self.vsc_names,
                vsc_power=self.vsc_Pf.reshape(1, -1),
                hvdc_names=self.hvdc_names,
                hvdc_power=self.hvdc_Pf.reshape(1, -1),
                phase_shifter_indices=self.phase_shifter_indices,
                phase_shift=self.phase_shift.reshape(1, -1),
                tied_groups=self.worst_contingency_ties
            )

        else:
            raise ValueError(f"Unknown NTC result type {result_type}")
