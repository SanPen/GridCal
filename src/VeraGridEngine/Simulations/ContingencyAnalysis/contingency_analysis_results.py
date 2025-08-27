# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


import numpy as np
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.Simulations.results_template import ResultsTemplate
from VeraGridEngine.Simulations.ContingencyAnalysis.contingencies_report import ContingencyResultsReport
from VeraGridEngine.basic_structures import IntVec, StrVec, CxMat, Mat
from VeraGridEngine.enumerations import StudyResultsType, ResultTypes, DeviceType


class ContingencyAnalysisResults(ResultsTemplate):
    """
    Contingency analysis results
    """

    def __init__(self, ncon: int, nbus: int, nbr: int,
                 bus_names: StrVec, branch_names: StrVec, bus_types: IntVec, con_names: StrVec):
        """
        ContingencyAnalysisResults
        :param ncon: number of contingencies
        :param nbus: number of buses
        :param nbr: number of Branches
        :param bus_names: bus names
        :param branch_names: branch names
        :param bus_types: bus types array
        :param con_names: contingency names
        """
        ResultsTemplate.__init__(
            self,
            name='Contingency Analysis Results',
            available_results=[
                ResultTypes.BusActivePower,
                ResultTypes.BranchActivePowerFrom,
                ResultTypes.BranchLoading,
                ResultTypes.ContingencyAnalysisReport,
                ResultTypes.SrapUsedPower

            ],
            time_array=None,
            clustering_results=None,
            study_results_type=StudyResultsType.ContingencyAnalysis
        )

        self.branch_names = branch_names
        self.bus_names = bus_names
        self.bus_types = bus_types
        self.con_names = con_names

        self.voltage: CxMat = np.ones((ncon, nbus), dtype=complex)
        self.Sbus: CxMat = np.zeros((ncon, nbus), dtype=complex)
        self.Sf: CxMat = np.zeros((ncon, nbr), dtype=complex)
        self.loading: CxMat = np.zeros((ncon, nbr), dtype=complex)
        self.srap_used_power = np.zeros((nbr, nbus), dtype=float)

        self.report: ContingencyResultsReport = ContingencyResultsReport()

        self.register(name='branch_names', tpe=StrVec)
        self.register(name='bus_names', tpe=StrVec)
        self.register(name='con_names', tpe=StrVec)
        self.register(name='bus_types', tpe=IntVec)

        self.register(name='voltage', tpe=CxMat)
        self.register(name='Sbus', tpe=CxMat)
        self.register(name='Sf', tpe=CxMat)
        self.register(name='loading', tpe=CxMat)
        self.register(name='srap_used_power', tpe=Mat)

        self.register(name='report', tpe=ContingencyResultsReport)

    def apply_new_rates(self, nc: NumericalCircuit):
        """
        Apply new rates
        :param nc: NumericalCircuit
        """
        rates = nc.Rates
        self.loading = self.Sf / (rates + 1e-9)

    @staticmethod
    def get_steps():
        """
        Get the simulation steps
        :return:
        """
        return list()

    # def get_dict(self):
    #     """
    #     Returns a dictionary with the results sorted in a dictionary
    #     :return: dictionary of 2D numpy arrays (probably of complex numbers)
    #     """
    #     data = {
    #         'Vm': np.abs(self.voltage).tolist(),
    #         'Va': np.angle(self.voltage).tolist(),
    #         'P': self.Sbus.real.tolist(),
    #         'Q': self.Sbus.imag.tolist(),
    #         'Sbr_real': self.Sf.real.tolist(),
    #         'Sbr_imag': self.Sf.imag.tolist(),
    #         'loading': np.abs(self.loading).tolist()
    #     }
    #     return data

    def mdl(self, result_type: ResultTypes):
        """
        Plot the results
        :param result_type:
        :return:
        """

        index = ['# ' + x for x in self.con_names]

        if result_type == ResultTypes.BusVoltageModule:

            return ResultsTable(
                data=np.abs(self.voltage),
                index=index,
                columns=self.bus_names,
                title=result_type.value,
                units='(p.u.)',
                cols_device_type=DeviceType.ContingencyDevice,
                idx_device_type=DeviceType.BusDevice
            )

        elif result_type == ResultTypes.BusVoltageAngle:

            return ResultsTable(
                data=np.angle(self.voltage, deg=True),
                index=index,
                columns=self.bus_names,
                title=result_type.value,
                units='(deg)',
                cols_device_type=DeviceType.ContingencyDevice,
                idx_device_type=DeviceType.BusDevice
            )

        elif result_type == ResultTypes.BusActivePower:

            return ResultsTable(
                data=self.Sbus.real,
                index=index,
                columns=self.bus_names,
                title=result_type.value,
                units='(MW)',
                cols_device_type=DeviceType.ContingencyDevice,
                idx_device_type=DeviceType.BusDevice
            )

        elif result_type == ResultTypes.BranchActivePowerFrom:

            return ResultsTable(
                data=self.Sf.real,
                index=index,
                columns=self.branch_names,
                title=result_type.value,
                units='(MW)',
                cols_device_type=DeviceType.ContingencyDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.BranchLoading:

            return ResultsTable(
                data=self.loading.real * 100,
                index=index,
                columns=self.branch_names,
                title=result_type.value,
                units='(%)',
                cols_device_type=DeviceType.ContingencyDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.SrapUsedPower:

            return ResultsTable(
                data=self.srap_used_power,
                index=self.branch_names,
                columns=self.bus_names,
                title=result_type.value,
                units="(MW)",
                cols_device_type=DeviceType.BusDevice,
                idx_device_type=DeviceType.BranchDevice
            )

        elif result_type == ResultTypes.ContingencyAnalysisReport:

            return ResultsTable(
                data=self.report.get_data(),
                index=self.report.get_index(),
                columns=self.report.get_headers(),
                title=result_type.value,
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.NoDevice
            )

        else:
            raise Exception('Result type not understood:' + str(result_type))
