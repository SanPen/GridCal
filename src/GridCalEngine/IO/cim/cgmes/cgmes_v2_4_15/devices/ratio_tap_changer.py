# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

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
