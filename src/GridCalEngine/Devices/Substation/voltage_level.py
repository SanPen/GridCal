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
from GridCalEngine.Devices.Parents.editable_device import DeviceType
from GridCalEngine.Devices.Parents.editable_device import EditableDevice
from GridCalEngine.Devices.Substation.substation import Substation


class VoltageLevel(EditableDevice):

    def __init__(self, name='VoltageLevel', idtag: Union[str, None] = None, code: str = '',
                 Vnom: float = 1.0, substation: Union[None, Substation] = None):
        """
        Constructor
        :param name: Name
        :param idtag: UUID
        :param code: secondary ID
        :param Vnom: Nominal voltage in kV
        :param substation: Substation object (optional)
        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=DeviceType.VoltageLevelDevice)

        self.Vnom = Vnom

        self.substation: Union[None, Substation] = substation

        self.register(key='Vnom', units='kV', tpe=float, definition='Nominal voltage')

        self.register(key="substation", tpe=DeviceType.SubstationDevice,
                      definition="Substation of this Voltage level (optional)")
