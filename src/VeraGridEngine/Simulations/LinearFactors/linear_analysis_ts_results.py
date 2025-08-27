# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.Simulations.results_template import ResultsTemplate
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.basic_structures import DateVec, IntVec, StrVec, CxMat, Mat
from VeraGridEngine.enumerations import StudyResultsType, ResultTypes, DeviceType


class LinearAnalysisTimeSeriesResults(ResultsTemplate):

    def __init__(
            self,
            n: int,
            m: int,
            time_array: DateVec,
            bus_names: StrVec,
            bus_types: IntVec,
            branch_names: StrVec,
            clustering_results):
        """
        Constructor
        :param n: number of buses
        :param m: number of Branches
        :param time_array: array of time steps
        :param bus_names: array of bus names
        :param bus_types: array of bus types
        :param branch_names: array of branch names
        """
        ResultsTemplate.__init__(
            self,
            name='Linear Analysis time series',
            available_results=[
                ResultTypes.BusActivePower,
                ResultTypes.BranchActivePowerFrom,
                ResultTypes.BranchLoading
            ],
            time_array=time_array,
            clustering_results=clustering_results,
            study_results_type=StudyResultsType.LinearAnalysisTimeSeries
        )

        nt: int = len(time_array)

        self.bus_names: StrVec = bus_names
        self.bus_types: IntVec = bus_types
        self.branch_names: StrVec = branch_names

        self.voltage: CxMat = np.ones((nt, n), dtype=complex)
        self.S: CxMat = np.zeros((nt, n), dtype=complex)
        self.Sf: CxMat = np.zeros((nt, m), dtype=complex)
        self.loading: Mat = np.zeros((nt, m), dtype=float)
        self.losses: CxMat = np.zeros((nt, m), dtype=float)

        self.register(name='branch_names', tpe=StrVec)
        self.register(name='bus_names', tpe=StrVec)
        self.register(name='bus_types', tpe=IntVec)

        self.register(name='voltage', tpe=CxMat)
        self.register(name='Sf', tpe=CxMat)
        self.register(name='S', tpe=CxMat)
        self.register(name='losses', tpe=CxMat)
        self.register(name='loading', tpe=CxMat)

    def apply_new_time_series_rates(self, nc: NumericalCircuit) -> None:
        rates = nc.Rates.T
        self.loading = self.Sf / (rates + 1e-9)

    # def get_dict(self):
    #     """
    #     Returns a dictionary with the results sorted in a dictionary
    #     :return: dictionary of 2D numpy arrays (probably of complex numbers)
    #     """
    #     data = {
    #         'V': self.voltage.tolist(),
    #         'P': self.S.real.tolist(),
    #         'Q': self.S.imag.tolist(),
    #         'Sbr_real': self.Sf.real.tolist(),
    #         'Sbr_imag': self.Sf.imag.tolist(),
    #         'loading': np.abs(self.loading).tolist()
    #     }
    #     return data

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """
        Get ResultsModel instance
        :param result_type:
        :return: ResultsModel instance
        """
        # if self.time_array is not None:
        #     index = self.time_array
        # else:
        #     index = list(range(data.shape[0]))

        if result_type == ResultTypes.BusActivePower:

            return ResultsTable(
                data=self.S.real,
                index=self.time_array,
                idx_device_type=DeviceType.TimeDevice,
                columns=self.bus_names,
                cols_device_type=DeviceType.BusDevice,
                title=result_type.value,
                ylabel='(MW)',
                units='(MW)'
            )

        elif result_type == ResultTypes.BusVoltageModule:

            return ResultsTable(
                data=np.abs(self.voltage),
                index=self.time_array,
                idx_device_type=DeviceType.TimeDevice,
                columns=self.bus_names,
                cols_device_type=DeviceType.BusDevice,
                title=result_type.value,
                ylabel='(p.u.)',
                units='(p.u.)'
            )

        elif result_type == ResultTypes.BranchActivePowerFrom:

            return ResultsTable(
                data=self.Sf.real,
                index=self.time_array,
                idx_device_type=DeviceType.TimeDevice,
                columns=self.branch_names,
                cols_device_type=DeviceType.BranchDevice,
                title=result_type.value,
                ylabel='(MW)',
                units='(MW)'
            )

        elif result_type == ResultTypes.BranchLoading:

            return ResultsTable(
                data=np.abs(self.loading) * 100,
                index=self.time_array,
                idx_device_type=DeviceType.TimeDevice,
                columns=self.branch_names,
                cols_device_type=DeviceType.BranchDevice,
                title=result_type.value,
                ylabel='(%)',
                units='(%)'
            )

        elif result_type == ResultTypes.BranchLosses:

            return ResultsTable(
                data=self.losses,
                index=self.time_array,
                idx_device_type=DeviceType.TimeDevice,
                columns=self.branch_names,
                cols_device_type=DeviceType.BranchDevice,
                title=result_type.value,
                ylabel='(MW)',
                units='(MW)'
            )

        else:
            raise Exception('Result type not understood:' + str(result_type))


