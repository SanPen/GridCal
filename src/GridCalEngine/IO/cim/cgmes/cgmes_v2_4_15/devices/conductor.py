# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.conducting_equipment import ConductingEquipment
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class Conductor(ConductingEquipment):
	def __init__(self, rdfid='', tpe='Conductor'):
		ConductingEquipment.__init__(self, rdfid, tpe)

		self.length: float = None

		self.register_property(
			name='length',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.m,
			description='''Unit of length. Never negative.''',
			profiles=[]
		)
