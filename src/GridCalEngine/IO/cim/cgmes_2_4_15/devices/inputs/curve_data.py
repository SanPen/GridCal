# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.base import Base
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.inputs.curve import Curve
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class CurveData(Base):

    def __init__(self, rdfid, tpe, resources=list(), class_replacements=dict()):
        """
        General CIM object container
        :param rdfid: RFID
        :param tpe: type of the object (class)
        """
        Base.__init__(self, rdfid='', tpe=tpe, resources=resources, class_replacements=class_replacements)

        self.Curve: Curve = None
        self.xvalue: float = 0.0
        self.y1value: float = 0.0
        self.y2value: float = 0.0

        self.register_property(name='Curve',
                               class_type=Curve,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The point data values that define this curve.",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='xvalue',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The data value of the X-axis variable,  depending on the X-axis units.",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='y1value',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The data value of the first Y-axis variable, "
                                           "depending on the Y-axis units.",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='y2value',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The data value of the second Y-axis variable (if present), "
                                           "depending on the Y-axis units.",
                               profiles=[cgmesProfile.EQ])
