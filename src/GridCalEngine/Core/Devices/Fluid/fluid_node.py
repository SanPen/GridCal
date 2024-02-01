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
from GridCalEngine.Core.Devices.editable_device import EditableDevice
from GridCalEngine.Core.Devices.Substation.bus import Bus
from GridCalEngine.enumerations import BuildStatus, DeviceType


class FluidNode(EditableDevice):

    def __init__(self,
                 name: str = '',
                 idtag: Union[str, None] = None,
                 code: str = '',
                 min_level: float = 0.0,
                 max_level: float = 0.0,
                 current_level: float = 0.0,
                 spillage_cost: float = 1000.0,
                 inflow: float = 0.0,
                 spillage_cost_prof=None,
                 inflow_prof=None,
                 bus: Union[None, Bus] = None,
                 build_status: BuildStatus = BuildStatus.Commissioned):
        """
        FluidNode
        :param name: name of the node
        :param idtag: UUID
        :param code: secondary code
        :param min_level: Minimum amount of fluid at the node/reservoir [m3]
        :param max_level: Maximum amount of fluid at the node/reservoir [m3]
        :param current_level: Initial level of the node/reservoir [m3]
        :param spillage_cost: Spillage cost [e/(m3/s)]
        :param inflow: Inflow from the rain [m3/s]
        :param inflow_prof: Profile for the inflow [m3/s]
        :param bus: electrical bus they are linked with
        :param build_status
        """
        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=DeviceType.FluidNodeDevice)

        self.min_level = min_level  # hm3
        self.max_level = max_level  # hm3
        self.initial_level = current_level  # hm3
        self.spillage_cost = spillage_cost  # m3/s
        self.inflow = inflow  # m3/s
        self._bus: Bus = bus
        self.build_status = build_status

        self.inflow_prof = inflow_prof  # m3/s
        self.spillage_cost_prof = spillage_cost_prof  # e/(m3/s)

        # list of turbines
        self.turbines = list()

        # list of pumps
        self.pumps = list()

        # list of power to gas devices
        self.p2xs = list()

        self.register(key='min_level', units='hm3', tpe=float,
                      definition="Minimum amount of fluid at the node/reservoir")

        self.register(key='max_level', units='hm3', tpe=float,
                      definition="Maximum amount of fluid at the node/reservoir")

        self.register(key='initial_level', units='hm3', tpe=float,
                      definition="Initial level of the node/reservoir")

        self.register(key='bus', units='', tpe=DeviceType.BusDevice,
                      definition='Electrical bus.', editable=False)

        self.register(key='build_status', units='', tpe=BuildStatus,
                      definition='Branch build status. Used in expansion planning.')

        self.register(key='spillage_cost', units='e/(m3/s)', tpe=float,
                      definition='Cost of nodal spillage',
                      profile_name='spillage_cost_prof')

        self.register(key='inflow', units='m3/s', tpe=float,
                      definition='Flow of fluid coming from the rain',
                      profile_name='inflow_prof')

    def copy(self):
        """
        Make a deep copy of this object
        :return: Copy of this object
        """

        # make a new instance (separated object in memory)
        fluid_node = FluidNode()

        fluid_node.min_level = self.min_level  # hm3
        fluid_node.max_level = self.max_level  # hm3
        fluid_node.initial_level = self.initial_level  # hm3
        fluid_node.spillage_cost = self.spillage_cost  # m3/s
        fluid_node.inflow = self.inflow  # m3/s
        fluid_node._bus = self._bus
        fluid_node.build_status = self.build_status

        fluid_node.inflow_prof = self.inflow_prof  # m3/s
        fluid_node.spillage_cost_prof = self.spillage_cost_prof  # e/(m3/s)

        # list of turbines
        fluid_node.turbines = self.turbines.copy()

        # list of pumps
        fluid_node.pumps = self.pumps.copy()

        # list of power to gas devices
        fluid_node.p2xs = self.p2xs.copy()

        return fluid_node

    @property
    def bus(self) -> Bus:
        """
        Bus getter function
        :return: Bus
        """
        return self._bus

    @bus.setter
    def bus(self, val: Bus):
        """
        bus setter function
        :param val: Bus
        """
        if isinstance(val, Bus):
            self._bus = val
            self._bus.is_internal = True

    def add_turbine(self, elm):
        """
        Add turbine
        :param elm: FluidTurbine
        """
        self.turbines.append(elm)

    def add_pump(self, elm):
        """
        Add pump device
        :param elm: FluidPump device
        """
        self.pumps.append(elm)

    def add_p2x(self, elm):
        """
        Add power to gas
        :param elm: FluidP2x device
        """
        self.p2xs.append(elm)

    def add_device(self, device) -> None:
        """
        Add device to the bus in the corresponding list
        :param device: FluidTurbine, FluidPump or FluidP2X
        """
        if device.device_type == DeviceType.FluidTurbineDevice:
            self.add_turbine(device)

        elif device.device_type == DeviceType.FluidPumpDevice:
            self.add_pump(device)

        elif device.device_type == DeviceType.FluidP2XDevice:
            self.add_p2x(device)

        else:
            raise Exception('Fluid Device type not understood:' + str(device.device_type))

    def get_device_number(self) -> int:
        """
        Get number of injection devices
        :return: int
        """
        return len(self.turbines) + len(self.pumps) + len(self.p2xs)

    def create_profiles(self, index):
        """
        Format all profiles
        """

        # create the profiles of this very object
        super().create_profiles(index)

        for elm in self.turbines:
            elm.create_profiles(index)

        for elm in self.pumps:
            elm.create_profiles(index)

        for elm in self.p2xs:
            elm.create_profiles(index)
