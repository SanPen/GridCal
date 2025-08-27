# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.IO.base.units import UnitMultiplier, UnitSymbol
from VeraGridEngine.IO.cim.cgmes.base import Base
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType


class PositionPoint(Base):
	def __init__(self, rdfid, tpe="PositionPoint", resources=list(), class_replacements=dict()):
		Base.__init__(self, rdfid=rdfid, tpe=tpe, resources=resources, class_replacements=class_replacements)

		from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.location import Location
		self.Location: Location | None = None
		self.sequenceNumber: int = None
		self.xPosition: str = None
		self.yPosition: str = None
		self.zPosition: str = None

		self.register_property(
			name='Location',
			class_type=Location,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Location described by this position point.''',
			profiles=[]
		)
		self.register_property(
			name='sequenceNumber',
			class_type=int,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Zero-relative sequence number of this point within a series of points.''',
			profiles=[]
		)
		self.register_property(
			name='xPosition',
			class_type=str,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''X axis position.''',
			profiles=[]
		)
		self.register_property(
			name='yPosition',
			class_type=str,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Y axis position.''',
			profiles=[]
		)
		self.register_property(
			name='zPosition',
			class_type=str,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''(if applicable) Z axis position.''',
			profiles=[]
		)
