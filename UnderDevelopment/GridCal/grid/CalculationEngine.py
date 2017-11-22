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

__GridCal_VERSION__ = 1.76

from GridCal.grid.JacobianBased import IwamotoNR, Jacobian, LevenbergMarquardtPF
from GridCal.grid.FastDecoupled import FDPF
from GridCal.grid.ContinuationPowerFlow import continuation_nr
from GridCal.grid.HelmVect import helm
from GridCal.grid.DCPF import dcpf
from GridCal.grid.SC import short_circuit_3p

import os
from enum import Enum
from warnings import warn
import json
import networkx as nx
import pandas as pd
import pickle as pkl
from datetime import datetime, timedelta
from PyQt5.QtCore import QThread, QRunnable, pyqtSignal
from matplotlib import pyplot as plt
from networkx import connected_components
from numpy import complex, double, sqrt, zeros, ones, nan_to_num, exp, conj, ndarray, vstack, power, delete, angle, \
    where, r_, Inf, linalg, maximum, array, random, nan, shape, arange, sort, interp, iscomplexobj, c_, argwhere, floor
from scipy.sparse import csc_matrix as sparse
from scipy.sparse.linalg import inv
from pyDOE import lhs
from pySOT import *
from poap.controller import ThreadController, BasicWorkerThread, SerialController
from sklearn.neural_network import MLPRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestRegressor
from sklearn.tree import DecisionTreeRegressor
from sklearn.linear_model import LinearRegression

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
    Inverse Cumulative density function of a given array f data
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
        l = len(data)
        if l > 1:
            self.prob = 1. * arange(l) / (l - 1)
        else:
            self.prob = 1. * arange(l)

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
        Rest of two CDF
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

            else:
                # just pick the DataFrame
                df = xl.parse(name, index_col=0)
                data[name] = df

    return data


########################################################################################################################
# Circuit classes
########################################################################################################################


class Bus:

    def __init__(self, name="Bus", vnom=10, vmin=0.9, vmax=1.1, xpos=0, ypos=0, active=True):
        """
        Bus  constructor
        """

        self.name = name

        self.type_name = 'Bus'

        self.properties_with_profile = None

        # Nominal voltage (kV)
        self.Vnom = vnom

        self.Vmin = vmin

        self.Vmax = vmax

        self.Qmin_sum = 0

        self.Qmax_sum = 0

        self.Zf = 0

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

        # Bus type
        self.type = NodeType.NONE

        # Flag to determine if the bus is a slack bus or not
        self.is_slack = False

        # if true, the presence of storage devices turn the bus into a Reference bus in practice
        # So that P +jQ are computed
        self.dispatch_storage = False

        self.x = xpos

        self.y = ypos

        self.graphic_obj = None

        self.edit_headers = ['name', 'active', 'is_slack', 'Vnom', 'Vmin', 'Vmax', 'Zf', 'x', 'y']

        self.units = ['', '', '', 'kV', 'p.u.', 'p.u.', 'p.u.', '', '']

        self.edit_types = {'name': str,
                           'active': bool,
                           'is_slack': bool,
                           'Vnom': float,
                           'Vmin': float,
                           'Vmax': float,
                           'Zf': complex,
                           'x': float,
                           'y': float}

    def determine_bus_type(self):
        """
        Infer the bus type from the devices attached to it
        @return: Nothing
        """
        if len(self.controlled_generators) > 0:

            if self.is_slack:  # If contains generators and is marked as REF, then set it as REF
                self.type = NodeType.REF
            else:  # Otherwise set as PV
                self.type = NodeType.PV

        elif len(self.batteries) > 0:

            if self.dispatch_storage:
                # If there are storage devices and the dispatchable flag is on, set the bus as dispatchable
                self.type = NodeType.STO_DISPATCH
            else:
                # Otherwise a storage device shall be marked as a voltage controlld bus
                self.type = NodeType.PV
        else:
            if self.is_slack:  # If there is no device but still is marked as REF, then set as REF
                self.type = NodeType.REF
            else:
                # Nothing special; set it as PQ
                self.type = NodeType.PQ

    def get_YISV(self, index=None):
        """
        Compose the
            - Z: Impedance attached to the bus
            - I: Current attached to the bus
            - S: Power attached to the bus
            - V: Voltage of the bus
        All in complex values
        @return: Y, I, S, V, Yprof, Iprof, Sprof
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

        self.Qmin_sum = 0
        self.Qmax_sum = 0

        is_v_controlled = False

        # Loads
        for elm in self.loads:

            if elm.active:

                if elm.Z != 0:
                    Y += 1 / elm.Z
                I -= elm.I  # Reverse sign convention in the load
                S -= elm.S  # Reverse sign convention in the load

                # Add the profiles
                elm_s_prof, elm_i_prof, elm_z_prof = elm.get_profiles(index)
                if elm_z_prof is not None:
                    if elm_z_prof.values.sum(axis=0) != complex(0):
                        if y_profile is None:
                            y_profile = 1 / elm_z_prof
                            y_cdf = CDF(y_profile)
                        else:
                            pr = 1 / elm_z_prof
                            y_profile = y_profile.add(pr, fill_value=0)
                            y_cdf = y_cdf + CDF(pr)

                if elm_i_prof is not None:
                    if elm_i_prof.values.sum(axis=0) != complex(0):
                        if i_profile is None:
                            i_profile = -elm_i_prof  # Reverse sign convention in the load
                            i_cdf = CDF(i_profile)
                        else:
                            pr = -elm_i_prof
                            i_profile = i_profile.add(pr, fill_value=0)  # Reverse sign convention in the load
                            i_cdf = i_cdf + CDF(pr)

                if elm_s_prof is not None:
                    if elm_s_prof.values.sum(axis=0) != complex(0):
                        if s_profile is None:
                            s_profile = -elm_s_prof  # Reverse sign convention in the load
                            s_cdf = CDF(s_profile)
                        else:
                            pr = -elm_s_prof
                            s_profile = s_profile.add(pr, fill_value=0)  # Reverse sign convention in the load
                            s_cdf = s_cdf + CDF(pr)
            else:
                warn(elm.name + ' is not active')

        # controlled gen and batteries
        for elm in self.controlled_generators + self.batteries:

            if elm.active:
                # Add the generator active power
                S = complex(S.real + elm.P, S.imag)

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
                elm_p_prof, elm_vset_prof = elm.get_profiles(index)
                if elm_p_prof is not None:
                    if s_profile is None:
                        s_profile = elm_p_prof  # Reverse sign convention in the load
                        s_cdf = CDF(s_profile)
                    else:
                        s_profile = s_profile.add(elm_p_prof, fill_value=0)
                        s_cdf = s_cdf + CDF(elm_p_prof)
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
            else:
                warn(elm.name + ' is not active')

        # Static generators
        for elm in self.static_generators:

            if elm.active:
                S += elm.S

                if elm.Sprof is not None:
                    if s_profile is None:
                        s_profile = elm.Sprof  # Reverse sign convention in the load
                        s_cdf = CDF(s_profile)
                    else:
                        s_profile = s_profile.add(elm.Sprof, fill_value=0)
                        s_cdf = s_cdf + CDF(elm.Pprof)
            else:
                warn(elm.name + ' is not active')

        # Align profiles into a common column sum based on the time axis
        if s_profile is not None:
            s_profile = s_profile.sum(axis=1)

        if i_profile is not None:
            i_profile = i_profile.sum(axis=1)

        if y_profile is not None:
            y_profile = y_profile.sum(axis=1)

        return Y, I, S, V, y_profile, i_profile, s_profile, y_cdf, i_cdf, s_cdf

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

        # self.graphic_obj = None

        return bus

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        self.retrieve_graphic_position()
        return [self.name, self.active, self.is_slack, self.Vnom, self.Vmin, self.Vmax, self.Zf, self.x, self.y]

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
        Uhv = self.HV_nominal_voltage

        Ulv = self.LV_nominal_voltage

        Sn = self.Nominal_power

        Pcu = self.Copper_losses

        Pfe = self.Iron_losses

        I0 = self.No_load_current

        Usc = self.Short_circuit_voltage

        # Nominal impedance HV (Ohm)
        Zn_hv = Uhv * Uhv / Sn

        # Nominal impedance LV (Ohm)
        Zn_lv = Ulv * Ulv / Sn

        # Short circuit impedance (p.u.)
        zsc = Usc / 100

        # Short circuit resistance (p.u.)
        rsc = (Pcu / 1000) / Sn

        # Short circuit reactance (p.u.)
        xsc = sqrt(zsc * zsc - rsc * rsc)

        # HV resistance (p.u.)
        rcu_hv = rsc * self.GR_hv1

        # LV resistance (p.u.)
        rcu_lv = rsc * (1 - self.GR_hv1)

        # HV shunt reactance (p.u.)
        xs_hv = xsc * self.GX_hv1

        # LV shunt reactance (p.u.)
        xs_lv = xsc * (1 - self.GX_hv1)

        # Shunt resistance (p.u.)
        rfe = Sn / (Pfe / 1000)

        # Magnetization impedance (p.u.)
        zm = 1 / (I0 / 100)

        # Magnetization reactance (p.u.)
        if rfe > zm:
            xm = 1 / sqrt(1 / (zm * zm) - 1 / (rfe * rfe))
        else:
            xm = 0  # the square root cannot be computed

        # Calculated parameters in per unit
        leakage_impedance = rsc + 1j * xsc
        magnetizing_impedance = rfe + 1j * xm

        return leakage_impedance, magnetizing_impedance


class Branch:

    def __init__(self, bus_from: Bus, bus_to: Bus, name='Branch', r=1e-20, x=1e-20, g=1e-20, b=1e-20,
                 rate=1, tap=1, shift_angle=0, active=True, mttf=0, mttr=0):
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
        """

        self.name = name

        self.type_name = 'Branch'

        self.properties_with_profile = None

        self.bus_from = bus_from
        self.bus_to = bus_to

        self.active = active

        # self.z_series = zserie  # R + jX
        # self.y_shunt = yshunt  # G + jB

        self.R = r
        self.X = x
        self.G = g
        self.B = b

        if tap != 0:
            self.tap_module = tap
        else:
            self.tap_module = 1

        self.angle = shift_angle

        self.rate = rate

        self.mttf = mttf

        self.mttr = mttr

        self.type_obj = None

        self.edit_headers = ['name', 'bus_from', 'bus_to', 'active', 'rate', 'mttf', 'mttr', 'R', 'X', 'G', 'B',
                             'tap_module', 'angle']

        self.units = ['', '', '', '', 'MVA', 'h', 'h', 'p.u.', 'p.u.', 'p.u.', 'p.u.',
                      'p.u.', 'rad']

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
                           'angle': float}

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
                   mttr=self.mttr)

        return b

    def get_tap(self):
        """
        Get the complex tap value
        @return:
        """
        return self.tap_module * exp(-1j * self.angle)

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
        tap = self.get_tap()
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

        # Y shunt for HELM
        Yshunt[f] += Yff_sh
        Yshunt[t] += Ytt_sh

        # Y series for HELM
        Yseries[f, f] += Ys / (tap * conj(tap))
        Yseries[f, t] += Yft
        Yseries[t, f] += Ytf
        Yseries[t, t] += Ys

        # B1 for FDPF (no shunts, no resistance, no tap module)
        z_series = complex(0, self.X)
        y_shunt = complex(0, 0)
        tap = exp(-1j * self.angle)  # self.tap_module * exp(-1j * self.angle)
        Ysh = y_shunt / 2
        Ys = 1 / z_series

        Ytt = Ys + Ysh
        Yff = Ytt / (tap * conj(tap))
        Yft = - Ys / conj(tap)
        Ytf = - Ys / tap

        B1[f, f] -= Yff.imag
        B1[f, t] -= Yft.imag
        B1[t, f] -= Ytf.imag
        B1[t, t] -= Ytt.imag

        # B2 for FDPF (with shunts, only the tap module)
        z_series = complex(self.R, self.X)
        y_shunt = complex(self.G, self.B)
        tap = self.tap_module  # self.tap_module * exp(-1j * self.angle)
        Ysh = y_shunt / 2
        Ys = 1 / z_series

        Ytt = Ys + Ysh
        Yff = Ytt / (tap * conj(tap))
        Yft = - Ys / conj(tap)
        Ytf = - Ys / tap

        B2[f, f] -= Yff.imag
        B2[f, t] -= Yft.imag
        B2[t, f] -= Ytf.imag
        B2[t, t] -= Ytt.imag

        return f, t

    def apply_transformer_type(self, obj: TransformerType):
        """
        Apply a transformer type definition to this object
        Args:
            obj:

        Returns:

        """
        leakage_impedance, magnetizing_impedance = obj.get_impedances()

        z_series = magnetizing_impedance
        y_shunt = 1 / leakage_impedance

        self.R = z_series.real
        self.X = z_series.imag
        self.G = y_shunt.real
        self.B = y_shunt.imag

        self.type_obj = obj

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        return [self.name, self.bus_from.name, self.bus_to.name, self.active, self.rate, self.mttf, self.mttr,
                self.R, self.X, self.G, self.B, self.tap_module, self.angle]


