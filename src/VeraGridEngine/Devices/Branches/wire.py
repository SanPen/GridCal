# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union, Tuple
import math
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice, DeviceType, GCProp
from VeraGridEngine.enumerations import PrpCat


def calc_GMR(is_tube: bool, r: float, q: float) -> float:
    """Geometric mean radius in metres, assuming uniform current density.

    :param is_tube: Whether the conductor is tubular.
    :param r: Outer radius in metres.
    :param q: Inner radius in metres (used only for tubes).
    """
    if is_tube:
        return r * math.exp((3 * q ** 2 - r ** 2) / (4 * (r ** 2 - q ** 2))
                            - q ** 4 / (r ** 2 - q ** 2) ** 2 * math.log(r / q))
    return r * math.exp(-0.25)


class Wire(EditableDevice):
    """
    This class represents a wire (an actual wire)
    to compose towers
    """
    __slots__ = (
        '_stranding',
        '_material',
        '_diameter',
        '_gmr',
        '_diameter_internal',
        '_is_tube',
        '_R',
        '_max_current',
    )

    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp(
            prop_name='R',
            units='Ohm/km',
            tpe=float,
            definition='resistance of the conductor',
            old_names=['r'],
            cat=[PrpCat.PF],
        ),
        GCProp(
            prop_name='diameter',
            units='mm',
            tpe=float,
            definition='Diameter of wire',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='gmr',
            units='mm',
            tpe=float,
            definition='Geometric mean radius in mm for series impedance. '
                       '0 = automatic from conductor geometry; positive = specified GMR. '
                       'The physical diameter still determines capacitance.',
            old_names=['gmr_mm'],
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='diameter_internal',
            units='mm',
            tpe=float,
            definition='Internal radius of the conductor',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='is_tube',
            units='',
            tpe=bool,
            definition='Is it a tubular conductor?',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='max_current',
            units='kA',
            tpe=float,
            definition='Maximum current of the conductor',
            cat=[PrpCat.PF],
        ),
        GCProp(
            prop_name='stranding',
            tpe=str,
            definition='Stranding of wire',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='material',
            tpe=str,
            definition='Material of wire',
            cat=[PrpCat.TP],
        ),
    )

    def __init__(self, name='',
                 idtag: Union[str, None] = None,
                 r: float = 0.01,
                 max_current: float = 1.0,
                 stranding: str = "",
                 material: str = "",
                 diameter: float = 1.0,
                 diameter_internal: float = 0.01,
                 is_tube: bool = False,
                 code: str = "",
                 gmr: float = 0.0):
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
        :param gmr: Specified GMR in mm; zero calculates it from conductor geometry.
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
        self.gmr = gmr
        self._diameter_internal = float(diameter_internal)
        self._is_tube = bool(is_tube)
        self._R = float(r)
        self._max_current = float(max_current)

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
    def gmr(self) -> float:
        """Specified GMR in mm, or zero for automatic calculation."""
        return self._gmr

    @gmr.setter
    def gmr(self, value: float) -> None:
        value = float(value)
        if not math.isfinite(value) or value < 0.0:
            raise ValueError('GMR must be finite and non-negative (0 = automatic).')
        self._gmr = value

    def get_gmr(self) -> float:
        """Return the effective GMR in metres, without changing the physical diameter."""
        if self.gmr > 0.0:
            return self.gmr / 1000.0
        return calc_GMR(self.is_tube, self.diameter / 2000.0, self.diameter_internal / 2000.0)

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
