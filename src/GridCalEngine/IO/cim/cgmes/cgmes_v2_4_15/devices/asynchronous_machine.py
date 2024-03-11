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