class Load:

    def __init__(self, name='Load', impedance=complex(0, 0), current=complex(0, 0), power=complex(0, 0),
                 impedance_prof=None, current_prof=None, power_prof=None, active=True):
        """
        Load model constructor
        This model implements the so-called ZIP model
        composed of an impedance value, a current value and a power value
        @param impedance: Impedance complex (Ohm)
        @param current: Current complex (kA)
        @param power: Power complex (MVA)
        """

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

        self.edit_headers = ['name', 'bus', 'active', 'Z', 'I', 'S']

        self.units = ['', '', '', 'MVA', 'MVA', 'MVA']  # ['', '', 'Ohm', 'kA', 'MVA']

        self.edit_types = {'name': str,
                           'bus': None,
                           'active': bool,
                           'Z': complex,
                           'I': complex,
                           'S': complex}

    def create_profiles(self, index):
        """
        Create the load object default profiles
        Args:
            index:
            steps:

        Returns:

        """

        self.create_S_profile(index)
        self.create_I_profile(index)
        self.create_Z_profile(index)

    def create_S_profile(self, index):
        """
        Create power profile based on index
        Args:
            index:

        Returns:

        """
        steps = len(index)
        self.Sprof = pd.DataFrame(data=ones(steps), index=index, columns=[self.name]) * self.S

    def create_I_profile(self, index):
        """
        Create current profile based on index
        Args:
            index:

        Returns:

        """
        steps = len(index)
        self.Iprof = pd.DataFrame(data=ones(steps), index=index, columns=[self.name]) * self.I

    def create_Z_profile(self, index):
        """
        Create impedance profile based on index
        Args:
            index:

        Returns:

        """
        steps = len(index)
        self.Zprof = pd.DataFrame(data=ones(steps), index=index, columns=[self.name]) * self.Z

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

        return load

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        return [self.name, self.bus.name, str(self.Z), str(self.I), str(self.S)]


class StaticGenerator:

    def __init__(self, name='StaticGen', power=complex(0, 0), power_prof=None, active=True):
        """

        @param power:
        """

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

        self.edit_headers = ['name', 'bus', 'active', 'S']

        self.units = ['', '', '', 'MVA']

        self.edit_types = {'name': str,
                           'bus': None,
                           'active': bool,
                           'S': complex}

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
        return [self.name, self.bus.name, str(self.S)]

    def create_profiles(self, index):
        """
        Create the load object default profiles
        Args:
            index:
            steps:

        Returns:

        """
        self.create_S_profile(index)

    def create_S_profile(self, index):
        """
        Create power profile based on index
        Args:
            index:

        Returns:

        """
        steps = len(index)
        self.Sprof = pd.DataFrame(data=ones(steps), index=index, columns=[self.name]) * self.S

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


