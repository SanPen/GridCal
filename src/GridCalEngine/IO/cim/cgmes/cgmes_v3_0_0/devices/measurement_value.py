# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.io_point import IOPoint
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class MeasurementValue(IOPoint):
	def __init__(self, rdfid='', tpe='MeasurementValue'):
		IOPoint.__init__(self, rdfid, tpe)

		import datetime
		self.timeStamp: datetime.datetime | None = None
		self.sensorAccuracy: float = None

		self.register_property(
			name='timeStamp',
			class_type=datetime.datetime,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The time when the value was last updated.''',
			profiles=[]
		)
		self.register_property(
			name='sensorAccuracy',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Percentage on a defined base.   For example, specify as 100 to indicate at the defined base.''',
			profiles=[]
		)
