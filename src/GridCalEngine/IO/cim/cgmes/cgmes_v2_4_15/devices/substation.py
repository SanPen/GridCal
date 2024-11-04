# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equipment_container import EquipmentContainer
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class Substation(EquipmentContainer):
	def __init__(self, rdfid='', tpe='Substation'):
		EquipmentContainer.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_converter_unit import DCConverterUnit
		self.DCConverterUnit: DCConverterUnit | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.sub_geographical_region import SubGeographicalRegion
		self.Region: SubGeographicalRegion | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.voltage_level import VoltageLevel
		self.VoltageLevels: VoltageLevel | None = None

		self.register_property(
			name='DCConverterUnit',
			class_type=DCConverterUnit,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''None''',
			profiles=[]
		)
		self.register_property(
			name='Region',
			class_type=SubGeographicalRegion,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The SubGeographicalRegion containing the substation.''',
			profiles=[]
		)
		self.register_property(
			name='VoltageLevels',
			class_type=VoltageLevel,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The voltage levels within this substation.''',
			profiles=[]
		)