class Battery:

    def __init__(self, name='batt', active_power=0.0, voltage_module=1.0, Qmin=-9999, Qmax=9999, Snom=9999, Enom=9999,
                 power_prof=None, vset_prof=None, active=True):
        """
        Batery (Voltage controlled and dispatchable)
        @param name:
        @param active_power:
        @param voltage_module:
        @param Qmin:
        @param Qmax:
        @param Snom:
        @param Enom:
        @param power_prof:
        @param vset_prof:
        @param active:
        """

        self.name = name

        self.active = active

        self.type_name = 'Battery'

        self.properties_with_profile = (['P', 'Vset'], [float, float])

        self.graphic_obj = None

        # The bus this element is attached to: Not necessary for calculations
        self.bus = None

        # Power (MVA)
        # MVA = kV * kA
        self.P = active_power

        # power profile for this load
        self.Pprof = power_prof

        # Voltage module set point (p.u.)
        self.Vset = voltage_module

        # voltage set profile for this load
        self.Vsetprof = vset_prof

        # minimum reactive power in per unit
        self.Qmin = Qmin

        # Maximum reactive power in per unit
        self.Qmax = Qmax

        # Nominal power MVA
        self.Snom = Snom

        # Nominal energy MWh
        self.Enom = Enom

        self.edit_headers = ['name', 'bus', 'active', 'P', 'Vset', 'Snom', 'Enom', 'Qmin', 'Qmax']

        self.units = ['', '', '', 'MW', 'p.u.', 'MVA', 'kV', 'p.u.', 'p.u.']

        self.edit_types = {'name': str,
                           'bus': None,
                           'active': bool,
                           'P': float,
                           'Vset': float,
                           'Snom': float,
                           'Enom': float,
                           'Qmin': float,
                           'Qmax': float}

    def copy(self):

        batt = Battery()

        batt.name = self.name

        # Power (MVA)
        # MVA = kV * kA
        batt.P = self.P

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

        return batt

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        return [self.name, self.bus.name, self.P, self.Vset, self.Snom, self.Enom, self.Qmin, self.Qmax]

    def create_profiles(self, index):
        """
        Create the load object default profiles
        Args:
            index:
            steps:

        Returns:

        """
        self.create_P_profile(index)

        self.create_Vset_profile(index)

    def create_P_profile(self, index):
        """
        Create power profile based on index
        Args:
            index:

        Returns:

        """
        steps = len(index)
        self.Pprof = pd.DataFrame(data=ones(steps), index=index, columns=[self.name]) * self.P

    def create_Vset_profile(self, index):
        """
        Create power profile based on index
        Args:
            index:

        Returns:

        """
        steps = len(index)
        self.Vsetprof = pd.DataFrame(data=ones(steps), index=index, columns=[self.name]) * self.Vset

    def get_profiles(self, index=None):
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
                self.create_vset_profile(index)
        return self.Pprof, self.Vsetprof


class ControlledGenerator:

    def __init__(self, name='gen', active_power=0.0, voltage_module=1.0, Qmin=-9999, Qmax=9999, Snom=9999,
                 power_prof=None, vset_prof=None, active=True):
        """
        Voltage controlled generator
        @param name:
        @param active_power: Active power (MW)
        @param voltage_module: Voltage set point (p.u.)
        @param Qmin:
        @param Qmax:
        @param Snom:
        @param power_prof:
        @param vset_prof
        @param active
        """

        self.name = name

        self.active = active

        self.type_name = 'ControlledGenerator'

        self.graphic_obj = None

        self.properties_with_profile = (['P', 'Vset'], [float, float])

        # The bus this element is attached to: Not necessary for calculations
        self.bus = None

        # Power (MVA)
        # MVA = kV * kA
        self.P = active_power

        # power profile for this load
        self.Pprof = power_prof

        # Voltage module set point (p.u.)
        self.Vset = voltage_module

        # voltage set profile for this load
        self.Vsetprof = vset_prof

        # minimum reactive power in per unit
        self.Qmin = Qmin

        # Maximum reactive power in per unit
        self.Qmax = Qmax

        # Nominal power
        self.Snom = Snom

        self.edit_headers = ['name', 'bus', 'active', 'P', 'Vset', 'Snom', 'Qmin', 'Qmax']

        self.units = ['', '', '', 'MW', 'p.u.', 'MVA', 'p.u.', 'p.u.']

        self.edit_types = {'name': str,
                           'bus': None,
                           'active': bool,
                           'P': float,
                           'Vset': float,
                           'Snom': float,
                           'Qmin': float,
                           'Qmax': float}

    def copy(self):

        gen = ControlledGenerator()

        gen.name = self.name

        # Power (MVA)
        # MVA = kV * kA
        gen.P = self.P

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

        return gen

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        return [self.name, self.bus.name, self.P, self.Vset, self.Snom, self.Qmin, self.Qmax]

    def create_profiles(self, index):
        """
        Create the load object default profiles
        Args:
            index:
            steps:

        Returns:

        """
        self.create_P_profile(index)

        self.create_Vset_profile(index)

    def create_P_profile(self, index):
        """
        Create power profile based on index
        Args:
            index:

        Returns:

        """
        steps = len(index)
        self.Pprof = pd.DataFrame(data=ones(steps), index=index, columns=[self.name]) * self.P

    def create_Vset_profile(self, index):
        """
        Create power profile based on index
        Args:
            index:

        Returns:

        """
        steps = len(index)
        self.Vsetprof = pd.DataFrame(data=ones(steps), index=index, columns=[self.name]) * self.Vset

    def get_profiles(self, index=None):
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
                self.create_vset_profile(index)
        return self.Pprof, self.Vsetprof


class Shunt:

    def __init__(self, name='shunt', admittance=complex(0, 0), admittance_prof=None, active=True):
        """
        Shunt object
        Args:
            name:
            admittance: Admittance in MVA at 1 p.u. voltage
            admittance_prof: Admittance profile in MVA at 1 p.u. voltage
            active: Is active True or False
        """
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

        self.edit_headers = ['name', 'bus', 'active', 'Y']

        self.units = ['', '', '', 'MVA']  # MVA at 1 p.u.

        self.edit_types = {'name': str,
                           'active': bool,
                           'bus': None,
                           'Y': complex}

    def copy(self):

        shu = Shunt()

        shu.name = self.name

        # Impedance (Ohm)
        # Z * I = V -> Ohm * kA = kV
        shu.Y = self.Y

        # admittance profile
        shu.Yprof = self.Yprof

        return shu

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        return [self.name, self.bus.name, str(self.Y)]

    def create_profiles(self, index):
        """
        Create the load object default profiles
        Args:
            index:
            steps:

        Returns:

        """
        self.create_Y_profile(index)

    def create_Y_profile(self, index):
        """
        Create power profile based on index
        Args:
            index:

        Returns:

        """
        steps = len(index)
        self.Yprof = pd.DataFrame(data=ones(steps), index=index, columns=[self.name]) * self.Y

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


