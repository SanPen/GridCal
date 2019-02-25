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
from GridCal.Engine.meta_devices import EditableDevice, DeviceType, GCProp
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

########################################################################################################################
# Circuit classes
########################################################################################################################


class Bus(EditableDevice):
    """
    The Bus object is the container of all the possible devices that can be attached to
    a bus bar or substation. Such objects can be loads, voltage controlled generators,
    static generators, batteries, shunt elements, etc.

    Arguments:

        **name** (str, "Bus"): Name of the bus

        **vnom** (float, 10.0): Nominal voltage in kV

        **vmin** (float, 0.9): Minimum per unit voltage

        **vmax** (float, 1.1): Maximum per unit voltage

        **r_fault** (float, 0.0): Resistance of the fault in per unit (SC only)

        **x_fault** (float, 0.0): Reactance of the fault in per unit (SC only)

        **xpos** (int, 0): X position in pixels (GUI only)

        **ypos** (int, 0): Y position in pixels (GUI only)

        **height** (int, 0): Height of the graphic object (GUI only)

        **width** (int, 0): Width of the graphic object (GUI only)

        **active** (bool, True): Is the bus active?

        **is_slack** (bool, False): Is this bus a slack bus?

        **area** (str, "Default"): Name of the area

        **zone** (str, "Default"): Name of the zone

        **substation** (str, "Default"): Name of the substation

    Additional Properties:

        **Qmin_sum** (float, 0): Minimum reactive power of this bus (inferred from the devices)

        **Qmax_sum** (float, 0): Maximum reactive power of this bus (inferred from the devices)

        **loads** (list, list()): List of loads attached to this bus

        **controlled_generators** (list, list()): List of controlled generators attached to this bus

        **shunts** (list, list()): List of shunts attached to this bus

        **batteries** (list, list()): List of batteries attached to this bus

        **static_generators** (list, list()): List of static generators attached to this bus

        **measurements** (list, list()): List of measurements

    """

    def __init__(self, name="Bus", vnom=10, vmin=0.9, vmax=1.1, r_fault=0.0, x_fault=0.0,
                 xpos=0, ypos=0, height=0, width=0, active=True, is_slack=False,
                 area='Default', zone='Default', substation='Default'):

        EditableDevice.__init__(self,
                                name=name,
                                active=active,
                                device_type=DeviceType.BusDevice,
                                editable_headers={'name': GCProp('', str, 'Name of the bus'),
                                                  'active': GCProp('', bool,
                                                                   'Is the bus active? used to disable the bus.'),
                                                  'is_slack': GCProp('', bool,
                                                                     'Force the bus to be of slack type.'),
                                                  'Vnom': GCProp('kV', float,
                                                                 'Nominal line voltage of the bus.'),
                                                  'Vmin': GCProp('p.u.', float,
                                                                 'Lower range of allowed voltage.'),
                                                  'Vmax': GCProp('p.u.', float,
                                                                 'Higher range of allowed range.'),
                                                  'r_fault': GCProp('p.u.', float,
                                                                    'Resistance of the fault.\n'
                                                                    'This is used for short circuit studies.'),
                                                  'x_fault': GCProp('p.u.', float,
                                                                    'Reactance of the fault.\n'
                                                                    'This is used for short circuit studies.'),
                                                  'x': GCProp('px', float, 'x position in pixels.'),
                                                  'y': GCProp('px', float, 'y position in pixels.'),
                                                  'h': GCProp('px', float, 'height of the bus in pixels.'),
                                                  'w': GCProp('px', float, 'Width of the bus in pixels.'),
                                                  'area': GCProp('', str, 'Area of the bus'),
                                                  'zone': GCProp('', str, 'Zone of the bus'),
                                                  'substation': GCProp('', str, 'Substation of the bus.')},
                                non_editable_attributes=list(),
                                properties_with_profile=dict())

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

    def create_profiles(self, index):
        """
        Delete all profiles
        :return:
        """
        for elm in self.loads:
            elm.create_profiles(index)

        for elm in self.static_generators:
            elm.create_profiles(index)

        for elm in self.batteries:
            elm.create_profiles(index)

        for elm in self.controlled_generators:
            elm.create_profiles(index)

        for elm in self.shunts:
            elm.create_profiles(index)

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


