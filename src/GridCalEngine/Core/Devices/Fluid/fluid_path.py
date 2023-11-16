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
from GridCalEngine.enumerations import BuildStatus, DeviceType
from GridCalEngine.Core.Devices.Fluid.fluid_node import FluidNode
from GridCalEngine.basic_structures import Vec


class FluidPath(EditableDevice):

    def __init__(self,
                 name: str = '',
                 idtag: Union[str, None] = None,
                 code: str = '',
                 source: FluidNode = None,
                 target: FluidNode = None,
                 min_flow: float = 0.0,
                 max_flow: float = 0.0):
        """
        Fluid path
        :param name:Name of the fluid transporter
        :param idtag: UUID
        :param code: secondary ID
        :param source: Source of fluid
        :param target: target for the fluid
        :param min_flow: minimum flow (m3/h)
        :param max_flow: maximum flow (m3/h)
        """
        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=DeviceType.FluidPath)

        self.source = source
        self.target = target
        self.min_flow = min_flow
        self.max_flow = max_flow

        self.register(key='source', units="", tpe=FluidNode, definition="Source node")
        self.register(key='target', units="", tpe=FluidNode, definition="Target node")
        self.register(key='min_flow', units="m3/h", tpe=float, definition="Minimum power")
        self.register(key='max_flow', units="m3/h", tpe=float, definition="Maximum power")
