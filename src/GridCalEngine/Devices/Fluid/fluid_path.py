# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import numpy as np
from typing import Union, TYPE_CHECKING, Tuple
from GridCalEngine.Devices.Parents.physical_device import PhysicalDevice
from GridCalEngine.enumerations import DeviceType, SubObjectType
from GridCalEngine.Devices.Fluid.fluid_node import FluidNode
from GridCalEngine.Devices.Branches.line_locations import LineLocations
from GridCalEngine.basic_structures import Logger

if TYPE_CHECKING:
    from GridCalEngine.Devices.types import CONNECTION_TYPE


class FluidPath(PhysicalDevice):

    def __init__(self,
                 name: str = '',
                 idtag: Union[str, None] = None,
                 code: str = '',
                 source: FluidNode = None,
                 target: FluidNode = None,
                 min_flow: float = 0.0,
                 max_flow: float = 0.0,
                 color: str | None = None):
        """
        Fluid path
        :param name:Name of the fluid transporter
        :param idtag: UUID
        :param code: secondary ID
        :param source: source of fluid (direction matters)
        :param target: target for the fluid (direction matters)
        :param min_flow: minimum flow (m3/s)
        :param max_flow: maximum flow (m3/s)
        :param color: color of the fluid
        """
        PhysicalDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=DeviceType.FluidPathDevice)

        self.source = source
        self.target = target
        self.min_flow = float(min_flow)
        self.max_flow = float(max_flow)

        self.color = color if color is not None else "#00aad4"  # nice blue color

        # Line locations
        self._locations: LineLocations = LineLocations()

        self.register(key='source', units="", tpe=DeviceType.FluidNodeDevice, definition="Source node")
        self.register(key='target', units="", tpe=DeviceType.FluidNodeDevice, definition="Target node")
        self.register(key='min_flow', units="m3/s", tpe=float, definition="Minimum flow")
        self.register(key='max_flow', units="m3/s", tpe=float, definition="Maximum flow")
        self.register(key='locations', units='', tpe=SubObjectType.LineLocations, definition='Locations', editable=False)
        self.register(key='color', units='', tpe=str, definition='Color to paint the device in the map diagram')

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

    def get_from_and_to_objects(self,
                                t_idx: Union[int, None] = None,
                                logger: Logger = Logger(),
                                prefer_node_breaker: bool = True) -> Tuple[CONNECTION_TYPE, CONNECTION_TYPE, bool]:
        """
        Get the from and to connection objects of the branch
        :param t_idx: Time index (optional)
        :param logger: Logger object
        :param prefer_node_breaker: If true the connectivity nodes are examined first,
                                    otherwise the buses are returned right away
        :return: Object from, Object to, is it ok?
        """

        # Pick the right bus
        bus_from = self.source
        bus_to = self.target

        ok = bus_from is not None and bus_to is not None
        return bus_from, bus_to, ok
