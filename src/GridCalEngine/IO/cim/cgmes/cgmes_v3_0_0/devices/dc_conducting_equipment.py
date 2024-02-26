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
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equipment import Equipment
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class DCConductingEquipment(Equipment):
	def __init__(self, rdfid='', tpe='DCConductingEquipment'):
		Equipment.__init__(self, rdfid, tpe)

		self.ratedUdc: float = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_terminal import DCTerminal
		self.DCTerminals: DCTerminal | None = None

		self.register_property(
			name='ratedUdc',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='DCTerminals',
			class_type=DCTerminal,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A DC conducting equipment has DC terminals.''',
			profiles=[]
		)
