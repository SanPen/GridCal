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
from datetime import datetime, timedelta
from enum import Enum
from warnings import warn
import networkx as nx
import pandas as pd
import pulp
import json
import multiprocessing
from networkx import connected_components
from numpy import complex, double, sqrt, zeros, ones, nan_to_num, exp, conj, ndarray, vstack, power, delete, where, \
    r_, Inf, linalg, maximum, array, nan, shape, arange, sort, interp, iscomplexobj, c_, argwhere, floor
from poap.controller import SerialController
from pyDOE import lhs
from pySOT import *
from scipy.sparse import csc_matrix, lil_matrix, hstack as hstack_s, vstack as vstack_s
from scipy.sparse.linalg import inv
from sklearn.ensemble import RandomForestRegressor


from matplotlib import pyplot as plt

from PyQt5.QtCore import QThread, QRunnable, pyqtSignal
from PyQt5.QtWidgets import QMessageBox

from GridCal.Engine.Numerical.ContinuationPowerFlow import continuation_nr
from GridCal.Engine.Numerical.LinearizedPF import dcpf, lacpf
from GridCal.Engine.Numerical.HELM import helm
from GridCal.Engine.Numerical.JacobianBased import IwamotoNR, Jacobian, LevenbergMarquardtPF
from GridCal.Engine.Numerical.FastDecoupled import FDPF
from GridCal.Engine.Numerical.SC import short_circuit_3p
from GridCal.Engine.Numerical.SE import solve_se_lm
from GridCal.Engine.Numerical.DynamicModels import DynamicModels, dynamic_simulation

########################################################################################################################
# Set Matplotlib global parameters
########################################################################################################################
if 'fivethirtyeight' in plt.style.available:
    plt.style.use('fivethirtyeight')

SMALL_SIZE = 8
MEDIUM_SIZE = 10
BIGGER_SIZE = 12
LINEWIDTH = 1

LEFT = 0.12
RIGHT = 0.98
TOP = 0.8
BOTTOM = 0.2
plt.rc('font', size=SMALL_SIZE)  # controls default text sizes
plt.rc('axes', titlesize=SMALL_SIZE)  # fontsize of the axes title
plt.rc('axes', labelsize=SMALL_SIZE)  # fontsize of the x and y labels
plt.rc('xtick', labelsize=SMALL_SIZE)  # fontsize of the tick labels
plt.rc('ytick', labelsize=SMALL_SIZE)  # fontsize of the tick labels
plt.rc('legend', fontsize=SMALL_SIZE)  # legend fontsize
plt.rc('figure', titlesize=MEDIUM_SIZE)  # fontsize of the figure title


########################################################################################################################
# Enumerations
########################################################################################################################


class NodeType(Enum):
    PQ = 1,
    PV = 2,
    REF = 3,
    NONE = 4,
    STO_DISPATCH = 5  # Storage dispatch, in practice it is the same as REF


class MeasurementType(Enum):
    Pinj = 1,
    Qinj = 2,
    Vmag = 3,
    Pflow = 4,
    Qflow = 5,
    Iflow = 6


class SolverType(Enum):
    NR = 1
    NRFD_XB = 2
    NRFD_BX = 3
    GAUSS = 4
    DC = 5,
    HELM = 6,
    ZBUS = 7,
    IWAMOTO = 8,
    CONTINUATION_NR = 9,
    HELMZ = 10,
    LM = 11  # Levenberg-Marquardt
    FASTDECOUPLED = 12,
    LACPF = 13,
    DC_OPF = 14,
    AC_OPF = 15


class TimeGroups(Enum):
    NoGroup = 0,
    ByDay = 1,
    ByHour = 2


class CascadeType(Enum):
    PowerFlow = 0,
    LatinHypercube = 1


########################################################################################################################
# Statistics classes
########################################################################################################################


class CDF(object):
    """
    Inverse Cumulative density function of a given array of data
    """

    def __init__(self, data):
        """
        Constructor
        @param data: Array (list or numpy array)
        """
        # Create the CDF of the data
        # sort the data:
        if type(data) is pd.DataFrame:
            self.arr = sort(ndarray.flatten(data.values))

        else:
            # self.arr = sort(ndarray.flatten(data), axis=0)
            self.arr = sort(data, axis=0)

        self.iscomplex = iscomplexobj(self.arr)

        # calculate the proportional values of samples
        n = len(data)
        if n > 1:
            self.prob = 1. * arange(n) / (n - 1)
        else:
            self.prob = 1. * arange(n)

        # iterator index
        self.idx = 0

        # array length
        self.len = len(self.arr)

    def __call__(self):
        """
        Call this as CDF()
        @return:
        """
        return self.arr

    def __iter__(self):
        """
        Iterator constructor
        @return:
        """
        self.idx = 0
        return self

    def __next__(self):
        """
        Iterator next element
        @return:
        """
        if self.idx == self.len:
            raise StopIteration

        self.idx += 1
        return self.arr[self.idx - 1]

    def __add__(self, other):
        """
        Sum of two CDF
        @param other:
        @return: A CDF object with the sum of other CDF to this CDF
        """
        return CDF(array([a + b for a in self.arr for b in other]))

    def __sub__(self, other):
        """
        Subtract of two CDF
        @param other:
        @return: A CDF object with the subtraction a a CDF to this CDF
        """
        return CDF(array([a - b for a in self.arr for b in other]))

    def get_sample(self, npoints=1):
        """
        Samples a number of uniform distributed points and
        returns the corresponding probability values given the CDF.
        @param npoints: Number of points to sample, 1 by default
        @return: Corresponding probabilities
        """
        pt = np.random.uniform(0, 1, npoints)
        if self.iscomplex:
            a = interp(pt, self.prob, self.arr.real)
            b = interp(pt, self.prob, self.arr.imag)
            return a + 1j * b
        else:
            return interp(pt, self.prob, self.arr)

    def get_at(self, prob):
        """
        Samples a number of uniform distributed points and
        returns the corresponding probability values given the CDF.
        @param prob: probability from 0 to 1
        @return: Corresponding CDF value
        """
        if self.iscomplex:
            a = interp(prob, self.prob, self.arr.real)
            b = interp(prob, self.prob, self.arr.imag)
            return a + 1j * b
        else:
            return interp(prob, self.prob, self.arr)

    def plot(self, ax=None):
        """
        Plots the CFD
        @param ax: MatPlotLib axis to plot into
        @return:
        """
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)
        ax.plot(self.prob, self.arr, linewidth=LINEWIDTH)
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

    def __init__(self, gen_P, load_P, load_Q):
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
        rows, cols = shape(gen_P)
        for i in range(cols):
            cdf = CDF(gen_P[:, i])
            self.gen_P_laws.append(cdf)

        rows, cols = shape(load_P)
        for i in range(cols):
            cdf = CDF(load_P[:, i])
            self.load_P_laws.append(cdf)

        rows, cols = shape(load_Q)
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

        P = array(P)
        Q = array(Q)
        S = P + 1j * Q

        PG = array(PG)

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
            ax.plot(cdf.prob, cdf.data_sorted, color='g', marker='x')
        for cdf in self.load_Q_laws:
            ax.plot(cdf.prob, cdf.data_sorted, color='b', marker='x')
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
    mx = t[n - 1].hour * t[n - 1].dayofyear

    arr = list()

    for i in range(mx - offset + 1):
        arr.append(list())

    for i in range(n):
        hourofyear = t[i].hour * t[i].dayofyear
        arr[hourofyear - offset].append(i)

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
    mx = t[n - 1].dayofyear

    arr = list()

    for i in range(mx - offset + 1):
        arr.append(list())

    for i in range(n):
        hourofyear = t[i].dayofyear
        arr[hourofyear - offset].append(i)

    return arr


def load_from_xls(filename):
    """
    Loads the excel file content to a dictionary for parsing the data
    """
    data = dict()
    xl = pd.ExcelFile(filename)
    names = xl.sheet_names

    # this dictionary sets the allowed excel sheets and the possible specific converter
    allowed_data_sheets = {'Conf': None,
                           'config': None,
                           'bus': None,
                           'branch':None,
                           'load': None,
                           'load_Sprof': complex,
                           'load_Iprof': complex,
                           'load_Zprof': complex,
                           'static_generator': None,
                           'static_generator_Sprof': complex,
                           'battery': None,
                           'battery_Vset_profiles': float,
                           'battery_P_profiles': float,
                           'controlled_generator': None,
                           'CtrlGen_Vset_profiles': float,
                           'CtrlGen_P_profiles': float,
                           'shunt': None,
                           'shunt_Y_profiles': complex}

    # check the validity of this excel file
    for name in names:
        if name not in allowed_data_sheets.keys():
            raise Exception('The file sheet ' + name + ' is not allowed.\n'
                            'Did you create this file manually? Use GridCal instead.')

    # parse the file
    if 'Conf' in names:
        for name in names:

            if name.lower() == "conf":
                df = xl.parse(name)
                data["baseMVA"] = double(df.values[0, 1])

            elif name.lower() == "bus":
                df = xl.parse(name)
                data["bus"] = nan_to_num(df.values)
                if len(df) > 0:
                    if df.index.values.tolist()[0] != 0:
                        data['bus_names'] = df.index.values.tolist()

            elif name.lower() == "gen":
                df = xl.parse(name)
                data["gen"] = nan_to_num(df.values)
                if len(df) > 0:
                    if df.index.values.tolist()[0] != 0:
                        data['gen_names'] = df.index.values.tolist()

            elif name.lower() == "branch":
                df = xl.parse(name)
                data["branch"] = nan_to_num(df.values)
                if len(df) > 0:
                    if df.index.values.tolist()[0] != 0:
                        data['branch_names'] = df.index.values.tolist()

            elif name.lower() == "storage":
                df = xl.parse(name)
                data["storage"] = nan_to_num(df.values)
                if len(df) > 0:
                    if df.index.values.tolist()[0] != 0:
                        data['storage_names'] = df.index.values.tolist()

            elif name.lower() == "lprof":
                df = xl.parse(name, index_col=0)
                data["Lprof"] = nan_to_num(df.values)
                data["master_time"] = df.index

            elif name.lower() == "lprofq":
                df = xl.parse(name, index_col=0)
                data["LprofQ"] = nan_to_num(df.values)
                # ppc["master_time"] = df.index.values

            elif name.lower() == "gprof":
                df = xl.parse(name, index_col=0)
                data["Gprof"] = nan_to_num(df.values)
                data["master_time"] = df.index  # it is the same

    elif 'config' in names:  # version 2

        for name in names:

            if name.lower() == "config":
                df = xl.parse('config')
                idx = df['Property'][df['Property'] == 'BaseMVA'].index
                if len(idx) > 0:
                    data["baseMVA"] = double(df.values[idx, 1])
                else:
                    data["baseMVA"] = 100

                idx = df['Property'][df['Property'] == 'Version'].index
                if len(idx) > 0:
                    data["version"] = double(df.values[idx, 1])

                idx = df['Property'][df['Property'] == 'Name'].index
                if len(idx) > 0:
                    data["name"] = df.values[idx[0], 1]
                else:
                    data["name"] = 'Grid'

                idx = df['Property'][df['Property'] == 'Comments'].index
                if len(idx) > 0:
                    data["Comments"] = df.values[idx[0], 1]
                else:
                    data["Comments"] = ''

            else:
                # just pick the DataFrame
                df = xl.parse(name, index_col=0)

                if allowed_data_sheets[name] == complex:
                    # pandas does not read complex numbers right,
                    # so when we expect a complex number input, parse directly
                    for c in df.columns.values:
                        df[c] = df[c].apply(lambda x: np.complex(x))

                data[name] = df

    else:
        raise Exception('This excel file is not in GridCal Format')

    return data

########################################################################################################################
# Circuit classes
########################################################################################################################


class Measurement:

    def __init__(self, value, uncertainty, mtype: MeasurementType):
        """
        Constructor
        :param value: value 
        :param uncertainty: uncertainty (standard deviation) 
        :param mtype: type of measurement
        """
        self.val = value
        self.sigma = uncertainty
        self.measurement_type = mtype


class ReliabilityDevice:

    def __init__(self, mttf, mttr):
        """
        Class to provide reliability derived functionality
        :param mttf: Mean Time To Failure (h)
        :param mttr: Mean Time To Repair (h)
        """
        self.mttf = mttf

        self.mttr = mttr

    def get_failure_time(self, n_samples):
        """
        Get an array of possible failure times
        :param n_samples: number of samples to draw
        :return: Array of times in hours
        """
        return -1.0 * self.mttf * np.log(np.random.rand(n_samples))

    def get_repair_time(self, n_samples):
        """
        Get an array of possible repair times
        :param n_samples: number of samples to draw
        :return: Array of times in hours
        """
        return -1.0 * self.mttr * np.log(np.random.rand(n_samples))

    def get_reliability_events(self, horizon, n_samples):
        """
        Get random fail-repair events until a given time horizon in hours
        :param horizon: maximum horizon in hours
        :return: list of events
        """
        t = zeros(n_samples)
        events = list()
        while t.any() < horizon:  # if all event get to the horizon, finnish the sampling

            # simulate failure
            te = self.get_failure_time(n_samples)
            if (t + te).any() <= horizon:
                t += te
                events.append(t)

            # simulate repair
            te = self.get_repair_time(n_samples)
            if (t + te).any() <= horizon:
                t += te
                events.append(t)

        return events


class Bus:

    def __init__(self, name="Bus", vnom=10, vmin=0.9, vmax=1.1, xpos=0, ypos=0, height=0, width=0,
                 active=True, is_slack=False):
        """
        Bus  constructor
        :param name: name of the bus
        :param vnom: nominal voltage in kV
        :param vmin: minimum per unit voltage (i.e. 0.9)
        :param vmax: maximum per unit voltage (i.e. 1.1)
        :param xpos: x position in pixels
        :param ypos: y position in pixels
        :param height: height of the graphic object
        :param width: width of the graphic object
        :param active: is the bus active?
        :param is_slack: is this bus a slack bus?
        """

        self.name = name

        self.type_name = 'Bus'

        self.properties_with_profile = None

        # Nominal voltage (kV)
        self.Vnom = vnom

        # minimum voltage limit
        self.Vmin = vmin

        # maximum voltage limit
        self.Vmax = vmax

        # summation of lower reactive power limits connected
        self.Qmin_sum = 0

        # summation of upper reactive power limits connected
        self.Qmax_sum = 0

        # short circuit impedance
        self.Zf = 0

        # is the bus active?
        self.active = active

        # List of load s attached to this bus
        self.loads = list()

        # List of Controlled generators attached to this bus
        self.controlled_generators = list()

        # List of shunt s attached to this bus
        self.shunts = list()

        # List of batteries attached to this bus
        self.batteries = list()

        # List of static generators attached tot this bus
        self.static_generators = list()

        # List of measurements
        self.measurements = list()

        # Bus type
        self.type = NodeType.NONE

        # Flag to determine if the bus is a slack bus or not
        self.is_slack = is_slack

        # if true, the presence of storage devices turn the bus into a Reference bus in practice
        # So that P +jQ are computed
        self.dispatch_storage = False

        # position and dimensions
        self.x = xpos
        self.y = ypos
        self.h = height
        self.w = width

        # associated graphic object
        self.graphic_obj = None

        self.edit_headers = ['name', 'active', 'is_slack', 'Vnom', 'Vmin', 'Vmax', 'Zf', 'x', 'y', 'h', 'w']

        self.units = ['', '', '', 'kV', 'p.u.', 'p.u.', 'p.u.', 'px', 'px', 'px', 'px']

        self.edit_types = {'name': str,
                           'active': bool,
                           'is_slack': bool,
                           'Vnom': float,
                           'Vmin': float,
                           'Vmax': float,
                           'Zf': complex,
                           'x': float,
                           'y': float,
                           'h': float,
                           'w': float}

    def determine_bus_type(self):
        """
        Infer the bus type from the devices attached to it
        @return: Nothing
        """

        gen_on = 0
        for elm in self.controlled_generators:
            if elm.active:
                gen_on += 1

        batt_on = 0
        for elm in self.batteries:
            if elm.active:
                batt_on += 1

        if gen_on > 0:

            if self.is_slack:  # If contains generators and is marked as REF, then set it as REF
                self.type = NodeType.REF
            else:  # Otherwise set as PV
                self.type = NodeType.PV

        elif batt_on > 0:

            if self.dispatch_storage:
                # If there are storage devices and the dispatchable flag is on, set the bus as dispatchable
                self.type = NodeType.STO_DISPATCH
            else:
                # Otherwise a storage device shall be marked as a voltage controlled bus
                self.type = NodeType.PV
        else:
            if self.is_slack:  # If there is no device but still is marked as REF, then set as REF
                self.type = NodeType.REF
            else:
                # Nothing special; set it as PQ
                self.type = NodeType.PQ

        pass

    def get_YISV(self, index=None, with_profiles=True, use_opf_vals=False, dispatch_storage=False):
        """
        Compose the
            - Z: Impedance attached to the bus
            - I: Current attached to the bus
            - S: Power attached to the bus
            - V: Voltage of the bus
        All in complex values
        :param index: index of the Pandas DataFrame
        :param with_profiles: also fill the profiles
        :return: Y, I, S, V, Yprof, Iprof, Sprof
        """

        Y = complex(0, 0)
        I = complex(0, 0)  # Positive Generates, negative consumes
        S = complex(0, 0)  # Positive Generates, negative consumes
        V = complex(1, 0)

        y_profile = None
        i_profile = None  # Positive Generates, negative consumes
        s_profile = None  # Positive Generates, negative consumes

        y_cdf = None
        i_cdf = None  # Positive Generates, negative consumes
        s_cdf = None  # Positive Generates, negative consumes

        eps = 1e-20

        self.Qmin_sum = 0
        self.Qmax_sum = 0

        is_v_controlled = False

        # Loads
        for elm in self.loads:

            if elm.active:

                if elm.Z != complex(0.0, 0.0):
                    Y += 1 / elm.Z  # Do not touch this one!!!!! it will break the Ybus matrix, when Z=0 -> Y=0 not inf.
                I -= elm.I  # Reverse sign convention in the load
                S -= elm.S  # Reverse sign convention in the load

                # Add the profiles
                if with_profiles:

                    elm_s_prof, elm_i_prof, elm_z_prof = elm.get_profiles(index)

                    if elm_z_prof is not None:
                        if y_profile is None:
                            y_profile = 1.0 / (elm_z_prof.values + eps)
                        else:
                            y_profile += 1.0 / (elm_z_prof.values + eps)

                    if elm_i_prof is not None:
                        if i_profile is None:
                            i_profile = -elm_i_prof.values  # Reverse sign convention in the load
                        else:
                            i_profile -= elm_i_prof.values  # Reverse sign convention in the load

                    if elm_s_prof is not None:
                        if s_profile is None:
                            s_profile = -elm_s_prof.values  # Reverse sign convention in the load
                        else:
                            s_profile -= elm_s_prof.values  # Reverse sign convention in the load

                else:
                    pass
            else:
                warn(elm.name + ' is not active')

        # controlled gen and batteries
        if dispatch_storage:
            generators = self.controlled_generators  # do not include batteries
        else:
            generators = self.controlled_generators + self.batteries

        for elm in generators:

            if elm.active:
                # Add the generator active power
                S += complex(elm.P, 0)

                self.Qmin_sum += elm.Qmin
                self.Qmax_sum += elm.Qmax

                # Voltage of the bus
                if not is_v_controlled:
                    V = complex(elm.Vset, 0)
                    is_v_controlled = True
                else:
                    if elm.Vset != V.real:
                        raise Exception("Different voltage controlled generators try to control " +
                                        "the same bus with different voltage set points")
                    else:
                        pass

                # add the power profile
                if with_profiles:
                    elm_p_prof, elm_vset_prof = elm.get_profiles(index, use_opf_vals=use_opf_vals)
                    if elm_p_prof is not None:
                        if s_profile is None:
                            s_profile = elm_p_prof.values  # Reverse sign convention in the load
                        else:
                            s_profile += elm_p_prof.values
                else:
                    pass
            else:
                warn(elm.name + ' is not active')

        # set maximum reactive power limits
        if self.Qmin_sum == 0:
            self.Qmin_sum = -999900
        if self.Qmax_sum == 0:
            self.Qmax_sum = 999900

        # Shunts
        for elm in self.shunts:
            if elm.active:
                Y += elm.Y

                # add profiles
                if with_profiles:
                    if elm.Yprof is not None:
                        if y_profile is None:
                            y_profile = elm.Yprof.values  # Reverse sign convention in the load
                        else:
                            y_profile += elm.Yprof.values
                else:
                    pass
            else:
                warn(elm.name + ' is not active')

        # Static generators
        for elm in self.static_generators:

            if elm.active:
                S += elm.S

                # add profiles
                if with_profiles:
                    if elm.Sprof is not None:
                        if s_profile is None:
                            s_profile = elm.Sprof.values  # Reverse sign convention in the load
                        else:
                            s_profile += elm.Sprof.values
                else:
                    pass
            else:
                warn(elm.name + ' is not active')

        # Align profiles into a common column sum based on the time axis
        if s_profile is not None:
            s_cdf = CDF(s_profile[:, 0])

        if i_profile is not None:
            i_cdf = CDF(i_profile[:, 0])

        if y_profile is not None:
            y_cdf = CDF(y_profile[:, 0])

        return Y, I, S, V, y_profile, i_profile, s_profile, y_cdf, i_cdf, s_cdf

    def initialize_lp_profiles(self):
        """
        Dimention the LP var profiles
        :return:
        """
        for elm in (self.controlled_generators + self.batteries):
            elm.initialize_lp_vars()

    def plot_profiles(self, ax=None):
        """

        @param time_idx: Master time profile: usually stored in the circuit
        @param ax: Figure axis, if not provided one will be created
        @return:
        """

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)
            show_fig = True
        else:
            show_fig = False

        for elm in self.loads:
            ax.plot(elm.Sprof.index, elm.Sprof.values.real, label=elm.name)

        for elm in self.controlled_generators + self.batteries:
            ax.plot(elm.Pprof.index, elm.Pprof.values, label=elm.name)

        for elm in self.static_generators:
            ax.plot(elm.Sprof.index, elm.Sprof.values.real, label=elm.name)

        plt.legend()
        plt.title(self.name)
        plt.ylabel('MW')
        if show_fig:
            plt.show()

    def copy(self):
        """

        :return:
        """
        bus = Bus()
        bus.name = self.name

        # Nominal voltage (kV)
        bus.Vnom = self.Vnom

        bus.vmin = self.Vmin

        bus.Vmax = self.Vmax

        bus.Zf = self.Zf

        bus.Qmin_sum = self.Qmin_sum

        bus.Qmax_sum = self.Qmax_sum

        bus.active = self.active

        # List of load s attached to this bus
        for elm in self.loads:
            bus.loads.append(elm.copy())

        # List of Controlled generators attached to this bus
        for elm in self.controlled_generators:
            bus.controlled_generators.append(elm.copy())

        # List of shunt s attached to this bus
        for elm in self.shunts:
            bus.shunts.append(elm.copy())

        # List of batteries attached to this bus
        for elm in self.batteries:
            bus.batteries.append(elm.copy())

        # List of static generators attached tot this bus
        for g in self.static_generators:
            bus.static_generators.append(g.copy())

        # Bus type
        bus.type = self.type

        # Flag to determine if the bus is a slack bus or not
        bus.is_slack = self.is_slack

        # if true, the presence of storage devices turn the bus into a Reference bus in practice
        # So that P +jQ are computed
        bus.dispatch_storage = self.dispatch_storage

        bus.x = self.x

        bus.y = self.y

        bus.h = self.h

        bus.w = self.w

        bus.measurements = self.measurements

        # self.graphic_obj = None

        return bus

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        self.retrieve_graphic_position()
        return [self.name, self.active, self.is_slack, self.Vnom, self.Vmin, self.Vmax, self.Zf,
                self.x, self.y, self.h, self.w]

    def get_json_dict(self, id):
        """
        Return Json-like dictionary
        :return: 
        """
        return {'id': id,
                'type': 'bus',
                'phases': 'ps',
                'name': self.name,
                'active': self.active,
                'is_slack': self.is_slack,
                'Vnom': self.Vnom,
                'vmin': self.Vmin,
                'vmax': self.Vmax,
                'rf': self.Zf.real,
                'xf': self.Zf.imag,
                'x': self.x,
                'y': self.y,
                'h': self.h,
                'w': self.w}

    def set_state(self, t):
        """
        Set the profiles state of the objects in this bus to the value given in the profiles at the index t
        :param t: index of the profile
        :return:
        """
        for elm in self.loads:
            elm.S = elm.Sprof.values[t, 0]
            elm.I = elm.Iprof.values[t, 0]
            elm.Z = elm.Zprof.values[t, 0]

        for elm in self.static_generators:
            elm.S = elm.Sprof.values[t, 0]

        for elm in self.batteries:
            elm.P = elm.Pprof.values[t, 0]
            elm.Vset = elm.Vsetprof.values[t, 0]

        for elm in self.controlled_generators:
            elm.P = elm.Pprof.values[t, 0]
            elm.Vset = elm.Vsetprof.values[t, 0]

        for elm in self.shunts:
            elm.Y = elm.Yprof.values[t, 0]

    def retrieve_graphic_position(self):
        """
        Get the position set by the graphic object
        :return:
        """
        if self.graphic_obj is not None:
            self.x = self.graphic_obj.pos().x()
            self.y = self.graphic_obj.pos().y()
            self.w, self.h = self.graphic_obj.rect().getCoords()[2:4]

    def delete_profiles(self):
        """
        Delete all profiles
        :return: 
        """
        for elm in self.loads:
            elm.delete_profiles()

        for elm in self.static_generators:
            elm.delete_profiles()

        for elm in self.batteries:
            elm.delete_profiles()

        for elm in self.controlled_generators:
            elm.delete_profiles()

        for elm in self.shunts:
            elm.delete_profiles()

    def set_profile_values(self, t):
        """
        Set the default values from the profiles at time index t
        :param t: profile time index
        """

        for elm in self.loads:
            elm.set_profile_values(t)

        for elm in self.static_generators:
            elm.set_profile_values(t)

        for elm in self.batteries:
            elm.set_profile_values(t)

        for elm in self.controlled_generators:
            elm.set_profile_values(t)

        for elm in self.shunts:
            elm.set_profile_values(t)

    def apply_lp_profiles(self, Sbase):
        """
        Sets the lp solution to the regular generators profile
        :return:
        """
        for elm in self.batteries + self.controlled_generators:
            elm.apply_lp_profile(Sbase)

    def __str__(self):
        return self.name


class TransformerType:

    def __init__(self, HV_nominal_voltage, LV_nominal_voltage, Nominal_power, Copper_losses, Iron_losses,
                 No_load_current, Short_circuit_voltage, GR_hv1, GX_hv1, name='TransformerType'):
        """
        Constructor
        @param HV_nominal_voltage: High voltage side nominal voltage (kV)
        @param LV_nominal_voltage: Low voltage side nominal voltage (kV)
        @param Nominal_power: Transformer nominal power (MVA)
        @param Copper_losses: Copper losses (kW)
        @param Iron_losses: Iron Losses (kW)
        @param No_load_current: No load current (%)
        @param Short_circuit_voltage: Short circuit voltage (%)
        @param GR_hv1:
        @param GX_hv1:
        """

        self.name = name

        self.type_name = 'TransformerType'

        self.properties_with_profile = None

        self.HV_nominal_voltage = HV_nominal_voltage

        self.LV_nominal_voltage = LV_nominal_voltage

        self.Nominal_power = Nominal_power

        self.Copper_losses = Copper_losses

        self.Iron_losses = Iron_losses

        self.No_load_current = No_load_current

        self.Short_circuit_voltage = Short_circuit_voltage

        self.GR_hv1 = GR_hv1

        self.GX_hv1 = GX_hv1

    def get_impedances(self):
        """
        Compute the branch parameters of a transformer from the short circuit
        test values
        @return:
            leakage_impedance: Series impedance
            magnetizing_impedance: Shunt impedance
        """
        Vhv = self.HV_nominal_voltage

        Vlv = self.LV_nominal_voltage

        Sn = self.Nominal_power

        Pcu = self.Copper_losses

        Pfe = self.Iron_losses

        I0 = self.No_load_current

        Vsc = self.Short_circuit_voltage

        # GRhv = self.GR_hv1
        # GXhv = self.GX_hv1

        # Zn_hv = (Vhv ** 2) / Sn
        # Zn_lv = (Vlv ** 2) / Sn

        zsc = Vsc / 100.0
        rsc = (Pcu / 1000.0) / Sn
        # xsc = 1 / sqrt(zsc ** 2 - rsc ** 2)
        xsc = sqrt(zsc ** 2 - rsc ** 2)

        # rcu_hv = rsc * self.GR_hv1
        # rcu_lv = rsc * (1 - self.GR_hv1)
        # xs_hv = xsc * self.GX_hv1
        # xs_lv = xsc * (1 - self.GX_hv1)

        if Pfe > 0.0 and I0 > 0.0:
            rfe = Sn / (Pfe / 1000.0)

            zm = 1.0 / (I0 / 100.0)

            xm = 1.0 / sqrt((1.0 / (zm ** 2)) - (1.0 / (rfe ** 2)))

        else:

            rfe = 0.0
            xm = 0.0

        # series impedance
        z_series = rsc + 1j * xsc

        # y_series = 1.0 / z_series

        # shunt impedance
        zl = rfe + 1j * xm

        # y_shunt = 1.0 / zl

        return z_series, zl

    def __str__(self):
        return self.name


class TapChanger:

    def __init__(self, taps_up=5, taps_down=5, max_reg=1.1, min_reg=0.9):
        """
        Tap changer
        Args:
            taps_up: Number of taps position up
            taps_down: Number of tap positions down
            max_reg: Maximum regulation up i.e 1.1 -> +10%
            min_reg: Maximum regulation down i.e 0.9 -> -10%
        """
        self.max_tap = taps_up

        self.min_tap = -taps_down

        self.inc_reg_up = (max_reg - 1.0) / taps_up

        self.inc_reg_down = (1.0 - min_reg) / taps_down

        self.tap = 0

    def tap_up(self):
        """
        Go to the next upper tap position
        """
        if self.tap + 1 <= self.max_tap:
            self.tap += 1

    def tap_down(self):
        """
        Go to the next upper tap position
        """
        if self.tap - 1 >= self.min_tap:
            self.tap -= 1

    def get_tap(self):
        """
        Get the tap voltage regulation module
        """
        if self.tap == 0:
            return 1.0
        elif self.tap > 0:
            return 1.0 + self.tap * self.inc_reg_up
        elif self.tap < 0:
            return 1.0 + self.tap * self.inc_reg_down

    def set_tap(self, tap_module):
        """
        Set the integer tap position corresponding to a tap vlaue
        @param tap_module: value like 1.05
        """
        if tap_module == 1.0:
            self.tap = 0
        elif tap_module > 1:
            self.tap = int(round(tap_module - 1.0) / self.inc_reg_up)
        elif tap_module < 1:
            self.tap = int(round(1.0 - tap_module) / self.inc_reg_down)


