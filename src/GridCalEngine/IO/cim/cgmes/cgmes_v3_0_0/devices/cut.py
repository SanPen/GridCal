# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.switch import Switch
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class Cut(Switch):
	def __init__(self, rdfid='', tpe='Cut'):
		Switch.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.ac_line_segment import ACLineSegment
		self.ACLineSegment: ACLineSegment | None = None
		self.lengthFromTerminal1: float = None

		self.register_property(
			name='ACLineSegment',
			class_type=ACLineSegment,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The line segment to which the cut is applied.''',
			profiles=[]
		)
		self.register_property(
			name='lengthFromTerminal1',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.m,
			description='''Unit of length. It shall be a positive value or zero.''',
			profiles=[]
		)
