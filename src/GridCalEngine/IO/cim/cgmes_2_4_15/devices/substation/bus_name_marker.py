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
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class BusNameMarker(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.priority: int = 0

        self.register_property(name='priority',
                               class_type=int,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="Priority of bus name marker for use as "
                                           "topology bus name. Use 0 for don t care. Use "
                                           "1 for highest priority. Use 2 as priority is "
                                           "less than 1 and so on.",
                               profiles=[cgmesProfile.EQ])
