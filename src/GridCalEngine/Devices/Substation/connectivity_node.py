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

from GridCalEngine.Devices.Substation.voltage_level import VoltageLevel
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType


class ConnectivityNode(EditableDevice):

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
        :param code: secondary identifyier
        :param dc: is this a DC connectivity node?
        :param default_bus: Default bus to use for topology processing (optional)
        :param voltage_level: Substation of this connectivity node (optional)
        :param internal: Is internal?
        :param Vnom: Nominal voltage in kV
        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=DeviceType.ConnectivityNodeDevice)

        self.dc = dc

        self.default_bus: Union[None, Bus] = default_bus

        self._voltage_level: Union[VoltageLevel, None] = voltage_level

        self.internal: bool = internal

        self.Vnom = Vnom if voltage_level is None else voltage_level.Vnom

        self.register(key='Vnom', units='kV', tpe=float, definition='Nominal line voltage of the cn.')

        self.register(key="dc", tpe=bool, definition="is this a DC connectivity node?")

        self.register(key="internal", tpe=bool, definition="is internal of a busbar?")

        self.register(key="default_bus", tpe=DeviceType.BusDevice,
                      definition="Default bus to use for topology processing (optional)")

        self.register(key="voltage_level", tpe=DeviceType.VoltageLevelDevice,
                      definition="Voltage level of this connectivity node (optional)")

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