class Circuit:

    def __init__(self, name='Circuit'):
        """
        Circuit constructor
        @param name: Name of the circuit
        """

        self.name = name

        # Base power (MVA)
        self.Sbase = 100

        # Should be able to accept Branches, Lines and Transformers alike
        self.branches = list()

        # array of branch indices in the master circuit
        self.branch_original_idx = list()

        # Should accept buses
        self.buses = list()

        # array of bus indices in the master circuit
        self.bus_original_idx = list()

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

    def compile(self):
        """
        Compile the circuit into all the needed arrays:
            - Ybus matrix
            - Sbus vector
            - Vbus vector
            - etc...
        """
        n = len(self.buses)
        m = len(self.branches)

        self.graph = nx.Graph()

        # declare power flow results
        power_flow_input = PowerFlowInput(n, m)

        # time series inputs
        Sprofile = pd.DataFrame()
        Iprofile = pd.DataFrame()
        Yprofile = pd.DataFrame()
        Scdf_ = [None] * n
        Icdf_ = [None] * n
        Ycdf_ = [None] * n
        time_series_input = None
        monte_carlo_input = None

        are_cdfs = False

        # Dictionary that helps referencing the nodes
        buses_dict = dict()

        # declare the square root of 3 to do it only once
        sqrt3 = sqrt(3.0)

        # Compile the buses
        for i in range(n):

            # Add buses dictionary entry
            buses_dict[self.buses[i]] = i

            # set the name
            power_flow_input.bus_names[i] = self.buses[i].name

            # assign the nominal voltage value
            power_flow_input.Vnom[i] = self.buses[i].Vnom

            # Determine the bus type
            self.buses[i].determine_bus_type()

            # compute the bus magnitudes
            Y, I, S, V, Yprof, Iprof, Sprof, Ycdf, Icdf, Scdf = self.buses[i].get_YISV()
            power_flow_input.Vbus[i] = V  # set the bus voltages
            power_flow_input.Sbus[i] += S  # set the bus power
            power_flow_input.Ibus[i] += I  # set the bus currents

            power_flow_input.Ybus[i, i] += Y  # set the bus shunt impedance in per unit
            power_flow_input.Yshunt[i] += Y  # copy the shunt impedance

            power_flow_input.types[i] = self.buses[i].type.value[0]  # set type

            power_flow_input.Vmin[i] = self.buses[i].Vmin
            power_flow_input.Vmax[i] = self.buses[i].Vmax
            power_flow_input.Qmin[i] = self.buses[i].Qmin_sum
            power_flow_input.Qmax[i] = self.buses[i].Qmax_sum

            # compute the time series arrays  ##############################################

            # merge the individual profiles. The profiles are Pandas DataFrames
            # ttt, nnn = Sprof.shape
            if Sprof is not None:
                k = where(Sprof.values == nan)
                Sprofile = pd.concat([Sprofile, Sprof], axis=1)
            else:
                nn = len(Sprofile)
                Sprofile['Sprof@Bus' + str(i)] = pd.Series(ones(nn) * S, index=Sprofile.index)  # append column of zeros

            if Iprof is not None:
                Iprofile = pd.concat([Iprofile, Iprof], axis=1)
            else:
                Iprofile['Iprof@Bus' + str(i)] = pd.Series(ones(len(Iprofile)) * I, index=Iprofile.index)

            if Yprof is not None:
                Yprofile = pd.concat([Yprofile, Yprof], axis=1)
            else:
                Yprofile['Iprof@Bus' + str(i)] = pd.Series(ones(len(Yprofile)) * Y, index=Yprofile.index)

            # Store the CDF's form Monte Carlo ##############################################

            if Scdf is None and S != complex(0, 0):
                Scdf = CDF(array([S]))

            if Icdf is None and I != complex(0, 0):
                Icdf = CDF(array([I]))

            if Ycdf is None and Y != complex(0, 0):
                Ycdf = CDF(array([Y]))

            if Scdf is not None or Icdf is not None or Ycdf is not None:
                are_cdfs = True

            Scdf_[i] = Scdf
            Icdf_[i] = Icdf
            Ycdf_[i] = Ycdf

        # normalize the power array
        power_flow_input.Sbus /= self.Sbase

        # normalize the currents array (I was given in MVA at v=1 p.u.)
        power_flow_input.Ibus /= self.Sbase

        # normalize the admittances array (Y was given in MVA at v=1 p.u.)
        power_flow_input.Ybus /= self.Sbase
        power_flow_input.Yshunt /= self.Sbase

        # normalize the reactive power limits array (Q was given in MVAr)
        power_flow_input.Qmax /= self.Sbase
        power_flow_input.Qmin /= self.Sbase

        if Sprofile is not None:
            Sprofile /= self.Sbase
            Sprofile.columns = ['Sprof@Bus' + str(i) for i in range(Sprofile.shape[1])]

        if Iprofile is not None:
            Iprofile /= self.Sbase
            Iprofile.columns = ['Iprof@Bus' + str(i) for i in range(Iprofile.shape[1])]

        if Yprofile is not None:
            Yprofile /= self.Sbase
            Yprofile.columns = ['Yprof@Bus' + str(i) for i in range(Yprofile.shape[1])]

        time_series_input = TimeSeriesInput(Sprofile, Iprofile, Yprofile)
        time_series_input.compile()

        if are_cdfs:
            monte_carlo_input = MonteCarloInput(n, Scdf_, Icdf_, Ycdf_)

        # Compile the branches
        for i in range(m):

            if self.branches[i].active:
                # Set the branch impedance

                f = buses_dict[self.branches[i].bus_from]
                t = buses_dict[self.branches[i].bus_to]

                f, t = self.branches[i].apply_to(Ybus=power_flow_input.Ybus,
                                                 Yseries=power_flow_input.Yseries,
                                                 Yshunt=power_flow_input.Yshunt,
                                                 Yf=power_flow_input.Yf,
                                                 Yt=power_flow_input.Yt,
                                                 B1=power_flow_input.B1,
                                                 B2=power_flow_input.B2,
                                                 i=i, f=f, t=t)
                # add the bus shunts
                # power_flow_input.Yf[i, f] += power_flow_input.Yshunt[f, f]
                # power_flow_input.Yt[i, t] += power_flow_input.Yshunt[t, t]

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
        self.mc_time_series = self.monte_carlo_input(batch_size, use_latin_hypercube)

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


class MultiCircuit(Circuit):

    def __init__(self):
        """
        Multi Circuit Constructor
        """
        Circuit.__init__(self)

        self.name = 'Grid'

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

    def load_file(self, filename):
        """
        Load GridCal compatible file
        @param filename:
        @return:
        """
        if os.path.exists(filename):
            name, file_extension = os.path.splitext(filename)
            print(name, file_extension)
            if file_extension == '.xls' or file_extension == '.xlsx':
                ppc = load_from_xls(filename)

                # Pass the table-like data dictionary to objects in this circuit
                if 'version' not in ppc.keys():
                    from GridCal.grid.ImportParsers.matpower_parser import interpret_data_v1
                    interpret_data_v1(self, ppc)
                    return True
                elif ppc['version'] == 2.0:
                    self.interpret_data_v2(ppc)
                    return True
                else:
                    warn('The file could not be processed')
                    return False

            elif file_extension == '.dgs':
                from GridCal.grid.ImportParsers.DGS_Parser import dgs_to_circuit
                circ = dgs_to_circuit(filename)
                self.buses = circ.buses
                self.branches = circ.branches

            elif file_extension == '.m':
                from GridCal.grid.ImportParsers.matpower_parser import parse_matpower_file
                circ = parse_matpower_file(filename)
                self.buses = circ.buses
                self.branches = circ.branches

            elif file_extension in ['.raw', '.RAW', '.Raw']:
                from GridCal.grid.ImportParsers.PSS_Parser import PSSeParser
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
        print('Interpreting V2 data...')

        # clear all the data
        self.clear()

        self.name = data['name']

        # set the base magnitudes
        self.Sbase = data['baseMVA']

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
            obj = Branch(bus_from=bus_dict[bus_from[i]], bus_to=bus_dict[bus_to[i]])
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

            bus = bus_dict[bus_from[i]]

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
                obj.Pprof = pd.DataFrame(data=val, index=idx)

            if 'CtrlGen_Vset_profiles' in data.keys():
                val = data['CtrlGen_Vset_profiles'].values[:, i]
                idx = data['CtrlGen_Vset_profiles'].index
                obj.Vsetprof = pd.DataFrame(data=val, index=idx)

            bus = bus_dict[bus_from[i]]

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
                obj.Pprof = pd.DataFrame(data=val, index=idx)

            if 'battery_Vset_profiles' in data.keys():
                val = data['battery_Vset_profiles'].values[:, i]
                idx = data['battery_Vset_profiles'].index
                obj.Vsetprof = pd.DataFrame(data=val, index=idx)

            bus = bus_dict[bus_from[i]]

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

            bus = bus_dict[bus_from[i]]

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

            bus = bus_dict[bus_from[i]]

            if obj.name == 'shunt':
                obj.name += str(len(bus.shunts) + 1) + '@' + bus.name

            obj.bus = bus
            bus.shunts.append(obj)

        print('Done!')

        # ['branch', 'load_Zprof', 'version', 'CtrlGen_Vset_profiles', 'CtrlGen_P_profiles', 'basekA',
        #                   'baseMVA', 'load_Iprof', 'battery', 'load', 'bus', 'shunt', 'controlled_generator',
        #                   'load_Sprof', 'static_generator']

    def save_file(self, file_path):
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
            dfs['shunt_Y_profiles'] = pd.DataFrame(data=y_profiles, columns=hdr, index=T)

        # flush-save
        writer = pd.ExcelWriter(file_path)
        for key in dfs.keys():
            dfs[key].to_excel(writer, key)

        writer.save()

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

    def compile(self):
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

            circuit.compile()
            self.power_flow_input.set_from(circuit.power_flow_input,
                                           circuit.bus_original_idx,
                                           circuit.branch_original_idx)

            self.time_series_input.apply_from_island(circuit.time_series_input,
                                                     circuit.bus_original_idx,
                                                     circuit.branch_original_idx,
                                                     n, m)

            self.circuits.append(circuit)

            self.has_time_series = self.has_time_series and circuit.time_series_input.valid

            isl_idx += 1

        print(islands)

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
                 verbose=False, robust=False, initialize_with_existing_solution=True, dispatch_storage=True,
                 tolerance=1e-6, max_iter=25, control_q=True):
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

        self.dispatch_storage = dispatch_storage

        self.verbose = verbose

        self.robust = robust

        self.initialize_with_existing_solution = initialize_with_existing_solution

        self.dispatch_storage = dispatch_storage


