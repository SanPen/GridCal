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

from GridCal.Engine.basic_structures import CDF
from GridCal.Engine.basic_structures import BusMode
from GridCal.Engine.meta_devices import EditableDevice, ReliabilityDevice, InjectionDevice
from GridCal.Engine.device_types import TransformerType, Tower, BranchTemplate, BranchType, \
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
            self.conv[o.lower()] = v
            self.inv_conv[v] = o.lower()

    def __str__(self):
        """
        Convert value to string
        """
        return self.inv_conv[self.tpe]

    def __call__(self, str_value):
        """
        Convert from string
        """
        return self.conv[str_value.lower()]


class TimeGroups(Enum):
    NoGroup = 0,
    ByDay = 1,
    ByHour = 2


class DeviceType(Enum):
    BusDevice = 1,
    BranchDevice = 2,
    GeneratorDevice = 3,
    StaticGeneratorDevice = 4,
    BatteryDevice = 5,
    ShuntDevice = 6,
    LoadDevice = 7


########################################################################################################################
# Circuit classes
########################################################################################################################


class Bus(EditableDevice):

    def __init__(self, name="Bus", vnom=10, vmin=0.9, vmax=1.1, r_fault=0.0, x_fault=0.0,
                 xpos=0, ypos=0, height=0, width=0, active=True, is_slack=False,
                 area='Defualt', zone='Default', substation='Default'):
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

        EditableDevice.__init__(self,
                                name=name,
                                active=active,
                                type_name='Bus',
                                editable_headers={'name': ('', str, 'Name of the bus'),
                                                  'active': ('', bool, 'Is the bus active? used to disable the bus.'),
                                                  'is_slack': ('', bool, 'Force the bus to be of slack type.'),
                                                  'Vnom': ('kV', float, 'Nominal line voltage of the bus.'),
                                                  'Vmin': ('p.u.', float, 'Lower range of allowed voltage.'),
                                                  'Vmax': ('p.u.', float, 'Higher range of allowed range.'),
                                                  'r_fault': ('p.u.', float, 'Resistance of the fault.\n'
                                                                             'This is used for short circuit studies.'),
                                                  'x_fault': ('p.u.', float, 'Reactance of the fault.\n'
                                                                             'This is used for short circuit studies.'),
                                                  'x': ('px', float, 'x position in pixels.'),
                                                  'y': ('px', float, 'y position in pixels.'),
                                                  'h': ('px', float, 'height of the bus in pixels.'),
                                                  'w': ('px', float, 'Width of the bus in pixels.'),
                                                  'area': ('', str, 'Area of the bus'),
                                                  'zone': ('', str, 'Zone of the bus'),
                                                  'substation': ('', str, 'Substation of the bus.')})

        # self.name = name
        #
        # self.type_name = 'Bus'

        # self.properties_with_profile = None

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
        self.r_fault = r_fault
        self.x_fault = x_fault

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

    def determine_bus_type(self):
        """
        Infer the bus type from the devices attached to it
        @return: Nothing
        """

        gen_on = 0
        for elm in self.controlled_generators:
            if elm.active and elm.is_controlled:
                gen_on += 1

        batt_on = 0
        for elm in self.batteries:
            if elm.active and elm.is_controlled:
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
            elm.P_prof.columns = [elm.name]
            elm.P_prof.plot(ax=ax_load)

        for elm in self.controlled_generators + self.batteries:
            elm.P_prof.columns = [elm.name]
            elm.P_prof.plot(ax=ax_load)

        for elm in self.static_generators:
            elm.P_prof.columns = [elm.name]
            elm.P_prof.plot(ax=ax_load)

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

        bus.r_fault = self.r_fault

        bus.x_fault = self.x_fault

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

    # def get_save_data(self):
    #     """
    #     Return the data that matches the edit_headers
    #     :return:
    #     """
    #     self.retrieve_graphic_position()
    #     return [self.name, self.active, self.is_slack, self.Vnom, self.Vmin, self.Vmax, self.Zf,
    #             self.x, self.y, self.h, self.w, self.area, self.zone, self.substation]

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
                'rf': self.r_fault,
                'xf': self.x_fault,
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
            elm.P = elm.P_prof.values[t, 0]
            elm.Q = elm.Q_prof.values[t, 0]
            elm.Ir = elm.Ir_prof.values[t, 0]
            elm.Ii = elm.Ii_prof.values[t, 0]
            elm.G = elm.G_prof.values[t, 0]
            elm.B = elm.B_prof.values[t, 0]

        for elm in self.static_generators:
            elm.P = elm.P_prof.values[t, 0]
            elm.Q = elm.Q_prof.values[t, 0]

        for elm in self.batteries:
            elm.P = elm.P_prof.values[t, 0]
            elm.Vset = elm.Vset_prof.values[t, 0]

        for elm in self.controlled_generators:
            elm.P = elm.P_prof.values[t, 0]
            elm.Vset = elm.Vset_prof.values[t, 0]

        for elm in self.shunts:
            elm.G = elm.G_prof.values[t, 0]
            elm.B = elm.B_prof.values[t, 0]

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

    def get_fault_impedance(self):
        return complex(self.r_fault, self.x_fault)

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
        Set the integer tap position corresponding to a tap value
        @param tap_module: value like 1.05
        """
        if tap_module == 1.0:
            self.tap = 0
        elif tap_module > 1:
            self.tap = int((tap_module - 1.0) / self.inc_reg_up)
        elif tap_module < 1:
            self.tap = -int((1.0 - tap_module) / self.inc_reg_down)


class Branch(ReliabilityDevice):

    def __init__(self, bus_from: Bus, bus_to: Bus, name='Branch', r=1e-20, x=1e-20, g=1e-20, b=1e-20,
                 rate=1.0, tap=1.0, shift_angle=0, active=True, mttf=0, mttr=0, r_fault=0.0, x_fault=0.0, fault_pos=0.5,
                 branch_type: BranchType=BranchType.Line, length=1, vset=1.0, temp_base=20, temp_oper=20, alpha=0.00330,
                 bus_to_regulated=False, template=BranchTemplate(), ):
        """
        Branch model constructor
        Args:
            bus_from:Bus Object
            bus_to: Bus Object
            name: name of the branch
            r:
            x:
            g:
            b:
            rate: branch rate in MVA
            tap: tap module
            shift_angle: tap shift angle in radians
            active:
            mttf: Mean time to failure
            mttr: Mean time to repair
            r_fault:
            x_fault:
            fault_pos:
            branch_type: Is the branch a transformer?
            length: eventual line length in km
            vset: Set voltage of the tap-controlled bus in p.u.
            temp_base: Base temperature at which r is measured in ºC
            temp_oper: Operating temperature in ºC
            alpha: Thermal constant of the material in 1/ºC at temp_base (Cu = 0.00323, Al = 0.00330 @ 75ºC)
            bus_to_regulated:
            template: Type object template (i.e. Tower, TransformerType, etc...)
        """

        ReliabilityDevice.__init__(self, name,
                                   active=active,
                                   type_name='Branch',
                                   editable_headers={'name': ('', str, 'Name of the branch.'),
                                                     'bus_from': ('', Bus, 'Name of the bus at the "from" '
                                                                           'side of the branch.'),
                                                     'bus_to': ('', Bus, 'Name of the bus at the "to" '
                                                                         'side of the branch.'),
                                                     'active': ('', bool, 'Is the branch active?'),
                                                     'rate': ('MVA', float, 'Thermal rating power of the branch.'),
                                                     'mttf': ('h', float, 'Mean time to failure, '
                                                                          'used in reliability studies.'),
                                                     'mttr': ('h', float, 'Mean time to recovery, '
                                                                          'used in reliability studies.'),
                                                     'R': ('p.u.', float, 'Total resistance.'),
                                                     'X': ('p.u.', float, 'Total reactance.'),
                                                     'G': ('p.u.', float, 'Total shunt conductance.'),
                                                     'B': ('p.u.', float, 'Total shunt susceptance.'),
                                                     'length': ('km', float, 'Length of the branch '
                                                                             '(not used for calculation)'),
                                                     'tap_module': ('', float, 'Tap changer module, '
                                                                               'it a value close to 1.0'),
                                                     'angle': ('rad', float, 'Angle shift of the tap changer.'),
                                                     'bus_to_regulated': ('', bool, 'Is the bus tap regulated?'),
                                                     'vset': ('p.u.', float, 'Objective voltage at the "to" side of '
                                                                             'the bus when regulating the tap.'),
                                                     'temp_base': ('ºc', float, 'Base temperature at which R was '
                                                                                'measured.'),
                                                     'temp_oper': ('ºc', float, 'Operation temperature to modify R.'),
                                                     'alpha': ('1/K', float, 'Thermal coefficient to modify R.\n'
                                                                             'Silver: 0.0038, \n'
                                                                             'Copper: 0.00404,\n'
                                                                             'Annealed copper: 0.00393, \n'
                                                                             'Gold: 0.0034, \n'
                                                                             'Aluminium: 0.0039, \n'
                                                                             'Tungsten: 0.0045'),
                                                     'r_fault': ('p.u.', float, 'Resistance of the mid-line fault.\n'
                                                                                'Used in short circuit studies.'),
                                                     'x_fault': ('p.u.', float, 'Reactance of the mid-line fault.\n'
                                                                                'Used in short circuit studies.'),
                                                     'fault_pos': ('p.u.', float, 'Per-unit positioning of the fault:\n'
                                                                                  '0 would be at the "from" side,\n'
                                                                                  '1 would be at the "to" side,\n'
                                                                                  'therefore 0.5 is at the middle.'),
                                                     'branch_type': ('', BranchType, ''),
                                                     'template': ('', BranchTemplate, '')},
                                   mttf=mttf,
                                   mttr=mttr)

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

        # short circuit impedance
        self.r_fault = r_fault
        self.x_fault = x_fault
        self.fault_pos = fault_pos

        # total impedance and admittance in p.u.
        self.R = r
        self.X = x
        self.G = g
        self.B = b

        # Conductor base and operating temperatures in ºC
        self.temp_base = temp_base
        self.temp_oper = temp_oper

        # Conductor thermal constant (1/ºC)
        self.alpha = alpha

        # tap changer object
        self.tap_changer = TapChanger()

        # Tap module
        if tap != 0:
            self.tap_module = tap
            self.tap_changer.set_tap(self.tap_module)
        else:
            self.tap_module = self.tap_changer.get_tap()

        # Tap angle
        self.angle = shift_angle

        # branch rating in MVA
        self.rate = rate

        # branch type: Line, Transformer, etc...
        self.branch_type = branch_type

        # type template
        self.template = template
        self.bus_to_regulated = bus_to_regulated
        self.vset = vset

        self.non_editable_indices = [1, 2, 19]

        # converter for enumerations
        self.conv = {'branch': BranchType.Branch,
                     'line': BranchType.Line,
                     'transformer': BranchType.Transformer,
                     'switch': BranchType.Switch,
                     'reactance': BranchType.Reactance}

        self.inv_conv = {val: key for key, val in self.conv.items()}

    @property
    def R_corrected(self):
        """
        Returns a temperature corrected resistance based on a formula provided by:
        NFPA 70-2005, National Electrical Code, Table 8, footnote #2; and
        https://en.wikipedia.org/wiki/Electrical_resistivity_and_conductivity#Linear_approximation
        (version of 2019-01-03 at 15:20 EST).
        """
        return self.R * (1 + self.alpha * (self.temp_oper - self.temp_base))

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
                   temp_base=self.temp_base,
                   temp_oper=self.temp_oper,
                   alpha=self.alpha,
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

    def apply_tap_changer(self, tap_changer: TapChanger):
        """
        Apply a new tap changer
        Args:
            tap_changer: Tap Changer object
        """
        self.tap_changer = tap_changer

        if self.tap_module != 0:
            self.tap_changer.set_tap(self.tap_module)
        else:
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
                self.vset, self.temp_base, self.temp_base, self.alpha, self.r_fault, self.x_fault, self.fault_pos,
                conv.inv_conv[self.branch_type], template]

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
                'temp_base': self.temp_base,
                'temp_oper': self.temp_oper,
                'alpha': self.alpha,
                'tap_angle': self.angle,
                'branch_type': self.branch_type}

    def __str__(self):
        return self.name


class Load(InjectionDevice):

    def __init__(self, name='Load', G=0.0, B=0.0, Ir=0.0, Ii=0.0, P=0.0, Q=0.0,
                 G_prof=None, B_prof=None, Ir_prof=None, Ii_prof=None, P_prof=None, Q_prof=None,
                 active=True, mttf=0.0, mttr=0.0):
        """
        Load model constructor
        This model implements the so-called ZIP model
        composed of an impedance value, a current value and a power value
        Args:
            name:
            G: Conductance in equivalent MW
            B: Susceptance in equivalent MVAr
            Ir: Real current equivalent in MW
            Ii: Imaginary current equivalent in MVAr
            P: Power in MW
            Q: Reactive power in MVAr
            G_prof:
            B_prof:
            Ir_prof:
            Ii_prof:
            P_prof:
            Q_prof:
            active: is active?
            mttf: Mean time to failure (h)
            mttr: Meat time to recovery (h)
        """

        InjectionDevice.__init__(self,
                                 name=name,
                                 bus=None,
                                 active=active,
                                 type_name='Load',
                                 editable_headers={'name': ('', str, 'Load name'),
                                                   'bus': ('', None, 'Connection bus name'),
                                                   'active': ('', bool, 'Is the load active?'),
                                                   'P': ('MW', float, 'Active power'),
                                                   'Q': ('MVAr', float, 'Reactive power'),
                                                   'Ir': ('MW', float, 'Active power of the current component at V=1.0 p.u.'),
                                                   'Ii': ('MVAr', float, 'Reactive power of the current component at V=1.0 p.u.'),
                                                   'G': ('MW', float, 'Active power of the impedance component at V=1.0 p.u.'),
                                                   'B': ('MVAr', float, 'Reactive power of the impedance component at V=1.0 p.u.'),
                                                   'mttf': ('h', float, 'Mean time to failure'),
                                                   'mttr': ('h', float, 'Mean time to recovery')},
                                 mttf=mttf,
                                 mttr=mttr,
                                 properties_with_profile={'P': 'P_prof',
                                                          'Q': 'Q_prof',
                                                          'Ir': 'Ir_prof',
                                                          'Ii': 'Ii_prof',
                                                          'G': 'G_prof',
                                                          'B': 'B_prof'})

        # Impedance in equivalent MVA
        self.G = G
        self.B = B
        self.Ir = Ir
        self.Ii = Ii
        self.P = P
        self.Q = Q
        self.G_prof = G_prof
        self.B_prof = B_prof
        self.Ir_prof = Ir_prof
        self.Ii_prof = Ii_prof
        self.P_prof = P_prof
        self.Q_prof = Q_prof

    def create_profiles(self, index, S=None, I=None, Y=None):
        """
        Create the load object default profiles
        Args:
            index: DataFrame time index
            S: Array of complex power values
            I: Array of complex current values
            Y: Array of complex admittance values
        """

        self.create_S_profile(index, S)
        self.create_I_profile(index, I)
        self.create_Y_profile(index, Y)

    def create_S_profile(self, index, arr=None, arr_in_pu=False):
        """
        Create power profile based on index
        Args:
            index: time index
            arr: array
            arr_in_pu: is the array in per unit? if true, it is applied as a mask profile
        """
        if arr_in_pu:
            P = arr * self.P
            Q = arr * self.Q
        else:
            nt = len(index)
            P = np.ones(nt) * self.P if arr is None else arr
            Q = np.ones(nt) * self.Q if arr is None else arr

        self.P_prof = pd.DataFrame(data=P, index=index, columns=[self.name])
        self.Q_prof = pd.DataFrame(data=Q, index=index, columns=[self.name])

    def create_I_profile(self, index, arr, arr_in_pu=False):
        """
        Create current profile based on index
        Args:
            index: time index
            arr: array
            arr_in_pu: is the array in per unit? if true, it is applied as a mask profile
        """
        if arr_in_pu:
            Ir = arr * self.Ir
            Ii = arr * self.Ii
        else:
            nt = len(index)
            Ir = np.ones(nt) * self.Ir if arr is None else arr
            Ii = np.ones(nt) * self.Ii if arr is None else arr

        self.Ir_prof = pd.DataFrame(data=Ir, index=index, columns=[self.name])
        self.Ii_prof = pd.DataFrame(data=Ii, index=index, columns=[self.name])

    def create_Y_profile(self, index, arr, arr_in_pu=False):
        """
        Create impedance profile based on index
        Args:
            index: time index
            arr: array
            arr_in_pu: is the array in per unit? if true, it is applied as a mask profile
        Returns:

        """
        if arr_in_pu:
            G = arr * self.G
            B = arr * self.B
        else:
            nt = len(index)
            G = np.ones(nt) * self.G if arr is None else arr
            B = np.ones(nt) * self.B if arr is None else arr

        self.G_prof = pd.DataFrame(data=G, index=index, columns=[self.name])
        self.B_prof = pd.DataFrame(data=B, index=index, columns=[self.name])

    def delete_profiles(self):
        """
        Delete the object profiles
        :return:
        """
        self.P_prof = None
        self.Q_prof = None
        self.Ir_prof = None
        self.Ii_prof = None
        self.G_prof = None
        self.B_prof = None

    def set_profile_values(self, t):
        """
        Set the profile values at t
        :param t: time index
        """
        self.P = self.P_prof.values[t]
        self.Q = self.Q_prof.values[t]
        self.Ir = self.Ir_prof.values[t]
        self.Ii = self.Ii_prof.values[t]
        self.G = self.G_prof.values[t]
        self.B = self.B_prof.values[t]

    def copy(self):

        load = Load()

        load.name = self.name

        # Impedance (MVA)
        load.G = self.G
        load.B = self.B

        # Current (MVA)
        load.Ir = self.Ir
        load.Ii = self.Ii

        # Power (MVA)
        load.P = self.P
        load.Q = self.Q

        # Impedance (MVA)
        load.G_prof = self.G_prof
        load.B_prof = self.B_prof

        # Current (MVA)
        load.Ir_prof = self.Ir_prof
        load.Ii_prof = self.Ii_prof

        # Power (MVA)
        load.P_prof = self.P_prof
        load.Q_prof = self.Q_prof

        load.mttf = self.mttf

        load.mttr = self.mttr

        return load

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
                'G': self.G,
                'B': self.B,
                'Ir': self.Ir,
                'Ii': self.Ii,
                'P': self.P,
                'Q': self.Q}

    def __str__(self):
        return self.name


class StaticGenerator(InjectionDevice):

    def __init__(self, name='StaticGen', P=0.0, Q=0.0, P_prof=None, Q_prof=None, active=True, mttf=0.0, mttr=0.0):
        """
        Static generator constructor
        :param name: Name
        :param P: Active power in MW
        :param Q: Reactive power in MVAr
        :param P_prof: Profile of active power values
        :param Q_prof: Profile of reactive power values
        :param active: Active?
        :param mttf: Mean time to failure (h)
        :param mttr: MEan time to repair (h)
        """

        InjectionDevice.__init__(self,
                                 name=name,
                                 bus=None,
                                 active=active,
                                 type_name='StaticGenerator',
                                 editable_headers={'name': ('', str, ''),
                                                   'bus': ('', None, ''),
                                                   'active': ('', bool, ''),
                                                   'P': ('MW', float, 'Active power'),
                                                   'Q': ('MVAr', float, 'Reactive power'),
                                                   'mttf': ('h', float, 'Mean time to failure'),
                                                   'mttr': ('h', float, 'Mean time to recovery')},
                                 mttf=mttf,
                                 mttr=mttr,
                                 properties_with_profile={'P': 'P_prof',
                                                          'Q': 'Q_prof'})

        # Power (MW + jMVAr)
        self.P = P
        self.Q = Q

        # power profile for this load
        self.P_prof = P_prof
        self.Q_prof = Q_prof

    def copy(self):
        """
        Deep copy of this object
        :return:
        """
        return StaticGenerator(name=self.name,
                               P=self.P,
                               Q=self.Q,
                               P_prof=self.P_prof,
                               Q_prof=self.Q_prof,
                               mttf=self.mttf,
                               mttr=self.mttr)

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
                'P': self.P,
                'Q': self.Q}

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
        :param index: pandas index
        :param arr: array of values to set
        :param arr_in_pu:
        :return:
        """
        if arr_in_pu:
            P = arr * self.P
            Q = arr * self.Q
        else:
            P = np.ones(len(index)) * self.P if arr is None else arr
            Q = np.ones(len(index)) * self.Q if arr is None else arr

        self.P_prof = pd.DataFrame(data=P, index=index, columns=[self.name])
        self.Q_prof = pd.DataFrame(data=Q, index=index, columns=[self.name])

    def create_profile(self, magnitude, index, arr, arr_in_pu=False):
        """
        Create power profile based on index
        :param magnitude: name of the property
        :param index: pandas index
        :param arr: array of values to set
        :param arr_in_pu: is the array in per-unit?
        """
        x = getattr(self, magnitude)
        x_prof = getattr(self, self.properties_with_profile[magnitude])

        if arr_in_pu:
            val = arr * x
        else:
            val = np.ones(len(index)) * x if arr is None else arr

        x_prof = pd.DataFrame(data=val, index=index, columns=[self.name])

    def delete_profiles(self):
        """
        Delete the object profiles
        :return:
        """
        self.P_prof = None
        self.Q_prof = None

    def set_profile_values(self, t):
        """
        Set the profile values at t
        :param t: time index
        """
        self.P = self.P_prof.values[t]
        self.Q = self.Q_prof.values[t]

    def __str__(self):
        return self.name


