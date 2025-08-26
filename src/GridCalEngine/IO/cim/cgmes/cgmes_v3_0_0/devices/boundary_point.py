# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_system_resource import PowerSystemResource
from GridCalEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType


class BoundaryPoint(PowerSystemResource):
	def __init__(self, rdfid='', tpe='BoundaryPoint'):
		PowerSystemResource.__init__(self, rdfid, tpe)

		self.fromEndIsoCode: str = None
		self.fromEndName: str = None
		self.fromEndNameTso: str = None
		self.toEndIsoCode: str = None
		self.toEndName: str = None
		self.toEndNameTso: str = None
		self.isDirectCurrent: bool = None
		self.isExcludedFromAreaInterchange: bool = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.connectivity_node import ConnectivityNode
		self.ConnectivityNode: ConnectivityNode | None = None

		self.register_property(
			name='fromEndIsoCode',
			class_type=str,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The ISO code of the region which the "From" side of the Boundary point belongs to or it is connected to.
The ISO code is a two-character country code as defined by ISO 3166 (http://www.iso.org/iso/country_codes). The length of the string is 2 characters maximum.''',
			profiles=[]
		)
		self.register_property(
			name='fromEndName',
			class_type=str,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A human readable name with length of the string 64 characters maximum. It covers the following two cases:
-if the Boundary point is placed on a tie-line, it is the name (IdentifiedObject.name) of the substation at which the "From" side of the tie-line is connected to.
-if the Boundary point is placed in a substation, it is the name (IdentifiedObject.name) of the element (e.g. PowerTransformer, ACLineSegment, Switch, etc.) at which the "From" side of the Boundary point is connected to.''',
			profiles=[]
		)
		self.register_property(
			name='fromEndNameTso',
			class_type=str,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Identifies the name of the transmission system operator, distribution system operator or other entity at which the "From" side of the interconnection is connected to. The length of the string is 64 characters maximum.''',
			profiles=[]
		)
		self.register_property(
			name='toEndIsoCode',
			class_type=str,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The ISO code of the region which the "To" side of the Boundary point belongs to or is connected to.
The ISO code is a two-character country code as defined by ISO 3166 (http://www.iso.org/iso/country_codes). The length of the string is 2 characters maximum.''',
			profiles=[]
		)
		self.register_property(
			name='toEndName',
			class_type=str,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A human readable name with length of the string 64 characters maximum. It covers the following two cases:
-if the Boundary point is placed on a tie-line, it is the name (IdentifiedObject.name) of the substation at which the "To" side of the tie-line is connected to.
-if the Boundary point is placed in a substation, it is the name (IdentifiedObject.name) of the element (e.g. PowerTransformer, ACLineSegment, Switch, etc.) at which the "To" side of the Boundary point is connected to.''',
			profiles=[]
		)
		self.register_property(
			name='toEndNameTso',
			class_type=str,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Identifies the name of the transmission system operator, distribution system operator or other entity at which the "To" side of the interconnection is connected to. The length of the string is 64 characters maximum.''',
			profiles=[]
		)
		self.register_property(
			name='isDirectCurrent',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''If true, this boundary point is a point of common coupling (PCC) of a direct current (DC) interconnection, otherwise the interconnection is AC (default).''',
			profiles=[]
		)
		self.register_property(
			name='isExcludedFromAreaInterchange',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''If true, this boundary point is on the interconnection that is excluded from control area interchange calculation and consequently has no related tie flows. Otherwise, the interconnection is included in control area interchange and a TieFlow is required at all sides of the boundary point (default).''',
			profiles=[]
		)
		self.register_property(
			name='ConnectivityNode',
			class_type=ConnectivityNode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The connectivity node that is designated as a boundary point.''',
			profiles=[]
		)
