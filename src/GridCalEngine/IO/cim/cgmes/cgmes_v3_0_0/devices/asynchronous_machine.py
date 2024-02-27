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
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.rotating_machine import RotatingMachine
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, AsynchronousMachineKind, UnitSymbol


class AsynchronousMachine(RotatingMachine):
	def __init__(self, rdfid='', tpe='AsynchronousMachine'):
		RotatingMachine.__init__(self, rdfid, tpe)

		self.nominalFrequency: float = None
		self.nominalSpeed: float = None
		self.asynchronousMachineType: AsynchronousMachineKind = None

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
			unit=UnitSymbol.Hz,
			description='''Number of revolutions per second.''',
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
