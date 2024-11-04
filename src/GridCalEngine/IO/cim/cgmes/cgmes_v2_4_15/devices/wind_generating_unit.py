# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.generating_unit import GeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, WindGenUnitKind


class WindGeneratingUnit(GeneratingUnit):
	def __init__(self, rdfid='', tpe='WindGeneratingUnit'):
		GeneratingUnit.__init__(self, rdfid, tpe)

		self.windGenUnitType: WindGenUnitKind = None

		self.register_property(
			name='windGenUnitType',
			class_type=WindGenUnitKind,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The kind of wind generating unit''',
			profiles=[]
		)