class TapChanger:
    """
    The **TapChanger** class defines a transformer's tap changer, either onload or
    offload. It needs to be attached to a predefined transformer (i.e. a
    :ref:`Branch<branch>` object).
    
    The following example shows how to attach a tap changer to a transformer tied to a
    voltage regulated :ref:`bus`:

    .. code:: ipython3

        from GridCal.Engine.Core.multi_circuit import MultiCircuit
        from GridCal.Engine.devices import *
        from GridCal.Engine.device_types import *

        # Create grid
        grid = MultiCircuit()

        # Create buses
        POI = Bus(name="POI",
                  vnom=100, #kV
                  is_slack=True)
        grid.add_bus(POI)

        B_C3 = Bus(name="B_C3",
                   vnom=10) #kV
        grid.add_bus(B_C3)

        # Create transformer types
        SS = TransformerType(name="SS",
                             hv_nominal_voltage=100, # kV
                             lv_nominal_voltage=10, # kV
                             nominal_power=100, # MVA
                             copper_losses=10000, # kW
                             iron_losses=125, # kW
                             no_load_current=0.5, # %
                             short_circuit_voltage=8) # %
        grid.add_transformer_type(SS)

        # Create transformer
        X_C3 = Branch(bus_from=POI,
                      bus_to=B_C3,
                      name="X_C3",
                      branch_type=BranchType.Transformer,
                      template=SS,
                      bus_to_regulated=True,
                      vset=1.05)

        # Attach tap changer
        X_C3.tap_changer = TapChanger(taps_up=16, taps_down=16, max_reg=1.1, min_reg=0.9)
        X_C3.tap_changer.set_tap(X_C3.tap_module)

        # Add transformer to grid
        grid.add_branch(X_C3)
    
    Arguments:

        **taps_up** (int, 5): Number of taps position up

        **taps_down** (int, 5): Number of tap positions down

        **max_reg** (float, 1.1): Maximum regulation up i.e 1.1 -> +10%

        **min_reg** (float, 0.9): Maximum regulation down i.e 0.9 -> -10%

    Additional Properties:

        **tap** (int, 0): Current tap position

    """

    def __init__(self, taps_up=5, taps_down=5, max_reg=1.1, min_reg=0.9):
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

        Attribute:

            **tap_module** (float): Tap module centered around 1.0

        """
        if tap_module == 1.0:
            self.tap = 0
        elif tap_module > 1:
            self.tap = int((tap_module - 1.0) / self.inc_reg_up)
        elif tap_module < 1:
            self.tap = -int((1.0 - tap_module) / self.inc_reg_down)


class Branch(EditableDevice):
    """
    The **Branch** class represents the connections between nodes (i.e.
    :ref:`buses<bus>`) in **GridCal**. A branch is an element (cable, line, capacitor,
    transformer, etc.) with an electrical impedance. The basic **Branch** class
    includes basic electrical attributes for most passive elements, but other
    :ref:`device types<device_types>` may be passed to the **Branch** constructor to
    configure it as a specific type.

    For example, a transformer may be created with the following code:

    .. code:: ipython3

        from GridCal.Engine.Core.multi_circuit import MultiCircuit
        from GridCal.Engine.devices import *
        from GridCal.Engine.device_types import *

        # Create grid
        grid = MultiCircuit()

        # Create buses
        POI = Bus(name="POI",
                  vnom=100, #kV
                  is_slack=True)
        grid.add_bus(POI)

        B_C3 = Bus(name="B_C3",
                   vnom=10) #kV
        grid.add_bus(B_C3)

        # Create transformer types
        SS = TransformerType(name="SS",
                             hv_nominal_voltage=100, # kV
                             lv_nominal_voltage=10, # kV
                             nominal_power=100, # MVA
                             copper_losses=10000, # kW
                             iron_losses=125, # kW
                             no_load_current=0.5, # %
                             short_circuit_voltage=8) # %
        grid.add_transformer_type(SS)

        # Create transformer
        X_C3 = Branch(bus_from=POI,
                      bus_to=B_C3,
                      name="X_C3",
                      branch_type=BranchType.Transformer,
                      template=SS,
                      )

        # Add transformer to grid
        grid.add_branch(X_C3)

    Refer to the :ref:`TapChanger<tap_changer>` class for an example using a
    voltage regulator.

    Arguments:

        **bus_from** (:ref:`Bus`): "From" :ref:`bus<Bus>` object

        **bus_to** (:ref:`Bus`): "To" :ref:`bus<Bus>` object
        
        **name** (str, "Branch"): Name of the branch
        
        **r** (float, 1e-20): Branch resistance in per unit
        
        **x** (float, 1e-20): Branch reactance in per unit
        
        **g** (float, 1e-20): Branch shunt conductance in per unit
        
        **b** (float, 1e-20): Branch shunt susceptance in per unit
        
        **rate** (float, 1.0): Branch rate in MVA
        
        **tap** (float, 1.0): Branch tap module
        
        **shift_angle** (int, 0): Tap shift angle in radians
        
        **active** (bool, True): Is the branch active?
        
        **tolerance** (float, 0): Tolerance specified for the branch impedance in %
        
        **mttf** (float, 0.0): Mean time to failure in hours
        
        **mttr** (float, 0.0): Mean time to recovery in hours
        
        **r_fault** (float, 0.0): Mid-line fault resistance in per unit (SC only)
        
        **x_fault** (float, 0.0): Mid-line fault reactance in per unit (SC only)
        
        **fault_pos** (float, 0.0): Mid-line fault position in per unit (0.0 = `bus_from`, 0.5 = middle, 1.0 = `bus_to`)
        
        **branch_type** (BranchType, BranchType.Line): Device type enumeration (ex.: :ref:`BranchType.Transformer<transformer_type>`)
        
        **length** (float, 0.0): Length of the branch in km
        
        **vset** (float, 1.0): Voltage set-point of the voltage controlled bus in per unit
        
        **temp_base** (float, 20.0): Base temperature at which `r` is measured in °C
        
        **temp_oper** (float, 20.0): Operating temperature in °C
        
        **alpha** (float, 0.0033): Thermal constant of the material in °C
        
        **bus_to_regulated** (bool, False): Is the `bus_to` voltage regulated by this branch?
        
        **template** (BranchTemplate, BranchTemplate()): Basic branch template
    """

    def __init__(self, bus_from: Bus, bus_to: Bus, name='Branch', r=1e-20, x=1e-20, g=1e-20, b=1e-20,
                 rate=1.0, tap=1.0, shift_angle=0, active=True, tolerance=0,
                 mttf=0, mttr=0, r_fault=0.0, x_fault=0.0, fault_pos=0.5,
                 branch_type: BranchType = BranchType.Line, length=1, vset=1.0,
                 temp_base=20, temp_oper=20, alpha=0.00330,
                 bus_to_regulated=False, template=BranchTemplate(), ):

        EditableDevice.__init__(self,
                                name=name,
                                active=active,
                                device_type=DeviceType.BranchDevice,
                                editable_headers={'name': GCProp('', str, 'Name of the branch.'),
                                                  'bus_from': GCProp('', Bus,
                                                                     'Name of the bus at the "from" side of the branch.'),
                                                  'bus_to': GCProp('', Bus, 'Name of the bus at the "to" '
                                                                   'side of the branch.'),
                                                  'active': GCProp('', bool, 'Is the branch active?'),
                                                  'rate': GCProp('MVA', float, 'Thermal rating power of the branch.'),
                                                  'mttf': GCProp('h', float, 'Mean time to failure, '
                                                                 'used in reliability studies.'),
                                                  'mttr': GCProp('h', float, 'Mean time to recovery, '
                                                                 'used in reliability studies.'),
                                                  'R': GCProp('p.u.', float, 'Total resistance.'),
                                                  'X': GCProp('p.u.', float, 'Total reactance.'),
                                                  'G': GCProp('p.u.', float, 'Total shunt conductance.'),
                                                  'B': GCProp('p.u.', float, 'Total shunt susceptance.'),
                                                  'tolerance': GCProp('%', float,
                                                                      'Tolerance expected for the impedance values\n'
                                                                      '7% is expected for transformers\n'
                                                                      '0% for lines.'),
                                                  'length': GCProp('km', float, 'Length of the branch '
                                                                   '(not used for calculation)'),
                                                  'tap_module': GCProp('', float, 'Tap changer module, '
                                                                       'it a value close to 1.0'),
                                                  'angle': GCProp('rad', float, 'Angle shift of the tap changer.'),
                                                  'bus_to_regulated': GCProp('', bool, 'Is the bus tap regulated?'),
                                                  'vset': GCProp('p.u.', float, 'Objective voltage at the "to" side of '
                                                                 'the bus when regulating the tap.'),
                                                  'temp_base': GCProp('ºC', float, 'Base temperature at which R was '
                                                                      'measured.'),
                                                  'temp_oper': GCProp('ºC', float, 'Operation temperature to modify R.'),
                                                  'alpha': GCProp('1/ºC', float, 'Thermal coefficient to modify R,\n'
                                                                  'around a reference temperature\n'
                                                                  'using a linear approximation.\n'
                                                                  'For example:\n'
                                                                  'Copper @ 20ºC: 0.004041,\n'
                                                                  'Copper @ 75ºC: 0.00323,\n'
                                                                  'Annealed copper @ 20ºC: 0.00393,\n'
                                                                  'Aluminum @ 20ºC: 0.004308,\n'
                                                                  'Aluminum @ 75ºC: 0.00330'),
                                                  'r_fault': GCProp('p.u.', float, 'Resistance of the mid-line fault.\n'
                                                                    'Used in short circuit studies.'),
                                                  'x_fault': GCProp('p.u.', float, 'Reactance of the mid-line fault.\n'
                                                                    'Used in short circuit studies.'),
                                                  'fault_pos': GCProp('p.u.', float, 'Per-unit positioning of the fault:\n'
                                                                      '0 would be at the "from" side,\n'
                                                                      '1 would be at the "to" side,\n'
                                                                      'therefore 0.5 is at the middle.'),
                                                  'branch_type': GCProp('', BranchType, ''),
                                                  'template': GCProp('', BranchTemplate, '')},
                                non_editable_attributes=['bus_from', 'bus_to', 'template'],
                                properties_with_profile={'active': 'active_prof'})

        # connectivity
        self.bus_from = bus_from
        self.bus_to = bus_to

        # Is the branch active?
        self.active = active

        # List of measurements
        self.measurements = list()

        # line length in km
        self.length = length

        # branch impedance tolerance
        self.tolerance = tolerance

        # short circuit impedance
        self.r_fault = r_fault
        self.x_fault = x_fault
        self.fault_pos = fault_pos

        # total impedance and admittance in p.u.
        self.R = r
        self.X = x
        self.G = g
        self.B = b

        self.mttf = mttf

        self.mttr = mttr

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

        Argument:

            **tap_changer** (:ref:`TapChanger<tap_changer>`): Tap changer object

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

            **tap_f** (float, 1.0): Virtual tap at the *from* side

            **tap_t** (float, 1.0): Virtual tap at the *to* side

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

        Arguments:

            **obj**: TransformerType or Tower object

            **Sbase** (float): Nominal power in MVA

            **logger** (list, []): Log list

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

                z = obj.z_series() * self.length / Zbase
                y = obj.y_shunt() * self.length / Ybase

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

            z = obj.z_series() * self.length / Zbase
            y = obj.y_shunt() * self.length / Ybase

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
                self.R, self.X, self.G, self.B, self.tolerance, self.length, self.tap_module, self.angle,
                self.bus_to_regulated,  self.vset, self.temp_base, self.temp_oper, self.alpha, self.r_fault,
                self.x_fault, self.fault_pos, conv.inv_conv[self.branch_type], template]

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


class Load(EditableDevice):
    """
    The load object implements the so-called ZIP model, in which the load can be
    represented by a combination of power (P), current(I), and impedance (Z).

    The sign convention is: Positive to act as a load, negative to act as a generator.

    Arguments:

        **name** (str, "Load"): Name of the load

        **G** (float, 0.0): Conductance in equivalent MW

        **B** (float, 0.0): Susceptance in equivalent MVAr

        **Ir** (float, 0.0): Real current in equivalent MW

        **Ii** (float, 0.0): Imaginary current in equivalent MVAr

        **P** (float, 0.0): Active power in MW

        **Q** (float, 0.0): Reactive power in MVAr

        **G_prof** (DataFrame, None): Pandas DataFrame with the conductance profile in equivalent MW

        **B_prof** (DataFrame, None): Pandas DataFrame with the susceptance profile in equivalent MVAr

        **Ir_prof** (DataFrame, None): Pandas DataFrame with the real current profile in equivalent MW

        **Ii_prof** (DataFrame, None): Pandas DataFrame with the imaginary current profile in equivalent MVAr

        **P_prof** (DataFrame, None): Pandas DataFrame with the active power profile in equivalent MW

        **Q_prof** (DataFrame, None): Pandas DataFrame with the reactive power profile in equivalent MVAr

        **active** (bool, True): Is the load active?

        **mttf** (float, 0.0): Mean time to failure in hours

        **mttr** (float, 0.0): Mean time to recovery in hours

    """

    def __init__(self, name='Load', G=0.0, B=0.0, Ir=0.0, Ii=0.0, P=0.0, Q=0.0,
                 G_prof=None, B_prof=None, Ir_prof=None, Ii_prof=None, P_prof=None, Q_prof=None,
                 active=True, mttf=0.0, mttr=0.0):

        EditableDevice.__init__(self,
                                name=name,
                                active=active,
                                device_type=DeviceType.LoadDevice,
                                editable_headers={'name': GCProp('', str, 'Load name'),
                                                   'bus': GCProp('', None, 'Connection bus name'),
                                                   'active': GCProp('', bool, 'Is the load active?'),
                                                   'P': GCProp('MW', float, 'Active power'),
                                                   'Q': GCProp('MVAr', float, 'Reactive power'),
                                                   'Ir': GCProp('MW', float,
                                                                'Active power of the current component at V=1.0 p.u.'),
                                                   'Ii': GCProp('MVAr', float,
                                                                'Reactive power of the current component at V=1.0 p.u.'),
                                                   'G': GCProp('MW', float,
                                                               'Active power of the impedance component at V=1.0 p.u.'),
                                                   'B': GCProp('MVAr', float,
                                                               'Reactive power of the impedance component at V=1.0 p.u.'),
                                                   'mttf': GCProp('h', float, 'Mean time to failure'),
                                                   'mttr': GCProp('h', float, 'Mean time to recovery')},
                                non_editable_attributes=list(),
                                properties_with_profile={'P': 'P_prof',
                                                         'Q': 'Q_prof',
                                                         'Ir': 'Ir_prof',
                                                         'Ii': 'Ii_prof',
                                                         'G': 'G_prof',
                                                         'B': 'B_prof'})

        self.bus = None

        self.mttf = mttf

        self.mttr = mttr

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

    # def create_profiles(self, index, S=None, I=None, Y=None):
    #     """
    #     Create the load object default profiles
    #     Args:
    #         index: DataFrame time index
    #         S: Array of complex power values
    #         I: Array of complex current values
    #         Y: Array of complex admittance values
    #     """
    #
    #     self.create_S_profile(index, S)
    #     self.create_I_profile(index, I)
    #     self.create_Y_profile(index, Y)
    #
    # def create_S_profile(self, index, arr=None, arr_in_pu=False):
    #     """
    #     Create power profile based on index
    #     Args:
    #         index: time index
    #         arr: array
    #         arr_in_pu: is the array in per unit? if true, it is applied as a mask profile
    #     """
    #     if arr_in_pu:
    #         P = arr * self.P
    #         Q = arr * self.Q
    #     else:
    #         nt = len(index)
    #         P = np.ones(nt) * self.P if arr is None else arr
    #         Q = np.ones(nt) * self.Q if arr is None else arr
    #
    #     self.P_prof = pd.DataFrame(data=P, index=index, columns=[self.name])
    #     self.Q_prof = pd.DataFrame(data=Q, index=index, columns=[self.name])
    #
    # def create_I_profile(self, index, arr, arr_in_pu=False):
    #     """
    #     Create current profile based on index
    #     Args:
    #         index: time index
    #         arr: array
    #         arr_in_pu: is the array in per unit? if true, it is applied as a mask profile
    #     """
    #     if arr_in_pu:
    #         Ir = arr * self.Ir
    #         Ii = arr * self.Ii
    #     else:
    #         nt = len(index)
    #         Ir = np.ones(nt) * self.Ir if arr is None else arr
    #         Ii = np.ones(nt) * self.Ii if arr is None else arr
    #
    #     self.Ir_prof = pd.DataFrame(data=Ir, index=index, columns=[self.name])
    #     self.Ii_prof = pd.DataFrame(data=Ii, index=index, columns=[self.name])
    #
    # def create_Y_profile(self, index, arr, arr_in_pu=False):
    #     """
    #     Create impedance profile based on index
    #     Args:
    #         index: time index
    #         arr: array
    #         arr_in_pu: is the array in per unit? if true, it is applied as a mask profile
    #     Returns:
    #
    #     """
    #     if arr_in_pu:
    #         G = arr * self.G
    #         B = arr * self.B
    #     else:
    #         nt = len(index)
    #         G = np.ones(nt) * self.G if arr is None else arr
    #         B = np.ones(nt) * self.B if arr is None else arr
    #
    #     self.G_prof = pd.DataFrame(data=G, index=index, columns=[self.name])
    #     self.B_prof = pd.DataFrame(data=B, index=index, columns=[self.name])
    #
    # def delete_profiles(self):
    #     """
    #     Delete the object profiles
    #     :return:
    #     """
    #     self.P_prof = None
    #     self.Q_prof = None
    #     self.Ir_prof = None
    #     self.Ii_prof = None
    #     self.G_prof = None
    #     self.B_prof = None
    #
    # def set_profile_values(self, t):
    #     """
    #     Set the profile values at t
    #     :param t: time index
    #     """
    #     self.P = self.P_prof.values[t]
    #     self.Q = self.Q_prof.values[t]
    #     self.Ir = self.Ir_prof.values[t]
    #     self.Ii = self.Ii_prof.values[t]
    #     self.G = self.G_prof.values[t]
    #     self.B = self.B_prof.values[t]

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


