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
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, SynchronousMachineOperatingMode, SynchronousMachineKind, UnitSymbol


class SynchronousMachine(RotatingMachine):
	def __init__(self, rdfid='', tpe='SynchronousMachine'):
		RotatingMachine.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.reactive_capability_curve import ReactiveCapabilityCurve
		self.InitialReactiveCapabilityCurve: ReactiveCapabilityCurve | None = None
		self.maxQ: float = None
		self.minQ: float = None
		self.qPercent: float = None
		self.type: SynchronousMachineKind = None
		self.operatingMode: SynchronousMachineOperatingMode = None
		self.referencePriority: int = None

		self.register_property(
			name='InitialReactiveCapabilityCurve',
			class_type=ReactiveCapabilityCurve,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The default reactive capability curve for use by a synchronous machine.''',
			profiles=[]
		)
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
			name='qPercent',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Percentage on a defined base.   For example, specify as 100 to indicate at the defined base.''',
			profiles=[]
		)
		self.register_property(
			name='type',
			class_type=SynchronousMachineKind,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Modes that this synchronous machine can operate in.''',
			profiles=[]
		)
		self.register_property(
			name='operatingMode',
			class_type=SynchronousMachineOperatingMode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Current mode of operation.''',
			profiles=[]
		)
		self.register_property(
			name='referencePriority',
			class_type=int,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Priority of unit for use as powerflow voltage phase angle reference bus selection. 0 = don t care (default) 1 = highest priority. 2 is less than 1 and so on.''',
			profiles=[]
		)
