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
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.acdc_terminal import ACDCTerminal
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, PhaseCode


class Terminal(ACDCTerminal):
	def __init__(self, rdfid='', tpe='Terminal'):
		ACDCTerminal.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.acdc_converter import ACDCConverter
		self.ConverterDCSides: ACDCConverter | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.auxiliary_equipment import AuxiliaryEquipment
		self.AuxiliaryEquipment: AuxiliaryEquipment | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.conducting_equipment import ConductingEquipment
		self.ConductingEquipment: ConductingEquipment | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.connectivity_node import ConnectivityNode
		self.ConnectivityNode: ConnectivityNode | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.regulating_control import RegulatingControl
		self.RegulatingControl: RegulatingControl | None = None
		self.phases: PhaseCode = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.transformer_end import TransformerEnd
		self.TransformerEnd: TransformerEnd | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.tie_flow import TieFlow
		self.TieFlow: TieFlow | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sv_power_flow import SvPowerFlow
		self.SvPowerFlow: SvPowerFlow | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.topological_node import TopologicalNode
		self.TopologicalNode: TopologicalNode | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.mutual_coupling import MutualCoupling
		self.HasSecondMutualCoupling: MutualCoupling | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.mutual_coupling import MutualCoupling
		self.HasFirstMutualCoupling: MutualCoupling | None = None

		self.register_property(
			name='ConverterDCSides',
			class_type=ACDCConverter,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''All converters' DC sides linked to this point of common coupling terminal.''',
			profiles=[]
		)
		self.register_property(
			name='AuxiliaryEquipment',
			class_type=AuxiliaryEquipment,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The auxiliary equipment connected to the terminal.''',
			profiles=[]
		)
		self.register_property(
			name='ConductingEquipment',
			class_type=ConductingEquipment,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The conducting equipment of the terminal.  Conducting equipment have  terminals that may be connected to other conducting equipment terminals via connectivity nodes or topological nodes.''',
			profiles=[]
		)
		self.register_property(
			name='ConnectivityNode',
			class_type=ConnectivityNode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The connectivity node to which this terminal connects with zero impedance.''',
			profiles=[]
		)
		self.register_property(
			name='RegulatingControl',
			class_type=RegulatingControl,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The controls regulating this terminal.''',
			profiles=[]
		)
		self.register_property(
			name='phases',
			class_type=PhaseCode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Represents the normal network phasing condition. If the attribute is missing, three phases (ABC) shall be assumed, except for terminals of grounding classes (specializations of EarthFaultCompensator, GroundDisconnector, and Ground) which will be assumed to be N. Therefore, phase code ABCN is explicitly declared when needed, e.g. for star point grounding equipment.
The phase code on terminals connecting same ConnectivityNode or same TopologicalNode as well as for equipment between two terminals shall be consistent.''',
			profiles=[]
		)
		self.register_property(
			name='TransformerEnd',
			class_type=TransformerEnd,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''All transformer ends connected at this terminal.''',
			profiles=[]
		)
		self.register_property(
			name='TieFlow',
			class_type=TieFlow,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The control area tie flows to which this terminal associates.''',
			profiles=[]
		)
		self.register_property(
			name='SvPowerFlow',
			class_type=SvPowerFlow,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The power flow state variable associated with the terminal.''',
			profiles=[]
		)
		self.register_property(
			name='TopologicalNode',
			class_type=TopologicalNode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The topological node associated with the terminal.   This can be used as an alternative to the connectivity node path to topological node, thus making it unnecessary to model connectivity nodes in some cases.   Note that the if connectivity nodes are in the model, this association would probably not be used as an input specification.''',
			profiles=[]
		)
		self.register_property(
			name='HasSecondMutualCoupling',
			class_type=MutualCoupling,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Mutual couplings with the branch associated as the first branch.''',
			profiles=[]
		)
		self.register_property(
			name='HasFirstMutualCoupling',
			class_type=MutualCoupling,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Mutual couplings associated with the branch as the first branch.''',
			profiles=[]
		)
