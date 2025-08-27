# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import pandas as pd
from typing import Union, List

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.enumerations import BuildStatus, SubObjectType, DeviceType
from VeraGridEngine.Devices.Branches.underground_line_type import UndergroundLineType
from VeraGridEngine.Devices.Branches.overhead_line_type import OverheadLineType
from VeraGridEngine.Devices.Parents.branch_parent import BranchParent
from VeraGridEngine.Devices.Branches.sequence_line_type import SequenceLineType, get_line_impedances_with_c
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.profile import Profile
from VeraGridEngine.Devices.Associations.association import Associations
from VeraGridEngine.Devices.Branches.line_locations import LineLocations
from VeraGridEngine.Devices.admittance_matrix import AdmittanceMatrix
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Const, DynamicVarType
from VeraGridEngine.Utils.Symbolic.symbolic import cos, sin


def accept_line_connection(V1: float, V2: float, branch_connection_voltage_tolerance=0.1) -> float:
    """
    This function checks if a line can be connected between 2 voltages
    :param V1: Voltage 1
    :param V2: Voltage 2
    :param branch_connection_voltage_tolerance:
    :return: Can be connected?
    """
    if V2 > 0:
        per = V1 / V2

        if per < (1.0 - branch_connection_voltage_tolerance):
            return False
        else:
            return True
    else:
        return V1 == V2


