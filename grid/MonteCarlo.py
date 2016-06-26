import numpy as np
import pandas as pd
from enum import Enum
from multiprocessing import Pool, cpu_count
from warnings import warn
from matplotlib import pyplot as plt
from PyQt4.QtCore import QThread, SIGNAL
from numpy import zeros, r_
import time

from grid.PowerFlow import MultiCircuitPowerFlow
from grid.BusDefinitions import *
from grid.GenDefinitions import *
from grid.TimeSeries import TimeSeries
import grid.InterpolationNDim as interp_nd


class TimeGroups(Enum):
    NoGroup = 0,
    ByDay = 1,
    ByHour = 2


class CDF(object):
    """
    Cumulative density function of a given array f data
    """
    def __init__(self, data):
        # Create the CDF of the data
        # sort the data:
        self.data_sorted = np.sort(data)
        # calculate the proportional values of samples
        self.prob = 1. * np.arange(len(data)) / (len(data) - 1)

    def get_sample(self, npoints=1):
        """
        Samples a number of uniform distributed points and
        returns the corresponding probability values given the CDF.
        @param npoints: Number of points to sample, 1 by default
        @return: Corresponding probabilities
        """
        return np.interp(np.random.uniform(0, 1, npoints), self.prob, self.data_sorted)

    def plot(self, ax=None):
        """
        Plots the CFD
        @param ax: Matplotlib axis to plot into
        @return:
        """
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)
        ax.plot(self.prob, self.data_sorted)
        ax.set_xlabel('$p(x)$')
        ax.set_ylabel('$x$')
        # ax.plot(self.norm_points, self.values, 'x')


class StatisticalCharacterization(object):
    """
    Object to store the statistical characterization
    It is useful because the statistical characterizations can be:
    - not grouped
    - grouped by day
    - grouped by hour
    """
    def __init__(self, gen_P: np.ndarray, load_P: np.ndarray, load_Q: np.ndarray):
        """
        Constructor
        @param gen_P: 2D array with the active power generation profiles (time, generator)
        @param load_P: 2D array with the active power load profiles (time, load)
        @param load_Q: 2D array with the reactive power load profiles time, load)
        @return:
        """
        # Arrays where to store the statistical laws for sampling
        self.gen_P_laws = list()
        self.load_P_laws = list()
        self.load_Q_laws = list()

        # Create a CDF for every profile
        rows, cols = np.shape(gen_P)
        for i in range(cols):
            cdf = CDF(gen_P[:, i])
            self.gen_P_laws.append(cdf)

        rows, cols = np.shape(load_P)
        for i in range(cols):
            cdf = CDF(load_P[:, i])
            self.load_P_laws.append(cdf)

        rows, cols = np.shape(load_Q)
        for i in range(cols):
            cdf = CDF(load_Q[:, i])
            self.load_Q_laws.append(cdf)

    def get_sample(self, load_enabled_idx, gen_enabled_idx, npoints=1):
        """
        Returns a 2D array containing for load and generation profiles, shape (time, load)
        The profile is sampled from the original data CDF functions

        @param npoints: number of sampling points
        @return:
        PG: generators profile
        S: loads profile
        """
        # nlp = len(self.load_P_laws)
        # nlq = len(self.load_Q_laws)
        # ngp = len(self.gen_P_laws)
        nlp = len(load_enabled_idx)
        ngp = len(gen_enabled_idx)

        if len(self.load_P_laws) != len(self.load_Q_laws):
            raise Exception('Different number of elements in the load active and reactive profiles.')

        P = [None] * nlp
        Q = [None] * nlp
        PG = [None] * ngp

        k = 0
        for i in load_enabled_idx:
            P[k] = self.load_P_laws[i].get_sample(npoints)
            Q[k] = self.load_Q_laws[i].get_sample(npoints)
            k += 1

        k = 0
        for i in gen_enabled_idx:
            PG[k] = self.gen_P_laws[i].get_sample(npoints)
            k += 1

        P = np.array(P)
        Q = np.array(Q)
        S = P + 1j * Q

        PG = np.array(PG)

        return PG.transpose(), S.transpose()

    def plot(self, ax):
        """
        Plot this statistical characterization
        @param ax:  matplotlib index
        @return:
        """
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        for cdf in self.gen_P_laws:
            ax.plot(cdf.prob, cdf.data_sorted, color='r', marker='x')
        for cdf in self.load_P_laws:
            ax.plot(cdf.prob, cdf.data_sorted, color='g',  marker='x')
        for cdf in self.load_Q_laws:
            ax.plot(cdf.prob, cdf.data_sorted, color='b',  marker='x')
        ax.set_xlabel('$p(x)$')
        ax.set_ylabel('$x$')


