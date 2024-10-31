# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class DCTopologicalIsland(IdentifiedObject):
	def __init__(self, rdfid='', tpe='DCTopologicalIsland'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_topological_node import DCTopologicalNode
		self.DCTopologicalNodes: DCTopologicalNode | None = None

		self.register_property(
			name='DCTopologicalNodes',
			class_type=DCTopologicalNode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The DC topological nodes in a DC topological island.''',
			profiles=[]
		)
