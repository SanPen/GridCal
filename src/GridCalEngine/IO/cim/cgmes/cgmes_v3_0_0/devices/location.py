# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType


class Location(IdentifiedObject):
	def __init__(self, rdfid='', tpe='Location'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.coordinate_system import CoordinateSystem
		self.CoordinateSystem: CoordinateSystem | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_system_resource import PowerSystemResource
		self.PowerSystemResources: PowerSystemResource | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.position_point import PositionPoint
		self.PositionPoints: PositionPoint | None = None

		self.register_property(
			name='CoordinateSystem',
			class_type=CoordinateSystem,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Coordinate system used to describe position points of this location.''',
			profiles=[]
		)
		self.register_property(
			name='PowerSystemResources',
			class_type=PowerSystemResource,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''All power system resources at this location.''',
			profiles=[]
		)
		self.register_property(
			name='PositionPoints',
			class_type=PositionPoint,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Sequence of position points describing this location, expressed in coordinate system 'Location.CoordinateSystem'.''',
			profiles=[]
		)
