import pandas as pd
from matplotlib import pyplot as plt
from numpy.core.multiarray import zeros, array

from GridCal.grid.plot.params import LINEWIDTH


class VoltageCollapseResults:

    def __init__(self, nbus):
        """
        VoltageCollapseResults instance
        @param voltages: Resulting voltages
        @param lambdas: Continuation factor
        """

        self.voltages = None

        self.lambdas = None

        self.error = None

        self.converged = False

        self.available_results = ['Bus voltage']

    def apply_from_island(self, res, bus_original_idx, nbus_full):
        """
        Apply the results of an island to this VoltageCollapseResults instance
        :param res: VoltageCollapseResults instance of the island
        :param bus_original_idx: indices of the buses in the complete grid
        :param nbus_full: total number of buses in the complete grid
        :return:
        """

        if len(res.voltages) > 0:
            l, n = res.voltages.shape

            if self.voltages is None:
                self.voltages = zeros((l, nbus_full), dtype=complex)
                self.voltages[:, bus_original_idx] = res.voltages
                self.lambdas = res.lambdas
            else:
                self.voltages[:, bus_original_idx] = res.voltages

    def plot(self, result_type='Bus voltage', ax=None, indices=None, names=None):
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

        if names is None:
            names = array(['bus ' + str(i + 1) for i in range(self.voltages.shape[1])])

        if indices is None:
            indices = array(range(len(names)))

        if len(indices) > 0:
            labels = names[indices]
            ylabel = ''
            if result_type == 'Bus voltage':
                y = abs(array(self.voltages)[:, indices])
                x = self.lambdas
                title = 'Bus voltage'
                ylabel = '(p.u.)'
            else:
                pass

            df = pd.DataFrame(data=y, index=x, columns=indices)
            df.columns = labels
            if len(df.columns) > 10:
                df.plot(ax=ax, linewidth=LINEWIDTH, legend=False)
            else:
                df.plot(ax=ax, linewidth=LINEWIDTH, legend=True)

            ax.set_title(title)
            ax.set_ylabel(ylabel)
            ax.set_xlabel('Loading from the base situation ($\lambda$)')

            return df
