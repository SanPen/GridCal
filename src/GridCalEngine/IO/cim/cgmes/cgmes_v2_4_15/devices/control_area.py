# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_system_resource import PowerSystemResource
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, ControlAreaTypeKind, UnitSymbol


class ControlArea(PowerSystemResource):
	def __init__(self, rdfid='', tpe='ControlArea'):
		PowerSystemResource.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.energy_area import EnergyArea
		self.EnergyArea: EnergyArea | None = None
		self.type: ControlAreaTypeKind = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.tie_flow import TieFlow
		self.TieFlow: TieFlow | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.control_area_generating_unit import ControlAreaGeneratingUnit
		self.ControlAreaGeneratingUnit: ControlAreaGeneratingUnit | None = None
		self.netInterchange: float = None
		self.pTolerance: float = None

		self.register_property(
			name='EnergyArea',
			class_type=EnergyArea,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The energy area that is forecast from this control area specification.''',
			profiles=[]
		)
		self.register_property(
			name='type',
			class_type=ControlAreaTypeKind,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The primary type of control area definition used to determine if this is used for automatic generation control, for planning interchange control, or other purposes.   A control area specified with primary type of automatic generation control could still be forecast and used as an interchange area in power flow analysis.''',
			profiles=[]
		)
		self.register_property(
			name='TieFlow',
			class_type=TieFlow,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The tie flows associated with the control area.''',
			profiles=[]
		)
		self.register_property(
			name='ControlAreaGeneratingUnit',
			class_type=ControlAreaGeneratingUnit,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The generating unit specificaitons for the control area.''',
			profiles=[]
		)
		self.register_property(
			name='netInterchange',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.W,
			description='''Product of RMS value of the voltage and the RMS value of the in-phase component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='pTolerance',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.W,
			description='''Product of RMS value of the voltage and the RMS value of the in-phase component of the current.''',
			profiles=[]
		)
