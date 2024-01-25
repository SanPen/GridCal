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
from GridCalEngine.Core.Devices.editable_device import EditableDevice, DeviceType
from GridCalEngine.Core.Devices.Substation.busbar import BusBar


class ConnectivityNode(EditableDevice):

    def __init__(self, name='CN', idtag=None, code='', dc: bool = False,
                 bus_bar: Union[None, BusBar] = None):
        """
        Constructor
        :param name: Name of the connectivity node
        :param idtag: unique identifier
        :param code: secondary identifyier
        :param dc: is this a DC connectivity node?
        :param bus_bar: Associated bus bar
        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=DeviceType.ConnectivityNodeDevice)

        self.dc = dc

        self.bus_bar = bus_bar

        self.register("dc", "", bool, "is this a DC connectivity node?")
        self.register("bus_bar", "", DeviceType.BusBarDevice, "Associated bus bar")

