# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equipment import Equipment
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class PowerElectronicsUnit(Equipment):
	def __init__(self, rdfid='', tpe='PowerElectronicsUnit'):
		Equipment.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_electronics_connection import PowerElectronicsConnection
		self.PowerElectronicsConnection: PowerElectronicsConnection | None = None
		self.maxP: float = None
		self.minP: float = None

		self.register_property(
			name='PowerElectronicsConnection',
			class_type=PowerElectronicsConnection,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A power electronics unit has a connection to the AC network.''',
			profiles=[]
		)
		self.register_property(
			name='maxP',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.W,
			description='''Product of RMS value of the voltage and the RMS value of the in-phase component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='minP',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.W,
			description='''Product of RMS value of the voltage and the RMS value of the in-phase component of the current.''',
			profiles=[]
		)
