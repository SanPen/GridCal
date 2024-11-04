# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class LimitSet(IdentifiedObject):
	def __init__(self, rdfid='', tpe='LimitSet'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		self.isPercentageLimits: bool = None

		self.register_property(
			name='isPercentageLimits',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Tells if the limit values are in percentage of normalValue or the specified Unit for Measurements and Controls.''',
			profiles=[]
		)
