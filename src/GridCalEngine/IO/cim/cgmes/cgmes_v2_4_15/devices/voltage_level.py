# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equipment_container import EquipmentContainer
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class VoltageLevel(EquipmentContainer):
	def __init__(self, rdfid='', tpe='VoltageLevel'):
		EquipmentContainer.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.base_voltage import BaseVoltage
		self.BaseVoltage: BaseVoltage | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.bay import Bay
		self.Bays: Bay | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.substation import Substation
		self.Substation: Substation | None = None
		self.highVoltageLimit: float = None
		self.lowVoltageLimit: float = None

		self.register_property(
			name='BaseVoltage',
			class_type=BaseVoltage,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The base voltage used for all equipment within the voltage level.''',
			profiles=[]
		)
		self.register_property(
			name='Bays',
			class_type=Bay,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The bays within this voltage level.''',
			profiles=[]
		)
		self.register_property(
			name='Substation',
			class_type=Substation,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The substation of the voltage level.''',
			profiles=[]
		)
		self.register_property(
			name='highVoltageLimit',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='lowVoltageLimit',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
			profiles=[]
		)
