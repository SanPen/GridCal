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

import numpy as np
import pandas as pd
from typing import Union
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Simulations.ContingencyAnalysis.contingencies_report import ContingencyResultsReport
from GridCalEngine.basic_structures import DateVec, IntVec, StrVec, Mat
from GridCalEngine.enumerations import StudyResultsType, ResultTypes
from GridCalEngine.Simulations.Clustering.clustering_results import ClusteringResults


class ContingencyAnalysisTimeSeriesResults(ResultsTemplate):
    """
    Contingency analysis time series results
    """

    def __init__(self, n: int, nbr: int, nc: int,
                 time_array: DateVec,
                 bus_names: StrVec,
                 branch_names: StrVec,
                 bus_types: IntVec,
                 con_names: StrVec,
                 clustering_results: Union[ClusteringResults, None]):
        """
        ContingencyAnalysisTimeSeriesResults
        :param n: number of nodes
        :param nbr: number of branches
        :param nc: number of contingencies
        :param time_array: array of time values
        :param bus_names: rray of bus names
        :param branch_names: array of branch names
        :param bus_types: array of bus types
        :param con_names: array of contingency names
        :param clustering_results: Clustering results if applicable
        """

        ResultsTemplate.__init__(
            self,
            name='N-1 time series',
            available_results={
                ResultTypes.StatisticResults: [
                    ResultTypes.MaxContingencyFlows,
                    ResultTypes.MaxContingencyLoading,
                    ResultTypes.ContingencyOverloadSum,
                    ResultTypes.MeanContingencyOverLoading,
                    ResultTypes.StdDevContingencyOverLoading,
                    ResultTypes.SrapUsedPower,
                ],
                ResultTypes.ReportsResults: [
                    ResultTypes.ContingencyAnalysisReport,
                    ResultTypes.ContingencyStatisticalAnalysisReport
                ]
            },
            time_array=time_array,
            clustering_results=clustering_results,
            study_results_type=StudyResultsType.ContingencyAnalysisTimeSeries
        )

        self.nt = len(time_array)

        self.branch_names: StrVec = branch_names
        self.bus_names: StrVec = bus_names
        self.con_names: StrVec = con_names
        self.bus_types: IntVec = bus_types

        """
        Tabla de sobrecargas máximas (tiempo, rama)
        Tabla de desviación típica (tiempo, rama)
        Tabla de frecuencia de sobrecarga (tiempo, rama)
        Tabla de índices de la máxima sobrecarga (tiempo, rama)
        Tabla de suma de sobrecarga (tiempo, rama)
        """

        self.S: Mat = np.zeros((self.nt, n))

        self.max_flows: Mat = np.zeros((self.nt, nbr))

        self.max_loading: Mat = np.zeros((self.nt, nbr))

        self.overload_count: Mat = np.zeros((self.nt, nbr))

        self.sum_overload: Mat = np.zeros((self.nt, nbr))

        self.mean_overload: Mat = np.zeros((self.nt, nbr))

        self.std_dev_overload: Mat = np.zeros((self.nt, nbr))

        self.srap_used_power = np.zeros((nbr, n), dtype=float)

        self.report: ContingencyResultsReport = ContingencyResultsReport()

        self.register(name='branch_names', tpe=StrVec)
        self.register(name='bus_names', tpe=StrVec)
        self.register(name='bus_types', tpe=IntVec)
        self.register(name='con_names', tpe=StrVec)

        self.register(name='S', tpe=Mat)
        self.register(name='max_flows', tpe=Mat)
        self.register(name='max_loading', tpe=Mat)
        self.register(name='sum_overload', tpe=Mat)
        self.register(name='mean_overload', tpe=Mat)
        self.register(name='std_dev_overload', tpe=Mat)
        self.register(name='srap_used_power', tpe=Mat)
        self.register(name='report', tpe=ContingencyResultsReport)

    @property
    def nbus(self) -> int:
        """
        Number of buses
        """
        return len(self.bus_names)

    @property
    def nbranch(self) -> int:
        """
        Number of branches
        """
        return len(self.branch_names)

    @property
    def ncon(self) -> int:
        """
        Number of contingencies
        """
        return len(self.con_names)

    def apply_new_time_series_rates(self, nc: NumericalCircuit):
        """
        Apply new rates
        :param nc:
        :return:
        """
        rates = nc.Rates.T
        self.max_loading = self.max_flows / (rates + 1e-9)

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {
            # 'overload_count': self.overload_count.tolist(),
            # 'relative_frequency': self.relative_frequency.tolist(),
            # 'max_overload': self.max_overload.tolist(),
            'worst_flows': self.max_flows.tolist(),
            'worst_loading': self.max_loading.tolist(),
        }
        return data

    def mdl(self, result_type: ResultTypes):
        """
        Plot the results
        :param result_type:
        :return:
        """

        if result_type == ResultTypes.MaxContingencyFlows:
            data = self.max_flows
            y_label = '(MW)'
            title = 'Worst contingency Sf '
            labels = self.branch_names
            index = pd.to_datetime(self.time_array)

        elif result_type == ResultTypes.MaxContingencyLoading:
            data = self.max_loading * 100.0
            y_label = '(%)'
            title = 'Worst contingency loading '
            labels = self.branch_names
            index = pd.to_datetime(self.time_array)

        elif result_type == ResultTypes.ContingencyOverloadSum:
            data = self.sum_overload
            y_label = '(MW)'
            title = result_type.value[0]
            labels = self.branch_names
            index = pd.to_datetime(self.time_array)

        elif result_type == ResultTypes.MeanContingencyOverLoading:
            data = self.mean_overload * 100.0
            y_label = '(%)'
            title = result_type.value[0]
            labels = self.branch_names
            index = pd.to_datetime(self.time_array)

        elif result_type == ResultTypes.StdDevContingencyOverLoading:
            data = self.std_dev_overload * 100.0
            y_label = '(%)'
            title = result_type.value[0]
            labels = self.branch_names
            index = pd.to_datetime(self.time_array)

        elif result_type == ResultTypes.SrapUsedPower:
            data = self.srap_used_power
            y_label = ''
            title = result_type.value[0]
            labels = self.bus_names
            index = self.branch_names

        elif result_type == ResultTypes.ContingencyAnalysisReport:
            data = self.report.get_data()
            y_label = ''
            title = result_type.value[0]
            labels = self.report.get_headers()
            index = self.report.get_index()

        elif result_type == ResultTypes.ContingencyStatisticalAnalysisReport:
            df = self.report.get_summary_table()
            y_label = ''
            title = result_type.value[0]
            data = df.values
            labels = df.columns.tolist()
            index = df.index.tolist()
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