class Branch(ReliabilityDevice):

    def __init__(self, bus_from: Bus, bus_to: Bus, name='Branch', r=1e-20, x=1e-20, g=1e-20, b=1e-20,
                 rate=1.0, tap=1.0, shift_angle=0, active=True, mttf=0, mttr=0, is_transformer=False):
        """
        Branch model constructor
        @param bus_from: Bus Object
        @param bus_to: Bus Object
        @param name: name of the branch
        @param zserie: branch series impedance (complex)
        @param yshunt: branch shunt admittance (complex)
        @param rate: branch rate in MVA
        @param tap: tap module
        @param shift_angle: tap shift angle in radians
        @param mttf: Mean time to failure
        @param mttr: Mean time to repair
        @param is_transformer: Is the branch a transformer?
        """

        ReliabilityDevice.__init__(self, mttf, mttr)

        self.name = name

        self.type_name = 'Branch'

        self.properties_with_profile = None

        self.bus_from = bus_from
        self.bus_to = bus_to

        self.active = active

        # List of measurements
        self.measurements = list()

        self.R = r
        self.X = x
        self.G = g
        self.B = b

        self.tap_changer = TapChanger()

        if tap != 0:
            self.tap_module = tap
            self.tap_changer.set_tap(self.tap_module)
        else:
            self.tap_module = self.tap_changer.get_tap()

        self.angle = shift_angle

        self.rate = rate

        # self.mttf = mttf

        # self.mttr = mttr

        self.is_transformer = is_transformer

        self.type_obj = None

        self.edit_headers = ['name', 'bus_from', 'bus_to', 'active', 'rate', 'mttf', 'mttr', 'R', 'X', 'G', 'B',
                             'tap_module', 'angle', 'is_transformer']

        self.units = ['', '', '', '', 'MVA', 'h', 'h', 'p.u.', 'p.u.', 'p.u.', 'p.u.',
                      'p.u.', 'rad', '']

        self.edit_types = {'name': str,
                           'bus_from': None,
                           'bus_to': None,
                           'active': bool,
                           'rate': float,
                           'mttf': float,
                           'mttr': float,
                           'R': float,
                           'X': float,
                           'G': float,
                           'B': float,
                           'tap_module': float,
                           'angle': float,
                           'is_transformer':bool}

    def copy(self, bus_dict=None):
        """
        Returns a copy of the branch
        @return: A new  with the same content as this
        """

        if bus_dict is None:
            f = self.bus_from
            t = self.bus_to
        else:
            f = bus_dict[self.bus_from]
            t = bus_dict[self.bus_to]

        # z_series = complex(self.R, self.X)
        # y_shunt = complex(self.G, self.B)
        b = Branch(bus_from=f,
                   bus_to=t,
                   name=self.name,
                   r=self.R,
                   x=self.X,
                   g=self.G,
                   b=self.B,
                   rate=self.rate,
                   tap=self.tap_module,
                   shift_angle=self.angle,
                   active=self.active,
                   mttf=self.mttf,
                   mttr=self.mttr,
                   is_transformer=self.is_transformer)

        b.measurements = self.measurements

        return b

    def tap_up(self):
        """
        Move the tap changer one position up
        """
        self.tap_changer.tap_up()
        self.tap_module = self.tap_changer.get_tap()

    def tap_down(self):
        """
        Move the tap changer one position up
        """
        self.tap_changer.tap_down()
        self.tap_module = self.tap_changer.get_tap()

    def apply_to(self, Ybus, Yseries, Yshunt, Yf, Yt, B1, B2, i, f, t):
        """

        Modify the circuit admittance matrices with the admittances of this branch
        @param Ybus: Complete Admittance matrix
        @param Yseries: Admittance matrix of the series elements
        @param Yshunt: Admittance matrix of the shunt elements
        @param Yf: Admittance matrix of the branches with the from buses
        @param Yt: Admittance matrix of the branches with the to buses
        @param B1: Jacobian 1 for the fast-decoupled power flow
        @param B1: Jacobian 2 for the fast-decoupled power flow
        @param i: index of the branch in the circuit
        @return: Nothing, the inputs are implicitly modified
        """
        z_series = complex(self.R, self.X)
        y_shunt = complex(self.G, self.B)
        tap = self.tap_module * exp(-1j * self.angle)
        Ysh = y_shunt / 2
        if abs(z_series) > 0:
            Ys = 1 / z_series
        else:
            raise ValueError("The impedance at " + self.name + " is zero")

        Ytt = Ys + Ysh
        Yff = Ytt / (tap * conj(tap))
        Yft = - Ys / conj(tap)
        Ytf = - Ys / tap

        Yff_sh = Ysh
        Ytt_sh = Yff_sh / (tap * conj(tap))

        # Full admittance matrix
        Ybus[f, f] += Yff
        Ybus[f, t] += Yft
        Ybus[t, f] += Ytf
        Ybus[t, t] += Ytt

        # Y-from and Y-to for the lines power flow computation
        Yf[i, f] += Yff
        Yf[i, t] += Yft
        Yt[i, f] += Ytf
        Yt[i, t] += Ytt

        # Y shunt
        Yshunt[f] += Yff_sh
        Yshunt[t] += Ytt_sh

        # Y series
        Yseries[f, f] += Ys / (tap * conj(tap))
        Yseries[f, t] += Yft
        Yseries[t, f] += Ytf
        Yseries[t, t] += Ys

        # B1 for FDPF (no shunts, no resistance, no tap module)
        b1 = 1.0 / (self.X + 1e-20)
        B1[f, f] -= b1
        B1[f, t] -= b1
        B1[t, f] -= b1
        B1[t, t] -= b1

        # B2 for FDPF (with shunts, only the tap module)
        b2 = b1 + self.B
        B2[f, f] -= b2 / (tap * conj(tap))
        B2[f, t] -= b1 / conj(tap)
        B2[t, f] -= b1 / tap
        B2[t, t] -= b2

        # # B1 for FDPF (no shunts, no resistance, no tap module)
        # B1[f, f] -= Yff.imag
        # B1[f, t] -= Yft.imag
        # B1[t, f] -= Ytf.imag
        # B1[t, t] -= Ytt.imag
        #
        # # B2 for FDPF (with shunts, only the tap module)
        # B2[f, f] -= Yff.imag
        # B2[f, t] -= Yft.imag
        # B2[t, f] -= Ytf.imag
        # B2[t, t] -= Ytt.imag

        return f, t

    def apply_transformer_type(self, obj: TransformerType):
        """
        Apply a transformer type definition to this object
        Args:
            obj: TransformerType object
        """
        z_series, zsh = obj.get_impedances()

        y_shunt = 1 / zsh

        self.R = np.round(z_series.real, 6)
        self.X = np.round(z_series.imag, 6)
        self.G = np.round(y_shunt.real, 6)
        self.B = np.round(y_shunt.imag, 6)

        self.type_obj = obj

        self.rate = obj.Nominal_power

        self.is_transformer = True

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        return [self.name, self.bus_from.name, self.bus_to.name, self.active, self.rate, self.mttf, self.mttr,
                self.R, self.X, self.G, self.B, self.tap_module, self.angle, self.is_transformer]

    def get_json_dict(self, id, bus_dict):
        """
        Get json dictionary
        :param id: ID: Id for this object
        :param bus_dict: Dictionary of buses [object] -> ID 
        :return: 
        """
        return {'id': id,
                'type': 'branch',
                'phases': 'ps',
                'name': self.name,
                'from': bus_dict[self.bus_from],
                'to': bus_dict[self.bus_to],
                'active': self.active,
                'rate': self.rate,
                'r': self.R,
                'x': self.X,
                'g': self.G,
                'b': self.B,
                'tap_module': self.tap_module,
                'tap_angle': self.angle,
                'is_transformer': self.is_transformer}

    def __str__(self):
        return self.name


class Load(ReliabilityDevice):

    def __init__(self, name='Load', impedance=complex(0, 0), current=complex(0, 0), power=complex(0, 0),
                 impedance_prof=None, current_prof=None, power_prof=None, active=True, mttf=0.0, mttr=0.0):
        """
        Load model constructor
        This model implements the so-called ZIP model
        composed of an impedance value, a current value and a power value
        @param impedance: Impedance complex (Ohm)
        @param current: Current complex (kA)
        @param power: Power complex (MVA)
        """

        ReliabilityDevice.__init__(self, mttf, mttr)

        self.name = name

        self.active = active

        self.type_name = 'Load'

        self.properties_with_profile = (['S', 'I', 'Z'], [complex, complex, complex])

        self.graphic_obj = None

        # The bus this element is attached to: Not necessary for calculations
        self.bus = None

        # Impedance (Ohm)
        # Z * I = V -> Ohm * kA = kV
        self.Z = impedance

        # Current (kA)
        self.I = current

        # Power (MVA)
        # MVA = kV * kA
        self.S = power

        # impedances profile for this load
        self.Zprof = impedance_prof

        # Current profiles for this load
        self.Iprof = current_prof

        # power profile for this load
        self.Sprof = power_prof

        self.graphic_obj = None

        self.edit_headers = ['name', 'bus', 'active', 'Z', 'I', 'S', 'mttf', 'mttr']

        self.units = ['', '', '', 'MVA', 'MVA', 'MVA', 'h', 'h']  # ['', '', 'Ohm', 'kA', 'MVA']

        self.edit_types = {'name': str,
                           'bus': None,
                           'active': bool,
                           'Z': complex,
                           'I': complex,
                           'S': complex,
                           'mttf': float,
                           'mttr': float}

        self.profile_f = {'S': self.create_S_profile,
                          'I': self.create_I_profile,
                          'Z': self.create_Z_profile}

        self.profile_attr = {'S': 'Sprof',
                             'I': 'Iprof',
                             'Z': 'Zprof'}

    def create_profiles(self, index, S=None, I=None, Z=None):
        """
        Create the load object default profiles
        Args:
            index:
            steps:

        Returns:

        """

        self.create_S_profile(index, S)
        self.create_I_profile(index, I)
        self.create_Z_profile(index, Z)

    def create_S_profile(self, index, arr=None, arr_in_pu=False):
        """
        Create power profile based on index
        Args:
            index: time index
            arr: array
            arr_in_pu: is the array in per unit? if true, it is applied as a mask profile
        """
        if arr_in_pu:
            dta = arr * self.S
        else:
            nt = len(index)
            dta = ones(nt) * self.S if arr is None else arr
        self.Sprof = pd.DataFrame(data=dta, index=index, columns=[self.name])

    def create_I_profile(self, index, arr, arr_in_pu=False):
        """
        Create current profile based on index
        Args:
            index: time index
            arr: array
            arr_in_pu: is the array in per unit? if true, it is applied as a mask profile
        """
        if arr_in_pu:
            dta = arr * self.I
        else:
            dta = ones(len(index)) * self.I if arr is None else arr
        self.Iprof = pd.DataFrame(data=dta, index=index, columns=[self.name])

    def create_Z_profile(self, index, arr, arr_in_pu=False):
        """
        Create impedance profile based on index
        Args:
            index: time index
            arr: array
            arr_in_pu: is the array in per unit? if true, it is applied as a mask profile
        Returns:

        """
        if arr_in_pu:
            dta = arr * self.Z
        else:
            dta = ones(len(index)) * self.Z if arr is None else arr
        self.Zprof = pd.DataFrame(data=dta, index=index, columns=[self.name])

    def get_profiles(self, index=None):
        """
        Get profiles and if the index is passed, create the profiles if needed
        Args:
            index: index of the Pandas DataFrame

        Returns:
            Power, Current and Impedance profiles
        """
        if index is not None:
            if self.Sprof is None:
                self.create_S_profile(index)
            if self.Iprof is None:
                self.create_I_profile(index)
            if self.Zprof is None:
                self.create_Z_profile(index)
        return self.Sprof, self.Iprof, self.Zprof

    def delete_profiles(self):
        """
        Delete the object profiles
        :return: 
        """
        self.Sprof = None
        self.Iprof = None
        self.Zprof = None

    def set_profile_values(self, t):
        """
        Set the profile values at t
        :param t: time index
        """
        self.S = self.Sprof.values[t]
        self.I = self.Iprof.values[t]
        self.Z = self.Zprof.values[t]

    def copy(self):

        load = Load()

        load.name = self.name

        # Impedance (Ohm)
        # Z * I = V -> Ohm * kA = kV
        load.Z = self.Z

        # Current (kA)
        load.I = self.I

        # Power (MVA)
        # MVA = kV * kA
        load.S = self.S

        # impedances profile for this load
        load.Zprof = self.Zprof

        # Current profiles for this load
        load.Iprof = self.Iprof

        # power profile for this load
        load.Sprof = self.Sprof

        load.mttf = self.mttf

        load.mttr = self.mttr

        return load

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        return [self.name, self.bus.name, self.active, str(self.Z), str(self.I), str(self.S), self.mttf, self.mttr]

    def get_json_dict(self, id, bus_dict):
        """
        Get json dictionary
        :param id: ID: Id for this object
        :param bus_dict: Dictionary of buses [object] -> ID 
        :return: 
        """
        return {'id': id,
                'type': 'load',
                'phases': 'ps',
                'name': self.name,
                'bus': bus_dict[self.bus],
                'active': self.active,
                'Zr': self.Z.real,
                'Zi': self.Z.imag,
                'Ir': self.I.real,
                'Ii': self.I.imag,
                'P': self.S.real,
                'Q': self.S.imag}

    def __str__(self):
        return self.name


class StaticGenerator(ReliabilityDevice):

    def __init__(self, name='StaticGen', power=complex(0, 0), power_prof=None, active=True, mttf=0.0, mttr=0.0):
        """

        :param name:
        :param power:
        :param power_prof:
        :param active:
        :param mttf:
        :param mttr:
        """

        ReliabilityDevice.__init__(self, mttf, mttr)

        self.name = name

        self.active = active

        self.type_name = 'StaticGenerator'

        self.properties_with_profile = (['S'], [complex])

        self.graphic_obj = None

        # The bus this element is attached to: Not necessary for calculations
        self.bus = None

        # Power (MVA)
        # MVA = kV * kA
        self.S = power

        # power profile for this load
        self.Sprof = power_prof

        self.edit_headers = ['name', 'bus', 'active', 'S', 'mttf', 'mttr']

        self.units = ['', '', '', 'MVA', 'h', 'h']

        self.edit_types = {'name': str,
                           'bus': None,
                           'active': bool,
                           'S': complex,
                           'mttf': float,
                           'mttr': float}

        self.profile_f = {'S': self.create_S_profile}

        self.profile_attr = {'S': 'Sprof'}

    def copy(self):
        """

        :return:
        """
        return StaticGenerator(name=self.name, power=self.S, power_prof=self.Sprof)

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        return [self.name, self.bus.name, self.active, str(self.S), self.mttf, self.mttr]

    def get_json_dict(self, id, bus_dict):
        """
        Get json dictionary
        :param id: ID: Id for this object
        :param bus_dict: Dictionary of buses [object] -> ID 
        :return: 
        """
        return {'id': id,
                'type': 'static_gen',
                'phases': 'ps',
                'name': self.name,
                'bus': bus_dict[self.bus],
                'active': self.active,
                'P': self.S.real,
                'Q': self.S.imag}

    def create_profiles(self, index, S=None):
        """
        Create the load object default profiles
        Args:
            index:
            steps:

        Returns:

        """
        self.create_S_profile(index, S)

    def create_S_profile(self, index, arr, arr_in_pu=False):
        """
        Create power profile based on index
        Args:
            index:

        Returns:

        """
        if arr_in_pu:
            dta = arr * self.S
        else:
            dta = ones(len(index)) * self.S if arr is None else arr
        self.Sprof = pd.DataFrame(data=dta, index=index, columns=[self.name])

    def get_profiles(self, index=None):
        """
        Get profiles and if the index is passed, create the profiles if needed
        Args:
            index: index of the Pandas DataFrame

        Returns:
            Power, Current and Impedance profiles
        """
        if index is not None:
            if self.Sprof is None:
                self.create_S_profile(index)
        return self.Sprof

    def delete_profiles(self):
        """
        Delete the object profiles
        :return: 
        """
        self.Sprof = None

    def set_profile_values(self, t):
        """
        Set the profile values at t
        :param t: time index
        """
        self.S = self.Sprof.values[t]

    def __str__(self):
        return self.name


class ControlledGenerator(ReliabilityDevice):

    def __init__(self, name='gen', active_power=0.0, voltage_module=1.0, Qmin=-9999, Qmax=9999, Snom=9999,
                 power_prof=None, vset_prof=None, active=True, p_min=0.0, p_max=9999.0, op_cost=1.0, Sbase=100,
                 enabled_dispatch=True, mttf=0.0, mttr=0.0, Ra=0.0, Xa=0.0,
                 Xd=1.68, Xq=1.61, Xdp=0.32, Xqp=0.32, Xdpp=0.2, Xqpp=0.2,
                 Td0p=5.5, Tq0p=4.60375, Td0pp=0.0575, Tq0pp=0.0575, H=2, speed_volt=True,
                 machine_model=DynamicModels.SynchronousGeneratorOrder4):
        """
        Voltage controlled generator
        @param name: Name of the device
        @param active_power: Active power (MW)
        @param voltage_module: Voltage set point (p.u.)
        @param Qmin: minimum reactive power in MVAr
        @param Qmax: maximum reactive power in MVAr
        @param Snom: Nominal power in MVA
        @param power_prof: active power profile (Pandas DataFrame)
        @param vset_prof: voltage set point profile (Pandas DataFrame)
        @param active: Is the generator active?
        @param p_min: minimum dispatchable power in MW
        @param p_max maximum dispatchable power in MW
        @param op_cost operational cost in Eur (or other currency) per MW
        @param enabled_dispatch is the generator enabled for OPF?
        @param mttf: Mean time to failure
        @param mttr: Mean time to repair
        @param Ra: armature resistance (pu)
        @param Xa: armature reactance (pu)
        @param Xd: d-axis reactance (p.u.)
        @param Xq: q-axis reactance (p.u.)
        @param Xdp: d-axis transient reactance (p.u.)
        @param Xqp: q-axis transient reactance (p.u.)
        @param Xdpp: d-axis subtransient reactance (pu)
        @param Xqpp: q-axis subtransient reactance (pu)
        @param Td0p: d-axis transient open loop time constant (s)
        @param Tq0p: q-axis transient open loop time constant (s)
        @param Td0pp: d-axis subtransient open loop time constant (s)
        @param Tq0pp: q-axis subtransient open loop time constant (s)
        @param H: machine inertia constant (MWs/MVA)
        @param machine_model: Type of machine represented
        """

        ReliabilityDevice.__init__(self, mttf, mttr)

        # name of the device
        self.name = name

        # is the device active for simulation?
        self.active = active

        # is the device active active power dispatch?
        self.enabled_dispatch = enabled_dispatch

        # type of device
        self.type_name = 'ControlledGenerator'

        self.machine_model = machine_model

        # graphical object associated to this object
        self.graphic_obj = None

        # properties that hold a profile
        self.properties_with_profile = (['P', 'Vset'], [float, float])

        # The bus this element is attached to: Not necessary for calculations
        self.bus = None

        # Power (MVA)
        self.P = active_power

        # Nominal power in MVA (also the machine base)
        self.Snom = Snom

        # Minimum dispatched power in MW
        self.Pmin = p_min

        # Maximum dispatched power in MW
        self.Pmax = p_max

        # power profile for this load in MW
        self.Pprof = power_prof

        # Voltage module set point (p.u.)
        self.Vset = voltage_module

        # voltage set profile for this load in p.u.
        self.Vsetprof = vset_prof

        # minimum reactive power in MVAr
        self.Qmin = Qmin

        # Maximum reactive power in MVAr
        self.Qmax = Qmax

        # Cost of operation €/MW
        self.Cost = op_cost

        # Dynamic vars
        self.Ra = Ra
        self.Xa = Xa
        self.Xd = Xd
        self.Xq = Xq
        self.Xdp = Xdp
        self.Xqp = Xqp
        self.Xdpp = Xdpp
        self.Xqpp = Xqpp
        self.Td0p = Td0p
        self.Tq0p = Tq0p
        self.Td0pp = Td0pp
        self.Tq0pp = Tq0pp
        self.H = H
        self.speed_volt = speed_volt
        # self.base_mva = base_mva  # machine base MVA

        # system base power MVA
        self.Sbase = Sbase

        # Linear problem generator dispatch power variable (in p.u.)
        self.lp_name = self.type_name + '_' + self.name + str(id(self))

        # variable to dispatch the power in a Linear program
        self.LPVar_P = pulp.LpVariable(self.lp_name + '_P', self.Pmin / self.Sbase, self.Pmax / self.Sbase)

        # list of variables of active power dispatch in a series of linear programs
        self.LPVar_P_prof = None

        self.edit_headers = ['name', 'bus', 'active', 'P', 'Vset', 'Snom',
                             'Qmin', 'Qmax', 'Pmin', 'Pmax', 'Cost', 'enabled_dispatch', 'mttf', 'mttr']

        self.units = ['', '', '', 'MW', 'p.u.', 'MVA', 'MVAr', 'MVAr', 'MW', 'MW', 'e/MW', '', 'h', 'h']

        self.edit_types = {'name': str,
                           'bus': None,
                           'active': bool,
                           'P': float,
                           'Vset': float,
                           'Snom': float,
                           'Qmin': float,
                           'Qmax': float,
                           'Pmin': float,
                           'Pmax': float,
                           'Cost': float,
                           'enabled_dispatch': bool,
                           'mttf': float,
                           'mttr': float}

        self.profile_f = {'P': self.create_P_profile,
                          'Vset': self.create_Vset_profile}

        self.profile_attr = {'P': 'Pprof',
                             'Vset': 'Vsetprof'}

    def copy(self):
        """
        Make a deep copy of this object
        :return: Copy of this object
        """

        # make a new instance (separated object in memory)
        gen = ControlledGenerator()

        gen.name = self.name

        # Power (MVA)
        # MVA = kV * kA
        gen.P = self.P

        # is the generator active?
        gen.active = self.active

        # power profile for this load
        gen.Pprof = self.Pprof

        # Voltage module set point (p.u.)
        gen.Vset = self.Vset

        # voltage set profile for this load
        gen.Vsetprof = self.Vsetprof

        # minimum reactive power in per unit
        gen.Qmin = self.Qmin

        # Maximum reactive power in per unit
        gen.Qmax = self.Qmax

        # Nominal power
        gen.Snom = self.Snom

        # is the generator enabled for dispatch?
        gen.enabled_dispatch = self.enabled_dispatch

        gen.mttf = self.mttf

        gen.mttr = self.mttr

        return gen

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        return [self.name, self.bus.name, self.active, self.P, self.Vset, self.Snom,
                self.Qmin, self.Qmax, self.Pmin, self.Pmax, self.Cost, self.enabled_dispatch, self.mttf, self.mttr]

    def get_json_dict(self, id, bus_dict):
        """
        Get json dictionary
        :param id: ID: Id for this object
        :param bus_dict: Dictionary of buses [object] -> ID 
        :return: json-compatible dictionary
        """
        return {'id': id,
                'type': 'controlled_gen',
                'phases': 'ps',
                'name': self.name,
                'bus': bus_dict[self.bus],
                'active': self.active,
                'P': self.P,
                'vset': self.Vset,
                'Snom': self.Snom,
                'qmin': self.Qmin,
                'qmax': self.Qmax,
                'Pmin': self.Pmin,
                'Pmax': self.Pmax,
                'Cost': self.Cost}

    def create_profiles_maginitude(self, index, arr, mag):
        """
        Create profiles from magnitude
        Args:
            index: Time index
            arr: values array
            mag: String with the magnitude to assign
        """
        if mag == 'P':
            self.create_profiles(index, arr, None)
        elif mag == 'V':
            self.create_profiles(index, None, arr)
        else:
            raise Exception('Magnitude ' + mag + ' not supported')

    def create_profiles(self, index, P=None, V=None):
        """
        Create the load object default profiles
        Args:
            index: time index associated
            P: Active power (MW)
            V: voltage set points
        """
        self.create_P_profile(index, P)
        self.create_Vset_profile(index, V)

    def create_P_profile(self, index, arr=None, arr_in_pu=False):
        """
        Create power profile based on index
        Args:
            index: time index associated
            arr: array of values
            arr_in_pu: is the array in per unit?
        """
        if arr_in_pu:
            dta = arr * self.P
        else:
            dta = ones(len(index)) * self.P if arr is None else arr
        self.Pprof = pd.DataFrame(data=dta, index=index, columns=[self.name])

    def initialize_lp_vars(self):
        """
        Initialize the LP variables
        """
        self.lp_name = self.type_name + '_' + self.name + str(id(self))

        self.LPVar_P = pulp.LpVariable(self.lp_name + '_P', self.Pmin / self.Sbase, self.Pmax / self.Sbase)

        self.LPVar_P_prof = [
            pulp.LpVariable(self.lp_name + '_P_' + str(t), self.Pmin / self.Sbase, self.Pmax / self.Sbase) for t in range(self.Pprof.shape[0])]

    def get_lp_var_profile(self, index):
        """
        Get the profile of the LP solved values into a Pandas DataFrame
        :param index: time index
        :return: DataFrame with the LP values
        """
        dta = [x.value() for x in self.LPVar_P_prof]
        return pd.DataFrame(data=dta, index=index, columns=[self.name])

    def create_Vset_profile(self, index, arr=None, arr_in_pu=False):
        """
        Create power profile based on index
        Args:
            index: time index associated
            arr: array of values
            arr_in_pu: is the array in per unit?
        """
        if arr_in_pu:
            dta = arr * self.Vset
        else:
            dta = ones(len(index)) * self.Vset if arr is None else arr

        self.Vsetprof = pd.DataFrame(data=dta, index=index, columns=[self.name])

    def get_profiles(self, index=None, use_opf_vals=False):
        """
        Get profiles and if the index is passed, create the profiles if needed
        Args:
            index: index of the Pandas DataFrame

        Returns:
            Power, Current and Impedance profiles
        """
        if index is not None:
            if self.Pprof is None:
                self.create_P_profile(index)
            if self.Vsetprof is None:
                self.create_Vset_profile(index)

        if use_opf_vals:
            return self.get_lp_var_profile(index), self.Vsetprof
        else:
            return self.Pprof, self.Vsetprof

    def delete_profiles(self):
        """
        Delete the object profiles
        :return: 
        """
        self.Pprof = None
        self.Vsetprof = None

    def set_profile_values(self, t):
        """
        Set the profile values at t
        :param t: time index
        """
        self.P = self.Pprof.values[t]
        self.Vset = self.Vsetprof.values[t]

    def apply_lp_vars(self, at=None):
        """
        Set the LP vars to the main value or the profile
        """
        if self.LPVar_P is not None:
            if at is None:
                self.P = self.LPVar_P.value()
            else:
                self.Pprof.values[at] = self.LPVar_P.value()

    def apply_lp_profile(self, Sbase):
        """
        Set LP profile to the regular profile
        :return:
        """
        n = self.Pprof.shape[0]
        if self.active and self.enabled_dispatch:
            for i in range(n):
                self.Pprof.values[i] = self.LPVar_P_prof[i].value() * Sbase
        else:
            # there are no values in the LP vars because this generator is deactivated,
            # therefore fill the profiles with zeros when asked to copy the lp vars to the power profiles
            self.Pprof.values = zeros(self.Pprof.shape[0])

    def __str__(self):
        return self.name


# class BatteryController:
#
#     def __init__(self, nominal_energy=100000.0, charge_efficiency=0.9, discharge_efficiency=0.9,
#                  max_soc=0.99, min_soc=0.3, soc=0.8, charge_per_cycle=0.1, discharge_per_cycle=0.1):
#         """
#         Battery controller constructor
#         :param charge_efficiency: efficiency when charging
#         :param discharge_efficiency: efficiency when discharging
#         :param max_soc: maximum state of charge
#         :param min_soc: minimum state of charge
#         :param soc: current state of charge
#         :param nominal_energy: declared amount of energy in MWh
#         :param charge_per_cycle: per unit of power to take per cycle when charging
#         :param discharge_per_cycle: per unit of power to deliver per cycle when charging
#         """
#
#         self.charge_efficiency = charge_efficiency
#
#         self.discharge_efficiency = discharge_efficiency
#
#         self.max_soc = max_soc
#
#         self.min_soc = min_soc
#
#         self.min_soc_charge = (self.max_soc + self.min_soc) / 2  # SoC state to force the battery charge
#
#         self.charge_per_cycle = charge_per_cycle  # charge 10% per cycle
#
#         self.discharge_per_cycle = discharge_per_cycle
#
#         self.min_energy = nominal_energy * self.min_soc
#
#         self.Enom = nominal_energy
#
#         self.soc_0 = soc
#
#         self.soc = soc
#
#         self.energy = self.Enom * self.soc
#
#     def reset(self):
#         """
#         Set he battery to its initial state
#         """
#         self.soc = self.soc_0
#         self.energy = self.Enom * self.soc
#         # self.energy_array = zeros(0)
#         # self.power_array = zeros(0)
#
#     def process(self, P, dt, charge_if_needed=False, store_values=True):
#         """
#         process a cycle in the battery
#         :param P: proposed power in MW
#         :param dt: time increment in hours
#         :param charge_if_needed: True / False
#         :param store_values: Store the values into the internal arrays?
#         :return: Amount of power actually processed in MW
#         """
#
#         # if self.Enom is None:
#         #     raise Exception('You need to set the battery nominal power!')
#
#         if np.isnan(P):
#             warn('NaN found!!!!!!')
#
#         # pick the right efficiency value
#         if P >= 0.0:
#             eff = self.discharge_efficiency
#             # energy_per_cycle = self.nominal_energy * self.discharge_per_cycle
#         else:
#             eff = self.charge_efficiency
#
#         # amount of energy that the battery can take in a cycle of 1 hour
#         energy_per_cycle = self.Enom * self.charge_per_cycle
#
#         # compute the proposed energy. Later we check how much is actually possible
#         proposed_energy = self.energy - P * dt * eff
#
#         # charge the battery from the grid if the SoC is too low and we are allowing this behaviour
#         if charge_if_needed and self.soc < self.min_soc_charge:
#             proposed_energy -= energy_per_cycle / dt  # negative is for charging
#
#         # Check the proposed energy
#         if proposed_energy > self.Enom * self.max_soc:  # Truncated, too high
#
#             energy_new = self.Enom * self.max_soc
#             power_new = (self.energy - energy_new) / (dt * eff)
#
#         elif proposed_energy < self.Enom * self.min_soc:  # Truncated, too low
#
#             energy_new = self.Enom * self.min_soc
#             power_new = (self.energy - energy_new) / (dt * eff)
#
#         else:  # everything is within boundaries
#
#             energy_new = proposed_energy
#             power_new = P
#
#         # Update the state of charge and the energy state
#         self.soc = energy_new / self.Enom
#         self.energy = energy_new
#
#         return power_new, self.energy


class Battery(ControlledGenerator):

    def __init__(self, name='batt', active_power=0.0, voltage_module=1.0, Qmin=-9999, Qmax=9999,
                 Snom=9999, Enom=9999, p_min=-9999, p_max=9999, op_cost=1.0,
                 power_prof=None, vset_prof=None, active=True, Sbase=100, enabled_dispatch=True,
                 mttf=0.0, mttr=0.0, charge_efficiency=0.9, discharge_efficiency=0.9,
                 max_soc=0.99, min_soc=0.3, soc=0.8, charge_per_cycle=0.1, discharge_per_cycle=0.1,
                 Ra=0.0, Xa=0.0, Xd=1.68, Xq=1.61, Xdp=0.32, Xqp=0.32, Xdpp=0.2, Xqpp=0.2,
                 Td0p=5.5, Tq0p=4.60375, Td0pp=0.0575, Tq0pp=0.0575, H=2 ):
        """
        Battery (Voltage controlled and dispatchable)
        :param name: Name of the device
        :param active_power: Active power (MW)
        :param voltage_module: Voltage set point (p.u.)
        :param Qmin: minimum reactive power in MVAr
        :param Qmax: maximum reactive power in MVAr
        :param Snom: Nominal power in MVA
        :param Enom: Nominal energy in MWh
        :param power_prof: active power profile (Pandas DataFrame)
        :param vset_prof: voltage set point profile (Pandas DataFrame)
        :param active: Is the generator active?
        :param p_min: minimum dispatchable power in MW
        :param p_max maximum dispatchable power in MW
        :param op_cost operational cost in Eur (or other currency) per MW
        :param enabled_dispatch is the generator enabled for OPF?
        :param mttf: Mean time to failure
        :param mttr: Mean time to repair
        :param charge_efficiency: efficiency when charging
        :param discharge_efficiency: efficiency when discharging
        :param max_soc: maximum state of charge
        :param min_soc: minimum state of charge
        :param soc: current state of charge
        :param charge_per_cycle: per unit of power to take per cycle when charging
        :param discharge_per_cycle: per unit of power to deliver per cycle when charging
        """
        ControlledGenerator.__init__(self, name=name,
                                     active_power=active_power,
                                     voltage_module=voltage_module,
                                     Qmin=Qmin, Qmax=Qmax, Snom=Snom,
                                     power_prof=power_prof,
                                     vset_prof=vset_prof,
                                     active=active,
                                     p_min=p_min, p_max=p_max,
                                     op_cost=op_cost,
                                     Sbase=Sbase,
                                     enabled_dispatch=enabled_dispatch,
                                     mttf=mttf,
                                     mttr=mttr,
                                     Ra=Ra,
                                     Xa=Xa,
                                     Xd=Xd,
                                     Xq=Xq,
                                     Xdp=Xdp,
                                     Xqp=Xqp,
                                     Xdpp=Xdpp,
                                     Xqpp=Xqpp,
                                     Td0p=Td0p,
                                     Tq0p=Tq0p,
                                     Td0pp=Td0pp,
                                     Tq0pp=Tq0pp,
                                     H=H)

        # type of this device
        self.type_name = 'Battery'

        self.charge_efficiency = charge_efficiency

        self.discharge_efficiency = discharge_efficiency

        self.max_soc = max_soc

        self.min_soc = min_soc

        self.min_soc_charge = (self.max_soc + self.min_soc) / 2  # SoC state to force the battery charge

        self.charge_per_cycle = charge_per_cycle  # charge 10% per cycle

        self.discharge_per_cycle = discharge_per_cycle

        self.min_energy = Enom * self.min_soc

        self.Enom = Enom

        self.soc_0 = soc

        self.soc = soc

        self.energy = self.Enom * self.soc

        self.energy_array = None

        self.power_array = None

        self.edit_headers = ['name', 'bus', 'active', 'P', 'Vset', 'Snom', 'Enom',
                             'Qmin', 'Qmax', 'Pmin', 'Pmax', 'Cost', 'enabled_dispatch', 'mttf', 'mttr',
                             'soc_0', 'max_soc', 'min_soc', 'charge_efficiency', 'discharge_efficiency']

        self.units = ['', '', '', 'MW', 'p.u.', 'MVA', 'MWh',
                      'p.u.', 'p.u.', 'MW', 'MW', '€/MWh', '', 'h', 'h',
                      '', '', '', '', '']

        self.edit_types = {'name': str,
                           'bus': None,
                           'active': bool,
                           'P': float,
                           'Vset': float,
                           'Snom': float,
                           'Enom': float,
                           'Qmin': float,
                           'Qmax': float,
                           'Pmin': float,
                           'Pmax': float,
                           'Cost': float,
                           'enabled_dispatch': bool,
                           'mttf': float,
                           'mttr': float,
                           'soc_0': float,
                           'max_soc': float,
                           'min_soc': float,
                           'charge_efficiency': float,
                           'discharge_efficiency': float}

    def copy(self):
        """
        Make a copy of this object
        Returns: Battery instance
        """

        # create a new instance of the battery
        batt = Battery()

        batt.name = self.name

        # Power (MVA)
        # MVA = kV * kA
        batt.P = self.P

        batt.Pmax = self.Pmax

        batt.Pmin = self.Pmin

        # power profile for this load
        batt.Pprof = self.Pprof

        # Voltage module set point (p.u.)
        batt.Vset = self.Vset

        # voltage set profile for this load
        batt.Vsetprof = self.Vsetprof

        # minimum reactive power in per unit
        batt.Qmin = self.Qmin

        # Maximum reactive power in per unit
        batt.Qmax = self.Qmax

        # Nominal power MVA
        batt.Snom = self.Snom

        # Nominal energy MWh
        batt.Enom = self.Enom

        # Enable for active power dispatch?
        batt.enabled_dispatch = self.enabled_dispatch

        batt.mttf = self.mttf

        batt.mttr = self.mttr

        batt.charge_efficiency = self.charge_efficiency

        batt.discharge_efficiency = self.discharge_efficiency

        batt.max_soc = self.max_soc

        batt.min_soc = self.min_soc

        batt.min_soc_charge = self.min_soc_charge  # SoC state to force the battery charge

        batt.charge_per_cycle = self.charge_per_cycle  # charge 10% per cycle

        batt.discharge_per_cycle = self.discharge_per_cycle

        batt.min_energy = self.min_energy

        batt.soc_0 = self.soc

        batt.soc = self.soc

        batt.energy = self.energy

        batt.energy_array = self.energy_array

        batt.power_array = self.power_array

        return batt

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        return [self.name, self.bus.name, self.active, self.P, self.Vset, self.Snom, self.Enom,
                self.Qmin, self.Qmax, self.Pmin, self.Pmax, self.Cost, self.enabled_dispatch, self.mttf, self.mttr,
                self.soc_0, self.max_soc, self.min_soc, self.charge_efficiency, self.discharge_efficiency]

    def get_json_dict(self, id, bus_dict):
        """
        Get json dictionary
        :param id: ID: Id for this object
        :param bus_dict: Dictionary of buses [object] -> ID
        :return: json-compatible dictionary
        """
        return {'id': id,
                'type': 'battery',
                'phases': 'ps',
                'name': self.name,
                'bus': bus_dict[self.bus],
                'active': self.active,
                'P': self.P,
                'Vset': self.Vset,
                'Snom': self.Snom,
                'Enom': self.Enom,
                'qmin': self.Qmin,
                'qmax': self.Qmax,
                'Pmin': self.Pmin,
                'Pmax': self.Pmax,
                'Cost': self.Cost}

    def create_P_profile(self, index, arr=None, arr_in_pu=False):
        """
        Create power profile based on index
        Args:
            index: time index associated
            arr: array of values
            arr_in_pu: is the array in per unit?
        """
        if arr_in_pu:
            dta = arr * self.P
        else:
            dta = ones(len(index)) * self.P if arr is None else arr
        self.Pprof = pd.DataFrame(data=dta, index=index, columns=[self.name])

        self.power_array = pd.DataFrame(data=dta.copy(), index=index, columns=[self.name])
        self.energy_array = pd.DataFrame(data=dta.copy(), index=index, columns=[self.name])

    def reset(self):
        """
        Set he battery to its initial state
        """
        self.soc = self.soc_0
        self.energy = self.Enom * self.soc
        dta = self.Pprof.values.copy()
        index = self.Pprof.index
        self.power_array = pd.DataFrame(data=dta.copy(), index=index, columns=[self.name])
        self.energy_array = pd.DataFrame(data=dta.copy(), index=index, columns=[self.name])

    def process(self, P, dt, charge_if_needed=False):
        """
        process a cycle in the battery
        :param P: proposed power in MW
        :param dt: time increment in hours
        :param charge_if_needed: True / False
        :param store_values: Store the values into the internal arrays?
        :return: Amount of power actually processed in MW
        """

        # if self.Enom is None:
        #     raise Exception('You need to set the battery nominal power!')

        if np.isnan(P):
            warn('NaN found!!!!!!')

        # pick the right efficiency value
        if P >= 0.0:
            eff = self.discharge_efficiency
            # energy_per_cycle = self.nominal_energy * self.discharge_per_cycle
        else:
            eff = self.charge_efficiency

        # amount of energy that the battery can take in a cycle of 1 hour
        energy_per_cycle = self.Enom * self.charge_per_cycle

        # compute the proposed energy. Later we check how much is actually possible
        proposed_energy = self.energy - P * dt * eff

        # charge the battery from the grid if the SoC is too low and we are allowing this behaviour
        if charge_if_needed and self.soc < self.min_soc_charge:
            proposed_energy -= energy_per_cycle / dt  # negative is for charging

        # Check the proposed energy
        if proposed_energy > self.Enom * self.max_soc:  # Truncated, too high

            energy_new = self.Enom * self.max_soc
            power_new = (self.energy - energy_new) / (dt * eff)

        elif proposed_energy < self.Enom * self.min_soc:  # Truncated, too low

            energy_new = self.Enom * self.min_soc
            power_new = (self.energy - energy_new) / (dt * eff)

        else:  # everything is within boundaries

            energy_new = proposed_energy
            power_new = P

        # Update the state of charge and the energy state
        self.soc = energy_new / self.Enom
        self.energy = energy_new

        return power_new, self.energy

    def get_processed_at(self, t, dt, store_values=True):
        """
        Get the processed power at the time index t
        :param t: time index
        :param dt: time step in hours
        :param store_values: store the values?
        :return: active power processed by the battery control in MW
        """
        power_value = self.Pprof.values[t]

        processed_power, processed_energy = self.process(power_value, dt)

        if store_values:
            self.energy_array.values[t] = processed_energy
            self.power_array.values[t] = processed_power

        return processed_power


