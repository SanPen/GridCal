# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_system_resource import PowerSystemResource
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class CombinedCyclePlant(PowerSystemResource):
	def __init__(self, rdfid='', tpe='CombinedCyclePlant'):
		PowerSystemResource.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.thermal_generating_unit import ThermalGeneratingUnit
		self.ThermalGeneratingUnits: ThermalGeneratingUnit | None = None

		self.register_property(
			name='ThermalGeneratingUnits',
			class_type=ThermalGeneratingUnit,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A thermal generating unit may be a member of a combined cycle plant.''',
			profiles=[]
		)
