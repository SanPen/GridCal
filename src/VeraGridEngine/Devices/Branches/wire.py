# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice, DeviceType


class Wire(EditableDevice):
    """
    This class represents a wire (an actual wire)
    to compose towers
    """
    __slots__ = (
        '_stranding',
        '_material',
        '_diameter',
        '_diameter_internal',
        '_is_tube',
        '_R',
        '_max_current',
    )

    def __init__(self, name='',
                 idtag: Union[str, None] = None,
                 r: float = 0.01,
                 max_current: float = 1.0,
                 stranding: str = "",
                 material: str = "",
                 diameter: float = 0.0,
                 diameter_internal: float = 0.0,
                 is_tube: bool = False,
                 code: str = ""):
        """
        Wire definition
        :param name: Name of the wire type
        :param r: Resistance per unit length (Ohm / km)
        :param max_current: Maximum current of the conductor in (kA)
        :param stranding: Stranding of the wire type
        :param material: Material of the wire type
        :param diameter: Diameter of the wire type (mm)
        :param diameter_internal: Internal diameter (in case of tubular conductor) (mm)
        :param is_tube: Whether the wire is a tubular conductor
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
        self._diameter = float(diameter)
        self._diameter_internal = float(diameter_internal)
        self._is_tube = bool(is_tube)
        self._R = float(r)
        self._max_current = float(max_current)

        self.register(key='R', units='Ohm/km', tpe=float, definition='resistance of the conductor', old_names=['r'])
        self.register(key='diameter', units='mm', tpe=float, definition='Diameter of wire', old_names=['GMR', 'gmr'])
        self.register(key='diameter_internal', units='mm', tpe=float, definition='Internal radius of the conductor')
        self.register(key='is_tube', units='', tpe=bool, definition='Is it a tubular conductor?')
        self.register(key='max_current', units='kA', tpe=float, definition='Maximum current of the conductor')
        self.register(key='stranding', tpe=str, definition='Stranding of wire')
        self.register(key='material', tpe=str, definition='Material of wire')

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

    @property
    def diameter(self) -> float:
        return self._diameter

    @diameter.setter
    def diameter(self, value: float) -> None:
        self._diameter = float(value)

    @property
    def diameter_internal(self) -> float:
        return self._diameter_internal

    @diameter_internal.setter
    def diameter_internal(self, value: float) -> None:
        self._diameter_internal = float(value)

    @property
    def is_tube(self) -> bool:
        return self._is_tube

    @is_tube.setter
    def is_tube(self, value: bool) -> None:
        self._is_tube = bool(value)

    @property
    def R(self) -> float:
        return self._R

    @R.setter
    def R(self, value: float) -> None:
        self._R = float(value)

    @property
    def max_current(self) -> float:
        return self._max_current

    @max_current.setter
    def max_current(self, value: float) -> None:
        self._max_current = float(value)
