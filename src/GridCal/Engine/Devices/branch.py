# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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

import uuid
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Devices.bus import Bus
from GridCal.Engine.Devices.enumerations import BranchType
from GridCal.Engine.Devices.transformer import TransformerType, Transformer2W
from GridCal.Engine.Devices.line import SequenceLineType, Line
from GridCal.Engine.Devices.hvdc_line import HvdcLine
from GridCal.Engine.Devices.underground_line import UndergroundLineType

from GridCal.Engine.Devices.editable_device import EditableDevice, DeviceType, GCProp
from GridCal.Engine.Devices.tower import Tower

# Global sqrt of 3 (bad practice?)
SQRT3 = np.sqrt(3.0)


class BranchTemplate:

    def __init__(self, name='BranchTemplate', tpe=BranchType.Branch):

        self.idtag = uuid.uuid4().hex

        self.name = name

        self.tpe = tpe

        self.device_type = DeviceType.BranchTypeDevice

        self.edit_headers = []
        self.units = []
        self.non_editable_indices = []
        self.edit_types = {}

    def __str__(self):
        return self.name

    def get_save_data(self):

        dta = list()
        for property in self.edit_headers:
            dta.append(getattr(self, property))
        return dta


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
            self.tap = round((tap_module - 1.0) / self.inc_reg_up)
        elif tap_module < 1:
            self.tap = -round((1.0 - tap_module) / self.inc_reg_down)


