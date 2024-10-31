# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.conducting_equipment import ConductingEquipment
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class EquivalentEquipment(ConductingEquipment):
	def __init__(self, rdfid='', tpe='EquivalentEquipment'):
		ConductingEquipment.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equivalent_network import EquivalentNetwork
		self.EquivalentNetwork: EquivalentNetwork | None = None

		self.register_property(
			name='EquivalentNetwork',
			class_type=EquivalentNetwork,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The equivalent where the reduced model belongs.''',
			profiles=[]
		)
