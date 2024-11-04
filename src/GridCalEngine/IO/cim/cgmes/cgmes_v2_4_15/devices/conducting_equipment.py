# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equipment import Equipment
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class ConductingEquipment(Equipment):
	def __init__(self, rdfid='', tpe='ConductingEquipment'):
		Equipment.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.base_voltage import BaseVoltage
		self.BaseVoltage: BaseVoltage | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.terminal import Terminal
		self.Terminals: Terminal | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.sv_status import SvStatus
		self.SvStatus: SvStatus | None = None

		self.register_property(
			name='BaseVoltage',
			class_type=BaseVoltage,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''All conducting equipment with this base voltage.  Use only when there is no voltage level container used and only one base voltage applies.  For example, not used for transformers.''',
			profiles=[]
		)
		self.register_property(
			name='Terminals',
			class_type=Terminal,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Conducting equipment have terminals that may be connected to other conducting equipment terminals via connectivity nodes or topological nodes.''',
			profiles=[]
		)
		self.register_property(
			name='SvStatus',
			class_type=SvStatus,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The status state variable associated with this conducting equipment.''',
			profiles=[]
		)
