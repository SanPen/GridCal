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
from GridCal.Engine.Simulations.driver_template import DriverTemplate
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.results_template import ResultsTemplate
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_table import ResultsTable
from GridCal.Engine.Core.Devices.multi_circuit import MultiCircuit
from GridCal.Engine.basic_structures import Vec


class InvestmentsEvaluationResults(ResultsTemplate):
    tpe = 'Investments Evaluation Results'

    def __init__(self, grid: MultiCircuit):
        """
        Construct the analysis
        :param grid: MultiCircuit
        """
        available_results = {
                             ResultTypes.ReportsResults: [ResultTypes.InvestmentsReportResults, ]
                            }

        ResultsTemplate.__init__(self,
                                 name='Investments Evaluation',
                                 available_results=available_results,
                                 data_variables=[])

        self.grid = grid
        self.n_groups = len(grid.investments_groups)

        self._capex: Vec = np.zeros(self.n_groups, dtype=float)
        self._opex: Vec = np.zeros(self.n_groups, dtype=float)
        self._losses: Vec = np.zeros(self.n_groups, dtype=float)
        self._f_obj: Vec = np.zeros(self.n_groups, dtype=float)

    def set_at(self, i, capex, opex, losses, objective_function):
        """
        Set the results at an investment group
        :param i: investment group index
        :param capex:
        :param opex:
        :param losses:
        :param objective_function:
        :return:
        """
        self._capex[i] = capex
        self._opex[i] = opex
        self._losses[i] = losses
        self._f_obj[i] = objective_function

    def mdl(self, result_type) -> "ResultsTable":
        """
        Plot the results
        :param result_type: type of results (string)
        :return: DataFrame of the results
                (or None if the result was not understood)
        """

        if result_type == ResultTypes.InvestmentsReportResults:
            labels = self.grid.get_investment_groups_names()
            columns = ["CAPEX (M€)", "OPEX (M€/yr)", "Losses (MW)", "Objective function"]
            y = np.c_[self._capex,
                      self._opex,
                      self._losses,
                      self._f_obj]
            y_label = ''
            title = ''

        else:
            columns = []
            labels = []
            y = np.zeros(0)
            y_label = '(MW)'
            title = ''

        mdl = ResultsTable(data=y,
                           index=np.array(labels),
                           columns=np.array(columns),
                           title=title,
                           ylabel=y_label,
                           xlabel='',
                           units=y_label)
        return mdl

