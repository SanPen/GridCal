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
from GridCalEngine.Devices.Aggregation.modelling_authority import ModellingAuthority
from GridCalEngine.enumerations import DeviceType


class PhysicalDevice(EditableDevice):
    """
    Parent class for Injections, Branches, Buses and other physical devices
    """

    def __init__(self,
                 name: str,
                 idtag: Union[str, None],
                 code: str,
                 device_type: DeviceType):
        """
        PhysicalDevice
        :param name: Name of the device
        :param idtag: unique id of the device (if None or "" a new one is generated)
        :param code: secondary code for compatibility
        :param device_type: DeviceType
        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=device_type)

        self.modelling_authority: Union[ModellingAuthority, None] = None

        self.register(key='modelling_authority', units='', tpe=DeviceType.ModellingAuthority,
                      definition='Modelling authority of this asset')
