# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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

import copy
import numpy as np
from typing import Union, Tuple
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Core.Devices.Substation.bus import Bus
from GridCalEngine.Core.Devices.enumerations import BranchType, BuildStatus
from GridCalEngine.Core.Devices.Branches.templates.underground_line import UndergroundLineType
from GridCalEngine.Core.Devices.Branches.templates.overhead_line_type import OverheadLineType
from GridCalEngine.Core.Devices.Branches.transformer import Transformer2W
from GridCalEngine.Core.Devices.Branches.templates.parent_branch import ParentBranch
from GridCalEngine.Core.Devices.Branches.templates.sequence_line_type import SequenceLineType
from GridCalEngine.Core.Devices.Branches.templates.line_template import LineTemplate
from GridCalEngine.Core.Devices.editable_device import DeviceType


class Line(ParentBranch):
    """
    The **Line** class represents the connections between nodes (i.e.
    :ref:`buses<bus>`) in **GridCal**. A branch is an element (cable, line, capacitor,
    transformer, etc.) with an electrical impedance. The basic **Branch** class
    includes basic electrical attributes for most passive elements, but other device
    types may be passed to the **Branch** constructor to configure it as a specific
    type.

    For example, a transformer may be created with the following code:

    .. code:: ipython3

        from GridCalEngine.Core.multi_circuit import MultiCircuit
        from GridCalEngine.Core.Devices import *
        from GridCalEngine.Core.Devices.types import *

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

    Refer to the :class:`GridCalEngine.Devices.branch.TapChanger` class for an example
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

        **branch_type** (BranchType, BranchType.Line): Device type enumeration (ex.: :class:`GridCalEngine.Devices.transformer.TransformerType`)

        **length** (float, 0.0): Length of the branch in km

        **vset** (float, 1.0): Voltage set-point of the voltage controlled bus in per unit

        **temp_base** (float, 20.0): Base temperature at which `r` is measured in °C

        **temp_oper** (float, 20.0): Operating temperature in °C

        **alpha** (float, 0.0033): Thermal constant of the material in °C

        **bus_to_regulated** (bool, False): Is the `bus_to` voltage regulated by this branch?

        **template** (BranchTemplate, BranchTemplate()): Basic branch template
    """

    def __init__(self, bus_from: Bus = None, bus_to: Bus = None, name='Line', idtag=None, code='',
                 r=1e-20, x=1e-20, b=1e-20, rate=1.0, active=True, tolerance=0, cost=100.0,
                 mttf=0, mttr=0, r_fault=0.0, x_fault=0.0, fault_pos=0.5,
                 length=1, temp_base=20, temp_oper=20, alpha=0.00330,
                 template=LineTemplate(), rate_prof=None, Cost_prof=None, active_prof=None, temp_oper_prof=None,
                 contingency_factor=1.0, contingency_enabled=True, monitor_loading=True, contingency_factor_prof=None,
                 r0=1e-20, x0=1e-20, b0=1e-20, r2=1e-20, x2=1e-20, b2=1e-20,
                 capex=0, opex=0, build_status: BuildStatus = BuildStatus.Commissioned):

        ParentBranch.__init__(self,
                              name=name,
                              idtag=idtag,
                              code=code,
                              bus_from=bus_from,
                              bus_to=bus_to,
                              active=active,
                              active_prof=active_prof,
                              rate=rate,
                              rate_prof=rate_prof,
                              contingency_factor=contingency_factor,
                              contingency_factor_prof=contingency_factor_prof,
                              contingency_enabled=contingency_enabled,
                              monitor_loading=monitor_loading,
                              mttf=mttf,
                              mttr=mttr,
                              build_status=build_status,
                              capex=capex,
                              opex=opex,
                              Cost=cost,
                              Cost_prof=Cost_prof,
                              device_type=DeviceType.LineDevice,
                              branch_type=BranchType.Line)

        # List of measurements
        self.measurements = list()

        # line length in km
        self.length = length

        # line impedance tolerance
        self.tolerance = tolerance

        # short circuit impedance
        self.r_fault = r_fault
        self.x_fault = x_fault
        self.fault_pos = fault_pos

        # total impedance and admittance in p.u.
        self.R = r
        self.X = x
        self.B = b

        self.R0 = r0
        self.X0 = x0
        self.B0 = b0

        self.R2 = r2
        self.X2 = x2
        self.B2 = b2

        # Conductor base and operating temperatures in ºC
        self.temp_base = temp_base
        self.temp_oper = temp_oper

        self.temp_oper_prof = temp_oper_prof

        # Conductor thermal constant (1/ºC)
        self.alpha = alpha

        # line type: Line, Transformer, etc...
        self.branch_type = BranchType.Line

        # type template
        self.template = template

        self.register(key='R', units='p.u.', tpe=float, definition='Total positive sequence resistance.')
        self.register(key='X', units='p.u.', tpe=float, definition='Total positive sequence reactance.')
        self.register(key='B', units='p.u.', tpe=float, definition='Total positive sequence shunt susceptance.')
        self.register(key='R0', units='p.u.', tpe=float, definition='Total zero sequence resistance.')
        self.register(key='X0', units='p.u.', tpe=float, definition='Total zero sequence reactance.')
        self.register(key='B0', units='p.u.', tpe=float, definition='Total zero sequence shunt susceptance.')
        self.register(key='R2', units='p.u.', tpe=float, definition='Total negative sequence resistance.')
        self.register(key='X2', units='p.u.', tpe=float, definition='Total negative sequence reactance.')
        self.register(key='B2', units='p.u.', tpe=float, definition='Total negative sequence shunt susceptance.')
        self.register(key='tolerance', units='%', tpe=float,
                      definition='Tolerance expected for the impedance values % is expected for transformers0% for lines.')
        self.register(key='length', units='km', tpe=float, definition='Length of the line (not used for calculation)')
        self.register(key='temp_base', units='ºC', tpe=float, definition='Base temperature at which R was measured.')
        self.register(key='temp_oper', units='ºC', tpe=float, definition='Operation temperature to modify R.',
                      profile_name='temp_oper_prof')
        self.register(key='alpha', units='1/ºC', tpe=float,
                      definition='Thermal coefficient to modify R,around a reference temperatureusing a linear approximation.For example:Copper @ 20ºC: 0.004041,Copper @ 75ºC: 0.00323,Annealed copper @ 20ºC: 0.00393,Aluminum @ 20ºC: 0.004308,Aluminum @ 75ºC: 0.00330')
        self.register(key='Cost', units='e/MWh', tpe=float, definition='Cost of overloads. Used in OPF.',
                      profile_name='Cost_prof')
        self.register(key='capex', units='e/MW', tpe=float,
                      definition='Cost of investment. Used in expansion planning.')
        self.register(key='opex', units='e/MWh', tpe=float, definition='Cost of operation. Used in expansion planning.')
        self.register(key='build_status', units='', tpe=BuildStatus,
                      definition='Branch build status. Used in expansion planning.')
        self.register(key='r_fault', units='p.u.', tpe=float,
                      definition='Resistance of the mid-line fault.Used in short circuit studies.')
        self.register(key='x_fault', units='p.u.', tpe=float,
                      definition='Reactance of the mid-line fault.Used in short circuit studies.')
        self.register(key='fault_pos', units='p.u.', tpe=float,
                      definition='Per-unit positioning of the fault:0 would be at the "from" side,1 would be at the "to" side,therefore 0.5 is at the middle.')
        self.register(key='template', units='', tpe=DeviceType.SequenceLineDevice, definition='')

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
        """
        Change the inpedance base
        :param Sbase_old: old base (MVA)
        :param Sbase_new: new base (MVA)
        """
        b = Sbase_new / Sbase_old

        self.R *= b
        self.X *= b
        self.B *= b

    def get_weight(self) -> float:
        """
        Get a weight of this line for graph porpuses
        the weight is the impedance moudule (sqrt(r^2 + x^2))
        :return: weight value
        """
        return np.sqrt(self.R * self.R + self.X * self.X)

    def apply_template(self, obj: Union[OverheadLineType, UndergroundLineType, SequenceLineType], Sbase: float,
                       logger=Logger()):
        """
        Apply a line template to this object
        :param obj: OverheadLineType, UndergroundLineType, SequenceLineType
        :param Sbase: Nominal power in MVA
        :param logger: Logger
        """

        if type(obj) is OverheadLineType:

            if self.branch_type == BranchType.Line:
                Vn = self.bus_to.Vnom
                Zbase = (Vn * Vn) / Sbase
                Ybase = 1 / Zbase

                z1 = obj.z_series() * self.length / Zbase
                y1 = obj.y_shunt() * self.length / Ybase
                self.R = np.round(z1.real, 6)
                self.X = np.round(z1.imag, 6)
                self.B = np.round(y1.imag, 6)

                z0 = obj.z0_series() * self.length / Zbase
                y0 = obj.y0_shunt() * self.length / Ybase
                self.R = np.round(z0.real, 6)
                self.X = np.round(z0.imag, 6)
                self.B = np.round(y0.imag, 6)

                z2 = obj.z2_series() * self.length / Zbase
                y2 = obj.y2_shunt() * self.length / Ybase
                self.R = np.round(z2.real, 6)
                self.X = np.round(z2.imag, 6)
                self.B = np.round(y2.imag, 6)

                # get the rating in MVA = kA * kV
                self.rate = obj.rating * Vn * np.sqrt(3)

                if self.template is not None:
                    if obj != self.template:
                        self.template = obj
                else:
                    self.template = obj
            else:
                raise Exception('You are trying to apply an Overhead line type to a non-line line')

        elif type(obj) is UndergroundLineType:
            Vn = self.bus_to.Vnom
            Zbase = (Vn * Vn) / Sbase
            Ybase = 1 / Zbase

            z = obj.z_series() * self.length / Zbase
            y = obj.y_shunt() * self.length / Ybase

            self.R = np.round(z.real, 6)
            self.X = np.round(z.imag, 6)
            self.B = np.round(y.imag, 6)

            # get the rating in MVA = kA * kV
            self.rate = obj.rating * Vn * np.sqrt(3)

            if self.template is not None:
                if obj != self.template:
                    self.template = obj
            else:
                self.template = obj

        elif type(obj) is SequenceLineType:

            Vn = self.bus_to.Vnom
            Zbase = (Vn * Vn) / Sbase
            Ybase = 1 / Zbase

            self.R = np.round(obj.R * self.length / Zbase, 6)
            self.X = np.round(obj.X * self.length / Zbase, 6)
            self.B = np.round(obj.B * self.length / Ybase, 6)

            # get the rating in MVA = kA * kV
            self.rate = obj.rating * Vn * np.sqrt(3)

            if self.template is not None:
                if obj != self.template:
                    self.template = obj
            else:
                self.template = obj

        else:
            logger.add_error('Template not recognised', self.name)

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
            if properties.tpe == DeviceType.BusDevice:
                obj = obj.idtag

            elif properties.tpe == LineTemplate:
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
        if version == 2:
            return {'id': self.idtag,
                    'type': 'line',
                    'phases': 'ps',
                    'name': self.name,
                    'name_code': self.code,
                    'bus_from': self.bus_from.idtag,
                    'bus_to': self.bus_to.idtag,
                    'active': self.active,

                    'rate': self.rate,
                    'r': self.R,
                    'x': self.X,
                    'b': self.B,

                    'length': self.length,
                    'base_temperature': self.temp_base,
                    'operational_temperature': self.temp_oper,
                    'alpha': self.alpha,
                    'locations': []
                    }

        elif version == 3:
            return {'id': self.idtag,
                    'type': 'line',
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
                    'r': self.R,
                    'x': self.X,
                    'b': self.B,

                    'length': self.length,
                    'base_temperature': self.temp_base,
                    'operational_temperature': self.temp_oper,
                    'alpha': self.alpha,

                    'overload_cost': self.Cost,
                    'capex': self.capex,
                    'opex': self.opex,
                    'build_status': str(self.build_status.value).lower(),

                    'locations': []
                    }
        else:
            return dict()

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
                'length': 'km',
                'base_temperature': 'ºC',
                'operational_temperature': 'ºC',
                'alpha': '1/ºC'}

    def convertible_to_vsc(self):
        """
        Is this line convertible to VSC?
        :return:
        """
        if self.bus_to is not None and self.bus_from is not None:
            # connectivity:
            # for the later primitives to make sense, the "bus from" must be AC and the "bus to" must be DC
            if self.bus_from.is_dc and not self.bus_to.is_dc:  # this is the correct sense
                return True
            elif not self.bus_from.is_dc and self.bus_to.is_dc:  # opposite sense, revert
                return True
            else:
                return False
        else:
            return False

    def fix_inconsistencies(self, logger: Logger):
        """
        Fix the inconsistencies
        :param logger:
        :return:
        """
        errors = False

        if self.R < 0.0:
            logger.add_warning("Corrected transformer R<0", self.name, self.R, -self.R)
            self.R = -self.R
            errors = True

        return errors

    @property
    def Vf(self) -> float:
        """
        Get the voltage "from" (kV)
        :return: get the nominal voltage from
        """
        return self.bus_from.Vnom

    @property
    def Vt(self) -> float:
        """
        Get the voltage "to" (kV)
        :return: get the nominal voltage to
        """
        return self.bus_to.Vnom

    def should_this_be_a_transformer(self, branch_connection_voltage_tolerance: float = 0.1) -> bool:
        """

        :param branch_connection_voltage_tolerance:
        :return:
        """
        V1 = min(self.bus_to.Vnom, self.bus_from.Vnom)
        V2 = max(self.bus_to.Vnom, self.bus_from.Vnom)
        if V2 > 0:
            per = V1 / V2
            return per < (1.0 - branch_connection_voltage_tolerance)
        else:
            return V1 != V2

    def get_equivalent_transformer(self) -> Transformer2W:
        """
        Convert this line into a transformer
        This is necessary if the buses' voltage differ too much
        :return: Transformer2W
        """
        V1 = min(self.bus_to.Vnom, self.bus_from.Vnom)
        V2 = max(self.bus_to.Vnom, self.bus_from.Vnom)
        return Transformer2W(bus_from=self.bus_from,
                             bus_to=self.bus_to,
                             name=self.name,
                             code=self.code,
                             active=self.active,
                             rate=self.rate,
                             HV=V2,
                             LV=V1,
                             r=self.R,
                             x=self.X,
                             b=self.B,
                             active_prof=self.active_prof,
                             rate_prof=self.rate_prof)

    def split_line(self, position: float) -> Tuple["Line", "Line", Bus]:
        """
        Split a branch by a given distance
        :param position: per unit distance measured from the "from" bus (0 ~ 1)
        :return: the two new Branches and the mid short circuited bus
        """

        assert (0.0 < position < 1.0)

        # Each of the Branches will have the proportional impedance
        # Bus_from           Middle_bus            Bus_To
        # o----------------------o--------------------o
        #   >-------- x -------->|
        #   (x: distance measured in per unit (0~1)

        middle_bus = self.bus_from.copy()
        middle_bus.name += ' split'
        middle_bus.delete_children()

        # C(x, y) = (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
        middle_bus.x = self.bus_from.x + (self.bus_to.x - self.bus_from.x) * position
        middle_bus.y = self.bus_from.y + (self.bus_to.y - self.bus_from.y) * position

        props_to_scale = ['R', 'R0', 'X', 'X0', 'B', 'B0', 'length']  # list of properties to scale

        br1 = self.copy()
        br1.bus_from = self.bus_from
        br1.bus_to = middle_bus
        for p in props_to_scale:
            setattr(br1, p, getattr(self, p) * position)

        br2 = self.copy()
        br2.bus_from = middle_bus
        br2.bus_to = self.bus_to
        for p in props_to_scale:
            setattr(br2, p, getattr(self, p) * (1.0 - position))

        return br1, br2, middle_bus