class PowerFlowInput:

    def __init__(self, n, m):
        """
        Power Flow study input values
        @param n: Number of buses
        @param m: Number of branches
        """
        # Array of integer values representing the buses types
        self.types = zeros(n, dtype=int)

        self.ref = None

        self.pv = None

        self.pq = None

        self.sto = None

        self.pqpv = None

        # Branch admittance matrix with the from buses
        self.Yf = zeros((m, n), dtype=complex)

        # Branch admittance matrix with the to buses
        self.Yt = zeros((m, n), dtype=complex)

        # Array with the 'from' index of the from bus of each branch
        self.F = zeros(m, dtype=int)

        # Array with the 'to' index of the from bus of each branch
        self.T = zeros(m, dtype=int)

        # array to store a 1 for the active branches
        self.active_branches = zeros(m, dtype=int)

        # Full admittance matrix (will be converted to sparse)
        self.Ybus = zeros((n, n), dtype=complex)

        # Full impedance matrix (will be computed upon requirement ad the inverse of Ybus)
        self.Zbus = None

        # Admittance matrix of the series elements (will be converted to sparse)
        self.Yseries = zeros((n, n), dtype=complex)

        # Admittance matrix of the shunt elements (actually it is only the diagonal, so let's make it a vector)
        self.Yshunt = zeros(n, dtype=complex)

        # Jacobian matrix 1 for the fast-decoupled power flow
        self.B1 = zeros((n, n), dtype=double)

        # Jacobian matrix 2 for the fast-decoupled power flow
        self.B2 = zeros((n, n), dtype=double)

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
        self.Yf = sparse(self.Yf)
        self.Yt = sparse(self.Yt)
        self.Ybus = sparse(self.Ybus)
        self.Yseries = sparse(self.Yseries)
        self.B1 = sparse(self.B1)
        self.B2 = sparse(self.B2)
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

        if len(self.ref) == 0:
            if len(self.pv) == 0:
                warn('There are no slack nodes selected')
            else:  # select the first PV generator as the slack
                mx = max(self.Sbus)
                i = where(self.Sbus == mx)[0]
                print('Setting the bus ' + str(i) + ' as slack instead of pv')
                self.pv = delete(self.pv, i)
                self.ref = [i]
            self.ref = ndarray.flatten(array(self.ref))
        else:
            pass  # no problem :)

        self.pqpv = r_[self.pq, self.pv]
        self.pqpv.sort()

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

        self.overvoltage[b_idx] = results.overvoltage

        self.undervoltage[b_idx] = results.undervoltage

        self.Sbranch[br_idx] = results.Sbranch

        self.Ibranch[br_idx] = results.Ibranch

        self.loading[br_idx] = results.loading

        self.losses[br_idx] = results.losses

        self.overloads[br_idx] = results.overloads

        # if results.error > self.error:
        self.error.append(results.error)

        self.converged.append(results.converged)

        self.inner_iterations.append(results.inner_iterations)

        self.outer_iterations.append(results.outer_iterations)

        self.elapsed.append(results.elapsed)

        self.methods.append(results.methods)

        # self.converged = self.converged and results.converged

        if results.buses_useful_for_storage is not None:
            self.buses_useful_for_storage = b_idx[results.buses_useful_for_storage]

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

            else:
                pass

            df = pd.DataFrame(data=y, index=labels, columns=[result_type])
            if len(df.columns) < self.plot_bars_limit:
                df.plot(ax=ax, kind='bar')
            else:
                df.plot(ax=ax, legend=False, linewidth=LINEWIDTH)
            ax.set_ylabel(ylabel)
            ax.set_title(title)

            return df

        else:
            return None


