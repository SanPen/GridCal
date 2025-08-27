# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import textwrap
import numpy as np
from matplotlib import pyplot as plt
import matplotlib.colors as plt_colors

from VeraGridEngine.Simulations.results_template import ResultsTemplate
from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.basic_structures import IntVec, Vec, StrVec, Mat
from VeraGridEngine.enumerations import StudyResultsType, ResultTypes, DeviceType
from VeraGridEngine.Utils.NumericalMethods.MVRSM_mo_pareto import non_dominated_sorting


class InvestmentsEvaluationResults(ResultsTemplate):
    tpe = 'Investments Evaluation Results'

    def __init__(self, f_names: StrVec, x_names: StrVec, max_eval: int, plot_x_idx: int, plot_y_idx: int):
        """
        Constructor
        :param f_names: Names of the objectives
        :param x_names: Names of the decision vars
        :param max_eval: Maximum number of evaluations
        :param plot_x_idx: index of f to use as x when plotting
        :param plot_y_idx: index of f to use as y when plotting
        """
        available_results = {
            ResultTypes.ReportsResults: [ResultTypes.InvestmentsReportResults,
                                         ResultTypes.InvestmentsCombinationsResults,
                                         ResultTypes.InvestmentsObjectivesResults,
                                         ResultTypes.InvestmentsFrequencyResults],

            ResultTypes.ParetoResults: [ResultTypes.InvestmentsParetoReportResults,
                                        ResultTypes.InvestmentsParetoCombinationsResults,
                                        ResultTypes.InvestmentsParetoObjectivesResults
                                        ],

            ResultTypes.SpecialPlots: [ResultTypes.InvestmentsParetoPlot,
                                       ResultTypes.InvestmentsIterationsPlot,
                                       ResultTypes.InvestmentsWhenToMakePlot],
        }

        ResultsTemplate.__init__(self,
                                 name='Investments Evaluation',
                                 available_results=available_results,
                                 time_array=None,
                                 clustering_results=None,
                                 study_results_type=StudyResultsType.InvestmentEvaluations)

        n_f = len(f_names)
        n_x = len(x_names)

        self._max_eval = max_eval
        self.f_names: StrVec = f_names
        self.x_names: StrVec = x_names
        self.plot_x_idx = plot_x_idx
        self.plot_y_idx = plot_y_idx

        self._x: IntVec = np.zeros((max_eval, n_x), dtype=float)
        self._f: IntVec = np.zeros((max_eval, n_f), dtype=float)
        self._f_best = np.zeros(n_f, dtype=float)
        self._sorting_indices = np.zeros(max_eval, dtype=int)

        self.__eval_index: int = 0

        self.register(name='max_eval', tpe=int)
        self.register(name='f_names', tpe=StrVec)
        self.register(name='x_names', tpe=StrVec)
        self.register(name='plot_x_idx', tpe=int)
        self.register(name='plot_y_idx', tpe=int)
        self.register(name='x', tpe=Mat)
        self.register(name='f', tpe=Mat)
        self.register(name='f_best', tpe=Vec)
        self.register(name='sorting_indices', tpe=IntVec)

    @property
    def max_eval(self) -> int:
        return self._max_eval

    @max_eval.setter
    def max_eval(self, val: int):
        self._max_eval = val

    @property
    def x(self) -> Mat:
        return self._x

    @x.setter
    def x(self, val: Vec):
        if isinstance(val, np.ndarray):
            self._x = val
        else:
            raise ValueError("X must be a numpy array")

    @property
    def f(self) -> Mat:
        return self._f

    @f.setter
    def f(self, val: Vec):
        if isinstance(val, np.ndarray):
            self._f = val
        else:
            raise ValueError("f must be a numpy array")

    @property
    def f_best(self) -> IntVec:
        return self._f_best

    @f_best.setter
    def f_best(self, val: Vec):
        if isinstance(val, np.ndarray):
            self._f_best = val
        else:
            raise ValueError("f_best must be a numpy array")

    @property
    def current_evaluation(self) -> int:
        return self.__eval_index

    @property
    def sorting_indices(self) -> IntVec:
        return self._sorting_indices

    @sorting_indices.setter
    def sorting_indices(self, val: IntVec):
        if isinstance(val, np.ndarray):
            self._sorting_indices = val.astype(int)
        else:
            raise ValueError("sorting indices must be an array of integer")

    def get_index(self) -> StrVec:
        return np.array([f"Eval {i + 1}" for i in range(self.x.shape[0])])

    def set_at(self, i: int, x_vec: Vec, f_vec: Vec):
        """

        :param i:
        :param x_vec:
        :param f_vec:
        :return:
        """
        self._x[i, :] = x_vec
        self._f[i, :] = f_vec

    def add(self, x_vec: Vec, f_vec: Vec) -> None:
        """

        :param x_vec:
        :param f_vec:
        :return:
        """
        if self.__eval_index < self.max_eval:
            self.set_at(i=self.__eval_index, x_vec=x_vec, f_vec=f_vec)

            self.__eval_index += 1
        else:
            print('Evaluation index out of range')

    def finalize(self):
        """
        Finalize the results after simulation
        """
        # crop the data to the latest call index
        if self.__eval_index > 0:
            self._f = self._f[:self.__eval_index, :]
            self._x = self._x[:self.__eval_index, :]

            # compute the pareto sorting indices
            _, _, self._sorting_indices = non_dominated_sorting(y_values=self.f, x_values=self.x)

            # we curtail this one too
            self.max_eval = self.__eval_index

    def set_best_combination(self, combination: IntVec) -> None:
        """
        Set the best combination of investment groups
        :param combination: Vector of integers (0/1)
        """
        self._f_best = combination

    def mdl(self, result_type) -> ResultsTable:
        """
        Plot the results
        :param result_type: type of results (string)
        :return: DataFrame of the results (or None if the result was not understood)
        """
        n = self.x.shape[0]
        index = self.get_index()

        if result_type in (ResultTypes.InvestmentsReportResults,
                           ResultTypes.InvestmentsParetoReportResults):

            columns = np.r_[np.array(self.f_names), np.array(self.x_names)]
            data = np.c_[self.f, self.x]

            if result_type == ResultTypes.InvestmentsParetoReportResults:
                # slice results according to the pareto indices
                index = index[self.sorting_indices]
                data = data[self.sorting_indices, :]

            return ResultsTable(data=data,
                                index=index,
                                idx_device_type=DeviceType.NoDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice.NoDevice,
                                title=str(result_type.value),
                                ylabel="",
                                xlabel='',
                                units="")

        elif result_type == ResultTypes.InvestmentsFrequencyResults:

            freq = np.sum(self._x, axis=0)
            freq_rel = freq / freq.sum()
            data = np.c_[freq, freq_rel]

            return ResultsTable(data=data,
                                index=np.array(self.x_names),
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
                data = self._x[self.sorting_indices, :]
                index = index[self.sorting_indices]
            else:
                data = self._x

            return ResultsTable(data=data,
                                index=index,
                                idx_device_type=DeviceType.NoDevice,
                                columns=self.x_names,
                                cols_device_type=DeviceType.NoDevice.NoDevice,
                                title=str(result_type.value),
                                ylabel="",
                                xlabel="",
                                units="")

        elif result_type in (ResultTypes.InvestmentsObjectivesResults,
                             ResultTypes.InvestmentsParetoObjectivesResults):

            data = self.f

            if result_type == ResultTypes.InvestmentsParetoObjectivesResults:
                # slice results according to the pareto indices
                data = data[self.sorting_indices, :]
                index = index[self.sorting_indices]

            return ResultsTable(data=data,
                                index=index,
                                idx_device_type=DeviceType.NoDevice,
                                columns=self.f_names,
                                cols_device_type=DeviceType.NoDevice.NoDevice,
                                title=str(result_type.value),
                                ylabel="",
                                xlabel="",
                                units="")

        elif result_type == ResultTypes.InvestmentsParetoPlot:

            x_vals = self.f[:, self.plot_x_idx]
            y_vals = self.f[:, self.plot_y_idx]

            plt.ion()
            color_norm = plt_colors.Normalize()
            fig, ax3 = plt.subplots(1, 1, figsize=(16, 12))

            # Match magnitude of technical score with investment score
            color_score = y_vals * 10 ** -2

            # Plot 1: Technical vs investment
            scatter_plot = ax3.scatter(x_vals, y_vals, c=color_score)
            ax3.set_xlabel(self.f_names[self.plot_x_idx], fontsize=10)
            ax3.set_ylabel(self.f_names[self.plot_y_idx], fontsize=10)
            ax3.set_title('Pareto plot', fontsize=12)
            ax3.tick_params(axis='both', which='major', labelsize=8)
            cbar1 = plt.colorbar(scatter_plot, ax=ax3, fraction=0.05)
            cbar1.set_label('Objective function', fontsize=10)
            cbar1.ax.tick_params(labelsize=8)

            fig.suptitle(result_type.value)
            plt.tight_layout()

            annot = ax3.annotate("", xy=(0, 0), xytext=(20, 20),
                                 textcoords="offset points",
                                 bbox=dict(boxstyle="round", fc="w", pad=0.3),
                                 arrowprops=dict(arrowstyle="->"),
                                 fontsize=8,
                                 zorder=10)  # Set z-order to a higher value to ensure it's in front
            annot.set_visible(False)

            def update_annotation(ind):
                """

                :param ind:
                :return:
                """
                i = ind["ind"][0]
                annot.xy = scatter_plot.get_offsets()[i]
                text = f"Solution:\n{index[i]}"
                wrapped_text = textwrap.fill(text, width=30)
                annot.set_text(wrapped_text)
                annot.get_bbox_patch().set_alpha(0.8)

            def hover(event):
                """

                :param event:
                :return:
                """
                if event.inaxes == ax3:
                    cont, ind = scatter_plot.contains(event)
                    if cont:
                        update_annotation(ind)
                        annot.set_visible(True)
                        fig.canvas.draw_idle()
                    else:
                        if annot.get_visible():
                            annot.set_visible(False)
                            fig.canvas.draw_idle()

            def click_solution(event):
                """

                :param event:
                :return:
                """
                if event.inaxes is not None:
                    click_x, click_y = event.xdata, event.ydata
                    tolerance = 0.1 * (ax3.get_xlim()[1] - ax3.get_xlim()[0])
                    offsets = scatter_plot.get_offsets()
                    scatter_x = offsets[:, 0]
                    scatter_y = offsets[:, 1]
                    distances = np.hypot(scatter_x - click_x, scatter_y - click_y)
                    min_idx = distances.argmin()

                    if distances[min_idx] < tolerance:
                        investment_names = index[min_idx]
                        print("Investments made:")
                        for i, x_val in enumerate(self.x[min_idx, :]):
                            if x_val != 0.0:
                                print(self.x_names[i])

            fig.canvas.mpl_connect("motion_notify_event", hover)
            fig.canvas.mpl_connect('button_press_event', click_solution)
            plt.show()
            plt.show()

            return ResultsTable(data=np.c_[x_vals, y_vals],
                                index=np.array(index),
                                idx_device_type=DeviceType.NoDevice,
                                columns=np.array([self.f_names[self.plot_x_idx],
                                                  self.f_names[self.plot_y_idx]]),
                                cols_device_type=DeviceType.NoDevice.NoDevice,
                                title="Pareto plot",
                                ylabel=self.f_names[self.plot_y_idx],
                                xlabel=self.f_names[self.plot_x_idx],
                                units="")

        elif result_type == ResultTypes.InvestmentsIterationsPlot:

            columns = ["Iteration", "Objectives summation"]
            x = np.arange(self.max_eval)
            y = self.f.sum(axis=1)
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
                                index=np.array(index),
                                idx_device_type=DeviceType.NoDevice,
                                columns=np.array(columns),
                                cols_device_type=DeviceType.NoDevice.NoDevice,
                                title=title,
                                ylabel=y_label,
                                xlabel='',
                                units=y_label)

        elif result_type == ResultTypes.InvestmentsWhenToMakePlot:

            # Create subplots
            fig, ax = plt.subplots(1, 1, figsize=(16, 6), sharey=False)

            # _x is (max_eval, n_investments)
            # X is (pareto solutions, n_investments)

            X = self._x[self.sorting_indices, :].astype(int)

            max_years = np.max(X)
            mat = np.zeros((X.shape[1], max_years))
            for i in range(X.shape[0]):  # evaluation index
                for j in range(X.shape[1]):  # investment index
                    year = X[i, j]
                    if year > 0:
                        mat[j, year - 1] += 1

            ax.imshow(mat)
            ax.set_title("When to make the investments", fontsize=14)
            ax.set_xlabel("", fontsize=12)
            ax.set_xticks(np.arange(max_years), np.arange(1, max_years + 1))
            ax.set_yticks(np.arange(len(self.x_names)))
            ax.set_yticklabels(self.x_names)
            ax.tick_params(axis='x', labelsize=11)
            ax.tick_params(axis='y', labelsize=11)
            ax.set_xlabel("Year", fontsize=12)
            fig.tight_layout()
            plt.show()

            return ResultsTable(data=mat,
                                index=self.x_names,
                                idx_device_type=DeviceType.NoDevice,
                                columns=np.array([str(y) for y in range(max_years)]),
                                cols_device_type=DeviceType.NoDevice.NoDevice,
                                title=str(result_type.value),
                                ylabel="",
                                xlabel="",
                                units="")
        else:
            raise Exception('Result type not understood:' + str(result_type))