def classify_by_hour(t: pd.DatetimeIndex):
    """
    Passes an array of TimeStamps to an array of arrays of indices
    classified by hour of the year
    @param t: Pandas time Index array
    @return: list of lists of integer indices
    """
    n = len(t)

    offset = t[0].hour * t[0].dayofyear
    mx = t[n-1].hour * t[n-1].dayofyear

    arr = list()

    for i in range(mx-offset+1):
        arr.append(list())

    for i in range(n):
        hourofyear = t[i].hour * t[i].dayofyear
        arr[hourofyear-offset].append(i)

    return arr


def classify_by_day(t: pd.DatetimeIndex):
    """
    Passes an array of TimeStamps to an array of arrays of indices
    classified by day of the year
    @param t: Pandas time Index array
    @return: list of lists of integer indices
    """
    n = len(t)

    offset = t[0].dayofyear
    mx = t[n-1].dayofyear

    arr = list()

    for i in range(mx-offset+1):
        arr.append(list())

    for i in range(n):
        hourofyear = t[i].dayofyear
        arr[hourofyear-offset].append(i)

    return arr


class MonteCarlo(QThread):
    """
    This class imports a set of generation and load profiles and characterizes them statistically so an
    infinite number of in-range samples can be withdrawn. The aim is to perform a MonteCarlo simulation
    using those samples
    """
    def __init__(self, base_time_series_object: TimeSeries, group_by: TimeGroups):
        """
        Class constructor
        Args:
            base_time_series_object: TimeSeries object from which to take the data
            group_by: Option for date grouping
        """

        QThread.__init__(self)

        self.cancel = False

        # store how the data is grouped
        self.group_by = group_by

        # obtain time classifications
        self.time_indices = None

        self.time_series = base_time_series_object

        # run options
        self.tolerance = 1e-3
        self.max_iterations = 1000
        self.pf_tolerance = 1e-3
        self.pf_max_iterations = 20
        self.enforce_reactive_power_limits = False

        # intermediate results
        self.num_eval = 0
        self.V_sum = None
        self.I_sum = None
        self.Loading_sum = None
        self.Losses_sum = None

        # self.V2 = None
        # self.I2 = None
        # self.Loading2 = None
        # self.Losses2 = None

        self.V_avg = None
        self.I_avg = None
        self.Loading_avg = None
        self.Losses_avg = None

        self.V_std = None
        self.I_std = None
        self.Loading_std = None
        self.Losses_std = None

        self.V_avg_series = None
        self.V_std_series = None
        self.error_series = None

        # interpolation tensor structure
        self.power_injection = None
        self.voltage_values = None
        self.loading_values = None

        # for the grouping indices
        if group_by == TimeGroups.ByDay:
            self.time_indices = classify_by_day(base_time_series_object.time)
        elif group_by == TimeGroups.ByHour:
            self.time_indices = classify_by_hour(base_time_series_object.time)
        else:
            self.time_indices = [np.arange(0, len(base_time_series_object.time))]

        # obtain statistical groups
        self.n_groups = len(self.time_indices)

        # Statistical characterization of the complete grid for the time interval
        self.stat_groups = [None] * self.n_groups

        # time interval start time stamp
        self.t_from = [None] * self.n_groups

        # time interval end time stamp
        self.t_to = [None] * self.n_groups

        # fill the values for each group
        for i in range(self.n_groups):
            # get the pertinent data slice
            GP = base_time_series_object.gen_profiles[self.time_indices[i]]
            LP = base_time_series_object.load_profiles.real[self.time_indices[i]]
            LQ = base_time_series_object.load_profiles.imag[self.time_indices[i]]
            # get the start and end timestamps
            self.t_from[i] = base_time_series_object.time.values[self.time_indices[i][0]]
            self.t_to[i] = base_time_series_object.time.values[self.time_indices[i][len(self.time_indices[i])-1]]
            # compute the statistical characterization of the sliced data
            self.stat_groups[i] = StatisticalCharacterization(GP, LP, LQ)

        print('Monte Carlo initialized')

    def set_run_options(self, tol=1e-3, max_it=1000, tol_pf=1e-3, max_it_pf=10, enforce_reactive_power_limits=True):
        """
        Set the execution parameters in the power flow object and the Monte Carlo run
        @param tol: Standard deviation tolerance
        @param max_it: Maximum number of iterations
        @param tol_pf: Power flow tolerance
        @param max_it_pf: Power flow maximum iterations
        @param enforce_reactive_power_limits: Enforce the reactive power limits
        @return: Nothing
        """
        self.tolerance = tol
        self.max_iterations = max_it
        self.pf_tolerance = tol_pf
        self.pf_max_iterations = max_it_pf
        self.enforce_reactive_power_limits = enforce_reactive_power_limits

    def plot_stc(self, idx, ax):
        """
        Plot the statistical characterization at the given index
        @param idx: index of self.stat_groups
        @param ax: matplotlib axis
        @return:
        """
        self.stat_groups[idx].plot(ax)

    def end_process(self):
        """
        set the cancel flag to true
        @return:
        """
        self.cancel = True

    def initialize(self):
        """
        Initialize all the results variables
        @return:
        """
        nb = len(self.time_series.pf.bus)
        nl = len(self.time_series.pf.branch)

        self.num_eval = 0

        self.V_sum = zeros(nb, dtype=complex)
        self.I_sum = zeros(nl, dtype=complex)
        self.Loading_sum = zeros(nl, dtype=complex)
        self.Losses_sum = zeros(nl, dtype=complex)

        # self.V2 = zeros(nb, dtype=complex)
        # self.I2 = zeros(nl, dtype=complex)
        # self.Loading2 = zeros(nl, dtype=complex)
        # self.Losses2 = zeros(nl, dtype=complex)

        self.V_avg = zeros(nb, dtype=complex)
        self.I_avg = zeros(nl, dtype=complex)
        self.Loading_avg = zeros(nl, dtype=complex)
        self.Losses_avg = zeros(nl, dtype=complex)

        self.V_std = zeros(nb, dtype=complex)
        self.I_std = zeros(nl, dtype=complex)
        self.Loading_std = zeros(nl, dtype=complex)
        self.Losses_std = zeros(nl, dtype=complex)

        self.V_avg_series = list()
        self.V_std_series = list()
        self.error_series = list()

        # interpolation tensor structure
        self.power_injection = list()
        self.voltage_values = list()
        self.loading_values = list()

    def process_values(self, S, V, I, Loading, Losses):
        """
        After each power flow simulation, the results of it are stored and processed to obtain the convergence
        @param S: Array of power injections in p.u.
        @param V: Array of voltage values in p.u.
        @param I: Array of node current injections in p.u.
        @param Loading: Array of branch loading values
        @param Losses: Array of branch losses values
        @return: Nothing
        """

        # store the tensor values
        self.power_injection.append(S.copy())
        self.voltage_values.append(V.copy())
        self.loading_values.append(Loading.copy())

        # increase the number of evaluations
        self.num_eval += 1

        # sum of values
        self.V_sum += V
        self.I_sum += I
        self.Loading_sum += Loading
        self.Losses_sum += Losses

        # sum of squares
        # self.V2 += V**2
        # self.I2 += I**2
        # self.Loading2 += Loading**2
        # self.Losses2 += Losses**2

        # Mean
        self.V_avg = self.V_sum / self.num_eval
        self.I_avg = self.I_sum / self.num_eval
        self.Loading_avg = self.Loading_sum / self.num_eval
        self.Losses_avg = self.Losses_sum / self.num_eval

        # Variance
        if self.num_eval > 1:
            self.V_std = (V - self.V_avg)**2 / (self.num_eval - 1)
            self.I_std = (I - self.I_avg)**2 / (self.num_eval - 1)
            self.Loading_std = (Loading - self.Loading_avg)**2 / (self.num_eval - 1)
            self.Losses_std = (Losses - self.Losses_avg)**2 / (self.num_eval - 1)

        self.V_avg_series.append(self.V_avg)
        self.V_std_series.append(self.V_std)

        # std_dev = max(r_[self.V_std, self.I_std, self.Loading_std, self.Losses_std])
        std_dev = max(abs(self.V_std))
        if self.num_eval > 1:
            return std_dev
        else:
            return 1

    def consolidate(self):
        """
        Once the simulation is finished, the list are turned into arrays
        @return: Nothing
        """
        # store the tensor values
        self.power_injection = np.array(self.power_injection)
        self.voltage_values = np.array(self.voltage_values)
        self.loading_values = np.array(self.loading_values)

    def worker(self, args):
        """
        Element that processes a MonteCarlo iteration
        @param args: Power flow instance
        @return:
        """
        # pf: Power flow instance
        pf = args

        std_dev = zeros(self.n_groups)

        # get the enables for modification:
        # since the power flow object is sent already with user modifications it should be up to date on every run
        loads_enabled_for_change = np.where(self.time_series.pf.bus[:, FIX_POWER_BUS] == 0)[0]
        gens_enabled_for_change = np.where(self.time_series.pf.gen[:, FIX_POWER_GEN] == 0)[0]

        # this is the base load values, only those enabled for change will be replaced in the loop
        S = self.time_series.load_p_0 + 1j * self.time_series.load_q_0
        # this is the base generation values, only those enabled for change will be replaced in the loop
        Pgen = self.time_series.gen_p_0

        for i in range(self.n_groups):  # for every time group get a sample and run a power flow

            # get stochastic sample
            Pgen_mod, Smod = self.stat_groups[i].get_sample(loads_enabled_for_change, gens_enabled_for_change)

            # modify the default arrays withe values that are set to change during the simulation
            Pgen[gens_enabled_for_change] = Pgen_mod[0]
            S[loads_enabled_for_change] = Smod[0]

            # Setting the states
            pf.set_generators(Pgen)
            pf.set_loads(np.real(S), np.imag(S))

            # run the power flow
            pf.run()

            # gather the results (the results are ensured to have the same length as the time master)
            std_dev[i] = self.process_values(pf.power, pf.voltage, pf.current, pf.loading, pf.losses)

            # if self.cancel:
            #     continue_run = False

        return max(std_dev)

    def run(self):
        """
        Run the monte carlo algorithm using a single thread
        @return:
        """
        start = time.clock()

        self.cancel = False

        # initialize the structures to store the data and perform the average
        self.initialize()

        continue_run = True

        prog = 0.0
        iter = 0
        err = 0
        std_sum = 0
        self.emit(SIGNAL('progress(float)'), prog)

        while continue_run:

            # Execute time series of group runs
            mx_stdev = self.worker(self.time_series.pf)

            # Increase iteration
            iter += 1

            std_sum += mx_stdev
            err = std_sum / iter
            if err == 0:
                err = 1e-200  # to avoid division by zeros
            self.error_series.append(err)

            # emmit the progress signal
            prog = 100 * self.tolerance / err
            if prog > 100:
                prog = 100
            self.emit(SIGNAL('progress(float)'), prog)

            if self.cancel:
                continue_run = False

            # check if to stop
            if iter >= self.max_iterations or err <= self.tolerance:
                continue_run = False

        # consolidate the results
        self.consolidate()

        # send the finnish signal
        self.emit(SIGNAL('done()'))

        elapsed = (time.clock() - start)
        print('Elapsed time: ', elapsed)

    def plot_convergence(self):
        """
        Plot the Monte Carlo run convergence
        @return:
        """
        print('plotting...')
        plt.figure()
        plt.subplot(1, 3, 1)
        plt.plot(self.V_avg_series)
        plt.title('Voltage average evolution')

        plt.subplot(1, 3, 2)
        plt.plot(self.V_std_series)
        plt.title('Voltage standard deviation evolution')
        plt.yscale('log')

        plt.subplot(1, 3, 3)
        plt.plot(self.error_series)
        plt.title('Error: Standard deviation average')
        plt.yscale('log')

        plt.show()


