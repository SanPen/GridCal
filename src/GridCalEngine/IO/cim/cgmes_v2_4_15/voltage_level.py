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
from GridCalEngine.IO.cim.cgmes_v2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_v2_4_15.equipment_container import EquipmentContainer
from GridCalEngine.IO.cim.cgmes_v2_4_15.base_voltage import BaseVoltage
from GridCalEngine.IO.cim.cgmes_v2_4_15.bay import Bay
from GridCalEngine.IO.cim.cgmes_v2_4_15.substation import Substation


class VoltageLevel(EquipmentContainer):
	def __init__(self, rdfid='', tpe='VoltageLevel'):
		EquipmentContainer.__init__(self, rdfid, tpe)

		self.BaseVoltage: BaseVoltage | None = None
		self.Bays: Bay | None = None
		self.Substation: Substation | None = None
		self.highVoltageLimit: float = 0.0
		self.lowVoltageLimit: float = 0.0

		self.register_property(
			name='BaseVoltage',
			class_type=BaseVoltage,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='The base voltage used for all equipment within the voltage level.',
			profiles=[]
		)
		self.register_property(
			name='Bays',
			class_type=Bay,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='The bays within this voltage level.',
			profiles=[]
		)
		self.register_property(
			name='Substation',
			class_type=Substation,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='The substation of the voltage level.',
			profiles=[]
		)
		self.register_property(
			name='highVoltageLimit',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='Electrical voltage, can be both AC and DC.',
			profiles=[]
		)
		self.register_property(
			name='lowVoltageLimit',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='Electrical voltage, can be both AC and DC.',
			profiles=[]
		)