class StaticGenerator(EditableDevice):
    """
    Arguments:

        **name** (str, "StaticGen"): Name of the static generator

        **P** (float, 0.0): Active power in MW

        **Q** (float, 0.0): Reactive power in MVAr

        **P_prof** (DataFrame, None): Pandas DataFrame with the active power profile in MW

        **Q_prof** (DataFrame, None): Pandas DataFrame with the reactive power profile in MVAr

        **active** (bool, True): Is the static generator active?

        **mttf** (float, 0.0): Mean time to failure in hours

        **mttr** (float, 0.0): Mean time to recovery in hours

    """

    def __init__(self, name='StaticGen', P=0.0, Q=0.0, P_prof=None, Q_prof=None, active=True, mttf=0.0, mttr=0.0):

        EditableDevice.__init__(self,
                                name=name,
                                active=active,
                                device_type=DeviceType.StaticGeneratorDevice,
                                editable_headers={'name': GCProp('', str, ''),
                                                  'bus': GCProp('', None, ''),
                                                  'active': GCProp('', bool, ''),
                                                  'P': GCProp('MW', float, 'Active power'),
                                                  'Q': GCProp('MVAr', float, 'Reactive power'),
                                                  'mttf': GCProp('h', float, 'Mean time to failure'),
                                                  'mttr': GCProp('h', float, 'Mean time to recovery')},
                                non_editable_attributes=list(),
                                properties_with_profile={'P': 'P_prof',
                                                         'Q': 'Q_prof'})

        self.bus = None

        self.mttf = mttf

        self.mttr = mttr

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


