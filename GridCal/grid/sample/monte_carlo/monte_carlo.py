import pickle as pkl

import os
import pandas as pd
from PyQt5.QtCore import QThread, pyqtSignal
from UnderDevelopment.GridCal.grid.calculate.time_series.time_series import \
    TimeSeriesInput, TimeSeriesResults
from matplotlib import pyplot as plt
from numpy import vstack
from numpy.core.multiarray import zeros, arange, array
from numpy.core.umath import power, floor
from pyDOE import lhs
from sklearn.ensemble import RandomForestRegressor
from warnings import warn



class MonteCarloInput:

    def __init__(self, n, Scdf, Icdf, Ycdf):
        """

        @param Scdf: Power cumulative density function
        @param Icdf: Current cumulative density function
        @param Ycdf: Admittances cumulative density function
        """
        self.n = n

        self.Scdf = Scdf

        self.Icdf = Icdf

        self.Ycdf = Ycdf

    def __call__(self, samples=0, use_latin_hypercube=False):

        if use_latin_hypercube:

            lhs_points = lhs(self.n, samples=samples, criterion='center')

            if samples > 0:
                S = zeros((samples, self.n), dtype=complex)
                I = zeros((samples, self.n), dtype=complex)
                Y = zeros((samples, self.n), dtype=complex)

                for i in range(self.n):
                    if self.Scdf[i] is not None:
                        S[:, i] = self.Scdf[i].get_at(lhs_points[:, i])

        else:
            if samples > 0:
                S = zeros((samples, self.n), dtype=complex)
                I = zeros((samples, self.n), dtype=complex)
                Y = zeros((samples, self.n), dtype=complex)

                for i in range(self.n):
                    if self.Scdf[i] is not None:
                        S[:, i] = self.Scdf[i].get_sample(samples)
            else:
                S = zeros(self.n, dtype=complex)
                I = zeros(self.n, dtype=complex)
                Y = zeros(self.n, dtype=complex)

                for i in range(self.n):
                    if self.Scdf[i] is not None:
                        S[i] = complex(self.Scdf[i].get_sample()[0])

        time_series_input = TimeSeriesInput()
        time_series_input.S = S
        time_series_input.I = I
        time_series_input.Y = Y
        time_series_input.valid = True

        return time_series_input

    def get_at(self, x):
        """
        Get samples at x
        Args:
            x: values in [0, 1+ to sample the CDF

        Returns:

        """
        S = zeros((1, self.n), dtype=complex)
        I = zeros((1, self.n), dtype=complex)
        Y = zeros((1, self.n), dtype=complex)

        for i in range(self.n):
            if self.Scdf[i] is not None:
                S[:, i] = self.Scdf[i].get_at(x[i])

        time_series_input = TimeSeriesInput()
        time_series_input.S = S
        time_series_input.I = I
        time_series_input.Y = Y
        time_series_input.valid = True

        return time_series_input


class MonteCarlo(QThread):

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


