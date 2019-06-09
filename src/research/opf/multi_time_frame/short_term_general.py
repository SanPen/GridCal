from Ordena2.engine.model.asset_model import AssetsModel
from Ordena2.engine.enumerations import *

import numpy as np
import pandas as pd
from scipy.sparse import csc_matrix
from matplotlib import pyplot as plt


class ProblemOptions:

    def __init__(self, use_transmission_grid=True, start_=0, end_=None, use_ramps=True, use_regulation=True):

        self.use_transmission_grid = use_transmission_grid

        self.use_ramps = use_ramps

        self.use_frequency_regulation = use_regulation

        self.start_ = start_

        self.end_ = end_

    def print(self):

        print('Problem options')
        print('Transmission grid', self.use_transmission_grid)
        print('Ramps', self.use_ramps)
        print('Frequency regulation', self.use_frequency_regulation)


class GeneralSolver:

    def __init__(self, problem: AssetsModel, options: ProblemOptions):

        self.problem = problem

        self.options = options

        self.success = False

    def solve(self):
        pass

    @staticmethod
    def Cproduct(M, arr):
        """
        CSC matrix-vector or CSC matrix-matrix product
        :param M: CSC sparse matrix
        :param arr: vector or matrix of object type
        :return: vector or matrix
        """
        n_rows, n_cols = M.shape

        # check dimensional compatibility
        assert (n_cols == arr.shape[0])

        # check that the sparse matrix is indeed of CSC format
        if M.format == 'csc':
            M2 = M
        else:
            M2 = csc_matrix(M)

        if len(arr.shape) == 1:
            """
            Unidimensional sparse matrix - vector product
            """
            res = np.zeros(n_rows, dtype=arr.dtype)
            for i in range(n_cols):
                for ii in range(M2.indptr[i], M2.indptr[i + 1]):
                    j = M2.indices[ii]  # row index
                    res[j] += M2.data[ii] * arr[i]  # C.data[ii] is equivalent to C[i, j]
        else:
            """
            Multidimensional sparse matrix - matrix product
            """
            cols_vec = arr.shape[1]
            res = np.zeros((n_rows, cols_vec), dtype=arr.dtype)

            for k in range(cols_vec):  # for each column of the matrix "vec", do the matrix vector product
                for i in range(n_cols):
                    for ii in range(M2.indptr[i], M2.indptr[i + 1]):
                        j = M2.indices[ii]  # row index
                        res[j, k] += M2.data[ii] * arr[i, k]  # C.data[ii] is equivalent to C[i, j]
        return res


