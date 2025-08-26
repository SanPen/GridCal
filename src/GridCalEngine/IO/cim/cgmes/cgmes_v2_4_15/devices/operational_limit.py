# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType


class OperationalLimit(IdentifiedObject):
	def __init__(self, rdfid='', tpe='OperationalLimit'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.operational_limit_set import OperationalLimitSet
		self.OperationalLimitSet: OperationalLimitSet | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.operational_limit_type import OperationalLimitType
		self.OperationalLimitType: OperationalLimitType | None = None

		self.register_property(
			name='OperationalLimitSet',
			class_type=OperationalLimitSet,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Values of equipment limits.''',
			profiles=[]
		)
		self.register_property(
			name='OperationalLimitType',
			class_type=OperationalLimitType,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The limit type associated with this limit.''',
			profiles=[]
		)
