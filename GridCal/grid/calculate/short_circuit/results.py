import pandas as pd
from matplotlib import pyplot as plt
from numpy.core.multiarray import array
from numpy.ma import zeros

from GridCal.grid.calculate.power_flow.results import PowerFlowResults
from GridCal.grid.plot.params import LINEWIDTH


class ShortCircuitResults(PowerFlowResults):

    def __init__(self, Sbus=None, voltage=None, Sbranch=None, Ibranch=None, loading=None, losses=None, SCpower=None,
                 error=None, converged=None, Qpv=None):

        """

        Args:
            Sbus:
            voltage:
            Sbranch:
            Ibranch:
            loading:
            losses:
            SCpower:
            error:
            converged:
            Qpv:
        """
        PowerFlowResults.__init__(self, Sbus=Sbus, voltage=voltage, Sbranch=Sbranch, Ibranch=Ibranch,
                                  loading=loading, losses=losses, error=error, converged=converged, Qpv=Qpv)

        self.Scpower = SCpower

        self.available_results = ['Bus voltage', 'Branch power', 'Branch current', 'Branch_loading', 'Branch losses',
                                  'Bus short circuit power']

    def copy(self):
        """
        Return a copy of this
        @return:
        """
        return ShortCircuitResults(Sbus=self.Sbus, voltage=self.voltage, Sbranch=self.Sbranch,
                                   Ibranch=self.Ibranch, loading=self.loading,
                                   losses=self.losses, SCpower=self.Scpower, error=self.error,
                                   converged=self.converged, Qpv=self.Qpv)

    def initialize(self, n, m):
        """
        Initialize the arrays
        @param n: number of buses
        @param m: number of branches
        @return:
        """
        self.Sbus = zeros(n, dtype=complex)

        self.voltage = zeros(n, dtype=complex)

        self.Scpower = zeros(n, dtype=float)

        self.overvoltage = zeros(n, dtype=complex)

        self.undervoltage = zeros(n, dtype=complex)

        self.Sbranch = zeros(m, dtype=complex)

        self.Ibranch = zeros(m, dtype=complex)

        self.loading = zeros(m, dtype=complex)

        self.losses = zeros(m, dtype=complex)

        self.overloads = zeros(m, dtype=complex)

        self.error = 0

        self.converged = True

        self.buses_useful_for_storage = list()

    def apply_from_island(self, results, b_idx, br_idx):
        """
        Apply results from another island circuit to the circuit results represented here
        @param results: PowerFlowResults
        @param b_idx: bus original indices
        @param br_idx: branch original indices
        @return:
        """
        self.Sbus[b_idx] = results.Sbus

        self.voltage[b_idx] = results.voltage

        self.Scpower[b_idx] = results.Scpower

        self.overvoltage[b_idx] = results.overvoltage

        self.undervoltage[b_idx] = results.undervoltage

        self.Sbranch[br_idx] = results.Sbranch

        self.Ibranch[br_idx] = results.Ibranch

        self.loading[br_idx] = results.loading

        self.losses[br_idx] = results.losses

        self.overloads[br_idx] = results.overloads

        if results.error > self.error:
            self.error = results.error

        self.converged = self.converged and results.converged

        if results.buses_useful_for_storage is not None:
            self.buses_useful_for_storage = b_idx[results.buses_useful_for_storage]

    def plot(self, result_type, ax=None, indices=None, names=None):
        """
        Plot the results
        Args:
            result_type:
            ax:
            indices:
            names:

        Returns:

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
                y = self.voltage[indices]
                ylabel = '(p.u.)'
                title = 'Bus voltage '

            elif result_type == 'Branch power':
                y = self.Sbranch[indices]
                ylabel = '(MVA)'
                title = 'Branch power '

            elif result_type == 'Branch current':
                y = self.Ibranch[indices]
                ylabel = '(p.u.)'
                title = 'Branch current '

            elif result_type == 'Branch_loading':
                y = self.loading[indices] * 100
                ylabel = '(%)'
                title = 'Branch loading '

            elif result_type == 'Branch losses':
                y = self.losses[indices]
                ylabel = '(MVA)'
                title = 'Branch losses '

            elif result_type == 'Bus short circuit power':
                y = self.Scpower[indices]
                ylabel = '(MVA)'
                title = 'Bus short circuit power'
            else:
                pass

            df = pd.DataFrame(data=y, index=labels, columns=[result_type])
            df.plot(ax=ax, kind='bar', linewidth=LINEWIDTH)
            ax.set_ylabel(ylabel)
            ax.set_title(title)

            return df

        else:
            return None
