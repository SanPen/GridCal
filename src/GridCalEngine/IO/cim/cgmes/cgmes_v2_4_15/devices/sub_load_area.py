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
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.energy_area import EnergyArea
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class SubLoadArea(EnergyArea):
	def __init__(self, rdfid='', tpe='SubLoadArea'):
		EnergyArea.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.load_area import LoadArea
		self.LoadArea: LoadArea | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.load_group import LoadGroup
		self.LoadGroups: LoadGroup | None = None

		self.register_property(
			name='LoadArea',
			class_type=LoadArea,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The LoadArea where the SubLoadArea belongs.''',
			profiles=[]
		)
		self.register_property(
			name='LoadGroups',
			class_type=LoadGroup,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The Loadgroups in the SubLoadArea.''',
			profiles=[]
		)
