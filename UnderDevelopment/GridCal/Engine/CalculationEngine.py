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
from networkx import connected_components
from numpy import complex, double, sqrt, zeros, ones, nan_to_num, exp, conj, ndarray, vstack, power, delete, where, \
    r_, Inf, linalg, maximum, array, nan, shape, arange, sort, interp, iscomplexobj, c_, argwhere, floor


from pySOT import *


from matplotlib import pyplot as plt

from GridCal.Gui.GeneralDialogues import *
from GridCal.Engine.Numerical.JacobianBased import Jacobian
from GridCal.Engine.PlotConfig import *
from GridCal.Engine.BasicStructures import CDF
from GridCal.Engine.PlotConfig import LINEWIDTH
from GridCal.Engine.BasicStructures import BusMode
from GridCal.Engine.IoStructures import PowerFlowInput, TimeSeriesInput, MonteCarloInput
from GridCal.Engine.Numerical.DynamicModels import DynamicModels
from GridCal.Engine.ObjectTypes import TransformerType, Tower, BranchTemplate, BranchType, \
                                            UndergroundLineType, SequenceLineType, Wire


########################################################################################################################
# Enumerations
########################################################################################################################



class BranchTypeConverter:

    def __init__(self, tpe: BranchType):

        self.tpe = tpe

        self.options = ['branch',
                        'line',
                        'transformer',
                        'switch',
                        'reactance']

        self.values = [BranchType.Branch,
                       BranchType.Line,
                       BranchType.Transformer,
                       BranchType.Switch,
                       BranchType.Reactance]

        self.conv = dict()
        self.inv_conv = dict()

        for o, v in zip(self.options, self.values):
            self.conv[o] = v
            self.inv_conv[v] = o

    def __str__(self):
        """
        Convert value to string
        """
        return self.inv_conv[self.tpe]

    def __call__(self, str_value):
        """
        Convert from string
        """
        return self.conv[str_value]


