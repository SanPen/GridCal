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
from GridCalEngine.basic_structures import IntVec, Vec, StrVec, Mat
from GridCalEngine.enumerations import StudyResultsType, ResultTypes, DeviceType
from GridCalEngine.Simulations.InvestmentsEvaluation.NumericalMethods.MVRSM_mo_pareto import non_dominated_sorting
from collections import Counter


class InvestmentsEvaluationResults(ResultsTemplate):
    tpe = 'Investments Evaluation Results'

    def __init__(self, investment_groups_names: StrVec, max_eval: int):
        """
        Construct the analysis
        :param investment_groups_names: List of investment groups names
        :param max_eval: maximum number of evaluations
        """
        available_results = {
            ResultTypes.ReportsResults: [ResultTypes.InvestmentsReportResults,
                                         ResultTypes.InvestmentsCombinationsResults,
                                         ResultTypes.InvestmentsObjectivesResults,
                                         ResultTypes.InvestmentsFrequencyResults],

            ResultTypes.ParetoResults: [ResultTypes.InvestmentsParetoReportResults,
                                        ResultTypes.InvestmentsParetoCombinationsResults,
                                        ResultTypes.InvestmentsParetoObjectivesResults,
                                        ResultTypes.InvestmentsParetoFrequencyResults],

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
        self._electrical: Vec = np.zeros(max_eval, dtype=float)
        self._financial: Vec = np.zeros(max_eval, dtype=float)
        self._f_obj: Vec = np.zeros(max_eval, dtype=float)
        self._index_names: Vec = np.zeros(max_eval, dtype=object)
        self._best_combination: IntVec = np.zeros(max_eval, dtype=int)

        self._sorting_indices: IntVec = np.zeros(0, dtype=int)

        self.overload_mag = []
        self.losses_mag = []
        self.voltage_mag = []

        self.overload_max_magnitude = None
        self.losses_majority_magnitude = None
        self.voltage_majority_magnitude = None
        self.calculate_magnitude(value=0)
        self.calculate_tech_score_magnitudes()

        self.losses_scale = None
        self.voltage_scale = None

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
        self.register(name='_sorting_indices', tpe=IntVec)

        self.__eval_index: int = 0

    @property
    def current_evaluation(self) -> int:
        """

        :return:
        """
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
               electrical: float,
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
        :param electrical:
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
        self._electrical[eval_idx] = electrical
        self._financial[eval_idx] = financial
        self._f_obj[eval_idx] = objective_function_sum
        self._combinations[eval_idx, :] = combination
        self._index_names[eval_idx] = index_name

    def scaling_factor_losses(self, overload_max_magnitude, losses_majority_magnitudes) -> float:
        """
        Calculate the scaling factor based on the difference in magnitude between overload and losses magnitudes.
        """
        losses_scale = None
        if losses_majority_magnitudes is not None:
            magnitude_diff_losses = overload_max_magnitude - losses_majority_magnitudes
            if magnitude_diff_losses >= 0:
                losses_scale = 10 ** magnitude_diff_losses
            else:
                losses_scale = 1.0 / (10 ** abs(magnitude_diff_losses))

        return losses_scale

    def scaling_factor_voltage(self, overload_max_magnitude, voltage_majority_magnitudes) -> float:
        """
        Calculate the scaling factor based on the difference in magnitude between overload and voltage magnitudes.
        """
        voltage_scale = None

        if voltage_majority_magnitudes is not None:
            magnitude_diff_voltage = overload_max_magnitude - voltage_majority_magnitudes - 1
            if magnitude_diff_voltage >= 0:
                voltage_scale = 10 ** magnitude_diff_voltage
            else:
                voltage_scale = 1.0 / (10 ** abs(magnitude_diff_voltage))

        return voltage_scale

    def calculate_tech_score_magnitudes(self):
        """
        Calculate the max magnitude of overload score and the magnitudes that appear most in losses and voltage scores
        """
        if self.overload_mag:
            self.overload_max_magnitude = max(self.overload_mag)
        else:
            self.overload_max_magnitude = None

        if self.losses_mag:
            losses_magnitude_counts = Counter(self.losses_mag)
            losses_max_count = max(losses_magnitude_counts.values())
            losses_majority_magnitudes = [magnitude for magnitude, count in losses_magnitude_counts.items() if
                                          count == losses_max_count]
            self.losses_majority_magnitude = max(losses_majority_magnitudes)
        else:
            self.losses_majority_magnitude = None

        if self.voltage_mag:
            voltage_magnitude_counts = Counter(self.voltage_mag)
            voltage_max_count = max(voltage_magnitude_counts.values())
            voltage_majority_magnitudes = [magnitude for magnitude, count in voltage_magnitude_counts.items() if
                                           count == voltage_max_count]
            self.voltage_majority_magnitude = max(voltage_majority_magnitudes)
        else:
            self.voltage_majority_magnitude = None

        return self.overload_max_magnitude, self.losses_majority_magnitude, self.voltage_majority_magnitude

    def calculate_magnitude(self, value):
        return int(np.floor(np.log10(np.abs(value)))) if value != 0 else 0

    def get_objectives(self) -> Mat:
        """
        Returns the multi-objectives matrix
        :return: Matrix (n_eval, n_dim)
        """
        return np.c_[
            self._capex,
            self._opex,
            self._losses,
            self._overload_score,
            self._voltage_score
        ]

    def get_pareto_indices(self) -> None:
        """
        Get and store the pareto sorting indices of the best front
        """
        _, _, self._sorting_indices = non_dominated_sorting(y_values=self.get_objectives(),
                                                            x_values=self._combinations)

    def add(self,
            capex: float,
            opex: float,
            losses: float,
            overload_score: float,
            voltage_score: float,
            electrical: float,
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
        self.overload_mag.append(self.calculate_magnitude(overload_score))
        self.losses_mag.append(self.calculate_magnitude(losses))
        self.voltage_mag.append(self.calculate_magnitude(voltage_score))

        if self.__eval_index < self.max_eval:
            self.set_at(eval_idx=self.__eval_index,
                        capex=capex,
                        opex=opex,
                        losses=losses,
                        overload_score=overload_score,
                        voltage_score=voltage_score,
                        electrical=electrical,
                        financial=financial,
                        objective_function_sum=objective_function_sum,
                        combination=combination,
                        index_name=f'Solution {self.__eval_index}')

            self.__eval_index += 1
        else:
            print('Evaluation index out of range')

    def trim(self):
        """
        Trim results to the last values
        :return:
        """
        if len(self._capex) > self.__eval_index:
            self._capex = self._capex[:self.__eval_index]
            self._opex = self._opex[:self.__eval_index]
            self._losses = self._losses[:self.__eval_index]
            self._overload_score = self._overload_score[:self.__eval_index]
            self._voltage_score = self._voltage_score[:self.__eval_index]
            self._financial = self._financial[:self.__eval_index]
            self._f_obj = self._f_obj[:self.__eval_index]
            self._combinations = self._combinations[:self.__eval_index]
            self._index_names = self._index_names[:self.__eval_index]

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

        if result_type in (ResultTypes.InvestmentsReportResults, ResultTypes.InvestmentsParetoReportResults):

            # compose the investment names
            used_investments = np.zeros(len(self._capex), dtype=object)
            for i in range(self._combinations.shape[0]):
                used_investments[i] = ""
                for j in range(self._combinations.shape[1]):
                    if self._combinations[i, j] > 0:
                        name = self.investment_groups_names[j]
                        used_investments[i] += f"{name},"

            columns = ["CAPEX (M€)",
                       "OPEX (M€)",
                       "Losses (MW)",
                       "Overload score",
                       "Voltage score",
                       "Total technical score",
                       "Total financial score (M€)",
                       "Combined objectives",
                       "Investments"]

            data = np.c_[
                self._capex,
                self._opex,
                self._losses,
                self._overload_score / 1e6,
                self._voltage_score / 1e6,
                self._electrical,
                #self._losses + self._voltage_score + self._overload_score,
                self._financial,
                self._f_obj,
                used_investments
            ]
            y_label = ''
            title = ''

            if result_type == ResultTypes.InvestmentsParetoReportResults:
                # slice results according to the pareto indices
                data = data[self._sorting_indices, :]
                index = self._index_names[self._sorting_indices]
            else:
                index = self._index_names

            return ResultsTable(data=data,
                                index=index,
                                idx_device_type=DeviceType.NoDevice,
                                columns=np.array(columns),
                                cols_device_type=DeviceType.NoDevice.NoDevice,
                                title=title,
                                ylabel=y_label,
                                xlabel='',
                                units=y_label)

        elif result_type in (ResultTypes.InvestmentsFrequencyResults, ResultTypes.InvestmentsParetoFrequencyResults):

            if result_type == ResultTypes.InvestmentsParetoFrequencyResults:
                # slice results according to the pareto indices
                freq = np.sum(self._combinations[self._sorting_indices, :], axis=0)
            else:
                freq = np.sum(self._combinations, axis=0)

            freq_rel = freq / freq.sum()
            data = np.c_[freq, freq_rel]

            return ResultsTable(data=data,
                                index=np.array(self.investment_groups_names),
                                idx_device_type=DeviceType.NoDevice,
                                columns=np.array(["Frequency", "Relative frequency"]),
                                cols_device_type=DeviceType.NoDevice.NoDevice,
                                title=str(result_type.value),
                                ylabel="",
                                xlabel="",
                                units="")

        elif result_type in (ResultTypes.InvestmentsCombinationsResults,
                             ResultTypes.InvestmentsParetoCombinationsResults):

            if result_type == ResultTypes.InvestmentsParetoCombinationsResults:
                # slice results according to the pareto indices
                data = self._combinations[self._sorting_indices, :]
                index = self._index_names[self._sorting_indices]
            else:
                data = self._combinations
                index = self._index_names

            return ResultsTable(data=data,
                                index=index,
                                idx_device_type=DeviceType.NoDevice,
                                columns=self.investment_groups_names,
                                cols_device_type=DeviceType.NoDevice.NoDevice,
                                title=str(result_type.value),
                                ylabel="",
                                xlabel="",
                                units="")

        elif result_type in (ResultTypes.InvestmentsObjectivesResults, ResultTypes.InvestmentsParetoObjectivesResults):

            data = np.c_[
                self._losses,
                self._overload_score,
                self._voltage_score,
                self._capex,
                self._opex,
                self._f_obj
            ]

            if result_type == ResultTypes.InvestmentsParetoObjectivesResults:
                # slice results according to the pareto indices
                data = data[self._sorting_indices, :]
                index = self._index_names[self._sorting_indices]
            else:
                index = self._index_names

            return ResultsTable(data=data,
                                index=index,
                                idx_device_type=DeviceType.NoDevice,
                                columns=np.array(["Losses (MW)",
                                                  "Overload score",
                                                  "Voltage score",
                                                  "CAPEX",
                                                  "OPEX",
                                                  "Combined objective"]),
                                cols_device_type=DeviceType.NoDevice.NoDevice,
                                title=str(result_type.value),
                                ylabel="",
                                xlabel="",
                                units="")

        elif result_type == ResultTypes.InvestmentsParetoPlot:
            labels = self._index_names

            # Scale losses and voltage scores to match overload score, creating smooth Pareto curve
            overload_score = np.sum(self._overload_score)
            if overload_score != 0:
                self.calculate_tech_score_magnitudes()
                self.losses_scale = self.scaling_factor_losses(self.overload_max_magnitude,
                                                               self.losses_majority_magnitude)
                self.voltage_scale = self.scaling_factor_voltage(self.overload_max_magnitude,
                                                                 self.voltage_majority_magnitude)
            else:
                self.losses_scale = 1.0
                self.voltage_scale = 1.0

            columns = ["Investment cost (M€)", "Technical cost (M€)", "Losses (M€)", "Overload cost (M€)",
                       "Voltage cost (M€)"]
            data = np.c_[
                self._financial,
                self._losses * self.losses_scale + self._voltage_score * self.voltage_scale + self._overload_score,
                self._losses,
                self._overload_score,
                self._voltage_score
            ]
            y_label = ''
            title = ''

            plt.ion()
            color_norm = plt_colors.Normalize()
            fig, ax3 = plt.subplots(2, 2, figsize=(16, 12))

            # Match magnitude of technical score with investment score
            technical_score = self._losses * self.losses_scale + self._voltage_score * self.voltage_scale + self._overload_score
            max_x_order_of_magnitude = self.calculate_magnitude(max(self._financial))
            max_y_order_of_magnitude = self.calculate_magnitude(
                max(self._losses * self.losses_scale + self._voltage_score * self.voltage_scale + self._overload_score))
            order_of_magnitude_difference = max_x_order_of_magnitude - max_y_order_of_magnitude
            scaled_technical_score = technical_score * 10 ** order_of_magnitude_difference

            # Plot 1: Technical vs investment
            sc1 = ax3[0, 0].scatter(self._financial, scaled_technical_score, c=self._f_obj, norm=color_norm)
            ax3[0, 0].set_xlabel('Investment cost (M€)', fontsize=10)
            ax3[0, 0].set_ylabel('Technical cost (M€)', fontsize=10)
            ax3[0, 0].set_title('Technical vs investment', fontsize=12)
            ax3[0, 0].tick_params(axis='both', which='major', labelsize=8)
            cbar1 = plt.colorbar(sc1, ax=ax3[0, 0], fraction=0.05)
            cbar1.set_label('Objective function', fontsize=10)
            cbar1.ax.tick_params(labelsize=8)

            # Plot 2: Losses vs investment
            sc2 = ax3[0, 1].scatter(self._financial, self._losses, c=self._f_obj, norm=color_norm)
            ax3[0, 1].set_xlabel('Investment cost (M€)', fontsize=10)
            ax3[0, 1].set_ylabel('Losses cost (M€)', fontsize=10)
            ax3[0, 1].set_title('Power losses vs investment', fontsize=12)
            ax3[0, 1].tick_params(axis='both', which='major', labelsize=8)
            cbar2 = plt.colorbar(sc2, ax=ax3[0, 1], fraction=0.05)
            cbar2.set_label('Objective function', fontsize=10)
            cbar2.ax.tick_params(labelsize=8)

            # Plot 3: Overload vs investment
            sc3 = ax3[1, 0].scatter(self._financial, self._overload_score, c=self._f_obj, norm=color_norm)
            ax3[1, 0].set_xlabel('Investment cost (M€)', fontsize=10)
            ax3[1, 0].set_ylabel('Overload cost (M€)', fontsize=10)
            ax3[1, 0].set_title('Branch overload vs investment', fontsize=12)
            ax3[1, 0].tick_params(axis='both', which='major', labelsize=8)
            cbar3 = plt.colorbar(sc3, ax=ax3[1, 0], fraction=0.05)
            cbar3.set_label('Objective function', fontsize=10)
            cbar3.ax.tick_params(labelsize=8)

            # Plot 4: Undervoltage vs investment
            sc4 = ax3[1, 1].scatter(self._financial, self._voltage_score, c=self._f_obj, norm=color_norm)
            ax3[1, 1].set_xlabel('Investment cost (M€)', fontsize=10)
            ax3[1, 1].set_ylabel('Voltage cost (M€)', fontsize=10)
            ax3[1, 1].set_title('Undervoltage vs investment', fontsize=12)
            ax3[1, 1].tick_params(axis='both', which='major', labelsize=8)
            cbar4 = plt.colorbar(sc4, ax=ax3[1, 1], fraction=0.05)
            cbar4.set_label('Objective function', fontsize=10)
            cbar4.ax.tick_params(labelsize=8)

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
            fig.suptitle(str(result_type.value))
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
