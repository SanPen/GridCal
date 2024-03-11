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
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.conducting_equipment import ConductingEquipment
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class Switch(ConductingEquipment):
	def __init__(self, rdfid='', tpe='Switch'):
		ConductingEquipment.__init__(self, rdfid, tpe)

		self.normalOpen: bool = None
		self.ratedCurrent: float = None
		self.retained: bool = None
		self.open: bool = None

		self.register_property(
			name='normalOpen',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The attribute is used in cases when no Measurement for the status value is present. If the Switch has a status measurement the Discrete.normalValue is expected to match with the Switch.normalOpen.''',
			profiles=[]
		)
		self.register_property(
			name='ratedCurrent',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.A,
			description='''Electrical current with sign convention: positive flow is out of the conducting equipment into the connectivity node. Can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='retained',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Branch is retained in a bus branch model.  The flow through retained switches will normally be calculated in power flow.''',
			profiles=[]
		)
		self.register_property(
			name='open',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The attribute tells if the switch is considered open when used as input to topology processing.''',
			profiles=[]
		)
