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
from GridCalEngine.Core.Devices.Fluid.fluid_node import FluidNode
from GridCalEngine.enumerations import BuildStatus, DeviceType
from GridCalEngine.basic_structures import Vec


class FluidTurbine(EditableDevice):

    def __init__(self,
                 name: str = '',
                 idtag: Union[str, None] = None,
                 code: str = '',
                 Pmin: float = 0.0,
                 Pmax: float = 0.0,
                 efficiency: float = 1.0,
                 max_flow_rate: float = 0.0,
                 plant: FluidNode = None):
        """
        Fluid turbine
        :param name: name
        :param idtag: UUID code
        :param code: secondary code
        :param Pmin: Minimum power (MW)
        :param Pmax: Maximum power (MW)
        :param efficiency: energy consumption per fluid unit (MWh/m3)
        :param max_flow_rate: maximum fluid flow (m3/h)
        :param plant: Connection reservoir/node
        """
        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=DeviceType.FluidTurbine)

        self.p_min = Pmin  # MW
        self.p_max = Pmax  # MW
        self.efficiency = efficiency  # MWh/m3
        self.max_flow_rate = max_flow_rate  # m3/h
        self.plant: FluidNode = plant

        self.register(key='p_min', units="MW", tpe=float, definition="Minimum power")
        self.register(key='p_max', units="MW", tpe=float, definition="Maximum power")
        self.register(key='efficiency', units="MWh/m3", tpe=float,
                      definition="Power plant energy production per fluid unit")
        self.register(key='max_flow_rate', units="m3/h", tpe=float, definition="maximum fluid flow")
        self.register(key='plant', units="", tpe=FluidNode, definition="Connection reservoir/node")
