# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from typing import Union
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Devices.Parents.physical_device import PhysicalDevice
from GridCalEngine.Devices.Substation.voltage_level import VoltageLevel
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode


class BusBar(PhysicalDevice):

    def __init__(self,
                 name='BusBar',
                 idtag: Union[None, str] = None,
                 code: str = '',
                 voltage_level: Union[None, VoltageLevel] = None,
                 cn: Union[None, ConnectivityNode] = None) -> None:
        """
        Constructor
        :param name: Name of the bus bar
        :param idtag: unique identifier of the device
        :param code: secondary identifier
        :param voltage_level: VoltageLevel of this bus bar (optional)
        :param cn: internal Connectivity node, if none a new one is created
        """
        PhysicalDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=DeviceType.BusBarDevice)

        self.voltage_level: Union[None, VoltageLevel] = voltage_level

        self._cn: ConnectivityNode = cn if cn is not None else ConnectivityNode(name=name,
                                                                                voltage_level=voltage_level,
                                                                                internal=True)
        self._cn.internal = True  # always

        self.register(key="voltage_level", tpe=DeviceType.VoltageLevelDevice,
                      definition="Substation voltage level (optional)")

        self.register(key="cn", tpe=DeviceType.ConnectivityNodeDevice,
                      definition="Internal connectivity node")

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