class Shunt(ReliabilityDevice):

    def __init__(self, name='shunt', admittance=complex(0, 0), admittance_prof=None, active=True, mttf=0.0, mttr=0.0):
        """
        Shunt object
        Args:
            name:
            admittance: Admittance in MVA at 1 p.u. voltage
            admittance_prof: Admittance profile in MVA at 1 p.u. voltage
            active: Is active True or False
        """

        ReliabilityDevice.__init__(self, mttf, mttr)

        self.name = name

        self.active = active

        self.type_name = 'Shunt'

        self.properties_with_profile = (['Y'], [complex])

        self.graphic_obj = None

        # The bus this element is attached to: Not necessary for calculations
        self.bus = None

        # Impedance (Ohm)
        # Z * I = V -> Ohm * kA = kV
        self.Y = admittance

        # admittance profile
        self.Yprof = admittance_prof

        self.edit_headers = ['name', 'bus', 'active', 'Y', 'mttf', 'mttr']

        self.units = ['', '', '', 'MVA', 'h', 'h']  # MVA at 1 p.u.

        self.edit_types = {'name': str,
                           'active': bool,
                           'bus': None,
                           'Y': complex,
                           'mttf': float,
                           'mttr': float}

        self.profile_f = {'Y': self.create_Y_profile}

        self.profile_attr = {'Y': 'Yprof'}

    def copy(self):
        """
        Copy of this object
        :return: a copy of this object
        """
        shu = Shunt()

        shu.name = self.name

        # Impedance (Ohm)
        # Z * I = V -> Ohm * kA = kV
        shu.Y = self.Y

        # admittance profile
        shu.Yprof = self.Yprof

        shu.mttf = self.mttf

        shu.mttr = self.mttr

        return shu

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        return [self.name, self.bus.name, self.active, str(self.Y), self.mttf, self.mttr]

    def get_json_dict(self, id, bus_dict):
        """
        Get json dictionary
        :param id: ID: Id for this object
        :param bus_dict: Dictionary of buses [object] -> ID 
        :return: 
        """
        return {'id': id,
                'type': 'shunt',
                'phases': 'ps',
                'name': self.name,
                'bus': bus_dict[self.bus],
                'active': self.active,
                'g': self.Y.real,
                'b': self.Y.imag}

    def create_profiles_maginitude(self, index, arr, mag):
        """
        Create profiles from magnitude
        Args:
            index: Time index
            arr: values array
            mag: String with the magnitude to assign
        """
        if mag == 'Y':
            self.create_profiles(index, arr)
        else:
            raise Exception('Magnitude ' + mag + ' not supported')

    def create_profiles(self, index, Y=None):
        """
        Create the load object default profiles
        Args:
            index: time index to use
            Y: admittance values
        Returns: Nothing
        """
        self.create_Y_profile(index, Y)

    def create_Y_profile(self, index, arr, arr_in_pu=False):
        """
        Create power profile based on index
        Args:
            index: time index to use
        Returns: Nothing
        """
        if arr_in_pu:
            dta = arr * self.Y
        else:
            dta = ones(len(index)) * self.Y if arr is None else arr
        self.Yprof = pd.DataFrame(data=dta, index=index, columns=[self.name])

    def get_profiles(self, index=None):
        """
        Get profiles and if the index is passed, create the profiles if needed
        Args:
            index: index of the Pandas DataFrame

        Returns:
            Power, Current and Impedance profiles
        """
        if index is not None:
            if self.Yprof is None:
                self.create_Y_profile(index)
        return self.Yprof

    def delete_profiles(self):
        """
        Delete the object profiles
        :return: 
        """
        self.Yprof = None

    def set_profile_values(self, t):
        """
        Set the profile values at t
        :param t: time index
        """
        self.Y = self.Yprof.values[t]

    def __str__(self):
        return self.name


