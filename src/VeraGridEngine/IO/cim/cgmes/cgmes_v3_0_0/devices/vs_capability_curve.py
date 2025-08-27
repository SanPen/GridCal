# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.IO.base.units import UnitMultiplier, UnitSymbol
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.curve import Curve
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType


class VsCapabilityCurve(Curve):
	def __init__(self, rdfid='', tpe='VsCapabilityCurve'):
		Curve.__init__(self, rdfid, tpe)

		from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.vs_converter import VsConverter
		self.VsConverterDCSides: VsConverter | None = None

		self.register_property(
			name='VsConverterDCSides',
			class_type=VsConverter,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''All converters with this capability curve.''',
			profiles=[]
		)
