from GridCal.grid.calculate.power_flow.runnable import PowerFlowRunnable
from GridCal.grid.calculate.power_flow.options import PowerFlowOptions
from GridCal.grid.calculate.time_series.results import TimeSeriesResults
from GridCal.grid.model.circuit import MultiCircuit
from GridCal.grid.sample.monte_carlo.results import MonteCarloResults


class LatinHypercubeSampling(QThread):

    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, sampling_points=1000):
        """

        Args:
            grid:
            options:
            sampling_points:
        """
        QThread.__init__(self)

        self.grid = grid

        self.options = options

        self.sampling_points = sampling_points

        self.results = None

        self.__cancel__ = False

    def run(self):
        """
        Run the monte carlo simulation
        @return:
        """
        print('LHS run')
        self.__cancel__ = False

        # initialize the power flow
        powerflow = PowerFlowRunnable(self.grid, self.options)

        # initialize the grid time series results
        # we will append the island results with another function
        self.grid.time_series_results = TimeSeriesResults(0, 0, 0)

        batch_size = self.sampling_points
        n = len(self.grid.buses)
        m = len(self.grid.branches)

        self.progress_signal.emit(0.0)
        self.progress_text.emit('Running Latin Hypercube Sampling...')

        lhs_results = MonteCarloResults(n, m, batch_size)

        max_iter = batch_size * len(self.grid.circuits)
        it = 0

        # For every circuit, run the time series
        for c in self.grid.circuits:

            # set the time series as sampled
            c.sample_monte_carlo_batch(batch_size, use_latin_hypercube=True)

            # run the time series
            for t in range(batch_size):
                # print(t + 1, ' / ', batch_size)
                # set the power values
                Y, I, S = c.mc_time_series.get_at(t)

                res = powerflow.run_at(t, mc=True)
                lhs_results.S_points[t, c.bus_original_idx] = S
                lhs_results.V_points[t, c.bus_original_idx] = res.voltage[c.bus_original_idx]
                lhs_results.I_points[t, c.branch_original_idx] = res.Ibranch[c.branch_original_idx]
                lhs_results.loading_points[t, c.branch_original_idx] = res.loading[c.branch_original_idx]

                it += 1
                self.progress_signal.emit(it / max_iter * 100)

                if self.__cancel__:
                    break

            if self.__cancel__:
                break

        # compile MC results
        self.progress_text.emit('Compiling results...')
        lhs_results.compile()

        # lhs_results the averaged branch magnitudes
        lhs_results.sbranch, Ibranch, loading, lhs_results.losses = powerflow.compute_branch_results(self.grid, lhs_results.voltage)

        self.results = lhs_results

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled')
        self.done_signal.emit()


