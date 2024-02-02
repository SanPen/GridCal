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
from GridCalEngine.Core.Devices.Substation.substation import Substation
from GridCalEngine.Core.Devices.Substation.connectivity_node import ConnectivityNode


class BusBar(EditableDevice):

    def __init__(self, name='BusBar', idtag: Union[None, str] = None, code: str = '',
                 substation: Union[None, Substation] = None,
                 cn: Union[None, ConnectivityNode] = None) -> None:
        """
        Constructor
        :param name: Name of the bus bar
        :param idtag: unique identifier of the device
        :param code: secondary identifyer
        :param substation: Substation of this bus bar (optional)
        :param cn: internal Connectivity node, if none a new one is created
        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=DeviceType.BusBarDevice)

        self.substation: Union[None, Substation] = substation

        self._cn: ConnectivityNode = cn if cn is not None else ConnectivityNode(name=name)

        self.register("substation", "", DeviceType.SubstationDevice,
                      "Substation of this bus bar (optional)")

        self.register("cn", "", DeviceType.ConnectivityNodeDevice,
                      "Internal connectvity node")

    @property
    def cn(self) -> ConnectivityNode:
        """
        Connectivity node getter
        :return: ConnectivityNode
        """
        return self._cn

    @cn.setter
    def cn(self, val: ConnectivityNode):
        """
        Connectivity node setter
        :param val: ConnectivityNode
        """
        self._cn: ConnectivityNode = val
