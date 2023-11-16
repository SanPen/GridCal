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


import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from GridCalEngine.basic_structures import BusMode, ExternalGridMode, Vec, CxVec
from GridCalEngine.Core.Devices.editable_device import EditableDevice, DeviceType
from GridCalEngine.Core.Devices.Aggregation import Area, Zone, Country
from GridCalEngine.Core.Devices.Substation.substation import Substation


class Bus(EditableDevice):
    """
    The Bus object is the container of all the possible devices that can be attached to
    a bus bar or Substation. Such objects can be loads, voltage controlled generators,
    static generators, batteries, shunt elements, etc.

    Arguments:

        **name** (str, "Bus"): Name of the bus

        **vnom** (float, 10.0): Nominal voltage in kV

        **vmin** (float, 0.9): Minimum per unit voltage

        **vmax** (float, 1.1): Maximum per unit voltage

        **r_fault** (float, 0.0): Resistance of the fault in per unit (SC only)

        **x_fault** (float, 0.0): Reactance of the fault in per unit (SC only)

        **xpos** (int, 0): X position in pixels (GUI only)

        **ypos** (int, 0): Y position in pixels (GUI only)

        **height** (int, 0): Height of the graphic object (GUI only)

        **width** (int, 0): Width of the graphic object (GUI only)

        **active** (bool, True): Is the bus active?

        **is_slack** (bool, False): Is this bus a slack bus?

        **area** (str, "Default"): Name of the area

        **zone** (str, "Default"): Name of the zone

        **Substation** (str, "Default"): Name of the Substation

    Additional Properties:

        **Qmin_sum** (float, 0): Minimum reactive power of this bus (inferred from the devices)

        **Qmax_sum** (float, 0): Maximum reactive power of this bus (inferred from the devices)

        **loads** (list, list()): List of loads attached to this bus

        **controlled_generators** (list, list()): List of controlled generators attached to this bus

        **shunts** (list, list()): List of shunts attached to this bus

        **batteries** (list, list()): List of batteries attached to this bus

        **static_generators** (list, list()): List of static generators attached to this bus

        **measurements** (list, list()): List of measurements

    """

    def __init__(self, name="Bus",
                 idtag=None,
                 code='',
                 vnom=10,
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
                 is_tr_bus=False,
                 area: Area = None,
                 zone: Zone = None,
                 substation: Substation = None,
                 country: Country = None,
                 longitude=0.0,
                 latitude=0.0,
                 Vm0=1,
                 Va0=0):

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=DeviceType.BusDevice)

        self.active = active
        self.active_prof = None

        # Nominal voltage (kV)
        self.Vnom = vnom

        # minimum voltage limit
        self.Vmin = vmin

        # maximum voltage limit
        self.Vmax = vmax

        self.Vm0 = Vm0

        self.Va0 = Va0

        self.angle_min = angle_min

        self.angle_max = angle_max

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

        # List of load s attached to this bus
        self.loads = list()

        # List of Controlled generators attached to this bus
        self.generators = list()

        # List of External Grids
        self.external_grids = list()

        # List of shunt s attached to this bus
        self.shunts = list()

        # List of batteries attached to this bus
        self.batteries = list()

        # List of static generators attached tot this bus
        self.static_generators = list()

        # List of measurements
        self.measurements = list()

        # Bus type
        self.type = BusMode.PQ

        # Flag to determine if the bus is a slack bus or not
        self.is_slack = is_slack

        # determined if this bus is an AC or DC bus
        self.is_dc = is_dc

        # determine if this bus is part of a composite transformer such as a 3-winding transformer
        self.is_tr_bus = is_tr_bus

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

        self.register(key='name', units='', tpe=str, definition='Name of the bus', profile_name='')
        self.register(key='idtag', units='', tpe=str, definition='Unique ID', profile_name='', editable=False)
        self.register(key='code', units='', tpe=str, definition='Some code to further identify the bus',
                      profile_name='')
        self.register(key='active', units='', tpe=bool, definition='Is the bus active? used to disable the bus.',
                      profile_name='active_prof')
        self.register(key='is_slack', units='', tpe=bool, definition='Force the bus to be of slack type.',
                      profile_name='')
        self.register(key='is_dc', units='', tpe=bool, definition='Is this bus of DC type?.', profile_name='')
        self.register(key='is_tr_bus', units='', tpe=bool,
                      definition='Is this bus part of a composite transformer, such as  a 3-winding transformer?.',
                      profile_name='')
        self.register(key='Vnom', units='kV', tpe=float, definition='Nominal line voltage of the bus.', profile_name='')
        self.register(key='Vm0', units='p.u.', tpe=float, definition='Voltage module guess.', profile_name='')
        self.register(key='Va0', units='rad.', tpe=float, definition='Voltage angle guess.', profile_name='')
        self.register(key='Vmin', units='p.u.', tpe=float, definition='Lower range of allowed voltage module.',
                      profile_name='')
        self.register(key='Vmax', units='p.u.', tpe=float, definition='Higher range of allowed voltage module.',
                      profile_name='')
        self.register(key='angle_min', units='rad.', tpe=float, definition='Lower range of allowed voltage angle.',
                      profile_name='')
        self.register(key='angle_max', units='rad.', tpe=float, definition='Higher range of allowed voltage angle.',
                      profile_name='')
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
        self.register(key='substation', units='', tpe=DeviceType.SubstationDevice, definition='Substation of the bus.',
                      profile_name='')
        self.register(key='longitude', units='deg', tpe=float, definition='longitude of the bus.', profile_name='')
        self.register(key='latitude', units='deg', tpe=float, definition='latitude of the bus.', profile_name='')

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, val: str):
        self._name = val

    def delete_children(self):
        """
        Delete all the children
        """
        self.batteries.clear()
        self.shunts.clear()
        self.static_generators.clear()
        self.external_grids.clear()
        self.loads.clear()
        self.generators.clear()

    def add_device(self, device) -> None:
        """
        Add device to the bus in the corresponding list
        :param device:
        """
        if device.device_type == DeviceType.BatteryDevice:
            self.batteries.append(device)

        elif device.device_type == DeviceType.ShuntDevice:
            self.shunts.append(device)

        elif device.device_type == DeviceType.StaticGeneratorDevice:
            self.static_generators.append(device)

        elif device.device_type == DeviceType.LoadDevice:
            self.loads.append(device)

        elif device.device_type == DeviceType.GeneratorDevice:
            self.generators.append(device)

        elif device.device_type == DeviceType.ExternalGridDevice:
            self.external_grids.append(device)
        else:
            raise Exception('Device type not understood:' + str(device.device_type))

    def determine_bus_type(self) -> BusMode:
        """
        Infer the bus type from the devices attached to it
        @return: self.type
        """
        if not self.active:
            return BusMode.PQ

        if self.is_slack:
            # if it is set as slack, set the bus as slack and exit
            self.type = BusMode.Slack
            return BusMode.Slack

        elif len(self.external_grids) > 0:  # there are devices setting this as a slack bus

            # count the number of active external grids
            ext_on = 0
            for elm in self.external_grids:
                if elm.active and elm.mode == ExternalGridMode.VD:
                    ext_on += 1

            # if there ar any active external grids, set as slack and exit
            if ext_on > 0:
                self.type = BusMode.Slack
                return BusMode.Slack

        # if we got here, determine what to do...

        # count the active and controlled generators
        gen_on = 0
        for elm in self.generators:
            if elm.active and elm.is_controlled:
                gen_on += 1

        # count the active and controlled batteries
        batt_on = 0
        for elm in self.batteries:
            if elm.active and elm.is_controlled:
                batt_on += 1

        shunt_on = 0
        for elm in self.shunts:
            if elm.active and elm.is_controlled:
                shunt_on += 1

        if (gen_on + batt_on + shunt_on) > 0:
            self.type = BusMode.PV
            return BusMode.PV

        else:
            # Nothing special; set it as PQ
            self.type = BusMode.PQ
            return BusMode.PQ

    def determine_bus_type_at(self, t) -> BusMode:
        """
        Infer the bus type from the devices attached to it
        :param t: time index
        @return: self.type
        """
        if not self.active_prof[t]:
            return BusMode.PQ

        if self.is_slack:
            # if it is set as slack, set the bus as slack and exit
            return BusMode.Slack

        elif len(self.external_grids) > 0:  # there are devices setting this as a slack bus

            # count the number of active external grids
            ext_on = 0
            for elm in self.external_grids:
                if elm.active_prof[t] and elm.mode == ExternalGridMode.VD:
                    ext_on += 1

            # if there ar any active external grids, set as slack and exit
            if ext_on > 0:
                return BusMode.Slack

        # if we got here, determine what to do...

        # count the active and controlled generators
        gen_on = 0
        for elm in self.generators:
            if elm.active_prof[t] and elm.is_controlled:
                gen_on += 1

        # count the active and controlled batteries
        batt_on = 0
        for elm in self.batteries:
            if elm.active_prof[t] and elm.is_controlled:
                batt_on += 1

        shunt_on = 0
        for elm in self.shunts:
            if elm.active_prof[t] and elm.is_controlled:
                shunt_on += 1

        if (gen_on + batt_on + shunt_on) > 0:
            return BusMode.PV

        else:
            # Nothing special; set it as PQ
            return BusMode.PQ

    def determine_bus_type_prof(self):
        """
        Array of bus types according to the profile
        :return: array of bus type numbers
        """
        if self.active_prof is not None:
            nt = self.active_prof.shape[0]
            values = np.zeros(nt, dtype=int)
            for t in range(nt):
                values[t] = self.determine_bus_type_at(t).value
            return values
        else:
            raise Exception('Asked the profile types with no profile!')

    def get_reactive_power_limits(self):
        """
        get the summation of reactive power
        @return: Qmin, Qmax
        """
        Qmin = 0.0
        Qmax = 0.0

        # count the active and controlled generators
        for elm in self.generators + self.batteries:
            if elm.active:
                if elm.is_controlled:
                    Qmin += elm.Qmin
                    Qmax += elm.Qmax

        for elm in self.shunts:
            if elm.active:
                if elm.is_controlled:
                    Qmin += elm.Bmin
                    Qmax += elm.Bmax

        return Qmin, Qmax

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
            vm = 1.0
            va = 0.0
            v = complex(1, 0)

            for lst in [self.generators, self.batteries]:
                for elm in lst:
                    if vm == 1.0:
                        v = complex(elm.Vset, 0)
                        vm = elm.Vset
                    elif elm.Vset != vm:
                        if logger is not None:
                            logger.append(
                                'Different set points at ' + self.name + ': ' + str(elm.Vset) + ' !=' + str(v))

            return v

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
            p = np.abs(time_series_driver.results.S[:, my_index])
            t = time_series_driver.results.time_array
            pd.DataFrame(data=v, index=t, columns=['Voltage (p.u.)']).plot(ax=ax_voltage)
            pd.DataFrame(data=p, index=t, columns=['Computed power (p.u.)']).plot(ax=ax_load)

            # plot the objects' active power profiles

            devices = self.loads + self.generators + self.batteries + self.static_generators
            if len(devices) > 0:
                dta = dict()
                for elm in devices:
                    dta[elm.name + ' defined'] = elm.P_prof
                pd.DataFrame(data=dta, index=t).plot(ax=ax_load)

            ax_load.set_ylabel('Power [MW]', fontsize=11)
            ax_load.legend()
        else:
            pass

        if ax_voltage is not None:
            ax_voltage.set_ylabel('Voltage module [p.u.]', fontsize=11)
            ax_voltage.legend()

        if show_fig:
            plt.show()

    def get_active_injection_profiles_dictionary(self):
        """
        Get the devices' profiles in a dictionary with the correct sign
        :return:
        """
        dta = dict()
        devices = self.generators + self.batteries + self.static_generators
        if len(devices) > 0:
            for elm in devices:
                dta[elm.name] = elm.P_prof

        for elm in self.loads:
            dta[elm.name] = -elm.P_prof

        return dta

    def get_properties_dict(self, version=3):
        """
        Return Json-like dictionary
        :return: Dictionary
        """
        if version in [2, 3]:
            return {'id': self.idtag,
                    'type': self.determine_bus_type().value,
                    'phases': 'ps',
                    'name': self.name,
                    'name_code': self.code,
                    'active': self.active,
                    'is_slack': bool(self.is_slack),
                    'vnom': self.Vnom,
                    'vmin': self.Vmin,
                    'vmax': self.Vmax,
                    'rf': self.r_fault,
                    'xf': self.x_fault,
                    'x': self.x,
                    'y': self.y,
                    'h': self.h,
                    'w': self.w,
                    'lat': self.latitude,
                    'lon': self.longitude,
                    'alt': 0.0,
                    'country': self.country.idtag if self.country is not None else "",
                    'area': self.area.idtag if self.area is not None else "",
                    'zone': self.zone.idtag if self.zone is not None else "",
                    'Substation': self.substation.idtag if self.substation is not None else ""
                    }
        else:
            return dict()

    def get_profiles_dict(self, version=3):
        """

        :return:
        """
        if self.active_prof is not None:
            active_profile = self.active_prof.tolist()
        else:
            active_profile = list()

        return {'id': self.idtag,
                'active': active_profile}

    def get_units_dict(self, version=3):
        """
        Get units of the values
        """
        return {'vnom': 'kV',
                'vmin': 'p.u.',
                'vmax': 'p.u.',
                'rf': 'p.u.',
                'xf': 'p.u.',
                'x': 'px',
                'y': 'px',
                'h': 'px',
                'w': 'px',
                'lat': 'degrees',
                'lon': 'degrees',
                'alt': 'm'}

    def set_state(self, t):
        """
        Set the profiles state of the objects in this bus to the value given in the profiles at the index t
        :param t: index of the profile
        :return: Nothing
        """

        self.set_profile_values(t)

        for elm in self.loads:
            elm.set_profile_values(t)

        for elm in self.static_generators:
            elm.set_profile_values(t)

        for elm in self.external_grids:
            elm.set_profile_values(t)

        for elm in self.batteries:
            elm.set_profile_values(t)

        for elm in self.generators:
            elm.set_profile_values(t)

        for elm in self.shunts:
            elm.set_profile_values(t)

    def delete_profiles(self):
        """
        Delete all profiles
        """
        for elm in self.loads:
            elm.delete_profiles()

        for elm in self.static_generators:
            elm.delete_profiles()

        for elm in self.external_grids:
            elm.delete_profiles()

        for elm in self.batteries:
            elm.delete_profiles()

        for elm in self.generators:
            elm.delete_profiles()

        for elm in self.shunts:
            elm.delete_profiles()

    def create_profiles(self, index):
        """
        Format all profiles
        """

        # create the profiles of this very object
        super().create_profiles(index)

        for elm in self.loads:
            elm.create_profiles(index)

        for elm in self.static_generators:
            elm.create_profiles(index)

        for elm in self.external_grids:
            elm.create_profiles(index)

        for elm in self.batteries:
            elm.create_profiles(index)

        for elm in self.generators:
            elm.create_profiles(index)

        for elm in self.shunts:
            elm.create_profiles(index)

    def set_profile_values(self, t):
        """
        Set the default values from the profiles at time index t
        :param t: profile time index
        """
        super().set_profile_values(t)

        for elm in self.loads:
            elm.set_profile_values(t)

        for elm in self.static_generators:
            elm.set_profile_values(t)

        for elm in self.external_grids:
            elm.set_profile_values(t)

        for elm in self.batteries:
            elm.set_profile_values(t)

        for elm in self.generators:
            elm.set_profile_values(t)

        for elm in self.shunts:
            elm.set_profile_values(t)

    def merge(self, other_bus: "Bus"):
        """
        Add the elements of the "Other bus" to this bus
        :param other_bus: Another instance of Bus
        """
        # List of load s attached to this bus
        self.loads += other_bus.loads.copy()

        # List of Controlled generators attached to this bus
        self.generators += other_bus.generators.copy()

        self.external_grids += other_bus.external_grids.copy()

        # List of shunt s attached to this bus
        self.shunts += other_bus.shunts.copy()

        # List of batteries attached to this bus
        self.batteries += other_bus.batteries.copy()

        # List of static generators attached tot this bus
        self.static_generators += other_bus.static_generators.copy()

        # List of measurements
        self.measurements += other_bus.measurements.copy()

    def get_fault_impedance(self):
        """
        Get the fault impedance
        :return: complex value of fault impedance
        """
        return complex(self.r_fault, self.x_fault)

    def get_coordinates(self):
        """
        Get tuple of the bus coordinates (longitude, latitude)
        """
        return self.longitude, self.latitude

    def get_devices_list(self):
        """
        Return a list of all the connected objects
        :return: list of connected objects
        """
        return self.loads + \
            self.generators + \
            self.batteries + \
            self.static_generators + \
            self.shunts + \
            self.external_grids

    def get_device_number(self) -> int:
        """
        Return a list of all the connected objects
        :return: list of connected objects
        """
        return (len(self.loads) +
                len(self.generators) +
                len(self.batteries) +
                len(self.static_generators) +
                len(self.shunts) +
                len(self.external_grids))

    # def ensure_area_objects(self, circuit: "MultiCircuit"):
    #     """
    #     Ensure that every grouping parameter has an object
    #     :param circuit: MultiCircuit instance
    #     """
    #     if self.area is None:
    #         self.area = circuit.areas[0]
    #
    #     if self.zone is None:
    #         self.zone = circuit.zones[0]
    #
    #     if self.substation is None:
    #         self.substation = circuit.substations[0]
    #
    #     if self.country is None:
    #         self.country = circuit.countries[0]

    @staticmethod
    def get_fused_device_lst(elm_list, property_names: list):
        """
        Fuse all the devices of a list by adding their selected properties
        :param elm_list: list of devices
        :param property_names: properties to fuse
        :return: list of one element
        """
        if len(elm_list) > 1:
            # more than a single element, fuse the list

            elm1 = elm_list[0]  # select the main generator
            act_final = elm1.active
            act_prof_final = elm1.active_prof

            # set the final active value
            for i in range(1, len(elm_list)):  # for each of the other generators
                elm2 = elm_list[i]

                # modify the final status
                act_final = bool(act_final + elm2.active)  # equivalent to OR

                if act_prof_final is not None:
                    act_prof_final = (act_prof_final + elm2.active_prof).astype(bool)

            for prop in property_names:  # sum the properties

                # initialize the value with whatever it is inside elm1
                if 'prof' not in prop:
                    # is a regular property
                    val = getattr(elm1, prop) * elm1.active
                else:
                    if act_prof_final is not None:
                        # it is a profile property
                        val = getattr(elm1, prop) * elm1.active_prof
                    else:
                        val = None

                for i in range(1, len(elm_list)):  # for each of the other generators
                    elm2 = elm_list[i]

                    if 'prof' not in prop:
                        # is a regular property
                        val += getattr(elm2, prop) * elm2.active
                    else:
                        if act_prof_final is not None:
                            # it is a profile property
                            val += getattr(elm2, prop) * elm2.active_prof

                # set the final property value
                if 'prof' not in prop:
                    setattr(elm1, prop, val)
                else:
                    setattr(elm1, prop, val)

            # set the final active status
            elm1.active = act_final
            elm1.active_prof = act_prof_final

            return [elm1]

        elif len(elm_list) == 1:
            # single element list, return it as it comes
            return elm_list

        else:
            # the list is empty
            return list()

    def fuse_devices(self):
        """
        Fuse the devices into one device per type
        """
        self.generators = self.get_fused_device_lst(self.generators,
                                                    ['P', 'Pmin', 'Pmax', 'Qmin', 'Qmax', 'Snom', 'P_prof'])
        self.batteries = self.get_fused_device_lst(self.batteries,
                                                   ['P', 'Pmin', 'Pmax', 'Qmin', 'Qmax', 'Snom', 'Enom', 'P_prof'])

        self.loads = self.get_fused_device_lst(self.loads, ['P', 'Q', 'Ir', 'Ii', 'G', 'B', 'P_prof', 'Q_prof'])
        self.static_generators = self.get_fused_device_lst(self.static_generators, ['P', 'Q', 'P_prof', 'Q_prof'])

        self.shunts = self.get_fused_device_lst(self.shunts, ['G', 'B', 'G_prof', 'B_prof'])
        self.external_grids = self.get_fused_device_lst(self.external_grids, [])

    def get_Sbus(self) -> complex:
        """
        Compute the complex power Injections, includes the active effect
        :return: complex bus power injection (snapshot value)
        """
        val = 0.0j

        for elm in self.generators:
            val += elm.P * elm.active

        for elm in self.batteries:
            val += elm.P * elm.active

        for elm in self.static_generators:
            val += (elm.P + 1j * elm.Q) * elm.active

        for elm in self.external_grids:
            val += (elm.P + 1j * elm.Q) * elm.active

        for elm in self.loads:
            val -= (elm.P + 1j * elm.Q) * elm.active

        return val

    def get_Sbus_prof(self) -> CxVec:
        """
        Compute the complex power Injections, includes the active effect
        :return: vector of complex nodal injections
        """
        nt = len(self.active_prof)
        val = np.zeros(nt, dtype=complex)

        for elm in self.generators:
            val += elm.P_prof * elm.active_prof

        for elm in self.batteries:
            val += elm.P_prof * elm.active_prof

        for elm in self.static_generators:
            val += (elm.P_prof + 1j * elm.Q_prof) * elm.active_prof

        for elm in self.external_grids:
            val += (elm.P_prof + 1j * elm.Q_prof) * elm.active_prof

        for elm in self.loads:
            val -= (elm.P_prof + 1j * elm.Q_prof) * elm.active_prof

        return val

    def get_Sbus_prof_fixed(self) -> CxVec:
        """
        Compute the complex power Injections considering only the fixed devices
        For generators and batteries this means that they are included only if they are enabled_dispatch=False
        :return: vector of complex nodal injections
        """
        nt = len(self.active_prof)
        val = np.zeros(nt, dtype=complex)

        for elm in self.generators:
            if not elm.enabled_dispatch:
                val += elm.P_prof * elm.active_prof

        for elm in self.batteries:
            if not elm.enabled_dispatch:
                val += elm.P_prof * elm.active_prof

        for elm in self.static_generators:
            val += (elm.P_prof + 1j * elm.Q_prof) * elm.active_prof

        for elm in self.external_grids:
            val += (elm.P_prof + 1j * elm.Q_prof) * elm.active_prof

        for elm in self.loads:
            val -= (elm.P_prof + 1j * elm.Q_prof) * elm.active_prof

        return val

    def get_Sbus_prof_dispatchable(self) -> CxVec:
        """
        Compute the complex power Injections considering only the dispatchable devices
        For generators and batteries this means that they are included only if they are enabled_dispatch=True
        :return: vector of complex nodal injections
        """
        nt = len(self.active_prof)
        val = np.zeros(nt, dtype=complex)

        for elm in self.generators:
            if elm.enabled_dispatch:
                val += elm.P_prof * elm.active_prof

        for elm in self.batteries:
            if elm.enabled_dispatch:
                val += elm.P_prof * elm.active_prof

        return val
