# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.base import Base
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class SvShuntCompensatorSections(Base):
	def __init__(self, rdfid, tpe="SvShuntCompensatorSections", resources=list(), class_replacements=dict()):
		Base.__init__(self, rdfid=rdfid, tpe=tpe, resources=resources, class_replacements=class_replacements)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.shunt_compensator import ShuntCompensator
		self.ShuntCompensator: ShuntCompensator | None = None
		self.sections: float = None

		self.register_property(
			name='ShuntCompensator',
			class_type=ShuntCompensator,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The shunt compensator for which the state applies.''',
			profiles=[]
		)
		self.register_property(
			name='sections',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The number of sections in service as a continuous variable. The attribute shall be a positive value or zero. To get integer value scale with ShuntCompensator.bPerSection.''',
			profiles=[]
		)
