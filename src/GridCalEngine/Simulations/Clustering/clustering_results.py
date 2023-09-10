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
from GridCalEngine.basic_structures import DateVec, IntVec, StrVec, Vec, Mat, CxVec, IntMat, CxMat


class ClusteringResults(ResultsTemplate):

    def __init__(self, time_indices: IntVec, sampled_probabilities: Vec, time_array: DateVec, original_sample_idx: IntVec):
        """
        Clustering Results constructor
        :param time_indices: number of Branches
        :param sampled_probabilities: number of buses
        :param time_array: Array of time values (all of them, because this array is sliced with time_indices)
        :param original_sample_idx: Array signifying to which cluster does each original value belong (same size as time_array)
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
                'time_array',
                'original_sample_idx'
            ],
            clustering_results=None,
            time_array=time_array
        )

        self.time_indices = time_indices

        self.sampled_probabilities = sampled_probabilities

        # self.time_array = time_array
        self.original_sample_idx = original_sample_idx

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
            index = np.array([])
            labels = np.array([])
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

