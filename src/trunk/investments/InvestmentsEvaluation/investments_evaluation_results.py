# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from matplotlib import pyplot as plt
import matplotlib.colors as plt_colors
from VeraGridEngine.Simulations.results_template import ResultsTemplate
from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.basic_structures import IntVec, Vec, StrVec
from VeraGridEngine.enumerations import StudyResultsType, ResultTypes, DeviceType


class InvestmentsEvaluationResults(ResultsTemplate):
    tpe = 'Investments Evaluation Results'

    def __init__(self, investment_groups_names: StrVec, max_eval: int):
        """
        Construct the analysis
        :param investment_groups_names: List of investment groups names
        :param max_eval: maximum number of evaluations
        """
        available_results = {
            ResultTypes.ReportsResults: [ResultTypes.InvestmentsReportResults, ],
            ResultTypes.SpecialPlots: [ResultTypes.InvestmentsParetoPlot,
                                       ResultTypes.InvestmentsIterationsPlot]
        }

        ResultsTemplate.__init__(self,
                                 name='Investments Evaluation',
                                 available_results=available_results,
                                 time_array=None,
                                 clustering_results=None,
                                 study_results_type=StudyResultsType.InvestmentEvaluations)

        n_groups = len(investment_groups_names)

        self.investment_groups_names: StrVec = investment_groups_names
        self._combinations: IntVec = np.zeros((max_eval, n_groups), dtype=int)
        self._capex: Vec = np.zeros(max_eval, dtype=float)
        self._opex: Vec = np.zeros(max_eval, dtype=float)
        self._losses: Vec = np.zeros(max_eval, dtype=float)
        self._overload_score: Vec = np.zeros(max_eval, dtype=float)
        self._voltage_score: Vec = np.zeros(max_eval, dtype=float)
        self._f_obj: Vec = np.zeros(max_eval, dtype=float)
        self._index_names: Vec = np.zeros(max_eval, dtype=object)

        self.register(name='investment_groups_names', tpe=StrVec)
        self.register(name='_combinations', tpe=Vec)
        self.register(name='_capex', tpe=Vec)
        self.register(name='_opex', tpe=Vec)
        self.register(name='_losses', tpe=Vec)
        self.register(name='_overload_score', tpe=Vec)
        self.register(name='_voltage_score', tpe=Vec)
        self.register(name='_f_obj', tpe=Vec)
        self.register(name='_index_names', tpe=Vec)

    @property
    def n_groups(self) -> int:
        """

        :return:
        """
        return self._combinations.shape[1]

    @property
    def max_eval(self) -> int:
        """

        :return:
        """
        return self._combinations.shape[0]

    def get_index(self) -> StrVec:
        """
        Return index names
        """
        return self._index_names

    def set_at(self, eval_idx, capex, opex, losses, overload_score, voltage_score, objective_function,
               combination: IntVec, index_name) -> None:
        """
        Set the results at an investment group
        :param eval_idx: evaluation index
        :param capex:
        :param opex:
        :param losses:
        :param overload_score:
        :param voltage_score:
        :param objective_function:
        :param combination: vector of size (n_investment_groups) with ones in those investments used
        :param index_name: Name of the evaluation
        """
        self._capex[eval_idx] = capex
        self._opex[eval_idx] = opex
        self._losses[eval_idx] = losses
        self._overload_score[eval_idx] = overload_score
        self._voltage_score[eval_idx] = voltage_score
        self._f_obj[eval_idx] = objective_function
        self._combinations[eval_idx, :] = combination
        self._index_names[eval_idx] = index_name

    def mdl(self, result_type) -> "ResultsTable":
        """
        Plot the results
        :param result_type: type of results (string)
        :return: DataFrame of the results
                (or None if the result was not understood)
        """

        if result_type == ResultTypes.InvestmentsReportResults:
            labels = self._index_names
            columns = ["CAPEX (M€)",
                       "OPEX (M€/yr)",
                       "Losses (MW)",
                       "Overload cost (€)",
                       "Voltage deviations cost (€)",
                       "Objective function"] + list(self.investment_groups_names)
            data = np.c_[
                self._capex,
                self._opex,
                self._losses,
                self._overload_score,
                self._voltage_score,
                self._f_obj,
                self._combinations
            ]
            y_label = ''
            title = ''

        elif result_type == ResultTypes.InvestmentsParetoPlot:
            labels = self._index_names
            columns = ["CAPEX (M€) + OPEX (M€)", "Objective function"]
            x = self._capex + self._opex
            y = self._losses + self._overload_score + self._voltage_score
            z = self._f_obj

            color_norm = plt_colors.Normalize()

            data = np.c_[x, y]
            y_label = ''
            title = ''

            if self.plotting_allowed():
                # plt.ion()
                fig = plt.figure(figsize=(8, 6))
                ax3 = plt.subplot(1, 1, 1)
                sc3 = ax3.scatter(x, y, c=range(len(x)), norm=color_norm)
                ax3.set_xlabel('Investment cost (M€)')
                ax3.set_ylabel('Technical cost (M€)')
                plt.colorbar(sc3, fraction=0.05, label='Objective function')
                fig.suptitle(result_type.value[0])
                plt.tight_layout()
                # plt.show()

        elif result_type == ResultTypes.InvestmentsIterationsPlot:
            labels = self._index_names
            columns = ["CAPEX (M€) + OPEX (M€)", "Objective function"]
            x = np.arange(self.max_eval)
            y = self._f_obj
            data = np.c_[x, y]
            y_label = ''
            title = ''

            if self.plotting_allowed():
                plt.ion()
                fig = plt.figure(figsize=(8, 6))
                ax3 = plt.subplot(1, 1, 1)
                ax3.plot(x, y, '.')
                # plt.plot(iters, self.best_y[0:self.iter], 'r')
                ax3.set_xlabel('Iteration')
                ax3.set_ylabel('Objective')
                fig.suptitle(result_type.value[0])
                plt.grid()
                plt.show()

        else:
            columns = []
            labels = []
            data = np.zeros(0)
            y_label = '(MW)'
            title = ''

        mdl = ResultsTable(data=data,
                           index=np.array(labels),
                           columns=np.array(columns),
                           title=title,
                           cols_device_type=DeviceType.CircuitDevice,
                           idx_device_type=DeviceType.NoDevice,
                           ylabel=y_label,
                           xlabel='',
                           units=y_label)
        return mdl
