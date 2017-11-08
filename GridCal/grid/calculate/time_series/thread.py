from GridCal.grid.calculate.power_flow.options import PowerFlowOptions
from GridCal.grid.calculate.power_flow.runnable import PowerFlowRunnable
from GridCal.grid.calculate.time_series.results import TimeSeriesResults


class TimeSeriesThread(QThread):

    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions):
        """
        TimeSeries constructor
        @param grid: MultiCircuit instance
        @param options: PowerFlowOptions instance
        """
        QThread.__init__(self)

        # reference the grid directly
        self.grid = grid

        self.options = options

        self.results = None

        self.__cancel__ = False

    def run(self):
        """
        Run the time series simulation
        @return:
        """
        # initialize the power flow
        powerflow = PowerFlowRunnable(self.grid, self.options)

        # initialize the grid time series results
        # we will append the island results with another function
        self.grid.time_series_results = TimeSeriesResults(0, 0, 0)

        # For every circuit, run the time series
        for nc, c in enumerate(self.grid.circuits):

            self.progress_text.emit('Time series at circuit ' + str(nc) + '...')

            if c.time_series_input.valid:

                nt = len(c.time_series_input.time_array)
                n = len(c.buses)
                m = len(c.branches)
                results = TimeSeriesResults(n, m, nt)

                self.progress_signal.emit(0.0)

                t = 0
                while t < nt and not self.__cancel__:
                    print(t + 1, ' / ', nt)
                    # set the power values
                    Y, I, S = c.time_series_input.get_at(t)

                    res = powerflow.run_at(t)
                    results.set_at(t, res, c.bus_original_idx, c.branch_original_idx)

                    prog = ((t + 1) / nt) * 100
                    self.progress_signal.emit(prog)
                    t += 1

                c.time_series_results = results
                self.grid.time_series_results.apply_from_island(results, c.bus_original_idx, c.branch_original_idx,
                                                                c.time_series_input.time_array, c.name)
            else:
                print('There are no profiles')
                self.progress_text.emit('There are no profiles')

        self.results = self.grid.time_series_results

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True
