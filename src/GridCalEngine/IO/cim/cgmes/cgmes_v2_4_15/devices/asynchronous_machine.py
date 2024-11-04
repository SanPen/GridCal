# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.rotating_machine import RotatingMachine
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol, AsynchronousMachineKind


class AsynchronousMachine(RotatingMachine):
	def __init__(self, rdfid='', tpe='AsynchronousMachine'):
		RotatingMachine.__init__(self, rdfid, tpe)

		self.converterFedDrive: bool = None
		self.efficiency: float = None
		self.iaIrRatio: float = None
		self.nominalFrequency: float = None
		self.nominalSpeed: float = None
		self.polePairNumber: int = None
		self.ratedMechanicalPower: float = None
		self.reversible: bool = None
		self.rxLockedRotorRatio: float = None
		self.asynchronousMachineType: AsynchronousMachineKind = None

		self.register_property(
			name='converterFedDrive',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Indicates whether the machine is a converter fed drive. Used for short circuit data exchange according to IEC 60909''',
			profiles=[]
		)
		self.register_property(
			name='efficiency',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Percentage on a defined base.   For example, specify as 100 to indicate at the defined base.''',
			profiles=[]
		)
		self.register_property(
			name='iaIrRatio',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A floating point number. The range is unspecified and not limited.''',
			profiles=[]
		)
		self.register_property(
			name='nominalFrequency',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.Hz,
			description='''Cycles per second.''',
			profiles=[]
		)
		self.register_property(
			name='nominalSpeed',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Number of revolutions per second.''',
			profiles=[]
		)
		self.register_property(
			name='polePairNumber',
			class_type=int,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Number of pole pairs of stator. Used for short circuit data exchange according to IEC 60909''',
			profiles=[]
		)
		self.register_property(
			name='ratedMechanicalPower',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.W,
			description='''Product of RMS value of the voltage and the RMS value of the in-phase component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='reversible',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Indicates for converter drive motors if the power can be reversible. Used for short circuit data exchange according to IEC 60909''',
			profiles=[]
		)
		self.register_property(
			name='rxLockedRotorRatio',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A floating point number. The range is unspecified and not limited.''',
			profiles=[]
		)
		self.register_property(
			name='asynchronousMachineType',
			class_type=AsynchronousMachineKind,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Indicates the type of Asynchronous Machine (motor or generator).''',
			profiles=[]
		)
