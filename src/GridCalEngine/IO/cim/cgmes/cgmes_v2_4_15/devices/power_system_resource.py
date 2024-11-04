# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class PowerSystemResource(IdentifiedObject):
	def __init__(self, rdfid='', tpe='PowerSystemResource'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.control import Control
		self.Controls: Control | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.measurement import Measurement
		self.Measurements: Measurement | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.location import Location
		self.Location: Location | None = None

		self.register_property(
			name='Controls',
			class_type=Control,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Regulating device governed by this control output.''',
			profiles=[]
		)
		self.register_property(
			name='Measurements',
			class_type=Measurement,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The power system resource that contains the measurement.''',
			profiles=[]
		)
		self.register_property(
			name='Location',
			class_type=Location,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Location of this power system resource.''',
			profiles=[]
		)
