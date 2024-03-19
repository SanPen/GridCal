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
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.enumerations import (TransformerControlType, BuildStatus, TapModuleControl, TapAngleControl,
                                        SubObjectType)
from GridCalEngine.Devices.Parents.branch_parent import BranchParent
from GridCalEngine.Devices.Branches.tap_changer import TapChanger
from GridCalEngine.Devices.Parents.editable_device import DeviceType
from GridCalEngine.Devices.profile import Profile


class ControllableBranchParent(BranchParent):

    def __init__(self,
                 bus_from: Bus,
                 bus_to: Bus,
                 name: str,
                 idtag: Union[None, str],
                 code: str,
                 cn_from: ConnectivityNode,
                 cn_to: ConnectivityNode,
                 active: bool,
                 rate: float,
                 r: float,
                 x: float,
                 g: float,
                 b: float,
                 tap_module: float,
                 tap_module_max: float,
                 tap_module_min: float,
                 tap_phase: float,
                 tap_phase_max: float,
                 tap_phase_min: float,
                 tolerance: float,
                 vset: float,
                 Pset: float,
                 regulation_branch: Union[BranchParent, None],
                 regulation_bus: Union[Bus, None],
                 regulation_cn: Union[ConnectivityNode, None],
                 temp_base: float,
                 temp_oper: float,
                 alpha: float,
                 control_mode: TransformerControlType,
                 tap_module_control_mode: TapModuleControl,
                 tap_angle_control_mode: TapAngleControl,
                 contingency_factor: float,
                 protection_rating_factor: float,
                 contingency_enabled: bool,
                 monitor_loading: bool,
                 r0: float,
                 x0: float,
                 g0: float,
                 b0: float,
                 r2: float,
                 x2: float,
                 g2: float,
                 b2: float,
                 Cost: float,
                 mttf: float,
                 mttr: float,
                 capex: float,
                 opex: float,
                 build_status: BuildStatus,
                 device_type: DeviceType):
        """
        Transformer constructor
        :param name: Name of the branch
        :param idtag: UUID code
        :param code: secondary id
        :param bus_from: "From" :ref:`bus<Bus>` object
        :param bus_to: "To" :ref:`bus<Bus>` object
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
        :param Cost: Cost of overload (e/MW)
        :param mttf: Mean time to failure in hours
        :param mttr: Mean time to recovery in hours
        :param vset: Voltage set-point of the voltage controlled bus in per unit
        :param Pset: Power set point
        :param regulation_branch: Branch object where the flow regulation is applied
        :param regulation_bus: Bus object where the regulation is applied
        :param regulation_cn: ConnectivityNode where the regulation is applied
        :param temp_base: Base temperature at which `r` is measured in °C
        :param temp_oper: Operating temperature in °C
        :param alpha: Thermal constant of the material in °C
        :param control_mode: Control model
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
                              Cost=Cost,
                              device_type=device_type)

        # branch impedance tolerance
        self.tolerance = tolerance

        # total impedance and admittance in p.u.
        self.R = r
        self.X = x
        self.G = g
        self.B = b

        self.R0 = r0
        self.X0 = x0
        self.G0 = g0
        self.B0 = b0

        self.R2 = r2
        self.X2 = x2
        self.G2 = g2
        self.B2 = b2

        # Conductor base and operating temperatures in ºC
        self.temp_base = temp_base
        self.temp_oper = temp_oper
        self._temp_oper_prof = Profile(default_value=temp_oper)

        # Conductor thermal constant (1/ºC)
        self.alpha = alpha

        # tap changer object
        self._tap_changer = TapChanger()

        # Tap module
        if tap_module != 0:
            self.tap_module = tap_module
            self._tap_changer.set_tap_module(self.tap_module)
        else:
            self.tap_module = self._tap_changer.get_tap_module()

        self._tap_module_prof = Profile(default_value=tap_module)

        # Tap angle
        self.tap_phase = tap_phase
        self._tap_phase_prof = Profile(default_value=tap_phase)

        self.tap_module_max = tap_module_max
        self.tap_module_min = tap_module_min
        self.tap_phase_max = tap_phase_max
        self.tap_phase_min = tap_phase_min

        self.vset = vset
        self.Pset = Pset

        self.control_mode: TransformerControlType = control_mode
        self.tap_module_control_mode: TapModuleControl = tap_module_control_mode
        self.tap_angle_control_mode: TapAngleControl = tap_angle_control_mode
        self.regulation_branch: BranchParent = regulation_branch
        self.regulation_bus: Bus = regulation_bus
        self.regulation_cn: ConnectivityNode = regulation_cn

        self.register(key='R', units='p.u.', tpe=float, definition='Total positive sequence resistance.')
        self.register(key='X', units='p.u.', tpe=float, definition='Total positive sequence reactance.')
        self.register(key='G', units='p.u.', tpe=float, definition='Total positive sequence shunt conductance.')
        self.register(key='B', units='p.u.', tpe=float, definition='Total positive sequence shunt susceptance.')
        self.register(key='R0', units='p.u.', tpe=float, definition='Total zero sequence resistance.')
        self.register(key='X0', units='p.u.', tpe=float, definition='Total zero sequence reactance.')
        self.register(key='G0', units='p.u.', tpe=float, definition='Total zero sequence shunt conductance.')
        self.register(key='B0', units='p.u.', tpe=float, definition='Total zero sequence shunt susceptance.')
        self.register(key='R2', units='p.u.', tpe=float, definition='Total negative sequence resistance.')
        self.register(key='X2', units='p.u.', tpe=float, definition='Total negative sequence reactance.')
        self.register(key='G2', units='p.u.', tpe=float, definition='Total negative sequence shunt conductance.')
        self.register(key='B2', units='p.u.', tpe=float, definition='Total negative sequence shunt susceptance.')

        self.register(key='tolerance', units='%', tpe=float,
                      definition='Tolerance expected for the impedance values% '
                                 'is expected for transformers0% for lines.')

        self.register(key='tap_changer', units='', tpe=SubObjectType.TapChanger, definition='Tap changer object',
                      editable=False)

        self.register(key='tap_module', units='', tpe=float, definition='Tap changer module, it a value close to 1.0',
                      profile_name='tap_module_prof', old_names=['tap'])
        self.register(key='tap_module_max', units='', tpe=float, definition='Tap changer module max value')
        self.register(key='tap_module_min', units='', tpe=float, definition='Tap changer module min value')

        self.register(key='tap_phase', units='rad', tpe=float, definition='Angle shift of the tap changer.',
                      profile_name='tap_phase_prof', old_names=['angle'])
        self.register(key='tap_phase_max', units='rad', tpe=float, definition='Max angle.', old_names=['angle_max'])
        self.register(key='tap_phase_min', units='rad', tpe=float, definition='Min angle.', old_names=['angle_min'])

        self.register(key='control_mode', units='', tpe=TransformerControlType,
                      definition='Control type of the transformer')

        self.register(key='tap_module_control_mode', units='', tpe=TapModuleControl,
                      definition='Control available with the tap module')

        self.register(key='tap_angle_control_mode', units='', tpe=TapAngleControl,
                      definition='Control available with the tap angle')

        self.register(key='vset', units='p.u.', tpe=float,
                      definition='Objective voltage at the "to" side of the bus when regulating the tap.')

        self.register(key='Pset', units='p.u.', tpe=float,
                      definition='Objective power at the "from" side of when regulating the angle.')

        self.register(key='regulation_branch', units='', tpe=DeviceType.BranchDevice,
                      definition='Branch where the controls are applied.')

        self.register(key='regulation_bus', units='', tpe=DeviceType.BusDevice,
                      definition='Bus where the regulation is applied.')

        self.register(key='regulation_cn', units='', tpe=DeviceType.ConnectivityNodeDevice,
                      definition='Connectivity node where the regulation is applied.')

        self.register(key='temp_base', units='ºC', tpe=float, definition='Base temperature at which R was measured.')
        self.register(key='temp_oper', units='ºC', tpe=float, definition='Operation temperature to modify R.',
                      profile_name='temp_oper_prof')
        self.register(key='alpha', units='1/ºC', tpe=float,
                      definition='Thermal coefficient to modify R,around a reference temperatureusing a linear '
                                 'approximation.For example:Copper @ 20ºC: 0.004041,Copper @ 75ºC: 0.00323,'
                                 'Annealed copper @ 20ºC: 0.00393,Aluminum @ 20ºC: 0.004308,Aluminum @ 75ºC: 0.00330')

    @property
    def tap_module_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._tap_module_prof

    @tap_module_prof.setter
    def tap_module_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._tap_module_prof = val
        elif isinstance(val, np.ndarray):
            self._tap_module_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a tap_module_prof')

    @property
    def tap_phase_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._tap_phase_prof

    @tap_phase_prof.setter
    def tap_phase_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._tap_phase_prof = val
        elif isinstance(val, np.ndarray):
            self._tap_phase_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a tap_phase_prof')

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
    def tap_changer(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._tap_changer

    @tap_changer.setter
    def tap_changer(self, val: TapChanger):
        if isinstance(val, TapChanger):
            self._tap_changer = val
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a tap_changer')

    @property
    def R_corrected(self):
        """
        Returns a temperature corrected resistance based on a formula provided by:
        NFPA 70-2005, National Electrical Code, Table 8, footnote #2; and
        https://en.wikipedia.org/wiki/Electrical_resistivity_and_conductivity#Linear_approximation
        (version of 2019-01-03 at 15:20 EST).
        """
        return self.R * (1 + self.alpha * (self.temp_oper - self.temp_base))

    def change_base(self, Sbase_old: float, Sbase_new: float):
        """
        Change the impedance base
        :param Sbase_old: old base (MVA)
        :param Sbase_new: new base (MVA)
        """
        b = Sbase_new / Sbase_old

        self.R *= b
        self.X *= b
        self.G *= b
        self.B *= b

    def get_weight(self):
        """
        Get a weight for the graphs
        :return: sqrt(r^2 + x^2)
        """
        return np.sqrt(self.R * self.R + self.X * self.X)

    def flip(self):
        """
        Change the terminals' positions
        """
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

            **tap_changer** (:class:`GridCalEngine.Devices.branch.TapChanger`): Tap changer object

        """
        self.tap_changer = tap_changer

        if self.tap_module != 0:
            self.tap_changer.set_tap(self.tap_module)
        else:
            self.tap_module = self.tap_changer.get_tap()