class Branch(EditableDevice):
    """
    * This class exists for legacy reasons, use the Line or Transformer2w classes instead! *
    The **Branch** class represents the connections between nodes (i.e.
    :ref:`buses<bus>`) in **GridCal**. A branch is an element (cable, line, capacitor,
    transformer, etc.) with an electrical impedance. The basic **Branch** class
    includes basic electrical attributes for most passive elements, but other device
    types may be passed to the **Branch** constructor to configure it as a specific
    type.

    For example, a transformer may be created with the following code:

    .. code:: ipython3

        from GridCal.Engine.Core.multi_circuit import MultiCircuit
        from GridCal.Engine.Devices import *
        from GridCal.Engine.Devices.types import *

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

    Refer to the :class:`GridCal.Engine.Devices.branch.TapChanger` class for an example
    using a voltage regulator.

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

        **branch_type** (BranchType, BranchType.Line): Device type enumeration (ex.: :class:`GridCal.Engine.Devices.transformer.TransformerType`)

        **length** (float, 0.0): Length of the branch in km

        **vset** (float, 1.0): Voltage set-point of the voltage controlled bus in per unit

        **temp_base** (float, 20.0): Base temperature at which `r` is measured in °C

        **temp_oper** (float, 20.0): Operating temperature in °C

        **alpha** (float, 0.0033): Thermal constant of the material in °C

        **bus_to_regulated** (bool, False): Is the `bus_to` voltage regulated by this branch?

        **template** (BranchTemplate, BranchTemplate()): Basic branch template
    """

    def __init__(self, bus_from: Bus = None, bus_to: Bus = None, name='Branch', idtag=None, r=1e-20, x=1e-20, g=1e-20, b=1e-20,
                 rate=1.0, tap=1.0, shift_angle=0, active=True, tolerance=0, cost=0.0,
                 mttf=0, mttr=0, r_fault=0.0, x_fault=0.0, fault_pos=0.5,
                 branch_type: BranchType = BranchType.Line, length=1, vset=1.0,
                 temp_base=20, temp_oper=20, alpha=0.00330,
                 bus_to_regulated=False, template=BranchTemplate(), ):

        EditableDevice.__init__(self,
                                idtag=idtag,
                                name=name,
                                active=active,
                                device_type=DeviceType.BranchDevice,
                                editable_headers={'name': GCProp('', str, 'Name of the branch.'),
                                                  'idtag': GCProp('', str, 'Unique ID'),
                                                  'bus_from': GCProp('', DeviceType.BusDevice,
                                                                     'Name of the bus at the "from" side of the branch.'),
                                                  'bus_to': GCProp('', DeviceType.BusDevice,
                                                                   'Name of the bus at the "to" side of the branch.'),
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
                                                  'Cost': GCProp('e/MWh', float,
                                                                 'Cost of overloads. Used in OPF.'),
                                                  'r_fault': GCProp('p.u.', float, 'Resistance of the mid-line fault.\n'
                                                                    'Used in short circuit studies.'),
                                                  'x_fault': GCProp('p.u.', float, 'Reactance of the mid-line fault.\n'
                                                                    'Used in short circuit studies.'),
                                                  'fault_pos': GCProp('p.u.', float,
                                                                      'Per-unit positioning of the fault:\n'
                                                                      '0 would be at the "from" side,\n'
                                                                      '1 would be at the "to" side,\n'
                                                                      'therefore 0.5 is at the middle.'),
                                                  'branch_type': GCProp('', BranchType, ''),
                                                  'template': GCProp('', BranchTemplate, '')},
                                non_editable_attributes=['bus_from', 'bus_to', 'template'],
                                properties_with_profile={'active': 'active_prof',
                                                         'rate': 'rate_prof',
                                                         'temp_oper': 'temp_oper_prof',
                                                         'Cost': 'Cost_prof'})

        # connectivity
        self.bus_from = bus_from
        self.bus_to = bus_to

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

        self.Cost = cost

        self.Cost_prof = None

        self.active_prof = None

        # Conductor base and operating temperatures in ºC
        self.temp_base = temp_base
        self.temp_oper = temp_oper

        self.temp_oper_prof = None

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

        self.rate_prof = None

        # branch type: Line, Transformer, etc...
        self.branch_type = branch_type

        # type template
        self.template = template
        self.bus_to_regulated = bus_to_regulated
        self.vset = vset

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

    def get_weight(self):
        return np.sqrt(self.R * self.R + self.X * self.X)

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

        b.active_prof = self.active_prof.copy()

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

            **tap_changer** (:class:`GridCal.Engine.Devices.branch.TapChanger`): Tap changer object

        """
        self.tap_changer = tap_changer

        if self.tap_module != 0:
            self.tap_changer.set_tap(self.tap_module)
        else:
            self.tap_module = self.tap_changer.get_tap()

    def get_virtual_taps(self):
        """
        Get the branch virtual taps

        The virtual taps generate when a transformer nominal winding voltage differs
        from the bus nominal voltage.

        Returns:

            **tap_f** (float, 1.0): Virtual tap at the *from* side

            **tap_t** (float, 1.0): Virtual tap at the *to* side

        """
        if self.branch_type == BranchType.Transformer and type(self.template) == TransformerType:
            # resolve how the transformer is actually connected and set the virtual taps
            bus_f_v = self.bus_from.Vnom
            bus_t_v = self.bus_to.Vnom

            dhf = abs(self.template.HV - bus_f_v)
            dht = abs(self.template.HV - bus_t_v)

            if dhf < dht:
                # the HV side is on the from side
                tpe_f_v = self.template.HV
                tpe_t_v = self.template.LV
            else:
                # the HV side is on the to side
                tpe_t_v = self.template.HV
                tpe_f_v = self.template.LV

            tap_f = tpe_f_v / bus_f_v
            tap_t = tpe_t_v / bus_t_v
            return tap_f, tap_t
        else:
            return 1.0, 1.0

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        data = list()
        for name, properties in self.editable_headers.items():
            obj = getattr(self, name)

            if properties.tpe == BranchType:
                obj = self.branch_type.value

            elif properties.tpe == BranchTemplate:
                if obj is None:
                    obj = ''
                else:
                    obj = str(obj)

            elif properties.tpe not in [str, float, int, bool]:
                obj = str(obj)

            data.append(obj)
        return data

    def get_properties_dict(self, version=3):
        """
        Get json dictionary
        :return:
        """

        d = {'id': self.idtag,
             'type': 'branch',
             'phases': 'ps',
             'name': self.name,
             'from': self.bus_from.idtag,
             'to': self.bus_to.idtag,
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
             'branch_type': str(self.branch_type),
             'active_profile': [],
             'rate_prof': []}

        if self.active_prof is not None:
            d['active_profile'] = self.active_prof.tolist()
            d['rate_prof'] = self.rate_prof.tolist()

        return d

    def plot_profiles(self, time_series=None, my_index=0, show_fig=True):
        """
        Plot the time series results of this object
        :param time_series: TimeSeries Instance
        :param my_index: index of this object in the simulation
        :param show_fig: Show the figure?
        """

        if time_series is not None:
            fig = plt.figure(figsize=(12, 8))

            ax_1 = fig.add_subplot(211)
            ax_2 = fig.add_subplot(212, sharex=ax_1)

            x = time_series.results.time

            # loading
            y = time_series.results.loading * 100.0
            df = pd.DataFrame(data=y[:, my_index], index=x, columns=[self.name])
            ax_1.set_title('Loading', fontsize=14)
            ax_1.set_ylabel('Loading [%]', fontsize=11)
            df.plot(ax=ax_1)

            # losses
            y = time_series.results.losses
            df = pd.DataFrame(data=y[:, my_index], index=x, columns=[self.name])
            ax_2.set_title('Losses', fontsize=14)
            ax_2.set_ylabel('Losses [MVA]', fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

        if show_fig:
            plt.show()

    def get_coordinates(self):
        """
        Get the branch defining coordinates
        """
        return [self.bus_from.get_coordinates(), self.bus_to.get_coordinates()]


def convert_branch(branch: Branch):
    """

    :param branch:
    :return:
    """
    if branch.branch_type == BranchType.Line:

        return Line(bus_from=branch.bus_from,
                    bus_to=branch.bus_to,
                    name=branch.name,
                    r=branch.R,
                    x=branch.X,
                    b=branch.B,
                    rate=branch.rate,
                    active=branch.active,
                    tolerance=branch.tolerance,
                    cost=branch.Cost,
                    mttf=branch.mttf,
                    mttr=branch.mttr,
                    r_fault=branch.r_fault,
                    x_fault=branch.x_fault,
                    fault_pos=branch.fault_pos,
                    length=branch.length,
                    temp_base=branch.temp_base,
                    temp_oper=branch.temp_oper,
                    alpha=branch.alpha,
                    rate_prof=branch.rate_prof,
                    Cost_prof=branch.Cost_prof,
                    active_prof=branch.active_prof,
                    temp_oper_prof=branch.temp_oper_prof)

    elif branch.branch_type == BranchType.Transformer:

        return Transformer2W(bus_from=branch.bus_from,
                             bus_to=branch.bus_to,
                             name=branch.name,
                             r=branch.R,
                             x=branch.X,
                             b=branch.B,
                             rate=branch.rate,
                             active=branch.active,
                             tolerance=branch.tolerance,
                             cost=branch.Cost,
                             mttf=branch.mttf,
                             mttr=branch.mttr,
                             tap=branch.tap_module,
                             shift_angle=branch.angle,
                             vset=branch.vset,
                             bus_to_regulated=branch.bus_to_regulated,
                             temp_base=branch.temp_base,
                             temp_oper=branch.temp_oper,
                             alpha=branch.alpha,
                             template=branch.template,
                             rate_prof=branch.rate_prof,
                             Cost_prof=branch.Cost_prof,
                             active_prof=branch.active_prof,
                             temp_oper_prof=branch.temp_oper_prof)
    else:
        return branch
