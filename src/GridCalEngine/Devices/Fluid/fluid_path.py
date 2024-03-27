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
import numpy as np
from typing import Union
from GridCalEngine.Devices.Parents.editable_device import EditableDevice
from GridCalEngine.enumerations import DeviceType, SubObjectType
from GridCalEngine.Devices.Fluid.fluid_node import FluidNode
from GridCalEngine.Devices.Branches.line_locations import LineLocations


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
        :param source: source of fluid (direction matters)
        :param target: target for the fluid (direction matters)
        :param min_flow: minimum flow (m3/s)
        :param max_flow: maximum flow (m3/s)
        """
        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=DeviceType.FluidPathDevice)

        self.source = source
        self.target = target
        self.min_flow = min_flow
        self.max_flow = max_flow

        # Line locations
        self._locations: LineLocations = LineLocations()

        self.register(key='source', units="", tpe=DeviceType.FluidNodeDevice, definition="Source node")
        self.register(key='target', units="", tpe=DeviceType.FluidNodeDevice, definition="Target node")
        self.register(key='min_flow', units="m3/s", tpe=float, definition="Minimum flow")
        self.register(key='max_flow', units="m3/s", tpe=float, definition="Maximum flow")
        self.register(key='locations', units='', tpe=SubObjectType.LineLocations, definition='Locations', editable=False)

    def copy(self):
        """
        Make a deep copy of this object
        :return: Copy of this object
        """

        # make a new instance (separated object in memory)
        fluid_path = FluidPath()

        fluid_path.source = self.source
        fluid_path.target = self.target
        fluid_path.min_flow = self.min_flow
        fluid_path.max_flow = self.max_flow

        return fluid_path

    @property
    def locations(self) -> LineLocations:
        """
        Cost profile
        :return: Profile
        """
        return self._locations

    @locations.setter
    def locations(self, val: Union[LineLocations, np.ndarray]):
        if isinstance(val, LineLocations):
            self._locations = val
        elif isinstance(val, np.ndarray):
            self._locations.set(data=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a locations')