class MonteCarloResults:

    def __init__(self, n, m, p=0):
        """
        Constructor
        @param n: number of nodes
        @param m: number of branches
        @param p: number of points (rows)
        """
        self.S_points = zeros((p, n), dtype=complex)

        self.V_points = zeros((p, n), dtype=complex)

        self.I_points = zeros((p, m), dtype=complex)

        self.loading_points = zeros((p, m), dtype=complex)

        # self.Vstd = zeros(n, dtype=complex)

        self.error_series = list()

        self.voltage = None
        self.current = None
        self.loading = None
        self.sbranch = None
        self.losses = None

        # magnitudes standard deviation convergence
        self.v_std_conv = None
        self.c_std_conv = None
        self.l_std_conv = None

        # magnitudes average convergence
        self.v_avg_conv = None
        self.c_avg_conv = None
        self.l_avg_conv = None

        self.available_results = ['Bus voltage avg', 'Bus voltage std',
                                  'Bus current avg', 'Bus current std',
                                  'Branch loading avg', 'Branch loading std',
                                  'Bus voltage CDF', 'Branch loading CDF']

    def append_batch(self, mcres):
        """
        Append a batch (a MonteCarloResults object) to this object
        @param mcres: MonteCarloResults object
        @return:
        """
        self.S_points = vstack((self.S_points, mcres.S_points))
        self.V_points = vstack((self.V_points, mcres.V_points))
        self.I_points = vstack((self.I_points, mcres.I_points))
        self.loading_points = vstack((self.loading_points, mcres.loading_points))

    def get_voltage_sum(self):
        """
        Return the voltage summation
        @return:
        """
        return self.V_points.sum(axis=0)

    def compile(self):
        """
        Compiles the final Monte Carlo values by running an online mean and
        @return:
        """
        p, n = self.V_points.shape
        ni, m = self.I_points.shape
        step = 1
        nn = int(floor(p / step) + 1)
        self.v_std_conv = zeros((nn, n))
        self.c_std_conv = zeros((nn, m))
        self.l_std_conv = zeros((nn, m))
        self.v_avg_conv = zeros((nn, n))
        self.c_avg_conv = zeros((nn, m))
        self.l_avg_conv = zeros((nn, m))

        v_mean = zeros(n)
        c_mean = zeros(m)
        l_mean = zeros(m)
        v_std = zeros(n)
        c_std = zeros(m)
        l_std = zeros(m)

        for t in range(1, p, step):
            v_mean_prev = v_mean.copy()
            c_mean_prev = c_mean.copy()
            l_mean_prev = l_mean.copy()

            v = abs(self.V_points[t, :])
            c = abs(self.I_points[t, :])
            l = abs(self.loading_points[t, :])

            v_mean += (v - v_mean) / t
            v_std += (v - v_mean) * (v - v_mean_prev)
            self.v_avg_conv[t] = v_mean
            self.v_std_conv[t] = v_std / t

            c_mean += (c - c_mean) / t
            c_std += (c - c_mean) * (c - c_mean_prev)
            self.c_std_conv[t] = c_std / t
            self.c_avg_conv[t] = c_mean

            l_mean += (l - l_mean) / t
            l_std += (l - l_mean) * (l - l_mean_prev)
            self.l_std_conv[t] = l_std / t
            self.l_avg_conv[t] = l_mean

        self.voltage = self.v_avg_conv[-2]
        self.current = self.c_avg_conv[-2]
        self.loading = self.l_avg_conv[-2]

    def save(self, fname):
        """
        Export as pickle
        Args:
            fname:

        Returns:

        """
        data = [self.S_points, self.V_points, self.I_points]

        with open(fname, "wb") as output_file:
            pkl.dump(data, output_file)

    def open(self, fname):
        """
        open pickle
        Args:
            fname:

        Returns:

        """
        if os.path.exists(fname):
            with open(fname, "rb") as input_file:
                self.S_points, self.V_points, self.I_points = pkl.load(input_file)
            return True
        else:
            warn(fname + " not found")
            return False

    def query_voltage(self, power_array):
        """
        Fantastic function that allows to query the voltage from the sampled points without having to run power flows
        Args:
            power_array: power injections vector

        Returns: Interpolated voltages vector
        """
        x_train = np.hstack((self.S_points.real, self.S_points.imag))
        y_train = np.hstack((self.V_points.real, self.V_points.imag))
        x_test = np.hstack((power_array.real, power_array.imag))

        n, d = x_train.shape

        # #  declare PCA reductor
        # red = PCA()
        #
        # # Train PCA
        # red.fit(x_train, y_train)
        #
        # # Reduce power dimensions
        # x_train = red.transform(x_train)

        # model = MLPRegressor(hidden_layer_sizes=(10*n, n, n, n), activation='relu', solver='adam', alpha=0.0001,
        #                      batch_size=2, learning_rate='constant', learning_rate_init=0.01, power_t=0.5,
        #                      max_iter=3, shuffle=True, random_state=None, tol=0.0001, verbose=True,
        #                      warm_start=False, momentum=0.9, nesterovs_momentum=True, early_stopping=False,
        #                      validation_fraction=0.1, beta_1=0.9, beta_2=0.999, epsilon=1e-08)

        # algorithm : {‘auto’, ‘ball_tree’, ‘kd_tree’, ‘brute’},
        # model = KNeighborsRegressor(n_neighbors=4, algorithm='brute', leaf_size=16)

        model = RandomForestRegressor(10)

        # model = DecisionTreeRegressor()

        # model = LinearRegression()

        model.fit(x_train, y_train)

        y_pred = model.predict(x_test)

        return y_pred[:, :int(d/2)] + 1j * y_pred[:, int(d/2):d]

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

        p, n = self.V_points.shape

        if indices is None:
            if names is None:
                indices = arange(0, n, 1)
                labels = None
            else:
                indices = array(range(len(names)))
                labels = names[indices]
        else:
            labels = names[indices]

        if len(indices) > 0:

            ylabel = ''
            title = ''
            if result_type == 'Bus voltage avg':
                y = self.v_avg_conv[1:-1, indices]
                ylabel = '(p.u.)'
                xlabel = 'Sampling points'
                title = 'Bus voltage \naverage convergence'

            elif result_type == 'Bus current avg':
                y = self.c_avg_conv[1:-1, indices]
                ylabel = '(p.u.)'
                xlabel = 'Sampling points'
                title = 'Bus current \naverage convergence'

            elif result_type == 'Branch loading avg':
                y = self.l_avg_conv[1:-1, indices]
                ylabel = '(%)'
                xlabel = 'Sampling points'
                title = 'Branch loading \naverage convergence'

            elif result_type == 'Bus voltage std':
                y = self.v_std_conv[1:-1, indices]
                ylabel = '(p.u.)'
                xlabel = 'Sampling points'
                title = 'Bus voltage standard \ndeviation convergence'

            elif result_type == 'Bus current std':
                y = self.c_std_conv[1:-1, indices]
                ylabel = '(p.u.)'
                xlabel = 'Sampling points'
                title = 'Bus current standard \ndeviation convergence'

            elif result_type == 'Branch loading std':
                y = self.l_std_conv[1:-1, indices]
                ylabel = '(%)'
                xlabel = 'Sampling points'
                title = 'Branch loading standard \ndeviation convergence'

            elif result_type == 'Bus voltage CDF':
                cdf = CDF(self.V_points.real[:, indices])
                cdf.plot(ax=ax)
                ylabel = '(p.u.)'
                xlabel = 'Probability $P(X \leq x)$'
                title = 'Bus voltage'

            elif result_type == 'Branch loading CDF':
                cdf = CDF(self.loading_points.real[:, indices])
                cdf.plot(ax=ax)
                ylabel = '(p.u.)'
                xlabel = 'Probability $P(X \leq x)$'
                title = 'Branch loading'

            else:
                pass

            if 'CDF' not in result_type:
                df = pd.DataFrame(data=y, columns=labels)

                if len(df.columns) > 10:
                    df.plot(ax=ax, linewidth=LINEWIDTH, legend=False)
                else:
                    df.plot(ax=ax, linewidth=LINEWIDTH, legend=True)
            else:
                df = pd.DataFrame(index=cdf.prob, data=cdf.arr, columns=labels)

            ax.set_title(title)
            ax.set_ylabel(ylabel)
            ax.set_xlabel(xlabel)

            return df

        else:
            return None
