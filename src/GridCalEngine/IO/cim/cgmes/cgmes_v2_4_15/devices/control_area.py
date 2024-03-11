# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
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