class Circuit:

    def __init__(self, name='Circuit'):
        """
        Circuit constructor
        @param name: Name of the circuit
        """

        self.name = name

        # Base power (MVA)
        self.Sbase = 100.0

        # Base frequency in Hz
        self.fBase = 50.0

        # Should be able to accept Branches, Lines and Transformers alike
        self.branches = list()

        # array of branch indices in the master circuit
        self.branch_original_idx = list()

        # Should accept buses
        self.buses = list()

        # array of bus indices in the master circuit
        self.bus_original_idx = list()

        # Dictionary relating the bus object to its index. Updated upon compilation
        self.buses_dict = dict()

        # Object with the necessary inputs for a power flow study
        self.power_flow_input = None

        #  containing the power flow results
        self.power_flow_results = None

        # containing the short circuit results
        self.short_circuit_results = None

        # Object with the necessary inputs for th time series simulation
        self.time_series_input = None

        # Object with the time series simulation results
        self.time_series_results = None

        # Monte Carlo input object
        self.monte_carlo_input = None

        # Monte Carlo time series batch
        self.mc_time_series = None

        # Bus-Branch graph
        self.graph = None

    def clear(self):
        """
        Delete the Circuit content
        @return:
        """
        self.Sbase = 100
        self.branches = list()
        self.branch_original_idx = list()
        self.buses = list()
        self.bus_original_idx = list()

    def compile(self, time_profile=None, with_profiles=True, use_opf_vals=False, dispatch_storage=False):
        """
        Compile the circuit into all the needed arrays:
            - Ybus matrix
            - Sbus vector
            - Vbus vector
            - etc...
        """

        # declare length of arrays
        n = len(self.buses)
        m = len(self.branches)

        if time_profile is None:
            t = 0
        else:
            t = len(time_profile)

        # declare a graph
        self.graph = nx.Graph()

        # declare power flow results
        power_flow_input = PowerFlowInput(n, m)

        # time series inputs
        S_profile_data = zeros((t, n), dtype=complex)
        I_profile_data = zeros((t, n), dtype=complex)
        Y_profile_data = zeros((t, n), dtype=complex)
        S_prof_names = [None] * n
        I_prof_names = [None] * n
        Y_prof_names = [None] * n
        Scdf_ = [None] * n
        Icdf_ = [None] * n
        Ycdf_ = [None] * n
        time_series_input = None
        monte_carlo_input = None

        are_cdfs = False

        # Dictionary that helps referencing the nodes
        self.buses_dict = dict()

        # Compile the buses
        for i in range(n):

            # Add buses dictionary entry
            self.buses_dict[self.buses[i]] = i

            # set the name
            power_flow_input.bus_names[i] = self.buses[i].name

            # assign the nominal voltage value
            power_flow_input.Vnom[i] = self.buses[i].Vnom

            # Determine the bus type
            self.buses[i].determine_bus_type()

            # compute the bus magnitudes
            Y, I, S, V, Yprof, Iprof, Sprof, Y_cdf, I_cdf, S_cdf = self.buses[i].get_YISV(use_opf_vals=use_opf_vals,
                                                                                          dispatch_storage=dispatch_storage)

            # Assign the values to the simulation objects
            power_flow_input.Vbus[i] = V  # set the bus voltages
            power_flow_input.Sbus[i] += S  # set the bus power
            power_flow_input.Ibus[i] += I  # set the bus currents

            power_flow_input.Ybus[i, i] += Y / self.Sbase  # set the bus shunt impedance in per unit
            power_flow_input.Yshunt[i] += Y / self.Sbase  # copy the shunt impedance

            power_flow_input.types[i] = self.buses[i].type.value[0]  # set type

            power_flow_input.Vmin[i] = self.buses[i].Vmin  # in p.u.
            power_flow_input.Vmax[i] = self.buses[i].Vmax  # in p.u.
            power_flow_input.Qmin[i] = self.buses[i].Qmin_sum  # in MVAr
            power_flow_input.Qmax[i] = self.buses[i].Qmax_sum  # in MVAr

            # Compile all the time related variables

            # compute the time series arrays  ##############################################

            if Sprof is not None:
                S_profile_data[:, i] = Sprof.reshape(-1)
            if Iprof is not None:
                I_profile_data[:, i] = Iprof.reshape(-1)
            if Yprof is not None:
                Y_profile_data[:, i] = Yprof.reshape(-1)

            S_prof_names[i] = 'Sprof@Bus' + str(i)
            I_prof_names[i] = 'Iprof@Bus' + str(i)
            Y_prof_names[i] = 'Yprof@Bus' + str(i)

            # Store the CDF's for Monte Carlo ##############################################

            if S_cdf is None and S != complex(0, 0):
                S_cdf = CDF(array([S]))

            if I_cdf is None and I != complex(0, 0):
                I_cdf = CDF(array([I]))

            if Y_cdf is None and Y != complex(0, 0):
                Y_cdf = CDF(array([Y]))

            if S_cdf is not None or I_cdf is not None or Y_cdf is not None:
                are_cdfs = True

            Scdf_[i] = S_cdf
            Icdf_[i] = I_cdf
            Ycdf_[i] = Y_cdf

        # Compute the base magnitudes
        # (not needed since I and Y are given in MVA, you can demonstrate that only Sbase is needed to pass to p.u.)
        # Ibase = self.Sbase / (Vbase * sqrt3)
        # Ybase = self.Sbase / (Vbase * Vbase)

        # normalize_string the power array
        power_flow_input.Sbus /= self.Sbase

        # normalize_string the currents array (the I vector was given in MVA at v=1 p.u.)
        power_flow_input.Ibus /= self.Sbase

        # normalize the admittances array (the Y vector was given in MVA at v=1 p.u.)
        # At this point only the shunt and load related values are added here
        # power_flow_input.Ybus /= self.Sbase
        # power_flow_input.Yshunt /= self.Sbase

        # normalize_string the reactive power limits array (Q was given in MVAr)
        power_flow_input.Qmax /= self.Sbase
        power_flow_input.Qmin /= self.Sbase

        # make the profiles as DataFrames
        S_profile = pd.DataFrame(data=S_profile_data / self.Sbase, columns=S_prof_names, index=time_profile)
        I_profile = pd.DataFrame(data=I_profile_data / self.Sbase, columns=I_prof_names, index=time_profile)
        Y_profile = pd.DataFrame(data=Y_profile_data / self.Sbase, columns=Y_prof_names, index=time_profile)

        time_series_input = TimeSeriesInput(S_profile, I_profile, Y_profile)
        time_series_input.compile()

        if are_cdfs:
            monte_carlo_input = MonteCarloInput(n, Scdf_, Icdf_, Ycdf_)
        else:
            monte_carlo_input = None

        # Compile the branches
        for i in range(m):

            if self.branches[i].active:

                # get the from and to bus indices
                f = self.buses_dict[self.branches[i].bus_from]
                t = self.buses_dict[self.branches[i].bus_to]

                # apply the branch properties to the circuit matrices
                f, t = self.branches[i].apply_to(Ybus=power_flow_input.Ybus,
                                                 Yseries=power_flow_input.Yseries,
                                                 Yshunt=power_flow_input.Yshunt,
                                                 Yf=power_flow_input.Yf,
                                                 Yt=power_flow_input.Yt,
                                                 B1=power_flow_input.B1,
                                                 B2=power_flow_input.B2,
                                                 i=i, f=f, t=t)

                # Add graph edge (automatically adds the vertices)
                self.graph.add_edge(f, t)

                # Set the active flag in the active branches array
                power_flow_input.active_branches[i] = 1

                # Arrays with the from and to indices per bus
                power_flow_input.F[i] = f
                power_flow_input.T[i] = t

            # fill rate
            if self.branches[i].rate > 0:
                power_flow_input.branch_rates[i] = self.branches[i].rate
            else:
                power_flow_input.branch_rates[i] = 1e-6
                warn('The branch ' + str(i) + ' has no rate. Setting 1e-6 to avoid zero division.')

        # Assign the power flow inputs  button
        power_flow_input.compile()
        self.power_flow_input = power_flow_input
        self.time_series_input = time_series_input
        self.monte_carlo_input = monte_carlo_input

    def set_at(self, t, mc=False):
        """
        Set the current values given by the profile step of index t
        @param t: index of the profiles
        @param mc: Is this being run from MonteCarlo?
        @return: Nothing
        """
        if self.time_series_input is not None:
            if mc:

                if self.mc_time_series is None:
                    warn('No monte carlo inputs in island!!!')
                else:
                    self.power_flow_input.Sbus = self.mc_time_series.S[t, :] / self.Sbase
            else:
                self.power_flow_input.Sbus = self.time_series_input.S[t, :] / self.Sbase
        else:
            warn('No time series values')

    def sample_monte_carlo_batch(self, batch_size, use_latin_hypercube=False):
        """
        Samples a monte carlo batch as a time series object
        @param batch_size: size of the batch (integer)
        @return:
        """
        if self.monte_carlo_input is not None:
            self.mc_time_series = self.monte_carlo_input(batch_size, use_latin_hypercube)
        else:
            raise Exception('self.monte_carlo_input is None')

    def sample_at(self, x):
        """
        Get samples at x
        Args:
            x: values in [0, 1+ to sample the CDF

        Returns:

        """
        self.mc_time_series = self.monte_carlo_input.get_at(x)

    def get_loads(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.loads:
                elm.bus = bus
            lst = lst + bus.loads
        return lst

    def get_static_generators(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.static_generators:
                elm.bus = bus
            lst = lst + bus.static_generators
        return lst

    def get_shunts(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.shunts:
                elm.bus = bus
            lst = lst + bus.shunts
        return lst

    def get_controlled_generators(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.controlled_generators:
                elm.bus = bus
            lst = lst + bus.controlled_generators
        return lst

    def get_batteries(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.batteries:
                elm.bus = bus
            lst = lst + bus.batteries
        return lst

    def get_Jacobian(self, sparse=False):
        """
        Returns the Grid Jacobian matrix
        Returns:
            Grid Jacobian Matrix in CSR sparse format or as full matrix
        """

        # Initial magnitudes
        pvpq = r_[self.power_flow_input.pv, self.power_flow_input.pq]

        J = Jacobian(Ybus=self.power_flow_input.Ybus,
                     V=self.power_flow_input.Vbus,
                     Ibus=self.power_flow_input.Ibus,
                     pq=self.power_flow_input.pq,
                     pvpq=pvpq)

        if sparse:
            return J
        else:
            return J.todense()

    def get_bus_pf_results_df(self):
        """
        Returns a Pandas DataFrame with the bus results
        :return: DataFrame
        """

        cols = ['|V| (p.u.)', 'angle (rad)', 'P (p.u.)', 'Q (p.u.)', 'Qmin', 'Qmax', 'Q ok?']

        if self.power_flow_results is not None:
            q_l = self.power_flow_input.Qmin < self.power_flow_results.Sbus.imag
            q_h = self.power_flow_results.Sbus.imag < self.power_flow_input.Qmax
            q_ok = q_l * q_h
            data = c_[np.abs(self.power_flow_results.voltage),
                      np.angle(self.power_flow_results.voltage),
                      self.power_flow_results.Sbus.real,
                      self.power_flow_results.Sbus.imag,
                      self.power_flow_input.Qmin,
                      self.power_flow_input.Qmax,
                      q_ok.astype(np.bool)]
        else:
            data = [0, 0, 0, 0, 0, 0]

        return pd.DataFrame(data=data, index=self.power_flow_input.bus_names, columns=cols)

    def apply_lp_profiles(self):
        """
        Apply the LP results as device profiles
        :return:
        """
        for bus in self.buses:
            bus.apply_lp_profiles(self.Sbase)

    def copy(self):
        """
        Returns a deep (true) copy of this circuit
        @return:
        """

        cpy = Circuit()

        cpy.name = self.name

        bus_dict = dict()
        for bus in self.buses:
            bus_cpy = bus.copy()
            bus_dict[bus] = bus_cpy
            cpy.buses.append(bus_cpy)

        for branch in self.branches:
            cpy.branches.append(branch.copy(bus_dict))

        cpy.Sbase = self.Sbase

        cpy.branch_original_idx = self.branch_original_idx.copy()

        cpy.bus_original_idx = self.bus_original_idx.copy()

        cpy.time_series_input = self.time_series_input.copy()

        cpy.power_flow_input = self.power_flow_input.copy()

        return cpy

    def __str__(self):
        return self.name


class MultiCircuit(Circuit):

    def __init__(self):
        """
        Multi Circuit Constructor
        """
        Circuit.__init__(self)

        self.name = 'Grid'

        self.comments = ''

        # List of circuits contained within this circuit
        self.circuits = list()

        # self.power_flow_results = PowerFlowResults()

        self.bus_dictionary = dict()

        self.branch_dictionary = dict()

        self.has_time_series = False

        self.bus_names = None

        self.branch_names = None

        self.objects_with_profiles = [Load(), StaticGenerator(), ControlledGenerator(), Battery(), Shunt()]

        self.time_profile = None

        self.profile_magnitudes = dict()

        '''
        self.type_name = 'Shunt'

        self.properties_with_profile = ['Y']
        '''
        for dev in self.objects_with_profiles:
            if dev.properties_with_profile is not None:
                self.profile_magnitudes[dev.type_name] = dev.properties_with_profile

    def get_json_dict(self, id):
        """
        Get json dictionary
        :return: 
        """
        return {'id': id,
                'type': 'circuit',
                'phases': 'ps',
                'name': self.name,
                'Sbase': self.Sbase,
                'comments': self.comments}

    def load_file(self, filename):
        """
        Load GridCal compatible file
        @param filename:
        @return:
        """
        if os.path.exists(filename):
            name, file_extension = os.path.splitext(filename)
            # print(name, file_extension)
            if file_extension.lower() in ['.xls', '.xlsx']:

                ppc = load_from_xls(filename)

                # Pass the table-like data dictionary to objects in this circuit
                if 'version' not in ppc.keys():
                    from GridCal.Engine.Importers.matpower_parser import interpret_data_v1
                    interpret_data_v1(self, ppc)
                    return True
                elif ppc['version'] == 2.0:
                    self.interpret_data_v2(ppc)
                    return True
                else:
                    warn('The file could not be processed')
                    return False

            elif file_extension.lower() == '.dgs':
                from GridCal.Engine.Importers.DGS_Parser import dgs_to_circuit
                circ = dgs_to_circuit(filename)
                self.buses = circ.buses
                self.branches = circ.branches

            elif file_extension.lower() == '.m':
                from GridCal.Engine.Importers.matpower_parser import parse_matpower_file
                circ = parse_matpower_file(filename)
                self.buses = circ.buses
                self.branches = circ.branches

            elif file_extension.lower() == '.json':
                from GridCal.Engine.Importers.JSON_parser import parse_json
                circ = parse_json(filename)
                self.buses = circ.buses
                self.branches = circ.branches

            elif file_extension.lower() == '.raw':
                from GridCal.Engine.Importers.PSS_Parser import PSSeParser
                parser = PSSeParser(filename)
                circ = parser.circuit
                self.buses = circ.buses
                self.branches = circ.branches

        else:
            warn('The file does not exist.')
            return False

    def interpret_data_v2(self, data):
        """
        Interpret the new file version
        Args:
            data: Dictionary with the excel file sheet labels and the corresponding DataFrame

        Returns: Nothing, just applies the loaded data to this MultiCircuit instance

        """
        # print('Interpreting V2 data...')

        # clear all the data
        self.clear()

        self.name = data['name']

        # set the base magnitudes
        self.Sbase = data['baseMVA']

        # Set comments
        self.comments = data['Comments'] if 'Comments' in data.keys() else ''

        self.time_profile = None





        # common function
        def set_object_attributes(obj_, attr_list, values):
            for a, attr in enumerate(attr_list):

                # Hack to change the enabled by active...
                if attr == 'is_enabled':
                    attr = 'active'

                conv = obj.edit_types[attr]  # get the type converter
                if conv is None:
                    setattr(obj_, attr, values[a])
                else:
                    setattr(obj_, attr, conv(values[a]))

        # Add the buses
        lst = data['bus']
        hdr = lst.columns.values
        vals = lst.values
        bus_dict = dict()
        for i in range(len(lst)):
            obj = Bus()
            set_object_attributes(obj, hdr, vals[i, :])
            bus_dict[obj.name] = obj
            self.add_bus(obj)

        # Add the branches
        lst = data['branch']
        bus_from = lst['bus_from'].values
        bus_to = lst['bus_to'].values
        hdr = lst.columns.values
        hdr = delete(hdr, argwhere(hdr == 'bus_from'))
        hdr = delete(hdr, argwhere(hdr == 'bus_to'))
        vals = lst[hdr].values
        for i in range(len(lst)):

            try:
                obj = Branch(bus_from=bus_dict[str(bus_from[i])], bus_to=bus_dict[str(bus_to[i])])
            except KeyError as ex:
                raise Exception(str(i) + ': Branch bus is not in the buses list.\n' + str(ex))

            set_object_attributes(obj, hdr, vals[i, :])
            self.add_branch(obj)

        # add the loads
        lst = data['load']
        bus_from = lst['bus'].values
        hdr = lst.columns.values
        hdr = delete(hdr, argwhere(hdr == 'bus'))
        vals = lst[hdr].values
        for i in range(len(lst)):
            obj = Load()
            set_object_attributes(obj, hdr, vals[i, :])

            if 'load_Sprof' in data.keys():
                val = [complex(v) for v in data['load_Sprof'].values[:, i]]
                idx = data['load_Sprof'].index
                obj.Sprof = pd.DataFrame(data=val, index=idx)

                if self.time_profile is None:
                    self.time_profile = idx

            if 'load_Iprof' in data.keys():
                val = [complex(v) for v in data['load_Iprof'].values[:, i]]
                idx = data['load_Iprof'].index
                obj.Iprof = pd.DataFrame(data=val, index=idx)

                if self.time_profile is None:
                    self.time_profile = idx

            if 'load_Zprof' in data.keys():
                val = [complex(v) for v in data['load_Zprof'].values[:, i]]
                idx = data['load_Zprof'].index
                obj.Zprof = pd.DataFrame(data=val, index=idx)

                if self.time_profile is None:
                    self.time_profile = idx

            try:
                bus = bus_dict[str(bus_from[i])]
            except KeyError as ex:
                raise Exception(str(i) + ': Load bus is not in the buses list.\n' + str(ex))

            if obj.name == 'Load':
                obj.name += str(len(bus.loads) + 1) + '@' + bus.name

            obj.bus = bus
            bus.loads.append(obj)

        # add the controlled generators
        lst = data['controlled_generator']
        bus_from = lst['bus'].values
        hdr = lst.columns.values
        hdr = delete(hdr, argwhere(hdr == 'bus'))
        vals = lst[hdr].values
        for i in range(len(lst)):
            obj = ControlledGenerator()
            set_object_attributes(obj, hdr, vals[i, :])

            if 'CtrlGen_P_profiles' in data.keys():
                val = data['CtrlGen_P_profiles'].values[:, i]
                idx = data['CtrlGen_P_profiles'].index
                # obj.Pprof = pd.DataFrame(data=val, index=idx)
                obj.create_P_profile(index=idx, arr=val)

            if 'CtrlGen_Vset_profiles' in data.keys():
                val = data['CtrlGen_Vset_profiles'].values[:, i]
                idx = data['CtrlGen_Vset_profiles'].index
                obj.Vsetprof = pd.DataFrame(data=val, index=idx)

            try:
                bus = bus_dict[str(bus_from[i])]
            except KeyError as ex:
                raise Exception(str(i) + ': Controlled generator bus is not in the buses list.\n' + str(ex))

            if obj.name == 'gen':
                obj.name += str(len(bus.controlled_generators) + 1) + '@' + bus.name

            obj.bus = bus
            bus.controlled_generators.append(obj)

        # add the batteries
        lst = data['battery']
        bus_from = lst['bus'].values
        hdr = lst.columns.values
        hdr = delete(hdr, argwhere(hdr == 'bus'))
        vals = lst[hdr].values
        for i in range(len(lst)):
            obj = Battery()
            set_object_attributes(obj, hdr, vals[i, :])

            if 'battery_P_profiles' in data.keys():
                val = data['battery_P_profiles'].values[:, i]
                idx = data['battery_P_profiles'].index
                # obj.Pprof = pd.DataFrame(data=val, index=idx)
                obj.create_P_profile(index=idx, arr=val)

            if 'battery_Vset_profiles' in data.keys():
                val = data['battery_Vset_profiles'].values[:, i]
                idx = data['battery_Vset_profiles'].index
                obj.Vsetprof = pd.DataFrame(data=val, index=idx)

            try:
                bus = bus_dict[str(bus_from[i])]
            except KeyError as ex:
                raise Exception(str(i) + ': Battery bus is not in the buses list.\n' + str(ex))

            if obj.name == 'batt':
                obj.name += str(len(bus.batteries) + 1) + '@' + bus.name

            obj.bus = bus
            bus.batteries.append(obj)

        # add the static generators
        lst = data['static_generator']
        bus_from = lst['bus'].values
        hdr = lst.columns.values
        hdr = delete(hdr, argwhere(hdr == 'bus'))
        vals = lst[hdr].values
        for i in range(len(lst)):
            obj = StaticGenerator()
            set_object_attributes(obj, hdr, vals[i, :])

            if 'static_generator_Sprof' in data.keys():
                val = data['static_generator_Sprof'].values[:, i]
                idx = data['static_generator_Sprof'].index
                obj.Sprof = pd.DataFrame(data=val, index=idx)

            try:
                bus = bus_dict[str(bus_from[i])]
            except KeyError as ex:
                raise Exception(str(i) + ': Static generator bus is not in the buses list.\n' + str(ex))

            if obj.name == 'StaticGen':
                obj.name += str(len(bus.static_generators) + 1) + '@' + bus.name

            obj.bus = bus
            bus.static_generators.append(obj)

        # add the shunts
        lst = data['shunt']
        bus_from = lst['bus'].values
        hdr = lst.columns.values
        hdr = delete(hdr, argwhere(hdr == 'bus'))
        vals = lst[hdr].values
        for i in range(len(lst)):
            obj = Shunt()
            set_object_attributes(obj, hdr, vals[i, :])

            if 'shunt_Y_profiles' in data.keys():
                val = data['shunt_Y_profiles'].values[:, i]
                idx = data['shunt_Y_profiles'].index
                obj.Yprof = pd.DataFrame(data=val, index=idx)

            try:
                bus = bus_dict[str(bus_from[i])]
            except KeyError as ex:
                raise Exception(str(i) + ': Shunt bus is not in the buses list.\n' + str(ex))

            if obj.name == 'shunt':
                obj.name += str(len(bus.shunts) + 1) + '@' + bus.name

            obj.bus = bus
            bus.shunts.append(obj)

        # print('Done!')

    def save_file(self, file_path):
        """
        Save File
        :param file_path: 
        :return: 
        """
        if file_path.endswith('.xlsx'):
            self.save_excel(file_path)
        elif file_path.endswith('.json'):
            self.save_json(file_path)
        elif file_path.endswith('.xml'):
            self.save_cim(file_path)
        else:
            raise Exception('File path extension not understood\n' + file_path)

    def save_excel(self, file_path):
        """
        Save the circuit information
        :param file_path: file path to save
        :return:
        """
        dfs = dict()

        # configuration ################################################################################################
        obj = list()
        obj.append(['BaseMVA', self.Sbase])
        obj.append(['Version', 2])
        obj.append(['Name', self.name])
        obj.append(['Comments', self.comments])
        dfs['config'] = pd.DataFrame(data=obj, columns=['Property', 'Value'])

        # get the master time profile
        T = self.time_profile

        # buses ########################################################################################################
        obj = list()
        names_count = dict()
        for elm in self.buses:

            # check name: if the name is repeated, change it so that it is not
            if elm.name in names_count.keys():
                names_count[elm.name] += 1
                elm.name = elm.name + '_' + str(names_count[elm.name])
            else:
                names_count[elm.name] = 1

            obj.append(elm.get_save_data())
        dfs['bus'] = pd.DataFrame(data=array(obj).astype('str'), columns=Bus().edit_headers)

        # branches #####################################################################################################
        obj = list()
        for elm in self.branches:
            obj.append(elm.get_save_data())
        dfs['branch'] = pd.DataFrame(data=obj, columns=Branch(None, None).edit_headers)

        # loads ########################################################################################################
        obj = list()
        s_profiles = None
        i_profiles = None
        z_profiles = None
        hdr = list()
        for elm in self.get_loads():
            obj.append(elm.get_save_data())
            hdr.append(elm.name)
            if T is not None:
                if s_profiles is None and elm.Sprof is not None:
                    s_profiles = elm.Sprof.values
                    i_profiles = elm.Iprof.values
                    z_profiles = elm.Zprof.values
                else:
                    s_profiles = c_[s_profiles, elm.Sprof.values]
                    i_profiles = c_[i_profiles, elm.Iprof.values]
                    z_profiles = c_[z_profiles, elm.Zprof.values]

        dfs['load'] = pd.DataFrame(data=obj, columns=Load().edit_headers)

        if s_profiles is not None:
            dfs['load_Sprof'] = pd.DataFrame(data=s_profiles.astype('str'), columns=hdr, index=T)
            dfs['load_Iprof'] = pd.DataFrame(data=i_profiles.astype('str'), columns=hdr, index=T)
            dfs['load_Zprof'] = pd.DataFrame(data=z_profiles.astype('str'), columns=hdr, index=T)

        # static generators ############################################################################################
        obj = list()
        hdr = list()
        s_profiles = None
        for elm in self.get_static_generators():
            obj.append(elm.get_save_data())
            hdr.append(elm.name)
            if T is not None:
                if s_profiles is None and elm.Sprof is not None:
                    s_profiles = elm.Sprof.values
                else:
                    s_profiles = c_[s_profiles, elm.Sprof.values]

        dfs['static_generator'] = pd.DataFrame(data=obj, columns=StaticGenerator().edit_headers)

        if s_profiles is not None:
            dfs['static_generator_Sprof'] = pd.DataFrame(data=s_profiles.astype('str'), columns=hdr, index=T)

        # battery ######################################################################################################
        obj = list()
        hdr = list()
        v_set_profiles = None
        p_profiles = None
        for elm in self.get_batteries():
            obj.append(elm.get_save_data())
            hdr.append(elm.name)
            if T is not None:
                if p_profiles is None and elm.Pprof is not None:
                    p_profiles = elm.Pprof.values
                    v_set_profiles = elm.Vsetprof.values
                else:
                    p_profiles = c_[p_profiles, elm.Pprof.values]
                    v_set_profiles = c_[v_set_profiles, elm.Vsetprof.values]
        dfs['battery'] = pd.DataFrame(data=obj, columns=Battery().edit_headers)

        if p_profiles is not None:
            dfs['battery_Vset_profiles'] = pd.DataFrame(data=v_set_profiles, columns=hdr, index=T)
            dfs['battery_P_profiles'] = pd.DataFrame(data=p_profiles, columns=hdr, index=T)

        # controlled generator
        obj = list()
        hdr = list()
        v_set_profiles = None
        p_profiles = None
        for elm in self.get_controlled_generators():
            obj.append(elm.get_save_data())
            hdr.append(elm.name)
            if T is not None and elm.Pprof is not None:
                if p_profiles is None:
                    p_profiles = elm.Pprof.values
                    v_set_profiles = elm.Vsetprof.values
                else:
                    p_profiles = c_[p_profiles, elm.Pprof.values]
                    v_set_profiles = c_[v_set_profiles, elm.Vsetprof.values]
        dfs['controlled_generator'] = pd.DataFrame(data=obj, columns=ControlledGenerator().edit_headers)
        if p_profiles is not None:
            dfs['CtrlGen_Vset_profiles'] = pd.DataFrame(data=v_set_profiles, columns=hdr, index=T)
            dfs['CtrlGen_P_profiles'] = pd.DataFrame(data=p_profiles, columns=hdr, index=T)

        # shunt
        obj = list()
        hdr = list()
        y_profiles = None
        for elm in self.get_shunts():
            obj.append(elm.get_save_data())
            hdr.append(elm.name)
            if T is not None:
                if y_profiles is None and elm.Yprof.values is not None:
                    y_profiles = elm.Yprof.values
                else:
                    y_profiles = c_[y_profiles, elm.Yprof.values]

        dfs['shunt'] = pd.DataFrame(data=obj, columns=Shunt().edit_headers)

        if y_profiles is not None:
            dfs['shunt_Y_profiles'] = pd.DataFrame(data=y_profiles.astype(str), columns=hdr, index=T)

        # flush-save
        writer = pd.ExcelWriter(file_path)
        for key in dfs.keys():
            dfs[key].to_excel(writer, key)

        writer.save()

    def save_json(self, file_path):
        """
        
        :param file_path: 
        :return: 
        """

        from GridCal.Engine.Importers.JSON_parser import save_json_file
        save_json_file(file_path, self)

    def save_cim(self, file_path):
        """

        :param file_path:
        :return:
        """

        from GridCal.Engine.Importers.CIM import CimExport

        cim = CimExport(self)

        cim.save(file_name=file_path)

    def save_calculation_objects(self, file_path):
        """
        Save all the calculation objects of all the grids
        Args:
            file_path: path to file

        Returns:

        """
        writer = pd.ExcelWriter(file_path)

        for c, circuit in enumerate(self.circuits):

            for elm_type in circuit.power_flow_input.available_structures:

                name = elm_type + '_' + str(c)
                df = circuit.power_flow_input.get_structure(elm_type).astype(str)
                df.to_excel(writer, name)

        writer.save()

    def compile(self, use_opf_vals=False, dispatch_storage=False):
        """
        Divide the grid into the different possible grids
        @return:
        """

        n = len(self.buses)
        m = len(self.branches)
        self.power_flow_input = PowerFlowInput(n, m)

        self.time_series_input = TimeSeriesInput()

        self.graph = nx.Graph()

        self.circuits = list()

        self.has_time_series = True

        self.bus_names = zeros(n, dtype=object)
        self.branch_names = zeros(m, dtype=object)

        # create bus dictionary
        for i in range(n):
            self.bus_dictionary[self.buses[i]] = i
            self.bus_names[i] = self.buses[i].name

        # Compile the branches
        for i in range(m):
            self.branch_names[i] = self.branches[i].name
            if self.branches[i].active:
                if self.branches[i].bus_from.active and self.branches[i].bus_to.active:
                    f = self.bus_dictionary[self.branches[i].bus_from]
                    t = self.bus_dictionary[self.branches[i].bus_to]
                    # Add graph edge (automatically adds the vertices)
                    self.graph.add_edge(f, t, length=self.branches[i].R)
                    self.branch_dictionary[self.branches[i]] = i

        # Split the graph into islands
        islands = [list(isl) for isl in connected_components(self.graph)]

        isl_idx = 0
        for island in islands:

            # Convert island to dictionary
            isl_dict = dict()
            for idx in range(len(island)):
                isl_dict[island[idx]] = idx

            # create circuit of the island
            circuit = Circuit(name='Island ' + str(isl_idx))

            # Set buses of the island
            circuit.buses = [self.buses[b] for b in island]
            circuit.bus_original_idx = island

            # set branches of the island
            for i in range(m):
                f = self.bus_dictionary[self.branches[i].bus_from]
                t = self.bus_dictionary[self.branches[i].bus_to]
                if f in island and t in island:
                    # Copy the branch into a new
                    branch = self.branches[i].copy()
                    # Add the branch to the circuit
                    circuit.branches.append(branch)
                    circuit.branch_original_idx.append(i)

            circuit.compile(self.time_profile, use_opf_vals=use_opf_vals, dispatch_storage=dispatch_storage)

            # initialize the multi circuit power flow inputs (for later use in displays and such)
            self.power_flow_input.set_from(circuit.power_flow_input,
                                           circuit.bus_original_idx,
                                           circuit.branch_original_idx)

            # initialize the multi circuit time series inputs (for later use in displays and such)
            self.time_series_input.apply_from_island(circuit.time_series_input,
                                                     circuit.bus_original_idx,
                                                     circuit.branch_original_idx,
                                                     n, m)

            self.circuits.append(circuit)

            self.has_time_series = self.has_time_series and circuit.time_series_input.valid

            isl_idx += 1

        pass

    def create_profiles(self, steps, step_length, step_unit, time_base: datetime = datetime.now()):
        """
        Set the default profiles in all the objects enabled to have profiles
        Args:
            steps: Number of time steps
            step_length: time length (1, 2, 15, ...)
            step_unit: unit of the time step
            time_base: Date to start from
        """

        index = [None] * steps
        for i in range(steps):
            if step_unit == 'h':
                index[i] = time_base + timedelta(hours=i * step_length)
            elif step_unit == 'm':
                index[i] = time_base + timedelta(minutes=i * step_length)
            elif step_unit == 's':
                index[i] = time_base + timedelta(seconds=i * step_length)

        self.format_profiles(index)

    def format_profiles(self, index):
        """
        Format the pandas profiles in place using a time index
        Args:
            index: Time profile
        """

        self.time_profile = array(index)

        for bus in self.buses:

            for elm in bus.loads:
                elm.create_profiles(index)

            for elm in bus.static_generators:
                elm.create_profiles(index)

            for elm in bus.controlled_generators:
                elm.create_profiles(index)

            for elm in bus.batteries:
                elm.create_profiles(index)

            for elm in bus.shunts:
                elm.create_profiles(index)

    def get_node_elements_by_type(self, element_type):
        """
        Get set of elements and their parent nodes
        Args:
            element_type: String {'Load', 'StaticGenerator', 'ControlledGenerator', 'Battery', 'Shunt'}

        Returns: List of elements, list of matching parent buses
        """
        elements = list()
        parent_buses = list()

        if element_type == 'Load':
            for bus in self.buses:
                for elm in bus.loads:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif element_type == 'StaticGenerator':
            for bus in self.buses:
                for elm in bus.static_generators:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif element_type == 'ControlledGenerator':
            for bus in self.buses:
                for elm in bus.controlled_generators:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif element_type == 'Battery':
            for bus in self.buses:
                for elm in bus.batteries:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif element_type == 'Shunt':
            for bus in self.buses:
                for elm in bus.shunts:
                    elements.append(elm)
                    parent_buses.append(bus)

        return elements, parent_buses

    def set_power(self, S):
        """
        Set the power array in the circuits
        @param S: Array of power values in MVA for all the nodes in all the islands
        """
        for circuit_island in self.circuits:
            idx = circuit_island.bus_original_idx  # get the buses original indexing in the island
            circuit_island.power_flow_input.Sbus = S[idx]  # set the values

    def add_bus(self, obj: Bus):
        """
        Add bus keeping track of it as object
        @param obj:
        """
        self.buses.append(obj)

    def delete_bus(self, obj: Bus):
        """
        Remove bus
        @param obj: Bus object
        """

        # remove associated branches in reverse order
        for i in range(len(self.branches) - 1, -1, -1):
            if self.branches[i].bus_from == obj or self.branches[i].bus_to == obj:
                self.branches.pop(i)

        # remove the bus itself
        self.buses.remove(obj)

    def add_branch(self, obj: Branch):
        """
        Add a branch object to the circuit
        @param obj: Branch object
        """
        self.branches.append(obj)

    def delete_branch(self, obj: Branch):
        """
        Delete a branch object from the circuit
        @param obj:
        """
        self.branches.remove(obj)

    def add_load(self, bus: Bus, api_obj=None):
        """
        Add load object to a bus
        Args:
            bus: Bus object
            api_obj: Load object
        """
        if api_obj is None:
            api_obj = Load()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        if api_obj.name == 'Load':
            api_obj.name += '@' + bus.name

        bus.loads.append(api_obj)

        return api_obj

    def add_controlled_generator(self, bus: Bus, api_obj=None):
        """
        Add controlled generator to a bus
        Args:
            bus: Bus object
            api_obj: ControlledGenerator object
        """
        if api_obj is None:
            api_obj = ControlledGenerator()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.controlled_generators.append(api_obj)

        return api_obj

    def add_static_generator(self, bus: Bus, api_obj=None):
        """
        Add a static generator object to a bus
        Args:
            bus: Bus object to add it to
            api_obj: StaticGenerator object
        """
        if api_obj is None:
            api_obj = StaticGenerator()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.static_generators.append(api_obj)

        return api_obj

    def add_battery(self, bus: Bus, api_obj=None):
        """
        Add battery object to a bus
        Args:
            bus: Bus object to add it to
            api_obj: Battery object to add it to
        """
        if api_obj is None:
            api_obj = Battery()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.batteries.append(api_obj)

        return api_obj

    def add_shunt(self, bus: Bus, api_obj=None):
        """
        Add shunt object to a bus
        Args:
            bus: Bus object to add it to
            api_obj: Shunt object
        """
        if api_obj is None:
            api_obj = Shunt()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.shunts.append(api_obj)

        return api_obj

    def plot_graph(self, ax=None):
        """
        Plot the grid
        @param ax: Matplotlib axis object
        @return: Nothing
        """
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        nx.draw_spring(self.graph, ax=ax)

    def export_pf(self, file_name):
        """
        Export power flow results to file
        :param file_name: Excel file name
        :return: Nothing
        """

        if self.power_flow_results is not None:
            df_bus, df_branch = self.power_flow_results.export_all()

            df_bus.index = self.bus_names
            df_branch.index = self.branch_names

            writer = pd.ExcelWriter(file_name)
            df_bus.to_excel(writer, 'Bus results')
            df_branch.to_excel(writer, 'Branch results')
            writer.save()
        else:
            raise Exception('There are no power flow results!')

    def export_profiles(self, file_name):
        """
        Export object profiles to file
        :param file_name: Excel file name
        :return: Nothing
        """

        if self.time_profile is not None:

            # collect data
            P = list()
            Q = list()
            Ir = list()
            Ii = list()
            G = list()
            B = list()
            P_gen = list()
            V_gen = list()
            E_batt = list()

            load_names = list()
            gen_names = list()
            bat_names = list()

            for bus in self.buses:

                for elm in bus.loads:
                    load_names.append(elm.name)
                    P.append(elm.Sprof.values.real[:, 0])
                    Q.append(elm.Sprof.values.imag[:, 0])

                    Ir.append(elm.Iprof.values.real[:, 0])
                    Ii.append(elm.Iprof.values.imag[:, 0])

                    G.append(elm.Zprof.values.real[:, 0])
                    B.append(elm.Zprof.values.imag[:, 0])

                for elm in bus.controlled_generators:
                    gen_names.append(elm.name)

                    P_gen.append(elm.Pprof.values[:, 0])
                    V_gen.append(elm.Vsetprof.values[:, 0])

                for elm in bus.batteries:
                    bat_names.append(elm.name)
                    gen_names.append(elm.name)
                    P_gen.append(elm.Pprof.values[:, 0])
                    V_gen.append(elm.Vsetprof.values[:, 0])
                    E_batt.append(elm.energy_array.values[:, 0])

            # form DataFrames
            P = pd.DataFrame(data=np.array(P).transpose(), index=self.time_profile, columns=load_names)
            Q = pd.DataFrame(data=np.array(Q).transpose(), index=self.time_profile, columns=load_names)
            Ir = pd.DataFrame(data=np.array(Ir).transpose(), index=self.time_profile, columns=load_names)
            Ii = pd.DataFrame(data=np.array(Ii).transpose(), index=self.time_profile, columns=load_names)
            G = pd.DataFrame(data=np.array(G).transpose(), index=self.time_profile, columns=load_names)
            B = pd.DataFrame(data=np.array(B).transpose(), index=self.time_profile, columns=load_names)
            P_gen = pd.DataFrame(data=np.array(P_gen).transpose(), index=self.time_profile, columns=gen_names)
            V_gen = pd.DataFrame(data=np.array(V_gen).transpose(), index=self.time_profile, columns=gen_names)
            E_batt = pd.DataFrame(data=np.array(E_batt).transpose(), index=self.time_profile, columns=bat_names)

            writer = pd.ExcelWriter(file_name)
            P.to_excel(writer, 'P loads')
            Q.to_excel(writer, 'Q loads')

            Ir.to_excel(writer, 'Ir loads')
            Ii.to_excel(writer, 'Ii loads')

            G.to_excel(writer, 'G loads')
            B.to_excel(writer, 'B loads')

            P_gen.to_excel(writer, 'P generators')
            V_gen.to_excel(writer, 'V generators')

            E_batt.to_excel(writer, 'Energy batteries')
            writer.save()
        else:
            raise Exception('There are no time series!')

    def copy(self):
        """
        Returns a deep (true) copy of this circuit
        @return:
        """

        cpy = MultiCircuit()

        cpy.name = self.name

        bus_dict = dict()
        for bus in self.buses:
            bus_cpy = bus.copy()
            bus_dict[bus] = bus_cpy
            cpy.add_bus(bus_cpy)

        for branch in self.branches:
            cpy.add_branch(branch.copy(bus_dict))

        cpy.time_profile = self.time_profile

        return cpy

    def dispatch(self):
        """
        Dispatch either load or generation using a simple equalised share rule of the shedding to be done
        @return: Nothing
        """
        if self.power_flow_input is not None:

            # get the total power balance
            balance = abs(self.power_flow_input.Sbus.sum())

            if balance > 0:  # more generation than load, dispatch generation
                Gmax = 0
                Lt = 0
                for bus in self.buses:
                    for load in bus.loads:
                        Lt += abs(load.S)
                    for gen in bus.controlled_generators:
                        Gmax += abs(gen.Snom)

                # reassign load
                factor = Lt / Gmax
                print('Decreasing generation by ', factor * 100, '%')
                for bus in self.buses:
                    for gen in bus.controlled_generators:
                        gen.P *= factor

            elif balance < 0:  # more load than generation, dispatch load

                Gmax = 0
                Lt = 0
                for bus in self.buses:
                    for load in bus.loads:
                        Lt += abs(load.S)
                    for gen in bus.controlled_generators:
                        Gmax += abs(gen.P + 1j * gen.Qmax)

                # reassign load
                factor = Gmax / Lt
                print('Decreasing load by ', factor * 100, '%')
                for bus in self.buses:
                    for load in bus.loads:
                        load.S *= factor

            else:  # nothing to do
                pass

        else:
            warn('The grid must be compiled before dispatching it')

    def set_state(self, t):
        """
        Set the profiles state at the index t as the default values
        :param t:
        :return:
        """
        for bus in self.buses:
            bus.set_state(t)


########################################################################################################################
# Power flow classes
########################################################################################################################


class PowerFlowOptions:

    def __init__(self, solver_type: SolverType = SolverType.NR, aux_solver_type: SolverType = SolverType.HELM,
                 verbose=False, robust=False, initialize_with_existing_solution=True,
                 tolerance=1e-6, max_iter=25, control_q=True, multi_core=True, dispatch_storage=False):
        """
        Power flow execution options
        @param solver_type:
        @param aux_solver_type:
        @param verbose:
        @param robust:
        @param initialize_with_existing_solution:
        @param dispatch_storage:
        @param tolerance:
        @param max_iter:
        @param control_q:
        """
        self.solver_type = solver_type

        self.auxiliary_solver_type = aux_solver_type

        self.tolerance = tolerance

        self.max_iter = max_iter

        self.control_Q = control_q

        self.verbose = verbose

        self.robust = robust

        self.initialize_with_existing_solution = initialize_with_existing_solution

        self.multi_thread = multi_core

        self.dispatch_storage = dispatch_storage


class PowerFlowInput:

    def __init__(self, n, m):
        """
        Power Flow study input values
        @param n: Number of buses
        @param m: Number of branches
        """
        self.n = n

        self.m = m

        # Array of integer values representing the buses types
        self.types = zeros(n, dtype=int)

        self.ref = None

        self.pv = None

        self.pq = None

        self.sto = None

        self.pqpv = None

        # Branch admittance matrix with the from buses
        self.Yf = lil_matrix((m, n), dtype=complex)

        # Branch admittance matrix with the to buses
        self.Yt = lil_matrix((m, n), dtype=complex)

        # Array with the 'from' index of the from bus of each branch
        self.F = zeros(m, dtype=int)

        # Array with the 'to' index of the from bus of each branch
        self.T = zeros(m, dtype=int)

        # array to store a 1 for the active branches
        self.active_branches = zeros(m, dtype=int)

        # Full admittance matrix (will be converted to sparse)
        self.Ybus = lil_matrix((n, n), dtype=complex)

        # Full impedance matrix (will be computed upon requirement ad the inverse of Ybus)
        self.Zbus = None

        # Admittance matrix of the series elements (will be converted to sparse)
        self.Yseries = lil_matrix((n, n), dtype=complex)

        # Admittance matrix of the shunt elements (actually it is only the diagonal, so let's make it a vector)
        self.Yshunt = zeros(n, dtype=complex)

        # Jacobian matrix 1 for the fast-decoupled power flow
        self.B1 = lil_matrix((n, n), dtype=double)

        # Jacobian matrix 2 for the fast-decoupled power flow
        self.B2 = lil_matrix((n, n), dtype=double)

        # Array of line-line nominal voltages of the buses
        self.Vnom = zeros(n)

        # Currents at the buses array
        self.Ibus = zeros(n, dtype=complex)

        # Powers at the buses array
        self.Sbus = zeros(n, dtype=complex)

        # Voltages at the buses array
        self.Vbus = zeros(n, dtype=complex)

        self.Vmin = zeros(n, dtype=double)

        self.Vmax = zeros(n, dtype=double)

        self.Qmin = ones(n, dtype=double) * -9999

        self.Qmax = ones(n, dtype=double) * 9999

        self.branch_rates = zeros(m)

        self.bus_names = zeros(n, dtype=object)

        self.available_structures = ['Vbus', 'Sbus', 'Ibus', 'Ybus', 'Yshunt', 'Yseries', 'Types', 'Jacobian']

    def compile(self):
        """
        Make the matrices sparse
        Create the ref, pv and pq lists
        @return:
        """
        self.Yf = csc_matrix(self.Yf)
        self.Yt = csc_matrix(self.Yt)
        self.Ybus = csc_matrix(self.Ybus)
        self.Yseries = csc_matrix(self.Yseries)
        self.B1 = csc_matrix(self.B1)
        self.B2 = csc_matrix(self.B2)
        # self.Yshunt = sparse(self.Yshunt)  No need to make it sparse, it is a vector already
        # compile the types lists from the types vector
        self.compile_types()

    def mismatch(self, V, Sbus):
        """
        Compute the power flow mismatch
        @param V: Voltage array (calculated)
        @param Sbus: Power array (especified)
        @return: mismatch of the computed solution
        """
        Scalc = V * conj(self.Ybus * V)
        mis = Scalc - Sbus  # compute the mismatch
        F = r_[mis[self.pv].real,
               mis[self.pq].real,
               mis[self.pq].imag]

        # check tolerance
        normF = linalg.norm(F, Inf)

        return normF

    def compile_types(self, types_new=None):
        """
        Compile the types
        @return:
        """
        if types_new is not None:
            self.types = types_new.copy()
        self.pq = where(self.types == NodeType.PQ.value[0])[0]
        self.pv = where(self.types == NodeType.PV.value[0])[0]
        self.ref = where(self.types == NodeType.REF.value[0])[0]
        self.sto = where(self.types == NodeType.STO_DISPATCH.value)[0]

        if len(self.ref) == 0:  # there is no slack!

            if len(self.pv) == 0:  # there are no pv neither -> blackout grid

                warn('There are no slack nodes selected')

            else:  # select the first PV generator as the slack

                mx = max(self.Sbus[self.pv])
                if mx > 0:
                    # find the generator that is injecting the most
                    i = where(self.Sbus == mx)[0][0]

                else:
                    # all the generators are injecting zero, pick the first pv
                    i = self.pv[0]

                # delete the selected pv bus from the pv list and put it in the slack list
                self.pv = delete(self.pv, where(self.pv == i)[0])
                self.ref = [i]
                # print('Setting bus', i, 'as slack')

            self.ref = ndarray.flatten(array(self.ref))
            self.types[self.ref] = NodeType.REF.value[0]
        else:
            pass  # no problem :)

        self.pqpv = r_[self.pq, self.pv]
        self.pqpv.sort()
        pass

    def set_from(self, obj, bus_idx, br_idx):
        """
        Copy data from other PowerFlowInput object
        @param obj: PowerFlowInput instance
        @param bus_idx: original bus indices
        @param br_idx: original branch indices
        @return:
        """
        self.types[bus_idx] = obj.types

        self.bus_names[bus_idx] = obj.bus_names

        # self.ref = None
        #
        # self.pv = None
        #
        # self.pq = None
        #
        # self.sto = None

        # Branch admittance matrix with the from buses
        self.Yf[br_idx, :][:, bus_idx] = obj.Yf.todense()

        # Branch admittance matrix with the to buses
        self.Yt[br_idx, :][:, bus_idx] = obj.Yt.todense()

        # Array with the 'from' index of the from bus of each branch
        self.F[br_idx] = obj.F

        # Array with the 'to' index of the from bus of each branch
        self.T[br_idx] = obj.T

        # array to store a 1 for the active branches
        self.active_branches[br_idx] = obj.active_branches

        # Full admittance matrix (will be converted to sparse)
        self.Ybus[bus_idx, :][:, bus_idx] = obj.Ybus.todense()

        # Admittance matrix of the series elements (will be converted to sparse)
        self.Yseries[bus_idx, :][:, bus_idx] = obj.Yseries.todense()

        # Admittance matrix of the shunt elements (will be converted to sparse)
        self.Yshunt[bus_idx] = obj.Yshunt

        # Currents at the buses array
        self.Ibus[bus_idx] = obj.Ibus

        # Powers at the buses array
        self.Sbus[bus_idx] = obj.Sbus

        # Voltages at the buses array
        self.Vbus[bus_idx] = obj.Vbus

        self.Vmin[bus_idx] = obj.Vmin

        self.Vmax[bus_idx] = obj.Vmax

        # self.Qmin = ones(n, dtype=double) * -9999
        #
        # self.Qmax = ones(n, dtype=double) * 9999

        self.branch_rates[br_idx] = obj.branch_rates

        self.compile()

    def get_structure(self, structure_type):
        """
        Get a DataFrame with the input
        Args:
            structure_type: 'Vbus', 'Sbus', 'Ibus', 'Ybus', 'Yshunt', 'Yseries', 'Types'

        Returns: Pandas DataFrame
        """

        if structure_type == 'Vbus':

            df = pd.DataFrame(data=self.Vbus, columns=['Voltage (p.u.)'], index=self.bus_names)

        elif structure_type == 'Sbus':
            df = pd.DataFrame(data=self.Sbus, columns=['Power (p.u.)'], index=self.bus_names)

        elif structure_type == 'Ibus':
            df = pd.DataFrame(data=self.Ibus, columns=['Current (p.u.)'], index=self.bus_names)

        elif structure_type == 'Ybus':
            df = pd.DataFrame(data=self.Ybus.toarray(), columns=self.bus_names, index=self.bus_names)

        elif structure_type == 'Yshunt':
            df = pd.DataFrame(data=self.Yshunt, columns=['Shunt admittance (p.u.)'], index=self.bus_names)

        elif structure_type == 'Yseries':
            df = pd.DataFrame(data=self.Yseries.toarray(), columns=self.bus_names, index=self.bus_names)

        elif structure_type == 'Types':
            df = pd.DataFrame(data=self.types, columns=['Bus types'], index=self.bus_names)

        elif structure_type == 'Jacobian':

            J = Jacobian(self.Ybus, self.Vbus, self.Ibus, self.pq, self.pqpv)

            """
            J11 = dS_dVa[array([pvpq]).T, pvpq].real
            J12 = dS_dVm[array([pvpq]).T, pq].real
            J21 = dS_dVa[array([pq]).T, pvpq].imag
            J22 = dS_dVm[array([pq]).T, pq].imag
            """
            npq = len(self.pq)
            npv = len(self.pv)
            npqpv = npq + npv
            cols = ['dS/dVa'] * npqpv + ['dS/dVm'] * npq
            rows = cols
            df = pd.DataFrame(data=J.toarray(), columns=cols, index=rows)

        else:

            raise Exception('PF input: structure type not found')

        return df

    def copy(self):

        cpy = PowerFlowInput(self.n, self.m)

        cpy.types = self.types.copy()

        cpy.ref = self.ref.copy()

        cpy.pv = self.pv.copy()

        cpy.pq = self.pq.copy()

        cpy.sto = self.sto.copy()

        cpy.pqpv = self.pqpv.copy()

        # Branch admittance matrix with the from buses
        cpy.Yf = self.Yf.copy()

        # Branch admittance matrix with the to buses
        cpy.Yt = self.Yt.copy()

        # Array with the 'from' index of the from bus of each branch
        cpy.F = self.F.copy()

        # Array with the 'to' index of the from bus of each branch
        cpy.T = self.T.copy()

        # array to store a 1 for the active branches
        cpy.active_branches = self.active_branches.copy()

        # Full admittance matrix (will be converted to sparse)
        cpy.Ybus = self.Ybus.copy()

        # Full impedance matrix (will be computed upon requirement ad the inverse of Ybus)
        # self.Zbus = None

        # Admittance matrix of the series elements (will be converted to sparse)
        cpy.Yseries = self.Yseries.copy()

        # Admittance matrix of the shunt elements (actually it is only the diagonal, so let's make it a vector)
        cpy.Yshunt = self.Yshunt.copy()

        # Jacobian matrix 1 for the fast-decoupled power flow
        cpy.B1 = self.B1.copy()

        # Jacobian matrix 2 for the fast-decoupled power flow
        cpy.B2 = self.B2.copy()

        # Array of line-line nominal voltages of the buses
        cpy.Vnom = self.Vnom.copy()

        # Currents at the buses array
        cpy.Ibus = self.Ibus.copy()

        # Powers at the buses array
        cpy.Sbus = self.Sbus.copy()

        # Voltages at the buses array
        cpy.Vbus = self.Vbus.copy()

        cpy.Vmin = self.Vmin.copy()

        cpy.Vmax = self.Vmax.copy()

        cpy.Qmin = self.Qmin.copy()

        cpy.Qmax = self.Qmax.copy()

        cpy.branch_rates = self.branch_rates.copy()

        cpy.bus_names = self.bus_names.copy()

        cpy.available_structures = self.available_structures.copy()

        return cpy


class PowerFlowResults:

    def __init__(self, Sbus=None, voltage=None, Sbranch=None, Ibranch=None, loading=None, losses=None, error=None,
                 converged=None, Qpv=None, inner_it=None, outer_it=None, elapsed=None, methods=None):
        """

        @param voltage: Voltages array (p.u.)
        @param Sbranch: Branches power array (MVA)
        @param Ibranch: Branches current array (p.u.)
        @param loading: Branches loading array (p.u.)
        @param losses: Branches losses array (MW)
        @param error: power flow error value
        @param converged: converged (True / False)
        @param Qpv: Reactive power at the PV nodes array (p.u.)
        """
        self.Sbus = Sbus

        self.voltage = voltage

        self.Sbranch = Sbranch

        self.Ibranch = Ibranch

        self.loading = loading

        self.losses = losses

        self.error = error

        self.converged = converged

        self.Qpv = Qpv

        self.overloads = None

        self.overvoltage = None

        self.undervoltage = None

        self.overloads_idx = None

        self.overvoltage_idx = None

        self.undervoltage_idx = None

        self.buses_useful_for_storage = None

        self.available_results = ['Bus voltage', 'Branch power', 'Branch current', 'Branch_loading', 'Branch losses']

        self.plot_bars_limit = 100

        self.inner_iterations = inner_it

        self.outer_iterations = outer_it

        self.elapsed = elapsed

        self.methods = methods

    def copy(self):
        """
        Return a copy of this
        @return:
        """
        return PowerFlowResults(Sbus=self.Sbus, voltage=self.voltage, Sbranch=self.Sbranch,
                                Ibranch=self.Ibranch, loading=self.loading,
                                losses=self.losses, error=self.error,
                                converged=self.converged, Qpv=self.Qpv, inner_it=self.inner_iterations,
                                outer_it=self.outer_iterations, elapsed=self.elapsed, methods=self.methods)

    def initialize(self, n, m):
        """
        Initialize the arrays
        @param n: number of buses
        @param m: number of branches
        @return:
        """
        self.Sbus = zeros(n, dtype=complex)

        self.voltage = zeros(n, dtype=complex)

        self.overvoltage = zeros(n, dtype=complex)

        self.undervoltage = zeros(n, dtype=complex)

        self.Sbranch = zeros(m, dtype=complex)

        self.Ibranch = zeros(m, dtype=complex)

        self.loading = zeros(m, dtype=complex)

        self.losses = zeros(m, dtype=complex)

        self.overloads = zeros(m, dtype=complex)

        self.error = list()

        self.converged = list()

        self.buses_useful_for_storage = list()

        self.plot_bars_limit = 100

        self.inner_iterations = list()

        self.outer_iterations = list()

        self.elapsed = list()

        self.methods = list()

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

        # self.overvoltage[b_idx] = results.overvoltage

        # self.undervoltage[b_idx] = results.undervoltage

        self.Sbranch[br_idx] = results.Sbranch

        self.Ibranch[br_idx] = results.Ibranch

        self.loading[br_idx] = results.loading

        self.losses[br_idx] = results.losses

        # self.overloads[br_idx] = results.overloads

        # if results.error > self.error:
        self.error.append(results.error)

        self.converged.append(results.converged)

        self.inner_iterations.append(results.inner_iterations)

        self.outer_iterations.append(results.outer_iterations)

        self.elapsed.append(results.elapsed)

        self.methods.append(results.methods)

        # self.converged = self.converged and results.converged

        # if results.buses_useful_for_storage is not None:
        #     self.buses_useful_for_storage = b_idx[results.buses_useful_for_storage]

    def check_limits(self, inputs: PowerFlowInput, wo=1, wv1=1, wv2=1):
        """
        Check the grid violations
        @param inputs: PowerFlowInput object
        @return: summation of the deviations
        """
        # branches: Returns the loading rate when greater than 1 (nominal), zero otherwise
        br_idx = where(self.loading > 1)[0]
        bb_f = inputs.F[br_idx]
        bb_t = inputs.T[br_idx]
        self.overloads = self.loading[br_idx]

        # Over and under voltage values in the indices where it occurs
        vo_idx = where(self.voltage > inputs.Vmax)[0]
        self.overvoltage = (self.voltage - inputs.Vmax)[vo_idx]
        vu_idx = where(self.voltage < inputs.Vmin)[0]
        self.undervoltage = (inputs.Vmin - self.voltage)[vu_idx]

        self.overloads_idx = br_idx

        self.overvoltage_idx = vo_idx

        self.undervoltage_idx = vu_idx

        self.buses_useful_for_storage = list(set(r_[vo_idx, vu_idx, bb_f, bb_t]))

        return abs(wo * sum(self.overloads) + wv1 * sum(self.overvoltage) + wv2 * sum(self.undervoltage))

    def get_convergence_report(self):

        res = 'converged' + str(self.converged)

        res += '\n\tinner_iterations: ' + str(self.inner_iterations)

        res += '\n\touter_iterations: ' + str(self.outer_iterations)

        res += '\n\terror: ' + str(self.error)

        res += '\n\telapsed: ' + str(self.elapsed)

        res += '\n\tmethods: ' + str(self.methods)

        return res

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

        if indices is None and names is not None:
            indices = array(range(len(names)))

        if len(indices) > 0:
            labels = names[indices]
            y_label = ''
            title = ''
            if result_type == 'Bus voltage':
                y = self.voltage[indices]
                y_label = '(p.u.)'
                title = 'Bus voltage '

            elif result_type == 'Branch power':
                y = self.Sbranch[indices]
                y_label = '(MVA)'
                title = 'Branch power '

            elif result_type == 'Branch current':
                y = self.Ibranch[indices]
                y_label = '(p.u.)'
                title = 'Branch current '

            elif result_type == 'Branch_loading':
                y = self.loading[indices] * 100
                y_label = '(%)'
                title = 'Branch loading '

            elif result_type == 'Branch losses':
                y = self.losses[indices]
                y_label = '(MVA)'
                title = 'Branch losses '

            else:
                pass

            df = pd.DataFrame(data=y, index=labels, columns=[result_type])
            if len(df.columns) < self.plot_bars_limit:
                df.abs().plot(ax=ax, kind='bar')
            else:
                df.abs().plot(ax=ax, legend=False, linewidth=LINEWIDTH)
            ax.set_ylabel(y_label)
            ax.set_title(title)

            return df

        else:
            return None

    def export_all(self):
        """
        Exports all the results to DataFrames
        :return: Bus results, Branch reuslts
        """

        # buses results
        vm = np.abs(self.voltage)
        va = np.angle(self.voltage)
        vr = self.voltage.real
        vi = self.voltage.imag
        bus_data = c_[vr, vi, vm, va]
        bus_cols = ['Real voltage (p.u.)', 'Imag Voltage (p.u.)', 'Voltage module (p.u.)', 'Voltage angle (rad)']
        df_bus = pd.DataFrame(data=bus_data, columns=bus_cols)

        # branch results
        sr = self.Sbranch.real
        si = self.Sbranch.imag
        sm = np.abs(self.Sbranch)
        ld = np.abs(self.loading)
        ls = np.abs(self.losses)

        branch_data = c_[sr, si, sm, ld, ls]
        branch_cols = ['Real power (MW)', 'Imag power (MVAr)', 'Power module (MVA)', 'Loading(%)', 'Losses (MVA)']
        df_branch = pd.DataFrame(data=branch_data, columns=branch_cols)

        return df_bus, df_branch


class PowerFlowMP:
    """
    Power flow without QT to use with multi processing
    """
    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions):
        """
        PowerFlow class constructor
        @param grid: MultiCircuit Object
        """

        # Grid to run a power flow in
        self.grid = grid

        # Options to use
        self.options = options

        self.results = None

        self.last_V = None

        self.__cancel__ = False

    @staticmethod
    def compile_types(Sbus, types=None):
        """
        Compile the types
        @return:
        """

        pq = where(types == NodeType.PQ.value[0])[0]
        pv = where(types == NodeType.PV.value[0])[0]
        ref = where(types == NodeType.REF.value[0])[0]
        sto = where(types == NodeType.STO_DISPATCH.value)[0]

        if len(ref) == 0:  # there is no slack!

            if len(pv) == 0:  # there are no pv neither -> blackout grid

                warn('There are no slack nodes selected')

            else:  # select the first PV generator as the slack

                mx = max(Sbus[pv])
                if mx > 0:
                    # find the generator that is injecting the most
                    i = where(Sbus == mx)[0][0]

                else:
                    # all the generators are injecting zero, pick the first pv
                    i = pv[0]

                # delete the selected pv bus from the pv list and put it in the slack list
                pv = delete(pv, where(pv == i)[0])
                ref = [i]
                # print('Setting bus', i, 'as slack')

            ref = ndarray.flatten(array(ref))
            types[ref] = NodeType.REF.value[0]
        else:
            pass  # no problem :)

        pqpv = r_[pq, pv]
        pqpv.sort()

        return ref, pq, pv, pqpv

    def single_power_flow(self, circuit: Circuit, solver_type: SolverType, voltage_solution, Sbus, Ibus):
        """
        Run a power flow simulation for a single circuit
        @param circuit:
        @param solver_type
        @param voltage_solution
        @return:
        """

        original_types = circuit.power_flow_input.types.copy()
        ref, pq, pv, pqpv = self.compile_types(Sbus, original_types)

        any_control_issue = True  # guilty assumption...

        control_max_iter = 10

        inner_it = list()
        outer_it = 0
        elapsed = list()
        methods = list()
        converged_lst = list()
        errors = list()
        it = list()
        el = list()

        while any_control_issue and outer_it < control_max_iter:

            if len(circuit.power_flow_input.ref) == 0:
                voltage_solution = zeros(len(Sbus), dtype=complex)
                normF = 0
                Scalc = Sbus.copy()
                any_control_issue = False
                converged = True
                warn('Not solving power flow because there is no slack bus')
            else:
                # type HELM
                if solver_type == SolverType.HELM:
                    methods.append(SolverType.HELM)
                    voltage_solution, converged, normF, Scalc, it, el = helm(Vbus=voltage_solution,
                                                                             Sbus=Sbus,
                                                                             Ybus=circuit.power_flow_input.Ybus,
                                                                             pq=pq,
                                                                             pv=pv,
                                                                             ref=ref,
                                                                             pqpv=pqpv,
                                                                             tol=self.options.tolerance,
                                                                             max_coefficient_count=self.options.max_iter)

                # type DC
                elif solver_type == SolverType.DC:
                    methods.append(SolverType.DC)
                    voltage_solution, converged, normF, Scalc, it, el = dcpf(Ybus=circuit.power_flow_input.Ybus,
                                                                             Sbus=Sbus,
                                                                             Ibus=Ibus,
                                                                             V0=voltage_solution,
                                                                             ref=ref,
                                                                             pvpq=pqpv,
                                                                             pq=pq,
                                                                             pv=pv)

                elif solver_type == SolverType.LACPF:
                    methods.append(SolverType.LACPF)

                    voltage_solution, converged, normF, Scalc, it, el = lacpf(Y=circuit.power_flow_input.Ybus,
                                                                              Ys=circuit.power_flow_input.Yseries,
                                                                              S=Sbus,
                                                                              I=Ibus,
                                                                              Vset=voltage_solution,
                                                                              pq=pq,
                                                                              pv=pv)

                # Levenberg-Marquardt
                elif solver_type == SolverType.LM:
                    methods.append(SolverType.LM)
                    voltage_solution, converged, normF, Scalc, it, el = LevenbergMarquardtPF(
                        Ybus=circuit.power_flow_input.Ybus,
                        Sbus=Sbus,
                        V0=voltage_solution,
                        Ibus=Ibus,
                        pv=pv,
                        pq=pq,
                        tol=self.options.tolerance,
                        max_it=self.options.max_iter)

                # Fast decoupled
                elif solver_type == SolverType.FASTDECOUPLED:
                    methods.append(SolverType.FASTDECOUPLED)
                    voltage_solution, converged, normF, Scalc, it, el = FDPF(Vbus=voltage_solution,
                                                                             Sbus=Sbus,
                                                                             Ibus=Ibus,
                                                                             Ybus=circuit.power_flow_input.Ybus,
                                                                             B1=circuit.power_flow_input.B1,
                                                                             B2=circuit.power_flow_input.B2,
                                                                             pq=pq,
                                                                             pv=pv,
                                                                             pqpv=pqpv,
                                                                             tol=self.options.tolerance,
                                                                             max_it=self.options.max_iter)

                # Newton-Raphson
                elif solver_type == SolverType.NR:
                    methods.append(SolverType.NR)

                    # presolve linear system
                    voltage_solution, converged, normF, Scalc, it, el = lacpf(Y=circuit.power_flow_input.Ybus,
                                                                              Ys=circuit.power_flow_input.Yseries,
                                                                              S=Sbus,
                                                                              I=Ibus,
                                                                              Vset=voltage_solution,
                                                                              pq=pq,
                                                                              pv=pv)
                    # Solve NR with the linear AC solution
                    voltage_solution, converged, normF, Scalc, it, el = IwamotoNR(Ybus=circuit.power_flow_input.Ybus,
                                                                                  Sbus=Sbus,
                                                                                  V0=voltage_solution,
                                                                                  Ibus=Ibus,
                                                                                  pv=pv,
                                                                                  pq=pq,
                                                                                  tol=self.options.tolerance,
                                                                                  max_it=self.options.max_iter,
                                                                                  robust=False)

                # Newton-Raphson-Iwamoto
                elif solver_type == SolverType.IWAMOTO:
                    methods.append(SolverType.IWAMOTO)
                    voltage_solution, converged, normF, Scalc, it, el = IwamotoNR(Ybus=circuit.power_flow_input.Ybus,
                                                                                  Sbus=Sbus,
                                                                                  V0=voltage_solution,
                                                                                  Ibus=Ibus,
                                                                                  pv=pv,
                                                                                  pq=pq,
                                                                                  tol=self.options.tolerance,
                                                                                  max_it=self.options.max_iter,
                                                                                  robust=True)

                # for any other method, for now, do a LM
                else:
                    methods.append(SolverType.LM)
                    voltage_solution, converged, \
                    normF, Scalc, it, el = LevenbergMarquardtPF(Ybus=circuit.power_flow_input.Ybus,
                                                                Sbus=Sbus,
                                                                V0=voltage_solution,
                                                                Ibus=Ibus,
                                                                pv=pv,
                                                                pq=pq,
                                                                tol=self.options.tolerance,
                                                                max_it=self.options.max_iter)

                if converged:
                    # Check controls
                    if self.options.control_Q:
                        voltage_solution, \
                        Qnew, \
                        types_new, \
                        any_control_issue = self.switch_logic(V=voltage_solution,
                                                              Vset=abs(voltage_solution),
                                                              Q=Scalc.imag,
                                                              Qmax=circuit.power_flow_input.Qmax,
                                                              Qmin=circuit.power_flow_input.Qmin,
                                                              types=circuit.power_flow_input.types,
                                                              original_types=original_types,
                                                              verbose=self.options.verbose)
                        if any_control_issue:
                            # voltage_solution = Vnew
                            Sbus = Sbus.real + 1j * Qnew
                            ref, pq, pv, pqpv = self.compile_types(Sbus, types_new)
                        else:
                            if self.options.verbose:
                                print('Controls Ok')

                    else:
                        # did not check Q limits
                        any_control_issue = False
                else:
                    any_control_issue = False

            # increment the inner iterations counter
            inner_it.append(it)

            # increment the outer control iterations counter
            outer_it += 1

            # add the time taken by the solver in this iteration
            elapsed.append(el)

            # append loop error
            errors.append(normF)

            # append converged
            converged_lst.append(bool(converged))

        # revert the types to the original
        # ref, pq, pv, pqpv = self.compile_types(original_types)

        # Compute the branches power and the slack buses power
        Sbranch, Ibranch, loading, losses, Sbus = self.power_flow_post_process(circuit=circuit, V=voltage_solution)

        # voltage, Sbranch, loading, losses, error, converged, Qpv
        results = PowerFlowResults(Sbus=Sbus,
                                   voltage=voltage_solution,
                                   Sbranch=Sbranch,
                                   Ibranch=Ibranch,
                                   loading=loading,
                                   losses=losses,
                                   error=errors,
                                   converged=converged_lst,
                                   Qpv=None,
                                   inner_it=inner_it,
                                   outer_it=outer_it,
                                   elapsed=elapsed,
                                   methods=methods)

        return results

    @staticmethod
    def power_flow_post_process(circuit: Circuit, V, only_power=False):
        """
        Compute the power flows trough the branches
        @param circuit: instance of Circuit
        @param V: Voltage solution array for the circuit buses
        @param only_power: compute only the power injection
        @return: Sbranch (MVA), Ibranch (p.u.), loading (p.u.), losses (MVA), Sbus(MVA)
        """
        # Compute the slack and pv buses power
        Sbus = circuit.power_flow_input.Sbus

        vd = circuit.power_flow_input.ref
        pv = circuit.power_flow_input.pv

        # power at the slack nodes
        Sbus[vd] = V[vd] * conj(circuit.power_flow_input.Ybus[vd, :][:, :].dot(V))

        # Reactive power at the pv nodes
        P = Sbus[pv].real
        Q = (V[pv] * conj(circuit.power_flow_input.Ybus[pv, :][:, :].dot(V))).imag
        Sbus[pv] = P + 1j * Q  # keep the original P injection and set the calculated reactive power

        if not only_power:
            # Branches current, loading, etc
            If = circuit.power_flow_input.Yf * V
            It = circuit.power_flow_input.Yt * V
            Sf = V[circuit.power_flow_input.F] * conj(If)
            St = V[circuit.power_flow_input.T] * conj(It)

            # Branch losses in MVA
            losses = (Sf + St) * circuit.Sbase

            # Branch current in p.u.
            Ibranch = maximum(If, It)

            # Branch power in MVA
            Sbranch = maximum(Sf, St) * circuit.Sbase

            # Branch loading in p.u.
            loading = Sbranch / (circuit.power_flow_input.branch_rates + 1e-9)

            return Sbranch, Ibranch, loading, losses, Sbus

        else:
            no_val = zeros(len(circuit.branches), dtype=complex)
            return no_val, no_val, no_val, no_val, Sbus

    @staticmethod
    def switch_logic(V, Vset, Q, Qmax, Qmin, types, original_types, verbose):
        """
        Change the buses type in order to control the generators reactive power
        @param pq: array of pq indices
        @param pv: array of pq indices
        @param ref: array of pq indices
        @param V: array of voltages (all buses)
        @param Vset: Array of set points (all buses)
        @param Q: Array of reactive power (all buses)
        @param types: Array of types (all buses)
        @param original_types: Types as originally intended (all buses)
        @param verbose: output messages via the console
        @return:
            Vnew: New voltage values
            Qnew: New reactive power values
            types_new: Modified types array
            any_control_issue: Was there any control issue?
        """

        '''
        ON PV-PQ BUS TYPE SWITCHING LOGIC IN POWER FLOW COMPUTATION
        Jinquan Zhao

        1) Bus i is a PQ bus in the previous iteration and its
        reactive power was fixed at its lower limit:

        If its voltage magnitude Vi ≥ Viset, then

            it is still a PQ bus at current iteration and set Qi = Qimin .

            If Vi < Viset , then

                compare Qi with the upper and lower limits.

                If Qi ≥ Qimax , then
                    it is still a PQ bus but set Qi = Qimax .
                If Qi ≤ Qimin , then
                    it is still a PQ bus and set Qi = Qimin .
                If Qimin < Qi < Qi max , then
                    it is switched to PV bus, set Vinew = Viset.

        2) Bus i is a PQ bus in the previous iteration and
        its reactive power was fixed at its upper limit:

        If its voltage magnitude Vi ≤ Viset , then:
            bus i still a PQ bus and set Q i = Q i max.

            If Vi > Viset , then

                Compare between Qi and its upper/lower limits

                If Qi ≥ Qimax , then
                    it is still a PQ bus and set Q i = Qimax .
                If Qi ≤ Qimin , then
                    it is still a PQ bus but let Qi = Qimin in current iteration.
                If Qimin < Qi < Qimax , then
                    it is switched to PV bus and set Vinew = Viset

        3) Bus i is a PV bus in the previous iteration.

        Compare Q i with its upper and lower limits.

        If Qi ≥ Qimax , then
            it is switched to PQ and set Qi = Qimax .
        If Qi ≤ Qimin , then
            it is switched to PQ and set Qi = Qimin .
        If Qi min < Qi < Qimax , then
            it is still a PV bus.
        '''
        if verbose:
            print('Control logic')

        n = len(V)
        Vm = abs(V)
        Qnew = Q.copy()
        Vnew = V.copy()
        types_new = types.copy()
        any_control_issue = False
        for i in range(n):

            if types[i] == NodeType.REF.value[0]:
                pass

            elif types[i] == NodeType.PQ.value[0] and original_types[i] == NodeType.PV.value[0]:

                if Vm[i] != Vset[i]:

                    if Q[i] >= Qmax[i]:  # it is still a PQ bus but set Qi = Qimax .
                        Qnew[i] = Qmax[i]

                    elif Q[i] <= Qmin[i]:  # it is still a PQ bus and set Qi = Qimin .
                        Qnew[i] = Qmin[i]

                    else:  # switch back to PV, set Vinew = Viset.
                        if verbose:
                            print('Bus', i, ' switched back to PV')
                        types_new[i] = NodeType.PV.value[0]
                        Vnew[i] = complex(Vset[i], 0)

                    any_control_issue = True

                else:
                    pass  # The voltages are equal

            elif types[i] == NodeType.PV.value[0]:

                if Q[i] >= Qmax[i]:  # it is switched to PQ and set Qi = Qimax .
                    if verbose:
                        print('Bus', i, ' switched to PQ: Q', Q[i], ' Qmax:', Qmax[i])
                    types_new[i] = NodeType.PQ.value[0]
                    Qnew[i] = Qmax[i]
                    any_control_issue = True

                elif Q[i] <= Qmin[i]:  # it is switched to PQ and set Qi = Qimin .
                    if verbose:
                        print('Bus', i, ' switched to PQ: Q', Q[i], ' Qmin:', Qmin[i])
                    types_new[i] = NodeType.PQ.value[0]
                    Qnew[i] = Qmin[i]
                    any_control_issue = True

                else:  # it is still a PV bus.
                    pass

            else:
                pass

        return Vnew, Qnew, types_new, any_control_issue

    def run(self, store_in_island=False):
        """
        Pack run_pf for the QThread
        :return:
        """
        # print('PowerFlow at ', self.grid.name)
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        results = PowerFlowResults()
        results.initialize(n, m)
        # self.progress_signal.emit(0.0)
        Sbase = self.grid.Sbase

        for circuit in self.grid.circuits:
            Vbus = circuit.power_flow_input.Vbus
            Sbus = circuit.power_flow_input.Sbus
            Ibus = circuit.power_flow_input.Ibus

            # run circuit power flow
            res = self.run_pf(circuit, Vbus, Sbus, Ibus)

            circuit.power_flow_results = res

            # merge the results from this island
            results.apply_from_island(res,
                                      circuit.bus_original_idx,
                                      circuit.branch_original_idx)

        self.last_V = results.voltage  # done inside single_power_flow

        # check the limits
        # sum_dev = results.check_limits(self.grid.power_flow_input)

        self.results = results

        return results

    def run_pf(self, circuit: Circuit, Vbus, Sbus, Ibus):
        """
        Run a power flow for a circuit
        @return:
        """

        # Run the power flow
        results = self.single_power_flow(circuit=circuit,
                                         solver_type=self.options.solver_type,
                                         voltage_solution=Vbus,
                                         Sbus=Sbus,
                                         Ibus=Ibus)

        # Retry with another solver
        if not np.all(results.converged) and self.options.auxiliary_solver_type is not None:
            # print('Retying power flow with' + str(self.options.auxiliary_solver_type))
            # compose a voltage array that makes sense
            # if np.isnan(circuit.power_flow_results.voltage).any():
            #     print('Corrupt voltage, using flat solution in retry')
            #     voltage = ones(len(circuit.buses), dtype=complex)
            # else:
            #     voltage = circuit.power_flow_results.voltage

            voltage = ones(len(circuit.buses), dtype=complex)

            # re-run power flow
            results = self.single_power_flow(circuit=circuit,
                                             solver_type=self.options.auxiliary_solver_type,
                                             voltage_solution=voltage,
                                             Sbus=Sbus,
                                             Ibus=Ibus)

            if not np.all(results.converged):
                print('Did not converge, even after retry!, Error:', results.error)
        else:
            pass

        # check the power flow limits
        results.check_limits(circuit.power_flow_input)

        return results

    def cancel(self):
        self.__cancel__ = True


def power_flow_worker(t, options: PowerFlowOptions, circuit: Circuit, Vbus, Sbus, Ibus, return_dict):
    """
    Power flow worker to schedule parallel power flows
    :param t: execution index
    :param options: power flow options
    :param circuit: circuit
    :param Vbus: Voltages to initialize
    :param Sbus: Power injections
    :param Ibus: Current injections
    :param return_dict: parallel module dictionary in wich to return the values
    :return:
    """

    instance = PowerFlowMP(None, options)
    return_dict[t] = instance.run_pf(circuit, Vbus, Sbus, Ibus)


def power_flow_worker_args(args):
    """
    Power flow worker to schedule parallel power flows

    args -> t, options: PowerFlowOptions, circuit: Circuit, Vbus, Sbus, Ibus, return_dict


    :param t: execution index
    :param options: power flow options
    :param circuit: circuit
    :param Vbus: Voltages to initialize
    :param Sbus: Power injections
    :param Ibus: Current injections
    :param return_dict: parallel module dictionary in wich to return the values
    :return:
    """
    t, options, circuit, Vbus, Sbus, Ibus, return_dict = args
    instance = PowerFlowMP(None, options)
    return_dict[t] = instance.run_pf(circuit, Vbus, Sbus, Ibus)


class PowerFlow(QRunnable):
    """
    Power flow wrapper to use with Qt
    """

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions):
        """
        PowerFlow class constructor
        @param grid: MultiCircuit Object
        """
        QRunnable.__init__(self)

        # Grid to run a power flow in
        self.grid = grid

        # Options to use
        self.options = options

        self.results = None

        self.pf = PowerFlowMP(grid, options)

        self.__cancel__ = False

    def run(self):
        """
        Pack run_pf for the QThread
        :return: 
        """

        results = self.pf.run(store_in_island=True)
        self.results = results
        self.grid.power_flow_results = results

    def run_pf(self, circuit: Circuit, Vbus, Sbus, Ibus):
        """
        Run a power flow for every circuit
        @return:
        """

        return self.pf.run_pf(circuit, Vbus, Sbus, Ibus)

    def cancel(self):
        self.__cancel__ = True


########################################################################################################################
# Short circuit classes
########################################################################################################################


class ShortCircuitOptions:

    def __init__(self, bus_index, verbose=False):
        """

        Args:
            bus_index: indices of the short circuited buses
            zf: fault impedance
        """
        self.bus_index = bus_index

        self.verbose = verbose


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

        self.short_circuit_power = SCpower

        self.available_results = ['Bus voltage', 'Branch power', 'Branch current', 'Branch_loading', 'Branch losses',
                                  'Bus short circuit power']

    def copy(self):
        """
        Return a copy of this
        @return:
        """
        return ShortCircuitResults(Sbus=self.Sbus, voltage=self.voltage, Sbranch=self.Sbranch,
                                   Ibranch=self.Ibranch, loading=self.loading,
                                   losses=self.losses, SCpower=self.short_circuit_power, error=self.error,
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

        self.short_circuit_power = zeros(n, dtype=complex)

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

        self.short_circuit_power[b_idx] = results.short_circuit_power

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
                y = self.short_circuit_power[indices]
                ylabel = '(MVA)'
                title = 'Bus short circuit power'
            else:
                pass

            df = pd.DataFrame(data=y, index=labels, columns=[result_type])
            df.abs().plot(ax=ax, kind='bar', linewidth=LINEWIDTH)
            ax.set_ylabel(ylabel)
            ax.set_title(title)

            return df

        else:
            return None


class ShortCircuit(QRunnable):
    # progress_signal = pyqtSignal(float)
    # progress_text = pyqtSignal(str)
    # done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: ShortCircuitOptions, pf_results: PowerFlowResults):
        """
        PowerFlow class constructor
        @param grid: MultiCircuit Object
        """
        QRunnable.__init__(self)

        # Grid to run a power flow in
        self.grid = grid

        # power flow results
        self.pf_results = pf_results

        # Options to use
        self.options = options

        # compile the buses short circuit impedance array
        n = len(self.grid.buses)
        self.Zf = zeros(n, dtype=complex)
        for i in range(n):
            self.Zf[i] = self.grid.buses[i].Zf

        self.results = None

        self.__cancel__ = False

    def single_short_circuit(self, circuit: Circuit, Vpf):
        """
        Run a power flow simulation for a single circuit
        @param circuit:
        @param Vpf: Power flow voltage
        @return: short circuit results
        """
        # compute Zbus if needed
        if circuit.power_flow_input.Zbus is None:
            # is dense, so no need to store it as sparse
            circuit.power_flow_input.Zbus = inv(circuit.power_flow_input.Ybus).toarray()

        # Compute the short circuit
        V, SCpower = short_circuit_3p(bus_idx=self.options.bus_index,
                                      Zbus=circuit.power_flow_input.Zbus,
                                      Vbus=Vpf,
                                      Zf=self.Zf, baseMVA=circuit.Sbase)

        # Compute the branches power
        Sbranch, Ibranch, loading, losses = self.compute_branch_results(circuit=circuit, V=V)

        # voltage, Sbranch, loading, losses, error, converged, Qpv
        results = ShortCircuitResults(Sbus=circuit.power_flow_input.Sbus,
                                      voltage=V,
                                      Sbranch=Sbranch,
                                      Ibranch=Ibranch,
                                      loading=loading,
                                      losses=losses,
                                      SCpower=SCpower,
                                      error=0,
                                      converged=True,
                                      Qpv=None)

        return results

    @staticmethod
    def compute_branch_results(circuit: Circuit, V):
        """
        Compute the power flows trough the branches
        @param circuit: instance of Circuit
        @param V: Voltage solution array for the circuit buses
        @return: Sbranch, Ibranch, loading, losses
        """
        If = circuit.power_flow_input.Yf * V
        It = circuit.power_flow_input.Yt * V
        Sf = V[circuit.power_flow_input.F] * conj(If)
        St = V[circuit.power_flow_input.T] * conj(It)
        losses = Sf - St
        Ibranch = maximum(If, It)
        Sbranch = maximum(Sf, St)
        loading = Sbranch * circuit.Sbase / circuit.power_flow_input.branch_rates

        # idx = where(abs(loading) == inf)[0]
        # loading[idx] = 9999

        return Sbranch, Ibranch, loading, losses

    def run(self):
        """
        Run a power flow for every circuit
        @return:
        """
        # print('Short circuit at ', self.grid.name)
        # self.progress_signal.emit(0.0)

        n = len(self.grid.buses)
        m = len(self.grid.branches)
        results = ShortCircuitResults()  # yes, reuse this class
        results.initialize(n, m)
        k = 0
        for circuit in self.grid.circuits:
            if self.options.verbose:
                print('Solving ' + circuit.name)

            circuit.short_circuit_results = self.single_short_circuit(circuit=circuit,
                                                                      Vpf=self.pf_results.voltage[circuit.bus_original_idx])
            results.apply_from_island(circuit.short_circuit_results,
                                      circuit.bus_original_idx,
                                      circuit.branch_original_idx)

            # self.progress_signal.emit((k+1) / len(self.grid.circuits))
            k += 1

        self.results = results
        self.grid.short_circuit_results = results

    def cancel(self):
        self.__cancel__ = True


########################################################################################################################
# Time series classes
########################################################################################################################


class TimeSeriesInput:

    def __init__(self, s_profile: pd.DataFrame = None, i_profile: pd.DataFrame = None, y_profile: pd.DataFrame = None):
        """
        Time series input
        @param s_profile: DataFrame with the profile of the injected power at the buses
        @param i_profile: DataFrame with the profile of the injected current at the buses
        @param y_profile: DataFrame with the profile of the shunt admittance at the buses
        """

        # master time array. All the profiles must match its length
        self.time_array = None

        self.Sprof = s_profile
        self.Iprof = i_profile
        self.Yprof = y_profile

        # Array of load admittances (shunt)
        self.Y = None

        # Array of load currents
        self.I = None

        # Array of aggregated bus power (loads, generators, storage, etc...)
        self.S = None

        # is this timeSeriesInput valid? typically it is valid after compiling it
        self.valid = False

    def compile(self):
        """
        Generate time-consistent arrays
        @return:
        """
        cols = list()
        self.valid = False
        merged = None
        for p in [self.Sprof, self.Iprof, self.Yprof]:
            if p is None:
                cols.append(None)
            else:
                if merged is None:
                    merged = p
                else:
                    merged = pd.concat([merged, p], axis=1)
                cols.append(p.columns)
                self.valid = True

        # by merging there could have been time inconsistencies that would produce NaN
        # to solve it we "interpolate" by replacing the NaN by the nearest value
        if merged is not None:
            merged.interpolate(method='nearest', axis=0, inplace=True)

            t, n = merged.shape

            # pick the merged series time
            self.time_array = merged.index.values

            # Array of aggregated bus power (loads, generators, storage, etc...)
            if cols[0] is not None:
                self.S = merged[cols[0]].values
            else:
                self.S = zeros((t, n), dtype=complex)

            # Array of load currents
            if cols[1] is not None:
                self.I = merged[cols[1]].values
            else:
                self.I = zeros((t, n), dtype=complex)

            # Array of load admittances (shunt)
            if cols[2] is not None:
                self.Y = merged[cols[2]].values
            else:
                self.Y = zeros((t, n), dtype=complex)

    def get_at(self, t):
        """
        Returns the necessary values
        @param t: time index
        @return:
        """
        return self.Y[t, :], self.I[t, :], self.S[t, :]

    def get_from_buses(self, bus_idx):
        """

        @param bus_idx:
        @return:
        """
        ts = TimeSeriesInput()
        ts.S = self.S[:, bus_idx]
        ts.I = self.I[:, bus_idx]
        ts.Y = self.Y[:, bus_idx]
        ts.valid = True
        return ts

    def apply_from_island(self, res, bus_original_idx, branch_original_idx, nbus_full, nbranch_full):
        """

        :param res: TimeSeriesInput
        :param bus_original_idx:
        :param branch_original_idx:
        :param nbus_full:
        :param nbranch_full:
        :return:
        """

        if res is not None:
            if self.Sprof is None:
                self.time_array = res.time_array
                # t = len(self.time_array)
                self.Sprof = pd.DataFrame()  # zeros((t, nbus_full), dtype=complex)
                self.Iprof = pd.DataFrame()  # zeros((t, nbranch_full), dtype=complex)
                self.Yprof = pd.DataFrame()  # zeros((t, nbus_full), dtype=complex)

            self.Sprof[res.Sprof.columns.values] = res.Sprof
            self.Iprof[res.Iprof.columns.values] = res.Iprof
            self.Yprof[res.Yprof.columns.values] = res.Yprof

    def copy(self):

        cpy = TimeSeriesInput()

        # master time array. All the profiles must match its length
        cpy.time_array = self.time_array

        cpy.Sprof = self.Sprof.copy()
        cpy.Iprof = self.Iprof.copy()
        cpy.Yprof = self.Yprof.copy()

        # Array of load admittances (shunt)
        cpy.Y = self.Y.copy()

        # Array of load currents
        cpy.I = self.I.copy()

        # Array of aggregated bus power (loads, generators, storage, etc...)
        cpy.S = self.S.copy()

        # is this timeSeriesInput valid? typically it is valid after compiling it
        cpy.valid = self.valid

        return cpy


class TimeSeriesResults(PowerFlowResults):

    def __init__(self, n, m, nt, start, end, time=None):
        """
        TimeSeriesResults constructor
        @param n: number of buses
        @param m: number of branches
        @param nt: number of time steps
        """
        PowerFlowResults.__init__(self)

        self.nt = nt
        self.m = m
        self.n = n
        self.start = start
        self.end = end

        self.time = time

        if nt > 0:
            self.voltage = zeros((nt, n), dtype=complex)

            self.Sbranch = zeros((nt, m), dtype=complex)

            self.Ibranch = zeros((nt, m), dtype=complex)

            self.loading = zeros((nt, m), dtype=complex)

            self.losses = zeros((nt, m), dtype=complex)

            self.error = zeros(nt)

            self.converged = ones(nt, dtype=bool)  # guilty assumption

            # self.Qpv = Qpv

            self.overloads = [None] * nt

            self.overvoltage = [None] * nt

            self.undervoltage = [None] * nt

            self.overloads_idx = [None] * nt

            self.overvoltage_idx = [None] * nt

            self.undervoltage_idx = [None] * nt

            self.buses_useful_for_storage = [None] * nt

        else:
            self.voltage = None

            self.Sbranch = None

            self.Ibranch = None

            self.loading = None

            self.losses = None

            self.error = None

            self.converged = None

            # self.Qpv = Qpv

            self.overloads = None

            self.overvoltage = None

            self.undervoltage = None

            self.overloads_idx = None

            self.overvoltage_idx = None

            self.undervoltage_idx = None

            self.buses_useful_for_storage = None

            self.available_results = ['Bus voltage', 'Branch power', 'Branch current', 'Branch_loading',
                                      'Branch losses']

    def set_at(self, t, results: PowerFlowResults):
        """
        Set the results at the step t
        @param t:
        @param results:
        @return:
        """

        self.voltage[t, :] = results.voltage

        self.Sbranch[t, :] = results.Sbranch

        self.Ibranch[t, :] = results.Ibranch

        self.loading[t, :] = results.loading

        self.losses[t, :] = results.losses

        self.error[t] = max(results.error)

        self.converged[t] = min(results.converged)

        # self.Qpv = Qpv

        self.overloads[t] = results.overloads

        self.overvoltage[t] = results.overvoltage

        self.undervoltage[t] = results.undervoltage

        self.overloads_idx[t] = results.overloads_idx

        self.overvoltage_idx[t] = results.overvoltage_idx

        self.undervoltage_idx[t] = results.undervoltage_idx

        self.buses_useful_for_storage[t] = results.buses_useful_for_storage

    @staticmethod
    def merge_if(df, arr, ind, cols):
        """

        @param df:
        @param arr:
        @param ind:
        @param cols:
        @return:
        """
        obj = pd.DataFrame(data=arr, index=ind, columns=cols)
        if df is None:
            df = obj
        else:
            df = pd.concat([df, obj], axis=1)

        return df

    def apply_from_island(self, results, b_idx, br_idx, index, grid_idx):
        """
        Apply results from another island circuit to the circuit results represented here
        @param results: PowerFlowResults
        @param b_idx: bus original indices
        @param br_idx: branch original indices
        @return:
        """

        self.voltage[:, b_idx] = results.voltage

        self.Sbranch[:, br_idx] = results.Sbranch

        self.Ibranch[:, br_idx] = results.Ibranch

        self.loading[:, br_idx] = results.loading

        self.losses[:, br_idx] = results.losses

        if (results.error > self.error).any():
            self.error = results.error

        self.converged = self.converged * results.converged

        # self.voltage = self.merge_if(self.voltage, results.voltage, index, b_idx)
        #
        # self.Sbranch = self.merge_if(self.Sbranch, results.Sbranch, index, br_idx)
        #
        # self.Ibranch = self.merge_if(self.Ibranch, results.Ibranch, index, br_idx)
        #
        # self.loading = self.merge_if(self.loading, results.loading, index, br_idx)
        #
        # self.losses = self.merge_if(self.losses, results.losses, index, br_idx)
        #
        # self.error = self.merge_if(self.error, results.error, index, [grid_idx])
        #
        # self.converged = self.merge_if(self.converged, results.converged, index, [grid_idx])

        # self.Qpv = Qpv

        # self.overloads = self.merge_if(self.voltage, results.voltage, index, b_idx)
        #
        # self.overvoltage = self.merge_if(self.voltage, results.voltage, index, b_idx)
        #
        # self.undervoltage = self.merge_if(self.voltage, results.voltage, index, b_idx)
        #
        # self.overloads_idx = None
        #
        # self.overvoltage_idx = None
        #
        # self.undervoltage_idx = None
        #
        # self.buses_useful_for_storage = None

    def analyze(self):
        """
        Analyze the results
        @return:
        """
        branch_overload_frequency = zeros(self.m)
        bus_undervoltage_frequency = zeros(self.n)
        bus_overvoltage_frequency = zeros(self.n)
        buses_selected_for_storage_frequency = zeros(self.n)
        for i in range(self.nt):
            branch_overload_frequency[self.overloads_idx[i]] += 1
            bus_undervoltage_frequency[self.undervoltage_idx[i]] += 1
            bus_overvoltage_frequency[self.overvoltage_idx[i]] += 1
            buses_selected_for_storage_frequency[self.buses_useful_for_storage[i]] += 1

        return branch_overload_frequency, bus_undervoltage_frequency, bus_overvoltage_frequency, buses_selected_for_storage_frequency

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

        if indices is None:
            indices = array(range(len(names)))

        if len(indices) > 0:
            labels = names[indices]
            ylabel = ''
            title = ''
            if result_type == 'Bus voltage':
                data = self.voltage[:, indices]
                ylabel = '(p.u.)'
                title = 'Bus voltage '

            elif result_type == 'Branch power':
                data = self.Sbranch[:, indices]
                ylabel = '(MVA)'
                title = 'Branch power '

            elif result_type == 'Branch current':
                data = self.Ibranch[:, indices]
                ylabel = '(kA)'
                title = 'Branch current '

            elif result_type == 'Branch_loading':
                data = self.loading[:, indices] * 100
                ylabel = '(%)'
                title = 'Branch loading '

            elif result_type == 'Branch losses':
                data = self.losses[:, indices]
                ylabel = '(MVA)'
                title = 'Branch losses'

            else:
                pass

            # df.columns = labels
            if self.time is not None:
                df = pd.DataFrame(data=data, columns=labels, index=self.time)
            else:
                df = pd.DataFrame(data=data, columns=labels)

            if len(df.columns) > 10:
                df.abs().plot(ax=ax, linewidth=LINEWIDTH, legend=False)
            else:
                df.abs().plot(ax=ax, linewidth=LINEWIDTH, legend=True)

            ax.set_title(title)
            ax.set_ylabel(ylabel)
            ax.set_xlabel('Time')

            return df

        else:
            return None


class TimeSeriesResultsAnalysis:

    def __init__(self, results: TimeSeriesResults):
        self.res = results

        self.branch_overload_frequency = None
        self.bus_undervoltage_frequency = None
        self.bus_overvoltage_frequency = None

        self.branch_overload_accumulated = None
        self.bus_undervoltage_accumulated = None
        self.bus_overvoltage_accumulated = None

        self.buses_selected_for_storage_frequency = None

        self.__run__()

    def __run__(self):
        self.branch_overload_frequency = zeros(self.res.m)
        self.bus_undervoltage_frequency = zeros(self.res.n)
        self.bus_overvoltage_frequency = zeros(self.res.n)

        self.branch_overload_accumulated = zeros(self.res.m, dtype=complex)
        self.bus_undervoltage_accumulated = zeros(self.res.n, dtype=complex)
        self.bus_overvoltage_accumulated = zeros(self.res.n, dtype=complex)

        self.buses_selected_for_storage_frequency = zeros(self.res.n)

        for i in range(self.res.start, self.res.end):
            self.branch_overload_frequency[self.res.overloads_idx[i]] += 1
            self.bus_undervoltage_frequency[self.res.undervoltage_idx[i]] += 1
            self.bus_overvoltage_frequency[self.res.overvoltage_idx[i]] += 1

            self.branch_overload_accumulated[self.res.overloads_idx[i]] += self.res.overloads[i]
            self.bus_undervoltage_accumulated[self.res.undervoltage_idx[i]] += self.res.undervoltage[i]
            self.bus_overvoltage_accumulated[self.res.overvoltage_idx[i]] += self.res.overvoltage[i]

            self.buses_selected_for_storage_frequency[self.res.buses_useful_for_storage[i]] += 1


class TimeSeries(QThread):
    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, start=0, end=None):
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

        self.start_ = start

        self.end_ = end

        self.__cancel__ = False

    def run_single_thread(self):
        """
        Run single thread time series
        :return:
        """
        # initialize the power flow
        powerflow = PowerFlowMP(self.grid, self.options)

        # initialize the grid time series results
        # we will append the island results with another function
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        nt = len(self.grid.time_profile)
        self.grid.time_series_results = TimeSeriesResults(n, m, nt, self.start_, self.end_, time=self.grid.time_profile)
        if self.end_ is None:
            self.end_ = nt

        # For every circuit, run the time series
        for nc, circuit in enumerate(self.grid.circuits):

            # make a copy of the circuit to allow controls in place
            # circuit = circuit_orig.copy()

            # are we dispatching storage? if so, generate a dictionary of battery -> bus index
            # to be able to set the batteries values into the vector S
            if self.options.dispatch_storage:
                batteries = list()
                batteries_bus_idx = list()
                for k, bus in enumerate(circuit.buses):
                    for batt in bus.batteries:
                        batt.reset()  # reset the calculation values
                        batteries.append(batt)
                        batteries_bus_idx.append(k)

            self.progress_text.emit('Time series at circuit ' + str(nc) + '...')

            # if there are valid profiles...
            if circuit.time_series_input.valid:

                nt = len(circuit.time_series_input.time_array)
                n = len(circuit.buses)
                m = len(circuit.branches)
                results = TimeSeriesResults(n, m, nt, self.start_, self.end_)
                Vlast = circuit.power_flow_input.Vbus

                self.progress_signal.emit(0.0)

                t = self.start_
                dt = 1.0  # default value in case of single-valued profile

                # traverse the profiles time and simulate each time step
                while t < self.end_ and not self.__cancel__:
                    # set the power values
                    # if the storage dispatch option is active, the batteries power was not included
                    # it shall be included now, after processing
                    Y, I, S = circuit.time_series_input.get_at(t)

                    # add the controlled storage power if controlling storage
                    if self.options.dispatch_storage:

                        if t < self.end_-1:
                            # compute the time delta: the time values come in nanoseconds
                            dt = int(circuit.time_series_input.time_array[t+1]
                                     - circuit.time_series_input.time_array[t]) * 1e-9 / 3600

                        for k, batt in enumerate(batteries):

                            P = batt.get_processed_at(t, dt=dt, store_values=True)
                            bus_idx = batteries_bus_idx[k]
                            S[bus_idx] += (P / circuit.Sbase)
                        else:
                            pass

                    # run power flow at the circuit
                    res = powerflow.run_pf(circuit=circuit, Vbus=Vlast, Sbus=S, Ibus=I)

                    # Recycle voltage solution
                    Vlast = res.voltage

                    # store circuit results at the time index 't'
                    results.set_at(t, res)

                    progress = ((t - self.start_ + 1) / (self.end_ - self.start_)) * 100
                    self.progress_signal.emit(progress)
                    self.progress_text.emit('Simulating ' + circuit.name + ' at '
                                            + str(circuit.time_series_input.time_array[t]))
                    t += 1

                # store at circuit level
                circuit.time_series_results = results

                # merge  the circuit's results
                self.grid.time_series_results.apply_from_island(results,
                                                                circuit.bus_original_idx,
                                                                circuit.branch_original_idx,
                                                                circuit.time_series_input.time_array,
                                                                circuit.name)
            else:
                print('There are no profiles')
                self.progress_text.emit('There are no profiles')

        return self.grid.time_series_results

    def run_multi_thread(self):
        """
        Run multi thread time series
        :return:
        """

        # initialize the grid time series results
        # we will append the island results with another function
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        nt = len(self.grid.time_profile)
        self.grid.time_series_results = TimeSeriesResults(n, m, nt, self.start_, self.end_, time=self.grid.time_profile)
        if self.end_ is None:
            self.end_ = nt

        n_cores = multiprocessing.cpu_count()

        # For every circuit, run the time series
        for nc, circuit in enumerate(self.grid.circuits):

            self.progress_text.emit('Time series at circuit ' + str(nc) + ' in parallel using ' + str(n_cores) + ' cores ...')

            if circuit.time_series_input.valid:

                nt = len(circuit.time_series_input.time_array)
                n = len(circuit.buses)
                m = len(circuit.branches)
                results = TimeSeriesResults(n, m, nt, self.start_, self.end_)
                Vlast = circuit.power_flow_input.Vbus

                self.progress_signal.emit(0.0)

                # Start jobs
                manager = multiprocessing.Manager()
                return_dict = manager.dict()

                t = self.start_
                while t < self.end_ and not self.__cancel__:

                    k = 0
                    jobs = list()

                    # launch only n_cores jobs at the time
                    while k < n_cores+2 and (t+k) < nt:
                        # set the power values
                        Y, I, S = circuit.time_series_input.get_at(t)

                        # run power flow at the circuit
                        p = multiprocessing.Process(target=power_flow_worker, args=(t, self.options, circuit, Vlast, S, I, return_dict))
                        jobs.append(p)
                        p.start()
                        k += 1
                        t += 1

                    # wait for all jobs to complete
                    for proc in jobs:
                        proc.join()

                    progress = ((t - self.start_ + 1) / (self.end_ - self.start_)) * 100
                    self.progress_signal.emit(progress)

                # collect results
                self.progress_text.emit('Collecting results...')
                for t in return_dict.keys():
                    # store circuit results at the time index 't'
                    results.set_at(t, return_dict[t])

                # store at circuit level
                circuit.time_series_results = results

                # merge  the circuit's results
                self.grid.time_series_results.apply_from_island(results,
                                                                circuit.bus_original_idx,
                                                                circuit.branch_original_idx,
                                                                circuit.time_series_input.time_array,
                                                                circuit.name)
            else:
                print('There are no profiles')
                self.progress_text.emit('There are no profiles')

        return self.grid.time_series_results

    def run_multi_thread_map(self):
        """
        Run multi thread time series
        :return:
        """

        results_ = list()
        self.completed_processes = 0
        total_processes = 1
        def complete(result):
            results_.append(result)
            self.completed_processes += 1
            # print('Progress:', (self.completed_processes / total_processes) * 100)
            progress = (self.completed_processes / total_processes) * 100
            self.progress_signal.emit(progress)

        # initialize the grid time series results
        # we will append the island results with another function
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        nt = len(self.grid.time_profile)
        self.grid.time_series_results = TimeSeriesResults(n, m, nt, self.start_, self.end_, time=self.grid.time_profile)

        n_cores = multiprocessing.cpu_count()
        total_processes = nt

        pool = multiprocessing.Pool()

        # For every circuit, run the time series
        for nc, circuit in enumerate(self.grid.circuits):

            self.progress_text.emit('Time series at circuit ' + str(nc) + ' in parallel using ' + str(n_cores) + ' cores ...')

            if circuit.time_series_input.valid:

                nt = len(circuit.time_series_input.time_array)
                n = len(circuit.buses)
                m = len(circuit.branches)
                results = TimeSeriesResults(n, m, nt, self.start_, self.end_)
                Vlast = circuit.power_flow_input.Vbus

                self.progress_signal.emit(0.0)

                # Start jobs
                manager = multiprocessing.Manager()
                return_dict = manager.dict()

                t = 0
                while t < nt and not self.__cancel__:

                    # set the power values
                    Y, I, S = circuit.time_series_input.get_at(t)

                    # run power flow at the circuit
                    pool.apply_async(func=power_flow_worker,
                                     args=(t, self.options, circuit, Vlast, S, I, return_dict),
                                     callback=complete)
                    t += 1

                pool.close()
                pool.join()

                # collect results
                self.progress_text.emit('Collecting results...')
                for t in return_dict.keys():
                    # store circuit results at the time index 't'
                    results.set_at(t, return_dict[t])

                # store at circuit level
                circuit.time_series_results = results

                # merge  the circuit's results
                self.grid.time_series_results.apply_from_island(results,
                                                                circuit.bus_original_idx,
                                                                circuit.branch_original_idx,
                                                                circuit.time_series_input.time_array,
                                                                circuit.name)
            else:
                print('There are no profiles')
                self.progress_text.emit('There are no profiles')

        return self.grid.time_series_results

    def run(self):
        """
        Run the time series simulation
        @return:
        """

        if self.options.multi_thread:
            self.results = self.run_multi_thread()
        else:
            self.results = self.run_single_thread()

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True


########################################################################################################################
# Voltage collapse classes
########################################################################################################################


class VoltageCollapseOptions:

    def __init__(self, step=0.01, approximation_order=1, adapt_step=True, step_min=0.0001, step_max=0.2,
                 error_tol=1e-3, tol=1e-6, max_it=20, stop_at='NOSE', verbose=False):
        """
        Voltage collapse options
        @param step: Step length
        @param approximation_order: Order of the approximation: 1, 2, 3, etc...
        @param adapt_step: Use adaptive step length?
        @param step_min: Minimum step length
        @param step_max: Maximum step length
        @param error_tol: Error tolerance
        @param tol: tolerance
        @param max_it: Maximum number of iterations
        @param stop_at: Value of lambda to stop at, it can be specified by a concept namely NOSE to sto at the edge or
        FULL tp draw the full curve
        """

        self.step = step

        self.approximation_order = approximation_order

        self.adapt_step = adapt_step

        self.step_min = step_min

        self.step_max = step_max

        self.error_tol = error_tol

        self.tol = tol

        self.max_it = max_it

        self.stop_at = stop_at

        self.verbose = verbose


class VoltageCollapseInput:

    def __init__(self, Sbase, Vbase, Starget):
        """
        VoltageCollapseInput constructor
        @param Sbase: Initial power array
        @param Vbase: Initial voltage array
        @param Starget: Final power array
        """
        self.Sbase = Sbase

        self.Starget = Starget

        self.Vbase = Vbase


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
                lprev = self.voltages.shape[0]
                if l > lprev:
                    vv = self.voltages.copy()
                    self.voltages = zeros((l, nbus_full), dtype=complex)
                    self.voltages[0:l, :] = vv

                self.voltages[0:l, bus_original_idx] = res.voltages

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
                df.abs().plot(ax=ax, linewidth=LINEWIDTH, legend=False)
            else:
                df.abs().plot(ax=ax, linewidth=LINEWIDTH, legend=True)

            ax.set_title(title)
            ax.set_ylabel(ylabel)
            ax.set_xlabel('Loading from the base situation ($\lambda$)')

            return df


class VoltageCollapse(QThread):
    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: VoltageCollapseOptions, inputs: VoltageCollapseInput):
        """
        VoltageCollapse constructor
        @param grid:
        @param options:
        """
        QThread.__init__(self)

        # MultiCircuit instance
        self.grid = grid

        # voltage stability options
        self.options = options

        self.inputs = inputs

        self.results = list()

        self.__cancel__ = False

    def progress_callback(self, l):
        """
        Send progress report
        :param l: lambda value
        :return: None
        """
        self.progress_text.emit('Running voltage collapse lambda:' + "{0:.2f}".format(l) + '...')

    def run(self):
        """
        run the voltage collapse simulation
        @return:
        """
        print('Running voltage collapse...')
        nbus = len(self.grid.buses)
        self.results = VoltageCollapseResults(nbus=nbus)

        for nc, c in enumerate(self.grid.circuits):

            self.progress_text.emit('Running voltage collapse at circuit ' + str(nc) + '...')

            # Voltage_series, Lambda_series, \
            # normF, success = continuation_nr(Ybus=c.power_flow_input.Ybus,
            #                                  Ibus_base=c.power_flow_input.Ibus[c.bus_original_idx],
            #                                  Ibus_target=c.power_flow_input.Ibus[c.bus_original_idx],
            #                                  Sbus_base=self.inputs.Sbase[c.bus_original_idx],
            #                                  Sbus_target=self.inputs.Starget[c.bus_original_idx],
            #                                  V=self.inputs.Vbase[c.bus_original_idx],
            #                                  pv=c.power_flow_input.pv,
            #                                  pq=c.power_flow_input.pq,
            #                                  step=self.options.step,
            #                                  approximation_order=self.options.approximation_order,
            #                                  adapt_step=self.options.adapt_step,
            #                                  step_min=self.options.step_min,
            #                                  step_max=self.options.step_max,
            #                                  error_tol=1e-3,
            #                                  tol=1e-6,
            #                                  max_it=20,
            #                                  stop_at='NOSE',
            #                                  verbose=False)

            Voltage_series, Lambda_series, \
            normF, success = continuation_nr(Ybus=c.power_flow_input.Ybus,
                                             Ibus_base=c.power_flow_input.Ibus,
                                             Ibus_target=c.power_flow_input.Ibus,
                                             Sbus_base=self.inputs.Sbase[c.bus_original_idx],
                                             Sbus_target=self.inputs.Starget[c.bus_original_idx],
                                             V=self.inputs.Vbase[c.bus_original_idx],
                                             pv=c.power_flow_input.pv,
                                             pq=c.power_flow_input.pq,
                                             step=self.options.step,
                                             approximation_order=self.options.approximation_order,
                                             adapt_step=self.options.adapt_step,
                                             step_min=self.options.step_min,
                                             step_max=self.options.step_max,
                                             error_tol=1e-3,
                                             tol=1e-6,
                                             max_it=20,
                                             stop_at='NOSE',
                                             verbose=False,
                                             call_back_fx=self.progress_callback)

            res = VoltageCollapseResults(nbus=0)  # nbus can be zero, because all the arrays are going to be overwritten
            res.voltages = array(Voltage_series)
            res.lambdas = array(Lambda_series)
            res.error = normF
            res.converged = bool(success)

            self.results.apply_from_island(res, c.bus_original_idx, nbus)
        print('done!')
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True


########################################################################################################################
# Monte Carlo classes
########################################################################################################################


class MonteCarloInput:

    def __init__(self, n, Scdf, Icdf, Ycdf):
        """
        Monte carlo input constructor
        @param n: number of nodes
        @param Scdf: Power cumulative density function
        @param Icdf: Current cumulative density function
        @param Ycdf: Admittances cumulative density function
        """

        # number of nodes
        self.n = n

        self.Scdf = Scdf

        self.Icdf = Icdf

        self.Ycdf = Ycdf

    def __call__(self, samples=0, use_latin_hypercube=False):
        """
        Call this object
        :param samples: number of samples
        :param use_latin_hypercube: use Latin Hypercube to sample
        :return: Time series object
        """
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
            x: values in [0, 1] to sample the CDF

        Returns: Time series object
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

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, mc_tol=1e-3, batch_size=100, max_mc_iter=10000):
        """
        Monte Carlo simulation constructor
        :param grid: MultiGrid instance
        :param options: Power flow options
        :param mc_tol: monte carlo std.dev tolerance
        :param batch_size: size of the batch
        :param max_mc_iter: maximum monte carlo iterations in case of not reach the precission
        """
        QThread.__init__(self)

        self.grid = grid

        self.options = options

        self.mc_tol = mc_tol

        self.batch_size = batch_size
        self.max_mc_iter = max_mc_iter

        n = len(self.grid.buses)
        m = len(self.grid.branches)

        self.results = MonteCarloResults(n, m)

        self.__cancel__ = False

    def run_multi_thread(self):
        """
        Run the monte carlo simulation
        @return:
        """

        self.__cancel__ = False

        # initialize the grid time series results
        # we will append the island results with another function
        self.grid.time_series_results = TimeSeriesResults(0, 0, 0, 0, 0)
        Sbase = self.grid.Sbase
        n_cores = multiprocessing.cpu_count()

        it = 0
        variance_sum = 0.0
        std_dev_progress = 0
        v_variance = 0

        n = len(self.grid.buses)
        m = len(self.grid.branches)

        mc_results = MonteCarloResults(n, m)

        v_sum = zeros(n, dtype=complex)

        self.progress_signal.emit(0.0)

        while (std_dev_progress < 100.0) and (it < self.max_mc_iter) and not self.__cancel__:

            self.progress_text.emit('Running Monte Carlo: Variance: ' + str(v_variance))

            batch_results = MonteCarloResults(n, m, self.batch_size)

            # For every circuit, run the time series
            for circuit in self.grid.circuits:

                # set the time series as sampled
                # c.sample_monte_carlo_batch(batch_size)
                mc_time_series = circuit.monte_carlo_input(self.batch_size, use_latin_hypercube=False)
                Vbus = circuit.power_flow_input.Vbus

                manager = multiprocessing.Manager()
                return_dict = manager.dict()

                t = 0
                while t < self.batch_size and not self.__cancel__:

                    k = 0
                    jobs = list()

                    # launch only n_cores jobs at the time
                    while k < n_cores + 2 and (t + k) < self.batch_size:
                        # set the power values
                        Y, I, S = mc_time_series.get_at(t)

                        # run power flow at the circuit
                        p = multiprocessing.Process(target=power_flow_worker,
                                                    args=(t, self.options, circuit, Vbus, S / Sbase, I / Sbase, return_dict))
                        jobs.append(p)
                        p.start()
                        k += 1
                        t += 1

                    # wait for all jobs to complete
                    for proc in jobs:
                        proc.join()

                    # progress = ((t + 1) / self.batch_size) * 100
                    # self.progress_signal.emit(progress)

                # collect results
                self.progress_text.emit('Collecting batch results...')
                for t in return_dict.keys():
                    # store circuit results at the time index 't'
                    res = return_dict[t]

                    batch_results.S_points[t, circuit.bus_original_idx] = res.Sbus
                    batch_results.V_points[t, circuit.bus_original_idx] = res.voltage
                    batch_results.I_points[t, circuit.branch_original_idx] = res.Ibranch
                    batch_results.loading_points[t, circuit.branch_original_idx] = res.loading

                # # run the time series
                # for t in range(batch_size):
                #     # set the power values
                #     Y, I, S = mc_time_series.get_at(t)
                #
                #     # res = powerflow.run_at(t, mc=True)
                #     res = powerflow.run_pf(circuit=c, Vbus=Vbus, Sbus=S, Ibus=I)
                #
                #     batch_results.S_points[t, c.bus_original_idx] = res.Sbus
                #     batch_results.V_points[t, c.bus_original_idx] = res.voltage
                #     batch_results.I_points[t, c.branch_original_idx] = res.Ibranch
                #     batch_results.loading_points[t, c.branch_original_idx] = res.loading

            # Compute the Monte Carlo values
            it += self.batch_size
            mc_results.append_batch(batch_results)
            v_sum += batch_results.get_voltage_sum()
            v_avg = v_sum / it
            v_variance = abs((power(mc_results.V_points - v_avg, 2.0) / (it - 1)).min())

            # progress
            variance_sum += v_variance
            err = variance_sum / it
            if err == 0:
                err = 1e-200  # to avoid division by zeros
            mc_results.error_series.append(err)

            # emmit the progress signal
            std_dev_progress = 100 * self.mc_tol / err
            if std_dev_progress > 100:
                std_dev_progress = 100
            self.progress_signal.emit(max((std_dev_progress, it / self.max_mc_iter * 100)))

            # print(iter, '/', max_mc_iter)
            # print('Vmc:', Vavg)
            # print('Vstd:', Vvariance, ' -> ', std_dev_progress, ' %')

        # compile results
        self.progress_text.emit('Compiling results...')
        mc_results.compile()

        # compute the averaged branch magnitudes
        mc_results.sbranch, _, _, _, _ = PowerFlowMP.power_flow_post_process(self.grid, mc_results.voltage)

        # print('V mc: ', mc_results.voltage)

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

        return mc_results

    def run_single_thread(self):
        """
        Run the monte carlo simulation
        @return:
        """

        self.__cancel__ = False

        # initialize the power flow
        powerflow = PowerFlowMP(self.grid, self.options)

        # initialize the grid time series results
        # we will append the island results with another function
        self.grid.time_series_results = TimeSeriesResults(0, 0, 0, 0, 0)
        Sbase = self.grid.Sbase

        it = 0
        variance_sum = 0.0
        std_dev_progress = 0
        v_variance = 0

        n = len(self.grid.buses)
        m = len(self.grid.branches)

        mc_results = MonteCarloResults(n, m)

        v_sum = zeros(n, dtype=complex)

        self.progress_signal.emit(0.0)

        while (std_dev_progress < 100.0) and (it < self.max_mc_iter) and not self.__cancel__:

            self.progress_text.emit('Running Monte Carlo: Variance: ' + str(v_variance))

            batch_results = MonteCarloResults(n, m, self.batch_size)

            # For every circuit, run the time series
            for c in self.grid.circuits:

                # set the time series as sampled
                # c.sample_monte_carlo_batch(batch_size)
                mc_time_series = c.monte_carlo_input(self.batch_size, use_latin_hypercube=False)
                Vbus = c.power_flow_input.Vbus

                # run the time series
                for t in range(self.batch_size):
                    # set the power values
                    Y, I, S = mc_time_series.get_at(t)

                    # res = powerflow.run_at(t, mc=True)
                    res = powerflow.run_pf(circuit=c, Vbus=Vbus, Sbus=S/Sbase, Ibus=I/Sbase)

                    batch_results.S_points[t, c.bus_original_idx] = res.Sbus
                    batch_results.V_points[t, c.bus_original_idx] = res.voltage
                    batch_results.I_points[t, c.branch_original_idx] = res.Ibranch
                    batch_results.loading_points[t, c.branch_original_idx] = res.loading

            # Compute the Monte Carlo values
            it += self.batch_size
            mc_results.append_batch(batch_results)
            v_sum += batch_results.get_voltage_sum()
            v_avg = v_sum / it
            v_variance = abs((power(mc_results.V_points - v_avg, 2.0) / (it - 1)).min())

            # progress
            variance_sum += v_variance
            err = variance_sum / it
            if err == 0:
                err = 1e-200  # to avoid division by zeros
            mc_results.error_series.append(err)

            # emmit the progress signal
            std_dev_progress = 100 * self.mc_tol / err
            if std_dev_progress > 100:
                std_dev_progress = 100
            self.progress_signal.emit(max((std_dev_progress, it / self.max_mc_iter * 100)))

            # print(iter, '/', max_mc_iter)
            # print('Vmc:', Vavg)
            # print('Vstd:', Vvariance, ' -> ', std_dev_progress, ' %')

        # compile results
        self.progress_text.emit('Compiling results...')
        mc_results.compile()

        mc_results.sbranch, _, _, _, _ = PowerFlowMP.power_flow_post_process(self.grid, mc_results.voltage)

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

        return mc_results

    def run(self):
        """
        Run the monte carlo simulation
        @return:
        """
        # print('LHS run')
        self.__cancel__ = False

        if self.options.multi_thread:
            self.results = self.run_multi_thread()
        else:
            self.results = self.run_single_thread()

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        """
        Cancel the simulation
        :return:
        """
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

        self.n = n

        self.m = m

        self.S_points = zeros((p, n), dtype=complex)

        self.V_points = zeros((p, n), dtype=complex)

        self.I_points = zeros((p, m), dtype=complex)

        self.loading_points = zeros((p, m), dtype=complex)

        # self.Vstd = zeros(n, dtype=complex)

        self.error_series = list()

        self.voltage = zeros(n)
        self.current = zeros(m)
        self.loading = zeros(m)
        self.sbranch = zeros(m)
        self.losses = zeros(m)

        # magnitudes standard deviation convergence
        self.v_std_conv = None
        self.c_std_conv = None
        self.l_std_conv = None

        # magnitudes average convergence
        self.v_avg_conv = None
        self.c_avg_conv = None
        self.l_avg_conv = None

        self.available_results = ['Bus voltage avg', 'Bus voltage std',
                                  'Branch current avg', 'Branch current std',
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

            y_label = ''
            title = ''
            if result_type == 'Bus voltage avg':
                y = self.v_avg_conv[1:-1, indices]
                y_label = '(p.u.)'
                x_label = 'Sampling points'
                title = 'Bus voltage \naverage convergence'

            elif result_type == 'Branch current avg':
                y = self.c_avg_conv[1:-1, indices]
                y_label = '(p.u.)'
                x_label = 'Sampling points'
                title = 'Bus current \naverage convergence'

            elif result_type == 'Branch loading avg':
                y = self.l_avg_conv[1:-1, indices]
                y_label = '(%)'
                x_label = 'Sampling points'
                title = 'Branch loading \naverage convergence'

            elif result_type == 'Bus voltage std':
                y = self.v_std_conv[1:-1, indices]
                y_label = '(p.u.)'
                x_label = 'Sampling points'
                title = 'Bus voltage standard \ndeviation convergence'

            elif result_type == 'Branch current std':
                y = self.c_std_conv[1:-1, indices]
                y_label = '(p.u.)'
                x_label = 'Sampling points'
                title = 'Bus current standard \ndeviation convergence'

            elif result_type == 'Branch loading std':
                y = self.l_std_conv[1:-1, indices]
                y_label = '(%)'
                x_label = 'Sampling points'
                title = 'Branch loading standard \ndeviation convergence'

            elif result_type == 'Bus voltage CDF':
                cdf = CDF(np.abs(self.V_points[:, indices]))
                cdf.plot(ax=ax)
                y_label = '(p.u.)'
                x_label = 'Probability $P(X \leq x)$'
                title = 'Bus voltage'

            elif result_type == 'Branch loading CDF':
                cdf = CDF(np.abs(self.loading_points.real[:, indices]))
                cdf.plot(ax=ax)
                y_label = '(p.u.)'
                x_label = 'Probability $P(X \leq x)$'
                title = 'Branch loading'

            else:
                pass

            if 'CDF' not in result_type:
                df = pd.DataFrame(data=y, columns=labels)

                if len(df.columns) > 10:
                    df.abs().plot(ax=ax, linewidth=LINEWIDTH, legend=False)
                else:
                    df.abs().plot(ax=ax, linewidth=LINEWIDTH, legend=True)
            else:
                df = pd.DataFrame(index=cdf.prob, data=cdf.arr, columns=labels)

            ax.set_title(title)
            ax.set_ylabel(y_label)
            ax.set_xlabel(x_label)

            return df

        else:
            return None


class LatinHypercubeSampling(QThread):
    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, sampling_points=1000):
        """
        Latin Hypercube constructor
        Args:
            grid: MultiCircuit instance
            options: Power flow options
            sampling_points: number of sampling points
        """
        QThread.__init__(self)

        self.grid = grid

        self.options = options

        self.sampling_points = sampling_points

        self.results = None

        self.__cancel__ = False

    def run_multi_thread(self):
        """
        Run the monte carlo simulation
        @return:
        """
        # print('LHS run')
        self.__cancel__ = False

        # initialize vars
        batch_size = self.sampling_points
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        n_cores = multiprocessing.cpu_count()

        self.progress_signal.emit(0.0)
        self.progress_text.emit('Running Latin Hypercube Sampling in parallel using ' + str(n_cores) + ' cores ...')

        lhs_results = MonteCarloResults(n, m, batch_size)

        max_iter = batch_size * len(self.grid.circuits)
        Sbase = self.grid.Sbase
        it = 0

        # For every circuit, run the time series
        for circuit in self.grid.circuits:

            # try:
            # set the time series as sampled in the circuit
            # c.sample_monte_carlo_batch(batch_size, use_latin_hypercube=True)
            mc_time_series = circuit.monte_carlo_input(batch_size, use_latin_hypercube=True)
            Vbus = circuit.power_flow_input.Vbus

            manager = multiprocessing.Manager()
            return_dict = manager.dict()

            t = 0
            while t < batch_size and not self.__cancel__:

                k = 0
                jobs = list()

                # launch only n_cores jobs at the time
                while k < n_cores + 2 and (t + k) < batch_size:
                    # set the power values
                    Y, I, S = mc_time_series.get_at(t)

                    # run power flow at the circuit
                    p = multiprocessing.Process(target=power_flow_worker,
                                                args=(t, self.options, circuit, Vbus, S/Sbase, I/Sbase, return_dict))
                    jobs.append(p)
                    p.start()
                    k += 1
                    t += 1

                # wait for all jobs to complete
                for proc in jobs:
                    proc.join()

                progress = ((t + 1) / batch_size) * 100
                self.progress_signal.emit(progress)

            # collect results
            self.progress_text.emit('Collecting results...')
            for t in return_dict.keys():
                # store circuit results at the time index 't'
                res = return_dict[t]

                lhs_results.S_points[t, circuit.bus_original_idx] = res.Sbus
                lhs_results.V_points[t, circuit.bus_original_idx] = res.voltage
                lhs_results.I_points[t, circuit.branch_original_idx] = res.Ibranch
                lhs_results.loading_points[t, circuit.branch_original_idx] = res.loading

            # except Exception as ex:
            #     print(c.name, ex)

            if self.__cancel__:
                break

        # compile MC results
        self.progress_text.emit('Compiling results...')
        lhs_results.compile()

        # lhs_results the averaged branch magnitudes
        # lhs_results.sbranch, Ibranch, \
        # loading, lhs_results.losses, Sbus = PowerFlowMP.power_flow_post_process(self.grid, lhs_results.voltage)

        self.results = lhs_results

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

        return lhs_results

    def run_single_thread(self):
        """
        Run the monte carlo simulation
        @return:
        """
        # print('LHS run')
        self.__cancel__ = False

        # initialize the power flow
        power_flow = PowerFlowMP(self.grid, self.options)

        # initialize the grid time series results
        # we will append the island results with another function
        self.grid.time_series_results = TimeSeriesResults(0, 0, 0, 0, 0)

        batch_size = self.sampling_points
        n = len(self.grid.buses)
        m = len(self.grid.branches)

        self.progress_signal.emit(0.0)
        self.progress_text.emit('Running Latin Hypercube Sampling...')

        lhs_results = MonteCarloResults(n, m, batch_size)

        max_iter = batch_size * len(self.grid.circuits)
        Sbase = self.grid.Sbase
        it = 0

        # For every circuit, run the time series
        for c in self.grid.circuits:

            # try:
            # set the time series as sampled in the circuit
            # c.sample_monte_carlo_batch(batch_size, use_latin_hypercube=True)
            mc_time_series = c.monte_carlo_input(batch_size, use_latin_hypercube=True)
            Vbus = c.power_flow_input.Vbus

            # run the time series
            for t in range(batch_size):

                # set the power values from a Monte carlo point at 't'
                Y, I, S = mc_time_series.get_at(t)

                # Run the set monte carlo point at 't'
                # res = power_flow.run_at(t, mc=True)
                res = power_flow.run_pf(circuit=c, Vbus=Vbus, Sbus=S / Sbase, Ibus=I / Sbase)

                # Gather the results
                lhs_results.S_points[t, c.bus_original_idx] = res.Sbus
                lhs_results.V_points[t, c.bus_original_idx] = res.voltage
                lhs_results.I_points[t, c.branch_original_idx] = res.Ibranch
                lhs_results.loading_points[t, c.branch_original_idx] = res.loading

                it += 1
                self.progress_signal.emit(it / max_iter * 100)
                # print(it / max_iter * 100)

                if self.__cancel__:
                    break
            # except Exception as ex:
            #     print(c.name, ex)

            if self.__cancel__:
                break

        # compile MC results
        self.progress_text.emit('Compiling results...')
        lhs_results.compile()

        # lhs_results the averaged branch magnitudes
        lhs_results.sbranch, Ibranch, \
        loading, lhs_results.losses, Sbus = power_flow.power_flow_post_process(self.grid, lhs_results.voltage)

        self.results = lhs_results

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

        return lhs_results

    def run(self):
        """
        Run the monte carlo simulation
        @return:
        """
        # print('LHS run')
        self.__cancel__ = False

        if self.options.multi_thread:
            self.results = self.run_multi_thread()
        else:
            self.results = self.run_single_thread()

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        """
        Cancel the simulation
        """
        self.__cancel__ = True
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled')
        self.done_signal.emit()


########################################################################################################################
# Cascading classes
########################################################################################################################


class CascadingReportElement:

    def __init__(self, removed_idx, pf_results, criteria):
        """
        CascadingReportElement constructor
        :param removed_idx: list of removed branch indices
        :param pf_results: power flow results object
        :param criteria: criteria used in the end
        """
        self.removed_idx = removed_idx
        self.pf_results = pf_results
        self.criteria = criteria


class CascadingResults:

    def __init__(self, cascade_type: CascadeType):
        """
        Cascading results constructor
        :param cascade_type: Cascade type
        """
        self.cascade_type = cascade_type

        self.events = list()

    def get_failed_idx(self):
        """
        Return the array of all failed branches
        Returns:
            array of all failed branches
        """
        res = None
        for i in range(len(self.events)):
            if i == 0:
                res = self.events[i][0]
            else:
                res = r_[res, self.events[i][0]]

        return res

    def get_table(self):
        """
        Get DataFrame of the failed elements
        :return: DataFrame
        """
        dta = list()
        for i in range(len(self.events)):
            dta.append(['Step ' + str(i + 1), len(self.events[i].removed_idx), self.events[i].criteria])

        return pd.DataFrame(data=dta, columns=['Cascade step', 'Elements failed', 'Criteria'])

    def plot(self):

        # TODO: implement cascading plot
        pass


class Cascading(QThread):
    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, triggering_idx=None, max_additional_islands=1,
                 cascade_type_: CascadeType = CascadeType.LatinHypercube, n_lhs_samples_=1000):
        """
        Constructor
        Args:
            grid: MultiCircuit instance to cascade
            options: Power flow Options
            triggering_idx: branch indices to trigger first
            max_additional_islands: number of islands that shall be formed to consider a blackout
            cascade_type_: Cascade simulation kind
            n_lhs_samples_: number of latin hypercube samples if using LHS cascade
        """

        QThread.__init__(self)

        self.grid = grid

        self.options = options

        self.triggering_idx = triggering_idx

        self.__cancel__ = False

        self.current_step = 0

        self.max_additional_islands = max_additional_islands

        self.cascade_type = cascade_type_

        self.n_lhs_samples = n_lhs_samples_

        self.results = CascadingResults(self.cascade_type)

    @staticmethod
    def remove_elements(circuit: Circuit, loading_vector, idx=None):
        """
        Remove branches based on loading
        Returns:
            Nothing
        """

        if idx is None:
            load = abs(loading_vector)
            idx = where(load > 1.0)[0]

            if len(idx) == 0:
                idx = where(load >= load.max())[0]

        # disable the selected branches
        # print('Removing:', idx, load[idx])

        for i in idx:
            circuit.branches[i].active = False

        return idx

    @staticmethod
    def remove_probability_based(circuit: MultiCircuit, results: MonteCarloResults, max_val, min_prob):
        """
        Remove branches based on their chance of overload
        :param circuit:
        :param results:
        :param max_val:
        :param min_prob:
        :return: list of indices actually removed
        """
        idx, val, prob, loading = results.get_index_loading_cdf(max_val=max_val)

        any_removed = False
        indices = list()
        criteria = 'None'

        for i, idx_val in enumerate(idx):
            if prob[i] >= min_prob:
                any_removed = True
                circuit.branches[idx_val].active = False
                indices.append(idx_val)
                criteria = 'Overload probability > ' + str(min_prob)

        if not any_removed:

            if len(loading) > 0:
                if len(idx) > 0:
                    # pick a random value
                    idx_val = np.random.randint(0, len(idx))
                    criteria = 'Random with overloads'

                else:
                    # pick the most loaded
                    idx_val = int(np.where(loading == max(loading))[0][0])
                    criteria = 'Max loading, Overloads not seen'

                circuit.branches[idx_val].active = False
                indices.append(idx_val)
            else:
                indices = []
                criteria = 'No branches'

        return indices, criteria

    def perform_step_run(self):
        """
        Perform only one step cascading
        Returns:
            Nothing
        """

        # recompile the grid
        self.grid.compile()

        # initialize the simulator
        if self.cascade_type is CascadeType.PowerFlow:
            model_simulator = PowerFlow(self.grid, self.options)

        elif self.cascade_type is CascadeType.LatinHypercube:
            model_simulator = LatinHypercubeSampling(self.grid, self.options, sampling_points=self.n_lhs_samples)

        else:
            model_simulator = PowerFlow(self.grid, self.options)

        # For every circuit, run a power flow
        # for c in self.grid.circuits:
        model_simulator.run()

        if self.current_step == 0:
            # the first iteration try to trigger the selected indices, if any
            idx = self.remove_elements(self.grid, idx=self.triggering_idx)
        else:
            # cascade normally
            idx = self.remove_elements(self.grid)

        # store the removed indices and the results
        entry = CascadingReportElement(idx, model_simulator.results)
        self.results.events.append(entry)

        # increase the step number
        self.current_step += 1

        # print(model_simulator.results.get_convergence_report())

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def run(self):
        """
        Run the monte carlo simulation
        @return:
        """

        self.__cancel__ = False

        self.results = CascadingResults(self.cascade_type)

        if len(self.grid.circuits) == 0:
            self.grid.compile()

        # initialize the simulator
        if self.cascade_type is CascadeType.PowerFlow:
            model_simulator = PowerFlowMP(self.grid, self.options)

        elif self.cascade_type is CascadeType.LatinHypercube:
            model_simulator = LatinHypercubeSampling(self.grid, self.options, sampling_points=self.n_lhs_samples)

        else:
            model_simulator = PowerFlowMP(self.grid, self.options)

        self.progress_signal.emit(0.0)
        self.progress_text.emit('Running cascading failure...')

        n_grids = len(self.grid.circuits) + self.max_additional_islands
        if n_grids > len(self.grid.buses):  # safety check
            n_grids = len(self.grid.buses) - 1

        # print('n grids: ', n_grids)

        it = 0
        while len(self.grid.circuits) <= n_grids and it <= n_grids:

            # For every circuit, run a power flow
            # for c in self.grid.circuits:
            results = model_simulator.run()
            # print(model_simulator.results.get_convergence_report())

            # remove grid elements (branches)
            idx, criteria = self.remove_probability_based(self.grid, results, max_val=1.0, min_prob=0.1)

            # store the removed indices and the results
            entry = CascadingReportElement(idx, results, criteria)
            self.results.events.append(entry)

            # recompile grid
            self.grid.compile()

            it += 1

            prog = max(len(self.grid.circuits) / (n_grids+1), it/(n_grids+1))
            self.progress_signal.emit(prog * 100.0)

            if self.__cancel__:
                break

        print('Grid split into ', len(self.grid.circuits), ' islands after', it, ' steps')

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def get_failed_idx(self):
        """
        Return the array of all failed branches
        Returns:
            array of all failed branches
        """
        return self.results.get_failed_idx()

    def get_table(self):
        """
        Get DataFrame of the failed elements
        :return: DataFrame
        """
        return self.results.get_table()

    def cancel(self):
        """
        Cancel the simulation
        :return:
        """
        self.__cancel__ = True
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled')
        self.done_signal.emit()


