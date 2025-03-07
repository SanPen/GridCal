# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equipment import Equipment
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, Currency, UnitSymbol, GeneratorControlSource


class GeneratingUnit(Equipment):
	def __init__(self, rdfid='', tpe='GeneratingUnit'):
		Equipment.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.control_area_generating_unit import ControlAreaGeneratingUnit
		self.ControlAreaGeneratingUnit: ControlAreaGeneratingUnit | None = None
		self.genControlSource: GeneratorControlSource = None
		self.governorSCD: float = None
		self.longPF: float = None
		self.maximumAllowableSpinningReserve: float = None
		self.maxOperatingP: float = None
		self.minOperatingP: float = None
		self.nominalP: float = None
		self.ratedGrossMaxP: float = None
		self.ratedGrossMinP: float = None
		self.ratedNetMaxP: float = None
		self.shortPF: float = None
		self.startupCost: float = None
		self.variableCost: float = None
		self.startupTime: float = None
		self.totalEfficiency: float = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.rotating_machine import RotatingMachine
		self.RotatingMachine: RotatingMachine | None = None
		self.normalPF: float = None

		self.register_property(
			name='ControlAreaGeneratingUnit',
			class_type=ControlAreaGeneratingUnit,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''ControlArea specifications for this generating unit.''',
			profiles=[]
		)
		self.register_property(
			name='genControlSource',
			class_type=GeneratorControlSource,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The source of controls for a generating unit.  Defines the control status of the generating unit.''',
			profiles=[]
		)
		self.register_property(
			name='governorSCD',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Percentage on a defined base.   For example, specify as 100 to indicate at the defined base.''',
			profiles=[]
		)
		self.register_property(
			name='longPF',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Generating unit long term economic participation factor.''',
			profiles=[]
		)
		self.register_property(
			name='maximumAllowableSpinningReserve',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.W,
			description='''Product of RMS value of the voltage and the RMS value of the in-phase component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='maxOperatingP',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.W,
			description='''Product of RMS value of the voltage and the RMS value of the in-phase component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='minOperatingP',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.W,
			description='''Product of RMS value of the voltage and the RMS value of the in-phase component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='nominalP',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.W,
			description='''Product of RMS value of the voltage and the RMS value of the in-phase component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='ratedGrossMaxP',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.W,
			description='''Product of RMS value of the voltage and the RMS value of the in-phase component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='ratedGrossMinP',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.W,
			description='''Product of RMS value of the voltage and the RMS value of the in-phase component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='ratedNetMaxP',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.W,
			description='''Product of RMS value of the voltage and the RMS value of the in-phase component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='shortPF',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Generating unit short term economic participation factor.''',
			profiles=[]
		)
		self.register_property(
			name='startupCost',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Amount of money.''',
			profiles=[]
		)
		self.register_property(
			name='variableCost',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Amount of money.''',
			profiles=[]
		)
		self.register_property(
			name='startupTime',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.s,
			description='''Time, in seconds.''',
			profiles=[]
		)
		self.register_property(
			name='totalEfficiency',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Percentage on a defined base.   For example, specify as 100 to indicate at the defined base.''',
			profiles=[]
		)
		self.register_property(
			name='RotatingMachine',
			class_type=RotatingMachine,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A synchronous machine may operate as a generator and as such becomes a member of a generating unit.''',
			profiles=[]
		)
		self.register_property(
			name='normalPF',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Generating unit economic participation factor.  The sum of the participation factors across generating units does not have to sum to one.  It is used for representing distributed slack participation factor. The attribute shall be a positive value or zero.''',
			profiles=[]
		)
