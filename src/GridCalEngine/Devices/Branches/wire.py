# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

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
        self.diameter = float(diameter)
        self.R = float(r)
        self.X = float(x)
        self.GMR = float(gmr)
        self.max_current = float(max_current)

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
