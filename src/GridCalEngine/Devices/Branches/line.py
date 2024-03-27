# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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

import numpy as np
from typing import Union
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.enumerations import BuildStatus, SubObjectType, DeviceType
from GridCalEngine.Devices.Branches.underground_line_type import UndergroundLineType
from GridCalEngine.Devices.Branches.overhead_line_type import OverheadLineType
from GridCalEngine.Devices.Parents.branch_parent import BranchParent
from GridCalEngine.Devices.Branches.sequence_line_type import SequenceLineType
from GridCalEngine.Devices.Branches.transformer import Transformer2W
from GridCalEngine.Devices.profile import Profile
from GridCalEngine.Devices.Branches.line_locations import LineLocations


class Line(BranchParent):

    def __init__(self, bus_from: Bus = None, bus_to: Bus = None, cn_from: ConnectivityNode = None,
                 cn_to: ConnectivityNode = None, name='Line', idtag=None, code='',
                 r=1e-20, x=0.00001, b=1e-20, rate=1.0, active=True, tolerance=0.0, cost=100.0,
                 mttf=0.0, mttr=0, r_fault=0.0, x_fault=0.0, fault_pos=0.5,
                 length=1.0, temp_base=20, temp_oper=20, alpha=0.00330,
                 template=None, contingency_factor=1.0, protection_rating_factor: float = 1.4,
                 contingency_enabled=True, monitor_loading=True,
                 r0=1e-20, x0=1e-20, b0=1e-20, r2=1e-20, x2=1e-20, b2=1e-20,
                 capex=0, opex=0, build_status: BuildStatus = BuildStatus.Commissioned):
        """
        AC current Line
        :param bus_from: "From" :ref:`bus<Bus>` object
        :param bus_to: "To" :ref:`bus<Bus>` object
        :param name: Name of the branch
        :param idtag: UUID code
        :param code: secondary ID
        :param r: Branch resistance in per unit
        :param x: Branch reactance in per unit
        :param b: Branch shunt susceptance in per unit
        :param rate: Branch rate in MVA
        :param active: Is the branch active?
        :param tolerance: Tolerance specified for the branch impedance in %
        :param cost: overload cost
        :param mttf: Mean time to failure in hours
        :param mttr: Mean time to recovery in hours
        :param r_fault: Mid-line fault resistance in per unit (SC only)
        :param x_fault: Mid-line fault reactance in per unit (SC only)
        :param fault_pos: Mid-line fault position in per unit (0.0 = `bus_from`, 0.5 = middle, 1.0 = `bus_to`)
        :param length: Length of the branch in km
        :param temp_base: Base temperature at which `r` is measured in °C
        :param temp_oper: Operating temperature in °C
        :param alpha: Thermal constant of the material in °C
        :param template: Basic branch template
        :param contingency_factor: Rating factor in case of contingency
        :param protection_rating_factor: Rating factor before the protections tripping
        :param contingency_enabled: enabled for contingencies (Legacy)
        :param monitor_loading: monitor the loading (used in OPF)
        :param r0: zero-sequence resistence (p.u.)
        :param x0: zero-sequence reactance (p.u.)
        :param b0: zero-sequence susceptance (p.u.)
        :param r2: negative-sequence resistence (p.u.)
        :param x2: negative-sequence reactance (p.u.)
        :param b2: negative-sequence susceptance (p.u.)
        :param capex: Cost of investment (e/MW)
        :param opex: Cost of operation (e/MWh)
        :param build_status: build status (now time)
        """

        BranchParent.__init__(self,
                              name=name,
                              idtag=idtag,
                              code=code,
                              bus_from=bus_from,
                              bus_to=bus_to,
                              cn_from=cn_from,
                              cn_to=cn_to,
                              active=active,
                              rate=rate,
                              contingency_factor=contingency_factor,
                              protection_rating_factor=protection_rating_factor,
                              contingency_enabled=contingency_enabled,
                              monitor_loading=monitor_loading,
                              mttf=mttf,
                              mttr=mttr,
                              build_status=build_status,
                              capex=capex,
                              opex=opex,
                              Cost=cost,
                              device_type=DeviceType.LineDevice)

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
        self._temp_oper_prof = Profile(default_value=temp_oper)

        # Conductor thermal constant (1/ºC)
        self.alpha = alpha

        # type template
        self.template: Union[OverheadLineType, SequenceLineType, UndergroundLineType] = template

        # Line locations
        self._locations: LineLocations = LineLocations()

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
                      definition='Tolerance expected for the impedance values % is expected '
                                 'for transformers0% for lines.')

        self.register(key='length', units='km', tpe=float, definition='Length of the line (not used for calculation)')
        self.register(key='temp_base', units='ºC', tpe=float, definition='Base temperature at which R was measured.')
        self.register(key='temp_oper', units='ºC', tpe=float, definition='Operation temperature to modify R.',
                      profile_name='temp_oper_prof')
        self.register(key='alpha', units='1/ºC', tpe=float,
                      definition='Thermal coefficient to modify R,around a reference temperatureusing a '
                                 'linear approximation.For example:Copper @ 20ºC: 0.004041,Copper @ 75ºC: 0.00323,'
                                 'Annealed copper @ 20ºC: 0.00393,Aluminum @ 20ºC: 0.004308,Aluminum @ 75ºC: 0.00330')
        self.register(key='r_fault', units='p.u.', tpe=float,
                      definition='Resistance of the mid-line fault.Used in short circuit studies.')
        self.register(key='x_fault', units='p.u.', tpe=float,
                      definition='Reactance of the mid-line fault.Used in short circuit studies.')
        self.register(key='fault_pos', units='p.u.', tpe=float,
                      definition='Per-unit positioning of the fault:'
                                 '0 would be at the "from" side,'
                                 '1 would be at the "to" side,'
                                 'therefore 0.5 is at the middle.')
        self.register(key='template', units='', tpe=DeviceType.SequenceLineDevice, definition='', editable=False)
        self.register(key='locations', units='', tpe=SubObjectType.LineLocations, definition='', editable=False)

    @property
    def temp_oper_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._temp_oper_prof

    @temp_oper_prof.setter
    def temp_oper_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._temp_oper_prof = val
        elif isinstance(val, np.ndarray):
            self._temp_oper_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a temp_oper_prof')

    @property
    def locations(self) -> LineLocations:
        """
        Cost profile
        :return: Profile
        """
        return self._locations

    @locations.setter
    def locations(self, val: Union[LineLocations, np.ndarray]):
        if isinstance(val, LineLocations):
            self._locations = val
        elif isinstance(val, np.ndarray):
            self._locations.set(data=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a locations')

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

        if type(obj) in [OverheadLineType, UndergroundLineType, SequenceLineType]:

            self.R, self.X, self.B, self.R0, self.X0, self.B0, self.rate = obj.get_values(Sbase=Sbase,
                                                                                          length=self.length)

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
        for name, properties in self.registered_properties.items():
            obj = getattr(self, name)

            if obj is None:
                data.append("")
            else:

                if hasattr(obj, 'idtag'):
                    obj = obj.idtag
                else:
                    if properties.tpe not in [str, float, int, bool]:
                        obj = str(obj)
                    else:
                        obj = str(obj)

                data.append(obj)
        return data

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

    def should_this_be_a_transformer(self, branch_connection_voltage_tolerance: float = 0.1) -> bool:
        """

        :param branch_connection_voltage_tolerance:
        :return:
        """
        if self.bus_to is not None and self.bus_from is not None:
            V1 = min(self.bus_to.Vnom, self.bus_from.Vnom)
            V2 = max(self.bus_to.Vnom, self.bus_from.Vnom)
            if V2 > 0:
                per = V1 / V2
                return per < (1.0 - branch_connection_voltage_tolerance)
            else:
                return V1 != V2
        else:
            return False

    def get_equivalent_transformer(self) -> Transformer2W:
        """
        Convert this line into a transformer
        This is necessary if the buses' voltage differ too much
        :return: Transformer2W
        """
        V1 = min(self.bus_to.Vnom, self.bus_from.Vnom)
        V2 = max(self.bus_to.Vnom, self.bus_from.Vnom)
        elm = Transformer2W(bus_from=self.bus_from,
                            bus_to=self.bus_to,
                            name=self.name,
                            code=self.code,
                            active=self.active,
                            rate=self.rate,
                            HV=V2,
                            LV=V1,
                            r=self.R,
                            x=self.X,
                            b=self.B)
        elm.active_prof = self.active_prof
        elm.rate_prof = self.rate_prof
        elm.temperature_prof = self.temp_oper_prof
        return elm

    def fill_design_properties(self, r_ohm, x_ohm, c_nf, length, Imax, freq, Sbase):
        """
        Fill R, X, B from not-in-per-unit parameters
        :param r_ohm: Resistance per km in OHM
        :param x_ohm: Reactance per km in OHM
        :param c_nf: Capacitance per km in nF
        :param length: lenght in kn
        :param Imax: Maximum current in kA
        :param freq: System frequency in Hz
        :param Sbase: Base power in MVA (take always 100 MVA)
        """
        R = r_ohm * length
        X = x_ohm * length
        B = (
                    2 * np.pi * freq * c_nf * 1e-9) * length  # impedance = 1 / (2 * pi * f * c), susceptance = (2 * pi * f * c)

        Vf = self.get_max_bus_nominal_voltage()

        Zbase = (Vf * Vf) / Sbase
        Ybase = 1.0 / Zbase

        self.R = np.round(R / Zbase, 6)
        self.X = np.round(X / Zbase, 6)
        self.B = np.round(B / Ybase, 6)
        self.rate = np.round(Imax * Vf * 1.73205080757, 6)  # nominal power in MVA = kA * kV * sqrt(3)
        self.length = length
