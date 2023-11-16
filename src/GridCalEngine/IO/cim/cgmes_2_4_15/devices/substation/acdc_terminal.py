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
import GridCalEngine.IO.cim.cgmes_2_4_15.devices.aggregation.operational_limit_set
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.bus_name_marker import BusNameMarker
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class ACDCTerminal(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.connected: bool = True
        self.BusNameMarker: BusNameMarker | None = None
        # self.Measurements = Measurements
        self.sequenceNumber = 0

        # keep long import because it avoids a CIM circular reference :(
        self.OperationalLimitSet: GridCalEngine.IO.cim.cgmes_2_4_15.devices.aggregation.operational_limit_set.OperationalLimitSet = None

        self.register_property(name='connected',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               profiles=[cgmesProfile.SSH])

        self.register_property(name='BusNameMarker',
                               class_type=BusNameMarker,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               comment="No explanation given by the standard",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='sequenceNumber',
                               class_type=int,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='OperationalLimitSet',
                               class_type=GridCalEngine.IO.cim.cgmes_2_4_15.devices.aggregation.operational_limit_set.OperationalLimitSet,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="OperationalLimitSet",
                               profiles=[cgmesProfile.EQ])
