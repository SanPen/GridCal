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
from typing import List, Tuple, Dict
import numpy as np
import pandas as pd
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.basic_structures import DateVec, IntVec, Vec, StrVec, CxVec
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
                 hvdc_names: StrVec):
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
                                     ],
                                     ResultTypes.BranchResults: [
                                         ResultTypes.BranchPower,
                                         ResultTypes.BranchLoading,
                                         ResultTypes.BranchTapAngle,
                                         ResultTypes.BranchMonitoring
                                     ],
                                     ResultTypes.HvdcResults: [
                                         ResultTypes.HvdcPowerFrom,
                                     ],
                                     ResultTypes.AreaResults: [
                                         ResultTypes.AvailableTransferCapacityAlpha,
                                         ResultTypes.InterAreaExchange,
                                     ],
                                     ResultTypes.FlowReports: [
                                         ResultTypes.ContingencyFlowsReport,
                                         ResultTypes.ContingencyFlowsBranchReport,
                                         ResultTypes.ContingencyFlowsGenerationReport,
                                         ResultTypes.ContingencyFlowsHvdcReport,
                                     ],
                                 },
                                 time_array=None,
                                 clustering_results=None,
                                 study_results_type=StudyResultsType.NetTransferCapacityTimeSeries
                                 )

        n = len(bus_names)
        m = len(branch_names)
        nhvdc = len(hvdc_names)

        self.bus_names = bus_names
        self.branch_names = branch_names
        self.hvdc_names = hvdc_names
        self.bus_types = np.ones(n, dtype=int)

        self.voltage = np.zeros(n, dtype=complex)
        self.Sbus = np.zeros(n, dtype=complex)
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

        self.hvdc_Pf = np.zeros(nhvdc, dtype=float)
        self.hvdc_loading = np.zeros(nhvdc, dtype=float)
        self.hvdc_losses = np.zeros(nhvdc, dtype=float)

        # t, m, c, contingency, negative_slack, positive_slack
        self.contingency_flows_list = list()

        self.converged = False

        self.register(name='bus_names', tpe=StrVec)
        self.register(name='branch_names', tpe=StrVec)
        self.register(name='hvdc_names', tpe=StrVec)
        self.register(name='bus_types', tpe=IntVec)

        self.register(name='voltage', tpe=CxVec)
        self.register(name='Sbus', tpe=CxVec)
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

        self.register(name='hvdc_Pf', tpe=Vec)
        self.register(name='hvdc_loading', tpe=Vec)
        self.register(name='hvdc_losses', tpe=Vec)

        self.register(name='converged', tpe=bool)
        self.register(name='contingency_flows_list', tpe=list)

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

        elif result_type == ResultTypes.BusPower:
            return ResultsTable(
                data=self.loading * 100.0,
                index=self.Sbus.real,
                columns=['Sb'],
                title=str(result_type.value),
                ylabel='(MW)',
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.BusDevice
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

        elif result_type == ResultTypes.AvailableTransferCapacityAlphaN1:
            return ResultsTable(
                data=self.alpha_n1,
                index=self.branch_names,
                columns=self.branch_names,
                title=str(result_type.value),
                ylabel='(p.u.)',
                xlabel='',
                units='',
                cols_device_type=DeviceType.BranchDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.BranchMonitoring:
            return self.get_monitoring_logic_report()

        elif result_type == ResultTypes.InterAreaExchange:
            return self.get_interarea_exchange_report()

        elif result_type == ResultTypes.ContingencyFlowsReport:
            return self.get_contingency_report(
                loading_threshold=self.loading_threshold,
                reverse=self.reversed_sort_loading,
            )

        elif result_type == ResultTypes.ContingencyFlowsBranchReport:
            return self.get_contingency_branch_report(
                loading_threshold=self.loading_threshold,
                reverse=self.reversed_sort_loading,
            )

        elif result_type == ResultTypes.ContingencyFlowsGenerationReport:
            return self.get_contingency_generation_report(
                loading_threshold=self.loading_threshold,
                reverse=self.reversed_sort_loading,
            )

        elif result_type == ResultTypes.ContingencyFlowsHvdcReport:
            return self.get_contingency_hvdc_report(
                loading_threshold=self.loading_threshold,
                reverse=self.reversed_sort_loading,
            )

        else:
            raise Exception(f"Unknown NTC result type {result_type}")
