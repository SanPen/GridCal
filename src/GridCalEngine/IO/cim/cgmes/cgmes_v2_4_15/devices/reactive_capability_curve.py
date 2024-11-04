# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.curve import Curve
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class ReactiveCapabilityCurve(Curve):
	def __init__(self, rdfid='', tpe='ReactiveCapabilityCurve'):
		Curve.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equivalent_injection import EquivalentInjection
		self.EquivalentInjection: EquivalentInjection | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.synchronous_machine import SynchronousMachine
		self.InitiallyUsedBySynchronousMachines: SynchronousMachine | None = None

		self.register_property(
			name='EquivalentInjection',
			class_type=EquivalentInjection,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The reactive capability curve used by this equivalent injection.''',
			profiles=[]
		)
		self.register_property(
			name='InitiallyUsedBySynchronousMachines',
			class_type=SynchronousMachine,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The default reactive capability curve for use by a synchronous machine.''',
			profiles=[]
		)