class PowerFlow(QRunnable):
    # progress_signal = pyqtSignal(float)
    # progress_text = pyqtSignal(str)
    # done_signal = pyqtSignal()

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

        self.last_V = None

        self.__cancel__ = False

    @staticmethod
    def optimization(pv, circuit, Sbus, V, tol, maxiter, robust, verbose):
        """

        @param pv:
        @param circuit:
        @param Sbus:
        @param V:
        @param tol:
        @param maxiter:
        @param robust:
        @param verbose:
        @return:
        """
        from scipy.optimize import minimize

        def optimization_function(x, pv, circuit, Sbus, V, tol, maxiter, robust, verbose):
            # Set the voltage set points given by x
            V[pv] = ones(len(pv), dtype=complex) * x

            # run power flow: The voltage V is modified by reference
            V, converged, normF, Scalc = IwamotoNR(Ybus=circuit.power_flow_input.Ybus,
                                                   Sbus=Sbus,
                                                   V0=V,
                                                   pv=circuit.power_flow_input.pv,
                                                   pq=circuit.power_flow_input.pq,
                                                   tol=tol,
                                                   max_it=maxiter,
                                                   robust=robust)

            # calculate the reactive power mismatches
            n = len(Scalc)
            excess = zeros(n)
            Qgen = circuit.power_flow_input.Sbus.imag - Scalc.imag
            exceed_up = where(Qgen > circuit.power_flow_input.Qmax)[0]
            exceed_down = where(Qgen < circuit.power_flow_input.Qmin)[0]
            # exceed = r_[exceed_down, exceed_up]
            excess[exceed_up] = circuit.power_flow_input.Qmax[exceed_up] - Qgen[exceed_up]
            excess[exceed_down] = circuit.power_flow_input.Qmax[exceed_down] - Qgen[exceed_down]

            fev = sum(excess)
            if verbose:
                print('f:', fev, 'x:', x)
                print('\tQmin:', circuit.power_flow_input.Qmin[pv])
                print('\tQgen:', Qgen[pv])
                print('\tQmax:', circuit.power_flow_input.Qmax[pv])
            return fev

        x0 = ones(len(pv))  # starting solution for the iteration
        bounds = ones((len(pv), 2))
        bounds[:, 0] *= 0.7
        bounds[:, 1] *= 1.2

        args = (pv, circuit, Sbus, V, tol, maxiter, robust, verbose)  # extra arguments of the function after x
        method = 'SLSQP'  # 'Nelder-Mead', TNC, SLSQP
        tol = 0.001
        options = dict()
        options['disp'] = verbose
        options['maxiter'] = 1000

        res = minimize(fun=optimization_function, x0=x0, args=args, method=method, tol=tol,
                       bounds=bounds, options=options)

        # fval = res.fun
        # xsol = res.x
        norm = circuit.power_flow_input.mismatch(V, Sbus)
        return res.fun, norm

    def single_power_flow(self, circuit: Circuit):
        """
        Run a power flow simulation for a single circuit
        @param circuit:
        @return:
        """
        # print('Single grid PF')
        optimize = False

        # Initial magnitudes
        if self.options.initialize_with_existing_solution and self.last_V is not None:
            V = self.last_V[circuit.bus_original_idx]
        else:
            V = circuit.power_flow_input.Vbus
        Sbus = circuit.power_flow_input.Sbus
        original_types = circuit.power_flow_input.types.copy()

        any_control_issue = True  # guilty assumption...

        control_max_iter = 10

        inner_it = list()
        outer_it = 0
        elapsed = list()
        methods = list()
        it = list()
        el = list()

        while any_control_issue and outer_it < control_max_iter:

            if len(circuit.power_flow_input.ref) == 0:
                V = zeros(len(Sbus), dtype=complex)
                normF = 0
                Scalc = Sbus.copy()
                any_control_issue = False
                converged = True
            else:
                # type HELM
                if self.options.solver_type == SolverType.HELM:
                    methods.append(SolverType.HELM)
                    V, converged, normF, Scalc, it, el = helm(Y=circuit.power_flow_input.Ybus,
                                                              Ys=circuit.power_flow_input.Yseries,
                                                              Ysh=circuit.power_flow_input.Yshunt,
                                                              max_coefficient_count=30,
                                                              S=circuit.power_flow_input.Sbus,
                                                              voltage_set_points=V,
                                                              pq=circuit.power_flow_input.pq,
                                                              pv=circuit.power_flow_input.pv,
                                                              vd=circuit.power_flow_input.ref,
                                                              eps=self.options.tolerance)
                # type DC
                elif self.options.solver_type == SolverType.DC:
                    methods.append(SolverType.DC)
                    V, converged, normF, Scalc, it, el = dcpf(Ybus=circuit.power_flow_input.Ybus,
                                                              Sbus=Sbus,
                                                              Ibus=circuit.power_flow_input.Ibus,
                                                              V0=V,
                                                              ref=circuit.power_flow_input.ref,
                                                              pvpq=circuit.power_flow_input.pqpv,
                                                              pq=circuit.power_flow_input.pq,
                                                              pv=circuit.power_flow_input.pv)

                elif self.options.solver_type == SolverType.LM:
                    methods.append(SolverType.LM)
                    V, converged, normF, Scalc, it, el = LevenbergMarquardtPF(Ybus=circuit.power_flow_input.Ybus,
                                                                              Sbus=Sbus,
                                                                              V0=V,
                                                                              Ibus=circuit.power_flow_input.Ibus,
                                                                              pv=circuit.power_flow_input.pv,
                                                                              pq=circuit.power_flow_input.pq,
                                                                              tol=self.options.tolerance,
                                                                              max_it=self.options.max_iter)

                elif self.options.solver_type == SolverType.FASTDECOUPLED:
                    methods.append(SolverType.FASTDECOUPLED)
                    V, converged, normF, Scalc, it, el = FDPF(Vbus=circuit.power_flow_input.Vbus,
                                                              Sbus=circuit.power_flow_input.Sbus,
                                                              Ibus=circuit.power_flow_input.Ibus,
                                                              Ybus=circuit.power_flow_input.Ybus,
                                                              B1=circuit.power_flow_input.B1,
                                                              B2=circuit.power_flow_input.B2,
                                                              pq=circuit.power_flow_input.pq,
                                                              pv=circuit.power_flow_input.pv,
                                                              pqpv=circuit.power_flow_input.pqpv,
                                                              tol=self.options.tolerance,
                                                              max_it=self.options.max_iter)

                elif self.options.solver_type == SolverType.NR:
                    methods.append(SolverType.NR)
                    V, converged, normF, Scalc, it, el = IwamotoNR(Ybus=circuit.power_flow_input.Ybus,
                                                                   Sbus=Sbus,
                                                                   V0=V,
                                                                   Ibus=circuit.power_flow_input.Ibus,
                                                                   pv=circuit.power_flow_input.pv,
                                                                   pq=circuit.power_flow_input.pq,
                                                                   tol=self.options.tolerance,
                                                                   max_it=self.options.max_iter,
                                                                   robust=False)

                elif self.options.solver_type == SolverType.IWAMOTO:
                    methods.append(SolverType.IWAMOTO)
                    V, converged, normF, Scalc, it, el = IwamotoNR(Ybus=circuit.power_flow_input.Ybus,
                                                                   Sbus=Sbus,
                                                                   V0=V,
                                                                   Ibus=circuit.power_flow_input.Ibus,
                                                                   pv=circuit.power_flow_input.pv,
                                                                   pq=circuit.power_flow_input.pq,
                                                                   tol=self.options.tolerance,
                                                                   max_it=self.options.max_iter,
                                                                   robust=True)

                # for any other method, for now, do a NR Iwamoto
                else:
                    methods.append(SolverType.IWAMOTO)
                    V, converged, normF, Scalc, it, el = IwamotoNR(Ybus=circuit.power_flow_input.Ybus,
                                                                   Sbus=Sbus,
                                                                   V0=V,
                                                                   Ibus=circuit.power_flow_input.Ibus,
                                                                   pv=circuit.power_flow_input.pv,
                                                                   pq=circuit.power_flow_input.pq,
                                                                   tol=self.options.tolerance,
                                                                   max_it=self.options.max_iter,
                                                                   robust=self.options.robust)

                    if not converged:
                        # Try with HELM
                        methods.append(SolverType.HELM)
                        V, converged, normF, Scalc, it, el = helm(Y=circuit.power_flow_input.Ybus,
                                                                  Ys=circuit.power_flow_input.Yseries,
                                                                  Ysh=circuit.power_flow_input.Yshunt,
                                                                  max_coefficient_count=30,
                                                                  S=circuit.power_flow_input.Sbus,
                                                                  voltage_set_points=circuit.power_flow_input.Vbus,
                                                                  pq=circuit.power_flow_input.pq,
                                                                  pv=circuit.power_flow_input.pv,
                                                                  vd=circuit.power_flow_input.ref,
                                                                  eps=self.options.tolerance)
                        Vhelm = V.copy()

                        # Retry NR using the HELM solution as starting point
                        if not converged:
                            methods.append(SolverType.IWAMOTO)
                            V, converged, normF, Scalc, it, el = IwamotoNR(Ybus=circuit.power_flow_input.Ybus,
                                                                           Sbus=Sbus,
                                                                           V0=V,
                                                                           Ibus=circuit.power_flow_input.Ibus,
                                                                           pv=circuit.power_flow_input.pv,
                                                                           pq=circuit.power_flow_input.pq,
                                                                           tol=self.options.tolerance,
                                                                           max_it=self.options.max_iter,
                                                                           robust=self.options.robust)

                            # if it still did not converge, just use the helm voltage approximation
                            if not converged:
                                V = Vhelm

                # Check controls
                if self.options.control_Q:
                    Vnew, Qnew, types_new, any_control_issue = self.switch_logic(V=V,
                                                                                 Vset=abs(V),
                                                                                 Q=Scalc.imag,
                                                                                 Qmax=circuit.power_flow_input.Qmax,
                                                                                 Qmin=circuit.power_flow_input.Qmin,
                                                                                 types=circuit.power_flow_input.types,
                                                                                 original_types=original_types,
                                                                                 verbose=self.options.verbose)
                    if any_control_issue:
                        V = Vnew
                        Sbus = Sbus.real + 1j * Qnew
                        circuit.power_flow_input.compile_types(types_new)
                    else:
                        if self.options.verbose:
                            print('Controls Ok')
                else:
                    # did not check Q limits
                    any_control_issue = False

            # increment the inner iterations counter
            inner_it.append(it)

            # increment the outer control iterations counter
            outer_it += 1

            # add the time taken by the solver in this iteration
            elapsed.append(el)

        # revert the types to the original
        circuit.power_flow_input.compile_types(original_types)

        # Compute the branches power
        Sbranch, Ibranch, loading, losses = self.compute_branch_results(circuit=circuit, V=V)

        # voltage, Sbranch, loading, losses, error, converged, Qpv
        results = PowerFlowResults(Sbus=Sbus,
                                   voltage=V,
                                   Sbranch=Sbranch,
                                   Ibranch=Ibranch,
                                   loading=loading,
                                   losses=losses,
                                   error=normF,
                                   converged=bool(converged),
                                   Qpv=None,
                                   inner_it=inner_it,
                                   outer_it=outer_it,
                                   elapsed=elapsed,
                                   methods=methods)

        # # check the limits
        # sum_dev = results.check_limits(circuit.power_flow_input)
        # print('dev sum: ', sum_dev)

        return results

    @staticmethod
    def compute_branch_results(circuit: Circuit, V):
        """
        Compute the power flows trough the branches
        @param circuit: instance of Circuit
        @param V: Voltage solution array for the circuit buses
        @return: Sbranch (MVA), Ibranch (p.u.), loading (p.u.), losses (MVA)
        """
        If = circuit.power_flow_input.Yf * V
        It = circuit.power_flow_input.Yt * V
        Sf = V[circuit.power_flow_input.F] * conj(If)
        St = V[circuit.power_flow_input.T] * conj(It)
        losses = (Sf + St) * circuit.Sbase  # Branch losses in MVA
        Ibranch = maximum(If, It)  # Branch current in p.u.
        Sbranch = maximum(Sf, St) * circuit.Sbase  # Branch power in MVA
        loading = Sbranch / circuit.power_flow_input.branch_rates  # Branch loading in p.u.

        # idx = where(abs(loading) == inf)[0]
        # loading[idx] = 9999

        return Sbranch, Ibranch, loading, losses

    @staticmethod
    def switch_logic(V, Vset, Q, Qmax, Qmin, types, original_types, verbose):
        """
        Change the buses type in order to control the generators reactive power
        @param pq: array of pq indices
        @param pv: array of pq indices
        @param ref: array of pq indices
        @param V: array of voltages (all buses)
        @param Vset: Array of set points (all buses)
        @param Q: Array of rective power (all buses)
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

    def run(self):
        """
        Run a power flow for every circuit
        @return:
        """
        print('PowerFlow at ', self.grid.name)
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        results = PowerFlowResults()
        results.initialize(n, m)
        # self.progress_signal.emit(0.0)
        k = 0
        for circuit in self.grid.circuits:
            if self.options.verbose:
                print('Solving ' + circuit.name)

            circuit.power_flow_results = self.single_power_flow(circuit)
            results.apply_from_island(circuit.power_flow_results, circuit.bus_original_idx, circuit.branch_original_idx)

            # self.progress_signal.emit((k+1) / len(self.grid.circuits))
            k += 1
        # remember the solution for later
        self.last_V = results.voltage

        # check the limits
        sum_dev = results.check_limits(self.grid.power_flow_input)

        self.results = results
        self.grid.power_flow_results = results

        # self.progress_signal.emit(0.0)
        # self.done_signal.emit()

    def run_at(self, t, mc=False):
        """
        Run power flow at the time series object index t
        @param t:
        @return:
        """
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        if self.grid.power_flow_results is None:
            self.grid.power_flow_results = PowerFlowResults()
        self.grid.power_flow_results.initialize(n, m)
        i = 1
        # self.progress_signal.emit(0.0)
        for circuit in self.grid.circuits:
            if self.options.verbose:
                print('Solving ' + circuit.name)

            # Set the profile values
            circuit.set_at(t, mc)
            # run
            circuit.power_flow_results = self.single_power_flow(circuit)
            self.grid.power_flow_results.apply_from_island(circuit.power_flow_results,
                                                           circuit.bus_original_idx,
                                                           circuit.branch_original_idx)

            # prog = (i / len(self.grid.circuits)) * 100
            # self.progress_signal.emit(prog)
            i += 1

        # check the limits
        sum_dev = self.grid.power_flow_results.check_limits(self.grid.power_flow_input)

        # self.progress_signal.emit(0.0)
        # self.done_signal.emit()

        return self.grid.power_flow_results

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

        self.Scpower = SCpower

        self.available_results = ['Bus voltage', 'Branch power', 'Branch current', 'Branch_loading', 'Branch losses',
                                  'Bus short circuit power']

    def copy(self):
        """
        Return a copy of this
        @return:
        """
        return ShortCircuitResults(Sbus=self.Sbus, voltage=self.voltage, Sbranch=self.Sbranch,
                                   Ibranch=self.Ibranch, loading=self.loading,
                                   losses=self.losses, SCpower=self.Scpower, error=self.error,
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

        self.Scpower = zeros(n, dtype=float)

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

        self.Scpower[b_idx] = results.Scpower

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
                y = self.Scpower[indices]
                ylabel = '(MVA)'
                title = 'Bus short circuit power'
            else:
                pass

            df = pd.DataFrame(data=y, index=labels, columns=[result_type])
            df.plot(ax=ax, kind='bar', linewidth=LINEWIDTH)
            ax.set_ylabel(ylabel)
            ax.set_title(title)

            return df

        else:
            return None


class ShortCircuit(QRunnable):
    # progress_signal = pyqtSignal(float)
    # progress_text = pyqtSignal(str)
    # done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: ShortCircuitOptions):
        """
        PowerFlow class constructor
        @param grid: MultiCircuit Object
        """
        QRunnable.__init__(self)

        # Grid to run a power flow in
        self.grid = grid

        # Options to use
        self.options = options

        # compile the buses short circuit impedance array
        n = len(self.grid.buses)
        self.Zf = zeros(n, dtype=complex)
        for i in range(n):
            self.Zf[i] = self.grid.buses[i].Zf

        self.results = None

        self.__cancel__ = False

    def single_short_circuit(self, circuit: Circuit):
        """
        Run a power flow simulation for a single circuit
        @param circuit:
        @return:
        """

        assert (circuit.power_flow_results is not None)

        # compute Zbus if needed
        if circuit.power_flow_input.Zbus is None:
            circuit.power_flow_input.Zbus = inv(
                circuit.power_flow_input.Ybus).toarray()  # is dense, so no need to store it as sparse

        # Compute the short circuit
        V, SCpower = short_circuit_3p(bus_idx=self.options.bus_index,
                                      Zbus=circuit.power_flow_input.Zbus,
                                      Vbus=circuit.power_flow_results.voltage,
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

        # # check the limits
        # sum_dev = results.check_limits(circuit.power_flow_input)
        # print('dev sum: ', sum_dev)

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
        print('Short circuit at ', self.grid.name)
        # self.progress_signal.emit(0.0)

        n = len(self.grid.buses)
        m = len(self.grid.branches)
        results = ShortCircuitResults()  # yes, reuse this class
        results.initialize(n, m)
        k = 0
        for circuit in self.grid.circuits:
            if self.options.verbose:
                print('Solving ' + circuit.name)

            circuit.short_circuit_results = self.single_short_circuit(circuit)
            results.apply_from_island(circuit.short_circuit_results, circuit.bus_original_idx,
                                      circuit.branch_original_idx)

            # self.progress_signal.emit((k+1) / len(self.grid.circuits))
            k += 1

        self.results = results
        self.grid.short_circuit_results = results

        # self.progress_signal.emit(0.0)
        # self.done_signal.emit()

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

        :param res:
        :param bus_original_idx:
        :param branch_original_idx:
        :param nbus_full:
        :param nbranch_full:
        :return:
        """

        if self.Sprof is None:
            self.time_array = res.time_array
            t = len(self.time_array)
            self.Sprof = pd.DataFrame()  # zeros((t, nbus_full), dtype=complex)
            self.Iprof = pd.DataFrame()  # zeros((t, nbranch_full), dtype=complex)
            self.Yprof = pd.DataFrame()  # zeros((t, nbus_full), dtype=complex)

        self.Sprof[res.Sprof.columns.values] = res.Sprof
        self.Iprof[res.Iprof.columns.values] = res.Iprof
        self.Yprof[res.Yprof.columns.values] = res.Yprof


