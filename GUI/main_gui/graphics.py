from numpy import ones, array
import pandas as pd

from GridCalMain.GUI.main_gui.grid.circuit_ import Circuit
from grid.PowerFlow import *
from grid.BusDefinitions import *
from grid.GenDefinitions import *
from grid.BranchDefinitions import *




def display_branch_magnitude(self, ax, fig, y, ylabel, xlabel=''):
    """

    :param ax:
    :param fig:
    :param y:
    :param ylabel:
    :param xlabel:
    :return:
    """
    width = 0.5
    nx = len(self.circuit.branch)
    x = np.array(list(range(nx)))
    labels = self.circuit.get_branch_labels()

    df_data = y
    ax.bar(x, df_data, width=width, color='b', align='center')
    ax.plot(x, ones(nx) * 100, color='r')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation='vertical')
    ax.set_xlim([0-width, len(x)])

    # plot
    ax.set_aspect('auto')
    ax.axes.set_ylabel(ylabel)
    ax.axes.set_xlabel(xlabel)

    fig.tight_layout()

    self.ui.resultsPlot.redraw()

    df = pd.DataFrame(data=[df_data], columns=labels)
    self.ui.resultsTableView.setModel(PandasModel(df))

def display_bus_magnitude(self, ax, fig, y, ylabel, xlabel='', bar=False):
    """

    :param ax:
    :param fig:
    :param y:
    :param ylabel:
    :param xlabel:
    :return:
    """
    x = self.circuit.bus[:, BUS_I].astype(int)
    labels = self.circuit.get_bus_labels()
    dims = np.ndim(y)
    print('dims:', dims)
    if dims == 2:
        df_data = y[:, 0]
        df = pd.DataFrame(data=[df_data], columns=labels)
        ax.plot(x, y[:, 0], color='k', marker='o')
        ax.plot(x, y[:, 1], color='r')
        ax.plot(x, y[:, 2], color='r')
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation='vertical')
    else:
        df_data = y

        if not bar:
            df = pd.DataFrame(data=[df_data], columns=labels, index=x)
            ax.plot(x, y, color='k', marker='o')
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation='vertical')
        else:
            df = pd.DataFrame(data=df_data.transpose(), columns=[ylabel], index=labels)
            df.plot(ax=ax, kind='bar')
            # ax.redraw()

    # plot
    ax.set_aspect('auto')
    ax.axes.set_ylabel(ylabel)
    ax.axes.set_xlabel(xlabel)
    fig.tight_layout()
    self.ui.resultsPlot.redraw()

    self.ui.resultsTableView.setModel(PandasModel(df))

def display_series_bus_magnitude(self, ax, fig, x, y, ylabel, xlabel='', y2=None, ylabel2=None, y_limits=None,
                                 boxplot=False, elm_idx=None):
    """

    :param ax:
    :param fig:
    :param y:
    :param ylabel:
    :param xlabel:
    :return:
    """
    labels = self.circuit.get_bus_labels()
    if elm_idx is not None:
        labels = [labels[elm_idx]]

    # plot limits
    if y_limits is not None:
        ax.plot(x, y_limits[:, 0], color='r')
        ax.plot(x, y_limits[:, 1], color='r')

    # Display data
    df = pd.DataFrame(data=y, columns=labels, index=x)
    self.ui.resultsTableView.setModel(PandasModel(df))

    # plot
    if boxplot:
        df.boxplot(ax=ax, return_type='axes')
        ax.set_xticklabels(labels, rotation='vertical')
    else:
        df.plot(yerr=y2, ax=ax)
        # print('Mismatches:\n', y2)
    ax.set_aspect('auto')
    ax.axes.set_ylabel(ylabel)
    ax.axes.set_xlabel(xlabel)

    # add mismatch on the secondary axis
    # if y2 is not None:
    #     ax2 = ax.twinx()
    #     ax2.plot(y2, 'r.')
    #     if ylabel2 is not None:
    #         ax2.set_ylabel(ylabel2)

    fig.tight_layout()
    self.ui.resultsPlot.redraw()