class Generator(EditableDevice):
    """
    Voltage controlled generator. This generators supports several
    :ref:`reactive power control modes<q_control>` to regulate the voltage on its
    :ref:`bus` during :ref:`power flow simulations<pf_driver>`.

    Arguments:

        **name** (str, "gen"): Name of the generator

        **active_power** (float, 0.0): Active power in MW

        **power_factor** (float, 0.8): Power factor

        **voltage_module** (float, 1.0): Voltage setpoint in per unit

        **is_controlled** (bool, True): Is the generator voltage controlled?

        **Qmin** (float, -9999): Minimum reactive power in MVAr

        **Qmax** (float, 9999): Maximum reactive power in MVAr

        **Snom** (float, 9999): Nominal apparent power in MVA

        **power_prof** (DataFrame, None): Pandas DataFrame with the active power profile in MW

        **power_factor_prof** (DataFrame, None): Pandas DataFrame with the power factor profile

        **vset_prof** (DataFrame, None): Pandas DataFrame with the voltage setpoint profile in per unit

        **active** (bool, True): Is the generator active?

        **p_min** (float, 0.0): Minimum dispatchable power in MW

        **p_max** (float, 9999): Maximum dispatchable power in MW

        **op_cost** (float, 1.0): Operational cost in Eur (or other currency) per MW

        **Sbase** (float, 100): Nominal apparent power in MVA

        **enabled_dispatch** (bool, True): Is the generator enabled for OPF?

        **mttf** (float, 0.0): Mean time to failure in hours

        **mttr** (float, 0.0): Mean time to recovery in hours

    """

    def __init__(self, name='gen', active_power=0.0, power_factor=0.8, voltage_module=1.0, is_controlled=True,
                 Qmin=-9999, Qmax=9999, Snom=9999, power_prof=None, power_factor_prof=None, vset_prof=None, active=True,
                 p_min=0.0, p_max=9999.0, op_cost=1.0, Sbase=100, enabled_dispatch=True, mttf=0.0, mttr=0.0):

        EditableDevice.__init__(self,
                                name=name,
                                active=active,
                                device_type=DeviceType.GeneratorDevice,
                                editable_headers={'name': GCProp('', str, 'Name of the generator'),
                                                  'bus': GCProp('', None, 'Connection bus name'),
                                                  'active': GCProp('', bool, 'Is the generator active?'),
                                                  'is_controlled': GCProp('', bool,
                                                                          'Is this generator voltage-controlled?'),
                                                  'P': GCProp('MW', float, 'Active power'),
                                                  'Pf': GCProp('', float,
                                                               'Power factor (cos(fi)). '
                                                               'This is used for non-controlled generators.'),
                                                  'Vset': GCProp('p.u.', float,
                                                                 'Set voltage. '
                                                                 'This is used for controlled generators.'),
                                                  'Snom': GCProp('MVA', float, 'Nomnial power.'),
                                                  'Qmin': GCProp('MVAr', float, 'Minimum reactive power.'),
                                                  'Qmax': GCProp('MVAr', float, 'Maximum reactive power.'),
                                                  'Pmin': GCProp('MW', float, 'Minimum active power. Used in OPF.'),
                                                  'Pmax': GCProp('MW', float, 'Maximum active power. Used in OPF.'),
                                                  'Cost': GCProp('e/MWh', float, 'Generation unitary cost. Used in OPF.'),
                                                  'enabled_dispatch': GCProp('', bool,
                                                                             'Enabled for dispatch? Used in OPF.'),
                                                  'mttf': GCProp('h', float, 'Mean time to failure'),
                                                  'mttr': GCProp('h', float, 'Mean time to recovery')},
                                non_editable_attributes=list(),
                                properties_with_profile={'P': 'P_prof',
                                                         'Pf': 'Pf_prof',
                                                         'Vset': 'Vset_prof'})

        self.bus = None

        self.mttf = mttf

        self.mttr = mttr

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

    def initialize_lp_vars(self):
        """
        Initialize the LP variables
        """
        self.lp_name = self.type_name + '_' + self.name + str(id(self))

        self.LPVar_P = pulp.LpVariable(self.lp_name + '_P', self.Pmin / self.Sbase, self.Pmax / self.Sbase)

    def get_lp_var_profile(self, index):
        """
        Get the profile of the LP solved values into a Pandas DataFrame
        :param index: time index
        :return: DataFrame with the LP values
        """
        dta = [x.value() for x in self.LPVar_P_prof]
        return pd.DataFrame(data=dta, index=index, columns=[self.name])

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


