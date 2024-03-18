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

from typing import Union
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.enumerations import (TransformerControlType, WindingsConnection, BuildStatus,
                                        TapAngleControl, TapModuleControl)
from GridCalEngine.Devices.Branches.transformer_type import TransformerType
from GridCalEngine.Devices.Branches.transformer import Transformer2W
from GridCalEngine.Devices.Parents.editable_device import DeviceType


class Winding(Transformer2W):

    def __init__(self,
                 bus_from: Bus = None,
                 bus_to: Bus = None,
                 name='Winding',
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
                 build_status: BuildStatus = BuildStatus.Commissioned):
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
        Transformer2W.__init__(self,
                               bus_from=bus_from,
                               bus_to=bus_to,
                               name=name,
                               idtag=idtag,
                               code=code,
                               cn_from=cn_from,
                               cn_to=cn_to,
                               HV=HV,
                               LV=LV,
                               nominal_power=nominal_power,
                               copper_losses=copper_losses,
                               iron_losses=iron_losses,
                               no_load_current=no_load_current,
                               short_circuit_voltage=short_circuit_voltage,
                               r=r,
                               x=x,
                               g=g,
                               b=b,
                               rate=rate,
                               tap_module=tap_module,
                               tap_module_max=tap_module_max,
                               tap_module_min=tap_module_min,
                               tap_phase=tap_phase,
                               tap_phase_max=tap_phase_max,
                               tap_phase_min=tap_phase_min,
                               active=active,
                               tolerance=tolerance,
                               cost=cost,
                               mttf=mttf,
                               mttr=mttr,
                               vset=vset,
                               Pset=Pset,
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
                               conn=conn,
                               capex=capex,
                               opex=opex,
                               build_status=build_status)

        self.device_type = DeviceType.WindingDevice
