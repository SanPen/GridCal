# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import pandas as pd
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.basic_structures import DateVec, IntVec, Vec
from GridCalEngine.enumerations import StudyResultsType, ResultTypes, DeviceType


class ClusteringResults(ResultsTemplate):

    def __init__(self,
                 time_indices: IntVec,
                 sampled_probabilities: Vec,
                 time_array: DateVec,
                 original_sample_idx: IntVec):
        """
        Clustering Results constructor
        :param time_indices: array of reduced time indices matching the number of samples
        :param sampled_probabilities: array of probabilities of each sample
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
