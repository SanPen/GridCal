# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.acdc_terminal import ACDCTerminal
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class DCBaseTerminal(ACDCTerminal):
	def __init__(self, rdfid='', tpe='DCBaseTerminal'):
		ACDCTerminal.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_node import DCNode
		self.DCNode: DCNode | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_topological_node import DCTopologicalNode
		self.DCTopologicalNode: DCTopologicalNode | None = None

		self.register_property(
			name='DCNode',
			class_type=DCNode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The DC connectivity node to which this DC base terminal connects with zero impedance.''',
			profiles=[]
		)
		self.register_property(
			name='DCTopologicalNode',
			class_type=DCTopologicalNode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''See association end Terminal.TopologicalNode.''',
			profiles=[]
		)
