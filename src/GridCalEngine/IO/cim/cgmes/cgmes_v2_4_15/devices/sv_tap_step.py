# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.base import Base
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class SvTapStep(Base):
	def __init__(self, rdfid, tpe='SvTapStep', resources=list(), class_replacements=dict()):
		Base.__init__(self, rdfid=rdfid, tpe=tpe, resources=resources, class_replacements=class_replacements)

		self.position: float = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.tap_changer import TapChanger
		self.TapChanger: TapChanger | None = None

		self.register_property(
			name='position',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A floating point number. The range is unspecified and not limited.''',
			profiles=[]
		)
		self.register_property(
			name='TapChanger',
			class_type=TapChanger,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The tap changer associated with the tap step state.''',
			profiles=[]
		)
