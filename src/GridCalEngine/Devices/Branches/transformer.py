# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import numpy as np
from typing import Tuple

from GridCalEngine.basic_structures import Logger
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.Devices.Associations.association import Associations
from GridCalEngine.enumerations import (WindingsConnection, BuildStatus, TapPhaseControl,
                                        TapModuleControl, SubObjectType, TapChangerTypes)
from GridCalEngine.Devices.Parents.controllable_branch_parent import ControllableBranchParent
from GridCalEngine.Devices.Branches.transformer_type import TransformerType, reverse_transformer_short_circuit_study
from GridCalEngine.Devices.Parents.editable_device import DeviceType


class Transformer2W(ControllableBranchParent):

    def __init__(self,
                 bus_from: Bus | None = None,
                 bus_to: Bus | None = None,
                 name='Branch',
                 idtag: str | None = None,
                 code: str = '',
                 cn_from: ConnectivityNode | None = None,
                 cn_to: ConnectivityNode | None = None,
                 HV: float | None = None,
                 LV: float | None = None,
                 nominal_power: float = 0.001,
                 copper_losses: float = 0.0,
                 iron_losses: float = 0.0,
                 no_load_current: float = 0.0,
                 short_circuit_voltage: float = 0.0,
                 r: float = 1e-20,
                 x: float = 1e-20,
                 g: float = 1e-20,
                 b: float = 1e-20,
                 rate: float = 1.0,
                 tap_module: float = 1.0,
                 tap_module_max: float = 1.2,
                 tap_module_min: float = 0.5,
                 tap_phase: float = 0.0,
                 tap_phase_max: float = 6.28,
                 tap_phase_min: float = -6.28,
                 active: bool = True,
                 reducible: bool = False,
                 tolerance: float = 0.0,
                 cost: float = 100.0,
                 mttf: float = 0.0,
                 mttr: float = 0.0,
                 vset: float = 1.0,
                 Pset: float = 0.0,
                 Qset: float = 0.0,
                 temp_base: float = 20.0,
                 temp_oper: float = 20.0,
                 alpha: float = 0.00330,
                 tap_module_control_mode: TapModuleControl = TapModuleControl.fixed,
                 tap_phase_control_mode: TapPhaseControl = TapPhaseControl.fixed,
                 template: TransformerType | None = None,
                 contingency_factor: float = 1.0,
                 protection_rating_factor: float = 1.4,
                 contingency_enabled: bool = True,
                 monitor_loading: bool = True,
                 r0: float = 1e-20,
                 x0: float = 1e-20,
                 g0: float = 1e-20,
                 b0: float = 1e-20,
                 r2: float = 1e-20,
                 x2: float = 1e-20,
                 g2: float = 1e-20,
                 b2: float = 1e-20,
                 conn: WindingsConnection = WindingsConnection.GG,
                 capex: float = 0.0,
                 opex: float = 0.0,
                 build_status: BuildStatus = BuildStatus.Commissioned,
                 tc_total_positions: int = 5,
                 tc_neutral_position: int = 2,
                 tc_normal_position: int = 2,
                 tc_dV: float = 0.01,
                 tc_asymmetry_angle=90,
                 tc_type: TapChangerTypes = TapChangerTypes.NoRegulation):
        """
        Transformer constructor
        :param name: Name of the branch
        :param idtag: UUID code
        :param code: secondary id
        :param bus_from: "From" :ref:`bus<Bus>` object
        :param bus_to: "To" :ref:`bus<Bus>` object
        :param HV: Higher voltage value in kV
        :param LV: Lower voltage value in kV
        :param nominal_power: Nominal power of the machine in MVA
        :param copper_losses: Copper losses in kW
        :param iron_losses: Iron losses in kW
        :param no_load_current: No load current in %
        :param short_circuit_voltage: Short circuit voltage in %
        :param r: resistance in per unit
        :param x: reactance in per unit
        :param g: shunt conductance in per unit
        :param b: shunt susceptance in per unit
        :param rate: rate in MVA
        :param tap_module: tap module in p.u.
        :param tap_module_max:
        :param tap_module_min:
        :param tap_phase: phase shift angle (rad)
        :param tap_phase_max:
        :param tap_phase_min:
        :param active: Is the branch active?
        :param tolerance: Tolerance specified for the branch impedance in %
        :param cost: Cost of overload (e/MW)
        :param mttf: Mean time to failure in hours
        :param mttr: Mean time to recovery in hours
        :param vset: Voltage set-point of the voltage controlled bus in per unit
        :param Pset: Power set point
        :param temp_base: Base temperature at which `r` is measured in °C
        :param temp_oper: Operating temperature in °C
        :param alpha: Thermal constant of the material in °C
        :param template: Branch template
        :param contingency_factor: Rating factor in case of contingency
        :param contingency_enabled: enabled for contingencies (Legacy)
        :param monitor_loading: monitor the loading (used in OPF)
        :param r0: zero-sequence resistence (p.u.)
        :param x0: zero-sequence reactance (p.u.)
        :param g0: zero-sequence conductance (p.u.)
        :param b0: zero-sequence susceptance (p.u.)
        :param r2: negative-sequence resistence (p.u.)
        :param x2: negative-sequence reactance (p.u.)
        :param g2: negative-sequence conductance (p.u.)
        :param b2: negative-sequence susceptance (p.u.)
        :param conn: transformer connection type
        :param capex: Cost of investment (e/MW)
        :param opex: Cost of operation (e/MWh)
        :param build_status: build status (now time)
        """

        ControllableBranchParent.__init__(self,
                                          name=name,
                                          idtag=idtag,
                                          code=code,
                                          bus_from=bus_from,
                                          bus_to=bus_to,
                                          cn_from=cn_from,
                                          cn_to=cn_to,
                                          active=active,
                                          reducible=reducible,
                                          rate=rate,
                                          r=r,
                                          x=x,
                                          g=g,
                                          b=b,
                                          tap_module=tap_module,
                                          tap_module_max=tap_module_max,
                                          tap_module_min=tap_module_min,
                                          tap_phase=tap_phase,
                                          tap_phase_max=tap_phase_max,
                                          tap_phase_min=tap_phase_min,
                                          tolerance=tolerance,
                                          cost=cost,
                                          mttf=mttf,
                                          mttr=mttr,
                                          vset=vset,
                                          Pset=Pset,
                                          Qset=Qset,
                                          regulation_branch=None,
                                          regulation_bus=None,
                                          regulation_cn=None,
                                          temp_base=temp_base,
                                          temp_oper=temp_oper,
                                          alpha=alpha,
                                          # control_mode=control_mode,
                                          tap_module_control_mode=tap_module_control_mode,
                                          tap_phase_control_mode=tap_phase_control_mode,
                                          contingency_factor=contingency_factor,
                                          protection_rating_factor=protection_rating_factor,
                                          contingency_enabled=contingency_enabled,
                                          monitor_loading=monitor_loading,
                                          r0=r0,
                                          x0=x0,
                                          g0=g0,
                                          b0=b0,
                                          r2=r2,
                                          x2=x2,
                                          g2=g2,
                                          b2=b2,
                                          capex=capex,
                                          opex=opex,
                                          build_status=build_status,
                                          device_type=DeviceType.Transformer2WDevice,
                                          tc_total_positions=tc_total_positions,
                                          tc_neutral_position=tc_neutral_position,
                                          tc_normal_position=tc_normal_position,
                                          tc_dV=tc_dV,
                                          tc_asymmetry_angle=tc_asymmetry_angle,
                                          tc_type=tc_type)

        # set the high and low voltage values
        self.HV: None | float = None if HV is None else float(HV)
        self.LV: None | float = None if LV is None else float(LV)

        if self.bus_from and self.bus_to:
            self.set_hv_and_lv(HV, LV)

        self.Sn = float(nominal_power)

        self.Pcu = float(copper_losses)

        self.Pfe = float(iron_losses)

        self.I0 = float(no_load_current)

        self.Vsc = float(short_circuit_voltage)

        # connection type
        self.conn: WindingsConnection = conn

        # type template
        self.template: TransformerType = template

        # association with transformer templates
        self.possible_transformer_types: Associations = Associations(device_type=DeviceType.TransformerTypeDevice)

        # register
        self.register(key='HV', units='kV', tpe=float, definition='High voltage rating')
        self.register(key='LV', units='kV', tpe=float, definition='Low voltage rating')
        self.register(key='Sn', units='MVA', tpe=float, definition='Nominal power')
        self.register(key='Pcu', units='kW', tpe=float, definition='Copper losses (optional)')
        self.register(key='Pfe', units='kW', tpe=float, definition='Iron losses (optional)')
        self.register(key='I0', units='%', tpe=float, definition='No-load current (optional)')
        self.register(key='Vsc', units='%', tpe=float, definition='Short-circuit voltage (optional)')

        self.register(key='conn', units='', tpe=WindingsConnection,
                      definition='Windings connection (from, to):G: grounded starS: ungrounded starD: delta')

        self.register(key='template', units='', tpe=DeviceType.TransformerTypeDevice, definition='', editable=False)

        self.register(key='possible_transformer_types', units='', tpe=SubObjectType.Associations,
                      definition='Possible transformer types (>1 to denote association), - to denote no association',
                      display=False)

    def set_hv_and_lv(self, HV: float, LV: float):
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

    def get_from_to_nominal_voltages(self) -> Tuple[float, float]:
        """

        :return:
        """
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

    def get_virtual_taps(self) -> Tuple[float, float]:
        """
        Get the branch virtual taps

        The virtual taps generate when a transformer nominal winding voltage differs
        from the bus nominal voltage.
        :return: Virtual tap at the *from* side, **tap_t** (float, 1.0): Virtual tap at the *to* side
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
        :param obj: TransformerType or Tower object
        :param Sbase: circuit base power in MVA
        :param logger: Log list
        """

        if isinstance(obj, TransformerType):

            VH, VL = self.get_sorted_buses_voltages()

            # get the transformer impedance in the base of the transformer
            z_series, y_shunt = obj.get_impedances(VH=VH, VL=VL, Sbase=Sbase)

            self.R = z_series.real
            self.X = z_series.imag
            self.G = y_shunt.real
            self.B = y_shunt.imag

            self.rate = obj.Sn
            self.rate_prof.fill(self.rate)

            self.Sn = obj.Sn
            self.Pcu = obj.Pcu
            self.Pfe = obj.Pfe
            self.I0 = obj.I0
            self.Vsc = obj.Vsc

            self.HV = obj.HV
            self.LV = obj.LV

            self.tap_changer = obj.get_tap_changer()

            if self.template is not None:
                if obj != self.template:
                    self.template = obj
                else:
                    logger.add_error('Template not recognised', self.name)
            else:
                self.template = obj

    def delete_virtual_taps(self):
        """
        Set the HV and LV parameters such that any virtual tap is null
        """
        self.HV = max(self.bus_from.Vnom, self.bus_to.Vnom)
        self.LV = min(self.bus_from.Vnom, self.bus_to.Vnom)

    def fix_inconsistencies(self, logger: Logger, maximum_difference=0.1) -> bool:
        """
        Fix the inconsistencies
        :param logger:
        :param maximum_difference: proportion to be under or above
        (i.e. Transformer HV=41.9, bus HV=45 41.9/45 = 0.93 -> 0.9 <= 0.93 <= 1.1, so it's ok
        :return: were there any errors?
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

        if self.R < 0.0:
            logger.add_warning("Corrected transformer R<0", self.name, self.R, -self.R)
            self.R = -self.R
            errors = True

        return errors

    def fill_design_properties(self, Pcu: float, Pfe: float, I0: float, Vsc: float, Sbase: float,
                               round_vals: bool=False) -> "Transformer2W":
        """
        Fill R, X, G, B from the short circuit study values
        :param Pcu: copper_losses (kW)
        :param Pfe: Iron losses (kW)
        :param I0: No load current in %
        :param Vsc: Short circuit voltage (%)
        :param Sbase: Base power in MVA (take always 100 MVA)
        :param round_vals: round the values?
        :return: self pointer
        """

        if self.Sn > 0:
            nominal_power = self.Sn
        else:
            if self.rate > 0:
                nominal_power = self.rate
                print(f"{self.name}: Using rate to set compute the impedances...please fill a valid nominal power")
            else:
                nominal_power = 1.0
                print(f"{self.name}: Using 1 to set compute the impedances...please fill a valid nominal power")

        tpe = TransformerType(hv_nominal_voltage=self.HV,
                              lv_nominal_voltage=self.LV,
                              nominal_power=nominal_power,
                              copper_losses=Pcu,
                              iron_losses=Pfe,
                              no_load_current=I0,
                              short_circuit_voltage=Vsc,
                              gr_hv1=0.5,
                              gx_hv1=0.5,
                              name='type from ' + self.name)

        self.Pcu = Pcu
        self.Pfe = Pfe
        self.I0 = I0
        self.Vsc = Vsc

        z_series, y_shunt = tpe.get_impedances(VH=self.HV, VL=self.LV, Sbase=Sbase)

        if round_vals:
            self.R = np.round(z_series.real, 6)
            self.X = np.round(z_series.imag, 6)
            self.G = np.round(y_shunt.real, 6)
            self.B = np.round(y_shunt.imag, 6)
        else:
            self.R = z_series.real
            self.X = z_series.imag
            self.G = y_shunt.real
            self.B = y_shunt.imag

        return self

    def get_vcc(self) -> float:
        """
        Get the short circuit voltage in %
        This is the value from the short circuit study
        :return: value in %
        """
        return 100.0 * np.sqrt(self.R * self.R + self.X * self.X)

    def get_transformer_type(self, Sbase: float = 100.0) -> TransformerType:
        """
        Get the equivalent transformer type of this transformer
        :return: SequenceLineType
        :param Sbase:
        :return:
        """
        Pfe, Pcu, Vsc, I0, Sn = reverse_transformer_short_circuit_study(R=self.R,
                                                                        X=self.X,
                                                                        G=self.G,
                                                                        B=self.B,
                                                                        rate=self.rate,
                                                                        Sbase=Sbase)

        tpe = TransformerType(hv_nominal_voltage=self.HV,
                              lv_nominal_voltage=self.LV,
                              nominal_power=Sn,
                              copper_losses=Pcu,
                              iron_losses=Pfe,
                              no_load_current=I0,
                              short_circuit_voltage=Vsc,
                              gr_hv1=0.5,
                              gx_hv1=0.5,
                              name='type from ' + self.name)

        return tpe
