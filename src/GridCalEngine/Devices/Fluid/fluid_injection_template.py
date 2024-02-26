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
from GridCalEngine.Devices.Parents.editable_device import EditableDevice
from GridCalEngine.Devices.Fluid.fluid_node import FluidNode
from GridCalEngine.Devices.Injections.generator import Generator
from GridCalEngine.enumerations import BuildStatus, DeviceType


class FluidInjectionTemplate(EditableDevice):

    def __init__(self,
                 name: str = '',
                 idtag: Union[str, None] = None,
                 code: str = '',
                 efficiency: float = 1.0,
                 max_flow_rate: float = 0.0,
                 plant: FluidNode = None,
                 generator: Generator = None,
                 device_type: DeviceType = DeviceType.FluidTurbineDevice,
                 build_status: BuildStatus = BuildStatus.Commissioned):
        """
        Fluid turbine
        :param name: name
        :param idtag: UUID code
        :param code: secondary code
        :param efficiency: energy consumption per fluid unit (MWh/m3)
        :param max_flow_rate: maximum fluid flow (m3/s)
        :param plant: Connection reservoir/node
        :param generator: electrical machine connected
        :param device_type: type of machine (turbine, pump, p2x)
        :param build_status: status if the plant is built, planned, etc.
        """
        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=device_type)

        self.efficiency = efficiency  # MWh/m3
        self.max_flow_rate = max_flow_rate  # m3/s
        self._plant: FluidNode = plant
        self._generator: Generator = generator
        self.build_status = build_status

        self.register(key='efficiency', units="MWh/m3", tpe=float,
                      definition="Power plant energy production per fluid unit")
        self.register(key='max_flow_rate', units="m3/s", tpe=float, definition="maximum fluid flow")
        self.register(key='plant', units="", tpe=DeviceType.FluidNodeDevice, definition="Connection reservoir/node",
                      editable=False)
        self.register(key='generator', units="", tpe=DeviceType.GeneratorDevice, definition="Electrical machine",
                      editable=False)
        self.register(key='build_status', units='', tpe=BuildStatus,
                      definition='Branch build status. Used in expansion planning.')

    @property
    def plant(self) -> FluidNode:
        """
        Plant getter
        :return: FluidNode
        """
        return self._plant

    @plant.setter
    def plant(self, val: FluidNode):
        """

        :param val: FluidNode
        :return:
        """
        if isinstance(val, FluidNode):
            self._plant = val

    @property
    def generator(self) -> Generator:
        """
        Generator getter
        :return: Generator
        """
        return self._generator

    @generator.setter
    def generator(self, val: Generator):
        """
        generator setter
        :param val: Generator
        """
        if isinstance(val, Generator):
            self._generator = val
