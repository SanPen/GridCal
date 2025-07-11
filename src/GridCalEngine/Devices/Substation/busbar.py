# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from typing import Union
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Devices.Parents.physical_device import PhysicalDevice
from GridCalEngine.Devices.Substation.bus import Bus


class BusBar(PhysicalDevice):
    __slots__ = (
        'voltage_level',
        '_bus',
    )

    def __init__(self,
                 name='BusBar',
                 idtag: Union[None, str] = None,
                 code: str = '',
                 bus: Union[None, Bus] = None) -> None:
        """
        Constructor
        :param name: Name of the bus bar
        :param idtag: unique identifier of the device
        :param code: secondary identifier
        :param bus: internal Connectivity node, if none a new one is created
        """
        PhysicalDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=DeviceType.BusBarDevice)

        self._bus: Bus = bus if bus is not None else Bus(name=name, is_internal=True)
        self._bus.internal = True  # always

        self.register(key="bus", tpe=DeviceType.BusDevice,
                      definition="Internal connectivity node")

    @property
    def bus(self) -> Bus:
        """
        Connectivity node getter
        :return: ConnectivityNode
        """
        return self._bus

    @bus.setter
    def bus(self, val: Bus):
        """
        Connectivity node setter
        :param val: ConnectivityNode
        """
        if isinstance(val, Bus):
            self._bus: Bus = val
        else:
            raise ValueError("Must be a Bus object")
