# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.basic_interval_schedule import BasicIntervalSchedule
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class RegularIntervalSchedule(BasicIntervalSchedule):
	def __init__(self, rdfid='', tpe='RegularIntervalSchedule'):
		BasicIntervalSchedule.__init__(self, rdfid, tpe)

		self.timeStep: float = None
		import datetime
		self.endTime: datetime.datetime | None = None

		self.register_property(
			name='timeStep',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.s,
			description='''Time, in seconds.''',
			profiles=[]
		)
		self.register_property(
			name='endTime',
			class_type=datetime.datetime,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The time for the last time point.  The value can be a time of day, not a specific date.''',
			profiles=[]
		)
