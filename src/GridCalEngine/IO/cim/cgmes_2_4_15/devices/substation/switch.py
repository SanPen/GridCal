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
import GridCalEngine
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.conducting_equipment import ConductingEquipment
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.dipole import DiPole
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class Switch(DiPole, ConductingEquipment):

    def __init__(self, rdfid, tpe):
        DiPole.__init__(self, rdfid, tpe)
        ConductingEquipment.__init__(self, rdfid, tpe)

        self.open: bool = False
        self.normalOpen: bool = True
        self.ratedCurrent: float = 0.0
        self.retained: bool = False

        # self.EquipmentContainer: EquipmentContainer = None
        # self.BaseVoltage: BaseVoltage = None

        self.register_property(name='open',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               comment='The standard does not provide a proper description',
                               profiles=[cgmesProfile.SSH])

        self.register_property(name='normalOpen',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The attribute is used in cases when no "
                                           "Measurement for the status value is present. "
                                           "If the Switch has a status measurement the "
                                           "Discrete.normalValue is expected to match "
                                           "with the Switch.normalOpen.",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='ratedCurrent',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.A,
                               description="The maximum continuous current carrying "
                                           "capacity in amps governed by the device "
                                           "material and construction.",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='retained',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               comment='Branch is retained in a bus branch model. '
                                       'The flow through retained switches will normally '
                                       'be calculated in power flow.',
                               profiles=[cgmesProfile.EQ])

        # self.register_property(name='BaseVoltage',
        #                        class_type=BaseVoltage,
        #                        multiplier=UnitMultiplier.none,
        #                        unit=UnitSymbol.none,
        #                        description="",
        #                        comment='')
        #
        # self.register_property(name='EquipmentContainer',
        #                        class_type=EquipmentContainer,
        #                        multiplier=UnitMultiplier.none,
        #                        unit=UnitSymbol.none,
        #                        description="",
        #                        comment='')

    def get_nodes(self):
        """
        Get the TopologyNodes of this branch
        :return: two TopologyNodes or nothing
        """
        try:
            terminals = list(self.references_to_me['Terminal'])

            if len(terminals) == 2:
                n1 = GridCalEngine.IO.cim.cgmes_2_4_15.devices.topological_node.TopologicalNode
                n2 = GridCalEngine.IO.cim.cgmes_2_4_15.devices.topological_node.TopologicalNode
                return n1, n2
            else:
                return None, None

        except KeyError:
            return None, None
