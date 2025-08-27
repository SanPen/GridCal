# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from VeraGridEngine.IO.base.units import UnitMultiplier, UnitSymbol
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType


class LoadGroup(IdentifiedObject):
	def __init__(self, rdfid='', tpe='LoadGroup'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sub_load_area import SubLoadArea
		self.SubLoadArea: SubLoadArea | None = None

		self.register_property(
			name='SubLoadArea',
			class_type=SubLoadArea,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The SubLoadArea where the Loadgroup belongs.''',
			profiles=[]
		)
