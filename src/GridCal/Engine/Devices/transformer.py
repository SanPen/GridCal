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

import os
from numpy import sqrt
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Devices.bus import Bus
from GridCal.Engine.Devices.enumerations import BranchType, TransformerControlType

from GridCal.Engine.Devices.editable_device import EditableDevice, DeviceType, GCProp
from GridCal.Engine.Devices.tower import Tower


class TransformerType(EditableDevice):
    """
    Arguments:

        **hv_nominal_voltage** (float, 0.0): Primary side nominal voltage in kV (tied to the Branch's `bus_from`)

        **lv_nominal_voltage** (float, 0.0): Secondary side nominal voltage in kV (tied to the Branch's `bus_to`)

        **nominal_power** (float, 0.0): Transformer nominal apparent power in MVA

        **copper_losses** (float, 0.0): Copper losses in kW (also known as short circuit power)

        **iron_losses** (float, 0.0): Iron losses in kW (also known as no-load power)

        **no_load_current** (float, 0.0): No load current in %

        **short_circuit_voltage** (float, 0.0): Short circuit voltage in %

        **gr_hv1** (float, 0.5): Resistive contribution to the primary side in per unit (at the Branch's `bus_from`)

        **gx_hv1** (float, 0.5): Reactive contribution to the primary side in per unit (at the Branch's `bus_from`)

        **name** (str, "TransformerType"): Name of the type

        **tpe** (BranchType, BranchType.Transformer): Device type enumeration

    """

    def __init__(self, hv_nominal_voltage=0, lv_nominal_voltage=0, nominal_power=0.001, copper_losses=0, iron_losses=0,
                 no_load_current=0, short_circuit_voltage=0, gr_hv1=0.5, gx_hv1=0.5,
                 name='TransformerType', tpe=BranchType.Transformer, idtag=None):
        """
        Transformer template from the short circuit study
        :param hv_nominal_voltage: Nominal voltage of the high voltage side in kV
        :param lv_nominal_voltage: Nominal voltage of the low voltage side in kV
        :param nominal_power: Nominal power of the machine in MVA
        :param copper_losses: Copper losses in kW
        :param iron_losses: Iron losses in kW
        :param no_load_current: No load current in %
        :param short_circuit_voltage: Short circuit voltage in %
        :param gr_hv1: proportion of the resistance in the HV side (i.e. 0.5)
        :param gx_hv1: proportion of the reactance in the HV side (i.e. 0.5)
        :param name: Name of the device template
        :param tpe: Kind of template
        """
        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                active=True,
                                device_type=DeviceType.TransformerTypeDevice,
                                editable_headers={'name': GCProp('', str, "Name of the transformer type"),
                                                  'idtag': GCProp('', str, 'Unique ID'),
                                                  'HV': GCProp('kV', float, "Nominal voltage al the high voltage side"),
                                                  'LV': GCProp('kV', float, "Nominal voltage al the low voltage side"),
                                                  'rating': GCProp('MVA', float, "Nominal power"),
                                                  'Pcu': GCProp('kW', float, "Copper losses"),
                                                  'Pfe': GCProp('kW', float, "Iron losses"),
                                                  'I0': GCProp('%', float, "No-load current"),
                                                  'Vsc': GCProp('%', float, "Short-circuit voltage")},
                                non_editable_attributes=list(),
                                properties_with_profile={})

        self.tpe = tpe

        self.HV = hv_nominal_voltage

        self.LV = lv_nominal_voltage

        self.rating = nominal_power

        self.Pcu = copper_losses

        self.Pfe = iron_losses

        self.I0 = no_load_current

        self.Vsc = short_circuit_voltage

        self.GR_hv1 = gr_hv1

        self.GX_hv1 = gx_hv1

    def get_impedances(self, VH, VL, Sbase):
        """
        Compute the branch parameters of a transformer from the short circuit test
        values.
        :param VH: High voltage bus nominal voltage in kV
        :param VL: Low voltage bus nominal voltage in kV
        :param Sbase: Base power in MVA (normally 100 MVA)
        :return: Zseries and Yshunt in system per unit
        """

        Sn = self.rating
        Pcu = self.Pcu
        Pfe = self.Pfe
        I0 = self.I0
        Vsc = self.Vsc

        # Series impedance
        zsc = Vsc / 100.0
        rsc = (Pcu / 1000.0) / Sn
        if rsc < zsc:
            xsc = sqrt(zsc ** 2 - rsc ** 2)
        else:
            xsc = 0.0

        # series impedance in p.u. of the machine
        zs = rsc + 1j * xsc

        # Shunt impedance (leakage)
        if Pfe > 0.0 and I0 > 0.0:

            rfe = Sn / (Pfe / 1000.0)
            zm = 1.0 / (I0 / 100.0)
            val = (1.0 / (zm ** 2)) - (1.0 / (rfe ** 2))
            if val > 0:
                xm = 1.0 / sqrt(val)
                rm = sqrt(xm * xm - zm * zm)
            else:
                xm = 0.0
                rm = 0.0

        else:

            rm = 0.0
            xm = 0.0

        # shunt impedance in p.u. of the machine
        zsh = rm + 1j * xm

        # convert impedances from machine per unit to ohms
        ZbaseHv = (self.HV * self.HV) / Sn
        ZbaseLv = (self.LV * self.LV) / Sn

        ZseriesHv = zs * self.GR_hv1 * ZbaseHv  # Ohm
        ZseriesLv = zs * (1 - self.GR_hv1) * ZbaseLv  # Ohm
        ZshuntHv = zsh * self.GR_hv1 * ZbaseHv  # Ohm
        ZshuntLv = zsh * (1 - self.GR_hv1) * ZbaseLv  # Ohm

        # convert impedances from ohms to system per unit
        ZbaseHvSys = (VH * VH) / Sbase
        ZbaseLvSys = (VL * VL) / Sbase

        Zseries = ZseriesHv / ZbaseHvSys + ZseriesLv / ZbaseLvSys
        Zshunt = ZshuntHv / ZbaseHvSys + ZshuntLv / ZbaseLvSys

        if Zshunt != 0:
            Yshunt = 1 / Zshunt
        else:
            Yshunt = 0j

        return Zseries, Yshunt


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


