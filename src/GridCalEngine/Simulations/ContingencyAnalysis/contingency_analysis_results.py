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

import numpy as np
from GridCalEngine.Core.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Simulations.result_types import ResultTypes
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.Simulations.ContingencyAnalysis.contingencies_report import ContingencyResultsReport
from GridCalEngine.basic_structures import IntVec, StrVec, CxMat
from GridCalEngine.enumerations import StudyResultsType


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
                ResultTypes.ContingencyAnalysisReport
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

        self.report: ContingencyResultsReport = ContingencyResultsReport()

        self.register(name='branch_names', tpe=StrVec)
        self.register(name='bus_names', tpe=StrVec)
        self.register(name='con_names', tpe=StrVec)
        self.register(name='bus_types', tpe=IntVec)

        self.register(name='voltage', tpe=CxMat)
        self.register(name='Sbus', tpe=CxMat)
        self.register(name='Sf', tpe=CxMat)
        self.register(name='loading', tpe=CxMat)

        self.register(name='report', tpe=ContingencyResultsReport)

    def apply_new_rates(self, nc: NumericalCircuit):
        """
        Apply new rates
        :param nc: NumericalCircuit
        """
        rates = nc.Rates
        self.loading = self.Sf / (rates + 1e-9)

    def get_steps(self):
        return list()

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {
            'Vm': np.abs(self.voltage).tolist(),
            'Va': np.angle(self.voltage).tolist(),
            'P': self.Sbus.real.tolist(),
            'Q': self.Sbus.imag.tolist(),
            'Sbr_real': self.Sf.real.tolist(),
            'Sbr_imag': self.Sf.imag.tolist(),
            'loading': np.abs(self.loading).tolist()
        }
        return data

    def mdl(self, result_type: ResultTypes):
        """
        Plot the results
        :param result_type:
        :return:
        """

        index = ['# ' + x for x in self.con_names]

        if result_type == ResultTypes.BusVoltageModule:
            data = np.abs(self.voltage)
            y_label = '(p.u.)'
            title = 'Bus voltage '
            labels = self.bus_names
            # index = self.branch_names

        elif result_type == ResultTypes.BusVoltageAngle:
            data = np.angle(self.voltage, deg=True)
            y_label = '(Deg)'
            title = 'Bus voltage '
            labels = self.bus_names
            # index = self.branch_names

        elif result_type == ResultTypes.BusActivePower:
            data = self.Sbus.real
            y_label = '(MW)'
            title = 'Bus active power '
            labels = self.bus_names
            # index = self.branch_names

        elif result_type == ResultTypes.BranchActivePowerFrom:
            data = self.Sf.real
            y_label = 'MW'
            title = 'Branch active power '
            labels = self.branch_names
            # index = self.branch_names

        elif result_type == ResultTypes.BranchLoading:
            data = self.loading.real * 100
            y_label = '(%)'
            title = 'Branch loading '
            labels = self.branch_names
            # index = self.branch_names

        elif result_type == ResultTypes.ContingencyAnalysisReport:
            data = self.report.get_data()
            y_label = ''
            title = result_type.value[0]
            labels = self.report.get_headers()
            index = self.report.get_index()

        else:
            raise Exception('Result type not understood:' + str(result_type))

        # assemble model
        mdl = ResultsTable(
            data=data,
            index=index,
            columns=labels,
            title=title,
            ylabel=y_label
        )

        return mdl
