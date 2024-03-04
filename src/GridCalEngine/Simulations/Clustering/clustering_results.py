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
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.basic_structures import DateVec, IntVec, Vec
from GridCalEngine.enumerations import StudyResultsType, ResultTypes, DeviceType


class ClusteringResults(ResultsTemplate):

    def __init__(self, time_indices: IntVec, sampled_probabilities: Vec, time_array: DateVec,
                 original_sample_idx: IntVec):
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
            clustering_results=None,
            time_array=time_array,
            study_results_type=StudyResultsType.Clustering
        )

        self.time_indices = time_indices
        self.sampled_probabilities = sampled_probabilities
        self.original_sample_idx = original_sample_idx

        self.register(name='time_indices', tpe=IntVec)
        self.register(name='sampled_probabilities', tpe=Vec)
        self.register(name='original_sample_idx', tpe=IntVec)

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """
        Plot the results.
        :param result_type: ResultTypes
        :return: ResultsModel
        """

        if result_type == ResultTypes.ClusteringReport:

            return ResultsTable(data=np.array(self.sampled_probabilities),
                                index=pd.to_datetime(self.time_array[self.time_indices]),
                                columns=['Probability'],
                                title=result_type.value,
                                units="p.u.",
                                idx_device_type=DeviceType.TimeDevice,
                                cols_device_type=DeviceType.NoDevice)

        else:
            raise Exception('Result type not understood:' + str(result_type))
