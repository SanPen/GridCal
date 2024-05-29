# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
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
