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
from enum import Enum
from warnings import warn

import networkx as nx
import pandas as pd
from datetime import datetime, timedelta
from PyQt5.QtCore import QThread, QRunnable, pyqtSignal
from matplotlib import pyplot as plt
from matplotlib.pyplot import plot
from networkx import connected_components
from numpy import complex, double, sqrt, zeros, ones, nan_to_num, exp, conj, ndarray, vstack, power, delete, angle, \
    where, r_, Inf, linalg, maximum, array, random, nan, shape, arange, sort, interp, iscomplexobj, c_, argwhere, floor
from scipy.sparse import csc_matrix as sparse
from copy import deepcopy

if 'fivethirtyeight' in plt.style.available:
    plt.style.use('fivethirtyeight')

from grid.ImportParsers.DGS_Parser import read_DGS
from grid.ImportParsers.matpower_parser import parse_matpower_file
from grid.IwamotoNR import IwamotoNR
from grid.ContinuationPowerFlow import continuation_nr
from grid.HelmVect import helm
from grid.DCPF import dcpf


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
    HELMZ = 10


class TimeGroups(Enum):
    NoGroup = 0,
    ByDay = 1,
    ByHour = 2


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
            self.arr = sort(ndarray.flatten(data))

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
        pt = random.uniform(0, 1, npoints)
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
        ax.plot(self.prob, self.arr)
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
                data["baseMVA"] = double(df.values[0, 1])
                data["basekA"] = double(df.values[1, 1])
                data["version"] = double(df.values[2, 1])

            else:
                # just pick the DataFrame
                df = xl.parse(name, index_col=0)
                data[name] = df

    return data


def load_from_dgs(filename):
    """
    Use the DGS parset to get a circuit structure dictionary
    @param filename:
    @return: Circuit dictionary
    """
    baseMVA, BUSES, BRANCHES, GEN, graph, gpos, BUS_NAMES, BRANCH_NAMES, GEN_NAMES = read_DGS(filename)
    ppc = dict()
    ppc["baseMVA"] = baseMVA
    ppc["bus"] = BUSES.values
    ppc['bus_names'] = BUS_NAMES
    ppc["gen"] = GEN.values
    ppc['gen_names'] = GEN_NAMES
    ppc["branch"] = BRANCHES.values
    ppc['branch_names'] = BRANCH_NAMES

    return ppc


