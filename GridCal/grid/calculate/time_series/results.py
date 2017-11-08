import pandas as pd
from matplotlib import pyplot as plt
from numpy import ones
from numpy.core.multiarray import zeros, array

from GridCal.grid.calculate.power_flow.results import PowerFlowResults
from GridCal.grid.plot.params import LINEWIDTH


class TimeSeriesResults(PowerFlowResults):

    def __init__(self, n, m, nt):
        """
        TimeSeriesResults constructor
        @param n: number of buses
        @param m: number of branches
        @param nt: number of time steps
        """
        PowerFlowResults.__init__(self)

        self.nt = nt
        self.m = m
        self.n = n

        if nt > 0:
            self.voltage = zeros((nt, n), dtype=complex)

            self.Sbranch = zeros((nt, m), dtype=complex)

            self.Ibranch = zeros((nt, m), dtype=complex)

            self.loading = zeros((nt, m), dtype=complex)

            self.losses = zeros((nt, m), dtype=complex)

            self.error = zeros(nt)

            self.converged = ones(nt, dtype=bool)  # guilty assumption

            # self.Qpv = Qpv

            self.overloads = [None] * nt

            self.overvoltage = [None] * nt

            self.undervoltage = [None] * nt

            self.overloads_idx = [None] * nt

            self.overvoltage_idx = [None] * nt

            self.undervoltage_idx = [None] * nt

            self.buses_useful_for_storage = [None] * nt

        else:
            self.voltage = None

            self.Sbranch = None

            self.Ibranch = None

            self.loading = None

            self.losses = None

            self.error = None

            self.converged = None

            # self.Qpv = Qpv

            self.overloads = None

            self.overvoltage = None

            self.undervoltage = None

            self.overloads_idx = None

            self.overvoltage_idx = None

            self.undervoltage_idx = None

            self.buses_useful_for_storage = None

            self.available_results = ['Bus voltage', 'Branch power', 'Branch current', 'Branch_loading',
                                      'Branch losses']

    def set_at(self, t, results: PowerFlowResults, b_idx, br_idx):
        """
        Set the results at the step t
        @param t:
        @param results:
        @return:
        """

        self.voltage[t, :] = results.voltage[b_idx]

        self.Sbranch[t, :] = results.Sbranch[br_idx]

        self.Ibranch[t, :] = results.Ibranch[br_idx]

        self.loading[t, :] = results.loading[br_idx]

        self.losses[t, :] = results.losses[br_idx]

        self.error[t] = max(results.error)

        self.converged[t] = min(results.converged)

        # self.Qpv = Qpv

        self.overloads[t] = results.overloads

        self.overvoltage[t] = results.overvoltage

        self.undervoltage[t] = results.undervoltage

        self.overloads_idx[t] = results.overloads_idx

        self.overvoltage_idx[t] = results.overvoltage_idx

        self.undervoltage_idx[t] = results.undervoltage_idx

        self.buses_useful_for_storage[t] = results.buses_useful_for_storage

    @staticmethod
    def merge_if(df, arr, ind, cols):
        """

        @param df:
        @param arr:
        @param ind:
        @param cols:
        @return:
        """
        obj = pd.DataFrame(data=arr, index=ind, columns=cols)
        if df is None:
            df = obj
        else:
            df = pd.concat([df, obj], axis=1)

        return df

    def apply_from_island(self, results, b_idx, br_idx, index, grid_idx):
        """
        Apply results from another island circuit to the circuit results represented here
        @param results: PowerFlowResults
        @param b_idx: bus original indices
        @param br_idx: branch original indices
        @return:
        """

        # self.voltage[:, b_idx] = results.voltage
        #
        # self.Sbranch[:, br_idx] = results.Sbranch
        #
        # self.Ibranch[:, br_idx] = results.Ibranch
        #
        # self.loading[:, br_idx] = results.loading
        #
        # self.losses[:, br_idx] = results.losses
        #
        # if (results.error > self.error).any():
        #     self.error = results.error
        #
        # self.converged = self.converged * results.converged

        self.voltage = self.merge_if(self.voltage, results.voltage, index, b_idx)

        self.Sbranch = self.merge_if(self.Sbranch, results.Sbranch, index, br_idx)

        self.Ibranch = self.merge_if(self.Ibranch, results.Ibranch, index, br_idx)

        self.loading = self.merge_if(self.loading, results.loading, index, br_idx)

        self.losses = self.merge_if(self.losses, results.losses, index, br_idx)

        self.error = self.merge_if(self.error, results.error, index, [grid_idx])

        self.converged = self.merge_if(self.converged, results.converged, index, [grid_idx])

        # self.Qpv = Qpv

        # self.overloads = self.merge_if(self.voltage, results.voltage, index, b_idx)
        #
        # self.overvoltage = self.merge_if(self.voltage, results.voltage, index, b_idx)
        #
        # self.undervoltage = self.merge_if(self.voltage, results.voltage, index, b_idx)
        #
        # self.overloads_idx = None
        #
        # self.overvoltage_idx = None
        #
        # self.undervoltage_idx = None
        #
        # self.buses_useful_for_storage = None

    def analyze(self):
        """
        Analyze the results
        @return:
        """
        branch_overload_frequency = zeros(self.m)
        bus_undervoltage_frequency = zeros(self.n)
        bus_overvoltage_frequency = zeros(self.n)
        buses_selected_for_storage_frequency = zeros(self.n)
        for i in range(self.nt):
            branch_overload_frequency[self.overloads_idx[i]] += 1
            bus_undervoltage_frequency[self.undervoltage_idx[i]] += 1
            bus_overvoltage_frequency[self.overvoltage_idx[i]] += 1
            buses_selected_for_storage_frequency[self.buses_useful_for_storage[i]] += 1

        return branch_overload_frequency, bus_undervoltage_frequency, bus_overvoltage_frequency, buses_selected_for_storage_frequency

    def plot(self, result_type, ax=None, indices=None, names=None):
        """
        Plot the results
        :param result_type:
        :param ax:
        :param indices:
        :param names:
        :return:
        """

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        if indices is None:
            indices = array(range(len(names)))

        if len(indices) > 0:
            labels = names[indices]
            ylabel = ''
            title = ''
            if result_type == 'Bus voltage':
                df = self.voltage[indices]
                ylabel = '(p.u.)'
                title = 'Bus voltage '

            elif result_type == 'Branch power':
                df = self.Sbranch[indices]
                ylabel = '(MVA)'
                title = 'Branch power '

            elif result_type == 'Branch current':
                df = self.Ibranch[indices]
                ylabel = '(kA)'
                title = 'Branch current '

            elif result_type == 'Branch_loading':
                df = self.loading[indices] * 100
                ylabel = '(%)'
                title = 'Branch loading '

            elif result_type == 'Branch losses':
                df = self.losses[indices]
                ylabel = '(MVA)'
                title = 'Branch losses'

            else:
                pass

            df.columns = labels

            if len(df.columns) > 10:
                df.plot(ax=ax, linewidth=LINEWIDTH, legend=False)
            else:
                df.plot(ax=ax, linewidth=LINEWIDTH, legend=True)

            ax.set_title(title)
            ax.set_ylabel(ylabel)
            ax.set_xlabel('Time')

            return df

        else:
            return None
