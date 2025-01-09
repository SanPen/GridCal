# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union

from GridCalEngine.Devices.Substation.voltage_level import VoltageLevel
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Parents.physical_device import PhysicalDevice
from GridCalEngine.enumerations import DeviceType


class ConnectivityNode(PhysicalDevice):

    def __init__(self, name='CN',
                 idtag=None,
                 code='',
                 dc: bool = False,
                 default_bus: Union[None, Bus] = None,
                 voltage_level: Union[VoltageLevel, None] = None,
                 internal: bool = False,
                 Vnom: float = 10.0):
        """
        Constructor
        :param name: Name of the connectivity node
        :param idtag: unique identifier
        :param code: secondary identifier
        :param dc: is this a DC connectivity node?
        :param default_bus: Default bus to use for topology processing (optional)
        :param voltage_level: Substation of this connectivity node (optional)
        :param internal: Is internal?
        :param Vnom: Nominal voltage in kV
        """
        PhysicalDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=DeviceType.ConnectivityNodeDevice)

        self.dc = bool(dc)

        self._bus: Bus = default_bus if default_bus is not None else Bus(name=name,
                                                                        Vnom=Vnom,
                                                                        voltage_level=voltage_level, )

        self._voltage_level: Union[VoltageLevel, None] = voltage_level

        self._internal: bool = bool(internal)

        self.Vnom = float(Vnom) if voltage_level is None else voltage_level.Vnom

        self.register(key='Vnom', units='kV', tpe=float, definition='Nominal line voltage of the cn.')

        self.register(key="dc", tpe=bool, definition="is this a DC connectivity node?")

        self.register(key="internal", tpe=bool, definition="is internal of a busbar?")

        self.register(key="bus", tpe=DeviceType.BusDevice,
                      definition="The CN is just a bus by other means. This is the important thing.",
                      old_names=['default_bus'])

        self.register(key="voltage_level", tpe=DeviceType.VoltageLevelDevice,
                      definition="Voltage level of this connectivity node (optional)")

    @property
    def bus(self) -> Bus:
        """
        Bus internal to the CN
        :return: Bus
        """
        return self._bus

    @bus.setter
    def bus(self, val: Bus):
        if isinstance(val, Bus):
            self._bus = val
        else:
            raise Exception("You cannot set a connectivity node bus to anything other than a valid Bus object :/")

    @property
    def voltage_level(self) -> Union[VoltageLevel, None]:
        """
        The voltage level of this connectivity node
        :return: Voltage level
        """
        return self._voltage_level

    @voltage_level.setter
    def voltage_level(self, val: Union[VoltageLevel, None]):
        self._voltage_level = val

        if val is not None:
            self.Vnom = val.Vnom

    @property
    def internal(self):
        return self._internal

    @internal.setter
    def internal(self, val: bool):
        self._internal = val

        if self.auto_update_enabled:
            self.bus.internal = val
