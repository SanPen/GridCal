# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_base_terminal import DCBaseTerminal
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, DCPolarityKind


class ACDCConverterDCTerminal(DCBaseTerminal):
	def __init__(self, rdfid='', tpe='ACDCConverterDCTerminal'):
		DCBaseTerminal.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.acdc_converter import ACDCConverter
		self.DCConductingEquipment: ACDCConverter | None = None
		self.polarity: DCPolarityKind = None

		self.register_property(
			name='DCConductingEquipment',
			class_type=ACDCConverter,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A DC converter terminal belong to an DC converter.''',
			profiles=[]
		)
		self.register_property(
			name='polarity',
			class_type=DCPolarityKind,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Represents the normal network polarity condition. Depending on the converter configuration the value shall be set as follows:
- For a monopole with two converter terminals use DCPolarityKind �positive� and �negative�.
- For a bi-pole or symmetric monopole with three converter terminals use DCPolarityKind �positive�, �middle� and �negative�.''' ,
			profiles=[]
		)
