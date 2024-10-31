# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.acdc_converter import ACDCConverter
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, CsPpccControlKind, CsOperatingModeKind, UnitSymbol


class CsConverter(ACDCConverter):
	def __init__(self, rdfid='', tpe='CsConverter'):
		ACDCConverter.__init__(self, rdfid, tpe)

		self.maxAlpha: float = None
		self.maxGamma: float = None
		self.maxIdc: float = None
		self.minAlpha: float = None
		self.minGamma: float = None
		self.minIdc: float = None
		self.ratedIdc: float = None
		self.alpha: float = None
		self.gamma: float = None
		self.operatingMode: CsOperatingModeKind = None
		self.pPccControl: CsPpccControlKind = None
		self.targetAlpha: float = None
		self.targetGamma: float = None
		self.targetIdc: float = None

		self.register_property(
			name='maxAlpha',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.deg,
			description='''Measurement of angle in degrees.''',
			profiles=[]
		)
		self.register_property(
			name='maxGamma',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.deg,
			description='''Measurement of angle in degrees.''',
			profiles=[]
		)
		self.register_property(
			name='maxIdc',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.A,
			description='''Electrical current with sign convention: positive flow is out of the conducting equipment into the connectivity node. Can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='minAlpha',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.deg,
			description='''Measurement of angle in degrees.''',
			profiles=[]
		)
		self.register_property(
			name='minGamma',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.deg,
			description='''Measurement of angle in degrees.''',
			profiles=[]
		)
		self.register_property(
			name='minIdc',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.A,
			description='''Electrical current with sign convention: positive flow is out of the conducting equipment into the connectivity node. Can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='ratedIdc',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.A,
			description='''Electrical current with sign convention: positive flow is out of the conducting equipment into the connectivity node. Can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='alpha',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.deg,
			description='''Measurement of angle in degrees.''',
			profiles=[]
		)
		self.register_property(
			name='gamma',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.deg,
			description='''Measurement of angle in degrees.''',
			profiles=[]
		)
		self.register_property(
			name='operatingMode',
			class_type=CsOperatingModeKind,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Indicates whether the DC pole is operating as an inverter or as a rectifier. It is converter�s control variable used in power flow.''' ,
			profiles=[]
		)
		self.register_property(
			name='pPccControl',
			class_type=CsPpccControlKind,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Kind of active power control.''',
			profiles=[]
		)
		self.register_property(
			name='targetAlpha',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.deg,
			description='''Measurement of angle in degrees.''',
			profiles=[]
		)
		self.register_property(
			name='targetGamma',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.deg,
			description='''Measurement of angle in degrees.''',
			profiles=[]
		)
		self.register_property(
			name='targetIdc',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.A,
			description='''Electrical current with sign convention: positive flow is out of the conducting equipment into the connectivity node. Can be both AC and DC.''',
			profiles=[]
		)
