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
from matplotlib import pyplot as plt
import matplotlib.colors as plt_colors
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.basic_structures import IntVec, Vec, StrVec
from GridCalEngine.enumerations import StudyResultsType, ResultTypes, DeviceType


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
            ResultTypes.SpecialPlots: [ResultTypes.InvestmentsParetoPlot1,
                                       ResultTypes.InvestmentsParetoPlot2,
                                       ResultTypes.InvestmentsParetoPlot3,
                                       ResultTypes.InvestmentsParetoPlot4,
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
        self._electrical: Vec = np.zeros(max_eval, dtype=float)
        self._financial: Vec = np.zeros(max_eval, dtype=float)
        self._f_obj: Vec = np.zeros(max_eval, dtype=float)
        self._index_names: Vec = np.zeros(max_eval, dtype=object)
        self._best_combination: IntVec = np.zeros(max_eval, dtype=int)

        self.register(name='investment_groups_names', tpe=StrVec)
        self.register(name='_combinations', tpe=Vec)
        self.register(name='_capex', tpe=Vec)
        self.register(name='_opex', tpe=Vec)
        self.register(name='_losses', tpe=Vec)
        self.register(name='_overload_score', tpe=Vec)
        self.register(name='_voltage_score', tpe=Vec)
        self.register(name='_electrical', tpe=Vec)
        self.register(name='_financial', tpe=Vec)
        self.register(name='_f_obj', tpe=Vec)
        self.register(name='_index_names', tpe=Vec)
        self.register(name='_best_combination', tpe=IntVec)

        self.__eval_index: int = 0

    @property
    def current_evaluation(self) -> int:
        return self.__eval_index

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

    def set_at(self, eval_idx,
               capex: float,
               opex: float,
               losses: float,
               overload_score: float,
               voltage_score: float,
               # electrical: float,
               financial: float,
               objective_function_sum: float,
               combination: IntVec,
               index_name: str) -> None:
        """
        Set the results at an investment group
        :param eval_idx: evaluation index
        :param capex:
        :param opex:
        :param losses:
        :param overload_score:
        :param voltage_score:
        # :param electrical:
        :param financial:
        :param objective_function_sum:
        :param combination: vector of size (n_investment_groups) with ones in those investments used
        :param index_name: Name of the evaluation
        """
        self._capex[eval_idx] = capex
        self._opex[eval_idx] = opex
        self._losses[eval_idx] = losses
        self._overload_score[eval_idx] = overload_score
        self._voltage_score[eval_idx] = voltage_score
        # self._electrical[eval_idx] = electrical
        self._financial[eval_idx] = financial
        self._f_obj[eval_idx] = objective_function_sum
        self._combinations[eval_idx, :] = combination
        self._index_names[eval_idx] = index_name

    def add(self,
            capex: float,
            opex: float,
            losses: float,
            overload_score: float,
            voltage_score: float,
            # electrical: float,
            financial: float,
            objective_function_sum: float,
            combination: IntVec) -> None:
        """

        :param capex:
        :param opex:
        :param losses:
        :param overload_score:
        :param voltage_score:
        :param electrical:
        :param financial:
        :param objective_function_sum:
        :param combination:
        :return:
        """
        if self.__eval_index < self.max_eval:
            self.set_at(eval_idx=self.__eval_index,
                        capex=capex,
                        opex=opex,
                        losses=losses,
                        overload_score=overload_score,
                        voltage_score=voltage_score,
                        # electrical=electrical,
                        financial=financial,
                        objective_function_sum=objective_function_sum,
                        combination=combination,
                        index_name=f'Solution {self.__eval_index}')

            self.__eval_index += 1
        else:
            print('Evaluation index out of range')

    def set_best_combination(self, combination: IntVec) -> None:
        """
        Set the best combination of investment groups
        :param combination: Vector of integers (0/1)
        """
        self._best_combination = combination

    @property
    def best_combination(self) -> IntVec:
        return self._best_combination

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
                       "OPEX (M€)",
                       "Losses (MW)",
                       "Overload cost (M€)",
                       "Voltage cost (M€)",
                       # "Total technical score (M€)",
                       "Total financial score (M€)",
                       "Objective function"] + list(self.investment_groups_names)
            data = np.c_[
                self._capex,
                self._opex,
                self._losses,
                self._overload_score / 1e6,
                self._voltage_score / 1e6,
                # self._electrical,
                self._financial,
                self._f_obj,
                self._combinations
            ]
            y_label = ''
            title = ''

            return ResultsTable(data=data,
                                index=np.array(labels),
                                idx_device_type=DeviceType.NoDevice,
                                columns=np.array(columns),
                                cols_device_type=DeviceType.NoDevice.NoDevice,
                                title=title,
                                ylabel=y_label,
                                xlabel='',
                                units=y_label)

        elif result_type == ResultTypes.InvestmentsParetoPlot1:
            labels = self._index_names
            # columns = ["Investment cost (M€)", "Technical cost (M€)"]
            columns = ["Investment cost (M€)", "Losses (M€)"]
            data = np.c_[self._financial, self._losses]
            y_label = ''
            title = ''

            plt.ion()
            color_norm = plt_colors.Normalize()
            fig = plt.figure(figsize=(8, 6))
            ax3 = plt.subplot(1, 1, 1)
            sc3 = ax3.scatter(self._financial, self._losses, c=self._f_obj, norm=color_norm)
            ax3.set_xlabel('Investment cost (M€)')
            ax3.set_ylabel('Losses cost (M€)')
            plt.colorbar(sc3, fraction=0.05, label='Objective function')
            fig.suptitle(result_type.value)
            plt.tight_layout()
            plt.show()

            return ResultsTable(data=data,
                                index=np.array(labels),
                                idx_device_type=DeviceType.NoDevice,
                                columns=np.array(columns),
                                cols_device_type=DeviceType.NoDevice.NoDevice,
                                title=title,
                                ylabel=y_label,
                                xlabel='',
                                units=y_label)

        elif result_type == ResultTypes.InvestmentsParetoPlot2:
            labels = self._index_names
            # columns = ["Investment cost (M€)", "Technical cost (M€)"]
            columns = ["Investment cost (M€)", "Overload cost (M€)"]
            data = np.c_[self._financial, self._overload_score]
            y_label = ''
            title = ''

            plt.ion()
            color_norm = plt_colors.Normalize()
            fig = plt.figure(figsize=(8, 6))
            ax3 = plt.subplot(1, 1, 1)
            sc3 = ax3.scatter(self._financial, self._overload_score, c=self._f_obj, norm=color_norm)
            ax3.set_xlabel('Investment cost (M€)')
            ax3.set_ylabel('Overload cost (M€)')
            plt.colorbar(sc3, fraction=0.05, label='Objective function')
            fig.suptitle(result_type.value)
            plt.tight_layout()
            plt.show()

            return ResultsTable(data=data,
                                index=np.array(labels),
                                idx_device_type=DeviceType.NoDevice,
                                columns=np.array(columns),
                                cols_device_type=DeviceType.NoDevice.NoDevice,
                                title=title,
                                ylabel=y_label,
                                xlabel='',
                                units=y_label)

        elif result_type == ResultTypes.InvestmentsParetoPlot3:
            labels = self._index_names
            # columns = ["Investment cost (M€)", "Technical cost (M€)"]
            columns = ["Investment cost (M€)", "Voltage cost (M€)"]
            data = np.c_[self._financial, self._voltage_score]
            y_label = ''
            title = ''

            plt.ion()
            color_norm = plt_colors.Normalize()
            fig = plt.figure(figsize=(8, 6))
            ax3 = plt.subplot(1, 1, 1)
            sc3 = ax3.scatter(self._financial, self._voltage_score, c=self._f_obj, norm=color_norm)
            ax3.set_xlabel('Investment cost (M€)')
            ax3.set_ylabel('Voltage cost (M€)')
            plt.colorbar(sc3, fraction=0.05, label='Objective function')
            fig.suptitle(result_type.value)
            plt.tight_layout()
            plt.show()

            print(f"Result Type: {result_type}")
            print(f"Data shape: {data.shape}")
            print(f"Length of columns: {len(columns)}")
            print(f"Length of index: {len(labels)}")

            return ResultsTable(data=data,
                                index=np.array(labels),
                                idx_device_type=DeviceType.NoDevice,
                                columns=np.array(columns),
                                cols_device_type=DeviceType.NoDevice.NoDevice,
                                title=title,
                                ylabel=y_label,
                                xlabel='',
                                units=y_label)

        elif result_type == ResultTypes.InvestmentsParetoPlot4:
            labels = self._index_names
            # columns = ["Investment cost (M€)", "Technical cost (M€)"]
            columns = ["Investment cost (M€)", "Technical cost (M€)"]
            data = np.c_[self._financial, self._losses+self._voltage_score+self._overload_score]
            y_label = ''
            title = ''

            plt.ion()
            color_norm = plt_colors.Normalize()
            fig = plt.figure(figsize=(8, 6))
            ax3 = plt.subplot(1, 1, 1)
            sc3 = ax3.scatter(self._financial, self._losses+self._voltage_score+self._overload_score, c=self._f_obj, norm=color_norm)
            ax3.set_xlabel('Investment cost (M€)')
            ax3.set_ylabel('Technical cost (M€)')
            plt.colorbar(sc3, fraction=0.05, label='Objective function')
            fig.suptitle(result_type.value)
            plt.tight_layout()
            plt.show()

            return ResultsTable(data=data,
                                index=np.array(labels),
                                idx_device_type=DeviceType.NoDevice,
                                columns=np.array(columns),
                                cols_device_type=DeviceType.NoDevice.NoDevice,
                                title=title,
                                ylabel=y_label,
                                xlabel='',
                                units=y_label)

        elif result_type == ResultTypes.InvestmentsIterationsPlot:
            labels = self._index_names
            columns = ["Iteration", "Objective function"]
            x = np.arange(self.max_eval)
            y = self._f_obj
            data = np.c_[x, y]
            y_label = ''
            title = ''

            plt.ion()
            fig = plt.figure(figsize=(8, 6))
            ax3 = plt.subplot(1, 1, 1)
            ax3.plot(x, y, '.')
            ax3.set_xlabel('Iteration')
            ax3.set_ylabel('Objective')
            fig.suptitle(result_type.value)
            plt.grid()
            plt.show()

            return ResultsTable(data=data,
                                index=np.array(labels),
                                idx_device_type=DeviceType.NoDevice,
                                columns=np.array(columns),
                                cols_device_type=DeviceType.NoDevice.NoDevice,
                                title=title,
                                ylabel=y_label,
                                xlabel='',
                                units=y_label)

        else:
            raise Exception('Result type not understood:' + str(result_type))
