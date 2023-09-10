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
import pandas as pd
from GridCalEngine.Simulations.result_types import ResultTypes
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.Core.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Simulations.ContingencyAnalysis.contingencies_report import ContingencyResultsReport


class ContingencyAnalysisTimeSeriesResults(ResultsTemplate):
    """
    Contingency analysis time series results
    """

    def __init__(self, n, nbr, nc, time_array, bus_names, branch_names, bus_types, con_names, clustering_results):
        """
        ContingencyAnalysisTimeSeriesResults
        :param n: 
        :param nbr: 
        :param nc: 
        :param time_array: 
        :param bus_names: 
        :param branch_names: 
        :param bus_types: 
        :param con_names:
        :param clustering_results:
        """

        ResultsTemplate.__init__(
            self,
            name='N-1 time series',
            available_results=[
                # ResultTypes.ContingencyFrequency,
                # ResultTypes.ContingencyRelativeFrequency,
                # ResultTypes.MaxOverloads,
                ResultTypes.WorstContingencyFlows,
                ResultTypes.WorstContingencyLoading,
                ResultTypes.ContingencyAnalysisReport
            ],
            data_variables=[
                'branch_names',
                'bus_names',
                'bus_types',
                'time_array',
                'worst_flows',
                'worst_loading',
                'overload_count',
                'relative_frequency',
                'max_overload'
            ],
            time_array=time_array,
            clustering_results=clustering_results
        )

        nt = len(time_array)

        self.nbus = n
        self.nbranch = nbr
        self.ncon = nc

        self.branch_names = branch_names
        self.bus_names = bus_names
        self.con_names = con_names
        self.bus_types = bus_types

        # self.time_array = time_array

        self.S = np.zeros((nt, n))

        self.worst_flows = np.zeros((nt, nbr))
        self.worst_loading = np.zeros((nt, nbr))
        self.overload_count = np.zeros(nbr, dtype=int)

        self.relative_frequency = np.zeros(nbr)

        self.max_overload = np.zeros(nbr)

        self.report: ContingencyResultsReport = ContingencyResultsReport()

    def apply_new_time_series_rates(self, nc: NumericalCircuit):
        """
        Apply new rates
        :param nc:
        :return:
        """
        rates = nc.Rates.T
        self.worst_loading = self.worst_flows / (rates + 1e-9)

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {
            'overload_count': self.overload_count.tolist(),
            'relative_frequency': self.relative_frequency.tolist(),
            'max_overload': self.max_overload.tolist(),
            'worst_flows': self.worst_flows.tolist(),
            'worst_loading': self.worst_loading.tolist(),
        }
        return data

    def mdl(self, result_type: ResultTypes):
        """
        Plot the results
        :param result_type:
        :return:
        """

        # if result_type == ResultTypes.ContingencyFrequency:
        #     data = self.overload_count
        #     y_label = '(#)'
        #     title = 'Contingency count '
        #     labels = self.branch_names
        #     index = ['']
        #
        # elif result_type == ResultTypes.ContingencyRelativeFrequency:
        #     data = self.relative_frequency
        #     y_label = '(p.u.)'
        #     title = 'Contingency relative frequency '
        #     index = np.arange(0, len(data))
        #     labels = self.branch_names
        #
        # elif result_type == ResultTypes.MaxOverloads:
        #     data = self.max_overload
        #     y_label = '(#)'
        #     title = 'Maximum overloads '
        #     labels = self.branch_names
        #     index = np.arange(0, len(data))

        if result_type == ResultTypes.WorstContingencyFlows:
            data = self.worst_flows
            y_label = '(MW)'
            title = 'Worst contingency Sf '
            labels = self.branch_names
            index = pd.to_datetime(self.time_array)

        elif result_type == ResultTypes.WorstContingencyLoading:
            data = self.worst_loading * 100.0
            y_label = '(%)'
            title = 'Worst contingency loading '
            labels = self.branch_names
            index = pd.to_datetime(self.time_array)

        elif result_type == ResultTypes.ContingencyAnalysisReport:
            data = self.report.get_data()
            y_label = ''
            title = result_type.value
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
