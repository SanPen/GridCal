# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_equipment_container import DCEquipmentContainer
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, DCConverterOperatingModeKind


class DCConverterUnit(DCEquipmentContainer):
	def __init__(self, rdfid='', tpe='DCConverterUnit'):
		DCEquipmentContainer.__init__(self, rdfid, tpe)

		self.operationMode: DCConverterOperatingModeKind = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.substation import Substation
		self.Substation: Substation | None = None

		self.register_property(
			name='operationMode',
			class_type=DCConverterOperatingModeKind,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''None''',
			profiles=[]
		)
		self.register_property(
			name='Substation',
			class_type=Substation,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''None''',
			profiles=[]
		)
