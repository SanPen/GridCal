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
    def __init__(self, name='', idtag: Union[str, None] = None,
                 gmr: float = 0.01, r: float = 0.01, x: float = 0.0,
                 max_current: float = 1.0,
                 stranding: str = "",
                 material: str = "",
                 diameter: float = 0.0,
                 code: str = ""):
        """
        Wire definition
        :param name: Name of the wire type
        :param gmr: Geometric Mean Radius (m)
        :param r: Resistance per unit length (Ohm / km)
        :param x: Reactance per unit length (Ohm / km)
        :param max_current: Maximum current of the conductor in (kA)
        :param stranding: Stranding of the wire type
        :param material: Material of the wire type
        :param diameter: Diameter of the wire type
        :param code: Code of the wire type
        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=DeviceType.WireDevice)

        # self.wire_name = name
        self._stranding = str(stranding)
        self._material = str(material)
        self.diameter = diameter
        self.R = r
        self.X = x
        self.GMR = gmr
        self.max_current = max_current

        self.register(key='R', units='Ohm/km', tpe=float, definition='resistance of the conductor', old_names=['r'])
        self.register(key='X', units='Ohm/km', tpe=float, definition='reactance of the conductor', old_names=['x'])
        self.register(key='GMR', units='m', tpe=float, definition='Geometric Mean Radius of the conductor', old_names=['gmr'])
        self.register(key='max_current', units='kA', tpe=float, definition='Maximum current of the conductor')
        self.register(key='stranding', tpe=str, definition='Stranding of wire')
        self.register(key='material', tpe=str, definition='Material of wire')
        self.register(key='diameter', units='cm', tpe=float, definition='Diameter of wire')

    @property
    def stranding(self) -> str:
        """
        Stranding of wire
        :return:
        """
        return self._stranding

    @stranding.setter
    def stranding(self, value: str):
        self._stranding = str(value)

    @property
    def material(self) -> str:
        """
        Material of wire
        :return:
        """
        return self._material

    @material.setter
    def material(self, value: str):
        self._material = str(value)
