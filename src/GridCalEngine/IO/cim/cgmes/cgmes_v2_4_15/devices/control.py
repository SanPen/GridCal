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
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol, UnitMultiplier


class Control(IdentifiedObject):
	def __init__(self, rdfid='', tpe='Control'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		self.controlType: str = None
		self.operationInProgress: bool = None
		import datetime
		self.timeStamp: datetime.datetime | None = None
		self.unitMultiplier: UnitMultiplier = None
		self.unitSymbol: UnitSymbol = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_system_resource import PowerSystemResource
		self.PowerSystemResource: PowerSystemResource | None = None

		self.register_property(
			name='controlType',
			class_type=str,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Specifies the type of Control, e.g. BreakerOn/Off, GeneratorVoltageSetPoint, TieLineFlow etc. The ControlType.name shall be unique among all specified types and describe the type.''',
			profiles=[]
		)
		self.register_property(
			name='operationInProgress',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Indicates that a client is currently sending control commands that has not completed.''',
			profiles=[]
		)
		self.register_property(
			name='timeStamp',
			class_type=datetime.datetime,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The last time a control output was sent.''',
			profiles=[]
		)
		self.register_property(
			name='unitMultiplier',
			class_type=UnitMultiplier,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The unit multiplier of the controlled quantity.''',
			profiles=[]
		)
		self.register_property(
			name='unitSymbol',
			class_type=UnitSymbol,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The unit of measure of the controlled quantity.''',
			profiles=[]
		)
		self.register_property(
			name='PowerSystemResource',
			class_type=PowerSystemResource,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The controller outputs used to actually govern a regulating device, e.g. the magnetization of a synchronous machine or capacitor bank breaker actuator.''',
			profiles=[]
		)