########################################################################################################################
# Optimization classes
########################################################################################################################


class Optimize(QThread):
    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, max_iter=1000):
        """
        Constructor
        Args:
            grid: Grid to cascade
            options: Power flow Options
            max_iter: max iterations
        """

        QThread.__init__(self)

        self.grid = grid

        self.options = options

        self.__cancel__ = False

        # initialize the power flow
        self.power_flow = PowerFlow(self.grid, self.options)

        self.max_eval = max_iter
        n = len(self.grid.buses)
        m = len(self.grid.branches)

        # the dimension is the number of nodes
        self.dim = n

        # results
        self.results = MonteCarloResults(n, m, self.max_eval)

        # variables for the optimization
        self.xlow = zeros(n)  # lower bounds
        self.xup = ones(n)
        self.info = ""  # info
        self.integer = array([])  # integer variables
        self.continuous = arange(0, n, 1)  # continuous variables
        self.solution = None
        self.optimization_values = None
        self.it = 0

    def objfunction(self, x):
        """
        Objective function to run
        :param x: combinations of values between 0~1
        :return: objective function value, the average voltage in this case
        """
        Vbus = self.grid.power_flow_input.Vbus

        # For every circuit, run the time series
        for circuit in self.grid.circuits:
            # sample from the CDF give the vector x of values in [0, 1]
            # c.sample_at(x)
            mc_time_series = circuit.monte_carlo_input.get_at(x)

            Y, I, S = mc_time_series.get_at(t=0)

            #  run the sampled values
            # res = self.power_flow.run_at(0, mc=True)
            res = self.power_flow.run_pf(circuit=circuit, Vbus=Vbus, Sbus=S, Ibus=I)

            # Y, I, S = circuit.mc_time_series.get_at(0)
            self.results.S_points[self.it, circuit.bus_original_idx] = S
            self.results.V_points[self.it, circuit.bus_original_idx] = res.voltage[circuit.bus_original_idx]
            self.results.I_points[self.it, circuit.branch_original_idx] = res.Ibranch[circuit.branch_original_idx]
            self.results.loading_points[self.it, circuit.branch_original_idx] = res.loading[circuit.branch_original_idx]

        self.it += 1
        prog = self.it / self.max_eval * 100
        # self.progress_signal.emit(prog)

        f = abs(self.results.V_points[self.it - 1, :].sum()) / self.dim
        # print(prog, ' % \t', f)

        return f

    def run(self):
        """
        Run the optimization
        @return: Nothing
        """
        self.it = 0
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        self.xlow = zeros(n)  # lower bounds
        self.xup = ones(n)  # upper bounds
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Running stochastic voltage collapse...')
        self.results = MonteCarloResults(n, m, self.max_eval)

        # (1) Optimization problem
        # print(data.info)

        # (2) Experimental design
        # Use a symmetric Latin hypercube with 2d + 1 samples
        exp_des = SymmetricLatinHypercube(dim=self.dim, npts=2 * self.dim + 1)

        # (3) Surrogate model
        # Use a cubic RBF interpolant with a linear tail
        surrogate = RBFInterpolant(kernel=CubicKernel, tail=LinearTail, maxp=self.max_eval)

        # (4) Adaptive sampling
        # Use DYCORS with 100d candidate points
        adapt_samp = CandidateDYCORS(data=self, numcand=100 * self.dim)

        # Use the serial controller (uses only one thread)
        controller = SerialController(self.objfunction)

        # (5) Use the sychronous strategy without non-bound constraints
        strategy = SyncStrategyNoConstraints(worker_id=0,
                                             data=self,
                                             maxeval=self.max_eval,
                                             nsamples=1,
                                             exp_design=exp_des,
                                             response_surface=surrogate,
                                             sampling_method=adapt_samp)
        controller.strategy = strategy

        # Run the optimization strategy
        result = controller.run()

        # Print the final result
        print('Best value found: {0}'.format(result.value))
        print('Best solution found: {0}'.format(np.array_str(result.params[0], max_line_width=np.inf, precision=5,
                                                             suppress_small=True)))
        self.solution = result.params[0]

        # Extract function values from the controller
        self.optimization_values = np.array([o.value for o in controller.fevals])

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def plot(self, ax=None):
        """
        Plot the optimization convergence
        """
        clr = np.array(['#2200CC', '#D9007E', '#FF6600', '#FFCC00', '#ACE600', '#0099CC',
                        '#8900CC', '#FF0000', '#FF9900', '#FFFF00', '#00CC01', '#0055CC'])
        if self.optimization_values is not None:
            max_eval = len(self.optimization_values)

            if ax is None:
                f, ax = plt.subplots()
            # Points
            ax.scatter(np.arange(0, max_eval), self.optimization_values, color=clr[6])
            # Best value found
            ax.plot(np.arange(0, max_eval), np.minimum.accumulate(self.optimization_values), color=clr[1],
                    linewidth=3.0)
            ax.set_xlabel('Evaluations')
            ax.set_ylabel('Function Value')
            ax.set_title('Optimization convergence')

    def cancel(self):
        """
        Cancel the simulation
        """
        self.__cancel__ = True
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled')
        self.done_signal.emit()


