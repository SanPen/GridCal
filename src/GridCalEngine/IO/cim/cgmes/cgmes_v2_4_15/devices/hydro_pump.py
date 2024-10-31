# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equipment import Equipment
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class HydroPump(Equipment):
	def __init__(self, rdfid='', tpe='HydroPump'):
		Equipment.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.hydro_power_plant import HydroPowerPlant
		self.HydroPowerPlant: HydroPowerPlant | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.rotating_machine import RotatingMachine
		self.RotatingMachine: RotatingMachine | None = None

		self.register_property(
			name='HydroPowerPlant',
			class_type=HydroPowerPlant,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The hydro pump may be a member of a pumped storage plant or a pump for distributing water.''',
			profiles=[]
		)
		self.register_property(
			name='RotatingMachine',
			class_type=RotatingMachine,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The synchronous machine drives the turbine which moves the water from a low elevation to a higher elevation. The direction of machine rotation for pumping may or may not be the same as for generating.''',
			profiles=[]
		)
