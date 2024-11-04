# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.connectivity_node_container import ConnectivityNodeContainer
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class EquipmentContainer(ConnectivityNodeContainer):
	def __init__(self, rdfid='', tpe='EquipmentContainer'):
		ConnectivityNodeContainer.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equipment import Equipment
		self.Equipments: Equipment | None = None

		self.register_property(
			name='Equipments',
			class_type=Equipment,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Contained equipment.''',
			profiles=[]
		)