def display_series_branch_magnitude(self, ax, fig, x, y, ylabel, xlabel='', y2=None, ylabel2=None, y_limits=None,
                                    boxplot=False, elm_idx=None):
    """

    :param ax:
    :param fig:
    :param y:
    :param ylabel:
    :param xlabel:
    :return:
    """
    labels = self.circuit.get_branch_labels()
    if elm_idx is not None:
        labels = [labels[elm_idx]]

    # plot limits
    if y_limits is not None:
        ax.plot(x, y_limits[:, 0], color='r')
        ax.plot(x, y_limits[:, 1], color='r')

    # Display data
    df = pd.DataFrame(data=y, columns=labels, index=x)
    self.ui.resultsTableView.setModel(PandasModel(df))

    # plot
    if boxplot:
        df.boxplot(ax=ax, return_type='axes')
        ax.set_xticklabels(labels, rotation='vertical')
    else:
        df.plot(yerr=y2, ax=ax)
    ax.set_aspect('auto')
    ax.axes.set_ylabel(ylabel)
    ax.axes.set_xlabel(xlabel)

    # add mismatch on the secondary axis
    # if y2 is not None:
    #     ax2 = ax.twinx()
    #     ax2.plot(y2, 'r.')
    #     if ylabel2 is not None:
    #         ax2.set_ylabel(ylabel2)

    fig.tight_layout()
    self.ui.resultsPlot.redraw()

