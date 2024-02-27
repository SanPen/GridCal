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
from GridCalEngine.Devices.Fluid.fluid_node import FluidNode
from GridCalEngine.Devices.Fluid.fluid_injection_template import FluidInjectionTemplate
from GridCalEngine.Devices.Injections.generator import Generator
from GridCalEngine.enumerations import BuildStatus, DeviceType


class FluidTurbine(FluidInjectionTemplate):

    def __init__(self,
                 name: str = '',
                 idtag: Union[str, None] = None,
                 code: str = '',
                 efficiency: float = 1.0,
                 max_flow_rate: float = 0.0,
                 plant: FluidNode = None,
                 generator: Generator = None):
        """
        Fluid turbine
        :param name: name
        :param idtag: UUID code
        :param code: secondary code
        :param efficiency: energy consumption per fluid unit (MWh/m3)
        :param max_flow_rate: maximum fluid flow (m3/s)
        :param plant: Connection reservoir/node
        :param generator: electrical machine connected
        """
        FluidInjectionTemplate.__init__(self,
                                        name=name,
                                        idtag=idtag,
                                        code=code,
                                        efficiency=efficiency,
                                        max_flow_rate=max_flow_rate,
                                        plant=plant,
                                        generator=generator,
                                        device_type=DeviceType.FluidTurbineDevice)