class TimeGroups(Enum):
    NoGroup = 0,
    ByDay = 1,
    ByHour = 2




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
                           'branch': None,
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
                           'shunt_Y_profiles': complex,
                           'wires': None,
                           'overhead_line_types': None,
                           'underground_cable_types': None,
                           'sequence_line_types': None,
                           'transformer_types': None}

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
                 active=True, is_slack=False, area='Defualt', zone='Default', substation='Default'):
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

        self.area = area

        self.zone = zone

        self.substation = substation

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
        self.type = BusMode.NONE

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

        self.edit_headers = ['name', 'active', 'is_slack', 'Vnom', 'Vmin', 'Vmax', 'Zf', 'x', 'y', 'h', 'w',
                             'area', 'zone', 'substation']

        self.units = ['', '', '', 'kV', 'p.u.', 'p.u.', 'p.u.', 'px', 'px', 'px', 'px',
                      '', '', '']

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
                           'w': float,
                           'area': str,
                           'zone': str,
                           'substation': str}

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
                self.type = BusMode.REF
            else:  # Otherwise set as PV
                self.type = BusMode.PV

        elif batt_on > 0:

            if self.dispatch_storage:
                # If there are storage devices and the dispatchable flag is on, set the bus as dispatchable
                self.type = BusMode.STO_DISPATCH
            else:
                # Otherwise a storage device shall be marked as a voltage controlled bus
                self.type = BusMode.PV
        else:
            if self.is_slack:  # If there is no device but still is marked as REF, then set as REF
                self.type = BusMode.REF
            else:
                # Nothing special; set it as PQ
                self.type = BusMode.PQ

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

        bus.area = self.area

        bus.zone = self.zone

        bus.substation = self.substation

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
                self.x, self.y, self.h, self.w, self.area, self.zone, self.substation]

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
                'w': self.w,
                'area': self.area,
                'zone': self.zone,
                'substation': self.substation}

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
                 rate=1.0, tap=1.0, shift_angle=0, active=True, mttf=0, mttr=0,
                 branch_type: BranchType=BranchType.Line, length=1, type_obj=BranchTemplate()):
        """
        Branch model constructor
        @param bus_from: Bus Object
        @param bus_to: Bus Object
        @param name: name of the branch
        @param zserie: total branch series impedance in per unit (complex)
        @param yshunt: total branch shunt admittance in per unit (complex)
        @param rate: branch rate in MVA
        @param tap: tap module
        @param shift_angle: tap shift angle in radians
        @param mttf: Mean time to failure
        @param mttr: Mean time to repair
        @param branch_type: Is the branch a transformer?
        @param length: eventual line length in km
        @param type_obj: Type object template (i.e. Tower, TransformerType, etc...)
        """

        ReliabilityDevice.__init__(self, mttf, mttr)

        self.name = name

        # Identifier of this element type
        self.type_name = 'Branch'

        # list of properties that hold a profile
        self.properties_with_profile = None

        # connectivity
        self.bus_from = bus_from
        self.bus_to = bus_to

        # Is the branch active?
        self.active = active

        # List of measurements
        self.measurements = list()

        # line length in km
        self.length = length

        # total impedance and admittance in p.u.
        self.R = r
        self.X = x
        self.G = g
        self.B = b

        # tap changer object
        self.tap_changer = TapChanger()

        if tap != 0:
            self.tap_module = tap
            self.tap_changer.set_tap(self.tap_module)
        else:
            self.tap_module = self.tap_changer.get_tap()

        self.angle = shift_angle

        # branch rating in MVA
        self.rate = rate

        # branch type: Line, Transformer, etc...
        self.branch_type = branch_type

        # type template
        self.type_obj = type_obj

        self.edit_headers = ['name', 'bus_from', 'bus_to', 'active', 'rate', 'mttf', 'mttr', 'R', 'X', 'G', 'B',
                             'length', 'tap_module', 'angle', 'branch_type', 'type_obj']

        self.units = ['', '', '', '', 'MVA', 'h', 'h', 'p.u.', 'p.u.', 'p.u.', 'p.u.',
                      'km', 'p.u.', 'rad', '', '']

        # converter for enumerations
        self.conv = {'branch': BranchType.Branch,
                     'line': BranchType.Line,
                     'transformer': BranchType.Transformer,
                     'switch': BranchType.Switch,
                     'reactance': BranchType.Reactance}

        self.inv_conv = {val: key for key, val in self.conv.items()}

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
                           'length': float,
                           'tap_module': float,
                           'angle': float,
                           'branch_type': BranchType,
                           'type_obj': BranchTemplate}

    def branch_type_converter(self, val_string):
        """
        function to convert the branch type string into the BranchType
        :param val_string:
        :return: branch type conversion
        """
        return self.conv[val_string.lower()]

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
                   branch_type=self.branch_type,
                   type_obj=self.type_obj)

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
        if np.abs(z_series) > 0:
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
        B2[f, f] -= (b2 / (tap * conj(tap))).real
        B2[f, t] -= (b1 / conj(tap)).real
        B2[t, f] -= (b1 / tap).real
        B2[t, t] -= b2

        return f, t

    def apply_type(self, obj, Sbase, logger=list()):
        """
        Apply a transformer type definition to this object
        Args:
            obj: TransformerType or Tower object
        """

        if type(obj) is TransformerType:

            if self.branch_type == BranchType.Transformer:
                z_series, zsh = obj.get_impedances()

                y_shunt = 1 / zsh

                self.R = np.round(z_series.real, 6)
                self.X = np.round(z_series.imag, 6)
                self.G = np.round(y_shunt.real, 6)
                self.B = np.round(y_shunt.imag, 6)

                self.rate = obj.Nominal_power

                if obj != self.type_obj:
                    self.type_obj = obj
                    self.branch_type = BranchType.Transformer
            else:
                raise Exception('You are trying to apply a transformer type to a non-transformer branch')

        elif type(obj) is Tower:

            if self.branch_type == BranchType.Line:
                Vn = self.bus_to.Vnom
                Zbase = (Vn * Vn) / Sbase
                Ybase = 1 / Zbase

                z = obj.seq_resistance * self.length / Zbase
                y = obj.seq_admittance * self.length / Ybase

                self.R = np.round(z.real, 6)
                self.X = np.round(z.imag, 6)
                self.G = np.round(y.real, 6)
                self.B = np.round(y.imag, 6)

                if obj != self.type_obj:
                    self.type_obj = obj
                    self.branch_type = BranchType.Line
            else:
                raise Exception('You are trying to apply an Overhead line type to a non-line branch')

        elif type(obj) is UndergroundLineType:
            Vn = self.bus_to.Vnom
            Zbase = (Vn * Vn) / Sbase
            Ybase = 1 / Zbase

            z = obj.seq_resistance * self.length / Zbase
            y = obj.seq_admittance * self.length / Ybase

            self.R = np.round(z.real, 6)
            self.X = np.round(z.imag, 6)
            self.G = np.round(y.real, 6)
            self.B = np.round(y.imag, 6)

            if obj != self.type_obj:
                self.type_obj = obj
                self.branch_type = BranchType.Line

        elif type(obj) is SequenceLineType:

            Vn = self.bus_to.Vnom
            Zbase = (Vn * Vn) / Sbase
            Ybase = 1 / Zbase

            self.R = np.round(obj.R * self.length / Zbase, 6)
            self.X = np.round(obj.X * self.length / Zbase, 6)
            self.G = np.round(obj.G * self.length / Ybase, 6)
            self.B = np.round(obj.B * self.length / Ybase, 6)

            if obj != self.type_obj:
                self.type_obj = obj
                self.branch_type = BranchType.Line
        else:

            logger.append(self.name + ' the object type template was not recognised')

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        conv = BranchTypeConverter(None)

        if self.type_obj is None:
            type_obj = ''
        else:
            type_obj = str(self.type_obj)

        return [self.name, self.bus_from.name, self.bus_to.name, self.active, self.rate, self.mttf, self.mttr,
                self.R, self.X, self.G, self.B, self.length, self.tap_module, self.angle,
                conv.inv_conv[self.branch_type], type_obj]

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
                'length': self.length,
                'tap_module': self.tap_module,
                'tap_angle': self.angle,
                'branch_type': self.branch_type}

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

        # List of overhead line objects
        self.overhead_line_types = list()

        # list of wire types
        self.wire_types = list()

        # underground cable lines
        self.underground_cable_types = list()

        # sequence modelled lines
        self.sequence_line_types = list()

        # List of transformer types
        self.transformer_types = list()

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

    def compile(self, time_profile=None, with_profiles=True, use_opf_vals=False, dispatch_storage=False, logger=list()):
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
                logger.append('The branch ' + str(i) + ' has no rate. Setting 1e-6 to avoid zero division.')

        # Assign the power flow inputs  button
        power_flow_input.compile()
        self.power_flow_input = power_flow_input
        self.time_series_input = time_series_input
        self.monte_carlo_input = monte_carlo_input

        return logger

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

    def get_catalogue_dict(self, branches_only=False):
        """
        Returns a dictionary with the catalogue types and the associated list of objects
        :param branches_only: only branch types
        :return: dictionary
        """
        # 'Wires', 'Overhead lines', 'Underground lines', 'Sequence lines', 'Transformers'

        if branches_only:

            catalogue_dict = {'Overhead lines': self.overhead_line_types,
                              'Transformers': self.transformer_types,
                              'Underground lines': self.underground_cable_types,
                              'Sequence lines': self.sequence_line_types}
        else:
            catalogue_dict = {'Wires': self.wire_types,
                              'Overhead lines': self.overhead_line_types,
                              'Underground lines': self.underground_cable_types,
                              'Sequence lines': self.sequence_line_types,
                              'Transformers': self.transformer_types}

        return catalogue_dict

    def get_catalogue_dict_by_name(self, type_class=None):

        d = dict()

        # ['Wires', 'Overhead lines', 'Underground lines', 'Sequence lines', 'Transformers']

        if type_class is None:
            tpes = [self.overhead_line_types,
                    self.underground_cable_types,
                    self.wire_types,
                    self.transformer_types,
                    self.sequence_line_types]

        elif type_class == 'Wires':
            tpes = self.wire_types

        elif type_class == 'Overhead lines':
            tpes = self.overhead_line_types

        elif type_class == 'Underground lines':
            tpes = self.underground_cable_types

        elif type_class == 'Sequence lines':
            tpes = self.sequence_line_types

        elif type_class == 'Transformers':
            tpes = self.transformer_types

        else:
            tpes = list()

        # make dictionary
        for tpe in tpes:
            d[tpe.name] = tpe

        return d

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
        logger = list()

        if os.path.exists(filename):
            name, file_extension = os.path.splitext(filename)
            # print(name, file_extension)
            if file_extension.lower() in ['.xls', '.xlsx']:

                ppc = load_from_xls(filename)

                # Pass the table-like data dictionary to objects in this circuit
                if 'version' not in ppc.keys():
                    from GridCal.Engine.Importers.matpower_parser import interpret_data_v1
                    interpret_data_v1(self, ppc)
                    return logger
                elif ppc['version'] == 2.0:
                    self.load_excel(ppc)
                    return logger
                else:
                    warn('The file could not be processed')
                    return logger

            elif file_extension.lower() == '.dgs':
                from GridCal.Engine.Importers.DGS_Parser import dgs_to_circuit
                circ = dgs_to_circuit(filename)
                self.buses = circ.buses
                self.branches = circ.branches
                self.assign_circuit(circ)

            elif file_extension.lower() == '.m':
                from GridCal.Engine.Importers.matpower_parser import parse_matpower_file
                circ = parse_matpower_file(filename)
                self.buses = circ.buses
                self.branches = circ.branches
                self.assign_circuit(circ)

            elif file_extension.lower() == '.json':
                from GridCal.Engine.Importers.JSON_parser import parse_json
                circ = parse_json(filename)
                self.buses = circ.buses
                self.branches = circ.branches
                self.assign_circuit(circ)

            elif file_extension.lower() == '.raw':
                from GridCal.Engine.Importers.PSS_Parser import PSSeParser
                parser = PSSeParser(filename)
                circ = parser.circuit
                self.buses = circ.buses
                self.branches = circ.branches
                self.assign_circuit(circ)
                logger = parser.logger

            elif file_extension.lower() == '.xml':
                from GridCal.Engine.Importers.CIM import CIMImport
                parser = CIMImport()
                circ = parser.load_cim_file(filename)
                self.assign_circuit(circ)
                logger = parser.logger

        else:
            warn('The file does not exist.')
            logger.append(filename + ' does not exist.')

        return logger

    def assign_circuit(self, circ):
        """
        Assign a circuit object to this object
        :param circ: instance of MultiCircuit or Circuit
        """
        self.buses = circ.buses
        self.branches = circ.branches
        self.name = circ.name
        self.Sbase = circ.Sbase
        self.fBase = circ.fBase

    def load_excel(self, data):
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

        # dictionary of branch types [name] -> type object
        branch_types = dict()

        # Set comments
        self.comments = data['Comments'] if 'Comments' in data.keys() else ''

        self.time_profile = None

        self.logger = list()

        # common function
        def set_object_attributes(obj_, attr_list, values):
            for a, attr in enumerate(attr_list):

                # Hack to change the enabled by active...
                if attr == 'is_enabled':
                    attr = 'active'
                if hasattr(obj_, attr):
                    conv = obj_.edit_types[attr]  # get the type converter
                    if conv is None:
                        setattr(obj_, attr, values[a])
                    elif conv is BranchType:
                        cbr = BranchTypeConverter(None)
                        setattr(obj_, attr, cbr(values[a]))
                    else:
                        setattr(obj_, attr, conv(values[a]))
                else:
                    warn(str(obj_) + ' has no ' + attr + ' property.')

        # Add the buses ################################################################################################
        if 'bus' in data.keys():
            lst = data['bus']
            hdr = lst.columns.values
            vals = lst.values
            bus_dict = dict()
            for i in range(len(lst)):
                obj = Bus()
                set_object_attributes(obj, hdr, vals[i, :])
                bus_dict[obj.name] = obj
                self.add_bus(obj)
        else:
            self.logger.append('No buses in the file!')

        # add the loads ################################################################################################
        if 'load' in data.keys():
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
        else:
            self.logger.append('No loads in the file!')

        # add the controlled generators ################################################################################
        if 'controlled_generator' in data.keys():
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
        else:
            self.logger.append('No controlled generator in the file!')

        # add the batteries ############################################################################################
        if 'battery' in data.keys():
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
        else:
            self.logger.append('No battery in the file!')

        # add the static generators ####################################################################################
        if 'static_generator' in data.keys():
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
        else:
            self.logger.append('No static generator in the file!')

        # add the shunts ###############################################################################################
        if 'shunt' in data.keys():
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
        else:
            self.logger.append('No shunt in the file!')

        # Add the wires ################################################################################################
        if 'wires' in data.keys():
            lst = data['wires']
            hdr = lst.columns.values
            vals = lst.values
            for i in range(len(lst)):
                obj = Wire()
                set_object_attributes(obj, hdr, vals[i, :])
                self.add_wire(obj)
        else:
            self.logger.append('No wires in the file!')

        # Add the overhead_line_types ##################################################################################
        if 'overhead_line_types' in data.keys():
            lst = data['overhead_line_types']
            if data['overhead_line_types'].values.shape[0] > 0:
                for tower_name in lst['tower_name'].unique():
                    obj = Tower()
                    vals = lst[lst['tower_name'] == tower_name].values

                    # set the tower values
                    set_object_attributes(obj, obj.edit_headers, vals[0, :])

                    # add the wires
                    for i in range(vals.shape[0]):
                        wire = Wire()
                        set_object_attributes(wire, obj.get_wire_properties(), vals[i, len(obj.edit_headers):])
                        obj.wires.append(wire)

                    self.add_overhead_line(obj)
                    branch_types[str(obj)] = obj
            else:
                pass
        else:
            self.logger.append('No overhead_line_types in the file!')

        # Add the wires ################################################################################################
        if 'underground_cable_types' in data.keys():
            lst = data['underground_cable_types']
            hdr = lst.columns.values
            vals = lst.values
            # for i in range(len(lst)):
            #     obj = UndergroundLineType()
            #     set_object_attributes(obj, hdr, vals[i, :])
            #     self.underground_cable_types.append(obj)
            #     branch_types[str(obj)] = obj
        else:
            self.logger.append('No underground_cable_types in the file!')

        # Add the sequence line types ##################################################################################
        if 'sequence_line_types' in data.keys():
            lst = data['sequence_line_types']
            hdr = lst.columns.values
            vals = lst.values
            for i in range(len(lst)):
                obj = SequenceLineType()
                set_object_attributes(obj, hdr, vals[i, :])
                self.add_sequence_line(obj)
                branch_types[str(obj)] = obj
        else:
            self.logger.append('No sequence_line_types in the file!')

        # Add the transformer types ####################################################################################
        if 'transformer_types' in data.keys():
            lst = data['transformer_types']
            hdr = lst.columns.values
            vals = lst.values
            for i in range(len(lst)):
                obj = TransformerType()
                set_object_attributes(obj, hdr, vals[i, :])
                self.add_transformer_type(obj)
                branch_types[str(obj)] = obj
        else:
            self.logger.append('No transformer_types in the file!')

        # Add the branches #############################################################################################
        if 'branch' in data.keys():
            lst = data['branch']

            # fix the old 'is_transformer' property
            if 'is_transformer' in lst.columns.values:
                lst['is_transformer'] = lst['is_transformer'].map({True: 'transformer', False: 'line'})
                lst.rename(columns={'is_transformer': 'branch_type'}, inplace=True)

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

                # correct the branch template object
                template_name = str(obj.type_obj)
                if template_name in branch_types.keys():
                    obj.type_obj = branch_types[template_name]
                    print(template_name, 'updtaed!')

                # set the branch
                self.add_branch(obj)

        else:
            self.logger.append('No branches in the file!')

        # Other actions ################################################################################################
        self.logger += self.apply_all_branch_types()

    def save_file(self, file_path):
        """
        Save File
        :param file_path: 
        :return: 
        """

        if file_path.endswith('.xlsx'):
            logger = self.save_excel(file_path)
        elif file_path.endswith('.json'):
            logger = self.save_json(file_path)
        elif file_path.endswith('.xml'):
            logger = self.save_cim(file_path)
        else:
            logger = list()
            logger.append('File path extension not understood\n' + file_path)

        return logger

    def save_excel(self, file_path):
        """
        Save the circuit information
        :param file_path: file path to save
        :return:
        """
        logger = list()

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
        headers = Bus().edit_headers
        if len(self.buses) > 0:
            for elm in self.buses:

                # check name: if the name is repeated, change it so that it is not
                if elm.name in names_count.keys():
                    names_count[elm.name] += 1
                    elm.name = elm.name + '_' + str(names_count[elm.name])
                else:
                    names_count[elm.name] = 1

                obj.append(elm.get_save_data())

            dta = array(obj).astype('str')
        else:
            dta = np.zeros((0, len(headers)))

        dfs['bus'] = pd.DataFrame(data=dta, columns=headers)

        # branches #####################################################################################################
        headers = Branch(None, None).edit_headers
        if len(self.branches) > 0:
            obj = list()
            for elm in self.branches:
                obj.append(elm.get_save_data())

            dta = array(obj).astype('str')
        else:
            dta = np.zeros((0, len(headers)))

        dfs['branch'] = pd.DataFrame(data=dta, columns=headers)

        # loads ########################################################################################################
        headers = Load().edit_headers
        loads = self.get_loads()
        if len(loads) > 0:
            obj = list()
            s_profiles = None
            i_profiles = None
            z_profiles = None
            hdr = list()
            for elm in loads:
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

            dfs['load'] = pd.DataFrame(data=obj, columns=headers)

            if s_profiles is not None:
                dfs['load_Sprof'] = pd.DataFrame(data=s_profiles.astype('str'), columns=hdr, index=T)
                dfs['load_Iprof'] = pd.DataFrame(data=i_profiles.astype('str'), columns=hdr, index=T)
                dfs['load_Zprof'] = pd.DataFrame(data=z_profiles.astype('str'), columns=hdr, index=T)
        else:
            dfs['load'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # static generators ############################################################################################
        headers = StaticGenerator().edit_headers
        st_gen = self.get_static_generators()
        if len(st_gen) > 0:
            obj = list()
            hdr = list()
            s_profiles = None
            for elm in st_gen:
                obj.append(elm.get_save_data())
                hdr.append(elm.name)
                if T is not None:
                    if s_profiles is None and elm.Sprof is not None:
                        s_profiles = elm.Sprof.values
                    else:
                        s_profiles = c_[s_profiles, elm.Sprof.values]

            dfs['static_generator'] = pd.DataFrame(data=obj, columns=headers)

            if s_profiles is not None:
                dfs['static_generator_Sprof'] = pd.DataFrame(data=s_profiles.astype('str'), columns=hdr, index=T)
        else:
            dfs['static_generator'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # battery ######################################################################################################
        batteries = self.get_batteries()
        headers = Battery().edit_headers

        if len(batteries) > 0:
            obj = list()
            hdr = list()
            v_set_profiles = None
            p_profiles = None
            for elm in batteries:
                obj.append(elm.get_save_data())
                hdr.append(elm.name)
                if T is not None:
                    if p_profiles is None and elm.Pprof is not None:
                        p_profiles = elm.Pprof.values
                        v_set_profiles = elm.Vsetprof.values
                    else:
                        p_profiles = c_[p_profiles, elm.Pprof.values]
                        v_set_profiles = c_[v_set_profiles, elm.Vsetprof.values]
            dfs['battery'] = pd.DataFrame(data=obj, columns=headers)

            if p_profiles is not None:
                dfs['battery_Vset_profiles'] = pd.DataFrame(data=v_set_profiles, columns=hdr, index=T)
                dfs['battery_P_profiles'] = pd.DataFrame(data=p_profiles, columns=hdr, index=T)
        else:
            dfs['battery'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # controlled generator #########################################################################################
        con_gen = self.get_controlled_generators()
        headers = ControlledGenerator().edit_headers

        if len(con_gen) > 0:
            obj = list()
            hdr = list()
            v_set_profiles = None
            p_profiles = None
            for elm in con_gen:
                obj.append(elm.get_save_data())
                hdr.append(elm.name)
                if T is not None and elm.Pprof is not None:
                    if p_profiles is None:
                        p_profiles = elm.Pprof.values
                        v_set_profiles = elm.Vsetprof.values
                    else:
                        p_profiles = c_[p_profiles, elm.Pprof.values]
                        v_set_profiles = c_[v_set_profiles, elm.Vsetprof.values]

            dfs['controlled_generator'] = pd.DataFrame(data=obj, columns=headers)

            if p_profiles is not None:
                dfs['CtrlGen_Vset_profiles'] = pd.DataFrame(data=v_set_profiles, columns=hdr, index=T)
                dfs['CtrlGen_P_profiles'] = pd.DataFrame(data=p_profiles, columns=hdr, index=T)
        else:
            dfs['controlled_generator'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # shunt ########################################################################################################

        shunts = self.get_shunts()
        headers = Shunt().edit_headers

        if len(shunts) > 0:
            obj = list()
            hdr = list()
            y_profiles = None
            for elm in shunts:
                obj.append(elm.get_save_data())
                hdr.append(elm.name)
                if T is not None:
                    if y_profiles is None and elm.Yprof.values is not None:
                        y_profiles = elm.Yprof.values
                    else:
                        y_profiles = c_[y_profiles, elm.Yprof.values]

            dfs['shunt'] = pd.DataFrame(data=obj, columns=headers)

            if y_profiles is not None:
                dfs['shunt_Y_profiles'] = pd.DataFrame(data=y_profiles.astype(str), columns=hdr, index=T)
        else:

            dfs['shunt'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # wires ########################################################################################################

        elements = self.wire_types
        headers = Wire(name='', xpos=0, ypos=0, gmr=0, r=0, x=0, phase=0).edit_headers

        if len(elements) > 0:
            obj = list()
            for elm in elements:
                obj.append(elm.get_save_data())

            dfs['wires'] = pd.DataFrame(data=obj, columns=headers)
        else:
            dfs['wires'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # overhead cable types ######################################################################################

        elements = self.overhead_line_types
        headers = Tower().get_save_headers()

        if len(elements) > 0:
            obj = list()
            for elm in elements:
                elm.get_save_data(dta_list=obj)

            dfs['overhead_line_types'] = pd.DataFrame(data=obj, columns=headers)
        else:
            dfs['overhead_line_types'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # underground cable types ######################################################################################

        elements = self.underground_cable_types
        headers = UndergroundLineType().edit_headers

        if len(elements) > 0:
            obj = list()
            for elm in elements:
                obj.append(elm.get_save_data())

            dfs['underground_cable_types'] = pd.DataFrame(data=obj, columns=headers)
        else:
            dfs['underground_cable_types'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # sequence line types ##########################################################################################

        elements = self.sequence_line_types
        headers = SequenceLineType().edit_headers

        if len(elements) > 0:
            obj = list()
            hdr = list()
            for elm in elements:
                obj.append(elm.get_save_data())

            dfs['sequence_line_types'] = pd.DataFrame(data=obj, columns=headers)
        else:
            dfs['sequence_line_types'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # transformer types ############################################################################################

        elements = self.transformer_types
        headers = TransformerType().edit_headers

        if len(elements) > 0:
            obj = list()
            hdr = list()
            for elm in elements:
                obj.append(elm.get_save_data())

            dfs['transformer_types'] = pd.DataFrame(data=obj, columns=headers)
        else:
            dfs['transformer_types'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # flush-save ###################################################################################################
        writer = pd.ExcelWriter(file_path)
        for key in dfs.keys():
            dfs[key].to_excel(writer, key)

        writer.save()

        return logger

    def save_json(self, file_path):
        """
        
        :param file_path: 
        :return: 
        """

        from GridCal.Engine.Importers.JSON_parser import save_json_file
        logger = save_json_file(file_path, self)
        return logger

    def save_cim(self, file_path):
        """

        :param file_path:
        :return:
        """

        from GridCal.Engine.Importers.CIM import CIMExport

        cim = CIMExport(self)

        cim.save(file_name=file_path)

        return cim.logger

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

        logger = list()

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

            circuit.compile(self.time_profile, use_opf_vals=use_opf_vals, dispatch_storage=dispatch_storage, logger=logger)

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

        return logger

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

    def add_wire(self, obj: Wire):
        """
        Add wire object
        :param obj: Wire object
        """
        self.wire_types.append(obj)

    def delete_wire(self, i):
        """
        Remove wire
        :param i: index
        """
        self.wire_types.pop(i)

    def add_overhead_line(self, obj: Tower):
        """
        Add overhead line
        :param obj: Tower object
        """
        self.overhead_line_types.append(obj)

    def delete_overhead_line(self, i):

        self.overhead_line_types.pop(i)

    def add_underground_line(self, obj: UndergroundLineType):

        self.underground_cable_types.append(obj)

    def delete_underground_line(self, i):

        self.underground_cable_types.pop(i)

    def add_sequence_line(self, obj: SequenceLineType):

        self.sequence_line_types.append(obj)

    def delete_sequence_line(self, i):

        self.sequence_line_types.pop(i)

    def add_transformer_type(self, obj: TransformerType):

        self.transformer_types.append(obj)

    def delete_transformer_type(self, i):

        self.transformer_types.pop(i)

    def apply_all_branch_types(self):
        """
        Apply all the branch types
        """
        logger = list()
        for branch in self.branches:
            branch.apply_type(branch.type_obj, self.Sbase, logger=logger)

        return logger

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



