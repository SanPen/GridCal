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
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.acdc_converter import ACDCConverter
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, VsQpccControlKind, UnitSymbol, VsPpccControlKind


class VsConverter(ACDCConverter):
	def __init__(self, rdfid='', tpe='VsConverter'):
		ACDCConverter.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.vs_capability_curve import VsCapabilityCurve
		self.CapabilityCurve: VsCapabilityCurve | None = None
		self.maxModulationIndex: float = None
		self.delta: float = None
		self.uv: float = None
		self.droop: float = None
		self.droopCompensation: float = None
		self.pPccControl: VsPpccControlKind = None
		self.qPccControl: VsQpccControlKind = None
		self.qShare: float = None
		self.targetQpcc: float = None
		self.targetUpcc: float = None
		self.targetPowerFactorPcc: float = None
		self.targetPhasePcc: float = None
		self.targetPWMfactor: float = None

		self.register_property(
			name='CapabilityCurve',
			class_type=VsCapabilityCurve,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Capability curve of this converter.''',
			profiles=[]
		)
		self.register_property(
			name='maxModulationIndex',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The maximum quotient between the AC converter voltage (Uc) and DC voltage (Ud). A factor typically less than 1. It is converter�s configuration data used in power flow.''' ,
			profiles=[]
		)
		self.register_property(
			name='delta',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.deg,
			description='''Measurement of angle in degrees.''',
			profiles=[]
		)
		self.register_property(
			name='uv',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='droop',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Per Unit - a positive or negative value referred to a defined base. Values typically range from -10 to +10.''',
			profiles=[]
		)
		self.register_property(
			name='droopCompensation',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Resistance (real part of impedance).''',
			profiles=[]
		)
		self.register_property(
			name='pPccControl',
			class_type=VsPpccControlKind,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Kind of control of real power and/or DC voltage.''',
			profiles=[]
		)
		self.register_property(
			name='qPccControl',
			class_type=VsQpccControlKind,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Kind of reactive power control.''',
			profiles=[]
		)
		self.register_property(
			name='qShare',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Percentage on a defined base.   For example, specify as 100 to indicate at the defined base.''',
			profiles=[]
		)
		self.register_property(
			name='targetQpcc',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.VAr,
			description='''Product of RMS value of the voltage and the RMS value of the quadrature component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='targetUpcc',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='targetPowerFactorPcc',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Power factor target at the AC side, at point of common coupling. The attribute shall be a positive value.''',
			profiles=[]
		)
		self.register_property(
			name='targetPhasePcc',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.deg,
			description='''Measurement of angle in degrees.''',
			profiles=[]
		)
		self.register_property(
			name='targetPWMfactor',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Magnitude of pulse-modulation factor. The attribute shall be a positive value.''',
			profiles=[]
		)
