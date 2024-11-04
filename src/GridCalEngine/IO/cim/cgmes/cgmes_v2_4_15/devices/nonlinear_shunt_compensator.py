# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.shunt_compensator import ShuntCompensator
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class NonlinearShuntCompensator(ShuntCompensator):
	def __init__(self, rdfid='', tpe='NonlinearShuntCompensator'):
		ShuntCompensator.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.nonlinear_shunt_compensator_point import NonlinearShuntCompensatorPoint
		self.NonlinearShuntCompensatorPoints: NonlinearShuntCompensatorPoint | None = None

		self.register_property(
			name='NonlinearShuntCompensatorPoints',
			class_type=NonlinearShuntCompensatorPoint,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''All points of the non-linear shunt compensator.''',
			profiles=[]
		)