class MonteCarloMultiThread(MonteCarlo):
    """
    Inherits all the MonteCarlo functionality and overrides the run function to have it implemented
    making use of al the computer cores
    """

    def run(self):
        """
        Run the Monte carlo algorithm using multi-thread techniques
        @return:
        """
        self.cancel = False

        self.initialize()

        continue_run = True

        print('Monte Carlo run, Not implemented')
        prog = 0.0
        iter = 0
        err = 0
        std_sum = 0
        self.emit(SIGNAL('progress(float)'), prog)

        # setup the multi-treading variables
        cores = cpu_count()
        pool = Pool(processes=cores)

        pf_instances = list()
        for i in range(cores):
            pf_instances.append(self.time_series.pf)

        while continue_run:

            # Execute time series of group runs in parallel
            mx_stdev_arr = pool.map(self.worker, pf_instances)

            # Increase iteration
            iter += 1

            std_sum += max(mx_stdev_arr)
            err = std_sum / iter
            if err == 0:
                err = 1e-200  # to avoid division by zeros
            self.error_series.append(err)

            # emmit the progress signal
            prog = 100 * self.tolerance / err
            if prog > 100:
                prog = 100
            self.emit(SIGNAL('progress(float)'), prog)
            # self.emit(SIGNAL('progress(float)'), 100 * (iter+1)/self.max_iterations)

            if self.cancel:
                continue_run = False

            # check if to stop
            if iter >= self.max_iterations or err <= self.tolerance:
                continue_run = False

        # close pools
        pool.close()
        pool.terminate()

        # send the finnish signal
        self.emit(SIGNAL('done()'))


