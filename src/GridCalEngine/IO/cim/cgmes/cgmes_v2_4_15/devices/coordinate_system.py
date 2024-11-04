# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class CoordinateSystem(IdentifiedObject):
	def __init__(self, rdfid='', tpe='CoordinateSystem'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		self.crsUrn: str = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.location import Location
		self.Location: Location | None = None

		self.register_property(
			name='crsUrn',
			class_type=str,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A Uniform Resource Name (URN) for the coordinate reference system (crs) used to define 'Location.PositionPoints'.
An example would be the European Petroleum Survey Group (EPSG) code for a coordinate reference system, defined in URN under the Open Geospatial Consortium (OGC) namespace as: urn:ogc:def:uom:EPSG::XXXX, where XXXX is an EPSG code (a full list of codes can be found at the EPSG Registry web site http://www.epsg-registry.org/). To define the coordinate system as being WGS84 (latitude, longitude) using an EPSG OGC, this attribute would be urn:ogc:def:uom:EPSG::4236.
A profile should limit this code to a set of allowed URNs agreed to by all sending and receiving parties.''',
			profiles=[]
		)
		self.register_property(
			name='Location',
			class_type=Location,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''All locations described with position points in this coordinate system.''',
			profiles=[]
		)
