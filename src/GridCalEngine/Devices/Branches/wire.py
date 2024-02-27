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
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType


class Wire(EditableDevice):
    """
    This class represents a wire (an actual wire)
    to compose towers
    """
    def __init__(self, name='', idtag: Union[str, None] = None, gmr=0.01, r=0.01, x=0.0, max_current=1):
        """
        Wire definition
        :param name: Name of the wire type
        :param gmr: Geometric Mean Radius (m)
        :param r: Resistance per unit length (Ohm / km)
        :param x: Reactance per unit length (Ohm / km)
        :param max_current: Maximum current of the conductor in (kA)

        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code='',
                                device_type=DeviceType.WireDevice)

        # self.wire_name = name
        self.r = r
        self.x = x
        self.gmr = gmr
        self.max_current = max_current

        self.register(key='r', units='Ohm/km', tpe=float, definition='resistance of the conductor')
        self.register(key='x', units='Ohm/km', tpe=float, definition='reactance of the conductor')
        self.register(key='gmr', units='m', tpe=float, definition='Geometric Mean Radius of the conductor')
        self.register(key='max_current', units='kA', tpe=float, definition='Maximum current of the conductor')

    def copy(self):
        """
        Copy of the wire
        :return:
        """
        # name='', idtag=None, gmr=0.01, r=0.01, x=0.0, max_current=1
        return Wire(name=self.name, gmr=self.gmr, r=self.r, x=self.x, max_current=self.max_current)
