# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.conducting_equipment import ConductingEquipment
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class ACDCConverter(ConductingEquipment):
	def __init__(self, rdfid='', tpe='ACDCConverter'):
		ConductingEquipment.__init__(self, rdfid, tpe)

		self.baseS: float = None
		self.idleLoss: float = None
		self.maxUdc: float = None
		self.minUdc: float = None
		self.numberOfValves: int = None
		self.ratedUdc: float = None
		self.resistiveLoss: float = None
		self.switchingLoss: float = None
		self.valveU0: float = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.acdc_converterdc_terminal import ACDCConverterDCTerminal
		self.DCTerminals: ACDCConverterDCTerminal | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.terminal import Terminal
		self.PccTerminal: Terminal | None = None
		self.idc: float = None
		self.poleLossP: float = None
		self.uc: float = None
		self.udc: float = None
		self.p: float = None
		self.q: float = None
		self.targetPpcc: float = None
		self.targetUdc: float = None

		self.register_property(
			name='baseS',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.VA,
			description='''Product of the RMS value of the voltage and the RMS value of the current.''',
			profiles=[]
		)
		self.register_property(
			name='idleLoss',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.W,
			description='''Product of RMS value of the voltage and the RMS value of the in-phase component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='maxUdc',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='minUdc',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='numberOfValves',
			class_type=int,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Number of valves in the converter. Used in loss calculations.''',
			profiles=[]
		)
		self.register_property(
			name='ratedUdc',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='resistiveLoss',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Resistance (real part of impedance).''',
			profiles=[]
		)
		self.register_property(
			name='switchingLoss',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.W,
			description='''None''',
			profiles=[]
		)
		self.register_property(
			name='valveU0',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='DCTerminals',
			class_type=ACDCConverterDCTerminal,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''None''',
			profiles=[]
		)
		self.register_property(
			name='PccTerminal',
			class_type=Terminal,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''All converters' DC sides linked to this point of common coupling terminal.''',
			profiles=[]
		)
		self.register_property(
			name='idc',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.A,
			description='''Electrical current with sign convention: positive flow is out of the conducting equipment into the connectivity node. Can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='poleLossP',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.W,
			description='''Product of RMS value of the voltage and the RMS value of the in-phase component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='uc',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='udc',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
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
		self.register_property(
			name='targetPpcc',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.W,
			description='''Product of RMS value of the voltage and the RMS value of the in-phase component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='targetUdc',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
			profiles=[]
		)
