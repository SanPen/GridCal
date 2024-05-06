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
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, SVCControlMode, UnitSymbol


class StaticVarCompensator(RegulatingCondEq):
	def __init__(self, rdfid='', tpe='StaticVarCompensator'):
		RegulatingCondEq.__init__(self, rdfid, tpe)

		self.capacitiveRating: float = None
		self.inductiveRating: float = None
		self.slope: float = None
		self.sVCControlMode: SVCControlMode = None
		self.voltageSetPoint: float = None
		self.q: float = None

		self.register_property(
			name='capacitiveRating',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Reactance (imaginary part of impedance), at rated frequency.''',
			profiles=[]
		)
		self.register_property(
			name='inductiveRating',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Reactance (imaginary part of impedance), at rated frequency.''',
			profiles=[]
		)
		self.register_property(
			name='slope',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.VPerVAr,
			description='''Voltage variation with reactive power.''',
			profiles=[]
		)
		self.register_property(
			name='sVCControlMode',
			class_type=SVCControlMode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''SVC control mode.''',
			profiles=[]
		)
		self.register_property(
			name='voltageSetPoint',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
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
