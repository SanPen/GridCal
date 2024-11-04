# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List
import numpy as np
import pandas as pd
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.basic_structures import IntVec, Vec, StrVec, CxVec, ObjVec
from GridCalEngine.enumerations import StudyResultsType, ResultTypes, DeviceType


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

    def __init__(self,
                 bus_names: StrVec,
                 branch_names: StrVec,
                 hvdc_names: StrVec,
                 contingency_group_names: StrVec,):
        """

        :param bus_names:
        :param branch_names:
        :param hvdc_names:
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
                                 time_array=None,
                                 clustering_results=None,
                                 study_results_type=StudyResultsType.NetTransferCapacity
                                 )

        n = len(bus_names)
        m = len(branch_names)
        nhvdc = len(hvdc_names)

        self.bus_names = bus_names
        self.branch_names = branch_names
        self.hvdc_names = hvdc_names
        self.contingency_group_names = contingency_group_names
        self.bus_types = np.ones(n, dtype=int)

        self.voltage = np.zeros(n, dtype=complex)
        self.Sbus = np.zeros(n, dtype=complex)
        self.dSbus = np.zeros(n, dtype=complex)
        self.bus_shadow_prices = np.zeros(n, dtype=float)
        self.load_shedding = np.zeros(n, dtype=float)

        self.Sf = np.zeros(m, dtype=float)
        self.St = np.zeros(m, dtype=float)
        self.overloads = np.zeros(m, dtype=float)
        self.loading = np.zeros(m, dtype=float)
        self.losses = np.zeros(m, dtype=float)
        self.phase_shift = np.zeros(m, dtype=float)
        self.rates = np.zeros(m, dtype=float)
        self.contingency_rates = np.zeros(m, dtype=float)
        self.alpha = np.zeros(m, dtype=float)
        self.monitor_logic = np.zeros(m, dtype=object)

        self.hvdc_Pf = np.zeros(nhvdc, dtype=float)
        self.hvdc_loading = np.zeros(nhvdc, dtype=float)
        self.hvdc_losses = np.zeros(nhvdc, dtype=float)

        # indices to post process
        self.sending_bus_idx: List[int] = list()
        self.receiving_bus_idx: List[int] = list()
        self.inter_space_branches: List[tuple[int, float]] = list()  # index, sense
        self.inter_space_hvdc: List[tuple[int, float]] = list()  # index, sense

        # t, m, c, contingency, negative_slack, positive_slack
        self.contingency_flows_list = list()

        self.converged = False

        self.register(name='bus_names', tpe=StrVec)
        self.register(name='branch_names', tpe=StrVec)
        self.register(name='hvdc_names', tpe=StrVec)
        self.register(name='contingency_group_names', tpe=StrVec)
        self.register(name='bus_types', tpe=IntVec)

        self.register(name='voltage', tpe=CxVec)
        self.register(name='Sbus', tpe=CxVec)
        self.register(name='dSbus', tpe=CxVec)
        self.register(name='bus_shadow_prices', tpe=Vec)
        self.register(name='load_shedding', tpe=Vec)

        self.register(name='Sf', tpe=CxVec)
        self.register(name='St', tpe=CxVec)
        self.register(name='overloads', tpe=Vec)
        self.register(name='loading', tpe=Vec)
        self.register(name='losses', tpe=Vec)
        self.register(name='phase_shift', tpe=Vec)
        self.register(name='rates', tpe=Vec)
        self.register(name='contingency_rates', tpe=Vec)
        self.register(name='alpha', tpe=Vec)
        self.register(name='monitor_logic', tpe=ObjVec)

        self.register(name='hvdc_Pf', tpe=Vec)
        self.register(name='hvdc_loading', tpe=Vec)
        self.register(name='hvdc_losses', tpe=Vec)

        self.register(name='converged', tpe=bool)
        self.register(name='contingency_flows_list', tpe=list)

        self.register(name='sending_bus_idx', tpe=list)
        self.register(name='receiving_bus_idx', tpe=list)
        self.register(name='inter_space_branches', tpe=list)
        self.register(name='inter_space_hvdc', tpe=list)

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

        elif result_type == ResultTypes.BranchPower:
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

        elif result_type == ResultTypes.InterSpaceBranchPower:

            data = list()
            index = list()
            for k, sense in self.inter_space_branches:
                index.append(self.branch_names[k])
                data.append(self.Sf[k].real)

            for k, sense in self.inter_space_hvdc:
                index.append(self.hvdc_names[k])
                data.append(self.hvdc_Pf[k])

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

        elif result_type == ResultTypes.ContingencyFlowsReport:
            data = list()
            index = list()
            columns = ['Monitored index', 'Contingency group index',
                       'Contingency branch', 'Contingency group',
                       'Flow (MW)', 'Loading (%)']
            for t, m, c, contingency, negative_slack, positive_slack in self.contingency_flows_list:
                index.append("")
                flow_c = contingency - negative_slack + positive_slack
                loading_c = abs(flow_c) / self.contingency_rates[m] * 100
                data.append([
                    m, c, self.branch_names[m], self.contingency_group_names[c],
                    np.round(flow_c, 4),
                    np.round(loading_c, 4)
                ])

            return ResultsTable(
                data=np.array(data),
                index=np.array(index),
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
