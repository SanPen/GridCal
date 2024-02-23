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
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equivalent_equipment import EquivalentEquipment
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class EquivalentBranch(EquivalentEquipment):
	def __init__(self, rdfid='', tpe='EquivalentBranch'):
		EquivalentEquipment.__init__(self, rdfid, tpe)

		self.r: float = None
		self.r21: float = None
		self.x: float = None
		self.x21: float = None

		self.register_property(
			name='r',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Resistance (real part of impedance).''',
			profiles=[]
		)
		self.register_property(
			name='r21',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Resistance (real part of impedance).''',
			profiles=[]
		)
		self.register_property(
			name='x',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Reactance (imaginary part of impedance), at rated frequency.''',
			profiles=[]
		)
		self.register_property(
			name='x21',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Reactance (imaginary part of impedance), at rated frequency.''',
			profiles=[]
		)