########################################################################################################################
# Optimal Power flow classes
########################################################################################################################

class DcOpf:

    def __init__(self, circuit, options):
        """
        OPF simple dispatch problem
        :param circuit: GridCal Circuit instance (remember this must be a connected island)
        :param options: OptimalPowerFlowOptions instance
        """

        self.circuit = circuit

        self.load_shedding = options.load_shedding

        self.Sbase = circuit.Sbase
        self.B = circuit.power_flow_input.Ybus.imag.tocsr()
        self.nbus = self.B.shape[0]
        self.nbranch = len(self.circuit.branches)

        # node sets
        self.pqpv = circuit.power_flow_input.pqpv
        self.pv = circuit.power_flow_input.pv
        self.vd = circuit.power_flow_input.ref
        self.pq = circuit.power_flow_input.pq

        # declare the voltage angles and the possible load shed values
        self.theta = [None] * self.nbus
        self.load_shed = [None] * self.nbus
        for i in range(self.nbus):
            self.theta[i] = pulp.LpVariable("Theta_" + str(i), -0.5, 0.5)
            self.load_shed[i] = pulp.LpVariable("LoadShed_" + str(i), 0.0, 1e20)

        # declare the slack vars
        self.slack_loading_ij_p = [None] * self.nbranch
        self.slack_loading_ji_p = [None] * self.nbranch
        self.slack_loading_ij_n = [None] * self.nbranch
        self.slack_loading_ji_n = [None] * self.nbranch

        if self.load_shedding:
            pass

        else:

            for i in range(self.nbranch):
                self.slack_loading_ij_p[i] = pulp.LpVariable("LoadingSlack_ij_p_" + str(i), 0, 1e20)
                self.slack_loading_ji_p[i] = pulp.LpVariable("LoadingSlack_ji_p_" + str(i), 0, 1e20)
                self.slack_loading_ij_n[i] = pulp.LpVariable("LoadingSlack_ij_n_" + str(i), 0, 1e20)
                self.slack_loading_ji_n[i] = pulp.LpVariable("LoadingSlack_ji_n_" + str(i), 0, 1e20)

        # declare the generation
        self.PG = list()

        # LP problem
        self.problem = None

        # potential errors flag
        self.potential_errors = False

        # Check if the problem was solved or not
        self.solved = False

        # LP problem restrictions saved on build and added to the problem with every load change
        self.s_restrictions = list()
        self.p_restrictions = list()

        self.loads = np.zeros(self.nbus)

    def build(self, t_idx=None):
        """
        Build the OPF problem using the sparse formulation
        In this step, the circuit loads are not included
        those are added separately for greater flexibility
        """

        '''
        CSR format explanation:
        The standard CSR representation where the column indices for row i are stored in 

        -> indices[indptr[i]:indptr[i+1]] 

        and their corresponding values are stored in 

        -> data[indptr[i]:indptr[i+1]]

        If the shape parameter is not supplied, the matrix dimensions are inferred from the index arrays.

        https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csr_matrix.html
        '''

        print('Compiling LP')
        prob = pulp.LpProblem("DC optimal power flow", pulp.LpMinimize)

        # initialize the potential errors
        self.potential_errors = False

        ################################################################################################################
        # Add the objective function
        ################################################################################################################
        fobj = 0.0

        # add the voltage angles multiplied by zero (trick)
        for j in self.pqpv:
            fobj += self.theta[j] * 0.0

        # Add the generators cost
        for k, bus in enumerate(self.circuit.buses):

            generators = bus.controlled_generators + bus.batteries

            # check that there are at least one generator at the slack node
            if len(generators) == 0 and bus.type == NodeType.REF:
                self.potential_errors = True
                warn('There is no generator at the Slack node ' + bus.name + '!!!')

            # Add the bus LP vars
            for i, gen in enumerate(generators):

                # add the variable to the objective function
                if gen.active and gen.enabled_dispatch:
                    if t_idx is None:
                        fobj += gen.LPVar_P * gen.Cost
                        # add the var reference just to print later...
                        self.PG.append(gen.LPVar_P)
                    else:
                        fobj += gen.LPVar_P_prof[t_idx] * gen.Cost
                        # add the var reference just to print later...
                        self.PG.append(gen.LPVar_P_prof[t_idx])
                else:
                    pass  # the generator is not active

            # minimize the load shedding if activated
            if self.load_shedding:
                fobj += self.load_shed[k]

        # minimize the branch loading slack if not load shedding
        if not self.load_shedding:
            # Minimize the branch overload slacks
            for k, branch in enumerate(self.circuit.branches):
                if branch.active:
                    fobj += self.slack_loading_ij_p[k] + self.slack_loading_ij_n[k]
                    fobj += self.slack_loading_ji_p[k] + self.slack_loading_ji_n[k]
                else:
                    pass  # the branch is not active

        # Add the objective function to the problem
        prob += fobj

        ################################################################################################################
        # Add the nodal power balance equations as constraints (without loads, those are added later)
        # See: https://math.stackexchange.com/questions/1727572/solving-a-feasible-system-of-linear-equations-
        #      using-linear-programming
        ################################################################################################################
        for i in self.pqpv:

            calculated_node_power = 0
            node_power_injection = 0
            generators = self.circuit.buses[i].controlled_generators + self.circuit.buses[i].batteries

            # add the calculated node power
            for ii in range(self.B.indptr[i], self.B.indptr[i+1]):

                j = self.B.indices[ii]

                if j not in self.vd:

                    calculated_node_power += self.B.data[ii] * self.theta[j]

                    if self.B.data[ii] < 1e-6:
                        warn("There are susceptances close to zero.")

            # add the generation LP vars
            if t_idx is None:
                for gen in generators:
                    if gen.active:
                        if gen.enabled_dispatch:
                            # add the dispatch variable
                            node_power_injection += gen.LPVar_P
                        else:
                            # set the default value
                            node_power_injection += gen.P / self.Sbase
                    else:
                        pass
            else:
                for gen in generators:
                    if gen.active:
                        if gen.enabled_dispatch:
                            # add the dispatch variable
                            node_power_injection += gen.LPVar_P_prof[t_idx]
                        else:
                            # set the default profile value
                            node_power_injection += gen.Pprof.values[t_idx] / self.Sbase
                    else:
                        pass

            # Store the terms for adding the load later.
            # This allows faster problem compilation in case of recurrent runs
            self.s_restrictions.append(calculated_node_power)
            self.p_restrictions.append(node_power_injection)

            # # add the nodal demand: See 'set_loads()'
            # for load in self.circuit.buses[i].loads:
            #     node_power_injection -= load.S.real / self.Sbase
            #
            # prob.add(calculated_node_power == node_power_injection, 'ct_node_mismatch_' + str(i))

        ################################################################################################################
        #  set the slack nodes voltage angle
        ################################################################################################################
        for i in self.vd:
            prob.add(self.theta[i] == 0, 'ct_slack_theta_' + str(i))

        ################################################################################################################
        #  set the slack generator power
        ################################################################################################################
        for i in self.vd:

            val = 0
            g = 0
            generators = self.circuit.buses[i].controlled_generators + self.circuit.buses[i].batteries

            # compute the slack node power
            for ii in range(self.B.indptr[i], self.B.indptr[i+1]):
                j = self.B.indices[ii]
                val += self.B.data[ii] * self.theta[j]

            # Sum the slack generators
            if t_idx is None:
                for gen in generators:
                    if gen.active and gen.enabled_dispatch:
                        g += gen.LPVar_P
                    else:
                        pass
            else:
                for gen in generators:
                    if gen.active and gen.enabled_dispatch:
                        g += gen.LPVar_P_prof[t_idx]
                    else:
                        pass

            # the sum of the slack node generators must be equal to the slack node power
            prob.add(g == val, 'ct_slack_power_' + str(i))

        ################################################################################################################
        # Set the branch limits
        ################################################################################################################
        any_rate_zero = False
        for k, branch in enumerate(self.circuit.branches):

            if branch.active:
                i = self.circuit.buses_dict[branch.bus_from]
                j = self.circuit.buses_dict[branch.bus_to]

                # branch flow
                Fij = self.B[i, j] * (self.theta[i] - self.theta[j])
                Fji = self.B[i, j] * (self.theta[j] - self.theta[i])

                # constraints
                if not self.load_shedding:
                    # Add slacks
                    prob.add(Fij + self.slack_loading_ij_p[k] - self.slack_loading_ij_n[k] <= branch.rate / self.Sbase, 'ct_br_flow_ij_' + str(k))
                    prob.add(Fji + self.slack_loading_ji_p[k] - self.slack_loading_ji_n[k] <= branch.rate / self.Sbase, 'ct_br_flow_ji_' + str(k))
                    # prob.add(Fij <= branch.rate / self.Sbase, 'ct_br_flow_ij_' + str(k))
                    # prob.add(Fji <= branch.rate / self.Sbase, 'ct_br_flow_ji_' + str(k))
                else:
                    # The slacks are in the form of load shedding
                    prob.add(Fij <= branch.rate / self.Sbase, 'ct_br_flow_ij_' + str(k))
                    prob.add(Fji <= branch.rate / self.Sbase, 'ct_br_flow_ji_' + str(k))

                if branch.rate <= 1e-6:
                    any_rate_zero = True
            else:
                pass  # the branch is not active...

        # No branch can have rate = 0, otherwise the problem fails
        if any_rate_zero:
            self.potential_errors = True
            warn('There are branches with no rate.')

        # set the global OPF LP problem
        self.problem = prob

    def set_loads(self, t_idx=None):
        """
        Add the loads to the LP problem
        Args:
            t_idx: time index, if none, the default object values are taken
        """

        if t_idx is None:

            # use the default loads
            for k, i in enumerate(self.pqpv):

                # these restrictions come from the build step to be fulfilled with the load now
                node_power_injection = self.p_restrictions[k]
                calculated_node_power = self.s_restrictions[k]

                # add the nodal demand
                for load in self.circuit.buses[i].loads:
                    if load.active:
                        self.loads[i] += load.S.real / self.Sbase
                    else:
                        pass

                if calculated_node_power is 0 and node_power_injection is 0:
                    # nodes without injection or generation
                    pass
                else:
                    # add the restriction
                    if self.load_shedding:

                        self.problem.add(calculated_node_power == node_power_injection - self.loads[i] + self.load_shed[i],
                                         self.circuit.buses[i].name + '_ct_node_mismatch_' + str(k))

                        # if there is no load at the node, do not allow load shedding
                        if len(self.circuit.buses[i].loads) == 0:
                            self.problem.add(self.load_shed[i] == 0.0, self.circuit.buses[i].name + '_ct_null_load_shed_' + str(k))

                    else:
                        self.problem.add(calculated_node_power == node_power_injection - self.loads[i],
                                         self.circuit.buses[i].name + '_ct_node_mismatch_' + str(k))
        else:
            # Use the load profile values at index=t_idx
            for k, i in enumerate(self.pqpv):

                # these restrictions come from the build step to be fulfilled with the load now
                node_power_injection = self.p_restrictions[k]
                calculated_node_power = self.s_restrictions[k]

                # add the nodal demand
                for load in self.circuit.buses[i].loads:
                    if load.active:
                        self.loads[i] += load.Sprof.values[t_idx].real / self.Sbase
                    else:
                        pass

                # add the restriction
                if self.load_shedding:

                    self.problem.add(
                        calculated_node_power == node_power_injection - self.loads[i] + self.load_shed[i],
                        self.circuit.buses[i].name + '_ct_node_mismatch_' + str(k))

                    # if there is no load at the node, do not allow load shedding
                    if len(self.circuit.buses[i].loads) == 0:
                        self.problem.add(self.load_shed[i] == 0.0,
                                         self.circuit.buses[i].name + '_ct_null_load_shed_' + str(k))

                else:
                    self.problem.add(calculated_node_power == node_power_injection - self.loads[i],
                                     self.circuit.buses[i].name + '_ct_node_mismatch_' + str(k))

    def solve(self):
        """
        Solve the LP OPF problem
        """

        if not self.potential_errors:

            # if there is no problem there, make it
            if self.problem is None:
                self.build()

            print('Solving LP')
            print('Load shedding:', self.load_shedding)
            self.problem.solve()  # solve with CBC
            # prob.solve(CPLEX())

            # self.problem.writeLP('dcopf.lp')

            # The status of the solution is printed to the screen
            print("Status:", pulp.LpStatus[self.problem.status])

            # The optimised objective function value is printed to the screen
            print("Cost =", pulp.value(self.problem.objective), '€')

            self.solved = True

        else:
            self.solved = False

    def print(self):
        """
        Print results
        :return:
        """
        print('\nVoltage angles (in rad)')
        for i, th in enumerate(self.theta):
            print('Bus', i, '->', th.value())

        print('\nGeneration power (in MW)')
        for i, g in enumerate(self.PG):
            val = g.value() * self.Sbase if g.value() is not None else 'None'
            print(g.name, '->', val)

        # Set the branch limits
        print('\nBranch flows (in MW)')
        for k, branch in enumerate(self.circuit.branches):
            i = self.circuit.buses_dict[branch.bus_from]
            j = self.circuit.buses_dict[branch.bus_to]
            if self.theta[i].value() is not None and self.theta[j].value() is not None:
                F = self.B[i, j] * (self.theta[i].value() - self.theta[j].value()) * self.Sbase
            else:
                F = 'None'
            print('Branch ' + str(i) + '-' + str(j) + '(', branch.rate, 'MW) ->', F)

    def get_results(self, save_lp_file=False, t_idx=None, realistic=False):
        """
        Return the optimization results
        :param save_lp_file:
        :param t_idx:
        :param realistic:
        :return: OptimalPowerFlowResults instance
        """

        # initialize results object
        n = len(self.circuit.buses)
        m = len(self.circuit.branches)
        res = OptimalPowerFlowResults(is_dc=True)
        res.initialize(n, m)

        if save_lp_file:
            # export the problem formulation to an LP file
            self.problem.writeLP('dcopf.lp')

        if self.solved:

            if realistic:

                # Add buses
                for i in range(n):
                    # Set the voltage
                    res.voltage[i] = 1 * exp(1j * self.theta[i].value())

                    if self.load_shed is not None:
                        res.load_shedding[i] = self.load_shed[i].value()

                # Set the values
                res.Sbranch, res.Ibranch, res.loading, \
                res.losses, res.Sbus = PowerFlowMP.power_flow_post_process(self.circuit, res.voltage)

            else:
                # Add buses
                for i in range(n):
                    # g = 0.0
                    #
                    # generators = self.circuit.buses[i].controlled_generators + self.circuit.buses[i].batteries
                    #
                    # # Sum the slack generators
                    # if t_idx is None:
                    #     for gen in generators:
                    #         if gen.active and gen.enabled_dispatch:
                    #             g += gen.LPVar_P.value()
                    # else:
                    #     for gen in generators:
                    #         if gen.active and gen.enabled_dispatch:
                    #             g += gen.LPVar_P_prof[t_idx].value()
                    #
                    # # Set the results
                    # res.Sbus[i] = (g - self.loads[i]) * self.circuit.Sbase

                    # Set the voltage
                    res.voltage[i] = 1 * exp(1j * self.theta[i].value())

                    if self.load_shed is not None:
                        res.load_shedding[i] = self.load_shed[i].value()

                # Set the values
                res.Sbranch, res.Ibranch, res.loading, \
                res.losses, res.Sbus = PowerFlowMP.power_flow_post_process(self.circuit, res.voltage, only_power=True)

                # Add branches
                for k, branch in enumerate(self.circuit.branches):

                    if branch.active:
                        # get the from and to nodal indices of the branch
                        i = self.circuit.buses_dict[branch.bus_from]
                        j = self.circuit.buses_dict[branch.bus_to]

                        # compute the power flowing
                        if self.theta[i].value() is not None and self.theta[j].value() is not None:
                            F = self.B[i, j] * (self.theta[i].value() - self.theta[j].value()) * self.Sbase
                        else:
                            F = -1

                        # Set the results
                        if self.slack_loading_ij_p[k] is not None:
                            res.overloads[k] = (self.slack_loading_ij_p[k].value()
                                                + self.slack_loading_ji_p[k].value()
                                                - self.slack_loading_ij_n[k].value()
                                                - self.slack_loading_ji_n[k].value()) * self.Sbase
                        res.Sbranch[k] = F
                        res.loading[k] = abs(F / branch.rate)
                    else:
                        pass

        else:
            # the problem did not solve, pass
            pass

        return res


