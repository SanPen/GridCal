# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from GridCalEngine.basic_structures import CDF
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.enumerations import StudyResultsType, ResultTypes, DeviceType


class StochasticPowerFlowResults(ResultsTemplate):

    def __init__(self, n, m, p, bus_names, branch_names, bus_types):
        """
        Constructor
        @param n: number of nodes
        @param m: number of Branches
        @param p: number of points (rows)
        """
        ResultsTemplate.__init__(self,
                                 name='Stochastic Power Flow',
                                 available_results={
                                     ResultTypes.BusResults: [ResultTypes.BusVoltageAverage,
                                                              ResultTypes.BusVoltageStd,
                                                              ResultTypes.BusVoltageCDF,
                                                              ResultTypes.BusPowerCDF],
                                     ResultTypes.BranchResults: [ResultTypes.BranchPowerAverage,
                                                                 ResultTypes.BranchPowerStd,
                                                                 ResultTypes.BranchPowerCDF,
                                                                 ResultTypes.BranchLoadingAverage,
                                                                 ResultTypes.BranchLoadingStd,
                                                                 ResultTypes.BranchLoadingCDF,
                                                                 ResultTypes.BranchLossesAverage,
                                                                 ResultTypes.BranchLossesStd,
                                                                 ResultTypes.BranchLossesCDF]
                                 },
                                 time_array=None,
                                 clustering_results=None,
                                 study_results_type=StudyResultsType.StochasticPowerFlow)

        self.points_number = p

        self.bus_names = bus_names
        self.branch_names = branch_names
        self.bus_types = bus_types

        self.S_points = np.zeros((p, n), dtype=complex)
        self.V_points = np.zeros((p, n), dtype=complex)
        self.Sbr_points = np.zeros((p, m), dtype=complex)
        self.loading_points = np.zeros((p, m), dtype=complex)
        self.losses_points = np.zeros((p, m), dtype=complex)

        self.error_series = list()

        self.voltage = np.zeros(n)
        self.loading = np.zeros(m)
        self.sbranch = np.zeros(m)
        self.losses = np.zeros(m)

        # magnitudes standard deviation convergence
        self.v_std_conv = None
        self.s_std_conv = None
        self.l_std_conv = None
        self.loss_std_conv = None

        # magnitudes average convergence
        self.v_avg_conv = None
        self.s_avg_conv = None
        self.l_avg_conv = None
        self.loss_avg_conv = None

        # TODO: Register results

    def append_batch(self, mcres):
        """
        Append a batch (a StochasticPowerFlowResults object) to this object
        @param mcres: StochasticPowerFlowResults object
        @return:
        """
        self.S_points = np.vstack((self.S_points, mcres.S_points))
        self.V_points = np.vstack((self.V_points, mcres.V_points))
        self.Sbr_points = np.vstack((self.Sbr_points, mcres.Sbr_points))
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
        ni, m = self.Sbr_points.shape
        step = 1
        nn = int(np.floor(p / step) + 1)
        self.v_std_conv = np.zeros((nn, n))
        self.s_std_conv = np.zeros((nn, m))
        self.l_std_conv = np.zeros((nn, m))
        self.loss_std_conv = np.zeros((nn, m))
        self.v_avg_conv = np.zeros((nn, n))
        self.s_avg_conv = np.zeros((nn, m))
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

            v = np.abs(self.V_points[t, :])
            c = self.Sbr_points[t, :].real
            l = self.loading_points[t, :].real
            loss = self.losses_points[t, :].real

            v_mean += (v - v_mean) / t
            v_std += (v - v_mean) * (v - v_mean_prev)
            self.v_avg_conv[t] = v_mean
            self.v_std_conv[t] = v_std / t

            c_mean += (c - c_mean) / t
            c_std += (c - c_mean) * (c - c_mean_prev)
            self.s_std_conv[t] = c_std / t
            self.s_avg_conv[t] = c_mean

            l_mean += (l - l_mean) / t
            l_std += (l - l_mean) * (l - l_mean_prev)
            self.l_std_conv[t] = l_std / t
            self.l_avg_conv[t] = l_mean

            loss_mean += (loss - loss_mean) / t
            loss_std += (loss - loss_mean) * (loss - loss_mean_prev)
            self.loss_std_conv[t] = loss_std / t
            self.loss_avg_conv[t] = loss_mean

        self.voltage = self.v_avg_conv[-2]
        self.sbranch = self.s_avg_conv[-2]
        self.loading = self.l_avg_conv[-2]
        self.losses = self.loss_avg_conv[-2]

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {'P': self.S_points.real.tolist(),
                'Q': self.S_points.imag.tolist(),
                'Vm': np.abs(self.V_points).tolist(),
                'Va': np.angle(self.V_points).tolist(),
                'Ibr_real': self.Sbr_points.real.tolist(),
                'Ibr_imag': self.Sbr_points.imag.tolist(),
                'Sbr_real': self.Sbr_points.real.tolist(),
                'Sbr_imag': self.Sbr_points.imag.tolist(),
                'loading': np.abs(self.loading_points).tolist(),
                'losses': np.abs(self.losses_points).tolist()}
        return data

    def query_voltage(self, power_array):
        """
        Fantastic function that allows to query the voltage from the sampled points without having to run power Sf
        Args:
            power_array: power Injections vector

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

        # model = MLPRegressor(hidden_layer_sizes=(10*n, n, n, n), activation='relu', solver_type='adam', alpha=0.0001,
        #                      batch_size=2, learning_rate='constant', learning_rate_init=0.01, power_t=0.5,
        #                      max_iter=3, shuffle=True, random_state=None, tol=0.0001, verbose=True,
        #                      warm_start=False, momentum=0.9, nesterovs_momentum=True, early_stopping=False,
        #                      validation_fraction=0.1, beta_1=0.9, beta_2=0.999, epsilon=1e-08)

        # algorithm : {‘auto’, ‘ball_tree’, ‘kd_tree’, ‘brute’},
        # model = KNeighborsRegressor(n_neighbors=4, algorithm='brute', leaf_size=16)

        model = RandomForestRegressor(10)

        model.fit(x_train, y_train)

        y_pred = model.predict(x_test)

        return y_pred[:, :int(d / 2)] + 1j * y_pred[:, int(d / 2):d]

    def get_index_loading_cdf(self, max_val=1.0):
        """
        Find the elements where the CDF is greater or equal to a value
        :param max_val: value to compare
        :return: indices, associated probability
        """

        # turn the loading real values into CDF
        cdf = CDF(np.abs(self.Sbr_points.real))

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
                prob.append(1 - cdf.prob[many_idx[
                    0]])  # the CDF stores the chance of beign leq than the value, hence the overload is the complementary

        return idx, val, prob, cdf.arr[-1, :]

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """
        Plot the results
        :param result_type:
        :return:
        """
        if result_type == ResultTypes.BusVoltageAverage:
            labels = self.bus_names
            y = self.v_avg_conv[1:-1, :]
            y_label = '(p.u.)'
            x_label = 'Sampling points'

            return ResultsTable(data=y,
                                index=np.arange(0, y.shape[0], 1),
                                idx_device_type=DeviceType.NoDevice,
                                columns=labels,
                                cols_device_type=DeviceType.BusDevice,
                                title=result_type.value,
                                ylabel=y_label,
                                xlabel=x_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchPowerAverage:
            labels = self.branch_names
            y = self.s_avg_conv[1:-1, :]
            y_label = '(MW)'
            x_label = 'Sampling points'
            return ResultsTable(data=y,
                                index=np.arange(0, y.shape[0], 1),
                                idx_device_type=DeviceType.NoDevice,
                                columns=labels,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel=y_label,
                                xlabel=x_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchLoadingAverage:
            labels = self.branch_names
            y = self.l_avg_conv[1:-1, :] * 100.0
            y_label = '(%)'
            x_label = 'Sampling points'
            return ResultsTable(data=y,
                                index=np.arange(0, y.shape[0], 1),
                                idx_device_type=DeviceType.NoDevice,
                                columns=labels,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel=y_label,
                                xlabel=x_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchLossesAverage:
            labels = self.branch_names
            y = self.loss_avg_conv[1:-1, :]
            y_label = '(MVA)'
            x_label = 'Sampling points'
            return ResultsTable(data=y,
                                index=np.arange(0, y.shape[0], 1),
                                idx_device_type=DeviceType.NoDevice,
                                columns=labels,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel=y_label,
                                xlabel=x_label,
                                units=y_label)

        elif result_type == ResultTypes.BusVoltageStd:
            labels = self.bus_names
            y = self.v_std_conv[1:-1, :]
            y_label = '(p.u.)'
            x_label = 'Sampling points'
            return ResultsTable(data=y,
                                index=np.arange(0, y.shape[0], 1),
                                idx_device_type=DeviceType.NoDevice,
                                columns=labels,
                                cols_device_type=DeviceType.BusDevice,
                                title=result_type.value,
                                ylabel=y_label,
                                xlabel=x_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchPowerStd:
            labels = self.branch_names
            y = self.s_std_conv[1:-1, :]
            y_label = '(MW)'
            x_label = 'Sampling points'
            return ResultsTable(data=y,
                                index=np.arange(0, y.shape[0], 1),
                                idx_device_type=DeviceType.NoDevice,
                                columns=labels,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel=y_label,
                                xlabel=x_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchLoadingStd:
            labels = self.branch_names
            y = self.l_std_conv[1:-1, :] * 100.0
            y_label = '(%)'
            x_label = 'Sampling points'
            return ResultsTable(data=y,
                                index=np.arange(0, y.shape[0], 1),
                                idx_device_type=DeviceType.NoDevice,
                                columns=labels,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel=y_label,
                                xlabel=x_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchLossesStd:
            labels = self.branch_names
            y = self.loss_std_conv[1:-1, :]
            y_label = '(MVA)'
            x_label = 'Sampling points'
            return ResultsTable(data=y,
                                index=np.arange(0, y.shape[0], 1),
                                idx_device_type=DeviceType.NoDevice,
                                columns=labels,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel=y_label,
                                xlabel=x_label,
                                units=y_label)

        elif result_type == ResultTypes.BusVoltageCDF:
            labels = self.bus_names
            cdf = CDF(np.abs(self.V_points))
            y_label = '(p.u.)'
            x_label = r"Probability $P(X \leq x)$"
            return ResultsTable(data=cdf.arr,
                                index=cdf.prob,
                                idx_device_type=DeviceType.NoDevice,
                                columns=labels,
                                cols_device_type=DeviceType.BusDevice,
                                title=result_type.value,
                                ylabel=y_label,
                                xlabel=x_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchLoadingCDF:
            labels = self.branch_names
            cdf = CDF(np.abs(self.loading_points.real * 100.0))
            y_label = '(%)'
            x_label = r'Probability $P(X \leq x)$'
            return ResultsTable(data=cdf.arr,
                                index=cdf.prob,
                                idx_device_type=DeviceType.NoDevice,
                                columns=labels,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel=y_label,
                                xlabel=x_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchLossesCDF:
            labels = self.branch_names
            cdf = CDF(np.abs(self.losses_points))
            y_label = '(MVA)'
            x_label = r'Probability $P(X \leq x)$'

            return ResultsTable(data=cdf.arr,
                                index=cdf.prob,
                                idx_device_type=DeviceType.NoDevice,
                                columns=labels,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel=y_label,
                                xlabel=x_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchPowerCDF:
            labels = self.branch_names
            cdf = CDF(self.Sbr_points.real)
            y_label = '(MW)'
            x_label = r'Probability $P(X \leq x)$'
            return ResultsTable(data=cdf.arr,
                                index=cdf.prob,
                                idx_device_type=DeviceType.NoDevice,
                                columns=labels,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel=y_label,
                                xlabel=x_label,
                                units=y_label)

        elif result_type == ResultTypes.BusPowerCDF:
            labels = self.bus_names
            cdf = CDF(self.S_points.real)
            y_label = '(p.u.)'
            x_label = r'Probability $P(X \leq x)$'
            return ResultsTable(data=cdf.arr,
                                index=cdf.prob,
                                idx_device_type=DeviceType.NoDevice,
                                columns=labels,
                                cols_device_type=DeviceType.BusDevice,
                                title=result_type.value,
                                ylabel=y_label,
                                xlabel=x_label,
                                units=y_label)

        else:
            raise Exception('Unsupported result type: ' + str(result_type))