class Line(BranchParent):
    __slots__ = (
        '_length',
        'tolerance',
        'r_fault',
        'x_fault',
        'fault_pos',
        '_R',
        '_X',
        '_B',
        '_R0',
        '_X0',
        '_B0',
        '_R2',
        '_X2',
        '_B2',
        '_ys',
        '_ysh',
        'temp_base',
        'temp_oper',
        '_temp_oper_prof',
        'alpha',
        '_circuit_idx',
        'template',
        'possible_tower_types',
        'possible_underground_line_types',
        'possible_sequence_line_types',
        '_locations',
    )

    def __init__(self,
                 bus_from: Bus = None,
                 bus_to: Bus = None,
                 name='Line',
                 idtag=None,
                 code='',
                 r=1e-20, x=0.00001, b=1e-20,
                 rate=1.0,
                 active=True,
                 tolerance=0.0,
                 cost=100.0,
                 mttf=0.0,
                 mttr=0,
                 r_fault=0.0,
                 x_fault=0.0,
                 fault_pos=0.5,
                 length=1.0,
                 temp_base=20,
                 temp_oper=20,
                 alpha=0.00330,
                 template=None,
                 contingency_factor=1.0,
                 protection_rating_factor: float = 1.4,
                 contingency_enabled=True,
                 monitor_loading=True,
                 r0=1e-20, x0=1e-20, b0=1e-20,
                 r2=1e-20, x2=1e-20, b2=1e-20,
                 capex=0,
                 opex=0,
                 circuit_idx: int = 1,
                 build_status: BuildStatus = BuildStatus.Commissioned):
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
                              active=active,
                              reducible=False,
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
                              cost=cost,
                              device_type=DeviceType.LineDevice)

        # line length in km
        self._length = float(length)

        # line impedance tolerance
        self.tolerance = float(tolerance)

        # short circuit impedance
        self.r_fault = float(r_fault)
        self.x_fault = float(x_fault)
        self.fault_pos = float(fault_pos)

        # total impedance and admittance in p.u.
        self._R = float(r)
        self._X = float(x)
        self._B = float(b)

        self._R0 = float(r0)
        self._X0 = float(x0)
        self._B0 = float(b0)

        self._R2 = float(r2)
        self._X2 = float(x2)
        self._B2 = float(b2)

        self._ys = AdmittanceMatrix()
        self._ysh = AdmittanceMatrix()

        # Conductor base and operating temperatures in ºC
        self.temp_base = float(temp_base)
        self.temp_oper = float(temp_oper)
        self._temp_oper_prof = Profile(default_value=temp_oper, data_type=float)

        # Conductor thermal constant (1/ºC)
        self.alpha = float(alpha)

        self._circuit_idx: int = int(circuit_idx)

        # type template
        self.template: Union[OverheadLineType, SequenceLineType, UndergroundLineType] = template

        # association with various templates
        self.possible_tower_types: Associations = Associations(device_type=DeviceType.OverheadLineTypeDevice)
        self.possible_underground_line_types: Associations = Associations(device_type=DeviceType.UnderGroundLineDevice)
        self.possible_sequence_line_types: Associations = Associations(device_type=DeviceType.SequenceLineDevice)

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

        self.register('ys', units="p.u.", tpe=SubObjectType.AdmittanceMatrix,
                      definition='Series admittance matrix of the branch', editable=False, display=False)

        self.register('ysh', units="p.u.", tpe=SubObjectType.AdmittanceMatrix,
                      definition='Shunt admittance matrix of the branch', editable=False, display=False)

        self.register(key='tolerance', units='%', tpe=float,
                      definition='Tolerance expected for the impedance values % is expected '
                                 'for transformers0% for lines.')

        self.register(key='circuit_idx', units='', tpe=int,
                      definition='Circuit index, used for multiple circuits sharing towers (starts at zero)',
                      editable=False)

        self.register(key='length', units='km', tpe=float, definition='Length of the line (not used for calculation)')
        self.register(key='temp_base', units='ºC', tpe=float, definition='Base temperature at which R was measured.')
        self.register(key='temp_oper', units='ºC', tpe=float, definition='Operation temperature to modify R.',
                      profile_name='temp_oper_prof')
        self.register(key='alpha', units='1/ºC', tpe=float,
                      definition='Thermal coefficient to modify R,around a reference temperature using a '
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
        self.register(key='template', units='', tpe=DeviceType.AnyLineTemplateDevice, definition='', editable=False)
        self.register(key='locations', units='', tpe=SubObjectType.LineLocations, definition='', editable=False)

        self.register(key='possible_tower_types', units='', tpe=SubObjectType.Associations,
                      definition='Possible overhead line types (>1 to denote association), - to denote no association',
                      display=False)

        self.register(key='possible_underground_line_types', units='', tpe=SubObjectType.Associations,
                      definition='Possible underground line types (>1 to denote association), - to denote no association',
                      display=False)

        self.register(key='possible_sequence_line_types', units='', tpe=SubObjectType.Associations,
                      definition='Possible sequence line types (>1 to denote association), - to denote no association',
                      display=False)

    @property
    def R(self):
        return self._R

    @R.setter
    def R(self, value):
        self._R = float(value)

    @property
    def X(self):
        return self._X

    @X.setter
    def X(self, value):
        self._X = float(value)

    @property
    def B(self):
        return self._B

    @B.setter
    def B(self, value):
        self._B = float(value)

    @property
    def R0(self):
        return self._R0

    @R0.setter
    def R0(self, value):
        self._R0 = float(value)

    @property
    def X0(self):
        return self._X0

    @X0.setter
    def X0(self, value):
        self._X0 = float(value)

    @property
    def B0(self):
        return self._B0

    @B0.setter
    def B0(self, value):
        self._B0 = float(value)

    @property
    def R2(self):
        return self._R2

    @R2.setter
    def R2(self, value):
        self._R2 = float(value)

    @property
    def X2(self):
        return self._X2

    @X2.setter
    def X2(self, value):
        self._X2 = float(value)

    @property
    def B2(self):
        return self._B2

    @B2.setter
    def B2(self, value):
        self._B2 = float(value)

    @property
    def circuit_idx(self):
        return self._circuit_idx

    @circuit_idx.setter
    def circuit_idx(self, value):
        if value > 0:
            self._circuit_idx = int(value)

            if self.auto_update_enabled:
                print(
                    "No impedance updates are being done, use the apply_template method to update the impedance values")

    def set_circuit_idx(self, val: int, obj: Union[OverheadLineType, UndergroundLineType, SequenceLineType]):
        """
        Set the circuit_idx with additional behavior based on the is_user_action flag. Ensure that the template exists and is valid.
        :param val: The value to set
        :param obj: Template
        """
        # If the user is setting the circuit index, ensure that the template exists and is valid
        if obj is None:
            raise Exception("Template must be set before changing the circuit index.")
        if not isinstance(obj, (OverheadLineType, UndergroundLineType, SequenceLineType)):
            raise Exception(
                "Invalid template type. Must be OverheadLineType, UndergroundLineType, or SequenceLineType.")
        if isinstance(obj, OverheadLineType):
            if val > obj.n_circuits:
                raise Exception("Circuit index exceeds the number of circuits in the template.")
        if val <= 0:
            raise Exception("Circuit index must be greater than 0.")
        else:
            if val > 0:
                self._circuit_idx = int(val)

    @property
    def length(self) -> float:
        """
        Line length in km
        :return: float
        """
        return self._length

    @length.setter
    def length(self, val: float):
        """
        Set the length of the line, if a valid length is provided, the electric parameters are scaled appropriately
        :param val:
        :return:
        """
        self.set_length(val)

    def set_length(self, val: float):
        """
        Set the line length and change the electric parameters of the line as a consequence.
        :param val: value in km
        """
        if isinstance(val, float):
            if val > 0.0:
                if self._length != 0 and self.auto_update_enabled:
                    factor = np.round(val / self._length, 6)  # new length / old length

                    self.R *= factor
                    self.X *= factor
                    self.B *= factor
                    self.R0 *= factor
                    self.X0 *= factor
                    self.B0 *= factor
                    self.R2 *= factor
                    self.X2 *= factor
                    self.B2 *= factor

                # set the value
                self._length = val
            else:
                # print('The length cannot be zero, ignoring value')
                pass
        else:
            raise Exception('The length must be a float value')

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

    @property
    def ys(self) -> AdmittanceMatrix:

        if self._ys.size == 0:
            self.fill_3_phase_from_sequence()

        return self._ys

    @ys.setter
    def ys(self, val: AdmittanceMatrix):
        if isinstance(val, AdmittanceMatrix):
            self._ys = val
        else:
            raise ValueError(f'{val} is not a AdmittanceMatrix')

    @property
    def ysh(self) -> AdmittanceMatrix:
        if self._ysh.size == 0:
            self.fill_3_phase_from_sequence()

        return self._ysh

    @ysh.setter
    def ysh(self, val: AdmittanceMatrix):
        if isinstance(val, AdmittanceMatrix):
            self._ysh = val
        else:
            raise ValueError(f'{val} is not a AdmittanceMatrix')

    def change_base(self, Sbase_old: float, Sbase_new: float):
        """
        Change the impedance base
        :param Sbase_old: old base (MVA)
        :param Sbase_new: new base (MVA)
        """
        b = Sbase_new / Sbase_old

        self.R *= b
        self.X *= b
        self.B *= b

    def get_weight(self) -> float:
        """
        Get a weight of this line for graph purposes
        the weight is the impedance module (sqrt(r^2 + x^2))
        :return: weight value
        """
        return np.sqrt(self.R * self.R + self.X * self.X)

    def apply_template(self,
                       obj: Union[OverheadLineType, UndergroundLineType, SequenceLineType],
                       Sbase: float, freq: float,
                       logger=Logger()):
        """
        Apply a line template to this object
        :param obj: OverheadLineType, UndergroundLineType, SequenceLineType
        :param Sbase: Nominal power in MVA
        :param freq: Frequency in Hz
        :param logger: Logger
        """

        if isinstance(obj, OverheadLineType):
            if not obj.is_computed():
                obj.compute()
                if not obj.is_computed():
                    logger.add_error("No admittance data", device=obj.name)
                    return
            else:
                pass

            template_vn = obj.Vnom
            vn = self.get_max_bus_nominal_voltage()

            if not accept_line_connection(template_vn, vn, 0.1):
                raise Exception('Template voltage differs too much from the line nominal voltage')

            if obj.has_sequence_data():
                (self.R, self.X, self.B,
                 self.R0, self.X0, self.B0,
                 self.rate) = obj.get_values(Sbase=Sbase,
                                             length=self.length,
                                             circuit_index=self.circuit_idx,
                                             Vnom=vn)
            else:
                logger.add_info("No sequence data", device=obj.name)

            self.ys = obj.get_ys(circuit_idx=self.circuit_idx, Sbase=Sbase, length=self.length, Vnom=vn)
            self.ysh = obj.get_ysh(circuit_idx=self.circuit_idx, Sbase=Sbase, length=self.length, Vnom=vn)

            self.template = obj

        elif isinstance(obj, UndergroundLineType):
            (self.R, self.X, self.B,
             self.R0, self.X0, self.B0,
             self.rate) = obj.get_values(Sbase=Sbase, length=self.length)

            self.template = obj

        elif isinstance(obj, SequenceLineType):
            (self.R, self.X, self.B,
             self.R0, self.X0, self.B0,
             self.rate) = obj.get_values(Sbase=Sbase,
                                         freq=freq,
                                         length=self.length,
                                         line_Vnom=self.get_max_bus_nominal_voltage())

            self.ys = obj.get_ys_abc()
            self.ysh = obj.get_ysh_abc()

            self.template = obj

        else:
            logger.add_error('Template not recognised', self.name)

    def get_line_type(self) -> SequenceLineType:
        """
        Get the equivalent sequence line type of this line
        :return: SequenceLineType
        """
        if self.length == 0.0:
            raise Exception("Length must be greater than 0")

        return SequenceLineType(name=f"{self.name}_type",
                                Imax=1, Vnom=self.get_max_bus_nominal_voltage(),
                                R=self.R / self.length,
                                X=self.X / self.length,
                                B=self.B / self.length,
                                R0=self.R0 / self.length,
                                X0=self.X0 / self.length,
                                B0=self.B0 / self.length)

    def get_save_data(self) -> List[str]:
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

    def fix_inconsistencies(self, logger: Logger) -> bool:
        """
        Fix the inconsistencies
        :param logger:
        :return: any error
        """
        errors = False

        if self.R < 0.0:
            logger.add_warning("Corrected transformer R<0", self.name, self.R, -self.R)
            self.R = -self.R
            errors = True

        return errors

    def get_equivalent_transformer(self, index: pd.DatetimeIndex | None = None) -> Transformer2W:
        """
        Convert this line into a transformer
        This is necessary if the buses' voltage differ too much
        :return: Transformer2W
        """
        V1 = min(self.bus_to.Vnom, self.bus_from.Vnom)
        V2 = max(self.bus_to.Vnom, self.bus_from.Vnom)
        elm = Transformer2W(bus_from=self.bus_from,
                            bus_to=self.bus_to,
                            idtag=self.idtag,
                            name=self.name,
                            code=self.code,
                            active=self.active,
                            rate=self.rate,
                            HV=V2,
                            LV=V1,
                            r=self.R,
                            x=self.X,
                            b=self.B)

        if index is not None:
            elm.ensure_profiles_exist(index=index)
            elm.active_prof = self.active_prof
            elm.rate_prof = self.rate_prof
            elm.contingency_factor_prof = self.contingency_factor_prof
            elm.protection_rating_factor_prof = self.protection_rating_factor_prof
            elm.temp_oper_prof = self.temp_oper_prof
            elm.Cost_prof = self.Cost_prof

        return elm

    def fill_design_properties(self, r_ohm: float, x_ohm: float, c_nf: float, length: float,
                               Imax: float, freq: float, Sbase: float, apply_to_profile: bool = True, ) -> "Line":
        """
        Fill R, X, B from not-in-per-unit parameters
        :param r_ohm: Resistance per km in OHM/km
        :param x_ohm: Reactance per km in OHM/km
        :param c_nf: Capacitance per km in nF/km
        :param length: length in kn
        :param Imax: Maximum current in kA
        :param freq: System frequency in Hz
        :param Sbase: Base power in MVA (take always 100 MVA)
        :param apply_to_profile: modify the ratings profile if checked
        :return self pointer
        """
        self.R, self.X, self.B, new_rate = get_line_impedances_with_c(r_ohm=r_ohm,
                                                                      x_ohm=x_ohm,
                                                                      c_nf=c_nf,
                                                                      length=length,
                                                                      Imax=Imax,
                                                                      freq=freq,
                                                                      Sbase=Sbase,
                                                                      Vnom=self.get_max_bus_nominal_voltage())

        old_rate = float(self.rate)

        self.rate = new_rate
        self._length = length

        if apply_to_profile:
            if old_rate != 0.0:
                prof_old = self.rate_prof.toarray()
                self.rate_prof.set(prof_old * new_rate / old_rate)
            else:
                self.rate_prof.fill(new_rate)

        return self

    def fill_3_phase_from_sequence(self):
        """
        Fill the 3x3 from the sequence values
        """
        if self.R0 > 1e-10 and self.X0 > 1e-10:
            obj = SequenceLineType(R=self.R, R0=self.R0, X=self.X, X0=self.X0)
        else:
            obj = SequenceLineType(R=self.R, R0=2.0 * self.R, X=self.X, X0=2.0 * self.X)
        self.ys = obj.get_ys_abc()
        self.ysh = obj.get_ysh_abc()

    def initialize_rms(self):
        if self.rms_model.empty():
            Qf = Var("Qf")
            Qt = Var("Qt")
            Pf = Var("Pf")
            Pt = Var("Pt")

            ys = 1.0 / complex(self.R, self.X)
            g = Const(ys.real)
            b = Const(ys.imag)
            bsh = Const(self.B)

            Vmf = self.bus_from.rms_model.model.E(DynamicVarType.Vm)
            Vaf = self.bus_from.rms_model.model.E(DynamicVarType.Va)
            Vmt = self.bus_to.rms_model.model.E(DynamicVarType.Vm)
            Vat = self.bus_to.rms_model.model.E(DynamicVarType.Va)

            self.rms_model.model = Block(
                algebraic_eqs=[
                    Pf - ((Vmf ** 2 * g) - g * Vmf * Vmt * cos(Vaf - Vat) + b * Vmf * Vmt * cos(Vaf - Vat + np.pi / 2)),
                    Qf - (Vmf ** 2 * (-bsh / 2 - b) - g * Vmf * Vmt * sin(Vaf - Vat) + b * Vmf * Vmt * sin(Vaf - Vat + np.pi / 2)),
                    Pt - ((Vmt ** 2 * g) - g * Vmt * Vmf * cos(Vat - Vaf) + b * Vmt * Vmf * cos(Vat - Vaf + np.pi / 2)),
                    Qt - (Vmt ** 2 * (-bsh / 2 - b) - g * Vmt * Vmf * sin(Vat - Vaf) + b * Vmt * Vmf * sin(Vat - Vaf + np.pi / 2)),
                ],
                algebraic_vars=[Pf, Pt, Qf, Qt],
                init_eqs={},
                init_vars=[],
                parameters=[],
                external_mapping={
                    DynamicVarType.Pf: Pf,
                    DynamicVarType.Pt: Pt,
                    DynamicVarType.Qf: Qf,
                    DynamicVarType.Qt: Qt,
                }
            )
