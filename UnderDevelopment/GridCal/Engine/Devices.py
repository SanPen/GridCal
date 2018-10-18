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


from enum import Enum
from warnings import warn
import pandas as pd
import pulp
import numpy as np
from matplotlib import pyplot as plt

from GridCal.Engine.BasicStructures import CDF
from GridCal.Engine.BasicStructures import BusMode
from GridCal.Engine.Numerical.DynamicModels import DynamicModels
from GridCal.Engine.DeviceTypes import TransformerType, Tower, BranchTemplate, BranchType, \
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


class DeviceType(Enum):
    BusDevice = 1,
    BranchDevice = 2,
    ControlledGeneratorDevice = 3,
    StaticGeneratorDevice = 4,
    BatteryDevice = 5,
    ShuntDevice = 6,
    LoadDevice = 7


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
        t = np.zeros(n_samples)
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

        return self.type

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

    def plot_profiles(self, ax_load=None, ax_voltage=None, time_series=None, my_index=0):
        """

        @param time_idx: Master time profile: usually stored in the circuit
        @param ax_load: Figure axis, if not provided one will be created
        @return:
        """

        if ax_load is None:
            fig = plt.figure()
            if time_series is not None:
                # 2 plots: load + voltage
                ax_load = fig.add_subplot(211)
                ax_voltage = fig.add_subplot(212)
            else:
                # only 1 plot: load
                ax_load = fig.add_subplot(111)
                ax_voltage = None
            show_fig = True
        else:
            show_fig = False

        for elm in self.loads:
            # ax_load.plot(elm.Sprof.index, elm.Sprof.values.real, label=elm.name)
            elm.Sprof.columns = [elm.name]
            elm.Sprof.plot(ax=ax_load)

        for elm in self.controlled_generators + self.batteries:
            # ax_load.plot(elm.Pprof.index, elm.Pprof.values, label=elm.name)
            elm.Pprof.columns = [elm.name]
            elm.Pprof.plot(ax=ax_load)

        for elm in self.static_generators:
            # ax_load.plot(elm.Sprof.index, elm.Sprof.values.real, label=elm.name)
            elm.Sprof.columns = [elm.name]
            elm.Sprof.plot(ax=ax_load)

        if time_series is not None:
            y = time_series.results.voltage
            x = time_series.results.time
            df = pd.DataFrame(data=y[:, my_index], index=x, columns=[self.name])
            df.plot(ax=ax_voltage)

        plt.legend()
        plt.title(self.name)
        ax_load.set_ylabel('MW')
        if ax_voltage is not None:
            ax_voltage.set_ylabel('Voltage (p.u.)')
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

    def merge(self, other_bus):

        # List of load s attached to this bus
        self.loads += other_bus.loads

        # List of Controlled generators attached to this bus
        self.controlled_generators += other_bus.controlled_generators

        # List of shunt s attached to this bus
        self.shunts += other_bus.shunts

        # List of batteries attached to this bus
        self.batteries += other_bus.batteries

        # List of static generators attached tot this bus
        self.static_generators += other_bus.static_generators

        # List of measurements
        self.measurements += other_bus.measurements

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
                 rate=1.0, tap=1.0, shift_angle=0, active=True, mttf=0, mttr=0, branch_type: BranchType=BranchType.Line,
                 length=1, vset=1.0, bus_to_regulated=False, template=BranchTemplate()):
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
        @param template: Type object template (i.e. Tower, TransformerType, etc...)
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
        self.template = template
        self.bus_to_regulated = bus_to_regulated
        self.vset = vset

        self.edit_headers = ['name', 'bus_from', 'bus_to', 'active', 'rate', 'mttf', 'mttr', 'R', 'X', 'G', 'B',
                             'length', 'tap_module', 'angle', 'bus_to_regulated', 'vset', 'branch_type', 'template']

        self.units = ['', '', '', '', 'MVA', 'h', 'h', 'p.u.', 'p.u.', 'p.u.', 'p.u.',
                      'km', 'p.u.', 'rad', '', 'p.u.', '', '']

        self.non_editable_indices = [1, 2, 17]

        # converter for enumerations
        self.conv = {'branch': BranchType.Branch,
                     'line': BranchType.Line,
                     'transformer': BranchType.Transformer,
                     'switch': BranchType.Switch,
                     'reactance': BranchType.Reactance}

        self.inv_conv = {val: key for key, val in self.conv.items()}

        self.edit_types = {'name': str,
                           'bus_from': Bus,
                           'bus_to': Bus,
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
                           'bus_to_regulated': bool,
                           'vset': float,
                           'branch_type': BranchType,
                           'template': BranchTemplate}

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
                   bus_to_regulated=self.bus_to_regulated,
                   vset=self.vset,
                   branch_type=self.branch_type,
                   template=self.template)

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

    def get_virtual_taps(self):
        """
        Get the branch virtual taps

        The virtual taps generate when a transformer nominal winding voltage differs from the bus nominal voltage
        Returns:
            virtual taps at the from and to sides
        """
        if self.branch_type == BranchType.Transformer and type(self.template) == TransformerType:
            # resolve how the transformer is actually connected and set the virtual taps
            bus_f_v = self.bus_from.Vnom
            bus_t_v = self.bus_to.Vnom

            dhf = abs(self.template.HV_nominal_voltage - bus_f_v)
            dht = abs(self.template.HV_nominal_voltage - bus_t_v)

            if dhf < dht:
                # the HV side is on the from side
                tpe_f_v = self.template.HV_nominal_voltage
                tpe_t_v = self.template.LV_nominal_voltage
            else:
                # the HV side is on the to side
                tpe_t_v = self.template.HV_nominal_voltage
                tpe_f_v = self.template.LV_nominal_voltage

            tap_f = tpe_f_v / bus_f_v
            tap_t = tpe_t_v / bus_t_v
            return tap_f, tap_t
        else:
            return 1.0, 1.0

    def apply_template(self, obj, Sbase, logger=list()):
        """
        Apply a branch template to this object
        Args:
            obj: TransformerType or Tower object
        """

        if type(obj) is TransformerType:

            if self.branch_type == BranchType.Transformer:

                # get the transformer impedance in the base of the transformer
                z_series, zsh = obj.get_impedances()

                # Change the impedances to the system base
                base_change = Sbase / obj.Nominal_power
                z_series *= base_change
                zsh *= base_change

                # compute the shunt admittance
                y_shunt = 1.0 / zsh

                self.R = np.round(z_series.real, 6)
                self.X = np.round(z_series.imag, 6)
                self.G = np.round(y_shunt.real, 6)
                self.B = np.round(y_shunt.imag, 6)

                self.rate = obj.Nominal_power

                if obj != self.template:
                    self.template = obj
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

                if obj != self.template:
                    self.template = obj
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

            if obj != self.template:
                self.template = obj
                self.branch_type = BranchType.Line

        elif type(obj) is SequenceLineType:

            Vn = self.bus_to.Vnom
            Zbase = (Vn * Vn) / Sbase
            Ybase = 1 / Zbase

            self.R = np.round(obj.R * self.length / Zbase, 6)
            self.X = np.round(obj.X * self.length / Zbase, 6)
            self.G = np.round(obj.G * self.length / Ybase, 6)
            self.B = np.round(obj.B * self.length / Ybase, 6)

            if obj != self.template:
                self.template = obj
                self.branch_type = BranchType.Line
        elif type(obj) is BranchTemplate:
            # this is the default template that does nothing
            pass
        else:
            logger.append(self.name + ' the object type template was not recognised')

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        conv = BranchTypeConverter(None)

        if self.template is None:
            template = ''
        else:
            template = str(self.template)

        return [self.name, self.bus_from.name, self.bus_to.name, self.active, self.rate, self.mttf, self.mttr,
                self.R, self.X, self.G, self.B, self.length, self.tap_module, self.angle, self.bus_to_regulated,
                self.vset, conv.inv_conv[self.branch_type], template]

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
                'bus_to_regulated': self.bus_to_regulated,
                'vset': self.vset,
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

        if impedance.real != 0 or impedance.imag != 0.0:
            self.Y = 1 / impedance
        else:
            self.Y = complex(0, 0)

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
            dta = np.ones(nt) * self.S if arr is None else arr
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
            dta = np.ones(len(index)) * self.I if arr is None else arr
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
            dta = np.ones(len(index)) * self.Z if arr is None else arr
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
            dta = np.ones(len(index)) * self.S if arr is None else arr
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
            dta = np.ones(len(index)) * self.P if arr is None else arr
        self.Pprof = pd.DataFrame(data=dta, index=index, columns=[self.name])

    def initialize_lp_vars(self):
        """
        Initialize the LP variables
        """
        self.lp_name = self.type_name + '_' + self.name + str(id(self))

        self.LPVar_P = pulp.LpVariable(self.lp_name + '_P', self.Pmin / self.Sbase, self.Pmax / self.Sbase)

        # self.LPVar_P_prof = [pulp.LpVariable(self.lp_name + '_P_' + str(t),
        #                                      self.Pmin / self.Sbase,
        #                                      self.Pmax / self.Sbase) for t in range(self.Pprof.shape[0])]

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
            dta = np.ones(len(index)) * self.Vset if arr is None else arr

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
            self.Pprof.values = np.zeros(self.Pprof.shape[0])

    def __str__(self):
        return self.name


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
            dta = np.ones(len(index)) * self.P if arr is None else arr
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
            dta = np.ones(len(index)) * self.Y if arr is None else arr
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

