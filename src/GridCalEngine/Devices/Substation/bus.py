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

from typing import Tuple, Union
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from GridCalEngine.enumerations import BusMode
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType
from GridCalEngine.Devices.Aggregation import Area, Zone, Country
from GridCalEngine.Devices.Substation.substation import Substation
from GridCalEngine.Devices.Substation.voltage_level import VoltageLevel
from GridCalEngine.Devices.profile import Profile


class Bus(EditableDevice):

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
                 area: Area = None,
                 zone: Zone = None,
                 substation: Substation = None,
                 voltage_level: VoltageLevel = None,
                 country: Country = None,
                 longitude=0.0,
                 latitude=0.0,
                 Vm0=1,
                 Va0=0):
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
        :param is_internal: Is this bus an internal bus? (i.e. the central bus on a 3W transformer, or the bus of a FluidNode)
        :param area: Area object
        :param zone: Zone object
        :param substation: Substation object
        :param country: Country object
        :param longitude: longitude (deg)
        :param latitude: latitude (deg)
        :param Vm0: initial solution for the voltage module (p.u.)
        :param Va0: initial solution for the voltage angle (rad)
        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=DeviceType.BusDevice)

        self.active = active
        self._active_prof = Profile(default_value=active, data_type=bool)

        # Nominal voltage (kV)
        self.Vnom = Vnom

        # minimum voltage limit
        self.Vmin = vmin
        self.Vm_cost = 1.0

        # maximum voltage limit
        self.Vmax = vmax

        self.Vm0 = Vm0

        self.Va0 = Va0

        self.angle_min = angle_min

        self.angle_max = angle_max

        self.angle_cost = 0

        # summation of lower reactive power limits connected
        self.Qmin_sum = 0

        # summation of upper reactive power limits connected
        self.Qmax_sum = 0

        # short circuit impedance
        self.r_fault = r_fault
        self.x_fault = x_fault

        # is the bus active?
        self.active = active

        self.country: Country = country

        self.area: Area = area

        self.zone: Zone = zone

        self.substation: Substation = substation

        self._voltage_level: VoltageLevel = voltage_level

        # Bus type
        self.type = BusMode.PQ

        # Flag to determine if the bus is a slack bus or not
        self.is_slack = is_slack

        # determined if this bus is an AC or DC bus
        self.is_dc = is_dc

        # determine if this bus is part of a composite transformer such as a 3-winding transformer
        self.is_internal = is_internal

        # if true, the presence of storage devices turn the bus into a Reference bus in practice
        # So that P +jQ are computed
        self.dispatch_storage = False

        # position and dimensions
        self.x = xpos
        self.y = ypos
        self.h = height
        self.w = width
        self.longitude = longitude
        self.latitude = latitude

        self.register(key='active', units='', tpe=bool, definition='Is the bus active? used to disable the bus.',
                      profile_name='active_prof')
        self.register(key='is_slack', units='', tpe=bool, definition='Force the bus to be of slack type.',
                      profile_name='')
        self.register(key='is_dc', units='', tpe=bool, definition='Is this bus of DC type?.', profile_name='')
        self.register(key='is_internal', units='', tpe=bool,
                      definition='Is this bus part of a composite transformer, '
                                 'such as  a 3-winding transformer or a fluid node?.',
                      profile_name='', old_names=['is_tr_bus'])
        self.register(key='Vnom', units='kV', tpe=float, definition='Nominal line voltage of the bus.', profile_name='')
        self.register(key='Vm0', units='p.u.', tpe=float, definition='Voltage module guess.', profile_name='')
        self.register(key='Va0', units='rad.', tpe=float, definition='Voltage angle guess.', profile_name='')
        self.register(key='Vmin', units='p.u.', tpe=float, definition='Lower range of allowed voltage module.',
                      profile_name='')
        self.register(key='Vmax', units='p.u.', tpe=float, definition='Higher range of allowed voltage module.',
                      profile_name='')
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
        self.register(key='longitude', units='deg', tpe=float, definition='longitude of the bus.', profile_name='')
        self.register(key='latitude', units='deg', tpe=float, definition='latitude of the bus.', profile_name='')

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
            return BusMode.PQ

        if self.is_slack:
            # if it is set as slack, set the bus as slack and exit
            self.type = BusMode.Slack
            return BusMode.Slack

        return BusMode.PQ

    def get_voltage_guess(self, logger=None, use_stored_guess=False):
        """
        Determine the voltage initial guess
        :param logger: Logger object
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
            P_data = {"Load":  p_load, "Gen": p_gen}
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
