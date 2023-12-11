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
                 spillage: float = 0.0,
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
        :param spillage: Spillage value [m3/h]
        :param bus: electrical bus they are linked with
        :param build_status
        """
        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=DeviceType.FluidNodeDevice)

        self.min_level = min_level  # m3
        self.max_level = max_level  # m3
        self.initial_level = current_level  # m3
        self._bus: Bus = bus
        self.build_status = build_status

        # self.current_level = current_level  # m3 -> LpVar
        # self.spillage = spillage  # m3/h -> LpVar
        # self.inflow = 0.0  # m3/h -> LpExpression
        # self.outflow = 0.0  # m3/h -> LpExpression

        # list of turbines
        self.turbines = list()

        # list of pumps
        self.pumps = list()

        # list of power to gas devices
        self.p2xs = list()

        self.register(key='min_level', units='m3', tpe=float,
                      definition="Minimum amount of fluid at the node/reservoir")

        self.register(key='max_level', units='m3', tpe=float,
                      definition="Maximum amount of fluid at the node/reservoir")

        self.register(key='initial_level', units='m3', tpe=float,
                      definition="Initial level of the node/reservoir")

        self.register(key='bus', units='', tpe=DeviceType.BusDevice,
                      definition='Electrical bus.', editable=False)

        self.register(key='build_status', units='', tpe=BuildStatus,
                      definition='Branch build status. Used in expansion planning.')

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
        if device.device_type == DeviceType.FluidTurbine:
            self.add_turbine(device)

        elif device.device_type == DeviceType.FluidPump:
            self.add_pump(device)

        elif device.device_type == DeviceType.FluidP2X:
            self.add_p2x(device)

        else:
            raise Exception('Fluid Device type not understood:' + str(device.device_type))