class Generator(InjectionDevice):

    def __init__(self, name='gen', active_power=0.0, power_factor=0.8, voltage_module=1.0, is_controlled=True,
                 Qmin=-9999, Qmax=9999, Snom=9999, power_prof=None, power_factor_prof=None, vset_prof=None, active=True,
                 p_min=0.0, p_max=9999.0, op_cost=1.0, Sbase=100, enabled_dispatch=True, mttf=0.0, mttr=0.0):
        """
        Voltage controlled generator
        @param name: Name of the device
        @param active_power: Active power (MW)
        @param power_factor: Power factor
        @param voltage_module: Voltage set point (p.u.)
        @param Qmin: minimum reactive power in MVAr
        @param Qmax: maximum reactive power in MVAr
        @param Snom: Nominal power in MVA
        @param power_prof: active power profile (Pandas DataFrame)
        @param power_factor_prof: active power profile (Pandas DataFrame)
        @param vset_prof: voltage set point profile (Pandas DataFrame)
        @param active: Is the generator active?
        @param p_min: minimum dispatchable power in MW
        @param p_max maximum dispatchable power in MW
        @param op_cost operational cost in Eur (or other currency) per MW
        @param enabled_dispatch is the generator enabled for OPF?
        @param mttf: Mean time to failure
        @param mttr: Mean time to repair

        """

        InjectionDevice.__init__(self,
                                 name=name,
                                 bus=None,
                                 active=active,
                                 type_name='Generator',
                                 editable_headers={'name': ('', str, 'Name of the generator'),
                                                   'bus': ('', None, 'Connection bus name'),
                                                   'active': ('', bool, 'Is the generator active?'),
                                                   'is_controlled': ('', bool, 'Is this generator voltage-controlled?'),
                                                   'P': ('MW', float, 'Active power'),
                                                   'Pf': ('', float, 'Power factor (cos(fi)). This is used for non-controlled generators.'),
                                                   'Vset': ('p.u.', float, 'Set voltage. This is used for controlled generators.'),
                                                   'Snom': ('MVA', float, 'Nomnial power.'),
                                                   'Qmin': ('MVAr', float, 'Minimum reactive power.'),
                                                   'Qmax': ('MVAr', float, 'Maximum reactive power.'),
                                                   'Pmin': ('MW', float, 'Minimum active power. Used in OPF.'),
                                                   'Pmax': ('MW', float, 'Maximum active power. Used in OPF.'),
                                                   'Cost': ('e/MWh', float, 'Generation unitary cost. Used in OPF.'),
                                                   'enabled_dispatch': ('', bool, 'Enabled for dispatch? Used in OPF.'),
                                                   'mttf': ('h', float, 'Mean time to failure'),
                                                   'mttr': ('h', float, 'Mean time to recovery')},
                                 mttf=mttf,
                                 mttr=mttr,
                                 properties_with_profile={'P': 'P_prof',
                                                          'Pf': 'Pf_prof',
                                                          'Vset': 'Vset_prof'})

        # is the device active active power dispatch?
        self.enabled_dispatch = enabled_dispatch

        # Power (MVA)
        self.P = active_power

        # Power factor
        self.Pf = power_factor

        # voltage set profile for this load in p.u.
        self.Pf_prof = power_factor_prof

        # If this generator is voltage controlled it produces a PV node, otherwise the node remains as PQ
        self.is_controlled = is_controlled

        # Nominal power in MVA (also the machine base)
        self.Snom = Snom

        # Minimum dispatched power in MW
        self.Pmin = p_min

        # Maximum dispatched power in MW
        self.Pmax = p_max

        # power profile for this load in MW
        self.P_prof = power_prof

        # Voltage module set point (p.u.)
        self.Vset = voltage_module

        # voltage set profile for this load in p.u.
        self.Vset_prof = vset_prof

        # minimum reactive power in MVAr
        self.Qmin = Qmin

        # Maximum reactive power in MVAr
        self.Qmax = Qmax

        # Cost of operation €/MW
        self.Cost = op_cost

        # Dynamic vars
        # self.Ra = Ra
        # self.Xa = Xa
        # self.Xd = Xd
        # self.Xq = Xq
        # self.Xdp = Xdp
        # self.Xqp = Xqp
        # self.Xdpp = Xdpp
        # self.Xqpp = Xqpp
        # self.Td0p = Td0p
        # self.Tq0p = Tq0p
        # self.Td0pp = Td0pp
        # self.Tq0pp = Tq0pp
        # self.H = H
        # self.speed_volt = speed_volt
        # self.base_mva = base_mva  # machine base MVA

        # system base power MVA
        self.Sbase = Sbase

        # Linear problem generator dispatch power variable (in p.u.)
        self.lp_name = self.type_name + '_' + self.name + str(id(self))

        # variable to dispatch the power in a Linear program
        self.LPVar_P = pulp.LpVariable(self.lp_name + '_P', self.Pmin / self.Sbase, self.Pmax / self.Sbase)

        # list of variables of active power dispatch in a series of linear programs
        self.LPVar_P_prof = None

    def copy(self):
        """
        Make a deep copy of this object
        :return: Copy of this object
        """

        # make a new instance (separated object in memory)
        gen = Generator()

        gen.name = self.name

        # Power (MVA)
        # MVA = kV * kA
        gen.P = self.P

        # is the generator active?
        gen.active = self.active

        # power profile for this load
        gen.P_prof = self.P_prof

        # Power factor profile
        gen.Pf_prof = self.Pf_prof

        # Voltage module set point (p.u.)
        gen.Vset = self.Vset

        # voltage set profile for this load
        gen.Vset_prof = self.Vset_prof

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
                'is_controlled': self.is_controlled,
                'P': self.P,
                'Pf': self.Pf,
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
            self.create_profiles(index, P=arr, V=None, Pf=None)
        if mag == 'Pf':
            self.create_profiles(index, P=None, V=None, Pf=arr)
        elif mag == 'V':
            self.create_profiles(index, P=None, V=arr, Pf=None)
        else:
            raise Exception('Magnitude ' + mag + ' not supported')

    def create_profiles(self, index, P=None, V=None, Pf=None):
        """
        Create the load object default profiles
        Args:
            index: time index associated
            P: Active power (MW)
            Pf: Power factor
            V: voltage set points
        """
        self.create_P_profile(index, P)
        self.create_Pf_profile(index, Pf)
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
        self.P_prof = pd.DataFrame(data=dta, index=index, columns=[self.name])

    def create_Pf_profile(self, index, arr=None, arr_in_pu=False):
        """
        Create power profile based on index
        Args:
            index: time index associated
            arr: array of values
            arr_in_pu: is the array in per unit?
        """
        if arr_in_pu:
            dta = arr * self.Pf
        else:
            dta = np.ones(len(index)) * self.Pf if arr is None else arr
        self.Pf_prof = pd.DataFrame(data=dta, index=index, columns=[self.name])

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

        self.Vset_prof = pd.DataFrame(data=dta, index=index, columns=[self.name])

    def get_profiles(self, index=None, use_opf_vals=False):
        """
        Get profiles and if the index is passed, create the profiles if needed
        Args:
            index: index of the Pandas DataFrame

        Returns:
            Power, Current and Impedance profiles
        """
        if index is not None:
            if self.P_prof is None:
                self.create_P_profile(index)
            if self.Pf_prof is None:
                self.create_Pf_profile(index)
            if self.Vset_prof is None:
                self.create_Vset_profile(index)

        if use_opf_vals:
            return self.get_lp_var_profile(index), self.Vset_prof
        else:
            return self.P_prof, self.Vset_prof

    def delete_profiles(self):
        """
        Delete the object profiles
        :return:
        """
        self.P_prof = None
        self.Vset_prof = None

    def set_profile_values(self, t):
        """
        Set the profile values at t
        :param t: time index
        """
        self.P = self.P_prof.values[t]
        self.Vset = self.Vset_prof.values[t]

    def apply_lp_vars(self, at=None):
        """
        Set the LP vars to the main value or the profile
        """
        if self.LPVar_P is not None:
            if at is None:
                self.P = self.LPVar_P.value()
            else:
                self.P_prof.values[at] = self.LPVar_P.value()

    def apply_lp_profile(self, Sbase):
        """
        Set LP profile to the regular profile
        :return:
        """
        n = self.P_prof.shape[0]
        if self.active and self.enabled_dispatch:
            for i in range(n):
                self.P_prof.values[i] = self.LPVar_P_prof[i].value() * Sbase
        else:
            # there are no values in the LP vars because this generator is deactivated,
            # therefore fill the profiles with zeros when asked to copy the lp vars to the power profiles
            self.P_prof.values = np.zeros(self.P_prof.shape[0])

    def __str__(self):
        return self.name


