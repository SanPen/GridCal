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

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults
from GridCal.Engine.Simulations.results_model import ResultsModel


class PTDFVariation:

    def __init__(self, name, n, original_power):
        """
        PTDF variation
        :param name: name of the variation
        :param n: number of buses
        :param original_power: power failed in MW
        """
        self.name = name

        # vector that was actually subtracted to Sbus
        self.dP = np.zeros(n)

        # original amount of power failed
        self.original_power = original_power


class PTDFResults:

    def __init__(self, n_variations=0, n_br=0, n_bus=0, br_names=(), bus_names=(), bus_types=()):
        """
        Number of variations
        :param n_variations:
        :param n_br: number of branches:
        """

        self.name = 'PTDF'

        # number of variations
        self.n_variations = n_variations

        # number of branches
        self.n_br = n_br

        self.n_bus = n_bus

        # names of the branches
        self.br_names = br_names

        self.bus_names = bus_names

        self.bus_types = bus_types

        # default power flow results
        self.default_pf_results = None

        # results of the variation
        self.pf_results = [None] * n_variations  # type: List[PowerFlowResults]

        # definition of the variation
        self.variations = [None] * n_variations  # type: List[PTDFVariation]

        self.logger = Logger()

        self.flows_sensitivity_matrix = None
        self.voltage_sensitivity_matrix = None

        self.available_results = [ResultTypes.PTDFBranchesSensitivity,
                                  ResultTypes.PTDFBusVoltageSensitivity]

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
        delta = (self.pf_results[i].Sf.real - self.default_pf_results.Sf.real)
        # self.variations[i].original_power is the power increment
        return delta / (self.variations[i].original_power + 1e-20)

    def get_voltage_sensitivity_at(self, i):
        """
        get Branch sensitivities
        :param i: variation index
        :return: array of sensitivities from -1 to 1
        """
        v0 = np.abs(self.default_pf_results.voltage)
        delta = (np.abs(self.pf_results[i].voltage) - v0)
        return delta / (self.variations[i].original_power + 1e-20)

    def get_var_names(self):
        """
        Get variation names
        :return:
        """
        return [v.name for v in self.variations]

    def consolidate(self):
        """
        Consolidate results in matrix
        :return:
        """
        self.flows_sensitivity_matrix = np.zeros((self.n_variations, self.n_br))
        for i in range(self.n_variations):
            self.flows_sensitivity_matrix[i, :] = self.get_branch_sensitivity_at(i)

        self.voltage_sensitivity_matrix = np.zeros((self.n_variations, self.n_bus))
        for i in range(self.n_variations):
            self.voltage_sensitivity_matrix[i, :] = self.get_voltage_sensitivity_at(i)

    def get_flows_data_frame(self):
        """
        Get Pandas DataFrame with the results
        :return: pandas DataFrame
        """

        if self.flows_sensitivity_matrix is None:
            self.consolidate()

        var_names = self.get_var_names()
        df = pd.DataFrame(data=self.flows_sensitivity_matrix.T, index=self.br_names, columns=var_names).fillna(0)

        return df

    def mdl(self, result_type: ResultTypes) -> ResultsModel:
        """
        Plot the results.

        Arguments:

            **result_type**: ResultTypes

            **indices**: Indices f the array to plot (indices of the elements)

            **names**: Names of the elements

        Returns:

            DataFrame
        """

        if result_type == ResultTypes.PTDFBranchesSensitivity:
            labels = self.br_names
            y = self.flows_sensitivity_matrix
            y_label = '(p.u.)'
            title = 'Branches sensitivity'

        elif result_type == ResultTypes.PTDFBusVoltageSensitivity:
            labels = self.bus_names
            y = self.voltage_sensitivity_matrix
            y_label = '(p.u.)'
            title = 'Buses voltage sensitivity'

        else:
            labels = []
            y = np.zeros(0)
            y_label = ''
            title = ''

        # assemble model
        mdl = ResultsModel(data=y, index=self.get_var_names(), columns=labels, title=title,
                           ylabel=y_label, units=y_label)
        return mdl
