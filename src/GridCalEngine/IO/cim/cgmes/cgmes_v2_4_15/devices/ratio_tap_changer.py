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
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.tap_changer import TapChanger
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, TransformerControlMode, UnitSymbol


class RatioTapChanger(TapChanger):
	def __init__(self, rdfid='', tpe='RatioTapChanger'):
		TapChanger.__init__(self, rdfid, tpe)

		self.tculControlMode: TransformerControlMode = None
		self.stepVoltageIncrement: float = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.ratio_tap_changer_table import RatioTapChangerTable
		self.RatioTapChangerTable: RatioTapChangerTable | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.transformer_end import TransformerEnd
		self.TransformerEnd: TransformerEnd | None = None

		self.register_property(
			name='tculControlMode',
			class_type=TransformerControlMode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Specifies the regulation control mode (voltage or reactive) of the RatioTapChanger.''',
			profiles=[]
		)
		self.register_property(
			name='stepVoltageIncrement',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Percentage on a defined base.   For example, specify as 100 to indicate at the defined base.''',
			profiles=[]
		)
		self.register_property(
			name='RatioTapChangerTable',
			class_type=RatioTapChangerTable,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The ratio tap changer of this tap ratio table.''',
			profiles=[]
		)
		self.register_property(
			name='TransformerEnd',
			class_type=TransformerEnd,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Ratio tap changer associated with this transformer end.''',
			profiles=[]
		)