class AcOpf:

    def __init__(self, circuit: Circuit, options, voltage_band=0.1):
        """
        Linearized AC power flow, solved with a linear solver :o
        :param circuit: GridCal Circuit instance
        """

        self.vm_low = 1.0 - voltage_band
        self.vm_high = 1.0 + voltage_band

        self.load_shedding = options.load_shedding

        self.circuit = circuit
        self.Sbase = circuit.Sbase

        # node sets
        self.pv = circuit.power_flow_input.pv
        self.pq = circuit.power_flow_input.pq
        self.vd = circuit.power_flow_input.ref
        self.pvpq = r_[self.pv, self.pq]
        self.pvpqpq = r_[self.pv, self.pq, self.pq]

        Y = circuit.power_flow_input.Ybus
        self.B = circuit.power_flow_input.Ybus.imag
        Ys = circuit.power_flow_input.Yseries
        S = circuit.power_flow_input.Sbus
        self.V = circuit.power_flow_input.Vbus.copy()

        # form the system matrix
        A11 = -Ys.imag[self.pvpq, :][:, self.pvpq]
        A12 = Y.real[self.pvpq, :][:, self.pq]
        A21 = -Ys.real[self.pq, :][:, self.pvpq]
        A22 = -Y.imag[self.pq, :][:, self.pq]
        self.sys_mat = vstack_s([hstack_s([A11, A12]),
                                 hstack_s([A21, A22])], format="csr")

        # form the slack system matrix
        A11s = -Ys.imag[self.vd, :][:, self.pvpq]
        A12s = Y.real[self.vd, :][:, self.pq]
        self.sys_mat_slack = hstack_s([A11s, A12s], format="csr")

        # compose the right hand side (power vectors)
        self.rhs = r_[S.real[self.pvpq], S.imag[self.pq]]

        # declare the voltage increments dx
        self.nn = self.sys_mat.shape[0]
        self.nbranch = len(self.circuit.branches)
        self.nbus = len(self.circuit.buses)
        self.dx_var = [None] * self.nn

        self.flow_ij = [None] * self.nbranch
        self.flow_ji = [None] * self.nbranch

        self.theta_dict = dict()

        self.loads = np.zeros(self.nn)
        self.load_shed = [None] * self.nn

        npv = len(self.pv)
        npq = len(self.pq)
        for i in range(self.nn):
            if i < (npv+npq):
                self.dx_var[i] = pulp.LpVariable("Va" + str(i), -0.5, 0.5)
                self.theta_dict[self.pvpq[i]] = self.dx_var[i]  # dictionary to store the angles for the pvpq nodes
                self.load_shed[i] = pulp.LpVariable("LoadShed_P_" + str(i), 0.0, 1e20)
            else:
                self.dx_var[i] = pulp.LpVariable("Vm" + str(i))
                self.load_shed[i] = pulp.LpVariable("LoadShed_Q_" + str(i), 0.0, 1e20)

        # declare the slack vars
        self.slack_loading_ij_p = [None] * self.nbranch
        self.slack_loading_ji_p = [None] * self.nbranch
        self.slack_loading_ij_n = [None] * self.nbranch
        self.slack_loading_ji_n = [None] * self.nbranch

        if self.load_shedding:
            pass

        else:

            for i in range(self.nbranch):
                self.slack_loading_ij_p[i] = pulp.LpVariable("LoadingSlack_ij_p_" + str(i), 0, 1e20)
                self.slack_loading_ji_p[i] = pulp.LpVariable("LoadingSlack_ji_p_" + str(i), 0, 1e20)
                self.slack_loading_ij_n[i] = pulp.LpVariable("LoadingSlack_ij_n_" + str(i), 0, 1e20)
                self.slack_loading_ji_n[i] = pulp.LpVariable("LoadingSlack_ji_n_" + str(i), 0, 1e20)

        # declare the generation
        self.PG = list()

        # LP problem
        self.problem = None

        # potential errors flag
        self.potential_errors = False

        # Check if the problem was solved or not
        self.solved = False

        # LP problem restrictions saved on build and added to the problem with every load change
        self.s_restrictions = list()
        self.p_restrictions = list()

    def build(self, t_idx=None):
        """
        Formulate and Solve the AC LP problem
        :return: Nothing
        """
        prob = pulp.LpProblem("AC power flow", pulp.LpMinimize)

        npv = len(self.pv)
        npq = len(self.pq)

        ################################################################################################################
        # Add the objective function
        ################################################################################################################
        fobj = 0.0

        # Add the objective function (all zeros)
        # for i in range(self.nn):
        #     fobj += self.dx_var[i] * 0.0

        # Add the generators cost
        for k, bus in enumerate(self.circuit.buses):

            generators = bus.controlled_generators + bus.batteries

            # check that there are at least one generator at the slack node
            if len(generators) == 0 and bus.type == NodeType.REF:
                self.potential_errors = True
                warn('There is no generator at the Slack node ' + bus.name + '!!!')

            # Add the bus LP vars
            for i, gen in enumerate(generators):

                # add the variable to the objective function
                if gen.active and gen.enabled_dispatch:
                    if t_idx is None:
                        fobj += gen.LPVar_P * gen.Cost
                        # add the var reference just to print later...
                        self.PG.append(gen.LPVar_P)
                    else:
                        fobj += gen.LPVar_P_prof[t_idx] * gen.Cost
                        # add the var reference just to print later...
                        self.PG.append(gen.LPVar_P_prof[t_idx])
                else:
                    pass  # the generator is not active

            # minimize the load shedding if activated
            if self.load_shedding:
                fobj += self.load_shed[k]

        # minimize the branch loading slack if not load shedding
        if not self.load_shedding:
            # Minimize the branch overload slacks
            for k, branch in enumerate(self.circuit.branches):
                if branch.active:
                    fobj += self.slack_loading_ij_p[k] + self.slack_loading_ij_n[k]
                    fobj += self.slack_loading_ji_p[k] + self.slack_loading_ji_n[k]
                else:
                    pass  # the branch is not active

        # Add the objective function to the problem
        prob += fobj
        ################################################################################################################
        # Add the matrix multiplication as constraints
        # See: https://math.stackexchange.com/questions/1727572/solving-a-feasible-system-of-linear-equations-
        #      using-linear-programming
        ################################################################################################################

        # Matrix product
        for i in range(self.nn):

            calculated_node_power = 0
            node_power_injection = 0

            # add the calculated node power
            for ii in range(self.sys_mat.indptr[i], self.sys_mat.indptr[i + 1]):
                j = self.sys_mat.indices[ii]
                calculated_node_power += self.sys_mat.data[ii] * self.dx_var[j]

            # Only for PV!
            if i < npv:

                # gather the generators at the node
                k = self.pvpqpq[i]
                generators = self.circuit.buses[k].controlled_generators + self.circuit.buses[k].batteries

                # add the generation LP vars
                if t_idx is None:
                    for gen in generators:
                        if gen.active:
                            if gen.enabled_dispatch:
                                # add the dispatch variable
                                node_power_injection += gen.LPVar_P
                            else:
                                # set the default value
                                node_power_injection += gen.P / self.Sbase
                        else:
                            pass
                else:
                    for gen in generators:
                        if gen.active:
                            if gen.enabled_dispatch:
                                # add the dispatch variable
                                node_power_injection += gen.LPVar_P_prof[t_idx]
                            else:
                                # set the default profile value
                                node_power_injection += gen.Pprof.values[t_idx] / self.Sbase
                        else:
                            pass
            else:
                pass  # it is a PQ node, no generators there

            # Store the terms for adding the load later.
            # This allows faster problem compilation in case of recurrent runs
            self.s_restrictions.append(calculated_node_power)
            self.p_restrictions.append(node_power_injection)

            # const = s == self.rhs[i]
            # prob += const

        ################################################################################################################
        # Add the matrix multiplication as constraints (slack)
        ################################################################################################################

        for i in range(self.sys_mat_slack.shape[0]):  # vd nodes

            calculated_node_power = 0
            node_power_injection = 0

            # add the calculated node power
            for ii in range(self.sys_mat_slack.indptr[i], self.sys_mat_slack.indptr[i + 1]):
                j = self.sys_mat_slack.indices[ii]
                calculated_node_power += self.sys_mat_slack.data[ii] * self.dx_var[j]

            # Only for PV!
            if i < npv:

                # gather the generators at the node
                k = self.vd[i]
                generators = self.circuit.buses[k].controlled_generators + self.circuit.buses[k].batteries

                # add the generation LP vars
                if t_idx is None:
                    for gen in generators:
                        if gen.active and gen.enabled_dispatch:
                            node_power_injection += gen.LPVar_P
                        else:
                            pass
                else:
                    for gen in generators:
                        if gen.active and gen.enabled_dispatch:
                            node_power_injection += gen.LPVar_P_prof[t_idx]
                        else:
                            pass
            else:
                pass  # it is a PQ node, no generators there

            # the sum of the slack node generators must be equal to the slack node power
            prob.add(calculated_node_power == node_power_injection, 'ct_slack_power_' + str(i))

        ################################################################################################################
        # control the voltage module between vm_low and vm_high
        ################################################################################################################
        for k, i in enumerate(self.pq):
            vm_var = abs(self.V[i]) + self.dx_var[npv + npq + k]  # compose the voltage module
            prob += vm_var <= self.vm_high
            prob += self.vm_low <= vm_var

        ################################################################################################################
        # control the voltage angles: Already defined with bounds
        ################################################################################################################
        # No need, already done

        ################################################################################################################
        # Set the branch limits: This is the same as in the DC OPF, unless a better approximation is found
        ################################################################################################################
        for k, branch in enumerate(self.circuit.branches):
            i = self.circuit.buses_dict[branch.bus_from]
            j = self.circuit.buses_dict[branch.bus_to]

            if i in self.theta_dict.keys():
                va_i = self.theta_dict[i]
            else:
                va_i = 0.0  # is slack

            if j in self.theta_dict.keys():
                va_j = self.theta_dict[j]
            else:
                va_j = 0.0

            # branch flow
            self.flow_ij[k] = self.B[i, j] * (va_i - va_j)
            self.flow_ji[k] = self.B[i, j] * (va_j - va_i)

            # constraints
            if not self.load_shedding:
                # Add slacks
                prob.add(self.flow_ij[k] + self.slack_loading_ij_p[k] - self.slack_loading_ij_n[k] <= branch.rate / self.Sbase,
                         'ct_br_flow_ij_' + str(k))
                prob.add(self.flow_ji[k] + self.slack_loading_ji_p[k] - self.slack_loading_ji_n[k] <= branch.rate / self.Sbase,
                         'ct_br_flow_ji_' + str(k))
            else:
                # The slacks are in the form of load shedding
                prob.add(self.flow_ij[k] <= branch.rate / self.Sbase, 'ct_br_flow_ij_' + str(k))
                prob.add(self.flow_ji[k] <= branch.rate / self.Sbase, 'ct_br_flow_ji_' + str(k))

        # set the current problem
        self.problem = prob

    def set_loads(self, t_idx=None):
        """
        Add the loads to the LP problem
        Args:
            t_idx: time index, if none, the default object values are taken
        """
        npv = len(self.pv)
        npq = len(self.pq)

        if t_idx is None:

            # use the default loads
            for k, i in enumerate(self.pvpqpq):

                # these restrictions come from the build step to be fulfilled with the load now
                node_power_injection = self.p_restrictions[k]
                calculated_node_power = self.s_restrictions[k]

                # add the nodal demand
                for load in self.circuit.buses[i].loads:
                    if load.active:
                        if k < (npq + npv):
                            self.loads[i] += load.S.real / self.Sbase
                        else:
                            self.loads[i] += load.S.imag / self.Sbase
                    else:
                        pass

                if calculated_node_power is 0 and node_power_injection is 0:
                    # nodes without injection or generation
                    pass
                else:
                    # add the restriction
                    if self.load_shedding:

                        self.problem.add(calculated_node_power == node_power_injection - self.loads[i] + self.load_shed[i],
                                         self.circuit.buses[i].name + '_ct_node_mismatch_' + str(k))

                        # if there is no load at the node, do not allow load shedding
                        if len(self.circuit.buses[i].loads) == 0:
                            self.problem.add(self.load_shed[i] == 0.0, self.circuit.buses[i].name + '_ct_null_load_shed_' + str(k))

                    else:
                        self.problem.add(calculated_node_power == node_power_injection - self.loads[i],
                                         self.circuit.buses[i].name + '_ct_node_mismatch_' + str(k))
        else:
            # Use the load profile values at index=t_idx
            for k, i in enumerate(self.pvpq):

                # these restrictions come from the build step to be fulfilled with the load now
                node_power_injection = self.p_restrictions[k]
                calculated_node_power = self.s_restrictions[k]

                # add the nodal demand
                for load in self.circuit.buses[i].loads:
                    if load.active:
                        if k < (npq + npv):
                            self.loads[i] += load.Sprof.values[t_idx].real / self.Sbase
                        else:
                            self.loads[i] += load.Sprof.values[t_idx].imag / self.Sbase
                    else:
                        pass

                # add the restriction
                if self.load_shedding:

                    self.problem.add(
                        calculated_node_power == node_power_injection - self.loads[i] + self.load_shed[i],
                        self.circuit.buses[i].name + '_ct_node_mismatch_' + str(k))

                    # if there is no load at the node, do not allow load shedding
                    if len(self.circuit.buses[i].loads) == 0:
                        self.problem.add(self.load_shed[i] == 0.0,
                                         self.circuit.buses[i].name + '_ct_null_load_shed_' + str(k))

                else:
                    self.problem.add(calculated_node_power == node_power_injection - self.loads[i],
                                     self.circuit.buses[i].name + '_ct_node_mismatch_' + str(k))

    def solve(self):
        """
        Solve the LP OPF problem
        """

        if self.problem is None:
            self.build()

        if not self.potential_errors:

            # if there is no problem there, make it
            if self.problem is None:
                self.build()

            print('Solving LP')
            print('Load shedding:', self.load_shedding)
            self.problem.solve()  # solve with CBC
            # prob.solve(CPLEX())

            # self.problem.writeLP('dcopf.lp')

            # The status of the solution is printed to the screen
            print("Status:", pulp.LpStatus[self.problem.status])

            # The optimised objective function value is printed to the screen
            print("Cost =", pulp.value(self.problem.objective), '€')

            self.solved = True

            # Solve
            self.problem.solve()
            self.problem.writeLP('ac_opf.lp')

            # compose the results vector ###############################################################################
            npv = len(self.pv)
            npq = len(self.pq)

            x_inc = zeros(self.nn)
            for i, th in enumerate(self.dx_var):
                x_inc[i] = th.value()

            #  set the pv voltages
            va_pv = x_inc[0:npv]
            vm_pv = abs(self.V[self.pv])
            self.V[self.pv] = vm_pv * exp(1j * va_pv)

            # set the pq voltages
            va_pq = x_inc[npv:npv + npq]
            vm_pq = abs(self.V[self.pq]) + x_inc[npv + npq:]
            self.V[self.pq] = vm_pq * exp(1j * va_pq)

        else:
            self.solved = False

    def print(self):
        print('Voltage solution')

        # compose voltages results
        df_v = pd.DataFrame(data=np.c_[abs(self.V), np.angle(self.V), self.V.real, self.V.imag],
                            columns=['Module', 'Angle(rad)', 'Real', 'Imag'],
                            index=['Bus' + str(i) for i in range(self.V.shape[0])])

        # compose branches results
        flows = zeros(self.nbranch)
        loading = zeros(self.nbranch)
        br_names = [None] * self.nbranch
        for k in range(self.nbranch):
            flows[k] = abs(self.flow_ij[k].value()) * self.Sbase
            loading[k] = flows[k] / self.circuit.branches[k].rate * 100.0
            br_names[k] = 'Branch ' + str(k)

        df_f = pd.DataFrame(data=np.c_[flows, loading],
                            columns=['Flow (MW)', 'Loading (%)'],
                            index=br_names)

        generation = zeros(len(self.PG))
        gen_names = [None] * len(self.PG)
        for k, gen_var in enumerate(self.PG):
            generation[k] = gen_var.value() * self.Sbase
            gen_names[k] = 'Gen' + str(k)

        df_g = pd.DataFrame(data=generation,
                            columns=['Gen(MW)'],
                            index=gen_names)
        print(df_v)
        print(df_f)
        print(df_g)

    def get_results(self, save_lp_file=False, t_idx=None, realistic=False):
        """
        Return the optimization results
        :param save_lp_file:
        :param t_idx:
        :param realistic: compute the realistic values associated with the voltage solution
        :return: OptimalPowerFlowResults instance
        """

        # initialize results object
        n_bus = len(self.circuit.buses)
        n_branch = len(self.circuit.branches)
        res = OptimalPowerFlowResults(is_dc=False)
        res.initialize(n_bus, n_branch)

        if save_lp_file:
            # export the problem formulation to an LP file
            self.problem.writeLP('acopf.lp')

        if self.solved:

            if realistic:
                # Set the values
                res.Sbranch, res.Ibranch, res.loading, \
                res.losses, res.Sbus = PowerFlowMP.power_flow_post_process(self.circuit, self.V)
                res.voltage = self.V
            else:

                # Add buses
                for i in range(n_bus):

                    g = 0.0
                    generators = self.circuit.buses[i].controlled_generators + self.circuit.buses[i].batteries

                    # Sum the slack generators
                    if t_idx is None:
                        for gen in generators:
                            if gen.active and gen.enabled_dispatch:
                                g += gen.LPVar_P.value()
                    else:
                        for gen in generators:
                            if gen.active and gen.enabled_dispatch:
                                g += gen.LPVar_P_prof[t_idx].value()

                    # Set the results (power, load shedding)
                    res.Sbus[i] = (g - self.loads[i]) * self.circuit.Sbase

                    if self.load_shed is not None:
                        res.load_shedding[i] = self.load_shed[i].value()

                # Set the values
                res.Sbranch, res.Ibranch, res.loading, \
                res.losses, res.Sbus = PowerFlowMP.power_flow_post_process(self.circuit, self.V, only_power=True)
                res.voltage = self.V
                angles = np.angle(self.V)

                # Add branches
                for k, branch in enumerate(self.circuit.branches):

                    if branch.active:
                        # get the from and to nodal indices of the branch
                        i = self.circuit.buses_dict[branch.bus_from]
                        j = self.circuit.buses_dict[branch.bus_to]

                        # compute the power flowing
                        if angles[i] is not None and angles[j] is not None:
                            F = self.B[i, j] * (angles[i] - angles[j]) * self.Sbase
                        else:
                            F = -1

                        # Set the results
                        if self.slack_loading_ij_p[k] is not None:
                            res.overloads[k] = (self.slack_loading_ij_p[k].value()
                                                + self.slack_loading_ji_p[k].value()
                                                - self.slack_loading_ij_n[k].value()
                                                - self.slack_loading_ji_n[k].value()) * self.Sbase
                        res.Sbranch[k] = F
                        res.loading[k] = abs(F / branch.rate)
                    else:
                        pass

        else:
            # the problem did not solve, pass
            pass

        return res


