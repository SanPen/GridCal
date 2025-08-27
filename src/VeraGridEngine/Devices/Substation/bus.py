# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


from typing import Tuple, Union
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from VeraGridEngine.enumerations import BusMode, DeviceType, BusGraphicType, SubObjectType
from VeraGridEngine.Devices.Parents.physical_device import PhysicalDevice
from VeraGridEngine.Devices.Aggregation import Area, Zone, Country
from VeraGridEngine.Devices.Substation.substation import Substation
from VeraGridEngine.Devices.Substation.busbar import BusBar
from VeraGridEngine.Devices.Substation.voltage_level import VoltageLevel
from VeraGridEngine.Devices.profile import Profile
from VeraGridEngine.Devices.Dynamic.dynamic_model_host import DynamicModelHost
from VeraGridEngine.Utils.Symbolic.block import Block, Var, DynamicVarType


class Bus(PhysicalDevice):
    __slots__ = (
        'active',
        '_active_prof',
        'Vnom',
        'Vmin',
        'Vm_cost',
        'Vmax',
        'Vm0',
        'Va0',
        '_Vmin_prof',
        '_Vmax_prof',
        'angle_min',
        'angle_max',
        'angle_cost',
        'Qmin_sum',
        'Qmax_sum',
        'r_fault',
        'x_fault',
        'country',
        'area',
        'zone',
        'substation',
        '_voltage_level',
        'type',
        'is_slack',
        'is_dc',
        'x',
        'y',
        'h',
        'w',
        'longitude',
        'latitude',
        'ph_a',
        'ph_b',
        'ph_c',
        'ph_n',
        'is_grounded',
        'graphic_type',
        '_bus_bar',
        '_rms_model',
    )

    def __init__(self, name="Bus",
                 idtag=None,
                 code='',
                 Vnom=10,
                 vmin=0.9,
                 vmax=1.1,
                 angle_min=-6.28,
                 angle_max=6.28,
                 r_fault=0.0,
                 x_fault=0.0,
                 xpos=0,
                 ypos=0,
                 height=0,
                 width=0,
                 active=True,
                 is_slack=False,
                 is_dc=False,
                 is_internal=False,
                 is_grounded=False,
                 area: Area = None,
                 zone: Zone = None,
                 substation: Substation = None,
                 voltage_level: VoltageLevel = None,
                 country: Country = None,
                 longitude=0.0,
                 latitude=0.0,
                 Vm0=1,
                 Va0=0,
                 graphic_type: BusGraphicType = BusGraphicType.BusBar,
                 bus_bar: BusBar | None = None):
        """
        The Bus object is the container of all the possible devices that can be attached to
        a bus bar or Substation. Such objects can be loads, voltage controlled generators,
        static generators, batteries, shunt elements, etc.
        :param name: Name of the bus
        :param idtag: Unique identifier, if empty or None, a random one is generated
        :param code: Compatibility id with legacy systems
        :param Vnom: Nominal voltage in kV
        :param vmin: Minimum per unit voltage (p.u.)
        :param vmax: Maximum per unit voltage (p.u.)
        :param angle_min: Minimum voltage angle (rad)
        :param angle_max: Maximum voltage angle (rad)
        :param r_fault: Resistance of the fault in per unit (SC only)
        :param x_fault: Reactance of the fault in per unit (SC only)
        :param xpos: X position in pixels (GUI only)
        :param ypos: Y position in pixels (GUI only)
        :param height: Height of the graphic object (GUI only)
        :param width: Width of the graphic object (GUI only)
        :param active: Is the bus active?
        :param is_slack: Is this bus a slack bus?
        :param is_dc: Is this bus a DC bus?
        :param is_internal: Is this bus an internal bus?
                            (i.e. the central bus on a 3W transformer, or the bus of a FluidNode)
        :param is_grounded: Is this bus grounded, i.e., at V=0? Sometimes used for DC buses connected to a VSC
        :param area: Area object
        :param zone: Zone object
        :param substation: Substation object
        :param country: Country object
        :param longitude: longitude (deg)
        :param latitude: latitude (deg)
        :param Vm0: initial solution for the voltage module (p.u.)
        :param Va0: initial solution for the voltage angle (rad)
        :param graphic_type: BusGraphicType to represent the bus in the schematic
        """

        PhysicalDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=DeviceType.BusDevice)

        self.active = bool(active)
        self._active_prof = Profile(default_value=self.active, data_type=bool)

        # Nominal voltage (kV)
        self.Vnom = float(Vnom)

        # minimum voltage limit
        self.Vmin = float(vmin)
        self.Vm_cost = 1.0

        # maximum voltage limit
        self.Vmax = float(vmax)

        self.Vm0 = float(Vm0)

        self.Va0 = float(Va0)

        self._Vmin_prof = Profile(default_value=vmin, data_type=float)
        self._Vmax_prof = Profile(default_value=vmax, data_type=float)

        self.angle_min = float(angle_min)

        self.angle_max = float(angle_max)

        self.angle_cost = 0

        # summation of lower reactive power limits connected
        self.Qmin_sum = 0

        # summation of upper reactive power limits connected
        self.Qmax_sum = 0

        # short circuit impedance
        self.r_fault = float(r_fault)
        self.x_fault = float(x_fault)

        self.country: Country = country

        self.area: Area = area

        self.zone: Zone = zone

        self.substation: Substation = substation

        self._voltage_level: VoltageLevel = voltage_level

        self._bus_bar: BusBar = bus_bar

        if is_internal:
            self.graphic_type: BusGraphicType = BusGraphicType.Internal
        else:
            self.graphic_type: BusGraphicType = graphic_type

        if voltage_level is not None:

            if voltage_level.Vnom != Vnom:
                print(f"{self.idtag} {self.name} "
                      f"The nominal voltage of the voltage level is different from bus nominal voltage!"
                      f"{voltage_level.Vnom} != {Vnom}")

            if voltage_level.substation is not None:
                if substation is None:
                    self.substation = voltage_level.substation
                else:
                    if substation != voltage_level.substation:
                        print(f"{self.idtag} {self.name} "
                              f"The substation from the voltage level is different from bus substation!")

        # Bus type
        self.type = BusMode.PQ_tpe

        # Flag to determine if the bus is a slack bus or not
        self.is_slack = bool(is_slack)

        # determined if this bus is an AC or DC bus
        self.is_dc = bool(is_dc)

        # determine if the bus is solidly grounded
        self.is_grounded = bool(is_grounded)

        # position and dimensions
        self.x = float(xpos)
        self.y = float(ypos)
        self.h = float(height)
        self.w = float(width)
        self.longitude = float(longitude)
        self.latitude = float(latitude)

        self.ph_a: bool = True
        self.ph_b: bool = True
        self.ph_c: bool = True
        self.ph_n: bool = True
        self.is_grounded: bool = True

        self._rms_model: DynamicModelHost = DynamicModelHost()

        self.register(key='active', units='', tpe=bool, definition='Is the bus active? used to disable the bus.',
                      profile_name='active_prof')
        self.register(key='is_slack', units='', tpe=bool, definition='Force the bus to be of slack type.',
                      profile_name='')
        self.register(key='is_dc', units='', tpe=bool, definition='Is this bus of DC type?.', profile_name='')
        self.register(key='graphic_type', units='', tpe=BusGraphicType, definition='Graphic to use in the schematic.')
        self.register(key='Vnom', units='kV', tpe=float, definition='Nominal line voltage of the bus.', profile_name='')
        self.register(key='Vm0', units='p.u.', tpe=float, definition='Voltage module guess.', profile_name='')
        self.register(key='Va0', units='rad.', tpe=float, definition='Voltage angle guess.', profile_name='')
        self.register(key='Vmin', units='p.u.', tpe=float, definition='Lower range of allowed voltage module.',
                      profile_name='Vmin_prof')
        self.register(key='Vmax', units='p.u.', tpe=float, definition='Higher range of allowed voltage module.',
                      profile_name='Vmax_prof')
        self.register(key='Vm_cost', units='e/unit', tpe=float, definition='Cost of over and under voltages',
                      old_names=['voltage_module_cost'])
        self.register(key='angle_min', units='rad.', tpe=float, definition='Lower range of allowed voltage angle.',
                      profile_name='')
        self.register(key='angle_max', units='rad.', tpe=float, definition='Higher range of allowed voltage angle.',
                      profile_name='')
        self.register(key='angle_cost', units='e/unit', tpe=float, definition='Cost of over and under angles',
                      old_names=['voltage_angle_cost'])
        self.register(key='r_fault', units='p.u.', tpe=float,
                      definition='Resistance of the fault.This is used for short circuit studies.', profile_name='')
        self.register(key='x_fault', units='p.u.', tpe=float,
                      definition='Reactance of the fault.This is used for short circuit studies.', profile_name='')
        self.register(key='x', units='px', tpe=float, definition='x position in pixels.', profile_name='',
                      editable=False)
        self.register(key='y', units='px', tpe=float, definition='y position in pixels.', profile_name='',
                      editable=False)
        self.register(key='h', units='px', tpe=float, definition='height of the bus in pixels.', profile_name='',
                      editable=False)
        self.register(key='w', units='px', tpe=float, definition='Width of the bus in pixels.', profile_name='',
                      editable=False)
        self.register(key='country', units='', tpe=DeviceType.CountryDevice, definition='Country of the bus',
                      profile_name='')
        self.register(key='area', units='', tpe=DeviceType.AreaDevice, definition='Area of the bus', profile_name='')
        self.register(key='zone', units='', tpe=DeviceType.ZoneDevice, definition='Zone of the bus', profile_name='')
        self.register(key='substation', units='', tpe=DeviceType.SubstationDevice,
                      definition='Substation of the bus.')
        self.register(key='voltage_level', units='', tpe=DeviceType.VoltageLevelDevice,
                      definition='Voltage level of the bus.')
        self.register(key='bus_bar', units='', tpe=DeviceType.BusBarDevice,
                      definition='Busbar associated to the bus.')
        self.register(key='longitude', units='deg', tpe=float, definition='longitude of the bus.', profile_name='')
        self.register(key='latitude', units='deg', tpe=float, definition='latitude of the bus.', profile_name='')

        self.register(key='ph_a', units='', tpe=bool, definition='Has phase A?')
        self.register(key='ph_b', units='', tpe=bool, definition='Has phase B?')
        self.register(key='ph_c', units='', tpe=bool, definition='Has phase C?')
        self.register(key='ph_n', units='', tpe=bool, definition='Has phase N?')
        self.register(key='is_grounded', units='', tpe=bool, definition='Is this bus neutral grounded?.')
        self.register(key='rms_model', units='', tpe=SubObjectType.DynamicModelHostType,
                      definition='RMS dynamic model', display=False)

    @property
    def rms_model(self) -> DynamicModelHost:
        return self._rms_model

    @rms_model.setter
    def rms_model(self, value: DynamicModelHost):
        if isinstance(value, DynamicModelHost):
            self._rms_model = value

    @property
    def active_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._active_prof

    @active_prof.setter
    def active_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._active_prof = val
        elif isinstance(val, np.ndarray):
            self._active_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a active_prof')

    @property
    def Vmin_prof(self) -> Profile:
        """
        Pmin profile
        :return: Profile
        """
        return self._Vmin_prof

    @Vmin_prof.setter
    def Vmin_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Vmin_prof = val
        elif isinstance(val, np.ndarray):
            self._Vmin_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Vmin_prof')

    @property
    def Vmax_prof(self) -> Profile:
        """
        Pmin profile
        :return: Profile
        """
        return self._Vmax_prof

    @Vmax_prof.setter
    def Vmax_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Vmax_prof = val
        elif isinstance(val, np.ndarray):
            self._Vmax_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Vmax_prof')

    @property
    def voltage_level(self) -> Union[VoltageLevel, None]:
        """
        voltage_level getter
        :return: Union[VoltageLevel, None]
        """
        return self._voltage_level

    @voltage_level.setter
    def voltage_level(self, val: Union[VoltageLevel, None]):
        """
        voltage_level getter
        :param val: value
        """
        if isinstance(val, Union[VoltageLevel, None]):
            self._voltage_level = val

            if val is not None:
                if val.substation is not None and self.substation is None:
                    self.substation = val.substation
        else:
            raise Exception(f'{type(val)} not supported to be set into a '
                            f'voltage_level of type Union[VoltageLevel, None]')

    def determine_bus_type(self) -> BusMode:
        """
        Infer the bus type from the devices attached to it
        @return: BusMode
        """
        if not self.active:
            return BusMode.PQ_tpe

        if self.is_slack:
            # if it is set as slack, set the bus as slack and exit
            self.type = BusMode.Slack_tpe
            return BusMode.Slack_tpe

        return BusMode.PQ_tpe

    def get_voltage_guess(self, use_stored_guess=False) -> complex:
        """
        Determine the voltage initial guess
        :param use_stored_guess: use the stored guess or get one from the devices
        :return: voltage guess
        """
        if use_stored_guess:
            return self.Vm0 * np.exp(1j * self.Va0)
        else:
            return complex(1, 0)

    def plot_profiles(self, time_profile, ax_load=None, ax_voltage=None, time_series_driver=None, my_index=0):
        """
        plot the profiles of this bus
        :param time_profile: Master profile of time steps (stored in the MultiCircuit)
        :param time_series_driver: time series driver
        :param ax_load: Load axis, if not provided one will be created
        :param ax_voltage: Voltage axis, if not provided one will be created
        :param my_index: index of this object in the time series results
        """

        if ax_load is None:
            fig = plt.figure(figsize=(12, 8))
            fig.suptitle(self.name, fontsize=20)
            if time_series_driver is not None:
                # 2 plots: load + voltage
                ax_load = fig.add_subplot(211)
                ax_voltage = fig.add_subplot(212, sharex=ax_load)
            else:
                # only 1 plot: load
                ax_load = fig.add_subplot(111)
                ax_voltage = None
            show_fig = True
        else:
            show_fig = False

        if time_series_driver is not None:
            v = np.abs(time_series_driver.results.voltage[:, my_index])
            p = time_series_driver.results.S[:, my_index].real
            p_load = p.copy()
            p_load[p_load > 0] = 0
            p_gen = p.copy()
            p_gen[p_gen < 0] = 0
            P_data = {"Load": p_load, "Gen": p_gen}
            t = time_series_driver.results.time_array
            pd.DataFrame(data=v, index=t, columns=['Voltage (p.u.)']).plot(ax=ax_voltage)
            pd.DataFrame(data=P_data, index=t).plot(ax=ax_load)

            ax_load.set_ylabel('Power [MW]', fontsize=11)
            ax_load.legend()
        else:
            pass

        if ax_voltage is not None:
            ax_voltage.set_ylabel('Voltage module [p.u.]', fontsize=11)
            ax_voltage.legend()

        if show_fig:
            plt.show()

    def get_fault_impedance(self):
        """
        Get the fault impedance
        :return: complex value of fault impedance
        """
        return complex(self.r_fault, self.x_fault)

    def get_coordinates(self) -> Tuple[float, float]:
        """
        Get tuple of the bus coordinates (longitude, latitude)
        """
        return self.longitude, self.latitude

    def try_to_find_coordinates(self):
        """
        Try to find the bus coordinates
        """
        lon, lat = self.longitude, self.latitude

        if self.substation is not None:
            if lon == 0.0:
                lon = self.substation.longitude

        if self.substation is not None:
            if lat == 0.0:
                lat = self.substation.latitude

        return lon, lat

    @property
    def internal(self):
        return self.graphic_type == BusGraphicType.Internal

    @internal.setter
    def internal(self, val: bool):
        if val:
            self.graphic_type = BusGraphicType.Internal
        else:
            pass

    @property
    def bus_bar(self) -> BusBar:
        return self._bus_bar

    @bus_bar.setter
    def bus_bar(self, val: BusBar):
        if isinstance(val, BusBar) or val is None:
            self._bus_bar = val
        else:
            raise ValueError("The value must be a BusBar")

    def initialize_rms(self):

        if self.rms_model.empty():
            Vm = Var("Vm")
            Va = Var("Va")
            P = Var("P")
            Q = Var("Q")

            self.rms_model.model = Block(
                state_eqs=[],
                state_vars=[],
                algebraic_eqs=[
                ],
                algebraic_vars=[Vm, Va],

                init_eqs={},
                init_vars=[],
                external_mapping={
                    DynamicVarType.Vm: Vm,
                    DynamicVarType.Va: Va,
                    DynamicVarType.P: P,
                    DynamicVarType.Q: Q
                }
            )
