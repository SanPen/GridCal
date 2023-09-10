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
from GridCalEngine.Simulations.result_types import ResultTypes
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Simulations.results_template import ResultsTemplate
import GridCalEngine.basic_structures as bs


class LinearAnalysisResults(ResultsTemplate):
    """

    """

    def __init__(self, n_br=0, n_bus=0, br_names=(), bus_names=(), bus_types=()):
        """
        PTDF and LODF results class
        :param n_br: number of Branches
        :param n_bus: number of buses
        :param br_names: branch names
        :param bus_names: bus names
        :param bus_types: bus types array
        """
        ResultsTemplate.__init__(self,
                                 name='Linear Analysis',
                                 available_results=[ResultTypes.PTDFBranchesSensitivity,
                                                    ResultTypes.LODF,
                                                    ResultTypes.BranchActivePowerFrom,
                                                    ResultTypes.BranchLoading],
                                 data_variables=['branch_names',
                                                 'bus_names',
                                                 'bus_types',
                                                 'PTDF',
                                                 'LODF',
                                                 'Sf',
                                                 'loading'],
                                 time_array=None,
                                 clustering_results=None)
        # number of Branches
        self.n_br = n_br

        self.n_bus = n_bus

        # names of the Branches
        self.branch_names = br_names

        self.bus_names = bus_names

        self.bus_types = bus_types

        self.logger = bs.Logger()

        self.PTDF = np.zeros((n_br, n_bus))
        self.LODF = np.zeros((n_br, n_br))

        self.Sf = np.zeros(self.n_br)

        self.Sbus = np.zeros(self.n_bus)

        self.voltage = np.ones(self.n_bus, dtype=complex)

        self.loading = np.zeros(self.n_br)

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """
        Plot the results.

        Arguments:

            **result_type**: ResultTypes

        Returns: ResultsModel
        """

        if result_type == ResultTypes.PTDFBranchesSensitivity:
            labels = self.bus_names
            y = self.PTDF
            y_label = '(p.u.)'
            title = 'Branches sensitivity'

        elif result_type == ResultTypes.LODF:
            labels = self.branch_names
            y = self.LODF
            y_label = '(p.u.)'
            title = 'Branch failure sensitivity'

        elif result_type == ResultTypes.BranchActivePowerFrom:
            title = 'Branch Sf'
            labels = [title]
            y = self.Sf
            y_label = '(MW)'

        elif result_type == ResultTypes.BranchLoading:
            title = 'Branch loading'
            labels = [title]
            y = self.loading * 100.0
            y_label = '(%)'

        else:
            labels = []
            y = np.zeros(0)
            y_label = ''
            title = ''

        # assemble model
        mdl = ResultsTable(data=y,
                           index=self.branch_names,
                           columns=labels,
                           title=title,
                           ylabel=y_label,
                           units=y_label)
        return mdl