class Battery(Generator):
    """
    :ref:`Battery<battery>` (voltage controlled and dispatchable).

    Arguments:

        **name** (str, "batt"): Name of the battery

        **active_power** (float, 0.0): Active power in MW
        
        **power_factor** (float, 0.8): Power factor

        **voltage_module** (float, 1.0): Voltage setpoint in per unit

        **is_controlled** (bool, True): Is the unit voltage controlled (if so, the
        connection bus becomes a PV bus)

        **Qmin** (float, -9999): Minimum reactive power in MVAr

        **Qmax** (float, 9999): Maximum reactive power in MVAr

        **Snom** (float, 9999): Nominal apparent power in MVA

        **Enom** (float, 9999): Nominal energy capacity in MWh

        **p_min** (float, -9999): Minimum dispatchable power in MW

        **p_max** (float, 9999): Maximum dispatchable power in MW

        **op_cost** (float, 1.0): Operational cost in Eur (or other currency) per MW

        **power_prof** (DataFrame, None): Pandas DataFrame with the active power
        profile in MW

        **power_factor_prof** (DataFrame, None): Pandas DataFrame with the power factor
        profile

        **vset_prof** (DataFrame, None): Pandas DataFrame with the voltage setpoint
        profile in per unit

        **active** (bool, True): Is the battery active?

        **Sbase** (float, 100): Base apparent power in MVA

        **enabled_dispatch** (bool, True): Is the battery enabled for OPF?

        **mttf** (float, 0.0): Mean time to failure in hours

        **mttr** (float, 0.0): Mean time to recovery in hours

        **charge_efficiency** (float, 0.9): Efficiency when charging

        **discharge_efficiency** (float, 0.9): Efficiency when discharging

        **max_soc** (float, 0.99): Maximum state of charge

        **min_soc** (float, 0.3): Minimum state of charge

        **soc** (float, 0.8): Current state of charge

        **charge_per_cycle** (float, 0.1): Per unit of power to take per cycle when
        charging

        **discharge_per_cycle** (float, 0.1): Per unit of power to deliver per cycle
        when discharging

    """

    def __init__(self, name='batt', active_power=0.0, power_factor=0.8, voltage_module=1.0,
                 is_controlled=True, Qmin=-9999, Qmax=9999, Snom=9999, Enom=9999, p_min=-9999, p_max=9999,
                 op_cost=1.0, power_prof=None, power_factor_prof=None, vset_prof=None, active=True, Sbase=100,
                 enabled_dispatch=True, mttf=0.0, mttr=0.0, charge_efficiency=0.9, discharge_efficiency=0.9,
                 max_soc=0.99, min_soc=0.3, soc=0.8, charge_per_cycle=0.1, discharge_per_cycle=0.1):

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
        self.device_type = DeviceType.BatteryDevice

        # manually modify the editable headers
        self.editable_headers = {'name': GCProp('', str, 'Name of the battery'),
                                 'bus': GCProp('', None, 'Connection bus name'),
                                 'active': GCProp('', bool, 'Is the battery active?'),
                                 'is_controlled': GCProp('', bool, 'Is this battery voltage-controlled?'),
                                 'P': GCProp('MW', float, 'Active power'),
                                 'Pf': GCProp('', float,
                                              'Power factor (cos(fi)). This is used for non-controlled batteries.'),
                                 'Vset': GCProp('p.u.', float, 'Set voltage. This is used for controlled batteries.'),
                                 'Snom': GCProp('MVA', float, 'Nomnial power.'),
                                 'Enom': GCProp('MWh', float, 'Nominal energy capacity.'),
                                 'max_soc': GCProp('p.u.', float, 'Minimum state of charge.'),
                                 'min_soc': GCProp('p.u.', float, 'Maximum state of charge.'),
                                 'soc_0': GCProp('p.u.', float, 'Initial state of charge.'),
                                 'charge_efficiency': GCProp('p.u.', float, 'Charging efficiency.'),
                                 'discharge_efficiency': GCProp('p.u.', float, 'Discharge efficiency.'),
                                 'discharge_per_cycle': GCProp('p.u.', float, ''),
                                 'Qmin': GCProp('MVAr', float, 'Minimum reactive power.'),
                                 'Qmax': GCProp('MVAr', float, 'Maximum reactive power.'),
                                 'Pmin': GCProp('MW', float, 'Minimum active power. Used in OPF.'),
                                 'Pmax': GCProp('MW', float, 'Maximum active power. Used in OPF.'),
                                 'Cost': GCProp('e/MWh', float, 'Generation unitary cost. Used in OPF.'),
                                 'enabled_dispatch': GCProp('', bool, 'Enabled for dispatch? Used in OPF.'),
                                 'mttf': GCProp('h', float, 'Mean time to failure'),
                                 'mttr': GCProp('h', float, 'Mean time to recovery')}

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
        Returns: :ref:`Battery<battery>` instance
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

    def initialize_arrays(self, index, arr=None, arr_in_pu=False):
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
        self.power_array = pd.DataFrame(data=dta.copy(), index=index, columns=[self.name])
        self.energy_array = pd.DataFrame(data=dta.copy(), index=index, columns=[self.name])

    def reset(self):
        """
        Set the battery to its initial state
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


class Shunt(EditableDevice):
    """
    Arguments:

        **name** (str, "shunt"): Name of the shunt

        **G** (float, 0.0): Conductance in MW at 1 p.u. voltage

        **B** (float, 0.0): Susceptance in MW at 1 p.u. voltage

        **G_prof** (DataFrame, None): Pandas DataFrame with the conductance profile in MW at 1 p.u. voltage

        **B_prof** (DataFrame, None): Pandas DataFrame with the susceptance profile in MW at 1 p.u. voltage

        **active** (bool, True): Is the shunt active?

        **mttf** (float, 0.0): Mean time to failure in hours

        **mttr** (float, 0.0): Mean time to recovery in hours

    """

    def __init__(self, name='shunt', G=0.0, B=0.0, G_prof=None, B_prof=None, active=True, mttf=0.0, mttr=0.0):

        EditableDevice.__init__(self,
                                name=name,
                                active=active,
                                device_type=DeviceType.ShuntDevice,
                                editable_headers={'name': GCProp('', str, 'Load name'),
                                                  'bus': GCProp('', None, 'Connection bus name'),
                                                  'active': GCProp('', bool, 'Is the load active?'),
                                                  'G': GCProp('MW', float,
                                                              'Active power of the impedance component at V=1.0 p.u.'),
                                                  'B': GCProp('MVAr', float,
                                                              'Reactive power of the impedance component at V=1.0 p.u.'),
                                                  'mttf': GCProp('h', float, 'Mean time to failure'),
                                                  'mttr': GCProp('h', float, 'Mean time to recovery')},
                                non_editable_attributes=list(),
                                properties_with_profile={'G': 'G_prof',
                                                         'B': 'B_prof'})

        # The bus this element is attached to: Not necessary for calculations
        self.bus = None

        self.mttf = mttf

        self.mttr = mttr

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
