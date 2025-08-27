# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.IO.base.units import UnitMultiplier, UnitSymbol
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.operational_limit import OperationalLimit
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType, UnitSymbol


class ApparentPowerLimit(OperationalLimit):
	def __init__(self, rdfid='', tpe='ApparentPowerLimit'):
		OperationalLimit.__init__(self, rdfid, tpe)

		self.value: float = None

		self.register_property(
			name='value',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.VA,
			description='''Product of the RMS value of the voltage and the RMS value of the current.''',
			profiles=[]
		)
