from numpy.core.multiarray import zeros
from numpy.core.umath import power

from GridCal.grid.sample.monte_carlo.results import MonteCarloResults


class MonteCarloThread(QThread):

    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions):
        """

        @param grid:
        @param options:
        """
        QThread.__init__(self)

        self.grid = grid

        self.options = options

        n = len(self.grid.buses)
        m = len(self.grid.branches)

        self.results = MonteCarloResults(n, m)

        self.__cancel__ = False

    def run(self):
        """
        Run the monte carlo simulation
        @return:
        """

        self.__cancel__ = False

        # initialize the power flow
        powerflow = PowerFlow(self.grid, self.options)

        # initialize the grid time series results
        # we will append the island results with another function
        self.grid.time_series_results = TimeSeriesResults(0, 0, 0)

        mc_tol = 1e-6
        batch_size = 100
        max_mc_iter = 100000
        it = 0
        variance_sum = 0.0
        std_dev_progress = 0
        Vvariance = 0

        n = len(self.grid.buses)
        m = len(self.grid.branches)

        mc_results = MonteCarloResults(n, m)

        Vsum = zeros(n, dtype=complex)
        self.progress_signal.emit(0.0)

        while (std_dev_progress < 100.0) and (it < max_mc_iter) and not self.__cancel__:

            self.progress_text.emit('Running Monte Carlo: Variance: ' + str(Vvariance))

            batch_results = MonteCarloResults(n, m, batch_size)

            # For every circuit, run the time series
            for c in self.grid.circuits:

                # set the time series as sampled
                c.sample_monte_carlo_batch(batch_size)

                # run the time series
                for t in range(batch_size):
                    # print(t + 1, ' / ', batch_size)
                    # set the power values
                    Y, I, S = c.mc_time_series.get_at(t)

                    res = powerflow.run_at(t, mc=True)
                    batch_results.S_points[t, c.bus_original_idx] = S
                    batch_results.V_points[t, c.bus_original_idx] = res.voltage[c.bus_original_idx]
                    batch_results.I_points[t, c.branch_original_idx] = res.Ibranch[c.branch_original_idx]
                    batch_results.loading_points[t, c.branch_original_idx] = res.loading[c.branch_original_idx]

            # Compute the Monte Carlo values
            it += batch_size
            mc_results.append_batch(batch_results)
            Vsum += batch_results.get_voltage_sum()
            Vavg = Vsum / it
            Vvariance = abs((power(mc_results.V_points - Vavg, 2.0) / (it - 1)).min())

            # progress
            variance_sum += Vvariance
            err = variance_sum / it
            if err == 0:
                err = 1e-200  # to avoid division by zeros
            mc_results.error_series.append(err)

            # emmit the progress signal
            std_dev_progress = 100 * mc_tol / err
            if std_dev_progress > 100:
                std_dev_progress = 100
            self.progress_signal.emit(max((std_dev_progress, it/max_mc_iter*100)))

            print(iter, '/', max_mc_iter)
            # print('Vmc:', Vavg)
            print('Vstd:', Vvariance, ' -> ', std_dev_progress, ' %')

        # compile results
        self.progress_text.emit('Compiling results...')
        mc_results.compile()

        # compute the averaged branch magnitudes
        mc_results.sbranch, Ibranch, loading, mc_results.losses = powerflow.compute_branch_results(self.grid, mc_results.voltage)

        self.results = mc_results

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled')
        self.done_signal.emit()
