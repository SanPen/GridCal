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
from GridCalEngine.IO.cim.cgmes_v2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_v2_4_15.curve import Curve
from GridCalEngine.IO.cim.cgmes_v2_4_15.equivalent_injection import EquivalentInjection
from GridCalEngine.IO.cim.cgmes_v2_4_15.synchronous_machine import SynchronousMachine


class ReactiveCapabilityCurve(Curve):
	def __init__(self, rdfid='', tpe='ReactiveCapabilityCurve'):
		Curve.__init__(self, rdfid, tpe)

		self.EquivalentInjection: EquivalentInjection | None = None
		self.InitiallyUsedBySynchronousMachines: SynchronousMachine | None = None

		self.register_property(
			name='EquivalentInjection',
			class_type=EquivalentInjection,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='The reactive capability curve used by this equivalent injection.',
			profiles=[]
		)
		self.register_property(
			name='InitiallyUsedBySynchronousMachines',
			class_type=SynchronousMachine,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='The default reactive capability curve for use by a synchronous machine.',
			profiles=[]
		)