class TimeSeriesResults(PowerFlowResults):

    def __init__(self, n, m, nt):
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

    def set_at(self, t, results: PowerFlowResults, b_idx, br_idx):
        """
        Set the results at the step t
        @param t:
        @param results:
        @return:
        """

        self.voltage[t, :] = results.voltage[b_idx]

        self.Sbranch[t, :] = results.Sbranch[br_idx]

        self.Ibranch[t, :] = results.Ibranch[br_idx]

        self.loading[t, :] = results.loading[br_idx]

        self.losses[t, :] = results.losses[br_idx]

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

        # self.voltage[:, b_idx] = results.voltage
        #
        # self.Sbranch[:, br_idx] = results.Sbranch
        #
        # self.Ibranch[:, br_idx] = results.Ibranch
        #
        # self.loading[:, br_idx] = results.loading
        #
        # self.losses[:, br_idx] = results.losses
        #
        # if (results.error > self.error).any():
        #     self.error = results.error
        #
        # self.converged = self.converged * results.converged

        self.voltage = self.merge_if(self.voltage, results.voltage, index, b_idx)

        self.Sbranch = self.merge_if(self.Sbranch, results.Sbranch, index, br_idx)

        self.Ibranch = self.merge_if(self.Ibranch, results.Ibranch, index, br_idx)

        self.loading = self.merge_if(self.loading, results.loading, index, br_idx)

        self.losses = self.merge_if(self.losses, results.losses, index, br_idx)

        self.error = self.merge_if(self.error, results.error, index, [grid_idx])

        self.converged = self.merge_if(self.converged, results.converged, index, [grid_idx])

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
                df = self.voltage[indices]
                ylabel = '(p.u.)'
                title = 'Bus voltage '

            elif result_type == 'Branch power':
                df = self.Sbranch[indices]
                ylabel = '(MVA)'
                title = 'Branch power '

            elif result_type == 'Branch current':
                df = self.Ibranch[indices]
                ylabel = '(kA)'
                title = 'Branch current '

            elif result_type == 'Branch_loading':
                df = self.loading[indices] * 100
                ylabel = '(%)'
                title = 'Branch loading '

            elif result_type == 'Branch losses':
                df = self.losses[indices]
                ylabel = '(MVA)'
                title = 'Branch losses'

            else:
                pass

            df.columns = labels

            if len(df.columns) > 10:
                df.plot(ax=ax, linewidth=LINEWIDTH, legend=False)
            else:
                df.plot(ax=ax, linewidth=LINEWIDTH, legend=True)

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

        for i in range(self.res.nt):
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
        powerflow = PowerFlow(self.grid, self.options)

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

            Voltage_series, Lambda_series, \
            normF, success = continuation_nr(Ybus=c.power_flow_input.Ybus,
                                             Ibus_base=c.power_flow_input.Ibus[c.bus_original_idx],
                                             Ibus_target=c.power_flow_input.Ibus[c.bus_original_idx],
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
                                             verbose=False)

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
            self.progress_signal.emit(max((std_dev_progress, it / max_mc_iter * 100)))

            print(iter, '/', max_mc_iter)
            # print('Vmc:', Vavg)
            print('Vstd:', Vvariance, ' -> ', std_dev_progress, ' %')

        # compile results
        self.progress_text.emit('Compiling results...')
        mc_results.compile()

        # compute the averaged branch magnitudes
        mc_results.sbranch, Ibranch, loading, mc_results.losses = powerflow.compute_branch_results(self.grid,
                                                                                                   mc_results.voltage)

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

        return y_pred[:, :int(d / 2)] + 1j * y_pred[:, int(d / 2):d]

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
        powerflow = PowerFlow(self.grid, self.options)

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
        lhs_results.sbranch, Ibranch, loading, lhs_results.losses = powerflow.compute_branch_results(self.grid,
                                                                                                     lhs_results.voltage)

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


