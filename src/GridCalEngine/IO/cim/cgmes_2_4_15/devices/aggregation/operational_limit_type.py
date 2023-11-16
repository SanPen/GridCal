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
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import LimitTypeKind, OperationalLimitDirectionKind, cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class OperationalLimitType(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.limitType: LimitTypeKind = LimitTypeKind.patl
        self.direction: OperationalLimitDirectionKind = OperationalLimitDirectionKind.absoluteValue
        self.acceptableDuration: float = 0.0

        self.register_property(name='limitType',
                               class_type=LimitTypeKind,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="Types of limits defined in the ENTSO-E "
                                           "Operational Handbook Policy 3.",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='direction',
                               class_type=OperationalLimitDirectionKind,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The direction of the limit.",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='acceptableDuration',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.s,
                               description="The nominal acceptable duration of "
                                           "the limit. Limits are commonly "
                                           "expressed in terms of the a time "
                                           "limit for which the limit is "
                                           "normally acceptable. The actual "
                                           "acceptable duration of a specific "
                                           "limit may depend on other local "
                                           "factors such as temperature or "
                                           "wind speed.",
                               profiles=[cgmesProfile.EQ])
