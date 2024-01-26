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
from GridCalEngine.IO.cim.cgmes_v2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_v2_4_15.acdc_terminal import ACDCTerminal
from GridCalEngine.IO.cim.cgmes_v2_4_15.acdc_converter import ACDCConverter
from GridCalEngine.IO.cim.cgmes_v2_4_15.conducting_equipment import ConductingEquipment
from GridCalEngine.IO.cim.cgmes_v2_4_15.connectivity_node import ConnectivityNode
from GridCalEngine.IO.cim.cgmes_v2_4_15.mutual_coupling import MutualCoupling
from GridCalEngine.IO.cim.cgmes_v2_4_15.mutual_coupling import MutualCoupling
from GridCalEngine.IO.cim.cgmes_v2_4_15.regulating_control import RegulatingControl
from GridCalEngine.IO.cim.cgmes_v2_4_15.tie_flow import TieFlow
from GridCalEngine.IO.cim.cgmes_v2_4_15.transformer_end import TransformerEnd
from GridCalEngine.IO.cim.cgmes_v2_4_15.sv_power_flow import SvPowerFlow
from GridCalEngine.IO.cim.cgmes_v2_4_15.topological_node import TopologicalNode


class Terminal(ACDCTerminal):
	def __init__(self, rdfid='', tpe='Terminal'):
		ACDCTerminal.__init__(self, rdfid, tpe)

		self.ConverterDCSides: ACDCConverter | None = None
		self.ConductingEquipment: ConductingEquipment | None = None
		self.ConnectivityNode: ConnectivityNode | None = None
		self.phases: PhaseCode = None
		self.HasFirstMutualCoupling: MutualCoupling | None = None
		self.HasSecondMutualCoupling: MutualCoupling | None = None
		self.RegulatingControl: RegulatingControl | None = None
		self.TieFlow: TieFlow | None = None
		self.TransformerEnd: TransformerEnd | None = None
		self.SvPowerFlow: SvPowerFlow | None = None
		self.TopologicalNode: TopologicalNode | None = None

		self.register_property(
			name='ConverterDCSides',
			class_type=ACDCConverter,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='Point of common coupling terminal for this converter DC side. It is typically the terminal on the power transformer (or switch) closest to the AC network. The power flow measurement must be the sum of all flows into the transformer.',
			profiles=[]
		)
		self.register_property(
			name='ConductingEquipment',
			class_type=ConductingEquipment,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='The conducting equipment of the terminal.  Conducting equipment have  terminals that may be connected to other conducting equipment terminals via connectivity nodes or topological nodes.',
			profiles=[]
		)
		self.register_property(
			name='ConnectivityNode',
			class_type=ConnectivityNode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='Terminals interconnected with zero impedance at a this connectivity node. ',
			profiles=[]
		)
		self.register_property(
			name='phases',
			class_type=PhaseCode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='Represents the normal network phasing condition.
If the attribute is missing three phases (ABC or ABCN) shall be assumed.',
			profiles=[]
		)
		self.register_property(
			name='HasFirstMutualCoupling',
			class_type=MutualCoupling,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='Mutual couplings associated with the branch as the first branch.',
			profiles=[]
		)
		self.register_property(
			name='HasSecondMutualCoupling',
			class_type=MutualCoupling,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='Mutual couplings with the branch associated as the first branch.',
			profiles=[]
		)
		self.register_property(
			name='RegulatingControl',
			class_type=RegulatingControl,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='The terminal associated with this regulating control.  The terminal is associated instead of a node, since the terminal could connect into either a topological node (bus in bus-branch model) or a connectivity node (detailed switch model).  Sometimes it is useful to model regulation at a terminal of a bus bar object since the bus bar can be present in both a bus-branch model or a model with switch detail.',
			profiles=[]
		)
		self.register_property(
			name='TieFlow',
			class_type=TieFlow,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='The control area tie flows to which this terminal associates.',
			profiles=[]
		)
		self.register_property(
			name='TransformerEnd',
			class_type=TransformerEnd,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='All transformer ends connected at this terminal.',
			profiles=[]
		)
		self.register_property(
			name='SvPowerFlow',
			class_type=SvPowerFlow,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='The power flow state variable associated with the terminal.',
			profiles=[]
		)
		self.register_property(
			name='TopologicalNode',
			class_type=TopologicalNode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='The terminals associated with the topological node.   This can be used as an alternative to the connectivity node path to terminal, thus making it unneccesary to model connectivity nodes in some cases.   Note that if connectivity nodes are in the model, this association would probably not be used as an input specification.',
			profiles=[]
		)
