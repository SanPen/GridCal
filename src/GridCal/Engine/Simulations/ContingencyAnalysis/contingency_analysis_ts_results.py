# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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

import json
import numpy as np
import pandas as pd
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_table import ResultsTable
from GridCal.Engine.Simulations.results_template import ResultsTemplate


class ContingencyAnalysisTimeSeriesResults(ResultsTemplate):

    def __init__(self, n, ne, nc, time_array, bus_names, branch_names, bus_types):
        """
        TimeSeriesResults constructor
        @param n: number of buses
        @param m: number of branches
        """
        ResultsTemplate.__init__(self,
                                 name='N-1 time series',
                                 available_results=[ResultTypes.ContingencyFrequency,
                                                    ResultTypes.ContingencyRelativeFrequency,
                                                    ResultTypes.MaxOverloads,
                                                    ResultTypes.WorstContingencyFlows,
                                                    ResultTypes.WorstContingencyLoading],
                                 data_variables=['branch_names',
                                                 'bus_names',
                                                 'bus_types',
                                                 'time_array',
                                                 'worst_flows',
                                                 'worst_loading',
                                                 'overload_count',
                                                 'relative_frequency',
                                                 'max_overload'])

        nt = len(time_array)

        self.branch_names = branch_names

        self.bus_names = bus_names

        self.bus_types = bus_types

        self.time_array = time_array

        self.S = np.zeros((nt, n))

        self.worst_flows = np.zeros((nt, ne))

        self.worst_loading = np.zeros((nt, ne))

        self.overload_count = np.zeros((ne, nc), dtype=int)

        self.relative_frequency = np.zeros((ne, nc))

        self.max_overload = np.zeros((ne, nc))

    def apply_new_time_series_rates(self, nc: "TimeCircuit"):
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

        index = self.branch_names

        if result_type == ResultTypes.ContingencyFrequency:
            data = self.overload_count
            y_label = '(#)'
            title = 'Contingency count '
            labels = ['#' + x for x in self.branch_names]

        elif result_type == ResultTypes.ContingencyRelativeFrequency:
            data = self.relative_frequency
            y_label = '(p.u.)'
            title = 'Contingency relative frequency '
            labels = ['#' + x for x in self.branch_names]

        elif result_type == ResultTypes.MaxOverloads:
            data = self.max_overload
            y_label = '(#)'
            title = 'Contingency count '
            labels = ['#' + x for x in self.branch_names]

        elif result_type == ResultTypes.WorstContingencyFlows:
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

        else:
            raise Exception('Result type not understood:' + str(result_type))

        # assemble model
        mdl = ResultsTable(data=data,
                           index=index,
                           columns=labels,
                           title=title,
                           ylabel=y_label)
        return mdl

