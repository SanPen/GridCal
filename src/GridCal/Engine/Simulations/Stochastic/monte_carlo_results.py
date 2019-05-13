# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import os
import pickle as pkl
from warnings import warn
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from sklearn.ensemble import RandomForestRegressor

# from GridCal.Engine.NewEngine import NumericalCircuit
from GridCal.Engine.plot_config import LINEWIDTH
from GridCal.Engine.basic_structures import CDF
from GridCal.Engine.Simulations.result_types import ResultTypes


class MonteCarloResults:

    def __init__(self, n, m, p=0):
        """
        Constructor
        @param n: number of nodes
        @param m: number of branches
        @param p: number of points (rows)
        """

        self.n = n

        self.m = m

        self.points_number = p

        self.S_points = np.zeros((p, n), dtype=complex)

        self.V_points = np.zeros((p, n), dtype=complex)

        self.I_points = np.zeros((p, m), dtype=complex)

        self.Sbr_points = np.zeros((p, m), dtype=complex)

        self.loading_points = np.zeros((p, m), dtype=complex)

        self.losses_points = np.zeros((p, m), dtype=complex)

        # self.Vstd = zeros(n, dtype=complex)

        self.error_series = list()

        self.bus_types = np.zeros(n, dtype=int)

        self.voltage = np.zeros(n)
        self.current = np.zeros(m)
        self.loading = np.zeros(m)
        self.sbranch = np.zeros(m)
        self.losses = np.zeros(m)

        # magnitudes standard deviation convergence
        self.v_std_conv = None
        self.c_std_conv = None
        self.l_std_conv = None
        self.loss_std_conv = None

        # magnitudes average convergence
        self.v_avg_conv = None
        self.c_avg_conv = None
        self.l_avg_conv = None
        self.loss_avg_conv = None

        self.available_results = [ResultTypes.BusVoltageAverage,
                                  ResultTypes.BusVoltageStd,
                                  ResultTypes.BusVoltageCDF,
                                  ResultTypes.BusPowerCDF,
                                  ResultTypes.BranchCurrentAverage,
                                  ResultTypes.BranchCurrentStd,
                                  ResultTypes.BranchCurrentCDF,
                                  ResultTypes.BranchLoadingAverage,
                                  ResultTypes.BranchLoadingStd,
                                  ResultTypes.BranchLoadingCDF,
                                  ResultTypes.BranchLossesAverage,
                                  ResultTypes.BranchLossesStd,
                                  ResultTypes.BranchLossesCDF]

    def append_batch(self, mcres):
        """
        Append a batch (a MonteCarloResults object) to this object
        @param mcres: MonteCarloResults object
        @return:
        """
        self.S_points = np.vstack((self.S_points, mcres.S_points))
        self.V_points = np.vstack((self.V_points, mcres.V_points))
        self.I_points = np.vstack((self.I_points, mcres.I_points))
        self.loading_points = np.vstack((self.loading_points, mcres.loading_points))
        self.losses_points = np.vstack((self.losses_points, mcres.loading_points))

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
        nn = int(np.floor(p / step) + 1)
        self.v_std_conv = np.zeros((nn, n))
        self.c_std_conv = np.zeros((nn, m))
        self.l_std_conv = np.zeros((nn, m))
        self.loss_std_conv = np.zeros((nn, m))
        self.v_avg_conv = np.zeros((nn, n))
        self.c_avg_conv = np.zeros((nn, m))
        self.l_avg_conv = np.zeros((nn, m))
        self.loss_avg_conv = np.zeros((nn, m))

        v_mean = np.zeros(n)
        c_mean = np.zeros(m)
        l_mean = np.zeros(m)
        loss_mean = np.zeros(m)
        v_std = np.zeros(n)
        c_std = np.zeros(m)
        l_std = np.zeros(m)
        loss_std = np.zeros(m)

        for t in range(1, p, step):
            v_mean_prev = v_mean.copy()
            c_mean_prev = c_mean.copy()
            l_mean_prev = l_mean.copy()
            loss_mean_prev = loss_mean.copy()

            v = abs(self.V_points[t, :])
            c = abs(self.I_points[t, :])
            l = abs(self.loading_points[t, :])
            loss = abs(self.losses_points[t, :])

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

            loss_mean += (loss - loss_mean) / t
            loss_std += (loss - loss_mean) * (loss - loss_mean_prev)
            self.loss_std_conv[t] = loss_std / t
            self.loss_avg_conv[t] = loss_mean

        self.voltage = self.v_avg_conv[-2]
        self.current = self.c_avg_conv[-2]
        self.loading = self.l_avg_conv[-2]
        self.losses = self.loss_avg_conv[-2]

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {'S': self.S_points,
                'V': self.V_points,
                'Ibr': self.I_points,
                'Sbr': self.Sbr_points,
                'loading': self.loading_points,
                'losses': self.losses_points}
        return data

    def save(self, fname):
        """
        Export as pickle
        """
        with open(fname, "wb") as output_file:
            pkl.dump(self.get_results_dict(), output_file)

    def open(self, fname):
        """
        open pickle
        Args:
            fname: file name
        Returns: true if succeeded, false otherwise

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

        return y_pred[:, :int(d / 2)] + 1j * y_pred[:, int(d / 2):d]

    def get_index_loading_cdf(self, max_val=1.0):
        """
        Find the elements where the CDF is greater or equal to a velue
        :param max_val: value to compare
        :return: indices, associated probability
        """

        # turn the loading real values into CDF
        cdf = CDF(np.abs(self.loading_points.real[:, :]))

        n = cdf.arr.shape[1]
        idx = list()
        val = list()
        prob = list()
        for i in range(n):
            # Find the indices that surpass max_val
            many_idx = np.where(cdf.arr[:, i] > max_val)[0]

            # if there are indices, pick the first; store it and its associated probability
            if len(many_idx) > 0:
                idx.append(i)
                val.append(cdf.arr[many_idx[0], i])
                prob.append(1 - cdf.prob[many_idx[0]])  # the CDF stores the chance of beign leq than the value, hence the overload is the complementary

        return idx, val, prob, cdf.arr[-1, :]

    def plot(self, result_type: ResultTypes, ax=None, indices=None, names=None):
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

        cdf_result_types = [ResultTypes.BusVoltageCDF,
                            ResultTypes.BusPowerCDF,
                            ResultTypes.BranchCurrentCDF,
                            ResultTypes.BranchLoadingCDF,
                            ResultTypes.BranchLossesCDF]

        if indices is None:
            if names is None:
                indices = np.arange(0, n, 1)
                labels = None
            else:
                indices = np.array(range(len(names)))
                labels = names[indices]
        else:
            labels = names[indices]

        if len(indices) > 0:

            y_label = ''
            title = ''
            if result_type == ResultTypes.BusVoltageAverage:
                y = self.v_avg_conv[1:-1, indices]
                y_label = '(p.u.)'
                x_label = 'Sampling points'
                title = 'Bus voltage \naverage convergence'

            elif result_type == ResultTypes.BranchCurrentAverage:
                y = self.c_avg_conv[1:-1, indices]
                y_label = '(p.u.)'
                x_label = 'Sampling points'
                title = 'Bus current \naverage convergence'

            elif result_type == ResultTypes.BranchLoadingAverage:
                y = self.l_avg_conv[1:-1, indices]
                y_label = '(%)'
                x_label = 'Sampling points'
                title = 'Branch loading \naverage convergence'

            elif result_type == ResultTypes.BranchLossesAverage:
                y = self.loss_avg_conv[1:-1, indices]
                y_label = '(MVA)'
                x_label = 'Sampling points'
                title = 'Branch losses \naverage convergence'

            elif result_type == ResultTypes.BusVoltageStd:
                y = self.v_std_conv[1:-1, indices]
                y_label = '(p.u.)'
                x_label = 'Sampling points'
                title = 'Bus voltage standard \ndeviation convergence'

            elif result_type == ResultTypes.BranchCurrentStd:
                y = self.c_std_conv[1:-1, indices]
                y_label = '(p.u.)'
                x_label = 'Sampling points'
                title = 'Bus current standard \ndeviation convergence'

            elif result_type == ResultTypes.BranchLoadingStd:
                y = self.l_std_conv[1:-1, indices]
                y_label = '(%)'
                x_label = 'Sampling points'
                title = 'Branch loading standard \ndeviation convergence'

            elif result_type == ResultTypes.BranchLossesStd:
                y = self.loss_std_conv[1:-1, indices]
                y_label = '(MVA)'
                x_label = 'Sampling points'
                title = 'Branch losses standard \ndeviation convergence'

            elif result_type == ResultTypes.BusVoltageCDF:
                cdf = CDF(np.abs(self.V_points[:, indices]))
                cdf.plot(ax=ax)
                y_label = '(p.u.)'
                x_label = 'Probability $P(X \leq x)$'
                title = result_type.value[0]

            elif result_type == ResultTypes.BranchLoadingCDF:
                cdf = CDF(np.abs(self.loading_points.real[:, indices]))
                cdf.plot(ax=ax)
                y_label = '(p.u.)'
                x_label = 'Probability $P(X \leq x)$'
                title = result_type.value[0]

            elif result_type == ResultTypes.BranchLossesCDF:
                cdf = CDF(np.abs(self.losses_points[:, indices]))
                cdf.plot(ax=ax)
                y_label = '(MVA)'
                x_label = 'Probability $P(X \leq x)$'
                title = result_type.value[0]

            elif result_type == ResultTypes.BranchCurrentCDF:
                cdf = CDF(np.abs(self.I_points[:, indices]))
                cdf.plot(ax=ax)
                y_label = '(kA)'
                x_label = 'Probability $P(X \leq x)$'
                title = result_type.value[0]

            elif result_type == ResultTypes.BusPowerCDF:
                cdf = CDF(np.abs(self.S_points[:, indices]))
                cdf.plot(ax=ax)
                y_label = '(p.u.)'
                x_label = 'Probability $P(X \leq x)$'
                title = result_type.value[0]

            else:
                x_label = ''
                y_label = ''
                title = ''

            if result_type not in cdf_result_types:
                df = pd.DataFrame(data=np.abs(y), columns=labels)
                lines = ax.plot(np.abs(y), linewidth=LINEWIDTH)
                if len(df.columns) < 10:
                    ax.legend(lines, labels, loc='best')
            else:
                df = pd.DataFrame(index=cdf.prob, data=cdf.arr, columns=labels)

            ax.set_title(title)
            ax.set_ylabel(y_label)
            ax.set_xlabel(x_label)

            return df

        else:
            return None