class ProblemResults:

    def __init__(self, time_array, nbus, nbr, ngen, nload, nhydro, nprice):

        nt = len(time_array)

        self.time_array = time_array

        self.bus_names = list()
        self.branch_names = list()
        self.generator_names = list()
        self.load_names = list()
        self.price_names = list()
        self.hydro_names = list()

        # bus results
        self.voltage_modules = np.zeros((nt, nbus), dtype=float)
        self.voltage_angles = np.zeros((nt, nbus), dtype=float)
        self.node_power = np.zeros((nt, nbus), dtype=float)
        self.node_dual_price = np.zeros((nt, nbus), dtype=float)

        # branch results
        self.loading = np.zeros((nt, nbr), dtype=float)
        self.losses = np.zeros((nt, nbr), dtype=float)
        self.branch_power = np.zeros((nt, nbr), dtype=float)
        self.branch_power_overload = np.zeros((nt, nbr), dtype=float)

        # generator results
        self.gen_power = np.zeros((nt, ngen), dtype=float)
        self.gen_pr = np.zeros((nt, ngen), dtype=float)
        self.gen_sr = np.zeros((nt, ngen), dtype=float)
        self.gen_tr = np.zeros((nt, ngen), dtype=float)
        self.gen_ramp_slack = np.zeros((nt, ngen), dtype=float)

        self.gen_indices_by_type = dict()

        # price generators
        self.price_power = np.zeros((nt, nprice), dtype=float)

        # load results
        self.load_power = np.zeros((nt, nload), dtype=float)
        self.load_pr = np.zeros(nt, dtype=float)
        self.load_sr = np.zeros(nt, dtype=float)
        self.load_tr = np.zeros(nt, dtype=float)
        self.load_curtailed_power = np.zeros((nt, nload), dtype=float)

        # hydro results
        self.hydro_water = np.zeros((nt, nhydro), dtype=float)
        self.hydro_water_slack = np.zeros((nt, nhydro), dtype=float)

        self.available_results = dict()

    def link_results(self):
        """
        Re-link the results dictionary
        :return:
        """
        self.available_results = {ResultTypes.VoltageModule: (self.voltage_modules, DeviceType.BusDevice, 'p.u.'),
                                  ResultTypes.VoltageAngle: (self.voltage_angles, DeviceType.BusDevice, 'rad'),
                                  ResultTypes.NodePower: (self.node_power, DeviceType.BusDevice, 'MW'),
                                  ResultTypes.DualPrices: (self.node_dual_price, DeviceType.BusDevice, 'Currency/MWh'),
                                  ResultTypes.BranchLoading: (self.loading, DeviceType.BranchDevice, 'p.u.'),
                                  ResultTypes.BranchLosses: (self.losses, DeviceType.BranchDevice, 'MW'),
                                  ResultTypes.BranchPower: (self.branch_power, DeviceType.BranchDevice, 'MW'),
                                  ResultTypes.BranchPowerOverload: (self.branch_power_overload, DeviceType.BranchDevice, 'MW'),
                                  ResultTypes.GeneratorPower: (self.gen_power, DeviceType.GeneratorDevice, 'MW'),
                                  ResultTypes.GeneratorRampSlacks: (self.gen_ramp_slack, DeviceType.GeneratorDevice, 'MW'),
                                  ResultTypes.PricePower: (self.price_power, DeviceType.PricesDevice, 'MW'),
                                  ResultTypes.LoadPower: (self.load_power, DeviceType.LoadDevice, 'MW'),
                                  ResultTypes.LoadCurtailedPower: (self.load_curtailed_power, DeviceType.LoadDevice, 'MW'),
                                  ResultTypes.HydroWater: (self.hydro_water, DeviceType.WaterNodes, 'm3'),
                                  ResultTypes.HydroWaterSlack: (self.hydro_water_slack, DeviceType.WaterNodes, 'm3'),
                                  ResultTypes.AggregatedGeneration: (None, None, 'MW'),
                                  ResultTypes.PrimaryReg: (None, None, 'MW'),
                                  ResultTypes.SecondaryReg: (None, None, 'MW'),
                                  ResultTypes.TertiaryReg: (None, None, 'MW')}

    def get_aggregated_results_df(self, result_type: ResultTypes):
        """
        Get a DataFrame with the load and generation aggregation
        :return:
        """
        if result_type == ResultTypes.AggregatedGeneration:
            generation_types = list(self.gen_indices_by_type.keys())
            nt = len(self.time_array)
            gen_power = np.zeros((nt, len(generation_types)))
            for i, gen in enumerate(generation_types):
                idx = self.gen_indices_by_type[gen]
                gen_power[:, i] = self.gen_power[:, idx].sum(axis=1)

            load = self.load_power.sum(axis=1)
            curtailed_load = self.load_curtailed_power.sum(axis=1)

            price_power = self.price_power.sum(axis=1)

            data = np.c_[curtailed_load, gen_power, price_power]
            cols = ['Curtailed load']
            cols = cols + [str(elm).replace('DeviceType.', '').replace('Device', '') for elm in generation_types]
            cols = cols + ['Price devices']
            df_gen = pd.DataFrame(data=data, index=self.time_array, columns=cols)

            data = np.c_[load]
            cols = ['Load']
            df_load = pd.DataFrame(data=data, index=self.time_array, columns=cols)

        elif result_type == ResultTypes.PrimaryReg:

            df_gen = pd.DataFrame(data=self.gen_pr, index=self.time_array, columns=self.generator_names)
            df_load = pd.DataFrame(data=self.load_pr, index=self.time_array, columns=['Load'])

        elif result_type == ResultTypes.SecondaryReg:

            df_gen = pd.DataFrame(data=self.gen_sr, index=self.time_array, columns=self.generator_names)
            df_load = pd.DataFrame(data=self.load_sr, index=self.time_array, columns=['Load'])

        elif result_type == ResultTypes.TertiaryReg:

            df_gen = pd.DataFrame(data=self.gen_tr, index=self.time_array, columns=self.generator_names)
            df_load = pd.DataFrame(data=self.load_tr, index=self.time_array, columns=['Load'])

        else:
            raise Exception('Result type unknown: ' + str(result_type))

        return df_load, df_gen

    def get_df(self, result_type: ResultTypes, element_indices, element_names):
        """

        :param result_type:
        :param element_indices:
        :param element_names:
        :return:
        """
        data, device_type, units = self.available_results[result_type]

        if element_indices is None or len(element_indices) == 0:
            df = pd.DataFrame(data=data,
                              columns=element_names,
                              index=self.time_array)
        else:
            df = pd.DataFrame(data=data[:, element_indices],
                              columns=np.array(element_names)[element_indices],
                              index=self.time_array)

        return df, units

    def plot(self, result_type: ResultTypes, element_indices, element_names, ax=None):
        """

        :param result_type:
        :param element_indices:
        :param element_names:
        :param ax:
        :return:
        """

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        if result_type in [ResultTypes.AggregatedGeneration,
                           ResultTypes.PrimaryReg,
                           ResultTypes.SecondaryReg,
                           ResultTypes.TertiaryReg]:
            _, _, units = self.available_results[result_type]
            df_load, df_gen = self.get_aggregated_results_df(result_type)
            df_gen.plot.area(ax=ax)
            df_load.plot(ax=ax)
            df = pd.concat((df_gen, df_load), axis=1)
        else:
            df, units = self.get_df(result_type, element_indices, element_names)
            if df.shape[1] > 0:
                df.plot(ax=ax)
            else:
                print('Empty', result_type)

        ax.set_ylabel(units)

        return df

    def get_buses_df(self, t):
        """

        :param t:
        :return:
        """
        data = np.c_[self.voltage_modules[t, :],
                     self.voltage_angles[t, :],
                     self.node_power[t, :],
                     self.node_dual_price[t, :]]

        cols = ['Vm', 'Va', 'Power (MW)', 'Dual prices (€/MW)']
        if len(self.bus_names) > 0:
            return pd.DataFrame(data=data, columns=cols, index=self.bus_names)
        else:
            return pd.DataFrame(data=data, columns=cols)

    def get_branches_df(self, t):
        """

        :param t:
        :return:
        """
        data = np.c_[self.loading[t, :],
                     self.branch_power[t, :],
                     self.losses[t, :],
                     self.branch_power_overload[t, :]]

        cols = ['Loading (p.u.)', 'Power (MW)', 'Losses (MW)',  'Overload (MW)']
        if len(self.branch_names) > 0:
            return pd.DataFrame(data=data, columns=cols, index=self.branch_names)
        else:
            return pd.DataFrame(data=data, columns=cols)

    def get_generators_df(self, t):
        """

        :param t:
        :return:
        """
        data = np.c_[self.gen_power[t, :],
                     self.gen_ramp_slack[t, :]]

        cols = ['Power (MW)', 'Ramp slack (MW)']
        if len(self.generator_names) > 0:
            return pd.DataFrame(data=data, columns=cols, index=self.generator_names)
        else:
            return pd.DataFrame(data=data, columns=cols)

    def get_price_devices_df(self, t):
        """

        :param t:
        :return:
        """
        data = np.c_[self.price_power[t, :]]

        cols = ['Power (MW)']
        if len(self.generator_names) > 0:
            return pd.DataFrame(data=data, columns=cols, index=self.price_names)
        else:
            return pd.DataFrame(data=data, columns=cols)

    def get_loads_df(self, t):
        """
        Get pandas DataFrame that contains the Loads
        :param t: time step
        :return: DataFrame
        """
        data = np.c_[self.load_power[t, :], self.load_curtailed_power[t, :]]
        cols = ['Power (MW)', 'Curtailed power (MW)']
        return pd.DataFrame(data=data, columns=cols, index=self.load_names)

    def print(self, t):
        """
        Print the problem
        """
        print()
        print('#' * 80)
        print('Results at t:', t, ', time:', str(self.time_array[t]).replace('T', ' '))
        print('#' * 80)

        print('Buses:\n', self.get_buses_df(t=t))
        print('\nBranches:\n', self.get_branches_df(t=t))
        print('\nGenerators:\n', self.get_generators_df(t=t))
        print('\nPrice devices:\n', self.get_price_devices_df(t=t))
        print('\nLoads:\n', self.get_loads_df(t=t))
