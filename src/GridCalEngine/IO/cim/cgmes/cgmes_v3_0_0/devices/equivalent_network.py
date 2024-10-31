# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.connectivity_node_container import ConnectivityNodeContainer
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class EquivalentNetwork(ConnectivityNodeContainer):
	def __init__(self, rdfid='', tpe='EquivalentNetwork'):
		ConnectivityNodeContainer.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equivalent_equipment import EquivalentEquipment
		self.EquivalentEquipments: EquivalentEquipment | None = None

		self.register_property(
			name='EquivalentEquipments',
			class_type=EquivalentEquipment,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The associated reduced equivalents.''',
			profiles=[]
		)