class Battery(Generator):

    def __init__(self, name='batt', active_power=0.0, power_factor=0.8, voltage_module=1.0,
                 is_controlled=True, Qmin=-9999, Qmax=9999, Snom=9999, Enom=9999, p_min=-9999, p_max=9999,
                 op_cost=1.0, power_prof=None, power_factor_prof=None, vset_prof=None, active=True, Sbase=100,
                 enabled_dispatch=True, mttf=0.0, mttr=0.0, charge_efficiency=0.9, discharge_efficiency=0.9,
                 max_soc=0.99, min_soc=0.3, soc=0.8, charge_per_cycle=0.1, discharge_per_cycle=0.1):
        """
        Battery (Voltage controlled and dispatchable)
        :param name: Name of the device
        :param active_power: Active power (MW)
        :param power_factor: power factor
        :param voltage_module: Voltage set point (p.u.)
        :param: is_voltage_controlled: Is the unit voltage controlled (if so, the connection bus becomes a PV bus)
        :param Qmin: minimum reactive power in MVAr
        :param Qmax: maximum reactive power in MVAr
        :param Snom: Nominal power in MVA
        :param Enom: Nominal energy in MWh
        :param power_prof: active power profile (Pandas DataFrame)
        :param power_factor_prof: power factor profile
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
        Generator.__init__(self, name=name,
                           active_power=active_power,
                           power_factor=power_factor,
                           voltage_module=voltage_module,
                           is_controlled=is_controlled,
                           Qmin=Qmin, Qmax=Qmax, Snom=Snom,
                           power_prof=power_prof,
                           power_factor_prof=power_factor_prof,
                           vset_prof=vset_prof,
                           active=active,
                           p_min=p_min, p_max=p_max,
                           op_cost=op_cost,
                           Sbase=Sbase,
                           enabled_dispatch=enabled_dispatch,
                           mttf=mttf,
                           mttr=mttr)

        # type of this device
        self.type_name = 'Battery'

        # manually modify the editable headers
        self.editable_headers = {'name': ('', str, 'Name of the battery'),
                                 'bus': ('', None, 'Connection bus name'),
                                 'active': ('', bool, 'Is the battery active?'),
                                 'is_controlled': ('', bool, 'Is this battery voltage-controlled?'),
                                 'P': ('MW', float, 'Active power'),
                                 'Pf': ('', float, 'Power factor (cos(fi)). This is used for non-controlled batteries.'),
                                 'Vset': ('p.u.', float, 'Set voltage. This is used for controlled batteries.'),
                                 'Snom': ('MVA', float, 'Nomnial power.'),
                                 'Enom': ('MWh', float, 'Nominal energy capacity.'),
                                 'max_soc': ('p.u.', float, 'Minimum state of charge.'),
                                 'min_soc': ('p.u.', float, 'Maximum state of charge.'),
                                 'soc_0': ('p.u.', float, 'Initial state of charge.'),
                                 'charge_efficiency': ('p.u.', float, 'Charging efficiency.'),
                                 'discharge_efficiency': ('p.u.', float, 'Discharge efficiency.'),
                                 'discharge_per_cycle': ('p.u.', float, ''),
                                 'Qmin': ('MVAr', float, 'Minimum reactive power.'),
                                 'Qmax': ('MVAr', float, 'Maximum reactive power.'),
                                 'Pmin': ('MW', float, 'Minimum active power. Used in OPF.'),
                                 'Pmax': ('MW', float, 'Maximum active power. Used in OPF.'),
                                 'Cost': ('e/MWh', float, 'Generation unitary cost. Used in OPF.'),
                                 'enabled_dispatch': ('', bool, 'Enabled for dispatch? Used in OPF.'),
                                 'mttf': ('h', float, 'Mean time to failure'),
                                 'mttr': ('h', float, 'Mean time to recovery')}

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
        batt.P_prof = self.P_prof

        # Voltage module set point (p.u.)
        batt.Vset = self.Vset

        # voltage set profile for this load
        batt.Vset_prof = self.Vset_prof

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
        self.P_prof = pd.DataFrame(data=dta, index=index, columns=[self.name])

        self.power_array = pd.DataFrame(data=dta.copy(), index=index, columns=[self.name])
        self.energy_array = pd.DataFrame(data=dta.copy(), index=index, columns=[self.name])

    def reset(self):
        """
        Set he battery to its initial state
        """
        self.soc = self.soc_0
        self.energy = self.Enom * self.soc
        dta = self.P_prof.values.copy()
        index = self.P_prof.index
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
        power_value = self.P_prof.values[t]

        processed_power, processed_energy = self.process(power_value, dt)

        if store_values:
            self.energy_array.values[t] = processed_energy
            self.power_array.values[t] = processed_power

        return processed_power


class Shunt(InjectionDevice):

    def __init__(self, name='shunt', G=0.0, B=0.0, G_prof=None, B_prof=None, active=True, mttf=0.0, mttr=0.0):
        """
        Shunt object
        :param name:
        :param G: Conductance in MW at 1 p.u. voltage
        :param B: Susceptance in MW at 1 p.u. voltage
        :param G_prof:
        :param B_prof:
        :param active: Is active True or False
        :param mttf:
        :param mttr:
        """

        InjectionDevice.__init__(self,
                                 name=name,
                                 bus=None,
                                 active=active,
                                 type_name='Shunt',
                                 editable_headers={'name': ('', str, 'Shunt name'),
                                                   'bus': ('', None, 'Connection bus name'),
                                                   'active': ('', bool, 'Is the shunt active?'),
                                                   'G': ('MW', float, 'Active power of the impedance component at V=1.0 p.u.'),
                                                   'B': ('MVAr', float, 'Reactive power of the impedance component at V=1.0 p.u.'),
                                                   'mttf': ('h', float, 'Mean time to failure'),
                                                   'mttr': ('h', float, 'Mean time to recovery')},
                                 mttf=mttf,
                                 mttr=mttr,
                                 properties_with_profile={'G': 'G_prof',
                                                          'B': 'B_prof'})

        # The bus this element is attached to: Not necessary for calculations
        self.bus = None

        # Impedance (MVA)
        self.G = G
        self.B = B

        # admittance profile
        self.G_prof = G_prof
        self.B_prof = B_prof

    def copy(self):
        """
        Copy of this object
        :return: a copy of this object
        """
        shu = Shunt(name=self.name,
                    G=self.G,
                    B=self.B,
                    G_prof=self.G_prof,
                    B_prof=self.B_prof,
                    active=self.active,
                    mttf=self.mttf,
                    mttr=self.mttr)
        return shu

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
                'g': self.G,
                'b': self.B}

