# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.regular_interval_schedule import RegularIntervalSchedule
from GridCalEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType


class SeasonDayTypeSchedule(RegularIntervalSchedule):
	def __init__(self, rdfid='', tpe='SeasonDayTypeSchedule'):
		RegularIntervalSchedule.__init__(self, rdfid, tpe)


