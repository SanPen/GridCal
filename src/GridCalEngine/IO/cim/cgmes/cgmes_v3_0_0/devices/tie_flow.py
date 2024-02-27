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
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class TieFlow(IdentifiedObject):
	def __init__(self, rdfid='', tpe='TieFlow'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.control_area import ControlArea
		self.ControlArea: ControlArea | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.terminal import Terminal
		self.Terminal: Terminal | None = None
		self.positiveFlowIn: bool = None

		self.register_property(
			name='ControlArea',
			class_type=ControlArea,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The control area of the tie flows.''',
			profiles=[]
		)
		self.register_property(
			name='Terminal',
			class_type=Terminal,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The terminal to which this tie flow belongs.''',
			profiles=[]
		)
		self.register_property(
			name='positiveFlowIn',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Specifies the sign of the tie flow associated with a control area. True if positive flow into the terminal (load convention) is also positive flow into the control area.  See the description of ControlArea for further explanation of how TieFlow.positiveFlowIn is used.''',
			profiles=[]
		)
