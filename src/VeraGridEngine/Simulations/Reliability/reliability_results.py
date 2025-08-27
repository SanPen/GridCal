# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import pandas as pd
from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.Simulations.results_template import ResultsTemplate
from VeraGridEngine.basic_structures import DateVec, IntVec, Vec
from VeraGridEngine.enumerations import StudyResultsType, ResultTypes, DeviceType


class ReliabilityResults(ResultsTemplate):

    def __init__(self, nsim: int):
        """
        Clustering Results constructor
        """
        ResultsTemplate.__init__(
            self,
            name='Clustering Analysis',
            available_results=[
                ResultTypes.ReliabilityLoleResults
            ],
            clustering_results=None,
            time_array=None,
            study_results_type=StudyResultsType.Clustering
        )

        self.lole_evolution = np.zeros(nsim)

        self.register(name='lole_evolution', tpe=Vec)

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """
        Plot the results.
        :param result_type: ResultTypes
        :return: ResultsModel
        """

        if result_type == ResultTypes.ReliabilityLoleResults:

            return ResultsTable(data=self.lole_evolution,
                                index=np.arange(len(self.lole_evolution), dtype=int),
                                columns=np.array(['LOLE']),
                                title=result_type.value,
                                units="MWh",
                                idx_device_type=DeviceType.NoDevice,
                                cols_device_type=DeviceType.NoDevice)

        else:
            raise Exception('Result type not understood:' + str(result_type))