class OptimalPowerFlowOptions:

    def __init__(self, verbose=False, load_shedding=False, solver=SolverType.DC_OPF, realistic_results=False):
        """
        OPF options constructor
        :param verbose:
        :param load_shedding:
        :param solver:
        :param realistic_results:
        """
        self.verbose = verbose

        self.load_shedding = load_shedding

        self.solver = solver

        self.realistic_results = realistic_results


class OptimalPowerFlowResults:

    def __init__(self, Sbus=None, voltage=None, load_shedding=None, Sbranch=None, overloads=None,
                 loading=None, losses=None, converged=None, is_dc=False):
        """
        OPF results constructor
        :param Sbus: bus power injections
        :param voltage: bus voltages
        :param load_shedding: load shedding values
        :param Sbranch: branch power values
        :param overloads: branch overloading values
        :param loading: branch loading values
        :param losses: branch losses
        :param converged: converged?
        """
        self.Sbus = Sbus

        self.voltage = voltage

        self.load_shedding = load_shedding

        self.Sbranch = Sbranch

        self.overloads = overloads

        self.loading = loading

        self.losses = losses

        self.converged = converged

        self.available_results = ['Bus voltage', 'Bus power', 'Branch power', 'Branch loading',
                                  'Branch overloads', 'Load shedding']

        self.plot_bars_limit = 100

        self.is_dc = is_dc

    def copy(self):
        """
        Return a copy of this
        @return:
        """
        return OptimalPowerFlowResults(Sbus=self.Sbus,
                                       voltage=self.voltage,
                                       load_shedding=self.load_shedding,
                                       Sbranch=self.Sbranch,
                                       overloads=self.overloads,
                                       loading=self.loading,
                                       losses=self.losses,
                                       converged=self.converged)

    def initialize(self, n, m):
        """
        Initialize the arrays
        @param n: number of buses
        @param m: number of branches
        @return:
        """
        self.Sbus = zeros(n, dtype=complex)

        self.voltage = zeros(n, dtype=complex)

        self.load_shedding = zeros(n, dtype=float)

        self.Sbranch = zeros(m, dtype=complex)

        self.loading = zeros(m, dtype=complex)

        self.overloads = zeros(m, dtype=complex)

        self.losses = zeros(m, dtype=complex)

        self.converged = list()

        self.plot_bars_limit = 100

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

        self.load_shedding[b_idx] = results.load_shedding

        self.Sbranch[br_idx] = results.Sbranch

        self.loading[br_idx] = results.loading

        self.overloads[br_idx] = results.overloads

        self.losses[br_idx] = results.losses

        self.converged.append(results.converged)

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

        if indices is None:
            indices = array(range(len(names)))

        if len(indices) > 0:
            labels = names[indices]
            y_label = ''
            title = ''
            if result_type == 'Bus voltage':
                if self.is_dc:
                    y = np.angle(self.voltage[indices])
                    y_label = '(rad)'
                    title = 'Bus voltage angle'
                else:
                    y = np.abs(self.voltage[indices])
                    y_label = '(p.u.)'
                    title = 'Bus voltage'

            elif result_type == 'Branch power':
                y = self.Sbranch[indices].real
                y_label = '(MW)'
                title = 'Branch power '

            elif result_type == 'Bus power':
                y = self.Sbus[indices].real
                y_label = '(MW)'
                title = 'Bus power '

            elif result_type == 'Branch loading':
                y = np.abs(self.loading[indices] * 100.0)
                y_label = '(%)'
                title = 'Branch loading '

            elif result_type == 'Branch overloads':
                y = np.abs(self.overloads[indices])
                y_label = '(MW)'
                title = 'Branch overloads '

            elif result_type == 'Branch losses':
                y = self.losses[indices].real
                y_label = '(MW)'
                title = 'Branch losses '

            elif result_type == 'Load shedding':
                y = self.load_shedding[indices]
                y_label = '(MW)'
                title = 'Load shedding'

            else:
                pass

            df = pd.DataFrame(data=y, index=labels, columns=[result_type])
            df.fillna(0, inplace=True)

            if len(df.columns) < self.plot_bars_limit:
                df.plot(ax=ax, kind='bar')
            else:
                df.plot(ax=ax, legend=False, linewidth=LINEWIDTH)
            ax.set_ylabel(y_label)
            ax.set_title(title)

            return df

        else:
            return None


class OptimalPowerFlow(QRunnable):
    # progress_signal = pyqtSignal(float)
    # progress_text = pyqtSignal(str)
    # done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: OptimalPowerFlowOptions):
        """
        PowerFlow class constructor
        @param grid: MultiCircuit Object
        @param options: OPF options
        """
        QRunnable.__init__(self)

        # Grid to run a power flow in
        self.grid = grid

        # Options to use
        self.options = options

        # OPF results
        self.results = None

        # set cancel state
        self.__cancel__ = False

        self.all_solved = True

    def single_optimal_power_flow(self, circuit: Circuit, t_idx=None):
        """
        Run a power flow simulation for a single circuit
        @param circuit: Single island circuit
        @param t_idx: time index, if none the default values are taken
        @return: OptimalPowerFlowResults object
        """

        # declare LP problem
        if self.options.solver == SolverType.DC_OPF:
            problem = DcOpf(circuit, self.options)
        else:
            problem = AcOpf(circuit, self.options)

        problem.build(t_idx=t_idx)
        problem.set_loads(t_idx=t_idx)
        problem.solve()

        # results
        res = problem.get_results(t_idx=t_idx, realistic=self.options.realistic_results)

        return res, problem.solved

    def opf(self, t_idx=None):
        """
        Run a power flow for every circuit
        @return: OptimalPowerFlowResults object
        """
        # print('PowerFlow at ', self.grid.name)
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        self.results = OptimalPowerFlowResults()
        self.results.initialize(n, m)
        # self.progress_signal.emit(0.0)

        self.all_solved = True

        k = 0
        for circuit in self.grid.circuits:

            if self.options.verbose:
                print('Solving ' + circuit.name)

            # run OPF
            optimal_power_flow_results, solved = self.single_optimal_power_flow(circuit, t_idx=t_idx)

            # assert the total solvability
            self.all_solved = self.all_solved and solved

            # merge island results
            self.results.apply_from_island(optimal_power_flow_results,
                                           circuit.bus_original_idx,
                                           circuit.branch_original_idx)

            # self.progress_signal.emit((k+1) / len(self.grid.circuits))
            k += 1

        return self.results

    def run(self):
        """
        
        :return: 
        """
        self.opf()

    def run_at(self, t):
        """
        Run power flow at the time series object index t
        @param t: time index
        @return: OptimalPowerFlowResults object
        """

        res = self.opf(t)

        return res

    def cancel(self):
        self.__cancel__ = True


class OptimalPowerFlowTimeSeriesResults:

    def __init__(self, n, m, nt, time=None, is_dc=False):
        """
        OPF Time Series results constructor
        :param n: number of buses
        :param m: number of branches
        :param nt: number of time steps
        :param time: Time array (optional)
        """
        self.n = n

        self.m = m

        self.nt = nt

        self.time = time

        self.voltage = zeros((nt, n), dtype=complex)

        self.load_shedding = zeros((nt, n), dtype=float)

        self.loading = zeros((nt, m), dtype=float)

        self.losses = zeros((nt, m), dtype=float)

        self.overloads = zeros((nt, m), dtype=float)

        self.Sbus = zeros((nt, n), dtype=complex)

        self.Sbranch = zeros((nt, m), dtype=complex)

        self.available_results = ['Bus voltage', 'Bus power', 'Branch power',
                                  'Branch loading', 'Branch overloads', 'Load shedding']

        # self.generators_power = zeros((ng, nt), dtype=complex)

        self.is_dc = is_dc

    def set_at(self, t, res: OptimalPowerFlowResults):
        """
        Set the results
        :param t: time index
        :param res: OptimalPowerFlowResults instance
        """

        self.voltage[t, :] = res.voltage

        self.load_shedding[t, :] = res.load_shedding

        self.loading[t, :] = res.loading

        self.overloads[t, :] = res.overloads

        self.losses[t, :] = res.losses

        self.Sbus[t, :] = res.Sbus

        self.Sbranch[t, :] = res.Sbranch

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

        if indices is None:
            indices = array(range(len(names)))

        if len(indices) > 0:
            labels = names[indices]
            y_label = ''
            title = ''
            if result_type == 'Bus voltage':

                if self.is_dc:
                    y = np.angle(self.voltage[:, indices])
                    y_label = '(rad)'
                    title = 'Bus voltage angle'
                else:
                    y = np.abs(self.voltage[:, indices])
                    y_label = '(p.u.)'
                    title = 'Bus voltage'

            elif result_type == 'Branch power':
                y = self.Sbranch[:, indices].real
                y_label = '(MW)'
                title = 'Branch power '

            elif result_type == 'Bus power':
                y = self.Sbus[:, indices].real
                y_label = '(MW)'
                title = 'Bus power '

            elif result_type == 'Branch loading':
                y = np.abs(self.loading[:, indices] * 100.0)
                y_label = '(%)'
                title = 'Branch loading '

            elif result_type == 'Branch overloads':
                y = np.abs(self.overloads[:, indices])
                y_label = '(MW)'
                title = 'Branch overloads '

            elif result_type == 'Branch losses':
                y = self.losses[:, indices].real
                y_label = '(MW)'
                title = 'Branch losses '

            elif result_type == 'Load shedding':
                y = self.load_shedding[:, indices]
                y_label = '(MW)'
                title = 'Load shedding'

            else:
                pass

            if self.time is not None:
                df = pd.DataFrame(data=y, columns=labels, index=self.time)
            else:
                df = pd.DataFrame(data=y, columns=labels)

            df.fillna(0, inplace=True)

            if len(df.columns) > 10:
                df.plot(ax=ax, linewidth=LINEWIDTH, legend=False)
            else:
                df.plot(ax=ax, linewidth=LINEWIDTH, legend=True)

            ax.set_title(title)
            ax.set_ylabel(y_label)
            ax.set_xlabel('Time')

            return df

        else:
            return None


class OptimalPowerFlowTimeSeries(QThread):
    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: OptimalPowerFlowOptions, start_=0, end_=None):
        """
        OPF time series constructor
        :param grid: MultiCircuit instance
        :param options: OPF options instance
        """
        QThread.__init__(self)

        self.options = options

        self.grid = grid

        self.results = None

        self.start_ = start_

        self.end_ = end_

        self.__cancel__ = False

    def initialize_lp_vars(self):
        """
        initialize all the bus LP profiles
        :return:
        """
        for bus in self.grid.buses:
            bus.initialize_lp_profiles()

    def run(self):
        """
        Run the time series simulation
        @return:
        """
        # initialize the power flow
        opf = OptimalPowerFlow(self.grid, self.options)

        # initilize OPF time series LP var profiles
        self.initialize_lp_vars()

        # initialize the grid time series results
        # we will append the island results with another function

        if self.grid.time_profile is not None:

            if self.options.solver == SolverType.DC_OPF:
                self.progress_text.emit('Running DC OPF time series...')
                is_dc = True
            else:
                self.progress_text.emit('Running AC OPF time series...')
                is_dc = False

            n = len(self.grid.buses)
            m = len(self.grid.branches)
            nt = len(self.grid.time_profile)
            if self.end_ is None:
                self.end_ = nt
            self.results = OptimalPowerFlowTimeSeriesResults(n, m, nt, time=self.grid.time_profile, is_dc=is_dc)

            t = self.start_
            while t < self.end_ and not self.__cancel__:
                # print(t + 1, ' / ', nt)
                # set the power values
                # Y, I, S = self.grid.time_series_input.get_at(t)

                res = opf.run_at(t)
                self.results.set_at(t, res)

                progress = ((t - self.start_ + 1) / (self.end_ - self.start_)) * 100
                self.progress_signal.emit(progress)
                t += 1

        else:
            print('There are no profiles')
            self.progress_text.emit('There are no profiles')

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        """
        Set the cancel state
        """
        self.__cancel__ = True


########################################################################################################################
# State Estimation classes
########################################################################################################################

class StateEstimationInput:

    def __init__(self):
        """
        State estimation inputs constructor
        """

        # Node active power measurements vector of pointers
        self.p_inj =list()

        # Node  reactive power measurements vector of pointers
        self.q_inj = list()

        # Branch active power measurements vector of pointers
        self.p_flow = list()

        # Branch reactive power measurements vector of pointers
        self.q_flow = list()

        # Branch current module measurements vector of pointers
        self.i_flow = list()

        # Node voltage module measurements vector of pointers
        self.vm_m = list()

        # nodes without power injection measurements
        self.p_inj_idx = list()

        # branches without power measurements
        self.p_flow_idx = list()

        # nodes without reactive power injection measurements
        self.q_inj_idx = list()

        # branches without reactive power measurements
        self.q_flow_idx = list()

        # branches without current measurements
        self.i_flow_idx = list()

        # nodes without voltage module measurements
        self.vm_m_idx = list()

    def clear(self):
        """
        Clear
        """
        self.p_inj.clear()
        self.p_flow.clear()
        self.q_inj.clear()
        self.q_flow.clear()
        self.i_flow.clear()
        self.vm_m.clear()

        self.p_inj_idx.clear()
        self.p_flow_idx.clear()
        self.q_inj_idx.clear()
        self.q_flow_idx.clear()
        self.i_flow_idx.clear()
        self.vm_m_idx.clear()

    def consolidate(self):
        """
        consolidate the measurements into "measurements" and "sigma"
        :return: measurements, sigma
        """

        nz = len(self.p_inj) + len(self.p_flow) + len(self.q_inj) + len(self.q_flow) + len(self.i_flow) + len(self.vm_m)

        magnitudes = np.zeros(nz)
        sigma = np.zeros(nz)

        # go through the measurements in order and form the vectors
        k = 0
        for m in self.p_flow + self.p_inj + self.q_flow + self.q_inj + self.i_flow + self.vm_m:
            magnitudes[k] = m.val
            sigma[k] = m.sigma
            k += 1

        return magnitudes, sigma


class StateEstimationResults(PowerFlowResults):

    def __init__(self, Sbus=None, voltage=None, Sbranch=None, Ibranch=None, loading=None, losses=None,
                 error=None, converged=None, Qpv=None):
        """
        Constructor
        :param Sbus: Bus power injections
        :param voltage: Bus voltages
        :param Sbranch: Branch power flow
        :param Ibranch: Branch current flow
        :param loading: Branch loading
        :param losses: Branch losses
        :param error: error
        :param converged: converged?
        :param Qpv: Reactive power at the PV nodes
        """
        # initialize the
        PowerFlowResults.__init__(self, Sbus=Sbus, voltage=voltage, Sbranch=Sbranch, Ibranch=Ibranch,
                                  loading=loading, losses=losses, error=error, converged=converged, Qpv=Qpv)


class StateEstimation(QRunnable):

    def __init__(self, circuit: MultiCircuit):
        """
        Constructor
        :param circuit: circuit object 
        """

        QRunnable.__init__(self)

        self.grid = circuit

        self.se_results = None

    @staticmethod
    def collect_measurements(circuit: Circuit):
        """
        Form the input from the circuit measurements
        :return: nothing, the input object is stored in this class
        """
        se_input = StateEstimationInput()

        # collect the bus measurements
        for i, bus in enumerate(circuit.buses):

            for m in bus.measurements:

                if m.measurement_type == MeasurementType.Pinj:
                    se_input.p_inj_idx.append(i)
                    se_input.p_inj.append(m)

                elif m.measurement_type == MeasurementType.Qinj:
                    se_input.q_inj_idx.append(i)
                    se_input.q_inj.append(m)

                elif m.measurement_type == MeasurementType.Vmag:
                    se_input.vm_m_idx.append(i)
                    se_input.vm_m.append(m)

                else:
                    raise Exception('The bus ' + str(bus) + ' contains a measurement of type ' + str(m.measurement_type))

        # collect the branch measurements
        for i, branch in enumerate(circuit.branches):

            for m in branch.measurements:

                if m.measurement_type == MeasurementType.Pflow:
                    se_input.p_flow_idx.append(i)
                    se_input.p_flow.append(m)

                elif m.measurement_type == MeasurementType.Qflow:
                    se_input.q_flow_idx.append(i)
                    se_input.q_flow.append(m)

                elif m.measurement_type == MeasurementType.Iflow:
                    se_input.i_flow_idx.append(i)
                    se_input.i_flow.append(m)

                else:
                    raise Exception(
                        'The branch ' + str(branch) + ' contains a measurement of type ' + str(m.measurement_type))

        return se_input

    def run(self):
        """
        Run state estimation
        :return: 
        """
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        self.se_results = StateEstimationResults()
        self.se_results.initialize(n, m)

        for circuit in self.grid.circuits:

            # collect inputs
            se_input = self.collect_measurements(circuit=circuit)

            # run solver
            v_sol, err, converged = solve_se_lm(Ybus=circuit.power_flow_input.Ybus,
                                                Yf=circuit.power_flow_input.Yf,
                                                Yt=circuit.power_flow_input.Yt,
                                                f=circuit.power_flow_input.F,
                                                t=circuit.power_flow_input.T,
                                                se_input=se_input,
                                                ref=circuit.power_flow_input.ref,
                                                pq=circuit.power_flow_input.pq,
                                                pv=circuit.power_flow_input.pv)

            # Compute the branches power and the slack buses power
            Sbranch, Ibranch, loading, losses, Sbus = PowerFlowMP.power_flow_post_process(circuit=circuit, V=v_sol)

            # pack results into a SE results object
            results = StateEstimationResults(Sbus=Sbus,
                                             voltage=v_sol,
                                             Sbranch=Sbranch,
                                             Ibranch=Ibranch,
                                             loading=loading,
                                             losses=losses,
                                             error=[err],
                                             converged=[converged],
                                             Qpv=None)

            self.se_results.apply_from_island(results, circuit.bus_original_idx, circuit.branch_original_idx)


########################################################################################################################
# Transient stability
########################################################################################################################


class TransientStabilityOptions:

    def __init__(self, h=0.001, t_sim=15, max_err=0.0001, max_iter=25):

        # step length (s)
        self.h = h

        # simulation time (s)
        self.t_sim = t_sim

        # Maximum error in network iteration (voltage mismatches)
        self.max_err = max_err

        # Maximum number of network iterations
        self.max_iter = max_iter


class TransientStability(QThread):
    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: TransientStabilityOptions, pf_res: PowerFlowResults):
        """
        TimeSeries constructor
        @param grid: MultiCircuit instance
        @param options: PowerFlowOptions instance
        """
        QThread.__init__(self)

        self.grid = grid

        self.options = options

        self.pf_res = pf_res

        self.results = None

    def status(self, txt, progress):
        """
        Emit status
        :param txt: text to display
        :param progress: progress 0-100
        """
        self.progress_signal.emit(progress)
        self.progress_text.emit(txt)

    def run(self):
        """
        Run transient stability
        """
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Running transient stability...')

        for circuit in self.grid.circuits:
            dynamic_devices = circuit.get_controlled_generators()
            bus_indices = [circuit.buses_dict[elm.bus] for elm in dynamic_devices]

            res = dynamic_simulation(n=len(circuit.buses),
                                     Vbus=self.pf_res.voltage[circuit.bus_original_idx],
                                     Sbus=self.pf_res.Sbus[circuit.bus_original_idx],
                                     Ybus=circuit.power_flow_input.Ybus,
                                     Sbase=circuit.Sbase,
                                     fBase=circuit.fBase,
                                     t_sim=self.options.t_sim,
                                     h=self.options.h,
                                     dynamic_devices=dynamic_devices,
                                     bus_indices=bus_indices,
                                     callback=self.status)

        self.results = res

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()