class StochasticCollocation(QThread):

    def __init__(self, ts: TimeSeries, level):

        QThread.__init__(self)

        self.time_series = ts

        self.level = level

        # get the enables for modification:
        # since the power flow object is sent already with user modifications it should be up to date on every run
        loads_enabled_for_change = np.where(self.time_series.pf.bus[:, FIX_POWER_BUS] == 0)[0]
        gens_enabled_for_change = np.where(self.time_series.pf.gen[:, FIX_POWER_GEN] == 0)[0]

        # this is the base load values, only those enabled for change will be replaced in the loop
        self.S = self.time_series.load_p_0 + 1j * self.time_series.load_q_0
        # this is the base generation values, only those enabled for change will be replaced in the loop
        self.Pgen = self.time_series.gen_p_0

        self.gen_idx = list()
        self.load_idx = list()
        self.type = list()  # 1:P, 2:Q, 3:Pgen
        # compile the dataseries
        self.data_series = list()
        for i in loads_enabled_for_change:
            serie = self.time_series.load_profiles[:, i]
            if sum(serie.real) != 0.0:
                self.data_series.append(serie.real)
                self.load_idx.append(i)
                self.type.append(1)

            if sum(serie.imag) != 0.0:
                self.data_series.append(serie.imag)
                self.load_idx.append(i)
                self.type.append(2)

        for i in gens_enabled_for_change:
            serie = self.time_series.gen_profiles[:, i]
            if sum(serie) != 0.0:
                self.data_series.append(serie)
                self.gen_idx.append(i)
                self.type.append(3)

        self.ng_used = len(self.gen_idx)
        self.nl_used = len(self.load_idx)

        print('Stochastic collocation')

    def run(self):
        print('Stochastic collocation run')

        prog = 0.0
        self.emit(SIGNAL('progress(float)'), prog)

        self.level = 2

        ################################################################################################################
        # Pre-process
        ################################################################################################################

        roots_list, sampling_points, Weights, index_tensor, \
        max_number_of_samples, number_of_samples_per_dimension = self.pre_process(self.level, self.data_series)

        ################################################################################################################
        # Run the power flows
        ################################################################################################################

        # dummy processing
        number_of_results = 2
        number_of_combinations = len(sampling_points)
        results = np.zeros((number_of_combinations, number_of_results))
        sampling_points_descaled = sf.tensor_de_scaling(self.data_series, sampling_points)
        for i in range(number_of_combinations):
            m = 1
            s = 0
            for v in sampling_points_descaled[i, :]:  # loop for every value of the combination i
                m *= v
                s += v
            results[i, 0] = np.sin(s) + s * s
            results[i, 1] = np.cos(m) + s * m

        ################################################################################################################
        # Run the power flows
        ################################################################################################################

        # to be done...

        # send the finnish signal
        self.emit(SIGNAL('done()'))

    def pre_process(self, level, data_series):
        """
        Prepare the data for execution
        @param level: Precision level (less than 5)
        @param data_series: List of data series
        @return:
        """
        ###############################################################################
        # Pre-processing:
        ###############################################################################
        # level = 2
        # data_series = list()  # list of arrays
        dimensions = len(data_series)  # number of dimensions
        levels = [level] * dimensions  # array of levels at each dimension

        # Orthogonalize every data set to get the sampling points
        roots_list = list()
        weights = list()
        max_number_of_samples = list()
        data_series1 = list()
        number_of_samples_per_dimension = list()
        self.emit(SIGNAL('progress(float)'), 0)
        for idx_d in range(dimensions):
            # Sort and scale
            data1 = sf.sort_and_scale(data_series[idx_d])
            data_series1.append(data1)
            NL = levels[idx_d]

            # plt.figure(idx_d)
            # plt.plot(data1)
            # print(data1)

            # Gram-Schmidt Orthogonalization
            print('Obtaining quadrature points for data series ' + str(idx_d))
            roots, Z, NS = sf.get_quadrature_points(data1, NL, 0)

            number_of_samples_per_dimension.append(NS)
            roots_list.append(roots)
            weights.append(Z)
            max_number_of_samples.append(NS)

            prog = 100 * (idx_d+1) / dimensions
            self.emit(SIGNAL('progress(float)'), prog)

        # print('Creating full-tensor:')
        # sampling_points, Weights, index_tensor = sf.full_tensor(levels, roots_list, weights)

        print('Creating sparse-tensor:')
        sampling_points_s, Weights_s, index_tensor_s, sub_tensor_results_map = sf.sparse_grids_tensor(level, roots_list,
                                                                                                      weights)

        return roots_list, sampling_points, Weights, index_tensor, max_number_of_samples, number_of_samples_per_dimension

    def post_process(self, dimensions, weights, results, index_tensor, roots_list, num_samples_per_dimension,
                     single_level, levels, sub_tensor_results_map):
        """

        @param dimensions:
        @param weights:
        @param results:
        @param index_tensor:
        @param roots_list:
        @param num_samples_per_dimension:
        @param single_level:
        @param levels:
        @param sub_tensor_results_map:
        @return:
        """
        print('')

        # computing of the moments
        print('Post-Processing full-tensor:')
        moments = sf.moments_computation(weights, results)

        print('Post-Processing sparse-tensor:')
        # moments_s = sf.moments_computation(Weights_s, results_s)

        # compute the moments by generating new points and performing Monte Carlo
        sol_idx = 0
        # new monte carlo points in the interval [-1, 1]
        number_of_mc_points = 300
        new_points = np.random.rand(number_of_mc_points, dimensions) * 2 - 1  # Only to TEST!!

        interpolated_points = sf.interpolation_for_full_tensor(new_points, index_tensor, results, roots_list,
                                                               num_samples_per_dimension, levels)
        # (new_points, sub_tensor_results_map, results, roots, Nsd, NL, D,  w):

        interpolated_points_s = sf.interpolation_for_sparse_tensor(new_points, sub_tensor_results_map, results,
                                                                   roots_list,
                                                                   num_samples_per_dimension, levels, dimensions,
                                                                   single_level)

        print('MC average = ' + str(np.average(interpolated_points)))