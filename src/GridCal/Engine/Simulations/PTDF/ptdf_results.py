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

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from GridCal.Engine.plot_config import LINEWIDTH
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults


class PTDFVariation:

    def __init__(self, name, n):
        """
        PTDF variation
        :param name: name of the variation
        :param n: number of buses
        """
        self.name = name

        self.dP = np.zeros(n)


class PTDFResults:

    def __init__(self, n_variations=0, n_br=0, br_names=()):
        """
        Number of variations
        :param n_variations:
        :param n_br: number of branches:
        """
        # number of variations
        self.n_variations = n_variations

        # number of branches
        self.n_br = n_br

        # names of the branches
        self.br_names = br_names

        # default power flow results
        self.default_pf_results = None

        # results of the variation
        self.pf_results = [None] * n_variations

        # definition of the variation
        self.variations = [None] * n_variations

        self.logger = list()

        self.sensitivity_matrix = None

        self.available_results = [ResultTypes.PTDFBranchesSensitivity]

    def add_results_at(self, i, results: PowerFlowResults, variation: PTDFVariation):
        """
        Add the results
        :param i: variation index
        :param results: PowerFlowResults instance
        :param variation: PTDFVariation instance
        :return: None
        """
        # store the results
        self.pf_results[i] = results
        self.variations[i] = variation

    def get_branch_sensitivity_at(self, i):
        """
        get Branch sensitivities
        :param i: variation index
        :return: array of sensitivities from -1 to 1
        """
        return 1.0 - self.pf_results[i].Sbranch.real / (self.default_pf_results.Sbranch.real + 1e-20)

    def get_var_names(self):
        """
        GEt variation names
        :return:
        """
        return [v.name for v in self.variations]

    def consolidate(self):
        """
        Consolidate results in matrix
        :return:
        """
        self.sensitivity_matrix = np.zeros((self.n_variations, self.n_br))

        for i in range(self.n_variations):
            self.sensitivity_matrix[i, :] = self.get_branch_sensitivity_at(i)

        return self.sensitivity_matrix

    def get_results_data_frame(self):
        """
        Get Pandas DataFrame with the results
        :return: pandas DataFrame
        """
        values = self.consolidate()
        var_names = self.get_var_names()
        df = pd.DataFrame(data=values.transpose(), index=self.br_names, columns=var_names).fillna(0)

        return df

    def plot(self, result_type: ResultTypes, ax=None, indices=None, names=None):
        """
        Plot the results.

        Arguments:

            **result_type**: ResultTypes

            **ax**: matplotlib axis

            **indices**: Indices f the array to plot (indices of the elements)

            **names**: Names of the elements

        Returns:

            DataFrame
        """

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        if indices is None and names is not None:
            indices = np.array(range(len(names)))

        if len(indices) > 0:
            labels = names[indices]

            if result_type == ResultTypes.PTDFBranchesSensitivity:
                y = self.sensitivity_matrix[:, indices].transpose()
                y_label = '(p.u.)'
                title = 'Branches sensitivity'

            else:
                n = len(labels)
                y = np.zeros(n)
                y_label = ''
                title = ''

            # plot
            df = pd.DataFrame(data=y, index=labels, columns=self.get_var_names())
            df.plot(ax=ax, legend=False, linewidth=LINEWIDTH)
            ax.set_ylabel(y_label)
            ax.set_title(title)

            return df

        else:
            return None