class Transformer2W(EditableDevice):
    """
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

    def __init__(self, bus_from: Bus = None, bus_to: Bus = None, HV=None, LV=None, name='Branch', idtag=None, code='',
                 r=1e-20, x=1e-20, g=1e-20, b=1e-20,
                 rate=1.0,
                 tap=1.0, tap_module_max=1.2, tap_module_min=0.5,
                 shift_angle=0.0, theta_max=6.28, theta_min=-6.28,
                 active=True, tolerance=0, cost=100.0,
                 mttf=0, mttr=0,
                 vset=1.0, Pset=0, bus_to_regulated=False,
                 temp_base=20, temp_oper=20, alpha=0.00330,
                 control_mode: TransformerControlType = TransformerControlType.fixed,
                 template: TransformerType = None,
                 rate_prof=None, Cost_prof=None, active_prof=None, temp_oper_prof=None,
                 tap_module_prof=None, angle_prof=None,
                 contingency_factor=1.0,
                 contingency_enabled=True, monitor_loading=True, contingency_factor_prof=None):

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                active=active,
                                code=code,
                                device_type=DeviceType.Transformer2WDevice,
                                editable_headers={'name': GCProp('', str, 'Name of the branch.'),
                                                  'idtag': GCProp('', str, 'Unique ID', False),
                                                  'code': GCProp('', str, 'Secondary ID'),
                                                  'bus_from': GCProp('', DeviceType.BusDevice,
                                                                     'Name of the bus at the "from" side of the branch.'),
                                                  'bus_to': GCProp('', DeviceType.BusDevice,
                                                                   'Name of the bus at the "to" side of the branch.'),
                                                  'active': GCProp('', bool, 'Is the branch active?'),
                                                  'HV': GCProp('kV', float, 'High voltage rating'),
                                                  'LV': GCProp('kV', float, 'Low voltage rating'),

                                                  'rate': GCProp('MVA', float, 'Thermal rating power of the branch.'),

                                                  'contingency_factor': GCProp('p.u.', float,
                                                                               'Rating multiplier for contingencies.'),
                                                  'contingency_enabled': GCProp('', bool,
                                                                                'Consider this transformer for contingencies.'),
                                                  'monitor_loading': GCProp('', bool,
                                                                            'Monitor this device loading for optimization, NTC or contingency studies.'),
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
                                                  'tap_module': GCProp('', float,
                                                                       'Tap changer module, it a value close to 1.0'),
                                                  'tap_module_max': GCProp('', float,
                                                                           'Tap changer module max value'),
                                                  'tap_module_min': GCProp('', float,
                                                                           'Tap changer module min value'),
                                                  'angle': GCProp('rad', float, 'Angle shift of the tap changer.'),
                                                  'angle_max': GCProp('rad', float, 'Max angle.'),
                                                  'angle_min': GCProp('rad', float, 'Min angle.'),
                                                  'control_mode': GCProp('', TransformerControlType,
                                                                         'Control type of the transformer'),
                                                  # 'bus_to_regulated': GCProp('', bool, 'Is the bus tap regulated?'),
                                                  'vset': GCProp('p.u.', float, 'Objective voltage at the "to" side of '
                                                                 'the bus when regulating the tap.'),
                                                  'Pset': GCProp('p.u.', float, 'Objective power at the "from" side of '
                                                                                'when regulating the angle.'),
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
                                                  'template': GCProp('', DeviceType.TransformerTypeDevice, '')},
                                non_editable_attributes=['bus_from', 'bus_to', 'template'],
                                properties_with_profile={'active': 'active_prof',
                                                         'rate': 'rate_prof',
                                                         'contingency_factor': 'contingency_factor_prof',
                                                         'tap_module': 'tap_module_prof',
                                                         'angle': 'angle_prof',
                                                         'temp_oper': 'temp_oper_prof',
                                                         'Cost': 'Cost_prof'})

        # connectivity
        self.bus_from = bus_from
        self.bus_to = bus_to

        # set the high and low voltage values
        self.HV = 0
        self.LV = 0
        self.set_hv_and_lv(HV, LV)

        # List of measurements
        self.measurements = list()

        # branch impedance tolerance
        self.tolerance = tolerance

        # total impedance and admittance in p.u.
        self.R = r
        self.X = x
        self.G = g
        self.B = b

        self.mttf = mttf

        self.mttr = mttr

        self.Cost = cost

        self.Cost_prof = Cost_prof

        self.active_prof = active_prof

        # Conductor base and operating temperatures in ºC
        self.temp_base = temp_base
        self.temp_oper = temp_oper

        self.temp_oper_prof = temp_oper_prof

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

        self.tap_module_prof = tap_module_prof

        # Tap angle
        self.angle = shift_angle
        self.angle_prof = angle_prof

        self.tap_module_max = tap_module_max
        self.tap_module_min = tap_module_min
        self.angle_max = theta_max
        self.angle_min = theta_min

        # branch rating in MVA
        self.rate = rate
        self.contingency_factor = contingency_factor
        self.contingency_enabled: bool = contingency_enabled
        self.monitor_loading: bool = monitor_loading
        self.rate_prof = rate_prof
        self.contingency_factor_prof = contingency_factor_prof

        # branch type: Line, Transformer, etc...
        self.branch_type = BranchType.Transformer

        # type template
        self.template = template

        self.vset = vset
        self.Pset = Pset

        self.control_mode = control_mode

        self.bus_to_regulated = bus_to_regulated

        if bus_to_regulated and self.control_mode == TransformerControlType.fixed:
            print(self.name, self.idtag, 'Overriding to V controller')
            self.control_mode = TransformerControlType.Vt

        # converter for enumerations
        self.conv = {'branch': BranchType.Branch,
                     'line': BranchType.Line,
                     'transformer': BranchType.Transformer,
                     'switch': BranchType.Switch,
                     'reactance': BranchType.Reactance}

        self.inv_conv = {val: key for key, val in self.conv.items()}

    def set_hv_and_lv(self, HV, LV):
        """
        set the high and low voltage values
        :param HV: higher voltage value (kV)
        :param LV: lower voltage value (kV)
        """
        if self.bus_from is not None:
            vh = max(self.bus_from.Vnom, self.bus_to.Vnom)
            vl = min(self.bus_from.Vnom, self.bus_to.Vnom)
        else:
            vh = 1.0
            vl = 1.0

        if HV is None:
            self.HV = vh
        else:
            self.HV = HV

        if LV is None:
            self.LV = vl
        else:
            self.LV = LV

    @property
    def R_corrected(self):
        """
        Returns a temperature corrected resistance based on a formula provided by:
        NFPA 70-2005, National Electrical Code, Table 8, footnote #2; and
        https://en.wikipedia.org/wiki/Electrical_resistivity_and_conductivity#Linear_approximation
        (version of 2019-01-03 at 15:20 EST).
        """
        return self.R * (1 + self.alpha * (self.temp_oper - self.temp_base))

    def change_base(self, Sbase_old, Sbase_new):

        b = Sbase_new / Sbase_old

        self.R *= b
        self.X *= b
        self.G *= b
        self.B *= b

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
        b = Transformer2W(bus_from=f,
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
                          template=self.template)

        b.measurements = self.measurements

        b.active_prof = self.active_prof
        b.rate_prof = self.rate_prof
        b.Cost_prof = self.Cost_prof

        return b

    def flip(self):

        F, T = self.bus_from, self.bus_to
        self.bus_to, self.bus_from = F, T

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

    def get_buses_voltages(self):
        bus_f_v = self.bus_from.Vnom
        bus_t_v = self.bus_to.Vnom
        if bus_f_v > bus_t_v:
            return bus_f_v, bus_t_v
        else:
            return bus_t_v, bus_f_v

    def get_from_to_nominal_voltages(self):

        bus_f_v = self.bus_from.Vnom
        bus_t_v = self.bus_to.Vnom

        dhf = abs(self.HV - bus_f_v)
        dht = abs(self.HV - bus_t_v)

        if dhf < dht:
            # the HV side is on the from side
            tpe_f_v = self.HV
            tpe_t_v = self.LV
        else:
            # the HV side is on the to side
            tpe_t_v = self.HV
            tpe_f_v = self.LV

        return tpe_f_v, tpe_t_v

    def get_virtual_taps(self):
        """
        Get the branch virtual taps

        The virtual taps generate when a transformer nominal winding voltage differs
        from the bus nominal voltage.

        Returns:

            **tap_f** (float, 1.0): Virtual tap at the *from* side

            **tap_t** (float, 1.0): Virtual tap at the *to* side

        """
        # resolve how the transformer is actually connected and set the virtual taps
        bus_f_v = self.bus_from.Vnom
        bus_t_v = self.bus_to.Vnom

        # obtain the nominal voltages at the from and to sides
        tpe_f_v, tpe_t_v = self.get_from_to_nominal_voltages()

        tap_f = tpe_f_v / bus_f_v if bus_f_v > 0 else 1.0
        tap_t = tpe_t_v / bus_t_v if bus_t_v > 0 else 1.0

        if tap_f == 0.0:
            tap_f = 1.0

        if tap_t == 0.0:
            tap_t = 1.0

        return tap_f, tap_t

    def apply_template(self, obj: TransformerType, Sbase, logger=Logger()):
        """
        Apply a branch template to this object

        Arguments:
            **obj**: TransformerType or Tower object
            **Sbase** (float): circuit base power in MVA
            **logger** (list, []): Log list
        """
        if isinstance(obj, TransformerType):

            VH, VL = self.get_buses_voltages()

            # get the transformer impedance in the base of the transformer
            z_series, y_shunt = obj.get_impedances(VH=VH, VL=VL, Sbase=Sbase)

            self.R = np.round(z_series.real, 6)
            self.X = np.round(z_series.imag, 6)
            self.G = np.round(y_shunt.real, 6)
            self.B = np.round(y_shunt.imag, 6)

            self.rate = obj.rating

            self.HV = obj.HV
            self.LV = obj.LV

            if self.template is not None:
                if obj != self.template:
                    self.template = obj
                else:
                    logger.add_error('Template not recognised', self.name)
            else:
                self.template = obj

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

            elif properties.tpe == DeviceType.BusDevice:
                obj = obj.idtag

            elif properties.tpe == DeviceType.TransformerTypeDevice:
                if obj is None:
                    obj = ''
                else:
                    obj = obj.idtag

            elif properties.tpe not in [str, float, int, bool]:
                obj = str(obj)

            data.append(obj)
        return data

    def get_properties_dict(self, version=3):
        """
        Get json dictionary
        :return:
        """
        # get the virtual taps
        tap_f, tap_t = self.get_virtual_taps()

        # get the nominal voltages
        v_from, v_to = self.get_from_to_nominal_voltages()

        '''
        TransformerControlType(Enum):
        fixed = '0:Fixed'
        Pt = '1:Pt'
        Qt = '2:Qt'
        PtQt = '3:Pt+Qt'
        Vt = '4:Vt'
        PtVt = '5:Pt+Vt'
        
        '''
        control_modes = {TransformerControlType.fixed: 0,
                         TransformerControlType.Vt: 1,
                         TransformerControlType.Pt: 2,
                         TransformerControlType.PtVt: 3,
                         TransformerControlType.Qt: 4,
                         TransformerControlType.PtQt: 5}
        if version == 2:
            d = {'id': self.idtag,
                 'type': 'transformer',
                 'phases': 'ps',
                 'name': self.name,
                 'name_code': self.code,
                 'bus_from': self.bus_from.idtag,
                 'bus_to': self.bus_to.idtag,
                 'active': self.active,
                 'rate': self.rate,
                 'Vnomf': v_from,
                 'Vnomt': v_to,
                 'hv': self.HV,
                 'lv': self.LV,
                 'r': self.R,
                 'x': self.X,
                 'g': self.G,
                 'b': self.B,
                 'tap_module': self.tap_module,
                 'min_tap_module': self.tap_module_min,
                 'max_tap_module': self.tap_module_max,
                 'id_tap_module_table': "",

                 'tap_angle': self.angle,
                 'min_tap_angle': self.angle_min,
                 'max_tap_angle': self.angle_max,
                 'id_tap_angle_table': "",

                 'control_mode': control_modes[self.control_mode],

                 # 'min_tap_position': self.tap_changer.min_tap,
                 # 'max_tap_position': self.tap_changer.max_tap,
                 # 'tap_inc_reg_down': self.tap_changer.inc_reg_down,
                 # 'tap_inc_reg_up': self.tap_changer.inc_reg_up,
                 # 'virtual_tap_from': tap_f,
                 # 'virtual_tap_to': tap_t,
                 # 'bus_to_regulated': self.bus_to_regulated,

                 'vset': self.vset,
                 'pset': self.Pset,

                 'base_temperature': self.temp_base,
                 'operational_temperature': self.temp_oper,
                 'alpha': self.alpha
                 }

        elif version == 3:
            d = {'id': self.idtag,
                 'type': 'transformer',
                 'phases': 'ps',
                 'name': self.name,
                 'name_code': self.code,
                 'bus_from': self.bus_from.idtag,
                 'bus_to': self.bus_to.idtag,
                 'active': self.active,
                 'rate': self.rate,
                 'contingency_factor1': self.contingency_factor,
                 'contingency_factor2': self.contingency_factor,
                 'contingency_factor3': self.contingency_factor,

                 'Vnomf': v_from,
                 'Vnomt': v_to,
                 'hv': self.HV,
                 'lv': self.LV,
                 'r': self.R,
                 'x': self.X,
                 'g': self.G,
                 'b': self.B,
                 'tap_module': self.tap_module,
                 'min_tap_module': self.tap_module_min,
                 'max_tap_module': self.tap_module_max,
                 'id_tap_module_table': "",

                 'tap_angle': self.angle,
                 'min_tap_angle': self.angle_min,
                 'max_tap_angle': self.angle_max,
                 'id_tap_angle_table': "",

                 'control_mode': control_modes[self.control_mode],

                 # 'min_tap_position': self.tap_changer.min_tap,
                 # 'max_tap_position': self.tap_changer.max_tap,
                 # 'tap_inc_reg_down': self.tap_changer.inc_reg_down,
                 # 'tap_inc_reg_up': self.tap_changer.inc_reg_up,
                 # 'virtual_tap_from': tap_f,
                 # 'virtual_tap_to': tap_t,
                 # 'bus_to_regulated': self.bus_to_regulated,

                 'vset': self.vset,
                 'pset': self.Pset,

                 'base_temperature': self.temp_base,
                 'operational_temperature': self.temp_oper,
                 'alpha': self.alpha
                 }
        else:
            d = dict()

        return d

    def get_profiles_dict(self, version=3):
        """

        :return:
        """
        if self.active_prof is not None:
            active_prof = self.active_prof.tolist()
            rate_prof = self.rate_prof.tolist()
        else:
            active_prof = list()
            rate_prof = list()

        return {'id': self.idtag,
                'active': active_prof,
                'rate': rate_prof}

    def get_units_dict(self, version=3):
        """
        Get units of the values
        """
        return {'rate': 'MW',
                'r': 'p.u.',
                'x': 'p.u.',
                'b': 'p.u.',
                'g': 'p.u.',
                'base_temperature': 'ºC',
                'operational_temperature': 'ºC',
                'alpha': '1/ºC'}

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
            y = time_series.results.loading.real * 100.0
            df = pd.DataFrame(data=y[:, my_index], index=x, columns=[self.name])
            ax_1.set_title('Loading', fontsize=14)
            ax_1.set_ylabel('Loading [%]', fontsize=11)
            df.plot(ax=ax_1)

            # losses
            y = np.abs(time_series.results.losses)
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

    def delete_virtual_taps(self):
        """
        Set the HV and LV parameters such that any virtual tap is null
        """
        self.HV = max(self.bus_from.Vnom, self.bus_to.Vnom)
        self.LV = min(self.bus_from.Vnom, self.bus_to.Vnom)

    def fix_inconsistencies(self, logger: Logger, maximum_difference=0.1):
        """
        Fix the voltage inconsistencies
        :param logger:
        :param maximum_difference: proportion to be under or above (i.e. Transformer HV=41.9, bus HV=45 41.9/45 = 0.93 -> 0.9 <= 0.93 <= 1.1, so its ok
        :return:
        """
        errors = False
        HV = max(self.bus_from.Vnom, self.bus_to.Vnom)
        LV = min(self.bus_from.Vnom, self.bus_to.Vnom)

        if self.LV > self.HV:
            logger.add_warning("HV > LV", self.name, self.HV, HV)
            self.HV, self.LV = self.LV, self.HV
            errors = True

        rHV = self.HV / HV
        rLV = self.LV / LV
        LB = 1 - maximum_difference
        UB = 1 + maximum_difference
        if not (LB <= rHV <= UB):
            logger.add_warning("Corrected transformer HV", self.name, self.HV, HV)
            self.HV = HV
            errors = True

        if not (LB <= rLV <= UB):
            logger.add_warning("Corrected transformer LV", self.name, self.LV, LV)
            self.LV = LV
            errors = True

        return errors
