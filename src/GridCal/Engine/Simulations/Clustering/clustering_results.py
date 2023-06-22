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

import numpy as np
import pandas as pd
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_table import ResultsTable
from GridCal.Engine.Simulations.results_template import ResultsTemplate
from GridCal.Engine.basic_structures import DateVec, IntVec, StrVec, Vec, Mat, CxVec, IntMat, CxMat


class ClusteringResults(ResultsTemplate):

    def __init__(self, time_indices: IntVec, sampled_probabilities: Vec, time_array: DateVec):
        """
        Clustering Results constructor
        :param time_indices: number of branches
        :param sampled_probabilities: number of buses
        :param time_array: Array of time values (all of them, because this array is sliced with time_indices)
        """
        ResultsTemplate.__init__(
            self,
            name='Clustering Analysis',
            available_results=[
                ResultTypes.ClusteringReport
            ],
            data_variables=[
                'time_indices',
                'sampled_probabilities',
            ]
        )

        self.time_indices = time_indices
        self.sampled_probabilities = sampled_probabilities
        self.time_array = time_array

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """
        Plot the results.
        :param result_type: ResultTypes
        :return: ResultsModel
        """

        if result_type == ResultTypes.ClusteringReport:
            index = pd.to_datetime(self.time_array[self.time_indices])
            labels = ['Probability']
            y = np.array(self.sampled_probabilities)
            y_label = ''
            title = 'Clustering report'

        else:
            index = []
            labels = []
            y = np.zeros(0)
            y_label = ''
            title = ''

        # assemble model
        mdl = ResultsTable(data=y,
                           index=index,
                           columns=labels,
                           title=title,
                           ylabel=y_label,
                           units=y_label)

        return mdl

