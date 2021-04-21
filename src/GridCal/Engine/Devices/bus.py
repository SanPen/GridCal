# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.


import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from GridCal.Engine.basic_structures import BusMode
from GridCal.Engine.Devices.editable_device import EditableDevice, DeviceType, GCProp
from GridCal.Engine.Devices.groupings import Area, Substation, Zone, Country


class Bus(EditableDevice):
    """
    The Bus object is the container of all the possible devices that can be attached to
    a bus bar or substation. Such objects can be loads, voltage controlled generators,
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

        **substation** (str, "Default"): Name of the substation

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

    def __init__(self, name="Bus", idtag=None, code='', vnom=10, vmin=0.9, vmax=1.1, r_fault=0.0, x_fault=0.0,
                 xpos=0, ypos=0, height=0, width=0, active=True, is_slack=False, is_dc=False,
                 area=None, zone=None, substation=None, country=None, longitude=0.0, latitude=0.0):

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                active=active,
                                code=code,
                                device_type=DeviceType.BusDevice,
                                editable_headers={'name': GCProp('', str, 'Name of the bus'),
                                                  'idtag': GCProp('', str, 'Unique ID'),
                                                  'code': GCProp('', str, 'Some code to further identify the bus'),
                                                  'active': GCProp('', bool,
                                                                   'Is the bus active? used to disable the bus.'),
                                                  'is_slack': GCProp('', bool, 'Force the bus to be of slack type.'),
                                                  'is_dc': GCProp('', bool, 'Is this bus of DC type?.'),
                                                  'Vnom': GCProp('kV', float,
                                                                 'Nominal line voltage of the bus.'),
                                                  'Vmin': GCProp('p.u.', float,
                                                                 'Lower range of allowed voltage.'),
                                                  'Vmax': GCProp('p.u.', float,
                                                                 'Higher range of allowed range.'),
                                                  'r_fault': GCProp('p.u.', float,
                                                                    'Resistance of the fault.\n'
                                                                    'This is used for short circuit studies.'),
                                                  'x_fault': GCProp('p.u.', float, 'Reactance of the fault.\n'
                                                                    'This is used for short circuit studies.'),
                                                  'x': GCProp('px', float, 'x position in pixels.'),
                                                  'y': GCProp('px', float, 'y position in pixels.'),
                                                  'h': GCProp('px', float, 'height of the bus in pixels.'),
                                                  'w': GCProp('px', float, 'Width of the bus in pixels.'),
                                                  'country': GCProp('', DeviceType.CountryDevice, 'Country of the bus'),
                                                  'area': GCProp('', DeviceType.AreaDevice, 'Area of the bus'),
                                                  'zone': GCProp('', DeviceType.ZoneDevice, 'Zone of the bus'),
                                                  'substation': GCProp('', DeviceType.SubstationDevice, 'Substation of the bus.'),
                                                  'longitude': GCProp('deg', float, 'longitude of the bus.'),
                                                  'latitude': GCProp('deg', float, 'latitude of the bus.')},
                                non_editable_attributes=['idtag'],
                                properties_with_profile={'active': 'active_prof'})

        # Nominal voltage (kV)
        self.Vnom = vnom

        # minimum voltage limit
        self.Vmin = vmin

        # maximum voltage limit
        self.Vmax = vmax

        # summation of lower reactive power limits connected
        self.Qmin_sum = 0

        # summation of upper reactive power limits connected
        self.Qmax_sum = 0

        # short circuit impedance
        self.r_fault = r_fault
        self.x_fault = x_fault

        # is the bus active?
        self.active = active

        self.active_prof = None

        self.country = country

        self.area = area

        self.zone = zone

        self.substation = substation

        # List of load s attached to this bus
        self.loads = list()

        # List of Controlled generators attached to this bus
        self.controlled_generators = list()

        # List of shunt s attached to this bus
        self.shunts = list()

        # List of batteries attached to this bus
        self.batteries = list()

        # List of static generators attached tot this bus
        self.static_generators = list()

        # List of External grid devices
        self.external_grids = list()

        # List of measurements
        self.measurements = list()

        # Bus type
        self.type = BusMode.PQ

        # Flag to determine if the bus is a slack bus or not
        self.is_slack = is_slack

        # determined if this bus is an AC or DC bus
        self.is_dc = is_dc

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

    def delete_children(self):
        """
        Delete all the children
        """
        self.batteries.clear()
        self.shunts.clear()
        self.static_generators.clear()
        self.loads.clear()
        self.controlled_generators.clear()

    def add_device(self, device):
        """
        Add device to the bus in the corresponding list
        :param device:
        :return:
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
            self.controlled_generators.append(device)

        elif device.device_type == DeviceType.ExternalGridDevice:
            self.external_grids.append(device)
        else:
            raise Exception('Device type not understood:' + str(device.device_type))

    def determine_bus_type(self):
        """
        Infer the bus type from the devices attached to it
        @return: self.type
        """
        if self.is_slack:
            # if it is set as slack, set the bus as slack and exit
            self.type = BusMode.Slack
            return self.type

        elif len(self.external_grids) > 0:  # there are devices setting this as a slack bus

            # count the number of active external grids
            ext_on = 0
            for elm in self.external_grids:
                if elm.active:
                    ext_on += 1

            # if there ar any active external grids, set as slack and exit
            if ext_on > 0:
                self.type = BusMode.Slack
                return self.type

        # if we got here, determine what to do...

        # count the active and controlled generators
        gen_on = 0
        for elm in self.controlled_generators:
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

        # elif shunt_on > 0:
        #     self.type = BusMode.PVB

        else:
            # Nothing special; set it as PQ
            self.type = BusMode.PQ

        return self.type

    def get_reactive_power_limits(self):
        """
        get the summation of reactive power
        @return: Qmin, Qmax
        """
        Qmin = 0.0
        Qmax = 0.0

        # count the active and controlled generators
        for elm in self.controlled_generators + self.batteries:
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

    def initialize_lp_profiles(self):
        """
        Dimension the LP var profiles
        :return: Nothing
        """
        for elm in (self.controlled_generators + self.batteries):
            elm.initialize_lp_vars()

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
            t = time_series_driver.results.time
            pd.DataFrame(data=v, index=t, columns=['Voltage (p.u.)']).plot(ax=ax_voltage)
            pd.DataFrame(data=p, index=t, columns=['Computed power (p.u.)']).plot(ax=ax_load)

            # plot the objects' active power profiles

            devices = self.loads + self.controlled_generators + self.batteries + self.static_generators
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
        devices = self.controlled_generators + self.batteries + self.static_generators
        if len(devices) > 0:
            for elm in devices:
                dta[elm.name] = elm.P_prof

        for elm in self.loads:
            dta[elm.name] = -elm.P_prof

        return dta

    def copy(self):
        """
        Deep copy of this object
        :return: New instance of this object
        """
        bus = Bus()
        bus.name = self.name

        # Nominal voltage (kV)
        bus.Vnom = self.Vnom

        bus.vmin = self.Vmin

        bus.Vmax = self.Vmax

        bus.r_fault = self.r_fault

        bus.x_fault = self.x_fault

        bus.Qmin_sum = self.Qmin_sum

        bus.Qmax_sum = self.Qmax_sum

        bus.active = self.active

        # List of load s attached to this bus
        for elm in self.loads:
            bus.loads.append(elm.copy())

        # List of Controlled generators attached to this bus
        for elm in self.controlled_generators:
            bus.controlled_generators.append(elm.copy())

        # List of shunt s attached to this bus
        for elm in self.shunts:
            bus.shunts.append(elm.copy())

        # List of batteries attached to this bus
        for elm in self.batteries:
            bus.batteries.append(elm.copy())

        # List of static generators attached tot this bus
        for g in self.static_generators:
            bus.static_generators.append(g.copy())

        # Bus type
        bus.type = self.type

        # Flag to determine if the bus is a slack bus or not
        bus.is_slack = self.is_slack

        # if true, the presence of storage devices turn the bus into a Reference bus in practice
        # So that P +jQ are computed
        bus.dispatch_storage = self.dispatch_storage

        bus.x = self.x

        bus.y = self.y

        bus.h = self.h

        bus.w = self.w

        bus.area = self.area

        bus.zone = self.zone

        bus.substation = self.substation

        bus.measurements = self.measurements

        bus.active_prof = self.active_prof

        return bus

    def get_properties_dict(self):
        """
        Return Json-like dictionary
        :return: Dictionary
        """

        d = {'id': self.idtag,
             'type': self.determine_bus_type().value,
             'phases': 'ps',
             'name': self.name,
             'name_code': self.code,
             'active': self.active,
             'is_slack': self.is_slack,
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
             'country': self.country.idtag,
             'area': self.area.idtag,
             'zone': self.zone.idtag,
             'substation': self.substation.idtag
             }

        return d

    def get_profiles_dict(self):
        """

        :return:
        """
        if self.active_prof is not None:
            active_profile = self.active_prof.tolist()
        else:
            active_profile = list()

        return {'id': self.idtag,
                'active': active_profile}

    def get_units_dict(self):
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
        for elm in self.loads:
            elm.P = elm.P_prof[t]
            elm.Q = elm.Q_prof[t]
            elm.Ir = elm.Ir_prof[t]
            elm.Ii = elm.Ii_prof[t]
            elm.G = elm.G_prof[t]
            elm.B = elm.B_prof[t]

        for elm in self.static_generators:
            elm.P = elm.P_prof[t]
            elm.Q = elm.Q_prof[t]

        for elm in self.batteries:
            elm.P = elm.P_prof[t]
            elm.Vset = elm.Vset_prof[t]

        for elm in self.controlled_generators:
            elm.P = elm.P_prof[t]
            elm.Vset = elm.Vset_prof[t]

        for elm in self.shunts:
            elm.G = elm.G_prof[t]
            elm.B = elm.B_prof[t]

    def retrieve_graphic_position(self):
        """
        Get the position set by the graphic object into this object's variables
        :return: Nothing
        """
        if self.graphic_obj is not None:
            self.x = self.graphic_obj.pos().x()
            self.y = self.graphic_obj.pos().y()
            self.w, self.h = self.graphic_obj.rect().getCoords()[2:4]

    def delete_profiles(self):
        """
        Delete all profiles
        """
        for elm in self.loads:
            elm.delete_profiles()

        for elm in self.static_generators:
            elm.delete_profiles()

        for elm in self.batteries:
            elm.delete_profiles()

        for elm in self.controlled_generators:
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

        for elm in self.batteries:
            elm.create_profiles(index)

        for elm in self.controlled_generators:
            elm.create_profiles(index)

        for elm in self.shunts:
            elm.create_profiles(index)

    def set_profile_values(self, t):
        """
        Set the default values from the profiles at time index t
        :param t: profile time index
        """

        for elm in self.loads:
            elm.set_profile_values(t)

        for elm in self.static_generators:
            elm.set_profile_values(t)

        for elm in self.batteries:
            elm.set_profile_values(t)

        for elm in self.controlled_generators:
            elm.set_profile_values(t)

        for elm in self.shunts:
            elm.set_profile_values(t)

    def apply_lp_profiles(self, Sbase):
        """
        Sets the lp solution to the regular generators profile
        """
        for elm in self.batteries + self.controlled_generators:
            elm.apply_lp_profile(Sbase)

    def merge(self, other_bus):
        """
        Add the elements of the "Other bus" to this bus
        :param other_bus: Another instance of Bus
        """
        # List of load s attached to this bus
        self.loads += other_bus.loads.copy()

        # List of Controlled generators attached to this bus
        self.controlled_generators += other_bus.controlled_generators.copy()

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
        Get tuple of the bus coordinates (latitude, longitude)
        """
        return self.latitude, self.longitude

    def get_devices_list(self):
        """
        Return a list of all the connected objects
        :return: list of connected objects
        """
        return self.loads + self.controlled_generators + self.batteries + self.static_generators + self.shunts

    def get_device_number(self):
        """
        Return a list of all the connected objects
        :return: list of connected objects
        """
        return len(self.loads) + len(self.controlled_generators) + len(self.batteries) + len(self.static_generators) + len(self.shunts)

    def ensure_area_objects(self, circuit):
        """
        Ensure that every grouping parameter has an object
        :param circuit: MultiCircuit instance
        """
        if self.area is None:
            self.area = circuit.areas[0]

        if self.zone is None:
            self.zone = circuit.zones[0]

        if self.substation is None:
            self.substation = circuit.substations[0]

        if self.country is None:
            self.country = circuit.countries[0]


