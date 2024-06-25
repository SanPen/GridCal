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
from typing import Tuple, Union

from GridCalEngine.basic_structures import Logger
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.enumerations import (TransformerControlType, WindingsConnection, BuildStatus,
                                        TapAngleControl, TapModuleControl, TapChangerTypes)
from GridCalEngine.Devices.Parents.controllable_branch_parent import ControllableBranchParent
from GridCalEngine.Devices.Branches.transformer_type import TransformerType, reverse_transformer_short_circuit_study
from GridCalEngine.Devices.Parents.editable_device import DeviceType


class Transformer2W(ControllableBranchParent):

    def __init__(self,
                 bus_from: Bus = None,
                 bus_to: Bus = None,
                 name='Branch',
                 idtag: Union[None, str] = None,
                 code: str = '',
                 cn_from: ConnectivityNode = None,
                 cn_to: ConnectivityNode = None,
                 HV: Union[None, float] = None,
                 LV: Union[None, float] = None,
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
                 tolerance: float = 0.0,
                 cost: float = 100.0,
                 mttf: float = 0.0,
                 mttr: float = 0.0,
                 vset: float = 1.0,
                 Pset: float = 0.0,
                 temp_base: float = 20.0,
                 temp_oper: float = 20.0,
                 alpha: float = 0.00330,
                 control_mode: TransformerControlType = TransformerControlType.fixed,
                 tap_module_control_mode: TapModuleControl = TapModuleControl.fixed,
                 tap_angle_control_mode: TapAngleControl = TapAngleControl.fixed,
                 template: TransformerType = None,
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
        :param control_mode: Control model
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
                                          Cost=cost,
                                          mttf=mttf,
                                          mttr=mttr,
                                          vset=vset,
                                          Pset=Pset,
                                          regulation_branch=None,
                                          regulation_bus=None,
                                          regulation_cn=None,
                                          temp_base=temp_base,
                                          temp_oper=temp_oper,
                                          alpha=alpha,
                                          control_mode=control_mode,
                                          tap_module_control_mode=tap_module_control_mode,
                                          tap_angle_control_mode=tap_angle_control_mode,
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
                                          tc_dV=tc_dV,
                                          tc_asymmetry_angle=tc_asymmetry_angle,
                                          tc_type=tc_type)

        # set the high and low voltage values
        self.HV = HV
        self.LV = LV

        if self.bus_from and self.bus_to:
            self.set_hv_and_lv(HV, LV)

        self.Sn = nominal_power

        self.Pcu = copper_losses

        self.Pfe = iron_losses

        self.I0 = no_load_current

        self.Vsc = short_circuit_voltage

        # connection type
        self.conn = conn

        # type template
        self.template = template

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

    # def copy(self, bus_dict=None):
    #     """
    #     Returns a copy of the branch
    #     @return: A new  with the same content as this
    #     """
    #
    #     if bus_dict is None:
    #         f = self.bus_from
    #         t = self.bus_to
    #     else:
    #         f = bus_dict[self.bus_from]
    #         t = bus_dict[self.bus_to]
    #
    #     # z_series = complex(self.R, self.X)
    #     # y_shunt = complex(self.G, self.B)
    #     b = Transformer2W(bus_from=f,
    #                       bus_to=t,
    #                       name=self.name,
    #                       r=self.R,
    #                       x=self.X,
    #                       g=self.G,
    #                       b=self.B,
    #                       rate=self.rate,
    #                       tap_module=self.tap_module,
    #                       tap_phase=self.tap_phase,
    #                       active=self.active,
    #                       mttf=self.mttf,
    #                       mttr=self.mttr,
    #                       vset=self.vset,
    #                       temp_base=self.temp_base,
    #                       temp_oper=self.temp_oper,
    #                       alpha=self.alpha,
    #                       template=self.template,
    #                       opex=self.opex,
    #                       capex=self.capex)
    #
    #     b.regulation_bus = self.regulation_bus
    #     b.regulation_cn = self.regulation_cn
    #     b.active_prof = self.active_prof
    #     b.rate_prof = self.rate_prof
    #     b.Cost_prof = self.Cost_prof
    #
    #     return b

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

            self.R = np.round(z_series.real, 6)
            self.X = np.round(z_series.imag, 6)
            self.G = np.round(y_shunt.real, 6)
            self.B = np.round(y_shunt.imag, 6)

            self.rate = obj.Sn
            self.rate_prof.fill(self.rate)

            self.Sn = obj.Sn
            self.Pcu = obj.Pcu
            self.Pfe = obj.Pfe
            self.I0 = obj.I0
            self.Vsc = obj.Vsc

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
        for property_name, properties in self.registered_properties.items():
            obj = getattr(self, property_name)

            if properties.tpe == DeviceType.BusDevice:
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
        (i.e. Transformer HV=41.9, bus HV=45 41.9/45 = 0.93 -> 0.9 <= 0.93 <= 1.1, so its ok
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

    def fill_design_properties(self, Pcu, Pfe, I0, Vsc, Sbase):
        """
        Fill R, X, G, B from the short circuit study values
        :param Pcu: copper_losses (kW)
        :param Pfe: Iron losses (kW)
        :param I0: No load current in %
        :param Vsc: Short circuit voltage (%)
        :param Sbase: Base power in MVA (take always 100 MVA)
        """
        tpe = TransformerType(hv_nominal_voltage=self.HV,
                              lv_nominal_voltage=self.LV,
                              nominal_power=self.rate,
                              copper_losses=Pcu,
                              iron_losses=Pfe,
                              no_load_current=I0,
                              short_circuit_voltage=Vsc,
                              gr_hv1=0.5,
                              gx_hv1=0.5,
                              name='type from ' + self.name)

        z_series, y_shunt = tpe.get_impedances(VH=self.HV, VL=self.LV, Sbase=Sbase)

        self.R = np.round(z_series.real, 6)
        self.X = np.round(z_series.imag, 6)
        self.G = np.round(y_shunt.real, 6)
        self.B = np.round(y_shunt.imag, 6)

    def get_vcc(self) -> float:
        """
        Get the short circuit voltage in %
        This is the value from the short circuit study
        :return: value in %
        """
        return 100.0 * np.sqrt(self.R * self.R + self.X * self.X)

    def get_transformer_type(self, Sbase: float = 100.0) -> TransformerType:
        """

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
