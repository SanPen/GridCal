# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.base import Base
from GridCalEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType


class SvStatus(Base):
	def __init__(self, rdfid, tpe='SvStatus', resources=list(), class_replacements=dict()):
		Base.__init__(self, rdfid=rdfid, tpe=tpe, resources=resources, class_replacements=class_replacements)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.conducting_equipment import ConductingEquipment
		self.ConductingEquipment: ConductingEquipment | None = None
		self.inService: bool = None

		self.register_property(
			name='ConductingEquipment',
			class_type=ConductingEquipment,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The conducting equipment associated with the status state variable.''',
			profiles=[]
		)
		self.register_property(
			name='inService',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The in service status as a result of topology processing.''',
			profiles=[]
		)
