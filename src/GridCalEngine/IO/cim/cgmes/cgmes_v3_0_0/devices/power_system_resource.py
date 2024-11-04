# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class PowerSystemResource(IdentifiedObject):
	def __init__(self, rdfid='', tpe='PowerSystemResource'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.location import Location
		self.Location: Location | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.control import Control
		self.Controls: Control | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.measurement import Measurement
		self.Measurements: Measurement | None = None

		self.register_property(
			name='Location',
			class_type=Location,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Location of this power system resource.''',
			profiles=[]
		)
		self.register_property(
			name='Controls',
			class_type=Control,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The controller outputs used to actually govern a regulating device, e.g. the magnetization of a synchronous machine or capacitor bank breaker actuator.''',
			profiles=[]
		)
		self.register_property(
			name='Measurements',
			class_type=Measurement,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The measurements associated with this power system resource.''',
			profiles=[]
		)
