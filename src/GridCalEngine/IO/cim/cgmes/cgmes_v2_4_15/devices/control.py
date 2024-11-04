# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

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