def plot_results(self, type_of_result,  element_idx=None):
    """
    Plots the results stored according to the passed type
    @param type_of_result: variable determining the type of results to plot
    @return: Nothing
    """
    # print(type_of_result)

    if self.circuit.circuit_graph is not None:

        self.ui.resultsPlot.clear(force=True)
        ax = self.ui.resultsPlot.canvas.ax
        fig = self.ui.resultsPlot.canvas.fig

        # pick the selected time

        if self.circuit.time_series.is_ready():
            use_result_at_t = self.ui.values_at_t_radioButton.isChecked()
            t = self.ui.results_time_selection_comboBox.currentIndex()
        else:
            use_result_at_t = False

        series = self.ui.all_values_radioButton.isChecked() or self.ui.box_whiskers_radioButton.isChecked()
        useboxplot = self.ui.box_whiskers_radioButton.isChecked()

        if not series:

            if type_of_result == ResultTypes.branch_losses:
                if use_result_at_t:
                    y = abs(self.circuit.time_series.losses[t, :])
                else:
                    y = self.circuit.branch[:, LOSSES]
                ylabel = "Branch losses (MVA)"
                self.display_branch_magnitude(ax, fig, y, ylabel)

            elif type_of_result == ResultTypes.branches_loading:
                if use_result_at_t:
                    y = abs(self.circuit.time_series.loadings[t, :])
                else:
                    y = self.circuit.branch[:, LOADING]
                ylabel = "Branch loading (%)"
                self.display_branch_magnitude(ax, fig, y * 100, ylabel)

            elif type_of_result == ResultTypes.branch_current:
                if use_result_at_t:
                    y = abs(self.circuit.time_series.currents[t, :])
                else:
                    y = self.circuit.branch[:, BR_CURRENT]
                ylabel = "Branch Currents (kA)"
                self.display_branch_magnitude(ax, fig, y, ylabel)

            elif type_of_result == ResultTypes.bus_voltage_per_unit:
                if use_result_at_t:
                    nb = len(self.circuit.bus)
                    y = zeros((nb, 3))
                    y[:, 0] = abs(self.circuit.time_series.voltages[t, :])
                    y[:, [1, 2]] = self.circuit.bus[:, [VMIN, VMAX]]
                else:
                    y = self.circuit.bus[:, [VM, VMIN, VMAX]]

                ylabel = "Bus Voltages (p.u.)"
                self.display_bus_magnitude(ax, fig, y, ylabel)

            elif type_of_result == ResultTypes.bus_voltage:
                if use_result_at_t:
                    nb = len(self.circuit.bus)
                    y = zeros((nb, 3))
                    y[:, 0] = abs(self.circuit.time_series.voltages[t, :]).copy()
                    y[:, [1, 2]] = self.circuit.bus[:, [VMIN, VMAX]].copy()
                else:
                    y = self.circuit.bus[:, [VM, VMIN, VMAX]].copy()
                y[:, 0] *= self.circuit.bus[:, BASE_KV]
                y[:, 1] *= self.circuit.bus[:, BASE_KV]
                y[:, 2] *= self.circuit.bus[:, BASE_KV]
                ylabel = "Bus Voltages (kV)"
                self.display_bus_magnitude(ax, fig, y, ylabel)

            elif type_of_result == ResultTypes.bus_active_power:
                if use_result_at_t:
                    y = self.circuit.time_series.load_profiles[t, :].real
                else:
                    y = self.circuit.bus[:, PD]

                ylabel = "Bus Active power (MW)"
                self.display_bus_magnitude(ax, fig, y, ylabel, bar=True)

            elif type_of_result == ResultTypes.bus_reactive_power:
                if use_result_at_t:
                    y = self.circuit.time_series.load_profiles[t, :].imag
                else:
                    y = self.circuit.bus[:, QD]

                ylabel = "Bus reactive power (MVar)"
                self.display_bus_magnitude(ax, fig, y, ylabel, bar=True)

            elif type_of_result == ResultTypes.bus_apparent_power:
                if use_result_at_t:
                    y = abs(self.circuit.time_series.load_profiles[t, :])
                else:
                    y = abs(self.circuit.bus[:, PD] + 1j *self.circuit.bus[:, QD])

                ylabel = "Bus apparent power (MVA)"
                self.display_bus_magnitude(ax, fig, y, ylabel, bar=True)

            elif type_of_result == ResultTypes.bus_active_and_reactive_power:
                if use_result_at_t:
                    y = [self.circuit.time_series.load_profiles[t, :].real, self.circuit.time_series.load_profiles[t, :].imag]
                else:
                    y = [self.circuit.bus[:, PD], self.circuit.bus[:, QD]]

                ylabel = "Bus apparent power (MVA)"
                self.display_bus_magnitude(ax, fig, y, ylabel, bar=False)
        else:
            # time series
            if self.circuit.time_series.has_results():

                x = self.circuit.time_series.time

                if type_of_result == ResultTypes.bus_voltage_per_unit:
                    if element_idx is None:
                        y = abs(self.circuit.time_series.voltages)
                    else:
                        y = abs(self.circuit.time_series.voltages)[:, element_idx]
                    y2 = self.circuit.time_series.mismatch

                    ylabel = "Bus Voltages (p.u.)"
                    xlabel = 'Time'
                    ylabel2 = 'Error'
                    self.display_series_bus_magnitude(ax, fig, x, y, ylabel, xlabel, y2, ylabel2,
                                                      boxplot=useboxplot, elm_idx=element_idx)

                elif type_of_result == ResultTypes.bus_voltage:
                    if element_idx is None:
                        y = abs(self.circuit.time_series.voltages)
                        y *= self.circuit.bus[:, BASE_KV]
                    else:
                        y = abs(self.circuit.time_series.voltages)[:, element_idx]
                        y *= self.circuit.bus[element_idx, BASE_KV]

                    y2 = self.circuit.time_series.mismatch

                    ylabel = "Bus Voltages (kV)"
                    xlabel = 'Time'
                    ylabel2 = 'Error'
                    self.display_series_bus_magnitude(ax, fig, x, y, ylabel, xlabel, y2, ylabel2,
                                                      boxplot=useboxplot, elm_idx=element_idx)

                elif type_of_result == ResultTypes.bus_active_power:
                    if element_idx is None:
                        y = self.circuit.time_series.load_profiles.real
                    else:
                        y = self.circuit.time_series.load_profiles[:, element_idx].real

                    ylabel = "Bus active power (MW)"
                    xlabel = 'Time'
                    self.display_series_bus_magnitude(ax, fig, x, y, ylabel, xlabel,
                                                      boxplot=useboxplot, elm_idx=element_idx)

                elif type_of_result == ResultTypes.bus_reactive_power:
                    if element_idx is None:
                        y = self.circuit.time_series.load_profiles.imag
                    else:
                        y = self.circuit.time_series.load_profiles[:, element_idx].imag

                    ylabel = "Bus reactive power (MVar)"
                    xlabel = 'Time'
                    self.display_series_bus_magnitude(ax, fig, x, y, ylabel, xlabel,
                                                      boxplot=useboxplot, elm_idx=element_idx)

                elif type_of_result == ResultTypes.bus_apparent_power:
                    if element_idx is None:
                        y = abs(self.circuit.time_series.load_profiles)
                    else:
                        y = abs(self.circuit.time_series.load_profiles[:, element_idx])

                    ylabel = "Bus apparent power (MVA)"
                    xlabel = 'Time'
                    self.display_series_bus_magnitude(ax, fig, x, y, ylabel, xlabel,
                                                      boxplot=useboxplot, elm_idx=element_idx)

                elif type_of_result == ResultTypes.branches_loading:
                    if element_idx is None:
                        y = abs(self.circuit.time_series.loadings)*100
                    else:
                        y = abs(self.circuit.time_series.loadings)[:, element_idx]*100
                    y2 = self.circuit.time_series.mismatch

                    ylabel = "Branch loading (%)"
                    xlabel = 'Time'
                    ylabel2 = 'Error'
                    self.display_series_branch_magnitude(ax, fig, x, y, ylabel, xlabel, y2, ylabel2,
                                                         boxplot=useboxplot, elm_idx=element_idx)