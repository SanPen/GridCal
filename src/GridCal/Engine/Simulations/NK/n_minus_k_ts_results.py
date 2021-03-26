# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import json
import numpy as np
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_model import ResultsModel


class NMinusKTimeSeriesResults:

    def __init__(self, n, ne, nc, time_array, bus_names, branch_names, bus_types):
        """
        TimeSeriesResults constructor
        @param n: number of buses
        @param m: number of branches
        """

        self.name = 'N-1 time series'

        nt = len(time_array)

        self.bus_types = np.zeros(n, dtype=int)

        self.branch_names = branch_names

        self.bus_names = bus_names

        self.bus_types = bus_types

        self.time_array = time_array

        self.worst_flows = np.zeros((nt, ne))

        self.worst_loading = np.zeros((nt, ne))

        self.overload_count = np.zeros((ne, nc), dtype=int)

        self.relative_frequency = np.zeros((ne, nc))

        self.max_overload = np.zeros((ne, nc))

        self.available_results = [ResultTypes.ContingencyFrequency,
                                  ResultTypes.ContingencyRelativeFrequency,
                                  ResultTypes.MaxOverloads,
                                  ResultTypes.WorstContingencyFlows,
                                  ResultTypes.WorstContingencyLoading]

    def get_steps(self):
        return

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

    def save(self, fname):
        """
        Export as json
        """
        with open(fname, "w") as output_file:
            json_str = json.dumps(self.get_results_dict())
            output_file.write(json_str)

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
            title = 'Worst contingency flows '
            labels = self.branch_names
            index = self.time_array

        elif result_type == ResultTypes.WorstContingencyLoading:
            data = self.worst_loading * 100.0
            y_label = '(%)'
            title = 'Worst contingency loading '
            labels = self.branch_names
            index = self.time_array

        else:
            raise Exception('Result type not understood:' + str(result_type))

        # assemble model
        mdl = ResultsModel(data=data,
                           index=index,
                           columns=labels,
                           title=title,
                           ylabel=y_label)
        return mdl