class Bus:

    def __init__(self, name="Bus", vnom=0, vmin=0.9, vmax=1.1, xpos=None, ypos=None, is_enabled=True):
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

        self.is_enabled = is_enabled

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

        self.edit_headers = ['name', 'is_enabled', 'is_slack', 'Vnom', 'Vmin', 'Vmax', 'x', 'y']

        self.edit_types = {'name': str,
                           'is_enabled': bool,
                           'is_slack': bool,
                           'Vnom': float,
                           'Vmin': float,
                           'Vmax': float,
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

        Yprof = None
        Iprof = None  # Positive Generates, negative consumes
        Sprof = None  # Positive Generates, negative consumes

        Ycdf = None
        Icdf = None   # Positive Generates, negative consumes
        Scdf = None   # Positive Generates, negative consumes

        self.Qmin_sum = 0
        self.Qmax_sum = 0

        is_v_controlled = False

        for elm in self.loads:
            if elm.Z != 0:
                Y += 1 / elm.Z
            I -= elm.I  # Reverse sign convention in the load
            S -= elm.S  # Reverse sign convention in the load

            # Add the profiles
            elm_Sprof, elm_Iprof, elm_Zprof = elm.get_profiles(index)
            if elm_Zprof is not None:
                if elm_Zprof.values.sum(axis=0) != complex(0):
                    if Yprof is None:
                        Yprof = 1 / elm_Zprof
                        Ycdf = CDF(Yprof)
                    else:
                        pr = 1 / elm_Zprof
                        Yprof = Yprof.add(pr, fill_value=0)
                        Ycdf = Ycdf + CDF(pr)

            if elm_Iprof is not None:
                if elm_Iprof.values.sum(axis=0) != complex(0):
                    if Iprof is None:
                        Iprof = -elm_Iprof  # Reverse sign convention in the load
                        Icdf = CDF(Iprof)
                    else:
                        pr = -elm_Iprof
                        Iprof = Iprof.add(pr, fill_value=0)  # Reverse sign convention in the load
                        Icdf = Icdf + CDF(pr)

            if elm_Sprof is not None:
                if elm_Sprof.values.sum(axis=0) != complex(0):
                    if Sprof is None:
                        Sprof = -elm_Sprof  # Reverse sign convention in the load
                        Scdf = CDF(Sprof)
                    else:
                        pr = -elm_Sprof
                        Sprof = Sprof.add(pr, fill_value=0)  # Reverse sign convention in the load
                        Scdf = Scdf + CDF(pr)

        # controlled gen and batteries
        for elm in self.controlled_generators + self.batteries:

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
                    raise "Different voltage controlled generators try to control " \
                          "the same bus with different voltage set points"
                else:
                    pass

            # add the power profile
            elm_Pprof, elm_Vsetprof = elm.get_profiles(index)
            if elm_Pprof is not None:
                if Sprof is None:
                    Sprof = elm_Pprof  # Reverse sign convention in the load
                    Scdf = CDF(Sprof)
                else:
                    Sprof = Sprof.add(elm_Pprof, fill_value=0)
                    Scdf = Scdf + CDF(elm_Pprof)

        # set maximum reactive power limits
        if self.Qmin_sum == 0:
            self.Qmin_sum = -999900
        if self.Qmax_sum == 0:
            self.Qmax_sum = 999900

        for elm in self.shunts:
            Y += elm.Y

        # for elm in self.batteries:
        #     S += elm.S

        for elm in self.static_generators:
            S += elm.S

            if elm.Sprof is not None:
                if Sprof is None:
                    Sprof = elm.Sprof  # Reverse sign convention in the load
                    Scdf = CDF(Sprof)
                else:
                    Sprof = Sprof.add(elm.Sprof, fill_value=0)
                    Scdf = Scdf + CDF(elm.Pprof)

        if Sprof is not None:
            Sprof = Sprof.sum(axis=1)

        if Iprof is not None:
            Iprof = Iprof.sum(axis=1)

        if Yprof is not None:
            Yprof = Yprof.sum(axis=1)

        return Y, I, S, V, Yprof, Iprof, Sprof, Ycdf, Icdf, Scdf

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

        bus.Qmin_sum = self.Qmin_sum

        bus.Qmax_sum = self.Qmax_sum

        bus.is_enabled = self.is_enabled

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
        return [self.name, self.is_enabled, self.is_slack, self.Vnom, self.Vmin, self.Vmax, self.x, self.y]

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

        self.is_enabled = active

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

        self.edit_headers = ['name', 'bus_from', 'bus_to', 'is_enabled', 'rate', 'mttf', 'mttr', 'R', 'X', 'G', 'B', 'tap_module', 'angle']

        self.edit_types = {'name': str,
                           'bus_from': None,
                           'bus_to': None,
                           'is_enabled': bool,
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
                   active=self.is_enabled,
                   mttf=self.mttf,
                   mttr=self.mttr)

        return b

    def get_tap(self):
        """
        Get the complex tap value
        @return:
        """
        return self.tap_module * exp(-1j * self.angle)

    def apply_to(self, Ybus, Yseries, Yshunt, Yf, Yt, i, f, t):
        """

        Modify the circuit admittance matrices with the admittances of this branch
        @param Ybus: Complete Admittance matrix
        @param Yseries: Admittance matrix of the series elements
        @param Yshunt: Admittance matrix of the shunt elements
        @param Yf: Admittance matrix of the branches with the from buses
        @param Yt: Admittance matrix of the branches with the to buses
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

        Ybus[f, f] += Yff
        Ybus[f, t] += Yft
        Ybus[t, f] += Ytf
        Ybus[t, t] += Ytt

        # Yf = csr_matrix((r_[Yff, Yft], (i, r_[f, t])), (nl, nb))
        # Yt = csr_matrix((r_[Ytf, Ytt], (i, r_[f, t])), (nl, nb))
        Yf[i, f] += Yff  # Ybus[f, f]
        Yf[i, t] += Yft  # Ybus[f, t]
        Yt[i, f] += Ytf  # Ybus[t, f]
        Yt[i, t] += Ytt  # Ybus[t, t]

        Yshunt[f] += Yff_sh
        Yshunt[t] += Ytt_sh

        Yseries[f, f] += Ys / (tap * conj(tap))
        Yseries[f, t] += Yft
        Yseries[t, f] += Ytf
        Yseries[t, t] += Ys

        return f, t

    def apply_transformer_type(self, obj: TransformerType):
        """
        Apply a transformer type definition to this object
        Args:
            obj:

        Returns:

        """
        leakage_impedance, magnetizing_impedance = obj.get_impedances()

        self.z_series = magnetizing_impedance
        self.y_shunt = 1 / leakage_impedance

        self.type_obj = obj

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        return [self.name, self.bus_from.name, self.bus_to.name, self.is_enabled, self.rate, self.mttf, self.mttr,
                self.R, self.X, self.G, self.B, self.tap_module, self.angle]


class Load:

    def __init__(self, name='Load', impedance=complex(0, 0), current=complex(0, 0), power=complex(0, 0),
                 impedance_prof=None, current_prof=None, power_prof=None):
        """
        Load model constructor
        This model implements the so-called ZIP model
        composed of an impedance value, a current value and a power value
        @param impedance: Impedance complex (Ohm)
        @param current: Current complex (kA)
        @param power: Power complex (MVA)
        """

        self.name = name

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

        self.edit_headers = ['name', 'bus', 'Z', 'I', 'S']

        self.edit_types = {'name': str, 'bus': None, 'Z': complex, 'I': complex, 'S': complex}

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

    def __init__(self, name='StaticGen', power=complex(0, 0), power_prof=None):
        """

        @param power:
        """

        self.name = name

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

        self.edit_headers = ['name', 'bus', 'S']

        self.edit_types = {'name': str,  'bus': None,  'S': complex}

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
                 power_prof=None, vset_prof=None):
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
        """

        self.name = name

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

        self.edit_headers = ['name', 'bus', 'P', 'Vset', 'Snom', 'Enom', 'Qmin', 'Qmax']

        self.edit_types = {'name': str,
                           'bus': None,
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
                 power_prof=None, vset_prof=None):
        """
        Voltage controlled generator
        @param name:
        @param active_power: Active power (MW)
        @param voltage_module: Voltage set point (p.u.)
        @param Qmin:
        @param Qmax:
        @param Snom:
        @param Enom:
        """

        self.name = name

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

        self.edit_headers = ['name', 'bus', 'P', 'Vset', 'Snom', 'Qmin', 'Qmax']

        self.edit_types = {'name': str,
                           'bus': None,
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

    def __init__(self, name='shunt', admittance=complex(0, 0), admittance_prof=None):
        """
        Shunt
        @param admittance:
        """
        self.name = name

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

        self.edit_headers = ['name', 'bus', 'Y']

        self.edit_types = {'name': str,   'bus': None, 'Y': complex}

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

        # Base current (kA)
        self.Ibase = 100

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
        self.Ibase = 100
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

        # Compile the buses
        for i in range(n):

            # Add buses dictionary entry
            buses_dict[self.buses[i]] = i

            # Determine the bus type
            self.buses[i].determine_bus_type()

            # compute the bus magnitudes
            Y, I, S, V, Yprof, Iprof, Sprof, Ycdf, Icdf, Scdf = self.buses[i].get_YISV()
            power_flow_input.Vbus[i] = V  # set the bus voltages
            power_flow_input.Sbus[i] += S  # set the bus power
            power_flow_input.Ibus[i] += I  # set the bus currents

            power_flow_input.Ybus[i, i] += Y / self.Sbase  # set the bus shunt impedance in per unit
            power_flow_input.Yshunt[i] += power_flow_input.Ybus[i, i]  # copy the shunt impedance

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

        power_flow_input.Sbus /= self.Sbase  # normalize the power array
        power_flow_input.Ibus /= self.Ibase  # normalize the currents array
        power_flow_input.Qmax /= self.Sbase
        power_flow_input.Qmin /= self.Sbase

        if Sprofile is not None:
            Sprofile /= self.Sbase
            Sprofile.columns = ['Sprof@Bus' + str(i) for i in range(Sprofile.shape[1])]

        if Iprofile is not None:
            Iprofile /= self.Ibase
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

            if self.branches[i].is_enabled:
                # Set the branch impedance

                f = buses_dict[self.branches[i].bus_from]
                t = buses_dict[self.branches[i].bus_to]

                f, t = self.branches[i].apply_to(Ybus=power_flow_input.Ybus,
                                                 Yseries=power_flow_input.Yseries,
                                                 Yshunt=power_flow_input.Yshunt,
                                                 Yf=power_flow_input.Yf,
                                                 Yt=power_flow_input.Yt,
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
                warn('The branch ' + str(i) + ' has no rate.')

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
                self.power_flow_input.Sbus = self.mc_time_series.S[t, :] / self.Sbase
            else:
                self.power_flow_input.Sbus = self.time_series_input.S[t, :] / self.Sbase
        else:
            warn('No time series values')

    def sample_monte_carlo_batch(self, batch_size):
        """
        Samples a monte carlo batch as a time series object
        @param batch_size: size of the batch (integer)
        @return:
        """
        self.mc_time_series = self.monte_carlo_input(batch_size)

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


class MultiCircuit(Circuit):

    def __init__(self):
        """
        Multi Circuit Constructor
        """
        Circuit.__init__(self)

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
                data_in_zero_base = True
            elif file_extension == '.dgs':
                ppc = load_from_dgs(filename)
            elif file_extension == '.m':
                ppc = parse_matpower_file(filename)
                data_in_zero_base = False

            # Pass the table-like data dictionary to objects in this circuit
            if 'version' not in ppc.keys():
                self.interpret_data_v1(ppc)
                return True
            elif ppc['version'] == 2.0:
                self.interpret_data_v2(ppc)
                return True
            else:
                warn('The file could not be processed')
                return False

        else:
            warn('The file does not exist.')
            return False

    def interpret_data_v1(self, data):
        """
        Pass the loaded table-like data to the  structures
        @param data: Data dictionary
        @return:
        """

        self.clear()

        # time profile
        if 'master_time' in data.keys():
            master_time_array = data['master_time']
        else:
            master_time_array = None

        import grid.ImportParsers.BusDefinitions as e
        # Buses
        table = data['bus']
        buses_dict = dict()
        n = len(table)

        # load profiles
        if 'Lprof' in data.keys():
            Sprof = data['Lprof'] + 1j * data['LprofQ']
            are_load_prfiles = True
            print('There are load profiles')
        else:
            are_load_prfiles = False

        if 'bus_names' in data.keys():
            names = data['bus_names']
        else:
            names = ['bus ' + str(i) for i in range(n)]

        #   Buses
        for i in range(n):
            # Create bus
            bus = Bus(name=names[i],
                      vnom=table[i, e.BASE_KV],
                      vmax=table[i, e.VMAX],
                      vmin=table[i, e.VMIN],
                      xpos=table[i, e.BUS_X],
                      ypos=table[i, e.BUS_Y])

            # determine if the bus is set as slack manually
            tpe = table[i, e.BUS_TYPE]
            if tpe == e.REF:
                bus.is_slack = True
            else:
                bus.is_slack = False

            # Add the load
            if table[i, e.PD] != 0 or table[i, e.QD] != 0:
                load = Load(power=table[i, e.PD] + 1j * table[i, e.QD])
                load.bus = bus
                if are_load_prfiles:  # set the profile
                    load.Sprof = pd.DataFrame(data=Sprof[:, i],
                                              index=master_time_array,
                                              columns=['Load@' + names[i]])
                bus.loads.append(load)

            # Add the shunt
            if table[i, e.GS] != 0 or table[i, e.BS] != 0:
                shunt = Shunt(admittance=table[i, e.GS] + 1j * table[i, e.BS])
                shunt.bus = bus
                bus.shunts.append(shunt)

            # Add the bus to the circuit buses
            self.add_bus(bus)

        import grid.ImportParsers.GenDefinitions as e
        # Generators
        table = data['gen']
        n = len(table)
        # load profiles
        if 'Gprof' in data.keys():
            Gprof = data['Gprof']
            are_gen_prfiles = True
            print('There are gen profiles')
        else:
            are_gen_prfiles = False

        if 'gen_names' in data.keys():
            names = data['gen_names']
        else:
            names = ['gen ' + str(i) for i in range(n)]
        for i in range(len(table)):
            bus_idx = int(table[i, e.GEN_BUS])
            gen = ControlledGenerator(name=names[i],
                                      active_power=table[i, e.PG],
                                      voltage_module=table[i, e.VG],
                                      Qmax=table[i, e.QMAX],
                                      Qmin=table[i, e.QMIN])
            if are_gen_prfiles:
                gen.Pprof = pd.DataFrame(data=Gprof[:, i],
                                         index=master_time_array,
                                         columns=['Gen@' + names[i]])

            # Add the generator to the bus
            gen.bus = self.buses[bus_idx]
            self.buses[bus_idx].controlled_generators.append(gen)

        import grid.ImportParsers.BranchDefinitions as e
        # Branches
        table = data['branch']
        n = len(table)
        if 'branch_names' in data.keys():
            names = data['branch_names']
        else:
            names = ['branch ' + str(i) for i in range(n)]
        for i in range(len(table)):
            f = self.buses[int(table[i, e.F_BUS])]
            t = self.buses[int(table[i, e.T_BUS])]
            branch = Branch(bus_from=f,
                            bus_to=t,
                            name=names[i],
                            r=table[i, e.BR_R],
                            x=table[i, e.BR_X],
                            g=0,
                            b=table[i, e.BR_B],
                            rate=table[i, e.RATE_A],
                            tap=table[i, e.TAP],
                            shift_angle=table[i, e.SHIFT],
                            active=bool(table[i, e.BR_STATUS]))

            self.add_branch(branch)

        # add the profiles

        if master_time_array is not None:

            self.format_profiles(master_time_array)

            table = data['bus']
            for i in range(len(table)):
                if are_load_prfiles and len(self.buses[i].loads) > 0:  # set the profile
                    self.buses[i].loads[0].Sprof = pd.DataFrame(data=Sprof[:, i],
                                                                index=master_time_array,
                                                                columns=['Load@' + names[i]])
            import grid.ImportParsers.GenDefinitions as e
            table = data['gen']
            for i in range(len(table)):
                bus_idx = int(table[i, e.GEN_BUS])
                if are_gen_prfiles:
                    self.buses[bus_idx].controlled_generators[0].Pprof = pd.DataFrame(data=Gprof[:, i],
                                                                                      index=master_time_array,
                                                                                      columns=['Gen@' + names[i]])
        print('Interpreted.')

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

        # set the base magnitudes
        self.Sbase = data['baseMVA']
        self.Ibase = data['basekA']

        self.time_profile = None

        # common function
        def set_object_attributes(obj_, attr_list, values):
            for a, attr in enumerate(attr_list):
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
            obj.bus = bus
            bus.shunts.append(obj)

        print('Done!')

        # ['branch', 'load_Zprof', 'version', 'CtrlGen_Vset_profiles', 'CtrlGen_P_profiles', 'basekA',
        #                   'baseMVA', 'load_Iprof', 'battery', 'load', 'bus', 'shunt', 'controlled_generator',
        #                   'load_Sprof', 'static_generator']

    def save_file(self, filepath):
        """
        Save the circuit information
        :param filepath: file path to save
        :return:
        """
        dfs = dict()

        # configuration ################################################################################################
        obj = list()
        obj.append(['BaseMVA', self.Sbase])
        obj.append(['BasekA', self.Ibase])
        obj.append(['Version', 2])
        dfs['config'] = pd.DataFrame(data=obj, columns=['Property', 'Value'])

        # get the master time profile
        T = self.time_profile

        # buses ########################################################################################################
        obj = list()
        for elm in self.buses:
            obj.append(elm.get_save_data())
        dfs['bus'] = pd.DataFrame(data=obj, columns=Bus().edit_headers)

        # branches #####################################################################################################
        obj = list()
        for elm in self.branches:
            obj.append(elm.get_save_data())
        dfs['branch'] = pd.DataFrame(data=obj, columns=Branch(None, None).edit_headers)

        # loads ########################################################################################################
        obj = list()
        S_profiles = None
        I_profiles = None
        Z_profiles = None
        hdr = list()
        for elm in self.get_loads():
            obj.append(elm.get_save_data())
            hdr.append(elm.name)
            if T is not None:
                if S_profiles is None:
                    S_profiles = elm.Sprof.values
                    I_profiles = elm.Iprof.values
                    Z_profiles = elm.Zprof.values
                else:
                    S_profiles = c_[S_profiles, elm.Sprof.values]
                    I_profiles = c_[I_profiles, elm.Iprof.values]
                    Z_profiles = c_[Z_profiles, elm.Zprof.values]

        dfs['load'] = pd.DataFrame(data=obj, columns=Load().edit_headers)
        if S_profiles is not None:
            dfs['load_Sprof'] = pd.DataFrame(data=S_profiles.astype('str'), columns=hdr, index=T)
            dfs['load_Iprof'] = pd.DataFrame(data=I_profiles.astype('str'), columns=hdr, index=T)
            dfs['load_Zprof'] = pd.DataFrame(data=Z_profiles.astype('str'), columns=hdr, index=T)

        # static generators ############################################################################################
        obj = list()
        hdr = list()
        S_profiles = None
        for elm in self.get_static_generators():
            obj.append(elm.get_save_data())
            hdr.append(elm.name)
            if T is not None:
                if S_profiles is None:
                    S_profiles = elm.Sprof.values
                else:
                    S_profiles = c_[S_profiles, elm.Sprof.values]

        dfs['static_generator'] = pd.DataFrame(data=obj, columns=StaticGenerator().edit_headers)
        if S_profiles is not None:
            dfs['static_generator_Sprof'] = pd.DataFrame(data=S_profiles.astype('str'), columns=hdr, index=T)

        # battery ######################################################################################################
        obj = list()
        hdr = list()
        Vset_profiles = None
        P_profiles = None
        for elm in self.get_batteries():
            obj.append(elm.get_save_data())
            hdr.append(elm.name)
            if T is not None:
                if P_profiles is None:
                    P_profiles = elm.Pprof.values
                    Vset_profiles = elm.Vsetprof.values
                else:
                    P_profiles = c_[P_profiles, elm.Pprof.values]
                    Vset_profiles = c_[Vset_profiles, elm.Vsetprof.values]
        dfs['battery'] = pd.DataFrame(data=obj, columns=Battery().edit_headers)
        if P_profiles is not None:
            dfs['battery_Vset_profiles'] = pd.DataFrame(data=Vset_profiles, columns=hdr, index=T)
            dfs['battery_P_profiles'] = pd.DataFrame(data=P_profiles, columns=hdr, index=T)

        # controlled generator
        obj = list()
        hdr = list()
        Vset_profiles = None
        P_profiles = None
        for elm in self.get_controlled_generators():
            obj.append(elm.get_save_data())
            hdr.append(elm.name)
            if T is not None:
                if P_profiles is None:
                    P_profiles = elm.Pprof.values
                    Vset_profiles = elm.Vsetprof.values
                else:
                    P_profiles = c_[P_profiles, elm.Pprof.values]
                    Vset_profiles = c_[Vset_profiles, elm.Vsetprof.values]
        dfs['controlled_generator'] = pd.DataFrame(data=obj, columns=ControlledGenerator().edit_headers)
        if P_profiles is not None:
            dfs['CtrlGen_Vset_profiles'] = pd.DataFrame(data=Vset_profiles, columns=hdr, index=T)
            dfs['CtrlGen_P_profiles'] = pd.DataFrame(data=P_profiles, columns=hdr, index=T)

        # shunt
        obj = list()
        hdr = list()
        Yprofiles = None
        for elm in self.get_shunts():
            obj.append(elm.get_save_data())
            hdr.append(elm.name)
            if T is not None:
                if Yprofiles is None:
                    Yprofiles = elm.Yprof.values
                else:
                    Yprofiles = c_[Yprofiles, elm.Yprof.values]

        dfs['shunt'] = pd.DataFrame(data=obj, columns=Shunt().edit_headers)
        if Yprofiles is not None:
            dfs['shunt_Y_profiles'] = pd.DataFrame(data=Yprofiles, columns=hdr, index=T)

        # flush-save
        writer = pd.ExcelWriter(filepath)
        for key in dfs.keys():
            dfs[key].to_excel(writer, key)
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
            if self.branches[i].is_enabled:
                if self.branches[i].bus_from.is_enabled and self.branches[i].bus_to.is_enabled:
                    f = self.bus_dictionary[self.branches[i].bus_from]
                    t = self.bus_dictionary[self.branches[i].bus_to]
                    # Add graph edge (automatically adds the vertices)
                    self.graph.add_edge(f, t)
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
                    # # Re-reference the buses indices
                    # branch.bus_from = isl_dict[branch.bus_from]
                    # branch.bus_to = isl_dict[branch.bus_to]
                    # Add the branch to the circuit
                    circuit.branches.append(branch)
                    circuit.branch_original_idx.append(i)

            circuit.compile()
            self.power_flow_input.set_from(circuit.power_flow_input, circuit.bus_original_idx,
                                           circuit.branch_original_idx)

            self.time_series_input.apply_from_island(circuit.time_series_input,
                                                     circuit.bus_original_idx,
                                                     circuit.branch_original_idx,
                                                     n, m)

            self.circuits.append(circuit)

            self.has_time_series = self.has_time_series and circuit.time_series_input.valid

            isl_idx += 1

            # print(islands)

    def create_profiles(self, steps, step_length, step_unit, time_base: datetime=datetime.now()):
        """
        Set the default profiles in all the objects enabled to have profiles
        Args:
            steps: Number of time steps
            step_length: time length (1, 2, 15, ...)
            step_unit: unit of the time step
            time_base: Date to start from

        Returns:
            Nothing
        """

        index = [None] * steps
        for i in range(steps):
            if step_unit == 'h':
                index[i] = time_base + timedelta(hours=i*step_length)
            elif step_unit == 'm':
                index[i] = time_base + timedelta(minutes=i*step_length)
            elif step_unit == 's':
                index[i] = time_base + timedelta(seconds=i*step_length)

        self.format_profiles(index)

    def format_profiles(self, index):
        """

        Args:
            index:
            steps:

        Returns:

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

    def get_elements_by_type(self, type):

        elements = list()
        parent_buses = list()

        if type == 'Load':
            for bus in self.buses:
                for elm in bus.loads:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif type == 'StaticGenerator':
            for bus in self.buses:
                for elm in bus.static_generators:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif type == 'ControlledGenerator':
            for bus in self.buses:
                for elm in bus.controlled_generators:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif type == 'Battery':
            for bus in self.buses:
                for elm in bus.batteries:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif type == 'Shunt':
            for bus in self.buses:
                for elm in bus.shunts:
                    elements.append(elm)
                    parent_buses.append(bus)

        return elements, parent_buses

    def set_power(self, S):
        """
        Set the power array in the circuits
        @param S:
        @return:
        """
        for circuit in self.circuits:
            idx = circuit.bus_original_idx
            circuit.power_flow_input.Sbus = S[idx]

    def add_bus(self, obj: Bus):
        """
        Add bus keeping track of it as object
        @param obj:
        @return:
        """
        self.buses.append(obj)
        # self.bus_dictionary[obj] = len(self.buses) - 1

    def delete_bus(self, obj: Bus):
        """
        Remove bus
        @param obj:
        @return:
        """

        # remove associated branches
        for i in range(len(self.branches) - 1, -1, -1):
            if self.branches[i].bus_from == obj or self.branches[i].bus_to == obj:
                self.branches.pop(i)

        # remove the bus itself
        # idx = self.bus_dictionary[obj]
        self.buses.remove(obj)
        # self.buses.pop(idx)
        # del self.bus_dictionary[obj]

    def add_branch(self, obj: Branch):
        """
        Add a branch object to the circuit
        @param obj:
        @return:
        """
        self.branches.append(obj)
        # self.branch_dictionary[obj] = len(self.branches) - 1

    def delete_branch(self, obj: Branch):
        """
        Delete a branch object from the circuit
        @param obj:
        @return:
        """
        # idx = self.branch_dictionary[obj]
        # self.branches.pop(idx)
        # del self.branch_dictionary[obj]
        self.branches.remove(obj)

    def add_load(self, bus: Bus):
        print('')
        api_obj = Load()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.loads.append(api_obj)

        return api_obj

    def add_controlled_generator(self, bus: Bus):
        api_obj = ControlledGenerator()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.controlled_generators.append(api_obj)

        return api_obj

    def add_static_generator(self, bus: Bus):
        api_obj = StaticGenerator()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.static_generators.append(api_obj)

        return api_obj

    def add_battery(self, bus: Bus):
        api_obj = Battery()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.batteries.append(api_obj)

        return api_obj

    def add_shunt(self, bus: Bus):
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


class PowerFlowOptions:

    def __init__(self, solver_type: SolverType = SolverType.NR, aux_solver_type: SolverType = SolverType.HELM,
                 verbose=False, robust=False, initialize_with_existing_solution=True, dispatch_storage=True,
                 tolerance=1e-6, max_iter=25, control_Q=True):
        """

        @param solver_type:
        @param aux_solver_type:
        @param verbose:
        @param robust:
        @param initialize_with_existing_solution:
        @param dispatch_storage:
        @param tolerance:
        @param max_iter:
        @param control_Q:
        """
        self.solver_type = solver_type

        self.auxiliary_solver_type = aux_solver_type

        self.tolerance = tolerance

        self.max_iter = max_iter

        self.control_Q = control_Q

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

        # Admittance matrix of the series elements (will be converted to sparse)
        self.Yseries = zeros((n, n), dtype=complex)

        # Admittance matrix of the shunt elements (actually it is only the diagonal, so let's make it a vector)
        self.Yshunt = zeros(n, dtype=complex)

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
        # self.Yshunt = sparse(self.Yshunt)  No need to make it sparse, it is a vector already
        # compile the types lists from the types vector
        self.compile_types()

    def mismatch(self, V, Sbus):
        """
        Compute the powerflow mismatch
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
        self.pqpv = r_[self.pq, self.pv]

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

    def set_from(self, obj, bus_idx, br_idx):
        """

        @param obj:
        @param bus_idx:
        @param br_idx:
        @return:
        """
        self.types[bus_idx] = obj.types

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


class PowerFlowResults:

    def __init__(self, Sbus=None, voltage=None, Sbranch=None, Ibranch=None, loading=None, losses=None, error=None,
                 converged=None, Qpv=None):
        """

        @param voltage:
        @param Sbranch:
        @param Ibranch:
        @param loading:
        @param losses:
        @param error:
        @param converged:
        @param Qpv:
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

    def copy(self):
        """
        Return a copy of this
        @return:
        """
        return PowerFlowResults(Sbus=self.Sbus, voltage=self.voltage, Sbranch=self.Sbranch,
                                Ibranch=self.Ibranch, loading=self.loading,
                                losses=self.losses, error=self.error,
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

    def plot(self, type, ax=None, indices=None, names=None):
        """
        Plot the results
        Args:
            type:
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
            if type == 'Bus voltage':
                y = self.voltage[indices]
                ylabel = 'Bus voltage (p.u.)'

            elif type == 'Branch power':
                y = self.Sbranch[indices]
                ylabel = 'Branch power (MVA)'

            elif type == 'Branch current':
                y = self.Ibranch[indices]
                ylabel = 'Branch current (kA)'

            elif type == 'Branch_loading':
                y = self.loading[indices] * 100
                ylabel = 'Branch loading (%)'

            elif type == 'Branch losses':
                y = self.losses[indices]
                ylabel = 'Branch losses (MVA)'

            else:
                pass

            # ax.set_xticklabels(names)
            # ax.plot(indices, y)
            # ax.set_xlabel('Element')
            # ax.set_ylabel(ylabel)
            df = pd.DataFrame(data=y, index=labels, columns=['V'])
            df.plot(ax=ax, kind='bar')

            return df

        else:
            return None


class PowerFlow(QRunnable):
    # progress_signal = pyqtSignal(float)
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

        optimize = False

        # Initial magnitudes
        if self.options.initialize_with_existing_solution and self.last_V is not None:
            V = self.last_V[circuit.bus_original_idx]
        else:
            V = circuit.power_flow_input.Vbus
        Sbus = circuit.power_flow_input.Sbus
        original_types = circuit.power_flow_input.types.copy()

        any_control_issue = True  # guilty assumption...

        while any_control_issue:

            if len(circuit.power_flow_input.ref) == 0:
                V = zeros(len(Sbus), dtype=complex)
                normF = 0
                Scalc = Sbus.copy()
                any_control_issue = False
                converged = True
            else:
                if self.options.solver_type == SolverType.HELM:
                    V, converged, normF, Scalc = helm(Y=circuit.power_flow_input.Ybus,
                                                      Ys=circuit.power_flow_input.Yseries,
                                                      Ysh=circuit.power_flow_input.Yshunt,
                                                      max_coefficient_count=30,
                                                      S=circuit.power_flow_input.Sbus,
                                                      voltage_set_points=V,
                                                      pq=circuit.power_flow_input.pq,
                                                      pv=circuit.power_flow_input.pv,
                                                      vd=circuit.power_flow_input.ref,
                                                      eps=self.options.tolerance)
                elif self.options.solver_type == SolverType.DC:

                    V, converged, normF, Scalc = dcpf(Ybus=circuit.power_flow_input.Ybus,
                                                      Sbus=Sbus,
                                                      Ibus=circuit.power_flow_input.Ibus,
                                                      V0=V,
                                                      ref=circuit.power_flow_input.ref,
                                                      pvpq=circuit.power_flow_input.pqpv,
                                                      pq=circuit.power_flow_input.pq,
                                                      pv=circuit.power_flow_input.pv)

                else:  # for any other method, for now, do a NR Iwamoto
                    V, converged, normF, Scalc = IwamotoNR(Ybus=circuit.power_flow_input.Ybus,
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
                        V, converged, normF, Scalc = helm(Y=circuit.power_flow_input.Ybus,
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

                        # Retry using the HELM solution
                        if not converged:
                            V, converged, normF, Scalc = IwamotoNR(Ybus=circuit.power_flow_input.Ybus,
                                                                   Sbus=Sbus,
                                                                   V0=V,
                                                                   Ibus=circuit.power_flow_input.Ibus,
                                                                   pv=circuit.power_flow_input.pv,
                                                                   pq=circuit.power_flow_input.pq,
                                                                   tol=self.options.tolerance,
                                                                   max_it=self.options.max_iter,
                                                                   robust=self.options.robust)
                            if not converged:
                                V = Vhelm

                # Check controls
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

        # revert the types to the original
        circuit.power_flow_input.compile_types(original_types)

        # if not self.check_controls(circuit, Sbus):

        # if optimize:
        #     print('Controls out of bounds: optimizing...')
        #
        #     # The voltage solution V is mofified by reference, therefore after the optimization
        #     # V in this function is the voltage solution
        #     fev, normF = self.optimization(pv=circuit.power_flow_input.pv,
        #                                    circuit=circuit, Sbus=Sbus, V=V,
        #                                    tol=self.options.tolerance,
        #                                    maxiter=self.options.max_iter,
        #                                    robust=self.options.robust,
        #                                    verbose=self.options.verbose)
        #     if abs(fev) > 1e-3:
        #         print('Controls cannot be satisfied.')

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


class TimeSeriesInput:

    def __init__(self, Sprof: pd.DataFrame=None, Iprof: pd.DataFrame=None, Yprof: pd.DataFrame=None):
        """
        Time series input
        @param Sprof: DataFrame with the profile of the injected power at the buses
        @param Iprof: DataFrame with the profile of the injected current at the buses
        @param Yprof: DataFrame with the profile of the shunt admittance at the buses
        """

        # master time array. All the profiles must match its length
        self.time_array = None

        self.Sprof = Sprof
        self.Iprof = Iprof
        self.Yprof = Yprof

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

        self.error[t] = results.error

        self.converged[t] = results.converged

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

    def plot(self, type, ax=None, indices=None, names=None):
        """
        Plot the results
        :param type:
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
            if type == 'Bus voltage':
                df = self.voltage[indices]
                ylabel = 'Bus voltage (p.u.)'

            elif type == 'Branch power':
                df = self.Sbranch[indices]
                ylabel = 'Branch power (MVA)'

            elif type == 'Branch current':
                df = self.Ibranch[indices]
                ylabel = 'Branch current (kA)'

            elif type == 'Branch_loading':
                df = self.loading[indices] * 100
                ylabel = 'Branch loading (%)'

            elif type == 'Branch losses':
                df = self.losses[indices]
                ylabel = 'Branch losses (MVA)'

            else:
                pass

            # df = pd.DataFrame(data=y, index=time_index, columns=labels)
            df.columns = labels
            df.plot(ax=ax, linewidth=1)  # , kind='bar')

            ax.set_title(ylabel)
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
        for c in self.grid.circuits:

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

        self.results = self.grid.time_series_results

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True


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

        l, n = res.voltages.shape

        if self.voltages is None:
            self.voltages = zeros((l, nbus_full), dtype=complex)
            self.voltages[:, bus_original_idx] = res.voltages
            self.lambdas = res.lambdas
        else:
            self.voltages[:, bus_original_idx] = res.voltages

    def plot(self, type='Bus voltage', ax=None, indices=None, names=None):
        """
        Plot the results
        :param type:
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
            if type == 'Bus voltage':
                y = abs(array(self.voltages)[:, indices])
                x = self.lambdas
                ylabel = 'Bus voltage (p.u.)'
            else:
                pass

            df = pd.DataFrame(data=y, index=x, columns=indices)
            df.columns = labels
            df.plot(ax=ax, linewidth=1)  # , kind='bar')

            ax.set_title(ylabel)
            ax.set_ylabel(ylabel)
            ax.set_xlabel('Loading from the base situation ($\Lambda$)')

            return df


class VoltageCollapse(QThread):

    progress_signal = pyqtSignal(float)
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

        for c in self.grid.circuits:
            Voltage_series, Lambda_series, \
            normF, success = continuation_nr(Ybus=c.power_flow_input.Ybus,
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
        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True


class MonteCarloInput:

    def __init__(self, n, Scdf, Icdf, Ycdf):
        """

        @param Scdf:
        @param Icdf:
        @param Ycdf:
        """
        self.n = n

        self.Scdf = Scdf

        self.Icdf = Icdf

        self.Ycdf = Ycdf

    def __call__(self, *args, **kwargs):

        if len(args) > 0:
            samples = args[0]
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


class MonteCarlo(QThread):

    progress_signal = pyqtSignal(float)
    done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions):
        """

        @param grid:
        @param options:
        """
        QThread.__init__(self)

        self.grid = grid

        self.options = options

        self.results = None

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
        iter = 0
        variance_sum = 0.0
        std_dev_progress = 0

        n = len(self.grid.buses)
        m = len(self.grid.branches)

        mc_results = MonteCarloResults(n, m)

        Vsum = zeros(n, dtype=complex)
        self.progress_signal.emit(0.0)

        while (std_dev_progress < 100.0) and (iter < max_mc_iter) and not self.__cancel__:

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
            iter += batch_size
            mc_results.append_batch(batch_results)
            Vsum += batch_results.get_voltage_sum()
            Vavg = Vsum / iter
            Vvariance = abs((power(mc_results.V_points - Vavg, 2.0) / (iter - 1)).min())

            ##### progress ######
            variance_sum += Vvariance
            err = variance_sum / iter
            if err == 0:
                err = 1e-200  # to avoid division by zeros
            mc_results.error_series.append(err)

            # emmit the progress signal
            std_dev_progress = 100 * mc_tol / err
            if std_dev_progress > 100:
                std_dev_progress = 100
            self.progress_signal.emit(max((std_dev_progress, iter/max_mc_iter*100)))

            print(iter, '/', max_mc_iter)
            # print('Vmc:', Vavg)
            print('Vstd:', Vvariance, ' -> ', std_dev_progress, ' %')

        mc_results.compile()
        self.results = mc_results

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True


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

        self.Vstd = zeros(n, dtype=complex)

        self.error_series = list()

        self.voltage = None
        self.current = None
        self.loading = None

        self.v_convergence = None
        self.c_convergence = None
        self.l_convergence = None

        self.available_results = ['Bus voltage std', 'Bus current std', 'Branch loading std']

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
        Compiles the final Monte Carlo values
        @return:
        """
        self.voltage = self.V_points.mean(axis=0)
        self.current = self.I_points.mean(axis=0)
        self.loading = self.loading_points.mean(axis=0)

        p, n = self.V_points.shape
        p, m = self.I_points.shape
        step = 100
        nn = int(floor(p / step) + 1)
        self.v_convergence = zeros((nn, n))
        self.c_convergence = zeros((nn, m))
        self.l_convergence = zeros((nn, m))
        k = 0
        for i in range(1, p, 100):
            self.v_convergence[k, :] = abs(self.V_points[0:i, :].std(axis=0))
            self.c_convergence[k, :] = abs(self.I_points[0:i, :].std(axis=0))
            self.l_convergence[k, :] = abs(self.loading_points[0:i, :].std(axis=0))
            k += 1

    def plot(self, type, ax=None, indices=None, names=None):
        """
        Plot the results
        :param type:
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
            if type == 'Bus voltage std':
                y = self.v_convergence[1:-1, indices]
                ylabel = 'Bus voltage (p.u.)'

            elif type == 'Bus current std':
                y = self.c_convergence[1:-1, indices]
                ylabel = 'Branch current (kA)'

            elif type == 'Branch loading std':
                y = self.l_convergence[1:-1, indices]
                ylabel = 'Branch loading (%)'

            else:
                pass

            df = pd.DataFrame(data=y, columns=labels)
            df.plot(ax=ax, linewidth=1)  # , kind='bar')

            ax.set_title(ylabel)
            ax.set_ylabel(ylabel)
            ax.set_xlabel('MC points')

            return df

        else:
            return None