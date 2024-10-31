# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import numpy as np
from typing import List, Union, TYPE_CHECKING

from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.enumerations import ResultTypes, StudyResultsType
from GridCalEngine.Simulations.results_table import ResultsTable, DeviceType
from GridCalEngine.basic_structures import StrVec, DateVec, Vec, IntVec, Mat, CxMat, ObjMat, BoolVec

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCalEngine.Simulations.Clustering.clustering_results import ClusteringResults


class OptimalNetTransferCapacityTimeSeriesResults(ResultsTemplate):

    def __init__(self,
                 bus_names: StrVec,
                 branch_names: StrVec,
                 hvdc_names: StrVec,
                 contingency_group_names: StrVec,
                 time_array: DateVec,
                 time_indices: IntVec,
                 clustering_results: Union[ClusteringResults, None] = None):

        """

        :param bus_names:
        :param branch_names:
        :param hvdc_names:
        :param contingency_group_names:
        :param time_array:
        :param time_indices:
        :param clustering_results:
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
                    ResultTypes.BranchPower,
                    ResultTypes.BranchLoading,
                    ResultTypes.BranchTapAngle,
                    ResultTypes.BranchMonitoring,
                    ResultTypes.AvailableTransferCapacityAlpha,
                ],
                ResultTypes.HvdcResults: [
                    ResultTypes.HvdcPowerFrom,
                ],
                ResultTypes.FlowReports: [
                    ResultTypes.ContingencyFlowsReport,
                    ResultTypes.InterSpaceBranchPower,
                    ResultTypes.InterSpaceBranchLoading,
                ],
            },
            time_array=time_array,
            clustering_results=clustering_results,
            study_results_type=StudyResultsType.NetTransferCapacityTimeSeries)

        nt = len(time_indices)
        m = len(branch_names)
        n = len(bus_names)
        nhvdc = len(hvdc_names)

        # self.time_array = time_array
        self.time_indices = time_indices

        self.branch_names = np.array(branch_names, dtype=object)
        self.bus_names = bus_names
        self.hvdc_names = hvdc_names
        self.contingency_group_names = contingency_group_names
        self.bus_types = np.ones(n, dtype=int)

        self.voltage = np.zeros((nt, n), dtype=complex)
        self.Sbus = np.zeros((nt, n), dtype=complex)
        self.dSbus = np.zeros((nt, n), dtype=complex)
        self.bus_shadow_prices = np.zeros((nt, n), dtype=float)
        self.load_shedding = np.zeros((nt, n), dtype=float)

        self.Sf = np.zeros((nt, m), dtype=complex)
        self.St = np.zeros((nt, m), dtype=complex)
        self.overloads = np.zeros((nt, m), dtype=float)
        self.loading = np.zeros((nt, m), dtype=float)
        self.losses = np.zeros((nt, m), dtype=float)
        self.phase_shift = np.zeros((nt, m), dtype=float)
        self.overloads = np.zeros((nt, m), dtype=float)
        self.rates = np.zeros(m, dtype=float)
        self.contingency_rates = np.zeros(m, dtype=float)
        self.alpha = np.zeros((nt, m), dtype=float)
        self.monitor_logic = np.zeros((nt, m), dtype=object)

        self.hvdc_Pf = np.zeros((nt, nhvdc), dtype=float)
        self.hvdc_loading = np.zeros((nt, nhvdc), dtype=float)
        self.hvdc_losses = np.zeros((nt, nhvdc), dtype=float)

        # indices to post process
        self.sending_bus_idx: List[int] = list()
        self.receiving_bus_idx: List[int] = list()
        self.inter_space_branches: List[tuple[int, float]] = list()  # index, sense
        self.inter_space_hvdc: List[tuple[int, float]] = list()  # index, sense

        # t, m, c, contingency, negative_slack, positive_slack
        self.contingency_flows_list = list()

        self.converged = np.zeros(nt, dtype=bool)

        self.register(name='time_indices', tpe=DateVec)
        self.register(name='bus_names', tpe=StrVec)
        self.register(name='branch_names', tpe=StrVec)
        self.register(name='hvdc_names', tpe=StrVec)
        self.register(name='contingency_group_names', tpe=StrVec)
        self.register(name='bus_types', tpe=IntVec)

        self.register(name='voltage', tpe=CxMat)
        self.register(name='Sbus', tpe=CxMat)
        self.register(name='dSbus', tpe=CxMat)
        self.register(name='bus_shadow_prices', tpe=CxMat)
        self.register(name='load_shedding', tpe=CxMat)

        self.register(name='Sf', tpe=CxMat)
        self.register(name='St', tpe=CxMat)
        self.register(name='overloads', tpe=CxMat)
        self.register(name='loading', tpe=CxMat)
        self.register(name='losses', tpe=CxMat)
        self.register(name='phase_shift', tpe=CxMat)
        self.register(name='rates', tpe=Vec)
        self.register(name='contingency_rates', tpe=Vec)
        self.register(name='alpha', tpe=CxMat)
        self.register(name='monitor_logic', tpe=ObjMat)

        self.register(name='hvdc_Pf', tpe=Mat)
        self.register(name='hvdc_loading', tpe=Mat)
        self.register(name='hvdc_losses', tpe=Mat)

        self.register(name='sending_bus_idx', tpe=list)
        self.register(name='receiving_bus_idx', tpe=list)
        self.register(name='inter_space_branches', tpe=list)
        self.register(name='inter_space_hvdc', tpe=list)

        self.register(name='converged', tpe=BoolVec)
        self.register(name='contingency_flows_list', tpe=list)

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

        elif result_type == ResultTypes.BranchPower:
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

        elif result_type == ResultTypes.InterSpaceBranchPower:

            nt = len(self.time_array)
            ndev = len(self.inter_space_branches) + len(self.inter_space_hvdc)
            data = np.empty((nt, ndev))
            cols = list()
            i = 0
            for k, sense in self.inter_space_branches:
                cols.append(self.branch_names[k])
                data[:, i] = self.Sf[:, k].real
                i += 1

            offset = len(self.inter_space_branches)
            for k, sense in self.inter_space_hvdc:
                cols.append(self.hvdc_names[k])
                data[:, i] = self.hvdc_Pf[:, k]
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

        elif result_type == ResultTypes.ContingencyFlowsReport:
            data = list()
            cols = list()
            columns = ['Time index', 'Monitored index', 'Contingency group index',
                       'Time array', 'Contingency branch', 'Contingency group',
                       'Flow (MW)', 'Loading (%)']
            for t, m, c, contingency, negative_slack, positive_slack in self.contingency_flows_list:
                cols.append("")
                flow_c = contingency - negative_slack + positive_slack
                loading_c = abs(flow_c) / self.contingency_rates[m] * 100
                data.append([
                    t, m, c, str(self.time_array[t]), self.branch_names[m], self.contingency_group_names[c],
                    np.round(flow_c, 4),
                    np.round(loading_c, 4)
                ])

            return ResultsTable(
                data=np.array(data, dtype=object),
                index=np.array(cols),
                columns=columns,
                title=str(result_type.value),
                ylabel='',
                xlabel='',
                units='',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.NoDevice
            )

        else:
            raise ValueError(f"Unknown NTC result type {result_type}")
