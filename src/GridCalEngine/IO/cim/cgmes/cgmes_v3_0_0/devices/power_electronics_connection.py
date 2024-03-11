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
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.regulating_cond_eq import RegulatingCondEq
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class PowerElectronicsConnection(RegulatingCondEq):
	def __init__(self, rdfid='', tpe='PowerElectronicsConnection'):
		RegulatingCondEq.__init__(self, rdfid, tpe)

		self.maxQ: float = None
		self.minQ: float = None
		self.ratedS: float = None
		self.ratedU: float = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_electronics_unit import PowerElectronicsUnit
		self.PowerElectronicsUnit: PowerElectronicsUnit | None = None
		self.p: float = None
		self.q: float = None

		self.register_property(
			name='maxQ',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.VAr,
			description='''Product of RMS value of the voltage and the RMS value of the quadrature component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='minQ',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.VAr,
			description='''Product of RMS value of the voltage and the RMS value of the quadrature component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='ratedS',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.VA,
			description='''Product of the RMS value of the voltage and the RMS value of the current.''',
			profiles=[]
		)
		self.register_property(
			name='ratedU',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='PowerElectronicsUnit',
			class_type=PowerElectronicsUnit,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''An AC network connection may have several power electronics units connecting through it.''',
			profiles=[]
		)
		self.register_property(
			name='p',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.W,
			description='''Product of RMS value of the voltage and the RMS value of the in-phase component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='q',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.VAr,
			description='''Product of RMS value of the voltage and the RMS value of the quadrature component of the current.''',
			profiles=[]
		)