########################################################################################################################
# Cascading classes
########################################################################################################################


class CascadingReportElement:

    def __init__(self, removed_idx, pf_results):
        self.removed_idx = removed_idx
        self.pf_results = pf_results


class Cascading(QThread):
    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, triggering_idx=None, max_additional_islands=1,
                 cascade_type_: CascadeType = CascadeType.LatinHypercube, n_lhs_samples_=1000):
        """
        Constructor
        Args:
            grid: Grid to cascade
            options: Power flow Options
            triggering_idx: branch indices to trigger first
        """

        QThread.__init__(self)

        self.grid = grid

        self.options = options

        self.triggering_idx = triggering_idx

        self.__cancel__ = False

        self.report = list()

        self.current_step = 0

        self.max_additional_islands = max_additional_islands

        self.cascade_type = cascade_type_

        self.n_lhs_samples = n_lhs_samples_

    @staticmethod
    def remove_elements(circuit: Circuit, idx=None):
        """
        Remove branches based on loading
        Returns:
            Nothing
        """

        if idx is None:
            load = abs(circuit.power_flow_results.loading)
            idx = where(load > 1.0)[0]

            if len(idx) == 0:
                idx = where(load >= load.max())[0]

        # disable the selected branches
        print('Removing:', idx, load[idx])

        for i in idx:
            circuit.branches[i].active = False

        return idx

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
        self.report.append(entry)

        # increase the step number
        self.current_step += 1

        print(model_simulator.results.get_convergence_report())

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

        self.report = list()

        if len(self.grid.circuits) == 0:
            self.grid.compile()

        # initialize the simulator
        if self.cascade_type is CascadeType.PowerFlow:
            model_simulator = PowerFlow(self.grid, self.options)

        elif self.cascade_type is CascadeType.LatinHypercube:
            model_simulator = LatinHypercubeSampling(self.grid, self.options, sampling_points=1000)

        else:
            model_simulator = PowerFlow(self.grid, self.options)

        self.progress_signal.emit(0.0)
        self.progress_text.emit('Running cascading failure...')

        n_grids = len(self.grid.circuits) + self.max_additional_islands
        if n_grids > len(self.grid.buses):  # safety check
            n_grids = len(self.grid.buses) - 1

        print('n grids: ', n_grids)

        it = 0
        while len(self.grid.circuits) <= n_grids and it <= n_grids:

            # For every circuit, run a power flow
            # for c in self.grid.circuits:
            model_simulator.run()
            # print(model_simulator.results.get_convergence_report())

            if it == 0:
                # the first iteration try to trigger the selected indices, if any
                idx = self.remove_elements(self.grid, idx=self.triggering_idx)
            else:
                # for the next indices, just cascade normally
                idx = self.remove_elements(self.grid)

            # store the removed indices and the results
            entry = CascadingReportElement(idx, model_simulator.results)
            self.report.append(entry)

            # recompile grid
            self.grid.compile()

            it += 1

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
        res = None
        for i in range(len(self.report)):
            if i == 0:
                res = self.report[i][0]
            else:
                res = r_[res, self.report[i][0]]

        return res

    def get_table(self):

        dta = list()
        for i in range(len(self.report)):
            dta.append(['Step ' + str(i + 1), len(self.report[i].removed_idx)])

        return pd.DataFrame(data=dta, columns=['Cascade step', 'Elements failed'])

    def cancel(self):
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
            triggering_idx: branch indices to trigger first
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

        # For every circuit, run the time series
        for c in self.grid.circuits:
            # sample from the CDF give the vector x of values in [0, 1]
            c.sample_at(x)

            #  run the sampled values
            res = self.power_flow.run_at(0, mc=True)

            Y, I, S = c.mc_time_series.get_at(0)
            self.results.S_points[self.it, c.bus_original_idx] = S
            self.results.V_points[self.it, c.bus_original_idx] = res.voltage[c.bus_original_idx]
            self.results.I_points[self.it, c.branch_original_idx] = res.Ibranch[c.branch_original_idx]
            self.results.loading_points[self.it, c.branch_original_idx] = res.loading[c.branch_original_idx]

        self.it += 1
        prog = self.it / self.max_eval * 100
        # self.progress_signal.emit(prog)

        f = abs(self.results.V_points[self.it - 1, :].sum()) / self.dim
        print(prog, ' % \t', f)

        return f

    def run(self):
        """
        Run the monte carlo simulation
        @return:
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
        Returns:

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
        self.__cancel__ = True
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled')
        self.done_signal.emit()